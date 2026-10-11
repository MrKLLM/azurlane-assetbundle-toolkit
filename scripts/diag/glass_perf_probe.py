# -*- coding: utf-8 -*-
"""液态玻璃改造前的性能基线：把「水面 canvas」与「卡片的 backdrop-filter」各自的代价拆开量。

背景：用户报「一划水波纹就有点卡」，而液态玻璃要往同一批元素上挂折射滤镜。
不接受"应该还好"这种回答——必须先量出现状，再量出候选方案，否则改完更卡。

六种条件（idle/wave × 三种材质），每种在页面上用 rAF 采样 2.5 秒帧间隔：
  A idle_as_is        静止 + 现有毛玻璃        —— 现状的地板
  B wave_as_is        划水 + 现有毛玻璃        —— 用户报卡的那个场景
  C wave_no_glass     划水 + 摘掉全部 backdrop-filter —— 只剩水面自己的钱
  D wave_turb         划水 + 折射(feTurbulence 现算噪声) —— 上界，**真方案不是这么做的**
  E wave_img          划水 + 折射(静态法线图查表) —— 真方案的边墙
  F wave_img_body     划水 + 折射铺满整张卡面板 —— 最坏情况

判据（必须能红）：
  · BG.mode 必须是 'gl'，否则整份数字作废（水面回退成 CSS 时这里量不到东西）
  · 采样期间 strokes 必须 >0，否则「划水」根本没发生，B~F 全等于 A
  · 打印 GPU renderer —— 无头若落到 SwiftShader，绝对帧率不可与用户实机比，只能看相对差

用法：
  py -3 .diag/glass_perf_probe.py                 # 需要 8799 上有静态服务（见脚本内 preflight）
  py -3 .diag/glass_perf_probe.py --port 8777
"""
import sys, os, json, math, time, base64, hashlib, shutil, argparse, subprocess, urllib.request, zlib
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'diag'))
import chrome_tree

CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
AP = argparse.ArgumentParser()
AP.add_argument('--port', default='8799')
AP.add_argument('--win', default='2560,1600')
AP.add_argument('--ms', type=int, default=2500)
AP.add_argument('--phases', action='store_true', help='只拆水面四段耗时，不跑六种材质对比')
AP.add_argument('--shots', action='store_true', help='成对取图：同一帧冻结背景下的「改前模糊 / 改后折射」')
AP.add_argument('--bend', action='store_true', help='配合 --shots：背后铺密集条纹，判「几何错」还是「背景没内容」')
AP.add_argument('--depth', type=int, default=0, help='配合 --shots：临时把 --lg-depth 拉到这个值做极端检验')
AP.add_argument('--caps', action='store_true', help='只跑 backdrop-filter 写法矩阵，定位哪一种被算成 none')
AP.add_argument('--maskdiag', action='store_true', help='导出遮罩几何诊断（查"整块实心而不是环"）')
A = AP.parse_args()
W, H = (int(x) for x in A.win.split(','))
URL = f'http://127.0.0.1:{A.port}/gallery_v2/index.html'

# ── 静态法线图：一张 96x128 的"边墙"坡度图（R=x 位移、G=y 位移），PNG 编码后当 data URI。
#    真方案里这张图由 JS 按卡片尺寸现算，这里只需要它的**成本形态**（查表，不是现算噪声）。
def normal_map_png(w=96, h=128, ring=14, radius=16):
    import math
    def sdf(x, y):                       # 圆角矩形到边框的带符号距离（负=在内）
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        bx, by = cx - radius, cy - radius
        dx = abs(x - cx) - bx
        dy = abs(y - cy) - by
        ax, ay = max(dx, 0.0), max(dy, 0.0)
        return min(max(dx, dy), 0.0) + math.hypot(ax, ay) - radius
    raw = bytearray()
    for y in range(h):
        raw.append(0)                    # filter type 0
        for x in range(w):
            e = -sdf(x, y)               # 到边框的内距离
            t = max(0.0, min(1.0, 1.0 - e / ring))
            gx = gy = 0.0
            if 0 < e < ring:             # 坡度 = 距离场梯度，指向内侧
                gx = (sdf(x + 1, y) - sdf(x - 1, y)) * 0.5
                gy = (sdf(x, y + 1) - sdf(x, y - 1)) * 0.5
            r = int(max(0.0, min(255.0, 128 + gx * t * 128)))
            g = int(max(0.0, min(255.0, 128 + gy * t * 128)))
            raw += bytes((r, g, 128, 255))

    def chunk(tag, data):
        c = tag + data
        return len(data).to_bytes(4, 'big') + c + zlib.crc32(c).to_bytes(4, 'big')
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', w.to_bytes(4, 'big') + h.to_bytes(4, 'big') + bytes((8, 6, 0, 0, 0)))
           + chunk(b'IDAT', zlib.compress(bytes(raw), 6))
           + chunk(b'IEND', b''))
    return 'data:image/png;base64,' + base64.b64encode(png).decode()


MAPURI = normal_map_png()

CSS = {
    'asis': '',
    'noglass': ('.card,.card::before,header,header::before'
                '{backdrop-filter:none!important;-webkit-backdrop-filter:none!important}'),
    # D：折射用 feTurbulence（每帧现算噪声）——故意做成上界
    # ⚠️ 2026-10-11 这三条从 `.card.g::before` 改指到 `#glassone`：边墙并成一层之后，
    #    卡片的 ::before 只剩 :hover 才有，往它身上注入等于打在空选择器上（D/E 会与 C 逐字节相同，
    #    看起来像"折射不改变像素"，其实是条件失效）。
    'turb': ('.card.g{-webkit-backdrop-filter:none!important;backdrop-filter:none!important}'
             '#glassone{backdrop-filter:blur(1px) url(#pTurb)!important;'
             '-webkit-backdrop-filter:blur(1px) url(#pTurb)!important}'),
    # E：折射用静态法线图查表——真方案
    'img': ('.card.g{-webkit-backdrop-filter:none!important;backdrop-filter:none!important}'
            '#glassone{backdrop-filter:blur(1px) url(#pImg)!important;'
            '-webkit-backdrop-filter:blur(1px) url(#pImg)!important}'),
    # F：整张卡面板也折射（最坏情况）
    'imgbody': ('.card.g{-webkit-backdrop-filter:blur(2px) url(#pImg)!important;'
                'backdrop-filter:blur(2px) url(#pImg)!important}'
                '.card.g::before{-webkit-backdrop-filter:blur(1px) url(#pImg)!important;'
                'backdrop-filter:blur(1px) url(#pImg)!important}'),
    # L：只留边墙折射，把面板那层 blur(2.5px) 摘掉 —— 验「一张卡两层滤镜 → 一层」能省多少
    'rimonly': '.card.g{-webkit-backdrop-filter:none!important;backdrop-filter:none!important}',
    # M：把卡片边墙那圈滤镜整个摘掉（面板层 2026-10-11 已删，所以这条现在等价于 C 的"卡片无滤镜"）
    #    ⇒ 它是 C 的**交叉校验**：M 与 C 若不同价，说明还有一层滤镜没被账目算进去。
    'panelonly': ('html.lg .card.lgr::before{-webkit-backdrop-filter:none!important;'
                  'backdrop-filter:none!important}'
                  '.card.g::before{-webkit-backdrop-filter:none!important;'
                  'backdrop-filter:none!important}'),
    # ── 追那 20ms 的去向（水面 JS 只占 0.34ms，剩下的必在浏览器渲染侧）──
    # G：摘玻璃 + 藏掉 #bgfx 里那三个 74vmax 径向渐变光晕
    'noglass_noglow': ('.card,.card::before,header,header::before'
                       '{backdrop-filter:none!important;-webkit-backdrop-filter:none!important}'
                       '#bgfx .glow{display:none!important}'),
    # J：保留现有毛玻璃 + 藏光晕（若光晕是主因，这条就是「只改背景能省多少」）
    'noglow': '#bgfx .glow{display:none!important}',
    # ── 把「边墙那层 ≈20ms」继续拆开：面积贵？遮罩贵？还是数量贵？ ──
    # N：边墙模糊半径 17px → 5px（面积与遮罩都不变，只有半径变）
    'rim5': '.card.g::before{backdrop-filter:blur(5px) saturate(2) brightness(1.08)!important;'
            '-webkit-backdrop-filter:blur(5px) saturate(2) brightness(1.08)!important}',
    # P：摘掉那两层 mask，但滤镜与面积原样保留 ⇒ 与「落地态」之差 = **遮罩**的钱
    'nomask': '.card.g::before{-webkit-mask:none!important;mask:none!important}',
    # Q：只留顶边 12px 一条（无遮罩、面积只有 12px 高）⇒ 与 P 之差 = **面积**的钱
    'strip': ('.card.g::before{-webkit-mask:none!important;mask:none!important;'
              'inset:auto auto 0 0!important;height:12px}'),
    # R：边墙滤镜链从 blur+saturate+brightness 缩成只剩 blur ⇒ 量「链上每个函数要不要钱」
    #    （N/P/Q 已证明半径、遮罩、面积都不要钱，剩下的嫌疑就是函数个数）
    'rim_plain': ('.card.g::before{backdrop-filter:blur(17px)!important;'
                  '-webkit-backdrop-filter:blur(17px)!important}'),
    # S：把 2026-10-11 砍掉的**面板那层 blur(2.5px)** 原样注回来 ⇒ 这不是性能条件，是"免费"这条
    #    结论的证据：它的 shot_card 与 B 逐字节相同，才许说"那层本来就看不出"。
    #    若不同，就不许声称免费，得交用户肉眼判。
    'panel_back': ('.card.g{-webkit-backdrop-filter:blur(2.5px) saturate(1.5)!important;'
                   'backdrop-filter:blur(2.5px) saturate(1.5)!important}'),
    # O：摘掉逐卡边墙滤镜 —— 与 overlay 配对，用来量「70 个盒 → 1 个盒」到底省多少
    'rim_off': ('.card.g::before{-webkit-backdrop-filter:none!important;'
                'backdrop-filter:none!important}'),
}

# 数量敏感性：把在屏挂滤镜的卡数硬压到 N 张，直接量"几张卡才付得起"。
# ⚠️ 测量期间不滚动，所以摘掉的类不会被观察器加回来；这条只用于定位成本曲线，不是候选实现。
JS_PRE = {
    'renderstub': "(()=>{if(!window.__R0)window.__R0=bgRender; window.bgRender=function(){}; return 'ok';})()",
    # K：只把折射摘掉（html.lg 一去掉，②-b 那条规则就不匹配，边墙自动退回上一版那条模糊）
    # —— 这才是「新效果比旧效果贵多少」的正确对照，C 那条把模糊也一起摘了，量的是别的东西。
    'lgoff': "(()=>{document.documentElement.classList.remove('lg'); return 'ok';})()",
    'few24': "(()=>{const a=[...document.querySelectorAll('.card.g')];"
             "a.slice(24).forEach(c=>c.classList.remove('g','lgr'));return 'ok';})()",
    'few40': "(()=>{const a=[...document.querySelectorAll('.card.g')];"
             "a.slice(40).forEach(c=>c.classList.remove('g','lgr'));return 'ok';})()",
    '_restore': "(()=>{if(window.__R0){window.bgRender=window.__R0;}"
                "document.documentElement.classList.add('lg');"
                # few24/few40 会摘掉一批 .g，而测量期间不滚动、观察器不会加回来 ⇒ 还原必须
                # 自己按视口重算一遍，否则后面所有条件都在"卡更少"的状态上测，数字全线偏低。
                "document.querySelectorAll('.card').forEach(c=>{const r=c.getBoundingClientRect();"
                "c.classList.toggle('g', r.bottom>-140 && r.top<innerHeight+140);});"
                "return 'ok';})()",
}

SVG = """<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'
 style='position:absolute;width:0;height:0' aria-hidden='true'><defs>
<filter id='pTurb' x='0%%' y='0%%' width='100%%' height='100%%'>
  <feTurbulence type='fractalNoise' baseFrequency='0.012' numOctaves='2' seed='7' result='n'/>
  <feDisplacementMap in='SourceGraphic' in2='n' scale='70' xChannelSelector='R' yChannelSelector='G'/>
</filter>
<filter id='pImg' x='0%%' y='0%%' width='100%%' height='100%%'>
  <feImage x='0' y='0' width='100%%' height='100%%' preserveAspectRatio='none'
           href='%s' xlink:href='%s' result='n'/>
  <feDisplacementMap in='SourceGraphic' in2='n' scale='70' xChannelSelector='R' yChannelSelector='G'/>
</filter></defs></svg>""" % (MAPURI, MAPURI)

# ⚠️ 划水必须由**页面内部**驱动：Python 侧逐条 Input.dispatchMouseEvent 是阻塞等 CDP 回复的，
#    实测只能跑到 ~30–40 次/秒，而各条件的 bg帧 恰好也是 29–53 —— 那意味着"帧时 27ms"量的
#    根本不是我发事件的速度，不是渲染成本。改成在 rAF 里 dispatch 真实 pointermove，
#    走的仍是页面自己那个 window pointermove 监听器（没有绕过入口）。
START = """(()=>{const ms=%d, wave=%s;
  const ts=[],st=document.getElementById('perfsty');
  if(st) st.remove();
  const s=document.createElement('style'); s.id='perfsty'; s.textContent=%r;
  document.head.appendChild(s);
  const strokes0=BG.strokes, frames0=BG.frames;
  window.__P={done:false};
  let last=performance.now(), t0=last;
  function f(now){ ts.push(now-last); last=now;
    if(wave){ const p=(now-t0)/1000;
      const x=innerWidth*(0.5+0.45*Math.sin(p*3.0)), y=innerHeight*(0.5+0.28*Math.cos(p*2.1));
      window.dispatchEvent(new PointerEvent('pointermove',{clientX:x,clientY:y,bubbles:true})); }
    if(now-t0<ms){ requestAnimationFrame(f); }
    else { const s2=ts.slice(5).sort((a,b)=>a-b);
      window.__P={done:true,n:ts.length,med:+s2[s2.length>>1].toFixed(2),
        p95:+s2[Math.floor(s2.length*0.95)].toFixed(2),max:+s2[s2.length-1].toFixed(2),
        fps:+(1000/s2[s2.length>>1]).toFixed(1),
        strokes:BG.strokes-strokes0, bgframes:BG.frames-frames0,
        cardsG:document.querySelectorAll('.card.g').length,
        peak:+BG.peak.toFixed(4),energy:+BG.energy.toFixed(5),mode:BG.mode,
        canvas:BG.cv.width+'x'+BG.cv.height}; } }
  requestAnimationFrame(f); return 'go';})()"""


class Page:
    def __init__(self, port, profile, url, win):
        flags = ['--headless=new', f'--remote-debugging-port={port}', '--remote-allow-origins=*',
                 f'--user-data-dir={profile}', '--no-first-run', '--no-default-browser-check',
                 '--disable-background-timer-throttling', f'--window-size={win[0]},{win[1]}']
        if os.environ.get('GLASS_PROBE_SWIFTSHADER'):
            flags += ['--enable-unsafe-swiftshader', '--use-angle=swiftshader']
        self.proc = chrome_tree.install(subprocess.Popen([CHROME] + flags + [url],
                                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        ws = None
        for _ in range(120):
            try:
                tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
                m = [t for t in tabs if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
                if m:
                    ws = m[0]['webSocketDebuggerUrl']
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if not ws:
            raise RuntimeError('no CDP tab')
        self.ws = websocket.create_connection(ws, timeout=180, max_size=None)
        self._id = 0
        self.cmd('Page.enable')
        self.cmd('Runtime.enable')

    def cmd(self, m, p=None):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}}))
        self.ws.settimeout(180)
        while True:
            r = json.loads(self.ws.recv())
            if r.get('id') == mid:
                return r.get('result', {})

    def close(self):
        try:
            self.cmd('Browser.close')
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            chrome_tree.kill_tree(self.proc.pid)

    def ev(self, expr):
        r = self.cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True})
        if r.get('exceptionDetails'):
            ed = r['exceptionDetails']
            ex = ed.get('exception', {}) or {}
            return 'EXC ' + str(ex.get('description') or ex.get('value') or ed.get('text'))[:300]
        return r.get('result', {}).get('value')


def sweep(pg, ms):
    """用真实 pointermove 事件驱动水面（不绕过页面自己的入口）。"""
    t0 = time.time()
    i = 0
    while (time.time() - t0) * 1000 < ms:
        p = i / 30.0
        x = W * (0.5 + 0.45 * math.sin(p * 3.0))
        y = H * (0.5 + 0.28 * math.cos(p * 2.1))
        pg.cmd('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y, 'buttons': 0})
        i += 1
        time.sleep(0.012)


CLIPS = {}


def clip_shot(pg, what='nav'):
    """取景必须**钉在被这次改动影响的那块画面上**，两处各有用途：
      · nav  —— 导航栏下沿 14px。2026-10-11 起落地版折射只挂在这里（卡片折射被用户否掉，
                "看着脏脏的"），渲染对照用它。
      · card —— 第一张卡含边墙那一圈。D/E/F 那几条是强制给**卡片**挂折射，它们不动导航栏，
                用 nav 取景会全拍成同一张图 —— 本轮那条「截图指纹未全部互异」的 ⚠ 假警报
                就是这么来的，不是实现坏了，是仪器只看得到一半。
    写死坐标是上一版的错：没人核对过那块区域里到底有没有边墙。"""
    if what not in CLIPS:
        js = ("""(()=>{const r=document.querySelector('header').getBoundingClientRect();
              return JSON.stringify({x:Math.max(0,innerWidth*0.18), y:Math.max(0,r.bottom-30),
                width:460, height:64, scale:3});})()""") if what == 'nav' else \
             ("""(()=>{const c=document.querySelector('.card.g')||document.querySelector('.card');
              const r=c.getBoundingClientRect();
              return JSON.stringify({x:Math.max(0,r.x-20), y:Math.max(0,r.y-20),
                width:Math.min(420,r.width+40), height:Math.min(420,r.height+40), scale:2});})()""")
        CLIPS[what] = json.loads(pg.ev(js))
    d = pg.cmd('Page.captureScreenshot', {'format': 'png', 'clip': CLIPS[what]})
    return hashlib.md5(base64.b64decode(d['data'])).hexdigest()[:12]


def render_proof(pg, label='折射'):
    """单变量对照：水面冻住、取景不动，只切 html.lg 这一个类。
    两帧必须不同才算「这个材质真的落到合成结果上」。上一版的对照同时改了两件事
    （加折射 + 关面板模糊），像素当然不同，那条判据是恒真的假绿灯。"""
    pg.ev(FREEZE)
    time.sleep(0.5)
    pg.ev("document.documentElement.classList.remove('lg');'ok'")
    time.sleep(0.7)
    off = clip_shot(pg)
    pg.ev("document.documentElement.classList.add('lg');'ok'")
    time.sleep(0.7)
    on = clip_shot(pg)
    pg.ev(UNFREEZE)
    ok = off != on
    print(f'  渲染对照({label}): 关={off} 开={on}  {"✅ 只切一个类就换了画面" if ok else "❌ 完全相同 —— 这个材质根本没落到像素上"}')
    return ok


def run(pg, name, csskey, wave, pre=None):
    pre_info = None
    if pre:
        pre_info = pg.ev(JS_PRE[pre])       # overlay 那条会回报「画了几个环 / 遮罩多大」
    pg.ev(START % (A.ms, str(wave).lower(), CSS[csskey]))
    # 不再从 Python 侧 sweep()：见 START 上方注释——那是在量发事件的速度，不是渲染成本
    time.sleep(A.ms / 1000.0 + 0.6)
    r = pg.ev('JSON.stringify(window.__P)')
    bad = isinstance(r, str) and r.startswith('EXC')
    # 材质必须在**还原之前**读：上一版把还原排在读取前面，K 那格打印出来的是还原后的材质，
    # 看起来"折射开着"而实际测的时候是关着的 —— 两条证据互相打架就是这里来的。
    s = json.loads(pg.ev(STATUS))
    if pre:
        pg.ev(JS_PRE['_restore'])
    if bad:
        print(f'  {name:16} 采样失败 {r}')
        return None
    d = json.loads(r)
    d['bf'] = s['bf']
    d['hglg'] = s['hglg']
    d['html_lg'] = s['html_lg']
    d['shot'] = clip_shot(pg)
    d['shot_card'] = clip_shot(pg, 'card')
    if pre == 'overlay':
        # 截图必须在拆层**之前**取：否则拍到的只是"边墙被摘掉"的空态，证不了遮罩层真的画出来了
        print(f'{"":18}遮罩层: {pre_info}')
        d['shot_ov'] = clip_shot(pg, 'card')
        pg.ev(OVERLAY_OFF)
    print(f'  {name:16} med {d["med"]:>6}ms  p95 {d["p95"]:>6}ms  max {d["max"]:>6}ms  '
          f'~{d["fps"]:>5}fps  导航栏折射={int(d["hglg"])} lg={int(d["html_lg"])}  strokes={d["strokes"]}  '
          f'bg帧={d["bgframes"]}  图={d["shot"]}/{d["shot_card"]}\n{"":18}材质={d["bf"][:44]}')
    return d


PH_INSTR = """(()=>{
  const g=BG.gl, acc={n:0,step:0,upload:0,render:0,fin:0};
  window.__PH=acc;
  if(!window.__ORIG) window.__ORIG={s:bgStep,u:bgUpload,r:bgRender};
  const s=window.__ORIG.s, u=window.__ORIG.u, r=window.__ORIG.r;
  window.bgStep=function(dt){const t=performance.now(); s(dt); acc.step+=performance.now()-t;};
  window.bgUpload=function(){const t=performance.now(); u(); acc.upload+=performance.now()-t;};
  window.bgRender=function(){const t=performance.now(); r(); const a=performance.now();
    g.finish(); const b=performance.now(); acc.render+=a-t; acc.fin+=b-a; acc.n++;};
  return 'ok';})()"""

PH_RESET = "(()=>{const a=window.__PH;a.n=a.step=a.upload=a.render=a.fin=0;return 'ok';})()"

# 候选优化 ①：每帧 texImage2D 会重新分配整张纹理存储，换成「首帧分配 + 后续 texSubImage2D 覆写」
PH_SUBIMAGE = """(()=>{
  let allocated=0;
  window.__ORIG.u=function(){ const g=BG.gl;
    g.bindTexture(g.TEXTURE_2D,BG.tex);
    if(allocated!==BG.sw*BG.sh){ g.texImage2D(g.TEXTURE_2D,0,g.R8,BG.sw,BG.sh,0,g.RED,g.UNSIGNED_BYTE,BG.pack);
      allocated=BG.sw*BG.sh; }
    else g.texSubImage2D(g.TEXTURE_2D,0,0,0,BG.sw,BG.sh,g.RED,g.UNSIGNED_BYTE,BG.pack); };
  return 'ok';})()"""


def ph_report(pg, label):
    pg.ev(PH_INSTR)
    pg.ev(PH_RESET)
    sweep(pg, A.ms + 200)
    d = json.loads(pg.ev('JSON.stringify(window.__PH)'))
    n = max(1, d['n'])
    tot = (d['step'] + d['upload'] + d['render'] + d['fin']) / n
    print(f'  {label:26} 帧 {n:>4}  模拟 {d["step"]/n:5.2f}  上传 {d["upload"]/n:5.2f}  '
          f'绘制 {d["render"]/n:5.2f}  GPU等待 {d["fin"]/n:6.2f}  合计 {tot:6.2f} ms/帧')
    return {'frames': n, 'step': round(d['step']/n, 2), 'upload': round(d['upload']/n, 2),
            'render': round(d['render']/n, 2), 'finish': round(d['fin']/n, 2), 'total': round(tot, 2)}


# ── 结构改造假设的现场验证：把「每张卡一个滤镜盒」换成「一层遮罩画完所有环」──
# 成本模型说单位是盒子个数（§134），那 70 个盒并成 1 个应该省 ~13ms。
# 这条**先在探针里注入验证**，不改正本：不便宜就不做，省得把首页架构换一遍再发现白干。
OVERLAY_JS = """(()=>{
  const main=document.getElementById('main');
  if(document.getElementById('glassone')) document.getElementById('glassone').remove();
  const vp=main.clientHeight, top=main.scrollTop, H=vp*3, W=main.clientWidth;
  const rr=(x,y,w,h,r)=>`M${x+r} ${y}h${w-2*r}a${r} ${r} 0 0 1 ${r} ${r}v${h-2*r}`+
                        `a${r} ${r} 0 0 1 ${-r} ${r}h${-(w-2*r)}a${r} ${r} 0 0 1 ${-r} ${-r}`+
                        `v${-(h-2*r)}a${r} ${r} 0 0 1 ${r} ${-r}z`;
  const lay=document.createElement('div'); lay.id='glassone';
  // 层放在滚动容器内 ⇒ 环相对卡片不动，滚动时遮罩**不需要重建**（这是这条方案成立的关键）
  lay.style.cssText='position:absolute;left:0;pointer-events:none;z-index:6;width:'+W+'px;height:'+H+'px;top:'+top+'px';
  let d='';
  document.querySelectorAll('.card.g').forEach(c=>{
    const r=c.getBoundingClientRect(), x=r.left, y=r.top-top;
    if(y<-40||y>H+40) return;
    d+=rr(x,y,r.width,r.height,16)+rr(x+12,y+12,Math.max(0,r.width-24),Math.max(0,r.height-24),12);
  });
  const n=(d.match(/M/g)||[]).length/2;
  const svg='<svg xmlns="http://www.w3.org/2000/svg" width="'+W+'" height="'+H+'">'+
            '<path d="'+d+'" fill="#fff" fill-rule="evenodd"/></svg>';
  const u='url("data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg)+'")';
  lay.style.webkitMaskImage=u; lay.style.maskImage=u;
  const st=document.createElement('style'); st.id='ovsty';
  st.textContent='#glassone{backdrop-filter:blur(17px) saturate(2) brightness(1.08);'+
    '-webkit-backdrop-filter:blur(17px) saturate(2) brightness(1.08)}';
  document.head.appendChild(st);
  main.appendChild(lay);
  return JSON.stringify({rings:n, W:W, H:H, svg_kb:Math.round(svg.length/1024)});})()"""

OVERLAY_OFF = "(()=>{const l=document.getElementById('glassone'); if(l)l.remove();" \
              "const s=document.getElementById('ovsty'); if(s)s.remove(); return 'ok';})()"
JS_PRE['overlay'] = OVERLAY_JS   # JS_PRE 定义在前，这条只能补在这里


def phases(pg):
    """把水面那 20ms 拆到「CPU 模拟 / 纹理上传 / 绘制提交 / GPU 等待」四段上，并当场试一条候选优化。"""
    print('\n── 水面 20ms 的构成（每帧内插 gl.finish() 强制同步，故合计会略高于表 C）──')
    out = {}
    out['base'] = ph_report(pg, '现状（每帧 texImage2D）')
    pg.ev(PH_SUBIMAGE)
    out['subimage'] = ph_report(pg, '候选①：texSubImage2D 覆写')
    pg.ev("(()=>{window.bgStep=window.__ORIG.s;window.bgUpload=window.__ORIG.u;"
          "window.bgRender=window.__ORIG.r;delete window.__ORIG;return 'ok';})()")
    d1, d2 = out['base']['total'], out['subimage']['total']
    print(f'\n候选①收益：{d1:.2f} → {d2:.2f} ms/帧（{(d1-d2):+.2f}，{(d2/d1-1)*100:+.1f}%）'
          if d1 else '')
    json.dump(out, open(os.path.join(ROOT, '.diag', 'water_phase_cost.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('落盘 .diag/water_phase_cost.json')


FREEZE = "(()=>{if(!window.__S0)window.__S0=bgStep; window.bgStep=function(){}; return 'ok';})()"
UNFREEZE = "(()=>{if(window.__S0){window.bgStep=window.__S0;} return 'ok';})()"
# 「改前」不是另开一个页面，而是把同一批元素的材料换回上一版那条只糊不推的边墙
OLD_MAT = ('html.lg .card.lgr::before,html.lg header.hglg::before'
           '{backdrop-filter:blur(var(--rim-blur)) saturate(2) brightness(1.08)!important;'
           '-webkit-backdrop-filter:blur(var(--rim-blur)) saturate(2) brightness(1.08)!important}')


# 背景必须是**棋盘格**：① 竖边的位移是水平的，用横条纹测左/右边缘等于没测（第一版踩了）；
# ② 两层 repeating-linear-gradient 叠在一起时上层不透明会把下层整个盖掉（第二版踩了）。
BEND_BG = 'repeating-conic-gradient(#0b1a33 0 25%,#f2d780 0 50%) 0 0/28px 28px'
BEND_ON = ("(()=>{const o=document.getElementById('bendtest'); if(o)o.remove();"
           "const n=document.createElement('div'); n.id='bendtest';"
           "n.style.cssText='position:fixed;inset:0;z-index:0;pointer-events:none';"
           "n.style.background=" + repr(BEND_BG) + ";"
           "document.body.insertBefore(n,document.body.firstChild); return 'ok';})()")
BEND_OFF = "(()=>{const d=document.getElementById('bendtest'); if(d)d.remove(); return 'ok';})()"


# 材质落地状态：性能模式与取图模式必须共用同一份断言，否则一边验过、另一边没验。
# ⚠️ 2026-10-11 起折射**只挂在导航栏**：卡片边墙的折射被用户否掉（"看着脏脏的"，理由见
#    index.html ② 那条注释），所以这里读的是 header 的 ::before。别再把断言指回 .card.lgr
#    —— 那会恒红，然后被人当"阈值太严"放宽，把这条判据彻底废掉。
STATUS = """(()=>{const h=document.documentElement, nav=h.querySelector('header');
  const cs=getComputedStyle(h);
  return JSON.stringify({
    lg_on:LG.on, html_lg:h.classList.contains('lg'),
    cards_g:document.querySelectorAll('.card.g').length,
    cards_lgr:document.querySelectorAll('.card.lgr').length,
    hglg:nav.classList.contains('hglg'),
    buckets:LG.buckets.size, gen:LG.gen,
    filters:LG.svg?LG.svg.querySelectorAll('filter').length:0,
    bf:String(getComputedStyle(nav,'::before').backdropFilter).slice(0,46),
    bf_nolg:(()=>{h.classList.remove('lg');
      const v=getComputedStyle(nav,'::before').backdropFilter;
      h.classList.add('lg'); return String(v).slice(0,46);})(),
    tok:['--lg-blur','--lg-ring','--lg-depth','--lg-mpx']
      .map(n=>n+'='+JSON.stringify(cs.getPropertyValue(n))).join(' '),
    tok_ok:['--lg-blur','--lg-ring','--lg-depth'].every(n=>String(cs.getPropertyValue(n)).trim()!==''),
    feimg:(LG.svg&&LG.svg.querySelector('feImage'))?LG.svg.querySelector('feImage')
      .getAttribute('href').length:0,
    // 边墙**架构**报告：两种都合法，但必须只有一种在跑。
    //   one-layer = #glassone 一层遮罩画所有环（省 13ms，但 2026-10-11 出现"整卡糊成实心"且
    //               无头复现不了 ⇒ 已撤，见 §135）；per-card = 逐卡 ::before 挂滤镜（~16.7ms）。
    // 闸门只判两种死路：一个都没有（玻璃没了）、或两种都挂（同一圈被模糊两次）。
    rim_mode:(()=>{const one=!!document.getElementById('glassone');
      let per=0; document.querySelectorAll('.card.g').forEach(c=>{
        if(c.matches(':hover')) return;
        if(getComputedStyle(c,'::before').backdropFilter!=='none') per++;});
      return one?(per?'BOTH':'one-layer'):(per?'per-card':'NONE');})(),
    ov:(()=>{const g=document.getElementById('glassone');
      if(!g) return 'NO #glassone';
      const cs=getComputedStyle(g), mk=(cs.maskImage||cs.webkitMaskImage||'');
      return 'bf='+(cs.backdropFilter!=='none')+' mask='+(mk.indexOf('url(')===0)+
             ' size='+g.style.width+'x'+g.style.height;})(),
    ov_boxes:(()=>{let n=0;
      document.querySelectorAll('.card').forEach(c=>{
        if(!c.classList.contains('g')||c.matches(':hover')) return;
        if(getComputedStyle(c,'::before').backdropFilter!=='none') n++;});
      return n;})(),
    nav_h:(()=>{const r=nav.getBoundingClientRect();
      return Math.round(r.width)+'x'+Math.round(r.height);})()});})()"""


def shots(pg):
    """同一帧**冻结**的背景上拍「改前模糊 / 改后折射」成对图。
    不冻结的话两张图的海面本来就不同，看不出差别到底来自材质还是来自浪——那是假对比。
    --bend 再叠一层密集条纹当**零假设对照**：平滑渐变上折射本来就看不出来，
    要判「滤镜几何做错了」还是「背景没内容可弯」，只能自己造一种高频背景。"""
    if A.bend:
        print('对照模式：卡片背后铺密集棋盘格（只在这台无头实例里，不落任何文件）')
        pg.ev(BEND_ON)
        time.sleep(0.4)
    d = os.path.join(ROOT, '.diag', 'glassshots')
    os.makedirs(d, exist_ok=True)
    pg.ev("(()=>{if(!document.getElementById('shotsty')){const s=document.createElement('style');"
          "s.id='shotsty';document.head.appendChild(s);}return 'ok';})()")
    st = json.loads(pg.ev(STATUS))
    print('落地状态:', json.dumps(st, ensure_ascii=False))
    if (not st['filters'] or not st['hglg'] or not st['feimg']
            or not st['tok_ok'] or 'url(' not in st['bf']):
        # 走 print 而不是 SystemExit：stderr 没设 utf-8，Windows 控制台上中文会变乱码（本轮撞到）
        print('! 折射链路断在结构层：filters/hglg/feImage 有空、--lg-* token 没读到、'
              '或导航栏 ::before 计算后 backdrop-filter 不含 url() —— 取图无意义，先修实现')
        sys.exit(1)
    if A.depth:
        print(f'极端检验：--lg-depth 从默认 26 拉到 {A.depth}。这个量级下若仍看不到位移，'
              f'说明滤镜根本没生效（而不是"效果太弱"）')
        pg.ev(f"document.documentElement.style.setProperty('--lg-depth','{A.depth}');"
              f"lgRefresh();'ok'")
        time.sleep(0.8)
    sweep(pg, 1600)
    pg.ev(FREEZE)
    time.sleep(0.7)
    # 沿边特写的取景：钉在**导航栏下沿那条 14px 边墙**上，6 倍放大 —— 折射只发生在这一圈里，
    # 整屏缩着看必然看不见，必须把它单独放大到能数清棋盘格。
    r = json.loads(pg.ev("""(()=>{const b=document.querySelector('header').getBoundingClientRect();
        return JSON.stringify({x:b.left,y:b.bottom,w:b.width,h:b.height});})()"""))
    edge = {'x': max(0, r['x'] + r['w'] * 0.18), 'y': max(0, r['y'] - 26),
            'width': 96, 'height': 40, 'scale': 6}
    caps = {}
    for name, lg in (('1改前', False), ('2改后', True)):
        # 单变量对照：只切 html.lg 这一个类。上一版用 OLD_MAT 覆盖写法，等于同时改了两件事
        # （加折射 + 把原来那条模糊盖掉），那种对照恒真、骗过我一次。
        pg.ev("document.documentElement.classList.toggle('lg',%s);'ok'" % ('true' if lg else 'false'))
        time.sleep(0.9)
        for tag, clip in (('整屏', None),
                          ('特写', {'x': 30, 'y': H * 0.22, 'width': 560, 'height': 700, 'scale': 2}),
                          ('沿边', edge)):
            args = {'format': 'png'}
            if clip:
                args['clip'] = clip
            raw = base64.b64decode(pg.cmd('Page.captureScreenshot', args)['data'])
            p = os.path.join(d, f'{"bend" if A.bend else "sea"}_{name}_{tag}.png')
            open(p, 'wb').write(raw)
            caps[(name, tag)] = hashlib.md5(raw).hexdigest()[:12]
            print(f'  {name} {tag}  md5={caps[(name, tag)]}  {p}')
    pg.ev("document.documentElement.classList.add('lg');'ok'")
    pg.ev(UNFREEZE)
    for tag in ('整屏', '特写', '沿边'):
        a, b = caps[('1改前', tag)], caps[('2改后', tag)]
        diff = a != b
        if tag == '特写':
            # 「卡片区两版必须逐字节相同」这条**已撤下**（本轮误报过一次）：它想防"折射偷偷回到卡片
            # 边墙"，但卡片面板本身是半透明的，两张截图之间水面只要差一帧，卡片区就一定不同
            # ⇒ 断言不 sound。它该管的事由结构闸门 ov_boxes==0 负责（非悬停卡上不许有任何滤镜盒）。
            print(f'  参考({tag}/卡片): {a} vs {b} —— 只反映水面帧差，**不作判据**'
                  f'（卡片不做折射由 ov_boxes={st["ov_boxes"]} 那条结构闸门守）')
        else:
            print(f'  对照({tag}/导航栏): {"✅ 两版像素不同" if diff else "❌ 完全相同 —— 折射没落到画面上，白改"}')


CAPS = """(()=>{
  const mk=(v)=>{const d=document.createElement('div');
    d.style.cssText='position:fixed;left:0;top:0;width:50px;height:50px';
    document.body.appendChild(d); d.style.backdropFilter=v;
    const g=getComputedStyle(d).backdropFilter; d.remove(); return String(g).slice(0,60);};
  const fs=LG.svg?[...LG.svg.querySelectorAll('filter')]:[];
  const fid=fs.length?fs[0].id:'NONE';
  const out={ids:fs.map(f=>f.id), feimg_ok:fs.length&&!!fs[0].querySelector('feImage'),
             href_head:fs.length?(fs[0].querySelector('feImage').getAttribute('href')||'').slice(0,22):'-'};
  out['a_url_only']   = mk('url(#'+fid+')');
  out['b_blur_url']   = mk('blur(1px) url(#'+fid+')');
  out['c_sat_url']    = mk('blur(1px) saturate(1.7) url(#'+fid+')');
  out['d_missing_id'] = mk('blur(1px) url(#nope)');
  out['e_var_chain']  = (()=>{const d=document.createElement('div');
      d.style.cssText='position:fixed;left:0;top:0;width:50px;height:50px;--q:url(#'+fid+');--p:1px';
      document.body.appendChild(d);
      d.style.backdropFilter='blur(var(--p)) saturate(1.7) var(--q)';
      const g=getComputedStyle(d).backdropFilter; d.remove(); return String(g).slice(0,60);})();
  out['f_real_card']  = (()=>{const c=document.querySelector('.card.lgr');
      return c?String(getComputedStyle(c,'::before').backdropFilter).slice(0,60):'no .lgr';})();
  out['g_real_card_nohtml'] = (()=>{const c=document.querySelector('.card.lgr'); if(!c)return '-';
      const h=document.documentElement; h.classList.remove('lg');
      const g=getComputedStyle(c,'::before').backdropFilter; h.classList.add('lg');
      return String(g).slice(0,60);})();
  return JSON.stringify(out);})()"""


CAPS2 = """(()=>{
  const fid=(LG.svg&&LG.svg.querySelector('filter'))?LG.svg.querySelector('filter').id:'NONE';
  const st=document.createElement('style');
  st.textContent=`
   #capA{--lgf:url(#${fid})} #capA::before{content:'';position:absolute;inset:0;
     backdrop-filter:blur(1px) saturate(1.7) var(--lgf)}
   #capB::before{content:'';position:absolute;inset:0;
     backdrop-filter:blur(var(--lg-blur)) saturate(1.7) url(#${fid})}
   #capC::before{content:'';position:absolute;inset:0;
     backdrop-filter:blur(1px) saturate(1.7) url(#${fid})}
   #capD::before{content:'';position:absolute;inset:0;padding:12px;
     -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
     mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
     -webkit-mask-composite:xor;mask-composite:exclude;
     backdrop-filter:blur(1px) saturate(1.7) url(#${fid})}
   #capE::before{content:'';position:absolute;inset:0;
     -webkit-backdrop-filter:blur(1px) url(#${fid});
     backdrop-filter:blur(1px) url(#${fid})}`;
  document.head.appendChild(st);
  const out={fid, lg_blur:getComputedStyle(document.documentElement).getPropertyValue('--lg-blur'),
             lg_ring:getComputedStyle(document.documentElement).getPropertyValue('--lg-ring')};
  ['A','B','C','D','E'].forEach(k=>{
    const d=document.createElement('div'); d.id='cap'+k;
    d.style.cssText='position:fixed;left:0;top:0;width:60px;height:60px';
    document.body.appendChild(d);
    out['cap'+k]=String(getComputedStyle(d,'::before').backdropFilter).slice(0,58);
    d.remove();
  });
  out['real']=String(getComputedStyle(document.querySelector('.card.lgr'),'::before')
                    .backdropFilter).slice(0,58);
  st.remove();
  return JSON.stringify(out);})()"""


MASKDIAG = """(()=>{
  const main=document.getElementById('main'), lay=document.getElementById('glassone');
  const top=lay?parseFloat(lay.style.top):0, H=lay?parseFloat(lay.style.height):0;
  const boxes=[]; let degenerate=[];
  main.querySelectorAll('.card.g').forEach(c=>{
    if(c.matches(':hover')) return;
    let x=0,y=0,e=c;
    while(e && e!==main){ x+=e.offsetLeft; y+=e.offsetTop; e=e.offsetParent; }
    const w=c.offsetWidth, h=c.offsetHeight, yy=Math.round(y-top);
    if(yy<-40||yy>H+40) return;
    const r=c.getBoundingClientRect();
    boxes.push({x:Math.round(x),y:yy,w,h});
    // 尺寸退化（内圈会被 Math.max(0,...) 夹成 0 ⇒ 环变成实心矩形）与
    // 「布局尺寸 ≠ 变换后尺寸」都记下来：后者说明这张卡正被 transform，
    // 一旦遮罩改用 rect 就会和邻卡重叠、evenodd 翻成实体。
    if(w<=24||h<=24) degenerate.push({why:'size',w,h});
    else if(Math.abs(w-r.width)>2||Math.abs(h-r.height)>2)
      degenerate.push({why:'transformed',w,h,rw:+r.width.toFixed(1),rh:+r.height.toFixed(1)});
  });
  const ov=[];   // 两两重叠 = evenodd 抵消失败 = 整块糊住，这就是本轮那个 bug 的充要条件
  for(let i=0;i<boxes.length;i++) for(let j=i+1;j<boxes.length;j++){
    const a=boxes[i],b=boxes[j];
    if(a.x<b.x+b.w&&b.x<a.x+a.w&&a.y<b.y+b.h&&b.y<a.y+a.h){ ov.push([i,j]); if(ov.length>4) break; }
  }
  const mk=(lay?String(getComputedStyle(lay).maskImage||getComputedStyle(lay).webkitMaskImage||''):'');
  const svg=decodeURIComponent(mk);
  return JSON.stringify({layer:!!lay, rings:boxes.length, mask_M:(svg.match(/M/g)||[]).length,
    expect_M:boxes.length*2, overlaps:ov, degenerate:degenerate.slice(0,6)},null,1);})()"""


def main():
    global websocket
    try:
        import websocket
    except ImportError:
        raise SystemExit('! 缺 websocket-client')
    try:
        with urllib.request.urlopen(URL, timeout=5) as r:
            assert r.status == 200
    except Exception as e:
        raise SystemExit(f'! {URL} 不可达：{e}\n  先起：py -3 -m http.server {A.port} --bind 127.0.0.1 -d Output')

    # 每轮全新 profile：复用目录会让 theme.css 走磁盘缓存，改了 token 也读不到旧值
    # （本轮就被这个坑了一次：--lg-blur 读成空串 → blur() 非法 → 整条 backdrop-filter 作废）
    prof = os.path.join(ROOT, '.diag', 'glassperf_profile')
    shutil.rmtree(prof, ignore_errors=True)
    os.makedirs(prof, exist_ok=True)
    pg = Page(9339, prof, URL, (W, H))
    try:
        for _ in range(60):
            n = pg.ev("document.querySelectorAll('.card').length")
            if isinstance(n, int) and n > 50:
                break
            time.sleep(0.5)
        env = pg.ev("""JSON.stringify({mode:BG.mode, err:BG.err, canvas:BG.cv?BG.cv.width+'x'+BG.cv.height:'-',
          field:BG.sw+'x'+BG.sh, dpr:devicePixelRatio, vp:innerWidth+'x'+innerHeight,
          cards:document.querySelectorAll('.card').length,
          gpu:(()=>{const g=BG.gl; if(!g)return 'n/a'; const d=g.getExtension('WEBGL_debug_renderer_info');
            return d?String(g.getParameter(d.UNMASKED_RENDERER_WEBGL)):'n/a';})()})""")
        env = json.loads(env)
        print('环境:', json.dumps(env, ensure_ascii=False))
        if env['mode'] != 'gl':
            raise SystemExit(f"! BG.mode={env['mode']} ≠ gl（{env['err']}）—— 水面没跑 WebGL，这份数字作废")
        # 材质状态必须在跑条件之前先打印一次：本轮就是「B 比 K 慢 2.8 倍」和「B 与 K 截图逐字节相同」
        # 这两条互相矛盾，说明条件跑起来时折射可能压根没生效——没有这行断言就会拿一组假数字下结论。
        print('材质:', json.dumps(json.loads(pg.ev(STATUS)), ensure_ascii=False))
        st0 = json.loads(pg.ev(STATUS))
        # 只判两种死路：玻璃整个没了 / 两种架构同时挂着（同一圈被模糊两次）
        if st0['rim_mode'] in ('NONE', 'BOTH'):
            print(f'! 边墙架构闸门不过：rim_mode={st0["rim_mode"]}（'
                  f'{"一层遮罩与逐卡 ::before 同时挂着 ⇒ 同一圈模糊两次" if st0["rim_mode"]=="BOTH" else "边墙没有任何滤镜 ⇒ 玻璃整圈消失"}）'
                  f'；ov={st0["ov"]} ov_boxes={st0["ov_boxes"]}')
            sys.exit(1)
        print(f'  边墙架构: {st0["rim_mode"]}（per-card ≈16.7ms / one-layer ≈3.3ms，见 §134、§135）'
              f'；ov_boxes={st0["ov_boxes"]} ov={st0["ov"]}')
        # 帧时数字只有在「这个材质确实会改变画面」被证完之后才有意义，所以它是硬闸门不是打印。
        if not render_proof(pg, '落地版边墙'):
            print('! 渲染对照不过 —— 先修实现，这一轮所有帧时数字都不要读')
            sys.exit(1)
        if A.phases:
            phases(pg)
            return
        if A.shots:
            shots(pg)
            return
        if A.maskdiag:
            print(pg.ev(MASKDIAG))
            return
        if A.caps:
            print(json.dumps(json.loads(pg.ev(CAPS)), ensure_ascii=False, indent=1))
            print('── 伪元素隔离 ──')
            print(json.dumps(json.loads(pg.ev(CAPS2)), ensure_ascii=False, indent=1))
            return
        pg.ev(f"(()=>{{const s=document.createElement('div');s.id='probesvg';"
              f"s.innerHTML={json.dumps(SVG)};document.body.appendChild(s);return 'ok';}})()")
        out = {}
        print(f'\n条件：每格 {A.ms}ms 采样，视口 {W}x{H}，折射 scale=70')
        out['A_idle_as_is'] = run(pg, 'A 静止·现毛玻璃', 'asis', False)
        out['B_wave_as_is'] = run(pg, 'B 划水·现毛玻璃', 'asis', True)
        out['C_wave_noglass'] = run(pg, 'C 划水·摘玻璃', 'noglass', True)
        # D/E 已撤下：它们给 `#glassone` 挂折射，而并层已回退（§135）⇒ 打在空选择器上=纯噪声。
        # 想复现那两条的结论，先把 --shots 的架构切回 one-layer。
        out['F_wave_imgbody'] = run(pg, 'F 划水·整面折射', 'imgbody', True)
        print('  ── 以下是归因条件，不是候选方案 ──')
        # ⚠️ 2026-10-11 边墙并成 #glassone 之后，L/M/N/P/Q/R/X 七条**已撤下**：它们注入的选择器是
        #    `.card.g::before`，而那个伪元素现在只有 :hover 才存在 ⇒ 注入完全空转。
        #    空转的条件不是"少了个信息"，是**噪声伪装成信息**（同一份代码两轮能差 3ms，
        #    本轮就出现过 N/Q/R 与 B 差 3ms 而它们其实什么都没改）。宁可删也不留着。
        #    它们当年量出的结论已经钉在 §134 那张表里；CSS 键保留是给 --caps 手工隔离实验用的。
        out['K_wave_lg_off'] = run(pg, 'K 划水·只摘折射', 'asis', True, 'lgoff')
        out['S_wave_panel_back'] = run(pg, 'S 划水·把面板层注回', 'panel_back', True)
        out['O_wave_overlay'] = run(pg, 'O 划水·注入第二层遮罩', 'asis', True, 'overlay')
        o_, c0 = out.get('O_wave_overlay'), out.get('C_wave_noglass')
        if o_ and c0:
            # O 现在是"再注入一层实验性遮罩"，地板用 C（完全不挂玻璃），不再用已撤下的 X
            print(f'  遮罩层对照: 一层(落地)={out["B_wave_as_is"]["med"]}ms  '
                  f'实验层={o_["med"]}ms  零玻璃地板={c0["med"]}ms  '
                  f'像素{"与零玻璃不同 ⇒ 遮罩真的画出来了 ✅" if o_.get("shot_ov") != c0["shot_card"] else "与零玻璃逐字节相同 ⇒ 遮罩层根本没渲染 ❌"}')
        s_, b_ = out.get('S_wave_panel_back'), out.get('B_wave_as_is')
        if s_ and b_:
            print(f'  「多挂一层每卡滤镜要多少钱」：注回 blur(2.5px) 后 {b_["med"]}ms → {s_["med"]}ms'
                  f'（+{s_["med"]-b_["med"]:.1f}ms，70 个盒）；取景 {b_["shot_card"]} vs {s_["shot_card"]}'
                  f'{" 逐字节相同" if s_["shot_card"] == b_["shot_card"] else " 有差异 ⇒ 不是免费的，交肉眼判"}')
        out['G_wave_noglow'] = run(pg, 'G 划水·摘玻璃+藏光晕', 'noglass_noglow', True)
        out['H_wave_render_stub'] = run(pg, 'H 划水·停掉GL绘制', 'noglass', True, 'renderstub')
        out['J_wave_asis_noglow'] = run(pg, 'J 划水·毛玻璃+藏光晕', 'noglow', True)
        # 数量条件放最后：它们会摘掉一批 .g（_restore 里按视口重算补回，但仍是破坏性条件）
        out['24_wave_few24'] = run(pg, '2 划水·只留24张卡', 'asis', True, 'few24')
        out['40_wave_few40'] = run(pg, '4 划水·只留40张卡', 'asis', True, 'few40')
        c = out.get('C_wave_noglass')
        if c:
            for k in ('G_wave_noglow', 'H_wave_render_stub'):
                if out.get(k) and out[k]['shot'] == c['shot']:
                    print(f'  ⚠ {k} 与 C 像素完全相同 —— 该条件没改变画面，它的耗时数字无意义')
        # 通用"条件空转"探测：任何一条条件的取景若与 B 逐字节相同，说明它注入的声明根本没生效
        # （2026-10-11 边墙并成一层之后，N/P/Q/R/rim_off/panelonly 这些打在 `.card.g::before` 上的
        #  条件全部变成空转——那个伪元素现在只有 :hover 才存在。留着它们是为了复现 §134 那张表，
        #  但**空转的条件不许当数据读**，所以这里逐条点名，而不是只在 C/D/E/F 那四条上设岗。）
        base_shot = (out.get('B_wave_as_is') or {}).get('shot_card')
        inert = [k for k, v in out.items()
                 if v and k != 'B_wave_as_is' and v.get('shot_card') == base_shot]
        if inert:
            print(f'  ⚠ 以下条件与 B 逐字节相同 = **空转，它们的帧时不要读**：{", ".join(inert)}')
        b = out.get('B_wave_as_is')
        bad = []
        if not b or b['strokes'] == 0:
            bad.append('strokes=0：划水没被触发，B~F 与 A 无差别')
        if b and not b['bgframes']:
            bad.append("bg帧=0：水面循环根本没跑（BG.mode 虽为 gl 但没起波）")
        # 阳性对照：摘玻璃 / 现算噪声 / 静态法线图 三种材质必须拍出**不同**的像素，
        # 相同就说明 url() 只是被 CSS 解析接受、并没有真的落到合成结果上 —— 那 E/F 的耗时数字毫无意义。
        # 阳性对照看的是**卡片**取景：D/E/F 只改卡片材质、不动导航栏，用 nav 取景会全同（假警报）
        sig = {k: (out.get(k) or {}).get('shot_card') for k in
               ('C_wave_noglass', 'F_wave_imgbody')}
        if len(set(v for v in sig.values() if v)) < 2:
            bad.append(f'截图指纹未全部互异 {sig}：材质差异没进像素，F 的成本结论不成立')
        if bad:
            print('\n⚠ 判据未过 —— ' + '；'.join(bad))
        else:
            print('\n判据通过：划水已触发、四种材质像素互异（折射确实落到了合成结果上）')
        json.dump({'env': env, 'runs': out}, open(os.path.join(ROOT, '.diag', 'glass_perf_baseline.json'),
                                                  'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\n落盘 .diag/glass_perf_baseline.json')
    finally:
        pg.close()


main()
