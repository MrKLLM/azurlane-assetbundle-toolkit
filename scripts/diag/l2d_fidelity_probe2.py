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

JS = r"""(async(keys)=>{
  const t=ms=>new Promise(r=>setTimeout(r,ms)); const LIMIT1=keys.length===1;
  for(let i=0;i<90 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
  const res=[];
  for(const key of keys){
    let ship=null, sk=null;
    for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
    if(!sk){ res.push({key, skip:'no skin'}); continue; }
    openShip(ship); setSkin(sk); buildSkinList(ship);
    const l2=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d');
    l2.click(); await t(7000);
    const mdl=l2State.app.stage.children[0], im=mdl.internalModel, core=im.coreModel;
    const snap=()=>{ const o={};
      for(const a of (im.settings.hitAreas||[])){ let idx=-1; try{idx=core.getDrawableIndex(a.Id);}catch(e){}
        if(idx<0) continue; const p=core.getDrawableVertexPositions(idx); o[a.Name]=Array.from(p).slice(0,8); } return o; };
    const s1=snap(); await t(3000); const s2=snap();
    /* 四边形面积（strip 分解 v0v1v2 + v1v3v2） vs 包围盒面积；以及 3 秒内框的形变/位移 */
    /* 凸包面积：与顶点顺序无关（4 点判定标记即真实四边形面积） */
    const quad=(v)=>{ if(!v||v.length<8) return null;
      const P=[]; for(let k=0;k+1<v.length;k+=2) P.push([v[k],v[k+1]]);
      P.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
      const cr=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);
      const H=[]; for(const q of P){ while(H.length>=2&&cr(H[H.length-2],H[H.length-1],q)<=0) H.pop(); H.push(q); }
      const L=[]; for(let i=P.length-1;i>=0;i--){ const q=P[i]; while(L.length>=2&&cr(L[L.length-2],L[L.length-1],q)<=0) L.pop(); L.push(q); }
      H.pop(); L.pop(); const hull=H.concat(L); let a=0;
      for(let i=0;i<hull.length;i++){ const p=hull[i], q=hull[(i+1)%hull.length]; a+=p[0]*q[1]-q[0]*p[1]; }
      const hullArea=Math.abs(a/2);
      /* 三角带序 (v0,v1,v2)+(v1,v3,v2) 的面积——产品侧命中判定用的就是它，
         必须与凸包面积一致，否则说明顶点不是带序，判定会整批脱靶 */
      const ta=(i,j,k)=>Math.abs((P[j][0]-P[i][0])*(P[k][1]-P[i][1])-(P[k][0]-P[i][0])*(P[j][1]-P[i][1]))/2;
      const stripArea = P.length===4 ? ta(0,1,2)+ta(1,3,2) : null;
      return {hullArea, stripArea}; };
    const bbox=(v)=>{ let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
      for(let k=0;k+1<v.length;k+=2){ if(v[k]<x0)x0=v[k]; if(v[k]>x1)x1=v[k]; if(v[k+1]<y0)y0=v[k+1]; if(v[k+1]>y1)y1=v[k+1]; }
      return {a:(x1-x0)*(y1-y0), r:[x0,y0,x1,y1]}; };
    const areas=[];
    for(const nm of Object.keys(s1)){ const v=s1[nm]; const q=quad(v), b=bbox(v);
      const v2=s2[nm]||v; const moved=Math.max(...Array.from({length:4},(_,i)=>Math.abs(v2[i*2]-v[i*2])+Math.abs(v2[i*2+1]-v[i*2+1])));
      areas.push({name:nm, verts:v.length/2, hullArea:q?+q.hullArea.toFixed(3):null, stripArea:q?+q.stripArea.toFixed(3):null,
        stripEqHull:(q&&q.stripArea!=null)?Math.abs(q.stripArea-q.hullArea)<1e-3*Math.max(1,q.hullArea):null,
        bboxArea:+b.a.toFixed(3), fill:q?+(q.hullArea/b.a).toFixed(3):null, drift3s:+moved.toFixed(3)}); }
    /* breath 叠加幅度：连续采 2.5s 的 ParamAngleX/Y/Z 极差，与关掉 breath 后对比 */
    const pid=['ParamAngleX','ParamAngleY','ParamAngleZ','ParamBodyAngleX','ParamBreath'];
    const sample=(ms)=>{ const idx=pid.map(n=>core.getParameterIndex(n)); const mn=idx.map(()=>1e9), mx=idx.map(()=>-1e9);
      return new Promise(rs=>{ const end=performance.now()+ms;
        const f=()=>{ for(let i=0;i<idx.length;i++){ if(idx[i]<0) continue; const v=core.getParameterValueByIndex(idx[i]);
            if(v<mn[i])mn[i]=v; if(v>mx[i])mx[i]=v; }
          if(performance.now()<end) requestAnimationFrame(f); else rs(pid.map((n,i)=>({id:n, span:+(mx[i]-mn[i]).toFixed(2)}))); };
        f(); }); };
    res.push({key, areas}); if(LIMIT1) return JSON.stringify(res,null,1);
    const withBreath=await sample(2600);
    const saved=im.breath.getParameters(); im.breath.setParameters([]);
    await t(400); const noBreath=await sample(2600);
    im.breath.setParameters(saved);
    res.push({key, areas, angleSpan:{withBreath, noBreath}});
  }
  return JSON.stringify(res,null,1);
})"""
KEYS = sys.argv[1:] or ['antu_2']
raw = ev(JS + f"({json.dumps(KEYS)})")
path = os.path.join(ROOT, '.diag', '_fidelity_probe2.json')
with open(path, 'w', encoding='utf-8') as f:
    f.write(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False, indent=1))
print(raw)
print(f"\n已写出 {path}")
ws.close(); proc.terminate()
