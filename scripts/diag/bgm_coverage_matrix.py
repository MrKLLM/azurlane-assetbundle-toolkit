# -*- coding: utf-8 -*-
"""只读探针：音乐库标签覆盖矩阵 + 资产内音乐清单候选（2026-10-17 交接 B 任务取证）。

产出写 .diag/bgm_coverage_report.txt，不改任何产物。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import paths as P  # noqa: E402

OUT_TXT = os.path.join(ROOT, '.diag', 'bgm_coverage_report.txt')
LUA = os.path.join(P.ROOT, '.diag', 'sharecfg_re', 'lua_json')

lines = []


def w(s=''):
    lines.append(str(s))


# ── 1. bgm.json 覆盖矩阵 ────────────────────────────────
with open(os.path.join(P.GALLERY_OUT, 'bgm.json'), encoding='utf-8') as f:
    d = json.load(f)
tracks = d['tracks']
N = len(tracks)
w('=== 1. bgm.json 覆盖矩阵 ===')
w(f'总数: {N}')
w(f'generated: {d.get("generated")}')


def cnt(pred):
    return sum(1 for t in tracks if pred(t))


has_usage = cnt(lambda t: t['usage'])
has_scene = cnt(lambda t: t['scenes'])
has_album = cnt(lambda t: t['album'])
has_cn = cnt(lambda t: t['title_cn'])
has_ship = cnt(lambda t: t['ship'])
has_any_label = cnt(lambda t: t['usage'] or t['scenes'] or t['album'] or t['title_cn'] or t['ship'])
w(f'有用途(slug启发式): {has_usage}')
w(f'有出处(12张配置表): {has_scene}')
w(f'有专辑: {has_album}')
w(f'有官方中文名: {has_cn}')
w(f'关联舰名: {has_ship}')
w(f'五项任一非空: {has_any_label}   ⇒ 完全裸奔: {N - has_any_label}')

w('')
w('--- 用途分布 ---')
from collections import Counter  # noqa: E402
uc = Counter(t['usage'] or '(空)' for t in tracks)
for k, v in uc.most_common():
    w(f'  {k}: {v}')

w('')
w('--- 出处分布(按表标签) ---')
sc = Counter()
for t in tracks:
    for s in t['scenes']:
        sc[s['t']] += 1
for k, v in sc.most_common():
    w(f'  {k}: {v}')

# 未被出处覆盖的曲子按 slug 词根分组（- 前两段）
w('')
w('--- 未有任何"出处"的曲子（按 slug 前两段词根分组） ---')
root_cnt = Counter()
for t in tracks:
    if not t['scenes']:
        parts = t['slug'].split('-')
        root_cnt['-'.join(parts[:2])] += 1
for k, v in root_cnt.most_common(40):
    w(f'  {k}: {v}')
w(f'  … 共 {len(root_cnt)} 个词根组 / {N - has_scene} 首')

# 用途+出处都空的
both_empty = [t['slug'] for t in tracks if not t['usage'] and not t['scenes']]
w('')
w(f'--- 用途与出处双空的曲子: {len(both_empty)} 首 ---')
for s in both_empty[:60]:
    w(f'  {s}')

# ── 2. lua 表目录里音乐相关候选 ─────────────────────────
w('')
w('=== 2. sharecfg_re/lua_json 里音乐相关表 ===')
if os.path.isdir(LUA):
    names = sorted(os.listdir(LUA))
    w(f'表总数: {len(names)}')
    pat = re.compile(r'music|bgm|sound|song|audio|jukebox|collect', re.I)
    hits = [n for n in names if pat.search(n)]
    w('名字含 music/bgm/sound/song/audio/jukebox/collect 的表:')
    for n in hits:
        p = os.path.join(LUA, n)
        w(f'  {n}  ({os.path.getsize(p)} bytes)')
else:
    w(f'!! lua_json 目录不存在: {LUA}')

# ── 3. 逐张候选表抽样看结构（看有没有"曲目列表"性质的字段） ──
w('')
w('=== 3. 候选表结构抽样 ===')
def lua_rows(name):
    with open(os.path.join(LUA, name), encoding='utf-8') as f:
        d = json.load(f)
    return [v for v in d.values() if isinstance(v, dict) and '__name' not in v]

for n in hits:
    try:
        rows = lua_rows(n)
    except Exception as e:
        w(f'{n}: 读取失败 {e}')
        continue
    keys = Counter()
    for r in rows[:200]:
        for k in r.keys():
            keys[k] += 1
    top = ', '.join(f'{k}({c})' for k, c in keys.most_common(12))
    w(f'{n}: {len(rows)} 行 | 常见字段: {top}')

# ── 4. 全表扫描：找"值像曲名"的字段（bgm-xxx 或已知 slug 形状）──
w('')
w('=== 4. 全表扫描：哪些表的哪些字段装着曲名（对全部 536 个 slug 归一匹配） ===')
slugs = {_norm for t in tracks for _norm in (t['slug'], t['slug'][4:] if t['slug'].startswith('bgm-') else t['slug'])}
w(f'待匹配 slug(归一): {len(slugs)} 个')
pat = re.compile(r'^(bgm-)?(battle|story|theme|main|login|backyard|idol|ss|se|dorm|airraid|'
                 r'ninjacity|nier|ryza|azumaster|richang|event|room)', re.I)
# 扫描每张表：值命中已知 slug 集合 的字段名分布（比 build_bgm_index 的宽松正则准）
field_hits = {}
table_hits = {}
for n in sorted(os.listdir(LUA)):
    if not n.endswith('.json'):
        continue
    try:
        with open(os.path.join(LUA, n), encoding='utf-8') as f:
            dd = json.load(f)
    except Exception:
        continue
    rows = [v for v in dd.values() if isinstance(v, dict) and '__name' not in v]
    if not rows:
        continue
    tf = {}
    cnt_all = 0
    for r in rows:
        for k, v in r.items():
            if isinstance(v, str) and v:
                nv = v[4:] if v.startswith('bgm-') else v
                if nv in slugs or (pat.match(v) and '-' in v):
                    tf[k] = tf.get(k, 0) + 1
                    cnt_all += 1
    if cnt_all:
        table_hits[n[:-5]] = cnt_all
        field_hits[n[:-5]] = tf

w(f'含曲名形状引用的表: {len(table_hits)} 张')
for k, v in sorted(table_hits.items(), key=lambda x: -x[1])[:40]:
    fs = ', '.join(f'{fk}({fc})' for fk, fc in sorted(field_hits[k].items(), key=lambda x: -x[1])[:8])
    w(f'  {k}: {v}  字段: {fs}')

# ── 5. 12 张 SCENE_TABLES 之外的新表里，命中已知 slug 的 ──
w('')
w('=== 5. 名单外但命中"已知 slug 精确集合"的表（用户判断的"资产内曲目表"最可能在这） ===')
KNOWN = {'voice_bgm', 'activity_sp_story', 'expedition_data_by_map', 'memory_storyline',
         'music_collect_config', 'soundstory_template', 'dorm3d_rooms', 'island_map',
         'story_template', 'world_expedition_data', 'login', 'activity_series_enemy_story'}
for k, v in sorted(table_hits.items(), key=lambda x: -x[1]):
    if k in KNOWN:
        continue
    fs = ', '.join(f'{fk}({fc})' for fk, fc in sorted(field_hits[k].items(), key=lambda x: -x[1])[:8])
    w(f'  {k}: {v}  字段: {fs}')

with open(OUT_TXT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('written', OUT_TXT)
