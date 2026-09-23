#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析 global-metadata.dat 头，自检偏移量自洽性，并 dump 游戏自身的字符串字面量。

用法:
  py -3 tools/sharecfg_re/01_parse_metadata.py

无条件把 stringLiteral 写到 .diag/sharecfg_re/strings.txt（该目录在 gitignore，大件中间产物不入库）。

自检目的（README「推进路线」第 2 步）：
  metadata version=31 比常见的 24–29 高，要判断它是「新 Unity 的正常版本号」还是「被改过头的头」。
  判据：所有 (offset,count) 对都应满足 offset+count<=filesize、offset 对齐、count>0，
  且 stringLiteralData 区可打印字符占比高。全部自洽 = 正常版本；乱掉 = 头被改过，得手写解析器。
"""
import os, struct, sys, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MD = os.path.join(ROOT, 'files', 'il2cpp', 'Metadata', 'global-metadata.dat')
OUT = os.path.join(ROOT, '.diag', 'sharecfg_re', 'strings.txt')
MAGIC = 0xFAB11BAF

# Il2CppGlobalMetadataHeader 的 (offset,count) 字段对，v24–v29 及以后的顺序（前 4 对稳定）
PAIRS = [
    'stringLiteral', 'stringLiteralData', 'string', 'events', 'properties',
    'methods', 'parameterDefaultValues', 'fieldDefaultValues',
    'fieldAndParameterDefaultValueData', 'fieldMarshaledSizes', 'parameters',
    'fields', 'genericParameters', 'genericParameterConstraints',
    'genericContainers', 'nestedTypes', 'interfaces', 'vtableMethods',
    'interfaceOffsets', 'typeDefinitions',
]


def main():
    data = open(MD, 'rb').read()
    size = len(data)
    magic, ver = struct.unpack_from('<II', data, 0)
    print('size %d  magic 0x%08X (%s)  version %d' % (
        size, magic, 'OK' if magic == MAGIC else '!! 不符', ver))
    if magic != MAGIC:
        print('魔数不对，头可能被改过；停止。')
        return 2

    pairs = []
    for i, name in enumerate(PAIRS):
        off, cnt = struct.unpack_from('<ii', data, 8 + 8 * i)
        pairs.append((name, off, cnt))

    print('\n%-38s %12s %12s  %s' % ('field', 'offset', 'count', '自检'))
    bad = 0
    for name, off, cnt in pairs:
        ok = 0 <= off < size and cnt >= 0 and off + cnt <= size and (cnt > 0 or off == 0)
        if not ok:
            bad += 1
        print('%-38s %12d %12d  %s' % (name, off, cnt, 'ok' if ok else '!! 越界/反常'))
    print('\n异常字段数: %d / %d' % (bad, len(pairs)))
    print('判定: %s' % ('偏移全部自洽 → 是正常的高版本头，走标准 dumper 分支'
                      if bad == 0 else '头被改过或版本布局不同 → 必须手写解析器'))

    sl_off, sl_cnt = pairs[0][1], pairs[0][2]
    sd_off, sd_cnt = pairs[1][1], pairs[1][2]
    if bad == 0 and sd_cnt > 0:
        blob = data[sd_off:sd_off + sd_cnt]
        printable = sum(1 for b in blob if 32 <= b < 127 or b in (9, 10, 13) or b >= 0x80) / len(blob)
        print('\nstringLiteralData: %d 字节，可打印占比 %.3f' % (sd_cnt, printable))
        lits = []
        for rec in range(0, sl_cnt // 8):
            a, b = struct.unpack_from('<ii', data, sl_off + 8 * rec)
            # (length,dataIndex) 与 (dataIndex,length) 两种布局都试，取自洽的那种
            for ln, ix in ((a, b), (b, a)):
                if 0 <= ix and ln > 0 and ix + ln <= sd_cnt:
                    lits.append(blob[ix:ix + ln].decode('utf-8', 'replace'))
                    break
        print('解析出字面量 %d 条' % len(lits))
        kws = ('key', 'Key', 'secret', 'Secret', 'crypt', 'Crypt', 'xor', 'Xor',
               'decode', 'Decode', 'encrypt', 'Encrypt', 'salt', 'Salt', 'sharecfg', 'words')
        hit = [s for s in lits if any(k in s for k in kws)]
        print('含密钥/解密关键字的字面量 %d 条，前 30 条：' % len(hit))
        for s in hit[:30]:
            print('   ', s[:120])
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lits))
        print('\n全部字面量已写出: %s（%d 条）' % (OUT, len(lits)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
