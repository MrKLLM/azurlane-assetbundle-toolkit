#!/usr/bin/env python3
"""
Parse spine binary format with proper encoding handling.
"""
import UnityPy
import struct
import sys

BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\aerbien_4_res"
env = UnityPy.load(BUNDLE)

for obj in env.objects:
    data = obj.read()
    if obj.type.name == "TextAsset" and data.m_Name.endswith(".skel"):
        obj.reset()
        raw = obj.get_raw_data()
        
        name_len = struct.unpack_from("<i", raw, 0)[0]
        name = raw[4:4+name_len].decode("ascii")
        script_offset = (4 + name_len + 3) & ~3
        script_len = struct.unpack_from("<i", raw, script_offset)[0]
        sd = raw[script_offset + 4: script_offset + 4 + script_len]
        
        sys.stdout.buffer.write(f"Name: {name}\n".encode("utf-8"))
        sys.stdout.buffer.write(f"Data: {len(sd)} bytes\n".encode("utf-8"))
        
        # Analyze the structure
        # First byte: 0x1C
        sys.stdout.buffer.write(f"Byte 0: 0x{sd[0]:02x}\n".encode("utf-8"))
        
        # The spine-unity format might use a different layout than standard spine binary
        # Let's look at all null byte positions to understand the structure
        nulls = []
        for i in range(min(500, len(sd))):
            if sd[i] == 0:
                nulls.append(i)
        sys.stdout.buffer.write(f"Null positions (first 500 bytes): {nulls[:30]}\n".encode("utf-8"))
        
        # Try standard spine binary format (after 0x1C):
        # byte 1: format version (4=3.x, 5=4.x)
        sys.stdout.buffer.write(f"Byte 1 (format version?): 0x{sd[1]:02x} = {sd[1]}\n".encode("utf-8"))
        
        # Maybe the format is:
        # 0x1C + 32-byte hash + version string + null + data
        # But hash contains non-printable chars mixed in
        
        # Let me check if it could be:
        # 0x1C + 32-byte content hash (not ascii) + version string
        # In that case, the null at some position marks end of hash
        
        # Print first 100 bytes as hex with ASCII
        lines = []
        for i in range(0, min(200, len(sd)), 16):
            chunk = sd[i:i+16]
            hex_part = chunk.hex()
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"  {i:04x}: {hex_part:<32s} {ascii_part}")
        sys.stdout.buffer.write("\n".join(lines).encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        
        # Try looking for known string patterns
        # The version should be like "3.8.99" or "3.9.xx"
        for pattern in [b"3.8", b"3.9", b"4.0", b"4.1", b"4.2"]:
            idx = sd.find(pattern)
            if idx >= 0:
                sys.stdout.buffer.write(f"\nFound '{pattern.decode()}' at offset {idx}\n".encode("utf-8"))
                # Show context
                ctx = sd[max(0,idx-10):idx+30]
                sys.stdout.buffer.write(f"  Context hex: {ctx.hex()}\n".encode("utf-8"))
                ascii_ctx = "".join(chr(b) if 32 <= b < 127 else "." for b in ctx)
                sys.stdout.buffer.write(f"  Context ASCII: {ascii_ctx}\n".encode("utf-8"))
                
                # Check for null terminator
                null_after = sd.find(0, idx)
                if null_after > 0 and null_after - idx < 20:
                    ver = sd[idx:null_after]
                    sys.stdout.buffer.write(f"  Version string: {ver}\n".encode("utf-8"))
                    sys.stdout.buffer.write(f"  Data starts at: {null_after + 1}\n".encode("utf-8"))
                    
                    # Try reading data after version
                    d = sd[null_after+1:]
                    sys.stdout.buffer.write(f"  Remaining: {len(d)} bytes\n".encode("utf-8"))
                    
                    # Read first values
                    if len(d) >= 28:
                        h = d[:16]
                        w = struct.unpack_from("<f", d, 16)[0]
                        h2 = struct.unpack_from("<f", d, 20)[0]
                        f = struct.unpack_from("<f", d, 24)[0]
                        sys.stdout.buffer.write(f"  Hash: {h.hex()}\n".encode("utf-8"))
                        sys.stdout.buffer.write(f"  Width: {w}\n".encode("utf-8"))
                        sys.stdout.buffer.write(f"  Height: {h2}\n".encode("utf-8"))
                        sys.stdout.buffer.write(f"  FPS: {f}\n".encode("utf-8"))
                    break
