#!/usr/bin/env python3
"""
Check if skel files are standard Spine binary format.
Spine binary format starts with magic bytes: 0x1C 0xED (or just 0x1C for older versions)
"""
import UnityPy
import struct

BUNDLES = [
    (r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\aerbien_4_res", "aerbien_4"),
    (r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\lingbo_res", "lingbo"),
]

for bundle_path, label in BUNDLES:
    print(f"\n=== {label} ===")
    try:
        env = UnityPy.load(bundle_path)
    except Exception as e:
        print(f"  Failed to load: {e}")
        continue
    
    for obj in env.objects:
        data = obj.read()
        if obj.type.name == "TextAsset" and data.m_Name.endswith(".skel"):
            skel = data.m_Script
            if isinstance(skel, str):
                raw = skel.encode("latin-1", errors="replace")
            else:
                raw = skel
            print(f"  Size: {len(raw)} bytes")
            print(f"  First 4 bytes: {raw[:4].hex()}")
            
            # Standard Spine binary format header:
            # byte 0: 0x1C (signature)
            # byte 1: version (4 for Spine 3.x, 5 for Spine 4.x)
            # Then version string (null-terminated)
            if raw[0] == 0x1C:
                version_byte = raw[1]
                print(f"  Signature: 0x1C (Spine binary)")
                print(f"  Version byte: {version_byte}")
                
                # Find null terminator after version byte
                null_idx = raw.find(b'\x00', 2)
                if null_idx > 0:
                    version_str = raw[2:null_idx].decode('ascii', errors='replace')
                    print(f"  Version string: {version_str}")
                    
                    # After version string comes the skeleton data
                    data_start = null_idx + 1
                    print(f"  Data starts at offset: {data_start}")
                    print(f"  Data size: {len(raw) - data_start} bytes")
                    
                    # Try to read first few values (hash, width, height)
                    if len(raw) > data_start + 20:
                        # Read hash (16 bytes)
                        hash_bytes = raw[data_start:data_start+16]
                        print(f"  Hash: {hash_bytes.hex()}")
                        # Read float values (width, height, etc.)
                        floats = struct.unpack_from('<ff', raw, data_start+16)
                        print(f"  First floats: {floats}")
            else:
                print(f"  Unknown format, first byte: 0x{raw[0]:02x}")
