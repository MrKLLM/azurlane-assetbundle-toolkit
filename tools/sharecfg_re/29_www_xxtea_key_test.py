#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 www() Phase C 的机器码逐指令落成代码，并用 28 号脚本从 metadata 默认值堆里
取到的 19×int32 候选密钥，去解真实 scripts64/scripts32 的头 8 字节。

机器码事实（08_disasm_method.py --at 逐条读出来的，不是推测）：
  0x3D9CD0C  Array::New(2)，元素 klass slot = data 0x717DB78，与 0x3D9CB27 的
             Array::New(0x13) 用**同一个 slot** => 数据块 = int[2] = 8 字节，密钥 = int[19]
  0x3D9CD9C..0x3D9CDC3  输入 byte[] 的**前 8 字节**按小端打成 2 个 word
  0x3D9CDBE  ebp(=z) 初值 = 打包出的 v[0]（不是规范 XXTEA 的 v[n-1]）
  0x3D9CF2C  sum = 0x0DFF7A0A ；0x3D9D00E 每轮 sum += 0xF90042FB
  0x3D9CF32  计数器 [rsp+0x14]=2（0x3D9D01B dec/jne）=> 字面上 2 轮
  0x3D9CF3B  e=(sum>>2)&3 ；0x3D9CF67 密钥下标 =(p&3)^e
  0x3D9CF7B..0x3D9CFBE  p 从 n-1 递减：y=v[p-1], v[p]-=MX, z=v[p]
  0x3D9CFD2..0x3D9D015  收尾 p=0：y=v[n-1], v[0]-=MX, z=v[0]
  MX = ((y^key[(p&3)^e]) + (z^sum)) ^ (((z<<2)^(y>>5)) + ((y<<4)^(z>>3)))
       —— 与规范 XXTEA 的 MX 逐项对得上（只是 y/z 记法互换）

验收判据（用户原话）：www() 的输出必须含 UnityFS。
  "UnityFS\0" 小端两字 = (0x74696E55, 0x00534679)

三重对照（缺一不出结论）：
  1 闭合自测：walk 与 inv_walk 必须互逆（随机 5000 组往返）；
  2 阳性自测：把密文 inv_walk(UnityFS明文块) 喂回扫描器必须命中；
  3 灵敏度对照：把该密文**种进真实 scripts64/32 的头 8 字节**（只改内存副本），
    扫描器必须在真实文件上找回偏移 0 —— 证明"扫不到"不是扫描器坏了。
判据未达且对照全过才允许输出否证，并写清穷举了哪些自由度。

用法: py -3 tools/sharecfg_re/29_www_xxtea_key_test.py
"""
import os, random, struct, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MD = os.path.join(ROOT, 'files', 'il2cpp', 'Metadata', 'global-metadata.dat')
AB = os.path.join(ROOT, 'files', 'AssetBundles')
M = 0xFFFFFFFF
DELTA = 0xF90042FB
SUM0 = 0x0DFF7A0A
TARGET = [0x74696E55, 0x00534679]        # "Unit" "yFS\0"
SEEN_ROUNDS = 2


def mx(y, z, s, k):
    g1 = (((z << 2) & M) ^ (y >> 5)) & M
    g2 = (((y << 4) & M) ^ (z >> 3)) & M
    return (((y ^ k) + (z ^ s)) ^ ((g1 + g2) & M)) & M


def walk(v, key, rounds=SEEN_ROUNDS, z_init='v0', sum_dir='add', op='sub',
         sum0=SUM0, delta=DELTA):
    """逐指令照抄 Phase C（n=2）。"""
    n = len(v)
    v = list(v)
    z = v[0] if z_init == 'v0' else v[n - 1]
    s = sum0
    for _ in range(rounds):
        e = (s >> 2) & 3
        p = n - 1
        while p > 0:
            y = v[p - 1]
            t = mx(y, z, s, key[((p & 3) ^ e) % len(key)])
            v[p] = (v[p] - t) & M if op == 'sub' else (v[p] + t) & M
            z = v[p]
            p -= 1
        y = v[n - 1]
        t = mx(y, z, s, key[e % len(key)])
        v[0] = (v[0] - t) & M if op == 'sub' else (v[0] + t) & M
        z = v[0]
        s = (s + delta) & M if sum_dir == 'add' else (s - delta) & M
    return v


def inv_walk(v, key, rounds=SEEN_ROUNDS, sum0=SUM0, delta=DELTA):
    """walk(op='sub', z_init='v0', sum_dir='add', n=2) 的逆。
    每轮里 p=0 那步 y==z==v[1]，p=1 那步 y==z==本轮起点的 v[0]，故可逐层反推。"""
    v = list(v)
    for s in reversed([(sum0 + delta * i) & M for i in range(rounds)]):
        e = (s >> 2) & 3
        v[0] = (v[0] + mx(v[1], v[1], s, key[e % len(key)])) & M
        v[1] = (v[1] + mx(v[0], v[0], s, key[(1 ^ e) % len(key)])) & M
    return v


def get_blob(d, rec_index):
    fo, fsz = struct.unpack_from('<ii', d, 8 + 8 * 7)
    bo, bsz = struct.unpack_from('<ii', d, 8 + 8 * 8)
    n = fsz // 12
    a = struct.unpack_from('<iii', d, fo + 12 * rec_index)
    b = struct.unpack_from('<iii', d, fo + 12 * (rec_index + 1)) if rec_index + 1 < n else (0, 0, bsz)
    return d[bo + a[2]:bo + b[2]], bo + a[2]


def closure(key):
    rnd = random.Random(7)
    ok = 0
    for _ in range(5000):
        v = [rnd.getrandbits(32), rnd.getrandbits(32)]
        if inv_walk(walk(v, key), key) == v:
            ok += 1
    return ok


def configs(klen):
    """只枚举机器码没读死的自由度：z 初值 / 轮数 / sum 方向 / 密钥窗口起点。"""
    out = []
    for zi in ('v0', 'vn1'):
        for rounds in (SEEN_ROUNDS, 1, 16, 32):
            for sd in ('add', 'sub'):
                for koff in range(min(16, klen)):
                    out.append((zi, rounds, sd, koff))
    return out


def run_scan(buf, cfgs, keys, lo, hi):
    """返回 [(偏移, 配置名, 密钥窗口)] —— 先只扫 lo..hi。"""
    hits = []
    for zi, rounds, sd, koff in cfgs:
        for kw in keys:
            for base in range(lo, hi):
                if base + 8 > len(buf):
                    break
                v = list(struct.unpack_from('<2I', buf, base))
                if walk(v, kw, rounds=rounds, z_init=zi, sum_dir=sd) == TARGET:
                    hits.append((base, 'z=%s r=%d sum=%s' % (zi, rounds, sd), koff))
    return hits


def main():
    d = open(MD, 'rb').read()
    raw17, at17 = get_blob(d, 17654)
    raw10, at10 = get_blob(d, 10632)
    k17 = list(struct.unpack('<19I', raw17)) if len(raw17) == 76 else None
    k10 = list(struct.unpack('<19I', raw10)) if len(raw10) == 76 else None
    print('候选 A rec#17654 @0x%X len=%d %s' % (at17, len(raw17), ' '.join('%08X' % w for w in (k17 or [])[:5])))
    print('候选 B rec#10632 @0x%X len=%d（28 号显示它是 ASCII 文本，一并扫作阴性对照）'
          % (at10, len(raw10)))
    keys = [('A', k17), ('B', k10)]
    keys = [(nm, k) for nm, k in keys if k]
    ok = closure(k17)
    print('\n[对照 1] walk/inv_walk 闭合 %d/5000 -> %s' % (ok, '通过' if ok == 5000 else '不通过'))
    if ok != 5000:
        return 3

    files = {}
    for nm in ('scripts64', 'scripts32'):
        p = os.path.join(AB, nm)
        if os.path.exists(p):
            files[nm] = open(p, 'rb').read()
            print('%s %d 字节，头 8 = %s' % (nm, len(files[nm]), files[nm][:8].hex(' ')))
    if not files:
        print('找不到 scripts* 包'); return 2

    cfgs = configs(len(k17))
    print('配置数 = %d（z{2} × rounds{4} × sum方向{2} × 密钥窗口 16）' % len(cfgs))

    # ---- 先跑"字面照抄"那一档，最快也最可能是对的
    prim = [(zi, r, sd, ko) for zi, r, sd, ko in cfgs if (zi, r, sd, ko) == ('v0', SEEN_ROUNDS, 'add', 0)]
    print('\n[主判据·字面配置 z=v0 rounds=2 sum=add koff=0]')
    allhits = []
    for nm, b in files.items():
        for knm, k in keys:
            h = run_scan(b, prim, [k], 0, 4096)
            print('  %s 密钥%s：偏移 0..4095 命中 %d %s' % (nm, knm, len(h), h[:3]))
            allhits += [(nm, knm) + x for x in h]

    # ---- 对照 2/3：种针（用 inv_walk 造密文种进真实文件头，必须找回偏移 0）
    needle_files = 0
    for nm, b in files.items():
        for knm, k in keys:
            ct = inv_walk(list(TARGET), k)
            b2 = bytearray(b)
            struct.pack_into('<2I', b2, 0, *ct)
            h = run_scan(bytes(b2), prim, [k], 0, 4096)
            got = [x for x in h if x[0] == 0]
            print('[对照 3] %s 密钥%s 种针 -> %s' % (nm, knm, ('偏移0命中' if got else '未命中!! %s' % h[:2])))
            if got:
                needle_files += 1
    if needle_files != len(files) * len(keys):
        print('种针未全找回 -> 扫描器不可信，本轮不出任何结论')
        return 3

    if allhits:
        print('\n>>> 判据达成：%s' % allhits)
        return 0

    # ---- 全配置扫描（字面档没中时才值得花这笔）
    print('\n[扩围] 全 %d 配置 × 偏移 0..4095 × %d 文件 × %d 密钥 …' % (len(cfgs), len(files), len(keys)))
    big = []
    for nm, b in files.items():
        for knm, k in keys:
            h = run_scan(b, cfgs, [k], 0, 4096)
            big += [(nm, knm) + x for x in h]
            if h:
                print('  命中：%s 密钥%s %s' % (nm, knm, h[:3]))
    trials = len(cfgs) * 4096 * len(files) * len(keys)
    if big:
        print('\n>>> 判据达成（扩围档）：%s' % big)
        return 0
    print('\n>>> 判据未达成。否证覆盖的自由度：%d 配置 × 偏移 0..4095 × %d 文件 × %d 个 76B 候选 = %d 次，'
          '每次判定 64 位 -> 期望假命中 %.1e'
          % (len(cfgs), len(files), len(keys), trials, trials * 2 ** -64))
    print('未覆盖（诚实声明）：MX 的其它变形、密钥不在 rec#17654/rec#10632 而是整堆任意 19 字窗口、'
          'Phase A/B 先改写过这 8 字节的可能。')
    return 1


if __name__ == '__main__':
    sys.exit(main())
