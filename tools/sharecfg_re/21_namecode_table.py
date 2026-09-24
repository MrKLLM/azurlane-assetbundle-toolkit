#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⚠️ 本脚本的标签位假设（bit40..43 = TYP_STRING）**未经验证，且已被 (13) 的实测否证**：
全快照没有任何 u64 在 8/16/24/28/32/40/48 头偏移上指向已知台词串 -> 台词不是逐条 GCstr。
因此本脚本的 ARRAY/HASH 命中不可当证据使用，保留仅为记录方法。原说明如下：

路 B：不靠邻近配对，直接把 {namecode:NNN} 用的那张「码 -> 中文名字」表从内存里扫出来。

依据（LuaJIT 2.1 / x64 的 TValue 编码，这是可机器校验的、不是猜的）：
  * GCobj 指针在 64 位 TValue 里是 `ptr | 标签位`，**标签在 bit40..43**，`TYP_STRING = 5`。
    → 判"这个 8 字节是不是指向字符串的指针"，看 `(v >> 40) & 0xF == 5`，指针 = v & 0xFFFFFFFFFFFF。
  * 数字是「双精度裸值」（dual number），没有标签位 → 小整数键形如 38.0 的 double。
  * hash 节点 TNode = TKey(16B) + TValue val(16B) = **32 字节**；数组部分是 TValue 序列，**步长 16**。

于是扫两种形态，各自都有自校验（假命中做不到）：
  A. hash 节点：连续多条 `[整数 double 键][tag=5 字符串指针]`，步长 32，键应落在 namecode 值域内。
  B. 数组部分：连续多条 tag=5 字符串指针，步长 16，读出的应是一长串同类名字。

外部裁判：`Output/ship_meta.json` 递归收集的已知名字集合；真表的命中率应该很高。

用法: py -3 tools/sharecfg_re/21_namecode_table.py [--min-nodes 6] [--dir ...]
"""
import argparse, collections, json, os, re, struct, sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DUMP = os.path.join(ROOT, '.diag', 'sharecfg_re', 'memdump')
META = os.path.join(ROOT, 'Output', 'ship_meta.json')
TAG_STR = 5
PTRMASK = (1 << 48) - 1


def known_names():
    s = set()
    try:
        walk = json.load(open(META, encoding='utf-8'))
    except Exception as e:
        print('ship_meta 读不到（%s）' % e)
        return s

    def rec(o):
        if isinstance(o, dict):
            [rec(v) for v in o.values()]
        elif isinstance(o, list):
            [rec(v) for v in o]
        elif isinstance(o, str) and 1 < len(o) <= 12 and re.fullmatch(r'[一-鿿·\w]+', o):
            s.add(o)
    rec(walk)
    return s


def is_str_tag(v):
    return ((v >> 40) & 0xF) == TAG_STR


def read_str(data, base_va, va, maxlen=120):
    """按 GCstr 结构尽力取内容：找不到可信长度就退回"直接当 UTF-8 读"。"""
    off = va - base_va
    if off < 0 or off + 4 > len(data):
        return None
    for hdr in (8, 12, 16, 20, 24, 4, 0):          # GCstr 头部各版本 len 字段偏移不同，逐个试
        if off - hdr - 4 < 0:
            continue
        ln = int.from_bytes(data[off - hdr - 4:off - hdr], 'little')
        if 1 <= ln <= maxlen:
            raw = data[off:off + ln]
            if len(raw) == ln and (off + ln >= len(data) or data[off + ln] == 0):
                try:
                    s = raw.decode('utf-8')
                except UnicodeDecodeError:
                    continue
                if re.search(r'[一-鿿]', s) or re.fullmatch(r'[\w ·\.\-]+', s):
                    return s
    raw = data[off:off + 60].split(b'\x00')[0]
    try:
        s = raw.decode('utf-8')
    except UnicodeDecodeError:
        return None
    return s if re.search(r'[一-鿿]', s) and len(s) >= 2 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=DUMP)
    ap.add_argument('--min-nodes', type=int, default=6)
    ap.add_argument('--codes', default='', help='限定键值域，逗号分隔（默认 1..20000）')
    a = ap.parse_args()
    KN = known_names()
    print('外部裁判集合 %d 个已知名字' % len(KN))
    fs = [f for f in sorted(os.listdir(a.dir)) if f.endswith('.bin')]
    hits_hash, hits_arr = [], []
    n_scan = 0
    for f in fs:
        path = os.path.join(a.dir, f)
        st = os.stat(path)
        if st.st_size < 64 * 1024:
            continue
        m = re.match(r'(\d+)_([0-9a-f]{16})_([0-9a-f]{16})\.bin', f)
        if not m:
            continue
        base = int(m.group(2), 16)
        data = open(path, 'rb').read()
        n_scan += 1
        n = len(data) // 8
        arr = np.frombuffer(data[:n * 8], dtype='<u8')
        tag = (arr >> 40) & 0xF
        isptr = tag == TAG_STR
        # 结构尺寸（LuaJIT 2.1 / x64）：TValue=8B、TKey=16B -> TNode=24B（3 个 u64）；
        # 数组部分是 TValue 序列 -> 步长 1 个 u64。
        ip = np.nonzero(isptr)[0]
        # ---- A. hash 节点：键是整数 double 在 u64 i，值指针在 u64 i+2，节点步长 3
        lim = max(0, n - 3)
        # ⚠️ 必须用 view 做**位重解释**：astype 会把整数「换算」成浮点，那样判据完全失真。
        kd = arr[:lim].view(np.float64)
        with np.errstate(invalid='ignore'):
            intok = np.isfinite(kd) & (kd > 0) & (kd < 20000) & (kd == np.floor(kd))
        intok &= (arr[:lim] >> 48) < 0x30          # 排除带 GC 标签位的值被当成 double
        vp = np.nonzero(intok)[0]
        vp = vp[(vp + 2 < n) & isptr[vp + 2]]
        if len(vp):
            run, start = 1, vp[0]
            for k in range(1, len(vp)):
                if vp[k] - vp[k - 1] == 3:
                    run += 1
                else:
                    if run >= a.min_nodes:
                        hits_hash.append((f, base + start * 8, run))
                    run, start = 1, vp[k]
            if run >= a.min_nodes:
                hits_hash.append((f, base + start * 8, run))
        # ---- B. 数组部分：连续 isptr，步长 1
        if len(ip):
            run, start = 1, ip[0]
            for k in range(1, len(ip)):
                if ip[k] - ip[k - 1] == 1:
                    run += 1
                else:
                    if run >= a.min_nodes:
                        hits_arr.append((f, base + start * 8, run))
                    run, start = 1, ip[k]
            if run >= a.min_nodes:
                hits_arr.append((f, base + start * 8, run))
    print('扫了 %d 个大区域；hash 节点表 %d 处、字符串数组表 %d 处'
          % (n_scan, len(hits_hash), len(hits_arr)))
    for tag_, lst in (('HASH', hits_hash), ('ARRAY', hits_arr)):
        lst.sort(key=lambda t: -t[2])
        for f, va, run in lst[:12]:
            m = re.match(r'(\d+)_([0-9a-f]{16})_', f)
            base = int(m.group(2), 16)
            data = open(os.path.join(a.dir, f), 'rb').read()
            stride, voff = (3, 2) if tag_ == 'HASH' else (1, 0)
            print('\n--- %s %s @0x%x 连续 %d 节点 ---' % (tag_, f[-26:], va, run))
            got = []
            for i in range(min(run, 10)):
                p = (va - base) // 8 + i * stride
                key = ''
                if tag_ == 'HASH':
                    try:
                        key = '%g ' % struct.unpack_from('<d', data, p * 8)[0]
                    except Exception:
                        pass
                q = p + voff          # HASH 节点的值指针在键之后 2 个 u64
                v = int.from_bytes(data[q * 8:q * 8 + 8], 'little')
                s = read_str(data, base, (v & PTRMASK)) if is_str_tag(v) else None
                got.append((key, s))
            for key, s in got:
                mark = '' if s is None else ('[已知]' if s in KN else '')
                print('    %-10s %s%s' % (key.strip(), s if s else '(读不出)', mark))
    if not hits_hash and not hits_arr:
        print('\n判定：当前快照里没扫到 >=%d 节点的表 -> 需要放宽标签假设或换 stride' % a.min_nodes)


if __name__ == '__main__':
    main()
