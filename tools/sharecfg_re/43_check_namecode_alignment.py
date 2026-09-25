#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E3：证明「台词里的 `{namecode:NNN}` 用的就是 `name_code.id`」——带零假设对照，只读。

三条各自独立的检验（任一不过就报"未证成"，不许用"看起来对"糊过去）：
  T1 名称合法性：占位符引用的 N，在 name_code 里解出的名字，必须是**游戏里真实存在的实体名**
     （命中 ship_data_statistics 的舰名 / 已知 NPC 名）。随机编号不会全落在真名字上。
  T2 自称率：一行台词属于皮肤 X，而 X 的舰名 == name_code[N].name 的 (行, N) 对数
     vs **把 N 随机重分配给行**的同一统计（零假设）。真对齐应当显著高于对照。
  T3 人工可读：把若干整行按 T1 的映射就地替换，打印出来供人眼判语义是否通顺
     （例：`被{namecode:98}欺负…保护指挥官的钱包` → `被明石欺负…`，明石=商店猫，语义自洽）。

用法: py -3 tools/sharecfg_re/43_check_namecode_alignment.py [--rows 12]
"""
import json, os, random, re, sys, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
D = os.path.join(ROOT, '.diag', 'sharecfg_re', 'cfg_json_scalar')
PAT = re.compile(r'\{namecode:(\d+)\}')
# 舰名之外的已知实体（商店/秘书舰/剧情 NPC 等），来自 name_code 表自身与项目已有认知
EXTRA = {'明石', '甫', '罗恩', '构建者'}


def load(nm):
    return json.load(open(os.path.join(D, nm + '.json'), encoding='utf-8'))


def main():
    words = load('ship_skin_words')
    skin = load('ship_skin_template')
    stats = load('ship_data_statistics')
    nc = json.load(open(os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_json', 'name_code.json'), encoding='utf-8'))
    by_id = {int(r['id']): r for r in nc.values() if isinstance(r, dict) and 'id' in r and 'name' in r}
    ship_names = {r.get('name') for r in stats.values() if isinstance(r, dict) and isinstance(r.get('name'), str)}
    group2name = {}
    for r in stats.values():
        if isinstance(r, dict) and r.get('id') is not None and isinstance(r.get('name'), str):
            group2name[str(r['id'])] = r['name']
    for r in stats.values():
        if isinstance(r, dict) and isinstance(r.get('name'), str):
            group2name.setdefault(str(r.get('id')), r['name'])

    # 每行：占位符码集合 + 该行的舰名（words.id -> skin.id -> ship_group -> stats.name）
    rows = []
    for wid, w in words.items():
        if not isinstance(w, dict):
            continue
        codes = set()
        for v in w.values():
            if isinstance(v, str):
                codes.update(int(m) for m in PAT.findall(v))
        if not codes:
            continue
        sk = skin.get(wid) or {}
        own = group2name.get(str(sk.get('ship_group'))) or (sk.get('name') if isinstance(sk.get('name'), str) else None)
        rows.append((wid, sorted(codes), own, w))
    print('含占位符的行 %d；(行,码) 对 %d；name_code 可解析 id %d 个'
          % (len(rows), sum(len(r[1]) for r in rows), len(by_id)))

    # --- T1 名称合法性 ---
    allc = [c for _r in rows for c in _r[1]]
    known = sum(1 for c in allc if c in by_id and (by_id[c]['name'] in ship_names or by_id[c]['name'] in EXTRA))
    resolved = sum(1 for c in allc if c in by_id)
    print('\nT1 名称合法性：码能在 name_code 里查到 %d/%d (%.1f%%)；'
          '其中解出的名字确为游戏实体（舰名或已知 NPC）%d/%d (%.1f%%)'
          % (resolved, len(allc), 100.0 * resolved / max(1, len(allc)),
             known, len(allc), 100.0 * known / max(1, len(allc))))
    missN = [c for c in allc if c not in by_id]
    if missN:
        print('   查不到的码 %d 个，样例 %s（这些是"表里没有该 id"，不推翻对齐，但要记着）'
              % (len(set(missN)), sorted(set(missN))[:12]))

    # --- T2 自称率 vs 零假设 ---
    def self_rate(pairs):
        hit = 0
        for _wid, codes, own, _w in pairs:
            if own and any(c in by_id and by_id[c]['name'] == own for c in codes):
                hit += 1
        return hit

    obs = self_rate(rows)
    rnd = []
    codes_pool = allc
    random.seed(7)
    for _ in range(200):
        sh = [(wid, random.sample(codes_pool, min(len(c), 6)), own, w) for (wid, c, own, w) in rows]
        rnd.append(self_rate(sh))
    m = sum(rnd) / len(rnd)
    print('\nT2 自称率：实测 %d/%d 行里有一个码解出的名字 == 该行自己的舰名 (%.2f%%)'
          % (obs, len(rows), 100.0 * obs / max(1, len(rows))))
    print('   零假设（把码随机重分配给行，200 次）均值 %.2f%%  区间 [%.2f%%, %.2f%%]  比值 %.1fx'
          % (100 * m / len(rows), 100 * min(rnd) / len(rows), 100 * max(rnd) / len(rows),
             obs / max(m, 1e-9)))
    print('   ⇒ 判据：比值 ≥3 才算对齐成立；<1.5 判否；中间记"样本不足"')

    # --- T3 就地替换给人读 ---
    n = int(sys.argv[sys.argv.index('--rows') + 1]) if '--rows' in sys.argv else 12
    print('\nT3 就地替换（前 %d 行，只换查得到的码）：' % n)
    shown = 0
    for wid, codes, own, w in rows:
        for k, v in w.items():
            if not (isinstance(v, str) and PAT.search(v)):
                continue
            r = PAT.sub(lambda m: '[' + (by_id[int(m.group(1))]['name'] if int(m.group(1)) in by_id else '?') + ']', v)
            print('   %-8s %-11s 舰名=%-10s %s' % (wid, k, own or '-', r[:110]))
            shown += 1
            break
        if shown >= n:
            break
    return 0


if __name__ == '__main__':
    sys.exit(main())
