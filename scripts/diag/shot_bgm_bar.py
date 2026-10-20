# -*- coding: utf-8 -*-
"""一次性：给 bgm.html 播放条拍截图（浅色 + 暗色），并附一组几何取证。

判据（数字代替"看起来对不对"，踩过的坑都变成这里的断言）：
  ① 进度条 <svg> 必须铺满 .tide（宽高比误差 < 1px）—— 上一版 `.bar svg{16px}` 把它压成
     16×16 的小方块，症状是"整条空槽，只有一处 6×11 的墨点"，肉眼会误判成"颜色太淡"；
  ② `.w1/.w2` 的 bbox 宽度必须 ≈ prog × 1000，否则是路径算错而不是配色错；
  ③ 播放条必须 `.on` 且 opacity=1（它有 opacity:0 + translateY(105%)，没升起来拍到的是空的）；
  ④ 同时裁一张只含播放条（含 24px 余量，看投影与纸边）的图。

用法：
  py -3 scripts/diag/shot_bgm_bar.py                # 浅色 + 暗色
  py -3 scripts/diag/shot_bgm_bar.py --theme dark   # 只拍暗色
  输出：.diag/shots/<theme>_bar.png 与 <theme>_full.png（2 倍图，1664×1060 视口）
"""
import sys
import os
import time
import subprocess
import urllib.request
import json
import base64

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import websocket                      # noqa: E402
import chrome_tree                    # noqa: E402

CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 58970
PROF = os.path.join(ROOT, '.diag', 'chrome_shot')
URL = 'http://127.0.0.1:8777/gallery_v2/bgm.html'
OUT = os.path.join(ROOT, '.diag', 'shots')
os.makedirs(OUT, exist_ok=True)

DESKTOP = os.environ.get('GALLERY_URL', URL)
proc = subprocess.Popen([CHROME,
                         f'--remote-debugging-port={PORT}', '--remote-allow-origins=*',
                         f'--user-data-dir={PROF}', '--no-first-run', '--no-default-browser-check',
                         '--window-size=1600,1000', '--window-position=-2400,0',
                         '--force-device-scale-factor=2',
                         '--disable-backgrounding-occluded-windows',
                         '--disable-renderer-backgrounding',
                         '--disable-features=CalculateNativeWinOcclusion',
                         DESKTOP],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

fails = []


def check(ok, msg):
    print(('  PASS  ' if ok else '  FAIL  ') + msg)
    if not ok:
        fails.append(msg)


ws = None
try:
    for _ in range(80):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json', timeout=1))
            t = [x for x in tabs if x.get('type') == 'page']
            if t:
                ws = websocket.create_connection(t[0]['webSocketDebuggerUrl'], timeout=90)
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

    def ev(expr):
        return cmd('Runtime.evaluate', returnByValue=True, awaitPromise=True,
                   expression=expr).get('result', {}).get('value')

    cmd('Page.enable'); cmd('Runtime.enable')
    time.sleep(6.0)
    ev("(()=>{const r=document.querySelector('#list .row');if(r)r.click();return !!r})()")
    time.sleep(2.5)
    # 拖到 38%，让进度条有内容
    ev("""(()=>{const t=document.getElementById('tide');const r=t.getBoundingClientRect();
        const x=r.left+r.width*0.38,y=r.top+r.height/2;
        t.dispatchEvent(new PointerEvent('pointerdown',{clientX:x,clientY:y,bubbles:true,pointerId:1}));
        t.dispatchEvent(new PointerEvent('pointerup',{clientX:x,clientY:y,bubbles:true,pointerId:1}));
        return true})()""")
    time.sleep(1.2)

    only = None
    if '--theme' in sys.argv:
        only = sys.argv[sys.argv.index('--theme') + 1]
    themes = [only] if only else ['light', 'dark']

    for theme in themes:
        ev(f"(()=>{{const b=document.querySelector('[data-t=\"{theme}\"]');if(b)b.click();"
           f"return document.documentElement.dataset.theme}})()")
        time.sleep(1.4)
        st = ev("""(()=>{const b=document.getElementById('bar');const r=b.getBoundingClientRect();
          const t=document.getElementById('tide'), svg=t.querySelector('svg');
          const tr=t.getBoundingClientRect(), sr=svg.getBoundingClientRect();
          const bb=id=>{const e=document.getElementById(id);const g=e.getBBox();
            return {x:g.x,y:g.y,w:g.width,h:g.height}};
          return {cls:b.className, op:+getComputedStyle(b).opacity,
                  rect:{x:r.x,y:r.y,w:r.width,h:r.height},
                  tide:{w:tr.width,h:tr.height}, svg:{w:sr.width,h:sr.height},
                  w1:bb('w1'), w2:bb('w2'),
                  theme:document.documentElement.dataset.theme}})()""")
        print(f'[{theme}] {st.get("theme")}  bar={"on" in (st.get("cls") or "")}')
        check('on' in (st.get('cls') or ''), f'[{theme}] 播放条已升起（.bar.on）')
        check(st.get('op') == 1, f'[{theme}] 播放条 opacity=1（实得 {st.get("op")}）')
        check(abs(st['svg']['w'] - st['tide']['w']) < 1.5,
              f'[{theme}] 进度条 svg 铺满宽度（svg {st["svg"]["w"]:.1f} vs tide {st["tide"]["w"]:.1f}）')
        check(abs(st['svg']['h'] - st['tide']['h']) < 2.5,
              f'[{theme}] 进度条 svg 铺满高度（svg {st["svg"]["h"]:.1f} vs tide {st["tide"]["h"]:.1f}）')
        check(st['w1']['w'] > 300, f'[{theme}] 墨洇已铺开（w1 bbox 宽 {st["w1"]["w"]:.1f}）')

        full = cmd('Page.captureScreenshot', format='png')
        open(os.path.join(OUT, f'{theme}_full.png'), 'wb').write(base64.b64decode(full['data']))
        r = st['rect']
        clip = {'x': max(0, r['x'] - 24), 'y': max(0, r['y'] - 24),
                'width': min(1600, r['w'] + 48), 'height': r['h'] + 48, 'scale': 2}
        c = cmd('Page.captureScreenshot', format='png', clip=clip)
        open(os.path.join(OUT, f'{theme}_bar.png'), 'wb').write(base64.b64decode(c['data']))
        print(f'  写出 .diag/shots/{theme}_bar.png / _full.png')
finally:
    try:
        if ws:
            ws.close()
    except Exception:
        pass
    chrome_tree.kill_tree(proc.pid)

print()
if fails:
    print(f'== 截图取证：{len(fails)} 项失败')
    for f in fails:
        print('   -', f)
    sys.exit(1)
print('== 截图取证：全部通过')
