# -*- coding: utf-8 -*-
"""动态背景「会不会卡」—— 用**每帧工作量**而不是 fps 来回答。

为什么不能只看 fps：
  ① 第一版用 `--use-angle=swiftshader` 软渲染 ⇒ 15fps 是软件光栅化的代价，与实机无关；
  ② 第二版走真 GPU（RTX 5060 / D3D11）后，**每一档都是 300fps**（= 屏幕 240Hz 的采样上限），
     页面侧根本没有掉帧信号 —— 但"fps 打满"不等于"不费电/不发热"，它只是没被逼到极限。

所以这一版量的是**成本**，三组与后端无关的量：
  · 每帧 draw call 数（Spine：数 drawElements/drawArrays；Live2D：数 PIXI 的 batch）
  · 主线程 JS 每帧耗时（包一层 PIXI ticker 的 update，或用 longtask 旁证）
  · 进程 CPU 占用（走浏览器进程的 Performance.getMetrics —— 只统计该 renderer 进程）

再补一档 **限帧 24fps** 的对照：如果限帧后 CPU 明显降、画面看不出差别，那"不卡"就有了余量。

⚠️ 24fps 上限已写进 site_bg_live.js（Live2D 用 ticker.maxFPS，Spine 在 rAF 里提前 return），
   所以本脚本量到的就是**上线后的真实成本**。
   用法：py -3 scripts/diag/perf_cost.py
   前置：8777 端口上有 gallery_v2 服务，且 Output/gallery_v2/_perf_test.html 存在（那个测试页是临时件）。
"""
import sys, os, time, subprocess, urllib.request, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts', 'diag'))
import websocket, chrome_tree   # noqa

ROOT = os.path.abspath(os.path.join(HERE, '..'))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 58963
PROF = os.path.join(ROOT, '.diag', 'chrome_perf_cost')
URL = 'http://127.0.0.1:8777/gallery_v2/_perf_test.html'

L2D = {'kind': 'live2d', 'key': 'ninghai_4', 'model': 'Live2D/ninghai_4', 'base': 'ninghai_4'}
SPINE = {'kind': 'spine', 'key': 'huanchang_2', 'folder': 'huanchang_2',
         'parts': ['huanchang_2B', 'huanchang_2T']}

proc = subprocess.Popen([CHROME,
    f'--remote-debugging-port={PORT}', '--remote-allow-origins=*',
    f'--user-data-dir={PROF}', '--no-first-run', '--no-default-browser-check',
    '--window-size=1600,1000', '--window-position=-2400,0',
    '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding',
    '--disable-features=CalculateNativeWinOcclusion',
    URL],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ws = None
out = {}
try:
    for _ in range(80):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json', timeout=1))
            t = [x for x in tabs if x.get('type') == 'page']
            if t:
                ws = websocket.create_connection(t[0]['webSocketDebuggerUrl'], timeout=60)
                break
        except Exception:
            pass
        time.sleep(0.5)
    if ws is None:
        print('无法连接 Chrome'); sys.exit(1)

    mid = [0]
    def cmd(method, **params):
        mid[0] += 1
        ws.send(json.dumps({'id': mid[0], 'method': method, 'params': params}))
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == mid[0]:
                return r.get('result', {})

    def ev(expr, wait=0):
        r = cmd('Runtime.evaluate', returnByValue=True, awaitPromise=True, expression=expr)
        if wait:
            time.sleep(wait)
        return r.get('result', {}).get('value')

    cmd('Page.enable'); cmd('Runtime.enable'); cmd('Performance.enable')
    time.sleep(7.0)
    print('GPU: ' + str(ev("JSON.stringify(window.__perf.gpu())")), flush=True)

    def metrics():
        m = cmd('Performance.getMetrics').get('metrics', [])
        return {x['name']: x['value'] for x in m}

    def sample(tag):
        """量 3s：先读基线 metrics，再读末尾 metrics，差值 / 帧数 = 每帧成本。"""
        time.sleep(2.0)                                  # 预热
        ev("window.__perf.hookGL()")                     # 幂等
        base = metrics()
        g0 = ev("JSON.stringify(window.__glN||null)")
        d = ev("window.__perf.sample(3000)")
        g1 = ev("JSON.stringify(window.__glN||null)")
        end = metrics()
        st = ev("window.__perf.liveStats()")
        wf = ev("(()=>{const c=document.querySelector('#bgfx canvas');"
                "return c?getComputedStyle(c).display:null})()")
        frames = max(1, (d or {}).get('frames', 1))
        dsec = max(0.001, ((d or {}).get('ms', 3000)) / 1000.0)
        cost = {
            'TaskDur_ms_total': round((end.get('TaskDuration', 0) - base.get('TaskDuration', 0)) * 1000, 1),
            'ScriptDur_ms_total': round((end.get('ScriptDuration', 0) - base.get('ScriptDuration', 0)) * 1000, 1),
            'TaskDur_ms_per_frame': round((end.get('TaskDuration', 0) - base.get('TaskDuration', 0)) * 1000 / frames, 2),
            'ScriptDur_ms_per_frame': round((end.get('ScriptDuration', 0) - base.get('ScriptDuration', 0)) * 1000 / frames, 2),
            'CPU_pct': round((end.get('TaskDuration', 0) - base.get('TaskDuration', 0)) / dsec * 100, 1),
            'LayoutCount': round((end.get('LayoutCount', 0) - base.get('LayoutCount', 0)) / dsec, 1),
            'RecalcStyle': round((end.get('RecalcStyleCount', 0) - base.get('RecalcStyleCount', 0)) / dsec, 1),
            'gl_per_sec': None,
        }
        if g0 and g1:
            a, b = json.loads(g0), json.loads(g1)
            if a and b:
                cost['gl_per_sec'] = round(((b['de'] - a['de']) + (b['da'] - a['da'])) / dsec, 1)
        out[tag] = {'sample': d, 'cost': cost, 'stats': st, 'water': wf}
        print(f"== {tag}", flush=True)
        print(f"   fps={d['fps']:>6}  modFps={d['modFps']}  "
              f"task={cost['TaskDur_ms_per_frame']}ms/帧  script={cost['ScriptDur_ms_per_frame']}ms/帧  "
              f"CPU={cost['CPU_pct']}%  draw/秒={cost['gl_per_sec']}  "
              f"live={st.get('live') if st else '-'} kind={st.get('kind') if st else '-'}", flush=True)

    sample('A_基线_仅水面')
    ev(f"window.SiteBg.set({json.dumps(L2D)})", wait=1.0); time.sleep(9.0)
    sample('B_Live2D背景')
    ev(f"window.SiteBg.set({json.dumps(SPINE)})", wait=1.0); time.sleep(7.0)
    sample('C_Spine背景')
    ev(f"window.SiteBg.set({json.dumps(L2D)})", wait=1.0); time.sleep(9.0)
    ev("""(()=>{const s=document.createElement('style');s.id='__fw';
           s.textContent='html.has-livebg #bgfx canvas{display:block !important}';
           document.head.appendChild(s);})()""", wait=2.0)
    sample('D_Live2D+水面_最坏')

    json.dump(out, open(os.path.join(ROOT, '.diag', '_perf_cost.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\n已写 .diag/_perf_cost.json')
finally:
    try:
        if ws: ws.close()
    except Exception:
        pass
    chrome_tree.kill_tree(proc.pid)
