# -*- coding: utf-8 -*-
"""「皮肤 → 包内语音档位」取证：用科目指纹给每个待分配皮肤定档，并自报这套方法错多少。

背景（§86）：`extract_cv_voice.assign_pending_idx()` 过去按"目录名排序 + 取最低空档"分配档位，
是**位置猜测**。本脚本换成两条游戏自己的证据：

  1. **包号是权威的**：皮肤表 `ship_group` 就是语音包号（实测 `aisaikesi_10` 行 137090 →
     ship_group **10709**、`z23_10` 行 431232 → 40123、`qiye_10` 行 137061 → 10706）。
     所以"借哪个包"根本不用猜。
  2. **档位在包内有指纹**：游戏只为"这一档真的录了"的科目留 `_N` 文件；而台词表里该皮肤那一行
     **恰好只对那些科目有词**。两个集合做 Jaccard，正确档通常就是最高分。

⚠️ 方法本身有错率，所以脚本**先自评再出结论**：在"档位由行号权威给出"的皮肤上跑同一套打分，
报 top-1（唯一命中）/ 含并列 / 未命中 三档。只有自评命中率足够高、且某个皮肤的判定**明显压过次优**
时才叫"判死"，其余一律标"存疑"交人工——**不许把统计优势当权威**。

用法:
  py -3 scripts/diag/voice_tier_forensics.py            # 自评 + 全库待分配组判定表
  py -3 scripts/diag/voice_tier_forensics.py --ships aisaikesi,z23
输出: .diag/voice_tier_forensics.tsv（逐皮肤：现网档 / 指纹档 / 分差 / 判定）
"""
import os, sys, csv, json, argparse, itertools, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import extract_cv_voice as E      # noqa: E402
import skin_table                 # noqa: E402

GAMECFG = os.path.join(ROOT, 'inputs', 'gamecfg')
AUDIO = os.path.join(ROOT, 'Output', 'Audio', 'CV2')
SV = os.path.join(ROOT, 'Output', 'gallery_v2', 'skin_voice.json')
OUT = os.path.join(ROOT, '.diag', 'voice_tier_forensics.tsv')


def field2cue():
    """台词字段名 → cue 科目名（唯一一份映射来源：`character_voice.resource_key`）。"""
    cvt = json.load(open(os.path.join(GAMECFG, 'character_voice.json'), encoding='utf-8'))
    return {k: (r.get('resource_key') or '').strip() for k, r in cvt.items()
            if (r.get('resource_key') or '').strip()}


def row_cues(sid, words, f2c):
    """某皮肤行「游戏为它单独写了词」的科目集合；`main` 用 `|` 合并 → 展开成 main_1..k。"""
    r = words.get(str(sid)) or {}
    out = set()
    for f, v in r.items():
        if not (v or '').strip():
            continue
        c = f2c.get(f)
        if c:
            out.add(c)
        elif f == 'main':
            out |= {'main_%d' % i for i, x in enumerate([x for x in v.split('|') if x.strip()], 1)}
    return out


_tier_cache = {}


def tier_cats(cv):
    """一个包里「第 N 档独有的科目」：{档位: {科目}}（档位 0 = 基础档）。"""
    if cv in _tier_cache:
        return _tier_cache[cv]
    d = os.path.join(AUDIO, 'cv-%d' % cv)
    m = collections.defaultdict(set)
    if os.path.isdir(d):
        for f in os.listdir(d):
            if not f.endswith('.ogg'):
                continue
            cat, s, ev = E.split_cue(f[:-4])
            if cat:
                m[s or 0].add(cat)
    _tier_cache[cv] = m
    return m


def score(rc, have):
    u = len(rc | have)
    return len(rc & have) / u if u else 0.0


def rank(cv, rc, exclude_base=True):
    """包内各档对该科目集合的打分（降序）。"""
    m = tier_cats(cv)
    sc = {t: score(rc, s) for t, s in m.items() if not (exclude_base and t == 0)}
    return sorted(sc.items(), key=lambda kv: (-kv[1], kv[0])), sc


def selfcheck(sv, rows, words, f2c):
    """自评：档位由行号权威给出的那批皮肤，用同一套打分能不能把它排第一。"""
    top1 = tie = miss = 0
    for k, e in sv.items():
        if not e['src'].startswith(('row', 'strip')) or not e['idx']:
            continue
        sid = E.row_id_for(k.lower(), rows, e['cv'])
        if sid is None:
            continue
        rc = row_cues(sid, words, f2c)
        if not rc or not tier_cats(e['cv']):
            continue
        best, _ = rank(e['cv'], rc)
        if not best:
            continue
        b = best[0][1]
        win = {t for t, v in best if abs(v - b) < 1e-9}
        if e['idx'] in win:
            top1 += len(win) == 1
            tie += len(win) > 1
        else:
            miss += 1
    tot = top1 + tie + miss
    return top1, tie, miss, tot


def decide_group(skins, rows, words, f2c, sv):
    """一个 (包, 船) 里若干待分配皮肤 → 枚举双射，取总分最高；报与次优的差距。"""
    cv = sv[skins[0]]['cv']
    claimed = {e['idx'] for k, e in sv.items()
               if e['cv'] == cv and e['src'].startswith(('row', 'strip'))}
    free = sorted(set(tier_cats(cv)) - claimed - {0})
    rcs = {}
    for k in skins:
        sid = E.row_id_for(k.lower(), rows, cv)
        rcs[k] = row_cues(sid, words, f2c) if sid is not None else set()
    if not free or not any(rcs.values()):
        return []
    pool = free if len(free) >= len(skins) else free
    out = []
    perms = [p for p in itertools.permutations(pool, len(skins))] if len(skins) <= 6 else []
    scored = sorted(((sum(score(rcs[s], tier_cats(cv).get(t, set())) for s, t in zip(skins, p)), p)
                     for p in perms), key=lambda x: -x[0]) if perms else []
    best = scored[0] if scored else (0.0, None)
    second = scored[1][0] if len(scored) > 1 else None
    for i, s in enumerate(skins):
        t = best[1][i] if best[1] else None
        alone = sorted(((score(rcs[s], tier_cats(cv).get(x, set())), x) for x in pool),
                       key=lambda kv: -kv[0])
        gap = (alone[0][0] - alone[1][0]) if len(alone) > 1 else alone[0][0] if alone else 0.0
        verdict = ('存疑·无指纹' if not rcs[s] else
                   '判死' if alone and gap >= 0.15 and (second is None or best[0] - second >= 0.1)
                   else '倾向' if alone and alone[0][0] > 0 else '存疑')
        out.append(dict(skin=s, cv=cv, now=sv[s]['idx'], src=sv[s]['src'],
                        sid=E.row_id_for(s.lower(), rows, cv), nkeys=len(rcs[s]),
                        free=free, pick=t, own_top=alone[0][1] if alone else None,
                        gap=round(gap, 3), grp_gap=round((best[0] - second), 3) if second is not None else None,
                        verdict=verdict))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ships', default='', help='逗号分隔船名（stem），默认全部')
    ap.add_argument('--out', default=OUT)
    a = ap.parse_args()
    sv = json.load(open(SV, encoding='utf-8'))
    words = json.load(open(os.path.join(GAMECFG, 'ship_skin_words.json'), encoding='utf-8'))
    f2c = field2cue()
    rows = E.load_skin_rows()

    t1, tie, miss, tot = selfcheck(sv, rows, words, f2c)
    print('自评（档位由行号权威给出的 %d 个皮肤，同一套打分）：唯一命中 %d (%.1f%%) · 并列 %d (%.1f%%) · 未命中 %d (%.1f%%)'
          % (tot, t1, 100 * t1 / max(tot, 1), tie, 100 * tie / max(tot, 1), miss, 100 * miss / max(tot, 1)))
    print('  ⇒ 这套指纹的**上界错误率**约 %.1f%%（并列 + 未命中），所以只用于给歧义组排序，不自动改产物。'
          % (100 * (tie + miss) / max(tot, 1)))

    ships = {s.strip().lower() for s in a.ships.split(',') if s.strip()} or None
    pend = collections.defaultdict(list)
    for k, e in sv.items():
        if e['src'].startswith('sibling'):
            st = E.ship_stem(k.lower())
            if ships and st not in ships:
                continue
            pend[(e['cv'], st)].append(k)
    art_only = {g for g, ks in pend.items() if len(ks) == 1}
    print('\n待分配组 %d 个（其中单皮肤组 %d 个 = 由排除法直接定档，无需指纹）'
          % (len(pend), len(art_only)))
    recs = []
    for (cv, st), ks in sorted(pend.items()):
        roots = [k for k in ks if E.art_root(k, {x.lower() for x in sv}) == k.lower()]
        recs += decide_group(sorted(roots), rows, words, f2c, sv)
    hdr = ['皮肤', '包号', '现网档', '来源', '真行id', '指纹科目数', '候选空档', '指纹档',
           '单皮肤最高分差', '整组最优领先次优', '判定']
    with open(a.out, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t')
        w.writerow(hdr)
        for r in recs:
            w.writerow([r['skin'], r['cv'], r['now'], r['src'], r['sid'], r['nkeys'],
                        ','.join(map(str, r['free'])), r['pick'], r['gap'], r['grp_gap'], r['verdict']])
    print('\n%-20s %-8s %-6s %-6s %-8s %-6s %s' % ('皮肤', '现网档', '指纹档', '一致?', '单档分差', '组领先', '判定'))
    for r in recs:
        print('%-20s %-8s %-6s %-6s %-8s %-6s %s' % (
            r['skin'], r['now'], r['pick'], '==' if r['now'] == r['pick'] else '★不同',
            r['gap'], r['grp_gap'] if r['grp_gap'] is not None else '-', r['verdict']))
    diff = [r for r in recs if r['now'] != r['pick'] and r['pick'] is not None]
    print('\n指纹与现网分配不一致的 %d 个 / 共判定 %d 个；明细 → %s' % (len(diff), len(recs), a.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
