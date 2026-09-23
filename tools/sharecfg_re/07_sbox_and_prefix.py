#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C 步（S-box 自检）+ B 步补完（公共前导块长度）。

【B 补完】32 张表的 body 前 24 字节经修正后完全相同（`4e ff 00 00 51 ff 01 01 …`）。
  先按这段**公共前导**定位每张表真正的 body 起点（比按变长整数个数猜稳），
  再算全部表 body 的**最长公共前缀长度** —— 若显著大于 24，那就是一段共享的 schema 块。

【C】疑似 S-box：按 `(句柄 & 0x7fffffff)` 解成 fieldDefaultValues 条目后，
  取回的字节是 `00 02 04 06 08 0a…`、`34 36 38 3a…` 这类等差序列，像字节置换表。
  但 v31 的记录布局未确认，必须先自检再用。自检方法：**对候选步长 8/12/16/24 逐个解，
  看 fieldIndex 是否在合理范围（0..~1.5M）内且单调递增、dataIndex 是否单调且在堆内**。
  哪个步长自洽，就是真布局。

用法: py -3 tools/sharecfg_re/07_sbox_and_prefix.py
"""
import os, sys, struct, glob

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CFG = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
MD = os.path.join(ROOT, 'files', 'il2cpp', 'Metadata', 'global-metadata.dat')
FDV_OFF, FDV_CNT = 9515896, 224340
DATA_OFF, DATA_CNT = 9740240, 879152
PREFIX = bytes.fromhex('4e ff 00 00 51 ff 01 01')
HANDLES = {'Header_32': 0x80000023, 'Header_64': 0x80000005, 'Footer': 0x80000027}


def read_entry(fdv, idx, stride):
    if stride >= 12:
        fi, ti, di = struct.unpack_from('<iii', fdv, idx * stride)
    else:
        fi, di = struct.unpack_from('<ii', fdv, idx * stride)
        ti = -1
    return fi, ti, di


def part_b():
    print('=== B 补完：用公共前导定位 body 起点 + 最长公共前缀 ===')
    bodies = {}
    for p in sorted(glob.glob(os.path.join(CFG, '*'))):
        b = open(p, 'rb').read()
        i = b.find(PREFIX)
        name = os.path.basename(p)
        if i < 0:
            print('  %-30s 未找到公共前导（该表格式不同）' % name)
            continue
        bodies[name] = b[i:len(b) - 8]
        print('  %-30s body 起点=%2d  body=%d' % (name, i, len(bodies[name])))
    names = sorted(bodies)
    if len(names) < 2:
        return
    ref = bodies[names[0]]
    n = min(len(v) for v in bodies.values())
    lcp = 0
    while lcp < n and all(v[lcp] == ref[lcp] for v in bodies.values()):
        lcp += 1
    print('\n  %d 张表 body 的**最长公共前缀 = %d 字节**' % (len(names), lcp))
    for off in range(0, min(lcp, 64), 16):
        print('    +0x%02X  %s' % (off, ref[off:off + 16].hex(' ')))
    print('  公共块之后第一段（看是否开始分化）:')
    for k in names[:2]:
        print('    %-28s %s' % (k, ref[lcp:lcp + 24].hex(' ') if k == names[0]
                                else bodies[k][lcp:lcp + 24].hex(' ')))


def part_c():
    print('\n=== C：v31 fieldDefaultValues 记录布局自检（找自洽的步长）===')
    md = open(MD, 'rb').read()
    fdv = md[FDV_OFF:FDV_OFF + FDV_CNT]
    blob = md[DATA_OFF:DATA_OFF + DATA_CNT]
    best = None
    for stride in (8, 12, 16, 24):
        n = FDV_CNT // stride
        fidx, didx = [], []
        for i in range(n):
            fi, _ti, di = read_entry(fdv, i, stride)
            fidx.append(fi)
            didx.append(di)
        inr_f = sum(1 for v in fidx if 0 <= v < 1_500_000) / n
        inr_d = sum(1 for v in didx if 0 <= v < DATA_CNT) / n
        mono_f = sum(1 for a, b in zip(fidx, fidx[1:]) if b > a) / max(1, n - 1)
        mono_d = sum(1 for a, b in zip(didx, didx[1:]) if b >= a) / max(1, n - 1)
        score = inr_f + inr_d + mono_f + mono_d
        print('  步长%-3d 条目%-6d fieldIndex 范围%.3f/单调%.3f | dataIndex 范围%.3f/单调%.3f  综合%.3f'
              % (stride, n, inr_f, mono_f, inr_d, mono_d, score))
        if best is None or score > best[0]:
            best = (score, stride)
    print('  → 最自洽的步长 = %d（综合 %.3f）' % (best[1], best[0]))
    print('\n  三个句柄指向的 blob（各步长都列，肉眼判断是否像 S-box / 魔数）:')
    for tag, v in HANDLES.items():
        idx = v & 0x7FFFFFFF
        print('  -- %s  句柄=0x%08X -> 条目 %d' % (tag, v, idx))
        for stride in (8, 12, 16, 24):
            if idx * stride + stride > FDV_CNT:
                continue
            fi, ti, di = read_entry(fdv, idx, stride)
            raw = blob[di:di + 32] if 0 <= di < DATA_CNT else b''
            print('     步长%-3d fieldIndex=%-8d typeIndex=%-8d dataIndex=%-8d  %s'
                  % (stride, fi, ti, di, raw[:24].hex(' ') if raw else '(越界)'))
    print('\n  对照：scripts32 头 5 = %s   scripts64 头 5 = %s   sharecfgdata 尾 8 = %s'
          % (open(os.path.join(ROOT, 'files/AssetBundles/scripts32'), 'rb').read(5).hex(' '),
             open(os.path.join(ROOT, 'files/AssetBundles/scripts64'), 'rb').read(5).hex(' '),
             '8e 99 07 8f 99 07 a0 b9'))


if __name__ == '__main__':
    part_b()
    part_c()
