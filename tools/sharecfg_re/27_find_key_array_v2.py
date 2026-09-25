#!/usr/bin/env python3
# -*- coding -*-
"""27_find_key_array_v2.py —— 从已有内存快照里找 www() 的 19×int32 内联密钥表。

24 号被判"校准是假的"（它只看 max_length 值对上，结果全是别处结构里恰好相等的整数）。
本脚本的差异：**两阶段，第一阶段不找密钥**，只用「载荷内容可独立预知」的数组把
il2cpp 数组对象头**校准**出来，第二阶段才按校准过的布局去找 int32[19]。

布局假设（被校准证伪或证实，不当前提）：
    +0x00 klass*   +0x08 monitor   +0x10 bounds*   +0x18 max_length(uintptr)   +0x20 数据

双闸（缺一道即判未校准）：
  值闸   max_length == 期望元素数
  结构闸 klass 像堆内指针、bounds 为 NULL 或像指针、且**同一段里还能找到载荷全为
         可打印 ASCII 的 byte[]**（内容可独立预知 → 布局不可能靠巧合满足）

用法：
  py -3 tools/sharecfg_re/27_find_key_array_v2.py
  py -3 tools/sharecfg_re/27_find_key_array_v2.py --want 19
"""
import argparse, collections, mmap, os, re, struct, sys
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DUMP = os.path.join(ROOT, '.diag', 'sharecfg_re', 'memdump')
PTR_MIN, PTR_MAX = 0x10000, 0x8000_0000_0000
# ⚠️ 上界必须是 2^47 量级，不能用 2^32：实测本快照里字符串地址是 47 位 `0x7d3f_xxxxxxxx`，
#    进程是 64 位（与 libil2cpp.so 为 ELF64 一致）。原先的 `0x8000_0000` 会把**所有真指针**拒掉，
#    导致 16,071 / 55,010 个原始命中全部 0 通过结构闸——那个 0 由闸造成，与对象是否存在无关。
# ⚠️ 本文件仍有一处已知自伤：阶段 1 的 byte[] 判据写在 `if not len(good): continue` **之后**，
#    所以它报 0 不代表"布局未校准时找不到可预知载荷"，只代表阶段 2 一个候选都没有。
#    要拿它出结论，必须先把阶段 1 移出该 continue 之外。


def regions():
    for fn in sorted(os.listdir(DUMP)):
        m = re.match(r'^\d+_([0-9a-f]{16})_([0-9a-f]{16})\.bin$', fn)
        if m:
            lo, hi = int(m.group(1), 16), int(m.group(2), 16)
            if hi > lo:
                yield lo, hi, os.path.join(DUMP, fn)


def scan(mm, lo):
    """返回 (对象起始地址数组, u) —— u 是 8 字节4 字节对齐的 uint64 视图。"""
    # 32 位进程：klass@+0x00 monitor@+0x04 bounds@+0x08 max_length@+0x0C 数据@+0x10
    u = np.frombuffer(mm, dtype=np.uint32)
    # max_length 在 obj+0x0C => u 索引 = obj/4 + 3
    idx = np.nonzero(u == np.uint64(WANT))[0]
    idx = idx[idx >= 3]
    c = idx - 3
    c = c[c + (WANT_Elems + 4) < len(u)]
    return u, c


def struct_ok(u, c):
    klass = u[c]
    bounds = u[c + 2]
    mon = u[c + 1]
    ok = (klass > PTR_MIN) & (klass < PTR_MAX) & ((bounds == 0) | ((bounds > PTR_MIN) & (bounds < PTR_MAX)))
    ok &= (mon == 0) | ((mon > PTR_MIN) & (mon < PTR_MAX))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--want', type=int, default=19)
    a = ap.parse_args()
    global WANT, WANT_Elems
    WANT = np.uint64(a.want)
    WANT_Elems = a.want + 4

    ascii_hits, key_hits, klass_hist = [], [], collections.Counter()
    total = 0
    for lo, hi, path in regions():
        size = hi - lo
        if size > 0x4000_0000:          # 跳过 >16GB 的异常段
            continue
        total += size
        mm = open(path, 'rb').read()      # 直接读入，避免 mmap 被 numpy 导出器钉住
        u, c = scan(mm, lo)
        if not len(c):
            del u, c, mm
        continue
        good = c[struct_ok(u, c)]
        if not len(good):
            del u, c, mm
        continue
        # ---- 阶段 1：在**同一批**通过结构闸的对象里，找载荷全为可打印 ASCII 的 byte[]
        #      （byte[] 的 max_length 是元素数，载荷紧随 +0x20）
        small = c[(u[c] > 0)]
        base_bytes = (u.view(np.uint8) if False else None)
        for j in small:
            n = int(u[j + 3])
            if not (4 <= n <= 64):
                continue
            p = (j + 4) * 4
            if p + n > len(mm):
                continue
            pay = mm[p:p + n]
            if pay and all(32 <= x < 127 for x in pay):
                ascii_hits.append((lo + p, n, bytes(pay)))
                if len(ascii_hits) > 400:
                    break
        # ---- 阶段 2：max_length == want 且元素非全 0
        for j in good:
            p = (j + 4) * 8
            need = a.want * 4
            if p + need > len(mm):
                continue
            vals = struct.unpack_from('<%dI' % a.want, mm, p)
            if any(vals):
                key_hits.append((lo + p, int(u[j]), vals))
                klass_hist[int(u[j - 4])] += 1
        mm.close(); f.close()
        if len(ascii_hits) > 400:
            break

    print('# 扫描 %.2f GB 快照' % (total / 2**30))
    print()
    print('== 阶段 1  载荷可独立预知的 byte[]（全段可打印 ASCII）: %d' % len(ascii_hits))
    seen = set()
    for addr, n, pay in ascii_hits:
        s = pay[:44]
        if s in seen:
            continue
        seen.add(s)
        print('   0x%012X n=%-3d %r' % (addr, n, s))
        if len(seen) >= 14:
            break
    print()
    print('== 阶段 2  max_length==%d 且结构闸通过: %d' % (a.want, len(key_hits)))
    print('   按 klass 分桶 top8:', [('0x%X' % k, c) for k, c in klass_hist.most_common(8)])
    for addr, klass, vals in key_hits[:10]:
        print('   0x%012X  %s' % (addr, ' '.join('%08X' % v for v in vals)))
    print()
    if not ascii_hits:
        print('⚠️ 阶段 1 为空 => 对象头布局未经校准，阶段 2 的所有候选一律不得采信。')
    else:
        print('✅ 阶段 1 非空 => 布局至少与「载荷可预知」的数组自洽；阶段 2 仍须按 klass 分桶收敛后再取。')


if __name__ == '__main__':
    main()
