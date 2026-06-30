#!/usr/bin/env python3
"""
Analyze the spine binary to understand the bone name issue.
Read the .skel file and try to extract bone names manually.
"""
import struct
import sys

def read_varint(data, pos, optimize_positive=True):
    """Read a varint from data at pos."""
    b = data[pos]
    pos += 1
    value = b & 0x7F
    shift = 7
    while b & 0x80:
        if pos >= len(data):
            return value, pos
        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        shift += 7
    if not optimize_positive:
        value = (value >> 1) ^ -(value & 1)
    return value, pos

def read_string(data, pos):
    """Read a spine binary string (varint length + bytes)."""
    length, pos = read_varint(data, pos, True)
    if length <= 1:
        return "", pos
    length -= 1
    s = data[pos:pos+length].decode("utf-8", errors="replace")
    return s, pos + length

def read_float(data, pos):
    val = struct.unpack_from("<f", data, pos)[0]
    return val, pos + 4

SKEL_PATH = r"D:\Azur Lane Assets\Output\Spine\spinepainting\aerbien_4\aerbien_4.skel"

with open(SKEL_PATH, "rb") as f:
    data = f.read()

print(f"File size: {len(data)} bytes")
print(f"First byte: 0x{data[0]:02x}")

# Skip 0x1C signature
pos = 1

# Read hash string
hash_str, pos = read_string(data, pos)
print(f"Hash: '{hash_str[:50]}...' (len={len(hash_str)})")
print(f"  Hash bytes: {data[1:pos].hex()}")

# Read version string
version, pos = read_string(data, pos)
print(f"Version: '{version}'")
print(f"  Version bytes: {data[pos-len(version)-5:pos].hex()}")

# Read width, height, x, y
x, pos = read_float(data, pos)
y, pos = read_float(data, pos)
w, pos = read_float(data, pos)
h, pos = read_float(data, pos)
print(f"Position: ({x}, {y})")
print(f"Size: {w} x {h}")

# Read nonessential
nonessential = data[pos]
pos += 1
print(f"Nonessential: {nonessential}")

if nonessential:
    fps, pos = read_float(data, pos)
    images, pos = read_string(data, pos)
    audio, pos = read_string(data, pos)
    print(f"FPS: {fps}")
    print(f"Images: '{images}'")
    print(f"Audio: '{audio}'")

# Read shared strings
string_count, pos = read_varint(data, pos, True)
print(f"\nShared strings count: {string_count}")
shared_strings = []
for i in range(string_count):
    s, pos = read_string(data, pos)
    shared_strings.append(s)
    if i < 5:
        print(f"  [{i}] '{s}'")
if string_count > 5:
    print(f"  ... ({string_count} total)")

# Read bones
bone_count, pos = read_varint(data, pos, True)
print(f"\nBones count: {bone_count}")
bone_names = []
for i in range(min(bone_count, 20)):
    name, pos = read_string(data, pos)
    bone_names.append(name)
    # Read parent index
    parent_idx, pos = read_varint(data, pos, True)
    # Read remaining bone data
    rotation, pos = read_float(data, pos)
    bx, pos = read_float(data, pos)
    by, pos = read_float(data, pos)
    sx, pos = read_float(data, pos)
    sy, pos = read_float(data, pos)
    shx, pos = read_float(data, pos)
    shy, pos = read_float(data, pos)
    length, pos = read_float(data, pos)
    # Transform mode
    transform, pos = read_varint(data, pos, True)
    # skin required
    skin_req = data[pos]
    pos += 1
    parent_str = bone_names[parent_idx - 1] if parent_idx > 0 else "(root)"
    print(f"  [{i}] '{name}' parent={parent_str} pos=({bx:.1f},{by:.1f})")

if bone_count > 20:
    print(f"  ... ({bone_count} total)")

print(f"\nFinal position: {pos}/{len(data)}")
print(f"Remaining: {len(data) - pos} bytes")
