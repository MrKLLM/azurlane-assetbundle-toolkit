#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 metadata 的 fieldDefaultValues 堆里捞出 LuaConfDataReader 的 Header_32 / Header_64 / Footer 字节。

来源（见 README 推进路线第 5 步）：
  .cctor @ RVA 0x3C1577A 反汇编得到——两个 `new byte[5]` + `memcpy` + 存到静态字段 offset 0x0 / 0x8，
  源数据经 `.data` 句柄表间接取：`0x71E40B8 -> 0x80000005`、`0x71E4130 -> 0x80000023`（编码索引）。
  句柄是「奇数递增 + 0x80000000 位」的编码，疑似指向 fieldDefaultValues 表的第 (v-1)/2 项。

做法：把 fieldDefaultValues 每条 12 字节 (fieldIndex, typeIndex, dataIndex) 解出来，
逐条打印 dataIndex 指向的 blob 前 16 字节，再与 scripts32/scripts64/sharecfgdata 各文件头比对，
肉眼认出哪两条是 5 字节魔数、哪条是 Footer。
"""
import os, struct, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MD = os.path.join(ROOT, 'files', 'il2cpp', 'Metadata', 'global-metadata.dat')
FDV_OFF, FDV_CNT = 9515896, 224340
DATA_OFF, DATA_CNT = 9740240, 879152

HANDLES = {'0x71E40B8 (Header_64)': 0x80000005, '0x71E4130 (Header_32)': 0x80000023}


def hexs(b):
    return b.hex(' ') if b else '(空)'


def main():
    md = open(MD, 'rb').read()
    fdv = md[FDV_OFF:FDV_OFF + FDV_CNT]
    blob = md[DATA_OFF:DATA_OFF + DATA_CNT]
    n = FDV_CNT // 12
    print('fieldDefaultValues %d 条 / 12B；defaultValueData %d 字节\n' % (n, DATA_CNT))

    print('=== 句柄解码候选（(v-1)/2 与 (v&~0x80000000) 两种解释）===')
    for tag, v in HANDLES.items():
        for name, idx in ((('(v-1)/2', (v - 1) // 2)), ('(v&0x7fffffff)', v & 0x7FFFFFFF)):
            if 0 <= idx < n:
                fi, ti, di = struct.unpack_from('<iii', fdv, idx * 12)
                raw = blob[di:di + 24] if 0 <= di < DATA_CNT else b''
                print('  %-22s %-14s -> 第%6d条 fieldIndex=%-7d typeIndex=%-7d dataIndex=%-8d data=%s'
                      % (tag, name, idx, fi, ti, di, hexs(raw[:16])))
    print()
    print('=== fieldDefaultValues 前 26 条（含疑似 5 字节魔数）===')
    for i in range(min(26, n)):
        fi, ti, di = struct.unpack_from('<iii', fdv, i * 12)
        raw = blob[di:di + 16] if 0 <= di < DATA_CNT else b''
        mark = '  <== 句柄 0x800000%02X' % (2 * i + 1) if i in (2, 17) else ''
        print('  [%2d] fieldIndex=%-7d typeIndex=%-7d dataIndex=%-8d %s%s' % (i, fi, ti, di, hexs(raw), mark))

    print('\n=== 各候选文件头（前 8 字节）用于比对 ===')
    for rel in ('files/AssetBundles/scripts32', 'files/AssetBundles/scripts64'):
        p = os.path.join(ROOT, rel)
        print('  %-34s %s   tail=%s' % (os.path.basename(p), hexs(open(p, 'rb').read(8)),
                                         hexs(open(p, 'rb').read()[-8:])))
    cfg = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
    for f in sorted(os.listdir(cfg))[:8]:
        b = open(os.path.join(cfg, f), 'rb').read()
        print('  sharecfgdata/%-24s %s   tail=%s' % (f, hexs(b[:8]), hexs(b[-8:])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
