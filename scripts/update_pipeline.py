# -*- coding: utf-8 -*-
"""资产更新流水线编排器：把 WF-15 的 11 步变成一条命令跑到「待你确认」，第二条命令签字换入。
界面上的「资产更新控制台」是本文件薄薄一层壳，逻辑都在这。

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
import queue
import re
import shutil
import subprocess
import sys
import threading
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
PROG_RE = re.compile(r'(进度|\d+\s*/\s*\d+|完成|失败|合计|SUMMARY|✓|✗|\[\d+\s*/\s*\d+\])')


def kill_tree(pid, why=''):
    """杀**整棵**进程树。只杀直接子进程的话，起 Chrome 的那些脚本会漏一树 chrome
    在机器上（§50：16 个进程把可用内存压到 1.1GB）。"""
    try:
        subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                       capture_output=True, timeout=60)
    except Exception as e:
        log(f'  ⚠️ taskkill pid={pid} 失败 {type(e).__name__}: {e}（{why}）')


def run(argv, cwd=ROOT, timeout=None, echo=None, beat=2.5):
    """跑一个子命令，返回 (退出码, stdout, stderr)，**并且边跑边把进度吐给自己的 stdout**。

    两件事都是踩出来的，别再改回去：
    ① 原先是 `subprocess.run(capture_output=True)` —— 子进程的输出要等它整个跑完才
       一次性可见，而面板只看得到本进程的 stdout ⇒ 依赖表那 43 分钟里界面一个字都不
       动，看着就是死掉。现在两条流各一个线程读，逐行决定"转出去 / 计入抑制"。
    ② 原先超时由 `subprocess.run(timeout=)` 兜，它只杀直接子进程 ⇒ 起 Chrome 的脚本
       超时会漏整棵树。现在超时走 kill_tree，并照旧抛 TimeoutExpired 让阶段判红。
    """
    p = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, encoding='utf-8',
                         errors='replace', env=ENV, bufsize=1)
    q = queue.Queue()

    def pump(name, stream):
        try:
            for ln in stream:
                q.put((name, ln.rstrip('\r\n')))
        except Exception as e:                       # 流被杀时会抛，属正常收尾
            q.put((name, f'!! 读 {name} 失败 {type(e).__name__}'))
        finally:
            q.put((name, None))

    threading.Thread(target=pump, args=('o', p.stdout), daemon=True).start()
    threading.Thread(target=pump, args=('e', p.stderr), daemon=True).start()
    out, err, done = [], [], 0
    t0 = time.time()
    drop, last = 0, 0.0
    beat_at = t0
    timed_out = False
    while done < 2:
        try:
            name, ln = q.get(timeout=0.4)
        except queue.Empty:
            now = time.time()
            if timeout is not None and now - t0 > timeout:
                timed_out = True
                kill_tree(p.pid, f'{argv[-3:]} 超时 {timeout}s')
                log(f'  ⏱ 超时 {timeout}s ⇒ 已 taskkill 整棵进程树 pid={p.pid}')
                break
            # **静默心跳**：有些被调脚本从头到尾只打一行（或干脆不打），
            # 那 43 分钟里前台就会看着像死掉。没转发行也要定期报"还在跑"。
            if now - beat_at >= 25:
                beat_at = now
                log(f'    · …pid={p.pid} 已 {int(now - t0)} 秒无新输出，仍在跑'
                    f'（{" ".join(str(a) for a in argv[1:3])}）')
            continue
        if ln is None:
            done += 1
            continue
        (out if name == 'o' else err).append(ln)
        hit = bool(echo) and any(k in ln for k in echo)
        now = time.time()
        if hit or (PROG_RE.search(ln) and now - last >= beat):
            if drop:
                log(f'    …（以上抑制 {drop} 行）')
                drop = 0
            log(('    | ' if hit else '    · ') + ln[:180])
            last = now
            beat_at = now
        else:
            drop += 1
    if drop:
        log(f'    …（抑制 {drop} 行）')
    try:
        rc = p.wait(timeout=120)
    except Exception:
        kill_tree(p.pid, '收尾等待超时')
        rc = p.wait()
    if timed_out:
        raise subprocess.TimeoutExpired(argv, timeout)
    return rc, '\n'.join(out), '\n'.join(err)


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
    def __init__(self, key, title, tier, fn, judge_desc, produces=None, needs=None,
                 step=0, writes='', rate=0.0, unit='', est=0.0):
        self.key, self.title, self.tier, self.fn = key, title, tier, fn
        self.judge_desc, self.produces, self.needs = judge_desc, produces or [], needs or []
        self.step, self.writes = step, writes
        # 预计耗时的两种来源，**只允许填量过的数**（没量过就留 0，界面会显示"未知"）：
        #   rate/unit —— 按本次范围线性估算（秒/单位），范围越大越久的那类阶段
        #   est       —— 与范围基本无关的固定耗时（实测秒数）
        self.rate, self.unit, self.est = rate, unit, est

    @property
    def live(self):
        return self.tier == 'live'

    def eta(self, n):
        """→ (秒, 说明) 或 (None, 为什么未知)。"""
        if self.rate and n:
            return self.rate * n, f'按实测 {self.rate:g} 秒/{self.unit} × {n} {self.unit}'
        if self.est:
            return self.est, f'实测约 {self.est:g} 秒'
        return None, '这一步没量过，不猜'



# 阶段属于哪一步、写到哪里，是**流水线自身的事实**，所以定义在这里而不是面板里：
# 面板曾经打算自己抄一份分组表，抄了就会有「加了新阶段、界面把它藏起来」这种漂移。
# step=0 的阶段会被界面显式标成「未归组」并判红，不静默丢弃。
STEPS = {
    1: ('接模拟器', '只读比对设备包 · 拉包需签字'),
    2: ('重新导出', '源包重算 · 默认进暂存区'),
    3: ('看图对比', '出改前|改后总表 · 不写正式区'),
    4: ('签字换入', '暂存区 → Output/ · 重建索引 + 回归'),
}


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
def write_scope(paths, new, changed):
    """把"哪些源包变了"落成交付清单，并当场盖上**当前**输入指纹。

    两份文件必须一起写、一次写 —— 上一版只写了 affected.meta、从没写过 affected.txt，
    于是读侧永远拿到"没有清单"，而下游把那理解成全量（见 scope_state 的注释）。
    """
    os.makedirs(WORK, exist_ok=True)
    ps = sorted(set(x.strip() for x in paths if x.strip()))
    with open(os.path.join(WORK, 'affected.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(ps) + ('\n' if ps else ''))
    with open(os.path.join(WORK, 'affected.meta'), 'w', encoding='utf-8') as f:
        json.dump({'fingerprint': fingerprint(),          # 拉完包要重算：bundles= 变了
                   'at': time.strftime('%Y-%m-%d %H:%M:%S'),
                   'paths': len(ps), 'new': new, 'changed': changed}, f, ensure_ascii=False)
    return len(ps)


def st_pull(approved):
    os.makedirs(WORK, exist_ok=True)
    lst = os.path.join(WORK, 'diff_paths.txt')
    rc, so, se = run([PY, 'scripts/mumu_sync.py', 'diff', '--list-out', lst],
                     timeout=1800, echo=['新增', '大小不一致', '本地独有', '合计', '写出'])
    if rc != 0:
        return verdict('pull', False, f'mumu_sync diff 失败 rc={rc}（模拟器没开？adb 不在 PATH？）')
    txt = so + se
    m_new = re.search(r'新增[^\d]*(\d+)', txt)
    m_dir = re.search(r'大小不一致[^\d]*(\d+)', txt)
    new = int(m_new.group(1)) if m_new else -1
    diff_n = int(m_dir.group(1)) if m_dir else -1
    log(f'  diff: 新增 {new} / 大小不一致 {diff_n}')
    open(os.path.join(WORK, 'sync_diff.txt'), 'w', encoding='utf-8').write(txt)
    paths = [x for x in open(lst, encoding='utf-8')] if os.path.isfile(lst) else []
    if not paths:
        # **0 变更是合法状态，不是错误**：本地已经和设备一致（典型场景就是刚拉完包再点一次检查）。
        # 上一版把它判红 ⇒ 整条线钉死在第 1 步，而且第 1 步刚才是绿的（diff rc=0），红得毫无道理。
        mode, payload = scope_state(False)
        if mode == 'ok':
            n_stem = len(affected_stems(False) or [])
            return verdict('pull', True,
                           f'设备与本地一致（新增 0/变更 0）· 沿用上次 detect 的范围清单：'
                           f'{len(payload)} 个源包 → {n_stem} 个皮肤 stem')
        write_scope([], 0, 0)
        return verdict('pull', True, '设备与本地完全一致（新增 0/变更 0）⇒ 本轮没有要重算的东西；'
                                     '要整库重算请命令行 --full')
    n_scope = write_scope(paths, new, diff_n)
    np_ = len(affected_stems(False) or [])
    if 'pull' not in approved:
        return verdict('pull', True, f'只读到 diff（新增 {new}/变更 {diff_n}）'
                                     f'· 范围清单 {n_scope} 个源包 → {np_} 个皮肤 stem 已落盘'
                                     f'· 未签字，请 --approve pull')
    rc, so2, _ = run([PY, 'scripts/mumu_sync.py', 'sync', '--apply'], timeout=7200,
                     echo=['完成', '失败', '合计', '进度'])
    if rc == 0:
        # 拉完包之后 bundles= 变了 ⇒ 同一份范围清单要重盖指纹，否则下一次跑会把它判成"过期"
        write_scope(paths, new, diff_n)
    return verdict('pull', rc == 0, f'sync --apply rc={rc}'
                                    + (f'· 范围清单已按新指纹重盖（{np_} 个皮肤 stem）' if rc == 0 else ''))



# ---------------------------------------------------------- 3 deps
# 本管线**真正消费**依赖表的目录。判"丢了要不要命"只能按这个来：
# 整表要求"一条都不能少"看着严格，实际会把游戏自己删掉的 4 个 iconframe 条目
# 变成一条永远过不去的红（2026-10-01 首次真跑就撞上），而它跟我们的产物毫无关系。
CONSUMED_TOPS = ('painting', 'paintingface', 'spinepainting', 'live2d', 'cue', 'dependencies')


def deps_classify(old, new):
    """新表 vs 旧表 → (fatal, benign)：丢了**消费范围内**的条目才叫回退。"""
    def tops(k, rec):
        f = str((rec or {}).get('file', '')).replace('\\', '/')
        parts = [x for x in (k.split('/') + f.split('/')) if x and x != '..']
        return {p for p in parts if p in CONSUMED_TOPS}

    fatal, benign = [], []
    for k in old:
        if k not in new:
            (fatal if tops(k, old[k]) else benign).append(k)
    return fatal, benign


def st_deps(approved):
    """重生成官方依赖表。WF-15 第 3 步：最容易漏的一步，漏了新包 PPtr 解析不到。"""
    tmp = os.path.join(WORK, 'dependency_manifest.json')
    rc, _, _ = run([PY, 'scripts/export_dependency_manifest.py', '--out', tmp], timeout=3600)
    if rc or not os.path.isfile(tmp):
        return verdict('deps', False, f'重生成失败 rc={rc}')
    old = json.load(open(os.path.join(OUT, 'dependency_manifest.json'), encoding='utf-8')) \
        if os.path.isfile(os.path.join(OUT, 'dependency_manifest.json')) else {}
    new = json.load(open(tmp, encoding='utf-8'))
    fatal, benign = deps_classify(old, new)
    lost = fatal + benign
    log(f'  依赖表 旧 {len(old)} 条 → 新 {len(new)} 条，丢失 {len(lost)} 条'
        f'（其中本管线消费的 {len(fatal)} 条、不消费的 {len(benign)} 条）')
    if fatal:
        sample = '; '.join(f'{k}→{(old[k] or {}).get("file", "?")}' for k in fatal[:6])
        return verdict('deps', False, f'新表丢了 {len(fatal)} 个**本管线要消费的**旧包，拒绝换入。'
                                      f'丢了这些（最多列 6 个）：{sample}'
                                      f' ⇒ 先确认是本地源包被误删（那要先补包）还是游戏真删了')
    if benign:
        log(f'  · 忽略的丢失条目（本管线不消费）：{", ".join(benign[:6])}'
            + ('…' if len(benign) > 6 else ''))
    if not ('deps' in approved):
        return verdict('deps', True, f'新表已就绪（+{len(new) - len(old)} 条）在临时区'
                                     f'· 未签字，请 --approve deps')
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
        return verdict('meta', True, '新 ship_meta 已产到临时区'
                                     '· 未签字，请 --approve meta')
    bak = os.path.join(WORK, 'ship_meta.prev.json')
    if os.path.isfile(os.path.join(OUT, 'ship_meta.json')):
        shutil.copy2(os.path.join(OUT, 'ship_meta.json'), bak)
    shutil.copy2(os.path.join(tmpdir, 'ship_meta.json'), os.path.join(OUT, 'ship_meta.json'))
    rc2, so2, _ = run([PY, 'scripts/diag/ship_meta_authority_diff.py'], echo=['闸门', '改动'])
    return verdict('meta', rc2 == 0,
                   f'已换入并跑权威闸门 ship_meta_authority_diff → {"绿" if rc2 == 0 else "红"}'
                   + (f'：{(so2.strip().splitlines() or ["?"])[-1][:80]}' if rc2 else ''))


# ---------------------------------------------------------- 5 导出类（全部 staged 到临时区）
# 部件/纹理/投影/表情差分包不是"一张立绘"，口径与 run_v2_full.is_main 保持一致
PART_SUFFIX = ('_rw', '_bj', '_front', '_jz', '_bg', '_shadow', '_shophx', '_mat')


def is_main_painting(fn):
    if fn.endswith('_tex') or fn.endswith('_res'):
        return False
    if '_dark_shadow' in fn or '_face' in fn:
        return False
    if fn == 'mat' or fn.startswith('mat_'):
        return False
    return not any(fn.endswith(s) for s in PART_SUFFIX)


def scope_state(full):
    """这次更新的范围 → (mode, payload)：

      'full'    —— 显式 --full，payload=None
      'ok'      —— payload = 变更源包的相对路径清单（`AssetBundles/<top>/<file>`）
      'missing' —— 从没跑过 detect（或清单没有配套的指纹戳）
      'stale'   —— 清单属于另一批输入

    ⚠️ 这里**绝不把 missing/stale 当成"全量"**。上一版就是这个问题：`affected.txt` 从来
    没有人生成（st_pull 只写了 affected.meta），这个函数一路返回 None，而 None 在下游的
    含义恰好是"全量" ⇒ 所谓增量静默变成全库重跑，`--plan` 还印着"增量：尚未 detect"
    让人以为范围是收窄的。宁可判红停下，也不许偷偷扩大写入面。
    """
    if full:
        return 'full', None
    p = os.path.join(WORK, 'affected.txt')
    mp = os.path.join(WORK, 'affected.meta')
    if not os.path.isfile(p):
        # 只报文件名：别用 os.path.relpath(清单, ROOT)——WORK 落到别的盘符上会抛
        # ValueError: path is on mount 'C:', start on mount 'D:'
        return 'missing', '没有 affected.txt（第 1 步的 detect 还没跑过）'
    if not os.path.isfile(mp):
        return 'missing', 'affected.txt 没有配套的 affected.meta ⇒ 不知道它是哪次 detect 产的'
    try:
        meta = json.load(open(mp, encoding='utf-8'))
    except Exception as e:
        return 'missing', f'affected.meta 读不出来（{type(e).__name__}）'
    fp = fingerprint()
    if meta.get('fingerprint') != fp:
        return 'stale', (f'清单产于 {meta.get("at", "?")}，指纹 '
                         f'{str(meta.get("fingerprint"))[:26]} ≠ 当前 {fp[:26]}')
    return 'ok', [x.strip() for x in open(p, encoding='utf-8') if x.strip()]


def stems_for(top, paths, main_only=False):
    """把路径清单映射成**某一个阶段**能吃的 stem 集合。

    ⚠️ 必须按阶段过滤：立绘脚本收到不属于自己目录的名字会打 ✗，而它的判据正是
    「✗ 行数为 0」⇒ 一份混合清单会让这一步每次判红、并把整条线停在它那里。

    ⚠️ "是不是主皮肤"最终由**磁盘上有没有那个不带后缀的包**裁判，不靠后缀表：
    `run_v2_full` 那份 PART_SUFFIX 漏掉了带编号的部件（实测 `a2_n_bj1_tex` 归并成
    `a2_n_bj1` 后躲过了 `_bj` 检查，而 painting/ 下并没有 `a2_n_bj1` 这个主包 ⇒ 渲染
    报 ✗ ⇒ 整条线判红停住）。后缀只能当快速预筛。
    """
    pre = 'AssetBundles/' + top + '/'
    d = os.path.join(AB, top)
    got = set()
    for rel in paths or []:
        r = rel.replace('\\', '/')
        if not r.startswith(pre):
            continue
        fn = r[len(pre):]
        if '/' in fn:                       # 再往下一层的不属于本阶段的枚举口径
            continue
        stem = fn[:-4] if fn.endswith(('_tex', '_res')) else fn
        if main_only and not is_main_painting(stem):
            continue
        if os.path.isdir(d) and not (os.path.isfile(os.path.join(d, stem))
                                     or os.path.isdir(os.path.join(d, stem))):
            continue                        # 磁盘上没有这个主包 ⇒ 不是本阶段的活
        got.add(stem)
    return sorted(got)



def affected_stems(full):
    """**面板在读这个函数名**（pipeline_panel.scope_safe），别改名。

    返回本次增量涉及的 stem 列表（各阶段去重后的并集）；None = 范围不可用
    （显式 --full，或 detect 没跑 / 已过期）⇒ 面板显示"未算"。
    """
    mode, payload = scope_state(full)
    if mode != 'ok':
        return None
    u = set(stems_for('painting', payload, main_only=True)) | set(stems_for('spinepainting', payload))
    return sorted(u)


def scope_or_stop(key, full, top, main_only=False):
    """导出阶段的统一入口：范围不可用时**判红并停下**，可用时返回 stem 列表。

    返回 (todo, None) 或 (None, 已落好的判红结论)。`todo=None` 表示 --full。
    """
    mode, payload = scope_state(full)
    if mode in ('missing', 'stale'):
        return None, verdict(key, False, f'增量范围不可用：{payload}'
                                        f' ⇒ 拒绝按全量兜底。先看第 1 步的 diff，'
                                        f'真要做全量请命令行 --full')
    if mode == 'full':
        return None, None
    return stems_for(top, payload, main_only=main_only), None


def stale_in(tgt, made, pat='*.png'):
    """临时区里属于**上一批**的产物数 —— review/换入会把它们一起算进去，必须说出口。"""
    n = count(tgt, pat)
    return max(0, n - made) if n > 0 and made is not None else 0




def st_paintings(full, approved):
    todo, stop = scope_or_stop('paintings', full, 'painting', main_only=True)
    if stop is not None:
        return stop
    tgt = os.path.join(WORK, 'Paintings_v2')
    if todo is not None and not todo:
        return verdict('paintings', True, '本次增量没有立绘源包 ⇒ 跳过（临时区未动）')
    os.makedirs(tgt, exist_ok=True)
    if todo is None:
        log('  --full：以 painting/ 源包枚举主皮肤（沿用 run_v2_full 的 is_main 口径）')
        sys.path.insert(0, HERE)
        import run_v2_full as rv
        todo = rv.baseline_targets()
        log(f'  主皮肤 {len(todo)} 个 stem')
    fail = 0
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        rc, so, _ = run([PY, 'scripts/compose_paintings_v2.py'] + batch + ['--out', tgt],
                        timeout=3600, echo=['完成', '✗'])
        fail += len([l for l in so.splitlines() if l.startswith('✗')])
        log(f'  批次进度 {min(i + 50, len(todo))}/{len(todo)} 失败累计 {fail}')
    n = count(tgt, '*.png')
    left = stale_in(tgt, len(todo))
    return verdict('paintings', n > 0 and fail == 0,
                   f'本次渲染 {len(todo)} 个 stem / 临时区共 {n} 张 / 渲染失败 {fail} 个'
                   + (f' · ⚠️ 临时区还留着上一批的 {left} 张，第 3 步对照与第 4 步换入会把它们一起算进去'
                      if left else '')
                   + '（该脚本失败仍 exit 0，判据是数 ✗ 行不是退出码）')


def st_spine(full, approved):
    todo, stop = scope_or_stop('spine', full, 'spinepainting')
    if stop is not None:
        return stop
    tgt = os.path.join(WORK, 'Spine_v2')
    d = os.path.join(AB, 'spinepainting')
    allnames = sorted(f for f in os.listdir(d)
                      if os.path.isfile(os.path.join(d, f)) and not f.endswith('_res'))
    names = allnames if todo is None else [n for n in allnames if n in set(todo)]
    if todo is not None and not names:
        return verdict('spine', True, '本次增量没有 Spine 皮肤包 ⇒ 跳过（临时区未动）')
    os.makedirs(tgt, exist_ok=True)
    fail = []
    for i in range(0, len(names), 25):
        b = names[i:i + 25]
        rc, so, _ = run([PY, 'scripts/extract_spine_v2.py'] + b + ['--out', tgt],
                        timeout=3600, echo=['成功', '失败', '✗'])
        fail += [l.split(':')[0].lstrip('✗ ') for l in so.splitlines() if l.startswith('✗')]
        log(f'  批次进度 {min(i + 25, len(names))}/{len(names)} 失败累计 {len(fail)}')
    rc, so, _ = run([PY, 'scripts/extract_spine_v2.py', '--parts-only']
                    + names + ['--out', tgt], timeout=1800, echo=['成功', '失败'])
    nparts = count(tgt, '*/parts.json')
    left = stale_in(tgt, len(names), '*')
    return verdict('spine', len(fail) == 0 and nparts >= len(names) - 1,
                   f'本次 {len(names)} 个皮肤 / 临时区 {count(tgt, "*")} 个目录 / '
                   f'parts.json {nparts} 份 / 失败 {len(fail)} {fail[:5]}'
                   + (f' · ⚠️ 临时区还留着上一批的 {left} 个目录' if left else ''))



def st_live2d(full, approved):
    """reconstruct → extract_motions → fix_model3 → 三道闸门。写向一律 --out 临时区。

    ⚠️ 两个脚本的 `--out` 都不是可选的：**不带它默认写 `Output/Live2D` 正式区**
    （`extract_motions` 只对 `--all` 做了强制，`--name` 没做）⇒ 这里任何调用都必须带 --out。
    """
    tgt = os.path.join(WORK, 'Live2D')
    todo, stop = scope_or_stop('live2d', full, 'live2d')
    if stop is not None:
        return stop
    if todo is not None and not todo:
        return verdict('live2d', True, '本次增量没有 Live2D 包 ⇒ 跳过（临时区未动）')
    os.makedirs(tgt, exist_ok=True)
    summ = []
    if todo is None:
        run([PY, 'scripts/reconstruct_live2d.py', '--all', '--out', tgt],
            timeout=7200, echo=['完成', '失败', '进度'])
        _, so2, _ = run([PY, 'scripts/extract_motions.py', '--all', '--out', tgt],
                        timeout=7200, echo=['[SUMMARY]', '失败'])
        summ = re.findall(r'\[SUMMARY\] 模型 (\d+)/(\d+) 处理完', so2)
        want = 1
        last = summ[-1] if summ else None
        trunc = (not summ) or (last and last[0] != last[1])
    else:
        for i, m in enumerate(todo):
            run([PY, 'scripts/reconstruct_live2d.py', '--name', m, '--out', tgt],
                timeout=1800, echo=['完成', '失败'])
            _, so2, _ = run([PY, 'scripts/extract_motions.py', '--name', m, '--out', tgt],
                            timeout=1800, echo=['[SUMMARY]', '失败'])
            summ += re.findall(r'\[SUMMARY\] 模型 (\d+)/(\d+) 处理完', so2)
            log(f'  live2d 进度 {i + 1}/{len(todo)}：{m} 已收尾')
        want = len(todo)
        trunc = len(summ) < len(todo)
    if trunc:
        return verdict('live2d', False,
                       f'extract_motions 收尾行 {len(summ)}/{want} 个 ⇒ 判为未完成或被截断'
                       '（该脚本失败仍可能 exit 0，不能拿退出码当通过）')
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
    return verdict('live2d', gates.get('texorder') == 0 and gates.get('tex_completeness') == 0,
                   f'motion 收尾 {len(summ)}/{want}'
                   + (f'（本次增量 {len(todo)} 个模型）' if todo is not None else '（--all）')
                   + f'；闸门 texorder={gates["texorder"]} '
                     f'tex_completeness={gates["tex_completeness"]}（motion_audit 恒 exit 0，只作参考：'
                     f'shell={audit.get("shell", "?")}）')


def st_audio(approved):
    # ⚠️ 这一步**没有暂存通道**：extract_cv_voice 直接写 Output/Audio 与 gallery_v2/skin_voice.json。
    # 上一版收了 approved 参数却没检查它 ⇒ "签字放行"对这一步是空话，跑一次就覆写一次正式区。
    if 'audio' not in approved:
        rc2, so2, _ = run([PY, 'scripts/diag/voice_gap_audit.py'], timeout=1800,
                          echo=['缺口', '合计'])
        rc3, _, _ = run([PY, 'scripts/diag/l2d_voice_inventory.py'], timeout=600, echo=['合计'])
        return verdict('audio', True,
                       '只跑了两道只读语音审计，一个音频包都没解码 · Output/Audio 未动'
                       f'（gap_audit rc={rc2} · inventory rc={rc3}）· 未签字，请 --approve audio')
    rc, so, _ = run([PY, 'scripts/extract_cv_voice.py', '--all', '--skip-done'],
                    timeout=7200, echo=['包', '失败', '合计', '进度'])
    rc2, so2, _ = run([PY, 'scripts/diag/voice_gap_audit.py'], timeout=1800, echo=['缺口', '合计'])
    rc3, _, _ = run([PY, 'scripts/diag/l2d_voice_inventory.py'], timeout=600)
    return verdict('audio', rc3 == 0,
                   f'cv_voice rc={rc}（单包失败不反映到退出码）；voice_gap_audit 恒 exit 0 只作参考；'
                   f'l2d_voice_inventory（可信）rc={rc3}')


def st_cg(full, approved):
    # 同上：CG 导出经画廊服务器**就地覆写 Output/CG_v2**，没有暂存区可退 ⇒ 未签字不许跑。
    if 'cg' not in approved:
        n_live = count(os.path.join(OUT, 'CG_v2'), '*.png')
        return verdict('cg', True,
                       f'正式区现有 {n_live} 张，本次一张都没重导（导出会直接覆写 Output/CG_v2，'
                       f'无暂存通道）· 未签字，请 --approve cg')
    todo, stop = scope_or_stop('cg', full, 'spinepainting')
    if stop is not None:
        return stop
    if todo is not None and not todo:
        return verdict('cg', True, '本次增量没有 Spine 皮肤包 ⇒ 跳过（Output/CG_v2 未动）')
    argv = [PY, 'scripts/diag/run_cg_export.py', '--size', '2400', '--extra', 'animFrame=1', '--redo']
    if todo is not None:
        argv += ['--only', ','.join(todo)]
    rc, so, _ = run(argv, timeout=7200, echo=['全部结束', '完成', '失败'])
    m = re.search(r'完成(\d+) 跳过(\d+) 失败(\d+)', so)
    if not m:
        return verdict('cg', False, '没读到「完成N 跳过N 失败N」汇总行 ⇒ 不能判完成（该脚本超时也 exit 0）')
    ok, skip, bad = map(int, m.groups())
    return verdict('cg', bad == 0 and ok > 0,
                   f'CG 导出 完成{ok} 跳过{skip} 失败{bad}'
                   + (f'（范围 {len(todo)} 个皮肤）' if todo is not None else '（--full 全量）'))



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
        return verdict('swap-in', True, '未签字 ⇒ 跳过，请 --approve swap-in')
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
    return verdict('swap-in', rc == 0, f'painting_swap_in rc={rc}；备份 {bak}；'
                                       f'本次{"已" if hl else "无需"}断硬链')


def st_derive(approved):
    if 'derive' not in approved:
        return verdict('derive', True, '未签字 ⇒ 跳过，请 --approve derive')
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
          'check_inputs×2 + fetch_gallery_vendor --check 退出码',
          step=1, writes='不写', est=2),
    Stage('pull', '模拟器拉新包', 'live', lambda a, f: st_pull(a),
          'diff 只读；sync --apply 写 files/',
          step=1, writes='未签字只写清单 · 签字 files/AssetBundles', est=45),
    Stage('deps', '重生成官方依赖表', 'live', lambda a, f: st_deps(a),
          '新表须为旧表超集，丢包即拒',
          step=2, writes='未签字暂存 · 签字 Output/dependency_manifest.json', est=3),
    Stage('meta', '重建 ship_meta 元数据', 'live', lambda a, f: st_meta(a),
          'ship_meta_authority_diff 绿 · ⚠️ 预览须先换入',
          step=2, writes='未签字暂存 · 签字 Output/ship_meta.json'),
    Stage('paintings', '静态立绘合成 → 临时区', 'staged', lambda a, f: st_paintings(f, a),
          '数 ✗ 行（失败仍 exit 0）',
          step=2, writes='.diag/pipeline/Paintings_v2', rate=1.25, unit='张'),
    Stage('spine', 'Spine 提取 + parts.json → 临时区', 'staged', lambda a, f: st_spine(f, a),
          '每个目录都要有 parts.json',
          step=2, writes='.diag/pipeline/Spine_v2', rate=1.7, unit='个皮肤'),
    Stage('live2d', 'Live2D 还原 + motion → 临时区', 'staged', lambda a, f: st_live2d(f, a),
          '[SUMMARY] 收尾行 + texorder/tex_completeness 闸门',
          step=2, writes='.diag/pipeline/Live2D'),
    Stage('audio', 'CV 语音包解码 + 台词表', 'live', lambda a, f: st_audio(a),
          'l2d_voice_inventory 退出码',
          step=2, writes='Output/Audio（无暂存通道）'),
    Stage('cg', 'Spine 全屏 CG 导出', 'live', lambda a, f: st_cg(f, a),
          '必须读到「完成N 跳过N 失败N」且失败=0',
          step=2, writes='Output/CG_v2（无暂存通道）', rate=1.3, unit='张'),
    Stage('review', '出改前|改后总表 + 硬链扫描', 'read', lambda a, f: st_review(),
          '只出表；看图是人工',
          step=3, writes='.diag/pipeline/*.png 对照表 + 两份清单'),
    Stage('swap-in', '备份换入 Paintings_v2', 'live', lambda a, f: st_swapin(a),
          'painting_swap_in 四道硬检查退出码',
          step=4, writes='Output/Paintings_v2（先备份到 Output/_OLD_bak/pipeline_<日期>/）'),
    Stage('derive', '缩略图 / 索引 / 部署', 'live', lambda a, f: st_derive(a),
          'gallery_index_diff_check 绿 + deploy --check 4/4 同 inode',
          step=4, writes='Output/gallery_v2'),
    Stage('regress', 'WF-16 回归（跳全库 hit_verify）', 'staged', lambda a, f: st_regress(a),
          '串行 runner 退出码',
          step=4, writes='不改产物'),
]


def cmd_plan(full):
    print(f'\n输入指纹: {fingerprint()}')
    mode, payload = scope_state(full)
    if mode == 'full':
        scope = '**全量**（--full）——所有产物重算，Paintings/Spine/Live2D/CG/Audio 全部覆写'
    elif mode == 'ok':
        n_p = len(stems_for('painting', payload, main_only=True))
        n_s = len(stems_for('spinepainting', payload))
        n_l = len(stems_for('live2d', payload))
        scope = (f'增量：{len(payload)} 个变更源包 → 立绘 {n_p} 张 / Spine {n_s} 个皮肤 / '
                 f'Live2D {n_l} 个模型（没点到的不动）')
    else:
        scope = (f'⚠️ 范围不可用（{payload}）⇒ 第 2 步的导出阶段会**判红停下**，'
                 f'不会偷偷按全量跑。要收窄范围先跑第 1 步的 diff；要全量请命令行 --full')
    print(f'重跑范围: {scope}')
    print(f'\n{"步骤":6s} {"阶段":11s} {"档":7s} 干什么 / 判据')
    print('-' * 100)
    for n, (t, d) in STEPS.items():
        print(f'{n} {t} — {d}')
        for s in STAGES:
            if s.step == n:
                print(f'       {s.key:11s} {s.tier:7s} {s.title}')
                print(f'       {"":11s} {"":7s} 判据: {s.judge_desc}')
                if s.writes:
                    print(f'       {"":11s} {"":7s} 写到: {s.writes}')
    orphan = [s.key for s in STAGES if s.step not in STEPS]
    if orphan:
        print(f'\n⚠️ 未归组阶段（新加了阶段但没给 step）: {", ".join(orphan)}')
    live = [s.key for s in STAGES if s.live]
    print(f'\n要签字的 live 档: {", ".join(live)}')
    print('  py -3 scripts/update_pipeline.py --approve ' + ' '.join(live[:1]) + '   # 逐个点名')
    return 0


def fmt_dur(sec):
    sec = int(round(sec or 0))
    if sec < 60:
        return f'{sec} 秒'
    m, s = divmod(sec, 60)
    if m < 60:
        return f'{m} 分 {s:02d} 秒'
    return f'{m // 60} 小时 {m % 60} 分'


# 各阶段"本次要处理多少个单位"从哪来（给预计耗时用）：key → (源包顶层目录, 只要主皮肤)
SCOPE_UNIT = {'paintings': ('painting', True), 'spine': ('spinepainting', False),
              'cg': ('spinepainting', False), 'live2d': ('live2d', False)}


def stage_units(s, full):
    """→ 本次范围里这一步要处理多少个单位；None = 全量或这一步不吃范围。"""
    top = SCOPE_UNIT.get(s.key)
    if not top:
        return None
    mode, payload = scope_state(full)
    if mode != 'ok':
        return None
    return len(stems_for(top[0], payload, main_only=top[1]))


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

    plan = [x for x in STAGES if not want or x.key in want]
    T0 = time.time()
    for i, s in enumerate(plan, 1):
        # read 档**永不缓存**：preflight / review 这类安全检查缓存下来 = 从此不再检查，
        # 正是本项目最怕的静默失效。要重跑 staged 档用 --force。
        cacheable = s.tier == 'staged' and 'force' not in flags
        if cacheable and st['done'].get(s.key, {}).get('fingerprint') == fp:
            log(f'⏭  {s.key} 本指纹下已完成（{st["done"][s.key].get("detail", "")[:60]}），跳过；'
                f'要重跑请加 --force')
            RESULTS[s.key] = st['done'][s.key]
            continue
        # ⚠️ `== {key}` 的先后顺序不能动：面板进度台按 `== (\S+)` 认"现在在跑哪个阶段"。
        units = stage_units(s, a.full)
        sec, why = s.eta(units)
        gate = '⚠️ live 需签字' if s.live and s.key not in a.approve else s.tier
        log(f'== {s.key} —— {s.title} [{i}/{len(plan)}] [{gate}]  '
            + (f'范围 {units} 项 · ' if units is not None else '')
            + (f'预计 ~{fmt_dur(sec)}（{why}）' if sec else f'预计耗时：{why}'))
        t1 = time.time()
        try:
            s.fn(set(a.approve), a.full)
        except Exception as e:
            verdict(s.key, False, f'阶段自身抛异常 {type(e).__name__}: {e}')
        log(f'  ⏱ {s.key} 实际用了 {fmt_dur(time.time() - t1)}，整轮已用 {fmt_dur(time.time() - T0)}')
        # ⚠️ 只缓存**判绿**的暂存阶段当"已完成"：把失败也记成已完成，下次跑到这里会被直接跳过，
        #    等于一条永远不再复查的流水线 —— 正是本项目最怕的那类静默失效。
        if RESULTS[s.key]['ok'] and s.tier == 'staged':
            st['done'][s.key] = dict(RESULTS[s.key], fingerprint=fp)
        else:
            st['done'].pop(s.key, None)
        # verdict 是另一件事：**给界面看的"上次结论"**，13 个阶段全都记。
        # 以前只有 done 那 4 个能被界面读到，其余一律显示"未跑"，看着像整条线没跑过。
        # 它不参与任何跳过判断。
        st.setdefault('verdict', {})[s.key] = dict(RESULTS[s.key])
        json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        if not RESULTS[s.key]['ok']:
            log(f'!! {s.key} 判红 ⇒ 停在这里，不往下跑（红着继续只会把错的换进去）')
            break

    print('\n===== 汇总 =====')
    print(f'  整轮用时 {fmt_dur(time.time() - T0)}')
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
