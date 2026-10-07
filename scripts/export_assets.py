#!/usr/bin/env python3
r"""
export_assets.py - 批量导出 AssetBundle 资源到 Output/Raw/

主方案: UnityPy (Python 原生, 无需外部工具)
备选: AssetStudioCLI (需安装到 D:\AzurLaneTools\)

用法:
    python export_assets.py                        # 导出全部
    python export_assets.py --target painting      # 只导出立绘
    python export_assets.py --target bg            # 只导出背景
    python export_assets.py --dry-run              # 预览不导出

输出:
    Output/Raw/{子目录}/{资源名}.{png|wav|obj|json}
"""

import os
import sys
import json
import time
import struct
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ============================================================
# 依赖检查
# ============================================================

try:
    import UnityPy
except ImportError:
    print("[ERROR] 需要安装 UnityPy: pip install UnityPy")
    print("[*] 这是主要导出方案，无需外部工具")
    sys.exit(1)

# 新版 AssetBundle 的 unity_version 被伪装/缺失，需显式回退，否则较新包加载失败
from UnityPy import config
config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("[WARN] 未安装 Pillow，Texture2D 将以原始格式导出")

# ============================================================
# 配置区域
# ============================================================

# AssetBundles 源目录
ASSET_BUNDLES_DIR = r"D:\Azur Lane Assets\files\AssetBundles"

# 输出根目录
OUTPUT_ROOT = r"D:\Azur Lane Assets\Output"
RAW_OUTPUT = os.path.join(OUTPUT_ROOT, "Raw")

# 错误日志
ERROR_LOG = r"D:\Azur Lane Assets\docs\ERRORS.log"

# AssetStudioCLI（可选，增强导出能力）
ASSETSTUDIO_CLI = r"D:\Azur Lane Assets\tools\AssetStudioModGUI.net8.0\AssetStudio.CLI.exe"

# 导出目标配置
EXPORT_TARGETS = {
    "painting": {
        "dirs": ["painting", "paintingface", "metapainting", "shoppainting",
                 "painting_filte", "paintings", "paintingsother",
                 "painting_build", "painting_activity", "painting_feast",
                 "painting_commander"],
        "types": ["Texture2D", "Mesh", "Sprite"],
        "desc": "立绘资源",
    },
    "live2d": {
        "dirs": ["live2d", "live2dmask"],
        "types": ["Texture2D", "Mesh", "TextAsset"],
        "desc": "Live2D模型",
    },
    "spine": {
        "dirs": ["spinepainting", "spineitem"],
        "types": ["Texture2D", "Mesh", "TextAsset", "Sprite"],
        "desc": "Spine动画",
    },
    "bg": {
        "dirs": ["bg", "commonbg", "loadingbg", "loadingbg_hx", "helpbg",
                 "backyardbg", "newshipbg", "worldhelpbg", "lotterybg"],
        "types": ["Texture2D", "Sprite"],
        "desc": "背景图片",
        # 同一个包里有两张**同名**纹理是常态（loadingbg 51 个包里 22 个如此），
        # 而它们往往是两张不同的画 ⇒ 必须按内容裁决，不能按名字+顺序互相覆盖。
        "dedupe": "distinct",
    },
    "ui": {
        "dirs": ["ui", "activityuitable", "combatuistyle", "dailyui",
                 "dreamlandui", "hideseekui", "leveluiview",
                 "chatframe", "linkbutton", "linkbutton_mellow"],
        "types": ["Texture2D", "Sprite"],
        "desc": "UI资源",
    },
    "icons": {
        "dirs": ["iconframe", "qicon", "squareicon", "herohrzicon",
                 "memoryicon", "furnitureicon", "shipyardicon",
                 "skillicon", "storyicon", "strategyicon",
                 "enemies", "emoji", "aircrafticon",
                 "commandericon", "commanderskillicon", "commandertalenticon",
                 "dailylevelicon", "chargeicon", "holidayicon",
                 "ninjacityicon", "shipdesignicon", "shiprarity",
                 "tecfateskillicon", "technologyshipicon",
                 "towerclimbingcollectionicon",
                 "jiujiuexpeditioncollectionicon"],
        "types": ["Texture2D", "Sprite"],
        "desc": "图标资源",
    },
    "audio": {
        "dirs": ["cue"],
        "types": ["AudioClip"],
        "desc": "音频资源",
    },
    "char": {
        "dirs": ["char", "metaship"],
        "types": ["Texture2D", "Mesh", "Sprite", "TextAsset"],
        "desc": "角色资产",
    },
    "dorm3d": {
        "dirs": ["dorm3d", "dorm3daccompany", "dorm3dbanner", "dorm3dchar",
                 "dorm3dcollection", "dorm3dcucoloris", "dorm3dholylight",
                 "dorm3dicon", "dorm3dins", "dorm3dmemory",
                 "dorm3dphoto", "dorm3dselect", "dorm3dskinpart"],
        "types": ["Texture2D", "Mesh", "TextAsset"],
        "desc": "3D宿舍",
    },
    "effect": {
        "dirs": ["effect"],
        "types": ["Texture2D", "Mesh", "Sprite"],
        "desc": "视觉特效",
    },
    "furniture": {
        "dirs": ["furnitrues", "sfurniture", "furniture", "furnitures"],
        "types": ["Texture2D", "Mesh", "Sprite"],
        "desc": "家具资源",
    },
    "all": {
        "dirs": None,
        "types": ["Texture2D", "Mesh", "Sprite", "AudioClip", "TextAsset",
                  "Shader", "Font", "MovieTexture", "VideoClip"],
        "desc": "全部资源",
    },
}


class ExportStats:
    """导出统计"""

    def __init__(self):
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.dupes = []
        self.errors = []
        self.start_time = time.time()

    def elapsed(self):
        return time.time() - self.start_time

    def rate(self):
        e = self.elapsed()
        return (self.success + self.failed) / e if e > 0 else 0

    def summary(self):
        print(f"\n{'=' * 60}")
        print(f"[+] 导出完成!")
        print(f"    成功: {self.success}")
        print(f"    失败: {self.failed}")
        print(f"    跳过: {self.skipped}")
        if self.dupes:
            print(f"    同名让位: {len(self.dupes)} 个对象被更大的同名对象盖掉（本属预期，非失败）")
            for d in self.dupes[:10]:
                print(f"      {d}")
            if len(self.dupes) > 10:
                print(f"      ... 还有 {len(self.dupes) - 10} 个")
        print(f"    耗时: {self.elapsed():.1f} 秒 ({self.rate():.1f} 文件/秒)")
        print(f"    输出: {RAW_OUTPUT}")

        if self.errors:
            print(f"\n[!] 错误详情:")
            for err in self.errors[:20]:
                print(f"    {err}")
            if len(self.errors) > 20:
                print(f"    ... 还有 {len(self.errors) - 20} 个错误")

    def log_error(self, filepath, error_type, detail):
        self.errors.append(f"[{error_type}] {os.path.basename(filepath)}: {detail}")
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] [{error_type}] {filepath}\n")
            f.write(f"  {detail}\n\n")


def export_texture2d(obj, output_dir, name):
    """
    导出 Texture2D 资源

    参数:
        obj: UnityPy 对象
        output_dir: 输出目录
        name: 文件名（不含扩展名）

    返回:
        (success, filepath, error)
    """
    try:
        data = obj.read()

        # 获取纹理图像
        img = data.image

        if img is None:
            return False, "", "无法读取图像数据"

        # 确定输出路径
        if HAS_PIL:
            out_path = os.path.join(output_dir, f"{name}.png")
            img.save(out_path, "PNG")
        else:
            # 无 Pillow，保存为原始格式
            out_path = os.path.join(output_dir, f"{name}.tga")
            img.save(out_path)

        return True, out_path, ""

    except Exception as e:
        return False, "", str(e)[:200]


def export_sprite(obj, output_dir, name):
    """
    导出 Sprite 资源（裁剪后的子图）

    参数:
        obj: UnityPy 对象
        output_dir: 输出目录
        name: 文件名

    返回:
        (success, filepath, error)
    """
    try:
        data = obj.read()

        # Sprite 可能有多个子图像
        if hasattr(data, "image") and data.image is not None:
            if HAS_PIL:
                out_path = os.path.join(output_dir, f"{name}.png")
                data.image.save(out_path, "PNG")
            else:
                out_path = os.path.join(output_dir, f"{name}.tga")
                data.image.save(out_path)
            return True, out_path, ""

        return False, "", "Sprite 无图像数据"

    except Exception as e:
        return False, "", str(e)[:200]


def export_audio(obj, output_dir, name):
    """
    导出 AudioClip 资源

    参数:
        obj: UnityPy 对象
        output_dir: 输出目录
        name: 文件名

    返回:
        (success, filepath, error)
    """
    try:
        data = obj.read()

        # 尝试获取音频样本
        if hasattr(data, "samples"):
            samples = data.samples
            if samples:
                # samples 是 {clip_name: bytes} 字典
                for clip_name, audio_data in samples.items():
                    out_path = os.path.join(output_dir, f"{name}.wav")
                    with open(out_path, "wb") as f:
                        f.write(audio_data)
                    return True, out_path, ""

        # 备选：尝试导出为原始格式
        if hasattr(data, "save"):
            out_path = os.path.join(output_dir, f"{name}.fsb")
            data.save(out_path)
            return True, out_path, ""

        return False, "", "AudioClip 无音频数据"

    except Exception as e:
        return False, "", str(e)[:200]


def export_mesh(obj, output_dir, name):
    """
    导出 Mesh 资源为 OBJ 格式

    参数:
        obj: UnityPy 对象
        output_dir: 输出目录
        name: 文件名

    返回:
        (success, filepath, error)
    """
    try:
        data = obj.read()

        # 构建 OBJ 内容
        lines = [f"# Mesh: {name}", ""]

        # 顶点
        if hasattr(data, "vertices") and data.vertices:
            lines.append(f"# Vertices: {len(data.vertices)}")
            for v in data.vertices:
                if len(v) >= 3:
                    lines.append(f"v {v[0]} {v[1]} {v[2]}")
            lines.append("")

        # UV
        if hasattr(data, "uv") and data.uv:
            lines.append(f"# UVs: {len(data.uv)}")
            for uv in data.uv:
                if len(uv) >= 2:
                    lines.append(f"vt {uv[0]} {uv[1]}")
            lines.append("")

        # 法线
        if hasattr(data, "normals") and data.normals:
            lines.append(f"# Normals: {len(data.normals)}")
            for n in data.normals:
                if len(n) >= 3:
                    lines.append(f"vn {n[0]} {n[1]} {n[2]}")
            lines.append("")

        # 面
        if hasattr(data, "triangles") and data.triangles:
            tris = data.triangles
            lines.append(f"# Faces: {len(tris) // 3}")
            for i in range(0, len(tris), 3):
                if i + 2 < len(tris):
                    # OBJ 索引从 1 开始
                    lines.append(f"f {tris[i]+1}/{tris[i]+1}/{tris[i]+1} "
                                 f"{tris[i+1]+1}/{tris[i+1]+1}/{tris[i+1]+1} "
                                 f"{tris[i+2]+1}/{tris[i+2]+1}/{tris[i+2]+1}")

        out_path = os.path.join(output_dir, f"{name}.obj")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return True, out_path, ""

    except Exception as e:
        return False, "", str(e)[:200]


def export_text(obj, output_dir, name):
    """
    导出 TextAsset 资源

    返回:
        (success, filepath, error)
    """
    try:
        data = obj.read()

        if hasattr(data, "m_Script"):
            script = data.m_Script
            if isinstance(script, bytes):
                # 尝试解码为文本
                try:
                    text = script.decode("utf-8")
                    ext = ".txt"
                except UnicodeDecodeError:
                    ext = ".bin"
                    text = None

                out_path = os.path.join(output_dir, f"{name}{ext}")
                with open(out_path, "wb" if ext == ".bin" else "w",
                          encoding=None if ext == ".bin" else "utf-8") as f:
                    if ext == ".bin":
                        f.write(script)
                    else:
                        f.write(text)
                return True, out_path, ""

        return False, "", "TextAsset 无脚本数据"

    except Exception as e:
        return False, "", str(e)[:200]


# 导出函数映射
EXPORTERS = {
    "Texture2D": export_texture2d,
    "Sprite": export_sprite,
    "AudioClip": export_audio,
    "Mesh": export_mesh,
    "TextAsset": export_text,
}


def _pixel_area(type_name, data):
    """同名对象抢同一个输出文件名时用来裁决的像素面积；取不到尺寸的类型返回 0。

    ⚠️ Sprite 取的是 `m_Rect`（图集里的**声明**尺寸），而它真正落盘的是 tight-bounds 裁剪版，
    两者可以差好几倍 ⇒ 这个值对 Sprite 只能当上界看，「整图赢过裁剪图」由
    `_resolve_same_name` 的规则 1 负责。
    """
    try:
        if type_name == "Texture2D":
            return int(data.m_Width) * int(data.m_Height)
        if type_name == "Sprite":
            r = data.m_Rect
            return int(r.width) * int(r.height)
    except Exception:
        pass
    return 0


def _decoded_fingerprint(obj):
    """(解码像素指纹, 真实像素面积) —— 用来区分「同名但是两张不同的画」。"""
    try:
        im = obj.read().image
        return hashlib.sha256(im.tobytes()).hexdigest()[:16], int(im.size[0]) * int(im.size[1])
    except Exception:
        return None, 0


def _resolve_same_name(cands, filepath, stats):
    """同名对象裁决（背景类目用）。规则按证据排，不按对象顺序排：

    1. 同名里只要有 Texture2D，就丢掉 Sprite —— `export_sprite` 落的是 tight-bounds 裁剪版，
       整图能裁出裁剪版、反过来不行（实测 `bg/bg_story_star0` 被存成 378x378，包内是 1280x720）。
    2. 多张同名 Texture2D 先解码算像素指纹分组：**同内容只留最大的一份，内容不同就全都留**，
       第 2 份起文件名加 `__N`。实测 `loadingbg` 22 个多图包里有 21 个装的是两张互不相干的画
       （不同画师、各自带 ILLUST 署名）—— 按尺寸或对象顺序裁定都会把一整张插画静默丢掉。
    3. 组间顺序 = (-面积, path_id)，保证重跑得到同一套文件名。
    """
    by_name = {}
    for i, c in enumerate(cands):
        by_name.setdefault(c[0], []).append(i)

    keep = []
    for name, idxs in by_name.items():
        if len(idxs) == 1:
            keep.append(cands[idxs[0]])
            continue
        texs = [i for i in idxs if cands[i][1] == "Texture2D"]
        pool = texs or idxs
        groups = {}
        for i in pool:
            if texs:
                fp, real = _decoded_fingerprint(cands[i][2])
                if real:
                    cands[i][3] = real
                groups.setdefault(fp or ("读图失败", cands[i][4]), []).append(i)
            else:
                groups[("sprite", cands[i][4])] = [i]
        ordered = sorted(groups.values(),
                         key=lambda g: (-max(cands[i][3] for i in g), min(cands[i][4] for i in g)))
        for n, g in enumerate(ordered):
            pick = max(g, key=lambda i: (cands[i][3], i))
            c = list(cands[pick])
            c[0] = name if n == 0 else "%s__%d" % (name, n + 1)
            keep.append(c)
            for i in g:
                if i != pick:
                    stats.skipped += 1
        if len(ordered) > 1:
            stats.dupes.append("%s: %s 包内有 %d 张**内容不同**的同名画，第 2 张起另存为 %s__N.png"
                               % (os.path.basename(filepath), name, len(ordered), name))
        for i in idxs:
            if i not in pool:
                stats.skipped += 1
                stats.dupes.append("%s: %s 的 Sprite 裁剪版让位于整图"
                                   % (os.path.basename(filepath), name))
    return keep


def export_bundle(filepath, output_dir, allowed_types, stats, dedupe=None):
    """
    导出单个 AssetBundle 文件

    参数:
        filepath: Bundle 文件路径
        output_dir: 输出目录
        allowed_types: 允许导出的资源类型列表
        stats: 统计对象
        dedupe: 同名冲突裁决，"largest" = 面积最大者留盘；None = 维持原行为（后写覆盖前写）

    返回:
        (exported_count, failed_count)
    """
    exported = 0
    failed = 0

    try:
        # 加载 Bundle
        env = UnityPy.load(filepath)

        # 先把候选收齐（名字 + 面积）再决定谁落盘。原来是一个对象直接写一次，
        # 同包内的同名对象必然互相覆盖，留下哪张只取决于对象顺序 —— 实测背景库里
        # 因此有 4 张登录图存成了 1024x576，而包里那张是 1920x1080。
        cands = []
        for obj in env.objects:
            type_name = obj.type.name

            # 只导出允许的类型
            if type_name not in allowed_types:
                continue

            # 获取资源名称（UnityPy 用 m_Name 属性）
            name = ""
            area = 0
            try:
                data = obj.read()
                # UnityPy 的命名属性是 m_Name，不是 name
                name = getattr(data, "m_Name", "")
                area = _pixel_area(type_name, data)
                if not name:
                    name = f"{type_name}_{obj.path_id}"
            except Exception:
                name = f"{type_name}_{obj.path_id}"

            if not name:
                name = f"{type_name}_{obj.path_id}"

            # 清理文件名中的非法字符
            safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
            cands.append([safe_name, type_name, obj, area, int(obj.path_id)])

        if dedupe == "distinct":
            cands = _resolve_same_name(cands, filepath, stats)

        # 遍历要落盘的对象
        for safe_name, type_name, obj, _area, _pid in cands:
            # 选择导出函数
            exporter = EXPORTERS.get(type_name)
            if exporter:
                success, out_path, error = exporter(obj, output_dir, safe_name)
                if success:
                    exported += 1
                else:
                    failed += 1
                    stats.log_error(filepath, type_name, error)

    except Exception as e:
        failed += 1
        stats.log_error(filepath, "LOAD", str(e)[:200])

    return exported, failed


def collect_files(target_dirs):
    """收集要导出的文件"""
    bundles = {}

    for subdir in target_dirs:
        subdir_path = os.path.join(ASSET_BUNDLES_DIR, subdir)
        if not os.path.isdir(subdir_path):
            continue

        files = []
        for f in os.listdir(subdir_path):
            fp = os.path.join(subdir_path, f)
            if os.path.isfile(fp) and os.path.getsize(fp) >= 1024:
                files.append(fp)

        if files:
            bundles[subdir] = files

    return bundles


def get_all_dirs():
    """获取所有子目录"""
    dirs = []
    for entry in os.listdir(ASSET_BUNDLES_DIR):
        if os.path.isdir(os.path.join(ASSET_BUNDLES_DIR, entry)):
            dirs.append(entry)
    return dirs


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="批量导出 AssetBundle 资源")
    parser.add_argument("--target", choices=list(EXPORT_TARGETS.keys()),
                        default="all", help="导出目标")
    parser.add_argument("--dry-run", action="store_true",
                        help="预览模式，不实际导出")
    parser.add_argument("--only", metavar="包名[,包名...]",
                        help="只导这几个包（按源包文件名精确匹配）。用于「源包比导出层新」的定点补导，"
                             "避免 --target 整目录重导覆写已验证的产物；任一名字找不到就直接退出")
    parser.add_argument("--only-dir", metavar="子目录[,子目录...]",
                        help="把 --only 的匹配范围限定在这些子目录。跨目录同名是真实存在的"
                             "（`bg_1` 同时在 loadingbg / loadingbg_hx / newshipbg），"
                             "不限定就会顺手重写别的类目里的产物")
    args = parser.parse_args()

    target = EXPORT_TARGETS[args.target]
    print(f"[*] 导出目标: {target['desc']} ({args.target})")
    print(f"[*] 源目录: {ASSET_BUNDLES_DIR}")
    print(f"[*] 输出: {RAW_OUTPUT}")

    # 检查源目录
    if not os.path.isdir(ASSET_BUNDLES_DIR):
        print(f"[ERROR] 源目录不存在: {ASSET_BUNDLES_DIR}")
        return

    # 获取目录列表
    if target["dirs"] is None:
        target_dirs = get_all_dirs()
    else:
        target_dirs = target["dirs"]

    if args.only_dir:
        want_dirs = {d.strip() for d in args.only_dir.split(',') if d.strip()}
        unknown = sorted(want_dirs - set(target_dirs))
        if unknown:
            print(f"[ERROR] --only-dir 里的这些目录不属于目标 {args.target}: {unknown}")
            return
        target_dirs = [d for d in target_dirs if d in want_dirs]

    print(f"[+] 目标子目录: {len(target_dirs)}")

    # 收集文件
    bundles = collect_files(target_dirs)

    # --only：定点补导。任一名字不存在就整体退出，绝不"少导一半还报成功"
    if args.only:
        want = {w.strip() for w in args.only.split(',') if w.strip()}
        bundles = {d: [f for f in fs if os.path.basename(f) in want] for d, fs in bundles.items()}
        bundles = {d: fs for d, fs in bundles.items() if fs}
        got = {os.path.basename(f) for fs in bundles.values() for f in fs}
        missing = sorted(want - got)
        print(f"[+] --only 命中 {len(got)} / 请求 {len(want)} 个包")
        if missing:
            print(f"[ERROR] 这些名字在源目录里不存在（或小于 1KB 被 collect_files 滤掉）: {missing}")
            return
        # 跨目录同名是真实存在的（`bg_1` 同时在 loadingbg / loadingbg_hx / newshipbg），
        # 不加 --only-dir 就会顺手重写别的类目里已验证的产物 ⇒ 宁可停下让人来限定
        if not args.only_dir:
            amb = {n: [d for d, fs in bundles.items() if n in {os.path.basename(f) for f in fs}]
                   for n in got}
            amb = {n: ds for n, ds in amb.items() if len(ds) > 1}
            if amb:
                print(f"[ERROR] 这些包名在多个子目录里都有，请加 --only-dir 限定范围：")
                for n, ds in sorted(amb.items()):
                    print(f"        {n} -> {ds}")
                return
        for d, fs in bundles.items():
            print(f"      [{d}] {[os.path.basename(f) for f in fs]}")

    total = sum(len(f) for f in bundles.values())
    print(f"[+] 待导出文件: {total}")

    # Dry run
    if args.dry_run:
        print("\n[*] Dry Run 模式:")
        for subdir, files in bundles.items():
            print(f"\n  [{subdir}] ({len(files)} 文件)")
            for f in files[:3]:
                print(f"    {os.path.basename(f)} ({os.path.getsize(f) / 1024:.0f} KB)")
            if len(files) > 3:
                print(f"    ... 还有 {len(files) - 3} 个")
        return

    # 初始化
    stats = ExportStats()
    allowed_types = set(target["types"])

    # 开始导出
    for subdir, files in bundles.items():
        print(f"\n[*] 导出 [{subdir}] ({len(files)} 文件)...")

        output_dir = os.path.join(RAW_OUTPUT, subdir)
        os.makedirs(output_dir, exist_ok=True)

        for i, filepath in enumerate(files):
            filename = os.path.basename(filepath)

            # 导出
            exp, fail = export_bundle(filepath, output_dir, allowed_types, stats,
                                      target.get("dedupe"))
            stats.success += exp
            stats.failed += fail

            # 进度
            if (i + 1) % 50 == 0 or (i + 1) == len(files):
                print(f"    [{i + 1}/{len(files)}] {filename} "
                      f"(成功:{stats.success} 失败:{stats.failed}) "
                      f"[{stats.rate():.1f}/s]")

    # 打印摘要
    stats.summary()


if __name__ == "__main__":
    main()
