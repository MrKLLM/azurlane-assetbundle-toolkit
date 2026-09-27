#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「台词正文」并进皮肤语音表旁边，产出画廊前端用的 `skin_words.json`。

为什么单独一份产物而不是改写 `skin_voice.json`：后者是 75 分钟全量导出的已验收产物
（零回退闸门以它为基准），这里只做「按同一把钥匙 join」，两份产物各自可重生。

钥匙：`skin_voice.json` 每条皮肤带 `cv`（语音包号）与 `idx`（皮肤序号），
      皮肤行 id = `cv*10 + idx` —— 正是 `ship_skin_words` 表的主键。
      语音与正文因此取自**同一行**，不存在"字幕与声音不同皮肤"的错配。

类别名 → 台词字段全部查 `character_voice` 表，不靠语义猜：
  · cue 类别（cat）    = 表的 resource_key（`get`/`task`/`warcry`/`touch_head`…）
  · 动作组名 / 触摸槽   = 表的 l2d_action（`touch_body`/`touch_special`/`main_1`…）
  · 表里的 key 才是正文字段名（`unlock`/`mission`/`battle`/`headtouch`…）
`main1..main7` 常不在行里，游戏把它们合并在 `main` 字段用 `|` 分隔 → 按序号拆。

产物结构（前端只做两次字典取值，不做任何匹配）:
  {"gen": "...", "m": {皮肤key: 皮肤行id}, "w": {皮肤行id: {cat或动作组或触摸槽: 正文}},
   "L": {cat或动作组或触摸槽: 中文类别名}}

用法:
  py -3 scripts/build_skin_words.py --report              # 只统计不写盘
  py -3 scripts/build_skin_words.py [--out 路径]
"""
import os, sys, re, json, argparse, collections, datetime

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
GAL = os.path.join(ROOT, 'Output', 'gallery_v2')
GAMECFG = os.path.join(ROOT, 'inputs', 'gamecfg')
DEF_VOICE = os.path.join(GAL, 'skin_voice.json')
DEF_WORDS = os.path.join(GAMECFG, 'ship_skin_words.json')
DEF_ALIAS = os.path.join(GAMECFG, 'character_voice.json')
DEF_OUT = os.path.join(GAL, 'skin_words.json')

MAIN_SEQ = re.compile(r'^main(\d+)$')


def load_alias():
    """character_voice → (运行时名: 正文字段名) 与 (运行时名: cue 类别名)。

    运行时名有两套：cue 类别（=resource_key，`lines[].cat` 用的就是它）与
    Live2D 动作组 / 触摸槽（=l2d_action，如 touch_body）。
    一个运行时名若被多个 key 共用，取值就有二义 → 直接拒绝（实测全表 85 条无冲突）。
    """
    cv = json.load(open(DEF_ALIAS, encoding='utf-8'))
    by_name = collections.defaultdict(set)
    for key, ent in cv.items():
        for rk in ('resource_key', 'l2d_action'):
            name = (ent.get(rk) or '').strip()
            if name:
                by_name[name].add(key)
    conflict = {n: sorted(ks) for n, ks in by_name.items() if len(ks) > 1}
    if conflict:
        raise SystemExit('character_voice 里这些运行时名对应到多个台词字段，取值会有二义: %s' % conflict)
    field = {n: next(iter(ks)) for n, ks in by_name.items()}
    # 动作组 / 触摸槽 → 该 cue 的类别名（touch_body→touch_1），中文标签顺着这条链取
    group2cat = {}
    for key, ent in cv.items():
        g = (ent.get('l2d_action') or '').strip()
        c = (ent.get('resource_key') or '').strip()
        if g and c:
            group2cat.setdefault(g, c)
    return field, group2cat


def text_for(row, name, alias):
    """运行时名 → 该行正文；`main_N` 缺字段时回退到 `main` 的 `|` 分隔第 N 条。"""
    field = alias.get(name, name)
    v = row.get(field)
    if v:
        return v
    m = MAIN_SEQ.match(field or '')
    if m:
        merged = row.get('main')
        if merged:
            parts = [p.strip() for p in merged.split('|') if p.strip()]
            i = int(m.group(1)) - 1
            if 0 <= i < len(parts):
                return parts[i]
    return ''


def build(voice, words, alias, group2cat):
    """→ (m: 皮肤→行id, w: 行id→{运行时名: 正文}, L: 运行时名→中文类别名, 统计)"""
    m, w, labels = {}, {}, {}
    st = collections.Counter()
    for skin, e in voice.items():
        sid = str(int(e['cv']) * 10 + int(e['idx']))
        row = words.get(sid)
        if not row:
            st['皮肤无正文行'] += 1
            continue
        m[skin] = sid
        cats = {l['cat'] for l in e.get('lines', [])}
        names = set(cats) | set(e.get('l2d') or {}) | set(e.get('tap') or {})
        # 中文类别名：cue 侧导出时已带（voice_name），动作组/触摸槽顺着 group2cat 取
        for l in e.get('lines', []):
            if l.get('label'):
                labels.setdefault(l['cat'], l['label'])
        ent = w.setdefault(sid, {})
        for n in names:
            t = text_for(row, n, alias)
            if not t:
                st['槽位无正文'] += 1
                continue
            if ent.get(n) and ent[n] != t:
                raise SystemExit('同名槽位在同一个皮肤行上取到两条不同正文: %s/%s' % (skin, n))
            ent[n] = t
            st['正文字条'] += 1
        if not ent:
            del w[sid]
            m.pop(skin, None)
            st['整皮无正文'] += 1
        st['皮肤已配正文'] += 1
    for g, c in group2cat.items():
        if labels.get(c):
            labels.setdefault(g, labels[c])
    return m, w, labels, st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--voice', default=DEF_VOICE)
    ap.add_argument('--words', default=DEF_WORDS)
    ap.add_argument('--out', default=DEF_OUT)
    ap.add_argument('--report', action='store_true', help='只统计不写盘')
    a = ap.parse_args()
    voice = json.load(open(a.voice, encoding='utf-8'))
    words = json.load(open(a.words, encoding='utf-8'))
    alias, group2cat = load_alias()
    m, w, labels, st = build(voice, words, alias, group2cat)
    blob = json.dumps({'gen': datetime.date.today().isoformat(), 'm': m, 'w': w, 'L': labels},
                      ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    print('语音表皮肤 %d | 配上正文 %d | 无正文行 %d | 正文键 %d 个（皮肤行 id 去重后）'
          % (len(voice), st['皮肤已配正文'], st['皮肤无正文行'], len(w)))
    print('正文字条 %d | 空槽位 %d | 别名条目 %d | 中文名 %d'
          % (st['正文字条'], st['槽位无正文'], len(alias), len(labels)))
    print('产物 %d B (%.1f MB)' % (len(blob.encode('utf-8')), len(blob.encode('utf-8')) / 1048576))
    if a.report:
        print('（--report 未写盘）')
        return 0
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'wb').write(blob.encode('utf-8'))
    print('已写出 %s' % os.path.relpath(a.out, ROOT).replace('\\', '/'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
