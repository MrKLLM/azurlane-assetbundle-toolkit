#!/usr/bin/env python3
"""
fix_painting.py — 修复立绘合成方案
根本原因调查 + 多种提取方法对比

核心发现：Texture2D 是压缩纹理，需要正确解码
"""

import UnityPy
from PIL import Image
import os
import sys
import json

PAINTING_DIR = r"D:\Azur Lane Assets\files\AssetBundles\painting"
RAW_DIR = r"D:\Azur Lane Assets\Output\Raw\painting"
OUTPUT_DIR = r"D:\Azur Lane Assets\Output\Paintings_Synthesized"
TEST_DIR = r"D:\Azur Lane Assets\Output\painting_test_methods"
os.makedirs(TEST_DIR, exist_ok=True)

def deep_inspect_bundle(tex_name):
    """深度检查 bundle 内部结构"""
    bundle_path = os.path.join(PAINTING_DIR, tex_name)
    base_name = tex_name.replace("_tex", "")
    
    print(f"\n{'='*60}")
    print(f"Bundle: {tex_name}")
    print(f"{'='*60}")
    
    env = UnityPy.load(bundle_path)
    
    results = {}
    
    for obj in env.objects:
        data = obj.read()
        t = obj.type.name
        
        if t == "Texture2D":
            img = data.image
            fmt = getattr(data, "m_TextureFormat", None)
            name = getattr(data, "m_Name", "?")
            
            print(f"\n  Texture2D: {name}")
            print(f"    size: {img.size}, mode: {img.mode}")
            print(f"    format: {fmt}")
            
            # Save full texture
            out = os.path.join(TEST_DIR, f"{base_name}_full_texture.png")
            img.save(out, "PNG")
            print(f"    Saved full texture: {out}")
            
            results["texture"] = img
            
            # Try to get raw data for format analysis
            try:
                # Access internal data
                raw_data = data.get_raw_data()
                print(f"    Raw data size: {len(raw_data)} bytes")
                print(f"    First 64 bytes hex: {raw_data[:64].hex()}")
                
                # Check for ASTC magic
                if b'\x13\xAB\xA1\x5C' in raw_data[:100]:
                    print(f"    ASTC magic found!")
                elif b'\x5C\xA1\xAB\x13' in raw_data[:100]:
                    print(f"    ASTC magic found (reversed)!")
                    
            except Exception as e:
                print(f"    Raw data access failed: {e}")
        
        elif t == "Sprite":
            name = getattr(data, "m_Name", "?")
            print(f"\n  Sprite: {name}")
            print(f"    m_Rect: {data.m_Rect}")
            
            # Check all Sprite attributes
            for attr in dir(data):
                if attr.startswith('m_'):
                    try:
                        val = getattr(data, attr)
                        if not callable(val) and val is not None:
                            print(f"    {attr}: {val}")
                    except:
                        pass
            
            # Try Sprite.image
            try:
                sp_img = data.image
                if sp_img:
                    print(f"    Sprite.image: {sp_img.size} {sp_img.mode}")
                    
                    # Save sprite image
                    out = os.path.join(TEST_DIR, f"{base_name}_sprite_{name}.png")
                    sp_img.save(out, "PNG")
                    print(f"    Saved sprite: {out}")
                    
                    # Compare with texture
                    if "texture" in results:
                        tex = results["texture"]
                        if sp_img.size != tex.size:
                            print(f"    DIFFERENT SIZE: sprite={sp_img.size} vs texture={tex.size}")
                            # Check if sprite is a crop of texture
                            tex_data = list(tex.getdata())
                            sp_data = list(sp_img.getdata())
                            # Check if first pixel matches
                            print(f"    Texture[0,0]: {tex_data[0]}")
                            print(f"    Sprite[0,0]: {sp_data[0]}")
                            
            except Exception as e:
                print(f"    Sprite.image ERROR: {e}")
        
        elif t == "Mesh":
            name = getattr(data, "m_Name", "?")
            verts = getattr(data, "vertices", [])
            uvs = getattr(data, "uv", [])
            print(f"\n  Mesh: {name}")
            print(f"    vertices: {len(verts)}")
            print(f"    uv: {len(uvs)}")
            
            if verts:
                print(f"    vertex[0]: {verts[0]}")
            if uvs:
                print(f"    uv[0]: {uvs[0]}")
    
    return results


def compare_methods(tex_name):
    """对比不同提取方法"""
    base_name = tex_name.replace("_tex", "")
    
    # Method 1: Current approach (Texture2D.image + Sprite.m_Rect crop)
    print(f"\n--- Method 1: Texture2D + m_Rect crop ---")
    env = UnityPy.load(os.path.join(PAINTING_DIR, tex_name))
    for obj in env.objects:
        data = obj.read()
        if obj.type.name == "Texture2D":
            tex = data.image
            out = os.path.join(TEST_DIR, f"{base_name}_m1_texture2d.png")
            tex.save(out, "PNG")
            print(f"  Saved: {out} ({tex.size})")
            break
    
    # Method 2: Sprite.image (UnityPy's built-in)
    print(f"\n--- Method 2: Sprite.image ---")
    env = UnityPy.load(os.path.join(PAINTING_DIR, tex_name))
    for obj in env.objects:
        data = obj.read()
        if obj.type.name == "Sprite":
            try:
                sp = data.image
                if sp:
                    out = os.path.join(TEST_DIR, f"{base_name}_m2_sprite.png")
                    sp.save(out, "PNG")
                    print(f"  Saved: {out} ({sp.size})")
            except Exception as e:
                print(f"  Error: {e}")
            break
    
    # Method 3: Raw export comparison
    print(f"\n--- Method 3: Raw export ---")
    raw_path = os.path.join(RAW_DIR, f"{base_name}.png")
    if os.path.isfile(raw_path):
        raw = Image.open(raw_path)
        print(f"  Raw: {raw.size} {raw.mode}")
    else:
        print(f"  Raw not found: {raw_path}")
    
    # Method 4: Try to extract raw texture bytes and decode manually
    print(f"\n--- Method 4: Raw bytes analysis ---")
    env = UnityPy.load(os.path.join(PAINTING_DIR, tex_name))
    for obj in env.objects:
        data = obj.read()
        if obj.type.name == "Texture2D":
            fmt = getattr(data, "m_TextureFormat", None)
            print(f"  Format code: {fmt}")
            
            # Format codes:
            # 48 = ASTC_RGBA_4x4
            # 49 = ASTC_RGBA_5x5
            # 50 = ASTC_RGBA_6x6
            # 51 = ASTC_RGBA_8x8
            # 63 = ETC2_RGBA8
            # 64 = ETC2_RGBA1
            # 41 = DXT5
            
            format_names = {
                41: "DXT5", 42: "DXT3", 43: "DXT1",
                48: "ASTC_RGBA_4x4", 49: "ASTC_RGBA_5x5",
                50: "ASTC_RGBA_6x6", 51: "ASTC_RGBA_8x8",
                63: "ETC2_RGBA8", 64: "ETC2_RGBA1",
            }
            print(f"  Format name: {format_names.get(fmt, f'Unknown({fmt})')}")
            break


# Run diagnostics on test bundles
for name in ["lingbo_tex", "qiye_tex", "chicheng_tex"]:
    deep_inspect_bundle(name)
    compare_methods(name)
