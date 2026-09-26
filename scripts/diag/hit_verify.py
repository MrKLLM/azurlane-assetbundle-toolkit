# -*- coding: utf-8 -*-
"""验证「按部位点击触发对应动作」：对若干模型，把每个 HitArea 的几何中心换算成屏幕坐标，
   派发 pointerdown/pointerup，读 motionManager.state.currentGroup。

   2026-09-24 A3 裁定后每个部位给**四类**结论（旧版只有 ok/not-ok，把工具假设当成了产品缺陷）：
     HIT      播出的组 = 该部位
     INGROUP  播出的是候选集合里的**另一条** → 同一位置挂了多个 Touch 标记，A3 就是随机挑一条（设计，非缺陷）
     WIRING   真实派发结果**不在**产品自己的候选集合内 → 事件链路真断，**这类才算 bug**（退出码 1）
     OUTSIDE  中心点不在任何可用框内（退化框已被产品侧 geomOf 挡掉，见 index.html）
   另给两个总指标：**可点中率**（该部位自己的中心是否落在自己的可用框内）与**随机性抽查**
   （多候选处连点 6 次：既数出了几条不同动作，也数有几次落在候选外——"点了没反应"必须被量化，不许只报 distinct）。
   候选集合取自产品暴露的 window.__L2_HITALL，探针不复算几何（复算版实测与真实派发 4/38 条不一致）。
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
    /* 候选集合取自**产品自己的** hitAll（window.__L2_HITALL），探针不复算几何：
       复算版实测与真实派发有 4/38 条不一致，复算不可信就不许拿它下结论 */
    const cand=(window.__L2_HITALL? __L2_HITALL(c.v[0], c.v[1]) : [window.__L2_HIT?__L2_HIT(c.v[0],c.v[1]):null]).filter(Boolean);
    /* 每次点击都重算坐标：模型在呼吸/物理位移，真人点的永远是「它此刻在的位置」。
       沿用固定坐标连点会漂出框外，测出来的"点了没反应"是探针伪影（实测 offCand 一度 3/6→1/6）。 */
    const clickAt=async(pt)=>{ const opt={bubbles:true,cancelable:true,pointerId:1,
                                 clientX:pt[0],clientY:pt[1],button:0};
                               wrap.dispatchEvent(new PointerEvent('pointerdown',opt));
                               window.dispatchEvent(new PointerEvent('pointerup',opt));
                               await t(700); return mm.state.currentGroup; };
    /* 读结果不能用「点完等 700ms 再看一次 currentGroup」——短的 touch_idle 与 drag 类动作
       不到 700ms 就播完回落 idle，会被读成「没响应」（同 §6.10 那类假阴性，只是换了地方）。
       改成两路取：① 点完立刻读状态栏 pill（play() 成功时才写，同步且精确）；
       ② 之后每 120ms 轮询 currentGroup 共 14 次，任一次等于候选即算播出。 */
    const pillNow=()=>{ const el=document.getElementById('l2Hit'); return el?el.textContent||'':''; };
    const before=pillNow();
    const t0=performance.now();
    const opt0={bubbles:true,cancelable:true,pointerId:1,clientX:c.scr[0],clientY:c.scr[1],button:0};
    wrap.dispatchEvent(new PointerEvent('pointerdown',opt0));
    window.dispatchEvent(new PointerEvent('pointerup',opt0));
    let cur=null, fromPill=null;
    const pill=await (async()=>{ await t(30); return pillNow(); })();
    if(pill && pill!==before){ const m=/→\s*(.+)$/.exec(pill); if(m) fromPill=m[1].trim(); }
    for(let i=0;i<14 && !cur;i++){ await t(120);
      const g=mm.state.currentGroup; if(g && g!=='idle') cur=g; }
    const played=cur||fromPill||mm.state.currentGroup;
    cur=played;
    if(!cur && fromPill) cur=fromPill;
    /* A3（2026-09-24 用户裁定）：同一位置挂多个 Touch 标记时随机挑一条 →
       断言从「必须等于自己」改成「必须落在候选集合里」，否则把设计行为当失败 */
    const usable=window.__L2_HITUSE? window.__L2_HITUSE() : null;
    let cls;
    if(!cand.length) cls=(usable && !usable.includes(a.Name)) ? 'NOTCLICKABLE' : 'OUTSIDE';
    else if(cur===a.Name) cls='HIT';
    else if(cand.includes(cur)) cls='INGROUP';
    else cls='WIRING';
    res.push({area:a.Name, played:cur, cand, reachable:cand.includes(a.Name), cls});
  }
  /* ── 阶段 2：随机性抽查（与点击测试互斥，必须分开）──
     pixi 的动作用户可见推进依赖 ticker，冻结后 currentGroup 不再前进 → 点击测试要求它在跑；
     而"同一个点连调 8 次看是否换条目"要求几何不动（模型在放 idle，框一直在飘，
     实测同一位置瞬时候选数在 1~2 之间跳，边跑边测根本测不出随机性）。
     所以这一阶段**冻结 ticker**，且只调 __L2_HIT、不派发事件。 */
  /* 阶段 2（冻结）：用网格点统计"真有多少位置是重叠的"，并在一个多候选点上测随机是否生效。
     只看各部位自己的中心点是不够的——实测 lafeiii_3 静止态下 25 个中心点全都只落在 1 个框里
     （它当初的错响应源自退化框，已被 geomOf 挡掉），所以必须换一种取点方式才能覆盖重叠区。 */
  const tk=l2State.app.ticker; tk && tk.stop(); await t(80);
  let overlap=null, randChk=null;
  if(window.__L2_HITALL){
    let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
    for(const a of areas){ const p=core.getDrawableVertexPositions(a.idx); if(!p||!p.length) continue;
      for(let k=0;k+1<p.length;k+=2){ if(p[k]<x0)x0=p[k]; if(p[k]>x1)x1=p[k]; if(p[k+1]<y0)y0=p[k+1]; if(p[k+1]>y1)y1=p[k+1]; } }
    const N=24, seenMulti=[]; let multi=0, single=0, empty=0, best=null;
    for(let ix=0; ix<N; ix++) for(let iy=0; iy<N; iy++){
      const mx=x0+(x1-x0)*(ix+0.5)/N, my=y0+(y1-y0)*(iy+0.5)/N;
      const cf=window.__L2_HITALL(mx,my)||[];
      if(!cf.length) empty++; else if(cf.length===1) single++; else { multi++;
        if(!best || cf.length>best.cf.length) best={mx,my,cf}; } }
    const totPts=multi+single+empty;
    overlap={pts:totPts, multi, single, empty,
             multiPct: totPts? Math.round(1000*multi/totPts)/10 : 0};
    if(best){ const seq=[]; for(let i=0;i<8;i++) seq.push(window.__L2_HIT(best.mx,best.my));
      randChk={at:[+best.mx.toFixed(3),+best.my.toFixed(3)], candN:best.cf.length, cand:best.cf,
               seq, distinct:new Set(seq).size,
               noRepeatOK:seq.every((v,i)=>i===0||v!==seq[i-1])}; }
  }
  tk && tk.start();
  return JSON.stringify({key, nAreas:areas.length,
    hitOK:res.filter(x=>x.cls==='HIT').length, overlap, randChk, res});
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
    if 'nAreas' not in d:
        # skip / JS 异常都会缺 nAreas；旧写法把 bad=0 归进"全绿"分支，
        # 于是打印成 `命中自己 0 / 共 None` 看着像通过 —— 静默失败，必须显式报出来。
        print(json.dumps({'FAIL': k, 'reason': '没有 nAreas（skip 或 JS 异常）',
                          'raw': d}, ensure_ascii=False), flush=True)
        continue
    if bad or (d.get('randChk') and d['randChk']['distinct'] < 2):
        print(json.dumps(d, ensure_ascii=False), flush=True)
    else:
        rc = d.get('randChk')
        line = (f"  {k:<22} 命中自己 {cnt.get('HIT', 0)} / 共 {d.get('nAreas')}"
                f"  随机出同组另一条 {cnt.get('INGROUP', 0)}"
                f"  点不到自己 {cnt.get('OUTSIDE', 0) + cnt.get('NOGEOM', 0)}"
                f"  不可达自己中心 {sum(1 for x in d.get('res') or [] if not x.get('reachable'))}")
        ov = d.get('overlap')
        if ov:
            line += f"  | 静止态网格 {ov['pts']} 点: 多候选 {ov['multi']} 单候选 {ov['single']} 无框 {ov['empty']}"
        if rc:
            line += f"  | 随机抽查 候选{rc['candN']}→8 次出 {rc['distinct']} 条 不重复={rc.get('noRepeatOK')}"
        print(line, flush=True)
tot = sum(r.get('nAreas', 0) for r in rows)
allres = [x for r in rows for x in (r.get('res') or [])]
c = {}
for x in allres:
    c[x.get('cls')] = c.get(x.get('cls'), 0) + 1
wiring = c.get('WIRING', 0)
nclick = c.get('NOTCLICKABLE', 0)
outside = c.get('OUTSIDE', 0) + c.get('NOGEOM', 0)
reach = sum(1 for x in allres if x.get('reachable'))
rand = [r.get('randChk') for r in rows if r.get('randChk')]
rand_fail = [r for r in rand if r['distinct'] < 2 or not r.get('noRepeatOK')]
print(f"\n模型 {len(cands)} 个 | 全部部位都命中自己的模型 {ok_models}")
print(f"部位总计 {tot}：HIT(命中自己) {c.get('HIT', 0)} | INGROUP(随机出同组另一条) {c.get('INGROUP', 0)}"
      f" | WIRING(点了没播出/播了候选外的) {wiring} | OUTSIDE/NOGEOM {outside}"
      f" | NOTCLICKABLE(退化框，设计上不可点，不算异常) {nclick}")
print(f"可点中率（该部位自己的中心落在自己的可用框内）: {reach}/{tot} = "
      f"{round(100.0 * reach / tot, 1) if tot else 0}%")
if rand:
    print(f"随机性抽查（多候选点连调 __L2_HIT 8 次）{len(rand)} 个模型；不合格 {len(rand_fail)} 个: "
          + (str([(r['candN'], r['distinct']) for r in rand_fail]) if rand_fail
             else '无 —— 8 次里换了条目且相邻两次不重复'))
    for r in rand[:3]:
        print(f"   例 候选{r['candN']} {r['cand']} → 序列 {r['seq']}")
print("判据：WIRING 必须为 0（A3 下实播必须落在候选集合内）；多候选处连点必须换条目；"
      "HIT 不再是硬指标——同一位置挂多个标记时随机出别条是设计（2026-09-24 用户裁定 A3，见 §27）")
ws.close(); proc.terminate()
sys.exit(1 if (wiring or rand_fail) else 0)
