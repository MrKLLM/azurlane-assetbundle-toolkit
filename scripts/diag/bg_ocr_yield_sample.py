# -*- coding: utf-8 -*-
"""bg_ocr_yield_sample.py — 估算「把 OCR 铺到其余无名背景图上还能捞到多少标题」的**抽样试产**。

为什么先抽样再全量：`none` 档 1,190 张里，场景背景大多**不含文字**，而 `helpbg`/`commonbg`
这类界面底图含的是**界面文案**（按钮、说明、数字）而不是"这张图叫什么"。
全量跑约 30 分钟，先花 1 分钟量出三档比例，再决定值不值得跑。

分层：按类目比例抽，但每个类目**至少 2 张**（小类目恰恰是最想知道答案的）。
随机种子固定 ⇒ 同一份清单可复跑，改判据时能做对照。

分类口径（每条都打印理由，交人判，不由脚本自己定名）：
  no_text     —— 整张图没有中文段
  ui_text     —— 有中文，但命中界面套话词表（点击/前往/奖励/等级/完成……），不像名字
  title_like  —— 有中文且短（2~14 字）、不含界面套话；带 `「」` 的优先

用法:
  py -3 scripts/diag/bg_ocr_yield_sample.py                # 抽 40 张
  py -3 scripts/diag/bg_ocr_yield_sample.py --n 60 --seed 7
产出: `.diag/ocr/yield_sample.json`（逐张段落下）+ `.diag/ocr/yield_sample.txt`（人读汇总）
退出码：0 跑完即 0（这是**估算工具**，结论交人判，不当闸门）。
"""
import argparse
import collections
import json
import os
import random
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
META = os.path.join(ROOT, 'Output', 'gallery_v2', 'bg_meta.json')
RAW = os.path.join(ROOT, 'Output', 'Raw')
OUT_DIR = os.path.join(ROOT, '.diag', 'ocr')
CJK = re.compile(r'[一-鿿]')
# 界面套话：出现这些基本说明是"屏幕上的话"而不是"这张图的名字"
UI_WORDS = re.compile(r'(点击|前往|查看|确定|取消|返回|领取|解锁|购买|使用| equip|升级|等级|经验|'
                      r'完成任务|奖励|进度|条件|时间|剩余|每日|累计|达到|可获取|在内|限定|活动结束)')
QUOTE = re.compile(r'[「『【\[]|[]】』」]')


def classify(segs):
    """返回 (verdict, best, reason)。best = 最像标题的那一段。"""
    cn = [(t, c) for t, c in segs if CJK.search(t)]
    if not cn:
        return 'no_text', '', '整图无中文段'
    cand = [(t, c) for t, c in cn if not UI_WORDS.search(t)]
    if not cand:
        return 'ui_text', '', '全部中文段都命中界面套话词表'
    # 打分：带引号的优先，其次长度接近标题（4~12 字），置信度做微调
    def score(tc):
        t, c = tc
        s = 0.0
        if QUOTE.search(t):
            s += 3.0
        n = len(CJK.findall(t))
        s += 2.0 if 2 <= n <= 12 else 0.5
        s += c
        return s
    best = max(cand, key=score)
    v = 'title_like' if score(best) >= 4.0 else 'ui_text'
    return v, best[0], 'score=%.1f 引号=%s 中文字数=%d 置信=%.3f' % (
        score(best), bool(QUOTE.search(best[0])), len(CJK.findall(best[0])), best[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=40)
    ap.add_argument('--seed', type=int, default=20261007)
    a = ap.parse_args()
    if not os.path.isfile(META):
        print('[FAIL] 缺 bg_meta.json，先跑 scripts/build_bg_meta.py')
        return 2
    items = json.load(open(META, encoding='utf-8'))['items']
    none_items = [i for i in items if i['tier'] == 'none']
    by_dir = collections.defaultdict(list)
    for i in none_items:
        by_dir[i['dir']].append(i)

    rng = random.Random(a.seed)
    total = len(none_items)
    picked, quota = [], {}
    for d, lst in sorted(by_dir.items()):
        k = max(2, round(a.n * len(lst) / total))
        k = min(k, len(lst))
        quota[d] = k
        picked += rng.sample(lst, k)
    print('none 档 %d 张 / 分层配额 %s / 实际抽 %d 张（seed=%d）'
          % (total, quota, len(picked), a.seed))

    from rapidocr_onnxruntime import RapidOCR
    eng = RapidOCR()
    rows = []
    t0 = time.time()
    for i, it in enumerate(picked, 1):
        fp = os.path.join(RAW, it['dir'], it['name'] + '.png')
        try:
            raw, _ = eng(fp)
            segs = [(txt, round(float(cf), 3)) for _b, txt, cf in (raw or [])]
        except Exception as e:
            segs = []
            rows.append({'key': it['key'], 'verdict': 'err', 'best': '', 'reason': str(e)[:80], 'segs': []})
            continue
        v, best, reason = classify(segs)
        rows.append({'key': it['key'], 'dir': it['dir'], 'w': it['w'], 'h': it['h'],
                     'verdict': v, 'best': best, 'reason': reason,
                     'segs': segs[:14], 'n_segs': len(segs)})
        if i % 10 == 0 or i == len(picked):
            print('  %d/%d (%.0fs)' % (i, len(picked), time.time() - t0), flush=True)

    per = collections.defaultdict(collections.Counter)
    for r in rows:
        per[r['dir']][r['verdict']] += 1
    agg = collections.Counter(r['verdict'] for r in rows)
    el = time.time() - t0

    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump({'n': len(rows), 'seed': a.seed, 'elapsed_s': round(el, 1),
               'quota': quota, 'agg': dict(agg),
               'per_dir': {k: dict(v) for k, v in per.items()},
               'rows': rows},
              open(os.path.join(OUT_DIR, 'yield_sample.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    with open(os.path.join(OUT_DIR, 'yield_sample.txt'), 'w', encoding='utf-8') as fh:
        fh.write('none 档 %d 张 / 抽样 %d 张 / seed=%d / 耗时 %.0fs（外推全量约 %.0f 分钟）\n\n'
                 % (total, len(rows), a.seed, el, el / max(1, len(rows)) * total / 60))
        fh.write('汇总: %s\n\n' % dict(agg))
        fh.write('按类目:\n')
        for d in sorted(per):
            fh.write('  %-13s %s\n' % (d, dict(per[d])))
        fh.write('\n逐张（title_like 的候选都列出来，交人判这算不算名字）:\n')
        for r in sorted(rows, key=lambda x: (x['verdict'] != 'title_like', x['key'])):
            fh.write('[%-10s] %-34s %s\n' % (r['verdict'], r['key'], r['reason']))
            if r['verdict'] == 'title_like':
                fh.write('             候选: %r\n' % r['best'])
                fh.write('             全部段落: %s\n' % [t for t, _ in r['segs']][:8])
    print('\n汇总: %s' % dict(agg))
    print('按类目:')
    for d in sorted(per):
        print('  %-13s %s' % (d, dict(per[d])))
    print('外推：全量 %d 张约 %.0f 分钟' % (total, el / max(1, len(rows)) * total / 60))
    print('[报告] .diag/ocr/yield_sample.txt')
    return 0


if __name__ == '__main__':
    sys.exit(main())
