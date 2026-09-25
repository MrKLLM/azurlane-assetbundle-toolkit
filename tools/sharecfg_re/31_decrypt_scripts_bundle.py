#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 scripts64/scripts32 按 www() Phase C 的 ECB 全量解出，并试 UnityPy 能否打开。

模型（30 号已用 A1~A5 在真实文件上判死的部分）：
  L      = BE32(buf[-4:])                                   （scripts64 → 6517）
  ALEN   = filesize - 4 - L      = www() 返回缓冲长度        （AB 自报 fileSize 与它相等 = A3）
  out[8j .. 8j+7] = XXTEA2(block2, int[19] key)              j = 0.. while 8j < ALEN-8
  尾部不足一块的字节按原样搬（机器码里是一条拷贝循环）。

n=2 时每步 MX 的两个操作数**恒等**（y==z），所以整个反轮可压成 4 步定长序列，
用 numpy 向量化跑 490 万个块；同时**逐块与 29/30 号里的标量实现对比**，
不一致就 exit 3 —— 向量化很容易写错，不对齐就不许出结论。

用法: py -3 tools/sharecfg_re/31_decrypt_scripts_bundle.py [scripts64 ...]
产物: .diag/sharecfg_re/<name>.ab   （仅诊断，.diag 已 gitignore）
"""
import os, struct, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'sharecfg_re'))
MD = os.path.join(ROOT, 'files', 'il2cpp', 'Metadata', 'global-metadata.dat')
AB = os.path.join(ROOT, 'files', 'AssetBundles')
DI = os.path.join(ROOT, '.diag', 'sharecfg_re')
M = 0xFFFFFFFF
DELTA = 0xF90042FB
SUM0 = 0x0DFF7A0A
S1 = (SUM0 + DELTA) & M

import importlib
t30 = importlib.import_module('30_www_endtoend_reproduce')   # 复用已判死的标量实现


def key_windows():
    """e = (sum>>2)&3；n=2 时 p=1 用 key[1^e]，p=0 用 key[e]。"""
    out = []
    for s in (SUM0, S1):
        e = (s >> 2) & 3
        out.append((1 ^ e, e))
    return out          # [(idx_p1, idx_p0) 用于 round0, 同样用于 round1]


def decrypt_np(buf, alen, key):
    import numpy as np
    nblk = (alen - 8) // 8 + 1
    src = np.frombuffer(buf[:nblk * 8], dtype='<u4')
    a, b = src[0::2].copy(), src[1::2].copy()
    (k01, k00), (k11, k10) = key_windows()
    ks = (key[k01], key[k00], key[k11], key[k10])
    ss = (np.uint32(SUM0), np.uint32(SUM0), np.uint32(S1), np.uint32(S1))

    def mx(x, s, k):
        g1 = ((x << 2).astype(np.uint32) ^ (x >> np.uint32(5)))
        g2 = ((x << np.uint32(4)).astype(np.uint32) ^ (x >> np.uint32(3)))
        return ((x ^ np.uint32(k)) + (x ^ s)) ^ (g1 + g2)

    # 4 步定长序列（n=2 时每步 MX 的两个操作数恒等）：b-=mx(a), a-=mx(b), b-=mx(a), a-=mx(b)
    b = (b - mx(a, ss[0], ks[0])).astype(np.uint32)
    a = (a - mx(b, ss[1], ks[1])).astype(np.uint32)
    b = (b - mx(a, ss[2], ks[2])).astype(np.uint32)
    a = (a - mx(b, ss[3], ks[3])).astype(np.uint32)
    out = np.empty(nblk * 2, dtype=np.uint32)
    out[0::2] = a
    out[1::2] = b
    return out.tobytes(), nblk


def main():
    key = t30.load_key()
    names = sys.argv[1:] or ['scripts64', 'scripts32']
    os.makedirs(DI, exist_ok=True)
    for nm in names:
        raw = open(os.path.join(AB, nm), 'rb').read()
        n = len(raw)
        L = struct.unpack_from('>I', raw, n - 4)[0]
        alen = n - 4 - L
        if not (0 < L < n - 4):
            print('%s: L 不自洽，跳过' % nm); continue
        dec, nblk = decrypt_np(raw, alen, key)
        # ---- 与标量实现逐块对比（前 4096 块 + 随机 4096 块）
        import random
        rnd = random.Random(11)
        probe = list(range(min(4096, nblk))) + [rnd.randrange(nblk) for _ in range(4096)]
        bad = 0
        for j in probe:
            off = j * 8
            v = t30.block2(list(struct.unpack_from('<2I', raw, off)), key)
            if struct.pack('<2I', *v) != dec[off:off + 8]:
                bad += 1
        print('\n== %s  filesize=%d  L=%d  ALEN=%d  块数=%d' % (nm, n, L, alen, nblk))
        print('   向量化 vs 标量逐块对比 %d 块，不一致 %d %s'
              % (2 * len(probe) // 2, bad, '-> 判死，不出结论' if bad else '✓'))
        if bad:
            return 3
        head = dec[:48]
        print('   解出头部: %s  %r' % (head[:24].hex(' '), head[:24]))
        print('   AB 自报 fileSize（>i8 @30..37）= %d   模型 ALEN=%d  -> %s'
              % (struct.unpack_from('>q', dec, 30)[0], alen,
                 '一致' if struct.unpack_from('>q', dec, 30)[0] == alen else '不一致'))
        out = bytearray(dec)
        out[alen:] = raw[alen:alen + (n - alen)]          # 尾部不足一块原样搬
        path = os.path.join(DI, nm + '.ab')
        with open(path, 'wb') as fh:
            fh.write(bytes(out[:alen]))
        print('   写出 %s (%d B)' % (path, alen))
        try:
            import UnityPy
            try:
                env = UnityPy.Environment(path)
                objs = list(env.objects)
                print('   ✅ UnityPy 打开成功：%d 个对象，类型 = %s'
                      % (len(objs), sorted({str(t.type) for t in objs})[:8]))
                for t in objs[:5]:
                    print('      -', t.type, getattr(t.object, 'm_Name', ''))
            except Exception as e:
                print('   ❌ UnityPy 失败：%s: %s' % (type(e).__name__, str(e)[:200]))
        except ImportError:
            print('   没装 UnityPy')
    return 0


if __name__ == '__main__':
    sys.exit(main())
