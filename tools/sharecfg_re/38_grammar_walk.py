#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定向解析诊断：从**已确认的锚点**（基准 JSON 里已知的那个键）开始，按字典头声明的条目数
一条条走，逐条打印「键 / 值 / 消费区间」。走到第几条崩、崩在哪个字节，就是封帧规则错在哪。

为什么不直接猜规则：数组/字典头有 4 种自洽写法（长度是 `uleb` 还是 `uleb-1`、有没有尾随 `00`），
人眼对齐字节太慢且容易看错；从已知锚点出发走一遍，错的写法会在**第一条**就崩，对的一路走到底。

用法:
  py -3 tools/sharecfg_re/38_grammar_walk.py ship_skin_template name
  py -3 tools/sharecfg_re/38_grammar_walk.py ship_skin_words hp_warning --rec 1
"""
import os, struct, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')


def unmask(seg):
    return bytes(x ^ ((255 - i) & 0xFF) for i, x in enumerate(seg))


def enc(s):
    b = s.encode('utf-8')
    return bytes([len(b) + 5]) + bytes(x ^ ((255 - i) & 0xFF) for i, x in enumerate(b))


class Stop(Exception):
    pass


class W:
    """读取器；log 记录每条键的区间，崩的时候能直接说出「读完第几个字段后错位」"""

    def __init__(self, buf, p, end):
        self.b = buf
        self.p = p
        self.e = end
        self.log = []

    def uleb(self, max_bytes=5):
        v = 0
        s = 0
        for i in range(max_bytes):
            if self.p + i >= self.e:
                raise Stop('EOF uleb @%d' % self.p)
            c = self.b[self.p + i]
            v |= (c & 0x7F) << s
            if not (c & 0x80):
                self.p += i + 1
                return v
            s += 7
        raise Stop('uleb too long @%d' % self.p)

    def value(self, depth=0):
        if depth > 12 or self.p >= self.e:
            raise Stop('depth/EOF @%d' % self.p)
        t = self.b[self.p]
        if t == 0x00:
            self.p += 1
            return None
        if t in (0x02, 0x03):
            self.p += 1
            v = self.uleb()
            return v - (1 << 32) if v & (1 << 31) else v
        if t == 0x04:
            self.p += 1
            lo = self.uleb()
            hi = self.uleb()
            return struct.unpack('<d', struct.pack('<II', lo & 0xFFFFFFFF, hi & 0xFFFFFFFF))[0]
        if t == 0x01:
            return self.table(depth)
        n = self.uleb(max_bytes=3) - 5
        if n < 0 or self.p + n > self.e:
            raise Stop('串长 %d 越界 @%d (raw=%02x %s)' % (n, self.p - 1, t, self.b[self.p - 1:self.p + 3].hex(' ')))
        raw = self.b[self.p:self.p + n]
        self.p += n
        return unmask(raw).decode('utf-8', 'replace') if n else ''

    def table(self, depth):
        p0 = self.p
        self.p += 1
        if self.b[self.p] == 0x00:                 # 数组
            self.p += 1
            c = self.uleb(max_bytes=3)
            form = 'arr?'
            if self.p < self.e and self.b[self.p] == 0x00:
                self.p += 1
                form = 'arrT'
            n = c - 1
            out = []
            for i in range(max(n, 0)):
                out.append(self.value(depth + 1))
            return ('ARR', form, p0, self.p, n, out)
        c = self.uleb(max_bytes=3)                 # 字典
        form = 'dict?'
        if self.p < self.e and self.b[self.p] == 0x00:
            self.p += 1
            form = 'dictT'
        d = {}
        for i in range(c):
            kp = self.p
            k = self.value(depth + 1)
            vp = self.p
            d[k] = self.value(depth + 1)
            self.log.append((p0, i, k, kp, vp, self.p, depth))
        return ('DICT', form, p0, self.p, c, d)


def find_dict(buf, key, start, stop):
    """找「键 key 紧跟在某个字典头 `01 <uleb n> [00]` 之后」的位置"""
    pat = enc(key)
    hits = []
    pos = start
    while True:
        i = buf.find(pat, pos, stop)
        if i < 0:
            break
        for h in range(max(0, i - 8), i - 1):      # 候选头起点
            if buf[h] != 0x01:
                continue
            k = h + 1
            v = 0
            sh = 0
            ok = False
            while k < i:
                c = buf[k]
                v |= (c & 0x7F) << sh
                k += 1
                if not (c & 0x80):
                    ok = True
                    break
                sh += 7
            if not ok or v > 600:
                continue
            if k == i or (k + 1 == i and buf[k] == 0x00):
                hits.append((h, v, i))
        pos = i + 1
    return hits


def main():
    a = sys.argv[1:]
    name = a[0]
    key = a[1]
    rec = int(a[a.index('--rec') + 1]) if '--rec' in a else 0
    buf = open(os.path.join(SRC, name), 'rb').read()
    pos = 0
    start = end = 0
    for _i in range(rec + 1):
        w = W(buf, pos, len(buf))
        total = w.uleb()
        start = pos
        end = w.p + total
        pos = end
    print('%s 记录 %d = [%d,%d)，用键 %r 定位行字典' % (name, rec + 1, start, end, key))
    hits = find_dict(buf, key, start, end)
    print('  候选字典头: %s' % [(h[0], h[1]) for h in hits])
    for (hp, n, kp) in hits:
        print('\n--- 从字典头 @%d (n=%d) 走 ---' % (hp, n))
        w = W(buf, hp, end)
        try:
            t = w.value()
        except Stop as e:
            print('  崩: %s   现场 @%d: %s' % (e, w.p, buf[max(0, w.p - 8):w.p + 16].hex(' ')))
            print('  崩前已读 %d 条键值：' % len(w.log))
            for (hp, i, k, kp, vp, ep, dp) in w.log[-14:]:
                print('     头@%-5d #%%-3d d=%d %-24s 键[%d,%d) 值[%d,%d)' % (hp, i, dp, repr(k)[:24], kp, vp, vp, ep))
            continue
        kind, form, p0, p1, cnt, data = t
        print('  %s %s 声明 %d 项，消费 [%d,%d)，实际取到 %d 个键' % (kind, form, cnt, p0, p1, len(data)))
        for k, v in list(data.items())[:60]:
            sv = repr(v)
            print('    %-22s %s' % (repr(k)[:22], sv[:78] + ('…' if len(sv) > 78 else '')))
        print('  头后紧跟: %r' % (buf[p1:p1 + 14],))
    return 0


if __name__ == '__main__':
    sys.exit(main())
