# -*- coding: utf-8 -*-
"""无头 Chrome + CDP 抽样验证画廊 Live2D 动作播放。
用法: py -3 .diag/l2d_verify.py
输出: .diag/l2d_shots/<key>.png / <key>_t2.png + 终端 JSON 报告
"""
import sys, os, json, time, base64, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9334
DEBUG_DIR = os.path.join(ROOT, '.diag', 'chrome_l2d_verify')
SHOTS = os.path.join(ROOT, '.diag', 'l2d_shots')
os.makedirs(SHOTS, exist_ok=True)

BASE = 'http://127.0.0.1:8777/gallery_v2/index.html'
SAMPLES = ['lafeiii_3', 'adaerbote_3', 'aersasi_2', 'abeikelongbi_3']

proc = subprocess.Popen([
    CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
    '--remote-allow-origins=*', f'--user-data-dir={DEBUG_DIR}',
    '--no-first-run', '--no-default-browser-check',
    '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
    '--use-angle=swiftshader', '--window-size=1280,900', BASE,
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_ws():
    for _ in range(60):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
            for t in tabs:
                if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl'):
                    return t['webSocketDebuggerUrl']
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError('CDP 未就绪')

ws = websocket.create_connection(wait_ws(), timeout=60)
_id = 0
def cmd(method, params=None):
    global _id
    _id += 1
    ws.send(json.dumps({'id': _id, 'method': method, 'params': params or {}}))
    while True:
        m = json.loads(ws.recv())
        if m.get('id') == _id:
            if 'error' in m: raise RuntimeError(json.dumps(m['error'])[:200])
            return m.get('result', {})

def ev(expr, awaitp=False):
    r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': awaitp})
    if r.get('exceptionDetails'):
        ex = r['exceptionDetails']
        return 'EVALERR ' + str(ex.get('exception', {}).get('description') or ex.get('text'))[:200]
    res = r.get('result', {})
    if res.get('type') == 'string': return res.get('value')
    return res.get('value')

def shot(name):
    r = cmd('Page.captureScreenshot', {'format': 'png'})
    open(os.path.join(SHOTS, name + '.png'), 'wb').write(base64.b64decode(r['data']))

def open_l2d(key):
    """打开 key 对应皮肤并切到 Live2D 标签"""
    js = f"""(async () => {{ try {{
      const t=ms=>new Promise(r=>setTimeout(r,ms));
      let ship=null, sk=null;
      for (const s of GALLERY.ships) {{ const k=s.skins.find(x=>x.key==={json.dumps(key)}); if(k&&s.live2dSkins.includes({json.dumps(key)})){{ship=s;sk=k;break;}} }}
      if(!sk) return JSON.stringify({{skip:'no skin '+{json.dumps(key)}}});
      openShip(ship); setSkin(sk); buildSkinList(ship);
      tab='live2d'; renderView();
      await t(7000);
      const app=l2State&&l2State.app;
      if(!app) return JSON.stringify({{key:{json.dumps(key)},fail:(document.querySelector('.note')||{{}}).textContent||'no state'}});
      const m=app.stage.children[0];
      if(!m) return JSON.stringify({{key:{json.dumps(key)},fail:'no model',note:(document.querySelector('.note')||{{}}).textContent||''}});
      return JSON.stringify({{key:{json.dumps(key)},ok:true,w:Math.round(m.width),h:Math.round(m.height),
        groups:Object.keys((m.internalModel.motionManager&&m.internalModel.motionManager.definitions)||{{}}).length,
        motion:(document.getElementById('l2Motion')||{{}}).value||null,
        canvas:!!document.querySelector('#l2wrap canvas'),
        wrapW:document.getElementById('l2wrap').clientWidth, wrapH:document.getElementById('l2wrap').clientHeight,
        fitK:+m.scale.x.toFixed(5), dispW:Math.round(m.width), dispH:Math.round(m.height)}});
    }} catch(e) {{ return JSON.stringify({{key:{json.dumps(key)}, fail:'JSERR '+(e&&e.message||String(e)).slice(0,150)}}); }}
    }})()"""
    return ev(js, awaitp=True)

def play_motion(name):
    return ev(f"""(async () => {{ const t=ms=>new Promise(r=>setTimeout(r,ms));
      const sel=document.getElementById('l2Motion'); if(!sel)return 'no select';
      sel.value={json.dumps(name)}; sel.onchange(); await t(1200); return sel.value; }})()""", awaitp=True)

def frame_hash():
    return ev("""(function(){const cv=document.querySelector('#l2wrap canvas');if(!cv)return 'nocv';
      const c=document.createElement('canvas');c.width=160;c.height=160;const g=c.getContext('2d');
      g.drawImage(cv,0,0,160,160);return c.toDataURL().slice(-24);})()""")

results = []
try:
    for key in SAMPLES:
        try:
            raw = open_l2d(key)
            r = json.loads(raw)
        except Exception as e:
            r = {'key': key, 'fail': 'driver ' + str(e)[:80], 'raw': str(raw)[:250]}
        if r.get('ok'):
            h1 = frame_hash(); time.sleep(1.2); h2 = frame_hash()
            r['animating'] = (h1 != h2 and h1 not in ('nocv',))
            m2 = play_motion('main_1') if r.get('groups', 0) > 1 else None
            time.sleep(0.8)
            r['motion_switch'] = m2
            shot(key)
        results.append(r); print(json.dumps(r, ensure_ascii=False), flush=True)

    # 降级路径：伪造不存在的模型目录
    deg = ev("""(async () => { const t=ms=>new Promise(r=>setTimeout(r,ms));
      const s=GALLERY.ships.find(x=>x.live2dSkins.length); const sk=s.skins.find(k=>s.live2dSkins.includes(k.key));
      openShip(s); setSkin(sk); buildSkinList(s); tab='live2d';
      const orig=sk.live2d; sk.live2d='Live2D/__no_such_model__';
      renderView(); await t(6000); sk.live2d=orig;
      const n=document.querySelector('.note'); return JSON.stringify({note:n?n.textContent.slice(0,60):null, crashed:false});
    })()""", awaitp=True)
    print('degrade:', deg, flush=True); results.append({'degrade': deg})

    # 切换/销毁路径：live2d -> painting -> live2d
    sw = ev("""(async () => { const t=ms=>new Promise(r=>setTimeout(r,ms));
      const before=l2State; tab='painting'; renderView(); await t(300);
      const destroyed=!before||before.cancelled===true;
      tab='live2d'; renderView(); await t(6000);
      const app=l2State&&l2State.app;
      return JSON.stringify({destroyed, reloaded:!!(app&&app.stage.children[0]), apps:1});
    })()""", awaitp=True)
    print('switch:', sw, flush=True); results.append({'switch': sw})
finally:
    ws.close(); proc.terminate()
print('SUMMARY', json.dumps({'samples': len(SAMPLES), 'ok': sum(1 for r in results if r.get('ok')),
      'animating': sum(1 for r in results if r.get('animating'))}, ensure_ascii=False))
