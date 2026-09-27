# -*- coding: utf-8 -*-
"""按清单重渲立绘 + 与在盘产物逐像素比对 + 自动分诊（只写临时目录，不碰正式产物）。

分诊口径沿用 §14 的「按脸谱落笔足迹量旧像素」，落在**实际发生差异的区域**上：
  透明      = 底图这里没画（真洞，换入是修）
  不透明白灰 = 画了一块平涂占位（真洞，换入是修；§48 新查出的那一类）
  不透明彩色 = 这里本来就有一张画好的脸（叠上去=换表情，属回退，必须人工裁定）

用法：py -3 scripts/diag/painting_face_rerun.py --list .diag/face_holes_20260927.txt
      [--out .diag/facefix_rerun] [--tsv .diag/face_rerun_diff.tsv] [--limit N]
"""
import sys, os, hashlib, argparse, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from PIL import Image
import compose_paintings_v2 as C

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', '..'))
DISK = os.path.join(ROOT, 'Output', 'Paintings_v2')


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def classify(a, b):
    """返回 (差异像素数, 差异区, 旧图在该区域的三类占比)"""
    w, h = min(a.width, b.width), min(a.height, b.height)
    aa = np.asarray(a.crop((0, 0, w, h))).astype(np.int32)
    bb = np.asarray(b.crop((0, 0, w, h))).astype(np.int32)
    d = np.abs(aa - bb).max(axis=2) > 0
    n = int(d.sum())
    if not n:
        return 0, None, None
    ys, xs = np.where(d)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    sub = aa[box[1]:box[3], box[0]:box[2]]
    al, rgb = sub[..., 3], sub[..., :3]
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    tot = al.size
    return (n, box, (float((al < 250).sum()) / tot,
                     float(((al >= 250) & (sat < 30)).sum()) / tot,
                     float(((al >= 250) & (sat >= 30)).sum()) / tot))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', required=True)
    ap.add_argument('--out', default='.diag/facefix_rerun')
    ap.add_argument('--tsv', default='.diag/face_rerun_diff.tsv')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    out = os.path.join(ROOT, a.out) if not os.path.isabs(a.out) else a.out
    tsv = os.path.join(ROOT, a.tsv) if not os.path.isabs(a.tsv) else a.tsv
    os.makedirs(out, exist_ok=True)
    names = [l.strip() for l in open(os.path.join(ROOT, a.list) if not os.path.isabs(a.list) else a.list,
                                     encoding='utf-8') if l.strip()]
    if a.limit:
        names = names[:a.limit]
    print(f'清单 {len(names)} 个，重渲到 {out}', flush=True)

    rows = []
    t0 = time.time()
    for i, s in enumerate(names, 1):
        C.FACE_GATE.pop(s, None)
        disk = os.path.join(DISK, f'{s}.png')
        new = os.path.join(out, f'{s}.png')
        try:
            ok = C.compose(s, out, save=True)
        except Exception as e:
            ok = False
            print(f'  ERR {s}: {e}', flush=True)
        g = C.FACE_GATE.get(s) or {}
        if not ok or not os.path.isfile(new) or not os.path.isfile(disk):
            rows.append((s, 'missing', -1, '', '', '', g.get('frac_opaque', -1),
                         -1 if g.get('mad') is None else g['mad']))
            continue
        same = md5(disk) == md5(new)
        sizechg = ''
        if same:
            nd, box, cls = 0, None, None
        else:
            A = Image.open(disk).convert('RGBA')
            B = Image.open(new).convert('RGBA')
            nd, box, cls = classify(A, B)
            if A.size != B.size:
                sizechg = f'{A.width}x{A.height}->{B.width}x{B.height}'
            A.close(); B.close()
        rows.append((s, 'same' if same else 'diff', nd,
                     '' if cls is None else f'{cls[0]:.2f}/{cls[1]:.2f}/{cls[2]:.2f}',
                     '' if box is None else f'{box[0]},{box[1]},{box[2]},{box[3]}',
                     sizechg, g.get('frac_opaque', -1),
                     -1 if g.get('mad') is None else g['mad']))
        if i % 20 == 0 or i == len(names):
            dt = time.time() - t0
            print(f'  进度 {i}/{len(names)}  需换入 {sum(1 for r in rows if r[1]=="diff")}  '
                  f'用时 {dt:.0f}s  预计还需 {dt/i*(len(names)-i)/60:.1f} 分钟', flush=True)

    with open(tsv, 'w', encoding='utf-8') as f:
        f.write('stem\tstate\tdiffpx\t旧图透明/白灰/彩色\tdiffbox\t尺寸变化\tfrac_opaque\tmad\n')
        for r in rows:
            f.write('\t'.join(str(x) for x in r) + '\n')
    n_same = sum(1 for r in rows if r[1] == 'same')
    n_diff = [r for r in rows if r[1] == 'diff']
    n_miss = sum(1 for r in rows if r[1] == 'missing')
    # 分诊：差异区旧图三类里谁占大头
    def verdict(r):
        cls = r[3]
        if not cls:
            return 'same'
        tr, gr, co = (float(x) for x in cls.split('/'))
        if co >= 0.5:
            return '旧图已有彩色画(回退风险,须目视)'
        if gr >= 0.5:
            return '旧图不透明白灰块(真洞)'
        return '旧图透明洞(真洞)'
    vs = {}
    for r in n_diff:
        vs[verdict(r)] = vs.get(verdict(r), 0) + 1
    print(f'\n完成：与在盘相同 {n_same} / 有差异 {len(n_diff)} / 缺文件 {n_miss}，'
          f'总用时 {time.time()-t0:.0f}s')
    for k, v in sorted(vs.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v}')
    print(f'明细 -> {tsv}')
    with open(tsv + '.swaplist', 'w', encoding='utf-8') as f:
        for r in n_diff:
            f.write(r[0] + '\n')
    print(f'待换入清单 -> {tsv}.swaplist ({len(n_diff)})')


if __name__ == '__main__':
    main()
