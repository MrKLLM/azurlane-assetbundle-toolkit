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
   ② **版面照深色仪表盘的正经做法：中性阶梯 + 发丝线 + 零投影。**
      参照物是两个公开设计系统的实测 token（Linear / Raycast），它们的规则里
      逐条点到了上一版的病：
        · "Don't use lavender as a section background or card fill" ⇒ 上一版
          `--pane:#12101f / --card:#181527 / --deep:#150d1f` 全是薰衣草底；
        · "The brand resists drop shadows almost entirely, leaning on tonal lifts
          and subtle top-edge highlights" ⇒ 上一版每个面板挂 `0 22px 46px -32px`；
        · "Don't introduce a second chromatic accent / Don't add atmospheric
          gradients" ⇒ 上一版紫+品红+青三彩并用，还在每块面板顶边画了一道
          紫→品红的渐变"灯管"。
      ⇒ 现在：中性五档表面阶梯（只留一丝冷调，不偏紫）、1px 实色发丝线、
      投影全部换成 `inset` 顶边微高光、**唯一的 chrome 强调色 = 品牌紫**，
      氛围全部交给背景那片星野（他要的"东京夜"留在这儿，不留在面板上）。
      五个状态色 idle/pass/fail/await/run **一个都不动**——那是语义不是配色。
   所有可视量都走变量，于是旧版面整体挂在 `body.legacy` 上，`V` 键当场对照。 */
:root{
  /* 表面阶梯（Linear 是 #010102→#0f1011→#141516→#18191a；这里同构、偏冷不偏紫） */
  --abyss:#07080b; --deep:#0b0c10; --pane:#101116; --card:#15161b; --raise:#1b1d23;
  --head:#0c0d11;
  /* 发丝线：实色、1px、三档，不用 rgba 紫 */
  --line:#24262c; --line2:#33363e; --line3:#454954;
  /* 文字坡：中性冷灰，不用薰衣草白 */
  --txt:#f1f2f4; --txt2:#c9cdd4; --dim:#9096a0; --dim2:#666b75;
  --idle:#3f5a6e; --pass:#4fd6a8; --fail:#ff6f6f; --await:#f2bd72; --run:#5fd0e8;
  --brand:#8b8cf5;          /* 唯一的 chrome 强调色（Linear 的 #5e6ad2 同位） */
  --brand-hi:#a5a6ff;       /* 它的 hover，不算第二种彩 */
  --pop:var(--brand);       /* 兼容旧引用：品红退役，一律回落到品牌紫 */
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
  --glow:.26;                                 /* 背景那三团光的强度 */
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
  --glow:.55; --hero-fs:17px; --hero-ls:.04em;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;font:13px/1.55 var(--fb);color:var(--txt);overflow:hidden;
  background:linear-gradient(180deg,var(--abyss) 0%,var(--deep) 62%,var(--deep) 100%)}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-thumb{background:var(--line2);border-radius:6px}
::-webkit-scrollbar-thumb:hover{background:var(--line3)}
::-webkit-scrollbar-track{background:transparent}

/* ══ 背景层：东京夜的星野（氛围只留在这里，面板上一个都不给）═══════════
   三团不动的城市光晕当底（强度走 `--glow`，新版面压到 .26），星点画在一张 2D 画布上：
   鼠标划过 ⇒ 星点显影；停手 ⇒ 能量归零后**写回 home 再画一帧**。
   最后那一句是关键：它保证"亮过又淡掉"的终点和初始帧**逐像素相同**。 */
#bgfx{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
#bgfx .bfield{position:absolute;inset:-10%}
#bgfx .glow{position:absolute;border-radius:50%;opacity:var(--glow);
  transition:opacity .3s var(--ez)}
#bgfx .g1{left:-30vmax;bottom:-40vmax;width:86vmax;height:86vmax;
  background:radial-gradient(closest-side,rgba(255,150,66,.55) 0%,rgba(255,150,66,.16) 44%,
    transparent 100%)}
#bgfx .g2{right:-28vmax;bottom:-34vmax;width:76vmax;height:76vmax;
  background:radial-gradient(closest-side,rgba(139,140,245,.46) 0%,rgba(139,140,245,.13) 44%,
    transparent 100%)}
#bgfx .g3{right:-6vmax;top:-34vmax;width:62vmax;height:62vmax;
  background:radial-gradient(closest-side,rgba(47,208,255,.34) 0%,rgba(47,208,255,.10) 44%,
    transparent 100%)}
#bgfx canvas{position:absolute;inset:0;width:100%;height:100%}
/* 星云单独一张**永不重绘**的画布：它整幅是静态的，跟着星点画布每帧 clearRect 再 blit
   一次等于白拷 6MB/帧（SwiftShader 上实测拖慢截图到 2s+），而且每帧重合成还会带来
   dither 抖动。分开之后静止帧天然逐像素相同。 */
body.plain #bgfx .glow,body.plain #bgfx #nebula{display:none}

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
button:focus-visible{outline:2px solid rgba(139,140,245,.5);outline-offset:2px}
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
/* 左轨当前步的那道标记：不再每张卡各画一根，而是**一根从旧步走到新步**。
   新版面是实色 2px 紫条、不挂光晕（Linear 的当前项标记就是纯色一条）。 */
#railwrap{position:relative}
#railmark{position:absolute;left:-1px;width:2px;border-radius:2px;top:0;height:0;opacity:0;
  background:var(--brand);
  transition:top .42s var(--ez),height .42s var(--ez),opacity .3s var(--ez);pointer-events:none}
#chipmark{position:absolute;bottom:-1px;height:2px;border-radius:2px;left:0;width:0;
  background:var(--brand);opacity:0;pointer-events:none;
  transition:left .34s var(--ez),width .34s var(--ez),opacity .2s var(--ez)}
#chips{position:relative}
body.legacy #railmark,body.legacy #chipmark{
  background:linear-gradient(180deg,#a06bff,#ff3d7f);box-shadow:0 0 12px rgba(255,61,127,.7)}
/* 磁吸：只有主操作与左轨会朝指针让出 2px，普通按钮不让（它们挨得太近会晃）。
   写全 transition 列表而不是只写 transform —— 简写会连带抹掉底色/描边的过渡。 */
.mag{transition:transform .55s var(--ez),background .16s var(--ez),
  border-color .16s var(--ez),box-shadow .2s var(--ez),opacity .16s}

/* ══ 大气区与数据区的分工 ═══════════════════════════════════════════════
   规矩只有一条：**能读数据、能看图的位置一律不透明**。
   hero 是全局唯一让正文"坐在星野上"的地方，只放标题级短文（带 text-shadow 压亮度），
   阶段卡、日志、对照图、指标 pill 一个都不许放进去。 */
.wrap{flex:1 1 auto;min-height:0;display:grid;gap:var(--s4);
  padding:var(--s4) var(--s5) var(--s5);
  grid-template-columns:264px minmax(520px,1fr) minmax(360px,.66fr);max-width:1760px;
  margin:0 auto;width:100%;align-items:stretch}
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

/* ══ 步骤导航 ═════════════════════════════════════════════════════════ */
.step{position:relative;display:grid;grid-template-columns:26px 1fr auto;gap:10px;
  align-items:start;width:100%;text-align:left;padding:var(--s2) 10px;
  border-radius:var(--r-ctl);background:transparent;border:1px solid transparent;
  color:var(--txt)}
.step:hover{background:var(--card);border-color:var(--line)}
.step.on{background:var(--card);border-color:var(--line2)}
.step .num{font:600 17px/1.45 var(--fd);letter-spacing:-.3px;color:var(--dim);
  text-align:center;border:1px solid var(--line);border-radius:var(--r-ctl);
  background:var(--pane)}
.step.on .num{color:var(--brand-hi);border-color:rgba(139,140,245,.55)}
.step b{display:block;font-size:13px;font-weight:600;letter-spacing:-.05px}
.step em{display:block;font:400 11px/1.45 var(--fb);color:var(--dim);font-style:normal;
  margin-top:1px}
.step .cnt{font:11px/1 var(--fm);color:var(--dim2);margin-top:5px;display:block}
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
/* 页头**不再是一个盒子**：正经仪表盘里"当前在哪一步"就是一行标题 + 一行副标题，
   不需要再套一道描边和一块底色（那正是"卡片套卡片"的 AI 味来源）。
   只留 text-shadow 压住任何星点亮度；卡片、日志、对照图全在不透明面板里。 */
.hero{padding:2px 4px 6px}
body.legacy .hero{padding:15px 17px 14px;border-radius:16px;
  border:1px solid rgba(178,166,214,.14);
  background:linear-gradient(180deg,rgba(8,6,18,.20),rgba(6,4,14,.06))}
.whead{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}
.whead h2{margin:0;font:500 var(--hero-fs)/1.25 var(--fb);letter-spacing:var(--hero-ls);
  color:var(--txt);text-shadow:0 1px 12px rgba(3,4,10,.95),0 0 2px rgba(3,4,10,.8)}
.whead p{margin:3px 0 0;color:var(--dim);font-size:12.5px;max-width:70ch;
  text-shadow:0 1px 8px rgba(3,4,10,.95)}
.cta{display:flex;gap:var(--s2);flex-wrap:wrap;margin:var(--s3) 0 2px}
.scopenote{font-size:11.5px;color:var(--await);margin:6px 0 0;display:none}
.scopenote.on{display:block}

.g{display:flex;flex-direction:column;gap:var(--s2)}
/* 入场动画挂在 `.in` 上，**只有首次挂载才加**（见 render 里的 mounted 集合）。
   写在基础类上 = 每次数据刷新重建节点就重播一次，那就是"每 8 秒整屏闪一下"的根因。 */
.step.in,.stage.in{animation:rise .44s var(--ez) backwards}
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
.chip.on{border-color:rgba(139,140,245,.5);color:var(--txt);background:rgba(139,140,245,.13)}
.kbd{font:10.5px/1 var(--fm);padding:3px 7px;border-radius:var(--r-tag);
  border:1px solid var(--line);color:var(--dim);background:var(--pane)}
.kbd b{color:#e4d7ff;font-weight:600}

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
#help code{font:11.5px/1.5 var(--fm);background:rgba(139,140,245,.12);padding:1px 6px;
  border-radius:var(--r-tag);color:#b9bdf5}
#help .close{position:sticky;top:0;float:right}
.warn{background:rgba(255,111,111,.10);border:1px solid rgba(255,111,111,.34);
  border-radius:var(--r-ctl);
  padding:9px 12px;font-size:12.5px;color:#ffc2c2;margin-bottom:11px;display:none}
.warn.on{display:block}
#lightbox{position:fixed;inset:0;background:rgba(2,7,12,.95);display:none;z-index:99;
  align-items:center;justify-content:center;cursor:zoom-out}
#lightbox.on{display:flex}
#lightbox img{max-width:96vw;max-height:96vh;object-fit:contain}
/* ── M 键「动效从简」：整层光效停用，但**状态指示一个都不跟着没** ──────────
   #railmark 表达的是"当前在哪一步"，那是信息不是装饰 ⇒ 只掐它的位移，不掐它本身。 */
body.calm #fxbeam,body.calm #fxpool{display:none!important}
body.calm #railmark,body.calm #chipmark{transition:none}
body.calm .mag{transition:none}
body.calm .stage::before{transform:none!important}
body.calm .signbox.on::after{display:none}
@media (max-width:1240px){.wrap{grid-template-columns:230px minmax(400px,1fr)}
  .col.side{grid-column:1/-1}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head><body>

<div id="bgfx" aria-hidden="true"><div class="bfield">
  <i class="glow g1"></i><i class="glow g2"></i><i class="glow g3"></i></div>
  <canvas id="nebula"></canvas><canvas id="stars"></canvas></div>

<div class="app">
<header>
  <div class="brand">
    <svg width="24" height="24" viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <path d="M17.4 2.6l1.5 4.3 4.3 1.5-4.3 1.5-1.5 4.3-1.5-4.3L11.6 8.4l4.3-1.5z"
            fill="#8b8cf5"/>
      <circle cx="5.4" cy="6.6" r="1.1" fill="#eef4ff"/>
      <circle cx="10.2" cy="12.4" r=".8" fill="#fff2df" opacity=".9"/>
      <circle cx="3.6" cy="14.2" r=".7" fill="#dbe6f7" opacity=".7"/>
      <path d="M1 21.4c2.2 0 2.2-2 4.4-2s2.2 2 4.4 2 2.2-2 4.4-2 2.2 2 4.4 2 2.2-2 4.4-2"
            stroke="#f2bd72" stroke-width="1.2" stroke-linecap="round" fill="none" opacity=".5"/>
      <path d="M1 25.2c2.2 0 2.2-1.6 4.4-1.6s2.2 1.6 4.4 1.6" stroke="#8b8cf5"
            stroke-width="1" stroke-linecap="round" fill="none" opacity=".45"/>
    </svg>
    <div><h1>资产更新控制台</h1><p>拉包 · 重导 · 看图 · 换入</p></div>
  </div>
  <div class="meters">
    <span class="meter"><b>输入指纹</b><span id="fp">计算中</span></span>
    <span class="meter"><b>本次范围</b><span id="scope">…</span></span>
    <span class="meter"><b>阶段</b><span id="prog">…</span></span>
    <span class="meter" id="mjob"><b>任务</b><span id="jobstat">空闲</span></span>
  </div>
  <div class="act">
    <button id="bSea" class="ghost" title="S：星野背景 开/关">星辰 · 开</button>
    <span class="kbd" title="1-4 步骤 · R 跑 · P 只看计划 · H 帮助 · S 背景 · M 动效从简 · V 新旧版面对照">
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
      <div id="railwrap"><div id="rail"></div><i id="railmark"></i></div>
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
      <div class="ph">阶段 <span id="sCount" class="dim" style="font-size:11px"></span></div>
      <div class="g" id="cards"></div>
    </div>
    <div class="pane">
      <div class="ph">改前 | 改后 对照表</div>
      <div id="sheets" class="sheets"></div>
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

<i id="fxbeam"></i><i id="fxpool"></i>

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
  <code>S</code> 开关星野背景 · <code>M</code> 开关「动效从简」（关掉光沿边框走一圈、
  指针柔光、磁吸这些，只留状态本身）· <code>V</code> 开关「新旧版面对照」
  （新版面=中性阶梯+发丝线+零投影，旧版=薰衣草底+渐变灯管+投影），两个选择都会记住。</p>

  <h3>版面为什么长这样</h3>
  <p>深色仪表盘的正经分层法只有一条：<b>底色抬档 + 1px 发丝线 + 顶边一道微高光，不用投影</b>。
  参照的是两个公开设计系统的实测 token，它们的规则里逐条点到上一版的病：
  「别拿薰衣草色当分区底色或卡片填充」「几乎不用 drop shadow，纵向层级全靠色阶与描边」
  「别引入第二种强调色」「别加氛围渐变」。</p>
  <p>所以：五档中性表面（只留一丝冷调，不偏紫）、发丝线三档实色、
  圆角按 4/6/8/12 分档、间距走 4 的倍数栅格、小标签不再全大写加宽字距、
  chrome 强调色<b>只有一个</b>品牌紫（主动作用它，签字按钮借用「等你签字」那个琥珀，
  语义自洽）。氛围全部交给背景那片星野，面板上一分都不给。
  <b>五个状态色一个都没动</b>——那是语义不是配色。</p>

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
          AMB:0.10,          // 常驻星点占比的亮度；想要"完全只有经过才亮"就把它设成 0
          RMIN:9,RMAX:130,   // 显影半径：随笔画速度从 9px 长到 130px
          DECAY:4.6,         // 亮度衰减 /秒 ⇒ 520ms 后只剩 9%
          SPRING:34,DAMP:4.2,EPS:0.12,LIT_EPS:0.012,
          LINK_A:0.16,        // 星座连线的 alpha 上限（旧版 0.52 太像连点图）
          last:null,lastT:0,pend:null};
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
  const n=Math.round(Math.min(3200,Math.max(1100,w*h/520)));
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
    ST.list.push({hx:x,hy:y,x:x,y:y,vx:0,vy:0,z:z,kind:kind,lit:0,
      amb:(i%47===0 && kind!=='hero' ? ST.AMB*(0.4+R()*0.6) : 0),
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
  for(let i=0;i<30;i++){
    const t=R(), o=(R()-0.5)*w*0.20;
    const s=180+R()*340, al=0.018+R()*0.030;
    g.globalAlpha=al;
    g.drawImage(SPR.cloud[R()<0.72?0:1], gx+dx*t+o-s/2, gy+dy*t+(R()-0.5)*w*0.11-s/2, s, s);
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
let LEGACY = localStorage.getItem('panel.legacy')==='1';
function legacyApply(){
  document.body.classList.toggle('legacy',LEGACY);
  if(ST.g){ starColors(); starsResize(); }        // 星点色板跟着版面走
  else starColors();
}
const FX={beam:$('#fxbeam'),pool:$('#fxpool'),cur:null,last:null,down:false,pt:{}};
const FXSEL='button,.step,.signbox,.sheets a';
function fxTone(el){
  const c=el.classList;
  // 边框光/柔光的颜色跟着**语义**走：主动作=品牌紫，签字=等你签字的琥珀，其余中性。
  if(c.contains('go')) return ['#a5a6ff','rgba(139,140,245,.26)'];
  if(c.contains('sign')||c.contains('signbox')) return ['#f2bd72','rgba(242,189,114,.22)'];
  if(c.contains('step')) return ['#8b8cf5','rgba(139,140,245,.16)'];
  if(c.contains('chip')) return ['#8b8cf5','rgba(139,140,245,.13)'];
  return ['rgba(206,212,228,.75)','rgba(220,225,240,.13)'];
}
function fxOff(){ FX.pool&&(FX.pool.classList.remove('on')); FX.beam&&FX.beam.classList.remove('go');
                 if(FX.cur){ FX.cur.el.style.transform=''; FX.cur=null; } }
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
    const dx=(p.clientX-(r.left+r.width/2))/(r.width/2);
    const dy=(p.clientY-(r.top+r.height/2))/(r.height/2);
    el.style.transform='translate('+(dx*2.6).toFixed(2)+'px,'+(dy*2.0).toFixed(2)+'px)'+
                       (FX.down?' scale(.978)':'');
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
function railMark(){
  const on=$('.step.on'), mk=$('#railmark'); if(!on||!mk) return;
  mk.style.top=(on.offsetTop+9)+'px'; mk.style.height=Math.max(8,on.offsetHeight-18)+'px';
  mk.style.opacity='1';
}
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
function render(){
  RENDERED=true;
  if(!S) return;
  if(LASTSTEP!==step){ mounted.clear(); LASTSTEP=step; }   // 切步骤 = 这批卡的首次出现
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
    const fresh='s'+n; const first=!mounted.has(fresh); mounted.add(fresh);
    b.className='step mag'+(n===step?' on':'')+(first?' in':'');
    if(first) b.style.animationDelay=(n*55)+'ms';
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
  railMark();
  const ungrouped=all.filter(s=>!steps[s.step||0]);
  if(ungrouped.length){
    const b=document.createElement('div'); b.className='step';
    b.innerHTML='<span class="num">?</span><span><b>未归组</b>'+
      '<span class="cnt">缺 step：'+ungrouped.map(s=>s.key).join(', ')+'</span></span>'+
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
    sn.textContent='未签字：'+liveUnapproved.map(s=>s.key).join(' / ')+' 只算差异，不写正式区';
    sn.classList.add('on');
  } else if(S.scope==null&&step>=2){
    sn.textContent='未做增量 detect · 先跑 ① 看差异';
    sn.classList.add('on');
  } else sn.classList.remove('on');

  const cards=$('#cards'); cards.innerHTML='';
  list.forEach((s,i)=>{
    const st=statusOf(s.key), r=(S.state||{})[s.key]||{}, T=TIER[s.tier]||['?','r'];
    const d=document.createElement('div');
    const first=!mounted.has(s.key); mounted.add(s.key);
    d.className='stage'+(first?' in':'')+
      (st==='fail'?' fail':st==='await'?' await':'');
    if(first) d.style.animationDelay=(60+i*26)+'ms';
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
        s.key+'"> 签字放行</label>':'')+
      '<button class="mini" data-run="'+esc(s.key)+'">单独跑</button>'+
      '<span class="spacer"></span></div>';
    cards.appendChild(d);
  });

  const sh=$('#sheets');
  if(!(S.sheets||[]).length) sh.innerHTML='<p class="dim" style="font-size:12px;margin:0">'+
    '还没有对照表 · 先跑 ③</p>';
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
  if(n===1) return [{a:'diff',c:'go mag',t:'▶ 预检 + 看差异'},
                   {a:'pull',c:'sign mag',t:'⚑ 拉包进 files/'}];
  if(n===2) return [{a:'tocheck',c:'go mag',t:'▶ 跑到待确认'},
                   {a:'staged',c:'',t:'只重跑导出'}];
  if(n===3) return [{a:'review',c:'go mag',t:'▶ 出对照表'}];
  return [{a:'swap',c:'sign mag',t:'⚑ 换入正式区'},{a:'regress',c:'',t:'只跑回归'}];
}
function ctaRun(a){
  const live4=(S.stages||[]).filter(s=>s.step===4&&s.tier==='live').map(s=>s.key);
  if(a==='diff') return post({stages:['preflight','pull'],force:force});
  if(a==='pull') return sign(['pull'],'① 从模拟器拉包',
    'adb pull 写进 files/AssetBundles（只补缺的和变了的）。'+
    '源包一旦覆盖，旧版本本地就没了 —— 所以它是「写正式」。');
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
$('#bFollow').onclick=e=>{ follow=!follow; e.target.textContent=follow?'跟随最新':'暂停跟随'; };
$('#bClear').onclick=()=>{ LINES=[]; $('#log').textContent=''; };
$('#chips').onclick=e=>{ const b=e.target.closest('.chip'); if(!b) return;
  FILT=b.dataset.f; $$('#chips .chip').forEach(x=>x.classList.toggle('on',x===b));
  chipMark(); renderLog(); };
$('#bForce').onclick=e=>{ force=!force; e.target.textContent=force?'缓存：已绕过':'缓存：按指纹复用';
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
addEventListener('resize',()=>{ railMark(); chipMark(); });
chipMark();
let pollT=setInterval(()=>{ if(!timer) apiState(); },8000);
/* 验收钩子。`stop()` 是上一版留下的绕道：那时轮询会重播卡片入场动画，
   比对期间必须停掉轮询才拿得到可比的帧（实测假红 75）。
   现在入场动画只在首次挂载播、且 payload 没变根本不 render()，
   ⇒ 这个钩子**不再决定结论**：探针会带着轮询开着跑一遍静止比对，只有那一遍也绿才算修好了。 */
window.__probe={stop(){ if(pollT){ clearInterval(pollT); pollT=null; } },
                poll(on){ if(on&&!pollT) pollT=setInterval(()=>{ if(!timer) apiState(); },8000);
                          if(!on&&pollT){ clearInterval(pollT); pollT=null; } },
                pin(){ window.__pin=[...document.querySelectorAll('.step,.stage')]; return 1; },
                pinned(){ const now=[...document.querySelectorAll('.step,.stage')];
                          const p=window.__pin||[];
                          return p.length>0 && p.length===now.length && p.every(e=>now.includes(e)); },
                anims(){ return document.getAnimations().length; },
                go(n){ step=n; render(); }, state(){ return S; },
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
                marks(){ const a=$('#railmark'), b=$('#chipmark');
                  return {rail:a?a.style.opacity+'|'+a.style.top+'|'+a.style.height:null,
                          chip:b?b.style.opacity+'|'+b.style.left+'|'+b.style.width:null}; }};
window.ST=ST; window.SPR=SPR; window.panelState=()=>S;
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
