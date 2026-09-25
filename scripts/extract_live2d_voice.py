#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 CRIWARE ACB（files/AssetBundles/cue/cv-<id>.b）里按 Live2D 动作触发导出语音。

背景（2026-09-23 实测）：
  - Live2D 包内没有任何音频（antu_2 对象统计 0 个 AudioClip），语音在独立的 cue/*.b 里；
  - 一个 .b = 一条船的全部语音 bank（45~170 条带名字的 cue），6 月那次 export_cue_audio.py
    用 `vgmstream-cli -o x.wav file.acb` 只取了第 1 条（detail），其余全丢了；
  - cue 名与 model3.json 的动作组名**逐字同名**（home/login/mail/main_1..4/mission_complete/
    touch_head），所以不需要游戏配置就能对上；
  - 皮肤 → ACB 的路子：inputs/azdata/azdata_ship_skin_template.json 的 painting 字段 = 磁盘皮肤名，
    取 skin id // 10 即 cv 号。270 个 Live2D 皮肤里 253 个能命中现有 ACB。

用法:
  py -3 scripts/extract_live2d_voice.py --report antu_2      # 只列映射，不写任何文件
  py -3 scripts/extract_live2d_voice.py --key antu_2          # 单皮肤小样本
  L2D_VOICE_ALL=1 py -3 scripts/extract_live2d_voice.py       # 全量（必须显式开环境变量）
产物:
  Output/Audio/L2D/<皮肤>/<cue>.ogg
  Output/gallery_v2/l2d_voice.json   {皮肤: {动作组: [相对音频路径...]}}
"""
import os, sys, re, json, glob, shutil, zipfile, subprocess, tempfile, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CUE_DIR = os.path.join(ROOT, 'files', 'AssetBundles', 'cue')
L2D_DIR = os.path.join(ROOT, 'Output', 'Live2D')
OUT_AUDIO = os.path.join(ROOT, 'Output', 'Audio', 'L2D')
OUT_MAP = os.path.join(ROOT, 'Output', 'gallery_v2', 'l2d_voice.json')
DIAG = os.path.join(ROOT, '.diag')
AZDATA = os.path.join(ROOT, 'inputs', 'azdata')   # 权威快照，台账 inputs/azdata/MANIFEST.json

VGMSTREAM = r'C:\Users\KLLM\AppData\Local\vgmstream\vgmstream-cli.exe'
FFMPEG = shutil.which('ffmpeg') or r'C:\Users\KLLM\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'
OPUS_BITRATE = '48k'

# 动作组 → ACB cue 名别名。以前只有猜的两条（注释里自承"需人工试听确认"）；
# 现在从游戏自己的 `character_voice` 表生成：l2d_action → resource_key，touch_body→touch_1、
# touch_special→touch_2 得到证实，另外多出一条此前没认到的 headtouch(touch_head 同名，不走别名)。
# 台账 inputs/gamecfg/MANIFEST.json；取不到该表时退回原来那两条猜测，不影响跑通。
def _load_alias():
    f = os.path.join(ROOT, 'inputs', 'gamecfg', 'character_voice.json')
    try:
        cv = json.load(open(f, encoding='utf-8'))
    except Exception:
        print('!! 缺 inputs/gamecfg/character_voice.json，动作组别名退回硬编码猜测', file=sys.stderr)
        return {'touch_body': ['touch_1'], 'touch_special': ['touch_2']}
    m = {}
    for row in cv.values():
        g, rk = row.get('l2d_action'), row.get('resource_key')
        if g and rk and g != rk:
            m.setdefault(g, [])
            if rk not in m[g]:
                m[g].append(rk)
    return m


ALIAS = _load_alias()
# 变体后缀：同一触发游戏里有多条台词（main_1 / main_1_1 / main_1_2），随机取一条。
VARIANT_SUF = ['', '_1', '_2']
# 明确排除：_exNNNN 是活动限定台词，vocal_* 是歌曲人声，都不该在点模型时放。
EXCLUDE = re.compile(r'^(vocal_|.*_ex\d+$)')


def load_skin_index():
    """painting(磁盘皮肤名) → 该皮肤在皮肤表里的 id 列表（升序）。"""
    p = os.path.join(AZDATA, 'azdata_ship_skin_template.json')
    d = json.load(open(p, encoding='utf-8'))
    by = collections.defaultdict(list)
    for k, r in d.items():
        if not isinstance(r, dict):
            continue
        pid = str(r.get('painting') or '').strip()
        sid = r.get('id') or k
        if pid:
            by[pid].append(int(sid))
    return {k: sorted(v) for k, v in by.items()}


def model_groups(key):
    """该皮肤 model3.json 里的全部动作组名。"""
    for f in glob.glob(os.path.join(L2D_DIR, key, '*.model3.json')):
        d = json.load(open(f, encoding='utf-8'))
        M = (d.get('FileReferences') or {}).get('Motions')
        if isinstance(M, dict):
            return sorted(M.keys())
        if isinstance(M, list):
            return sorted({g['Group'] for g in M})
    return []


def acb_path_for(key, by_painting):
    """皮肤名 → cv ACB。先试皮肤名本身，再去掉 _hx/_n 等变体后缀。"""
    stems = [key]
    b = re.sub(r'(_hx|_n|_rw|_bj|_jz|_alter|_hei)$', '', key)
    if b != key:
        stems.append(b)
    for st in stems:
        for sid in by_painting.get(st, []):
            p = os.path.join(CUE_DIR, 'cv-%d.b' % (sid // 10))
            if os.path.exists(p):
                return p, sid
    return None, None


def decode_all(acb, tmp):
    """一次调用把 ACB 里全部 cue 解成 <cue名>.wav。返回 {cue名: wav路径}。"""
    src = os.path.join(tmp, 'in.acb')
    out = os.path.join(tmp, 'wav')
    os.makedirs(out, exist_ok=True)
    shutil.copy2(acb, src)
    r = subprocess.run([VGMSTREAM, '-i', '-S', '0', '-o', os.path.join(out, '?n.wav'), src],
                       capture_output=True, text=True, timeout=600)
    files = glob.glob(os.path.join(out, '*.wav'))
    if not files:
        raise RuntimeError('vgmstream 未解出任何流 (rc=%s) %s' % (r.returncode, (r.stderr or '')[:200]))
    return {os.path.splitext(os.path.basename(f))[0]: f for f in files}


def to_ogg(wav, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    r = subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-i', wav,
                        '-c:a', 'libopus', '-b:a', OPUS_BITRATE, dst],
                       capture_output=True, text=True, timeout=300)
    if not os.path.exists(dst) or os.path.getsize(dst) < 1024:
        raise RuntimeError('ffmpeg 转码失败 %s: %s' % (wav, (r.stderr or '')[:200]))


def plan_for(key, cues, groups):
    """动作组 → 要导出的 cue 名列表。"""
    plan, used = {}, set()
    for g in groups:
        cands = [g] + ALIAS.get(g, [])
        hit = []
        for base in cands:
            for suf in VARIANT_SUF:
                c = base + suf
                if c in cues and not EXCLUDE.match(c):
                    hit.append(c)
        if hit:
            plan[g] = hit
            used.update(hit)
    return plan, used


def run(keys, do_write):
    by_painting = load_skin_index()
    if not os.path.exists(VGMSTREAM):
        print('!! 缺 vgmstream: %s' % VGMSTREAM); return 2
    report, n_no_acb, n_no_voice = {}, 0, 0
    map_out = {}
    for key in keys:
        acb, sid = acb_path_for(key, by_painting)
        groups = model_groups(key)
        if not acb:
            n_no_acb += 1
            report[key] = {'skip': '没找到 ACB', 'groups': len(groups)}
            continue
        with tempfile.TemporaryDirectory() as tmp:
            try:
                cues = decode_all(acb, tmp)
            except Exception as e:
                report[key] = {'err': str(e)[:200]}; continue
            plan, used = plan_for(key, cues, groups)
            if not plan:
                n_no_voice += 1
                report[key] = {'acb': os.path.basename(acb), 'cues': len(cues),
                               'groups': len(groups), 'skip': '动作组与 cue 名零交集'}
                continue
            ent = {}
            for g, cs in sorted(plan.items()):
                rels = []
                for c in sorted(cs):
                    rel = 'Audio/L2D/%s/%s.ogg' % (key, c)
                    dst = os.path.join(ROOT, 'Output', rel)
                    if do_write:
                        to_ogg(cues[c], dst)
                    rels.append(rel)
                ent[g] = rels
            map_out[key] = ent
            report[key] = {'acb': os.path.basename(acb), 'skin_id': sid, 'cues': len(cues),
                           'groups': len(groups), 'mapped': len(ent),
                           'files': sum(len(v) for v in ent.values())}
            print('%-16s %-13s cue=%-4d 组=%-4d 映射组=%-3d 文件=%d  %s' % (
                key, os.path.basename(acb), len(cues), len(groups), len(ent),
                report[key]['files'], sorted(ent)))
    print('\n合计 %d 个皮肤 | 无 ACB %d | 有 ACB 但零交集 %d | 写入=%s' % (
        len(keys), n_no_acb, n_no_voice, do_write))
    if do_write and map_out:
        old = {}
        if os.path.exists(OUT_MAP):
            try: old = json.load(open(OUT_MAP, encoding='utf-8'))
            except Exception: old = {}
        old.update(map_out)
        os.makedirs(os.path.dirname(OUT_MAP), exist_ok=True)
        json.dump(old, open(OUT_MAP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('映射表: %s（%d 个皮肤）' % (OUT_MAP, len(old)))
    json.dump(report, open(os.path.join(DIAG, '_l2d_voice_report.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    argv = sys.argv[1:]
    only = [x for x in (argv[argv.index('--only') + 1] if '--only' in argv else '').split(',') if x]
    if '--report' in argv:
        keys = only or [d for d in sorted(os.listdir(L2D_DIR)) if not d.startswith('_')]
        sys.exit(run(keys, False))
    if '--key' in argv:
        keys = [x for x in argv[argv.index('--key') + 1].split(',') if x]
        sys.exit(run(keys, True))
    if os.environ.get('L2D_VOICE_ALL') == '1' or '--all' in argv:
        keys = [d for d in sorted(os.listdir(L2D_DIR)) if not d.startswith('_')]
        if only:
            keys = [k for k in keys if k in only]
        sys.exit(run(keys, True))
    print(__doc__)
    print('拒绝默认全量运行：用 --report <key> 看映射，--key <key> 小样本，或 L2D_VOICE_ALL=1 全量。')
    sys.exit(1)
