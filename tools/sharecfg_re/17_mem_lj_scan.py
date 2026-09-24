#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从内存快照里提取 LuaJIT 字节码，按 chunk 名归组，倒出常量池字符串。

为什么走这条路（2026-09-24 实测）：`16_mem_hunt.py` 全量拉了 1958.5MB 匿名内存，
`\x1bLJ`（LuaJIT 字节码魔数）在两个区域里各出现 5153 / 6838 次，旁边就是
`WorldShipRepairCommand.lua`、`W1138.lua`、`assets/luabuilds/android/normal/sharecfg/ship_skin_words.lua.bytes`
这类名字。→ **配置解析器的字节码已经在内存里是解密后的形态**，不必先破解 `scripts64` 容器。

⚠️ 本脚本刻意**不依赖**"完整反编译 LuaJIT 字节码"（那是另一件大事）。它只做两件稳的事：
  1) 按 `\x1bLJ` 切 blob，抓 blob 里的 **chunk 名**（LuaJIT 把源文件名存成以 `@` 开头的 GCstr，
     如 `=@assets/luabuilds/.../ship_skin_words.lua`）——用它定位"到底是哪个模块"；
  2) 抓 blob 内的**可打印 ASCII 串**（本轮只用宽松正则，不声称解析了 GCstr 结构），
     常量池里的密钥、`startPos/size` 用法、`bxor/string.char` 之类调用都会以字符串常量出现。
判据：只有在**同一条字节码 blob 内**同时看到目标 chunk 名与可疑常量才算线索；
跨 blob 拼出来的"发现"一律标为未证实。名字归属按"该 blob 里第一个 `@...lua`"判定，
一个 blob 含多个模块时会错配 —— 所以本脚本的输出只用于**缩小范围**，不作为结论。

用法:
  py -3 tools/sharecfg_re/17_mem_lj_scan.py                     # 全量归组 + 摘要
  py -3 tools/sharecfg_re/17_mem_lj_scan.py --grep sharecfg     # 只看名字含 sharecfg 的模块
  py -3 tools/sharecfg_re/17_mem_lj_scan.py --dump <序号>        # 打印某模块的全部常量
"""
import argparse, collections, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, '.diag', 'sharecfg_re', 'memdump')
MAGIC = b'\x1bLJ'
# ⚠️ 实测修正（本轮第一版在这里判成"0 个模块"，是脚本的错不是内存的错）：
#    chunk 名在内存里是**裸路径** `assets/luabuilds/android/normal/gamecfg/buff/buff_106040.lua`，
#    不带 LuaJIT 源码名惯有的 `=@` 前缀。前缀必须做成可选，否则正则全部落空。
NAME_RE = re.compile(rb'(?:=@|@|=\?)?[\w/.\-]{2,140}\.lua')
STR_RE = re.compile(rb'[\x20-\x7e]{5,}')
SUSPECT = re.compile(r'xor|bxor|bor|band|bnot|char|byte\(|sub\(|key|secret|md5|sha|'
                     r'startPos|start_pos|size|Header|Footer|sharecfg|confData|\.bytes',
                     re.I)


def blobs(b):
    """按 \x1bLJ 头切 blob：以相邻头间距为界，单 blob 最多 64KB（保守，够做归组与常量提取）。"""
    pos = [m.start() for m in re.finditer(re.escape(MAGIC), b)]
    for k, p in enumerate(pos):
        nxt = pos[k + 1] if k + 1 < len(pos) else p + 8192
        yield p, b[p:min(nxt, p + 65536, len(b))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--grep', default='')
    ap.add_argument('--dump', type=int, default=-1)
    ap.add_argument('--dir', default=OUT)
    a = ap.parse_args()
    fs = sorted(f for f in os.listdir(a.dir) if f.endswith('.bin'))
    if not fs:
        print('目录里没有 .bin，先跑 16_mem_hunt.py dump')
        return 1
    print('%d 个快照文件' % len(fs))
    mods = {}
    for f in fs:
        b = open(os.path.join(a.dir, f), 'rb').read()
        n = b.count(MAGIC)
        if not n:
            continue
        for p, seg in blobs(b):
            names = [m.group().decode('ascii', 'replace') for m in NAME_RE.finditer(seg[:8192])]
            if not names:
                continue
            nm = names[0].lstrip('=').lstrip('@')
            st = [m.group().decode('ascii', 'replace') for m in STR_RE.finditer(seg[:8192])]
            sus = [s for s in st if SUSPECT.search(s)]
            e = mods.setdefault(nm, {'count': 0, 'sus': collections.Counter(),
                                     'files': collections.Counter(), 'strs': set()})
            e['count'] += 1
            e['files'][f] += 1
            for s in sus:
                e['sus'][s] += 1
            e['strs'].update(s for s in st if len(s) > 6)
    print('归组出 %d 种带 chunk 名的字节码\n' % len(mods))
    rows = sorted(mods.items(), key=lambda kv: -kv[1]['count'])
    if a.grep:
        rows = [(k, v) for k, v in rows if re.search(a.grep, k, re.I)]
        print('--grep %r 命中 %d 个模块' % (a.grep, len(rows)))
    for i, (k, v) in enumerate(rows[:40]):
        print('  %-3d %-62s 出现%-5d 可疑常量%-4d' % (i, k[:62], v['count'], len(v['sus'])))
    if a.dump >= 0 and a.dump < len(rows):
        k, v = rows[a.dump]
        print('\n=== 模块 %s 的可疑常量（按次数）===' % k)
        for s, c in v['sus'].most_common(80):
            print('  %-4d %s' % (c, s[:160]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
