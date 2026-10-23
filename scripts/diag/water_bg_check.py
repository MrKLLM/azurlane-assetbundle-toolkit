# -*- coding: utf-8 -*-
"""验证「水面背景」在三页（首页 / 音乐库 / 背景库）都真的起来了、而且真的在跑。

为什么要有这个探针：2026-10-15 把水面从 index.html 抽成 `gallery_src/water_bg.js` 给三页共用，
而"抽出来"这件事的失败模式全是静默的：
  · 子页没引脚本        → 那页就是没有水，控制台一声不响；
  · 宿主 `#bgfx` 没建    → 同上；
  · WebGL2 起不来        → 模块自己退回 mode='css'，只有内部字段知道；
  · 循环没被唤醒        → 画面是静止的，而静止本来就是这版的正常态（所以肉眼分辨不出）。
⇒ 判据必须落在**可读的数字**上：mode / hasCanvas / frames 在涨 / strokes>0。

四条判据（每页都跑一遍）：
  ① `WaterBg.stats().mode === 'gl'` 且 `host` 与 `hasCanvas` 都为真；
  ② 发可信鼠标移动后 `frames` 增加、`strokes>0`、`peak>0`（证明循环真的在画）；
  ③ 设了站用背景 ⇒ 普通页循环停（`raf=false`）且 canvas 被 CSS 藏掉（`display:none`）；
     ⚠️ 音乐库页 `body.force-water` 例外：它有自己的海图背景，设站用背景后水面仍要跑；
  ④ 取消站用背景 ⇒ 循环自己回来（`raf=true`）—— 这条正是"取消背景之后海面不回来"那个老 bug 的判据。
     ⚠️ 取消这一步**走产品按钮**（`#clearBg`，2026-10-15 加的「去掉背景图」），没有该按钮的页才回落
     `SiteBg.clear()`；顺带查 ⑤ 按钮的置灰语义（设了背景必须可点、取消后必须置灰）。

用法：
  py -3 scripts/diag/water_bg_check.py                 # 三页全查
  py -3 scripts/diag/water_bg_check.py --pages bgm.html
⚠️ 本机 HTTP_PROXY 会劫持 127.0.0.1（CDP 与页面请求都变 502）⇒ 运行前清掉代理环境变量。
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, os.path.join(ROOT, 'gallery_src'))
import cdp_slot                 # noqa: E402
import chrome_tree              # noqa: E402
import _gallery_server as GS    # noqa: E402

CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
AP = argparse.ArgumentParser()
AP.add_argument('--pages', default='index.html,bgm.html,backgrounds.html')
AP.add_argument('--win', default='1366,853')
A = AP.parse_args()

STATS = 'JSON.stringify(window.WaterBg?WaterBg.stats():null)'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def check_page(page, httpd_port, win):
    url = f'http://127.0.0.1:{httpd_port}/gallery_v2/{page}?v={int(time.time())}'
    dport, profile = cdp_slot.slot(ROOT, 'waterbg')
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={dport}',
                             '--remote-allow-origins=*', f'--user-data-dir={profile}',
                             '--no-first-run', '--no-default-browser-check',
                             '--disable-background-timer-throttling', '--hide-scrollbars',
                             f'--window-size={win}', url],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(proc)
    ws = None
    try:
        import websocket
        for _ in range(90):
            try:
                tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{dport}/json'))
                cand = [t['webSocketDebuggerUrl'] for t in tabs
                        if page in t.get('url', '') and t.get('webSocketDebuggerUrl')]
                if cand:
                    ws = websocket.create_connection(cand[0], timeout=120, max_size=None)
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if ws is None:
            return ['[FAIL] DevTools 连不上']
        nid = [0]

        def cmd(method, params=None, timeout=120):
            nid[0] += 1
            ws.send(json.dumps({'id': nid[0], 'method': method, 'params': params or {}}))
            ws.settimeout(timeout)
            while True:
                r = json.loads(ws.recv())
                if r.get('id') == nid[0]:
                    if 'error' in r:
                        raise RuntimeError(json.dumps(r['error'])[:200])
                    return r.get('result', {})

        def ev(expr):
            r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True,
                                         'awaitPromise': True})
            if r.get('exceptionDetails'):
                return 'EXC ' + json.dumps(r['exceptionDetails'], ensure_ascii=False)[:200]
            return r.get('result', {}).get('value')

        fails = []
        # 等模块就绪（DOMContentLoaded 之后才建 canvas）
        st = None
        for _ in range(40):
            v = ev(STATS)
            st = json.loads(v) if isinstance(v, str) and v.startswith('{') else None
            if st and st.get('mode') == 'gl':
                break
            time.sleep(0.25)
        if not st:
            return [f'[FAIL] WaterBg 没起来：{ev(STATS)}']
        print(f'  初始: {json.dumps(st, ensure_ascii=False)}')
        # ① 模块与宿主
        if st['mode'] != 'gl':
            fails.append(f"① mode={st['mode']}（err={st.get('err')}）⇒ 水面没跑 WebGL")
        if not st['host']:
            fails.append('① #bgfx 宿主不存在')
        if not st['hasCanvas']:
            fails.append('① canvas 没建出来')
        # ② 划一下必须真的画（发可信鼠标事件：合成事件不走 hover，但水面的 pointermove 是 window 级，两者都收）
        f0, s0 = st['frames'], st['strokes']
        W, H = (int(x) for x in win.split(','))
        for i in range(24):
            x = W * (0.10 + 0.80 * (i / 23.0))
            y = H * (0.35 + 0.30 * ((i % 6) / 5.0))
            cmd('Input.dispatchMouseEvent',
                {'type': 'mouseMoved', 'x': x, 'y': y, 'buttons': 0, 'pointerType': 'mouse'})
            time.sleep(0.04)
        time.sleep(0.8)
        st2 = json.loads(ev(STATS))
        print(f'  划动后: frames {f0}→{st2["frames"]} · strokes {s0}→{st2["strokes"]} '
              f'· peak={st2["peak"]}')
        if st2['frames'] <= f0:
            fails.append('② 划动后 frames 没涨 ⇒ 波动循环没跑')
        if st2['strokes'] <= s0:
            fails.append('② 划动后 strokes 没涨 ⇒ 指针没注进水场')
        if not st2['peak'] > 0:
            fails.append('② peak=0 ⇒ 场是平的，画不出东西')
        # ③ 设站用背景：普通页让位（停循环 + 藏 canvas）；
        #    音乐库（force-water）例外——它有自己的海图背景，水面要留在上面。
        force = bool(ev("document.body.classList.contains('force-water')"))
        ev("window.SiteBg&&SiteBg.set({url:'/probe-not-exist.png',kind:'bg',key:'probe',label:'probe'})")
        time.sleep(0.6)
        st3 = json.loads(ev(STATS))
        disp = ev("(()=>{const c=document.querySelector('#bgfx canvas');"
                  "return c?getComputedStyle(c).display:'none';})()")
        site_set = bool(ev("!!(window.SiteBg&&SiteBg.get())"))
        print(f'  设背景后: raf={st3["raf"]} · siteBg={st3["siteBg"]} · '
              f'force={force} · canvas display={disp}')
        if not site_set:
            fails.append('③ 站用背景没设成功（探针前置失败）')
        if force:
            if not st3['raf']:
                fails.append('③ force-water 页设背景后水面不该停')
            if disp == 'none':
                fails.append('③ force-water 页设背景后 canvas 不该被藏')
        else:
            if st3['raf']:
                fails.append('③ 设了站用背景但水面循环还在跑 ⇒ 白烧帧')
            if disp != 'none':
                fails.append(f'③ 设了站用背景但 canvas 没被藏（display={disp}）')
        # ④ 取消背景 ⇒ 循环自己回来。**优先走产品按钮**（有 #clearBg 的页），没有才回落 API ——
        #    直接调 SiteBg.clear() 验不到"按钮点了到底有没有用"这条。
        has_btn = bool(ev("!!document.getElementById('clearBg')"))
        if has_btn:
            if ev("document.getElementById('clearBg').disabled"):
                fails.append('⑤ 设了站用背景，「去掉背景图」按钮却是置灰的')
            ev("document.getElementById('clearBg').click()")
        else:
            ev('window.SiteBg&&SiteBg.clear()')
        time.sleep(0.8)
        st4 = json.loads(ev(STATS))
        print(f'  取消背景后（{"产品按钮" if has_btn else "SiteBg.clear()"}）: '
              f'raf={st4["raf"]} · siteBg={st4["siteBg"]}')
        if st4['siteBg']:
            fails.append('④ 取消背景没生效')
        # force-water 页水面从头到尾都没停；取消后理应处于"平静"的 raf=false，
        # 不能拿"已经停了"当失败。普通页才检查"停过的循环要自己回来"。
        if not force and not st4['raf']:
            fails.append('④ 取消背景后水面没自己回来（老 bug：循环停在那不重启）')
        if has_btn and not ev("document.getElementById('clearBg').disabled"):
            fails.append('⑤ 取消后「去掉背景图」按钮没置灰（会让人以为还能再点）')
        return fails or None
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        chrome_tree.kill_tree(proc.pid)


def main():
    port = free_port()
    httpd = GS.make_server(port=port, root=os.path.join(ROOT, 'Output'))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    pages = [p.strip() for p in A.pages.split(',') if p.strip()]
    bad = 0
    try:
        for page in pages:
            print(f'== {page} ==')
            fails = check_page(page, port, A.win)
            if fails:
                bad += 1
                for f in fails:
                    print('  ' + f)
            else:
                print('  [PASS] ①模块/宿主 ②划动在画 ③站用背景停循环 ④取消后自己回来')
    finally:
        httpd.shutdown()
    print(f'\n{"[FAIL] " + str(bad) + " 页有问题" if bad else "[PASS] 三页水面背景全过"}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
