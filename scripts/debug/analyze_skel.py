#!/usr/bin/env python3
"""
Deep analysis of spine-unity binary format.
Try to parse the header and understand the structure.
"""
import struct
import UnityPy
import os

def analyze_skel(raw_bytes, label):
    print(f"\n=== {label} ({len(raw_bytes)} bytes) ===")
    
    # Byte 0: 0x1C (28) - this is consistent
    print(f"Byte 0: 0x{raw_bytes[0]:02x} (should be 0x1C)")
    
    # Bytes 1-32: appears to be a hash
    hash_bytes = raw_bytes[1:33]
    hash_ascii = hash_bytes.decode("ascii", errors="replace")
    print(f"Hash (bytes 1-32): {hash_ascii}")
    
    # Byte 33 onwards: version + data
    # Let's find the version string
    # The version format is: X.Y.Z (e.g., 3.8.99)
    # Look for pattern like "3." or "4."
    for i in range(33, min(100, len(raw_bytes))):
        if raw_bytes[i:i+2] == b"3." or raw_bytes[i:i+2] == b"4.":
            # Found version candidate
            version_end = raw_bytes.find(b"\x00", i)
            if version_end < 0:
                version_end = i + 20
            version_raw = raw_bytes[i:version_end]
            # Filter to printable chars
            version = "".join(chr(b) if 32 <= b < 127 else "" for b in version_raw)
            print(f"Version at offset {i}: '{version}'")
            break
    
    # Look for the actual data start
    # After the header, there should be serialized data
    # Let's try to find patterns
    print(f"Bytes 33-50 hex: {raw_bytes[33:50].hex()}")
    print(f"Bytes 33-50 ascii: {''.join(chr(b) if 32 <= b < 127 else '.' for b in raw_bytes[33:50])}")
    
    # Check for common spine data patterns
    # Spine skeleton starts with: hash, width, height, fps, images_path, audio_path
    # Try reading as big-endian and little-endian
    
    # Let's look for float values that could be width/height
    # (common sizes: 100-4096)
    for offset in [33, 40, 50, 60, 70, 80]:
        if offset + 8 <= len(raw_bytes):
            try:
                f_le = struct.unpack_from("<f", raw_bytes, offset)[0]
                f_be = struct.unpack_from(">f", raw_bytes, offset)[0]
                if 10 < f_le < 10000:
                    print(f"  Float LE at {offset}: {f_le}")
                if 10 < f_be < 10000:
                    print(f"  Float BE at {offset}: {f_be}")
            except:
                pass
    
    # Try reading the whole thing as little-endian binary Spine format
    # Spine binary format (after 0x1C + version):
    # - hash: 16 bytes
    # - width: float
    # - height: float
    # - fps: float
    # - images path: string (null-terminated)
    # - audio path: string (null-terminated)
    # - bones count: int
    # ...
    
    # Find version string end
    ver_end = 43  # approximate
    for i in range(33, min(200, len(raw_bytes))):
        if raw_bytes[i:i+2] in [b"3.", b"4."]:
            null_pos = raw_bytes.find(b"\x00", i)
            if null_pos > 0:
                ver_end = null_pos + 1
                break
    
    data = raw_bytes[ver_end:]
    print(f"Data after header (offset {ver_end}): {len(data)} bytes")
    
    # Try to read as Spine binary format
    # The hash should be 16 bytes
    if len(data) >= 16:
        hash_data = data[:16]
        print(f"Hash data: {hash_data.hex()}")
        
        # Width/height as float32 LE
        if len(data) >= 24:
            w, h = struct.unpack_from("<ff", data, 16)
            print(f"Width/Height candidates: {w:.1f} x {h:.1f}")
            
        # Try reading bone count
        if len(data) >= 28:
            bone_count = struct.unpack_from("<i", data, 24)[0]
            print(f"Bone count candidate: {bone_count}")

# Load and analyze a few bundles
bundles = [
    (r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\aerbien_4_res", "aerbien_4"),
    (r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\lingbo_res", "lingbo"),
    (r"D:\Azur Lane Assets\files\AssetBundles\spineitem\yxt_dashafa_skeletondata", "yxt_dashafa"),
]

for bundle_path, label in bundles:
    if not os.path.exists(bundle_path):
        print(f"\nSkipping {label}: file not found")
        continue
    env = UnityPy.load(bundle_path)
    for obj in env.objects:
        data = obj.read()
        if obj.type.name == "TextAsset" and data.m_Name.endswith(".skel"):
            skel = data.m_Script
            if isinstance(skel, str):
                raw = skel.encode("latin-1", errors="replace")
            else:
                raw = skel
            analyze_skel(raw, f"{label}/{data.m_Name}")
