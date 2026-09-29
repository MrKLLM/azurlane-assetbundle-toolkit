# -*- coding: utf-8 -*-
"""资产更新控制台 —— 本地网页仪表盘，双击「启动资产更新控制台.bat」打开。

它**不重新实现**任何流水线逻辑：每个按钮都是去起 `scripts/update_pipeline.py` 子进程，
然后把它写的日志实时读回来显示。这样"界面上看到的"和"命令行跑的"永远是同一套代码，
不存在两份逻辑各自漂移的问题（本项目栽过这类坑）。

界面按「四步主线」组织（接模拟器 / 重新导出 / 看图对比 / 签字换入），
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
import json
import os
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
             'step': s.step, 'writes': s.writes} for s in up.STAGES], dict(up.STEPS)


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
                    state = dict(raw.get('done', {}))
                    state.update(raw.get('verdict', {}))
            except Exception:
                pass
            sheets = []
            for p in sorted(glob_sheets()):
                sheets.append({'name': os.path.basename(p),
                               'kb': round(os.path.getsize(p) / 1024),
                               'mt': time.strftime('%m-%d %H:%M', time.localtime(
                                   os.path.getmtime(p)))})
            return self._send(200, {
                'stages': stages, 'steps': steps, 'state': state,
                'runs': load_runs()[-12:][::-1],
                'running': running_job(), 'error': err, 'sheets': sheets,
                'fingerprint': fingerprint_safe(),
                'scope': scope_safe(),
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


def glob_sheets():
    import glob
    return glob.glob(os.path.join(WORK, '*.png')) + glob.glob(os.path.join(WORK, '*.jpg'))


# 输入指纹要 os.walk 整个 files/AssetBundles（91,643 个文件，实测数秒）。
# 前端每 8s 轮询一次 /api/state，不缓存的话每次轮询都白扫一遍盘，首屏还会空着十几秒像死掉。
_CACHE = {'fp': [None, 0.0], 'scope': [None, 0.0]}


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


def scope_safe():
    def calc():
        sys.path.insert(0, HERE)
        try:
            import update_pipeline as up
            t = up.affected_stems(False)
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
   一条铁律贯穿到底：**一个颜色只表示一件事**。颜色只属于「状态」
   （未跑/判绿/判红/等你签字/在跑），阶段档位一律用文字+图标（只读/暂存/写正式）。
   上一版把 read=蓝 / staged=绿 / live=红 拿来标档位，于是"红色"同时意味着
   「写正式产物」和「出错了」，用户看到一片红就不敢点——那是看不懂的主因之一。 */
:root{
  --abyss:#04101c; --deep:#072033;
  --line:rgba(126,196,224,.16); --line2:rgba(126,196,224,.34);
  --txt:#dbeaf4; --dim:#7f9db1; --dim2:#5a7688;
  --idle:#3f5a6e; --pass:#4fd6a8; --fail:#ff6f6f; --await:#f2bd72; --run:#5fd0e8;
  --brand:#5fd0e8; --pop:#8fb8ff;
  /* 水面参数：只有背景那层读，组件一个都不碰（与画廊同源） */
  --w-foam:#ffffff; --w-glint:#dff0ff; --w-deep:#2f7fb8;
  --w-gain:9; --w-foamth:0.012; --w-alpha:0.82;
  --fd:'Bahnschrift','DIN Alternate','Microsoft YaHei UI',system-ui,sans-serif;
  --fb:'Microsoft YaHei UI','Microsoft YaHei',system-ui,sans-serif;
  --fm:'Cascadia Mono','Consolas',ui-monospace,monospace;
  --ez:cubic-bezier(.22,.61,.36,1);
  /* 内容面一律**不透明**：上一版 .pane 用 alpha .90，星点会渗进卡片文字区（实测最大 36）。
     主题的星辰大海只留在**没有正文**的地方：页面底、栏间空隙、以及那块 hero 带。 */
  --pane:#0b2135; --card:#0d2739;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;font:14px/1.65 var(--fb);color:var(--txt);overflow:hidden;
  background:linear-gradient(180deg,var(--abyss) 0%,#061a2b 44%,var(--deep) 100%)}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-thumb{background:rgba(126,196,224,.20);border-radius:6px}
::-webkit-scrollbar-thumb:hover{background:rgba(126,196,224,.34)}
::-webkit-scrollbar-track{background:transparent}

/* ══ 背景层：静止的星野 + 「一划才起浪」的水面 ════════════════════════════
   移植自 gallery_src/index.html 第四版，连同它换来的三条硬约束一起搬：
     · 静止时**逐像素完全相同**——前几版（气泡+正弦线 / 会漂的粒子星野 / 噪声着色器）
       被否不是因为不好看，而是背景自己在动，等于一张装饰壁纸。
     · pointer-events:none；z-index 低于内容；内容面板基本不透明 ⇒ 背景永不过遮挡。
     · 阻尼按**秒**算（0.11^dt），不是按帧——挂上模糊后无头只有十几帧，
       按帧写会导致"水永远不平"。
   星辰是一次性绘制的固定星野（同种子 ⇒ 刷新位置不变），不闪不漂。 */
#bgfx{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
#bgfx .bfield{position:absolute;inset:-10%}
#bgfx .glow{position:absolute;width:74vmax;height:74vmax;border-radius:50%;opacity:.66}
#bgfx .g1{left:-24vmax;top:-28vmax;
  background:radial-gradient(closest-side,color-mix(in srgb,var(--brand) 74%,transparent) 0%,
    color-mix(in srgb,var(--brand) 30%,transparent) 40%,transparent 100%)}
#bgfx .g2{right:-26vmax;bottom:-32vmax;width:68vmax;height:68vmax;
  background:radial-gradient(closest-side,color-mix(in srgb,var(--pop) 60%,transparent) 0%,
    color-mix(in srgb,var(--pop) 22%,transparent) 40%,transparent 100%)}
#bgfx .g3{right:2vmax;top:-26vmax;width:54vmax;height:54vmax;
  background:radial-gradient(closest-side,color-mix(in srgb,var(--pass) 48%,transparent) 0%,
    color-mix(in srgb,var(--pass) 18%,transparent) 40%,transparent 100%)}
#bgfx canvas{position:absolute;inset:0;width:100%;height:100%}
body.plain #bgfx .glow{display:none}

/* ══ 骨架：三个独立滚动的区，页面本身不滚 ═══════════════════════════════ */
.app{position:relative;z-index:1;display:flex;flex-direction:column;height:100vh}
header{position:relative;z-index:10;flex:0 0 auto;display:flex;align-items:center;gap:20px;
  padding:13px 22px;background:#08202f;
  border-bottom:1px solid rgba(150,215,240,.30);
  box-shadow:inset 0 1px 0 rgba(190,232,255,.28),0 1px 0 rgba(4,14,24,.6),0 16px 34px -26px #000}
header::after{content:'';position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(104deg,rgba(190,235,255,.10) 0 14%,transparent 14%)}
.brand{display:flex;align-items:center;gap:11px;flex:0 0 auto}
.brand svg{display:block}
.brand h1{margin:0;font:600 19px/1.15 var(--fd);letter-spacing:.06em}
.brand p{margin:2px 0 0;font-size:11.5px;color:var(--dim2);letter-spacing:.04em}
.meters{display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex:1 1 auto;min-width:0}
.meter{font:11px/1 var(--fm);padding:5px 9px;border-radius:8px;background:#0a2338;
  border:1px solid var(--line);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.meter b{color:var(--dim);font-weight:400;margin-right:6px}
.meter.ok b,.meter.ok span{color:var(--pass)}
.act{display:flex;gap:8px;flex:0 0 auto}

button{font:inherit;font-size:13px;padding:7px 14px;border-radius:9px;border:1px solid var(--line);
  background:var(--card);color:var(--txt);cursor:pointer;
  transition:background .16s var(--ez),border-color .16s var(--ez),transform .12s var(--ez),opacity .16s}
button:hover{border-color:var(--line2);background:rgba(20,52,78,.92)}
button:active{transform:translateY(1px)}
button:disabled{opacity:.38;cursor:not-allowed;transform:none}
button:disabled:hover{border-color:var(--line);background:var(--card)}
button:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
button.go{background:linear-gradient(180deg,#1a7fa6,#12617f);border-color:#2b9dc4;color:#eafcff;
  font-weight:600;box-shadow:0 12px 24px -14px rgba(31,160,196,.8)}
button.go:hover{background:linear-gradient(180deg,#2494bd,#16708f)}
button.sign{border-color:rgba(242,189,114,.55);color:#ffd9a2;background:rgba(58,42,20,.42)}
button.sign:hover{background:rgba(74,54,26,.62);border-color:var(--await)}
button.ghost{background:transparent;font-size:12.5px;padding:6px 11px}
button.mini{font-size:11.5px;padding:3px 9px;border-radius:7px}

/* ══ 大气区（hero / seaband）与数据区的分工 ═════════════════════════════
   规矩只有一条：**能读数据、能看图的位置一律不透明**，主题只出现在没有数据的带里。
   hero 放当前步的标题与一句说明；seaband 是底部那条海平面，划过就起浪、停下必平。
   两处都只许放标题级短文（带 text-shadow 压住任何星点亮度），
   阶段卡、日志、对照图、指标 pill 一个都不许放进去。 */
.seaband{flex:0 0 auto;height:136px;display:flex;flex-direction:column;align-items:center;
  justify-content:flex-start;gap:5px;text-align:center;position:relative;z-index:1;
  padding-top:16px;border-top:1px solid rgba(150,215,240,.10)}
.seaband .hl{font:600 11px/1 var(--fd);letter-spacing:.26em;text-transform:uppercase;
  color:rgba(191,224,242,.72);text-shadow:0 1px 10px rgba(3,12,20,.95)}
.seaband p{margin:0;font-size:11.5px;line-height:1.7;color:rgba(159,196,217,.7);
  max-width:76ch;text-shadow:0 1px 8px rgba(3,12,20,.95)}
.wrap{flex:1 1 auto;min-height:0;display:grid;gap:16px;padding:14px 26px 6px;
  grid-template-columns:262px minmax(520px,1fr) minmax(360px,.66fr);max-width:1760px;
  margin:0 auto;width:100%;align-items:stretch}
.col{min-height:0;overflow:auto;display:flex;flex-direction:column;gap:12px;padding-right:2px}
.pane{background:var(--pane);border:1px solid var(--line);border-radius:14px;padding:13px 15px;
  box-shadow:0 22px 46px -32px rgba(0,0,0,.92),inset 0 1px 0 rgba(180,225,255,.07)}
.ph{font:600 11px/1 var(--fd);letter-spacing:.18em;text-transform:uppercase;color:var(--dim);
  margin:0 0 11px;display:flex;align-items:center;justify-content:space-between;gap:8px}

/* ══ 步骤导航 ═════════════════════════════════════════════════════════ */
.step{position:relative;display:grid;grid-template-columns:26px 1fr auto;gap:10px;align-items:start;
  width:100%;text-align:left;padding:9px 10px;border-radius:12px;background:transparent;
  border:1px solid transparent;animation:rise .46s var(--ez) backwards}
.step:hover{background:#102c44;border-color:var(--line)}
.step.on{background:linear-gradient(180deg,#17395a,#0e2740);
  border-color:rgba(95,208,232,.42);box-shadow:0 14px 30px -20px rgba(0,0,0,.9)}
.step .num{font:600 15px/1.4 var(--fd);color:var(--dim);text-align:center;
  border:1px solid var(--line);border-radius:9px;background:rgba(6,22,36,.6)}
.step.on .num{color:var(--brand);border-color:rgba(95,208,232,.5)}
.step b{display:block;font-size:13.5px;font-weight:600;letter-spacing:.02em}
.step em{display:block;font:400 11px/1.45 var(--fb);color:var(--dim);font-style:normal;
  margin-top:1px}
.step .cnt{font:11px/1 var(--fm);color:var(--dim2);margin-top:5px;display:block}
.dots{display:flex;gap:3px;align-items:center;margin-top:6px}
.dot{width:7px;height:7px;border-radius:2px;background:var(--idle)}
.dot.pass{background:var(--pass)}.dot.fail{background:var(--fail)}
.dot.await{background:var(--await)}.dot.run{background:var(--run);animation:pulse 1.1s infinite}
.legend{display:flex;flex-direction:column;gap:5px;font-size:11px;color:var(--dim)}
.legend .lrow{display:flex;gap:14px}
.legend .lrow span{display:flex;align-items:center;gap:6px}
.legend .lnote{margin:7px 0 0;font-size:11px;line-height:1.65;color:var(--dim2)}
.legend .sw{width:9px;height:9px;border-radius:3px;flex:0 0 auto}
@keyframes rise{from{opacity:0;transform:translateY(7px)}}
@keyframes pulse{50%{opacity:.25}}

/* ══ 工作区 ═══════════════════════════════════════════════════════════ */
/* 主题带：整个界面里唯一让正文"坐在海面上"的地方，只有一句标题 + 一句说明 + 按钮。
   卡片、日志、对照图全是不透明面 ⇒ 需要读字和看图的位置，背景一点都渗不进来。
   这一层自带极淡的暗色纱，保证标题在任何星点亮度下都压得住。 */
.hero{padding:15px 17px 14px;border-radius:16px;border:1px solid rgba(126,196,224,.11);
  background:linear-gradient(180deg,rgba(6,22,36,.34),rgba(4,16,28,.16))}
.whead{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}
.whead h2{margin:0;font:600 17px/1.3 var(--fd);letter-spacing:.04em;
  text-shadow:0 1px 12px rgba(3,12,20,.9),0 0 2px rgba(3,12,20,.75)}
.whead p{margin:4px 0 0;color:#a9c6d8;font-size:12.5px;max-width:64ch;
  text-shadow:0 1px 8px rgba(3,12,20,.9)}
.cta{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 2px}
.scopenote{font-size:11.5px;color:var(--await);margin:6px 0 0;display:none}
.scopenote.on{display:block}

.g{display:flex;flex-direction:column;gap:9px}
.stage{position:relative;border:1px solid var(--line);border-radius:12px;padding:11px 13px;
  background:var(--card);animation:rise .4s var(--ez) backwards;
  transition:border-color .16s var(--ez),transform .16s var(--ez)}
.stage:hover{border-color:var(--line2);transform:translateY(-1px)}
.stage.fail{border-left:3px solid var(--fail)}
.stage.await{border-left:3px solid var(--await)}
.srow{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.skey{font:600 13.5px/1 var(--fm);letter-spacing:.02em}
/* 档位三枚一律中性色：只靠图标 + 字重 + 边框样式分级。
   上一版把「写正式」标成琥珀，而琥珀正好又是"等你签字"的颜色 —— 同一个 hue 负两件语义，
   用户就分不清"这行到底是我该动手，还是它出事了"。颜色这条资源整体留给状态。 */
.tier{font:10.5px/1 var(--fb);padding:3px 7px;border-radius:6px;border:1px solid var(--line);
  color:var(--dim);white-space:nowrap;background:rgba(126,196,224,.05)}
.tier.s{border-style:dashed;border-color:rgba(126,196,224,.30);color:#a8c2d4}
.tier.l{border-color:rgba(126,196,224,.46);color:#c6dceb;font-weight:600}
.stt{margin-left:auto;font:11.5px/1 var(--fb);padding:4px 9px;border-radius:999px;
  display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.stt::before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}
.stt.idle{background:rgba(63,90,110,.30);color:#9db4c4}
.stt.pass{background:rgba(79,214,168,.14);color:var(--pass)}
.stt.fail{background:rgba(255,111,111,.16);color:var(--fail)}
.stt.await{background:rgba(242,189,114,.15);color:var(--await)}
.stt.run{background:rgba(95,208,232,.16);color:var(--run);animation:pulse 1.1s infinite}
.stitle{font-size:13px;color:var(--txt);margin:7px 0 0}
.kv{display:grid;grid-template-columns:44px 1fr;gap:4px 9px;margin:8px 0 0;font-size:11.8px;
  color:var(--dim)}
.kv dt{color:var(--dim2);letter-spacing:.06em}
.kv dd{margin:0;font-family:var(--fm);font-size:11.5px;word-break:break-all;line-height:1.55}
.sact{display:flex;gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap}
.signbox{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:#f7d9a2;
  padding:3px 9px 3px 7px;border-radius:8px;border:1px solid rgba(242,189,114,.32);
  background:rgba(58,42,20,.30)}
.signbox input{accent-color:var(--await);width:14px;height:14px;margin:0;cursor:pointer}
.spacer{margin-left:auto}
.dim{color:var(--dim2)}

/* ══ 对照图：必须坐在完全不透明的底上 ═════════════════════════════════ */
.sheets{display:grid;grid-template-columns:repeat(auto-fill,minmax(238px,1fr));gap:10px}
.sheets a{display:block;border:1px solid var(--line);border-radius:10px;overflow:hidden;
  background:#081c2c;text-decoration:none;color:inherit;
  transition:border-color .16s var(--ez),transform .16s var(--ez)}
.sheets a:hover{border-color:var(--line2);transform:translateY(-2px)}
.sheets img{display:block;width:100%;height:196px;object-fit:contain;background:#0b2436;
  cursor:zoom-in}
.sheets .cap{font-size:11px;color:var(--dim);padding:6px 9px;display:flex;
  justify-content:space-between;gap:8px;border-top:1px solid var(--line)}

/* ══ 日志 / 任务 ══════════════════════════════════════════════════════ */
pre{margin:0;font:11.8px/1.6 var(--fm);white-space:pre-wrap;word-break:break-all;
  background:rgba(3,12,20,.78);border:1px solid var(--line);border-radius:10px;padding:10px 12px;
  overflow:auto;color:#bcd6e6;flex:1 1 auto;min-height:180px}
pre .good{color:var(--pass)}pre .bad{color:var(--fail)}
.runs{width:100%;border-collapse:collapse;font-size:12px}
.runs th{font:600 10.5px/1 var(--fd);letter-spacing:.12em;text-transform:uppercase;
  color:var(--dim2);text-align:left;padding:0 6px 7px;border-bottom:1px solid var(--line)}
.runs td{padding:7px 6px;border-bottom:1px solid rgba(126,196,224,.08);vertical-align:top}
.runs tr:last-child td{border-bottom:none}
.tag{font:10.5px/1 var(--fb);padding:3px 7px;border-radius:6px;white-space:nowrap}
.tag.done{background:rgba(79,214,168,.13);color:var(--pass)}
.tag.running{background:rgba(95,208,232,.14);color:var(--run);animation:pulse 1.1s infinite}
.tag.gone,.tag.donedirty{background:rgba(255,111,111,.14);color:var(--fail)}

/* ══ 使用说明抽屉 ══════════════════════════════════════════════════════ */
#help{position:fixed;inset:0;z-index:60;display:none}
#help.on{display:block}
#help .veil{position:absolute;inset:0;background:rgba(2,9,15,.72);backdrop-filter:blur(3px)}
#help .panel{position:absolute;right:0;top:0;bottom:0;width:min(660px,94vw);overflow:auto;
  background:linear-gradient(180deg,#0a2236,#071a2b);border-left:1px solid var(--line2);
  box-shadow:-30px 0 70px -30px #000;padding:22px 26px 40px;animation:slide .32s var(--ez)}
@keyframes slide{from{transform:translateX(28px);opacity:.6}}
#help h3{font:600 15px/1.3 var(--fd);margin:22px 0 8px;letter-spacing:.04em;color:var(--brand)}
#help h3:first-of-type{margin-top:4px}
#help p,#help li{font-size:13px;color:#c9dfec}
#help ul{margin:6px 0;padding-left:20px}
#help li{margin:4px 0}
#help table{width:100%;border-collapse:collapse;font-size:12.5px;margin:8px 0;
  table-layout:fixed}
#help table td:first-child,#help table th:first-child{width:7.4em;white-space:nowrap}
#help table td:nth-child(2){width:42%}
#help th,#help td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;
  vertical-align:top}
#help th{font:600 10.5px/1 var(--fd);letter-spacing:.1em;text-transform:uppercase;color:var(--dim2)}
#help code{font:11.8px/1.5 var(--fm);background:rgba(95,208,232,.10);padding:1px 6px;
  border-radius:5px;color:#a8e6f5}
#help .close{position:sticky;top:0;float:right}
.warn{background:rgba(255,111,111,.10);border:1px solid rgba(255,111,111,.34);border-radius:10px;
  padding:9px 12px;font-size:12.5px;color:#ffc2c2;margin-bottom:11px;display:none}
.warn.on{display:block}
#lightbox{position:fixed;inset:0;background:rgba(2,7,12,.95);display:none;z-index:99;
  align-items:center;justify-content:center;cursor:zoom-out}
#lightbox.on{display:flex}
#lightbox img{max-width:96vw;max-height:96vh;object-fit:contain}
@media (max-width:1240px){.wrap{grid-template-columns:230px minmax(400px,1fr)}
  .col.side{grid-column:1/-1}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head><body>

<div id="bgfx" aria-hidden="true"><div class="bfield">
  <i class="glow g1"></i><i class="glow g2"></i><i class="glow g3"></i></div>
  <canvas id="stars"></canvas></div>

<div class="app">
<header>
  <div class="brand">
    <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <circle cx="18.4" cy="6.2" r="1.5" fill="#5fd0e8"/>
      <path d="M18.4 2.4v7.6M14.6 6.2h7.6" stroke="#5fd0e8" stroke-width=".9"
            stroke-linecap="round" opacity=".55"/>
      <circle cx="6.2" cy="9.4" r=".9" fill="#dff0ff" opacity=".8"/>
      <circle cx="10.5" cy="4.4" r=".7" fill="#dff0ff" opacity=".55"/>
      <path d="M1 18.6c2.2 0 2.2-2.2 4.4-2.2s2.2 2.2 4.4 2.2 2.2-2.2 4.4-2.2 2.2 2.2 4.4 2.2
               2.2-2.2 4.4-2.2" stroke="#5fd0e8" stroke-width="1.4" stroke-linecap="round"
            fill="none" opacity=".95"/>
      <path d="M1 22.8c2.2 0 2.2-2.2 4.4-2.2s2.2 2.2 4.4 2.2 2.2-2.2 4.4-2.2 2.2 2.2 4.4 2.2
               2.2-2.2 4.4-2.2" stroke="#8fb8ff" stroke-width="1.2" stroke-linecap="round"
            fill="none" opacity=".5"/>
    </svg>
    <div><h1>资产更新控制台</h1><p>拉包 · 重导 · 看图 · 换入</p></div>
  </div>
  <div class="meters">
    <span class="meter"><b>输入指纹</b><span id="fp">首屏在算（要扫 9 万个源包）</span></span>
    <span class="meter"><b>本次范围</b><span id="scope">…</span></span>
    <span class="meter"><b>阶段</b><span id="prog">…</span></span>
    <span class="meter" id="mjob"><b>任务</b><span id="jobstat">空闲</span></span>
  </div>
  <div class="act">
    <button id="bSea" class="ghost" title="关掉就把星野与水面整个停用（背景不该挡正事）">星辰大海 · 开</button>
    <button id="bPlan" class="ghost">只看计划</button>
    <button id="bHelp" class="go">怎么用</button>
  </div>
</header>

<div class="wrap">
  <!-- 左：四步主线 -->
  <div class="col">
    <div class="pane">
      <div class="ph">主线</div>
      <div id="rail"></div>
    </div>
    <div class="pane">
      <div class="ph">状态是什么意思</div>
      <div class="legend">
        <div class="lrow">
          <span><i class="sw" style="background:var(--idle)"></i>未跑</span>
          <span><i class="sw" style="background:var(--pass)"></i>判绿</span>
          <span><i class="sw" style="background:var(--run)"></i>在跑</span>
        </div>
        <div class="lrow">
          <span><i class="sw" style="background:var(--await)"></i>等你签字</span>
          <span><i class="sw" style="background:var(--fail)"></i>判红</span>
        </div>
        <p class="lnote">判绿 = 按它自己写的判据过了；判红 = 停在这里不往下跑。<br>
          档位是文字不是颜色：<span class="tier">ⓘ 只读</span>
          <span class="tier s">▣ 暂存</span> <span class="tier l">⚑ 写正式</span>。
          <u>红色永远只等于「判红」</u>。</p>
      </div>
    </div>
  </div>

  <!-- 中：当前步的阶段卡 -->
  <div class="col">
    <div id="warn" class="warn"></div>
    <div class="hero">
      <div class="whead"><div><h2 id="sTitle">—</h2><p id="sDesc">—</p></div>
        <div id="sAct"></div></div>
      <div class="cta" id="cta"></div>
      <p class="scopenote" id="scopeNote"></p>
    </div>
    <div class="pane">
      <div class="ph">这一轮的阶段 <span id="sCount" class="dim" style="font-size:11px"></span></div>
      <div class="g" id="cards"></div>
    </div>
    <div class="pane">
      <div class="ph">待确认：改前 | 改后 对照表</div>
      <div id="sheets" class="sheets"></div>
      <p class="dim" style="font-size:11.5px;margin:9px 0 0">
        「看图对比」跑完后出现在这里；点开可放大。图放在不透明的底上，背景不会渗进来影响你看边缘。</p>
    </div>
  </div>

  <!-- 右：日志 + 任务 -->
  <div class="col side">
    <div class="pane" style="flex:1 1 auto;display:flex;flex-direction:column;min-height:0">
      <div class="ph">运行日志
        <span style="display:flex;gap:6px;align-items:center">
          <button id="bFollow" class="mini ghost">跟随最新</button>
          <button id="bClear" class="mini ghost">清空显示</button></span></div>
      <pre id="log">（还没有任务。左边选一步，再点中间那个蓝色主按钮。
看不懂某个词，就点右上角「怎么用」。）</pre>
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

<div class="seaband">
  <span class="hl">海平面</span>
  <p>划过任意位置，这条海面都会起浪，约两秒后自己散平；没人划时它一帧都不动。
     阶段卡、日志、对照图全在不透明面板里，背景渗不进去。</p>
</div>
</div>

<div id="help"><div class="veil" data-close></div><div class="panel">
  <button class="close ghost" data-close>关闭 ✕</button>
  <h3 style="margin-top:0">这是什么</h3>
  <p><b>资产更新控制台</b>把你游戏更新之后要做的那一串事，按四步排成一条主线。
  它<b>不重新实现</b>任何导出逻辑：每个按钮都是去起
  <code>scripts/update_pipeline.py</code> 这个命令行编排器，编排器再去起你仓库里原有的那些脚本
  （<code>mumu_sync</code> / <code>compose_paintings_v2</code> / <code>extract_spine_v2</code> /
  <code>reconstruct_live2d</code> / <code>build_gallery_index</code> …，全部原样调用）。
  所以「界面上看到的」和「命令行跑的」永远是同一套代码，不存在两份逻辑各自漂移。</p>

  <h3>动手之前</h3>
  <ul>
    <li>MuMu 已启动，且游戏已更新到你要导的那个版本；停在能进游戏主界面的状态。</li>
    <li>权威输入在位：<code>inputs/azdata/</code>、<code>inputs/gamecfg/</code>、画廊 vendor。
      第 1 步的 <code>preflight</code> 就是查这三样，红了别往下走。</li>
    <li>一次只跑一个重活（本机 15.4GB）。已有任务在跑时按钮会锁住，不是坏了。</li>
    <li>画廊服务器要先活着或让它自己起；回归那件会去连它。</li>
  </ul>

  <h3>四步分别动什么</h3>
  <table><thead><tr><th>步骤</th><th>会动</th><th>不会动</th></tr></thead><tbody>
    <tr><td>① 接模拟器</td><td>只读地列模拟器里的包，算出新增/变更清单</td>
        <td>不下载任何东西（下载是 <code>pull</code> 的签字项，要它才写 <code>files/</code>）</td></tr>
    <tr><td>② 重新导出</td><td>重算依赖表、元数据、立绘、Spine、Live2D、语音、CG</td>
        <td>立绘/Spine/Live2D 只写 <code>.diag/pipeline/</code> 暂存区，正式区一个字节都不碰</td></tr>
    <tr><td>③ 看图对比</td><td>产出「改前 | 改后」对照表和两张清单</td>
        <td>纯读，随时可反复跑</td></tr>
    <tr><td>④ 签字换入</td><td>把暂存区覆盖进 <code>Output/Paintings_v2</code>，
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

  <h3>背景那层是什么</h3>
  <p>静止的星野 + 一划才起浪的水面，跟画廊同源。它<b>静止时一帧都不动</b>，只有你划过才会起浪，
  然后自己散回平面——这是被验证过不挡正事的做法。觉得干扰就点顶栏「星辰大海 · 关」，
  整个背景层直接停用并记住你的选择。</p>

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
let SEA = localStorage.getItem('panel.sea')!=='0';

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

/* ── 背景：固定星野（画一次，不闪不漂）+ 静止水面 ─────────────────── */
function mul32(a){return()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);
  t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
function drawStars(){
  const cv=$('#stars'); if(!cv) return;
  const k=Math.min(2,window.devicePixelRatio||1), w=innerWidth, h=innerHeight;
  cv.width=Math.max(2,w*k|0); cv.height=Math.max(2,h*k|0);
  const g=cv.getContext('2d'); if(!g) return;
  g.setTransform(k,0,0,k,0,0); g.clearRect(0,0,w,h);
  const R=mul32(20260929);                       // 同种子 ⇒ 刷新后星位不变，不会"每次进来换一片天"
  const gx=w*0.12, gy=h*1.02, dx=w*0.9, dy=-h*0.72;   // 一条斜着的银河带
  for(let i=0;i<420;i++){
    let x,y;
    if(i<300){ const t=R(), s=(R()-0.5)*w*0.30;
      x=gx+dx*t+(-dy)*0.0+s*1.02; y=gy+dy*t+w*0.06*s/ (w*0.30||1)*0+ (R()-0.5)*w*0.16; }
    else { x=R()*w; y=R()*h; }
    const a=0.17+R()*0.66, r=0.4+R()*1.1;
    g.globalAlpha=a; g.fillStyle = i%7===0 ? '#cfe6ff' : '#eaf7ff';
    g.beginPath(); g.arc(x,y,r,0,6.2832); g.fill();
  }
  for(let i=0;i<24;i++){                          // 二十来颗亮一点的，带十字光晕，仍完全静止
    const x=R()*w, y=R()*h*0.86, r=1.2+R()*1.5;
    g.globalAlpha=0.62+R()*0.33; g.fillStyle='#e8f5ff';
    g.beginPath(); g.arc(x,y,r,0,6.2832); g.fill();
    g.globalAlpha=0.16; g.strokeStyle='#bfe4ff'; g.lineWidth=0.7;
    g.beginPath(); g.moveTo(x-r*4,y); g.lineTo(x+r*4,y); g.moveTo(x,y-r*4); g.lineTo(x,y+r*4);
    g.stroke();
  }
  g.globalAlpha=1;
}

const BG={mode:'none',err:'',cv:null,gl:null,prog:null,u:{},tex:null,pack:null,raf:0,lastT:0,
  last:null,t0:0,w:0,h:0,sw:0,sh:0,cur:null,prv:null,buf:null,energy:0,peak:0,frames:0,
  strokes:0,rs:0.72,HS:620,P:null};
function bgHex(h){h=(h||'').trim();
  if(h[0]!=='#'||(h.length!==7&&h.length!==4)) return [1,1,1];
  let s=h.slice(1); if(s.length===3) s=s.split('').map(c=>c+c).join('');
  return [parseInt(s.slice(0,2),16)/255,parseInt(s.slice(2,4),16)/255,parseInt(s.slice(4,6),16)/255];}
function bgColors(){
  const cs=getComputedStyle(document.documentElement);
  BG.P={foam:bgHex(cs.getPropertyValue('--w-foam')),glint:bgHex(cs.getPropertyValue('--w-glint')),
    deep:bgHex(cs.getPropertyValue('--w-deep')),gain:+(cs.getPropertyValue('--w-gain')||8),
    foamT:+(cs.getPropertyValue('--w-foamth')||0.010),alpha:+(cs.getPropertyValue('--w-alpha')||0.95)};
}
function bgResize(){
  if(!BG.cv) return;
  BG.w=innerWidth; BG.h=innerHeight;
  const k=Math.min(1.5,window.devicePixelRatio||1)*BG.rs;
  BG.cv.width=Math.max(2,Math.floor(BG.w*k)); BG.cv.height=Math.max(2,Math.floor(BG.h*k));
  BG.sw=240; BG.sh=Math.max(60,Math.round(240*BG.h/Math.max(1,BG.w)));
  const n=BG.sw*BG.sh;
  BG.cur=new Float32Array(n); BG.prv=new Float32Array(n); BG.buf=new Float32Array(n);
  BG.pack=new Uint8Array(n); BG.t0=0; BG.last=null; BG.energy=0; BG.peak=0;
  if(BG.gl){ BG.gl.viewport(0,0,BG.cv.width,BG.cv.height); bgClear(); }
  drawStars();
}
function bgClear(){ if(BG.gl){ const g=BG.gl; g.clearColor(0,0,0,0); g.clear(g.COLOR_BUFFER_BIT); } }
function bgStamp(sx,sy,amt,rad){
  const sw=BG.sw,sh=BG.sh,cur=BG.cur,r2=rad*rad;
  const x0=Math.max(1,Math.floor(sx-rad)),x1=Math.min(sw-1,Math.ceil(sx+rad));
  const y0=Math.max(1,Math.floor(sy-rad)),y1=Math.min(sh-1,Math.ceil(sy+rad));
  for(let y=y0;y<y1;y++){ const row=y*sw,dy=y-sy;
    for(let x=x0;x<x1;x++){ const dx=x-sx,d2=dx*dx+dy*dy; if(d2<r2) cur[row+x]+=amt*(1-d2/r2); } }
}
/* 阻尼按秒：0.964^60 ≈ 0.111 ⇒ "一秒衰减到 11%"。按帧写会在低帧率下永不平（画廊实测撞到）。 */
function bgStep(dt){
  const sw=BG.sw,sh=BG.sh,cur=BG.cur,prv=BG.prv,buf=BG.buf,
        damp=Math.pow(0.11,Math.min(0.1,Math.max(0.001,dt)));
  let e=0,pk=0;
  for(let y=1;y<sh-1;y++){ const row=y*sw;
    for(let x=1;x<sw-1;x++){ const i=row+x;
      const v=((cur[i-1]+cur[i+1]+cur[i-sw]+cur[i+sw])*0.5-prv[i])*damp;
      buf[i]=v; e+=v*v; const a=v<0?-v:v; if(a>pk) pk=a; } }
  for(let x=0;x<sw;x++){ buf[x]=0; buf[(sh-1)*sw+x]=0; }
  for(let y=0;y<sh;y++){ buf[y*sw]=0; buf[y*sw+sw-1]=0; }
  BG.prv=cur; BG.cur=buf; BG.buf=prv; BG.energy=e/(sw*sh); BG.peak=pk;
}
function bgUpload(){
  const g=BG.gl,cur=BG.cur,pk=BG.pack,HS=BG.HS;
  for(let i=0;i<pk.length;i++){ let v=128+cur[i]*HS; pk[i]=v<0?0:(v>255?255:v|0); }
  g.bindTexture(g.TEXTURE_2D,BG.tex);
  g.texImage2D(g.TEXTURE_2D,0,g.R8,BG.sw,BG.sh,0,g.RED,g.UNSIGNED_BYTE,pk);
}
const BG_VS='#version 300 es\nin vec2 a_pos; out vec2 vUv;\nvoid main(){ vUv = a_pos*0.5+0.5; gl_Position = vec4(a_pos,0.0,1.0); }';
const BG_FS=['#version 300 es','precision mediump float;','in vec2 vUv;',
'uniform sampler2D u_h;','uniform vec2 u_tx;','uniform vec3 u_foam, u_glint, u_deep;',
'uniform float u_gain, u_foamT, u_alpha;','out vec4 frag;','void main(){',
'  float h = texture(u_h, vUv).r;',
'  float re= texture(u_h, vUv+vec2(u_tx.x,0.0)).r;','  float le= texture(u_h, vUv-vec2(u_tx.x,0.0)).r;',
'  float up= texture(u_h, vUv+vec2(0.0,u_tx.y)).r;','  float dn= texture(u_h, vUv-vec2(0.0,u_tx.y)).r;',
'  vec2 gr = vec2(re-le, up-dn);','  float gm = length(gr);',
'  vec3 nz = normalize(vec3(-gr.x*u_gain, -gr.y*u_gain, 1.0));',
'  vec3 L  = normalize(vec3(-0.42, 0.55, 0.72));',
'  float sp = pow(max(dot(reflect(-L,nz), vec3(0.0,0.0,1.0)),0.0), 28.0);',
'  float crest = smoothstep(0.545, 0.70, h);',
   /* 陡坡起沫 + 波顶也起沫，两条取大：只留前一条就"水变蓝了"而不是"起了浪花"。 */
'  float foam  = max(smoothstep(u_foamT, u_foamT*2.2, gm) * (0.30 + 0.70*crest), crest);',
'  float body  = abs(h-0.5)*2.0;',
'  float a = clamp(foam + sp*0.9 + body*0.06, 0.0, 1.0) * u_alpha;',
'  vec3 col = (u_foam*foam + u_glint*sp*0.9 + u_deep*body*0.06) / max(a, 1e-3);',
'  frag = vec4(clamp(col,0.0,1.0), a);','}'].join('\n');
function bgShader(ty,src){ const g=BG.gl,s=g.createShader(ty); g.shaderSource(s,src); g.compileShader(s);
  if(!g.getShaderParameter(s,g.COMPILE_STATUS)){ BG.err=g.getShaderInfoLog(s)||'compile'; return null; }
  return s; }
function bgInit(){
  const g=BG.gl=BG.cv.getContext('webgl2',{alpha:true,premultipliedAlpha:false,powerPreference:'low-power'});
  if(!g){ BG.mode='css'; BG.err='no webgl2'; return; }
  const vs=bgShader(g.VERTEX_SHADER,BG_VS),fs=bgShader(g.FRAGMENT_SHADER,BG_FS);
  if(!vs||!fs){ BG.mode='css'; return; }
  const pr=g.createProgram(); g.attachShader(pr,vs); g.attachShader(pr,fs); g.linkProgram(pr);
  if(!g.getProgramParameter(pr,g.LINK_STATUS)){ BG.mode='css'; BG.err=g.getProgramInfoLog(pr)||'link'; return; }
  BG.prog=pr; BG.mode='gl'; g.useProgram(pr);
  const vao=g.createVertexArray(); g.bindVertexArray(vao);
  const b=g.createBuffer(); g.bindBuffer(g.ARRAY_BUFFER,b);
  g.bufferData(g.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),g.STATIC_DRAW);
  const loc=g.getAttribLocation(pr,'a_pos'); g.enableVertexAttribArray(loc);
  g.vertexAttribPointer(loc,2,g.FLOAT,false,0,0);
  'u_h u_tx u_foam u_glint u_deep u_gain u_foamT u_alpha'.split(' ')
    .forEach(n=>{ BG.u[n]=g.getUniformLocation(pr,n); });
  BG.tex=g.createTexture(); g.bindTexture(g.TEXTURE_2D,BG.tex);
  g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.LINEAR);
  g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.LINEAR);
  g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_S,g.CLAMP_TO_EDGE);
  g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_T,g.CLAMP_TO_EDGE);
  g.disable(g.DEPTH_TEST); g.enable(g.BLEND); g.blendFunc(g.SRC_ALPHA,g.ONE_MINUS_SRC_ALPHA);
}
function bgRender(){
  const g=BG.gl,P=BG.P; g.useProgram(BG.prog); g.activeTexture(g.TEXTURE0);
  g.bindTexture(g.TEXTURE_2D,BG.tex); g.uniform1i(BG.u.u_h,0);
  g.uniform2f(BG.u.u_tx,1/BG.sw,1/BG.sh);
  g.uniform3fv(BG.u.u_foam,P.foam); g.uniform3fv(BG.u.u_glint,P.glint); g.uniform3fv(BG.u.u_deep,P.deep);
  g.uniform1f(BG.u.u_gain,P.gain); g.uniform1f(BG.u.u_foamT,P.foamT); g.uniform1f(BG.u.u_alpha,P.alpha);
  g.drawArrays(g.TRIANGLES,0,3);
}
/* 收摊阈值按**峰值**而不是平均能量，且离衰减尾端留余量（0.012 对应纹理 58/255 的偏离，
   仍不可见，但比旧值 0.0045 高出 2.7 倍——贴着尾端定会让"能不能平"取决于最后一帧的运气）。 */
const BG_EPS=0.012;
function bgDraw(ts){
  if(!SEA){ BG.raf=0; return; }
  const dt=BG.t0?Math.min(0.1,(ts-BG.t0)/1000):1/60; BG.t0=ts;
  bgStep(dt); bgUpload(); bgRender(); BG.frames++;
  if(BG.peak>BG_EPS){ BG.raf=requestAnimationFrame(bgDraw); }
  else { BG.raf=0; bgClear(); }
}
function bgStart(){ if(!BG.raf && SEA && BG.mode==='gl') BG.raf=requestAnimationFrame(bgDraw); }
function bgWake(x,y,down){
  if(!SEA || BG.mode!=='gl') return;
  const sx=x/innerWidth*BG.sw, sy=(1-y/innerHeight)*BG.sh;
  let lx=sx,ly=sy,dx=0,dy=0;
  if(BG.last){ lx=BG.last[0]; ly=BG.last[1]; dx=sx-lx; dy=sy-ly; }
  BG.last=[sx,sy]; BG.lastT=performance.now();
  const sp=Math.hypot(dx,dy);
  /* 指针「瞬移」不算划水：光标从窗口外进来、跨标签回来、探针一把挪到角落，都会沿那条直线
     糊一道用户没要求的浪。超过阈值只挪锚点、不起浪。 */
  if(!down && sp>45) return;
  if(down||sp<0.3){ bgStamp(sx,sy,down?0.028:0.0022,down?5.0:2.4); }
  else{
    const amt=Math.min(0.042,0.009+sp*0.0040), rad=Math.max(2.2,Math.min(7.0,2.0+sp*0.45));
    const steps=Math.max(1,Math.min(12,Math.round(sp/(rad*0.5))));
    /* 偶极注入：前进方向给正、身后给负 —— 才有向外摊开的船头波（"聚了又散"的那一步）。 */
    for(let k=1;k<=steps;k++){ const f=k/steps,px=lx+dx*f,py=ly+dy*f;
      bgStamp(px+dx*0.12,py+dy*0.12,amt,rad);
      bgStamp(px-dx*0.16,py-dy*0.16,-amt*0.70,rad*0.85); }
    BG.strokes++;
  }
  bgStart();
}
let bgPend=null;
window.addEventListener('pointermove',e=>{
  if(!SEA||BG.mode!=='gl') return;                    // 节流到每帧一次，但取最新坐标不丢中间点
  if(bgPend) return;
  bgPend=requestAnimationFrame(()=>{ bgPend=null; bgWake(e.clientX,e.clientY,false); });
},{passive:true});
window.addEventListener('pointerdown',e=>{ bgWake(e.clientX,e.clientY,true); },{passive:true});
window.addEventListener('blur',()=>{ BG.last=null; });
function seaApply(){
  document.body.classList.toggle('plain',!SEA);
  $('#bSea').textContent='星辰大海 · '+(SEA?'开':'关');
  if(!SEA){ if(BG.raf){ cancelAnimationFrame(BG.raf); BG.raf=0; } bgClear();
    const st=$('#stars'); if(st){ const g=st.getContext('2d');
      if(g) g.clearRect(0,0,st.width,st.height); } return; }
  if(!BG.cv){
    BG.cv=document.createElement('canvas'); $('#bgfx').appendChild(BG.cv);
    bgColors(); bgInit(); bgResize(); window.addEventListener('resize',bgResize);
    if(BG.mode!=='gl'){ BG.cv.remove(); BG.cv=null; }
  } else bgResize();
  if(BG.mode==='gl') bgStart();
}
$('#bSea').onclick=()=>{ SEA=!SEA; localStorage.setItem('panel.sea',SEA?'1':'0'); seaApply(); };

/* ── 数据 ─────────────────────────────────────────────────────────── */
async function apiState(){
  // 首屏要等 /api/state 算完输入指纹（扫 9 万个源包），那之前 S 是 null ——
  // render() 必须扛得住空态，否则整页停在"只有图例、中间全空"的样子，看着像坏了。
  let j=null;
  try{ j=await (await fetch('/api/state')).json(); }
  catch(e){ LOADERR=String(e); setTimeout(apiState,2500); return; }
  S=j; S.state=S.state||{}; LOADED=true;
  render();
  if(S.running && !curJob) tail(S.running.id);
}
function stagesOf(n){ return (S.stages||[]).filter(s=>(s.step||0)===n); }
let LOADED=false, LOADERR='';
function render(){
  if(!S) return;
  $('#fp').textContent=S.fingerprint||'—';
  $('#scope').textContent = S.scope==null ? '未 detect（先跑 ①）' : '增量 '+S.scope+' 个 stem';
  const all=S.stages||[];
  const passN=all.filter(s=>statusOf(s.key)==='pass').length;
  $('#prog').textContent=passN+' / '+all.length+' 判绿';
  if(LOADERR){ $('#warn').textContent='读 /api/state 失败：'+LOADERR+'（2.5 秒后自动重试）';
    $('#warn').classList.add('on'); }
  else if(S.error){ $('#warn').textContent='读阶段清单失败：'+S.error; $('#warn').classList.add('on'); }
  else if(!all.length){ $('#warn').textContent='阶段清单为空：update_pipeline 没读到。';
    $('#warn').classList.add('on'); }
  else $('#warn').classList.remove('on');

  /* 左轨 */
  const steps=S.steps||{}; const rail=$('#rail'); rail.innerHTML='';
  Object.keys(steps).sort().forEach(k=>{
    const n=+k, list=stagesOf(n);
    const worst=list.map(s=>statusOf(s.key))
      .reduce((a,b)=>['fail','run','await','pass','idle'].indexOf(a)<=['fail','run','await','pass','idle'].indexOf(b)?a:b,'idle');
    const doneN=list.filter(s=>statusOf(s.key)==='pass').length;
    const b=document.createElement('button');
    b.className='step'+(n===step?' on':''); b.style.animationDelay=(n*55)+'ms';
    // 左轨不放步骤说明：那句话在中间 hero 里已经占了一整行，重复一遍会把图例挤到折叠线以下
    b.innerHTML='<span class="num">'+n+'</span><span><b>'+esc(steps[k][0])+'</b><span class="dots">'+
      list.map(s=>'<i class="dot '+statusOf(s.key)+'" title="'+esc(s.key)+'"></i>').join('')+
      '</span><span class="cnt">'+list.length+' 个阶段 · 判绿 '+doneN+'</span></span>'+
      (worst==='fail'?'<span class="stt fail">红</span>'
        :worst==='await'?'<span class="stt await">签</span>'
        :doneN===list.length&&list.length?'<span class="stt pass">齐</span>':'');
    b.onclick=()=>{ step=n; render(); };
    rail.appendChild(b);
  });
  const ungrouped=all.filter(s=>!steps[s.step||0]);
  if(ungrouped.length){
    const b=document.createElement('div'); b.className='step';
    b.innerHTML='<span class="num">?</span><span><b>未归组</b>'+
      '<span class="cnt">新加了阶段但没写 step：'+ungrouped.map(s=>s.key).join(', ')+'</span></span>'+
      '<span class="stt fail">红</span>';
    rail.appendChild(b);
  }

  /* 中间 */
  const list=step===0?all:stagesOf(step);
  $('#sTitle').textContent=(steps[step]?('①②③④'[step-1]+'  '+steps[step][0]):'全部阶段');
  $('#sDesc').textContent=steps[step]?steps[step][1]:'未归组的阶段';
  $('#sCount').textContent=list.length+' 个';
  $('#cta').innerHTML=ctaFor(step).map(c=>'<button class="'+c.c+'" data-a="'+c.a+'"'+
    (S.running?' disabled':'')+'>'+c.t+'</button>').join('');
  const liveUnapproved=list.filter(s=>s.tier==='live'&&statusOf(s.key)==='await');
  const sn=$('#scopeNote');
  if(step===2&&liveUnapproved.length){
    sn.textContent='这一步里 '+liveUnapproved.map(s=>s.key).join(' / ')+
      ' 标了「写正式」：不签字它们只算差异、不落正式区（详见每张卡上的「写到」）。';
    sn.classList.add('on');
  } else if(S.scope==null&&step>=2){
    sn.textContent='还没做过增量 detect：现在跑会把范围当成「未定」，先回第 ① 步跑一次差异。';
    sn.classList.add('on');
  } else sn.classList.remove('on');

  const cards=$('#cards'); cards.innerHTML='';
  list.forEach((s,i)=>{
    const st=statusOf(s.key), r=(S.state||{})[s.key]||{}, T=TIER[s.tier]||['?','r'];
    const d=document.createElement('div');
    d.className='stage '+(st==='fail'?'fail':st==='await'?'await':'');
    d.style.animationDelay=(60+i*26)+'ms';
    d.innerHTML='<div class="srow"><span class="skey">'+esc(s.key)+'</span>'+
      '<span class="tier '+T[1]+'">'+T[0]+'</span>'+
      '<span class="stt '+st+'">'+STT[st]+'</span></div>'+
      '<p class="stitle">'+esc(s.title)+'</p>'+
      '<dl class="kv">'+
      '<dt>写到</dt><dd>'+esc(s.writes||'—')+'</dd>'+
      '<dt>判据</dt><dd>'+esc(s.judge||'—')+'</dd>'+
      (r.detail?'<dt>上次</dt><dd>'+esc(r.detail)+(r.at?'　<span class="dim">'+esc(r.at)+'</span>':'')+'</dd>':'')+
      '</dl>'+
      '<div class="sact">'+
      (s.tier==='live'?'<label class="signbox"><input type="checkbox" class="appr" data-k="'+
        s.key+'"> 我签字：放行它写正式区</label>':'')+
      '<button class="mini" data-run="'+esc(s.key)+'">单独跑这一步</button>'+
      '<span class="spacer"></span></div>';
    cards.appendChild(d);
  });

  const sh=$('#sheets');
  if(!(S.sheets||[]).length) sh.innerHTML='<p class="dim" style="font-size:12px;margin:0">'+
    '（还没有对照表 —— 跑一次「看图对比」后出现在这里）</p>';
  else sh.innerHTML=S.sheets.map(x=>'<a target="_blank" href="/file?path='+encodeURIComponent(x.name)+
    '"><img loading="lazy" src="/file?path='+encodeURIComponent(x.name)+'" alt="'+esc(x.name)+
    '"><div class="cap"><span>'+esc(x.name)+'</span><span>'+x.kb+'KB '+esc(x.mt)+'</span></div></a>').join('');

  $('#runs').innerHTML=(S.runs||[]).map(rr=>'<tr><td class="dim" style="white-space:nowrap">'+
    esc((rr.started||'').slice(11))+'</td><td>'+esc(rr.label||'')+
    '<div class="dim" style="font-size:11px">'+esc(rr.state==='done'?(rr.clean===false?'没看到收尾行':'完成'):rr.state||'')
    +'</div></td><td style="text-align:right"><span class="tag '+esc(rr.state||'')+'">'+
    (rr.state==='running'?'在跑':'看日志')+'</span></td></tr>').join('')||
    '<tr><td colspan="3" class="dim">还没有任务</td></tr>';
  $$('#runs tr').forEach((tr,i)=>{ const rr=(S.runs||[])[i]; if(!rr) return;
    tr.style.cursor='pointer'; tr.onclick=()=>tail(rr.id); });
  $$('#cta button').forEach(b=>b.onclick=()=>ctaRun(b.dataset.a));
  $$('#cards [data-run]').forEach(b=>b.onclick=()=>{
    const k=b.dataset.run, s=(S.stages||[]).find(x=>x.key===k);
    const ap=s&&s.tier==='live'&&b.closest('.stage').querySelector('.appr').checked;
    if(ap&&!confirm('签字放行 '+k+'：它会写进正式区（会先备份）。确认？')) return;
    post({stages:[k],approve:ap?[k]:[],force:force},null); });
}
function ctaFor(n){
  if(n===1) return [{a:'diff',c:'go',t:'▶ 跑 preflight + 看差异（不下载）'},
                   {a:'pull',c:'sign',t:'⚑ 签字：从模拟器拉包进 files/'}];
  if(n===2) return [{a:'tocheck',c:'go',t:'▶ 跑到「待确认」（正式区不动）'},
                   {a:'staged',c:'',t:'只重跑导出三件'}];
  if(n===3) return [{a:'review',c:'go',t:'▶ 出对照表'}];
  return [{a:'swap',c:'sign',t:'⇩ 签字换入正式产物'},{a:'regress',c:'',t:'只跑回归'}];
}
function ctaRun(a){
  const live4=(S.stages||[]).filter(s=>s.step===4&&s.tier==='live').map(s=>s.key);
  const all4=(S.stages||[]).filter(s=>s.step===4).map(s=>s.key);
  if(a==='diff') return post({stages:['preflight','pull'],force:force});
  if(a==='pull') return sign(['pull'],'① 从模拟器拉包',
    '它会 adb pull 新包写进 files/AssetBundles（本地那 30GB 源目录，只补缺的和变了的）。'+
    '源包一旦覆盖，旧版本本地就没了——这正是它被划成「写正式」的原因。');
  if(a==='tocheck') return post({stages:[],force:force});
  if(a==='staged') return post({stages:['paintings','spine','live2d'],force:force});
  if(a==='review') return post({stages:['review'],force:force});
  if(a==='regress') return post({stages:['regress'],force:force});
  if(a==='swap') return sign(live4,'④ 换入：'+live4.join(' + '),
    '换入前整批备份到 Output/_OLD_bak/pipeline_<日期>/；随后重建缩略图与索引，'+
    '要过「索引零回退闸门」和「部署 4/4 同 inode」两道检查，任一判红就停。');
}
function sign(keys,what,note){
  if(!confirm('签字放行：'+what+'\n\n'+note+'\n\n确认？')) return;
  const s4=(S.stages||[]).filter(s=>s.step===4).map(s=>s.key);
  post({stages:keys.every(k=>s4.includes(k))?s4:keys,approve:keys,force:force});
}
async function post(b){
  const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(b)});
  const j=await r.json();
  if(j.error){ $('#warn').textContent=j.error; $('#warn').classList.add('on'); return; }
  $('#warn').classList.remove('on'); tail(j.id);
}
window.tail=async function(id){
  curJob=id; off=0; $('#log').textContent=''; $('#jobinfo').textContent='任务 '+id;
  if(timer) clearInterval(timer); timer=setInterval(pump,1100); pump();
};
function colorize(t){
  return esc(t).replace(/(✅[^\n]*|判绿[^\n]*)/g,'<span class="good">$1</span>')
               .replace(/(❌[^\n]*|!![^\n]*)/g,'<span class="bad">$1</span>');
}
async function pump(){
  if(!curJob) return;
  const j=await (await fetch('/api/log?id='+curJob+'&offset='+off)).json();
  if(j.text){ $('#log').insertAdjacentHTML('beforeend',colorize(j.text));
    if(follow) $('#log').scrollTop=$('#log').scrollHeight; }
  off=j.offset;
  $('#jobstat').innerHTML=j.state==='running'?'<span style="color:var(--run)">● 运行中</span>':'空闲';
  $('#jobinfo').textContent='任务 '+curJob+(j.state?(' · '+j.state):'');
  if(j.state!=='running'){ clearInterval(timer); timer=null; curJob=null; await apiState(); }
}
$('#bFollow').onclick=e=>{ follow=!follow; e.target.textContent=follow?'跟随最新':'已暂停跟随'; };
$('#bClear').onclick=()=>{ $('#log').textContent=''; };
$('#bForce').onclick=e=>{ force=!force; e.target.textContent=force?'缓存：已绕过（重跑暂存档）':'缓存：按指纹复用';
  e.target.style.borderColor=force?'var(--await)':''; };
$('#bHelp').onclick=()=>$('#help').classList.add('on');
$$('#help [data-close]').forEach(el=>el.onclick=()=>$('#help').classList.remove('on'));
document.addEventListener('keydown',e=>{ if(e.key==='Escape'){
  $('#help').classList.remove('on'); $('#lightbox').classList.remove('on'); } });
document.addEventListener('click',e=>{ if(e.target.matches('.sheets img')){
  $('#lightbox img').src=e.target.src; $('#lightbox').classList.add('on'); e.preventDefault(); } });
$('#lightbox').onclick=e=>e.currentTarget.classList.remove('on');
seaApply(); apiState(); setInterval(()=>{ if(!timer) apiState(); },8000);
window.BG=BG; window.panelState=()=>S;
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
