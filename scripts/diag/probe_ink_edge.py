# -*- coding: utf-8 -*-
"""进度条笔触前后沿是否真的"化开"：沿横向采样像素，把硬边量成一个数。

为什么要这个：肉眼看截图只能说"好像还有点硬"，说不清是渐变没生效、还是前沿本来就该硬。
把"跨越前沿的亮度跳变"量成一个数字，改前改后就能直接对比，而不是靠印象。

判据：
  · 前沿硬边：跨越前沿（右端）附近，相邻 3px 的平均亮度差 > 18 级 ⇒ 还是刀切
  · 渐变生效：同位置差值 ≤ 10 级
  · 起点硬头：左端 26px 内亮度应从背景色渐变过去，首像素与第 26px 差 < 6 级 ⇒ 淡入失效
用法: py -3 scripts/diag/probe_ink_edge.py [light|dark]
输出: .diag/shots/ink_edge_<theme>.png（整条进度条放大裁切）
"""
import sys, os, json, time, subprocess, base64, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websocket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chrome_tree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cdp_slot
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
THEME = sys.argv[1] if len(sys.argv) > 1 else 'light'
PORT, PROFILE = cdp_slot.slot(ROOT, 'inkedge')
SHOT = os.path.join(ROOT, '.diag', 'shots')
os.makedirs(SHOT, exist_ok=True)

proc = chrome_tree.install(subprocess.Popen(
    [CHROME, '--headless=new', f'--remote-debugging-port={PORT}', '--remote-allow-origins=*',
     f'--user-data-dir={PROFILE}', '--no-first-run', '--no-default-browser-check',
     '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
     '--use-angle=swiftshader', '--window-size=1400,900',
     'http://127.0.0.1:8777/gallery_v2/bgm.html'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

w = None
for _ in range(90):
    try:
        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
        w = [t['webSocketDebuggerUrl'] for t in tabs
             if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
        if w:
            break
    except Exception:
        pass
    time.sleep(0.5)
ws = websocket.create_connection(w[0], timeout=120, max_size=None)
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
            if 'error' in r:
                raise RuntimeError(json.dumps(r['error'])[:200])
            return r.get('result', {})


def ev(e):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    if r.get('exceptionDetails'):
        return 'EVALERR ' + str(r.get('exceptionDetails'))[:400]
    return r.get('result', {}).get('value')


time.sleep(2)
ev(f"try{{setTheme('{THEME}')}}catch(e){{}}")
time.sleep(0.6)
ev("(async()=>{const t=ms=>new Promise(r=>setTimeout(r,ms));"
   "play(0);await t(1200);"
   "try{A.currentTime=Math.min(45,total()*0.4);A.play()}catch(e){}await t(1500)})()")
time.sleep(1.6)

# 整条进度条截图（裁切 = #tide 的盒子）
box = ev("""(()=>{const t=document.getElementById('tide').getBoundingClientRect();
  return {x:Math.round(t.x),y:Math.round(t.y),w:Math.round(t.width),h:Math.round(t.height)+14}})()""")
shot = cmd('Page.captureScreenshot', {
    'format': 'png',
    'clip': {'x': box['x'], 'y': box['y'] - 4, 'width': box['w'], 'height': box['h'], 'scale': 2},
})
p = os.path.join(SHOT, f'ink_edge_{THEME}.png')
open(p, 'wb').write(base64.b64decode(shot['data']))
print('已写', p)

# 在页面里逐像素量亮度剖面（在同源 canvas 上重绘 SVG 太麻烦，直接从截图 dataURL 读）
res = ev("""(async()=>{
  const tide=document.getElementById('tide'), svg=tide.querySelector('svg');
  const b1=document.getElementById('w1').getBBox();
  const tr=tide.getBoundingClientRect(), sr=svg.getBoundingClientRect();
  const k=id=>parseFloat(document.getElementById(id).getAttribute('offset'));
  return JSON.stringify({
    geo:{tw:tr.width, th:tr.height, sw:sr.width, sh:sr.height},
    w1:{x:b1.x, wid:b1.width},
    edgeRatio:(b1.x+b1.width)/1000,
    stops:{k1b:k('k1b'), k1d:k('k1d'), k2b:k('k2b'), k2d:k('k2d')},
    maskApplied:document.getElementById('w1').getAttribute('mask'),
    progress:(()=>{const d=total();return d?+(A.currentTime/d).toFixed(4):0})()
  });
})()""")
print('数据:', res)
try:
    proc.kill()
except Exception:
    pass
