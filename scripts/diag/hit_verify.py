# -*- coding: utf-8 -*-
"""验证「按部位点击触发对应动作」：对若干模型，把每个 HitArea 的几何中心换算成屏幕坐标，
   派发 pointerdown/pointerup，读 motionManager.state.currentGroup。

   2026-09-24 起每个部位给**四类**结论（旧版只有 ok/not-ok，把工具假设当成了产品缺陷）：
     HIT       播出的组 = 该部位
     SHADOWED  播出的是**产品自己的 hitAt** 判出的另一个更小框 → 多个 Touch* 标记几何重叠，
               按「重叠取面积最小者」是设计，不算失败
     WIRING    真实派发结果与产品几何判定不一致 → 事件链路真断，**只有这类才算 bug**（退出码 1）
     OUTSIDE   中心点不在任何可用框内（含退化框被产品侧过滤的情形，见 index.html geomOf）
   几何判定走 window.__L2_HIT（产品页暴露的同一个 hitAt），探针不复算几何——复算版实测与真实
   派发有 4/38 条不一致，复算不可信就不许拿它下结论。
用法: py -3 scripts/diag/hit_verify.py [--limit N] [--only k1,k2]   # 都不给即全量
前置: 8777 画廊服务器在跑（否则 Chrome 换成导航失败页，会假报 nAreas=0，见 WF-16 踩坑段）
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

# 就绪等待必须真的等：旧写法 `for(let i=0;i<80 && !window.GALLERY;i++){}` 是同步空转，
# 微秒级就跑完等于没等，且只查 GALLERY 不查 stopLive2D -> 前若干模型必报
# "GALLERY is not defined" / "stopLive2D is not defined"（2026-09-23 实测冷启动必现）。
ev("(async()=>{ for(let i=0;i<200 && !(window.GALLERY && typeof openShip==='function'"
   " && typeof stopLive2D==='function' && typeof renderLive2D==='function');i++)"
   " await new Promise(r=>setTimeout(r,300));"
   " return (typeof GALLERY!=='undefined' && typeof stopLive2D==='function')?'ready':'NOT READY'; })()")
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
    return {scr:[r.left+g.x, r.top+g.y], v:[sx/n, sy/n]}; };
  const res=[];
  for(const a of areas){
    mm.startMotion('idle',0,3); await t(300);           // 先归位，避免上一次残留
    const c=centerOf(a); if(!c){ res.push({area:a.Name, played:null, cls:'NOGEOM'}); continue; }
    /* 几何判定用**产品自己的** hitAt（window.__L2_HIT），探针不再复算一份——
       2026-09-24 复算版与真实派发有 4/38 条不一致，复算不可信就不许拿它下结论 */
    const expected=(window.__L2_HIT? window.__L2_HIT(c.v[0], c.v[1]) : null);
    const opt={bubbles:true,cancelable:true,pointerId:1,clientX:c.scr[0],clientY:c.scr[1],button:0};
    wrap.dispatchEvent(new PointerEvent('pointerdown',opt));
    window.dispatchEvent(new PointerEvent('pointerup',opt));
    await t(700);
    const cur=mm.state.currentGroup;
    /* 四类：HIT 命中自己 / SHADOWED 几何上本就该更小的框赢（重叠标记，非缺陷）
       / WIRING 真实派发结果与产品几何判定不一致（事件链路真断，这才算 bug）
       / OUTSIDE 中心点不在任何可用框内（含退化框被产品侧过滤掉的情形） */
    let cls;
    if(cur===a.Name) cls='HIT';
    else if(expected===null||expected===undefined) cls='OUTSIDE';
    else if(cur===expected) cls='SHADOWED';
    else cls='WIRING';
    res.push({area:a.Name, played:cur, geom:expected, cls});
  }
  return JSON.stringify({key, nAreas:areas.length, hitOK:res.filter(x=>x.cls==='HIT').length, res});
}catch(e){ return JSON.stringify({key, err:''+(e.message||e)}); }})
"""
ok_models = 0; rows = []
for k in cands:
    for _attempt in range(3):   # 冷启动 / 偶发 WebGL 断连会返回 err，重试而不是记成失败
        out = ev(f"({JS})({json.dumps(k)})")
        try: d = json.loads(out)
        except Exception: d = {'key': k, 'raw': str(out)[:200]}
        if not d.get('err'):
            break
        print(f'  ↻ {k} 第{_attempt+1}次 err={str(d.get("err"))[:60]}，2s 后重试', flush=True)
        time.sleep(2)
    rows.append(d)
    if d.get('hitOK') and d.get('hitOK') == d.get('nAreas'): ok_models += 1
    cnt = {}
    for r in d.get('res') or []:
        cnt[r.get('cls')] = cnt.get(r.get('cls'), 0) + 1
    d['cls_counts'] = cnt
    bad = cnt.get('WIRING', 0) + cnt.get('OUTSIDE', 0) + cnt.get('NOGEOM', 0)
    if bad:
        print(json.dumps(d, ensure_ascii=False), flush=True)
    else:
        print(f"  {k:<22} {cnt.get('HIT', 0)}/{d.get('nAreas')} 命中"
              + (f"  （另有 {cnt['SHADOWED']} 个部位被更小的框合法遮住）" if cnt.get('SHADOWED') else ''),
              flush=True)
tot = sum(r.get('nAreas', 0) for r in rows)
allres = [x for r in rows for x in (r.get('res') or [])]
c = {}
for x in allres:
    c[x.get('cls')] = c.get(x.get('cls'), 0) + 1
wiring = c.get('WIRING', 0)
outside = c.get('OUTSIDE', 0) + c.get('NOGEOM', 0)
print(f"\n模型 {len(cands)} 个 | 全部部位都命中的模型 {ok_models}")
print(f"部位总计 {tot}：HIT {c.get('HIT', 0)} | SHADOWED(遮住，非缺陷) {c.get('SHADOWED', 0)}"
      f" | WIRING(事件链路断) {wiring} | OUTSIDE/NOGEOM(点不在任何可用框) {outside}")
print("判据：WIRING 必须为 0 才算过。SHADOWED 只说明多个 Touch* 标记几何互相重叠"
      "（产品按「重叠取面积最小者」是设计），2026-09-24 起不再当失败 —— 见 TROUBLESHOOTING §27")
if wiring or outside:
    print("需看的明细：")
    for x in allres:
        if x.get('cls') in ('WIRING', 'OUTSIDE', 'NOGEOM'):
            print(f"   [{x['cls']}] {x.get('area')} 实播={x.get('played')} 几何判定={x.get('geom')}")
ws.close(); proc.terminate()
sys.exit(1 if wiring else 0)
