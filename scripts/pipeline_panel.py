# -*- coding: utf-8 -*-
"""资产更新控制台 —— 本地网页仪表盘，双击「启动资产更新控制台.bat」打开。

它**不重新实现**任何流水线逻辑：每个按钮都是去起 `scripts/update_pipeline.py` 子进程，
然后把它写的日志实时读回来显示。这样"界面上看到的"和"命令行跑的"永远是同一套代码，
不存在两份逻辑各自漂移的问题（本项目栽过这类坑）。

界面按「五步主线」组织（接模拟器 / 同步配置表 / 重新导出 / 看图对比 / 签字换入），
步骤归属与「写到哪儿」两个事实定义在 `update_pipeline.STEPS` 与 `Stage.writes` 里，
面板只读不抄 —— 抄一份就会在新加阶段时把它藏起来。

    py -3 scripts/pipeline_panel.py            # 起服务并自动开浏览器
    py -3 scripts/pipeline_panel.py --no-open  # 只起服务（无人值守）
    py -3 scripts/pipeline_panel.py --port 8790

安全边界（这是个能起子进程的本地服务，所以写死三条）：
  · 只绑 127.0.0.1，不对外。
  · 能跑什么由 `update_pipeline.STAGES` 的**阶段名白名单**决定 —— 前端传进来的
    stage/approve 名字必须命中白名单，否则拒绝。不存在"把输入拼进命令行"这条路。
  · 图片只从 `.diag/pipeline/` 里出，realpath 前缀校验，防目录穿越。
"""
import argparse
import glob
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PIPE = os.path.join(ROOT, 'scripts', 'update_pipeline.py')
WORK = os.path.join(ROOT, '.diag', 'pipeline')
PANEL = os.path.join(WORK, 'panel')
RUNS = os.path.join(PANEL, 'runs.json')
PORT = 8788
PY = sys.executable
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')

_lock = threading.Lock()


def pid_alive(pid):
    """只读地判断一个子进程还在不在。

    ⚠️ Windows 上**绝对不能用 `os.kill(pid, 0)` 探活**：CPython 在非 POSIX 语义下把它
    实现成 `OpenProcess(...)+TerminateProcess(handle, 0)` —— 那不是探测，那是**杀掉**。
    本面板每 8 秒轮一次 /api/state，第一次轮询就会把正在跑的流水线子进程当场终止；
    一次真更新要跑几十分钟，症状会是"任务莫名结束、日志停在半路"。
    ⇒ 用 OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION) + GetExitCodeProcess 只读取退出码。
    """
    if not pid:
        return False
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    k = ctypes.windll.kernel32
    h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        if not k.GetExitCodeProcess(h, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        k.CloseHandle(h)


# ------------------------------------------------------------------ 阶段白名单
def stage_keys():
    """阶段名与档位一律从 update_pipeline 读，**不在面板里再抄一份清单**——
    抄了就会漂移（本项目栽过"谁写谁读各一份实现"这类坑）。
    update_pipeline 有 __main__ 保护，import 它没有副作用。"""
    sys.path.insert(0, HERE)
    import update_pipeline as up
    import importlib
    importlib.reload(up)          # 改了流水线脚本后不用重启面板
    return [{'key': s.key, 'title': s.title, 'tier': s.tier, 'judge': s.judge_desc,
             'step': s.step, 'writes': s.writes,
             # 预计耗时的两个来源都跟着阶段走（没量过的都是 0 ⇒ 进度台显示"未知"而不是猜）
             'est': getattr(s, 'est', 0.0), 'rate': getattr(s, 'rate', 0.0),
             'unit': getattr(s, 'unit', '')} for s in up.STAGES], dict(up.STEPS)


# ------------------------------------------------------------------ 运行记录
def load_runs():
    try:
        return json.load(open(RUNS, encoding='utf-8'))
    except Exception:
        return []


def save_runs(runs):
    os.makedirs(PANEL, exist_ok=True)
    tmp = RUNS + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(runs, f, ensure_ascii=False, indent=1)
    os.replace(tmp, RUNS)


def running_job():
    for r in load_runs():
        if r.get('state') == 'running':
            if pid_alive(r.get('pid')):
                return r
            r['state'] = 'gone'
    return None


def start_job(label, argv):
    """起一个脱离面板的流水线子进程。重活必须串行 —— 已有在跑就拒绝。"""
    with _lock:
        cur = running_job()
        if cur:
            return None, f'已经有一个任务在跑（{cur["label"]}，pid={cur["pid"]}）。' \
                         f'这台机器 15.4GB，重活只允许一次一个。'
        os.makedirs(PANEL, exist_ok=True)
        rid = time.strftime('%H%M%S')
        log = os.path.join(PANEL, f'run_{rid}.log')
        lf = open(log, 'w', encoding='utf-8', errors='replace')
        p = subprocess.Popen([PY, PIPE] + argv, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT,
                             env=ENV, creationflags=0x00000008 if os.name == 'nt' else 0)
        runs = load_runs()
        runs.append({'id': rid, 'label': label, 'argv': argv, 'pid': p.pid, 'log': log,
                     'state': 'running', 'started': time.strftime('%Y-%m-%d %H:%M:%S')})
        save_runs(runs)
        lf.close()   # 让子进程自己持有；父进程关掉句柄，进程结束后面板仍能读文件
        return rid, None


def refresh_states():
    """把每个 running 任务的实际状态回读一遍（靠日志收尾行，不靠 pid）。"""
    runs = load_runs()
    changed = False
    for r in runs:
        if r.get('state') != 'running':
            continue
        alive = pid_alive(r.get('pid'))
        tail = ''
        try:
            tail = open(r['log'], encoding='utf-8', errors='replace').read()[-4000:]
        except OSError:
            pass
        finished = ('===== 汇总 =====' in tail) or ('[FAIL]' in tail and not alive)
        if not alive:
            # 进程没了就是结束了。`--plan` 这类不打印「汇总」的正常结束也算 done，
            # 只是用 clean 记下有没有看到收尾行 —— 别把它误标成失败，那会让人以为跑挂了。
            r['state'] = 'done'
            r['clean'] = bool(finished or '要签字的 live 档' in tail or '[PASS]' in tail)
            r['ended'] = time.strftime('%Y-%m-%d %H:%M:%S')
            changed = True
    if changed:
        save_runs(runs)
    return runs


# ------------------------------------------------------------------ 进度台
# 跑的时候主屏上那条「已用 / 内存 / 阶段 N/M / 剩余」细带。四个量都必须是**可核对的事实**：
#   · 已用  = 子进程启动时刻（runs.json 的 started），不是"界面刷新了多久"
#   · 内存  = **整棵进程树**的工作集之和 —— 只算编排器自己会漏掉真正吃内存的那几个导出子进程
#   · 阶段  = 当前日志里最后一条 `== key` 行；N/M 的 M 来自**本次 argv 的范围**（--only 会缩小它）
#   · 剩余  = 各阶段**历史均值**之和（吃 .diag/pipeline/run_*.log 的时间戳）。
#             有阶段没样本时**不装作知道**：改报「≥」下限，而不是拿总时长×百分比糊一个数。
# 没在跑 ⇒ 返回 None，界面上一分都不多。这也是"静止时逐像素相同"能继续成立的前提。
_TS = re.compile(r'^\[(\d\d):(\d\d):(\d\d)\]')
_STAGE_START = re.compile(r'^\[\d\d:\d\d:\d\d\]\s+==\s+(\S+)')
_STAGE_VERDICT = re.compile(r'^\[\d\d:\d\d:\d\d\]\s+[\u2705\u274c]\s+(\S+):')
_STAGE_SKIP = re.compile(r'^\[\d\d:\d\d:\d\d\]\s+\u23ed\s+(\S+)')


def _secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + int(s)


def _stage_spans(path):
    """一份日志 → [(key, 起秒, 止秒)]。止 = 下一个阶段的起点，最后一个阶段止于日志末行。"""
    starts, last = [], None
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                m = _TS.match(ln)
                if not m:
                    continue
                t = _secs(*m.groups())
                if last is not None and t < last:
                    t += 86400                     # 跨零点：按单调递增修一次
                last = t
                sm = _STAGE_START.match(ln)
                if sm:
                    starts.append((t, sm.group(1)))
    except OSError:
        return []
    out = []
    for i, (t, k) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else last
        if end is not None and end > t:
            out.append((k, t, end))
    return out


def _stage_means():
    """各阶段历史平均耗时（秒），样本 = .diag/pipeline/run_*.log。"""
    acc = {}
    for p in glob.glob(os.path.join(PANEL, 'run_*.log')):
        for k, a, b in _stage_spans(p):
            acc.setdefault(k, []).append(b - a)
    return {k: sum(v) / len(v) for k, v in acc.items()}


def _scope_units(fp=None):
    """本次增量里每个"按项数线性耗时"的阶段要处理多少项（给速率估算用）。

    ⚠️ 历史均值在**第一次跑**时必然是空的（本项目 13 个阶段里 9 个从没真跑过），
    只认均值的话进度台的「剩余」永远显示未知 —— 那正是用户抱怨"不知道进行到什么程度"。
    """
    def calc():
        sys.path.insert(0, HERE)
        try:
            import update_pipeline as up
            importlib.reload(up)
            return {s.key: up.stage_units(s, False, fp) for s in up.STAGES
                    if getattr(s, 'rate', 0.0)}
        except Exception as e:
            print(f'[警告] 读各阶段本次项数失败：{e}')
            return None
    return _cached('units', 30.0, calc) or {}



def _progress_from_log(path):
    """当前日志 → (在跑的阶段key, 它的起点秒, 已判完的 key 集合, 已跳过的 key 集合)。"""
    started, done, skipped = [], set(), set()
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                if not _TS.match(ln):
                    continue
                m = _STAGE_START.match(ln)
                if m:
                    started.append((_secs(*_TS.match(ln).groups()), m.group(1)))
                    continue
                m = _STAGE_VERDICT.match(ln)
                if m:
                    done.add(m.group(1))
                    continue
                m = _STAGE_SKIP.match(ln)
                if m:
                    skipped.add(m.group(1))
    except OSError:
        return '', None, set(), set()
    cur, cur_t = '', None
    for t, k in started:
        if k not in done:
            cur, cur_t = k, t
    return cur, cur_t, done, skipped


def _scope_keys(argv, stages):
    """本次运行**打算考虑**的阶段（进度台的分母）。--plan 不跑阶段 ⇒ 0。"""
    allk = [s['key'] for s in stages]
    if '--plan' in argv:
        return []
    only = ''
    if '--only' in argv:
        i = argv.index('--only')
        if i + 1 < len(argv):
            only = argv[i + 1]
    if only:
        want = {x for x in only.split(',') if x}
        return [k for k in allk if k in want]
    return allk


def _tree_mem_mb(root):
    """整棵进程树的工作集合计（MB）+ 进程数。**只读查询**，与 pid_alive 同一条纪律。"""
    import ctypes

    class PE(ctypes.Structure):
        _fields_ = [('dwSize', ctypes.c_ulong), ('cntUsage', ctypes.c_ulong),
                    ('th32ProcessID', ctypes.c_ulong), ('th32DefaultHeapID', ctypes.c_void_p),
                    ('th32ModuleID', ctypes.c_ulong), ('cntThreads', ctypes.c_ulong),
                    ('th32ParentProcessID', ctypes.c_ulong), ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', ctypes.c_ulong), ('szExeFile', ctypes.c_char * 260)]

    class PMC(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                    ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]

    k = ctypes.windll.kernel32
    kids = {}
    snap = k.CreateToolhelp32Snapshot(0x2, 0)          # TH32CS_SNAPPROCESS
    if snap and snap != -1:
        try:
            e = PE()
            e.dwSize = ctypes.sizeof(e)
            ok = k.Process32First(snap, ctypes.byref(e))
            while ok:
                kids.setdefault(e.th32ParentProcessID, []).append(e.th32ProcessID)
                ok = k.Process32Next(snap, ctypes.byref(e))
        finally:
            k.CloseHandle(snap)
    pids, stack = [], [int(root)]
    while stack:
        p = stack.pop()
        pids.append(p)
        stack.extend(kids.get(p, []))
    getmem = getattr(k, 'K32GetProcessMemoryInfo', None) or ctypes.windll.psapi.GetProcessMemoryInfo
    total = 0
    for p in pids:
        h = k.OpenProcess(0x1000, False, p)            # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            continue
        try:
            c = PMC()
            c.cb = ctypes.sizeof(c)
            if getmem(h, ctypes.byref(c), c.cb):
                total += c.WorkingSetSize
        finally:
            k.CloseHandle(h)
    return total / 1048576.0, len(pids)


def _log_secs(path):
    """一份日志的首末时间戳差（秒）= 这一轮到底跑了多久。跨零点按 +86400 修一次。"""
    first = last = None
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                m = _TS.match(ln)
                if not m:
                    continue
                t = _secs(*m.groups())
                if first is None:
                    first = t
                elif t < last:
                    t += 86400
                last = t
    except OSError:
        return None
    return max(0, last - first) if first is not None and last is not None else None


def _unit_progress(path):
    """日志里**最后一条**「a/b」形态的阶段内进度 → (done, total, 原文)。

    流水线侧统一打了这几种：`批次进度 25/269`、`live2d 进度 3/4`、`进度 12/40 成功=…`、
    被调脚本自己的 `处理 1200/4488`。没有命中就返回 None ⇒ 界面只报阶段级进度，
    **不拿"上一次的值"假装还在动**。
    """
    hit = None
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                if '进度' not in ln:
                    continue
                m = re.search(r'(\d+)\s*/\s*(\d+)', ln)
                if m and int(m.group(2)) > 0:
                    hit = (int(m.group(1)), int(m.group(2)), ln.strip()[-64:])
    except OSError:
        return None
    return hit


def _last_run():
    """最近一次**已结束**的任务 → {id, label, secs, red}。没在跑、也没跑过 ⇒ None。"""
    for r in reversed(load_runs()):
        if r.get('state') == 'running':
            continue
        return {'id': r.get('id'), 'label': r.get('label'),
                'secs': _log_secs(r.get('log') or ''),
                'clean': bool(r.get('clean'))}
    return None


def gauge_safe(run, stages, fp=None):
    """在跑 → 进度台的数据；刚跑完 → 一条**静态收尾条**；没跑过 → None。"""
    if not run:
        return None
    try:
        t0 = time.mktime(time.strptime(run.get('started', ''), '%Y-%m-%d %H:%M:%S'))
    except Exception:
        t0 = None
    elapsed = max(0.0, time.time() - t0) if t0 else None

    log = run.get('log') or ''
    cur, cur_t, done, skipped = _progress_from_log(log)
    scope = _scope_keys(run.get('argv') or [], stages)
    mem_mb, nproc = _tree_mem_mb(run.get('pid') or 0)

    eta, missing, known, srcs = None, 0, 0, {}
    means = _cached('means', 60.0, _stage_means) or {}
    units = _scope_units(fp)
    bykey = {s['key']: s for s in stages}

    def est_sec(k):
        """一个阶段的预计秒数 + 它是**怎么来的**（历史均值 / 实测速率×项数 / 实测常量）。"""
        if k in means:
            return means[k], 'hist'
        s = bykey.get(k) or {}
        if s.get('rate') and units.get(k):
            return s['rate'] * units[k], 'rate'
        if s.get('est'):
            return s['est'], 'est'
        return None, None

    if scope:
        first_t = next((t for _, t, _ in _stage_spans(log)), None)
        cur_el = 0.0
        if cur and cur_t is not None and first_t is not None and elapsed is not None:
            cur_el = max(0.0, elapsed - (cur_t - first_t))
        rest = [k for k in scope if k not in done and k not in skipped and k != cur]
        total_s = 0.0
        for k in rest:
            e, src = est_sec(k)
            if e is None:
                missing += 1
            else:
                total_s += e
                known += 1
                srcs[src] = srcs.get(src, 0) + 1
        if cur:
            e, src = est_sec(cur)
            if e is None:
                missing += 1
            else:
                total_s += max(0.0, e - cur_el)
                known += 1
                srcs[src] = srcs.get(src, 0) + 1
        if known:
            eta = total_s

    title = next((s['title'] for s in stages if s['key'] == cur), '')
    up_ = _unit_progress(log) if log else None
    return {'t0': t0, 'elapsed': elapsed, 'mem_mb': round(mem_mb, 1), 'nproc': nproc,
            'stage': cur, 'stage_title': title, 'done': len(done | skipped),
            'total': len(scope), 'skipped': len(skipped),
            'eta': None if eta is None else round(eta), 'eta_missing': missing,
            'eta_n': known, 'eta_src': srcs, 'samples': len(means),
            # 阶段内进度：日志里没有 a/b 就返回 None，界面只报阶段级，不拿旧值假装在动。
            'unit_done': (up_ or (None, None, ''))[0], 'unit_total': (up_ or (None, None, ''))[1],
            'unit_src': (up_ or (None, None, ''))[2], 'scope_keys': scope,
            # 分段条要按"哪几段已完成/已跳过"上色，光给个计数画不出真状态
            'done_keys': sorted(done), 'skipped_keys': sorted(skipped),
            # 本轮用时：跑完之后进度台按契约收起（静止帧判据在守），
            # 所以"这轮跑了多久"改由主屏那句话带出来，数据源是同一条日志的首末时间戳。
            'secs': _log_secs(log)}



# ------------------------------------------------------------------ HTTP
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        raw = body if isinstance(body, bytes) else json.dumps(
            body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path in ('/', '/index.html'):
            return self._send(200, PAGE.encode('utf-8'), 'text/html; charset=utf-8')
        if u.path == '/api/state':
            refresh_states()
            err = ''
            try:
                stages, steps = stage_keys()
            except Exception as e:
                stages, steps = [], {}
                err = str(e)
            state = {}
            try:
                raw = json.load(open(os.path.join(WORK, 'pipeline_state.json'), encoding='utf-8'))
                if raw.get('fingerprint') == fingerprint_safe():
                    # done=跳过缓存（只有暂存判绿档），verdict=上次结论（13 档全记）。
                    # 两个都要，且**指纹不同就一个都不读** —— 拿旧更新包的结论给这次的界面涂绿，
                    # 正是这条流水线最怕的那类假绿灯。
                    sc_now = scope_stamp_safe()
                    # done（跳过缓存）同样要认范围章：清单换过之后那条"已完成"就是假的
                    state = {k: v for k, v in (raw.get('done') or {}).items()
                             if v.get('scope') == sc_now}
                    # verdict 还要过第二道章：**范围清单的身份**。清单换过（被冲空又复原也算），
                    # 上一批跑出来的"本次增量没有立绘源包 ⇒ 跳过"就不是这轮的结论。
                    for k, v in (raw.get('verdict') or {}).items():
                        if v.get('scope') == sc_now:
                            state[k] = v
            except Exception:
                pass
            sheets = []
            for p in sorted(glob_sheets()):
                sheets.append({'name': os.path.basename(p),
                               'kb': round(os.path.getsize(p) / 1024),
                               'mt': time.strftime('%m-%d %H:%M', time.localtime(
                                   os.path.getmtime(p)))})
            run = running_job()
            return self._send(200, {
                'stages': stages, 'steps': steps, 'state': state,
                'runs': load_runs()[-12:][::-1],
                'running': run, 'error': err, 'sheets': sheets,
                # 已发布皮肤表 vs 本轮解析产物：差几行（发布早于解析时会 > 0）。
                # 2026-10-17 §155：发布跑在解析刷新之前 ⇒ 新皮肤无名、语音档位派不出，
                # 而阶段结论全是绿的（缓存）——这个差就是唯一会说真话的信号。
                'skin_gap': skin_table_gap(),
                # 最近一次**已结束**的任务用了多久：进度台按契约跑完就收起（静止帧判据），
                # 所以"这轮跑了多久 / 停在哪"要由主屏那句话带出来。
                'last': _last_run(),
                'news': newsafe(),
                # 一次 /api/state 只算**一遍**输入指纹（walk 9 万多个源包），往下传。
                # 以前各处各算，实测冷缓存那一拍要 5.8 秒 —— 前端轮询超时，看着就是进度不动。
                'fingerprint': (fp := fingerprint_safe()),
                'scope': scope_safe(fp),
                'gauge': gauge_safe(run, stages, fp),
            })
        if u.path == '/api/log':
            # 必须在这里也刷一次状态：前端追日志期间停掉了 8s 一次的 /api/state 轮询，
            # 只靠那边刷新的话，任务早就结束了面板还会一直显示「运行中」。
            refresh_states()
            rid = q.get('id', '')
            run = next((r for r in load_runs() if r['id'] == rid), None)
            if not run:
                return self._send(404, {'error': '没有这个任务'})
            off = int(q.get('offset', 0) or 0)
            try:
                with open(run['log'], 'rb') as f:
                    f.seek(off)
                    data = f.read(400_000)
            except OSError:
                data = b''
            return self._send(200, {'text': data.decode('utf-8', 'replace'),
                                    'offset': off + len(data),
                                    'state': run.get('state')})
        if u.path == '/file':
            p = os.path.realpath(os.path.join(WORK, unquote(q.get('path', ''))))
            if not p.startswith(os.path.realpath(WORK) + os.sep) or not os.path.isfile(p):
                return self._send(403, {'error': '只允许读 .diag/pipeline 下的文件'})
            with open(p, 'rb') as f:
                return self._send(200, f.read(),
                                  'image/png' if p.endswith('.png') else 'application/octet-stream')
        return self._send(404, {'error': 'not found'})

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(n).decode('utf-8')) if n else {}
        except Exception:
            return self._send(400, {'error': '不是合法 JSON'})
        if u.path != '/api/run':
            return self._send(404, {'error': 'not found'})
        valid = {s['key'] for s in stage_keys()[0]}
        only = [x for x in body.get('stages', []) if x in valid]
        if len(only) != len(body.get('stages', [])):
            return self._send(400, {'error': '含未知阶段名，拒绝'})
        approve = [x for x in body.get('approve', []) if x in valid]
        if len(approve) != len(body.get('approve', [])):
            return self._send(400, {'error': '含未知阶段名，拒绝'})
        argv = []
        label = '跑到待确认（不碰正式产物）'
        if body.get('plan'):
            argv, label = ['--plan'], '只看计划'
        else:
            if only:
                argv += ['--only', ','.join(only)]
                label = '单阶段：' + ','.join(only)
            if approve:
                argv += ['--approve'] + approve
                label += ' + 签字放行 ' + ','.join(approve)
            if body.get('full'):
                argv.append('--full')
                label += ' 【全量】'
            if body.get('force'):
                argv.append('--force')
                label += '（强制重跑）'
        if body.get('full'):
            return self._send(400, {'error': '全量重跑请以命令行方式执行 '
                                             'py -3 scripts/update_pipeline.py --full '
                                             '（它要手输 FULL 二次确认，网页上不做这个）'})
        rid, err = start_job(label, argv)
        if err:
            return self._send(409, {'error': err})
        return self._send(200, {'id': rid})


def skin_table_gap():
    """已发布皮肤表 vs 本轮解析产物，差几行（读不动返回 None，不挡主流程）。

    为什么需要它：`cfg.publish` 的结论是按指纹缓存的，发布跑在解析刷新之前时
    结论仍绿，但 `inputs/gamecfg/ship_skin_template.json` 里就是缺行
    （2026-10-17 实测：19:46 发布用 09-25 的 scalar，21:11 才刷新 ⇒ 少 6 行）。
    行数差是唯一不依赖缓存的真信号。
    """
    try:
        pub_p = os.path.join(ROOT, 'inputs', 'gamecfg', 'ship_skin_template.json')
        dev_p = os.path.join(ROOT, '.diag', 'sharecfg_re', 'cfg_json_scalar',
                             'ship_skin_template.json')
        if not os.path.isfile(pub_p) or not os.path.isfile(dev_p):
            return None
        pub = json.load(open(pub_p, encoding='utf-8'))
        dev = json.load(open(dev_p, encoding='utf-8'))
        gap = len(set(map(str, dev)) - set(map(str, pub)))
        if gap <= 0:
            return None
        lost = sorted(set(map(str, pub)) - set(map(str, dev)))
        sample = [dev[k].get('painting') for k in sorted(set(map(str, dev)) - set(map(str, pub)))
                  if isinstance(dev.get(k), dict)][:6]
        return {'pub': len(pub), 'dev': len(dev), 'gap': gap, 'lost': len(lost),
                'sample': [s for s in sample if s]}
    except Exception:
        return None


def newsafe():
    """这次更新**新增**了哪些皮肤（正式区之前没有的）+ 它们现在在不在、有没有语音、叫什么名。

    数据源是 review 落的 `new_paintings.txt` —— 没有"线上新增"这一档，就没有这个板块可言
    （§79 的根因正是它曾被并进"与线上不同"里，结果永远是 0）。
    """
    def calc():
        out = os.path.join(ROOT, 'Output')          # 面板侧没有 OUT，别照搬流水线那套名字
        lst = os.path.join(WORK, 'new_paintings.txt')
        if not os.path.isfile(lst):
            return {'rows': [], 'note': '还没跑过第 3 步的对照表 —— 它才算得出"哪些是新增"'}
        names = [x.strip() for x in open(lst, encoding='utf-8') if x.strip()]
        try:
            meta = json.load(open(os.path.join(out, 'ship_meta.json'), encoding='utf-8'))
        except Exception:
            meta = {}
        try:
            voice = json.load(open(os.path.join(out, 'gallery_v2', 'skin_voice.json'), encoding='utf-8'))
        except Exception:
            voice = {}
        rows = []
        for s in names:
            m = meta.get(s) or {}
            v = voice.get(s) or {}
            rows.append({'stem': s, 'ship': m.get('cn') or '', 'skin': m.get('skin_name') or '',
                         'faction': m.get('faction') or '', 'rarity': m.get('rarity') or '',
                         'voice': len(v.get('lines') or []), 'meta': bool(m),
                         'live': os.path.isfile(os.path.join(out, 'Paintings_v2', s + '.png'))})
        return {'rows': rows,
                'live_n': sum(1 for r in rows if r['live']),
                'sheet': ('sheet_paintings.png'
                          if os.path.isfile(os.path.join(WORK, 'sheet_paintings.png')) else '')}
    return _cached('news', 45.0, calc)


def glob_sheets():
    import glob
    return glob.glob(os.path.join(WORK, '*.png')) + glob.glob(os.path.join(WORK, '*.jpg'))


# 输入指纹要 os.walk 整个 files/AssetBundles（91,643 个文件，实测数秒）。
# 前端每 8s 轮询一次 /api/state，不缓存的话每次轮询都白扫一遍盘，首屏还会空着十几秒像死掉。
_CACHE = {'fp': [None, 0.0], 'scope': [None, 0.0], 'means': [None, 0.0], 'units': [None, 0.0],
           'scopetag': [None, 0.0], 'news': [None, 0.0]}


def _cached(slot, ttl, fn):
    val, at = _CACHE[slot]
    now = time.time()
    if val is not None and now - at <= ttl:
        return val
    out = fn()
    if out is not None:          # 失败不缓存，下一拍就重试
        _CACHE[slot] = [out, now]
    return out


def fingerprint_safe():
    def calc():
        sys.path.insert(0, HERE)
        try:
            import update_pipeline as up
            return up.fingerprint()
        except Exception as e:
            print(f'[警告] 读输入指纹失败：{e}')
            return None
    return _cached('fp', 30.0, calc) or '(读不到：源包目录打不开？)'


def scope_stamp_safe():
    """当前范围清单的身份（与 `update_pipeline.scope_stamp()` 同源）。读不到 ⇒ 'none'。"""
    def calc():
        sys.path.insert(0, HERE)
        try:
            import update_pipeline as up
            return up.scope_stamp()
        except Exception as e:
            print(f'[警告] 读范围清单身份失败：{e}')
            return None
    return _cached('scopetag', 20.0, calc) or 'none'


def scope_safe(fp=None):
    def calc():
        sys.path.insert(0, HERE)
        try:
            import update_pipeline as up
            t = up.affected_stems(False, fp)
            return None if t is None else len(t)
        except Exception as e:
            print(f'[警告] 读增量范围失败：{e}')
            return None
    return _cached('scope', 30.0, calc)


PAGE = r'''
<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>资产更新控制台</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
/* ══ token ══════════════════════════════════════════════════════════════
   两条铁律：
   ① **一个颜色只表示一件事**。颜色只属于「状态」（未跑/判绿/判红/等你签字/在跑），
      阶段档位一律用文字+图标。
   ② **深色仪表盘的正经分层法：表面阶梯 + 发丝线 + 零投影。**
      参照物是两个公开设计系统的实测 token（Linear / Raycast），它们的规则：
        · 不用薰衣草色当分区底色或卡片填充；
        · 几乎不用 drop shadow，纵向层级全靠色阶与描边；
        · 不引入第二种强调色，不加氛围渐变。
      ⇒ 现在：**海军蓝**五档表面阶梯（色相压在 215° 一带）、1px 实色发丝线、
      投影全部换成 `inset` 顶边微高光、**唯一的 chrome 强调色 = 蓝白**（`--brand`）。
      五个状态色 idle/pass/fail/await/run **一个都不动**——那是语义不是配色。
   所有可视量都走变量，于是旧版面整体挂在 `body.legacy` 上，`V` 键当场对照。 */
:root{
  /* 表面阶梯（同构 Linear 的 5 档，色相压到 215° 的海军蓝，不偏紫） */
  --abyss:#04070d; --deep:#070c15; --pane:#0b1322; --card:#101a2c; --raise:#16243a;
  --head:#060b14;
  /* 发丝线：实色、1px、三档，冷蓝灰 */
  --line:#1a2740; --line2:#26375a; --line3:#3a5382;
  /* 文字坡：冷灰偏蓝 */
  --txt:#e9eef8; --txt2:#b3bfd5; --dim:#7b879f; --dim2:#586279;
  --idle:#3f5a6e; --pass:#4fd6a8; --fail:#ff6f6f; --await:#f2bd72; --run:#5fd0e8;
  --brand:#cfe0ff;          /* 唯一的 chrome 强调色：蓝白（与背景星野同源） */
  --brand-hi:#eef4ff;       /* 它的 hover，不算第二种彩 */
  --pop:var(--brand);       /* 兼容旧引用：品红退役，一律回落到强调色 */
  /* 星点色：按**色温**排（蓝白→白→淡金），不再有糖果粉 */
  --s-1:#eef4ff; --s-2:#dbe6f7; --s-3:#fff2df; --s-4:#ffd9ae;
  --s-link:#9aa4c8;         /* 星座连线：中性冷灰蓝，压到近不可见 */
  --fd:'Bahnschrift','DIN Alternate','Microsoft YaHei UI',system-ui,sans-serif;
  --fb:'Microsoft YaHei UI','Microsoft YaHei',system-ui,sans-serif;
  --fm:'Cascadia Mono','Consolas',ui-monospace,monospace;
  --ez:cubic-bezier(.22,.61,.36,1);
  /* 刻度（Linear/Raycast 都是 4 的倍数栅格 + 分档圆角） */
  --r-tag:4px; --r-chip:6px; --r-ctl:8px; --r-card:12px; --r-pill:999px;
  --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:24px; --s6:32px;
  --pad-pane:var(--s3) var(--s4);
  --elev:0 0 0 0 transparent;                 /* 投影一律归零 */
  --edge:inset 0 1px 0 rgba(255,255,255,.045);/* 换成顶边微高光 */
  --tt:none; --ph-ls:.2px;                    /* 小标签不再全大写 + .18em 宽字距 */
  --hero-fs:20px; --hero-ls:-.2px;
}
body.legacy{
  --abyss:#06040e; --deep:#150d1f; --pane:#12101f; --card:#181527; --raise:#241d3a;
  --head:#100d1d;
  --line:rgba(178,166,214,.18); --line2:rgba(178,166,214,.36); --line3:rgba(178,166,214,.5);
  --txt:#efe9f7; --txt2:#d6cde8; --dim:#9b90b4; --dim2:#6f6686;
  --brand:#a06bff; --brand-hi:#b489ff; --pop:#ff3d7f;
  --s-1:#f6e7d3; --s-2:#cfe6ff; --s-3:#ffd6a5; --s-4:#ff9ecb; --s-link:#a06bff;
  --r-tag:6px; --r-chip:999px; --r-ctl:9px; --r-card:14px;
  --pad-pane:13px 15px;
  --elev:0 22px 46px -32px rgba(0,0,0,.92);
  --edge:inset 0 1px 0 rgba(214,200,255,.07);
  --tt:uppercase; --ph-ls:.18em;
  --hero-fs:17px; --hero-ls:.04em;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;font:13px/1.55 var(--fb);color:var(--txt);overflow:hidden;
  background:linear-gradient(180deg,var(--abyss) 0%,var(--deep) 62%,var(--deep) 100%)}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-thumb{background:var(--line2);border-radius:6px}
::-webkit-scrollbar-thumb:hover{background:var(--line3)}
::-webkit-scrollbar-track{background:transparent}

/* ══ 背景层：夜航星野（氛围只留在这里，面板上一个都不给）═══════════════
   星点画在一张 2D 画布上：鼠标划过 ⇒ 星点显影；停手 ⇒ 能量归零后**写回 home 再画一帧**。
   最后那一句是关键：它保证"亮过又淡掉"的终点和初始帧**逐像素相同**。
   底是纯黑——连城市光晕也不给：那几团彩光是"AI 味"的主要来源。 */
#bgfx{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
#bgfx canvas{position:absolute;inset:0;width:100%;height:100%}
/* 星云单独一张**永不重绘**的画布：它整幅是静态的，跟着星点画布每帧 clearRect 再 blit
   一次等于白拷 6MB/帧（SwiftShader 上实测拖慢截图到 2s+），而且每帧重合成还会带来
   dither 抖动。分开之后静止帧天然逐像素相同。 */
body.plain #bgfx #nebula{display:none}

/* ══ 骨架：三个独立滚动的区，页面本身不滚 ═══════════════════════════════ */
.app{position:relative;z-index:1;display:flex;flex-direction:column;height:100vh}
/* 顶栏：一道发丝线收口，不挂投影、不挂那道品红斜切。 */
header{position:relative;z-index:10;flex:0 0 auto;display:flex;align-items:center;gap:var(--s5);
  padding:var(--s3) var(--s5);background:var(--head);
  border-bottom:1px solid var(--line);box-shadow:var(--edge)}
body.legacy header{border-bottom-color:rgba(206,186,255,.28);
  box-shadow:inset 0 1px 0 rgba(226,210,255,.24),0 1px 0 rgba(6,4,14,.6),0 16px 34px -26px #000}
header::after{content:'';position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(104deg,rgba(255,142,192,.10) 0 14%,transparent 14%)}
body:not(.legacy) header::after{display:none}
.brand{display:flex;align-items:center;gap:11px;flex:0 0 auto}
.brand svg{display:block}
.brand h1{margin:0;font:600 16px/1.2 var(--fd);letter-spacing:-.1px;color:var(--txt)}
.brand p{margin:1px 0 0;font-size:11px;color:var(--dim2);letter-spacing:.2px}
.meters{display:flex;gap:var(--s2);flex-wrap:wrap;align-items:center;flex:1 1 auto;min-width:0}
.meter{font:11px/1 var(--fm);padding:5px var(--s2);border-radius:var(--r-chip);
  background:var(--card);border:1px solid var(--line);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;color:var(--txt2)}
.meter b{color:var(--dim);font-weight:400;margin-right:6px}
.meter.ok b,.meter.ok span{color:var(--pass)}
.act{display:flex;gap:var(--s2);flex:0 0 auto}

/* 控件：8px 圆角、1px 发丝线、hover 走"抬一档表面"而不是描边发光（Linear 的
   "shift toward lighter backgrounds or higher surface tiers when hovered"）。 */
button{font:500 12.5px/1.2 var(--fb);letter-spacing:.1px;padding:7px var(--s4);
  border-radius:var(--r-ctl);border:1px solid var(--line);
  background:var(--card);color:var(--txt);cursor:pointer;
  transition:background .16s var(--ez),border-color .16s var(--ez),
    transform .12s var(--ez),color .16s var(--ez),opacity .16s}
button:hover{border-color:var(--line2);background:var(--raise);color:var(--txt)}
button:active{transform:translateY(1px)}
button:disabled{opacity:.35;cursor:not-allowed;transform:none}
button:disabled:hover{border-color:var(--line);background:var(--card);color:var(--txt)}
button:focus-visible{outline:2px solid color-mix(in srgb,var(--brand) 55%,transparent);outline-offset:2px}
/* 主动作 = 唯一的 chrome 强调色，**实心平涂、无渐变、无外发光**。
   旧版面那道品红渐变 + 光晕正是"AI 生成界面"的典型指纹。 */
button.go{background:var(--brand);border-color:var(--brand);color:#0b0c12;font-weight:600}
button.go:hover{background:var(--brand-hi);border-color:var(--brand-hi)}
button.go:disabled{background:var(--brand);color:#0b0c12}
body.legacy button.go{background:linear-gradient(180deg,#b32b62,#7c1c46);border-color:#ff3d7f;
  color:#ffe9f2;box-shadow:0 12px 26px -16px rgba(255,61,127,.85),
    inset 0 1px 0 rgba(255,190,215,.32)}
body.legacy button.go:hover{background:linear-gradient(180deg,#cb3a72,#8e2350)}
/* 签字 = 借用「等你签字」那个状态色，语义自洽（它本来就是 await 的动宾形态） */
button.sign{border-color:rgba(242,189,114,.5);color:var(--await);
  background:rgba(242,189,114,.10)}
button.sign:hover{background:rgba(242,189,114,.18);border-color:var(--await)}
button.ghost{background:transparent;font-size:12px;padding:6px 11px;color:var(--dim)}
button.ghost:hover{color:var(--txt);background:var(--card)}
button.help{background:transparent;border-color:var(--line2);color:var(--txt2)}
button.help:hover{background:var(--card);border-color:var(--line3)}
button.mini{font-size:11.5px;padding:var(--s1) var(--s2);border-radius:var(--r-tag)}

/* ══ 光效层：指针携光 —— 全站唯一一条动效语言 ══════════════════════════
   隐喻只有一句：**光由指针携带**。指针进入 → 一道光沿控件边框从进入点绕一圈；
   控件内部跟着一团柔光；按下 → 光从落点泄进背景星野（背景那层本来就吃这个冲量）。
   三条纪律，一条都不能破：
     · 全部**指针驱动**，没有一条常驻循环 ⇒ 静止时与初始帧逐像素相同（和背景同一条要求，
       也是 8 秒轮询不再闪的前提）。
     · 只上**控件**（按钮 / 步骤块 / 筛选片 / 签字框）和卡片左光条；
       日志 `pre`、对照图、指标 pill 这些**数据面一个都不放过光**。
     · `body.calm`（M 键）整层停用，用来当场对比"这层到底值不值"。 */
@property --ang{syntax:'<angle>';inherits:false;initial-value:0deg}
#fxbeam,#fxpool{position:fixed;z-index:70;pointer-events:none;display:none;opacity:0}
#fxbeam{padding:1.5px;
  background:conic-gradient(from var(--ang),transparent 0 52%,var(--bc,var(--brand)) 72%,
    #fff 81%,var(--bc,var(--brand)) 90%,transparent 98%);
  -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
  -webkit-mask-composite:xor;mask-composite:exclude}
#fxpool{background:radial-gradient(circle at var(--px,50%) var(--py,50%),
    var(--pc,rgba(210,216,235,.16)),transparent 60%);mix-blend-mode:screen}
body:not(.calm) #fxbeam.go,body:not(.calm) #fxpool.on{display:block}
#fxbeam.go{animation:beam .78s var(--ez)}
/* 不用 fill：播完 opacity 自己回到 0 ⇒ "光走了不留痕"是可断言的，而不是靠 JS 记时清类 */
@keyframes beam{0%{opacity:0;--ang:var(--a0,0deg)}14%{opacity:1}84%{opacity:1}
  100%{opacity:0;--ang:calc(var(--a0,0deg) + 360deg)}}
#chipmark{position:absolute;bottom:-1px;height:2px;border-radius:2px;left:0;width:0;
  background:var(--brand);opacity:0;pointer-events:none;
  transition:left .34s var(--ez),width .34s var(--ez),opacity .2s var(--ez)}
#chips{position:relative}
/* 磁吸：只有主操作与左轨会朝指针让出 2px，普通按钮不让（它们挨得太近会晃）。
   写全 transition 列表而不是只写 transform —— 简写会连带抹掉底色/描边的过渡。 */
.mag{transition:transform .55s var(--ez),background .16s var(--ez),
  border-color .16s var(--ez),box-shadow .2s var(--ez),opacity .16s}

/* ══ 主屏：一次只暴露下一步 ═══════════════════════════════════════════
   整块版面只回答一个问题：**"现在该做什么，点下去会发生什么"**。
   13 个阶段、日志、对照表、指纹全部搬进「细节」抽屉——那是证据，不是决策。
   ⚠️ 主屏**没有面板**：大字直接坐在夜面上。可读性不靠半透明纱来救
      （alpha .90 的"已经很实"实测仍会被一颗星在字下面顶出 36 级差异），
      而是靠**星野在文字区主动避让**（见 starsLight 的 avoid 矩形）——
      装饰给数据让路，是让装饰让步，不是给数据蒙一层膜。 */
.now{flex:1 1 auto;min-height:0;display:flex;flex-direction:column;justify-content:center;
  padding:0 var(--s6);max-width:1060px;margin:0 auto;width:100%;position:relative;z-index:2}
.eyebrow{margin:0 0 var(--s4);font:400 11.5px/1 var(--fm);letter-spacing:.2em;color:var(--dim);
  display:flex;align-items:center;gap:var(--s2)}
.eyebrow i{width:5px;height:5px;border-radius:50%;background:var(--brand);flex:0 0 auto}
/* 唯一的大字。CJK 走雅黑 Light —— 中文界面上"简约"几乎只能靠字重与留白做出来，
   细体大字 + 紧行距比任何装饰都干净。 */
.ask{margin:0;font:300 clamp(30px,4.3vw,52px)/1.18 var(--fb);letter-spacing:-.015em;
  color:var(--txt);max-width:20ch}
.ask b{font-weight:500;color:#fff}
.ask em{font-style:normal;font-family:var(--fd);font-weight:600;letter-spacing:-.01em;
  font-variant-numeric:tabular-nums;color:#fff}
.why{margin:var(--s4) 0 0;font-size:14px;line-height:1.65;color:var(--dim);max-width:48ch}
.do{display:flex;align-items:center;gap:var(--s5);margin:var(--s6) 0 0;flex-wrap:wrap}
/* 主行动：全站唯一一块实心。静止时一动不动，表现力全部留给"被操作那一瞬"
   （压缩 + 弹簧回弹 + 把光泄进背景星野，见 JS spring 与 pointerdown）。 */
.pact{font:500 15px/1 var(--fb);letter-spacing:.01em;padding:15px 26px;
  border-radius:var(--r-ctl);border:1px solid var(--brand);background:var(--brand);
  color:#0a0b10;cursor:pointer;display:inline-flex;align-items:center;gap:10px;
  will-change:transform;transition:background .18s var(--ez),border-color .18s var(--ez)}
/* ⚠️ color 必须显式重写：`button:hover{color:var(--txt)}` 是 (0,1,1)，压过 `.pact` 的
   (0,1,0) ⇒ hover 时底色走 --brand-hi（近白）而字色被拽成 --txt（近白）= 白底白字。 */
.pact:hover{background:var(--brand-hi);border-color:var(--brand-hi);color:#0a0b10}
.pact.sign{background:transparent;border-color:rgba(242,189,114,.6);color:var(--await)}
.pact.sign:hover{background:rgba(242,189,114,.14);border-color:var(--await)}
.pact:disabled{opacity:.35;cursor:not-allowed}
.link2{background:none;border:0;padding:9px 1px;color:var(--dim);font-size:13.5px;
  cursor:pointer;position:relative}
.link2:hover{color:var(--txt)}
.link2::after{content:'';position:absolute;left:0;right:0;bottom:5px;height:1px;
  background:currentColor;transform:scaleX(0);transform-origin:right;
  transition:transform .34s var(--ez)}
.link2:hover::after{transform:scaleX(1);transform-origin:left}
.foot{margin:var(--s5) 0 0;font-size:12.5px;color:var(--await);min-height:19px}
/* 这三块必须**贴着内容**撑开：block 元素默认拉满 .now 的 1060px，
   那会让「星野避让」矩形横盖半屏 —— 实测把"划过才显影"判成对鼠标没反应。 */
.eyebrow,.do,.foot{align-self:flex-start;max-width:fit-content}
.eyebrow.red i{background:var(--fail)}
.eyebrow.red{color:var(--fail)}
.eyebrow.run i{background:var(--run);animation:pulse 1.1s infinite}
/* 换句：旧句淡出上移、新句从下方顶进来。**只在内容真的变了时加**，
   所以 8 秒轮询不会让它重播（和 `.stage.in` 同一条纪律）。 */
@keyframes swapin{from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:none}}
.ask.swap{animation:swapin .42s var(--ez)}
#detail .body{transform:translateX(100%)}
#detail{transition:opacity .2s var(--ez)}
#detail .veil{animation:fadein .26s var(--ez)}
@keyframes fadein{from{opacity:0}}
body.calm #detail .body{transition:none}

/* ══ 底部步骤条：一根会**长过去**的进度线 + 五个节点 ══════════════════
   取代左轨那四张大块。节点上仍带该步全部阶段的状态方块 —— 13 个阶段
   一个都不许被藏起来，这是上一版就立的判据，换了版面也得保住。 */
.steps{flex:0 0 auto;position:relative;z-index:3;display:flex;align-items:flex-start;
  justify-content:space-between;gap:var(--s4);padding:var(--s5) var(--s6) var(--s6);
  max-width:1060px;margin:0 auto;width:100%}
.steps .track{position:absolute;left:calc(var(--s6) + 44px);right:calc(var(--s6) + 44px);
  top:calc(var(--s5) + 13px);height:1px;background:var(--line);pointer-events:none}
.steps .fill{position:absolute;left:0;top:-1px;height:3px;border-radius:3px;width:0;
  background:var(--brand);transform-origin:left center;pointer-events:none}
.snode{position:relative;display:flex;flex-direction:column;align-items:center;gap:7px;
  background:none;border:0;padding:0;cursor:pointer;color:var(--dim2);min-width:88px}
.snode .bead{width:9px;height:9px;border-radius:50%;background:var(--pane);
  border:1px solid var(--line2);transition:background .2s var(--ez),border-color .2s var(--ez),
  box-shadow .2s var(--ez)}
.snode:hover .bead{border-color:var(--line3)}
.snode.on .bead{background:var(--brand);border-color:var(--brand)}
.snode.done .bead{background:var(--pass);border-color:var(--pass)}
.snode.fail .bead{background:var(--fail);border-color:var(--fail)}
.snode.await .bead{background:var(--await);border-color:var(--await)}
.snode.run .bead{background:var(--run);border-color:var(--run);animation:pulse 1.1s infinite}
.snode label{font:500 12.5px/1 var(--fb);letter-spacing:.01em;color:var(--dim);
  transition:color .2s var(--ez)}
.snode.on label{color:var(--txt)}
.snode .sdots{display:flex;gap:3px;align-items:center}
.snode .cnt{font:10.5px/1 var(--fm);color:var(--dim2)}
/* 每一步自己带一条**会长的进度条**（用户："这四步主页不能加个运行中和进度条吗"）。
   静止时它是静态的（只有宽度，没有动画），跑起来才由 gaugeTick 推进。 */
.snode .sfill{display:block;width:72px;height:3px;border-radius:2px;background:var(--line);
  overflow:hidden;margin-top:3px}
.snode .sfill i{display:block;height:100%;width:0;background:var(--dim2);border-radius:2px}
.snode.run .sfill i{background:var(--run);transition:width .45s var(--ez)}
.snode.done .sfill i{background:var(--pass);width:100%}
.snode.fail .sfill i{background:var(--fail)}
.runline{display:none;align-items:center;gap:var(--s3);margin:0 auto;max-width:1060px;
  width:100%;padding:0 var(--s6);
  font:11.5px/1 var(--fm);color:var(--dim);font-variant-numeric:tabular-nums}
.runline.on{display:flex}
.runline b{color:var(--run);font-weight:600}
.runline .rl-stage{color:var(--txt2);max-width:30ch;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
/* 旧版左轨那套（四张大块 + 图例面板）整体退役，只挂在 legacy 下给 V 键对照用 */
/* ══ 细节抽屉：证据都在这儿 ═══════════════════════════════════════════
   抽屉里的东西**一律不透明**（延续那条用三轮换来的纪律），主屏才允许坐在夜面上。 */
#detail{position:fixed;inset:0;z-index:50;display:none}
#detail.on{display:block}
#detail .veil{position:absolute;inset:0;background:rgba(4,5,9,.6);backdrop-filter:blur(2px)}
#detail .body{position:absolute;right:0;top:0;bottom:0;width:min(1180px,96vw);
  background:var(--deep);border-left:1px solid var(--line2);
  display:grid;grid-template-columns:minmax(400px,1fr) minmax(340px,.86fr);
  gap:var(--s4);padding:var(--s5);overflow:hidden;will-change:transform}
#detail .dhead{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;
  gap:var(--s4);margin-bottom:var(--s1)}
#detail .dhead h2{margin:0;font:500 17px/1.2 var(--fb);letter-spacing:-.01em;color:var(--txt)}
#detail .dhead .meters{flex:0 1 auto;justify-content:flex-end}
body:not(.legacy) #detail .col:first-of-type{order:1}
body:not(.legacy) #detail .col.side{order:2}

/* 列是 flex 容器：面板必须 flex-shrink:0，否则"内容比列高"时**每个面板都被压扁**，
   再叠上 overflow:hidden 就是把卡片和日志的下沿直接切掉（实测第二张卡被切 45px、
   日志被切 81px）。要滚的是列本身，不是把内容塞进固定高度的盒子里。 */
.col{min-height:0;overflow:auto;display:flex;flex-direction:column;gap:var(--s3);padding-right:2px}
.col>.pane{flex:0 0 auto}
/* 日志格给**确定的视口高度**，不要用 flex:1 去"填满剩余"：
   在 grid + overflow:auto 这套组合下它实测会塌成 28px（只剩标题条），
   把 pre 顶出面板外 170px。可预测比聪明重要。 */
.col>.logpane{flex:0 0 auto}
/* 面板层级 = **底色抬一档 + 一道发丝线 + 顶边 1px 微高光**，不挂投影。
   （Linear："Zero drop shadows… vertical depth relies exclusively on the
    background ladder and consistent boundary strokes."） */
.pane{position:relative;background:var(--pane);border:1px solid var(--line);
  border-radius:var(--r-card);padding:var(--pad-pane);box-shadow:var(--edge)}
/* 旧版面那根"紫→品红灯管"是大气渐变的典型指纹，新版面整条撤掉；
   挂在 legacy 下保留，`V` 键能当场比出差别。 */
body.legacy .pane{box-shadow:0 22px 46px -32px rgba(0,0,0,.92),
  inset 0 1px 0 rgba(214,200,255,.07)}
.pane::before{content:'';position:absolute;left:14px;right:14px;top:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(160,107,255,.62) 16%,
    rgba(255,61,127,.58) 58%,transparent);
  opacity:.42;transition:opacity .22s var(--ez);display:none}
body.legacy .pane::before{display:block}
body.legacy .pane:hover::before{opacity:1}
.ph{font:500 12px/1 var(--fb);letter-spacing:var(--ph-ls);text-transform:var(--tt);
  color:var(--dim);
  margin:0 0 var(--s3);display:flex;align-items:center;justify-content:space-between;gap:var(--s2)}

.dots{display:flex;gap:3px;align-items:center;margin-top:6px}
.dot{width:7px;height:7px;border-radius:2px;background:var(--idle)}
.dot.pass{background:var(--pass)}.dot.fail{background:var(--fail)}
.dot.await{background:var(--await)}.dot.run{background:var(--run);animation:pulse 1.1s infinite}
.dot.hot{outline:2px solid var(--brand-hi);outline-offset:2px}
.legend{display:flex;flex-direction:column;gap:5px;font-size:11px;color:var(--dim)}
.legend .lrow{display:flex;gap:14px}
.legend .lrow span{display:flex;align-items:center;gap:6px}
.legend .sw{width:9px;height:9px;border-radius:3px;flex:0 0 auto}
@keyframes rise{from{opacity:0;transform:translateY(7px)}}
@keyframes pulse{50%{opacity:.25}}

/* ══ 工作区 ═══════════════════════════════════════════════════════════ */
.g{display:flex;flex-direction:column;gap:var(--s2)}
/* 入场动画挂在 `.in` 上，**只有首次挂载才加**（见 render 里的 mounted 集合）。
   写在基础类上 = 每次数据刷新重建节点就重播一次，那就是"每 8 秒整屏闪一下"的根因。 */
.stage.in,.snode.in{animation:rise .44s var(--ez) backwards}
/* 卡片层级 = 底色比面板抬一档 + 发丝线；hover 再抬一档，**不投影、不上浮**。
   （Linear：hover 是"shift toward lighter backgrounds or higher surface tiers"。） */
.stage{position:relative;border:1px solid var(--line);border-radius:var(--r-card);
  padding:var(--s3) var(--s4);background:var(--card);
  transition:border-color .16s var(--ez),background .16s var(--ez)}
.stage:hover{border-color:var(--line2);background:var(--raise)}
body.legacy .stage:hover{transform:translateY(-1px);
  box-shadow:0 16px 30px -24px rgba(0,0,0,.9)}
/* 卡片左光条：从指针进入的那个高度向上下**点燃**，离开时收回原位；静止时只留 34% 的一截 */
.stage::before{content:'';position:absolute;left:0;top:12px;height:calc(100% - 24px);width:2px;
  border-radius:2px;background:var(--line2);opacity:.35;transform:scaleY(.34);
  transform-origin:50% var(--oy,50%);
  transition:opacity .18s var(--ez),background .18s var(--ez),transform .38s var(--ez)}
.stage:hover::before{opacity:1;transform:scaleY(1);background:var(--brand)}
body.legacy .stage:hover::before{box-shadow:0 0 16px -2px rgba(255,61,127,.8);
  background:linear-gradient(180deg,#a06bff,#ff3d7f)}
.stage.hot::before{background:var(--brand-hi);opacity:1;transform:scaleY(1)}
.stage.fail{border-left:3px solid var(--fail)}
.stage.await{border-left:3px solid var(--await)}
.srow{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.skey{font:600 13px/1.3 var(--fm);letter-spacing:0;color:var(--txt)}
/* 档位三枚一律中性色：只靠图标 + 字重 + 边框样式分级。
   ⚠️ 这里的中性灰**不许撞上五个状态色**（探针逐条比计算色值），
   否则又回到"一个 hue 负两件事"。 */
.tier{font:10.5px/1 var(--fb);padding:3px 7px;border-radius:var(--r-tag);
  border:1px solid var(--line);color:var(--dim);white-space:nowrap;
  background:rgba(255,255,255,.025)}
.tier.s{border-style:dashed;border-color:var(--line2);color:#b9bec7}
.tier.l{border-color:var(--line3);color:#d6dae1;font-weight:600}
.stt{margin-left:auto;font:11.5px/1 var(--fb);padding:4px 9px;border-radius:var(--r-pill);
  display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.stt::before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}
.stt.idle{background:rgba(63,90,110,.30);color:#a2a8b2}
.stt.pass{background:rgba(79,214,168,.14);color:var(--pass)}
.stt.fail{background:rgba(255,111,111,.16);color:var(--fail)}
.stt.await{background:rgba(242,189,114,.15);color:var(--await)}
.stt.run{background:rgba(95,208,232,.16);color:var(--run);animation:pulse 1.1s infinite}
.stitle{font-size:12.5px;color:var(--txt2);margin:6px 0 0}
.kv{display:grid;grid-template-columns:44px 1fr;gap:var(--s1) 9px;margin:var(--s2) 0 0;
  font-size:11.5px;color:var(--dim)}
.kv dt{color:var(--dim2);letter-spacing:.2px}
.kv dd{margin:0;font-family:var(--fm);font-size:11.5px;word-break:break-all;line-height:1.5;
  color:var(--txt2)}
.sact{display:flex;gap:var(--s2);align-items:center;margin-top:10px;flex-wrap:wrap}
.signbox{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--await);
  padding:3px 9px 3px 7px;border-radius:var(--r-ctl);border:1px solid rgba(242,189,114,.32);
  background:rgba(242,189,114,.07);position:relative;overflow:hidden}
.signbox input{accent-color:var(--await);width:14px;height:14px;margin:0;cursor:pointer}
.signbox.on{background:rgba(242,189,114,.16);border-color:var(--await);color:#ffe3b8}
body.legacy .signbox.on{box-shadow:0 0 16px -6px rgba(242,189,114,.75)}
/* 勾上签字 = 一团暖光从方框泄开，一次性，播完自己消失（静止时不留痕） */
.signbox.on::after{content:'';position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(circle at 14px 50%,rgba(242,189,114,.6),transparent 68%);
  animation:bloom .62s var(--ez) both}
@keyframes bloom{from{opacity:1;transform:scale(.55)}to{opacity:0;transform:scale(1.7)}}
.spacer{margin-left:auto}
.dim{color:var(--dim2)}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 var(--s2)}
.chip{font-size:11px;padding:var(--s1) var(--s2);border-radius:var(--r-chip);
  border:1px solid var(--line);background:transparent;color:var(--dim)}
.chip:hover{color:var(--txt);border-color:var(--line2)}
.chip.on{border-color:color-mix(in srgb,var(--brand) 55%,transparent);color:var(--txt);
  background:color-mix(in srgb,var(--brand) 13%,transparent)}
.kbd{font:10.5px/1 var(--fm);padding:3px 7px;border-radius:var(--r-tag);
  border:1px solid var(--line);color:var(--dim);background:var(--pane)}
.kbd b{color:var(--brand-hi);font-weight:600}

/* ══ 对照图：必须坐在完全不透明的底上 ═════════════════════════════════ */
/* 「这次新增了什么」那张表：数据密度优先，不挂装饰 */
.newt{width:100%;border-collapse:collapse;font:12px/1.5 var(--fb)}
.newt th{text-align:left;font:500 11px/1 var(--fb);letter-spacing:.02em;color:var(--dim);
  text-transform:none;padding:0 8px 6px 0;border-bottom:1px solid var(--line)}
.newt td{padding:5px 8px 5px 0;border-bottom:1px solid var(--line);color:var(--txt2);
  vertical-align:top}
.newt tr:last-child td{border-bottom:0}
.newt code{font:11.5px/1 var(--fm);color:var(--txt)}
.newt .warn{color:var(--await)}
.sheets{display:grid;grid-template-columns:repeat(auto-fill,minmax(238px,1fr));gap:10px}
.sheets a{display:block;border:1px solid var(--line);border-radius:var(--r-ctl);overflow:hidden;
  background:var(--abyss);text-decoration:none;color:inherit;
  transition:border-color .16s var(--ez),background .16s var(--ez)}
.sheets a:hover{border-color:var(--line2);background:var(--raise)}
body.legacy .sheets a:hover{transform:translateY(-2px)}
/* 图的衬底用**中性**深色，不用薰衣草底（它会给改前/改后的白平衡带偏判断） */
.sheets img{display:block;width:100%;height:196px;object-fit:contain;background:#0e0f13;
  cursor:zoom-in}
.sheets .cap{font-size:11px;color:var(--dim);padding:6px var(--s2);display:flex;
  justify-content:space-between;gap:var(--s2);border-top:1px solid var(--line)}

/* ══ 日志 / 任务 ══════════════════════════════════════════════════════ */
pre{margin:0;font:11.5px/1.6 var(--fm);white-space:pre-wrap;word-break:break-all;
  background:var(--abyss);border:1px solid var(--line);border-radius:var(--r-ctl);
  padding:10px var(--s3);overflow:auto;color:var(--txt2);height:40vh;min-height:170px}
pre .good{color:var(--pass)}pre .bad{color:var(--fail)}
.runs{width:100%;border-collapse:collapse;font-size:12px}
.runs th{font:500 11px/1 var(--fb);letter-spacing:var(--ph-ls);text-transform:var(--tt);
  color:var(--dim);text-align:left;padding:0 6px 7px;border-bottom:1px solid var(--line)}
body.legacy .runs th{font-weight:600;font-family:var(--fd)}
/* 表格行分隔 = 1px 底描边（Linear 的 data row 就是这个做法） */
.runs td{padding:7px 6px;border-bottom:1px solid var(--line);vertical-align:top}
.runs tr:last-child td{border-bottom:none}
.tag{font:10.5px/1 var(--fb);padding:3px 7px;border-radius:var(--r-tag);white-space:nowrap}
.tag.done{background:rgba(79,214,168,.13);color:var(--pass)}
.tag.running{background:rgba(95,208,232,.14);color:var(--run);animation:pulse 1.1s infinite}
.tag.gone,.tag.donedirty{background:rgba(255,111,111,.14);color:var(--fail)}

/* ══ 使用说明抽屉 ══════════════════════════════════════════════════════ */
#help{position:fixed;inset:0;z-index:60;display:none}
#help.on{display:block}
#help .veil{position:absolute;inset:0;background:rgba(3,4,8,.7);backdrop-filter:blur(3px)}
/* 抽屉是**最高一档表面**：靠比页面更亮的底色 + 一道描边分层，不靠大投影 */
#help .panel{position:absolute;right:0;top:0;bottom:0;width:min(660px,94vw);overflow:auto;
  background:var(--pane);border-left:1px solid var(--line2);
  padding:22px var(--s5) 40px;animation:slide .32s var(--ez)}
body.legacy #help .panel{background:linear-gradient(180deg,#141024,#0c0817);
  box-shadow:-30px 0 70px -30px #000}
@keyframes slide{from{transform:translateX(28px);opacity:.6}}
#help h3{font:500 14px/1.3 var(--fb);margin:var(--s5) 0 var(--s2);letter-spacing:-.1px;
  color:var(--brand-hi)}
#help h3:first-of-type{margin-top:4px}
#help p,#help li{font-size:13px;color:var(--txt2)}
#help ul{margin:6px 0;padding-left:20px}
#help li{margin:4px 0}
#help table{width:100%;border-collapse:collapse;font-size:12.5px;margin:8px 0;
  table-layout:fixed}
#help table td:first-child,#help table th:first-child{width:7.4em;white-space:nowrap}
#help table td:nth-child(2){width:42%}
#help th,#help td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;
  vertical-align:top}
#help th{font:500 11px/1 var(--fb);letter-spacing:var(--ph-ls);text-transform:var(--tt);
  color:var(--dim)}
#help code{font:11.5px/1.5 var(--fm);background:color-mix(in srgb,var(--brand) 12%,transparent);padding:1px 6px;
  border-radius:var(--r-tag);color:var(--brand)}
#help .close{position:sticky;top:0;float:right}
#help .hmode{display:flex;align-items:center;gap:7px;margin:0 0 var(--s4);
  padding-bottom:var(--s3);border-bottom:1px solid var(--line)}
#help .hmode .seg{font:500 12px/1 var(--fb);padding:6px 13px;border-radius:999px;
  border:1px solid var(--line);background:transparent;color:var(--txt2);cursor:pointer;
  transition:color .16s var(--ez),border-color .16s var(--ez),background .16s var(--ez)}
#help .hmode .seg.on{color:var(--txt);border-color:var(--brand);
  background:color-mix(in srgb,var(--brand) 14%,transparent)}
#help .hmode .hmodenote{font-size:11.5px;color:var(--txt2);margin-left:2px}
body.hsimple #help .dt{display:none}
.warn{background:rgba(255,111,111,.10);border:1px solid rgba(255,111,111,.34);
  border-radius:var(--r-ctl);
  padding:9px 12px;font-size:12.5px;color:#ffc2c2;margin-bottom:11px;display:none}
.warn.on{display:block}
#lightbox{position:fixed;inset:0;background:rgba(2,7,12,.95);display:none;z-index:99;
  align-items:center;justify-content:center;cursor:zoom-out}
#lightbox.on{display:flex}
#lightbox img{max-width:96vw;max-height:96vh;object-fit:contain}
/* ── M 键「动效从简」：整层光效停用，但**状态指示一个都不跟着没** ──────────
   #stepfill 表达的是"当前在哪一步"，那是信息不是装饰 ⇒ 只掐它的位移，不掐它本身。 */
body.calm #fxbeam,body.calm #fxpool{display:none!important}
body.calm #stepfill,body.calm #chipmark{transition:none}
body.calm .mag{transition:none}
body.calm .stage::before{transform:none!important}
body.calm .signbox.on::after{display:none}
@media (max-width:1080px){#detail .body{grid-template-columns:1fr;overflow:auto}
  .now{padding:0 var(--s5)} .steps{padding-left:var(--s5);padding-right:var(--s5)}
  .ask{font-size:clamp(26px,6.2vw,38px)}}
/* ══ 进度台：只在"真的在跑"时出现的一条细带 ═══════════════════════════
   四个量都是**服务端算出来的事实**（见 gauge_safe）：已用 / 内存 / 阶段 N/M / 剩余。
   「剩余」按各阶段**历史均值**算；有阶段没样本时报「≥」下限，不拿百分比糊一个数。
   放在最后是有意的：下面这些规则要压过基础层 `button{cursor:pointer}` 一类。 */
.gauge{display:none;align-self:stretch;max-width:fit-content;margin:0 0 var(--s4);width:100%;
  flex-direction:column;align-items:stretch;gap:9px;padding:10px 14px 12px;
  border-radius:var(--r-ctl);border:1px solid var(--line);background:var(--pane);
  font:11.5px/1 var(--fm);color:var(--dim);font-variant-numeric:tabular-nums}
.gauge.on{display:flex}
.gauge .grow{display:flex;align-items:center;gap:var(--s4);flex-wrap:wrap}
.gauge b{color:var(--txt);font-weight:600}
.gauge .gdot{width:6px;height:6px;border-radius:50%;background:var(--run);
  animation:pulse 1.1s infinite;flex:0 0 auto}
.gauge .gsep{width:1px;height:12px;background:var(--line2);flex:0 0 auto}
.gauge .gst{color:var(--txt2);max-width:26ch;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
.gauge .gnote{color:var(--dim2)}
/* 条要**够宽够高**才叫进度条：96×3 的细线实测被用户判成"看不出在动"（2026-10-01）。
   现在整幅宽 + 9px 高 + 每阶段一道刻度，填充按「已完成 + 本阶段内比例」走。 */
.gauge .gbar{position:relative;height:9px;border-radius:3px;width:100%;
  background:var(--deep);border:1px solid var(--line);overflow:hidden}
.gauge .gbar i{position:absolute;top:0;bottom:0;left:0;width:0;background:var(--run);
  transition:width .4s var(--ez)}
.gauge .gbar u{position:absolute;inset:0;display:flex;pointer-events:none}
.gauge .gbar u s{flex:1 1 0;border-right:1px solid var(--pane);text-decoration:none}
.gauge .gbar u s:last-child{border-right:0}
.gauge .gun{color:var(--txt2)}

/* ══ 指针：三态自定义光标（默认 / 可点 / 主行动）═══════════════════════
   和星野同一套语言：细十字 + 中心亮点，色温取 --brand（蓝白）。三条纪律：
     · 每个光标先描一道**深色底**（stroke #060b14）。主按钮 .pact 的底是近白，
       只画亮线的光标在那儿整根看不见 —— 这是自定义光标最常见的翻车方式。
     · hotspot 一律写死成十字交点 `12 12`。写 0 0 会让指针和判定点错位一格。
     · 输入框留系统 text、对照图留系统 zoom-in/out：那两处系统图标比自绘的准。 */
body{cursor:url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='24'%20height='24'%20viewBox='0%200%2024%2024'%3E%3Cg%20fill='none'%20stroke='%23060b14'%20stroke-width='3.6'%20stroke-linecap='round'%3E%3Cpath%20d='M12%201.5v6.6M12%2015.9v6.6M1.5%2012h6.6M15.9%2012h6.6'/%3E%3C/g%3E%3Cg%20fill='none'%20stroke='%23cfe0ff'%20stroke-width='1.15'%20stroke-linecap='round'%3E%3Cpath%20d='M12%201.5v6.6M12%2015.9v6.6M1.5%2012h6.6M15.9%2012h6.6'/%3E%3C/g%3E%3Ccircle%20cx='12'%20cy='12'%20r='1.7'%20fill='%23060b14'/%3E%3Ccircle%20cx='12'%20cy='12'%20r='1'%20fill='%23eef4ff'/%3E%3C/svg%3E") 12 12,crosshair}
a,button,.chip,.snode,.link2,.signbox,label,.runs tbody tr{cursor:url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='24'%20height='24'%20viewBox='0%200%2024%2024'%3E%3Cg%20fill='none'%20stroke='%23060b14'%20stroke-width='3.6'%20stroke-linecap='round'%3E%3Cpath%20d='M12%201.6v4.6M12%2017.8v4.6M1.6%2012h4.6M17.8%2012h4.6'/%3E%3C/g%3E%3Cg%20fill='none'%20stroke='%23cfe0ff'%20stroke-width='1.15'%20stroke-linecap='round'%3E%3Cpath%20d='M12%201.6v4.6M12%2017.8v4.6M1.6%2012h4.6M17.8%2012h4.6'/%3E%3C/g%3E%3Ccircle%20cx='12'%20cy='12'%20r='6.2'%20fill='none'%20stroke='%23cfe0ff'%20stroke-width='1'%20opacity='.7'/%3E%3Ccircle%20cx='12'%20cy='12'%20r='1.7'%20fill='%23060b14'/%3E%3Ccircle%20cx='12'%20cy='12'%20r='1'%20fill='%23eef4ff'/%3E%3C/svg%3E") 12 12,pointer}
.pact,button.go{cursor:url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='24'%20height='24'%20viewBox='0%200%2024%2024'%3E%3Cg%20fill='none'%20stroke='%23060b14'%20stroke-width='3.6'%20stroke-linecap='round'%3E%3Cpath%20d='M12%201.6v4.2M12%2018.2v4.2M1.6%2012h4.2M18.2%2012h4.2'/%3E%3C/g%3E%3Cg%20fill='none'%20stroke='%23cfe0ff'%20stroke-width='1.15'%20stroke-linecap='round'%3E%3Cpath%20d='M12%201.6v4.2M12%2018.2v4.2M1.6%2012h4.2M18.2%2012h4.2'/%3E%3C/g%3E%3Ccircle%20cx='12'%20cy='12'%20r='6.6'%20fill='none'%20stroke='%23cfe0ff'%20stroke-width='1.1'%20opacity='.85'/%3E%3Ccircle%20cx='12'%20cy='12'%20r='3.2'%20fill='%23060b14'/%3E%3Ccircle%20cx='12'%20cy='12'%20r='2.2'%20fill='%23eef4ff'/%3E%3C/svg%3E") 12 12,pointer}
button:disabled,.pact:disabled{cursor:not-allowed}
input,textarea{cursor:text}

@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
/* ══════════════════════════════════════════════════════════════════════
   2026-10-17 · 纸本控制台（Paper Runbook）
   ----------------------------------------------------------------------
   上一版是「夜航星野 + 海军蓝 + 指针光效」。用户要的是更新控制台的品质跃升，
   并明确排除蓝紫色调与 AI 味（渐变 / 玻璃 / 霓虹 / 星野）。这一层做四件事：
     ① 换底：暖纸 + 极淡工程网格；星野与指针光效整层退役。
     ② 换字：中文标题走衬线（Noto Serif SC），标签与数字走等宽，正文无衬线。
     ③ 换骨架：主屏左侧「当前指令」，右侧「五步索引」竖排；证据仍在抽屉里。
     ④ 换色：墨黑为唯一 chrome 色；彩色只留给状态（苔绿/朱砂/赭石/深青）。
   所有旧组件类名与 ID 一律保留，只覆盖外观 —— JS 的渲染路径一行不动。
   ══════════════════════════════════════════════════════════════════════ */
:root{
  --paper:#F1ECE2; --paper-2:#E8E0D2; --paper-3:#FBF7EF;
  --ink:#1D1A16; --ink-2:#57504A; --ink-3:#8A8174; --ink-4:#A79C8B;
  --rule:#D2C8B7; --rule-2:#B6A992;
  --accent:#A6432E; --accent-d:#7D3121; --accent-l:#F2E2DB;
  --moss:#4F6B4A; --moss-l:#E5EAE0;
  --ochre:#A9762A; --ochre-l:#F2E8D4;
  --teal:#3E6B63; --teal-l:#E0EAE7;

  --abyss:var(--paper); --deep:var(--paper); --pane:var(--paper-3);
  --card:var(--paper-3); --raise:var(--paper-2); --head:var(--paper);
  --line:var(--rule); --line2:var(--rule-2); --line3:var(--ink-3);
  --txt:var(--ink); --txt2:var(--ink-2); --dim:var(--ink-3); --dim2:var(--ink-4);
  --idle:var(--ink-3); --pass:var(--moss); --fail:var(--accent);
  --await:var(--ochre); --run:var(--teal);
  --brand:var(--ink); --brand-hi:#000; --pop:var(--accent);

  --fd:"Noto Serif SC","Source Han Serif SC","Songti SC",STSong,SimSun,Georgia,serif;
  --fb:"Noto Sans SC","Microsoft YaHei UI","Microsoft YaHei",system-ui,sans-serif;
  --fm:"Cascadia Mono","Consolas","SFMono-Regular",ui-monospace,monospace;
  --font-display:var(--fd); --font-ui:var(--fb); --font-mono:var(--fm);
  --ez:cubic-bezier(.32,.72,0,1);
  --r-tag:0; --r-chip:0; --r-ctl:0; --r-card:0; --r-pill:0;
  --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:24px; --s6:32px;
  --pad-pane:18px 20px;
  --elev:none; --edge:none;
  --tt:none; --ph-ls:.16em;
  --hero-fs:clamp(38px,4.6vw,58px); --hero-ls:.015em;
  --gutter:clamp(28px,5.2vw,92px);
}
body.night{
  --paper:#171512; --paper-2:#1E1B17; --paper-3:#221E19;
  --ink:#E9E1D2; --ink-2:#B8AE9C; --ink-3:#847B6D; --ink-4:#9A8F7E;
  --rule:#3A342B; --rule-2:#574E42;
  --accent:#D0704F; --accent-d:#E28A69; --accent-l:#2E211C;
  --moss:#8B9B7C; --moss-l:#232A1F;
  --ochre:#C2A05E; --ochre-l:#2C2618;
  --teal:#7FA79C; --teal-l:#1C2A27;

  --abyss:var(--paper); --deep:var(--paper); --pane:var(--paper-3);
  --card:var(--paper-3); --raise:var(--paper-2); --head:var(--paper);
  --line:var(--rule); --line2:var(--rule-2); --line3:var(--ink-3);
  --txt:var(--ink); --txt2:var(--ink-2); --dim:var(--ink-3); --dim2:var(--ink-4);
  --idle:var(--ink-3); --pass:var(--moss); --fail:var(--accent);
  --await:var(--ochre); --run:var(--teal);
  --brand:var(--ink); --brand-hi:#fff; --pop:var(--accent);
  background-image:
    linear-gradient(color-mix(in srgb,var(--ink) 1.7%,transparent) 1px,transparent 1px),
    linear-gradient(90deg,color-mix(in srgb,var(--ink) 1.7%,transparent) 1px,transparent 1px)!important;
  background-size:40px 40px!important;
}
*{box-sizing:border-box}
body{
  margin:0;overflow:hidden;color:var(--ink);
  font:13.5px/1.6 var(--font-ui);
  background-color:var(--paper)!important;
  background-image:
    linear-gradient(color-mix(in srgb,var(--ink) 2.4%,transparent) 1px,transparent 1px),
    linear-gradient(90deg,color-mix(in srgb,var(--ink) 2.4%,transparent) 1px,transparent 1px)!important;
  background-size:40px 40px!important;
  cursor:default!important;
}
body::after{
  content:'';position:fixed;inset:0;z-index:0;pointer-events:none;
  background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='180' height='180' filter='url(%23n)' opacity='.045'/%3E%3C/svg%3E");
  opacity:.55;
}
#bgfx{display:none!important}
#fxbeam,#fxpool{display:none!important}
a,button,.chip,.snode,.link2,.signbox,label,.runs tbody tr{cursor:pointer!important}
input,textarea{cursor:text!important}
button:disabled,.pact:disabled{cursor:not-allowed!important}
::selection{background:var(--accent);color:var(--paper-3)}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-thumb{background:var(--rule-2);border:2px solid transparent;background-clip:content-box;border-radius:0}
::-webkit-scrollbar-thumb:hover{background:var(--ink-3);background-clip:content-box}

/* ── 骨架：左「当前指令」 / 右「五步索引」 ─────────────────────────── */
.app{
  position:relative;z-index:1;height:100vh;
  display:grid!important;
  grid-template-columns:minmax(0,1fr) 340px;
  grid-template-rows:auto auto 1fr auto;
  grid-template-areas:"head head" "warn warn" "now steps" "run steps";
}
header{grid-area:head}
#warn{grid-area:warn}
.now{grid-area:now}
.steps{grid-area:steps}
.runline{grid-area:run}

header{
  background:var(--paper)!important;border:0!important;
  border-bottom:1px solid var(--ink)!important;
  box-shadow:none!important;
  padding:17px var(--gutter)!important;gap:36px!important;
  position:relative;z-index:10;
}
header::after{display:none!important}
.brand{gap:14px!important}
.brand svg{width:26px;height:26px;color:var(--ink);flex:none}
.brand h1{
  font:500 19px/1.25 var(--font-display)!important;
  letter-spacing:.09em;color:var(--ink)!important;
}
.brand p{
  margin:4px 0 0!important;font:400 7.5px/1 var(--font-mono)!important;
  letter-spacing:.24em;color:var(--ink-3)!important;
}
.act{gap:0!important;align-items:center;margin-left:auto!important}
header .act button{
  background:none!important;border:0!important;
  border-bottom:1px solid var(--rule-2)!important;border-radius:0!important;
  padding:4px 0!important;margin-left:20px;
  font:400 9.5px/1.5 var(--font-mono)!important;letter-spacing:.08em;
  color:var(--ink-2)!important;box-shadow:none!important;
  transition:color .16s,border-color .16s!important;
}
header .act button:hover{
  color:var(--accent)!important;border-bottom-color:var(--accent)!important;
  background:none!important;transform:none!important;
}
header .kbd{
  background:none!important;border:0!important;border-left:1px solid var(--rule)!important;
  border-radius:0!important;padding:2px 0 2px 16px!important;margin-left:18px;
  font:400 8px/1.6 var(--font-mono)!important;letter-spacing:.06em;
  color:var(--ink-3)!important;
}
header .kbd b{color:var(--ink-2)!important;font-weight:600}

/* ── 主屏：一句话 + 一个行动 ─────────────────────────────────────── */
.now{
  display:flex!important;flex-direction:column!important;justify-content:center!important;
  align-self:stretch!important;height:100%;min-height:0;position:relative;
  max-width:920px!important;width:auto!important;margin:0!important;
  padding:24px 44px 76px var(--gutter)!important;
}
.rails{
  display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;
  margin:38px 0 0!important;border-top:1px solid var(--rule)!important;
}
.rail{
  padding:14px 20px 0 0!important;border-right:1px solid var(--rule)!important;
  min-width:0;
}
.rail:last-child{border-right:0!important;padding-right:0!important}
.rail span{
  display:block;font:500 8px/1.4 var(--font-mono)!important;letter-spacing:.18em;
  color:var(--ink-3)!important;text-transform:uppercase;
}
.rail b{
  display:block;margin-top:7px;
  font:500 13px/1.4 var(--font-display)!important;letter-spacing:.04em;
  color:var(--ink)!important;font-weight:500!important;
}
.rail p{
  margin:6px 0 0!important;font:400 11px/1.75 var(--font-ui)!important;
  color:var(--ink-2)!important;
}
.foot{
  position:absolute!important;left:var(--gutter)!important;right:44px!important;bottom:0!important;
  margin:0!important;min-height:0!important;
  padding:13px 0 18px!important;width:auto!important;max-width:none!important;
  border-top:1px solid var(--rule);
  font:400 9.5px/1.8 var(--font-mono)!important;letter-spacing:.03em;
  color:var(--ochre)!important;
}
.foot:empty::after{
  content:'READ ONLY · 预检不写盘 · 所有写操作都要签字';
  color:var(--ink-3);letter-spacing:.12em;font-size:8px;
}
.eyebrow{
  margin:0 0 26px!important;
  font:500 9px/1.5 var(--font-mono)!important;letter-spacing:.24em!important;
  text-transform:uppercase;color:var(--ink-3)!important;
  display:flex!important;align-items:center;gap:12px!important;
}
.eyebrow i{
  width:30px!important;height:1px!important;border-radius:0!important;
  background:var(--accent)!important;flex:0 0 auto;
}
.eyebrow.red i{background:var(--fail)!important}
.eyebrow.run i{background:var(--run)!important;animation:none!important}
.stepstate{
  margin-left:4px;padding:2px 6px;
  font:500 8px/1.4 var(--font-mono)!important;letter-spacing:.12em;
  border:1px solid var(--rule);color:var(--ink-3)!important;
}
.stepstate.cur{color:var(--accent)!important;border-color:var(--accent)!important}
.stepstate.preview{color:var(--ochre)!important;border-color:var(--ochre)!important}
.viewnote{
  display:flex!important;align-items:center;gap:16px;
  margin:0 0 18px!important;padding:9px 13px!important;
  border:1px solid var(--ochre)!important;border-left:3px solid var(--ochre)!important;
  background:var(--ochre-l)!important;color:var(--ochre)!important;
  font:400 10px/1.65 var(--font-mono)!important;
}
.viewnote[hidden]{display:none!important}
.viewnote b{color:var(--ink)!important;font-weight:600!important}
.viewnote .link2{margin-left:auto!important;border-bottom-color:var(--ochre)!important;color:var(--ochre)!important;white-space:nowrap}
.ask{
  margin:0!important;
  font:500 var(--hero-fs)/1.16 var(--font-display)!important;
  letter-spacing:var(--hero-ls)!important;
  color:var(--ink)!important;max-width:24ch!important;
  word-break:keep-all;overflow-wrap:anywhere;
}
.ask b{font-weight:600!important;color:var(--ink)!important}
.ask em{
  font:500 .92em/1 var(--font-mono)!important;font-style:normal!important;
  letter-spacing:-.02em;color:var(--accent)!important;
}
.why{
  margin:22px 0 0!important;max-width:58ch!important;
  font:400 13px/1.95 var(--font-ui)!important;color:var(--ink-2)!important;
  overflow-wrap:anywhere;
}
/* 卡点独立成块：红只出现在左边一条细线上，正文仍是墨色 —— 不是第二个"红字警告"，
   而是「这一步为什么先停」的一张便笺。 */
.gate{
  margin:26px 0 0!important;max-width:64ch!important;
  padding:15px 18px 14px!important;
  background:var(--paper-3)!important;
  border:1px solid var(--rule)!important;border-left:3px solid var(--fail)!important;
  border-radius:0!important;
}
.gate[hidden]{display:none!important}
.gate .gt{
  display:block;font:600 10px/1.5 var(--font-mono)!important;
  letter-spacing:.16em;text-transform:uppercase;color:var(--fail)!important;
}
.gate .gb{
  margin:8px 0 0!important;max-width:60ch;
  font:400 12.5px/1.9 var(--font-ui)!important;color:var(--ink-2)!important;
}
.gate .ga{
  display:flex!important;align-items:center!important;gap:22px!important;
  margin:13px 0 0!important;flex-wrap:wrap!important;
}
.gate .ga .pact{padding:10px 18px!important;font-size:12px!important}
.receipt{
  margin:16px 0 0!important;max-width:70ch!important;
  padding:2px 0 2px 12px!important;border-left:2px solid var(--rule)!important;
  font:400 11px/1.75 var(--font-mono)!important;letter-spacing:.02em;
  color:var(--ink-3)!important;overflow-wrap:anywhere;
}
.receipt[hidden]{display:none!important}
.receipt.run{border-left-color:var(--run)!important;color:var(--run)!important}
.receipt.good{border-left-color:var(--moss)!important;color:var(--moss)!important}
.receipt.await{border-left-color:var(--ochre)!important;color:var(--ochre)!important}
.receipt.bad{border-left-color:var(--fail)!important;color:var(--fail)!important}
.do{
  display:flex!important;align-items:center!important;gap:26px!important;
  margin:36px 0 0!important;flex-wrap:wrap!important;
}
.pact{
  font:500 13.5px/1 var(--font-ui)!important;letter-spacing:.1em!important;
  padding:15px 28px!important;border-radius:0!important;
  border:1px solid var(--ink)!important;background:var(--ink)!important;
  color:var(--paper-3)!important;box-shadow:none!important;
  display:inline-flex!important;align-items:center!important;gap:10px!important;
}
.pact:hover{
  background:var(--accent)!important;border-color:var(--accent)!important;
  color:var(--paper-3)!important;transform:none!important;
}
.pact.sign{
  background:transparent!important;border-color:var(--ochre)!important;
  color:var(--ochre)!important;
}
.pact.sign:hover{background:var(--ochre-l)!important;color:var(--ochre)!important}
.pact:disabled{opacity:.35!important}
.link2{
  background:none!important;border:0!important;border-bottom:1px solid var(--rule)!important;
  border-radius:0!important;padding:7px 0!important;
  font:400 10px/1.5 var(--font-mono)!important;letter-spacing:.08em;
  color:var(--ink-3)!important;
}
.link2:hover{color:var(--accent)!important;border-bottom-color:var(--accent)!important}
.link2::after{display:none!important}
.gauge{
  display:none!important;max-width:none!important;width:100%!important;
  margin:28px 0 0!important;padding:14px 18px!important;
  background:var(--paper-3)!important;border:1px solid var(--rule)!important;
  border-left:3px solid var(--run)!important;border-radius:0!important;
  box-shadow:none!important;font:400 10px/1.6 var(--font-mono)!important;
  color:var(--ink-3)!important;gap:11px!important;
}
.gauge.on{display:flex!important}
.gauge b{color:var(--ink)!important;font-weight:600!important}
.gauge .gdot{
  width:5px!important;height:5px!important;border-radius:0!important;
  background:var(--run)!important;animation:none!important;
}
.gauge .gsep{width:1px!important;height:11px!important;background:var(--rule)!important}
.gauge .gst{color:var(--ink-2)!important}
.gauge .gnote{color:var(--ink-3)!important}
.gauge .gbar{
  height:3px!important;border-radius:0!important;
  background:var(--rule)!important;border:0!important;
}
.gauge .gbar i{background:var(--run)!important;border-radius:0!important}
.gauge .gbar u s{border-right:1px solid var(--paper-3)!important}

/* ── 右栏：五步索引 ──────────────────────────────────────────────── */
.steps{
  display:flex!important;flex-direction:column!important;
  justify-content:center!important;align-items:stretch!important;
  gap:0!important;max-width:none!important;width:auto!important;
  margin:0!important;padding:0 var(--gutter) 0 28px!important;
  border-left:1px solid var(--rule)!important;
  position:relative;z-index:3;
  counter-reset:snode;
}
.rail-hd{
  order:-2;display:flex!important;align-items:baseline;justify-content:space-between;
  padding:0 0 12px;border-bottom:1px solid var(--ink);margin-bottom:2px;
}
.rail-hd span{font:500 8px/1 var(--font-mono)!important;letter-spacing:.26em;color:var(--ink-3)!important}
.rail-hd b{font:500 12px/1 var(--font-display)!important;letter-spacing:.12em;color:var(--ink)!important;font-weight:500}
.rail-ft{
  order:2;display:flex!important;align-items:baseline;justify-content:space-between;
  padding:12px 0 0;border-top:1px solid var(--rule);margin-top:2px;
  font:400 8px/1.6 var(--font-mono)!important;letter-spacing:.08em;color:var(--ink-3)!important;
}
.steps .track{display:none!important}
.snode{
  position:relative;display:grid!important;
  grid-template-columns:28px minmax(0,1fr) auto;
  grid-template-rows:auto auto auto;
  column-gap:12px;row-gap:7px;align-items:center;
  min-width:0!important;width:100%!important;
  padding:16px 0!important;border:0!important;
  border-top:1px solid var(--rule)!important;border-radius:0!important;
  background:none!important;text-align:left!important;
  color:var(--ink-3)!important;
  counter-increment:snode;
}
.snode:first-of-type{border-top:0!important}
.snode:last-of-type{border-bottom:0!important}
.snode::before{
  content:counter(snode,decimal-leading-zero);
  grid-column:1;grid-row:1;
  font:400 10px/1 var(--font-mono)!important;letter-spacing:.06em;
  color:var(--ink-3)!important;
}
.snode.on::before{color:var(--accent)!important}
.snode.done::before{color:var(--pass)!important}
.snode.fail::before{color:var(--fail)!important}
.snode .bead{display:none!important}
.snode label{
  grid-column:2;grid-row:1;
  font:500 14px/1.35 var(--font-display)!important;
  letter-spacing:.05em;color:var(--ink-3)!important;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.snode.on label{color:var(--ink)!important;font-weight:600!important}
.snode .sdots{grid-column:2;grid-row:2;display:flex!important;gap:4px!important}
.snode .dot{width:5px!important;height:5px!important;border-radius:0!important;animation:none!important}
.snode .cnt{
  grid-column:3;grid-row:1;
  font:400 9px/1 var(--font-mono)!important;color:var(--ink-3)!important;
  letter-spacing:.04em;
}
.snode .sfill{
  grid-column:2/4;grid-row:3;display:block!important;
  width:100%!important;height:2px!important;border-radius:0!important;
  background:var(--rule)!important;margin-top:2px!important;overflow:hidden;
}
.snode .sfill i{background:var(--ink-3)!important;border-radius:0!important}
.snode.done .sfill i{background:var(--pass)!important}
.snode.run .sfill i{background:var(--run)!important}
.snode.fail .sfill i{background:var(--fail)!important}
.snode.on .bead{background:var(--accent)!important;border-color:var(--accent)!important}
.snode.done .bead{background:var(--pass)!important;border-color:var(--pass)!important}
.snode.fail .bead{background:var(--fail)!important;border-color:var(--fail)!important}
.snode.await .bead{background:var(--await)!important;border-color:var(--await)!important}
.snode.run .bead{background:var(--run)!important;border-color:var(--run)!important}
.snode:hover .bead{border-color:var(--ink)!important}
.snode:hover label{color:var(--ink)!important}
.snode.on .cnt{color:var(--accent)!important}
/* 「当前实际进度」与「正在查看」是两件事：on=你在看这一步，cur=机器真的停在这一步。
   只给 cur 加一颗实心点 + 强调色，避免用户点来点去后把预览当成实际进度。 */
.snode.cur .cnt{color:var(--accent)!important}
.snode.cur .cnt::before{
  content:'';display:inline-block;width:5px;height:5px;margin-right:5px;
  background:var(--accent);vertical-align:1px;
}
.runline{
  max-width:none!important;width:auto!important;margin:0!important;
  padding:10px var(--gutter) 14px!important;
  border-top:1px solid var(--rule)!important;
  font:400 9px/1.6 var(--font-mono)!important;letter-spacing:.04em;
  color:var(--ink-3)!important;
}
.runline.on{display:flex!important}
.runline b{color:var(--run)!important}
#warn{
  margin:10px var(--gutter) 0!important;padding:10px 14px!important;
  background:var(--accent-l)!important;border:1px solid var(--accent)!important;
  border-left:3px solid var(--accent)!important;border-radius:0!important;
  font:400 11px/1.65 var(--font-ui)!important;color:var(--accent-d)!important;
}
#warn.on{display:block!important}

/* ── 细节抽屉：纸面 + 黑色电传日志 ───────────────────────────────── */
#detail .veil{background:rgba(24,21,17,.46)!important;backdrop-filter:none!important}
#detail .body{
  width:min(1320px,97vw)!important;
  background:var(--paper)!important;border-left:1px solid var(--ink)!important;
  padding:26px 26px 26px 30px!important;gap:18px!important;
  grid-template-columns:minmax(560px,1.12fr) minmax(390px,.88fr)!important;
}
#detail .dhead{
  border-bottom:1px solid var(--rule);padding-bottom:15px;margin-bottom:2px;
  align-items:flex-end!important;gap:20px!important;
}
#detail .dhead h2{
  font:500 24px/1.2 var(--font-display)!important;letter-spacing:.06em;
  color:var(--ink)!important;
}
#detail .dhead .meters{justify-content:flex-start!important;gap:0!important}
.meter{
  background:none!important;border:0!important;border-left:1px solid var(--rule)!important;
  border-radius:0!important;padding:1px 0 1px 12px!important;margin-left:12px!important;
  font:400 9px/1.55 var(--font-mono)!important;color:var(--ink-3)!important;
}
.meter b{
  display:block!important;margin:0 0 3px!important;
  font:500 7px/1 var(--font-mono)!important;letter-spacing:.18em;
  color:var(--dim2)!important;
}
.meter.ok b,.meter.ok span{color:var(--pass)!important}
button{
  font:400 11px/1.4 var(--font-ui)!important;padding:6px 12px!important;
  border:1px solid var(--rule)!important;border-radius:0!important;
  background:transparent!important;color:var(--ink)!important;
  box-shadow:none!important;
}
button:hover{background:var(--paper-2)!important;border-color:var(--rule-2)!important;color:var(--ink)!important}
button:active{transform:none!important}
button.ghost{border-color:transparent!important;color:var(--ink-3)!important;padding:5px 0!important}
button.ghost:hover{background:none!important;color:var(--accent)!important}
button.help{border-color:var(--ink)!important;color:var(--ink)!important}
button.mini{font:400 9px/1.4 var(--font-mono)!important;padding:3px 8px!important}
button.go{
  background:var(--ink)!important;border-color:var(--ink)!important;
  color:var(--paper-3)!important;font-weight:600!important;
}
button.go:hover{background:var(--accent)!important;border-color:var(--accent)!important;color:var(--paper-3)!important}
button.sign{background:transparent!important;border-color:var(--ochre)!important;color:var(--ochre)!important}
button.sign:hover{background:var(--ochre-l)!important;border-color:var(--ochre)!important}
button:focus-visible{outline:1.5px solid var(--accent)!important;outline-offset:2px!important}

.pane{
  background:var(--paper-3)!important;border:1px solid var(--rule)!important;
  border-radius:0!important;padding:18px 20px!important;box-shadow:none!important;
}
.pane::before{display:none!important}
.ph{
  font:500 8px/1.3 var(--font-mono)!important;letter-spacing:.22em!important;
  text-transform:uppercase!important;color:var(--ink-3)!important;
  border-bottom:1px solid var(--rule);padding-bottom:9px;margin-bottom:12px!important;
}
.g{gap:0!important}
.stage{
  background:transparent!important;border:0!important;border-top:1px solid var(--rule)!important;
  border-radius:0!important;padding:12px 0 13px 14px!important;
  transition:background .16s!important;
}
.stage:first-child{border-top:0!important}
.stage:hover{
  background:var(--paper-2)!important;border-color:var(--rule)!important;
  transform:none!important;box-shadow:none!important;
}
.stage::before{
  left:0!important;top:13px!important;height:calc(100% - 26px)!important;
  width:2px!important;border-radius:0!important;background:var(--rule)!important;
  opacity:1!important;transform:none!important;transition:background .16s!important;
}
.stage:hover::before{background:var(--ink-3)!important;transform:none!important}
.stage.fail{border-left:0!important}
.stage.fail::before{background:var(--fail)!important}
.stage.await::before{background:var(--await)!important}
.stage.hot::before{background:var(--accent)!important}
.srow{gap:8px!important}
.skey{font:500 11.5px/1.35 var(--font-mono)!important;color:var(--ink)!important;letter-spacing:.02em}
.stitle{font:400 11px/1.65 var(--font-ui)!important;color:var(--ink-2)!important;margin-top:6px!important}
.tier{
  background:none!important;border:1px solid var(--rule)!important;border-radius:0!important;
  font:400 8.5px/1.4 var(--font-mono)!important;color:var(--ink-3)!important;
  padding:2px 6px!important;letter-spacing:.04em;
}
.tier.s{border-style:dashed!important;border-color:var(--rule-2)!important;color:var(--ink-2)!important}
.tier.l{border-color:var(--ink)!important;color:var(--ink)!important;font-weight:600!important}
.stt{
  background:none!important;border:1px solid currentColor!important;border-radius:0!important;
  font:500 8.5px/1.4 var(--font-mono)!important;padding:3px 7px!important;
  letter-spacing:.06em;animation:none!important;
}
.stt::before{width:4px!important;height:4px!important;border-radius:0!important}
.stt.idle{color:var(--idle)!important}
.stt.pass{color:var(--pass)!important}
.stt.fail{color:var(--fail)!important}
.stt.await{color:var(--await)!important}
.stt.run{color:var(--run)!important}
.kv{
  grid-template-columns:62px 1fr!important;gap:3px 10px!important;margin-top:10px!important;
  font:400 10px/1.65 var(--font-mono)!important;color:var(--ink-3)!important;
}
.kv dt{color:var(--dim2)!important;letter-spacing:.04em!important}
.kv dd{font-size:10px!important;color:var(--ink-2)!important;line-height:1.65!important}
.sact{gap:8px!important;margin-top:10px!important}
.signbox{
  background:none!important;border:1px solid var(--rule)!important;border-radius:0!important;
  padding:4px 8px!important;font:400 9px/1.4 var(--font-mono)!important;
  color:var(--await)!important;gap:6px!important;
}
.signbox.on{background:var(--ochre-l)!important;border-color:var(--await)!important;color:var(--await)!important}
.signbox.on::after{display:none!important}
.signbox input{accent-color:var(--await)!important;border-radius:0!important}
.spacer{margin-left:auto}
.dim{color:var(--dim2)!important}

/* 新增清单 / 对照表 / 最近任务 */
.newt{font:400 11px/1.65 var(--font-ui)!important}
.newt th{
  font:500 8px/1.4 var(--font-mono)!important;letter-spacing:.16em!important;
  color:var(--ink-3)!important;text-transform:uppercase;
  border-bottom:1px solid var(--ink)!important;padding:0 6px 7px!important;
}
.newt td{border-bottom:1px solid var(--rule)!important;padding:6px!important;color:var(--ink-2)!important}
.newt code{font:10px/1.4 var(--font-mono)!important;color:var(--ink)!important}
.newt .warn{color:var(--ochre)!important}
.sheets{gap:12px!important}
.sheets a{
  border:1px solid var(--rule)!important;border-radius:0!important;
  background:var(--paper-2)!important;
}
.sheets a:hover{border-color:var(--accent)!important;background:var(--paper-2)!important;transform:none!important}
.sheets img{height:196px!important;background:var(--paper-2)!important}
.sheets .cap{
  font:400 8.5px/1.5 var(--font-mono)!important;color:var(--ink-3)!important;
  border-top:1px solid var(--rule)!important;padding:6px 8px!important;
}
pre{
  background:#12100D!important;border:1px solid #2C2720!important;border-radius:0!important;
  color:#D9D0C0!important;font:10px/1.7 var(--font-mono)!important;
  padding:12px!important;height:34vh!important;min-height:170px;
}
pre .good{color:#A9C096!important}
pre .bad{color:#E08A69!important}
.logpane{background:#14110E!important;border-color:#14110E!important;color:#D9D0C0!important}
.logpane .ph{color:#A79C8B!important;border-bottom-color:#3A342B!important}
.logpane button{color:#B8AE9C!important;border-color:#3A342B!important}
.logpane button:hover{color:#E9E1D2!important;background:#221E19!important;border-color:#574E42!important}
.logpane .dim{color:#847B6D!important}
.runs{font:400 10px/1.6 var(--font-mono)!important}
.runs th{
  font:500 8px/1.4 var(--font-mono)!important;letter-spacing:.16em!important;
  color:var(--ink-3)!important;border-bottom:1px solid var(--ink)!important;padding:0 6px 7px!important;
}
.runs td{border-bottom:1px solid var(--rule)!important;padding:7px 6px!important;color:var(--ink-2)!important}
.tag{border-radius:0!important;font:400 8px/1.4 var(--font-mono)!important;padding:3px 6px!important}
.tag.done{background:var(--moss-l)!important;color:var(--pass)!important}
.tag.running{background:var(--teal-l)!important;color:var(--run)!important;animation:none!important}
.tag.gone,.tag.donedirty{background:var(--accent-l)!important;color:var(--fail)!important}
.chips{gap:4px!important;margin-bottom:10px!important}
.chip{
  background:transparent!important;border:1px solid var(--rule)!important;border-radius:0!important;
  font:400 8.5px/1.4 var(--font-mono)!important;padding:3px 8px!important;color:var(--ink-3)!important;
}
.chip:hover{color:var(--ink)!important;border-color:var(--rule-2)!important}
.chip.on{background:var(--ink)!important;border-color:var(--ink)!important;color:var(--paper-3)!important}
#chipmark{display:none!important}
.kbd{background:none!important;border:1px solid var(--rule)!important;border-radius:0!important;font:400 8px/1.4 var(--font-mono)!important;color:var(--ink-3)!important;padding:2px 5px!important}
.kbd b{color:var(--ink-2)!important}
.legend{font:400 9px/1.8 var(--font-mono)!important;color:var(--ink-3)!important;gap:4px!important}
.legend .sw{width:7px!important;height:7px!important;border-radius:0!important}

/* 使用说明：纸面手册 */
#help .veil{background:rgba(24,21,17,.46)!important;backdrop-filter:none!important}
#help .panel{
  background:var(--paper)!important;border-left:1px solid var(--ink)!important;
  box-shadow:none!important;padding:30px 38px 50px!important;width:min(700px,94vw)!important;
}
#help h3{
  font:500 16px/1.4 var(--font-display)!important;letter-spacing:.04em;
  color:var(--ink)!important;border-bottom:1px solid var(--rule);
  padding-bottom:8px;margin:26px 0 10px!important;
}
#help p,#help li{font:400 12px/1.95 var(--font-ui)!important;color:var(--ink-2)!important}
#help code{
  background:var(--paper-2)!important;border:1px solid var(--rule)!important;
  border-radius:0!important;color:var(--accent-d)!important;
  font:10px/1.5 var(--font-mono)!important;padding:1px 5px!important;
}
#help table{font:400 11px/1.7 var(--font-ui)!important}
#help th,#help td{border-bottom:1px solid var(--rule)!important;padding:7px 8px!important;color:var(--ink-2)!important}
#help th{font:500 8px/1.4 var(--font-mono)!important;letter-spacing:.16em!important;color:var(--ink-3)!important;text-transform:uppercase}
#help .hmode{border-bottom:1px solid var(--rule)!important}
#help .hmode .seg{
  border-radius:0!important;border:1px solid var(--rule)!important;
  font:400 9px/1.4 var(--font-mono)!important;color:var(--ink-3)!important;background:none!important;
}
#help .hmode .seg.on{background:var(--ink)!important;border-color:var(--ink)!important;color:var(--paper-3)!important}
#help .close{background:none!important;border:0!important;color:var(--ink-3)!important;font:400 10px/1.4 var(--font-mono)!important}
#help .close:hover{color:var(--accent)!important}
.warn{
  background:var(--accent-l)!important;border:1px solid var(--accent)!important;
  border-radius:0!important;color:var(--accent-d)!important;
}
#lightbox{background:rgba(24,21,17,.92)!important}

/* ── 签字窗口：和主界面同一套纸/墨/朱砂 ───────────────────────────── */
#signmodal{position:fixed;inset:0;z-index:80;display:none}
#signmodal.on{display:flex;align-items:center;justify-content:center}
#signmodal .veil{position:absolute;inset:0;background:rgba(24,21,17,.58)}
#signmodal .sheet{
  position:relative;width:min(640px,94vw);max-height:90vh;overflow:auto;
  background:var(--paper-3);border:1px solid var(--ink);
  box-shadow:0 30px 70px rgba(0,0,0,.26);padding:28px 30px 24px;
}
#signmodal .kicker{
  display:block;font:500 8px/1.4 var(--font-mono)!important;letter-spacing:.26em;
  color:var(--ink-3)!important;text-transform:uppercase;
}
#signmodal .kicker i{font-style:normal;color:var(--accent);margin:0 6px}
#signmodal h3{
  margin:10px 0 4px;font:500 28px/1.25 var(--font-display)!important;
  letter-spacing:.05em;color:var(--ink)!important;
}
#signmodal .shead p{
  margin:0 0 16px;font:400 11px/1.7 var(--font-mono)!important;
  color:var(--ink-3)!important;
}
#signmodal .slist{
  border-top:1px solid var(--ink);border-bottom:1px solid var(--rule);
  margin:0 0 14px;
}
#signmodal .srow{
  display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;
  padding:10px 0;border-bottom:1px solid var(--rule);
}
#signmodal .srow:last-child{border-bottom:0}
#signmodal .srow .k{
  font:500 11px/1.4 var(--font-mono)!important;color:var(--ink)!important;
  letter-spacing:.02em;
}
#signmodal .srow .t{
  display:block;margin-top:3px;font:400 10px/1.6 var(--font-ui)!important;
  color:var(--ink-2)!important;
}
#signmodal .srow .w{
  display:block;margin-top:4px;font:400 9px/1.6 var(--font-mono)!important;
  color:var(--ink-3)!important;
}
#signmodal .srow .tier{
  align-self:start;white-space:nowrap;font:400 8px/1.4 var(--font-mono)!important;
  padding:2px 6px;border:1px solid var(--rule);color:var(--ink-3)!important;
}
#signmodal .srow .tier.l{border-color:var(--accent)!important;color:var(--accent)!important}
#signmodal .snote{
  margin:0 0 16px;padding:9px 12px;
  border-left:2px solid var(--ochre);background:var(--ochre-l);
  font:400 10px/1.75 var(--font-mono)!important;color:var(--ochre)!important;
}
#signmodal .scheck{
  display:flex;gap:9px;align-items:flex-start;margin:0 0 12px;
  font:400 11px/1.7 var(--font-ui)!important;color:var(--ink-2)!important;
  cursor:pointer;
}
#signmodal .scheck input{accent-color:var(--accent);width:14px;height:14px;margin:2px 0 0;flex:none}
#signmodal .sigline{
  display:flex;gap:10px;align-items:baseline;
  padding:10px 0 0;border-top:1px solid var(--rule);
  font:400 9px/1.4 var(--font-mono)!important;color:var(--ink-3)!important;
}
#signmodal .sigline>span{letter-spacing:.16em;text-transform:uppercase}
#signmodal .sigline input{
  flex:1;min-width:0;border:0;border-bottom:1px solid var(--rule-2);
  background:transparent;padding:2px 2px 4px;
  font:500 14px/1.3 var(--font-display)!important;color:var(--ink)!important;
  outline:none;
}
#signmodal .sigline input:focus{border-bottom-color:var(--accent)}
#signmodal .sigline em{
  font-style:normal;font:400 9px/1.4 var(--font-mono);color:var(--ink-3);
  white-space:nowrap;
}
#signmodal .sact{
  display:flex;justify-content:flex-end;gap:10px;align-items:center;
  margin-top:20px;padding-top:14px;border-top:1px solid var(--rule);
}
#signmodal .sact .ghost{border-bottom:1px solid var(--rule)!important;padding:6px 0!important}
#signmodal .sact #signAlt{margin-right:auto!important;border-bottom-color:var(--ochre)!important;color:var(--ochre)!important}
#signmodal .sact .pact{padding:11px 22px!important;font-size:12px!important}
#signmodal .sact .pact:disabled{opacity:.3!important;cursor:not-allowed!important}

/* ── 窄屏：右栏折回底部横排 ─────────────────────────────────────── */
@media (max-width:1080px){
  .app{
    display:flex!important;flex-direction:column!important;height:100vh!important;
  }
  header{padding:14px 20px!important}
  .rail-hd,.rail-ft{display:none!important}
  .now{
    max-width:760px!important;margin:0 auto!important;
    padding:24px 20px 20px!important;
    flex:1 1 auto!important;height:auto!important;min-height:0!important;overflow:auto!important;
    /* 窄屏不能再垂直居中：加了卡点/回执之后内容会高过一屏，
       flex 的 center 会把顶部（查看提示）挤出可视区，而且滚不回去。 */
    justify-content:flex-start!important;
  }
  /* 三张边界说明是"为什么敢点"的背景知识，窄屏让位给当前决策；
     全文仍在「怎么用」里，不是删掉。 */
  .rails{display:none!important}
  .foot{margin-top:18px!important}
  .ask{font-size:clamp(30px,6vw,42px)!important;max-width:22ch!important}
  .rails{grid-template-columns:1fr!important}
  .rail{border-right:0!important;border-bottom:1px solid var(--rule)!important;padding:12px 0!important}
  .rail:last-child{border-bottom:0!important}
  .foot{position:static!important;margin-top:20px!important;padding-bottom:0!important}
  .now{padding-bottom:20px!important}
  .steps{
    flex-direction:row!important;align-items:flex-start!important;
    justify-content:space-between!important;
    border-left:0!important;border-top:1px solid var(--rule)!important;
    padding:16px 20px 20px!important;gap:8px!important;
  }
  .steps .track{display:none!important}
  .snode{
    display:flex!important;flex-direction:column!important;align-items:center!important;
    text-align:center!important;border-top:0!important;padding:0!important;gap:6px!important;
    flex:1 1 0;min-width:0!important;
  }
  .snode:last-child{border-bottom:0!important}
  .snode label{font-size:11.5px!important;white-space:normal!important}
  .snode .cnt{grid-column:auto;grid-row:auto}
  .snode .sdots{grid-column:auto;grid-row:auto}
  .snode .sfill{grid-column:auto;grid-row:auto;width:64px!important;margin-top:2px}
  #detail .body{grid-template-columns:1fr!important;overflow:auto}
}

</style></head><body>

<div id="bgfx" aria-hidden="true">
  <canvas id="nebula"></canvas><canvas id="stars"></canvas></div>

<div class="app">
<header>
  <div class="brand">
    <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <circle cx="13" cy="13" r="9.6" stroke="currentColor" stroke-width="1.1"/>
      <path d="M13 3.4v3.1M13 19.5v3.1M3.4 13h3.1M19.5 13h3.1"
            stroke="currentColor" stroke-width="1.1" stroke-linecap="square"/>
      <path d="M13 7.2l2.6 5.8L13 18.8l-2.6-5.8z" fill="var(--accent, #A6432E)"/>
      <circle cx="13" cy="13" r="1.1" fill="var(--paper-3, #FBF7EF)"/>
    </svg>
    <div><h1>资产更新控制台</h1><p>ASSET UPDATE CONSOLE · RUNBOOK 05</p></div>
  </div>
  <div class="act">
    <button id="bDetail" class="ghost" title="D：展开证据（全部阶段 / 日志 / 对照表 / 指纹）">细节</button>
    <button id="bSea" class="ghost" title="S：夜读模式 开/关（暖墨底，非旧版紫黑）">夜读 · 关</button>
    <span class="kbd" title="1-5 切步骤 · R 跑当前这一步 · D 细节 · P 只看计划 · H 帮助 · Esc 关闭 · S 夜读 · M 动效从简 · V 夜读">
      <b>1-5</b> 步骤 · <b>R</b> 跑 · <b>D</b> 细节</span>
    <button id="bHelp" class="help">怎么用</button>
  </div>
</header>

<div id="warn" class="warn"></div>

<!-- 主屏：一句话 + 一个行动。整页只回答"现在该做什么"。 -->
<main class="now">
  <div id="viewnote" class="viewnote" hidden>
    <span id="viewnoteTx"></span>
    <button id="bBackCur" type="button" class="link2">去待办步骤</button>
  </div>
  <p class="eyebrow" id="eyebrow"><i></i><span id="eyebrowTx">正在读盘…</span><span id="stepState" class="stepstate"></span></p>
  <!-- 进度台：没在跑时 display:none，一个像素都不占（静止帧判据靠这个成立） -->
  <div class="gauge" id="gauge"></div>
  <h2 class="ask" id="ask">—</h2>
  <p class="why" id="why">—</p>
  <!-- 卡点：跨步的前置条件（例：配置表过期挡住导出）。它**不顶替**本步自己的按钮，
       只在旁边说清"为什么这一步先别跑、该去哪一步修"。 -->
  <div class="gate" id="gate" hidden></div>
  <div class="do" id="cta"></div>
  <!-- 回执：每个动作跑完都留一行结论（判绿/判红/待签字 + 用时）。
       以前点了「再查一次」界面一声不响，用户只能猜它到底跑没跑。 -->
  <p class="receipt" id="receipt" hidden></p>
  <!-- 三道硬边界：不是装饰，是这套工具**为什么敢让你点**的三条理由。
       文案与 AGENTS.md / update_pipeline 的实现一一对应；改实现时这三句要一起改。 -->
  <div class="rails" aria-label="运行边界">
    <div class="rail"><span>01 / 只读</span><b>先验证，再动手</b>
      <p>权威输入与源包清单逐份核对；预检不写盘，红了就停。</p></div>
    <div class="rail"><span>02 / 增量</span><b>范围由指纹裁定</b>
      <p>affected.txt 必须配 affected.meta；过期判红，不退化成全量。</p></div>
    <div class="rail"><span>03 / 签字</span><b>写正式区要留后路</b>
      <p>换入前整批备份；索引零回退、部署同 inode 两道闸门。</p></div>
  </div>
  <p class="foot" id="scopeNote"></p>
</main>

<!-- 运行中那一行：阶段 N/M + 现在在跑哪一档 + 已用/剩余（只在真在跑时出现） -->
<p class="runline" id="runline"></p>
<!-- 底部：一根会长过去的进度线 + 五个节点，节点上带该步全部阶段的状态方块 -->
<nav class="steps" id="stepsbar" aria-label="五个步骤">
  <div class="rail-hd"><span>RUNBOOK</span><b id="railCur">当前 01</b></div>
  <span class="track"><i class="fill" id="stepfill"></i></span>
  <div class="rail-ft"><span id="railCount">全部阶段</span><span>点击=查看 · 细节=证据</span></div>
</nav>
</div>

<!-- 细节抽屉：证据全在这儿，且一律不透明 -->
<div id="detail">
  <div class="veil" data-dclose></div>
  <div class="body">
    <div class="dhead">
      <h2>细节</h2>
      <div class="meters">
        <span class="meter"><b>本次更新包</b><span id="fp">计算中</span></span>
        <span class="meter"><b>范围</b><span id="scope">…</span></span>
        <span class="meter"><b>阶段</b><span id="prog">…</span></span>
        <span class="meter" id="mjob"><b>任务</b><span id="jobstat">空闲</span></span>
      </div>
      <button class="mini ghost" data-dclose>关闭 ✕</button>
    </div>
    <div class="col">
      <div class="pane">
        <div class="ph">阶段 <span id="sCount" class="dim" style="font-size:11px"></span></div>
        <div class="g" id="cards"></div>
      </div>
      <div class="pane" id="newpane">
        <div class="ph">这次新增了什么 <span class="gnote" id="newsum"></span></div>
        <div id="newtbl"></div>
      </div>
      <div class="pane">
        <div class="ph">改前 | 改后 对照表</div>
        <div id="sheets" class="sheets"></div>
      </div>
      <div class="pane">
        <div class="ph">颜色是什么意思</div>
        <div class="legend">
          <div class="lrow">
            <span><i class="sw" style="background:var(--idle)"></i>还没跑</span>
            <span><i class="sw" style="background:var(--pass)"></i>这步过了</span>
            <span><i class="sw" style="background:var(--run)"></i>正在跑</span>
          </div>
          <div class="lrow">
            <span><i class="sw" style="background:var(--await)"></i>等你签字</span>
            <span><i class="sw" style="background:var(--fail)"></i>卡住了</span>
          </div>
        </div>
      </div>
    </div>
    <div class="col side">
      <div class="pane logpane">
        <div class="ph">运行日志
          <span style="display:flex;gap:6px;align-items:center">
            <button id="bFollow" class="mini ghost">跟随最新</button>
            <button id="bClear" class="mini ghost">清空显示</button></span></div>
        <div class="chips" id="chips">
          <button class="chip on" data-f="all">全部</button>
          <button class="chip" data-f="bad">只看红</button>
          <button class="chip" data-f="await">等你签字</button>
          <button class="chip" data-f="stage">只看阶段行</button><i id="chipmark"></i></div>
        <pre id="log">等待任务</pre>
        <div style="display:flex;gap:8px;margin-top:9px;align-items:center">
          <button id="bForce" class="mini ghost">缓存：按指纹复用</button>
          <span class="dim" id="jobinfo" style="font-size:11.5px">—</span></div>
      </div>
      <div class="pane">
        <div class="ph">最近任务</div>
        <table class="runs"><thead><tr><th>时间</th><th>做什么</th><th></th></tr></thead>
          <tbody id="runs"></tbody></table>
      </div>
    </div>
  </div>
</div>

<!-- 签字窗口：不用原生 confirm()。原生弹窗是浏览器画的，和纸本界面两层皮；
     而且它只能放一句纯文本，写不清「会写哪几个阶段、写到哪儿、有没有备份」。 -->
<div id="signmodal" aria-hidden="true">
  <div class="veil" data-sclose></div>
  <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="signTitle">
    <div class="shead">
      <span class="kicker">SIGN-OFF <i>·</i> 签字放行</span>
      <h3 id="signTitle">签字放行</h3>
      <p id="signWhat">—</p>
    </div>
    <div class="slist" id="signList"></div>
    <p class="snote" id="signNote"></p>
    <label class="scheck">
      <input type="checkbox" id="signAgree">
      <span>我已核对上面的范围与写入位置，确认这一步会写正式区</span>
    </label>
    <label class="sigline">
      <span>签字</span>
      <input id="signName" type="text" maxlength="24" placeholder="输入名字或缩写" autocomplete="off">
      <em id="signDate"></em>
    </label>
    <div class="sact">
      <button type="button" class="ghost" id="signAlt" hidden></button>
      <button type="button" class="ghost" data-sclose>取消</button>
      <button type="button" class="pact" id="signGo" disabled>签字放行</button>
    </div>
  </div>
</div>

<i id="fxbeam"></i><i id="fxpool"></i>

<div id="help"><div class="veil" data-close></div><div class="panel">
  <button class="close ghost" data-close>关闭 ✕</button>
  <div class="hmode">
    <button class="seg" data-hm="simple">简洁</button><button class="seg" data-hm="detail">详细</button>
    <span class="hmodenote" id="hnote"></span>
  </div>
  <h3 style="margin-top:0">这是什么</h3>
  <p><b>资产更新控制台</b>把你游戏更新之后要做的那一串事，按五步排成一条主线。
  它<b>不重新实现</b>任何导出逻辑：每个按钮都是去起
  <code>scripts/update_pipeline.py</code> 这个命令行编排器，编排器再去起你仓库里原有的那些脚本
  （<code>mumu_sync</code> / <code>compose_paintings_v2</code> / <code>extract_spine_v2</code> /
  <code>reconstruct_live2d</code> / <code>build_gallery_index</code> …，全部原样调用）。
  所以「界面上看到的」和「命令行跑的」永远是同一套代码，不存在两份逻辑各自漂移。</p>

  <h3>颜色与档位怎么读</h3>
  <p>一个颜色只表示一件事，<b>颜色全部留给状态</b>：
  <span class="stt idle">未跑</span> <span class="stt pass">判绿</span>
  <span class="stt run">在跑</span> <span class="stt await">等你签字</span>
  <span class="stt fail">判红</span>。</p>
  <ul>
    <li><b>判绿</b> = 按这张卡上「判据」那行自己写的规则过了，不等于"结果一定对"——
      看图那一步永远是人工。</li>
    <li><b>判红</b> = 它停在这里不往下跑。<u>红色永远只等于判红</u>，
      不表示"这个会写正式产物"。</li>
    <li><b>档位是文字不是颜色</b>：<span class="tier">ⓘ 只读</span>
      <span class="tier s">▣ 暂存</span> <span class="tier l">⚑ 写正式</span>，
      三枚一律中性色，靠图标与字重分级。</li>
  </ul>

  <h3>动手之前</h3>
  <ul>
    <li>MuMu 已启动，且游戏已更新到你要导的那个版本；停在能进游戏主界面的状态。</li>
    <li>权威输入在位：<code>inputs/azdata/</code>、<code>inputs/gamecfg/</code>、画廊 vendor。
      第 1 步的 <code>preflight</code> 就是查这三样，红了别往下走。</li>
    <li>一次只跑一个重活（本机 15.4GB）。已有任务在跑时按钮会锁住，不是坏了。</li>
    <li>画廊服务器要先活着或让它自己起；回归那件会去连它。</li>
  </ul>

  <h3>五步分别动什么</h3>
  <table><thead><tr><th>步骤</th><th>会动</th><th>不会动</th></tr></thead><tbody>
    <tr><td>① 接模拟器</td><td>只读地列模拟器里的包，算出新增/变更清单</td>
        <td>不下载任何东西（下载是 <code>pull</code> 的签字项，要它才写 <code>files/</code>）</td></tr>
    <tr><td>② 同步配置表</td><td>解 <code>scripts32/64</code> 与 <code>sharecfgdata</code>，重发布
        <code>inputs/gamecfg</code>（皮肤表 / 声优 / 台词 / {namecode} / 秘书舰语音）</td>
        <td>前三档只写 <code>.diag/sharecfg_re/</code>；<b>发布那一档要签字</b>才写 <code>inputs/</code>。
        新角色没有这一档就不会出现在元数据里——<code>preflight</code> 的新鲜度判据就是盯这个的</td></tr>
    <tr><td>③ 重新导出</td><td>重算依赖表、元数据、立绘、Spine、Live2D、语音、CG</td>
        <td>立绘/Spine/Live2D 只写 <code>.diag/pipeline/</code> 暂存区，正式区一个字节都不碰</td></tr>
    <tr><td>④ 看图对比</td><td>产出「改前 | 改后」对照表和两张清单</td>
        <td>纯读，随时可反复跑</td></tr>
    <tr><td>⑤ 签字换入</td><td>把暂存区覆盖进 <code>Output/Paintings_v2</code>，
        重建缩略图与索引、部署画廊、跑回归</td>
        <td>换入前先整批备份到 <code>Output/_OLD_bak/pipeline_&lt;日期&gt;/</code>；
        索引有零回退闸门，掉条目会直接判红停住</td></tr>
  </tbody></table>

  <h3>「签字」到底签的是什么</h3>
  <p>标 <span class="tier l">⚑ 写正式</span> 的阶段，没签字时<b>不是静默跳过</b>——它会跑只读的那一半，
  把差异算出来，然后在状态里明写「未签字」。你勾了那张卡的签字框再按主按钮，才算放行它写进正式区。
  这是故意的：换入不可逆，而 AGENTS.md 要求全量运行前经人工确认，所以这里<b>没有</b>
  一键覆写一切的按钮。</p>
  <p>三处例外必须知道，因为它们的暂存不彻底：</p>
  <ul>
    <li><code>audio</code> / <code>cg</code>：底层脚本没有 <code>--out</code> 通道，签字后是<b>直写
      <code>Output/Audio</code>、<code>Output/CG_v2</code></b>。</li>
    <li><code>meta</code>：画廊索引读的是写死的 <code>Output/ship_meta.json</code>，
      所以「用新元数据预览索引」这件事<b>必须先换入</b>才能预览。</li>
    <li>覆写一批产物之前会先扫硬链接（历史上做过逐字节去重，共享 inode 的名字「写一个变两个」，
      会让修复看起来失效）。</li>
  </ul>

  <h3>为什么不信退出码</h3>
  <p>你有 9 个脚本<b>失败了照样 exit 0</b>（含 <code>compose_paintings_v2</code>、
  <code>extract_spine_v2</code>、<code>make_thumbs</code>、<code>export_cue_audio</code>）。
  所以每个阶段自带判据：数 <code>✗</code> 行、读到 <code>[SUMMARY] 模型 N/N</code>、
  读到「完成N 跳过N 失败N」、或去跑对应的闸门脚本。每张卡上都印着它<b>自己那条判据</b>，
  你可以核对它到底判了什么。</p>

  <h3>判红了怎么办</h3>
  <ul>
    <li>它会停在那里不往下跑（红着继续只会把错的东西换进去）。</li>
    <li>看日志里那行 <code>❌</code> 后面的原因，卡片上「上次结论」也带着它。</li>
    <li>常见三种：模拟器没开/adb 找不到（①）；权威输入缺（preflight）；
      闸门判红（④，说明这次换入会丢东西，<b>别绕</b>，先查源包）。</li>
  </ul>

  <h3>不在这里的两件事</h3>
  <ul>
    <li><b>全量重跑</b>：以数十小时计，且网页上没法做「手输 FULL」那道二次确认。
      要跑请用命令行 <code>py -3 scripts/update_pipeline.py --full</code>。</li>
    <li><b>画廊前端改动</b>：那是另一套流程（部署 + 硬链校验 + WF-16 回归），不归这个控制台管。</li>
  </ul>

  <h3>键位（摸熟比找按钮快）</h3>
  <p><code>1</code>…<code>4</code> 切步骤 · <code>R</code> 跑当前步的主动作 ·
  <code>P</code> 只看计划 · <code>H</code> 开关本抽屉 · <code>Esc</code> 关掉弹层 ·
  <code>S</code> 开关星野背景 · <code>M</code> 开关「动效从简」（关掉光沿边框走一圈、
  指针柔光、磁吸这些，只留状态本身）· <code>V</code> 开关「新旧版面对照」（对照更早那套
  版面，看差异用），两个选择都会记住。</p>

  <h3>进度台怎么读</h3>
  <p>只有<b>真的在跑</b>时，主屏下方才出现一条细带，四个量：<b>阶段 N/M</b>（M 是这次要跑的
  阶段数，<code>--only</code> 会把它缩小）、<b>已用</b>、<b>内存</b>（整棵进程树的工作集之和，
  导出子进程算在内）、<b>剩余</b>。剩余按各阶段的<b>历史均值</b>累加；某阶段还没有历史样本时
  它不装作知道 —— 前面标「≥」，表示那只是下限。不跑的时候这条带子完全不占位。</p>

  <h3>背景与光效</h3>
  <p>东京夜的星野，<b>显影式</b>：底上是三团不动的城市光晕（强度已压到旧版一半以下），
  星点画在一张画布上，<b>静止时全灭</b>——划过哪里哪里才亮。每颗星是<b>预渲染的精灵</b>：
  高斯核 + 按星随机旋转的锥形衍射芒，亮星六芒带淡色晕，暗星只是软边微点；
  亮度按幂律分布（亮星不到 1%），颜色按<b>色温</b>（蓝白→白→淡金）而不是糖果色。
  收摊时把每颗星的亮度与位置写回原位再画一帧，所以"亮过又淡掉"的终点和最初那张
  <b>逐像素相同</b>；控件上的光效同一条规矩：全部由指针驱动，没有一条常驻循环。</p>
  <p>觉得干扰：<code>S</code> 关整片星野，<code>M</code> 只关控件光效，
  <code>V</code> 换回旧版面对照，三个都会记住。
  想让它常驻一点微光（不划也能看见几颗），改 <code>ST.AMB</code> 这一个数就行。</p>

  <h3>出问题自己先查的三行</h3>
  <p><code>py -3 scripts/diag/check_inputs.py azdata</code> ·
    <code>py -3 scripts/diag/check_diag_hygiene.py</code> ·
    <code>py -3 scripts/mumu_sync.py diff</code></p>
  <p class="dim" style="font-size:12px">详细流程与判据：
    <code>docs/WORKFLOWS.md</code> WF-23（本工具）、WF-15（游戏更新还原全序）；
    踩坑：<code>docs/TROUBLESHOOTING.md</code> §63/§64/§65。</p>
</div></div>

<div id="lightbox"><img alt=""></div>

<script>
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
let S=null, step=1, curJob=null, off=0, follow=true, timer=null, force=false;
let SEA = false;   // 星野背景已退役（2026-10-17 纸本控制台）；变量保留只为不拆旧调用点
let NIGHT = localStorage.getItem('panel.night')==='1';

const TIER={read:['ⓘ 只读','r'],staged:['▣ 暂存','s'],live:['⚑ 写正式','l']};
const STT={idle:'未跑',pass:'判绿',await:'等你签字',fail:'判红',run:'在跑'};

/* ── 状态判定：唯一入口，颜色只从这里来 ─────────────────────────── */
function statusOf(k){
  const r=(S&&S.state||{})[k];
  if(!r) return 'idle';
  if(!r.ok) return 'fail';
  if(/未签字|请 --approve/.test(r.detail||'')) return 'await';
  return 'pass';
}

/* ── 背景：东京夜的星野 —— 静止时全黑，指针经过才显影、约 520ms 淡净 ──────
   显影口径借自 https://mimo.xiaomi.com/coder（量过那页才写准）：它**不是星野**，
   是"擦除式显影"——一层遮罩被光标擦出洞，洞随划速从 8px 长到 128px，
   亮点约 520ms 内二次衰减淡完、不残留，而且**故意用不规则软边 + 正弦抖动**
   去躲开"几何均一"。上一版我只借了"经过才亮"，星体本身却画成了正圆 + 一个手绘
   "+" 字形 —— 那就是用户说的"敷衍"。本轮把星体本身重做，见下面 SPR。

   每颗星只有一个 `lit`(0..1)：光标经过就充到 1，之后按秒指数衰减；
   **只有 lit 够亮的星才画** ⇒ 静止时整片天空是空的，划过才出现一条星带。

   三条硬约束仍然一条不丢：
     · 静止时逐像素完全相同：能量归零时把所有 lit 强制写回 0、位置写回 home 再画一帧
       ⇒ 显影过又淡掉的终点与初始帧是同一张图（探针逐像素比这个）。
       ⚠️ 所以"闪烁"只能调制 `lit` 那一项：`vis = amb + f(lit)`，amb 项绝不吃时间，
       否则常驻星点会让静止两帧自己就不相同。
     · 衰减与弹簧都按**秒**积分（乘 dt），不按帧 —— 按帧写在低帧率下会"永远淡不干净"。
     · 指针「瞬移」不算划过，且**按速度判**（>4200px/s 或距上一拍 >250ms），
       不能按固定像素：正常快扫一步就 48~58px，按像素判会把整层背景判成"对鼠标没反应"。
   仍然没有 WebGL、没有噪声函数：一张 2D 画布 + 一张预渲染精灵图集。 */
function mul32(a){return()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);
  t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
const ST={cv:null,g:null,w:0,h:0,list:[],pairs:[],neb:null,raf:0,t0:0,frames:0,
          peak:0,lit:0,strokes:0,bursts:0,rings:[],C:[],LC:'#9aa4c8',
          AMB:0.26,          // 常驻星点占比的亮度；想要"完全只有经过才亮"就把它设成 0
          RMIN:46,RMAX:190,  // 显影半径：随笔画速度从 46px 长到 190px（旧 9→130 时慢速划过
                             //   只点亮两三颗，用户读到的就是"撒了几粒灰"而不是"一片星空"）
          DECAY:4.6,         // 亮度衰减 /秒 ⇒ 520ms 后只剩 9%
          SPRING:34,DAMP:4.2,EPS:0.12,LIT_EPS:0.012,
          LINK_A:0.16,        // 星座连线的 alpha 上限（旧版 0.52 太像连点图）
          last:null,lastT:0,pend:null,avoid:[]};
function rgbOf(h){
  h=(h||'#ffffff').trim();
  if(h[0]==='#'){ const s=h.length===4? h.slice(1).split('').map(c=>c+c).join('') : h.slice(1);
    const v=parseInt(s,16); return [(v>>16)&255,(v>>8)&255,v&255]; }
  const m=h.match(/[\d.]+/g); return m?[+m[0],+m[1],+m[2]]:[255,255,255];
}
/* 精灵图集：把"一颗星长什么样"预先画到离屏画布，每帧只做 drawImage(+旋转)。
   为什么不能继续 `arc()`+`fill()`：
     · 半径 0.3px 的正圆会被抗锯齿成一个亮度失控的小方块 —— 暗星整片发灰；
     · 亮星挂一个 moveTo/lineTo 画的十字，那是个 **「+」字形**，不是衍射芒：
       真芒是从高斯核向外**锥形衰减**的，而且**每颗星的芒角不一样**（支架角/视差角）。
   ⇒ 每种星型 × 每档色温烘一张：高斯核（sigma 收紧到 2~3px 半宽）+ 软外晕 +
     锥形芒（star 四芒 / hero 六芒带淡外环），dust 只有核，cloud 是一团极平的高斯
     用来铺银河带的星云。 */
const SPR={dust:[],star:[],hero:[],cloud:[],dpr:1};
const SPR_SP={dust:16, star:64, hero:128, cloud:64};
function gaussSprite(SP,rgb,kind){
  const dpr=SPR.dpr, c=document.createElement('canvas');
  c.width=c.height=Math.max(2,Math.round(SP*dpr));
  const g=c.getContext('2d'); g.setTransform(dpr,0,0,dpr,0,0);
  const m=SP/2, col=a=>`rgba(${rgb[0]},${rgb[1]},${rgb[2]},${Math.max(0,Math.min(1,a)).toFixed(4)})`;
  /* ⚠️ 每个精灵的外层渐变**必须在画布边缘精确归零**：radial gradient 超出 r1 之后
     会一直沿用最后一个色标，而高斯在 t=1 处还剩 5~19% —— 于是每颗星外面套一圈
     **看得见的正方形**（旋转之后变成菱形，比"敷衍"更难看）。
     ⇒ 一律乘 `(1-t²)` 窗口，让 t=1 处严格为 0。 */
  const win=t=>Math.max(0,1-t*t);
  const stop=(gr,s,t)=>gr.addColorStop(t, col(Math.exp(-(t*t)/s)*win(t)));
  if(kind==='cloud'){                       // 星云：一层摊到边缘的高斯，没有核
    const gr=g.createRadialGradient(m,m,0,m,m,m);
    for(let i=0;i<=16;i++) stop(gr,0.18,i/16);
    g.fillStyle=gr; g.fillRect(0,0,SP,SP); return c;
  }
  if(kind!=='dust'){                        // 软外晕
    const gr=g.createRadialGradient(m,m,0,m,m,m);
    for(let i=0;i<=16;i++) stop(gr,0.055,i/16);
    g.fillStyle=gr; g.fillRect(0,0,SP,SP);
  }
  const R0=kind==='dust'? m : SP*0.22, s2=kind==='dust'? 0.05 : 0.02;
  const core=g.createRadialGradient(m,m,0,m,m,R0);
  for(let i=0;i<=16;i++) stop(core,s2,i/16);
  g.fillStyle=core; g.fillRect(0,0,SP,SP);
  if(kind==='dust') return c;
  const n=kind==='hero'?6:4, L=m*0.95, w=SP*(kind==='hero'?0.024:0.032);
  for(let k=0;k<n;k++){
    const long=(kind==='hero'&&k%3!==0)?0.46:1;
    g.save(); g.translate(m,m); g.rotate(k*Math.PI*2/n+(kind==='hero'?0.26:0));
    const lg=g.createLinearGradient(0,0,L*long,0);
    lg.addColorStop(0,col(0)); lg.addColorStop(.05,col(.9));
    lg.addColorStop(.42,col(.22)); lg.addColorStop(1,col(0));
    g.fillStyle=lg;
    g.beginPath(); g.moveTo(0,-w); g.lineTo(L*long,0); g.lineTo(0,w); g.closePath(); g.fill();
    g.restore();
  }
  if(kind==='hero'){                        // 亮星常见的极淡外环
    g.strokeStyle=col(.10); g.lineWidth=SP*0.010;
    g.beginPath(); g.arc(m,m,m*0.60,0,6.2832); g.stroke();
  }
  return c;
}
function spriteBake(){
  SPR.dpr=Math.min(2,window.devicePixelRatio||1);
  for(const k of Object.keys(SPR_SP))
    SPR[k]=ST.C.map(c=>gaussSprite(SPR_SP[k],rgbOf(c),k));
}
function starColors(){
  const cs=getComputedStyle(document.documentElement);
  const g=n=>(cs.getPropertyValue(n)||'').trim();
  // 四档**色温**（蓝白→冷白→淡金→暖金），不是糖果色；旧版面那套粉橙留在 legacy 变量里
  ST.C=[g('--s-1')||'#eef4ff',g('--s-2')||'#dbe6f7',g('--s-3')||'#fff2df',g('--s-4')||'#ffd9ae'];
  ST.LC=g('--s-link')||'#9aa4c8';
  spriteBake();
}
function starsBuild(){
  const R=mul32(20260930);                   // 同种子 ⇒ 刷新后星位不变，不会"每次进来换一片天"
  const w=ST.w, h=ST.h;
  const n=Math.round(Math.min(4200,Math.max(1500,w*h/400)));
  ST.list=[];
  const gx=w*0.04, gy=h*1.08, dx=w*0.96, dy=-h*0.84;          // 一条斜着的银河带
  for(let i=0;i<n;i++){
    let x,y;
    if(i<n*0.62){ const t=R(), o=(R()-0.5)*w*0.24;
      x=gx+dx*t+o; y=gy+dy*t+(R()-0.5)*w*0.13; }
    else { x=R()*w; y=R()*h; }
    /* 亮度按**幂律**分：真实天区里暗星是绝对多数。上一版 `big` 有 ~5%，
       于是满屏都是带十字的"亮星"，看着像撒了一把图钉。现在 hero <0.5%、star ~9%。 */
    const u=R();
    const kind = u>0.995 ? 'hero' : u>0.905 ? 'star' : 'dust';
    const z=0.34+R()*0.66;
    const sz = kind==='hero' ? 46+R()*40 : kind==='star' ? 16+R()*18 : 3.0+R()*3.2;
    const a  = kind==='hero' ? 0.74+R()*0.26 : kind==='star' ? 0.30+R()*0.32 : 0.10+R()*0.24;
    // 色温与亮度相关：暗尘偏蓝白，只有亮星才允许走到暖端
    const ci = kind==='dust' ? (R()<0.80?0:1) : kind==='star' ? (R()*3|0) : (R()*4|0);
    /* 常驻那一档按**星型分别抽**：旧版 `i%47` 是等概率抽，抽到的多半是最暗的 dust，
       而 dust 的 a 只有 0.10~0.34，再乘上 AMB 就落在 `al<0.008` 那条丢弃线附近 ⇒
       实测静止帧整屏只有 67 个像素亮着（占视口 0.01%），"静止全黑"黑到看不见天。
       ⇒ 亮星每 3 颗留 1 颗、尘每 13 颗留 1 颗（hero 一律不留，把惊喜留给划过那一刻）。 */
    const isAmb = kind==='star' ? (i%3===0) : kind==='dust' ? (i%13===0) : false;
    ST.list.push({hx:x,hy:y,x:x,y:y,vx:0,vy:0,z:z,kind:kind,lit:0,
      amb:(isAmb ? ST.AMB*(0.55+R()*0.45) : 0),
      sz:sz, a:a, c:ci, rot:R()*6.2832, ph:R()*6.2832});
  }
  /* 星座连线只算一次（建表时），每帧按当前亮度画：两端都亮才连线。
     新版把上限压到 0.16 alpha、线宽 0.6 —— 上一版 0.52 的紫线是"连点图"观感的主因。 */
  ST.pairs=[];
  const far=ST.list.filter(t=>t.kind!=='dust'&&t.z>0.70), lim=Math.min(150,w*0.10);
  for(let i=0;i<far.length;i++){
    const a=far[i], cand=[];
    for(let j=0;j<far.length;j++){
      if(j===i) continue; const b=far[j];
      const d=Math.hypot(b.hx-a.hx,b.hy-a.hy);
      if(d<lim) cand.push([d,b]);
    }
    cand.sort((p,q)=>p[0]-q[0]);
    for(const [d,b] of cand.slice(0,2)) if(d>16) ST.pairs.push([a,b,d]);
  }
  nebBake(R);
}
/* 银河带不是"点更密"就完事，得有**星云**：摊开的高斯团叠在带轴上，alpha 只有 2~5%。
   烘成一张静态位图，每帧一次 drawImage，所以它不吃"静止帧必须相同"这条。 */
function nebBake(R){
  if(!SPR.cloud||!SPR.cloud.length) return;
  const dpr=SPR.dpr, w=ST.w, h=ST.h;
  const c=ST.neb||(ST.neb=document.querySelector('#nebula'));
  if(!c) return;
  c.style.position='absolute'; c.style.inset='0';
  c.width=Math.max(2,Math.round(w*dpr)); c.height=Math.max(2,Math.round(h*dpr));
  const g=c.getContext('2d'); g.setTransform(dpr,0,0,dpr,0,0);
  g.clearRect(0,0,w,h);
  const gx=w*0.04, gy=h*1.08, dx=w*0.96, dy=-h*0.84;
  /* 旧版是 30 个**正圆**高斯（alpha 1.8~4.8%）：圆边沿一被看出来，整条带就假了 ——
     截图上读到的不是"银河"，是"撒了几团烟"。⇒ 沿带轴拉长 1.6~3.2 倍、数量翻倍、
     单颗 alpha 减半，并让横向偏移走三角分布（越靠带轴越密）。这样它们叠成一条
     连续、有纤维感的带子，而看不出任何一个单独的团。 */
  const ang=Math.atan2(dy,dx), cs=Math.cos(ang), sn=Math.sin(ang);
  const span=Math.hypot(dx,dy);
  for(let i=0;i<64;i++){
    const along=(R()-0.5)*span*1.04;
    const across=(R()+R()-1)*w*0.13;                 // 三角分布 ⇒ 带轴密、两侧稀
    const cx=gx+along*cs-across*sn, cy=gy+along*sn+across*cs;
    const s=150+R()*300, stretch=1.6+R()*1.6, al=0.010+R()*0.016;
    g.save(); g.translate(cx,cy); g.rotate(ang); g.scale(stretch,1);
    g.globalAlpha=al;
    g.drawImage(SPR.cloud[R()<0.78?0:1],-s/2,-s/2,s,s);
    g.restore();
  }
  g.globalAlpha=1;
}
/* 闪烁只调制 `lit` 那一项：lit=0 时返回值与时间无关 ⇒ 静止帧仍然逐像素相同。 */
function vis(st,t){
  return st.amb + (st.lit>0.0005
    ? st.lit*(0.84+0.16*Math.sin((t||0)*2.3+st.ph)) : 0);
}
function starsDraw(){
  const g=ST.g; if(!g) return;
  const t=performance.now()/1000;
  g.clearRect(0,0,ST.w,ST.h);      // 星云在另一张画布上，这里只画会动的部分
  g.lineWidth=0.6; g.strokeStyle=ST.LC;
  for(const [a,b,rest] of ST.pairs){
    const v=Math.min(vis(a,t),vis(b,t));
    if(v<0.55) continue;                       // 两端都够亮才连：显影区中心才出现星座
    const d=Math.hypot(b.x-a.x,b.y-a.y), over=Math.abs(d-rest)/Math.max(1,rest);
    const al=Math.max(0,ST.LINK_A-over*0.30)*v;
    if(al<0.006) continue;
    g.globalAlpha=Math.min(ST.LINK_A,al);
    g.beginPath(); g.moveTo(a.x,a.y); g.lineTo(b.x,b.y); g.stroke();
  }
  for(const st of ST.list){
    const v=vis(st,t);
    if(v<0.014) continue;                      // 静止时一颗都不画 —— "只有经过才显示"
    const al=st.a*v; if(al<0.008) continue;
    const spr=SPR[st.kind] && SPR[st.kind][st.c]; if(!spr) continue;
    const s=st.sz;
    g.globalAlpha=Math.min(1,al);
    if(st.kind==='dust') g.drawImage(spr,st.x-s/2,st.y-s/2,s,s);
    else { g.save(); g.translate(st.x,st.y); g.rotate(st.rot);
           g.drawImage(spr,-s/2,-s/2,s,s); g.restore(); }
  }
  for(const r of ST.rings){
    g.globalAlpha=Math.max(0,r.a); g.strokeStyle=r.c; g.lineWidth=1.4;
    g.beginPath(); g.arc(r.x,r.y,r.r,0,6.2832); g.stroke();
  }
  g.globalAlpha=1;
}
function starsResize(){
  if(!ST.cv) return;
  const dpr=Math.min(2,window.devicePixelRatio||1);
  ST.w=innerWidth; ST.h=innerHeight;
  ST.cv.width=Math.max(2,ST.w*dpr|0); ST.cv.height=Math.max(2,ST.h*dpr|0);
  ST.g.setTransform(dpr,0,0,dpr,0,0);
  starsBuild(); starsDraw();
}
function starsFrame(ts){
  const dt=ST.t0?Math.min(0.05,(ts-ST.t0)/1000):1/60; ST.t0=ts;
  const k=ST.SPRING, d=Math.exp(-ST.DAMP*dt), ld=Math.exp(-ST.DECAY*dt);
  let peak=0, lit=0;
  for(const st of ST.list){
    st.vx+=((st.hx-st.x)*k)*dt; st.vy+=((st.hy-st.y)*k)*dt;
    st.vx*=d; st.vy*=d;
    st.x+=st.vx*dt; st.y+=st.vy*dt;
    const ad=Math.abs(st.x-st.hx)+Math.abs(st.y-st.hy);
    if(ad>peak) peak=ad;
    st.lit*=ld; if(st.lit>lit) lit=st.lit;
  }
  for(const r of ST.rings){ r.r+=r.v*dt; r.a-=dt*1.5; }
  ST.rings=ST.rings.filter(r=>r.a>0.02);
  ST.peak=peak; ST.lit=lit; ST.frames++;
  if(lit>ST.LIT_EPS || peak>ST.EPS || ST.rings.length){
    starsDraw(); ST.raf=requestAnimationFrame(starsFrame);
  } else {                    // 收摊：亮度清零、位置写回 home，再画一帧 ⇒ 与初始帧逐像素相同
    ST.raf=0;
    for(const st of ST.list){ st.x=st.hx; st.y=st.hy; st.vx=0; st.vy=0; st.lit=0; }
    ST.rings.length=0; ST.lit=0; starsDraw();
  }
}
function starsStart(){ if(!ST.raf && SEA){ ST.t0=0; ST.raf=requestAnimationFrame(starsFrame); } }
/* 显影：半径随笔画速度长大（参考页 8→128px 的同一条曲线口径） */
function starsLight(x,y,speed,down){
  const R=down?ST.RMAX*1.5:Math.min(ST.RMAX, ST.RMIN + (speed||0)*1.5), R2=R*R;
  let hit=0;
  const av=ST.avoid||[];
  for(const st of ST.list){
    const dx=st.x-x, dy=st.y-y, d2=dx*dx+dy*dy;
    if(d2>R2) continue;
    if(av.length){ let skip=false;                   // 主屏文字区：装饰给它让路
      for(const a of av) if(st.hx>=a[0]&&st.hx<=a[2]&&st.hy>=a[1]&&st.hy<=a[3]){skip=true;break;}
      if(skip) continue; }
    const f=Math.pow(1-d2/R2, 1.15);
    if(f>st.lit) st.lit=f;
    hit++;
    if(down){                                  // 点击顺带轻轻拨一下，让"亮"有物理感
      const d=Math.sqrt(d2)||1, imp=520*(1-d2/R2)*st.z/(1+d/70);
      st.vx+=dx/d*imp; st.vy+=dy/d*imp;
    }
  }
  if(down && hit){ ST.bursts++; ST.rings.push({x:x,y:y,r:6,v:520,a:0.5,c:ST.LC}); }
  if(hit){ ST.strokes++; starsStart(); }
  return hit;
}
function starMove(x,y){
  if(!SEA) return;
  const now=performance.now();
  let jump=true, speed=0;
  if(ST.last){
    const dt=Math.max(0.004,(now-ST.lastT)/1000);
    speed=Math.hypot(x-ST.last[0],y-ST.last[1])/dt;
    jump=(now-ST.lastT>250)||speed>4200;
  }
  ST.last=[x,y]; ST.lastT=now;
  if(jump) return;
  starsLight(x,y,speed,false);
}
window.addEventListener('pointermove',e=>{
  if(!SEA) return;
  if(ST.pend){ ST.pend.e=e; return; }         // 节流到每帧一次，但永远取最新坐标不丢中间点
  ST.pend={e:e};
  requestAnimationFrame(()=>{ const ev=ST.pend&&ST.pend.e; ST.pend=null;
                              if(ev) starMove(ev.clientX,ev.clientY); });
},{passive:true});
window.addEventListener('pointerdown',e=>{
  if(!SEA) return;
  ST.last=[e.clientX,e.clientY]; ST.lastT=performance.now();
  starsLight(e.clientX,e.clientY,0,true);
},{passive:true});
window.addEventListener('blur',()=>{ ST.last=null; });
function seaApply(){
  document.body.classList.toggle('plain',true);   // 星野退役：始终 plain，不再起绘制循环
  const b=$('#bSea'); if(b) b.textContent = NIGHT ? '夜读 · 开' : '夜读 · 关';
  if(ST.raf){ cancelAnimationFrame(ST.raf); ST.raf=0; }
  ST.rings.length=0;
  if(ST.g) ST.g.clearRect(0,0,ST.w,ST.h);
}
/* 「夜读」= 暖墨底（不是旧版紫黑）。S / V 都切它；切换只改 body.night，不重建页面。 */
function nightApply(){
  document.body.classList.toggle('night',NIGHT);
  const b=$('#bSea');
  if(b){
    b.textContent = NIGHT ? '夜读 · 开' : '夜读 · 关';
    b.title = 'S：夜读模式 开/关（暖墨底，非旧版紫黑）';
  }
  if(ST.g){ starColors(); starsResize(); }
}
$('#bSea').onclick=()=>{
  NIGHT=!NIGHT; localStorage.setItem('panel.night',NIGHT?'1':'0');
  nightApply();
};
const bBackCur=$('#bBackCur');
if(bBackCur) bBackCur.onclick=()=>{ step=currentStep(); render(); };

/* ── 光效引擎：光由指针携带 ────────────────────────────────────────────
   三个动作，一套语言：
     ① 进入 —— 一道光沿控件**边框**从指针进入的那一点起跑，绕一圈回到它，然后消失；
     ② 停留 —— 控件内部一团柔光跟着指针走（`mix-blend-mode:screen`，只提亮不压暗，
                所以永远不会把字"糊掉"）；主操作与左轨额外朝指针让出 2px（磁吸）；
     ③ 按下 —— 光从落点泄进背景星野：往星野里打一圈**该控件自己的颜色**的涟漪，
                于是"点界面"和"那片天"是同一套物理，而不是两层各演各的。
   实现上是**两个全局单例浮层**（#fxbeam / #fxpool）搬到目标控件的矩形上，
   不给每个控件加子节点 —— 控件全是 render() 重建出来的，往节点里塞东西就会跟着抖。
   ⚠️ 数据面（`pre` 日志、对照图里的立绘）不吃柔光：screen 混合会改变画面像素值，
      而这张界面第一用途是**验资产正确性**。对照图只吃边框光（光在框上，不进图里）。 */
let CALM = localStorage.getItem('panel.calm')==='1';
/* V 键：新版面（中性阶梯、零投影）↔ 旧版面（薰衣草底 + 渐变灯管 + 投影）当场对照。
   两条都留在 CSS 里，靠 `body.legacy` 切换 —— 他判"丑不丑"要能立刻比，
   静态对比图不如这个（同一台服务器、同一个进程、同一个鼠标位置）。 */
let LEGACY = false;   // 旧紫黑版面退役；保留变量只让旧函数不报错（V 键现在切夜读）
function legacyApply(){
  document.body.classList.toggle('legacy',LEGACY);
  if(ST.g){ starColors(); starsResize(); }        // 星点色板跟着版面走
  else starColors();
}
const FX={beam:$('#fxbeam'),pool:$('#fxpool'),cur:null,last:null,down:false,pt:{}};
const FXSEL='button,.step,.signbox,.sheets a';
function fxTone(el){
  const c=el.classList;
  // 边框光/柔光的颜色跟着**语义**走：主动作=蓝白，签字=等你签字的琥珀，其余中性。
  if(c.contains('go')) return ['#cfe0ff','rgba(207,224,255,.26)'];
  if(c.contains('sign')||c.contains('signbox')) return ['#f2bd72','rgba(242,189,114,.22)'];
  if(c.contains('step')) return ['#cfe0ff','rgba(207,224,255,.16)'];
  if(c.contains('chip')) return ['#cfe0ff','rgba(207,224,255,.13)'];
  return ['rgba(206,212,228,.75)','rgba(220,225,240,.13)'];
}
function fxOff(){ FX.pool&&(FX.pool.classList.remove('on')); FX.beam&&FX.beam.classList.remove('go');
                 if(FX.cur){ magClear(); MAG.el=null; FX.cur.el.style.transform=''; FX.cur=null; } }
function fxEnter(el,e){
  if(CALM||!FX.beam) return;
  const r=el.getBoundingClientRect();
  if(r.width<10||r.height<10||r.bottom<0||r.top>innerHeight) return;
  const img=el.matches('.sheets a');                          // 图：只上边框光，不上柔光
  const [bc,pc]=fxTone(el), br=getComputedStyle(el).borderRadius||'9px';
  const b=FX.beam;
  b.style.left=(r.left-1.5)+'px'; b.style.top=(r.top-1.5)+'px';
  b.style.width=(r.width+3)+'px'; b.style.height=(r.height+3)+'px';
  b.style.borderRadius=br; b.style.setProperty('--bc',bc);
  // 让白色那段核心正好落在指针进入点上（conic 的 0deg 在 12 点，atan2 的 0 在 3 点）
  const th=Math.atan2(e.clientY-(r.top+r.height/2), e.clientX-(r.left+r.width/2))*180/Math.PI;
  b.style.setProperty('--a0',(((th+90-292)%360+360)%360)+'deg');
  b.classList.remove('go'); void b.offsetWidth; b.classList.add('go');
  b.onanimationend=()=>b.classList.remove('go');
  if(img){ FX.cur={el,r,img:true}; return; }
  const p=FX.pool;
  p.style.left=r.left+'px'; p.style.top=r.top+'px';
  p.style.width=r.width+'px'; p.style.height=r.height+'px';
  p.style.borderRadius=br; p.style.setProperty('--pc',pc);
  p.classList.add('on');
  FX.cur={el,r,img:false}; fxMove(e);
}
function fxMove(e){
  if(e&&e.clientX!=null) FX.pt=e;
  if(!FX.cur||CALM) return;
  const {el,r,img}=FX.cur, p=FX.pt;
  if(!r||img||p.clientX==null) return;
  FX.pool.style.setProperty('--px',(p.clientX-r.left)+'px');
  FX.pool.style.setProperty('--py',(p.clientY-r.top)+'px');
  if(el.classList.contains('mag')){
    // 位移上限 7px、按下压到 0.972 —— 全交给弹簧，所以松手有轻微过冲
    const dx=(p.clientX-(r.left+r.width/2))/(r.width/2);
    const dy=(p.clientY-(r.top+r.height/2))/(r.height/2);
    magTo(el, dx*7, dy*5.4, FX.down);
  }
}
document.addEventListener('pointerover',e=>{
  const el=e.target.closest?e.target.closest(FXSEL):null;
  if(el&&el!==FX.last){ FX.last=el; fxEnter(el,e); }
  const card=e.target.closest?e.target.closest('.stage'):null;
  if(card){ const cr=card.getBoundingClientRect();          // 光条从进入的高度点燃
    card.style.setProperty('--oy',
      Math.max(0,Math.min(1,(e.clientY-cr.top)/cr.height)*100).toFixed(1)+'%'); }
},{passive:true});
document.addEventListener('pointerout',e=>{
  const card=e.target.closest?e.target.closest('.stage'):null;
  if(card&&!card.contains(e.relatedTarget)) card.style.removeProperty('--oy');
  const el=e.target.closest?e.target.closest(FXSEL):null;
  if(!el||el!==FX.last) return;
  if(e.relatedTarget&&el.contains(e.relatedTarget)) return;
  FX.last=null; fxOff();
},{passive:true});
document.addEventListener('pointermove',e=>{ if(FX.cur) fxMove(e); },{passive:true});
document.addEventListener('pointerdown',e=>{
  FX.down=true; fxMove(e);
  const el=e.target.closest?e.target.closest(FXSEL):null;
  if(!el||CALM||!SEA) return;                 // 按下 = 把光泄进背景星野，颜色跟着控件走
  ST.rings.push({x:e.clientX,y:e.clientY,r:4,v:780,a:.7,c:fxTone(el)[0]});
  ST.bursts++; starsStart();
},{passive:true});
document.addEventListener('pointerup',()=>{ FX.down=false; fxMove(); },{passive:true});
addEventListener('scroll',()=>{ FX.last=null; fxOff(); },true);
function chipMark(){
  const on=$('.chip.on'), mk=$('#chipmark'); if(!on||!mk) return;
  mk.style.left=on.offsetLeft+'px'; mk.style.width=on.offsetWidth+'px'; mk.style.opacity='1';
}
function calmApply(){
  document.body.classList.toggle('calm',CALM);
  if(CALM) fxOff();
}

/* ── 数据 ─────────────────────────────────────────────────────────── */
/* 8 秒轮询曾经让整屏"闪"一下：render() 是 innerHTML 整片重建，而入场动画写在
   .step/.stage 的基础类上 ⇒ 每次重建都从头播。两道修：
     ① payload 签名没变就根本不 render()；
     ② 动画只挂在 `.in` 上，而 `.in` 只在**该 key 首次挂载**时加（切步骤时清空重来）。
   ② 才是根因修复 —— 就算状态真的变了，也不该有整屏淡入。 */
let SIG='', RENDERED=false, LASTSTEP=-1;
const mounted=new Set();
function sigOf(j){
  try{ return JSON.stringify([j.fingerprint,j.scope,j.state,j.running,j.sheets,j.runs,
                              j.stages,j.steps,j.error,j.skin_gap]); }
  catch(e){ return String(Math.random()); }
}
async function apiState(force){
  let j=null;
  try{ j=await (await fetch('/api/state')).json(); }
  catch(e){ LOADERR=String(e); render(); setTimeout(apiState,2500); return; }
  LOADERR=''; LOADED=true; S=j; S.state=S.state||{};
  gaugeSet(j.gauge);
  const ns=sigOf(j);
  if(!force && RENDERED && ns===SIG){          // 内容一个字节没变 ⇒ 一个节点都不碰
    if(S.running && !curJob) tail(S.running.id);
    return;
  }
  SIG=ns; render();
  if(S.running && !curJob) tail(S.running.id);
}
function stagesOf(n){ return (S.stages||[]).filter(s=>(s.step||0)===n); }
/* 「待办」= 下一步该动手的步骤；正在跑时以 running.step 为准。
   它和 `step`（用户正在看哪一步）是两件事——2026-10-17 用户点了几下步骤就迷路了，
   根因就是之前只有 `step`，没有「机器停在哪」这个锚。
   另一个坑：preflight 归在第 1 步，但它的红要靠第 2 步「同步配置表」来消。
   若照"第一处不绿"算，待办会死锁在第 1 步（第 1 步没有能修它的按钮）。
   ⇒ 配置表过期且第 2 步还有没跑完的阶段时，待办直接指向第 2 步。 */
function currentStep(){
  if(S.running && +S.running.step) return +S.running.step;
  const order=Object.keys(S.steps||{}).map(Number).sort((a,b)=>a-b);
  const pf=S.state&&S.state.preflight;
  const nCfg=stepNo('cfg.publish',2);
  const cfgPending=stagesOf(nCfg).some(s=>statusOf(s.key)!=='pass');
  if(pf&&!pf.ok&&/配置表过期/.test(pf.detail||'')&&cfgPending) return nCfg;
  /* 表漂移同理：修复动作（重新发布）在第 2 步，别让"待办"停在已经全绿的第 5 步。 */
  if(skinGapPending()) return stepNo('cfg.publish',2);
  for(const n of order){
    const list=stagesOf(n);
    if(!list.length) continue;
    const sts=list.map(s=>statusOf(s.key));
    if(sts.some(x=>x==='fail'||x==='run'||x==='await'||x==='idle')) return n;
  }
  return order.length?order[order.length-1]:1;
}
let LOADED=false, LOADERR='';

/* ── 进度台：只在真的在跑时出现 ─────────────────────────────────────────
   数字全部来自服务端 gauge_safe()（已用/内存/阶段/剩余），前端只负责显示，
   并把「已用」按本地时钟往下走 —— 8 秒一次轮询中间那几秒不动会看着像卡死。
   ⚠️ 它**不挂在 render() 里**：render() 会重建 13 张卡，每 8 秒重建一次会让探针的
   pin 判据当场红（"轮询没有重建 .stage 节点"）。所以单独走 gaugeSet()。 */
let GT=null, G=null, GKEY='';
function fmtDur(s){
  if(s==null) return '—';
  s=Math.max(0,Math.round(s));
  const h=Math.floor(s/3600), m=Math.floor(s%3600/60), x=s%60;
  return h ? (h+':'+String(m).padStart(2,'0')+':'+String(x).padStart(2,'0'))
           : (m+':'+String(x).padStart(2,'0'));
}
function fmtMem(mb){
  if(mb==null) return '—';
  return mb>=1024 ? (mb/1024).toFixed(2)+' GB' : Math.round(mb)+' MB';
}
function gaugeSrc(g){
  /* 「剩余」是怎么来的必须说出口：历史均值最可信，实测速率×本次项数次之，
     固定常量再次；三者都没有的阶段计入"未知"，前端就只报 ≥ 而不是 ~。 */
  const s=g.eta_src||{}, bits=[];
  if(s.hist) bits.push(s.hist+' 段历史均值');
  if(s.rate) bits.push(s.rate+' 段按实测速率×项数');
  if(s.est)  bits.push(s.est+' 段按实测常量');
  if(g.eta_missing) bits.push('另有 '+g.eta_missing+' 段没量过');
  /* 服务端没报来源（老版本，或探针注入的假 gauge）时，`eta_n` 只可能来自历史均值
     —— 这句措辞是界面判据在守的，别一丢了。 */
  return bits.length?bits.join(' · '):(g.eta_n?'按 '+g.eta_n+' 段历史均值':'估算');
}
function gaugeTick(){
  if(!G||!G.t0) return;
  const now=Date.now()/1000, e=$('#gEl'), m=$('#gMem'), t=$('#gEta'),
        f=$('#gFill'), u=$('#gUn');
  if(e) e.textContent=fmtDur(now-G.t0);
  if(m) m.textContent=fmtMem(G.mem_mb);
  if(t) t.textContent = (G.eta==null) ? '样本不足'
    : (G.eta_missing?'≥':'~')+fmtDur(Math.max(0, G.eta-(now-(G.at||now))));
  /* 条子的分子允许带上**本阶段内**的比例：立绘跑到 1200/4488 时它在动，
     用户就知道没卡死。该阶段不打 a/b 就退回阶段级 —— 绝不拿上一次的值假装在动。 */
  const has = G.unit_total>0 && G.unit_done!=null,
        frac = has ? Math.min(1, Math.max(0, G.unit_done/G.unit_total)) : 0;
  if(u) u.textContent = has ? ('本阶段 '+G.unit_done+' / '+G.unit_total)
                            : (G.stage ? '本阶段无项级进度（该脚本不打 a/b）' : '');
  if(f) f.style.width = (G.total ? Math.min(100, (G.done+frac)/G.total*100) : 0).toFixed(1)+'%';
  /* 五步主页那条**每一步自己的进度条**：跑起来才推进（含本阶段内比例），
     没在跑时整行 display:none —— 静止帧逐像素相同的判据不受影响。 */
  const rl=$('#runline');
  if(rl){
    rl.classList.add('on');
    rl.innerHTML='<b>运行中</b><span class="rl-stage">'+esc(G.stage||'')+
      (G.stage_title?' · '+esc(G.stage_title):'')+'</span>'+
      '<span>阶段 <b>'+(G.done||0)+'/'+(G.total||0)+'</b></span>'+
      (has?'<span>本阶段 <b>'+G.unit_done+'/'+G.unit_total+'</b></span>':'')+
      '<span>已用 <b>'+fmtDur(now-G.t0)+'</b></span>'+
      '<span>剩余 <b>'+(G.eta==null?'未知':(G.eta_missing?'≥':'~')+fmtDur(Math.max(0,G.eta-(now-(G.at||now)))))+'</b></span>';
  }
  document.querySelectorAll('.snode').forEach(nd=>{
    const tot=+nd.dataset.total||0, dn=+nd.dataset.done||0, el=nd.querySelector('.sfill i');
    /* 「正在跑哪一步」不能靠 verdict —— 跑动中的阶段此刻**还没有结论**，
       statusOf 会算成 idle ⇒ 节点不会是 .run ⇒ 进度条永远不推进。必须由 gauge 来标。 */
    const here=(S.stages||[]).some(s=>s.key===G.stage && String(s.step)===nd.dataset.step);
    nd.classList.toggle('run', !!here);
    if(!el||!tot) return;          // forEach 回调里只能 return，continue 会让整页 JS 解析失败
    if(here) el.style.width=Math.min(100,(dn+frac)/tot*100).toFixed(1)+'%';
    else if(!nd.classList.contains('done')) el.style.width=(dn/tot*100).toFixed(1)+'%';
  });
}
function gaugeSet(g){
  const el=$('#gauge'); if(!el) return;
  // 记下"这份数据是什么时候拿到的"：剩余时间靠它往下走。不记的话 `(G.at||now)` 每拍都
  // 等于 now、减数恒为 0 ⇒ 两次 8 秒轮询之间「剩余」是**死的**（「已用」走本地时钟，不受影响）。
  if(g&&g.at==null) g.at=Date.now()/1000;
  G=g;
  if(!g){ el.classList.remove('on'); el.innerHTML=''; GKEY='';
          const rl=$('#runline'); if(rl){ rl.classList.remove('on'); rl.innerHTML=''; }
          document.querySelectorAll('.snode.run').forEach(nd=>nd.classList.remove('run'));
          if(GT){ clearInterval(GT); GT=null; } return; }
  /* 骨架只在"结构变了"时重建：每 8 秒 innerHTML 一次会让脉冲重启、条宽从 0 重跑 transition，
     看着就是在闪。数字与宽度交给 gaugeTick 原地改。 */
  const key=(g.total||0)+'|'+(g.stage||'')+'|'+(g.eta_n?1:0)+'|'+(g.unit_total?1:0);
  if(key!==GKEY){
    GKEY=key;
    let ticks='';
    for(let i=0;i<Math.max(1,g.total||0);i++) ticks+='<s></s>';
    el.innerHTML=
      '<div class="grow"><i class="gdot"></i>'+
        '<span>阶段 <b>'+g.done+'/'+(g.total||'—')+'</b>'+
          (g.skipped?' <span class="gnote">跳过 '+g.skipped+'</span>':'')+'</span>'+
        '<span class="gst" id="gSt">'+esc(g.stage||'')+
          (g.stage_title?' · '+esc(g.stage_title):'')+'</span>'+
        '<span class="gsep"></span>'+
        '<span>已用 <b id="gEl">—</b></span>'+
        '<span>内存 <b id="gMem">—</b></span>'+
        '<span>剩余 <b id="gEta">—</b></span>'+
        (g.eta_n?'<span class="gnote" id="gSrc">'+gaugeSrc(g)+'</span>':'')+
      '</div>'+
      '<div class="grow"><span class="gbar"><i id="gFill"></i><u>'+ticks+'</u></span>'+
        '<span class="gun" id="gUn">—</span></div>';
  }
  el.classList.add('on');
  gaugeTick();
  if(!GT) GT=setInterval(gaugeTick,1000);
}
/* ══ 弹簧：所有"贵气"都来自这里 ══════════════════════════════════════
   为什么不用 cubic-bezier：贝塞尔曲线的尾巴是**匀速**的，弹簧会过冲再收回，
   那才是物理感。但弹簧有个必须付的代价 —— 它靠 rAF 跑，而本项目的硬约束是
   「静止时零个动画在跑、逐像素相同」。所以这里每条弹簧都在
   |位移|<0.0012 且 |速度|<0.012 时**写死到终点并停机**，
   全部停了就关掉 rAF；探针数 `__probe.springs()` 验这条。 */
const SPRG={m:new Map(),raf:0,last:0,
  to(id,t,apply,k,d,from){
    let c=this.m.get(id);
    if(!c){c={x:(from==null?t:from),v:0,t:t,apply:apply};this.m.set(id,c);}
    c.t=t; c.apply=apply; c.k=k||190; c.d=d==null?17:d;
    if(from!=null&&c.x===c.t&&c.x!==from) c.x=from;
    this.run(); return c;},
  run(){ if(this.raf) return; this.last=performance.now();
    const tick=ts=>{ let live=0;
      const dt=Math.min(0.034,(ts-this.last)/1000)||0.016; this.last=ts;
      for(const c of this.m.values()){
        const a=-c.k*(c.x-c.t)-c.d*c.v;         // 阻尼谐振子：k 刚度、d 阻尼
        c.v+=a*dt; c.x+=c.v*dt;
        if(Math.abs(c.x-c.t)<0.0012&&Math.abs(c.v)<0.012){c.x=c.t;c.v=0;}
        else live++;
        c.apply(c.x);
      }
      if(live) this.raf=requestAnimationFrame(tick); else this.raf=0;};
    this.raf=requestAnimationFrame(tick);},
  live(){ return this.raf?1:0; }};

/* ── 主行动按钮的磁吸 + 按压，全部走弹簧 ─────────────────────────────
   静止时 transform 必须回到**完全空**，否则"划过一圈再离开→回到同一张帧"会红。 */
const MAG={el:null};
function magPaint(){ const e=MAG.el; if(!e) return;
  // ⚠️ 弹簧条目只有 {x,v,t,k,d,apply}：位移是 x、速度是 v。这里曾把 y 轴写成 y.y
  //    （读一个不存在的字段）→ undefined.toFixed 抛异常 → **整条 rAF 循环被打死**，
  //    之后所有弹簧（含抽屉的进出）都不再更新，症状是"抽屉关不掉/卡片量不到"，
  //    看起来像版面问题，其实是一行拼写。apply 回调必须自己保证不抛。 */
  const x=SPRG.m.get('mx'), y=SPRG.m.get('my'), s=SPRG.m.get('ms');
  e.style.transform='translate3d('+(x?x.x:0).toFixed(2)+'px,'+(y?y.x:0).toFixed(2)+'px,0)'+
                     ' scale('+(s?s.x:1).toFixed(4)+')'; }
function magTo(el,dx,dy,press){
  if(MAG.el&&MAG.el!==el) magClear();
  MAG.el=el;
  SPRG.to('mx',dx,magPaint,260,20); SPRG.to('my',dy,magPaint,260,20);
  SPRG.to('ms',press?0.972:1,magPaint,320,22); }
function magClear(){ const e=MAG.el; if(!e) return;
  SPRG.to('mx',0,magPaint,150,17); SPRG.to('my',0,magPaint,150,17);
  SPRG.to('ms',1,magPaint,300,16);
  // 收敛后清掉内联 transform —— 留个 translate3d(0,0,0) 会改变合成层，像素比对会飘
  setTimeout(()=>{ if(!MAG.el&&e.style.transform&&/0\.000?0?\)/.test(e.style.transform))
                     e.style.transform=''; },420); }

/* ── 数字滚动：主屏那句里的量词是**数据**，让它从旧值滚到新值，
   而不是瞬间替换。滚动一次性收敛，不是常驻循环。 */
function rollNums(root){
  root.querySelectorAll('em[data-n]').forEach(el=>{
    const to=+el.dataset.n, from=el._shown==null?0:el._shown;
    if(from===to){ el.textContent=String(to); el._shown=to; return; }
    const t0=performance.now(), dur=760;
    const step=ts=>{ const p=Math.min(1,(ts-t0)/dur), e=1-Math.pow(1-p,3);
      el.textContent=String(Math.round(from+(to-from)*e));
      if(p<1) requestAnimationFrame(step); else el._shown=to; };
    requestAnimationFrame(step);
  });
}

/* ── 星野避让：主屏大字与主按钮**不坐面板**，可读性靠"星点不在这些矩形里显影"来保证。
   这是让装饰让步，不是给数据蒙一层纱 —— 蒙纱那条路实测 alpha .90 仍会被顶出 36 级差异。 */
function avoidRefresh(){
  const a=[];
  document.querySelectorAll('.eyebrow,.ask,.why,.do,.gate,.receipt,.foot').forEach(e=>{
    const r=e.getBoundingClientRect();
    if(r.width>2&&r.height>2&&r.bottom>0&&r.top<innerHeight)
      a.push([r.left-34,r.top-26,r.right+34,r.bottom+26]);});
  ST.avoid=a;
}

/* ══ 主屏那句话是怎么推出来的 ══════════════════════════════════════════
   优先级写死、可核对，不靠"看起来顺眼"：
     正在跑 > 卡住了 > 等你签字 > 还没做 > 这一步过了
   13 个阶段各自的「写到哪儿 / 判据 / 上次结论」是**证据**，全在「细节」抽屉里；
   主屏只留决策：一句现状 + 一个动作 + 一行"点下去会发生什么"。 */
const STEPNAME={1:'接模拟器',2:'同步配置表',3:'重新导出',4:'看图对比',5:'签字换入'};
/* 勾选的"签字放行"必须**存在这里**，不能只存在 DOM 上：
   ① 卡片每 8 秒可能被重绘，勾就丢了；② 更要紧的是主按钮「重跑到待确认」以前
   **根本不读这些框**（只有卡片上的「单独跑」读），用户勾完按主按钮，发出去的
   `approve` 永远是空的 —— 2026-10-01 用户就是在这儿卡住的（"我已经点了签字放行了呀"）。 */
const SIGNED=new Set();
function signedLive(){ return [...SIGNED].filter(k=>(S&&S.stages||[]).some(s=>s.key===k&&s.tier==='live')); }
function stepOfKey(k){ const s=((S&&S.stages)||[]).find(x=>x.key===k); return s?+s.step:0; }
function stepNo(k,d){ return stepOfKey(k)||d; }
function stepMax(){ const ks=Object.keys((S&&S.steps)||{}).map(Number);
  return ks.length?Math.max.apply(null,ks):5; }
function stepName(n){ return (S&&S.steps&&S.steps[String(n)]&&S.steps[String(n)][0])||STEPNAME[n]||''; }
/* 下一件该做的事在哪一步：第一个比 n 大、还有阶段没全绿的步骤。
   文案里的「去第 N 步」必须和真实跳转同一处算出来 —— 手写 nExport/nReview
   在步骤全部完成后会把用户指向一个已经做完的步骤（用户实测：第 5 步让他去第 3 步）。 */
/* 已发布皮肤表比本轮解出来的少行？少 = 第 2 步还有活（发布跑在解析刷新之前）。 */
function skinGapPending(){ return !!((S&&S.skin_gap)||{}).gap; }
/* 下一个**还有活**的步骤；全都跑完了返回 0（不再兜底成最后一步 ——
   2026-10-17 用户截图：第 2 步正文写"下一步：重算产物（第 3 步）"，按钮却把人
   送往已经 3/3 的第 5 步"签字换入"，两边各算各的）。 */
function nextWorkStep(n){
  const order=Object.keys((S&&S.steps)||{}).map(Number).sort((a,b)=>a-b);
  const nCfg=stepNo('cfg.publish',2);
  for(const k of order){
    if(k<=n) continue;
    /* 表漂移算第 2 步的活：阶段结论全绿，但发布出去的表缺行（§155）。 */
    if(k===nCfg && skinGapPending()) return k;
    if(stagesOf(k).some(s=>statusOf(s.key)!=='pass')) return k;
  }
  return 0;
}
/* 这一步会动什么，从阶段表当场算（档位数），不手抄 —— 手抄的那句在步骤
   已经跑完之后就会说谎（"要你签字才写正式区"其实早就签完了）。 */
function stepHint(n){
  const list=stagesOf(n);
  if(!list.length) return '';
  const c=(t)=>list.filter(s=>s.tier===t).length;
  const parts=[];
  if(c('staged')) parts.push(c('staged')+' 个只写暂存区');
  if(c('live')) parts.push(c('live')+' 个要签字才写正式区');
  if(c('read')) parts.push(c('read')+' 个只读');
  return parts.length?'（'+parts.join('，')+'）':'';
}
function allStagesPass(){
  const a=(S&&S.stages)||[];
  return a.length>0 && a.every(s=>statusOf(s.key)==='pass') && !skinGapPending();
}
/* 「去下一步」按钮 + 配套那句正文：同一个 nw 算出来，杜绝"正文说第 3 步、按钮去第 5 步"。 */
function nextStepAct(n){
  const nw=nextWorkStep(n);
  if(!nw) return {to:0, act:{a:'goto',to:1,t:'← 从第 1 步再来一轮',k:'pact mag'},
    why:'这一轮的阶段已全部判绿。'};
  return {to:nw, act:{a:'goto',to:nw,t:'去第 '+nw+' 步 '+stepName(nw)+' →',k:'pact mag'},
    why:'下一步：'+stepName(nw)+'（第 '+nw+' 步）'+stepHint(nw)+'。'};
}
/* 全局第一个没做完的步骤号（没有则 0）。第 5 步的"还没换完"靠它决定
   该往前跳还是就在本步开跑，不能再一律写死"去第 3 步"。 */
function firstGapStep(){
  if(skinGapPending()) return stepNo('cfg.publish',2);
  const g=((S&&S.stages)||[]).filter(s=>statusOf(s.key)!=='pass').map(s=>s.step).filter(Boolean);
  return g.length?Math.min.apply(null,g):0;
}
function askOf(n){
  const all=(S&&S.stages)||[], st=(S&&S.state)||{}, stn=statusOf;
  const list=n===0?all:stagesOf(n);
  /* 步骤号一律从阶段表反查，不再手抄。第 2 步「同步配置表」是后加的，
     手抄的 n===2/3/4 曾整体错位一位（第 2 步显示的是重导的文案），
     和 STEPNAME 那次是同一类漂移。 */
  const nConnect=stepNo('preflight',1), nCfg=stepNo('cfg.publish',2),
        nExport=stepNo('paintings',3), nReview=stepNo('review',4), nSwap=stepNo('swap-in',5);
  const eb='第 '+n+' 步 · '+stepName(n)+' · 共 '+
    ((Object.keys((S&&S.steps)||{}).length)||stepMax())+' 步';
  const fail=list.find(s=>stn(s.key)==='fail');
  const aw=list.filter(s=>stn(s.key)==='await');
  const idle=list.filter(s=>stn(s.key)==='idle');
  const nEm=v=>'<em data-n="'+v+'">'+v+'</em>';
  const detailOf=k=>((st[k]||{}).detail||'');
  const pf=st.preflight||null;
  const dm=/源\s*([\d-]+)\s*>\s*发布\s*([\d-]+)/.exec((pf&&pf.detail)||'');
  const dsrc=dm?dm[1]:'—', dpub=dm?dm[2]:'—';
  const stale=!!(pf&&!pf.ok&&/配置表过期/.test(pf.detail||''));
  /* 表漂移卡点：已发布的皮肤表比本轮解出来的少行（发布跑在解析刷新之前）。
     它和 preflight 的红是两件事：preflight 绿了，这条仍可能红 —— 2026-10-17 实测
     19:46 发布用了 09-25 的 scalar，21:11 才刷新，17/17 全绿却少 6 行。 */
  const sg=(S&&S.skin_gap)||null;
  const gapGate=(sg&&sg.gap>0)?{
    t:'发布出去的表比源旧 '+sg.gap+' 行',
    b:'已发布 '+sg.pub+' 行，本轮解出 '+sg.dev+' 行。缺的这些新皮肤现在没有名字，'+
      '语音档位也派不出去（'+(sg.sample||[]).join('、')+' 等）。重新同步并发布即可补上。',
    acts:[{a:'cfgsync',t:'⚑ 重新同步并发布',k:'pact sign mag'},
          {a:'detail',t:'看差在哪',k:'link2'}]
  }:null;
  /* 卡点只描述"跨步的前置条件"，不顶替本步的按钮。 */
  const gate=(pf&&!pf.ok)?{
    t: stale?'导出前置检查没过 · 配置表过期':'导出前置检查没过',
    b: stale
      ? ('盘上的配置源是 '+dsrc+'，inputs/gamecfg 里发布的是 '+dpub+'。'+
         '现在导出会拿旧表算舰名、阵营和语音，产物会对不上。同步配置表之后这道红会自己消。')
      : (detailOf('preflight')+'。它是导出的前置条件；拉包不受影响，但导出前得先修好。'),
    acts:(stale?[{a:'goto',to:nCfg,t:'▶ 去第 '+nCfg+' 步同步配置表',k:'pact mag'}]:[])
      .concat([{a:'recheck',t:'重查这道闸门',k:'link2'},
               {a:'detail',t:'看检查项',k:'link2'}])
  }:(!pf?{
    t:'还没查过导出的前置条件',
    b:'inputs/azdata、inputs/gamecfg 与画廊 vendor 是重导的唯一起点。先只读地查一遍，不写任何东西。',
    acts:[{a:'recheck',t:'▶ 先查一遍',k:'pact mag'},{a:'detail',t:'看检查项',k:'link2'}]
  }:null);

  if(n===nConnect){
    const pl=st.pull||{}, ps=stn('pull');
    if(ps==='fail') return {eb, red:1, ask:'拉包没成功',
      why:(pl.detail||'')+' 日志里有那行原因。',
      gate, acts:[{a:'pullcheck',t:'▶ 再试一次',k:'pact mag'},
                  {a:'detail',t:'看日志',k:'link2'}]};
    if(ps==='idle' && !pf) return {eb, gate,
      ask:'先确认权威输入还在位',
      why:'只读地查一遍 inputs/azdata、inputs/gamecfg 与画廊 vendor；不写任何东西。查完再看设备差异。',
      acts:[{a:'recheck',t:'▶ 先查一遍',k:'pact mag'},
            {a:'pullcheck',t:'同时看设备差异',k:'link2'}]};
    if(ps==='idle') return {eb, gate,
      ask: stale?'先接设备：看看多了什么':'看看模拟器上多了什么',
      why: stale
        ? '配置表过期只拦导出，不拦这一步：这里只读设备、算差异，不下载；确认要拉，才会签字写 files/。'
        : '只读地列一遍设备上的包、算出新增与变更，不下载。',
      acts:[{a:'pullcheck',t:'▶ 看设备上多了什么',k:'pact mag'},
            {a:'detail',t:'看这 '+list.length+' 个阶段',k:'link2'}]};
    if(ps==='await'){
      const m=/新增 (\d+)\/变更 (\d+)/.exec(pl.detail||'');
      return {eb, gate,
        ask:'模拟器上有 '+nEm(+(m?m[1]:0))+' 个新包、'+nEm(+(m?m[2]:0))+' 个变更还没拉到本地',
        why:'拉下来会写 files/AssetBundles；源包一旦被覆盖，旧版本本地就没了，所以要签字。'+
            (stale?'配置表还没对齐，但拉包不受影响。':''),
        acts:[{a:'pull',t:'⚑ 拉进本地',k:'pact sign mag'},
              {a:'pullcheck',t:'重算差异',k:'link2'}]};
    }
    const unreach=/设备不可达/.test(pl.detail||'');
    const nx1=nextStepAct(1);
    return {eb, gate,
      ask: unreach?'设备没连上，先用本地已有的包':'包已经在本地了',
      why: unreach?(pl.detail||'')+
        (stale?' 配置表也还没对齐：导出前先去第 '+nCfg+' 步。':'')
        : (stale?'但导出还开不了：配置表比源包旧，先去第 '+nCfg+' 步对齐。'
                :nx1.why),
      acts: stale
        ? [{a:'goto',to:nCfg,t:'▶ 去第 '+nCfg+' 步同步配置表',k:'pact mag'},
           {a:'detail',t:'看这 '+list.length+' 个阶段',k:'link2'}]
        : [nx1.act,{a:'pullcheck',t:'再算一遍差异',k:'link2'}]};
  }

  if(n===nCfg){
    const cfg=list, idleN=cfg.filter(s=>stn(s.key)==='idle').length;
    const failCfg=cfg.find(s=>stn(s.key)==='fail');
    if(failCfg) return {eb, red:1, ask:failCfg.key+' 判红，配置表没同步完',
      why:detailOf(failCfg.key)+' 修好再重跑；它前面已经判绿的阶段不会重跑。',
      acts:[{a:'cfgsync',t:'▶ 重跑同步',k:'pact sign mag'},
            {a:'detail',t:'看日志',k:'link2'}]};
    /* 阶段结论全绿、但发布出去的表还差行：这是缓存造成的假绿，
       必须自己说出来，否则用户会停在"配置表已对齐源包"上不动（§155）。 */
    if(gapGate) return {eb, red:1, gate:gapGate,
      ask:'配置表解出来了，但还没发布出去',
      why:'已发布 '+sg.pub+' 行 / 本轮解出 '+sg.dev+' 行，差 '+sg.gap+' 行。'+
          '缺行的皮肤现在没名字，第 3 步的元数据和语音档位也会漏它们。',
      acts:[{a:'cfgsync',t:'⚑ 重新同步并发布',k:'pact sign mag'},
            {a:'detail',t:'看差在哪',k:'link2'}]};
    if(idleN===cfg.length) return {eb,
      ask: stale?('把配置表对齐到 '+dsrc+' 的源包'):'从源包重解配置表',
      why:'4 个阶段：解 scripts → 导出 lua → 解析 sharecfg → 发布 inputs/gamecfg。约 7 分钟'+
          '（恒为强制重解，不用缓存）；前三步只写 .diag/，最后一步写正式区、要签字。'+
          '修好之后第 1 步那道红会自动消。',
      acts:[{a:'cfgsync',t:'⚑ 同步配置表',k:'pact sign mag'},
            {a:'detail',t:'看这 4 步写到哪儿',k:'link2'}]};
    if(idleN) return {eb, ask:'配置表还剩 '+nEm(idleN)+' 个阶段没跑',
      why:'继续跑会把剩下的补齐；已经判绿的（同一批输入）不会重跑。',
      acts:[{a:'cfgsync',t:'▶ 补齐剩下的',k:'pact sign mag'},
            {a:'detail',t:'看是哪几个',k:'link2'}]};
    if(aw.length) return {eb, ask:'配置表解好了，发布那一步等你签字',
      why:'inputs/gamecfg 是导出的权威元数据，写正式区要签字；签了才会覆盖。',
      acts:[{a:'cfgsync',t:'⚑ 签字发布',k:'pact sign mag'},
            {a:'detail',t:'看写到哪儿',k:'link2'}]};
    const nxCfg=nextStepAct(nCfg);
    return {eb, ask:'配置表已对齐源包',
      why:nxCfg.why,
      acts:[nxCfg.act,{a:'detail',t:'看这 4 步写到哪儿',k:'link2'}]};
  }

  if(n===nExport){
    if(pf&&!pf.ok) return {eb, red:1, gate,
      ask: stale?'导出被配置表挡着':'导出前置检查没过',
      why: stale?'配置表比源包旧时导出的元数据是错的，所以流水线会先停。同步完再回来，按钮就能按。'
                :'先修好第 1 步那道检查再导出；否则算出来的元数据不可信。',
      acts: stale
        ? [{a:'goto',to:nCfg,t:'▶ 去第 '+nCfg+' 步同步配置表',k:'pact mag'},
           {a:'detail',t:'看检查项',k:'link2'}]
        : [{a:'recheck',t:'▶ 重查闸门',k:'pact mag'},
           {a:'detail',t:'看检查项',k:'link2'}]};
    /* 表漂移：preflight 绿了也不放行导出 —— 拿旧表导出的元数据/语音档位就是缺新皮肤。
       先回第 2 步把发布补上（§155）。 */
    if(gapGate) return {eb, red:1, gate:gapGate,
      ask:'导出被旧皮肤表挡着',
      why:'已发布的表比本轮解出来的少 '+sg.gap+' 行，现在导出会漏掉这些新皮肤的元数据和语音。'+
          '先回第 2 步重新发布。',
      acts:[{a:'goto',to:nCfg,t:'▶ 去第 '+nCfg+' 步重新发布',k:'pact mag'},
            {a:'detail',t:'看差在哪',k:'link2'}]};
    if(fail) return {eb, red:1, ask:fail.key+' 这一步没过',
      why:detailOf(fail.key)+' 日志里有那行原因。',
      acts:[{a:'export',t:'▶ 再跑一次',k:'pact mag'},{a:'detail',t:'看日志',k:'link2'}]};
    if(idle.length===list.length) return {eb, ask:'从源包重算 '+nEm(list.length)+' 类产物',
      why:'立绘 / Spine / Live2D 只写暂存区；依赖表、元数据、语音、CG 要你签字才动正式区。'+
          '点下去会先弹确认单，再决定签不签。要跑一会儿。',
      acts:[{a:'export',t:'▶ 开始重导',k:'pact mag'}]};
    if(aw.length) return {eb, ask:'重导好了 '+nEm(list.length-idle.length)+' / '+nEm(list.length)+
        ' 项，其中 '+nEm(aw.length)+' 项要你签字才写正式区',
      why:'这 '+aw.length+' 项只算了差异，正式区一个字节没碰。点主按钮会先弹签字单；'+
          '不想签就按单子左下角「只跑到待确认」。',
      acts:[{a:'export',t:'⚑ 处理这 '+aw.length+' 项（签字）',k:'pact sign mag'},
            {a:'staged',t:'只重跑暂存三件',k:'link2'}]};
    if(idle.length) return {eb, ask:'重导跑好了 '+nEm(list.length-idle.length)+' 项，还剩 '+nEm(idle.length)+' 项',
      why:'继续跑会把剩下的算完。',
      acts:[{a:'export',t:'▶ 跑完剩下的',k:'pact mag'}]};
    const nxExp=nextStepAct(nExport);
    return {eb, ask:'产物都重导好了',
      why:'这一步不写任何正式产物。'+nxExp.why,
      acts:[nxExp.act,{a:'detail',t:'看这 '+list.length+' 项写到哪儿',k:'link2'}]};
  }

  if(n===nReview){
    const rv=st.review;
    if(fail) return {eb, red:1, ask:'对照表没做出来', why:(rv&&rv.detail)||'',
      acts:[{a:'review',t:'▶ 再出一次',k:'pact mag'},{a:'detail',t:'看日志',k:'link2'}]};
    if(!rv) return {eb, ask:'出一张改前 | 改后的对照表',
      why:'纯读，随时可以反复跑。图会放在「细节」里，点开能放大。',
      acts:[{a:'review',t:'▶ 出对照表',k:'pact mag'}]};
    const nxRv=nextStepAct(nReview);
    return {eb, ask:'对照表好了，'+nEm((S.sheets||[]).length)+' 张，'+
        (allStagesPass()?'本轮已照过、也已换入':'看一眼再决定换不换'),
      why:'这一步不写任何正式产物。'+nxRv.why,
      acts:[{a:'detail',t:'打开对照表',k:'pact mag'},nxRv.act]};
  }

  const live5=list.filter(s=>s.tier==='live'), aw5=live5.filter(s=>stn(s.key)==='await');
  /* 「换完了」这句必须看**全部阶段**，其余几句也要带上"这轮还有哪几档没跑"。
     2026-10-01 实测的假绿灯：用户只跑了 swap-in/derive/regress，第 2 步的立绘一张没重导，
     主屏却大字写「这次更新已经换完了」。 */
  const allSt=S.stages||[], notYet=allSt.filter(s=>stn(s.key)==='idle');
  const whereNot=notYet.map(s=>'第 '+s.step+' 步 '+s.key).join('、');
  const tail=notYet.length?(' 这轮还有 '+notYet.length+' 项没跑过：'+whereNot+'。'):'';
  /* 「还没换完」时该干什么，看**第一个缺口在哪一步**：
     缺口在前面（例：第 4 步对照表没出）→ 跳到那一步；缺口就在本步（swap-in/derive/regress 没跑）
     → 在本步开跑（换入要签字）。以前一律写死"去第 3 步重导"，
     用户在第 5 步被指回已经做完的第 3 步，点了还落到第 1 步（goto 没带 data-to）。 */
  const gap=firstGapStep();
  /* 暂存区是不是这一轮的，决定那句警告怎么说：第 3 步全绿 ⇒ 是刚重导出来的，
     可以放手换；否则可能是上一批的遗留，用户会拿它当"已重导"（2026-10-01 假绿灯）。 */
  const fresh = stagesOf(nExport).length>0 && stagesOf(nExport).every(s=>stn(s.key)==='pass');
  const staleWarn = fresh
    ? '暂存区是这一轮刚重导出来的，可以直接换。'
    : '暂存区里现在这些可能是上一批留下的，别当成"已重导"。';
  const goGap = (gap && gap<n)
    ? {a:'goto',to:gap,t:'▶ 去第 '+gap+' 步 '+stepName(gap),k:'pact mag'}
    : {a:'swap',t:'⚑ 换入正式区',k:'pact sign mag'};
  if(notYet.length && !aw5.length && !fail && !live5.some(s=>stn(s.key)==='pass'))
    return {eb, red:1, ask:'还没换完：有 '+nEm(notYet.length)+' 项这轮根本没跑',
      why:'没跑过的项不算完成。差在：'+whereNot+'。'+staleWarn,
      acts:[goGap,{a:'detail',t:'看是哪几项',k:'link2'}]};
  if(fail) return {eb, red:1, ask:fail.key+' 这一步没过',
    why:'闸门判红说明这次换入会丢东西——别绕，先查源包。'+tail,
    acts:[{a:'swap',t:'⚑ 再试一次换入',k:'pact sign mag'},
          {a:'detail',t:'看日志',k:'link2'}]};
  if(aw5.length) return {eb, ask:nEm(aw5.length)+' 项暂存产物等着换进正式区',
    why:'换入前整批备份到 Output/_OLD_bak/；索引有零回退闸门，会掉条目就直接停。'+tail,
    acts:[{a:'swap',t:'⚑ 换入正式区',k:'pact sign mag'},
          {a:'regress',t:'只跑回归',k:'link2'}]};
  if(!live5.some(s=>stn(s.key)==='pass')&&!S.running)
    return {eb, ask:'现在没有待换入的东西',
      why:'先跑第 '+nExport+' 步（重导）和第 '+nReview+' 步（看图），暂存区里有货了这里才会亮。'+
          (notYet.length?('没跑过的正是：'+whereNot+'。'):''),
      acts:[{a:'goto',to:nExport,t:'← 去第 '+nExport+' 步重导',k:'pact mag'},
            {a:'detail',t:'看暂存区有什么',k:'link2'}]};
  if(notYet.length){
    const byStep={};
    notYet.forEach(s=>{ (byStep[s.step]=byStep[s.step]||[]).push(s.key); });
    const where=Object.keys(byStep).map(k=>'第 '+k+' 步（'+byStep[k].join(' / ')+'）').join('、');
    return {eb, red:1, ask:'还没换完：有 '+nEm(notYet.length)+' 项这轮根本没跑',
      why:'没跑过的项不算完成。差在：'+where+'。'+staleWarn,
      acts:[goGap,{a:'detail',t:'看是哪几项',k:'link2'}]};
  }
  return {eb, ask:'这次更新已经换完了', why:'画廊已部署、回归跑过；要再来一轮就从第 1 步开始。',
    acts:[{a:'regress',t:'▶ 只跑回归',k:'pact mag'},{a:'detail',t:'看细节',k:'link2'}]};
}

function render(){
  RENDERED=true;
  if(!S) return;
  if(LASTSTEP!==step){ mounted.clear(); LASTSTEP=step; }   // 切步骤 = 这批卡的首次出现
  $('#fp').textContent=S.fingerprint||'—';
  $('#scope').textContent = S.scope==null ? '未算' : '增量 '+S.scope+' 项';
  const all=S.stages||[];
  const passN=all.filter(s=>statusOf(s.key)==='pass').length;
  $('#prog').textContent=passN+' / '+all.length;
  if(LOADERR){ $('#warn').textContent='读状态失败：'+LOADERR+'（2.5 秒后自动重试）';
    $('#warn').classList.add('on'); }
  else if(S.error){ $('#warn').textContent='读阶段清单失败：'+S.error; $('#warn').classList.add('on'); }
  else if(!all.length){ $('#warn').textContent='阶段清单为空：update_pipeline 没读到。';
    $('#warn').classList.add('on'); }
  else $('#warn').classList.remove('on');

  /* ── 底部步骤条：五个节点，节点上带该步全部阶段的状态方块 ─────────────
     判据「13 个阶段一个都不许被折叠掉」靠这里每个 dot 都在。 */
  const steps=S.steps||{}, bar=$('#stepsbar');
  const cur=currentStep();
  const rc=$('#railCount'); if(rc) rc.textContent=all.length+' 个阶段';
  const rcur=$('#railCur');
  /* 全判绿时右栏写「已跑完」，不再写「待办 05」——那一行在 17/17 全绿时
     会把人骗去找一件已经做完的事（2026-10-17 用户截图就是这个状态）。 */
  if(rcur) rcur.textContent=(S.running?'正在跑 ':(allStagesPass()?'已跑完 ':'待办 '))+
    String(cur).padStart(2,'0');
  bar.querySelectorAll('.snode').forEach(e=>e.remove());
  Object.keys(steps).sort().forEach(k=>{
    const n=+k, list=stagesOf(n);
    const worst=list.map(s=>statusOf(s.key))
      .reduce((a,b)=>['fail','run','await','pass','idle'].indexOf(a)<=['fail','run','await','pass','idle'].indexOf(b)?a:b,'idle');
    const doneN=list.filter(s=>statusOf(s.key)==='pass').length;
    const b=document.createElement('button');
    const fresh='s'+n, first=!mounted.has(fresh); mounted.add(fresh);
    b.className='snode'+(n===step?' on':'')+(n===cur?' cur':'')+(first?' in':'')+
      (worst==='fail'?' fail':worst==='await'?' await':worst==='run'?' run':
       doneN===list.length&&list.length?' done':'');
    b.title = n===cur ? (allStagesPass() ? '这一步也跑完了' : '待办：这一步还有没跑完的阶段')
                      : '查看第 '+n+' 步（不改变待办，按钮照样能按）';
    if(first) b.style.animationDelay=(n*70)+'ms';
    b.dataset.step=n; b.dataset.done=doneN; b.dataset.total=list.length;
    b.innerHTML='<span class="bead"></span><label>'+esc(steps[k][0])+'</label>'+
      '<span class="sdots">'+list.map(s=>'<i class="dot '+statusOf(s.key)+'" title="'+esc(s.key)+'"></i>').join('')+'</span>'+
      '<span class="cnt">'+doneN+'/'+list.length+'</span>'+
      '<span class="sfill"><i style="width:'+(list.length?Math.round(doneN/list.length*100):0)+'%"></i></span>';
    b.onclick=()=>{ step=n; render(); };
    bar.appendChild(b);
  });
  stepFill();
  /* 「正在看」与「待办」分开显示：点别的步骤只换视图，不改变待办；
     那一步的按钮仍然可用，所以提示里写「查看」而不是「只读」。 */
  const stEl=$('#stepState');
  if(stEl){
    const done=allStagesPass();
    stEl.textContent = done ? '已跑完' : (step===cur ? '待办' : '查看中');
    stEl.className = 'stepstate ' + (step===cur ? 'cur' : 'preview');
  }
  const vn=$('#viewnote'), vtx=$('#viewnoteTx'), bb=$('#bBackCur');
  if(vn){
    vn.hidden = step===cur;
    if(step!==cur){
      /* 说清"你在看哪"和"该去哪儿"。不要写"只读预览"——切到别的步骤，
         那一步的按钮仍然能按（第 1 步在配置表过期时也能拉包）。 */
      vtx.innerHTML = '你在看第 '+step+' 步 · <b>'+esc((steps[String(step)]||[])[0]||'')+
        '</b>（按钮照样能按）　'+
        (allStagesPass() ? '这一轮的阶段已全部判绿'
                         : ('待办是第 '+cur+' 步 · <b>'+esc((steps[String(cur)]||[])[0]||'')+'</b>'));
      if(bb) bb.textContent = allStagesPass() ? '去第 1 步' : ('去第 '+cur+' 步');
    }
  }
  /* 节点是刚重建出来的 —— "哪一步在跑"这个标记必须**重建之后再打一次**，
     否则 8 秒轮询会把 gaugeTick 打上的 .run 冲掉（探针实测：进度条永远停在已完成数上）。 */
  if(G) gaugeTick();

  /* ── 主屏 ─────────────────────────────────────────────────────────── */
  const A=askOf(step);
  /* 跨步的红不许被"本步挺好"盖掉：一次只暴露下一步是对的，但"另有 N 步判红"必须说一句 ——
     2026-10-01 用户就是在这里迷路的：regress 红着（真因是画廊服务器没起），
     大字却写「重导好了 7/7 项」，看起来像一切就绪。 */
  const redAll=(S.stages||[]).filter(s=>statusOf(s.key)==='fail');
  /* preflight 因配置表过期判红时，它的修复动作就在第 2 步：在第 1~3 步里
     别再补一句"另有 1 步判红（第 1 步）"，那正是当前这张卡点在说的事。 */
  const stalePf=!!(S.state&&S.state.preflight&&!S.state.preflight.ok&&
                   /配置表过期/.test(S.state.preflight.detail||''));
  const outSteps=[...new Set(redAll.map(s=>s.step))]
    .filter(n=>n!==step && !(stalePf&&n===stepNo('preflight',1)&&step<=stepNo('paintings',3)));
  if(redAll.length && outSteps.length)
    A.why += ' 另有 '+redAll.length+' 步判红（第 '+outSteps.join('、')+' 步），「细节」里能看到原因。';
  const eb=$('#eyebrowTx'), ask=$('#ask'), why=$('#why'), foot=$('#scopeNote');
  eb.textContent = S.running ? ('正在跑 · '+S.running.label) : A.eb;
  $('#eyebrow').classList.toggle('red', !!A.red);
  $('#eyebrow').classList.toggle('run', !!S.running);
  if(ask.innerHTML!==A.ask){
    ask.innerHTML=A.ask; rollNums(ask);
    if(RENDERED&&!CALM){ ask.classList.remove('swap'); void ask.offsetWidth; ask.classList.add('swap'); }
  }
  why.textContent=A.why;
  /* 卡点：跨步前置条件（配置表过期挡导出）。它有自己的动作，但不顶替本步按钮。 */
  const gateEl=$('#gate');
  if(gateEl){
    if(A.gate){
      gateEl.hidden=false;
      gateEl.innerHTML='<span class="gt">'+esc(A.gate.t)+'</span>'+
        '<p class="gb">'+esc(A.gate.b)+'</p>'+
        '<div class="ga">'+A.gate.acts.map(c=>
          '<button class="'+c.k+'" data-a="'+c.a+'"'+(c.to?' data-to="'+c.to+'"':'')+'>'+
          c.t+'</button>').join('')+'</div>';
    }else{
      gateEl.hidden=true; gateEl.innerHTML='';
    }
  }
  foot.textContent=A.foot||'';
  foot.classList.toggle('on',!!A.foot);
  /* 主按钮也必须带 `data-to`：`goto` 的目标只从 DOM 上取。漏了它，
     点「去第 3 步」会落到第 1 步（`+undefined||1`）——2026-10-17 用户就是这样
     在第 5 步点了「去第 3 步重导」，结果被扔回第 1 步。 */
  $('#cta').innerHTML=A.acts.map(c=>(c.k.indexOf('link2')>=0
      ? '<button class="link2" data-a="'+c.a+'"'
      : '<button class="'+c.k+'" data-a="'+c.a+'"')+
      (c.to?' data-to="'+c.to+'"':'')+'>'+c.t+'</button>').join('');
  avoidRefresh();

  const ungrouped=all.filter(s=>!steps[s.step||0]);
  if(ungrouped.length){
    foot.textContent='有 '+(ungrouped.map(s=>s.key).join(', '))+' 没归到任何一步，先补 step';
    foot.classList.add('on');
  }
  /* 勾了字就必须**在主屏上看得见**——勾是瞬时的、写正式区是不可逆的，
     一句"已勾签字：…"比一个藏在抽屉里的小方框靠谱。 */
  const apSign=signedLive();
  if(apSign.length){
    foot.textContent=(foot.textContent?foot.textContent+' ':'')+
      '已勾签字：'+apSign.join('、')+' —— 下一轮就会直接写正式区（换入前整批备份）。';
    foot.classList.add('on');
  }

  /* ── 抽屉里的证据（结构与旧版一致，判据一条都不放松） ───────────────── */
  const list=step===0?all:stagesOf(step);
  $('#sCount').textContent=list.length+' 个';
  const cards=$('#cards'); cards.innerHTML='';
  list.forEach((s,i)=>{
    const stt=statusOf(s.key), r=(S.state||{})[s.key]||{}, T=TIER[s.tier]||['?','r'];
    const d=document.createElement('div');
    const first=!mounted.has(s.key); mounted.add(s.key);
    d.className='stage'+(first?' in':'')+
      (stt==='fail'?' fail':stt==='await'?' await':'');
    if(first) d.style.animationDelay=(60+i*26)+'ms';
    d.innerHTML='<div class="srow"><span class="skey">'+esc(s.key)+'</span>'+
      '<span class="tier '+T[1]+'">'+T[0]+'</span>'+
      '<span class="stt '+stt+'">'+STT[stt]+'</span></div>'+
      '<p class="stitle">'+esc(s.title)+'</p>'+
      '<dl class="kv">'+
      '<dt>写到</dt><dd>'+esc(s.writes||'—')+'</dd>'+
      '<dt>判据</dt><dd>'+esc(s.judge||'—')+'</dd>'+
      (r.detail?'<dt>上次</dt><dd>'+esc(r.detail)+(r.at?'　<span class="dim">'+esc(r.at)+'</span>':'')+'</dd>':'')+
      '</dl>'+
      '<div class="sact">'+
      (s.tier==='live'?'<label class="signbox'+(SIGNED.has(s.key)?' on':'')+
        '"><input type="checkbox" class="appr" data-k="'+s.key+'"'+
        (SIGNED.has(s.key)?' checked':'')+'> 签字放行</label>':'')+
      '<button class="mini" data-run="'+esc(s.key)+'">单独跑</button>'+
      '<span class="spacer"></span></div>';
    cards.appendChild(d);
  });

  const sh=$('#sheets');
  if(!(S.sheets||[]).length) sh.innerHTML='<p class="dim" style="font-size:12px;margin:0">'+
    '还没有对照表 · 先跑第 3 步</p>';
  else sh.innerHTML=S.sheets.map(x=>'<a target="_blank" href="/file?path='+encodeURIComponent(x.name)+
    '"><img loading="lazy" src="/file?path='+encodeURIComponent(x.name)+'" alt="'+esc(x.name)+
    '"><div class="cap"><span>'+esc(x.name)+'</span><span>'+x.kb+'KB '+esc(x.mt)+'</span></div></a>').join('');

  /* ── 这次新增了什么（用户："我怎么知道这次新增了什么、是否合格"）────────────
     每行给"够不合格判断"的四件事：叫什么、属于哪艘船、有没有语音、进正式区了没。
     图不重复贴 —— 点表头那个链接看对照总表（图片路由仍只从 .diag/pipeline 出）。 */
  const nw=S.news||{rows:[]}, nt=$('#newtbl'), ns=$('#newsum');
  if(ns) ns.textContent = nw.rows.length
      ? ('新增 '+nw.rows.length+' 张 · 已在正式区 '+nw.live_n+' · 待换入 '+(nw.rows.length-nw.live_n))
      : '';
  if(!nt) { /* 节点没插进来就是接线断了，宁可哑掉也不留半截表 */ }
  else if(!nw.rows.length) nt.innerHTML='<p class="dim" style="font-size:12px;margin:0">'+
      esc(nw.note||'这次更新没有新增皮肤（或还没跑第 3 步的对照表）')+'</p>';
  else nt.innerHTML='<table class="newt"><thead><tr><th>皮肤</th><th>舰名 / 阵营</th>'+
      '<th>稀有度</th><th>语音</th><th>状态</th></tr></thead><tbody>'+nw.rows.map(r=>
      '<tr><td><code>'+esc(r.stem)+'</code>'+(r.skin?'<span class="dim"> · '+esc(r.skin)+'</span>':'')+
      '</td><td>'+(r.meta?esc(r.ship)+' <span class="dim">'+esc(r.faction)+'</span>'
                         :'<span class="warn">元数据缺（舰名取不到）</span>')+
      '</td><td>'+esc(r.rarity||'—')+'</td><td>'+(r.voice?r.voice+' 条':'<span class="warn">无</span>')+
      '</td><td>'+(r.live?'<span class="tag pass">已换入</span>'
                         :'<span class="tag await">待换入</span>')+'</td></tr>').join('')+
      '</tbody></table>'+(nw.sheet?'<p class="dim" style="font-size:11.5px;margin:6px 0 0">'+
      '<a class="link2" target="_blank" href="/file?path='+encodeURIComponent(nw.sheet)+
      '">改前 | 改后 对照总表（新增的左侧标"线上没有这张"）</a></p>':'');

  $('#runs').innerHTML=(S.runs||[]).map(rr=>'<tr><td class="dim" style="white-space:nowrap">'+
    esc((rr.started||'').slice(11))+'</td><td>'+esc(rr.label||'')+
    '<div class="dim" style="font-size:11px">'+esc(rr.state==='done'?(rr.clean===false?'没看到收尾行':'完成'):rr.state||'')
    +'</div></td><td style="text-align:right"><span class="tag '+esc(rr.state||'')+'">'+
    (rr.state==='running'?'在跑':'看日志')+'</span></td></tr>').join('')||
    '<tr><td colspan="3" class="dim">还没有任务</td></tr>';
  $$('#runs tr').forEach((tr,i)=>{ const rr=(S.runs||[])[i]; if(!rr) return;
    tr.style.cursor='pointer'; tr.onclick=()=>{ tail(rr.id); openDetail(); }; });
  $$('#cta button, #gate button[data-a]').forEach(b=>b.onclick=()=>
    ctaRun(b.dataset.a, b.dataset.to));
  $$('#cards .appr').forEach(cb=>cb.onchange=e=>{
    const k=e.target.dataset.k, box=e.target.closest('.signbox');
    if(e.target.checked) SIGNED.add(k); else SIGNED.delete(k);
    box.classList.toggle('on', e.target.checked);
    render();                       // 勾了就要在主屏上看得见（下面那句"已勾签字"）
  });
  $$('#cards .stage').forEach(el=>{
    el.addEventListener('mouseenter',()=>{ const k=el.querySelector('.skey').textContent;
      const d=document.querySelector('.snode .dot[title="'+k+'"]'); if(d) d.classList.add('hot'); });
    el.addEventListener('mouseleave',()=>{ [...document.querySelectorAll('.dot.hot')]
      .forEach(d=>d.classList.remove('hot')); });
  });
  $$('#cards [data-run]').forEach(b=>b.onclick=()=>{
    const k=b.dataset.run, s=(S.stages||[]).find(x=>x.key===k);
    const ap=s&&s.tier==='live'&&b.closest('.stage').querySelector('.appr').checked;
    if(ap){
      openSign({keys:[k],what:'单独跑 '+k,
        note:'它会写进正式区（换入前先备份）。单独跑不经过「重跑到待确认」的整批清单，确认范围只有这一个阶段。',
        onOk:()=>post({stages:[k],approve:[k],force:force})});
      return;
    }
    post({stages:[k],approve:[],force:force},null); });
}

/* 进度线**长到**当前节点，不是瞬间跳过去。弹簧用高阻尼（不过冲）——
   它会从左边伸出头，那看着像 bug 不像物理。 */
function stepFill(){
  const nodes=$$('.snode'), fill=$('#stepfill'), bar=$('#stepsbar');
  if(!nodes.length||!fill) return;
  const br=bar.getBoundingClientRect();
  const on=nodes[step-1]||nodes[0];
  const r=on.getBoundingClientRect();
  const target=Math.max(0, r.left+r.width/2-br.left);
  const prev=fill._x==null?target:fill._x;
  fill._x=target;
  if(CALM||prev===target){ fill.style.width=target+'px'; return; }
  SPRG.to('fill',target,v=>{ fill.style.width=Math.max(0,v).toFixed(1)+'px'; },150,26,prev);
}
/* ── 签字窗口 ───────────────────────────────────────────────────────
   原生 confirm() 是浏览器画的，和纸本界面两层皮；它也放不下一张「会写哪几个阶段、
   写到哪儿、有没有备份」的清单。这里用同一套纸/墨/朱砂画一张签字单：
   范围逐条列出 → 勾选确认 → 签名 → 才放行。 */
let SIGN_CTX=null, SIGN_ALT=null;
function syncSign(){
  const name=($('#signName').value||'').trim();
  $('#signGo').disabled = !($('#signAgree').checked && name);
}
function openSign(o){
  SIGN_CTX=o; SIGN_ALT=o.alt||null;
  $('#signWhat').textContent=o.what||'';
  $('#signList').innerHTML=(o.keys||[]).map(k=>{
    const s=(S.stages||[]).find(x=>x.key===k)||{};
    const T=TIER[s.tier]||['?','r'];
    return '<div class="srow"><div>'+
      '<div class="k">'+esc(k)+'</div>'+
      '<span class="t">'+esc(s.title||'')+'</span>'+
      '<span class="w">写到 '+esc(s.writes||'—')+'</span></div>'+
      '<span class="tier '+T[1]+'">'+T[0]+'</span></div>';
  }).join('');
  $('#signNote').textContent=o.note||'';
  const alt=$('#signAlt');
  if(alt){ alt.hidden=!SIGN_ALT; alt.textContent=SIGN_ALT?(SIGN_ALT.label||'不签字，先跑只读的那一半'):''; }
  $('#signAgree').checked=false;
  $('#signName').value=localStorage.getItem('panel.signer')||'';
  $('#signDate').textContent=new Date().toLocaleString('zh-CN',{hour12:false});
  syncSign();
  $('#signmodal').classList.add('on');
  $('#signmodal').setAttribute('aria-hidden','false');
  setTimeout(()=>{ ($('#signName').value?$('#signAgree'):$('#signName')).focus(); },30);
}
function closeSign(){
  $('#signmodal').classList.remove('on');
  $('#signmodal').setAttribute('aria-hidden','true');
  SIGN_CTX=null; SIGN_ALT=null;
}
$('#signAgree').onchange=syncSign;
$('#signName').oninput=syncSign;
$('#signGo').onclick=()=>{
  if($('#signGo').disabled||!SIGN_CTX) return;
  const nm=($('#signName').value||'').trim();
  if(nm) localStorage.setItem('panel.signer',nm);
  const cb=SIGN_CTX.onOk;
  closeSign();
  if(cb) cb(nm);
};
/* 「不签字，先跑只读的那一半」：这是签字单里的退路，不是取消。
   第 3 步的重导在未签字时仍会产出暂存区与差异，只有 live 阶段不写正式区。 */
$('#signAlt').onclick=()=>{
  if(!SIGN_ALT) return;
  const run=SIGN_ALT.run;
  closeSign();
  if(run) run();
};
$$('#signmodal [data-sclose]').forEach(el=>el.onclick=closeSign);

/* 每个动作**只跑自己这一步的阶段**。跨步的前置条件（配置表过期）由卡点说明，
   不再悄悄把整条管线从 preflight 拉起 —— 那样 preflight 一红就什么都不跑，
   界面又只留一个「再查一次」，用户点了没反应，自然不知道发生了什么。 */
function actStages(a){
  const byStep=n=>stagesOf(n).map(s=>s.key);
  switch(a){
    case 'recheck':   return ['preflight'];
    case 'pullcheck': return ['pull'];
    case 'pull':      return ['pull'];
    case 'cfgsync':   return byStep(stepNo('cfg.publish',2));
    case 'export':    return byStep(stepNo('paintings',3));
    case 'staged':    return ['paintings','spine','live2d'];
    case 'review':    return ['review'];
    case 'swap':      return byStep(stepNo('swap-in',5));
    case 'regress':   return ['regress'];
    default:          return [];
  }
}
function liveOf(keys){
  return keys.filter(k=>{ const s=(S.stages||[]).find(x=>x.key===k); return s&&s.tier==='live'; });
}
function ctaRun(a, to){
  if(a==='next') return void (step=Math.min(stepMax(),step+1), render());
  if(a==='goto') return void (step=Math.max(1,Math.min(stepMax(),+to||1)), render());
  if(a==='prev') return void (step=Math.max(1,step-1), render());
  if(a==='detail') return void openDetail();
  if(a==='diff'||a==='recheck') return post({stages:['preflight']},{label:'重查闸门'});
  if(a==='pullcheck') return post({stages:['pull']},{label:'看设备差异'});
  if(a==='pull'){
    openSign({keys:['pull'], what:'第 1 步：从模拟器拉包',
      note:'adb pull 写进 files/AssetBundles（只补缺的和变了的）。'+
           '源包一旦覆盖，旧版本本地就没了 —— 所以它要你签字。',
      onOk:()=>post({stages:['pull'],approve:['pull'],force:force},{label:'拉包'})});
    return;
  }
  if(a==='cfgsync'){
    const keys=actStages('cfgsync'), live=liveOf(keys);
    /* 恒 `force`：cfg.disk 是 staged 档、会被"同指纹已完成"缓存跳过，
       而它正是刷新 `cfg_json_scalar`（发布真正读的皮肤表）的那一步。
       2026-10-17：缓存让 cfg.disk 跳过 ⇒ 发布把 09-25 的旧皮肤表重新抄了一遍，
       新皮肤没名字、`_3` 档语音一条没解（§155）。同步配置表本来就该重解，不省这几分钟。 */
    const go=()=>post({stages:keys,approve:live,force:true},
                     {label:'同步配置表', after:['preflight']});
    if(!live.length) return go();
    openSign({keys:live, what:'第 '+stepNo('cfg.publish',2)+' 步：同步配置表',
      note:'会强制重解 sharecfgdata（--scalar-all，约 7 分钟，不用缓存）。'+
           '前 3 个阶段只写 .diag/；cfg.publish 会写 inputs/gamecfg（导出用的权威元数据）。'+
           '发布前有 4 道闸门，红了就停。跑完会自动重查第 1 步的 preflight。',
      onOk:go});
    return;
  }
  if(a==='export'){
    const keys=actStages('export'), live=liveOf(keys);
    const runUnsigned=()=>post({stages:keys,approve:[],force:force},
                               {label:'重新导出（不签字）'});
    if(!live.length) return runUnsigned();
    /* 只要这一步有 live 阶段，主按钮就先弹签字单，绝不"点了直接开跑"。
       2026-10-17 用户点「重跑到待确认」→ 直接跑完又回到同一屏，以为坏了。
       单子里给出两条路：签字写正式区 / 不签字只跑到待确认。 */
    openSign({
      keys:live,
      what:'第 '+stepNo('paintings',3)+' 步：重新导出',
      note:'立绘 / Spine / Live2D 只写 .diag/ 暂存区，不需要签字。'+
           '上面这些 live 阶段在签字后会直接写正式区（audio / cg 没有暂存通道）；'+
           '不签就按左下角「只跑到待确认」，它们只算差异，正式区一个字节不碰。',
      onOk:()=>post({stages:keys,approve:live,force:force},
                    {label:'重新导出（已签字）'}),
      alt:{label:'只跑到待确认（不签字）', run:runUnsigned}
    });
    return;
  }
  if(a==='staged') return post({stages:['paintings','spine','live2d'],force:force},
                              {label:'只重跑导出三件'});
  if(a==='review') return post({stages:['review'],force:force},{label:'出对照表'});
  if(a==='regress') return post({stages:['regress'],force:force},{label:'跑回归'});
  if(a==='swap'){
    const keys=actStages('swap'), live=liveOf(keys);
    openSign({keys:live, what:'第 '+stepNo('swap-in',5)+' 步：换入 '+live.join(' + '),
      note:'换入前整批备份到 Output/_OLD_bak/pipeline_<日期>/；随后重建缩略图与索引，'+
           '要过「索引零回退闸门」和「部署同 inode」两道检查，任一判红就停。',
      onOk:()=>post({stages:keys,approve:live,force:force},{label:'换入正式区'})});
    return;
  }
  /* 兼容旧按钮：整条管线跑到待确认。新界面不再把整条管线挂到某一步的主按钮上。 */
  if(a==='tocheck'){
    const ap=signedLive();
    return post({stages:[],approve:ap,force:force},{label:'跑到待确认'});
  }
}

/* ── 回执：每个动作跑完都留一行结论 ───────────────────────────────────
   旧版点「再查一次」后，若结论没变（preflight 还是红），状态签名一字不差，
   render 一个节点都不碰 ⇒ 界面看起来"什么都没发生"。用户没法区分
   "没跑"和"跑了但结论没变"。回执把这两件事分开：提交时先写一行"已提交"，
   跑完再写结果与用时，且**不随 8 秒轮询消失**。 */
let PENDING=null;
function clip(s,n){
  /* 只留结论，不留"⇒ 跑 cfg.…"那半句：修复动作已经写在卡点里，
     回执再抄一遍会套出「（配置表过期（源…）⇒ 跑…）」这种双层括号。 */
  s=String(s||'').replace(/^\s*红[:：]\s*/,'').split('⇒')[0]
    .replace(/\s+/g,' ').trim();
  const m=n||76; return s.length>m ? s.slice(0,m)+'…' : s;
}
function showReceipt(text,kind){
  const el=$('#receipt'); if(!el) return;
  el.textContent=text||''; el.hidden=!text;
  el.className='receipt'+(kind?' '+kind:'');
}
function labelFor(b){
  if(b.plan) return '只看计划';
  const ks=b.stages||[];
  if(!ks.length) return '整条管线';
  return ks.length<=3 ? ('跑 '+ks.join(' + ')) : ('跑 '+ks.length+' 个阶段');
}
async function post(b, opt){
  opt=opt||{};
  const keys=(b.stages&&b.stages.length)?b.stages.slice()
             :((S&&S.stages)||[]).map(s=>s.key);
  PENDING={label:opt.label||labelFor(b), keys:keys, plan:!!b.plan,
           after:opt.after||null, t0:Date.now()};
  showReceipt(PENDING.label+'：已提交，等结果…','run');
  let j=null;
  try{
    const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(b)});
    j=await r.json();
  }catch(e){
    PENDING=null; showReceipt((opt.label||'任务')+' 没发出去：'+e,'bad'); return;
  }
  if(j.error){
    if(opt.auto && /已经有一个任务在跑/.test(j.error)){
      showReceipt('上一个任务还在收尾，1.5 秒后自动重试…','run');
      setTimeout(()=>post(b,{auto:false,label:opt.label,after:opt.after}),1500);
      return;
    }
    PENDING=null;
    showReceipt((opt.label||'任务')+' 没起来：'+j.error,'bad');
    $('#warn').textContent=j.error; $('#warn').classList.add('on'); return;
  }
  $('#warn').classList.remove('on'); tail(j.id);
}
function finishReceipt(){
  const P=PENDING; if(!P) return; PENDING=null;
  if(P.plan){ showReceipt('只看计划：已生成，展开「细节」看日志里的阶段表','good'); return; }
  const parts=[]; let kind='good', skipped=0;
  P.keys.forEach(k=>{
    const stt=statusOf(k);
    if(stt==='idle'){ skipped++; return; }
    const d=clip(((S.state||{})[k]||{}).detail,72);
    if(stt==='fail') kind='bad';
    else if(stt==='await' && kind!=='bad') kind='await';
    parts.push(k+' '+STT[stt]+(d?' · '+d:''));
  });
  const secs=Math.max(0,Math.round((Date.now()-P.t0)/1000));
  if(!parts.length){
    showReceipt(P.label+'：跑完了，但没读到任何阶段结论 —— 展开「细节」看日志','bad');
    return;
  }
  showReceipt(P.label+' · '+parts.join('；')+
              (skipped?'（另有 '+skipped+' 项没跑到）':'')+' · '+secs+' 秒', kind);
  if(P.after && kind!=='bad'){
    setTimeout(()=>post({stages:P.after},{label:'同步后重查闸门',auto:true}),1200);
  }
}
window.tail=async function(id){
  curJob=id; off=0; LINES=[]; $('#log').textContent=''; $('#jobinfo').textContent='任务 '+id;
  if(timer) clearInterval(timer); timer=setInterval(pump,1100); pump();
};
let LINES=[], FILT='all';
function colorize(t){
  return esc(t).replace(/(✅[^\n]*|判绿[^\n]*)/g,'<span class="good">$1</span>')
               .replace(/(❌[^\n]*|!![^\n]*)/g,'<span class="bad">$1</span>');
}
function logHit(l){
  if(FILT==='all') return true;
  if(FILT==='bad') return /❌|!!|FAIL|Traceback|Error/i.test(l);
  if(FILT==='await') return /未签字|请 --approve|等你签字/.test(l);
  return /✅|❌|^\[[0-9:]+\] ==/.test(l);          // stage：只留阶段结论与阶段分隔行
}
function renderLog(){
  $('#log').innerHTML=LINES.filter(logHit).map(colorize).join('\n') ||
    '<span class="dim">（这个筛选下暂时没有行）</span>';
  if(follow) $('#log').scrollTop=$('#log').scrollHeight;
}
async function pump(){
  if(!curJob) return;
  const j=await (await fetch('/api/log?id='+curJob+'&offset='+off)).json();
  if(j.text){ LINES=LINES.concat(j.text.replace(/\r/g,'').split('\n')); renderLog(); }
  off=j.offset;
  $('#jobstat').innerHTML=j.state==='running'?'<span style="color:var(--run)">● 运行中</span>':'空闲';
  $('#jobinfo').textContent='任务 '+curJob+(j.state?(' · '+j.state):'');
  if(j.state!=='running'){ clearInterval(timer); timer=null; curJob=null;
    await apiState(); finishReceipt(); }
}
$('#bFollow').onclick=e=>{ follow=!follow; e.target.textContent=follow?'跟随最新':'暂停跟随'; };
$('#bClear').onclick=()=>{ LINES=[]; $('#log').textContent=''; };
$('#chips').onclick=e=>{ const b=e.target.closest('.chip'); if(!b) return;
  FILT=b.dataset.f; $$('#chips .chip').forEach(x=>x.classList.toggle('on',x===b));
  chipMark(); renderLog(); };
$('#bForce').onclick=e=>{ force=!force; e.target.textContent=force?'缓存：已绕过':'缓存：按指纹复用';
  e.target.style.borderColor=force?'var(--await)':''; };
$('#bHelp').onclick=()=>$('#help').classList.add('on');
/* 「细节」抽屉：弹簧推入（高阻尼、不过冲 —— 右侧抽屉过冲会在边上闪出一条缝，
   那是 bug 不是物理）。关掉时把焦点还给主屏。 */
function openDetail(){ $('#detail').classList.add('on');
  const b=$('#detail .body');
  if(CALM){ b.style.transform=''; return; }
  SPRG.to('drawer',0,v=>{ b.style.transform='translateX('+(v*100).toFixed(3)+'%)'; },170,26,1); }
function closeDetail(){ const d=$('#detail'), b=d.querySelector('.body');
  if(!d.classList.contains('on')) return;
  if(CALM){ d.classList.remove('on'); b.style.transform='translateX(100%)'; return; }
  SPRG.to('drawer',1.02,v=>{ b.style.transform='translateX('+(v*100).toFixed(3)+'%)'; },200,24);
  /* ⚠️ 摘 `.on` 交给**定时器**，不交给弹簧回调。
     交给弹簧时一旦那一帧没跑完（rAF 被节流、或 apply 里抛异常把整个弹簧循环打死），
     那层 position:fixed;inset:0 的遮罩就永远赖在屏上：抽屉里的卡片被推到视口外
     （hover 判据全量不到）、"背景可见区"退化成 0 像素、帧率被 backdrop-filter 拖垮。
     视觉出口动画照样有，但**状态落定不依赖动画跑完**。 */
  setTimeout(()=>{ d.classList.remove('on'); b.style.transform='translateX(100%)'; },260); }
function toggleDetail(){ $('#detail').classList.contains('on')?closeDetail():openDetail(); }
$('#bDetail').onclick=toggleDetail;
$$('#detail [data-dclose]').forEach(el=>el.onclick=closeDetail);
/* 键位：这类界面要反复切步骤、反复跑同一件事，摸熟键盘比找按钮快。
   输入框里打字时一律不劫持。 */
document.addEventListener('keydown',e=>{
  // e.target 不一定是元素（在 document 上 dispatch 时就是 document，没有 .matches）——
  // 上一版直接 e.target.matches(...) 抛异常，整条键位连同 Esc 一起失效，
  // 抽屉关不掉 ⇒ 那层全屏遮罩把"背景可见区"挤成 0 像素，五条背景判据跟着全塌。
  const t=e.target;
  if(t && t.matches && t.matches('input,textarea,select')) return;
  const k=(e.key||'').toLowerCase();
  if(k==='escape'){
    if($('#signmodal')&&$('#signmodal').classList.contains('on')){ closeSign(); return; }
    $('#help').classList.remove('on'); $('#lightbox').classList.remove('on');
    closeDetail(); return; }
  if(k==='d'){ toggleDetail(); e.preventDefault(); return; }
  if(k>='1'&&k<='9'&&Object.keys((S&&S.steps)||{}).map(Number).includes(Number(k))){
    step=Number(k); render(); e.preventDefault(); return; }
  if(k==='h'){ $('#help').classList.toggle('on'); }
  else if(k==='s'){ $('#bSea').click(); }
  else if(k==='m'){ CALM=!CALM; localStorage.setItem('panel.calm',CALM?'1':'0'); calmApply(); }
  else if(k==='v'){ $('#bSea').click(); }
  else if(k==='p'){ if(!S||S.running) return; post({plan:true}); }
  else if(k==='r'){ if(!S||S.running) return;
    /* R = 跑当前这一步的主动作；看图表那一步主动作是"打开对照表"，
       所以它固定重出表（纯读，重复跑没有副作用）。 */
    const a=step===stepNo('review',4)?'review':((askOf(step).acts||[])[0]||{}).a;
    if(a) ctaRun(a); }
});
$$('#help [data-close]').forEach(el=>el.onclick=()=>$('#help').classList.remove('on'));

// 说明书两档。默认「简洁」= 只留"我要做什么"那四节，其余细节收着（用户：没看懂说明书）。
// 分节靠 h3 的标题文本判定，所以改标题必须同时改这张表，否则那一节会静默变成常驻显示。
const HDETAIL=['颜色与档位怎么读','为什么不信退出码','不在这里的两件事',
               '键位','进度台怎么读','背景与光效','出问题自己先查的三行'];
(function helpGroup(){
  let on=false;
  for(const el of $('#help .panel').children){
    if(el.classList.contains('hmode')) continue;
    if(el.tagName==='H3') on=HDETAIL.some(k=>el.textContent.trim().startsWith(k));
    if(on) el.classList.add('dt');
  }
})();
let HM=localStorage.getItem('panel.helpmode')||'simple';
function hmApply(){
  document.body.classList.toggle('hsimple',HM!=='detail');
  $$('#help .hmode .seg').forEach(b=>b.classList.toggle('on',b.dataset.hm===HM));
  const n=$$('#help .dt').filter(e=>e.tagName==='H3').length;
  $('#hnote').textContent=HM==='detail'?'全部 '+$$('#help .panel h3').length+' 节'
                                       :'已收起 '+n+' 节细节';
}
$$('#help .hmode .seg').forEach(b=>b.onclick=()=>{
  HM=b.dataset.hm; localStorage.setItem('panel.helpmode',HM); hmApply(); });
hmApply();

document.addEventListener('click',e=>{ if(e.target.matches('.sheets img')){
  $('#lightbox img').src=e.target.src; $('#lightbox').classList.add('on'); e.preventDefault(); } });
$('#lightbox').onclick=e=>e.currentTarget.classList.remove('on');
nightApply(); seaApply(); calmApply(); apiState();
addEventListener('resize',()=>{ stepFill(); chipMark(); avoidRefresh(); });
chipMark();
let pollT=setInterval(()=>{ if(!timer) apiState(); },8000);
/* 验收钩子。`stop()` 是上一版留下的绕道：那时轮询会重播卡片入场动画，
   比对期间必须停掉轮询才拿得到可比的帧（实测假红 75）。
   现在入场动画只在首次挂载播、且 payload 没变根本不 render()，
   ⇒ 这个钩子**不再决定结论**：探针会带着轮询开着跑一遍静止比对，只有那一遍也绿才算修好了。 */
window.__probe={stop(){ if(pollT){ clearInterval(pollT); pollT=null; } },
                poll(on){ if(on&&!pollT) pollT=setInterval(()=>{ if(!timer) apiState(); },8000);
                          if(!on&&pollT){ clearInterval(pollT); pollT=null; } },
                pin(){ window.__pin=[...document.querySelectorAll('.snode,.stage')]; return 1; },
                pinned(){ const now=[...document.querySelectorAll('.snode,.stage')];
                          const p=window.__pin||[];
                          return p.length>0 && p.length===now.length && p.every(e=>now.includes(e)); },
                anims(){ return document.getAnimations().length; },
                api(){ return apiState(); },     // 真入口：进度台判据从这里灌合成 state，不直接调 gaugeSet
                go(n){ step=n; render(); }, state(){ return S; },
                view(){ return step; },
                calm(on){ CALM=!!on; localStorage.setItem('panel.calm',CALM?'1':'0');
                          calmApply(); return CALM; },
                legacy(on){ LEGACY=!!on; localStorage.setItem('panel.legacy',LEGACY?'1':'0');
                            legacyApply(); fxOff(); FX.last=null; return LEGACY; },
                fx(){ return {calm:CALM, beam:!!(FX.beam&&FX.beam.classList.contains('go')),
                              beamAnim:!!(FX.beam&&FX.beam.getAnimations().length),
                              pool:!!(FX.pool&&FX.pool.classList.contains('on')),
                              poolShown:!!(FX.pool&&getComputedStyle(FX.pool).display!=='none'),
                              cur:FX.cur?String(FX.cur.el.className):null}; },
                hover(sel){ const el=$(sel); if(!el) return null;
                  const r=el.getBoundingClientRect();
                  return {x:r.left+r.width*0.3,y:r.top+r.height*0.5}; },
                marks(){ const a=$('#stepfill'), b=$('#chipmark');
                  return {fill:a?a.style.width:null,
                          chip:b?b.style.opacity+'|'+b.style.left+'|'+b.style.width:null}; },
                springs(){ return SPRG.raf?SPRG.m.size:0; },
                live(){ return SPRG.live(); },
                det(on){ on?openDetail():closeDetail(); return 1; },
                ask(){ return {eb:$('#eyebrowTx').textContent, ask:$('#ask').textContent.trim(),
                                why:$('#why').textContent.trim(),
                                gate:$('#gate').hidden?'':$('#gate').textContent.trim(),
                                receipt:$('#receipt').hidden?'':$('#receipt').textContent.trim(),
                                acts:[...document.querySelectorAll('#cta button')]
                                      .map(x=>x.dataset.a+'|'+(x.dataset.to||'')+'|'+x.textContent),
                                gateActs:[...document.querySelectorAll('#gate button')]
                                      .map(x=>x.dataset.a+'|'+(x.dataset.to||'')+'|'+x.textContent)}; },
                scope(a){ return actStages(a); },
                live(a){ return liveOf(actStages(a)); },
                work(){ return currentStep(); },
                detail(){ const d=$('#detail');
                  return {on:d.classList.contains('on'),
                          vis:getComputedStyle(d).display!=='none',
                          cards:d.querySelectorAll('.stage').length}; },
                avoid(){ return (ST.avoid||[]).length; }};
window.ST=ST; window.SPR=SPR; window.SPRG=SPRG; window.panelState=()=>S;
</script></body></html>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=PORT)
    ap.add_argument('--no-open', action='store_true')
    a = ap.parse_args()

    class Server(ThreadingHTTPServer):
        allow_reuse_address = True            # 规避 TIME_WAIT 导致的绑定失败
        daemon_threads = True

        def handle_error(self, request, client_address):
            # 浏览器提前断开是常态（轮询/切页），默认实现会往 stderr 刷 traceback，
            # 而这正是把本地 dev server 楔成"半死"的那条路（见 docs/TROUBLESHOOTING.md §63）
            exc = sys.exc_info()[1]
            if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                                BrokenPipeError, TimeoutError)):
                return
            super().handle_error(request, client_address)

    # ⚠️ Windows 上 allow_reuse_address(=SO_REUSEADDR) 的语义和 POSIX 不同：
    #    它**允许两个进程绑同一个端口**，请求被随机分给其中一个 —— 于是会出现
    #    "两个控制台共用一个端口、各自看到的任务状态不一样"这种极难查的错。
    #    （本轮实测真的起了两个，靠数进程才发现。）所以绑之前先探一次端口。
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.6)
        if probe.connect_ex(('127.0.0.1', a.port)) == 0:
            print(f'端口 {a.port} 上已经有一个控制台在跑了 —— 直接用它，别再起第二个。')
            print(f'  （若那个其实已经死了，换个端口：py -3 scripts/pipeline_panel.py --port 8790）')
            if not a.no_open:
                webbrowser.open(f'http://127.0.0.1:{a.port}/')
            return 0

    try:
        stage_keys()          # 起服务前先确认阶段清单读得出来，别到点按钮才炸
    except Exception as e:
        print(f'[错误] 读不到 update_pipeline 的阶段清单：{e}')
        return 1

    url = f'http://127.0.0.1:{a.port}/'
    print('=' * 60)
    print('  资产更新控制台')
    print('  地址:', url)
    print('  只绑 127.0.0.1；能跑的阶段由 update_pipeline 的白名单决定')
    print('  关闭本窗口即停止控制台（正在跑的流水线任务不会因此中断）')
    print('=' * 60)
    if not a.no_open:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    httpd = Server(('127.0.0.1', a.port), H)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止。')
    finally:
        httpd.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
