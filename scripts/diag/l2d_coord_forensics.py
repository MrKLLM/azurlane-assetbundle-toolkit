# -*- coding: utf-8 -*-
"""Live2D 坐标系取证：验证「顶点 V ↔ 屏幕 P」仿射换算是否正确。

背景（2026-09-23 实测，TROUBLESHOOTING §20）：
  coreModel.getDrawableVertexPositions() 返回 V = Cubism 原生坐标（画布中心为原点、y 向上），
  而 mdl.toLocal()/pixelsPerUnit 得 P = 左上角原点、y 向下。换算：Vx=Px-cux/2，Vy=cuy/2-Py。

判据：在可见模型的 head/chest/hip 三个语义位置反查（不经过被测映射的独立锚点），
      经 flip 映射后应分别落入 Head / Special / Body 框；恒等映射应全部脱靶。
      若 flipHits 出现明显错配（如 head 落到 Body），说明前端 P2V/V2P 或框生成有问题。

用法: py -3 scripts/diag/l2d_coord_forensics.py [皮肤key，默认 lafeiii_3]
输出: .diag/_probe_affine.json（UTF-8），终端打印摘要
"""
import sys, os, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9371
PROFILE = os.path.join(ROOT, '.diag', 'chrome_coordfix')
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
ws = websocket.create_connection(w[0], timeout=180, max_size=None)
_id = 0
def cmd(m, p=None):
    global _id; _id += 1; mid = _id
    ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}})); ws.settimeout(180)
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == mid:
            if 'error' in r: raise RuntimeError(json.dumps(r['error'])[:150])
            return r.get('result', {})
def ev(e):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    if r.get('exceptionDetails'): return 'EVALERR ' + str(r.get('exceptionDetails'))[:300]
    return r.get('result', {}).get('value')

KEY = sys.argv[1] if len(sys.argv) > 1 else 'lafeiii_3'
JS = r"""(async(key)=>{ try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<90 && !window.GALLERY;i++) await t(300);
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  const l2=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d');
  l2.click(); await t(6000);
  const app=l2State.app, m=app.stage.children[0], im=m.internalModel, core=im.coreModel, ppu=im.pixelsPerUnit||1;
  const cu=im.width/ppu;
  const out={cu:+cu.toFixed(3), boxes:[]};
  const P2V=(px,py,flip)=>({x:px-cu/2, y:flip?cu/2-py:py-cu/2});
  for(const a of (im.settings.hitAreas||[])){
    const idx=core.getDrawableIndex(a.Id); const p=core.getDrawableVertexPositions(idx);
    let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
    for(let k=0;k+1<p.length;k+=2){ if(p[k]<x0)x0=p[k]; if(p[k]>x1)x1=p[k]; if(p[k+1]<y0)y0=p[k+1]; if(p[k+1]>y1)y1=p[k+1]; }
    out.boxes.push({name:a.Name, V:[+x0.toFixed(2),+y0.toFixed(2),+x1.toFixed(2),+y1.toFixed(2)]});
  }
  const wrap=document.getElementById('l2wrap');
  const pts=[{tag:'head',sx:0.44,sy:0.27},{tag:'chest',sx:0.44,sy:0.47},{tag:'hip',sx:0.44,sy:0.66}];
  out.pts=[];
  for(const q of pts){
    const lp=m.toLocal(new PIXI.Point(wrap.clientWidth*q.sx, wrap.clientHeight*q.sy));
    const Px=lp.x/ppu, Py=lp.y/ppu;
    const id={x:Px,y:Py}, flip=P2V(Px,Py,true);
    const inBox=(v,b,pad=0.5)=> v.x>=b[0]-pad&&v.x<=b[2]+pad&&v.y>=b[1]-pad&&v.y<=b[3]+pad;
    out.pts.push({tag:q.tag, P:[+Px.toFixed(2),+Py.toFixed(2)],
      identityHits:out.boxes.filter(b=>inBox(id,b.V)).map(b=>b.name),
      flipHits:out.boxes.filter(b=>inBox(flip,b.V)).map(b=>b.name)});
  }
  return JSON.stringify(out,null,1);
}catch(e){ return 'ERR '+(e.message||e); }})"""
out = ev(JS + f"({json.dumps(KEY)})")
path = os.path.join(ROOT, '.diag', '_probe_affine.json')
with open(path, 'w', encoding='utf-8') as f:
    f.write(out if isinstance(out, str) else json.dumps(out))
print(out)
print(f'\n已写出 {path}')
print('判据：head→Head / chest→Special / hip→Body（flipHits 列）；identityHits 应全空。')
ws.close(); proc.terminate()
