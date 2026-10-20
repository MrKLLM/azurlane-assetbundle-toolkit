# -*- coding: utf-8 -*-
"""动态背景（Live2D / Spine）作网页背景的性能实测 —— **硬件后端版**。

第一版（perf_livebg.py）的缺陷：Chrome 用 `--use-angle=swiftshader` 起，**纯 CPU 软渲染**
⇒ 量到的 15fps 是软件光栅化的代价，不是用户的实机表现。**量具本身决定了结论。**

第二版改三处：
  ① 去掉 `--use-angle=swiftshader`，让 Chrome 走真实 GPU；同时把 WEBGL_debug_renderer_info
     读出来记档（判断"这次到底有没有硬件加速"）。
  ② 不用 `--headless=new`（headless 常常拿不到 GPU），改用**真实窗口** + `--window-position=-2400,0`
     把它摆到屏幕外，不打扰用户。
  ③ 除以 rAF fps 为主，还同时记「模块内部帧数」「长任务数/最长任务」「两帧间隔」
     —— 这些量在软渲染/硬渲染下都成立，能交叉验证 fps 为什么低。

四档（fps 只作余量参考；成本请看 perf_cost.py）：
  A 基线        只有水面背景
  B Live2D 背景
  C Spine 背景
  D Live2D+水面 强制两套同时跑（最坏情况）

⚠️ 本脚本只回答"有没有硬件加速 + 页面掉不掉帧"。**fps 打满 ≠ 不费电**：
   实测各档都是 300fps（采样上限），所以真正的判据在 perf_cost.py（每帧主线程耗时 + CPU% + 长任务）。
"""
import sys, os, time, subprocess, urllib.request, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts', 'diag'))
import websocket, chrome_tree   # noqa

ROOT = os.path.abspath(os.path.join(HERE, '..'))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 58962
PROF = os.path.join(ROOT, '.diag', 'chrome_perf_gpu')
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

    cmd('Page.enable'); cmd('Runtime.enable')
    time.sleep(7.0)

    gpu = ev("JSON.stringify(window.__perf.gpu())")
    print('GPU: ' + str(gpu), flush=True)

    def sample(tag):
        time.sleep(1.5)                      # 预热，丢掉首帧抖动
        d = ev("window.__perf.sample(3000)")
        st = ev("window.__perf.liveStats()")
        wf = ev("(()=>{const c=document.querySelector('#bgfx canvas');"
                "return c?{display:getComputedStyle(c).display,w:c.width,h:c.height}:null})()")
        out[tag] = {'s': d, 'stats': st, 'water': wf, 'gpu': gpu}
        if d:
            lt = d.get('longtask') or {}
            print(f"== {tag}: fps={d['fps']:>6}  gap={d['gapMs']}ms  modFps={d['modFps']}  "
                  f"longtask={lt.get('n')}/{lt.get('totalMs')}ms max={lt.get('maxMs')}ms  "
                  f"live={st.get('live') if st else '-'} kind={st.get('kind') if st else '-'} "
                  f"err={st.get('err') if st else '-'} water={(wf or {}).get('display')}", flush=True)
        else:
            print(f"== {tag}: 采样失败", flush=True)

    sample('A_基线_仅水面')

    ev(f"window.SiteBg.set({json.dumps(L2D)})", wait=1.0)
    time.sleep(9.0)
    sample('B_Live2D背景')

    ev(f"window.SiteBg.set({json.dumps(SPINE)})", wait=1.0)
    time.sleep(7.0)
    sample('C_Spine背景')

    ev(f"window.SiteBg.set({json.dumps(L2D)})", wait=1.0)
    time.sleep(9.0)
    ev("""(()=>{
      const s=document.createElement('style'); s.id='__force_water';
      s.textContent='html.has-livebg #bgfx canvas{display:block !important}';
      document.head.appendChild(s);
    })()""", wait=2.0)
    sample('D_Live2D+水面_最坏')

    print('\n===== 汇总 =====')
    for k, v in out.items():
        d = v['s'] or {}
        print(f"{k:22s} fps={d.get('fps'):>6}  gap={d.get('gapMs')}ms  modFps={d.get('modFps')}  "
              f"longtask={(d.get('longtask') or {}).get('n')}")

    json.dump(out, open(os.path.join(ROOT, '.diag', '_perf_result_gpu.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\n已写 .diag/_perf_result_gpu.json')
finally:
    try:
        if ws: ws.close()
    except Exception:
        pass
    chrome_tree.kill_tree(proc.pid)
