#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_skin_table_drift.py — 权威皮肤表到底漏没漏？（"是真没有还是管线没拉取到"）

一条命令回答两类问题：
  1. **设备侧源里有、`inputs/gamecfg/ship_skin_template.json` 里没有**的皮肤行
     ⇒ 发布用的是过期表，皮肤会没名字、没语音映射（症状：画廊显示「皮肤4」、
       「该皮肤本地没有语音包」）。
  2. 对这些漏掉的皮肤，**语音包里到底有没有它的那一档**：解 `cue/cv-<ship_group>.b`
     数一遍流名，按「cue 名尾部的 `_N` = 皮肤档位」对号，再比对
     `Output/Audio/CV2/cv-<n>/` 里落了几个 ogg。
     ⇒ 源包有、盘上没落 = 管线漏解；源包也没有 = 游戏确实没配。

数据流（2026-10-17 §155 的根因链）：
  files/AssetBundles/sharecfgdata/ship_skin_template   （设备侧源，随包更新）
    → 37 号 `--scalar-all` → .diag/sharecfg_re/cfg_json_scalar/ship_skin_template.json
    → 42 号发布 → inputs/gamecfg/ship_skin_template.json   （`scripts/skin_table.py` 读它）
    → build_ship_meta 起名 / extract_cv_voice 派语音档位

用法:
  py -3 scripts/diag/check_skin_table_drift.py            # 只报漂移与语音缺口
  py -3 scripts/diag/check_skin_table_drift.py --all      # 顺带打印两边都有的行数统计
  py -3 scripts/diag/check_skin_table_drift.py --no-audio # 跳过语音包解码（快，~15 秒）
  py -3 scripts/diag/check_skin_table_drift.py --json --no-audio   # 给验证器喂结构化结论

退出码: 0 无漂移；1 有漂移或语音缺口；2 环境/输入不齐。
"""
import argparse
import collections
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import paths as P                                    # noqa: E402

SRC_TABLE = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata', 'ship_skin_template')
PUB_TABLE = os.path.join(ROOT, 'inputs', 'gamecfg', 'ship_skin_template.json')
CUE_DIR = os.path.join(ROOT, 'files', 'AssetBundles', 'cue')
AUDIO_DIR = os.path.join(ROOT, 'Output', 'Audio', 'CV2')
PARSER = os.path.join(ROOT, 'tools', 'sharecfg_re', '37_parse_sharecfgdata.py')


def load_parser():
    """按文件路径加载 37 号（它在 tools/ 下，不在 scripts/ 里，不能普通 import）。"""
    spec = importlib.util.spec_from_file_location('p37', PARSER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_cvvoice():
    """extract_cv_voice 的 split_cue：cue 名 → (类别, 皮肤档位, 活动码)。"""
    spec = importlib.util.spec_from_file_location(
        'ecv', os.path.join(ROOT, 'scripts', 'extract_cv_voice.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def tier_of(row):
    """表行 → 语音包内档位（与 extract_cv_voice.load_skin_rows 同一套口径）。"""
    sid = int(row.get('id') or 0)
    grp = row.get('ship_group')
    if not isinstance(grp, int):
        return None, None
    off = sid // 10 - grp
    tier = sid % 10 if off == 0 else (10 + sid % 10 if off == 3000 else None)
    return grp, tier


def bank_streams(bank):
    """解一个 cue 包，返回全部流名（vgmstream 只认 .acb 后缀，和 extract_cv_voice 一致）。"""
    if not os.path.isfile(bank):
        return None
    tmp = tempfile.mkdtemp(prefix='skindrift_')
    try:
        src = os.path.join(tmp, 'in.acb')
        shutil.copy2(bank, src)
        out = os.path.join(tmp, 'wav')
        os.makedirs(out, exist_ok=True)
        r = subprocess.run([P.VGMSTREAM, '-i', '-S', '0', '-o', os.path.join(out, '?n.wav'), src],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=900)
        names = [os.path.splitext(os.path.basename(f))[0]
                 for f in sorted(os.listdir(out)) if f.endswith('.wav')]
        if not names:
            print(f'  !! vgmstream 没解出流（rc={r.returncode}）：{bank}')
            return []
        return names
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true', help='顺带打印两边都有的行数统计')
    ap.add_argument('--no-audio', action='store_true', help='跳过语音包解码（只查表）')
    ap.add_argument('--json', action='store_true', help='输出结构化结论（供 verify_pipeline_e2e 消费）')
    a = ap.parse_args()

    def say(*xs):
        (sys.stderr if a.json else sys.stdout).write(' '.join(str(x) for x in xs) + "\n")

    def emit(rep, code):
        if a.json:
            sys.stdout.write(json.dumps(rep, ensure_ascii=False) + "\n")
        return code

    if not os.path.isfile(SRC_TABLE) or not os.path.isfile(PUB_TABLE):
        say('输入不齐：需要 sharecfgdata/ship_skin_template 与 inputs/gamecfg/ship_skin_template.json')
        return 2

    src = load_parser().export_scalar('ship_skin_template')[0]
    pub = json.load(open(PUB_TABLE, encoding='utf-8'))
    only_src = sorted(set(map(str, src)) - set(map(str, pub)), key=lambda k: int(k))
    only_pub = sorted(set(map(str, pub)) - set(map(str, src)), key=lambda k: int(k))
    rep = {'rows_src': len(src), 'rows_pub': len(pub),
           'only_src': [{'id': k, 'painting': src[k].get('painting'),
                         'name': src[k].get('name'), 'ship_group': src[k].get('ship_group'),
                         'voice_actor': src[k].get('voice_actor')} for k in only_src],
           'only_pub': [{'id': k, 'painting': pub[k].get('painting')} for k in only_pub],
           'audio': []}

    if not only_src and not only_pub:
        say(f'设备侧源 {len(src)} 行 · 已发布 {len(pub)} 行')
        say('✅ 两边一致 —— 没有漏发布的皮肤')
        return emit(rep, 0)

    say(f'设备侧源 {len(src)} 行 · 已发布 {len(pub)} 行')
    say(f'❌ 漂移：源里有 {len(only_src)} 行没发布，已发布里有 {len(only_pub)} 行源里没有')
    for k in only_src[:40]:
        r = src[k]
        say(f'  + {k:>8}  {str(r.get("painting")):<28} {str(r.get("name")):<22} '
              f'group={r.get("ship_group")} cv={r.get("voice_actor")}')
    if len(only_src) > 40:
        say(f'  …… 还有 {len(only_src) - 40} 行')
    for k in only_pub[:20]:
        say(f'  - {k:>8}  {str(pub[k].get("painting")):<28} （源里已经没有这行）')

    if a.no_audio:
        return emit(rep, 1)

    # 语音缺口：只查受影响的语音包（按 ship_group 聚合），别把 536 个包全解一遍
    ecv = load_cvvoice()
    banks = collections.defaultdict(list)
    for k in only_src:
        r = src[k]
        grp, tier = tier_of(r)
        if grp is None or tier is None:
            continue
        banks[grp].append((r.get('painting'), tier))
    if not banks:
        say('\n（漏掉的行都算不出语音档位，跳过语音核对）')
        return emit(rep, 1)

    miss_total = 0
    for grp in sorted(banks):
        bank = os.path.join(CUE_DIR, f'cv-{grp}.b')
        streams = bank_streams(bank)
        if streams is None:
            say(f'\n  cv-{grp}：盘上没有 cue/cv-{grp}.b ⇒ 语音包没拉到')
            rep['audio'].append({'cv': grp, 'bank': False})
            miss_total += 1
            continue
        outdir = os.path.join(AUDIO_DIR, f'cv-{grp}')
        have = set(os.listdir(outdir)) if os.path.isdir(outdir) else set()
        for painting, tier in banks[grp]:
            want = [n for n in streams
                    if (ecv.split_cue(n)[1] or 0) == tier and not ecv.SONG.match(n)]
            lack = [n for n in want if n + '.ogg' not in have]
            rec = {'painting': painting, 'cv': grp, 'tier': tier,
                   'in_bank': len(want), 'on_disk': len(want) - len(lack)}
            rep['audio'].append(rec)
            if not want:
                say(f'\n  {painting}（cv-{grp} 档 {tier}）：包里没有这一档的流 ⇒ 游戏没配语音')
            elif lack:
                miss_total += len(lack)
                say(f'\n  {painting}（cv-{grp} 档 {tier}）：源包有 {len(want)} 条，'
                      f'盘上只落 {len(want) - len(lack)} 条，缺 {len(lack)} 条')
                say('    缺：' + ', '.join(sorted(lack)[:12]) + (' …' if len(lack) > 12 else ''))
            else:
                say(f'\n  {painting}（cv-{grp} 档 {tier}）：{len(want)} 条都在 ✅')
    rep['audio_missing'] = miss_total
    if miss_total:
        say(f'\n合计缺 {miss_total} 条语音 —— 表刷新 + 重跑第 3 步语音档后应补齐')
        return emit(rep, 1)
    say('\n语音没有缺口（或游戏确实没配）')
    return emit(rep, 1)          # 表已漂移，即使语音齐了也算红


if __name__ == '__main__':
    sys.exit(main())
