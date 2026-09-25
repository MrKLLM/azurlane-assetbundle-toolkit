"""
批量导出碧蓝航线音频资源 (CRIWARE .b → .wav)

.cue/.b 文件是 CRIWARE ACB 格式，需要改名为 .acb 才能被 vgmstream 识别。
"""

import os
import sys
import subprocess
import shutil
import time

# 配置
VGMSTREAM_CLI = r"C:\Users\KLLM\AppData\Local\vgmstream\vgmstream-cli.exe"
FFMPEG = r"C:\Users\KLLM\AppData\Local\ffmpeg\ffmpeg.exe"
INPUT_DIR = r"D:\Azur Lane Assets\files\AssetBundles\cue"
OUTPUT_DIR = r"D:\Azur Lane Assets\Output\Audio"
TEMP_DIR = r"D:\Azur Lane Assets\Output\_audio_temp"

# 分类前缀映射
CATEGORY_MAP = {
    "bgm-": "BGM",
    "bgm_": "BGM",
    "se-": "SE",
    "se_": "SE",
    "cv-": "CV",
    "cv_": "CV",
    "voice-": "CV",
    "voice_": "CV",
}


def get_category(filename):
    """根据文件名判断音频类别"""
    lower = filename.lower()
    for prefix, cat in CATEGORY_MAP.items():
        if lower.startswith(prefix):
            return cat
    return "Other"


def convert_b_to_wav(input_path, output_path, temp_dir):
    """将 .b 文件转换为 .wav"""
    # 复制为 .acb
    acb_path = os.path.join(temp_dir, os.path.basename(input_path) + ".acb")
    shutil.copy2(input_path, acb_path)

    try:
        # 用 vgmstream 解码
        result = subprocess.run(
            [VGMSTREAM_CLI, "-o", output_path, acb_path],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60
        )
        if result.returncode == 0 and os.path.exists(output_path):
            return True
        else:
            # 如果 vgmstream 失败，尝试 ffmpeg
            result2 = subprocess.run(
                [FFMPEG, "-y", "-i", acb_path, "-acodec", "pcm_s16le", "-ar", "44100", output_path],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60
            )
            if result2.returncode == 0 and os.path.exists(output_path):
                return True
            return False
    except Exception as e:
        print(f"  Error: {e}")
        return False
    finally:
        # 清理临时 .acb 文件
        if os.path.exists(acb_path):
            os.remove(acb_path)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    # 获取所有 .b 文件
    b_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.b')]
    print(f"Found {len(b_files)} audio files in cue/")

    # 按类别分组
    categories = {}
    for f in b_files:
        cat = get_category(f)
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f)

    print(f"Categories: {', '.join(f'{k}({len(v)})' for k, v in categories.items())}")

    # 创建类别目录
    for cat in categories:
        os.makedirs(os.path.join(OUTPUT_DIR, cat), exist_ok=True)

    # 转换
    success = 0
    failed = 0
    skipped = 0
    start_time = time.time()

    for i, fname in enumerate(b_files):
        cat = get_category(fname)
        out_name = os.path.splitext(fname)[0] + ".wav"
        out_path = os.path.join(OUTPUT_DIR, cat, out_name)

        # 跳过已存在的
        if os.path.exists(out_path):
            skipped += 1
            continue

        input_path = os.path.join(INPUT_DIR, fname)
        print(f"[{i+1}/{len(b_files)}] {fname} → {cat}/", end=" ")

        if convert_b_to_wav(input_path, out_path, TEMP_DIR):
            size_kb = os.path.getsize(out_path) / 1024
            print(f"OK ({size_kb:.0f} KB)")
            success += 1
        else:
            print("FAILED")
            failed += 1

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Done! Time: {elapsed:.0f}s")
    print(f"Success: {success}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")
    print(f"Output: {OUTPUT_DIR}")

    # 清理临时目录
    shutil.rmtree(TEMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
