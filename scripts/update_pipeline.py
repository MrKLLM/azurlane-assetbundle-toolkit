# -*- coding: utf-8 -*-
"""资产更新流水线编排器：把 WF-15 的 11 步变成一条命令跑到「待你确认」，第二条命令签字换入。
界面上的「资产更新控制台」是本文件薄薄一层壳，逻辑都在这。

    py -3 scripts/update_pipeline.py --plan                 # 只读：这次更新会动什么
    py -3 scripts/update_pipeline.py                        # 跑到 review 就停（不碰正式产物）
    py -3 scripts/update_pipeline.py --approve meta live2d  # 签字放行指定 live 阶段
    py -3 scripts/update_pipeline.py --full                 # 显式全量（先报预计耗时再要确认）

三条不可妥协的设计（都是踩出来的，改这个文件前先读）：

1. **退出码不作通过证据。** `export_cue_audio` / `make_thumbs` / `fix_model3` /
   `compose_paintings_v2` / `l2d_motion_audit` /
   `spine_parts_prefab_diff` / `voice_gap_audit` / `run_cg_export` 这 8 个
   **失败时照样 exit 0**。所以每个阶段自带 `judge()`：数汇总行、或跑对应的 gate 脚本。
   没有判据的阶段一律标 `judge=None` 并在报告里写明「未证」，不许算通过。
   （`extract_spine_v2` 原也在此列，2026-10-07 起失败即非零退出；本阶段判据照旧数 `✗` 行，
   因为还要靠那份清单拿失败皮肤名。）
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
sys.path.insert(0, HERE)
import paths as P            # 仓库根的唯一出口；AL_ASSETS_ROOT 可整体换机器
ROOT = P.ROOT
PY = sys.executable
AB = P.AB
OUT = P.OUT
WORK = P.WORK                # 本工具唯一的落盘区
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


def gamecfg_stamp():
    """`inputs/gamecfg` 这一批权威表的指纹：逐个表的 size+mtime，按文件名排序后再哈希。

    为什么必须有它（2026-10-17 23:20，§157）：原指纹只算"源包数 + 依赖表"，
    **不含配置表**。于是 `cfg.publish` 把 `ship_skin_template` 从 2865 行刷成 2871 行之后，
    指纹一个字没变 ⇒ 第 3 步那 7 个阶段的"同指纹已完成"缓存全部命中、全部判绿，
    而它们的产物（`ship_meta.json` / `skin_voice.json` / `Output/Audio`）还是按旧表算的：
    实测 `ship_meta` 与 `skin_voice` 里都没有 `aerjiliya_4`、`cv-90302` 仍是 58/70 条。
    用户看到的是"表同步成功了，但皮肤名字和语音一点没变"。

    用 size+mtime 而不是逐字节哈希：这些表有 5MB 上下，每次轮询都全读一遍太浪费；
    真正会改它们的是 `cfg.publish`，它必然改 mtime。
    """
    d = os.path.join(ROOT, 'inputs', 'gamecfg')
    parts = []
    try:
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.json') or fn == 'MANIFEST.json':
                continue
            p = os.path.join(d, fn)
            stt = os.stat(p)
            parts.append(f'{fn}:{stt.st_size}:{int(stt.st_mtime)}')
    except OSError:
        return 'none'
    return hashlib.md5('|'.join(parts).encode('utf-8')).hexdigest()[:10] if parts else 'none'


def fingerprint(include_cfg=True):
    """这次更新的输入指纹：源包总数 + 依赖表哈希（+ 配置表指纹）。用来判断"同一批输入是否已跑过"。

    ⚠️ 少算一项就会造出"假绿灯"：见 `gamecfg_stamp()` 的注释（§157）。

    `include_cfg=False` 专供 **产出配置表的那几个阶段**（`cfg.*`）用：
    它们的工作**就是**改写 `inputs/gamecfg`，所以不能被"配置表变了"这条信号波及 ——
    否则 `cfg.publish` 刚写完表，指纹当场变掉，下一次跑连它自己和前面三个
    `cfg.*` 一起作废重跑（实测一次 12 分钟白跑）。反过来，下游阶段
    （`deps`/`meta`/`audio`/…）必须用全指纹：表变了它们的产物就该重算。
    """
    n = sum(len(f) for _, _, f in os.walk(AB)) if os.path.isdir(AB) else 0
    dm = os.path.join(OUT, 'dependency_manifest.json')
    h = hashlib.md5(open(dm, 'rb').read()).hexdigest()[:10] if os.path.isfile(dm) else 'none'
    base = f'bundles={n} deps={h}'
    return f'{base} cfg={gamecfg_stamp()}' if include_cfg else base


def stage_fp(s):
    """这个阶段该用哪条指纹判缓存命中（§157）。

    `cfg.*`（产出配置表的四个阶段）用不含 `cfg=` 的那条：它们改写 `inputs/gamecfg`，
    若把 `cfg=` 算进去，`cfg.publish` 刚写完表指纹就变 ⇒ 自己与前面三个阶段
    下一轮全部作废（实测一次 12 分钟白跑）。其余阶段用全指纹。
    """
    return fingerprint(include_cfg=not getattr(s, 'produces_cfg', False))


def stage_fp_by_key(key):
    """按阶段 key 取该阶段的指纹；认不出来的 key 保守用全指纹。"""
    for s in STAGES if 'STAGES' in globals() else ():
        if s.key == key:
            return stage_fp(s)
    return fingerprint()


def base_of(fp):
    """指纹里**不含配置表**的那半（`bundles=N deps=H`）。

    它是"换了一批源包"这个大事件的信号：变了就该保守地全部重判。
    只有 `cfg=` 变（配置表刷新）时**不**整体作废 ——
    逐阶段的指纹比较会自己判出哪些该重跑（§157）。
    """
    return ' '.join((fp or '').split(' ')[:2])


def rejudge_state(st, cur_fp=None):
    """把一份旧状态按**新指纹规则**重新过滤一遍，返回 (新状态, 保留的, 作废的)。

    什么时候需要：指纹的算法本身改了（比如 2026-10-17 23:20 才发现漏了 `inputs/gamecfg`），
    盘上已有状态是按老规则盖章的，直接整份作废会把**刚跑完的阶段也一起清掉**
    —— 那一刻 `cfg.*` 四步刚花了 12 分钟。而它们其实完全有效：
    产出配置表的阶段用的正是不含 `cfg=` 的那条指纹。

    只清"该重跑的那些"，保留的原地不动。这是一次性迁移，
    之后每轮都由 `stage_fp` 比较自然维持。
    """
    fp = cur_fp or fingerprint()
    st = dict(st or {})
    out, keep, drop = {}, [], []
    for k, v in (st.get('verdict') or {}).items():
        (keep if v.get('fingerprint') == stage_fp_by_key(k) else drop).append(k)
        if v.get('fingerprint') == stage_fp_by_key(k):
            out[k] = v
    dkeep, ddrop = [], []
    done = {}
    for k, v in (st.get('done') or {}).items():
        if v.get('fingerprint') == stage_fp_by_key(k):
            done[k] = v
            dkeep.append(k)
        else:
            ddrop.append(k)
    st['fingerprint'] = fp
    st['done'] = done
    st['verdict'] = out
    return st, keep + dkeep, drop + ddrop


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
                 step=0, writes='', rate=0.0, unit='', est=0.0, check=False):
        self.key, self.title, self.tier, self.fn = key, title, tier, fn
        self.judge_desc, self.produces, self.needs = judge_desc, produces or [], needs or []
        self.step, self.writes = step, writes
        # 这个阶段算缓存指纹时**要不要带上 `cfg=`**（§157）。默认带；
        # 只有"产出配置表本身"的 `cfg.*` 阶段要置 False ——
        # 它们的工作就是改写 inputs/gamecfg，被自己的产物判过期就成了永动机。
        self.produces_cfg = key.startswith('cfg.')
        # 预计耗时的两种来源，**只允许填量过的数**（没量过就留 0，界面会显示"未知"）：
        #   rate/unit —— 按本次范围线性估算（秒/单位），范围越大越久的那类阶段
        #   est       —— 与范围基本无关的固定耗时（实测秒数）
        self.rate, self.unit, self.est = rate, unit, est
        # check=True ⇒ 这一步是**验收**，不是生产：结果一律不缓存
        self.check = check

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
    2: ('同步配置表', '解 sharecfg 与 scripts · 重发布权威元数据（写 inputs/ 需签字）'),
    3: ('重新导出', '源包重算 · 默认进暂存区'),
    4: ('看图对比', '出改前|改后总表 · 不写正式区'),
    5: ('签字换入', '暂存区 → Output/ · 重建索引 + 回归'),
}


RESULTS = {}


def verdict(key, ok, detail):
    RESULTS[key] = {'ok': ok, 'detail': detail, 'at': time.strftime('%Y-%m-%d %H:%M:%S')}
    log(f'  {"✅" if ok else "❌"} {key}: {detail}')
    return ok


# ---------------------------------------------------------- 0 配置表链（sharecfg → inputs/gamecfg）
# 2026-10-05 并入。此前台子只管「源包 → 产物」，把 `inputs/` 当成静态前提——
# 而它恰恰会随版本过期：`preflight` 的 sha256 只证明"文件跟上次发布它时一样"，
# **不证明"它跟游戏一样"**（2026-10-04 实测：包是 10-01 拉的、表还是 09-24 那份，
# 于是新自机的皮肤行/台词/CV 全查不到，label 回落 + 语音接不上，见 §82）。
CFG_DIR = os.path.join(ROOT, '.diag', 'sharecfg_re')
CFG_PUBLISH = [('tools/sharecfg_re/42_publish_gamecfg.py', '皮肤表 / 声优 / 台词 / 语音类别'),
               ('tools/sharecfg_re/45_publish_npc_painting.py', '秘书舰 NPC 立绘名'),
               ('tools/sharecfg_re/46_publish_name_code.py', '{namecode} 占位符展开表'),
               ('tools/sharecfg_re/47_publish_npc_voice.py', '秘书舰语音包号与台词正文'),
               ('tools/sharecfg_re/48_publish_meta_group_bridge.py',
                'META 补桥表（有船行、缺皮肤行的实体；立绘取剧情行的 prefab）')]


def cfg_src_newest():
    """配置链三个输入源（sharecfgdata 目录、scripts32/64 两个包）在盘上的最新 mtime。"""
    out = {}
    d = os.path.join(AB, 'sharecfgdata')
    if os.path.isdir(d):
        out['sharecfgdata'] = max([os.path.getmtime(os.path.join(d, f)) for f in os.listdir(d)] or [0])
    for nm in ('scripts32', 'scripts64'):
        p = os.path.join(AB, nm)
        if os.path.isfile(p):
            out[nm] = os.path.getmtime(p)
    return out


def cfg_published_at():
    """`inputs/gamecfg` 上次发布的日期（台账 `landed_at`），取不到返回 ''。"""
    led = os.path.join(ROOT, 'inputs', 'gamecfg', 'MANIFEST.json')
    try:
        return str(json.load(open(led, encoding='utf-8'))['provenance'].get('landed_at') or '')
    except Exception:
        return ''


def cfg_fresh():
    """→ (源最新日期, 发布日, 源是否新于发布)。这是"这次到底有没有新配置可取"的唯一口径。"""
    src = cfg_src_newest()
    if not src:
        return '', '', False
    newest = max(src.values())
    import datetime as _dt
    sd = _dt.date.fromtimestamp(newest).isoformat()
    pub = cfg_published_at()
    return sd, pub, (not pub) or sd > pub


def st_cfg_decrypt(full, approved):
    """34 号：解 `scripts32/64`（www() 按块号 %4 的四种模式）。判据用它自带的已知明文比对。

    ⚠️ 这一步是整条链上**唯一可能因游戏大版本跳变而判红**的地方（密钥/模式排布换了）。
    红了要停下来给人看，不许把"猜出来的明文"写进下游。
    """
    sd, pub, stale = cfg_fresh()
    rc, so, se = run([PY, 'tools/sharecfg_re/34_www_four_modes.py'], timeout=3600,
                     echo=['UnityPy 打开成功', '排列', '失败', '❌'])
    txt = (so or '') + (se or '')
    # 判据必须**逐文件**看：34 是"一个文件一段"地验的，只看"输出里出现过成功"会被
    # 另一个文件的成功骗过去（实测 scripts64 的 .full.ab 打不开、scripts32 成功 ⇒ 判绿）。
    secs = {}
    for chunk in txt.split('\n== ')[1:]:
        secs[chunk.split()[0].strip()] = chunk
    src = cfg_src_newest()
    done, bad = [], []
    for nm in ('scripts64', 'scripts32'):
        ab = os.path.join(CFG_DIR, nm + '.full.ab')
        if not os.path.isfile(ab):
            continue                       # 这个包本来就不在盘上，不算失败
        done.append(nm)
        if 'UnityPy 打开成功' not in secs.get(nm, ''):
            bad.append(f'{nm} 的 UnityPy 复验未过')
        elif os.path.getmtime(ab) < (src.get(nm, 0) - 2):
            bad.append(f'{nm} 的产物比输入包旧（本次没真解它）')
    if not done:
        return verdict('cfg.decrypt', False, f'盘上没有 scripts32/64 任一源包（rc={rc}）'
                                             f' ⇒ 先跑 pull 把配置包拉下来')
    ok = rc == 0 and not bad
    sd, pub, stale = cfg_fresh()
    return verdict('cfg.decrypt', ok,
                   f'逐文件复验 {len(done)} 个（{"、".join(done)}）：'
                   + ('全过' if ok else '红: ' + '; '.join(bad))
                   + (f' | 源 {sd} 比发布日 {pub} 新 ⇒ 这次确实有新配置'
                      if stale else f' | 源 {sd} 不比发布日 {pub} 新（这次更新没带新配置）'))


def st_cfg_lua(full, approved):
    """35 + 41：从解开的 scripts 里导 774 张 lua 表 → `.diag/sharecfg_re/lua_json/`。"""
    rc, so, _ = run([PY, 'tools/sharecfg_re/35_export_sharecfg_lua.py', '--limit', '0'],
                    timeout=3600, echo=['本次导出', '字节码', '容器'])
    if rc:
        return verdict('cfg.lua', False, f'35 号导出失败 rc={rc}')
    rc2, so2, _ = run([PY, 'tools/sharecfg_re/41_export_lua_tables.py', '--all', '--yes'],
                      timeout=3600, echo=['遍历', '桩', 'FAIL', '✗'])
    d = os.path.join(CFG_DIR, 'lua_json')
    n = len([f for f in os.listdir(d) if f.endswith('.json')]) if os.path.isdir(d) else 0
    newest = max([os.path.getmtime(os.path.join(d, f)) for f in os.listdir(d)] or [0]) \
        if os.path.isdir(d) else 0
    ok = rc2 == 0 and n >= 700 and newest >= (max(cfg_src_newest().values() or [0]) - 2)
    return verdict('cfg.lua', ok, f'lua_json {n} 张（基线 772）· 41 号 rc={rc2}'
                                  f'· 落盘比源包新 {"是" if newest and ok else "否"}'
                                  + ('' if n >= 700 else ' ⇒ 表数掉了，多半是容器结构变了，要人看'))


def st_cfg_disk(full, approved):
    """37 号：解析盘上 `sharecfgdata/`（32 张表）→ cfg_json / cfg_json_scalar，并报**行数差分**。

    差分写进 `.diag/pipeline/cfg_delta.json`，供 `meta` 档的权威闸门当期望值——
    否则那条闸门的"条目集合增删必须为 0"会**天生拒绝新角色**（新自机一加行就判红）。

    ⚠️ **两个模式都必须跑，它们写不同的目录，而下游各读一个**：
      · `--all`        → `.diag/sharecfg_re/cfg_json/`（42 号发布 `ship_skin_words` 读它）
      · `--scalar-all` → `.diag/sharecfg_re/cfg_json_scalar/`（42 号发布
        **`ship_skin_template` 皮肤表读它** —— `scripts/skin_table.py` 的 DEV_FILE 源头）
    2026-10-17 实测：只跑 `--all` 时 `cfg_json_scalar` 静静停在 09-25，发布出去的皮肤表
    因此少 6 行（含 `aerjiliya_4`「严厉女仆不严厉」）⇒ 新皮肤没名字、`_3` 档语音一条都解不出来，
    而差分拿"旧的 scalar"比"旧的已发布"得出"新增 0 行"的假绿灯。见 docs/TROUBLESHOOTING.md §155。
    """
    t0 = time.time()
    rc, so, se = run([PY, 'tools/sharecfg_re/37_parse_sharecfgdata.py', '--all', '--yes'],
                     timeout=3600, echo=['帧覆盖', '残差', '✗', '失败'])
    rc2, so2, se2 = run([PY, 'tools/sharecfg_re/37_parse_sharecfgdata.py', '--scalar-all', '--yes'],
                        timeout=3600, echo=['记录', '词表', '含中文行'])
    sc = os.path.join(CFG_DIR, 'cfg_json_scalar')
    dev = os.path.join(sc, 'ship_skin_template.json')
    if rc or rc2 or not os.path.isfile(dev):
        return verdict('cfg.disk', False,
                       f'37 号解析失败（--all rc={rc} / --scalar-all rc={rc2}）'
                       f'或没产出 ship_skin_template.json')
    # 新鲜度闸：发布会读的那个文件必须是**这一轮**写的。旧文件比 t0 还早 = 没刷新，
    # 此时若放行，发布就是把过期皮肤表重新抄一遍（症状：新皮肤无名、无语音映射）。
    if os.path.getmtime(dev) < t0:
        return verdict('cfg.disk', False,
                       f'cfg_json_scalar/ship_skin_template.json 还是 '
                       f'{time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(dev)))} 的'
                       f'（本轮开始于 {time.strftime("%H:%M", time.localtime(t0))}）'
                       f' ⇒ --scalar-all 没写进去，发布会拿旧表，拒')
    try:
        new_rows = json.load(open(dev, encoding='utf-8'))
    except Exception as e:
        return verdict('cfg.disk', False, f'新皮肤表读不出来：{type(e).__name__} {str(e)[:80]}')
    # 内容健全性闸：帧模型解歪时"记录数/残差"照样好看（2026-10-17 实测 2871 条、残差 0、
    # 含中文值 0、字段全是 ship_data 的 smoke/torpedo）⇒ 只认"像皮肤表"的结果。
    probe = [r for r in list(new_rows.values())[:200] if isinstance(r, dict)]
    has_painting = any('painting' in r for r in probe)
    has_cjk = any(isinstance(v, str) and any('一' <= c <= '鿿' for c in v)
                  for r in probe for v in r.values())
    if not probe or not has_painting or not has_cjk:
        return verdict('cfg.disk', False,
                       f'解析结果不像皮肤表（{len(new_rows)} 行，painting={has_painting}，'
                       f'中文={has_cjk}） ⇒ 容器格式可能变了，别拿它发布，先看 37 号')
    pub_p = os.path.join(ROOT, 'inputs', 'gamecfg', 'ship_skin_template.json')
    old_rows = json.load(open(pub_p, encoding='utf-8')) if os.path.isfile(pub_p) else {}
    added = sorted(set(map(str, new_rows)) - set(map(str, old_rows)))
    lost = sorted(set(map(str, old_rows)) - set(map(str, new_rows)))
    delta = {'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'rows_new': len(new_rows),
             'rows_pub': len(old_rows), 'added': len(added), 'lost': len(lost),
             'added_sample': added[:12]}
    os.makedirs(WORK, exist_ok=True)
    json.dump(delta, open(os.path.join(WORK, 'cfg_delta.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    n_tab = len([f for f in os.listdir(sc) if f.endswith('.json')]) if os.path.isdir(sc) else 0
    ok = n_tab >= 30 and not lost
    return verdict('cfg.disk', ok,
                   f'磁盘侧 {n_tab} 张表（期望 32）· 皮肤行 {delta["rows_pub"]} → {delta["rows_new"]}'
                   f'，**新增 {delta["added"]} 行**{("：" + ", ".join(added[:6])) if added else ""}'
                   + (f'｜**丢掉 {len(lost)} 行**（{", ".join(lost[:4])}）——解析或发布漏了，拒'
                      if lost else '')
                   + (' ⇒ 发布后 meta 才会给这些皮肤起名、语音档位才解得出来' if added
                      else ' ⇒ 这次更新没带新皮肤'))


def st_cfg_publish(approved):
    """42/45/46/47：把解出来的表发布成 `inputs/gamecfg/*.json` + 台账。**live 档**（写权威输入）。

    未签字时只跑各脚本的 `--check`（只读断言），签字后才真写盘——`inputs/` 是整条线的
    唯一起点，写坏了下游全部跟着错，所以这一档的确认权必须留在人那里。

    ⚠️ 发布前先查**解析产物的新鲜度**：42 号读的皮肤表来自
    `.diag/sharecfg_re/cfg_json_scalar/ship_skin_template.json`，它必须比源包
    `sharecfgdata/ship_skin_template` 新。2026-10-17 实测：只跑 `--all` 不跑 `--scalar-all`
    时这个文件停在 09-25，发布只是把过期表重新抄一遍，`--check` 全绿也发现不了（§155）。
    `cfg.disk` 又是 staged 档、会被"同指纹已完成"缓存跳过 ⇒ 这一道闸必须长在发布档上。
    """
    mode = 'publish' if 'cfg.publish' in approved else 'check'
    src = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata', 'ship_skin_template')
    dev = os.path.join(CFG_DIR, 'cfg_json_scalar', 'ship_skin_template.json')
    if not os.path.isfile(dev):
        return verdict('cfg.publish', False,
                       f'没有解析产物 {os.path.relpath(dev, ROOT)} ⇒ 先跑 cfg.disk，'
                       f'否则发布的是 inputs/ 里的旧表')
    if os.path.isfile(src) and os.path.getmtime(dev) < os.path.getmtime(src):
        return verdict('cfg.publish', False,
                       '皮肤表解析产物比源包旧（%s < %s） ⇒ 先重跑 cfg.disk'
                       '（勾上「缓存：已绕过」，它现在会同时跑 --scalar-all），'
                       '否则这一发布只是把过期表重新抄一遍'
                       % (time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(dev))),
                          time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(src)))))
    bad = []
    for script, what in CFG_PUBLISH:
        cmd = [PY, script] + ([] if mode == 'publish' else ['--check'])
        rc, so, se = run(cmd, timeout=1800, echo=['闸门', '绿', '红', '✗', 'WRITE'])
        tail = ((so or '') + (se or '')).strip().splitlines()
        print('  %s %-14s %s' % ('✅' if rc == 0 else '❌', os.path.basename(script)[:12],
                                 (tail[-1][:78] if tail else f'rc={rc}')))
        if rc:
            bad.append(f'{os.path.basename(script)}(rc={rc})')
    rc2, so2, _ = run([PY, 'scripts/diag/check_inputs.py', 'gamecfg'], timeout=300,
                      echo=['PASS', 'FAIL', '漂移'])
    if mode == 'check':
        return verdict('cfg.publish', not bad,
                       f'未签字 ⇒ 只跑 4 个发布脚本的 --check（只读断言）：'
                       f'{"全过" if not bad else "红: " + "; ".join(bad)}'
                       f' ⇒ 看过差分再 --approve cfg.publish')
    return verdict('cfg.publish', (not bad) and rc2 == 0,
                   f'已发布 4 张表；台账校验 check_inputs {"绿" if rc2 == 0 else "红"}'
                   + (f'：{(so2 or "").strip().splitlines()[-1][:70]}' if rc2 else '')
                   + (f'｜红项 {"; ".join(bad)}' if bad else ''))


# ---------------------------------------------------------- 1 preflight
def st_preflight():
    bad = []
    for led in ('azdata', 'gamecfg'):
        rc, so, se = run([PY, 'scripts/diag/check_inputs.py', led])
        log(f'  权威输入台账 {led}: {"PASS" if rc == 0 else "FAIL"}')
        if rc:
            bad.append(f'{led}({(so or se).strip().splitlines()[-1][:70] if (so or se).strip() else "rc"}={rc})')
    # **新鲜度**：台账 sha256 只证明"文件跟上次发布时一样"，不证明"它跟游戏一样"。
    # 源包比发布日新 ⇒ 配置链必须重跑，否则 meta 档会拿旧表重刷一遍（§82 那个失效模式）。
    sd, pub, stale = cfg_fresh()
    log(f'  配置表新鲜度: 盘上配置源最新 {sd or "?"} / inputs/gamecfg 发布 {pub or "?"}'
        f' ⇒ {"⚠️ 源比表新，先跑 cfg 四档" if stale else "表不比源旧"}')
    if stale:
        bad.append(f'配置表过期（源 {sd} > 发布 {pub}）⇒ 跑 cfg.decrypt/cfg.lua/cfg.disk/cfg.publish')
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

    ⚠️ **空清单不得覆盖非空清单**。2026-10-01 15:53 用户那次运行就是这么把 1154 条真范围
    冲成 0 条的：包已经拉完 ⇒ diff 报 0 变更，同时依赖表刚换入 ⇒ 整条指纹变了 ⇒ 旧清单被判过期
    ⇒ 走进"写空"分支。之后所有导出阶段都以为"增量里没有东西"，14 张新立绘静默消失。
    现在：旧的先留 `affected.prev.txt`，空结果一律沿用旧清单，只重盖指纹戳。
    """
    os.makedirs(WORK, exist_ok=True)
    ps = sorted(set(x.strip() for x in paths if x.strip()))
    cur = os.path.join(WORK, 'affected.txt')
    had = [x.strip() for x in open(cur, encoding='utf-8') if x.strip()] if os.path.isfile(cur) else []
    kept = False
    if not ps and had:
        ps, kept = had, True
    elif had and had != ps:
        shutil.copy2(cur, os.path.join(WORK, 'affected.prev.txt'))
    with open(cur, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(ps) + ('\n' if ps else ''))
    with open(os.path.join(WORK, 'affected.meta'), 'w', encoding='utf-8') as f:
        json.dump({'fingerprint': fingerprint(),          # 拉完包要重算：bundles= 变了
                   'at': time.strftime('%Y-%m-%d %H:%M:%S'),
                   'paths': len(ps), 'new': new, 'changed': changed,
                   'kept_from_prev': kept}, f, ensure_ascii=False)
    return len(ps)



def st_pull(approved):
    os.makedirs(WORK, exist_ok=True)
    lst = os.path.join(WORK, 'diff_paths.txt')
    rc, so, se = run([PY, 'scripts/mumu_sync.py', 'diff', '--list-out', lst],
                     timeout=1800, echo=['新增', '大小不一致', '本地独有', '合计', '写出'])
    if rc != 0:
        txt0 = (so + se).strip()
        why = txt0.splitlines()[-1][:120] if txt0 else f'rc={rc}'
        dev = any(k in txt0 for k in ('连不上模拟器', 'ls 顶层失败', 'adb', 'offline', 'device'))
        # 设备不可达 ≠ 这轮不能跑：包已经在本地、范围清单还有效时，硬卡在第 1 步
        # 只会让人以为整条线坏了（2026-10-01 实测：用户同步完之后关掉了模拟器）。
        mode, payload = scope_state(False)
        if dev and mode == 'ok':
            n_stem = len(affected_stems(False) or [])
            return verdict('pull', True, f'设备不可达（{why}）· 但源包已在本地、范围清单仍有效'
                                         f'（{len(payload)} 个源包 → {n_stem} 个皮肤 stem）'
                                         f' ⇒ 沿用清单继续，本轮不需要拉包')
        return verdict('pull', False, f'mumu_sync diff 失败：{why}'
                                      f' ⇒ 要拉新包就得先开模拟器；源包若已在本地，'
                                      f'这份范围清单不可用（{payload}），需要一次能连上设备的 diff')
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
        n_stem = len(affected_stems(False) or [])
        if mode == 'ok' and n_stem:
            return verdict('pull', True,
                           f'设备与本地一致（新增 0/变更 0）· 沿用上次 detect 的范围清单：'
                           f'{len(payload)} 个源包 → {n_stem} 个皮肤 stem')
        write_scope([], 0, 0)          # 非空的旧清单不会被它冲掉，见 write_scope 的注释
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
    # 期望新增数取自 `cfg.disk` 报的差分：那条闸门的"条目增删必须为 0"**天生拒绝新角色**——
    # 游戏新出一艘自机就会加行，硬要求 0 等于把"更新"这件事本身判成回退（2026-10-05 修）。
    delta = 0
    dp = os.path.join(WORK, 'cfg_delta.json')
    if os.path.isfile(dp):
        try:
            delta = int(json.load(open(dp, encoding='utf-8')).get('added') or 0)
        except Exception:
            delta = 0
    rc2, so2, _ = run([PY, 'scripts/diag/ship_meta_authority_diff.py',
                       '--expect-added', str(delta)], echo=['闸门', '改动'])
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


def bundles_of(fp):
    """从输入指纹里取出**源包状态**那半（`bundles=92679`）。

    范围清单的新鲜度只能看这一半。原因（2026-10-01 真跑撞出来的）：正常顺序是
    「拉包 → 换入依赖表 → 跑导出」，而 `deps=` 那半会在换入依赖表的那一刻变掉
    ⇒ 拿整条指纹判过期，等于**每次正常运行都把刚写好的范围清单打成废纸**，
    于是所有导出阶段看到"增量里没有东西"，静默跳过 —— 14 张新立绘就这么没了。
    """
    return (fp or '').split(' ')[0]


def scope_stamp():
    """当前范围清单的身份（内容哈希）。清单换了 = 上一批"跳过/无事可做"的结论一律作废。

    只比输入指纹不够：2026-10-01 实测，清单被冲空之后跑出来的 `paintings: 本次增量没有立绘源包
    ⇒ 跳过` 也记在**同一个输入指纹**下；清单复原之后，界面照搬那条结论就还是绿的。
    """
    p = os.path.join(WORK, 'affected.txt')
    try:
        return hashlib.md5(open(p, 'rb').read()).hexdigest()[:10]
    except OSError:
        return 'none'


def scope_state(full, fp=None):
    """这次更新的范围 → (mode, payload)：

      'full'    —— 显式 --full，payload=None
      'ok'      —— payload = 变更源包的相对路径清单（`AssetBundles/<top>/<file>`）
      'missing' —— 从没跑过 detect（或清单没有配套的指纹戳）
      'stale'   —— 清单属于**另一批源包**（只比 `bundles=`，见 `bundles_of` 的注释）

    ⚠️ 这里**绝不把 missing/stale 当成"全量"**。上一版就是这个问题：`affected.txt` 从来
    没有人生成（st_pull 只写了 affected.meta），这个函数一路返回 None，而 None 在下游的
    含义恰好是"全量" ⇒ 所谓增量静默变成全库重跑，`--plan` 还印着"增量：尚未 detect"
    让人以为范围是收窄的。宁可判红停下，也不许偷偷扩大写入面。

    `fp` 让调用方把**已经算好的**输入指纹传进来：算一次要 walk 9 万多个源包，面板一次
    `/api/state` 里以前各处各算 4~6 遍，实测那一拍 5.8 秒 ⇒ 前端轮询超时，看着就是进度不动。
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
    fp = fp or fingerprint()
    if bundles_of(meta.get('fingerprint')) != bundles_of(fp):
        return 'stale', (f'清单产于 {meta.get("at", "?")}，源包数 '
                         f'{bundles_of(meta.get("fingerprint"))} ≠ 当前 {bundles_of(fp)}')
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



def affected_stems(full, fp=None):
    """**面板在读这个函数名**（pipeline_panel.scope_safe），别改名。

    返回本次增量涉及的 stem 列表（各阶段去重后的并集）；None = 范围不可用
    （显式 --full，或 detect 没跑 / 已过期）⇒ 面板显示"未算"。
    """
    mode, payload = scope_state(full, fp)
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
    # 动作导出配方必须**显式钉住并回读打印**：默认值虽然已是生产配方（2026-10-17 改），
    # 但这里再钉一次，防止以后有人改默认值让增量重跑悄悄产出 118 条曲线的 motion。
    ENV['L2D_MOTION_LINEAR'] = '1'
    ENV['L2D_MOTION_EMIT_CONST'] = '1'
    log('  live2d 动作配方: L2D_MOTION_LINEAR=1 + L2D_MOTION_EMIT_CONST=1（与盘上 269 模型一致）')
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
    # 降级台账**先跑**：它是只读的，且是"这一步到底该不该签字"的判据之一
    # （新增降级 = 游戏改了形状，这时候签 --approve audio 只会把猜的结果写进正式区）。
    rcg, sog, _ = run([PY, 'scripts/diag/check_degradation.py'], timeout=1800,
                      echo=['存量', '新增', 'OK', 'FAIL'])
    deg_line = next((l.strip() for l in (sog or '').splitlines()
                     if 'OK' in l or 'FAIL' in l), '降级台账没给结论（rc=%s）' % rcg)
    if 'audio' not in approved:
        rc2, so2, _ = run([PY, 'scripts/diag/voice_gap_audit.py'], timeout=1800,
                          echo=['缺口', '合计'])
        rc3, _, _ = run([PY, 'scripts/diag/l2d_voice_inventory.py'], timeout=600, echo=['合计'])
        # ⚠️ `voice_gap_audit` 的 rc **必须被消费**。它设计上恒 exit 0（结论是分类清单不是判据），
        # 所以 rc≠0 只有一个意思：**它自己崩了**。2026-10-03 实测这条被无视了一整天——
        # 换三元组时把它弄坏（ValueError），阶段结论照绿。恒 0 的辅助脚本一旦不看退出码，
        # 坏了也没有任何地方会变红，等于把"有没有坏"变成只有人工翻日志才知道。
        return verdict('audio', rcg == 0 and rc2 == 0 and rc3 == 0,
                       '只跑了两道只读语音审计 + 降级台账，一个音频包都没解码 · Output/Audio 未动'
                       f'（gap_audit rc={rc2} · inventory rc={rc3} · {deg_line}）'
                       + ('' if rcg == 0 else ' · 有新增降级，先判断再签字')
                       + ('' if rc2 == 0 else ' · gap_audit 崩了（它恒 exit 0，非 0 即故障）')
                       + ' · 未签字，请 --approve audio')
    rc, so, _ = run([PY, 'scripts/extract_cv_voice.py', '--all', '--skip-done'],
                    timeout=7200, echo=['包', '失败', '合计', '进度'])
    rc2, so2, _ = run([PY, 'scripts/diag/voice_gap_audit.py'], timeout=1800, echo=['缺口', '合计'])
    rc3, _, _ = run([PY, 'scripts/diag/l2d_voice_inventory.py'], timeout=600)
    return verdict('audio', rc3 == 0 and rcg == 0 and rc2 == 0,
                   f'cv_voice rc={rc}（单包失败不反映到退出码）；voice_gap_audit rc={rc2}'
                   f'（恒 exit 0，非 0 = 它自己崩了）；l2d_voice_inventory（可信）rc={rc3}；{deg_line}')


def st_bg_export(approved, full):
    """源包 → Output/Raw 的背景图重导出（含新活动新增的 bg 包）。

    参数表
    ------
    approved : set  已签字放行的阶段 key 集合
    full     : bool 是否 --full（本阶段不区分增量：背景导出本来就是全目录扫）

    为什么单独一步、且不做增量裁剪
    ------------------------------
    `export_assets.py --target bg` 扫的是 9 个背景子目录（bg/commonbg/loadingbg/…），
    一个包里可能有多张同名纹理、还要做同名让位，和"按皮肤名增量"不是一套模型。
    硬接进立绘范围会漏图，所以只在新版本或明确要刷新背景时整段跑。

    ⚠️ 判据不能用退出码：`export_assets.py` 在部分失败时仍然 return 0，
       只看 `ExportStats.summary()` 打出的「失败: N」——必须读到且为 0。
    """
    if 'bg' not in approved:
        n_now = count(os.path.join(OUT, 'Raw', 'bg'), '*.png')
        return verdict('bg', True,
                       f'未签字 ⇒ 跳过（直接覆写 Output/Raw，无暂存通道）；'
                       f'现有 bg/ {n_now} 张 · 签字请 --approve bg')
    rc, so, se = run([PY, 'scripts/export_assets.py', '--target', 'bg'],
                     timeout=10800, echo=['导出完成', '成功:', '失败:', '耗时:'])
    txt = so + se
    m_bad = re.search(r'失败:\s*(\d+)', txt)
    if not m_bad:
        return verdict('bg', False,
                       '没读到「失败: N」汇总行 ⇒ 不能判完成（该脚本失败也 exit 0）')
    m_ok = re.search(r'成功:\s*(\d+)', txt)
    good, bad = (int(m_ok.group(1)) if m_ok else 0), int(m_bad.group(1))
    return verdict('bg', rc == 0 and bad == 0 and good > 0,
                   f'背景导出 成功{good} 失败{bad}')


def st_labels(approved, full):
    """重建「背景词根标签 + 音乐专辑索引」，并输出新增/未命名的漂移报告。

    参数表
    ------
    approved : set  已签字放行的阶段 key 集合；不在集合里只跑 --check
    full     : bool 是否 --full（本阶段与范围无关）

    未签字为什么只跑 --check
    ------------------------
    51 发布器会写 `inputs/gamecfg/bg_series_labels.json`，属于 inputs/ 权威输入区；
    按项目规则，写 inputs/ 必须先签字。--check 只跑断言、不写任何产物。
    """
    unlocked = 'labels' in approved
    argv = [PY, 'scripts/rebuild_labels.py'] + ([] if unlocked else ['--check'])
    rc, so, se = run(argv, timeout=3600,
                     echo=['标签漂移报告', '新增词根', '未命名', '新增曲目', '新增专辑',
                           '结论', '闸门：', '[WRITE]', '[FAIL]'])
    txt = so + se
    if rc != 0:
        bad = [l.strip()[:100] for l in txt.splitlines()
               if '[FAIL]' in l or '✗' in l][:2]
        return verdict('labels', False,
                       '重建失败：' + ('；'.join(bad) or '见日志末尾'))
    m_un = re.search(r'当前未命名词根 (\d+) 个', txt)
    m_tr = re.search(r'曲目 (\d+) 首', txt)
    unnamed = m_un.group(1) if m_un else '?'
    tracks = m_tr.group(1) if m_tr else '?'
    if not unlocked:
        return verdict('labels', True,
                       f'未签字 ⇒ 只跑 --check（未写产物）：未命名词根 {unnamed} 个 / '
                       f'曲目 {tracks} 首 · 签字请 --approve labels')
    m_new = re.search(r'本次新增词根 (\d+) 个', txt)
    new_n = m_new.group(1) if m_new else '0'
    return verdict('labels', True,
                   f'标签已重建：新增词根 {new_n} 个（未命名 {unnamed} 个）/ 曲目 {tracks} 首')


def st_bgm(approved, full):
    """BGM 补导：新 cue 包 → FLAC → bgm.json。

    参数表
    ------
    approved : set  已签字放行的阶段 key 集合；不在集合里只跑 --check
    full     : bool 是否 --full（本阶段与范围无关）

    ⚠️ 覆盖边界：只处理热更 `files/AssetBundles/cue/` 里的曲目。
       烤在 `base.apk` 基础层的曲子（如 8 首开服 BGM）不在热更清单里，
       要单独从模拟器 `assets/AssetBundles/cue/` 提取后放进 cue/，再跑本阶段。
    """
    unlocked = 'bgm' in approved
    argv = [PY, 'scripts/rebuild_bgm_library.py'] + ([] if unlocked else ['--check'])
    rc, so, se = run(argv, timeout=7200,
                     echo=['cue/bgm', '缺 ', '完成 ', '成功 ', '失败 ', '官方中文名',
                           '完成：', '[FAIL]'])
    txt = so + se
    if rc != 0:
        bad = [l.strip()[:100] for l in txt.splitlines() if '[FAIL]' in l][:2]
        return verdict('bgm', False,
                       '音乐补导失败：' + ('；'.join(bad) or '见日志末尾'))
    m = re.search(r'(?:缺|还有)\s*(\d+)', txt)
    n = m.group(1) if m else '?'
    if not unlocked:
        return verdict('bgm', True,
                       f'未签字 ⇒ 只跑 --check（未写产物）：待解码 {n} 首 · 签字请 --approve bgm')
    return verdict('bgm', True, f'音乐库已重建：待解码 {n} 首已处理 · bgm.json 已更新')


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
    chg, new_only, todo = [], [], []
    p_new = os.path.join(WORK, 'Paintings_v2')
    live_p = os.path.join(OUT, 'Paintings_v2')
    if os.path.isdir(p_new) and os.path.isdir(live_p):
        news = [os.path.basename(x)[:-4] for x in glob.glob(os.path.join(p_new, '*.png'))]
        same_n = 0
        for s in news:
            sp, lp = os.path.join(p_new, s + '.png'), os.path.join(live_p, s + '.png')
            if not os.path.isfile(lp):
                new_only.append(s)          # 线上根本没有 = 必须换入的新皮肤
                continue
            if hashlib.md5(open(sp, 'rb').read()).digest() != hashlib.md5(open(lp, 'rb').read()).digest():
                chg.append(s)
            else:
                same_n += 1
        # ⚠️ 换入清单以前只收"线上已有且内容不同"的 ⇒ 新增皮肤永远进不了清单：
        # review 报「与线上不同 0 张」、swap-in 报「清单为空」，用户跑完更新却什么都没有。
        todo = sorted(set(new_only) | set(chg))
        open(os.path.join(WORK, 'changed_paintings.txt'), 'w', encoding='utf-8') \
            .write('\n'.join(todo))
        open(os.path.join(WORK, 'new_paintings.txt'), 'w', encoding='utf-8') \
            .write('\n'.join(sorted(new_only)))
        lines.append(f'立绘：临时区 {len(news)} 张 · 线上新增 {len(new_only)} · 内容有变 {len(chg)}'
                     f' · 逐字节相同 {same_n}')
        if todo:
            run([PY, 'scripts/diag/make_pair_sheet.py', '--old', live_p, '--new', p_new,
                 '--names', ','.join(todo[:12]), '--out', os.path.join(WORK, 'sheet_paintings.png'),
                 '--cell', '260'], timeout=1800, echo=['成对', '已写出', '线上没有'])
    else:
        lines.append(f'立绘：暂存区/正式区缺一侧（暂存 {os.path.isdir(p_new)} · 正式 {os.path.isdir(live_p)}）'
                     f'⇒ 先跑第 2 步的重导')
    hl = scan_hardlinks([os.path.join(live_p, s + '.png') for s in todo])
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
    stems = [l.strip() for l in open(lst, encoding='utf-8') if l.strip()]
    hl = [l for l in open(os.path.join(WORK, 'hardlinks.txt'), encoding='utf-8') if l.strip()]
    bak = os.path.join(OUT, '_OLD_bak', f'pipeline_{time.strftime("%Y%m%d_%H%M")}')
    argv = [PY, 'scripts/diag/painting_swap_in.py', '--list', lst,
            '--from', os.path.join(WORK, 'Paintings_v2'), '--bak', bak]
    if hl:
        argv.append('--break-hardlink')
    rc, so, _ = run(argv, timeout=3600, echo=['换入', '备份', 'nlink', '拒绝'])
    ok = rc == 0
    note = ''
    if ok and stems:
        # 换进正式区的那一刻才是"已还原"成立的时刻 —— 溯源台账必须在此刻记
        # （源包哈希与产物一一对上，将来 prune 才有依据判断"这个源包删了也不丢东西"）
        _, sor, _ = run([PY, 'scripts/asset_ledger.py', 'record', '--type', 'painting',
                         '--stems', ','.join(stems)], timeout=1800, echo=['溯源已记'])
        note = '；台账：' + ((sor or '').strip().splitlines() or ['没输出'])[-1][:70]
    return verdict('swap-in', ok, f'painting_swap_in rc={rc}；备份 {bak}；'
                                  f'本次{"已" if hl else "无需"}断硬链{note}')



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
    rc, so, se = run([PY, 'scripts/diag/wf16_regression.py', '--skip', 'hit_verify'],
                     timeout=7200, echo=['退出码', '汇总', '通过', '未通过', '不可达', '先起'])
    txt = so + se
    # 只报"有红"等于没报（2026-10-01 用户就是被这条卡住的：红的真因是 8777 画廊服务器没起，
    # 属于**前置环境缺失**，不是产物回归——两者的下一步完全不同）。
    env = [l.strip()[:120] for l in txt.splitlines()
           if any(k in l for k in ('不可达', '先起服务器', '连不上', '拒绝'))]
    bad = [l.strip()[:120] for l in txt.splitlines()
           if any(k in l for k in ('未通过', 'FAIL', '✗', '红'))]
    if rc and env:
        return verdict('regress', False, '前置环境没满足，不是产物回归：' + env[0]
                                       + ' ⇒ 先起画廊服务器（8777）再跑这一步')
    return verdict('regress', rc == 0,
                   'WF-16 五件（跳过 25 分钟全库 hit_verify）'
                   + ('全绿' if rc == 0 else '有红：' + ('；'.join(bad[:3]) or '见日志末尾')))



# ---------------------------------------------------------------- 驱动
STAGES = [
    Stage('preflight', '权威输入 / vendor / 依赖表在位性', 'read', lambda a, f: st_preflight(),
          'check_inputs×2 + fetch_gallery_vendor --check 退出码',
          step=1, writes='不写', est=2),
    Stage('pull', '模拟器拉新包', 'live', lambda a, f: st_pull(a),
          'diff 只读；sync --apply 写 files/',
          step=1, writes='未签字只写清单 · 签字 files/AssetBundles', est=45),
    Stage('cfg.decrypt', '解 scripts32/64（www 四模式）', 'staged', lambda a, f: st_cfg_decrypt(f, a),
          '自带四组 64 位已知明文比对 + UnityPy 复验 + 产物须比输入新',
          step=2, writes='.diag/sharecfg_re/*.full.ab', est=120),
    Stage('cfg.lua', '导出 774 张 lua 表 → JSON', 'staged', lambda a, f: st_cfg_lua(f, a),
          'lua_json ≥700 张 · 41 号三条判据（遍历到文件末/记录数/高字节）',
          step=2, writes='.diag/sharecfg_re/lua_json', est=180),
    Stage('cfg.disk', '解析 sharecfgdata 32 张表 + 报行数差分', 'staged', lambda a, f: st_cfg_disk(f, a),
          '32 张齐 · 皮肤表必须这一轮新解且有 painting/中文 · 行数增量写进 cfg_delta.json 供 meta 当期望值',
          step=2, writes='.diag/sharecfg_re/cfg_json* + .diag/pipeline/cfg_delta.json', est=420),
    Stage('cfg.publish', '发布 inputs/gamecfg（4 张表 + 台账）', 'live', lambda a, f: st_cfg_publish(a),
          '4 个发布脚本闸门全绿 + check_inputs gamecfg 绿',
          step=2, writes='未签字只跑 --check · 签字 inputs/gamecfg/*.json + MANIFEST.json', est=25),
    Stage('deps', '重生成官方依赖表', 'live', lambda a, f: st_deps(a),
          '新表须为旧表超集，丢包即拒',
          step=3, writes='未签字暂存 · 签字 Output/dependency_manifest.json', est=3),
    Stage('meta', '重建 ship_meta 元数据', 'live', lambda a, f: st_meta(a),
          'ship_meta_authority_diff 绿 · ⚠️ 预览须先换入',
          step=3, writes='未签字暂存 · 签字 Output/ship_meta.json'),
    Stage('bg', '背景图重导出（含新活动）', 'live', st_bg_export,
          'export_assets 汇总行「失败: 0」（退出码不可信）',
          step=3, writes='Output/Raw/{bg,commonbg,loadingbg,…}（无暂存通道）'),
    Stage('paintings', '静态立绘合成 → 临时区', 'staged', lambda a, f: st_paintings(f, a),
          '数 ✗ 行（失败仍 exit 0）',
          step=3, writes='.diag/pipeline/Paintings_v2', rate=1.25, unit='张'),
    Stage('spine', 'Spine 提取 + parts.json → 临时区', 'staged', lambda a, f: st_spine(f, a),
          '每个目录都要有 parts.json',
          step=3, writes='.diag/pipeline/Spine_v2', rate=1.7, unit='个皮肤'),
    Stage('live2d', 'Live2D 还原 + motion → 临时区', 'staged', lambda a, f: st_live2d(f, a),
          '[SUMMARY] 收尾行 + texorder/tex_completeness 闸门',
          step=3, writes='.diag/pipeline/Live2D'),
    Stage('audio', 'CV 语音包解码 + 台词表', 'live', lambda a, f: st_audio(a),
          'l2d_voice_inventory 退出码',
          step=3, writes='Output/Audio（无暂存通道）'),
    Stage('bgm', 'BGM 补导（cue → FLAC → 索引）', 'live', st_bgm,
          'rebuild_bgm_library 退出码 + 缺 N 汇总行（两个子脚本失败也 exit 0）',
          step=3, writes='Output/Audio/BGM（无暂存通道）'),
    Stage('cg', 'Spine 全屏 CG 导出', 'live', lambda a, f: st_cg(f, a),
          '必须读到「完成N 跳过N 失败N」且失败=0',
          step=3, writes='Output/CG_v2（无暂存通道）', rate=1.3, unit='张'),
    Stage('review', '出改前|改后总表 + 硬链扫描', 'read', lambda a, f: st_review(),
          '只出表；看图是人工',
          step=4, writes='.diag/pipeline/*.png 对照表 + 两份清单'),
    Stage('swap-in', '备份换入 Paintings_v2', 'live', lambda a, f: st_swapin(a),
          'painting_swap_in 四道硬检查退出码',
          step=5, writes='Output/Paintings_v2（先备份到 Output/_OLD_bak/pipeline_<日期>/）'),
    Stage('derive', '缩略图 / 索引 / 部署', 'live', lambda a, f: st_derive(a),
          'gallery_index_diff_check 绿 + deploy --check 4/4 同 inode',
          step=5, writes='Output/gallery_v2'),
    Stage('labels', '重建背景/音乐标签 + 漂移报告', 'live', st_labels,
          'rebuild_labels 退出码 + 新增词根/未命名清单',
          step=5, writes='Output/gallery_v2/{bg_meta,bgm}.json + inputs/gamecfg/bg_series_labels.json（签字后）'),
    Stage('regress', 'WF-16 回归（跳全库 hit_verify）', 'staged', lambda a, f: st_regress(a),
          '串行 runner 退出码',
          step=5, writes='不改产物', check=True),
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


def stage_units(s, full, fp=None):
    """→ 本次范围里这一步要处理多少个单位；None = 全量或这一步不吃范围。"""
    top = SCOPE_UNIT.get(s.key)
    if not top:
        return None
    mode, payload = scope_state(full, fp)
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
    sc = scope_stamp()      # 结论的第二枚章：范围清单的身份
    st = json.load(open(STATE, encoding='utf-8')) if os.path.isfile(STATE) else {}
    if base_of(st.get('fingerprint')) != base_of(fp):
        # 换了一批源包 ⇒ 保守地全部重判（这是"大事件"，不该只挑几个阶段）。
        log(f'输入指纹变了（{st.get("fingerprint", "无记录")} → {fp}），旧状态作废，全部重判')
        st = {'fingerprint': fp, 'done': {}}
    else:
        # 源包没变：逐阶段重判（可能是配置表刷新了，也可能指纹算法本身改过 ——
        # 2026-10-17 §157 加 `cfg=` 那次，盘上状态是按老规则盖章的，
        # 不这么过滤就会把刚跑完 12 分钟的 cfg.* 一起清掉）。
        st, keep, drop = rejudge_state(st, fp)
        if drop:
            log(f'配置表刷新/指纹规则更新 ⇒ 保留 {len(keep)} 项，'
                f'作废 {len(drop)} 项（该重跑）：{", ".join(sorted(set(drop))[:8])}'
                f'{" …" if len(set(drop)) > 8 else ""}')
    st.setdefault('done', {})

    plan = [x for x in STAGES if not want or x.key in want]
    T0 = time.time()
    for i, s in enumerate(plan, 1):
        # read 档**永不缓存**：preflight / review 这类安全检查缓存下来 = 从此不再检查，
        # 正是本项目最怕的静默失效。要重跑 staged 档用 --force。
        # 验收类阶段**永不缓存**：它缓存下来 = 换入之后不再复查，报的还是上一轮的绿。
        # （2026-10-01 实测：swap-in 换入 12 张后 regress 被 `done` 缓存跳过，
        #  范围章与指纹章都没变——变的是**正式区内容**，而那正是 regress 要验的东西。）
        cacheable = s.tier == 'staged' and 'force' not in flags and not s.check
        # 跳过缓存也必须认**范围清单的身份**：清单换过（被冲空又复原也算），上一批记的
        # "paintings 已完成"就是假的 —— 那会让这一次真的跳过 179 张不重导。
        d0 = st['done'].get(s.key, {})
        # 没盖章的旧条目一律不算这轮的：失效方向必须是"多跑一次"，不能是"少跑一次"。
        if cacheable and d0.get('fingerprint') == stage_fp(s) and d0.get('scope') == sc:
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
            st['done'][s.key] = dict(RESULTS[s.key], fingerprint=stage_fp(s), scope=sc)
        else:
            st['done'].pop(s.key, None)
        # verdict 是另一件事：**给界面看的"上次结论"**，13 个阶段全都记。
        # 以前只有 done 那 4 个能被界面读到，其余一律显示"未跑"，看着像整条线没跑过。
        # 它不参与任何跳过判断。但每条都要盖上"哪批输入 + 哪份范围"两枚章，否则界面会拿
        # 上一批的绿涂到这一批上（§74 那条假绿灯就是这么来的）。
        st.setdefault('verdict', {})[s.key] = dict(RESULTS[s.key], fingerprint=fp, scope=sc)
        st['scope'] = sc
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
