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
  /* 东京夜：偏紫的黑底 + 钠灯暖橙 + 霓虹品红/青。
     ⚠️ 五个**状态色一个都没动**（idle/pass/fail/await/run）—— 换主题不许顺手改语义色，
     否则"这个红是报错还是配色"又分不清了。 */
  --abyss:#06040e; --deep:#150d1f;
  --line:rgba(178,166,214,.18); --line2:rgba(178,166,214,.36);
  --txt:#efe9f7; --dim:#9b90b4; --dim2:#6f6686;
  --idle:#3f5a6e; --pass:#4fd6a8; --fail:#ff6f6f; --await:#f2bd72; --run:#5fd0e8;
  --brand:#a06bff; --pop:#ff3d7f;   /* 装饰专用两色：都不是状态色（见顶部纪律） */
  /* 星点色：只有背景那层读，组件一个都不碰 */
  --s-1:#f6e7d3; --s-2:#cfe6ff; --s-3:#ffd6a5; --s-4:#ff9ecb;
  --s-link:#a06bff;   /* 星座连线：紫，不是任何一个状态色 */
  --fd:'Bahnschrift','DIN Alternate','Microsoft YaHei UI',system-ui,sans-serif;
  --fb:'Microsoft YaHei UI','Microsoft YaHei',system-ui,sans-serif;
  --fm:'Cascadia Mono','Consolas',ui-monospace,monospace;
  --ez:cubic-bezier(.22,.61,.36,1);
  /* 内容面一律**不透明**：上一版 .pane 用 alpha .90，星点会渗进卡片文字区（实测最大 36）。
     主题只留在**没有正文**的地方：页面底、栏间空隙、hero 带、底部那条夜空带。
   换主题时**五个状态色一个都不许动**——那是语义，不是配色。 */
  --pane:#12101f; --card:#181527;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;font:14px/1.65 var(--fb);color:var(--txt);overflow:hidden;
  background:linear-gradient(180deg,var(--abyss) 0%,#0b0716 46%,var(--deep) 100%)}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-thumb{background:rgba(178,166,214,.22);border-radius:6px}
::-webkit-scrollbar-thumb:hover{background:rgba(178,166,214,.38)}
::-webkit-scrollbar-track{background:transparent}

/* ══ 背景层：东京夜的星野 ═══════════════════════════════════════════════
   三团不动的城市光晕（钠灯橙 / 霓虹品红 / 高架青）当底，星点画在一张 2D 画布上：
   鼠标划过 ⇒ 星点被推开；停手 ⇒ 弹簧把它们拉回原位，能量归零后**写回 home 再画一帧**。
   最后那一句是关键：它保证"散过又聚回"的终点和初始帧**逐像素相同**——
   画廊那版背景被否三轮换来的就是这条（背景自己在动 = 一张装饰壁纸）。 */
#bgfx{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
#bgfx .bfield{position:absolute;inset:-10%}
#bgfx .glow{position:absolute;width:74vmax;height:74vmax;border-radius:50%;opacity:.55}
#bgfx .g1{left:-26vmax;bottom:-34vmax;width:80vmax;height:80vmax;
  background:radial-gradient(closest-side,rgba(255,146,58,.62) 0%,rgba(255,146,58,.20) 42%,
    transparent 100%)}
#bgfx .g2{right:-24vmax;bottom:-30vmax;width:70vmax;height:70vmax;
  background:radial-gradient(closest-side,rgba(255,61,127,.52) 0%,rgba(255,61,127,.16) 42%,
    transparent 100%)}
#bgfx .g3{right:0vmax;top:-28vmax;width:56vmax;height:56vmax;
  background:radial-gradient(closest-side,rgba(47,208,255,.44) 0%,rgba(47,208,255,.14) 42%,
    transparent 100%)}
#bgfx canvas{position:absolute;inset:0;width:100%;height:100%}
body.plain #bgfx .glow{display:none}

/* ══ 骨架：三个独立滚动的区，页面本身不滚 ═══════════════════════════════ */
.app{position:relative;z-index:1;display:flex;flex-direction:column;height:100vh}
header{position:relative;z-index:10;flex:0 0 auto;display:flex;align-items:center;gap:20px;
  padding:13px 22px;background:#100d1d;
  border-bottom:1px solid rgba(206,186,255,.28);
  box-shadow:inset 0 1px 0 rgba(226,210,255,.24),0 1px 0 rgba(6,4,14,.6),0 16px 34px -26px #000}
header::after{content:'';position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(104deg,rgba(255,142,192,.10) 0 14%,transparent 14%)}
.brand{display:flex;align-items:center;gap:11px;flex:0 0 auto}
.brand svg{display:block}
.brand h1{margin:0;font:600 19px/1.15 var(--fd);letter-spacing:.06em}
.brand p{margin:2px 0 0;font-size:11.5px;color:var(--dim2);letter-spacing:.04em}
.meters{display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex:1 1 auto;min-width:0}
.meter{font:11px/1 var(--fm);padding:5px 9px;border-radius:8px;background:#1b1730;
  border:1px solid var(--line);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.meter b{color:var(--dim);font-weight:400;margin-right:6px}
.meter.ok b,.meter.ok span{color:var(--pass)}
.act{display:flex;gap:8px;flex:0 0 auto}

button{font:inherit;font-size:13px;padding:7px 14px;border-radius:9px;border:1px solid var(--line);
  background:var(--card);color:var(--txt);cursor:pointer;
  transition:background .16s var(--ez),border-color .16s var(--ez),transform .12s var(--ez),opacity .16s}
button:hover{border-color:var(--line2);background:#241d3a}
button:active{transform:translateY(1px)}
button:disabled{opacity:.38;cursor:not-allowed;transform:none}
button:disabled:hover{border-color:var(--line);background:var(--card)}
button:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
button.go{background:linear-gradient(180deg,#b32b62,#7c1c46);border-color:#ff3d7f;
  color:#ffe9f2;font-weight:600;
  box-shadow:0 12px 26px -16px rgba(255,61,127,.85),inset 0 1px 0 rgba(255,190,215,.32)}
button.go:hover{background:linear-gradient(180deg,#cb3a72,#8e2350)}
button.sign{border-color:rgba(242,189,114,.55);color:#ffd9a2;background:rgba(58,42,20,.42)}
button.sign:hover{background:rgba(74,54,26,.62);border-color:var(--await)}
button.ghost{background:transparent;font-size:12.5px;padding:6px 11px}
/* 「怎么用」不是动作按钮，不能和"当前步的主动作"共用同一块品红实心——
   实心品红在这个界面里只有一个含义：这一步的主操作。 */
button.help{background:transparent;border-color:rgba(180,137,255,.55);color:#e4d7ff;
  font-weight:600}
button.help:hover{background:rgba(180,137,255,.14);border-color:#b489ff}
button.mini{font-size:11.5px;padding:3px 9px;border-radius:7px}

/* ══ 大气区（hero / seaband）与数据区的分工 ═════════════════════════════
   规矩只有一条：**能读数据、能看图的位置一律不透明**，主题只出现在没有数据的带里。
   hero 放当前步的标题与一句说明；skyband 是底部那条夜空带，划过星点散开、停下必聚回。
   两处都只许放标题级短文（带 text-shadow 压住任何星点亮度），
   阶段卡、日志、对照图、指标 pill 一个都不许放进去。 */
.skyband{flex:0 0 auto;height:176px;display:flex;flex-direction:column;align-items:center;
  justify-content:flex-start;gap:5px;text-align:center;position:relative;z-index:1;
  padding-top:16px;border-top:1px solid rgba(206,186,255,.10)}
.skyband .hl{font:600 11px/1 var(--fd);letter-spacing:.26em;text-transform:uppercase;
  color:rgba(214,204,236,.72);text-shadow:0 1px 10px rgba(3,12,20,.95)}
.skyband p{margin:0;font-size:11.5px;line-height:1.7;color:rgba(190,180,214,.72);
  max-width:76ch;text-shadow:0 1px 8px rgba(3,12,20,.95)}
.wrap{flex:1 1 auto;min-height:0;display:grid;gap:16px;padding:14px 26px 6px;
  grid-template-columns:262px minmax(520px,1fr) minmax(360px,.66fr);max-width:1760px;
  margin:0 auto;width:100%;align-items:stretch}
/* 列是 flex 容器：面板必须 flex-shrink:0，否则"内容比列高"时**每个面板都被压扁**，
   再叠上 overflow:hidden 就是把卡片和日志的下沿直接切掉（实测第二张卡被切 45px、
   日志被切 81px）。要滚的是列本身，不是把内容塞进固定高度的盒子里。 */
.col{min-height:0;overflow:auto;display:flex;flex-direction:column;gap:12px;padding-right:2px}
.col>.pane{flex:0 0 auto}
/* 日志格给**确定的视口高度**，不要用 flex:1 去"填满剩余"：
   在 grid + overflow:auto 这套组合下它实测会塌成 28px（只剩标题条），
   把 pre 顶出面板外 170px。可预测比聪明重要。 */
.col>.logpane{flex:0 0 auto}
.pane{position:relative;background:var(--pane);border:1px solid var(--line);
  border-radius:14px;padding:13px 15px;
  box-shadow:0 22px 46px -32px rgba(0,0,0,.92),inset 0 1px 0 rgba(214,200,255,.07)}
/* 东京夜招牌的那根灯管：面板顶边一条 1px 紫→品红亮线，静止时半亮、指针过来才全亮。
   它是**静态渐变**（没有 animation）——背景可见区与内容区都要求"静止两帧逐像素相同"。 */
.pane::before{content:'';position:absolute;left:14px;right:14px;top:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(160,107,255,.62) 16%,
    rgba(255,61,127,.58) 58%,transparent);
  opacity:.42;transition:opacity .22s var(--ez)}
.pane:hover::before{opacity:1}
.ph{font:600 11px/1 var(--fd);letter-spacing:.18em;text-transform:uppercase;color:var(--dim);
  margin:0 0 11px;display:flex;align-items:center;justify-content:space-between;gap:8px}

/* ══ 步骤导航 ═════════════════════════════════════════════════════════ */
.step{position:relative;display:grid;grid-template-columns:26px 1fr auto;gap:10px;align-items:start;
  width:100%;text-align:left;padding:9px 10px;border-radius:12px;background:transparent;
  border:1px solid transparent;animation:rise .46s var(--ez) backwards}
.step:hover{background:#102c44;border-color:var(--line)}
.step.on{background:linear-gradient(180deg,#2a2145,#191329);
  border-color:rgba(160,107,255,.5);box-shadow:0 14px 30px -20px rgba(0,0,0,.9)}
.step.on::after{content:'';position:absolute;left:-1px;top:9px;bottom:9px;width:2px;
  border-radius:2px;background:linear-gradient(180deg,#a06bff,#ff3d7f);
  box-shadow:0 0 12px rgba(255,61,127,.7)}
.step .num{font:600 19px/1.35 var(--fd);letter-spacing:-.02em;color:var(--dim);
  text-align:center;border:1px solid var(--line);border-radius:9px;background:#0d0a18}
.step.on .num{color:var(--brand);border-color:rgba(47,208,255,.5)}
.step b{display:block;font-size:13.5px;font-weight:600;letter-spacing:.02em}
.step em{display:block;font:400 11px/1.45 var(--fb);color:var(--dim);font-style:normal;
  margin-top:1px}
.step .cnt{font:11px/1 var(--fm);color:var(--dim2);margin-top:5px;display:block}
.dots{display:flex;gap:3px;align-items:center;margin-top:6px}
.dot{width:7px;height:7px;border-radius:2px;background:var(--idle)}
.dot.pass{background:var(--pass)}.dot.fail{background:var(--fail)}
.dot.await{background:var(--await)}.dot.run{background:var(--run);animation:pulse 1.1s infinite}
.dot.hot{outline:2px solid #ff3d7f;outline-offset:2px}
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
.hero{padding:15px 17px 14px;border-radius:16px;border:1px solid rgba(178,166,214,.14);
  background:linear-gradient(180deg,rgba(8,6,18,.20),rgba(6,4,14,.06))}
.whead{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}
.whead h2{margin:0;font:600 17px/1.3 var(--fd);letter-spacing:.04em;
  text-shadow:0 1px 12px rgba(3,12,20,.9),0 0 2px rgba(3,12,20,.75)}
.whead p{margin:4px 0 0;color:#c2b7da;font-size:12.5px;max-width:64ch;
  text-shadow:0 1px 8px rgba(3,12,20,.9)}
.cta{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 2px}
.scopenote{font-size:11.5px;color:var(--await);margin:6px 0 0;display:none}
.scopenote.on{display:block}

.g{display:flex;flex-direction:column;gap:9px}
.stage{position:relative;border:1px solid var(--line);border-radius:12px;padding:11px 13px;
  background:var(--card);animation:rise .4s var(--ez) backwards;
  transition:border-color .16s var(--ez),transform .16s var(--ez),box-shadow .18s var(--ez)}
.stage::before{content:'';position:absolute;left:0;top:12px;bottom:12px;width:2px;
  border-radius:2px;background:var(--line2);opacity:.35;
  transition:opacity .18s var(--ez),background .18s var(--ez)}
.stage:hover{border-color:var(--line2);transform:translateY(-1px);
  box-shadow:0 16px 30px -24px rgba(0,0,0,.9)}
.stage:hover::before{opacity:1;background:linear-gradient(180deg,#a06bff,#ff3d7f)}
.stage.hot::before{background:#ff3d7f;opacity:1}
.stage.fail{border-left:3px solid var(--fail)}
.stage.await{border-left:3px solid var(--await)}
.srow{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.skey{font:600 13.5px/1 var(--fm);letter-spacing:.02em}
/* 档位三枚一律中性色：只靠图标 + 字重 + 边框样式分级。
   上一版把「写正式」标成琥珀，而琥珀正好又是"等你签字"的颜色 —— 同一个 hue 负两件语义，
   用户就分不清"这行到底是我该动手，还是它出事了"。颜色这条资源整体留给状态。 */
.tier{font:10.5px/1 var(--fb);padding:3px 7px;border-radius:6px;border:1px solid var(--line);
  color:var(--dim);white-space:nowrap;background:rgba(178,166,214,.06)}
.tier.s{border-style:dashed;border-color:rgba(178,166,214,.32);color:#bfb4d6}
.tier.l{border-color:rgba(178,166,214,.50);color:#ded4f0;font-weight:600}
.stt{margin-left:auto;font:11.5px/1 var(--fb);padding:4px 9px;border-radius:999px;
  display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.stt::before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}
.stt.idle{background:rgba(63,90,110,.30);color:#a99fc0}
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
.signbox.on{background:rgba(242,189,114,.20);border-color:var(--await);color:#ffe3b8;
  box-shadow:0 0 16px -6px rgba(242,189,114,.75)}
.spacer{margin-left:auto}
.dim{color:var(--dim2)}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 8px}
.chip{font-size:11px;padding:3px 9px;border-radius:999px;border:1px solid var(--line);
  background:transparent;color:var(--dim)}
.chip.on{border-color:rgba(160,107,255,.6);color:#e4d7ff;background:rgba(160,107,255,.14)}
.kbd{font:10.5px/1 var(--fm);padding:3px 7px;border-radius:6px;border:1px solid var(--line);
  color:var(--dim);background:#0d0a18}
.kbd b{color:#e4d7ff;font-weight:600}

/* ══ 对照图：必须坐在完全不透明的底上 ═════════════════════════════════ */
.sheets{display:grid;grid-template-columns:repeat(auto-fill,minmax(238px,1fr));gap:10px}
.sheets a{display:block;border:1px solid var(--line);border-radius:10px;overflow:hidden;
  background:#0d0a18;text-decoration:none;color:inherit;
  transition:border-color .16s var(--ez),transform .16s var(--ez)}
.sheets a:hover{border-color:var(--line2);transform:translateY(-2px)}
.sheets img{display:block;width:100%;height:196px;object-fit:contain;background:#171328;
  cursor:zoom-in}
.sheets .cap{font-size:11px;color:var(--dim);padding:6px 9px;display:flex;
  justify-content:space-between;gap:8px;border-top:1px solid var(--line)}

/* ══ 日志 / 任务 ══════════════════════════════════════════════════════ */
pre{margin:0;font:11.8px/1.6 var(--fm);white-space:pre-wrap;word-break:break-all;
  background:#0c0918;border:1px solid var(--line);border-radius:10px;padding:10px 12px;
  overflow:auto;color:#d6cde8;height:40vh;min-height:170px}
pre .good{color:var(--pass)}pre .bad{color:var(--fail)}
.runs{width:100%;border-collapse:collapse;font-size:12px}
.runs th{font:600 10.5px/1 var(--fd);letter-spacing:.12em;text-transform:uppercase;
  color:var(--dim2);text-align:left;padding:0 6px 7px;border-bottom:1px solid var(--line)}
.runs td{padding:7px 6px;border-bottom:1px solid rgba(178,166,214,.09);vertical-align:top}
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
  background:linear-gradient(180deg,#141024,#0c0817);border-left:1px solid var(--line2);
  box-shadow:-30px 0 70px -30px #000;padding:22px 26px 40px;animation:slide .32s var(--ez)}
@keyframes slide{from{transform:translateX(28px);opacity:.6}}
#help h3{font:600 15px/1.3 var(--fd);margin:22px 0 8px;letter-spacing:.04em;color:var(--brand)}
#help h3:first-of-type{margin-top:4px}
#help p,#help li{font-size:13px;color:#d6cde8}
#help ul{margin:6px 0;padding-left:20px}
#help li{margin:4px 0}
#help table{width:100%;border-collapse:collapse;font-size:12.5px;margin:8px 0;
  table-layout:fixed}
#help table td:first-child,#help table th:first-child{width:7.4em;white-space:nowrap}
#help table td:nth-child(2){width:42%}
#help th,#help td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;
  vertical-align:top}
#help th{font:600 10.5px/1 var(--fd);letter-spacing:.1em;text-transform:uppercase;color:var(--dim2)}
#help code{font:11.8px/1.5 var(--fm);background:rgba(47,208,255,.10);padding:1px 6px;
  border-radius:5px;color:#9fe4ff}
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
      <path d="M17.4 2.6l1.5 4.3 4.3 1.5-4.3 1.5-1.5 4.3-1.5-4.3L11.6 8.4l4.3-1.5z"
            fill="#2fd0ff"/>
      <circle cx="5.4" cy="6.6" r="1.1" fill="#ff9ecb"/>
      <circle cx="10.2" cy="12.4" r=".8" fill="#ffd6a5" opacity=".9"/>
      <circle cx="3.6" cy="14.2" r=".7" fill="#cfe6ff" opacity=".7"/>
      <path d="M1 21.4c2.2 0 2.2-2 4.4-2s2.2 2 4.4 2 2.2-2 4.4-2 2.2 2 4.4 2 2.2-2 4.4-2"
            stroke="#ff3d7f" stroke-width="1.2" stroke-linecap="round" fill="none" opacity=".55"/>
      <path d="M1 25.2c2.2 0 2.2-1.6 4.4-1.6s2.2 1.6 4.4 1.6" stroke="#2fd0ff"
            stroke-width="1" stroke-linecap="round" fill="none" opacity=".35"/>
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
    <button id="bSea" class="ghost" title="关掉就把星野整层停用（背景不该挡正事）">星辰 · 开</button>
    <span class="kbd" title="键盘直接操作：1-4 切步骤，R 跑，P 只看计划，H 帮助，S 星辰开关">
      <b>1-4</b> 步骤 · <b>R</b> 跑 · <b>H</b> 帮助</span>
    <button id="bPlan" class="ghost">只看计划</button>
    <button id="bHelp" class="help">怎么用</button>
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
    <div class="pane logpane">
      <div class="ph">运行日志
        <span style="display:flex;gap:6px;align-items:center">
          <button id="bFollow" class="mini ghost">跟随最新</button>
          <button id="bClear" class="mini ghost">清空显示</button></span></div>
      <div class="chips" id="chips">
        <button class="chip on" data-f="all">全部</button>
        <button class="chip" data-f="bad">只看红</button>
        <button class="chip" data-f="await">等你签字</button>
        <button class="chip" data-f="stage">只看阶段行</button></div>
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

<div class="skyband">
  <span class="hl">夜空</span>
  <p>静止时这片天是黑的：鼠标经过哪里，哪里的星点才亮起来，约半秒后淡掉、不留痕。
     没人划时它一帧都不动；阶段卡、日志、对照图全在不透明面板里，星点渗不进去。</p>
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

  <h3>键位（摸熟比找按钮快）</h3>
  <p><code>1</code>…<code>4</code> 切步骤 · <code>R</code> 跑当前步的主动作 ·
  <code>P</code> 只看计划 · <code>H</code> 开关本抽屉 · <code>S</code> 开关星辰背景 ·
  <code>Esc</code> 关掉弹层。日志区上方还能按「只看红 / 等你签字 / 只看阶段行」筛。</p>

  <h3>背景那层是什么</h3>
  <p>东京夜的星野，<b>显影式</b>的：底上是三团不动的城市光晕（钠灯橙 / 霓虹品红 / 高架青），
  星点约 1800 颗画在一张画布上，但<b>静止时它们全灭</b>——你划过哪里，哪里的星才亮起来，
  亮的范围随划速变大（慢挪约 9px、快扫约 130px），约半秒淡干净、不留痕，
  亮着的星之间还会临时连出星座线。</p>
  <p>收摊时程序会把每颗星的亮度写回 0、位置写回原位再画一帧，所以"亮过又淡掉"的终点
  和最初那张<b>逐像素相同</b>——静止时一帧都不动，这是被验证过不挡正事的做法。
  觉得干扰就点顶栏「星辰 · 关」，整层直接停用并记住你的选择。
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
let SEA = localStorage.getItem('panel.sea')!=='0';   // 变量名沿用 SEA：它就是「背景开/关」那一位

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
   口径照 https://mimo.xiaomi.com/coder 那页：它不是"把东西推开"，是**擦除式显影** ——
   一个遮罩被光标擦出洞来，洞随笔画速度从约 8px 长到约 128px，亮点不残留、约 520ms 内淡完。
   所以这里每颗星只有一个 `lit`(0..1)：光标经过就充到 1，之后按秒指数衰减；
   **只有 lit 够亮的星才画** ⇒ 静止时整片天空是空的，划过才出现一条星带。

   三条硬约束仍然一条不丢：
     · 静止时逐像素完全相同：能量归零时把所有 lit 强制写回 0、位置写回 home 再画一帧
       ⇒ 显影过又淡掉的终点与初始帧是同一张图（探针逐像素比这个）。
     · 衰减与弹簧都按**秒**积分（乘 dt），不按帧 —— 按帧写在低帧率下会"永远淡不干净"。
     · 指针「瞬移」不算划过，且**按速度判**（>4200px/s 或距上一拍 >250ms），
       不能按固定像素：正常快扫一步就 48~58px，按像素判会把整层背景判成"对鼠标没反应"。
   没有 WebGL、没有噪声函数：一张 2D 画布 + 每颗星一个 home/位移/速度/亮度。 */
function mul32(a){return()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);
  t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
const ST={cv:null,g:null,w:0,h:0,list:[],pairs:[],raf:0,t0:0,frames:0,
          peak:0,lit:0,strokes:0,bursts:0,rings:[],C:[],LC:'#b489ff',
          AMB:0.10,          // 常驻星点占比的亮度；想要"完全只有经过才亮"就把它设成 0
          RMIN:9,RMAX:130,   // 显影半径：随笔画速度从 9px 长到 130px（参考页 8→128）
          DECAY:4.6,         // 亮度衰减 /秒 ⇒ 520ms 后只剩 9%
          SPRING:34,DAMP:4.2,EPS:0.12,LIT_EPS:0.012,
          last:null,lastT:0,pend:null};
function starColors(){
  const cs=getComputedStyle(document.documentElement);
  const g=n=>(cs.getPropertyValue(n)||'').trim();
  ST.C=[g('--s-1')||'#f6e7d3',g('--s-2')||'#cfe6ff',g('--s-3')||'#ffd6a5',g('--s-4')||'#ff9ecb'];
  ST.LC=g('--s-link')||'#b489ff';
}
function starsBuild(){
  const R=mul32(20260929);                    // 同种子 ⇒ 刷新后星位不变，不会"每次进来换一片天"
  const w=ST.w, h=ST.h;
  const n=Math.round(Math.min(2800,Math.max(900,w*h/620)));   // 密：1440×900 下约 2100 颗
  ST.list=[];
  const gx=w*0.04, gy=h*1.08, dx=w*0.96, dy=-h*0.84;          // 一条斜着的银河带
  for(let i=0;i<n;i++){
    let x,y;
    if(i<n*0.66){ const t=R(), o=(R()-0.5)*w*0.26;
      x=gx+dx*t+o; y=gy+dy*t+(R()-0.5)*w*0.15; }
    else { x=R()*w; y=R()*h; }
    const z=0.34+R()*0.66;
    const big=R()<0.045+z*0.05;
    ST.list.push({hx:x,hy:y,x:x,y:y,vx:0,vy:0,z:z,big:big,lit:0,
      amb:(i%41===0? ST.AMB*(0.5+R()*0.5) : 0),   // 极少数几颗常驻，免得整页像坏了
      r:(big?1.0:0.28)+R()*(big?1.5:0.9)*(0.6+z*0.7),
      a:Math.min(1,(big?0.80:0.42)+R()*(big?0.20:0.45)*(0.6+z*0.6)),
      c:ST.C[(R()*ST.C.length)|0]});
  }
  /* 星座连线只算一次（建表时），每帧按当前亮度画：两端都亮才连线 ⇒
     划过时会"连出"一片星座，走开就整条一起淡掉。 */
  ST.pairs=[];
  const far=ST.list.filter(t=>t.z>0.72), lim=Math.min(150,w*0.10);
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
}
function vis(st){ return Math.max(st.lit, st.amb); }
function starsDraw(){
  const g=ST.g; if(!g) return;
  g.clearRect(0,0,ST.w,ST.h);
  g.lineWidth=0.75; g.strokeStyle=ST.LC;
  for(const [a,b,rest] of ST.pairs){
    const v=Math.min(vis(a),vis(b));
    if(v<0.30) continue;                       // 两端都亮才连：显影区里才出现星座
    const d=Math.hypot(b.x-a.x,b.y-a.y), over=Math.abs(d-rest)/Math.max(1,rest);
    const al=Math.max(0,0.40-over*0.75)*v*2.2;
    if(al<0.012) continue;
    g.globalAlpha=Math.min(0.52,al);
    g.beginPath(); g.moveTo(a.x,a.y); g.lineTo(b.x,b.y); g.stroke();
  }
  for(const st of ST.list){
    const v=vis(st);
    if(v<0.014) continue;                      // 静止时几乎一颗都不画 —— 这就是"只有经过才显示"
    g.globalAlpha=st.a*v; g.fillStyle=st.c;
    g.beginPath(); g.arc(st.x,st.y,st.r,0,6.2832); g.fill();
    if(st.big&&v>0.25){
      g.globalAlpha=st.a*v*0.16;
      g.beginPath(); g.arc(st.x,st.y,st.r*3.6,0,6.2832); g.fill();
      g.globalAlpha=st.a*v*0.5; g.strokeStyle=st.c; g.lineWidth=0.65;
      g.beginPath(); g.moveTo(st.x-st.r*4.2,st.y); g.lineTo(st.x+st.r*4.2,st.y);
      g.moveTo(st.x,st.y-st.r*4.2); g.lineTo(st.x,st.y+st.r*4.2); g.stroke();
      g.lineWidth=0.75; g.strokeStyle=ST.LC;
    }
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
  for(const st of ST.list){
    const dx=st.x-x, dy=st.y-y, d2=dx*dx+dy*dy;
    if(d2>R2) continue;
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
  document.body.classList.toggle('plain',!SEA);
  $('#bSea').textContent='星辰 · '+(SEA?'开':'关');
  if(!SEA){
    if(ST.raf){ cancelAnimationFrame(ST.raf); ST.raf=0; }
    ST.rings.length=0;
    if(ST.g) ST.g.clearRect(0,0,ST.w,ST.h);
    return;
  }
  if(!ST.cv){
    ST.cv=document.querySelector('#stars'); ST.g=ST.cv.getContext('2d');
    if(!ST.g) return;
    window.addEventListener('resize',()=>{ starColors(); starsResize(); });
  }
  starColors(); starsResize(); starsStart();
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
  $$('#cards .appr').forEach(cb=>cb.onchange=e=>
    e.target.closest('.signbox').classList.toggle('on', e.target.checked));
  // 悬停阶段卡 → 左轨那颗状态点跟着亮：省掉"这行对应上面哪个点"的眼力活
  $$('#cards .stage').forEach((el,i)=>{
    el.addEventListener('mouseenter',()=>{ const k=el.querySelector('.skey').textContent;
      const d=document.querySelector('.step .dot[title="'+k+'"]'); if(d) d.classList.add('hot'); });
    el.addEventListener('mouseleave',()=>{ [...document.querySelectorAll('.dot.hot')]
      .forEach(d=>d.classList.remove('hot')); });
  });
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
  if(j.state!=='running'){ clearInterval(timer); timer=null; curJob=null; await apiState(); }
}
$('#bFollow').onclick=e=>{ follow=!follow; e.target.textContent=follow?'跟随最新':'已暂停跟随'; };
$('#bClear').onclick=()=>{ LINES=[]; $('#log').textContent=''; };
$('#chips').onclick=e=>{ const b=e.target.closest('.chip'); if(!b) return;
  FILT=b.dataset.f; $$('#chips .chip').forEach(x=>x.classList.toggle('on',x===b)); renderLog(); };
$('#bForce').onclick=e=>{ force=!force; e.target.textContent=force?'缓存：已绕过（重跑暂存档）':'缓存：按指纹复用';
  e.target.style.borderColor=force?'var(--await)':''; };
$('#bHelp').onclick=()=>$('#help').classList.add('on');
/* 键位：这类界面要反复切步骤、反复跑同一件事，摸熟键盘比找按钮快。
   输入框里打字时一律不劫持。 */
document.addEventListener('keydown',e=>{
  // e.target 不一定是元素（在 document 上 dispatch 时就是 document，没有 .matches）——
  // 上一版直接 e.target.matches(...) 抛异常，整条键位连同 Esc 一起失效，
  // 抽屉关不掉 ⇒ 那层全屏遮罩把"背景可见区"挤成 0 像素，五条背景判据跟着全塌。
  const t=e.target;
  if(t && t.matches && t.matches('input,textarea,select')) return;
  const k=(e.key||'').toLowerCase();
  if(k==='escape'){ $('#help').classList.remove('on'); $('#lightbox').classList.remove('on'); return; }
  if(k>='1'&&k<='4'&&Number(k)<=Object.keys((S&&S.steps)||{}).length){
    step=Number(k); render(); e.preventDefault(); return; }
  if(k==='h'){ $('#help').classList.toggle('on'); }
  else if(k==='s'){ $('#bSea').click(); }
  else if(k==='p'){ if(!S||S.running) return; post({plan:true}); }
  else if(k==='r'){ if(!S||S.running) return; ctaRun(step===1?'diff':step===3?'review'
                    :step===4?'swap':'tocheck'); }
});
$$('#help [data-close]').forEach(el=>el.onclick=()=>$('#help').classList.remove('on'));

document.addEventListener('click',e=>{ if(e.target.matches('.sheets img')){
  $('#lightbox img').src=e.target.src; $('#lightbox').classList.add('on'); e.preventDefault(); } });
$('#lightbox').onclick=e=>e.currentTarget.classList.remove('on');
seaApply(); apiState();
let pollT=setInterval(()=>{ if(!timer) apiState(); },8000);
/* 验收钩子：逐像素比对期间必须能停掉 8 秒轮询——轮询里的 render() 会重建阶段卡，
   卡片带着入场动画（opacity 0→1 + 上移），两张照片之间一旦插进一次轮询，
   比的就不是"背景渗没渗进来"而是"卡片淡入到哪一帧了"（实测假红 75）。 */
window.__probe={stop(){ if(pollT){ clearInterval(pollT); pollT=null; } },
                go(n){ step=n; render(); }, state(){ return S; }};
window.ST=ST; window.panelState=()=>S;
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
