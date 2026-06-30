#!/usr/bin/env python3
"""Carefully parse spine 3.8 binary format - step by step with hex dump"""
import struct
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SKEL = r"D:\Azur Lane Assets\Output\Spine\spinepainting\aerbien_4\aerbien_4.skel"

with open(SKEL, "rb") as f:
    data = f.read()

# Show first 256 bytes in hex+ascii
print("=== First 256 bytes ===")
for i in range(0, min(256, len(data)), 16):
    chunk = data[i:i+16]
    hex_str = " ".join(f"{b:02x}" for b in chunk)
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    print(f"  {i:04x}: {hex_str:<48s} {ascii_str}")

# The format starts with 0x1C
# After 0x1C, the next 32 bytes should be the hash
# Let me check if the hash is 32 bytes fixed (no length prefix)
pos = 0
print(f"\nByte 0: 0x{data[0]:02x}")

# Skip 0x1C
pos = 1

# Hash: 32 bytes fixed?
hash_bytes = data[pos:pos+32]
print(f"Hash (32 bytes): {hash_bytes}")
pos += 32

# Now version string
# Check if there's a length prefix or null terminator
print(f"\nBytes after hash (offset {pos}):")
for i in range(0, min(64, len(data)-pos), 16):
    chunk = data[pos+i:pos+i+16]
    hex_str = " ".join(f"{b:02x}" for b in chunk)
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    print(f"  {pos+i:04x}: {hex_str:<48s} {ascii_str}")

# Look for version string pattern
# Find "3.8" in the data
idx38 = data.find(b"3.8", pos)
print(f"\n'3.8' found at offset: {idx38}")
if idx38 > 0:
    # Check bytes before and after
    before = data[max(0,idx38-5):idx38]
    after = data[idx38:idx38+20]
    print(f"  Before: {before.hex()} = {before}")
    print(f"  After: {after.hex()} = {after}")
    
    # Find null terminator after version
    null_pos = data.find(0, idx38)
    if null_pos > 0:
        version = data[idx38:null_pos].decode('ascii', errors='replace')
        print(f"  Version: '{version}' (ends at {null_pos})")
        
        # Now check what's before the version
        # If the format is: 0x1C + 28 bytes + "3.8.99\0" + data...
        # Then offset 1-28 is the hash, offset 29 is start of version
        pre_version = data[1:idx38]
        print(f"  Pre-version data ({len(pre_version)} bytes): {pre_version.hex()}")
        
        # Check if it could be a 28-byte hash
        if len(pre_version) == 28:
            print("  -> 28-byte hash confirmed!")
        
        # Now read data after version
        data_start = null_pos + 1
        print(f"\n  Data starts at offset {data_start}")
        
        # Read floats
        vals = []
        for i in range(8):
            if data_start + (i+1)*4 <= len(data):
                v = struct.unpack_from("<f", data, data_start + i*4)[0]
                vals.append(v)
        print(f"  First 8 floats (LE): {vals}")
        
        # Also try big-endian
        vals_be = []
        for i in range(8):
            if data_start + (i+1)*4 <= len(data):
                v = struct.unpack_from(">f", data, data_start + i*4)[0]
                vals_be.append(v)
        print(f"  First 8 floats (BE): {vals_be}")
        
        # Check what makes sense for skeleton dimensions
        # Typical values: x, y around -1000 to 1000, width/height around 100-5000
        print(f"\n  LE interpretation: pos=({vals[0]:.2f},{vals[1]:.2f}) size={vals[2]:.2f}x{vals[3]:.2f} refScale={vals[4]:.4f}")
        print(f"  BE interpretation: pos=({vals_be[0]:.2f},{vals_be[1]:.2f}) size={vals_be[2]:.2f}x{vals_be[3]:.2f} refScale={vals_be[4]:.4f}")
