# -*- coding: utf-8 -*-
"""35 个脸洞皮肤的「脸部区域 改前|改后」对照总表，供用户一次性复核。
每行：名字 + 判定标签 + 改前脸区 + 改后脸区（同一裁剪框，等比放大）
输出 .diag/facefix_cmp/_review_sheet.png
"""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
names = [l.strip() for l in open(os.path.join(ROOT, '.diag', 'face_holes.txt'), encoding='utf-8') if l.strip()]
try:
    F = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 20)
    Fs = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 15)
except Exception:
    F = Fs = ImageFont.load_default()

CELL = 300
ROWH = CELL + 34
report = json.load(open(os.path.join(ROOT, '.diag', 'facefix_cmp', '_report.json'), encoding='utf-8'))
rmap = {r['name']: r for r in report}

rows = []
for n in names:
    A = Image.open(os.path.join(ROOT, 'Output', 'Paintings_v2', n + '.png')).convert('RGBA')
    B = Image.open(os.path.join(ROOT, '.diag', 'facefix_rerun', n + '.png')).convert('RGBA')
    # 定位脸部：取两图差异包围盒；尺寸不同者按底边对齐后取新图上半部
    if A.size == B.size:
        a = np.asarray(A, int); b = np.asarray(B, int)
        d = np.abs(a - b).max(axis=2)
        ys, xs = np.where(d > 0)
        box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        boxA = boxA_ = box
        tag = ''
    else:
        dh = B.height - A.height
        boxB = (0, 0, B.width, max(1, B.height - A.height + 60))     # 新增出来的顶部区域
        boxA = (0, 0, A.width, 1)                                     # 旧图无对应内容
        boxA_ = boxB
        tag = '尺寸变化·头部找回'
    # 统一成正方形裁剪，便于并排
    def sq(im, bx):
        if bx[2] - bx[0] < 4 or bx[3] - bx[1] < 4:
            return Image.new('RGBA', (CELL, CELL), (60, 60, 66, 255))
        w = bx[2] - bx[0]; h = bx[3] - bx[1]; m = max(w, h)
        cx = (bx[0] + bx[2]) // 2; cy = (bx[1] + bx[3]) // 2
        x0 = max(0, min(im.width - m, cx - m // 2)); y0 = max(0, min(im.height - m, cy - m // 2))
        x1 = min(im.width, x0 + m); y1 = min(im.height, y0 + m)
        c = im.crop((x0, y0, x1, y1))
        c = c.resize((CELL, CELL), Image.LANCZOS)
        bg = Image.new('RGB', (CELL, CELL), (250, 250, 250)); bg.paste(c, mask=c.split()[3])
        return bg.convert('RGBA')
    rows.append((n, sq(A, boxA), sq(B, boxA_), tag, rmap.get(n, {})))

LBLW = 300
COLS = 2                      # 每行放 2 个皮肤（每个皮肤 = 改前|改后 两格）
CW = LBLW + CELL * 2 + 24
n_rows = len(rows)
per = 2
sheet = Image.new('RGB', (COLS * CW + 20, (n_rows // per + 1) * (ROWH + 62) + 70), (24, 26, 32))
d = ImageDraw.Draw(sheet)
d.text((20, 16), 'I-168 类脸部白块修复 — 35 个脸洞皮肤 改前(左) / 改后(右) 脸部对照   ⚠ 红字=需你确认', font=F, fill=(240, 240, 240))
suspect = {'leiniya_wjz'}     # 改前已是完整清晰另一表情，叠层会换掉
for i, (n, ca, cb, tag, info) in enumerate(rows):
    col = i % COLS; rr = i // COLS
    x = 20 + col * CW; y = 60 + rr * (ROWH + 62)
    d.text((x, y), n + (('  ' + tag) if tag else ''), font=Fs,
           fill=(255, 110, 110) if n in suspect else (225, 225, 225))
    sheet.paste(ca, (x, y + 24), ca)
    sheet.paste(cb, (x + CELL + 8, y + 24), cb)
    d.line([x + CELL + 3, y + 24, x + CELL + 3, y + 24 + CELL], fill=(90, 90, 100), width=2)
    if n in suspect:
        d.rectangle([x - 3, y + 21, x + CELL * 2 + 12, y + 30 + CELL], outline=(255, 80, 80), width=4)
        d.text((x, y + 28 + CELL), '改前已有完整脸(另一表情) → 建议排除', font=Fs, fill=(255, 130, 130))
    if n == 'missd':
        d.text((x, y + 28 + CELL), '注：§6.8 你标过「黑影」暂搁置，是否一并换入？', font=Fs, fill=(255, 200, 120))
out = os.path.join(ROOT, '.diag', 'facefix_cmp', '_review_sheet.png')
sheet.save(out)
print('总表 ->', out, sheet.size, '| 皮肤数', len(rows))
