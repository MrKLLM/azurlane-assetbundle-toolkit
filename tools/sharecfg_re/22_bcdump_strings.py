#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解 LuaJIT BCDUMP 的 gcdata（字符串常量段），把 ship_skin_words 的台词正文导出来。

分两步走、先做确定性高的这一步：
  * gcdata 段格式很简单：`\x1bLJ` + ver(1) + flags(1) + ULEB126(gcdata 总长) + 若干条
    `ULEB126(长度) + 字节` —— 逐条走就能干净地取出所有字符串，**不需要理解指令**。
  * 而 (skin_id -> 台词) 的配对要把 proto 头 + BC 操作数（KSHORT/KNUM/KPRI 与
    TNEW/TSETV 序列）走完才知道顺序，属于下一步；本脚本不假装已经做到。

自校验（防止把任意字节流当字符串读出来一大堆垃圾）：
  1. 版本字节必须是 0x01/0x02；
  2. gcdata 总长必须 <= blob 剩余长度，且**逐条走完正好消耗这么多字节**（走不完或超出即判错）；
  3. 解出的串里必须出现已确认的台词原文（如 `只是在检查刚入库的点心而已`）才算命中目标模块。

用法: py -3 tools/sharecfg_re/22_bcdump_strings.py [--name ship_skin_words]
"""
import argparse, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DUMP = os.path.join(ROOT, '.diag', 'sharecfg_re', 'memdump')
MAGIC = b'\x1bLJ'
CANARY = '只是在检查刚入库的点心而已'.encode()


def uleb(b, i):
    """LuaJIT 用 ULEB126（最高位=继续，每段 7 位）。返回 (值, 新下标) 或 (None, i)。"""
    v = 0
    sh = 0
    while i < len(b):
        c = b[i]
        i += 1
        v |= (c & 0x7F) << sh
        if not (c & 0x80):
            return v, i
        sh += 7
        if sh > 42:
            return None, i
    return None, i


def parse_blob(b):
    """b 从 \x1bLJ 开始。返回 (strings, ok, why)。"""
    if len(b) < 6 or b[:3] != MAGIC:
        return [], False, 'magic'
    ver = b[3]
    if ver not in (1, 2):
        return [], False, 'ver=%d' % ver
    flags = b[4]
    i = 5
    if flags & 0x02:          # BCDUMP_F_TRACE: 前面有 trace 编号 uleb
        _, i = uleb(b, i)
    glen, i = uleb(b, i)
    if glen is None or i + glen > len(b):
        return [], False, 'gcdata 长度越界 (%s)' % glen
    seg = b[i:i + glen]
    out = []
    j = 0
    while j < len(seg):
        ln, j2 = uleb(seg, j)
        if ln is None or j2 + ln > len(seg):
            return out, False, 'gcdata 内部走不完 @%d' % j
        raw = seg[j2:j2 + ln]
        out.append(raw)
        j = j2 + ln
    ok = (j == len(seg))
    return out, ok, 'flags=0x%02x ver=%d glen=%d' % (flags, ver, glen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', default='ship_skin_words')
    ap.add_argument('--dir', default=DUMP)
    ap.add_argument('--maxscan', type=int, default=400)
    a = ap.parse_args()
    pat = a.name.encode()
    fs = [f for f in sorted(os.listdir(a.dir)) if f.endswith('.bin')]
    tried = 0
    best = None
    for f in fs:
        b = open(os.path.join(a.dir, f), 'rb').read()
        if pat not in b:
            continue
        for m in re.finditer(re.escape(MAGIC), b):
            tried += 1
            strs, ok, why = parse_blob(b[m.start():m.start() + 4_000_000])
            cn = [s for s in strs if pat in s]
            if cn:
                has = CANARY in strs
                print('候选 %s @0x%x  串 %d 条  结构走完=%s  含canary=%s  (%s)  命中名=%r'
                      % (f[-26:], m.start(), len(strs), ok, has, why,
                         cn[0][:60] if cn else None))
                if ok and (best is None or len(strs) > len(best[2])):
                    best = (f, m.start(), strs, has)
            if tried > a.maxscan:
                break
        if best and best[3]:
            break
    if not best:
        print('\n没扫到「名字里含 %s 且 gcdata 结构自洽」的字节码块。' % a.name)
        print('可能原因：该表的字节码块里 chunk 名不带表名（被 strip），或块头不在 magic 上。')
        return 1
    f, off, strs, has = best
    print('\n=== 选定 %s @0x%x：%d 条字符串常量，canary %s ==='
          % (f[-26:], off, len(strs), '在' if has else '不在'))
    txt = [s for s in strs if any(0x80 <= c < 0xE0 or 0xE0 <= c for c in s)]
    cn = []
    for s in strs:
        try:
            t = s.decode('utf-8')
        except UnicodeDecodeError:
            continue
        if re.search(r'[一-鿿]', t):
            cn.append(t)
    print('其中含中文的 %d 条；前 20 条：' % len(cn))
    for t in cn[:20]:
        print('   ', t[:90])
    out = os.path.join(ROOT, '.diag', 'sharecfg_re', '%s_strings.txt' % a.name)
    with open(out, 'w', encoding='utf-8') as w:
        for idx, s in enumerate(strs):
            try:
                w.write('%d\t%s\n' % (idx, s.decode('utf-8')))
            except UnicodeDecodeError:
                w.write('%d\t<hex %s>\n' % (idx, s.hex()))
    print('\n全部字符串常量已写出：%s' % out)
    print('⚠️ 还没有做的一步：这些串的**顺序**不等于表里的 key 顺序；'
          '要拿到 (皮肤id -> 台词) 必须再走 proto 头 + BC 操作数。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
