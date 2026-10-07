#!/usr/bin/env python3
"""upscale_bg_hd.py — 给背景库里「源头就低清」的那批图做 AI 超分，产出独立的 `Output/Raw_hd/`。

为什么单独一个目录、且不动 `Output/Raw/`：Raw 是导出层（WF-15 承重白名单，删了不可复原），
超分产物是**派生**内容，必须能整目录删掉重来，也不能被 `--target bg` 重导覆写。

只处理「宽 <= --maxw 且（有角色 或 登录/加载类目）」这一子集：
其余图源头已是 1920/2048，超分只会平白多出几 GB 而看不出差别。

依赖装在隔离 venv 里，**不要**装进全局 python（全局那份 onnxruntime 是 OCR 脚本在用）：
  tools/upscale/venv/Scripts/python.exe scripts/upscale_bg_hd.py --limit 3   # 先小样本
  tools/upscale/venv/Scripts/python.exe scripts/upscale_bg_hd.py             # 全量（可反复跑，存在即跳）
  tools/upscale/venv/Scripts/python.exe scripts/upscale_bg_hd.py --check     # 只报清单，不写盘

分块：整图 4x 时 1280 宽要开 5120x2880 的中间张量，8GB 显存会炸 ⇒ 按 --tile 切块、
相邻块留 --overlap 重叠再裁掉，防止接缝。块尺寸必须是 4 的倍数（模型是 x4）。
"""
import argparse
import json
import os
import struct
import sys
import time

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW = os.path.join(ROOT, 'Output', 'Raw')
HD = os.path.join(ROOT, 'Output', 'Raw_hd')
META = os.path.join(ROOT, 'Output', 'gallery_v2', 'bg_meta.json')
MODELS = os.path.join(ROOT, 'tools', 'upscale', 'models')
LOG = os.path.join(ROOT, '.diag', 'upscale_bg_hd.log')
SCALE = 4                      # 三个候选模型都是 x4 网络
DEFAULT_MODEL = 'anime6b.onnx'  # 选型依据见 scripts/diag/bg_hd_model_cmp.py 的判据段
LOADING_DIRS = ('loadingbg', 'loadingbg_hx')


def png_size(p):
    with open(p, 'rb') as f:
        h = f.read(24)
    if h[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', h[16:24])


def png_complete(p):
    """尾部必须有 IEND。断电/进程被杀会留下**头部尺寸合法但内容截断**的 PNG，
    只看 png_size 会把它当"已完成"跳过 —— 那批产物就永久坏了，所以续跑判据要查尾。"""
    try:
        with open(p, 'rb') as f:
            f.seek(-12, os.SEEK_END)
            return f.read(8) == b'IEND\xaeB`\x82'
    except Exception:
        return False


def pick_targets(meta, maxw, dirs=None, keys=None):
    """目标 = 低清 且（有角色 或 登录/加载）。三态字段 has_char 缺失表示没判过，不算有角色。"""
    items = meta['items'] if isinstance(meta, dict) else meta
    out = []
    for it in items:
        if keys and it['key'] not in keys:
            continue
        if dirs and it['dir'] not in dirs:
            continue
        p = os.path.normpath(os.path.join(ROOT, 'Output', 'gallery_v2', it['img']))
        if not os.path.exists(p):
            continue
        sz = png_size(p)
        if not sz or sz[0] > maxw:
            continue
        if it.get('has_char') == 1 or it['dir'] in LOADING_DIRS:
            out.append((it['key'], p, sz))
    return sorted(out)


def _run_block(sess, iname, itype, blk):
    """单块推理：把 H/W 补到 4 的倍数（模型是 x4 网络，尺寸必须整除），跑完再裁回。"""
    h, w = blk.shape[:2]
    ph = (-h) % 4
    pw = (-w) % 4
    if ph or pw:
        blk = np.pad(blk, ((0, ph), (0, pw), (0, 0)), mode='edge')
    z = np.transpose(blk, (2, 0, 1))[None]
    if 'float16' in itype:
        z = z.astype(np.float16)
    r = sess.run(None, {iname: z})[0][0]
    r = np.transpose(r.astype(np.float32), (1, 2, 0))
    return r[:h * SCALE, :w * SCALE]


def upscale(sess, iname, itype, arr, tile, overlap):
    """arr: HxWx3 float32 in [0,1] -> x4 后的同布局。

    块按 step = tile-overlap 前进，每块只交付自己左上 [step]（末块交付到边界）那段，
    重叠区留给下一块算 ⇒ 无缝、无重复计费。
    """
    h, w = arr.shape[:2]
    step = max(64, tile - overlap)
    out = np.zeros((h * SCALE, w * SCALE, 3), dtype=np.float32)
    for y in range(0, h, step):
        y2 = min(h, y + tile)
        y3 = h if y + step >= h else y + step          # 本块负责交付到 y3
        for x in range(0, w, step):
            x2 = min(w, x + tile)
            x3 = w if x + step >= w else x + step
            r = _run_block(sess, iname, itype, arr[y:y2, x:x2])
            out[y * SCALE:y3 * SCALE, x * SCALE:x3 * SCALE] = \
                r[:(y3 - y) * SCALE, :(x3 - x) * SCALE]
    return np.clip(out, 0.0, 1.0)


def main():
    from PIL import Image
    import onnxruntime as ort

    ap = argparse.ArgumentParser()
    ap.add_argument('--maxw', type=int, default=1280)
    ap.add_argument('--model', default=DEFAULT_MODEL)
    ap.add_argument('--tile', type=int, default=512)
    ap.add_argument('--overlap', type=int, default=32)
    ap.add_argument('--limit', type=int, default=0, help='只跑前 N 张（小样本试跑）')
    ap.add_argument('--dirs', nargs='*', default=None, help='限定类目')
    ap.add_argument('--keys', nargs='*', default=None, help='指定 key')
    ap.add_argument('--check', action='store_true', help='只列清单与体积预估，不写盘')
    ap.add_argument('--overwrite', action='store_true', help='已存在的也重做')
    a = ap.parse_args()

    meta = json.load(open(META, encoding='utf-8'))
    tg = pick_targets(meta, a.maxw, a.dirs, set(a.keys) if a.keys else None)
    if a.limit:
        tg = tg[:a.limit]
    src_mb = sum(os.path.getsize(p) for _, p, _ in tg) / 1e6
    print('目标 %d 张（源 %.1f MB）；输出目录 %s' % (len(tg), src_mb, HD), flush=True)
    if a.check:
        for k, p, sz in tg[:20]:
            print('   ', k, sz)
        if len(tg) > 20:
            print('    ...共 %d 张' % len(tg))
        return 0

    mp = a.model if os.path.isabs(a.model) else os.path.join(MODELS, a.model)
    so = ort.SessionOptions()
    so.log_severity_level = 3
    sess = ort.InferenceSession(mp, sess_options=so,
                                providers=['DmlExecutionProvider', 'CPUExecutionProvider'])
    inp = sess.get_inputs()[0]
    print('模型 %s  EP=%s  dtype=%s' % (os.path.basename(mp), sess.get_providers()[0], inp.type), flush=True)

    done = skip = fail = 0
    t0 = time.time()
    for i, (key, src, (w, h)) in enumerate(tg, 1):
        d, nm = key.split('/', 1)
        dst = os.path.join(HD, d, nm + '.png')
        if not a.overwrite and os.path.exists(dst):
            if not png_complete(dst):
                print('  截断，删掉重来 %s' % key, flush=True)
                os.remove(dst)                       # 断电留下的半截文件，尺寸头是合法的
            elif png_size(dst) == (w * SCALE, h * SCALE):
                skip += 1
                continue
        try:
            im = Image.open(src).convert('RGB')
            arr = np.asarray(im, dtype=np.float32) / 255.0
            t = time.time()
            if w * h <= a.tile * a.tile:
                z = np.transpose(arr, (2, 0, 1))[None]
                if 'float16' in inp.type:
                    z = z.astype(np.float16)
                o = np.transpose(sess.run(None, {inp.name: z})[0][0].astype(np.float32), (1, 2, 0))
                o = np.clip(o, 0, 1)
            else:
                o = upscale(sess, inp.name, inp.type, arr, a.tile, a.overlap)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            Image.fromarray((o * 255).round().astype(np.uint8)).save(dst, 'PNG', optimize=False)
            done += 1
            el = time.time() - t0
            print('[%d/%d] %s  %dx%d -> %dx%d  %.1fs  %.1f MB  累计 %.0fs 剩 %.0fmin'
                  % (i, len(tg), key, w, h, o.shape[1], o.shape[0], time.time() - t,
                     os.path.getsize(dst) / 1e6, el, (el / i) * (len(tg) - i) / 60), flush=True)
        except Exception as e:
            fail += 1
            print('[%d/%d] FAIL %s: %s' % (i, len(tg), key, str(e)[:200]), flush=True)
    print('完成 %d / 跳过(已存在) %d / 失败 %d / 总耗时 %.0fs / 产物 %.1f MB'
          % (done, skip, fail, time.time() - t0,
             sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(HD) for f in fs) / 1e6), flush=True)
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
