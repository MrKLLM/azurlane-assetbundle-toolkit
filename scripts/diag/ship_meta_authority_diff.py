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
 2) 条目集合不得增减（新增/丢失都算红）；
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
import importlib.util
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FIELDS = ('cn', 'en', 'faction', 'type', 'rarity', 'category', 'base_painting')
PROTECTED = ('painting', 'suffix')                 # 本来就走配置桥，必须零改动
NEW_OK = ('painting_ci', 'suffix_ci', 'npc_table', 'npc_suffix', 'npc_family', 'family')


def load_new():
    path = os.path.join(ROOT, 'scripts', 'build_ship_meta.py')
    spec = importlib.util.spec_from_file_location('bsm', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    skin, stats, wiki = mod.load()
    meta, _, _, _ = mod.build_meta(skin, stats, wiki)
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
    new = {}
    for g, vs in by_group.items():
        cand = [s for s in vs if s.get('skin_id') == base.get(g)] or vs
        new[g] = min(cand, key=lambda x: x['id'])
    return old, new, base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--expect-unresolved', type=int, default=3)
    ap.add_argument('--out', default=os.path.join(ROOT, '.diag', 'ship_meta_authority_diff.tsv'))
    a = ap.parse_args()

    old = json.load(open(os.path.join(ROOT, 'Output', 'ship_meta.json'), encoding='utf-8'))
    new, wiki, mod, skin, stats = load_new()
    fails = []
    painting2skin, _pci, _sbg = mod.build_indexes(skin, stats)
    old_pick, new_pick, base_of = stats_picks(mod, skin, stats)
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

    npc_ok = [t for t in hard if justified(t)]
    fix_ok = [t for t in hard if not justified(t) and base_fix(t)]
    bad = [t for t in hard if not justified(t) and not base_fix(t)]
    groups_fixed = {new[t[0]].get('base_painting') for t in fix_ok}
    print('1) 受保护档(painting/suffix) %d 条 -> 字段改动 %d 处：'
          '"皮肤标题→NPC 实体名" %d 处（逐条回查表） + "脏 stats 行→基皮肤行" %d 处 / %d 组（方向性判据）'
          '，其余 %d 处（须为 0）'
          % (sum(1 for v in old.values() if v.get('source') in PROTECTED),
             len(hard), len(npc_ok), len(fix_ok), len(groups_fixed), len(bad)))
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

    add = [k for k in new if k not in old]
    drop = [k for k in old if k not in new]
    print('2) 条目集合：新增 %d 丢失 %d（须均为 0）' % (len(add), len(drop)))
    if add or drop:
        fails.append('条目集合变化')

    illegal = [(k, old[k].get('source'), new[k]['source'])
               for k in old if k in new
               and new[k]['source'] != old[k].get('source')
               and new[k]['source'] not in NEW_OK]
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
