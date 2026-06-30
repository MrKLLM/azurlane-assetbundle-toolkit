#!/usr/bin/env python3
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open(r"D:\Azur Lane Assets\Output\Spine\spinepainting\aerbien_4\aerbien_4.json", "r", encoding="utf-8") as f:
    data = json.load(f)

bones = data.get("bones", [])
slots = data.get("slots", [])
null_bones = [i for i, b in enumerate(bones) if not b.get("name")]
null_slots = [i for i, s in enumerate(slots) if not s.get("name")]

print(f"Total bones: {len(bones)}")
print(f"Null bone names: {len(null_bones)}")
if null_bones:
    print(f"  Indices: {null_bones[:20]}")
    for i in null_bones[:3]:
        print(f"  [{i}]: {bones[i]}")

print(f"Total slots: {len(slots)}")
print(f"Null slot names: {len(null_slots)}")

print(f"\nFirst 3 bones:")
for i, b in enumerate(bones[:3]):
    print(f"  [{i}]: {b}")

print(f"\nFirst 3 slots:")
for i, s in enumerate(slots[:3]):
    print(f"  [{i}]: {s}")
