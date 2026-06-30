#!/usr/bin/env python3
"""
Try different spine binary header interpretations to find the correct one.
"""
import struct
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SKEL_PATH = r"D:\Azur Lane Assets\Output\Spine\spinepainting\aerbien_4\aerbien_4.skel"

with open(SKEL_PATH, "rb") as f:
    data = f.read()

print(f"File: {len(data)} bytes")

# Print first 128 bytes hex + ascii
for i in range(0, min(128, len(data)), 16):
    chunk = data[i:i+16]
    hex_str = chunk.hex()
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    print(f"  {i:04x}: {hex_str:<32s} {ascii_str}")

print("\n=== Interpretation 1: Standard spine format (varint hash + varint version) ===")
pos = 1  # skip 0x1C
# varint hash length
b = data[pos]; pos += 1
hash_len = b & 0x7F
print(f"  Hash varint: {hash_len}")
if hash_len > 1:
    actual_hash_len = hash_len - 1
    hash_bytes = data[pos:pos+actual_hash_len]
    pos += actual_hash_len
    print(f"  Hash ({actual_hash_len} bytes): {hash_bytes[:50]}")
# varint version length
b = data[pos]; pos += 1
ver_len = b & 0x7F
print(f"  Version varint: {ver_len}")
if ver_len > 1:
    actual_ver_len = ver_len - 1
    ver_bytes = data[pos:pos+actual_ver_len]
    pos += actual_ver_len
    try:
        ver_str = ver_bytes.decode('ascii')
    except:
        ver_str = repr(ver_bytes)
    print(f"  Version ({actual_ver_len} bytes): '{ver_str}'")
# floats
x = struct.unpack_from("<f", data, pos)[0]; pos += 4
y = struct.unpack_from("<f", data, pos)[0]; pos += 4
w = struct.unpack_from("<f", data, pos)[0]; pos += 4
h = struct.unpack_from("<f", data, pos)[0]; pos += 4
print(f"  x={x:.2f} y={y:.2f} w={w:.2f} h={h:.2f}")
print(f"  pos now: {pos}")

print("\n=== Interpretation 2: Fixed 32-byte hash, then version ===")
pos = 1
hash32 = data[pos:pos+32]
pos += 32
print(f"  Hash (32 bytes): {hash32[:32]}")
# Try version as varint
b = data[pos]; pos += 1
ver_len = b & 0x7F
print(f"  Version varint: {ver_len}")
if ver_len > 1:
    actual_ver_len = ver_len - 1
    ver_bytes = data[pos:pos+actual_ver_len]
    pos += actual_ver_len
    try:
        ver_str = ver_bytes.decode('ascii')
    except:
        ver_str = repr(ver_bytes)
    print(f"  Version ({actual_ver_len} bytes): '{ver_str}'")
# floats
x = struct.unpack_from("<f", data, pos)[0]; pos += 4
y = struct.unpack_from("<f", data, pos)[0]; pos += 4
w = struct.unpack_from("<f", data, pos)[0]; pos += 4
h = struct.unpack_from("<f", data, pos)[0]; pos += 4
print(f"  x={x:.2f} y={y:.2f} w={w:.2f} h={h:.2f}")
print(f"  pos now: {pos}")

print("\n=== Interpretation 3: 32-byte hash, version as null-terminated ===")
pos = 1
hash32 = data[pos:pos+32]
pos += 32
print(f"  Hash (32 bytes): {hash32[:32]}")
# Find null terminator for version
null_pos = data.find(0, pos)
if null_pos > 0:
    ver_bytes = data[pos:null_pos]
    pos = null_pos + 1
    try:
        ver_str = ver_bytes.decode('ascii')
    except:
        ver_str = repr(ver_bytes)
    print(f"  Version: '{ver_str}'")
    x = struct.unpack_from("<f", data, pos)[0]; pos += 4
    y = struct.unpack_from("<f", data, pos)[0]; pos += 4
    w = struct.unpack_from("<f", data, pos)[0]; pos += 4
    h = struct.unpack_from("<f", data, pos)[0]; pos += 4
    print(f"  x={x:.2f} y={y:.2f} w={w:.2f} h={h:.2f}")
    print(f"  pos now: {pos}")

print("\n=== Interpretation 4: Skip 0x1C, read version directly ===")
pos = 1
# Maybe the hash is embedded and we skip to version
# Look for "3.8" pattern
idx = data.find(b"3.8", 1)
print(f"  '3.8' found at offset: {idx}")
if idx > 0:
    # Check what's before it
    before = data[1:idx]
    print(f"  Data before '3.8' ({idx-1} bytes): {before[:20].hex()}")
    # Check if it could be a 32-byte hash
    if idx - 1 == 32:
        print("  -> Exactly 32 bytes before '3.8'! Likely fixed hash.")
    # Find null after version
    null_pos = data.find(0, idx)
    if null_pos > 0:
        ver = data[idx:null_pos].decode('ascii', errors='replace')
        print(f"  Version string: '{ver}'")
        pos = null_pos + 1
        x = struct.unpack_from("<f", data, pos)[0]; pos += 4
        y = struct.unpack_from("<f", data, pos)[0]; pos += 4
        w = struct.unpack_from("<f", data, pos)[0]; pos += 4
        h = struct.unpack_from("<f", data, pos)[0]; pos += 4
        print(f"  x={x:.2f} y={y:.2f} w={w:.2f} h={h:.2f}")
        print(f"  pos now: {pos}")
        
        # Check nonessential
        noness = data[pos]; pos += 1
        print(f"  Nonessential: {noness}")
        if noness:
            fps = struct.unpack_from("<f", data, pos)[0]; pos += 4
            # images path
            b2 = data[pos]; pos += 1
            img_len = b2 & 0x7F
            if img_len > 1:
                img = data[pos:pos+img_len-1].decode('utf-8', errors='replace')
                pos += img_len - 1
                print(f"  Images: '{img}'")
            # audio path
            b3 = data[pos]; pos += 1
            aud_len = b3 & 0x7F
            if aud_len > 1:
                aud = data[pos:pos+aud_len-1].decode('utf-8', errors='replace')
                pos += aud_len - 1
                print(f"  Audio: '{aud}'")
        
        # Shared strings
        sc = data[pos]; pos += 1
        print(f"  Shared strings count: {sc}")
        
        # Bones
        bc_raw = data[pos]
        pos += 1
        bc = bc_raw & 0x7F
        if bc_raw & 0x80:
            bc |= (data[pos] & 0x7F) << 7
            pos += 1
        print(f"  Bones count: {bc}")
        
        # Try reading first few bones
        for i in range(min(bc, 5)):
            # bone name as string
            nb = data[pos]; pos += 1
            name_len = nb & 0x7F
            if nb & 0x80:
                name_len |= (data[pos] & 0x7F) << 7
                pos += 1
            if name_len > 1:
                bone_name = data[pos:pos+name_len-1].decode('utf-8', errors='replace')
                pos += name_len - 1
            else:
                bone_name = ""
            print(f"    Bone {i}: '{bone_name}'")
