#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用新读到的表去核对那几个挂着的待办（只读，不改任何正式产物）。

覆盖的待办（PROJECT_STATUS §6）：
  #6  声优中文姓名回填   —— `voice_actor_cn`（code → actor_name）× `ship_skin_template.voice_actor`
  #10 ① touch_* 别名裁定 —— `character_voice`（key ↔ resource_key ↔ voice_name）就是权威映射
  #10 ③ Spine/立绘配音   —— 同一张表给出全部触发名（detail/get/task/profile/feeling1-5/…）
  #7  阵营码「晶环联盟」  —— 385 新增皮肤的 nationality 取值分布 + `lover_nation` 对照
  #7  新皮肤归属          —— 盘上比基准多出的记录，直接给出 name/ship_group/painting

用法: py -3 tools/sharecfg_re/40_crosscheck_todos.py
"""
import importlib.util, json, os, re, sys, collections

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
spec = importlib.util.spec_from_file_location('m37', os.path.join(HERE, '37_parse_sharecfgdata.py'))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

LUA = os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_out')
CFG = os.path.join(ROOT, '.diag', 'sharecfg_re', 'cfg_json_scalar')
BASE = os.path.join(ROOT, 'inputs', 'azdata', 'azdata_ship_skin_template.json')


def load_lua(name):
    """读一张「只在 Lua 侧」的小表：去掉 5 字节魔数后走同一套 记录帧 + 常量区。
    返回常量区里出现的**所有字典常量**（这类表每条记录 = 一个 dict 常量）。"""
    b = open(os.path.join(LUA, name + '.bytes'), 'rb').read()
    body = b[5:]                      # 去掉 5 字节容器魔数
    out = []
    nrec = 0
    for (start, end, f) in M.iter_records(body):   # ⚠️ 必须走完所有记录，只读第一条会静默截断
        nrec += 1
        r = M.R(body, start, end)
        try:
            cpos, f2, _ = r.header()
        except M.Cur:
            continue
        items, _s = M.kgc_list(body, cpos, end)
        out += [v for (_p, v) in items if isinstance(v, dict)]
    return out, f, nrec, end


def show(title):
    print('\n' + '=' * 72 + '\n' + title + '\n' + '=' * 72)


def main():
    skin = json.load(open(os.path.join(CFG, 'ship_skin_template.json'), encoding='utf-8'))
    base = json.load(open(BASE, encoding='utf-8'))

    va, vf, vn, vstop = load_lua('voice_actor_cn')
    cv, cf, cn, cstop = load_lua('character_voice')
    ln, lf, ln_n, lstop = load_lua('lover_nation')

    show('① 声优中文姓名（待办 #6）')
    by_code = {}
    for d in va:
        if 'actor_name' in d and 'code' in d:
            by_code[int(d['code'])] = d['actor_name'].strip()
    print('  voice_actor_cn: 解析出 %d 条 code→中文名（表内字典常量 %d 个）' % (len(by_code), len(va)))
    ids = collections.Counter()
    miss = collections.Counter()
    for rid, r in skin.items():
        v = r.get('voice_actor')
        if isinstance(v, int):
            ids[v] += 1
            if v not in by_code:
                miss[v] += 1
    print('  ship_skin_template 用到 %d 个不同 voice_actor 值，其中不在中文名表里的 %d 个（涉及 %d 条皮肤）'
          % (len(ids), len(miss), sum(miss.values())))
    print('  样例: ' + ' | '.join('%s→%s' % (k, by_code[k]) for k in sorted(by_code)[:6] if isinstance(k, int)))
    if miss:
        print('  缺名字的 id(前 12): %s' % sorted(miss)[:12])
    json.dump({str(k): v for k, v in sorted(by_code.items())},
              open(os.path.join(LUA, '..', 'voice_actor_cn.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('  已写全量映射: .diag/sharecfg_re/voice_actor_cn.json')
    print('  记录数 %d（本表在盘上分成多条记录，必须全部走完）' % vn)

    show('② Live2D 点击动作别名（待办 #10 ①）')
    keys = [d for d in cv if 'key' in d]
    print('  character_voice: %d 条语音定义，字段 %s' % (len(keys), sorted(keys[0])))
    both = [d for d in keys if d.get('l2d_action') or d.get('spine_action')]
    print('  其中带 l2d_action / spine_action 的 %d 条 ⇒ 这张表就是「台词字段 ↔ Live2D 动作组 ↔ ACB 资源名 ↔ Spine 动作」的权威映射' % len(both))
    for d in keys:
        if 'touch' in str(d.get('key', '')) or 'touch' in str(d.get('resource_key', '')):
            print('    key=%-13s resource_key=%-14s l2d_action=%-22r spine_action=%-22r voice_name=%r' %
                  (d.get('key'), d.get('resource_key'), d.get('l2d_action'),
                   d.get('spine_action'), d.get('voice_name')))
    names = collections.Counter(str(d.get('key')) for d in keys)
    print('  全部 key 共 %d 种，出现最多的 20 个: %s' % (len(names), [k for k, _ in names.most_common(20)]))

    show('③ 触发名总表（待办 #10 ③：Spine/立绘配音要的就是这个）')
    rk = collections.Counter(str(d.get('resource_key')) for d in keys)
    print('  resource_key %d 种；含 detail/get/task/profile/feeling/present/title 的：' % len(rk))
    print('    ' + ', '.join(sorted(k for k in rk if re.match(r'(detail|get|task|profile|feeling\d|present_\w+|title|upgrade|hp_warning|login|main)', k)))[:1200])

    show('④ 385 比基准多出的皮肤（待办 #7：新皮肤归属）')
    extra = sorted(set(skin) - set(base))
    print('  多出 %d 条: %s' % (len(extra), extra[:12]))
    for rid in extra[:12]:
        r = skin[rid]
        print('    id=%-9s name=%-28r ship_group=%-7s painting=%-20r voice_actor=%s' %
              (rid, r.get('name'), r.get('ship_group'), r.get('painting'), r.get('voice_actor')))

    show('⑤ 阵营码（待办 #7：晶环联盟）')
    print('  lover_nation 给出 %d 条：nation / letter / bg' % len(ln))
    letters = {int(d['nation']): d.get('letter') for d in ln if 'nation' in d}
    print('  nation→letter: %s' % dict(sorted(letters.items())))
    nat = collections.Counter()
    try:
        sds = json.load(open(os.path.join(CFG, 'ship_data_statistics.json'), encoding='utf-8'))
        for r in sds.values():
            if isinstance(r.get('nationality'), int):
                nat[r['nationality']] += 1
        print('  ship_data_statistics 里 nationality 实际取值分布: %s' % dict(sorted(nat.items())))
        unknown = [k for k in nat if k not in letters]
        print('  其中 lover_nation 没覆盖的码: %s' % unknown)
    except FileNotFoundError:
        print('  (ship_data_statistics 未导出)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
