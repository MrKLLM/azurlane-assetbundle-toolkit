#!/usr/bin/env python3
# -*- coding -*-
"""www() 的输入契约（外层封装）+ 种子的**穷举**判据。

来源：08_disasm_method.py --xref www  →  全库唯一调用方 LuaScriptMgr.Load。
从 Load/www 两处机器码读到的契约（指令地址见 README (16)）：

  LuaScriptMgr.Load(path):
      bytes = PathUtil.ReadAllBytes(PathUtil.GetLuaBundle(path))
      if len(bytes) >= 14:
          m = bytes[len-14] & ~0x80
          plain = (m == 0) and (bytes[0] == 0x1B and bytes[1:4] == b"lua")
          data = bytes if plain else www(bytes)
      else: data = bytes
      luaL_loadbuffer(L, data, len, "@" + path)

  www(b):            # 只改 b[0 .. len-15]，尾部 14 字节原样保留
      flag  = b[len-1] & ~0x80                  # 0x3D9CC0C-0x3D9CC1F
      state = 235 + K + flag   (mod 2^32)       # K = byte[4] of a 19-byte const array
      n     = (b[len-13] & ~0x80) + 1  (mod 2^8) # 0x3D9CC9F 起：循环上界也来自尾部
      for i in 0..n-1:
          c = b[i]; b[i] = ((state>>8) ^ c); state = ((state+c)*205+207) mod 2^32

两个要点：
  1. **种子里唯一硬编码的是 235**，另外两项（尾部 flag 字节、常量数组 byte[4]）是逐文件的。
  2. `out[i]` 只取 `state>>8` 的第 8..15 位，而 `state=(state+c)*205+207` 是**仿射且只向高位进位**，
     所以第 8..15 位永远只由 `state` 的低 16 位决定 → **整条密钥流只依赖种子的低 16 位**。
     于是"种子没试对"这个可能性可以**穷举封死**（只有 65536 个有效种子），不必再抽样。

用法：
  py -3 tools/sharecfg_re/26_www_wrapper.py                 # 默认：scripts64/32 + 全部配置表
  py -3 tools/sharecfg_re/26_www_wrapper.py --max-off 8192
"""
import argparse, os, struct, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MOD16 = 0xFFFF

# 验收前缀：www()/Load 之后交给 luaL_loadbuffer 的东西只可能是这几种。
# 每多一个字节 = 多 8 位约束，而自由度只有 16 位（见文件头），所以长度 <5 的目标
# 纯属噪声，必须按期望假命中数（2^(16-8L) x 偏移数）打折看。
TARGETS = {
    b'UnityFS\x00':   'AssetBundle 头（上一轮的判据）',
    b'\x1blua':       'Load 的"不加密"标记（小写）',
    b'\x1bLuaT':      '真 Lua 字节码签名',
    b'local ':        'Lua 源码',
    b'--[':           'Lua 源码注释开头',
}


def solve_seeds(buf, off, target):
    """给定文件与起始偏移，返回**全部**能产出 target 前缀的种子低 16 位（0..65535）。

    穷举不是靠循环 65536 次：out[0] 直接钉死 state_0 的 bit8..15，bit0..7 只剩 256 种，
    之后每个字节过一轮滤 —— 与对 65536 个有效种子做全量检验完全等价。
    """
    if off + len(target) > len(buf):
        return []
    mid = (target[0] ^ buf[off]) & 0xFF
    cand = [(lo | (mid << 8), lo | (mid << 8)) for lo in range(256)]   # (seed, state_i)
    for i in range(1, len(target)):
        want = (target[i] ^ buf[off + i]) & 0xFF
        c = buf[off + i - 1]
        nxt = []
        for s, st in cand:
            ns = ((st + c) * 205 + 207) & MOD16
            if ((ns >> 8) & 0xFF) == want:
                nxt.append((s, ns))
        cand = nxt
        if not cand:
            return []
    return [s for s, _ in cand]


def keystream(buf, off, n, state):
    """真·www 递推（mod 2^32）。"""
    out = bytearray()
    for i in range(n):
        c = buf[off + i]
        out.append(((state >> 8) ^ c) & 0xFF)
        state = ((state + c) * 205 + 207) & 0xFFFFFFFF
    return bytes(out)


def keystream16(state, buf, off, n):
    """声称与 mod 2^32 等价的低 16 位版本 —— 由 closure_selftest 负责证伪/证实。"""
    out = bytearray()
    for i in range(n):
        c = buf[off + i]
        out.append(((state >> 8) ^ c) & 0xFF)
        state = ((state + c) * 205 + 207) & MOD16
    return bytes(out)


def closure_selftest():
    """承重墙自检：只改种子的高 16 位，输出必须逐字节不变。

    '65536 个种子就已经穷举完' 完全依赖这条；它若假，下面的否证强度全部作废。
    """
    import random
    rng = random.Random(7)
    bad = 0
    for _ in range(2000):
        buf = bytes(rng.randrange(256) for _ in range(32))
        low = rng.randrange(1 << 16)
        ref = keystream(buf, 0, 16, low)
        for _ in range(8):
            hi = rng.randrange(1, 1 << 16)
            s32 = low | (hi << 16)
            if keystream(buf, 0, 16, s32) != ref or keystream16(s32 & MOD16, buf, 0, 16) != ref:
                bad += 1
    print('# 低 16 位闭合自检: 2000 组 x (1 + 8 个高 16 位变体)，不一致 %d 次  %s'
          % (bad, 'OK（穷举成立）' if bad == 0 else '** 闭合不成立，穷举强度作废 **'))
    return bad == 0


def selftest():
    """阳性对照：随机构造已知种子的前缀，求解器必须原样反出来。

    没有这一段，'0 命中' 完全可能只是求解器写错的空结果。
    """
    import random
    rng = random.Random(20260924)
    bad = 0
    for _ in range(400):
        buf = bytes(rng.randrange(256) for _ in range(48))
        seed = rng.randrange(1 << 16)
        off = rng.randrange(0, 8)
        tgt = keystream16(seed, buf, off, 6)
        got = solve_seeds(buf, off, tgt)
        if seed not in got:
            bad += 1
    print('# 反解阳性对照: 400 次随机 (buffer, seed, off)，失败 %d 次  %s'
          % (bad, 'OK' if bad == 0 else '** 求解器不可信，下面所有结论作废 **'))
    return bad == 0


def scan(name, buf, max_off):
    print('\n=== %s  (%d 字节) ===' % (name, len(buf)))
    if len(buf) >= 14:
        flag = buf[len(buf) - 14] & 0x7F
        print('  封装位判定: byte[len-14]=0x%02X -> m=%d  %s' % (
            buf[len(buf) - 14], flag,
            '不加密（且需 \x1blua 头）' if flag == 0 else '会走 www()'))
        print('  头部 4 字节 %s' % buf[:4].hex(' '))
    hits = 0
    n_off = min(max_off, max(1, len(buf) - 8))
    for tgt, why in TARGETS.items():
        bits = 8 * len(tgt)
        exp_fp = n_off * (2 ** 16) / (2 ** bits)
        found = []
        for off in range(n_off):
            s = solve_seeds(buf, off, tgt)
            if s:
                found.append((off, s))
        mark = 'HIT ' if found else ' 0  '
        print('  [%s] %-12r %-26s 约束=%d位 期望假命中=%.2g 命中 %d'
              % (mark, tgt, why, bits, exp_fp, len(found)))
        for off, s in found[:6]:
            print('        off=%d 可行种子(低16)=%s' % (off, [hex(x) for x in s[:8]]))
            st = s[0]
            dec = keystream16(st, buf, off, 40)
            print('          该种子下前 40 字节: %s' % dec[:40])
        hits += len(found)
    return hits


def needle_test(path, max_off):
    """仪器灵敏度对照：在真文件里种一段 www 加密过的 'UnityFS\\0'，必须被抓到。

    selftest 只证明数学可逆；这条证明'读文件 + 扫偏移 + 报命中'这整条链路会响。
    """
    buf = bytearray(open(path, 'rb').read())
    rng = __import__('random').Random(11)
    planted = []
    for _ in range(5):
        off = rng.randrange(0, min(max_off, len(buf) - 16))
        seed = rng.randrange(1 << 16)
        pt = b'UnityFS\x00' + bytes(rng.randrange(256) for _ in range(8))
        # 加密方向：www 解密时 c 取的是**密文**字节，所以 state 必须用写下去的 c 推进
        enc = bytearray(len(pt))
        st = seed
        for i in range(len(pt)):
            c = ((st >> 8) ^ pt[i]) & 0xFF
            enc[i] = c
            st = ((st + c) * 205 + 207) & MOD16
        buf[off:off + len(enc)] = enc
        planted.append((off, seed))
    buf = bytes(buf)
    got = {}
    for off in range(min(max_off, len(buf) - 8)):
        s = solve_seeds(buf, off, b'UnityFS\x00')
        if s:
            got[off] = s
    ok = sum(1 for off, seed in planted if got.get(off) and seed in got[off])
    print('# 埋针对照 %s: 种 5 处，抓到 %d 处（额外命中 %d 处）  %s'
          % (os.path.basename(path), ok, len(got) - ok,
             'OK' if ok == 5 else '** 仪器不响，0 命中不可信 **'))
    return ok == 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-off', type=int, default=4096)
    a = ap.parse_args()
    ab = os.path.join(ROOT, 'files', 'AssetBundles')
    sp64 = os.path.join(ab, 'scripts64')
    if not closure_selftest() or not selftest() or not needle_test(sp64, a.max_off):
        print('\n对照未通过，拒绝输出否证结论。')
        sys.exit(3)

    total = 0
    for f in ('scripts64', 'scripts32'):
        p = os.path.join(ab, f)
        if os.path.exists(p):
            total += scan(f, open(p, 'rb').read(), a.max_off)

    cfg = os.path.join(ab, 'sharecfgdata')
    names = sorted(os.listdir(cfg))[:3]
    print('\n=== 配置表（对照：www() 不在配置读取路径上，这里只是留个数据点）===')
    for n in names:
        p = os.path.join(cfg, n)
        if os.path.isfile(p):
            print('  %-28s 头 5 字节 %s' % (n, open(p, 'rb').read(5).hex(' ')))

    print('\n判据结论: %s' % ('有命中，见上' if total else
          '全部 65536 个有效种子 x 0..%d 偏移，无任何前缀命中 —— 否证是穷举级的' % a.max_off))


if __name__ == '__main__':
    main()
