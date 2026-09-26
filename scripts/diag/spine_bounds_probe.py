# -*- coding: utf-8 -*-
"""探针：Spine 骨架里哪些槽位把包围盒撑大了（fit 后画面变小/偏心的定位用）。"""
import sys, os, json, time, subprocess, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9349
FOLDER = sys.argv[1] if len(sys.argv) > 1 else 'aluomangshi_2'
proc = subprocess.Popen([
    CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
    '--remote-allow-origins=*', f'--user-data-dir={os.path.join(ROOT,".diag","chrome_bounds")}',
    '--no-first-run', '--no-default-browser-check', '--enable-unsafe-swiftshader',
    '--use-angle=swiftshader', '--window-size=1280,900',
    'http://127.0.0.1:8777/gallery_v2/index.html',
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ws = None
for _ in range(120):
    try:
        for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')):
            if t.get('webSocketDebuggerUrl'):
                ws = websocket.create_connection(t['webSocketDebuggerUrl'], timeout=300); ws.settimeout(300)
                break
        if ws: break
    except Exception: pass
    time.sleep(0.5)
_id = 0
def cmd(m, p=None):
    global _id
    _id += 1
    ws.send(json.dumps({'id': _id, 'method': m, 'params': p or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == _id:
            if 'error' in r: raise RuntimeError(json.dumps(r['error'])[:160])
            return r.get('result', {})
def ev(e, a=False):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': a})
    if r.get('exceptionDetails'): return 'EVALERR ' + str(r['exceptionDetails'].get('text'))[:200]
    return r.get('result', {}).get('value')

JS = r"""
(async (folder) => {
  const t = ms => new Promise(r => setTimeout(r, ms));
  for (let i=0;i<240;i++){ if(typeof GALLERY!=='undefined'&&Array.isArray(GALLERY.ships)&&GALLERY.ships.length) break; await t(500); }
  for (let i=0;i<60;i++){ if (typeof spine!=='undefined'&&spine.webgl) break; await t(500); }
  if (typeof spine==='undefined') return 'no spine (spine-all.js 是页面第 156 行的普通 script，勿再动态加载第二份)';
  const fakeTex=()=>({setFilters(){},setWraps(){},dispose(){},getImage(){return{width:1,height:1};}});
  const base='../Spine_v2/'+folder+'/';
  const bytes=new Uint8Array(await (await fetch(base+folder+'.skel')).arrayBuffer());
  const atlas=new spine.TextureAtlas(await (await fetch(base+folder+'.atlas')).text(), fakeTex);
  const data=new spine.SkeletonBinary(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(bytes);
  const animNames=(data.animations||[]).map(a=>a&&a.name).filter(Boolean);
  const an = animNames.indexOf('normal')>=0 ? 'normal' : animNames[0];

  const extents = (skName) => {
    const s=new spine.Skeleton(data); const st=new spine.AnimationState(new spine.AnimationStateData(data));
    if(skName!==null) s.setSkin(data.findSkin(skName));
    s.setSlotsToSetupPose(); s.setBonesToSetupPose();
    st.setAnimation(0, an, true);
    for(const dt of [0.05,0.5,2.0]){ st.update(dt); st.apply(s); }
    s.updateWorldTransform();
    const rows=[];
    for(const sl of s.slots){ const a=sl.getAttachment(); if(!a||!sl.bone||!sl.bone.active) continue;
      let v,c;
      try{
        if(a instanceof spine.RegionAttachment){ v=spine.Utils.newFloatArray(8); c=8; a.computeWorldVertices(sl.bone,v,0,2); }
        else if(a instanceof spine.MeshAttachment && a.worldVerticesLength){ c=a.worldVerticesLength; v=spine.Utils.newFloatArray(c); a.computeWorldVertices(sl,0,c,v,0,2); }
        else continue;
      }catch(e){ continue; }
      let minX=1e9,maxX=-1e9,minY=1e9,maxY=-1e9;
      for(let j=0;j<c;j+=2){ if(v[j]<minX)minX=v[j]; if(v[j]>maxX)maxX=v[j]; if(v[j+1]<minY)minY=v[j+1]; if(v[j+1]>maxY)maxY=v[j+1]; }
      rows.push({slot:sl.data.name, att:(a.name||''), w:Math.round(maxX-minX), h:Math.round(maxY-minY),
                 x:Math.round(minX), y:Math.round(minY), far:Math.max(Math.abs(minX),Math.abs(maxX),Math.abs(minY),Math.abs(maxY))});
    }
    rows.sort((p,q)=>q.far-p.far);
    return {n:rows.length,
      bbox:[Math.min(...rows.map(r=>r.x)), Math.min(...rows.map(r=>r.y)),
            Math.max(...rows.map(r=>r.x+r.w)), Math.max(...rows.map(r=>r.y+r.h))].map(Math.round),
      farthest: rows.slice(0,10)};
  };
  return JSON.stringify({anim:an, none: extents(null), best: extents('1')}, null, 1);
})
"""
for _ in range(240):
    if ev('String(typeof GALLERY!=="undefined")') == 'true':
        break
    time.sleep(0.5)
print(ev(f'({JS})({json.dumps(FOLDER)})', True))
ws.close(); proc.terminate()
