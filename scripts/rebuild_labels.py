#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rebuild_labels.py — 一条命令重建「背景词根标签 + 音乐专辑索引」，并报告新增。

为什么需要这个脚本
------------------
新版本资产里出现新活动时，标签链本身其实是**数据驱动**的：

  · `tools/sharecfg_re/51_publish_bg_series.py`
      扫盘上 PNG → 走五条表内证据路线（memory / story / re_map / perform / child2）
      → 推出「词根 → 活动中文名」。新活动只要 `activity_sp_story` 里有
      `change_background` + `story`，就能靠拼音桥自动对上 `memory_group.title`。
  · `scripts/build_bg_meta.py`
      扫 `Output/Raw/*/*.png`，按文件名自动归词根，新词根自动成为子标签。
  · `scripts/build_bgm_index.py`
      扫 `Output/Audio/BGM*/*.flac`，读 `music_collect_config`（中文名 + album_id）
      与 `music_album`（`cover == MusicCover{n}`），新曲/新专辑自动挂上。

但这三条命令各自独立、**不在 `update_pipeline.py` 的编排里**，而且跑完不会告诉你
「这次新活动有几个自动认出了、几个还落在英文」。于是每次版本更新都要靠人记得
按顺序跑三条，再自己去页面里翻哪里变英文了。

本脚本只做两件事，不改任何判断逻辑：
  1. 按正确顺序把三条命令串起来（默认只重建标签，不动源包、不重导出图片）；
  2. 和上次基线对比，打印「新增词根 / 自动认出 / 仍需补名 / 新增曲目 / 新增专辑」，
     并把当前快照写回基线，供下次对比。

用法
----
    py -3 scripts/rebuild_labels.py                 # 重建两侧 + 漂移报告
    py -3 scripts/rebuild_labels.py --check         # 只跑只读闸门（不写任何产物）
    py -3 scripts/rebuild_labels.py --bg-only       # 只重建背景标签
    py -3 scripts/rebuild_labels.py --bgm-only      # 只重建音乐索引
    py -3 scripts/rebuild_labels.py --export-bg     # 先把新背景从源包导到 Output/Raw
    py -3 scripts/rebuild_labels.py --report-only   # 不重建，只对比现有产物与基线
    py -3 scripts/rebuild_labels.py --reset-baseline  # 丢弃旧基线，把当前快照当新基线
    py -3 scripts/rebuild_labels.py -v              # 打印子脚本完整输出

退出码
------
    0 = 重建成功（**未命名词根不算失败**：它们可能本来就没有表内证据，
        按项目纪律「不许编名」，只报告、不阻断）
    1 = 任一闸门红 / 子脚本失败（此时不更新基线，避免把坏状态记成"已知"）
    2 = 环境缺件（缺 lua_json / Output/Raw / Output/Audio/BGM）
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

GALLERY = os.path.join(ROOT, 'Output', 'gallery_v2')
BG_META = os.path.join(GALLERY, 'bg_meta.json')
BGM_JSON = os.path.join(GALLERY, 'bgm.json')
BASELINE = os.path.join(GALLERY, 'labels_baseline.json')
REPORT = os.path.join(GALLERY, 'labels_report.json')

LUAJ = os.path.join(ROOT, '.diag', 'sharecfg_re', 'lua_json')
RAW = os.path.join(ROOT, 'Output', 'Raw')
BGM_DIR = os.path.join(ROOT, 'Output', 'Audio', 'BGM')

PUB_BG = os.path.join(ROOT, 'tools', 'sharecfg_re', '51_publish_bg_series.py')
BUILD_BG = os.path.join(ROOT, 'scripts', 'build_bg_meta.py')
BUILD_BGM = os.path.join(ROOT, 'scripts', 'build_bgm_index.py')
MAKE_BG_THUMBS = os.path.join(ROOT, 'scripts', 'make_bg_thumbs.py')
EXPORT_BG = os.path.join(ROOT, 'scripts', 'export_assets.py')

# 子脚本输出很长，默认只回显这些"有判断价值"的行，避免刷屏。
KEY_LINE = re.compile(
    r'(发布 \d+ 组|\[WRITE\]|闸门：|背景图 \d+ 张|词根 \d+ 个|曲目|官方中文名|专辑关联'
    r'|失败:|成功:|完成 ok=|待生成|导出完成|耗时:|✓|✗|FAIL|WARN)')


# ---------------------------------------------------------------- 小工具

def rel(p):
    """把绝对路径压成相对项目根的形式，打印用。"""
    return os.path.relpath(p, ROOT).replace('\\', '/')


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')


def run_stage(name, argv, timeout=3600, verbose=False):
    """跑一个子脚本并回显关键行。

    参数表
    ------
    name     : str  阶段显示名（打印用）
    argv     : list 完整命令（含解释器与脚本路径）
    timeout  : int  超时秒数；导出背景才需要给大值
    verbose  : bool 为 True 时打印子脚本完整 stdout/stderr

    返回
    ----
    (returncode, 合并后的输出文本)
    """
    print('\n▶ %s' % name)
    t0 = time.time()
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    try:
        p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace',
                           timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        print('   ↳ 超时（%ds）' % timeout)
        return 124, ''
    out = (p.stdout or '') + (p.stderr or '')
    if verbose:
        print(out)
    else:
        for line in out.splitlines():
            if KEY_LINE.search(line):
                print('   ' + line.rstrip())
    print('   ↳ rc=%d / %.1fs' % (p.returncode, time.time() - t0))
    return p.returncode, out


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def snapshot():
    """读取当前两份产物，压成可对比的快照。

    返回
    ----
    dict:
      bg      {root: {'cn','from','n'}}   只含 bg_meta.roots（n>=2 的词根）
      tracks  [slug, …]                   音乐曲目
      albums  [专辑名, …]                 已挂上的专辑
      named   int                         有官方中文名的曲目数
      total   int                         曲目总数
    """
    bg = {}
    if os.path.isfile(BG_META):
        for k, v in (load_json(BG_META).get('roots') or {}).items():
            bg[k] = {'cn': v.get('cn', ''), 'from': v.get('cn_from', ''), 'n': v.get('n', 0)}
    tracks, albums, named, total, events = [], [], 0, 0, 0
    if os.path.isfile(BGM_JSON):
        d = load_json(BGM_JSON)
        tracks = sorted(t.get('slug', '') for t in d.get('tracks') or [])
        albums = sorted({t.get('album') for t in (d.get('tracks') or []) if t.get('album')})
        c = d.get('counts') or {}
        named = int(c.get('named_cn') or 0)
        events = int(c.get('with_event') or 0)
        total = len(tracks)
    return {'bg': bg, 'tracks': tracks, 'albums': albums, 'named': named,
            'total': total, 'events': events}


def load_baseline():
    if not os.path.isfile(BASELINE):
        return None
    try:
        return load_json(BASELINE)
    except (OSError, ValueError):
        return None


def write_baseline(cur):
    """把当前快照写成基线。只存"名单"，不存全部曲目详情，文件很小。"""
    os.makedirs(GALLERY, exist_ok=True)
    doc = {
        'saved_at': now(),
        'note': 'rebuild_labels.py 的对比基线；删掉它会退化为"首次运行"，不影响产物。',
        'bg_roots': {k: v['from'] for k, v in cur['bg'].items()},
        'tracks': cur['tracks'],
        'albums': cur['albums'],
    }
    with open(BASELINE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return BASELINE


# ---------------------------------------------------------------- 重建

def rebuild_bg(check=False, verbose=False):
    """重建背景标签：51 发布器 → build_bg_meta。

    返回 True/False。51 红则不再跑 bg_meta（标签没更新，重建没意义）。
    """
    if not os.path.isdir(LUAJ):
        print('[FAIL] 缺 %s —— 先跑 tools/sharecfg_re/41_export_lua_tables.py' % rel(LUAJ))
        return False
    if not os.path.isdir(RAW):
        print('[FAIL] 缺 %s —— 先跑 scripts/export_assets.py --target bg' % rel(RAW))
        return False

    argv = [PY, PUB_BG] + (['--check'] if check else [])
    rc, out = run_stage('背景①：发布器推词根中文名（五条证据路线）', argv, verbose=verbose)
    # 正式模式写盘会打印 [WRITE]；--check 模式打印「闸门：绿」
    ok = rc == 0 and ('[WRITE] inputs/gamecfg/' in out if not check else '闸门：绿' in out)
    if not ok:
        print('   ✗ 51 发布器未通过闸门，跳过 bg_meta 重建')
        return False

    argv = [PY, BUILD_BG] + (['--check'] if check else [])
    rc, out = run_stage('背景②：重建 bg_meta.json（自动归词根）', argv, verbose=verbose)
    ok = rc == 0 and ('[WRITE]' in out if not check else '闸门：绿' in out)
    if not ok:
        print('   ✗ bg_meta 未通过闸门')
        return False
    # 新图进库的最后一步：缩略图。增量、已存在即 skip；少了它背景页就是空格子。
    # 只在正式重建时跑；--check 不写盘，也不拿旧 bg_meta 的缺图数冒充本轮结论。
    if not check:
        rc, out = run_stage('背景③：补齐新缩略图（增量，已存在跳过）',
                            [PY, MAKE_BG_THUMBS], timeout=7200, verbose=verbose)
        ok = rc == 0 and '完成' in out
        if not ok:
            print('   ✗ 缩略图生成失败（bg_meta 已写，补齐后可重跑 labels）')
    return ok


def rebuild_bgm(check=False, verbose=False):
    """重建音乐索引。

    `build_bgm_index.py` 没有 --check 通道；--check 模式下只读现有产物做统计，
    不写盘（避免"检查"反而改了文件）。
    """
    if check:
        if not os.path.isfile(BGM_JSON):
            print('[FAIL] 缺 %s（--check 不重建）' % rel(BGM_JSON))
            return False
        print('\n▶ 音乐：--check 模式只读现有 bgm.json（不重建）')
        d = load_json(BGM_JSON)
        c = d.get('counts') or {}
        print('   %s 首 / 中文名 %s / 专辑 %s 张'
              % (len(d.get('tracks') or []), c.get('named_cn'), c.get('albums')))
        return True
    if not os.path.isdir(BGM_DIR):
        print('[FAIL] 缺 %s' % rel(BGM_DIR))
        return False
    rc, _ = run_stage('音乐：重建 bgm.json（扫 FLAC + 读专辑表）',
                      [PY, BUILD_BGM], verbose=verbose)
    return rc == 0


def export_bg(verbose=False):
    """可选：先把源包里的新背景导到 Output/Raw（全目录扫，耗时随包数增长）。"""
    if not os.path.isdir(os.path.join(ROOT, 'files', 'AssetBundles')):
        print('[FAIL] 缺 files/AssetBundles')
        return False
    rc, out = run_stage('背景⓪：从源包导出背景图 → Output/Raw（全量扫，可能几分钟）',
                        [PY, EXPORT_BG, '--target', 'bg'], timeout=10800, verbose=verbose)
    # export_assets 的退出码不可信（项目已知问题），判据只看汇总行的「失败: 0」
    m = re.search(r'失败:\s*(\d+)', out)
    ok = rc == 0 and m is not None and int(m.group(1)) == 0
    if m is None:
        print('   ✗ 没读到「失败: N」汇总行 —— 不能判定成功')
    return ok


# ---------------------------------------------------------------- 报告

def report(cur, base, write_file=True):
    """打印人话报告，并把结构化结果写到 labels_report.json。

    参数表
    ------
    cur        : dict  snapshot() 的当前快照
    base       : dict | None  上次基线；None 表示没有基线（首次运行或刚 --reset-baseline）
    write_file : bool  False 时只打印、不写 labels_report.json（--check 用）

    返回
    ----
    dict 报告本体
    """
    bg = cur['bg']
    unnamed = sorted([(k, v) for k, v in bg.items() if v['from'] == 'root'],
                     key=lambda x: -x[1]['n'])
    named_n = len(bg) - len(unnamed)

    print('\n' + '=' * 66)
    print('标签漂移报告  %s' % now())
    print('=' * 66)

    print('\n【背景】词根 %d 个（中文名 %d / 未命名 %d），这些词根覆盖 %d 张 png'
          % (len(bg), named_n, len(unnamed), sum(v['n'] for v in bg.values())))

    new_roots, auto_named, need_name, gone_roots = [], [], [], []
    if base is None:
        print('  没有基线（首次运行，或刚 --reset-baseline）：本次只列当前状态，不列新增。')
    else:
        old = base.get('bg_roots') or {}
        for k in sorted(set(bg) - set(old), key=lambda x: -bg[x]['n']):
            (auto_named if bg[k]['from'] != 'root' else need_name).append(k)
            new_roots.append(k)
        gone_roots = sorted(set(old) - set(bg))
        if new_roots:
            print('  本次新增词根 %d 个：' % len(new_roots))
            for k in auto_named:
                print('    ✅ %-22s → %s（%d 张，来源 %s）'
                      % (k, bg[k]['cn'], bg[k]['n'], bg[k]['from']))
            for k in need_name:
                print('    ⚠️ %-22s → 未命名（%d 张）—— 需人工补名' % (k, bg[k]['n']))
        else:
            print('  本次没有新增词根。')
        if gone_roots:
            print('  ⚠️ 消失词根 %d 个（图片被删/改名？）：%s'
                  % (len(gone_roots), ', '.join(gone_roots[:8])))

    if unnamed:
        print('  当前未命名词根 %d 个 / %d 张（按张数降序，前 15）：'
              % (len(unnamed), sum(v['n'] for _, v in unnamed)))
        for k, v in unnamed[:15]:
            print('    · %-24s %d 张' % (k, v['n']))
        if len(unnamed) > 15:
            print('    … 其余 %d 个见 labels_report.json' % (len(unnamed) - 15))
        print('  说明：这些词根五条证据路线都没命中，按「不许编名」保留英文；')
        print('        知道出处就补 inputs/gamecfg/bg_category_labels.json 或 bg_series_labels.json；')
        print('        也可在控制台「背景标注」复核台补名（写 annotations/bg_root_names.json，只补 root 档）。')

    print('\n【音乐】曲目 %d 首 / 官方中文名 %d / 专辑 %d 张 / 活动回忆 %d 首'
          % (cur['total'], cur['named'], len(cur['albums']), cur['events']))
    new_tracks, new_albums = [], []
    if base is not None:
        old_t = set(base.get('tracks') or [])
        old_a = set(base.get('albums') or [])
        new_tracks = sorted(set(cur['tracks']) - old_t)
        new_albums = sorted(set(cur['albums']) - old_a)
        if new_tracks:
            print('  本次新增曲目 %d 首：' % len(new_tracks))
            for s in new_tracks[:12]:
                print('    + %s' % s)
            if len(new_tracks) > 12:
                print('    … 其余 %d 首见 labels_report.json' % (len(new_tracks) - 12))
        else:
            print('  本次没有新增曲目。')
        if new_albums:
            print('  ✅ 本次新增专辑 %d 张：%s' % (len(new_albums), ', '.join(new_albums)))

    doc = {
        'generated_at': now(),
        'baseline_was_present': base is not None,
        'bg': {
            'roots_total': len(bg),
            'named': named_n,
            'unnamed': [{'root': k, 'n': v['n']} for k, v in unnamed],
            'new_roots': new_roots,
            'new_auto_named': [{'root': k, 'cn': bg[k]['cn'], 'from': bg[k]['from']}
                               for k in auto_named],
            'new_need_name': [{'root': k, 'n': bg[k]['n']} for k in need_name],
            'gone_roots': gone_roots,
        },
        'bgm': {
            'tracks_total': cur['total'],
            'named_cn': cur['named'],
            'albums': len(cur['albums']),
            'with_event': cur['events'],
            'new_tracks': new_tracks,
            'new_albums': new_albums,
        },
    }
    os.makedirs(GALLERY, exist_ok=True)
    if write_file:
        with open(REPORT, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        print('\n[WRITE] %s' % rel(REPORT))
    else:
        print('\n（--check：报告未写盘）')

    # 一句话结论，方便直接贴进交接
    if base is None:
        print('结论：本次为基线建立/对照缺失，只记录现状；下次起会列出新增。')
    elif need_name:
        print('结论：%d 个新词根需要补名；其余部分已自动完成。' % len(need_name))
    elif new_roots:
        print('结论：新词根全部自动认出中文名，无需人工补。')
    else:
        print('结论：无新增词根；索引与基线一致。')
    return doc


# ---------------------------------------------------------------- 入口

def main():
    ap = argparse.ArgumentParser(description='重建背景词根标签 + 音乐专辑索引，并报告新增')
    ap.add_argument('--check', action='store_true', help='只跑只读闸门，不写任何产物')
    ap.add_argument('--bg-only', action='store_true', help='只重建背景')
    ap.add_argument('--bgm-only', action='store_true', help='只重建音乐')
    ap.add_argument('--export-bg', action='store_true', help='先把源包背景导到 Output/Raw（慢）')
    ap.add_argument('--report-only', action='store_true', help='不重建，只对比现有产物与基线')
    ap.add_argument('--reset-baseline', action='store_true', help='丢弃旧基线，把当前快照当新基线')
    ap.add_argument('-v', '--verbose', action='store_true', help='打印子脚本完整输出')
    a = ap.parse_args()

    if a.bg_only and a.bgm_only:
        print('[FAIL] --bg-only 与 --bgm-only 不能同时给')
        return 2
    if a.check and a.report_only:
        print('[FAIL] --check 与 --report-only 不能同时给（前者要跑闸门，后者完全不跑）')
        return 2

    # pypinyin 是 story 路线（活动名拼音桥）的硬依赖。项目约定用 `py -3`（3.11，
    # 已装 0.55.0）；若用别的解释器跑本脚本，51 会静默降级成"只跑四条路线"，
    # 新活动就会大面积落英文 —— 这里必须先响一声。
    try:
        import pypinyin  # noqa: F401
        has_pinyin = True
    except ImportError:
        has_pinyin = False
    if has_pinyin is False:
        print('⚠️ 当前解释器没有 pypinyin —— 51 发布器的 story 路线会降级，')
        print('   新活动很可能对不上中文名。请改用 `py -3 scripts/rebuild_labels.py`。')
        print('   当前解释器：%s' % PY)

    if a.reset_baseline and os.path.isfile(BASELINE):
        os.remove(BASELINE)
        print('已删除旧基线：%s' % rel(BASELINE))

    if not a.report_only:
        if a.export_bg:
            if not export_bg(a.verbose):
                print('\n[FAIL] 背景导出失败，终止（未写任何标签产物）')
                return 1

        ok_bg = True
        if not a.bgm_only:
            ok_bg = rebuild_bg(check=a.check, verbose=a.verbose)

        ok_bgm = True
        if not a.bg_only:
            ok_bgm = rebuild_bgm(check=a.check, verbose=a.verbose)

        if not (ok_bg and ok_bgm):
            print('\n[FAIL] 有阶段未通过 —— 不更新基线，避免把坏状态记成"已知"')
            return 1

    cur = snapshot()
    if not cur['bg'] and not cur['tracks']:
        print('\n[FAIL] 两份产物都读不到，无法出报告')
        return 2

    # --check 也读基线（只读），这样"检查"能看到新增/消失；只是不写回。
    base = load_baseline()
    report(cur, base, write_file=not a.check)

    if not a.check and not a.report_only:
        write_baseline(cur)
        print('[WRITE] %s（下次对比用）' % rel(BASELINE))

    # --check / --report-only 只读，不碰基线；重建成功才更新基线
    return 0


if __name__ == '__main__':
    sys.exit(main())
