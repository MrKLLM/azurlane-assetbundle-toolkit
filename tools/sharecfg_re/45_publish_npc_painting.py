#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布「秘书舰 NPC 立绘名表」：head/painting 资源名 → 中文显示名（含台账）。

为什么需要这张表：`Output/ship_meta.json` 里有 36 个目录名（linghangyuan* / lingyangzhe* /
tansuozhe* / npclingyangzhe3_2）在 `ship_skin_template` 里**根本没有对应行**——它们不是舰皮肤，
而是指挥室秘书舰 NPC 的换装立绘，因此走不到「painting → skin → statistics」那条桥，
画廊里就一直显示拼音。而游戏自己的 `secretary_special_ship` 表逐行写着
`head` / `painting` 资源名 → `name`（领航员-TB / 领洋者-娜比娅 / 探索者-艾普洛），是权威来源。

产物不入库（`.gitignore: inputs/*/*.json`），台账 `inputs/gamecfg/MANIFEST.json` 入库。
下游消费者：`scripts/build_ship_meta.py`（在 painting/painting_ci 都没命中时查本表）。

用法: py -3 tools/sharecfg_re/45_publish_npc_painting.py [--check]
"""
import hashlib
import json
import os
import sys
import datetime

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LUAJ = os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_json')
DST = os.path.join(ROOT, 'inputs', 'gamecfg')
OUT_FN = 'npc_painting_name.json'
SRC_TABLE = 'secretary_special_ship'

ROLE = ('指挥室秘书舰 NPC 的立绘/头像资源名（小写）→ 中文显示名 + character_id，41 行 3 个实体'
        '（游戏本体 9.7.385 的 secretary_special_ship 表）')
CONSUMERS = ['scripts/build_ship_meta.py']


def build():
    raw = json.load(open(os.path.join(LUAJ, SRC_TABLE + '.json'), encoding='utf-8'))
    out = {}
    for v in raw.values():
        if not isinstance(v, dict) or not v.get('head'):
            continue
        rec = {'cn': str(v.get('name') or '').strip(),
               'character_id': v.get('character_id'),
               'row_id': v.get('id'),
               'group': v.get('group')}
        for f in ('head', 'painting'):
            key = str(v.get(f) or '').strip().lower()
            if key:
                prev = out.get(key)
                # 同一资源名被两行引用且名字不同 -> 报错，不能让后写的悄悄覆盖前一条
                if prev and prev['cn'] != rec['cn']:
                    raise SystemExit('歧义：%s 同时属于「%s」与「%s」' % (key, prev['cn'], rec['cn']))
                out[key] = rec
    return out


def selfcheck(data):
    """四条真值断言：任一条红即不得写文件、不得记台账。"""
    cn = {r['cn'] for r in data.values()}
    return [
        ('实体只有 3 个（领航员-TB / 领洋者-娜比娅 / 探索者-艾普洛）',
         cn == {'领航员-TB', '领洋者-娜比娅', '探索者-艾普洛'}),
        ('linghangyuan1_2 → 领航员-TB（head 列取的）',
         data.get('linghangyuan1_2', {}).get('cn') == '领航员-TB'),
        ('npclingyangzhe3_2 → 领洋者-娜比娅（只在 painting 列，head 是 lingyangzhe3_2）',
         data.get('npclingyangzhe3_2', {}).get('cn') == '领洋者-娜比娅'),
        ('没有一条名字带 {namecode} 占位符',
         not any('{namecode' in r['cn'] for r in data.values())),
        ('每个实体都有 ≥10 张立绘（3 个 NPC 的换装集齐全）',
         all(sum(1 for r in data.values() if r['cn'] == c) >= 10
             for c in ('领航员-TB', '领洋者-娜比娅', '探索者-艾普洛'))),
    ]


def merge_ledger(entry):
    """台账按 path 合并写回：不清掉别的发布脚本（42/44）记的条目。"""
    path = os.path.join(DST, 'MANIFEST.json')
    led = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else \
        {'schema_version': 1, 'purpose': '从游戏本体 sharecfg 容器直接解出的权威映射，管线以此为准（优于社区快照与语义推断）',
         'provenance': {'regenerate_via': []}, 'files': []}
    prov = led.setdefault('provenance', {})
    prov.setdefault('game_version_local_assets', '9.7.385')
    prov.setdefault('container_grammar', 'docs/TROUBLESHOOTING.md §33/§34')
    prov['landed_at'] = datetime.date.today().isoformat()
    rg = prov.setdefault('regenerate_via', [])
    for s in ('tools/sharecfg_re/41_export_lua_tables.py', 'tools/sharecfg_re/45_publish_npc_painting.py'):
        if s not in rg:
            rg.append(s)
    files = [f for f in led.get('files', []) if f.get('path') != OUT_FN]
    files.append(entry)
    files.sort(key=lambda f: f['path'])
    led['files'] = files
    return led


def main():
    check = '--check' in sys.argv
    data = build()
    print('%s 资源名 %d 个，实体 %d 个' % (SRC_TABLE, len(data), len({r['cn'] for r in data.values()})))
    ok = True
    for label, passed in selfcheck(data):
        print('  %s %s' % ('✓' if passed else '✗', label))
        ok &= passed
    if not ok:
        raise SystemExit('自检未通过，未写入任何文件')
    blob = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
    p = os.path.join(DST, OUT_FN)
    if not check:
        os.makedirs(DST, exist_ok=True)
        open(p, 'w', encoding='utf-8').write(blob)
    entry = {'path': OUT_FN, 'bytes': len(blob.encode('utf-8')),
             'sha256': hashlib.sha256(blob.encode('utf-8')).hexdigest(),
             'rows': len(data), 'role': ROLE, 'consumers': CONSUMERS}
    led = merge_ledger(entry)
    if not check:
        json.dump(led, open(os.path.join(DST, 'MANIFEST.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
    print('%-26s 行 %-5d sha256 %s…  %s' % (OUT_FN, len(data), entry['sha256'][:12],
                                            '已写入' if not check else '（--check 未写）'))
    print('台账条目共 %d 条' % len(led['files']))


if __name__ == '__main__':
    main()
