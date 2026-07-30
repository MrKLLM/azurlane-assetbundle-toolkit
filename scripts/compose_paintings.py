# -*- coding: utf-8 -*-
# 多部件立绘合成脚本（修复版）
# 修复点：
#   1) PAINTING_DIR 指向真实的 painting 资源目录（原代码误指向 scripts/）
#   2) find_tex_path 去掉未定义变量 `_`，补充「去下划线」命名变体（如 shop_hx -> shophx）
#   3) root 根节点（背着主立绘 _tex）不再被跳过
#   4) 合成前将 mesh 局部坐标图按 RectTransform 的 sizeDelta 缩放对齐到画布像素
#   坐标系约定：Unity UI 为 Y 轴向上；PIL 图像为 Y 轴向下。
#   组件原点(origin) 以「画布左下角为 (0,0)、Y 向上」计算，粘贴时再翻转成 PIL 坐标。
import os
import UnityPy
from PIL import Image
from UnityPy.helpers.MeshHelper import MeshHandler
from UnityPy.export.Texture2DConverter import get_image_from_texture2d

# 真实 painting 资源目录（绝对路径，避免误指向脚本目录）
PAINTING_DIR = r"D:\Azur Lane Assets\files\AssetBundles\painting"
# 面部特写资源目录（独立存放，命名约定 = {bundle_name}，无 _tex 后缀）
PAINTINGFACE_DIR = r"D:\Azur Lane Assets\files\AssetBundles\paintingface"

def find_tex_path(base_bundle, go_name):
    """根据组件名查找对应的 _tex 资源包。
    参数:
        base_bundle: 基础 bundle 名（如 aerbien_2）
        go_name:     RectTransform 对应的 GameObject 名（如 build / aerbien_2_rw / shop_hx / face）
    返回:
        找到则返回完整路径，否则返回 None
    """
    # 规范化：去掉下划线（部分 _tex 包会把 shop_hx 存成 shophx）
    def norm(s):
        return s.replace('_', '')
    base_norm = norm(base_bundle)
    go_norm = norm(go_name)

    candidates = [
        f'{go_name}_tex',                  # build        -> build_tex
        f'{base_bundle}_{go_name}_tex',    # aerbien_3+shop_hx -> aerbien_3_shop_hx_tex
        f'{base_bundle}_{go_norm}_tex',    #               -> aerbien_3_shophx_tex（去组件下划线）
        f'{base_norm}_{go_norm}_tex',      # 兜底：基名也去下划线
    ]
    # 小写变体（部分包名为全小写）
    candidates += [c.lower() for c in candidates]

    for cand in candidates:
        p = os.path.join(PAINTING_DIR, cand)
        if os.path.exists(p):
            return p

    # 兜底：面部特写存放在 paintingface/ 独立目录，命名约定 = {bundle_name}（无 _tex 后缀）
    # 例如：feiteliekaer_3 的 face 节点引用 paintingface/feiteliekaer_3 包
    # 注意：只对 `face` 节点应用此兜底，否则其他找不到 _tex 的 UI 热区会被错误匹配到 paintingface/
    if go_name == 'face':
        face_p = os.path.join(PAINTINGFACE_DIR, base_bundle)
        if os.path.exists(face_p):
            return face_p
    return None

def synthesize_tex_bundle(bundle_path):
    """从单个 _tex 包还原单部件图像（mesh 局部坐标，Y 轴已校正为正向）。
    参数: bundle_path 单个 _tex 资源包路径
    返回: PIL.Image（RGBA），失败时返回 None 或原始纹理图
    """
    try:
        env = UnityPy.load(bundle_path)
    except Exception as e:
        print(f'Failed to load {bundle_path}: {e}')
        return None

    texture_img_no_flip = None
    texture_img_flip = None
    mesh_obj = None

    for obj in env.objects:
        if obj.type.name == 'Texture2D':
            data = obj.read()
            texture_img_no_flip = get_image_from_texture2d(data, flip=False)
            texture_img_flip = get_image_from_texture2d(data, flip=True)
        elif obj.type.name == 'Mesh':
            data = obj.read()
            if data.m_VertexData and data.m_VertexData.m_VertexCount > 10:
                mesh_obj = data

    if not texture_img_no_flip:
        return None
    if not mesh_obj:
        # Sprite 资源（无 mesh 配套）：GPU 存储 Y 向下，用 flip=True 修正
        return texture_img_flip

    try:
        handler = MeshHandler(mesh_obj)
        handler.process()
    except Exception as e:
        print(f'Mesh processing failed: {e}')
        return texture_img_no_flip

    positions = handler.m_Vertices
    uvs = handler.m_UV0

    if not positions or not uvs or len(positions) != len(uvs):
        return texture_img_no_flip

    n = len(positions)
    if n < 4:
        return texture_img_no_flip

    aabb = mesh_obj.m_LocalAABB
    # Bug #1 修正：以 AABB 最小角为原点，画布尺寸 = 2 * extent
    min_x = aabb.m_Center.x - aabb.m_Extent.x
    min_y = aabb.m_Center.y - aabb.m_Extent.y
    out_w = int(2 * aabb.m_Extent.x) + 1
    out_h = int(2 * aabb.m_Extent.y) + 1

    if out_w <= 0 or out_h <= 0 or out_w > 8192 or out_h > 8192:
        return texture_img_no_flip

    tex_w, tex_h = texture_img_no_flip.size

    import numpy as np
    tex_arr = np.array(texture_img_no_flip)
    out_arr = np.zeros((out_h, out_w, 4), dtype=np.uint8)

    # 倒序遍历四边形面，保证绘制顺序正确
    for i in range(n - 4, -1, -4):
        v1_u, v1_v = uvs[i]
        v2_u, v2_v = uvs[i + 2]
        # 顶点按 AABB 最小角平移到图像坐标系（Y 向上）
        px = int(positions[i][0] - min_x)
        py = int(positions[i][1] - min_y)

        v1x = max(0, min(tex_w - 1, round(v1_u * tex_w)))
        v1y = max(0, min(tex_h - 1, round(v1_v * tex_h)))
        v2x = max(0, min(tex_w - 1, round(v2_u * tex_w)))
        v2y = max(0, min(tex_h - 1, round(v2_v * tex_h)))

        if v1x > v2x:
            v1x, v2x = v2x, v1x
        if v1y > v2y:
            v1y, v2y = v2y, v1y

        block_w = v2x - v1x
        block_h = v2y - v1y

        if block_w <= 0 or block_h <= 0:
            continue

        src = tex_arr[v1y:v2y, v1x:v2x]

        dst_y1 = max(0, py)
        dst_y2 = min(out_h, py + block_h)
        dst_x1 = max(0, px)
        dst_x2 = min(out_w, px + block_w)

        src_y1 = dst_y1 - py
        src_y2 = src_y1 + (dst_y2 - dst_y1)
        src_x1 = dst_x1 - px
        src_x2 = src_x1 + (dst_x2 - dst_x1)

        if dst_y2 > dst_y1 and dst_x2 > dst_x1:
            out_arr[dst_y1:dst_y2, dst_x1:dst_x2] = src[src_y1:src_y2, src_x1:src_x2]

    # flip=False 读出的纹理顶点 Y 向上写入数组后上下颠倒，这里翻转回正向（顶=顶）
    return Image.fromarray(out_arr).transpose(Image.FLIP_TOP_BOTTOM)

import numpy as np

def _is_lighting_overlay(img):
    """判定部件图是否为「光效/圣光/泛光」层（应跳过，避免把画布某块洗白）。

    判定依据（基于内容而非尺寸）：
      - 可见像素(α>30)中 ≥ 80% 接近纯白：RGB 三通道均 > 240 且通道间极差 < 10
    这样能区分：
      - 光效层：aerbien_3_shophx_tex（100% 像素 RGB=255）→ 跳过
      - 主图（含大量彩色）：肤色、衣服、背景都不到 80% 纯白 → 保留
      - 雪景/白衣角色：白衣服+皮肤+头发多色块，纯白像素 < 80% → 保留
    """
    try:
        arr = np.array(img)
    except Exception:
        return False
    if arr.ndim != 3 or arr.shape[2] < 4:
        return False
    rgb = arr[..., :3].astype(np.int16)
    a = arr[..., 3]
    visible = a > 30
    if visible.sum() < 100:  # 几乎全透明 → 不是光效，让后续正常处理
        return False
    pix = rgb[visible]
    is_pure_white = ((pix[:, 0] > 240) & (pix[:, 1] > 240) & (pix[:, 2] > 240) &
                     (pix.max(axis=1) - pix.min(axis=1) < 10))
    ratio = is_pure_white.sum() / len(pix)
    return ratio >= 0.80

def build_draw_order(rects, path_to_name, root_rect):
    """返回绘制顺序（path_id 列表，前者先绘制=在下层）。
    规则：父节点先于子节点（子覆盖父）；同层兄弟按 Transform.m_Children 顺序（后者覆盖前者）。
    这样背景(bj)自然落在人物(rw)之下，无需用面积排序或跳过规则来"猜"Z序。"""
    parent_of = {}
    raw_children = {}
    for pid, r in rects.items():
        f = getattr(r, 'm_Father', None)
        parent_of[pid] = f.path_id if (f and f.path_id) else None
        raw_children.setdefault(parent_of[pid], []).append(pid)
    # 用 m_Children 顺序矫正兄弟顺序（最权威的层级意图）
    children_of = {}
    for pid, r in rects.items():
        ch = getattr(r, 'm_Children', []) or []
        ordered = []
        seen = set()
        for c in ch:
            cp = getattr(c, 'path_id', None)
            if cp in rects and cp not in seen:
                ordered.append(cp); seen.add(cp)
        # 兜底：m_Children 未覆盖到的子节点按 m_Father 出现顺序补上
        for c in raw_children.get(pid, []):
            if c not in seen:
                ordered.append(c); seen.add(c)
        children_of[pid] = ordered
    order = []
    visited = set()
    def visit(pid):
        if pid in visited:
            return
        visited.add(pid)
        order.append(pid)
        for c in children_of.get(pid, []):
            visit(c)
    roots = [p for p in rects if parent_of[p] is None]
    if not roots:
        roots = [root_rect] if root_rect in rects else list(rects.keys())
    for r in roots:
        visit(r)
    # 兜底：异常结构里漏掉的节点追加到末尾
    for p in rects:
        if p not in visited:
            order.append(p)
    return order

def compose_paintings(bundle_name, output_dir):
    """将基础 bundle 的所有 _tex 部件按 RectTransform 布局合成完整立绘。
    参数:
        bundle_name: 基础 bundle 名（如 aerbien_2）
        output_dir:  输出目录（样本测试请指向 FIXTEST，避免覆盖正式结果）
    返回: 成功 True / 失败 False
    """
    path = os.path.join(PAINTING_DIR, bundle_name)
    if not os.path.exists(path):
        print(f'Bundle {bundle_name} not found')
        return False

    try:
        env = UnityPy.load(path)
    except Exception as e:
        print(f'Failed to load {bundle_name}: {e}')
        return False

    rects = {}
    path_to_name = {}
    root_rect = None

    for obj in env.objects:
        if obj.type.name == 'RectTransform':
            data = obj.read()
            rects[obj.path_id] = data
            go_name = 'Unknown'
            if getattr(data, 'm_GameObject', None):
                try:
                    go = data.m_GameObject.read()
                    go_name = go.m_Name
                except Exception:
                    pass
            path_to_name[obj.path_id] = go_name
            if go_name == bundle_name:
                root_rect = data

    if not root_rect:
        for r in rects.values():
            parent_ptr = getattr(r, 'm_Father', None)
            if not parent_ptr or parent_ptr.path_id == 0:
                root_rect = r
                break
        if not root_rect and rects:
            root_rect = list(rects.values())[0]

    if not root_rect:
        print('No Root RectTransform found!')
        return False

    # 递归计算每个 RectTransform 在画布中的「尺寸」与「左下角原点(origin, Y 向上)」
    sizes = {}
    origins = {}
    pivot_positions = {}

    def get_parent_id(r):
        f = getattr(r, 'm_Father', None)
        return f.path_id if f else None

    def compute_size_and_origin(pid):
        if pid in origins:
            return
        r = rects[pid]
        parent_id = get_parent_id(r)

        if parent_id is None or parent_id not in rects:
            sizes[pid] = (r.m_SizeDelta.x, r.m_SizeDelta.y)
            origins[pid] = (0.0, 0.0)
            pivot_positions[pid] = (r.m_Pivot.x * sizes[pid][0], r.m_Pivot.y * sizes[pid][1])
            return

        compute_size_and_origin(parent_id)

        parent_size = sizes[parent_id]
        parent_origin = origins[parent_id]

        amin = r.m_AnchorMin
        amax = r.m_AnchorMax
        s_delta = r.m_SizeDelta

        w = (amax.x - amin.x) * parent_size[0] + s_delta.x
        h = (amax.y - amin.y) * parent_size[1] + s_delta.y
        sizes[pid] = (w, h)

        pos = r.m_AnchoredPosition
        piv = r.m_Pivot

        # ALPA 算法：先算 pivot 在画布中的位置，再减去 pivot*size 得到左下角原点
        pp_x = (amax.x - amin.x) * parent_size[0] * piv.x + amin.x * parent_size[0] + parent_origin[0] + pos.x
        pp_y = (amax.y - amin.y) * parent_size[1] * piv.y + amin.y * parent_size[1] + parent_origin[1] + pos.y
        pivot_positions[pid] = (pp_x, pp_y)

        orig_x = pp_x - piv.x * w
        orig_y = pp_y - piv.y * h
        origins[pid] = (orig_x, orig_y)

    for pid in rects:
        compute_size_and_origin(pid)

    components = []
    for pid, r in rects.items():
        name = path_to_name[pid]
        # 跳过已知容器/无意义 UI 节点（root(bundle_name) 背负主立绘，不能跳过）
        if name in ['Touch', 'layers', 'Unknown', 'frameContain']:
            continue

        tex_path = find_tex_path(bundle_name, name)
        if tex_path:
            components.append({
                'pid': pid,
                'name': name,
                'origin': origins[pid],
                'size': sizes[pid],
                'tex_path': tex_path
            })

    canvas_w = int(root_rect.m_SizeDelta.x)
    canvas_h = int(root_rect.m_SizeDelta.y)
    print(f'Canvas size: {canvas_w}x{canvas_h}, components: {len(components)}')

    canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))

    # 按 Unity 层级兄弟顺序排定绘制次序（前者在下、后者在上）：
    #   - 父节点先绘制，子节点后绘制（子节点覆盖在父节点之上）
    #   - 同层兄弟按 m_Children 顺序（后者覆盖前者）
    # 这样背景(bj)自然落在人物(rw)之下、父(主立绘)在子(部件)之下，
    # 无需任何"面积排序"或"跳过 bj"之类的启发式，避免了蕨叶盖人/马被误删等问题。
    draw_order = build_draw_order(rects, path_to_name, root_rect)
    order_idx = {pid: i for i, pid in enumerate(draw_order)}
    components.sort(key=lambda c: order_idx.get(c['pid'], len(order_idx)))

    for c in components:
        comp_img = synthesize_tex_bundle(c['tex_path'])
        if not comp_img:
            continue

        # 按内容跳过「光效/圣光/泛光」层：mesh 原图几乎全白半透明、无彩色内容
        # 典型例子：aerbien_3_shophx_tex（385x417，100% 像素 RGB=255,255,255）
        # 这种层不是立绘本体，贴上去会把那一块区域洗白
        # 判定：可见像素(α>30)中 ≥ 80% 接近纯白（RGB 通道均 > 240）
        if _is_lighting_overlay(comp_img):
            print(f'  [skip lighting] {c["name"]}: mesh={comp_img.size} mostly pure-white → 光效层，跳过')
            continue

        # 按长宽比缩放（不拉伸）：用 min(rect/mesh) 比例
        # - 主图（mesh 长宽比 ≈ rect）：缩放前后尺寸一致，正常铺满
        # - 小贴纸（mesh << rect）：等比缩小到自然大小，不会被强行放大成大白块
        # 这样所有图层都保留，靠 bbox 裁剪收边
        mesh_w, mesh_h = comp_img.size
        rect_w, rect_h = c['size'][0], c['size'][1]
        if mesh_w > 0 and mesh_h > 0:
            ratio = min(rect_w / mesh_w, rect_h / mesh_h)
            new_w = max(1, int(round(mesh_w * ratio)))
            new_h = max(1, int(round(mesh_h * ratio)))
            if (new_w, new_h) != comp_img.size:
                comp_img = comp_img.resize((new_w, new_h), Image.LANCZOS)

        # 粘贴坐标转换为 PIL（Y 向下）：origin 为画布左下角、Y 向上
        px = int(round(c['origin'][0]))
        py = int(round(canvas_h - c['origin'][1] - comp_img.height))
        canvas.paste(comp_img, (px, py), comp_img)

    # 裁剪到不透明内容包围盒（去除大片透明边缘）
    bbox = canvas.getbbox()
    if bbox and bbox != (0, 0, canvas.width, canvas.height):
        canvas = canvas.crop(bbox)
        print(f'  cropped to content bbox: {canvas.size}')

    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, bundle_name + '.png')
    canvas.save(out_file)
    print(f'Composed painting saved to {out_file}')
    return True


if __name__ == '__main__':
    import sys
    targets = sys.argv[1:] or ['aerbien_2', 'adiliao_2', 'aerbien_3']
    out = r"D:\Azur Lane Assets\Output\Paintings_Synthesized_FIXTEST"
    for t in targets:
        compose_paintings(t, out)
    print("DONE ->", out)
