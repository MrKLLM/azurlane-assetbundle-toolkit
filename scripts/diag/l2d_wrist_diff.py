"""good(10.87s 两手都在) vs bad(15.40s 右手没) 逐片差分 —— 定位"消失的那只手"。

为什么：前几轮三次栽在"台账只能提名不能定案"（§123 追加-XXVII/XXX/XXXI）。本表不提名、
只做**同模型两拍差分**：op 由亮到灭 / 顶点面积由正常到坍缩 / 顶点位置大幅迁移的片，
就是这只手本身。三拍自证见 l2d_wrist_ledger.py 头注释（Param25/27 与用户存档偏差 ≤0.05）。

输出五类：
  A 亮→灭      ：op_good>0.5 且 op_bad<=0.01        ⇒ (c) 没画
  B 面积坍缩    ：good 面积>0.05 且 bad 面积<0.005   ⇒ (c) 几何塌了
  C 面积骤减    ：bad/good < 0.25                    ⇒ 部分没画
  D 位置迁移    ：bbox 中心移动 >3 单位              ⇒ (b) 画在别处
  E 反向出现    ：bad 亮而 good 灭                   ⇒ 排除项（切换类）
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
L = json.load(open(os.path.join(ROOT, '.diag', 'wrist_ledger.json'), encoding='utf-8'))


def area(b):
    if not b:
        return 0.0
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def center(b):
    if not b:
        return None
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def main():
    g = {r[0]: r for r in L['good']['snap']['rows']}
    b = {r[0]: r for r in L['bad']['snap']['rows']}
    tf = L['good']['snap']['tf']
    print('字段: [nm, tex, drawOrder, renderOrder, op, maskCount, vtxCount, idxCount, uv, vtxbbox]')
    cats = {'A': [], 'B': [], 'C': [], 'D': [], 'E': []}
    for nm in g:
        rg, rb = g[nm], b.get(nm)
        if rb is None:
            continue
        opg, opb = rg[4], rb[4]
        ag, ab = area(rg[9]), area(rb[9])
        if opg > 0.5 and opb <= 0.01:
            cats['A'].append((nm, rg, rb))
        elif opg > 0.5 and ag > 0.05 and ab < 0.005:
            cats['B'].append((nm, rg, rb))
        elif opg > 0.5 and ag > 0.05 and ab < 0.25 * ag:
            cats['C'].append((nm, rg, rb))
        elif opg > 0.5 and opb > 0.5 and ag > 0.05:
            cg, cb = center(rg[9]), center(rb[9])
            if cg and cb and ((cg[0] - cb[0]) ** 2 + (cg[1] - cb[1]) ** 2) ** 0.5 > 3:
                cats['D'].append((nm, rg, rb))
        elif opb > 0.5 and opg <= 0.01:
            cats['E'].append((nm, rg, rb))
    for k, title in (('A', 'A 亮→灭（good 亮、bad 灭）'), ('B', 'B 面积坍缩（good 正常、bad <0.005）'),
                     ('C', 'C 面积骤减（bad < good 的 25%）'), ('D', 'D 位置迁移（中心移 >3 单位）'),
                     ('E', 'E 反向出现（bad 亮、good 灭）')):
        print(f'\n== {k} {title}: {len(cats[k])} 片')
        for nm, rg, rb in sorted(cats[k], key=lambda x: -area(x[1][9]))[:40]:
            cg, cb = center(rg[9]), center(rb[9])
            print('  %-12s tex%d ro%-4d vtx%-4d  op %.2f→%.2f  面积 %8.3f→%8.3f  中心 %s→%s'
                  % (nm, rg[1], rg[3], rg[6], rg[4], rb[4], area(rg[9]), area(rb[9]),
                     ('(%.1f,%.1f)' % cg) if cg else 'None',
                     ('(%.1f,%.1f)' % cb) if cb else 'None'))
    # A/B/C 汇总给下一步（腕口实验的候选片名单）
    out = {k: [x[0] for x in v] for k, v in cats.items()}
    p = os.path.join(ROOT, '.diag', 'wrist_diff.json')
    json.dump(out, open(p, 'w'), ensure_ascii=False)
    print('\n落盘', p)


def sweep_main(path):
    """细扫模式：相邻两帧配一对，**同时**量「画布变了多少像素」和「逐片变了什么」。

    为什么要两列一起量：10.87s↔15.40s 那对里 A/B/C 全 0（没有片被关掉、没有片塌面积），
    但用户确实看到腕上没手 ⇒ 消失要么只持续几帧（两个采样点都落在"有手"的一侧），
    要么走**逐片台账看不见**的通道（剪贴蒙版、绘制序：op 与面积都不动）。判据：
      画布变多 + 逐片全 0  ⇒ 蒙版 / 绘制序类，台账这条路到此为止
      画布变多 + 有片在变  ⇒ 那几片就是手，直接进 §4.1 的遮罩实验
    ⚠️ 没有「肤色像素占比」这类列：画布被页面环境光压成近灰（实测暖色只占 0.3%，
       且 ambient 自己随时间变），绝对阈值判据在这条管线上不可信。
    """
    import numpy as np
    from PIL import Image
    d = os.path.dirname(path)
    S = json.load(open(path, encoding='utf-8'))
    tags = sorted(k for k in S if not k.startswith('_'))
    print(f'{"帧":>6} {"画布Δ":>7} {"op变":>5} {"面积变":>6} {"中心移":>6}  Param25/27  判读')
    prev_img = prev_rows = None
    for t in tags:
        f = S[t]
        rows = {r[0]: r for r in f['snap']['rows']}
        im = Image.open(os.path.join(d, f'{t}.png')).convert('RGB')
        a = np.asarray(im.resize((im.width // 4, im.height // 4)), dtype=int)
        if prev_img is not None:
            pct = 100.0 * int((np.abs(a - prev_img).max(axis=2) > 24).sum()) / (a.shape[0] * a.shape[1])
            op_ch, ar_ch, mo_ch = [], [], 0
            for n, r in rows.items():
                q = prev_rows.get(n)
                if not q:
                    continue
                if abs(r[4] - q[4]) > 0.1:
                    op_ch.append((n, q, r))
                ag, ab = area(q[9]), area(r[9])
                if ag > 0.05 and (ab < 0.5 * ag or ab > 2 * ag):
                    ar_ch.append((n, q, r))
                cg, cb = center(q[9]), center(r[9])
                if cg and cb and ((cg[0] - cb[0]) ** 2 + (cg[1] - cb[1]) ** 2) ** 0.5 > 0.5:
                    mo_ch += 1
            p = f['snap']['p']
            verdict = ('← 画布在变、逐片全 0 ⇒ 查蒙版/绘制序' if pct > 0.5 and not op_ch and not ar_ch
                       else '← 有片在变' if pct > 0.5 else '')
            print(f'{t:>6} {pct:6.2f}% {len(op_ch):5d} {len(ar_ch):6d} {mo_ch:6d}  '
                  f'{p.get("Param25")}/{p.get("Param27")}  {verdict}')
        prev_img, prev_rows = a, rows

    # 「短暂缺失」的形状不是"这一对变化最大"，而是**沉下去又弹回来**：按逐片时间序列找瞬断。
    print('\n-- 逐片序列瞬断（op / 面积 各自找"掉了又回来"的片） --')
    rowsby = {t: {r[0]: r for r in S[t]['snap']['rows']} for t in tags}
    names = sorted(rowsby[tags[0]])
    ops = {n: [rowsby[t][n][4] for t in tags] for n in names}
    ars = {n: [area(rowsby[t][n][9]) for t in tags] for n in names}
    CUT = next((i for i, t in enumerate(tags) if float(t) >= 15.70), len(tags))

    def dips(vals, rel):
        """最大瞬断深度 = min(左侧历史最高, 右侧未来最高) − 谷底，对每个谷位取最大。

        O(n)：max over i<j,k>j of min(v[i],v[k]) == min(max_{i<j}v[i], max_{k>j}v[k])。
        """
        n = len(vals)
        if n < 3:
            return (0.0, 0, 0, 0)
        pre, m = [0.0] * n, -1e9
        for i, x in enumerate(vals):
            m = max(m, x)
            pre[i] = m
        suf, m = [0.0] * n, -1e9
        for i in range(n - 1, -1, -1):
            m = max(m, vals[i])
            suf[i] = m
        best = (0.0, 0, 0, 0)
        for j in range(1, n - 1):
            hi = min(pre[j - 1], suf[j + 1])
            if hi <= (0.05 if rel else 1e-9):
                continue
            d = (hi - vals[j]) / hi if rel else hi - vals[j]
            if d > best[0]:
                best = (d, j, vals[j], hi)
        return best

    pre_t = [t for t in tags if float(t) < 15.70]
    print(f'  动作在 {tags[CUT] if CUT < len(tags) else "?"}s 之后整段重排（473→491 片同时移动、'
          f'Param25/27 钳住）⇒ 同时给「全窗」与「重排前 {pre_t[0]}–{pre_t[-1]}s」两个深度')
    for title, book, fv, fd in (('op', ops, '%.2f', '%.2f'), ('面积', ars, '%.1f', '%.0f%%')):
        rel = title == '面积'
        top = sorted(names, key=lambda n: -dips(book[n], rel)[0])[:12]
        print(f'\n  == {title} 瞬断前 12（序列里 * 标谷底）==')
        for n in top:
            v = book[n]
            d, j, lo, hi = dips(v, rel)
            dp = dips(v[:len(pre_t)], rel)
            s = ' '.join((fv + ('*' if i == j else ' ')) % x for i, x in enumerate(v))
            print(f'    {n:14s} 全窗 {fd % d:>5}（{fv % hi}→{fv % lo} @{tags[j]}s）  '
                  f'重排前 {fd % dp[0]:>5}  {s}')


def twice_main(path):
    """同一页面会话两遍对照：p1_*（刚加载）vs p2_*（纹理/网格/着色器全热）逐帧逐片比。

    判据（先写死再跑）：
      两遍逐片 op 最大差 ≤0.02 且画布差 ≤0.1%  ⇒ 「新的手没预加载 / 晚到一步」当场判死，
                                                  消失是数据里就有的淡变；
      只有 p1 缺（p1 某族 op 明显低于 p2）      ⇒ 加载时机说成立，去查上传/编译时机。
    """
    import numpy as np
    from PIL import Image
    d = os.path.dirname(path)
    S = json.load(open(path, encoding='utf-8'))
    tags = sorted(k[3:] for k in S if k.startswith('p1_'))
    # 前置校验：两遍必须落在同一条 clip 的同一拍上。参数轨迹对不上就作废，别去比像素。
    off = [(t, k, S['p1_' + t]['snap']['p'].get(k), S['p2_' + t]['snap']['p'].get(k))
           for t in tags if S.get('p2_' + t) for k in ('Param25', 'Param27')
           if None not in (S['p1_' + t]['snap']['p'].get(k), S['p2_' + t]['snap']['p'].get(k))
           and abs(S['p1_' + t]['snap']['p'][k] - S['p2_' + t]['snap']['p'][k]) > 0.05]
    if off:
        print(f'对照作废：{len(off)} 处两遍参数轨迹对不上（前 6 条）—— 下面的任何差值都不许引用')
        for t, k, va, vb in off[:6]:
            print(f'  {t}s {k}: p1={va} p2={vb}')
        print('⇒ 先确认两遍都真的在播 home（l2d_wrist_ledger.py 的 start_play 会验真并报错）。')
        return
    print(f'{"帧":>6} {"op最大差":>8} {"差>0.02":>7} {"画布Δ":>7}  两遍一致?')
    for t in tags:
        a, b = S.get('p1_' + t), S.get('p2_' + t)
        if not a or not b:
            print(f'{t:>6}  缺遍（--twice 没开？）')
            continue
        ra = {r[0]: r for r in a['snap']['rows']}
        rb = {r[0]: r for r in b['snap']['rows']}
        dif = sorted(((abs(ra[n][4] - rb[n][4]), n, ra[n][4], rb[n][4]) for n in ra if n in rb),
                     key=lambda x: -x[0])
        big = [x for x in dif if x[0] > 0.02]
        ia = Image.open(os.path.join(d, f'p1_{t}.png')).convert('RGB')
        ib = Image.open(os.path.join(d, f'p2_{t}.png')).convert('RGB')
        px = 0.0
        if ia.size == ib.size:
            x = np.asarray(ia, dtype=int) - np.asarray(ib, dtype=int)
            px = 100.0 * int((np.abs(x).max(axis=2) > 8).sum()) / (x.shape[0] * x.shape[1])
        same = not big and px <= 0.1
        print(f'{t:>6} {dif[0][0] if dif else 0:8.3f} {len(big):7d} {px:6.2f}%  '
              + ('是' if same else '否 ← ' + ', '.join(f'{n} {x:.2f}→{y:.2f}' for _, n, x, y in dif[:5])))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--twice' in sys.argv:
        twice_main(sys.argv[sys.argv.index('--twice') + 1])
    elif '--sweep' in sys.argv:
        sweep_main(sys.argv[sys.argv.index('--sweep') + 1])
    else:
        main()
