#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 LuaConfDataReader 的 Header_32[5]/Header_64[5]/Footer[26] 三个 byte[] 真值挖出来。

已知（08/09 号实测）：
  * `.cctor`（RVA 0x3C1577A）里是 `Array::New(5)/(5)/(0x1a)` + `RuntimeHelpers.InitializeArray`，
    三个 handle 全局各存一个 **FIELD 元数据 token**：0x80000023 / 0x80000005 / 0x80000027。
  * il2cpp 里 InitializeArray 的数据源就是 metadata 的 `fieldDefaultValues` 表
    （v24+ 记录 = {int32 fieldIndex; int32 typeIndex; int32 dataIndex}，12 字节），
    dataIndex 指向 `fieldAndParameterDefaultValueData` 堆。
    昨天按 `token & 0x7fffffff` 当**条目下标**去解，取出等差序列 -> 那条否证是对的，
    但归因错了：token 的 rid 不是条目下标。

本脚本不再猜索引，改用**内容反查**：LuaConfDataReader 的 TypeDefIndex 由 dump.cs 直接给出
（1133），于是在整份 global-metadata.dat 的 int32 视图里暴力找 `(a, 1133, c)` 这种三元组，
由命中位置反推真实 stride 与表边界，再用 dataIndex 去堆里取 5/5/26 字节。

**自验证判据**（这是关键，不接受"取出来了"就算完）：
  Header 若真是容器封帧，它必须**逐字节等于**真实文件的开头若干字节；
  Footer 必须等于文件结尾若干字节。两边任一不对，就如实报"取到的不是它"。

用法: py -3 tools/sharecfg_re/14_extract_field_blobs.py
"""
import json, os, re, struct, sys
from collections import Counter

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MD = os.path.join(ROOT, 'files', 'il2cpp', 'Metadata', 'global-metadata.dat')
CFG = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
DUMPCS = os.path.join(ROOT, '.diag', 'sharecfg_re', 'dump', 'dump.cs')
TYPEDEF = 1133                      # LuaConfDataReader，来自 dump.cs 注释
SIZES = {'Header_32': 5, 'Header_64': 5, 'Footer': 26}
TOKENS = {'Header_32': 0x80000023, 'Header_64': 0x80000005, 'Footer': 0x80000027}


def typedef_index_of(cls):
    """从 dump.cs 里读 `// TypeDefIndex: N`，避免硬编码。"""
    with open(DUMPCS, encoding='utf-8', errors='replace') as f:
        for line in f:
            if re.search(r'(class|struct|enum)\s+%s\b' % re.escape(cls), line):
                m = re.search(r'TypeDefIndex:\s*(\d+)', line)
                if m:
                    return int(m.group(1))
    return None


def main():
    data = open(MD, 'rb').read()
    n = len(data)
    print('metadata %d 字节  magic=0x%08X version=%d'
          % (n, *struct.unpack_from('<II', data, 0)))
    td = typedef_index_of('LuaConfDataReader')
    print('LuaConfDataReader TypeDefIndex = %s（脚本内置 %d）' % (td, TYPEDEF))
    td = td or TYPEDEF

    v = np.frombuffer(data, dtype='<i4')
    # 内容反查：(fieldIndex, typeIndex, dataIndex) 且 typeIndex == td
    cand = np.nonzero(v[:-1] == td)[0]
    print('typeIndex==%d 的 int32 出现 %d 次（抽样下标 %s）'
          % (td, len(cand), cand[:12].tolist()))
    # 也反查 token rid 本身（万一 stride/顺序不同）
    for name, tok in TOKENS.items():
        rid = tok & 0x7FFFFFFF
        pos = np.nonzero(v == rid)[0]
        print('  %-10s rid=%-4d 在 metadata 里作为 int32 出现 %d 次 %s'
              % (name, rid, len(pos), pos[:8].tolist()))

    # 用「三元组里第三个数落在合理 dataIndex 区间」筛出真正的 FDV 记录
    good = []
    for i in cand:
        a, b, c = int(v[i - 1]), int(v[i]), int(v[i + 1])
        if 0 <= c < n and 0 <= a < 200000:
            good.append((i, a, b, c))
    print('\n候选 FDV 三元组 (fieldIndex,typeIndex,dataIndex)：%d 个' % len(good))
    step = Counter(g[0] for g in good)
    for i, a, b, c in good[:40]:
        print('   v32 下标 %-9d -> fieldIndex=%-8d typeIndex=%-6d dataIndex=%-9d  字节对齐 0x%X'
              % (i, a, b, c, c))
    if not good:
        print('=> 没找到 (a,%d,c) 形态；说明 v31 的 FDV 记录不是 12 字节三元组，需要换布局假设' % td)
        return 1

    # dataIndex 是相对 fieldAndParameterDefaultValueData 堆的偏移；先猜堆起点：
    # 取所有 dataIndex 的最小值附近应当是 0，且堆内容可打印率高。
    dis = np.array([g[3] for g in good])
    print('\ndataIndex 范围 %d..%d；下面按“堆起点=0 的绝对/相对”两种解释各取一次字节' %
          (dis.min(), dis.max()))
    files = {os.path.basename(p): open(p, 'rb').read()
             for p in sorted(__import__('glob').glob(os.path.join(CFG, '*')))}
    ref = files.get('ship_skin_template') or next(iter(files.values()))
    for base_desc, base in (('绝对（dataIndex 直接当 metadata 偏移）', 0),
                            ('相对 fieldAndParameterDefaultValueData 起点', None)):
        if base is None:
            base = int(dis.min()) if dis.min() > 4_000_000 else 0
            print('  试探：相对基址取 dataIndex.min()=%d' % base)
        for i, a, b, c in good[:6]:
            for name, sz in SIZES.items():
                blob = data[base + c: base + c + sz]
                if len(blob) < sz:
                    continue
                head_ok = ref.startswith(blob[-sz:]) or blob in ref[:64]
                tail_ok = ref.endswith(blob[-8:]) and sz >= 8
                print('   base=%-9d fdv下标%-6d %-10s -> %s  在文件头64B内=%s 尾8一致=%s'
                      % (base, i, name, blob.hex(' '), head_ok, tail_ok))
    print('\n（自验证：Header/Footer 必须与真实文件首尾逐字节对得上，才算真挖到密钥材料）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
