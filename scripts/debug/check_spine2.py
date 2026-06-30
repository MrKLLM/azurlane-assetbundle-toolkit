#!/usr/bin/env python3
"""Check spineitem bundle format and look for JSON skeleton data"""
import UnityPy
import json
import os

SPINE_DIR = r"D:\Azur Lane Assets\files\AssetBundles\spinepainting"
SPINE_ITEM_DIR = r"D:\Azur Lane Assets\files\AssetBundles\spineitem"

# Check a spineitem file
print("=== spineitem ===")
for fname in os.listdir(SPINE_ITEM_DIR)[:3]:
    fpath = os.path.join(SPINE_ITEM_DIR, fname)
    print(f"\n--- {fname} ({os.path.getsize(fpath) / 1024:.0f} KB) ---")
    env = UnityPy.load(fpath)
    for obj in env.objects:
        data = obj.read()
        tname = obj.type.name
        if tname == "TextAsset":
            name = data.m_Name
            script = data.m_Script
            if isinstance(script, str):
                raw = script.encode("latin-1", errors="replace")
            else:
                raw = script
            print(f"  TextAsset: {name} ({len(raw)} bytes)")
            # Try to find JSON
            idx = raw.find(b"{")
            if idx >= 0:
                json_part = raw[idx:]
                depth = 0
                end = 0
                for i, b in enumerate(json_part):
                    if b == 0x7B:  # {
                        depth += 1
                    elif b == 0x7D:  # }
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                if end > 0:
                    json_text = json_part[:end].decode("utf-8", errors="replace")
                    try:
                        j = json.loads(json_text)
                        print(f"    JSON keys: {list(j.keys())}")
                        if "skeleton" in j:
                            print(f"    skeleton: {j['skeleton']}")
                        if "bones" in j:
                            print(f"    bones: {len(j['bones'])}")
                        if "slots" in j:
                            print(f"    slots: {len(j['slots'])}")
                        if "animations" in j:
                            anims = j["animations"]
                            print(f"    animations: {list(anims.keys())[:5]}...")
                    except Exception as e:
                        print(f"    JSON parse error: {e}")
            else:
                print(f"    No JSON found, first 20 hex: {raw[:20].hex()}")
        elif tname == "Texture2D":
            print(f"  Texture2D: {data.m_Name} {data.m_Width}x{data.m_Height}")

# Check a few spinepainting _res bundles for JSON skeletons
print("\n\n=== spinepainting _res bundles ===")
res_files = [f for f in os.listdir(SPINE_DIR) if f.endswith("_res")]
for fname in res_files[:5]:
    fpath = os.path.join(SPINE_DIR, fname)
    print(f"\n--- {fname} ---")
    env = UnityPy.load(fpath)
    for obj in env.objects:
        data = obj.read()
        if obj.type.name == "TextAsset" and data.m_Name.endswith(".skel"):
            script = data.m_Script
            if isinstance(script, str):
                raw = script.encode("latin-1", errors="replace")
            else:
                raw = script
            # Check if the data is actually JSON (not binary)
            first_brace = raw.find(b"{")
            if first_brace >= 0 and first_brace < 100:
                # Might be JSON starting near the beginning
                json_part = raw[first_brace:]
                try:
                    j = json.loads(json_part)
                    print(f"  JSON skeleton! Keys: {list(j.keys())}")
                except:
                    print(f"  Not JSON (offset {first_brace})")
            else:
                print(f"  Binary skel ({len(raw)} bytes, first: 0x{raw[0]:02x})")
