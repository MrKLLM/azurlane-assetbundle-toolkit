#!/usr/bin/env python3
"""为 Paintings_v2 高清 PNG 生成本地缩略图 gallery_v2/thumbs/<stem>.webp（含透明）。"""
import sys, os, glob, json
from multiprocessing import Pool
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'Output', 'Paintings_v2')
TDIR = os.path.join(ROOT, 'Output', 'gallery_v2', 'thumbs')
os.makedirs(TDIR, exist_ok=True)
MAXW = 380  # 缩略图最大宽

def work(png):
    stem = os.path.splitext(os.path.basename(png))[0]
    out = os.path.join(TDIR, stem + '.webp')
    if os.path.exists(out):
        return ('skip', stem)
    try:
        im = Image.open(png)
        im.load()
        w, h = im.size
        if w > MAXW:
            im = im.resize((MAXW, int(h * MAXW / w)), Image.LANCZOS)
        if im.mode not in ('RGBA', 'RGB'):
            im = im.convert('RGBA')
        im.save(out, 'WEBP', quality=82)
        return ('ok', stem)
    except Exception as e:
        return ('err', stem + ':' + str(e)[:60])

if __name__ == '__main__':
    files = sorted(glob.glob(os.path.join(SRC, '*.png')))
    total = len(files)
    print('待生成', total, flush=True)
    ok = skip = err = 0
    errs = []
    with Pool(processes=max(1, os.cpu_count() - 1)) as pool:
        for i, (st, name) in enumerate(pool.imap_unordered(work, files, chunksize=16), 1):
            if st == 'ok': ok += 1
            elif st == 'skip': skip += 1
            else: err += 1; errs.append(name)
            if i % 250 == 0 or i == total:
                print(f'{i}/{total} ok={ok} skip={skip} err={err}', flush=True)
    if errs:
        open(os.path.join(TDIR, '_err.txt'), 'w', encoding='utf-8').write('\n'.join(errs))
    print(f'完成 ok={ok} skip={skip} err={err}', flush=True)
