#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布「背景词根 → 系列中文名」的第二条权威路（2026-10-17 接手背景库 C 任务的产物）。

背景：bg_root_labels.json（拼音整值匹配，50 号发布器）只覆盖 18 组；92 组词根没有中文名，
下拉里只能显示 `huanglong` / `project_explorer` 这种原文。2026-10-17 全表共现扫描
（.diag/bg_probe8_report.txt）找到三条**游戏自己写着**的路线：

  1. memory（回忆战役）：`memory_template.mask == "bg/bg_<root>_N"`（4,702 行全带 bg/ 路径），
     同一组行里 condition 带「开始战役「活动名·上篇」」⇒ 活动名烤在游戏自己的文案里。
     例：bg_camelot_* ⇒ 泠誓光庭、bg_deepecho_* ⇒ 深度回音、bg_qiongding_* ⇒ 穹顶下的圣咏曲。
  2. re_map（常驻复刻）：`re_map_template.bg == "temp_<root>"` 且该行 `name == "<活动名>常驻复刻"`。
     例：temp_wuzang ⇒ 紫绛槿岚、temp_moran ⇒ 墨染的钢铁之花。
  3. child2（学园养成）：`child2_data.name_background == "educate_<root>_N"`，
     该行 `name` = 角色名（娜比娅/艾普洛）、`name2` = 称号（领洋者/探索者）。

产物：`inputs/gamecfg/bg_series_labels.json`
  `labels`：root → {cn, route, src:[{t,f,id,v}], n(盘上该词根 png 数)}

纪律：与 49 号一致——只发**游戏表里写着的**；route 优先级 memory > re_map > child2（冲突时低
优先级路线降级进证据，不丢）；没有任何一条路线的词根不硬凑。词根↔png 的对应在 build 时按
49 号同款 root_of() 现算，发悬空词根直接红。

不入库（`.gitignore: inputs/*/*.json`），台账 `inputs/gamecfg/MANIFEST.json` 入库。

用法:
  py -3 tools/sharecfg_re/51_publish_bg_series.py           # 写盘
  py -3 tools/sharecfg_re/51_publish_bg_series.py --check   # 只跑统计与断言
退出码：任一断言不过即 1（红时不写文件）。
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import sys

try:
    from pypinyin import lazy_pinyin
except ImportError:          # 允许缺：缺了 story/perform 两条路线自动跳过，其余照常（不静默改判）
    lazy_pinyin = None

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LUAJ = os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_json')
RAW = os.path.join(ROOT, 'Output', 'Raw')
DST = os.path.join(ROOT, 'inputs', 'gamecfg')
OUT_FN = 'bg_series_labels.json'

CJK = re.compile(r'[一-鿿]')
JUNK = re.compile(r'\||CHAPTER|_E\b|_EX|\{|\}|\\')
QUOTED = re.compile(r'「([^「」]{2,20})」')
# 事件名尾缀：组内系列名剥掉上下篇/EX/SP（剥完还剩什么就是什么）
EVENT_TAIL = re.compile(r'(·上篇|·下篇|·中篇|·EX|·SP|·EXTRA)$')
TAIL = re.compile(r'(_?cg_?\d+|_cut\d+|_?\d+|_tip|_hx|_n|_bg|_new)$')
GENERIC_MASK = {'bg/bg_memory'}          # 回忆页通用底图，不属于任何活动
MIN_ROOTS = 15                            # 地板：三条路合计至少 15 组（2026-10-17 实测 ~25）

ROLE = ('背景图词根（Output/Raw png 的 root）→ 系列中文名，来源只有三条游戏表内路线：'
        'memory_template.mask+condition / re_map_template.bg+name / child2_data.name_background+name')
CONSUMERS = ['scripts/build_bg_meta.py']


def png_roots():
    """盘上真实存在的背景图：{root: [png名, …]}（root 用 49 号同款 root_of）。"""
    out = collections.defaultdict(list)
    if not os.path.isdir(RAW):
        return out
    for d in os.listdir(RAW):
        p = os.path.join(RAW, d)
        if not os.path.isdir(p):
            continue
        for f in os.listdir(p):
            if f.endswith('.png'):
                out[root_of(f[:-4])].append(f[:-4])
    return out


def root_of(name):
    s = name[3:] if name.startswith('bg_') else name
    prev = None
    while prev != s:
        prev = s
        s = TAIL.sub('', s)
    return s if len(s) >= 4 else ''


def load_rows(tbl):
    doc = json.load(open(os.path.join(LUAJ, tbl + '.json'), encoding='utf-8'))
    return [v for v in doc.values() if isinstance(v, dict) and '__name' not in v]


def cn_ok(s):
    return bool(s) and len(s) <= 20 and bool(CJK.search(s)) and not JUNK.search(s)


def route_memory(roots):
    """memory_template：mask='bg/bg_<stem>' 的行，condition 里「…」的出现次数定系列名。"""
    votes = collections.defaultdict(collections.Counter)
    src = collections.defaultdict(list)
    for r in load_rows('memory_template'):
        mask = str(r.get('mask') or '')
        if mask in GENERIC_MASK or not mask.startswith('bg/bg_'):
            continue
        stem = mask[6:]
        root = root_of(stem)
        # ⚠️ root_of 对 <4 字符的词根返回 ''（`hms` 就是）：空词根在 build_bg_meta 里
        # 本来就不进下拉（`not i['root']` 跳过），发它会误伤 94 张无关图 ⇒ 跳过。
        if not root or root not in roots:
            continue
        for m in QUOTED.findall(str(r.get('condition') or '')):
            name = EVENT_TAIL.sub('', m).strip()
            if cn_ok(name):
                votes[root][name] += 1
                src[root].append({'t': 'memory_template', 'f': 'mask+condition', 'id': r.get('id'),
                                  'v': '%s ⇒ %s' % (mask, m)})
    out = {}
    for root, c in votes.items():
        if not c:
            continue
        cn = c.most_common(1)[0][0]
        out[root] = {'cn': cn, 'route': 'memory', 'src': src[root][:4],
                     'detail': {'votes': dict(c.most_common(5))}}
    return out


def route_re_map(roots):
    """re_map_template：bg='temp_<root>' 且 name='<活动名>常驻复刻'。"""
    out = {}
    for r in load_rows('re_map_template'):
        bg = str(r.get('bg') or '')
        name = str(r.get('name') or '').strip()
        if not bg.startswith('temp_') or not name.endswith('常驻复刻'):
            continue
        root = root_of('bg_' + bg[5:])          # temp_hongran → bg_hongran → hongran
        if not root or root not in roots:
            continue
        cn = name[:-4].strip()                   # 剥「常驻复刻」四字
        if not cn_ok(cn):
            continue
        out[root] = {'cn': cn, 'route': 're_map',
                     'src': [{'t': 're_map_template', 'f': 'bg+name', 'id': r.get('id'),
                              'v': '%s ⇒ %s' % (bg, name)}],
                     'detail': {}}
    return out


def route_child2(roots):
    """child2_data：name_background='educate_<root>_N'，name=角色名，name2=称号。"""
    out = {}
    for r in load_rows('child2_data'):
        nb = str(r.get('name_background') or '')
        name = str(r.get('name') or '').strip()
        name2 = str(r.get('name2') or '').strip()
        if not nb or not cn_ok(name):
            continue
        root = root_of(nb)
        if not root or root not in roots:
            continue
        out[root] = {'cn': name, 'route': 'child2',
                     'src': [{'t': 'child2_data', 'f': 'name_background+name', 'id': r.get('id'),
                              'v': '%s ⇒ %s%s' % (nb, name, ('·' + name2) if cn_ok(name2) else '')}],
                     'detail': {'name2': name2}}
    return out


def py_key(s):
    """中文 → 哑音拼音串（纯大写字母）。缺 pypinyin 时返回 ''（调用方据此跳过该路线）。"""
    if not lazy_pinyin or not s:
        return ''
    return re.sub(r'[^A-Z]', '', ''.join(lazy_pinyin(str(s))).upper())


def titles_index():
    """memory_group.title 的拼音 → (中文标题, id)。活动名/养成计划名都在这张表里，
    但表内没有 story 码 —— 得靠「story 码本身就是活动名拼音」这条桥来对。"""
    if not lazy_pinyin:
        return {}
    out = {}
    for r in load_rows('memory_group'):
        t = str(r.get('title') or '').strip()
        if cn_ok(t):
            k = py_key(t)
            if len(k) >= 6:
                out.setdefault(k, (t, r.get('id')))
    return out


def _code_base(code):
    """story/performance 码去尾数字，只留纯字母（拼音）骨架；纯数字主体（如 1966001）返回 ''。"""
    b = re.sub(r'\d+$', '', str(code or '').upper())
    return b if re.fullmatch(r'[A-Z]{6,}', b) else ''


def route_story(roots, idx):
    """活动剧情：`activity_sp_story.change_background`（bg_<root>_*）+ `story` 码。
    story 码是活动名拼音（XIANGCHEYUTIANQIONGZHIYIN）⇒ 与 memory_group.title 拼音对上。
    ⚠️ 只认 `bg_` 打头的 change_background：`star_level_bg_546` 这类通用底纹若混进来，
    会把 265 张 star_level 图误挂到某个活动名下（root_of 对 star_level_bg 也会给出 star_level）。"""
    votes = collections.defaultdict(collections.Counter)
    src = collections.defaultdict(dict)
    for r in load_rows('activity_sp_story'):
        bg = str(r.get('change_background') or '')
        if not bg.startswith('bg_'):
            continue
        root = root_of(bg)
        if not root or root not in roots:
            continue
        hit = idx.get(_code_base(r.get('story')))
        if not hit:
            continue
        votes[root][hit[0]] += 1
        src[root][hit[0]] = {'t': 'activity_sp_story', 'f': 'change_background+story',
                             'id': r.get('id'), 'v': '%s ⇒ %s' % (bg, r.get('story'))}
    out = {}
    for root, c in votes.items():
        cn = c.most_common(1)[0][0]
        out[root] = {'cn': cn, 'route': 'story', 'src': [src[root][cn]],
                     'detail': {'votes': dict(c.most_common(5))}}
    return out


def route_perform(roots, idx):
    """养成结局：`child2_ending.performance` 是「X者养成计划」拼音，配图 `bg_project_<x>_cg*`。
    project_oceana/explorer 走 performance；project_tb 无 performance 字段（其 pic 在 child_ending），
    靠 `child_data.name`『领航员-TB』的代号 TB 反连到「领航员养成计划」。"""
    out = {}

    def _assign(root, title, src):
        out[root] = {'cn': title, 'route': 'perform', 'src': [src], 'detail': {}}
        if root + '_room' in roots:          # project_x_room 同属该养成，一并挂上
            out[root + '_room'] = {'cn': title, 'route': 'perform',
                                   'src': [dict(src, v=src['v'] + '（_room 变体）')], 'detail': {}}

    for r in load_rows('child2_ending'):
        pic = str(r.get('pic') or '')
        if not pic.startswith('bg_project_'):
            continue
        root = root_of(pic)
        if not root or root not in roots:
            continue
        hit = idx.get(_code_base(r.get('performance')))
        if hit:
            _assign(root, hit[0], {'t': 'child2_ending', 'f': 'pic+performance',
                                   'id': r.get('id'), 'v': '%s ⇒ %s' % (pic, r.get('performance'))})

    # project_tb / educate_tb：child_data.name = 「领航员-TB」；代号大写反查中文前缀
    tb_titles = [t for t, _ in idx.values() if t.endswith('养成计划')]
    code2 = {}
    for r in load_rows('child_data'):
        m = re.match(r'^([^\-\s]+)-([A-Za-z0-9]+)$', str(r.get('name') or ''))
        if m:
            code2[m.group(2).upper()] = (m.group(1), r.get('id'))
    for r in load_rows('child_ending'):
        root = root_of(str(r.get('pic') or ''))
        if not root or root not in roots or root in out:
            continue
        code = root.split('_')[-1].upper()
        if code not in code2:
            continue
        cn_prefix, cid = code2[code]
        title = next((t for t in tb_titles if t.startswith(cn_prefix)), None)
        if title:
            _assign(root, title, {'t': 'child_data', 'f': 'name', 'id': cid,
                                  'v': '%s ⇒ %s' % (cn_prefix + '-' + code, title)})
    return out


def build(verbose=False):
    roots = png_roots()
    if verbose:
        print('盘上词根 %d 组 / png %d 张' % (len(roots), sum(len(v) for v in roots.values())))
    cand = {}
    idx = titles_index()
    routes = ((route_memory, 'memory'),
              (lambda r: route_story(r, idx), 'story'),
              (route_re_map, 're_map'),
              (lambda r: route_perform(r, idx), 'perform'),
              (route_child2, 'child2'))
    for fn, route in routes:
        got = fn(roots)
        if verbose:
            print('  route %-8s: %d 组' % (route, len(got)))
        for root, ent in got.items():
            if root in cand:                    # 优先级：memory > story > re_map > perform > child2
                cand[root]['detail']['superseded_by'] = ent['route']
                cand[root]['src'].extend(ent['src'][:1])
                continue
            cand[root] = ent
    # 只发盘上真有图的词根，n 记录张数
    labels = {r: dict(e, n=len(roots[r])) for r, e in cand.items() if r in roots and len(roots[r]) >= 2}
    return labels, roots


def selfcheck(labels, roots):
    n_png = sum(v['n'] for v in labels.values())
    return [
        ('每条都带可回指出处 (表/字段/行id/原值)',
         all(e['src'] and all(x.get('t') and x.get('f') and x.get('id') is not None and x.get('v')
                              for x in e['src']) for e in labels.values())),
        ('cn 都是纯中文短标签（无代码分隔符/不超长）',
         all(cn_ok(e['cn']) for e in labels.values())),
        ('发布的词根盘上真有图（≥2 张），不产悬空词根',
         all(r in roots and roots[r] and e['n'] >= 2 for r, e in labels.items())),
        ('route 只有五档且与来源一致',
         all(e['route'] in ('memory', 'story', 're_map', 'perform', 'child2')
             for e in labels.values())),
        ('三条路线覆盖不低于地板 %d 组（实测 2026-10-17 = %d；掉了说明表源变了）'
         % (MIN_ROOTS, len(labels)), len(labels) >= MIN_ROOTS),
        ('覆盖 png ≥ 100 张（实测 2026-10-17 ≈ 250；掉了说明 mask/temp_ 形状变了）', n_png >= 100),
    ]


def merge_ledger(entry):
    path = os.path.join(DST, 'MANIFEST.json')
    led = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else \
        {'schema_version': 1, 'purpose': '从游戏本体 sharecfg 容器直接解出的权威映射',
         'provenance': {'regenerate_via': []}, 'files': []}
    prov = led.setdefault('provenance', {})
    prov.setdefault('game_version_local_assets', '9.7.385')
    prov.setdefault('container_grammar', 'docs/TROUBLESHOOTING.md §33/§34')
    prov['landed_at'] = datetime.date.today().isoformat()
    rg = prov.setdefault('regenerate_via', [])
    for s in ('tools/sharecfg_re/41_export_lua_tables.py', 'tools/sharecfg_re/51_publish_bg_series.py'):
        if s not in rg:
            rg.append(s)
    files = [f for f in led.get('files', []) if f.get('path') != OUT_FN]
    files.append(entry)
    files.sort(key=lambda f: f['path'])
    led['files'] = files
    return led


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只跑统计与断言，不写文件')
    a = ap.parse_args()

    if not os.path.isdir(LUAJ):
        print('[FAIL] %s 不在盘上 —— 先跑 tools/sharecfg_re/41_export_lua_tables.py' % LUAJ)
        return 2

    labels, roots = build(verbose=True)
    n_png = sum(v['n'] for v in labels.values())
    print('发布 %d 组词根 / 覆盖 %d 张 png' % (len(labels), n_png))
    for r in sorted(labels, key=lambda x: -labels[x]['n']):
        e = labels[r]
        print('  %-24s → %-14s (%s, %d 张)  例: %s' % (r, e['cn'], e['route'], e['n'], e['src'][0]['v'][:40]))
    ok = True
    for desc, passed in selfcheck(labels, roots):
        print('%s %s' % ('✓' if passed else '✗', desc))
        ok &= passed
    if not ok:
        print('\n闸门：红 —— 断言未全过，不写文件')
        return 1
    if a.check:
        print('\n闸门：绿（--check 未写文件）')
        return 0

    body = json.dumps({'schema': 1,
                       'generated_at': datetime.date.today().isoformat(),
                       'labels': {k: labels[k] for k in sorted(labels)}},
                      ensure_ascii=False, indent=1, sort_keys=True)
    blob = body.encode('utf-8')
    os.makedirs(DST, exist_ok=True)
    with open(os.path.join(DST, OUT_FN), 'wb') as f:
        f.write(blob)
    entry = {'path': OUT_FN, 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest(),
             'rows': len(labels), 'role': ROLE, 'consumers': CONSUMERS,
             'source': '.diag/sharecfg_re/lua_json/{memory_template,re_map_template,child2_data}.json',
             'coverage': '词根中文名 %d 组 / %d 张 png' % (len(labels), n_png)}
    led = merge_ledger(entry)
    with open(os.path.join(DST, 'MANIFEST.json'), 'w', encoding='utf-8') as f:
        json.dump(led, f, ensure_ascii=False, indent=1)
    print('\n[WRITE] inputs/gamecfg/%s（%d 组）+ 台账已更新' % (OUT_FN, len(labels)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
