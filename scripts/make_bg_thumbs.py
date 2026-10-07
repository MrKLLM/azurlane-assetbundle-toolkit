#!/usr/bin/env python3
"""make_bg_thumbs.py — 为 `Output/Raw/` 背景图生成画廊缩略图 `gallery_v2/bg_thumbs/<类目>/<名>.webp`。

为什么单独一套目录而不是复用 `thumbs/`：背景图里有**同名跨类目**（实测 `bg_1` 同时在
`loadingbg` / `loadingbg_hx` / `newshipbg`，内容还不一样），扁平目录会互相覆盖。

`--check` 只数不写；缺缩略图的类目/张数会打出来，收尾用来自证"页面每个格子都有图"。
增量：存在即 skip，可反复跑。

用法:
  py -3 scripts/make_bg_thumbs.py            # 全量（已存在的跳过）
  py -3 scripts/make_bg_thumbs.py --limit 30 # 小样本试跑，估时间与体积
  py -3 scripts/make_bg_thumbs.py --check     # 只报缺哪些，不写
"""
import argparse
import glob
import json
import os
import sys
from multiprocessing import Pool

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW = os.path.join(ROOT, 'Output', 'Raw')
TDIR = os.path.join(ROOT, 'Output', 'gallery_v2', 'bg_thumbs')
META = os.path.join(ROOT, 'Output', 'gallery_v2', 'bg_meta.json')
MAXW = 400


def out_path(key):
    d, name = key.split('/', 1)
    return os.path.join(TDIR, d, name + '.webp')


def work(key):
    d, name = key.split('/', 1)
    src = os.path.join(RAW, d, name + '.png')
    out = out_path(key)
    if os.path.exists(out):
        return ('skip', key)
    try:
        im = Image.open(src)
        im.load()
        w, h = im.size
        if w > MAXW:
            im = im.resize((MAXW, int(h * MAXW / w)), Image.LANCZOS)
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        im.save(out, 'WEBP', quality=80)
        return ('ok', key)
    except Exception as e:
        return ('err', '%s: %s' % (key, str(e)[:70]))


def all_keys():
    return ['%s/%s' % (d, f[:-4]) for d in sorted(os.listdir(RAW))
            if os.path.isdir(os.path.join(RAW, d))
            for f in sorted(os.listdir(os.path.join(RAW, d))) if f.endswith('.png')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, help='只处理前 N 张（估时间/体积用）')
    ap.add_argument('--check', action='store_true', help='只报缺哪些，不写文件')
    a = ap.parse_args()

    keys = all_keys()
    if a.check:
        miss = [k for k in keys if not os.path.isfile(out_path(k))]
        print('盘上背景图 %d 张 / 缩略图缺 %d 张' % (len(keys), len(miss)))
        if miss:
            print('  缺的样例:', miss[:5])
        # 反向对照：索引里每张图都必须有缩略图，否则页面会出现点不开的格子
        if os.path.isfile(META):
            items = json.load(open(META, encoding='utf-8'))['items']
            m2 = [i['key'] for i in items if not os.path.isfile(out_path(i['key']))]
            print('bg_meta.json 里 %d 条 / 其中缩略图缺 %d 条' % (len(items), len(m2)))
            return 1 if m2 else 0
        return 1 if miss else 0

    if a.limit:
        keys = keys[:a.limit]
    total = len(keys)
    print('待生成 %d 张（最大宽 %d px）' % (total, MAXW), flush=True)
    ok = skip = err = 0
    errs = []
    with Pool(processes=max(1, os.cpu_count() - 1)) as pool:
        for i, (st, name) in enumerate(pool.imap_unordered(work, keys, chunksize=16), 1):
            if st == 'ok':
                ok += 1
            elif st == 'skip':
                skip += 1
            else:
                err += 1
                errs.append(name)
            if i % 250 == 0 or i == total:
                print('%d/%d ok=%d skip=%d err=%d' % (i, total, ok, skip, err), flush=True)
    made = glob.glob(os.path.join(TDIR, '**', '*.webp'), recursive=True)
    print('完成 ok=%d skip=%d err=%d / 目录现有 %d 张 / %.1f MB'
          % (ok, skip, err, len(made), sum(os.path.getsize(p) for p in made) / 1e6))
    if errs:
        open(os.path.join(TDIR, '_err.txt'), 'w', encoding='utf-8').write('\n'.join(errs))
    return 1 if err else 0


if __name__ == '__main__':
    sys.exit(main())
