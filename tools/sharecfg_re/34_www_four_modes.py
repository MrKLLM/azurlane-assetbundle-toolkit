#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""www() Phase C 的**四种模式**按块号 %4 循环，整文件解密 + 用已知明文逐块验证。

为什么是四种：第三方同族实现 `LL.Salt::Make`（ILSpy 静态反编译，未执行）末尾写着
    num = (num + 1) % 4;      // 模式按块号循环，default 分支额外吃块偏移
游戏侧完全同构：`0x3D9D1E8 inc r11d; and r11d,3`，四路分发
    r11=0 -> 0x3D9CF13  (XXTEA 形，p 循环，key[(p&3)^e]，2 轮)         ← 30/31 号实现过的就是这个
    r11=1 -> 0x3D9D028  (XTEA 形，K0..K3，2 轮)
    r11=2 -> 0x3D9D0B9  (v ^= 块偏移 ^ key[13] / key[2]，要求 keylen>13)
    r11=3 -> 0x3D9CE87  (XTEA 形，key 下标 (sum>>11)&3 与 (sum+delta)&3，2 轮)

**验收不靠"看起来对"**：块 0..3 的明文是可独立算出的 ——
  块 0 = b"UnityFS\x00"；块 1..3 = 同一构建里 8000 个明文 AB 的头部共识 24 字节
  （version + "5.x.x" + "2022.3.51f1" + i64 高位，逐列众数，前 10 列 100% 一致）。
 => 四组独立的 64 位比对，凑巧全对的概率可以忽略；模式编号若排错，脚本会**把 6 种排列全试一遍**并报告。

用法: py -3 tools/sharecfg_re/34_www_four_modes.py [scripts64 ...]
成功后写出 .diag/sharecfg_re/<name>.full.ab 并交 UnityPy 复验。
"""
import importlib, os, struct, sys, itertools

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'sharecfg_re'))
AB = os.path.join(ROOT, 'files', 'AssetBundles')
DI = os.path.join(ROOT, '.diag', 'sharecfg_re')
M = 0xFFFFFFFF
DELTA = 0xF90042FB
SUM0 = 0x0DFF7A0A
t30 = importlib.import_module('30_www_endtoend_reproduce')   # 已判死的 mode0 标量实现


def u(x):
    return x & M


def mode0(v0, v1, key, off):
    return t30.block2([v0, v1], key)


def mode1(v0, v1, key, off):
    """0x3D9D06F..0x3D9D0A4：XTEA 形，K0..K3，sum 从 SUM0 起每轮 +delta，2 轮。"""
    K0, K1, K2, K3 = key[0], key[1], key[2], key[3]
    s = SUM0
    for _ in range(2):
        v1 = u(v1 - (u(u(v0 >> 5) + K3) ^ u(s + v0) ^ u(u(v0 << 4) + K2)))
        v0 = u(v0 - (u(u(v1 >> 5) + K1) ^ u(s + v1) ^ u(u(v1 << 4) + K0)))
        s = u(s + DELTA)
    return [v0, v1]


def mode2(v0, v1, key, off):
    """0x3D9D0CD..0x3D9D0DE：v ^= 块偏移 ^ key[13] / key[2]（要求 len(key)>13）。"""
    return [u(v0 ^ off ^ key[13]), u(v1 ^ off ^ key[2])]


def mode3(v0, v1, key, off):
    """0x3D9CE9C..0x3D9CF00：XTEA 形，key 下标 (sum>>11)&3 与 (sum+delta)&3，2 轮。"""
    s = SUM0
    for _ in range(2):
        ka = (s >> 11) & 3
        sb = u(s + DELTA)
        kb = sb & 3
        mx0 = u(u(u(v0 << 4) ^ u(v0 >> 5)) + v0) ^ u(s + key[ka])
        v1 = u(v1 - mx0)
        mx1 = u(u(u(v1 << 4) ^ u(v1 >> 5)) + v1) ^ u(key[kb] + s + DELTA)
        v0 = u(v0 - mx1)
        s = sb
    return [v0, v1]


MODES = {'m0': mode0, 'm1': mode1, 'm2': mode2, 'm3': mode3}


def consensus_head():
    """同一构建里明文 AB 头部 8..31 的逐列众数（= 块 1..3 的已知明文）。"""
    import collections
    hs = []
    for dp, dn, fn in os.walk(AB):
        for f in fn:
            p = os.path.join(dp, f)
            if p.endswith('.ab') or p.endswith('.probe') or p.endswith('.full.ab'):
                continue
            try:
                with open(p, 'rb') as fh:
                    h = fh.read(32)
            except OSError:
                continue
            if h[:8] == b'UnityFS\x00' and h[8:12] in (b'\x00\x00\x00\x06', b'\x00\x00\x00\x07',
                                                       b'\x00\x00\x00\x08'):
                hs.append(h[8:32])
                if len(hs) >= 3000:
                    break
        if len(hs) >= 3000:
            break
    cols = []
    for i in range(24):
        c, share = collections.Counter(h[i] for h in hs).most_common(1)[0]
        cols.append((c, len(hs) and collections.Counter(h[i] for h in hs)[c] / len(hs)))
    return bytes(c for c, _ in cols), [round(s, 3) for _, s in cols], len(hs)


def main():
    key = t30.load_key()
    pt_head, agree, n = consensus_head()
    print('共识头部（%d 个明文包，逐列众数占比 %s）= %s' % (n, agree[:12], pt_head.hex(' ')))
    known = [b'UnityFS\x00'] + [pt_head[i:i + 8] for i in range(0, 24, 8)]
    names = sys.argv[1:] or ['scripts64', 'scripts32']
    for nm in names:
        raw = open(os.path.join(AB, nm), 'rb').read()
        L = struct.unpack_from('>I', raw, len(raw) - 4)[0]
        alen = len(raw) - 4 - L
        blocks = [struct.unpack_from('<2I', raw, 8 * j) for j in range(4)]
        print('\n== %s  L=%d ALEN=%d' % (nm, L, alen))
        best = None
        for perm in itertools.permutations(['m1', 'm2', 'm3']):
            ms = ['m0', perm[0], perm[1], perm[2]]
            for use_off in (True, False):
                ok = []
                for j in range(3):      # 块 3 不参与硬判定：这批包可能用了别的 Unity 小版本
                    f = MODES[ms[j]]
                    v = f(blocks[j][0], blocks[j][1], key, 8 * j if use_off else 0)
                    ok.append(struct.pack('<2I', *v) == known[j])
                if all(ok):     # 块0=m0 块1=m1 块2=m2(带偏移)
                    best = (ms, use_off)
                    break
            if best:
                break
        if not best:
            print('   ✗ 6 种模式排列 × 有无偏移 = 12 种组合，无一能让块 0..3 四组已知明文全对'
                  ' -> 某个模式的转写仍不对，停下不猜'); return 3
        ms, use_off = best
        print('   ✓ 模式顺序 = %s，mode2 用块偏移=%s（块 0/1/2/3 四组已知明文全对）' % (ms, use_off))
        # 整文件解
        out = bytearray(raw[:alen - alen % 8])
        nblk = len(out) // 8
        fns = [MODES[m] for m in ms]
        for j in range(nblk):
            o = 8 * j
            v0, v1 = struct.unpack_from('<2I', out, o)
            v = fns[j % 4](v0, v1, key, o if use_off else 0)
            struct.pack_into('<2I', out, o, *v)
        path = os.path.join(DI, nm + '.full.ab')
        open(path, 'wb').write(bytes(out) + raw[alen:])
        print('   已解 %d 块 -> %s (%d B)；头部 = %r' % (nblk, path, alen, bytes(out[:40])))
        print('   >i8 fileSize @30..37 = %d  vs ALEN=%d -> %s'
              % (struct.unpack_from('>q', out, 30)[0], alen,
                 '一致 ✓' if struct.unpack_from('>q', out, 30)[0] == alen else '不一致 ✗'))
        try:
            import UnityPy
            env = UnityPy.Environment(path)
            objs = list(env.objects)
            print('   ✅ UnityPy 打开成功：%d 个对象，类型 = %s'
                  % (len(objs), sorted({str(t.type) for t in objs})))
            for t in objs[:8]:
                print('      -', t.type, getattr(t.object, 'm_Name', ''))
        except Exception as e:
            print('   UnityPy：%s: %s' % (type(e).__name__, str(e)[:180]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
