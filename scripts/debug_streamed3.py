#!/usr/bin/env python3
"""调试 OffsetPtr.data 结构"""

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
    clip_ptr = getattr(muscle, "m_Clip", None)
    
    print(f"clip_ptr type: {type(clip_ptr)}")
    print(f"clip_ptr.data type: {type(clip_ptr.data)}")
    
    clip_data = clip_ptr.data
    print(f"clip_data attrs: {[a for a in dir(clip_data) if not a.startswith('_')]}")
    
    # 检查 StreamedClip
    sc = getattr(clip_data, 'm_StreamedClip', None)
    if sc:
        print(f"\nStreamedClip type: {type(sc)}")
        if hasattr(sc, '__dict__'):
            print(f"StreamedClip attrs: {[a for a in dir(sc) if not a.startswith('_')]}")
            for attr in ['curveCount', 'data', 'discreteCurveCount']:
                val = getattr(sc, attr, 'NOT_FOUND')
                if isinstance(val, (list, tuple)):
                    print(f"  {attr}: len={len(val)}, first 20: {list(val[:20])}")
                else:
                    print(f"  {attr}: {val}")
    
    # 检查 DenseClip
    dc = getattr(clip_data, 'm_DenseClip', None)
    if dc:
        print(f"\nDenseClip type: {type(dc)}")
        if hasattr(dc, '__dict__'):
            print(f"DenseClip attrs: {[a for a in dir(dc) if not a.startswith('_')]}")
            for attr in ['curveCount', 'frameCount', 'sampleArray']:
                val = getattr(dc, attr, 'NOT_FOUND')
                if isinstance(val, (list, tuple)):
                    print(f"  {attr}: len={len(val)}")
                else:
                    print(f"  {attr}: {val}")
    
    # 检查 ConstantClip
    cc = getattr(clip_data, 'm_ConstantClip', None)
    if cc:
        print(f"\nConstantClip type: {type(cc)}")
        if hasattr(cc, 'data'):
            print(f"  data: {list(cc.data)}")
    
    break
