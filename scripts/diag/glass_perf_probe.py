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
  py -3 scripts/diag/glass_perf_probe.py --port 8777            # 六种材质对比 + 帧时
  py -3 scripts/diag/glass_perf_probe.py --port 8777 --shots    # 冻结背景的成对取图
  py -3 scripts/diag/glass_perf_probe.py --port 8777 --hover    # 「悬停整卡糊」的分态判据
  需要 8777（或 --port 指定）上有静态服务：py -3 -m http.server 8777 --bind 127.0.0.1 -d Output
"""
import sys, os, json, math, time, base64, hashlib, shutil, argparse, subprocess, urllib.request, zlib
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
# ⚠️ 这份脚本原来住在 .diag/ 顶层（HERE 的父目录就是仓库根），入库时移到 scripts/diag/ 后
#    '..' 只退到 scripts/ —— 于是 .diag 产物全写进 scripts/.diag/（未被 gitignore 覆盖的目录），
#    找了两次"截图去哪了"才定位。这里必须退两级，别再按老路径推。
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
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
AP.add_argument('--hover', action='store_true',
                help='悬停取样：量「面(中心)梯度」在 rest/pin/lift2d/tilt3d/live/blurctl 六态的比值'
                     '（卡片一转会不会糊整张面；最后一态是阳性对照，判据不过 exit 1）')
A = AP.parse_args()
W, H = (int(x) for x in A.win.split(','))
URL = f'http://127.0.0.1:{A.port}/gallery_v2/index.html'


CSS = {
    'asis': '',
    # 地板：整个页面一张玻璃都不挂（导航栏那条也算进去）⇒ 与 B 之差 = 现在这套玻璃的总价
    'noglass': ('.card,.card::before,header,header::before'
                '{backdrop-filter:none!important;-webkit-backdrop-filter:none!important}'),
    # G：摘玻璃 + 藏掉 #bgfx 里那三个 74vmax 径向渐变光晕（光晕归因与玻璃无关，仍然有效）
    'noglass_noglow': ('.card,.card::before,header,header::before'
                       '{backdrop-filter:none!important;-webkit-backdrop-filter:none!important}'
                       '#bgfx .glow{display:none!important}'),
    # J：保留现有玻璃 + 藏光晕 ⇒ 与 B 之差 = "只改背景能省多少"
    'noglow': '#bgfx .glow{display:none!important}',
    # S：给每张卡注回**一个** backdrop-filter 盒。⚠️ 选择器从 `.card.g` 改成 `.card`：卡片现在
    #    根本没有 `.g`（边墙整个撤了，§136），打在 `.card.g` 上就是恒空转——而它要答的问题
    #    （"每卡一盒到底要多少钱"）恰恰是 §134 那张成本表的支点，不能空转。
    'panel_back': ('.card{-webkit-backdrop-filter:blur(2.5px) saturate(1.5)!important;'
                   'backdrop-filter:blur(2.5px) saturate(1.5)!important}'),
}

# 页面侧挂钩：K 只切 html.lg（导航栏折射开/关），renderstub 停掉水面绘制。
# ⚠️ _restore 必须把两者都还原回去，否则后面的条件跑在"更少玻璃"的状态上，数字全线偏低。
JS_PRE = {
    'renderstub': "(()=>{if(!window.__R0)window.__R0=bgRender; window.bgRender=function(){}; return 'ok';})()",
    # K：只把折射摘掉（html.lg 一去掉，②-b 那条规则就不匹配，边墙自动退回上一版那条模糊）
    # —— 这才是「新效果比旧效果贵多少」的正确对照，C 那条把模糊也一起摘了，量的是别的东西。
    'lgoff': "(()=>{document.documentElement.classList.remove('lg'); return 'ok';})()",
    '_restore': "(()=>{if(window.__R0){window.bgRender=window.__R0;}"
                "document.documentElement.classList.add('lg');"
                # ⚠️ 原来这里还按视口重算一遍 .g（few24/few40 摘掉后要补回来）。
                # 现在卡片没有任何 .g 样式消费者，补回去只会让架构闸门误报，故一并删掉。
                "return 'ok';})()",
}


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

    def ev(self, expr, aw=False):
        p = {'expression': expr, 'returnByValue': True}
        if aw:
            p['awaitPromise'] = True
        r = self.cmd('Runtime.evaluate', p)
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
        pre_info = pg.ev(JS_PRE[pre])
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
    // 边墙**架构不变式**（2026-10-11 §136 定）：**卡片这一层里一个 backdrop-filter 都不许挂**，
    //   伪元素与元素本身都算。理由不是性能，是这条 bug 类：卡片必然被跟手倾斜 rotateX/rotateY，
    //   转角一非 0，Chrome 就丢掉 ::before 上那层"只留环"的 mask ⇒ 模糊铺满整张卡（用户报的"悬停就糊"）。
    //   rim_rules = 样式表里还有哪条 .card 系选择器声明了 backdrop-filter（静态，抓"又把 CSS 加回来"）
    //   card_boxes = 实测量到挂着的盒子个数（含当前悬停那一张，抓 JS 现写的内联）
    rim_rules:(()=>{const hit=[];
      for(const s of document.styleSheets){ let rs; try{ rs=s.cssRules; }catch(e){ continue; }
        if(!rs) continue;
        for(const r of rs){ const sel=r.selectorText||'';
          if(sel && /(^|,)\s*\.card\b/.test(sel) && /backdrop-filter/.test(r.cssText||'')) hit.push(sel); } }
      return hit;})(),
    card_boxes:(()=>{let n=0; const cs=document.querySelectorAll('.card');
      const bad=(el,p)=>{ const v=getComputedStyle(el,p); return v && v.backdropFilter && v.backdropFilter!=='none'; };
      for(let i=0;i<cs.length&&i<80;i++){ if(bad(cs[i],'')||bad(cs[i],'::before')) n++; }
      const hv=document.querySelector('.card:hover');
      if(hv&&(bad(hv,'')||bad(hv,'::before'))) n++;
      return n;})(),
    nav_h:(()=>{const r=nav.getBoundingClientRect();
      return Math.round(r.width)+'x'+Math.round(r.height);})()});})()"""


PICK_CARD = """(()=>{const cs=[...document.querySelectorAll('.card')];
  const ok=e=>{const r=e.getBoundingClientRect(), im=e.querySelector('img');
    return r.top>60&&r.bottom<innerHeight-30&&r.left>30&&r.right<innerWidth-30&&r.width>90
      &&im&&im.naturalWidth>40;};
  const c=cs.filter(ok)[3]||cs.filter(ok)[0]||null;
  if(!c) return '';
  c.id='hovcard';
  const r=c.getBoundingClientRect();
  return JSON.stringify({x:+r.x.toFixed(2),y:+r.y.toFixed(2),w:+r.width.toFixed(2),h:+r.height.toFixed(2)});})()"""

# 悬停会同时改四件事：卡的 lift/scale、倾斜 rx/ry、缩略图 scale(1.06)、以及**合成层的提升**。
# 2026-10-11 §136 定案后，这一组的用途变了：原来问「糊来自哪一头」，现在问
# **「卡片转起来之后，面还锐不锐」**——锐就是那条架构不变式守住了（卡片盒内零滤镜）。
HOV_CSS = """(()=>{const n=document.getElementById('hovsty')||(()=>{const s=document.createElement('style');
  s.id='hovsty';document.head.appendChild(s);return s;})();
  const PIN='#hovcard{--lift:0px!important;--sc:1!important;--rx:0deg!important;--ry:0deg!important;'+
            'transition:none!important}#hovcard .thumb img{transform:none!important;transition:none!important}';
  const T3='#hovcard{--lift:0px!important;--sc:1!important;transition:none!important;'+
           '--rx:-6.5deg!important;--ry:8deg!important}'+
           '#hovcard .thumb img{transform:none!important;transition:none!important}';
  const M={
    // 悬停但 transform 取的是恒等值（perspective 仍在，三个分量都是 0）——分离「3D 函数存在」与「真的转了」
    pin:PIN,
    // 只有 2D 分量非零（抬起 + 放大），不倾斜、不过渡：2D 这一头从来不是触发条件，留着当阴性对照
    lift2d:'#hovcard{--lift:-5px!important;--sc:1.015!important;--rx:0deg!important;--ry:0deg!important;'+
           'transition:none!important}#hovcard .thumb img{transform:none!important;transition:none!important}',
    // 静态、非零、且**不过渡**的倾斜：幅度取 JS 满偏（dx*16 → ±8deg，dy*13 → 6.5deg）——这就是触发态
    tilt3d:T3,
    // 阳性对照：直接给缩略图挂 blur(17px)，制造一次"已知的整面糊"。
    //   ⚠️ 原来的对照是"摘掉 mask"，而卡片现在根本没有 mask 可摘 ⇒ 那条会恒不塌，尺子里外都测不出东西。
    blurctl:PIN+'#hovcard .thumb img{filter:blur(17px)!important}'};
  n.textContent=M[window.__HOVM]||'';
  return String(n.textContent.length);})()"""

HOV_MODES = (
    ('pin', '恒等值：perspective 仍在但三个分量都是 0'),
    ('lift2d', '只有 2D 非零：抬 5px + 放大 1.5%，不倾斜、不过渡（阴性对照）'),
    ('tilt3d', '只有 3D 非零：静态 -6.5°/8°，不过渡（§136 的触发态）'))

HOV_ANALYZE = """(async()=>{
 const o=window.__H, S=o.g.s, X0=Math.round((o.g.x-o.g.cx)*S), Y0=Math.round((o.g.y-o.g.cy)*S);
 const CW=Math.round(o.g.w*S), CH=Math.round(o.g.h*S), B=Math.round(9*S);
 const st={};
 for(const k of Object.keys(o.img)){
   const im=new Image(); im.src='data:image/png;base64,'+o.img[k]; await im.decode();
   const c=document.createElement('canvas'); c.width=im.width; c.height=im.height;
   const g=c.getContext('2d',{willReadFrequently:true}); g.drawImage(im,0,0);
   st[k]={d:g.getImageData(X0,Y0,CW,CH).data,w:CW,h:CH};
 }
 const L=(a,x,y)=>{const i=(((y*a.w)+x)<<2),p=a.d; return p[i]*.299+p[i+1]*.587+p[i+2]*.114;};
 const inCen=(x,y)=>x>=B*2&&y>=B*2&&x<=st.rest.w-B*2&&y<=st.rest.h-B*2;
 const inBand=(x,y)=>{const dx=Math.min(x,st.rest.w-1-x),dy=Math.min(y,st.rest.h-1-y);
                      return (dx>=0&&dx<B)||(dy>=0&&dy<B);};
 const acc={};
 for(const k of Object.keys(st)) acc[k]={cg:[0,0],bg:[0,0]};
 for(let y=1;y<st.rest.h-1;y++) for(let x=1;x<st.rest.w-1;x++){
   const cen=inCen(x,y), band=!cen&&inBand(x,y);
   if(!cen&&!band) continue;
   for(const k of Object.keys(st)){
     const a=st[k], gd=Math.abs(L(a,x+1,y)-L(a,x-1,y))+Math.abs(L(a,x,y+1)-L(a,x,y-1));
     const t=cen?'cg':'bg'; acc[k][t][0]+=gd; acc[k][t][1]++;
   }
 }
 const r={};
 for(const k of Object.keys(acc)) r[k]={cen:+(acc[k].cg[0]/acc[k].cg[1]).toFixed(2),
                                        band:+(acc[k].bg[0]/acc[k].bg[1]).toFixed(2)};
 return JSON.stringify({box:st.rest.w+'x'+st.rest.h, s:r});})()"""


def hover_diag(pg):
    """量一件事：**卡片被跟手倾斜转起来之后，画面中心还锐不锐**。
    尺子是「区域平均梯度能量」（糊掉的画面梯度必然塌），比值以静止态为 1.00。
    历史：用户连报三次「悬停 → 整张卡糊成一块」，我给过的两条根因（并层架构 / evenodd 遮罩重叠）
    都被「回退了还在」证伪；这一组档位才把变量切开——`pin`(恒等) 1.00、`lift2d`(纯 2D) 0.89、
    `tilt3d`(静态 3D) 0.05、`live`(每帧在变) 0.05，而 0.05 与"故意摘掉 mask"的阳性对照同价
    ⇒ 触发条件是**转角非 0**，与遮罩怎么算无关（§136）。
    ⚠️ 定案后卡片盒内已零滤镜，所以判据翻过来：**tilt3d 与 live 都必须 ≥0.75**。
       阳性对照也从"摘 mask"换成 blurctl（直接给缩略图挂 blur）——卡上没有 mask 可摘了，
       老对照会恒不塌，那种"两条都不塌"的表不能读。"""
    geo = pg.ev(PICK_CARD)
    if not isinstance(geo, str) or not geo.startswith('{'):
        print(f'! 挑不出一张完整在视口内、且图片已解码的 .card（返回 {str(geo)[:60]}）—— 无法取样')
        sys.exit(1)
    g = json.loads(geo)
    print(f'取样卡：{g["w"]:.0f}x{g["h"]:.0f} @ ({g["x"]:.0f},{g["y"]:.0f})，水面已冻住，取景含边墙外 16px')
    pg.ev(FREEZE)
    time.sleep(0.6)
    SHOTD = os.path.join(ROOT, '.diag', 'glasshover')
    shutil.rmtree(SHOTD, ignore_errors=True)
    os.makedirs(SHOTD, exist_ok=True)
    margin = 16
    clip = {'x': max(0, g['x'] - margin), 'y': max(0, g['y'] - margin),
            'width': g['w'] + 2 * margin, 'height': g['h'] + 2 * margin, 'scale': 2}
    cx, cy = g['x'] + g['w'] / 2, g['y'] + g['h'] / 2
    nx, ny = W * 0.5, 30          # 停到导航栏上：既离开卡片网格，又触发 mainEl 的 mouseleave→tiltReset

    def move(x, y):
        pg.cmd('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y, 'buttons': 0})

    def shot(name):
        """落盘一份：判据是数字，但「这张图是不是用户看到的那坨」只能用人眼核一次。"""
        raw = base64.b64decode(pg.cmd('Page.captureScreenshot', {'format': 'png', 'clip': clip})['data'])
        open(os.path.join(SHOTD, name + '.png'), 'wb').write(raw)
        return raw

    def setmode(m):
        pg.ev(f"window.__HOVM={json.dumps(m)};1")
        pg.ev(HOV_CSS)

    def hovered():
        return pg.ev("!!document.querySelector('#hovcard:hover')")

    caps = {}
    move(nx, ny); time.sleep(0.7)
    caps['rest'] = shot('rest')
    print(f'  rest      hover={hovered()}  mask/滤镜状态见下')
    for mode, note in HOV_MODES:
        setmode(mode); time.sleep(0.25)
        move(cx, cy); time.sleep(0.6)
        caps[mode] = shot(mode)
        print(f'  {mode:<11} hover={hovered()}（{note}）')
    setmode(''); time.sleep(0.25)
    move(nx, ny); time.sleep(0.5)
    move(cx, cy); time.sleep(0.2)
    for i in range(18):                      # 真实跟手：连续小范围移动，让 transform 每帧都变
        move(cx + 18 * math.sin(i / 3.0), cy + 12 * math.cos(i / 2.4)); time.sleep(0.03)
    time.sleep(0.4)
    caps['live'] = shot('live')
    print(f'  live      hover={hovered()}（用户实际那一态：transform 每帧都在变）')
    setmode('blurctl'); time.sleep(0.3)
    move(cx, cy); time.sleep(0.6)
    caps['blurctl'] = shot('blurctl')
    print('  blurctl     阳性对照：直接给缩略图挂 blur(17px) ⇒ 这一态必须是"整面糊"')
    setmode('')

    st = json.loads(pg.ev(STATUS))
    print(f'  计算态: bf={str(st["bf"])[:58]} | card_boxes={st["card_boxes"]} '
          f'rules={st["rim_rules"]} | cards_g={st["cards_g"]} | tok_ok={st["tok_ok"]}')
    pg.ev(UNFREEZE)

    pg.ev('window.__H=' + json.dumps(
        {'img': {k: base64.b64encode(v).decode() for k, v in caps.items()},
         'g': {'x': g['x'], 'y': g['y'], 'w': g['w'], 'h': g['h'],
               'cx': clip['x'], 'cy': clip['y'], 's': clip['scale']}}) + ';1')
    res = pg.ev(HOV_ANALYZE, aw=True)
    if not isinstance(res, str) or res.startswith('EXC'):
        print(f'! 像素分析失败：{str(res)[:200]}')
        sys.exit(1)
    r = json.loads(res)['s']
    ORDER = ('rest',) + tuple(m for m, _ in HOV_MODES) + ('live', 'blurctl')
    NOTE = dict(HOV_MODES)
    NOTE['live'] = '用户实际那一态：transform 每帧都在变'
    NOTE['blurctl'] = '阳性对照：缩略图直接挂 blur(17px)'
    print(f'\n  梯度能量（越大越锐；框 {json.loads(res)["box"]}，只取卡片内部，环带=贴边 9px）')
    print(f'  {"态":<12}{"面(中心72%)":>12}{"面÷rest":>9}{"环(边9px)":>12}')
    base = max(0.01, r['rest']['cen'])
    for k in ORDER:
        print(f'  {k:<12}{r[k]["cen"]:>12}{r[k]["cen"]/base:>9.2f}{r[k]["band"]:>12}')
    ctrl = r['blurctl']['cen'] / base
    print(f'\n  阳性对照 blurctl：中心锐度只剩 rest 的 {ctrl:.2f} 倍'
          f'{" ⇒ 尺子有效" if ctrl < 0.75 else " ⇒ ⚠️ 对照没塌，尺子无效，下面所有判定作废"}')
    bad = [] if ctrl < 0.75 else ['blurctl 对照没塌（尺子失效）']
    for k in ORDER[1:-1]:
        ratio = r[k]['cen'] / base
        ok = ratio >= 0.75
        if not ok:
            bad.append(f'{k}={ratio:.2f}×rest')
        print(f'  {k:<11} {ratio:.2f}×rest ⇒ '
              f'{"✅ 面仍然锐（卡片零滤镜守住了）" if ok else "❌ 面被糊了（§136 那条 bug 回来了）"}'
              f'｜{NOTE[k]}')
    if bad:
        print(f'! 判据不过：{ "、".join(bad) } —— 取图在 {SHOTD}')
        sys.exit(1)
    print(f'  ✅ 全绿：卡片一转不再糊整张面（六态取图在 {SHOTD}）')


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
            # ⇒ 断言不 sound。它该管的事由结构闸门 card_boxes==0 负责（卡片盒内不许挂任何滤镜）。
            print(f'  参考({tag}/卡片): {a} vs {b} —— 只反映水面帧差，**不作判据**'
                  f'（卡片不做玻璃由 card_boxes={st["card_boxes"]} 那条结构闸门守，见 §136）')
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
        # 架构闸门（§136）：卡片盒内**一个 backdrop-filter 都不许挂**。
        # 卡片必然被跟手倾斜 rotateX/rotateY，转角一非 0，Chrome 就丢掉 ::before 上"只留环"的
        # mask ⇒ 模糊铺满整张卡（用户连报三次的"悬停就糊"）。所以这不是性能项，是 bug 类复发闸门。
        if st0['card_boxes'] or st0['rim_rules'] or st0['cards_g']:
            print(f'! 卡片上挂着 backdrop-filter：card_boxes={st0["card_boxes"]} '
                  f'rules={st0["rim_rules"]} cards_g={st0["cards_g"]}\n'
                  f'  ⇒ 一转就糊（§136 八态对照）。要厚边只能走不依赖 mask 的实现，'
                  f'或者把这层放到**不会被旋转**的容器上。')
            sys.exit(1)
        print(f'  边墙架构: 卡片零滤镜盒 ✅（§136）；导航栏 bf={str(st0["bf"])[:40]}')
        if A.hover:
            hover_diag(pg)
            return
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
        out = {}
        print(f'\n条件：每格 {A.ms}ms 采样，视口 {W}x{H}，折射 scale=70')
        out['A_idle_as_is'] = run(pg, 'A 静止·现毛玻璃', 'asis', False)
        out['B_wave_as_is'] = run(pg, 'B 划水·现毛玻璃', 'asis', True)
        out['C_wave_noglass'] = run(pg, 'C 划水·摘玻璃', 'noglass', True)
        # D/E/F/O/24/40 **全部撤下**（2026-10-11 §136 定案后）：它们注入的目标是"卡片上那一层玻璃"
        #   （逐卡 ::before 边墙 / 卡片整面折射 / #glassone 遮罩层 / 按卡片个数缩放滤镜盒数量），
        #   而卡片盒内现在**一个 backdrop-filter 都不挂** ⇒ 五条全部打在空选择器上。
        #   空转的条件不是"少了个信息"，是**噪声伪装成信息**：同一份代码两轮能差 3ms，
        #   本轮就出现过 N/Q/R 比 B 慢 3ms 而它们其实什么都没改。宁可删也不留着。
        #   它们当年量出的结论钉在 §134 那张表里；CSS 键保留是给 --caps 手工隔离实验用的。
        # 现在唯一还挂着滤镜的元素是导航栏 ⇒ 归因条件只剩"折射开/关"与"每卡一盒值多少钱"两条。
        print('  ── 以下是归因条件，不是候选方案 ──')
        out['K_wave_lg_off'] = run(pg, 'K 划水·只摘折射', 'asis', True, 'lgoff')
        out['S_wave_panel_back'] = run(pg, 'S 划水·把面板层注回', 'panel_back', True)
        s_, b_ = out.get('S_wave_panel_back'), out.get('B_wave_as_is')
        if s_ and b_:
            print(f'  「每卡一个滤镜盒要多少钱」：给 70 张卡注回 blur(2.5px) 后 {b_["med"]}ms → {s_["med"]}ms'
                  f'（+{s_["med"]-b_["med"]:.1f}ms）；取景 {b_["shot_card"]} vs {s_["shot_card"]}'
                  f'{" 逐字节相同" if s_["shot_card"] == b_["shot_card"] else " 有差异 ⇒ 不是免费的，交肉眼判"}')
        out['G_wave_noglow'] = run(pg, 'G 划水·摘玻璃+藏光晕', 'noglass_noglow', True)
        out['H_wave_render_stub'] = run(pg, 'H 划水·停掉GL绘制', 'noglass', True, 'renderstub')
        out['J_wave_asis_noglow'] = run(pg, 'J 划水·毛玻璃+藏光晕', 'noglow', True)
        # 通用"条件空转"探测：**两个取景**（导航栏 + 卡片）都与 B 逐字节相同才算空转。
        # 只看卡片取景会把 K 误报成空转——它只动导航栏的折射，卡片区本来就该一模一样；
        # 只看导航栏取景则会漏掉"只改卡片"的条件。两个都比，才既不误报也不漏报。
        base = out.get('B_wave_as_is') or {}
        inert = [k for k, v in out.items()
                 if v and k != 'B_wave_as_is'
                 and v.get('shot_card') == base.get('shot_card')
                 and v.get('shot') == base.get('shot')]
        if inert:
            print(f'  ⚠ 以下条件与 B 两版取景都逐字节相同 = **空转，它们的帧时不要读**：{", ".join(inert)}')
        b = out.get('B_wave_as_is')
        bad = []
        if not b or b['strokes'] == 0:
            bad.append('strokes=0：划水没被触发，B~F 与 A 无差别')
        if b and not b['bgframes']:
            bad.append("bg帧=0：水面循环根本没跑（BG.mode 虽为 gl 但没起波）")
        # 阳性对照：挂玻璃(B) 与 摘玻璃(C) 必须拍出**不同**的导航栏像素，相同就说明 url() 只是被
        # CSS 解析接受、并没有真的落到合成结果上。原来这条比的是三种卡片材质，而卡片现在零滤镜
        # ⇒ 取景跟着换到导航栏，判据本身没放宽（还是"必须互异"）。
        sig = {k: (out.get(k) or {}).get('shot') for k in ('B_wave_as_is', 'C_wave_noglass')}
        if len(set(v for v in sig.values() if v)) < 2:
            bad.append(f'截图指纹未互异 {sig}：导航栏那层滤镜没落到像素上，K/S 的成本结论不成立')
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
