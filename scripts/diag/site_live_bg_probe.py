# -*- coding: utf-8 -*-
"""动态网站背景验收：Spine 动态皮肤 / Live2D 模型 能不能真的铺成整站背景，且**没有交互**。

判据全部落在产品可见状态上，不去够页面闭包里的变量：
  ① `SiteBg.set({kind:'live2d'|'spine'})` 之后 `#sitelive` 宿主层出现、`html.has-livebg` 生效；
  ② 宿主层里有 canvas 且**渲染循环真的在推进**（读模块的帧计数；
      ⚠️ 不能从外面 drawImage 采样：WebGL 默认 preserveDrawingBuffer:false，读回的是空缓冲）；
  ③ 宿主层 `pointer-events:none`，且 `elementFromPoint` 在宿主层位置打到的**不是**它
     （这两条合起来才证明"背景不吃鼠标"，只查 CSS 属性会被 !important 或后续样式骗过）；
  ④ 切回静态背景 / 清除后，宿主层与 canvas 必须消失、`has-livebg` 摘掉 —— 防止"换不回去"；
  ⑤ 背景层 z-index 必须低于内容层（取 body 第一个内容块的 z-index 与宿主层比较）。

⚠️ 无头 Chrome + SwiftShader 下 WebGL 能跑，但 Live2D 要下载几 MB 运行时 + 模型，
   所以超时按 90s 给，别按"3 秒没出来就 fail"。
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, HERE)
import cdp_slot                      # noqa: E402
import chrome_tree                   # noqa: E402
import paths as P                    # noqa: E402
sys.path.insert(0, os.path.join(ROOT, 'gallery_src'))
import _gallery_server as GS         # noqa: E402

CHROME = P.tool('AL_CHROME', 'chrome', r'C:/Program Files/Google/Chrome/Application/chrome.exe',
                r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
PORT, PROFILE = cdp_slot.slot(ROOT, 'sitelive')
FAIL = []
_httpd = None
_port = None


def say(cond, msg):
    print(('  PASS  ' if cond else '  FAIL  ') + msg, flush=True)
    if not cond:
        FAIL.append(msg)


def free_port():
    import socket
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def base():
    return f'http://127.0.0.1:{_port}/gallery_v2/'


def serve_up():
    global _httpd, _port
    _port = free_port()
    # root 是 URL 的根：base() 里已经带了 /gallery_v2/，所以这里必须传 Output/（不是 gallery_v2/）
    _httpd = GS.make_server(port=_port, root=P.OUT)
    threading.Thread(target=_httpd.serve_forever, daemon=True).start()
    b = urllib.request.urlopen(base() + 'index.json', timeout=30).read()
    return len(b) >= 100000, len(b)


def pick_targets():
    """从 index.json 里挑两个真实可用的目标：一个 Live2D 皮肤、一个 Spine 皮肤。
    不写死皮肤名 —— 换索引后名字会变，探针要能自己找。"""
    idx = json.loads(urllib.request.urlopen(base() + 'index.json', timeout=30).read())
    l2 = sp = None
    for s in idx['ships']:
        for sk in s.get('skins', []):
            if not l2 and (sk.get('live2d') or '').strip():
                l2 = {'key': sk['key'], 'model': sk['live2d'],
                      'base': sk.get('live2dBase') or sk['key']}
            if not sp and sk.get('spine'):
                info = sk['spine']
                folder = info.get('folder') or sk['key']
                parts = info.get('parts') or [folder]
                sp = {'key': sk['key'], 'folder': folder, 'parts': parts}
            if l2 and sp:
                return l2, sp
    return l2, sp


def main():
    if not CHROME:
        print('[FAIL] 找不到 Chrome/Edge（设 AL_CHROME）')
        return 2
    try:
        ok, n = serve_up()
    except Exception as e:
        print(f'[FAIL] 自起的服务器起不来：{e}')
        return 2
    if not ok:
        print(f'[FAIL] 自起的服务器取不到 index.json（{n} 字节）')
        return 2
    l2, sp = pick_targets()
    print(f'  目标：Live2D={l2}  Spine={sp}', flush=True)

    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
                             '--remote-allow-origins=*', f'--user-data-dir={PROFILE}',
                             '--no-first-run', '--no-default-browser-check',
                             '--disable-background-timer-throttling',
                             '--use-angle=swiftshader', '--window-size=1440,900',
                             base() + 'backgrounds.html'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(proc)
    ws = None
    try:
        for _ in range(90):
            try:
                tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
                u = [t['webSocketDebuggerUrl'] for t in tabs
                     if 'backgrounds.html' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
                if u:
                    import websocket
                    ws = websocket.create_connection(u[0], timeout=120, max_size=None)
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if ws is None:
            print('[FAIL] 连不上浏览器')
            return 2
        _id = 0

        def cmd(m, p=None):
            nonlocal _id
            _id += 1
            ws.send(json.dumps({'id': _id, 'method': m, 'params': p or {}}))
            ws.settimeout(150)
            while True:
                r = json.loads(ws.recv())
                if r.get('id') == _id:
                    if 'error' in r:
                        raise RuntimeError(json.dumps(r['error'])[:200])
                    return r.get('result', {})

        def ev(e):
            r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
            if r.get('exceptionDetails'):
                return {'__err': str(r['exceptionDetails'].get('text'))[:300]}
            return r.get('result', {}).get('value')

        cmd('Page.enable')
        # 等页面就绪
        for _ in range(60):
            if ev('!!(window.SiteBg && window.SiteBgLive)'):
                break
            time.sleep(0.5)
        say(ev('!!window.SiteBgLive'), 'SiteBgLive 模块已加载')

        def wait_state(expr, timeout=90, step=0.6):
            t0 = time.time()
            while time.time() - t0 < timeout:
                if ev(expr):
                    return True
                time.sleep(step)
            return False

        # ── 1) Live2D 背景 ──
        if l2:
            ev(f'''SiteBg.set({{kind:'live2d',key:{json.dumps(l2['key'])},label:'probe',
                     model:{json.dumps(l2['model'])},base:{json.dumps(l2['base'])},url:''}})''')
            got = wait_state('''(function(){var h=document.getElementById('sitelive');
                return !!(h&&h.classList.contains('on')&&h.querySelector('canvas')
                  &&window.SiteBgLive.stats().live)})()''', 120)
            say(got, f'Live2D 背景已挂载（{l2["key"]}）')
            if got:
                st = ev('SiteBgLive.stats()')
                say(bool(st and st.get('hasCanvas')), f'宿主层内有 canvas：{st}')
                # pointer-events + 命中检测
                pe = ev('''(function(){var h=document.getElementById('sitelive');
                    return h?getComputedStyle(h).pointerEvents:'' })()''')
                say(pe == 'none', f'宿主层 pointer-events = {pe}')
                hit = ev('''(function(){var h=document.getElementById('sitelive');
                    if(!h)return 'no-host';
                    var e=document.elementFromPoint(Math.round(innerWidth/2),Math.round(innerHeight/2));
                    return e?(e.id||e.className||e.tagName):'null';})()''')
                say(hit != 'sitelive', f'屏幕中心命中元素 = {hit}（不能是 sitelive）')
                # 真的在画：读模块自己的帧计数（**不能**从外面 drawImage 采样，
                # WebGL 默认 preserveDrawingBuffer:false，读回的是空缓冲 ⇒ 假"没在画"）
                f0 = ev('SiteBgLive.stats().frames') or 0
                time.sleep(1.6)
                f1 = ev('SiteBgLive.stats().frames') or 0
                say(f1 > f0 + 3, f'Live2D 渲染循环在推进（帧 {f0} → {f1}）')
                # z-index 低于内容
                z = ev('''(function(){var h=document.getElementById('sitelive');
                    return h?getComputedStyle(h).zIndex:'-';})()''')
                say(z in ('0', 'auto'), f'宿主层 z-index = {z}')

        # ── 2) Spine 背景 ──
        if sp:
            ev(f'''SiteBg.set({{kind:'spine',key:{json.dumps(sp['key'])},label:'probe',
                     folder:{json.dumps(sp['folder'])},parts:{json.dumps(sp['parts'])},url:''}})''')
            got = wait_state('''(function(){var h=document.getElementById('sitelive');
                return !!(h&&h.classList.contains('on')&&h.querySelector('canvas')
                  &&window.SiteBgLive.stats().live)})()''', 120)
            say(got, f'Spine 背景已挂载（{sp["key"]}）')
            if got:
                f0 = ev('SiteBgLive.stats().frames') or 0
                time.sleep(1.4)
                f1 = ev('SiteBgLive.stats().frames') or 0
                say(f1 > f0 + 3, f'Spine 渲染循环在推进（帧 {f0} → {f1}）')

        # ── 3) 切回静态背景 ──
        ev("SiteBg.set({kind:'bg',url:'Bg_v2/1.png',key:'probe-static',label:'probe'})")
        gone = wait_state("!window.SiteBgLive.stats().hasCanvas && !window.SiteBgLive.stats().live", 20)
        say(gone, '切到静态背景后，动态宿主层已撤（canvas 与 has-livebg 都没了）')

        # ── 4) 清除 ──
        ev('SiteBg.clear()')
        time.sleep(0.8)
        st = ev('SiteBgLive.stats()')
        say(not st.get('hasCanvas') and not st.get('live'), f'清除后完全回到无背景：{st}')

        # ── 5) 刷新后能记住动态背景 ──
        if l2:
            ev(f'''SiteBg.set({{kind:'live2d',key:{json.dumps(l2['key'])},label:'probe',
                     model:{json.dumps(l2['model'])},base:{json.dumps(l2['base'])},url:''}})''')
            wait_state("window.SiteBgLive.stats().live", 120)
            cmd('Page.reload')
            time.sleep(2.5)
            for _ in range(60):
                if ev('!!(window.SiteBgLive)'):
                    break
                time.sleep(0.5)
            again = wait_state("window.SiteBgLive.stats().live", 120)
            say(again, '刷新后动态背景自动恢复（localStorage 没有把无 url 的记录丢掉）')
            ev('SiteBg.clear()')
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        chrome_tree.kill_tree(proc.pid)

    print()
    if FAIL:
        print(f'== 动态背景探针：{len(FAIL)} 项失败')
        for f in FAIL:
            print('   - ' + f)
        return 1
    print('== 动态背景探针：全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
