# -*- coding: utf-8 -*-
"""全量 Live2D 无头加载扫描：逐条驱动（Python 侧每个模型一次 evaluate），断言
   ① 模型加载成功 ② 动作组解析数 ③ 默认动作真的启动(state.currentGroup 非空)
   ④ 切到另一组动作也启动 ⑤ **内容判据**：目标动作在其播放窗口内真的驱动参数
      （curveCount>0 且跨帧有参数值变化）。

⚠️ 历史缺陷（2026-09-21）：旧版把整个循环塞进**一次** Runtime.evaluate(awaitPromise)，
   换入重建后的动作数据后卡在第一条不返回（单次求值期间 ws 轮询与解析互相阻塞）。
   **2026-09-22 重写**：改为 Python 侧逐条 evaluate；每评估若干模型重载一次页面，规避
   单 Chrome 连续加载大量 Live2D 后 WebGL 上下文耗尽断连（hit_verify 同因在 ~110 个后崩）。

内容判据要点（务必照此，别退回看 currentGroup）：
   - currentGroup 变了不代表有效——"Curves":[] 空壳照样能"启动"（曾误报 260/260 全通过、实际 57% 空壳）。
   - 无头 rAF 被节流：必须手动 PIXI.Ticker.shared.tick()+app.render() 才推进；且 idle 被运行时
     解析成非循环（全模型一致），要在 clip 时长内高频密采参数跨帧 min/max，晚采样会假报不动。

用法: py -3 scripts/diag/l2d_sweep.py [--limit N] [--only a,b,c] [--recycle M] [--per S]
      （需先在 Output 根起 http.server 8777： py -3 -m http.server 8777 -b 127.0.0.1 -d Output）
输出: .diag/l2d_sweep.json + 进度 .diag/l2d_sweep.log
"""
import sys, os, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = int(os.environ.get('L2D_SWEEP_PORT', '9338'))
SRV_PORT = int(os.environ.get('L2D_SWEEP_SRV', '8777'))
URL = f'http://127.0.0.1:{SRV_PORT}/gallery_v2/index.html'
DEBUG = os.path.join(ROOT, '.diag', 'chrome_l2d_sweep')
LOG = os.path.join(ROOT, '.diag', 'l2d_sweep.log')
OUT = os.path.join(ROOT, '.diag', 'l2d_sweep.json')

def arg(name, default=None, cast=str):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default

limit = arg('--limit', 0, int)
only = [x for x in (arg('--only', '') or '').split(',') if x]
recycle_n = arg('--recycle', 60, int)   # 每评估多少个模型重载一次页面（回收 WebGL 上下文）
per_samples = arg('--per', 8, int)      # 内容判据密采帧数

idx = json.load(open(os.path.join(ROOT, 'Output', 'gallery_v2', 'index.json'), encoding='utf-8'))
items = []
for s in idx['ships']:
    for sk in s['skins']:
        if sk.get('live2d'):
            items.append({'ship': s['id'], 'key': sk['key'], 'dir': sk['live2d'],
                          'base': sk.get('live2dBase') or sk['key']})
if only:
    items = [it for it in items if it['key'] in only] or [{'key': k} for k in only]
if limit:
    items = items[:limit]
print(f'待扫 {len(items)} 个 Live2D 皮肤（逐条驱动，每 {recycle_n} 个重载页面，密采 {per_samples} 帧）', flush=True)

# 起本地服务器（若 8777 未被占用）
def srv_alive():
    try:
        return urllib.request.urlopen(URL, timeout=2).status == 200
    except Exception:
        return False
srv = None
if not srv_alive():
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(SRV_PORT), '-b', '127.0.0.1',
                            '-d', os.path.join(ROOT, 'Output')],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        if srv_alive():
            break
        time.sleep(0.5)

def kill_stale(ud):
    ps = ("$ErrorActionPreference='SilentlyContinue';"
          "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
          "Where-Object { $_.CommandLine -like '*%s*' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % ud)
    subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

kill_stale(DEBUG)
proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
  '--remote-allow-origins=*', f'--user-data-dir={DEBUG}', '--no-first-run', '--no-default-browser-check',
  '--disable-background-timer-throttling', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--js-flags=--max-old-space-size=4096', '--window-size=1280,900', URL],
  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ws_url = None
for _ in range(80):
    try:
        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
        c = [t['webSocketDebuggerUrl'] for t in tabs if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
        if c:
            ws_url = c[0]; break
    except Exception:
        pass
    time.sleep(0.5)
ws = websocket.create_connection(ws_url, timeout=180, max_size=None)
_id = 0
def cmd(method, params=None, timeout=180):
    global _id; _id += 1; mid = _id
    ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
    ws.settimeout(timeout)
    while True:
        m = json.loads(ws.recv())
        if m.get('id') == mid:
            if 'error' in m:
                raise RuntimeError(json.dumps(m['error'])[:200])
            return m.get('result', {})
def ev(expr, timeout=120):
    r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True}, timeout)
    if r.get('exceptionDetails'):
        return json.dumps({'err': str(r['exceptionDetails'].get('text') or r['exceptionDetails'].get('exception', {}).get('description'))[:160]})
    v = r.get('result', {}).get('value')
    return v if v is not None else 'null'

cmd('Page.enable'); cmd('Runtime.enable')

def wait_ready(timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if ev("typeof GALLERY!=='undefined' && typeof renderLive2D==='function'", timeout=15) is True:
            return True
        time.sleep(0.5)
    return False

def reload_page():
    try:
        cmd('Page.navigate', {'url': URL}, timeout=30)
    except Exception:
        pass
    return wait_ready()

# 单模型：加载 + 默认/切组 + 内容判据（密采参数 min/max）。一次 evaluate 返回一条记录。
def sweep_one(it):
    return f"""(async () => {{ try {{
      const t=ms=>new Promise(r=>setTimeout(r,ms));
      const it={json.dumps(it)};
      const rec={{ship:it.ship,key:it.key,dir:it.dir}};
      const s=GALLERY.ships.find(x=>x.id===it.ship);
      const sk=s && s.skins.find(k=>k.key===it.key);
      if(!sk){{ return JSON.stringify(Object.assign(rec,{{fail:'skin missing'}})); }}
      stopLive2D();
      await renderLive2D(s, sk);
      await t(1500);
      const app=l2State && l2State.app;
      if(!app) return JSON.stringify(Object.assign(rec,{{fail:'no app',note:(document.querySelector('.note')||{{}}).textContent||''}}));
      const m=app.stage.children[0];
      if(!m) return JSON.stringify(Object.assign(rec,{{fail:'no model'}}));
      const mm=m.internalModel.motionManager, core=m.internalModel.coreModel;
      const defs=mm.definitions||{{}};
      rec.groups=Object.keys(defs).length;
      rec.defGroup=(mm.state && mm.state.currentGroup)||null;
      rec.defPriority=(mm.state && mm.state.currentPriority);
      // 切到另一组验证切换生效
      const other=Object.keys(defs).find(g=>g!==rec.defGroup);
      if(other){{ mm.startMotion(other,0,(PIXI.live2d.MotionPriority||{{FORCE:3}}).FORCE); await t(600);
        rec.switchedTo=(mm.state && mm.state.currentGroup)||null; rec.switchOK=(rec.switchedTo===other); }}
      else rec.switchedTo='only-one-group';
      // 内容判据：选一个真实存在的动作组（优先 idle），FORCE 播，密采全参数跨帧 min/max
      const target=defs['idle']?'idle':(other||Object.keys(defs)[0]||null);
      if(target){{
        mm.startMotion(target,0,(PIXI.live2d.MotionPriority||{{FORCE:3}}).FORCE);
        await t(1200);
        try{{ const mo=mm.motionManager? null:null; }}catch(e){{}}
        const ids=(core._parameterIds||[]).slice(0,500);
        const mn={{}},mx={{}}; ids.forEach(id=>{{mn[id]=Infinity;mx[id]=-Infinity;}});
        for(let f=0;f<{per_samples};f++){{
          for(let k=0;k<2;k++){{ try{{ PIXI.Ticker.shared.tick(performance.now()); }}catch(e){{}} try{{ app.render(); }}catch(e){{}} }}
          ids.forEach(id=>{{ let v; try{{ v=core.getParameterValueById(id); }}catch(e){{}} if(typeof v==='number'){{ if(v<mn[id])mn[id]=v; if(v>mx[id])mx[id]=v; }} }});
          await t(230);
        }}
        rec.movedParams=ids.filter(id=>isFinite(mn[id])&&(mx[id]-mn[id])>1e-3).length;
        rec.contentOK=rec.movedParams>0;
      }} else {{ rec.contentOK=false; }}
      rec.tex=(m.internalModel.textures||[]).length;
      rec.w=Math.round(m.width); rec.h=Math.round(m.height);
      return JSON.stringify(rec);
    }} catch(e) {{ return JSON.stringify({{key:(typeof it!=='undefined'&&it.key)||'?', fail:(''+(e&&e.message||e)).slice(0,160)}}); }} }})()"""

data = []
t0 = time.time()
need_ready = wait_ready()
for i, it in enumerate(items):
    if not need_ready:
        print(f'  [{i}] 页面未就绪，重载…', flush=True)
        need_ready = reload_page()
    try:
        raw = ev(sweep_one(it), timeout=120)
        try:
            rec = json.loads(raw)
        except Exception:
            rec = {'key': it['key'], 'fail': 'parse', 'raw': str(raw)[:160]}
    except Exception as e:
        rec = {'key': it['key'], 'fail': 'eval ' + str(e)[:120]}
        need_ready = False   # 连接可能已坏，下一条前重载
    rec['_i'] = i
    data.append(rec)
    flag = 'OK' if rec.get('contentOK') else ('FAIL' if rec.get('fail') else 'STATIC')
    line = (f"[{int(time.time()-t0):5d}s] {i+1}/{len(items)} {rec.get('key'):18s} {flag:6s} "
            f"groups={rec.get('groups')} def={rec.get('defGroup')} moved={rec.get('movedParams')}"
            + (f" fail={rec.get('fail')}" if rec.get('fail') else ''))
    print(line, flush=True); open(LOG, 'a', encoding='utf-8').write(line + '\n')
    # 每 recycle_n 个或连接异常后重载页面回收上下文
    if (i + 1) % recycle_n == 0:
        need_ready = reload_page()

json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
fails = [r for r in data if r.get('fail')]
nomot = [r['key'] for r in data if not r.get('fail') and not r.get('defGroup')]
nosw = [r['key'] for r in data if r.get('switchedTo') and r.get('switchOK') is False]
static = [r['key'] for r in data if not r.get('fail') and r.get('contentOK') is False]
print(f"\n总计 {len(data)} | 失败 {len(fails)} | 默认动作未启动 {len(nomot)} | 切动作未生效 {len(nosw)}")
print(f"内容判据: 未驱动任何参数(疑似空壳/静态) {len(static)}")
print('失败:', [(r['key'], r['fail']) for r in fails][:30])
print('默认动作未启动:', nomot[:40])
print('切动作未生效:', nosw[:40])
print('内容判据未过(不动):', static[:60])
try:
    ws.close()
except Exception:
    pass
proc.terminate()
if srv:
    srv.terminate()
print(f"\n耗时 {int(time.time()-t0)}s，明细见 {OUT}")
