#!/usr/bin/env python3
"""调试 StreamedClip 和 DenseClip 属性"""

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
    
    muscle = getattr(data, "m_MuscleClip", None)
    clip_ptr = getattr(muscle, "m_Clip", None)
    clip_data = clip_ptr.data
    
    sc = getattr(clip_data, 'm_StreamedClip', None)
    dc = getattr(clip_data, 'm_DenseClip', None)
    
    print("=== StreamedClip ===")
    print(f"  type: {type(sc)}")
    all_attrs = [a for a in dir(sc) if not a.startswith('_')]
    print(f"  all attrs: {all_attrs}")
    
    # 尝试获取所有属性值
    for attr in all_attrs:
        try:
            val = getattr(sc, attr)
            if isinstance(val, (list, tuple)):
                print(f"  {attr}: len={len(val)}, first 30: {list(val[:30])}")
            elif isinstance(val, bytes):
                print(f"  {attr}: len={len(val)}, first 30: {list(val[:30])}")
            else:
                print(f"  {attr}: {val}")
        except Exception as e:
            print(f"  {attr}: ERROR {e}")
    
    print("\n=== DenseClip ===")
    print(f"  type: {type(dc)}")
    all_attrs = [a for a in dir(dc) if not a.startswith('_')]
    print(f"  all attrs: {all_attrs}")
    
    for attr in all_attrs:
        try:
            val = getattr(dc, attr)
            if isinstance(val, (list, tuple)):
                print(f"  {attr}: len={len(val)}")
            elif isinstance(val, bytes):
                print(f"  {attr}: len={len(val)}")
            else:
                print(f"  {attr}: {val}")
        except Exception as e:
            print(f"  {attr}: ERROR {e}")
    
    break
