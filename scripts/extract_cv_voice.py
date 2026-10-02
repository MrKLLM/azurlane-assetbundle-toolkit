#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按「船级语音包」去重导出全部台词语音，并生成「皮肤 → 语音」映射 skin_voice.json。

与 extract_live2d_voice.py 的两点根本差别：
  1) 不再只按 Live2D 目录跑，而是覆盖全部皮肤（静态立绘 / Spine / Live2D 共用同一份音频）；
     同一语音包只解码一次，皮肤侧只写引用，不再出现 gin / gin_hx 各存一份的情况。
  2) 修掉「皮肤序号」语义错：cue 名尾部的 `_N` 是**皮肤序号**（= skin id 末位），不是随机变体。
     取证：cv-10501 内华达三个皮肤 idx=0/1/9(neihuada_g)，包内恰好是 detail / detail_1 / detail_9；
           cv-10001 两皮肤只有 detail / detail_1；`_9` 不可能来自"第三条随机台词"。
     取词规则：本皮肤序号档优先，逐条回退基础档（改造皮肤 _g 即 idx=9，包里常无独有台词）。

cue 名切分必须走「最长已知类别前缀」，不能直接剥尾部数字：`main_1`/`touch_1` 本身就是类别名，
`main_1_2` 才是「类别 main_1 的 1 号皮肤」。类别表 = inputs/gamecfg/character_voice.json
(resource_key / l2d_action / voice_name) + 表没覆盖但包内实际存在的类别名。

用法:
  py -3 scripts/extract_cv_voice.py --probe gin_3,neihuada_g,guying_g     # 只解码+选词，不落盘
  py -3 scripts/extract_cv_voice.py --sample gin_3,...                    # 小样本落盘到 .diag/_cv
  py -3 scripts/extract_cv_voice.py --all [--jobs 4] [--only a,b] [--limit N]
产物:
  Output/Audio/CV2/cv-<语音包号>/<cue>.ogg
  Output/gallery_v2/skin_voice.json  {皮肤: {cv, idx, src, l2d:{动作组:[路径]}, tap:{}, lines:[]}}
"""
import os, sys, re, json, glob, shutil, tempfile, argparse, subprocess, collections
from concurrent.futures import ThreadPoolExecutor
import sys as _p_sys, os as _p_os
_p_sys.path.insert(0, _p_os.path.dirname(_p_os.path.abspath(__file__)))
import paths as P  # 仓库根与外部工具位置：见 scripts/paths.py（AL_ASSETS_ROOT 可覆盖）
import skin_table  # 皮肤表唯一读取口：azdata 快照 + 设备侧权威表逐字段合并（见 scripts/skin_table.py）

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CUE_DIR = os.path.join(ROOT, 'files', 'AssetBundles', 'cue')
PAINT_DIR = os.path.join(ROOT, 'Output', 'Paintings_v2')
L2D_DIR = os.path.join(ROOT, 'Output', 'Live2D')
SPINE_DIR = os.path.join(ROOT, 'Output', 'Spine_v2')
AZDATA = os.path.join(ROOT, 'inputs', 'azdata')
GAMECFG = os.path.join(ROOT, 'inputs', 'gamecfg')
DIAG = os.path.join(ROOT, '.diag')
DEF_AUDIO = os.path.join(ROOT, 'Output', 'Audio', 'CV2')
DEF_MAP = os.path.join(ROOT, 'Output', 'gallery_v2', 'skin_voice.json')

VGMSTREAM = P.VGMSTREAM
FFMPEG = P.FFMPEG
OPUS_BITRATE = '48k'

# 皮肤目录名里的「后处理变体」：同一皮肤的另一张画法，语音与皮肤序号都不受影响。
# ⚠️ 不含 _g/_meta/_asmr —— 它们是独立皮肤（guying_g 在皮肤表里有自己的行、idx=9），剥掉会串到基础皮肤。
VAR = re.compile(r'(_hx|_n|_rw|_bj|_jz|_alter|_heihei|_hei)+$')
# 「第几号皮肤」尾缀：定位船名(stem)时要剥掉；_g/_h 这类不带数字的也是独立皮肤
SKIN_TAIL = re.compile(r'(_\d+|_h|_g|_meta|_asmr|_gv|_rw|_bj|_jz|_alter|_heihei|_hei)$')
SONG = re.compile(r'^vocal_')           # 歌曲人声，不是台词
EVENT = re.compile(r'_ex(\d+)$')        # 活动限定台词后缀：导出并列出，但不进点击/动作触发

# character_voice 表没覆盖、但包里实际存在的类别名 → 中文标签
EXTRA_LABEL = {
    'get': '获得', 'unlock': '获得', 'present_like': '秘书舰喜欢', 'present_dislike': '秘书舰不喜欢',
    'title': '标题', 'chime': '互动彩蛋', 'extra': '额外',
    'skill_1': '技能1', 'skill_2': '技能2',
}
# 点击触发用的触摸类别（不同船包里写法不一：touch / touch_1 都算普通触摸）
TAP_CATS = {'touch': 'touch_body', 'touch_1': 'touch_body',
            'touch_2': 'touch_special', 'touch_head': 'touch_head'}


def load_table():
    """cue 基名 → {cat, label, l2d_action, spine_action}。"""
    rows = json.load(open(os.path.join(GAMECFG, 'character_voice.json'), encoding='utf-8'))
    by_cue = {}
    for cat, r in rows.items():
        rk = (r.get('resource_key') or cat).strip() or cat
        ent = {'cat': cat, 'label': (r.get('voice_name') or cat).strip() or cat,
               'l2d_action': (r.get('l2d_action') or '').strip(),
               'spine_action': (r.get('spine_action') or '').strip()}
        by_cue.setdefault(rk, ent)
        by_cue.setdefault(cat, by_cue[rk])
    for k, v in EXTRA_LABEL.items():
        by_cue.setdefault(k, {'cat': k, 'label': v, 'l2d_action': '', 'spine_action': ''})
    for i in range(1, 10):        # main_1..main_9 / feeling1..9 本身就是带数字的类别名
        by_cue.setdefault('main_%d' % i, {'cat': 'main%d' % i, 'label': '主界面%d' % i,
                                          'l2d_action': 'main_%d' % i, 'spine_action': 'normal'})
        by_cue.setdefault('feeling%d' % i, {'cat': 'feeling%d' % i, 'label': '心情%d' % i,
                                            'l2d_action': 'feeling%d' % i, 'spine_action': 'normal'})
    return by_cue


CUE2CAT = load_table()
CATS_SORTED = sorted(CUE2CAT, key=len, reverse=True)      # 最长前缀优先


def split_cue(n):
    """cue 名 → (类别基名, 皮肤序号 or None, 活动码 or None)；切不出类别时返回 None。"""
    ev = None
    m = EVENT.search(n)
    if m:
        ev, n = m.group(1), n[:m.start()]
    for c in CATS_SORTED:
        if n == c:
            return c, None, ev
        if n.startswith(c + '_') and n[len(c) + 1:].isdigit():
            return c, int(n[len(c) + 1:]), ev
    return None, None, ev


def load_skin_rows():
    """painting（磁盘皮肤名）→ [(cv, idx)]，cv = skin id // 10（语音包号），idx = skin id % 10。

    ⚠️ 表键**一律小写归一**：皮肤表里 `2B`/`A2`/`HDN101` 这类是大写，而磁盘目录名是小写，
    原样查表会让 145 张明明有包的皮肤掉进「无解」（2026-09-27 普查 499 无解时查出）。
    磁盘侧候选也要 `.lower()`（见 resolve）。"""
    d = skin_table.load()
    by = collections.defaultdict(list)
    for k, r in d.items():
        if not isinstance(r, dict):
            continue
        p = str(r.get('painting') or '').strip()
        if not p:
            continue
        sid = int(r.get('id') or k)
        by[p.lower()].append((sid // 10, sid % 10))
    return {p: sorted(set(v)) for p, v in by.items()}


def gallery_keys():
    keys = set()
    if os.path.isdir(PAINT_DIR):
        for f in os.listdir(PAINT_DIR):
            if f.lower().endswith('.png') and not f.startswith(('_', '.')):
                keys.add(os.path.splitext(f)[0])
    for d in (L2D_DIR, SPINE_DIR):
        if os.path.isdir(d):
            for name in os.listdir(d):
                if not name.startswith(('_', '.')) and os.path.isdir(os.path.join(d, name)):
                    keys.add(name)
    return sorted(keys)


def banks_on_disk():
    out = {}
    for f in os.listdir(CUE_DIR):
        m = re.match(r'cv-(\d+)\.b$', f)
        if m:
            out[int(m.group(1))] = os.path.join(CUE_DIR, f)
    return out


def ship_stem(k):
    """皮肤目录名 → 船名（反复剥掉画法变体与皮肤尾缀）。"""
    s, prev = k, None
    while s != prev:
        prev = s
        s = SKIN_TAIL.sub('', VAR.sub('', s))
    return s


def resolve(keys, rows, banks):
    """皮肤 → {cv, idx or None, src}。idx=None 表示等解码出包内序号档后再定（同船回退）。

    候选一律小写（表已按小写归一，见 load_skin_rows）。**不做身份后缀剥离**：
    `_memory/_rank/_heihua/_ex/_wjz` 这类可能是另一个发声实体，剥错就是把别人的台词派给它。"""
    res, miss = {}, []
    rows_l = {p.lower(): v for p, v in rows.items()}
    stems = {p: ship_stem(p) for p in rows_l}
    for k in keys:
        kl = k.lower()
        for cand, src in ((kl, 'row'), (VAR.sub('', kl), 'strip')):
            hit = [t for t in rows_l.get(cand, []) if t[0] in banks]
            if hit:
                res[k] = {'cv': hit[0][0], 'idx': hit[0][1], 'src': src}
                break
        else:
            st = ship_stem(kl)
            alt = sorted({t for p in rows_l if stems[p] == st for t in rows_l[p] if t[0] in banks})
            if alt:
                res[k] = {'cv': alt[0][0], 'idx': None, 'src': 'sibling'}
            else:
                miss.append(k)
    return res, miss


def assign_pending_idx(res, cue_sets):
    """快照缺行的皮肤分配皮肤序号：取「包内实际存在的序号档」里还没被同船其它皮肤占用的。

    不拿目录名尾缀硬算——实测 `_N`→N-1 这条推断对配置表已知行也只有 78% 正确（lafei_8 实际 idx=5）。
    分不到档的退回基础档 idx=0。
    """
    pend = collections.defaultdict(list)
    for k, e in res.items():
        if e['idx'] is None:
            pend[(e['cv'], ship_stem(k))].append(k)
    for (cv, stem), ks in pend.items():
        used = {e['idx'] for e in res.values() if e['cv'] == cv and e['idx'] is not None}
        tiers = {s for n in cue_sets.get(cv, []) for s in [split_cue(n)[1]] if s is not None}
        free = sorted(tiers - used)
        for k in sorted(ks, key=lambda x: (re.findall(r'\d+', VAR.sub('', x)) or ['999'])[-1]):
            e = res[k]
            if free:
                e['idx'], e['src'] = free.pop(0), 'sibling-tier'
            else:
                e['idx'], e['src'] = 0, 'sibling-base'


def decode_bank(acb, tmp):
    """一个语音包 → {cue 名: wav 路径}（一次 vgmstream 调用取全部流）。"""
    src = os.path.join(tmp, 'in.acb')
    out = os.path.join(tmp, 'wav')
    os.makedirs(out, exist_ok=True)
    shutil.copy2(acb, src)
    r = subprocess.run([VGMSTREAM, '-i', '-S', '0', '-o', os.path.join(out, '?n.wav'), src],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
    files = glob.glob(os.path.join(out, '*.wav'))
    if not files:
        raise RuntimeError('vgmstream 未解出流 (rc=%s) %s' % (r.returncode, (r.stderr or '')[:160]))
    return {os.path.splitext(os.path.basename(f))[0]: f for f in files}


def to_ogg(wav, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    r = subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-i', wav,
                        '-c:a', 'libopus', '-b:a', OPUS_BITRATE, dst],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    if not os.path.exists(dst) or os.path.getsize(dst) < 1024:
        raise RuntimeError('ffmpeg 转码失败 %s: %s' % (wav, (r.stderr or '')[:160]))


def pick_for(names):
    """包内全部流 → {类别: {皮肤序号(基础档记 0): {活动码 or None: cue 名}}}，另给出切不出类别的名字。"""
    by_cat = collections.defaultdict(lambda: collections.defaultdict(dict))
    unknown = []
    for n in names:
        if SONG.match(n):
            continue
        cat, sidx, ev = split_cue(n)
        if not cat:
            unknown.append(n)
            continue
        by_cat[cat][sidx or 0][ev] = n
    return by_cat, unknown


def tier_for(slots, idx):
    """本皮肤可用台词档：本皮肤序号档优先，逐条（含活动码）回退基础档；别的皮肤的独有台词不进表。"""
    mine, base = slots.get(idx) or {}, slots.get(0) or {}
    return {ev: mine.get(ev, base.get(ev)) for ev in set(mine) | set(base)}


def build_entry(cv, idx, src, names, rel):
    by_cat, unknown = pick_for(names)
    lines, l2d, tap = [], {}, {}
    for cat, slots in sorted(by_cat.items()):
        ent = CUE2CAT.get(cat, {})
        for ev, name in sorted(tier_for(slots, idx).items(), key=lambda kv: str(kv[1])):
            if not name:
                continue
            item = {'cat': cat, 'label': ent.get('label') or cat, 'f': rel(cv, name)}
            if ev:
                item['ev'] = ev
            lines.append(item)
            if not ev:
                if ent.get('l2d_action'):
                    l2d.setdefault(ent['l2d_action'], []).append(item['f'])
                if cat in TAP_CATS:
                    tap[TAP_CATS[cat]] = item['f']
    return ({'cv': cv, 'idx': idx, 'src': src,
             'l2d': {g: sorted(v) for g, v in sorted(l2d.items())},
             'tap': tap, 'lines': lines}, unknown)


def process_bank(cv, acb, out_audio, skip_done=False):
    dst_dir = os.path.join(out_audio, 'cv-%d' % cv)
    if skip_done and os.path.isdir(dst_dir):
        have = sorted(os.path.splitext(f)[0] for f in os.listdir(dst_dir)
                      if f.endswith('.ogg') and os.path.getsize(os.path.join(dst_dir, f)) >= 1024)
        if have:
            # 增量：整包已解过就复用文件名即 cue 名这一对应关系，不再跑 vgmstream+ffmpeg。
            # 换入前仍要过 l2d_voice_diff_check 的「磁盘缺失/占位 = 0」闸门，防止半截包被当成完整。
            return cv, have
    with tempfile.TemporaryDirectory(dir=DIAG) as tmp:
        names = decode_bank(acb, tmp)
        keep = [n for n in names if not SONG.match(n)]
        for n in keep:
            to_ogg(names[n], os.path.join(dst_dir, n + '.ogg'))
        return cv, sorted(keep)


def run(skin_keys, mode, out_audio, map_path, jobs, skip_done=False):
    rows = load_skin_rows()
    banks = banks_on_disk()
    if not banks:
        print('!! %s 下没有任何 cv-*.b' % CUE_DIR)
        return 2
    if not os.path.exists(VGMSTREAM):
        print('!! 缺 vgmstream: %s' % VGMSTREAM)
        return 2
    os.makedirs(DIAG, exist_ok=True)
    res, miss = resolve(skin_keys, rows, banks)
    need = sorted({e['cv'] for e in res.values()})
    print('皮肤 %d | 可定位包 %d | 无解 %d | 需解码 %d 包 | 来源 %s'
          % (len(skin_keys), len(res), len(miss), len(need),
             dict(collections.Counter(e['src'] for e in res.values()))))
    rel = lambda cv, n: 'Audio/CV2/cv-%d/%s.ogg' % (cv, n)

    cue_sets = {}
    if mode == 'probe':
        for cv in need:
            with tempfile.TemporaryDirectory(dir=DIAG) as tmp:
                cue_sets[cv] = sorted(decode_bank(banks[cv], tmp))
    else:
        os.makedirs(out_audio, exist_ok=True)
        reused = 0
        if skip_done:
            reused = sum(1 for cv in need
                         if os.path.isdir(os.path.join(out_audio, 'cv-%d' % cv)))
            print('增量：复用已解包 %d / %d，只新解 %d 个'
                  % (reused, len(need), len(need) - reused), flush=True)
        done = fail = 0
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
            futs = [ex.submit(process_bank, cv, banks[cv], out_audio, skip_done) for cv in need]
            for f in futs:
                try:
                    cv, names = f.result()
                    cue_sets[cv] = names
                except Exception as e:
                    fail += 1
                    print('!! 语音包失败:', str(e)[:200])
                    continue
                done += 1
                if done % 25 == 0 or done == len(need):
                    print('  已导出 %d/%d 包 (失败 %d)' % (done, len(need), fail))
    assign_pending_idx(res, cue_sets)

    map_out, unknown_all = {}, collections.Counter()
    for k in skin_keys:
        cv = res.get(k, {}).get('cv')
        if not cv or not cue_sets.get(cv):
            continue
        e = res[k]
        ent, unk = build_entry(cv, e['idx'], e['src'], cue_sets[cv], rel)
        for n in unk:
            unknown_all[n] += 1
        if ent['lines']:
            map_out[k] = ent
    print('映射 %d 皮肤 | 可点击(有触摸) %d | 台词条目 %d | 未识别 cue 种类 %d'
          % (len(map_out), sum(1 for e in map_out.values() if e['tap']),
             sum(len(e['lines']) for e in map_out.values()), len(unknown_all)))
    if unknown_all:
        print('  未识别 cue 前 12:', [u for u, _ in unknown_all.most_common(12)])
    probe = ['detail', 'home', 'main_1', 'touch_1', 'touch_2', 'touch_head']
    for k in skin_keys:
        e = map_out.get(k)
        if not e:
            print('  %-18s 无语音' % k)
            continue
        got = {p: [l['f'].rsplit('/', 1)[1] for l in e['lines'] if l['cat'] == p] for p in probe}
        print('  %-18s cv=%-8d idx=%-2d src=%-13s 动作组=%-3d 台词=%-3d tap=%s %s'
              % (k, e['cv'], e['idx'], e['src'], len(e['l2d']), len(e['lines']),
                 sorted(e['tap']), json.dumps(got, ensure_ascii=False)))
    if map_path and mode != 'probe':
        old = {}
        if os.path.exists(map_path):
            try:
                old = json.load(open(map_path, encoding='utf-8'))
            except Exception:
                old = {}
        old.update(map_out)
        os.makedirs(os.path.dirname(map_path), exist_ok=True)
        json.dump(old, open(map_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('映射表: %s（%d 皮肤）' % (map_path, len(old)))
    if miss:
        p = os.path.join(DIAG, '_cv_voice_miss.json')
        json.dump(sorted(miss), open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('无解清单: %s（%d）' % (p, len(miss)))
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--probe', metavar='K1,K2')
    ap.add_argument('--sample', metavar='K1,K2')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--only', default='')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--out-dir', default='')
    ap.add_argument('--map', default='')
    ap.add_argument('--skip-done', action='store_true',
                    help='磁盘上已解过的包不再解码，只复用现有 ogg 重建映射（增量重跑）')
    a = ap.parse_args()
    keys = gallery_keys()
    sel = [x for x in (a.probe or a.sample or a.only).split(',') if x]
    if a.probe:
        sys.exit(run([k for k in keys if k in sel], 'probe', '', None, a.jobs))
    if a.sample:
        sys.exit(run([k for k in keys if k in sel], 'sample',
                     a.out_dir or os.path.join(DIAG, '_cv', 'CV2'),
                     a.map or os.path.join(DIAG, 'skin_voice_sample.json'), a.jobs))
    if a.all:
        if sel:
            keys = [k for k in keys if k in sel]
        if a.limit:
            keys = keys[:a.limit]
        sys.exit(run(keys, 'all', a.out_dir or DEF_AUDIO, a.map or DEF_MAP, a.jobs,
                   skip_done=a.skip_done))
    print(__doc__)
    sys.exit(1)
