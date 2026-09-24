#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定位 Header_32/Header_64/Footer 三个常量字节 + 把 34 张表的头/尾结构做对照。

两条线一起跑：
① **Footer 反查**（比猜 v31 结构稳）：Footer 的字节已从经验上量出来 = `8e 99 07 8f 99 07 a0 b9`
   （34 个 sharecfgdata 文件尾部完全一致）。拿它去 metadata / libil2cpp.so / DummyDll 里搜，
   落点就是「字段默认值 blob 区」，Header_32/Header_64（.cctor 里两个 new byte[5]）应在附近。
② **头/尾结构对照**：34 个文件逐个 dump 头 12 字节与尾 8 字节，并用 3 张**已知记录数**的表
   （ship_skin_template=2863 / ship_data_statistics=4119 / ship_data_template=3968，
   来自 inputs/azdata/azdata_*.json）做交叉验证 —— 哪个头字段等于记录数，哪就是「记录数」语义。

用法: py -3 tools/sharecfg_re/05_header_footer_map.py
"""
import os, sys, glob, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CFG = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
IL2 = os.path.join(ROOT, 'files', 'il2cpp')
DUMP = os.path.join(ROOT, '.diag', 'sharecfg_re', 'dump')
FOOTER = bytes.fromhex('8e 99 07 8f 99 07 a0 b9')

# 已知记录数（azdata 明文缓存的真实条数），用来反查头里的「记录数」语义
KNOWN_ROWS = {'ship_skin_template': 2863, 'ship_data_statistics': 4119, 'ship_data_template': 3968}


def hexs(b, n=None):
    return (b[:n] if n else b).hex(' ')


def hunt_footer():
    print('=== ① Footer %s 反查（找默认值 blob 区）===' % FOOTER.hex(' '))
    targets = [os.path.join(IL2, 'Metadata', 'global-metadata.dat'),
               os.path.join(IL2, 'libil2cpp.so')]
    targets += sorted(glob.glob(os.path.join(DUMP, 'DummyDll', '**', '*.dll'), recursive=True))
    for p in targets:
        b = open(p, 'rb').read()
        hits = []
        i = b.find(FOOTER)
        while i >= 0 and len(hits) < 8:
            hits.append(i)
            i = b.find(FOOTER, i + 1)
        tag = os.path.relpath(p, ROOT)
        if not hits:
            print('  %-46s 未命中' % tag)
            continue
        print('  %-46s 命中 %d 处: %s' % (tag, len(hits), [hex(h) for h in hits]))
        for h in hits[:3]:
            lo, hi = max(0, h - 48), h + 24
            print('      @0x%X  邻域(-48..+24):' % h)
            for off in range(lo, hi, 16):
                seg = b[off:off + 16]
                mark = ' <== Footer 起点' if off <= h < off + 16 else ''
                print('        0x%08X  %-47s%s' % (off, hexs(seg), mark))
    print()


def map_tables():
    print('=== ② 34 张表的头 12 / 尾 8 结构对照（%s 为已知记录数的表）===' % ','.join(KNOWN_ROWS))
    print('%-30s %9s  %-35s %-23s %s' % ('table', 'size', 'head12', 'tail8', '已知行数'))
    rows = []
    for p in sorted(glob.glob(os.path.join(CFG, '*'))):
        b = open(p, 'rb').read()
        name = os.path.basename(p)
        rows.append((name, len(b), b[:12], b[-8:], KNOWN_ROWS.get(name)))
        print('%-30s %9d  %-35s %-23s %s' % (name, len(b), hexs(b[:12]),
                                             hexs(b[-8:]), KNOWN_ROWS.get(name, '')))
    tailset = collections.Counter(r[3] for r in rows)
    print('\n尾 8 字节取值种类: %d  %s' % (len(tailset), [(hexs(k), v) for k, v in tailset.items()]))
    print('byte[4] 取值:', sorted({r[2][4] for r in rows}))
    print('byte[5] 取值:', sorted({r[2][5] for r in rows}))
    print('byte[6] 取值:', sorted({r[2][6] for r in rows}))
    print()
    print('--- 与「已知行数」逐字段比对（找记录数语义）---')
    for name, size, h, t, nrows in rows:
        if nrows is None:
            continue
        cands = []
        for i in range(len(h) - 1):
            le = h[i] | (h[i + 1] << 8)
            be = (h[i] << 8) | h[i + 1]
            for tag, v in (('LE16@%d' % i, le), ('BE16@%d' % i, be)):
                if v == nrows:
                    cands.append(tag)
        print('  %-26s 已知行数 %-6d 命中头字段: %s   头=%s' % (
            name, nrows, cands or '无（16 位内）', hexs(h)))
    print()
    print('--- 行数与 size 的关系（若 body 是定长记录，size/行数 应接近整数）---')
    for name, size, h, t, nrows in rows:
        if nrows:
            body = size - 12 - 8
            print('  %-26s (size-头-尾)=%-9d / 行数 %-6d = %.2f' % (name, body, nrows, body / nrows))


if __name__ == '__main__':
    hunt_footer()
    map_tables()
