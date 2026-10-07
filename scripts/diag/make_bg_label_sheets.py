#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_bg_label_sheets.py — 把场景背景拼成 5×5 标注板，供"图里有没有角色"的视觉标注用。

为什么要标注而不是用规则：实测「名字含 `_cg`」这条规则精确率 86% / 召回率 79%
（分层抽 48 张目视得出），当预筛够用，当**默认视图**不够 —— 漏掉的 21% 会被静默藏掉。
详见 docs/TROUBLESHOOTING.md §118 的抽样口径。

产物：
  .diag/bglabels/sheet_<NN>.png   每格左上角印 **全局序号**（不是板内序号，避免跨板错位）
  .diag/bglabels/manifest.json    序号 -> `<类目>/<名>`，以及每板的 key 列表
  .diag/bglabels/expected.json    该板的序号清单（校验器据此判"漏格/编造序号"）
  .diag/bglabels/prior_<NN>.json  该板的 `_cg` 规则预测，只作**事后交叉核对**用

用法:
  py -3 scripts/diag/make_bg_label_sheets.py            # 全量场景背景
  py -3 scripts/diag/make_bg_label_sheets.py --limit 24 # 先出一板试读图效果
"""
import argparse
import collections
import json
import os
import re
import sys

from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
META = os.path.join(ROOT, 'Output', 'gallery_v2', 'bg_meta.json')
OUT = os.path.join(ROOT, '.diag', 'bglabels')
CELL_W, COLS, ROWS = 300, 5, 5
CG = re.compile(r'_?cg[_]?\d*$')


def build(limit=None):
    items = [i for i in json.load(open(META, encoding='utf-8'))['items']
             if i['group'] == 'scene']
    items.sort(key=lambda i: i['key'])
    if limit:
        items = items[:limit]
    os.makedirs(OUT, exist_ok=True)
    manifest, sheets = {}, []
    prior_all = {}
    cell_h = CELL_W * 9 // 16 + 26
    for si in range(0, len(items), COLS * ROWS):
        chunk = items[si:si + COLS * ROWS]
        n = len(chunk)
        rows = (n + COLS - 1) // COLS
        S = Image.new('RGB', (COLS * CELL_W, rows * cell_h), (18, 18, 22))
        d = ImageDraw.Draw(S)
        expect = []
        prior = {}
        for k, it in enumerate(chunk):
            g = si + k                          # 全局序号
            expect.append(g)
            manifest[str(g)] = it['key']
            prior[str(g)] = 1 if CG.search(it['name']) else 0
            x, y = (k % COLS) * CELL_W, (k // COLS) * cell_h
            p = os.path.join(ROOT, 'Output', it['img'][3:])
            try:
                im = Image.open(p).convert('RGB')
                im.thumbnail((CELL_W, cell_h - 26))
                S.paste(im, (x, y))
            except Exception as e:
                d.text((x + 6, y + 6), 'ERR ' + str(e)[:24], fill=(255, 90, 90))
            # 深色底 + 亮字：缩略图再暗，序号也得读得出来
            d.rectangle([x, y + cell_h - 26, x + CELL_W, y + cell_h], fill=(232, 238, 248))
            # 格子里**只印序号、不印文件名**：文件名里的 `_cg` 就是那条待核对的规则，
            # 印出来等于把答案写在考卷上 —— 标注必须与先验独立，交叉核对才有意义。
            d.text((x + 5, y + cell_h - 23), '#%d' % g, fill=(8, 8, 10))
        name = 'sheet_%02d.png' % (len(sheets) + 1)
        S.save(os.path.join(OUT, name))
        sheets.append(name)
        json.dump(expect, open(os.path.join(OUT, 'expected_%02d.json' % len(sheets)), 'w'),
                  ensure_ascii=False)
        json.dump(prior, open(os.path.join(OUT, 'prior_%02d.json' % len(sheets)), 'w'),
                  ensure_ascii=False)
        prior_all.update(prior)
    json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    print('场景背景 %d 张 -> %d 板（每板 %d 格） 产物在 %s'
          % (len(items), len(sheets), COLS * ROWS, os.path.relpath(OUT, ROOT)))
    n_p = sum(1 for v in prior_all.values() if v)
    print('其中 `_cg` 规则预测为"有角色"的：%d 张（%d%%）—— 只作事后交叉核对，不是标注结果'
          % (n_p, 100 * n_p // max(1, len(prior_all))))
    return sheets


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int)
    build(ap.parse_args().limit)
