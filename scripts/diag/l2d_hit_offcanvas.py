# -*- coding: utf-8 -*-
"""l2d_hit_offcanvas.py —— 只读取证两件事：
① 已登记的 HitArea 有多少个框压根不在画面内；「判定区可视化」的标签实际落在哪儿
   （用户看到的"角落里有判定区却点不到"= 标签被 clamp 拽到屏幕边缘，框本身在几千像素外）。
② moc3 里**全部** `Touch*` 标记的几何与可见性，与 model3.json 的登记情况对账：
   有多少「在画面内、可点、却没被登记」的标记（换装开关类功能缺失），
   有多少「登记了却在画布外」（编辑器停放标记）。

判据落在真实可观测量上：打开判定区开关后直接从 PIXI 场景图读标签的
.text / .visible / .position，再与同一框的真实 stage 矩形比对。

用法: py -3 scripts/diag/l2d_hit_offcanvas.py qiershazhi_2 [yuanchou_3 ...]
前置: 8777 画廊服务器在跑（否则 Chrome 换成自己的导航失败页，见 WORKFLOWS WF-16 踩坑段）
"""
import sys, os, json, time, subprocess, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import websocket
import chrome_tree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = int(os.environ.get("L2D_OFFC_PORT", "9383"))
PROFILE = os.path.join(ROOT, ".diag", "chrome_offcanvas")
SRV = os.environ.get("L2D_HITGEOM_SRV", "8777")

JS = r"""(async key => {
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<120 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key);
    if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  /* 走真实 UI 路径（openShip → 选皮肤 → 点 Live2D 页签），否则 #l2wrap 尺寸为 0，
     stage 坐标与视口比对全都没有意义。 */
  openShip(ship); setSkin(sk); buildSkinList(ship);
  const tab=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d');
  if(!tab) return JSON.stringify({key, skip:'no live2d tab'});
  tab.click();
  const t0=performance.now();
  while(!l2State || !l2State.app || !l2State.app.stage.children.length){
    if(performance.now()-t0>40000) break; await t(200); }
  if(!l2State || !l2State.app || !l2State.app.stage.children.length)
    return JSON.stringify({key, skip:'model not loaded'});
  const mdl=l2State.app.stage.children[0], im=mdl.internalModel, core=im.coreModel;
  const ppu=im.pixelsPerUnit||1, cux=im.width/ppu, cuy=im.height/ppu, s=mdl.scale.x;
  const wrap=document.getElementById('l2wrap');
  const VW=wrap.clientWidth, VH=wrap.clientHeight;
  const triArea=(a,b,c)=>Math.abs((b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1]))/2;
  const toStage=(vx,vy)=>[mdl.x+(vx+cux/2)*ppu*s, mdl.y+(cuy/2-vy)*ppu*s];
  /* 一个 drawable 的几何档案：V 包围盒 + stage 像素矩形 + 是否落在画布/视口内 + 可见性 */
  const probe=(idx)=>{
    const p=core.getDrawableVertexPositions(idx);
    if(!p||!p.length) return {cls:'NOGEOM'};
    let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
    for(let k=0;k+1<p.length;k+=2){ if(p[k]<x0)x0=p[k]; if(p[k]>x1)x1=p[k];
      if(p[k+1]<y0)y0=p[k+1]; if(p[k+1]>y1)y1=p[k+1]; }
    const A=toStage(x1,y1), B=toStage(x0,y0);
    const gx0=Math.min(A[0],B[0]), gx1=Math.max(A[0],B[0]);
    const gy0=Math.min(A[1],B[1]), gy1=Math.max(A[1],B[1]);
    let area=(x1-x0)*(y1-y0);
    if(p.length===8){ const v=[[p[0],p[1]],[p[2],p[3]],[p[4],p[5]],[p[6],p[7]]];
      area=triArea(v[0],v[1],v[2])+triArea(v[1],v[3],v[2]); }
    const inCanvas=Math.abs((x0+x1)/2)<=cux/2 && Math.abs((y0+y1)/2)<=cuy/2;
    const onVp = gx1>0 && gx0<VW && gy1>0 && gy0<VH;
    const deg = area<1e-6 || Math.min(x1-x0,y1-y0)<1e-4;
    let op=null; try{ op=core.getDrawableOpacity(idx); }catch(e){}
    return {vc:[+((x0+x1)/2).toFixed(1), +((y0+y1)/2).toFixed(1)],
      wh:[+(x1-x0).toFixed(2), +(y1-y0).toFixed(2)], area:+area.toFixed(3),
      stage:[+gx0.toFixed(0),+gy0.toFixed(0),+gx1.toFixed(0),+gy1.toFixed(0)],
      op:op==null?null:+op.toFixed(2),
      cls: deg?'DEGENERATE' : (inCanvas? (onVp?'VISIBLE':'OFFVIEW') : 'OFFCANVAS')};
  };
  const areas=(im.settings.hitAreas||[]).map(a=>{ let i=-1; try{i=core.getDrawableIndex(a.Id);}catch(e){}
    return i<0?null:{id:a.Id, name:a.Name, idx:i}; }).filter(Boolean);
  /* 打开判定区开关（点按钮，不直接调内部函数），让 ticker 真的画一帧 */
  const btn=document.getElementById('l2AreasBtn');
  if(btn && !btn.classList.contains('on')) btn.click();
  await t(600);
  /* 真实场景图里的标签 */
  const labels=[];
  for(const ch of l2State.app.stage.children){
    if(ch instanceof PIXI.Text && ch.visible) labels.push({text:ch.text,
      x:+ch.position.x.toFixed(0), y:+ch.position.y.toFixed(0)}); }
  const rows=areas.map(a=>Object.assign({name:a.name}, probe(a.idx)));
  const byName={}; rows.forEach(r=>byName[r.name]=r);
  const ghost=labels.filter(L=>{ const r=byName[L.text];
    return r && (r.cls==='OFFCANVAS'||r.cls==='OFFVIEW'); });
  /* ② 全量对账：moc3 里所有 Touch* drawable，不管有没有登记 */
  const regIds=new Set((im.settings.hitAreas||[]).map(a=>a.Id));
  const all=[];
  for(const id of core.getDrawableIds()){
    if(!/^Touch/i.test(id)) continue;
    let i=-1; try{ i=core.getDrawableIndex(id); }catch(e){}
    if(i<0) continue;
    all.push(Object.assign({id, reg:regIds.has(id)}, probe(i))); }
  return JSON.stringify({key, canvas:[+cux.toFixed(2),+cuy.toFixed(2)], vp:[VW,VH],
    n:areas.length, nTouch:all.length, nLabels:labels.length, rows,
    ghostLabels:ghost.map(L=>L.text+'@'+L.x+','+L.y),
    offReg:all.filter(r=> r.reg && (r.cls==='OFFCANVAS'||r.cls==='OFFVIEW')).map(r=>r.id),
    onNotReg:all.filter(r=>!r.reg && r.cls==='VISIBLE').map(r=>({id:r.id,vc:r.vc,wh:r.wh,op:r.op})),
    touchAll:all});
})
"""


# --sweep：逐个播放**所有**动作组（走页面自己的下拉框 onchange，不绕过 play()），
# 每组播放中重新量一遍 Touch* 标记的在画布数 —— 用来判定「出画」到底是
# 编辑器遗留的死停放位，还是被动画拉进画面的换装开关（如"垂电线"菜单）。
SWEEP_JS = r"""(async key => {
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<120 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key);
    if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  const tab=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d');
  if(!tab) return JSON.stringify({key, skip:'no live2d tab'});
  tab.click();
  const t0=performance.now();
  while(!l2State || !l2State.app || !l2State.app.stage.children.length){
    if(performance.now()-t0>40000) break; await t(200); }
  if(!l2State || !l2State.app || !l2State.app.stage.children.length)
    return JSON.stringify({key, skip:'model not loaded'});
  const mdl=l2State.app.stage.children[0], im=mdl.internalModel, core=im.coreModel;
  const mm=im.motionManager, ppu=im.pixelsPerUnit||1;
  const cux=im.width/ppu, cuy=im.height/ppu;
  const ids=core.getDrawableIds().filter(x=>/^Touch/i.test(x));
  const idxOf={}; for(const id of ids){ try{ idxOf[id]=core.getDrawableIndex(id); }catch(e){} }
  /* 只看「中心是否落进画布矩形」——与缩放/平移无关，是数据本身的属性 */
  const onCanvas=()=>{ const s=new Set();
    for(const id of ids){ const i=idxOf[id]; if(i==null) continue;
      const p=core.getDrawableVertexPositions(i); if(!p||!p.length) continue;
      let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
      for(let k=0;k+1<p.length;k+=2){ if(p[k]<x0)x0=p[k]; if(p[k]>x1)x1=p[k];
        if(p[k+1]<y0)y0=p[k+1]; if(p[k+1]>y1)y1=p[k+1]; }
      if(Math.abs((x0+x1)/2)<=cux/2 && Math.abs((y0+y1)/2)<=cuy/2) s.add(id); }
    return s; };
  const rest=onCanvas();
  const sel=document.getElementById('l2Motion');
  if(!sel) return JSON.stringify({key, skip:'no motion select'});
  const groups=[...sel.options].map(o=>o.value);
  const rows=[];
  for(const g of groups){
    sel.value=g; sel.onchange();
    await t(1200);
    const now=onCanvas();
    const appeared=[...now].filter(x=>!rest.has(x));
    const gone=[...rest].filter(x=>!now.has(x));
    if(appeared.length||gone.length)
      rows.push({grp:g, played:mm.state.currentGroup, on:now.size, appeared, gone});
    await t(300); }
  sel.value='idle'; sel.onchange(); await t(1500);
  return JSON.stringify({key, nTouch:ids.length, restOn:[...rest], restCount:rest.size,
    groups:groups.length, rows});
})
"""


def kill_tree(proc):
    """统一走 chrome_tree（taskkill /T /F 整棵树）——§50 记过 proc.terminate() 只杀启动器。"""
    chrome_tree.kill_tree(proc.pid)


def main():
    keys = [a for a in sys.argv[1:] if not a.startswith("--")] or ["qiershazhi_2"]
    sweep = "--sweep" in sys.argv
    os.makedirs(PROFILE, exist_ok=True)
    proc = chrome_tree.install(subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
      '--remote-allow-origins=*', f'--user-data-dir={PROFILE}', '--no-first-run',
      '--no-default-browser-check', '--disable-background-timer-throttling',
      '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--window-size=1600,1000',
      f'http://127.0.0.1:{SRV}/gallery_v2/index.html'],
      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    ws = None
    for _ in range(90):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
            tt = [x['webSocketDebuggerUrl'] for x in tabs
                  if 'gallery_v2' in x.get('url', '') and x.get('webSocketDebuggerUrl')]
            if tt:
                ws = websocket.create_connection(tt[0], timeout=180, max_size=None)
                break
        except Exception:
            pass
        time.sleep(0.5)
    if ws is None:
        print('[ERROR] 连不上 Chrome 或页面未开——先确认 8777 服务器在跑')
        kill_tree(proc)
        return 2
    _id = 0

    def ev(expr, t=180):
        nonlocal _id
        _id += 1
        ws.send(json.dumps({'id': _id, 'method': 'Runtime.evaluate',
                            'params': {'expression': expr, 'returnByValue': True, 'awaitPromise': True}}))
        ws.settimeout(t)
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == _id:
                res = r.get('result', {})
                if res.get('exceptionDetails'):
                    return json.dumps({'err': str(res['exceptionDetails'].get('text'))[:200]})
                return res.get('result', {}).get('value')

    result = {}
    if sweep:
        for k in keys:
            try:
                d = json.loads(ev(f"({SWEEP_JS})({json.dumps(k)})", t=900))
            except Exception as e:
                print(f"  {k}: 解析失败 {e}")
                continue
            result[k] = d
            if d.get('err') or d.get('skip'):
                print(f"  {k}: {d.get('err') or d.get('skip')}")
                continue
            print(f"\n== {k}  Touch* 标记 {d['nTouch']} 个，静止态在画布内 {d['restCount']} 个 "
                  f"{d['restOn']}   动作组 {d['groups']} 个")
            if not d['rows']:
                print("   播完全部动作组后**没有任何标记移进/移出画布** → 出画的那些是死停放位")
            for r in d['rows']:
                print(f"   [{r['grp']:<16}] 实播{r['played']:<16} 在画布 {r['on']:<3} "
                      f"移入={r['appeared']} 移出={r['gone']}")
        out = os.path.join(ROOT, ".diag", "l2d_hit_sweep.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f"\n明细已写出 {out}")
        try:
            ws.close()
        except Exception:
            pass
        kill_tree(proc)
        return 0
    for k in keys:
        try:
            d = json.loads(ev(f"({JS})({json.dumps(k)})"))
        except Exception as e:
            print(f"  {k}: 解析失败 {e}")
            continue
        result[k] = d
        if d.get('err') or d.get('skip'):
            print(f"  {k}: {d.get('err') or d.get('skip')}")
            continue
        cnt = {}
        for r in d['rows']:
            cnt[r['cls']] = cnt.get(r['cls'], 0) + 1
        tcnt = {}
        for r in d['touchAll']:
            tcnt[r['cls']] = tcnt.get(r['cls'], 0) + 1
        print(f"\n== {k}  画布 {d['canvas']} 单位  视口 {d['vp']}")
        print(f"   ① 已登记 {d['n']} 个 → " + "  ".join(f"{a}={b}" for a, b in sorted(cnt.items())) +
              f"   |  幽灵标签 {len(d['ghostLabels'])} 个 {d['ghostLabels'][:6]}")
        print(f"   ② moc3 共 {d['nTouch']} 个 Touch* 标记 → " + "  ".join(f"{a}={b}" for a, b in sorted(tcnt.items())))
        print(f"      登记了却在画布外 {len(d['offReg'])} 个: {d['offReg'][:14]}")
        print(f"      ⚠️ 在画面内、可点、却没登记 {len(d['onNotReg'])} 个:")
        for r in d['onNotReg'][:16]:
            print(f"         {r['id']:<20} V中心{r['vc']} 宽高{r['wh']} 不透明度{r['op']}")
    out = os.path.join(ROOT, ".diag", "l2d_hit_offcanvas.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"\n明细已写出 {out}")
    try:
        ws.close()
    except Exception:
        pass
    kill_tree(proc)
    return 0


if __name__ == '__main__':
    sys.exit(main())
