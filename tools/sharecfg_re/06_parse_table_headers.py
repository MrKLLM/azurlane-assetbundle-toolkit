#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B 步：把 32 张 sharecfgdata 表的头按 LEB128 变长整数解开，并用已知行数定位「记录数」语义。

依据（05_ 的实测）：
  - 头的尾段是变长整数（`activity_coloring` 的 `b7 03`、`world_chapter` 的 `80 01`；
    `gametip`/`weapon_name` 头短 2 字节），不是定长字段。
  - `byte[2] == byte[3]` 恒成立（gametip/weapon_name 例外 byte[3]=0）；`byte[4]` 恒 0。
  - 记录**变长**（body/行数 1076.28 / 507.39 / 1420.23 全非整数）。
  - 尾 8 字节 32/32 一致 = `8e 99 07 8f 99 07 a0 b9`。

一锤定音的判据：**已知行数 2863 / 4119 / 3968 到底编码在哪里**。
对每张已知表，在「头 32 字节 + body 前 4096 字节」里按 7 种编码穷举：
  u8 / u16-LE / u16-BE / u24-LE / u32-LE / u32-BE / LEB128 / zigzag-LEB128
命中即定语义；同时也试「行数-1」「行数+1」（索引表常少一条或含哨兵）。
"""
import os, sys, struct, glob

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CFG = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
KNOWN_ROWS = {'ship_skin_template': 2863, 'ship_data_statistics': 4119, 'ship_data_template': 3968}
TAIL8 = bytes.fromhex('8e 99 07 8f 99 07 a0 b9')


def leb128(b, i):
    v = s = 0
    while i < len(b):
        c = b[i]; i += 1
        v |= (c & 0x7F) << s
        s += 7
        if not (c & 0x80):
            return v, i
    return None, i


def zigzag(v):
    return (v >> 1) ^ -(v & 1)


def parse_header(b):
    """b[0] 视为校验字节，其后连着读 LEB128，直到读到 9 个值或碰到 body 特征。
    body 起点经验值在 8~11 字节处，所以最多读 8 个值即可覆盖。"""
    out = [('b0', b[0])]
    i = 1
    for k in range(8):
        v, j = leb128(b, i)
        if v is None:
            break
        out.append(('v%d' % k, v))
        i = j
    return out, i


def find_number(buf, target):
    """在 buf 里找 target 的各种编码，返回 [(编码, 偏移)]。"""
    hits = []
    for name, enc in (('u16-LE', struct.pack('<H', target)), ('u16-BE', struct.pack('>H', target)),
                      ('u24-LE', struct.pack('<I', target)[:3]), ('u24-BE', struct.pack('>I', target)[1:]),
                      ('u32-LE', struct.pack('<I', target)), ('u32-BE', struct.pack('>I', target))):
        i = buf.find(enc)
        while i >= 0 and len(hits) < 6:
            hits.append((name, i))
            i = buf.find(enc, i + 1)
    # LEB128 / zigzag
    for tag, want in (('LEB128', target), ('zigzag', (target << 1))):
        i = 0
        while i < len(buf) and len(hits) < 24:
            v, j = leb128(buf, i)
            if v is None:
                break
            if v == want:
                hits.append((tag, i))
            i += 1 if j == i else (j - i) if j > i else 1
            if i >= len(buf):
                break
    return hits


def main():
    files = sorted(glob.glob(os.path.join(CFG, '*')))
    print('=== ① 头部按 LEB128 解开（b0 视为校验字节，其后是变长整数序列）===')
    print('%-30s %4s  %s' % ('table', 'hdr', '解出的值'))
    heads = {}
    for p in files:
        b = open(p, 'rb').read()
        vals, hdr = parse_header(b)
        heads[os.path.basename(p)] = (vals, hdr)
        print('%-30s %4d  %s' % (os.path.basename(p), hdr,
                                 ' '.join('%s=%d' % kv for kv in vals)))

    print('\n=== ② 一锤定音：已知行数编码在哪（头 32B + body 前 4096B，含 行数±1）===')
    for name, nrows in KNOWN_ROWS.items():
        p = os.path.join(CFG, name)
        b = open(p, 'rb').read()
        window = b[:4128]
        print('  %s（行数 %d）头=%s' % (name, nrows, b[:12].hex(' ')))
        for label, t in (('行数', nrows), ('行数-1', nrows - 1), ('行数+1', nrows + 1)):
            hits = find_number(window, t)
            print('     %-7s %-5d -> %s' % (label, t, hits[:8] if hits else '未命中'))

    print('\n=== ③ body 起点后的 4 字节记录结构（索引表候选）===')
    for name in list(KNOWN_ROWS) + ['gametip', 'weapon_name']:
        p = os.path.join(CFG, name)
        b = open(p, 'rb').read()
        vals, hdr = heads[name]
        body = b[hdr:len(b) - 8]
        nrec4 = len(body) // 4
        print('  %-24s hdr=%d body=%d  /4=%d  /8=%d  /12=%d  已知行数=%s'
              % (name, hdr, len(body), nrec4, len(body) // 8, len(body) // 12,
                 KNOWN_ROWS.get(name, '-')))
        print('     body 前 24: %s' % body[:24].hex(' '))
    return 0


if __name__ == '__main__':
    sys.exit(main())
