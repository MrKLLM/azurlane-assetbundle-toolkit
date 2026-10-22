# -*- coding: utf-8 -*-
"""无头 Chrome + CDP 驱动 cg_export.html 导出 Spine setup-pose CG。
用法: py -3 scripts/diag/run_cg_export.py [--only a,b,c] [--size 2400] [--timeout 1800] [--extra 'k=v&k2=v2']
"""
import sys, os, json, time, subprocess, urllib.request, threading
sys.stdout.reconfigure(encoding='utf-8')
import websocket
import sys as _p_sys, os as _p_os
# ⚠️ 本文件在 scripts/diag/ 下，仓库根要**上溯三层**（scripts/diag/run_cg_export.py）。
# 原来只上溯两层再 join "scripts" ⇒ 得到 scripts/scripts ⇒ `import paths` 直接 ModuleNotFoundError
# （2026-10-05 修；脚本从 scripts/ 挪到 scripts/diag/ 时这行没跟着改）。
_AL_ROOT = _p_os.path.dirname(_p_os.path.dirname(_p_os.path.dirname(_p_os.path.abspath(__file__))))
_p_sys.path.insert(0, _p_os.path.join(_AL_ROOT, "scripts"))
import paths as P  # 仓库根与外部工具位置：见 scripts/paths.py（AL_ASSETS_ROOT 可覆盖）


def _chrome_fallback():
    raise SystemExit("找不到 Chrome：设环境变量 AL_CHROME 指向 chrome.exe 再跑")

ROOT = _AL_ROOT
CHROME = P.CHROME.replace(os.sep, "/") or _chrome_fallback()
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
extra = arg('--extra', '')   # 透传给导出页的额外 query，如 --extra 'animFrame=1'
if extra:
    url += '&' + extra
# ⚠️ 破 HTTP 缓存：本脚本复用固定的 DEBUG_DIR profile，浏览器会把
# `/gallery_v2/cg_export.html` 缓存住（只差 query 的 URL 命中同一条缓存）⇒
# **改了页面却导出旧结果**，且两次跑产物 md5 一模一样，极易误判成"改动无效果"
# （2026-10-05 实测踩到）。加个每次都不同的参数即可。
url += '&_t=' + str(int(time.time()))
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

# 页面来自 8777。服务器没起时 Chrome 停在错误页，下面等 #prog 会一直空转到
# --timeout（实测 30 分 03 秒），上层只看到"仍在跑"。连上后 10 秒内没有 #prog
# 就直接失败，把根因说出来。
try:
    for _ in range(10):
        if ev("!!document.querySelector('#prog')"):
            break
        time.sleep(1)
    else:
        print('✗ cg_export.html 没有加载出 #prog（画廊服务器 8777 没起，或页面报错）', flush=True)
        ws.close(); proc.terminate(); sys.exit(2)
except Exception as e:
    print(f'✗ 连上 CDP 但读不到页面（{type(e).__name__}: {e}）', flush=True)
    ws.close(); proc.terminate(); sys.exit(2)

t0 = time.time()
last = ''
done = False
while time.time() - t0 < timeout:
    prog = ev("document.querySelector('#prog').textContent") or ''
    tail = ev("(function(){var l=document.querySelectorAll('#log div');return l.length?l[l.length-1].textContent:''})()") or ''
    line = f'{prog} | {tail[:110]}'
    if line != last:
        print(f'[{int(time.time()-t0):4d}s] {line}', flush=True)
        last = line
    if ('全部结束' in tail) or ('已停止' in tail):
        done = True
        break
    time.sleep(2)
if not done:
    print(f'✗ {timeout}s 内没有收尾行（导出没跑完/页面卡住）', flush=True)
    ws.close()
    proc.terminate()
    sys.exit(3)
print('完成：读到收尾行', flush=True)
ws.close()
proc.terminate()
