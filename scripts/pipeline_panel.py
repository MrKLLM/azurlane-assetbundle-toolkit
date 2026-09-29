# -*- coding: utf-8 -*-
"""一条龙可视化控制台 —— 本地网页，双击 .bat 打开。

它**不重新实现**任何流水线逻辑：每个按钮都是去起 `scripts/update_pipeline.py` 子进程，
然后把它写的日志实时读回来显示。这样"界面上看到的"和"命令行跑的"永远是同一套代码，
不存在两份逻辑各自漂移的问题（本项目栽过这类坑）。

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


# ------------------------------------------------------------------ 阶段白名单
def stage_keys():
    """阶段名与档位一律从 update_pipeline 读，**不在面板里再抄一份清单**——
    抄了就会漂移（本项目栽过"谁写谁读各一份实现"这类坑）。
    update_pipeline 有 __main__ 保护，import 它没有副作用。"""
    sys.path.insert(0, HERE)
    import update_pipeline as up
    import importlib
    importlib.reload(up)          # 改了流水线脚本后不用重启面板
    return [{'key': s.key, 'title': s.title, 'tier': s.tier, 'judge': s.judge_desc}
            for s in up.STAGES]


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
            try:
                os.kill(r['pid'], 0)
                return r
            except OSError:
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
        try:
            os.kill(r['pid'], 0)
            alive = True
        except OSError:
            alive = False
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
            try:
                stages = stage_keys()
            except Exception as e:
                stages = []
                err = str(e)
            else:
                err = ''
            state = {}
            try:
                state = json.load(open(os.path.join(WORK, 'pipeline_state.json'),
                                       encoding='utf-8')).get('done', {})
            except Exception:
                pass
            sheets = []
            for p in sorted(glob_sheets()):
                sheets.append({'name': os.path.basename(p),
                               'kb': round(os.path.getsize(p) / 1024),
                               'mt': time.strftime('%m-%d %H:%M', time.localtime(
                                   os.path.getmtime(p)))})
            return self._send(200, {
                'stages': stages, 'state': state, 'runs': load_runs()[-12:][::-1],
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
        valid = {s['key'] for s in stage_keys()}
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


def fingerprint_safe():
    sys.path.insert(0, HERE)
    try:
        import update_pipeline as up
        return up.fingerprint()
    except Exception as e:
        return f'(读不到：{e})'


def scope_safe():
    sys.path.insert(0, HERE)
    try:
        import update_pipeline as up
        t = up.affected_stems(False)
        return None if t is None else len(t)
    except Exception:
        return None


PAGE = r'''<!doctype html><html lang=zh><head><meta charset=utf-8>
<title>资产一条龙 · 控制台</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{--bg:#0f1319;--panel:#171d26;--panel2:#1e2733;--line:#2a3644;--txt:#e6edf3;--dim:#8b98a9;
--ok:#3fb950;--warn:#d29922;--live:#f85149;--acc:#58a6ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.6 "Microsoft YaHei",system-ui,sans-serif}
header{position:sticky;top:0;z-index:5;background:linear-gradient(180deg,#141a23,#0f1319);
border-bottom:1px solid var(--line);padding:14px 22px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
h1{font-size:16px;margin:0;font-weight:600;letter-spacing:.5px}
.badge{font:12px/1 ui-monospace,Consolas;padding:4px 8px;border-radius:6px;background:var(--panel2);
border:1px solid var(--line);color:var(--dim)}
.badge b{color:var(--txt);font-weight:600}
main{display:grid;grid-template-columns:minmax(420px,1fr) minmax(420px,1.1fr);gap:18px;padding:18px 22px;
align-items:start;max-width:1500px;margin:0 auto}
section{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:16px}
h2{font-size:13px;margin:0 0 10px;color:var(--dim);font-weight:600;letter-spacing:1px;text-transform:uppercase}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
button{font:inherit;padding:7px 13px;border-radius:7px;border:1px solid var(--line);
background:var(--panel2);color:var(--txt);cursor:pointer;transition:.14s}
button:hover{border-color:var(--acc);background:#243040}
button:active{transform:translateY(1px)}
button.primary{background:#1f6feb;border-color:#1f6feb;color:#fff;font-weight:600}
button.primary:hover{background:#388bfd}
button.danger{border-color:#6d2623;color:#ff9d97}
button.danger:hover{background:#3a1d1b;border-color:var(--live)}
button:disabled{opacity:.4;cursor:not-allowed;transform:none}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--dim);font-weight:500;font-size:12px}
.tier{font:11px/1 ui-monospace,Consolas;padding:3px 6px;border-radius:5px;white-space:nowrap}
.read{background:#1230553;color:#79c0ff}.staged{background:#1c2a1c;color:#7ee787}.live{background:#3a1d1b;color:#ff9d97}
.st{font:11px/1 ui-monospace,Consolas;padding:3px 6px;border-radius:5px}
.ok{background:#12401e;color:#56d364}.bad{background:#4a1d1d;color:#ff7b72}.none{background:#222;color:#8b98a9}
input[type=checkbox]{accent-color:var(--acc);width:15px;height:15px;margin-top:3px}
pre{margin:0;font:12px/1.55 ui-monospace,Consolas;white-space:pre-wrap;word-break:break-all;
background:#0b0f14;border:1px solid var(--line);border-radius:8px;padding:10px 12px;
height:46vh;overflow:auto;color:#c9d1d9}
.hint{color:var(--dim);font-size:12px;margin:6px 0 0}
.sheets{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.sheets a{display:block;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#0b0f14}
.sheets img{display:block;width:100%;height:190px;object-fit:contain;cursor:zoom-in}
.sheets .cap{font-size:11px;color:var(--dim);padding:5px 8px;display:flex;justify-content:space-between}
#lightbox{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;z-index:99;
align-items:center;justify-content:center;cursor:zoom-out}
#lightbox img{max-width:96vw;max-height:96vh;object-fit:contain}
.pulse{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--ok);
animation:p 1s infinite;margin-right:6px;vertical-align:middle}
@keyframes p{50%{opacity:.25}}
.warn{background:#3a2a12;border:1px solid #6a4b1a;color:#ffd9a0;padding:8px 11px;border-radius:8px;
font-size:12.5px;margin-bottom:10px}
</style></head><body>
<header>
 <h1>资产一条龙 · 控制台</h1>
 <span class=badge id=fp>指纹 —</span>
 <span class=badge id=scope>范围 —</span>
 <span class=badge id=jobstat>空闲</span>
 <button id=bPlan>只看计划</button>
 <button id=bRun class=primary>▶ 跑到「待确认」</button>
 <button id=bSwap class=danger>⇩ 签字换入正式产物</button>
</header>
<main>
<div>
 <section>
  <h2>阶段 · 勾选=只跑这些</h2>
  <div class=row><button id=bAll>全选</button><button id=bNone>全不选</button>
   <button id=bForce>绕过缓存重跑</button></div>
  <table id=tbl><thead><tr><th></th><th>阶段</th><th>档</th><th>上次结论</th><th></th></tr></thead><tbody></tbody></table>
  <p class=hint><b>read</b> 只读检查 · <b>staged</b> 只写 <code>.diag/pipeline/</code> ·
   <b>live</b> 会写 <code>Output/</code> 或 <code>files/</code>，<u>必须勾选"签字"才会执行</u>。
   不勾任何阶段 = 按顺序从头跑到 review。</p>
 </section>
 <section>
  <h2>待确认：改前 | 改后 对照表</h2>
  <div id=sheets class=sheets></div>
  <p class=hint>review 阶段跑完后出现在这里。图片点开可放大。</p>
 </section>
</div>
<div>
 <section>
  <h2>运行日志</h2>
  <div id=warn></div>
  <pre id=log>（还没跑任何东西）</pre>
  <div class=row style="margin-top:8px"><button id=bClear>清空显示</button>
   <button id=bFollow>跟随最新</button><span class=badge id=jobinfo>—</span></div>
 </section>
 <section>
  <h2>最近任务</h2>
  <table id=runs><thead><tr><th>时间</th><th>做什么</th><th>状态</th></tr></thead><tbody></tbody></table>
 </section>
</div>
</main>
<div id=lightbox><img></div>
<script>
let S=null, curJob=null, off=0, follow=true, timer=null;
const $=s=>document.querySelector(s);
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

async function state(){
  const r=await fetch('/api/state'); S=await r.json();
  $('#fp').textContent='指纹 '+ (S.fingerprint||'—');
  $('#scope').textContent = S.scope==null ? '范围：未 detect（先跑 pull）' : '范围：增量 '+S.scope+' 个 stem';
  const tb=$('#tbl tbody'); tb.innerHTML='';
  for(const s of S.stages){
    const st=(S.state||{})[s.key];
    const tr=document.createElement('tr');
    tr.innerHTML=`<td><input type=checkbox data-k="${s.key}"></td>
      <td><b>${s.key}</b><div class=hint style=margin:0>${esc(s.title)}</div>
          <div class=hint style=margin:0;color:#6e7f91>${esc(s.judge)}</div></td>
      <td><span class="tier ${s.tier}">${s.tier}</span></td>
      <td>${st?`<span class="st ${st.ok?'ok':'bad'}" title="${esc(st.detail||'')}">${st.ok?'绿':'红'}</span>`
              :'<span class="st none">未跑</span>'}</td>
      <td>${s.tier=='live'?`<label class=hint style="margin:0;white-space:nowrap">
            <input type=checkbox class=appr data-k="${s.key}"> 签字</label>`:''}</td>`;
    tb.appendChild(tr);
  }
  const sh=$('#sheets');
  if(!(S.sheets||[]).length){ sh.innerHTML='<p class=hint>（还没有对照表 —— 跑一次带 review 的流程后出现）</p>'; }
  else sh.innerHTML=S.sheets.map(x=>`<a target=_blank href="/file?path=${encodeURIComponent(x.name)}">
      <img loading=lazy src="/file?path=${encodeURIComponent(x.name)}" alt="${esc(x.name)}">
      <div class=cap><span>${esc(x.name)}</span><span>${x.kb}KB ${x.mt}</span></div></a>`).join('');
  const rb=$('#runs tbody'); rb.innerHTML=(S.runs||[]).map(r=>
    `<tr><td>${esc(r.started||'')}</td><td>${esc(r.label||'')}</td>
     <td><span class="st ${r.state=='done'?'ok':r.state=='running'?'none':'bad'}">${esc(r.state||'')}</span>
     ${r.id?`<button style="padding:2px 7px;font-size:11px" onclick="tail('${r.id}')">日志</button>`:''}</td></tr>`).join('');
  if(S.running && !curJob) tail(S.running.id);
  $('#bRun').disabled = !!S.running; $('#bSwap').disabled = !!S.running;
}

async function post(b){
  const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(b)});
  const j=await r.json(); if(j.error){ $('#warn').innerHTML=`<div class=warn>${esc(j.error)}</div>`; return; }
  tail(j.id);
}
window.tail=async function(id){
  curJob=id; off=0; $('#log').textContent=''; $('#jobinfo').textContent='任务 '+id;
  if(timer) clearInterval(timer); timer=setInterval(pump,1200); pump();
};
async function pump(){
  if(!curJob) return;
  const r=await fetch(`/api/log?id=${curJob}&offset=${off}`); const j=await r.json();
  if(j.text){ $('#log').insertAdjacentHTML('beforeend',esc(j.text));
    if(follow) $('#log').scrollTop=$('#log').scrollHeight; }
  off=j.offset;
  $('#jobstat').innerHTML = j.state=='running' ? '<span class=pulse></span>任务运行中' : '空闲';
  $('#jobinfo').textContent='任务 '+curJob+(j.state?(' · '+j.state):'');
  if(j.state!='running'){ clearInterval(timer); timer=null; curJob=null; state(); }
}
$('#bRun').onclick=()=>{
  const stages=[...document.querySelectorAll('#tbl tbody input:not(.appr):checked')].map(x=>x.dataset.k);
  const appr=[...document.querySelectorAll('.appr:checked')].map(x=>x.dataset.k);
  if(appr.length && !confirm('已勾选 '+appr.length+' 个 live 档签字放行：\n  '+appr.join(', ')
      +'\n\n这些会写进 Output/ 或 files/ 的正式产物（换入前会先备份）。确认？')) return;
  post({stages,approve:appr,force:force});
};
$('#bPlan').onclick=()=>post({plan:true});
$('#bSwap').onclick=()=>{
  const appr=['swap-in','derive','regress'];
  if(!confirm('签字换入：这一步会把 .diag/pipeline/ 里的临时产物覆盖进 Output/ 正式目录。\n'+
      '会先备份到 Output/_OLD_bak/，且换入后要过索引零回退闸门与 deploy --check。\n\n确认放行 '+appr.join(' + ')+'？')) return;
  post({stages:appr,approve:['swap-in','derive']});
};
let force=false;
$('#bForce').onclick=e=>{force=!force;e.target.style.borderColor=force?'var(--warn)':'';
  e.target.textContent=force?'绕过缓存：开':'绕过缓存：关'};
$('#bAll').onclick=()=>document.querySelectorAll('#tbl tbody input:not(.appr)').forEach(x=>x.checked=true);
$('#bNone').onclick=()=>document.querySelectorAll('#tbl tbody input').forEach(x=>x.checked=false);
$('#bClear').onclick=()=>$('#log').textContent='';
$('#bFollow').onclick=e=>{follow=!follow;e.target.textContent=follow?'跟随最新':'已暂停跟随'};
$('#lightbox').onclick=e=>e.currentTarget.style.display='none';
document.addEventListener('click',e=>{
  if(e.target.matches('.sheets img')){ $('#lightbox img').src=e.target.src;
    $('#lightbox').style.display='flex'; e.preventDefault(); }});
state(); setInterval(()=>{if(!timer)state();},8000);
</script></body></html>'''


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
    print('=' * 56)
    print('  资产一条龙 · 可视化控制台')
    print('  地址:', url)
    print('  只绑 127.0.0.1；能跑的阶段由 update_pipeline 的白名单决定')
    print('  关闭本窗口即停止控制台（正在跑的流水线任务不会因此中断）')
    print('=' * 56)
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
