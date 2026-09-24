#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读进程内存取证：判定「解密后的配置 / Lua 解析器源码」能不能从运行中的游戏里直接拿到。

为什么需要它（2026-09-24）：密文侧已被逐条判死（见 README 的「追加排除的假设汇总」），
而盘上/设备上也没有解密缓存（后台 adb 勘察实测：进程 fd 直接指向 AssetBundles/sharecfgdata/）。
唯一还可能有明文的地点就是**进程内存**。本工具全程只读：只 `cat /proc/<pid>/maps` 和
`dd if=/proc/<pid>/mem`，不 push、不写设备、不 attach 调试器、不暂停进程。

⚠️ adb 引号坑（本轮踩过，别再踩）：`adb shell su -c pidof X` 会被设备 sh 拆成
   `su -c pidof` + `$0=X` → pidof 收不到参数，返回空。必须把整条命令**带引号当一个参数**传：
   `adb shell 'su -c "pidof X"'`。本工具统一用 sh() 传单个字符串，就是为了避开这个坑。

⚠️ 流式读取必须自检：`exec-out` 走的是文本通道的可能性存在（\\n→\\r\\n 改写会毁掉二进制）。
   所以 dump 阶段对每个区域**校验字节数**，hunt 阶段先拿一个"内容已知"的文件映射区
   （global-metadata.dat 的头部魔数 FAB11BAF）当**阳性对照**——对照不过就不许宣布任何命中。

用法:
  py -3 tools/sharecfg_re/16_mem_hunt.py maps                 # 枚举区域 + 总量
  py -3 tools/sharecfg_re/16_mem_hunt.py dump --anon          # 只拉匿名可写区（堆）
  py -3 tools/sharecfg_re/16_mem_hunt.py dump --all           # 全拉（约等于 RSS）
  py -3 tools/sharecfg_re/16_mem_hunt.py selftest             # 阳性对照：只验流是否无损
  py -3 tools/sharecfg_re/16_mem_hunt.py hunt                 # 本地扫明文/Lua 源码/字节码
"""
import argparse, hashlib, json, os, re, subprocess, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ADB = r"C:\Program Files\Netease\MuMuPlayer\nx_main\adb.exe"
SERIAL = "127.0.0.1:16384"
PKG = "com.bilibili.azurlane"
OUT = os.path.join(ROOT, '.diag', 'sharecfg_re', 'memdump')
LOG = os.path.join(ROOT, '.diag', 'sharecfg_re', 'memhunt.log')
AZ = os.path.join(ROOT, 'inputs', 'azdata', 'azdata_ship_skin_template.json')
MD_MAGIC = bytes.fromhex('af1bfab1')            # global-metadata.dat 的魔数（小端 FAB11BAF）
PAGE = 4096


def log(msg):
    line = '%s %s' % (__import__('datetime').datetime.now().strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def sh(cmd, binary=False, timeout=300):
    """整条命令当一个参数传给 adb shell，由设备侧 sh 解析引号（见文件头的坑）。"""
    p = subprocess.run([ADB, '-s', SERIAL, 'shell', cmd], capture_output=True, timeout=timeout)
    out = p.stdout if binary else p.stdout.decode('utf-8', 'replace').replace('\r\n', '\n')
    if p.returncode != 0:
        log('  !! 命令非零退出 %d: %s | stderr=%s' % (p.returncode, cmd[:90], p.stderr[:200]))
    return out


def pidof():
    s = sh('su -c "pidof %s"' % PKG).strip()
    return s.split()[0] if s else None


def maps(pid):
    txt = sh('su -c "cat /proc/%d/maps"' % pid)
    regs = []
    for ln in txt.splitlines():
        # 真实格式：start-end perms offset dev inode pathname  —— inode 必须单独吃掉，
        # 否则 pathname 组会拿到 inode（本轮就因此把所有区域都误判成匿名区）
        m = re.match(r'([0-9a-f]+)-([0-9a-f]+) (\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*(.*)', ln)
        if not m:
            continue
        a, b, perms, off, dev, inode, path = m.groups()
        regs.append({'start': int(a, 16), 'end': int(b, 16), 'perms': perms,
                     'off': int(off, 16), 'dev': dev, 'path': path.strip()})
    return regs


def readable(regs, anon_only=False, all_=False):
    out = []
    for r in regs:
        if 'r' not in r['perms']:
            continue
        isfile = bool(r['path']) and r['path'][0] == '/'
        if anon_only and isfile:
            continue
        if not all_ and not anon_only and isfile:
            continue
        out.append(r)
    return out


def shx(cmd, timeout=900):
    """二进制通道：必须走 exec-out。实测 `adb shell` 会把 \n 改写成 \r\n
    （请求 262144 字节拿回 266643），用 shell 传内存快照等于自己污染证据。"""
    p = subprocess.run([ADB, '-s', SERIAL, 'exec-out', cmd], capture_output=True, timeout=timeout)
    return p.stdout


def dump_region(pid, r):
    start, end = r['start'], r['end']
    pages = (end - start) // PAGE
    if pages <= 0:
        return None
    name = '%d_%016x_%016x.bin' % (pid, start, end)
    p = os.path.join(OUT, name)
    if os.path.exists(p) and os.path.getsize(p) == pages * PAGE:
        return p
    raw = shx('su -c "dd if=/proc/%d/mem bs=%d skip=%d count=%d 2>/dev/null"'
              % (pid, PAGE, start // PAGE, pages))
    # 自检 1：字节数必须整页对齐且等于期望（不等 = 被截断 / 被文本改写）
    if len(raw) != pages * PAGE:
        log('  !! %s 取回 %d 字节，期望 %d -> 判为不完整，丢弃' % (name, len(raw), pages * PAGE))
        return None
    with open(p, 'wb') as f:
        f.write(raw)
    return p


def selftest(pid, regs):
    """阳性对照：拿一个**本地已有**的文件映射区（off==0），把内存里读回来的前 4KB
    与本地文件逐字节比对。这比"看着像魔数"强得多——不等就说明通道在改字节。"""
    local = {'global-metadata': os.path.join(ROOT, 'files', 'il2cpp', 'Metadata', 'global-metadata.dat'),
             'libil2cpp': os.path.join(ROOT, 'files', 'il2cpp', 'libil2cpp.so')}
    for key, lp in local.items():
        if not os.path.exists(lp):
            continue
        cand = [r for r in regs if key in r['path'] and r['off'] == 0]
        if not cand:
            continue
        r = cand[0]
        got = dump_region(pid, {**r, 'end': r['start'] + PAGE})
        if not got:
            continue
        a = open(got, 'rb').read(PAGE)
        b = open(lp, 'rb').read(PAGE)
        ok = a == b
        log('对照：%s 内存前 %d 字节 vs 本地 %s -> %s'
            % (os.path.basename(r['path']), PAGE, os.path.basename(lp),
               'PASS（逐字节一致，通道无损）' if ok else 'FAIL（有字节被改，禁止宣布任何命中）'))
        if not ok:
            d = [i for i in range(PAGE) if a[i] != b[i]][:8]
            log('   首个差异位置 %s  内存=%s 本地=%s'
                % (d, a[:16].hex(' '), b[:16].hex(' ')))
        return ok
    log('!! 找不到可做阳性对照的区域（本地无对应文件 / 没有 off==0 的映射）')
    return False


def words(n=300):
    import json as J
    out = []

    def rec(o):
        if isinstance(o, dict):
            [rec(v) for v in o.values()]
        elif isinstance(o, list):
            [rec(v) for v in o]
        elif isinstance(o, str) and len(o) >= 3 and re.search(r'[一-鿿]', o):
            out.append(o)
    rec(J.load(open(AZ, encoding='utf-8')))
    return [w.encode('utf-8') for w in sorted(set(out))[:n]]


LUA_MARK = [b'function ', b'require(', b'ship_skin_words', b'ship_skin_template',
            b'LuaConfDataReader', b'ReadData', b'bit.bxor', b'string.char',
            b'\x1bLJ', b'\x1bLua', b'AssetBundles/sharecfgdata/']


def ctx(b, i, n=96):
    lo, hi = max(0, i - n), min(len(b), i + n)
    seg = b[lo:hi]
    return ''.join(chr(c) if 32 <= c < 127 else '.' for c in seg)


def hunt():
    """两趟扫：直接 300 词 × 1294 文件要几十分钟，先用少量高判别力标记过一遍 1.9GB
    定位候选区域，再在候选区域上跑全词表并打印上下文。"""
    fs = sorted(f for f in os.listdir(OUT) if f.endswith('.bin'))
    if not fs:
        log('memdump 目录是空的，先跑 dump')
        return
    W = words()
    triage = [b'ship_skin_words', b'ship_skin_template', b'AssetBundles/sharecfgdata/',
              b'LuaConfDataReader', b'ReadBufferFromCSharp', b'\x1bLJ', b'\x1bLua',
              b'function ', b'string.char', b'bit.bxor', b'scripts64', b'scripts32']
    log('趟 1：%d 个区域文件 / %.1f MB，只用 %d 个高判别力标记做初筛'
        % (len(fs), sum(os.path.getsize(os.path.join(OUT, f)) for f in fs) / 2**20, len(triage)))
    cands = []
    for f in fs:
        b = open(os.path.join(OUT, f), 'rb').read()
        mk = [(m, b.find(m)) for m in triage if m in b]
        cnt = {m: b.count(m) for m, _ in mk}
        if mk:
            cands.append((f, b, cnt))
            log('  %-46s %s' % (f, {m.decode('utf-8', 'replace')[:20]: c for m, c in cnt.items()}))
    log('趟 1 结论：%d / %d 个区域含标记' % (len(cands), len(fs)))
    if not cands:
        log('匿名区里没有任何配置/Lua 痕迹 -> 需要连文件映射区一起拉，或游戏当前场景没加载配置')
        return
    log('趟 2：在候选区域上跑 %d 个已知明文中文词 + 打印上下文' % len(W))
    for f, b, cnt in cands:
        cn = [w for w in W if w in b]
        log('== %s  大小 %.2f MB  中文命中 %d 个' % (f, len(b) / 2**20, len(cn)))
        for m, c in list(cnt.items())[:6]:
            i = b.find(m)
            log('   标记 %-26s 次数=%-6d 首个@0x%x  上下文: %s'
                % (m.decode('utf-8', 'replace'), c, i, ctx(b, i)))
        for w in cn[:8]:
            i = b.find(w)
            log('   中文 %s @0x%x  上下文: %s' % (w.decode('utf-8'), i, ctx(b, i)))
        if cn:
            log('   ==> 内存里存在解密后的中文配置文本，可按该区域还原表结构')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['maps', 'dump', 'selftest', 'hunt'])
    ap.add_argument('--anon', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--cap', type=int, default=0, help='最多拉多少 MB（0=不限）')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.cmd == 'hunt':
        hunt()
        return
    pid = pidof()
    if not pid:
        log('游戏进程没在跑（pidof 空）。需要你先在 MuMu 里把碧蓝航线启动进主界面。')
        return 1
    pid = int(pid)
    regs = maps(pid)
    log('pid=%d  区域 %d 个' % (pid, len(regs)))
    if a.cmd == 'maps':
        rd = [r for r in regs if 'r' in r['perms']]
        isf = lambda r: r['path'].startswith('/')
        tot = sum(r['end'] - r['start'] for r in rd)
        an = sum(r['end'] - r['start'] for r in rd if not isf(r))
        print('可读区域 %d 个 / 虚拟 %.1f MB；其中匿名(堆/栈/JIT) %d 个 / %.1f MB，'
              '文件映射 %d 个 / %.1f MB（文件映射多半本地已有，不必拉）'
              % (len(rd), tot / 2**20, sum(1 for r in rd if not isf(r)), an / 2**20,
                 sum(1 for r in rd if isf(r)), (tot - an) / 2**20))
        big = sorted(rd, key=lambda r: -(r['end'] - r['start']))
        print('最大的 12 个可读区域：')
        for r in big[:12]:
            print('  %012x-%012x %-4s %7.2f MB  %s'
                  % (r['start'], r['end'], r['perms'], (r['end'] - r['start']) / 2**20, r['path'][:60]))
        return
    if a.cmd == 'selftest':
        selftest(pid, regs)
        return
    sel = readable(regs, anon_only=a.anon, all_=a.all)
    sel.sort(key=lambda r: -(r['end'] - r['start']))
    want = sum(r['end'] - r['start'] for r in sel)
    log('候选 %d 个区域，共 %.1f MB' % (len(sel), want / 2**20))
    if not selftest(pid, regs):
        log('!! 阳性对照没过，停止 dump（读回来的字节不可信）')
        return 2
    done = 0
    for r in sel:
        if a.cap and done >= a.cap * 2**20:
            log('到达 --cap %dMB，停' % a.cap)
            break
        p = dump_region(pid, r)
        if p:
            done += os.path.getsize(p)
            log('  + %s (%.2f MB) 累计 %.1f MB' % (os.path.basename(p),
                                                   (r['end'] - r['start']) / 2**20, done / 2**20))
    log('dump 完成：%d 个区域 / %.1f MB 落到 %s' % (len(os.listdir(OUT)), done / 2**20, OUT))


if __name__ == '__main__':
    sys.exit(main() or 0)
