# -*- coding: utf-8 -*-
"""skin_voice_row_probe.py —— 只读回答一句话：「这个皮肤**自己那一行**到底有没有语音包」。

用法:
  py -3 scripts/diag/skin_voice_row_probe.py                 # 默认普查全部 `_hei`（黑化）皮肤
  py -3 scripts/diag/skin_voice_row_probe.py qiye_hei ...    # 指定键
  py -3 scripts/diag/skin_voice_row_probe.py --suf _hei      # 换后缀普查

存在的理由：撤掉错派之后，"这张为什么没声"会被反复问到，而**两种"没有"必须分开**：
  · 表里根本没有这一行            —— 我们漏抽 / 名字对不上，是我们的问题；
  · 有自己的行、但包号没随资产下发 —— 游戏侧就没给这个实体配录音，不是链路坏了。
判据落在三处独立事实：皮肤表那一行的 `id`（→ 包号 `id//10`）、源包目录 `files/AssetBundles/cue/`、
已解码目录 `Output/Audio/CV2/`。⚠️ 别拿 `voice_actor=-1` 当"没 CV"的证据（那条在剧情角色上是哨兵值，
不等于该实体无配音），也别拿"某个号段整段不在"当结论——黑化用的 9002x~9005x 段确实整段没下发，
但同一个 9xxxx 大段里的 META 包 90101+ 是在盘上的，所以只能逐包号判。
"""
import sys, os, re, json, io, glob, argparse

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import skin_table  # noqa: E402

CUE = os.path.join(ROOT, 'files', 'AssetBundles', 'cue')
CV2 = os.path.join(ROOT, 'Output', 'Audio', 'CV2')
META = os.path.join(ROOT, 'Output', 'ship_meta.json')
NCODE = os.path.join(ROOT, 'inputs', 'gamecfg', 'name_code.json')


def _nums(path, pat):
    out = set()
    if not os.path.isdir(path):
        return out
    for f in os.listdir(path):
        m = re.match(pat, f)
        if m:
            out.add(int(m.group(1)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('keys', nargs='*')
    ap.add_argument('--suf', default='_hei')
    a = ap.parse_args()

    src = _nums(CUE, r'cv-(\d+)\.b$')
    dec = _nums(CV2, r'cv-(\d+)(?:-|$)')
    nc = {}
    if os.path.isfile(NCODE):
        for k, v in json.load(io.open(NCODE, encoding='utf-8')).items():
            if isinstance(v, dict):
                nc[str(k)] = v.get('name')
    meta = json.load(io.open(META, encoding='utf-8')) if os.path.isfile(META) else {}

    by = {}
    for k, r in skin_table.load().items():
        if not isinstance(r, dict):
            continue
        p = str(r.get('painting') or '').strip().lower()
        if p.endswith(a.suf):
            by.setdefault(p, []).append((int(r.get('id') or k), r.get('voice_actor'),
                                         str(r.get('name') or '')))

    want = [k.lower() for k in a.keys] or sorted(by)
    print('%-28s %-9s %-11s %-7s %-8s %s' % ('皮肤名', '行 id', 'voice_actor', '源包', '已解码', '表内皮肤名 / 元数据名'))
    hit_own = hit_pack = 0
    for p in want:
        rows = sorted(by.get(p, []))
        if not rows:
            print('%-28s %-9s %-11s %-7s %-8s %s' % (p, '—', '—', '—', '—', '皮肤表里没有这一行（不是漏抽就是名字对不上）'))
            continue
        for sid, va, nm in rows:
            cv = sid // 10
            s, d = cv in src, cv in dec
            hit_own += 1
            hit_pack += bool(s or d)
            mm = re.search(r'namecode:(\d+)', nm)
            nm2 = nc.get(mm.group(1), '') if mm else ''
            label = nm + (f'（={nm2}）' if nm2 else '')
            m = meta.get(p, {})
            if label in ('？？？', '?', '') and m.get('cn'):
                label += f"｜meta:{m['cn']}"
            print('%-28s %-9s %-11s %-7s %-8s %s' % (p, sid, va,
                                                     '有' if s else '无', '有' if d else '无', label))
    print(f'\n{len(want)} 个键里：有自己那一行 {hit_own} 处，其中包号在盘上（源包或已解码任一）{hit_pack} 处')
    print('⇒ 其余的"没声"是**游戏侧没给这个实体下发录音包**，不是归属链路坏了；要翻案只能去设备侧核对该包号在不在游戏里。')


if __name__ == '__main__':
    main()
