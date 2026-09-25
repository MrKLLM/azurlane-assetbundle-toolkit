#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dump.cs 符号 → libil2cpp.so 机器码反汇编（sharecfgdata 逆向的关键工具）。

上一轮只有 metadata 里的**标识符**（XorShift64 / ctXor …），读不到方法体，
所有算法猜测只能在密文上做统计检验（全部失败）。本工具把 Il2CppDumper 的
`dump.cs`（每个方法带 RVA / Offset）与 `libil2cpp.so` 接起来，直接读真实指令，
并把 `.data` 里的字符串字面量 / 常量 blob 一并解出来。

实测前提（本轮查出，别再按 README 旧说法当 ARM 处理）：
  libil2cpp.so 是 **ELF64 / e_machine=0x3E(x86-64) / ET_SHARED** —— 来自 **x86 安卓模拟器
  （MuMu）** 的产物，不是 ARM64。本机 mingw objdump 只支持 x86 恰好对得上；
  函数起始地址**不 4 字节对齐**（0x...7A 这种），是 x86 变长指令的正常现象，不是"头被改过"。

顺带把 dump.cs 解析成 name→offset 索引（.diag/sharecfg_re/method_index.json，
136652 个方法），之后任何会话查方法体都不用再 grep 44MB 文本。

依赖：capstone（`py -3 -m pip install capstone`）。

用法：
  py -3 tools/sharecfg_re/08_disasm_method.py --list  LuaConfDataReader
  py -3 tools/sharecfg_re/08_disasm_method.py  "LuaConfDataReader..cctor"
  py -3 tools/sharecfg_re/08_disasm_method.py  "FileHelper.ReadBytes" --count 400 --no-stop
  py -3 tools/sharecfg_re/08_disasm_method.py  --find ReadCfg
  py -3 tools/sharecfg_re/08_disasm_method.py  --blob 0x7000000 64        # 裸字节（按 file offset）
  py -3 tools/sharecfg_re/08_disasm_method.py  --va 0x7123456 64          # 裸字节（按 vaddr）
"""
import argparse, json, mmap, os, re, struct, sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SO = os.path.join(ROOT, 'files', 'il2cpp', 'libil2cpp.so')
DUMPCS = os.path.join(ROOT, '.diag', 'sharecfg_re', 'dump', 'dump.cs')
IDX = os.path.join(ROOT, '.diag', 'sharecfg_re', 'method_index.json')

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
except ImportError:
    print('缺少 capstone：py -3 -m pip install capstone')
    sys.exit(2)

SHN_UNDEF, SHT_RELA, SHT_PROGBITS = 0, 4, 1
STT_FUNC = 2


# ---------------------------------------------------------------- ELF
class Elf:
    def __init__(self, path, want_relocs=False):
        self.fh = open(path, 'rb')
        self.data = mmap.mmap(self.fh.fileno(), 0, access=mmap.ACCESS_READ)
        if self.data[:4] != b'\x7fELF' or self.data[4] != 2:
            raise SystemExit('不是 ELF64')
        self.e_machine = struct.unpack_from('<H', self.data, 18)[0]
        e_phoff = struct.unpack_from('<Q', self.data, 0x20)[0]
        e_shoff = struct.unpack_from('<Q', self.data, 0x28)[0]
        e_phentsize, e_phnum = struct.unpack_from('<HH', self.data, 0x36)
        e_shentsize, e_shnum = struct.unpack_from('<HH', self.data, 0x3A)
        self.loads = []
        for i in range(e_phnum):
            # 必须带终点：mmap 切片不给上限会把 121MB 整个复制一遍（实测每条头 3~4s）
            p = self.data[e_phoff + i * e_phentsize:e_phoff + (i + 1) * e_phentsize]
            p_type, p_flags, p_offset, p_vaddr, _, p_filesz, p_memsz = \
                struct.unpack_from('<IIQQQQQ', p, 0)
            if p_type == 1:
                self.loads.append((p_vaddr, p_filesz, p_offset, p_flags))
        self.sections = {}
        strtab_off = 0
        shstrndx = struct.unpack_from('<H', self.data, 0x3E)[0]
        if shstrndx < e_shnum:
            sh = self.data[e_shoff + shstrndx * e_shentsize:
                           e_shoff + (shstrndx + 1) * e_shentsize]
            strtab_off = struct.unpack_from('<Q', sh, 0x18)[0]
        for i in range(e_shnum):
            sh = self.data[e_shoff + i * e_shentsize:e_shoff + (i + 1) * e_shentsize]
            sh_name, sh_type = struct.unpack_from('<II', sh, 0)
            sh_offset, sh_size = struct.unpack_from('<QQ', sh, 0x18)
            sh_addralign = struct.unpack_from('<Q', sh, 0x30)[0]
            nm = self.cstr(self.data, strtab_off + sh_name) if sh_name else ''
            self.sections[nm or 'sec%d' % i] = (sh_type, sh_offset, sh_size, sh_addralign)
        self._reloc_cache = None
        self.symbols = self._syms()

    @staticmethod
    def cstr(buf, off, maxlen=200):
        end = buf.find(b'\x00', off, off + maxlen)
        return buf[off:end].decode('utf-8', 'replace') if end > 0 else ''

    @property
    def relocs(self):
        """r_offset -> (r_info, r_addend)。70 万条，只在真要解引用 .data 指针时才解析。"""
        if self._reloc_cache is None:
            out = {}
            for nm, (sh_type, sh_offset, sh_size, _al) in self.sections.items():
                if sh_type != SHT_RELA:
                    continue
                buf = self.data[sh_offset:sh_offset + sh_size]
                for r_off, r_info, r_add in struct.iter_unpack('<QQq', buf):
                    out[r_off] = (r_info, r_add)
            self._reloc_cache = out
        return self._reloc_cache

    def _syms(self):
        """dynsym：addr -> name（用于给 call 目标标 dl 级符号名）。"""
        out = {}
        sym = self.sections.get('.dynsym')
        strn = self.sections.get('.dynstr')
        if not sym or not strn:
            return out
        base = strn[1]
        for i in range(sym[2] // 24):
            e = self.data[sym[1] + i * 24:sym[1] + (i + 1) * 24]
            st_name, st_info, _o, _s, st_value, st_size = struct.unpack_from('<IBBHQQ', e, 0)
            if (st_info & 0xF) == STT_FUNC and st_value:
                out[st_value] = self.cstr(self.data, base + st_name)
        return out

    def off2va(self, off):
        for va, fsz, fo, _f in self.loads:
            if fo <= off < fo + fsz:
                return va + (off - fo)
        return None

    def va2off(self, va):
        for v, fsz, fo, _f in self.loads:
            if v <= va < v + fsz:
                return fo + (va - v)
        return None

    def read(self, va, n):
        off = self.va2off(va)
        return b'' if off is None else self.data[off:off + n]

    # ---- 把一个 vaddr 处尽力解释成字符串（il2cpp 字面量 / C 串 / UTF-16）
    def as_string(self, va):
        # 两种字面量布局都试：{len,bom,chars[]} 与 {len,chars[]}
        raw = self.read(va, 8)
        if len(raw) == 8:
            ln = struct.unpack_from('<i', raw, 0)[0]
            for skip in (8, 4):
                if not (0 < ln < 4000):
                    break
                u = self.read(va + skip, ln * 2)
                if len(u) == ln * 2:
                    try:
                        s = u.decode('utf-16-le')
                    except Exception:
                        continue
                    if s and all(31 < ord(c) < 0xFFFF for c in s):
                        bom = struct.unpack_from('<i', raw, 4)[0] if skip == 8 else None
                        if skip == 4 or bom in (0, 0xFEFF, 1):
                            return ('lit', s[:120])
        # 直接 UTF-16LE C 串
        raw = self.read(va, 64)
        if len(raw) >= 6 and raw[1] == 0 and raw[3] == 0:
            s = raw.decode('utf-16-le', 'replace').split('\x00')[0]
            if len(s) >= 2 and all(31 <= ord(c) < 127 for c in s):
                return ('u16', s[:120])
        # ASCII C 串
        raw = self.read(va, 200)
        s = raw.split(b'\x00')[0]
        if len(s) >= 3 and all(32 <= c < 127 for c in s):
            return ('asc', s.decode('ascii')[:120])
        return (None, None)


# ---------------------------------------------------------------- dump.cs 索引
SIG = re.compile(r'^\s*(?:public|private|protected|internal|static|virtual|override|'
                 r'abstract|sealed|readonly|const|extern|unsafe|\[[^\]]*\]\s*)*'
                 r'[\w<>\[\],\.\?\s]+?\s+([\w\.<>]+)\s*\(')
RVA = re.compile(r'// RVA: (0x[0-9A-Fa-f\-]+) Offset: (0x[0-9A-Fa-f\-]+)'
                 r'(?: VA: (0x[0-9A-Fa-f\-]+))?(?: Slot: (\-?\d+))?')
CLS = re.compile(r'^\s*(?:public|private|internal|abstract|sealed|static|\s)*'
                 r'(?:class|struct|enum|interface)\s+([\w\.<>]+)')


def build_index():
    out, cls, img, pending = {}, None, '?', None
    with open(DUMPCS, encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.startswith('// Image:'):
                img = line.split(':', 1)[1].strip()
            elif line.startswith('public ') or line.startswith('internal ') \
                    or line.startswith('private '):
                m = CLS.match(line)
                if m:
                    cls = m.group(1)
                    continue
            if line.strip().startswith('// RVA:'):
                m = RVA.search(line)
                if m:
                    pending = m.groups()
                continue
            if pending and '{' in line:
                m = SIG.match(line)
                if m:
                    rva, off, va, slot = pending
                    key = '%s.%s' % (cls, m.group(1)) if cls else m.group(1)
                    k, i = key, 2
                    while k in out:
                        k, i = '%s#%d' % (key, i), i + 1
                    out[k] = {'rva': rva, 'offset': off, 'va': va, 'slot': slot,
                              'image': img, 'sig': line.strip().rstrip('{ ')}
                pending = None
    print('解析出方法 %d 个 -> %s' % (len(out), IDX))
    json.dump(out, open(IDX, 'w', encoding='utf-8'))
    return out


def load_index(force=False):
    if force or not os.path.exists(IDX):
        return build_index()
    return json.load(open(IDX, encoding='utf-8'))


# ---------------------------------------------------------------- 反汇编
def disasm(elf, offset, count, stop_at_ret, byname, verbose=True):
    va = elf.off2va(offset)
    if va is None:
        print('Offset 0x%X 不在任何 PT_LOAD 里' % offset)
        return []
    arch = (CS_ARCH_X86, CS_MODE_64) if elf.e_machine == 0x3E \
        else (CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    md = Cs(*arch)
    md.detail = True
    lines, nret = [], 0
    for ins in md.disasm(elf.data[offset:offset + count * 4], va):
        tail = ''
        if elf.e_machine == 0x3E:
            txt = ins.insn_detail().op_text if hasattr(ins, 'insn_detail') else ins.op_str
            m = re.search(r'\[rip \+ (0x[0-9a-f]+|-?0x[0-9a-f]+)\]', ins.op_str.lower()) \
                or re.search(r'rip \+ (0x[0-9a-f]+)', ins.op_str.lower())
            if m:
                tgt = ins.address + ins.size + int(m.group(1), 0)
                tail = '  ; data 0x%X' % tgt
                rel = elf.relocs.get(tgt)
                if rel:
                    tail += ' ->0x%X' % rel[1]
                kind, s = elf.as_string(tgt)
                if kind:
                    tail += '  %s"%s"' % (kind + ':', s)
                elif rel:
                    kind, s = elf.as_string(rel[1])
                    if kind:
                        tail += '  %s*:"%s"' % (kind, s)
            if ins.mnemonic in ('call', 'jmp') and ins.op_str.startswith('0x'):
                tgt = int(ins.op_str, 16)
                nm = byname.get(tgt) or elf.symbols.get(tgt)
                if nm:
                    tail = '  <%s>' % nm
        lines.append('  0x%08X  %-22s %-7s %-34s%s'
                     % (ins.address, ins.bytes.hex(' '), ins.mnemonic, ins.op_str, tail))
        if stop_at_ret and ins.mnemonic == 'ret':
            nret += 1
            if nret >= 1 and len(lines) >= 8:
                break
    return lines


def xref(elf, target):
    """谁 call/jmp 到这个 VA —— 全库扫 E8/E9 rel32。

    不做逐条反汇编：rel32 的期望值随指令地址变化，所以用 numpy 把所有 0xE8/0xE9
    位置一次性取出来，算 `va+i+5+rel32 == target`，比反汇编 13 万个方法快几个数量级。
    返回 [(指令 VA, 0xE8=call / 0xE9=jmp)]
    """
    import numpy as np
    hits = []
    for va, fsz, fo, flags in elf.loads:
        if not (flags & 1):                      # 只看可执行段
            continue
        arr = np.frombuffer(elf.data[fo:fo + fsz], dtype=np.uint8)
        cand = np.nonzero((arr == 0xE8) | (arr == 0xE9))[0]
        cand = cand[cand + 5 < len(arr)]
        if not len(cand):
            continue
        c64 = cand.astype(np.int64)
        w = (arr[cand + 1].astype(np.int64) | (arr[cand + 2].astype(np.int64) << 8)
             | (arr[cand + 3].astype(np.int64) << 16) | (arr[cand + 4].astype(np.int64) << 24))
        w = np.where(w >= (1 << 31), w - (1 << 32), w)
        pred = va + c64 + 5 + w
        for i in np.nonzero(pred == target)[0]:
            hits.append((int(va + cand[i]), int(arr[cand[i]])))
    return sorted(hits)


def xrefslot(elf, target):
    """谁用 rip 相对方式引用了这个**数据地址**（静态字段槽 / klass 槽 / InitializeArray 句柄槽）。

    `--xref` 只能找 call/jmp 目标，找不到"某个方法读取了哪个全局槽"——而那正是
    "同一把密钥/同一个静态数组还有谁在用"的唯一查法。
    编码约束：ModRM.mod=00 且 rm=101（rip+disp32、无 SIB）⇒ ModRM 低 3 位=5、高 2 位=0
    → 只可能取 {05,0d,15,1d,25,2d,35,3d}（reg 域 0..7，REX.B 会加到 reg 上不影响 rm）。
    disp32 在 ModRM 之后 4 字节，RIP 基准 = ModRM 地址 + 5。
    ⚠️ 这是**字节模式扫描**、不是完整反汇编，会有假阳性 → 结果里连同前一字节（opcode）一起给出，
       调用方按 opcode 过滤（8d=lea / 8b,89=a8..=mov / 3d=cmp ...）或直接 --at 回看上下文。
    返回 [(ModRM 所在 VA, 该字节, 前一字节 opcode)]
    """
    import numpy as np
    hits = []
    mods = np.array([0x05, 0x0d, 0x15, 0x1d, 0x25, 0x2d, 0x35, 0x3d], dtype=np.uint8)
    for va, fsz, fo, flags in elf.loads:
        if not (flags & 1):
            continue
        arr = np.frombuffer(elf.data[fo:fo + fsz], dtype=np.uint8)
        idxs = []
        for m in mods:
            c = np.nonzero(arr == m)[0]
            idxs.append(c)
        cand = np.sort(np.concatenate(idxs)) if idxs else np.array([], dtype=np.int64)
        cand = cand[(cand >= 1) & (cand + 5 < len(arr))]
        if not len(cand):
            continue
        c64 = cand.astype(np.int64)
        w = (arr[cand + 1].astype(np.int64) | (arr[cand + 2].astype(np.int64) << 8)
             | (arr[cand + 3].astype(np.int64) << 16) | (arr[cand + 4].astype(np.int64) << 24))
        w = np.where(w >= (1 << 31), w - (1 << 32), w)
        pred = va + c64 + 5 + w
        for i in np.nonzero(pred == np.int64(target))[0]:
            hits.append((int(va + cand[i]), int(arr[cand[i]]), int(arr[cand[i] - 1])))
    return sorted(hits)


def owner_of(sorted_vas, sorted_names, va):
    """按 VA 反查包含该地址的方法体。"""
    import bisect
    i = bisect.bisect_right(sorted_vas, va) - 1
    return sorted_names[i] if i >= 0 else '?'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('symbol', nargs='?')
    ap.add_argument('--list')
    ap.add_argument('--find')
    ap.add_argument('--xref', help='谁 call/jmp 到该方法（全库扫 E8/E9 rel32）')
    ap.add_argument('--xrefslot', help='谁 rip 相对引用到这个**数据 VA**（静态字段/klass/句柄槽的使用方）')
    ap.add_argument('--blob')
    ap.add_argument('--va')
    ap.add_argument('--at', help='按 VA 反汇编任意地址：il2cpp 内部调用（icxx_ thunk）在 dump.cs 里没有符号')
    ap.add_argument('--count', type=int, default=600)
    ap.add_argument('--no-stop', action='store_true')
    ap.add_argument('--rebuild-index', action='store_true')
    a = ap.parse_args()

    elf = Elf(SO)
    print('# e_machine=0x%X (%s)  PT_LOAD: %s'
          % (elf.e_machine, 'x86-64' if elf.e_machine == 0x3E else hex(elf.e_machine),
             '  '.join('va=0x%X/sz=0x%X/off=0x%X' % (v, f, o) for v, f, o, _ in elf.loads)))

    if a.blob or a.va:
        n = int(a.count)
        if a.blob:
            off = int(a.blob, 0)
            va = elf.off2va(off)
        else:
            va = int(a.va, 0)
            off = elf.va2off(va)
        print('file 0x%X  vaddr 0x%s' % (off, '%X' % va if va else '?'))
        b = elf.data[off:off + n]
        for i in range(0, len(b), 16):
            chunk = b[i:i + 16]
            print('  %08X  %-48s |%s|' % ((va or off) + i, chunk.hex(' '),
                                          ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)))
        kind, s = elf.as_string(va) if va else (None, None)
        if kind:
            print('  as %s: %r' % (kind, s))
        return

    idx = load_index(a.rebuild_index)
    byname = {}
    for k, v in idx.items():
        if v['va'] and v['va'] != '0x-1':
            byname[int(v['va'], 16)] = k

    if a.at:
        va = int(a.at, 0)
        off = elf.va2off(va)
        if off is None:
            print('VA 0x%X 不在任何 PT_LOAD 里' % va)
            return
        nm = byname.get(va) or elf.symbols.get(va)
        print('# --at VA=0x%X  file=0x%X  %s' % (va, off, ('<%s>' % nm) if nm else ''))
        for ln in disasm(elf, off, a.count, not a.no_stop, byname):
            print(ln)
        return

    if a.find:
        r = re.compile(a.find, re.I)
        hits = sorted(k for k in idx if r.search(k))
        print('%d 个匹配：' % len(hits))
        for h in hits[:150]:
            e = idx[h]
            print('  %-68s RVA=%-11s Offset=%-11s [%s]' % (h, e['rva'], e['offset'], e['image']))
        return

    if a.xref:
        t = a.xref if a.xref in idx else None
        if t is None:
            cand = [k for k in idx if re.search(
                re.escape(a.xref).replace('\\.', '.'), k, re.I)]
            if len(cand) != 1:
                print('%r 匹配 %d 个，请给得更精确：' % (a.xref, len(cand)))
                for c in sorted(cand)[:40]:
                    print('   ', c)
                return
            t = cand[0]
        e = idx[t]
        va = int(e['va'], 16) if e['va'] and e['va'] != '0x-1' else int(e['rva'], 16)
        sv = sorted(int(v['va'], 16) for v in idx.values()
                    if v['va'] and v['va'] != '0x-1')
        sn = {}
        for k, v in idx.items():
            if v['va'] and v['va'] != '0x-1':
                sn.setdefault(int(v['va'], 16), k)
        vas = sorted(sn)
        hits = xref(elf, va)
        print('# %s  VA=0x%X  ->  %d 处交叉引用' % (t, va, len(hits)))
        for addr, op in hits:
            print('  %s @0x%08X  宿主=%s' % ('call' if op == 0xE8 else 'jmp',
                                             addr, owner_of(vas, [sn[v] for v in vas], addr)))
        return

    if a.xrefslot:
        tv = int(a.xrefslot, 0)
        sn = {}
        for k, v in idx.items():
            if v['va'] and v['va'] != '0x-1':
                sn.setdefault(int(v['va'], 16), k)
        vas = sorted(sn)
        hits = xrefslot(elf, tv)
        print('# 数据 VA=0x%X  ->  %d 处 rip 相对引用（字节模式扫描，含假阳性；opcode 供过滤）'
              % (tv, len(hits)))
        for addr, m, op in hits:
            print('  @0x%08X  modrm=%02x opcode=%02x  宿主=%s'
                  % (addr, m, op, owner_of(vas, [sn[v] for v in vas], addr)))
        return

    if a.list:
        keys = [k for k in idx if k.startswith(a.list + '.')]
        print('%s：%d 个方法' % (a.list, len(keys)))
        for k in sorted(keys):
            print('  %-58s RVA=%-11s Offset=%s  %s' % (k, idx[k]['rva'], idx[k]['offset'], idx[k]['sig']))
        return

    if not a.symbol:
        ap.print_help()
        return
    target = a.symbol
    if target not in idx:
        r = re.compile(re.escape(target).replace('\\.', '.'), re.I)
        cand = [k for k in idx if r.search(k)]
        if len(cand) == 1:
            target = cand[0]
        else:
            print('未找到 %r（%d 个候选）' % (target, len(cand)))
            for c in sorted(cand)[:60]:
                print('   ', c, idx[c]['offset'])
            return
    e = idx[target]
    off = int(e['offset'], 16)
    print('# %s   RVA=%s Offset=%s VA=%s  [%s]' % (target, e['rva'], e['offset'], e['va'], e['image']))
    print('# sig: %s' % e['sig'])
    for ln in disasm(elf, off, a.count, not a.no_stop, byname):
        print(ln)


if __name__ == '__main__':
    main()
