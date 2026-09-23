# -*- coding: utf-8 -*-
"""改后验收（只读）：Live2D 四项体检
  ① 补丁是否生效：breath 参数数=0 / idle 的 isLoop=true 且 loopFadeIn=false / groups.idle 已对齐
  ② 30s 内 idle 是否还有「播完冻结」：currentGroup=null 的采样点数必须为 0，startMotion 调用数应为 0
  ③ 点部位 → 播对应反应 → 自动回落 idle 并继续循环（交叉淡入淡出期间队列应有 2 条）
  ④ 斜框模型：四边形判定相对包围盒收窄了多少（bbox 命中但 quad 不命中的面积占比）
用法: py -3 .diag/l2d_after_fix_check.py [key ...]
"""
import sys, os, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9378
PROFILE = os.path.join(ROOT, '.diag', 'chrome_afterfix')
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
    if r.get('exceptionDetails'): return 'EVALERR ' + str(r.get('exceptionDetails'))[:400]
    return r.get('result', {}).get('value')

JS = r"""(async(keys)=>{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<90 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
  const res=[];
  for(const key of keys){
    const o={key};
    let ship=null, sk=null;
    for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
    if(!sk){ o.skip='no skin'; res.push(o); continue; }
    openShip(ship); setSkin(sk); buildSkinList(ship);
    const l2=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d');
    l2.click();
    const t0=performance.now();
    while(!l2State||!l2State.app||!l2State.app.stage.children.length){ if(performance.now()-t0>40000) break; await t(200); }
    if(!l2State||!l2State.app||!l2State.app.stage.children.length){ o.skip='model not ready'; res.push(o); continue; }
    const mdl=l2State.app.stage.children[0], im=mdl.internalModel, core=im.coreModel, mm=im.motionManager;
    const gs=Object.keys(mm.definitions||{}); const idleGroup=['idle','main','home'].find(g=>gs.includes(g))||gs[0]||null;
    /* ① 补丁体检 */
    const arr=(mm.motionGroups&&mm.motionGroups[idleGroup])||[]; const m0=arr[0];
    o.health={ groupsIdle:mm.groups&&mm.groups.idle, idleGroup,
      breathParams:(im.breath&&im.breath.getParameters?im.breath.getParameters().length:'n/a'),
      idle:(m0&&m0.isLoop)?{isLoop:m0.isLoop(),loopFadeIn:m0.isLoopFadeIn(),dur:m0.getDuration(),loopDur:m0.getLoopDuration()}:'not-loaded' };
    /* ② 30s 冻结观察 */
    const starts=[]; const orig=mm.startMotion.bind(mm);
    mm.startMotion=function(g,i,p){ starts.push({g,p,at:+((performance.now()-t0)/1000).toFixed(2)}); return orig(g,i,p); };
    let nulls=0, ns=0; const end=performance.now()+30000;
    while(performance.now()<end){ const s=mm.state.currentGroup||null; ns++; if(s===null) nulls++; await t(250); }
    mm.startMotion=orig;
    o.idle30s={samples:ns, nullSamples:nulls, startMotionCalls:starts.length,
               grp:mm.state.currentGroup||null, entries:mm.queueManager._motions.length};
    /* ③ 点第一个判定框中心 → 播对应反应 → 回落 idle 且不再冻结 */
    const areas=(im.settings.hitAreas||[]);
    if(areas.length){ const a=areas[0]; const idx=core.getDrawableIndex(a.Id); const p=core.getDrawableVertexPositions(idx);
      let sx=0,sy=0,n=0; for(let k=0;k+1<p.length;k+=2){sx+=p[k];sy+=p[k+1];n++;}
      const cux2=im.width/(im.pixelsPerUnit||1), cuy2=im.height/(im.pixelsPerUnit||1);
      const wrap=document.getElementById('l2wrap'), rect=wrap.getBoundingClientRect();
      const gp=mdl.toGlobal(new PIXI.Point((sx/n+cux2/2)*(im.pixelsPerUnit||1), (cuy2/2-sy/n)*(im.pixelsPerUnit||1)));
      const e={bubbles:true,cancelable:true,pointerId:21,clientX:rect.left+gp.x,clientY:rect.top+gp.y,button:0};
      wrap.dispatchEvent(new PointerEvent('pointerdown',e)); window.dispatchEvent(new PointerEvent('pointerup',e));
      await t(600);
      o.click={want:a.Name, played:mm.state.currentGroup||null, entriesDuringFade:mm.queueManager._motions.length,
               pill:(document.getElementById('l2Hit')||{}).textContent};
      /* 等它播完（最长 20s）再看是否回 idle */
      let back=null, nullAfter=0, k=0;
      while(k++<80){ const g=mm.state.currentGroup||null; if(g===null) nullAfter++;
        if(g===idleGroup && k>6){ back={at:k*0.25, nullAfter}; break; } await t(250); }
      o.click.returnedToIdle=back; o.click.nullSamplesAfterClick=nullAfter;
    }
    /* ④ 四边形 vs 包围盒 收窄率（网格采样，与产品侧同语义） */
    const triIn=(x,y,A,B,C)=>{ const d=(B[1]-C[1])*(A[0]-C[0])+(C[0]-B[0])*(A[1]-C[1]);
      if(Math.abs(d)<1e-12) return false;
      const l=((B[1]-C[1])*(x-C[0])+(C[0]-B[0])*(y-C[1]))/d, m=((C[1]-A[1])*(x-C[0])+(A[0]-C[0])*(y-C[1]))/d;
      return l>=-0.02&&m>=-0.02&&(l+m)<=1.04; };
    const G=[];
    for(const a of areas){ const idx=core.getDrawableIndex(a.Id); const p=core.getDrawableVertexPositions(idx);
      if(!p||p.length!==8) continue;
      let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
      for(let k=0;k+1<p.length;k+=2){x0=Math.min(x0,p[k]);x1=Math.max(x1,p[k]);y0=Math.min(y0,p[k+1]);y1=Math.max(y1,p[k+1]);}
      G.push({name:a.Name,x0,y0,x1,y1,v:[[p[0],p[1]],[p[2],p[3]],[p[4],p[5]],[p[6],p[7]]]}); }
    if(G.length){ let inBox=0, inQuad=0, over=0; const N=200;
      const bx0=Math.min(...G.map(g=>g.x0)), bx1=Math.max(...G.map(g=>g.x1));
      const by0=Math.min(...G.map(g=>g.y0)), by1=Math.max(...G.map(g=>g.y1));
      for(let i=0;i<N;i++) for(let j=0;j<N;j++){ const x=bx0+(bx1-bx0)*i/(N-1), y=by0+(by1-by0)*j/(N-1);
        let b=null,q=null;
        for(const g of G){ const hw=(g.x1-g.x0)/2, hh=(g.y1-g.y0)/2;
          const inb = x>=g.x0-hw*0.02&&x<=g.x1+hw*0.02&&y>=g.y0-hh*0.02&&y<=g.y1+hh*0.02;
          if(inb && b===null) b=g.name;
          if(q===null && (triIn(x,y,g.v[0],g.v[1],g.v[2])||triIn(x,y,g.v[1],g.v[3],g.v[2]))) q=g.name; }
        if(b||q){ inBox+= (b?1:0); inQuad += (q?1:0); if(b&&!q) over++; } }
      o.hit={boxHits:inBox, quadHits:inQuad, boxOnlyHits:over, shrink:+(over/Math.max(1,inBox)).toFixed(3)}; }
    res.push(o);
  }
  return JSON.stringify(res,null,1);
})"""
KEYS = sys.argv[1:] or ['antu_2']
raw = ev(JS + f"({json.dumps(KEYS)})")
path = os.path.join(ROOT, '.diag', '_after_fix_check.json')
with open(path, 'w', encoding='utf-8') as f:
    f.write(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False, indent=1))
print(raw)
print(f"\n已写出 {path}")
ws.close(); proc.terminate()
