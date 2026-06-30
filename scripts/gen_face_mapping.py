#!/usr/bin/env python3
"""生成 paintingface_mapping.json"""
import os
import json
from collections import defaultdict

FACE_DIR = r"D:\Azur Lane Assets\files\AssetBundles\paintingface"
PAINT_DIR = r"D:\Azur Lane Assets\files\AssetBundles\painting"
OUTPUT = r"D:\Azur Lane Assets\paintingface_mapping.json"

face_files = sorted(os.listdir(FACE_DIR))
paint_files = set(os.listdir(PAINT_DIR))

mapping = {}
for name in face_files:
    face_path = os.path.join(FACE_DIR, name)
    if not os.path.isfile(face_path):
        continue

    has_tex = (name + "_tex") in paint_files
    has_base = name in paint_files

    mapping[name] = {
        "base_bundle": name if has_base else None,
        "tex_bundle": name + "_tex" if has_tex else None,
        "has_painting": has_base and has_tex,
    }

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(mapping, f, ensure_ascii=False, indent=2)

print(f"Generated {OUTPUT}")
print(f"Total: {len(mapping)} entries")
matched = sum(1 for v in mapping.values() if v["has_painting"])
print(f"Matched (has base+tex): {matched}")
print(f"Unmatched (face only): {len(mapping) - matched}")
