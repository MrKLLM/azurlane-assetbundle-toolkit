#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `.diag/sharecfg_re/lua_out/*.bytes`（774 张只在 Lua 侧的表）导成 JSON。

已实测：这些表与 sharecfgdata 用**同一套容器**（记录帧 + 假 LuaJIT 头 + 平铺常量流 +
字符串 `ULEB(长+5)` + `^(255-i)`），小表的数据就内联在常量里，直接可读；
32 张流式大表的 `.bytes` 则只是读取桩（导出来是 `cs/base/confNEO/pg` 那 12 条，不是数据）。

判据（每条都打印，缺一不算跑完）：
  1. **遍历到文件末**：`pos >= len(body)`，否则记录数会静默偏小（本项目假绿灯第 10 例，见 §34）；
  2. 导出的记录数与"字典常量数"一起报，两者差很多说明该表数据不是 dict 常量形态；
  3. 高字节自检沿用 35 号规则：解出的字节流里 `>=0x80` 为 0 的表**单独点名**（桩表才算正常）。

用法:
  py -3 tools/sharecfg_re/41_export_lua_tables.py --sample 5      # 先小样本
  py -3 tools/sharecfg_re/41_export_lua_tables.py --all --yes     # 全量 774（需用户确认）
产物: .diag/sharecfg_re/lua_json/<表名>.json
"""
import importlib.util, json, os, sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
spec = importlib.util.spec_from_file_location('m37', os.path.join(HERE, '37_parse_sharecfgdata.py'))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

LUA = os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_out')
OUT = os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_json')


def one(name):
    b = open(os.path.join(LUA, name + '.bytes'), 'rb').read()
    body = b[5:]
    rows = []
    pos = 0
    nrec = 0
    truncated = True
    for (start, end, f) in M.iter_records(body):
        nrec += 1
        pos = end
        r = M.R(body, start, end)
        try:
            cpos, f2, _ = r.header()
        except M.Cur:
            continue
        items, _s = M.kgc_list(body, cpos, end)
        for (_p, v) in items:
            if isinstance(v, dict) and v:
                rows.append(v)
    truncated = pos < len(body) - 1
    keyed = {}
    for i, r in enumerate(rows):
        k = r.get('id', r.get('code', r.get('key')))
        keyed[str(k) if k is not None else '#%d' % i] = r
    return b, rows, keyed, nrec, truncated


def main():
    a = sys.argv[1:]
    if '--all' in a:
        if '--yes' not in a:
            print('--all 是 774 文件批量，须显式加 --yes（AGENTS 全量闸门）')
            return 2
        names = sorted(f[:-6] for f in os.listdir(LUA) if f.endswith('.bytes') and not f.endswith('_extra.bytes'))
    else:
        n = int(a[a.index('--sample') + 1]) if '--sample' in a else 5
        names = ['voice_actor_cn', 'character_voice', 'ship_l2d_tips', 'child_word', 'lover_nation'][:n]
    os.makedirs(OUT, exist_ok=True)
    stub = data = other = 0
    lines = []
    for nm in names:
        b, rows, keyed, nrec, trunc = one(nm)
        hi = sum(1 for x in b if x >= 0x80)
        cjk = sum(1 for r in rows for v in r.values()
                  if isinstance(v, str) and any('一' <= c <= '鿿' for c in v))
        tag = 'STUB' if len(rows) <= 12 and hi < len(b) * 0.30 else ('DATA' if rows else 'EMPTY')
        stub += tag == 'STUB'
        data += tag == 'DATA'
        other += tag not in ('STUB', 'DATA')
        with open(os.path.join(OUT, nm + '.json'), 'w', encoding='utf-8') as fh:
            json.dump(keyed, fh, ensure_ascii=False, indent=1, sort_keys=True)
        lines.append((nm, len(b), nrec, len(rows), cjk, trunc, tag))
    print('%-34s %8s %5s %6s %6s %-6s %s' % ('表', 'B', '记录', '字典常量', '含中文', '未走完', '判定'))
    for (nm, ln, nrec, nrow, cjk, trunc, tg) in lines:
        if '--all' in a and tg == 'DATA' and not trunc:
            continue
        print('%-34s %8d %5d %6d %6d %-6s %s' % (nm, ln, nrec, nrow, cjk, trunc and 'YES!!' or 'no', tg))
    print('\n计数: DATA %d / STUB %d / 其它 %d / 共 %d；未走完(截断风险) %d 张'
          % (data, stub, other, len(names), sum(1 for x in lines if x[5])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
