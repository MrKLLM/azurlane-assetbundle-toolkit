#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""publish_bg_char_flags.py — 发布「这张背景图里有没有角色」的标注结论。

产 `inputs/gamecfg/bg_char_flags.json`（台账 `inputs/gamecfg/MANIFEST.json`），
供 `scripts/build_bg_meta.py` 接成 `has_char` 字段 ⇒ 背景页的默认视图靠它筛。

为什么要有这份文件而不是用规则：「名字含 `_cg`」这条规则精确率 86% / 召回率 79%
（分层抽 48 张目视），当预筛够用、当**默认视图**不够 —— 漏掉的会被静默藏掉。
标注全文见 docs/WORKFLOWS.md WF-33，判据与踩坑见 docs/TROUBLESHOOTING.md §118/§119。

数据链（**人工标注是不可再生劳动，正本必须在 git 里**）：
  .diag/bglabels/labels_part*.json  5×5 拼板逐格标注（1=有 / 0=无 / 2=不确定）—— 临时区，可丢
  annotations/bg_char_adjudications.json  17 个 `2` 的全分辨率裁定 —— **入库正本**
        ↓ 本脚本合并（裁定覆盖 `2`，合并结果再落一份入库正本，防 .diag 清盘后无从重跑）
  annotations/bg_char_labels.json   1,305 张场景背景的完整结论 —— **入库正本**
        ↓
  inputs/gamecfg/bg_char_flags.json 发布件（gitignore，按台账 sha256 校验）

用法:
  py -3 scripts/publish_bg_char_flags.py            # 从拼板标注 + 裁定合并，写两份
  py -3 scripts/publish_bg_char_flags.py --from-annotations  # .diag 已清盘：只用入库正本重发
  py -3 scripts/publish_bg_char_flags.py --check    # 只跑闸门，不写文件
退出码：闸门红即 1（红时不写文件）。
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHEETS = os.path.join(ROOT, '.diag', 'bglabels')
ADJ = os.path.join(ROOT, 'annotations', 'bg_char_adjudications.json')
MERGED = os.path.join(ROOT, 'annotations', 'bg_char_labels.json')
META = os.path.join(ROOT, 'Output', 'gallery_v2', 'bg_meta.json')
OUT = os.path.join(ROOT, 'inputs', 'gamecfg', 'bg_char_flags.json')


def read_json(p):
    return json.load(open(p, encoding='utf-8'))


def from_sheets():
    """拼板逐格标注 + 裁定覆盖 `2` -> {`<dir>/<名>`: 0|1}。"""
    parts = sorted(glob.glob(os.path.join(SHEETS, 'labels_part*.json')))
    if not parts:
        return None
    man = read_json(os.path.join(SHEETS, 'manifest.json'))
    cells = {}
    for p in parts:
        for k, v in read_json(p).items():
            cells[man[str(k)]] = int(v)
    unresolved = sorted(k for k, v in cells.items() if v == 2)
    adj = read_json(ADJ)['cells']
    # 裁定表与标注表必须**互相闭合**：漏裁定 => 还有 2；多裁定 => 裁定的是别的批次
    if set(unresolved) != set(adj):
        print('[FAIL] 裁定表与标注里的 `2` 不吻合')
        print('  标注里判 2 的: %d，裁定表覆盖: %d' % (len(unresolved), len(adj)))
        for k in sorted(set(unresolved) - set(adj)):
            print('  [缺裁定] %s' % k)
        for k in sorted(set(adj) - set(unresolved)):
            print('  [裁定表多余（那格已不是 2）] %s = %s' % (k, cells.get(k)))
        return None
    for k, rec in adj.items():
        cells[k] = int(rec['v'])
    return cells


def gate(cells):
    """发布前闸门：值域穷尽、覆盖 = 索引里的 scene 全集、且键都能在盘上找到。"""
    scene = {i['key'] for i in read_json(META)['items'] if i['group'] == 'scene'}
    checks = [
        ('值域只有 0/1（裁定未收敛就不许发布）', set(cells.values()) <= {0, 1}),
        ('索引里的每张场景背景都有结论（默认视图不许出现"没判过"的场景图）',
         scene <= set(cells)),
        ('标注里没有索引已不存在的键（类目重排/改名要能看见）', set(cells) <= scene),
        ('裁定表每条都带 why（无凭据的裁定不可复核）',
         all((read_json(ADJ)['cells'][k].get('why') or '').strip() for k in read_json(ADJ)['cells'])),
    ]
    ok = True
    for desc, passed in checks:
        print('%s %s' % ('OK ' if passed else 'FAIL', desc))
        ok &= passed
    n_has = sum(cells.values())
    print('  覆盖 %d 张：有角色 %d / 无角色 %d（%.1f%% 有角色）'
          % (len(cells), n_has, len(cells) - n_has, 100 * n_has / max(1, len(cells))))
    return ok


def update_manifest(cells):
    """发布后同步台账的 bytes/sha/rows/coverage。

    这个文件由脚本生成、本体 gitignore；台账是唯一入库的回指。不更新台账，
    `check_inputs.py gamecfg` 必然报 drift —— 而漂移本身是正确信号，
    不能靠"反正没人看"把它留成常态。"""
    mp = os.path.join(ROOT, 'inputs', 'gamecfg', 'MANIFEST.json')
    if not os.path.isfile(mp):
        return
    try:
        with open(mp, encoding='utf-8') as f:
            led = json.load(f)
        raw = open(OUT, 'rb').read()
        sha = hashlib.sha256(raw).hexdigest()
        n_has = sum(cells.values())
        n = len(cells)
        for rec in led.get('files') or []:
            if rec.get('path') != 'bg_char_flags.json':
                continue
            rec['bytes'] = len(raw)
            rec['sha256'] = sha
            rec['rows'] = n
            rec['coverage'] = ('%d/%d 场景背景全覆盖（有角色 %d / 无角色 %d）；'
                               '登录与其他类目未标注，消费方不得把它们当「无角色」隐藏'
                               % (n, n, n_has, n - n_has))
            break
        led.setdefault('provenance', {})['landed_at'] = datetime.date.today().isoformat()
        tmp = mp + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(led, f, ensure_ascii=False, indent=1)
        os.replace(tmp, mp)
        print('[WRITE] %s（台账同步 bytes/sha）' % os.path.relpath(mp, ROOT))
    except (OSError, ValueError) as e:
        print('[WARN] 台账同步失败：%s（发布件已写，需手工修 MANIFEST）' % e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from-annotations', action='store_true',
                    help='.diag 拼板已清盘时，只用入库的合并正本重发')
    ap.add_argument('--check', action='store_true', help='只跑闸门，不写文件')
    a = ap.parse_args()

    if a.from_annotations:
        cells = {k: int(v) for k, v in read_json(MERGED)['labels'].items()}
        print('从入库正本 %s 读 %d 条' % (os.path.relpath(MERGED, ROOT), len(cells)))
    else:
        cells = from_sheets()
        if cells is None:
            return 1
        print('拼板标注 + 裁定合并 %d 条' % len(cells))
        if not a.check:
            doc = {'schema': 1,
                   'note': '场景背景「画面里有没有角色」的人工视觉标注合并正本（拼板逐格标注 + '
                           '`2` 的全分辨率裁定）。这是**不可再生劳动的正本**，必须入库；'
                           '.diag/bglabels 只是可重生成的临时拼板。',
                   'adjudications_from': 'annotations/bg_char_adjudications.json',
                   'updated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                   'labels': dict(sorted(cells.items()))}
            os.makedirs(os.path.dirname(MERGED), exist_ok=True)
            with open(MERGED, 'w', encoding='utf-8') as f:
                json.dump(doc, f, ensure_ascii=False, indent=0)
            print('[WRITE] %s' % os.path.relpath(MERGED, ROOT))
    if not gate(cells):
        print('\n闸门：红 —— 不写发布件')
        return 1
    if a.check:
        print('\n闸门：绿（--check 未写文件）')
        return 0
    n_has = sum(cells.values())
    doc = {'schema': 1,
           'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
           'scale': {'1': '画面里有角色形象（含只有局部身体的分镜特写）',
                     '0': '画面里没有角色（纯场景/器物/底纹）'},
           'unlabeled': '只有场景背景（`group=scene`）判过；登录/其他类目未标注，'
                        '消费方不得把它们当"无角色"隐藏',
           'note': '5×5 拼板逐格目视标注（1,305 格全覆盖）+ 17 个「不确定」格的全分辨率裁定；'
                   '与 `_cg` 文件名先验做过交叉核对：先验=1 而标注≠1 有 24 格（22 格复核确认无人，'
                   '2 格为漏判），先验=0 而标注=1 有 164 格 ⇒ 文件名规则的漏报由标注补回',
           'counts': {'has': n_has, 'none': len(cells) - n_has},
           'labels': dict(sorted(cells.items()))}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print('[WRITE] %s（%d 条 / %.1f KB）'
          % (os.path.relpath(OUT, ROOT), len(cells), os.path.getsize(OUT) / 1024))
    update_manifest(cells)
    return 0


if __name__ == '__main__':
    sys.exit(main())
