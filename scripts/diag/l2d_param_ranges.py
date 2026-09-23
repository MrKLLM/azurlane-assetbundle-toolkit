# -*- coding: utf-8 -*-
"""导出某模型全部参数的 (min,max,default) —— 与 motion3.json 曲线实际驱动范围对照，
用于定位「曲线超出合法量程被 Cubism 硬钳 → 部件卡到极值再弹回」这类系统性失真。
用法: py -3 .diag/l2d_param_ranges.py antu_2
输出: .diag/_param_ranges_<key>.json
"""
import sys, os, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9379
PROFILE = os.path.join(ROOT, '.diag', 'chrome_ranges')
os.makedirs(PROFILE, exist_ok=True)
KEY = sys.argv[1] if len(sys.argv) > 1 else 'antu_2'
proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
  '--remote-allow-origins=*', f'--user-data-dir={PROFILE}', '--no-first-run',
  '--no-default-browser-check', '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
  '--use-angle=swiftshader', '--window-size=1280,900',
  'http://127.0.0.1:8777/gallery_v2/index.html'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
w = None
for _ in range(90):
    try:
        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
        w = [t['webSocketDebuggerUrl'] for t in tabs if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
        if w: break
    except Exception: pass
    time.sleep(0.5)
ws = websocket.create_connection(w[0], timeout=240, max_size=None)
_id = 0
def cmd(m, p=None):
    global _id; _id += 1; mid = _id
    ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}})); ws.settimeout(240)
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == mid:
            if 'error' in r: raise RuntimeError(json.dumps(r['error'])[:200])
            return r.get('result', {})
def ev(e):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    if r.get('exceptionDetails'): return 'EVALERR ' + str(r.get('exceptionDetails'))[:300]
    return r.get('result', {}).get('value')

JS = r"""(async(key)=>{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<90 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  const l2=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d');
  l2.click();
  const t0=performance.now();
  while(!l2State||!l2State.app||!l2State.app.stage.children.length){ if(performance.now()-t0>40000) break; await t(200); }
  const im=l2State.app.stage.children[0].internalModel, core=im.coreModel;
  const ids=core._parameterIds||[]; const out={};
  for(let i=0;i<core.getParameterCount();i++){
    const nm=(ids[i]&&ids[i].string)||ids[i]||('Param#'+i);
    out[nm]=[core.getParameterMinimumValue(i), core.getParameterMaximumValue(i), core.getParameterDefaultValue(i)];
  }
  return JSON.stringify({key, count:core.getParameterCount(), ranges:out});
})"""
raw = ev(JS + f"({json.dumps(KEY)})")
path = os.path.join(ROOT, f'.diag/_param_ranges_{KEY}.json')
with open(path, 'w', encoding='utf-8') as f:
    f.write(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))
d = json.loads(raw) if isinstance(raw, str) else raw
print('params:', d.get('count'), '→', path)
ws.close(); proc.terminate()
