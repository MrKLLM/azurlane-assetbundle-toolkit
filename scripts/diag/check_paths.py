# -*- coding: utf-8 -*-
"""漂移探测器：还有没有脚本把 `D:\\Azur Lane Assets` / `C:\\Users\\xxx` 写死在源码里。

2026-10-01 把 13 阶段调用链上 9 个脚本改成走 `scripts/paths.py` 之后，必须有东西**拦住下一个人**
（包括下一个会话里的我）：这类回归不会报错，只会在新机器上第一次跑的时候炸，
或者更糟——静默把资产写到错误的目录。

    py -3 scripts/diag/check_paths.py            # 退出码即结论
    py -3 scripts/diag/check_paths.py --verbose  # 列出每条命中

允许出现绝对路径的只有两处：`paths.py` 自己的候选清单、以及明确标了 legacy 的归档脚本。
"""
import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.dirname(HERE)                       # scripts/
ROOT = os.path.dirname(S)

DRIVE = re.compile(r'''["'][A-Za-z]:[\\/](?:Users|Program Files|Azur Lane Assets|azur)''')
# 允许：路径出口本身（它的职责就是列已知安装位置）
ALLOW = {'paths.py'}
# 归档/一次性脚本：不在调用链上，改它们等于扩大战线；新增条目要写明理由
LEGACY = set()

sys.path.insert(0, S)
# 调用链上这些**必须**已经走 paths —— 少一个就是漏改，直接判红
MUST_USE_PATHS = ['compose_paintings_v2.py', 'extract_spine_v2.py', 'reconstruct_live2d.py',
                  'extract_motions.py', 'fix_model3.py', 'extract_cv_voice.py',
                  'export_dependency_manifest.py', 'mumu_sync.py',
                  os.path.join('diag', 'run_cg_export.py'), 'update_pipeline.py']

# 分两档，是为了让这个闸门**现在就能绿**并且一直拦得住回归：
# 一次扫出 46 个文件全判红 = 闸门当天就被绕过（本项目对"永远红的检查"的态度见 §71）。
# 硬档 = 会被日常跑到的链路；软档 = 一次性诊断脚本（多数只是那一行 Chrome 路径），
# 只报数不判红，等谁去动那个脚本时顺手迁。
SOFT_DIRS = ('diag/',)
SOFT_FILES = {'export_assets.py', 'scan_assets.py', 'organize.py', 'probe_matching.py',
              'generate_audio_doc.py', 'gen_face_mapping.py', 'extract_paintingface.py',
              'export_painting_layout.py', 'export_cue_audio.py', 'extract_cpk.py',
              'extract_live2d_voice.py', 'scrape_wiki_fast.py', 'mumu_adb.py'}


def tier_of(rel):
    if rel.startswith(SOFT_DIRS) or rel.split('/')[-1] in SOFT_FILES:
        return 'soft'
    return 'hard'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--strict', action='store_true', help='软档也算判红（清完账之后把它设成默认）')
    a = ap.parse_args()
    bad, missing, soft_n = [], [], 0
    for dirpath, dirnames, files in os.walk(S):
        dirnames[:] = [d for d in dirnames if d not in ('__pycache__', '_archive')]
        for fn in files:
            if not fn.endswith('.py'):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), S).replace('\\', '/')
            base = rel.split('/')[-1]
            if base in ALLOW or rel in LEGACY:
                continue
            try:
                txt = io.open(os.path.join(dirpath, fn), encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            hits = [(i + 1, l.strip()[:110]) for i, l in enumerate(txt.splitlines()) if DRIVE.search(l)]
            if not hits:
                continue
            if tier_of(rel) == 'soft' and not a.strict:
                soft_n += 1
                if a.verbose:
                    print(f'  （软档·待迁）{rel}:{hits[0][0]} {hits[0][1][:70]}')
            else:
                bad.append((rel, hits))
    for rel in MUST_USE_PATHS:
        p = os.path.join(S, rel.replace('/', os.sep))
        txt = io.open(p, encoding='utf-8', errors='replace').read() if os.path.isfile(p) else ''
        if 'import paths as P' not in txt:
            missing.append(rel)

    if a.verbose or bad or missing:
        for rel, hits in bad:
            print(f'  写死了绝对路径: {rel}')
            for n, l in hits[:4]:
                print(f'      {n}: {l}')
        for rel in missing:
            print(f'  调用链上的脚本没走 paths: {rel}')
    n = len(bad) + len(missing)
    print(f'{"[FAIL] " if n else "[PASS] "}调用链上绝对路径 {len(bad)} 个文件'
          f'，未接 paths 的链路脚本 {len(missing)} 个'
          f'；另有一次性脚本 {soft_n} 个待迁（--strict 把它们也算红）')
    return 1 if n else 0



if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
