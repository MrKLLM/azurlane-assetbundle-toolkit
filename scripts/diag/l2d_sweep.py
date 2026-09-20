# -*- coding: utf-8 -*-
"""全量 Live2D 无头加载扫描：逐个渲染 260 个模型，断言
   ① 模型加载成功 ② 动作组解析 ③ 默认动作真的启动(state.currentGroup 非空) ④ 切到另一组动作也启动
用法: py -3 .diag/l2d_sweep.py [--limit N]
输出: .diag/l2d_sweep.json + 进度 .diag/l2d_sweep.log
"""
import sys, os, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9338
DEBUG = os.path.join(ROOT, '.diag', 'chrome_l2d_sweep')
LOG = os.path.join(ROOT, '.diag', 'l2d_sweep.log')
OUT = os.path.join(ROOT, '.diag', 'l2d_sweep.json')
limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else 0

idx = json.load(open(os.path.join(ROOT, 'Output', 'gallery_v2', 'index.json'), encoding='utf-8'))
items = []
for s in idx['ships']:
    for sk in s['skins']:
        if sk.get('live2d'):
            items.append({'ship': s['id'], 'key': sk['key'], 'dir': sk['live2d'], 'base': sk.get('live2dBase') or sk['key']})
if limit:
    items = items[:limit]
print(f'待扫 {len(items)} 个 Live2D 皮肤', flush=True)

proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
  '--remote-allow-origins=*', f'--user-data-dir={DEBUG}', '--no-first-run', '--no-default-browser-check',
  '--disable-background-timer-throttling', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--js-flags=--max-old-space-size=4096', '--window-size=1280,900',
  'http://127.0.0.1:8777/gallery_v2/index.html'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ws_url = None
for _ in range(80):
    try:
        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
        c = [t['webSocketDebuggerUrl'] for t in tabs if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
        if c: ws_url = c[0]; break
    except Exception: pass
    time.sleep(0.5)
ws = websocket.create_connection(ws_url, timeout=180, max_size=None)
_id = 0
def cmd(method, params=None, timeout=180):
    global _id; _id += 1
    mid = _id
    ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
    ws.settimeout(timeout)
    while True:
        m = json.loads(ws.recv())
        if m.get('id') == mid: return m.get('result', {})
def ev(expr, timeout=180):
    r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True}, timeout)
    if r.get('exceptionDetails'): return json.dumps({'err': str(r['exceptionDetails'].get('text'))[:160]})
    v = r.get('result', {}).get('value')
    return v if v is not None else 'null'

# 注入清单，页面内串行跑
ev(f"window.__ITEMS={json.dumps(items)}; window.__RES=[]; window.__DONE=false; window.__IDX=0;")
BOOT = r"""
(async () => {
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  window.__RUNNING=true;
  for (let i=0;i<__ITEMS.length;i++){
    const it=__ITEMS[i]; __IDX=i;
    let rec={ship:it.ship,key:it.key,dir:it.dir};
    try{
      const s=GALLERY.ships.find(x=>x.id===it.ship);
      const sk=s && s.skins.find(k=>k.key===it.key);
      if(!sk){ rec.fail='skin missing in GALLERY'; __RES.push(rec); continue; }
      stopLive2D();
      await renderLive2D(s, sk);
      await t(1500);   // startMotion 内部要 fetch motion3.json，需等一拍再读 state
      const app=l2State && l2State.app;
      if(!app){ rec.fail='no app'; __RES.push(rec); continue; }
      const m=app.stage.children[0];
      if(!m){ rec.fail='no model'; __RES.push(rec); continue; }
      const mm=m.internalModel.motionManager;
      rec.groups=Object.keys(mm.definitions||{}).length;
      rec.defGroup=mm.state && mm.state.currentGroup || null;
      rec.defPriority=mm.state && mm.state.currentPriority;
      const other=Object.keys(mm.definitions||{}).find(g=>g!==rec.defGroup);
      if(other){ mm.startMotion(other,0,(PIXI.live2d.MotionPriority||{FORCE:3}).FORCE); await t(600);
                 rec.switchedTo=mm.state.currentGroup; rec.switchOK=(mm.state.currentGroup===other); }
      else rec.switchedTo='only-one-group';
      rec.tex=(m.internalModel.textures||[]).length;
      rec.w=Math.round(m.width); rec.h=Math.round(m.height);
      __RES.push(rec);
    }catch(e){ rec.fail=(''+(e&&e.message||e)).slice(0,160); __RES.push(rec); }
    if(i%10===0){ try{ app2=l2State&&l2State.app; }catch(_){} }
  }
  stopLive2D(); window.__DONE=true; window.__RUNNING=false;
  return 'finished';
})()
"""
ws.send(json.dumps({'id': 999999, 'method': 'Runtime.evaluate',
                    'params': {'expression': BOOT, 'awaitPromise': True, 'returnByValue': True}}))
t0 = time.time()
last = -1
while time.time() - t0 < 3600:
    prog = ev("(function(){return __IDX+'/'+__RES.length+'/'+(__DONE?'DONE':'RUN')})()", timeout=30)
    try:
        cur = int(str(prog).split('/')[1])
    except Exception:
        cur = last
    if cur != last:
        line = f'[{int(time.time()-t0):5d}s] 进度 {prog}'
        print(line, flush=True)
        open(LOG, 'a', encoding='utf-8').write(line + '\n')
        last = cur
    if str(prog).endswith('DONE') or '/DONE/' in str(prog):
        break
    time.sleep(4)

res = ev("JSON.stringify(__RES)")
data = json.loads(res) if isinstance(res, str) else res
json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
fails = [r for r in data if r.get('fail')]
nomot = [r['key'] for r in data if not r.get('fail') and not r.get('defGroup')]
nosw = [r['key'] for r in data if r.get('switchedTo') and r.get('switchOK') is False]
print(f"\n总计 {len(data)} | 失败 {len(fails)} | 默认动作未启动 {len(nomot)} | 切动作未生效 {len(nosw)}")
print('失败:', [(r['key'], r['fail']) for r in fails][:20])
print('默认动作未启动:', nomot[:30])
print('切动作未生效:', nosw[:30])
ws.close(); proc.terminate()
