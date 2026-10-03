# -*- coding: utf-8 -*-
"""探针：Spine 骨架里哪些槽位把包围盒撑大了（fit 后画面变小/偏心的定位用）。"""
import sys, os, json, time, subprocess, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cdp_slot            # 端口不写死：写死会让两个会话灌进同一个页面（见该模块 docstring）
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = cdp_slot.port('bounds')
FOLDER = sys.argv[1] if len(sys.argv) > 1 else 'aluomangshi_2'
SKIN = sys.argv[2] if len(sys.argv) > 2 else '1'
PROFILE = cdp_slot.profile(ROOT, 'bounds')   # 每次全新 profile：复用会把上一次的 chrome 当本页
proc = subprocess.Popen([
    CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
    '--remote-allow-origins=*', f'--user-data-dir={PROFILE}',
    '--no-first-run', '--no-default-browser-check', '--enable-unsafe-swiftshader',
    '--use-angle=swiftshader', '--window-size=1280,900',
    'http://127.0.0.1:8777/gallery_v2/index.html',
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ws = None
for _ in range(120):
    try:
        for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')):
            # 必须按 URL 过滤 target：不过滤会连到 devtools/新标签页，eval 打到空页面上
            if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl'):
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
(async (folder, SKIN) => {
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
  const anim = data.animations && data.animations.length ? (function(){
    for(const A of data.animations) if(A && A.name===an) return A; return null; })() : null;

  /* 对给定槽位，沿整条动画采样 alpha：决定「透明不计入取景」是否是确定性规则 */
  const alphaTrace = (names) => {
    const out = {};
    for(const n of names) out[n] = {setup:null, max:0, times:0};
    const s0=new spine.Skeleton(data); s0.setSlotsToSetupPose(); s0.setBonesToSetupPose();
    for(const n in out){ const sl=s0.slots.find(x=>x.data.name===n);
      if(sl) out[n].setup = sl.color? sl.color.a : (sl.data.color? sl.data.color.a : null); }
    const st=new spine.AnimationState(new spine.AnimationStateData(data));
    if(an) st.setAnimation(0, an, true);
    const dur = anim? anim.duration : 0;
    const NSTEP=40;
    for(let i=0;i<=NSTEP;i++){
      const s=new spine.Skeleton(data); s.setSlotsToSetupPose(); s.setBonesToSetupPose();
      st.update(i===0?0:dur/NSTEP); st.apply(s);
      for(const n in out){ const sl=s.slots.find(x=>x.data.name===n); if(!sl) continue;
        const a=sl.color? sl.color.a : (sl.data.color? sl.data.color.a : 0);
        if(out[n].setup===null) out[n].setup=a;
        if(a>out[n].max) out[n].max=+a.toFixed(3); if(a>0.001) out[n].times++; }
    }
    out.__samples = NSTEP+1; out.__dur = +dur.toFixed(2);
    return out;
  };

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
      const col = sl.color || sl.data.color;
      rows.push({slot:sl.data.name, att:(a.name||''), w:Math.round(maxX-minX), h:Math.round(maxY-minY),
                 x:Math.round(minX), y:Math.round(minY), far:Math.max(Math.abs(minX),Math.abs(maxX),Math.abs(minY),Math.abs(maxY)),
                 a:col?+(col.a).toFixed(3):null, r:col?+(col.r).toFixed(2):null,
                 bsx:+sl.bone.scaleX.toFixed(2), bsy:+sl.bone.scaleY.toFixed(2),
                 reg:(a.width||0)+'x'+(a.height||0)});
    }
    rows.sort((p,q)=>q.far-p.far);
    return {n:rows.length,
      bbox:[Math.min(...rows.map(r=>r.x)), Math.min(...rows.map(r=>r.y)),
            Math.max(...rows.map(r=>r.x+r.w)), Math.max(...rows.map(r=>r.y+r.h))].map(Math.round),
      farthest: rows.slice(0,10)};
  };
  const named = (data.skins||[]).map(k=>k.name).filter(n=>n && n!=='default');
  const sk = named.indexOf(SKIN)>=0 ? SKIN : (named.length? named[0] : null);
  const ext = extents(sk);
  return JSON.stringify({anim:an, skin:sk, n:ext.n, bbox:ext.bbox,
    farthest: ext.farthest, alpha: alphaTrace(ext.farthest.slice(0,6).map(r=>r.slot))}, null, 1);
})
"""
for _ in range(240):
    if ev('String(typeof GALLERY!=="undefined"&&Array.isArray(GALLERY.ships)&&GALLERY.ships.length)') != 'false':
        break
    time.sleep(0.5)
print(ev(f'({JS})({json.dumps(FOLDER)}, {json.dumps(SKIN)})', True))
ws.close()
# 只按本次 PID 杀进程树：terminate() 不回收 chrome 子进程，残留实例会让下次同 profile 跑到旧页面上
subprocess.call(['taskkill', '/T', '/F', '/PID', str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
