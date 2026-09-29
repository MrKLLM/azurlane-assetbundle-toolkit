# -*- coding: utf-8 -*-
""".diag 卫生检查：顶层不许留唯一副本代码。

AGENTS.md 收尾清单第 4 条早就写着「本次在 `.diag/` 新写的 .py，要么移进 `scripts/diag/` 入库，
要么删掉——`.diag/` 不留任何唯一副本代码」。但**这条规则一直只在被想起来时生效**：
2026-09-29 盘点时 `.diag/` 顶层堆了 67 个代码文件（62 个 .py），跨十几个会话攒出来的，
没有一个会话去执行那条。所以这里把它变成一个能跑、有退出码的东西。

用法:
  py -3 scripts/diag/check_diag_hygiene.py            # 检查（退出码即结论）
  py -3 scripts/diag/check_diag_hygiene.py --archive  # 打包归档 + 删散文件，并校验每份 md5 可回读

判什么：只看 `.diag/` **顶层**的代码文件（`.py/.js/.ps1/.sh/.bat`）。
`.diag/` 的子目录（截图、chrome profile、临时产物区）不在范围内 —— 那条规则针对的是"代码"，
不是"产物"。git 里已跟踪的同名文件也不算（`.diag` 本身在 .gitignore 里）。
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DIAG = os.path.join(ROOT, '.diag')
CODE_EXT = ('.py', '.js', '.ps1', '.sh', '.bat')


def loose_files():
    return [p for p in sorted(glob.glob(os.path.join(DIAG, '*')))
            if os.path.isfile(p) and os.path.splitext(p)[1].lower() in CODE_EXT]


def tracked_code():
    """仓库里已跟踪的代码文件（相对路径）。"""
    out = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True).stdout
    return [x for x in out.split() if os.path.splitext(x)[1].lower() in CODE_EXT]


def classify(paths, tracked):
    """把散文件分成三档：内容已在库 / 同名正本在库 / 独有。

    ⚠️ 内容档必须按**哈希**比，不能按文件名匹配 —— "复制一份改个名再跑"是最常见的重复来源，
    按名字比会把它误判成独有（本脚本第一版就错在这，被一个 `check_inputs.py` 的改名副本抓到）。
    """
    def norm(raw):
        return raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')   # 行尾不算内容差异

    by_hash = {}
    for t in tracked:
        tp = os.path.join(ROOT, t)
        if os.path.isfile(tp):
            try:
                by_hash.setdefault(hashlib.md5(norm(open(tp, 'rb').read())).hexdigest(), t)
            except OSError:
                pass
    names = {os.path.basename(t) for t in tracked}
    dup, twin, uniq = [], [], []
    for p in paths:
        b = os.path.basename(p)
        hit = by_hash.get(hashlib.md5(norm(open(p, 'rb').read())).hexdigest())
        (dup if hit else (twin if b in names else uniq)).append((p, hit))
    return dup, twin, uniq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--archive', action='store_true',
                    help='把独有文件打包进 .diag/cleanup/orphans_<date>.zip 并删散文件（逐份校验 md5 可回读）')
    a = ap.parse_args()
    files = loose_files()
    if not files:
        print('[PASS] .diag 顶层没有散落代码')
        return 0
    tracked = tracked_code()
    dup, twin, uniq = classify(files, tracked)
    print(f'.diag 顶层散落代码 {len(files)} 个：')
    print(f'  与已跟踪文件逐字节相同（可直接删）  : {len(dup)}')
    for p, t in dup:
        print(f'      {os.path.basename(p)}  ==  {t}')
    print(f'  在 scripts/ 下有同名正本（需人工比）: {len(twin)}')
    for p, _ in twin:
        print(f'      {os.path.basename(p)}')
    print(f'  独有（入库或删，规则不允许留着）    : {len(uniq)}')
    if not a.archive:
        print('\n[FAIL] 按 AGENTS.md 收尾清单第 4 条，这些必须入库或删除。'
              '\n  先看是什么:  逐个读文件首行 docstring'
              '\n  打包归档:    py -3 scripts/diag/check_diag_hygiene.py --archive')
        return 1
    clean = os.path.join(DIAG, 'cleanup')
    os.makedirs(clean, exist_ok=True)
    # ⚠️ 同一天再跑一次不能把上一份归档覆盖掉 —— 那是唯一副本，覆盖等于第二次清理把
    #    第一次清理的成果销毁了。已存在就往后缀 _2/_3 让位。
    base = f'orphans_{dt.date.today():%Y%m%d}'
    zp = os.path.join(clean, base + '.zip')
    n = 1
    while os.path.exists(zp):
        n += 1
        zp = os.path.join(clean, f'{base}_{n}.zip')
    man = []
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for p, _ in uniq + twin:
            raw = open(p, 'rb').read()
            z.write(p, os.path.basename(p))
            man.append({'name': os.path.basename(p), 'bytes': len(raw),
                        'md5': hashlib.md5(raw).hexdigest()})
    with zipfile.ZipFile(zp) as z:                       # 回读校验，别只信写进去了
        bad = [m['name'] for m in man if hashlib.md5(z.read(m['name'])).hexdigest() != m['md5']]
    if bad:
        print(f'[FAIL] zip 回读校验失败 {bad} —— 不删任何散文件')
        return 1
    json.dump({'note': '.diag 顶层散落代码归档，unzip 回 .diag/ 即复原',
               'at': dt.datetime.now().strftime('%Y-%m-%d %H:%M'), 'files': man},
              open(zp[:-4] + '.manifest.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    for p, _ in uniq + twin:
        os.remove(p)
    for p, _ in dup:
        os.remove(p)                                     # 库里有一份，删了零损失
    print(f'[OK] 归档 {len(uniq) + len(twin)} 个独有/同名 → {zp}（md5 全部回读校验通过）；'
          f'另删 {len(dup)} 个与库内逐字节相同者')
    print(f'     .diag 顶层剩余散落代码 = {len(loose_files())}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
