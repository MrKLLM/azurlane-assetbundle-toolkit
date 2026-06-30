#!/usr/bin/env python3
"""Correct spine 3.8 binary format parser"""
import struct
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SKEL = r"D:\Azur Lane Assets\Output\Spine\spinepainting\aerbien_4\aerbien_4.skel"

with open(SKEL, "rb") as f:
    data = f.read()

pos = 1  # skip 0x1C

# Hash: read as string (varint length + bytes)
# But wait - the "hash" at offset 1-32 includes "3.8." at the end
# So the hash is NOT a length-prefixed string
# Let me check: is the format fixed 32-byte hash + then version?

# Read 32 bytes as hash
hash_bytes = data[pos:pos+32]
pos += 32
print(f"Hash (32 bytes): {hash_bytes}")

# Now at offset 33: 0x07
# This could be: varint 7 (version string length) 
# Or: fixed byte (not a length prefix)
b = data[pos]
print(f"Byte at {pos}: 0x{b:02x} = {b}")

# If it's a varint for string length:
# spine readString: length varint, then length-1 bytes
if b == 7:
    # Version string is 6 bytes: "3.8.99"
    version = data[pos+1:pos+1+6].decode('ascii')
    pos += 1 + 6
    print(f"Version: '{version}'")
elif b < 128:
    # It's a varint
    str_len = b
    if str_len > 1:
        actual_len = str_len - 1
        version = data[pos+1:pos+1+actual_len].decode('ascii', errors='replace')
        pos += 1 + actual_len
        print(f"Version (varint {str_len}): '{version}'")
    else:
        version = ""
        pos += 1
        print("Version: empty")

# Now read floats: x, y, width, height
# These should be after the version string
print(f"\nReading floats from offset {pos}:")
for i in range(8):
    if pos + 4 <= len(data):
        v = struct.unpack_from("<f", data, pos)[0]
        print(f"  float[{i}] at {pos}: {v:.4f}")
        pos += 4

# Check nonessential flag
print(f"\nNonessential at {pos}: {data[pos]}")
noness = data[pos]
pos += 1

if noness:
    fps = struct.unpack_from("<f", data, pos)[0]; pos += 4
    print(f"FPS: {fps}")
    # Read images path
    b = data[pos]
    img_len = b if b < 128 else (b & 0x7F) | ((data[pos+1] & 0x7F) << 7)
    if b < 128:
        pos += 1
    else:
        pos += 2
    if img_len > 1:
        images = data[pos:pos+img_len-1].decode('utf-8', errors='replace')
        pos += img_len - 1
    else:
        images = ""
    print(f"Images: '{images}'")
    # Audio path
    b = data[pos]
    aud_len = b if b < 128 else (b & 0x7F) | ((data[pos+1] & 0x7F) << 7)
    if b < 128:
        pos += 1
    else:
        pos += 2
    if aud_len > 1:
        audio = data[pos:pos+aud_len-1].decode('utf-8', errors='replace')
        pos += aud_len - 1
    else:
        audio = ""
    print(f"Audio: '{audio}'")

# Shared strings
sc_b = data[pos]
sc = sc_b if sc_b < 128 else (sc_b & 0x7F) | ((data[pos+1] & 0x7F) << 7)
if sc_b < 128:
    pos += 1
else:
    pos += 2
print(f"\nShared strings: {sc}")

# Read shared strings
shared = []
for i in range(sc):
    b = data[pos]
    s_len = b if b < 128 else (b & 0x7F) | ((data[pos+1] & 0x7F) << 7)
    if b < 128:
        pos += 1
    else:
        pos += 2
    if s_len > 1:
        s = data[pos:pos+s_len-1].decode('utf-8', errors='replace')
        pos += s_len - 1
    else:
        s = ""
    shared.append(s)
    if i < 5:
        print(f"  [{i}] '{s}'")

# Bones
bc_b = data[pos]
bc = bc_b if bc_b < 128 else (bc_b & 0x7F) | ((data[pos+1] & 0x7F) << 7)
if bc_b < 128:
    pos += 1
else:
    pos += 2
print(f"\nBones: {bc}")

# Read first 3 bones
bones = []
for i in range(min(bc, 3)):
    # Bone name
    b = data[pos]
    n_len = b if b < 128 else (b & 0x7F) | ((data[pos+1] & 0x7F) << 7)
    if b < 128:
        pos += 1
    else:
        pos += 2
    if n_len > 1:
        bone_name = data[pos:pos+n_len-1].decode('utf-8', errors='replace')
        pos += n_len - 1
    else:
        bone_name = ""
    
    # Parent index
    pi_b = data[pos]
    pi = pi_b if pi_b < 128 else (pi_b & 0x7F) | ((data[pos+1] & 0x7F) << 7)
    if pi_b < 128:
        pos += 1
    else:
        pos += 2
    
    # Read bone floats
    rotation = struct.unpack_from("<f", data, pos)[0]; pos += 4
    bx = struct.unpack_from("<f", data, pos)[0]; pos += 4
    by = struct.unpack_from("<f", data, pos)[0]; pos += 4
    sx = struct.unpack_from("<f", data, pos)[0]; pos += 4
    sy = struct.unpack_from("<f", data, pos)[0]; pos += 4
    shx = struct.unpack_from("<f", data, pos)[0]; pos += 4
    shy = struct.unpack_from("<f", data, pos)[0]; pos += 4
    length = struct.unpack_from("<f", data, pos)[0]; pos += 4
    
    # Transform mode
    tm_b = data[pos]
    tm = tm_b if tm_b < 128 else (tm_b & 0x7F) | ((data[pos+1] & 0x7F) << 7)
    if tm_b < 128:
        pos += 1
    else:
        pos += 2
    
    # Skin required
    skin_req = data[pos]; pos += 1
    
    parent = bones[pi - 1]["name"] if pi > 0 else "(root)"
    bones.append({"name": bone_name})
    print(f"  [{i}] '{bone_name}' parent={pi}('{parent}') rot={rotation:.2f} pos=({bx:.2f},{by:.2f}) scale=({sx:.2f},{sy:.2f}) len={length:.2f} transform={tm}")

print(f"\nFinal pos: {pos}/{len(data)}")
