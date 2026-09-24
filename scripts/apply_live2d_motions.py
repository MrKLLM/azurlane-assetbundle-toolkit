#!/usr/bin/env python3
"""apply_live2d_motions.py — 把临时目录里重跑出的 motion 换入正式 Live2D 目录。

安全设计（默认只报告、不动文件）:
  * 干跑（默认）：只统计将发生的变更，不写任何文件。
  * `--yes`：真正执行。执行前把每个模型的旧 `motion/` **整体移动**到
    `Output/_OLD_bak/l2d_motion_<日期>/<模型>/`（移动而非复制：省磁盘、且旧数据完整可回滚）。
  * 只替换 `motion/` 子目录；moc3 / 贴图 / physics / model3.json 一律不动。
  * 结束后按 AGENTS.md 的约定提示跑 fix_model3.py 与画廊回归。
  * **源目录必须显式给出**，否则拒绝执行。曾经默认回落到 `.diag/l2d_new`，而管线各脚本用的是
    `L2D_OUT_DIR`、本脚本读 `L2D_SRC_DIR`——照文档设 `L2D_OUT_DIR` 会静默换入默认目录里的陈旧数据。

用法:
  py -3 scripts/apply_live2d_motions.py                       # 干跑看清单
  L2D_SRC_DIR=<源目录> py -3 scripts/apply_live2d_motions.py --yes
"""
import os, sys, shutil, argparse, datetime, json

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"D:\Azur Lane Assets"
SRC = os.environ.get("L2D_SRC_DIR") or os.environ.get("L2D_OUT_DIR")
DST = os.path.join(ROOT, "Output", "Live2D")


def count_curves(motion_dir):
    n = curves = 0
    if not os.path.isdir(motion_dir):
        return 0, 0
    for f in os.listdir(motion_dir):
        if not f.endswith(".motion3.json"):
            continue
        n += 1
        try:
            curves += len(json.load(open(os.path.join(motion_dir, f), encoding="utf-8")).get("Curves", []))
        except Exception:
            pass
    return n, curves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="真正执行（默认干跑）")
    args = ap.parse_args()

    if not SRC:
        print("[ERROR] 未指定源目录：设 L2D_SRC_DIR=<临时重导目录>（管线其它脚本用的 L2D_OUT_DIR 也认）。\n"
              "        不给源目录一律拒绝，避免静默换入默认目录里的陈旧数据。")
        return 2
    if not os.path.isdir(SRC):
        print(f"[ERROR] 源目录不存在: {SRC}")
        return 2
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(ROOT, "Output", "_OLD_bak", f"l2d_motion_{stamp}")

    models = sorted(d for d in os.listdir(SRC)
                    if os.path.isdir(os.path.join(SRC, d, "motion")))
    tot_new = tot_old = 0
    empty_new = []
    plan = []
    print(f"[*] 源: {SRC}\n[*] 目标: {DST}\n[*] 备份到: {backup}\n[*] 模式: {'执行' if args.yes else '干跑'}")
    for m in models:
        s_md = os.path.join(SRC, m, "motion")
        d_dir = os.path.join(DST, m)
        d_md = os.path.join(d_dir, "motion")
        if not os.path.isdir(d_dir):
            print(f"  [!] 正式目录没有模型 {m}，跳过")
            continue
        sn, sc = count_curves(s_md)
        on, oc = count_curves(d_md)
        tot_new += sc
        tot_old += oc
        if sc == 0:
            empty_new.append(m)
            continue
        if sn == 0:
            continue
        plan.append((m, s_md, d_md))
    print(f"\n曲线总数: 旧 {tot_old} → 新 {tot_new}")
    if empty_new:
        print(f"[!] 源里曲线为 0 的模型（未换入）: {empty_new}")

    # 本次修的是「漏读 constant 曲线 + 空壳占位」，只会让曲线变多；变少即源目录是修复前的旧产物。
    if tot_new < tot_old and not os.environ.get("L2D_ALLOW_CURVE_DROP"):
        print(f"[BLOCKED] 源目录曲线总数比正式目录少 {tot_old - tot_new} 条，判定为修复前的陈旧产物，拒绝换入。\n"
              f"          确认这是有意为之再 `L2D_ALLOW_CURVE_DROP=1` 重跑。")
        return 3

    if not args.yes:
        print(f"[i] 干跑结束；将换入 {len(plan)} 个模型的 motion/，确认无误后加 --yes 执行")
        return 0
    for m, s_md, d_md in plan:
        if os.path.isdir(d_md):
            dst_bak = os.path.join(backup, m)
            os.makedirs(os.path.dirname(dst_bak), exist_ok=True)
            shutil.move(d_md, dst_bak)          # 备份目录带时间戳，不覆盖也不删除任何旧备份
        shutil.copytree(s_md, d_md)
    print(f"[+] 已换入 {len(plan)} 个模型的 motion/，旧数据备份在 {backup}")
    print("[i] 下一步: 1) py -3 scripts/fix_model3.py   2) 画廊回归 + 增量重建")
    return 0


if __name__ == "__main__":
    sys.exit(main())
