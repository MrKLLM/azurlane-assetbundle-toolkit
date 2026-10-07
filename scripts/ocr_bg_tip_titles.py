#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布「图内烤字标题」表：从 `Output/Raw/**/*_tip.png` 这类**横幅图**里 OCR 出中文活动名。

为什么需要第二条命名源：`bg_worldcruise_<N>_tip` 这一族在配置表里**零引用**（精确引用面拿不到它们），
但游戏把活动名**直接烤进了图里**（固定版式：`AZUR LANE-OUTFIT` / `获得限定换装` /
**<活动标题>** / `特许巡游奖励达到30级` / `完成任务累计` / `可获取` / `「<舰名>·META」` / `在内的丰富奖励`）。

⚠️ **引号匹配不通用**：只有 9/13/14 的装饰引号被 OCR 认出来，10/11/12 的引号是美术字形，
识别结果里根本没有 `「`。⇒ 判据换成**模板位**：把版式里的固定锚点段与舰名段（含 `META`）剔掉，
剩下的那条中文段就是标题。

⚠️ **OCR 单路不可信，必须配第二条路**：实测 `bg_worldcruise_11_tip` 的标题 OCR 成 `微的海风e`
（丢了「醺」+ 尾部噪声），目视 3× 放大才读出「微醺的海风」。⇒ 本脚本把**目视核对后的定稿**放在
`CONFIRMED` 里（照 48 号发布器的 `CONFIRMED + via` 形状），并断言它与 OCR 候选**字符重合度 ≥0.6**——
两边谁漂了都会红，而不是各说各话。

⚠️ **舰名不发布**：6 张图里 OCR 读到的奖励舰名有 3 个（树城 / 克劳迪亚 / 阿尔伯缇娜 / 诺菈 一类）
在 `Output/ship_meta.json` 的 `cn` 集合里查不到，无法判定是 OCR 读错还是译名口径不同
⇒ 只把原始段落在 `segs` 里留作证据，**不产出 `ship` 字段**（宁可少一个字段，不挂一个可能对不上号的名字）。

产物：`inputs/gamecfg/bg_tip_titles.json`，键 = 图名（不含扩展名），值含
`cn / via / ocr_raw / ocr_conf / segs`。不入库（`.gitignore: inputs/*/*.json`），台账 `MANIFEST.json` 入库。

用法:
  py -3 scripts/ocr_bg_tip_titles.py            # 跑 OCR + 断言 + 写盘
  py -3 scripts/ocr_bg_tip_titles.py --check    # 只跑，不写文件
退出码：任一断言不过即 1（红时不写文件）。
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'Output', 'Raw')
DST = os.path.join(ROOT, 'inputs', 'gamecfg')
OUT_FN = 'bg_tip_titles.json'

# 版式里的固定锚点（剔掉它们，剩下的中文段才是标题）。OCR 会把 OUTFIT 读成 OUTEIT，两种都挡。
ANCHORS = re.compile(r'(AZUR|OUTFIT|OUTEIT|获得限定换装|特许巡游奖励|完成任务累计|可获取|在内的)')
SHIP = re.compile(r'META', re.I)
CJK = re.compile(r'[一-鿿★]')
MIN_CONF = 0.85          # 低于此的段不参与判标题
MIN_OVERLAP = 0.6        # 定稿与 OCR 候选的字符重合度地板

CONFIRMED = {
    'bg_worldcruise_9_tip':  {'cn': '放学后的观察作业', 'via': '目视 3× 放大读图 + RapidOCR 双路径一致（2026-10-07）'},
    'bg_worldcruise_10_tip': {'cn': '击球手★全垒打',   'via': '目视 3× 放大读图 + RapidOCR 一致（引号未被识别，走模板位）'},
    'bg_worldcruise_11_tip': {'cn': '微醺的海风',       'via': '目视 3× 放大读图；RapidOCR 读成「微的海风e」丢了「醺」⇒ 以目视为准，重合度判据仍过'},
    'bg_worldcruise_12_tip': {'cn': '甜蜜的意外序曲',   'via': '目视 3× 放大读图 + RapidOCR 一致（引号未被识别，走模板位）'},
    'bg_worldcruise_13_tip': {'cn': '放学后的补习时间', 'via': '目视 3× 放大读图 + RapidOCR 双路径一致（2026-10-07）'},
    'bg_worldcruise_14_tip': {'cn': '漫游微缩世界',     'via': '目视 3× 放大读图 + RapidOCR 双路径一致（2026-10-07）'},
}

ROLE = ('背景横幅图（Output/Raw/**/*_tip.png）里烤进像素的中文活动名 —— 图内文字证据，'
        '与"配置表字段整值引用"是两条独立命名源，页面必须分档显示，不许混')
CONSUMERS = ['scripts/build_bg_meta.py']


def tip_images():
    out = {}
    if not os.path.isdir(RAW):
        return out
    for d in sorted(os.listdir(RAW)):
        p = os.path.join(RAW, d)
        if not os.path.isdir(p):
            continue
        for f in sorted(os.listdir(p)):
            if f.endswith('.png') and '_tip' in f:
                out[f[:-4]] = os.path.join(p, f)
    return out


def overlap(a, b):
    """定稿与 OCR 结果的字符重合度：以定稿字符集为分母（OCR 丢字要能看出来）。"""
    if not a:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa)


def ocr_all(paths):
    from rapidocr_onnxruntime import RapidOCR
    eng = RapidOCR()
    res = {}
    for name, fp in sorted(paths.items()):
        raw, _ = eng(fp)
        # RapidOCR 的每条是 [box, 文本, 置信]，顺序写错就会拿文本去 float()
        segs = [(txt, float(conf)) for _box, txt, conf in (raw or [])]
        cands = [s for s in segs
                 if not ANCHORS.search(s[0]) and not SHIP.search(s[0])
                 and s[1] >= MIN_CONF and len(CJK.findall(s[0])) >= 3]
        best = max(cands, key=lambda s: len(CJK.findall(s[0]))) if cands else None
        res[name] = {'segs': [[t, round(c, 3)] for t, c in segs],
                     'cands': [[t, round(c, 3)] for t, c in cands],
                     'best': best[0] if best else '',
                     'best_conf': round(best[1], 3) if best else 0.0}
    return res


def build():
    paths = tip_images()
    missing = sorted(set(CONFIRMED) - set(paths))
    extra = sorted(set(paths) - set(CONFIRMED))
    res = ocr_all(paths) if paths else {}
    out = {}
    for name, rec in res.items():
        conf = CONFIRMED.get(name)
        if not conf:
            continue
        out[name] = {'cn': conf['cn'], 'via': conf['via'],
                     'ocr_raw': rec['best'], 'ocr_conf': rec['best_conf'],
                     'overlap': round(overlap(conf['cn'], rec['best']), 3),
                     'segs': rec['segs'], 'img': os.path.relpath(paths[name], RAW).replace('\\', '/')}
    return out, res, missing, extra, paths


def selfcheck(out, res, missing, extra, paths):
    checks = [
        ('每张 *_tip 图恰好产出一个标题（不多不少，缺图/多图都判红）',
         not missing and not extra and len(out) == len(paths)),
        ('每条定稿都与 OCR 候选高度重合（≥%.1f，两边谁漂了都会红）' % MIN_OVERLAP,
         all(v['overlap'] >= MIN_OVERLAP for v in out.values())),
        ('每条都带 via（说明这条名字是怎么定的）', all(v['via'] for v in out.values())),
        ('OCR 每条都真的找到了候选（模板位规则没落空）',
         all(r['best'] for r in res.values())),
        ('标题里不含版式锚点词（锚点没被误当标题）',
         all(not ANCHORS.search(v['cn']) for v in out.values())),
    ]
    return checks, missing, extra


def merge_ledger(entry):
    path = os.path.join(DST, 'MANIFEST.json')
    led = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else \
        {'schema_version': 1, 'purpose': '权威外部输入', 'provenance': {'regenerate_via': []}, 'files': []}
    prov = led.setdefault('provenance', {})
    prov.setdefault('game_version_local_assets', '9.7.385')
    prov['landed_at'] = datetime.date.today().isoformat()
    rg = prov.setdefault('regenerate_via', [])
    if 'scripts/ocr_bg_tip_titles.py' not in rg:
        rg.append('scripts/ocr_bg_tip_titles.py')
    files = [f for f in led.get('files', []) if f.get('path') != OUT_FN]
    files.append(entry)
    files.sort(key=lambda f: f['path'])
    led['files'] = files
    return led


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只跑 OCR 与断言，不写文件')
    a = ap.parse_args()
    if not os.path.isdir(RAW):
        print('[FAIL] %s 不在盘上' % RAW)
        return 2

    out, res, missing, extra, paths = build()
    for name in sorted(res):
        r = res[name]
        c = CONFIRMED.get(name, {})
        print('%-24s OCR=%-14r(%.3f)  定稿=%-10s  重合=%.2f'
              % (name, r['best'], r['best_conf'], c.get('cn', '—'),
                 overlap(c.get('cn', ''), r['best'])))
    if missing:
        print('  ! 字典里有、盘上没有的图:', missing)
    if extra:
        print('  ! 盘上有、字典里没核对的图:', extra)
    checks, missing, extra = selfcheck(out, res, missing, extra, paths)
    ok = True
    for desc, passed in checks:
        print('%s %s' % ('✓' if passed else '✗', desc))
        ok &= passed
    if not ok:
        print('\n闸门：红 —— 断言未全过，不写文件')
        return 1
    if a.check:
        print('\n闸门：绿（--check 未写文件）')
        return 0

    body = json.dumps({'schema': 1,
                       'generated_at': datetime.date.today().isoformat(),
                       'method': 'rapidocr_onnxruntime 模板位提取 + 3× 放大目视定稿（双路径）',
                       'titles': {k: out[k] for k in sorted(out)}},
                      ensure_ascii=False, indent=1, sort_keys=True)
    blob = body.encode('utf-8')
    os.makedirs(DST, exist_ok=True)
    with open(os.path.join(DST, OUT_FN), 'wb') as f:      # 二进制写：防 CRLF 改哈希（§103）
        f.write(blob)
    entry = {'path': OUT_FN, 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest(),
             'rows': len(out), 'role': ROLE, 'consumers': CONSUMERS,
             'source': 'Output/Raw/**/*_tip.png 像素（rapidocr_onnxruntime）+ 目视核对',
             'note': '舰名段不发布：6 条里 3 条在 ship_meta 的 cn 集合查不到，无法判读错还是译名口径'}
    led = merge_ledger(entry)
    with open(os.path.join(DST, 'MANIFEST.json'), 'w', encoding='utf-8') as f:
        json.dump(led, f, ensure_ascii=False, indent=1)
    print('\n[WRITE] inputs/gamecfg/%s（%d 条）+ 台账已更新' % (OUT_FN, len(out)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
