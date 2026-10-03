# -*- coding: utf-8 -*-
"""语音缺口审计（只读）：把「🔇 无语音」的皮肤按**可救性**分类，而不是只数总数。

为什么需要：`extract_cv_voice.py` 的 miss 列表只有一个名字清单，看不出哪些是
「等游戏下发就行」、哪些是「需要人来裁定后缀语义」、哪些是「其实正文已经在手，只是没声音」。
三者的下一步动作完全不同，混在一个 354 的数字里就没法拍板。

分类（互斥，按优先级）：
  no-pack-device-also-missing  包号推得出、盘上无主包 —— §49 已证设备侧同样没有 ⇒ 只能等下发
  no-row-suffix               表里没有这张图，剥掉某个「身份后缀」才有行 ⇒ 需逐后缀裁定语义
  no-row-unknown              表里查不到、剥后缀也查不到 ⇒ 名字对不上，需单独看
  ship-without-cv             该皮肤 voice_actor 为 0/-1（这艘船本就没有 CV）⇒ 结构性无解
  other

并交叉「正文可得性」：**直接查权威表** `inputs/gamecfg/ship_skin_words.json`（键 = 皮肤表**主键 id**，
按 painting 查表得到，⚠️ 不是 `cv*10+idx`——那个算式在皮肤序号 ≥10 处会撞进隔壁船的行，见 §86），
不看 `skin_words.json` 的 `m`——那张 `m` 是 `build_skin_words.py` 只遍历
`skin_voice.json` 里已解析出声的皮肤建出来的，拿它问「无解皮肤有没有正文」是循环判据，
恒为 0 且不构成证据。一批「没声音」的皮肤正文其实齐全，可以只做字幕不做点击播放。

用法：py -3 scripts/diag/voice_gap_audit.py [--json .diag/voice_gap_audit.json]
"""
import os, sys, re, json, argparse, collections

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import extract_cv_voice as E          # 复用同一套解析器，判据不允许两处各写一份

CUE_DIR = E.CUE_DIR
WORDS = os.path.join(ROOT, 'inputs', 'gamecfg', 'ship_skin_words.json')
# 身份后缀候选：VAR 里的「画法变体」已由解析器处理，这里只剥没被处理的那一类
TAIL_TOKEN = re.compile(r'_[a-z]+$')


def cue_files_for(cv):
    """盘上与该语音包号相关的全部文件名（含 -battle/-gift 等变体包）。"""
    pref = 'cv-%d' % cv
    return [f for f in os.listdir(CUE_DIR) if f.startswith(pref)]


def strip_to_row(ml, rows):
    """反复剥掉尾部字母 token，直到命中皮肤表；返回 (命中的 painting 键, 剥掉的后缀列表)。"""
    gone = []
    s = ml
    while True:
        if s in rows:
            return s, gone
        m = TAIL_TOKEN.search(s)
        if not m:
            return None, gone
        gone.append(m.group(0))
        s = s[:m.start()]


def drill(out, keys):
    """对「皮肤表里查无此名」这一类再查一层：到底是不参与配音的 NPC 皮肤，还是我们漏接线。

    判据只用游戏自己的表：① 有没有出现在秘书舰 NPC 图名表里；② 两份皮肤表里有没有**任何**同族行；
    ③ 语音包号是从行里推的——没行就没包号、也没台词行（台词表按行 id 索引）⇒ 本机零线索。
    ⚠️ 这只证"本机数据里没有"，不证"游戏里也没有"；后者要么按耳朵要么看游戏内界面。
    """
    npc = json.load(open(os.path.join(ROOT, 'inputs', 'gamecfg', 'npc_painting_name.json'), encoding='utf-8'))
    sc = json.load(open(os.path.join(ROOT, '.diag', 'sharecfg_re', 'cfg_json_scalar',
                                     'ship_skin_template.json'), encoding='utf-8'))
    sc_p = {str(r.get('painting') or '').strip().lower() for r in sc.values() if isinstance(r, dict)}
    unk = [r for r in out if r['cls'] == 'no-row-unknown']
    by_fam = collections.defaultdict(list)
    for r in unk:
        by_fam[E.ship_stem(r['skin'].lower())].append(r['skin'])
    print('\n查无此名的 %d 张，按同族归并成 %d 族：'
          % (len(unk), len(by_fam)))
    n_npc = n_family_row = 0
    for fam in sorted(by_fam):
        ks = sorted(by_fam[fam])
        innpc = [k for k in ks if k in npc or E.VAR.sub('', k) in npc]
        kin = [k for k in ks if k in sc_p]
        famrow = [p for p in sc_p if p == fam or p.startswith(fam + '_') or p.startswith(fam)]
        n_npc += len(innpc)
        n_family_row += len(kin)
        print('  %-18s %2d 张  NPC图名表 %2d  表里有此名 %2d  同族在表里 %s  例 %s'
              % (fam, len(ks), len(innpc), len(kin), len(famrow), ks[0]))
    print('  合计：命中 NPC 图名表 %d 张 / 表里直接有此名 %d 张 ⇒ '
          '这两份都不等于"游戏里没配音"，只等于"本机推不出包号，也就没有台词行"' % (n_npc, n_family_row))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default=os.path.join(ROOT, '.diag', 'voice_gap_audit.json'))
    ap.add_argument('--drill', action='store_true', help='只对「查无此名」类再查一层 NPC 归属')
    args = ap.parse_args()

    rows = E.load_skin_rows()
    banks = E.banks_on_disk()
    keys = E.gallery_keys()
    res, miss = E.resolve(keys, rows, banks)

    skin_tbl = json.load(open(os.path.join(E.AZDATA, 'azdata_ship_skin_template.json'), encoding='utf-8'))
    va_by_painting = collections.defaultdict(list)
    for r in skin_tbl.values():
        if isinstance(r, dict) and r.get('painting'):
            va_by_painting[str(r['painting']).strip().lower()].append(int(r.get('voice_actor') or 0))
    words_by_id = json.load(open(WORDS, encoding='utf-8'))

    def voiceless(painting_key):
        """该 painting 的每一行 voice_actor 都是 0 ⇒ 这艘船本就没有 CV。

        ⚠️ `-1` **不算**：实测 35 张已经解析出语音、`skin_voice.json` 里能播的皮肤，
        其皮肤表行就是 `-1` —— 它是「本行未单独配置（继承）」，判成无 CV 会把
        140 张「缺包（可等下发）」错标成「结构性无解」，等于自己造一条否证。"""
        va = va_by_painting.get(painting_key) or []
        return bool(va) and all(v == 0 for v in va)

    # 「这张图到底是独立皮肤，还是同一皮肤的另一张画法」的非循环证据：
    # 皮肤表里一行 = 一个皮肤（一个 painting），数一数盘上有多少个文件名剥掉后缀后落在同一行。
    # >1 ⇒ 这一行本来就有多张画法（`_hx` 和谐版、`_n` 无背景版就是已被承认的先例），
    #      于是 `_wjz`/`_ex` 这类再多一张也是同一皮肤的另一张画法，继承它的音频与正文不违背语义；
    # ==1 且盘上只有带后缀那张 ⇒ 该行的画法是独占的，剥后缀等于把别的皮肤的台词派给它，不能做。
    attach = collections.defaultdict(list)
    for k in keys:
        ml = k.lower()
        base = E.VAR.sub('', ml)
        p = base if base in rows else None
        if p is None:
            p, _gone = strip_to_row(base, rows)
        if p is not None:
            attach[p].append(k)
    base_on_disk = {k.lower() for k in keys}

    def family_evidence(hit_key):
        fam = sorted(attach.get(hit_key, []))
        return {'row_files': len(fam), 'row_has_plain_name': hit_key in base_on_disk,
                'fam': fam}

    out = []
    for k in miss:
        ml = k.lower()
        rec = {'skin': k, 'text': 0}
        hit_key = ml if ml in rows else (E.VAR.sub('', ml) if E.VAR.sub('', ml) in rows else None)
        stripped = []
        if hit_key is None:
            hit_key, stripped = strip_to_row(E.VAR.sub('', ml), rows)
        if hit_key is None:
            rec.update(cls='no-row-unknown', cv=None, stripped=[], row_files=0, fam=[])
            out.append(rec)
            continue
        # 三元组 (语音包号, 包内档位, 表行主键)——主键只能查，不能再写 `cv*10+idx` 反推：
        # 皮肤序号 ≥10 的新批次那 28 行会被算成隔壁船的行（§86），这里跟着错过正文。
        cv, idx, row_id = rows[hit_key][0]
        sid = str(row_id)
        wrow = words_by_id.get(sid) or {}
        files = sorted(cue_files_for(cv))
        has_main = ('cv-%d.b' % cv) in files
        if voiceless(hit_key):
            cls = 'ship-without-cv'
        elif not files:
            cls = 'no-pack-device-also-missing'
        elif not has_main:
            cls = 'no-main-pack-only-variant'
        else:
            # 包在盘上却没解析出来，只可能是「剥了身份后缀才命中」⇒ 这一类是能救的，代价是裁定后缀语义
            cls = 'recoverable-by-suffix' if stripped else 'PARSED-BUT-MISS(矛盾)'
        rec.update(cls=cls, cv=cv, idx=idx, sid=sid, stripped=stripped,
                   on_disk=files, painting=hit_key, text=len(wrow),
                   **family_evidence(hit_key))
        out.append(rec)

    by = collections.Counter(r['cls'] for r in out)
    text_by = collections.Counter(r['cls'] for r in out if r['text'])
    suffix = collections.Counter(tuple(r.get('stripped') or ()) for r in out
                                if r['cls'] == 'recoverable-by-suffix')
    nodisk = collections.Counter(
        'only-variant-pack' if r.get('on_disk') else 'no-file-at-all'
        for r in out if r['cls'] in ('no-pack-device-also-missing', 'no-main-pack-only-variant'))
    cv_by_ship = collections.defaultdict(set)
    for r in out:
        if r['cls'] in ('no-pack-device-also-missing', 'no-main-pack-only-variant') and r.get('cv'):
            cv_by_ship[r['painting']].add(r['cv'])

    print('画廊皮肤 %d 张，可解析 %d，无解 %d' % (len(keys), len(res), len(miss)))
    print('\n按可救性分类（正文=权威表 ship_skin_words 里该皮肤行有台词，与音频是否在盘上无关）')
    for c, n in by.most_common():
        print('  %-30s %4d   其中正文可得 %4d' % (c, n, text_by.get(c, 0)))
    print('  ----')
    print('  合计无解 %d，正文可得 %d' % (len(out), sum(1 for r in out if r['text'])))
    print('\n缺包侧细分：', dict(nodisk), ' 涉及语音包号 %d 个' % len({c for s in cv_by_ship.values() for c in s}))
    print('\n剥掉身份后缀即可命中（包就在盘上）——每个后缀都要人裁定是不是另一个发声实体')
    print('  非循环证据 = 皮肤表里这一行在盘上挂了几张画法（`_hx`/`_n` 已是被承认的先例）')
    for s, n in suffix.most_common(20):
        rs = [r for r in out if r['cls'] == 'recoverable-by-suffix'
              and tuple(r['stripped']) == s]
        ok = sum(1 for r in rs if r['row_files'] > 1 and r['row_has_plain_name'])
        print('  %-12s %3d 张  正文 %3d  同一行已挂多张画法 %3d'
              % (','.join(s) or '(空)', n, sum(1 for r in rs if r['text']), ok))
    for s in (('_wjz',), ('_ex',), ('_heihua',), ('_idolns',), ('_pt',), ('_blueprint',)):
        r = next((x for x in out if tuple(x.get('stripped') or ()) == s), None)
        if r:
            print('   %s → 表行 %s，盘上挂: %s' % (r['skin'], r['painting'], ', '.join(r['fam'])))
    unk = [r['skin'] for r in out if r['cls'] == 'no-row-unknown']
    print('\n表里完全查不到的皮肤名（前 20）: %s' % ', '.join(unk[:20]))
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, 'w', encoding='utf-8') as f:
        json.dump({'gen': __file__, 'total': len(keys), 'resolved': len(res),
                   'total_miss': len(out), 'by_class': dict(by), 'detail': out},
                  f, ensure_ascii=False, indent=1)
    print('\n明细 → %s' % os.path.relpath(args.json, ROOT))
    if args.drill:
        drill(out, keys)
    return 0


if __name__ == '__main__':
    main()
