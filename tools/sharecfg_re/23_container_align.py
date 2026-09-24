#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 (15) 的强推断：内存里 `1b 4c 4a 02 02` 开头的 blob，其表体是否与磁盘 sharecfgdata **逐字节相同**。

为什么必须先证这一条：如果相同 -> 「载荷被变换」前提作废，问题降级成
「读懂一个明文两段式格式（表体 + 独立字符串区）」，磁盘文件本身就能直接读；
如果不同 -> 说明内存里这份是**另一份数据**（例如已解压/已重排的运行时副本），
那磁盘文件的载荷仍是被动过手脚的，不能据此宣布"没加密"。
所以这一步是**闸门**，不过就不许往下盖楼。

做法（不靠猜字段含义，只用"长公共片段"这种硬事实）：
  1. 从内存区域里按 `1b 4c 4a` 切 blob；
  2. 每个 blob 取若干**中段窗口**（默认 64 字节，避开头部歧义），
     在全部 32 张磁盘表里 find；
  3. 报告：命中表名、磁盘偏移、以及**从 blob 起算能连续匹配多少字节**（这才是判据）；
  4. 反向也做一次：拿磁盘表的中段窗口去内存里找，确认对齐是双向的、不是单侧巧合。

判据：连续匹配 >= 64 字节 且 双向都成立 -> 判"表体明文同构"；否则判否并如实报。

用法: py -3 tools/sharecfg_re/23_container_align.py [--win 64] [--nblob 40]
"""
import argparse, collections, glob, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DUMP = os.path.join(ROOT, '.diag', 'sharecfg_re', 'memdump')
CFG = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
MAGIC = b'\x1bLJ\x02\x02'


def run_match(a, ai, b, bi, cap=1 << 20):
    """从 a[ai] 与 b[bi] 起能连续匹配多少字节。"""
    n = min(len(a) - ai, len(b) - bi, cap)
    k = 0
    while k < n and a[ai + k] == b[bi + k]:
        k += 1
    return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--win', type=int, default=64)
    ap.add_argument('--nblob', type=int, default=40)
    ap.add_argument('--dir', default=DUMP)
    a = ap.parse_args()
    disk = {os.path.basename(p): open(p, 'rb').read()
            for p in sorted(glob.glob(os.path.join(CFG, '*')))}
    print('磁盘表 %d 张，共 %.1f MB' % (len(disk), sum(len(v) for v in disk.values()) / 2**20))

    # 1) 收集内存 blob
    blobs = []
    for f in sorted(glob.glob(os.path.join(a.dir, '*.bin'))):
        b = open(f, 'rb').read()
        pos = [m.start() for m in re.finditer(re.escape(MAGIC), b)]
        if not pos:
            continue
        base = int(re.match(r'\d+_([0-9a-f]{16})', os.path.basename(f)).group(1), 16)
        for k, p in enumerate(pos[:a.nblob]):
            end = pos[k + 1] if k + 1 < len(pos) else min(len(b), p + 65536)
            if end - p > 256:
                blobs.append((os.path.basename(f), base + p, b[p:end]))
        if len(blobs) >= a.nblob * 6:
            break
    print('内存 blob 取 %d 个（magic=%s）' % (len(blobs), MAGIC.hex(' ')))

    # 2) 正向：blob 中段窗口 -> 磁盘
    best = []
    for name, va, blb in blobs:
        for off in (a.win, len(blb) // 2, max(a.win, len(blb) - a.win * 2)):
            w = blb[off:off + a.win]
            if len(w) < a.win:
                continue
            for dn, db in disk.items():
                di = db.find(w)
                if di >= 0:
                    run = run_match(blb, off, db, di)
                    best.append((run, name[-24:], hex(va), off, dn, di))
                    break
            else:
                continue
            break
    best.sort(key=lambda t: -t[0])
    print('\n=== 正向（内存 blob 中段 -> 磁盘表）连续匹配 top 8 ===')
    for run, f, va, off, dn, di in best[:8]:
        print('   连续 %5d 字节   blob %s@%s+%d   ->  %s @磁盘偏移 %d'
              % (run, f, va, off, dn, di))
    if not best:
        print('   （无命中）')

    # 3) 反向：磁盘表中段 -> 内存区域
    rev = []
    for dn, db in disk.items():
        for off in (64, len(db) // 3, len(db) // 2):
            w = db[off:off + a.win]
            if len(w) < a.win:
                continue
            for f in sorted(glob.glob(os.path.join(a.dir, '*.bin'))):
                b = open(f, 'rb').read()
                mi = b.find(w)
                if mi >= 0:
                    rev.append((run_match(db, off, b, mi), dn, off, os.path.basename(f)[-24:], mi))
                    break
            if rev and rev[-1][0] >= a.win:
                break
    rev.sort(key=lambda t: -t[0])
    print('\n=== 反向（磁盘表中段 -> 内存）连续匹配 top 6 ===')
    for run, dn, off, f, mi in rev[:6]:
        print('   连续 %5d 字节   %s @%d  ->  内存 %s +0x%x' % (run, dn, off, f, mi))
    if not rev:
        print('   （无命中）')

    fwd_ok = bool(best) and best[0][0] >= a.win
    rev_ok = bool(rev) and rev[0][0] >= a.win
    print('\n=== 闸门判定 ===')
    print('  正向 >=%d 字节连续匹配: %s' % (a.win, 'YES' if fwd_ok else 'no'))
    print('  反向 >=%d 字节连续匹配: %s' % (a.win, 'YES' if rev_ok else 'no'))
    if fwd_ok and rev_ok:
        print('  -> 判「表体明文同构」成立：内存里这份与磁盘文件是同一种明文格式，'
              '"载荷被变换"这个前提作废；台词文字在**独立的字符串区**，下一步对齐偏移字段。')
    else:
        print('  -> 判否：内存这份不是磁盘文件的同一形态（可能是运行时重排副本）。'
              '不得据此宣布"没加密"，回到载荷仍可疑的状态。')


if __name__ == '__main__':
    main()
