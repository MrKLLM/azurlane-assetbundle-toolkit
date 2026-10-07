#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_bg_meta.py — 给 `Output/Raw/` 的 1,897 张背景图生成带中文命名的图库索引。

产 `Output/bg_meta.json`，供 `Output/gallery_v2/backgrounds.html` 消费。

三档命名口径（**页面必须如实分档，不许把推断当确定名**）：
  exact    —— 本图自己被某表的背景语义字段整值引用，且该行有中文 name/title ⇒ 直接给中文关卡名
  baked    —— 配置表查不到，但**名字烤在图像素里**（`*_tip` 横幅那一族）⇒ 由
              `scripts/ocr_bg_tip_titles.py` 走「OCR 模板位 + 3× 放大目视」双路径发布，
              证据强度与"表字段整值"不同源，页面要单列一档，不与 exact 混
  inferred —— 本图自己没有引用，但同**词根**（剥掉 `bg_` 前缀与 `_cgN/_N/_cutN/_tip/_hx/_n` 等尾缀）
              的兄弟图有 ⇒ 继承该词根的中文标签众数，页面标「推断」并显示"同组 N 张已确定"
  none     —— 三档都没有 ⇒ 显示英文原名，**不编中文名**

数据源：`inputs/gamecfg/bg_scene_refs.json`（由 `tools/sharecfg_re/49_publish_bg_scene.py` 发布，
台账 `inputs/gamecfg/MANIFEST.json`）。⚠️ 不读 `.diag/`（权威输入不得住临时区，AGENTS.md）。

同名 png 会跨类目重复（实测 `bg_1` 同时在 loadingbg / loadingbg_hx / newshipbg），
所以**记录键是 `<dir>/<name>`**，按 name 去重会把 22 张图吞掉。

用法:
  py -3 scripts/build_bg_meta.py                    # 全量，写 Output/bg_meta.json
  py -3 scripts/build_bg_meta.py --sample a,b,c     # 只出这几张的记录到 .diag/bgscan/sample.txt，不写正式产物
  py -3 scripts/build_bg_meta.py --check            # 只跑统计与断言，不写文件
退出码：断言红即 1（红时不写文件）。
"""
import argparse
import collections
import datetime
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'Output', 'Raw')
REFS = os.path.join(ROOT, 'inputs', 'gamecfg', 'bg_scene_refs.json')
TITLES = os.path.join(ROOT, 'inputs', 'gamecfg', 'bg_tip_titles.json')
OUT = os.path.join(ROOT, 'Output', 'gallery_v2', 'bg_meta.json')
SAMPLE_TXT = os.path.join(ROOT, '.diag', 'bgscan', 'sample.txt')

TAIL = re.compile(r'(_?cg_?\d+|_cut\d+|_?\d+|_tip|_hx|_n|_bg|_new)$')
# `X__2` 是导出层为「同一个包里两张**同名但内容不同**的画」补的后缀（见 export_assets
# 的 dedupe=distinct）。查配置表与取词根都要先剥掉它 —— 但**不能**因此把两张都发「确定」名：
# 配置表按名字引用，同一个名字对应两张画时它分不清是哪一张，所以第 2 张起只给「推断」。
DUP_SUFFIX = re.compile(r'__\d+$')
# 中文标签清洗：游戏里写的是「起舞于天原之上·下篇|| ||CHAPTER EX||E.X.」，
# `||` 之后是排版串，`·` 之后是该章的小节 —— 系列名只取 `·` 前那一段。
GAME_SEP = re.compile(r'\|\|')
CHAPTER_SPLIT = re.compile(r'[·・]')

# 类目中文说明。标 `via` 说明它是**从出处表反推的**（哪张表在引用这一类目），
# 不是按目录名猜的；`none` 表示配置表里查不到引用面，只能显示英文类目名。
DIR_LABELS = {
    'bg':          ('场景背景', 'activity_sp_story.change_background / expedition_data_by_map.default_background 等 901 处引用'),
    'helpbg':      ('帮助说明底图', '配置表无引用（按类目名 help+bg 归类的界面图）'),
    'commonbg':    ('通用底图', '配置表无引用（按类目名归类）'),
    'loadingbg':   ('登录/加载底图', 'login.login_static 92 处 + gallery_config.illustration 10 处引用'),
    'loadingbg_hx': ('登录/加载底图（_hx 变体）', '与 loadingbg 同名集合；`_hx` 语义配置侧无出处，未定'),
    'newshipbg':   ('新舰登场底图', '配置表无引用（按类目名归类）'),
    'worldhelpbg': ('世界地图说明底图', '配置表无引用（按类目名归类）'),
    'lotterybg':   ('建造/抽卡底图', '配置表无引用（按类目名归类）'),
    'backyardbg':  ('后宅底图', '配置表无引用（按类目名归类）'),
}


def root_of(name):
    """bg_amahara_cg10 -> amahara。机械剥离，剥完剩什么就是什么，不做语义猜测。"""
    s = name[3:] if name.startswith('bg_') else name
    prev = None
    while prev != s and len(s) >= 4:
        prev = s
        s = TAIL.sub('', s)
    return s if len(s) >= 4 else ''


def series_of(cn):
    """从中文标签取**系列/章节名**：`起舞于天原之上·下篇|| ||CHAPTER EX` → `起舞于天原之上`。

    只有 `章节·小节` 形状（expedition 表）才给得出系列名；活动关卡标题
    （`EP1-3 云海之宴`）没有 `·`，返回空串 —— 宁可不显示系列名，也不把某一个小节名当系列名。
    """
    if not cn:
        return ''
    s = GAME_SEP.split(cn)[0].strip()
    parts = CHAPTER_SPLIT.split(s)
    return parts[0].strip() if len(parts) > 1 else ''


def pick_group(pool, ch):
    """从同词根的标签池里定「系列名 + 展示证据」。

    证据默认取出现次数最高的 3 条；但若系列名来自第 4 条之后的标签，**必须把它换进证据里** ——
    否则卡片上会出现一个在这张图的证据列表中查不到的系列名（实测 `bg_jufengv1_*` 的
    「飓风与自由群岛」正是这种：前 3 名是活动关卡标题 `EP2-4 淅淅索索` 等，章节名排在后面）。
    """
    ev = pool[:3]
    if ch:
        s = ch.most_common(1)[0][0]
        src = next((x for x in pool if series_of(x['cn']) == s), None)
        if src and src['cn'] not in [e['cn'] for e in ev]:
            ev = (pool[:2] + [src]) if len(pool) >= 3 else (pool + [src])
        return {'series': s, 'series_src': src['cn'] if src else '', 'evidence': ev}
    return {'series': '', 'series_src': '', 'evidence': ev}


def disk_items():
    """盘上每张背景图：(dir, name, 相对 gallery 根的路径, bytes)。"""
    if not os.path.isdir(RAW):
        return []
    out = []
    for d in sorted(os.listdir(RAW)):
        p = os.path.join(RAW, d)
        if not os.path.isdir(p):
            continue
        for f in sorted(os.listdir(p)):
            if not f.endswith('.png'):
                continue
            fp = os.path.join(p, f)
            out.append((d, f[:-4], fp, os.path.getsize(fp)))
    return out


def px_size(path):
    """只读 PNG 头拿尺寸（页面按宽高比排网格，避免图片加载完才重排）。"""
    try:
        import struct
        with open(path, 'rb') as fh:
            head = fh.read(24)
        if head[:8] != b'\x89PNG\r\n\x1a\n' or head[12:16] != b'IHDR':
            return 0, 0
        return struct.unpack('>II', head[16:24])
    except Exception:
        return 0, 0


def labels_of(ref_rows):
    """把同一张图的多条引用压成中文标签列表（按出现次数降序，去重）。"""
    c = collections.Counter(r['cn'] for r in ref_rows if r['cn'])
    return [{'cn': k, 'n': v,
             'src': [{'t': r['t'], 'f': r['f'], 'id': r['id']}
                     for r in ref_rows if r['cn'] == k][:3]}
            for k, v in c.most_common()]


def build(sample=None):
    if not os.path.isfile(REFS):
        print('[FAIL] 缺 %s —— 先跑 py -3 tools/sharecfg_re/49_publish_bg_scene.py' % REFS)
        return None
    exact = json.load(open(REFS, encoding='utf-8'))['exact']
    # 图内烤字是**第二条命名源**（OCR + 目视双路径），文件可以不存在（那就没有 baked 档）
    titles = (json.load(open(TITLES, encoding='utf-8'))['titles']
              if os.path.isfile(TITLES) else {})

    items = []
    for d, name, fp, size in disk_items():
        key = '%s/%s' % (d, name)
        base = DUP_SUFFIX.sub('', name)          # bg_1__2 -> bg_1
        rows = exact.get(base, [])
        own = labels_of(rows)
        t = titles.get(base)
        if own:
            tier, labels = 'exact', own
        elif t:
            tier, labels = 'baked', [{'cn': t['cn'], 'n': 1, 'src': [], 'via': t['via']}]
        else:
            tier, labels = 'none', []
        it = {
            'key': key, 'dir': d, 'name': name,
            'img': '../Raw/%s/%s.png' % (d, name),
            'thumb': 'bg_thumbs/%s/%s.webp' % (d, name),
            'bytes': size,
            'w': 0, 'h': 0,
            'root': root_of(base),
            'tier': tier,
            'cn': labels,
            'refs': [{'t': r['t'], 'f': r['f'], 'id': r['id']} for r in rows][:6],
        }
        if base != name:
            # 同名多张：配置表只认名字，认不出是哪一张 ⇒ 第 2 张起不发「确定」，只发「推断」，
            # 并把主图那条名字作为继承来源标出来（页面要显示「同名第 N 张」而不是冒充确定名）
            if tier in ('exact', 'baked'):
                it['same_name_of'] = base
                it['why'] = '同一个包里有两张内容相同命名的画，配置表按名引用无法区分是哪一张'
                it['tier'] = 'inferred'
                it['inferred_from'] = '%s/%s' % (d, base)
            else:
                it['same_name_of'] = base
        if t and tier == 'baked':
            # 保留机器读到的原文与重合度：定稿与 OCR 不一致时（`_11` 丢了「醺」）要能查是谁改的
            it['baked'] = {'ocr_raw': t['ocr_raw'], 'ocr_conf': t['ocr_conf'],
                           'overlap': t['overlap'], 'via': t['via']}
        items.append(it)

    # 组内传播：同词根的 exact 标签给没有自己引用的兄弟图
    by_root = collections.defaultdict(list)
    for it in items:
        if it['tier'] == 'exact' and it['root']:
            by_root[it['root']].extend(it['cn'])
    root_labels, root_group = {}, {}
    for r, lst in by_root.items():
        c, ch = collections.Counter(), collections.Counter()
        for x in lst:
            c[x['cn']] += x['n']
            s = series_of(x['cn'])
            if s:
                ch[s] += x['n']
        root_labels[r] = [{'cn': k, 'n': v} for k, v in c.most_common()]
        root_group[r] = pick_group(root_labels[r], ch)
    for it in items:
        grp = root_group.get(it['root'])
        own = series_of(it['cn'][0]['cn']) if it['cn'] else ''
        if own:
            it['series'], it['series_src'] = own, it['cn'][0]['cn']
        else:
            it['series'] = grp['series'] if grp else ''
            it['series_src'] = grp['series_src'] if grp else ''
        if it['tier'] == 'none' and it['root'] in root_labels:
            # 推断档不冒充"这张图具体在哪一关用过"：主名给**系列名**，具体关卡标题只当证据留着
            it['tier'] = 'inferred'
            it['cn'] = grp['evidence'] if grp else []
            it['inferred_from'] = it['root']
        elif not own and it['series'] and it['series_src'] and \
                it['series_src'] not in [x['cn'] for x in it['cn']]:
            # 确定档若系列名来自同组别张图的章节标签，把那条标签补进证据并标 `via=group`，
            # 否则卡片上会出现一个在这张图自己的证据里查不到的系列名。
            it['cn'] = it['cn'][:2] + [{'cn': it['series_src'], 'n': 0, 'src': [], 'via': 'group'}]

    for it in items:
        d, name = it['key'].split('/', 1)
        it['w'], it['h'] = px_size(os.path.join(RAW, d, name + '.png'))

    if sample:
        want = set(sample)
        picked = [it for it in items
                  if it['name'] in want or it['key'] in want or it['dir'] in want]
        return items, root_labels, picked
    return items, root_labels, None


def stats(items):
    t = collections.Counter(i['tier'] for i in items)
    d = collections.defaultdict(lambda: collections.Counter())
    for i in items:
        d[i['dir']][i['tier']] += 1
        d[i['dir']]['total'] += 1
    return t, d


def selfcheck(items, t):
    return [
        ('每张 item 的 key 唯一（同名跨类目没被吞）',
         len({i['key'] for i in items}) == len(items)),
        ('img 路径都指向盘上真实文件',
         all(os.path.isfile(os.path.join(ROOT, 'Output', i['img'][3:])) for i in items)),
        ('tier 四档穷尽（没有其它值，且 none 之外都必须有 cn）',
         set(t) <= {'exact', 'baked', 'inferred', 'none'}
         and all(i['cn'] for i in items if i['tier'] != 'none')),
        ('baked 档都带 via，且带 OCR 原文与重合度（图内文字这条源要可回溯）',
         all(i.get('baked', {}).get('via') and i['baked']['ocr_raw'] and 'overlap' in i['baked']
             for i in items if i['tier'] == 'baked')),
        ('exact 的每条 cn 都能回指出处 (表/字段/行标识)',
         all(r.get('t') and r.get('f') and r.get('id') is not None
             for i in items if i['tier'] == 'exact' for r in i['refs'])),
        ('inferred 都带 inferred_from（继承自哪个词根）',
         all(i.get('inferred_from') for i in items if i['tier'] == 'inferred')),
        ('系列名逐字来自它自己的出处标签(series_src)，且该标签出现在这张图的证据里（不许出现查不到的系列名）',
         all(i['series'] in i.get('series_src', '')
             and any(i.get('series_src') == x['cn'] for x in i['cn'])
             for i in items if i['series'])),
        ('尺寸读数没塌（w/h 为 0 的图不超过 1%）',
         sum(1 for i in items if not i['w']) <= len(items) // 100),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', help='逗号分隔的图名或类目，只出这几条记录，不写正式产物')
    ap.add_argument('--check', action='store_true', help='只跑统计与断言，不写文件')
    a = ap.parse_args()

    want = a.sample.split(',') if a.sample else None
    res = build(want)
    if res is None:
        return 2
    items, root_labels, picked = res
    t, per = stats(items)
    n = len(items)
    print('背景图 %d 张 / 词根 %d 个已拿到中文标签' % (n, len(root_labels)))
    for tier in ('exact', 'baked', 'inferred', 'none'):
        print('  %-9s %5d (%4.1f%%)' % (tier, t[tier], 100 * t[tier] / max(1, n)))
    # 优先级（exact > baked）在当前数据上是**空规则**：没有一张图同时有两种源。
    # 空转的判据不能报绿，所以这里只把它当观察量打印出来。
    both = [i['key'] for i in items if i.get('baked') and i['tier'] == 'exact']
    print('  同时有"表精确引用"和"图内烤字"的图: %d 张 %s'
          % (len(both), '(优先级规则当前未被触发)' if not both else both[:5]))
    print('\n按类目:')
    for d, c in sorted(per.items(), key=lambda kv: -kv[1]['total']):
        print('  %-13s 总 %4d  exact %3d  baked %2d  inferred %4d  none %4d   %s'
              % (d, c['total'], c['exact'], c['baked'], c['inferred'], c['none'],
                 DIR_LABELS.get(d, ('?', ''))[0]))

    ok = True
    for desc, passed in selfcheck(items, t):
        print('%s %s' % ('✓' if passed else '✗', desc))
        ok &= passed

    if want is not None:
        os.makedirs(os.path.dirname(SAMPLE_TXT), exist_ok=True)
        with open(SAMPLE_TXT, 'w', encoding='utf-8') as fh:
            fh.write('# 样本 %s\n\n' % a.sample)
            for it in picked:
                fh.write('== %s  [tier=%s]  系列名: %s\n'
                         % (it['key'], it['tier'], it['series'] or '(取不到)'))
                fh.write('   尺寸 %dx%d  %.2fMB  词根 %s\n' % (it['w'], it['h'], it['bytes'] / 1e6, it['root'] or '(无)'))
                for x in it['cn']:
                    fh.write('   中文名: %s  (出现 %d 次)\n' % (x['cn'], x['n']))
                    for s in x.get('src', []):
                        fh.write('       出处: %s.%s 行 %s\n' % (s['t'], s['f'], s['id']))
                if it['tier'] == 'none':
                    fh.write('   中文名: （无 —— 配置表里没有这张图的引用，按口径不许编）\n')
                if it.get('inferred_from'):
                    fh.write('   推断来源: 同词根 "%s" 的兄弟图\n' % it['inferred_from'])
            fh.write('\n(未匹配到请求的图名: %s)\n' % [w for w in want
                                                       if not any(it['name'] == w or it['key'] == w or it['dir'] == w for it in picked)])
        print('\n[样本] 写到 %s（%d 条）—— 未写正式产物' % (SAMPLE_TXT, len(picked)))
        return 0 if ok else 1
    if not ok:
        print('\n闸门：红 —— 断言未全过，不写文件')
        return 1
    if a.check:
        print('\n闸门：绿（--check 未写文件）')
        return 0

    doc = {'schema': 1,
           'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
           'source': 'inputs/gamecfg/bg_scene_refs.json',
           'note': 'tier=exact 是配置表逐张引用；baked 是图内烤字（OCR+目视双路径，见 inputs/gamecfg/bg_tip_titles.json）；'
                   'inferred 是同词根兄弟图传播（页面要标「推断」）；none 无中文名，页面显示英文原名，不得编造',
           'sources': {'exact': 'inputs/gamecfg/bg_scene_refs.json',
                       'baked': 'inputs/gamecfg/bg_tip_titles.json'},
           'dirs': {d: {'cn': lbl, 'via': via, 'count': per[d]['total']}
                    for d, (lbl, via) in DIR_LABELS.items() if d in per},
           'counts': dict(t),
           'items': sorted(items, key=lambda i: (i['dir'], i['name']))}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print('\n[WRITE] %s（%d 条 / %.1f KB）'
          % (os.path.relpath(OUT, ROOT).replace('\\', '/'), n, os.path.getsize(OUT) / 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
