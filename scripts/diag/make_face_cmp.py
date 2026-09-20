# -*- coding: utf-8 -*-
"""为 35 个脸洞皮肤生成「改前 | 改后」对比图 + 差异区放大图 + 总览拼图。
输出 .diag/facefix_cmp/<name>.png 与 .diag/facefix_cmp/_overview.png
"""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OLD = os.path.join(ROOT, 'Output', 'Paintings_v2')
NEW = os.path.join(ROOT, '.diag', 'facefix_rerun')
CMP = os.path.join(ROOT, '.diag', 'facefix_cmp')
os.makedirs(CMP, exist_ok=True)
names = [l.strip() for l in open(os.path.join(ROOT, '.diag', 'face_holes.txt'), encoding='utf-8') if l.strip()]

try:
    F = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 22)
    Fs = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16)
except Exception:
    F = Fs = ImageFont.load_default()

H_THUMB = 460          # 对比图整图统一高度
MAX_EDGE = 3000        # 单张对比图最大边长


def load(p):
    return Image.open(p).convert('RGBA')


def on_white(im):
    bg = Image.new('RGB', im.size, (250, 250, 250))
    bg.paste(im, mask=im.split()[3])
    return bg


def fit_h(im, h):
    return im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)


def diff_bbox(a, b):
    """对齐左上角比较（两图同宽时才有意义）；返回差异 bbox 或 None"""
    w = min(a.width, b.width); h = min(a.height, b.height)
    aa = np.asarray(a.crop((0, 0, w, h)), dtype=int)
    bb = np.asarray(b.crop((0, 0, w, h)), dtype=int)
    d = np.abs(aa - bb).max(axis=2)
    m = d > 0
    if not m.any():
        return None, 0
    ys, xs = np.where(m)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), int(m.sum())


def panel(a, b, name, note):
    """[改前 | 改后 | 差异区放大(改前/改后上下)]"""
    ha = fit_h(on_white(a), H_THUMB)
    hb = fit_h(on_white(b), H_THUMB)
    pad = 12
    top = 46
    W = ha.width + hb.width + pad * 4
    H = max(ha.height, hb.height) + top + pad * 2
    # 差异区放大
    zoom = None
    bb, ndiff = diff_bbox(a, b)
    if bb:
        x0, y0, x1, y1 = bb
        bw, bh = x1 - x0, y1 - y0
        s = min(1.0, 320 / max(bw, bh))
        crop_a = on_white(a.crop(bb)).resize((max(1, round(bw * s)), max(1, round(bh * s))), Image.LANCZOS)
        crop_b = on_white(b.crop(bb)).resize((crop_a.size), Image.LANCZOS)
        zoom = (crop_a, crop_b, (bw, bh), s)
        W += crop_a.width + pad * 2
        H = max(H, top + crop_a.height + crop_b.height + pad * 3 + 24)
    img = Image.new('RGB', (W, H), (24, 26, 32))
    d = ImageDraw.Draw(img)
    d.text((pad, 10), f"{name}   {note}", font=F, fill=(240, 240, 240))
    y = top
    img.paste(ha, (pad, y))
    img.paste(hb, (pad * 2 + ha.width, y))
    d.text((pad, y + H_THUMB + 2), "改前", font=Fs, fill=(180, 180, 180))
    d.text((pad * 2 + ha.width, y + H_THUMB + 2), "改后", font=Fs, fill=(120, 220, 120))
    if zoom:
        ca, cb, (bw, bh), s = zoom
        x = pad * 3 + ha.width + hb.width
        img.paste(ca, (x, y))
        img.paste(cb, (x, y + ca.height + 24))
        d.text((x, y + ca.height + 2), f"差异区 {bw}x{bh} (x{s:.2f}) 上=改前 下=改后", font=Fs, fill=(255, 200, 120))
    return img


rows = []
thumbs = []
for n in names:
    a = load(os.path.join(OLD, n + '.png'))
    b = load(os.path.join(NEW, n + '.png'))
    bb, ndiff = diff_bbox(a, b)
    sizechg = a.size != b.size
    note = f"old {a.width}x{a.height} -> new {b.width}x{b.height}"
    if sizechg:
        note += f"  ⚠尺寸变化 Δh={b.height - a.height} Δw={b.width - a.width}"
    if bb:
        note += f"  差异 {ndiff}px @ {bb[2]-bb[0]}x{bb[3]-bb[1]}"
    img = panel(a, b, n, note)
    img.save(os.path.join(CMP, n + '.png'))
    rows.append({'name': n, 'old': list(a.size), 'new': list(b.size), 'sizechg': sizechg,
                 'diffpx': ndiff, 'diffbox': list(bb) if bb else None})
    thumbs.append((n, on_white(b).resize((200, max(1, round(b.height * 200 / b.width))), Image.LANCZOS), sizechg))
    print(f"{n:26} {note}", flush=True)

json.dump(rows, open(os.path.join(CMP, '_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# 总览拼图（改后缩略，⚠尺寸变化者标红框）
COLS = 6
TW, TH = 210, 260
pad = 10
R = (len(thumbs) + COLS - 1) // COLS
ov = Image.new('RGB', (COLS * (TW + pad) + pad, R * (TH + pad) + pad), (24, 26, 32))
d = ImageDraw.Draw(ov)
for i, (n, t, warn) in enumerate(thumbs):
    cx = pad + (i % COLS) * (TW + pad)
    cy = pad + (i // COLS) * (TH + pad)
    ov.paste(t, (cx + (TW - t.width) // 2, cy))
    d.text((cx + 2, cy + TH - 20), n + ('  ⚠' if warn else ''), font=Fs,
           fill=(255, 120, 120) if warn else (220, 220, 220))
    if warn:
        d.rectangle([cx, cy, cx + TW, cy + TH], outline=(255, 80, 80), width=3)
ov.save(os.path.join(CMP, '_overview.png'))
print('\nSIZE-DIFF:', [r['name'] for r in rows if r['sizechg']])
print('对比图 ->', CMP, '| 总览 _overview.png')
