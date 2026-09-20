# -*- coding: utf-8 -*-
"""无头 Chrome + CDP 驱动 cg_export.html 导出 Spine setup-pose CG。
用法: py -3 .diag/run_cg_export.py [--only a,b,c] [--size 2400] [--timeout 1800]
"""
import sys, os, json, time, subprocess, urllib.request, threading
sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9333
DEBUG_DIR = os.path.join(ROOT, '.diag', 'chrome_cg_export')

def arg(name, default=None):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default

only = arg('--only', '')
size = arg('--size', '2400')
timeout = int(arg('--timeout', '1800'))

url = f'http://127.0.0.1:8777/gallery_v2/cg_export.html?autostart=1&size={size}'
if only:
    url += '&only=' + only
if '--redo' in sys.argv:
    url += '&redo=1'

os.makedirs(DEBUG_DIR, exist_ok=True)
proc = subprocess.Popen([
    CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
    '--remote-allow-origins=*',
    f'--user-data-dir={DEBUG_DIR}', '--no-first-run', '--no-default-browser-check',
    '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
    '--use-angle=swiftshader', '--window-size=1280,900',
    url,
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_ws():
    for _ in range(60):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
            for t in tabs:
                if 'cg_export' in t.get('url', '') and t.get('webSocketDebuggerUrl'):
                    return t['webSocketDebuggerUrl']
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError('CDP 未就绪')

ws_url = wait_ws()
ws = websocket.create_connection(ws_url, timeout=30)
_id = 0
def ev(expr):
    global _id
    _id += 1
    ws.send(json.dumps({'id': _id, 'method': 'Runtime.evaluate',
                        'params': {'expression': expr, 'returnByValue': True}}))
    while True:
        m = json.loads(ws.recv())
        if m.get('id') == _id:
            return m.get('result', {}).get('result', {}).get('value')

t0 = time.time()
last = ''
while time.time() - t0 < timeout:
    prog = ev("document.querySelector('#prog').textContent") or ''
    tail = ev("(function(){var l=document.querySelectorAll('#log div');return l.length?l[l.length-1].textContent:''})()") or ''
    line = f'{prog} | {tail[:110]}'
    if line != last:
        print(f'[{int(time.time()-t0):4d}s] {line}', flush=True)
        last = line
    if ('全部结束' in tail) or ('已停止' in tail):
        break
    time.sleep(2)
print('DONE, rc check')
ws.close()
proc.terminate()
