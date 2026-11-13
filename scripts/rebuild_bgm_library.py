#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rebuild_bgm_library.py — 把「新 cue 包 → 可播放 FLAC → bgm.json」这条链一次跑完。

为什么需要它
------------
`build_bgm_index.py` 只负责「已经解码好的 FLAC → 索引」。`files/AssetBundles/cue/`
里新同步进来的 `.b`（CRIWARE ACB）必须先过 vgmstream 解码、再转 FLAC，索引才看得见。
这三步以前是三条手工命令：

    bgm_backfill_decode.py  →  transcode_bgm.py  →  build_bgm_index.py

本脚本把它们串成一条，并统一判据（两个子脚本都存在"失败仍 exit 0"的历史问题，
所以不信退出码，只认汇总行）。它**不碰 APK 基础层**——烤在 base.apk 里的曲目
（如 8 首开服 BGM）仍需单独从模拟器提取后放进 `cue/`，再跑本脚本。

用法
----
    py -3 scripts/rebuild_bgm_library.py           # 解码缺的 → 转 FLAC → 重建索引
    py -3 scripts/rebuild_bgm_library.py --check   # 只报"缺多少首"，不写任何文件
    py -3 scripts/rebuild_bgm_library.py --probe   # 额外跑页面探针（需 8777 画廊服务）
    py -3 scripts/rebuild_bgm_library.py -v        # 打印子脚本完整输出

退出码
------
    0 = 全部成功（没有新曲也算成功）
    1 = 解码/转码有失败项，或索引重建失败
    2 = 环境缺件（cue 目录 / 输出目录）
"""

import argparse
import os
import re
import subprocess
import sys
import time

import stage_run  # 子脚本编排唯一实现（与 rebuild_labels 共用）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

CUE_DIR = os.path.join(ROOT, 'files', 'AssetBundles', 'cue')
STAGING = os.path.join(ROOT, '.diag', 'bgm_backfill_wav')
OFFICIAL = os.path.join(ROOT, 'Output', 'Audio', 'BGM')

DECODE = os.path.join(ROOT, 'scripts', 'diag', 'bgm_backfill_decode.py')
TRANSCODE = os.path.join(ROOT, 'scripts', 'transcode_bgm.py')
BUILD = os.path.join(ROOT, 'scripts', 'build_bgm_index.py')
PROBE = os.path.join(ROOT, 'scripts', 'diag', 'bgm_page_probe.py')

KEY_LINE = re.compile(r'(cue/bgm|缺 \d+|完成 \d+/\d+|成功 \d+|失败 \d+|台账|官方中文名|曲目|\[FAIL\]|\[WRITE\])')


def rel(p):
    return os.path.relpath(p, ROOT).replace('\\', '/')


def run_stage(name, argv, timeout=7200, verbose=False):
    """跑一个子脚本，回显关键行。返回 (rc, output)。超时不兜底（原行为：直接抛）。"""
    return stage_run.run_stage(name, argv, key_line=KEY_LINE, root=ROOT,
                               timeout=timeout, verbose=verbose)


def main():
    ap = argparse.ArgumentParser(description='解码新 cue 包 → 转 FLAC → 重建 bgm.json')
    ap.add_argument('--check', action='store_true', help='只报缺多少首，不写任何文件')
    ap.add_argument('--probe', action='store_true', help='额外跑页面探针（需 8777 服务）')
    ap.add_argument('-v', '--verbose', action='store_true', help='打印子脚本完整输出')
    a = ap.parse_args()

    if not os.path.isdir(CUE_DIR):
        print('[FAIL] 缺 %s —— 先跑 scripts/mumu_sync.py 同步新包' % rel(CUE_DIR))
        return 2
    if not os.path.isdir(OFFICIAL):
        print('[FAIL] 缺 %s' % rel(OFFICIAL))
        return 2

    # ① 解码：bgm_backfill_decode 自己会对比 cue 与已导 FLAC
    rc, out = run_stage('① 解码未导出的 cue 包（vgmstream → wav）',
                        [PY, DECODE] + (['--check'] if a.check else []), verbose=a.verbose)
    m_miss = re.search(r'缺\s*(\d+)', out)
    missing = int(m_miss.group(1)) if m_miss else None

    if a.check:
        if missing is None:
            print('\n[FAIL] 没读到「缺 N」汇总行，不能判状态')
            return 1
        print('\n检查结果：还有 %d 首未解码（--check 未写任何文件）' % missing)
        return 0

    # ② 解码失败项要拦住，否则转码会把空目录当好数据
    m_dec = re.search(r'完成\s*(\d+)/(\d+)，失败\s*(\d+)', out)
    if missing and missing > 0 and m_dec is None:
        print('\n[FAIL] 有缺失但没读到「完成 N/M，失败 K」汇总行 —— 不能判完成')
        return 1
    if m_dec and int(m_dec.group(3)) > 0:
        print('\n[FAIL] 解码失败 %s 首，停止（不转码、不重建索引）' % m_dec.group(3))
        return 1

    # 没有新曲就跳过转码：transcode 对空 staging 目录没有意义
    if not missing:
        print('\n没有未解码的曲目，跳过转码。')
    else:
        rc2, out2 = run_stage('② 转 FLAC 进正式区（ffmpeg + 台账）',
                              [PY, TRANSCODE, '--src', STAGING, '--out', OFFICIAL,
                               '--codec', 'flac'], timeout=7200, verbose=a.verbose)
        m_tr = re.search(r'成功\s*(\d+)\s*/\s*已存在跳过\s*(\d+)\s*/\s*失败\s*(\d+)', out2)
        if m_tr is None:
            print('\n[FAIL] 没读到「成功 N / 已存在跳过 N / 失败 N」汇总行 —— 不能判完成')
            return 1
        if int(m_tr.group(3)) > 0:
            print('\n[FAIL] 转码失败 %s 首，停止（不重建索引）' % m_tr.group(3))
            return 1

    # ③ 重建索引（labels 阶段也会跑一次，幂等；这里保证单独跑本脚本也完整）
    rc3, _ = run_stage('③ 重建 bgm.json（扫 FLAC + 读专辑表）', [PY, BUILD], verbose=a.verbose)
    if rc3 != 0:
        print('\n[FAIL] 索引重建失败')
        return 1

    # ④ 可选：页面探针（依赖 8777 服务，默认不跑）
    if a.probe:
        rc4, _ = run_stage('④ 页面探针（播放/分组/拖拽）', [PY, PROBE], timeout=1800,
                           verbose=a.verbose)
        if rc4 != 0:
            print('\n[FAIL] 页面探针未通过（索引本身可能没问题，先确认 8777 服务已起）')
            return 1

    print('\n完成：音乐库已同步到最新 cue 包。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
