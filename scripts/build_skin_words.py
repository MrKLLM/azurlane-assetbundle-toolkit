#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「台词正文」并进皮肤语音表旁边，产出画廊前端用的 `skin_words.json`。

为什么单独一份产物而不是改写 `skin_voice.json`：后者是 75 分钟全量导出的已验收产物
（零回退闸门以它为基准），这里只做「按同一把钥匙 join」，两份产物各自可重生。

钥匙：**皮肤表里那一行的主键 id**（`E.row_id_for`，与语音层共用同一份后缀口径 `E.row_candidates`）。
      ⚠️ 不是 `cv*10 + idx` —— 那是把「语音包号 + 包内档位」当主键，两件事。老批次恰好形如
      `cv*10+idx`，皮肤序号 ≥10 之后游戏换了号段（`aisaikesi_10` 真行是 **137090**），
      算术式会进位撞进下一艘船的行（`10709*10+10=107100` = 约克城II ⇒ 埃塞克斯的皮肤10
      整列台词显示成约克城的，2026-10-02 用户从「普通触摸字幕比语音短」报出）。
      音频侧本来就是对的（`cv-10709.b` 里确有 `touch_1_10` 这一档，14.08 秒），错的只有文本钥匙。
      两层取值：皮肤行优先；皮肤行**没有**的类别回退到该船本体行 —— 誓约/资料/强化这类是船级台词，
      皮肤行里根本没这个字段，而音频侧 `tier_for()` 对这些类别取的就是本体档文件，正文必须跟着同源
      （第一版只换钥匙、没加这层，实测把 432 条本来能显示的台词判成"无正文"= 修好触摸弄没誓约）。
      黑化版是独立发声实体（§84 用户口径），不回退本体。

类别名 → 台词字段全部查 `character_voice` 表，不靠语义猜：
  · cue 类别（cat）    = 表的 resource_key（`get`/`task`/`warcry`/`touch_head`…）
  · 动作组名 / 触摸槽   = 表的 l2d_action（`touch_body`/`touch_special`/`main_1`…）
  · 表里的 key 才是正文字段名（`unlock`/`mission`/`battle`/`headtouch`…）
`main1..main7` 常不在行里，游戏把它们合并在 `main` 字段用 `|` 分隔 → 按序号拆。

**两趟**：① 语音表里有的皮肤，按 cue 取词（音频与正文同源）；② **皮肤表里有行但语音表里没有**的那批
（主包没随资产下发、只有 `-battle/-gift` 变体，§57），只出门能显示的台词——键用**字段名本身**
（它就是 `character_voice` 的 key，中文类别名直接从表里取），`drop_descrip` 这类**不是台词**的字段排除。

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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_cv_voice as E              # 皮肤表→包号/序号 这条 join 只允许有一份实现
GAL = os.path.join(ROOT, 'Output', 'gallery_v2')
GAMECFG = os.path.join(ROOT, 'inputs', 'gamecfg')
DEF_VOICE = os.path.join(GAL, 'skin_voice.json')
DEF_WORDS = os.path.join(GAMECFG, 'ship_skin_words.json')
DEF_ALIAS = os.path.join(GAMECFG, 'character_voice.json')
DEF_OUT = os.path.join(GAL, 'skin_words.json')

MAIN_SEQ = re.compile(r'^main(\d+)$')
# 不是"说出来的话"的字段：获得描述/图鉴文案，进不了台词列表
NOT_LINE = {'drop_descrip'}
# 游戏配置里的台词自带实体占位符，运行时才换名字；不展开就直接把 `{namecode:98}` 端给用户看
NAMECODE = re.compile(r'\{namecode:(\d+)\}')
DEF_NAMECODE = os.path.join(GAMECFG, 'name_code.json')


def expand(text, nc, st):
    """`{namecode:NN}` → 中文实体名。查不到就**原样留着**并计数：宁可看见占位符，不许编一个名字。"""
    def rep(m):
        hit = nc.get(m.group(1))
        if hit:
            st['占位符展开'] += 1
            return hit['name']
        st['占位符未展开'] += 1
        return m.group(0)
    return NAMECODE.sub(rep, text)


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


def text_for(row, name, alias, nc=None, st=None):
    """运行时名 → 该行正文；`main_N` 缺字段时回退到 `main` 的 `|` 分隔第 N 条。"""
    field = alias.get(name, name)
    v = row.get(field)
    out = ''
    if v:
        out = v
    else:
        m = MAIN_SEQ.match(field or '')
        if m:
            merged = row.get('main')
            if merged:
                parts = [p.strip() for p in merged.split('|') if p.strip()]
                i = int(m.group(1)) - 1
                if 0 <= i < len(parts):
                    out = parts[i]
    return expand(out, nc, st) if (out and nc is not None) else out


def field_lines(row, cv_tbl, labels, nc=None, st=None):
    """无音频皮肤的一行 → {字段名: 正文}；中文类别名顺着 character_voice 取，非台词字段排除。"""
    ent = {}
    for f, v in (row or {}).items():
        if f in NOT_LINE or not (v or '').strip():
            continue
        if f not in cv_tbl:
            continue                      # 认不出类别的字段一律不进（不猜）
        ent[f] = expand(v.strip(), nc, st) if nc is not None else v.strip()
        labels.setdefault(f, (cv_tbl[f].get('voice_name') or '').strip() or f)
    merged = (row or {}).get('main')
    if merged:
        for i, p in enumerate([x.strip() for x in merged.split('|') if x.strip()], 1):
            name = 'main%d' % i
            ent[name] = expand(p, nc, st) if nc is not None else p
            labels.setdefault(name, '主界面%d' % i)      # 与导出侧 main_N 的中文名同源
    return ent


def build(voice, words, alias, group2cat, cv_tbl, rows_by_painting, gallery_keys, nc):
    """→ (m: 皮肤→行id, w: 行id→{运行时名: 正文}, L: 运行时名→中文类别名, 统计, 钥匙改派清单)"""
    m, w, labels = {}, {}, {}
    audit = []
    st = collections.Counter()
    for skin, e in voice.items():
        arith = int(e['cv']) * 10 + int(e['idx'])
        auth = E.row_id_for(skin.lower(), rows_by_painting, e['cv'])
        sid = str(auth if auth is not None else arith)
        if auth is not None and auth != arith:
            st['钥匙改派'] += 1
            audit.append((skin, arith, auth, '改派' if str(auth) in words else '真行没正文·靠船级回退'))
        row = words.get(sid)
        # 船级类别（誓约/资料/强化/委托…）皮肤行里根本没有这些字段 —— 音频侧 `tier_for()`
        # 取的就是本体档的文件，正文必须跟着回退到**本体行**，否则修好触摸、弄没誓约（实测 432 条）。
        # 黑化版是独立发声实体（§84 用户口径），不许回退本体。
        brow = None
        if not E.HEI_SUF.search(E.art_chain(skin.lower())[-1]):
            base = E.row_id_for(E.ship_stem(skin.lower()), rows_by_painting, e['cv'])
            if base is not None and str(base) != sid:
                brow = words.get(str(base))
        if not row and not brow:
            st['皮肤无正文行'] += 1
            continue
        m[skin] = sid
        cats = {l['cat'] for l in e.get('lines', [])}
        names = set(cats) | set(e.get('l2d') or {}) | set(e.get('tap') or {})

        # 「本皮肤档」的槽位：音频文件名里带着这条皮肤自己的序号 ⇒ 游戏给这一档单独录了词。
        # 这些槽位**不许**回退到本体行（那等于把本体的句子冒充成这一档的字幕，是另一种错派）；
        # 只有音频取自基础档（`tier_for()` 回退到 0 档文件）的类别，正文才跟着回本体行。
        def cue_tier(path):
            return E.split_cue(os.path.splitext(os.path.basename(path))[0])[1]
        own_tier = set()
        if e['idx']:
            for l in e.get('lines', []):
                if not l.get('ev') and cue_tier(l['f']) == e['idx']:
                    own_tier.add(l['cat'])
            for g, ps in (e.get('l2d') or {}).items():
                if any(cue_tier(p) == e['idx'] for p in ps):
                    own_tier.add(g)
            own_tier |= {g for g, p in (e.get('tap') or {}).items() if cue_tier(p) == e['idx']}
        # 中文类别名：cue 侧导出时已带（voice_name），动作组/触摸槽顺着 group2cat 取
        for l in e.get('lines', []):
            if l.get('label'):
                labels.setdefault(l['cat'], l['label'])
        ent = w.setdefault(sid, {})
        for n in names:
            t = text_for(row, n, alias, nc, st) if row else ''
            if not t and brow and n not in own_tier:
                t = text_for(brow, n, alias, nc, st)
                if t:
                    st['船级类别·取自本体行'] += 1
            if not t:
                st['槽位无正文'] += 1
                if n in own_tier:
                    st['本皮肤档无同源正文'] += 1
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

    # 第二趟：皮肤表里有行、语音表里却没有的皮肤（主包没随资产下发，§57 那 43 张）。
    # 键用字段名本身（= character_voice 的 key），中文类别名照表取。
    # ⚠️ 归属与第一趟、与语音层**同一份规则**（`E.row_id_for` → `E.row_candidates`）：这里原来写的是
    #    `E.VAR.sub('', kl)` 一次贪婪剥光，于是 12 个黑化键被剥到本体那一行，
    #    把本体的台词派给了黑化版——与 §84 刚在语音层撤掉的是同一份错派（见 §85）。
    for k in gallery_keys:
        if k in voice:
            continue
        auth = E.row_id_for(k.lower(), rows_by_painting)
        if auth is None:
            continue
        sid = str(auth)
        row = words.get(sid)
        if not row:
            st['无音频皮肤·表里无词行'] += 1
            continue
        ent = field_lines(row, cv_tbl, labels, nc, st)
        if not ent:
            st['无音频皮肤·整皮无台词'] += 1
            continue
        prev = w.get(sid)
        if prev is None:
            w[sid] = dict(ent)
        else:                                    # 同船另一档已按 cue 建过 → 只补没冲突的键
            for n, t in ent.items():
                if prev.get(n) and prev[n] != t:
                    raise SystemExit('同一皮肤行取到两条不同正文: %s/%s' % (k, n))
                prev.setdefault(n, t)
        m.setdefault(k, sid)
        st['无音频皮肤·配上台词'] += 1
        st['无音频皮肤·正文字条'] += len(ent)
    return m, w, labels, st, audit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--voice', default=DEF_VOICE)
    ap.add_argument('--words', default=DEF_WORDS)
    ap.add_argument('--out', default=DEF_OUT)
    ap.add_argument('--report', action='store_true', help='只统计不写盘')
    ap.add_argument('--audit', default='', help='把钥匙改派清单写到这个路径（对照表用）')
    a = ap.parse_args()
    voice = json.load(open(a.voice, encoding='utf-8'))
    words = json.load(open(a.words, encoding='utf-8'))
    alias, group2cat = load_alias()
    cv_tbl = json.load(open(DEF_ALIAS, encoding='utf-8'))
    nc = json.load(open(DEF_NAMECODE, encoding='utf-8'))
    import extract_cv_voice as E          # 皮肤表→包号/序号 这条 join 只允许有一份实现
    rows = E.load_skin_rows()
    keys = E.gallery_keys()
    m, w, labels, st, audit = build(voice, words, alias, group2cat, cv_tbl, rows, keys, nc)
    left = sum(1 for ent in w.values() for t in ent.values() if '{namecode' in t)
    if st['占位符未展开'] or left:
        raise SystemExit('台词里还有 %d 处 {namecode} 没展开（%d 行受影响）——'
                         'name_code 表与 ship_skin_words 不同版本？重跑 tools/sharecfg_re/46_publish_name_code.py'
                         % (st['占位符未展开'], left))
    blob = json.dumps({'gen': datetime.date.today().isoformat(), 'm': m, 'w': w, 'L': labels},
                      ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    print('语音表皮肤 %d | 配上正文 %d | 无正文行 %d | 正文键 %d 个（皮肤行 id 去重后）'
          % (len(voice), st['皮肤已配正文'], st['皮肤无正文行'], len(w)))
    print('正文字条 %d | 空槽位 %d | 别名条目 %d | 中文名 %d | 实体占位符展开 %d 处'
          % (st['正文字条'], st['槽位无正文'], len(alias), len(labels), st['占位符展开']))
    print('无音频皮肤（有表行、主包未下发）%d 张配上台词 / 正文字条 %d | 整皮无台词 %d | 表里无词行 %d'
          % (st['无音频皮肤·配上台词'], st['无音频皮肤·正文字条'],
             st['无音频皮肤·整皮无台词'], st['无音频皮肤·表里无词行']))
    print('台词钥匙 改用表主键 %d 处（算术式会撞上别的实体）| 船级类别取自本体行 %d 条'
          % (st['钥匙改派'], st['船级类别·取自本体行']))
    if a.audit:
        with open(a.audit, 'w', encoding='utf-8', newline='') as f:
            f.write('皮肤\t旧钥匙(算术cv*10+idx)\t真行id\t处置\n')
            for k, old, new, act in sorted(audit):
                f.write('%s\t%d\t%d\t%s\n' % (k, old, new, act))
        print('  改派清单: %s（%d 行）' % (a.audit, len(audit)))
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
