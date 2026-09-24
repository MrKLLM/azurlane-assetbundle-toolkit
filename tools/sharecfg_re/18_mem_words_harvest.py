#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从内存快照里抽取台词候选，并尽量拼出完整的「文本#起始#结束」行。

参照物（本轮 adb 勘察捞到的真实明文）：`originsource/cipher/soundstory2_jp.txt` 的行格式是
    呼…海风真舒服…指挥官…#1#15
即 **文本 + '#' + 起始 + '#' + 结束**，且整行是**一个字符串**。
所以抽取分两种模式，且互相校验：

  A 整行模式：直接找 `文本#\d+#\d+` 形态的串。命中即"完整台词行"，归属只差皮肤 id。
  B GCstr 模式：找中文串，并回看它前面 8..48 字节处是否存在一个 uint32 == 该串长度、
    且串尾紧跟 NUL —— 满足才认它是**真正的 Lua 字符串对象**，而不是巧合字节序列。

⚠️ 为什么必须有 B 做校验：A 的 `#\d+#\d+` 在 2GB 随机内存里会撞出大量假阳性
   （颜色码、URL、其它表的时间字段都长这样）。上一轮"14058 次 #n#n"就是裸计数，
   没做结构校验，所以那个数字**不能当台词条数**。本脚本把"结构确认率"作为主判据。

判据：只有 **A 命中且 B 结构确认** 的条目才进候选表；其余单独报数为"未确认"，不混在一起。

用法: py -3 tools/sharecfg_re/18_mem_words_harvest.py [--min-chars 4] [--out ...]
"""
import argparse, collections, glob, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT_DIR = os.path.join(ROOT, '.diag', 'sharecfg_re', 'memdump')
CJK = rb'[\xe4-\xe9][\x80-\xbf]{2}'
RUN_RE = re.compile(rb'(?:' + CJK + rb'|[\x20-\x7e]){4,}')
# 锚点：`#起#止`。⚠️ 不用惰性量词写"文本#\d+#\d+"整行正则 —— 在 2GB 二进制上会灾难性回溯。
# 正确做法：先用这个快正则定位锚点，再从锚点**向左有界回扫**取文本（线性、且更准）。
ANCHOR_RE = re.compile(rb'#(\d{1,6})#(\d{1,6})')
TXT_RE = re.compile(rb'(?:' + CJK + rb'|[\x20-\x7e])+$')


def gcstr_confirmed(b, start, length):
    """回看 start 前 8..48 字节有没有一个 uint32 == length，且串尾是 NUL。"""
    if start + length >= len(b) or b[start + length] != 0:
        return False
    lo = max(0, start - 48)
    for k in range(start - 8, lo - 1, -4):
        if k < 0:
            break
        if int.from_bytes(b[k:k + 4], 'little') == length:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=OUT_DIR)
    ap.add_argument('--min-chars', type=int, default=4)
    ap.add_argument('--out', default=os.path.join(ROOT, '.diag', 'sharecfg_re', 'words_candidates.tsv'))
    ap.add_argument('--limit', type=int, default=0, help='只扫前 N 个区域（调试用）')
    a = ap.parse_args()
    fs = sorted(f for f in os.listdir(a.dir) if f.endswith('.bin'))
    if a.limit:
        fs = fs[:a.limit]
    print('%d 个区域文件' % len(fs))

    lines_ok, lines_raw, runs_ok = [], 0, 0
    n_run = n_conf = 0
    for f in fs:
        b = open(os.path.join(a.dir, f), 'rb').read()
        if len(b) < 4096:
            continue
        # A：整行 —— 先定位 #起#止 锚点，再向左有界回扫取文本
        for m in ANCHOR_RE.finditer(b):
            lo = max(0, m.start() - 240)
            tm = TXT_RE.search(b[lo:m.start()])
            if not tm:
                continue
            tstart = lo + tm.start()
            text = b[tstart:m.start()]
            if len(text) < a.min_chars * 3 or not re.search(CJK, text):
                continue
            s = text + m.group()
            lines_raw += 1
            if gcstr_confirmed(b, tstart, len(s)):
                lines_ok.append((f, hex(tstart), s))
        # B：GCstr 结构确认率（用来判断"我们能否信任读到的串"）
        for m in RUN_RE.finditer(b):
            s = m.group()
            if len(s) < a.min_chars * 3:
                continue
            n_run += 1
            if gcstr_confirmed(b, m.start(), len(s)):
                n_conf += 1
    print('\n=== 结构可信度 ===')
    print('中文/ASCII 连续串 %d 条，其中通过 GCstr 长度前缀+NUL 校验 %d 条（%.3f%%）'
          % (n_run, n_conf, 100.0 * n_conf / max(1, n_run)))
    print('\n=== 整行模式（文本#起#止）===')
    print('裸命中 %d 条；其中 GCstr 结构确认 %d 条' % (lines_raw, len(lines_ok)))
    uniq = collections.OrderedDict()
    for f, off, s in lines_ok:
        t = s.decode('utf-8', 'replace')
        uniq.setdefault(t, (f, off))
    print('去重后端到端确认的完整台词行：%d 条' % len(uniq))
    for t, (f, off) in list(uniq.items())[:25]:
        print('   %-58s  %s @%s' % (t[:58], f[-24:], off))
    with open(a.out, 'w', encoding='utf-8') as w:
        w.write('text\tregion\toffset\n')
        for t, (f, off) in uniq.items():
            w.write('%s\t%s\t%s\n' % (t.replace('\t', ' '), f, off))
    print('\n候选表已写出：%s' % a.out)
    if not uniq:
        print('判定：整行形态未成立 -> 台词的文本与 #起#止 在内存里是分开存的，'
              '需要改用「GCstr 数组邻接」重建行，或回到解析器路线')


if __name__ == '__main__':
    main()
