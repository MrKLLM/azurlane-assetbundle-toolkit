# -*- coding: utf-8 -*-
"""背景库页（backgrounds.html）验收：图真的解码出像素、三档命名各自显示对、筛选与详情层可用、
   出处能回指到配置表的表/字段/行号，并**深浅两套主题各拍一张图交人看**。

判据形状照 `bgm_page_probe.py`（同一条 harness：自起服务器 + `cdp_slot` 隔离端口/profile）。
为什么第 1 组量的是 `naturalWidth>0` 而不是"卡片数量"：
   2026-10-07 第一版把懒加载挂在 IntersectionObserver 上，而连着的应用内浏览器页
   `innerHeight=0` ⇒ IO 永不判相交 ⇒ **1897 个格子全在、全空**。只量 DOM 存在会报绿。
   ⇒ 探针必须量"图片对象真的解出像素"，并且配一条**反向对照**：故意请求一张不存在的图，
      看 `.miss` 标记会不会出现（标记不出来 = 这组判据是假的）。
⚠️ 服务器自起一份，不复用 8777（那台可能跑着改动前的代码，也可能被另一个会话的探针占着）。
"""
import base64
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
PORT, PROFILE = cdp_slot.slot(ROOT, 'bgp')
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
        b = urllib.request.urlopen(base() + 'bg_meta.json', timeout=8).read()
        return len(b) >= 100000, len(b)
    except Exception as e:
        print(f'  ! bg_meta.json 取不到: {e}')
        return False, 0


def main():
    if not CHROME:
        print('[FAIL] 找不到 Chrome/Edge（设 AL_CHROME）')
        return 2
    ok, n = serve_up()
    if not ok:
        print(f'[FAIL] 自起的服务器取不到 bg_meta.json（{n} 字节）⇒ 先跑 build_bg_meta.py')
        return 2
    META = json.load(open(os.path.join(P.OUT, 'gallery_v2', 'bg_meta.json'), encoding='utf-8'))
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
                             '--remote-allow-origins=*', f'--user-data-dir={PROFILE}',
                             '--no-first-run', '--no-default-browser-check',
                             '--disable-background-timer-throttling',
                             '--use-angle=swiftshader', '--window-size=1440,1000',
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
            cmd('Page.enable')
            args = {'format': 'png'}
            if sel:
                # 网格整高有 39 万像素，不夹到视口就会拍出一张几乎全空的长图
                box = cmd('Runtime.evaluate', {
                    'expression': '(function(){var e=document.querySelector('
                                  + json.dumps(sel) + ');if(!e)return "";'
                                  'var b=e.getBoundingClientRect();'
                                  'var h=Math.min(b.height, innerHeight-b.top);'
                                  'return JSON.stringify({x:b.x,y:b.y,width:b.width,height:h});})()',
                    'returnByValue': True})
                try:
                    r = json.loads(box['result']['value'])
                except (KeyError, ValueError):
                    r = None
                if r and r.get('width'):
                    args['clip'] = {'x': r['x'], 'y': r['y'], 'width': r['width'],
                                    'height': r['height'], 'scale': 2.0}
            b64 = cmd('Page.captureScreenshot', args)['data']
            fp = os.path.join(OUT_SHOTS, f'bg_shot_{tag}.png')
            with open(fp, 'wb') as f:
                f.write(base64.b64decode(b64))
            return fp

        print('== 1) 图是不是真解出像素（不是"格子在、内容空"）==')
        d = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          for(let i=0;i<120 && !document.querySelector('.card');i++) await t(200);
          await t(1500);
          const imgs=[...document.querySelectorAll('.card img')];
          const inView=imgs.filter(i=>{const b=i.getBoundingClientRect();
            return b.top<innerHeight&&b.bottom>0&&b.width>0;});
          return {cards:document.querySelectorAll('.card').length,
                  vh:innerHeight, vw:innerWidth,
                  withSrc:imgs.filter(i=>i.getAttribute('src')).length,
                  decoded:imgs.filter(i=>i.complete&&i.naturalWidth>0).length,
                  inView:inView.length,
                  inViewDecoded:inView.filter(i=>i.complete&&i.naturalWidth>0).length,
                  zeroSize:imgs.filter(i=>i.complete&&i.naturalWidth===0).length,
                  miss:document.querySelectorAll('.card.miss').length,
                  sub:(document.getElementById('sub')||{}).textContent||''};
        })()""")
        if isinstance(d, dict) and '__err' in d:
            say(False, f"页面 JS 异常: {d['__err']}")
        else:
            say(d['vh'] > 400, f"浏览器视口有真实尺寸 {d['vw']}×{d['vh']}（0×0 时懒加载类判据全是假的）")
            say(d['cards'] == len(META['items']),
                f"卡片 {d['cards']} 张 == bg_meta.json 的 {len(META['items'])} 条")
            say(d['inView'] > 4 and d['inViewDecoded'] == d['inView'],
                f"视口内 {d['inView']} 张缩略图全部解出像素（decoded={d['inViewDecoded']}）"
                f"；全页已解码 {d['decoded']}")
            say(d['zeroSize'] == 0 and d['miss'] == 0,
                f"解出但 0 像素的图 {d['zeroSize']} 张 / 标了缺失的 {d['miss']} 张（都要 0）")
            say(d['sub'].count('/') == 1 and str(META['counts']['exact']) in d['sub'],
                f"计数条: {d['sub']}")

        print('== 2) 反向对照：故意请求不存在的缩略图，.miss 必须亮起来 ==')
        nc = ev(r"""(async()=>{
          const c=document.querySelector('.card');
          const im=c.querySelector('img'); const old=im.getAttribute('src');
          im.src='bg_thumbs/__no_such_file__.webp';
          await new Promise(r=>setTimeout(r,900));
          const lit=c.classList.contains('miss');
          im.src=old; c.classList.remove('miss');
          await new Promise(r=>setTimeout(r,700));
          return {lit, recovered:im.complete&&im.naturalWidth>0};
        })()""")
        say(isinstance(nc, dict) and nc.get('lit'), f"坏图会打标记（.miss={nc}）—— 上面那条 ✅ 不是空集给的绿")

        print('== 3) 三档命名各自显示对，且没有把排版串漏出来 ==')
        d3 = ev(r"""(()=>{
          const cards=[...document.querySelectorAll('.card')];
          const by={};
          for(const c of cards){const b=c.querySelector('.badge');(by[b.className.split(' ')[1]] ||= []).push(c);}
          const txt=c=>c.querySelector('.t1').textContent;
          const pick=k=>by[k]?by[k][0]:null;
          return {counts:Object.fromEntries(Object.entries(by).map(([k,v])=>[k,v.length])),
                  exact:txt(pick('exact')), inferred:txt(pick('inferred')), none:txt(pick('none')),
                  hasPipe:[...cards].filter(c=>txt(c).includes('||')).length,
                  emptyTitle:[...cards].filter(c=>!txt(c).trim()).length,
                  badgeText:[...document.querySelectorAll('.badge')].slice(0,3).map(x=>x.textContent)};
        })()""")
        say(isinstance(d3, dict) and d3.get('counts', {}).get('exact') == META['counts']['exact']
            and d3.get('counts', {}).get('none') == META['counts']['none'],
            f"三档卡片数与数据一致: {d3.get('counts') if isinstance(d3, dict) else d3}")
        say(isinstance(d3, dict) and d3.get('hasPipe') == 0,
            f"没有一张卡的标题漏出游戏排版串 `||`（{d3.get('hasPipe')} 张）")
        say(isinstance(d3, dict) and d3.get('emptyTitle') == 0,
            f"没有空标题卡片（{d3.get('emptyTitle')} 张）")
        say(isinstance(d3, dict) and any('\u4e00' <= ch <= '\u9fff' for ch in str(d3.get('exact', ''))),
            f"确定档示例: {d3.get('exact')!r} / 推断档: {d3.get('inferred')!r} / 类目说明档: {d3.get('none')!r}")

        print('== 4) 筛选与搜索 ==')
        # ⚠️ 这页的 chip 是**单选组**（要回到不限就点「全部」那颗），不是"再点同一颗取消"的开关。
        # 上一版照抄音乐库 usage chip 的"再点一次取消"写法，把产品没错的行为打成了红。
        d4 = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          const N=()=>document.querySelectorAll('.card').length;
          const pick=(host,label)=>{const c=[...document.querySelectorAll('#'+host+' .chip')]
              .find(x=>x.textContent.startsWith(label)); c.click(); return c;};
          const n0=N();
          pick('gTier','确定'); await t(500); const n1=N();
          const on1=document.querySelector('#gTier .chip.on').textContent;
          pick('gTier','全部'); await t(500); const n1b=N();
          pick('gDir','场景背景'); await t(600); const n2=N();
          const onlyBg=[...document.querySelectorAll('.card')].every(c=>
              (document.getElementById('sub').textContent||'').length>0);
          pick('gDir','全部'); await t(500); const n2b=N();
          const q=document.getElementById('q'); q.value='起舞于天原之上';
          q.dispatchEvent(new Event('input')); await t(600);
          const n3=N(); const ft=document.querySelector('.card .t1').textContent;
          q.value=''; q.dispatchEvent(new Event('input')); await t(500);
          const n4=N();
          return {n0,n1,n1b,n2,n2b,n3,n4,on1,ft,onlyBg};
        })()""")
        say(isinstance(d4, dict) and d4.get('n1') == META['counts']['exact']
            and str(d4.get('on1', '')).startswith('确定'),
            f"筛「确定」得 {d4.get('n1')} 张，选中态停在「{d4.get('on1')}」")
        say(isinstance(d4, dict) and d4.get('n1b') == d4.get('n0'), f"点「全部」解开档位筛，恢复 {d4.get('n1b')} 张")
        say(isinstance(d4, dict) and d4.get('n2') == META['dirs']['bg']['count'],
            f"筛类目「场景背景」得 {d4.get('n2')} 张")
        say(isinstance(d4, dict) and d4.get('n2b') == d4.get('n0'), f"类目解开后恢复 {d4.get('n2b')} 张")
        say(isinstance(d4, dict) and 0 < d4.get('n3', 0) < d4.get('n0'),
            f"搜中文系列名「起舞于天原之上」得 {d4.get('n3')} 张，首张标题 {d4.get('ft')!r}")
        say(isinstance(d4, dict) and d4.get('n4') == d4.get('n0'), f"清空搜索后恢复 {d4.get('n4')} 张")

        print('== 5) 详情层：原图真解码 + 出处可回指 ==')
        d5 = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          const chips=[...document.querySelectorAll('#gTier .chip')];
          chips.find(c=>c.textContent==='确定').click(); await t(500);
          document.querySelector('.card').click(); await t(2500);
          const ov=document.getElementById('ov').classList.contains('open');
          const im=document.getElementById('ovimg');
          return {ov, name:document.getElementById('ovname').textContent,
            en:document.getElementById('oven').textContent,
            imgSrc:im.getAttribute('src'), decoded:im.complete&&im.naturalWidth>0,
            nat:im.naturalWidth+'x'+im.naturalHeight,
            kv:document.getElementById('ovkv').textContent.slice(0,150),
            ev:(document.getElementById('ovev').textContent||'').slice(0,180),
            warn:document.getElementById('ovwarn').textContent.slice(0,60),
            theme:getComputedStyle(document.documentElement).getPropertyValue('--brand').trim()};
        })()""")
        say(isinstance(d5, dict) and d5.get('ov'), f"点开详情层（{d5.get('name') if isinstance(d5, dict) else d5}）")
        say(isinstance(d5, dict) and d5.get('decoded'),
            f"原图真的解出像素: {d5.get('imgSrc')} → {d5.get('nat')}")
        say(isinstance(d5, dict) and '行' in str(d5.get('ev', ''))
            and ('activity_sp_story' in str(d5.get('ev')) or 'expedition_data_by_map' in str(d5.get('ev'))),
            f"出处可回指到表/字段/行: {str(d5.get('ev'))[:120]!r}")
        say(isinstance(d5, dict) and '确定' in str(d5.get('warn', '')),
            f"口径说明随档位换: {str(d5.get('warn'))[:40]!r}")
        say(isinstance(d5, dict) and bool(d5.get('theme')), f"theme.css token 生效: --brand={d5.get('theme')!r}")

        print('== 6) 主页入口 + served 页面与磁盘正本一致（防"跑的是改动前的代码"）==')
        d6 = ev(r"""(async()=>{
          const r=await fetch('index.html',{cache:'no-store'}); const b=await r.text();
          const s=await (await fetch('backgrounds.html',{cache:'no-store'})).arrayBuffer();
          return {idx:r.status, hasBtn:b.includes("location.href='backgrounds.html'"),
                  servedBytes:s.byteLength};
        })()""")
        disk = os.path.getsize(os.path.join(ROOT, 'gallery_src', 'backgrounds.html'))
        say(isinstance(d6, dict) and d6.get('idx') == 200 and d6.get('hasBtn'),
            f"index.html 里有「背景库」入口按钮")
        # ⚠️ 量字节必须用 `arrayBuffer().byteLength`，不能用 `text().length`：后者是 UTF-16 单元数，
        # 中文一页里有几百个，会把"正本 17309 字节"读成 15569 —— 上一版就是这条自己造出的假红灯。
        served = d6.get('servedBytes') if isinstance(d6, dict) else -1
        say(served == disk, f"served {served} 字节 == 正本 {disk} 字节（不一致就是跑着旧副本）")

        print('== 7) 两套主题截图（交人看，不由脚本判审美）==')
        # 上一版拍的时候详情层还开着，网格图被浮层挡了一半；先关层、回顶，再拍
        ev("""(()=>{document.getElementById('ovclose').click();
              [...document.querySelectorAll('#gTier .chip')][0].click();
              scrollTo(0,0);return 1})()""")
        time.sleep(0.9)
        p1 = shot('light')
        say(os.path.getsize(p1) > 30000, f"昼：{p1}")
        p2 = shot('light_grid', '.grid')
        say(os.path.getsize(p2) > 20000, f"网格特写：{p2}")
        # 推断档与类目说明档各拍一张：这两档是"名字从别处继承/压根没有"，最需要人眼确认没吹牛
        ev("""(()=>{const c=[...document.querySelectorAll('#gTier .chip')].find(x=>x.textContent==='推断');
              c.click();scrollTo(0,0);return 1})()""")
        time.sleep(1.0)
        p2b = shot('inferred')
        say(os.path.getsize(p2b) > 20000, f"推断档网格：{p2b}")
        ev("""(()=>{const c=[...document.querySelectorAll('#gTier .chip')].find(x=>x.textContent==='类目说明');
              c.click();scrollTo(0,0);return 1})()""")
        time.sleep(1.0)
        p2c = shot('none_tier')
        say(os.path.getsize(p2c) > 20000, f"类目说明档网格：{p2c}")
        ev("""(()=>{[...document.querySelectorAll('#gTier .chip')][0].click();
              document.querySelector('.card').click();return 1})()""")
        time.sleep(2.0)
        p3 = shot('sheet')
        say(os.path.getsize(p3) > 20000, f"详情层：{p3}")
        ev("""(()=>{document.getElementById('ovclose').click();
              document.querySelector('#gTheme [data-t=dark]').click();return 1})()""")
        time.sleep(1.0)
        p4 = shot('dark')
        say(os.path.getsize(p4) > 30000, f"夜：{p4}")

        print()
        if FAIL:
            print(f'[FAIL] {len(FAIL)} 条判据未过')
            return 1
        print('[PASS] 背景库页全部判据通过（截图 .diag/bg_shot_*.png，需人眼过一遍）')
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
