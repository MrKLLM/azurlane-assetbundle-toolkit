# -*- coding: utf-8 -*-
import os
import UnityPy
from PIL import Image
from UnityPy.helpers.MeshHelper import MeshHandler
from UnityPy.export.Texture2DConverter import get_image_from_texture2d

PAINTING_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '/mnt/local/Azur_Lane_Assets/files/AssetBundles/painting'
if not os.path.exists(PAINTING_DIR):
    PAINTING_DIR = '/mnt/local/Azur_Lane_Assets/files/AssetBundles/painting'

def find_tex_path(base_bundle, go_name):
    candidates = [
        go_name + '_tex',
        f'{base_bundle}_{go_name}_tex',
        f'{base_bundle}_{go_name.replace(_, )}_tex',
        f'{base_bundle.replace(_, )}_{go_name.replace(_, )}_tex'
    ]
    for cand in candidates:
        p = os.path.join(PAINTING_DIR, cand)
        if os.path.exists(p):
            return p
            
    # Try lowercase / uppercase permutations
    candidates2 = [
        go_name.lower() + '_tex',
        f'{base_bundle}_{go_name.lower()}_tex',
        f'{base_bundle}_{go_name.replace(_, ).lower()}_tex',
        f'{base_bundle.lower()}_{go_name.replace(_, ).lower()}_tex'
    ]
    for cand in candidates2:
        p = os.path.join(PAINTING_DIR, cand)
        if os.path.exists(p):
            return p
    return None

def synthesize_tex_bundle(bundle_path):
    try:
        env = UnityPy.load(bundle_path)
    except Exception as e:
        print(f'Failed to load {bundle_path}: {e}')
        return None

    texture_img = None
    mesh_obj = None

    for obj in env.objects:
        if obj.type.name == 'Texture2D':
            data = obj.read()
            texture_img = get_image_from_texture2d(data, flip=False)
        elif obj.type.name == 'Mesh':
            data = obj.read()
            if data.m_VertexData and data.m_VertexData.m_VertexCount > 10:
                mesh_obj = data

    if not texture_img:
        return None
    if not mesh_obj:
        return texture_img

    try:
        handler = MeshHandler(mesh_obj)
        handler.process()
    except Exception as e:
        print(f'Mesh processing failed: {e}')
        return texture_img

    positions = handler.m_Vertices
    uvs = handler.m_UV0

    if not positions or not uvs or len(positions) != len(uvs):
        return texture_img

    n = len(positions)
    if n < 4:
        return texture_img

    aabb = mesh_obj.m_LocalAABB
    # Bug #1 Fix: Use 2 * extent, offset vertices by min_x/min_y
    min_x = aabb.m_Center.x - aabb.m_Extent.x
    min_y = aabb.m_Center.y - aabb.m_Extent.y
    out_w = int(2 * aabb.m_Extent.x) + 1
    out_h = int(2 * aabb.m_Extent.y) + 1

    if out_w <= 0 or out_h <= 0 or out_w > 8192 or out_h > 8192:
        return texture_img

    tex_w, tex_h = texture_img.size

    import numpy as np
    tex_arr = np.array(texture_img)
    out_arr = np.zeros((out_h, out_w, 4), dtype=np.uint8)

    for i in range(n - 4, -1, -4):
        v1_u, v1_v = uvs[i]
        v2_u, v2_v = uvs[i + 2]
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

    return Image.fromarray(out_arr).transpose(Image.FLIP_TOP_BOTTOM)

def compose_paintings(bundle_name, output_dir):
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
                except:
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

    # Bug #2 & Bug #4: Handle full recursive origin position conversion (Unity Y↑ -> PIL Y↓)
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
        
        # ALPA algorithm for child pivot position:
        pp_x = (amax.x - amin.x) * parent_size[0] * piv.x + amin.x * parent_size[0] + parent_origin[0] + pos.x
        pp_y = (amax.y - amin.y) * parent_size[1] * piv.y + amin.y * parent_size[1] + parent_origin[1] + pos.y
        pivot_positions[pid] = (pp_x, pp_y)
        
        # getOrigin() = pivotPosition - pivot * size
        orig_x = pp_x - piv.x * w
        orig_y = pp_y - piv.y * h
        origins[pid] = (orig_x, orig_y)

    for pid in rects:
        compute_size_and_origin(pid)

    components = []
    for pid, r in rects.items():
        name = path_to_name[pid]
        if name in ['Touch', 'layers', bundle_name, 'Unknown', 'frameContain', 'face']:
            continue
        if 'shadow' in name.lower():
            continue
            
        tex_path = find_tex_path(bundle_name, name)
        if tex_path:
            components.append({
                'name': name,
                'origin': origins[pid],
                'size': sizes[pid],
                'tex_path': tex_path
            })

    canvas_w = int(root_rect.m_SizeDelta.x)
    canvas_h = int(root_rect.m_SizeDelta.y)
    print(f'Canvas size: {canvas_w}x{canvas_h}')

    canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))

    components.sort(key=lambda c: c['size'][0] * c['size'][1], reverse=True)

    for c in components:
        comp_img = synthesize_tex_bundle(c['tex_path'])
        if not comp_img:
            continue
        
        # Paste in PIL coordinate system (Y↓)
        px = int(round(c['origin'][0]))
        py = int(round(canvas_h - c['origin'][1] - comp_img.height))
        canvas.paste(comp_img, (px, py), comp_img)

    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, bundle_name + '.png')
    canvas.save(out_file)
    print(f'Composed painting saved to {out_file}')
    return True
