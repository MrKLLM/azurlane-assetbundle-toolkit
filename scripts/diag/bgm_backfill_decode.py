# -*- coding: utf-8 -*-
"""补导未解码的 BGM 源包：cue/*.b → wav（vgmstream，ACB 需改名后缀）→ staging 目录。

背景：§112 记录 cue/ 有 561 个 bgm-*.b，首轮导出只得到 536 首 —— 25 个包从未解码
（含 bgm-nier-az-story），其中 18+ 首被 voice_bgm 等配置表引用（2026-10-17 反向对账）。
本工具只负责 .b → wav，转码（wav → FLAC + 台账）继续走 transcode_bgm.py。

用法:
  py -3 scripts/diag/bgm_backfill_decode.py                # 全部缺的 25 个
  py -3 scripts/diag/bgm_backfill_decode.py --only a,b,c   # 指定 slug（不带 bgm- 前缀也行）
  py -3 scripts/diag/bgm_backfill_decode.py --limit 3      # 样本模式
  py -3 scripts/diag/bgm_backfill_decode.py --check        # 只报告缺口，不落盘
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import paths as P  # noqa: E402

CUE = os.path.join(P.FILES, 'AssetBundles', 'cue')
STAGING = os.path.join(P.ROOT, '.diag', 'bgm_backfill_wav')
OUT_BGM = os.path.join(P.OUT, 'Audio', 'BGM')


def existing_bgm_slugs():
    return {os.path.splitext(f)[0] for f in os.listdir(OUT_BGM) if f.lower().endswith('.flac')}


def main():
    ap = argparse.ArgumentParser(description='补导未解码的 bgm-*.b → wav')
    ap.add_argument('--only', default='', help='逗号分隔的包名（可带 bgm- 前缀）')
    ap.add_argument('--limit', type=int, default=0, help='只处理前 N 个（样本模式）')
    ap.add_argument('--check', action='store_true', help='只报告缺口，不落盘')
    a = ap.parse_args()

    if not P.VGMSTREAM:
        print('[FAIL] 找不到 vgmstream-cli（环境变量 AL_VGMSTREAM / PATH / AppData）')
        return 2
    if not os.path.isdir(CUE):
        print(f'[FAIL] cue 目录不存在: {CUE}')
        return 2

    have = existing_bgm_slugs()
    cue_bgm = sorted(f for f in os.listdir(CUE) if f.startswith('bgm-') and f.endswith('.b'))
    missing = [os.path.splitext(f)[0] for f in cue_bgm
               if os.path.splitext(f)[0] not in have]
    print(f'cue/bgm-*.b 共 {len(cue_bgm)}，已导 flac {len(have)}，缺 {len(missing)}')

    if a.only:
        want = {x.strip().lower() for x in a.only.split(',') if x.strip()}
        want = {x if x.startswith('bgm-') else 'bgm-' + x for x in want}
        unknown = want - {os.path.splitext(f)[0] for f in cue_bgm}
        if unknown:
            print(f'[FAIL] 这些名字在 cue/ 里不存在（宁可不跑也不少跑一半）: {sorted(unknown)}')
            return 2
        missing = [m for m in missing if m in want]
    if a.limit:
        missing = missing[:a.limit]
    if not missing:
        print('没有需要补的（或 --only 全部已导）')
        return 0
    if a.check:
        for m in missing:
            print(f'  {m}')
        return 0

    os.makedirs(STAGING, exist_ok=True)
    temp = os.path.join(STAGING, '_tmp')
    os.makedirs(temp, exist_ok=True)
    ok, fail = 0, []
    for slug in missing:
        src = os.path.join(CUE, slug + '.b')
        dst = os.path.join(STAGING, slug + '.wav')
        if os.path.exists(dst):
            print(f'  {slug}: staging 已有，跳过')
            ok += 1
            continue
        acb = os.path.join(temp, slug + '.acb')
        shutil.copy2(src, acb)
        try:
            r = subprocess.run([P.VGMSTREAM, '-o', dst, acb], capture_output=True,
                               text=True, encoding='utf-8', errors='replace', timeout=120)
        except subprocess.TimeoutExpired:
            r = None
        finally:
            if os.path.exists(acb):
                os.remove(acb)
        if r is not None and r.returncode == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 1024:
            print(f'  {slug}: OK ({os.path.getsize(dst) / 2**20:.1f} MB)')
            ok += 1
        else:
            if os.path.exists(dst):
                os.remove(dst)
            err = (r.stderr or '').strip().splitlines()[-1] if r is not None and (r.stderr or '').strip() else '无输出'
            fail.append(slug)
            print(f'  {slug}: FAIL —— {err[:160]}')
    shutil.rmtree(temp, ignore_errors=True)
    print(f'\n完成 {ok}/{len(missing)}，失败 {len(fail)}')
    if fail:
        print('失败名单: ' + ', '.join(fail))
        return 1
    print(f'wav staging: {STAGING}')
    print(f'下一步: py -3 scripts/transcode_bgm.py --src "{STAGING}" --out "{OUT_BGM}" --codec flac')
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
