#!/usr/bin/env python3
"""
extract_motions.py - 从 Unity AnimationClip 提取真实动作数据到 motion3.json

StreamedClip 格式 (参考 AssetStudio 源码):
    data: uint32[] (包含 sentinel + curveCount + 帧数据)
    
    帧格式:
        time: float (4 bytes)
        numKeys: int (4 bytes)
        对每个 key:
            index: int (4 bytes) -- 曲线索引
            coeff[0]: float -- 未使用
            coeff[1]: float -- 未使用
            coeff[2]: float -- outSlope
            coeff[3]: float -- value (当前值)
"""

import os
import sys
import json
import struct
import argparse
from pathlib import Path
from datetime import datetime

try:
    import UnityPy
except ImportError:
    print("[ERROR] 需要安装 UnityPy: pip install UnityPy")
    sys.exit(1)

LIVE2D_DIR = r"D:\Azur Lane Assets\files\AssetBundles\live2d"
OUTPUT_DIR = r"D:\Azur Lane Assets\Output\Live2D"
ERROR_LOG = r"D:\Azur Lane Assets\ERRORS.log"


def log_error(name, error):
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] [MOTION] {name}: {error}\n")


def read_float(data, offset):
    return struct.unpack_from('<f', data, offset)[0]


def read_int32(data, offset):
    return struct.unpack_from('<i', data, offset)[0]


def parse_streamed_clip(streamed_clip):
    """
    解析 StreamedClip 数据为帧列表
    
    返回:
        [(time, [(curve_index, value, outSlope), ...]), ...]
    """
    raw_uint32 = streamed_clip.data
    if not raw_uint32:
        return []
    
    # 转换为 bytes
    buffer = b''.join(struct.pack('<I', v & 0xFFFFFFFF) for v in raw_uint32)
    
    frames = []
    pos = 0
    
    while pos + 8 <= len(buffer):  # 至少需要 time(4) + numKeys(4)
        time = read_float(buffer, pos)
        pos += 4
        
        # 检查终止符 (+infinity)
        if time == float('inf'):
            break
        
        num_keys = read_int32(buffer, pos)
        pos += 4
        
        # 检查无效数据
        if num_keys < 0 or num_keys > 100:
            break
        
        keys = []
        for _ in range(num_keys):
            if pos + 20 > len(buffer):  # index(4) + 4*float(16) = 20
                break
            index = read_int32(buffer, pos)
            pos += 4
            coeff = []
            for _ in range(4):
                coeff.append(read_float(buffer, pos))
                pos += 4
            
            out_slope = coeff[2]
            value = coeff[3]
            keys.append((index, value, out_slope))
        
        # 跳过负时间帧（初始参考姿态）
        if time < 0:
            continue
        
        # 将极小的时间值视为 0
        if abs(time) < 1e-6:
            time = 0.0
        
        if keys:
            frames.append((time, keys))
    
    return frames


def get_parameter_names(env):
    """
    获取 CubismParameter 名称列表（按绑定顺序）
    """
    params = []
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            data = obj.read()
            script_ref = getattr(data, "m_Script", None)
            if not script_ref:
                continue
            script_obj = script_ref.read()
            script_name = getattr(script_obj, "m_Name", "")
            if "CubismParameter" not in script_name:
                continue
            name = getattr(data, "m_Name", "")
            if not name:
                name = getattr(data, "m_Id", "")
            if name:
                params.append(name)
        except:
            continue
    return params


def extract_motion(env, clip_name, param_names):
    """
    从 AnimationClip 提取动作数据并转换为 motion3.json 格式
    """
    # 找到 AnimationClip
    clip_data = None
    for obj in env.objects:
        if obj.type.name != "AnimationClip":
            continue
        try:
            data = obj.read()
            if getattr(data, "m_Name", "") == clip_name:
                clip_data = data
                break
        except:
            continue
    
    if not clip_data:
        return None
    
    muscle = getattr(clip_data, "m_MuscleClip", None)
    if not muscle:
        return None
    
    clip_ptr = getattr(muscle, "m_Clip", None)
    if not clip_ptr:
        return None
    
    clip_obj = clip_ptr.data
    streamed = getattr(clip_obj, 'm_StreamedClip', None)
    if not streamed:
        return None
    
    # 获取时长
    duration = getattr(muscle, "m_StopTime", 0.0) - getattr(muscle, "m_StartTime", 0.0)
    if duration <= 0:
        duration = 3.0
    
    # 解析 StreamedClip
    frames = parse_streamed_clip(streamed)
    if not frames:
        return None
    
    # 构建曲线数据: curve_index -> [(time, value)]
    curve_data = {}
    for time, keys in frames:
        for curve_idx, value, out_slope in keys:
            if curve_idx not in curve_data:
                curve_data[curve_idx] = []
            curve_data[curve_idx].append((time, value))
    
    # 转换为 motion3.json Curves 格式
    curves = []
    total_segments = 0
    total_points = 0
    
    for curve_idx in sorted(curve_data.keys()):
        keyframes = curve_data[curve_idx]
        if not keyframes:
            continue
        
        # 获取参数名称
        param_name = f"Param_{curve_idx}"
        if curve_idx < len(param_names):
            param_name = param_names[curve_idx]
        
        # 构建 Segments: [time0, value0, type, time1, value1, ...]
        # type 0 = linear interpolation
        segments = []
        for i, (t, v) in enumerate(keyframes):
            if i == 0:
                segments.extend([t, v])
            else:
                segments.extend([0, t, v])
        
        total_segments += len(keyframes)
        total_points += len(keyframes) * 2
        
        curves.append({
            "Target": "Parameter",
            "Id": param_name,
            "Segments": segments
        })
    
    if not curves:
        return None
    
    motion = {
        "Version": 3,
        "Meta": {
            "Duration": round(duration, 3),
            "Fps": 30.0,
            "Loop": bool(getattr(muscle, "m_LoopTime", True)),
            "AreBeziersRestricted": True,
            "CurveCount": len(curves),
            "TotalSegmentCount": total_segments,
            "TotalPointCount": total_points,
            "UserDataCount": 0,
            "TotalUserDataSize": 0
        },
        "Curves": curves,
        "UserData": [],
        "Physics": None
    }
    
    return motion


def process_model(model_name):
    """处理单个模型的所有动作"""
    bundle_path = os.path.join(LIVE2D_DIR, model_name)
    if not os.path.isfile(bundle_path):
        bundle_path = os.path.join(LIVE2D_DIR, model_name + ".bundle")
        if not os.path.isfile(bundle_path):
            return False, "Bundle 文件不存在"
    
    model_dir = os.path.join(OUTPUT_DIR, model_name)
    motion_dir = os.path.join(model_dir, "motion")
    
    if not os.path.isdir(model_dir):
        return False, "输出目录不存在"
    
    try:
        env = UnityPy.load(bundle_path)
    except Exception as e:
        return False, f"加载失败: {e}"
    
    # 获取参数名称
    param_names = get_parameter_names(env)
    
    # 获取所有 AnimationClip 名称
    clip_names = []
    for obj in env.objects:
        if obj.type.name == "AnimationClip":
            try:
                data = obj.read()
                name = getattr(data, "m_Name", "")
                if name:
                    clip_names.append(name)
            except:
                continue
    
    success_count = 0
    fail_count = 0
    
    for clip_name in clip_names:
        motion = extract_motion(env, clip_name, param_names)
        if motion:
            motion_path = os.path.join(motion_dir, f"{clip_name}.motion3.json")
            with open(motion_path, "w", encoding="utf-8") as f:
                json.dump(motion, f, indent=2, ensure_ascii=False)
            success_count += 1
        else:
            fail_count += 1
    
    return True, f"成功: {success_count}, 失败: {fail_count}"


def main():
    parser = argparse.ArgumentParser(description="提取 Live2D 动作数据")
    parser.add_argument("--name", help="指定模型名称")
    parser.add_argument("--test", help="测试模式，只处理一个模型")
    parser.add_argument("--all", action="store_true", help="处理全部模型")
    args = parser.parse_args()
    
    if not os.path.isdir(LIVE2D_DIR):
        print(f"[ERROR] Live2D 目录不存在: {LIVE2D_DIR}")
        return
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if args.test:
        models = [args.test]
    elif args.name:
        models = [args.name]
    elif args.all:
        models = sorted(os.listdir(LIVE2D_DIR))
    else:
        print("[*] 用法:")
        print("  python extract_motions.py --test lingbo")
        print("  python extract_motions.py --name lingbo")
        print("  python extract_motions.py --all")
        return
    
    success_count = 0
    fail_count = 0
    
    for model_name in models:
        model_dir = os.path.join(OUTPUT_DIR, model_name)
        if not os.path.isdir(model_dir):
            continue
        
        success, msg = process_model(model_name)
        if success:
            success_count += 1
            print(f"[+] {model_name}: {msg}")
        else:
            fail_count += 1
            print(f"[-] {model_name}: {msg}")
            log_error(model_name, msg)
    
    print(f"\n{'=' * 40}")
    print(f"[+] 完成! 成功: {success_count}, 失败: {fail_count}")


if __name__ == "__main__":
    main()
