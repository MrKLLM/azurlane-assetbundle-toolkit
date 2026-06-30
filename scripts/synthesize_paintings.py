# -*- coding: utf-8 -*-
import os
import UnityPy
from PIL import Image
from UnityPy.helpers.MeshHelper import MeshHandler
from UnityPy.export.Texture2DConverter import get_image_from_texture2d

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
