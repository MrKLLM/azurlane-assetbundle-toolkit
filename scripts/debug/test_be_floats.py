#!/usr/bin/env python3
"""Test big-endian float reading after version string"""
import struct
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SKEL = r"D:\Azur Lane Assets\Output\Spine\spinepainting\aerbien_4\aerbien_4.skel"

with open(SKEL, "rb") as f:
    data = f.read()

# Format: 0x1C + 32-byte hash + null + version_string + null + floats...
pos = 1  # skip 0x1C

# 32-byte hash
hash32 = data[pos:pos+32]
pos += 32
print(f"Hash: {hash32}")

# Null terminator
print(f"Null at {pos}: {data[pos]}")
pos += 1

# Version string - find null terminator
null_pos = data.find(0, pos)
version = data[pos:null_pos].decode('ascii', errors='replace')
pos = null_pos + 1
print(f"Version: '{version}'")

# Now read floats - try BOTH endianness
print(f"\nReading 8 floats from offset {pos}:")
print("  Little-endian:")
for i in range(8):
    v = struct.unpack_from("<f", data, pos + i*4)[0]
    print(f"    [{i}] {v:.6f}")

print("  Big-endian:")
for i in range(8):
    v = struct.unpack_from(">f", data, pos + i*4)[0]
    print(f"    [{i}] {v:.6f}")

# Also try reading as int32 and checking
print("\n  As int32 LE:")
for i in range(4):
    v = struct.unpack_from("<i", data, pos + i*4)[0]
    print(f"    [{i}] {v} (0x{v:08x})")

print("  As int32 BE:")
for i in range(4):
    v = struct.unpack_from(">i", data, pos + i*4)[0]
    print(f"    [{i}] {v} (0x{v:08x})")

# Check if the data at pos looks like slot names
print(f"\nData at offset {pos}:")
for i in range(0, min(64, len(data)-pos), 16):
    chunk = data[pos+i:pos+i+16]
    hex_str = " ".join(f"{b:02x}" for b in chunk)
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    print(f"  {pos+i:04x}: {hex_str:<48s} {ascii_str}")
