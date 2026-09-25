#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用已知明文在 global-metadata.dat 的 fieldAndParameterDefaultValueData 堆里定位
Header_32 / Header_64 / Footer，并把 fieldDefaultValues 的 12 字节记录索引法一次判死。

为什么重做：README (14) 那次按 v24–v29 的**节序**读头，把第 8 对当成了别的节，
于是"blob 堆只有 21388 字节、里面没有 1b4c4a"——那条否证打的是错区域，不算数。

本轮先把节序重新对齐（v31 头里多了一对），并用两个独立事实交叉验证：
  * 上一轮实测 fieldDefaultValues size=224340（`%12==0`）—— 对齐后落在第 7 对。
  * 对齐后第 8 对 = 堆，size 879152；全盘 `1b4c4a` 的 6 个命中**全部**落在堆内。

判据（不接受"看着像"）：
  A. 32 张表的**文件中段** 32 字节针，若堆里存在完整副本必须逐字节命中；
  B. 11 字节公共后缀 与 26 字节 Footer 的关系（包含/被包含/无关）由命中位置直接读出；
  C. 阴性对照：同样数量、同长度的随机针（从无关区取字节后打乱），期望 0 命中；
     否则说明命中是本领域字母表太小造成的，A/B 一律不作结论。
  D. fieldDefaultValues 记录自检：12 字节步长下 (fieldIndex 单调不减、
     dataIndex < 堆大小) 两条必须同时成立，否则步长/字段序仍未知。

用法: py -3 tools/sharecfg_re/28_blob_heap_known_plaintext.py
"""
import os, struct, sys, random

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MD = os.path.join(ROOT, 'files', 'il2cpp', 'Metadata', 'global-metadata.dat')
CFG = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')

# v31 头里 (offset,size) 对的实测对齐结果：第 0 对 @256，逐对首尾相接（CONTIG 已核）
IDX_FDV = 7     # fieldDefaultValues
IDX_BLOB = 8    # fieldAndParameterDefaultValueData


def all_offsets(d):
    """堆在文件里的绝对区间。"""
    fo, fsz = struct.unpack_from('<ii', d, 8 + 8 * IDX_FDV)
    bo, bsz = struct.unpack_from('<ii', d, 8 + 8 * IDX_BLOB)
    return (fo, fsz), (bo, bsz)


def find_all(buf, pat):
    out, i = [], 0
    while True:
        j = buf.find(pat, i)
        if j < 0:
            return out
        out.append(j)
        i = j + 1


def common_suffix(raws):
    n = min(len(r) for r in raws)
    i = 0
    while i < n and len({r[-1 - i] for r in raws}) == 1:
        i += 1
    return raws[0][-i:] if i else b''


def main():
    d = open(MD, 'rb').read()
    magic, ver = struct.unpack_from('<II', d, 0)
    (fo, fsz), (bo, bsz) = all_offsets(d)
    blob = d[bo:bo + bsz]
    fdv = d[fo:fo + fsz]
    print('metadata %d B  magic=0x%08X ver=%d' % (len(d), magic, ver))
    print('fieldDefaultValues  @%-9d %d B   (%%12=%d, 记录 %d 条)'
          % (fo, fsz, fsz % 12, fsz // 12))
    print('defaultValueData 堆 @%-9d %d B   [%d..%d]' % (bo, bsz, bo, bo + bsz))

    files = sorted(os.listdir(CFG))
    raws = [open(os.path.join(CFG, f), 'rb').read() for f in files]
    print('\n配置表 %d 张，体积 %d..%d' % (len(raws), min(map(len, raws)), max(map(len, raws))))

    # ---- C. 阴性对照先跑：对照不过，后面全部不作结论
    rnd = random.Random(20260925)
    neg = []
    src = d[bo + bsz: bo + bsz + 4_000_000] or d[:232904]
    for _ in range(len(raws)):
        off = rnd.randrange(0, len(src) - 32)
        b = bytearray(src[off:off + 32])
        rnd.shuffle(b)                      # 破坏任何真实结构，保持字母表
        neg.append(bytes(b))
    neg_hits = sum(1 for p in neg if find_all(d, p))
    print('[对照 C] 32 条随机 32B 针在全文件命中 %d 条 -> %s'
          % (neg_hits, '通过（字母表不致假命中）' if neg_hits == 0 else '不通过，本轮不作任何肯定结论'))
    if neg_hits:
        return 3

    # ---- A. 表体中段 32B 针：堆里有没有整表副本
    print('\n[A] 各表中段 32B 针 -> global-metadata 全文件命中（括号内为相对堆基址）')
    a_hit = 0
    for f, r in zip(files, raws):
        mid = r[len(r) // 2:len(r) // 2 + 32]
        hs = find_all(d, mid)
        inblob = [h - bo for h in hs if bo <= h < bo + bsz]
        if hs:
            a_hit += 1
        print('  %-30s abs=%s  in-heap=%s' % (f, ['0x%X' % h for h in hs[:3]], inblob[:3]))
    print('  => %d/%d 命中' % (a_hit, len(files)))

    # ---- B. 公共后缀 / Header
    cs = common_suffix(raws)
    print('\n[B] %d 字节公共后缀 = %s' % (len(cs), cs.hex()))
    for h in find_all(d, cs):
        tag = 'heap+%d' % (h - bo) if bo <= h < bo + bsz else 'outside-heap'
        print('    全文件命中 0x%X (%s)  前 16B: %s  后 16B: %s'
              % (h, tag, d[h - 16:h].hex(' '), d[h:h + 16].hex(' ')))
    for h in find_all(d, bytes.fromhex('1b4c4a')):
        print('    1b4c4a @0x%X  head16=%s  %s' % (h, d[h:h + 16].hex(' '),
              'in-heap' if bo <= h < bo + bsz else 'outside'))
    # 每张表自己的头 5B 是否也在堆里
    for f, r in zip(files[:6], raws[:6]):
        hs = find_all(d, r[:5])
        print('    %-28s head5=%s -> %s' % (f, r[:5].hex(), ['0x%X' % x for x in hs[:4]]))

    # ---- D. fieldDefaultValues 记录自检
    print('\n[D] 12B 记录 (a,b,c) 自检')
    n = fsz // 12
    vals = [struct.unpack_from('<iii', fdv, 12 * i) for i in range(n)]
    mono = sum(1 for i in range(1, n) if vals[i][0] < vals[i - 1][0])
    rng_a = (min(v[0] for v in vals), max(v[0] for v in vals))
    rng_b = (min(v[1] for v in vals), max(v[1] for v in vals))
    rng_c = (min(v[2] for v in vals), max(v[2] for v in vals))
    print('  记录 %d 条  a 逆序次数=%d  a 范围=%s' % (n, mono, rng_a))
    print('  b 范围=%s  c 范围=%s   (堆大小 %d)' % (rng_b, rng_c, bsz))
    inc = sum(1 for i in range(1, n) if vals[i][2] >= vals[i - 1][2])
    print('  c 单调不减比例=%.3f  -> 若 a 单调且 c 单调，则 (fieldIndex,?,dataIndex) 成立'
          % (inc / (n - 1)))
    dist_c = {}
    for i in range(0, min(n, 12)):
        a, b, c = vals[i]
        loc = bo + c if 0 <= c < bsz else None
        dist_c[i] = (a, b, c, d[loc:loc + 8].hex(' ') if loc else '-')
    for i, t in dist_c.items():
        print('    #%d a=%d b=%d c=%d -> %s' % (i, *t[:3], t[3]))

    # ---- E. 用相邻 dataIndex 之差切出每个 blob 的真实长度，再按内容定位三个数组
    print('\n[E] blob 切分（len_k = c_{k+1} - c_k）')
    starts = {}
    for i, (a, b, c) in enumerate(vals):
        starts.setdefault(c, i)
    lens = []
    for i, (a, b, c) in enumerate(vals):
        nxt = vals[i + 1][2] if i + 1 < n else bsz
        lens.append(nxt - c)
    h64 = bytes.fromhex('1b4c4a0202')
    cand = [(i, vals[i][0], lens[i]) for i in range(n)
            if d[bo + vals[i][2]:bo + vals[i][2] + 5] == h64]
    print('  内容 == Header_64(1b4c4a0202) 的记录: %s' % ([(i, a, l) for i, a, l in cand],))
    print('  所有以 1b4c4a 开头的 blob（不限长度）：')
    for i, (a, b, c) in enumerate(vals):
        if d[bo + c:bo + c + 3] == bytes.fromhex('1b4c4a'):
            print('    rec#%-6d fieldIndex=%-6d len=%-6d %s'
                  % (i, a, lens[i], d[bo + c:bo + c + min(lens[i], 24)].hex(' ')))
    for i, a, l in cand:
        print('    记录#%d fieldIndex=%d len=%d' % (i, a, l))
        for delta, name in ((30, 'Header_32(应 5B)'), (0, 'Header_64'), (34, 'Footer(应 26B)')):
            j = next((k for k, v in enumerate(vals) if v[0] == a + delta), None)
            if j is None:
                print('      fieldIndex %d (%s) 无记录' % (a + delta, name))
                continue
            c = vals[j][2]
            print('      fieldIndex %-6d (%s) rec#%-6d len=%-4d data=%s'
                  % (a + delta, name, j, lens[j], d[bo + c:bo + c + max(lens[j], 1)].hex(' ')))
    # 76 字节 = 19 个 int32 的候选（www 的 TEA 密钥表）
    print('\n  76B 且能读成 19 个"像密钥"的 int32 的 blob：')
    k76 = 0
    for i, L in enumerate(lens):
        if L != 76:
            continue
        w = list(struct.unpack_from('<19i', d, bo + vals[i][2]))
        # 判据：至少 4 个字 >=2^24（真随机密钥几乎必然），排除小整数表
        if sum(1 for x in w if x < 0 or x >= (1 << 24)) >= 4:
            k76 += 1
            if k76 <= 12:
                print('    rec#%-6d fieldIndex=%-6d %s' % (i, vals[i][0],
                      ' '.join('%08X' % (x & 0xFFFFFFFF) for x in w[:8]) + ' ...'))
    print('    => %d 个候选（整堆 76B blob 共 %d 个）'
          % (k76, sum(1 for L in lens if L == 76)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
