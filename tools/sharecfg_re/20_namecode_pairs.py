#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反解 {namecode:NNN} -> 名字：按「同一行的模板串与已解析成品串在堆里相邻」这个物理线索配对。

已证事实（19 号）：内存里**同时**存在
    模板   {namecode:38}级轻巡洋舰——{namecode:306}
    成品   克利夫兰级轻巡洋舰——帕萨迪纳
所以占位符是运行时替换的，替换结果留在 RAM 里。但 19 号那 5 条成品与那条模板**不是同一行**，
不能据此断言 38=克利夫兰。

配对原理：同一行的模板串（来自配置表原文）与成品串（来自显示期拼接）通常在**同一区域相近地址**
被分配。于是：
  1. 先从全部模板里抽出「固定中段」mid（如 `级轻巡洋舰——`）——它是模板与成品的公共锚；
  2. 对每个模板命中点，在 ±WIN 字节内找同 mid 的成品串；
  3. **只有窗口内恰好一条成品**才记一次观测（多条则歧义，丢弃 —— 宁缺不滥）；
  4. 聚合：同一 (码 -> 名字) 被多少条独立观测支持；判据 = **>=3 条且无冲突**才写进映射表。

外部裁判：用 `Output/ship_meta.json` 递归收集全部字符串当"已知舰名/阵营名"集合，
对解出的名字做命中率校验；命中不了不否决（385 新内容本地可能没有），但会如实报比例。

用法: py -3 tools/sharecfg_re/20_namecode_pairs.py [--win 8192] [--min-obs 3]
"""
import argparse, collections, glob, json, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DUMP = os.path.join(ROOT, '.diag', 'sharecfg_re', 'memdump')
META = os.path.join(ROOT, 'Output', 'ship_meta.json')
TPL = re.compile(rb'\{namecode:(\d+)\}([^\x00{]{1,18}?)\{namecode:(\d+)\}')
NAMECH = rb'[\xe4-\xe9][\x80-\xbf]{2}|[\x20-\x7e]{1,3}'


def known_names():
    s = set()
    try:
        walk = json.load(open(META, encoding='utf-8'))
    except Exception as e:
        print('ship_meta.json 读不到（%s）：跳过外部裁判' % e)
        return s

    def rec(o):
        if isinstance(o, dict):
            [rec(v) for v in o.values()]
        elif isinstance(o, list):
            [rec(v) for v in o]
        elif isinstance(o, str) and 1 < len(o) <= 12 and re.fullmatch(r'[一-鿿·\w]+', o):
            s.add(o)
    rec(walk)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--win', type=int, default=8192)
    ap.add_argument('--min-obs', type=int, default=3)
    ap.add_argument('--dir', default=DUMP)
    a = ap.parse_args()
    KN = known_names()
    print('外部裁判集合：%d 个已知名字' % len(KN))
    fs = [f for f in sorted(os.listdir(a.dir)) if f.endswith('.bin')]
    obs = collections.defaultdict(collections.Counter)   # code -> Counter(name)
    n_tpl = n_pair = n_amb = 0
    for f in fs:
        b = open(os.path.join(a.dir, f), 'rb').read()
        if len(b) < 4096:
            continue
        tpls = list(TPL.finditer(b))
        if not tpls:
            continue
        n_tpl += len(tpls)
        # 先把本区域所有成品串按 mid 归好，避免每个模板都全文扫
        mids = {m.group(2) for m in tpls}
        res = []
        for mid in mids:
            try:
                pat = re.compile(b'(' + NAMECH + b'{1,10}?)' + re.escape(mid) + b'(' + NAMECH + b'{2,14})')
            except re.error:
                continue
            for m in pat.finditer(b):
                n1, n2 = m.group(1), m.group(2)
                if b'{' in n1 or b'{' in n2 or not n1 or not n2:
                    continue
                res.append((m.start(), mid, n1.decode('utf-8', 'replace'),
                            n2.decode('utf-8', 'replace')))
        if not res:
            continue
        for m in tpls:
            A, mid, B = int(m.group(1)), m.group(2), int(m.group(3))
            near = [r for r in res if r[1] == mid and abs(r[0] - m.start()) <= a.win]
            uniq = {(r[2], r[3]) for r in near}
            if len(uniq) == 1:
                (n1, n2) = next(iter(uniq))
                obs[A][n1] += 1
                obs[B][n2] += 1
                n_pair += 1
            elif len(uniq) > 1:
                n_amb += 1
    print('模板命中 %d 处；可配对观测 %d 条；歧义丢弃 %d 条' % (n_tpl, n_pair, n_amb))

    good, weak = {}, {}
    for code, cnt in obs.items():
        name, n = cnt.most_common(1)[0]
        tot = sum(cnt.values())
        conflict = len(cnt) > 1
        if n >= a.min_obs and not conflict:
            good[code] = (name, n, tot)
        elif n >= 2:
            weak[code] = (name, n, tot, dict(cnt))
    print('\n=== 达标映射（>= %d 条独立观测且无冲突）：%d 个码 ===' % (a.min_obs, len(good)))
    hit = sum(1 for c, (n, _, _) in good.items() if n in KN)
    for c in sorted(good)[:40]:
        n, k, t = good[c]
        print('   namecode %-6d -> %-14s 观测%-3d 已知表命中=%s' % (c, n, k, 'Y' if n in KN else '?'))
    print('   外部裁判命中率：%d / %d' % (hit, len(good)))
    print('\n=== 弱证据（有冲突或观测不足）：%d 个码 ===' % len(weak))
    for c in sorted(weak)[:15]:
        n, k, t, d = weak[c]
        print('   namecode %-6d 最优=%-12s %d/%d  全部候选=%s' % (c, n, k, t, d))
    out = os.path.join(ROOT, '.diag', 'sharecfg_re', 'namecode_map.tsv')
    with open(out, 'w', encoding='utf-8') as w:
        w.write('code\tname\tobs\ttotal\tin_ship_meta\n')
        for c in sorted(good):
            n, k, t = good[c]
            w.write('%d\t%s\t%d\t%d\t%s\n' % (c, n, k, t, 'Y' if n in KN else 'N'))
    print('\n映射表已写出：%s（达标 %d 条 / 弱证据 %d 条）' % (out, len(good), len(weak)))


if __name__ == '__main__':
    main()
