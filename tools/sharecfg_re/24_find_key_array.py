#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用阳性对照从内存里定位 www() 用的那个 19 字节密钥数组。

为什么要对照而不是直接猜：上一轮我拿"函数里有个变换循环"当"那就是文件解密"，结果判错——
教训是**没有对照的结构推断不许往下盖楼**。这次手里有个真锚：
  * `Header_64` 的真值已经从内存 blob 头拿到了 = `1b 4c 4a 02 02`（5 字节）；
  * 它和 19 字节密钥数组**同为 IL2CPP 数组对象**，布局一致：
      +0  Il2CppClass*   +8  monitor   +16 bounds*   +24 max_length(u32)   +32 数据
所以先用已知值的 byte[5] 去**校准 +24/+32 这组偏移**；校准不成立就不许报任何密钥候选。

用法: py -3 tools/sharecfg_re/24_find_key_array.py [--dataoff 32] [--lenoff 24]
"""
import argparse, collections, glob, os, re, struct, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DUMP = os.path.join(ROOT, '.diag', 'sharecfg_re', 'memdump')
HDR64 = bytes.fromhex('1b4c4a0202')
HDR32_CAND = bytes.fromhex('1b4c4a0201')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=DUMP)
    ap.add_argument('--lenoff', type=int, default=24)
    ap.add_argument('--dataoff', type=int, default=32)
    ap.add_argument('--top', type=int, default=12)
    a = ap.parse_args()
    fs = sorted(glob.glob(os.path.join(a.dir, '*.bin')))
    cal = 0
    cands = collections.Counter()
    for f in fs:
        b = open(f, 'rb').read()
        # 1) 校准：找 byte[5] 数组，其数据正好是已知的 Header_64
        for m in re.finditer(re.escape(HDR64), b):
            i = m.start()
            if i < a.dataoff or i + 5 > len(b):
                continue
            if int.from_bytes(b[i - a.lenoff:i - a.lenoff + 4], 'little') == 5:
                cal += 1
                if cal <= 3:
                    print('校准命中 %s @0x%x  对象头=%s'
                          % (os.path.basename(f)[-26:], i - a.dataoff,
                             b[i - a.dataoff:i].hex(' ')))
        # 2) 用同一偏移捞所有 byte[19]
        pat = struct.pack('<I', 19) + b'\x00\x00\x00\x00'
        j = b.find(pat)
        while j >= 0:
            obj = j - (a.lenoff - 4) if False else j - (a.lenoff - 4)
            d = b[j + 8:j + 8 + 19]        # max_length 之后 4 字节 pad + 数据
            if len(d) == 19:
                # 粗筛：密钥不该是全 0 / 全 ff / 大段可打印文本
                nz = sum(1 for c in d if c)
                if 6 <= nz <= 19 and not re.fullmatch(rb'[\x20-\x7e]+', d):
                    cands[d] += 1
            j = b.find(pat, j + 1)
    print('\n=== 校准（已知 Header_64 的 byte[5] 数组，偏移 +24/+32）：%d 处 ===' % cal)
    if cal == 0:
        print('校准失败 -> 数组对象头偏移假设不成立，**不得**采信下面的任何候选。')
        print('可试：--lenoff/--dataoff 组合（16/24、20/28、24/32、28/36）')
        return 1
    print('校准通过 -> 下面的 byte[19] 候选是在**已验证的布局**上取的。')
    print('\n=== byte[19] 候选（按出现次数）top %d ===' % a.top)
    for d, c in cands.most_common(a.top):
        print('   x%-6d %s' % (c, d.hex(' ')))
    print('\n（候选仍需用"能否解出可读明文"来终判，这里只负责把范围从 2.3GB 收到几十条。）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
