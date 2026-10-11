# -*- coding: utf-8 -*-
"""l2d_curve_plateau_scan.py — 离线算一条 motion 里**每个参数值恒定多久**（平台段），用来对"游戏里那个姿势撑了多久"。

为什么要它（§6.37 第十二轮续）：录屏量实游戏侧 `home` 的"站立举手"撑了约 **10.5 秒**（角色在画 3.0~13.5s），
而我们页面里同一相位只有约 1.5 秒。像素侧对齐已自判死（追加-XVIII），换成**参数空间**：
平台段结构直接在 `motion3.json` 里，离线就能算，不需要浏览器也不需要猜。
它把问题切成两半，两半的修法完全不同：
  **A. 数据里有长平台**（某参数恒定 ≥8s）⇒ 我们导出的曲线是对的，问题在**运行时时钟/播放速度**；
  **B. 数据里根本没有长平台**（最长只有 1~2s）⇒ 问题在**数据侧**：那个"撑住姿势"的东西不在
      `m_MuscleClip` 里（源包 57 个 clip 的 Position/Rotation/Euler/Float 曲线已证全空，追加-XVIII），
      那就只剩"游戏侧这条动作不是单 clip 播完"这一类解释，要回去查 Animator 的状态机行为。
⚠️ 只看参数曲线**不等于**看画面：画面还受 part 透明度、物理、以及本项目实测的**显隐锁存**（追加-XV）影响。
   所以本脚本只回答"时间轴上有没有那段平台"，不回答"画面上有没有"。

求值口径：产物清一色 `Segments=[t0,v0,type,…]`、type `0=线性 1=贝塞尔(再 4 个浮点) 2/3=阶梯/反向阶梯`
（运行时 `CubismMotionSegmentType` 的规矩）。线性段按 30Hz 网格采样；阶梯段取**起点值保持**；
贝塞尔段取控制多边形上的三次曲线（当前产物没有，遇到会如实报"未精确求值"）。

用法: py -3 scripts/diag/l2d_curve_plateau_scan.py gezi_2 home
      py -3 scripts/diag/l2d_curve_plateau_scan.py gezi_2 home --show Param25,All_Y2,Param_Angle_Rotation93
      py -3 scripts/diag/l2d_curve_plateau_scan.py gezi_2 home --hold 8 --eps 1e-3
输出: stdout 报告（无落盘）
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HZ = 30.0


def parse_segments(seg):
    """→ [(t, v, kind)]：kind ∈ {'pt','lin','bez','step','istep'}，'pt' 是首点。"""
    out, i, n = [], 0, len(seg)
    while i + 1 < n:
        t, v = seg[i], seg[i + 1]
        i += 2
        if i >= n:
            out.append((t, v, 'pt'))
            break
        ty = int(seg[i]); i += 1
        if ty == 1:
            cps = seg[i:i + 4]; i += 4
            out.append((t, v, 'bez', cps)); continue
        kind = {0: 'lin', 2: 'step', 3: 'istep'}.get(ty, 'lin')
        out.append((t, v, kind))
    return out


def eval_curve(items, dur, bez_exact=False):
    """在 30Hz 网格上求值 → (samples[list], 是否含贝塞尔段)。"""
    segs = [x for x in items if x[2] != 'pt']
    pts = [(x[0], x[1]) for x in items if x[2] == 'pt'] + \
          [(x[0], x[1]) for x in items if x[2] != 'pt' and len(x) == 3]
    # 首点单独给：items[0] 是 (t,v,'pt')
    keys = [(items[0][0], items[0][1])] if items and items[0][2] == 'pt' else []
    has_bez = any(len(x) == 4 and x[2] == 'bez' for x in items)
    # 段序列：每个条目带它**指向下一点**的类型，下一点的 (t,v) 在下一个条目上
    seq = []
    for j in range(len(items) - 1):
        it = items[j]
        nxt = items[j + 1]
        seq.append((it[0], it[1], it[2], nxt[0], nxt[1]))
    N = int(dur * HZ) + 1
    out = [None] * N
    for k in range(N):
        t = k / HZ
        if not seq:
            out[k] = keys[0][1] if keys else 0.0
            continue
        if t <= seq[0][0]:
            out[k] = seq[0][1]; continue
        if t >= seq[-1][3]:
            out[k] = seq[-1][4]; continue
        for (t0, v0, kind, t1, v1) in seq:
            if t0 <= t <= t1:
                if kind == 'step':
                    out[k] = v0
                elif kind == 'istep':
                    out[k] = v1
                elif kind == 'bez':
                    f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                    out[k] = v0 + (v1 - v0) * f          # 未精确求值：按线性近似（当前产物无贝塞尔）
                else:
                    f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                    out[k] = v0 + (v1 - v0) * f
                break
    return out, has_bez


def plateaus(s, eps):
    """值恒定（相邻差 < eps）的最长连续段 → [(起秒, 止秒, 值)]，按时长降序。"""
    runs, i, n = [], 0, len(s)
    while i < n:
        j = i
        while j + 1 < n and abs(s[j + 1] - s[i]) < eps:
            j += 1
        runs.append((i / HZ, (j + 1) / HZ, s[i]))
        i = j + 1
    runs.sort(key=lambda r: -(r[1] - r[0]))
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("clip")
    ap.add_argument("--eps", type=float, default=1e-3, help="判「值没变」的绝对容差")
    ap.add_argument("--hold", type=float, default=8.0, help="算「长平台」的秒数门槛（对表游戏那 10.5s）")
    ap.add_argument("--show", default="", help="逗号分隔参数名，逐条打印它们的全部平台段")
    a = ap.parse_args()

    fp = os.path.join(ROOT, "Output", "Live2D", a.model, "motion", "%s.motion3.json" % a.clip)
    if not os.path.isfile(fp):
        print("[FAIL] 没有 %s" % fp)
        return 2
    d = json.load(open(fp, encoding="utf-8"))
    dur = float(d["Meta"]["Duration"])
    curves = [c for c in d.get("Curves", []) if c.get("Target") == "Parameter"]
    print("%s/%s  时长 %.2fs  参数曲线 %d 条  网格 %.0fHz  容差 %g" %
          (a.model, a.clip, dur, len(curves), HZ, a.eps))

    top, long_hold, bez, moving, flat = [], 0, 0, 0, 0
    for c in curves:
        items = parse_segments(c["Segments"])
        if not items:
            continue
        if any(len(x) == 4 and x[2] == 'bez' for x in items):
            bez += 1
        s, _ = eval_curve(items, dur)
        span = max(s) - min(s)
        # ⚠️ 必须先剔「整条不动」的曲线：产物里 502 条参数曲线有 300 条是发射的定值曲线（值恒为 0 或某常数），
        #    它们的"平台"就是整条 clip —— 上一版没剔，判据 A 被 320 个假长平台灌满，等于没判。
        if span < max(a.eps, 1e-3):
            flat += 1
            continue
        moving += 1
        r = plateaus(s, a.eps)
        if not r:
            continue
        top.append((r[0][1] - r[0][0], c["Id"], r[0], span))
        if r[0][1] - r[0][0] >= a.hold:
            long_hold += 1
    top.sort(key=lambda x: -x[0])
    if bez:
        print("⚠️ 有 %d 条曲线含贝塞尔段：本脚本对它们按线性近似求值（当前产物应全为线性，出现即说明口径变了）" % bez)
    print("\n最长平台段排行（**只列会动的曲线**，前 18）：")
    print("%-26s %8s %8s %8s %10s %9s" % ("参数", "时长s", "起s", "止s", "值", "跨度"))
    for ln, pid, r, span in top[:18]:
        print("%-26s %8.2f %8.2f %8.2f %10.3f %9.3f" % (pid, ln, r[0], r[1], r[2], span))
    n2 = sum(1 for x in top if x[0] >= 2.0)
    print("\n判据 A/B（整条恒定的 %d 条已剔除 —— 上一版没剔，判据被 320 个假长平台灌满，等于没判；"
          "剩下会动的 %d 条）：" % (flat, moving))
    print("   恒定 ≥%.1fs 的动参数 **%d 个**（≥2s 的 %d 个）" % (a.hold, long_hold, n2))
    print("   ⇒ %s" % ("A：会动的参数里**有**撑住这个姿势的长平台 ⇒ 该查运行时时钟/播放速度，不是导出"
                       if long_hold else
                       "B：会动的参数里**没有** ≥%.1fs 的平台 ⇒ 那个「撑 10 秒」的东西不在 m_MuscleClip 曲线里，"
                       "要回去查游戏侧这条动作到底怎么被驱动的（状态机/多 clip/代码补间）" % a.hold))

    want = [x.strip() for x in a.show.split(",") if x.strip()]
    for pid in want:
        c = next((x for x in curves if x["Id"] == pid), None)
        if not c:
            print("   [WARN] 没有参数 %s" % pid); continue
        items = parse_segments(c["Segments"])
        s, _ = eval_curve(items, dur)
        rs = [r for r in plateaus(s, a.eps) if r[1] - r[0] >= 0.5]
        print("\n   %s 的全部 ≥0.5s 平台段（按时长）：" % pid)
        for r in rs[:12]:
            print("      %.2f~%.2fs（%.2fs）值 %s" % (r[0], r[1], r[1] - r[0], round(r[2], 3)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
