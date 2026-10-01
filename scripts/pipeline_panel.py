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
   两条铁律：
   ① **一个颜色只表示一件事**。颜色只属于「状态」（未跑/判绿/判红/等你签字/在跑），
      阶段档位一律用文字+图标。
   ② **深色仪表盘的正经分层法：表面阶梯 + 发丝线 + 零投影。**
      参照物是两个公开设计系统的实测 token（Linear / Raycast），它们的规则里
      逐条点到了更早那版的病：
        · "Don't use lavender as a section background or card fill" ⇒ 旧版
          `--pane:#12101f / --card:#181527 / --deep:#150d1f` 全是薰衣草底；
        · "The brand resists drop shadows almost entirely, leaning on tonal lifts
          and subtle top-edge highlights" ⇒ 旧版每个面板挂 `0 22px 46px -32px`；
        · "Don't introduce a second chromatic accent / Don't add atmospheric
          gradients" ⇒ 旧版紫+品红+青三彩并用，还在每块面板顶边画了一道
          紫→品红的渐变"灯管"。
      ⇒ 现在：**海军蓝**五档表面阶梯（色相压在 215° 一带，与背景那片夜航星野同源）、
      1px 实色发丝线、投影全部换成 `inset` 顶边微高光、
      **唯一的 chrome 强调色 = 蓝白**（`--brand`），氛围只交给背景的星野。
      五个状态色 idle/pass/fail/await/run **一个都不动**——那是语义不是配色，
      探针逐条比它们的计算 rgb，改一个字都算红。
   所有可视量都走变量，于是更早那套薰衣草版面整体挂在 `body.legacy` 上，
   `V` 键当场对照。 */
:root{
  /* 表面阶梯（同构 Linear 的 5 档，色相压到 215° 的海军蓝，不偏紫） */
  --abyss:#04070d; --deep:#070c15; --pane:#0b1322; --card:#101a2c; --raise:#16243a;
  --head:#060b14;
  /* 发丝线：实色、1px、三档，冷蓝灰 */
  --line:#1a2740; --line2:#26375a; --line3:#3a5382;
  /* 文字坡：冷灰偏蓝 */
  --txt:#e9eef8; --txt2:#b3bfd5; --dim:#7b879f; --dim2:#586279;
  --idle:#3f5a6e; --pass:#4fd6a8; --fail:#ff6f6f; --await:#f2bd72; --run:#5fd0e8;
  --brand:#cfe0ff;          /* 唯一的 chrome 强调色：蓝白（与夜航星野同源） */
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
   上一版是"东京夜"：三团不动的城市光晕（橙/紫/青）当底 + 显影式星点（划过才亮、
   520ms 淡净、静止时全黑）。那三团光晕是**第二、第三、第四个彩**，正是"AI 味"
   的来源；显影式星点则让天在 99% 的时间里等于不存在。
   ⇒ 现在：光晕全删，换成**底边一条极淡的地平线雾**（给"夜"一个落脚点，静态）；
   星点改成**常驻 + 极慢视差漂移**，亮度全局封顶（见 JS 的 `ST.DIM`），
   可读性另外还靠主屏文字区的 avoid 矩形。天从此一直在，且它是状态面。
   星云单独一张**永不重绘**的画布：它整幅是静态的，跟着星点画布每帧 clearRect 再 blit
   一次等于白拷 6MB/帧（SwiftShader 上实测拖慢截图到 2s+）。 */
#bgfx{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
/* 地平线雾：`::before` 排在两张画布之前 ⇒ 在星点之下，只给底边垫一层空气。 */
#bgfx::before{content:'';position:absolute;left:0;right:0;bottom:0;height:34vh;
  pointer-events:none;
  background:linear-gradient(180deg,transparent,rgba(120,150,210,.055) 62%,
    rgba(150,170,215,.03) 100%)}
#bgfx canvas{position:absolute;inset:0;width:100%;height:100%}
body.plain #bgfx::before,body.plain #bgfx #nebula{display:none}

/* 指针光晕：一团极淡的冷白光跟着指针走（B 方向保留的那一条）。
   压在 `#bgfx` 之上、`.app` 之下 ⇒ **天然进不了数据面**：抽屉、日志 `pre`、
   对照图都是不透明面板，光晕在它们底下，一个像素都渗不进去。 */
#pool{position:fixed;z-index:0;pointer-events:none;width:520px;height:520px;left:0;top:0;
  margin:-260px 0 0 -260px;border-radius:50%;opacity:0;
  background:radial-gradient(closest-side,rgba(180,205,255,.075),transparent 100%);
  transition:opacity .3s var(--ez)}
body.plain #pool,body.calm #pool,body.nopool #pool{display:none}

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
   隐喻只有一句：**光由指针携带**。这一版把上版那套"每个控件绕一圈的边框跑光 +
   磁吸位移"删了 —— 一次 hover 四个动作同时开火，吵，而且 conic 渐变绕边本身就是
   最典型的"AI 加的特效"。现在只剩两件事：
     · 一团极淡的光晕跟着指针（`#pool`，在 `.app` 之下 ⇒ 数据面天然吃不到）；
     · hover 时控件**离指针最近的那条边**亮起 1px（`#fxedge`）—— 像光打在实体件的棱上，
       不是绕着按钮跑一圈。
   三条纪律，一条都不能破：
     · 全部**指针驱动**，没有一条常驻循环（常驻的只有背景那层，且它在 `calm` 下冻结）。
     · 只上**控件**（按钮 / 步骤块 / 筛选片 / 签字框）；日志 `pre`、对照图、指标 pill
       这些**数据面一个都不放过光**。
     · `body.calm`（M 键）整层停用，用来当场对比"这层到底值不值"。 */
#fxedge{position:fixed;z-index:70;pointer-events:none;display:none;opacity:0;overflow:hidden;
  transition:opacity .18s var(--ez)}
body:not(.calm) #fxedge.on{display:block;opacity:.85}
#chipmark{position:absolute;bottom:-1px;height:2px;border-radius:2px;left:0;width:0;
  background:var(--brand);opacity:0;pointer-events:none;
  transition:left .34s var(--ez),width .34s var(--ez),opacity .2s var(--ez)}
#chips{position:relative}

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
.pact:hover{background:var(--brand-hi);border-color:var(--brand-hi)}
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

/* ══ 底部步骤条：一根会**长过去**的进度线 + 四个节点 ══════════════════
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
.warn{background:rgba(255,111,111,.10);border:1px solid rgba(255,111,111,.34);
  border-radius:var(--r-ctl);
  padding:9px 12px;font-size:12.5px;color:#ffc2c2;margin-bottom:11px;display:none}
.warn.on{display:block}
#lightbox{position:fixed;inset:0;background:rgba(2,7,12,.95);display:none;z-index:99;
  align-items:center;justify-content:center;cursor:zoom-out}
#lightbox.on{display:flex}
#lightbox img{max-width:96vw;max-height:96vh;object-fit:contain}
/* ── M 键「动效从简」：整层光效停用、背景星野冻结，但**状态指示一个都不跟着没** ──
   #stepfill 表达的是"当前在哪一步"，那是信息不是装饰 ⇒ 只掐它的位移，不掐它本身。 */
body.calm #fxedge{display:none!important}
body.calm #stepfill,body.calm #chipmark{transition:none}
body.calm .stage::before{transform:none!important}
body.calm .signbox.on::after{display:none}
@media (max-width:1080px){#detail .body{grid-template-columns:1fr;overflow:auto}
  .now{padding:0 var(--s5)} .steps{padding-left:var(--s5);padding-right:var(--s5)}
  .ask{font-size:clamp(26px,6.2vw,38px)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head><body>

<div id="bgfx" aria-hidden="true">
  <canvas id="nebula"></canvas><canvas id="stars"></canvas></div>
<i id="pool" aria-hidden="true"></i>

<div class="app">
<header>
  <div class="brand">
    <svg width="22" height="22" viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <path d="M17.4 2.6l1.5 4.3 4.3 1.5-4.3 1.5-1.5 4.3-1.5-4.3L11.6 8.4l4.3-1.5z"
            fill="#cfe0ff"/>
      <circle cx="5.4" cy="6.6" r="1.1" fill="#eef4ff"/>
      <circle cx="10.2" cy="12.4" r=".8" fill="#fff2df" opacity=".9"/>
      <circle cx="3.6" cy="14.2" r=".7" fill="#dbe6f7" opacity=".7"/>
      <path d="M1 21.4c2.2 0 2.2-2 4.4-2s2.2 2 4.4 2 2.2-2 4.4-2 2.2 2 4.4 2 2.2-2 4.4-2"
            stroke="#f2bd72" stroke-width="1.2" stroke-linecap="round" fill="none" opacity=".5"/>
    </svg>
    <div><h1>资产更新控制台</h1></div>
  </div>
  <div class="act">
    <button id="bDetail" class="ghost" title="D：展开证据（13 个阶段 / 日志 / 对照表 / 指纹）">细节</button>
    <button id="bSea" class="ghost" title="S：星野背景 开/关">星辰 · 开</button>
    <span class="kbd" title="1-4 切步骤 · R 跑当前这一步 · D 细节 · P 只看计划 · H 帮助 · Esc 关闭 · S 背景 · M 动效从简 · V 新旧配色">
      <b>1-4</b> 步骤 · <b>R</b> 跑 · <b>D</b> 细节</span>
    <button id="bHelp" class="help">怎么用</button>
  </div>
</header>

<div id="warn" class="warn"></div>

<!-- 主屏：一句话 + 一个行动。整页只回答"现在该做什么"。 -->
<main class="now">
  <p class="eyebrow" id="eyebrow"><i></i><span id="eyebrowTx">正在读盘…</span></p>
  <h2 class="ask" id="ask">—</h2>
  <p class="why" id="why">—</p>
  <div class="do" id="cta"></div>
  <p class="foot" id="scopeNote"></p>
</main>

<!-- 底部：一根会长过去的进度线 + 四个节点，节点上带该步全部阶段的状态方块 -->
<nav class="steps" id="stepsbar" aria-label="四个步骤">
  <span class="track"><i class="fill" id="stepfill"></i></span>
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

<i id="fxedge"></i>

<div id="help"><div class="veil" data-close></div><div class="panel">
  <button class="close ghost" data-close>关闭 ✕</button>
  <h3 style="margin-top:0">这是什么</h3>
  <p><b>资产更新控制台</b>把你游戏更新之后要做的那一串事，按四步排成一条主线。
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
  <code>P</code> 只看计划 · <code>H</code> 开关本抽屉 · <code>Esc</code> 关掉弹层 ·
  <code>S</code> 开关星野背景 · <code>M</code> 开关「动效从简」（把指针光晕与棱边光
  整层停用，<b>并冻结背景星野</b>，只留状态本身）· <code>V</code> 开关「新旧版面对照」
  （新版面=海军蓝阶梯+发丝线+零投影，旧版=薰衣草底+渐变灯管+投影），两个选择都会记住。</p>

  <h3>版面为什么长这样</h3>
  <p>深色仪表盘的正经分层法只有一条：<b>底色抬档 + 1px 发丝线 + 顶边一道微高光，不用投影</b>。
  参照的是两个公开设计系统的实测 token，它们的规则里逐条点到上一版的病：
  「别拿薰衣草色当分区底色或卡片填充」「几乎不用 drop shadow，纵向层级全靠色阶与描边」
  「别引入第二种强调色」「别加氛围渐变」。</p>
  <p>所以：五档<b>海军蓝</b>表面阶梯（色相压在 215° 一带，与背景那片夜航星野同源，
  不是中性冷灰也不是薰衣草）、发丝线三档实色、圆角按 4/6/8/12 分档、
  间距走 4 的倍数栅格、小标签不再全大写加宽字距、
  chrome 强调色<b>只有一个</b>蓝白（主动作用它，签字按钮借用「等你签字」那个琥珀，
  语义自洽）。氛围全部交给背景那片星野，面板上一分都不给。
  <b>五个状态色一个都没动</b>——那是语义不是配色。</p>

  <h3>背景与光效</h3>
  <p>夜航星野，<b>常驻</b>：天一直在，只是很暗（亮度全局封顶，像夜里抬头）。三层视差以
  0.35 / 0.7 / 1.4 px·s⁻¹ 极慢漂移，银河带上的星沿带轴走，带外水平漂并环绕 ——
  带子不会被撕开，边缘也不会突然跳出一颗。每颗星是<b>预渲染的精灵</b>：
  高斯核 + 按星随机旋转的锥形衍射芒，亮星六芒带淡色晕，暗星只是软边微点；
  亮度按幂律分布（亮星不到 1%），颜色按<b>色温</b>（蓝白→白→淡金）而不是糖果色。
  这片天还是<b>状态面</b>：当前那一步的正上方，星点亮度抬起来（信标列）；某个阶段判绿，
  就从信标处荡开一圈很淡的波。主屏大字底下<b>不画星</b>，可读性靠避让而不是蒙纱。</p>
  <p>光效只有两件事，全部由指针驱动：一团极淡的光晕跟着指针，以及 hover 时控件
  <b>离指针最近的那条边</b>亮起 1px（像光打在实体件的棱上，不是绕按钮跑一圈）。
  觉得干扰：<code>S</code> 关整片星野，<code>M</code> 连光晕一起关并冻结背景，
  <code>V</code> 换回旧版面对照，三个都会记住。
  想让天更亮/更暗，改 <code>ST.DIM</code> 这一个数就行；想让漂移更快，改 <code>ST.DRIFT</code>。</p>

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

/* ── 背景：夜航星野 —— 天一直活着，且它有职责 ──────────────────────────
   上一版是"显影式"：静止全黑、光标划过才亮、约 520ms 淡净。三条问题：
     · 它是**死的** —— 静止时屏幕上什么都没有，鼠标一停就"关灯"，星空只在被摸到的一瞬存在；
     · 它和**任务无关** —— 星星亮不亮跟"哪个阶段过了"毫无关系，纯装饰，
       这正是它读起来像"AI 加的太空背景"的原因；
     · 它上面还叠了四层同时开火的效果（边框跑光 + 柔光团 + 磁吸位移 + 涟漪）。
   这一版改三件事（B 方向「夜航」）：
     ① **常驻**：每颗星有自己的基准亮度（幂律分布，暗星是绝对多数），全局封顶 `DIM`；
     ② **漂移**：三层视差 0.35 / 0.7 / 1.4 px·s⁻¹。银河带上的星**沿带轴**漂（参数 tb 取模），
        带外的按水平漂并环绕 —— 这样带子永远不会被撕开，边缘也不会"啪"地跳出一颗；
     ③ **有职责**：当前那一步正上方，星点亮度抬起来（信标列）；某个阶段判绿 ⇒
        一圈极淡的波从信标处荡开。天从此是**状态面**。
   ⚠️ 代价必须说清：这版天空**永不静止**，上一版"静止两帧逐像素相同"那条探针判据不再成立。
      换成的判据是「冻结态（M）逐像素相同 + 漂移有界且慢 + 内容区跨轮询逐像素相同」，
      见 `scripts/diag/panel_ui_probe.py`。自绘还限流到 `FPS`：漂移极慢，不需要 60 帧。
   仍然没有 WebGL、没有噪声函数：一张 2D 画布 + 一张预渲染精灵图集。 */
function mul32(a){return()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);
  t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
const ST={cv:null,g:null,w:0,h:0,list:[],pairs:[],neb:null,raf:0,t:0,acc:0,frames:0,lastDraw:0,
          bursts:0,rings:[],C:[],LC:'#9aa4c8',
          DIM:0.62,          // 全局亮度封顶：夜里抬头那种亮度，大字底下也读得清
          FPS:20,            // 自绘帧率：漂移 ≤1.4px/s，20 帧足够顺
          DRIFT:[0.35,0.7,1.4],   // 三层视差速度 px/s（层速差 = 深度感）
          PTR:300,           // 指针软性提亮半径（按距离平方衰减，不是硬圆盘）
          band:null,beacon:null,ptr:{x:-9999,y:-9999},
          LINK_A:0.16,        // 星座连线的 alpha 上限（旧版 0.52 太像连点图）
          frozen:false,       // 冻结位（见 freezeSky）：钉住天，供逐像素比对
          last:null,avoid:[]};
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
  const R=mul32(20261001);                   // 同种子 ⇒ 刷新后星位不变，不会"每次进来换一片天"
  const w=ST.w, h=ST.h;
  /* 常驻星野的星数要比"显影式"克制：上一版 3200 颗只在划过时画一小片，
     现在**每颗每帧都要画**，得按真实开销定价。 */
  const n=Math.round(Math.min(1600,Math.max(700,w*h/2400)));
  ST.list=[]; ST.pairs=[];
  const gx=w*0.04, gy=h*1.08, dx=w*0.96, dy=-h*0.84;          // 一条斜着的银河带
  const len=Math.hypot(dx,dy);
  ST.band={gx:gx,gy:gy,dx:dx,dy:dy};
  for(let i=0;i<n;i++){
    const band=i<n*0.62, layer=i%3;
    /* 亮度按**幂律**分：真实天区里暗星是绝对多数。hero <0.5%、star ~9%。 */
    const u=R();
    const kind = u>0.995 ? 'hero' : u>0.905 ? 'star' : 'dust';
    const z=0.34+R()*0.66;
    const sz = kind==='hero' ? 46+R()*40 : kind==='star' ? 16+R()*18 : 3.0+R()*3.2;
    const a  = kind==='hero' ? 0.74+R()*0.26 : kind==='star' ? 0.30+R()*0.32 : 0.10+R()*0.24;
    // 色温与亮度相关：暗尘偏蓝白，只有亮星才允许走到暖端
    const ci = kind==='dust' ? (R()<0.80?0:1) : kind==='star' ? (R()*3|0) : (R()*4|0);
    const st={band:band,layer:layer,kind:kind,z:z,sz:sz,a:a,c:ci,lit:0,
      rot:R()*6.2832, ph:R()*6.2832, tw:0.5+R()*1.2, x:0,y:0,v:0};
    if(band){
      /* 带上的星**沿带轴**漂：只存参数 tb∈[0,1) 与垂直抖动 ox/oy，位置每帧现算。
         换成"横移 + 环绕"会把这条斜带切成两截（出左边的星带着带轴的 y 回到右边）。 */
      st.tb=R(); st.ox=(R()-0.5)*w*0.24; st.oy=(R()-0.5)*w*0.13;
      st.dv=ST.DRIFT[layer]/len;             // 每秒推进的 tb 比例
      st.hx=gx+dx*st.tb+st.ox; st.hy=gy+dy*st.tb+st.oy;
    } else {
      st.hx=R()*w; st.hy=R()*h;
      st.dv=ST.DRIFT[layer];                 // 带外：水平漂 px/s
    }
    ST.list.push(st);
  }
  /* 星座连线只算一次（建表时），每帧按当前亮度画：两端都亮才连线。
     上限 0.16 alpha、线宽 0.6 —— 上一版 0.52 的紫线是"连点图"观感的主因。 */
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
   烘成一张静态位图，每帧一次 drawImage；它不吃"冻结帧必须可复现"这条（它本来就不动）。 */
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
  for(let i=0;i<30;i++){
    const t=R(), o=(R()-0.5)*w*0.20;
    const s=180+R()*340, al=0.018+R()*0.030;
    g.globalAlpha=al;
    g.drawImage(SPR.cloud[R()<0.72?0:1], gx+dx*t+o-s/2, gy+dy*t+(R()-0.5)*w*0.11-s/2, s, s);
  }
  g.globalAlpha=1;
}
/* 常驻可见度 = 基准亮度 × 慢闪 × 信标提亮 × 指针软提亮 × 点击余辉。
   ⚠️ 每一项都吃时间（闪烁、漂移）⇒「静止两帧逐像素相同」不再成立；
   换成的判据是「冻结态（CALM）逐像素相同」：冻结时 t 不再推进，整帧可复现。 */
function vis(st,t){
  let v=st.a*(0.86+0.14*Math.sin(t*st.tw+st.ph));
  const bc=ST.beacon;
  // 系数 1.20：列心提亮到 2.2×，列内均值约 1.5×全屏 —— 低于这个量级信标就只是
  // "碰巧有几颗亮星"，读不出"天在告诉你现在走到第几步"。
  if(bc){ const d=Math.abs(st.x-bc.x)/bc.half; if(d<1) v*=1+1.20*(1-d)*(1-d); }
  if(!CALM&&!ST.frozen){ const dx=st.x-ST.ptr.x, dy=st.y-ST.ptr.y, R=ST.PTR, d2=dx*dx+dy*dy;
    if(d2<R*R){ const f=1-d2/(R*R); v*=1+2.4*f*f; } }
  if(st.lit>0.001) v*=1+st.lit*1.5;
  return v;
}
/* 主屏文字区：装饰给它让路（同一条纪律，只是从"不在那儿显影"改成"不在那儿画"）。 */
function inAvoid(x,y){
  const av=ST.avoid; if(!av||!av.length) return false;
  for(const a of av) if(x>=a[0]&&x<=a[2]&&y>=a[1]&&y<=a[3]) return true;
  return false;
}
function starsDraw(t){
  const g=ST.g; if(!g) return;
  const w=ST.w, h=ST.h, B=ST.band;
  g.clearRect(0,0,w,h);            // 星云在另一张画布上，这里只画会动的部分
  for(const st of ST.list){        // 先算这一帧每颗星的位置与可见度（连线要复用，别算两遍）
    if(st.band){ const tb=(st.tb+t*st.dv)%1;
      st.x=B.gx+B.dx*tb+st.ox; st.y=B.gy+B.dy*tb+st.oy; }
    else { st.x=((st.hx+t*st.dv)%(w+120))-60; st.y=st.hy; }
    st.v=inAvoid(st.x,st.y)?0:vis(st,t);
  }
  g.lineWidth=0.6; g.strokeStyle=ST.LC;
  for(const [a,b,rest] of ST.pairs){
    const v=Math.min(a.v,b.v);
    if(v<0.50) continue;                       // 两端都够亮才连
    if(inAvoid((a.x+b.x)/2,(a.y+b.y)/2)) continue;
    const d=Math.hypot(b.x-a.x,b.y-a.y), over=Math.abs(d-rest)/Math.max(1,rest);
    const al=Math.max(0,ST.LINK_A-over*0.30)*Math.min(1,v);
    if(al<0.006) continue;
    g.globalAlpha=Math.min(ST.LINK_A,al);
    g.beginPath(); g.moveTo(a.x,a.y); g.lineTo(b.x,b.y); g.stroke();
  }
  for(const st of ST.list){
    if(st.v<=0) continue;
    const al=Math.min(ST.DIM, st.a*st.v); if(al<0.008) continue;
    const spr=SPR[st.kind] && SPR[st.kind][st.c]; if(!spr) continue;
    const s=st.sz; g.globalAlpha=al;
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
  starsBuild(); starsDraw(ST.t);
}
/* 常驻循环：漂移 ≤1.4px/s，20 帧足够顺，所以把重绘限流到 `FPS`，
   中间那些 rAF 只累加时间 —— 常驻不等于要烧满 60 帧。 */
function starsFrame(ts){
  const dt=ST.last?Math.min(0.1,(ts-ST.last)/1000):1/60; ST.last=ts;
  ST.t+=dt; ST.acc+=dt;
  if(ts-ST.lastDraw < 1000/ST.FPS){ ST.raf=requestAnimationFrame(starsFrame); return; }
  const ad=ST.acc; ST.acc=0; ST.lastDraw=ts;
  for(const r of ST.rings){ r.r+=r.v*ad; r.a-=ad*1.6; }
  ST.rings=ST.rings.filter(r=>r.a>0.02);
  const ld=Math.exp(-2.6*ad);
  for(const st of ST.list){ if(st.lit>0.0005) st.lit*=ld; else st.lit=0; }
  ST.frames++; starsDraw(ST.t);
  ST.raf=requestAnimationFrame(starsFrame);
}
function starsStart(){ if(!ST.raf && SEA && !CALM && !ST.frozen){ ST.last=0; ST.acc=0; ST.raf=requestAnimationFrame(starsFrame); } }
/* ── 冻结位：把天停在**当前这一帧**，用于逐像素比对（漂移常开 ⇒ 没有别的办法拿到可比的两帧）。
   与 `CALM` 的区别只有一个：它**不碰光效层** —— 探针要一边冻结背景、一边验棱边光。
   产品里没有单独暴露这个开关，只有 M 键会同时置上两者（见 calmApply）。 */
function freezeSky(on){
  ST.frozen=!!on;
  if(ST.frozen){ if(ST.raf){ cancelAnimationFrame(ST.raf); ST.raf=0; } if(ST.g) starsDraw(ST.t); }
  else starsStart();
}
/* 指针只做两件事：挪软提亮中心、按下时在落点荡一圈波并给附近星点余辉。
   不再有"划过才显影"的逐星循环 —— 天本来就是亮的，指针只是把它提亮一点。 */
function starMove(x,y){ if(!SEA) return; ST.ptr.x=x; ST.ptr.y=y; }
window.addEventListener('pointermove',e=>{ starMove(e.clientX,e.clientY); },{passive:true});
window.addEventListener('pointerdown',e=>{
  if(!SEA||CALM) return;
  ST.ptr.x=e.clientX; ST.ptr.y=e.clientY; ST.bursts++;
  ST.rings.push({x:e.clientX,y:e.clientY,r:5,v:520,a:0.34,c:'#cfe0ff'});
  const R=ST.PTR, R2=R*R;
  for(const st of ST.list){ const dx=st.x-e.clientX, dy=st.y-e.clientY, d2=dx*dx+dy*dy;
    if(d2<R2){ const f=(1-d2/R2)*0.85; if(f>st.lit) st.lit=f; } }
},{passive:true});
/* 指针离开窗口 ⇒ 提亮中心收走，否则那片"亮"会永远停在原处。 */
function ptrGone(){ ST.ptr.x=ST.ptr.y=-9999; }
window.addEventListener('blur',ptrGone);
document.addEventListener('pointerleave',ptrGone);
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

/* ── 光效引擎：光由指针携带 ────────────────────────────────────────────
   这一版只剩两件事（上版那套"边框绕一圈跑光 + 控件内柔光 + 磁吸位移"全删了）：
     ① 光晕 —— 一团极淡的冷白光跟着指针（`#pool`）。它压在 `.app` 之下，
        而抽屉 / 日志 `pre` / 对照图 / 指标 pill 全是不透明面板 ⇒ **数据面天然吃不到光**，
        不再需要靠"挑选择器"来挡。
     ② 棱边光 —— hover 时控件**离指针最近的那条边**亮起 1px（`#fxedge`），
        像光打在实体件的棱上；颜色跟着**语义**走：主动作=蓝白、签字=琥珀、其余中性。
   按下仍然把光泄进背景星野（往星野里打一圈该控件颜色的涟漪），
   于是"点界面"和"那片天"还是同一套物理，而不是两层各演各的。
   实现上是**全局单例浮层**搬到目标控件的矩形上 —— 控件全是 render() 重建出来的，
   往节点里塞子元素或类名都会在重建时丢。 */
let CALM = localStorage.getItem('panel.calm')==='1';
/* V 键：新版面（海军蓝阶梯、零投影）↔ 旧版面（薰衣草底 + 渐变灯管 + 投影）当场对照。
   两条都留在 CSS 里，靠 `body.legacy` 切换 —— 他判"丑不丑"要能立刻比，
   静态对比图不如这个（同一台服务器、同一个进程、同一个鼠标位置）。 */
let LEGACY = localStorage.getItem('panel.legacy')==='1';
function legacyApply(){
  document.body.classList.toggle('legacy',LEGACY);
  if(ST.g){ starColors(); starsResize(); }        // 星点色板跟着版面走
  else starColors();
}
const FX={edge:$('#fxedge'),pool:$('#pool'),cur:null,last:null,pt:{}};
/* 步骤节点 `.snode` 不是"实体件"（没有边框、是个竖排的标签组），给它打棱边光很怪 ⇒ 排除。 */
const FXSEL='button:not(.snode),.signbox,.sheets a';
function fxTone(el){
  const c=el.classList;
  // 棱边光的颜色跟着**语义**走：主动作=蓝白，签字=等你签字的琥珀，其余中性。
  if(c.contains('go')) return 'rgba(207,224,255,.9)';
  if(c.contains('sign')||c.contains('signbox')) return 'rgba(242,189,114,.9)';
  if(c.contains('chip')||c.contains('mini')) return 'rgba(207,224,255,.55)';
  return 'rgba(214,224,242,.5)';
}
function fxOff(){ FX.edge&&FX.edge.classList.remove('on'); FX.cur=null; FX.k=null; }
function fxEnter(el,e){
  if(CALM||!FX.edge) return;
  const r=el.getBoundingClientRect();
  if(r.width<10||r.height<10||r.bottom<0||r.top>innerHeight) return;
  FX.cur={el:el,r:r}; fxMove(e);
}
/* 最近棱边：把指针在控件内的相对位置换算成四条边各自的距离，取最小那条。 */
function fxMove(e){
  if(e&&e.clientX!=null) FX.pt=e;
  const p=FX.pt; if(!FX.cur||CALM||p.clientX==null) return;
  const r=FX.cur.r, el=FX.cur.el, b=FX.edge;
  const nx=(p.clientX-r.left)/Math.max(1,r.width), ny=(p.clientY-r.top)/Math.max(1,r.height);
  const px=(Math.max(0,Math.min(1,nx))*100).toFixed(1), py=(Math.max(0,Math.min(1,ny))*100).toFixed(1);
  const d={t:ny,b:1-ny,l:nx,r:1-nx};
  const k=Object.keys(d).sort((a,c)=>d[a]-d[c])[0];
  FX.k=k;                       // 探针读它验"最近棱边"这条逻辑真的在跑
  const col=fxTone(el);
  b.style.left=r.left+'px'; b.style.top=r.top+'px';
  b.style.width=r.width+'px'; b.style.height=r.height+'px';
  b.style.borderRadius=getComputedStyle(el).borderRadius||'8px';
  b.style.background = k==='t' ? 'radial-gradient(58px 1px at '+px+'% 0,'+col+',transparent)'
    : k==='b' ? 'radial-gradient(58px 1px at '+px+'% 100%,'+col+',transparent)'
    : k==='l' ? 'radial-gradient(1px 58px at 0 '+py+'%,'+col+',transparent)'
    : 'radial-gradient(1px 58px at 100% '+py+'%,'+col+',transparent)';
  b.classList.add('on');
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
document.addEventListener('pointermove',e=>{
  if(FX.cur) fxMove(e);
  const p=FX.pool; if(!p) return;                          // 光晕：跟着指针，进出窗口即收
  p.style.transform='translate('+e.clientX+'px,'+e.clientY+'px)';
  p.style.opacity=(SEA&&!CALM)?'1':'0';
},{passive:true});
document.addEventListener('pointerdown',e=>{
  fxMove(e);
  const el=e.target.closest?e.target.closest(FXSEL):null;
  if(!el||CALM||!SEA) return;                 // 按下 = 把光泄进背景星野，颜色跟着控件走
  ST.rings.push({x:e.clientX,y:e.clientY,r:4,v:780,a:.5,c:fxTone(el)});
  ST.bursts++; starsStart();
},{passive:true});
addEventListener('scroll',()=>{ FX.last=null; fxOff(); },true);
function chipMark(){
  const on=$('.chip.on'), mk=$('#chipmark'); if(!on||!mk) return;
  mk.style.left=on.offsetLeft+'px'; mk.style.width=on.offsetWidth+'px'; mk.style.opacity='1';
}
/* M 键「动效从简」= 光效整层停用 + **背景星野冻结**。
   冻结不是"看不见"：t 停止推进后整帧可复现，探针正是拿这个当"没有失控动画"的证据。 */
function calmApply(){
  document.body.classList.toggle('calm',CALM);
  if(CALM) fxOff();
  freezeSky(CALM);
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
                              j.stages,j.steps,j.error]); }
  catch(e){ return String(Math.random()); }
}
async function apiState(force){
  let j=null;
  try{ j=await (await fetch('/api/state')).json(); }
  catch(e){ LOADERR=String(e); render(); setTimeout(apiState,2500); return; }
  LOADERR=''; LOADED=true; S=j; S.state=S.state||{};
  const ns=sigOf(j);
  if(!force && RENDERED && ns===SIG){          // 内容一个字节没变 ⇒ 一个节点都不碰
    if(S.running && !curJob) tail(S.running.id);
    return;
  }
  SIG=ns; render();
  if(S.running && !curJob) tail(S.running.id);
}
function stagesOf(n){ return (S.stages||[]).filter(s=>(s.step||0)===n); }
let LOADED=false, LOADERR='';
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

/* ── 星野避让：主屏大字与主按钮**不坐面板**，可读性靠"星点不在这些矩形里画"来保证。
   这是让装饰让步，不是给数据蒙一层纱 —— 蒙纱那条路实测 alpha .90 仍会被顶出 36 级差异。 */
function avoidRefresh(){
  const a=[];
  document.querySelectorAll('.eyebrow,.ask,.why,.do,.foot').forEach(e=>{
    const r=e.getBoundingClientRect();
    if(r.width>2&&r.height>2&&r.bottom>0&&r.top<innerHeight)
      a.push([r.left-34,r.top-26,r.right+34,r.bottom+26]);});
  ST.avoid=a;
  beaconRefresh();
}
/* ── 信标列：当前那一步节点的正上方，星点亮度抬起来 —— 天从此和任务有关。
   节点是 render() 重建出来的，所以每次 render / resize 都重取一次（挂在 avoidRefresh 上）。 */
function beaconRefresh(){
  const on=$('#stepsbar .snode.on')||$('#stepsbar .snode');
  if(!on){ ST.beacon=null; return; }
  const r=on.getBoundingClientRect();
  ST.beacon={x:r.left+r.width/2, half:Math.min(150,innerWidth*0.13)};
}
/* ── 判绿荡波：某个阶段从"没绿"变成"绿" ⇒ 从信标处荡开一圈极淡的波。
   这条是"天是状态面"的落地 —— 不是随便加个涟漪：只在**状态真的翻转**时才响。
   首帧不响（PASSWATCH 为空 ⇒ 没有"从 false 变 true"），所以刷新页面不会有假波。 */
let PASSWATCH={};
function passWatch(){
  const st=(S&&S.state)||{}; let hit=false;
  for(const k in st){ const now=statusOf(k)==='pass';
    if(now&&PASSWATCH[k]===false) hit=true;
    PASSWATCH[k]=now; }
  if(hit&&ST.beacon){
    ST.rings.push({x:ST.beacon.x,y:innerHeight*0.62,r:8,v:620,a:0.30,c:'#cfe0ff'});
    ST.bursts++; starsStart();
  }
}

/* ══ 主屏那句话是怎么推出来的 ══════════════════════════════════════════
   优先级写死、可核对，不靠"看起来顺眼"：
     正在跑 > 卡住了 > 等你签字 > 还没做 > 这一步过了
   13 个阶段各自的「写到哪儿 / 判据 / 上次结论」是**证据**，全在「细节」抽屉里；
   主屏只留决策：一句现状 + 一个动作 + 一行"点下去会发生什么"。 */
const STEPNAME={1:'接模拟器',2:'重新导出',3:'看图对比',4:'签字换入'};
function askOf(n){
  const all=S.stages||[], list=n===0?all:stagesOf(n), stn=k=>statusOf(k);
  const st=S.state||{}, eb='第 '+n+' 步 · '+STEPNAME[n]+' · 共 4 步';
  const fail=list.find(s=>stn(s.key)==='fail');
  const aw=list.filter(s=>stn(s.key)==='await');
  const idle=list.filter(s=>stn(s.key)==='idle');
  const nEm=v=>'<em data-n="'+v+'">'+v+'</em>';

  if(n===1){
    const pf=st.preflight, pl=st.pull;
    if(fail) return {eb, red:1, ask:esc(fail.key)+' 这一步没过',
      why:esc((pf&&fail.key==='preflight'?pf.detail:fail.key)+'：先看它为什么红。'),
      acts:[{a:'diff',t:'▶ 再查一次',k:'pact'},{a:'detail',t:'看细节',k:'link2'}]};
    if(pf&&!pf.ok) return {eb, red:1, ask:'权威输入缺东西，先别往下走',
      why:'inputs/azdata、inputs/gamecfg 与画廊 vendor 是重导的唯一起点，缺了跑出来的是错的。',
      acts:[{a:'diff',t:'▶ 再查一次',k:'pact'},{a:'detail',t:'看缺了哪些',k:'link2'}]};
    if(!pf) return {eb, ask:'先确认权威输入还在位',
      why:'只读地查一遍，不写任何东西。',
      acts:[{a:'diff',t:'▶ 预检 + 看差异',k:'pact'}]};
    const m=/新增 (\d+)\/变更 (\d+)/.exec((pl&&pl.detail)||'');
    if(!pl) return {eb, ask:'看看模拟器上多了什么',
      why:'只读地列一遍设备上的包、算出新增与变更，不下载。',
      acts:[{a:'diff',t:'▶ 看差异',k:'pact'}]};
    if(aw.length) return {eb, ask:'模拟器上有 '+nEm(+(m?m[1]:0))+' 个新包、'+nEm(+(m?m[2]:0))+
        ' 个变更还没拉到本地',
      why:'拉下来会写 files/AssetBundles。源包一旦被覆盖，旧版本本地就没有了——所以这一步要你签字。',
      acts:[{a:'pull',t:'⚑ 拉进本地',k:'pact sign'},{a:'diff',t:'重新算一遍差异',k:'link2'}]};
    return {eb, ask:'包已经在本地了', why:'下一步：从这些源包重算产物，全部先进暂存区。',
      acts:[{a:'next',t:'去第 2 步 →',k:'pact'},{a:'diff',t:'再算一遍差异',k:'link2'}]};
  }
  if(n===2){
    if(fail) return {eb, red:1, ask:esc(fail.key)+' 这一步没过',
      why:'它停在这里不往下跑。日志里有那行原因。',
      acts:[{a:'tocheck',t:'▶ 重跑到待确认',k:'pact'},{a:'detail',t:'看日志',k:'link2'}]};
    if(idle.length===list.length) return {eb, ask:'从源包重算 '+nEm(list.length)+' 类产物',
      why:'立绘 / Spine / Live2D 只写暂存区；依赖表、元数据、语音、CG 要你签字才动正式区。要跑一会儿。',
      acts:[{a:'tocheck',t:'▶ 开始重导',k:'pact'}]};
    if(aw.length) return {eb, ask:'重导好了 '+nEm(list.length-idle.length)+' / '+nEm(list.length)+
        ' 项，其中 '+nEm(aw.length)+' 项要你签字才写正式区',
      why:'没签字的那几项只算了差异，正式区一个字节没碰。勾上签字再跑才会覆盖。',
      acts:[{a:'tocheck',t:'▶ 重跑到待确认',k:'pact'},{a:'staged',t:'只重跑导出三件',k:'link2'}]};
    if(idle.length) return {eb, ask:'重导跑好了 '+nEm(list.length-idle.length)+' 项，还剩 '+nEm(idle.length)+' 项',
      why:'继续跑会把剩下的算完。',
      acts:[{a:'tocheck',t:'▶ 跑完剩下的',k:'pact'}]};
    return {eb, ask:'产物都重导好了', why:'下一步：出改前 | 改后的对照表，纯读。',
      acts:[{a:'next',t:'去第 3 步 →',k:'pact'},{a:'detail',t:'看这 7 项写到哪儿',k:'link2'}]};
  }
  if(n===3){
    const rv=st.review;
    if(fail) return {eb, red:1, ask:'对照表没做出来', why:esc(rv&&rv.detail||''),
      acts:[{a:'review',t:'▶ 再出一次',k:'pact'},{a:'detail',t:'看日志',k:'link2'}]};
    if(!rv) return {eb, ask:'出一张改前 | 改后的对照表',
      why:'纯读，随时可以反复跑。图会放在「细节」里，点开能放大。',
      acts:[{a:'review',t:'▶ 出对照表',k:'pact'}]};
    return {eb, ask:'对照表好了，'+nEm((S.sheets||[]).length)+' 张，看一眼再决定换不换',
      why:'这一步不写任何正式产物。换入是第 4 步，要你签字。',
      acts:[{a:'detail',t:'打开对照表',k:'pact'},{a:'next',t:'去第 4 步 →',k:'link2'}]};
  }
  const live4=list.filter(s=>s.tier==='live'), aw4=live4.filter(s=>stn(s.key)==='await');
  if(fail) return {eb, red:1, ask:esc(fail.key)+' 这一步没过',
    why:'闸门判红说明这次换入会丢东西——别绕，先查源包。',
    acts:[{a:'swap',t:'⚑ 再试一次换入',k:'pact sign'},{a:'detail',t:'看日志',k:'link2'}]};
  if(aw4.length) return {eb, ask:nEm(aw4.length)+' 项暂存产物等着换进正式区',
    why:'换入前整批备份到 Output/_OLD_bak/；索引有零回退闸门，会掉条目就直接停。',
    acts:[{a:'swap',t:'⚑ 换入正式区',k:'pact sign'},{a:'regress',t:'只跑回归',k:'link2'}]};
  if(!live4.some(s=>stn(s.key)==='pass')&&!S.running)
    return {eb, ask:'现在没有待换入的东西',
      why:'先跑第 2 步（重导）和第 3 步（看图），暂存区里有货了这里才会亮。',
      acts:[{a:'prev',t:'← 回第 2 步',k:'pact'},{a:'detail',t:'看暂存区有什么',k:'link2'}]};
  return {eb, ask:'这次更新已经换完了', why:'画廊已部署、回归跑过；要再来一轮就从第 1 步开始。',
    acts:[{a:'regress',t:'▶ 只跑回归',k:'pact'},{a:'detail',t:'看细节',k:'link2'}]};
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

  /* ── 底部步骤条：四个节点，节点上带该步全部阶段的状态方块 ─────────────
     判据「13 个阶段一个都不许被折叠掉」靠这里每个 dot 都在。 */
  const steps=S.steps||{}, bar=$('#stepsbar');
  bar.querySelectorAll('.snode').forEach(e=>e.remove());
  Object.keys(steps).sort().forEach(k=>{
    const n=+k, list=stagesOf(n);
    const worst=list.map(s=>statusOf(s.key))
      .reduce((a,b)=>['fail','run','await','pass','idle'].indexOf(a)<=['fail','run','await','pass','idle'].indexOf(b)?a:b,'idle');
    const doneN=list.filter(s=>statusOf(s.key)==='pass').length;
    const b=document.createElement('button');
    const fresh='s'+n, first=!mounted.has(fresh); mounted.add(fresh);
    b.className='snode'+(n===step?' on':'')+(first?' in':'')+
      (worst==='fail'?' fail':worst==='await'?' await':worst==='run'?' run':
       doneN===list.length&&list.length?' done':'');
    if(first) b.style.animationDelay=(n*70)+'ms';
    b.innerHTML='<span class="bead"></span><label>'+esc(steps[k][0])+'</label>'+
      '<span class="sdots">'+list.map(s=>'<i class="dot '+statusOf(s.key)+'" title="'+esc(s.key)+'"></i>').join('')+'</span>'+
      '<span class="cnt">'+doneN+'/'+list.length+'</span>';
    b.onclick=()=>{ step=n; render(); };
    bar.appendChild(b);
  });
  stepFill();

  /* ── 主屏 ─────────────────────────────────────────────────────────── */
  const A=askOf(step);
  const eb=$('#eyebrowTx'), ask=$('#ask'), why=$('#why'), foot=$('#scopeNote');
  eb.textContent = S.running ? ('正在跑 · '+S.running.label) : A.eb;
  $('#eyebrow').classList.toggle('red', !!A.red);
  $('#eyebrow').classList.toggle('run', !!S.running);
  if(ask.innerHTML!==A.ask){
    ask.innerHTML=A.ask; rollNums(ask);
    if(RENDERED&&!CALM){ ask.classList.remove('swap'); void ask.offsetWidth; ask.classList.add('swap'); }
  }
  why.textContent=A.why;
  foot.textContent=A.foot||'';
  foot.classList.toggle('on',!!A.foot);
  $('#cta').innerHTML=A.acts.map(c=>c.k.indexOf('link2')>=0
      ? '<button class="link2" data-a="'+c.a+'">'+c.t+'</button>'
      : '<button class="'+c.k+'" data-a="'+c.a+'">'+c.t+'</button>').join('');
  avoidRefresh();
  passWatch();

  const ungrouped=all.filter(s=>!steps[s.step||0]);
  if(ungrouped.length){
    foot.textContent='有 '+(ungrouped.map(s=>s.key).join(', '))+' 没归到任何一步，先补 step';
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
      (s.tier==='live'?'<label class="signbox"><input type="checkbox" class="appr" data-k="'+
        s.key+'"> 签字放行</label>':'')+
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

  $('#runs').innerHTML=(S.runs||[]).map(rr=>'<tr><td class="dim" style="white-space:nowrap">'+
    esc((rr.started||'').slice(11))+'</td><td>'+esc(rr.label||'')+
    '<div class="dim" style="font-size:11px">'+esc(rr.state==='done'?(rr.clean===false?'没看到收尾行':'完成'):rr.state||'')
    +'</div></td><td style="text-align:right"><span class="tag '+esc(rr.state||'')+'">'+
    (rr.state==='running'?'在跑':'看日志')+'</span></td></tr>').join('')||
    '<tr><td colspan="3" class="dim">还没有任务</td></tr>';
  $$('#runs tr').forEach((tr,i)=>{ const rr=(S.runs||[])[i]; if(!rr) return;
    tr.style.cursor='pointer'; tr.onclick=()=>{ tail(rr.id); openDetail(); }; });
  $$('#cta button').forEach(b=>b.onclick=()=>ctaRun(b.dataset.a));
  $$('#cards .appr').forEach(cb=>cb.onchange=e=>
    e.target.closest('.signbox').classList.toggle('on', e.target.checked));
  $$('#cards .stage').forEach(el=>{
    el.addEventListener('mouseenter',()=>{ const k=el.querySelector('.skey').textContent;
      const d=document.querySelector('.snode .dot[title="'+k+'"]'); if(d) d.classList.add('hot'); });
    el.addEventListener('mouseleave',()=>{ [...document.querySelectorAll('.dot.hot')]
      .forEach(d=>d.classList.remove('hot')); });
  });
  $$('#cards [data-run]').forEach(b=>b.onclick=()=>{
    const k=b.dataset.run, s=(S.stages||[]).find(x=>x.key===k);
    const ap=s&&s.tier==='live'&&b.closest('.stage').querySelector('.appr').checked;
    if(ap&&!confirm('签字放行 '+k+'：它会写进正式区（会先备份）。确认？')) return;
    post({stages:[k],approve:ap?[k]:[],force:force},null); });
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
function ctaRun(a){
  if(a==='next') return void (step=Math.min(4,step+1), render());
  if(a==='prev') return void (step=Math.max(1,step-1), render());
  if(a==='detail') return void openDetail();
  const live4=(S.stages||[]).filter(s=>s.step===4&&s.tier==='live').map(s=>s.key);
  if(a==='diff') return post({stages:['preflight','pull'],force:force});
  if(a==='pull') return sign(['pull'],'第 1 步：从模拟器拉包',
    'adb pull 写进 files/AssetBundles（只补缺的和变了的）。'+
    '源包一旦覆盖，旧版本本地就没了 —— 所以它要你签字。');
  if(a==='tocheck') return post({stages:[],force:force});
  if(a==='staged') return post({stages:['paintings','spine','live2d'],force:force});
  if(a==='review') return post({stages:['review'],force:force});
  if(a==='regress') return post({stages:['regress'],force:force});
  if(a==='swap') return sign(live4,'第 4 步：换入 '+live4.join(' + '),
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
  if(k==='escape'){ $('#help').classList.remove('on'); $('#lightbox').classList.remove('on');
                    closeDetail(); return; }
  if(k==='d'){ toggleDetail(); e.preventDefault(); return; }
  if(k>='1'&&k<='4'&&Number(k)<=Object.keys((S&&S.steps)||{}).length){
    step=Number(k); render(); e.preventDefault(); return; }
  if(k==='h'){ $('#help').classList.toggle('on'); }
  else if(k==='s'){ $('#bSea').click(); }
  else if(k==='m'){ CALM=!CALM; localStorage.setItem('panel.calm',CALM?'1':'0'); calmApply(); }
  else if(k==='v'){ LEGACY=!LEGACY; localStorage.setItem('panel.legacy',LEGACY?'1':'0');
                    legacyApply(); fxOff(); FX.last=null; }
  else if(k==='p'){ if(!S||S.running) return; post({plan:true}); }
  else if(k==='r'){ if(!S||S.running) return; ctaRun(step===1?'diff':step===3?'review'
                    :step===4?'swap':'tocheck'); }
});
$$('#help [data-close]').forEach(el=>el.onclick=()=>$('#help').classList.remove('on'));

document.addEventListener('click',e=>{ if(e.target.matches('.sheets img')){
  $('#lightbox img').src=e.target.src; $('#lightbox').classList.add('on'); e.preventDefault(); } });
$('#lightbox').onclick=e=>e.currentTarget.classList.remove('on');
legacyApply(); seaApply(); calmApply(); apiState();
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
                go(n){ step=n; render(); }, state(){ return S; },
                calm(on){ CALM=!!on; localStorage.setItem('panel.calm',CALM?'1':'0');
                          calmApply(); return CALM; },
                legacy(on){ LEGACY=!!on; localStorage.setItem('panel.legacy',LEGACY?'1':'0');
                            legacyApply(); fxOff(); FX.last=null; return LEGACY; },
                fx(){ const e=FX.edge,p=FX.pool;
                  return {calm:CALM, k:FX.k||null,
                          edge:!!(e&&e.classList.contains('on')),
                          edgeShown:!!(e&&getComputedStyle(e).display!=='none'),
                          edgeBg:e?e.style.background:'',
                          pool:!!(p&&Number(p.style.opacity||0)>0),
                          poolShown:!!(p&&getComputedStyle(p).display!=='none'),
                          cur:FX.cur?String(FX.cur.el.className):null}; },
                /* 背景星野的现状。探针靠这几项判「漂移有界且慢」与「冻结态可复现」，
                   不再有"静止零动画"这条（那正是 B2 方向要付的代价）。 */
                sky(){ return {sea:SEA, calm:CALM, frozen:!!ST.frozen, running:!!ST.raf,
                               t:ST.t, frames:ST.frames, stars:ST.list.length,
                               drift:ST.DRIFT.slice(), fps:ST.FPS, dim:ST.DIM,
                               beacon:ST.beacon?ST.beacon.x:null,
                               beaconHalf:ST.beacon?ST.beacon.half:null,
                               avoid:(ST.avoid||[]).length, rings:ST.rings.length}; },
                /* 冻结/解冻：冻结后 `t` 不再推进、指针提亮也停用 ⇒ 整帧可复现。
                   这是唯一能在"漂移常开"下拿到可比两帧的办法。 */
                freeze(on){ freezeSky(on); return !!ST.frozen; },
                /* 把相位钉到指定值再画一帧。冻结只保证"不再推进"，但两次冻结落在不同相位上
                   ⇒ 跨段的像素比对仍会差一整片天。钉住相位之后，"新版↔旧版""切回来"这些
                   比对量到的才只有 chrome 本身。 */
                tAt(v){ ST.t=+v||0; if(ST.g) starsDraw(ST.t); return ST.t; },
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
                                acts:[...document.querySelectorAll('#cta button')]
                                      .map(x=>x.className+'|'+x.textContent)}; },
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
