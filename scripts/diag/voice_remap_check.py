# -*- coding: utf-8 -*-
"""只读重算 `skin_voice.json`（不解码、不写 Output/），并列出与现网的差异。

为什么要有它：归属规则（档位分配、后缀三分类、台词钥匙）改了之后，**换入前**必须知道
"哪些皮肤的音频/台词会变、变成什么"，但 `extract_cv_voice.py --all` 会直接覆写正式产物。
磁盘上 889 个包早已解完（`--skip-done` 那条路径就是"复用文件名当 cue 名"），
所以整条映射可以纯本地重算 —— 零子进程、零写入。

用法:
  py -3 scripts/diag/voice_remap_check.py [--out .diag/_cv/skin_voice_new.json] [--ships a,b]
输出:
  改后映射（默认 .diag/_cv/）+ 三段差异：档位变了 / lines 增减 / 只在本轮消失或新增的皮肤
"""
import os, sys, json, glob, argparse, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import extract_cv_voice as E      # noqa: E402

DIAG = os.path.join(ROOT, '.diag')
CUR = os.path.join(ROOT, 'Output', 'gallery_v2', 'skin_voice.json')
AUDIO = os.path.join(ROOT, 'Output', 'Audio', 'CV2')


def cue_sets_from_disk(banks):
    """已解码目录 → {cv: [cue 名]}（与 process_bank(skip_done=True) 同一份口径）。"""
    out = {}
    for cv in banks:
        d = os.path.join(AUDIO, 'cv-%d' % cv)
        if os.path.isdir(d):
            out[cv] = sorted(os.path.splitext(f)[0] for f in os.listdir(d)
                             if f.endswith('.ogg') and os.path.getsize(os.path.join(d, f)) >= 1024)
    return out


def remap(ships=None):
    keys = E.gallery_keys()
    if ships:
        keys = [k for k in keys if E.ship_stem(k.lower()) in ships]
    rows, banks = E.load_skin_rows(), E.banks_on_disk()
    res, miss = E.resolve(keys, rows, banks)
    cue_sets = cue_sets_from_disk(banks)
    E.assign_pending_idx(res, cue_sets)
    rel = lambda cv, n: 'Audio/CV2/cv-%d/%s.ogg' % (cv, n)
    out = {}
    for k in keys:
        e = res.get(k)
        if not e or not cue_sets.get(e['cv']):
            continue
        ent, _ = E.build_entry(e['cv'], e['idx'], e['src'], cue_sets[e['cv']], rel)
        if ent['lines']:
            out[k] = ent
    return out, miss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(DIAG, '_cv', 'skin_voice_new.json'))
    ap.add_argument('--ships', default='', help='逗号分隔船名（stem），只算这些')
    ap.add_argument('--cur', default=CUR)
    a = ap.parse_args()
    ships = {s.strip().lower() for s in a.ships.split(',') if s.strip()} or None
    new, miss = remap(ships)
    cur = json.load(open(a.cur, encoding='utf-8'))
    if ships:
        cur = {k: v for k, v in cur.items() if E.ship_stem(k.lower()) in ships}

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(new, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    print('改后映射 %d 皮肤（%s）| 现网 %d | 无解 %d' % (len(new), a.out, len(cur), len(miss)))
    print('src 分布 改后 %s' % dict(collections.Counter(e['src'] for e in new.values())))
    print('src 分布 现网 %s' % dict(collections.Counter(e['src'] for e in cur.values())))

    ch = [(k, cur[k]['cv'], cur[k]['idx'], cur[k]['src'], new[k]['cv'], new[k]['idx'], new[k]['src'])
          for k in sorted(set(cur) & set(new))
          if (cur[k]['cv'], cur[k]['idx']) != (new[k]['cv'], new[k]['idx'])]
    print('\n── 音频归属 (cv, idx) 变了 %d 个 ──' % len(ch))
    for t in ch[:80]:
        print('   %-22s 现网 cv=%-8s idx=%-3s %-13s → 改后 cv=%-8s idx=%-3s %s' % t)
    print('   （全库共 %d，前 80 条）' % len(ch) if len(ch) > 80 else '')

    def sig(e):
        return {(l['cat'], l.get('ev'), l['f']) for l in e['lines']}
    grew = [(k, len(sig(new[k])) - len(sig(cur[k]))) for k in sorted(set(cur) & set(new))
            if sig(new[k]) != sig(cur[k])]
    print('\n── lines 集合变化 %d 个皮肤 | 净增 %d 条 / 净减 %d 条'
          % (len(grew), sum(g for _, g in grew if g > 0), sum(-g for _, g in grew if g < 0)))
    print('   消失的键 %s | 新增的键 %s' % (sorted(set(cur) - set(new))[:10], sorted(set(new) - set(cur))[:10]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
