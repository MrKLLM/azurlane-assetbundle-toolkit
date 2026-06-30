#!/usr/bin/env python3
"""调试 m_Clip 对象结构"""

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
    
    print(f"=== Clip: {data.m_Name} ===")
    
    muscle = getattr(data, "m_MuscleClip", None)
    if not muscle:
        print("No m_MuscleClip")
        continue
    
    print(f"m_MuscleClip type: {type(muscle)}")
    print(f"m_MuscleClip attrs: {[a for a in dir(muscle) if not a.startswith('_')]}")
    
    clip_obj = getattr(muscle, "m_Clip", None)
    if not clip_obj:
        print("No m_Clip")
        continue
    
    print(f"\nm_Clip type: {type(clip_obj)}")
    print(f"m_Clip attrs: {[a for a in dir(clip_obj) if not a.startswith('_')]}")
    
    # 尝试直接访问属性
    for attr in ['m_StreamedClip', 'm_DenseClip', 'm_ConstantClip', 'm_Binding']:
        val = getattr(clip_obj, attr, 'NOT_FOUND')
        print(f"  {attr}: {type(val)} = {val if not hasattr(val, '__len__') or len(val) < 100 else f'<len={len(val)}>'}")
    
    # 如果 m_StreamedClip 是嵌套对象，检查它的属性
    sc = getattr(clip_obj, 'm_StreamedClip', None)
    if sc and hasattr(sc, '__dict__'):
        print(f"\nStreamedClip attrs: {[a for a in dir(sc) if not a.startswith('_')]}")
        for attr in ['curveCount', 'data', 'discreteCurveCount']:
            val = getattr(sc, attr, 'NOT_FOUND')
            if isinstance(val, (list, tuple)):
                print(f"  {attr}: len={len(val)}")
            else:
                print(f"  {attr}: {val}")
    
    break
