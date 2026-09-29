# -*- coding: utf-8 -*-
"""游戏更新一条龙：把 WF-15 的 11 步变成一条命令跑到「待你确认」，第二条命令签字换入。

    py -3 scripts/update_pipeline.py --plan                 # 只读：这次更新会动什么
    py -3 scripts/update_pipeline.py                        # 跑到 review 就停（不碰正式产物）
    py -3 scripts/update_pipeline.py --approve meta live2d  # 签字放行指定 live 阶段
    py -3 scripts/update_pipeline.py --full                 # 显式全量（先报预计耗时再要确认）

三条不可妥协的设计（都是踩出来的，改这个文件前先读）：

1. **退出码不作通过证据。** `export_cue_audio` / `make_thumbs` / `fix_model3` /
   `extract_spine_v2` / `compose_paintings_v2` / `l2d_motion_audit` /
   `spine_parts_prefab_diff` / `voice_gap_audit` / `run_cg_export` 这 9 个
   **失败时照样 exit 0**。所以每个阶段自带 `judge()`：数汇总行、或跑对应的 gate 脚本。
   没有判据的阶段一律标 `judge=None` 并在报告里写明「未证」，不许算通过。
2. **写向优先 argv；只有 env 通道的脚本必须把注入值打出来。**
   `build_gallery_index.py`(GALLERY_OUT_DIR) / `fix_model3.py`(L2D_OUT_DIR) /
   `make_thumbs.py` / `deploy_gallery.py` 没有 argv 通道 —— 2026-09-24 那次
   269 个模型被原地覆写，就是因为脱离进程下 env 能不能被子进程读到**不可复现**（§25）。
3. **覆写一批产物之前先扫硬链接。** 历史上做过逐字节去重，共享 inode 的两个名字
   「写一个变两个」，会让修复看起来失效（§64）。`live` 阶段前强制 `scan_hardlinks()`。

阶段分三档：
  read   —— 只读，永远自动跑
  staged —— 只写 `.diag/pipeline/`，天然安全，自动跑
  live   —— 写 `Output/` 或 `files/`，**必须 --approve 点名放行**
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
AB = os.path.join(ROOT, 'files', 'AssetBundles')
OUT = os.path.join(ROOT, 'Output')
WORK = os.path.join(ROOT, '.diag', 'pipeline')          # 本工具唯一的落盘区
STATE = os.path.join(WORK, 'pipeline_state.json')
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')


def log(m):
    print(f'[{time.strftime("%H:%M:%S")}] {m}', flush=True)


# ---------------------------------------------------------------- 基础设施
def run(argv, cwd=ROOT, timeout=None, echo=None):
    """跑一个子命令，返回 (退出码, stdout, stderr)。"""
    r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=ENV, timeout=timeout)
    if echo and r.stdout:
        for ln in r.stdout.splitlines():
            if any(k in ln for k in echo):
                log('    | ' + ln[:160])
    return r.returncode, r.stdout or '', r.stderr or ''


def count(d, pat):
    return len([p for p in glob.glob(os.path.join(d, pat))]) if os.path.isdir(d) else -1


def fingerprint():
    """这次更新的输入指纹：源包总数 + 依赖表哈希。用来判断"同一批输入是否已跑过"。"""
    n = sum(len(f) for _, _, f in os.walk(AB)) if os.path.isdir(AB) else 0
    dm = os.path.join(OUT, 'dependency_manifest.json')
    h = hashlib.md5(open(dm, 'rb').read()).hexdigest()[:10] if os.path.isfile(dm) else 'none'
    return f'bundles={n} deps={h}'


def scan_hardlinks(paths):
    """返回这批路径里 st_nlink>1 的（= 去重留下的共享 inode，覆写会连坐）。"""
    out = []
    for p in paths:
        try:
            if os.stat(p).st_nlink > 1:
                out.append(p)
        except OSError:
            pass
    return out


# ---------------------------------------------------------------- 阶段定义
class Stage:
    def __init__(self, key, title, tier, fn, judge_desc, produces=None, needs=None):
        self.key, self.title, self.tier, self.fn = key, title, tier, fn
        self.judge_desc, self.produces, self.needs = judge_desc, produces or [], needs or []

    @property
    def live(self):
        return self.tier == 'live'


RESULTS = {}


def verdict(key, ok, detail):
    RESULTS[key] = {'ok': ok, 'detail': detail, 'at': time.strftime('%Y-%m-%d %H:%M:%S')}
    log(f'  {"✅" if ok else "❌"} {key}: {detail}')
    return ok


# ---------------------------------------------------------- 1 preflight
def st_preflight():
    bad = []
    for led in ('azdata', 'gamecfg'):
        rc, so, se = run([PY, 'scripts/diag/check_inputs.py', led])
        log(f'  权威输入台账 {led}: {"PASS" if rc == 0 else "FAIL"}')
        if rc:
            bad.append(f'{led}({(so or se).strip().splitlines()[-1][:70] if (so or se).strip() else "rc"}={rc})')
    rc, so, _ = run([PY, 'scripts/fetch_gallery_vendor.py', '--check'])
    log(f'  vendor 台账: {"PASS" if rc == 0 else "FAIL"}')
    if rc:
        bad.append('vendor')
    # 依赖表与权威元数据在不在（后面好几个阶段要吃它）
    for f in ('dependency_manifest.json', 'ship_meta.json'):
        if not os.path.isfile(os.path.join(OUT, f)):
            bad.append(f'缺 {f}')
    return verdict('preflight', not bad, '权威输入与 vendor 全绿' if not bad else '红: ' + '; '.join(bad))


# ---------------------------------------------------------- 2 pull（读档 + 可选换入）
def st_pull(approved):
    rc, so, se = run([PY, 'scripts/mumu_sync.py', 'diff'], timeout=1800,
                     echo=['新增', '大小不一致', '本地独有', '合计'])
    if rc != 0:
        return verdict('pull', False, f'mumu_sync diff 失败 rc={rc}（模拟器没开？adb 不在 PATH？）')
    txt = so + se
    new = int((re.search(r'新增[^\d]*(\d+)', txt) or [0, 0])[1]) if re.search(r'新增[^\d]*(\d+)', txt) else -1
    diff_n = int(re.search(r'大小不一致[^\d]*(\d+)', txt).group(1)) if re.search(r'大小不一致[^\d]*(\d+)', txt) else -1
    log(f'  diff: 新增 {new} / 大小不一致 {diff_n}')
    os.makedirs(WORK, exist_ok=True)
    open(os.path.join(WORK, 'sync_diff.txt'), 'w', encoding='utf-8').write(txt)
    if 'pull' not in approved:
        return verdict('pull', True, f'只读到 diff（新增 {new}/变更 {diff_n}）。'
                                     f'**拉包写 files/ 是 live 档**，要放行请 --approve pull')
    rc, so2, _ = run([PY, 'scripts/mumu_sync.py', 'sync', '--apply'], timeout=7200,
                     echo=['完成', '失败', '合计'])
    return verdict('pull', rc == 0, f'sync --apply rc={rc}（该脚本的退出码可信：fail>0 即 1）')


# ---------------------------------------------------------- 3 deps
def st_deps(approved):
    """重生成官方依赖表。WF-15 第 3 步：最容易漏的一步，漏了新包 PPtr 解析不到。"""
    tmp = os.path.join(WORK, 'dependency_manifest.json')
    rc, _, _ = run([PY, 'scripts/export_dependency_manifest.py', '--out', tmp], timeout=3600)
    if rc or not os.path.isfile(tmp):
        return verdict('deps', False, f'重生成失败 rc={rc}')
    old = json.load(open(os.path.join(OUT, 'dependency_manifest.json'), encoding='utf-8')) \
        if os.path.isfile(os.path.join(OUT, 'dependency_manifest.json')) else {}
    new = json.load(open(tmp, encoding='utf-8'))
    lost = [k for k in old if k not in new]
    log(f'  依赖表 旧 {len(old)} 条 → 新 {len(new)} 条，丢失 {len(lost)} 条')
    if lost:
        return verdict('deps', False, f'新表**丢了 {len(lost)} 个旧包**（不该发生）——拒绝换入，先查源包')
    if not ('deps' in approved):
        return verdict('deps', True, f'新表已就绪（+{len(new) - len(old)} 条）在临时区。'
                                     f'写 Output/ 是 live 档，请 --approve deps')
    shutil.copy2(os.path.join(OUT, 'dependency_manifest.json'),
                 os.path.join(WORK, 'dependency_manifest.prev.json'))
    shutil.copy2(tmp, os.path.join(OUT, 'dependency_manifest.json'))
    return verdict('deps', True, f'已换入 Output/（旧表留在 {WORK}/dependency_manifest.prev.json）')


# ---------------------------------------------------------- 4 meta
def st_meta(approved):
    rc, so, se = run([PY, 'scripts/build_ship_meta.py'], timeout=1800, echo=['条目', '无源', 'source'])
    if rc:
        return verdict('meta', False, f'--diag 失败 rc={rc}')
    tmpdir = os.path.join(WORK, 'meta')
    os.makedirs(tmpdir, exist_ok=True)
    rc, so, _ = run([PY, 'scripts/build_ship_meta.py', '--write', '--out', tmpdir],
                    timeout=1800, echo=['写入', '条目'])
    if rc or not os.path.isfile(os.path.join(tmpdir, 'ship_meta.json')):
        return verdict('meta', False, f'--write --out 失败 rc={rc}')
    if not ('meta' in approved):
        return verdict('meta', True, f'新 ship_meta 已产到临时区。'
                                     f'⚠️ 索引读的是写死的 Output/ship_meta.json（无 argv/env 通道），'
                                     f'所以"用新元数据预览索引"必须先换入 —— 请 --approve meta')
    bak = os.path.join(WORK, 'ship_meta.prev.json')
    if os.path.isfile(os.path.join(OUT, 'ship_meta.json')):
        shutil.copy2(os.path.join(OUT, 'ship_meta.json'), bak)
    shutil.copy2(os.path.join(tmpdir, 'ship_meta.json'), os.path.join(OUT, 'ship_meta.json'))
    rc2, so2, _ = run([PY, 'scripts/diag/ship_meta_authority_diff.py'], echo=['闸门', '改动'])
    return verdict('meta', rc2 == 0,
                   f'已换入并跑权威闸门 ship_meta_authority_diff → {"绿" if rc2 == 0 else "红"}'
                   + (f'：{(so2.strip().splitlines() or ["?"])[-1][:80]}' if rc2 else ''))


# ---------------------------------------------------------- 5 导出类（全部 staged 到临时区）
def affected_stems(full):
    """增量范围：detect 出来的新增/变更包 → 磁盘 stem 集合。"""
    if full:
        return None
    p = os.path.join(WORK, 'affected.txt')
    if os.path.isfile(p):
        return [x.strip() for x in open(p, encoding='utf-8') if x.strip()]
    return None


def st_paintings(full, approved):
    todo = affected_stems(full)
    tgt = os.path.join(WORK, 'Paintings_v2')
    os.makedirs(tgt, exist_ok=True)
    if todo is None:
        log('  --full：以 painting/ 源包枚举主皮肤（沿用 run_v2_full 的 is_main 口径）')
        sys.path.insert(0, HERE)
        import run_v2_full as rv
        todo = rv.baseline_targets()
    fail = 0
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        rc, so, _ = run([PY, 'scripts/compose_paintings_v2.py'] + batch + ['--out', tgt], timeout=3600)
        fail += len([l for l in so.splitlines() if l.startswith('✗')])
        if (i // 50) % 4 == 0:
            log(f'  进度 {min(i + 50, len(todo))}/{len(todo)} 失败累计 {fail}')
    n = count(tgt, '*.png')
    return verdict('paintings', n > 0 and fail == 0,
                   f'临时区 {n} 张 / 渲染失败 {fail} 个'
                   + ('（⚠️ 该脚本失败仍 exit 0，判据是数 ✗ 行不是退出码）' if True else ''))


def st_spine(full, approved):
    tgt = os.path.join(WORK, 'Spine_v2')
    os.makedirs(tgt, exist_ok=True)
    todo = affected_stems(full)
    d = os.path.join(AB, 'spinepainting')
    allnames = sorted(f for f in os.listdir(d)
                      if os.path.isfile(os.path.join(d, f)) and not f.endswith('_res'))
    names = allnames if todo is None else [n for n in allnames if n in set(todo)]
    fail = []
    for i in range(0, len(names), 25):
        b = names[i:i + 25]
        rc, so, _ = run([PY, 'scripts/extract_spine_v2.py'] + b + ['--out', tgt], timeout=3600)
        fail += [l.split(':')[0].lstrip('✗ ') for l in so.splitlines() if l.startswith('✗')]
    rc, so, _ = run([PY, 'scripts/extract_spine_v2.py', '--parts-only']
                    + names + ['--out', tgt], timeout=1800)
    nparts = count(tgt, '*/parts.json')
    return verdict('spine', len(fail) == 0 and nparts >= len(names) - 1,
                   f'临时区 {count(tgt, "*")} 个目录 / parts.json {nparts} 份 / 失败 {len(fail)} {fail[:5]}')


def st_live2d(full, approved):
    """reconstruct → extract_motions → fix_model3 → 三道闸门。写向一律 --out 临时区。"""
    tgt = os.path.join(WORK, 'Live2D')
    os.makedirs(tgt, exist_ok=True)
    rc, so, _ = run([PY, 'scripts/reconstruct_live2d.py', '--all', '--out', tgt],
                    timeout=7200, echo=['完成', '失败', '进度'])
    # ⚠️ extract_motions --all 必须带 --out，否则它自己就拒绝（§25 那次事故换来的约定）
    rc2, so2, _ = run([PY, 'scripts/extract_motions.py', '--all', '--out', tgt],
                      timeout=7200, echo=['[SUMMARY]', '失败'])
    done = re.findall(r'\[SUMMARY\] 模型 (\d+)/(\d+) 处理完', so2)
    if not done:
        return verdict('live2d', False, 'extract_motions 没打出 [SUMMARY] 收尾行 ⇒ 判为未完成/被截断，'
                                        '不能拿退出码当通过')
    # fix_model3 只有 env 通道 —— 显式注入并**打出来**（设计第 2 条）
    os.environ['L2D_OUT_DIR'] = tgt
    ENV['L2D_OUT_DIR'] = tgt
    log(f'  ⚠️ fix_model3 无 argv 通道，注入 L2D_OUT_DIR={tgt}（env 在脱离进程下不可复现，故必须回读确认）')
    rc3, so3, _ = run([PY, 'scripts/fix_model3.py'], timeout=1800)
    gates = {}
    for name, argv in (('texorder', ['scripts/diag/l2d_texorder_check.py']),
                       ('tex_completeness', ['scripts/diag/l2d_tex_completeness.py']),
                       ('motion_audit', ['scripts/diag/l2d_motion_audit.py'])):
        rcg, sog, _ = run([PY] + argv, timeout=3600, echo=['shell', 'misassign', 'missing', '升序'])
        gates[name] = rcg
    audit = json.load(open(os.path.join(ROOT, '.diag', 'l2d_motion_audit.json'), encoding='utf-8')) \
        if os.path.isfile(os.path.join(ROOT, '.diag', 'l2d_motion_audit.json')) else {}
    return verdict('live2d', done[-1][0] == done[-1][1] and gates.get('texorder') == 0
                   and gates.get('tex_completeness') == 0,
                   f'motion {done[-1][0]}/{done[-1][1]} 模型；闸门 texorder={gates["texorder"]} '
                   f'tex_completeness={gates["tex_completeness"]}（motion_audit 恒 exit 0，只作参考：'
                   f'shell={audit.get("shell", "?")}）')


def st_audio(approved):
    rc, so, _ = run([PY, 'scripts/extract_cv_voice.py', '--all', '--skip-done'],
                    timeout=7200, echo=['包', '失败', '合计'])
    rc2, so2, _ = run([PY, 'scripts/diag/voice_gap_audit.py'], timeout=1800, echo=['缺口', '合计'])
    rc3, _, _ = run([PY, 'scripts/diag/l2d_voice_inventory.py'], timeout=600)
    return verdict('audio', rc3 == 0,
                   f'cv_voice rc={rc}（单包失败不反映到退出码）；voice_gap_audit 恒 exit 0 只作参考；'
                   f'l2d_voice_inventory（可信）rc={rc3}')


def st_cg(full, approved):
    todo = affected_stems(full)
    only = '' if todo is None else ','.join(todo)
    argv = [PY, 'scripts/diag/run_cg_export.py', '--size', '2400', '--extra', 'animFrame=1', '--redo']
    if only:
        argv += ['--only', only]
    rc, so, _ = run(argv, timeout=7200, echo=['全部结束', '完成', '失败'])
    m = re.search(r'完成(\d+) 跳过(\d+) 失败(\d+)', so)
    if not m:
        return verdict('cg', False, '没读到「完成N 跳过N 失败N」汇总行 ⇒ 不能判完成（该脚本超时也 exit 0）')
    ok, skip, bad = map(int, m.groups())
    return verdict('cg', bad == 0 and ok > 0, f'CG 导出 完成{ok} 跳过{skip} 失败{bad}')


# ---------------------------------------------------------- 6 review（出对照，不写正式）
def st_review():
    lines = []
    chg = []
    p_new = os.path.join(WORK, 'Paintings_v2')
    live_p = os.path.join(OUT, 'Paintings_v2')
    if os.path.isdir(p_new) and os.path.isdir(live_p):
        news = [os.path.basename(x)[:-4] for x in glob.glob(os.path.join(p_new, '*.png'))]
        chg = [s for s in news
               if os.path.isfile(os.path.join(live_p, s + '.png'))
               and hashlib.md5(open(os.path.join(p_new, s + '.png'), 'rb').read()).digest()
               != hashlib.md5(open(os.path.join(live_p, s + '.png'), 'rb').read()).digest()]
        open(os.path.join(WORK, 'changed_paintings.txt'), 'w', encoding='utf-8') \
            .write('\n'.join(chg))
        lines.append(f'立绘：临时区 {len(news)} 张，其中与线上不同 {len(chg)} 张')
        if chg:
            run([PY, 'scripts/diag/make_pair_sheet.py', '--old', live_p, '--new', p_new,
                 '--names', ','.join(chg[:12]), '--out', os.path.join(WORK, 'sheet_paintings.png'),
                 '--cell', '260'], timeout=1800)
    hl = scan_hardlinks([os.path.join(live_p, s + '.png') for s in (chg if chg else [])])
    lines.append(f'⚠️ 硬链待断 {len(hl)} 个（不断则"写一个变两个"，见 §64）')
    open(os.path.join(WORK, 'hardlinks.txt'), 'w', encoding='utf-8').write('\n'.join(hl))
    return verdict('review', True, ' | '.join(lines))


# ---------------------------------------------------------- 7 换入（live，必须签字）
def st_swapin(approved):
    if 'swap-in' not in approved:
        return verdict('swap-in', True, '未签字 ⇒ 跳过。要换入请 --approve swap-in '
                                        '（会先备份到 Output/_OLD_bak/<主题>_<日期>/）')
    lst = os.path.join(WORK, 'changed_paintings.txt')
    if not os.path.isfile(lst) or not open(lst, encoding='utf-8').read().strip():
        return verdict('swap-in', True, '没有待换入的立绘（清单为空）')
    hl = [l for l in open(os.path.join(WORK, 'hardlinks.txt'), encoding='utf-8') if l.strip()]
    bak = os.path.join(OUT, '_OLD_bak', f'pipeline_{time.strftime("%Y%m%d_%H%M")}')
    argv = [PY, 'scripts/diag/painting_swap_in.py', '--list', lst,
            '--from', os.path.join(WORK, 'Paintings_v2'), '--bak', bak]
    if hl:
        argv.append('--break-hardlink')
    rc, so, _ = run(argv, timeout=3600, echo=['换入', '备份', 'nlink', '拒绝'])
    return verdict('swap-in', rc == 0, f'painting_swap_in rc={rc}（它自带四道硬检查，退出码可信）'
                                       f'；备份 {bak}；本次{"已" if hl else "无需"}断硬链')


def st_derive(approved):
    if 'derive' not in approved:
        return verdict('derive', True, '未签字 ⇒ 跳过缩略图/索引/部署。要跑请 --approve derive')
    chg = [l.strip() for l in open(os.path.join(WORK, 'changed_paintings.txt'), encoding='utf-8')
           if l.strip()] if os.path.isfile(os.path.join(WORK, 'changed_paintings.txt')) else []
    old_idx = os.path.join(WORK, 'index.prev.json')
    if os.path.isfile(os.path.join(OUT, 'gallery_v2', 'index.json')):
        shutil.copy2(os.path.join(OUT, 'gallery_v2', 'index.json'), old_idx)
    for s in chg:                                     # make_thumbs 存在即 skip ⇒ 必须先删
        for t in (f'{s}.webp', f'{s}_cg.webp'):
            p = os.path.join(OUT, 'gallery_v2', 'thumbs', t)
            if os.path.isfile(p):
                os.remove(p)
    run([PY, 'scripts/make_thumbs.py'], timeout=3600, echo=['完成'])
    rc, so, _ = run([PY, 'scripts/build_gallery_index.py'], timeout=1800, echo=['DONE'])
    new_idx = os.path.join(OUT, 'gallery_v2', 'index.json')
    rc2, so2, _ = run([PY, 'scripts/diag/gallery_index_diff_check.py', old_idx, new_idx],
                      echo=['PASS', 'FAIL', '差异']) if os.path.isfile(old_idx) else (2, '', '')
    run([PY, 'scripts/deploy_gallery.py'], timeout=300)
    rc3, so3, _ = run([PY, 'scripts/deploy_gallery.py', '--check'], timeout=120)
    return verdict('derive', rc == 0 and rc2 == 0 and rc3 == 0,
                   f'index 闸门 {"绿" if rc2 == 0 else "红"}；deploy --check {"4/4" if rc3 == 0 else "断链/漂移"}'
                   + (f'：{(so2.strip().splitlines() or ["?"])[-1][:70]}' if rc2 else ''))


def st_regress(approved):
    rc, so, _ = run([PY, 'scripts/diag/wf16_regression.py', '--skip', 'hit_verify'],
                    timeout=7200, echo=['退出码', '汇总', '通过', '未通过'])
    return verdict('regress', rc == 0, f'WF-16 五件（跳过 25 分钟全库 hit_verify）{"全绿" if rc == 0 else "有红"}')


# ---------------------------------------------------------------- 驱动
STAGES = [
    Stage('preflight', '权威输入 / vendor / 依赖表在位性', 'read', lambda a, f: st_preflight(),
          'check_inputs×2 + fetch_gallery_vendor --check 退出码（这三个可信）'),
    Stage('pull', '模拟器拉新包', 'live', lambda a, f: st_pull(a),
          'diff 只读；sync --apply 写 files/ 26GB ⇒ live'),
    Stage('deps', '重生成官方依赖表', 'live', lambda a, f: st_deps(a),
          '新表必须是旧表超集（丢包即拒），换入前留 prev 副本'),
    Stage('meta', '重建 ship_meta 元数据', 'live', lambda a, f: st_meta(a),
          'ship_meta_authority_diff 绿；⚠️ 索引读死路径，预览必须先换入'),
    Stage('paintings', '静态立绘合成 → 临时区', 'staged', lambda a, f: st_paintings(f, a),
          '数 ✗ 行（该脚本失败仍 exit 0）'),
    Stage('spine', 'Spine 提取 + parts.json → 临时区', 'staged', lambda a, f: st_spine(f, a),
          '每个目录都要有 parts.json'),
    Stage('live2d', 'Live2D 还原 + motion → 临时区', 'staged', lambda a, f: st_live2d(f, a),
          '[SUMMARY] 收尾行 + texorder/tex_completeness 两道真闸门'),
    Stage('audio', 'CV 语音包解码 + 台词表', 'live', lambda a, f: st_audio(a),
          'l2d_voice_inventory 退出码（另两个恒 0 只作参考）'),
    Stage('cg', 'Spine 全屏 CG 导出', 'live', lambda a, f: st_cg(f, a),
          '必须读到「完成N 跳过N 失败N」且失败=0'),
    Stage('review', '出改前|改后总表 + 硬链扫描', 'read', lambda a, f: st_review(),
          '人工看图，机器只负责把表做出来'),
    Stage('swap-in', '备份换入 Paintings_v2', 'live', lambda a, f: st_swapin(a),
          'painting_swap_in 自带四道硬检查，退出码可信'),
    Stage('derive', '缩略图 / 索引 / 部署', 'live', lambda a, f: st_derive(a),
          'gallery_index_diff_check 绿 + deploy --check 4/4 同 inode'),
    Stage('regress', 'WF-16 回归（跳全库 hit_verify）', 'staged', lambda a, f: st_regress(a),
          '串行 runner 退出码'),
]


def cmd_plan(full):
    print(f'\n输入指纹: {fingerprint()}')
    todo = affected_stems(full)
    scope = '**全量**（--full）' if full else (
        f'增量 {len(todo)} 个 stem' if todo else '增量：尚未 detect，先跑 pull 阶段')
    print(f'重跑范围: {scope}')
    print(f'\n{"阶段":11s} {"档":7s} 干什么 / 判据')
    print('-' * 100)
    for s in STAGES:
        print(f'{s.key:11s} {s.tier:7s} {s.title}')
        print(f'{"":11s} {"":7s} 判据: {s.judge_desc}')
    live = [s.key for s in STAGES if s.live]
    print(f'\n要签字的 live 档: {", ".join(live)}')
    print('  py -3 scripts/update_pipeline.py --approve ' + ' '.join(live[:1]) + '   # 逐个点名')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', action='store_true', help='只读：打印阶段表与影响面，不跑任何东西')
    ap.add_argument('--approve', nargs='*', default=[], help='点名放行的 live 阶段')
    ap.add_argument('--full', action='store_true', help='全量重跑（默认只跑 detect 出来的增量）')
    ap.add_argument('--only', default='', help='只跑这些阶段（逗号分隔，按声明顺序）')
    ap.add_argument('--force', action='store_true', help='忽略"本指纹已完成"缓存，staged 阶段重跑')
    a = ap.parse_args()

    if a.plan:
        return cmd_plan(a.full)

    if a.full:
        n = sum(len(f) for _, _, f in os.walk(os.path.join(AB, 'painting')))
        print(f'--full：将重跑全部产物（源包 painting/ 下 {n} 个文件），'
              f'按 WF-15 记录全量耗时以**数十小时**计。')
        if input('确认请输入 FULL：').strip() != 'FULL':
            print('已取消。'); return 1

    os.makedirs(WORK, exist_ok=True)
    flags = set(a.approve) | ({'force'} if a.force else set())
    want = {x.strip() for x in a.only.split(',') if x.strip()}
    fp = fingerprint()
    st = json.load(open(STATE, encoding='utf-8')) if os.path.isfile(STATE) else {}
    if st.get('fingerprint') != fp:
        log(f'输入指纹变了（{st.get("fingerprint", "无记录")} → {fp}），旧状态作废，全部重判')
        st = {'fingerprint': fp, 'done': {}}
    st.setdefault('done', {})

    for s in STAGES:
        if want and s.key not in want:
            continue
        # read 档**永不缓存**：preflight / review 这类安全检查缓存下来 = 从此不再检查，
        # 正是本项目最怕的静默失效。要重跑 staged 档用 --force。
        cacheable = s.tier == 'staged' and 'force' not in flags
        if cacheable and st['done'].get(s.key, {}).get('fingerprint') == fp:
            log(f'⏭  {s.key} 本指纹下已完成（{st["done"][s.key].get("detail", "")[:60]}），跳过；'
                f'要重跑请加 --force')
            RESULTS[s.key] = st['done'][s.key]
            continue
        log(f'== {s.key} —— {s.title} [{"⚠️ live 需签字" if s.live and s.key not in a.approve else s.tier}]')
        try:
            s.fn(set(a.approve), a.full)
        except Exception as e:
            verdict(s.key, False, f'阶段自身抛异常 {type(e).__name__}: {e}')
        # ⚠️ 只缓存**判绿**的阶段：把失败也记成"已完成"，下次跑到这里会被直接跳过，
        #    等于一条永远不再复查的流水线 —— 正是本项目最怕的那类静默失效。
        if RESULTS[s.key]['ok'] and s.tier == 'staged':
            st['done'][s.key] = dict(RESULTS[s.key], fingerprint=fp)
        else:
            st['done'].pop(s.key, None)
        json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        if not RESULTS[s.key]['ok']:
            log(f'!! {s.key} 判红 ⇒ 停在这里，不往下跑（红着继续只会把错的换进去）')
            break

    print('\n===== 汇总 =====')
    for s in STAGES:
        r = RESULTS.get(s.key)
        mark = '—' if not r else ('✅' if r['ok'] else '❌')
        print(f'  {mark} {s.key:11s} {(r or {}).get("detail", "未跑")[:96]}')
    blocked = [s.key for s in STAGES if s.live and s.key not in a.approve and s.key in RESULTS]
    if blocked:
        print(f'\n未签字而跳过的 live 档: {", ".join(blocked)}')
        print(f'  看过 review 的对照表后：py -3 scripts/update_pipeline.py --approve '
              f'{" ".join(blocked[:3])}')
    return 0 if all(r['ok'] for r in RESULTS.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
