# -*- coding: utf-8 -*-
"""临时取证：播某个动作组后，库有没有真的创建并播放 Audio（量 currentAudio 的真实状态，不听「有没有调 startMotion」）。
用法: py -3 .diag/l2d_voice_probe.py antu_2 touch_head,touch_body,touch_special
"""
import sys, os, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9385
PROFILE = os.path.join(ROOT, '.diag', 'chrome_voice')
os.makedirs(PROFILE, exist_ok=True)
proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
  '--remote-allow-origins=*', f'--user-data-dir={PROFILE}', '--no-first-run',
  '--no-default-browser-check', '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
  '--use-angle=swiftshader', '--autoplay-policy=no-user-gesture-required',
  '--window-size=1280,900',
  'http://127.0.0.1:8777/gallery_v2/index.html'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
w = None
for _ in range(90):
    try:
        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
        w = [t['webSocketDebuggerUrl'] for t in tabs if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
        if w: break
    except Exception: pass
    time.sleep(0.5)
ws = websocket.create_connection(w[0], timeout=300, max_size=None)
_id = 0
def cmd(m, p=None):
    global _id; _id += 1; mid = _id
    ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}})); ws.settimeout(300)
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == mid:
            if 'error' in r: raise RuntimeError(json.dumps(r['error'])[:200])
            return r.get('result', {})
def ev(e):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    if r.get('exceptionDetails'): return 'EVALERR ' + str(r.get('exceptionDetails'))[:300]
    return r.get('result', {}).get('value')

JS = r"""(async(args)=>{ const key=args[0], grps=args[1].split(',');
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  window.__w=[]; const ow=console.warn; console.warn=(...a)=>{ window.__w.push(a.map(x=>String(x&&x.message||x)).join(' ').slice(0,180)); ow(...a); };
  for(let i=0;i<90 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  [...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d').click();
  const t0=performance.now();
  while(!l2State||!l2State.app||!l2State.app.stage.children.length){ if(performance.now()-t0>40000) break; await t(200); }
  const mdl=l2State.app.stage.children[0], im=mdl.internalModel, mm=im.motionManager;
  const out={key, cfg:{sound:PIXI.live2d.config.sound, motionSync:PIXI.live2d.config.motionSync}, tests:[]};
  const sel=document.getElementById('l2Motion');
  for(let i=0;i<20 && ((document.getElementById('l2Voice')||{}).textContent||'').indexOf('加载')>=0;i++) await t(200);
  out.voicePill=(document.getElementById('l2Voice')||{}).textContent;   /* 必须等完再读，早读必然还是「加载中」 */
  out.firstGroup=mm.state&&mm.state.currentGroup;                        /* 开局有没有真的播上 idle */
  /* fillSel 会给有语音的组加「（语音）」后缀 —— 读 option 文案就能反推前端实际认到了哪些组 */
  out.voiceOptions=[...sel.options].filter(o=>o.textContent.includes('（语音）')).map(o=>o.value);
  out.nOptions=sel.options.length;
  out.hasTouchHeadDef=!!(mm.definitions||{}).touch_head;
  out.touchHeadFile=(((mm.definitions||{}).touch_head||[])[0]||{}).File;
  for(const g of grps){
    const before=window.__w.length;
    sel.value=g; const applied=sel.value;
    sel.onchange();
    let seen=null;
    for(let i=0;i<14;i++){ await t(250); const a=mm.currentAudio;
      if(a){ seen={src:a.src, readyState:a.readyState, networkState:a.networkState, paused:a.paused,
                    cur:+a.currentTime.toFixed(2), dur:a.duration, vol:a.volume,
                    err:a.error?('code'+a.error.code):null}; break; } }
    const d=((mm.definitions[g]||[])[0]||{});
    out.tests.push({group:g, applied:applied, defSound:d.Sound?d.Sound.split('/').slice(-2).join('/'):null,
                    audio:seen, newWarns:window.__w.slice(before)});
    await t(600);
  }
  return JSON.stringify(out, null, 1);
})"""
key = sys.argv[1] if len(sys.argv) > 1 else 'antu_2'
grps = sys.argv[2] if len(sys.argv) > 2 else 'touch_head,touch_body,touch_special,main_1,home'
raw = ev(JS + f"({json.dumps([key, grps])})")
print(raw)
open(os.path.join(ROOT, '.diag', '_voice_probe.json'), 'w', encoding='utf-8').write(
    raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))
ws.close(); proc.terminate()
