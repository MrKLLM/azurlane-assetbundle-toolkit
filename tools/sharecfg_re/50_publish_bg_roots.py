#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""50_publish_bg_roots.py — 把「背景词根 → 中文名」做成可重跑的确定性发布，不靠人猜拼音。

原理：`bg_*` 的词根就是活动/章节名的**拼音**（`canghongzhiyan` = 苍红之炎），
而 773 张只在 Lua 侧的配置表里有大量中文短名 ⇒ 对每条中文值算 `lazy_pinyin` 整值比对词根，
**只发布唯一命中**。多义（`yujin` 同时是「余烬」和「浴巾」）与零命中一律不发。

已试过并**否证**的第二条路（别再跑）：把词根当字段整值去表里反查同行中文名。
命中 12 组里只有 `port_*` 9 个各 1 张，且 `night`→「休息或其它」、`commander`→「装扮」、
`white`→「马里亚纳风云」都是错配 —— 收益 13 张、错误率高，判否。
英文/缩写词根（`star_level` / `project_tb` / `bsmre` / `worldcruise` / `underheaven`）
**没有任何自动路**：它们是内部英文标识，配置表里既不以整值出现、也不是拼音。
⇒ 剩下约 99 组只能人工写词典，或接外部维基。

用法:
  py -3 tools/sharecfg_re/50_publish_bg_roots.py            # 发布到 inputs/gamecfg/
  py -3 tools/sharecfg_re/50_publish_bg_roots.py --check     # 只算不写
前置: `.diag/sharecfg_re/lua_json/`（由 41_export_lua_tables.py 产出，773 张）
退出码：断言红即 1（红时不写文件）。
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

from pypinyin import lazy_pinyin

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
LUA = os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_json')
META = os.path.join(ROOT, 'Output', 'gallery_v2', 'bg_meta.json')
OUT = os.path.join(ROOT, 'inputs', 'gamecfg', 'bg_root_labels.json')

CJK_ONLY = re.compile(r'^[一-鿿]{2,12}$')
TAIL_NUM = re.compile(r'(v|ver)?\d+$')


def py_of(s):
    return ''.join(lazy_pinyin(s))


def chinese_names():
    """773 张表里所有「整值就是一个中文短名」的串 -> 出现处。"""
    idx = defaultdict(list)
    for f in sorted(os.listdir(LUA)):
        try:
            t = json.load(open(os.path.join(LUA, f), encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(t, dict):
            continue
        for rid, row in t.items():
            if not isinstance(row, dict):
                continue
            for k, v in row.items():
                if not isinstance(v, str):
                    continue
                v = v.strip()
                if not CJK_ONLY.match(v):
                    continue
                idx[py_of(v)].append({'t': f[:-5], 'id': rid, 'f': k, 'cn': v})
    return idx


def scene_roots():
    m = json.load(open(META, encoding='utf-8'))
    c = defaultdict(int)
    for i in m['items']:
        if i['group'] == 'scene' and i['root']:
            c[i['root']] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只算不写')
    a = ap.parse_args()
    if not os.path.isdir(LUA):
        print('[FAIL] 缺 %s —— 先跑 py -3 tools/sharecfg_re/41_export_lua_tables.py --all --yes' % LUA)
        return 2
    idx = chinese_names()
    roots = scene_roots()
    labels, ambiguous = {}, []
    for r, n in sorted(roots.items(), key=lambda kv: -kv[1]):
        key = TAIL_NUM.sub('', re.sub(r'[^a-z0-9]', '', r.lower()))
        rows = idx.get(key, [])
        cands = sorted({x['cn'] for x in rows})
        if len(cands) == 1:
            labels[r] = {'cn': cands[0], 'n': n,
                         'src': [{'t': x['t'], 'f': x['f'], 'id': x['id']} for x in rows[:3]]}
        elif len(cands) > 1:
            ambiguous.append({'root': r, 'n': n, 'cands': cands})

    print('词根 %d 个 / 唯一命中 %d 组（覆盖 %d 张）/ 多义不发 %d 组'
          % (len(roots), len(labels), sum(v['n'] for v in labels.values()), len(ambiguous)))
    for r, v in sorted(labels.items(), key=lambda kv: -kv[1]['n'])[:10]:
        print('  %-18s n=%3d  %s' % (r, v['n'], v['cn']))
    for x in ambiguous[:5]:
        print('  多义 %-14s n=%3d  %s' % (x['root'], x['n'], x['cands']))

    checks = [
        ('词根表非空', len(roots) > 100),
        ('每条发布项的 cn 的拼音整值 == 该词根（剥尾部数字/下划线后），不许是"沾边"匹配',
         all(py_of(v['cn']) == TAIL_NUM.sub('', re.sub(r'[^a-z0-9]', '', r.lower()))
             for r, v in labels.items())),
        ('每条发布项都带回指出处 (表/字段/行)',
         all(v['src'] and all(s.get('t') and s.get('f') and s.get('id') for s in v['src'])
             for v in labels.values())),
        ('多义组一条都没进发布集',
         not (set(labels) & {x['root'] for x in ambiguous})),
        ('命中数没跌破下限（配置表或词根算法退化时要报警，而不是静默发一张空表）',
         len(labels) >= 15),
    ]
    ok = True
    for desc, passed in checks:
        print('%s %s' % ('✓' if passed else '✗', desc))
        ok &= passed
    if not ok:
        print('\n闸门：红 —— 不写文件')
        return 1
    if a.check:
        print('\n闸门：绿（--check 未写文件）')
        return 0
    doc = {'schema': 1,
           'method': 'lazy_pinyin 整值匹配 773 张 lua 表的中文短名；只发布唯一命中',
           'source': '.diag/sharecfg_re/lua_json (tools/sharecfg_re/41_export_lua_tables.py)',
           'rejected_route': '词根作字段整值反查同行中文名：命中 12 组多为错配（night/commander/white），'
                             '判否，勿再跑',
           'ceiling': '英文/缩写词根（star_level/project_tb/bsmre/worldcruise 等）无自动路，'
                      '只能人工词典或接外部维基',
           'labels': labels, 'ambiguous': ambiguous}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print('\n[WRITE] %s（%d 组 / %.1f KB）'
          % (os.path.relpath(OUT, ROOT).replace('\\', '/'), len(labels), os.path.getsize(OUT) / 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
