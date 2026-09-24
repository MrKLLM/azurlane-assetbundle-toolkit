#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""差分签名搜索：不猜密钥，直接把"任意段内恒定密钥"这一整类假设一次判掉。

原理：若密文 C[i] = P[i] ⊙ K[i]，且在某段内 K 恒为 k（⊙ ∈ {xor, +, -}），则
  xor:  C[i+t] ^ C[i+t+1] == P[t] ^ P[t+1]      （k 抵消，与 k 取值无关）
  add:  C[i+t+1] - C[i+t]  == P[t+1] - P[t] (mod 256)
于是「整条流的相邻差分」A 里，明文串的差分序列 DA 一定作为**连续子串**出现。
用 bytes.find 扫 A，**一次覆盖 256 个常量密钥**；更关键的是：
  * 与昨天/今天 256-key 全局扫的区别 —— 那条要求**整文件同一个 k**；
    差分法允许 **k 逐记录/逐字段变化**（每条行记录一个 k、每个字段一个 k 都能命中），
    这正是"明文索引 + 每行独立轻变换"这种实际设计的形状。
  * 若真答案是"整体 AES/CTR 流"（k 逐字节变），差分签名必然 0 命中，
    那就是干净的否证，可以直接放弃密文侧、转内存/代码取证。

额外两档变体：
  - 步长 2 差分（应对"2 字节一换的密钥" / UTF-16 双字节交织）
  - 反号/取反后再差分（应对 C = ~P ⊕ k）

用法: py -3 tools/sharecfg_re/12_diff_signature.py [--tables 3] [--maxpat 260]
"""
import argparse, collections, glob, json, math, os, re, sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CFG = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
AZDIR = os.path.join(ROOT, 'inputs', 'azdata')

# 没有基准的表也值得撞：中文台词里几乎必现的高频词
GUESS = ('指挥官', '您好', '欢迎', '我们', '出发', '战斗', '契约', '誓爱', '心跳',
         '日常', '今天', '喜欢', '谢谢', '碧蓝', '航线', '港区', '誓约', '胜利')


def words_from_json(path, n):
    out = []

    def rec(o):
        if isinstance(o, dict):
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)
        elif isinstance(o, str) and len(o) >= 2 and re.search(r'[一-鿿]', o):
            out.append(o)
    rec(json.load(open(path, encoding='utf-8')))
    return sorted(set(out))[:n]


def variants(s):
    v = []
    for enc in ('utf-8', 'utf-16-le', 'utf-16-be', 'gbk'):
        try:
            e = s.encode(enc)
        except Exception:
            continue
        if len(e) >= 4:
            v.append(e)
    return v


def diff_xor(b):
    a = np.frombuffer(b, np.uint8)
    return (a[1:] ^ a[:-1]).tobytes()


def diff_add(b):
    a = np.frombuffer(b, np.uint8).astype(np.int16)
    return ((a[1:] - a[:-1]) & 0xFF).astype(np.uint8).tobytes()


def diff_stride2(b):
    """lag-2 差分：密钥周期为 2（2 字节一换 / UTF-16 交织）时 K[i]^K[i+2]=0，仍然抵消。

    视图 = 偶数位序列的 lag-2 差分 ++ 奇数位序列的 lag-2 差分，命中位置要按 view2off 换算。
    """
    a = np.frombuffer(b, np.uint8)
    return b''.join((a[off + 2::2] ^ a[off:-2:2]).tobytes() for off in (0, 1))


def view2off(vn, i, nl):
    """差分视图里的下标 i -> 原文起始字节偏移（nl = 原文长度）。"""
    if vn != 's2':
        return i
    half = max(0, (nl + 1) // 2 - 2)
    return 2 * i if i < half else 2 * (i - half) + 1


def scan(C, pats):
    """在 C 的四种差分视图里找每个明文串的差分签名。

    不截断签名：长度 <4 的差分在 4MB 视图上是噪声级别，必须整条命中才算。
    （inv 视图被删掉了：~P 的 XOR 差分与 P 完全相同，只有 SUB 方向才不同 → 用 sub 视图。）
    """
    a = np.frombuffer(C, np.uint8).astype(np.int16)
    views = {
        'xor': diff_xor(C),
        'add': ((a[1:] - a[:-1]) & 0xFF).astype(np.uint8).tobytes(),
        'sub': ((a[:-1] - a[1:]) & 0xFF).astype(np.uint8).tobytes(),
        's2': diff_stride2(C),
    }
    res = {}
    for vn, A in views.items():
        hits = []
        for p in pats:
            for enc, e in (('u8', p.encode('utf-8', 'ignore')),
                           ('16b', p.encode('utf-16-be', 'ignore')),
                           ('16l', p.encode('utf-16-le', 'ignore')),
                           ('gbk', p.encode('gbk', 'ignore'))):
                if len(e) < 6:
                    continue
                if vn == 'xor':
                    d = diff_xor(e)
                elif vn in ('add', 'sub'):
                    x = np.frombuffer(e, np.uint8).astype(np.int16)
                    d = (((x[1:] - x[:-1]) if vn == 'add' else (x[:-1] - x[1:]))
                         & 0xFF).astype(np.uint8).tobytes()
                else:                       # s2：隔一位异或，密钥 2 字节一换时也成立
                    x = np.frombuffer(e, np.uint8)
                    d = b''.join(bytes((x[o + 2::2] ^ x[o:-2:2])) for o in (0, 1))
                if len(d) < 4:
                    continue
                j = A.find(d)
                while j >= 0:
                    hits.append((p, enc, view2off(vn, j, len(C))))
                    j = A.find(d, j + 1)
        res[vn] = hits
        print('    %-4s 差分视图命中 %3d / %d 串   例 %s'
              % (vn, len(hits), len(pats), hits[:4]))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--maxpat', type=int, default=120)
    a = ap.parse_args()
    base = {'ship_skin_template': 'azdata_ship_skin_template.json',
            'ship_data_statistics': 'azdata_ship_data_statistics.json',
            'ship_data_template': 'azdata_ship_data_template.json'}
    pats = {t: words_from_json(os.path.join(AZDIR, az), a.maxpat) for t, az in base.items()}
    for tbl, az in base.items():
        p = os.path.join(CFG, tbl)
        if not os.path.exists(p):
            print('缺表 %s' % tbl)
            continue
        C = open(p, 'rb').read()
        print('\n=== %s  size=%d  已知明文串 %d 个（来自 %s）' % (tbl, len(C), len(pats[tbl]), az))
        r = scan(C, pats[tbl])
        tot = sum(len(v) for v in r.values())
        # 阴性对照：拿**别的表**的词串撞这张表，命中数应≈0，否则说明签名太短、判据不成立
        other = [w for t2, ws in pats.items() if t2 != tbl for w in ws[:40]]
        rc = scan(C, other)
        ctot = sum(len(v) for v in rc.values())
        print('  ==> 本表词表命中 %d ／ 阴性对照（别表词表）命中 %d —— %s' % (tot, ctot,
              '命中显著高于对照：存在段内恒定密钥，立刻按记录逐段解密钥'
              if tot > ctot * 3 + 5 else
              '与对照同量级 —— 载荷不是任何"段内恒定 xor/加减"变换（干净否证）'))
    # 没有基准的表：用高频台词猜测撞
    p = os.path.join(CFG, 'ship_skin_words')
    if os.path.exists(p):
        print('\n=== ship_skin_words  size=%d  （无基准，用中文台词高频词撞）' % os.path.getsize(p))
        scan(open(p, 'rb').read(), list(GUESS))


if __name__ == '__main__':
    main()
