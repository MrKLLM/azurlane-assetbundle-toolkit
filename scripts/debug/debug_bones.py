#!/usr/bin/env python3
"""Debug bone reading step by step"""
import struct
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SKEL = r"D:\Azur Lane Assets\Output\Spine\spinepainting\aerbien_4\aerbien_4.skel"

with open(SKEL, "rb") as f:
    data = f.read()

pos = 1  # skip 0x1C

# Read hash string
def read_varint(d, p):
    b = d[p]; p += 1
    v = b & 0x7F
    s = 7
    while b & 0x80:
        b = d[p]; p += 1
        v |= (b & 0x7F) << s
        s += 7
    return v, p

def read_str(d, p):
    length, p = read_varint(d, p)
    if length <= 1:
        return "", p
    length -= 1
    s = d[p:p+length].decode('utf-8', errors='replace')
    return s, p + length

def read_float(d, p):
    return struct.unpack_from("<f", d, p)[0], p + 4

# Hash
hash_str, pos = read_str(data, pos)
print(f"Hash: len={len(hash_str)}")

# Version
version, pos = read_str(data, pos)
print(f"Version: '{version}'")

# x, y, w, h
x, pos = read_float(data, pos)
y, pos = read_float(data, pos)
w, pos = read_float(data, pos)
h, pos = read_float(data, pos)
print(f"Pos: ({x:.2f}, {y:.2f})")
print(f"Size: {w:.2f} x {h:.2f}")

# Nonessential
noness = data[pos]; pos += 1
print(f"Nonessential: {noness}")

if noness:
    fps, pos = read_float(data, pos)
    images, pos = read_str(data, pos)
    audio, pos = read_str(data, pos)
    print(f"FPS: {fps}, Images: '{images}', Audio: '{audio}'")

# Shared strings
sc, pos = read_varint(data, pos)
print(f"\nShared strings: {sc}")
shared = []
for i in range(sc):
    s, pos = read_str(data, pos)
    shared.append(s)
    if i < 10:
        print(f"  [{i}] '{s}'")

# Bones
bc, pos = read_varint(data, pos)
print(f"\nBones: {bc}")

# Read first 5 bones carefully
bones = []
for i in range(min(bc, 5)):
    name, pos = read_str(data, pos)
    parent_idx, pos = read_varint(data, pos)
    rotation, pos = read_float(data, pos)
    bx, pos = read_float(data, pos)
    by, pos = read_float(data, pos)
    sx, pos = read_float(data, pos)
    sy, pos = read_float(data, pos)
    shx, pos = read_float(data, pos)
    shy, pos = read_float(data, pos)
    length, pos = read_float(data, pos)
    transform, pos = read_varint(data, pos)
    skin_req = data[pos]; pos += 1
    
    parent = bones[parent_idx - 1]["name"] if parent_idx > 0 else "(root)"
    bones.append({"name": name, "parent_idx": parent_idx})
    print(f"  [{i}] name='{name}' parent_idx={parent_idx} parent='{parent}' "
          f"rot={rotation:.2f} pos=({bx:.2f},{by:.2f}) scale=({sx:.2f},{sy:.2f}) "
          f"shear=({shx:.2f},{shy:.2f}) len={length:.2f} trans={transform} skin={skin_req}")

print(f"\nPos after 5 bones: {pos}")
print(f"Remaining: {len(data) - pos}")
