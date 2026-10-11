# -*- coding: utf-8 -*-
"""l2d_motion_timewarp.py — 把游戏录屏的帧序列与我们页面抓的帧序列做**姿态对齐**，判"时间差是均匀还是分段"。

为什么要它（§6.37 第十二轮续）：录屏确认就是 `home`，两边**相位顺序一致**，但"站立双手举起"那一段
游戏里持续约 10.6 秒、我们只有约 1.5 秒。这句有两种落法，代价完全不同：
  (a) 均匀倍速 ⇒ 我们的时钟 / `Meta.Fps` / 段时长口径错了 ⇒ 改导出参数就能修；
  (b) **分段压缩** ⇒ 游戏侧有"撑住这个姿势"的东西我们**整类没导出**——头号嫌疑是 Unity 挂在
      GameObject 变换上的 `m_PositionCurves`/`m_RotationCurves`：它们**不走 `genericBindings`**，
      而 `extract_motions.py` 只读 `m_MuscleClip` 的三容器 ⇒ 那是全库 269 模型的系统性缺口。
"第 X 秒 vs 第 X 秒"的比法不成立（录屏不是从 clip 起点录的，§123 追加-XIII 定过规矩），
所以这里做的是**与相位无关**的对齐：找一条单调路径把两边帧配起来，再看这条路径是不是近似直线。

描述子刻意不用整帧像素（两边取景/缩放/UI 完全不同），只用**角色本身**：
  皮肤掩码 ⇒ 取包围盒 ⇒ 盒内灰度缩到 --size 见方、去均值除标准差 ⇒ 再加两个标量：
  皮肤面积占比（判"角色出画"这个强地标）与包围盒长宽比（判"倒立/站立"这类大姿态）。
判据与对照（三条，缺一不许下结论）：
  ① **看路径形状不看总代价**：打印"游戏每 10 帧 → 我们对应帧"的映射与局部斜率；
     斜率≈常数 ⇒ (a)；斜率分段（某段极陡=我们快进、某段≈0=我们停住）⇒ (b)。
  ② **零假设对照**：把我们的序列**时间倒放**再对齐一次。倒放与正放路径无关的东西不该有好结果——
     若倒放的代价明显更低或差不多，说明描述子没有判别力，本轮结论一律不许下。
  ③ **目视复核**：把匹配上的帧对成图（游戏帧 | 我们帧）存一张表，人眼抽查若干对。
     DTW 完全可能给出一条自洽但错的路径，只有配对图能拆穿它。

只读：不改任何产物。用法:
  py -3 scripts/diag/l2d_motion_timewarp.py .diag/game_hd .diag/ours30_off --gamerect 55,65,505,350
输出: stdout 报告 + .diag/timewarp_<前缀>.json + .diag/timewarp_<前缀>_pairs.png
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")


def skin_bounds(imgs, lo0=20, hi0=140):
    """从若干帧里量 R-B 的分位数当皮肤阈值（两边的调色不同，不能共用常数）。"""
    acc = []
    for p in imgs:
        a = np.asarray(Image.open(p).convert("RGB")).astype(np.int16)
        d = a[..., 0] - a[..., 2]
        sel = d[(a[..., 0] > a[..., 1]) & (a[..., 1] >= a[..., 2]) & (a[..., 0] >= 110)]
        if sel.size > 400:
            acc.append(sel)
    if not acc:
        return lo0, hi0
    v = np.concatenate(acc)[:400000]
    return int(np.percentile(v, 15)), int(np.percentile(v, 85))


def feats(files, rect, size, lo, hi, minarea):
    """每帧 → (描述子矩阵, 皮肤面积占比, 包围盒长宽比, 有效标记)。皮肤像素不足 = 「角色出画」，
    这本身是最强的地标，所以单独留一列而不是丢掉该帧。"""
    D, A, R, OK = [], [], [], []
    for pth in files:
        im = Image.open(pth).convert("RGB")
        if rect:
            im = im.crop(rect)
        a = np.asarray(im).astype(np.int16)
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        m = (r > g) & (g >= b) & (r - b >= lo) & (r - b <= hi) & (r >= 110)
        n = int(m.sum())
        A.append(n / float(m.shape[0] * m.shape[1]))
        if n < minarea:
            D.append(np.zeros(size * size, dtype=np.float32)); R.append(1.0); OK.append(0)
            continue
        ys, xs = np.where(m)
        y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
        h, w = max(1, y1 - y0 + 1), max(1, x1 - x0 + 1)
        crop = Image.fromarray(np.asarray(im)[y0:y1 + 1, x0:x1 + 1]).convert("L").resize((size, size))
        v = np.asarray(crop, dtype=np.float32) / 255.0
        v = (v - v.mean()) / (v.std() + 1e-6)
        D.append(v.reshape(-1).astype(np.float32)); R.append(h / float(w)); OK.append(1)
    return (np.asarray(D, dtype=np.float32), np.asarray(A, dtype=np.float32),
            np.asarray(R, dtype=np.float32), np.asarray(OK, dtype=np.int8))


def cost_matrix(Pa, Aa, Ra, Oa, Pb, Ab, Rb, Ob, warea=0.0, wmiss=0.0, war=0.8):
    """逐帧对代价。**默认只用姿态描述子 + 包围盒长宽比**。
    ⚠️ 面积差与「一边有角色一边没有」这两项默认权重 0：两边取景尺度/弹窗边界完全不同，
    它们量的其实是"我的裁剪框对不对"，不是"角色姿态对不对"——上一版把它们算进代价，
    DTW 就给出了一条自洽但全错的路径（配对图里游戏站姿对上我们倒立）。留着开关只为做反向实验。"""
    n, m = len(Pa), len(Pb)
    C = np.zeros((n, m), dtype=np.float32)
    for i in range(n):
        d = np.linalg.norm(Pb - Pa[i], axis=1)
        C[i] = d + np.abs(Rb - Ra[i]) * war
        if warea: C[i] += np.abs(Ab - Aa[i]) * warea
        if wmiss: C[i] += (Oa[i] != Ob).astype(np.float32) * wmiss
    return C


def dtw(C):
    n, m = C.shape
    D = np.full((n + 1, m + 1), np.inf, dtype=np.float64)
    D[0, 0] = 0.0
    P = np.zeros((n + 1, m + 1), dtype=np.int8)
    for i in range(1, n + 1):
        Ci = C[i - 1]
        for j in range(1, m + 1):
            a, b, c = D[i - 1, j], D[i - 1, j - 1], D[i, j - 1]
            if a <= b and a <= c:
                D[i, j] = a + Ci[j - 1]; P[i, j] = 1        # 1=向上（游戏多走一帧）
            elif b <= c:
                D[i, j] = b + Ci[j - 1]; P[i, j] = 2        # 2=对角
            else:
                D[i, j] = c + Ci[j - 1]; P[i, j] = 3        # 3=向左（我们多走一帧）
    path = []
    i, j = n, m
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        s = P[i, j]
        if s == 1: i -= 1
        elif s == 3: j -= 1
        else: i -= 1; j -= 1
    path.reverse()
    return D[n, m], path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game_dir")
    ap.add_argument("ours_dir")
    ap.add_argument("--gamepat", default="g")
    ap.add_argument("--ourspat", default="f")
    ap.add_argument("--gamerect", default="", help="游戏帧要先裁的视口 x0,y0,x1,y1（框掉模拟器外的桌面）")
    ap.add_argument("--oursrect", default="", help="我们帧的裁剪框（默认整张）")
    ap.add_argument("--size", type=int, default=24)
    ap.add_argument("--minarea", type=int, default=900, help="皮肤像素少于此数判「角色出画」")
    ap.add_argument("--fpsg", type=float, default=30.0)
    ap.add_argument("--fspo", type=float, default=30.0)
    ap.add_argument("--prefix", default="home")
    ap.add_argument("--pairs", type=int, default=12, help="存几对匹配图供目视复核")
    ap.add_argument("--warea", type=float, default=0.0, help="面积差权重（默认 0，见 cost_matrix 注释）")
    ap.add_argument("--wmiss", type=float, default=0.0, help="「一边有一边没有」惩罚权重（默认 0，同上）")
    a = ap.parse_args()

    gf = sorted(glob.glob(os.path.join(a.game_dir, a.gamepat + "*.png")) +
                glob.glob(os.path.join(a.game_dir, a.gamepat + "*.jpg")))
    of = sorted(glob.glob(os.path.join(a.ours_dir, a.ourspat + "*.png")) +
                glob.glob(a.ours_dir + os.sep + a.ourspat + "*.jpg"))
    if len(gf) < 30 or len(of) < 30:
        print("[FAIL] 帧太少：game=%d ours=%d" % (len(gf), len(of)))
        return 2
    gr = tuple(int(v) for v in a.gamerect.split(",")) if a.gamerect else None
    orr = tuple(int(v) for v in a.oursrect.split(",")) if a.oursrect else None
    print("游戏 %d 帧（%s）  我们 %d 帧（%s）" % (len(gf), a.game_dir, len(of), a.ours_dir))

    loG, hiG = skin_bounds(gf[::37])
    loO, hiO = skin_bounds(of[::37])
    print("皮肤阈值 游戏 R-B∈[%d,%d] / 我们 R-B∈[%d,%d]（各自现场量，两边调色不同）" % (loG, hiG, loO, hiO))
    Pg, Ag, Rg, Og = feats(gf, gr, a.size, loG, hiG, a.minarea)
    Po, Ao, Ro, Oo = feats(of, orr, a.size, loO, hiO, a.minarea)
    print("有效帧：游戏 %d/%d（出画 %d）  我们 %d/%d（出画 %d）"
          % (int(Og.sum()), len(Og), int((1 - Og).sum()), int(Oo.sum()), len(Oo), int((1 - Oo).sum())))

    C = cost_matrix(Pg, Ag, Rg, Og, Po, Ao, Ro, Oo, a.warea, a.wmiss)
    cost, path = dtw(C)
    # 零假设对照：把我们的序列时间倒放再对齐一次
    Cd = cost_matrix(Pg, Ag, Rg, Og, Po[::-1], Ao[::-1], Ro[::-1], Oo[::-1], a.warea, a.wmiss)
    costd, pathd = dtw(Cd)
    print("\n① 总代价 正放 %.1f  vs  倒放（零假设）%.1f  ⇒ 描述子%s判别力"
          % (cost, costd, "有" if cost < costd * 0.97 else "**没有（本轮结论一律不许下）**"))

    # 映射表：游戏每 K 帧 → 我们对应帧
    K = max(1, len(gf) // 26)
    byG = {}
    for gi, oi in path:
        byG.setdefault(gi, oi)
    rows = []
    for gi in range(0, len(gf), K):
        if gi in byG:
            rows.append((gi, byG[gi]))
    print("\n② 对齐路径（游戏帧 → 我们帧；括号为秒）：")
    prev = None
    slopes = []
    for gi, oi in rows:
        s = "" if prev is None else "  Δ我们=%+d 帧" % (oi - prev[1])
        print("   g%04d t=%5.2fs → o%04d t=%5.2fs%s" % (gi + 1, gi / a.fpsg, oi + 1, oi / a.fspo, s))
        if prev is not None and gi - prev[0] > 0:
            slopes.append((gi - prev[0], oi - prev[1]))
        prev = (gi, oi)
    if slopes:
        sp = [b / float(max(1, aa)) for aa, b in slopes]
        print("   局部斜率（我们帧数/游戏帧数）min %.2f 中位 %.2f max %.2f  ⇒ %s"
              % (min(sp), float(np.median(sp)), max(sp),
                 "近似均匀（指向「时钟/倍速」类问题）" if max(sp) < 2.5 * max(min(sp), 1e-6)
                 else "**分段**（有的段我们快进、有的段几乎停住 ⇒ 指向「整类曲线没导出」）"))

    # 关键地标：游戏里"出画"的区间、"站立段"的区间映射到我们这边
    def runs(mask):
        out, s = [], None
        for i, v in enumerate(list(mask) + [0]):
            if v and s is None: s = i
            if not v and s is not None:
                out.append((s, i - 1)); s = None
        return out
    print("\n③ 地标对照（出画 = 皮肤像素不足）：")
    for s, e in runs(1 - Og):
        if e - s >= 3:
            g0, g1 = byG.get(s), byG.get(e)
            print("   游戏 t=%.2f~%.2fs（%d 帧）→ 我们 %s"
                  % (s / a.fpsg, (e + 1) / a.fpsg, e - s + 1,
                     "对不上" if g0 is None or g1 is None else
                     "t=%.2f~%.2fs（%d 帧）" % (g0 / a.fspo, (g1 + 1) / a.fspo, g1 - g0 + 1)))
    for s, e in runs(1 - Oo):
        if e - s >= 3:
            print("   我们 t=%.2f~%.2fs（%d 帧）出画" % (s / a.fspo, (e + 1) / a.fspo, e - s + 1))

    out = os.path.join(os.path.dirname(os.path.abspath(a.ours_dir.rstrip("/\\"))), "timewarp_%s.json" % a.prefix)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"game": a.game_dir, "ours": a.ours_dir, "fps": [a.fpsg, a.fspo],
                   "cost_fwd": cost, "cost_rev": costd,
                   "path": path[:20000], "map_sample": rows}, fh, ensure_ascii=False)
    print("\n④ 路径与映射 → %s" % out)

    if a.pairs:
        from PIL import ImageDraw
        cols = 2
        CW = 150
        rowsn = min(a.pairs, len(rows))
        sheet = Image.new("RGB", (cols * (CW + 8), rowsn * (int(CW * 1.3) + 22)), (16, 16, 22))
        d = ImageDraw.Draw(sheet)
        for n, (gi, oi) in enumerate(rows[:rowsn]):
            ig = Image.open(gf[gi]).convert("RGB")
            if gr: ig = ig.crop(gr)
            io_ = Image.open(of[oi]).convert("RGB")
            if orr: io_ = io_.crop(orr)
            ig = ig.resize((CW, int(CW * ig.size[1] / ig.size[0])))
            io_ = io_.resize((CW, int(CW * io_.size[1] / io_.size[0])))
            y = n * (int(CW * 1.3) + 22)
            sheet.paste(ig, (4, y + 16)); sheet.paste(io_, (CW + 12, y + 16))
            d.text((4, y), "g%04d %.2fs → o%04d %.2fs" % (gi + 1, gi / a.fpsg, oi + 1, oi / a.fspo),
                   fill=(235, 235, 235))
        sp = out.replace(".json", "_pairs.png")
        sheet.save(sp)
        print("⑤ 目视复核（每行：游戏帧 | 我们匹配帧）→ %s" % sp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
