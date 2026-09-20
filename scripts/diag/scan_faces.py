# -*- coding: utf-8 -*-
"""扫描所有「有 paintingface 包」的立绘皮肤，用门控渲染判定哪些是脸洞(需叠脸)。
只渲染不落盘(save=False)，把触发叠脸的皮肤写入 .diag/face_holes.txt。"""
import sys, os, glob, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import compose_paintings_v2 as C

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'Output')
pf = set(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, 'files', 'AssetBundles', 'paintingface', '*')) if os.path.isfile(p))
stems = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(OUT, 'Paintings_v2', '*.png')))
cands = [s for s in stems if s in pf]
print(f'候选 {len(cands)} 个，开始扫描…', flush=True)

tmp = os.path.join(ROOT, '.diag', 'face_scan_tmp')
os.makedirs(tmp, exist_ok=True)
holes = []
errs = 0
t0 = time.time()
for i, s in enumerate(cands, 1):
    try:
        C.compose(s, tmp, save=False)
        if C.FACE_APPLIED.get(s):
            holes.append(s)
    except Exception as e:
        errs += 1
        if errs <= 20: print(f'  ERR {s}: {e}', flush=True)
    if i % 100 == 0:
        print(f'  进度 {i}/{len(cands)}  已发现脸洞 {len(holes)}  用时 {time.time()-t0:.0f}s  err={errs}', flush=True)

io = open(os.path.join(ROOT, '.diag', 'face_holes.txt'), 'w', encoding='utf-8')
io.write('\n'.join(holes))
io.close()
print(f'完成：候选 {len(cands)}，脸洞 {len(holes)}，err {errs}，总用时 {time.time()-t0:.0f}s', flush=True)
print('脸洞清单 -> .diag/face_holes.txt', flush=True)
