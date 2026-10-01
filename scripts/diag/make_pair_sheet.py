# -*- coding: utf-8 -*-
"""「改前 | 改后」成对总表：给一批同名图片，两边并排 + 差异度量，拼成一张可一眼看完的复核表。

为什么需要：数据管线改完要交人拍板（WF-15 第 4 步），而"34 张图各自打开看"这件事
没人做得完 —— 没有总表就等于没确认。逐字节是否相同、内容占比怎么变，都直接标在格子上，
这样"没变化"和"变坏了"能被区分开，而不是只看一叠缩略图。

用法:
  py -3 scripts/diag/make_pair_sheet.py --old <旧目录> --new <新目录> \
      --names a,b,c --out .diag/pair_sheet.png [--cell 300] [--only-changed]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
Image.MAX_IMAGE_PIXELS = None

try:
    F = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18)
    Fs = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 13)
except Exception:
    F = Fs = ImageFont.load_default()


def load(p, cell):
    im = Image.open(p)
    im.load()
    if im.mode != 'RGBA':
        im = im.convert('RGBA')
    w, h = im.size
    s = min(cell / w, cell / h)
    return im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)


def diff_pct(a, b, cell):
    """两张都归一到同一格再比 —— 尺寸不同的图直接比字节没有意义。"""
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    pa, pb = a.convert('RGB').tobytes(), b.convert('RGB').tobytes()
    n = len(pa) // 3
    d = sum(1 for i in range(0, len(pa), 3 * 7)          # 每 7 个像素采一个，够看趋势
            if abs(pa[i] - pb[i]) > 24 or abs(pa[i + 1] - pb[i + 1]) > 24
            or abs(pa[i + 2] - pb[i + 2]) > 24)
    return 100.0 * d / max(1, n // 7)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', required=True)
    ap.add_argument('--new', required=True)
    ap.add_argument('--names', required=True, help='逗号分隔，或 @文件路径（文件内为逗号分隔的一行）')
    ap.add_argument('--out', default='.diag/pair_sheet.png')
    ap.add_argument('--cell', type=int, default=300)
    ap.add_argument('--only-changed', action='store_true', help='跳过逐字节相同的（但会先报有几个相同）')
    a = ap.parse_args()

    spec = a.names
    if spec.startswith('@'):
        spec = open(spec[1:], encoding='utf-8').read().strip()
    names = [x.strip() for x in spec.split(',') if x.strip()]

    rows = []
    ident = []
    for n in names:
        po, pn = os.path.join(a.old, n + '.png'), os.path.join(a.new, n + '.png')
        if not os.path.isfile(pn):
            print(f'  ! 新侧缺文件，跳过 {n}')
            continue
        if not os.path.isfile(po):
            # 「线上新增」也要能出图：以前两侧任一缺失就跳过 ⇒ 新皮肤永远不出现在对照表里，
            # 而它恰恰是最需要人看的那一类（2026-10-01 用户问"怎么知道新增了什么"的源头）
            print(f'  · 线上没有这张（新增）: {n}')
            rows.append((n, None, pn, False))
            continue
        same = os.path.getsize(po) == os.path.getsize(pn) and \
            open(po, 'rb').read() == open(pn, 'rb').read()

        if same:
            ident.append(n)
            if a.only_changed:
                continue
        rows.append((n, po, pn, same))
    print(f'成对 {len(rows)} 张（其中逐字节相同 {len(ident)}）-> {a.out}')

    cell, head = a.cell, 30
    W = cell * 2 + 24
    H = (cell + head) * len(rows) + 8
    sheet = Image.new('RGB', (W, H), (250, 250, 250))
    d = ImageDraw.Draw(sheet)
    for i, (n, po, pn, same) in enumerate(rows):
        y = i * (cell + head)
        io, inp = (None if po is None else load(po, cell)), load(pn, cell)
        for j, im in enumerate((io, inp)):
            x = 8 + j * (cell + 8)
            d.rectangle([x, y + head - 2, x + cell, y + head - 2 + cell], fill=(255, 255, 255))
            if im is None:      # 新增：左侧画一块明确的"线上没有"占位，不留白当渲染坏了
                d.rectangle([x + 1, y + head - 1, x + cell - 1, y + head - 2 + cell - 1],
                            fill=(236, 236, 238))
                d.text((x + 12, y + head + cell // 2 - 8), '线上没有这张', fill=(90, 90, 96), font=Fs)
                continue
            sheet.paste(im, (x + (cell - im.width) // 2, y + head + (cell - im.height) // 2), im)
        pct = 0.0 if same else (0.0 if io is None else diff_pct(io, inp, cell))
        tag = ('线上新增' if io is None else
               ('逐字节相同' if same else f'差异像素≈{pct:.1f}%'))
        d.text((10, y), f'{n}   {tag}   旧 | 新', fill=(20, 20, 20), font=F)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or '.', exist_ok=True)
    sheet.save(a.out)
    print(f'已写出 {a.out}  {W}x{H}')
    if ident:
        print('  逐字节相同（= 本次改动对它零影响）:', ident)


if __name__ == '__main__':
    main()
