#!/usr/bin/env python3
"""调试 StreamedClip 数据格式"""

import os
import struct
import UnityPy

BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\live2d\lingbo"

env = UnityPy.load(BUNDLE)

# 找 idle AnimationClip
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
    
    clip_obj = getattr(muscle, "m_Clip", None)
    if not clip_obj:
        print("No m_Clip")
        continue
    
    streamed = getattr(clip_obj, "m_StreamedClip", None)
    if not streamed:
        print("No m_StreamedClip")
        continue
    
    print(f"curveCount: {streamed.curveCount}")
    print(f"data length: {len(streamed.data)}")
    print(f"discreteCurveCount: {streamed.discreteCurveCount}")
    
    # 打印前 100 个 uint32 值
    print(f"\nFirst 100 uint32 values:")
    for i, val in enumerate(streamed.data[:100]):
        fval = struct.unpack('f', struct.pack('I', val & 0xFFFFFFFF))[0]
        print(f"  [{i:4d}] {val:10d} (0x{val:08X}) -> float: {fval:.6e}")
    
    # 打印常量值
    constant = getattr(clip_obj, "m_ConstantClip", None)
    if constant and hasattr(constant, 'data'):
        print(f"\nConstantClip ({len(constant.data)} values):")
        for i, val in enumerate(constant.data):
            fval = struct.unpack('f', struct.pack('I', val & 0xFFFFFFFF))[0] if isinstance(val, int) else val
            print(f"  [{i:2d}] {fval:.6f}")
    
    # 检查 DenseClip
    dense = getattr(clip_obj, "m_DenseClip", None)
    if dense:
        print(f"\nDenseClip: curveCount={dense.curveCount}, frameCount={dense.frameCount}")
        if hasattr(dense, 'sampleArray'):
            print(f"  sampleArray length: {len(dense.sampleArray)}")
    
    # 检查 muscle clip 的其他字段
    print(f"\nm_CycleOffset: {muscle.m_CycleOffset}")
    print(f"m_StartTime: {muscle.m_StartTime}")
    print(f"m_StopTime: {muscle.m_StopTime}")
    print(f"m_LoopTime: {muscle.m_LoopTime}")
    
    # 检查 binding
    binding = getattr(data, "m_ClipBindingConstant", None)
    if binding:
        generic = getattr(binding, "genericBindings", [])
        print(f"\nBindings: {len(generic)}")
        for i, b in enumerate(generic[:10]):
            print(f"  [{i}] attribute={b.attribute}, typeID={b.typeID}, script={b.script}")
    
    break
