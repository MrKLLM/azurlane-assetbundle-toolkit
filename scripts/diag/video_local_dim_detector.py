# -*- coding: utf-8 -*-
"""video_local_dim_detector.py — 在一段帧序列里找**局部、短暂、可恢复**的变暗（判"半透明的那一帧"有没有出现过）。

为什么要它（§6.37 判"游戏里有没有那一段半透明/缺手"）：录屏**不是从动作 clip 起点录的**，
所以任何"第 X 秒 vs 第 X 秒"的对比都不作数（§123 追加-XIII 定过的规矩）⇒ 只能用**与相位无关**的判据：
"整段里有没有出现过这种画面"。而"参数滑过 0.05 那档"在画面上的形状是确定的：
**一小块皮肤色区域在 1~4 帧里变淡、随后自己回来**（gezi_2 实测 A 组手 1→0.5→0，穿过半透明约 85ms ≈ 30fps 的 2~3 帧）。

三条判据缺一不可，否则会把别的东西读成"手变淡"：
  ① **局部**：该块的峰值跌幅要明显大于**全 ROI 同期共模跌幅**（整屏一起暗 = 转场/曝光，不是某块美术）。
     ⚠️ 别拿"八邻域"当共模：手比一个块大，真变淡时邻域是一起跌的，那条判据会把真信号全部否掉；
  ② **短暂可恢复**：连续帧数 ≤ --maxrun，且前后都回到基线（用**居中滚动中位数**当基线，
     拿均值会被大幅运动带跑，拿"全片最小值"会被转场黑帧带跑）；
  ③ **落在皮肤色上**：只统计皮肤掩码内的亮度（手/身体是皮肤色，紫色夜空与建筑不是），
     皮肤像素数不足的门直接判不可信 —— 皮肤色阈值是**从被检帧里量出来的**，见 --skinfrom。
⚠️ 阳性对照必须跑：本检测器要在"我们自己的页面播同一条 clip"的帧序列上**能抓到**已知的半透明帧，
   才允许把"游戏帧里没抓到"读成"游戏里没有"。没有这条对照，阴性结论一律不许下。

用法: py -3 scripts/diag/video_local_dim_detector.py .diag/game_hd --roi 55,65,505,350 --prefix game
      py -3 scripts/diag/video_local_dim_detector.py .diag/ours_hd --roi 0,0,640,400 --prefix ours   # 阳性对照
输出: stdout 排名 + .diag/dim_<prefix>_top.png（前 N 处各裁一块放大图，供目视裁定）
      .diag/dim_<prefix>.json（全部命中与逐块曲线，离线可复算）
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")


def skin_mask(rgb, lo, hi):
    """皮肤色启发式：R 最亮、R>G>B、R-B 在一个带内、亮度不接近黑。阈值由 --skinfrom 现场量。"""
    r = rgb[..., 0].astype(np.int16)
    g = rgb[..., 1].astype(np.int16)
    b = rgb[..., 2].astype(np.int16)
    m = (r > g) & (g >= b) & (r - b >= lo) & (r - b <= hi) & (r >= 110)
    return m


def measure_skin(path):
    """从一帧里量 R-B 的分布，给皮肤阈值当依据（不拍脑袋定常数）。"""
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    d = a[..., 0] - a[..., 2]
    sel = d[(a[..., 0] > a[..., 1]) & (a[..., 1] >= a[..., 2]) & (a[..., 0] >= 110)]
    if sel.size < 500:
        return 20, 120
    return int(np.percentile(sel, 10)), int(np.percentile(sel, 90))


def rolling_median(a, half):
    """沿第 0 轴（帧）做居中滚动中位数；a=(T,H,W) 允许 NaN。"""
    T = a.shape[0]
    out = np.full_like(a, np.nan)
    pad = np.full((T + 2 * half,) + a.shape[1:], np.nan)
    pad[half:half + T] = a
    for t in range(T):
        win = pad[t:t + 2 * half + 1]
        with np.errstate(all="ignore"):
            out[t] = np.nanmedian(win, axis=0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", help="帧目录（*.png/*.jpg）")
    ap.add_argument("--roi", default="", help="只看这块（x0,y0,x1,y1，帧坐标）；游戏录屏要框掉模拟器外的桌面")
    ap.add_argument("--tile", type=int, default=16, help="网格边长（像素）")
    ap.add_argument("--win", type=int, default=10, help="基线窗口半宽（帧）：居中滚动中位数取 2*win+1 帧")
    ap.add_argument("--thresh", type=float, default=0.12, help="相对跌幅阈值（低于基线的比例）")
    ap.add_argument("--maxrun", type=int, default=5, help="连续多少帧以内算「短暂」（超过就是姿态/转场，不是闪）")
    ap.add_argument("--minskin", type=int, default=10, help="块内最少皮肤像素数，不足则该块不可信")
    ap.add_argument("--locality", type=float, default=3.0,
                    help="本块峰值跌幅必须 > 全 ROI 同期跌幅 × 此系数（整屏一起暗 = 转场/曝光，不是某块美术）")
    ap.add_argument("--pat", default="*", help="帧文件名前缀（拼板图混在同一目录会被当成一帧，把序列污染）")
    ap.add_argument("--skinfrom", default="", help="用哪一帧量皮肤阈值，默认取序列中点那帧")
    ap.add_argument("--top", type=int, default=10, help="存前 N 处的放大裁图")
    ap.add_argument("--prefix", default="dim", help="产物前缀")
    a = ap.parse_args()

    files = sorted(glob.glob(os.path.join(a.frames, a.pat + "*.png")) + glob.glob(os.path.join(a.frames, a.pat + "*.jpg")))
    if len(files) < 12:
        print("[FAIL] 帧太少（%d）：短暂事件至少要几十帧才谈得上滚动基线" % len(files))
        return 2
    probe = a.skinfrom or files[len(files) // 2]
    lo, hi = measure_skin(probe)
    print("帧 %d 张；皮肤阈值 R-B∈[%d,%d]（从 %s 现场量的）" % (len(files), lo, hi, os.path.basename(probe)))

    W, H = Image.open(files[0]).size
    if a.roi:
        x0, y0, x1, y1 = [int(v) for v in a.roi.split(",")]
    else:
        x0, y0, x1, y1 = 0, 0, W, H
    tw = max(1, (x1 - x0) // a.tile)
    th = max(1, (y1 - y0) // a.tile)
    print("ROI=(%d,%d,%d,%d) ⇒ 网格 %d×%d，块边长 %dpx" % (x0, y0, x1, y1, tw, th, a.tile))

    S = np.full((len(files), th, tw), np.nan, dtype=np.float32)
    C = np.zeros((len(files), th, tw), dtype=np.int32)
    for i, f in enumerate(files):
        rgb = np.asarray(Image.open(f).convert("RGB"))[y0:y0 + th * a.tile, x0:x0 + tw * a.tile]
        lum = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
        m = skin_mask(rgb, lo, hi).astype(np.float32)
        sl = (lum * m).reshape(th, a.tile, tw, a.tile).sum(axis=(1, 3))
        sc = m.reshape(th, a.tile, tw, a.tile).sum(axis=(1, 3))
        with np.errstate(invalid="ignore", divide="ignore"):
            S[i] = np.where(sc >= a.minskin, sl / np.maximum(sc, 1), np.nan)
        C[i] = sc.astype(np.int32)
        if (i + 1) % 100 == 0:
            print("   读了 %d/%d 帧" % (i + 1, len(files)))
    valid = np.isfinite(S)
    print("逐块皮肤加权亮度：可用块 %d / %d（%d 帧）" % (int(valid.any(axis=0).sum()), tw * th, len(files)))

    base = rolling_median(S, a.win)
    with np.errstate(invalid="ignore"):
        rel = (base - S) / np.maximum(base, 1e-3)
    rel[~valid] = np.nan
    hot = np.where(np.isfinite(rel) & (rel > a.thresh), rel, 0.0)
    # 整屏同期跌幅：转场/曝光会让所有块一起跌，手变淡只会让一小片跌 ⇒ 用"全 ROI 中位数"当共模去扣
    gdrop = np.nanmedian(np.where(np.isfinite(rel), rel, np.nan), axis=1)
    gdrop = np.where(np.isfinite(gdrop), gdrop, 0.0)

    hits = []
    for t in range(len(files)):
        for yy in range(th):
            for xx in range(tw):
                if hot[t, yy, xx] <= 0:
                    continue
                if t > 0 and hot[t - 1, yy, xx] > 0:
                    continue                       # 只从一段命中的第一帧起算
                r = 0
                while t + r < len(files) and hot[t + r, yy, xx] > 0:
                    r += 1
                if r > a.maxrun:
                    continue                       # 太长 ⇒ 姿态/转场，不是"闪一下"
                peak = float(hot[t:t + r, yy, xx].max())
                comode = float(np.median(gdrop[t:t + r]))
                if peak < a.locality * max(comode, 1e-4):
                    continue                       # 全 ROI 一样跌 ⇒ 共模（转场/曝光），不是局部美术
                hits.append({"frame": t, "run": r, "peak": round(peak, 4), "tile": [xx, yy],
                             "xy": [x0 + xx * a.tile, y0 + yy * a.tile],
                             "skin": int(C[t, yy, xx]), "comode": round(comode, 4),
                             "score": round((peak - comode) * r * min(C[t, yy, xx], 200) / 200.0, 4)})
    hits.sort(key=lambda h: -h["score"])
    print("\n命中 %d 处（局部+短暂+皮肤：跌幅>%.0f%%、连续≤%d 帧、峰值 > 全 ROI 共模×%.1f）"
          % (len(hits), 100 * a.thresh, a.maxrun, a.locality))
    for h in hits[:a.top]:
        print("   f%04d t=%5.2fs 连续 %d 帧 峰跌 %4.1f%% 共模 %4.1f%% 块(%d,%d)@(%d,%d) 皮肤 %d px score=%s"
              % (h["frame"] + 1, h["frame"] / 30.0, h["run"], 100 * h["peak"], 100 * h["comode"],
                 h["tile"][0], h["tile"][1], h["xy"][0], h["xy"][1], h["skin"], h["score"]))
    # 灵敏度扫描：0 命中必须配"阈值降到多少才开始出东西"，否则"没抓到"读成"没有"是耍赖
    print("   灵敏度扫描（同一批 rel，只换跌幅阈值）：", end="")
    for tv in (0.03, 0.05, 0.08, 0.12, 0.20):
        n = int(((rel > tv) & np.isfinite(rel)).sum())
        print("  >%.0f%%:%d 块·帧" % (100 * tv, n), end="")
    print("\n   全片最大单块跌幅 %.1f%%（共模峰值 %.1f%%）"
          % (100 * float(np.nanmax(np.where(np.isfinite(rel), rel, 0))), 100 * float(gdrop.max())))

    out = os.path.join(os.path.dirname(os.path.abspath(a.frames.rstrip("/\\"))), "dim_%s.json" % a.prefix)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"frames": len(files), "roi": [x0, y0, x1, y1], "tile": a.tile, "skinRB": [lo, hi],
                   "thresh": a.thresh, "maxrun": a.maxrun, "hits": hits}, fh, ensure_ascii=False)
    print("全部命中 → %s" % out)

    if hits:
        from PIL import ImageDraw
        CW = CH = 112
        cols = min(4, min(len(hits), a.top))
        rows = (min(len(hits), a.top) + cols - 1) // cols
        cell = CW * 3 + 12                       # 每格三条：事件前 6 帧 / 事件帧 / 事件后 6 帧
        sheet = Image.new("RGB", (cols * (cell + 8), rows * (CH + 24)), (16, 16, 22))
        d = ImageDraw.Draw(sheet)
        for n, h in enumerate(hits[:a.top]):
            cx = h["xy"][0] + a.tile // 2
            cy = h["xy"][1] + a.tile // 2
            r, c = divmod(n, cols)
            ox, oy = c * (cell + 8), r * (CH + 24)
            for j, fidx in enumerate((max(0, h["frame"] - 6), h["frame"],
                                      min(len(files) - 1, h["frame"] + h["run"] + 6))):
                box = (max(0, min(W - 112, cx - 56)), max(0, min(H - 112, cy - 56)),
                       max(0, min(W - 112, cx - 56)) + 112, max(0, min(H - 112, cy - 56)) + 112)
                im = Image.open(files[fidx]).crop(box).resize((CW, CH))
                sheet.paste(im, (ox + j * (CW + 4), oy))
            d.text((ox + 2, oy + CH + 4),
                   "f%04d 连%d帧 峰跌%.0f%% 共模%.0f%%" % (h["frame"] + 1, h["run"], 100 * h["peak"], 100 * h["comode"]),
                   fill=(235, 235, 235))
        sp = os.path.join(os.path.dirname(out), "dim_%s_top.png" % a.prefix)
        sheet.save(sp)
        print("前 %d 处放大图 → %s（每格三条：前 6 帧 | 事件帧 | 后 6 帧。要目视裁定：是手变淡，还是头发/花瓣/姿态）"
              % (min(len(hits), a.top), sp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
