#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 29112 条游戏字符串字面量里按「像密钥/像算法名/像表名」的形态筛选。

输入 .diag/sharecfg_re/strings.txt（01_parse_metadata.py 产出）。
关注四种形态：
  ① 十六进制串（MD5=32 / SHA1=40 / SHA256=64 hex，AES key 16/24/32 字节=32/48/64 hex）
  ② Base64 疑似块（纯 [A-Za-z0-9+/=]，长度 12~88，自解码后是随机字节）
  ③ 高熵短串（8~40 字符，字符熵高、无空格、不像自然语言）
  ④ 表名/表路径（sharecfgdata、ship_skin_words 等 —— 用来确认配置加载入口的命名空间）

输出结论，不写文件。
"""
import os, re, sys, math, base64, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, '.diag', 'sharecfg_re', 'strings.txt')

HEX = re.compile(r'^[0-9A-Fa-f]{16,88}$')
B64 = re.compile(r'^[A-Za-z0-9+/]{12,88}={0,2}$')
IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_\-\. ]*$')


def entropy(s):
    n = len(s)
    return -sum(c / n * math.log2(c) for c in collections.Counter(s).values())


def looks_random_bytes(b):
    return len(set(b)) >= min(len(b) - 2, 12)


def main():
    lits = [ln.strip() for ln in open(SRC, encoding='utf-8')]
    lits = [s for s in lits if s]
    print('字面量 %d 条\n' % len(lits))

    print('=== ① 十六进制串（候选密钥/摘要）')
    hexs = [s for s in lits if HEX.match(s)]
    bylen = collections.Counter(len(s) for s in hexs)
    print('共 %d 条，长度分布 %s' % (len(hexs), sorted(bylen.items())))
    for s in sorted(set(hexs), key=len)[:40]:
        print('   len=%-3d %s' % (len(s), s[:88]))

    print('\n=== ② Base64 疑似块（自解码后是随机字节才算候选）')
    b64c = []
    for s in set(lits):
        if not B64.match(s) or HEX.match(s):
            continue
        try:
            raw = base64.b64decode(s + '=' * (-len(s) % 4), validate=True)
        except Exception:
            continue
        if 8 <= len(raw) <= 64 and looks_random_bytes(raw):
            b64c.append((s, raw))
    print('共 %d 条' % len(b64c))
    for s, raw in sorted(b64c, key=lambda x: -len(x[1]))[:30]:
        print('   %2dB  %-44s  hex=%s' % (len(raw), s[:44], raw.hex()[:48]))

    print('\n=== ③ 高熵短串（8~40 字符、无空格、不像自然语言）')
    cand = []
    for s in set(lits):
        if not (8 <= len(s) <= 40) or ' ' in s or not IDENT.match(s):
            continue
        if HEX.match(s) or B64.match(s):
            continue
        if entropy(s) >= 3.6:
            cand.append((entropy(s), s))
    cand.sort(reverse=True)
    print('共 %d 条，前 40 条：' % len(cand))
    for e, s in cand[:40]:
        print('   H=%.2f %s' % (e, s))

    print('\n=== ④ 配置加载相关的表名/路径（用来确认命名空间与入口）')
    keys = ('sharecfg', 'skin_words', 'words', 'CfgFile', 'CfgLoader', 'XorShift',
            'Xor', 'Decrypt', 'Decode', 'LoadCfg', 'JsonConvert', 'Deserialize')
    for k in keys:
        hit = sorted({s for s in lits if k in s})
        if hit:
            print('== %-14s %d 条:' % (k, len(hit)))
            for s in hit[:10]:
                print('     ', s[:110])
    return 0


if __name__ == '__main__':
    sys.exit(main())
