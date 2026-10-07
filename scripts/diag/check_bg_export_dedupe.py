#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_bg_export_dedupe.py — 证明 export_assets 的同名裁决「只补漏、不丢图、不改无关行为」。

背景：`loadingbg` 51 个包里 22 个含多张**同名** Texture2D，实测其中 **21 个包装的是两张
互不相干的画**（不同画师、各有 ILLUST 署名，例 `bg_12` = 黑萌 / BSue 各一张 1920x1080）；
`export_bundle` 原来逐个落盘、后写覆盖前写 ⇒ 每个这种包都静默丢掉一整张。
另有 `bg/bg_story_star0` 被 Sprite 的 tight-bounds 裁剪版（378x378）盖掉整图（1280x720）。

两条臂各跑一遍，判据互斥：
  对照臂 dedupe=None      → 产物必须与盘上现文件**逐字节相同**（证明重构没顺手改掉别的导出行为）
  实验臂 dedupe="distinct" → ① 包内每一种**不同内容**都要有产物（不许丢）
                            ② 主文件名那张的面积 == 包内同名最大内容（不许留小的）
                            ③ 产物数 == 不同内容数（不许把同图两尺寸存成两张）

裁判刻意走**另一条量法**：把包内对象真解码一次拿 `.image` 尺寸与像素 sha，
不用 `m_Rect`（Sprite 的 rect 是图集声明尺寸，与落盘尺寸可以差好几倍），
这样"实验臂等于包内上限"才不是在复述实现。

用法:
  py -3 scripts/diag/check_bg_export_dedupe.py
  py -3 scripts/diag/check_bg_export_dedupe.py --bundles loadingbg/bg_1,bg/bg_story_star0
退出码：任一断言红即 1。
"""
import argparse
import hashlib
import os
import shutil
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import UnityPy  # noqa: E402
import export_assets as ea  # noqa: E402
from UnityPy import config as upy_config  # noqa: E402

upy_config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = os.path.join(ROOT, ".diag", "bgscan", "dedupe_check")

# 5 个样本各代表一类：跨尺寸两图 / 同尺寸两图 / 同图两副本 / Sprite 顶掉整图 / 单图对照
DEFAULT = ["loadingbg/bg_1", "loadingbg/bg_8", "loadingbg/bg_12",
           "bg/bg_story_star0", "bg/bg_amahara_1"]


def png_head(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return 0, 0, ""
    w, h = struct.unpack(">II", head[16:24])
    return w, h, ""


def png_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def truth(bundle_path, want_name):
    """独立裁判：包内**同名**对象真实解码后的 {像素sha: 最大面积}。

    只数 Texture2D —— Sprite 落的是同一张图的 tight-bounds 裁剪版，不是一种"新内容"，
    裁决规则 1 就是故意丢掉它（`bg/bg_story_star0` 的 378x378 就是这么冒出来的）。
    只有该名字下确实一张 Texture2D 都没有时，才把 Sprite 当唯一来源。
    """
    env = UnityPy.load(bundle_path)
    tex, spr = {}, {}
    for obj in env.objects:
        if obj.type.name not in ("Texture2D", "Sprite"):
            continue
        d = obj.read()
        if d.m_Name != want_name:
            continue
        im = d.image.convert("RGB")
        fp = hashlib.sha256(im.tobytes()).hexdigest()[:16]
        ar = im.size[0] * im.size[1]
        dst = tex if obj.type.name == "Texture2D" else spr
        dst[fp] = max(dst.get(fp, 0), ar)
    return tex or spr


def run_arm(items, dedupe):
    """把 items 导到临时目录，返回 {key: [产物路径...]}。每个包导到独立子目录，
    这样「跨包同名」不会混进来干扰 —— 本脚本只管包内裁决。"""
    arm = os.path.join(TMP, "distinct" if dedupe else "asis")
    shutil.rmtree(arm, ignore_errors=True)
    res = {}
    for key in items:
        cat, name = key.split("/", 1)
        src = os.path.join(ea.ASSET_BUNDLES_DIR, cat, name)
        if not os.path.isfile(src):
            continue
        out = os.path.join(arm, cat, name)
        os.makedirs(out, exist_ok=True)
        stats = ea.ExportStats()
        ea.export_bundle(src, out, {"Texture2D", "Sprite"}, stats, dedupe)
        res[key] = sorted(os.path.join(dp, f) for dp, _d, fs in os.walk(out)
                          for f in fs if f.endswith(".png"))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundles", help="逗号分隔的 类目/包名")
    a = ap.parse_args()
    items = a.bundles.split(",") if a.bundles else DEFAULT
    os.makedirs(TMP, exist_ok=True)

    control = run_arm(items, None)
    fixed = run_arm(items, "distinct")

    bad_ctrl, bad_fix = [], []
    rows = []
    for key in items:
        cat, name = key.split("/", 1)
        cur = os.path.join(ea.RAW_OUTPUT, cat, name + ".png")
        src = os.path.join(ea.ASSET_BUNDLES_DIR, cat, name)
        if not os.path.isfile(cur):
            print("[SKIP] 盘上没有 %s（属于补导，本脚本不覆盖）" % key)
            continue
        if not os.path.isfile(src):
            bad_ctrl.append("%s 找不到源包" % key)
            continue
        grp = truth(src, name)
        cw, ch = png_head(cur)[:2]
        cp, fp = control.get(key, []), fixed.get(key, [])
        # 断言 A：对照臂必须逐字节复现盘上现文件
        if len(cp) != 1 or png_sha(cp[0]) != png_sha(cur):
            bad_ctrl.append("%s 对照臂没逐字节复现盘上现文件（%s）" % (key, [os.path.basename(x) for x in cp]))
        # 断言 B：实验臂不许丢内容 —— 包内每种不同内容都得有对应产物
        made = {}
        for p in fp:
            w, h = png_head(p)[:2]
            made[w * h] = p
        if len(fp) != len(grp):
            bad_fix.append("%s 实验臂 %d 个文件 != 包内 %d 种不同内容" % (key, len(fp), len(grp)))
        for _fp, ar in grp.items():
            if ar not in made:
                bad_fix.append("%s 包内 %d px 那种内容没有产物（丢了）" % (key, ar))
        # 断言 C：主文件必须是最大的那种内容
        best = max(grp.values()) if grp else 0
        prim = [p for p in fp if os.path.basename(p) == name + ".png"]
        if not prim:
            bad_fix.append("%s 实验臂没产出主文件名" % key)
        else:
            gw, gh = png_head(prim[0])[:2]
            if gw * gh != best:
                bad_fix.append("%s 主文件 %dx%d 不是包内最大内容 %d px" % (key, gw, gh, best))
        rows.append((key, "%dx%d" % (cw, ch),
                     "%dx%d" % (png_head(prim[0])[:2] if prim else (0, 0)),
                     len(grp), [os.path.basename(p) for p in fp]))

    print("%-24s %-10s %-10s %-6s %s" % ("样本", "盘上", "实验臂主图", "内容种数", "实验臂产物"))
    for r in rows:
        print("%-24s %-10s %-10s %-6d %s" % r)
    for desc, bad in [("对照臂逐字节复现盘上现文件（未改无关行为）", bad_ctrl),
                      ("实验臂不丢内容、主图取最大、产物数==不同内容数", bad_fix)]:
        print("%s %s%s" % ("✓" if not bad else "✗", desc, "" if not bad else "\n     " + "\n     ".join(bad)))
    ok = not (bad_ctrl or bad_fix)
    print("\n%s" % ("闸门：绿" if ok else "闸门：红"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
