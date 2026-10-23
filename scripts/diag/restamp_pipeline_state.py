# -*- coding: utf-8 -*-
"""一次性：把 pipeline_state 的结论按**当前**指纹重新盖章，并从运行日志补回被误清的阶段。

背景（2026-10-23）：`labels` 阶段写 `inputs/gamecfg/bg_series_labels.json`，而
`gamecfg_stamp()` 把 `inputs/gamecfg/*.json` **全部**算进 `cfg=`；`labels` 在
`swap-in/derive` 之后跑，一写就把前两步的结论盖成旧指纹 ⇒ 面板 2/4、日志 4/4。
修法（`gamecfg_stamp` 排除 `bg_*`）之后，旧结论的 `cfg=` 仍是旧哈希，必须一次性重盖。

本工具只改 `done`/`verdict` 的 `fingerprint`/`scope` 章，以及从日志补回的 ok/detail；
**不动任何产物**。`--step3-log`/`--review-log` 用于补回被 rejudge 清掉的 03/04 结论。

用法:
  py -3 scripts/diag/restamp_pipeline_state.py                 # 干跑
  py -3 scripts/diag/restamp_pipeline_state.py --apply         # 备份 + 原子写
  py -3 scripts/diag/restamp_pipeline_state.py --verify        # 只校验
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import update_pipeline as up  # noqa: E402

LOG_RE = re.compile(r'^\S*\[\d\d:\d\d:\d\d\]\s+\u2705\s+([a-z0-9.\-]+):\s+(.*)$', re.M)
STEP3 = ('deps', 'meta', 'bg', 'paintings', 'spine', 'live2d', 'audio', 'bgm', 'cg')
STAGED_DONE = ('paintings', 'spine', 'live2d')


def _latest_log(pred):
    logs = sorted(glob.glob(os.path.join(up.WORK, 'panel', 'run_*.log')),
                  key=os.path.getmtime, reverse=True)
    for p in logs:
        try:
            txt = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        if pred(txt):
            return p, txt
    return None, ''


def _parse(txt):
    out = {}
    for m in LOG_RE.finditer(txt):
        out[m.group(1)] = m.group(2).strip()
    return out


def _stamp(v, key, sc):
    v = dict(v or {})
    v['fingerprint'] = up.stage_fp_by_key(key)
    v['scope'] = sc
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--step3-log', default='')
    ap.add_argument('--review-log', default='')
    a = ap.parse_args()

    fp, sc = up.fingerprint(), up.scope_stamp()
    st = json.load(open(up.STATE, encoding='utf-8')) if os.path.isfile(up.STATE) else {}
    done = dict(st.get('done') or {})
    verdict = dict(st.get('verdict') or {})

    if a.verify:
        bad = []
        for grp, d in (('done', done), ('verdict', verdict)):
            for k, v in d.items():
                if v.get('fingerprint') != up.stage_fp_by_key(k) or v.get('scope') != sc:
                    bad.append(f'{grp}.{k}')
        print('当前指纹', fp, '范围', sc)
        print('条目', len(done), 'done /', len(verdict), 'verdict')
        print('未对齐:', bad or '无')
        return 1 if bad or st.get('fingerprint') != fp or st.get('scope') != sc else 0

    # 1) 补 03：最新一份含「✅ paintings + ✅ cg」的日志（10:56 那轮）
    p3 = a.step3_log or None
    t3 = open(p3, encoding='utf-8', errors='replace').read() if p3 else ''
    if not p3:
        p3, t3 = _latest_log(lambda t: '✅ paintings' in t and '✅ cg' in t)
    at3 = time.strftime('%Y-%m-%d %H:%M:%S',
                        time.localtime(os.path.getmtime(p3) if p3 else time.time()))
    v3 = _parse(t3)
    added3 = []
    for k in STEP3:
        if k in v3:
            detail = v3[k]
            if k not in verdict:
                added3.append(k)
            verdict[k] = _stamp({'ok': True, 'detail': detail, 'at': at3}, k, sc)
            if k in STAGED_DONE:
                done[k] = dict(verdict[k])

    # 2) 补 04：最新一份含「✅ review」的日志
    p4 = a.review_log or None
    t4 = open(p4, encoding='utf-8', errors='replace').read() if p4 else ''
    if not p4:
        p4, t4 = _latest_log(lambda t: '✅ review' in t)
    v4 = _parse(t4)
    if 'review' in v4:
        if 'review' not in verdict:
            added3.append('review')
        at4 = time.strftime('%Y-%m-%d %H:%M:%S',
                            time.localtime(os.path.getmtime(p4) if p4 else time.time()))
        verdict['review'] = _stamp({'ok': True, 'detail': v4['review'], 'at': at4},
                                    'review', sc)

    # 3) 现有 05 四项 + 任何已有结论统一重盖
    for k in list(done):
        done[k] = _stamp(done[k], k, sc)
    for k in list(verdict):
        verdict[k] = _stamp(verdict[k], k, sc)

    st['fingerprint'] = fp
    st['scope'] = sc
    st['done'] = done
    st['verdict'] = verdict

    print('step3 日志:', p3 or '未找到', '补回:', added3)
    print('review 日志:', p4 or '未找到')
    print('done:', sorted(done))
    print('verdict:', sorted(verdict))
    print('新指纹:', fp, '范围:', sc)
    if not a.apply:
        print('\n干跑；确认无误后加 --apply')
        return 0

    bak = up.STATE + '.bak_' + time.strftime('%Y%m%d_%H%M%S')
    shutil.copy2(up.STATE, bak)
    tmp = up.STATE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, up.STATE)
    print('\n[WRITE]', up.STATE, '备份:', bak)
    return 0


if __name__ == '__main__':
    sys.exit(main())
