# -*- coding: utf-8 -*-
"""全库普查「磁盘立绘产物 vs 当前管线重渲」是否一致 —— 只出清单，不动任何正式产物。

为什么要它：§6.11 查 moermansike_2 时发现，正式目录里有些文件是 09-15 那批渲染留下的，
之后落地的系统性修复（叠脸判据、mesh 越框、嵌套容器错位…）**从没落到它们身上**。
只按脸槽扫是看不见的（本轮 haman_4 就是整条身子缺失，差异覆盖全图）。
所以要把「当前管线画出来的是什么」和「盘上现在是什么」逐张对一遍。

判据：同一条渲染路径（compose(save=True) 到临时目录）→ 与在盘文件比 md5；
不同则再量差异像素数 + 差异外接框 + 尺寸变化，供分诊（脸槽内 / 全图 / 仅尺寸）。
临时文件**逐张删除**，避免在 .diag 里堆出十几 GB。

用法: py -3 scripts/diag/painting_staleness_scan.py [--stamp 20260927] [--limit N] [--resume]
产物: .diag/stale_<stamp>.tsv（逐条落盘） + .diag/stale_<stamp>.diff.txt（差异清单）
"""
import sys, os, glob, time, hashlib, argparse, gc
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from PIL import Image
import compose_paintings_v2 as C

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', '..'))
DIR = os.path.join(ROOT, 'Output', 'Paintings_v2')
TSV_HEAD = 'stem\tstate\tdiffpx\tdiffbox\t尺寸变化\tdisk_MB\tnew_MB\n'


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def diff_stats(a, b):
    ia = Image.open(a).convert('RGBA')
    ib = Image.open(b).convert('RGBA')
    sizechg = '' if ia.size == ib.size else f'{ia.width}x{ia.height}->{ib.width}x{ib.height}'
    w, h = min(ia.width, ib.width), min(ia.height, ib.height)
    aa = np.asarray(ia.crop((0, 0, w, h)), dtype=np.int16)
    bb = np.asarray(ib.crop((0, 0, w, h)), dtype=np.int16)
    ia.close(); ib.close()
    m = np.abs(aa - bb).max(axis=2) > 0
    n = int(m.sum())
    if not n:
        return 0, '', sizechg
    ys, xs = np.where(m)
    return n, f'{int(xs.min())},{int(ys.min())},{int(xs.max())+1},{int(ys.max())+1}', sizechg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stamp', default=time.strftime('%Y%m%d'))
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--only', default='', help='逗号分隔的皮肤名（小样本自测）')
    a = ap.parse_args()
    tmp = os.path.join(ROOT, '.diag', 'stale_tmp')
    os.makedirs(tmp, exist_ok=True)
    tsv = os.path.join(ROOT, '.diag', f'stale_{a.stamp}.tsv')
    dfp = os.path.join(ROOT, '.diag', f'stale_{a.stamp}.diff.txt')

    stems = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(DIR, '*.png')))
    if a.only:
        stems = [s.strip() for s in a.only.split(',') if s.strip()]
    if a.limit:
        stems = stems[:a.limit]
    done, diffs = set(), []
    if a.resume and os.path.isfile(tsv):
        with open(tsv, encoding='utf-8') as f:
            for line in f:
                c = line.rstrip('\n').split('\t')
                if len(c) >= 2 and c[0] != 'stem':
                    done.add(c[0])
                    if c[1] == 'diff':
                        diffs.append(c[0])
        print(f'续跑：已在册 {len(done)}（其中差异 {len(diffs)}），跳过', flush=True)
    stems = [s for s in stems if s not in done]
    print(f'待比对 {len(stems)} 张', flush=True)

    anew = not (a.resume and os.path.isfile(tsv))
    rf = open(tsv, 'w' if anew else 'a', encoding='utf-8', newline='\n')
    if anew:
        rf.write(TSV_HEAD)
    t0 = time.time()
    n_diff = n_err = n_skip = 0
    try:
        for i, s in enumerate(stems, 1):
            disk = os.path.join(DIR, f'{s}.png')
            new = os.path.join(tmp, f'{s}.png')
            try:
                ok = C.compose(s, tmp, save=True)
                if not ok or not os.path.isfile(new):
                    rf.write(f'{s}\tnorender\t0\t\t\t\t\n')
                    n_err += 1
                elif md5(disk) == md5(new):
                    rf.write(f'{s}\tsame\t0\t\t\t{os.path.getsize(disk)/1048576:.2f}\t\n')
                else:
                    nd, box, sizechg = diff_stats(disk, new)
                    rf.write(f'{s}\tdiff\t{nd}\t{box}\t{sizechg}\t'
                             f'{os.path.getsize(disk)/1048576:.2f}\t{os.path.getsize(new)/1048576:.2f}\n')
                    diffs.append(s)
                    n_diff += 1
                    print(f'  差异 {s}: {nd}px box={box} {sizechg}', flush=True)
            except Exception as e:
                rf.write(f'{s}\terr\t0\t\t\t\t\n')
                n_err += 1
                if n_err <= 20:
                    print(f'  ERR {s}: {str(e)[:120]}', flush=True)
            finally:
                if os.path.isfile(new):
                    os.remove(new)          # 逐张删，别在 .diag 堆十几 GB
            if i % 10 == 0:
                rf.flush()
                gc.collect()
            if i % 100 == 0:
                dt = time.time() - t0
                print(f'  进度 {i}/{len(stems)}  差异 {n_diff}  不出 {n_skip}  err {n_err}  用时 {dt:.0f}s  '
                      f'预计还需 {dt/i*(len(stems)-i)/60:.0f} 分钟', flush=True)
    finally:
        rf.flush()
        rf.close()
    with open(dfp, 'w', encoding='utf-8') as f:
        f.write('\n'.join(diffs))
    print(f'完成：比对 {len(stems)}，差异 {n_diff}，渲染不出/缺件 {n_skip}，'
          f'异常 {n_err}，总用时 {time.time()-t0:.0f}s', flush=True)
    print(f'明细 -> {tsv}\n差异清单 -> {dfp}（{len(diffs)}）')


if __name__ == '__main__':
    main()
