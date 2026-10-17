#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""panel_paper_probe.py — 纸本控制台的界面验收（2026-10-17 版面）。

上一版 `panel_ui_probe.py` 判的是「夜航星野 + 海军蓝 + 指针光效」那套版面；
2026-10-17 用户改判为纸本控制台（暖纸 / 墨 / 朱砂 / 苔绿 / 零玻璃 / 零星野），
旧探针里的星点密度、背景显影、指针光效等判据已失去前提，保留作历史对照。
本探针只判**新版面自己声称的东西**：

  1. 骨架：5 个步骤、全部阶段卡片都在（不是"看起来有"）；
  2. 字与色：主标题确实是衬线、纸底是暖色、全站零 backdrop-filter；
  3. 边界：星野与指针光效层确实退役（display:none），静止时 0 个动画；
  4. 交互：五步可点、细节/说明可开合、夜读可切换且能切回；
  5. 窄屏：右栏折到底部、进度线不横穿文字、无横向溢出；
  6. 截图：主屏 / 细节 / 夜读 / 窄屏四张，落到 .diag/panel_paper/。

用法:
  py -3 scripts/diag/panel_paper_probe.py --port 8790
  py -3 scripts/diag/panel_paper_probe.py --port 8790 --win 1600,1000

退出码: 0 全绿；1 有判红（逐条打印）。
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import websocket          # noqa: E402
import chrome_tree        # noqa: E402
from gallery_ui_shots import CHROME   # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, '.diag', 'panel_paper')
FAILS = []


def chk(name, ok, detail=''):
    print(('  PASS  ' if ok else '  FAIL  ') + name + ((' — ' + detail) if detail else ''))
    if not ok:
        FAILS.append(name)


class Pg:
    def __init__(self, cdp, url, win):
        prof = os.path.join(OUT, f'chrome_{os.getpid()}')
        os.makedirs(prof, exist_ok=True)
        self.proc = chrome_tree.install(subprocess.Popen([
            CHROME, '--headless=new', f'--remote-debugging-port={cdp}',
            '--remote-allow-origins=*', f'--user-data-dir={prof}',
            '--no-first-run', '--no-default-browser-check',
            '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
            '--use-angle=swiftshader', f'--window-size={win[0]},{win[1]}', url,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        ws = None
        for _ in range(120):
            try:
                tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{cdp}/json'))
                hit = [t for t in tabs if '127.0.0.1' in t.get('url', '')
                       and t.get('webSocketDebuggerUrl')]
                if hit:
                    ws = hit[0]['webSocketDebuggerUrl']
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if not ws:
            raise RuntimeError('no CDP tab（控制台起来了么？）')
        self.ws = websocket.create_connection(ws, timeout=120, max_size=None)
        self.i = 0
        self.exc = []

    def cmd(self, method, params=None):
        self.i += 1
        self.ws.send(json.dumps({'id': self.i, 'method': method, 'params': params or {}}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get('method') == 'Runtime.exceptionThrown':
                self.exc.append(m['params']['exceptionDetails'].get('text'))
            if m.get('id') == self.i:
                return m.get('result', {})

    def ev(self, expr):
        r = self.cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True})
        return r.get('result', {}).get('value')

    def shot(self, name):
        r = self.cmd('Page.captureScreenshot', {'format': 'png'})
        with open(os.path.join(OUT, name), 'wb') as f:
            f.write(base64.b64decode(r['data']))

    def size(self, w, h):
        self.cmd('Emulation.setDeviceMetricsOverride',
                 {'width': w, 'height': h, 'deviceScaleFactor': 1, 'mobile': False})

    def go(self, url, wait=2.4):
        self.cmd('Page.navigate', {'url': url})
        time.sleep(wait)

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def start_panel(port):
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1.5)
        return None
    except Exception:
        pass
    p = subprocess.Popen([sys.executable, os.path.join(ROOT, 'scripts', 'pipeline_panel.py'),
                          '--no-open', '--port', str(port)],
                         cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(p)
    for _ in range(60):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1.5)
            return p
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f'控制台没在 {port} 上起来')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8790)
    ap.add_argument('--cdp', type=int, default=8891)
    ap.add_argument('--win', default='1600,1000')
    a = ap.parse_args()
    win = tuple(int(x) for x in a.win.split(','))
    os.makedirs(OUT, exist_ok=True)
    start_panel(a.port)
    url = f'http://127.0.0.1:{a.port}/'
    pg = Pg(a.cdp, url, win)
    try:
        pg.cmd('Runtime.enable')
        pg.cmd('Page.enable')
        pg.size(*win)
        pg.go(url, 3)

        print('\n── 骨架与文案 ─────────────────────────────────')
        nstep = pg.ev("document.querySelectorAll('.snode').length")
        ndot = pg.ev("document.querySelectorAll('.snode .dot').length")
        nstage = pg.ev("(window.__probe&&__probe.state().stages||[]).length")
        chk('五个步骤全部渲染', nstep == 5, f'.snode={nstep}')
        chk('阶段方块数与状态表一致', ndot == nstage, f'.dot={ndot} / stages={nstage}')

        counts = []
        asks = []
        for n in range(1, 6):
            pg.ev(f"document.querySelectorAll('.snode')[{n-1}].click()")
            time.sleep(0.35)
            counts.append(pg.ev("document.querySelectorAll('#cards .stage').length"))
            asks.append(pg.ev("document.querySelector('.ask').textContent.trim()"))
        chk('每个阶段的卡片都挂在某一步下（合计 = 阶段数）',
            sum(counts) == nstage, f'{counts} 合计 {sum(counts)} / {nstage}')
        chk('五步都有各自的指令句', len(set(asks)) >= 4 and all(asks),
            ' / '.join(x[:10] for x in asks))

        print('\n── 字与色 ─────────────────────────────────────')
        fam = pg.ev("getComputedStyle(document.querySelector('.ask')).fontFamily") or ''
        size = pg.ev("parseFloat(getComputedStyle(document.querySelector('.ask')).fontSize)")
        chk('主标题走衬线字体', 'Noto Serif SC' in fam or 'Source Han Serif' in fam, fam[:42])
        chk('主标题字号 >= 40px', (size or 0) >= 40, f'{size}px')
        body = pg.ev("getComputedStyle(document.body).backgroundColor") or ''
        import re
        m = re.search(r'(\d+),\s*(\d+),\s*(\d+)', body)
        rgb = tuple(int(x) for x in m.groups()) if m else (0, 0, 0)
        chk('纸底是暖色（R>G>B，且不是高饱和）',
            rgb[0] > rgb[1] > rgb[2] and max(rgb) - min(rgb) < 40, str(rgb))
        nbd = pg.ev("[...document.querySelectorAll('*')].filter(e=>"
                    "getComputedStyle(e).backdropFilter!=='none').length")
        chk('全站零 backdrop-filter（玻璃退役）', nbd == 0, f'{nbd} 个')
        nbg = pg.ev("getComputedStyle(document.getElementById('bgfx')).display")
        nfx = pg.ev("getComputedStyle(document.getElementById('fxbeam')).display")
        chk('星野层退役', nbg == 'none', nbg)
        chk('指针光效层退役', nfx == 'none', nfx)

        print('\n── 静止与交互 ─────────────────────────────────')
        time.sleep(1.2)   # 五步点完会触发 .snode.in / .ask.swap 的入场动画，等它们跑完再判
        chk('静止时零个动画在跑', (pg.ev("document.getAnimations().length") or 0) == 0,
            f"getAnimations={pg.ev('document.getAnimations().length')}")
        pg.shot('main.png')
        pg.ev("document.getElementById('bDetail').click()")
        time.sleep(0.9)
        chk('细节抽屉能打开', bool(pg.ev("document.getElementById('detail').classList.contains('on')")))
        chk('细节里有日志与最近任务',
            bool(pg.ev("!!document.getElementById('log')")) and
            (pg.ev("document.querySelectorAll('#runs tr').length") or 0) > 0)
        chk('日志是深色电传面（与纸面分层）',
            'rgb(18, 16, 13)' == pg.ev("getComputedStyle(document.getElementById('log')).backgroundColor"),
            pg.ev("getComputedStyle(document.getElementById('log')).backgroundColor"))
        pg.shot('detail.png')
        pg.ev("document.getElementById('bDetail').click()")
        time.sleep(0.4)
        pg.ev("document.getElementById('bHelp').click()")
        time.sleep(0.6)
        chk('说明抽屉能打开', bool(pg.ev("document.getElementById('help').classList.contains('on')")))
        pg.ev("document.querySelector('#help [data-close]').click()")
        time.sleep(0.3)
        chk('说明抽屉能关闭', not bool(pg.ev("document.getElementById('help').classList.contains('on')")))

        pg.ev("localStorage.setItem('panel.night','0');document.body.classList.remove('night')")
        time.sleep(0.3)
        day = pg.ev("getComputedStyle(document.body).backgroundColor")
        pg.ev("document.getElementById('bSea').click()")
        time.sleep(0.5)
        night = pg.ev("getComputedStyle(document.body).backgroundColor")
        pg.shot('night.png')
        chk('夜读确实换了底色', day != night, f'{day} → {night}')
        chk('夜读是暖墨而不是蓝黑', bool(pg.ev(
            "(()=>{const c=getComputedStyle(document.body).backgroundColor;"
            "const m=c.match(/\\d+/g).map(Number);return m[0]>=m[1]&&m[1]>=m[2]})()")), night)
        pg.ev("document.getElementById('bSea').click()")
        time.sleep(0.4)

        print('\n── 窄屏 ───────────────────────────────────────')
        pg.size(1000, 800)
        pg.go(url, 2.6)
        chk('右栏折成底部横排',
            pg.ev("getComputedStyle(document.querySelector('.steps')).flexDirection") == 'row')
        chk('进度线不再横穿步骤文字',
            pg.ev("getComputedStyle(document.querySelector('.steps .track')).display") == 'none')
        chk('窄屏无横向溢出',
            bool(pg.ev("document.documentElement.scrollWidth<=innerWidth")))
        pg.shot('narrow.png')

        chk('全程无 JS 异常', not pg.exc, '; '.join(pg.exc[:3]))
        print('\n截图: ' + os.path.relpath(OUT, ROOT))
    finally:
        pg.close()

    if FAILS:
        print(f'\n[FAIL] {len(FAILS)} 条判红：')
        for x in FAILS:
            print('  - ' + x)
        return 1
    print('\n[PASS] 纸本控制台界面判据全绿')
    return 0


if __name__ == '__main__':
    sys.exit(main())
