#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_bg_adjudicate_sheet.py — 把标注板里判为「不确定」(`2`) 的格子导出成整图，供逐格目视裁定。

为什么单独出图：拼板每格只有 300px，"人物极小/被前景挡住"这类边界格在这个尺寸上
判不出来；裁定会直接决定背景页的**默认视图**，必须看全分辨率。

产物：
  .diag/bglabels/adjudicate/cell_<N>_<名>.png   等比缩到长边 <=1000（原图 1024~1920，不放大）
  .diag/bglabels/adjudicate/zoom_<N>_<x>_<y>.png  指定格的 2x 局部（--zoom 给出，用于小人物复核）
  .diag/bglabels/adjudicate/index.json           N -> {key, name, src, w, h}

用法:
  py -3 scripts/diag/make_bg_adjudicate_sheet.py                 # 导出全部 `2` 格
  py -3 scripts/diag/make_bg_adjudicate_sheet.py --zoom 616      # 再对 616 号出 3x3 九宫格局部
"""
import argparse
import glob
import json
import os
import sys

from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(ROOT, 'Output', 'Raw')
OUT = os.path.join(ROOT, '.diag', 'bglabels', 'adjudicate')
MAX_SIDE = 1000


def load_labels():
    labels = {}
    for f in sorted(glob.glob(os.path.join(ROOT, '.diag', 'bglabels', 'labels_part*.json'))):
        labels.update({int(k): int(v) for k, v in json.load(open(f, encoding='utf-8')).items()})
    return labels


def src_path(key):
    d, name = key.split('/', 1)
    p = os.path.join(RAW, d, name + '.png')
    if not os.path.exists(p):                      # 拼板里可能是 <name>__2 这种后缀
        alt = os.path.join(RAW, d, name + '.png')
        return alt
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zoom', action='append', default=[], help='对指定序号出 3x3 局部放大')
    args = ap.parse_args()
    labels = load_labels()
    manifest = json.load(open(os.path.join(ROOT, '.diag', 'bglabels', 'manifest.json'),
                              encoding='utf-8'))
    os.makedirs(OUT, exist_ok=True)
    idx = {}
    todo = sorted(n for n, v in labels.items() if v == 2)
    for n in todo:
        key = manifest[str(n)]
        p = src_path(key)
        if not os.path.exists(p):
            print('MISSING %s -> %s' % (key, os.path.relpath(p, ROOT)))
            continue
        im = Image.open(p).convert('RGB')
        w, h = im.size
        scale = min(1.0, MAX_SIDE / max(w, h))
        out = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS) if scale < 1.0 else im
        name = 'cell_%04d_%s.png' % (n, os.path.basename(key))
        out.save(os.path.join(OUT, name))
        idx[n] = {'key': key, 'file': name, 'w': w, 'h': h, 'view': out.size}
        print('#%d  %-40s 原 %dx%d  视图 %dx%d' % (n, key, w, h, out.width, out.height))
    for s in args.zoom:
        n = int(s)
        rec = idx.get(n) or json.load(open(os.path.join(OUT, 'index.json'), encoding='utf-8')).get(str(n))
        p = src_path(rec['key'])
        im = Image.open(p).convert('RGB')
        w, h = im.size
        for ry in range(3):
            for rx in range(3):
                box = (rx * w // 3, ry * h // 3, (rx + 1) * w // 3, (ry + 1) * h // 3)
                c = im.crop(box)
                c = c.resize((c.width * 2, c.height * 2), Image.LANCZOS)
                c.save(os.path.join(OUT, 'zoom_%04d_%d_%d.png' % (n, rx, ry)))
        print('#%d 九宫格局部 -> zoom_%04d_r_c.png（3x3，2 倍放大）' % (n, n))
    json.dump(idx, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('共 %d 格，产物在 %s' % (len(idx), os.path.relpath(OUT, ROOT)))


if __name__ == '__main__':
    main()
