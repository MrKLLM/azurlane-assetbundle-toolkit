# -*- coding: utf-8 -*-
"""探针：Live2D 动作播完之后，语音有没有被掐掉。

关键手法：用 CDP `Page.addScriptToEvaluateOnNewDocument` 在**页面脚本执行之前**
包住 `window.Audio`，把每个实例的 play/pause/ended/网络错误录进 window.__AUD。
否则事后在 console 里找"当前有哪些 Audio"是找不到的（库自己 new 完就藏在闭包里）。
"""
import sys, os, json, time, subprocess, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9342
DEBUG_DIR = os.path.join(ROOT, '.diag', 'chrome_l2d_voicecut2')
BASE = 'http://127.0.0.1:8777/gallery_v2/index.html'
KEY = sys.argv[1] if len(sys.argv) > 1 else 'benningdun_2'
GROUP = sys.argv[2] if len(sys.argv) > 2 else 'touch_head'
SECONDS = int(sys.argv[3]) if len(sys.argv) > 3 else 14

HOOK = r"""
window.__AUD = [];
(function(){
  const Real = window.Audio;
  function Wrapped(src){
    const el = new Real(src);
    const rec = {id: window.__AUD.length, src: String(src||'').split('/').pop(),
                 created: +(performance.now()/1000).toFixed(2), events: []};
    rec.el = el;
    window.__AUD.push(rec);
    const push = (k, extra) => rec.events.push(k + '@' + (performance.now()/1000).toFixed(2)
                        + ' t=' + (el.currentTime||0).toFixed(2) + (extra?(' '+extra):''));
    el.addEventListener('play',      ()=>push('play'));
    el.addEventListener('pause',     ()=>push('pause'));
    el.addEventListener('ended',     ()=>push('ended'));
    el.addEventListener('error',     ()=>push('error', el.error && el.error.code));
    el.addEventListener('loadeddata',()=>push('loadeddata',' dur='+el.duration));
    const op = el.play.bind(el); el.play = function(){ push('call:play'); return op(); };
    const pa = el.pause.bind(el); el.pause = function(){ push('call:pause'); return pa(); };
    return el;
  }
  Wrapped.prototype = Real.prototype;
  window.Audio = Wrapped;
})();
"""

proc = subprocess.Popen([
    CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
    '--remote-allow-origins=*', f'--user-data-dir={DEBUG_DIR}',
    '--no-first-run', '--no-default-browser-check',
    '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
    '--use-angle=swiftshader', '--autoplay-policy=no-user-gesture-required',
    '--window-size=1280,900', 'about:blank',
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_ws():
    for _ in range(80):
        try:
            for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')):
                if t.get('webSocketDebuggerUrl'):
                    return t['webSocketDebuggerUrl']
        except Exception:
            pass
        time.sleep(0.5)
    raise SystemExit('CDP 未就绪')


ws = websocket.create_connection(wait_ws(), timeout=300)
ws.settimeout(300)   # 页面冷启动 + 模型加载可 >60s，默认 60s 会把探针自己超时掉
_id = 0


def cmd(method, params=None):
    global _id
    _id += 1
    ws.send(json.dumps({'id': _id, 'method': method, 'params': params or {}}))
    while True:
        m = json.loads(ws.recv())
        if m.get('id') == _id:
            if 'error' in m:
                raise RuntimeError(json.dumps(m['error'])[:200])
            return m.get('result', {})


def ev(expr, awaitp=False):
    r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': awaitp})
    if r.get('exceptionDetails'):
        return 'EVALERR ' + str(r['exceptionDetails'].get('text'))[:120]
    return r.get('result', {}).get('value')


cmd('Page.enable')
cmd('Page.addScriptToEvaluateOnNewDocument', {'source': HOOK})
cmd('Page.navigate', {'url': BASE})

SETTLE = ("""(async () => {
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  // GALLERY 由 index.js 赋值，openShip/renderView 是页面内联脚本后段才定义的函数，
  // 只等 GALLERY 就绪会抢跑（实测报 "openShip is not defined"）。
  const ready=()=>typeof GALLERY!=='undefined'&&Array.isArray(GALLERY.ships)&&GALLERY.ships.length>0
              &&typeof openShip==='function'&&typeof setSkin==='function'&&typeof renderView==='function';
  for(let i=0;i<240;i++){ if(ready()) break; await t(500); }
  if(!ready()) return '页面 120s 未就绪';
  const KEY=__KEY__;
  let ship=null, sk=null;
  for (const s of GALLERY.ships) { const k=s.skins.find(x=>x.key===KEY);
    if(k&&s.live2dSkins.includes(KEY)){ship=s;sk=k;break;} }
  if(!sk) return 'index 里没有该皮肤';
  openShip(ship); setSkin(sk); buildSkinList(ship); tab='live2d'; renderView();
  for(let i=0;i<60;i++){ if(l2State&&l2State.app&&l2State.app.stage.children[0]) break; await t(500); }
  const app=l2State&&l2State.app; if(!app) return '模型未加载';
  const mm=app.stage.children[0].internalModel.motionManager;
  const pill=document.getElementById('l2Voice');
  return JSON.stringify({idleGroup:mm.groups&&mm.groups.idle,
    voicePill: pill&&pill.textContent,
    defsHaveSound: Object.entries(mm.definitions).filter(([k,v])=>v&&v[0]&&v[0].Sound).length});
})()""").replace('__KEY__', json.dumps(KEY))
print('setup:', ev(SETTLE, True), flush=True)

# 语音表是异步回填的：等一拍再读，否则会把"还没到"误读成"没接线"。
# 可观测面 = pill 文案 + 下拉项是否带「（语音）」后缀（fillSel 在 voice[g] 非空时才加）
print('after 4s:', ev("""(async () => { const t=ms=>new Promise(r=>setTimeout(r,ms)); await t(4000);
  const sel=document.getElementById('l2Motion');
  const opt=sel? [...sel.options].find(o=>o.value==='touch_head'):null;
  return JSON.stringify({pill:(document.getElementById('l2Voice')||{}).textContent,
     touchHeadLabel: opt&&opt.textContent, fetchOK: undefined}); })()""", True), flush=True)
try:
    print('fetch l2d_voice.json:', ev("""(async()=>{const r=await fetch('./l2d_voice.json');
      const j=await r.json(); const e=j['benningdun_2']||{};
      return JSON.stringify({status:r.status, groups:Object.keys(e).length,
        touch_head:e['touch_head']}); })()""", True), flush=True)
except Exception as e:
    print('fetch probe failed:', e)

PLAY = ("""(async () => {
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  window.__T0 = +(performance.now()/1000).toFixed(2);
  const sel=document.getElementById('l2Motion'); if(!sel) return 'no select';
  sel.value=__GROUP__; sel.onchange(); return 'started '+sel.value;
})()""").replace('__GROUP__', json.dumps(GROUP))
print('play  :', ev(PLAY, True), flush=True)

PROBE = """(function(){
  const app=l2State&&l2State.app; if(!app) return JSON.stringify({err:'no app'});
  const mm=app.stage.children[0].internalModel.motionManager;
  const t=+(performance.now()/1000).toFixed(2);
  const aud=(window.__AUD||[]).filter(a=>a.el).map(a=>({src:a.src,
     t:+a.el.currentTime.toFixed(2), dur:+a.el.duration.toFixed(2),
     paused:!!a.el.paused, ended:!!a.el.ended, ev:a.events.slice(-2).join(' ')}));
  return JSON.stringify({dt:+(t-(window.__T0||t)).toFixed(1), group:mm.state&&mm.state.currentGroup,
                         nAudio:(window.__AUD||[]).length, aud:aud.slice(-3)});
})()"""
print(f'\n--- 采样 {SECONDS}s ---', flush=True)
for i in range(SECONDS + 1):
    print(f'{ev(PROBE)}', flush=True)
    time.sleep(1.0)

print('\n=== 全部 Audio 实例与事件（相对 play 的秒数） ===')
print(ev("""JSON.stringify((window.__AUD||[]).map(a=>({src:a.src,
  created:+(a.created-(window.__T0||0)).toFixed(2), events:a.events})), null, 1)"""))

ws.close(); proc.terminate()
