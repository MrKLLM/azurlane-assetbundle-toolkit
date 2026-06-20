#!/usr/bin/env python3
"""
scan_assets.py — 扫描 AssetBundles 目录，按资源类型生成 JSON 清单

用法:
    python scan_assets.py

输出:
    asset_manifest.json — 完整资源清单（含文件路径、大小、类型分类）
"""

import os
import json
import hashlib
from pathlib import Path
from collections import defaultdict

# ============================================================
# 配置区域 — 按需修改
# ============================================================

# AssetBundles 根目录（源数据，只读扫描）
ASSET_BUNDLES_DIR = r"D:\Azur Lane Assets\files\AssetBundles"

# 输出清单路径
OUTPUT_JSON = r"D:\Azur Lane Assets\asset_manifest.json"

# ============================================================
# 分类规则 — 根据 DEV_LOG_DRAFT.md 的审计结果定义
# ============================================================

# 按子目录名自动分类的映射表
CATEGORY_MAP = {
    # --- 立绘系统 ---
    "painting":        "painting",       # 立绘拆分资源
    "paintingface":    "painting_face",  # 面部特写
    "painting_filte":  "painting_filter",# 立绘滤镜
    "paintings":       "painting_album", # 立绘画集
    "paintingsother":  "painting_other", # 其他立绘
    "metapainting":    "painting_meta",  # META立绘
    "shoppainting":    "painting_shop",  # 商店立绘
    "commanderpainting": "painting_commander", # 指挥官立绘
    "feastpainting":   "painting_feast", # 祭典立绘
    "activitypainting": "painting_activity", # 活动立绘
    "buildpainting":   "painting_build", # 建造立绘

    # --- 动态皮肤 ---
    "live2d":          "live2d",         # Live2D模型
    "live2dmask":      "live2d_mask",    # Live2D遮罩
    "spinepainting":   "spine",          # Spine动画立绘
    "spineitem":       "spine_item",     # Spine道具

    # --- 背景系统 ---
    "bg":              "background",     # 场景背景
    "commonbg":        "background_common", # 通用背景
    "loadingbg":       "background_loading", # 加载背景
    "loadingbg_hx":    "background_loading_hx", # 加载背景HX
    "helpbg":          "background_help", # 帮助背景
    "backyardbg":      "background_backyard", # 后院背景
    "newshipbg":       "background_newship", # 新舰船背景
    "worldhelpbg":     "background_worldhelp", # 世界帮助背景
    "lotterybg":       "background_lottery", # 抽奖背景

    # --- UI系统 ---
    "ui":              "ui",             # UI系统
    "activityuitable": "ui_activity",    # 活动UI
    "combatuistyle":   "ui_combat",      # 战斗UI
    "dailyui":         "ui_daily",       # 每日UI
    "dreamlandui":     "ui_dreamland",   # 梦境UI
    "hideseekui":      "ui_hideseek",    # 躲猫猫UI
    "leveluiview":     "ui_level",       # 关卡UI
    "chatframe":       "ui_chat",        # 聊天框
    "linkbutton":      "ui_link",        # 链接按钮
    "linkbutton_mellow": "ui_link_mellow", # 链接按钮圆润版

    # --- 图标系统 ---
    "iconframe":       "icon_frame",     # 图标边框
    "qicon":           "icon_q",         # Q版图标
    "squareicon":      "icon_square",    # 方形图标
    "herohrzicon":     "icon_hero_hrz",  # 横版英雄图标
    "memoryicon":      "icon_memory",    # 回忆图标
    "furnitureicon":   "icon_furniture", # 家具图标
    "shipyardicon":    "icon_shipyard",  # 船坞图标
    "skillicon":       "icon_skill",     # 技能图标
    "storyicon":       "icon_story",     # 剧情图标
    "strategyicon":    "icon_strategy",  # 策略图标
    "enemies":         "icon_enemy",     # 敌人图标
    "emoji":           "icon_emoji",     # 表情
    "aircrafticon":    "icon_aircraft",  # 飞机图标
    "commandericon":   "icon_commander", # 指挥官图标
    "commanderskillicon": "icon_commander_skill", # 指挥官技能
    "commandertalenticon": "icon_commander_talent", # 指挥官天赋
    "dailylevelicon":  "icon_dailylevel", # 每日关卡图标
    "chargeicon":      "icon_charge",    # 充值图标
    "holidayicon":     "icon_holiday",   # 节日图标
    "ninjacityicon":   "icon_ninjacity", # 忍者城图标
    "shipdesignicon":  "icon_shipdesign", # 舰船设计图标
    "shiprarity":      "icon_shiprarity", # 舰船稀有度
    "tecfateskillicon": "icon_tecfate_skill", # 科技命运技能
    "technologyshipicon": "icon_tech_ship", # 科技舰船图标
    "towerclimbingcollectionicon": "icon_tower", # 爬塔收藏
    "jiujiuexpeditioncollectionicon": "icon_expedition", # 远征收藏

    # --- 音频系统 ---
    "cue":             "audio",          # 音频Cue Bundle

    # --- 3D系统 ---
    "dorm3d":          "dorm_3d",        # 3D宿舍
    "dorm3daccompany": "dorm_3d_accompany",
    "dorm3dbanner":    "dorm_3d_banner",
    "dorm3dchar":      "dorm_3d_char",
    "dorm3dcollection": "dorm_3d_collection",
    "dorm3dcucoloris": "dorm_3d_cucoloris",
    "dorm3dholylight": "dorm_3d_holylight",
    "dorm3dicon":      "dorm_3d_icon",
    "dorm3dins":       "dorm_3d_ins",
    "dorm3dmemory":    "dorm_3d_memory",
    "dorm3dphoto":     "dorm_3d_photo",
    "dorm3dselect":    "dorm_3d_select",
    "dorm3dskinpart":  "dorm_3d_skinpart",
    "model":           "model_3d",       # 3D模型
    "shipmodels":      "ship_model",     # 舰船模型

    # --- 角色资产 ---
    "char":            "char",           # 角色资产包
    "metaship":        "char_meta",      # META角色

    # --- 家具系统 ---
    "furnitrues":      "furniture",      # 家具数据
    "sfurniture":      "furniture_special", # 特殊家具
    "furniture":       "furniture_raw",  # 家具原始
    "furnitures":      "furniture_other", # 其他家具

    # --- 地图系统 ---
    "bg":              "map_bg",         # 地图背景
    "chapter":         "chapter",        # 章节地图
    "map":             "map",            # 地图数据
    "levelmap":        "level_map",      # 关卡地图
    "worldmap3d":      "world_map_3d",   # 3D世界地图
    "mapres":          "map_res",        # 地图资源

    # --- 道具/装备 ---
    "item":            "item",           # 道具图标
    "equips":          "equip",          # 装备图标
    "props":           "prop",           # 道具资源
    "spweapon":        "sp_weapon",      # 特殊武器

    # --- 活动系统 ---
    "island":          "island",         # 岛屿系统
    "activitybanner":  "activity_banner", # 活动横幅
    "activitymedal":   "activity_medal", # 活动勋章
    "activitybossbuff": "activity_bossbuff", # 活动Boss Buff

    # --- 视频 ---
    "originsource":    "video",          # 视频封存

    # --- 其他 ---
    "effect":          "effect",         # 视觉特效
    "font":            "font",           # 字体
    "shader":          "shader",         # 着色器（根级文件）
    "mangapic":        "manga",          # 漫画图片
    "gallerypic":      "gallery",        # 图鉴图片
    "educatepolaroid": "educate_polaroid", # 教育拍立得
    "educatepicture":  "educate_picture", # 教育图片
    "medal":           "medal",          # 勋章
    "medalalbum":      "medal_album",    # 勋章专辑
    "memorystoryline": "memory_story",   # 回忆剧情线
    "prints":          "print",          # 印花
    "backyardtheme":   "backyard_theme", # 后院主题
    "roguecards":      "rogue_card",     # 肉鸽卡牌
    "roguegifts":      "rogue_gift",     # 肉鸽礼物
    "vote":            "vote",           # 投票
    "world":           "world",          # 世界系统
    "sharecfgdata":    "config",         # 配置数据
    "clutter":         "misc",           # 杂项
    "template":        "template",       # 模板
}


def get_file_size_human(size_bytes):
    """将字节大小转换为可读格式"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def classify_file(rel_path, filename):
    """
    根据相对路径和文件名，推断资源类型

    参数:
        rel_path: 相对于 AssetBundles 的路径
        filename: 文件名

    返回:
        (category, sub_type) 元组
    """
    parts = rel_path.replace("\\", "/").split("/")
    top_dir = parts[0] if len(parts) > 1 else "root"

    # 根据顶层目录分类
    if top_dir in CATEGORY_MAP:
        category = CATEGORY_MAP[top_dir]
    else:
        category = "unclassified"

    # 细分类型：识别 _tex, _n, _hx 等后缀
    sub_type = "bundle"
    if "_tex" in filename:
        sub_type = "texture"
    elif "_n_tex" in filename:
        sub_type = "texture_normal"
    elif "_rw_tex" in filename:
        sub_type = "texture_rw"
    elif "_bj_tex" in filename:
        sub_type = "texture_bg"
    elif "_hx_tex" in filename:
        sub_type = "texture_hx"
    elif filename.endswith(".b"):
        sub_type = "audio_cue"
    elif filename.endswith(".cpk"):
        sub_type = "video_archive"
    elif filename.endswith(".dll"):
        sub_type = "native_plugin"
    elif filename.endswith(".shadowmap"):
        sub_type = "shadow_map"
    elif "_res" in filename:
        sub_type = "spine_resource"

    return category, sub_type


def parse_painting_name(filename):
    """
    解析立绘文件名，提取舰名和皮肤信息

    示例:
        aidang → (aidang, default, "")
        aidang_2_tex → (aidang, 2, "tex")
        aidang_6_n_hx_tex → (aidang, 6, "n_hx_tex")
    """
    name = filename
    skin_num = "default"
    variant = ""

    # 移除 _tex 后缀用于解析
    base = name.replace("_tex", "")

    # 尝试匹配皮肤编号 _2, _3 等
    import re
    match = re.match(r"^(.+?)_(\d+)(.*)$", base)
    if match:
        ship_name = match.group(1)
        skin_num = match.group(2)
        variant = match.group(3).lstrip("_")
    else:
        ship_name = base

    return ship_name, skin_num, variant


def scan_directory(root_dir):
    """
    递归扫描目录，生成文件清单

    返回:
        文件信息列表
    """
    files_info = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)

            # 计算相对路径
            rel_path = os.path.relpath(filepath, root_dir)

            # 获取文件大小
            try:
                size = os.path.getsize(filepath)
            except OSError:
                size = 0

            # 分类
            category, sub_type = classify_file(rel_path, filename)

            # 计算文件哈希（前 1KB 快速哈希，避免大文件耗时）
            file_hash = ""
            try:
                with open(filepath, "rb") as f:
                    chunk = f.read(1024)
                    file_hash = hashlib.md5(chunk).hexdigest()
            except Exception:
                file_hash = "unreadable"

            file_info = {
                "path": rel_path,
                "filename": filename,
                "size_bytes": size,
                "size_human": get_file_size_human(size),
                "category": category,
                "sub_type": sub_type,
                "quick_hash": file_hash,
            }

            # 如果是立绘相关，额外解析舰名和皮肤
            if category.startswith("painting"):
                ship_name, skin_num, variant = parse_painting_name(filename)
                file_info["ship_name"] = ship_name
                file_info["skin_number"] = skin_num
                file_info["variant"] = variant

            files_info.append(file_info)

    return files_info


def generate_summary(files_info):
    """生成统计摘要"""
    summary = {
        "total_files": len(files_info),
        "total_size_bytes": sum(f["size_bytes"] for f in files_info),
        "by_category": {},
        "by_sub_type": {},
    }

    # 按类别统计
    for f in files_info:
        cat = f["category"]
        if cat not in summary["by_category"]:
            summary["by_category"][cat] = {"count": 0, "size_bytes": 0}
        summary["by_category"][cat]["count"] += 1
        summary["by_category"][cat]["size_bytes"] += f["size_bytes"]

        st = f["sub_type"]
        if st not in summary["by_sub_type"]:
            summary["by_sub_type"][st] = {"count": 0, "size_bytes": 0}
        summary["by_sub_type"][st]["count"] += 1
        summary["by_sub_type"][st]["size_bytes"] += f["size_bytes"]

    # 转换大小为可读格式
    for cat in summary["by_category"]:
        summary["by_category"][cat]["size_human"] = get_file_size_human(
            summary["by_category"][cat]["size_bytes"]
        )
    for st in summary["by_sub_type"]:
        summary["by_sub_type"][st]["size_human"] = get_file_size_human(
            summary["by_sub_type"][st]["size_bytes"]
        )

    summary["total_size_human"] = get_file_size_human(summary["total_size_bytes"])

    return summary


def main():
    """主函数：执行扫描并输出 JSON"""
    print(f"[*] 扫描目录: {ASSET_BUNDLES_DIR}")
    print(f"[*] 这可能需要几分钟...")

    # 检查目录是否存在
    if not os.path.isdir(ASSET_BUNDLES_DIR):
        print(f"[ERROR] 目录不存在: {ASSET_BUNDLES_DIR}")
        return

    # 扫描
    files_info = scan_directory(ASSET_BUNDLES_DIR)
    print(f"[+] 扫描完成，共 {len(files_info)} 个文件")

    # 生成摘要
    summary = generate_summary(files_info)

    # 构建输出结构
    output = {
        "scan_info": {
            "source_dir": ASSET_BUNDLES_DIR,
            "scan_mode": "read_only",
        },
        "summary": summary,
        "files": files_info,
    }

    # 写入 JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[+] 清单已写入: {OUTPUT_JSON}")
    print(f"[+] 总文件数: {summary['total_files']}")
    print(f"[+] 总大小: {summary['total_size_human']}")

    # 打印类别分布
    print("\n[*] 资源类别分布:")
    for cat, info in sorted(summary["by_category"].items(), key=lambda x: -x[1]["size_bytes"]):
        print(f"    {cat:30s}  {info['count']:6d} 文件  {info['size_human']:>10s}")


if __name__ == "__main__":
    main()
