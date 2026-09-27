#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语音映射表（l2d_voice.json）改前/改后零回退比对。

判据（任一不为 0 就不得声称"重导安全"）：
  丢掉动作组的 (皮肤,组) 数 = 0；映射指向但磁盘缺失的音频 = 0；<2KB 的占位文件 = 0。
另报新增组分布与总大小，供人核对"新增数 = 皮肤数 × 别名新增类别数"。

踩坑：映射里的路径是**相对 `Output/`**（如 `Audio/L2D/<皮肤>/<cue>.ogg`），
不是相对 `gallery_v2/`；拿错根会误报"全部缺失"（`docs/TROUBLESHOOTING.md` §37）。

用法:
  py -3 scripts/diag/l2d_voice_diff_check.py                     # 默认 备份 vs 现行
  py -3 scripts/diag/l2d_voice_diff_check.py 旧表.json 新表.json
"""
import collections, json, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
DEF_OLD = os.path.join(ROOT, 'Output', '_OLD_bak', 'l2d_voice_pre_25.json')
DEF_NEW = os.path.join(ROOT, 'Output', 'gallery_v2', 'l2d_voice.json')


def gmap(t):
    """把两种表形都归一成 {皮肤:{动作组:[路径]}}（v2 取它的 `l2d` 子表）。"""
    out = {}
    for k, v in t.items():
        out[k] = (v.get('l2d') or {}) if isinstance(v, dict) and 'l2d' in v else v
    return out


def all_paths(t):
    """一张表引用到的全部音频路径（v2 还要算 tap 与台词清单），去重。"""
    s = set()
    for v in t.values():
        if isinstance(v, dict) and 'l2d' in v:
            for a in (v.get('l2d') or {}).values():
                s.update(a)
            s.update((v.get('tap') or {}).values())
            s.update(l['f'] for l in (v.get('lines') or []) if l.get('f'))
        elif isinstance(v, dict):
            for a in v.values():
                s.update(a)
    return sorted(s)


def old_is_other_skin_index(old_path, idx):
    """v2 迁移专用裁定：cue 名尾部的 `_N` 是**皮肤序号**（§47），旧管线把它当随机变体全导、
    前端再 `Math.random()` 抽一条 ⇒ 旧表里存在"本皮肤拿到别的皮肤序号台词"的条目。
    这类 (皮肤,组) 在新表里消失是**修正**，不是回退；序号对不上或无序号的才算真丢。"""
    stem = os.path.splitext(os.path.basename(old_path))[0]
    m = re.search(r'_(\d+)$', stem)
    return idx is not None and bool(m) and int(m.group(1)) != int(idx)


def main():
    old_p = sys.argv[1] if len(sys.argv) > 1 else DEF_OLD
    new_p = sys.argv[2] if len(sys.argv) > 2 else DEF_NEW
    o = json.load(open(old_p, encoding='utf-8'))
    n = json.load(open(new_p, encoding='utf-8'))
    # 表形兼容：v1 = {皮肤:{组:[路径]}}；v2 = {皮肤:{cv,idx,src,l2d:{组:[...]},tap:{},lines:[]}}
    o_g, n_g = gmap(o), gmap(n)
    lost = [(k, g) for k in o_g if k in n_g for g in o_g[k] if g not in n_g[k]]
    gone = [k for k in o_g if k not in n_g]
    print('旧表 %s -> 新表 %s' % (os.path.basename(old_p), os.path.basename(new_p)))
    print('皮肤 %d -> %d ；(皮肤,组) %d -> %d ；文件条目 %d -> %d' % (
        len(o_g), len(n_g), sum(len(v) for v in o_g.values()), sum(len(v) for v in n_g.values()),
        sum(len(x) for v in o_g.values() for x in v.values()),
        sum(len(x) for v in n_g.values() for x in v.values())))
    print('丢掉的 (皮肤,组) = %d %s ；丢掉的皮肤 = %d %s' % (len(lost), lost[:4], len(gone), gone[:4]))
    # v2 迁移：旧表里"本皮肤拿到别的皮肤序号台词"的条目消失属修正，单列出来，不计入回退
    fixed, real_lost = [], []
    for k, g in lost:
        idx = n.get(k, {}).get('idx') if isinstance(n.get(k), dict) else None
        files = o_g[k][g]
        if files and all(old_is_other_skin_index(p, idx) for p in files):
            fixed.append((k, g, files[0], idx))
        else:
            real_lost.append((k, g))
    if fixed:
        print('其中「旧表派错了皮肤序号台词」、新表已纠正 = %d' % len(fixed))
        for k, g, p, idx in fixed[:8]:
            print('   %s/%s 旧=%s 本皮肤序号=%s' % (k, g, os.path.basename(p), idx))
    real_lost += [('%s(整皮肤消失)' % k, '-') for k in gone]
    print('真·丢组 = %d %s' % (len(real_lost), real_lost[:6]))
    add = collections.Counter(g for k in n_g for g in n_g[k] if k in o_g and g not in o_g[k])
    print('新增动作组分布:', dict(add.most_common(10)))
    paths = all_paths(n)
    missing = [p for p in paths if not os.path.exists(os.path.join(ROOT, 'Output', p))]
    small = [p for p in paths if os.path.exists(os.path.join(ROOT, 'Output', p))
             and os.path.getsize(os.path.join(ROOT, 'Output', p)) < 2048]
    tot = sum(os.path.getsize(os.path.join(ROOT, 'Output', p)) for p in paths
              if os.path.exists(os.path.join(ROOT, 'Output', p)))
    print('音频 %d 个：磁盘缺失 %d、<2KB %d、合计 %.1f MB' % (len(paths), len(missing), len(small), tot / 1048576.0))
    if missing[:3]:
        print('  缺失样例:', missing[:3])
    bad = bool(real_lost or missing or small)
    print('零回退判定:', '不通过（有丢失/占位）' if bad else '通过')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
