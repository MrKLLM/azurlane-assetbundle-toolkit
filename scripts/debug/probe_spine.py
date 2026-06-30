#!/usr/bin/env python3
"""Probe Spine asset bundle structure"""
import UnityPy
import json
import os
import sys

BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\aerbien_4_res"

env = UnityPy.load(BUNDLE)

print("=== Objects in bundle ===")
for obj in env.objects:
    data = obj.read()
    name = getattr(data, "m_Name", "N/A")
    print(f"  {obj.type.name}: {name} (path_id={obj.path_id})")

print("\n=== TextAssets ===")
for obj in env.objects:
    data = obj.read()
    if obj.type.name == "TextAsset":
        name = data.m_Name
        script = data.m_Script
        if isinstance(script, str):
            raw = script.encode("utf-8", errors="replace")
        else:
            raw = script
        print(f"\n  {name}: {len(raw)} bytes")
        
        # Find JSON
        idx = raw.find(b"{")
        if idx >= 0:
            print(f"  JSON starts at offset {idx}")
            json_part = raw[idx:]
            try:
                j = json.loads(json_part)
                print(f"  Top-level keys: {list(j.keys())}")
                if "skeleton" in j:
                    print(f"  skeleton: {j['skeleton']}")
                if "bones" in j:
                    print(f"  bones count: {len(j['bones'])}")
                if "slots" in j:
                    print(f"  slots count: {len(j['slots'])}")
                if "skins" in j:
                    skins = j["skins"]
                    if isinstance(skins, dict):
                        print(f"  skins: {list(skins.keys())}")
                    elif isinstance(skins, list):
                        print(f"  skins count: {len(skins)}")
                if "animations" in j:
                    anims = j["animations"]
                    print(f"  animations: {list(anims.keys())}")
            except Exception as e:
                print(f"  JSON parse error: {e}")
                print(f"  First 200 of JSON: {json_part[:200]}")
        else:
            print(f"  No JSON found. First 100 hex: {raw[:100].hex()}")

print("\n=== Texture2D ===")
for obj in env.objects:
    data = obj.read()
    if obj.type.name == "Texture2D":
        print(f"  {data.m_Name}: {data.m_Width}x{data.m_Height}")

print("\n=== MonoBehaviour details ===")
for obj in env.objects:
    data = obj.read()
    if obj.type.name == "MonoBehaviour":
        name = getattr(data, "m_Name", "N/A")
        print(f"\n  {name}:")
        for k, v in data.__dict__.items():
            if k.startswith("_") or k == "object_reader":
                continue
            val_str = str(v)[:150]
            print(f"    {k} = {val_str}")

# Also check a main bundle (non-res)
print("\n\n=== Main bundle: aerbien_4 ===")
MAIN_BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\aerbien_4"
env2 = UnityPy.load(MAIN_BUNDLE)
mono_count = 0
for obj in env2.objects:
    if obj.type.name == "MonoBehaviour":
        data = obj.read()
        name = getattr(data, "m_Name", "N/A")
        mono_count += 1
        # Check for spine-related fields
        for k, v in data.__dict__.items():
            if k.startswith("_") or k == "object_reader":
                continue
            val_str = str(v)[:100]
            if "spine" in k.lower() or "skeleton" in k.lower() or "atlas" in k.lower() or "skeletonJSON" in k.lower():
                print(f"  {name}.{k} = {val_str}")
print(f"  Total MonoBehaviours: {mono_count}")

# Count all spinepainting files
SPINE_DIR = r"D:\Azur Lane Assets\files\AssetBundles\spinepainting"
files = os.listdir(SPINE_DIR)
res_files = [f for f in files if f.endswith("_res")]
main_files = [f for f in files if not f.endswith("_res")]
print(f"\n=== Summary ===")
print(f"Total files: {len(files)}")
print(f"Main bundles (non-res): {len(main_files)}")
print(f"Resource bundles (_res): {len(res_files)}")

# Check spineitem
SPINE_ITEM_DIR = r"D:\Azur Lane Assets\files\AssetBundles\spineitem"
if os.path.isdir(SPINE_ITEM_DIR):
    item_files = os.listdir(SPINE_ITEM_DIR)
    print(f"\n=== spineitem: {len(item_files)} files ===")
    for f in item_files[:5]:
        print(f"  {f} ({os.path.getsize(os.path.join(SPINE_ITEM_DIR, f)) / 1024:.0f} KB)")
