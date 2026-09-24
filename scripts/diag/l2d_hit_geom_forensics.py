#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""l2d_hit_geom_forensics.py —— 只读取证：按部位点击漏命中，到底是「自己的框拒绝自己的中心点」
还是「中心点真的被更小的邻框盖住」。两者修法完全不同，不能一起当"产品 bug"改。

背景（2026-09-24）：全量重导后 `fix_model3.py` 把判定区从 3 个补登到几十个（mean 12.3 / max 78），
`hit_verify.py` 抽样 8 模型 40/54。产品侧 `hitAt` 已经是「包含点的框里取面积最小者」，
所以"改成面积最小"这条路是空的——必须先看几何。

分类（对每个 HitArea，点 = 顶点均值，与 hit_verify 同语义）：
  WIN          预测赢家 = 自己，且真实派发也 = 自己
  SELF_REJECT  中心点被**自己**的四边形 triIn 判在框外  → 顶点序/三角划分假定错（产品侧要修 geomOf）
  NESTED       中心点在自己框内，但另有**更小**的框也含它并赢了 → 几何真重叠，产品行为符合设计，
               该修的是断言（"点大框中心必须触发大框"对嵌套框不成立）
  NOGEOM       取不到顶点
用法: py -3 scripts/diag/l2d_hit_geom_forensics.py jianwu_2 lafeiii_3 antu_2
前置: 8777 画廊服务器在跑（否则 Chrome 会换成自己的导航失败页，见 WORKFLOWS WF-16 踩坑段）
"""
import sys, os, json, time, subprocess, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9381
PROFILE = os.path.join(ROOT, ".diag", "chrome_hitgeom")
SRV = os.environ.get("L2D_HITGEOM_SRV", "8777")
_id = 0          # CDP 请求序号（模块级，供 ev() 里的 global 用）

JS = r"""(async key => {
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  stopLive2D(); await renderLive2D(ship, sk); await t(2500);
  const m=l2State.app.stage.children[0], im=m.internalModel, core=im.coreModel, ppu=im.pixelsPerUnit||1;
  const mm=im.motionManager, wrap=document.getElementById('l2wrap'), r=wrap.getBoundingClientRect();
  const areas=(im.settings.hitAreas||[]).map(a=>{ let i=-1; try{i=core.getDrawableIndex(a.Id);}catch(e){}
    return i<0?null:{name:a.Name, idx:i}; }).filter(Boolean);
  /* 与产品侧 index.html 的 triIn/triArea/geomOf/hitAt 同一套算式（逐字搬过来） */
  const triIn=(x,y,a,b,c)=>{ const d=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);
    if(Math.abs(d)<1e-12) return false;
    const l=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/d, m=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/d;
    return l>=-0.02&&m>=-0.02&&(l+m)<=1.04; };
  const triArea=(a,b,c)=>Math.abs((b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1]))/2;
  const geomOf=(idx)=>{ const p=core.getDrawableVertexPositions(idx); if(!p||!p.length) return null;
    let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9,sx=0,sy=0,n=0;
    for(let k=0;k+1<p.length;k+=2){ if(p[k]<x0)x0=p[k]; if(p[k]>x1)x1=p[k];
      if(p[k+1]<y0)y0=p[k+1]; if(p[k+1]>y1)y1=p[k+1]; sx+=p[k]; sy+=p[k+1]; n++; }
    const g={x0,y0,x1,y1,cx:sx/n,cy:sy/n,quad:null,nv:p.length/2};
    if(p.length===8){ const v=[[p[0],p[1]],[p[2],p[3]],[p[4],p[5]],[p[6],p[7]]];
      g.quad={v, area:triArea(v[0],v[1],v[2])+triArea(v[1],v[3],v[2])}; }
    return g; };
  const inOwn=(g)=>{ if(!g.quad) { const a=(g.x1-g.x0)*(g.y1-g.y0); return {inside:true, area:a}; }
    const v=g.quad.v;
    return {inside: triIn(g.cx,g.cy,v[0],v[1],v[2])||triIn(g.cx,g.cy,v[1],v[3],v[2]), area:g.quad.area}; };
  const out=[];
  for(const a of areas){
    const g=geomOf(a.idx);
    if(!g){ out.push({area:a.name, cls:'NOGEOM'}); continue; }
    /* 候选 = 通过「包围盒 2% 容差 + 自身几何含点」的框；赢家 = 其中面积最小者（产品侧同规则） */
    const cand=[];
    for(const b of areas){ const gb=geomOf(b.idx); if(!gb) continue;
      const hw=Math.max(1e-6,(gb.x1-gb.x0)/2), hh=Math.max(1e-6,(gb.y1-gb.y0)/2);
      if(g.cx<gb.x0-hw*0.02||g.cx>gb.x1+hw*0.02||g.cy<gb.y0-hh*0.02||g.cy>gb.y1+hh*0.02) continue;
      const io=inOwn({quad:gb.quad, x0:gb.x0,y0:gb.y0,x1:gb.x1,y1:gb.y1,
                      cx:g.cx, cy:g.cy, nv:gb.nv});   // 用**被测点**而非该框自身中心做含点判定
      if(!io.inside) continue;
      cand.push({name:b.name, area:+io.area.toFixed(4)}); }
    cand.sort((p,q)=>p.area-q.area);
    const win=cand.length?cand[0].name:null;
    const self=inOwn(g);
    let cls;
    if(win===a.name) cls='WIN';
    else if(!self.inside) cls='SELF_REJECT';
    else cls='NESTED';
    /* 真实派发一遍，验证上面这套复算与产品行为一致（不一致=复算不可信） */
    mm.startMotion('idle',0,3); await t(300);
    const P2Vx=g.cx, P2Vy=g.cy, cux=im.width/ppu, cuy=im.height/ppu;
    const gp=m.toGlobal(new PIXI.Point((P2Vx+cux/2)*ppu, (cuy/2-P2Vy)*ppu));
    const opt={bubbles:true,cancelable:true,pointerId:1,clientX:r.left+gp.x,clientY:r.top+gp.y,button:0};
    wrap.dispatchEvent(new PointerEvent('pointerdown',opt));
    window.dispatchEvent(new PointerEvent('pointerup',opt));
    await t(700);
    const played=mm.state.currentGroup;
    out.push({area:a.name, cls, nv:g.nv, predicted:win, played,
              agree:(played===win), selfArea:+self.area.toFixed(4),
              smaller: cand.filter(c=>c.area<self.area && c.name!==a.name).slice(0,3)});
  }
  return JSON.stringify({key, n:areas.length, rows:out});
})
"""


SCAN_JS = r"""(async key => {
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  stopLive2D(); await renderLive2D(ship, sk); await t(2200);
  const im=l2State.app.stage.children[0].internalModel, core=im.coreModel, ppu=im.pixelsPerUnit||1;
  const areas=(im.settings.hitAreas||[]).map(a=>{ let i=-1; try{i=core.getDrawableIndex(a.Id);}catch(e){}
    return i<0?null:{name:a.Name, idx:i}; }).filter(Boolean);
  const triArea=(a,b,c)=>Math.abs((b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1]))/2;
  const rec=[];
  for(const a of areas){ const p=core.getDrawableVertexPositions(a.idx);
    if(!p||!p.length){ rec.push({name:a.name, nv:0, area:-1, w:-1, h:-1}); continue; }
    let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
    for(let k=0;k+1<p.length;k+=2){ if(p[k]<x0)x0=p[k]; if(p[k]>x1)x1=p[k]; if(p[k+1]<y0)y0=p[k+1]; if(p[k+1]>y1)y1=p[k+1]; }
    let area;
    if(p.length===8){ const v=[[p[0],p[1]],[p[2],p[3]],[p[4],p[5]],[p[6],p[7]]];
      area=triArea(v[0],v[1],v[2])+triArea(v[1],v[3],v[2]); }
    else area=(x1-x0)*(y1-y0);
    rec.push({name:a.name, nv:p.length/2, area:+area.toFixed(6), w:+(x1-x0).toFixed(4), h:+(y1-y0).toFixed(4)}); }
  return JSON.stringify({key, n:areas.length, rec});
})
"""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    scan = "--scan-all" in sys.argv
    keys = args or (["<all>"] if scan else ["jianwu_2", "lafeiii_3"])
    os.makedirs(PROFILE, exist_ok=True)
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
      '--remote-allow-origins=*', f'--user-data-dir={PROFILE}', '--no-first-run',
      '--no-default-browser-check', '--disable-background-timer-throttling',
      '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--window-size=1280,900',
      f'http://127.0.0.1:{SRV}/gallery_v2/index.html'],
      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    for _ in range(90):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
            t = [x['webSocketDebuggerUrl'] for x in tabs
                 if 'gallery_v2' in x.get('url', '') and x.get('webSocketDebuggerUrl')]
            if t:
                ws = websocket.create_connection(t[0], timeout=120, max_size=None)
                break
        except Exception:
            pass
        time.sleep(0.5)
    if ws is None:
        print('[ERROR] 连不上 Chrome 或页面未开——先确认 8777 服务器在跑（page_sanity_check.py）')
        proc.terminate()
        return 2

    def ev(expr, t=120):
        global _id
        _id += 1
        ws.send(json.dumps({'id': _id, 'method': 'Runtime.evaluate',
                            'params': {'expression': expr, 'returnByValue': True, 'awaitPromise': True}}))
        ws.settimeout(t)
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == _id:
                res = r.get('result', {})
                if res.get('exceptionDetails'):
                    return json.dumps({'err': str(res['exceptionDetails'].get('text'))[:160]})
                return res.get('result', {}).get('value')

    ev("(async()=>{ for(let i=0;i<200 && !(window.GALLERY && typeof openShip==='function'"
       " && typeof stopLive2D==='function' && typeof renderLive2D==='function');i++)"
       " await new Promise(r=>setTimeout(r,300)); return 'ok'; })()")
    tally = {}
    if scan:
        root_live2d = os.path.join(ROOT, "Output", "Live2D")
        keys = sorted(k for k in os.listdir(root_live2d)
                      if os.path.isdir(os.path.join(root_live2d, k)) and not k.startswith("_"))
        deg_models, dup_models, rows_out = [], [], []
        for i, k in enumerate(keys, 1):
            if i > 1 and (i - 1) % 55 == 0:      # 单 Chrome ~110 个模型后 WebGL 断连，主动重载
                ev("location.reload()")
                time.sleep(6)
                ev("(async()=>{ for(let j=0;j<200 && !(window.GALLERY && typeof renderLive2D==='function');j++)"
                   " await new Promise(r=>setTimeout(r,300)); return 'ok'; })()")
            try:
                d = json.loads(ev(f"({SCAN_JS})({json.dumps(k)})"))
            except Exception as e:
                print(f"  [{i}/{len(keys)}] {k} 解析失败 {e}", flush=True)
                continue
            rec = d.get("rec") or []
            if not rec:
                print(f"  [{i}/{len(keys)}] {k} {d.get('skip') or 'no areas'}", flush=True)
                continue
            deg = [r for r in rec if r["area"] < 1e-6 or min(r["w"], r["h"]) < 1e-4]
            sig = {}
            for r in rec:
                sig.setdefault((r["area"], r["w"], r["h"]), []).append(r["name"])
            dupgroups = [v for v in sig.values() if len(v) > 1]
            if deg:
                deg_models.append((k, len(deg), len(rec)))
            if dupgroups:
                dup_models.append((k, [len(g) for g in dupgroups]))
            rows_out.append((k, len(rec), len(deg), len(dupgroups)))
            print(f"  [{i}/{len(keys)}] {k:<22} 框 {len(rec):<3} 退化 {len(deg):<3} 同几何组 {len(dupgroups)}",
                  flush=True)
        n = len(rows_out)
        print(f"\n===== 全库几何体检（{n} 个模型）=====")
        print(f"  有退化框（面积或宽/高≈0，点不到却在「取最小面积」时抢赢）: "
              f"{len(deg_models)}/{n} 个模型，退化框合计 {sum(x[1] for x in deg_models)} 个")
        print(f"  有完全相同几何的框: {len(dup_models)}/{n} 个模型")
        print(f"  框总数 {sum(r[1] for r in rows_out)}，其中退化 {sum(r[2] for r in rows_out)}")
        json.dump({"per_model": rows_out, "degenerate": deg_models,
                   "duplicate_groups": dup_models},
                  open(os.path.join(ROOT, ".diag", "l2d_hit_geom_scan.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"  明细: .diag/l2d_hit_geom_scan.json")
        print("  最严重的 10 个模型（按退化框占比）:",
              sorted(deg_models, key=lambda x: -x[1] / x[2])[:10])
        ws.close(); proc.terminate()
        return 0
    for k in keys:
        out = ev(f"({JS})({json.dumps(k)})")
        try:
            d = json.loads(out)
        except Exception:
            print(f'  {k}: 解析失败 {str(out)[:120]}')
            continue
        if d.get('err') or d.get('skip'):
            print(f"  {k}: {d.get('err') or d.get('skip')}")
            continue
        cnt = {}
        for r in d['rows']:
            cnt[r['cls']] = cnt.get(r['cls'], 0) + 1
            tally[r['cls']] = tally.get(r['cls'], 0) + 1
        disagree = [r for r in d['rows'] if r['cls'] != 'WIN' and r.get('agree') is False]
        print(f"\n== {k}  判定区 {d['n']}  " + "  ".join(f'{a}={b}' for a, b in sorted(cnt.items())))
        for r in d['rows']:
            if r['cls'] == 'WIN':
                continue
            print(f"   [{r['cls']:<11}] {r['area']:<16} 顶点{r.get('nv')} 面积{r.get('selfArea')}"
                  f" 预测={r.get('predicted')} 实播={r.get('played')} 复算一致={r.get('agree')}"
                  + (f" 更小竞争框={r.get('smaller')}" if r.get('smaller') else ''))
        if disagree:
            print(f"   ⚠️ 复算与实际派发不一致 {len(disagree)} 条 → 本脚本的几何复算不可信，别据此下结论")
    print(f"\n===== 合计 =====  {tally}")
    ws.close()
    proc.terminate()
    return 0


if __name__ == '__main__':
    sys.exit(main())
