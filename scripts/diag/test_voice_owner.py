# -*- coding: utf-8 -*-
"""语音归属解析器的反向对照测试（后缀三分类）。

为什么单独一个文件：`resolve()` 的三档分类（画法后缀 / 改造=同角色皮肤 / 黑化=独立发声实体）
是**语义裁定**的落地（2026-10-02 用户口径，见 docs/TROUBLESHOOTING.md §83），
它坏掉的方式不是崩，而是**静默把台词派给另一个实体**——正向跑全库看不出来（本轮就差点把
"回退到本体"误标成"命中自有行"当成成果报出去，靠逐条核样例才发现）。
⇒ 每条规则都配一个"必须不成立"的对照，且全部用合成数据走 `resolve()` 真入口。

用法: py -3 scripts/diag/test_voice_owner.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')

import extract_cv_voice as E      # noqa: E402

# 合成：painting → [(cv, idx)]。⚠️ 名字必须真的以裁定过的那几个后缀**结尾**，
# 否则测的是"查无此名"而不是分类规则（上一版 fixture 写成 `_alt` 就是白测两条）。
ROWS = {
    'tongti':        [(1001, 0)],   # 本体
    'tongti_alter':  [(9001, 0)],   # 改造版：同角色的另一套皮肤，有自己的行与包
    'gaizao_alter':  [(9006, 7)],   # 改造版：有行，但包没下发
    'gaizao':        [(1006, 0)],   # ↑ 它的本体（回退要有落点，否则测的是"查无此名"）
    'heihua_hei':    [(9003, 0)],   # 黑化版：有行也有包（游戏真给它配了声）
    'hei2_hei':      [(9004, 0)],   # 黑化版：有行，包没下发
    'hei3_hei_n':    [(9005, 3)],   # 黑化版的无背景版：有行，包没下发
    'both_alter_hei': [(9007, 0)],  # 改造+黑化：黑化必须压过改造
}
BANKS = {1001, 9001, 9003, 1006}     # 盘上真有主包的 cv；其余都没下发
# 让 ship_stem 能把 `solo_9_n` 归到 `solo`（同船回退那条路要有样本）
ROWS['solo'] = [(2002, 0)]
BANKS.add(2002)


def one(name):
    res, miss = E.resolve([name], ROWS, BANKS)
    return res.get(name), (name in miss)


CASES = [
    # (说明, 皮肤名, 期望 cv, 期望 src)  —— 期望 cv=None 表示"必须判无解"
    ('改造立绘必须停在改造自己那一行，不能跳回本体',
     'tongti_alter', 9001, 'row'),
    ('改造立绘的另一张画（无背景版）也必须停在改造那一行',
     'tongti_alter_n', 9001, 'strip'),
    ('画法后缀单独剥一层就该命中（本体无背景版 = 本体）',
     'tongti_n', 1001, 'strip'),
    ('改造版包没下发时，允许回退到本体（同一角色，用户口径"相当于皮肤"）',
     'gaizao_alter', 1006, 'strip'),
    ('同上，带画法后缀也要走这条回退',
     'gaizao_alter_n', 1006, 'strip'),
    ('黑化版有自己的包 → 用它自己的',
     'heihua_hei', 9003, 'row'),
    ('黑化版没自己的包 → 必须判无解，**不许**回退到本体（独立发声实体）',
     'hei2_hei', None, None),
    ('黑化版连画法后缀也不许救回来',
     'hei3_hei_n', None, None),
    ('改造+黑化同时出现时，黑化优先（独立实体压过同角色皮肤）',
     'both_alter_hei', None, None),
    ('普通"第 N 套皮肤"仍走同船回退，且序号档留空等解码',
     'solo_9_n', 2002, 'sibling'),
]

fails = 0
for desc, name, want_cv, want_src in CASES:
    got, missed = one(name)
    ok = (want_cv is None and missed) or (got and got['cv'] == want_cv and got['src'] == want_src)
    fails += 0 if ok else 1
    实得 = '无解' if missed else (f'{got["cv"]}/{got["src"]}' if got else '没算出来')
    print('%s %-46s %-16s 期望 %-12s 实得 %s'
          % ('✓' if ok else '✗', desc, name,
             ('无解' if want_cv is None else f'{want_cv}/{want_src}'), 实得))

# 最后一条：全库回归口径 —— 改完不得让"能解析"的总数莫名增加（黑化那批必须掉下去）
keys = E.gallery_keys()
rows = E.load_skin_rows(); banks = E.banks_on_disk()
res, miss = E.resolve(keys, rows, banks)
hei = [k for k in res if E.HEI_SUF.search(E.art_chain(k.lower())[-1])]
print('\n%s 全库 %d 个皮肤名：可解析 %d · 无解 %d；黑化名里仍被派到别人包的: %d（须为 0）'
      % ('[OK]' if not hei else '[FAIL]', len(keys), len(res), len(miss), len(hei)))
fails += len(hei)

print('\n%s 语音归属解析 %d/%d' % ('[PASS]' if not fails else '[FAIL]',
                                 len(CASES) + 1 - fails, len(CASES) + 1))
sys.exit(1 if fails else 0)
