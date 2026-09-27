# -*- coding: utf-8 -*-
"""按「prefab 里关闭的图层」清单定向重渲 + 与在盘逐像素比对 + 出改前/改后对照总表。
**只写临时目录，不碰 Output/Paintings_v2。**

配套取证脚本：painting_inactive_scan.py（只读扫全库，出清单）。
过滤动作**已经在 compose_paintings_v2.parse_painting/compose 里落码**，本脚本直接调
`C.compose`，从 `C.INACTIVE_SKIPPED` / `C.INACTIVE_ALL` 读它实际跳过了什么 ——
即「对照图走的正是生产路径」，不是在这里另算一遍判据。

用法:
  py -3 scripts/diag/painting_inactive_rerun.py --list .diag/inactive_20260927b.tsv \
      [--out .diag/inactivefix_rerun] [--sheet .diag/inactivefix_cmp] [--limit N] [--only a,b]
产物:
  <out>/<stem>.png            重渲结果
  <out>/_report.json          逐张差异像素数 / 差异包围盒 / 被去掉的层名
  <sheet>/sheet_kk.png        改前|改后 对照总表（按差异面积降序，每页 8 行）
"""
import sys, os, csv, json, time, argparse, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import compose_paintings_v2 as C

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', '..'))
DISK = os.path.join(ROOT, 'Output', 'Paintings_v2')


def diff_stats(disk_png, new_png):
    a = Image.open(disk_png).convert('RGBA')
    b = Image.open(new_png).convert('RGBA')
    sizechg = '' if a.size == b.size else f'{a.width}x{a.height}->{b.width}x{b.height}'
    w, h = min(a.width, b.width), min(a.height, b.height)
    aa = np.asarray(a.crop((0, 0, w, h))).astype(np.int16)
    bb = np.asarray(b.crop((0, 0, w, h))).astype(np.int16)
    a.close(); b.close()
    m = np.abs(aa - bb).max(axis=2) > 0
    n = int(m.sum())
    if not n:
        return 0, None, sizechg
    ys, xs = np.where(m)
    return n, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), sizechg


def build_sheet(rows, sheet_dir, per_page=8, cell=380):
    try:
        F = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 20)
        Fs = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 15)
    except Exception:
        F = Fs = ImageFont.load_default()
    os.makedirs(sheet_dir, exist_ok=True)
    pages = [rows[i:i + per_page] for i in range(0, len(rows), per_page)] or [[]]
    out = []
    for pi, page in enumerate(pages, 1):
        W = cell * 2 + 24
        H = (cell + 58) * len(page) + 40
        sheet = Image.new('RGB', (W, H), (18, 20, 26))
        d = ImageDraw.Draw(sheet)
        d.text((12, 10), f'关闭图层过滤 改前(左)|改后(右)  第 {pi}/{len(pages)} 页', font=F, fill=(230, 230, 235))
        y = 40
        for r in page:
            A = Image.open(r['disk']).convert('RGBA')
            B = Image.open(r['new']).convert('RGBA')
            box = r['box']
            if box:
                w = max(1, box[2] - box[0]); h = max(1, box[3] - box[1])
                pad = int(max(w, h) * 0.12)
                cx0 = max(0, box[0] - pad); cy0 = max(0, box[1] - pad)
                cx1 = min(min(A.width, B.width), box[2] + pad)
                cy1 = min(min(A.height, B.height), box[3] + pad)
                crop = (cx0, cy0, cx1, cy1)
            else:
                crop = (0, 0, min(A.width, B.width), min(A.height, B.height))
            tiles = []
            for im in (A, B):
                c = im.crop(crop)
                s = min(cell / max(1, c.width), (cell) / max(1, c.height))
                tiles.append(c.resize((max(1, int(c.width * s)), max(1, int(c.height * s))), Image.LANCZOS))
            for k, t in enumerate(tiles):
                bg = Image.new('RGBA', (cell, cell), (12, 14, 20, 255))
                bg.paste(t, ((cell - t.width) // 2, (cell - t.height) // 2), t)
                sheet.paste(bg.convert('RGB'), (12 + k * (cell + 12), y))
            d.text((12, y + cell + 2),
                   f"{r['stem']}  差异 {r['diffpx']:,}px  去掉: {','.join(r['layers'])}  {r['sizechg']}",
                   font=Fs, fill=(200, 205, 215))
            y += cell + 58
        p = os.path.join(sheet_dir, f'sheet_{pi:02d}.png')
        sheet.save(p)
        out.append(p)
        A.close(); B.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', required=True, help='painting_inactive_scan 产出的 TSV')
    ap.add_argument('--out', default=os.path.join(ROOT, '.diag', 'inactivefix_rerun'))
    ap.add_argument('--sheet', default=os.path.join(ROOT, '.diag', 'inactivefix_cmp'))
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only', default='')
    a = ap.parse_args()

    stems = sorted({r[0] for r in list(csv.reader(open(a.list, encoding='utf-8'), delimiter='\t'))[1:]})
    if a.only:
        want = {s.strip() for s in a.only.split(',') if s.strip()}
        stems = [s for s in stems if s in want]
    if a.limit:
        stems = stems[:a.limit]

    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    rows = []
    same = blank = err = 0
    for i, s in enumerate(stems, 1):
        disk = os.path.join(DISK, f'{s}.png')
        new = os.path.join(a.out, f'{s}.png')
        try:
            C.INACTIVE_SKIPPED.pop(s, None)
            if not C.compose(s, a.out, save=True):
                raise RuntimeError('compose 返回 False')
            if s in C.INACTIVE_ALL:
                blank += 1
                print(f'  ⚠️ {s}: 全层关闭态，本次未过滤（原样保留）', flush=True)
                continue
            nd, box, sizechg = diff_stats(disk, new)
            if nd == 0 and not sizechg:
                same += 1
                print(f'  = {s}: 与在盘逐像素相同（该层实际没落笔？）', flush=True)
                continue
            rows.append({'stem': s, 'disk': disk, 'new': new, 'diffpx': nd,
                         'box': box, 'sizechg': sizechg,
                         'layers': C.INACTIVE_SKIPPED.get(s, [])})
        except Exception as e:
            err += 1
            print(f'  ERR {s}: {str(e)[:140]}', flush=True)
        if i % 20 == 0:
            print(f'  进度 {i}/{len(stems)} 有变化 {len(rows)} 相同 {same} 全关 {blank} err {err} '
                  f'用时 {time.time() - t0:.0f}s', flush=True)

    rows.sort(key=lambda r: -r['diffpx'])
    json.dump(rows, open(os.path.join(a.out, '_report.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('=' * 70)
    print(f'清单 {len(stems)} 张 → 有变化 {len(rows)} / 逐像素相同 {same} / 全层关闭跳过 {blank} / err {err}'
          f'  用时 {time.time() - t0:.0f}s')
    cnt = collections.Counter()
    for r in rows:
        for l in r['layers']:
            cnt[l] += 1
    print('被去掉的层名分布:', dict(cnt.most_common()))
    if rows:
        pages = build_sheet(rows, a.sheet)
        print(f'对照总表 {len(pages)} 页 -> {a.sheet}')
        print('差异最大 12 张:', ', '.join(f"{r['stem']}({r['diffpx']:,})" for r in rows[:12]))


if __name__ == '__main__':
    main()
