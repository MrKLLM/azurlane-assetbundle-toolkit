# -*- coding: utf-8 -*-
"""静默降级闸门：把"游戏改了形状、我们只能猜"的那些点，从**悄悄降级**改成**停下来点名**。

背景（2026-10-03）：例行的"拉取 → 还原"其实早就是一条命令的事，真正需要人的地方是
**数据语义变了**的时候。麻烦在于这类变化**不报错**——比如语音号段哪天多出第三种偏移，
`load_skin_rows()` 会算不出档位，然后 `resolve()` 安安静静去借同船别人的包，
产出一堆"能播但播错"的皮肤（§86 那个字幕挂错船就是这么绿了一整天的）。

判据是**存量记账 + 新增即红**，不是"有没有"：
- 今天这四类都有非零存量（8 张借包、366 张表里查无行…），要求它们归零不现实，
  只会逼人给闸门开后门；
- 所以把**具体皮肤名**逐条记进 `ledger/degradation.json`（不是记计数——记计数会把
  "3 条旧的换成 3 条新的"这种最该报警的情况吞掉）；
- 基线里**没有的新条目** = 游戏改了形状 = 非零退出，并点名是哪几条。

用法:
  py -3 scripts/diag/check_degradation.py              # 现算现比（只读）
  py -3 scripts/diag/check_degradation.py --write      # 确认这些是正常存量后，收紧/更新基线
退出码: 0 无新增 / 1 有新增（或基线缺这一类）/ 2 算不出来
"""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import extract_cv_voice as E      # noqa: E402

BASELINE = os.path.join(ROOT, 'ledger', 'degradation.json')
KIND_CN = {
    'unknown-offset': '号段偏移不认识（档位推不出来）',
    'borrow-pack':    '借了同船别人的语音包',
    'tier-allocated': '档位是按"哪个空着填哪个"分配的（猜）',
    'no-row':         '磁盘有这份皮肤、权威表里查无对应行',
}


def current():
    rows = E.load_skin_rows()
    keys = E.gallery_keys()
    res, miss = E.resolve(keys, rows, E.banks_on_disk())
    # 与 extract_cv_voice.run() 同序：先让画法变体继承、再看还剩谁在猜
    cue_sets = {}
    for cv in {e['cv'] for e in res.values()}:
        d = os.path.join(ROOT, 'Output', 'Audio', 'CV2', 'cv-%d' % cv)
        if os.path.isdir(d):
            cue_sets[cv] = sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith('.ogg'))
    E.assign_pending_idx(res, cue_sets)
    return E.degradation_report(res, miss, keys, rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='把当前清单写成基线（确认存量正常后才用）')
    ap.add_argument('--baseline', default=BASELINE, help='基线路径（红路径自测时指到临时副本）')
    a = ap.parse_args()
    try:
        cur = current()
    except Exception as ex:
        print('[ERROR] 算不出降级清单：%s' % str(ex)[:200])
        return 2
    if a.write:
        os.makedirs(os.path.dirname(a.baseline), exist_ok=True)
        blob = {'generated_by': 'scripts/diag/check_degradation.py --write',
                'note': '存量记账：这些是"已知且在等人判断"的降级点。新增条目 = 闸门判红。',
                'kinds': cur}
        open(a.baseline, 'w', encoding='utf-8').write(
            json.dumps(blob, ensure_ascii=False, indent=1, sort_keys=True) + '\n')
        print('已写基线 %s：%s' % (os.path.relpath(a.baseline, ROOT),
              {k: len(v) for k, v in sorted(cur.items())}))
        return 0
    if not os.path.isfile(a.baseline):
        print('[FAIL] 没有基线 %s —— 先人工确认存量后跑 --write 建账' % os.path.relpath(a.baseline, ROOT))
        print('       当前清单：%s' % {k: len(v) for k, v in sorted(cur.items())})
        return 1
    base = (json.load(open(a.baseline, encoding='utf-8')) or {}).get('kinds') or {}
    bad = 0
    print('降级台账比对（基线 %s）' % ' / '.join('%s=%d' % (k, len(base.get(k) or [])) for k in sorted(KIND_CN)))
    for kind, cn in KIND_CN.items():
        b, c = set(base.get(kind) or []), set(cur.get(kind) or [])
        new, gone = sorted(c - b), sorted(b - c)
        print('  %-14s %-34s 存量 %4d  新增 %3d  已消除 %3d' % (kind, cn, len(c), len(new), len(gone)))
        if new:
            bad += len(new)
            print('      ⚠️ 新增（游戏改了形状或本地缺数据，需要人判断，不许自动猜着填）:')
            for x in new[:12]:
                print('         - %s' % x)
            if len(new) > 12:
                print('         …还有 %d 条' % (len(new) - 12))
        if gone:
            print('      ✓ 消除 %d 条（可以 `--write` 收紧基线，否则它们下次"复活"就不会再报）' % len(gone))
    if bad:
        print('\n[FAIL] %d 处新增降级：见上。修法是补权威判据，**不是**把它们写进基线。' % bad)
        return 1
    print('\n[OK] 无新增降级：例行拉取-还原可以无人值守')
    return 0


if __name__ == '__main__':
    sys.exit(main())
