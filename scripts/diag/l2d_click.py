# -*- coding: utf-8 -*-
"""真实点击路径验证：搜索 -> 点卡片 -> 点皮肤 -> 点 Live2D 标签 -> 断言高亮/画面/fit"""
import sys, os, json, time, base64, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9336
proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
  '--remote-allow-origins=*', f'--user-data-dir={ROOT}/.diag/chrome_l2d_click',
  '--no-first-run', '--no-default-browser-check', '--disable-background-timer-throttling',
  '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--window-size=1280,900',
  'http://127.0.0.1:8777/gallery_v2/index.html'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
w = None
for _ in range(60):
    try:
        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
        w = [t['webSocketDebuggerUrl'] for t in tabs if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
        if w: break
    except Exception: pass
    time.sleep(0.5)
ws = websocket.create_connection(w[0], timeout=60)
_id = 0
def cmd(m, p=None):
    global _id; _id += 1
    ws.send(json.dumps({'id': _id, 'method': m, 'params': p or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == _id:
            if 'error' in r: raise RuntimeError(json.dumps(r['error'])[:200])
            return r.get('result', {})
def ev(e, ap=True):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': ap})
    if r.get('exceptionDetails'): return 'EVALERR ' + str(r['exceptionDetails'].get('text'))[:150]
    return r.get('result', {}).get('value')

JS = r"""(async()=>{ try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  const rep=[];
  const targets=[...new Set(GALLERY.ships.filter(x=>(x.live2dSkins||[]).length).map(s=>s.live2dSkins[0]))].slice(0,3);
  for (const key of targets){
    const ship=GALLERY.ships.find(s=>s.live2dSkins.includes(key));
    const q=document.getElementById('search');
    q.value=ship.id; q.dispatchEvent(new Event('input',{bubbles:true}));
    await t(900);
    const card=[...document.querySelectorAll('.card')].find(c=>{const p=c.querySelector('.py');return p&&p.textContent.trim().startsWith(ship.id);});
    if(!card){ rep.push({key, fail:'card not in grid'}); continue; }
    card.click(); await t(700);
    const skinEl=document.querySelector('.skin[data-k="'+key+'"]');
    if(!skinEl){ rep.push({key, fail:'skin el missing'}); continue; }
    skinEl.click(); await t(700);
    const tabs=[...document.querySelectorAll('#mTabs .tab')];
    const l2=tabs.find(x=>x.dataset.k==='live2d');
    if(!l2||l2.classList.contains('dis')){ rep.push({key, fail:'tab missing/disabled'}); continue; }
    l2.click(); await t(7000);
    const app=l2State&&l2State.app, m=app&&app.stage.children[0];
    const wrap=document.getElementById('l2wrap');
    rep.push({key, ship:ship.id, activeTab:[...document.querySelectorAll('#mTabs .tab.on')].map(x=>x.dataset.k),
      model:!!m, dispW:m&&Math.round(m.width), dispH:m&&Math.round(m.height),
      wrapW:wrap&&wrap.clientWidth, wrapH:wrap&&wrap.clientHeight,
      fitsInWrap: m? (m.width<=wrap.clientWidth+2 && m.height<=wrap.clientHeight+2):null,
      groups:m&&Object.keys(m.internalModel.motionManager.definitions).length,
      motion:(document.getElementById('l2Motion')||{}).value||null});
    document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})); await t(400);
  }
  return JSON.stringify(rep,null,1);
}catch(e){ return 'ERR '+(e.message||e); }})()"""

print('CLICK:', ev(JS))
cmd('Emulation.setDeviceMetricsOverride', {'width':1280,'height':900,'deviceScaleFactor':1,'mobile':False})
r = cmd('Page.captureScreenshot', {'format':'png'})
open(os.path.join(ROOT,'.diag','l2d_shots','click_path.png'),'wb').write(base64.b64decode(r['data']))
ws.close(); proc.terminate()
