# -*- coding: utf-8 -*-
# 判别式：DOM 渲染了没 vs 页面全局可见不可见
import sys, os, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9379
P = os.path.join(ROOT, '.diag', 'chrome_galprobe3')
os.makedirs(P, exist_ok=True)
URL = 'http://127.0.0.1:8777/gallery_v2/index.html'

subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
  '--remote-allow-origins=*', f'--user-data-dir={P}', '--no-first-run', '--no-default-browser-check',
  '--disable-background-timer-throttling', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--window-size=1280,900', URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

w = None
for i in range(80):
    try:
        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
        w = [t for t in tabs if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
        if w:
            break
    except Exception:
        pass
    time.sleep(0.5)

print('matched tabs = %d ; all targets:' % len(w))
for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')):
    print('   type=%-8s url=%s' % (t.get('type'), str(t.get('url'))[:80]))

ws = websocket.create_connection(w[0]['webSocketDebuggerUrl'], timeout=120, max_size=None)
_id = 0


def cmd(m, p=None):
    global _id
    _id += 1
    mid = _id
    ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}}))
    ws.settimeout(120)
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == mid:
            return r.get('result', {})


def ev(e):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    if r.get('exceptionDetails'):
        return 'EXC ' + str(r['exceptionDetails'].get('text'))[:70]
    return r.get('result', {}).get('value')


time.sleep(6)
print('')
print('--- DOM evidence:')
print('   title            =', ev('document.title'))
print('   body childCount  =', ev('document.body?document.body.childElementCount:-1'))
print('   #grid exists     =', ev('!!document.getElementById("grid")'))
print('   .card count      =', ev('document.querySelectorAll(".card").length'))
print('   script tags      =', ev('[].slice.call(document.scripts).map(function(s){'
                                 'return s.src ? ("src="+s.src.split("/").pop()) : ("inline "+s.textContent.length+"B");'
                                 '}).join(" | ")'))
print('')
print('--- global evidence:')
print('   typeof openShip  =', ev('typeof openShip'))
print('   window.GALLERY   =', ev('typeof window.GALLERY'))
print('   globalThis hits  =', ev('Object.keys(globalThis).filter(function(k){'
                                 'return /GALLERY|openShip|l2State|curShip/i.test(k);}).join(",") || "NONE"'))
print('')
print('--- did index.js run (page-rendered text):')
print('   header stat text =', ev('(document.querySelector(".stat")||{}).textContent || "NO .stat"'))
print('   select option cnt=', ev('document.querySelectorAll("select option").length'))
ws.close()
