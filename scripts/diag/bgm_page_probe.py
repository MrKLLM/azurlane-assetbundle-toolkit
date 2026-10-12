# -*- coding: utf-8 -*-
"""BGM 页验收：数据能载入、配色 token 生效、**点了真的在响**、潮水进度真的在动、
   拖动水面真的找位，并且**深浅两套主题各拍一张图交人看**。

判据全部落在产品可见状态上（DOM 文本 / SVG 路径 / 截图），故意不去够页面闭包里的 `A`——
探针替产品造钩子 = 自证循环（WF-16 硬规则 4）。
⚠️ 无头 Chrome 的自动播放策略会把 `A.play()` 静默拒掉（`element.click()` 不算用户手势），
   所以必须带 `--autoplay-policy=no-user-gesture-required`，否则"没在播"是假红灯。
⚠️ 服务器自己起一份（`make_server`），不复用 8777：那台可能跑着改动前的代码，
   而且另一个会话的探针可能正在用它（端口/profile 走 `cdp_slot`，写死会让两个会话灌进同一个页面）。
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
PORT, PROFILE = cdp_slot.slot(ROOT, 'bgmp')
OUT_SHOTS = os.path.join(P.ROOT, '.diag')
FAIL = []
_httpd = None
_port = None


def say(cond, msg):
    print(('  PASS  ' if cond else '  FAIL  ') + msg)
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
    _httpd = GS.make_server(port=_port, root=P.OUT)
    threading.Thread(target=_httpd.serve_forever, daemon=True).start()
    try:
        b = urllib.request.urlopen(base() + 'bgm.json', timeout=8).read()
        return len(b) >= 20000, len(b)
    except Exception as e:
        print(f'  ! bgm.json 取不到: {e}')
        return False, 0


def main():
    if not CHROME:
        print('[FAIL] 找不到 Chrome/Edge（设 AL_CHROME）')
        return 2
    ok, n = serve_up()
    if not ok:
        print(f'[FAIL] 自起的服务器取不到 bgm.json（{n} 字节）⇒ 先跑 build_bgm_index.py / deploy_gallery.py')
        return 2
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
                             '--remote-allow-origins=*', f'--user-data-dir={PROFILE}',
                             '--no-first-run', '--no-default-browser-check',
                             '--autoplay-policy=no-user-gesture-required',
                             '--disable-background-timer-throttling',
                             '--use-angle=swiftshader', '--window-size=1280,900',
                             base() + 'bgm.html'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(proc)
    ws = None
    try:
        for _ in range(90):
            try:
                tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
                u = [t['webSocketDebuggerUrl'] for t in tabs
                     if 'bgm.html' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
                if u:
                    import websocket
                    ws = websocket.create_connection(u[0], timeout=120, max_size=None)
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if ws is None:
            print('[FAIL] 128 秒内没连上浏览器')
            return 2
        _id = 0

        def cmd(m, p=None):
            nonlocal _id
            _id += 1
            ws.send(json.dumps({'id': _id, 'method': m, 'params': p or {}}))
            ws.settimeout(120)
            while True:
                r = json.loads(ws.recv())
                if r.get('id') == _id:
                    if 'error' in r:
                        raise RuntimeError(json.dumps(r['error'])[:160])
                    return r.get('result', {})

        def ev(e):
            r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
            if r.get('exceptionDetails'):
                return {'__err': str(r['exceptionDetails'].get('text'))[:200]}
            return r.get('result', {}).get('value')

        def shot(tag, sel=None):
            """整页截图；给 `sel` 时只裁那个元素 —— 潮水条在全页图里只有几十像素高，
            不裁根本看不出波形对不对（`scale:2.2` 放大再看）。"""
            cmd('Page.enable')
            args = {'format': 'png'}
            if sel:
                box = cmd('Runtime.evaluate', {
                    'expression': '(function(){var e=document.querySelector('
                                  + json.dumps(sel) + ');if(!e)return "";'
                                  'var b=e.getBoundingClientRect();'
                                  'return JSON.stringify({x:b.x,y:b.y,width:b.width,height:b.height});})()',
                    'returnByValue': True})
                try:
                    r = json.loads(box['result']['value'])
                except (KeyError, ValueError):
                    r = None
                if r and r.get('width'):
                    args['clip'] = {'x': r['x'], 'y': r['y'], 'width': r['width'],
                                    'height': r['height'], 'scale': 2.2}
                else:
                    print(f'  ! 取不到 {sel} 的包围盒，退回整页')
            b64 = cmd('Page.captureScreenshot', args)['data']
            fp = os.path.join(OUT_SHOTS, f'bgm_shot_{tag}.png')
            with open(fp, 'wb') as f:
                import base64 as _b
                f.write(_b.b64decode(b64))
            return fp

        print('== 数据与样式 ==')
        d = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          for(let i=0;i<80 && !document.querySelector('.row');i++) await t(250);
          return {rows:document.querySelectorAll('.row').length,
                  sub:(document.getElementById('sub')||{}).textContent||'',
                  brand:getComputedStyle(document.documentElement).getPropertyValue('--brand').trim(),
                  ease:getComputedStyle(document.documentElement).getPropertyValue('--ease-ios').trim(),
                  bodyBg:getComputedStyle(document.body).backgroundImage,
                  glass:getComputedStyle(document.querySelector('.bar')||document.body)
                          .backdropFilter||getComputedStyle(document.querySelector('.row')||document.body).backdropFilter,
                  tagRows:document.querySelectorAll('.row .tag').length,
                  chips:document.querySelectorAll('.chip').length,
                  err:(document.getElementById('list')||{}).textContent||''};
        })()""")
        if isinstance(d, dict) and '__err' in d:
            say(False, f"页面 JS 异常: {d['__err']}")
        else:
            say(d['rows'] >= 500, f"列表渲染 {d['rows']} 行（期望 ≥500）")
            say('小时' in d['sub'] and '有出处' in d['sub'], f"计数条文案: {d['sub'][:72]}")
            say(bool(d['brand']) and bool(d['ease']),
                f"theme.css 生效：--brand={d['brand']!r} --ease-ios={d['ease'][:20]!r}")
            say('gradient' in d['bodyBg'], f"body 渐变背景由 token 渲染: {d['bodyBg'][:58]}")
            say(d['tagRows'] >= 200, f"带归属徽章的行 {d['tagRows']} 个（出处/专辑/舰名）")
            say(d['chips'] >= 15, f"筛选 chip {d['chips']} 个（用途/出处/专辑三组）")

        print('== 播放与潮水 ==')
        d2 = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          document.querySelector('.play').click();
          const barOn=document.getElementById('bar').classList.contains('on');
          const playing=document.querySelector('.row.playing')!==null;
          const cur=document.getElementById('cur').textContent;
          /* 轮询到"真的开始出声计时"再量 —— 固定 await 600ms 对首曲（要现取现解码 1.8MB）
             不够，就会把"还在缓冲"读成"没在播"。这是 WF-16 踩坑第 1 条的原样复现。 */
          for(let i=0;i<40 && document.getElementById('t0').textContent==='0:00';i++) await t(250);
          const w0=document.getElementById('w1').getAttribute('d')||'';
          const t0a=document.getElementById('t0').textContent;
          for(let i=0;i<40 && document.getElementById('t0').textContent===t0a;i++) await t(250);
          const w1=document.getElementById('w1').getAttribute('d')||'';
          const t0b=document.getElementById('t0').textContent;
          const bead=document.getElementById('bead').getAttribute('cx');
          const prog=w1!==w0;
          // 「退平」要量**振幅**（波峰-波谷的高度差），不是量路径是否一模一样：
          // 静止时水面仍会极慢漂移（设计如此），拿字符串相等当判据会把它误报成"没退平"。
          /* 先拖到 50% 再量振幅：刚播 1 秒时水面只占进度条 0.9%，
             那一段正弦本来就几乎不弯（上一版在这里量出 0.35px 并误判成"没退平"）。 */
          const el=document.getElementById('tide'),r=el.getBoundingClientRect();
          const mk=(type)=>new PointerEvent(type,{bubbles:true,
            clientX:r.left+r.width*0.5,clientY:r.top+r.height/2,pointerId:1,isPrimary:true});
          el.dispatchEvent(mk('pointerdown'));el.dispatchEvent(mk('pointermove'));
          el.dispatchEvent(mk('pointerup'));
          const s0=document.getElementById('t0').textContent;
          for(let i=0;i<24 && document.getElementById('t0').textContent===s0;i++) await t(250);
          await t(300);
          /* 只能量 #crest（纯水面线）：#w1 是填充路径，末尾 `L x 46Z` 把水底算进 y 范围，
             量它恒得 ~26px，看不出波有没有退平。 */
          const ampOf=s=>{const ys=[...(s.match(/[ML]([-\d.]+) ([-\d.]+)/g)||[])]
            .map(x=>+x.split(' ')[1]).filter(y=>y<40);
            return ys.length?+(Math.max(...ys)-Math.min(...ys)).toFixed(2):0};
          const ampPlay=ampOf(document.getElementById('crest').getAttribute('d')||'');
          const seeked=document.getElementById('t0').textContent;
          const rip=document.getElementById('rip').classList.contains('go');
          const durTxt=document.getElementById('t1').textContent;
          document.getElementById('pp').click(); await t(2200);
          const ampPause=ampOf(document.getElementById('crest').getAttribute('d')||'');
          return {barOn,playing,cur,t0a,t0b,bead,prog,ampPlay,ampPause,seeked,durTxt,rip};
        })()""")
        if isinstance(d2, dict) and '__err' in d2:
            say(False, f"播放 JS 异常: {d2['__err']}")
        else:
            say(d2['barOn'] and d2['playing'], f"播放器浮起且当前行高亮（{d2['cur'][:24]}）")
            say(d2['t0a'] != d2['t0b'], f"进度在走：{d2['t0a']} → {d2['t0b']}")
            say(d2['prog'], "潮水路径随时间变化（波在动，不是静态图）")
            say(float(d2['bead']) > 0, f"水珠沿水面右移 cx={d2['bead']}")


        print('== 拖动水面找位（只有支持 Range 的服务器才可能过）==')
        say(isinstance(d2, dict) and 'Infinity' not in str(d2.get('durTxt', '')),
            f"总时长用的是已知真值（不是 Infinity:NaN）: {d2.get('durTxt') if isinstance(d2,dict) else d2}")
        if isinstance(d2, dict) and not d2.get('__err'):
            hh,mm=d2['durTxt'].split(':'); th=d2['seeked'].split(':')
            want=int(hh)*60+int(mm); got=int(th[0])*60+int(th[1])
            say(abs(got-want/2)<=4, f"拖到 50% 后落在 {d2['seeked']}（目标 ≈ {want//2} 秒）")
            say(d2['rip'], "松手甩出涟漪（.rip.go 已触发）")
            say(d2['ampPlay']>5 and d2['ampPause']<d2['ampPlay']*0.55,
                f"潮水随播放状态涨落：播放中振幅 {d2['ampPlay']}px → 暂停后 {d2['ampPause']}px")

        print('== 筛选与搜索 ==')
        d4 = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms)); const n0=document.querySelectorAll('.row').length;
          const q=document.getElementById('q'); q.value='灾厄'; q.dispatchEvent(new Event('input')); await t(300);
          const n1=document.querySelectorAll('.row').length;
          q.value=''; q.dispatchEvent(new Event('input')); await t(300);
          const cu=[...document.querySelectorAll('.chip[data-k=usage]')][0]; cu.click(); await t(300);
          const n2=document.querySelectorAll('.row').length; const on1=cu.classList.contains('on');
          cu.click(); await t(300); const n3=document.querySelectorAll('.row').length;
          const cs=[...document.querySelectorAll('.chip[data-k=scene]')][0]; cs.click(); await t(300);
          const n4=document.querySelectorAll('.row').length; cs.click(); await t(300);
          return {n0,n1,n2,n3,n4,on1,first:cu.dataset.v,scene:cs.dataset.v};
        })()""")
        if isinstance(d4, dict) and '__err' not in d4:
            say(d4['n1'] >= 1 and d4['n1'] < d4['n0'], f"搜「灾厄」得 {d4['n1']} 行")
            say(0 < d4['n2'] < d4['n0'] and d4['on1'], f"按用途「{d4['first']}」筛出 {d4['n2']} 行且 chip 高亮")
            say(d4['n3'] == d4['n0'], f"再点一次取消筛选，恢复 {d4['n3']} 行")
            say(0 < d4['n4'] < d4['n0'], f"按出处「{d4['scene']}」筛出 {d4['n4']} 行")
        else:
            say(False, f"筛选 JS 异常: {d4}")

        print('== 两套主题截图（交人看，不由脚本判审美）==')
        say(os.path.getsize(shot('light')) > 20000, f"昼：{shot('light')}")
        # 潮水特写：拖到 42% 再裁 #bar，2.2 倍放大 —— 全页图里那条只有 46px 高，看不出波
        ev("""(()=>{const el=document.getElementById('tide'),r=el.getBoundingClientRect();
            const mk=(ty)=>new PointerEvent(ty,{bubbles:true,clientX:r.left+r.width*0.42,
              clientY:r.top+r.height/2,pointerId:7,isPrimary:true});
            el.dispatchEvent(mk('pointerdown'));el.dispatchEvent(mk('pointermove'));
            el.dispatchEvent(mk('pointerup'));return 1})()""")
        time.sleep(1.0)
        say(os.path.getsize(shot('bar', '#bar')) > 8000, f"潮水特写：{shot('bar', '#bar')}")
        # 标签行特写：整页图里那几个小 chip 糊成一片，"是不是重复了"根本判不了
        say(os.path.getsize(shot('row', '.row')) > 8000, f"首行特写：{shot('row', '.row')}")
        # 上一组筛选可能把正在播的曲子筛出列表（`.row.playing` 就不存在了），
        # 所以量材质前先就地重播当前视图的第一行——也让夜主题截图里能看到播放行的玻璃。
        ev("""(()=>{document.querySelector('.row .play').click();return 1})()""")
        time.sleep(0.8)
        ev("""(()=>{document.querySelector('#gTheme [data-t=dark]').click();return 1})()""")
        time.sleep(1.2)
        say(os.path.getsize(shot('dark')) > 20000, f"夜：{shot('dark')}")
        d5 = ev("""(()=>{const el=document.querySelector('.row.playing');
            const p=el?getComputedStyle(el).backdropFilter:'(无播放行)';
            const q=getComputedStyle(document.querySelector('input.q')).backdropFilter;
            const n=[...document.querySelectorAll('.row:not(.playing)')].slice(0,40)
              .every(r=>(getComputedStyle(r).backdropFilter||'none')==='none');
            return {play:p,search:q.slice(0,36),plainZero:n}})()""")
        # 2026-10-12 改判据：普通行**故意不挂** backdrop-filter（§134/§136，见 bgm.html .row 注释），
        # 旧判据"行卡有 blur"与该决定直接矛盾，是探针过期而非页面缺陷。
        # 新口径：玻璃材质只认三处结构件——播放器、搜索框、正在播放的行；普通行必须零盒。
        say(isinstance(d5, dict) and 'url(' in str(d5.get('play', ''))
            and 'url(' in str(d5.get('search', '')) and d5.get('plainZero'),
            f"夜主题：播放行+搜索框挂折射、普通行零 backdrop-filter: {d5}")

        print('== 主页入口 ==')
        d6 = ev("""(async()=>{ const r=await fetch('index.html'); const b=await r.text();
                    return {status:r.status, has:b.includes(\"location.href='bgm.html'\")}; })()""")
        say(isinstance(d6, dict) and d6.get('status') == 200 and d6.get('has'),
            f"index.html 可取且含「音乐库」入口按钮")
        print()
        if FAIL:
            print(f'[FAIL] {len(FAIL)} 条判据未过')
            return 1
        print('[PASS] BGM 页全部判据通过（截图在 .diag/bgm_shot_*.png，需人眼过一遍）')
        return 0
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        chrome_tree.kill_tree(proc.pid)
        if _httpd:
            _httpd.shutdown()
            _httpd.server_close()


if __name__ == '__main__':
    sys.exit(main())
