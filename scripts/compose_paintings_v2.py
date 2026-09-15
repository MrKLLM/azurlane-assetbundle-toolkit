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


# ---------------------------------------------------------------- 渲染

def rasterize_mesh(verts, uvs, tris, tex_img, frame_w, frame_h):
    """三角形重心插值光栅化：mesh（sprite 像素坐标系, Y-up）+ UV 图集
    -> 画框大小的 RGBA numpy（Y-up）。只覆盖内容 AABB。
    返回 (ndarray RGBA Y-up, (x0,y0,x1,y1)) 或 (None, None)。"""
    tex = np.asarray(tex_img.convert("RGBA"))
    th, tw = tex.shape[:2]
    fw = max(1, int(np.ceil(frame_w)))
    fh = max(1, int(np.ceil(frame_h)))

    px = verts[:, 0]
    py = verts[:, 1]
    x0 = max(0, int(np.floor(px.min())))
    y0 = max(0, int(np.floor(py.min())))
    x1 = min(fw, int(np.ceil(px.max())) + 1)
    y1 = min(fh, int(np.ceil(py.max())) + 1)
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
    for o in env.objects:
        if o.type.name == "RectTransform":
            r = o.read()
            rects[o.path_id] = r
            go = getattr(r, "m_GameObject", None)
            go_pid = getattr(go, "m_PathID", 0) if go is not None else 0
            g = self_objs.get(go_pid)
            go_names[o.path_id] = g.read().m_Name if g else ""
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
        })
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
    # 无 mesh：sprite 矩形从纹理整块裁（flip=False 空间 -> 转 Y-up 数组）
    tw, th = tex.size
    sx0 = int(round(rect.x)); sy0 = int(round(th - rect.y - rect.height))
    sx1 = sx0 + int(round(rect.width)); sy1 = sy0 + int(round(rect.height))
    arr = np.asarray(tex.convert("RGBA"))[max(0, sy0):sy1, max(0, sx0):sx1]
    arr = arr[::-1]  # 转 Y-up
    x0 = max(0, int(round(rect.x)))
    y0 = max(0, int(round(frame[1] - rect.y - rect.height)))
    bbox = (x0, y0, x0 + arr.shape[1], y0 + arr.shape[0])
    return arr, bbox, frame


# ---------------------------------------------------------------- 布局

def layout_all(rects, father_map, children_map):
    """递归计算每个 RectTransform 的世界矩形（Y-up 画布坐标，含 localScale）。
    返回 {pid: (ox, oy, w, h)}（ox,oy = rect 左下角，已含父级累计缩放）。"""
    out = {}

    def get_size(pid):
        r = rects[pid]
        sd = r.m_SizeDelta
        return (sd.x, sd.y)

    def visit(pid, parent_box, parent_scale):
        if pid in out:
            return
        r = rects[pid]
        ox, oy, pw, ph = parent_box
        amin, amax = r.m_AnchorMin, r.m_AnchorMax
        sd = r.m_SizeDelta
        ap = r.m_AnchoredPosition
        piv = r.m_Pivot
        ls = getattr(r, "m_LocalScale", None)
        sx = (ls.x if ls else 1) or 1
        sy = (ls.y if ls else 1) or 1

        a0x, a0y = ox + amin.x * pw, oy + amin.y * ph
        a1x, a1y = ox + amax.x * pw, oy + amax.y * ph
        w = (a1x - a0x) + sd.x * parent_scale
        h = (a1y - a0y) + sd.y * parent_scale
        px = a0x + ap.x * parent_scale + (a1x - a0x) * piv.x
        py = a0y + ap.y * parent_scale + (a1y - a0y) * piv.y
        rx = px - piv.x * w
        ry = py - piv.y * h
        out[pid] = (rx, ry, w, h)
        own_scale = parent_scale * ((sx + sy) / 2.0)
        for c in children_map.get(pid, []):
            if c in rects:
                visit(c, (rx, ry, w * sx, h * sy), own_scale)

    roots = [p for p in rects if not father_map.get(p)]
    for root in roots:
        r = rects[root]
        sd = r.m_SizeDelta
        out[root] = (0.0, 0.0, sd.x, sd.y)
        sc = getattr(r, "m_LocalScale", None)
        s = ((sc.x + sc.y) / 2.0 if sc else 1) or 1
        for c in children_map.get(root, []):
            if c in rects:
                visit(c, (0.0, 0.0, sd.x, sd.y), s)
    return out, roots


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


def compose(bundle_name, out_dir, faces=None):
    """合成一个皮肤。faces=None 只出默认脸；faces=[..] 额外输出差分。"""
    rects, go_names, father_map, children_map, parts, deps = parse_painting(bundle_name)
    if not parts:
        print(f"  ✗ {bundle_name}: 没有可绘制部件")
        return False
    boxes, roots = layout_all(rects, father_map, children_map)
    order = draw_order(rects, father_map, children_map)
    rank = {p: i for i, p in enumerate(order)}

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
                # 内容在画框坐标 -> 世界(Y-up) -> PIL(Y-down)
                wx0 = rx + x0 * sx
                wy0 = ry + y0 * sy
                ww = max(1, int(round((x1 - x0) * sx)))
                wh = max(1, int(round((y1 - y0) * sy)))
                img = Image.fromarray(arr.astype(np.uint8), "RGBA")
                # arr 是 Y-up，转 PIL 需要上下翻转
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
                if (img.width, img.height) != (ww, wh):
                    img = img.resize((ww, wh), Image.BILINEAR)
                px = int(round(wx0))
                py = int(round(ch - (wy0 + wh)))
                canvas.paste(img, (px, py), img)
                cinfo.append(f"{part['name'] or pid}")
        return canvas, cinfo

    os.makedirs(out_dir, exist_ok=True)
    canvas, cinfo = render()
    base = canvas.crop(canvas.getbbox() or (0, 0, cw, ch))
    out = os.path.join(out_dir, f"{bundle_name}.png")
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
