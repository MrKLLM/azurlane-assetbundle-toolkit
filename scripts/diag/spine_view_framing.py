# -*- coding: utf-8 -*-
"""量 Spine 弹窗里「可见内容占视口多少」——取景缺陷的客观判据。

存在的理由：顶点包围盒撑爆这类问题，代理指标（加载成功、层数）全绿，
只有量"画面里真正有像素的区域占多大"才能暴露。弹窗背景是两种固定色
（(13,17,32)/(18,23,42) 棋盘），所以按"非背景像素"求包围盒即可。

用法:
    py -3 scripts/diag/spine_view_framing.py                 # 读 .diag/l2d_shots_visual 全部
    py -3 scripts/diag/spine_view_framing.py siwanshi_4 2b_2  # 只看这几个
前置: 先用 scripts/diag/l2d_shot_models.py --tab spine <key> 截图
"""
import sys, os, glob

sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHOTS = os.path.join(ROOT, '.diag', 'l2d_shots_visual')
BG = [(13, 17, 32), (18, 23, 42)]
BAR_H = 46          # 底部控制条高度，不算内容


def measure(path):
    im = Image.open(path).convert('RGB')
    w, h = im.size
    px = im.load()
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(0, h - BAR_H):
        for x in range(0, w):
            r, g, b = px[x, y]
            if any(abs(r - br) <= 3 and abs(g - bg) <= 3 and abs(b - bb) <= 3 for br, bg, bb in BG):
                continue
            if x < x0: x0 = x
            if x > x1: x1 = x
            if y < y0: y0 = y
            if y > y1: y1 = y
    if x1 < 0:
        return None
    area_h = h - BAR_H
    cw, ch = x1 - x0 + 1, y1 - y0 + 1
    # fill = 内容在"较长那一轴上占满视口多少"。frac（面积占比）会被宽高比失配稀释，
    # 单独看会把"正常竖图"误读成取景过小；fill≈0.91 才是"贴合 1.1 倍留边适配"的满分线。
    return {'size': (w, area_h), 'bbox': (x0, y0, x1, y1),
            'fill': round(max(cw / w, ch / area_h), 3),
            'frac': round(cw * ch / (w * area_h), 3),
            'touch': ''.join(c for c, v in (('L', x0 <= 1), ('R', x1 >= w - 2),
                                            ('T', y0 <= 1), ('B', y1 >= area_h - 2)) if v) or '-'}


if __name__ == '__main__':
    keys = [a for a in sys.argv[1:] if not a.startswith('--')]
    files = [os.path.join(SHOTS, k + '.png') for k in keys] if keys else sorted(glob.glob(os.path.join(SHOTS, '*.png')))
    rows = []
    for p in files:
        if not os.path.isfile(p):
            print(f'{os.path.basename(p)[:-4]:26s} 缺截图')
            continue
        m = measure(p)
        name = os.path.basename(p)[:-4]
        if m is None:
            print(f'{name:26s} 全空白')
            continue
        rows.append((m['fill'], name))
        print(f'{name:26s} 视口{m["size"][0]}x{m["size"][1]} 内容{m["bbox"]} '
              f'长轴占满 {m["fill"]:.3f} 面积占比 {m["frac"]:.3f} 贴边 {m["touch"]}')
    if len(rows) > 3:
        rows.sort()
        print('\n长轴占满最小 8 个:', ', '.join(f'{n}={f}' for f, n in rows[:8]))
