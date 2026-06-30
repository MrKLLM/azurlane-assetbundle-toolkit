#!/usr/bin/env python3
"""检查解析后的帧数据"""

import os
import struct
import UnityPy

BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\live2d\lingbo"

env = UnityPy.load(BUNDLE)

def read_float(data, offset):
    return struct.unpack_from('<f', data, offset)[0]

def read_int32(data, offset):
    return struct.unpack_from('<i', data, offset)[0]

for obj in env.objects:
    if obj.type.name != "AnimationClip":
        continue
    data = obj.read()
    if getattr(data, "m_Name", "") != "idle":
        continue
    
    muscle = getattr(data, "m_MuscleClip", None)
    clip_ptr = getattr(muscle, "m_Clip", None)
    clip_obj = clip_ptr.data
    streamed = getattr(clip_obj, 'm_StreamedClip', None)
    
    raw_uint32 = streamed.data
    buffer = b''.join(struct.pack('<I', v & 0xFFFFFFFF) for v in raw_uint32)
    
    print(f"Buffer size: {len(buffer)} bytes")
    
    # 解析前 5 帧
    pos = 0
    for frame_idx in range(5):
        if pos + 8 > len(buffer):
            break
        
        time = read_float(buffer, pos)
        pos += 4
        
        num_keys = read_int32(buffer, pos)
        pos += 4
        
        print(f"\nFrame {frame_idx}: time={time}, numKeys={num_keys}")
        
        for i in range(min(num_keys, 5)):
            if pos + 20 > len(buffer):
                break
            index = read_int32(buffer, pos)
            pos += 4
            coeff = []
            for _ in range(4):
                coeff.append(read_float(buffer, pos))
                pos += 4
            print(f"  Key {i}: index={index}, coeff={[f'{c:.4f}' for c in coeff]}")
    
    break
