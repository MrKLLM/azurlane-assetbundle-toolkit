#!/usr/bin/env python3
"""检查 UnityPy StreamedClip 的内置方法"""

import os
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
    
    # 检查 StreamedClip 的所有方法
    print("StreamedClip methods:")
    for attr in dir(sc):
        if not attr.startswith('_'):
            val = getattr(sc, attr)
            if callable(val):
                print(f"  {attr}()")
    
    # 检查 AnimationClip 的所有方法
    print("\nAnimationClip methods:")
    for attr in dir(data):
        if not attr.startswith('_'):
            val = getattr(data, attr)
            if callable(val):
                print(f"  {attr}()")
    
    # 检查是否有 decode 或 parse 方法
    print("\nTrying to find decode methods:")
    for attr in dir(sc):
        if 'decode' in attr.lower() or 'parse' in attr.lower() or 'read' in attr.lower():
            print(f"  Found: {attr}")
