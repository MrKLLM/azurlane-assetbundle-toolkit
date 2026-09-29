# -*- coding: utf-8 -*-
"""
静态立绘还原 v2 —— 完全由游戏官方数据驱动，不再猜名字/猜坐标/手调参数。

与 v1 (compose_paintings.py) 的本质区别：
1. 部件→纹理包来自 AssetBundles/dependencies 官方依赖表
   （PPtr.m_FileID = deps 1-based 索引，0=本体），不按命名规则猜测；
2. 每个节点用 PPtr.m_PathID 精确定位包内 Sprite/Mesh/Texture2D 对象，
   一个包里多个部件也能各取所需（v1 只取"第一个大 mesh"）；
3. 统一 Unity UI 布局数学：sprite 画框(mRawSpriteSize) 映射到
   RectTransform rect（anchor/pivot/sizeDelta/anchoredPosition/localScale
   全递归计算），mesh 内容落在画框内，背景/角色/道具同一套公式；
4. face 表情差分：paintingface/<name> 包内 Sprite 命名 1..N，
   默认脸 = prefab 引用的那张；--faces all 输出 {name}_face{k}.png。

用法:
  python compose_paintings_v2.py 2b feiteliekaer_3
  python compose_paintings_v2.py 2b --faces all --out <dir>
"""
import argparse
import json
import math
import os
import sys

import numpy as np
import UnityPy
from PIL import Image
from UnityPy import config
from UnityPy.export.Texture2DConverter import get_image_from_texture2d
from UnityPy.helpers.MeshHelper import MeshHandler

config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

AB_ROOT = r"D:\Azur Lane Assets\files\AssetBundles"
MANIFEST_PATH = r"D:\Azur Lane Assets\Output\dependency_manifest.json"
DEFAULT_OUT = r"D:\Azur Lane Assets\Output\Paintings_v2"

_manifest = None
_env_cache = {}      # bundle_name -> env / False
_obj_cache = {}      # (bundle, path_id) -> UnityPy object
_img_cache = {}      # (bundle, path_id) -> PIL RGBA (flip=False)
FACE_APPLIED = {}    # bundle_name -> 是否触发了 paintingface 脸洞叠层（扫描用）
FACE_GATE = {}       # bundle_name -> 门控实际读到的数（复扫/分诊用，见 diag/scan_faces.py）
# 关闭层过滤的实际动作（审计用）：跳过了哪些层名 / 哪些皮肤「全层都是关闭态」
INACTIVE_SKIPPED = {}
INACTIVE_ALL = set()
# face 槽在 prefab 里恒为关闭，游戏运行时才激活来显示表情差分 ⇒ 不过滤它
FACE_SLOT_EXEMPT = {"face"}
# 门控阈值：脸谱落笔处下方
#   不透明占比低于 FACE_OPAQUE_MIN -> 透明洞（脸没烤进底图）
#   底图与脸谱逐像素平均色差高于 FACE_MAD_MAX -> 那块画的不是这张脸（平涂灰块/缺头）
# 二者任一成立即判洞、叠脸。见 §14 与 §48。
FACE_OPAQUE_MIN = float(os.environ.get("FACE_OPAQUE_MIN", "0.5"))
FACE_MAD_MAX = float(os.environ.get("FACE_MAD_MAX", "30"))


def manifest():
    global _manifest
    if _manifest is None:
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            _manifest = json.load(f)
    return _manifest


def load_bundle(name):
    """按资源名（painting/2b_tex、custom_builtin…）加载，带缓存。
    本地落盘路径 = files/AssetBundles/<资源名小写>。"""
    if name in _env_cache:
        return _env_cache[name]
    path = os.path.join(AB_ROOT, name.lower().replace("/", os.sep))
    env = False
    if os.path.isfile(path):
        try:
            env = UnityPy.load(path)
        except Exception as e:
            print(f"  ! 加载 {name} 失败: {e}")
    _env_cache[name] = env
    return env


def serialized_file(env):
    """BundleFile -> 第一个 SerializedFile。"""
    from UnityPy.files.SerializedFile import SerializedFile
    bundle = list(env.files.values())[0]
    for f in bundle.files.values():
        if isinstance(f, SerializedFile):
            return f
    return list(bundle.files.values())[0]


def cab_names(env):
    """该 bundle 内 SerializedFile 的 CAB 名列表（去掉 .resS）。"""
    bundle = list(env.files.values())[0]
    return [n for n in bundle.files.keys() if isinstance(n, str) and not n.endswith(".resS")]


def find_obj(bundle_name, path_id):
    key = (bundle_name, path_id)
    if key in _obj_cache:
        return _obj_cache[key]
    env = load_bundle(bundle_name)
    obj = None
    if env:
        for o in env.objects:
            if o.path_id == path_id:
                obj = o
                break
    _obj_cache[key] = obj
    return obj


_SKEL_SUFFIX = "_SkeletonData"
_cab_owner_cache = {}


def cab_owner(prefab_bundle, cab):
    """CAB 名 -> 它所在的 bundle（本包或某个依赖包）。与 parse_painting 同一套 PPtr 口径。"""
    if prefab_bundle not in _cab_owner_cache:
        m = {}
        env = load_bundle(prefab_bundle)
        if env:
            for cn in cab_names(env):
                m[cn] = prefab_bundle
        for dep in manifest().get(prefab_bundle, {}).get("deps", []):
            d = load_bundle(dep)
            if d:
                for cn in cab_names(d):
                    m[cn] = dep
        _cab_owner_cache[prefab_bundle] = m
    return _cab_owner_cache[prefab_bundle].get(cab)


def skel_layers(prefab_bundle):
    """列出 UI prefab 里每个 `SkeletonGraphic` 节点 —— 即游戏**真正挂着**的一个 Spine 图层。

    这是分层的权威来源，用来取代「按导出目录里有哪些 .skel 猜分层」：同一个
    `Output/Spine_v2/<name>/` 里除了真分层还躺着 `_hx`（和谐版）等**变体**的 skel，
    它们不是层、是另一张画。`_hx` 的做法是**替换其中一层**（`huajia_2_hx` 的 prefab =
    `[2B, 2M, 2T_hx]`）而不是多加一层 —— 实测 234 个目录里 30 个被 glob 多画、
    15 对本体/`_hx` 的 CG 因此逐像素完全相同。取证与判据见 `docs/TROUBLESHOOTING.md` §58。

    层名取自 `skeletonDataAsset` 解析到的 `SkeletonDataAsset.m_Name` 剥掉 `_SkeletonData`
    后缀，**不受"节点名 `buleisiteB` vs 文件名 `buleisite_B`"这类命名错配影响**。
    顺带给出每层该用的 `startingAnimation` / `initialSkinName` / 激活位 / localScale /
    anchoredPosition / 绕 Z 旋转 —— 这几项画廊此前一律没读。

    返回 [] 表示读不到该 prefab 或它里面没有 SkeletonGraphic（调用方**必须**把它当错误，
    不许回落到 glob，否则等于把这个 bug 留着）。
    """
    env = load_bundle(prefab_bundle)
    if not env:
        return []
    objs = {o.path_id: o for o in env.objects}
    scr = {o.path_id: o.read().m_Name for o in env.objects if o.type.name == "MonoScript"}
    rect_of_go = {}
    for o in env.objects:
        if o.type.name == "RectTransform":
            r = o.read()
            rect_of_go[getattr(getattr(r, "m_GameObject", None), "m_PathID", 0)] = r
    ext_cabs = [x.name for x in serialized_file(env).externals]
    out = []
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        d = o.read()
        if scr.get(getattr(getattr(d, "m_Script", None), "m_PathID", 0)) != "SkeletonGraphic":
            continue
        gp = getattr(getattr(d, "m_GameObject", None), "m_PathID", 0)
        go = objs.get(gp)
        gd = go.read() if go else None
        layer, why = "", "无 skeletonDataAsset"
        p = getattr(d, "skeletonDataAsset", None)
        if p is not None:
            b = prefab_bundle
            fid = getattr(p, "m_FileID", 0)
            if fid:
                cab = ext_cabs[fid - 1] if 1 <= fid <= len(ext_cabs) else None
                b = cab_owner(prefab_bundle, cab) if cab else None
                if b is None:
                    why = "CAB 不在依赖表"
            if b:
                t = find_obj(b, getattr(p, "m_PathID", 0))
                if t is not None:
                    nm = t.read().m_Name or ""
                    layer = nm[:-len(_SKEL_SUFFIX)] if nm.endswith(_SKEL_SUFFIX) else nm
                    why = ""
                else:
                    why = "解析不到 SkeletonDataAsset 对象"
        r = rect_of_go.get(gp)
        ap = sc = [0.0, 0.0]
        rot = 0.0
        if r is not None:
            a, l = r.m_AnchoredPosition, r.m_LocalScale
            ap = [round(float(a.x), 2), round(float(a.y), 2)]
            sc = [round(float(l.x), 4), round(float(l.y), 4)]
            q = getattr(r, "m_LocalRotation", None)
            if q is not None:
                rot = round(math.degrees(2 * math.atan2(float(q.z), float(q.w))), 3)
        out.append({
            "layer": layer, "why": why,
            "node": gd.m_Name if gd else "",
            "active": bool(gd.m_IsActive) if gd is not None else None,
            "anim": str(getattr(d, "startingAnimation", "") or ""),
            "skin": str(getattr(d, "initialSkinName", "") or ""),
            "anchoredPosition": ap, "localScale": sc, "rotZ": rot,
        })
    return out


def decoded_texture(bundle_name, path_id):
    """Texture2D -> PIL（flip=False：数组行序与 UV 的 v 空间一致）。"""
    key = (bundle_name, path_id)
    if key in _img_cache:
        return _img_cache[key]
    o = find_obj(bundle_name, path_id)
    if o is None or o.type.name != "Texture2D":
        # 回退：包内第一张 Texture2D（多数 _tex 包只有一张）
        env = load_bundle(bundle_name)
        o = None
        if env:
            o = next((x for x in env.objects if x.type.name == "Texture2D"), None)
        if o is None:
            _img_cache[key] = None
            return None
    img = get_image_from_texture2d(o.read(), flip=False)
    _img_cache[key] = img
    return img


def paintingface_face(bundle_name, want="1"):
    """从 paintingface/<name> 取指定表情名(默认 '1')的 Sprite 纹理 -> (PIL RGBA Y-up, (w,h))。
    找不到该表情名则退回数字名最小的一张；无包返回 None。"""
    env = load_bundle("paintingface/" + bundle_name)
    if not env:
        return None
    spr = {}
    for o in env.objects:
        if o.type.name == "Sprite":
            s = o.read()
            spr[str(s.m_Name)] = s
    chosen = spr.get(str(want))
    if chosen is None:
        nums = sorted([k for k in spr if k.isdigit()], key=int)
        if nums:
            chosen = spr[nums[0]]
    if chosen is None:
        return None
    rd = getattr(chosen, "m_RD", None)
    tex = getattr(rd, "texture", None) if rd is not None else None
    tex_pid = getattr(tex, "m_PathID", 0) if tex is not None else 0
    img = decoded_texture("paintingface/" + bundle_name, tex_pid)
    if img is None:
        return None
    return img.convert("RGBA"), (img.width, img.height)


# ---------------------------------------------------------------- 渲染

def rasterize_mesh(verts, uvs, tris, tex_img, frame_w, frame_h):
    """三角形重心插值光栅化：mesh（sprite 像素坐标系, Y-up）+ UV 图集
    -> 内容 AABB 的 RGBA numpy（Y-up）。返回 (ndarray, (x0,y0,x1,y1)) 或 (None, None)。
    注意：mesh 顶点可以合法超出画框 mRawSpriteSize（如 kuersike_rw 头部越出 1536 框顶），
    不能把内容裁进框内——只按内容 AABB 输出，越框部分由 render() 的仿射照常映射。
    安全钳制 [-2fw..3fw]×[-2fh..3fh] 防退化控制点撑爆画布。"""
    tex = np.asarray(tex_img.convert("RGBA"))
    th, tw = tex.shape[:2]
    fw = max(1, int(np.ceil(frame_w)))
    fh = max(1, int(np.ceil(frame_h)))

    px = verts[:, 0]
    py = verts[:, 1]
    x0 = max(-2 * fw, int(np.floor(px.min())))
    y0 = max(-2 * fh, int(np.floor(py.min())))
    x1 = min(3 * fw, int(np.ceil(px.max())) + 1)
    y1 = min(3 * fh, int(np.ceil(py.max())) + 1)
    if x1 <= x0 or y1 <= y0:
        return None, None

    W, H = x1 - x0, y1 - y0
    out = np.zeros((H, W, 4), np.uint8)
    depth = np.full((H, W), -np.inf)

    tv = verts[tris]                     # (T,3,2)
    tu = uvs[tris]                       # (T,3,2)
    for ti in range(len(tris)):
        (ax, ay), (bx, by), (cx, cy) = tv[ti]
        tx0 = max(x0, int(np.floor(min(ax, bx, cx))))
        tx1 = min(x1, int(np.ceil(max(ax, bx, cx))) + 1)
        ty0 = max(y0, int(np.floor(min(ay, by, cy))))
        ty1 = min(y1, int(np.ceil(max(ay, by, cy))) + 1)
        if tx1 <= tx0 or ty1 <= ty0:
            continue
        gx = np.arange(tx0, tx1) + 0.5
        gy = np.arange(ty0, ty1) + 0.5
        FX, FY = np.meshgrid(gx, gy)
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-9:
            continue
        w1 = ((by - cy) * (FX - cx) + (cx - bx) * (FY - cy)) / d
        w2 = ((cy - ay) * (FX - cx) + (ax - cx) * (FY - cy)) / d
        w3 = 1.0 - w1 - w2
        inside = (w1 >= -1e-4) & (w2 >= -1e-4) & (w3 >= -1e-4)
        if not inside.any():
            continue
        # z 用三角形序号（绘制顺序后画盖先画）
        zval = np.where(inside, float(ti), -np.inf)
        win = depth[ty0 - y0:ty1 - y0, tx0 - x0:tx1 - x0]
        take = inside & (zval >= win)
        if not take.any():
            continue
        uu = w1 * tu[ti, 0, 0] + w2 * tu[ti, 1, 0] + w3 * tu[ti, 2, 0]
        vv = w1 * tu[ti, 0, 1] + w2 * tu[ti, 1, 1] + w3 * tu[ti, 2, 1]
        sx = np.clip(np.rint(uu * (tw - 1)), 0, tw - 1).astype(np.int64)
        sy = np.clip(np.rint(vv * (th - 1)), 0, th - 1).astype(np.int64)
        pix = tex[sy, sx]
        sub = out[ty0 - y0:ty1 - y0, tx0 - x0:tx1 - x0]
        sub[take] = pix[take]
        win[take] = zval[take]
        out[ty0 - y0:ty1 - y0, tx0 - x0:tx1 - x0] = sub
        depth[ty0 - y0:ty1 - y0, tx0 - x0:tx1 - x0] = win

    if not out.any():
        return None, None
    return out, (x0, y0, x1, y1)


# ---------------------------------------------------------------- 解析


def parse_painting(bundle_name):
    """读取 painting/<name> prefab。
    返回 (rects, go_names, father_map, children_map, nodes, deps)。
    PPtr 解析：FileID=0 本包；FileID=N -> externals[N-1] 的 CAB 所在依赖包。"""
    path = os.path.join(AB_ROOT, "painting", bundle_name)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    env = UnityPy.load(path)
    self_objs = {o.path_id: o for o in env.objects}
    base_name = f"painting/{bundle_name}"

    deps = manifest().get(base_name, {}).get("deps", [])
    # PPtr FileID -> 实际 bundle：用 SerializedFile externals 表（CAB 名）解析。
    # 注意：externals 顺序 ≠ manifest deps 排序，必须以 externals 为准。
    sf_base = serialized_file(env)
    ext_cabs = [x.name for x in sf_base.externals]
    cab2bundle = {}
    for cab in cab_names(env):
        cab2bundle[cab] = base_name
    for dep in deps:
        denv = load_bundle(dep)
        if denv:
            for cab in cab_names(denv):
                cab2bundle[cab] = dep

    def resolve_bundle(file_id):
        if file_id == 0:
            return base_name
        if 1 <= file_id <= len(ext_cabs):
            b = cab2bundle.get(ext_cabs[file_id - 1])
            if b:
                return b
            print(f"  ! FileID={file_id} CAB={ext_cabs[file_id-1]} 不在依赖表中")
        return None

    rects = {}
    go_names = {}
    children_map = {}
    father_map = {}
    rect_go = {}       # RectTransform pid -> GameObject pid（判激活位要用）
    go_active = {}     # GameObject pid -> m_IsActive
    for o in env.objects:
        if o.type.name == "RectTransform":
            r = o.read()
            rects[o.path_id] = r
            go = getattr(r, "m_GameObject", None)
            go_pid = getattr(go, "m_PathID", 0) if go is not None else 0
            g = self_objs.get(go_pid)
            if g is not None:
                gd = g.read()
                go_names[o.path_id] = gd.m_Name
                rect_go[o.path_id] = go_pid
                go_active[go_pid] = bool(gd.m_IsActive)
            else:
                go_names[o.path_id] = ""
            f = getattr(r, "m_Father", None)
            father_map[o.path_id] = getattr(f, "m_PathID", 0) if f is not None else 0
            children_map[o.path_id] = [getattr(c, "m_PathID", 0)
                                       for c in (getattr(r, "m_Children", None) or [])]
        elif o.type.name == "Transform":
            t = o.read()
            f = getattr(t, "m_Father", None)
            pid_go = getattr(t, "m_GameObject", None)
            go_pid = getattr(pid_go, "m_PathID", 0) if pid_go is not None else 0
            # 无 RectTransform 的节点不参与 UI 布局，记名即可
            g = self_objs.get(go_pid)
            if g is not None:
                go_names.setdefault(("T", o.path_id), g.read().m_Name)

    def resolve(pid_ref_bundle, path_id):
        return pid_ref_bundle, path_id


    nodes = []
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        d = o.read()
        try:
            spr = d.m_Sprite
        except Exception:
            continue
        path_id = getattr(spr, "m_PathID", 0)
        file_id = getattr(spr, "m_FileID", 0)
        if not path_id:
            continue
        go = getattr(d, "m_GameObject", None)
        go_pid = getattr(go, "m_PathID", 0) if go is not None else 0
        # GameObject -> RectTransform（同 GO 的 rect）
        rect_pid = next((rp for rp, rp2 in
                         ((rp, getattr(rects[rp], "m_GameObject", None)) for rp in rects)
                         if rp2 is not None and getattr(rp2, "m_PathID", 0) == go_pid),
                        go_pid)
        # PPtr 解析：FileID=0 -> 本包；FileID=N -> externals[N-1] 对应依赖包
        spr_bundle = resolve_bundle(file_id)
        if spr_bundle is None:
            print(f"  ! {''}FileID={file_id} 无法解析，跳过部件")
            continue
        # 同 GO 上的 mesh 引用（独立 FileID，需单独解析）
        mesh_pid = 0
        mesh_bundle = spr_bundle
        try:
            m = d.mMesh
            mesh_pid = getattr(m, "m_PathID", 0)
            if mesh_pid:
                mb = resolve_bundle(getattr(m, "m_FileID", 0))
                if mb:
                    mesh_bundle = mb
        except Exception:
            pass
        frame = None
        try:
            rs = d.mRawSpriteSize
            if rs and rs.x > 0 and rs.y > 0:
                frame = (rs.x, rs.y)
        except Exception:
            pass
        nodes.append({
            "rect_pid": rect_pid,
            "go_pid": go_pid,
            "name": go_names.get(rect_pid) or go_names.get(go_pid) or "",
            "spr_bundle": spr_bundle,
            "spr_pid": path_id,
            "mesh_pid": mesh_pid,
            "mesh_bundle": mesh_bundle,
            "frame": frame,
            "active": True,
        })

    # 游戏侧的层开关：GameObject.m_IsActive=False 的节点根本不渲染（Unity 语义下父节点关了
    # 整棵子树都不画）。此前不读这个位 ⇒ 把 `shadow`（纯黑剪影）/`shop_hx`（"NOT ABLE TO
    # DISPLAY" 遮挡条）/`chicheng_alter_rw1..4`（备用画法）这类**关着的层**画在角色身上，
    # 表现为头部整片发黑、身上贴白条。旁证：`_n`（无背景版）皮肤的 `bj` 背景节点恒为 False，
    # 与「_n 就是不显示背景」的语义对上 ⇒ 这个位是游戏的真开关，不是我们的启发式。
    def eff_active(rect_pid, go_pid):
        seen, cur = set(), rect_pid
        while cur and cur not in seen:
            seen.add(cur)
            g = rect_go.get(cur)
            if g is not None and not go_active.get(g, True):
                return False
            cur = father_map.get(cur) or 0
        return go_active.get(go_pid, True)   # rect_pid 兜底成 go_pid 的部件走这一支

    for n in nodes:
        n["active"] = eff_active(n["rect_pid"], n["go_pid"])
    return rects, go_names, father_map, children_map, nodes, deps


def build_part(part, face_sprite_name=None):
    """把一个解析出的部件渲染成 (RGBA numpy Y-up, bbox, frame)。
    优先 mesh 光栅化；无 mesh 时用 Sprite 矩形整块裁纹理。"""
    sbundle, spid = part["spr_bundle"], part["spr_pid"]
    so = find_obj(sbundle, spid)
    if so is None:
        return None
    sdata = so.read()
    # 纹理指针（字段名随 UnityPy 版本变化：texture / m_Texture；再兜底包内第一张）
    tex_pid = 0
    rd = getattr(sdata, "m_RD", None)
    for attr in ("texture", "m_Texture"):
        t = getattr(rd, attr, None) if rd is not None else None
        pid = getattr(t, "m_PathID", None) if t is not None else None
        if pid:
            tex_pid = pid
            break
    if not tex_pid:
        t = getattr(sdata, "m_Texture", None)
        tex_pid = getattr(t, "m_PathID", 0) if t is not None else 0
    # 表情差分替换：face 部件按名字换同包 Sprite
    if face_sprite_name is not None:
        env = load_bundle(sbundle)
        for o in env.objects:
            if o.type.name == "Sprite" and str(o.read().m_Name) == str(face_sprite_name):
                so = o
                sdata = o.read()
                part = dict(part, spr_pid=o.path_id)
                rd2 = getattr(sdata, "m_RD", None)
                tex_pid = (getattr(rd2, "texture", None) or
                           getattr(rd2, "m_Texture", None) or
                           getattr(sdata, "m_Texture", None))
                tex_pid = getattr(tex_pid, "m_PathID", 0) if tex_pid is not None else 0
                break
    tex = decoded_texture(sbundle, tex_pid)
    if tex is None:
        return None
    rect = sdata.m_Rect
    frame = part["frame"] or (rect.width, rect.height)
    if frame[0] <= 0 or frame[1] <= 0:
        frame = (rect.width, rect.height)

    mesh_pid = part["mesh_pid"]
    if mesh_pid:
        mo = find_obj(part.get("mesh_bundle", sbundle), mesh_pid)
        if mo is not None and mo.type.name == "Mesh":
            m = mo.read()
            try:
                h = MeshHandler(m)
                h.process()
                verts = np.asarray(h.m_Vertices, np.float64)[:, :2]
                uvs = np.asarray(h.m_UV0, np.float64)[:, :2]
                tris = np.asarray(h.get_triangles(), np.int64).reshape(-1, 3)
            except Exception as e:
                print(f"    ! mesh 解析失败 {sbundle}:{mesh_pid}: {e}")
                verts = None
            if verts is not None and len(verts) == len(uvs) and len(tris):
                img, bbox = rasterize_mesh(verts, uvs, tris, tex, *frame)
                if img is not None:
                    return img, bbox, frame
    # 无 mesh：sprite 矩形从纹理整块裁。
    # decoded_texture 用 flip=False 读出 —— 数组第 0 行就是 v=0（Unity 底部），
    # 而 m_Rect.y 本身就是自底坐标，直接切片得到的就是 Y-up 内容，无需再翻转。
    # （旧版这里 th-rect.y-h 再 [::-1] 是双重翻转，正是背景层上下颠倒的根因）
    # 绘制画框 = 纹理矩形本身：Unity UI Image 语义是把 textureRect 拉伸铺满
    # RectTransform。不能用 CanvasRenderer.mRawSpriteSize 当画框——多背景视差皮肤
    # （i404 型）的每条背景带都记录着切分前原图尺寸(2048x1770)，按它缩放会把
    # 竖带横向压窄 2 倍，拼不满留下黑洞（§6 第 2 条的根因）。
    sx0 = int(round(rect.x)); sy0 = int(round(rect.y))
    sx1 = sx0 + int(round(rect.width)); sy1 = sy0 + int(round(rect.height))
    arr = np.asarray(tex.convert("RGBA"))[sy0:sy1, sx0:sx1]
    bbox = (0, 0, arr.shape[1], arr.shape[0])
    frame = (float(rect.width), float(rect.height))
    return arr, bbox, frame


# ---------------------------------------------------------------- 布局

def layout_all(rects, father_map, children_map):
    """正确的 Unity UI 布局：
    1) 局部空间纯 anchor 数学（sizeDelta/anchoredPosition 不乘父 scale）；
    2) 递归把局部 rect 经「父局部→父世界」仿射映射到世界（继承全部祖先缩放）；
    3) 节点自身 localScale 绕 pivot 缩放（负值 = 镜像，记入 mirrors）。
    root 自身 scale 归一为 1（游戏屏幕适配缩放，不影响层间比例）。
    返回 ({pid: (rx,ry,w,h) 世界 Y-up}, {pid: (mx,my)}, roots)。"""
    boxes, mirrors = {}, {}

    def local_rect(r, pw, ph):
        """节点在父局部空间的 rect（Y-up，父左下为原点）。"""
        amin, amax = r.m_AnchorMin, r.m_AnchorMax
        sd = r.m_SizeDelta
        ap = r.m_AnchoredPosition
        piv = r.m_Pivot
        w = (amax.x - amin.x) * pw + sd.x
        h = (amax.y - amin.y) * ph + sd.y
        px = amin.x * pw + ap.x + (amax.x - amin.x) * pw * piv.x
        py = amin.y * ph + ap.y + (amax.y - amin.y) * ph * piv.y
        return (px - piv.x * w, py - piv.y * h, w, h)

    def visit(pid, p_local, p_world):
        r = rects[pid]
        lx, ly, lw, lh = local_rect(r, p_local[2], p_local[3])
        # 父局部 -> 父世界 仿射（纯缩放+平移）
        # 注意：local_rect 返回的 (lx,ly) 已是「相对父节点局部矩形左下角(0,0)」的偏移，
        # 不能再减 p_local[0]/[1]（那是父节点在它自己父级里的位置）——多减会让
        # 嵌套容器(如 layers)的子层整体错位甩到左下（jialimaoxian 角色脱离背景的根因）。
        ax = p_world[2] / p_local[2] if p_local[2] else 1.0
        ay = p_world[3] / p_local[3] if p_local[3] else 1.0
        wx = p_world[0] + lx * ax
        wy = p_world[1] + ly * ay
        ww, wh = lw * ax, lh * ay
        # 自身 localScale 绕 pivot 缩放（负值镜像）
        ls = getattr(r, "m_LocalScale", None)
        sx = (ls.x if ls else 1) or 1
        sy = (ls.y if ls else 1) or 1
        piv = r.m_Pivot
        pcx, pcy = wx + piv.x * ww, wy + piv.y * wh
        ww2, wh2 = ww * abs(sx), wh * abs(sy)
        wx2, wy2 = pcx - piv.x * ww2, pcy - piv.y * wh2
        boxes[pid] = (wx2, wy2, ww2, wh2)
        mirrors[pid] = (sx < 0, sy < 0)
        for c in children_map.get(pid, []):
            if c in rects:
                visit(c, (lx, ly, lw, lh), (wx2, wy2, ww2, wh2))

    roots = [p for p in rects if not father_map.get(p)]
    for root in roots:
        r = rects[root]
        sd = r.m_SizeDelta
        boxes[root] = (0.0, 0.0, sd.x, sd.y)
        mirrors[root] = (False, False)
        for c in children_map.get(root, []):
            if c in rects:
                visit(c, (0.0, 0.0, sd.x, sd.y), (0.0, 0.0, sd.x, sd.y))
    return boxes, mirrors, roots


def draw_order(rects, father_map, children_map):
    """Unity 层级遍历序 = 绘制序（父先子后，兄弟按 m_Children，后画在上）。"""
    order = []
    seen = set()

    def visit(pid):
        if pid in seen:
            return
        seen.add(pid)
        order.append(pid)
        for c in children_map.get(pid, []):
            if c in rects:
                visit(c)
    for p in rects:
        if not father_map.get(p):
            visit(p)
    for p in rects:
        visit(p)
    return order


# ---------------------------------------------------------------- 合成

LIGHTING_SKIP = True


def is_lighting(arr):
    """可见像素 80% 近纯白 -> 游戏内加算光效层，直接贴会洗白，跳过。"""
    a = arr[..., 3]
    vis = a > 30
    if vis.sum() < 100:
        return False
    rgb = arr[..., :3].astype(np.int16)[vis]
    white = (rgb.min(axis=1) > 240)
    return white.mean() >= 0.80


def compose(bundle_name, out_dir, faces=None, save=True):
    """合成一个皮肤。faces=None 只出默认脸；faces=[..] 额外输出差分。save=False 只渲染判定不落盘。"""
    # 每个 bundle 处理前释放解码缓存（4096² ASTC 一张 ~64MB，长跑必须清）
    _env_cache.clear()
    _obj_cache.clear()
    _img_cache.clear()
    rects, go_names, father_map, children_map, parts, deps = parse_painting(bundle_name)
    if not parts:
        print(f"  ✗ {bundle_name}: 没有可绘制部件")
        return False
    # 只画游戏里真开着的层。全层都是关闭态时**一律不动**：过滤会把整张画清空，
    # 而「游戏运行时激活哪一层」没有权威依据，宁可维持现状并记进清单交人工裁定。
    kept = [p for p in parts
            if p.get("active", True) or p["name"] in FACE_SLOT_EXEMPT]
    dropped = [p["name"] or str(p["rect_pid"]) for p in parts
               if not (p.get("active", True) or p["name"] in FACE_SLOT_EXEMPT)]
    if kept:
        if dropped:
            INACTIVE_SKIPPED[bundle_name] = dropped
        parts = kept
    else:
        INACTIVE_ALL.add(bundle_name)
        INACTIVE_SKIPPED.pop(bundle_name, None)
        print(f"  ! {bundle_name}: {len(parts)} 层全为关闭态，未过滤（交人工裁定）")
    boxes, mirrors, roots = layout_all(rects, father_map, children_map)
    order = draw_order(rects, father_map, children_map)
    rank = {p: i for i, p in enumerate(order)}

    # face 节点：GameObject 名为 'face' 的 RectTransform（其 m_Sprite 常为空，故不在 parts 里）。
    # 真脸在独立 paintingface/<name> 包，需按此节点世界矩形叠回，否则 _rw 留脸洞者出白块。
    face_pid = next((rp for rp in rects if go_names.get(rp) == "face"), None)
    FACE_DEFAULT = os.environ.get("FACE_DEFAULT", "1")

    # 画布 = root 矩形范围
    allb = list(boxes.values())
    cw = int(max(b[0] + b[2] for b in allb))
    ch = int(max(b[1] + b[3] for b in allb))
    if not (256 <= cw <= 12000 and 256 <= ch <= 12000):
        print(f"  ! 画布尺寸异常 {cw}x{ch}，截断到 12000")
        cw, ch = min(cw, 12000), min(ch, 12000)

    # 部件按 rect 归属分组（同一 GO 多 renderer 时各自绘制）
    by_rect = {}
    for p in parts:
        by_rect.setdefault(p["rect_pid"], []).append(p)

    def render(face_override=None):
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        cinfo = []
        for pid in order:
            for part in by_rect.get(pid, []):
                try:
                    res = build_part(dict(part), face_sprite_name=face_override)
                except Exception as e:
                    print(f"    ! {part['name']} 渲染失败: {e}")
                    continue
                if res is None:
                    continue
                arr, bbox, frame = res
                if LIGHTING_SKIP and is_lighting(arr):
                    cinfo.append(f"lighting-skip:{part['name']}")
                    continue
                rx, ry, rw, rh = boxes.get(pid, (0, 0, frame[0], frame[1]))
                sx = rw / frame[0] if frame[0] else 1
                sy = rh / frame[1] if frame[1] else 1
                x0, y0, x1, y1 = bbox
                mx, my = mirrors.get(pid, (False, False))
                if mx:  # 画框内水平镜像
                    x0, x1 = frame[0] - x1, frame[0] - x0
                if my:  # 画框内垂直镜像
                    y0, y1 = frame[1] - y1, frame[1] - y0
                # 内容在画框坐标 -> 世界(Y-up) -> PIL(Y-down)
                wx0 = rx + x0 * sx
                wy0 = ry + y0 * sy
                ww = max(1, int(round((x1 - x0) * sx)))
                wh = max(1, int(round((y1 - y0) * sy)))
                img = Image.fromarray(arr.astype(np.uint8), "RGBA")
                # arr 是 Y-up，转 PIL 需要上下翻转
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
                if mx:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                if my:
                    img = img.transpose(Image.FLIP_TOP_BOTTOM)
                if (img.width, img.height) != (ww, wh):
                    img = img.resize((ww, wh), Image.BILINEAR)
                px = int(round(wx0))
                py = int(round(ch - (wy0 + wh)))
                canvas.paste(img, (px, py), img)
                cinfo.append(f"{part['name'] or pid}")
        # ---- 叠 paintingface 默认脸（只在脸谱自身落笔处量底图：透明洞看不透明占比，
        #      「这里画的是不是这张脸」看与脸谱的逐像素色差 MAD。sat≥30 那版判据会把淡色真脸
        #      整片误判成洞——48 张带标签样本上 MAD 两侧差 5 倍，见 §14 与 §48）----
        if face_pid is not None and face_pid in boxes:
            rx, ry, rw, rh = boxes[face_pid]
            fpx = int(round(rx)); fpy = int(round(ch - (ry + rh)))
            fww = max(1, int(round(rw))); fwh = max(1, int(round(rh)))
            fx = paintingface_face(bundle_name, FACE_DEFAULT if face_override is None else face_override)
            if fx is not None and fww > 8 and fwh > 8:
                fimg, (fw, fh) = fx
                mx, my = mirrors.get(face_pid, (False, False))
                fimg = fimg.transpose(Image.FLIP_TOP_BOTTOM)   # Y-up -> PIL Y-down
                if mx:
                    fimg = fimg.transpose(Image.FLIP_LEFT_RIGHT)
                if my:
                    fimg = fimg.transpose(Image.FLIP_TOP_BOTTOM)
                if (fimg.width, fimg.height) != (fww, fwh):
                    fimg = fimg.resize((fww, fwh), Image.BILINEAR)
                sp = np.asarray(fimg).astype(int)
                foot = sp[..., 3] > 200                        # 脸谱真正落笔的像素
                n_foot = int(foot.sum())
                if n_foot >= 64:
                    # PIL crop 越界部分补 0（透明），语义上等于「那里没画」
                    sub = np.asarray(canvas.crop((fpx, fpy, fpx + fww, fpy + fwh))).astype(int)
                    rgb = sub[..., :3]
                    sat = rgb.max(axis=2) - rgb.min(axis=2)
                    opq = (sub[..., 3] >= 250) & foot
                    frac_opaque = float(opq.sum()) / n_foot
                    frac_realart = float((opq & (sat >= 30)).sum()) / n_foot
                    # 底图在脸槽处画的是不是这张脸：直接和脸谱逐像素比色差。
                    # 可比像素 <64 说明底图这里几乎没落笔 -> 属透明洞，交给 frac_opaque 分支。
                    mad = float(np.abs(sp[..., :3] - rgb)[opq].mean()) if int(opq.sum()) >= 64 else None
                    hole = frac_opaque < FACE_OPAQUE_MIN or mad is None or mad > FACE_MAD_MAX
                    if face_override is None:
                        FACE_GATE[bundle_name] = {
                            "n_foot": n_foot,
                            "frac_opaque": frac_opaque,
                            "frac_realart": frac_realart,   # 已退役的 sat 判据，仅留作与 §14 对照
                            "mad": mad,
                            "hole": hole,
                            # 脸槽在画布上的像素框，供「量在盘产物」的复核工具对齐用
                            "face_px": (fpx, fpy, fww, fwh),
                        }
                    if hole:
                        canvas.paste(fimg, (fpx, fpy), fimg)
                        cinfo.append(f"face-overlay:{FACE_DEFAULT if face_override is None else face_override}")
                    else:
                        cinfo.append(f"face-skip(mad={mad:.1f})")
        return canvas, cinfo

    os.makedirs(out_dir, exist_ok=True)
    canvas, cinfo = render()
    face_applied = any(str(x).startswith("face-overlay") for x in cinfo)
    FACE_APPLIED[bundle_name] = face_applied
    bb = canvas.getbbox() or (0, 0, cw, ch)
    base = canvas.crop(bb)
    if bundle_name in FACE_GATE:
        # 成品 = 画布按 getbbox 裁过，落盘坐标 = 画布坐标 - 此偏移
        FACE_GATE[bundle_name]["crop_off"] = (bb[0], bb[1])
        FACE_GATE[bundle_name]["canvas"] = (cw, ch)
    out = os.path.join(out_dir, f"{bundle_name}.png")
    if save:
        base.save(out)
        print(f"✓ {bundle_name}: {len(parts)} 部件 / 画出 {len(cinfo)} 层 / "
              f"画布 {cw}x{ch} -> {base.size}  {out}")

    # 表情差分：找 face 部件所在包，列出全部 Sprite
    if faces:
        face_part = next((p for p in parts if p["name"] == "face"), None)
        if face_part:
            env = load_bundle(face_part["spr_bundle"])
            names = []
            if env:
                for o in env.objects:
                    if o.type.name == "Sprite":
                        n = str(o.read().m_Name)
                        if n.isdigit():
                            names.append(n)
            for n in sorted(set(names), key=int):
                canvas, _ = render(face_override=n)
                b = canvas.crop(canvas.getbbox() or (0, 0, cw, ch))
                fp = os.path.join(out_dir, f"{bundle_name}_face{n}.png")
                b.save(fp)
            print(f"  face 差分 x{len(set(names))}: {sorted(set(names), key=int)}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--faces", default=None,
                    help="all=导出全部表情差分（仅 face 部件存在的皮肤）")
    args = ap.parse_args()
    ok = fail = 0
    for n0 in args.names:
        n = n0.strip()
        if not n:
            continue
        try:
            if compose(n, args.out, faces="all" if args.faces == "all" else None):
                ok += 1
            else:
                fail += 1
        except Exception as e:
            print(f"✗ {n}: {e}")
            fail += 1
    print(f"\n完成 {ok}，失败 {fail} -> {args.out}")


if __name__ == "__main__":
    main()
