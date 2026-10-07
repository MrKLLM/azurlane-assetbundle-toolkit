"""dorm3d 蒙皮网格 → glTF 2.0 (.glb) 装配层。

UnityPy 的 `Mesh.export()` 只给不含骨骼的 OBJ，蒙皮这条路**必须自己装配**：
节点层级(Transform) + 蒙皮(skins: joints + inverseBindMatrices) + 网格
(POSITION/NORMAL/TEXCOORD_0/JOINTS_0/WEIGHT_0) + 基础色贴图(ASTC 当场解成 PNG 内嵌)。

    py -3 scripts/dorm3d_to_gltf.py files/AssetBundles/dorm3d/character/tianlangxing_db/res/tianlangxing_noshoes --check
    py -3 scripts/dorm3d_to_gltf.py <res包> --mesh body --out .diag/dorm3d_gltf/body.glb

顶点缓冲的流切分与元素宽度**不写死**：复用探针的反解 + 三重自证
（`diag/probe_3d_capability`），解不成立就拒绝出图，不硬凑权重。

坐标系：Unity 左手系、glTF 右手系，按镜像 X 统一处理且**处处一致**——顶点/法线 x 取反、
三角形换绕序、矩阵做 C·M·C 共轭、四元数 (x,y,z,w)→(x,-y,-z,w)。少做任何一处都会得到
镜像但 inside-out、或朝向对但面反的模型。

两处语义只能靠浏览器里目视定（`--transpose-ibm` / `--no-flipuv` 就是为这一步准备的）：
① `m_BindPose` 的元素序要不要按转置喂给 glTF；② UV 的 V 要不要翻。判据都是同一条：
站着、不炸面、贴图不上下颠倒。
"""
import argparse
import io
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "diag"))

import UnityPy  # noqa: E402

import probe_3d_capability as probe  # noqa: E402

UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

GLB_MAGIC, GLB_VERSION = 0x46546C67, 2
CHUNK_JSON, CHUNK_BIN = 0x4E4F534A, 0x004E4942
CH_POS, CH_NORMAL, CH_TANGENT, CH_COLOR, CH_UV0 = 0, 1, 2, 3, 4
ELEMTYPE = {1: ("B", 5121), 2: ("e", 5122), 4: ("f", 5126)}
ARR_BUFFER, ARRAY_BUFFER = 34962, 34963
ITEMS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def die(msg, code=1):
    print("[FAIL] " + msg)
    sys.exit(code)


class Buf:
    """单个 GLB BIN chunk；所有 bufferView 4 字节对齐。"""

    def __init__(self):
        self.data = bytearray()
        self.views = []

    def add(self, raw, target=None):
        while len(self.data) % 4:
            self.data += b"\0"
        off = len(self.data)
        self.data += raw
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(raw)}
        if target:
            v["target"] = target
        self.views.append(v)
        return len(self.views) - 1

    def add_pack(self, fmt, values, target=None):
        return self.add(struct.pack("<" + str(len(values)) + fmt, *values), target)


def add_accessor(gltf, buf, fmt, values, count, atype, target=None, vmin=None, vmax=None):
    if len(values) != count * ITEMS[atype]:
        die("accessor 长度不变式破了: %s 要 %d 个元素 x %d = %d，实得 %d"
            % (atype, count, ITEMS[atype], count * ITEMS[atype], len(values)))
    bv = buf.add_pack(fmt, values, target)
    acc = {"bufferView": bv, "componentType": comp_of(fmt), "count": count, "type": atype}
    if vmin is not None:
        acc["min"], acc["max"] = vmin, vmax
    gltf["accessors"].append(acc)
    return len(gltf["accessors"]) - 1


def comp_of(fmt):
    return {"B": 5121, "e": 5122, "H": 5123, "f": 5126, "I": 5125}[fmt]


def channel_dtype(cid, width):
    """同一个"2 字节宽"在不同通道上含义完全不同，不能一律按 float16 读。

    实测踩坑：按半精度读 uint16 骨号，`1` 变成次正规数 6e-8，`int()` 之后**全部归零**
    —— 每个顶点都挂到 0 号骨，模型塌成一团；按半精度读 UNorm16 权重，
    `32767` 直接是 NaN、`32768` 是 -Inf。
    """
    if cid == probe.CH_BLEND_WEIGHT:
        return ('H', False) if width == 2 else ('f', False)     # UNorm16 或 Float32
    if cid == probe.CH_BLEND_INDICES:
        return {1: ('B', False), 2: ('H', False), 4: ('I', False)}[width]
    if cid == CH_COLOR:
        return ('B', True)                                       # 归一化 ubyte
    return {4: ('f', False), 2: ('e', False)}.get(width, (None, False))


def read_plain_channel(mesh, ch, stride, base, e, cid, n):
    """按通道读数值；权重按 UNorm16 归一到 0..1，骨号保持整数。"""
    rec = next((t for t in ch if t[3] == cid), None)
    if rec is None:
        return None
    s, off, dim, idx = rec
    code, normalized = channel_dtype(cid, e.get(idx))
    if code is None:
        die(f"通道 {cid} 的元素宽度 {e.get(idx)}B 不支持")
    data = probe.data_at(mesh)
    fmt = "<%d%s" % (dim, code)
    scale = (1.0 / 65535.0) if (cid == probe.CH_BLEND_WEIGHT and code == 'H') else \
        (1.0 / 255.0 if normalized else 1.0)
    out = []
    for v in range(n):
        raw = struct.unpack_from(fmt, data, base[s] + v * stride[s] + off)
        out.append([x * scale for x in raw] if scale != 1.0 else list(raw))
    return out


def index_buffer(mesh):
    """索引宽度也自证：解出来全部 < 顶点数、且三角形数整除 3 才算数。"""
    data = bytes(mesh.m_IndexBuffer or b"")
    nv = mesh.m_VertexData.m_VertexCount
    for width, code in ((2, "H"), (4, "I")):
        if len(data) % width:
            continue
        cnt = len(data) // width
        if cnt % 3:
            continue
        ii = list(struct.unpack("<%d%s" % (cnt, code), data))
        if max(ii) < nv:
            return code, ii
    die(f"索引缓冲解不出（{len(data)}B / 顶点 {nv}）")


def matrix_rows(mm):
    """Unity Matrix4x4f -> 行主序 16 元素（e00..e03, e10..）。"""
    return [float(getattr(mm, "e%d%d" % (r, c), 0.0) or 0.0)
            for r in range(4) for c in range(4)]


def mirror_matrix_rows(rows):
    """C·M·C，C=diag(-1,1,1,1)：行号或列号恰有一个是 0 的条目取反。"""
    out = list(rows)
    for r in range(4):
        for c in range(4):
            if (r == 0) ^ (c == 0):
                out[r * 4 + c] = -out[r * 4 + c]
    return out


def rows_to_column_major(rows):
    return [rows[r * 4 + c] for c in range(4) for r in range(4)]


def build_index(env):
    """path_id -> ObjectReader，以及 Transform/GameObject 的双向映射。

    一律用 path_id 关联，不靠对象 `id()`——UnityPy 每次 read() 可能新建对象，
    按 id 比对会静默匹不上。
    """
    by = {}
    for o in env.objects:
        by[o.path_id] = o
    trs, gos = [], []
    for o in env.objects:
        if o.type.name == "Transform":
            trs.append(o)
        elif o.type.name == "GameObject":
            gos.append(o)
    node_of = {}
    node_of_go = {}
    for i, o in enumerate(trs):
        node_of[o.path_id] = i
    name_of = {}
    for o in trs:
        t = o.read()
        gp = getattr(t, "m_GameObject", None)
        gpid = getattr(gp, "path_id", None) if gp is not None else None
        g = by.get(gpid) if gpid else None
        name_of[o.path_id] = g.read().m_Name if g is not None and g.type.name == "GameObject" else ""
        if gpid:
            node_of_go[gpid] = node_of[o.path_id]
    return by, trs, node_of, name_of, node_of_go


def build_nodes(trs, node_of, name_of, by):
    nodes, kids, roots = [], {i: [] for i in range(len(trs))}, []
    for i, o in enumerate(trs):
        t = o.read()
        fpid = getattr(getattr(t, "m_Father", None), "path_id", 0) or 0
        p = node_of.get(fpid) if fpid else None
        if p is None:
            roots.append(i)
        else:
            kids[p].append(i)
    for i, o in enumerate(trs):
        t = o.read()
        node = {"name": name_of.get(o.path_id) or "node_%d" % i}
        p, r, s = t.m_LocalPosition, t.m_LocalRotation, t.m_LocalScale
        node["translation"] = [-float(p.x), float(p.y), float(p.z)]
        node["rotation"] = [float(r.x), -float(r.y), -float(r.z), float(r.w)]
        sc = [float(s.x), float(s.y), float(s.z)]
        if sc != [1.0, 1.0, 1.0]:
            node["scale"] = sc
        if kids[i]:
            node["children"] = kids[i]
        nodes.append(node)
    return nodes, roots, kids


def ancestor_root(pid, by, node_of):
    seen = set()
    cur = pid
    while cur and cur not in seen:
        seen.add(cur)
        t = by.get(cur)
        if t is None or t.type.name != "Transform":
            break
        fp = getattr(t.read().m_Father, "path_id", 0) or 0
        if not fp or fp not in node_of:
            return node_of.get(cur)
        cur = fp
    return node_of.get(cur)


def material_entry(gltf, buf, mat):
    """基础色 = m_TexEnvs 里第一个真有贴图引用的槽位。

    ⚠️ 这个字段在 UnityPy 1.25.3 里叫 **m_TexEnvs**；按 `m_Textures` 读会得到恒 0 的假读数。
    """
    sp = getattr(mat, "m_SavedProperties", None)
    if sp is None:
        return None
    entry = {"name": mat.m_Name, "doubleSided": True,
             "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 0.9}}
    colors = dict(list(getattr(sp, "m_Colors", None) or []))
    base = colors.get("_BaseColor") or colors.get("_Color")
    if base is not None:
        entry["pbrMetallicRoughness"]["baseColorFactor"] = [
            float(getattr(base, k, d)) for k, d in (("r", 1), ("g", 1), ("b", 1), ("a", 1))]
    for kv in (list(getattr(sp, "m_TexEnvs", None) or [])):
        key, env = kv[0], kv[1]
        tp = getattr(env, "m_Texture", None)
        pid = getattr(tp, "path_id", 0) or 0
        if not pid:
            continue
        tobj = gltf["_by"].get(pid)
        if tobj is None or tobj.type.name != "Texture2D":
            continue
        try:
            img = tobj.read().image
        except Exception as ex:
            print("      贴图 %s 解码失败 %s（跳过，不放占位）" % (key, type(ex).__name__))
            continue
        b = io.BytesIO()
        img.save(b, format="PNG")
        raw = b.getvalue()
        bv = buf.add(raw)
        gltf["images"].append({"bufferView": bv, "mimeType": "image/png",
                               "name": getattr(tobj.read(), "m_Name", key)})
        gltf["textures"].append({"source": len(gltf["images"]) - 1})
        entry["pbrMetallicRoughness"]["baseColorTexture"] = {"index": len(gltf["textures"]) - 1}
        entry["_unitySlot"] = key
        break
    gltf["materials"].append(entry)
    return len(gltf["materials"]) - 1


def prefab_material_lists(prefab_path, res_cab, res_by):
    """从 prefab 取每个 SMR 的真实材质序列（按 submesh 顺序）。

    res 包里的 SMR 只指着占位材质 `Lit`；真材质由 **prefab** 的 SMR 以外链 PPtr 引用。
    落点不靠名字猜：prefab 的 `externals[i].name == res 包的内层 CAB 名` ⇒
    该 PPtr 的 `path_id` 就在 res 包里。对不上的那些如实报"未解出"，不填占位。
    """
    penv = UnityPy.load(prefab_path)
    idx_of_res = None
    for f in penv.file.files.values():
        ext = getattr(f, "externals", None) or []
        for i, e in enumerate(ext):
            if getattr(e, "name", "") == res_cab:
                idx_of_res = i + 1          # PPtr file_id 从 1 起
                break
        if idx_of_res:
            break
    if idx_of_res is None:
        die("prefab 的 externals 里没有 %s —— 这两个包不是一对，别硬配" % res_cab)
    out, unresolved = {}, 0
    for o in penv.objects:
        if o.type.name != "SkinnedMeshRenderer":
            continue
        s = o.read()
        gpid = getattr(s.m_GameObject, "path_id", 0) or 0
        objs = [x for x in penv.objects if x.type.name == "GameObject"]
        nm = "?"
        for g in objs:
            if g.path_id == gpid:
                nm = g.read().m_Name
                break
        lst = []
        for mp in list(s.m_Materials or []):
            fid = getattr(mp, "file_id", None)
            fid = getattr(mp, "m_FileID", fid) if fid is None else fid
            if fid == 0:
                mo = res_by.get(mp.path_id)
            elif fid == idx_of_res:
                mo = res_by.get(mp.path_id)
            else:
                mo = None
                unresolved += 1
            lst.append(mo)
        out[nm] = lst
    if unresolved:
        print("  ⚠️ prefab 里有 %d 个材质 PPtr 指向第三方包（本轮不解析，会退化为无材质）" % unresolved)
    return out


def build(res_path, only=None, out_path=None, check_only=False,
          transpose_ibm=False, flipuv=True, prefab_path=None):
    env = UnityPy.load(res_path)
    by, trs, node_of, name_of, node_of_go = build_index(env)
    if not trs:
        die("包里无 Transform")
    nodes, roots, _ = build_nodes(trs, node_of, name_of, by)
    smrs = [o.read() for o in env.objects if o.type.name == "SkinnedMeshRenderer"]
    if not smrs:
        die("包里无 SkinnedMeshRenderer，不是蒙皮包")
    res_cab = next((k for k in env.file.files if not k.endswith(".resS")), "")
    pref_mats = {}
    if prefab_path:
        pref_mats = prefab_material_lists(prefab_path, res_cab, by)

    gltf = {"asset": {"version": "2.0", "generator": "dorm3d_to_gltf"},
            "scene": 0,
            "scenes": [{"nodes": sorted(set(r for r in roots))}],
            "nodes": nodes, "meshes": [], "materials": [], "skins": [],
            "accessors": [], "bufferViews": [], "images": [], "textures": []}
    gltf["_by"] = by
    buf = Buf()
    rows_out = []

    for smr in smrs:
        gpid = getattr(smr.m_GameObject, "path_id", 0) or 0
        gname = by[gpid].read().m_Name if gpid in by else "?"
        if only and gname not in only:
            continue
        try:
            mesh = smr.m_Mesh.read()
        except Exception as ex:
            die(f"{gname}: m_Mesh 解不开（{type(ex).__name__}）—— 网格不在本包，需先把它所在的 res 包给进来")
        lay = None
        for ctx in probe.candidate_layouts(mesh.m_VertexData, len(probe.data_at(mesh))):
            ch, streams, stride, base, e, n, per, tail = ctx
            if probe.self_proof(probe.decode_skin(mesh, ch, stride, base, e, n)):
                lay = ctx
                break
        if not lay:
            die(f"{gname}: 顶点布局反解失败 —— 拒绝出图（别硬凑权重）")
        ch, streams, stride, base, e, n, per, tail = lay

        pos = read_plain_channel(mesh, ch, stride, base, e, CH_POS, n)
        if not pos:
            die(f"{gname}: 无 POSITION 通道")
        flat = []
        for c in pos:
            flat += [-c[0], c[1], c[2]]
        acc = add_accessor(gltf, buf, "f", flat, n, "VEC3", ARR_BUFFER,
                           [min(flat[i::3]) for i in range(3)],
                           [max(flat[i::3]) for i in range(3)])
        attrs = {"POSITION": acc}
        nrm = read_plain_channel(mesh, ch, stride, base, e, CH_NORMAL, n)
        if nrm:
            nf = []
            for c in nrm:
                nf += [-c[0], c[1], c[2]]
            attrs["NORMAL"] = add_accessor(gltf, buf, "f", nf, n, "VEC3", ARR_BUFFER)
        uv = read_plain_channel(mesh, ch, stride, base, e, CH_UV0, n)
        if uv:
            uf = []
            for c in uv:
                u, v = c[0], (c[1] if len(c) > 1 else 0.0)
                uf += [u, (1.0 - v) if flipuv else v]
            attrs["TEXCOORD_0"] = add_accessor(gltf, buf, "f", uf, n, "VEC2")

        wrows = read_plain_channel(mesh, ch, stride, base, e, probe.CH_BLEND_WEIGHT, n)
        irows = read_plain_channel(mesh, ch, stride, base, e, probe.CH_BLEND_INDICES, n)
        if not irows:
            die(f"{gname}: 无 BlendIndices 通道")
        if not wrows:
            wrows = [[1.0]] * n          # 单骨部件：Unity 不写权重通道，权重恒 1
        joints, weights = [], []
        for v in range(n):
            iv = [int(x) for x in irows[v]]
            wv = [float(x) for x in wrows[v]]
            iv += [0] * (4 - len(iv))
            wv += [0.0] * (4 - len(wv))
            sw = sum(wv[:4]) or 1.0
            joints += iv[:4]
            weights += [x / sw for x in wv[:4]]
        nj = len(smr.m_Bones)
        if max(joints) >= nj:
            die(f"{gname}: 骨索引 {max(joints)} >= m_Bones {nj} —— 骨序或布局不对")
        if nj > 255:
            die(f"{gname}: 骨数 {nj} > 255，JOINTS_0 需改 ushort（本包未覆盖，先报错不出错图）")
        attrs["JOINTS_0"] = add_accessor(gltf, buf, "B", joints, n, "VEC4", ARRAY_BUFFER)
        attrs["WEIGHTS_0"] = add_accessor(gltf, buf, "f", weights, n, "VEC4", ARRAY_BUFFER)

        code, idx = index_buffer(mesh)
        width = 2 if code == "H" else 4
        subm = list(getattr(mesh, "m_SubMeshes", None) or [])
        mlist = pref_mats.get(gname)
        if mlist is None:
            mlist = [by.get(getattr(mp, "path_id", 0) or 0)
                     for mp in list(getattr(smr, "m_Materials", None) or [])]
        prims = []
        if not subm:
            ranges = [(0, len(idx))]
        else:
            ranges = [(s.firstByte // width, s.indexCount) for s in subm]
        for k, (start, cnt) in enumerate(ranges):
            seg = idx[start:start + cnt]
            if len(seg) != cnt:
                die(f"{gname}: submesh {k} 索引越界（{start}+{cnt} > {len(idx)}）")
            flipped = []
            for t in range(0, len(seg), 3):
                flipped += [seg[t + 1], seg[t], seg[t + 2]]      # 换绕序抵消镜像
            ia = add_accessor(gltf, buf, code, flipped, len(flipped), "SCALAR", ARRAY_BUFFER)
            prim = {"attributes": dict(attrs), "indices": ia, "mode": 4}
            mo = mlist[k] if k < len(mlist) else None
            if mo is not None and mo.type.name == "Material":
                mi = material_entry(gltf, buf, mo.read())
                if mi is not None:
                    prim["material"] = mi
            prims.append(prim)

        bone_nodes = []
        for b in smr.m_Bones:
            pid = getattr(b, "path_id", 0) or 0
            if pid not in node_of:
                die(f"{gname}: 骨 path_id={pid} 不在本包 Transform 里 —— 骨骼层与网格不同包")
            bone_nodes.append(node_of[pid])
        bind = list(mesh.m_BindPose or [])
        if len(bind) != len(bone_nodes):
            die(f"{gname}: bindPose {len(bind)} != m_Bones {len(bone_nodes)}")
        mats = []
        for x in bind:
            rows = mirror_matrix_rows(matrix_rows(x))
            mats += rows_to_column_major(rows) if not transpose_ibm else rows
        ibm = add_accessor(gltf, buf, "f", mats, len(mats) // 16, "MAT4")

        skel = ancestor_root(smr.m_Bones[0].path_id, by, node_of)
        gltf["skins"].append({"joints": bone_nodes, "inverseBindMatrices": ibm,
                              "skeleton": skel if skel is not None else bone_nodes[0],
                              "name": gname + "_skin"})
        tri = sum(gltf["accessors"][p["indices"]]["count"] // 3 for p in prims)
        gltf["meshes"].append({"name": gname + "_mesh", "primitives": prims,
                               "extras": {"unityMesh": mesh.m_Name, "vertexBytes": per,
                                          "streams": [stride[s] for s in streams],
                                          "bonesPerVert": len(irows[0])}})
        host = node_of_go.get(gpid)
        if host is None:
            die(f"{gname}: 找不到承载该网格的节点（该 GameObject 没有 Transform？）")
        # ⚠️ glTF 的 skin 挂在 **node** 上，不是挂在 mesh 上。只写 meshes/skins 两段而不在节点上
        #    点名 skin，three.js 会当成普通 Mesh 画出来——蒙皮静默失效，画面还"正常"。
        node = gltf["nodes"][host]
        node["mesh"] = len(gltf["meshes"]) - 1
        node["skin"] = len(gltf["skins"]) - 1
        sk = gltf["skins"][-1]
        rows_out.append((gname, mesh.m_Name, n, tri, len(sk["joints"]), len(prims),
                         sum(1 for p in prims if "material" in p)))

    if not gltf["meshes"]:
        die("一个网格都没装配出来（--mesh 过滤名写错了？）")
    gltf["buffers"] = [{"byteLength": len(buf.data)}]
    gltf["bufferViews"] = buf.views
    del gltf["_by"]

    print("  %-14s %-14s %8s %8s %7s %8s %8s" %
          ("节点", "Unity网格", "顶点", "三角", "关节", "子网格", "带材质"))
    for gname, mname, n, tri, nj, nprim, nmat in rows_out:
        print("  %-14s %-14s %8d %8d %7d %8d %8s" %
              (gname, mname, n, tri, nj, nprim, "%d/%d" % (nmat, nprim)))
    print("  nodes=%d roots=%d meshes=%d skins=%d materials=%d textures=%d images=%d  BIN=%d B"
          % (len(gltf["nodes"]), len(gltf["scenes"][0]["nodes"]), len(gltf["meshes"]),
             len(gltf["skins"]), len(gltf["materials"]), len(gltf["textures"]),
             len(gltf["images"]), len(buf.data)))
    if check_only:
        print("  [--check] 只装配校验，未落盘")
        return gltf, buf
    out = out_path or os.path.join(".diag", "dorm3d_gltf",
                                   os.path.basename(res_path) + ".glb")
    write_glb(out, gltf, bytes(buf.data))
    print("  -> %s (%.1f KB)" % (out, os.path.getsize(out) / 1024))
    return gltf, buf


def write_glb(path, gltf, bindata):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    j = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(j) % 4:
        j += b" "
    while len(bindata) % 4:
        bindata += b"\0"
    total = 12 + 8 + len(j) + 8 + len(bindata)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", GLB_MAGIC, GLB_VERSION, total))
        f.write(struct.pack("<II", len(j), CHUNK_JSON))
        f.write(j)
        f.write(struct.pack("<II", len(bindata), CHUNK_BIN))
        f.write(bindata)


LEGAL_ATTRS = {"POSITION", "NORMAL", "TANGENT", "COLOR_0", "COLOR_1",
                 "TEXCOORD_0", "TEXCOORD_1", "TEXCOORD_2", "JOINTS_0", "WEIGHTS_0"}
CSIZE = {5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}


def acc_bytes(g, acc):
    return acc["count"] * ITEMS[acc["type"]] * CSIZE[acc["componentType"]]


def read_acc(g, raw, bin_off, ai):
    """按 accessor 编号从 BIN 里把原始数值读回来（独立回读，不复用装配时的变量）。"""
    acc = g["accessors"][ai]
    bv = g["bufferViews"][acc["bufferView"]]
    fmt = {5121: "B", 5122: "e", 5123: "H", 5125: "I", 5126: "f"}[acc["componentType"]]
    per = ITEMS[acc["type"]]
    off = bin_off + bv["byteOffset"]
    out = []
    for i in range(acc["count"]):
        out.append(struct.unpack_from("<%d%s" % (per, fmt), raw, off + i * per * CSIZE[acc["componentType"]]))
    return acc, out


def verify(path):
    """读回自己写的 .glb 做独立断言。判据全部落在**文件字节**上，不看装配过程的中间值。"""
    raw = open(path, "rb").read()
    magic, ver, total = struct.unpack_from("<III", raw, 0)
    if magic != GLB_MAGIC or ver != 2:
        die("GLB 魔数/版本不对")
    if total != len(raw):
        die("GLB 声明长度 %d != 实际 %d" % (total, len(raw)))
    jlen, jtype = struct.unpack_from("<II", raw, 12)
    if jtype != CHUNK_JSON:
        die("第一块不是 JSON")
    g = json.loads(raw[20:20 + jlen].decode("utf-8"))
    blen, btype = struct.unpack_from("<II", raw, 20 + jlen)
    if btype != CHUNK_BIN:
        die("第二块不是 BIN")
    bin_off = 20 + jlen + 8
    if bin_off + blen != len(raw):
        die("BIN 长度 %d 与文件尾部不合（%d+%d != %d）" % (blen, bin_off, len(raw)))
    bad = []

    for i, bv in enumerate(g["bufferViews"]):
        if bv["byteOffset"] + bv["byteLength"] > blen:
            bad.append("bufferView %d 越出 BIN" % i)
    for i, acc in enumerate(g["accessors"]):
        bv = g["bufferViews"][acc["bufferView"]]
        if acc_bytes(g, acc) > bv["byteLength"]:
            bad.append("accessor %d 需要 %dB > bufferView %d 的 %dB"
                       % (i, acc_bytes(g, acc), acc["bufferView"], bv["byteLength"]))
    for ti, tex in enumerate(g.get("textures", [])):
        if not (0 <= tex["source"] < len(g.get("images", []))):
            bad.append("texture %d 指向不存在的 image" % ti)
    for ii, img in enumerate(g.get("images", [])):
        if img["bufferView"] >= len(g["bufferViews"]):
            bad.append("image %d bufferView 越界" % ii)
        else:
            off = bin_off + g["bufferViews"][img["bufferView"]]["byteOffset"]
            if raw[off:off + 8] != b"\x89PNG\r\n\x1a\n":
                bad.append("image %d 内容不是 PNG 魔数" % ii)

    for si, sk in enumerate(g.get("skins", [])):
        ibm = g["accessors"][sk["inverseBindMatrices"]]
        if ibm["type"] != "MAT4":
            bad.append("skin %d inverseBindMatrices 类型不是 MAT4" % si)
        if ibm["count"] != len(sk["joints"]):
            bad.append("skin %d: bind 矩阵 %d 个 != 关节 %d 个"
                       % (si, ibm["count"], len(sk["joints"])))
        if not (0 <= sk["skeleton"] < len(g["nodes"])):
            bad.append("skin %d skeleton 越界" % si)
        for jn in sk["joints"]:
            if not (0 <= jn < len(g["nodes"])):
                bad.append("skin %d 关节索引越界" % si)
                break
        _, cols = read_acc(g, raw, bin_off, sk["inverseBindMatrices"])
        ident = sum(1 for c in cols if tuple(round(x, 6) for x in c) ==
                    (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0))
        if ident:
            bad.append("skin %d: 有 %d 个 bind 矩阵是单位阵 —— 没做 C·M·C 共轭或读错了"
                       % (si, ident))

    for mi, me in enumerate(g.get("meshes", [])):
        pr = me["primitives"][0]
        at = pr["attributes"]
        for need in ("POSITION", "JOINTS_0", "WEIGHTS_0"):
            if need not in at:
                bad.append("mesh %d 缺 %s" % (mi, need))
        if any(x.startswith("mesh %d 缺" % mi) for x in bad):
            continue
        for k in at:
            if k not in LEGAL_ATTRS:
                bad.append("mesh %d 属性名 %s 不是 glTF 合法名 —— 前端会**静默忽略**它"
                           "（WEIGHT_0 少个 S 就是这一类）" % (mi, k))
        npos = g["accessors"][at["POSITION"]]["count"]
        for k in ("JOINTS_0", "WEIGHTS_0"):
            if g["accessors"][at[k]]["count"] != npos:
                bad.append("mesh %d: %s 条数 != 顶点数" % (mi, k))
        _, wt = read_acc(g, raw, bin_off, at["WEIGHTS_0"])
        nonfinite = [i for i, w in enumerate(wt) if not all(math.isfinite(x) for x in w)]
        if nonfinite:
            bad.append("mesh %d: %d 个顶点权重含 NaN/Inf（第一个在 %d）—— NaN 会让"
                       "\"权重和 != 1\"这类比较恒为 False，所以必须单独查"
                       % (mi, len(nonfinite), nonfinite[0]))
        off = [i for i, w in enumerate(wt)
               if not all(math.isfinite(x) for x in w) or abs(sum(w) - 1.0) > 1e-3]
        if off:
            bad.append("mesh %d: %d 个顶点权重和 != 1（第一个在 %d）" % (mi, len(off), off[0]))
        _, jt = read_acc(g, raw, bin_off, at["JOINTS_0"])
        nj = max(max(j) for j in jt)
        skname = me["name"].replace("_mesh", "_skin")
        sk = next((s for s in g["skins"] if s.get("name") == skname), None)
        if sk is None:
            bad.append("mesh %d: 找不到配套 skin %s" % (mi, skname))
        elif nj >= len(sk["joints"]):
            bad.append("mesh %d: 最大关节索引 %d >= 关节数 %d" % (mi, nj, len(sk["joints"])))
        ia_missing = [pi for pi, pr in enumerate(me["primitives"]) if "indices" not in pr]
        if ia_missing:
            bad.append("mesh %d: primitive %s 无 indices" % (mi, ia_missing))
        for pi, pr in enumerate(me["primitives"]):
            ia = pr.get("indices")
            if ia is None:
                continue
            _, ix = read_acc(g, raw, bin_off, ia)
            if g["accessors"][ia]["count"] % 3:
                bad.append("mesh %d prim %d: 索引数不是 3 的倍数" % (mi, pi))
            if not ix or max(x[0] for x in ix) >= npos:
                bad.append("mesh %d prim %d: 索引越出顶点范围" % (mi, pi))
            if "material" in pr and not (0 <= pr["material"] < len(g["materials"])):
                bad.append("mesh %d prim %d: material 索引越界" % (mi, pi))
        pmin = g["accessors"][at["POSITION"]].get("min")
        pmax = g["accessors"][at["POSITION"]].get("max")
        if pmin is None or pmax is None:
            bad.append("mesh %d: POSITION 缺 min/max（glTF 硬要求）" % mi)

    referenced = set()
    skinned = set()
    for ni, nd in enumerate(g["nodes"]):
        if "mesh" in nd and not (0 <= nd["mesh"] < len(g["meshes"])):
            bad.append("node %d mesh 索引越界" % ni)
        else:
            if "mesh" in nd:
                referenced.add(nd["mesh"])
                if "skin" in nd:
                    skinned.add(nd["mesh"])
        if "skin" in nd and not (0 <= nd["skin"] < len(g["skins"])):
            bad.append("node %d skin 索引越界" % ni)
        for c in nd.get("children", []):
            if not (0 <= c < len(g["nodes"])):
                bad.append("node %d 子索引越界" % ni)
    orphan = [i for i in range(len(g["meshes"])) if i not in referenced]
    if orphan:
        bad.append("有 %d 个 mesh 没挂在任何节点上（three.js 不会画它）: %s"
                   % (len(orphan), orphan))
    noskin = [i for i in range(len(g["meshes"])) if i not in skinned]
    if noskin:
        bad.append("有 %d 个 mesh 的宿主节点没写 skin：%s —— glTF 的 skin 挂在 **node** 上而不是 mesh 上，"
                   "漏了它 three.js 照样画得出来，但当成普通 Mesh，**蒙皮静默失效**"
                   % (len(noskin), [g["meshes"][i]["name"] for i in noskin]))
    for nd_i in g["scenes"][0]["nodes"]:
        if not (0 <= nd_i < len(g["nodes"])):
            bad.append("scene 根节点索引越界")
            break
    print("  读回: nodes=%d meshes=%d skins=%d materials=%d images=%d BIN=%dB  断言 %s"
          % (len(g["nodes"]), len(g["meshes"]), len(g["skins"]), len(g["materials"]),
             len(g["images"]), blen, "全部通过" if not bad else "%d 条失败" % len(bad)))
    for b in bad[:10]:
        print("    [FAIL] " + b)
    return not bad


def cross_check_against_source(glb_path, res_path, rows=200):
    """把 GLB 里的权重/骨号与**源包重读值**逐行比对。

    为什么必须有这条：内部不变式（权重和==1）挡不住"系统性读错"——
    把 UNorm16 当 float16 读会得到另一组自洽的数，除以自身和之后照样和为 1。
    只有拿第二个来源逐行比，才能发现整列被读错了。
    """
    raw = open(glb_path, "rb").read()
    jlen = struct.unpack_from("<I", raw, 12)[0]
    g = json.loads(raw[20:20 + jlen].decode("utf-8"))
    bin_off = 20 + jlen + 8
    env = UnityPy.load(res_path)
    bad = []
    for me in g["meshes"]:
        nm = me["extras"]["unityMesh"]
        src = next((o.read() for o in env.objects
                    if o.type.name == "Mesh" and o.read().m_Name == nm), None)
        if src is None:
            bad.append("%s: 源包里找不到同名网格" % nm)
            continue
        lay = None
        for ctx in probe.candidate_layouts(src.m_VertexData, len(probe.data_at(src))):
            if probe.self_proof(probe.decode_skin(src, ctx[0], ctx[2], ctx[3], ctx[4], ctx[5])):
                lay = ctx
                break
        if not lay:
            bad.append("%s: 源包布局反解失败" % nm)
            continue
        ch, streams, stride, base, e, n = lay[0], lay[1], lay[2], lay[3], lay[4], lay[5]
        w_src = read_plain_channel(src, ch, stride, base, e, probe.CH_BLEND_WEIGHT, n)
        if w_src is None:
            w_src = [[1.0]] * n        # 单骨部件源包无权重通道，装配器按隐式 1 填，比对要同口径
        j_src = read_plain_channel(src, ch, stride, base, e, probe.CH_BLEND_INDICES, n)
        at = me["primitives"][0]["attributes"]
        _, w_g = read_acc(g, raw, bin_off, at["WEIGHTS_0"])
        _, j_g = read_acc(g, raw, bin_off, at["JOINTS_0"])
        k = min(rows, n)
        wbad = [i for i in range(k)
                if max(abs(w_g[i][t] - (w_src[i][t] if t < len(w_src[i]) else 0.0))
                       for t in range(4)) > 1e-4]
        jbad = [i for i in range(k)
                if list(j_g[i][:len(j_src[i])]) != list(j_src[i])]
        if wbad:
            bad.append("%s: 前 %d 行里 %d 行权重与源包不符（首例 行%d GLB=%s 源=%s）"
                       % (nm, k, len(wbad), wbad[0],
                          [round(x, 5) for x in w_g[wbad[0]]],
                          [round(x, 5) for x in w_src[wbad[0]]]))
        if jbad:
            bad.append("%s: 前 %d 行里 %d 行骨号与源包不符（首例 行%d GLB=%s 源=%s）"
                       % (nm, k, len(jbad), jbad[0], list(j_g[jbad[0]]), list(j_src[jbad[0]])))
        print("  逐行比对 %-14s 前 %d 行: 权重%s 骨号%s"
              % (nm, k, "全等" if not wbad else "不符", "全等" if not jbad else "不符"))
    return bad


def main():
    ap = argparse.ArgumentParser(description="dorm3d 蒙皮包 -> .glb")
    ap.add_argument("res", help="含 Mesh + SkinnedMeshRenderer 的包路径")
    ap.add_argument("--mesh", action="append", default=None, help="只出指定网格节点名（可重复）")
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", action="store_true", help="只装配，不落盘")
    ap.add_argument("--verify", metavar="GLB", default=None, help="读回一个 glb 做独立断言")
    ap.add_argument("--against", default=None,
                    help="逐行比对源包（--verify 时给出 res 包路径）；权重和==1 这种内部不变式"
                         "挡不住系统性读错，必须有第二条来源")
    ap.add_argument("--prefab", default=None,
                    help="对应的 prefab 包（真材质由它以外链 PPtr 引用；不给则退化为包内占位材质）")
    ap.add_argument("--transpose-ibm", action="store_true", help="inverseBindMatrices 不按列主序转置")
    ap.add_argument("--no-flipuv", action="store_true", help="不翻转 UV 的 V")
    a = ap.parse_args()
    if a.verify:
        ok = verify(a.verify)
        if a.against:
            cb = cross_check_against_source(a.verify, a.against)
            for c in cb:
                print("    [FAIL] " + c)
            ok = ok and not cb
        return 0 if ok else 1
    if not os.path.isfile(a.res):
        die("文件不存在: " + a.res, 2)
    if a.prefab and not os.path.isfile(a.prefab):
        die("prefab 文件不存在: " + a.prefab, 2)
    print("装配 %s%s" % (a.res, "  (材质取自 " + a.prefab + ")" if a.prefab else ""))
    gltf, buf = build(a.res, a.mesh, a.out, a.check,
                      transpose_ibm=a.transpose_ibm, flipuv=not a.no_flipuv,
                      prefab_path=a.prefab)
    if not a.check:
        if not verify(a.out or os.path.join(".diag", "dorm3d_gltf", os.path.basename(a.res) + ".glb")):
            die("读回断言未过 —— 产物不合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
