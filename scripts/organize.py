#!/usr/bin/env python3
"""
organize.py — 将 Output/Raw/ 中导出的资源按类型分类整理到 Output/ 目录

用法:
    python organize.py

输出目录结构:
    Output/
    ├── Paintings/           # 立绘（按舰名/皮肤分类）
    │   ├── 企业/
    │   │   ├── 默认.png
    │   │   ├── 2_誓约.png
    │   │   └── 3_婚纱.png
    │   └── ...
    ├── Backgrounds/         # 背景图
    │   ├── Scene/           # 场景背景
    │   ├── Common/          # 通用背景
    │   └── Loading/         # 加载背景
    ├── Live2D/              # Live2D 模型
    ├── Spine/               # Spine 动画
    ├── UI/                  # UI 资源
    ├── Icons/               # 图标
    ├── Audio/               # 音频
    │   ├── BGM/
    │   ├── SE/
    │   └── CV/
    ├── Characters/          # 角色资产
    ├── Effects/             # 特效
    └── Others/              # 其他
"""

import os
import re
import shutil
import json
from pathlib import Path
from collections import defaultdict

# ============================================================
# 配置区域
# ============================================================

# Raw 导出目录（AssetStudio 导出到这里）
RAW_DIR = r"D:\Azur Lane Assets\Output\Raw"

# 整理后的输出目录
OUTPUT_DIR = r"D:\Azur Lane Assets\Output"

# 立绘文件名映射（舰名拼音 → 中文名）
# 这个映射需要根据实际情况补充
SHIP_NAME_MAP = {
    "aidang": "爱宕",
    "chicheng": "赤城",
    "jiahe": "加贺",
    "zhihuiguan": "指挥官",
    "lingbo": "凌波",
    "z23": "Z23",
    "qiye": "企业",
    "xinnong": "信浓",
    "yuekecheng": "约克城",
    "dafeng": "大凤",
    "aerjiliya": "阿尔及利亚",
    "bisimai": "俾斯麦",
    "shengluyisi": "圣路易斯",
    "huangjiafangzhou": "皇家方舟",
    "guanghui": "光辉",
    "jianye": "翔鹤",
    "gaoxiong": "高雄",
    "tianlangxing": "天狼星",
    "ougen": "欧根亲王",
    "baiyanjuren": "白盐巨人",
    "nengdai": "能代",
    "aijier": "阿基尔",
    "weixi": "威悉",
    "lafei": "拉菲",
    "xuefeng": "雪风",
    "linuo": "利托里奥",
    "feiteliedadi": "斐特烈大帝",
    "kelaimengsuo": "克莱蒙梭",
    "kubo": "久保",
    "qingxing": "清空",
    "changmen": "长门",
    "yingrui": "萤火虫",
    "weizhang": "威尔士亲王",
    "wuerlixi": "乌尔里希·冯·胡滕",
    "kelifulan": "科隆",
    "zhala": "扎拉",
    "yanusi": "雅努斯",
    "yichui": "伊吹",
    "dewenjun": "德文郡",
    "tiancheng": "天城",
    "zhangfei": "张飞",
    "zhangwu": "张武",
    "shengluyisi": "圣路易斯",
    "junhe": "君河",
    "junzhu": "郡主",
    "liyiman": "黎塞留",
    "qianjian": "前卫",
    "jiuyun": "加贺",
    "xingdengbao": "兴登堡",
    "mingji": "鸣门",
    "mingshi": "明石",
    "xiafei": "霞飞",
    "xianghe": "翔鹤",
    "xukufu": "库库富",
    "yuanchou": "怨仇",
    "yunxian": "云仙",
    "zengkehaijunshangjiang": "曾克海军上将",
}

# 皮肤名称映射（后缀 → 中文名）
SKIN_NAME_MAP = {
    "": "默认",
    "alter": "改造",
    "hei": "黑化",
    "idol": "偶像",
    "younv": "幼年",
    "memory": "回忆",
    "g": "G",
    "h": "H",
    "dark_shadow": "暗影",
    "wjz": "特殊",
    "rank": "竞技",
    "ex": "EX",
    "asmr": "ASMR",
}

# 皮肤编号 → 常见皮肤名（需要根据实际情况补充）
SKIN_NUMBER_MAP = {
    "2": "2",
    "3": "3",
    "4": "4",
    "5": "5",
    "6": "6",
    "7": "7",
    "8": "8",
    "9": "9",
    "10": "10",
}


def get_chinese_name(ship_pinyin):
    """获取舰名的中文名"""
    return SHIP_NAME_MAP.get(ship_pinyin, ship_pinyin)


def parse_painting_filename(filename):
    """
    解析立绘文件名

    返回:
        (ship_pinyin, skin_number, variant, is_texture)
    """
    name = filename
    is_texture = "_tex" in name

    # 移除 .png 后缀（导出后可能有）
    name = name.replace(".png", "").replace(".tga", "")

    # 移除 _tex 后缀
    base = name.replace("_tex", "")

    # 匹配皮肤编号
    match = re.match(r"^(.+?)_(\d+)(.*)$", base)
    if match:
        ship = match.group(1)
        skin_num = match.group(2)
        variant = match.group(3).lstrip("_")
    else:
        ship = base
        skin_num = ""
        variant = ""

    return ship, skin_num, variant, is_texture


def get_skin_display_name(skin_num, variant):
    """生成皮肤显示名"""
    parts = []

    if skin_num:
        skin_name = SKIN_NUMBER_MAP.get(skin_num, skin_num)
        parts.append(skin_name)

    if variant:
        variant_name = SKIN_NAME_MAP.get(variant, variant)
        parts.append(variant_name)

    return "_".join(parts) if parts else "默认"


def organize_paintings(raw_dir, output_dir):
    """整理立绘资源"""
    painting_raw = os.path.join(raw_dir, "painting")
    if not os.path.isdir(painting_raw):
        print(f"    [!] 立绘 Raw 目录不存在: {painting_raw}")
        return

    paintings_output = os.path.join(output_dir, "Paintings")
    os.makedirs(paintings_output, exist_ok=True)

    # 统计
    stats = defaultdict(int)

    for filename in os.listdir(painting_raw):
        filepath = os.path.join(painting_raw, filename)
        if not os.path.isfile(filepath):
            continue

        # 只处理 Texture2D 导出的图片
        if not any(filename.endswith(ext) for ext in [".png", ".tga", ".jpeg", ".bmp"]):
            continue

        # 解析文件名
        ship, skin_num, variant, _ = parse_painting_filename(filename)

        # 获取舰名中文名
        chinese_name = get_chinese_name(ship)

        # 皮肤显示名
        skin_display = get_skin_display_name(skin_num, variant)

        # 目标路径: Output/Paintings/企业/2_誓约.png
        ship_dir = os.path.join(paintings_output, chinese_name)
        os.makedirs(ship_dir, exist_ok=True)

        ext = os.path.splitext(filename)[1] or ".png"
        target_name = f"{skin_display}{ext}"
        target_path = os.path.join(ship_dir, target_name)

        # 处理重名
        if os.path.exists(target_path):
            base, ext = os.path.splitext(target_path)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            target_path = f"{base}_{counter}{ext}"

        # 复制文件
        shutil.copy2(filepath, target_path)
        stats[chinese_name] += 1

    print(f"[+] 立绘整理完成: {sum(stats.values())} 个文件")
    for name, count in sorted(stats.items(), key=lambda x: -x[1])[:10]:
        print(f"    {name}: {count} 个皮肤")


def organize_by_extension(raw_dir, output_dir, target_exts, output_name):
    """
    按文件扩展名整理资源

    参数:
        raw_dir: Raw 源目录
        output_dir: 输出根目录
        target_exts: 目标扩展名列表
        output_name: 输出子目录名
    """
    if not os.path.isdir(raw_dir):
        print(f"    [!] Raw 目录不存在: {raw_dir}")
        return

    target_dir = os.path.join(output_dir, output_name)
    os.makedirs(target_dir, exist_ok=True)

    count = 0
    for filename in os.listdir(raw_dir):
        filepath = os.path.join(raw_dir, filename)
        if not os.path.isfile(filepath):
            continue

        ext = os.path.splitext(filename)[1].lower()
        if ext in target_exts:
            shutil.copy2(filepath, os.path.join(target_dir, filename))
            count += 1

    print(f"[+] {output_name} 整理完成: {count} 个文件")


def organize_backgrounds(raw_dir, output_dir):
    """整理背景资源"""
    bg_output = os.path.join(output_dir, "Backgrounds")
    os.makedirs(bg_output, exist_ok=True)

    # 场景背景
    scene_raw = os.path.join(raw_dir, "bg")
    if os.path.isdir(scene_raw):
        scene_dir = os.path.join(bg_output, "Scene")
        os.makedirs(scene_dir, exist_ok=True)
        count = 0
        for f in os.listdir(scene_raw):
            fp = os.path.join(scene_raw, f)
            if os.path.isfile(fp) and f.endswith((".png", ".tga", ".jpeg", ".bmp")):
                shutil.copy2(fp, os.path.join(scene_dir, f))
                count += 1
        print(f"[+] 场景背景: {count} 个")

    # 通用背景
    common_raw = os.path.join(raw_dir, "commonbg")
    if os.path.isdir(common_raw):
        common_dir = os.path.join(bg_output, "Common")
        os.makedirs(common_dir, exist_ok=True)
        count = 0
        for f in os.listdir(common_raw):
            fp = os.path.join(common_raw, f)
            if os.path.isfile(fp) and f.endswith((".png", ".tga", ".jpeg", ".bmp")):
                shutil.copy2(fp, os.path.join(common_dir, f))
                count += 1
        print(f"[+] 通用背景: {count} 个")

    # 加载背景
    for loading_dir_name in ["loadingbg", "loadingbg_hx"]:
        loading_raw = os.path.join(raw_dir, loading_dir_name)
        if os.path.isdir(loading_raw):
            suffix = "_HX" if "hx" in loading_dir_name else ""
            loading_output = os.path.join(bg_output, f"Loading{suffix}")
            os.makedirs(loading_output, exist_ok=True)
            count = 0
            for f in os.listdir(loading_raw):
                fp = os.path.join(loading_raw, f)
                if os.path.isfile(fp) and f.endswith((".png", ".tga", ".jpeg", ".bmp")):
                    shutil.copy2(fp, os.path.join(loading_output, f))
                    count += 1
            print(f"[+] 加载背景{suffix}: {count} 个")

    # 帮助背景
    help_raw = os.path.join(raw_dir, "helpbg")
    if os.path.isdir(help_raw):
        help_output = os.path.join(bg_output, "Help")
        os.makedirs(help_output, exist_ok=True)
        count = 0
        for f in os.listdir(help_raw):
            fp = os.path.join(help_raw, f)
            if os.path.isfile(fp) and f.endswith((".png", ".tga", ".jpeg", ".bmp")):
                shutil.copy2(fp, os.path.join(help_output, f))
                count += 1
        print(f"[+] 帮助背景: {count} 个")


def organize_audio(raw_dir, output_dir):
    """整理音频资源"""
    cue_raw = os.path.join(raw_dir, "cue")
    if not os.path.isdir(cue_raw):
        print(f"    [!] 音频 Raw 目录不存在: {cue_raw}")
        return

    audio_output = os.path.join(output_dir, "Audio")
    os.makedirs(audio_output, exist_ok=True)

    stats = {"BGM": 0, "SE": 0, "CV": 0, "Other": 0}

    for filename in os.listdir(cue_raw):
        filepath = os.path.join(cue_raw, filename)
        if not os.path.isfile(filepath):
            continue

        # 按前缀分类
        if filename.startswith("bgm-") or filename.startswith("bgm_"):
            subdir = "BGM"
        elif filename.startswith("se-") or filename.startswith("se_"):
            subdir = "SE"
        elif filename.startswith("cv-") or filename.startswith("cv_"):
            subdir = "CV"
        else:
            subdir = "Other"

        target_dir = os.path.join(audio_output, subdir)
        os.makedirs(target_dir, exist_ok=True)

        shutil.copy2(filepath, os.path.join(target_dir, filename))
        stats[subdir] += 1

    print(f"[+] 音频整理完成:")
    for subdir, count in stats.items():
        if count > 0:
            print(f"    {subdir}: {count} 个")


def organize_live2d(raw_dir, output_dir):
    """整理 Live2D 资源"""
    live2d_raw = os.path.join(raw_dir, "live2d")
    if not os.path.isdir(live2d_raw):
        print(f"    [!] Live2D Raw 目录不存在: {live2d_raw}")
        return

    live2d_output = os.path.join(output_dir, "Live2D")
    os.makedirs(live2d_output, exist_ok=True)

    count = 0
    for filename in os.listdir(live2d_raw):
        filepath = os.path.join(live2d_raw, filename)
        if os.path.isfile(filepath):
            shutil.copy2(filepath, os.path.join(live2d_output, filename))
            count += 1

    print(f"[+] Live2D 整理完成: {count} 个文件")


def organize_spine(raw_dir, output_dir):
    """整理 Spine 资源"""
    spine_raw = os.path.join(raw_dir, "spinepainting")
    if not os.path.isdir(spine_raw):
        print(f"    [!] Spine Raw 目录不存在: {spine_raw}")
        return

    spine_output = os.path.join(output_dir, "Spine")
    os.makedirs(spine_output, exist_ok=True)

    count = 0
    for filename in os.listdir(spine_raw):
        filepath = os.path.join(spine_raw, filename)
        if os.path.isfile(filepath):
            shutil.copy2(filepath, os.path.join(spine_output, filename))
            count += 1

    print(f"[+] Spine 整理完成: {count} 个文件")


def organize_ui(raw_dir, output_dir):
    """整理 UI 资源"""
    ui_raw = os.path.join(raw_dir, "ui")
    if not os.path.isdir(ui_raw):
        print(f"    [!] UI Raw 目录不存在: {ui_raw}")
        return

    ui_output = os.path.join(output_dir, "UI")
    os.makedirs(ui_output, exist_ok=True)

    count = 0
    for filename in os.listdir(ui_raw):
        filepath = os.path.join(ui_raw, filename)
        if os.path.isfile(filepath) and filename.endswith((".png", ".tga", ".jpeg", ".bmp")):
            shutil.copy2(filepath, os.path.join(ui_output, filename))
            count += 1

    print(f"[+] UI 整理完成: {count} 个文件")


def organize_icons(raw_dir, output_dir):
    """整理图标资源"""
    icons_output = os.path.join(output_dir, "Icons")
    os.makedirs(icons_output, exist_ok=True)

    count = 0
    # 遍历所有 icon 相关目录
    for dirname in os.listdir(raw_dir):
        if "icon" in dirname.lower() or dirname in ["enemies", "emoji"]:
            src = os.path.join(raw_dir, dirname)
            if os.path.isdir(src):
                dst = os.path.join(icons_output, dirname)
                if os.path.exists(dst):
                    # 合并目录
                    for f in os.listdir(src):
                        fp = os.path.join(src, f)
                        if os.path.isfile(fp):
                            shutil.copy2(fp, os.path.join(dst, f))
                            count += 1
                else:
                    shutil.copytree(src, dst)
                    count += len([f for f in os.listdir(src)
                                  if os.path.isfile(os.path.join(src, f))])

    print(f"[+] 图标整理完成: {count} 个文件")


def organize_others(raw_dir, output_dir):
    """整理其他未分类资源"""
    others_output = os.path.join(output_dir, "Others")
    os.makedirs(others_output, exist_ok=True)

    # 已处理的目录
    processed = {
        "painting", "paintingface", "metapainting", "shoppainting",
        "painting_filte", "paintings", "paintingsother",
        "live2d", "live2dmask",
        "spinepainting", "spineitem",
        "bg", "commonbg", "loadingbg", "loadingbg_hx", "helpbg",
        "backyardbg", "newshipbg", "worldhelpbg", "lotterybg",
        "cue",
        "ui", "activityuitable", "combatuistyle", "dailyui",
        "dreamlandui", "hideseekui", "leveluiview",
        "chatframe", "linkbutton", "linkbutton_mellow",
    }

    count = 0
    for dirname in os.listdir(raw_dir):
        if dirname in processed or dirname.startswith("icon"):
            continue

        src = os.path.join(raw_dir, dirname)
        if os.path.isdir(src):
            dst = os.path.join(others_output, dirname)
            if not os.path.exists(dst):
                shutil.copytree(src, dst)
                count += sum(1 for f in os.listdir(src)
                             if os.path.isfile(os.path.join(src, f)))

    print(f"[+] 其他资源整理完成: {count} 个文件")


def main():
    """主函数：整理所有导出的资源"""
    print(f"[*] 整理目录: {RAW_DIR}")
    print(f"[*] 输出目录: {OUTPUT_DIR}")

    if not os.path.isdir(RAW_DIR):
        print(f"[ERROR] Raw 目录不存在: {RAW_DIR}")
        print("[*] 请先运行 export_assets.py 导出资源")
        return

    # 1. 整理立绘
    print("\n[*] 整理立绘...")
    organize_paintings(RAW_DIR, OUTPUT_DIR)

    # 2. 整理背景
    print("\n[*] 整理背景...")
    organize_backgrounds(RAW_DIR, OUTPUT_DIR)

    # 3. 整理 Live2D
    print("\n[*] 整理 Live2D...")
    organize_live2d(RAW_DIR, OUTPUT_DIR)

    # 4. 整理 Spine
    print("\n[*] 整理 Spine...")
    organize_spine(RAW_DIR, OUTPUT_DIR)

    # 5. 整理音频
    print("\n[*] 整理音频...")
    organize_audio(RAW_DIR, OUTPUT_DIR)

    # 6. 整理 UI
    print("\n[*] 整理 UI...")
    organize_ui(RAW_DIR, OUTPUT_DIR)

    # 7. 整理图标
    print("\n[*] 整理图标...")
    organize_icons(RAW_DIR, OUTPUT_DIR)

    # 8. 整理其他
    print("\n[*] 整理其他资源...")
    organize_others(RAW_DIR, OUTPUT_DIR)

    print(f"\n[+] 整理完成！")
    print(f"[*] 输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
