#!/usr/bin/env python3
"""Verify spine 4.x format interpretation"""
import struct
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SKEL = r"D:\Azur Lane Assets\Output\Spine\spinepainting\aerbien_4\aerbien_4.skel"

with open(SKEL, "rb") as f:
    data = f.read()

print(f"File: {len(data)} bytes")

# Spine 4.x format: skip 0x1C, read two int32, then string, then floats
pos = 0

# Skip 0x1C
pos = 1

# Two int32 for hash
n = struct.unpack_from("<i", data, pos)[0]; pos += 4
r = struct.unpack_from("<i", data, pos)[0]; pos += 4
print(f"Hash int32s: n={n} (0x{n:08x}), r={r} (0x{r:08x})")
if r == 0 and n == 0:
    print("Hash: null")
else:
    print(f"Hash: {r.toString(16)}{n.toString(16)}")

# Version string (varint+ length + bytes)
# In spine 4.x, readString uses readVarint then reads bytes
# Let me check what readVarint does in the minified code
# Actually, let me just try reading the version as a null-terminated string
# from the current position

# Check what's at current position
print(f"\nBytes at pos {pos}: {data[pos:pos+20].hex()}")

# Try reading as string with length prefix (varint)
# Read first byte as varint
b = data[pos]
print(f"First byte: 0x{b:02x} = {b}")
if b < 0x80:
    str_len = b
    pos += 1
else:
    str_len = b & 0x7F
    b2 = data[pos+1]
    str_len |= (b2 & 0x7F) << 7
    pos += 2

print(f"String length varint: {str_len}")

# Spine readString: if len <= 1, return empty/null; else read len-1 bytes
if str_len > 1:
    actual_len = str_len - 1
    version = data[pos:pos+actual_len].decode('utf-8', errors='replace')
    pos += actual_len
    print(f"Version: '{version}'")
else:
    version = ""
    print(f"Version: empty")

# Now read floats: x, y, width, height
x = struct.unpack_from("<f", data, pos)[0]; pos += 4
y = struct.unpack_from("<f", data, pos)[0]; pos += 4
w = struct.unpack_from("<f", data, pos)[0]; pos += 4
h = struct.unpack_from("<f", data, pos)[0]; pos += 4
print(f"Position: ({x:.2f}, {y:.2f})")
print(f"Size: {w:.2f} x {h:.2f}")

# Reference scale
ref_scale = struct.unpack_from("<f", data, pos)[0]; pos += 4
print(f"Reference scale: {ref_scale}")

# Nonessential
noness = struct.unpack_from("<B", data, pos)[0]; pos += 1
print(f"Nonessential: {noness}")

if noness:
    fps = struct.unpack_from("<f", data, pos)[0]; pos += 4
    # images path
    b = data[pos]
    img_len = b if b < 0x80 else (b & 0x7F) | ((data[pos+1] & 0x7F) << 7)
    if b < 0x80:
        pos += 1
    else:
        pos += 2
    if img_len > 1:
        images = data[pos:pos+img_len-1].decode('utf-8', errors='replace')
        pos += img_len - 1
    else:
        images = ""
    # audio path
    b = data[pos]
    aud_len = b if b < 0x80 else (b & 0x7F) | ((data[pos+1] & 0x7F) << 7)
    if b < 0x80:
        pos += 1
    else:
        pos += 2
    if aud_len > 1:
        audio = data[pos:pos+aud_len-1].decode('utf-8', errors='replace')
        pos += aud_len - 1
    else:
        audio = ""
    print(f"FPS: {fps}, Images: '{images}', Audio: '{audio}'")

# Shared strings count
sc_raw = data[pos]
sc = sc_raw if sc_raw < 0x80 else (sc_raw & 0x7F) | ((data[pos+1] & 0x7F) << 7)
if sc_raw < 0x80:
    pos += 1
else:
    pos += 2
print(f"Shared strings: {sc}")

# Bones count
bc_raw = data[pos]
bc = bc_raw if bc_raw < 0x80 else (bc_raw & 0x7F) | ((data[pos+1] & 0x7F) << 7)
if bc_raw < 0x80:
    pos += 1
else:
    pos += 2
print(f"Bones: {bc}")

# Read first few bone names
for i in range(min(bc, 5)):
    nb = data[pos]
    name_len = nb if nb < 0x80 else (nb & 0x7F) | ((data[pos+1] & 0x7F) << 7)
    if nb < 0x80:
        pos += 1
    else:
        pos += 2
    if name_len > 1:
        bone_name = data[pos:pos+name_len-1].decode('utf-8', errors='replace')
        pos += name_len - 1
    else:
        bone_name = ""
    print(f"  Bone {i}: '{bone_name}'")

print(f"\nFinal pos: {pos}/{len(data)} ({len(data)-pos} remaining)")
