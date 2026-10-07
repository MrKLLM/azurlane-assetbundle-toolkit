#!/usr/bin/env python3
"""bg_hd_model_cmp.py — 背景图 AI 超分**选型**探针：同一张图跑多个 ONNX 模型，出同尺寸对比条。

为什么需要它：超分模型的名字（anime / general / UltraSharp）看不出真实差异，而它们对
「厚涂场景」和「平涂登录图」的表现正好相反——一个把笔触抹平、一个把线稿画糊。
必须同图同区域并排看，不能凭 README 选。

必须用 venv 的 python 跑（依赖 onnxruntime-directml，不装进全局环境）：
  tools/upscale/venv/Scripts/python.exe scripts/diag/bg_hd_model_cmp.py

判据（每条都要过一遍再下结论）：
  1. 线稿边缘：平涂图看眼睛/发丝有没有断裂或凭空多出的线条（幻觉）。
  2. 厚涂纹理：战斗/烟雾场景看笔触颗粒有没有被抹成塑料面。
  3. 文字与水印：CG 上若有小字，放大后不许变形糊成一团。
  4. 耗时：单张推理秒数，决定 263 张全量的可行性。
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MODELS = os.path.join(ROOT, 'tools', 'upscale', 'models')
DEF_MODELS = ['realesr-general-x4v3-fp16.onnx', 'anime6b.onnx', 'ultrasharp-fp16.onnx']


def load(p):
    so = ort.SessionOptions()
    so.log_severity_level = 3
    s = ort.InferenceSession(p, sess_options=so,
                             providers=['DmlExecutionProvider', 'CPUExecutionProvider'])
    i = s.get_inputs()[0]
    return s, i.name, i.type


def run(sess, iname, itype, im):
    """PIL RGB -> 4x ndarray。fp16 模型要喂 fp16，喂错 dtype 会在 DML 侧直接抛。"""
    a = np.asarray(im, dtype=np.float32) / 255.0
    x = np.transpose(a, (2, 0, 1))[None]
    if 'float16' in itype:
        x = x.astype(np.float16)
    o = sess.run(None, {iname: x})[0][0]
    o = np.clip(np.transpose(o.astype(np.float32), (1, 2, 0)), 0.0, 1.0)
    return Image.fromarray((o * 255).round().astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keys', nargs='+', required=True,
                    help='形如 bg/bg_banama_3 的索引 key（<类目>/<不含扩展名的文件名>）')
    ap.add_argument('--models', nargs='+', default=DEF_MODELS)
    ap.add_argument('--disp', type=int, default=900, help='每个分栏的显示宽度（模拟屏幕放大）')
    ap.add_argument('--out', default=os.path.join(ROOT, '.diag', 'hd_test'))
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    loaded = []
    for m in a.models:
        p = m if os.path.isabs(m) else os.path.join(MODELS, m)
        s, iname, itype = load(p)
        loaded.append((os.path.basename(p).replace('.onnx', ''), s, iname, itype))
        print('模型就绪', os.path.basename(p), 'EP=', s.get_providers()[0], 'in dtype=', itype)

    for key in a.keys:
        d, nm = key.split('/', 1)
        src = os.path.join(ROOT, 'Output', 'Raw', d, nm + '.png')
        im = Image.open(src).convert('RGB')
        w, h = im.size
        # 中心偏上取 1/4：角色脸部和主体细节基本落在这里
        cw, ch = w // 2, h // 2
        top = max(0, min(h - ch, int(h * 0.18)))
        crop = im.crop((w // 2 - cw // 2, top, w // 2 - cw // 2 + cw, top + ch))
        disp_h = int(a.disp * crop.height / crop.width)

        panels = [('native', crop)]
        secs = {}
        for label, s, iname, itype in loaded:
            t = time.time()
            ai = run(s, iname, itype, crop)
            secs[label] = time.time() - t
            panels.append((label, ai))

        sheet = Image.new('RGB', (a.disp * len(panels) + 8 * (len(panels) - 1), disp_h + 22), (18, 20, 26))
        dr = ImageDraw.Draw(sheet)
        for i, (label, img) in enumerate(panels):
            small = img.resize((a.disp, disp_h), Image.LANCZOS) if label == 'native' else \
                img.resize((a.disp, disp_h), Image.LANCZOS)
            x = i * (a.disp + 8)
            sheet.paste(small, (x, 22))
            tag = '%s %s' % (label, '' if label == 'native' else '%.1fs' % secs[label])
            dr.text((x + 6, 6), tag, fill=(255, 255, 0))
        out = os.path.join(a.out, 'cmp4_%s.png' % nm)
        sheet.save(out)
        print('对比条 %s  源 %dx%d  ->  %s  %s' % (key, w, h,
              ' | '.join('%s %.1fs' % (k, v) for k, v in secs.items()), out))


if __name__ == '__main__':
    main()
