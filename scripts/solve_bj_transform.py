# -*- coding: utf-8 -*-
"""Solve bj-layer transform (S, dx, dy) against a reference game screenshot.

Method:
1. Build base painting (all layers except bj) using current contain+center logic.
2. Calibrate viewport: game shows painting fit-width with vertical crop.
   Search crop_top maximizing full-frame NCC between base slice and reference.
3. Template-match the bj sprite (alpha-masked NCC via FFT) against the reference
   over a range of scales -> ref-space box -> canvas-space (S, px, py).
4. Render final composite with solved bj transform and emit game-view comparison.
"""
import sys, os, argparse
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, r'D:\Azur Lane Assets\scripts')
import UnityPy
import compose_paintings as cp
import screen_bj_misalign as scr

PAINT = scr.PAINT


# ---------- FFT helpers ----------

def _np2(x):
    n = 1
    while n < x:
        n <<= 1
    return n


def fft_xcorr(img, ker):
    """Valid-region cross-correlation: out[y,x] = sum ker * img[y:y+h, x:x+w]."""
    H, W = img.shape
    h, w = ker.shape
    fh2, fw2 = _np2(H + h - 1), _np2(W + w - 1)
    Fi = np.fft.rfft2(img, (fh2, fw2))
    Fk = np.fft.rfft2(ker[::-1, ::-1], (fh2, fw2))
    c = np.fft.irfft2(Fi * Fk, (fh2, fw2))
    return c[h - 1:H, w - 1:W]


def masked_ncc(ref, templ, mask):
    """Masked normalized cross-correlation of templ over ref (both float RGB)."""
    H, W = ref.shape[:2]
    h, w = templ.shape[:2]
    N = mask.sum()
    if N < 10:
        return None
    oH, oW = H - h + 1, W - w + 1
    if oH <= 0 or oW <= 0:
        return None
    num = np.zeros((oH, oW), dtype=np.float64)
    den_i = np.zeros((oH, oW), dtype=np.float64)
    den_t = 0.0
    for c in range(3):
        T = mask * templ[..., c]
        tsum = T.sum()
        I = ref[..., c].astype(np.float64)
        xc_T_I = fft_xcorr(I, T)
        xc_M_I = fft_xcorr(I, mask)
        xc_M_I2 = fft_xcorr(I * I, mask)
        num += xc_T_I - tsum * xc_M_I / N
        den_i += xc_M_I2 - xc_M_I ** 2 / N
        den_t += (mask * templ[..., c] ** 2).sum() - tsum ** 2 / N
    den = np.sqrt(np.maximum(den_i * max(den_t, 1e-9), 1e-12))
    return num / den


# ---------- painting assembly ----------

def load_parts(bundle):
    env = UnityPy.load(os.path.join(PAINT, bundle))
    rects, ptn = scr.get_rects(env)
    scr.path_to_name = ptn
    sizes, origins, root = scr.alpa(rects, bundle)
    cw, ch = int(root.m_SizeDelta.x), int(root.m_SizeDelta.y)
    order = cp.build_draw_order(rects, ptn, root)
    parts = []
    for pid in order:
        name = ptn[pid]
        if name in ['Touch', 'layers', 'Unknown', 'frameContain']:
            continue
        tex = cp.find_tex_path(bundle, name)
        if not tex:
            continue
        img = cp.synthesize_tex_bundle(tex)
        if img is None:
            continue
        parts.append((pid, name, img, sizes[pid], origins[pid]))
    return cw, ch, parts


def paste_contain(canvas, img, size, origin, ch):
    mw, mh = img.size
    rw_, rh_ = size
    ratio = min(rw_ / mw, rh_ / mh) if mw > 0 and mh > 0 else 1.0
    W, H = int(round(mw * ratio)), int(round(mh * ratio))
    img2 = img.resize((W, H), Image.LANCZOS) if (W, H) != img.size else img
    px = int(round(origin[0] + (rw_ - W) / 2.0))
    py = int(round(ch - (origin[1] + (rh_ - H) / 2.0) - H))
    canvas.paste(img2, (px, py), img2)


def build_base(bundle, cw, ch, parts):
    """Compose everything except bj. Returns base RGBA canvas."""
    canvas = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
    for pid, name, img, size, origin in parts:
        if name == f'{bundle}_bj':
            continue
        if cp._is_lighting_overlay(img):
            continue
        paste_contain(canvas, img, size, origin, ch)
    return canvas


# ---------- solving ----------

def calibrate_viewport(base_rgba, ref_f):
    """Game shows painting fit-width + vertical crop. Find crop_top via NCC."""
    a = np.array(base_rgba.convert('RGB')).astype(np.float64)
    ch_, cw_ = a.shape[:2]
    H, W = ref_f.shape[:2]
    k = W / cw_
    vis_h = int(round(H / k))
    if vis_h >= ch_:
        return k, 0
    ref_c = ref_f - ref_f.mean()
    ref_den = np.sqrt((ref_c ** 2).sum())

    def ncc_at(ct):
        sl = a[ct:ct + vis_h].astype(np.uint8)
        t = np.array(Image.fromarray(sl).resize((W, H), Image.BILINEAR)).astype(np.float64)
        t_c = t - t.mean()
        return float((t_c * ref_c).sum() / (np.sqrt((t_c ** 2).sum()) * ref_den + 1e-12))

    best = (-2, 0)
    for ct in range(0, ch_ - vis_h + 1, 8):
        v = ncc_at(ct)
        if v > best[0]:
            best = (v, ct)
    lo, hi = max(0, best[1] - 10), min(ch_ - vis_h, best[1] + 10)
    for ct in range(lo, hi + 1):
        v = ncc_at(ct)
        if v > best[0]:
            best = (v, ct)
    return k, best[1], best[0]


def match_bj(ref_f, sprite_rgba, s_lo=0.1, s_hi=2.5, coarse=1.06, refine=0.005):
    """Multi-scale masked template match. Returns (s_ref, x, y, ncc)."""
    a = np.array(sprite_rgba).astype(np.float64)
    alpha = a[..., 3] / 255.0
    ys, xs = np.where(alpha > 0.03)
    if len(xs) == 0:
        return None
    x1, x2, y1, y2 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    rgb = a[y1:y2, x1:x2, :3]
    msk = alpha[y1:y2, x1:x2]
    th, tw = msk.shape

    H, W = ref_f.shape[:2]
    best = None
    s = s_lo
    while s <= s_hi:
        nw, nh = max(4, int(round(tw * s))), max(4, int(round(th * s)))
        if nw > W - 4 or nh > H - 4:
            s *= coarse
            continue
        t_img = Image.fromarray(rgb.astype(np.uint8)).resize((nw, nh), Image.BILINEAR)
        m_img = Image.fromarray((msk * 255).astype(np.uint8)).resize((nw, nh), Image.BILINEAR)
        t = np.array(t_img).astype(np.float64)
        m = np.array(m_img).astype(np.float64) / 255.0
        ncc = masked_ncc(ref_f, t, m)
        if ncc is not None:
            pk = ncc.max()
            if best is None or pk > best[0]:
                yx = np.unravel_index(ncc.argmax(), ncc.shape)
                best = (pk, s, yx[1], yx[0])
        s *= coarse
    if best is None:
        return None
    # refine scale around best
    pk0, s0, x0, y0 = best
    for s in np.arange(s0 / coarse, s0 * coarse + 1e-9, refine):
        nw, nh = max(4, int(round(tw * s))), max(4, int(round(th * s)))
        if nw > W - 4 or nh > H - 4:
            continue
        t_img = Image.fromarray(rgb.astype(np.uint8)).resize((nw, nh), Image.BILINEAR)
        m_img = Image.fromarray((msk * 255).astype(np.uint8)).resize((nw, nh), Image.BILINEAR)
        t = np.array(t_img).astype(np.float64)
        m = np.array(m_img).astype(np.float64) / 255.0
        ncc = masked_ncc(ref_f, t, m)
        if ncc is None:
            continue
        pk = ncc.max()
        if pk > best[0]:
            yx = np.unravel_index(ncc.argmax(), ncc.shape)
            best = (pk, s, yx[1], yx[0])
    pk, s, x, y = best
    trim = (x1, y1, x2, y2)
    return pk, s, x, y, trim


def render_final(bundle, cw, ch, parts, sprite_rgba, S, px, py, below_rw):
    canvas = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
    bj_name = f'{bundle}_bj'
    bj_pasted = False

    def paste_bj():
        nonlocal bj_pasted
        sw, sh = sprite_rgba.size
        W, H = int(round(sw * S)), int(round(sh * S))
        sp = sprite_rgba.resize((W, H), Image.LANCZOS)
        canvas.paste(sp, (int(round(px)), int(round(py))), sp)
        bj_pasted = True

    for pid, name, img, size, origin in parts:
        if name == bj_name:
            if not below_rw and not bj_pasted:
                paste_bj()
            continue
        if below_rw and name == f'{bundle}_rw' and not bj_pasted:
            paste_bj()
        if cp._is_lighting_overlay(img):
            continue
        paste_contain(canvas, img, size, origin, ch)
    if not bj_pasted:
        paste_bj()
    return canvas


def game_view(canvas, k, crop_top, ref_size):
    W, H = ref_size
    vis_h = int(round(H / k))
    sl = canvas.crop((0, crop_top, canvas.width, min(canvas.height, crop_top + vis_h)))
    return sl.convert('RGB').resize((W, H), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('bundle')
    ap.add_argument('ref')
    ap.add_argument('--below-rw', action='store_true', help='draw bj below rw layer')
    ap.add_argument('--anchor', choices=['bg', 'rw'], default='bg',
                    help='viewport anchor: bg=fit-width full-frame, rw=match rw layer (use when bg framing differs)')
    ap.add_argument('--s-lo', type=float, default=0.1)
    ap.add_argument('--s-hi', type=float, default=2.5)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    b = args.bundle
    out_dir = args.out or os.path.join(r'D:\Azur Lane Assets\Output\Paintings_Synthesized_FIXTEST', 'solve_' + b)
    os.makedirs(out_dir, exist_ok=True)

    print(f'[1/4] building base for {b} ...')
    cw, ch, parts = load_parts(b)
    print(f'  canvas {cw}x{ch}, parts: {[n for _, n, _, _, _ in parts]}')
    base = build_base(b, cw, ch, parts)

    ref_img = Image.open(args.ref).convert('RGB')
    ref_f = np.array(ref_img).astype(np.float64)

    bj_part = rw_part = None
    rw_canvas_pos = None
    for pid, name, img, size, origin in parts:
        if name == f'{b}_bj':
            bj_part = img
        elif name == f'{b}_rw':
            rw_part = img
            mw, mh = img.size
            rw_, rh_ = size
            ratio = min(rw_ / mw, rh_ / mh) if mw > 0 and mh > 0 else 1.0
            W0, H0 = int(round(mw * ratio)), int(round(mh * ratio))
            rw_canvas_pos = (origin[0] + (rw_ - W0) / 2.0,
                             ch - (origin[1] + (rh_ - H0) / 2.0) - H0, ratio)

    rw_map = None
    if args.anchor == 'rw':
        print('[2/4] anchoring on rw layer ...')
        # content-trimmed rw sprite
        a = np.array(rw_part).astype(np.float64)
        alpha = a[..., 3] / 255.0
        ys, xs = np.where(alpha > 0.03)
        rx1, rx2, ry1, ry2 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        rw_trim = rw_part.crop((rx1, ry1, rx2, ry2))
        res = match_bj(ref_f, rw_trim, 0.1, 1.0)
        if res is None:
            print('  ERROR: rw anchor match failed')
            return
        pk_r, s_r, x_r, y_r, _ = res
        print(f'  rw anchor: ncc={pk_r:.4f} s={s_r:.4f} ref_pos=({x_r},{y_r})')
        # canvas pos of trimmed rw sprite
        rcx = rw_canvas_pos[0] + rx1 * rw_canvas_pos[2]
        rcy = rw_canvas_pos[1] + ry1 * rw_canvas_pos[2]
        rw_map = (s_r, x_r, y_r, rcx, rcy)
        k, crop_top, cal_ncc = None, None, pk_r
    else:
        print('[2/4] calibrating viewport ...')
        k, crop_top, cal_ncc = calibrate_viewport(base, ref_f)
        print(f'  k={k:.4f} crop_top={crop_top} ncc={cal_ncc:.4f}')
        base_gv = game_view(base, k, crop_top, ref_img.size)
        base_gv.save(os.path.join(out_dir, 'base_gameview.png'))

    print('[3/4] matching bj sprite ...')
    if bj_part is None:
        print('  ERROR: no bj part found')
        return
    res = match_bj(ref_f, bj_part, args.s_lo, args.s_hi)
    if res is None:
        print('  ERROR: match failed')
        return
    pk, s_ref, x_ref, y_ref, trim = res
    print(f'  match: ncc={pk:.4f} s_ref={s_ref:.4f} ref_pos=({x_ref},{y_ref}) trim={trim}')

    # convert to canvas params
    if rw_map is not None:
        s_r, x_r, y_r, rcx, rcy = rw_map
        S = s_ref / s_r
        px = rcx + (x_ref - x_r) / s_r
        py = rcy + (y_ref - y_r) / s_r
    else:
        S = s_ref / k
        px = x_ref / k
        py = y_ref / k + crop_top
    print(f'  SOLVED: S={S:.4f} px={px:.1f} py={py:.1f} below_rw={args.below_rw} anchor={args.anchor}')

    # trim sprite to content box for exact placement
    sprite_t = bj_part.crop(trim)

    print('[4/4] rendering final ...')
    final = render_final(b, cw, ch, parts, sprite_t, S, px, py, args.below_rw)
    bbox = final.getbbox()
    if bbox:
        final.crop(bbox).save(os.path.join(out_dir, f'{b}_solved_full.png'))

    # game-view for comparison
    W, H = ref_img.size
    if rw_map is not None:
        # affine: ref(u,v) <- canvas(x,y): u = (x - rcx)*s_r + x_r ; v = (y - rcy)*s_r + y_r
        s_r, x_r, y_r, rcx, rcy = rw_map
        # PIL transform needs inverse: canvas x = (u - x_r)/s_r + rcx
        mat = (1.0 / s_r, 0, rcx - x_r / s_r, 0, 1.0 / s_r, rcy - y_r / s_r)
        final_gv = final.transform((W, H), Image.AFFINE, mat, Image.BICUBIC).convert('RGB')
        base_gv = base.transform((W, H), Image.AFFINE, mat, Image.BICUBIC).convert('RGB')
        base_gv.save(os.path.join(out_dir, 'base_gameview.png'))
    else:
        final_gv = game_view(final, k, crop_top, ref_img.size)

    side = Image.new('RGB', (W * 2 + 20, H + 40), (20, 20, 20))
    d = ImageDraw.Draw(side)
    side.paste(ref_img, (0, 40))
    side.paste(final_gv, (W + 20, 40))
    d.text((8, 12), 'GAME REF', fill=(255, 220, 100))
    d.text((W + 28, 12), f'SOLVED  S={S:.3f} px={px:.0f} py={py:.0f} ncc={pk:.3f}', fill=(100, 255, 150))
    side.save(os.path.join(out_dir, 'compare.png'))

    a2 = np.array(ref_img).astype(np.float64)
    t2 = np.array(final_gv).astype(np.float64)
    psnr = 20 * np.log10(255.0 / (np.sqrt(((a2 - t2) ** 2).mean()) + 1e-9))
    print(f'  full-frame PSNR vs ref: {psnr:.2f} dB')
    print(f'  params: {{ "{b}": {{ "S": {S:.4f}, "dx": {px:.1f}, "dy": {py:.1f}, "below_rw": {str(args.below_rw).lower()} }} }}')
    print(f'  out: {out_dir}')


if __name__ == '__main__':
    main()
