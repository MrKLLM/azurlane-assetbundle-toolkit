#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sharecfgdata 容器**文法**解析器（自研实现，零依赖）。

结论（2026-09-25 由第三方公开解析器 Fernando2603/AzurLaneDataExtractor 佐证后自建）：
  磁盘侧 `files/AssetBundles/sharecfgdata/<表>` 根本不是加密，而是「假 LuaJIT 头 + 自定义
  tag 序列化」，串与串之间是平铺的 (key, value)：
    记录帧   : ULEB(整条记录长) 起于记录首字节
    假 BC 头 : ULEB len / 跳 3 / ULEB(1B) upvalues / ULEB knum / ULEB kgc / ULEB 指令数
               -> 指令数*4 字节 -> upvalues*2 -> knum 个 ULEB  -> 之后才是常量区
    tag      : 00=nil  02=bool(true)  03=ULEB int(32 位回绕)  04=double(两个 ULEB 拼 <II)
               01 00 n 00=数组(n-1 项)  01 n 00=字典(n 对)   其余=字符串
    字符串   : ULEB(字节长+5) 然后逐字节 `c ^ (255-i)`，i 从 0 起、**每条串各自归零**
               所以 05 = 空串；ASCII 过掩码后恰好落在 0x80-0xBF —— 这就是二十轮来
               看到的「高字节游程」，也是 GB18030/UTF-8 直解必然失败的原因。

用法:
  py -3 tools/sharecfg_re/37_parse_sharecfgdata.py --trace ship_skin_words   # 头部逐字段走一遍
  py -3 tools/sharecfg_re/37_parse_sharecfgdata.py --kgc ship_skin_template  # 常量区平铺取证
  py -3 tools/sharecfg_re/37_parse_sharecfgdata.py --table ship_skin_words    # 单表 -> .diag 下 JSON
  py -3 tools/sharecfg_re/37_parse_sharecfgdata.py --verify                   # 与 azdata 基准逐字段比对
  py -3 tools/sharecfg_re/37_parse_sharecfgdata.py --all --yes                # 32 张表全量（需用户确认）
  py -3 tools/sharecfg_re/37_parse_sharecfgdata.py --entries ship_skin_words 1  # 判据：顶层条目数须==kgc 且末条停在记录末
  py -3 tools/sharecfg_re/37_parse_sharecfgdata.py --kgc ship_skin_template     # 常量区平铺取证（看结构被打散成什么样）
  py -3 tools/sharecfg_re/37_parse_sharecfgdata.py --scalar-all --yes           # 32 表「键定位+只接受标量」重导（与 --verify 同源）

状态(2026-09-25 B 段): 32/32 张表帧覆盖残差 0（140 MB / 220,568 条记录）；
      `--verify ship_skin_template` = 2863/2865 条 id 命中基准、**标量 138,669 对一致率 99.974%**
      （残差 36 处 = 381 快照 vs 385 设备内容差；另有 31.9% 字段对是「键不落盘=取默认值」）。
      **只剩 21 个容器字段名的值不内联**（占字段对 10.3%），装配关系在假 BC 指令区 → 待解栈码或人写字段表。
      注意 `01` 的位置语义：常量流顶层=表头，**值位=bool false**；`02` 在 bool 字段=true、在整数字段=varint。
出处: 文法事实来自公开仓库 `Fernando2603/AzurLaneDataExtractor`（**无 LICENSE 文件、pyproject 亦无
      license 字段 ⇒ 不得 vendor 其源码**）；本文件是按其格式事实**自写**的实现，非改写其代码。
      结论与判据见 docs/TROUBLESHOOTING.md §33、docs/WORKFLOWS.md WF-20。
"""
import json, os, re, struct, sys, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata')
OUT = os.path.join(ROOT, '.diag', 'sharecfg_re', 'cfg_json')
BASELINE = os.path.join(ROOT, 'inputs', 'azdata', 'azdata_ship_skin_template.json')


def unmask(seg):
    return bytes(x ^ ((255 - i) & 0xFF) for i, x in enumerate(seg))


class Cur(Exception):
    pass


class R:
    """按参考语义实现的读取器；position 相对 view 起点。"""

    def __init__(self, view, pos=0, end=None, strict=True):
        self.v = view
        self.p = pos
        self.e = len(view) if end is None else end

    def peek(self, n=1):
        return self.v[self.p:self.p + n]

    def seek(self, n):
        self.p = min(self.p + n, self.e)

    def take(self, n):
        if self.p + n > self.e:
            raise Cur('overrun: @%d +%d > end %d' % (self.p, n, self.e))
        out = self.v[self.p:self.p + n]
        self.p += n
        return out

    def uleb(self, max_bytes=10, signed=True):
        r = 0
        s = 0
        for i in range(max_bytes):
            if self.p >= self.e:
                raise Cur('EOF in uleb @%d' % self.p)
            b = self.v[self.p]
            self.p += 1
            r |= (b & 0x7F) << s
            if not (b & 0x80):
                if signed and (r & (1 << 31)):
                    r -= 1 << 32
                return r
            s += 7
        raise Cur('uleb too long @%d' % self.p)

    def string(self):
        n = self.uleb(max_bytes=2, signed=False) - 5
        if n < 0:
            raise Cur('string len field %d < 5 @%d' % (n + 5, self.p))
        if n == 0:
            return ''
        return unmask(self.take(n)).decode('utf-8', 'replace')

    def header(self):
        """假 LuaJIT 头 -> 返回 (常量区起点, 各字段)"""
        p0 = self.p
        f = {}
        f['rec_len'] = self.uleb()
        f['len_size'] = self.p - p0
        self.seek(3)                                   # FrameSize / <FrameSize+Flags> / Flags
        f['upvalues'] = self.uleb(max_bytes=1)
        f['knum'] = self.uleb()
        f['kgc'] = self.uleb()
        f['insn'] = self.uleb()
        self.seek(4 * f['insn'])
        self.seek(2 * f['upvalues'])
        for _ in range(f['knum']):
            self.uleb()
        return self.p, f, p0

    def table_header(self):
        """返回 (kind, n)：kind in ('arr','dict')；已在 0x01 上"""
        if self.peek(1) != b'\x01':
            raise Cur('expected table @%d got %r' % (self.p, self.peek(1)))
        if self.peek(2) == b'\x01\x00':                 # 数组
            self.take(2)
            n = self.uleb(max_bytes=2, signed=False) - 1
            self.take(1)
            return 'arr', n
        self.take(1)
        n = self.uleb(max_bytes=2, signed=False)
        self.take(1)
        return 'dict', n

    def value(self, depth=0):
        if depth > 12 or self.p >= self.e:
            raise Cur('too deep / EOF @%d' % self.p)
        t = self.peek(1)[0]
        if t == 0x00:
            self.seek(1)
            return None
        if t == 0x02:
            # 常量流里 02 与 03 同为整数（参考实现 read_constant 的口径）；
            # 把它们当 bool 会让整条流**下标走飞**（ship_skin_template 第一版就死在这）
            self.seek(1)
            return self.uleb()
        if t == 0x03:
            self.seek(1)
            return self.uleb()
        if t == 0x04:
            self.seek(1)
            lo = self.uleb(max_bytes=10, signed=False)
            hi = self.uleb(max_bytes=10, signed=False)
            return struct.unpack('<d', struct.pack('<II', lo & 0xFFFFFFFF, hi & 0xFFFFFFFF))[0]
        if t == 0x01:
            kind, n = self.table_header()
            if kind == 'arr':
                return [self.value(depth + 1) for _ in range(n)]
            d = {}
            for _ in range(n):
                k = self.string()
                d[k] = self.value(depth + 1)
            return d
        return self.string()


def parse_consts(buf, cpos, end):
    """常量区顶层（实测形态，非规范承诺）：
        [前置键 值]…（如 couple_encourage 的数组，存在行字典**之前**）
        [数组部分]  [行字典 01 n 00]  [环境尾巴: 'pg' '_G' <表名> 'base']
    规则：**DICT 一律当行字典，绝不把 DICT 当作某个 STR 的值**（实测这样两条记录都能取净）。
    """
    r = R(buf, cpos, end)
    row = {}
    arr = []
    tail = {}
    pending = None
    seen_dict = False
    while r.p < r.e - 1:
        tag = buf[r.p]
        try:
            if tag == 0x01:
                kind, n = r.table_header()
                if kind == 'arr':
                    v = [r.value() for _ in range(n)]
                    if pending is not None:
                        (tail if seen_dict else row)[pending] = v
                        pending = None
                    else:
                        arr.extend(v)
                else:
                    d = {r.string(): r.value() for _ in range(n)}
                    if not seen_dict:
                        row.update(d)
                        seen_dict = True
                    elif pending is not None:
                        tail[pending] = d
                        pending = None
                    else:
                        row.update(d)
                continue
            if tag in (0x00, 0x02, 0x03, 0x04):
                v = r.value()
                if pending is not None:
                    (tail if seen_dict else row)[pending] = v
                    pending = None
                else:
                    arr.append(v)
                continue
            s = r.string()
            if pending is None:
                pending = s
            else:
                (tail if seen_dict else row)[pending] = s
                pending = None
        except Cur:
            break
    if pending is not None:
        (tail if seen_dict else row)[pending] = None
    row = {k: v for k, v in row.items() if k}
    return row, arr, tail, r.p


def parse_record(buf, pos):
    """一条记录 -> (row, 下一条起点, 头字段)"""
    r = R(buf, pos)
    cpos, f, p0 = r.header()
    total = f['len_size'] + f['rec_len']
    end = min(len(buf), pos + total)
    row, arr, tail, stop = parse_consts(buf, cpos, end)
    if 'id' not in row and arr and isinstance(arr[0], int):
        row['id'] = arr[0]
    if arr:
        row['__array__'] = arr
    if tail:
        row['__env__'] = tail
    return row, f, pos + total, stop


# ---- 按「键定位 + 带类型读取」取一行的字段（参考实现同一条路，绕开 01 的歧义） --------
def enc_key(k):
    b = k.encode('utf-8')
    n = len(b) + 5
    out = bytearray()
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out) + bytes(x ^ ((255 - i) & 0xFF) for i, x in enumerate(b))


def read_typed(buf, p, end):
    """在 p 上读一个值。01 的歧义按位置解：能当成自洽容器就走容器，否则是 bool false。"""
    r = R(buf, p, end)
    t = buf[p]
    if t == 0x00:
        return None, p + 1
    if t == 0x02:
        r.seek(1)
        return r.uleb(), r.p
    if t == 0x03:
        r.seek(1)
        return r.uleb(), r.p
    if t == 0x04:
        r.seek(1)
        lo = r.uleb(max_bytes=10, signed=False)
        hi = r.uleb(max_bytes=10, signed=False)
        return struct.unpack('<d', struct.pack('<II', lo & 0xFFFFFFFF, hi & 0xFFFFFFFF))[0], r.p
    if t == 0x01:
        # 容器 or bool false：先按容器走，走不通就是 false
        try:
            v = r.value()
            return v, r.p
        except Cur:
            return False, p + 1
    try:
        v = r.string()
        return v, r.p
    except Cur:
        return None, p


def row_from_keys(buf, start, end, keys):
    """在一条记录的窗口里，按键名定位后读值。返回 (dict, 未命中的键)"""
    row = {}
    miss = []
    for k in keys:
        pat = enc_key(k)
        i = buf.find(pat, start, end)
        if i < 0:
            miss.append(k)
            continue
        j = i + len(pat)
        v, np_ = read_typed(buf, j, end)
        row[k] = v
    return row, miss


def iter_records(buf):
    pos = 0
    while pos < len(buf):
        try:
            r = R(buf, pos)
            _cl, f, _p = r.header()
        except Cur:
            return
        total = f['len_size'] + f['rec_len']
        if total <= 0:
            return
        yield pos, min(len(buf), pos + total), f
        pos += total


ENV_NOISE = {'base', '_G', 'pg', 'all', 'cs', '__name', '__stream__', '__namecode__', 'confNEO',
             'setmetatable', 'rawget', 'true', 'false', 'nil'}
IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_.]{1,40}$')


def key_vocab(buf, min_freq=2, min_frac=0.0, n_rec=0):
    """词表 = 全文里能按掩码解成「像标识符」的串，且出现次数 >= min_freq。
    字段名每张表出现 ~记录数 次，值串通常只出现几次，所以频次本身就是筛子。"""
    cand = collections.Counter()
    n_rec = 0
    n = len(buf)
    i = 0
    while i < n - 2:
        L = buf[i]
        if L < 0x80:
            k = L - 5
            if 1 <= k <= 40 and i + 1 + k <= n:
                t = unmask(buf[i + 1:i + 1 + k])
                if IDENT.rematch if False else all(32 <= c < 127 for c in t):
                    s2 = t.decode('ascii')
                    if IDENT.match(s2) and s2 not in ENV_NOISE:
                        cand[s2] += 1
                        i += 1 + k
                        continue
        i += 1
    # 字段键的定义性质：每条记录至多出现一次 => 频次带 [2% , 160%] x 记录数。
    # 短「标识符」(A2/AA) 是随机字节的假命中，用长度 >=3 + 频次带一起挡掉。
    floor = min_freq          # 下界放低：稀疏字段（如 bg，空值不落盘）也是真字段，不能按记录数比例砍
    ceil = max(min_freq * 4, int(1.6 * (n_rec or 0))) if n_rec else 10 ** 9
    return [k for k, c in cand.items() if floor <= c <= ceil], cand


def export_scalar(name, vocab=None, min_frac=0.15):
    """按「键定位 + 带类型读取」导出一张表：这是 verify 那条已被基准验证过的路。"""
    buf = open(os.path.join(SRC, name), 'rb').read()
    if vocab is None:
        nrec = sum(1 for _ in iter_records(buf))
        keys, cand = key_vocab(buf, min_frac=min_frac, n_rec=nrec)
    else:
        keys, cand = vocab
    keys = [k for k in keys if k != 'id']
    rows = {}
    noid = 0
    for (start, end, f) in iter_records(buf):
        pat = enc_key('id') + bytes([0x03])
        i = buf.find(pat, start, end)
        if i < 0:
            noid += 1
            rid = '#%d' % len(rows)
        else:
            rid = str(R(buf, i + len(pat), end).uleb())
        row = {}
        for k in keys:
            p2 = buf.find(enc_key(k), start, end)
            if p2 < 0:
                continue
            j = p2 + len(enc_key(k))
            try:
                v, np_ = read_typed(buf, j, end)
            except Cur:
                continue
            if np_ <= j:
                continue
            if isinstance(v, (list, dict)) and v and all(isinstance(x, (list, dict)) for x in v):
                continue                     # 只接受一层以内的值：更深的要靠指令装配
            row[k] = v
        if row:
            row.setdefault('id', rid if rid.isdigit() else None)
            rows[rid if rid not in rows else rid + '#' + str(len(rows))] = row
    return rows, keys, noid, cand


def kgc_list(buf, cpos, end):
    """把常量区读成**平铺的 kgc 流**（参考实现 read_constant 的口径），返回条目列表"""
    r = R(buf, cpos, end)
    out = []
    while r.p < r.e - 1:
        p = r.p
        try:
            out.append((p, r.value()))
        except Cur as e:
            out.append((p, '<<stop: %s>>' % e))
            break
    return out, r.p


# ---- 带回溯的封帧求解器：用「顶层条目数 == kgc 且 终点 == 记录末」当唯一判据 -------------
CANDS = ('nil', 'i3', 'i2', 'f64', 'str', 'arr4', 'arr3', 'dict4', 'dict3')


def cands(buf, p, end, depth=0):
    """位置 p 上所有**在字节上可行**的读法，返回 (newpos, label, value)"""
    out = []
    if p >= end:
        return out
    t = buf[p]
    if t == 0x00:
        out.append((p + 1, 'nil', None))
    r = R(buf, p, end)
    for tag in (('i3', 0x03), ('i2', 0x02)):
        if t == tag[1]:
            try:
                r2 = R(buf, p + 1, end)
                v = r2.uleb()
                out.append((r2.p, tag[0], v))
            except Cur:
                pass
    if t == 0x04:
        try:
            r2 = R(buf, p + 1, end)
            lo = r2.uleb(max_bytes=10, signed=False)
            hi = r2.uleb(max_bytes=10, signed=False)
            out.append((r2.p, 'f64', struct.unpack('<d', struct.pack('<II', lo & 0xFFFFFFFF, hi & 0xFFFFFFFF))[0]))
        except Cur:
            pass
    # 字符串（tag 不在已知集合里，或长度自洽）
    if t not in (0x00, 0x01):
        try:
            r2 = R(buf, p, end)
            n = r2.uleb(max_bytes=3, signed=False) - 5
            if 0 <= n <= (end - r2.p) and (depth or all(0x20 <= c < 0x80 or c >= 0x80 for c in buf[r2.p:r2.p + n])):
                out.append((r2.p + n, 'str', unmask(buf[r2.p:r2.p + n]).decode('utf-8', 'replace')))
        except Cur:
            pass
    if depth < 10 and t == 0x01:
        for (lab, hdr) in (('arr4', 2), ('arr3', 2), ('dict4', 1), ('dict3', 1)):
            q = p + 1
            try:
                rr = R(buf, q, end)
                if lab.startswith('arr'):
                    if rr.peek(1) != bytes([0]):
                        continue
                    rr.seek(1)
                c = rr.uleb(max_bytes=3, signed=False)
                n = c - 1
                skip = lab in ('arr4', 'dict4')
                if skip:
                    if rr.peek(1) != bytes([0]):
                        continue
                    rr.seek(1)
                if n < 0 or n > 4000:
                    continue
                items = []
                ok = True
                for _ in range(n):
                    sub = cands(buf, rr.p, end, depth + 1)
                    if not sub:
                        ok = False
                        break
                    # 取第一个可行读法进子树；顶层冲突交给外层回溯
                    items.append(sub[0])
                    rr.p = sub[0][0]
                if ok:
                    val = items if lab.startswith('arr') else {items[i][2]: items[i + 1][2] for i in range(0, len(items) - 1, 2)}
                    out.append((rr.p, lab, val))
            except Cur:
                pass
    return out


def solve(buf, cpos, end, kgc, budget=[3000000]):
    """DFS：找一条「正好 kgc 条、正好停在 end」的顶层切分"""
    memo = {}

    def walk(p, n):
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        if n == kgc:
            return [] if p == end else None
        if (p, n) in memo:
            return memo[(p, n)]
        for (np_, lab, v) in cands(buf, p, end):
            r = walk(np_, n + 1)
            if r is not None:
                memo[(p, n)] = [(p, np_, lab, v)] + r
                return memo[(p, n)]
        memo[(p, n)] = None
        return None

    return walk(cpos, 0)


def solve_table(name, rec=0):
    buf = open(os.path.join(SRC, name), 'rb').read()
    pos = 0
    for i in range(rec + 1):
        r = R(buf, pos)
        cpos, f, _ = r.header()
        end = pos + f['len_size'] + f['rec_len']
        pos = end
    print('%s 记录 %d [%d,%d) kgc=%d insn=%d 常量区@%d' % (name, rec + 1, end - f['len_size'] - f['rec_len'], end, f['kgc'], f['insn'], cpos))
    # 起点本身也是未知量：把「跳几个字节才算常量区」一起扫（knum 区的宽度规则我们没证实过）
    base = 9 + 4 * f['insn'] + 2 * f['upvalues']
    sols = {}
    for st in range(base - 2, base + 14):
        r = R(buf, max(0, st), end)
        try:
            for _ in range(f['knum']):
                r.uleb()
        except Cur:
            continue
        sol = solve(buf, r.p, end, f['kgc'], budget=[400000])
        if sol is not None:
            sols[r.p] = sol
            print('  常量区起点 @%d 有解（原公式给 @%d）' % (r.p, cpos))
            break
    sol = next(iter(sols.values()), None)
    if sol is None:
        print('  无解（预算内找不到「恰好 kgc 条并停在记录末」的切分）')
        return
    from collections import Counter
    print('  有解，读法分布:', dict(Counter(x[2] for x in sol)))
    for (a, b, lab, v) in sol:
        sv = repr(v)
        print('    @%-6d->%-6d %-6s %s' % (a, b, lab, sv[:92] + ('…' if len(sv) > 92 else '')))


def strict_entries(name, rec=0, show=40):
    """判据：常量区顶层**条目数必须等于头里的 kgc**，且最后一条必须正好停在记录末尾。
    这条不含任何主观阈值，能把我方解码偏差定位到具体第几条、哪段字节。"""
    buf = open(os.path.join(SRC, name), 'rb').read()
    pos = 0
    for i in range(rec + 1):
        r = R(buf, pos)
        cpos, f, _ = r.header()
        end = pos + f['len_size'] + f['rec_len']
        pos = end
    r = R(buf, pos)
    cpos, f, _ = r.header()
    end = min(len(buf), pos + f['len_size'] + f['rec_len'])
    print('%s 记录 %d [%d,%d) knum=%d kgc=%d insn=%d 常量区@%d' %
          (name, rec + 1, pos, end, f['knum'], f['kgc'], f['insn'], cpos))
    rr = R(buf, cpos, end)
    n = 0
    while rr.p < end:
        p0 = rr.p
        try:
            v = rr.value()
        except Cur as e:
            print('  #%02d @%-5d STOP: %s   原始=%s' % (n, p0, e, buf[p0:p0 + 12].hex(' ')))
            break
        n += 1
        sv = repr(v)
        if n <= show:
            print('  #%02d @%-5d->%-5d %-7s %s' % (n, p0, rr.p, type(v).__name__, sv[:96] + ('…' if len(sv) > 96 else '')))
    print('  条目数 %d  vs kgc %d  ->  %s   | 停在 @%d vs 记录末 @%d -> %s' %
          (n, f['kgc'], 'OK' if n == f['kgc'] else '不吻合', rr.p, end, 'OK' if rr.p == end else '不吻合'))


def dump_kgc(name, records=3):
    buf = open(os.path.join(SRC, name), 'rb').read()
    r = R(buf, 0)
    cpos, f, p0 = r.header()
    pos = 0
    for i in range(records):
        rr = R(buf, pos)
        c, f, _ = rr.header()
        items, stop = kgc_list(buf, c, pos + f['len_size'] + f['rec_len'])
        print('--- 记录 %d  [%d,%d) knum=%d kgc=%d insn=%d 常量区@%d 走到@%d' %
              (i + 1, pos, pos + f['len_size'] + f['rec_len'], f['knum'], f['kgc'], f['insn'], c, stop))
        for p, v in items:
            sv = repr(v)
            print('    @%-6d %-6s %s' % (p, type(v).__name__, sv[:110] + ('…' if len(sv) > 110 else '')))
        pos += f['len_size'] + f['rec_len']
        if pos >= len(buf):
            break


def load_table(name):
    buf = open(os.path.join(SRC, name), 'rb').read()
    rows = {}
    pos = 0
    n = 0
    empty = 0
    while pos < len(buf):
        try:
            row, f, nxt, stop = parse_record(buf, pos)
        except Cur:
            break
        n += 1
        if not row:
            empty += 1
        pid = row.get('id')
        key = str(pid) if pid is not None else '#%d' % n
        if key in rows:
            key = '%s#%d' % (key, n)
        rows[key] = row
        if nxt <= pos:
            break
        pos = nxt
    # 自证：记录长度必须把文件**正好吃完**（残差 = 帧模型错的直接证据，不看统计量）
    return buf, rows, n, pos, empty


def trace(name):
    buf = open(os.path.join(SRC, name), 'rb').read()
    r = R(buf, 0)
    cpos, f, p0 = r.header()
    print('%s  文件 %d B' % (name, len(buf)))
    print('  假 BC 头: rec_len=%d upvalues=%d knum=%d kgc=%d insn=%d -> 常量区 @%d'
          % (f['rec_len'], f['upvalues'], f['knum'], f['kgc'], f['insn'], cpos))
    print('  头前 12 字节: %s' % buf[:12].hex(' '))
    print('  常量区前 48 字节: %s' % buf[cpos:cpos + 48].hex(' '))
    row, arr, tail, stop = parse_consts(buf, cpos, cpos + f['rec_len'])
    print('  顶层取到: 数组部分 %r' % (arr,))
    print('           行字典 %d 键: %s' % (len(row), list(row)[:12]))
    print('           环境尾巴 %r' % (tail,))
    print('           消费到 @%d（记录末 @%d）' % (stop, cpos + f['rec_len']))


def verify(table='ship_skin_template', baseline=None, deep=0):
    """验收 = 逐条记录按键定位取值，再与基准逐字段比。
    容器字段单独统计（那 5 个才需要指令装配），不与标量混在一个百分比里糊过去。"""
    path = baseline or BASELINE
    base = json.load(open(path, encoding='utf-8'))
    keys = sorted({k for v in base.values() for k in v})
    # 按“基准里从没当过容器”的算标量；其余每条记录看它自己的实际类型（同一字段不同记录类型可以不同）
    scal = [k for k in keys if all(not isinstance(v.get(k), (list, dict)) for v in base.values() if k in v)]
    cont = [k for k in keys if k not in scal]
    buf = open(os.path.join(SRC, table), 'rb').read()
    tot = collections.Counter()
    bad = collections.defaultdict(list)
    matched = 0
    recs = list(iter_records(buf))
    if deep:
        recs = recs[:deep]
    for (start, end, f) in recs:
        pat = enc_key('id') + bytes([0x03])
        i = buf.find(pat, start, end)
        if i < 0:
            tot['no_id'] += 1
            continue
        _rv = R(buf, i + len(pat), end)      # pat 已含 03 标签，这里直接读 varint
        rid = str(_rv.uleb())
        ref = base.get(rid)
        if ref is None:
            tot['不在基准'] += 1
            continue
        matched += 1
        row, miss = row_from_keys(buf, start, end, scal)
        for k in miss:
            tot['missing'] += 1
            bad[k + '(键未找到)'].append(rid)
        for k, want in ref.items():
            bucket = 'cfield' if isinstance(want, (list, dict)) else 'field'
            if isinstance(want, (list, dict)):
                # 容器字段也照读：实测嵌套值就内联在行字典里（`01 00 04 00 …` = [0,0,0]）
                row.update(row_from_keys(buf, start, end, [k])[0])
            tot[bucket] += 1
            if k not in row:
                if isinstance(want, (list, dict)):
                    tot['cmiss'] += 1
                    bad[k + '(容器缺)'].append('%s want=%r' % (rid, want))
                elif norm(want) in ('', 0, None, False):
                    tot['default'] += 1
                else:
                    tot['missing'] += 1
                    bad[k + '(缺)'].append('%s want=%r' % (rid, want))
                continue
            got = row[k]
            if isinstance(want, bool) and isinstance(got, int):
                got = (got != 0)          # 02 在「声明为 bool 的字段」上是 true，不是整数 2
            if norm(got) == norm(want):
                tot['cok' if bucket == 'cfield' else 'ok'] += 1
            else:
                tot['cdiff' if bucket == 'cfield' else 'diff'] += 1
                if len(bad[k]) < 3:
                    bad[k].append('%s: got=%r want=%r' % (rid, got, want))
    print('%s: 记录 %d 条，命中基准 %d 条（无 id %d / 不在基准 %d）' %
          (table, len(recs), matched, tot['no_id'], tot['不在基准']))
    print('标量字段比对: 基准可比 %d  直接一致 %d  +键缺失取默认 %d  不一致 %d  真缺 %d' %
          (tot['field'], tot['ok'], tot['default'], tot['diff'], tot['missing']))
    acc = (tot['ok'] + tot['default']) / max(1, tot['field'])
    print('标量字段一致率 = %.3f%%（含默认值约定；不含默认值 %.3f%%）' %
          (100 * acc, 100.0 * tot['ok'] / max(1, tot['field'])))
    print('容器字段（需指令装配，本轮不计入分母）: %s' % cont)
    print('容器字段比对: 共 %d  一致 %d  不一致 %d  真缺 %d' %
          (tot['cfield'], tot['cok'], tot['cdiff'], tot['cmiss']))
    for kk in ('cok', 'cdiff', 'cmiss'):
        pass
    if bad:
        print()
        print('不一致 / 未找到 Top 12:')
        for k, v in sorted(bad.items(), key=lambda kv: -len(kv[1]))[:12]:
            print('  %-26s n=%-4d %s' % (k, len(v), v[0]))
    return tot['diff'] + tot['missing']


def norm(x):
    """把 bool/int、1.0/1、空串/None 这类表示差异归一，避免把「同一值的两种写法」记成不一致"""
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, float) and x == int(x):
        return int(x)
    if x is None:
        return ''
    if isinstance(x, list):
        return [norm(i) for i in x]
    if isinstance(x, dict):
        return {k: norm(v) for k, v in sorted(x.items())}
    return x


def main():
    a = sys.argv[1:]
    if '--solve' in a:
        rest = a[a.index('--solve') + 1:]
        solve_table(rest[0], int(rest[1]) if len(rest) > 1 else 0)
        return 0
    if '--entries' in a:
        rest = a[a.index('--entries') + 1:]
        strict_entries(rest[0], int(rest[1]) if len(rest) > 1 else 0)
        return 0
    if '--kgc' in a:
        dump_kgc(a[a.index('--kgc') + 1], int(a[a.index('--n') + 1]) if '--n' in a else 3)
        return 0
    if '--trace' in a:
        trace(a[a.index('--trace') + 1])
        return 0
    if '--verify' in a:
        t = a[a.index('--verify') + 1] if len(a) > a.index('--verify') + 1 and not a[a.index('--verify') + 1].startswith('--') else 'ship_skin_template'
        d = int(a[a.index('--deep') + 1]) if '--deep' in a else 0
        return 1 if verify(t, deep=d) else 0
    os.makedirs(OUT, exist_ok=True)
    if '--scalar-all' in a:
        if '--yes' not in a:
            print('--scalar-all 是 32 文件批量，须显式加 --yes（AGENTS 全量闸门）')
            return 2
        out2 = OUT + '_scalar'
        os.makedirs(out2, exist_ok=True)
        for nm in sorted(os.listdir(SRC)):
            rows, keys, noid, cand = export_scalar(nm)
            cjk = sum(1 for r in rows.values() if any(isinstance(v, str) and any('一' <= c <= '鿿' for c in v) for v in r.values()))
            with open(os.path.join(out2, nm + '.json'), 'w', encoding='utf-8') as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=1, sort_keys=True)
            print('%-28s 记录 %-6d 词表 %-4d 有值字段中位 %-3d 含中文行 %-6d 无id %d' %
                  (nm, len(rows), len(keys),
                   (sorted((len(r) for r in rows.values()))[len(rows) // 2] if rows else 0), cjk, noid))
        return 0
    if '--all' in a:
        if '--yes' not in a:
            print('--all 是 32 文件批量，须显式加 --yes（AGENTS 全量闸门）')
            return 2
        names = sorted(os.listdir(SRC))
    else:
        names = [a[a.index('--table') + 1]] if '--table' in a else ['ship_skin_words']
    for nm in names:
        buf, rows, n, consumed, empty = load_table(nm)
        p = os.path.join(OUT, nm + '.json')
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=1, sort_keys=True)
        hi = sum(1 for x in buf if x >= 0x80)
        cjk = sum(1 for v in rows.values() for s in v.values()
                  if isinstance(s, str) and any('一' <= c <= '鿿' for c in s))
        print('%-28s 记录 %-6d 帧覆盖 %d/%d 残差 %-5d 空记录 %-4d 含中文值 %-6d -> %s'
              % (nm, len(rows), consumed, len(buf), len(buf) - consumed, empty, cjk, os.path.relpath(p, ROOT)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
