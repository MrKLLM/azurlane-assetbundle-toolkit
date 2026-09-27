#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布「实体代号表 name_code」：`{namecode:NN}` → 中文实体名（含台账）。

为什么需要：游戏配置里的台词正文**自带占位符**——`ship_skin_words` 的 941 行里有 1760 个
`{namecode:NN}`，游戏运行时才换成名字。我们直接把表里的字符串端给前端，于是
**862 个能播的皮肤的字幕里现在就在显示 `{namecode:98}` 这种东西**（2026-09-27 目视验收时抓到）。
`name_code` 表逐行写着 `id → name`，是权威来源；对齐关系由
`43_check_namecode_alignment.py` 带零假设证成（可解析 1760/1760、自称率 80× 于随机重分配）。

产物不入库（`.gitignore: inputs/*/*.json`），台账 `inputs/gamecfg/MANIFEST.json` 入库。
下游消费者：`scripts/build_skin_words.py`（出台词正文时就地把占位符换成名字）。

用法: py -3 tools/sharecfg_re/46_publish_name_code.py [--check]
"""
import hashlib
import json
import os
import re
import sys
import datetime

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LUAJ = os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_json')
DST = os.path.join(ROOT, 'inputs', 'gamecfg')
OUT_FN = 'name_code.json'
SRC_TABLE = 'name_code'
META = re.compile(r'^#\d+$')

ROLE = ('台词正文里 `{namecode:NN}` 占位符的权威展开表：id → 中文实体名 + 单字代号（456 行，'
        '游戏本体 9.7.385 的 name_code 表）')
CONSUMERS = ['scripts/build_skin_words.py']


def build():
    raw = json.load(open(os.path.join(LUAJ, SRC_TABLE + '.json'), encoding='utf-8'))
    out = {}
    for k, v in raw.items():
        if META.match(str(k)) or not isinstance(v, dict) or v.get('id') is None:
            continue                     # 表尾那个 `#456` 是元信息行，不是数据
        sid = str(int(v['id']))
        name = str(v.get('name') or '').strip()
        if not name:
            continue
        prev = out.get(sid)
        if prev and prev['name'] != name:      # 同一个 id 两个名字 → 停，别让后写的悄悄覆盖
            raise SystemExit('歧义：id %s 同时叫「%s」与「%s」' % (sid, prev['name'], name))
        out[sid] = {'name': name, 'code': str(v.get('code') or '').strip()}
    return out


def selfcheck(data):
    """真值断言：任一条红即不得写文件、不得记台账。"""
    ids = sorted(int(k) for k in data)
    names = {v['name'] for v in data.values()}
    # 最硬的一条：台词里真正用到的每一个码都必须能展开（不是"表好看"，是"下游够用"）。
    # 读的是**已入库那份**（build_skin_words 消费的就是它），不是中间产物。
    words = json.load(open(os.path.join(ROOT, 'inputs', 'gamecfg', 'ship_skin_words.json'),
                           encoding='utf-8'))
    used = {m.group(1) for row in words.values() if isinstance(row, dict)
            for txt in row.values() for m in re.finditer(r'\{namecode:(\d+)\}', str(txt))}
    return [
        ('456 行、id 唯一（id 段不连续是表本身的形状：max=%d）' % max(ids),
         len(data) == 456 and len(set(ids)) == 456),
        ('台词里用到的 %d 个码 100%% 能展开（下游不会漏出占位符）' % len(used),
         bool(used) and used <= set(data)),
        ('没有一行名字还带着 {namecode} 占位符', not any('{namecode' in n for n in names)),
        ('已知实体在表里（明石=商店猫 / 比叡 / 绫波 / Z23）',
         {'明石', '比叡', '绫波'} <= names and any(n.upper() == 'Z23' for n in names)),
        ('每行都有非空单字代号（代号可用于 UI 简称）', all(v['code'] for v in data.values())),
    ]


def merge_ledger(entry):
    path = os.path.join(DST, 'MANIFEST.json')
    led = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else \
        {'schema_version': 1, 'purpose': '从游戏本体 sharecfg 容器直接解出的权威映射，管线以此为准（优于社区快照与语义推断）',
         'provenance': {'regenerate_via': []}, 'files': []}
    prov = led.setdefault('provenance', {})
    prov.setdefault('game_version_local_assets', '9.7.385')
    prov.setdefault('container_grammar', 'docs/TROUBLESHOOTING.md §33/§34')
    prov['landed_at'] = datetime.date.today().isoformat()
    rg = prov.setdefault('regenerate_via', [])
    for s in ('tools/sharecfg_re/41_export_lua_tables.py', 'tools/sharecfg_re/46_publish_name_code.py'):
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
    print('%s 表 %d 行（id %s…%s）' % (SRC_TABLE, len(data), min(map(int, data)), max(map(int, data))))
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
        open(p, 'wb').write(blob.encode('utf-8'))   # 二进制写：CRLF 会让台账 bytes/sha256 永久对不上
    entry = {'path': OUT_FN, 'bytes': len(blob.encode('utf-8')),
             'sha256': hashlib.sha256(blob.encode('utf-8')).hexdigest(),
             'rows': len(data), 'role': ROLE, 'consumers': CONSUMERS,
             'source': '.diag/sharecfg_re/lua_json/name_code.json',
             'alignment_proof': 'tools/sharecfg_re/43_check_namecode_alignment.py（带零假设）'}
    led = merge_ledger(entry)
    if not check:
        json.dump(led, open(os.path.join(DST, 'MANIFEST.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
    print('%-26s 行 %-5d sha256 %s…  %s' % (OUT_FN, len(data), entry['sha256'][:12],
                                            '已写入' if not check else '（--check 未写）'))
    print('台账条目共 %d 条' % len(led['files']))


if __name__ == '__main__':
    main()
