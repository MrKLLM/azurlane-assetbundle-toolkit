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

状态: 标量字段已通（ship_skin_words 2601 行、帧覆盖残差 0）；`--verify` **尚未达标**——
      嵌套字段(smoke/bound_bone/couple_encourage)的装配关系在假 BC 指令区，待解栈码，故 id 交集 0。
出处: 文法事实来自公开仓库 `Fernando2603/AzurLaneDataExtractor`（**无 LICENSE 文件、pyproject 亦无
      license 字段 ⇒ 不得 vendor 其源码**）；本文件是按其格式事实**自写**的实现，非改写其代码。
      结论与判据见 docs/TROUBLESHOOTING.md §33、docs/WORKFLOWS.md WF-20。
"""
import json, os, struct, sys, collections

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


def verify():
    _, rows, n, consumed, empty = load_table('ship_skin_template')
    print('帧覆盖: %d / %d B  残差 %d  空记录 %d' % (consumed, os.path.getsize(os.path.join(SRC,'ship_skin_template')), os.path.getsize(os.path.join(SRC,'ship_skin_template'))-consumed, empty))
    base = json.load(open(BASELINE, encoding='utf-8'))
    print('解析: 记录 %d 条 / 基准 %d 条' % (len(rows), len(base)))
    for k in list(rows)[:2]:
        print('  样本 %s -> %d 键 %s' % (k, len(rows[k]), list(rows[k])[:14]))
    inter = sorted(set(rows) & set(base), key=lambda x: int(x) if x.isdigit() else 0)
    print('id 交集 %d（仅我有 %d / 仅基准 %d）' %
          (len(inter), len(set(rows) - set(base)), len(set(base) - set(rows))))
    tot = collections.Counter()
    bad = collections.defaultdict(list)
    for rid in inter:
        mine, ref = rows[rid], base[rid]
        for k, want in ref.items():
            tot['field'] += 1
            if k not in mine:
                tot['missing'] += 1
                bad[k + '(缺字段)'].append(rid)
                continue
            got = mine[k]
            if norm(got) == norm(want):
                tot['ok'] += 1
            else:
                tot['diff'] += 1
                if len(bad[k]) < 3:
                    bad[k].append('%s: got=%r want=%r' % (rid, got, want))
    print('字段比对: 共 %d  一致 %d (%.2f%%)  不一致 %d  缺字段 %d' %
          (tot['field'], tot['ok'], 100.0 * tot['ok'] / max(1, tot['field']), tot['diff'], tot['missing']))
    print('\n不一致/缺字段 Top 15:')
    for k, v in sorted(bad.items(), key=lambda kv: -len(kv[1]))[:15]:
        print('  %-28s n=%-4d %s' % (k, len(v), v[0]))
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
    if '--kgc' in a:
        dump_kgc(a[a.index('--kgc') + 1], int(a[a.index('--n') + 1]) if '--n' in a else 3)
        return 0
    if '--trace' in a:
        trace(a[a.index('--trace') + 1])
        return 0
    if '--verify' in a:
        return 1 if verify() else 0
    os.makedirs(OUT, exist_ok=True)
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
