#!/usr/bin/env python3
"""
Try to extract raw bytes from skel files using different UnityPy approaches.
Also check if the binary can be loaded by spine-ts format.
"""
import UnityPy
import struct
import json
import os

BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\aerbien_4_res"

env = UnityPy.load(BUNDLE)

for obj in env.objects:
    data = obj.read()
    if obj.type.name == "TextAsset" and data.m_Name.endswith(".skel"):
        print(f"TextAsset: {data.m_Name}")
        print(f"m_Script type: {type(data.m_Script)}")
        
        # Method 1: Direct string
        skel_str = data.m_Script
        if isinstance(skel_str, str):
            # Try different encodings to get raw bytes
            for enc in ["latin-1", "cp1252", "iso-8859-1", "utf-8"]:
                try:
                    raw = skel_str.encode(enc, errors="strict")
                    print(f"  {enc}: {len(raw)} bytes, first 4: {raw[:4].hex()}")
                    break
                except:
                    pass
            else:
                raw = skel_str.encode("utf-8", errors="surrogateescape")
                print(f"  utf-8 surrogateescape: {len(raw)} bytes, first 4: {raw[:4].hex()}")
        
        # Method 2: Try to get raw bytes from object reader
        obj.reset()
        raw_bytes = obj.get_raw_data()
        print(f"\n  Raw data from reader: {len(raw_bytes)} bytes")
        print(f"  First 20 hex: {raw_bytes[:20].hex()}")
        
        # Check if it matches the string data
        if isinstance(skel_str, str):
            str_bytes = skel_str.encode("latin-1", errors="replace")
            if raw_bytes[:100] == str_bytes[:100]:
                print("  Raw data matches string data")
            else:
                print("  Raw data DIFFERS from string data!")
                print(f"  String first 20 hex: {str_bytes[:20].hex()}")
        
        # Method 3: Read the raw file bytes directly
        # UnityPy stores the raw asset data
        reader = obj.object_reader
        print(f"\n  Reader type: {type(reader)}")
        
        # Try to find the raw data in the reader
        if hasattr(reader, "reader"):
            inner = reader.reader
            print(f"  Inner reader type: {type(inner)}")
            if hasattr(inner, "data"):
                print(f"  Inner data type: {type(inner.data)}, len: {len(inner.data)}")

        # Now let's check: is the data actually standard Spine binary?
        # Standard Spine binary starts with 0x1C, then version byte, then version string
        # Let me check if the issue is that the string encoding corrupted the data
        raw_data = raw_bytes
        
        print(f"\n=== Binary analysis ===")
        print(f"First byte: 0x{raw_data[0]:02x}")
        
        if raw_data[0] == 0x1C:
            ver_byte = raw_data[1]
            print(f"Version byte: {ver_byte}")
            
            # In spine 3.x, version byte is 4 (or similar)
            # In spine 4.x, version byte is 5
            # Version 99 seems wrong - might be corrupted
            
            # Let's look at what the actual format might be
            # Maybe it's: 0x1C + 32-byte hash + version string + data
            hash_data = raw_data[1:33]
            print(f"Hash (32 bytes): {hash_data}")
            
            # Find version string
            for i in range(33, min(200, len(raw_data))):
                if raw_data[i:i+2] in [b"3.", b"4."]:
                    null_pos = raw_data.find(0, i)
                    if null_pos > 0:
                        ver = raw_data[i:null_pos].decode("ascii", errors="replace")
                        print(f"Version string at {i}: '{ver}'")
                        data_start = null_pos + 1
                        print(f"Data starts at: {data_start}")
                        
                        # Try to parse the remaining data as Spine binary
                        # After version, there should be:
                        # - hash (16 bytes)
                        # - width (float)
                        # - height (float)
                        # - fps (float)
                        # - images path (null-terminated string)
                        # - audio path (null-terminated string)
                        d = raw_data[data_start:]
                        print(f"Remaining data: {len(d)} bytes")
                        
                        # Read hash
                        if len(d) >= 16:
                            skel_hash = d[:16]
                            print(f"Skeleton hash: {skel_hash.hex()}")
                        
                        # Read width/height
                        if len(d) >= 24:
                            w, h = struct.unpack_from("<ff", d, 16)
                            print(f"Width: {w}, Height: {h}")
                        
                        # Read fps
                        if len(d) >= 28:
                            fps = struct.unpack_from("<f", d, 24)[0]
                            print(f"FPS: {fps}")
                        
                        # Read strings
                        if len(d) > 28:
                            # Find null terminator for images path
                            img_end = d.find(0, 28)
                            if img_end > 0:
                                img_path = d[28:img_end].decode("utf-8", errors="replace")
                                print(f"Images path: '{img_path}'")
                                
                                # Audio path
                                aud_end = d.find(0, img_end + 1)
                                if aud_end > 0:
                                    aud_path = d[img_end+1:aud_end].decode("utf-8", errors="replace")
                                    print(f"Audio path: '{aud_path}'")
                                    
                                    # Bones count
                                    bone_count = struct.unpack_from("<i", d, aud_end + 1)[0]
                                    print(f"Bones count: {bone_count}")
                        break
        else:
            print(f"First byte is not 0x1C: 0x{raw_data[0]:02x}")
