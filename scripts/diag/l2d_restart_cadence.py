# -*- coding: utf-8 -*-
"""取证 3（只读）：idle 到底多久被重启一次？（看守者用 fetch 到的 Duration 定时重开，
fetch 失败会回落 4000ms → 9 秒的 idle 每 3.9 秒被打回起点，观感就是"一直在有点快地动"）
用法: py -3 .diag/l2d_restart_cadence.py [皮肤key] [观察秒数]
"""
import sys, os, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9377
PROFILE = os.path.join(ROOT, '.diag', 'chrome_cadence')
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
ws = websocket.create_connection(w[0], timeout=240, max_size=None)
_id = 0
def cmd(m, p=None):
    global _id; _id += 1; mid = _id
    ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}})); ws.settimeout(240)
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == mid:
            if 'error' in r: raise RuntimeError(json.dumps(r['error'])[:200])
            return r.get('result', {})
def ev(e):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    if r.get('exceptionDetails'): return 'EVALERR ' + str(r.get('exceptionDetails'))[:300]
    return r.get('result', {}).get('value')

KEY = sys.argv[1] if len(sys.argv) > 1 else 'antu_2'
SECS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
JS = r"""(async(args)=>{ const key=args[0], secs=args[1];
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<90 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  const l2=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d');
  l2.click();
  const t0=performance.now();
  while(!l2State || !l2State.app || !l2State.app.stage.children.length){ if(performance.now()-t0>40000) return JSON.stringify({key,skip:'model not ready'}); await t(200); }
  const mdl=l2State.app.stage.children[0], im=mdl.internalModel, core=im.coreModel, mm=im.motionManager;
  const log=[]; const orig=mm.startMotion.bind(mm);
  const idleName=(()=>{const gs=Object.keys(mm.definitions||{});return ['idle','main','home'].find(g=>gs.includes(g))||gs[0]||null;})();
  const arr0=(mm.motionGroups&&mm.motionGroups[idleName])||[]; const m0=arr0[0];
  const patch={groupsIdle:mm.groups&&mm.groups.idle, idleName,
    breathParams:(im.breath&&im.breath.getParameters?im.breath.getParameters().length:'n/a'),
    idleIsLoop:(m0&&m0.isLoop)?{isLoop:m0.isLoop(),loopFadeIn:m0.isLoopFadeIn(),dur:m0.getDuration(),loopDur:m0.getLoopDuration()}:'not loaded yet'};
  window.__stop=false;
  mm.startMotion=function(g,i,p){ log.push({ev:'startMotion', g, p, at:+((performance.now()-t0)/1000).toFixed(2)}); return orig(g,i,p); };
  /* 每 250ms 采样：当前组 + 头部角度（用于看是否被"打回起点"） */
  const iz=core.getParameterIndex('ParamAngleZ'), ix=core.getParameterIndex('ParamAngleX');
  const series=[];
  const end=performance.now()+secs*1000;
  while(performance.now()<end){
    series.push({at:+((performance.now()-t0)/1000).toFixed(2), grp:mm.state.currentGroup||null,
      pri:mm.state.currentPriority, ang: iz>=0?+core.getParameterValueByIndex(iz).toFixed(2):null,
      angx: ix>=0?+core.getParameterValueByIndex(ix).toFixed(2):null,
      entries:(mm.queueManager&&mm.queueManager._motions.length)||0});
    await t(250);
  }
  mm.startMotion=orig;
  return JSON.stringify({key, secs, patch, starts:log, samples:series.filter((_,k)=>k%2===0)},null,1);
})"""
raw = ev(JS + f"({json.dumps([KEY, SECS])})")
path = os.path.join(ROOT, '.diag', '_cadence.json')
with open(path, 'w', encoding='utf-8') as f:
    f.write(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False, indent=1))
try:
    d = json.loads(raw)
    print('key', d.get('key'), 'skip', d.get('skip', ''))
    print('补丁体检：', json.dumps(d.get('patch'),ensure_ascii=False))
    print('startMotion 调用：')
    for s in d.get('starts', []): print('   t=%6.2fs  group=%-8s prio=%s' % (s['at'], s['g'], s['p']))
    ss = d.get('samples', [])
    nulls = [s for s in ss if s['grp'] is None]
    print(f"采样 {len(ss)} 点，currentGroup=null 的点数 {len(nulls)}")
    if ss:
        print('  t(s)  group        pri entries  ParamAngleZ')
        for s in ss[:80]:
            print(f"  {s['at']:6.2f} {str(s['grp']):12s} {s['pri']:3d} {s['entries']:5d}   {s['ang']}")
except Exception:
    print(raw[:3000])
print(f'\n已写出 {path}')
ws.close(); proc.terminate()
