# -*- coding: utf-8 -*-
"""首页网格分批渲染验收：首屏不再一次建完全部卡片，滚动能拿全，筛选/分档能重置。

为什么量这些：
  · "DOM 里有 1,022 张卡"不等于"首屏渲染快"——首屏遮罩的根因是 `renderGrid()` 同步建卡，
    所以第一条判据是**首屏 DOM 上限**，不是总数；
  · 只量首屏上限又会假绿（分页把内容弄丢也没人发现）⇒ 必须滚到底再核对总数 == 索引三档之和；
  · 搜索/筛选/分档走的是同一条 `renderGrid()`，重置漏掉就会出现"筛完还停在第二页"；
  · 缩略图要真的解出像素（背景库 §119 的假绿：格子都在、全是空的）。

用法:
  py -3 scripts/diag/index_paging_probe.py            # 回归（断言）
  py -3 scripts/diag/index_paging_probe.py --baseline # 只打印现状指标，不判红
退出码: 0 全绿；1 有判红；2 环境/启动失败。
"""
import argparse
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
PORT, PROFILE = cdp_slot.slot(ROOT, 'idxpg')
SHOT_DIR = os.path.join(P.ROOT, '.diag', 'index_paging')
FAIL = []
_httpd = None
_port = None

# 首屏上限：页面每批 120（窄屏 60），留一点余量给"分区头 + 同批"的边界。
MAX_FIRST = 130
MAX_FIRST_NARROW = 70


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
        n = len(urllib.request.urlopen(base() + 'index.js', timeout=8).read())
        return n > 100000, n
    except Exception as e:
        print(f'  ! index.js 取不到: {e}')
        return False, 0


INIT = r"""
window.__probe={errors:[],long:[],nav:performance.now()};
try{
  new PerformanceObserver(function(l){
    l.getEntries().forEach(function(e){
      __probe.long.push([Math.round(e.startTime),Math.round(e.duration),
        (e.attribution||[]).map(function(a){return {type:a.containerType,src:a.containerSrc,
          name:a.name,dur:Math.round(a.duration||0)};})]);
    });
  }).observe({entryTypes:['longtask'],buffered:true});
}catch(e){}
try{
  new MutationObserver(function(){
    var el=document.getElementById('bootveil');
    if(el && el.classList.contains('off') && !__probe.bootOff) __probe.bootOff=performance.now();
  }).observe(document,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
}catch(e){}
addEventListener('error',function(e){
  __probe.errors.push((e.message||String(e))+' @ '+(e.filename||'?')+':'+(e.lineno||0));
});
addEventListener('unhandledrejection',function(e){ __probe.errors.push('rejection:'+String(e.reason)); });
(function(){var oe=console.error;console.error=function(){
  __probe.errors.push('console.error:'+Array.prototype.join.call(arguments,' ').slice(0,200));
  return oe.apply(this,arguments);};})();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', action='store_true', help='只打印指标，不判红')
    ap.add_argument('--profile', action='store_true', help='对首屏做 3s CPU 采样并打印自耗时前 15')
    a = ap.parse_args()
    if not CHROME:
        print('[FAIL] 找不到 Chrome/Edge（设 AL_CHROME）')
        return 2
    ok, n = serve_up()
    if not ok:
        print(f'[FAIL] 自起的服务器取不到 index.js（{n} 字节）⇒ 先跑 build_gallery_index.py')
        return 2
    os.makedirs(SHOT_DIR, exist_ok=True)

    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
                             '--remote-allow-origins=*', f'--user-data-dir={PROFILE}',
                             '--no-first-run', '--no-default-browser-check',
                             '--disable-background-timer-throttling',
                             '--use-angle=swiftshader', '--window-size=1440,900',
                             'about:blank'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(proc)
    ws = None
    try:
        for _ in range(90):
            try:
                tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
                # ⚠️ 不能取第一个带 ws 的 target：本机 Chrome 装了扩展时，
                # `/json` 第一项是 background_page（扩展页），连上去量到的是空白页。
                u = [t['webSocketDebuggerUrl'] for t in tabs
                     if t.get('type') == 'page' and t.get('webSocketDebuggerUrl')]
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
        events = []

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
                events.append(r)

        def ev(e):
            r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True,
                                         'awaitPromise': True})
            if r.get('exceptionDetails'):
                return {'__err': str(r['exceptionDetails'].get('text'))[:300]}
            return r.get('result', {}).get('value')

        def wait_ready(timeout=20):
            return ev(r"""(async()=>{const t=ms=>new Promise(r=>setTimeout(r,ms));
              for(let i=0;i<%d;i++){
                if(window.GALLERY && document.getElementById('count') &&
                   document.getElementById('count').textContent.indexOf('共')>=0) {
                  await t(900); return 1;
                }
                await t(100);
              }
              return 0})()""" % (timeout * 10))

        def shot(tag):
            cmd('Page.enable')
            b64 = cmd('Page.captureScreenshot', {'format': 'png'})['data']
            fp = os.path.join(SHOT_DIR, f'index_{tag}.png')
            with open(fp, 'wb') as f:
                f.write(base64.b64decode(b64))
            return fp

        def metrics():
            return ev(r"""(()=>{
              const main=document.getElementById('main');
              const cards=[...document.querySelectorAll('#main .card')];
              const imgs=cards.map(c=>c.querySelector('img')).filter(Boolean);
              return {cards:cards.length, nodes:document.querySelectorAll('*').length,
                count:(document.getElementById('count')||{}).textContent||'',
                more:(document.querySelector('#main .more')||{}).textContent||'',
                scrollTop:main?main.scrollTop:0,
                scrollHeight:main?main.scrollHeight:0,
                hiddenMask:!document.getElementById('bootveil'),
                bootOff:__probe.bootOff||0, nav:__probe.nav||0,
                long:__probe.long||[], errors:__probe.errors||[],
                imgs:imgs.length, decoded:imgs.filter(i=>i.naturalWidth>0).length,
                width:innerWidth, scrollWidth:document.documentElement.scrollWidth};
            })()""")

        cmd('Page.enable')
        cmd('Page.addScriptToEvaluateOnNewDocument', {'source': INIT})
        if a.profile:
            cmd('Profiler.enable')
            cmd('Profiler.setSamplingInterval', {'interval': 1000})
            cmd('Profiler.start')
        cmd('Page.navigate', {'url': base() + 'index.html'})
        time.sleep(0.4)
        ready = wait_ready()
        if not ready:
            print('[FAIL] 页面未就绪（GALLERY / #count 没出来）')
            print(ev('document.body && document.body.innerText.slice(0,300)'))
            return 2
        if a.profile:
            time.sleep(1.2)
            prof = cmd('Profiler.stop').get('profile') or {}
            nodes = {n['id']: n for n in prof.get('nodes') or []}
            per = {}
            samples = prof.get('samples') or []
            deltas = prof.get('timeDeltas') or []
            for i, sid in enumerate(samples):
                dt = deltas[i] / 1000.0 if i < len(deltas) else 0
                cf = (nodes.get(sid) or {}).get('callFrame') or {}
                key = (cf.get('functionName') or '(anonymous)', cf.get('url', ''),
                       cf.get('lineNumber', -1))
                per[key] = per.get(key, 0) + dt
            print('== CPU 采样（首屏，自耗时前 15） ==')
            for key, ms in sorted(per.items(), key=lambda x: -x[1])[:15]:
                print('  %8.1fms  %s  %s:%s' % (ms, key[0], key[1], key[2]))

        m0 = metrics()
        total = ev("window.GALLERY.counts.ships+window.GALLERY.counts.silhouettes"
                   "+window.GALLERY.counts.variants")
        other = ev("(()=>{const b=document.querySelector('#fCat button[data-c=\"other\"]');"
                   "return b?parseInt(b.textContent.replace(/\\D+/g,''),10):-1})()")
        # vendor/spine/spine-all.js 的可选 three 集成在没加载 THREE 时会在顶层抛错。
        # 这条在本次改动前就存在（基线同样报），不属于首页渲染链路；按文件名精确排除，
        # 其余任何页面错误仍然判红。
        def real_errors(errs):
            return [e for e in (errs or [])
                    if not ('vendor/spine/spine-all.js' in e and 'THREE is not defined' in e)]
        errs = real_errors(m0.get('errors'))
        print('== 首屏 ==')
        print('  cards=%s nodes=%s decoded=%s/%s bootOff=%.0fms count=%r'
              % (m0.get('cards'), m0.get('nodes'), m0.get('decoded'), m0.get('imgs'),
                 m0.get('bootOff', 0), m0.get('count')))
        longs = m0.get('long') or []
        max_long = max([x[1] for x in longs] or [0])
        boot_at = m0.get('bootOff', 0)
        pre = [x for x in longs if boot_at and x[0] <= boot_at]
        post = [x for x in longs if not boot_at or x[0] > boot_at]
        max_pre = max([x[1] for x in pre] or [0])
        max_post = max([x[1] for x in post] or [0])
        print('  longtasks=%d 总阻塞=%dms 最大=%dms（遮罩收起前 %dms / 之后 %dms）'
              % (len(longs), sum(x[1] for x in longs), max_long, max_pre, max_post))
        for x in sorted(longs, key=lambda y: -y[1])[:3]:
            print('    %dms @%dms %s' % (x[1], x[0], x[2] if len(x) > 2 else ''))
        print('  errors=%s' % (real_errors(m0.get('errors')) or []))
        shot('desktop')
        if a.baseline:
            print('\n[baseline] 只打印指标，不判红。')
            return 0

        say(total >= 1000, f'索引量级正常（三档之和 {total}）')
        say(isinstance(m0.get('cards'), int) and m0['cards'] <= MAX_FIRST,
            f'首屏 DOM 卡数 ≤ {MAX_FIRST}（实际 {m0.get("cards")}）')
        say(m0.get('nodes', 99999) < 6000,
            f'首屏 DOM 节点 < 6,000（实际 {m0.get("nodes")}；改动前 15,399）')
        say(m0.get('hiddenMask') or boot_at > 0,
            f'首屏遮罩已收起（hidden={m0.get("hiddenMask")}, bootOff={boot_at:.0f}ms）')
        say(0 < boot_at < 2000, f'遮罩在 2s 内收起（实际 {boot_at:.0f}ms）')
        # 只判遮罩收起**之前**的长任务：那一段才是首屏建卡/排序直接占住的时间。
        # 收起之后那条 1s+ 的阻塞在 headless SwiftShader 下是 water_bg 的 WebGL 初始化
        # （CPU 采样 1,522ms 落在 bgInit），真机 GPU 上量级不同，不能拿来当本页的成绩。
        say(max_pre < 600, f'遮罩收起前最长任务 < 600ms（实际 {max_pre}ms；总阻塞含水面初始化）')
        print('  · 参考：遮罩收起后最长任务 %dms（water_bg/WebGL，本次不改）' % max_post)
        say(m0.get('decoded', 0) > 0,
            f'首屏缩略图真的解出像素（{m0.get("decoded")}/{m0.get("imgs")}）')
        say(not errs, f'首屏 0 页面报错（{errs}）')

        print('== 滚到底：分页必须能拿全 ==')
        last, stable = -1, 0
        for i in range(40):
            ev("(document.getElementById('main').scrollTop="
               "document.getElementById('main').scrollHeight);1")
            time.sleep(0.22)
            n = ev("document.querySelectorAll('#main .card').length")
            if n == last:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
                last = n
        m1 = metrics()
        say(m1.get('cards') == total,
            f'滚到底后 DOM 卡数 == {total}（实际 {m1.get("cards")}）')
        say('全部' in (m1.get('more') or '') or '已显示' in (m1.get('more') or ''),
            f'底部状态文案可见：{m1.get("more")!r}')

        print('== 分档重置 ==')
        ev("document.querySelector('#fCat button[data-c=\"other\"]').click();1")
        time.sleep(0.8)
        mo = metrics()
        say(mo.get('cards') == other,
            f'「其他」档全渲染（{mo.get("cards")} / 索引 {other}；< 一页时不触发分页）')
        say(mo.get('scrollTop') == 0, f'切档后回到顶部（scrollTop={mo.get("scrollTop")}）')
        more_hidden = ev("(()=>{const m=document.querySelector('#main .more');"
                         "if(!m)return true;const b=m.querySelector('button');"
                         "return getComputedStyle(b).display==='none'||b.hidden;})()")
        say(bool(more_hidden), '「其他」档不足一页时「加载更多」按钮隐藏')
        ev("(()=>{const m=document.querySelector('#main .more');"
           "if(m) m.scrollIntoView({block:'center'});return 1})()")
        time.sleep(0.4)
        shot('more')

        print('== 搜索重置 ==')
        ev("document.querySelector('#fCat button[data-c=\"\"]').click();1")
        time.sleep(0.5)
        ev("(()=>{const s=document.getElementById('search');s.value='埃塞克斯';"
           "s.dispatchEvent(new Event('input',{bubbles:true}));return 1})()")
        time.sleep(0.8)
        ms = metrics()
        names = ev("JSON.stringify([...document.querySelectorAll('#main .card .nm')]"
                   ".map(x=>x.textContent.trim()))")
        names = json.loads(names or '[]')
        say(bool(names) and all('埃塞克斯' in x for x in names),
            f'搜索结果全部命中关键词（{len(names)} 张：{names[:5]}）')
        say(ms.get('scrollTop') == 0, f'搜索后回到顶部（scrollTop={ms.get("scrollTop")}）')
        ev("(()=>{const s=document.getElementById('search');s.value='';"
           "s.dispatchEvent(new Event('input',{bubbles:true}));return 1})()")
        time.sleep(0.8)

        print('== 追加批次：兜底按钮 + 事件委托 ==')
        m2 = metrics()
        say(m2.get('cards') == 120, f'清空搜索后回到第一页 120 张（实际 {m2.get("cards")}）')
        ev("document.querySelector('#main .more button').click();1")
        time.sleep(0.8)
        m3 = metrics()
        say(m3.get('cards') == m2.get('cards', 0) + 120,
            f'「加载更多」按钮追加一批（{m2.get("cards")} → {m3.get("cards")}）')
        ev("(()=>{const cs=[...document.querySelectorAll('#main .card')];"
           "cs[cs.length-1].scrollIntoView({block:'center'});return 1})()")
        time.sleep(0.5)
        ev("(()=>{const cs=[...document.querySelectorAll('#main .card')];"
           "cs[cs.length-1].click();return 1})()")
        time.sleep(1.0)
        op = ev("(()=>{const m=document.getElementById('mask');"
                "return {on:m.classList.contains('on'),"
                "name:(document.getElementById('mName')||{}).textContent.trim()};})()")
        say(bool(isinstance(op, dict) and op.get('on') and op.get('name')),
            '追加出来的卡片点得开（mask=%s, name=%r）'
            % ((op or {}).get('on'), (op or {}).get('name')))
        ev("document.getElementById('close').click();1")
        time.sleep(0.5)

        print('== 窄屏 390×844 ==')
        cmd('Emulation.setDeviceMetricsOverride',
            {'width': 390, 'height': 844, 'deviceScaleFactor': 2, 'mobile': True})
        cmd('Page.navigate', {'url': base() + 'index.html'})
        time.sleep(0.4)
        ready = wait_ready()
        mn = metrics() if ready else {}
        print('  cards=%s scrollWidth=%s viewport=%s' %
              (mn.get('cards'), mn.get('scrollWidth'), mn.get('width')))
        shot('mobile')
        say(ready == 1 and mn.get('cards', 999) <= MAX_FIRST_NARROW,
            f'窄屏首屏 DOM 卡数 ≤ {MAX_FIRST_NARROW}（实际 {mn.get("cards")}）')
        say(int(mn.get('scrollWidth', 9999)) <= int(mn.get('width', 0)) + 1,
            f'窄屏无横向溢出（scrollWidth={mn.get("scrollWidth")} viewport={mn.get("width")}）')
        say(not real_errors(mn.get('errors')),
            f'窄屏 0 页面报错（{real_errors(mn.get("errors"))}）')

        print('\n截图: %s' % SHOT_DIR)
        print('结果: %s' % ('全绿' if not FAIL else f'{len(FAIL)} 条判红'))
        return 0 if not FAIL else 1
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == '__main__':
    sys.exit(main())
