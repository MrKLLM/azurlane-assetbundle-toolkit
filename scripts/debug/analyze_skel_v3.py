#!/usr/bin/env python3
"""Analyze spine binary bone names with encoding fix"""
import struct
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def read_varint(data, pos, optimize_positive=True):
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

pos = 1

# Read hash
hash_str, pos = read_string(data, pos)
print(f"Hash len: {len(hash_str)}, first 10 bytes hex: {data[1:min(pos,11)].hex()}")

# Read version
version, pos = read_string(data, pos)
print(f"Version: '{version}'")

# Read x, y, width, height
x, pos = read_float(data, pos)
y, pos = read_float(data, pos)
w, pos = read_float(data, pos)
h, pos = read_float(data, pos)
print(f"Position: ({x:.2f}, {y:.2f})")
print(f"Size: {w:.2f} x {h:.2f}")

# Read nonessential
nonessential = data[pos]
pos += 1
print(f"Nonessential: {nonessential}")

if nonessential:
    fps, pos = read_float(data, pos)
    images, pos = read_string(data, pos)
    audio, pos = read_string(data, pos)
    print(f"FPS: {fps:.2f}, Images: '{images}', Audio: '{audio}'")

# Shared strings
string_count, pos = read_varint(data, pos, True)
print(f"\nShared strings: {string_count}")
shared_strings = []
for i in range(string_count):
    s, pos = read_string(data, pos)
    shared_strings.append(s)

# Bones
bone_count, pos = read_varint(data, pos, True)
print(f"Bones: {bone_count}")

if bone_count > 0 and bone_count < 500:
    bone_names = []
    for i in range(bone_count):
        name, pos = read_string(data, pos)
        bone_names.append(name)
        parent_idx, pos = read_varint(data, pos, True)
        rotation, pos = read_float(data, pos)
        bx, pos = read_float(data, pos)
        by, pos = read_float(data, pos)
        sx, pos = read_float(data, pos)
        sy, pos = read_float(data, pos)
        shx, pos = read_float(data, pos)
        shy, pos = read_float(data, pos)
        length, pos = read_float(data, pos)
        transform, pos = read_varint(data, pos, True)
        skin_req = data[pos]
        pos += 1
        if i < 10 or name == "":
            parent_str = bone_names[parent_idx - 1] if parent_idx > 0 else "(root)"
            print(f"  [{i}] '{name}' parent='{parent_str}' pos=({bx:.1f},{by:.1f})")
    print(f"  ({bone_count} total)")

# Slots
slot_count, pos = read_varint(data, pos, True)
print(f"\nSlots: {slot_count}")
if slot_count > 0 and slot_count < 500:
    for i in range(min(slot_count, 10)):
        name, pos = read_string(data, pos)
        bone_idx, pos = read_varint(data, pos, True)
        color, pos = read_float(data, pos)  # actually int32
        pos -= 4  # undo - color is an int
        rgba = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        dark = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        att, pos = read_string(data, pos)
        # Blend mode
        # blend = data[pos]; pos += 1  -- only if nonessential?
        print(f"  [{i}] '{name}' bone={bone_idx} att='{att}'")

print(f"\nFinal pos: {pos}/{len(data)} ({len(data)-pos} remaining)")
