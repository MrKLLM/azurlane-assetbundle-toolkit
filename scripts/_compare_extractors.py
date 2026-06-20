#!/usr/bin/env python3
"""
compare_extractors.py — 对比 UnityPy vs AssetStudio 提取质量
用 AssetStudio CLI 提取单个 painting bundle，与 UnityPy 输出对比
"""

import subprocess
import os
from PIL import Image

ASSETSTUDIO_CLI = r"D:\Azur Lane Assets\AssetStudioModGUI.net8.0\AssetStudio.CLI.exe"
PAINTING_DIR = r"D:\Azur Lane Assets\files\AssetBundles\painting"
TEST_OUTPUT = r"D:\Azur Lane Assets\Output\extractor_comparison"
os.makedirs(TEST_OUTPUT, exist_ok=True)

# Test bundle
TEST_BUNDLE = "lingbo_tex"
bundle_path = os.path.join(PAINTING_DIR, TEST_BUNDLE)

print(f"Testing: {TEST_BUNDLE}")
print(f"Bundle: {bundle_path}")

# Method 1: AssetStudio CLI
print(f"\n--- Method 1: AssetStudio CLI ---")
as_output = os.path.join(TEST_OUTPUT, "assetstudio")
os.makedirs(as_output, exist_ok=True)

try:
    result = subprocess.run(
        [ASSETSTUDIO_CLI, bundle_path, as_output,
         "--game", "Normal",
         "--types", "Texture2D",
         "--export_type", "Raw"],
        capture_output=True, text=True, timeout=60
    )
    print(f"  stdout: {result.stdout[:500]}")
    print(f"  stderr: {result.stderr[:500]}")
    
    # Check output
    for f in os.listdir(as_output):
        fp = os.path.join(as_output, f)
        if f.endswith('.png'):
            img = Image.open(fp)
            print(f"  Output: {f} ({img.size} {img.mode})")
        else:
            print(f"  Output: {f} ({os.path.getsize(fp)} bytes)")
except Exception as e:
    print(f"  Error: {e}")

# Method 2: UnityPy
print(f"\n--- Method 2: UnityPy ---")
import UnityPy
env = UnityPy.load(bundle_path)
for obj in env.objects:
    data = obj.read()
    if obj.type.name == "Texture2D":
        img = data.image
        out = os.path.join(TEST_OUTPUT, "unitypy.png")
        img.save(out, "PNG")
        print(f"  Output: unitypy.png ({img.size} {img.mode})")
        
        # Also try Sprite.image
        break

for obj in env.objects:
    data = obj.read()
    if obj.type.name == "Sprite":
        try:
            sp_img = data.image
            if sp_img:
                out = os.path.join(TEST_OUTPUT, "unitypy_sprite.png")
                sp_img.save(out, "PNG")
                print(f"  Sprite: unitypy_sprite.png ({sp_img.size} {sp_img.mode})")
        except Exception as e:
            print(f"  Sprite error: {e}")
        break

# Compare
print(f"\n--- Comparison ---")
for f in os.listdir(TEST_OUTPUT):
    fp = os.path.join(TEST_OUTPUT, f)
    if f.endswith('.png'):
        img = Image.open(fp)
        # Count non-transparent pixels
        if img.mode == 'RGBA':
            pixels = list(img.getdata())
            non_trans = sum(1 for p in pixels if p[3] > 0)
            pct = non_trans / len(pixels) * 100
            print(f"  {f}: {img.size}, {pct:.1f}% content")
        else:
            print(f"  {f}: {img.size} {img.mode}")
