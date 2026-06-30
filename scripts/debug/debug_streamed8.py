#!/usr/bin/env python3
"""检查 AnimationClip 原始字节数据"""

import os
import struct
import UnityPy

BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\live2d\lingbo"

env = UnityPy.load(BUNDLE)

for obj in env.objects:
    if obj.type.name != "AnimationClip":
        continue
    data = obj.read()
    if getattr(data, "m_Name", "") != "idle":
        continue
    
    # 获取原始数据
    raw = obj.get_raw_data()
    print(f"Raw data size: {len(raw)} bytes")
    
    # 打印前 200 字节的十六进制
    print("\nFirst 200 bytes hex:")
    for i in range(0, min(200, len(raw)), 16):
        hex_str = ' '.join(f'{b:02X}' for b in raw[i:i+16])
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in raw[i:i+16])
        print(f"  {i:04X}: {hex_str}  {ascii_str}")
    
    # 搜索 MOC3 魔数
    moc3_pos = raw.find(b'MOC3')
    print(f"\nMOC3 magic at offset: {moc3_pos}")
    
    # 搜索其他可能的标志
    for pattern in [b'curve', b'motion', b'anim', b'clip']:
        pos = raw.find(pattern)
        if pos >= 0:
            print(f"'{pattern.decode()}' found at offset: {pos}")
