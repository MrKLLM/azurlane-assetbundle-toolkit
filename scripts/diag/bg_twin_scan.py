#!/usr/bin/env python3
"""bg_twin_scan.py — 在背景库里找「同一张画存在两个尺寸」的孪生对（唯一不涉及生成的提清晰度手段）。

为什么需要：用户 2026-10-08 否掉了 AI 超分（补出来的像素属于推断，见 §121），但库里确实有极少数
图**同一张画画了两份、一份分辨率更高**。这类不是加工，是"把条目指向已有的那份大的"，零编造。

两步判据（缺一不可，单靠任何一步都会误判）：
  1. **感知哈希**（dHash 16×16，汉明距离 <= --maxham）先粗筛出候选对——只看结构，不受尺寸影响。
  2. **像素 RMS + 对照组**再定性：两图各自缩到 64×36 比逐通道 RMS，并和"随机两张不同图"的
     RMS 分布比。**没有对照组就无法判定**——RMS 30 到底是"很像"还是"一般像"，只有对照能回答。
     （本轮实测：对照组中位 81.3，命中的 8 对全在 0.5~21.1。）
  3. **宽高比必须一致**才算"同一张图的清晰版"。宽高比不同说明是**不同裁切**（例：`login__2`
     是 2:1 横幅、`login_qiye` 是 16:9），指向它等于换画面构图，那不是提清晰度而是改内容。
  4. ⚠️ **过了 1~3 也只是"候选"，必须逐对目视**。本脚本第一轮跑出 6 对"数值全过"的候选，
     人眼一遍后 **5 对被否**（见 `.diag/twin_check*.png`）：
     · `bg_camelot_4`(1024) vs `star_level_bg_5_1`(1920) 与 `newshipbg/bg_5_1`(1920)：
       大图把 **"NEW SHIP LAUNCHED" 等 UI 文字烤进了像素**，不是干净底图；
     · `star_level_bg_1103`(1024) vs `star_level_bg_106`(1280)：小图是**故意做的虚化版**（游戏拿来垫 UI），
       指过去等于替用户去掉景深；
     · `star_level_bg_107`(1280) vs `star_level_bg_599`(1920)：墙上那幅**画的内容不一样**（鲨鱼 / 山景）；
     · `commonbg/technology_bg`(1280) vs `bg_lottery`(1920)：大图多烤了一行中文说明
       「※当前奖池主要奖励获取完毕后，可以解锁下一个奖池」。
     ⇒ 数值只能筛"结构相似"，**分不清"同一张画的两个尺寸"和"同一场景的两个版本"**，
       而后者指过去就是换内容。目视要看三样：有没有多烤字、有没有虚化/调色差异、细节元素是否一致。

用法: py -3 scripts/diag/bg_twin_scan.py [--maxham 10] [--ratio 0.45]
产物: .diag/bg_twin_scan.json（**候选**与证据，含被拒的宽高比不一致对）—— 名字就叫 candidates，
      不叫 accepted：过数值 ≠ 可指。人工目视后若真有可指的，再写进
      `annotations/bg_twin_pairs.json`（入库正本，本轮**为空**），索引只读那份正本、不读这里。
"""
import argparse
import itertools
import json
import os
import struct
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RAW = os.path.join(ROOT, 'Output', 'Raw')
OUT = os.path.join(ROOT, '.diag', 'bg_twin_scan.json')


def list_pngs():
    out = []
    for d in sorted(os.listdir(RAW)):
        p = os.path.join(RAW, d)
        if not os.path.isdir(p):
            continue
        for f in sorted(os.listdir(p)):
            if f.endswith('.png'):
                out.append('%s/%s' % (d, f[:-4]))
    return out


def dhash(key, size=16):
    im = Image.open(os.path.join(RAW, key.replace('/', os.sep) + '.png')).convert('L')
    a = np.asarray(im.resize((size + 1, size), Image.BILINEAR), dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()


def small(key, wh=(64, 36)):
    im = Image.open(os.path.join(RAW, key.replace('/', os.sep) + '.png')).convert('RGB')
    return np.asarray(im.resize(wh, Image.BILINEAR), dtype=np.float32)


def rms(a, b):
    return float(np.sqrt(((a - b) ** 2).mean()))


def png_size(key):
    with open(os.path.join(RAW, key.replace('/', os.sep) + '.png'), 'rb') as f:
        return struct.unpack('>II', f.read(24)[16:24])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--maxham', type=int, default=10)
    ap.add_argument('--ratio', type=float, default=0.45)
    a = ap.parse_args()

    keys = list_pngs()
    print('扫描 %d 张' % len(keys))
    H = np.stack([dhash(k) for k in keys])
    D = (H[:, None, :] != H[None, :, :]).sum(axis=2)
    cand = [(keys[i], keys[j], int(D[i, j])) for i, j in zip(*np.triu_indices(len(keys), 1))
            if D[i, j] <= a.maxham]
    print('汉明 <= %d 的候选对: %d' % (a.maxham, len(cand)))

    # 对照组：随机抽 400 对**不同**的图，量出"完全不相干"的 RMS 基线
    rng = np.random.default_rng(11)
    ctl = []
    for _ in range(400):
        i, j = rng.integers(0, len(keys), 2)
        if i == j:
            continue
        ctl.append(rms(small(keys[i]), small(keys[j])))
    ctl_med = float(np.median(ctl))
    print('对照组 RMS 中位 %.1f（区间 %.1f~%.1f）—— 没有这个数，"RMS 21"是无法判定的'
          % (ctl_med, min(ctl), max(ctl)))

    candidates, rejected, same_size = [], [], []
    for x, y, ham in cand:
        sx, sy = png_size(x), png_size(y)
        if sx == sy:
            same_size.append((x, y, ham))
            continue
        r = rms(small(x), small(y))
        rec = {'a': x, 'b': y, 'a_size': sx, 'b_size': sy, 'hamming': ham, 'rms': round(r, 2),
               'ctrl_median': round(ctl_med, 1),
               'aspect_a': round(sx[0] / sx[1], 4), 'aspect_b': round(sy[0] / sy[1], 4)}
        if r >= a.ratio * ctl_med:
            continue                                    # 不像同图，直接丢
        if abs(rec['aspect_a'] - rec['aspect_b']) > 0.02:
            rec['why_reject'] = '宽高比不同 ⇒ 是不同裁切，指向它等于换构图'
            rejected.append(rec)
        else:
            rec['bigger'] = x if sx[0] * sx[1] > sy[0] * sy[1] else y
            rec['smaller'] = y if rec['bigger'] == x else x
            candidates.append(rec)
    print('同图不同尺寸：候选（宽高比一致，**仍需逐对目视**）%d 对 / 拒绝（不同裁切）%d 对 / 同尺寸重复 %d 对'
          % (len(candidates), len(rejected), len(same_size)))
    for rec in candidates:
        print('   [待目视] %-29s %-32s rms %5.1f  大 = %s'
              % (rec['a'], rec['b'], rec['rms'], rec['bigger']))
    print('⚠️ 数值过 ≠ 可指：本轮 6 对候选目视后 5 对被否（多烤字 / 虚化版 / 细节不同），见脚本头第 4 条')
    for rec in rejected:
        print('   [拒] %-31s %-34s rms %5.1f  %.3f vs %.3f'
              % (rec['a'], rec['b'], rec['rms'], rec['aspect_a'], rec['aspect_b']))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'ctrl_median': ctl_med, 'candidates': candidates, 'rejected': rejected,
                   'identical_size_pairs': same_size[:50]}, f, ensure_ascii=False, indent=1)
    print('证据写到', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
