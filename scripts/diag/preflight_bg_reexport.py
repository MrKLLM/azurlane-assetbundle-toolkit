#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preflight_bg_reexport.py —— 背景导出层的「只读预演」：不改盘，先算出会改/会新增/会删哪些文件。

为什么需要它：`export_assets.py --target bg` 整类目重导会覆写 1,900+ 张已验证产物，
而真正受影响的往往只有几十个包。预演直接 import 生产代码里的 `_resolve_same_name`
（不复刻逻辑），对每个包算出「新策略会落盘哪些文件名 + 面积」，与盘上现状比内容，
于是重导范围缩到精确的包清单，其余一字节不碰。

⚠️ 判据口径：**必须比真实解码尺寸，不能比 `m_Rect`**（Sprite 的 rect 是图集声明尺寸，
    实测 `bg/bg_story_star0` rect 1280x720 / 真实产物 378x378）。
⚠️ 只比面积会漏报「同尺寸但换了另一张画」——本项目实测漏 6 个 ⇒ 收尾必须再跑一遍
    像素级全覆盖校验（见 `check_bg_export_dedupe.py` 的裁判量法），不能只信本脚本的面积对比。

用法:
  py -3 scripts/diag/preflight_bg_reexport.py                 # 默认 bg,loadingbg,loadingbg_hx
  py -3 scripts/diag/preflight_bg_reexport.py --cats bg       # 只预演一个类目
  py -3 scripts/diag/preflight_bg_reexport.py --apply-list    # 顺便写 redo 包清单
退出码：有「会删文件」或加载失败即 1（预演阶段就该红，别等重导）。
产物：`.diag/bgscan/export_plan.json`
"""
import argparse
import json
import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import UnityPy  # noqa: E402
import export_assets as ea  # noqa: E402
from UnityPy import config as upy_config  # noqa: E402

upy_config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
OUT = os.path.join(ROOT, ".diag", "bgscan", "export_plan.json")
REDO = os.path.join(ROOT, ".diag", "bgscan", "redo_bundles.txt")
TYPES = {"Texture2D", "Sprite"}


def png_head(p):
    with open(p, "rb") as f:
        h = f.read(24)
    if h[:8] != b"\x89PNG\r\n\x1a\n":
        return 0
    w, hh = struct.unpack(">II", h[16:24])
    return w * hh


def plan_for(cat):
    """返回 (新增[], 尺寸变大[], 加载失败[], 需重导的包[], 盘上无源的文件[])"""
    src = os.path.join(ROOT, "files", "AssetBundles", cat)
    dst = os.path.join(ROOT, "Output", "Raw", cat)
    new, grow, bad, bundles = [], [], [], set()
    produced = set()
    for f in sorted(os.listdir(src)):
        fp = os.path.join(src, f)
        if not os.path.isfile(fp):
            continue
        try:
            env = UnityPy.load(fp)
        except Exception as e:
            bad.append("%s/%s 加载失败 %s" % (cat, f, str(e)[:60]))
            continue
        cands = []
        for obj in env.objects:
            tn = obj.type.name
            if tn not in TYPES:
                continue
            try:
                d = obj.read()
                name = d.m_Name or ("%s_%d" % (tn, obj.path_id))
                area = ea._pixel_area(tn, d)
                if tn == "Sprite":
                    # 声明尺寸不可信：真解码拿实际落盘尺寸（只有同名冲突时才会走到裁决）
                    w, h = d.image.size
                    area = int(w) * int(h)
            except Exception:
                continue
            safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
            cands.append([safe, tn, obj, area, int(obj.path_id)])
        if not cands:
            continue
        kept = ea._resolve_same_name(cands, fp, ea.ExportStats()) if len(cands) > 1 else cands
        touched = False
        for c in kept:
            name, area = c[0], c[3]
            produced.add(name + ".png")
            p = os.path.join(dst, name + ".png")
            if not os.path.isfile(p):
                new.append({"cat": cat, "file": name + ".png", "px": area, "bundle": f})
                touched = True
            elif png_head(p) != area:
                grow.append({"cat": cat, "file": name + ".png", "bundle": f,
                             "disk_px": png_head(p), "want_px": area})
                touched = True
        if touched:
            bundles.add(f)
    orphan = [x for x in sorted(os.listdir(dst))
              if x.endswith(".png") and x not in produced]
    return new, grow, bad, sorted(bundles), orphan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cats", default="bg,loadingbg,loadingbg_hx")
    ap.add_argument("--apply-list", action="store_true")
    a = ap.parse_args()
    rep = {"new": [], "grow": [], "bad": [], "orphan": [], "bundles": []}
    for cat in [c.strip() for c in a.cats.split(",") if c.strip()]:
        new, grow, bad, bundles, orphan = plan_for(cat)
        rep["new"] += new
        rep["grow"] += grow
        rep["bad"] += bad
        rep["orphan"] += [{"cat": cat, "file": o} for o in orphan]
        rep["bundles"] += [{"cat": cat, "bundle": b} for b in bundles]
        print("%-13s 新增 %3d  尺寸变 %3d  加载失败 %d  需重导包 %d  盘上无源文件 %d"
              % (cat, len(new), len(grow), len(bad), len(bundles), len(orphan)), flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rep, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n合计：新增 %d / 尺寸变 %d / 需重导 %d 个包 -> %s"
          % (len(rep["new"]), len(rep["grow"]), len(rep["bundles"]),
             os.path.relpath(OUT, ROOT).replace("\\", "/")))
    for n in rep["new"][:25]:
        print("  NEW   %s/%s %d px" % (n["cat"], n["file"], n["px"]))
    for g in rep["grow"][:25]:
        print("  GROW  %s/%s %d -> %d px" % (g["cat"], g["file"], g["disk_px"], g["want_px"]))
    for o in rep["orphan"][:10]:
        print("  ⚠ 盘上有、包里没找到: %s/%s" % (o["cat"], o["file"]))
    if a.apply_list:
        open(REDO, "w", encoding="utf-8").write(
            "\n".join("%s/%s" % (b["cat"], b["bundle"]) for b in rep["bundles"]))
        print("重导包清单 -> %s" % os.path.relpath(REDO, ROOT).replace("\\", "/"))
    return 1 if (rep["bad"] or rep["orphan"]) else 0


if __name__ == "__main__":
    sys.exit(main())
