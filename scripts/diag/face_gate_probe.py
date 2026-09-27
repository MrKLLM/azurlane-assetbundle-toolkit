# -*- coding: utf-8 -*-
"""单个皮肤的「脸区为什么是灰/白块」取证：走 compose() 真实渲染路径，
打印 ① face 槽世界矩形与成品像素框 ② 门控实际读到的两个数（直接读生产侧 FACE_GATE，
不在探针里复算——复算容易读到已叠脸之后的画布，本轮就踩过）③ 与脸区重叠的落笔层及其颜色统计。

用法：py -3 scripts/diag/face_gate_probe.py <bundle> [bundle2 ...]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from PIL import Image
import compose_paintings_v2 as C

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', '..'))


def stats(img):
    """PIL RGBA -> (落笔数, 不透明数, 不透明像素 mean rgb, mean sat, mean alpha)"""
    a = np.asarray(img).astype(np.int32)
    al, rgb = a[..., 3], a[..., :3]
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    op = al >= 250
    n = int((al > 200).sum())
    if not op.any():
        return n, 0, None, None, round(float(al.mean()), 1)
    return (n, int(op.sum()),
            tuple(round(float(x), 1) for x in rgb[op].mean(axis=0)),
            round(float(sat[op].mean()), 1), round(float(al.mean()), 1))


def run(bundle):
    print('=' * 78)
    print(f'bundle = {bundle}')
    rects, go_names, father_map, children_map, parts, deps = C.parse_painting(bundle)
    boxes, mirrors, roots = C.layout_all(rects, father_map, children_map)
    order = C.draw_order(rects, father_map, children_map)
    face_pid = next((rp for rp in rects if go_names.get(rp) == 'face'), None)
    allb = list(boxes.values())
    cw = int(max(b[0] + b[2] for b in allb))
    ch = int(max(b[1] + b[3] for b in allb))
    print(f'部件 {len(parts)} / 层序 {len(order)} / 画布 {cw}x{ch} / face_pid={face_pid}')

    fbox = None
    if face_pid is None:
        print('!! prefab 里没有名为 face 的 RectTransform 节点（该皮肤不可能被叠脸）')
    else:
        rx, ry, rw, rh = boxes[face_pid]
        fpx, fpy = int(round(rx)), int(round(ch - (ry + rh)))
        fww, fwh = max(1, int(round(rw))), max(1, int(round(rh)))
        fbox = (fpx, fpy, fww, fwh)
        print(f'face 槽世界矩形(Y-up)= ({rx:.0f},{ry:.0f},{rw:.0f},{rh:.0f})')
        print(f'face 槽在画布上的像素框 = x[{fpx}:{fpx+fww}] y[{fpy}:{fpy+fwh}] ({fww}x{fwh})')

    # ---- 拦截真实渲染路径，按绘制序记录每一层落笔 ----
    builds, lightings, pastes = [], [], []
    orig_build, orig_light, orig_paste = C.build_part, C.is_lighting, Image.Image.paste

    def w_build(part, face_sprite_name=None):
        r = orig_build(part, face_sprite_name)
        builds.append((part.get('name'), r is not None))
        return r

    def w_light(arr):
        r = orig_light(arr)
        lightings.append(bool(r))
        return r

    def w_paste(self, im, box=None, mask=None):
        orig_paste(self, im, box, mask)
        pastes.append({'pos': tuple(box) if box else None, 'size': im.size,
                       'st': stats(im), 'canvas': self})

    C.build_part, C.is_lighting, Image.Image.paste = w_build, w_light, w_paste
    try:
        C.FACE_GATE.pop(bundle, None)
        C.compose(bundle, os.path.join(ROOT, '.diag', 'face_gate_probe_tmp'), save=False)
    finally:
        C.build_part, C.is_lighting, Image.Image.paste = orig_build, orig_light, orig_paste

    # build_part 成功且未被 lighting 跳过的，按序即 paste 序（最后一层是叠脸，不在 builds 里）
    kept = [name for (name, ok), lit in zip([b for b in builds if b[1]], lightings) if not lit]

    g = C.FACE_GATE.get(bundle)
    fx = C.paintingface_face(bundle, '1')
    print(f'\n[门控] paintingface/{bundle} 表情"1" -> {"有 " + str(fx[1]) if fx else "None（读不到脸谱）"}')
    if g is None:
        print('[门控] 未参与判定（无 face 槽 / 无脸谱 / 脸谱落笔 <64 px）')
    else:
        mad = g['mad']
        print(f'[门控] 脸谱落笔 n_foot = {g["n_foot"]}   (阈值 >=64)')
        print(f'[门控] 分支一 其下「不透明」占比 frac_opaque = {g["frac_opaque"]:.3f}   '
              f'低于 {C.FACE_OPAQUE_MIN} 即透明洞')
        print(f'[门控] 分支二 底图 vs 脸谱逐像素色差 MAD = '
              f'{"n/a(可比像素<64)" if mad is None else f"{mad:.1f}"}   '
              f'高于 {C.FACE_MAD_MAX} 即「这里画的不是这张脸」')
        print(f'[门控] (退役判据) sat≥30 占比 frac_realart = {g["frac_realart"]:.3f}')
        print(f'[门控] 判定 = {"洞 -> 叠脸" if g["hole"] else "脸已烤好 -> 不叠"}   '
              f'本次 FACE_APPLIED={C.FACE_APPLIED.get(bundle)}')
        if g['frac_opaque'] >= C.FACE_OPAQUE_MIN and g['hole']:
            print('[门控] ★ 不透明但画的不是这张脸（平涂灰块类）——旧的两版判据都管不住')

    if fbox and pastes:
        fpx, fpy, fww, fwh = fbox
        print('\n[落笔] 与 face 槽框重叠的层（按绘制序）:')
        for i, p in enumerate(pastes):
            if p['pos'] is None:
                continue
            px, py = p['pos']
            pw, ph = p['size']
            if px >= fpx + fww or px + pw <= fpx or py >= fpy + fwh or py + ph <= fpy:
                continue
            name = kept[i] if i < len(kept) else 'face-overlay'
            n, nop, mean, msat, mal = p['st']
            print(f'  #{i:2d} {name!r:26s} pos=({px},{py}) size={pw}x{ph} '
                  f'落笔{n} 不透明{nop} mean_rgb={mean} sat={msat} alpha={mal}')


if __name__ == '__main__':
    for b in sys.argv[1:] or ['moermansike_2']:
        run(b)
