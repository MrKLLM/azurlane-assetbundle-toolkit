# -*- coding: utf-8 -*-
"""坏帧里定位「腕口锚点」：按**手镯那片 ArtMesh 的模型坐标**算，不再目测、也不再肤色分割。

为什么改：`docs/HANDOFF_6.37_手不见了_2026-10-12.md` §4.1 要求用手镯的包围盒中心当锚点。
上一版（10-12 19:21 版）走「画布肤色分割 → 连通域 → 肢体末端」，两个毛病：① 端点是肢体最远点对、
不是腕口；② 结论落在像素上，换一帧就得重跑，且要人看图确认。
本版：手镯是 texture 上一块**金色小图**，而 `.diag/wrist_ledger.json` 每片都带 UV 包围盒
⇒ 把 UV 回采样到 `Output/Live2D/gezi_2/texture_0*.png` 量金色占比，「金色占比高 + 两拍都亮 +
上屏(ro≥0) + 面积小」的片 = 手镯候选；锚点直接取它在**模型空间**的 vtx 包围盒中心，全程不进图像模型。

顺带把候选片自己的 UV 贴片裁成 `.diag/wrist_anchor/<片名>.png`（几十像素的小图）——
「这片到底是不是手镯」看这张贴片就能定案，比看整帧立绘小两个数量级。

三条自证（缺一条结论不许引用）：
① 空白对照：texture 里整行全透明的带上取一块，金色占比必须为 0；
② 阈值稳定：饱和度阈值 R−B> 70/80/90 三档扫描，第一名片名必须一致；
③ 投影逐字一致：toStage 的式子必须与 `gallery_src/index.html` 那行字面相同，对不上直接报错。

用法：
  py -3 scripts/diag/l2d_wrist_anchor.py                  # 候选表 + 用第一名出邻居表
  py -3 scripts/diag/l2d_wrist_anchor.py --top 20         # 多看几个候选
  py -3 scripts/diag/l2d_wrist_anchor.py --nm ArtMesh123  # 人工定案后直接用该片当锚点
"""
import json
import os
import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, '.diag', 'wrist_ledger.json')
TEXDIR = os.path.join(ROOT, 'Output', 'Live2D', 'gezi_2')
OUTDIR = os.path.join(ROOT, '.diag', 'wrist_anchor')
INDEX_HTML = os.path.join(ROOT, 'gallery_src', 'index.html')
# 与 gallery_src/index.html 的 toStage 同式：stage = mdl.pos + (v + cu/2) * ppu * scale
TF_STAGE_LINE = 'return [mdl.x+(vx+cux/2)*ppu*s, mdl.y+(cuy/2-vy)*ppu*s];'
NM, TEX, DRO, RO, OP, MSC, VTC, IDC, UV, VTX = range(10)
ECLASS = ['ArtMesh319', 'ArtMesh320', 'ArtMesh321', 'ArtMesh322', 'ArtMesh323']


def arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def load():
    L = json.load(open(LEDGER, encoding='utf-8'))
    good = {r[NM]: r for r in L['good']['snap']['rows']}
    bad = {r[NM]: r for r in L['bad']['snap']['rows']}
    return L, good, bad, L['bad']['snap']['tf']


def load_tex():
    pages = []
    for i in range(2):
        p = os.path.join(TEXDIR, f'texture_0{i}.png')
        if os.path.exists(p):
            pages.append(np.asarray(Image.open(p).convert('RGBA')).astype(np.int16))
    if not pages:
        raise SystemExit(f'texture 不在 {TEXDIR}')
    return pages


def sample(page, uv, flip):
    """UV 包围盒 → texture 像素矩形。Live2D 的 v 轴朝向未定，两种约定都试，由贴片定案。"""
    H, W = page.shape[:2]
    u0, v0, u1, v1 = uv
    if flip:
        v0, v1 = 1.0 - v1, 1.0 - v0
    x0, x1 = max(0, int(round(u0 * W))), min(W, int(round(u1 * W)))
    y0, y1 = max(0, int(round(v0 * H))), min(H, int(round(v1 * H)))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    patch = page[y0:y1, x0:x1]
    if patch.shape[0] * patch.shape[1] > 120000:      # 大步片先降采样，别把内存吃掉
        patch = patch[::2, ::2]
    return patch, [x0, y0, x1, y1]


def goldness(patch, sat=80):
    """金色占比 + 贴片实心度。

    只量金色占比会把**发光点**判成金饰（实测：ArtMesh172 的贴片是一粒橙色光晕，
    外圈 alpha=0 但中心饱和 ⇒ frac=1.00）。所以必须同时量「UV 包围盒里有多少是不透明像素」：
    真饰品的贴片基本是实心的，光晕/发丝这类贴片实心度只有几个百分点。
    """
    R, G, B, A = patch[..., 0], patch[..., 1], patch[..., 2], patch[..., 3]
    total = patch.shape[0] * patch.shape[1]
    solid = A > 8
    n = int(solid.sum())
    if n == 0:
        return 0.0, 0.0, (0, 0, 0)
    gold = solid & (R > 130) & (R >= G) & ((R - B) > sat) & ((G - B) > sat - 30)
    m = (R[solid].mean(), G[solid].mean(), B[solid].mean())
    return float(gold.sum()) / n, n / total, tuple(int(round(v)) for v in m)


def blank_uv_center(page):
    """自检①： integral image 找一块 8×8 全透明窗口，取它的 UV 当伪 UV。"""
    solid = (page[..., 3] > 8).astype(np.int32)
    S = np.zeros((page.shape[0] + 1, page.shape[1] + 1), dtype=np.int64)
    S[1:, 1:] = solid.cumsum(0).cumsum(1)
    k = 8
    win = S[k:, k:] - S[:-k, k:] - S[k:, :-k] + S[:-k, :-k]
    ys, xs = np.unravel_index(int(np.argmin(win)), win.shape)
    if int(win[ys, xs]) != 0:
        return None
    W, H = page.shape[1], page.shape[0]
    return ((xs + k / 2) / W, (ys + k / 2) / H, int((win == 0).sum()))


def area(row):
    b = row[VTX]
    return 0.0 if not b else max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def center(row):
    b = row[VTX]
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def to_stage(vx, vy, tf):
    cux, cuy, ppu, scale, mx, my = tf
    return [mx + (vx + cux / 2) * ppu * scale, my + (cuy / 2 - vy) * ppu * scale]


def candidates(good, bad, pages, sat=80, top=12, min_gold=0.35, min_cov=0.25):
    out = []
    for nm, r in bad.items():
        if r[UV] is None or not (0 <= r[UV][0] <= 1):
            continue
        if r[RO] < 0:
            continue                                   # 遮罩件不上屏
        g = good.get(nm)
        if g is None or r[OP] < 0.05 or g[OP] < 0.05:
            continue                                   # 手镯两拍都得在
        if area(r) < 0.05 or area(g) < 0.05:
            continue                                   # 退化片（顶点塌成一个点）画不出任何东西
        hit = sample(pages[r[TEX]], r[UV], True) or sample(pages[r[TEX]], r[UV], False)
        if hit is None:
            continue
        frac, cov, mean = goldness(hit[0], sat)
        if frac < min_gold or cov < min_cov:
            continue
        out.append(dict(nm=nm, frac=round(frac, 3), cov=round(cov, 2), mean=mean, tex=r[TEX],
                        dro=r[DRO], ro=r[RO], op_bad=r[OP], op_good=g[OP],
                        vtx=r[VTX], uv=r[UV], area=round(area(r), 2), px=hit[1],
                        vtxc=[round(v, 2) for v in center(r)]))
    out.sort(key=lambda d: (-(d['frac'] * d['cov']), d['area']))
    return out[:top]


def save_patch(c, pages):
    hit = sample(pages[c['tex']], c['uv'], True)
    flip = hit is not None
    hit = hit or sample(pages[c['tex']], c['uv'], False)
    patch = hit[0]
    im = Image.fromarray(patch.astype(np.uint8)).resize(
        (patch.shape[1] * 6, patch.shape[0] * 6), Image.NEAREST)
    os.makedirs(OUTDIR, exist_ok=True)
    fp = os.path.join(OUTDIR, f"{c['nm']}_tex{c['tex']}_{'vflip' if flip else 'vraw'}.png")
    im.save(fp)
    print(f"    贴片 {os.path.relpath(fp, ROOT)}  原 {patch.shape[1]}x{patch.shape[0]}px")


def funnel(good, bad, pages, sat=80):
    """全 770 片过一遍判据，打印每一级剩多少 + 不设门槛时的金色前 10。

    为什么必须有这张表：「没有金色实心片」这个否证，只有先证明不是筛选口径误杀才许引用
    （否则可能只是 min_cov / 两拍都亮 把真手镯卡掉了）。
    """
    rows = []
    for nm, r in bad.items():
        uv_ok = r[UV] is not None and 0 <= r[UV][0] <= 1
        ro_ok = r[RO] >= 0
        g = good.get(nm)
        lit_ok = g is not None and r[OP] >= 0.05 and g[OP] >= 0.05
        deg_ok = area(r) >= 0.05 and (g is None or area(g) >= 0.05)
        hit = sample(pages[r[TEX]], r[UV], True) or sample(pages[r[TEX]], r[UV], False) \
            if uv_ok else None
        frac, cov, mean = goldness(hit[0], sat) if hit else (0.0, 0.0, (0, 0, 0))
        rows.append((nm, frac, cov, mean, uv_ok, ro_ok, lit_ok, deg_ok, hit is not None))
    print(f'\n-- 筛选漏斗（共 {len(rows)} 片） --')
    print(f'  UV 合法 {sum(1 for x in rows if x[4])}  上屏 ro>=0 {sum(1 for x in rows if x[5])}  '
          f'两拍都亮 {sum(1 for x in rows if x[6])}  不退化 {sum(1 for x in rows if x[7])}  '
          f'UV 框够大 {sum(1 for x in rows if x[8])}')
    print('  不设任何门槛、金色占比前 10（含被门槛卡掉的）：')
    for nm, frac, cov, mean, a, b, c, d, e in sorted(rows, key=lambda x: -x[1])[:10]:
        keep = '留' if (a and b and c and d and e) else \
            ''.join('' if x else y for x, y in
                    [(a, 'UV'), (b, '遮罩'), (c, '两拍'), (d, '退化'), (e, '框小')])
        print(f'    {nm:14s} 金色{frac:.2f} 实心{cov:.2f} 均色{str(mean):16s} {keep}')


ECLASS = ['ArtMesh319', 'ArtMesh320', 'ArtMesh321', 'ArtMesh322', 'ArtMesh323']
# 美术自起的拼音名 —— 比颜色判据硬：戒指环戴在手指上，所以「戒指环在哪」= 「手指在哪」
NAMED = ['R2shou11'] + [f'jiezhihuan{i}' for i in range(16, 22)]


def skinness(patch):
    """肤色判据（可审计：把均色一起打出来，别只给一个布尔）。"""
    R, G, B, A = patch[..., 0], patch[..., 1], patch[..., 2], patch[..., 3]
    solid = A > 8
    n = int(solid.sum())
    if n == 0:
        return 0.0, (0, 0, 0)
    skin = solid & (R > 190) & (R >= G) & (G > B) & ((R - B) > 20) & ((R - B) < 90)
    m = (int(R[solid].mean()), int(G[solid].mean()), int(B[solid].mean()))
    return float(skin.sum()) / n, m


def hand_mode(good, bad, pages, tf):
    """用「不画但仍在变形」的命名片（右手 / 6 枚戒指环）反查：哪几片亮着的件是手指。"""
    print('\n== --hand：命名片当标尺 ==')
    for nm in NAMED:
        r, q = bad.get(nm), good.get(nm)
        if not r or r[VTX] is None:
            print(f'  {nm:14s} 不在台账 / 无顶点')
            continue
        print(f'  {nm:14s} op {q[OP] if q else -1:.2f}→{r[OP]:.2f} 面积 {area(q) if q else 0:6.2f}→'
              f'{area(r):6.2f} 中心 {tuple(round(v, 2) for v in center(q)) if q and q[VTX] else "?"}'
              f'→{tuple(round(v, 2) for v in center(r))} 框{tuple(r[VTX])}')

    print('\n-- 落在标尺框内（外扩 1.5 单位）的**亮片** --')
    for nm in NAMED:
        r = bad.get(nm)
        if not r or r[VTX] is None or area(r) < 0.05:
            continue
        x0, y0, x1, y1 = r[VTX]
        pad = 1.5
        inside = [(n2, r2) for n2, r2 in bad.items()
                  if r2[VTX] and r2[OP] >= 0.05 and n2 != nm
                  and x0 - pad <= center(r2)[0] <= x1 + pad and y0 - pad <= center(r2)[1] <= y1 + pad]
        print(f'  {nm} 框内亮片 {len(inside)} 片：')
        for n2, r2 in sorted(inside, key=lambda x: -area(x[1]))[:14]:
            q = good.get(n2)
            hit = sample(pages[r2[TEX]], r2[UV], True) or sample(pages[r2[TEX]], r2[UV], False)
            sk, mean = skinness(hit[0]) if hit and hit[0].shape[0] * hit[0].shape[1] else (0.0, (0, 0, 0))
            w, h = r2[VTX][2] - r2[VTX][0], r2[VTX][3] - r2[VTX][1]
            print(f'    {n2:14s} op {q[OP] if q else -1:.2f}→{r2[OP]:.2f} 面积{area(r2):7.2f} '
                  f'{abs(w):5.2f}x{abs(h):5.2f} 肤色{sk:.2f} 均色{str(mean):16s} '
                  f'do{r2[DRO]}/ro{r2[RO]}')

    print('\n-- 手指签名：簇内两两相对距离在两拍之间的变化（刚性=一起动的装饰，散开=各自弯的手指） --')
    for tag, src in (('good', good), ('bad', bad)):
        pts = [(nm, center(src[nm])) for nm in NAMED if src.get(nm) and src[nm][VTX]]
        ds = []
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                ds.append(((pts[i][0], pts[j][0]),
                           round(((pts[i][1][0] - pts[j][1][0]) ** 2 +
                                  (pts[i][1][1] - pts[j][1][1]) ** 2) ** 0.5, 2)))
        print(f'  {tag}: ' + ', '.join(f'{a}↔{b}={d}' for (a, b), d in sorted(ds, key=lambda x: x[1])[:8]))


def point_rect_dist(px, py, box):
    dx = max(box[0] - px, 0, px - box[2])
    dy = max(box[1] - py, 0, py - box[3])
    return (dx * dx + dy * dy) ** 0.5


def main():
    force = arg('--nm', None)
    L, good, bad, tf = load()
    pages = load_tex()
    print(f'台账两拍：good {L["good"]["t"]}s(实到 {L["good"]["tReached"]})  '
          f'bad {L["bad"]["t"]}s(实到 {L["bad"]["tReached"]})  片数 {len(bad)}  tex {len(pages)} 页')
    if '--hand' in sys.argv:
        hand_mode(good, bad, pages, tf)
        return

    blk = blank_uv_center(pages[0])
    if blk is None:
        print('自检① 红：texture_00 上找不到 8×8 全透明窗口，空白对照做不了')
    else:
        b = [blk[0] - .002, blk[1] - .002, blk[0] + .002, blk[1] + .002]
        fake = sample(pages[0], b, True)
        f0 = goldness(fake[0])[0] if fake else 0.0
        print(f'自检① 空白对照：全透明 8×8 窗口共 {blk[2]} 个，取 UV=({blk[0]:.4f},{blk[1]:.4f}) '
              f'金色占比 {f0:.3f} → {"OK" if f0 == 0 else "红"}')

    try:
        s = open(INDEX_HTML, encoding='utf-8').read()
    except OSError as e:
        s = ''
        print(f'自检③ 红：读不到 {INDEX_HTML}（{e}）')
    print('自检③ 投影式与 index.html 的 toStage 字面一致 → OK' if TF_STAGE_LINE in s
          else f'自检③ 红：index.html 里找不到 {TF_STAGE_LINE!r}，先对齐公式再引用本表')

    tables = {sat: candidates(good, bad, pages, sat=sat, top=int(arg('--top', '12')),
                             min_cov=float(arg('--cov', '0.25')),
                             min_gold=float(arg('--mingold', '0.35')))
              for sat in (70, 80, 90)}
    cs = tables[80]
    print('\n-- 金色候选（两拍都亮、上屏；按金色占比降序、同分按面积升序） --')
    for sat, v in tables.items():
        print(f'  阈值 R−B>{sat}: {len(v)} 片，前 3 {[c["nm"] for c in v[:3]]}')
    if not cs:
        raise SystemExit('没有金色候选片 —— 手镯判定不成立，先回去查 UV 采样朝向')
    tops = {v[0]['nm'] if v else None for v in tables.values()}
    print(f'自检② 阈值 ±10 第一名：{"稳定 " + cs[0]["nm"] if len(tops) == 1 else "跳了 → 下面的表只算提名"}')

    for c in cs:
        print(f'  {c["nm"]:14s} 金色{c["frac"]:.2f} 实心{c["cov"]:.2f} '
              f'UV框{c["px"][2] - c["px"][0]}x{c["px"][3] - c["px"][1]:<3d}px '
              f'均色{str(c["mean"]):16s} tex{c["tex"]} '
              f'do{c["dro"]}/ro{c["ro"]} op {c["op_good"]:.2f}→{c["op_bad"]:.2f} '
              f'面积{c["area"]:8.2f} 中心{tuple(c["vtxc"])}')
    funnel(good, bad, pages)

    print('\n-- 前 3 名的 UV 贴片（判「这片是不是手镯」只看这几张几十像素的小图） --')
    for c in cs[:3]:
        print(f'  {c["nm"]}:')
        save_patch(c, pages)

    anchor = bad.get(force) if force else bad[cs[0]['nm']]
    if anchor is None:
        raise SystemExit(f'--nm {force} 不在台账里')
    print(f'\n锚点：{anchor[NM]}' + ('（--nm 指定）' if force else '（第一名，未定案前只算提名）'))

    ax, ay = center(anchor)
    sx, sy = to_stage(ax, ay, tf)
    frame = tf[0] * tf[1]        # 画面在模型(V)空间的面积 = cux × cuy，§4.1 的「画面 5%」按这个量
    print(f'腕口锚点（模型空间）= {anchor[NM]} 的 vtx 包围盒中心 ({ax:.3f}, {ay:.3f})，'
          f'框 {tuple(anchor[VTX])}')
    print(f'投影到画布 = ({sx:.1f}, {sy:.1f}) px   [tf={tf}]')

    rows = []
    for nm, r in bad.items():
        if r[VTX] is None or r[OP] < 0.05 or nm == anchor[NM]:
            continue
        bx, by = center(r)
        dc = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5          # 中心到中心：判「片整体在哪」
        dr = point_rect_dist(ax, ay, r[VTX])                    # 点到矩形：判「有没有伸进腕口」
        g = good.get(nm)
        mv = 0.0 if not g or g[VTX] is None else (
            ((center(g)[0] - bx) ** 2 + (center(g)[1] - by) ** 2) ** 0.5)
        rows.append((dc, dr, mv, nm, r, area(r)))
    # 排序按「中心距」——按点到矩形排会被铺满画面的大片全部打成 0 分（上一版就栽在这）
    huge = [x for x in rows if x[5] > 0.05 * frame]
    near = sorted([x for x in rows if x[5] <= 0.05 * frame], key=lambda x: x[0])
    print(f'\n-- 坏帧里围绕锚点的亮片（按**中心距**排序；巨片阈值 面积>{0.05 * frame:.0f}，'
          f'共 {len(huge)} 片另列，不静默排除） --')
    for dc, dr, mv, nm, r, a in near[:25]:
        tag = '  ← E类(好帧灭/坏帧亮)' if nm in ECLASS else ''
        print(f'  中心距{dc:6.2f} 边距{dr:6.2f} 移动{mv:6.2f}  {nm:12s} '
              f'op {good[nm][OP] if nm in good else -1:.2f}→{r[OP]:.2f} '
              f'do{r[DRO]}/ro{r[RO]} 面积{a:8.2f} 中心({center(r)[0]:.1f},{center(r)[1]:.1f}){tag}')
    print('  巨片（面积降序前 10，只列名与中心距，判 (a) 被盖住时才用得上）：',
          ', '.join(f'{nm}(距{dc:.0f}/{a:.0f})' for dc, dr, mv, nm, r, a in
                    sorted(huge, key=lambda x: -x[5])[:10]) or '无')
    print('\nE类 5 片到锚点的距离：',
          {nm: round(point_rect_dist(ax, ay, bad[nm][VTX]), 2)
           for nm in ECLASS if bad.get(nm) and bad[nm][VTX]})

    os.makedirs(OUTDIR, exist_ok=True)
    fp = os.path.join(OUTDIR, 'wrist_anchor.json')
    json.dump(dict(anchor=anchor[NM], anchor_center=[ax, ay], anchor_box=anchor[VTX], tf=tf,
                   screen=[sx, sy], frame_area=frame,
                   sat_sweep={k: [c['nm'] for c in v] for k, v in tables.items()},
                   near=[[round(dc, 3), round(dr, 3), round(mv, 3), nm, r[OP], r[DRO], r[RO],
                          round(a, 2), r[VTX]] for dc, dr, mv, nm, r, a in near[:80]],
                   huge=[[round(dc, 2), nm, round(a, 1)]
                         for dc, dr, mv, nm, r, a in sorted(huge, key=lambda x: -x[5])]),
              open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'落盘 {os.path.relpath(fp, ROOT)}')


if __name__ == '__main__':
    main()
