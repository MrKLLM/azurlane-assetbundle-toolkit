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

# 合成：painting → [(语音包号, 包内档位, 表行主键)]（与 `load_skin_rows()` 的三元组同形）。
# ⚠️ 名字必须真的以裁定过的那几个后缀**结尾**，
# 否则测的是"查无此名"而不是分类规则（上一版 fixture 写成 `_alt` 就是白测两条）。
ROWS = {
    'tongti':        [(1001, 0, 10010)],   # 本体
    'tongti_alter':  [(9001, 0, 90010)],   # 改造版：同角色的另一套皮肤，有自己的行与包
    'gaizao_alter':  [(9006, 7, 90067)],   # 改造版：有行，但包没下发
    'gaizao':        [(1006, 0, 10060)],   # ↑ 它的本体（回退要有落点，否则测的是"查无此名"）
    'heihua_hei':    [(9003, 0, 90030)],   # 黑化版：有行也有包（游戏真给它配了声）
    'hei2_hei':      [(9004, 0, 90040)],   # 黑化版：有行，包没下发
    'hei3_hei_n':    [(9005, 3, 90053)],   # 黑化版的无背景版：有行，包没下发
    'both_alter_hei': [(9007, 0, 90070)],  # 改造+黑化：黑化必须压过改造
}
BANKS = {1001, 9001, 9003, 1006}     # 盘上真有主包的 cv；其余都没下发
# 让 ship_stem 能把 `solo_9_n` 归到 `solo`（同船回退那条路要有样本）
ROWS['solo'] = [(2002, 0, 20020)]
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

# ── 共用规则本体：`row_candidates()` 是语音层与台词层唯一的口径来源 ──────────
# （台词层原来自己写了一遍贪婪剥后缀，于是同一份错派在两个产物里各存一份，§85）
print()
RC = [
    ('黑化名不产生任何回退候选', 'hei2_hei', ['hei2_hei']),
    ('黑化+画法后缀只回到黑化那一层', 'hei3_hei_n', ['hei3_hei_n', 'hei3_hei']),
    ('改造名先自己、再本体（本体那层排在最后）',
     'gaizao_alter', ['gaizao_alter', 'gaizao']),
    ('改造+画法后缀逐层剥，本体排在最末',
     'tongti_alter_n', ['tongti_alter_n', 'tongti_alter', 'tongti']),
    ('改造+黑化：黑化压过改造，不给回退候选', 'both_alter_hei', ['both_alter_hei']),
]
rc_fail = 0
for desc, name, want in RC:
    got = E.row_candidates(name)
    ok = got == want
    rc_fail += 0 if ok else 1
    print('%s %-40s %-18s 期望 %-42s 实得 %s' % ('✓' if ok else '✗', desc, name, want, got))
fails += rc_fail

# ── 台词钥匙 = 表主键，**不能**由「语音包号 × 10 + 包内档位」反算 ──────────────
# 2026-10-02 真实案例：埃塞克斯皮肤10 的真行是 137090，而音频在 cv-10709 包里的档位是 10，
# 算术式 `10709*10+10` = 107100 正好是**约克城II**那一行 ⇒ 整列台词派给了别的船（用户从
# 「字幕比语音短」报出）。正向全库看不出来：那一行存在、有正文，join 判"成功"。
KEYROWS = {'aisaikesi': [(10709, 0, 107090)],
           'aisaikesi_10': [(10709, 10, 137090)],   # 包号来自 ship_group，不是 id//10
           'yuekechengII': [(10710, 0, 107100)]}
AK = [
    ('皮肤序号 ≥10 换号段 ⇒ 主键不是 cv*10+idx', 'aisaikesi_10', 137090),
    ('老批次恰好吻合（正向对照，规则不得把对的改坏）', 'aisaikesi', 107090),
    ('画法变体逐层剥，仍回到那张皮肤的真行', 'aisaikesi_10_n', 137090),
    ('查无此名必须返回 None，不许猜一个', 'aisaikesi_99', None),
]
ak_fail = 0
for desc, name, want in AK:
    got = E.row_id_for(name, KEYROWS)
    ok = got == want
    ak_fail += 0 if ok else 1
    print('%s %-42s %-16s 期望 %-9s 实得 %s' % ('✓' if ok else '✗', desc, name, want, got))
# 反向对照：算术式在这条案例上会得到什么（必须是"隔壁船"那一行，否则案例失效）
arith = 10709 * 10 + 10
ok = arith == 107100 and E.row_id_for('yuekechengII', KEYROWS) == 107100
ak_fail += 0 if ok else 1
print('%s %-42s %-16s 算术式 %d == 约克城II 行 %s' % ('✓' if ok else '✗',
      '对照：旧算术式确实撞进了隔壁船的行', 'aisaikesi_10', arith, ok))
fails += ak_fail

# ── 真表上的权威三元组（包号 = ship_group；档位 = id%10 或 10+批次序）──────────────
# 这条把"从猜改成推"钉住：数值全部取自 2026-10-02 的 `inputs/gamecfg/ship_skin_template.json`。
# ⚠️ 排序也必须测：算不出档位的剧情档（900xxx，tier=None）要排在**后面**，
#    否则 `row_id_for` 取 hit[0] 会取到故事行，等于把台词派给剧情实体。
REAL = [
    ('aisaikesi',     (10709, 0, 107090)),    # 老号段：档位 == id%10
    ('aisaikesi_g',   (10709, 9, 107099)),
    ('aisaikesi_10',  (10709, 10, 137090)),   # +3000 号段：包号仍是本体，档位 = 10+批次序 0
    ('qiye_9',        (10706, 10, 137060)),
    ('qiye_10',       (10706, 11, 137061)),   # 批次序 ≠ 皮肤序号：_9 先上线
    ('biaoqiang_10',  (20121, 11, 231211)),
    ('dujiaoshou_11', (20603, 12, 236032)),
    ('lafei_11',      (10117, 10, 131170)),   # 同组三行：_11=0 / _10=1 / _12=2
    ('lafei_10',      (10117, 11, 131171)),
    ('lafei_12',      (10117, 12, 131172)),
    ('z23_9',         (40123, 10, 431230)),
    ('z23_11',        (40123, 11, 431231)),
    ('z23_10',        (40123, 12, 431232)),
    ('nengdai_9',     (30221, 10, 332210)),
    ('guanghui_8',    (20703, 10, 237030)),
]
_rows = E.load_skin_rows()
real_fail = 0
for name, want in REAL:
    got = _rows.get(name, [None])[0]
    ok = got == want
    real_fail += 0 if ok else 1
    print('%s 真表 %-14s 期望 %-20s 实得 %s' % ('✓' if ok else '✗', name, want, got))
# 阴性对照：带剧情档同名的皮肤，第一行必须是能算出档位的真皮肤行
for name in ('aisaikesi', 'salatuojia_10', 'z23_10', 'lafei_10'):
    first = _rows[name][0]
    ok = first[1] is not None
    real_fail += 0 if ok else 1
    print('%s 剧情档不抢位 %-14s 第一行 %s' % ('✓' if ok else '✗', name, first))
fails += real_fail

# ── 画法变体不占语音档位，必须从所属皮肤继承 ────────────────────────────────
# 旧实现按「一个目录名一档」分配，`X_n`/`X_hx` 各吃掉一档：变体播到别的皮肤的台词，
# 又把真皮肤该拿的档挤掉（实测 15 个变体，`z23_10_hx/_n/_n_hx` 占走 11/12/13、
# `z23_11` 被推到 14）。
TIER = [
    ('变体不抢档：两张真皮肤各自命中，变体继承',
     {'es': {'cv': 1, 'idx': 0, 'src': 'row'},
      'es_2': {'cv': 1, 'idx': None, 'src': 'sibling'},
      'es_2_n': {'cv': 1, 'idx': None, 'src': 'sibling'},
      'es_3': {'cv': 1, 'idx': None, 'src': 'sibling'}},
     {1: ['touch_1', 'touch_1_2', 'touch_1_3']},
     {'es_2': 2, 'es_2_n': 2, 'es_3': 3}),
    ('包里有空档也不许分给变体（`_10` 只有一张皮肤拿）',
     {'ai': {'cv': 10709, 'idx': 0, 'src': 'row'},
      'ai_10': {'cv': 10709, 'idx': None, 'src': 'sibling'},
      'ai_10_hx': {'cv': 10709, 'idx': None, 'src': 'sibling'}},
     {10709: ['touch_1', 'touch_1_10', 'touch_1_11']},
     {'ai_10': 10, 'ai_10_hx': 10}),
]
tier_fail = 0
for desc, res, cs, want in TIER:
    E.assign_pending_idx(res, cs)
    bad = {k: (res[k]['idx'], res[k]['src']) for k, v in want.items() if res[k]['idx'] != v}
    ok = not bad
    tier_fail += 0 if ok else 1
    print('%s %-40s 期望 %s 实得 %s' % ('✓' if ok else '✗', desc, list(want.values()),
          {k: res[k]['idx'] for k in want}))
fails += tier_fail

# 台词层必须与语音层同源：直接查 build_skin_words 里不该再有第二份剥后缀逻辑
bsw = open(os.path.join(ROOT, 'scripts', 'build_skin_words.py'), encoding='utf-8').read()
leak = [ln.strip()[:70] for ln in bsw.splitlines()
        if 'VAR.sub' in ln and not ln.strip().startswith('#')]
print('\n%s 台词层没有第二份剥后缀实现（源码里 VAR.sub 出现 %d 处）: %s'
      % ('[OK]' if not leak else '[FAIL]', len(leak), leak or '无'))
fails += len(leak)

TOTAL = len(CASES) + 1 + len(RC) + 1 + len(AK) + 1 + len(REAL) + 4 + len(TIER)
print('\n%s 语音归属解析 %d/%d' % ('[PASS]' if not fails else '[FAIL]', TOTAL - fails, TOTAL))
sys.exit(1 if fails else 0)
