# -*- coding: utf-8 -*-
"""取证 2（只读）：判定区是否随动作形变（bbox 与真实四边形的差异）+ breath 层对头部的叠加幅度。
用法: py -3 .diag/l2d_fidelity_probe2.py [皮肤key ...]
"""
import sys, os, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9376
PROFILE = os.path.join(ROOT, '.diag', 'chrome_fidelity2')
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


KEYS = sys.argv[1:] or ['antu_2']
JS = r"""(async(keys)=>{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<90 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
  const res=[];
  for(const key of keys){
    let ship=null, sk=null;
    for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
    if(!sk){ res.push({key, skip:'no skin'}); continue; }
    openShip(ship); setSkin(sk); buildSkinList(ship);
    const l2=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d');
    l2.click();
    const t0=performance.now();
    while(!l2State||!l2State.app||!l2State.app.stage.children.length){ if(performance.now()-t0>40000) break; await t(200); }
    const mdl=l2State.app.stage.children[0], im=mdl.internalModel, core=im.coreModel, mm=im.motionManager;
    const A=[];
    for(const a of (im.settings.hitAreas||[])){ let idx=-1; try{idx=core.getDrawableIndex(a.Id);}catch(e){}
      if(idx<0) continue; const p=core.getDrawableVertexPositions(idx);
      if(!p||p.length!==8) continue;
      const v=[[p[0],p[1]],[p[2],p[3]],[p[4],p[5]],[p[6],p[7]]];
      let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
      for(const q of v){ x0=Math.min(x0,q[0]);x1=Math.max(x1,q[0]);y0=Math.min(y0,q[1]);y1=Math.max(y1,q[1]); }
      const ar=(a,b,c)=>Math.abs((b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1]))/2;
      A.push({name:a.Name, area:ar(v[0],v[1],v[2])+ar(v[1],v[3],v[2]), bb:[x0,y0,x1,y1], v}); }
    const triIn=(x,y,a,b,c)=>{ const d=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);
      if(Math.abs(d)<1e-12) return false;
      const l=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/d, m=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/d;
      return l>=0&&m>=0&&(l+m)<=1; };
    const inQ=(q,x,y)=>triIn(x,y,q[0],q[1],q[2])||triIn(x,y,q[1],q[3],q[2]);
    const CORE=['touch_head','touch_body','touch_special'];
    const pairs=[];
    for(let i=0;i<A.length;i++) for(let j=i+1;j<A.length;j++){
      if(!(CORE.includes(A[i].name)||CORE.includes(A[j].name))) continue;
      const bx0=Math.max(A[i].bb[0],A[j].bb[0]), bx1=Math.min(A[i].bb[2],A[j].bb[2]);
      const by0=Math.max(A[i].bb[1],A[j].bb[1]), by1=Math.min(A[i].bb[3],A[j].bb[3]);
      if(bx1<=bx0||by1<=by0) continue;
      let ov=0, n=40;
      for(let a=0;a<n;a++) for(let b=0;b<n;b++){
        const x=bx0+(bx1-bx0)*a/(n-1), y=by0+(by1-by0)*b/(n-1);
        if(inQ(A[i].v,x,y)&&inQ(A[j].v,x,y)) ov++; }
      const frac=ov/(n*n);
      if(frac>0.002) pairs.push([A[i].name,A[j].name,+frac.toFixed(3),+A[i].area.toFixed(1),+A[j].area.toFixed(1)]);
    }
    pairs.sort((x,y)=>y[2]-x[2]);
    res.push({key, areas:A.length, coreAreas:A.filter(a=>CORE.includes(a.name)).map(a=>a.name+':'+a.area.toFixed(1)),
      fade:mm.motionGroups&&mm.motionGroups.idle&&mm.motionGroups.idle[0]?{in:mm.motionGroups.idle[0].getFadeInTime(),out:mm.motionGroups.idle[0].getFadeOutTime()}:null,
      blink:!!im.eyeBlink, overlaps:pairs.slice(0,10)});
  }
  return JSON.stringify(res,null,1);
})"""
raw = ev(JS + f"({json.dumps(KEYS)})")
path = os.path.join(ROOT, '.diag', '_hit_overlap.json')
with open(path, 'w', encoding='utf-8') as f:
    f.write(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False, indent=1))
print(raw)
ws.close(); proc.terminate()
