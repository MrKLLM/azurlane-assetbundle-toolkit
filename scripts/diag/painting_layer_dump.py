# -*- coding: utf-8 -*-
"""立绘「逐层单独落盘」：回答「画面里这块东西到底是哪个部件画的」。

§6.11 就是这么定性的：摩尔曼斯克皮肤2 脸上那块灰梯形，逐层拆开后发现
底图部件 `moermansike_2` 自己就画了那块平涂（源纹理本来如此，游戏运行时靠 face 槽叠真脸），
而 `_front` 层在脸区**一个像素都没落** —— 于是「某部件盖住脸了」这条假设被直接否掉。

落盘位置：.diag/layer_dump/<bundle>_layer<i>_<部件名>.png（每张都是整画布大小，只含这一层）
用法: py -3 scripts/diag/painting_layer_dump.py <bundle> [bundle2 ...]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from PIL import Image
import compose_paintings_v2 as C

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', '..'))
OUT = os.path.join(ROOT, '.diag', 'layer_dump')


def run(bundle):
    rects, go_names, father_map, children_map, parts, deps = C.parse_painting(bundle)
    boxes, mirrors, roots = C.layout_all(rects, father_map, children_map)
    order = C.draw_order(rects, father_map, children_map)
    allb = list(boxes.values())
    cw = int(max(b[0] + b[2] for b in allb))
    ch = int(max(b[1] + b[3] for b in allb))
    face_pid = next((rp for rp in rects if go_names.get(rp) == 'face'), None)
    fbox = None
    if face_pid is not None and face_pid in boxes:
        rx, ry, rw, rh = boxes[face_pid]
        fbox = (int(round(rx)), int(round(ch - (ry + rh))),
                max(1, int(round(rw))), max(1, int(round(rh))))
    print('=' * 70)
    print(f'{bundle}: 部件 {len(parts)} 层序 {len(order)} 画布 {cw}x{ch} '
          f'face 槽像素框 {fbox}')
    by_rect = {}
    for p in parts:
        by_rect.setdefault(p['rect_pid'], []).append(p)
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for pid in order:
        for part in by_rect.get(pid, []):
            res = C.build_part(dict(part))
            if res is None:
                print(f'  --- {part["name"]!r}: build_part 返回 None（无纹理/解析失败）')
                continue
            arr, bbox, frame = res
            rx, ry, rw, rh = boxes.get(pid, (0, 0, frame[0], frame[1]))
            sx = rw / frame[0] if frame[0] else 1
            sy = rh / frame[1] if frame[1] else 1
            x0, y0, x1, y1 = bbox
            mx, my = mirrors.get(pid, (False, False))
            if mx:
                x0, x1 = frame[0] - x1, frame[0] - x0
            if my:
                y0, y1 = frame[1] - y1, frame[1] - y0
            ww = max(1, int(round((x1 - x0) * sx)))
            wh = max(1, int(round((y1 - y0) * sy)))
            img = Image.fromarray(arr.astype(np.uint8), 'RGBA').transpose(Image.FLIP_TOP_BOTTOM)
            if mx:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            if my:
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
            if (img.width, img.height) != (ww, wh):
                img = img.resize((ww, wh), Image.BILINEAR)
            # 与 render() 同一套仿射：内容 AABB -> 画布像素
            px, py = int(round(rx + x0 * sx)), int(round(ch - (ry + y1 * sy)))
            solo = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
            solo.paste(img, (px, py), img)
            a = np.asarray(img).astype(np.int32)
            al, rgb = a[..., 3], a[..., :3]
            sat = rgb.max(axis=2) - rgb.min(axis=2)
            opq = al >= 250
            inface = ''
            if fbox:
                fx, fy, fw, fh = fbox
                # 量「这一层在脸槽里到底落了多少笔」——框重叠不等于画了东西
                # （moermansike_2 的 _front 框住满脸槽，却在脸区一个像素都没落）
                ix0, iy0 = max(0, fx - px), max(0, fy - py)
                ix1, iy1 = min(ww, fx + fw - px), min(wh, fy + fh - py)
                if ix1 > ix0 and iy1 > iy0:
                    ink = int((al[iy0:iy1, ix0:ix1] > 200).sum())
                else:
                    ink = 0
                inface = f' 脸槽内落笔={ink}/{fw * fh}'
            print(f'  #{n} {part["name"]!r:26s} mesh={bool(part["mesh_pid"])} '
                  f'画布({px},{py},{ww}x{wh}) 不透明{int(opq.sum())} '
                  f'mean_rgb={tuple(round(float(x),1) for x in rgb[opq].mean(axis=0)) if opq.any() else None}'
                  f' sat={round(float(sat[opq].mean()),1) if opq.any() else 0}'
                  f' lighting={C.is_lighting(arr)}{inface}')
            solo.save(os.path.join(OUT, f'{bundle}_layer{n}_{part["name"]}.png'))
            n += 1
    print(f'  -> {n} 张单层图落在 {OUT}')


if __name__ == '__main__':
    for b in sys.argv[1:] or ['moermansike_2']:
        run(b)
