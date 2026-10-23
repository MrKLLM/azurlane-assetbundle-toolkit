#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""权威源切换回归闸门：`build_ship_meta.py` 的解析优先级被改动后，改前/改后逐字段比对。

为什么需要：立绘名从「大小写敏感的精确匹配」改成「精确 → 大小写不敏感 → NPC 表 → 同族前缀」后，
受影响的不只是原来无源的目录，还会**接管**原先靠手抄表 `SHIP_NAME_MAP` / `MANUAL` 兜底的那一批
（实测 138 个）。这类改动的正确判据不是"什么都不能变"，而是"只允许在预期的档位上变"。

四条硬判据（任一不满足退出码 1，退出码即结论）：
 1) 旧条目里 source ∈ {painting, suffix} 的（本来就走配置桥命中的），7 个字段必须一字不改；
    仅两类改动可自动放行，且都必须**回查表**、不许凭空放行：
      a) `name_via=npc_table:*` 的「皮肤标题→秘书舰实体名」（原皮肤标题仍留在 skin_name）；
      b) **方向性判据** `base_fix`：该组的 stats 选行从「skin_id ≠ 基皮肤」换成「skin_id == 基皮肤」。
         这条用来吃掉 `ship_data_statistics` 里的脏行（name 写甲、english_name/nationality/type 是乙、
         且 id 更小，会钻「组内取 min(id)」的空子）。反向改动一律仍是红。
 2) 条目集合：丢失必须为 0；新增不得超过 `--expect-added`（取自 cfg.disk 报的皮肤行新增数，默认 0）；
 3) 名字来源档位只允许出现在白名单里（painting_ci/suffix_ci/npc_*/family），
    且不落在这四档的新档一律视为回退；
 4) 仍无源的条目数必须等于给定期望值（默认 3：_ab / unknown / tansuozhe21_2）。
另附一项**第三方裁判**（不作为闸门，只打印）：改名条目里"新值命中维基名表 / 旧值命中"的计数，
两边各自独立可算，用来区分"配置表纠正手抄表"与"手抄表本来更对"。

用法:
  py -3 scripts/diag/ship_meta_authority_diff.py [--expect-unresolved 3] [--out .diag/ship_meta_diff.tsv]
"""
import argparse
import collections
import collections
import importlib.util
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FIELDS = ('cn', 'en', 'faction', 'type', 'rarity', 'category', 'base_painting')
# 本来就走配置桥（含 META 补桥表）的档，必须零改动；要改只能落进方向性判据。
# ⚠️ `bridge` 也在受保护档里：补桥条目一旦成档，后面的填值（稀有度/CV）就得逐条盖章，
#    不然"权威源换了但没人核对"这条洞会原样留着（§108 第一轮就是这么漏过去的）。
PROTECTED = ('painting', 'suffix', 'bridge', 'bridge_suffix')
NEW_OK = ('painting_ci', 'suffix_ci', 'npc_table', 'npc_suffix', 'npc_family', 'family',
          'bridge', 'bridge_suffix')


def bridge_fix(t, new_entry, old_entry):
    """方向性判据：META 实体从「剥后缀折进本体船」改成「补桥表里她自己那一行」，只放行这一个方向。

    改前 `lingmin_alter` 的 `source=suffix`、`base_painting=lingmin` —— 阵营/舰种/稀有度/英文名/CV
    全部来自**本体灵敏**（北方联合/精锐/花井美春）。补桥表（§108）之后她挂自己的组号 970113。
    于是这一类改动里**允许出现"字段变空"**（`en`/`rarity`/`voice_actor`），因为那些值本来就是错贴的；
    拦的是反方向与无出处的接管：
      · 新 source 必须是 `bridge`/`bridge_suffix`，且带 `meta_via`（三张表的连接串）与 `meta_group`；
      · 旧值必须是"剥后缀剥出来的另一实体"：`base_painting != 本键`，即旧口径里她根本没有自己的行；
      · 阵营只允许从本体船换成 META（反向 META → 本体一律红）。
    """
    k, f, a, b = t
    ns = str(new_entry.get('source') or '')
    if not ns.startswith('bridge') or not new_entry.get('meta_via') or not new_entry.get('meta_group'):
        return False
    osrc = str(old_entry.get('source') or '')
    if osrc.startswith('bridge'):
        # 第二种合法改动（§108 第二轮）：**同一张补桥条目内**，把补桥表里显式声明过的稀有度从空填上。
        # 只放行「空 → 有」，且新条目必须带 `confirmed_via`（声明出处），反向（有 → 空 / 换个值）一律红。
        return (f in ('rarity', 'rarity_code') and not str(a).strip()
                and bool(str(b).strip()) and bool(new_entry.get('confirmed_via')))
    if osrc not in ('painting', 'suffix'):
        return False
    if str(old_entry.get('base_painting') or '') == k:
        return False                       # 旧口径已经有她自己那一行 ⇒ 这条不该被桥接管
    if f == 'faction':
        return b == 'META'
    return f in ('cn', 'en', 'type', 'rarity', 'category', 'base_painting',
                 'voice_actor', 'voice_actor_name', 'skin_name',
                 'nationality_code', 'type_code', 'rarity_code', 'meta_group',
                 'voice_bank', 'meta_via', 'source')


def row_backed(t, tab_paint):
    """「有据升级」判据（提到模块级是为了能被反向对照测到 —— 闸门里的判据没法测就等于橡皮章）。

    新 base 必须同时满足：①权威皮肤表里**确实有这一行**；②是本名的前缀（同族回退，不是随便换个名）；
    ③比旧值更贴近本名（更长）。反向（从近退回远）、表里查无此行、改的不是 base_painting 一律 False。
    """
    k, f, a, b = t
    if f != 'base_painting' or not a or a == b:
        return False
    kl, bl = k.lower(), str(b).lower()
    return bl in tab_paint and kl.startswith(bl) and len(bl) > len(str(a))


def dup_row_fix(t, bp, rows_by_paint, picked, groups_with_stats):
    """方向性判据：同一 painting 在皮肤表里有**多行**时，只放行「无配音且查不到舰级行 → 有配音且查得到」这一个方向。

    背景：自机化时游戏不新增 painting 目录，而是给同一个 painting **再加一行**（带真
    `voice_actor` 和一个能在 `ship_data_statistics` 里查到的 `ship_group`）。旧代码
    `painting2skin.setdefault()` 让迭代序第一行（剧情那行）胜出 ⇒ 17 张已自机化的卡
    （11 张 META + 霞飞/阿尔及利亚/不屈/沃克兰/弗兰德尔/加斯科涅）显示「无阵营 + 无语音」。

    和 `row_backed` 一样放在模块级：闸门里的判据没法测就等于橡皮章。
    它是一条**任何组都能套、且只放行正确方向**的规则，不是给那 17 张卡开的后门：
      · 该 painting 必须真的有多行（单行一律 False，防"其实没换行也放行"）；
      · `rows[0]` 是旧规则(setdefault)的胜行，必须不满足 good、新行必须满足 good
        —— 反向（把有 CV 的换成没 CV 的）一律红；
      · 只允许行派生的字段；`category` 还额外要求 story→ship 这一个方向。
    影响面由 `diag/painting_dup_probe.py` 用同一套 good 定义独立复核。
    """
    k, f, a, b = t
    if f not in ('cn', 'en', 'faction', 'type', 'rarity', 'category'):
        return False
    rows = rows_by_paint.get(bp) or []
    if len(rows) < 2:
        return False
    old_r, new_r = rows[0], picked.get(bp)
    if old_r is None or new_r is None or old_r.get('id') == new_r.get('id'):
        return False

    def good(r):
        return (r.get('voice_actor') or -1) > 0 and r.get('ship_group') in groups_with_stats

    if not good(new_r) or good(old_r):
        return False
    return (a, b) != ('ship', 'story') if f == 'category' else True


def load_new(work=None):
    path = os.path.join(ROOT, 'scripts', 'build_ship_meta.py')
    spec = importlib.util.spec_from_file_location('bsm', path)
    mod = importlib.util.module_from_spec(spec)
    # importlib 直接 exec 模块时，`sys.path[0]` 不是 scripts/（那是 `python scripts/x.py` 才有的），
    # 于是 build_ship_meta 里的兄弟模块导入（skin_table）会 ModuleNotFoundError。
    # 只在这台机器上"看起来能跑"的闸门等于没有闸门 —— 显式把 scripts/ 放进去。
    d = os.path.dirname(path)
    if d not in sys.path:
        sys.path.insert(0, d)
    spec.loader.exec_module(mod)
    skin, stats, wiki = mod.load()
    meta, _, _, _ = mod.build_meta(skin, stats, wiki, work=work)
    return meta, wiki, mod, skin, stats


def stats_picks(mod, skin, stats):
    """复算「组 -> 选中的 stats 行」在新旧两条规则下各是什么，供闸门判定改动方向。

    旧规则：组内取 min(stats.id)。新规则：先要求 skin_id == 该组基皮肤（id 最小的皮肤行），
    再取最小 id。脏行能钻旧规则的空子（name 写着甲、english_name/nationality/type 是乙，
    且 id 更小），新规则把它筛掉。"""
    skinid2skin = {v['id']: v for v in skin.values() if 'id' in v}
    by_group = {}
    for sv in stats.values():
        g = skinid2skin.get(sv.get('skin_id'), {}).get('ship_group')
        if g is not None:
            by_group.setdefault(g, []).append(sv)
    base = {}
    for v in skin.values():
        g = v.get('ship_group')
        if g in by_group and (g not in base or v['id'] < base[g]):
            base[g] = v['id']
    old = {g: min(vs, key=lambda x: x['id']) for g, vs in by_group.items()}
    cand_by_group = {}
    for g, vs in by_group.items():
        cand_by_group[g] = [s for s in vs if s.get('skin_id') == base.get(g)] or vs
    new = {g: min(vs, key=lambda x: x['id']) for g, vs in cand_by_group.items()}
    # 第三条规则（今天的正本）：候选集内取「(nationality,type,rarity) 众数」那一族的
    # 非占位英文名行，族内优先「id == 基皮肤 id」的配对行，再 min(id)。
    # `maj` 与 `support` 供 `majority_fix` / `pair_tiebreak` 判方向。
    # ⚠️ 选行必须 import 正本 `pick_stats_row`，不许在这里手抄一份——抄一份就会和
    #    `build_indexes` 漂移，下面那条「复算行 == 正本实际选行」的自检就变成橡皮章。
    TUPLE = lambda r: (r.get('nationality'), r.get('type'), r.get('rarity'))
    support, maj = {}, {}
    for g, vs in cand_by_group.items():
        support[g] = collections.Counter(TUPLE(r) for r in vs)
        maj[g] = mod.pick_stats_row(vs, base.get(g))
    return old, new, base, maj, support, TUPLE


def pair_rescue(t, new_entry, old_entry, stats_by_id, skinid2skin, clean_ship_name):
    """方向性判据：皮肤行所在组查不到任何 stats 行时，只放行「无舰级 → 同名配对行有舰级」。

    `ship_data_statistics` 与 `ship_skin_template` 在 900xxx 段的约定是 **stats.id 与 skin.id 同号**
    （`qiye_dark` 两侧都是 900072/900135），但游戏有少数行的 `skin_id` 写歪了：
    `aisaikesi_alter` 那行（id 900406，name 埃塞克斯·META）对应的 stats 行 id 也是 900406，
    `skin_id` 却指向 900550 ⇒ 按 ship_group 永远查不到它，卡片显示「无阵营」。
    判据全部可回查，且反向（有舰级 → 无）一律 False：
      · 新条目带 `stats_via=id_pair:<id>`，且盘上确有该 id 的 stats 行与皮肤行；
      · 那一行的 id == 皮肤行的 id，且清洗后的 `name` 两侧相同；
      · `base_painting` 就是那个皮肤行的 painting，`cn` 就是配对行的 name；
      · 旧条目阵营必须为空（只是补回来，不是换掉）。
    """
    k, f, a, b = t
    if f not in ('cn', 'en', 'faction', 'type', 'rarity', 'category'):
        return False
    if str(old_entry.get('faction') or ''):
        return False
    via = str(new_entry.get('stats_via') or '')
    if not via.startswith('id_pair:'):
        return False
    try:
        sid = int(via.split(':', 1)[1])
    except ValueError:
        return False
    sv, sk = stats_by_id.get(sid), skinid2skin.get(sid)
    if not sv or not sk:
        return False
    if str(sk.get('painting') or '').strip().lower() != str(new_entry.get('base_painting') or '').strip().lower():
        return False
    n1, n2 = clean_ship_name(sv.get('name') or ''), clean_ship_name(sk.get('name') or '')
    return bool(n1) and n1 == n2 and new_entry.get('cn') == n1


def pair_tiebreak(t, g, base_id, prev_pick, maj_pick, TUPLE):
    """方向性判据：众数**并列**时只放行「min(id) 行 → id == 基皮肤 id 的配对行」，反向 False。

    `majority_fix` 要求新行支持度严格大于旧行，并列时它必然 False —— 那正是这条的入口：
    组 900550（萨拉托加·META 的剧情行，`npcsalatuojia_alter.png` 与 `salatuojia_alter.png`
    md5 逐字节相同）里 id=900406 写「埃塞克斯·META」、id=900550 写「萨拉托加·META」，
    三列全同而 900406 更小 ⇒ min(id) 把埃塞克斯·META 顶在了萨拉托加的图上。
    """
    k, f, a, b = t
    if f not in ('cn', 'en', 'faction', 'type', 'rarity') or g is None:
        return False
    o, n = prev_pick.get(g), maj_pick.get(g)
    if o is None or n is None or o['id'] == n['id']:
        return False
    return (TUPLE(o) == TUPLE(n) and n.get('id') == base_id
            and o.get('id') != base_id)


def majority_fix(t, g, support, prev_pick, maj_pick, TUPLE):
    """方向性判据：组内候选行自相矛盾时，只放行「少数派行 → 多数派行」这一个方向。

    §56 那次只补了「先要求 skin_id == 基皮肤」，但脏行**可以本身就是基皮肤行**：
    `ship_data_statistics` 的 id=900399 单条把 加斯科涅 的 nationality 写成 2(皇家)、
    id=900398 单条把 弗兰德尔 的 type 写成 18(超巡)，而同组其余 5 行都是 9/5。
    于是「组内 min(id)」让 1 条 outlier 压掉 5 条一致行。

    判据是可回查的支持度比较，不是"新值看起来更顺眼"：
      · 必须是同一个 painting 组、且确实换了行；
      · 新行的 (阵营,舰种,稀有度) 组合在候选集里的支持度必须**严格大于**旧行；
        并列一律 False（拿不出多数派就不许自动放行）；
      · 反向（多数派→少数派）支持度变小，天然被这条挡住。
    第二条单向子句：同族（三列全同）之内只允许「占位英文名 → 真英文名」改 `en`，反向一律 False。
    """
    k, f, a, b = t
    if f not in ('cn', 'en', 'faction', 'type', 'rarity') or g is None:
        return False
    o, n = prev_pick.get(g), maj_pick.get(g)
    if o is None or n is None or o['id'] == n['id']:
        return False
    cnt = support.get(g)
    if cnt and cnt[TUPLE(n)] > cnt[TUPLE(o)]:
        return True
    # 同族之内的另一种单向改善：旧行 `english_name` 是占位（空 / `simulation`，全表 44 行），
    # 新行是真英文名。只放行 `en` 这一列——同族里两行的 `name` 也可能不同（§93 那类
    # 「（后排）」后缀），那属于另一条判据的范围，不许混在这里一起盖章。
    PH = ('', 'simulation')
    return (f == 'en' and TUPLE(n) == TUPLE(o)
            and str(o.get('english_name') or '').strip().lower() in PH
            and str(n.get('english_name') or '').strip().lower() not in PH)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--expect-unresolved', type=int, default=3)
    ap.add_argument('--expect-added', type=int, default=0,
                    help='允许的新增条目数，取自 cfg.disk 报出的皮肤表新增行数'
                         '（默认 0 = 不允许任何新增，与旧行为一致）')
    ap.add_argument('--out', default=os.path.join(ROOT, '.diag', 'ship_meta_authority_diff.tsv'))
    ap.add_argument('--work', default=None,
                    help='额外扫描的临时区（.diag/pipeline）；换入前的新皮肤只在临时区')
    a = ap.parse_args()

    old = json.load(open(os.path.join(ROOT, 'Output', 'ship_meta.json'), encoding='utf-8'))
    new, wiki, mod, skin, stats = load_new(a.work)
    fails = []
    painting2skin, _pci, _sbg, _sbid = mod.build_indexes(skin, stats)
    # 「同一 painting 多行」的原始候选集 + 「哪些 ship_group 查得到 stats 行」，供 dup_row_fix 回查
    rows_by_paint = {}
    for v in skin.values():
        p = v.get('painting')
        if p:
            rows_by_paint.setdefault(p, []).append(v)
    _sid2skin = {v['id']: v for v in skin.values() if 'id' in v}
    _stats_by_id = {v['id']: v for v in stats.values() if 'id' in v}
    groups_with_stats = {_sid2skin[s['skin_id']]['ship_group'] for s in stats.values()
                         if s.get('skin_id') in _sid2skin}
    old_pick, new_pick, base_of, maj_pick, support, TUPLE = stats_picks(mod, skin, stats)
    # 自检：闸门复算出的「众数代表行」必须**就是正本 `build_indexes` 实际选中的那一行**。
    # 不复算这一条，判据就是在给一个不存在的规则盖章。
    maj_drift = [g for g, r in maj_pick.items()
                 if _sbg.get(g) is not None and _sbg[g]['id'] != r['id']]
    # 只有这几列是从 stats 行派下来的，改它们才可能是「换 stats 行」引起的
    STATS_FIELDS = {'en', 'faction', 'type', 'rarity'}

    hard = [(k, f, old[k].get(f, ''), new[k].get(f, ''))
            for k in old if k in new and old[k].get('source') in PROTECTED
            for f in FIELDS if old[k].get(f, '') != new[k].get(f, '')]
    # 受保护档里唯一的合法例外：皮肤行没有舰级行时 cn 本来是「皮肤标题」，
    # 被秘书舰 NPC 表纠正成实体名（`name_via=npc_table`）。逐条回查表，不许凭空放行。
    npc_tab = json.load(open(os.path.join(ROOT, 'inputs', 'gamecfg', 'npc_painting_name.json'),
                             encoding='utf-8')) if os.path.exists(
        os.path.join(ROOT, 'inputs', 'gamecfg', 'npc_painting_name.json')) else {}

    def justified(t):
        k, f, a, b = t
        via = str(new[k].get('name_via') or '')
        key = via.split(':', 1)[1] if via.startswith('npc_table:') else ''
        return (f == 'cn' and key in npc_tab and b == npc_tab[key]['cn']
                and new[k].get('skin_name') == a)   # 原皮肤标题必须还留在 skin_name，不许丢

    def base_fix(t):
        """方向性判据：这条改动必须是「从非基皮肤的 stats 行 换成 基皮肤那一行」。
        反过来（从基皮肤行换走）一律算回退 —— 所以这不是给敦刻尔克开的后门，
        而是一条任何组都能套、且只放行正确方向的规则。"""
        k, f, a, b = t
        if f not in STATS_FIELDS:
            return False
        sk = painting2skin.get(new[k].get('base_painting'))
        g = (sk or {}).get('ship_group')
        o, n = old_pick.get(g), new_pick.get(g)
        return (o is not None and n is not None and o['id'] != n['id']
                and o.get('skin_id') != base_of.get(g)
                and n.get('skin_id') == base_of.get(g)
                and str(n.get('name') or '') == str(new[k].get('cn') or ''))

    # 「有据升级」：权威皮肤表里**确实有这一行**了，所以 base_painting 从"退到亲戚"变成"它自己"。
    # 这条专门服务数据源升级（设备侧表补出社区快照缺的行），判据是可回查的行存在性，
    # 不是"新值看起来更像名字" —— 所以它同样是一方向性判据：只允许 退让值 → 本名，反向一律算回退。
    tab_paint = {str(r.get('painting') or '').strip().lower()
                 for r in skin.values() if isinstance(r, dict)}


    def _dup(t):
        return dup_row_fix(t, new[t[0]].get('base_painting'), rows_by_paint,
                           painting2skin, groups_with_stats)

    def _maj(t):
        sk = painting2skin.get(new[t[0]].get('base_painting'))
        return majority_fix(t, (sk or {}).get('ship_group'), support,
                            new_pick, maj_pick, TUPLE)

    def _pair(t):
        return pair_rescue(t, new[t[0]], old[t[0]], _stats_by_id, _sid2skin,
                           mod.clean_ship_name)

    def _pairtie(t):
        sk = painting2skin.get(new[t[0]].get('base_painting'))
        g = (sk or {}).get('ship_group')
        return pair_tiebreak(t, g, base_of.get(g), new_pick, maj_pick, TUPLE)

    def _bridge(t):
        return bridge_fix(t, new[t[0]], old[t[0]])

    # 每条改动都必须落到某一条**方向性判据**上；落不进就是回退。
    # 判据之间互斥地按顺序取第一条成立的，所以计数不会重复计同一处。
    PROOFS = (('皮肤标题→NPC 实体名', justified),
              ('脏 stats 行→基皮肤行', base_fix),
              ('快照缺行→权威表已有行', lambda t: row_backed(t, tab_paint)),
              ('本体船行→META 补桥（允许去错贴值）', _bridge),
              ('剧情行→自机行', _dup),
              ('少数派脏行→多数派行', _maj),
              ('组无舰级行→同名 id 配对行', _pair),
              ('众数并列→id 配对行', _pairtie))

    def proof(t):
        for nm, fn in PROOFS:
            if fn(t):
                return nm
        return ''

    ok_by = collections.OrderedDict((nm, [t for t in hard if proof(t) == nm]) for nm, _ in PROOFS)
    bad = [t for t in hard if not proof(t)]
    fix_ok = ok_by['脏 stats 行→基皮肤行']
    dup_ok = ok_by['剧情行→自机行']
    maj_ok = ok_by['少数派脏行→多数派行']
    groups_fixed = {new[t[0]].get('base_painting') for t in fix_ok}
    dup_cards = sorted({t[0] for t in dup_ok})
    maj_groups = sorted({(painting2skin.get(new[t[0]].get('base_painting')) or {}).get('ship_group')
                         for t in maj_ok})
    print('1) 受保护档(painting/suffix) %d 条 -> 字段改动 %d 处，按方向性判据归类：'
          % (sum(1 for v in old.values() if v.get('source') in PROTECTED), len(hard)))
    for nm, ts in ok_by.items():
        print('   · %-22s %d 处' % (nm, len(ts)))
    print('   其余 %d 处（须为 0）| 复算众数行与正本选行不一致 %d 组（须为 0）'
          % (len(bad), len(maj_drift)))
    print('   · 换行放行的卡 %d 张: %s' % (len(dup_cards), ' '.join(dup_cards) or '无'))
    print('   · 众数改判的组: %s' % (maj_groups or '无'))
    for g in sorted(groups_fixed):
        sk = painting2skin.get(g)
        o, n = old_pick.get((sk or {}).get('ship_group')), new_pick.get((sk or {}).get('ship_group'))
        print('   · %s: 旧行 id=%s %r/%s nat=%s type=%s  ->  新行 id=%s %r/%s nat=%s type=%s'
              % (g, o['id'], o.get('name'), o.get('english_name'), o.get('nationality'), o.get('type'),
                 n['id'], n.get('name'), n.get('english_name'), n.get('nationality'), n.get('type')))
    for t in bad[:8]:
        print('   ! %s %s: %r -> %r' % t)
    if bad:
        fails.append('受保护档被改动')
    if maj_drift:
        fails.append('闸门复算的众数行与正本 build_indexes 实际选行不一致')

    add = [k for k in new if k not in old]
    drop = [k for k in old if k not in new]
    # 「新增」的合法上限由 `cfg.disk` 报出的**皮肤表新增行数**给出（`--expect-added`）：
    # 硬要求"增删为 0"等于把"游戏出新角色"这件事本身判成回退，闸门会在每次更新后必红。
    # 丢失仍然零容忍——元数据条目不会因为更新而消失。
    print('2) 条目集合：新增 %d（期望 ≤%d，取自 cfg_delta）丢失 %d（须为 0）'
          % (len(add), a.expect_added, len(drop)))
    if len(add) > a.expect_added:
        print('   新增样例: %s' % ', '.join(add[:10]))
        fails.append('新增条目数超过 cfg.disk 报出的差分')
    if drop:
        print('   丢失样例: %s' % ', '.join(drop[:10]))
        fails.append('条目集合丢失')

    illegal = [(k, old[k].get('source'), new[k]['source'])
               for k in old if k in new
               and new[k]['source'] != old[k].get('source')
               and new[k]['source'] not in NEW_OK
               # 唯一允许的额外换档：升到 `painting`（直查权威表命中），且这一行**确实在表里**。
               # 与上面 row_backed 同源同判据，不接受"看起来更准"。
               and not (new[k]['source'] == 'painting' and k.lower() in tab_paint)]
    moved = collections.Counter((old[k].get('source'), new[k]['source'])
                                for k in old if k in new and new[k]['source'] != old[k].get('source'))
    print('3) 换档条目 %d 个，非法新档 %d（须为 0）' % (sum(moved.values()), len(illegal)))
    for (a1, b1), n in sorted(moved.items(), key=lambda kv: -kv[1]):
        print('   %-10s -> %-12s %d' % (a1, b1, n))
    if illegal:
        fails.append('出现白名单外的新档')

    un = [k for k, v in new.items() if v['source'] == 'unresolved']
    print('4) 仍无源 %d 个（期望 %d）: %s' % (len(un), a.expect_unresolved, un))
    if len(un) != a.expect_unresolved:
        fails.append('无源数量不符')

    # 第三方裁判：维基名表投票（只打印，不作闸门）
    wn = {w.get('name') for w in wiki if isinstance(w, dict) and w.get('name')}
    ren = [(k, old[k]['cn'], new[k]['cn']) for k in old
           if k in new and old[k]['source'] not in ('unresolved',) and old[k].get('cn') != new[k].get('cn')]
    print('\n[裁判] 改名 %d 处：新值命中维基名表 %d · 旧值命中 %d · 仅旧值命中 %d（>0 需人看）'
          % (len(ren), sum(1 for r in ren if r[2] in wn), sum(1 for r in ren if r[1] in wn),
             sum(1 for r in ren if r[1] in wn and r[2] not in wn)))
    for r in [x for x in ren if x[1] in wn and x[2] not in wn][:10]:
        print('   ! 手抄表更可能对: %s %s -> %s' % r)
    print('[裁判] 补名 %d 个 · category story->ship %d 个'
          % (sum(1 for k in old if old[k]['source'] == 'unresolved' and new[k]['source'] != 'unresolved'),
             sum(1 for k in old if old[k]['category'] == 'story' and new[k]['category'] == 'ship')))

    with open(a.out, 'w', encoding='utf-8') as fh:
        fh.write('类型\tstem\t旧值\t新值\t新来源\n')
        for k in sorted(old):
            if k not in new:
                continue
            if old[k].get('cn') != new[k].get('cn'):
                fh.write('%s\t%s\t%s\t%s\t%s\n'
                         % ('补名' if old[k]['source'] == 'unresolved' else '改名',
                            k, old[k].get('cn', ''), new[k].get('cn', ''), new[k]['source']))
            if old[k]['category'] != new[k]['category']:
                fh.write('category\t%s\t%s\t%s\t%s\n'
                         % (k, old[k]['category'], new[k]['category'], new[k]['source']))
    print('\n明细 -> %s' % a.out)
    if fails:
        print('闸门：红 — ' + '；'.join(fails))
        return 1
    print('闸门：绿')
    return 0


if __name__ == '__main__':
    sys.exit(main())
