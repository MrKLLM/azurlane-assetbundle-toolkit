#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给一串明文，在 sharecfgdata（32 份磁盘表）与 sharecfg/*.bytes（774 份 Lua 侧）里定位它出现的位置。

为什么需要：挂着的待办基本都是"**某个名字到底存在哪张表**"（阵营名、声优名、新皮肤归属）。
既然字符串编码已定死（`ULEB(长+5)` + 逐字节 `^(255-i)`，i 每串归零），那"某个整串在不在某张表里"
就是一个**确定性搜索**，不需要再猜格式。
⚠️ 只能命中**整串**（长度字节紧挨着串首），子串命中不了 —— 所以探针要给完整词条，
   命中数 0 **不等于**"这个概念不在数据里"，只等于"不是以这个整串形态存在"。

用法:
  py -3 tools/sharecfg_re/39_find_string.py 晶环联盟 竹达彩奈 touch_body
  py -3 tools/sharecfg_re/39_find_string.py --ctx 8 --side both 泛用型布里
"""
import os, sys, glob

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DISK = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
LUA = os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_out')


def unmask(seg):
    return bytes(x ^ ((255 - i) & 0xFF) for i, x in enumerate(seg))


def tok(s, extra=0):
    """按已定死的规则把明文编成盘上字节；extra 用来试"游戏里拼了前后缀"的情形"""
    b = s.encode('utf-8')
    n = len(b) + 5 + extra
    out = bytearray()
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    out += bytes(x ^ ((255 - i) & 0xFF) for i, x in enumerate(b))
    return bytes(out)


def files(side):
    fs = []
    if side in ('both', 'disk'):
        fs += [(os.path.relpath(p, DISK), 'disk', p) for p in sorted(glob.glob(os.path.join(DISK, '*'))) if os.path.isfile(p)]
    if side in ('both', 'lua'):
        fs += [(os.path.basename(p)[:-6], 'lua', p) for p in sorted(glob.glob(os.path.join(LUA, '*.bytes')))
               if not p.endswith('_extra.bytes')]
    return fs


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    side = 'both'
    if '--side' in sys.argv:
        side = sys.argv[sys.argv.index('--side') + 1]
    show = int(sys.argv[sys.argv.index('--show') + 1]) if '--show' in sys.argv else 4
    probes = a or ['晶环联盟']
    fs = files(side)
    blobs = [(n, k, open(p, 'rb').read()) for (n, k, p) in fs]
    look = {(n, k): b for (n, k, b) in blobs}
    print('索引 %d 份文件 / 共 %.1f MB（disk=%d lua=%d）' %
          (len(blobs), sum(len(b) for _, _, b in blobs) / 1048576.0,
           sum(1 for _, k, _ in blobs if k == 'disk'), sum(1 for _, k, _ in blobs if k == 'lua')))
    for s in probes:
        pat = tok(s)
        hits = [(n, k, b.find(pat)) for (n, k, b) in blobs if b.find(pat) >= 0]
        cnt = [(n, k, b.count(pat)) for (n, k, b) in blobs if pat in b]
        print('\n=== %r  (盘上 %d 字节: %s)' % (s, len(pat), pat.hex(' ')))
        if not cnt:
            print('    0 命中  ⚠️ 只说明"不是以这个整串形态存在"，不等于概念不存在')
            continue
        for (n, k, c) in sorted(cnt, key=lambda x: -x[2])[:show]:
            b = look[(n, k)]
            i = b.find(pat)
            tail = unmask(b[i + len(pat): i + len(pat) + 24])
            print('    %-30s %-5s x%-4d 首现 @%-9d 后 24 字节解出 %r' %
                  (n, k, c, i, tail.decode('utf-8', 'replace')[:24]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
