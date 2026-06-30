#!/usr/bin/env python3
"""
Properly extract raw bytes from TextAsset using UnityPy's raw data access.
"""
import UnityPy
import struct
import os

BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\aerbien_4_res"

env = UnityPy.load(BUNDLE)

for obj in env.objects:
    data = obj.read()
    if obj.type.name == "TextAsset" and data.m_Name.endswith(".skel"):
        print(f"TextAsset: {data.m_Name}")
        
        # The m_Script in UnityPy for TextAsset is the raw bytes of the text content
        # But it's returned as a string with encoding issues
        # Let's try to get the raw data properly
        
        # Method 1: Read raw data from the object
        obj.reset()
        raw = obj.get_raw_data()
        print(f"Raw data size: {len(raw)}")
        print(f"Raw first 50 hex: {raw[:50].hex()}")
        
        # The raw data seems to be the Unity serialization wrapper
        # Let's try to find the actual content
        # Unity TextAsset serialization:
        # - int32: name length
        # - char[]: name
        # - int32: script length  
        # - byte[]: script
        
        if len(raw) > 8:
            # Try reading as Unity serialized TextAsset
            name_len = struct.unpack_from("<i", raw, 0)[0]
            print(f"Name length: {name_len}")
            if 0 < name_len < 100:
                name_bytes = raw[4:4+name_len]
                print(f"Name: {name_bytes}")
                
                # After name, there might be padding or the script data
                script_offset = 4 + name_len
                # Align to 4 bytes
                script_offset = (script_offset + 3) & ~3
                print(f"Script offset (aligned): {script_offset}")
                
                if script_offset + 4 <= len(raw):
                    script_len = struct.unpack_from("<i", raw, script_offset)[0]
                    print(f"Script length: {script_len}")
                    
                    if 0 < script_len < len(raw):
                        script_data = raw[script_offset+4:script_offset+4+script_len]
                        print(f"Script data size: {len(script_data)}")
                        print(f"Script first 20 hex: {script_data[:20].hex()}")
                        print(f"Script first byte: 0x{script_data[0]:02x}")
                        
                        # Check if this is the actual skel data
                        if script_data[0] == 0x1C:
                            print("\n==> Found Spine binary data!")
                            # Save it for testing
                            out_path = r"D:\Azur Lane Assets\scripts\debug\aerbien_4.skel"
                            with open(out_path, "wb") as f:
                                f.write(script_data)
                            print(f"Saved to: {out_path}")
                        else:
                            print(f"Not Spine binary (first byte: 0x{script_data[0]:02x})")
        
        # Method 2: Try the objects reader directly
        print("\n--- Method 2: Object reader ---")
        obj.reset()
        # Read the raw data and try to find the pattern
        raw2 = obj.get_raw_data()
        # Search for the 0x1C signature
        idx = raw2.find(b"\x1c")
        if idx >= 0:
            print(f"Found 0x1C at offset {idx}")
            # Check if next bytes make sense
            print(f"Context: {raw2[max(0,idx-4):idx+20].hex()}")
