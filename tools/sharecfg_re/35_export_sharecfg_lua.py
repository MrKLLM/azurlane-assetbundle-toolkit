#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从已解开的 scripts64/scripts32 里导出 sharecfg 的 lua 表（以及 gamecfg 等），
并顺手判一下它们到底是不是 LuaJIT 字节码。

背景：`34_www_four_modes.py` 把 www() 的四种模式按块号 %4 全部落成代码后，
`scripts64` 整包解出、UnityPy 可开：容器条目 45,739 个，其中
`assets/luabuilds/android/arm64/sharecfg/*.lua.bytes` **774 个**（与内存快照里那份
776 项 sharecfg 清单基本吻合），另有 gamecfg 38,178 / view 3,774 / mod 1,533 等。
每个条目的字节以 `1b 4c 4a 02 0a` 开头 = 我们追了二十轮的容器头部。

⚠️ 默认只导 3 个样本（`--limit`），全量 774 个要先经用户确认（AGENTS 全量规则）。
用法:
  py -3 tools/sharecfg_re/35_export_sharecfg_lua.py                # 3 个样本 + 格式判定
  py -3 tools/sharecfg_re/35_export_sharecfg_lua.py --limit 0      # 全量（需确认）
产物: .diag/sharecfg_re/lua_out/<name>.lua
"""
import os, struct, sys, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DI = os.path.join(ROOT, '.diag', 'sharecfg_re')
AB = os.path.join(DI, 'scripts64.full.ab')
OUT = os.path.join(DI, 'lua_out')
HDR = bytes.fromhex('1b4c4a020a')


def bc_probe(b):
    """按 LuaJIT 2.1 BC dump 的结构做**否证式**检查（不看像不像，看能不能自洽走通）。"""
    i = len(HDR)
    tags = collections.Counter()
    ok = True
    why = ''
    try:
        while i < len(b):
            tag = b[i]
            if tag > 0x10:
                ok = False; why = '第 %d 字节 section tag=%02x 越界(>0x10)' % (i, tag); break
            i += 1
            n = 0
            v = 0
            while True:                      # ULEB128
                if i >= len(b):
                    raise EOFError
                c = b[i]; i += 1
                v |= (c & 0x7F) << n; n += 7
                if not (c & 0x80):
                    break
            tags[tag] += 1
            if tag == 0:                     # BCDUMP_PROTO_HEADER: 8 个 ULEB + 1 字节 flags
                continue
    except Exception as e:
        ok = False; why = 'ULEB 走飞：%s（停在 %d / %d）' % (type(e).__name__, i, len(b))
    return ok, why, tags


def grab(env, path_id_map, name):
    """**必须走这条路**：UnityPy 的 TextAsset.m_Script 是 str 且按 UTF-8 errors=replace 解码，
    实测 80,505 字节里有 32,935 个字节被打成 U+FFFD（>=0x80 的字节全变 0）——
    用 m_Script 导出会静默毁数据。正确做法：容器项 -> PPtr.m_PathID -> Object.get_raw_data()，
    再按 "int32 长度前缀 + 1b4c4a020a" 定位取字节。"""
    c = env.container
    v = c[name]
    pp = v[0] if isinstance(v, (list, tuple)) else v
    pid = getattr(pp, 'm_PathID', None)
    obj = path_id_map.get(pid)
    if obj is None:
        return None, '找不到 pathID %s 的对象' % pid
    raw = obj.get_raw_data()
    i = raw.find(HDR)
    if i < 4:
        return None, '原始数据里没有容器魔数'
    ln = struct.unpack_from('<i', raw, i - 4)[0]
    body = raw[i:i + ln] if 0 < ln <= len(raw) - i else raw[i:]
    if len(body) != ln:
        return body, '长度前缀 %d 与实际 %d 不符' % (ln, len(body))
    return body, None


def main():
    limit = 3
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
    import UnityPy
    env = UnityPy.Environment(AB)
    c = env.container
    pid_map = {o.path_id: o for o in env.objects}
    names = sorted(k for k in c if '/sharecfg/' in k)
    print('sharecfg 条目 = %d（bundle 内总条目 %d）' % (len(names), len(c)))
    if limit:
        want = ('ship_skin_words.lua.bytes', 'ship_skin_template.lua.bytes', 'gametip.lua.bytes')
        pick = [n for n in names if n.rsplit('/', 1)[-1] in want][:limit] or names[:limit]
    else:
        pick = names
    os.makedirs(OUT, exist_ok=True)
    stat = collections.Counter()
    for k in pick:
        b, err = grab(env, pid_map, k)
        if b is None:
            print('  失败 %-40s %s' % (k.rsplit('/', 1)[-1], err)); stat['fail'] += 1; continue
        hi = sum(1 for x in b if x >= 0x80)
        if hi == 0:
            print('  !! %-40s 无任何 >=0x80 字节 -> 又走了有损路径，停' % k.rsplit('/', 1)[-1]); return 3
        p = os.path.join(OUT, k.rsplit('/', 1)[-1].replace('.lua.bytes', '.bytes'))
        open(p, 'wb').write(b)
        ok, why, tags = bc_probe(b)
        stat['ok'] += 1
        if limit:
            print('  %-38s %8d B  头=%s  高字节 %d  ->  %s' % (k.rsplit('/', 1)[-1], len(b),
                  b[:5].hex(' '), hi, p))
            print('      LuaJIT-BC 自洽 = %s %s section=%s' % ('是' if ok else '否',
                  '' if ok else '(' + why + ')', dict(list(tags.items())[:6])))
    print('计数 =', dict(stat), '（本次导出 %d 个；全量 774 个需 --limit 0 + 用户确认）' % len(pick))
    return 0


if __name__ == '__main__':
    sys.exit(main())
