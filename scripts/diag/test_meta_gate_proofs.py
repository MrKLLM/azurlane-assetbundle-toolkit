# -*- coding: utf-8 -*-
"""闸门判据的反向对照测试：`ship_meta_authority_diff.row_backed()`。

为什么单独一个文件：这条判据是"权威源升级时允许 base_painting 改动"的唯一出口。
它写错的方向是**放行回退**（把新值换成更远/不存在的行也认），而正向跑一遍永远看不出来——
只有把反向样本喂进去才知道它拦不拦。⇒ 每条都配一个"必须为 False"的对照。

用法: py -3 scripts/diag/test_meta_gate_proofs.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

import ship_meta_authority_diff as G      # noqa: E402

TAB = {'aierdeliqi', 'aierdeliqi_9', 'mile', 'mile_3', 'lingmin', 'npclingmin_alter'}
CASES = [
    # (说明, (key, field, old, new), 期望)
    ('变体名退回远亲 → 停在表里真实存在的近行（本轮真实改动）',
     (('aierdeliqi_9_n', 'base_painting', 'aierdeliqi', 'aierdeliqi_9'), TAB), True),
    ('本名行自己补上（旧值是别的行）',
     (('mile_3', 'base_painting', 'mile', 'mile_3'), TAB), True),
    ('反向：从近行退回远亲 = 回退，必须拦',
     (('aierdeliqi_9_n', 'base_painting', 'aierdeliqi_9', 'aierdeliqi'), TAB), False),
    ('新 base 在权威表里根本没有这一行 = 凭空造名，必须拦',
     (('aierdeliqi_9_n', 'base_painting', 'aierdeliqi', 'aierdeliqi_12'), TAB), False),
    ('新 base 不是本名的前缀（换成不相干的皮肤）',
     (('aierdeliqi_9_n', 'base_painting', 'aierdeliqi', 'mile_3'), TAB), False),
    ('改的不是 base_painting 字段（skin_name 之类不走这条）',
     (('aierdeliqi_9_n', 'skin_name', '埃尔德里奇', '金月桂香'), TAB), False),
    ('旧值为空（从无到有不算"升级"，该走新增条目那条判据）',
     (('mile_3', 'base_painting', '', 'mile_3'), TAB), False),
    ('新旧相同（没改动却混进这条计数）',
     (('mile_3', 'base_painting', 'mile_3', 'mile_3'), TAB), False),
]

fails = 0
for desc, args, want in CASES:
    got = G.row_backed(*args)
    ok = got == want
    fails += 0 if ok else 1
    print('%s %-52s 期望 %-5s 实得 %s' % ('✓' if ok else '✗', desc, want, got))
print('\n%s 判据反向对照 %d/%d' % ('[PASS]' if not fails else '[FAIL]', len(CASES) - fails, len(CASES)))
sys.exit(1 if fails else 0)
