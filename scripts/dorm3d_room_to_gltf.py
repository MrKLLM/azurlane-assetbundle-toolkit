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
            "uvs1": [list(v[:2]) for v in (h.m_UV1 or [])] if h.m_UV1 else [],
            "declared_v": int(m.m_VertexData.m_VertexCount or 0), "aabb": decl,
            "declared_idx": int(sum(int(getattr(s, "indexCount", 0) or 0)
                                    for s in (getattr(m, "m_SubMeshes", None) or []))),
            "submesh_decl": len(getattr(m, "m_SubMeshes", None) or [])}


def bake_lightmap_uv(rec, st):
    """把「每 renderer 的 lightmap 矩形」烘进第二套 UV：`uv1 * tiling + offset`。

    Unity 侧网格里的 UV1 是 0..1 铺满的，真正的位置由 `Renderer.m_LightmapTilingOffset`
    =(tilingX, tilingY, offsetX, offsetY) 决定（实测 uv1 范围 ~[0.004,0.993] 配
    ST=(0.163,0.162,0.47,0.739)）。烘进几何而不是放进贴图 repeat/offset，是因为
    同一张 lightmap 在 three.js 里只能有一份 `texture.matrix`，而本房间有 **196 个不同矩形**
    ⇒ 按 ST 克隆贴图会变成 196 次 1024² 上传。代价：几何不能再按网格名跨对象复用
    （所以去重键里带上了 ST）。
    """
    if not rec.get("uvs1"):
        return rec, False
    tx, ty, ox, oy = st
    out = [[u[0] * tx + ox, u[1] * ty + oy] for u in rec["uvs1"]]
    r2 = dict(rec)
    r2["uvs1"] = out
    r2["uvs1_baked"] = True
    return r2, True


def add_mesh(gltf, buf, rec, mats, placeholder=None, lm=None, src=None):
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
    # 只有**烘进过 ST** 的第二套 UV 才发出去：没挂 lightmap 的对象留着满幅 UV1 只会让人以为
    # 它参与烘焙（并且让"带 uv1 的几何数"这条判据变成混合母体）
    u1acc = (G.add_accessor(gltf, buf, "f", [x for v in rec["uvs1"] for x in v], n, "VEC2",
                            G.ARR_BUFFER)
             if rec.get("uvs1_baked") and len(rec.get("uvs1") or []) == n else None)
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
        if u1acc is not None:
            attrs["TEXCOORD_1"] = u1acc
        mat = mats[si] if si < len(mats) else (mats[-1] if mats else None)
        primitives.append({"attributes": attrs, "indices": iacc, "material": mat, "mode": 4})
    if not primitives:
        return None
    mesh = {"name": rec["name"], "primitives": primitives}
    ex = {}
    if placeholder:
        ex["placeholder"] = placeholder
    if lm:
        ex["unityLightmapPage"] = lm[0]
        ex["unityLightmapST"] = [round(v, 6) for v in lm[1]]
    if src:
        # 回指源包网格（cab/path_id），让 --verify 能重读原始 UV1 逐点核对线性映射
        ex["unitySrcMesh"] = "%s/%d" % (src[0], src[1])
    if ex:
        mesh["extras"] = ex
    gltf["meshes"].append(mesh)
    return len(gltf["meshes"]) - 1


def material_of(gltf, buf, res, mat_reader, with_textures, tex_cache, texstat, page=None):
    key = (P.cab_key(mat_reader.assets_file.name), mat_reader.path_id, page)
    if key in gltf["_matkey"]:
        return gltf["_matkey"][key]
    mt = mat_reader.read()
    sp = getattr(mt, "m_SavedProperties", None)
    entry = {"name": mt.m_Name, "doubleSided": True,
             "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 0.9}}
    if page is not None:
        # glTF 核心没有"烘焙 GI / lightmap"这个概念（只有 occlusion/emissive），所以页号走 extras，
        # 由查看端（dorm3d_room_probe.py 的 harness）按 sidecar 挂到 material.lightMap 上。
        entry["extras"] = {"unityLightmapPage": page}
    colors = dict(list(getattr(sp, "m_Colors", None) or []))
    floats = dict(list(getattr(sp, "m_Floats", None) or []))
    base = colors.get("_BaseColor") or colors.get("_Color")
    alpha = 1.0
    if base is not None:
        alpha = float(getattr(base, "a", 1))
        entry["pbrMetallicRoughness"]["baseColorFactor"] = [
            float(getattr(base, k, d)) for k, d in (("r", 1), ("g", 1), ("b", 1), ("a", 1))]
    # 透明模式：glTF 的 alphaMode 必须从 Unity 材质的**渲染状态**推，不能猜。
    # 三个信号（缺一不可，本轮就是漏了第三个才把窗外云层画成一块黑）：
    #   ① 混合方程 _SrcBlend=SrcAlpha 且 _DstBlend=OneMinusSrcAlpha
    #   ② baseColor 的 alpha < 1
    #   ③ **baseColor 贴图自带 alpha 通道**（不是恒 255）——云层/光束这类自定义 shader
    #      的材质既没有 ① 也没有 ②，透明信息只在贴图的 A 里（实测云纹理 alpha 均值 0.066）。
    # ⚠️ 不能用 `_Cutoff`：348 个材质里 289 个带着默认值 0.5（包括明显不透明的墙和木头），
    #    拿它当依据会把大半房间变成 alpha 测试。
    # 漏掉这条的真实后果：窗玻璃 mat_db_glass06（alpha 0.196）被画成实心黑玻璃；
    # 而漏掉 ③ 的后果是窗外云层把近乎全黑的 RGB 糊在天空位置上，补摆的穹顶整片被盖住。
    blend_eq = (float(floats["_SrcBlend"]) == 5.0 and float(floats["_DstBlend"]) == 10.0
                if floats.get("_SrcBlend") is not None and floats.get("_DstBlend") is not None
                else False)
    if blend_eq or alpha < 0.999:
        entry["alphaMode"] = "BLEND"
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
                # 信号③要在**首次解码**时算一次并记下：贴图常常被多个材质复用，
                # 只写在解码分支里会让走缓存的那些材质漏判（本轮实测漏了树叶与花两种）
                lo = 255
                if img.mode.endswith("A"):
                    lo = img.split()[-1].getextrema()[0]
                gltf.setdefault("_texalpha", {})[tk] = lo
                raw = b.getvalue()
                gltf["images"].append({"bufferView": buf.add(raw), "mimeType": "image/png",
                                       "name": tobj.m_Name})
                gltf["textures"].append({"source": len(gltf["images"]) - 1})
                tex_cache[tk] = len(gltf["textures"]) - 1
                ti = tex_cache[tk]
            entry["pbrMetallicRoughness"]["baseColorTexture"] = {"index": ti, "texCoord": 0}
            entry["_unitySlot"] = slot
            if gltf.get("_texalpha", {}).get(tk, 255) < 250:
                entry["alphaMode"] = "BLEND"     # 信号③：baseColor 贴图自带 alpha
                texstat.setdefault("alpha_tex", set()).add(mt.m_Name)
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


def jobs_from_scene(env, res, own, trs, tr_of_go, rend_of_go, only, limit, include_inactive,
                  cull_bits=None):
    node_of = {o.path_id: i for i, o in enumerate(trs)}
    name_of = {}
    for o in trs:
        sfn = P.cab_key(o.assets_file.name)
        gp = getattr(o.read().m_GameObject, "path_id", 0) or 0
        g = own.get((sfn, gp))
        name_of[o.path_id] = g.read().m_Name if g is not None else ""
    want = set(x.strip() for x in only.split(",") if x.strip()) if only else None
    jobs, skipped_by, builtin_groups, unresolved = [], {}, {}, 0
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
        # 三重门控（少一条就会多画游戏里看不见的东西）：
        #   ① 自身+全祖先 m_IsActive   ② MeshRenderer.m_Enabled   ③ GameObject.m_Layer 在相机 cullingMask 里
        # 实测房间 1：348 个 MeshFilter 只有 269 个该画（49 关着 / 26 渲染器禁用 / 4 层被相机剔除），
        # 而那 31 个 Unity 内置原语**一个都不画**（它们是碰撞/标记物）⇒ 画成白方块是错的。
        on, blocker = P.go_active(own, tr_of_go, sfn, goid)
        rend0 = rend_of_go.get((sfn, goid))
        ren_on = bool(rend0 is not None and int(getattr(rend0.read(), "m_Enabled", 1) or 0) == 1)
        go0 = own.get((sfn, goid))
        layer = int(getattr(go0.read(), "m_Layer", 0) or 0) if go0 is not None else 0
        in_mask = True if cull_bits is None else bool((cull_bits >> layer) & 1)
        reason = (None if (on and ren_on and in_mask) else
                  ("inactive" if not on else ("renderer_off" if not ren_on else "layer")))
        if reason and not include_inactive:
            skipped_by[reason] = skipped_by.get(reason, 0) + 1
            continue
        if reason:
            skipped_by[reason] = skipped_by.get(reason, 0) + 1
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
        lm = None
        if rend is not None:
            rr = rend.read()
            li = int(getattr(rr, "m_LightmapIndex", 65535) or 65535)
            if li != 65535:
                v = getattr(rr, "m_LightmapTilingOffset", None)
                if v is not None:
                    lm = (li, (float(v.x), float(v.y), float(v.z), float(v.w)))
            for mp in (rr.m_Materials or []):
                b2, c2, p2 = res.classify(rend.assets_file, mp)
                t2, _e2 = res.fetch(own, b2, c2, p2)
                mats.append(t2 if (t2 is not None and t2.type.name == "Material") else None)
        jobs.append({"node": node_of[trp], "name": gname, "bucket": bucket, "cab": cab,
                     "path_id": pid, "reader": rdr, "mats": mats, "lm": lm,
                     "builtin_key": (cab, pid) if rdr is None else None})
        if limit and len(jobs) >= limit:
            break
    return jobs, node_of, name_of, skipped_by, builtin_groups, unresolved


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
          include_inactive=False, mirror=True, flipuv=True, verbose=True, truth_out=None,
          bake_lm=True):
    t0 = time.time()
    deps, _k = P.dep_bundle_paths(scene, P.DEP_MANIFEST)
    index, scanned, isec, _dup = P.build_index([P.DEF_DIR], extra_bundles=deps)
    res = P.Resolver(index)
    env = UnityPy.load(scene)
    own, trs, tr_of_go, rend_of_go = scene_tables(env)
    cam = [o for o in env.objects if o.type.name == "Camera"]
    cull_bits = None
    if cam:
        cm = getattr(cam[0].read(), "m_CullingMask", None)
        cull_bits = int(getattr(cm, "m_Bits", getattr(cm, "value", 0xFFFFFFFF)) or 0) if cm else None
    jobs, node_of, name_of, skipped_by, bgroups, unresolved = jobs_from_scene(
        env, res, own, trs, tr_of_go, rend_of_go, only, limit, include_inactive, cull_bits)
    skipped = sum(skipped_by.values())
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
    n_place = lm_baked = lm_nouv1 = lm_prims = 0
    lm_rows = []
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
            mk = None
            n_place += 1
        else:
            lmst = j.get("lm") if bake_lm else None
            st = lmst[1] if lmst else None
            mk = (P.cab_key(j["cab"] or "self"), j["path_id"], st)
            rec = mesh_cache.get(mk) or mesh_from_handler(j["reader"], mirror, flipuv)
            if st is not None:
                rec, baked = bake_lightmap_uv(rec, st)
                if baked:
                    lm_baked += 1
                    lm_prims += len([t for t in rec["tris"] if t])
                else:
                    lm_nouv1 += 1
                    lmst = None
                    mk = (mk[0], mk[1], None)
            ph = None
            mesh_cache.setdefault(mk, rec)
        page = lmst[0] if (mk is not None and mk[2] is not None) else None
        mvals = [material_of(gltf, buf, res, mi, with_textures, tex_cache, texstat, page)
                 for mi in j["mats"] if mi is not None]
        key = (mk, ph, tuple(mvals))
        if key in gltf["_meshkey"]:
            midx = gltf["_meshkey"][key]
        else:
            midx = add_mesh(gltf, buf, rec, mvals, placeholder=ph,
                            lm=(page, j["lm"][1]) if page is not None else None,
                            src=mk[:2] if mk else None)
            gltf["_meshkey"][key] = midx
        if page is not None and rec.get("uvs1"):
            u1 = rec["uvs1"]
            lm_rows.append({"object": j["name"], "page": page,
                            "st": [round(v, 6) for v in (j["lm"][1])],
                            "uv1_bbox": [[round(min(p[k] for p in u1), 5),
                                          round(max(p[k] for p in u1), 5)] for k in (0, 1)]})
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
    # 剪掉没有被任何 primitive 引用的材质：glTF 允许它存在，但 three.js 根本不会实例化，
    # 于是"前端挂上 lightMap 的材质数"与 sidecar 声明数会差一个——母体必须先对齐。
    used_mat = sorted({pr["material"] for m in gltf["meshes"] for pr in m["primitives"]
                       if pr.get("material") is not None})
    remap = {old: new for new, old in enumerate(used_mat)}
    dropped = len(gltf["materials"]) - len(used_mat)
    for m in gltf["meshes"]:
        for pr in m["primitives"]:
            if pr.get("material") is not None:
                pr["material"] = remap[pr["material"]]
    gltf["materials"] = [gltf["materials"][i] for i in used_mat]
    truth = {"scene": P.rel(scene), "nodes": len(nodes), "objects": len(anchors),
             "prim_total": prim_total, "pos_total": pos_total, "tri_total": tri_total,
             "world_box": [wmin, wmax], "world_box_skipped": wb_skipped,
             "placeholders": n_place, "materials": len(gltf["materials"]),
             "tex_hit": texstat["hit"], "tex_miss": len(texstat["miss"]),
             "tex_no_slot": len(texstat["none"]),
             "placeholder_basis": "占位对象按本装配器生成的单位立方体计入总数(24 顶点/12 三角)，"
                                  "其 Unity 侧声明值不可得；世界盒不含占位对象",
             "textures": len(gltf["images"]), "skipped_by": skipped_by, "mirror": mirror,
             "alpha_blend": sum(1 for m in gltf["materials"] if m.get("alphaMode") == "BLEND"),
             "per_object": [{"object": a["object"], "mesh": a["mesh"], "verts": a["declared_v"],
                             "tris": a["tris"], "submeshes": a["submesh_decl"],
                             "center": a.get("center"), "size": a.get("size"),
                             "placeholder": bool(a["placeholder"])} for a in anchors]}
    lights, lskip = add_lights(env, own, gltf, nodes, tr_of_go, node_of)
    lm_dir = os.path.join(os.path.dirname(os.path.abspath(out)), "lightmaps") if out else None
    pages = lightmap_pages(env, res, own, lm_dir) if with_textures else []
    mat_pages = {str(i): m["extras"]["unityLightmapPage"] for i, m in enumerate(gltf["materials"])
                 if (m.get("extras") or {}).get("unityLightmapPage") is not None}
    if out:
        side = os.path.splitext(out)[0] + ".lightmaps.json"
        json.dump({"pages": pages, "material_pages": mat_pages, "objects": lm_rows,
                   "convention": "uv1_baked = 网格UV1 * m_LightmapTilingOffset.xy + .zw；"
                                 "glTF 核心没有 lightmap，页号在 material.extras.unityLightmapPage，"
                                 "由查看端挂 material.lightMap（three.js 用 uv1 属性）",
                   "lm_objects": len(lm_rows), "lm_baked": lm_baked, "lm_no_uv1": lm_nouv1,
                   "lm_prims": lm_prims, "lm_st_unique": len({tuple(r["st"]) for r in lm_rows})},
                  open(side, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    truth["lights"] = len(lights)
    truth["lights_skipped"] = lskip
    truth["lm_pages"] = len(pages)
    truth["lm_objects"] = len(lm_rows)
    truth["lm_baked"] = lm_baked
    truth["lm_no_uv1"] = lm_nouv1
    truth["lm_materials"] = len(mat_pages)
    truth["dropped_materials"] = dropped
    truth["cull_bits"] = cull_bits
    truth["skipped_by"] = skipped_by
    truth["lm_prims"] = lm_prims
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
    for k in ("_own", "_matkey", "_meshkey", "_texalpha"):
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
        print("索引 %d 包 / %.1f 秒 | 工单 %d（门控剔除 %d，无 Transform %d）| 节点 %d | "
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
        print("  烘焙光照: lightmap %d 页 / 烘进几何 UV1 的对象 %d / 有页号但网格无 UV1 %d / "
              "带页号的材质 %d 个（未烘焙对象 %d，另有无引用材质被剪掉 %d 个）"
              % (len(pages), lm_baked, lm_nouv1, len(mat_pages),
                 len(jobs) - lm_baked - lm_nouv1, dropped))
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


def lightmap_pages(env, res, own, out_dir):
    """把 `LightmapSettings.m_Lightmaps[i].m_Lightmap` 那几张烘焙图解成 PNG，返回页清单。"""
    ls = [o for o in env.objects if o.type.name == "LightmapSettings"]
    if not ls:
        return []
    lo = ls[0]
    L = lo.read()
    pages = []
    for i, ld in enumerate(list(getattr(L, "m_Lightmaps", None) or [])):
        pp = getattr(ld, "m_Lightmap", None)
        if pp is None or not (getattr(pp, "path_id", 0) or 0):
            continue
        bucket, cab, pid = res.classify(lo.assets_file, pp)
        t, err = res.fetch(own, bucket, cab, pid)
        if t is None or t.type.name != "Texture2D":
            print("      lightmap 页 %d 解析失败: %s" % (i, err))
            continue
        tx = t.read()
        try:
            img = tx.image
        except Exception as ex:
            print("      lightmap 页 %d(%s) 解码失败 %s" % (i, tx.m_Name, type(ex).__name__))
            continue
        fn = "lm%d_%s.png" % (i, tx.m_Name)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            img.convert("RGBA").save(os.path.join(out_dir, fn), format="PNG")
        pages.append({"index": i, "name": tx.m_Name, "file": fn,
                      "size": [int(tx.m_Width), int(tx.m_Height)]})
    return pages


def scene_ctx(scene):
    """一次装好源包上下文（env / 对象表 / Transform 列表 / CAB 索引 + 解析器），给两条跨源锚点共用。"""
    env = UnityPy.load(scene)
    own, trs, tr_of_go, rend_of_go = scene_tables(env)
    deps, _k = P.dep_bundle_paths(scene, P.DEP_MANIFEST)
    index, _n, _s, _d = P.build_index([P.DEF_DIR], extra_bundles=deps)
    return {"env": env, "own": own, "trs": trs, "tr_of_go": tr_of_go,
            "rend_of_go": rend_of_go, "res": P.Resolver(index), "index": index}


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


def mirror_anchor(ctx, g):
    """跨源验镜像只做了一次：glTF 世界盒中心（全取自**文件字节**）应恰为
    Unity 世界盒中心（全取自**源包声明**：Transform 链 + Mesh.m_LocalAABB）的 x 反号、y/z 相等。

    两侧都由各自的 TRS 复算，所以「漏做一次镜像」和「做了两次」都会红；
    而只比我自己那套转换的断言对此是恒真的。
    """
    env, own, res = ctx["env"], ctx["own"], ctx["res"]
    trs = ctx["trs"]
    if len(trs) != len(g["nodes"]):
        return ["镜像锚点前提不成立: 源包 Transform %d 个 vs 文件节点 %d 个"
                % (len(trs), len(g["nodes"]))]
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


def lightmap_anchor(ctx, g, raw, bin_off, binraw):
    """逐点核对烘焙映射：文件里的 TEXCOORD_1 == 源包网格原始 UV1 * tiling + offset。

    这条挡三种假绿灯：① ST 根本没乘；② 乘错（tiling/offset 顺序颠倒）；
    ③ 页号与 ST 不配对。跨度类判据挡不住 ②（跨度只由 tiling 决定），
    而"重读源包原始 UV1 再算一遍"是**跨源**的，与镜像锚点同一族。
    """
    from UnityPy.helpers.MeshHelper import MeshHandler
    bad, tagged, checked, worst = [], 0, 0, 0.0
    for mesh in g["meshes"]:
        ex = mesh.get("extras") or {}
        st, src = ex.get("unityLightmapST"), ex.get("unitySrcMesh")
        if st is None:
            continue
        tagged += 1
        if ex.get("unityLightmapPage") is None:
            bad.append("网格 %s 带 ST 却没有页号" % mesh["name"])
            continue
        if not src:
            bad.append("网格 %s 带 ST 但没有源网格回指" % mesh["name"])
            continue
        cab, pid = src.rsplit("/", 1)
        t = None
        bp = ctx["res"].bundle_of(cab)
        if bp:
            t = ctx["res"].table(bp).get((P.cab_key(cab), int(pid)))
        if t is None:
            t = ctx["own"].get((P.cab_key(cab), int(pid)))
        if t is None or t.type.name != "Mesh":
            bad.append("网格 %s 的回指 %s 在源包里找不到" % (mesh["name"], src))
            continue
        h = MeshHandler(t.read())
        h.process()
        raw1 = h.m_UV1 or []
        pr = mesh["primitives"][0]
        if "TEXCOORD_1" not in pr["attributes"]:
            bad.append("网格 %s 声明了 ST 却没有 TEXCOORD_1" % mesh["name"])
            continue
        vals = G.read_acc(g, raw, bin_off, pr["attributes"]["TEXCOORD_1"])[1]
        if len(vals) != len(raw1):
            bad.append("网格 %s UV1 顶点数 %d != 源包 %d" % (mesh["name"], len(vals), len(raw1)))
            continue
        step = max(1, len(vals) // 32)
        err = 0.0
        for i in range(0, len(vals), step):
            err = max(err, abs(vals[i][0] - (raw1[i][0] * st[0] + st[2])),
                           abs(vals[i][1] - (raw1[i][1] * st[1] + st[3])))
        worst = max(worst, err)
        checked += 1
        if err > 1e-4:
            bad.append("网格 %s(page %s, ST %s) 烘焙映射逐点最大偏差 %.2e，样例 uv1=%s 源=%s"
                       % (mesh["name"], ex.get("unityLightmapPage"), st, err,
                          list(vals[0]), list(raw1[0])))
    print("  lightmap 锚点（逐点核对 TEXCOORD_1 == 源包 UV1 * tiling + offset）: "
          "带 ST 的网格 %d / 核对通过 %d / 最大偏差 %.2e" % (tagged, checked, worst))
    if tagged == 0:
        bad.append("没有任何网格带 lightmap ST —— 烘焙光照通路等于没做")
    elif checked < tagged:
        bad.append("带 ST 的网格 %d 个，只有 %d 个核对成功" % (tagged, checked))
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
    # 透明一致性：带着 alpha<1 的因子却标 OPAQUE，等于"半透明材质按实心画"——
    # 这正是窗玻璃变成一整块黑的原因，所以把它写成回读断言而不是靠人眼发现。
    badfac = [m.get("name") for m in g.get("materials", [])
              if (m.get("pbrMetallicRoughness", {}).get("baseColorFactor")
                  or [1, 1, 1, 1])[3] < 0.999
              and m.get("alphaMode", "OPAQUE") == "OPAQUE"]
    if badfac:
        bad.append("有 %d 个材质 alpha<1 却是 OPAQUE（会被画成实心）: %s" % (len(badfac), badfac[:5]))
    nblend = sum(1 for m in g.get("materials", []) if m.get("alphaMode") == "BLEND")
    print("  材质: %d 个，其中 alphaMode=BLEND %d 个（alpha<1 却实心 %d 个）"
          % (len(g.get("materials", [])), nblend, len(badfac)))
    # 信号③的回读不变式：贴图自带 alpha 却按实心画（云层被糊成黑天空就是这么来的）
    badtex = []
    for m in g.get("materials", []):
        ti = ((m.get("pbrMetallicRoughness") or {}).get("baseColorTexture") or {}).get("index")
        if ti is None or m.get("alphaMode", "OPAQUE") != "OPAQUE":
            continue
        try:
            im = g["images"][g["textures"][ti]["source"]]
            bv = g["bufferViews"][im["bufferView"]]
            from PIL import Image as _Im
            aa = _Im.open(io.BytesIO(binraw[bv["byteOffset"]:bv["byteOffset"] + bv["byteLength"]]))
            if aa.mode.endswith("A") and aa.split()[-1].getextrema()[0] < 250:
                badtex.append(m.get("name"))
        except Exception:
            pass
    if badtex:
        bad.append("有 %d 个材质的 baseColor 贴图自带 alpha 却是 OPAQUE（会被画成实心）: %s"
                   % (len(badtex), badtex[:6]))
    print("  贴图自带 alpha 却实心: %d 个" % len(badtex))
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
        ctx = scene_ctx(scene)
        bad += mirror_anchor(ctx, g)
        side = os.path.splitext(path)[0] + ".lightmaps.json"
        tagged_mat = sum(1 for m in g["materials"]
                         if (m.get("extras") or {}).get("unityLightmapPage") is not None)
        if not os.path.isfile(side) and tagged_mat:
            bad.append("有 %d 个材质声明了 lightmap 页号，但 sidecar 不存在（%s）"
                       % (tagged_mat, P.rel(side)))
        bad += lightmap_anchor(ctx, g, raw, bin_off, binraw)
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
    ap.add_argument("--no-lightmap", action="store_true",
                    help="反向对照：不烘 m_LightmapTilingOffset（lightmap 锚点必须判红）")
    ap.add_argument("--truth-out", help="Unity 侧口径真值 json（默认跟着 --out 落 <glb>.truth.json）")
    a = ap.parse_args()
    if a.verify:
        return verify_glb(a.verify, scene=a.scene)
    build(a.scene, a.out, only=a.only, limit=a.limit, with_textures=not a.no_textures,
          include_inactive=a.include_inactive, mirror=not a.no_mirror, flipuv=not a.no_flipuv,
          truth_out=a.truth_out, bake_lm=not a.no_lightmap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
