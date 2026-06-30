#!/usr/bin/env python3
"""
Properly extract and validate the skel binary data.
"""
import UnityPy
import struct
import json

BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\aerbien_4_res"
env = UnityPy.load(BUNDLE)

for obj in env.objects:
    data = obj.read()
    if obj.type.name == "TextAsset" and data.m_Name.endswith(".skel"):
        obj.reset()
        raw = obj.get_raw_data()
        
        # Parse Unity TextAsset format
        name_len = struct.unpack_from("<i", raw, 0)[0]
        name = raw[4:4+name_len].decode("ascii")
        
        # Script data starts after name (aligned to 4 bytes)
        script_offset = 4 + name_len
        script_offset = (script_offset + 3) & ~3  # align to 4
        script_len = struct.unpack_from("<i", raw, script_offset)[0]
        script_data = raw[script_offset + 4: script_offset + 4 + script_len]
        
        print(f"Name: {name}")
        print(f"Script offset: {script_offset}")
        print(f"Script length: {script_len}")
        print(f"Script data: {len(script_data)} bytes")
        print(f"First byte: 0x{script_data[0]:02x}")
        
        # Now analyze the spine binary format
        # Format: 0x1C + hash(32) + version_string + null + data
        if script_data[0] != 0x1C:
            print("Not spine binary!")
            continue
        
        # The hash is 32 bytes after 0x1C
        hash_bytes = script_data[1:33]
        print(f"Hash: {hash_bytes.decode('ascii', errors='replace')}")
        
        # Version string starts at offset 33
        # Find null terminator
        ver_start = 33
        null_pos = script_data.find(0, ver_start)
        if null_pos < 0:
            print("No null terminator found for version!")
            continue
        
        version = script_data[ver_start:null_pos].decode("ascii", errors="replace")
        print(f"Version: '{version}'")
        
        data_start = null_pos + 1
        remaining = script_data[data_start:]
        print(f"Data starts at: {data_start}")
        print(f"Remaining: {len(remaining)} bytes")
        
        # Now parse the Spine binary skeleton data
        # According to Spine runtime source code:
        # 1. hash: 16 bytes
        # 2. width: float32
        # 3. height: float32
        # 4. fps: float32
        # 5. images path: null-terminated string
        # 6. audio path: null-terminated string
        
        d = remaining
        pos = 0
        
        # Hash (16 bytes)
        skel_hash = d[pos:pos+16]
        print(f"\nSkeleton hash: {skel_hash.hex()}")
        pos += 16
        
        # Width
        width = struct.unpack_from("<f", d, pos)[0]
        print(f"Width: {width}")
        pos += 4
        
        # Height
        height = struct.unpack_from("<f", d, pos)[0]
        print(f"Height: {height}")
        pos += 4
        
        # FPS
        fps = struct.unpack_from("<f", d, pos)[0]
        print(f"FPS: {fps}")
        pos += 4
        
        # Images path
        img_end = d.find(0, pos)
        if img_end > 0:
            images_path = d[pos:img_end].decode("utf-8", errors="replace")
            print(f"Images path: '{images_path}'")
            pos = img_end + 1
        
        # Audio path
        aud_end = d.find(0, pos)
        if aud_end > 0:
            audio_path = d[pos:aud_end].decode("utf-8", errors="replace")
            print(f"Audio path: '{audio_path}'")
            pos = aud_end + 1
        
        # Bones count
        bone_count = struct.unpack_from("<i", d, pos)[0]
        print(f"\nBones count: {bone_count}")
        pos += 4
        
        # Check if bone_count is reasonable
        if 0 < bone_count < 1000:
            print("Bone count looks reasonable!")
            
            # Try to read bone names
            for i in range(min(5, bone_count)):
                name_end = d.find(0, pos)
                if name_end > 0:
                    bone_name = d[pos:name_end].decode("utf-8", errors="replace")
                    print(f"  Bone {i}: {bone_name}")
                    pos = name_end + 1
        else:
            print(f"Bone count seems wrong: {bone_count}")
            # Maybe the format is different
            # Let's check if there's a different interpretation
            print(f"Bytes at pos: {d[pos:pos+20].hex()}")
