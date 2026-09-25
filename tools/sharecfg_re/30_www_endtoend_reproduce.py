#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""www() 的三段在**真实文件**上端到端复现，并给出四条互相独立的自洽判据。

为什么值得单独成工具：上一轮（含我自己）把 trailer 读成 **LE32**，于是得到
L = 19.6 亿 > 文件长 → 判"盘上 scripts 文件不是 www 的输入"。逐指令重读 0x3D9CAAB-0x3D9CB04：
    word = b[len-4]<<24 | b[len-3]<<16 | b[len-2]<<8 | b[len-1]   → **大端**
`scripts64` 末 4 字节 = 00 00 19 75 → L = **6517**（自洽）。所以那条"不是 www 输入"的否证作废。

四条判据（任一不过即 exit 3，不输出任何结论）：
  A1  L = BE32(buf[-4:]) 必须 0 < L < filesize-4；
  A2  Phase C：逐 8 字节块 ECB 解开后，块 0 必须 == b"UnityFS\\0"；
  A3  **自报长度互校**：解出的前 64 字节里必须出现 `>i4(filesize-4-L)`
      ——即 AB 自己声明的 fileSize 恰好等于"按我的模型算出的返回缓冲长度"，
      这是不含任何未知量的性质，比"可打印率高"强得多；
  A4  Phase A+B：尾段 buf[-4-L:-4] 过 235 反馈流后必须以 1b 4c 4a 开头（容器 Header_32/_64 魔数）。
  A5  阴性对照：换一把密钥（把 19 个字整体 +1）后 A2/A3 必须同时失效。

参照物用途：A4 解出的那段是**已知良好的载荷明文**（6512 字节），它与
`sharecfgdata/<表>` 的正文在**同一偏移**上共享记录骨架（`4e ff 00 00 51` 逐字节相同）、
字符串区是同一种 0x80-0xBF 游程编码 ⇒ 用来判"配置表到底要不要解密"，
也顺手否掉"用可打印率当判据"这种做法（这段真明文的可打印率只有 0.216）。

用法: py -3 tools/sharecfg_re/30_www_endtoend_reproduce.py [文件名 ...]
产物: .diag/sharecfg_re/<name>.tailpayload.bin（A4 解出的参照载荷，仅诊断用）
"""
import os, struct, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MD = os.path.join(ROOT, 'files', 'il2cpp', 'Metadata', 'global-metadata.dat')
AB = os.path.join(ROOT, 'files', 'AssetBundles')
DI = os.path.join(ROOT, '.diag', 'sharecfg_re')
M = 0xFFFFFFFF
DELTA = 0xF90042FB
SUM0 = 0x0DFF7A0A


def mx(y, z, s, k):
    g1 = (((z << 2) & M) ^ (y >> 5)) & M
    g2 = (((y << 4) & M) ^ (z >> 3)) & M
    return (((y ^ k) + (z ^ s)) ^ ((g1 + g2) & M)) & M


def block2(v, key):
    """Phase C 的 n=2 反轮（z 初值 = 本块 v[0]，sum 每块重置、每轮 +delta、共 2 轮）。"""
    v = list(v)
    z = v[0]
    s = SUM0
    for _ in range(2):
        e = (s >> 2) & 3
        y = v[0]
        v[1] = (v[1] - mx(y, z, s, key[1 ^ e])) & M
        z = v[1]
        y = v[1]
        v[0] = (v[0] - mx(y, z, s, key[e])) & M
        z = v[0]
        s = (s + DELTA) & M
    return v


def stream235(b):
    b = bytearray(b)
    st = 235
    for i, c in enumerate(b):
        b[i] = ((st >> 8) & 0xFF) ^ c
        st = ((st + c) * 205 + 207) & M
    return bytes(b)


def load_key():
    d = open(MD, 'rb').read()
    fo, fsz = struct.unpack_from('<ii', d, 8 + 8 * 7)
    bo, bsz = struct.unpack_from('<ii', d, 8 + 8 * 8)
    c = struct.unpack_from('<iii', d, fo + 12 * 17654)[2]
    nx = struct.unpack_from('<iii', d, fo + 12 * 17655)[2]
    return list(struct.unpack('<19I', d[bo + c:bo + nx]))


def runs_stat(b):
    import re
    r = [len(m.group(0)) for m in re.finditer(rb'[\x80-\xbf]{4,}', b)]
    return (len(r), round(sum(r) / len(r), 2), max(r) if r else 0) if r else (0, 0, 0)


def one(name, key, verbose=True):
    p = os.path.join(AB, name)
    raw = open(p, 'rb').read()
    n = len(raw)
    L = struct.unpack_from('>I', raw, n - 4)[0]
    print('\n== %s  filesize=%d  L=BE32(末4)=%d' % (name, n, L))
    if not (0 < L < n - 4):
        print('   A1 不过：L 不自洽 -> 该文件不是 www 容器形态'); return None
    print('   A1 过（返回缓冲 = new byte[%d]）' % (n - 4 - L))
    # A2/A3：ECB 逐块解头
    head = bytearray(raw[:64])
    for off in range(0, 64, 8):
        struct.pack_into('<2I', head, off, *block2(list(struct.unpack_from('<2I', raw, off)), key))
    ok2 = bytes(head[:8]) == b'UnityFS\x00'
    size_be = struct.pack('>i', n - 4 - L)
    at = bytes(head).find(size_be)
    print('   A2 %s（块0 = %r）' % ('过' if ok2 else '**不过**', bytes(head[:8])))
    print('   A3 %s（AB 自报 fileSize %s = %d 出现在解出偏移 %s；模型算得 %d）'
          % ('过' if at >= 0 else '**不过**', size_be.hex(' '), n - 4 - L, at, n - 4 - L))
    # A4：尾段
    tail = stream235(raw[n - 4 - L:n - 4])
    ok4 = tail[:3] == bytes.fromhex('1b4c4a')
    print('   A4 %s（尾段过 235 流后头 5 = %s）' % ('过' if ok4 else '**不过**', tail[:5].hex(' ')))
    if not (ok2 and at >= 0 and ok4):
        return None
    os.makedirs(DI, exist_ok=True)
    open(os.path.join(DI, name + '.tailpayload.bin'), 'wb').write(tail[5:])
    print('   参照载荷已写出 .diag/sharecfg_re/%s.tailpayload.bin (%d B, 可打印率 %.3f, 0x80-0xBF 游程 %s)'
          % (name, len(tail) - 5,
             sum(1 for x in tail[5:] if 32 <= x < 127) / (len(tail) - 5), runs_stat(tail[5:])))
    if verbose:
        cfg = open(os.path.join(AB, 'sharecfgdata', 'aircraft_template'), 'rb').read()[:24]
        print('   与 sharecfgdata/aircraft_template 同偏移比对: 参照 %s | 表 %s'
              % (tail[5:19].hex(' '), cfg[:14].hex(' ')))
    return tail


def main():
    key = load_key()
    print('密钥 int[19] = %s ...' % ' '.join('%08X' % w for w in key[:4]))
    names = sys.argv[1:] or ['scripts64', 'scripts32']
    passed = []
    for nm in names:
        if one(nm, key) is not None:
            passed.append(nm)
    # A5 阴性对照
    bad = [(w + 1) & M for w in key]
    print('\n== A5 阴性对照（19 个字整体 +1）')
    raw = open(os.path.join(AB, names[0]), 'rb').read()
    h = block2(list(struct.unpack_from('<2I', raw, 0)), bad)
    print('   假密钥解块0 = %r  -> 应为垃圾（判据 A2 随之失效）' % struct.pack('<2I', *h))
    if bytes(struct.pack('<2I', *h)) == b'UnityFS\x00':
        print('   假密钥也命中 -> 判据无区分力，本轮结论全部作废'); return 3
    if len(passed) != len(names):
        print('   有文件未过 A1-A4 -> 不出结论'); return 3
    print('\n全部判据通过：%s' % passed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
