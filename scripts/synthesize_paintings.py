#!/usr/bin/env python3
"""
synthesize_paintings.py — 从 _tex AssetBundle 正确提取立绘

算法来源：ALPA (AzurLanePaintingAnalysis-Kt) 的 rebuildPainting 函数
1. 从 _tex bundle 加载 Texture2D + 独立 Mesh 对象
2. 解析 Mesh 顶点位置（像素坐标）和 UV 坐标（[0,1]）
3. 按每 4 个顶点一个四边形，用 UV 从纹理裁剪矩形块
4. 按位置粘贴到输出画布
"""

import os
import sys
import struct
import time
from multiprocessing import Pool, cpu_count

try:
    from PIL import Image
except ImportError:
    print("[ERROR] 需要安装 Pillow: pip install Pillow")
    sys.exit(1)

try:
    import UnityPy
except ImportError:
    print("[ERROR] 需要安装 UnityPy: pip install UnityPy")
    sys.exit(1)

PAINTING_DIR = r"D:\Azur Lane Assets\files\AssetBundles\painting"
SYNTH_OUTPUT = r"D:\Azur Lane Assets\Output\Paintings_Synthesized"
ERROR_LOG = r"D:\Azur Lane Assets\ERRORS.log"


def rebuild_painting_from_bundle(bundle_path):
    """从单个 _tex bundle 重建立绘"""
    try:
        env = UnityPy.load(bundle_path)
    except Exception:
        return None

    texture_img = None
    mesh_data = None

    for obj in env.objects:
        if obj.type.name == "Texture2D":
            data = obj.read()
            texture_img = data.image
        elif obj.type.name == "Mesh":
            data = obj.read()
            if data.m_VertexData.m_VertexCount > 10:
                mesh_data = data

    # If no mesh, just return the texture directly (simple painting)
    if not texture_img:
        return None
    if not mesh_data:
        return texture_img

    # Parse vertex data
    vd = mesh_data.m_VertexData
    raw = vd.m_DataSize
    n = vd.m_VertexCount
    stride = len(raw) // n if n > 0 else 0

    if stride == 0 or stride % 4 != 0:
        return None

    floats_per_vert = stride // 4
    if floats_per_vert < 5:
        return None

    # Parse positions and UVs
    positions = []
    uvs = []
    for i in range(n):
        off = i * stride
        if off + stride <= len(raw):
            vals = struct.unpack_from(f"<{floats_per_vert}f", raw, off)
            positions.append((vals[0], vals[1]))
            uvs.append((vals[3], vals[4]))

    # Get output size from LocalAABB
    aabb = mesh_data.m_LocalAABB
    out_w = int(aabb.m_Center.x + aabb.m_Extent.x) + 1
    out_h = int(aabb.m_Center.y + aabb.m_Extent.y) + 1

    if out_w <= 0 or out_h <= 0 or out_w > 8192 or out_h > 8192:
        return None

    tex_w, tex_h = texture_img.size

    # Use numpy for fast rendering
    import numpy as np
    tex_arr = np.array(texture_img)  # (H, W, 4) RGBA
    out_arr = np.zeros((out_h, out_w, 4), dtype=np.uint8)

    # ALPA algorithm: step 4 on vertices
    for i in range(0, n - 3, 4):
        v1_u, v1_v = uvs[i]
        v2_u, v2_v = uvs[i + 2]
        px = int(positions[i][0])
        py = int(positions[i][1])

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

        # Source region in texture
        src = tex_arr[v1y:v2y, v1x:v2x]

        # Destination region in output
        dst_y1 = max(0, py)
        dst_y2 = min(out_h, py + block_h)
        dst_x1 = max(0, px)
        dst_x2 = min(out_w, px + block_w)

        # Source region adjusted for clipping
        src_y1 = dst_y1 - py
        src_y2 = src_y1 + (dst_y2 - dst_y1)
        src_x1 = dst_x1 - px
        src_x2 = src_x1 + (dst_x2 - dst_x1)

        if dst_y2 > dst_y1 and dst_x2 > dst_x1:
            out_arr[dst_y1:dst_y2, dst_x1:dst_x2] = src[src_y1:src_y2, src_x1:src_x2]

    return Image.fromarray(out_arr)


def process_bundle(args):
    """处理单个 _tex bundle（子进程）"""
    tex_name, output_dir = args
    base_name = tex_name[:-4]  # remove "_tex"
    output_path = os.path.join(output_dir, f"{base_name}.png")

    if os.path.exists(output_path):
        return ("skip", base_name)

    bundle_path = os.path.join(PAINTING_DIR, tex_name)
    img = rebuild_painting_from_bundle(bundle_path)

    if img is None:
        return ("fail", base_name, "rebuild failed")

    try:
        img.save(output_path, "PNG")
        return ("ok", base_name)
    except Exception as e:
        return ("fail", base_name, str(e)[:200])


def log_error(name, error):
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"[SYNTHESIZE] {name}: {error}\n")


def main():
    print("[*] 立绘合成（Mesh UV 重建算法）")
    print(f"[*] 源: {PAINTING_DIR}")
    print(f"[*] 输出: {SYNTH_OUTPUT}")

    os.makedirs(SYNTH_OUTPUT, exist_ok=True)

    all_files = os.listdir(PAINTING_DIR)
    tex_bundles = [f for f in all_files if f.endswith("_tex")
                   and os.path.isfile(os.path.join(PAINTING_DIR, f))]
    print(f"[+] {len(tex_bundles)} 个 _tex bundle")

    tasks = [(name, SYNTH_OUTPUT) for name in tex_bundles]
    workers = min(cpu_count(), 8)
    print(f"[+] {workers} 进程")

    start_time = time.time()
    ok = fail = skip = 0

    with Pool(workers) as pool:
        for result in pool.imap_unordered(process_bundle, tasks):
            if result[0] == "ok":
                ok += 1
            elif result[0] == "skip":
                skip += 1
            else:
                fail += 1
                log_error(result[1], result[2])

            done = ok + fail + skip
            if done % 200 == 0:
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                print(f"    [{done}/{len(tex_bundles)}] ok:{ok} fail:{fail} skip:{skip} [{rate:.1f}/s]")

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"[+] 完成! ok:{ok} fail:{fail} skip:{skip}")
    print(f"    耗时: {elapsed:.1f}s ({(ok+fail+skip)/elapsed:.1f}/s)")

    if fail > 0:
        print(f"[!] 详情: {ERROR_LOG}")


if __name__ == "__main__":
    main()
