#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查明 {namecode:NNN} 的对应关系——重点找「模板」与「已解析成品」是否同时驻留内存。

背景（18 号实测）：台词/描述文本里带的是 `{namecode:NNN}` 占位符，不含皮肤 id。
而形如 `{namecode:38}级轻巡洋舰——{namecode:306}` 的串，模式是
    {阵营名}级{舰种}——{舰名}
→ **38 这类码很可能就是 §6 待办 7 卡住的阵营码**（现有 nationality 表只到 115，
   且 96/97/98 是特殊段；38/75/134/143/181/306 明显不在这套编号里，说明 namecode 是
   **另一张"码→名字"表的索引**，不是 nationality）。

判据（一击得手的形状）：取模板里**不含占位符的那段固定文字**（如 `级轻巡洋舰——`）当锚，
把内存里所有命中处按"是否仍含 {namecode" 分成两类：
  * 模板类：`{namecode:38}级轻巡洋舰——{namecode:306}`
  * 成品类：`东煌级轻巡洋舰——逸仙`        ← 若存在，则同一条模板的占位符已被替换
只要**同一锚的成品类**能凑出若干条，就能用"模板位置 ↔ 成品位置"的对应
（同一行、同一顺序）反解出 N→名字。**这一步不成立就说明游戏没在内存里留下成品**，
那 namecode 只能从表本身解，须回解析器路线。

用法: py -3 tools/sharecfg_re/19_namecode_probe.py [--anchor 级轻巡洋舰——]
"""
import argparse, collections, glob, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT_DIR = os.path.join(ROOT, '.diag', 'sharecfg_re', 'memdump')
NC = re.compile(r'\{namecode:(\d+)\}')
NC_B = re.compile(rb'\{namecode:(\d+)\}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=OUT_DIR)
    ap.add_argument('--anchor', default='级轻巡洋舰——')
    ap.add_argument('--win', type=int, default=90, help='锚点两侧取多少字节')
    a = ap.parse_args()
    fs = [f for f in sorted(os.listdir(a.dir)) if f.endswith('.bin')]
    ids = collections.Counter()
    tmpl, done = [], []
    anchor = a.anchor.encode('utf-8')
    print('%d 个区域；锚=%r' % (len(fs), a.anchor))
    for f in fs:
        b = open(os.path.join(a.dir, f), 'rb').read()
        if len(b) < 4096:
            continue
        for m in NC_B.finditer(b):
            ids[int(m.group(1))] += 1
        for m in re.finditer(re.escape(anchor), b):
            lo = max(0, m.start() - a.win)
            hi = min(len(b), m.end() + a.win)
            seg = b[lo:hi]
            s = seg.decode('utf-8', 'replace')
            if NC_B.search(seg):
                tmpl.append(s)
            else:
                done.append(s)
    print('\n=== namecode 码空间 ===')
    ks = sorted(ids)
    print('出现过的码 %d 种，总引用 %d 次；范围 %s..%s'
          % (len(ks), sum(ids.values()), ks[0] if ks else '-', ks[-1] if ks else '-'))
    print('最高频 20 个：%s' % ids.most_common(20))
    print('\n=== 锚点两侧对照（模板 %d 条 / 已解析成品 %d 条）===' % (len(tmpl), len(done)))
    print('模板例：')
    for s in list(dict.fromkeys(tmpl))[:6]:
        print('   ', re.sub(r'[^\w\u4e00-\u9fff{}:—，。！？·]', '·', s)[:100])
    print('成品例（若为空 = 内存里没有已解析串，配对法作废）：')
    for s in list(dict.fromkeys(done))[:12]:
        print('   ', re.sub(r'[^\w\u4e00-\u9fff{}:—，。！？·]', '·', s)[:100])
    if not done:
        print('\n判定：配对法不成立 -> namecode 表必须从配置本身解，回解析器路线')
    else:
        print('\n判定：存在 %d 条已解析串，可尝试与模板按顺序对齐反解 N->名字' % len(done))


if __name__ == '__main__':
    main()
