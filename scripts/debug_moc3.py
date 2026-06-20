#!/usr/bin/env python3
"""Investigate Live2D model structure and moc3 extraction issues"""

import os
import struct
import UnityPy

BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\live2d\lingbo"
OUTPUT_MOC3 = r"D:\Azur Lane Assets\Output\Live2D\lingbo\lingbo.moc3"

env = UnityPy.load(BUNDLE)

print("=" * 60)
print("1. Bundle Object Inventory")
print("=" * 60)

type_counts = {}
for obj in env.objects:
    t = obj.type.name
    type_counts[t] = type_counts.get(t, 0) + 1
for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c}")

print("\n" + "=" * 60)
print("2. MonoBehaviour with MOC3")
print("=" * 60)

for obj in env.objects:
    if obj.type.name != "MonoBehaviour":
        continue
    raw = obj.get_raw_data()
    moc3_pos = raw.find(b"MOC3")
    if moc3_pos >= 0:
        print(f"  Found MOC3 at raw_data offset {moc3_pos}")
        print(f"  Raw data size: {len(raw)} bytes")
        
        # Show bytes around MOC3
        start = max(0, moc3_pos - 20)
        end = min(len(raw), moc3_pos + 80)
        print(f"  Bytes [{start}:{end}] around MOC3:")
        for i in range(start, end, 16):
            hex_str = ' '.join(f'{b:02X}' for b in raw[i:min(i+16, end)])
            print(f"    {i:04X}: {hex_str}")
        
        # Try to find the end of moc3 data
        # MOC3 header: magic(4) + version(4) + ...
        # Check what comes after the moc3 data
        moc3_end_search_start = moc3_pos + 4
        # Look for common Unity patterns after moc3
        print(f"\n  MOC3 data starts at offset {moc3_pos}")
        print(f"  Remaining data after MOC3: {len(raw) - moc3_pos} bytes")
        
        # Check the moc3 version
        version_bytes = raw[moc3_pos+4:moc3_pos+8]
        version = struct.unpack('<I', version_bytes)[0]
        print(f"  MOC3 version: {version}")
        
        break

print("\n" + "=" * 60)
print("3. Texture2D objects")
print("=" * 60)

textures = []
for obj in env.objects:
    if obj.type.name != "Texture2D":
        continue
    data = obj.read()
    name = getattr(data, "m_Name", "unknown")
    width = getattr(data, "m_Width", 0)
    height = getattr(data, "m_Height", 0)
    fmt = getattr(data, "m_TextureFormat", "unknown")
    textures.append((name, width, height, fmt))
    print(f"  {name}: {width}x{height}, format={fmt}")

print(f"\n  Total textures: {len(textures)}")

print("\n" + "=" * 60)
print("4. Extracted moc3 file comparison")
print("=" * 60)

if os.path.isfile(OUTPUT_MOC3):
    extracted_size = os.path.getsize(OUTPUT_MOC3)
    print(f"  Extracted moc3 size: {extracted_size} bytes")
    with open(OUTPUT_MOC3, 'rb') as f:
        header = f.read(20)
    print(f"  First 20 bytes: {' '.join(f'{b:02X}' for b in header)}")
    moc3_magic = header[:4]
    print(f"  Magic: {moc3_magic}")
    if moc3_magic == b'MOC3':
        version = struct.unpack('<I', header[4:8])[0]
        print(f"  Version: {version}")
else:
    print("  Extracted moc3 file not found!")

print("\n" + "=" * 60)
print("5. TextAsset objects")
print("=" * 60)

for obj in env.objects:
    if obj.type.name != "TextAsset":
        continue
    data = obj.read()
    name = getattr(data, "m_Name", "unknown")
    script = getattr(data, "m_Script", b"")
    if isinstance(script, str):
        script = script.encode("utf-8")
    print(f"  {name}: {len(script)} bytes")
    if len(script) > 0:
        print(f"    First 20 bytes: {' '.join(f'{b:02X}' for b in script[:20])}")
        if script[:4] == b'MOC3':
            print(f"    *** This TextAsset contains MOC3 data! ***")

print("\n" + "=" * 60)
print("6. CubismMoc MonoBehaviour details")
print("=" * 60)

for obj in env.objects:
    if obj.type.name != "MonoBehaviour":
        continue
    try:
        data = obj.read()
        script_ref = getattr(data, "m_Script", None)
        if not script_ref:
            continue
        script_obj = script_ref.read()
        script_name = getattr(script_obj, "m_Name", "")
        if "Moc" in script_name or "Cubism" in script_name:
            print(f"  Script: {script_name}")
            print(f"  All attrs: {[a for a in dir(data) if not a.startswith('_') and not callable(getattr(data, a, None))]}")
            # Print all non-callable attribute values
            for attr in dir(data):
                if attr.startswith('_'):
                    continue
                try:
                    val = getattr(data, attr)
                    if callable(val):
                        continue
                    if isinstance(val, (list, tuple)):
                        print(f"    {attr}: list[{len(val)}]")
                    elif isinstance(val, bytes):
                        print(f"    {attr}: bytes[{len(val)}]")
                    elif isinstance(val, str):
                        print(f"    {attr}: '{val[:100]}'")
                    else:
                        print(f"    {attr}: {val}")
                except:
                    pass
    except:
        continue
