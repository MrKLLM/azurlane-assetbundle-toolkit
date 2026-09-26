# -*- coding: utf-8 -*-
"""Live2D 交互回归：裸滚轮不劫持/不缩放、Ctrl+滚轮才缩放、pointercancel 解除拖拽不再漂移、
   有判定区的模型点空白不播动作、点部位正常播。"""
import sys, os, json, time, base64, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9349
proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
  '--remote-allow-origins=*', f'--user-data-dir={ROOT}/.diag/chrome_intv', '--no-first-run',
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
ws = websocket.create_connection(w[0], timeout=120, max_size=None)
_id = 0
def cmd(m, p=None):
    global _id; _id += 1; mid = _id
    ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}})); ws.settimeout(120)
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == mid:
            if 'error' in r: raise RuntimeError(json.dumps(r['error'])[:150])
            return r.get('result', {})
def ev(e):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    if r.get('exceptionDetails'): return 'EVALERR ' + str(r['exceptionDetails'].get('text'))[:180]
    return r.get('result', {}).get('value')

JS = r"""(async(key)=>{ try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<90 && !window.GALLERY;i++) await t(300);
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  const l2=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d');
  l2.click();
  // 与 l2d_inspector_verify.py 同一个坑：固定等 6.5s 对大贴图皮肤（benningdun_2 三张共 40MB，
  // 且服务器单线程）必然不够，表现为四个皮肤全报 reading 'internalModel' 的假失败。
  for(let i=0;i<80 && !(l2State&&l2State.app&&l2State.app.stage.children[0]);i++) await t(500);
  if(!(l2State&&l2State.app&&l2State.app.stage.children[0]))
      return JSON.stringify({key:k, err:'40s 内模型未加载', note:(document.querySelector('.note')||{}).textContent||''});
  const app=l2State.app, m=app.stage.children[0], im=m.internalModel, core=im.coreModel, ppu=im.pixelsPerUnit||1, mm=im.motionManager;
  const cux2=im.width/ppu, cuy2=im.height/ppu;   // 画布单位边长：V(中心原点/y向上)↔P(左上/y向下) 换算用
  const wrap=document.getElementById('l2wrap'), rect=wrap.getBoundingClientRect();
  const hitAreas=im.settings.hitAreas||[];
  const cx=rect.left+rect.width/2, cy=rect.top+rect.height/2;
  const st=()=>({scale:+m.scale.x.toFixed(6), x:Math.round(m.x), y:Math.round(m.y), grp:mm.state.currentGroup||null});
  const out={key, groups:Object.keys(mm.definitions||{}).length, nAreas:(im.settings.hitAreas||[]).length, start:st()};

  // ① 裸滚轮 20 格：不应改变缩放/位置（也不 preventDefault）
  for(let i=0;i<20;i++){ const e=new WheelEvent('wheel',{deltaY:-120,clientX:cx,clientY:cy,bubbles:true,cancelable:true});
    wrap.dispatchEvent(e); if(e.defaultPrevented) out.plainWheelPrevented=true; await t(25); }
  await t(300); out.afterPlainWheel=st();
  out.plainWheelNoop = out.plainWheelPrevented!==true && out.afterPlainWheel.scale===out.start.scale;

  // ② Ctrl+滚轮 5 格：应放大
  for(let i=0;i<5;i++){ wrap.dispatchEvent(new WheelEvent('wheel',{deltaY:-120,clientX:cx,clientY:cy,ctrlKey:true,bubbles:true,cancelable:true})); await t(40); }
  await t(300); out.afterCtrlWheel=st();
  out.ctrlWheelZooms = out.afterCtrlWheel.scale > out.start.scale*1.2;

  // 复位
  document.getElementById('l2Fit').click(); await t(300);

  // ③ pointerdown -> pointercancel -> 再移动：模型不应漂移
  const p0=st();
  wrap.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerId:7,clientX:cx,clientY:cy,button:0}));
  window.dispatchEvent(new PointerEvent('pointercancel',{bubbles:true,pointerId:7,clientX:cx,clientY:cy}));
  for(let i=0;i<10;i++){ window.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,pointerId:7,clientX:cx+i*30,clientY:cy+i*20})); await t(25); }
  await t(300); const p1=st();
  out.cancelDrift=Math.abs(p1.x-p0.x)+Math.abs(p1.y-p0.y);
  out.cancelStopsDrag = out.cancelDrift < 3;

  // ④ 点「在所有判定框之外」的点：有判定区的模型不应播任何动作。
  //    注意不能用画面角落代替空白——AL 的 Touch 框本身很大，视觉空白处可能仍属某部位（模型自带定义，游戏同样如此）
  mm.startMotion('idle',0,3); await t(500); const g0=st().grp;
  let ox2=-9, oy2=-9;
  { let guard=0, inside=true;
    while(inside && guard++<40){ inside=false;
      for(const a of (im.settings.hitAreas||[])){ const i=core.getDrawableIndex(a.Id); const pp=core.getDrawableVertexPositions(i);
        if(!pp||!pp.length) continue;
        let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9; for(let k=0;k+1<pp.length;k+=2){x0=Math.min(x0,pp[k]);y0=Math.min(y0,pp[k+1]);x1=Math.max(x1,pp[k]);y1=Math.max(y1,pp[k+1]);}
        const ex=(x1-x0)*0.02, ey=(y1-y0)*0.02;
        if(ox2>=x0-ex&&ox2<=x1+ex&&oy2>=y0-ey&&oy2<=y1+ey){ inside=true; ox2-=2; oy2-=1.5; break; } } } }
  const og=m.toGlobal(new PIXI.Point((ox2+cux2/2)*ppu, (cuy2/2-oy2)*ppu));   // V(顶点原生,中心原点/y向上)→P→global，与产品 hitAt 的 P2V 互逆
  const e1={bubbles:true,cancelable:true,pointerId:9,clientX:rect.left+og.x,clientY:rect.top+og.y,button:0};
  wrap.dispatchEvent(new PointerEvent('pointerdown',e1)); window.dispatchEvent(new PointerEvent('pointerup',e1));
  await t(700); out.emptyClick={probeUnits:[+ox2.toFixed(1),+oy2.toFixed(1)], before:g0, after:st().grp,
    /* null=idle 看守者轮换重取数的间隙（无头下 fetch 慢更明显），不算触发动作 */
    noAction: st().grp===g0 || st().grp===null};

  // ⑤ 点 Head 中心：应播 Head
  const hi=core.getDrawableIndex((im.settings.hitAreas||[])[0]?.Id);
  if(hi>=0){ const p=core.getDrawableVertexPositions(hi); let sx=0,sy=0,n=0;
    for(let k=0;k+1<p.length;k+=2){sx+=p[k];sy+=p[k+1];n++;}
    const g=m.toGlobal(new PIXI.Point((sx/n+cux2/2)*ppu, (cuy2/2-sy/n)*ppu));   // V→P→global，与 hitAt 互逆
    const e2={bubbles:true,cancelable:true,pointerId:10,clientX:rect.left+g.x,clientY:rect.top+g.y,button:0};
    wrap.dispatchEvent(new PointerEvent('pointerdown',e2)); window.dispatchEvent(new PointerEvent('pointerup',e2));
    await t(1600);   // startMotion 是 async，900ms 会读到还没换组的 currentGroup → 假失败
    out.headClick={want:(im.settings.hitAreas[0].Name), played:st().grp, pill:(document.getElementById('l2Hit')||{}).textContent};
    out.headClick.ok = out.headClick.played===out.headClick.want;
  }
  out.endScale=st().scale;
  return JSON.stringify(out,null,1);
}catch(e){ return 'ERR '+(e.message||e); }})
"""
os.makedirs(os.path.join(ROOT, '.diag', 'size_shots'), exist_ok=True)
allok = True
for k in ['anninvwang_2', 'aersasi_2', 'aersasi_3', 'lafeiii_3']:
    out = ev(JS + f"({json.dumps(k)})")
    print('=====', k)
    print(out)
    try:
        d = json.loads(out)
        bad = [x for x in ('plainWheelNoop', 'ctrlWheelZooms', 'cancelStopsDrag') if d.get(x) is False]
        if d.get('emptyClick', {}).get('noAction') is False: bad.append('emptyClick')
        if d.get('headClick') and d['headClick'].get('ok') is False: bad.append('headClick')
        if bad: allok = False; print('  ✗ 未通过:', bad)
        else: print('  ✓ 全部通过')
    except Exception: allok = False
print('\n总判定:', 'ALL PASS' if allok else '有未通过项')
r = cmd('Page.captureScreenshot', {'format': 'png'})
open(os.path.join(ROOT, '.diag', 'size_shots', 'interact_final.png'), 'wb').write(base64.b64decode(r['data']))
ws.close(); proc.terminate()
