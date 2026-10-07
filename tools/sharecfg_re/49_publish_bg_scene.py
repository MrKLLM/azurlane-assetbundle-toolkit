#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布「背景图 → 中文场景/关卡名」权威引用表（含台账）。

为什么需要这一步：`Output/Raw/` 的 1,897 张背景图只有 `bg_amahara_1` 这类英文资源名，
而游戏配置表里**逐张写着这张图用在哪个关卡** —— 实测形状：

  `activity_sp_story.change_background == "bg_amahara_1"`，该行 `name == "EP1-3 云海之宴"`
  `expedition_data_by_map.default_background == "bg_aircraft_future"`，该行 `name == "圣印前的同盟·EX…"`

⇒ 中文名不靠命名规则猜，**只认"某字段整值等于 png 名"这种精确引用**，并把出处（表/字段/行 id）
一起写进产物，页面上能回指。

字段面收窄（关键，否则会把无关字段撞出的假配对当命名）：
  只收**背景语义字段**（`*_bg` / `bg` / `*background*` / `pic` / `illustration` / `login_static` /
  `scene` / `image` / `banner`），并**排除** `icon` / `battle_character` / `prefab` / `ani*` /
  `anchor` / `*suffix` 这些"值可能是资源名但不是背景"的字段。

产物：`inputs/gamecfg/bg_scene_refs.json`
  `exact`：png 名 → [{t 表, f 字段, id 行标识(无 id 时退到 map/容器键), cn 中文标签, cnf 标签来自哪个字段}]

⚠️ 原设计的第二层"用 `bgm` 名模板 `story-<root>-stageN` 反推章节名"**已否证并删除**：
`memory_storyline` 99 行里只有 16 行的 `bgm` 是 `story-*` 形状（其余是 `main-newyear`/`bsm-7` 等别的命名族），
能对上 png 词根的只剩 **4 个** ⇒ 这个面既不通用也不可靠，不如不做。
同 root 兄弟图的中文名改由 `scripts/build_bg_meta.py` 从这些精确事实做**组内传播**并标「推断」——
事实面（本文件）与显示策略（build_bg_meta）分开。

不入库（`.gitignore: inputs/*/*.json`），台账 `inputs/gamecfg/MANIFEST.json` 入库。

用法:
  py -3 tools/sharecfg_re/49_publish_bg_scene.py           # 写盘
  py -3 tools/sharecfg_re/49_publish_bg_scene.py --check   # 只跑统计与断言，不写文件
退出码：任一断言不过即 1（红时不写文件）。
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LUAJ = os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_json')
RAW = os.path.join(ROOT, 'Output', 'Raw')
DST = os.path.join(ROOT, 'inputs', 'gamecfg')
OUT_FN = 'bg_scene_refs.json'

CJK = re.compile(r'[一-鿿]')
# 背景语义字段（整值等于 png 名才算引用）
BG_FIELD = re.compile(r'^(bg|.*_bg|background|.*background.*|pic|illustration|login_static|'
                      r'scene|image|banner)$', re.I)
# 这些字段虽然也可能装资源名，但语义上不是"这张图用在哪"，一律不收
BAD_FIELD = re.compile(r'(icon|battle_character|prefab|anchor|controller|ani_|animtor|suffix)', re.I)
LABEL_FIELDS = ('name', 'title', 'show_name', 'chapter_name', 'map_name', 'label')
# 词根尾缀（机械剥离，剥完还剩什么就是什么）—— `build_bg_meta.py` 复用 root_of() 做"组内传播"
TAIL = re.compile(r'(_?cg_?\d+|_cut\d+|_?\d+|_tip|_hx|_n|_bg|_new)$')
# 闸门地板值：不是目标，是"掉了就说明字段白名单或表源变了"的报警器。
# 2026-10-07 实测 = 284 个 png 拿到精确中文名（占 1875 的 15.1%），地板取 240（≈ −15%）。
MIN_CN_PNGS = 240

ROLE = ('背景图（Output/Raw/*.png 的资源名）→ 逐张的中文关卡名/章节名 + 出处(表/字段/行标识)，'
        '只认"某表背景语义字段整值 == png 名"这种精确引用；同组兄弟图的推断由 build_bg_meta.py 负责')
CONSUMERS = ['scripts/build_bg_meta.py']


def png_names():
    """盘上真实存在的背景图名（含所在类目，页面要按类目分组）。"""
    out = {}
    if not os.path.isdir(RAW):
        return out
    for d in os.listdir(RAW):
        p = os.path.join(RAW, d)
        if not os.path.isdir(p):
            continue
        for f in os.listdir(p):
            if f.endswith('.png'):
                out.setdefault(f[:-4], []).append(d)
    return out


def root_of(name):
    s = name[3:] if name.startswith('bg_') else name
    prev = None
    while prev != s:
        prev = s
        s = TAIL.sub('', s)
    return s if len(s) >= 4 else ''


def rows_of(doc, path=''):
    """摊平设备侧表：容器可能是 {id:{...}} 或带一层嵌套，统一产出 (行标识, dict 行)。

    ⚠️ 实测 143,583 行里 **26.2% 没有 `id` 字段**（`expedition_data_by_map` 用 `map` 当键），
    所以行标识取 `id` → 常见主键字段 → 容器键 三级回落，出处必须可回指，不能因为没 id 就丢。
    """
    out = []
    if isinstance(doc, list):
        for i, r in enumerate(doc):
            if isinstance(r, dict):
                out.append((i, r))
        return out
    for k, v in (doc or {}).items():
        if not isinstance(v, dict):
            continue
        keys = list(v.values())[:6]
        if 'id' in v or (keys and any(not isinstance(x, dict) for x in keys)):
            rid = v.get('id')
            if rid is None:
                for alt in ('map', 'key', 'group', 'chapter', 'idx'):
                    if v.get(alt) is not None:
                        rid = v[alt]
                        break
            if rid is None:
                rid = k
            out.append((rid, v))
        else:
            out.extend(rows_of(v, '%s/%s' % (path, k)))
    return out


def cn_label(row):
    for k in LABEL_FIELDS:
        v = row.get(k)
        if isinstance(v, str) and CJK.search(v):
            return k, v.strip()
    return None, None


def build(verbose=False):
    """只产**精确引用事实**：某表的背景语义字段整值 == 盘上某张 png 名。

    原设计里还有一层"bgm 名模板 `story-<root>-stageN` 反推章节"，实测**否掉**：
    `memory_storyline` 99 行里只有 16 行的 `bgm` 是 `story-*` 形状（其余是 `main-newyear`/`bsm-7`
    等别的命名族），能对上 png 词根的只剩 4 个 ⇒ 覆盖面太小且每跳都在猜，不如不做。
    同 root 兄弟图的中文名改由 `scripts/build_bg_meta.py` 从这些精确事实**组内传播**得到，
    标"推断"并带出处计数 —— 事实面与显示策略分开。
    """
    names = png_names()
    if not names:
        print('[WARN] Output/Raw 不在盘上，exact 面会空（页面就没有确定名了）')
    exact = {}
    for fn in sorted(os.listdir(LUAJ)):
        if not fn.endswith('.json'):
            continue
        tbl = fn[:-5]
        try:
            doc = json.load(open(os.path.join(LUAJ, fn), encoding='utf-8'))
        except Exception as e:
            print('  ! %s 读不了: %s' % (fn, e))
            continue
        for rid, r in rows_of(doc):
            rk, rcn = cn_label(r)
            for f, v in r.items():
                if not isinstance(v, str) or not BG_FIELD.match(f) or BAD_FIELD.search(f):
                    continue
                if v in names:
                    exact.setdefault(v, []).append(
                        {'t': tbl, 'f': f, 'id': rid, 'cn': rcn or '', 'cnf': rk or ''})
    if verbose:
        cn = sum(1 for k, v in exact.items() if any(x['cn'] for x in v))
        print('exact 命中 png %d 个（其中有中文标签 %d 个）/ 盘上 png %d 个'
              % (len(exact), cn, len(names)))
    return exact, names


def selfcheck(exact, names):
    seen, dup_ok = set(), True
    for v in exact.values():
        for x in v:
            k = (x['t'], x['f'], x['id'])
            if k in seen:
                dup_ok = False
            seen.add(k)
    cn_pngs = sum(1 for k, v in exact.items() if any(x['cn'] for x in v))
    return [
        ('每条 exact 都带可回指的出处 (表/字段/行标识，行标识允许是容器键)',
         all(x['t'] and x['f'] and x['id'] is not None for v in exact.values() for x in v)),
        ('exact 的键都是盘上真存在的 png 名（不产悬空名）',
         all(k in names for k in exact)),
        ('每条带中文标签的记录，标签确实含中文',
         all(bool(CJK.search(x['cn'])) for v in exact.values() for x in v if x['cn'])),
        ('有中文名的 png 不低于地板值 %d（实测 2026-10-07 = %d；掉了说明字段白名单或表源变了）'
         % (MIN_CN_PNGS, cn_pngs), cn_pngs >= MIN_CN_PNGS),
        ('同一 (表,字段,行) 不重复登记', dup_ok),
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
    for s in ('tools/sharecfg_re/41_export_lua_tables.py', 'tools/sharecfg_re/49_publish_bg_scene.py'):
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

    exact, names = build(verbose=True)
    covered = sum(1 for n in names if any(x['cn'] for x in exact.get(n, [])))
    print('有精确中文名的覆盖: %d / %d png (%.1f%%)'
          % (covered, len(names), 100 * covered / max(1, len(names))))
    ok = True
    for desc, passed in selfcheck(exact, names):
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
                       'exact': {k: exact[k] for k in sorted(exact)}},
                      ensure_ascii=False, indent=1, sort_keys=True)
    blob = body.encode('utf-8')
    os.makedirs(DST, exist_ok=True)
    # 二进制写：文本模式在 Windows 把 \n 变 \r\n，台账 bytes/sha256 就对不上（§103）
    with open(os.path.join(DST, OUT_FN), 'wb') as f:
        f.write(blob)
    entry = {'path': OUT_FN, 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest(),
             'rows': len(exact), 'role': ROLE, 'consumers': CONSUMERS,
             'source': '.diag/sharecfg_re/lua_json/*.json（773 张表全扫，只收背景语义字段的整值引用）',
             'coverage': '精确中文名 %d/%d png (%.1f%%)' % (covered, len(names), 100 * covered / max(1, len(names)))}
    led = merge_ledger(entry)
    with open(os.path.join(DST, 'MANIFEST.json'), 'w', encoding='utf-8') as f:
        json.dump(led, f, ensure_ascii=False, indent=1)
    print('\n[WRITE] inputs/gamecfg/%s（%d 条精确引用）+ 台账已更新' % (OUT_FN, len(exact)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
