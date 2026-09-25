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
import collections, json, os, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
DEF_OLD = os.path.join(ROOT, 'Output', '_OLD_bak', 'l2d_voice_pre_25.json')
DEF_NEW = os.path.join(ROOT, 'Output', 'gallery_v2', 'l2d_voice.json')


def main():
    old_p = sys.argv[1] if len(sys.argv) > 1 else DEF_OLD
    new_p = sys.argv[2] if len(sys.argv) > 2 else DEF_NEW
    o = json.load(open(old_p, encoding='utf-8'))
    n = json.load(open(new_p, encoding='utf-8'))
    lost = [(k, g) for k in o if k in n for g in o[k] if g not in n[k]]
    gone = [k for k in o if k not in n]
    print('旧表 %s -> 新表 %s' % (os.path.basename(old_p), os.path.basename(new_p)))
    print('皮肤 %d -> %d ；(皮肤,组) %d -> %d ；文件条目 %d -> %d' % (
        len(o), len(n), sum(len(v) for v in o.values()), sum(len(v) for v in n.values()),
        sum(len(x) for v in o.values() for x in v.values()),
        sum(len(x) for v in n.values() for x in v.values())))
    print('丢掉的 (皮肤,组) = %d %s ；丢掉的皮肤 = %d %s' % (len(lost), lost[:4], len(gone), gone[:4]))
    add = collections.Counter(g for k in n for g in n[k] if k in o and g not in o[k])
    print('新增动作组分布:', dict(add.most_common(10)))
    paths = [p for k in n for g in n[k] for p in n[k][g]]
    missing = [p for p in paths if not os.path.exists(os.path.join(ROOT, 'Output', p))]
    small = [p for p in paths if os.path.exists(os.path.join(ROOT, 'Output', p))
             and os.path.getsize(os.path.join(ROOT, 'Output', p)) < 2048]
    tot = sum(os.path.getsize(os.path.join(ROOT, 'Output', p)) for p in paths
              if os.path.exists(os.path.join(ROOT, 'Output', p)))
    print('音频 %d 个：磁盘缺失 %d、<2KB %d、合计 %.1f MB' % (len(paths), len(missing), len(small), tot / 1048576.0))
    if missing[:3]:
        print('  缺失样例:', missing[:3])
    bad = bool(lost or gone or missing or small)
    print('零回退判定:', '不通过（有丢失/占位）' if bad else '通过')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
