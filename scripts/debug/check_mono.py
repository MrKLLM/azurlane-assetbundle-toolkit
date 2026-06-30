#!/usr/bin/env python3
"""
Check if the SkeletonData MonoBehaviour contains readable skeleton data.
Also try to understand the spine-unity binary format.
"""
import UnityPy
import struct
import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\aerbien_4_res"

env = UnityPy.load(BUNDLE)

print("=== All objects ===")
for obj in env.objects:
    data = obj.read()
    name = getattr(data, "m_Name", "N/A")
    print(f"  {obj.type.name}: {name} (path_id={obj.path_id})")

print("\n=== SkeletonData MonoBehaviour ===")
for obj in env.objects:
    data = obj.read()
    if obj.type.name == "MonoBehaviour" and "SkeletonData" in getattr(data, "m_Name", ""):
        print(f"  Name: {data.m_Name}")
        # Try to read raw data
        obj.reset()
        raw = obj.get_raw_data()
        print(f"  Raw size: {len(raw)} bytes")
        print(f"  First 100 hex: {raw[:100].hex()}")
        
        # Check if there's JSON in the data
        json_idx = raw.find(b'{')
        if json_idx >= 0:
            print(f"  JSON found at offset {json_idx}")
            # Try to parse JSON
            json_data = raw[json_idx:]
            # Find matching closing brace
            depth = 0
            end = 0
            for i, b in enumerate(json_data):
                if b == 0x7B: depth += 1
                elif b == 0x7D: depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            if end > 0:
                json_str = json_data[:end].decode('utf-8', errors='replace')
                try:
                    j = json.loads(json_str)
                    print(f"  JSON keys: {list(j.keys())}")
                    if 'bones' in j:
                        print(f"  Bones: {len(j['bones'])}")
                    if 'slots' in j:
                        print(f"  Slots: {len(j['slots'])}")
                    if 'animations' in j:
                        print(f"  Animations: {list(j['animations'].keys())[:5]}")
                except Exception as e:
                    print(f"  JSON parse error: {e}")
        
        # Check for skeletonJSON PPtr reference
        if hasattr(data, 'skeletonJSON'):
            print(f"  skeletonJSON PPtr: {data.skeletonJSON}")

print("\n=== Looking for JSON skeleton in all objects ===")
for obj in env.objects:
    data = obj.read()
    if obj.type.name == "TextAsset":
        name = data.m_Name
        if not name.endswith('.skel') and not name.endswith('.atlas'):
            # Check if it's JSON
            script = data.m_Script
            if isinstance(script, str) and script.strip().startswith('{'):
                print(f"  Found JSON TextAsset: {name}")
                print(f"  First 200 chars: {script[:200]}")

# Also check the main bundle
print("\n=== Main bundle check ===")
MAIN_BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\aerbien_4"
try:
    env2 = UnityPy.load(MAIN_BUNDLE)
    for obj in env2.objects:
        data = obj.read()
        if obj.type.name == "MonoBehaviour":
            name = getattr(data, "m_Name", "")
            if "SkeletonData" in name or "skeletonData" in name.lower():
                print(f"  Found: {name}")
                if hasattr(data, 'skeletonJSON'):
                    print(f"  skeletonJSON: {data.skeletonJSON}")
except Exception as e:
    print(f"  Error: {e}")
