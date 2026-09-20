#!/usr/bin/env python3
"""
extract_paintingface.py — 批量提取 paintingface bundles 中的表情贴图

每个 paintingface bundle 包含多个编号的 Texture2D（1, 2, 3...），
对应不同表情变体。提取后输出为 PNG。
"""

import os
import sys
import time
from multiprocessing import Pool, cpu_count

try:
    from PIL import Image
except ImportError:
    print("[ERROR] 需要安装 Pillow: pip install Pillow")
    sys.exit(1)

try:
    import UnityPy
    from UnityPy import config
    config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
except ImportError:
    print("[ERROR] 需要安装 UnityPy: pip install UnityPy")
    sys.exit(1)

from UnityPy.export.Texture2DConverter import get_image_from_texture2d

FACE_DIR = r"D:\Azur Lane Assets\files\AssetBundles\paintingface"
OUTPUT_DIR = r"D:\Azur Lane Assets\Output\Paintingface"
ERROR_LOG = r"D:\Azur Lane Assets\ERRORS.log"


def extract_face_bundle(args):
    """提取单个 paintingface bundle 中的所有表情贴图"""
    bundle_name, output_dir = args
    bundle_path = os.path.join(FACE_DIR, bundle_name)

    try:
        env = UnityPy.load(bundle_path)
    except Exception as e:
        return ("fail", bundle_name, str(e)[:200])

    extracted = 0
    for obj in env.objects:
        if obj.type.name != "Texture2D":
            continue
        try:
            data = obj.read()
            img = get_image_from_texture2d(data, flip=True)
            if img is None:
                continue
            out_path = os.path.join(output_dir, f"{bundle_name}_{data.m_Name}.png")
            if os.path.exists(out_path):
                extracted += 1
                continue
            img.save(out_path, "PNG")
            extracted += 1
        except Exception as e:
            return ("fail", bundle_name, f"texture {obj.path_id}: {str(e)[:200]}")

    if extracted == 0:
        return ("fail", bundle_name, "no textures found")
    return ("ok", bundle_name, extracted)


def log_error(name, error):
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"[PAINTINGFACE] {name}: {error}\n")


def main():
    print("[*] Paintingface 表情贴图提取")
    print(f"[*] 源: {FACE_DIR}")
    print(f"[*] 输出: {OUTPUT_DIR}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_files = os.listdir(FACE_DIR)
    bundles = [f for f in all_files if os.path.isfile(os.path.join(FACE_DIR, f))]
    if len(sys.argv) > 1:
        only = set(sys.argv[1:])
        bundles = [b for b in bundles if b in only]
    print(f"[+] {len(bundles)} 个 paintingface bundle")

    tasks = [(name, OUTPUT_DIR) for name in bundles]
    workers = min(cpu_count(), 8)
    print(f"[+] {workers} 进程")

    start_time = time.time()
    ok = fail = 0
    total_textures = 0

    with Pool(workers) as pool:
        for result in pool.imap_unordered(extract_face_bundle, tasks):
            if result[0] == "ok":
                ok += 1
                total_textures += result[2]
            else:
                fail += 1
                log_error(result[1], result[2])

            done = ok + fail
            if done % 200 == 0:
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                print(f"    [{done}/{len(bundles)}] ok:{ok} fail:{fail} [{rate:.1f}/s]")

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"[+] 完成! ok:{ok} fail:{fail}")
    print(f"    提取表情贴图: {total_textures} 张")
    print(f"    耗时: {elapsed:.1f}s ({(ok+fail)/elapsed:.1f}/s)")

    if fail > 0:
        print(f"[!] 详情: {ERROR_LOG}")


if __name__ == "__main__":
    main()
