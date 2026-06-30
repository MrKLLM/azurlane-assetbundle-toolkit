#!/usr/bin/env python3
"""Batch convert all .skel files to .json using Node.js spine 3.8 runtime"""
import subprocess
import os
import sys

SPINE_DIR = r"D:\Azur Lane Assets\Output\Spine\spinepainting"
CONVERT_SCRIPT = r"D:\Azur Lane Assets\scripts\convert_skel.js"

# Find all .skel files
skel_files = []
for root, dirs, files in os.walk(SPINE_DIR):
    for f in files:
        if f.endswith(".skel"):
            skel_files.append(os.path.join(root, f))

print(f"Found {len(skel_files)} .skel files to convert")

success = 0
failed = 0

for i, skel_path in enumerate(skel_files):
    json_path = skel_path.replace(".skel", ".json")
    
    # Skip if JSON already exists
    if os.path.exists(json_path):
        success += 1
        continue
    
    try:
        result = subprocess.run(
            ["node", CONVERT_SCRIPT, skel_path, json_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            success += 1
        else:
            failed += 1
            print(f"  FAILED: {os.path.basename(skel_path)}: {result.stderr[:100]}")
    except Exception as e:
        failed += 1
        print(f"  ERROR: {os.path.basename(skel_path)}: {e}")
    
    if (i + 1) % 20 == 0:
        print(f"  [{i+1}/{len(skel_files)}] OK:{success} FAIL:{failed}")

print(f"\nDone! Success: {success}, Failed: {failed}")
