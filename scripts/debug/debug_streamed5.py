#!/usr/bin/env python3
"""解码 StreamedClip 数据"""

import os
import struct
import UnityPy

BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\live2d\lingbo"

env = UnityPy.load(BUNDLE)

def uint32_to_float(val):
    return struct.unpack('f', struct.pack('I', val & 0xFFFFFFFF))[0]

for obj in env.objects:
    if obj.type.name != "AnimationClip":
        continue
    data = obj.read()
    if getattr(data, "m_Name", "") != "idle":
        continue
    
    muscle = getattr(data, "m_MuscleClip", None)
    clip_ptr = getattr(muscle, "m_Clip", None)
    clip_data = clip_ptr.data
    sc = getattr(clip_data, 'm_StreamedClip', None)
    
    raw = sc.data
    print(f"Total uint32 values: {len(raw)}")
    
    # 跳过哨兵和 curveCount
    i = 2  # skip 0xFF7FFFFF and curveCount=15
    
    print("\nDecoding frames:")
    frame_count = 0
    while i < len(raw) and frame_count < 20:
        # 读取时间
        time_raw = raw[i]
        i += 1
        
        # 检查终止符
        if time_raw == 0x7F800000:
            print(f"  TERMINATOR at index {i-1}")
            break
        
        time = uint32_to_float(time_raw)
        
        # 读取曲线数量
        if i >= len(raw):
            break
        num_curves = raw[i]
        i += 1
        
        print(f"  Frame {frame_count}: time={time:.6f} ({time_raw}=0x{time_raw:08X}), numCurves={num_curves}")
        
        # 读取曲线数据
        for c in range(num_curves):
            if i + 1 >= len(raw):
                break
            curve_idx = raw[i]
            i += 1
            value_raw = raw[i]
            i += 1
            value = uint32_to_float(value_raw)
            print(f"    curve[{curve_idx}] = {value:.6f} ({value_raw}=0x{value_raw:08X})")
        
        frame_count += 1
    
    print(f"\nDecoded {frame_count} frames, stopped at index {i}/{len(raw)}")
