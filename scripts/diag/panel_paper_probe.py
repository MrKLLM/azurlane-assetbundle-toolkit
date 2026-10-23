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
  5. 背景与悬停擦除（2026-10-21）：画布遮罩静止两帧 alpha 逐像素一致、划过处 alpha
     显著下降而没划过的角落不变、约 0.8s 淡回同值；`calm` / 减少动态效果 / 弹层打开时停用；
     夜读时画布纸色也换暖墨；自定义图片跨刷新保留；
  6. 悬停语言回归（用户点名满意的那套）：阶段卡表面抬一档 + 左墨条变深 + 交叉高亮接线，
     对照表 hover 转朱砂且不位移；五步索引 hover 下划线真的画得出来（不被 overflow 裁掉）；
  7. 窄屏：右栏折到底部、进度线不横穿文字、无横向溢出；
  8. 截图：主屏 / 细节 / 夜读 / 窄屏 / 擦除前后 / 背景选择器，落到 .diag/panel_paper/。

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
    PANEL_PORT = a.port          # 单独存一份：下面有 `for a, to, txt in acts` 会覆盖 a
    win = tuple(int(x) for x in a.win.split(','))
    os.makedirs(OUT, exist_ok=True)
    start_panel(a.port)
    url = f'http://127.0.0.1:{a.port}/'
    pg = Pg(a.cdp, url, win)
    try:
        pg.cmd('Runtime.enable')
        pg.cmd('Page.enable')
        pg.size(*win)
        # ⚠️ 等 6 秒而不是 3：`/api/state` 要 walk 7 万多个源包算输入指纹，实测冷启动
        # 约 3 秒才回。3 秒正好卡在边界上，于是 `LOADED=false`、snode=0、
        # 所有判据读到的都是占位符「—」⇒ 一片假红（2026-10-17 23:40 实测）。
        # 判据失败时先确认 `__probe.state().stages` 有 17 条，别急着改产品代码。
        pg.go(url, 6)
        for _ in range(12):
            if (pg.ev("typeof LOADED!=='undefined'&&LOADED") or False):
                break
            time.sleep(0.5)
        # 首屏必须落到机器真正停的那一步；固定从第 1 步打开会让全部完成的人
        # 先看到"先确认权威输入还在位"（2026-10-23 §187）。这里必须在下面
        # 五步点击循环之前量，否则量到的是探针自己切过去的步骤。
        chk('首屏落在当前步（不是固定第 1 步）',
            (pg.ev("step") or 0) == (pg.ev("__probe.work()") or 0),
            f'step={pg.ev("step")} work={pg.ev("__probe.work()")}')

        print('\n── 骨架与文案 ─────────────────────────────────')
        nstep = pg.ev("document.querySelectorAll('.snode').length")
        ndot = pg.ev("document.querySelectorAll('.snode .dot').length")
        nstage = pg.ev("(window.__probe&&__probe.state().stages||[]).length")
        chk('五个步骤全部渲染', nstep == 5, f'.snode={nstep}')
        chk('阶段方块数与状态表一致', ndot == nstage, f'.dot={ndot} / stages={nstage}')

        counts = []
        asks = []
        ebs = []
        for n in range(1, 6):
            pg.ev(f"document.querySelectorAll('.snode')[{n-1}].click()")
            time.sleep(0.35)
            counts.append(pg.ev("document.querySelectorAll('#cards .stage').length"))
            asks.append(pg.ev("document.querySelector('.ask').textContent.trim()"))
            ebs.append(pg.ev("document.getElementById('eyebrowTx').textContent.trim()"))
        chk('每个阶段的卡片都挂在某一步下（合计 = 阶段数）',
            sum(counts) == nstage, f'{counts} 合计 {sum(counts)} / {nstage}')
        chk('五步都有各自的指令句', len(set(asks)) >= 4 and all(asks),
            ' / '.join(x[:10] for x in asks))
        # 步骤标题必须来自状态表，不能是第二份手抄的 STEPNAME（2026-10-17 它曾整体错位一位）
        import json as _json
        titles = _json.loads(pg.ev(
            "JSON.stringify(Object.values(window.__probe.state().steps||{}).map(x=>x[0]))") or '[]')
        chk('步骤标题与状态表逐字一致',
            len(titles) == 5 and all(t in eb for t, eb in zip(titles, ebs)),
            ' / '.join(f'{t}↔{eb.split("·")[1].strip() if "·" in eb else eb}' for t, eb in zip(titles, ebs)))
        # 动作范围必须落在本步：第 2 步「同步配置表」是后加的，旧版手抄的 n===2/3/4
        # 曾整体错位一位，还把「换入」签成空清单（step===4 时 swap 阶段已经搬到第 5 步）。
        scopes = _json.loads(pg.ev(
            "JSON.stringify({cfg:__probe.scope('cfgsync'),exp:__probe.scope('export'),"
            "sw:__probe.scope('swap'),live:__probe.live('swap'),review:__probe.scope('review')})") or '{}')
        smap = _json.loads(pg.ev(
            "JSON.stringify(Object.fromEntries((__probe.state().stages||[]).map(s=>[s.key,s.step])))") or '{}')
        chk('同步配置表动作只跑第 2 步的阶段',
            bool(scopes.get('cfg')) and all(smap.get(k) == 2 for k in scopes['cfg']),
            f"{scopes.get('cfg')}")
        chk('重导动作只跑第 3 步的阶段',
            bool(scopes.get('exp')) and all(smap.get(k) == 3 for k in scopes['exp']),
            f"{scopes.get('exp')}")
        chk('换入动作只跑第 5 步的阶段',
            bool(scopes.get('sw')) and all(smap.get(k) == 5 for k in scopes['sw']),
            f"{scopes.get('sw')}")
        chk('换入签字单不是空清单（swap-in + derive 至少两项）',
            len(scopes.get('live') or []) >= 2, f"{scopes.get('live')}")
        # 截图回到第一步，别把测试末态（第 5 步）当成产品首屏
        pg.ev("document.querySelectorAll('.snode')[0].click()")
        time.sleep(0.4)

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

        # ── 背景与悬停擦除（2026-10-21）────────────────────────────────
        # 判据全部落在**像素**上：遮罩画布自身的 alpha（240≈纸面 .94，0=全擦开）。
        # 不靠截图肉眼，也不靠"有没有那个元素"冒充"效果成立"。
        print('\n── 背景与悬停擦除 ─────────────────────────────')
        TINY_PNG = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ'
                    'AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
        chk('背景四层在位（图 / 纸面遮罩 / 网格 / 纸纹）',
            bool(pg.ev("!!document.getElementById('bgstage')&&"
                       "!!document.getElementById('bgart')&&"
                       "!!document.getElementById('bgveil')&&"
                       "!!document.getElementById('bggrid')&&"
                       "!!document.getElementById('bggrain')")))
        bg0 = pg.ev("__probe.bg()") or {}
        chk('默认背景是「航路版画」且是真的 SVG（不是空 DIV）',
            bg0.get('art') == 'logbook' and bool(bg0.get('svg')), str(bg0.get('art')))
        chk('遮罩画布按视口×dpr 建（不是 300×150 的默认画布）',
            bool(pg.ev("(()=>{const c=document.getElementById('bgveil');"
                       "const d=window.BG?BG.dpr:1;"
                       "return c.width===Math.round(innerWidth*d)&&"
                       "c.height===Math.round(innerHeight*d)&&c.width>800})()")),
            str(bg0.get('veil')))
        # 指针先停到角落，避免 hover/视差干扰静止比对
        pg.cmd('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': 12, 'y': 12})
        time.sleep(1.1)
        pa = pg.ev("__probe.bgAlpha(800,420)")
        pb = pg.ev("__probe.bgAlpha(1240,660)")
        time.sleep(1.0)
        pa2 = pg.ev("__probe.bgAlpha(800,420)")
        pb2 = pg.ev("__probe.bgAlpha(1240,660)")
        chk('静止时纸面接近不透明（底画只透 ~6%）',
            isinstance(pa, int) and 232 <= pa <= 245, str(pa))
        chk('静止两帧遮罩 alpha 完全一致（不闪）', pa == pa2 and pb == pb2,
            f'{pa}/{pa2} {pb}/{pb2}')
        chk('静止时没有绘制循环、没有残留笔迹',
            not (bg0.get('raf') or False) and (pg.ev("__probe.bg().stamps") or 0) == 0,
            f"raf={bg0.get('raf')} stamps={bg0.get('stamps')}")

        for k in range(22):
            pg.cmd('Input.dispatchMouseEvent',
                   {'type': 'mouseMoved', 'x': 700 + k * 16,
                    'y': 470 + (k % 4) * 6})
            time.sleep(0.012)
        time.sleep(0.05)
        # 采样点必须在**笔迹末端**：淡出是按时间衰减的，取笔画中段会读到"已经淡了一半"的
        # alpha（同一份实现早读 3、晚读 111 都发生过）。末端 ~30ms 前刚擦，才代表"擦得开"。
        mid = pg.ev("__probe.bgAlpha(1010,495)")
        far = pg.ev("__probe.bgAlpha(1400,900)")
        dur = pg.ev("__probe.bg().lastMs") or 0
        chk('划过处纸面被擦开（alpha 显著下降）',
            isinstance(mid, int) and mid < 90, str(mid))
        chk('没划过的角落不受影响（不是整张淡掉）',
            isinstance(far, int) and far >= 232, str(far))
        chk('单帧擦除耗时 < 12ms（不是拿卡顿换效果；SwiftShader 下留余量）', dur < 12, f'{dur}ms')
        pg.shot('bg_erase.png')
        time.sleep(1.5)
        he = pg.ev("__probe.bgAlpha(820,500)")
        chk('约 0.8s 内淡回同一张纸（alpha 复原）',
            isinstance(he, int) and abs(he - pa) <= 1, f'{he} vs {pa}')
        chk('淡净后绘制循环已停、无残留笔迹、无动画',
            not (pg.ev("__probe.bg().raf") or False) and
            (pg.ev("__probe.bg().stamps") or 0) == 0 and
            (pg.ev("document.getAnimations().length") or 0) == 0)
        pg.shot('bg_healed.png')

        # 「设了 vs 没设」整屏对照：素纸必须真的回到旧观感（截图不同），
        # 否则可能只是"选了个名字没换图"——这类假接线比效果本身更常见。
        import hashlib
        h1 = hashlib.sha1(open(os.path.join(OUT, 'bg_healed.png'), 'rb').read()).hexdigest()
        pg.ev("__probe.bgChoose('paper')")
        time.sleep(0.55)
        pg.shot('bg_plain.png')
        h2 = hashlib.sha1(open(os.path.join(OUT, 'bg_plain.png'), 'rb').read()).hexdigest()
        chk('「素纸」与「航路版画」整屏观感确实不同（底图真的在渲染）',
            h1 != h2, h1[:10] + ' vs ' + h2[:10])
        chk('「素纸」下底层图隐藏、纸面遮罩仍在',
            (pg.ev("getComputedStyle(document.getElementById('bgart')).opacity") or '') == '0'
            and (pg.ev("__probe.bgAlpha(800,420)") or 0) >= 232)
        pg.ev("__probe.bgChoose('logbook')")
        time.sleep(0.5)

        pg.ev("document.getElementById('bBg').click()")
        time.sleep(0.4)
        chk('「背景」按钮能打开选择器', bool(pg.ev("__probe.bg().open")))
        chk('选择器给 5 个背景（含素纸与自定义）',
            (pg.ev("document.querySelectorAll('#bgpresets .bgtile').length") or 0) == 5)
        pg.shot('bg_picker.png')
        pg.ev("__probe.bgChoose('chart')")
        time.sleep(0.35)
        chk('切到「海图」后底层图真的换了（并记进 localStorage）',
            (pg.ev("__probe.bg().art") or '') == 'chart' and
            (pg.ev("localStorage.getItem('panel.bgpreset')") or '') == 'chart')
        pg.ev("__probe.bgChoose('logbook')")
        pg.ev("__probe.bgPick(false)")
        time.sleep(0.3)
        # 选择器开着时擦除必须暂停：那是正在选东西，不是在看背景
        pg.ev("__probe.bgPick(true)")
        time.sleep(0.25)
        for k in range(8):
            pg.cmd('Input.dispatchMouseEvent',
                   {'type': 'mouseMoved', 'x': 600 + k * 20, 'y': 640})
            time.sleep(0.012)
        time.sleep(0.1)
        chk('选择器打开时擦除暂停（不抢交互）',
            not (pg.ev("__probe.bg().raf") or False) and
            (pg.ev("__probe.bgAlpha(700,640)") or 0) >= 232,
            str(pg.ev("__probe.bgAlpha(700,640)")))
        pg.ev("__probe.bgPick(false)")
        time.sleep(0.3)
        # 「动效从简」= 连背景擦除也停（用户按 M 就是要安静）
        pg.ev("__probe.calm(true)")
        for k in range(8):
            pg.cmd('Input.dispatchMouseEvent',
                   {'type': 'mouseMoved', 'x': 900 + k * 20, 'y': 700})
            time.sleep(0.012)
        time.sleep(0.1)
        chk('「动效从简」下擦除停用',
            not (pg.ev("__probe.bg().raf") or False) and
            (pg.ev("__probe.bgAlpha(960,700)") or 0) >= 232,
            str(pg.ev("__probe.bgAlpha(960,700)")))
        pg.ev("__probe.calm(false)")
        time.sleep(0.25)

        # 五步索引 hover：下划线必须真的"从 0 拉到 100%"。
        # 这条专门防那个坑：下划线写在 `label::after` 上会被 `label{overflow:hidden}` 裁掉，
        # 屏幕上什么都没有、代码看着却对。现在画在盒内的 background-size 上。
        pg.cmd('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': 12, 'y': 12})
        time.sleep(0.3)
        bs0 = pg.ev("getComputedStyle(document.querySelector('.snode:not(.on) label'))"
                    ".backgroundSize") or ''
        nr = pg.ev("JSON.stringify((()=>{const e=document.querySelector('.snode:not(.on)');"
                   "if(!e) return null;const r=e.getBoundingClientRect();"
                   "return [r.left,r.top,r.width,r.height]})())")
        nr = json.loads(nr) if nr else None
        if nr and nr[2] > 0:
            pg.cmd('Input.dispatchMouseEvent',
                   {'type': 'mouseMoved', 'x': int(nr[0] + nr[2] * .5),
                    'y': int(nr[1] + nr[3] * .5)})
            time.sleep(0.45)
            bs1 = pg.ev("getComputedStyle(document.querySelector('.snode:not(.on):hover label'))"
                        ".backgroundSize") or ''
            chk('五步索引 hover 拉出一道下划线（盒内画，不会被 overflow 裁掉）',
                bs0.replace('px', '').startswith('0') and bs1.startswith('100%'),
                f'{bs0} → {bs1}')
            pg.cmd('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': 12, 'y': 12})
            time.sleep(0.25)

        print('\n── 静止与交互 ─────────────────────────────────')
        time.sleep(1.2)   # 五步点完会触发 .snode.in / .ask.swap 的入场动画，等它们跑完再判
        chk('静止时零个动画在跑', (pg.ev("document.getAnimations().length") or 0) == 0,
            f"getAnimations={pg.ev('document.getAnimations().length')}")
        # 数据状态相关：preflight 因配置表过期判红时，第 1 步不能被锁死成只剩「重查」，
        # 卡点要把修复动作指到第 2 步（2026-10-17 用户：点完再查一次没反应，第一步也没处按）。
        why_now = pg.ev("document.getElementById('why').textContent") or ''
        if '配置表过期' in why_now:
            acts = pg.ev("__probe.ask().acts") or []
            gate_acts = pg.ev("__probe.ask().gateActs") or []
            chk('配置表过期时第 1 步仍能拉包（不把整步锁死）',
                any(x.startswith('pullcheck|') for x in acts), ' / '.join(acts))
            chk('卡点提供「去第 2 步同步配置表」',
                any(x.startswith('goto|') and '同步配置表' in x for x in gate_acts),
                ' / '.join(gate_acts))
            chk('待办指向第 2 步（修复动作所在）',
                pg.ev("__probe.work()") == 2, str(pg.ev("__probe.work()")))
        pg.shot('main.png')

        # 回执：结论没变时也必须留下"跑过"的证据（旧版这里一声不响）
        if '配置表过期' in why_now:
            pg.ev("document.querySelectorAll('#gate button')[1].click()")
            time.sleep(0.3)
            mid = pg.ev("document.getElementById('receipt').textContent") or ''
            chk('动作提交后立刻有回执', ('已提交' in mid or ' 秒' in mid), mid[:60])
            rc = ''
            for _ in range(30):
                time.sleep(0.5)
                rc = pg.ev("document.getElementById('receipt').textContent") or ''
                if ' 秒' in rc:
                    break
            chk('重查跑完留下结论与用时', ('重查闸门' in rc and ' 秒' in rc), rc[:90])
            chk('回执不再把「⇒ 跑 cfg…」塞进括号', '⇒' not in rc, rc[:90])
            pg.shot('gate_receipt.png')

        pg.ev("document.getElementById('bDetail').click()")
        time.sleep(0.9)
        chk('细节抽屉能打开', bool(pg.ev("document.getElementById('detail').classList.contains('on')")))
        chk('细节里有日志与最近任务',
            bool(pg.ev("!!document.getElementById('log')")) and
            (pg.ev("document.querySelectorAll('#runs tr').length") or 0) > 0)
        # 悬停语言：用户在细节界面"挺满意"的就是这一套，写成判据防回归 ——
        #   ① 阶段卡：表面**抬一档**（换底色），transform 永不动；
        #   ② 左侧 2px 墨条变深（强调靠一道细线，不靠发光）；
        #   ③ 右栏对应状态点被点亮（证据卡 ↔ 状态点的交叉高亮）。
        # 用 CDP 可信鼠标制造 :hover，读 computed style —— 不靠截图肉眼。
        rect = pg.ev("JSON.stringify((()=>{const e=document.querySelector("
                     "'#cards .stage:not(.fail):not(.await)')||"
                     "document.querySelector('#cards .stage');"
                     "if(!e) return null;const r=e.getBoundingClientRect();"
                     "return [r.left,r.top,r.width,r.height]})())")
        rect = json.loads(rect) if rect else None
        if rect and rect[2] > 0:
            pg.cmd('Input.dispatchMouseEvent',
                   {'type': 'mouseMoved', 'x': int(rect[0] + rect[2] * 0.3),
                    'y': int(rect[1] + rect[3] * 0.5)})
            time.sleep(0.45)
            st_sel = "#cards .stage:not(.fail):not(.await)||#cards .stage"
            st_bg = pg.ev("(()=>{const e=document.querySelector('#cards .stage:hover');"
                          "return e?getComputedStyle(e).backgroundColor:null})()")
            st_tick = pg.ev("(()=>{const e=document.querySelector('#cards .stage:hover');"
                            "return e?getComputedStyle(e,'::before').backgroundColor:null})()")
            hot = pg.ev("document.querySelectorAll('.snode .dot.hot').length") or 0
            chk('阶段卡 hover 抬一档表面（纸面阶梯，不是上浮）',
                st_bg == 'rgb(232, 224, 210)', str(st_bg))
            chk('阶段卡 hover 左侧墨条变深（2px 细线语言）',
                st_tick == 'rgb(138, 129, 116)', str(st_tick))
            chk('阶段卡 hover 仍会标记右栏对应状态点（交叉高亮接线；当前布局下被抽屉盖住）',
                hot >= 1, str(hot))
            # 对照表：悬停边框转朱砂，图片与卡片本身不位移（不许上浮/果冻）
            if (pg.ev("document.querySelectorAll('#sheets a').length") or 0) > 0:
                pg.ev("document.querySelector('#sheets a').scrollIntoView({block:'center'})")
                time.sleep(0.35)
                r2 = json.loads(pg.ev(
                    "JSON.stringify((()=>{const e=document.querySelector('#sheets a');"
                    "const r=e.getBoundingClientRect();"
                    "return [r.left,r.top,r.width,r.height]})())"))
                pg.cmd('Input.dispatchMouseEvent',
                       {'type': 'mouseMoved', 'x': int(r2[0] + r2[2] / 2),
                        'y': int(r2[1] + r2[3] / 2)})
                time.sleep(0.4)
                sh_bd = pg.ev("getComputedStyle(document.querySelector('#sheets a:hover'))"
                              ".borderTopColor")
                sh_tf = pg.ev("getComputedStyle(document.querySelector('#sheets a:hover'))"
                              ".transform")
                chk('对照表 hover 边框转朱砂', sh_bd == 'rgb(166, 67, 46)', str(sh_bd))
                chk('对照表 hover 不上浮/不缩放（纸面不许果冻）',
                    sh_tf in (None, 'none'), str(sh_tf))
                pg.ev("const c=document.querySelector('#detail .col');if(c)c.scrollTop=0")
                time.sleep(0.25)
            pg.cmd('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': 12, 'y': 12})
            time.sleep(0.2)
        # 盘面与清单：打开抽屉会自动触发一次盘点（后台算，前端轮询）。
        # 只判骨架与接口接线，不判数值——数值随盘面变。
        chk('细节里有「盘面与清单」账本（四个目录行 + 清单行）',
            (pg.ev("document.querySelectorAll('#disk .drow').length") or 0) >= 5 or
            '盘点' in (pg.ev("document.getElementById('disk').textContent") or ''),
            pg.ev("document.getElementById('disk').textContent.slice(0,60)"))
        chk('盘面判据写明「源包别删 / 产物删了画廊就缺」',
            '别删' in (pg.ev("document.querySelector('.dnote').textContent") or '') and
            '画廊' in (pg.ev("document.querySelector('.dnote').textContent") or ''))
        # 清理中心弹窗：只验骨架与"禁止项说清了原因"，**绝不真的点清理**。
        pg.ev("document.getElementById('bClean').click()")
        time.sleep(0.6)
        chk('清理中心弹窗能打开',
            bool(pg.ev("document.getElementById('cleanmodal').classList.contains('on')")))
        # ⚠️ "DOM 在"≠"看得见"：.veil/.sheet 的定位样式挂在 ID 选择器上，
        # 漏了 #cleanmodal 那份就是一段不可见的 inline 文本（2026-10-18 实测翻车）。
        chk('清理弹窗真的可见（不是不可见的 inline 文本）',
            bool(pg.ev("(()=>{const m=document.getElementById('cleanmodal');"
                       "if(!m.classList.contains('on')) return false;"
                       "const s=m.querySelector('.sheet').getBoundingClientRect();"
                       "return s.width>300 && s.top>=0 && s.height>300})()")),
            str(pg.ev("JSON.stringify((()=>{const s=document.querySelector('#cleanmodal .sheet')"
                      ".getBoundingClientRect();return [s.width,s.top,s.height]})())")))
        # 账单尺寸是冷缓存慢算（实测首算 ~15s），探针轮询等它出来
        rows = 0
        for _ in range(30):
            rows = pg.ev("document.querySelectorAll('#cleanList .crow').length") or 0
            if rows >= 4:
                break
            time.sleep(1.5)
        chk('清理账单列出可清理目标', rows >= 4, str(rows))
        blocked = pg.ev("document.querySelector('#cleanmodal .blocked').textContent") or ''
        chk('禁止区点名源包并给出理由（清单≠内容）',
            '源包' in blocked and '清单' in blocked and '目录' in blocked and '重导' in blocked,
            blocked[:80])
        chk('换入备份项要求手输 DELETE 而不是一键删',
            'DELETE' in (pg.ev("document.getElementById('cleanSub').textContent") or '') or
            bool(pg.ev("[...document.querySelectorAll('#cleanList .crow .dim')]"
                       ".some(x=>x.textContent.includes('DELETE'))")),
            '看账单各行说明')
        pg.ev("document.querySelector('#cleanmodal [data-cclose]').click()")
        time.sleep(0.3)
        chk('清理弹窗能关（Esc/遮罩/按钮三路）',
            not bool(pg.ev("document.getElementById('cleanmodal').classList.contains('on')")))
        chk('日志是深色电传面（与纸面分层）',
            'rgb(18, 16, 13)' == pg.ev("getComputedStyle(document.getElementById('log')).backgroundColor"),
            pg.ev("getComputedStyle(document.getElementById('log')).backgroundColor"))
        pg.shot('detail.png')
        pg.ev("document.getElementById('bDetail').click()")
        time.sleep(0.4)

        print('\n── 步骤状态与签字 ─────────────────────────────')
        # 探针不能假设"待办一定是第 2 步"：用户可能已经同步完配置表、正在第 3 步。
        work = pg.ev("__probe.work()")
        # 第 3 步：只要这一步还有导出动作，主按钮必须先弹签字单，不能"点了直接开跑又回来"
        # （2026-10-17 用户点的就是「重跑到待确认」，以为签字窗坏了）。
        # 判据按**动作类型**（data-a=export）而不是文案：这一部全部跑完之后，
        # 主按钮会变成"去第 5 步"，那时没有签字单可弹，不能算 FAIL。
        pg.ev("document.querySelectorAll('.snode')[2].click()")
        time.sleep(0.45)
        acts3 = _json.loads(pg.ev(
            "JSON.stringify([...document.querySelectorAll('#cta button')]"
            ".map(b=>[b.dataset.a,b.textContent.trim()]))") or '[]')
        has_export = any(x[0] == 'export' for x in acts3)
        if has_export:
            cta3 = pg.ev("document.querySelector('#cta .pact').textContent") or ''
            chk('第 3 步主按钮写明签字或重导', ('签字' in cta3 or '重导' in cta3), cta3)
            pg.shot('export.png')
            pg.ev("document.querySelector('#cta .pact').click()")
            time.sleep(0.5)
            chk('点第 3 步主按钮先弹签字单，不直接开跑',
                bool(pg.ev("document.getElementById('signmodal').classList.contains('on')")))
            rows3 = pg.ev(
                "[...document.querySelectorAll('#signList .srow .k')].map(x=>x.textContent).join(',')") or ''
            chk('第 3 步签字单列出 deps / meta / audio / cg',
                all(k in rows3 for k in ('deps', 'meta', 'audio', 'cg')), rows3)
            alt = pg.ev("(()=>{const b=document.getElementById('signAlt');"
                        "return b?[b.hidden,b.textContent]:null})()")
            chk('签字单提供「只跑到待确认」退路',
                bool(alt) and not alt[0] and '只跑到待确认' in alt[1], str(alt))
            pg.shot('export_sign.png')
            pg.ev("closeSign()")
            time.sleep(0.3)

        # 查看提示：必须切到一个**非待办**步骤才成立。
        # 全绿时没有"待办"，界面改说「已跑完」——判据要同时接受两种状态，
        # 否则一轮跑完后探针全红（2026-10-17 实测）。
        view = 5 if work != 5 else 1
        # “真跑完”直接问页面自己的判据，别在探针里重写一份：
        # `allStagesPass()` 会把「整步 idle、后面已有进展」的前缀算作已完成（§184），
        # 探针旧版按原始 verdict 逐条要求 ok ⇒ 01/02 为 — 时误判成"没跑完"，
        # 于是拿"待办"文案去量一个"已跑完"的界面（2026-10-23 §187 当场抓到）。
        allpass = bool(pg.ev("allStagesPass()"))
        pg.ev(f"document.querySelectorAll('.snode')[{view-1}].click()")
        time.sleep(0.45)
        vn = pg.ev("!document.getElementById('viewnote').hidden")
        vtx = pg.ev("document.getElementById('viewnote').textContent") or ''
        chk('切到非待办步骤会出查看提示', vn and '你在看第' in vtx, vtx[:48])
        chk('查看提示说清待办/已跑完',
            ('待办是第' in vtx) if not allpass else ('已全部判绿' in vtx), vtx[:60])
        chk('徽标写「查看中」（全绿时写「已跑完」）',
            (pg.ev("document.getElementById('stepState').textContent") or '').strip()
            == ('查看中' if not allpass else '已跑完'),
            pg.ev("document.getElementById('stepState').textContent"))
        chk('右栏有且只有一个「待办/已跑完」标记',
            (pg.ev("document.querySelectorAll('.snode.cur').length") or 0) == 1)
        chk('右栏标题常驻显示待办或已跑完',
            bool(pg.ev("/^(待办|已跑完) \\d\\d$/"
                       ".test(document.getElementById('railCur').textContent.trim())")),
            pg.ev("document.getElementById('railCur').textContent"))
        if allpass:
            # 全绿时四个入口必须都指向结果步：不能再让人去重查/重解，也不能把
            # "回第 1 步"伪装成"再来一轮"（2026-10-23 §187）。
            a1 = pg.ev("askOf(1).ask") or ''
            a2 = pg.ev("askOf(2).ask") or ''
            chk('全绿时第 1/2 步说明这一轮没重新检查',
                '没重新检查' in a1 and '没重新检查' in a2, f'{a1} / {a2}')
            chk('全绿时下一步 CTA 指向第 5 步',
                pg.ev("nextStepAct(4).act.to") == 5,
                str(pg.ev("nextStepAct(4).act.to")))
            chk('右栏按钮文案与真实目标一致',
                '去看第 5 步' in (pg.ev(
                    "document.getElementById('bBackCur').textContent") or ''))
        pg.shot('preview.png')
        pg.ev("document.getElementById('bBackCur').click()")
        time.sleep(0.4)
        chk('一键跳到待办步骤后提示消失', bool(pg.ev("document.getElementById('viewnote').hidden")))

        # 第 2 步：文案永远是配置表；签字单只在它还没同步完时才有得测。
        pg.ev("document.querySelectorAll('.snode')[1].click()")
        time.sleep(0.45)
        ask2 = pg.ev("document.querySelector('.ask').textContent") or ''
        cta2 = pg.ev("document.querySelector('#cta .pact').textContent") or ''
        chk('第 2 步文案是配置表，不是重导', '配置表' in ask2 and '重算' not in ask2, ask2[:40])
        if '同步配置表' in cta2:
            chk('第 2 步主动作是同步配置表', '同步配置表' in cta2, cta2)
            pg.shot('cfg.png')
            pg.ev("document.querySelector('#cta .pact').click()")
            time.sleep(0.5)
            chk('同步配置表会开签字单（不是直接开跑）',
                bool(pg.ev("document.getElementById('signmodal').classList.contains('on')")))
            sign_txt = pg.ev("document.getElementById('signList').textContent") or ''
            chk('签字单列的是 cfg.publish 与写入位置',
                'cfg.publish' in sign_txt and 'inputs/gamecfg' in sign_txt, sign_txt[:70])
            chk('未勾选/未签名时放行按钮禁用',
                bool(pg.ev("document.getElementById('signGo').disabled")))
            pg.ev("document.getElementById('signAgree').checked=true;"
                  "const n=document.getElementById('signName');n.value='测试';"
                  "n.dispatchEvent(new Event('input'))")
            time.sleep(0.2)
            chk('勾选并签名后才可放行',
                not bool(pg.ev("document.getElementById('signGo').disabled")))
            pg.shot('cfg_sign.png')
            pg.ev("closeSign()")          # 只验接线，不真的发布 inputs/gamecfg
            time.sleep(0.3)
            chk('取消签字不会关掉配置表这一步',
                '配置表' in (pg.ev("document.querySelector('.ask').textContent") or ''))
        else:
            print(f'  SKIP  第 2 步已同步完成（主动作「{cta2}」），跳过同步签字单')

        # 表漂移卡点（§155）：已发布皮肤表比本轮解出来的少行时，
        # 第 2 步必须自己说出来，并把主按钮换成"重新同步并发布"，
        # 而不是停在全绿的"配置表已对齐源包"上。
        gap = pg.ev("((window.__probe.state().skin_gap||{}).gap)||0")
        if gap:
            pg.ev("document.querySelectorAll('.snode')[1].click()")
            time.sleep(0.4)
            cta2b = pg.ev("document.querySelector('#cta .pact').textContent") or ''
            ask2b = pg.ev("document.querySelector('.ask').textContent") or ''
            chk('表漂移时第 2 步主按钮是重新发布', '发布' in cta2b, cta2b)
            chk('表漂移时第 2 步文案说清缺行', '还没发布' in ask2b, ask2b[:40])
            acts3b = _json.loads(pg.ev(
                "JSON.stringify([...document.querySelectorAll('#cta button')]"
                ".map(b=>[b.dataset.a,b.dataset.to||'',b.textContent.trim()]))") or '[]')
            pg.ev("document.querySelectorAll('.snode')[2].click()")
            time.sleep(0.4)
            acts3c = _json.loads(pg.ev(
                "JSON.stringify([...document.querySelectorAll('#cta button')]"
                ".map(b=>[b.dataset.a,b.dataset.to||'',b.textContent.trim()]))") or '[]')
            chk('表漂移时第 3 步不放行导出（先回第 2 步）',
                not any(x[0] == 'export' for x in acts3c) and
                any(x[0] == 'goto' and x[1] == '2' for x in acts3c),
                ' / '.join(f'{x[0]}|{x[2]}' for x in acts3c))
        else:
            print('  SKIP  皮肤表无漂移，跳过漂移卡点检查')

        pg.ev("openSign({keys:['pull'],what:'测试签字',note:'这是一条测试说明，不会真的发请求。',"
              "onOk:()=>{window.__signed=1}})")
        time.sleep(0.45)
        chk('签字窗口能打开', bool(pg.ev("document.getElementById('signmodal').classList.contains('on')")))
        chk('签字窗口逐条列出阶段与写入位置',
            (pg.ev("document.querySelectorAll('#signmodal .srow').length") or 0) > 0 and
            bool(pg.ev("document.getElementById('signList').textContent.includes('写到')")))
        pg.shot('sign.png')
        pg.ev("document.getElementById('signAgree').checked=true;"
              "const m=document.getElementById('signName');m.value='测试';"
              "m.dispatchEvent(new Event('input'))")
        time.sleep(0.2)
        pg.ev("document.getElementById('signGo').click()")
        time.sleep(0.4)
        chk('签字回调执行且窗口关闭',
            pg.ev("window.__signed===1") and
            not bool(pg.ev("document.getElementById('signmodal').classList.contains('on')")))

        # 退路按钮：不签字只跑差异。用桩验证接线，不真的发 export 请求。
        pg.ev("openSign({keys:['deps'],what:'测试退路',note:'不会发请求。',"
              "onOk:()=>{},alt:{label:'只跑到待确认（不签字）',run:()=>{window.__alt=1}}})")
        time.sleep(0.35)
        chk('签字单的退路按钮可见', not bool(pg.ev("document.getElementById('signAlt').hidden")))
        pg.ev("document.getElementById('signAlt').click()")
        time.sleep(0.35)
        chk('退路按钮执行回调并关闭窗口',
            pg.ev("window.__alt===1") and
            not bool(pg.ev("document.getElementById('signmodal').classList.contains('on')")))

        # 跳步按钮：标签写的第几步必须和真实目标一致，点下去必须真的落到那一步
        # （2026-10-17 用户在第 5 步点「去第 3 步重导」，被扔回第 1 步——
        #  goto 的 data-to 没渲染进主按钮，`+undefined||1` 落到了第 1 步）。
        print('\n── 跳步按钮的标签与目标 ───────────────────────')
        acts5 = []
        for n in range(1, 6):
            pg.ev(f"document.querySelectorAll('.snode')[{n-1}].click()")
            time.sleep(0.3)
            acts = _json.loads(pg.ev(
                "JSON.stringify([...document.querySelectorAll('#cta button')]"
                ".map(b=>[b.dataset.a,b.dataset.to||'',b.textContent.trim()]))") or '[]')
            if n == 5:
                acts5 = acts
            bad = []
            for a, to, txt in acts:
                if a != 'goto':
                    continue
                m = re.search(r'第\s*(\d+)\s*步', txt)
                if not m or m.group(1) != str(to):
                    bad.append(f'{txt}→{to or "无目标"}')
            chk(f'第 {n} 步跳转按钮的标签与目标一致', not bad, '; '.join(bad) or f'{len(acts)} 个按钮')
        pg.ev("document.querySelectorAll('.snode')[4].click()")
        time.sleep(0.3)
        goto_btn = pg.ev("(()=>{const b=[...document.querySelectorAll('#cta button')]"
                         ".find(x=>x.dataset.a==='goto');"
                         "return b?[b.dataset.to,b.textContent.trim()]:null})()")
        # 「缺口在本步 ⇒ 主按钮是换入」只在**第 5 步真的是缺口所在**时成立。
        # 上游有活（第 1/3 步没跑）时，往回跳才是对的 —— 2026-10-17 §157 之后
        # 配置表一刷新，下游全部回到"未跑"，缺口就在上游。
        gap_step = pg.ev("__probe.gap()")
        if goto_btn:
            if gap_step == 5:
                chk('第 5 步缺口在本步时主按钮是换入（签字），不是往回跳',
                    any(x[0] == 'swap' for x in acts5),
                    ' / '.join(f'{x[0]}|{x[2]}' for x in acts5))
            else:
                chk(f'上游第 {gap_step} 步有活时，第 5 步主按钮回跳到那一大步',
                    any(x[0] == 'goto' and int(x[1] or 0) == int(gap_step) for x in acts5),
                    f'缺口在第 {gap_step} 步 / ' + ' / '.join(f'{x[0]}|{x[2]}' for x in acts5))
            pg.ev("[...document.querySelectorAll('#cta button')]"
                  ".find(x=>x.dataset.a==='goto').click()")
            time.sleep(0.35)
            chk('点跳转按钮真的落到标签写的那一步',
                pg.ev("__probe.view()") == int(goto_btn[0]),
                f'label={goto_btn[1]} view={pg.ev("__probe.view()")}')
            pg.ev("document.querySelectorAll('.snode')[4].click()")
            time.sleep(0.3)

        # 正文点名的步骤号必须等于按钮目标：2026-10-17 用户截图里第 2 步正文写
        # 「下一步：从源包重算产物（第 3 步）」，按钮却是「去第 5 步 签字换入 →」
        # ——步骤 3/4 早就跑完了，按钮按"下一个还有活的步骤"算，正文写死了 nExport。
        print('\n── 正文与按钮目标必须同源 ─────────────────────')
        for n in range(1, 6):
            pg.ev(f"document.querySelectorAll('.snode')[{n-1}].click()")
            time.sleep(0.3)
            why = pg.ev("document.getElementById('why').textContent") or ''
            acts = _json.loads(pg.ev(
                "JSON.stringify([...document.querySelectorAll('#cta button')]"
                ".map(b=>[b.dataset.a,b.dataset.to||'',b.textContent.trim()]))") or '[]')
            bad = []
            tos = [str(x[1]) for x in acts if x[0] == 'goto']
            mw = re.search(r'第\s*(\d+)\s*步', why)
            if mw and tos and mw.group(1) not in tos:
                bad.append(f'正文说第 {mw.group(1)} 步，按钮去第 {"/".join(tos)} 步')
            chk(f'第 {n} 步正文与按钮目标同源', not bad,
                '; '.join(bad) or (why[:46] if why else '（无正文）'))

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
        # 画布也得换纸色：只换 body 的话，米色纸面会盖在暖墨底上（§137 型假绿）。
        chk('夜读时纸面遮罩也换成暖墨（不是只在 body 上变色）',
            (pg.ev("__probe.bg().paper") or '') == '23,21,18' and
            abs((pg.ev("__probe.bgAlpha(800,420)") or 0) - 240) <= 2,
            str(pg.ev("__probe.bg().paper")) + ' / alpha=' +
            str(pg.ev("__probe.bgAlpha(800,420)")))
        pg.ev("document.getElementById('bSea').click()")
        time.sleep(0.4)

        print('\n── 窄屏 ───────────────────────────────────────')
        pg.size(1000, 800)
        pg.go(url, 2.6)
        for _ in range(12):
            if (pg.ev("typeof LOADED!=='undefined'&&LOADED") or False):
                break
            time.sleep(0.5)
        # 窄屏这段要看「查看中」的提示条，所以必须切到一个**非待办**步骤。
        # 待办是哪一步随数据变（§157 修完指纹后可能是第 1 步也可能是第 5 步），
        # 写死切第 5 步会在"待办正好是 5"时测不到提示条 ⇒ 假红。
        work_n = pg.ev("__probe.work()") or 1
        view_n = 5 if work_n != 5 else 1
        pg.ev(f"document.querySelectorAll('.snode')[{view_n-1}].click()")
        time.sleep(0.5)
        chk('右栏折成底部横排',
            pg.ev("getComputedStyle(document.querySelector('.steps')).flexDirection") == 'row')
        chk('进度线不再横穿步骤文字',
            pg.ev("getComputedStyle(document.querySelector('.steps .track')).display") == 'none')
        chk('窄屏无横向溢出',
            bool(pg.ev("document.documentElement.scrollWidth<=innerWidth")))
        chk(f'窄屏首屏能看到「查看中」提示（当前看第 {view_n} 步，待办第 {work_n} 步）',
            bool(pg.ev("(()=>{const e=document.getElementById('viewnote');"
                       "const r=e.getBoundingClientRect();"
                       "return !e.hidden && r.top>=0 && r.bottom<=innerHeight})()")),
            pg.ev("JSON.stringify((()=>{const e=document.getElementById('viewnote');"
                  "const r=e.getBoundingClientRect();return [e.hidden,r.top,r.bottom,innerHeight]})())"))
        chk('窄屏首屏能看到本步主按钮（不用先滚动）',
            bool(pg.ev("(()=>{const b=document.querySelector('#cta .pact');"
                       "if(!b) return false; const r=b.getBoundingClientRect();"
                       "return r.top>=0 && r.bottom<=innerHeight})()")))
        pg.shot('narrow.png')

        print('\n── 版本自检（长驻旧标签页）───────────────────────')
        # 2026-10-17 22:45：用户对着"已跑完 05 / 去第 5 步"的旧界面反复问，
        # 因为那个标签页从服务重启前就一直开着（no-store 只管刷新，不管"没刷新"）。
        # 这里用 `/?asbuild=...` 让服务下发一份"内联 build 是假的"的页面，走真实代码路径。
        srv_build = pg.ev("window.__probe.state().build")
        pg.size(1600, 1000)
        pg.go(f'http://127.0.0.1:{PANEL_PORT}/?asbuild=deadbeef0000', wait=4.0)
        chk('旧版本页面会自己刷到最新版',
            pg.ev("MY_BUILD") == srv_build and srv_build,
            f'页面 {pg.ev("MY_BUILD")} vs 服务 {srv_build}')
        chk('自刷后回到规范 URL（不带 asbuild，否则会自己刷成死循环）',
            (pg.ev("location.search") or '') == '',
            pg.ev('location.href'))
        chk('自刷后样式与骨架完好（不是裸 HTML）',
            pg.ev("document.querySelectorAll('.snode').length") == 5 and
            bool(pg.ev("getComputedStyle(document.body).backgroundColor")),
            'snode=%s bg=%s' % (pg.ev("document.querySelectorAll('.snode').length"),
                                pg.ev("getComputedStyle(document.body).backgroundColor")))
        chk('自刷后给用户一句确认，而不是静默换脸',
            '自动刷新' in (pg.ev("document.getElementById('warn').textContent") or ''),
            pg.ev("document.getElementById('warn').textContent"))
        pg.go(url, wait=2.4)

        # ── 背景选择跨刷新保留（自定义图片走 localStorage 这条真实路径）──────
        print('\n── 背景选择跨刷新 ─────────────────────────────')
        pg.ev("__probe.bgImg(" + repr(TINY_PNG).replace("'", '"') + ")")
        time.sleep(0.3)
        bgc = pg.ev("__probe.bg()") or {}
        chk('自定义图片能换上去（is-photo + data URL 落 localStorage）',
            bool(bgc.get('photo')) and bool(pg.ev("localStorage.getItem('panel.bgimg')")),
            str(bgc.get('art')))
        pg.go(url, wait=3.0)
        for _ in range(12):
            if pg.ev("typeof LOADED!=='undefined'&&LOADED"):
                break
            time.sleep(0.5)
        bgc2 = pg.ev("__probe.bg()") or {}
        chk('刷新后自定义图片仍生效（不是刷新就回默认）',
            bool(bgc2.get('photo')) and (bgc2.get('art') or '') == 'custom',
            str(bgc2.get('art')))
        pg.ev("localStorage.removeItem('panel.bgimg');__probe.bgChoose('logbook')")
        time.sleep(0.35)
        chk('「恢复默认」回到航路版画',
            (pg.ev("__probe.bg().preset") or '') == 'logbook',
            str(pg.ev("__probe.bg().preset")))

        # ── 系统「减少动态效果」：擦除必须停用（不是只在 CSS 里 respect）──────
        print('\n── 减少动态效果 ───────────────────────────────')
        pg.cmd('Emulation.setEmulatedMedia',
               {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
        pg.go(url, wait=3.0)
        for _ in range(12):
            if pg.ev("typeof LOADED!=='undefined'&&LOADED"):
                break
            time.sleep(0.5)
        pa0 = pg.ev("__probe.bgAlpha(800,420)")
        for k in range(10):
            pg.cmd('Input.dispatchMouseEvent',
                   {'type': 'mouseMoved', 'x': 500 + k * 22, 'y': 560})
            time.sleep(0.012)
        time.sleep(0.15)
        chk('系统「减少动态效果」下擦除停用（不是只在 CSS 里 respect）',
            not (pg.ev("__probe.bg().raf") or False) and
            abs((pg.ev("__probe.bgAlpha(800,420)") or 0) - pa0) <= 1,
            str(pg.ev("__probe.bgAlpha(800,420)")))
        pg.cmd('Emulation.setEmulatedMedia', {'features': []})

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
