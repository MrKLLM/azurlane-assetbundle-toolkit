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

另一个维度 `has_char`（画面里有没有角色）来自 `inputs/gamecfg/bg_char_flags.json`
（`scripts/publish_bg_char_flags.py` 发布的人工逐格标注），背景页的**默认视图**靠它筛。
⚠️ 该文件只覆盖场景背景：登录/其他类目从没判过，所以那些条目**不带这个字段**，
页面必须把"没字段"和"字段=0"区分开——否则 604 张没判过的图会被静默藏掉。

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
import hashlib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'Output', 'Raw')
REFS = os.path.join(ROOT, 'inputs', 'gamecfg', 'bg_scene_refs.json')
TITLES = os.path.join(ROOT, 'inputs', 'gamecfg', 'bg_tip_titles.json')
# 词根→中文名的确定性词典（tools/sharecfg_re/50_publish_bg_roots.py 发布，可缺：缺了就退回 series）
ROOT_LABELS = os.path.join(ROOT, 'inputs', 'gamecfg', 'bg_root_labels.json')
# 场景背景「画面里有没有角色」的人工逐格标注（scripts/publish_bg_char_flags.py 发布，可缺：
# 缺了页面就没有筛选依据，会退回「全部」并显式说明——不许静默降级）
CHARS = os.path.join(ROOT, 'inputs', 'gamecfg', 'bg_char_flags.json')
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

# 一级分组：页面只出这三个类目 chip，`other` 组点开才展开子类目（用户 2026-10-07 定的折叠）。
# 折叠的依据不是"张数少"，是**这 6 类在配置表里零引用** —— 它们和 bg/loadingbg 不在同一个证据面上。
GROUP_OF_DIR = {
    'bg': 'scene',
    'loadingbg': 'login', 'loadingbg_hx': 'login',
    'helpbg': 'other', 'commonbg': 'other', 'worldhelpbg': 'other',
    'newshipbg': 'other', 'lotterybg': 'other', 'backyardbg': 'other',
}
GROUP_LABELS = {
    'scene': ('场景背景', '游戏内场景/关卡/活动 CG 底图，配置表有逐张引用'),
    'login': ('登录/加载底图', '登录界面与加载图；`_hx` 是和谐版，合并进同一类目'),
    'other': ('其他', '帮助/通用/世界地图说明/新舰登场/建造抽卡/后宅底图 —— 配置表零引用的界面底图'),
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
        # `_hx` 与主目录合并成一个类目：`dir` 是**展示类目**，`root_dir` 才是盘上真目录
        # （img/thumb 仍按 root_dir 走，key 也不变 —— 同名跨类目会互相吞，见文件头）。
        disp = 'loadingbg' if d == 'loadingbg_hx' else d
        it = {
            'key': key, 'dir': disp, 'root_dir': d, 'name': name,
            'group': GROUP_OF_DIR.get(d, 'other'),
            'variant': 'hx' if d == 'loadingbg_hx' else '',
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

    # 合并 `_hx` 后类目内会出现**逐字节相同**的重复卡（那张本来就不需要和谐处理，
    # 或它的内容正好等于 P0 补回来的 `__N` 那张）。留着就是重复卡，但"丢重复"必须先证
    # "同内容那张确实在保留集里"——否则就是 §118 那一类静默少图。
    def _sha(it):
        p = os.path.join(RAW, it['root_dir'], it['name'] + '.png')
        h = hashlib.sha256()
        with open(p, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                h.update(chunk)
        return h.hexdigest()

    # 去重范围 = **整个登录类目**，不是"hx vs 同名主图"：P0 把主图换成大图之后，
    # `_hx` 那张小的现在和 `bg_1__2` 同内容了 —— 只按同名配对会漏，合并类目就多出重复卡。
    # 保留优先级：非 _hx > 非 __N > 名字序；被丢的每条都记 `same_as`，可回溯、可复原。
    login = [i for i in items if i['dir'] == 'loadingbg']
    rank = lambda i: (1 if i.get('variant') else 0, '__' in i['name'], i['name'])
    first = {}
    for it in sorted(login, key=rank):
        first.setdefault(_sha(it), it)
    keep_id = {id(first[k]) for k in first}
    dropped_identical = [{'key': i['key'], 'same_as': first[_sha(i)]['key']}
                         for i in login if id(i) not in keep_id]
    items = [i for i in items if i['dir'] != 'loadingbg' or id(i) in keep_id]

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

    # has_char：**只有标注覆盖到的键才带这个字段**。登录/其他类目从没判过，
    # 给它们补 0 会让默认视图把 604 张没判过的图静默藏掉（页面要区分"没字段"与"字段=0"）。
    cmap = (json.load(open(CHARS, encoding='utf-8')).get('labels', {})
            if os.path.isfile(CHARS) else {})
    for it in items:
        if it['key'] in cmap:
            it['has_char'] = int(cmap[it['key']])

    for it in items:
        d, name = it['key'].split('/', 1)
        it['w'], it['h'] = px_size(os.path.join(RAW, d, name + '.png'))

    # 一级分组与「场景背景」二级分组的展示数据：页面不许自己从目录名/词根现推中文
    groups = {g: {'cn': GROUP_LABELS[g][0], 'via': GROUP_LABELS[g][1],
                  'count': sum(1 for i in items if i['group'] == g)}
              for g in ('scene', 'login', 'other')}
    # 二级分组只给场景背景：按词根，词根中文名取该组里出现最多的 series（拿不到就留词根本身，
    # 页面标 `cn_from:'root'` 让人看得出这条不是资产名）
    roots = {}
    for i in items:
        if i['group'] != 'scene' or not i['root']:
            continue
        r = roots.setdefault(i['root'], {'n': 0, 'series': collections.Counter()})
        r['n'] += 1
        if i.get('series'):
            r['series'][i['series']] += 1
    # 词根中文名的**权威顺序**：拼音整值词典 > series 传播 > 词根原文。
    # series 排第二是因为它会错：实测 `star_level`（264 张抽象底纹）被同词根的别张图
    # 传播来一个「响彻于天穹之音」—— 名字看着像、其实与这组无关。词典有值时一律压过它。
    RL = (json.load(open(ROOT_LABELS, encoding='utf-8'))['labels']
          if os.path.isfile(ROOT_LABELS) else {})
    named = {}
    for k, v in roots.items():
        if v['n'] < 2:
            continue
        d = RL.get(k)
        if d:
            named[k] = {'n': v['n'], 'cn': d['cn'], 'cn_from': 'pinyin'}
        elif v['series']:
            named[k] = {'n': v['n'], 'cn': v['series'].most_common(1)[0][0], 'cn_from': 'series'}
        else:
            named[k] = {'n': v['n'], 'cn': k, 'cn_from': 'root'}
    roots = named

    if sample:
        want = set(sample)
        picked = [it for it in items
                  if it['name'] in want or it['key'] in want or it['dir'] in want]
        return items, root_labels, picked, dropped_identical, groups, roots
    return items, root_labels, None, dropped_identical, groups, roots


def stats(items):
    t = collections.Counter(i['tier'] for i in items)
    d = collections.defaultdict(lambda: collections.Counter())
    for i in items:
        d[i['dir']][i['tier']] += 1
        d[i['dir']]['total'] += 1
    return t, d


def _sha_equal(k1, k2):
    """两个 <目录>/<名> 键指向的文件是否逐字节相同。"""
    def h(k):
        d, n = k.split('/', 1)
        import hashlib
        return hashlib.sha256(open(os.path.join(RAW, d, n + '.png'), 'rb').read()).hexdigest()
    return h(k1) == h(k2)


def selfcheck(items, t, dropped=None):
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
        ('每张 item 都有一级分组，且只有 scene/login/other 三档',
         all(i.get('group') in ('scene', 'login', 'other') for i in items)),
        ('_hx 已并进 loadingbg 类目、但 root_dir 仍可回溯到盘上真目录（img/thumb 不会指错）',
         all(i['root_dir'] == 'loadingbg_hx' and os.path.isfile(os.path.join(RAW, 'loadingbg_hx', i['name'] + '.png'))
             for i in items if i.get('variant') == 'hx')),
        ('被当重复丢掉的 _hx，其同内容主图确实在保留集里且逐字节相同（丢重复≠丢图）',
         all(any(i['key'] == d['same_as'] for i in items)
             and _sha_equal(d['key'], d['same_as']) for d in (dropped or []))),
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
    items, root_labels, picked, dropped, groups, roots = res
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
    for desc, passed in selfcheck(items, t, dropped):
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
    # 词根表闸门：必须排在 --check 的提前 return **之前**，否则 --check 模式压根不触发它
    rl = (json.load(open(ROOT_LABELS, encoding='utf-8'))['labels']
          if os.path.isfile(ROOT_LABELS) else {})
    for desc, passed in [
        # 下限断言：词典文件没了 / 被清空时，上面几条会**全部空转报绿**，
        # 名字会静默退回 series —— 这条负责让它响。
        ('词典在位且有 >=15 组（缺文件不许静默退回 series）', len(rl) >= 15),
        ('词根表非空，且来源只有 pinyin/series/root 三档',
         bool(roots) and all(v['cn_from'] in ('pinyin', 'series', 'root') for v in roots.values())),
        ('pinyin 档逐字等于词典值（索引与页面都不许改写或自己升档）',
         all(roots[k]['cn'] == rl[k]['cn'] for k in roots
             if roots[k]['cn_from'] == 'pinyin' and k in rl)),
        ('词典里 >=2 张的词根全部进了 pinyin 档（接了词典又静默漏用要能看见）',
         all(k in roots and roots[k]['cn_from'] == 'pinyin' for k in rl if rl[k]['n'] >= 2)),
        ('series 档不可能压过词典已有的词根（star_level 那种错传播就是这么来的）',
         all(roots[k]['cn_from'] != 'series' or k not in rl for k in roots)),
    ]:
        print('%s %s' % ('OK ' if passed else 'FAIL', desc))
        ok &= passed

    # 「画面里有没有角色」这一维：发布件**可以缺**（缺了背景页退回「全部」并写明原因），
    # 但在位时必须逐字透传，且不许越界标到从没标注过的类目。
    cf = json.load(open(CHARS, encoding='utf-8')) if os.path.isfile(CHARS) else None
    marked = [i for i in items if 'has_char' in i]
    print('%s 标注发布件在位（缺了则背景页默认视图退回「全部」，不静默改判）'
          % ('OK ' if cf else 'WARN'))
    if cf:
        for desc, passed in [
            ('场景背景每张都带 has_char（默认视图不许藏掉"没判过"的场景图）',
             all('has_char' in i for i in items if i['group'] == 'scene')),
            ('has_char 值域只有 0/1（裁定没收敛就不该有这份发布件）',
             set(i['has_char'] for i in marked) <= {0, 1}),
            ('非场景类目不带 has_char（没判过 ≠ 无角色，不许被默认视图隐藏）',
             not any(i['group'] != 'scene' for i in marked)),
            ('逐字等于发布件的值（索引不许自己改判）',
             all(i['has_char'] == cf['labels'][i['key']] for i in marked)),
            ('条数与有角色数同发布件 counts 一致',
             len(marked) == len(cf['labels'])
             and sum(i['has_char'] for i in marked) == cf['counts']['has']),
        ]:
            print('%s %s' % ('OK ' if passed else 'FAIL', desc))
            ok &= passed
        print('  画面: 有角色 %d / 无角色 %d / 未标注 %d（默认视图只隐藏"无角色"）'
              % (sum(1 for i in marked if i['has_char']),
                 len(marked) - sum(1 for i in marked if i['has_char']),
                 n - len(marked)))
    if not ok:
        print('\n闸门：红 —— 断言未全过，不写文件')
        return 1
    if a.check:
        print('\n闸门：绿（--check 未写文件）')
        return 0

    n_has = sum(1 for i in items if i.get('has_char') == 1)
    n_no = sum(1 for i in items if i.get('has_char') == 0)
    doc = {'schema': 3,
           'groups': groups,
           'roots': roots,
           'dropped_identical': dropped,
           'char': ({'has': n_has, 'none': n_no, 'unlabeled': n - n_has - n_no,
                     'source': 'inputs/gamecfg/bg_char_flags.json',
                     'note': '背景页默认视图只隐藏 has_char==0（人工逐格标注，仅覆盖场景背景）；'
                             'unlabeled 的 %d 张从没判过，照常显示，不许当成"无角色"藏掉'
                             % (n - n_has - n_no)} if cf else None),
           'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
           'source': 'inputs/gamecfg/bg_scene_refs.json',
           'note': 'tier=exact 是配置表逐张引用；baked 是图内烤字（OCR+目视双路径，见 inputs/gamecfg/bg_tip_titles.json）；'
                   'inferred 是同词根兄弟图传播（页面要标「推断」）；none 无中文名，页面显示英文原名，不得编造',
           'sources': {'exact': 'inputs/gamecfg/bg_scene_refs.json',
                       'baked': 'inputs/gamecfg/bg_tip_titles.json',
                       'has_char': 'inputs/gamecfg/bg_char_flags.json'},
           'dirs': {d: {'cn': lbl, 'via': via, 'count': per[d]['total']}
                    for d, (lbl, via) in DIR_LABELS.items() if d in per},
           'counts': dict(t),
           # 排序走**一级组**而不是目录名：按 dir 排的话「全部」视图开头两张是
           # backyardbg（b 打头），用户第一眼看到的是全库最小的类目而不是主力场景背景
           'items': sorted(items, key=lambda i: (
               {'scene': 0, 'login': 1, 'other': 2}.get(i['group'], 3),
               i['dir'], i['name']))}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print('\n[WRITE] %s（%d 条 / %.1f KB）'
          % (os.path.relpath(OUT, ROOT).replace('\\', '/'), n, os.path.getsize(OUT) / 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
