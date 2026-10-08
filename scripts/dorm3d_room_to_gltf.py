"""dorm3d 房间场景 → glTF 2.0 (.glb)：把「哪个物体用哪份网格」落成能在浏览器里显示的房间。

跨包解析复用 `diag/dorm3d_pptr_resolve.py`（判据已打通），GLB 容器与镜像 X 转换复用
`dorm3d_to_gltf.py`（WF-32 已验证），**不重写第二套**。

    py -3 scripts/dorm3d_room_to_gltf.py --only "Bed,Sofa,pre_db_chandelier02,pre_db_carpet06,WallLeft,Floor"
    py -3 scripts/dorm3d_room_to_gltf.py --out .diag/dorm3d_room/room.glb
    py -3 scripts/dorm3d_room_to_gltf.py --verify .diag/dorm3d_room/room.glb
    py -3 scripts/dorm3d_room_to_gltf.py --out ... --include-inactive    # 反向对照：该判红
    py -3 scripts/dorm3d_room_to_gltf.py --out ... --no-mirror           # 反向对照：该判红

三件必须知道的口径：
1. **网格解码用 UnityPy 自己的 `MeshHelper.MeshHandler`**，不是 §116 那套反解。
   原因（实测）：房间 FBX 网格把 Normal 通道的 `dimension` 存成打包字节（读到 52，UnityPy 自己
   按 `dimension & 0xF` 用），`probe.candidate_layouts` 的"非末段通道宽度可由相邻偏移差整除推出"
   这条前提不成立 ⇒ 直接 KeyError。MeshHandler 已在天狼星 `body` 上跨实现对齐（13,412 顶点、
   首顶点权重 (32768,32767,0,0)、骨号 (27,31) 与 step 5 浏览器验过的值逐位相同），
   且内联与 `.resS` 流式两种数据都覆盖。
2. **只画激活对象**：348 个 MeshFilter 里 **49 个挂在关闭态对象上**（首因 39 个是 `night` 祖先），
   日夜两套在同一位置，都画会叠面（§55「只画游戏里开着的层」的 3D 版）。
3. **31 个物体用的是 Unity 内置原语**（盘上没有对应文件），一律按**单位立方体**占位并打
   `extras.placeholder` 标记 —— 不声明它到底是 Cube/Plane/Cylinder（按 path_id 只分 3 组：
   10202×28 / 10206×2 / 10209×1），这一部分**不算已还原**。

光照：包里 21 盏 = Point 7 / Spot 4 / Directional 6 / **Area 4**（glTF 无面光源，Area 如实跳过并计数）。
Unity 与 glTF 的光强单位不同（cd/m² vs lux/无量纲），数值**原样写出**，观感对齐交给 three.js 那步目视裁定。
"""
import argparse
import io
import json
import math
import os
import struct
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)

import UnityPy                                         # noqa: E402
from UnityPy.helpers.MeshHelper import MeshHandler     # noqa: E402

import dorm3d_to_gltf as G                             # noqa: E402
import dorm3d_pptr_resolve as P                        # noqa: E402

UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
LIGHT_TYPE = {0: "area", 1: "directional", 2: "point", 3: "spot"}
KHR = "KHR_lights_punctual"


def die(msg, code=1):
    print("[FAIL] " + msg)
    sys.exit(code)


def unit_cube():
    """24 顶点 / 12 三角的单位立方体（边长 1，中心在原点）—— 内置原语的占位形状。"""
    s = 0.5
    faces = [  # (4 角逆时针, 法线)
        ([(-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s)], (0, 0, 1)),
        ([(-s, -s, -s), (-s, s, -s), (s, s, -s), (s, -s, -s)], (0, 0, -1)),
        ([(-s, s, s), (-s, s, -s), (s, s, -s), (s, s, s)], (0, 1, 0)),
        ([(-s, -s, s), (s, -s, s), (s, -s, -s), (-s, -s, -s)], (0, -1, 0)),
        ([(-s, -s, s), (-s, s, s), (-s, s, -s), (-s, -s, -s)], (-1, 0, 0)),
        ([(s, -s, s), (s, -s, -s), (s, s, -s), (s, s, s)], (1, 0, 0)),
    ]
    pos, nor, uv, tris = [], [], [], []
    for corners, n in faces:
        base = len(pos)
        for i, c in enumerate(corners):
            pos.append([c[0], c[1], c[2]])
            nor.append([n[0], n[1], n[2]])
            uv.append([(0, 0), (1, 0), (1, 1), (0, 1)][i])
        tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    return pos, nor, uv, [tris]


def mesh_from_handler(reader, mirror, flipuv):
    """MeshHandler 解码 → 顶点/法线/UV/按 submesh 的索引 + 源包声明值（供独立锚点比对）。"""
    m = reader.read()
    h = MeshHandler(m)
    h.process()
    verts = [list(v[:3]) for v in (h.m_Vertices or [])]
    normals = [list(v[:3]) for v in (h.m_Normals or [])]
    uvs = [list(v[:2]) for v in (h.m_UV0 or [])] if h.m_UV0 else []
    if mirror:
        for v in verts:
            v[0] = -v[0]
        for v in normals:
            v[0] = -v[0]
    if flipuv:
        for t in uvs:
            t[1] = 1.0 - t[1]
    tris = [list(t) for t in (h.get_triangles() or [])]
    if mirror:
        tris = [[(c, b, a) for (a, b, c) in t] for t in tris]
    aabb = getattr(m, "m_LocalAABB", None)
    decl = None
    if aabb is not None:
        c, e = aabb.m_Center, aabb.m_Extent
        decl = ([float(c.x), float(c.y), float(c.z)], [float(e.x), float(e.y), float(e.z)])
    return {"name": m.m_Name, "verts": verts, "normals": normals, "uvs": uvs, "tris": tris,
            "declared_v": int(m.m_VertexData.m_VertexCount or 0), "aabb": decl,
            "declared_idx": int(sum(int(getattr(s, "indexCount", 0) or 0)
                                    for s in (getattr(m, "m_SubMeshes", None) or []))),
            "submesh_decl": len(getattr(m, "m_SubMeshes", None) or [])}


def add_mesh(gltf, buf, rec, mats, placeholder=None):
    """一个 (网格, 材质序列) 组合出一个 glTF mesh；每个 submesh 出一个 primitive。"""
    n = len(rec["verts"])
    if not n:
        return None
    pacc = G.add_accessor(gltf, buf, "f", [x for v in rec["verts"] for x in v], n, "VEC3", G.ARR_BUFFER,
                          vmin=[min(v[i] for v in rec["verts"]) for i in range(3)],
                          vmax=[max(v[i] for v in rec["verts"]) for i in range(3)])
    nacc = (G.add_accessor(gltf, buf, "f", [x for v in rec["normals"] for x in v], n, "VEC3", G.ARR_BUFFER)
            if len(rec["normals"]) == n else None)
    uacc = (G.add_accessor(gltf, buf, "f", [x for v in rec["uvs"] for x in v], n, "VEC2", G.ARR_BUFFER)
            if len(rec["uvs"]) == n else None)
    primitives = []
    for si, tri in enumerate(rec["tris"]):
        flat = [i for t in tri for i in t]
        if not flat:
            continue
        iacc = G.add_accessor(gltf, buf, "H" if n < 65536 else "I",
                              flat, len(flat), "SCALAR", 34963)
        attrs = {"POSITION": pacc}
        if nacc is not None:
            attrs["NORMAL"] = nacc
        if uacc is not None:
            attrs["TEXCOORD_0"] = uacc
        mat = mats[si] if si < len(mats) else (mats[-1] if mats else None)
        primitives.append({"attributes": attrs, "indices": iacc, "material": mat, "mode": 4})
    if not primitives:
        return None
    mesh = {"name": rec["name"], "primitives": primitives}
    if placeholder:
        mesh["extras"] = {"placeholder": placeholder}
    gltf["meshes"].append(mesh)
    return len(gltf["meshes"]) - 1


def material_of(gltf, buf, res, mat_reader, with_textures, tex_cache, texstat):
    key = (P.cab_key(mat_reader.assets_file.name), mat_reader.path_id)
    if key in gltf["_matkey"]:
        return gltf["_matkey"][key]
    mt = mat_reader.read()
    sp = getattr(mt, "m_SavedProperties", None)
    entry = {"name": mt.m_Name, "doubleSided": True,
             "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 0.9}}
    colors = dict(list(getattr(sp, "m_Colors", None) or []))
    base = colors.get("_BaseColor") or colors.get("_Color")
    if base is not None:
        entry["pbrMetallicRoughness"]["baseColorFactor"] = [
            float(getattr(base, k, d)) for k, d in (("r", 1), ("g", 1), ("b", 1), ("a", 1))]
    if with_textures:
        tried = 0
        for slot, env in list(getattr(sp, "m_TexEnvs", None) or []):
            tp = getattr(env, "m_Texture", None)
            if tp is None or not (getattr(tp, "path_id", 0) or 0):
                continue
            tried += 1
            bucket, cab, pid = res.classify(mat_reader.assets_file, tp)
            tgt, err = res.fetch(gltf["_own"], bucket, cab, pid)
            if tgt is None or tgt.type.name != "Texture2D":
                texstat["miss"].append("%s/%s: %s" % (mt.m_Name, slot,
                                                      err or ("类型 %s" % (tgt.type.name if tgt else "-"))))
                continue
            tk = (P.cab_key(cab or ""), pid)
            if tk in tex_cache:
                ti = tex_cache[tk]
            else:
                tobj = tgt.read()
                try:
                    img = tobj.image
                except Exception as ex:
                    print("      贴图 %s(%s) 解码失败 %s（跳过，不放占位）"
                          % (slot, tobj.m_Name, type(ex).__name__))
                    continue
                b = io.BytesIO()
                img.convert("RGBA").save(b, format="PNG")
                raw = b.getvalue()
                gltf["images"].append({"bufferView": buf.add(raw), "mimeType": "image/png",
                                       "name": tobj.m_Name})
                gltf["textures"].append({"source": len(gltf["images"]) - 1})
                tex_cache[tk] = len(gltf["textures"]) - 1
                ti = tex_cache[tk]
            entry["pbrMetallicRoughness"]["baseColorTexture"] = {"index": ti, "texCoord": 0}
            entry["_unitySlot"] = slot
            texstat["hit"] += 1
            break
        if "baseColorTexture" not in entry["pbrMetallicRoughness"]:
            texstat["none"].append(mt.m_Name)
    gltf["materials"].append(entry)
    i = len(gltf["materials"]) - 1
    gltf["_matkey"][key] = i
    return i


def scene_tables(env):
    own, trs, tr_of_go, rend_of_go = {}, [], {}, {}
    for o in env.objects:
        own[(P.cab_key(o.assets_file.name), o.path_id)] = o
        if o.type.name == "Transform":
            sfn = P.cab_key(o.assets_file.name)
            trs.append(o)
            gp = getattr(o.read().m_GameObject, "path_id", 0) or 0
            if gp:
                tr_of_go[(sfn, gp)] = o.path_id
    for o in env.objects:
        if o.type.name in ("MeshRenderer", "SkinnedMeshRenderer"):
            gp = getattr(o.read(), "m_GameObject", None)
            gp = getattr(gp, "path_id", 0) or 0 if gp is not None else 0
            if gp:
                rend_of_go[(P.cab_key(o.assets_file.name), gp)] = o
    return own, trs, tr_of_go, rend_of_go


def jobs_from_scene(env, res, own, trs, tr_of_go, rend_of_go, only, limit, include_inactive):
    node_of = {o.path_id: i for i, o in enumerate(trs)}
    name_of = {}
    for o in trs:
        sfn = P.cab_key(o.assets_file.name)
        gp = getattr(o.read().m_GameObject, "path_id", 0) or 0
        g = own.get((sfn, gp))
        name_of[o.path_id] = g.read().m_Name if g is not None else ""
    want = set(x.strip() for x in only.split(",") if x.strip()) if only else None
    jobs, skipped, builtin_groups, unresolved = [], 0, {}, 0
    for o in env.objects:
        if o.type.name != "MeshFilter":
            continue
        sfn = P.cab_key(o.assets_file.name)
        mf = o.read()
        goid = getattr(mf.m_GameObject, "path_id", 0) or 0
        trp = tr_of_go.get((sfn, goid))
        gname = name_of.get(trp, "?")
        if want and gname not in want:
            continue
        on, blocker = P.go_active(own, tr_of_go, sfn, goid)
        if not on and not include_inactive:
            skipped += 1
            continue
        if trp is None:
            unresolved += 1
            continue
        bucket, cab, pid = res.classify(o.assets_file, mf.m_Mesh)
        rdr, err = (None, None)
        if bucket in ("self", "ext_hit"):
            rdr, err = res.fetch(own, bucket, cab, pid)
            if rdr is None or rdr.type.name != "Mesh":
                jobs.append({"node": node_of[trp], "name": gname,
                             "error": err or "目标不是 Mesh"})
                continue
        elif bucket != "builtin":
            jobs.append({"node": node_of[trp], "name": gname, "error": "分桶 %s 不可画" % bucket})
            continue
        else:
            builtin_groups[(cab, pid)] = builtin_groups.get((cab, pid), 0) + 1
        rend = rend_of_go.get((sfn, goid))
        mats = []
        if rend is not None:
            for mp in (rend.read().m_Materials or []):
                b2, c2, p2 = res.classify(rend.assets_file, mp)
                t2, _e2 = res.fetch(own, b2, c2, p2)
                mats.append(t2 if (t2 is not None and t2.type.name == "Material") else None)
        jobs.append({"node": node_of[trp], "name": gname, "bucket": bucket, "cab": cab,
                     "path_id": pid, "reader": rdr, "mats": mats, "builtin_key": (cab, pid) if rdr is None else None})
        if limit and len(jobs) >= limit:
            break
    return jobs, node_of, name_of, skipped, builtin_groups, unresolved


def add_lights(env, own, gltf, nodes, tr_of_go, node_of):
    """21 盏灯 → KHR_lights_punctual；Area 灯 glTF 没有对应类型，如实跳过并计数。"""
    lights, skipped = [], {"area": 0, "inactive": 0}
    for o in env.objects:
        if o.type.name != "Light":
            continue
        sfn = P.cab_key(o.assets_file.name)
        gp = getattr(o.read().m_GameObject, "path_id", 0) or 0
        trp = tr_of_go.get((sfn, gp))
        L = o.read()
        kind = LIGHT_TYPE.get(int(L.m_Type) if not hasattr(L.m_Type, "value") else L.m_Type.value,
                              str(L.m_Type))
        if kind == "area":
            skipped["area"] += 1
            continue
        if trp is None or not P.go_active(own, tr_of_go, sfn, gp)[0]:
            skipped["inactive"] += 1
            continue
        col = [float(getattr(L.m_Color, k, 1.0)) for k in ("r", "g", "b")]
        entry = {"name": nodes[node_of[trp]].get("name") or ("light_%d" % len(lights)),
                 "type": kind, "color": col,
                 "intensity": float(L.m_Intensity)}
        if kind in ("point", "spot"):
            entry["range"] = float(getattr(L, "m_Range", 0.0) or 0.0)
        if kind == "spot":
            outer = math.radians(float(getattr(L, "m_SpotAngle", 30.0) or 30.0))
            inner = float(getattr(L, "m_InnerSpotAngle", 21.5) or 21.5)
            entry["outerConeAngle"] = outer
            entry["innerConeAngle"] = math.radians(inner)
        nodes[node_of[trp]].setdefault("extensions", {})[KHR] = {"light": len(lights)}
        lights.append(entry)
    if lights:
        gltf.setdefault("extensionsUsed", []).append(KHR)
        gltf["extensions"] = {KHR: {"lights": lights}}
    return lights, skipped


def build(scene, out=None, only=None, limit=None, with_textures=True,
          include_inactive=False, mirror=True, flipuv=True, verbose=True, truth_out=None):
    t0 = time.time()
    deps, _k = P.dep_bundle_paths(scene, P.DEP_MANIFEST)
    index, scanned, isec, _dup = P.build_index([P.DEF_DIR], extra_bundles=deps)
    res = P.Resolver(index)
    env = UnityPy.load(scene)
    own, trs, tr_of_go, rend_of_go = scene_tables(env)
    jobs, node_of, name_of, skipped, bgroups, unresolved = jobs_from_scene(
        env, res, own, trs, tr_of_go, rend_of_go, only, limit, include_inactive)
    nodes, roots, _ = G.build_nodes(trs, node_of, name_of, own)
    gltf = {"asset": {"version": "2.0", "generator": "dorm3d_room_to_gltf"},
            "scene": 0, "scenes": [{"nodes": sorted(set(roots))}],
            "nodes": nodes, "meshes": [], "materials": [],
            "accessors": [], "bufferViews": [], "images": [], "textures": []}
    gltf["_own"], gltf["_matkey"], gltf["_meshkey"] = own, {}, {}
    buf = G.Buf()
    anchors, errors, mesh_cache, tex_cache = [], [], {}, {}
    world = unity_world_mats(trs)
    texstat = {"hit": 0, "miss": [], "none": []}
    pos_total = tri_total = prim_total = wb_skipped = 0
    wmin = wmax = None
    n_place = 0
    for j in jobs:
        if j.get("error"):
            errors.append(j)
            continue
        if j["reader"] is None:
            pv, nv, uv, tris = unit_cube()
            rec = {"name": "%s__PLACEHOLDER" % j["name"], "verts": pv, "normals": nv,
                   "uvs": uv, "tris": tris, "declared_v": len(pv), "declared_idx": 36,
                   "aabb": None, "submesh_decl": 1}
            ph = "cube-for-builtin(path_id=%s)" % j["builtin_key"][1]
            n_place += 1
        else:
            mk = (P.cab_key(j["cab"] or "self"), j["path_id"])
            rec = mesh_cache.get(mk) or mesh_from_handler(j["reader"], mirror, flipuv)
            mesh_cache[mk] = rec
            ph = None
        mvals = [material_of(gltf, buf, res, mi, with_textures, tex_cache, texstat)
                 for mi in j["mats"] if mi is not None]
        key = (mk_or_none(j), ph, tuple(mvals))
        if key in gltf["_meshkey"]:
            midx = gltf["_meshkey"][key]
        else:
            midx = add_mesh(gltf, buf, rec, mvals, placeholder=ph)
            gltf["_meshkey"][key] = midx
        if midx is None:
            errors.append({"name": j["name"], "error": "无有效 submesh"})
            continue
        gltf["nodes"][j["node"]]["mesh"] = midx
        got = rec["verts"]
        mn = [min(v[i] for v in got) for i in range(3)]
        mx = [max(v[i] for v in got) for i in range(3)]
        calc_c = [(a + b) / 2 for a, b in zip(mn, mx)]
        calc_e = [(b - a) / 2 for a, b in zip(mn, mx)]
        dev = 0.0
        if rec["aabb"]:
            dc, de = rec["aabb"]
            if mirror:
                dc = [-dc[0], dc[1], dc[2]]
            span = max(max(abs(x) for x in de), 1e-6)
            dev = max(max(abs(a - b) for a, b in zip(dc, calc_c)),
                      max(abs(a - b) for a, b in zip(de, calc_e))) / span
        ntri = sum(len(t) for t in rec["tris"])
        anchors.append({"object": j["name"], "mesh": rec["name"], "verts": len(got),
                        "declared_v": rec["declared_v"], "tris": ntri,
                        "submeshes": len(rec["tris"]), "submesh_decl": rec["submesh_decl"],
                        "aabb_dev_pct": round(dev * 100, 3), "placeholder": ph,
                        "mats": [gltf["materials"][i]["name"] for i in mvals]})
        # Unity 侧口径的总量（给 three.js 探针当**独立裁判**：这些数全部来自源包声明字段，
        # 不是我写进 GLB 的那份字节）
        npr = len([t for t in rec["tris"] if t])
        pos_total += rec["declared_v"] * npr
        tri_total += rec["declared_idx"] // 3
        prim_total += npr
        if rec["aabb"]:
            A, t = world(j["node"])
            dc, de = rec["aabb"]
            ext = [sum(abs(A[i][k]) * de[k] for k in range(3)) for i in range(3)]
            anchors[-1]["center"] = [round(v, 4) for v in _mx(_apply(A, t, dc))]
            anchors[-1]["size"] = [round(2 * e, 4) for e in ext]
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz in (-1, 1):
                        p = _apply(A, t, [dc[0] + sx * de[0], dc[1] + sy * de[1], dc[2] + sz * de[2]])
                        p = [-p[0], p[1], p[2]]
                        wmin = [min(a, b) for a, b in zip(wmin, p)] if wmin else list(p)
                        wmax = [max(a, b) for a, b in zip(wmax, p)] if wmax else list(p)
        else:
            wb_skipped += 1
    truth = {"scene": P.rel(scene), "nodes": len(nodes), "objects": len(anchors),
             "prim_total": prim_total, "pos_total": pos_total, "tri_total": tri_total,
             "world_box": [wmin, wmax], "world_box_skipped": wb_skipped,
             "placeholders": n_place, "materials": len(gltf["materials"]),
             "tex_hit": texstat["hit"], "tex_miss": len(texstat["miss"]),
             "tex_no_slot": len(texstat["none"]),
             "placeholder_basis": "占位对象按本装配器生成的单位立方体计入总数(24 顶点/12 三角)，"
                                  "其 Unity 侧声明值不可得；世界盒不含占位对象",
             "textures": len(gltf["images"]), "skipped_inactive": skipped, "mirror": mirror,
             "per_object": [{"object": a["object"], "mesh": a["mesh"], "verts": a["declared_v"],
                             "tris": a["tris"], "submeshes": a["submesh_decl"],
                             "center": a.get("center"), "size": a.get("size"),
                             "placeholder": bool(a["placeholder"])} for a in anchors]}
    lights, lskip = add_lights(env, own, gltf, nodes, tr_of_go, node_of)
    truth["lights"] = len(lights)
    truth["lights_skipped"] = lskip
    cam = None
    for o in env.objects:
        if o.type.name != "Camera":
            continue
        C = o.read()
        gp = getattr(C.m_GameObject, "path_id", 0) or 0
        sfn = P.cab_key(o.assets_file.name)
        i = node_of.get(tr_of_go.get((sfn, gp), -1))
        if i is None:
            continue
        A, t = world(i)

        def axis(e):
            return [sum(A[r][k] * e[k] for k in range(3)) for r in range(3)]
        cam = {"pos": [round(v, 4) for v in _mx(t)],
               "fwd": [round(v, 4) for v in _mx(axis((0, 0, 1)))],
               "up": [round(v, 4) for v in _mx(axis((0, 1, 0)))],
               "note": "这台 Camera 的 TypeTree 里没有 m_FieldOfView/m_Near/m_Far"
                       "（只有镜头/物理相机类字段）⇒ 视场角不是包里的权威值，截图用的 FOV 由观看者定"}
        break
    truth["camera"] = cam
    gltf["buffers"] = [{"byteLength": len(buf.data)}]
    gltf["bufferViews"] = buf.views
    used = set(n["mesh"] for n in nodes if "mesh" in n)
    orphans = [i for i in range(len(gltf["meshes"])) if i not in used]
    gltf["extras"] = {"scene": P.rel(scene), "jobs": len(jobs), "skipped_inactive": skipped,
                      "builtin_groups": {"%s/%s" % k: v for k, v in bgroups.items()},
                      "placeholders": n_place, "lights": len(lights), "lights_skipped": lskip,
                      "mirror": mirror, "flipuv": flipuv, "with_textures": with_textures}
    for k in ("_own", "_matkey", "_meshkey"):
        gltf.pop(k, None)
    if out:
        G.write_glb(out, gltf, buf.data)
        tp = truth_out or (out + ".truth.json")
        json.dump(truth, open(tp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if verbose:
            print("  真值 %s: primitive %d / position 计数 %d / 三角 %d / 世界盒 %s（无 AABB 跳过 %d）"
                  % (P.rel(tp), prim_total, pos_total, tri_total,
                     [[round(v, 3) for v in wmin], [round(v, 3) for v in wmax]] if wmin else "空",
                     wb_skipped))
    if verbose:
        print("索引 %d 包 / %.1f 秒 | 工单 %d（跳过关闭态 %d，无 Transform %d）| 节点 %d | "
              "网格 %d（占位 %d）| 材质 %d | 贴图 %d | 灯 %d（跳过 %s）"
              % (scanned, isec, len(jobs), skipped, unresolved, len(nodes),
                 len(gltf["meshes"]), n_place, len(gltf["materials"]), len(gltf["images"]),
                 len(lights), lskip))
        print("  %-26s %-26s %7s %7s %7s %5s %8s %s"
              % ("对象", "网格", "顶点", "声明", "三角", "subm", "AABB差%", "材质"))
        for a in anchors:
            print("  %-26s %-26s %7d %7d %7d %5d %8.3f %s%s"
                  % (a["object"][:26], a["mesh"][:26], a["verts"], a["declared_v"], a["tris"],
                     a["submeshes"], a["aabb_dev_pct"], ",".join(a["mats"])[:22],
                     "  [占位]" if a["placeholder"] else ""))
        badv = [a for a in anchors if a["verts"] != a["declared_v"]]
        badsub = [a for a in anchors if a["submeshes"] != a["submesh_decl"]]
        bigdev = [a for a in anchors if a["aabb_dev_pct"] > 3]
        print("  锚点: 顶点数 vs 源包声明 不符 %d | submesh 数不符 %d | AABB 偏差>3%% %d | "
              "解包错误 %d | orphan mesh %d" % (len(badv), len(badsub), len(bigdev),
                                                len(errors), len(orphans)))
        print("  材质贴图: 挂上 %d 张引用 / 解析失败 %d / 该材质本就无可解析贴图槽 %d"
              % (texstat["hit"], len(texstat["miss"]), len(texstat["none"])))
        for s in texstat["miss"][:4]:
            print("    [贴图未解析] %s" % s)
        for e in errors[:6]:
            print("    [错] %s: %s" % (e.get("name"), e.get("error")))
        for a in badv[:6] + bigdev[:6]:
            print("    [红] %s 顶点 %d vs 声明 %d，AABB 差 %.2f%%"
                  % (a["object"], a["verts"], a["declared_v"], a["aabb_dev_pct"]))
        if out:
            print("  产物 %s (%.1f KB) / 总耗时 %.1f 秒"
                  % (P.rel(out), os.path.getsize(out) / 1024.0, time.time() - t0))
    return gltf, anchors, errors


def mk_or_none(j):
    return (P.cab_key(j["cab"] or "self"), j["path_id"]) if j["reader"] is not None else None


def _quat_mat(t, r, s):
    """四元数 + 缩放 -> 3x3 线性部分（行主序 m[a][b]，点按 p·M 的行向量写法配 t）。"""
    x, y, z, w = r
    n = (x * x + y * y + z * z + w * w) or 1.0
    k = math.sqrt(2.0 / n)
    x, y, z, w = x * k, y * k, z * k, w * k
    m = [[1 - (y * y + z * z), x * y - z * w, x * z + y * w],
         [x * y + z * w, 1 - (x * x + z * z), y * z - x * w],
         [x * z - y * w, y * z + x * w, 1 - (x * x + y * y)]]
    return [[m[a][b] * s[b] for b in range(3)] for a in range(3)], list(t)


def _mul(A, tA, B, tB):
    return ([[sum(A[a][k] * B[k][b] for k in range(3)) for b in range(3)] for a in range(3)],
            [sum(A[a][k] * tB[k] for k in range(3)) + tA[a] for a in range(3)])


def _apply(A, t, p):
    return [sum(A[i][k] * p[k] for k in range(3)) + t[i] for i in range(3)]


def unity_world_mats(trs):
    """按源包的 Transform 链复算每个节点序号的世界矩阵（行主序 3x3 + 平移）。"""
    idx_of_pid = {o.path_id: i for i, o in enumerate(trs)}
    utrs, upar = {}, {}
    for i, o in enumerate(trs):
        t = o.read()
        p, r, s = t.m_LocalPosition, t.m_LocalRotation, t.m_LocalScale
        utrs[i] = ((float(p.x), float(p.y), float(p.z)),
                   (float(r.x), float(r.y), float(r.z), float(r.w)),
                   (float(s.x), float(s.y), float(s.z)))
        fp = getattr(getattr(t, "m_Father", None), "path_id", 0) or 0
        upar[i] = idx_of_pid.get(fp) if fp else None
    memo = {}

    def world(i):
        if i in memo:
            return memo[i]
        A, t = _quat_mat(*utrs[i])
        pi = upar.get(i)
        if pi is not None and pi != i:
            PA, Pt = world(pi)
            A, t = _mul(PA, Pt, A, t)
        memo[i] = (A, t)
        return A, t
    return world


def _mx(p):
    """Unity 世界量 → glTF 世界量：镜像 X，只动 x（`M_gltf = C·M_unity·C` 的作用结果）。"""
    return [-p[0], p[1], p[2]]


def mirror_anchor(g, bin_off, binraw, scene):
    """跨源验镜像只做了一次：glTF 世界盒中心（全取自**文件字节**）应恰为
    Unity 世界盒中心（全取自**源包声明**：Transform 链 + Mesh.m_LocalAABB）的 x 反号、y/z 相等。

    两侧都由各自的 TRS 复算，所以「漏做一次镜像」和「做了两次」都会红；
    而只比我自己那套转换的断言对此是恒真的。
    """
    env = UnityPy.load(scene)
    own, trs, tr_of_go, _rend = scene_tables(env)
    if len(trs) != len(g["nodes"]):
        return ["镜像锚点前提不成立: 源包 Transform %d 个 vs 文件节点 %d 个"
                % (len(trs), len(g["nodes"]))]
    deps, _k = P.dep_bundle_paths(scene, P.DEP_MANIFEST)
    index, _n, _s, _d = P.build_index([P.DEF_DIR], extra_bundles=deps)
    res = P.Resolver(index)
    world = unity_world_mats(trs)

    kids = {}
    for i, n in enumerate(g["nodes"]):
        for c in n.get("children", []):
            kids[c] = i
    gmemo = {}

    def gltf_world(i):
        if i in gmemo:
            return gmemo[i]
        n = g["nodes"][i]
        A, t = _quat_mat(n.get("translation", [0, 0, 0]), n.get("rotation", [0, 0, 0, 1]),
                         n.get("scale", [1, 1, 1]))
        p = kids.get(i)
        if p is not None:
            PA, Pt = gltf_world(p)
            A, t = _mul(PA, Pt, A, t)
        gmemo[i] = (A, t)
        return A, t

    local_box = {}
    for mi, mesh in enumerate(g["meshes"]):
        mn = mx = None
        for pr in mesh["primitives"]:
            acc = g["accessors"][pr["attributes"]["POSITION"]]
            mn = list(acc["min"]) if mn is None else [min(a, b) for a, b in zip(mn, acc["min"])]
            mx = list(acc["max"]) if mx is None else [max(a, b) for a, b in zip(mx, acc["max"])]
        local_box[mi] = (mn, mx)

    bad, checked, worst = [], 0, 0.0
    skipped_ph, skipped_centered = 0, 0
    idx_of_go = {}
    for i, o in enumerate(trs):
        gp = getattr(o.read().m_GameObject, "path_id", 0) or 0
        if gp:
            idx_of_go[(P.cab_key(o.assets_file.name), gp)] = i
    for o in env.objects:
        if o.type.name != "MeshFilter":
            continue
        sfn = P.cab_key(o.assets_file.name)
        mf = o.read()
        goid = getattr(mf.m_GameObject, "path_id", 0) or 0
        i = idx_of_go.get((sfn, goid))
        if i is None:
            continue
        node = g["nodes"][i]
        if "mesh" not in node:
            continue
        mesh = g["meshes"][node["mesh"]]
        if (mesh.get("extras") or {}).get("placeholder"):
            skipped_ph += 1
            continue
        # 名字对齐守卫：源包第 i 个 Transform 的 GameObject 名必须等于文件第 i 个节点名
        go = own.get((sfn, goid))
        gname = go.read().m_Name if go is not None else ""
        bucket, cab, pid = res.classify(o.assets_file, mf.m_Mesh)
        tgt, err = res.fetch(own, bucket, cab, pid)
        if tgt is None or tgt.type.name != "Mesh":
            bad.append("锚点回指失败 node %d(%s): %s" % (i, mesh["name"], err or "非 Mesh"))
            continue
        if node.get("name") and gname and node["name"] != gname:
            bad.append("节点序不对齐 node %d: 文件=%s 源包=%s" % (i, node["name"], gname))
            continue
        c = tgt.read().m_LocalAABB.m_Center
        uc = [float(c.x), float(c.y), float(c.z)]
        # 敏感度守卫：本地盒中心在原点上时，做没做镜像两种结果重合，这条对象**给不出证据**
        if max(abs(v) for v in uc) < 1e-3:
            skipped_centered += 1
            continue
        A, t = world(i)
        uw = _apply(A, t, uc)
        GA, Gt = gltf_world(i)
        mn, mx = local_box[node["mesh"]]
        gw = _apply(GA, Gt, [(a + b) / 2 for a, b in zip(mn, mx)])
        scale = max(1.0, max(abs(v) for v in uw))
        err_rel = max(abs(gw[0] + uw[0]), abs(gw[1] - uw[1]), abs(gw[2] - uw[2])) / scale
        worst = max(worst, err_rel)
        checked += 1
        if err_rel > 2e-3:
            bad.append("镜像锚点 %s: gltf=(%.4f,%.4f,%.4f) 应等于 -unity=(%.4f,%.4f,%.4f)，相对差 %.1e"
                       % (mesh["name"], gw[0], gw[1], gw[2], -uw[0], uw[1], uw[2], err_rel))
    print("  镜像锚点（文件字节 vs 源包声明，逐对象世界盒）: 有效检查 %d | 本地盒中心在原点(给不出证据,已剔除) %d "
          "| 占位跳过 %d | 最大相对差 %.2e" % (checked, skipped_centered, skipped_ph, worst))
    if checked < 3:
        bad.append("镜像锚点只有 %d 条**有敏感度**的对象（<3）——分母不足，不许算通过" % checked)
    return bad


def verify_glb(path, scene=None):
    """从**文件字节**回读断言，不看装配过程的中间变量（WF-32 第 5 步）。"""
    raw = open(path, "rb").read()
    magic, _ver, total = struct.unpack_from("<III", raw, 0)
    if magic != G.GLB_MAGIC or total != len(raw):
        die("GLB 头不对: magic=%08x 声明 %d 实际 %d" % (magic, total, len(raw)))
    jl, jt = struct.unpack_from("<II", raw, 12)
    if jt != G.CHUNK_JSON:
        die("第一个 chunk 不是 JSON")
    g = json.loads(raw[20:20 + jl].decode("utf-8"))
    bl, bt = struct.unpack_from("<II", raw, 20 + jl)
    if bt != G.CHUNK_BIN:
        die("第二个 chunk 不是 BIN")
    bin_off = 20 + jl + 8
    binraw = raw[bin_off:bin_off + bl]
    PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
    bad = []
    if len(g.get("bufferViews", [])) == 0:
        bad.append("bufferViews 段是空的 —— accessor 无处可指")
    if g.get("buffers") and g["buffers"][0]["byteLength"] > bl:
        bad.append("buffer[0].byteLength %d 大于 BIN 块 %d" % (g["buffers"][0]["byteLength"], bl))
    used = set(n["mesh"] for n in g["nodes"] if "mesh" in n)
    orphans = [i for i in range(len(g["meshes"])) if i not in used]
    if orphans:
        bad.append("orphan mesh %d 个（不会被渲染）" % len(orphans))
    nprim = 0
    for mi, mesh in enumerate(g["meshes"]):
        ph = (mesh.get("extras") or {}).get("placeholder")
        for pr in mesh["primitives"]:
            nprim += 1
            unknown = [k for k in pr["attributes"] if k not in G.LEGAL_ATTRS]
            if unknown:
                bad.append("mesh %d 属性名不在规范白名单: %s" % (mi, unknown))
            if pr.get("material") is None and not ph:
                bad.append("mesh %d(%s) 无材质却也不是占位" % (mi, mesh["name"]))
            pa = g["accessors"][pr["attributes"]["POSITION"]]
            for an, ai in pr["attributes"].items():
                acc = g["accessors"][ai]
                bv = g["bufferViews"][acc["bufferView"]]
                need = acc["count"] * G.CSIZE[acc["componentType"]] * G.ITEMS[acc["type"]]
                if acc["count"] != pa["count"]:
                    bad.append("mesh %d 属性 %s 的 count %d != POSITION %d"
                               % (mi, an, acc["count"], pa["count"]))
                if bv["byteOffset"] + need > len(binraw):
                    bad.append("accessor %d(%s) 越界: 要 %d 字节，缓冲剩 %d"
                               % (ai, an, need, len(binraw) - bv["byteOffset"]))
            ia = g["accessors"][pr["indices"]]
            if ia["count"] % 3:
                bad.append("mesh %d 索引数 %d 不被 3 整除" % (mi, ia["count"]))
            if max(v[0] for v in G.read_acc(g, raw, bin_off, pr["indices"])[1]) >= pa["count"]:
                bad.append("mesh %d 最大索引 >= 顶点数" % mi)
    for i, im in enumerate(g["images"]):
        bv = g["bufferViews"][im["bufferView"]]
        if binraw[bv["byteOffset"]:bv["byteOffset"] + 8] != PNG:
            bad.append("image %d 不是 PNG 魔数" % i)
    ext = (g.get("extensions") or {}).get(KHR, {})
    withmesh = sum(1 for n in g["nodes"] if "mesh" in n)
    ph = sum(1 for m in g["meshes"] if (m.get("extras") or {}).get("placeholder"))
    print("回读 %s: 节点 %d（挂网格 %d）/ 网格 %d（占位 %d）/ primitive %d / 材质 %d / 贴图 %d / 灯 %d"
          % (P.rel(path), len(g["nodes"]), withmesh, len(g["meshes"]), ph, nprim,
             len(g["materials"]), len(g["images"]), len(ext.get("lights", []))))
    print("  extras: %s" % json.dumps(g.get("extras", {}), ensure_ascii=False)[:400])
    if scene:
        bad += mirror_anchor(g, bin_off, binraw, scene)
    if bad:
        for b in bad[:14]:
            print("  [FAIL] " + b)
        die("回读断言 %d 条不过" % len(bad))
    print("  回读断言全过")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default=P.DEF_SCENE)
    ap.add_argument("--out")
    ap.add_argument("--only", help="逗号分隔的 GameObject 名，做 1-8 个样本")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--no-textures", action="store_true", help="只出几何（先量体积与耗时）")
    ap.add_argument("--include-inactive", action="store_true", help="反向对照：把关闭态也画上去")
    ap.add_argument("--no-mirror", action="store_true", help="反向对照：故意不做镜像 X")
    ap.add_argument("--no-flipuv", action="store_true")
    ap.add_argument("--verify")
    ap.add_argument("--truth-out", help="Unity 侧口径真值 json（默认跟着 --out 落 <glb>.truth.json）")
    a = ap.parse_args()
    if a.verify:
        return verify_glb(a.verify, scene=a.scene)
    build(a.scene, a.out, only=a.only, limit=a.limit, with_textures=not a.no_textures,
          include_inactive=a.include_inactive, mirror=not a.no_mirror, flipuv=not a.no_flipuv,
          truth_out=a.truth_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
