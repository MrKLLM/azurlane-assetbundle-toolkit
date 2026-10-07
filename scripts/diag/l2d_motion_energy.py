# -*- coding: utf-8 -*-
"""l2d_motion_energy.py — 从一串帧里量「哪些区域在动、每帧动多少像素」，用来把"动作僵硬/抽搐"
变成可比较的数字（游戏录像 vs 画廊实拍，同一把尺子）。

用法:
  py -3 scripts/diag/l2d_motion_energy.py .diag/game_vid                 # 帧目录
  py -3 scripts/diag/l2d_motion_energy.py .diag/game_vid --crop 0,24,640,372 --grid 8x5
判据怎么读:
  · `动像素/千像素` = 相邻两帧变化的像素占比。持续 >1 说明画面一直在动；
    接近 0 的段 = 静止（游戏里若只有花瓣在动，占比会很低但不为零）。
  · 网格热区用来区分"全身在动"(pose 层) 与 "只有几小块在动"(花瓣/光量)。
  · 本脚本只报**相对**差异：两边帧率/尺寸不同时要先归一到同一 fps 与同一裁剪框再比。
"""
import argparse
import os
import sys

from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", help="帧目录（按文件名排序即时间序）")
    ap.add_argument("--crop", default="", help="x,y,w,h；裁掉模拟器/任务栏等静态外壳")
    ap.add_argument("--grid", default="8x5", help="热区网格 列x行")
    ap.add_argument("--thresh", type=int, default=18, help="灰度差阈值，低于它算没变")
    a = ap.parse_args()

    files = sorted(f for f in os.listdir(a.frames) if f.lower().endswith((".png", ".jpg")))
    if len(files) < 2:
        print("帧数不足:", len(files)); return 2
    gx, gy = (int(v) for v in a.grid.lower().split("x"))
    box = None
    if a.crop:
        x, y, w, h = (int(v) for v in a.crop.split(","))
        box = (x, y, x + w, y + h)

    def load(name):
        im = Image.open(os.path.join(a.frames, name)).convert("L")
        if box:
            im = im.crop(box)
        return im

    prev = load(files[0])
    W, H = prev.size
    cell = (W // gx) * (H // gy)
    heat = [0] * (gx * gy)
    rows = []
    for i in range(1, len(files)):
        cur = load(files[i])
        if cur.size != prev.size:
            print("尺寸不一致，停在中途", prev.size, cur.size); break
        d = [abs(x - y) > a.thresh for x, y in zip(prev.getdata(), cur.getdata())]
        px = sum(d)
        for idx, v in enumerate(d):
            if v:
                x, y = idx % W, idx // W
                c = (y // (H // gy)) * gx + (x // (W // gx))
                if 0 <= c < len(heat):
                    heat[c] += 1
        rows.append((i, px))
        prev = cur
    n = W * H
    print("帧 %d 张 / 裁剪后 %dx%d / 阈值 %d" % (len(files), W, H, a.thresh))
    per = [p / float(n) * 1000.0 for _, p in rows]
    print("每对帧的变化像素（‰ 全画面）: 均值 %.2f  最小 %.2f  最大 %.2f"
          % (sum(per) / len(per), min(per), max(per)))
    print("逐帧序列:", " ".join("%.1f" % v for v in per))
    zeros = [i for i, v in enumerate(per) if v < 0.3]
    print("几乎静止的帧对: %d / %d  %s" % (len(zeros), len(per), zeros[:12]))
    print("热区网格 %dx%d（每格累计变化像素，千分位）:" % (gx, gy))
    for r in range(gy):
        print("  " + " ".join("%6.1f" % (heat[r * gx + c] / 1000.0) for c in range(gx)))
    top = sorted(range(len(heat)), key=lambda i: -heat[i])[:6]
    print("最活跃格 (行,列, 占比):",
          [(i // gx, i % gx, "%.1f%%" % (100.0 * heat[i] / max(1, sum(heat)))) for i in top])
    return 0


if __name__ == "__main__":
    sys.exit(main())
