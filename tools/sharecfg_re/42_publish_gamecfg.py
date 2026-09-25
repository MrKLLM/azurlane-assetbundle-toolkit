#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把从游戏本体解出的两张**权威映射**发布成管线可用的输入（含台账）。

为什么单独一步：`build_ship_meta.py` 与 `extract_live2d_voice.py` 过去靠
「社区快照 + 语义推断」，而这两张表现在是**从游戏文件直接解出的事实**：
  voice_actor_cn    code → 中文声优名        （替代"CV 姓名表未缓存"）
  character_voice   台词字段 → Live2D 动作组 → ACB 资源名 → Spine 动作 → 中文名
                                              （替代 extract_live2d_voice 里注释自承的"语义推断"）

产物**不入库**（`.gitignore: inputs/*/*.json`），台账 `inputs/gamecfg/MANIFEST.json` 入库。
数据本体可由 `34 → 35 → 41 → 本脚本` 一键重取，但**重取要模拟器同步过的 assets**，
故仍属承重文件，清理磁盘前按 WF-15 白名单核对。

用法: py -3 tools/sharecfg_re/42_publish_gamecfg.py [--check]
"""
import hashlib, json, os, sys, datetime

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LUAJ = os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_json')
DST = os.path.join(ROOT, 'inputs', 'gamecfg')

SPECS = [
    ('voice_actor_cn.json', 'voice_actor_cn',
     '声优 code → 中文姓名（游戏本体 9.7.385，525 条）',
     ['scripts/build_ship_meta.py']),
    ('character_voice.json', 'character_voice',
     '台词字段 key ↔ Live2D 动作组 l2d_action ↔ ACB 资源名 resource_key ↔ Spine 动作 ↔ 中文语音名（85 条）',
     ['scripts/extract_live2d_voice.py']),
]


def reshape(name, rows):
    if name == 'voice_actor_cn':
        out = {}
        for r in rows:
            if isinstance(r, dict) and 'code' in r and 'actor_name' in r:
                out[str(int(r['code']))] = str(r['actor_name']).strip()
        return out
    if name == 'character_voice':
        out = {}
        for r in rows:
            if isinstance(r, dict) and r.get('key'):
                out[str(r['key'])] = {k: r.get(k) for k in
                                      ('voice_name', 'resource_key', 'l2d_action', 'spine_action',
                                       'sp_trans_l2d', 'profile_index')}
        return out
    return {str(i): r for i, r in enumerate(rows)}


def main():
    check = '--check' in sys.argv
    os.makedirs(DST, exist_ok=True)
    ledger = {'schema_version': 1,
              'purpose': '从游戏本体 sharecfg 容器直接解出的权威映射，管线以此为准（优于社区快照与语义推断）',
              'provenance': {'game_version_local_assets': '9.7.385',
                             'container_grammar': 'docs/TROUBLESHOOTING.md §33/§34',
                             'regenerate_via': ['tools/sharecfg_re/34_www_four_modes.py',
                                                'tools/sharecfg_re/35_export_sharecfg_lua.py',
                                                'tools/sharecfg_re/41_export_lua_tables.py',
                                                'tools/sharecfg_re/42_publish_gamecfg.py'],
                             'landed_at': datetime.date.today().isoformat()},
              'files': []}
    for fn, src, role, consumers in SPECS:
        raw = json.load(open(os.path.join(LUAJ, src + '.json'), encoding='utf-8'))
        rows = [v for v in raw.values() if isinstance(v, dict) and len(v) > 1]
        data = reshape(src, rows)
        p = os.path.join(DST, fn)
        blob = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
        if not check:
            open(p, 'w', encoding='utf-8').write(blob)
        h = hashlib.sha256(blob.encode('utf-8')).hexdigest()
        ledger['files'].append({'path': fn, 'bytes': len(blob.encode('utf-8')), 'sha256': h,
                                'rows': len(data), 'role': role, 'consumers': consumers})
        print('%-24s 行 %-5d sha256 %s…  %s' % (fn, len(data), h[:12],
              '已写入' if not check else '（--check 未写）'))
    # 自检：真值抽查（这两条是 §34 里取证过的具体事实，改坏了这里就该红）
    va = json.load(open(os.path.join(LUAJ, 'voice_actor_cn.json'), encoding='utf-8'))
    who = {str(int(r['code'])): str(r['actor_name']).strip() for r in va.values()
           if isinstance(r, dict) and 'code' in r and 'actor_name' in r}
    cv = json.load(open(os.path.join(LUAJ, 'character_voice.json'), encoding='utf-8'))
    crows = {str(r['key']): r for r in cv.values() if isinstance(r, dict) and r.get('key')}
    asserts = [('voice_actor 72 → 泛用型布里的声优', who.get('72') is not None),
               ('touch → resource_key touch_1 且 l2d_action touch_body',
                crows.get('touch', {}).get('resource_key') == 'touch_1'
                and crows.get('touch', {}).get('l2d_action') == 'touch_body'),
               ('touch2 → touch_2 / touch_special',
                crows.get('touch2', {}).get('resource_key') == 'touch_2'
                and crows.get('touch2', {}).get('l2d_action') == 'touch_special'),
               ('headtouch → touch_head / touch_head（第三条，此前靠猜）',
                crows.get('headtouch', {}).get('resource_key') == 'touch_head')]
    ok = True
    for t, r in asserts:
        print('  %s %s' % ('✓' if r else '✗', t))
        ok &= bool(r)
    if not ok:
        print('自检不过，台账不写')
        return 3
    if not check:
        mine = {e['path'] for e in ledger['files']}
        mp = os.path.join(DST, 'MANIFEST.json')
        if os.path.exists(mp):  # 按 path 合并：不清掉别的发布脚本（44/45）记的条目
            prev = json.load(open(mp, encoding='utf-8'))
            old = [f for f in prev.get('files', []) if f.get('path') not in mine]
            ledger['files'] = sorted(old + ledger['files'], key=lambda f: f['path'])
            rg = ledger['provenance']['regenerate_via']
            rg += [s for s in prev.get('provenance', {}).get('regenerate_via', []) if s not in rg]
        open(mp, 'w', encoding='utf-8').write(
            json.dumps(ledger, ensure_ascii=False, indent=2) + '\n')
        print('台账: inputs/gamecfg/MANIFEST.json（共 %d 条）' % len(ledger['files']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
