#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两项昨天没做过的密文结构检验：跨表共密钥流（many-time-pad）与组内重复块（ECB 特征）。

为什么值得做：昨天把所有检验都花在**单文件内部**（IC / 熵 / 位置函数 / 自同步），
但从没利用「我们手里有 32 张表」这个事实。而昨天自己的观测里藏着两条强线索：
  1. 32 张表 body 的**最长公共前缀 = 16 字节**（`4e ff 00 00 51 ff 01 01 …`）。
     若加密是「位置相关的全局密钥流」（无每文件 nonce），那不同表同位置的明文不同
     而密文前缀却相同 —— 除非前缀那段明文恰好相同。反之若同密钥流成立，
     **任意两表逐字节 XOR 就能把密钥流完全消掉**（C1^C2 = P1^P2），
     这是 classic many-time-pad，32 张表足够做逐列频率攻击。
  2. 若分组密码是 ECB（无 IV/链接），同文明确块 → 同密文块；表里同结构行极多，
     重复块应该藏不住。

判据（先定死，避免"看着像"）：
  * 两两 XOR 零率显著 > 1/256(=0.391%)  -> 共密钥流成立，继续逐列攻击
  * 逐列最优 key 的 IC 明显高于其余候选 -> 密钥流可分离，能出明文
  * 重复密文块数 > 0（16B 对齐）        -> ECB 类，直接可按块字典攻击
  * 以上全 0 -> 每文件独立密钥流/IV，密文侧到此为止，必须走取密钥那条线
"""
import collections, glob, os, sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CFG = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
PREFIX = bytes.fromhex('4e ff 00 00 51 ff 01 01')   # 昨天实测的 32 表公共 body 前导
CAP = 1 << 18                                       # 对齐比对最多取 256KB
MTP_COLS = 4096                                     # 逐列攻击只扫前 4096 列
PRINTABLE = np.array([c for c in range(256) if 32 <= c < 127], dtype=np.uint8)


def ic(bs):
    n = len(bs)
    if n < 2:
        return 0.0
    return sum((c / n) ** 2 for c in collections.Counter(bs).values())


def ic_np(mat):
    """mat: (rows, ) uint8 -> IC"""
    c = np.bincount(mat, minlength=256).astype(np.float64)
    n = c.sum()
    return float(((c / n) ** 2).sum()) if n else 0.0


def load_aligned():
    out = {}
    for p in sorted(glob.glob(os.path.join(CFG, '*'))):
        b = open(p, 'rb').read()
        i = b.find(PREFIX)
        name = os.path.basename(p)
        if i < 0:
            print('  跳过 %-30s（无公共前导，格式不同）' % name)
            continue
        out[name] = np.frombuffer(b[i:i + CAP], dtype=np.uint8)
    print('  对齐 body 的表：%d 张，每张 <=%d 字节' % (len(out), CAP))
    return out


def part_pad(files):
    print('\n=== 1) 跨表两两 XOR 零率（共密钥流判据；随机基线 0.391%）===')
    names = sorted(files, key=lambda k: len(files[k]))
    best = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = files[names[i]], files[names[j]]
            n = min(len(a), len(b), CAP)
            x = a[:n] ^ b[:n]
            best.append((float((x == 0).sum()) / n, names[i], names[j], n, ic_np(x)))
    best.sort(key=lambda t: -t[0])
    for z, n1, n2, n, _i in best[:8]:
        print('  零率 %.4f%%  %s ^ %s  (%d B)' % (100 * z, n1, n2, n))
    zs = [b[0] for b in best]
    print('  全部 %d 对：max %.4f%%  中位 %.4f%%  min %.4f%%'
          % (len(best), 100 * max(zs), 100 * sorted(zs)[len(zs) // 2], 100 * min(zs)))
    print('  判定：%s' % ('存在共密钥流' if max(zs) > 0.01 else
                        '无共密钥流（每文件独立密钥流/IV）——两时间垫这条路封死'))


def part_mtp(files):
    print('\n=== 2) many-time-pad 逐列 key 攻击（仅当第 1 步成立才有意义）===')
    names = sorted(files)
    L = min(min(len(files[k]) for k in names), MTP_COLS)
    M = np.stack([files[k][:L] for k in names])          # (nfiles, L)
    print('  矩阵 %s（行=表，列=body 内偏移），前 %d 列' % (M.shape, L))
    scores = np.zeros((256, L), dtype=np.int32)
    for k in range(256):
        scores[k] = np.isin(M ^ np.uint8(k), PRINTABLE).sum(axis=0)
    bestk = scores.argmax(axis=0)
    bestscore = scores.max(axis=0)
    mean_rand = L * 0 + (95.0 / 256) * M.shape[0]        # 随机 key 的期望可打印数
    confident = int((bestscore > mean_rand * 1.6).sum())
    print('  逐列最优 key 的可打印数：中位 %.1f  满列 %d/%d（随机期望 %.1f）'
          % (np.median(bestscore), confident, L, mean_rand))
    top = collections.Counter(bestk.tolist()).most_common(8)
    print('  最优 key 的分布（共密钥流应出现峰值）：', top)
    print('  判定：%s' % ('有可利用峰值，密钥流可分离' if confident > L * 0.15 else
                        '无峰值，密钥流逐列独立 -> 密文侧攻击到此为止'))


def part_ecb(files):
    print('\n=== 3) 组内重复块检测（ECB / 无 IV 判据）===')
    for blk in (8, 16, 32):
        tot_rep = 0
        worst = []
        for name, b in sorted(files.items()):
            n = len(b) // blk
            c = collections.Counter(b[i * blk:(i + 1) * blk].tobytes() for i in range(n))
            rep = sum(v - 1 for v in c.values() if v > 1)
            tot_rep += rep
            if rep:
                worst.append((rep, name, n))
        print('  块长 %2d：重复块总数 %d（%d 张表里 %d 张有重复）%s'
              % (blk, tot_rep, len(files), len(worst),
                 '  例：%s' % worst[:3] if worst else ''))
    print('  判定：0 重复 -> 非 ECB/无固定字典；有重复 -> 立刻可按块字典攻击')


def main():
    print('=== 0) 载入并按公共前导对齐 ===')
    files = load_aligned()
    if len(files) < 3:
        return
    part_pad(files)
    part_mtp(files)
    part_ecb(files)


if __name__ == '__main__':
    main()
