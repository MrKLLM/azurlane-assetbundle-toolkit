# -*- coding: utf-8 -*-
"""验证「按部位点击触发对应动作」：对若干模型，把每个 HitArea 的几何中心换算成屏幕坐标，
   派发 pointerdown/pointerup，断言 motionManager.state.currentGroup == 该部位对应的动作组。
用法: py -3 scripts/diag/hit_verify.py [--limit N]   # 不给 --limit 即全量
"""
import sys, os, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9342
limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else 0
only = [x for x in (sys.argv[sys.argv.index('--only')+1] if '--only' in sys.argv else '').split(',') if x]

idx = json.load(open(os.path.join(ROOT, 'Output', 'gallery_v2', 'index.json'), encoding='utf-8'))
cands = []
for s in idx['ships']:
    for sk in s['skins']:
        if sk.get('live2d'):
            cands.append(sk['key'])        # 覆盖全部带 live2d 的皮肤，不只取每船第一个
    if limit and len(cands) >= limit: break
if only: cands = [c for c in cands if c in only] or only
if limit: cands = cands[:limit]

proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
  '--remote-allow-origins=*', f'--user-data-dir={ROOT}/.diag/chrome_hitv', '--no-first-run',
  '--no-default-browser-check', '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
  '--use-angle=swiftshader', '--window-size=1280,900', 'http://127.0.0.1:8777/gallery_v2/index.html'],
  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
w = None
for _ in range(80):
    try:
        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
        w = [t['webSocketDebuggerUrl'] for t in tabs if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
        if w: break
    except Exception: pass
    time.sleep(0.5)
ws = websocket.create_connection(w[0], timeout=120, max_size=None)
_id = 0
def cmd(m, p=None, t=120):
    global _id; _id += 1; mid = _id
    ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}}))
    ws.settimeout(t)
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == mid: return r.get('result', {})
def ev(e, t=120):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True}, t)
    if r.get('exceptionDetails'): return json.dumps({'err': str(r['exceptionDetails'].get('text'))[:180]})
    return r.get('result', {}).get('value')

ev("for(let i=0;i<80 && !window.GALLERY;i++){}; 'ready'")
JS = r"""(async key => { try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  stopLive2D(); await renderLive2D(ship, sk); await t(2000);
  const m=l2State.app.stage.children[0]; const im=m.internalModel; const core=im.coreModel;
  const ppu=im.pixelsPerUnit||1; const mm=im.motionManager;
  const wrap=document.getElementById('l2wrap'); const r=wrap.getBoundingClientRect();
  const areas=(im.settings.hitAreas||[]).map(a=>{ let i=-1; try{i=core.getDrawableIndex(a.Id);}catch(e){}
    return i<0?null:{Name:a.Name, idx:i}; }).filter(Boolean);
  const centerOf=(a)=>{ const p=core.getDrawableVertexPositions(a.idx); if(!p||!p.length) return null;
    /* 探针取顶点平均：与产品侧「包围盒包含」判定同语义（三角面重心对斜置框会落在盒外，测的是另一种语义）。
       ⚠️ 顶点是 V=Cubism 原生坐标（中心原点/y向上），须先 V2P（Px=Vx+cux/2，Py=cuy/2-Vy）再 toGlobal，
       与产品侧 hitAt 的 P2V 互逆（2026-09-23 坐标系修正，证据 .diag/_probe_affine.json） */
    let sx=0,sy=0,n=0; for(let k=0;k+1<p.length;k+=2){sx+=p[k];sy+=p[k+1];n++;}
    const cux=im.width/ppu, cuy=im.height/ppu;
    const g=m.toGlobal(new PIXI.Point((sx/n+cux/2)*ppu, (cuy/2-sy/n)*ppu));   // 点击瞬间重算：框会随呼吸/物理位移
    return [r.left+g.x, r.top+g.y]; };
  const res=[];
  for(const a of areas){
    mm.startMotion('idle',0,3); await t(300);           // 先归位，避免上一次残留
    const c=centerOf(a); if(!c){ res.push({area:a.Name, played:null, ok:false, note:'no geom'}); continue; }
    const opt={bubbles:true,cancelable:true,pointerId:1,clientX:c[0],clientY:c[1],button:0};
    wrap.dispatchEvent(new PointerEvent('pointerdown',opt));
    window.dispatchEvent(new PointerEvent('pointerup',opt));
    await t(700);
    const cur=mm.state.currentGroup;
    res.push({area:a.Name, played:cur, ok:cur===a.Name});
  }
  return JSON.stringify({key, nAreas:areas.length, hitOK:res.filter(x=>x.ok).length, res});
}catch(e){ return JSON.stringify({key, err:''+(e.message||e)}); }})
"""
ok_models = 0; rows = []
for k in cands:
    out = ev(f"({JS})({json.dumps(k)})")
    try: d = json.loads(out)
    except Exception: d = {'key': k, 'raw': str(out)[:200]}
    rows.append(d)
    if d.get('hitOK') and d.get('hitOK') == d.get('nAreas'): ok_models += 1
    print(json.dumps(d, ensure_ascii=False), flush=True)
print(f"\n模型 {len(cands)} 个 | 全部部位都命中的模型 {ok_models}")
tot = sum(r.get('nAreas', 0) for r in rows); good = sum(r.get('hitOK', 0) for r in rows)
print(f"部位点击总计 {good}/{tot} 命中")
ws.close(); proc.terminate()
