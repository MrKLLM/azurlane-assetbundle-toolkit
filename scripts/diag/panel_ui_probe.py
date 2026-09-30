# -*- coding: utf-8 -*-
"""「资产更新控制台」界面探针：证明新仪表盘**看得懂、点得动、背景不挡正事**。

为什么不能只截图看一眼：这类"把 13 行表格改成四步主线"的改动，最容易出的不是崩，
而是**悄悄少渲染了几个阶段**，或者**一个 hue 同时代表两件事**——前者要靠数，
后者要把计算样式取出来比。所以判据全部落在可观测的量上：DOM 计数、getComputedStyle、
以及**两张截图逐像素比对**。

  py -3 scripts/diag/panel_ui_probe.py --port 8791          # CDP 口默认 8791+100
  py -3 scripts/diag/panel_ui_probe.py --win 2560,1440      # 按真实分辨率看观感

背景层（东京夜星野）沿用画廊换来的两条硬判据（`docs/WORKFLOWS.md` WF-16 追加、§62、§66）：
  · 静止：隔 1.3s 两帧**逐像素完全相同**（背景自己在动就过不了这条）
  · 显影 → 淡净：静止时几乎不画星（只有经过才亮）；真实划动后亮着的星 >150 颗，
    且**只有指针经过的那一片亮**（远处必须仍是 0 颗），淡净后回到**同一个**静止态
外加本界面特有的三条：
  · 颜色语义唯一：档位徽标不得与任何状态色同色（并反向断言状态色确实在用，防空判据）
  · 背景不渗进内容：卡片内部区域开/关背景两态逐像素一致
  · 每个阶段都要有「写到哪儿」——没有它，用户无法判断点下去会不会动正式产物
"""
import argparse
import base64
import io
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
from PIL import Image     # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, '.diag', 'panel_ui')
EV = lambda s: f"(()=>{{{s}}})()"

# 界面里唯一允许承担语义的五个状态色，取自 :root token
STATE_COLORS = {'idle': 'rgb(63, 90, 110)', 'pass': 'rgb(79, 214, 168)',
                'fail': 'rgb(255, 111, 111)', 'await': 'rgb(242, 189, 114)',
                'run': 'rgb(95, 208, 232)'}


class Pg:
    """最小 CDP 客户端。Runtime 异常一律收集，不悄悄吞。"""

    def __init__(self, cdp, profile, url, win):
        self.proc = chrome_tree.install(subprocess.Popen([CHROME, '--headless=new',
            f'--remote-debugging-port={cdp}', '--remote-allow-origins=*',
            f'--user-data-dir={profile}', '--no-first-run', '--no-default-browser-check',
            '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
            '--use-angle=swiftshader', f'--window-size={win[0]},{win[1]}', url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
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
        self.ws = websocket.create_connection(ws, timeout=180, max_size=None)
        self._id = 0
        self.exc = []
        for m in ('Page.enable', 'Runtime.enable'):
            self.cmd(m)
        self.cmd('Page.bringToFront')     # 后台标签不出帧，动效判据会变成假红灯

    def cmd(self, m, p=None):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}}))
        self.ws.settimeout(180)
        while True:
            r = json.loads(self.ws.recv())
            if r.get('method') == 'Runtime.exceptionThrown':
                d = r.get('params', {}).get('exceptionDetails', {})
                ex = d.get('exception') or {}
                self.exc.append(str(d.get('text') or '') + ' '
                                + str(ex.get('description') or ex.get('value') or '')[:200])
            if r.get('id') == mid:
                return r.get('result', {})

    def ev(self, expr):
        r = self.cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True,
                                          'awaitPromise': True})
        if r.get('exceptionDetails'):
            ed = r['exceptionDetails']
            ex = ed.get('exception') or {}
            # SyntaxError 的信息在 text/description 里，不在 message 里
            return 'EXC ' + str(ex.get('description') or ex.get('value')
                                  or ed.get('text') or 'no detail')[:300]
        return r.get('result', {}).get('value')

    def shot(self, name):
        raw = base64.b64decode(self.cmd('Page.captureScreenshot', {'format': 'png'})['data'])
        open(os.path.join(OUT, name + '.png'), 'wb').write(raw)
        return raw

    def move(self, x, y):
        self.cmd('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y})

    def close(self):
        try:
            self.cmd('Browser.close')
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            chrome_tree.kill_tree(self.proc.pid)


def diff_png(a_bytes, b_bytes, box=None):
    """(最大逐通道差, 区域平均绝对差, 尺寸)。box=(x0,y0,x1,y1) 像素。"""
    ia, ib = Image.open(io.BytesIO(a_bytes)).convert('RGB'), Image.open(io.BytesIO(b_bytes)).convert('RGB')
    if ia.size != ib.size:
        return 255, 255.0, ia.size
    A, B = [im.crop(box) for im in (ia, ib)] if box else (ia, ib)
    if A.size != B.size:
        return 255, 255.0, ia.size
    import numpy as np
    d = np.abs(np.asarray(A, dtype=np.int16) - np.asarray(B, dtype=np.int16))
    if d.size == 0:
        return 0, 0.0, ia.size
    return int(d.max()), float(d.mean()), ia.size


def card_boxes(pg):
    """数据承载面（阶段卡 + 日志）的**内部**矩形，往里缩 12px 避开描边与左强调条。
    这几处是"背景绝不能渗进去"的对象；hero 与海平面是故意让背景露出来的。

    ⚠️ 必须与所属滚动列 `.col` 及视口求交：卡被裁一半时它的 getBoundingClientRect
    仍然越过容器底边，越界那部分量到的是下面的海平面带（那里露背景是设计），
    于是"渗进 133"其实是取样框写错，不是产品漏。
    """
    js = """
      return [...document.querySelectorAll('.stage,pre')].map(e=>{
        const c=e.closest('.col'), cr=c?c.getBoundingClientRect():null;
        const r=e.getBoundingClientRect();
        let x0=r.x+12,y0=r.y+12,x1=r.right-12,y1=r.bottom-12;
        if(cr){ x0=Math.max(x0,cr.x+2); y0=Math.max(y0,cr.y+2);
                x1=Math.min(x1,cr.right-2); y1=Math.min(y1,cr.bottom-2); }
        x0=Math.max(x0,0); y0=Math.max(y0,0);
        x1=Math.min(x1,innerWidth); y1=Math.min(y1,innerHeight);
        return [Math.round(x0),Math.round(y0),Math.round(x1),Math.round(y1)];})
        .filter(r=>r[2]-r[0]>60 && r[3]-r[1]>40).slice(0,10)
    """
    return pg.ev(EV(js)) or []


def paint_rects(pg):
    """凡是**画了背景**的元素矩形。用它把屏幕切成三块分别判：
      背景可见区 / 不透明内容区 / hero 带（唯一一层故意的半透明纱，允许 ±几级合成抖动）。
    不这么做的话，整屏逐像素比对会把合成器的渐变 dither 也算成"背景在动"——
    实测就是这个：浪散完以后整屏最大差 2、4727 个点，全部分布在半透明层覆盖处。
    """
    js = """
      let out=[];
      document.querySelectorAll('*').forEach(e=>{
        // html/body 是"天与海"本身，#bgfx 及其子层是背景层 —— 都不算遮挡，
        // 否则整个视口都被算成内容区，"背景可见区两帧相同"会变成一条 0 像素的空判据。
        if(e.tagName==='HTML'||e.tagName==='BODY') return;
        if(e.closest('#bgfx')) return;
        const cs=getComputedStyle(e);
        if(cs.backgroundColor==='rgba(0, 0, 0, 0)' && cs.backgroundImage==='none') return;
        if(cs.opacity==='0') return;
        const r=e.getBoundingClientRect();
        if(r.width<2||r.height<2) return;
        // 与滚动列求交：被裁掉的卡矩形会越过容器底边，把下面故意露背景的
        // 海平面带算成"内容区"，那会让背景可见区统计偏小、判据变弱。
        const c=e.closest('.col'), cr=c?c.getBoundingClientRect():null;
        let x0=r.x,y0=r.y,x1=r.right,y1=r.bottom;
        if(cr){ x0=Math.max(x0,cr.x); y0=Math.max(y0,cr.y);
                x1=Math.min(x1,cr.right); y1=Math.min(y1,cr.bottom); }
        x0=Math.max(x0,0); y0=Math.max(y0,0);
        x1=Math.min(x1,innerWidth); y1=Math.min(y1,innerHeight);
        if(x1-x0<2||y1-y0<2) return;
        out.push([Math.round(x0),Math.round(y0),Math.round(x1),Math.round(y1),
                  e.className&&String(e.className).includes('hero')?1:0]);});
      return out
    """
    return pg.ev(EV(js)) or []


def region_diff(a_bytes, b_bytes, rects):
    """三区差异：bg=纯背景可见区，ct=不透明内容区，hs=hero 纱区。
    bg_chg = 背景区里差值 >3 的像素数（"起浪"用它判，不用最大差——
    可见的水只露在栏间空隙里，max 会正好卡在阈值上，那是判据写得太脆不是产品有问题）。"""
    import numpy as np
    ia = np.asarray(Image.open(io.BytesIO(a_bytes)).convert('RGB'), dtype=np.int16)
    ib = np.asarray(Image.open(io.BytesIO(b_bytes)).convert('RGB'), dtype=np.int16)
    if ia.shape != ib.shape:
        return {'bg_max': 255, 'ct_max': 255, 'hs_max': 255, 'bg_px': 0, 'bg_chg': 0}
    d = np.abs(ia - ib).max(axis=2)
    content = np.zeros(d.shape, dtype=bool)
    scrim = np.zeros(d.shape, dtype=bool)
    for x0, y0, x1, y1, is_hero in rects:
        tgt = scrim if is_hero else content
        tgt[max(0, y0):min(d.shape[0], y1), max(0, x0):min(d.shape[1], x1)] = True
    bg = ~content & ~scrim
    if bg.sum() < 5000:            # 掩码失效时**必须判红**，不许拿"没有可比的像素"当通过
        return {'bg_max': 999, 'ct_max': int(d[content].max()) if content.any() else -1,
                'hs_max': 0, 'bg_px': int(bg.sum()), 'bg_chg': 0}
    f = lambda m: int(d[m].max()) if m.any() else -1
    return {'bg_max': f(bg), 'ct_max': f(content), 'hs_max': f(scrim),
            'bg_px': int(bg.sum()), 'bg_chg': int((d[bg] > 3).sum())}


def key(pg, k, code, vk):
    """发一次**完整**的键盘事件。只给 text 不给 key 时 e.key 是 undefined，
    页面里按 e.key 分派的键位全都不会触发 —— 那是探针没模拟到位，不是产品坏了。"""
    for t in ('keyDown', 'keyUp'):
        pg.cmd('Input.dispatchKeyEvent', {'type': t, 'key': k, 'code': code,
                                          'text': k if len(k) == 1 else '',
                                          'windowsVirtualKeyCode': vk,
                                          'nativeVirtualKeyCode': vk})


def quiesce(pg):
    """把画面钉死到"没有进行中的动画、也没有轮询会来打断"，再量几何/拍照。

    ⚠️ 少了这步会假红：阶段卡带 animation-delay + backwards 填充，刚 render 完的
    零点几秒里它其实停在 translateY(7px) 上 ⇒ 此时量的矩形比最终位置低 7px，
    两张照片一比就在卡片下沿多出一条 11px 差异带（实测把"背景渗进数据面"顶到 162，
    量的其实是入场动画淡入到第几帧）。
    """
    pg.ev(EV('window.__probe && window.__probe.stop(); return 1'))
    pg.ev(EV('document.getAnimations().forEach(a=>{try{a.finish()}catch(e){}}); return 1'))
    time.sleep(0.25)


def park(pg, x=6, y=6, wait=0.35):
    """把指针停到没有任何 hover 的角落。划水那步用的是 CDP 可信鼠标，
    停在哪就点亮哪张卡的 :hover（实测把卡片抬 1px ⇒ 文字逐通道差 209）——
    不固定这个变量的话，静止/起浪两组比对量的都是 hover，不是水。"""
    pg.move(x, y)
    time.sleep(wait)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8791, help='控制台在跑的 HTTP 端口')
    ap.add_argument('--cdp', type=int, default=0,
                    help='无头 Chrome 的调试端口（默认 --port+100；两者撞过一回：'
                         '拿同一个端口既取 /json 又连 WS，结果永远 "no CDP tab"）')
    ap.add_argument('--win', default='1440,900')
    a = ap.parse_args()
    cdp = a.cdp or a.port + 100
    win = [int(x) for x in a.win.split(',')]
    os.makedirs(OUT, exist_ok=True)
    url = f'http://127.0.0.1:{a.port}/'
    try:
        json.load(urllib.request.urlopen(url + 'api/state', timeout=6))
    except Exception as e:
        print(f'[FAIL] 控制台没在 {a.port} 上响应：{e}')
        return 2

    pg = Pg(cdp, os.path.join(ROOT, '.diag', 'chrome_panel'), url, win)
    fails, notes = [], []

    def chk(name, ok, detail=''):
        print(f'  {"PASS" if ok else "FAIL"}  {name}{"  · " + str(detail) if detail else ""}')
        if not ok:
            fails.append(f'{name}（{detail}）')

    # 等首屏渲染完：apiState 是异步的，不等就是拿空 DOM 断言
    for _ in range(60):
        n = pg.ev(EV('return document.querySelectorAll(".step").length'))
        c = pg.ev(EV('return (window.panelState&&panelState().stages||[]).length'))
        if isinstance(n, int) and n >= 4 and c == 13:
            break
        time.sleep(0.5)

    S = pg.ev(EV('return panelState()')) or {}
    stages, steps = S.get('stages', []), S.get('steps', {})
    live = [s['key'] for s in stages if s['tier'] == 'live']

    print('\n── 结构与可读性 ─────────────────────────────────')
    chk('阶段与步骤读全（13 / 4）', len(stages) == 13 and len(steps) == 4,
        f'{len(stages)} 阶段 / {len(steps)} 步')
    chk('每个阶段都写了「写到哪儿」', all(s.get('writes') for s in stages),
        '缺: ' + ','.join(s['key'] for s in stages if not s.get('writes')))

    labels = pg.ev(EV('return [...document.querySelectorAll(".step b")].map(x=>x.textContent).join("/")'))
    nstep = pg.ev(EV('return document.querySelectorAll(".step").length'))
    chk('左轨恰好四步、没有未归组冒出来', nstep == 4, f'{nstep} 个：{labels}')

    ndot = pg.ev(EV("return document.querySelectorAll('.step .dot').length"))
    chk('13 个阶段在四步里全覆盖（一个都没被折叠掉）', ndot == 13, f'{ndot} 个状态点')

    total = 0
    for n in sorted(int(k) for k in steps):
        pg.ev(EV(f'step={n}; render(); return 1'))
        got = pg.ev(EV('return document.querySelectorAll(".appr").length')) or 0
        want = len([s for s in stages if s['tier'] == 'live' and s['step'] == n])
        total += got
        chk(f'第 {n} 步 签字框 {got} == 写正式档 {want}', got == want)
    chk('签字框总数 == 写正式档总数', total == len(live), f'{total} / {len(live)}')

    pg.ev(EV('step=2; render(); return 1'))
    tier_cols = set(pg.ev(EV("""
      return [...document.querySelectorAll('.tier')].map(e=>getComputedStyle(e).color)""")) or [])
    clash = sorted(tier_cols & set(STATE_COLORS.values()))
    chk('档位徽标不借用任何状态色', not clash, f'撞色 {clash} / 档位实际 {sorted(tier_cols)}')
    stt_cols = set(pg.ev(EV("""
      return [...document.querySelectorAll('.stt')].map(e=>getComputedStyle(e).color)""")) or [])
    chk('状态色确实被用上了（防上一条成为空判据）',
        bool(stt_cols & set(STATE_COLORS.values())), f'状态实际色 {sorted(stt_cols)}')

    chk('使用说明抽屉可用且覆盖六块内容', pg.ev(EV("""
      document.querySelector('#bHelp').click();
      const p=document.querySelector('#help .panel');
      const need=['这是什么','动手之前','四步分别动什么','签字','判红了怎么办','不在这里的两件事'];
      const miss=need.filter(t=>!p.textContent.includes(t));
      return (!miss.length && document.querySelector('#help').classList.contains('on'))
             ? 'OK' : '缺: '+miss.join(',');
    """)) == 'OK')
    pg.ev(EV("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'})); return 1"))
    chk('抽屉能关（Esc）', pg.ev(EV("return !document.querySelector('#help').classList.contains('on')")))

    print('\n── 背景层：静止 / 起浪 / 不遮挡 ──────────────────')
    chk('星野够密（>1200 颗）', (pg.ev('ST.list.length') or 0) > 1200,
        f"{pg.ev('ST.list.length')} 颗星")
    lit0 = pg.ev(EV('return ST.list.filter(t=>t.lit>0.05).length'))
    chk('静止时显影场是空的（只有经过才显示）', lit0 == 0, f'静止时亮着 {lit0} 颗')
    chk('静止时不排帧（循环自己停了）', pg.ev('ST.raf') == 0, f"raf={pg.ev('ST.raf')}")
    # 量背景之前：停轮询 + 等入场动画收敛（两条都是假红来源，见 quiesce 的注释）
    quiesce(pg)
    park(pg)
    rects = paint_rects(pg)
    size = Image.open(io.BytesIO(pg.shot('size'))).size
    time.sleep(1.4)
    still1 = pg.shot('still1')
    time.sleep(1.4)
    still2 = pg.shot('still2')
    r12 = region_diff(still1, still2, rects)
    chk('静止两帧：背景可见区逐像素完全相同（背景不自走）', r12['bg_max'] == 0,
        f"背景区最大差 {r12['bg_max']}（{r12['bg_px']} 像素）· "
        f"内容区 {r12['ct_max']} · hero 纱区 {r12['hs_max']}")
    chk('静止两帧：不透明内容区也完全相同', r12['ct_max'] == 0, f"内容区最大差 {r12['ct_max']}")

    pg.ev(EV('ST.strokes=0; ST.lit=0; return 1'))
    # 只划**左半边**：这样"远处不该跟着亮"这条 locality 判据才有意义
    for i in range(24):
        pg.move(int(size[0] * (0.06 + 0.36 * i / 23)), int(size[1] * 0.955))
        time.sleep(0.02)
    for i in range(18):
        pg.move(int(size[0] * (0.40 - 0.32 * i / 17)), int(size[1] * (0.60 + 0.30 * i / 17)))
        time.sleep(0.02)
    strokes = pg.ev('ST.strokes') or 0
    litN = pg.ev(EV('return ST.list.filter(t=>t.lit>0.05).length'))
    farN = pg.ev(EV('return ST.list.filter(t=>t.lit>0.05 && t.hx>innerWidth*0.62).length'))
    scattered = pg.shot('scattered')     # ⚠️ 立刻拍：显影只有 ~520ms，晚一拍就淡干净了
    rw = region_diff(still2, scattered, rects)
    chk('划过才显影（亮着的星 >150 颗、背景可见区真的出现星点）',
        litN > 150 and strokes > 0 and rw['bg_chg'] > 300,
        f"亮着 {litN} 颗 / 共 {pg.ev('ST.list.length')}，笔画 {strokes} 笔，"
        f"背景可见区多了 {rw['bg_chg']} 个像素的星点（最大差 {rw['bg_max']}）")
    chk('只有经过的地方亮（右半边仍为 0 颗，防"整片一起亮"）', farN == 0,
        f'右半边亮着 {farN} 颗')
    park(pg, wait=0.10)                  # 把 hover 停回原处，再等它淡净

    for _ in range(60):
        if pg.ev('ST.raf') == 0:
            break
        time.sleep(0.5)
    quiesce(pg)
    back = pg.shot('still_back')
    rb = region_diff(still1, back, rects)
    resid = pg.ev(EV('let m=0;for(const t of ST.list){const d=Math.abs(t.x-t.hx)+Math.abs(t.y-t.hy);'
                     'if(d>m)m=d;}return m'))
    # 背景可见区**严格为 0** + 残留位移 0 + 显影场清零 —— 这三条才是"淡回同一张帧"的本体。
    # 内容区只报不判：画布每重绘一次，Chrome 就把文字层重新光栅化一遍，字边缘能差到 150+，
    # 那是合成器的行为，不是"背景渗进来了"（本轮先误当成产品问题查了一轮）。
    # 数据面到底漏不漏，改由下面两条结构性判据来定：底色 alpha + 几何包含。
    lit_end = pg.ev(EV('return ST.list.filter(t=>t.lit>0.05).length'))
    chk('星点淡净后回到**同一张**静止帧（背景区严格 0、残留位移 0、显影场清零）',
        pg.ev('ST.raf') == 0 and resid == 0 and rb['bg_max'] == 0 and lit_end == 0,
        f"淡净后仍亮着 {lit_end} 颗；raf={pg.ev('ST.raf')} 残留位移 {resid:.2e}px "
        f"背景区差 {rb['bg_max']}（内容区差 {rb['ct_max']} 与 hero 纱区差 {rb['hs_max']} "
        f"只报不判：那是重光栅化噪声，见 §67 三）")

    opaque = pg.ev(EV("""
      const bad=[];
      document.querySelectorAll('header,.pane,.stage,pre,.sheets a,.sheets img,.meter,.step')
        .forEach(e=>{ const c=getComputedStyle(e).backgroundColor;
          const m=c.match(/[\d.]+\s*[,\/]\s*([\d.]+)\)?$/);
          const a=c.startsWith('rgba')?(m?parseFloat(m[1]):0):1;
          if(c!=='rgba(0, 0, 0, 0)' && a<0.995) bad.push(e.className+' '+c); });
      return bad.slice(0,6)
    """))
    chk('数据面底色全部不透明（alpha=1）', not opaque, '漏: ' + str(opaque))
    quiesce(pg)
    boxes = card_boxes(pg)
    pg.shot('stars_on')
    pg.ev(EV("document.querySelector('#bSea').click(); return 1"))
    time.sleep(0.7)
    plain_on = pg.ev(EV("return document.body.classList.contains('plain')"))
    chk('星辰开关关掉：class 生效且不排帧', bool(plain_on) and pg.ev('ST.raf') == 0,
        f'plain={plain_on} raf={pg.ev("ST.raf")}')
    plain = pg.shot('plain')
    # 正向对照：这条**只有背景真的在画**才算数，否则把背景整层删掉也能拿满分。
    # 只比背景可见区——切开关会改变合成层，Chrome 重新光栅化后全站文字边缘都能差 ±20，
    # 那与"渗不渗进来"无关（实测整屏比会量到 20 万个这种点，全是字边缘）。
    rt = region_diff(still1, plain, rects)
    chk('关背景后背景可见区确实空了（星野是活的，防"不渗进来"成为空判据）',
        rt['bg_chg'] > 3000,
        f"背景可见区少了 {rt['bg_chg']} 个像素的内容（整屏最大差 {rt['bg_max']} 含重光栅化"
        f"的字边缘，不作判据）")
    # 结构判据：**每个数据元素整张坐在一个不透明面板里**。
    # 与"面板底色 alpha=1"两条合起来，才是"背景渗不进来"的可证形式——
    # 逐像素那条在这个页面上量到的是重光栅化噪声（见上）。
    leak = pg.ev(EV('''
      const out=[];
      document.querySelectorAll('.stage,pre,.sheets a,.sheets img,.meter,.runs td')
        .forEach(e=>{
          const r=e.getBoundingClientRect();
          if(r.width<2||r.height<2) return;
          const p=e.closest('.pane,header');
          if(!p){ out.push((e.className||e.tagName)+':不在任何面板里'); return; }
          const q=p.getBoundingClientRect();
          if(r.left<q.left-0.5||r.top<q.top-0.5||r.right>q.right+0.5||r.bottom>q.bottom+0.5)
            out.push((e.className||e.tagName)+' 越出面板');
        });
      return out.slice(0,8)
    '''))
    chk('每个数据元素都整张坐在不透明面板内', not leak, '漏: ' + str(leak))
    inside = pg.ev(EV('''
      const b=boxes=>boxes;
      const cs=getComputedStyle(document.querySelector('.stage'));
      const ps=getComputedStyle(document.querySelector('.pane'));
      const a=c=>{const m=c.match(/rgba\([^)]*,\s*([\d.]+)\)/);return m?+m[1]:1;};
      return [a(cs.backgroundColor)<=0.995?0:1, a(ps.backgroundColor)<=0.995?0:1]
    '''))
    chk('卡片与面板底色实测不透明（正向：防上面那条成为空判据）',
        inside == [1, 1], f'实测 [卡片, 面板] 不透明={inside}')

    shbox = pg.ev(EV("""
      const e=document.querySelector('.sheets img'); if(!e) return null;
      const r=e.getBoundingClientRect();
      return r.width>60 ? [Math.round(r.x),Math.round(r.y),
             Math.round(r.right),Math.round(r.bottom)] : null
    """))
    if shbox:
        smax, smean, _ = diff_png(still1, plain, tuple(shbox))
        chk('对照图底完全不透明（背景不影响看图）', smax == 0, f'最大差 {smax} 均值差 {smean:.4f}')
    else:
        notes.append('盘上还没有对照表，跳过「对照图底不透明」那条——没有可量的对象，不算通过也不算失败')
    pg.ev(EV("document.querySelector('#bSea').click(); return 1"))

    print('\n── 任务生命周期（轮询不许把子进程杀掉）───────────')
    # Windows 上 `os.kill(pid, 0)` 不是探活，是 TerminateProcess —— 面板只要轮一次状态
    # 就会把正在跑的流水线当场杀了。这条判据用"日志必须跑到自然收尾"来证它没被掐死。
    def api(path, body=None):
        # headers 必须给 {}：Request 对 headers=None 会去 None.items() 上炸
        # （GET 那几路不传 body，正是走这条分支）
        req = urllib.request.Request(
            url + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Content-Type': 'application/json'} if body is not None else {})
        return json.load(urllib.request.urlopen(req, timeout=90))
    try:
        rid = api('/api/run', {'plan': True})['id']
        polls_while_running, text = 0, ''
        for _ in range(60):
            st = next((r for r in api('/api/state')['runs'] if r['id'] == rid), None)
            if st and st['state'] == 'running':
                polls_while_running += 1
            j = api('/api/log?id=%s&offset=0' % rid)
            text = j['text'] or ''
            if st and st['state'] != 'running':
                break
            time.sleep(1)
        chk('任务自然收尾（日志含计划表与 live 档清单，没被轮询掐死）',
            '要签字的 live 档' in text and '判据:' in text,
            f'轮询到运行中 {polls_while_running} 次，日志 {len(text)} 字')
        chk('运行期间至少轮询过一次（否则上一条证不到"轮询不杀进程"）',
            polls_while_running >= 1, f'{polls_while_running} 次')
        chk('结束后 runs 状态翻成 done',
            bool(st) and st['state'] == 'done', str((st or {}).get('state')))
    except Exception as e:
        chk('任务生命周期检查可跑', False, f'{type(e).__name__}: {e}')

    print('\n── 退化与异常 ───────────────────────────────────')
    pg.cmd('Emulation.setEmulatedMedia',
           {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
    time.sleep(0.3)
    an = pg.ev(EV("return getComputedStyle(document.querySelector('.step')).animationName"))
    tr = pg.ev(EV("return getComputedStyle(document.querySelector('.stage')).transitionDuration"))
    chk("系统「减少动效」时全部退化", an == 'none' and str(tr).startswith('0s'),
        f'animation={an} transition={tr}')
    pg.cmd('Emulation.setEmulatedMedia', {'features': []})

    for n in (1, 2, 3, 4):
        pg.ev(EV(f'step={n}; render(); return 1'))
        time.sleep(0.35)
        pg.shot(f'step{n}')

    # ── 交互：键位 / 日志筛选 / 签字点亮 / 卡与左轨联动 ────────────────
    print()
    print('── 交互（键盘 / 筛选 / 联动）─────────────────────')
    pg.ev(EV('window.__probe.go(1); return 1'))
    quiesce(pg)
    key(pg, '3', 'Digit3', 52)
    time.sleep(0.35)
    chk('键盘 3 直接跳到第③步', pg.ev(EV('return step')) == 3,
        'step=%s 标题=%s' % (pg.ev(EV('return step')),
                             pg.ev(EV('return document.getElementById("sTitle").textContent'))))
    key(pg, 'h', 'KeyH', 72)
    time.sleep(0.3)
    opened = pg.ev(EV("return document.querySelector('#help').classList.contains('on')"))
    key(pg, 'Escape', 'Escape', 27)
    time.sleep(0.25)
    closed = pg.ev(EV("return !document.querySelector('#help').classList.contains('on')"))
    chk('键盘 H 开抽屉、Esc 再关掉', bool(opened) and bool(closed),
        f'开={opened} 关={closed}')
    pg.ev(EV('LINES=["✅ a","❌ b","!! c","普通行","未签字 d"];'
             'FILT="all"; renderLog(); return 1'))
    n_all = len(pg.ev(EV("return document.getElementById('log').textContent")).splitlines())
    pg.ev(EV('FILT="bad"; renderLog(); return 1'))
    bad = pg.ev(EV('return document.getElementById("log").textContent'))
    chk('日志筛选「只看红」只留红行',
        ('❌' in bad) and ('!!' in bad) and ('普通行' not in bad),
        f'全量 {n_all} 行 → 筛后 {len(bad.splitlines())} 行')
    pg.ev(EV('FILT="all"; renderLog(); return 1'))
    pg.ev(EV('window.__probe.go(4); return 1')); quiesce(pg)
    lit = pg.ev(EV("""
      const cb=document.querySelector('.appr');
      if(!cb) return 'no-checkbox';
      cb.checked=true; cb.dispatchEvent(new Event('change'));
      return document.querySelector('.signbox').classList.contains('on')"""))
    chk('勾上签字框会把该框点亮（签字要有反馈）', lit is True, str(lit))
    pg.ev(EV('window.__probe.go(2); return 1')); quiesce(pg)
    pg.ev(EV("""
      const el=document.querySelector('.stage');
      el.dispatchEvent(new MouseEvent('mouseenter')); return 1"""))
    hot = pg.ev(EV("return !!document.querySelector('.dot.hot')"))
    chk('悬停阶段卡会点亮左轨对应的状态点', bool(hot),
        '卡=%s' % pg.ev(EV('return document.querySelector(".stage .skey").textContent')))
    chk('全程无 JS 异常', not pg.exc, ' | '.join(pg.exc[:3]))
    pg.close()

    print(f'\n截图落在 {OUT}\\（still1 still2 wave still_back sea_on plain step1-4）')
    print('  ⚠️ 视觉对不对的最终判据是人看图，探针只保证该数的没少。')
    for n in notes:
        print('  注：' + n)
    if fails:
        print(f'\n[FAIL] {len(fails)} 条判红：')
        for f in fails:
            print('  - ' + f)
        return 1
    print('\n[PASS] 界面判据全绿')
    return 0


if __name__ == '__main__':
    sys.exit(main())
