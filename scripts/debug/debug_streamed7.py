#!/usr/bin/env python3
"""检查 m_ValueArrayDelta 和其他可用数据"""

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
    
    print("=== m_MuscleClip ===")
    print(f"m_ValueArrayDelta type: {type(muscle.m_ValueArrayDelta)}")
    print(f"m_ValueArrayDelta len: {len(muscle.m_ValueArrayDelta)}")
    
    # 检查 ValueDelta 结构
    if muscle.m_ValueArrayDelta:
        vad = muscle.m_ValueArrayDelta[0]
        print(f"\nFirst ValueDelta type: {type(vad)}")
        print(f"First ValueDelta attrs: {[a for a in dir(vad) if not a.startswith('_')]}")
        for attr in dir(vad):
            if not attr.startswith('_'):
                val = getattr(vad, attr)
                print(f"  {attr}: {val}")
    
    # 检查 m_ValueArrayReferencePose
    print(f"\nm_ValueArrayReferencePose type: {type(muscle.m_ValueArrayReferencePose)}")
    print(f"m_ValueArrayReferencePose len: {len(muscle.m_ValueArrayReferencePose)}")
    if muscle.m_ValueArrayReferencePose:
        print(f"  first 10: {list(muscle.m_ValueArrayReferencePose[:10])}")
    
    # 检查 m_IndexArray
    print(f"\nm_IndexArray type: {type(muscle.m_IndexArray)}")
    print(f"m_IndexArray len: {len(muscle.m_IndexArray)}")
    print(f"  first 20: {list(muscle.m_IndexArray[:20])}")
    
    # 检查 binding
    binding = getattr(data, "m_ClipBindingConstant", None)
    if binding:
        generic = getattr(binding, "genericBindings", [])
        print(f"\nBindings: {len(generic)}")
        for i, b in enumerate(generic):
            print(f"  [{i}] attribute={b.attribute}, typeID={b.typeID}, path={b.path}")
    
    break
