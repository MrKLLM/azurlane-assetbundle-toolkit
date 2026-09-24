#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""已知明文探针：sharecfgdata 到底是"加密"还是"自定义二进制格式"？

昨天（09-23）的结论是「有真实密钥流的加密，密钥不在密文里」，但它的所有检验都是
**统计式**的（IC / 熵 / 位置函数变换后看中文密度），**没有一次用真实已知明文去撞**。
本脚本用 `inputs/azdata/azdata_ship_skin_template.json`（社区 dump，381 版）里
逐字提取的字符串去撞 32 张表，三种编码各来一遍，并顺手做字节分布与 ASCII 串体检。

判据（写死，不接受"看起来像"）：
  * 若任一表里命中 >=3 个来自 azdata 的不同中文串   -> 明文可见，问题只是**格式**，不需要密钥
  * 若 0 命中，但表里有成片的可读 ASCII 列名/字段名 -> 头部明文 + 载荷另说，可继续走格式逆向
  * 若 0 命中且无任何可读 ASCII                     -> "加密"前提成立，回到读密钥那条线

用法: py -3 tools/sharecfg_re/09_plaintext_probe.py [--min-len 2] [--top 25]
"""
import argparse, collections, glob, json, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CFG = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
AZ = os.path.join(ROOT, 'inputs', 'azdata', 'azdata_ship_skin_template.json')


def azdata_strings(min_len):
    """从已知明文基准里抽出一批中文串 + 一批 ASCII 键名，作为撞库词表。"""
    cn, en = set(), set()
    walk = json.load(open(AZ, encoding='utf-8'))

    def rec(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(k, str) and len(k) >= 3:
                    en.add(k)
                rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)
        elif isinstance(o, str):
            if len(o) >= min_len and re.search(r'[一-鿿]', o):
                cn.add(o)
            elif len(o) >= 4 and re.fullmatch(r'[A-Za-z_][\w\.]*', o):
                en.add(o)
        elif isinstance(o, bool) or o is None:
            pass
    rec(walk)
    return sorted(cn), sorted(en)


def variants(s):
    out = [s.encode('utf-8'), s.encode('utf-16-le'), s.encode('gbk', 'ignore')]
    return [v for v in out if v]


def ascii_runs(b, minlen=5):
    """粗版 strings：返回可打印 ASCII 连续段。"""
    return [m.group().decode('ascii') for m in
            re.finditer(rb'[\x20-\x7e]{%d,}' % minlen, b)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min-len', type=int, default=2)
    ap.add_argument('--top', type=int, default=25)
    ap.add_argument('--only', help='只查某一张表')
    a = ap.parse_args()

    cn, en = azdata_strings(a.min_len)
    print('azdata 已知明文词表：中文串 %d 个（取前 %d 个入库撞库）、ASCII 串 %d 个'
          % (len(cn), min(len(cn), 400), len(en)))
    probe_cn = cn[:400]
    files = sorted(glob.glob(os.path.join(CFG, '*')))
    if a.only:
        files = [f for f in files if a.only in os.path.basename(f)]

    verdict_total = collections.Counter()
    for p in files:
        name = os.path.basename(p)
        b = open(p, 'rb').read()
        h = collections.Counter(b)
        n = len(b)
        ic = sum((c / n) ** 2 for c in h.values())
        ent = -sum((c / n) * __import__('math').log2(c / n) for c in h.values())
        top = h.most_common(a.top)
        cn_hits = [(s, enc, b.find(v)) for s in probe_cn
                   for enc, v in (('utf8', s.encode('utf-8')),
                                  ('u16', s.encode('utf-16-le')),
                                  ('gbk', s.encode('gbk', 'ignore')))
                   if len(v) >= 2 * max(1, len(s)) and v in b]
        en_hits = sorted({s for s in en if s.encode('utf-8') in b})
        runs = ascii_runs(b)
        runs_total = sum(len(r) for r in runs)
        verdict_total['cn' if cn_hits else 'nocn'] += 1
        print('\n=== %s  size=%d  IC=%.4f  熵=%.3f  distinct=%d' % (name, n, ic, ent, len(h)))
        print('    高频字节: ' + ' '.join('%02x:%.3f' % (v, c / n) for v, c in top[:12]))
        print('    中文明文命中 %d 处 %s' % (len(cn_hits), cn_hits[:6]))
        print('    ASCII 键名命中 %d: %s' % (len(en_hits), en_hits[:12]))
        print('    可打印串 %d 段/共 %d 字节（占 %.4f%%） 样例: %s'
              % (len(runs), runs_total, 100.0 * runs_total / n,
                 ['%s' % r[:24] for r in sorted(runs, key=len, reverse=True)[:6]]))
    print('\n判定：%d/%d 张表含已知中文明文' % (verdict_total['cn'], len(files)))


if __name__ == '__main__':
    main()
