# -*- coding: utf-8 -*-
"""「资产更新控制台」界面探针：证明新仪表盘**看得懂、点得动、背景不挡正事**。

为什么不能只截图看一眼：这类"把 13 行表格改成四步主线"的改动，最容易出的不是崩，
而是**悄悄少渲染了几个阶段**，或者**一个 hue 同时代表两件事**——前者要靠数，
后者要把计算样式取出来比。所以判据全部落在可观测的量上：DOM 计数、getComputedStyle、
以及**两张截图逐像素比对**。

  py -3 scripts/diag/panel_ui_probe.py --port 8791          # CDP 口默认 8791+100
  py -3 scripts/diag/panel_ui_probe.py --win 2560,1440      # 按真实分辨率看观感

背景层已换成「夜航星野」：**常驻 + 三层极慢视差漂移**，并且是**状态面**（信标列 + 判绿荡波）。
这直接推翻了旧契约里"静止时零个动画、两帧逐像素相同"那三条护栏，换成四条新的
（每条都能单独红，也都能解释为什么它替代了旧的哪一条）：

  · 旧「静止两帧逐像素相同」→ 新 **常驻 + 漂移有界且慢**：不碰鼠标天也在动（t 推进、
    星点真的位移），但实测位移 ≤ DRIFT 上限×Δt + 0.6px，且配置速度 ≤2px/s、自绘限流 ≤30 帧。
    旧判据在"漂移常开"下**必然**红，它保护的其实是"背景不许自己走"这个已作废的设计意图。
  · 旧「静止时几乎不画星（只有经过才亮）」→ 新 **避让生效且非空判据**：落在主屏文字矩形
    里的星**一颗都没画**（`v==0`），矩形外的星**一颗都没被误杀**。后半句是关键 ——
    没有它，"把整片天关掉"也能冒充避让。
  · 旧「淡净后回到同一个静止态」→ 新 **冻结态可复现**：`__probe.freeze(true)` 后 t 停推进、
    指针提亮停用，隔 1.4s 两帧**整屏逐像素相同**。逐像素比对全部改在冻结 + `tAt(固定相位)`
    下做，否则量到的是漂移相位差（本轮实测假红 150 级）。
  · 新增 **天是状态面**：信标列对准当前步节点、其正上方星点亮度均值 > 全屏均值 1.25 倍；
    某阶段从"非绿"翻成"绿" ⇒ 从信标处荡开一圈波。

光效也从"边框绕一圈跑光 + 磁吸"换成"指针携光"（棱边光 + 光晕），判据跟着换：
  · 悬停控件 → **离指针最近的那条边**亮起 1px，且指针从控件上沿移到下沿时棱边跟着换向
  · 离开即收净，冻结背景下"划过一圈再离开"必须回到同一张帧
  · **装饰不进数据面**：日志 `pre` 不挂棱边光；`#pool` 的 z-index 必须低于 `.app`
    （结构性保证：不透明面板天然吃不到光）
  · M 键 = 光效整层停用 **且背景冻结**（"从简"= 屏幕上一个东西都不再动）

其余保留：颜色语义唯一（档位徽标不得与状态色同色，并反向断言状态色确实在用）、
面板/卡片色相必须落在海军蓝带（200~240°，不是薰衣草 250~330°）、
chrome 零外投影、零渐变、小标签不全大写、
每个阶段都有「写到哪儿」、**静止不闪**（带着 8 秒轮询跨一次 tick，在冻结相位下整屏逐像素
相同、节点不被重建、`getAnimations()==0`；这一条**不许**先 stop() 再比 —— 上一版就是那样
把闪屏验没的）、背景不渗进内容。
"""
import argparse
import base64
import io
import json
import math
import os
import re
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
                # 带上栈顶两帧：只报 message 的话，"undefined.toFixed" 这种
                # 根本定位不到是哪条弹簧的 apply 回调（本轮就卡过一次）。
                st = [f"{x.get('functionName','?')}:{x.get('lineNumber')}:{x.get('columnNumber')}"
                      for x in (d.get('stackTrace') or {}).get('callFrames', [])][:3]
                self.exc.append(str(d.get('text') or '') + ' '
                                + str(ex.get('description') or ex.get('value') or '')[:200]
                                + ('  << ' + ' <- '.join(st) if st else ''))
            if r.get('id') == mid:
                return r.get('result', {})

    def ev(self, expr):
        r = self.cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True,
                                          'awaitPromise': True})
        if r.get('exceptionDetails'):
            ed = r['exceptionDetails']
            ex = ed.get('exception') or {}
            # SyntaxError 的信息在 text/description 里，不在 message 里
            msg = str(ex.get('description') or ex.get('value')
                      or ed.get('text') or 'no detail')[:300]
            # ⚠️ 以前这里只往 self.exc 收 Runtime.exceptionThrown **事件**，
            # 但 Runtime.evaluate 抛错时错误是在**响应里**回来的、不发事件 ——
            # 于是「全程无 JS 异常」对一个真实的 TypeError 放了绿灯（假绿灯）。
            # 探针自己调出来的异常必须同样计入。
            self.exc.append('ev: ' + msg)
            return 'EXC ' + msg
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


def _count_above(a_bytes, b_bytes, thr):
    """逐通道差 > thr 的**像素个数**。用于把"合成器 dither 的 ±1~2"和"真的留痕"分开判，
    而不是把最大差阈值一路放宽到失去意义。"""
    import numpy as np
    ia = np.asarray(Image.open(io.BytesIO(a_bytes)).convert('RGB'), dtype=np.int16)
    ib = np.asarray(Image.open(io.BytesIO(b_bytes)).convert('RGB'), dtype=np.int16)
    if ia.shape != ib.shape:
        return -1
    return int((np.abs(ia - ib).max(axis=2) > thr).sum())


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



def _wait_det(pg, want, timeout=14):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pg.ev(EV("return document.querySelector('#detail').classList.contains('on')")) == want:
            return True
        time.sleep(0.2)
    return False


def open_detail(pg, wait=0.6):
    """打开「细节」抽屉。抽屉是 display:none 的覆盖层 —— **关着的时候里面所有元素
    getBoundingClientRect() 全是 0**，凡是量几何的判据都必须先开它，否则会拿到
    "没有可量的对象"式的假绿灯。"""
    pg.ev(EV("window.__probe && __probe.det(true); return 1"))
    ok = _wait_det(pg, True)
    time.sleep(wait)
    if not ok:
        print('  FAIL  抽屉没能打开（后面的判据全部失去前提）')
    return pg.ev(EV("return document.querySelectorAll('#detail .stage').length"))


def close_detail(pg, wait=0.5):
    pg.ev(EV("window.__probe && __probe.det(false); return 1"))
    # ⚠️ 这里以前只 sleep(0.5)：关抽屉是弹簧推出去的，0.5s 内没到位就往下量，
    #    那层 position:fixed;inset:0 且带 backdrop-filter 的遮罩还盖着整屏 ——
    #    "背景可见区"被算成 0 像素（region_diff 拿 999 判红）、帧率被拖垮、
    #    划动全被 250ms 阈值判成瞬移（实测笔画从 41 掉到 4）。必须轮询到真的关了。
    ok = _wait_det(pg, False)
    time.sleep(wait)
    if not ok:
        print('  FAIL  抽屉没能关闭（遮罩还在屏上，背景判据失去前提）')

def settle(pg, timeout=25, freeze=True):
    """等弹簧停机；`freeze=True` 时再把**星野钉住**。

    ⚠️ 旧契约里"静止" == `ST.raf==0`（显影式星野会自己淡净、循环自己停）。新契约
    （B2 漂移常开）里 `ST.raf` **永不归零**，那条判据必然红 —— 它保护的是"背景不许自己走"
    这个已作废的设计意图。现在"静止"由 `__probe.freeze(true)` 定义：t 停推进 + 指针提亮
    停用 ⇒ 整帧可复现。冻结本身可不可复现，另由 `frozen_pair()` 逐像素验。
    """
    t0 = time.time()
    springs_ok = False
    while time.time() - t0 < timeout:
        if (pg.ev(EV('return __probe.live()')) or 0) == 0:
            springs_ok = True
            break
        time.sleep(0.3)
    if freeze:
        pg.ev(EV('__probe.freeze(true); return 1'))
    time.sleep(0.4)
    return springs_ok and (not freeze or pg.ev('ST.frozen') is True)


def pin_sky(pg, t=0.0):
    """冻结星野 + 把相位钉到 `t`，再画一帧。

    两件事缺一不可：只冻结，两次冻结落在不同相位上，跨段比对仍会差一整片天；
    只钉相位，t 会继续推进，下一次 draw 就把相位冲掉。所有跨段的逐像素比对都必须先走这里。
    """
    pg.ev(EV('__probe.freeze(true); return 1'))
    pg.ev(EV(f'return __probe.tAt({t})'))
    time.sleep(0.35)


def frozen_pair(pg, gap=1.4):
    """冻结态下隔 `gap` 秒拍两帧，返回 (整屏最大差, >8 级的像素数)。
    这是"冻结可复现"的本体判据 —— 它替代了旧版"淡净后回到同一个静止态"。"""
    a = pg.shot('frozen_a')
    time.sleep(gap)
    b = pg.shot('frozen_b')
    mx, _, _ = diff_png(a, b)
    return mx, _count_above(a, b, 8)


def drift_sample(pg, dt=0.9):
    """解冻后隔 `dt` 秒采两次星位，返回 (实际耗时, Δt, Δ帧数, 每颗星位移列表)。

    这是「常驻 + 漂移有界且慢」的本体判据 —— 它替代了旧版"静止时零个动画、两帧逐像素相同"。
    旧判据保护的是"背景不许自己走"，而 B2 方向明确要它走；能守的只剩"走得多快、有没有真的在走"。
    """
    pg.ev(EV('__probe.freeze(false); return 1'))
    t0 = time.time()
    a = pg.ev(EV('return {t:ST.t,f:ST.frames,p:ST.list.map(s=>[s.x,s.y])}'))
    time.sleep(dt)
    b = pg.ev(EV('return {t:ST.t,f:ST.frames,p:ST.list.map(s=>[s.x,s.y])}'))
    el = time.time() - t0
    if not isinstance(a, dict) or not isinstance(b, dict):
        return el, 0.0, 0, []
    disp = [math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(a['p'], b['p'])]
    return el, b['t'] - a['t'], b['f'] - a['f'], disp


def hue_of(rgb):
    """把 getComputedStyle 的 rgb()/rgba() 串换成色相（度）。取不到返回 None。

    为什么不用旧的"通道极差 ≤8"：那条是上一轮"去薰衣草"时立的，判的是**中性**。
    现在版面故意走海军蓝（215° 一带），通道极差天然 >20 ⇒ 旧判据必红。
    要守的规则其实没变（"别拿薰衣草当卡片填充"），只是改判**色相落在哪条带**：
    海军蓝 200~240° 通过，薰衣草/紫 250~330° 红。
    """
    v = [int(x) for x in re.findall(r'\d+', rgb or '')][:3]
    if len(v) != 3:
        return None
    r, g, b = [x / 255 for x in v]
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return 0.0
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60


def edge_axis(bg):
    """`#fxedge` 的 background 里那道光的**走向**：'h'=横着一条（贴上/下棱）、
    'v'=竖着一条（贴左/右棱）。读不出返回 None。

    为什么只看走向、方向去读 `__probe.fx().k`：`k` 是页面自己算出的"最近棱"，
    单独信它等于让被测者给自己判分；而只看 CSS 又要去猜 Chrome 的 shorthand 序列化格式。
    两条配对用最稳：**一个说方向，一个说画出来的走向，必须自洽** ——
    不自洽就说明"逻辑判上边、画出来是左边"这类错位真的发生了。
    """
    m = re.search(r'radial-gradient\(\s*([\d.]+)px\s+([\d.]+)px', bg or '')
    if not m:
        return None
    rx, ry = float(m.group(1)), float(m.group(2))
    if rx == ry:
        return None
    return 'h' if rx > ry else 'v'


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
        n = pg.ev(EV('return document.querySelectorAll(".snode").length'))
        # S 在首屏要等 /api/state 算完指纹才有 —— 轮询期间 panelState() 返回 null 是**预期**，
        # 用可选链读，别让探针自己的表达式抛异常（那会被计入"页面有 JS 异常"）。
        c = pg.ev(EV('return (window.panelState&&panelState()?.stages||[]).length'))
        if isinstance(n, int) and n >= 4 and c == 13:
            break
        time.sleep(0.5)

    S = pg.ev(EV('return panelState()')) or {}
    stages, steps = S.get('stages', []), S.get('steps', {})
    live = [s['key'] for s in stages if s['tier'] == 'live']

    print(chr(10) + '── 主屏：一次只暴露下一步（抽屉关着量） ───────────')
    # 这一节必须在**抽屉关闭**时跑：主屏的全部意义就是"只回答一个问题"，
    # 抽屉一开就被证据盖住了。
    n_act = pg.ev(EV("return [...document.querySelectorAll('#cta button')]"
                     ".filter(b=>b.classList.contains('pact')).length"))
    n_pane = pg.ev(EV("return document.querySelectorAll('.now .pane').length"))
    ask_tx = pg.ev(EV("return document.querySelector('.ask').textContent.trim()"))
    chk('主屏只有一个实心行动（其余一律文字链）', n_act == 1, f'{n_act} 个主行动')
    chk('主屏上没有任何面板（证据全在抽屉里）', n_pane == 0, f'{n_pane} 个 .pane')
    chk('主屏有一句人话的现状', len(ask_tx) >= 6, f'「{ask_tx}」')
    asks = []
    for n in (1, 2, 3, 4):
        pg.ev(EV(f'window.__probe.go({n}); return 1')); time.sleep(0.12)
        asks.append(pg.ev(EV("return document.querySelector('.ask').textContent.trim()")))
    chk('四步各有一句不同的现状（不是一句套话复用四次）',
        len(set(asks)) == 4 and all(len(a) >= 6 for a in asks), ' | '.join(asks))
    pg.ev(EV('window.__probe.go(1); return 1')); time.sleep(0.15)

    # ★ 可读性不再靠"给文字蒙一层半透明纱"——实测 alpha .90 仍会被一颗星在字下面顶出
    #   36 级差异。新做法是**星野在文字区主动避让**：落在避让矩形里的星 `v` 直接归零。
    #   旧判据（"划过之后远处亮着 >150 颗、字底下 0 颗"）在常驻星野下失去意义 ——
    #   现在每颗星**一直都在画**，没有"划过才亮"这回事，`ST.strokes` 也一并作废。
    #   换成一对直接问 DOM 的判据：字底下一颗都没画，且矩形外的星一颗都没被误杀。
    #   后半句是关键 —— 没有它，"把整片天关掉"也能冒充避让。
    av = pg.ev(EV('return (ST.avoid||[]).length'))
    chk('主屏文字区登记了避让矩形', av >= 3, f'{av} 个')
    park(pg)
    settle(pg, timeout=12)                 # 冻结 + 重画一帧，下面读到的 v 才是当前帧的
    au = pg.ev(EV("""
      let inAv=0,inAvDrawn=0,out=0,outDark=0;
      for(const t of ST.list){ const a=inAvoid(t.x,t.y), d=t.v>0;
        if(a){inAv++; if(d)inAvDrawn++;} else {out++; if(!d)outDark++;} }
      return {total:ST.list.length,inAv:inAv,inAvDrawn:inAvDrawn,out:out,outDark:outDark}"""))
    chk('避让生效：落在主句矩形里的星**一颗都没画**，矩形外的星**一颗都没被误杀**',
        bool(au) and au['inAv'] > 0 and au['inAvDrawn'] == 0
        and au['out'] > 0 and au['outDark'] == 0, str(au))
    chk('避让区确实压在主句上（防避让矩形画在别处，成为空判据）',
        bool(pg.ev(EV("""const r=document.querySelector('.ask').getBoundingClientRect();
          return inAvoid(r.left+r.width/2, r.top+r.height/2)"""))))
    spr = pg.ev(EV('return __probe.live()'))
    chk('弹簧会自己停机（滚动数字与推拉都收敛了）', spr == 0, f'SPRG.raf={spr}')
    pg.shot('main_step1')
    open_detail(pg)      # 结构与 token 判据量的是抽屉里的卡片
    print('\n── 结构与可读性 ─────────────────────────────────')
    pg.shot('detail_open')      # 抽屉展开态：留一张给人看「证据都长什么样」
    chk('阶段与步骤读全（13 / 4）', len(stages) == 13 and len(steps) == 4,
        f'{len(stages)} 阶段 / {len(steps)} 步')
    chk('每个阶段都写了「写到哪儿」', all(s.get('writes') for s in stages),
        '缺: ' + ','.join(s['key'] for s in stages if not s.get('writes')))

    labels = pg.ev(EV('return [...document.querySelectorAll(".snode label")].map(x=>x.textContent).join("/")'))
    nstep = pg.ev(EV('return document.querySelectorAll(".snode").length'))
    chk('左轨恰好四步、没有未归组冒出来', nstep == 4, f'{nstep} 个：{labels}')

    ndot = pg.ev(EV("return document.querySelectorAll('.snode .dot').length"))
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

    print('\n── 版面 token：照参照物立的那几条能不能验 ─────────')
    # 这四条全部来自公开设计系统的**成文规则**（Linear / Raycast），不是审美偏好：
    # 每条都写成"旧版面会红"的形式，否则换一版配色照样全绿 = 空判据。
    # ⚠️ 旧版这里判的是"通道极差 ≤8"（中性）。那条是上一轮"去薰衣草"时立的，判的是
    #    **中性**；现在版面故意走海军蓝（215° 一带），通道极差天然 >20 ⇒ 旧判据必红。
    #    要守的规则一个字没变（"别拿薰衣草当卡片填充"），改判**色相落在哪条带**。
    pane_bg = pg.ev(EV("return getComputedStyle(document.querySelector('.pane')).backgroundColor"))
    ph = hue_of(pane_bg)
    chk('面板底色落在**海军蓝**带（色相 200~240°），不是薰衣草/紫（250~330°）',
        ph is not None and 200 <= ph <= 240, f'.pane 底色 {pane_bg} 色相 {ph:.0f}°')
    card_bg = pg.ev(EV("return getComputedStyle(document.querySelector('.stage')).backgroundColor"))
    ch = hue_of(card_bg)
    chk('卡片同色带，且比面板**抬高一档**（层级靠色阶不靠投影）',
        ch is not None and 200 <= ch <= 240 and
        sum(int(x) for x in re.findall(r'\d+', card_bg)[:3]) >
        sum(int(x) for x in re.findall(r'\d+', pane_bg)[:3]),
        f'面板 {pane_bg}（{ph:.0f}°）→ 卡片 {card_bg}（{ch:.0f}°）')
    # 唯一强调色：旧版是品牌紫（~262°），新版是蓝白（~219°）。这条直接钉死"第二种彩退役"。
    # 拿 `.steps .fill`（当前步进度条）当强调色的取样点：它是**恒在**的一块实心 `var(--brand)`，
    # 不像 `.pact` 会在第 4 步变成 `.pact.sign`（透明底 + 琥珀）。
    acc_bg = pg.ev(EV("return getComputedStyle(document.querySelector('.steps .fill')).backgroundColor"))
    ah = hue_of(acc_bg)
    chk('唯一 chrome 强调色是**蓝白**（色相 205~235°），品牌紫已退役',
        ah is not None and 205 <= ah <= 235, f'强调色取样 {acc_bg} 色相 {ah:.0f}°')

    def outer_layers(sel):
        raw = pg.ev(EV(f"return getComputedStyle(document.querySelector('{sel}')).boxShadow")) or ''
        out = []
        for lay in re.sub(r'rgba?\([^)]*\)', 'C', raw).split(','):
            lay = lay.strip()
            # ⚠️ Chrome 把 inset 序列化在**末尾**（`rgba(...) 0px 1px 0px 0px inset`），
            # 只判 startswith('inset') 会把内阴影误判成外投影，得到假红灯。
            if lay and lay != 'none' and 'inset' not in lay.split():
                out.append(lay)
        return out
    bad_sh = {s: outer_layers(s) for s in ('.pane', '.stage', 'header', '.pact')}
    bad_sh = {k: v for k, v in bad_sh.items() if v}
    chk('chrome 一律**零外投影**（纵深只靠色阶与描边，投影是"AI 生成界面"的指纹）',
        not bad_sh, str(bad_sh))
    caps = pg.ev(EV("""return [...document.querySelectorAll('.ph,.runs th')].
        map(e=>getComputedStyle(e).textTransform).filter(v=>v==='uppercase').length"""))
    chk('小标签不再全大写 + 宽字距（那是"设计感"最廉价的一种）', caps == 0, f'{caps} 个 uppercase')
    grads = pg.ev(EV("""return [...document.querySelectorAll('.pane,.stage,header,.pact,#stepfill,.ask')]
      .filter(e=>{const b=getComputedStyle(e).backgroundImage;
        return b&&b!=='none'&&/gradient/.test(b)}).map(e=>e.className)""")) or []
    chk('chrome 上不许有渐变填充（大气渐变是参照物明文禁止项）', not grads, f'带渐变: {grads}')

    close_detail(pg)
    print('\n── 星野画法：精灵图集 + 幂律亮度 ──────────────────')
    kinds = ('dust', 'star', 'hero', 'cloud')
    baked = pg.ev(EV("""const o={};
      for(const k of ['dust','star','hero','cloud'])
        o[k]=(window.SPR&&SPR[k]||[]).filter(c=>c&&c.width>4).length;
      return o"""))
    chk('四种星型精灵全部烘出（每型 4 档色温）',
        all(baked.get(k) == 4 for k in kinds), str(baked))
    # radial gradient 超出 r1 之后会**一直沿用最后一个色标**，而高斯在 t=1 处还剩 5~19%
    # ⇒ 精灵四边不透明 = 每颗星外面套一圈看得见的正方形（旋转后变菱形），比"敷衍"更难看。
    # 这条实测抓到过一次：外晕写成 `(i/14)*0.30` 时四角 alpha 高达 48。
    edge = pg.ev(EV("""const out={};
      for(const k of ['dust','star','hero','cloud']){
        let worst=0;
        for(const c of (SPR[k]||[])){
          const g=c.getContext('2d'), n=c.width, e=g.getImageData(0,0,n,n).data;
          const h=n>>1;
          for(const p of [[0,0],[n-1,0],[0,n-1],[n-1,n-1],[h,0],[0,h],[n-1,h],[h,n-1]])
            worst=Math.max(worst, e[(p[1]*n+p[0])*4+3]);
        }
        out[k]=worst;
      }
      return out""")) or {}
    chk('精灵四角与四边中点必须透明（不透明就会画出方框）',
        len(edge) == 4 and all(v <= 8 for v in edge.values()), f'边缘最大 alpha {edge}')
    dist = pg.ev(EV("""const L=ST.list, n=L.length||1;
      const c=k=>L.filter(t=>t.kind===k).length;
      return {n:n,hero:c('hero')/n,star:c('star')/n,dust:c('dust')/n}"""))
    chk('亮度按**幂律**分（hero <1.5%、star 5~18%，不是撒一把带十字的图钉）',
        0 < dist['hero'] < 0.015 and 0.05 < dist['star'] < 0.18,
        f"{dist['n']} 颗：hero {dist['hero']*100:.2f}% · star {dist['star']*100:.1f}% "
        f"· dust {dist['dust']*100:.1f}%")
    chk('银河带有**星云**层（静态位图，不吃"静止帧相同"那条）',
        bool(pg.ev(EV('return !!(ST.neb && ST.neb.width>100)'))))
    link_a = pg.ev('ST.LINK_A')
    chk('星座连线压到近不可见（上限 alpha ≤0.18；旧版 0.52 是"连点图"观感主因）',
        isinstance(link_a, (int, float)) and 0 < link_a <= 0.18, f'LINK_A={link_a}')

    print('\n── V 键：新旧版面必须一眼看得出不同（正向对照） ────')
    quiesce(pg)
    park(pg)
    chk('V 节前弹簧停机 + 星野已冻结（不然下面的像素比对量的是漂移相位）', settle(pg))
    pg.ev(EV('__probe.pin(); return 1'))      # 换版面不该重建节点，下面拿它验"切换无副作用"
    pin_sky(pg, 0.0)                          # 三张对照图全部钉在**同一相位**，只差 chrome
    new_shot = pg.shot('layout_new')
    pg.ev(EV('__probe.legacy(true); return 1'))
    time.sleep(0.5)
    park(pg)
    pin_sky(pg, 0.0)
    old_shot = pg.shot('layout_old')
    dmax, dmean, _ = diff_png(new_shot, old_shot)
    chk('V 切到旧版面：整屏必须**明显**变化（防"改了等于没改"）',
        dmax > 24 and dmean > 1.0, f'最大差 {dmax} 均值 {dmean:.2f}')
    pg.ev(EV('__probe.legacy(false); return 1'))
    time.sleep(0.5)
    park(pg)
    pin_sky(pg, 0.0)
    back_shot = pg.shot('layout_back')
    bmax, _, _ = diff_png(new_shot, back_shot)
    nbig = _count_above(new_shot, back_shot, 8)
    # 整页底是 linear-gradient，切 body 类会让 Chrome 重新合成 ⇒ 渐变 dither 会差 ±1~2
    # （§67 三记过这条地板）。所以"不留痕"不能拿"像素 == 0"当判据——那会把测量通道的抖动
    # 算成产品缺陷；但也不能只把数字放宽了事，真正会留痕的东西用**结构**断言钉死：
    # 类名回位、点光余辉清零、波数清零、节点没被重建。任何一条红都是真留痕。
    #
    # ⚠️ 旧版这里还有一条"星位残留位移 0"（`|t.x-t.hx|`）。**在漂移常开下它必红且无意义**：
    #    带上的星按参数 tb 漂，本来就会离 hx 很远（本轮实测 1.98e+03px）。位置漂移不再当留痕，
    #    改由 `pin_sky` 把相位钉死 + 下面的"冻结可复现"来兜。
    lit_end = pg.ev(EV('return ST.list.filter(t=>t.lit>0.05).length'))
    rings_end = pg.ev('ST.rings.length') or 0
    # 判"切回来了"要落在**语义**上（不再带 legacy 类），不要拿 className 的字面串比：
    # 上一版写 `cls in ('','none')` 却去比 JS 侧自造的哨兵串 `'(none)'`，自己把自己判红了。
    cls = pg.ev(EV("return [document.body.classList.contains('legacy'),"
                   "document.body.classList.contains('calm'),"
                   "document.body.classList.contains('plain')]"))
    pininfo = pg.ev(EV("""const p=window.__pin||[], now=[...document.querySelectorAll('.snode,.stage')];
      return {pinned:p.length, now:now.length,
              same:now.length>0 && p.length===now.length && p.every(e=>now.includes(e))}"""))
    chk('V 切回来不留痕：类名回位 + 点光余辉 0 + 波数 0 + 节点未被重建',
        cls[0] is False and lit_end == 0 and rings_end == 0 and pininfo['same'],
        f'class="{cls}" 仍亮 {lit_end} 颗 波 {rings_end} 节点 {pininfo}')
    # 地板取 6 而不是 3：夜航版底色是**两层** linear-gradient（天 + 地平线雾），
    # 切 body 类让 Chrome 重合成时 dither 能到 ±4（实测本版就是这个数），±3 那条
    # 会把两层叠加的抖动误判成留痕。真正咬人的仍是 `nbig == 0`（没有任何一个像素差 >8），
    # bmax 只是防"整片都差一点"的兜底。
    chk('V 切回来像素只允许 dither 地板级差异（>8 级的像素必须为 0）',
        bmax <= 6 and nbig == 0, f'最大差 {bmax} · >8 级的像素 {nbig} 个')
    quiesce(pg)

    print('\n── 静止不闪：轮询**开着**跨一次 8 秒 tick ─────────')
    # 这一节必须带着轮询跑。上一版是靠 `__probe.stop()` 把轮询停掉才比得出静止帧，
    # 于是"验收全绿"和"用户屏幕上每 8 秒整屏淡入一次"并存了三天 ——
    # 绕开真实入口的验证等于没验证（根因：入场动画写在 .step/.stage 基础类上，
    # 而 render() 是 innerHTML 整片重建 ⇒ 每次轮询都从头播）。
    pg.ev(EV('__probe.poll(true); return 1'))
    park(pg)
    pg.ev(EV('__probe.pin(); return 1'))
    # ⚠️ 必须先把相位钉死再拍：天在漂，不钉的话"整屏逐像素相同"量到的是漂移相位差
    #    （本轮实测 149 级假红），而这一节真正要抓的是**轮询把整屏重建**那类闪。
    pin_sky(pg, 0.0)
    a_tick = pg.shot('poll_a')
    time.sleep(9.6)                              # 覆盖一次 8s tick，留首屏指纹计算余量
    b_tick = pg.shot('poll_b')
    pmax, pmean, _ = diff_png(a_tick, b_tick)
    nanim = pg.ev(EV('return __probe.anims()'))
    chk('跨一次轮询整屏逐像素相同（相位已钉死；旧版这里必闪）', pmax == 0,
        f'整屏最大差 {pmax} 均值 {pmean:.2f}')
    chk('轮询没有重建 .snode/.stage 节点（动画无从重播）',
        bool(pg.ev(EV('return __probe.pinned()'))))
    chk('没有 WAAPI 动画在跑（轮询开着；星野是 rAF 自绘，不在 getAnimations 里）',
        nanim == 0, f'getAnimations={nanim}')

    print('\n── 光效：指针携光（棱边光 + 光晕），离开即收净、不进数据面 ──')
    # ⚠️ 这一段**不关星野**，改用 `pin_sky` 把天钉在固定相位。
    #    旧版关星野（body.plain）是为了让"两帧之间变了"只能来自光效；但 `body.plain #pool`
    #    是 `display:none`（CSS 里 .plain/.calm/.nopool 共享一条规则）⇒ 光晕在像素上根本验不到。
    #    冻结星野既去掉了漂移这个变量，又保住光晕可见。
    pin_sky(pg, 0.0)
    park(pg)
    time.sleep(0.4)                  # 让 #pool 的 .3s 淡出与定位收干净，fx_base 才是"干净"基线
    fx_base = pg.shot('fx_base')
    # 旧版量的是"边框绕一圈跑光"（`#fxbeam` + WAAPI 钉时刻）。那套整个删了 ——
    # conic 渐变绕边跑正是最典型的"AI 加的特效"。现在只有两件事，判据也跟着换成：
    #   ① 最近棱边光：指针在控件上沿 vs 下沿，棱边必须**换向**；
    #   ② 光晕：跟着指针，且压在 `.app` 之下（数据面天然吃不到，不靠"挑选择器"挡）。
    # ⚠️ 取样点用主行动 `.pact`，**不能用 `.snode`** —— 步骤节点被 `FXSEL`
    #    （`button:not(.snode)`）显式排除了：它是竖排标签组、没有实体边框，给它打棱边光很怪。
    #    旧版拿 `.snode.on` 当靶子，那是"边框跑光"时代的写法，套到棱边光上会恒红。
    sn = pg.ev(EV("""const r=document.querySelector('#cta .pact').getBoundingClientRect();
      return [Math.round(r.left),Math.round(r.top),Math.round(r.right),Math.round(r.bottom)]"""))
    pg.move(sn[0] + int((sn[2] - sn[0]) * 0.3), sn[1] + 3)        # 贴上棱
    time.sleep(0.15)
    f1 = pg.ev(EV('return __probe.fx()'))
    ax1 = edge_axis(f1['edgeBg'])
    chk('悬停控件 → 最近棱边亮起 1px + 光晕挂上',
        bool(f1['edge'] and f1['edgeShown'] and f1['pool']),
        f"edge={f1['edge']} shown={f1['edgeShown']} pool={f1['pool']} k={f1['k']}")
    chk('棱边光的**走向**与它自称的方向自洽（贴上/下棱 ⇒ 横着一条）',
        f1['k'] == 't' and ax1 == 'h', f"k={f1['k']} 走向={ax1} bg={f1['edgeBg']}")
    pg.shot('fx_edge_top')
    pg.move(sn[0] + int((sn[2] - sn[0]) * 0.3), sn[3] - 3)        # 贴下棱
    time.sleep(0.15)
    f1b = pg.ev(EV('return __probe.fx()'))
    ax1b = edge_axis(f1b['edgeBg'])
    chk('棱边光跟着「离指针最近的那条边」换向（上棱 → 下棱）',
        f1b['k'] == 'b' and ax1b == 'h' and f1b['edgeBg'] != f1['edgeBg'],
        f"k={f1['k']}→{f1b['k']} · bg 变了={f1b['edgeBg'] != f1['edgeBg']}")
    pg.shot('fx_edge_bottom')
    chk('光晕落在主行动上（不是挂在别处）',
        bool(f1['pool'] and f1['cur'] and 'pact' in f1['cur']), f"cur={f1['cur']}")
    pg.shot('fx_btn')

    def bar_scale():
        return pg.ev(EV("""const s=document.querySelector('.stage');
          const t=getComputedStyle(s,'::before').transform; const m=t&&t.match(/matrix\\(([^)]+)\\)/);
          return m?parseFloat(m[1].split(',')[3]):1"""))
    def bar_org():
        return pg.ev(EV("""const s=document.querySelector('.stage');
          return getComputedStyle(s,'::before').transformOrigin"""))
    pg.move(6, 6)
    open_detail(pg)      # 阶段卡在抽屉里，量它得先开
    time.sleep(0.5)
    rest_scale, rest_org0 = bar_scale(), bar_org()
    cd = pg.ev(EV("""const r=document.querySelector('.stage').getBoundingClientRect();
      return [Math.round(r.left+r.width*0.4), Math.round(r.top+r.height*0.78)]"""))
    pg.move(cd[0], cd[1])
    # ⚠️ 不能固定 sleep 就读值：光条是 .38s 的 CSS 过渡，抽屉开着 + 背景画布在跑时
    #    无头里起步会晚得多，实测 sleep(0.55) 只走到 scaleY 0.886 —— 那是采样太早，
    #    不是产品没展开（技能第 11 条同一条规矩，我自己新加的判据先犯了）。
    t0 = time.time(); hot_scale = rest_scale
    while time.time() - t0 < 3.0:
        hot_scale = bar_scale()
        if hot_scale > 0.995: break
        time.sleep(0.15)
    hot_scale = bar_scale()
    chk('阶段卡左光条从进入高度**展开**（静止 34% → 悬停 100%）',
        rest_scale < 0.5 and hot_scale > 0.95, f'静止 {rest_scale} → 悬停 {hot_scale}')
    pg.shot('fx_card')
    pg.move(6, 6)
    time.sleep(0.5)
    # ⚠️ 必须连**收缩原点**一起复位：光条静止时是 scaleY(34%)，`transform-origin` 若还停在
    # 指针进入的高度，那 2px 的条就永久偏在那个位置 —— 实测留下 104 个差异像素（最大差 22），
    # 全部落在卡片左边缘的同一列上。只量 scaleY 回没回 0.34 是抓不到这条的。
    # 断言拿"进入前"当基线，不写死字面值：计算样式会把 `50% 50%` 解析成 `1px 67.32px`。
    org_back, sc_back = bar_org(), bar_scale()
    close_detail(pg)
    chk('指针离开卡片后光条收回原位（不留展开态、也不留收缩原点）',
        sc_back < 0.5 and org_back == rest_org0,
        f'scale={sc_back} origin={org_back} 进入前={rest_org0}')

    # ── 离开即收净 ────────────────────────────────────────────────────
    pg.move(6, 6)
    time.sleep(0.6)                              # 棱边光摘掉、#pool 回到角落
    f2 = pg.ev(EV('return __probe.fx()'))
    chk('指针离开控件后棱边光摘掉（不留残影、不留挂着的动画）',
        not f2['edge'], str(f2))
    # 光晕是"跟着指针"的：指针只要还在窗口里它就亮着，这是设计如此 ⇒ **不能**拿"看不见"当判据。
    # 「装饰不进数据面」改成**结构性**断言：光晕层压在 .app 之下，不透明面板天然吃不到光。
    zx = pg.ev(EV("""return {pool:+getComputedStyle(document.querySelector('#pool')).zIndex||0,
      app:+getComputedStyle(document.querySelector('.app')).zIndex||0}"""))
    chk('#pool 压在 .app 之下（不透明面板天然吃不到光，不靠"挑选择器"挡）',
        zx['pool'] < zx['app'], str(zx))
    fxmax, _, _ = diff_png(fx_base, pg.shot('fx_after'))
    chk('划过控件再离开 → 回到同一张帧（冻结相位下，光效不留痕）',
        fxmax == 0, f'整屏最大差 {fxmax}')

    # 日志 `pre` 不在 FXSEL 里：悬停它不该出现棱边光（装饰不进数据面）。
    open_detail(pg)
    time.sleep(0.4)
    lg = pg.ev(EV("""const e=document.querySelector('pre'); if(!e) return null;
      const r=e.getBoundingClientRect();
      return [Math.round(r.left+r.width/2), Math.round(r.top+r.height/2)]"""))
    if lg:
        pg.move(lg[0], lg[1])
        time.sleep(0.2)
        f3 = pg.ev(EV('return __probe.fx()'))
        chk('日志面上方不挂棱边光（pre 不在 FXSEL 里，装饰不进数据面）',
            not f3['edge'] and f3['cur'] is None, str(f3))
    else:
        notes.append('抽屉里没有日志 pre，跳过「日志面不挂棱边光」——没有可量的对象，'
                     '不算通过也不算失败')
    close_detail(pg)

    # ── M 键「动效从简」= 光效整层停用 **且背景冻结** ────────────────
    pg.move(6, 6)
    chk('M 键关掉整层光效：棱边光与光晕两个浮层都 display:none',
        bool(pg.ev(EV("""__probe.calm(true);
          return getComputedStyle(document.querySelector('#fxedge')).display==='none'
              && getComputedStyle(document.querySelector('#pool')).display==='none'"""))))
    chk('M 键同时把背景星野冻结（"从简"= 屏幕上一个东西都不再动）',
        bool(pg.ev(EV('return __probe.sky().frozen'))), str(pg.ev(EV('return __probe.sky()'))))
    pg.move(sn[0] + 10, sn[1] + 3)
    time.sleep(0.15)
    chk('从简模式下悬停：棱边光不再出现', not pg.ev(EV('return __probe.fx()'))['edge'],
        str(pg.ev(EV('return __probe.fx()'))))
    pg.move(6, 6)
    pg.ev(EV('__probe.calm(false); return 1'))
    rm = pg.ev(EV("""const on=document.querySelector('.snode.on'), mk=document.querySelector('#stepfill');
      const br=document.querySelector('#stepsbar').getBoundingClientRect();
      const r=on.getBoundingClientRect();
      const want=Math.round(r.left+r.width/2-br.left);
      return {ok: Math.abs(parseFloat(mk.style.width)-(want))<=2.5,
              got:mk.style.width, want:want+'px'}"""))
    chk('当前步指示条仍在且跟着换步落位（那是信息，不是被一起关掉的装饰）', rm['ok'], str(rm))
    cm = pg.ev(EV("""document.querySelector('.chip[data-f=bad]').click();
      const on=document.querySelector('.chip.on'), mk=document.querySelector('#chipmark');
      return {ok: mk.style.opacity==='1' && mk.style.left===on.offsetLeft+'px'
                  && mk.style.width===on.offsetWidth+'px',
              got:mk.style.left+'/'+mk.style.width, want:on.offsetLeft+'/'+on.offsetWidth}"""))
    chk('日志筛选片：指示条滑到当前项', cm['ok'], str(cm))
    pg.ev(EV("""document.querySelector('.chip[data-f=all]').click();
      __probe.go(2); return 1"""))
    quiesce(pg)

    print('\n── 背景层：常驻 / 漂移有界且慢 / 天是状态面 / 不遮挡 ──')
    # 量背景之前先确认**屏幕上没有那层全屏遮罩**：它 position:fixed;inset:0 且带背景色，
    # 一旦还在，「背景可见区」会被算成 0 像素，region_diff 只能拿 999 判红 ——
    # 那看起来像「掩码写错了」，实际是上一节的抽屉没关严（本轮实测踩过）。
    veil = pg.ev(EV('''
      const v=document.querySelector('#detail .veil'); if(!v) return 0;
      let n=v, vis=true;
      while(n){ const c=getComputedStyle(n);
        if(c.display==='none'||c.visibility==='hidden'||parseFloat(c.opacity)<0.02){vis=false;break;}
        n=n.parentElement; }
      if(!vis) return 0;
      const r=v.getBoundingClientRect(); return Math.round(r.width*r.height)'''))
    chk('量背景前没有全屏遮罩（遮罩会让背景可见区退化成 0 像素的空判据）',
        (veil or 0) < 5000, f'遮罩面积 {veil}')
    n_stars = pg.ev('ST.list.length') or 0
    chk('星野够密（常驻星野按屏幕面积定价，700~1600 颗）', 600 <= n_stars <= 1700,
        f'{n_stars} 颗星')

    # ── 常驻 + 漂移有界且慢（替代旧「静止两帧逐像素相同」）────────────────
    # 旧判据保护的是"背景不许自己走"——那正是 B2「漂移常开」明确放弃的设计意图，
    # 在漂移常开下**必然**红。新判据问的是两件更有用的事：天是不是真的在动、动得多快。
    park(pg)
    el, dts, dfr, disp = drift_sample(pg, 0.9)
    mx_d = max(disp) if disp else -1
    bound = max(pg.ev('ST.DRIFT')) * el + 0.6
    slow = sum(1 for d in disp if d <= bound)
    frac = slow / len(disp) if disp else 0
    chk('常驻：不碰鼠标时星野仍在走（t 与自绘帧数都在推进）',
        dts > 0.5 and dfr > 0, f'Δt={dts:.2f}s 帧 +{dfr}')
    # 环绕会让个别星"瞬移"一整个屏宽（带上的星按 tb 取模、带外的按水平取模），
    # 那不是"漂移超速"⇒ 判**绝大多数**星；但"确实有位移"仍必须为真，
    # 否则"把速度调成 0"也能冒充"漂移有界"。
    chk('漂移有界且慢：绝大多数星位移 ≤ 上限×Δt+0.6px，且确实有位移',
        frac > 0.95 and mx_d > 0.05,
        f'{slow}/{len(disp)} 颗在界内（{frac*100:.1f}%）· 最大位移 {mx_d:.2f}px '
        f'· 界 {bound:.2f}px（{el:.2f}s）')
    cfg = pg.ev(EV('return __probe.sky()'))
    chk('「慢」是配置约束不是碰巧：视差 ≤2px/s、自绘限流 ≤30 帧',
        max(cfg['drift']) <= 2 and cfg['fps'] <= 30,
        f"DRIFT={cfg['drift']} FPS={cfg['fps']} DIM={cfg['dim']}")

    # ── 冻结态可复现（替代旧「淡净后回到同一个静止态」）──────────────────
    # 漂移常开 ⇒ 只有冻结才拿得到可比的两帧。冻结可不可复现，本身必须逐像素验。
    pin_sky(pg, 0.0)
    fmx, fbig = frozen_pair(pg)
    chk('冻结态可复现：钉住相位后隔 1.4s 两帧整屏逐像素相同（>8 级像素为 0）',
        fbig == 0, f'最大差 {fmx} · >8 级的像素 {fbig}')

    # ── 天是状态面（新增）────────────────────────────────────────────────
    # 信标列必须对准"当前那一步"的节点，且它正上方的星点确实被抬亮。
    bc = pg.ev(EV("""const b=ST.beacon; if(!b) return null;
      const on=document.querySelector('#stepsbar .snode.on')||document.querySelector('#stepsbar .snode');
      const r=on.getBoundingClientRect();
      return {bx:Math.round(b.x), half:Math.round(b.half), cx:Math.round(r.left+r.width/2)}"""))
    chk('信标列对准当前那一步的节点（天和任务挂上了钩）',
        bool(bc) and abs(bc['bx'] - bc['cx']) <= 2, str(bc))
    bm = pg.ev(EV("""const b=ST.beacon; if(!b) return null;
      let si=0,sn=0,ai=0,an=0;
      for(const t of ST.list){ ai+=t.v; an++;
        if(Math.abs(t.x-b.x)<b.half*0.6){ si+=t.v; sn++; } }
      return {inMean:+(sn?si/sn:0).toFixed(4), allMean:+(an?ai/an:0).toFixed(4),
              inN:sn, allN:an}"""))
    chk('信标列正上方的星点亮度高于全屏均值（天是状态面，不是撒一把星）',
        bool(bm) and bm['inN'] > 0 and bm['allMean'] > 0 and bm['inMean'] > bm['allMean'] * 1.25,
        str(bm))
    # 判绿荡波：只在状态**真的翻转**时才响（首帧不响 ⇒ 刷新不会假响）。
    rr = pg.ev(EV("""
      __probe.freeze(false);
      __probe.go(2);
      const ks=Object.keys((S&&S.state)||{}); if(!ks.length) return {err:'no state'};
      const k=ks[0], bak=JSON.parse(JSON.stringify(S.state[k]));
      PASSWATCH={};
      S.state[k]={ok:false,detail:'x'}; passWatch();     // 先落一个"没绿"
      S.state[k]={ok:true,detail:'y'}; ST.rings.length=0;
      const bx=ST.beacon?ST.beacon.x:null;
      passWatch();                                        // 再翻成"绿" ⇒ 该响一圈
      const out={rings:ST.rings.length, bx:bx, rx:ST.rings[0]?ST.rings[0].x:null};
      S.state[k]=bak; render();
      return out"""))
    chk('某个阶段判绿 ⇒ 从信标处荡开一圈波（波心对得上信标）',
        bool(rr) and rr.get('rings', 0) > 0 and rr.get('rx') is not None
        and rr.get('bx') is not None and abs(rr['rx'] - rr['bx']) <= 2, str(rr))

    # ── 不遮挡：底色不透明 + 几何包含 + 关掉背景后可见区真的空了 ──────────
    park(pg)
    pin_sky(pg, 0.0)
    rects = paint_rects(pg)
    base = pg.shot('bg_base')
    opaque = pg.ev(EV("""
      const bad=[];
      document.querySelectorAll('header,.pane,.stage,pre,.sheets a,.sheets img,.meter,.snode,.pact,.dhead,#detail .body')
        .forEach(e=>{ const c=getComputedStyle(e).backgroundColor;
          const m=c.match(/[\\d.]+\\s*[,\\/]\\s*([\\d.]+)\\)?$/);
          const a=c.startsWith('rgba')?(m?parseFloat(m[1]):0):1;
          if(c!=='rgba(0, 0, 0, 0)' && a<0.995) bad.push(e.className+' '+c); });
      return bad.slice(0,6)
    """))
    chk('数据面底色全部不透明（alpha=1）', not opaque, '漏: ' + str(opaque))
    # 正向对照：关掉背景后背景可见区必须真的空了 —— 否则"背景不渗进来"是空判据
    # （把背景整层删掉也能拿满分）。只在**抽屉关着**时比，区域掩码才和基线同构。
    pg.ev(EV("document.querySelector('#bSea').click(); return 1"))
    time.sleep(0.7)
    plain_on = pg.ev(EV("return document.body.classList.contains('plain')"))
    chk('星辰开关关掉：class 生效', bool(plain_on), f'plain={plain_on}')
    plain = pg.shot('plain')
    rt = region_diff(base, plain, rects)
    chk('关背景后背景可见区确实空了（星野是活的，防"不渗进来"成为空判据）',
        rt['bg_chg'] > 3000,
        f"背景可见区少了 {rt['bg_chg']} 个像素的内容（整屏最大差 {rt['bg_max']} 含重光栅化"
        f"的字边缘，不作判据）")
    pg.ev(EV("document.querySelector('#bSea').click(); return 1"))
    time.sleep(0.6)
    # 结构判据：**每个数据元素整张坐在一个不透明面板里**。
    # 与"面板底色 alpha=1"两条合起来，才是"背景渗不进来"的可证形式——
    # 逐像素那条在这个页面上量到的是重光栅化噪声（见 §67 三）。
    open_detail(pg)
    quiesce(pg)
    pg.shot('stars_on')
    leak = pg.ev(EV('''
      const out=[];
      document.querySelectorAll('.stage,pre,.sheets a,.sheets img,.meter,.runs td')
        .forEach(e=>{
          const r=e.getBoundingClientRect();
          if(r.width<2||r.height<2) return;
          // 抽屉的 .body 本身就是不透明表面（--deep），量「在不在面板里」必须算它
          const p=e.closest('.pane,header,#detail .body');
          if(!p){ out.push((e.className||e.tagName)+':不在任何面板里'); return; }
          const q=p.getBoundingClientRect();
          if(r.left<q.left-0.5||r.top<q.top-0.5||r.right>q.right+0.5||r.bottom>q.bottom+0.5)
            out.push((e.className||e.tagName)+' 越出面板');
        });
      return out.slice(0,8)
    '''))
    chk('每个数据元素都整张坐在不透明面板内', not leak, '漏: ' + str(leak))
    inside = pg.ev(EV('''
      const a=c=>{const m=c.match(/rgba\\([^)]*,\\s*([\\d.]+)\\)/);return m?+m[1]:1;};
      return [a(getComputedStyle(document.querySelector('.stage')).backgroundColor)<=0.995?0:1,
              a(getComputedStyle(document.querySelector('.pane')).backgroundColor)<=0.995?0:1]
    '''))
    chk('卡片与面板底色实测不透明（正向：防上面那条成为空判据）',
        inside == [1, 1], f'实测 [卡片, 面板] 不透明={inside}')
    # 对照图只有在抽屉里才看得见 ⇒ 单独在**抽屉开着**的状态下再取一对（开/关背景）来比，
    # 否则量到的是"抽屉关着时那块位置本来就没有图"，属于空判据。
    shbox = pg.ev(EV("""
      const e=document.querySelector('.sheets img'); if(!e) return null;
      const r=e.getBoundingClientRect();
      return r.width>60 ? [Math.round(r.x),Math.round(r.y),
             Math.round(r.right),Math.round(r.bottom)] : null
    """))
    if shbox:
        s_on = pg.shot('sheets_on')
        pg.ev(EV("document.querySelector('#bSea').click(); return 1"))
        time.sleep(0.6)
        s_off = pg.shot('sheets_off')
        smax, smean, _ = diff_png(s_on, s_off, tuple(shbox))
        chk('对照图底完全不透明（背景不影响看图）', smax == 0, f'最大差 {smax} 均值差 {smean:.4f}')
    else:
        notes.append('盘上还没有对照表，跳过「对照图底不透明」那条——没有可量的对象，不算通过也不算失败')
    pg.ev(EV("if(document.body.classList.contains('plain'))"
             " document.querySelector('#bSea').click(); return 1"))
    time.sleep(0.4)

    close_detail(pg)
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
    an = pg.ev(EV("return getComputedStyle(document.querySelector('.snode')).animationName"))
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
    open_detail(pg)
    print('── 交互（键盘 / 筛选 / 联动）─────────────────────')
    pg.ev(EV('window.__probe.go(1); return 1'))
    quiesce(pg)
    key(pg, '3', 'Digit3', 52)
    time.sleep(0.35)
    chk('键盘 3 直接跳到第③步', pg.ev(EV('return step')) == 3,
        'step=%s 标题=%s' % (pg.ev(EV('return step')),
                             pg.ev(EV('return document.getElementById("eyebrowTx").textContent'))))
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
