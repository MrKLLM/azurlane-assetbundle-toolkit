# -*- coding: utf-8 -*-
"""取证（只读）：播 touch_idle* 之后，Touch* 判定标记是否跟着部件移出画布 / 塌成零面积。
用法: py -3 .diag/l2d_touchidle_probe.py antu_2 touch_idle1
"""
import sys, os, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9381
PROFILE = os.path.join(ROOT, '.diag', 'chrome_touchidle')
os.makedirs(PROFILE, exist_ok=True)
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
ws = websocket.create_connection(w[0], timeout=300, max_size=None)
_id = 0
def cmd(m, p=None):
    global _id; _id += 1; mid = _id
    ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}})); ws.settimeout(300)
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == mid:
            if 'error' in r: raise RuntimeError(json.dumps(r['error'])[:200])
            return r.get('result', {})
def ev(e):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    if r.get('exceptionDetails'): return 'EVALERR ' + str(r.get('exceptionDetails'))[:300]
    return r.get('result', {}).get('value')

JS = r"""(async(args)=>{ const key=args[0], grp=args[1];
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
  const mdl=l2State.app.stage.children[0], im=mdl.internalModel, core=im.coreModel, mm=im.motionManager;
  const cux=im.width/(im.pixelsPerUnit||1), cuy=im.height/(im.pixelsPerUnit||1);
  const snap=()=>{ const o={};
    for(const a of (im.settings.hitAreas||[])){ let idx=-1; try{idx=core.getDrawableIndex(a.Id);}catch(e){}
      if(idx<0){ o[a.Name]={miss:true}; continue; }
      const p=core.getDrawableVertexPositions(idx);
      if(!p||p.length<8){ o[a.Name]={bad:p?p.length:0}; continue; }
      let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
      for(let k=0;k+1<p.length;k+=2){ x0=Math.min(x0,p[k]);x1=Math.max(x1,p[k]);y0=Math.min(y0,p[k+1]);y1=Math.max(y1,p[k+1]); }
      o[a.Name]={cx:+((x0+x1)/2).toFixed(2), cy:+((y0+y1)/2).toFixed(2),
                 w:+(x1-x0).toFixed(3), h:+(y1-y0).toFixed(3)}; }
    return o; };
  const before=snap();
  const MP=(PIXI.live2d&&PIXI.live2d.MotionPriority)||{IDLE:1,NORMAL:2,FORCE:3};
  mm.startMotion(grp,0,MP.FORCE);
  await t(4000);
  const mid=snap();
  await t(6000);
  const after=snap();
  const inCanvas=(q)=>q && !q.miss && !q.bad && Math.abs(q.cx)<=cux/2 && Math.abs(q.cy)<=cuy/2;
  const stat=(s)=>{ let n=0,off=0,tiny=0,miss=0;
    for(const k in s){ const q=s[k]; if(q.miss){miss++;continue;} n++;
      if(q.w<0.02||q.h<0.02) tiny++;
      if(!inCanvas(q)) off++; }
    return {areas:n, outsideCanvas:off, collapsed:tiny, unresolved:miss}; };
  const moved=[];
  for(const k in before){ const a=before[k], b=after[k];
    if(!a.cx||!b.cx) continue;
    const d=Math.hypot(b.cx-a.cx, b.cy-a.cy);
    if(d>0.3) moved.push([k,+d.toFixed(2), [a.cx,a.cy], [b.cx,b.cy]]); }
  moved.sort((x,y)=>y[1]-x[1]);
  return JSON.stringify({key, grp, canvas:[+cux.toFixed(2),+cuy.toFixed(2)],
    idleNow:mm.state.currentGroup, before:stat(before), mid:stat(mid), after:stat(after),
    movedCount:moved.length, movedSample:moved.slice(0,10)}, null, 1);
})"""
args = sys.argv[1:] or ['antu_2', 'touch_idle1']
raw = ev(JS + f"({json.dumps(args)})")
path = os.path.join(ROOT, '.diag', '_touchidle.json')
with open(path, 'w', encoding='utf-8') as f:
    f.write(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False, indent=1))
print(raw)
print(f"\n已写出 {path}")
ws.close(); proc.terminate()
