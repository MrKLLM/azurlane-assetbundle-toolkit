#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""周期密钥攻击：利用「UTF-8 汉字的三字节结构对字节区间的约束」直接解出短周期密钥。

动机（14 号之后 15 号前的实测）：
  * lag 自相关在 3/6/9/12 上成倍频尖峰（ship_skin_words lag3=3.96x、gametip=7.11x），
    ship_skin_template 则在 4/8/12/16/32 上尖峰（4 字节记录）。
  * **周期 3 的密钥流正好让 12 号的 lag-1 差分签名失效**（同一条明文串内密钥每字节都在换），
    所以"差分全零"当时不能排除短周期 XOR —— 这是那个测试的真实盲区，本脚本来补。
  * 而 UTF-8 汉字给了极强的先验：三字节的字节**区间是确定的** ——
    首字节 E4..E9（CJK 主区），第 2/3 字节 80..BF。
    于是「每 3 列一组，各组独立挑一个 k 使该类落进期望区间的计数最大」= **可分优化**，
    256×3 次计数即可，不需要任何已知明文。

判据（写死，不接受"看着像"）：解出密钥后解密体必须
  (a) 合法 UTF-8 三连比例显著上升，且
  (b) 出现 azdata 已知明文词表里的真实中文串，或高频字（的一是不了我人这中大生）
只有 (a) 没有 (b) 算部分信号，要继续查；两者都无就如实报否证。

用法: py -3 tools/sharecfg_re/15_period_utf8_attack.py [--table ship_skin_words]
"""
import argparse, collections, json, math, os, re, sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CFG = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
AZ = os.path.join(ROOT, 'inputs', 'azdata', 'azdata_ship_skin_template.json')
LEAD = (0xE4, 0xE9)          # CJK 主区 UTF-8 首字节常见范围
CONT = (0x80, 0xBF)
COMMON = '的一是不了我人这中大生来时国对公和地也里可上发'


def in_range(a, lo, hi):
    return (a >= lo) & (a <= hi)


def best_key_for_class(bytes_in_class, lo, hi):
    """给一列（同残差类）字节，找使落进 [lo,hi] 计数最大的 k。返回 [(k, count), ...] 排序。"""
    cnt = np.zeros(256, dtype=np.int64)
    for k in range(256):
        cnt[k] = in_range((bytes_in_class ^ np.uint8(k)), lo, hi).sum()
    order = np.argsort(-cnt)
    return [(int(k), int(cnt[k])) for k in order[:4]]


def utf8_triple_rate(b):
    """整段里 E4-E9 + 80-BF + 80-BF 三连的占比（明文应 >=20%，随机 ~0.01%）。"""
    a = np.frombuffer(b, np.uint8)
    n = len(a) - 2
    if n < 1:
        return 0.0
    m = (in_range(a[:n], *LEAD) & in_range(a[1:n + 1], *CONT)
         & in_range(a[2:n + 2], *CONT))
    return float(m.sum()) / n


def words(n=200):
    out = []

    def rec(o):
        if isinstance(o, dict):
            [rec(v) for v in o.values()]
        elif isinstance(o, list):
            [rec(v) for v in o]
        elif isinstance(o, str) and len(o) >= 2 and re.search(r'[一-鿿]', o):
            out.append(o)
    rec(json.load(open(AZ, encoding='utf-8')))
    return sorted(set(out))[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--table', default='ship_skin_words')
    ap.add_argument('--skip', type=int, default=0, help='从第几字节开始（跳过头部）')
    ap.add_argument('--win', type=int, default=262144)
    a = ap.parse_args()
    b = open(os.path.join(CFG, a.table), 'rb').read()
    body = b[a.skip:a.skip + a.win]
    print('%s: 取 %d 字节（skip=%d）  原三元组合法率 %.5f'
          % (a.table, len(body), a.skip, utf8_triple_rate(body)))

    for p in (3, 4, 6, 2, 8, 12):
        # 每残差类：分别试「该类是首字节」与「该类是续字节」两种角色，取全局最优组合
        cands = []
        for r in range(p):
            col = np.frombuffer(body[r::p], np.uint8)
            lead = best_key_for_class(col, *LEAD)
            cont = best_key_for_class(col, *CONT)
            cands.append((r, lead[0], cont[0], lead[0][1] / len(col), cont[0][1] / len(col)))
        # 组装密钥：第 0 类当首字节，其余当续字节（p=3 正是 UTF-8 节奏）
        key = bytes([cands[0][1][0]] + [cands[r][2][0] for r in range(1, p)])
        dec = (np.frombuffer(body, np.uint8) ^ np.frombuffer((key * (len(body) // p + 1))[:len(body)], np.uint8)).tobytes()
        rate = utf8_triple_rate(dec)
        hits = [w for w in words() if len(w.encode('utf-8')) >= 6 and w.encode('utf-8') in dec]
        common = sum(dec.count(c.encode('utf-8')) for c in COMMON)
        print('  p=%-2d key=%s  三元组合法率 %.5f  已知明文命中 %d  常用字出现 %d'
              % (p, key.hex(' '), rate, len(hits), common))
        if hits:
            print('      命中例：%s' % hits[:6])
        # 再按「每类最优角色」穷举 2^p 角色组合里最好的一种（只在前 64KB 上评分，控成本）
        small = body[:65536]
        best = (rate, key, None)
        for mask in range(1 << p):
            kk = bytes(cands[r][1][0] if (mask >> r) & 1 else cands[r][2][0] for r in range(p))
            d2 = (np.frombuffer(small, np.uint8)
                  ^ np.frombuffer((kk * (len(small) // p + 1))[:len(small)], np.uint8)).tobytes()
            rr = utf8_triple_rate(d2)
            if rr > best[0]:
                best = (rr, kk, d2)
        if len(best) == 3:
            h2 = [w for w in words() if len(w.encode('utf-8')) >= 6 and w.encode('utf-8') in best[2]]
            print('      最优角色组合 key=%s 合法率 %.5f 已知明文命中 %d %s'
                  % (best[1].hex(' '), best[0], len(h2), h2[:4]))
    print('\n判据：只有「合法率大幅上升」且「真的撞出已知明文中文串」才算破口，'
          '否则本表按短周期 XOR 假设判否。')


if __name__ == '__main__':
    main()
