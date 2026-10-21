# -*- coding: utf-8 -*-
"""动态网站背景的 UI 验收 + 内存/主线程成本。

为什么不能只测 `SiteBg.set()`：那会绕过首页弹窗自己的 `bgTarget()` 与按钮重绘逻辑。
2026-10-20 回滚后 `site_bg_live.js` 还在、入口按钮却没了，直接调 SiteBg 的探针会全绿。
本探针只走用户路径：卡片 → 皮肤 →「设为网站背景」→ 刷新恢复。

判据：
  ① 弹窗主按钮默认选中当前皮肤的动态版本（Live2D 优先，其次 Spine），按钮里带类型角标；
  ② 点下去后 `SiteBg.get().kind` 正确、`#sitelive` 挂载、渲染帧在推进；
  ③ 旁边「静态图」是显式次级动作，点了能退回静态；
  ④ 同一个按钮再点一次 = 取消；换另一个动态皮肤 = 切换，不是取消（判等必须按 kind+key）；
  ⑤ 刷新后动态背景恢复；
  ⑥ 记录 Chrome 整棵进程树的 WorkingSet（只报事实，不设成败阈值）与主线程 TaskDuration。

用法：
  py -3 scripts/diag/livebg_ui_probe.py
  py -3 scripts/diag/livebg_ui_probe.py --headed   # 真窗口，便于看画面
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import websocket                      # noqa: E402
import chrome_tree                    # noqa: E402
import cdp_slot                       # noqa: E402
import paths as P                     # noqa: E402
from peak_mem import snapshot_ppid, descendants, ws_gb   # noqa: E402

CHROME = P.tool('AL_CHROME', 'chrome',
                r'C:/Program Files/Google/Chrome/Application/chrome.exe',
                r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
BASE = 'http://127.0.0.1:8777/gallery_v2/index.html'
OUT = os.path.join(ROOT, '.diag', 'livebg_ui_probe.json')
FAIL = []


def say(ok, msg):
    print(('  PASS  ' if ok else '  FAIL  ') + msg, flush=True)
    if not ok:
        FAIL.append(msg)


def tree_ws_gb(pid):
    return sum(ws_gb(p) for p in descendants(pid, snapshot_ppid()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--headed', action='store_true', help='用真实窗口（默认也走 GPU，只是摆到屏幕外）')
    a = ap.parse_args()
    if not CHROME:
        print('[FAIL] 找不到 Chrome/Edge（设 AL_CHROME）')
        return 2
    try:
        urllib.request.urlopen(BASE, timeout=5).read(1024)
    except Exception as e:
        print(f'[FAIL] 8777 上没有画廊服务：{e}')
        return 2

    port, profile = cdp_slot.slot(ROOT, 'livebgui')
    args = [CHROME, f'--remote-debugging-port={port}', '--remote-allow-origins=*',
            f'--user-data-dir={profile}', '--no-first-run', '--no-default-browser-check',
            '--window-size=1600,1000', '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding', '--disable-features=CalculateNativeWinOcclusion',
            BASE]
    if not a.headed:
        args.insert(3, '--window-position=-2400,0')
    proc = chrome_tree.install(subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                                stderr=subprocess.DEVNULL))
    ws = None
    result = {'base': None, 'live2d': None, 'static': None, 'spine': None, 'reload': None}
    try:
        for _ in range(90):
            try:
                tabs = json.load(urllib.request.urlopen(
                    f'http://127.0.0.1:{port}/json', timeout=1))
                u = [t['webSocketDebuggerUrl'] for t in tabs
                     if t.get('type') == 'page' and t.get('webSocketDebuggerUrl')]
                if u:
                    ws = websocket.create_connection(u[0], timeout=120, max_size=None)
                    break
            except Exception:
                pass
            time.sleep(0.4)
        if ws is None:
            print('[FAIL] 连不上浏览器')
            return 2

        _id = [0]

        def cmd(method, params=None):
            _id[0] += 1
            ws.send(json.dumps({'id': _id[0], 'method': method, 'params': params or {}}))
            ws.settimeout(150)
            while True:
                r = json.loads(ws.recv())
                if r.get('id') == _id[0]:
                    if 'error' in r:
                        raise RuntimeError(json.dumps(r['error'])[:300])
                    return r.get('result', {})

        def ev(expr):
            r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True,
                                         'awaitPromise': True, 'userGesture': True})
            if r.get('exceptionDetails'):
                return {'__err': str(r['exceptionDetails'].get('text'))[:300]}
            return r.get('result', {}).get('value')

        def wait(expr, timeout=90):
            t0 = time.time()
            while time.time() - t0 < timeout:
                if ev(expr):
                    return True
                time.sleep(0.4)
            return False

        cmd('Page.enable')
        cmd('Performance.enable')
        say(wait('document.querySelectorAll("#main .card").length>0', 60),
            '首页卡片已渲染')
        print('  [env] visibilityState=%s hidden=%s' %
              (ev('document.visibilityState'), ev('document.hidden')), flush=True)

        def metrics():
            m = {x['name']: x['value'] for x in cmd('Performance.getMetrics').get('metrics', [])}
            return {'heapMB': round(m.get('JSHeapUsedSize', 0) / 1048576, 1),
                    'taskSec': round(m.get('TaskDuration', 0), 3)}

        def sample(tag, settle=3.0):
            time.sleep(settle)
            m0 = metrics()
            time.sleep(2.0)
            m1 = metrics()
            result[tag] = {'wsGB': round(tree_ws_gb(proc.pid), 2),
                           'heapMB': m1['heapMB'],
                           'taskSecPer2s': round(m1['taskSec'] - m0['taskSec'], 3)}
            print(f'  [{tag}] Chrome树WS={result[tag]["wsGB"]:.2f} GB · '
                  f'JS堆={m1["heapMB"]:.1f} MB · 2s主线程={result[tag]["taskSecPer2s"]:.3f}s',
                  flush=True)

        sample('base')

        def open_ship(name, key):
            """真路径：点卡片打开弹窗，再点皮肤卡。返回是否点到了。"""
            ok = ev('''(function(){
              var nm=%s, card=[...document.querySelectorAll('#main .card')]
                .find(c=>c.querySelector('.nm')&&c.querySelector('.nm').textContent.trim()===nm);
              if(!card) return false; card.click(); return true;})()''' % json.dumps(name))
            if not ok:
                return False
            time.sleep(0.45)
            ok2 = ev('''(function(){
              var el=document.querySelector('#mSkins .skin[data-k="%s"]');
              if(!el) return false; el.click(); return true;})()''' % key)
            time.sleep(0.35)
            return bool(ok2)

        def bg_text(which='mSetBg'):
            return ev('''(function(){var b=document.getElementById('%s');
              return b?b.textContent.trim():'(缺按钮)';})()''' % which)

        def click_bg():
            return ev('''(function(){var b=document.getElementById('mSetBg');
              if(!b) return 'no-button'; b.click(); return 'clicked';})()''')

        def close_modal():
            ev('''(function(){var b=document.getElementById('close');
              if(b) b.click();})()''')
            time.sleep(0.4)

        def host_live(expect_kind):
            return wait('''(function(){var v=window.SiteBg&&SiteBg.get();
              return !!(v&&v.kind==='%s'&&window.SiteBgLive&&SiteBgLive.stats().live
                &&document.querySelector('#sitelive canvas'));})()''' % expect_kind, 120)

        def frames_moving():
            f0 = ev('window.SiteBgLive.stats().frames') or 0
            time.sleep(1.5)
            f1 = ev('window.SiteBgLive.stats().frames') or 0
            return f1 > f0 + 3, f0, f1

        # ── Live2D：真入口 ──
        ok = open_ship('宁海', 'ninghai_4')
        say(ok, '点卡片 + 点皮肤卡打开了宁海/ninghai_4')
        tag = ev('''(function(){var b=document.querySelector('#mSetBg .bgtag');
          return b?b.textContent.trim():'';})()''')
        say(tag == 'Live2D', f'主按钮角标 = {tag!r}（应为 Live2D）')
        click_bg()
        time.sleep(0.25)
        txt = bg_text()
        say(isinstance(txt, str) and '已设为背景' in txt, f'点击后按钮文案 = {txt!r}')
        say(host_live('live2d'), 'Live2D 背景已挂载且 SiteBgLive 认为在播')
        moving, f0, f1 = frames_moving()
        say(moving, f'Live2D 渲染帧推进（{f0} → {f1}）')
        say(ev('''(function(){var h=document.getElementById('sitelive');
          return !!h&&getComputedStyle(h).pointerEvents==='none';})()''') is True,
            '背景层 pointer-events=none')
        say(ev('''(function(){var h=document.getElementById('sitelive');
          var e=document.elementFromPoint(Math.round(innerWidth/2),Math.round(innerHeight/2));
          return !!e&&e.id!=='sitelive';})()''') is True,
            '屏幕中心命中元素不是背景层')
        close_modal()
        sample('live2d')

        # ── 静态次级动作 ──
        open_ship('宁海', 'ninghai_4')
        ev('''(function(){var b=document.getElementById('mSetBgStatic');
          if(b) b.click();})()''')
        time.sleep(0.25)
        txt = bg_text('mSetBgStatic')
        say(isinstance(txt, str) and '已用静态图' in txt, f'静态图次级键文案 = {txt!r}')
        say(wait("SiteBg.get().kind==='skin'", 20), '退回静态立绘成功')
        say(wait("!SiteBgLive.stats().hasCanvas && !SiteBgLive.stats().live", 20),
            '退回静态后动态宿主层已撤')
        sample('static', 4.0)

        # ── Spine：另一个皮肤 ──
        close_modal()
        ok = open_ship('寰昌', 'huanchang_2')
        say(ok, '打开寰昌/huanchang_2')
        tag = ev('''(function(){var b=document.querySelector('#mSetBg .bgtag');
          return b?b.textContent.trim():'';})()''')
        say(tag == '动态皮肤', f'主按钮角标 = {tag!r}（应为 动态皮肤）')
        click_bg()
        say(host_live('spine'), 'Spine 背景已挂载')
        moving, f0, f1 = frames_moving()
        say(moving, f'Spine 渲染帧推进（{f0} → {f1}）')
        if not moving:
            print('  [diag] visibility=%s hidden=%s stats=%s' %
                  (ev('document.visibilityState'), ev('document.hidden'),
                   ev('JSON.stringify(SiteBgLive.stats())')), flush=True)
        close_modal()
        sample('spine')

        # ── 切换：Spine → Live2D 必须是换背景，不是取消 ──
        open_ship('宁海', 'ninghai_4')
        click_bg()
        say(wait("SiteBg.get().kind==='live2d'", 30),
            '在 Spine 背景上点 Live2D 皮肤 = 切换（不是取消）')
        say(host_live('live2d'), '切换后 Live2D 背景在播')

        # 同一个按钮再点一次 = 取消
        click_bg()
        say(wait('!SiteBg.get()', 20), '同一皮肤再点一次 = 取消背景')
        click_bg()
        say(host_live('live2d'), '再次点回 Live2D 背景')
        close_modal()

        # ── 刷新恢复 ──
        cmd('Page.reload')
        time.sleep(2.5)
        say(wait('!!window.SiteBgLive', 60), '刷新后 SiteBgLive 重新加载')
        say(wait("SiteBgLive.stats().live", 120), '刷新后动态背景自动恢复')
        sample('reload')

        # 清掉，别把探针的状态留给用户
        ev('window.SiteBg&&SiteBg.clear()')
        base = result.get('base') or {}
        for tag in ('live2d', 'spine'):
            cur = result.get(tag) or {}
            if base and cur:
                cur['deltaWsGB'] = round(cur.get('wsGB', 0) - base.get('wsGB', 0), 2)
                cur['deltaTaskSecPer2s'] = round(cur.get('taskSecPer2s', 0) -
                                                 base.get('taskSecPer2s', 0), 3)
        json.dump(result, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\n相对基线：Live2D ΔWS=%+.2f GB / Δ主线程 %+.3fs/2s；Spine ΔWS=%+.2f GB / Δ主线程 %+.3fs/2s'
              % ((result.get('live2d') or {}).get('deltaWsGB', 0),
                 (result.get('live2d') or {}).get('deltaTaskSecPer2s', 0),
                 (result.get('spine') or {}).get('deltaWsGB', 0),
                 (result.get('spine') or {}).get('deltaTaskSecPer2s', 0)))
        print(f'\n已写 {os.path.relpath(OUT, ROOT)}')
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        chrome_tree.kill_tree(proc.pid)

    print()
    if FAIL:
        print(f'== 动态背景 UI 探针：{len(FAIL)} 项失败')
        for f in FAIL:
            print('   - ' + f)
        return 1
    print('== 动态背景 UI 探针：全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
