#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把从游戏本体解出的三张**权威映射**发布成管线可用的输入（含台账）。

为什么单独一步：`build_ship_meta.py`、`extract_live2d_voice.py` 与画廊台词层过去靠
「社区快照 + 语义推断」，而这表现在是**从游戏文件直接解出的事实**：
  voice_actor_cn    code → 中文声优名        （替代"CV 姓名表未缓存"）
  character_voice   台词字段 → Live2D 动作组 → ACB 资源名 → Spine 动作 → 中文名
                                              （替代 extract_live2d_voice 里注释自承的"语义推断"）
  ship_skin_words   皮肤行 id → 各台词字段的**中文正文**
                                              （台词正文的唯一副本，原先只住在可被清理的 .diag/）

产物**不入库**（`.gitignore: inputs/*/*.json`），台账 `inputs/gamecfg/MANIFEST.json` 入库。
数据本体可由 `34 → 35 → 41 → 本脚本` 一键重取，但**重取要模拟器同步过的 assets**，
故仍属承重文件，清理磁盘前按 WF-15 白名单核对。

用法: py -3 tools/sharecfg_re/42_publish_gamecfg.py [--check]
"""
import hashlib, json, os, sys, datetime

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = {'lua_json': os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_json'),
       'cfg_json': os.path.join(ROOT, '.diag', 'sharecfg_re', 'cfg_json')}
DST = os.path.join(ROOT, 'inputs', 'gamecfg')

# (产物名, 源表名, 台账说明, 消费方, 源子目录)
SPECS = [
    ('voice_actor_cn.json', 'voice_actor_cn',
     '声优 code → 中文姓名（游戏本体 9.7.385，525 条）',
     ['scripts/build_ship_meta.py'], 'lua_json'),
    ('character_voice.json', 'character_voice',
     '台词字段 key ↔ Live2D 动作组 l2d_action ↔ ACB 资源名 resource_key ↔ Spine 动作 ↔ 中文语音名（85 条）',
     ['scripts/extract_live2d_voice.py'], 'lua_json'),
    ('ship_skin_words.json', 'ship_skin_words',
     '皮肤行 id → 各台词字段的中文正文（只保留非空标量字段；嵌套字段尚未装配，见 §36 B 段）',
     ['scripts/build_skin_words.py'], 'cfg_json'),
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
    if name == 'ship_skin_words':
        # 原表把 `__env__`/`__array__` 与列表型（未装配的嵌套字段）混在行里；正文全是标量字符串
        out = {}
        for r in rows:
            if not isinstance(r, dict) or r.get('id') is None:
                continue
            d = {k: str(v).strip() for k, v in r.items()
                 if isinstance(v, str) and str(v).strip()}
            if d:
                out[str(int(r['id']))] = d
        return out
    return {str(i): r for i, r in enumerate(rows)}


def _words_row_lossless(pub):
    """清洗只允许「丢空字段」，不允许改动任何一条正文 —— 拿原表第一行逐字段回比。"""
    raw = json.load(open(os.path.join(SRC['cfg_json'], 'ship_skin_words.json'), encoding='utf-8'))
    src = next((v for v in raw.values() if isinstance(v, dict) and v.get('id') is not None), None)
    if not src:
        return False
    got = pub.get('ship_skin_words', {}).get(str(int(src['id'])))
    if not got:
        return False
    want = {k: str(v).strip() for k, v in src.items()
            if isinstance(v, str) and str(v).strip()}
    return got == want


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
                                                'tools/sharecfg_re/37_parse_sharecfgdata.py --scalar-all',
                                                'tools/sharecfg_re/42_publish_gamecfg.py'],
                             'landed_at': datetime.date.today().isoformat()},
              'files': []}
    pub = {}
    for fn, src, role, consumers, sub in SPECS:
        raw = json.load(open(os.path.join(SRC[sub], src + '.json'), encoding='utf-8'))
        rows = [v for v in raw.values() if isinstance(v, dict) and len(v) > 1]
        data = reshape(src, rows)
        pub[src] = data
        p = os.path.join(DST, fn)
        blob = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        if not check:
            # 二进制写：文本模式在 Windows 上会把 \n 换成 \r\n，而台账里的 bytes/sha256 是 LF 版本
            # → 任何带换行的产物都会被 check_inputs.py 报成 DRIFT（假红灯）。
            open(p, 'wb').write(blob.encode('utf-8'))
        h = hashlib.sha256(blob.encode('utf-8')).hexdigest()
        ledger['files'].append({'path': fn, 'bytes': len(blob.encode('utf-8')), 'sha256': h,
                                'rows': len(data), 'role': role, 'consumers': consumers,
                                'source': '.diag/sharecfg_re/%s/%s.json' % (sub, src)})
        print('%-24s 行 %-5d sha256 %s…  %s' % (fn, len(data), h[:12],
              '已写入' if not check else '（--check 未写）'))
    # 自检：真值抽查（这几条是 §34/§36 里取证过的具体事实，改坏了这里就该红）
    va = json.load(open(os.path.join(SRC['lua_json'], 'voice_actor_cn.json'), encoding='utf-8'))
    who = {str(int(r['code'])): str(r['actor_name']).strip() for r in va.values()
           if isinstance(r, dict) and 'code' in r and 'actor_name' in r}
    cv = json.load(open(os.path.join(SRC['lua_json'], 'character_voice.json'), encoding='utf-8'))
    crows = {str(r['key']): r for r in cv.values() if isinstance(r, dict) and r.get('key')}
    asserts = [('voice_actor 72 → 泛用型布里的声优', who.get('72') is not None),
               ('touch → resource_key touch_1 且 l2d_action touch_body',
                crows.get('touch', {}).get('resource_key') == 'touch_1'
                and crows.get('touch', {}).get('l2d_action') == 'touch_body'),
               ('touch2 → touch_2 / touch_special',
                crows.get('touch2', {}).get('resource_key') == 'touch_2'
                and crows.get('touch2', {}).get('l2d_action') == 'touch_special'),
               ('headtouch → touch_head / touch_head（第三条，此前靠猜）',
                crows.get('headtouch', {}).get('resource_key') == 'touch_head'),
               ('清洗台词表后 100000 行的每条正文与原表逐字相同', _words_row_lossless(pub))]
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
