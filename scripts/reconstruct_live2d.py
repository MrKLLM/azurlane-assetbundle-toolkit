#!/usr/bin/env python3
"""
reconstruct_live2d.py - 从 Unity AssetBundle 还原可播放的 Live2D 模型

原理:
    碧蓝航线 Live2D 模型存储在 Unity AssetBundle 中，包含:
    - CubismMoc MonoBehaviour: 包含 .moc3 模型数据（MOC3 魔数在偏移 44 处）
    - Texture2D: 模型贴图
    - TextAsset: .physics3 物理数据
    - AnimationClip: 动作数据（idle, home, login 等）
    - MonoBehaviour: 模型配置（参数、部件等）

用法:
    python reconstruct_live2d.py                    # 还原全部 Live2D
    python reconstruct_live2d.py --name lingbo      # 只还原 lingbo
    python reconstruct_live2d.py --list             # 列出所有 Live2D 模型

输出:
    Output/Live2D/{舰名}/
    ├── {舰名}.model3.json     # 模型配置
    ├── {舰名}.moc3            # 模型二进制
    ├── {舰名}.physics3.json   # 物理数据
    ├── texture_00.png         # 贴图
    ├── texture_01.png
    └── motion/
        ├── idle.motion3.json  # idle 动作
        └── ...
"""

import os
import sys
import json
import argparse
import struct
from pathlib import Path
from datetime import datetime

try:
    import UnityPy
    from UnityPy import config
    config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
except ImportError:
    print("[ERROR] 需要安装 UnityPy: pip install UnityPy")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("[WARN] 未安装 Pillow，贴图将以原始格式导出")

# ============================================================
# 配置
# ============================================================

LIVE2D_DIR = r"D:\Azur Lane Assets\files\AssetBundles\live2d"
OUTPUT_DIR = r"D:\Azur Lane Assets\Output\Live2D"
ERROR_LOG = r"D:\Azur Lane Assets\ERRORS.log"

# moc3 数据在 MonoBehaviour raw_data 中的起始偏移
MOC3_HEADER_SIZE = 44  # Unity 对象头 + CubismMoc 字段


def log_error(name, error):
    """记录错误"""
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] [LIVE2D] {name}: {error}\n")


def extract_moc3(env):
    """
    从 CubismMoc MonoBehaviour 提取 .moc3 数据

    返回:
        bytes 或 None
    """
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue

        data = obj.read()
        script_ref = getattr(data, "m_Script", None)
        if not script_ref:
            continue

        try:
            script_obj = script_ref.read()
            script_name = getattr(script_obj, "m_Name", "")
            if "Moc" not in script_name:
                continue

            # 找到 CubismMoc 实例
            raw = obj.get_raw_data()
            moc3_offset = raw.find(b"MOC3")
            if moc3_offset >= 0:
                return raw[moc3_offset:]

        except Exception:
            continue

    return None


def extract_textures(env):
    """
    提取所有 Texture2D

    返回:
        [(name, PIL.Image), ...]
    """
    textures = []
    for obj in env.objects:
        if obj.type.name != "Texture2D":
            continue

        data = obj.read()
        name = getattr(data, "m_Name", f"texture_{len(textures):02d}")

        try:
            img = data.image
            if img is not None:
                textures.append((name, img))
        except Exception:
            continue

    return textures


def extract_physics(env):
    """
    提取 physics3 数据

    返回:
        bytes 或 None
    """
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue

        data = obj.read()
        name = getattr(data, "m_Name", "")
        if "physics" not in name.lower():
            continue

        script = getattr(data, "m_Script", b"")
        if isinstance(script, str):
            script = script.encode("utf-8")
        if script:
            return script

    return None


def extract_animation_clips(env):
    """
    提取动作列表（名称）

    返回:
        [str, ...]
    """
    clips = []
    for obj in env.objects:
        if obj.type.name != "AnimationClip":
            continue

        data = obj.read()
        name = getattr(data, "m_Name", "")
        if name:
            clips.append(name)

    return clips


def generate_model3_json(name, texture_files, motion_names):
    """
    生成 .model3.json 配置文件

    Live2D Cubism 格式的 model3.json 结构:
    {
        "Version": 3,
        "FileReferences": {
            "Moc": "{name}.moc3",
            "Textures": ["texture_00.png", ...],
            "Physics": "{name}.physics3.json",
            "Motions": {
                "idle": [{"File": "motion/idle.motion3.json"}],
                ...
            }
        },
        "Groups": [...],
        "Parameters": [...]
    }
    """
    model = {
        "Version": 3,
        "FileReferences": {
            "Moc": f"{name}.moc3",
            "Textures": [f"{f}" for f in texture_files],
            "DisplayInfo": {
                "Size": {"Width": 2000, "Height": 2000}
            }
        },
        "Groups": [
            {
                "Target": "Parameter",
                "Name": "AngleX",
                "Id": "AngleX",
                "GroupIds": ["AngleX"]
            },
            {
                "Target": "Parameter",
                "Name": "AngleY",
                "Id": "AngleY",
                "GroupIds": ["AngleY"]
            },
            {
                "Target": "Parameter",
                "Name": "AngleZ",
                "Id": "AngleZ",
                "GroupIds": ["AngleZ"]
            }
        ]
    }

    # 添加物理数据
    if any("physics" in f.lower() for f in os.listdir(".")):
        model["FileReferences"]["Physics"] = f"{name}.physics3.json"

    # 添加动作
    if motion_names:
        motions = {}
        for clip_name in motion_names:
            motions[clip_name] = [{"File": f"motion/{clip_name}.motion3.json"}]
        model["FileReferences"]["Motions"] = motions

    return model


def reconstruct_model(bundle_path, output_dir):
    """
    从单个 AssetBundle 还原 Live2D 模型

    返回:
        (success: bool, error: str)
    """
    bundle_name = os.path.basename(bundle_path)
    name = os.path.splitext(bundle_name)[0]

    model_dir = os.path.join(output_dir, name)
    motion_dir = os.path.join(model_dir, "motion")
    os.makedirs(motion_dir, exist_ok=True)

    try:
        env = UnityPy.load(bundle_path)
    except Exception as e:
        return False, f"加载失败: {e}"

    # 1. 提取 moc3
    moc3_data = extract_moc3(env)
    if moc3_data:
        with open(os.path.join(model_dir, f"{name}.moc3"), "wb") as f:
            f.write(moc3_data)
    else:
        return False, "未找到 moc3 数据"

    # 2. 提取贴图（使用原始 m_Name 保持纹理顺序）
    textures = extract_textures(env)
    texture_files = []
    for tex_name, img in textures:
        filename = f"{tex_name}.png"
        texture_files.append(filename)
        img.save(os.path.join(model_dir, filename), "PNG")

    # 3. 提取物理数据
    physics_data = extract_physics(env)
    if physics_data:
        with open(os.path.join(model_dir, f"{name}.physics3.json"), "wb") as f:
            f.write(physics_data)

    # 4. 提取动作名称
    motion_names = extract_animation_clips(env)

    # 5. 生成 model3.json
    model3 = generate_model3_json(name, texture_files, motion_names)
    with open(os.path.join(model_dir, f"{name}.model3.json"), "w", encoding="utf-8") as f:
        json.dump(model3, f, indent=2, ensure_ascii=False)

    # 6. 生成 motion 占位文件（实际动作数据需要从 AnimationClip 提取）
    for clip_name in motion_names:
        motion_data = {
            "Version": 3,
            "Meta": {
                "Duration": 3.0,
                "Fps": 30.0,
                "Loop": True,
                "AreBeziersRestricted": True,
                "CurveCount": 0,
                "TotalSegmentCount": 0,
                "TotalPointCount": 0,
                "UserDataCount": 0,
                "TotalUserDataSize": 0
            },
            "Curves": [],
            "Segments": [],
            "UserData": [],
            "Physics": None
        }
        with open(os.path.join(motion_dir, f"{clip_name}.motion3.json"), "w") as f:
            json.dump(motion_data, f, indent=2)

    return True, ""


def list_models():
    """列出所有 Live2D 模型"""
    if not os.path.isdir(LIVE2D_DIR):
        print(f"[ERROR] Live2D 目录不存在: {LIVE2D_DIR}")
        return

    models = sorted(os.listdir(LIVE2D_DIR))
    print(f"[*] Live2D 模型列表 ({len(models)} 个):")
    for m in models:
        print(f"  {m}")


def main():
    parser = argparse.ArgumentParser(description="还原 Live2D 模型")
    parser.add_argument("--name", help="指定模型名称（如 lingbo）")
    parser.add_argument("--list", action="store_true", help="列出所有模型")
    parser.add_argument("--all", action="store_true", help="还原全部模型")
    parser.add_argument("--out", help="覆盖输出目录（默认 Output/Live2D）")
    args = parser.parse_args()

    global OUTPUT_DIR
    if args.out:
        OUTPUT_DIR = args.out

    if args.list:
        list_models()
        return

    if not os.path.isdir(LIVE2D_DIR):
        print(f"[ERROR] Live2D 目录不存在: {LIVE2D_DIR}")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 确定要处理的模型
    if args.name:
        models = [args.name]
    elif args.all:
        models = sorted(os.listdir(LIVE2D_DIR))
    else:
        print("[*] 用法:")
        print("  python reconstruct_live2d.py --name lingbo")
        print("  python reconstruct_live2d.py --all")
        print("  python reconstruct_live2d.py --list")
        return

    success_count = 0
    fail_count = 0

    for model_name in models:
        # 跳过已还原的模型
        model_dir = os.path.join(OUTPUT_DIR, model_name)
        model3_path = os.path.join(model_dir, f"{model_name}.model3.json")
        if os.path.isfile(model3_path):
            success_count += 1
            continue

        bundle_path = os.path.join(LIVE2D_DIR, model_name)
        if not os.path.isfile(bundle_path):
            # 尝试加 .bundle 后缀
            bundle_path = os.path.join(LIVE2D_DIR, model_name + ".bundle")
            if not os.path.isfile(bundle_path):
                print(f"[!] 跳过: {model_name} (文件不存在)")
                fail_count += 1
                continue

        success, error = reconstruct_model(bundle_path, OUTPUT_DIR)

        if success:
            success_count += 1
            print(f"[+] {model_name} 还原成功")
        else:
            fail_count += 1
            print(f"[-] {model_name} 还原失败: {error}")
            log_error(model_name, error)

    print(f"\n{'=' * 40}")
    print(f"[+] 完成! 成功: {success_count}, 失败: {fail_count}")
    print(f"[*] 输出: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
