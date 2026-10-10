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
    'turb': ('.card.g{-webkit-backdrop-filter:none!important;backdrop-filter:none!important}'
             '.card.g::before{-webkit-backdrop-filter:blur(1px) url(#pTurb)!important;'
             'backdrop-filter:blur(1px) url(#pTurb)!important}'),
    # E：折射用静态法线图查表——真方案
    'img': ('.card.g{-webkit-backdrop-filter:none!important;backdrop-filter:none!important}'
            '.card.g::before{-webkit-backdrop-filter:blur(1px) url(#pImg)!important;'
            'backdrop-filter:blur(1px) url(#pImg)!important}'),
    # F：整张卡面板也折射（最坏情况）
    'imgbody': ('.card.g{-webkit-backdrop-filter:blur(2px) url(#pImg)!important;'
                'backdrop-filter:blur(2px) url(#pImg)!important}'
                '.card.g::before{-webkit-backdrop-filter:blur(1px) url(#pImg)!important;'
                'backdrop-filter:blur(1px) url(#pImg)!important}'),
    # L：只留边墙折射，把面板那层 blur(2.5px) 摘掉 —— 验「一张卡两层滤镜 → 一层」能省多少
    'rimonly': '.card.g{-webkit-backdrop-filter:none!important;backdrop-filter:none!important}',
    # M：只留面板那层模糊，把边墙整个摘掉 —— 与 L 配对，看这两层各值多少钱
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
}

# H：把 GL 绘制整个停掉（canvas 不再产生新帧）—— 用来判「20ms 是 canvas 重绘带出来的，
#    还是 DOM 自己的」。必须能红：若这条例同 20ms，说明跟 canvas 无关。
JS_PRE = {
    'renderstub': "(()=>{if(!window.__R0)window.__R0=bgRender; window.bgRender=function(){}; return 'ok';})()",
    # K：只把折射摘掉（html.lg 一去掉，②-b 那条规则就不匹配，边墙自动退回上一版那条模糊）
    # —— 这才是「新效果比旧效果贵多少」的正确对照，C 那条把模糊也一起摘了，量的是别的东西。
    'lgoff': "(()=>{document.documentElement.classList.remove('lg'); return 'ok';})()",
    '_restore': "(()=>{if(window.__R0){window.bgRender=window.__R0;}"
                "document.documentElement.classList.add('lg'); return 'ok';})()",
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


CLIP = None


def clip_shot(pg):
    """取景必须**钉在某张卡的边墙上**：上一版写死在 (2%, 42%) 那块，落点是不是真有卡片边缘
    没人核对过，于是「三格截图逐字节相同」这种结果既可能是折射没渲染，也可能只是取到了一片
    没有边的背景——仪器本身不成立，任何结论都推不出来。"""
    global CLIP
    if CLIP is None:
        CLIP = json.loads(pg.ev("""(()=>{const c=document.querySelector('.card.lgr')
              ||document.querySelector('.card'); const r=c.getBoundingClientRect();
            return JSON.stringify({x:Math.max(0,r.x-26), y:Math.max(0,r.y-26),
              width:Math.min(460,r.width+52), height:Math.min(460,r.height+52), scale:2});})()"""))
    d = pg.cmd('Page.captureScreenshot', {'format': 'png', 'clip': CLIP})
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
    if pre:
        pg.ev(JS_PRE[pre])
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
    d['lgr'] = s['lgr']
    d['html_lg'] = s['html_lg']
    d['shot'] = clip_shot(pg)
    print(f'  {name:16} med {d["med"]:>6}ms  p95 {d["p95"]:>6}ms  max {d["max"]:>6}ms  '
          f'~{d["fps"]:>5}fps  lgr={d["lgr"]} lg={int(d["html_lg"])}  strokes={d["strokes"]}  '
          f'bg帧={d["bgframes"]}  图={d["shot"]}\n{"":18}材质={d["bf"][:44]}')
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
STATUS = """(()=>{const h=document.documentElement, c0=document.querySelector('.card.lgr');
  const cs=getComputedStyle(h);
  return JSON.stringify({
    lg_on:LG.on, html_lg:h.classList.contains('lg'),
    cards_g:document.querySelectorAll('.card.g').length,
    lgr:document.querySelectorAll('.card.lgr').length,
    buckets:LG.buckets.size, gen:LG.gen,
    filters:LG.svg?LG.svg.querySelectorAll('filter').length:0,
    nav:h.querySelector('header').classList.contains('hglg'),
    bf:c0?String(getComputedStyle(c0,'::before').backdropFilter).slice(0,46):'no .lgr',
    bf_nolg:(()=>{const c=document.querySelector('.card.g'); if(!c)return 'no .g';
      h.classList.remove('lg'); const v=getComputedStyle(c,'::before').backdropFilter;
      h.classList.add('lg'); return String(v).slice(0,46);})(),
    tok:['--lg-blur','--lg-ring','--lg-depth'].map(n=>n+'='+JSON.stringify(cs.getPropertyValue(n))).join(' '),
    tok_ok:['--lg-blur','--lg-ring','--lg-depth'].every(n=>String(cs.getPropertyValue(n)).trim()!==''),
    feimg:(LG.svg&&LG.svg.querySelector('feImage'))?LG.svg.querySelector('feImage')
      .getAttribute('href').length:0,
    size:(()=>{const c=document.querySelector('.card');const r=c.getBoundingClientRect();
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
    if (not st['filters'] or not st['nav'] or not st['lgr'] or not st['feimg']
            or not st['tok_ok'] or 'url(' not in st['bf']):
        # 走 print 而不是 SystemExit：stderr 没设 utf-8，Windows 控制台上中文会变乱码（本轮撞到）
        print('! 折射链路断在结构层：filters/nav/lgr/feImage 有空、--lg-* token 没读到、'
              '或 ::before 计算后 backdrop-filter 不含 url() —— 取图无意义，先修实现')
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
    # 沿边特写的取景：钉在第一张卡的**左边缘中段**，6 倍放大 —— 折射只发生在 12px 环带里，
    # 整屏缩着看必然看不见，必须把那一圈单独放大到能数清条纹。
    r = json.loads(pg.ev("""(()=>{const b=document.querySelector('.card').getBoundingClientRect();
        return JSON.stringify({x:b.left,y:b.top,w:b.width,h:b.height});})()"""))
    edge = {'x': max(0, r['x'] - 26), 'y': r['y'] + r['h'] * 0.42, 'width': 88, 'height': 88, 'scale': 6}
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
        print(f'  对照({tag}): {"✅ 两版像素不同" if a != b else "❌ 完全相同 —— 折射没落到画面上，白改"}')


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
        out['D_wave_turb'] = run(pg, 'D 划水·现算噪声', 'turb', True)
        out['E_wave_img'] = run(pg, 'E 划水·静态法线图', 'img', True)
        out['F_wave_imgbody'] = run(pg, 'F 划水·整面折射', 'imgbody', True)
        print('  ── 以下四条是追那 20ms 的去向 + 落地后的真实对照，不是候选方案 ──')
        out['K_wave_lg_off'] = run(pg, 'K 划水·只摘折射', 'asis', True, 'lgoff')
        out['L_wave_rimonly'] = run(pg, 'L 划水·只留边墙', 'rimonly', True)
        out['M_wave_panelonly'] = run(pg, 'M 划水·只留面板', 'panelonly', True)
        out['G_wave_noglow'] = run(pg, 'G 划水·摘玻璃+藏光晕', 'noglass_noglow', True)
        out['H_wave_render_stub'] = run(pg, 'H 划水·停掉GL绘制', 'noglass', True, 'renderstub')
        out['J_wave_asis_noglow'] = run(pg, 'J 划水·毛玻璃+藏光晕', 'noglow', True)
        c = out.get('C_wave_noglass')
        if c:
            for k in ('G_wave_noglow', 'H_wave_render_stub'):
                if out.get(k) and out[k]['shot'] == c['shot']:
                    print(f'  ⚠ {k} 与 C 像素完全相同 —— 该条件没改变画面，它的耗时数字无意义')
        b = out.get('B_wave_as_is')
        bad = []
        if not b or b['strokes'] == 0:
            bad.append('strokes=0：划水没被触发，B~F 与 A 无差别')
        if b and not b['bgframes']:
            bad.append("bg帧=0：水面循环根本没跑（BG.mode 虽为 gl 但没起波）")
        # 阳性对照：摘玻璃 / 现算噪声 / 静态法线图 三种材质必须拍出**不同**的像素，
        # 相同就说明 url() 只是被 CSS 解析接受、并没有真的落到合成结果上 —— 那 E/F 的耗时数字毫无意义。
        sig = {k: (out.get(k) or {}).get('shot') for k in
               ('C_wave_noglass', 'D_wave_turb', 'E_wave_img', 'F_wave_imgbody')}
        if len(set(v for v in sig.values() if v)) < 4:
            bad.append(f'截图指纹未全部互异 {sig}：材质差异没进像素，E/F 的成本结论不成立')
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
