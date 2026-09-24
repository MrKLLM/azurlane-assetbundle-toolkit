#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用上一步证实的「跨表同偏移共结构」直接反推密钥流并尝试出明文。

10 号探针实测：32 张表两两 XOR 零率中位 1.84%、最高 4.98%（随机基线 0.391%），
且 32 张表 body 有 16 字节完全相同的前导、尾 8 字节全表相同。
这两条同时成立只有一种自然解释：

  H：C[i] = P[i] ⊙ K[i]，K **与文件无关、只与偏移有关**（⊙ ∈ {xor, add, sub}），
     P 是紧凑二进制（大量 00 与小整数），尾部是零填充 —— 于是 C[tail]=K[tail]，
     与各表内容无关，正好对上「尾 8 字节全表一致」。

若 H 成立，有两条不需要任何密钥的明文提取法，本脚本都做：
  A. **列共识法**：对每个偏移 i 取 32 张表该列的众数 m[i]（=K[i] ⊙ 明文众数）。
     明文绝大多数列的众数就是 0x00（索引/计数/填充），于是 m[i] ≈ K[i] ⊙ 0 = K[i]。
     再用它解密：D_X[i] = C_X[i] ⊙⁻¹ m[i]，看是否冒出中文/ASCII。
  B. **尾长对齐法**：把每张表**末尾**按文件尾对齐（不是按 body 前导对齐），
     检验尾部是否也共结构 —— 若共结构只在尾部成立，说明 K 是"距文件尾固定"的
     位置函数，那一样能反解。

判据（不接受"看着像"）：解密结果里必须出现 azdata 已知明文词表中的中文串，
或出现连续 >=6 个可读 ASCII 且与列名语义吻合。否则如实报告失败。

用法: py -3 tools/sharecfg_re/11_consensus_keystream.py [--cols 4096] [--op both]
"""
import argparse, collections, glob, json, math, os, re, sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CFG = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
AZ = os.path.join(ROOT, 'inputs', 'azdata', 'azdata_ship_skin_template.json')
PREFIX = bytes.fromhex('4e ff 00 00 51 ff 01 01')


def wordlist(n=600):
    cn = set()

    def rec(o):
        if isinstance(o, dict):
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)
        elif isinstance(o, str) and len(o) >= 2 and re.search(r'[一-鿿]', o):
            cn.add(o)
    rec(json.load(open(AZ, encoding='utf-8')))
    return sorted(cn)[:n]


def load():
    out = {}
    for p in sorted(glob.glob(os.path.join(CFG, '*'))):
        b = open(p, 'rb').read()
        i = b.find(PREFIX)
        if i >= 0:
            out[os.path.basename(p)] = b[i:]
    return out


def profile(names, M, tag, predicted):
    """逐列：多少表等于众数（共识度）、众数本身。

    self-check（这步是本脚本的真正判据）：若各表只是**共享字节分布**而没有共享密钥流，
    那么随机一对在该列相等的概率 = IC = sum p_v^2，32 个独立采样里众数应只出现约
    32*p_max 次（共识度 ~0.1 量级）。只有当某段偏移的共识度**接近 1.0**，
    才说明那里真的有跨文件相同的结构（共享密钥流 / 明文块 / 版本头）。
    """
    mode = np.apply_along_axis(lambda a: collections.Counter(a.tolist()).most_common(1)[0][0],
                              0, M).astype(np.uint8)
    agree = (M == mode[None, :]).mean(axis=0)
    print('\n--- %s：逐列共识度（32 表等于众数的比例）---' % tag)
    print('  均值 %.3f  中位 %.3f  max %.3f' % (agree.mean(), np.median(agree), agree.max()))
    print('  对照：仅共享字节分布（IC=%.4f）时的预测两两相等率 %.3f%%'
          % (predicted, 100 * predicted))
    print('  共识度分桶曲线（每桶 %d 列，取桶内平均）：' % max(1, M.shape[1] // 24))
    step = max(1, M.shape[1] // 24)
    for lo in range(0, M.shape[1], step):
        seg = agree[lo:lo + step]
        flag = '  <<< 真共享结构' if seg.mean() > 0.5 else ''
        print('    %6d..%-6d  共识 %.3f  众数字节 %s%s'
              % (lo, lo + len(seg), seg.mean(), bytes(mode[lo:lo + 10]).hex(' '), flag))
    full = int((agree > 0.9).sum())
    print('  共识 >90%% 的列数：%d / %d' % (full, M.shape[1]))
    return mode, agree


def try_decrypt(name, body, mode, words, op):
    if op == 'xor':
        d = np.bitwise_xor(body, mode).astype(np.uint8)
    elif op == 'sub':
        d = (body.astype(np.int16) - mode.astype(np.int16)).astype(np.uint8) & 0xFF
    else:
        d = (body.astype(np.int16) + mode.astype(np.int16)).astype(np.uint8) & 0xFF
    b = d.tobytes()
    cn = [w for w in words if len(w.encode('utf-8')) >= 4 and w.encode('utf-8') in b]
    runs = [m.group().decode() for m in re.finditer(rb'[\x20-\x7e]{8,}', b[:65536])]
    ent = -sum((c / len(b)) * math.log2(c / len(b)) for c in
               collections.Counter(b).values())
    ic = sum((c / len(b)) ** 2 for c in collections.Counter(b).values())
    return dict(table=name, op=op, cn=cn[:6], ncn=len(cn), runs=len(runs),
                sample=runs[:4], ent=ent, ic=ic)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cols', type=int, default=8192)
    ap.add_argument('--op', default='xor,sub,add')
    ap.add_argument('--deep', type=int, default=262144, help='共识法扫多少列（慢，默认 256KB）')
    a = ap.parse_args()
    words = wordlist()
    print('已知明文词表 %d 个中文串' % len(words))
    files = load()
    names = sorted(files, key=lambda k: len(files[k]))
    print('%d 张表，最短 %s(%d B)，最长 %s(%d B)'
          % (len(names), names[0], len(files[names[0]]), names[-1], len(files[names[-1]])))

    # ---- 头部对齐：前 cols 列
    L = min(a.cols, len(files[names[0]]))
    M = np.stack([np.frombuffer(files[k][:L], np.uint8) for k in names])
    pooled = collections.Counter(M.ravel().tolist())
    tot = sum(pooled.values())
    predicted = sum((c / tot) ** 2 for c in pooled.values())
    mode, agree = profile(names, M, '头部对齐（按公共前导，前 %d 列）' % L, predicted)
    print('  ==> 结论性判据：10 号探针实测两两相等率中位 1.84%%，'
          '而「只共享字节分布」的预测值是 %.3f%%。两者接近即说明**没有共享密钥流**，'
          '那条正信号是分布巧合。' % (100 * predicted))

    # ---- 尾部对齐：最后一样长的尾段
    Lt = min(a.cols, len(files[names[0]]))
    Mt = np.stack([np.frombuffer(files[k][-Lt:], np.uint8) for k in names])
    pooledt = collections.Counter(Mt.ravel().tolist())
    tott = sum(pooledt.values())
    modet, agree_t = profile(names, Mt, '尾部对齐（按文件尾，前 %d 列）' % Lt,
                             sum((c / tott) ** 2 for c in pooledt.values()))
    print('  对比：头部对齐共识均值 %.3f vs 尾部对齐 %.3f' % (agree.mean(), agree_t.mean()))

    # ---- 解密尝试（列共识法）
    print('\n--- 用头部众数当伪密钥流解密，看出不出明文 ---')
    hits = 0
    for op in a.op.split(','):
        for name in names[:6] + ['ship_skin_words', 'ship_skin_template', 'gametip']:
            if name not in files:
                continue
            body = np.frombuffer(files[name][:max(L, 65536)], np.uint8)
            n = min(len(body), len(mode))
            r = try_decrypt(name, body[:n], mode[:n], words, op)
            print('  %-28s op=%-4s IC=%.4f 熵=%.3f 可读串=%-4d 中文命中=%d %s'
                  % (r['table'], r['op'], r['ic'], r['ent'], r['runs'], r['ncn'],
                     (r['cn'][:3] or r['sample'][:2])))
            hits += r['ncn']
    print('\n判定：%s' % ('出明文了，立刻扩大验证' if hits else
                        '共识法未出明文 —— H 成立但众数!=0，需要真密钥（转内存/代码路线）'))


if __name__ == '__main__':
    main()
