#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按「记录边界」试解压：检验"逐记录/逐字段压缩"这一形状。

为什么之前的压缩测试不算数：昨天只试过**文件偏移 0..63** 起头的裸 zlib/deflate/lz4/bz2。
但 12 号差分签名已把"段内恒定 xor/加减"整类否证掉，而下面四件事必须同时成立：
  1) 单文件内 16 字节块重复数百次（iid 期望 1e-6，加密流不可能）
  2) 已知明文 0 命中（4634 串 × 4 编码）
  3) 整体熵 6.7~7.8、IC 0.01~0.02
  4) 头部是可解的定长记录 + LEB128 小整数，且 `ReadData(name,startPos,size)` 是**定点切片读**
唯一同时满足的自然解释就是：**明文索引/头 + 每条记录载荷各自压缩**（同文本 -> 同压缩块，
所以块重复；文本本身被压掉，所以 0 明文）。既然是逐记录压缩，压缩流起点就落在**记录边界**上，
而记录边界我们已经能从重复标记量出来了 —— 所以要试的偏移是那 ~2865 个标记位置，
不是 0..63。这才是没做过的测试。

用法: py -3 tools/sharecfg_re/13_record_inflate.py [--table ship_skin_template]
"""
import argparse, json, os, re, sys, zlib, bz2, lzma

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CFG = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
AZ = os.path.join(ROOT, 'inputs', 'azdata')
MARK = bytes.fromhex('8e99078f9907a0b9')

try:
    import lz4.block as _L4
    HAVE_LZ4 = True
except Exception:
    HAVE_LZ4 = False


def known_strings(tbl, n=200):
    f = {'ship_skin_template': 'azdata_ship_skin_template.json',
         'ship_data_statistics': 'azdata_ship_data_statistics.json'}.get(tbl)
    if not f:
        return []
    out = []

    def rec(o):
        if isinstance(o, dict):
            [rec(v) for v in o.values()]
        elif isinstance(o, list):
            [rec(v) for v in o]
        elif isinstance(o, str) and len(o) >= 2 and re.search(r'[一-鿿]', o):
            out.append(o)
    rec(json.load(open(os.path.join(AZ, f), encoding='utf-8')))
    return sorted(set(out))[:n]


def offsets_of(b, pat, cap=4000):
    offs, i = [], b.find(pat)
    while i >= 0 and len(offs) < cap:
        offs.append(i)
        i = b.find(pat, i + 1)
    return offs


def score(buf, words):
    """解压产物评分：命中原表中文串 > 可读比例。"""
    hit = sum(1 for w in words if w.encode('utf-8') in buf)
    pr = sum(1 for c in buf if 32 <= c < 127 or c >= 0x80) / max(1, len(buf))
    return hit, pr


def try_at(b, o, words, sizes=(2048, 8192, 65536)):
    """在一个候选起点上把所有 codec × 长度前缀约定各试一遍。"""
    got = []
    for ln in (None,) + tuple(
            [int.from_bytes(b[o - k:o], 'little') for k in (4, 2)
             if o >= k and 8 < int.from_bytes(b[o - k:o], 'little') < 1 << 20]):
        for back, cut in ((0, b[o:o + (ln or 65536)]),
                          (1, b[o + 1:o + 1 + (ln or 65536)])):
            raw = cut
            if len(raw) < 8:
                continue
            trials = []
            try:
                trials.append(('zlib', zlib.decompress(raw)))
            except Exception:
                pass
            for wbits, nm in ((-15, 'raw-deflate'), (31, 'gzip'), (16, 'raw-rle?')):
                try:
                    d = zlib.decompressobj(wbits)
                    out = d.decompress(raw, 1 << 22)
                    if len(out) > 16:
                        trials.append((nm, out))
                except Exception:
                    pass
            try:
                trials.append(('lzma', lzma.decompress(raw[:1 << 20])))
            except Exception:
                pass
            try:
                trials.append(('bz2', bz2.decompress(raw[:1 << 20])))
            except Exception:
                pass
            if HAVE_LZ4:
                for us in sizes:
                    try:
                        out = _L4.decompress(raw, uncompressed_size=us)
                        if len(out) > 16:
                            trials.append(('lz4.block/%d' % us, out))
                    except Exception:
                        pass
            for nm, out in trials:
                h, p = score(out, words)
                if h or p > 0.6:
                    got.append((o, back, ln, nm, len(out), h, round(p, 3), out[:48]))
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--table', default='ship_skin_template')
    ap.add_argument('--noff', type=int, default=200, help='最多试多少个记录边界')
    a = ap.parse_args()
    p = os.path.join(CFG, a.table)
    b = open(p, 'rb').read()
    words = known_strings(a.table)
    print('%s size=%d  已知明文串 %d  标记出现位置取前 %d 个' % (a.table, len(b), len(words), a.noff))
    offs = offsets_of(b, MARK, a.noff)
    print('候选起点：%d 个，前 6 个 %s' % (len(offs), offs[:6]))
    # 也试文件头、以及"标记 +1/+4/-4" 等常见帧偏移
    extra = [x for o in offs[:40] for x in (o - 4, o - 2, o + 1, o + 2, o + 4, o + 8)] + \
            [8, 9, 10, 11, 12, 16, 24, 32, 60, 64, 128, 256, 512, 1024]
    cand = sorted(set(offs + [x for x in extra if 0 <= x < len(b) - 16]))
    print('总试 %d 个起点（含标记前后 ±4/±8 与文件头若干）…' % len(cand))
    wins = []
    for o in cand:
        wins += try_at(b, o, words)
        if len(wins) > 6:
            break
    if not wins:
        print('\n判定：0 个起点能按 zlib/deflate/gzip/lzma/bz2%s 解出可读块'
              % ('/lz4.block' if HAVE_LZ4 else '（lz4 不可用）'))
        print('  -> 「逐记录压缩」这一形状里，**标准 codec + 常见长度前缀**已排除；'
              '剩下的可能是自研/Lua 内实现的压缩（如 Lua 版 huffman / RLE / 位打包），'
              '或"非压缩的真加密"。这两种都必须看解析器代码，密文侧到此为止。')
    else:
        print('\n!! 有解出可读内容的起点：')
        for w in wins[:12]:
            print('   off=%d back=%d len_pref=%s codec=%s 出=%d 命中=%d 可读=%.3f 前48B=%r'
                  % w)


if __name__ == '__main__':
    main()
