# -*- coding: utf-8 -*-
"""把「滑动鼠标卡顿」归因到具体某一层：水面动效 / 卡片悬停 / 输入通路。

为什么必须另开一个探针，glass_perf_probe 不够用：
  glass_perf_probe 的"划水"是**页面内 `dispatchEvent(new PointerEvent('pointermove'))`** 驱动的。
  合成事件**不会命中 CSS `:hover`**（gallery_motion_probe 头部已记过），于是它量到的场景里
  **不含卡片悬停的重绘** —— 而那恰好是真实鼠标移动时唯一多出来的工作。
  拿它答"滑动鼠标卡不卡"，是在量一个缺了一半的场景。
  本探针改用 CDP `Input.dispatchMouseEvent`（可信事件，会命中 :hover）。

§133 坑三（"帧时是发事件的速度造的"）在这里怎么绕开：
  坑三是 `cmd()` **阻塞等 CDP 回复**，只能 30–40 次/秒，于是帧时被发事件的速度锁死。
  这里改成**发而不等**（fire-and-forget），最后一次性 drain。
  残余风险是另一个方向：事件发太快、页面来不及消费，帧时又会等于事件间隔。
  所以判据 G3 用**阳性对照**兜底 —— "悬停全摘"那一格必须跑回地板速度，
  否则说明输入通路本身就是瓶颈，整份数字作废。

两个模式：
  --mode ab（默认）  2×2 归因矩阵 + 单变量二分（每次只摘一条 hover 属性）
  --mode share       量背景层（水面 canvas）**逐像素的可见占比**：冻结→灌满→两图相减

2026-10-14 实测结论（2560×1600 / dpr=1 / canvas 1827×1081 / 1021 卡在 DOM、70 张在屏）：
  2×2 帧时中位数  水开·悬停开 26.7–33.3ms ｜ 水关·悬停开 30.1–36.7ms
                  水开·悬停关 3.4ms        ｜ 水关·悬停关 3.4ms
  ⇒ **悬停 ≈ +27ms，水面 ≈ 0（符号甚至反向）**。用户报的"滑鼠标卡"不是水面。
  单变量二分：`.card{transition:none}` 一条就省 +16.7ms（26.7→10）；只摘缩略图放大、
  只摘悬停投影、只摘跟手倾斜都**不动**（±3.3ms 内）。⇒ 大头是卡片自己的 CSS 过渡
  （transform .14s + box-shadow .24s，每次 mousemove 都重新触发 ⇒ 主线程动画永远在跑）。
  可见占比：水面落在 **73.2%** 的视口像素上（仪器噪声 0px）⇒ 全屏 canvas 不算浪费。

用法：
  py -3 scripts/diag/hover_frame_cost_probe.py --port 8799 --win 2560,1600
  py -3 scripts/diag/hover_frame_cost_probe.py --port 8799 --mode share
  需要 8799 上有静态服务：py -3 -m http.server 8799 --bind 127.0.0.1 -d Output
  ⚠️ 本机 HTTP_PROXY 会劫持 127.0.0.1 的 CDP 与页面请求 ⇒ 运行前清掉代理环境变量
     （HTTP_PROXY= HTTPS_PROXY= NO_PROXY=127.0.0.1,localhost）
"""
import sys, os, json, math, time, base64, subprocess, urllib.request, argparse

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import chrome_tree

CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
AP = argparse.ArgumentParser()
AP.add_argument('--port', default='8799')
AP.add_argument('--cdp', default='9342')
AP.add_argument('--win', default='2560,1600')
AP.add_argument('--ms', type=int, default=2500, help='每格采样时长')
AP.add_argument('--step', type=float, default=40.0, help='鼠标事件节拍 ms')
AP.add_argument('--mode', default='ab', choices=['ab', 'share', 'layout', 'commit'])
AP.add_argument('--thr', type=int, default=8, help='share 模式：逐像素判定阈值')
AP.add_argument('--dpr', type=float, default=0,
                help='强制 devicePixelRatio（0=不干预）。用来验"画布分辨率随 dpr 变化"那类改动——'
                     '无头默认 dpr=1，不强制就永远量不到 HiDPI 分支')
A = AP.parse_args()
W, H = (int(x) for x in A.win.split(','))
URL = f'http://127.0.0.1:{A.port}/gallery_v2/index.html'

# ── 单变量开关 ───────────────────────────────────────────────────────────────
# 每次只摘一条 hover 属性，用来定位"那 27ms 到底买的是哪一件"。
# 全摘（all_off）同时改四件事，只能当上界，不能用来归因（§133 坑二的同类错误）。
CSSV = {
    'none': '',
    'no_img': '.card:hover .thumb img{transform:none!important}',
    'no_shadow': '.card:hover{box-shadow:var(--sh2),inset 0 1px 0 var(--rim-hi)!important}',
    'no_trans': '.card{transition:none!important}',
    'no_tilt': '.card{transform:none!important}',
    'all_off': ('.card,.card *{transition:none!important;animation:none!important}'
                '.card{transform:none!important}'
                '.card:hover{box-shadow:var(--sh2),inset 0 1px 0 var(--rim-hi)!important;'
                'border-color:var(--glass-line)!important}'
                '.card:hover .thumb img{transform:none!important}'),
    # ── 候选优化（先在这里量，便宜才落到正本；§134 的"先在探针里注入验证"）──────────
    # 候选A：把 transform 从过渡列表里摘掉，只让「抬起」那两个变量过渡。
    #   现状 `.card{transition:transform .14s}` 而跟手倾斜**每次 mousemove 都写 --rx/--ry**
    #   ⇒ 140ms 的过渡被无限重启，主线程动画永远在跑。
    #   @property 把 --lift/--sc 注册成可插值，于是"抬起"仍有缓动、倾斜变成立即。
    'cand_tilt_instant': (
        "@property --lift{syntax:'<length>';inherits:false;initial-value:0px}"
        "@property --sc{syntax:'<number>';inherits:false;initial-value:1}"
        '.card{transition:--lift .24s ease-out,--sc .24s ease-out,'
        'box-shadow .24s ease-out,border-color .18s ease-out!important}'),
    # 候选B：离屏卡整棵子树跳过样式/布局/绘制。DOM 里 1021 张、屏上只有 70 张。
    #   contain-intrinsic-size 用 auto 关键字记住上次渲染尺寸，避免滚动条跳动。
    # 估计值取实测卡高（2560 窗实测 320.3px）。⚠️ 卡宽走 `minmax(154px,1fr)` 会随窗宽拉伸，
    #   卡高因此有 ~320~339px 的带宽；固定估计值只能取中值，`auto` 关键字会在首次渲染后自校正。
    'cand_cv': '.card{content-visibility:auto;contain-intrinsic-size:auto 330px}',
    # 候选C：只留 transform 那条过渡，把 box-shadow / border-color 的过渡摘掉。
    #   上一轮 A（只摘 transform 那条）没用 ⇒ 贵的应该是**不能合成的那两条属性上的过渡**：
    #   box-shadow 无法合成 ⇒ 过渡期间只能主线程逐帧重绘；而 transform 可以合成。
    'cand_trans_only': '.card{transition:transform .14s ease-out!important}',
    'cand_noshadow_trans': '.card{transition:transform .14s ease-out,'
                           'border-color .18s ease-out!important}',
    'cand_cv_trans_only': ('.card{transition:transform .14s ease-out!important;'
                           'content-visibility:auto;contain-intrinsic-size:auto 420px}'),
    # 候选H：决定性实验 —— 把 hover 反馈整体搬到**可合成的 opacity** 上。
    #   若 H ≈ 「过渡全摘」，说明"任何主线程过渡 ⇒ 每帧重栅格化"这条机制成立，
    #   于是存在"既省又不丢缓动"的改法；若 H 仍慢，则 opacity 也救不了，得换思路。
    'cand_opacity_hover': (
        '.card{transition:none!important}'
        '.card::before{content:"";position:absolute;inset:0;z-index:4;pointer-events:none;'
        'border-radius:var(--r-card);background:color-mix(in srgb,var(--brand) 26%,transparent);'
        'opacity:0;transition:opacity .24s ease-out}'
        '.card:hover::before{opacity:1}'),
    # 候选I：H + 让那层自己成合成层（will-change:opacity）。判"搬去 opacity 不行"
    #   到底是因为属性不可合成，还是因为那层没被提升。
    'cand_opacity_wc': (
        '.card{transition:none!important}'
        '.card::before{content:"";position:absolute;inset:0;z-index:4;pointer-events:none;'
        'border-radius:var(--r-card);background:color-mix(in srgb,var(--brand) 26%,transparent);'
        'opacity:0;transition:opacity .24s ease-out;will-change:opacity}'
        '.card:hover::before{opacity:1}'),
    # 候选J：**一行、零观感改动**——原过渡全保留，只在悬停时给卡片一个提升提示，
    #   让 transform 过渡真的跑在合成器上。若 J ≈ 10ms，就是"既省又不丢缓动"的答案。
    'cand_wc_hover': '.card:hover{will-change:transform}',
    # 候选K：**折中**——缓动保留但时长压短。若代价正比于"过渡在跑的帧数"，
    #   240ms→90ms 应该能拿到大半个收益，而观感只差在"稍微干脆一点"。
    'cand_short_trans': ('.card{transition:transform .09s ease-out,'
                         'box-shadow .1s ease-out,border-color .09s ease-out!important}'),
    'cand_short_cv': ('.card{transition:transform .09s ease-out,'
                      'box-shadow .1s ease-out,border-color .09s ease-out!important;'
                      'content-visibility:auto;contain-intrinsic-size:auto 420px}'),
    # 候选L：`contain:content`（= layout paint style）—— **不需要尺寸估计**，因此不会动滚动高度。
    #   它不像 content-visibility 那样整棵跳过，但能收窄样式/布局的失效范围。
    'cand_contain': '.card{contain:content}',
    'cand_contain_notrans': '.card{contain:content;transition:none!important}',
    # 候选M：把 content-visibility 的估计值改成贴着实测卡高（320.3），验证"漂移只是估计值的问题"。
    'cand_cv320': '.card{content-visibility:auto;contain-intrinsic-size:auto 320px}',
    'cand_cv_notrans_330': ('.card{transition:none!important;content-visibility:auto;'
                            'contain-intrinsic-size:auto 330px}'),
    # 候选F：上界组合 —— 过渡全摘 + 离屏卡跳过。用来判"这两条能不能叠加"。
    'cand_notrans_cv': ('.card{transition:none!important;'
                        'content-visibility:auto;contain-intrinsic-size:auto 420px}'),
    'cand_both': (
        "@property --lift{syntax:'<length>';inherits:false;initial-value:0px}"
        "@property --sc{syntax:'<number>';inherits:false;initial-value:1}"
        '.card{transition:--lift .24s ease-out,--sc .24s ease-out,'
        'box-shadow .24s ease-out,border-color .18s ease-out!important;'
        'content-visibility:auto;contain-intrinsic-size:auto 420px}'),
}
SETCSS = """(()=>{let s=document.getElementById('hov');
  if(!s){s=document.createElement('style');s.id='hov';document.head.appendChild(s);}
  s.textContent=%s; return 'ok';})()"""
WATER_OFF = """(()=>{if(!window.__B0){window.__B0=window.bgStart;}
  window.bgStart=function(){}; if(BG.raf){cancelAnimationFrame(BG.raf);BG.raf=0;}
  return 'water off';})()"""
WATER_ON = "(()=>{if(window.__B0){window.bgStart=window.__B0;} return 'water on';})()"

REC = r"""(()=>{const ms=%d; window.__P={done:false}; window.__ev=0;
  if(!window.__hooked){ window.__hooked=1;
    window.addEventListener('mousemove',()=>window.__ev++,{capture:true,passive:true}); }
  const t0=performance.now(); const ts=[]; let last=t0; const s0=BG.strokes, f0=BG.frames;
  function f(now){ ts.push(now-last); last=now;
    if(now-t0<ms){ requestAnimationFrame(f); }
    else { const s=ts.slice(3).sort((a,b)=>a-b);
      window.__P={done:true,n:ts.length,ev:window.__ev,
        med:+s[s.length>>1].toFixed(2), p95:+s[Math.floor(s.length*.95)].toFixed(2),
        max:+s[s.length-1].toFixed(2), fps:+(1000/s[s.length>>1]).toFixed(1),
        strokes:BG.strokes-s0, bgframes:BG.frames-f0, peak:+BG.peak.toFixed(4)}; } }
  requestAnimationFrame(f); return 'rec';})()"""

MET = ('TaskDuration', 'ScriptDuration', 'LayoutDuration', 'RecalcStyleDuration',
       'LayoutCount', 'RecalcStyleCount')

STOP = "(()=>{window.bgStart=function(){};if(BG.raf){cancelAnimationFrame(BG.raf);BG.raf=0;}return 'raf='+BG.raf;})()"
FLAT = "(()=>{BG.cur.fill(0);BG.prv.fill(0);bgUpload();bgRender();return 'flat';})()"
FLOOD = "(()=>{BG.cur.fill(0.62);bgUpload();bgRender();return 'flood';})()"


def open_page(profile):
    try:
        import websocket
    except ImportError:
        raise SystemExit('! 缺 websocket-client（用 ~/.workbuddy-ai/binaries/python/envs/default）')
    os.makedirs(profile, exist_ok=True)
    flags = ['--headless=new', f'--remote-debugging-port={A.cdp}', '--remote-allow-origins=*',
             f'--user-data-dir={profile}', '--no-first-run', '--no-default-browser-check',
             f'--window-size={A.win}', '--disable-background-timer-throttling', '--hide-scrollbars']
    if A.dpr:
        flags.append(f'--force-device-scale-factor={A.dpr}')
    proc = chrome_tree.install(subprocess.Popen([CHROME] + flags + [URL],
                                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    ws = None
    for _ in range(120):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{A.cdp}/json'))
            m = [t for t in tabs if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
            if m:
                ws = m[0]['webSocketDebuggerUrl']
                break
        except Exception:
            pass
        time.sleep(0.5)
    if not ws:
        chrome_tree.kill_tree(proc.pid)
        raise SystemExit('! no CDP tab（代理是否劫持了 127.0.0.1？见文件头）')
    conn = websocket.create_connection(ws, timeout=180, max_size=None)
    n = [0]

    def fire(m, p=None):
        n[0] += 1
        conn.send(json.dumps({'id': n[0], 'method': m, 'params': p or {}}))

    def drain(mid, timeout=180):
        conn.settimeout(timeout)
        while True:
            r = json.loads(conn.recv())
            if r.get('id') == mid:
                return r.get('result', {})

    def dom(m, p=None):
        """CDP 域方法（Page.enable / Performance.enable）—— 不能走 Runtime.evaluate：
        塞进 ev() 里会被当成 JS 表达式求值，域从未真的开启，指标全读成 0（本轮撞过）。"""
        n[0] += 1
        mid = n[0]
        conn.send(json.dumps({'id': mid, 'method': m, 'params': p or {}}))
        return drain(mid)

    def ev(expr):
        n[0] += 1
        mid = n[0]
        conn.send(json.dumps({'id': mid, 'method': 'Runtime.evaluate',
                              'params': {'expression': expr, 'returnByValue': True}}))
        r = drain(mid)
        ed = r.get('exceptionDetails')
        if ed:
            return 'EXC ' + json.dumps(ed, ensure_ascii=False)[:300]
        return r.get('result', {}).get('value')

    def evAw(expr):
        n[0] += 1
        mid = n[0]
        conn.send(json.dumps({'id': mid, 'method': 'Runtime.evaluate',
                              'params': {'expression': expr, 'returnByValue': True,
                                         'awaitPromise': True}}))
        r = drain(mid, timeout=300)
        ed = r.get('exceptionDetails')
        if ed:
            return 'EXC ' + json.dumps(ed, ensure_ascii=False)[:400]
        return r.get('result', {}).get('value')

    dom('Page.enable')
    dom('Performance.enable')
    for _ in range(60):
        c = ev("document.querySelectorAll('.card').length")
        if isinstance(c, int) and c > 50:
            break
        time.sleep(0.5)
    time.sleep(3.0)
    return proc, conn, fire, drain, dom, ev, evAw


def main():
    prof = os.path.join(ROOT, '.diag', f'hovercost_profile_{os.getpid()}')
    proc, conn, fire, drain, dom, ev, evAw = open_page(prof)
    try:
        env = json.loads(ev("""JSON.stringify({mode:BG.mode, canvas:BG.cv?BG.cv.width+'x'+BG.cv.height:null,
          vp:innerWidth+'x'+innerHeight, dpr:devicePixelRatio,
          cards:document.querySelectorAll('.card').length,
          gpu:(()=>{const g=BG.gl;if(!g)return 'n/a';const d=g.getExtension('WEBGL_debug_renderer_info');
            return d?String(g.getParameter(d.UNMASKED_RENDERER_WEBGL)):'n/a';})()})"""))
        print('环境:', json.dumps(env, ensure_ascii=False))
        if env['mode'] != 'gl':
            raise SystemExit('! BG.mode≠gl ⇒ 水面没跑 WebGL，整份数字作废')

        if A.mode == 'share':
            return mode_share(ev, dom, env)
        if A.mode == 'layout':
            return mode_layout(ev)
        if A.mode == 'commit':
            return mode_commit(evAw)

        def metrics():
            d = dom('Performance.getMetrics')
            return {m['name']: m['value'] for m in d.get('metrics', []) if m['name'] in MET}

        def run(label, water, css='none', move=True):
            ev(WATER_ON if water else WATER_OFF)
            ev(SETCSS % (repr(CSSV[css]),))
            ev(REC % A.ms)
            time.sleep(0.05)
            m0 = metrics()
            t0 = time.time()
            i = 0
            while move and (time.time() - t0) * 1000 < A.ms + 250:
                p = i / 26.0
                x = W * (0.08 + 0.84 * abs(((p * 0.35) % 2) - 1))
                y = H * (0.14 + 0.72 * (0.5 + 0.5 * math.sin(p * 1.7)))
                fire('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y,
                                                  'buttons': 0, 'pointerType': 'mouse'})
                i += 1
                time.sleep(A.step / 1000.0)
            while (time.time() - t0) * 1000 < A.ms + 300:
                time.sleep(0.05)
            d = json.loads(ev('JSON.stringify(window.__P)'))
            m1 = metrics()
            el = time.time() - t0
            d['m'] = {k: round((m1.get(k, 0) - m0.get(k, 0)) * 1000, 1) for k in MET}
            d['rate'] = d['ev'] / el
            # 水面自己的出帧率：这才是"波纹看着卡不卡"对应的量。
            # 页面的 rAF 帧率和水面的出帧率在实测里始终相等（水面从不独立掉帧）⇒
            # 波纹的卡顿就是页面帧率的卡顿，不是水面自己慢。
            d['wfps'] = d['bgframes'] / (A.ms / 1000.0 + 0.3)
            print(f'  {label:22} med {d["med"]:>6}ms  p95 {d["p95"]:>6}ms  max {d["max"]:>7}ms  '
                  f'~{d["fps"]:>5}fps  帧{d["n"]:>4}  ev {d["rate"]:4.0f}/s  '
                  f'bg帧 {d["bgframes"]:>4}（水面 {d["wfps"]:5.1f}/s）')
            mm = d['m']
            print(f'{"":24}主线程任务 {mm["TaskDuration"]:7.0f}ms  脚本 {mm["ScriptDuration"]:6.0f}ms  '
                  f'样式重算 {mm["RecalcStyleDuration"]:6.0f}ms({mm["RecalcStyleCount"]:>7}次)  '
                  f'布局 {mm["LayoutDuration"]:6.0f}ms({mm["LayoutCount"]:>6}次)')
            return d

        print(f'\n每格 {A.ms}ms，鼠标节拍 {A.step}ms，视口 {W}x{H} —— 2×2 归因矩阵')
        r = {}
        r['1_idle'] = run('1 idle（不划）', True, move=False)
        r['2_water_on_hover_on'] = run('2 划卡·水开·悬停开', True, 'none')
        r['3_water_off_hover_on'] = run('3 划卡·水停·悬停开', False, 'none')
        r['4_water_off_hover_off'] = run('4 划卡·水停·悬停摘', False, 'all_off')
        r['5_water_on_hover_off'] = run('5 划卡·水开·悬停摘', True, 'all_off')
        print('\n单变量二分（基准 = 条件 2）')
        print('\n候选优化（先量再决定改不改正本）')
        for k, lbl, key in (('6_no_img', '6 只摘缩略图放大', 'no_img'),
                            ('7_no_shadow', '7 只摘悬停投影', 'no_shadow'),
                            ('8_no_trans', '8 只摘卡片过渡', 'no_trans'),
                            ('9_no_tilt', '9 只摘跟手倾斜', 'no_tilt'),
                            ('A_tilt_instant', 'A 倾斜立即·抬起仍缓动', 'cand_tilt_instant'),
                            ('B_cv_auto', 'B 离屏卡 content-visibility', 'cand_cv'),
                            ('AB_both', 'A+B 一起上', 'cand_both'),
                            ('C_trans_only', 'C 只留 transform 过渡', 'cand_trans_only'),
                            ('D_noshadow_trans', 'D 摘投影过渡留描边', 'cand_noshadow_trans'),
                            ('E_cv_plus_C', 'E = B + C', 'cand_cv_trans_only'),
                            ('F_cv_notrans', 'F = B + 过渡全摘', 'cand_notrans_cv'),
                            ('H_opacity_hover', 'H hover 走 opacity', 'cand_opacity_hover'),
                            ('I_opacity_wc', 'I = H + 那层成合成层', 'cand_opacity_wc'),
                            ('J_willchange_hover', 'J 悬停时 will-change', 'cand_wc_hover'),
                            ('K_short_trans', 'K 缩短过渡时长', 'cand_short_trans'),
                            ('K2_short_cv', 'K2 = K + 离屏跳过', 'cand_short_cv'),
                            ('L_contain', 'L contain:content', 'cand_contain'),
                            ('L2_contain_notrans', 'L2 = L + 过渡全摘', 'cand_contain_notrans'),
                            ('M_cv320', 'M cv + 估计值320', 'cand_cv320')):
            r[k] = run(lbl, True, key)
        ev(WATER_ON)
        ev(SETCSS % (repr(''),))

        base = r['2_water_on_hover_on']['med']
        floor = r['1_idle']['med']
        print('\n── 归因 ──')
        print(f'  水面的钱（2−3，悬停都开）    : {r["2_water_on_hover_on"]["med"]-r["3_water_off_hover_on"]["med"]:+7.2f}ms')
        print(f'  水面的钱（5−4，悬停都摘）    : {r["5_water_on_hover_off"]["med"]-r["4_water_off_hover_off"]["med"]:+7.2f}ms')
        print(f'  悬停的钱（2−5，水都开）      : {base-r["5_water_on_hover_off"]["med"]:+7.2f}ms')
        print(f'  悬停的钱（3−4，水都停）      : {r["3_water_off_hover_on"]["med"]-r["4_water_off_hover_off"]["med"]:+7.2f}ms')
        print('  四格中位数：水开/悬停开 %.1f ｜ 水开/悬停关 %.1f ｜ 水关/悬停开 %.1f ｜ 水关/悬停关 %.1f'
              % (r['2_water_on_hover_on']['med'], r['5_water_on_hover_off']['med'],
                 r['3_water_off_hover_on']['med'], r['4_water_off_hover_off']['med']))
        won = r['2_water_on_hover_on']['wfps']
        woff = r['5_water_on_hover_off']['wfps']
        print(f'\n── 水面的出帧率（"波纹看着卡不卡"就是这个数）──')
        print(f'  水面开·悬停开（用户报的场景）: {won:6.1f}/s')
        print(f'  水面开·悬停关              : {woff:6.1f}/s   ← 同一份水面代码，摘掉悬停后的上限')
        if won > 0:
            print(f'  ⇒ 悬停那套把水面的出帧率压掉了 {woff/won:.1f} 倍')
        print('\n── 单变量二分（比基准省多少）──')
        for k, lbl in (('6_no_img', '摘缩略图放大'), ('7_no_shadow', '摘悬停投影'),
                       ('8_no_trans', '摘卡片过渡'), ('9_no_tilt', '摘跟手倾斜'),
                       ('A_tilt_instant', 'A 倾斜立即'), ('B_cv_auto', 'B content-visibility'),
                       ('AB_both', 'A+B 一起上'), ('C_trans_only', 'C 只留 transform 过渡'),
                       ('D_noshadow_trans', 'D 摘投影过渡留描边'), ('E_cv_plus_C', 'E = B + C'),
                       ('F_cv_notrans', 'F = B + 过渡全摘'),
                       ('H_opacity_hover', 'H hover 走 opacity'),
                       ('I_opacity_wc', 'I = H + 那层成合成层'),
                       ('J_willchange_hover', 'J 悬停时 will-change'),
                       ('K_short_trans', 'K 缩短过渡时长'),
                       ('K2_short_cv', 'K2 = K + 离屏跳过'),
                       ('L_contain', 'L contain:content'),
                       ('L2_contain_notrans', 'L2 = L + 过渡全摘'),
                       ('M_cv320', 'M cv + 估计值320')):
            print(f'  {lbl:16} med {r[k]["med"]:>6}ms  省 {base-r[k]["med"]:+7.2f}ms  '
                  f'p95 {r[k]["p95"]:>6}ms  fps {r[k]["fps"]:>5}')
        print(f'  {"全摘（上界）":12} med {r["5_water_on_hover_off"]["med"]:>6}ms  '
              f'省 {base-r["5_water_on_hover_off"]["med"]:+7.2f}ms')

        ok = True
        if r['1_idle']['bgframes'] != 0:
            print('! G1 地板格 bg帧≠0 ⇒「有浪才跑」不成立'); ok = False
        for k in ('3_water_off_hover_on', '4_water_off_hover_off'):
            if r[k]['bgframes'] > 0:
                print(f'! G2 {k} bg帧={r[k]["bgframes"]} ⇒ 水面没真停，水面的差值作废'); ok = False
        # G3 阳性对照：悬停摘掉那两格必须跑回地板速度。跑不回去 = 输入通路本身是瓶颈，
        #    这时"水面很便宜"这个结论是仪器造出来的（§133 坑三的同一个陷阱）。
        for k in ('4_water_off_hover_off', '5_water_on_hover_off'):
            if r[k]['med'] > floor * 2 + 2:
                print(f'! G3 {k} med={r[k]["med"]}ms 远高于地板 {floor}ms ⇒ 输入通路是瓶颈，'
                      f'整份数字作废（把 --step 调大重跑）'); ok = False
        spread = max(r[k]['med'] for k in ('2_water_on_hover_on', '5_water_on_hover_off',
                                          '3_water_off_hover_on', '4_water_off_hover_off')) - \
                 min(r[k]['med'] for k in ('2_water_on_hover_on', '5_water_on_hover_off',
                                           '3_water_off_hover_on', '4_water_off_hover_off'))
        if spread < 5:
            print(f'! G4 四格极差只有 {spread:.1f}ms ⇒ 仪器分不开，判据无效'); ok = False
        print('\n判据: ' + ('✅ G1–G4 全过' if ok else '❌ 有红，上面的差值不可用'))
        json.dump(r, open(os.path.join(ROOT, '.diag', 'hover_frame_cost.json'), 'w',
                          encoding='utf-8'), ensure_ascii=False, indent=1)
        print('落盘 .diag/hover_frame_cost.json')
        return 0 if ok else 1
    finally:
        try:
            conn.send(json.dumps({'id': 99999, 'method': 'Browser.close'}))
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            chrome_tree.kill_tree(proc.pid)


LAY = """(()=>{
  /* 自动找真正的滚动容器：scrollHeight 明显大于 clientHeight 且 overflow-y 允许滚动的那个。
     上一版写死 '#grid'.parentElement，量到一个不滚的元素（scroll==client，判据恒绿=空转）。 */
  let best=null, bestOver=0;
  for(const el of document.querySelectorAll('body *')){
    const cs=getComputedStyle(el);
    if(!/auto|scroll/.test(cs.overflowY)) continue;
    const over=el.scrollHeight-el.clientHeight;
    if(over>bestOver){ bestOver=over; best=el; }
  }
  const g=document.getElementById('grid')||document.querySelector('[class*=grid]')||document.body;
  const c=document.querySelector('.card');
  const r=c?c.getBoundingClientRect():{width:0,height:0};
  const gcs=getComputedStyle(g);
  return JSON.stringify({scroller:best?(best.tagName+'#'+(best.id||'')+'.'+(best.className||'').toString().split(' ')[0]):null,
    scroll:best?best.scrollHeight:0, client:best?best.clientHeight:0,
    gridTag:g.tagName+'#'+(g.id||''), display:gcs.display, gap:gcs.gap,
    cols:gcs.gridTemplateColumns.split(' ').length,
    cardW:+r.width.toFixed(1), cardH:+r.height.toFixed(1),
    cards:document.querySelectorAll('.card').length});})()"""


def mode_layout(ev):
    """content-visibility 的**代价闸**：它给离屏卡一个估计尺寸，估错了滚动高度就会漂。
    判据：加规则前后 `scrollHeight` 变化必须 < 2%（卡高估计值要贴着实测卡高取）。"""
    print('\n── content-visibility 的滚动高度代价 ──')
    ev(SETCSS % (repr(''),))
    a = json.loads(ev(LAY))
    print('  原状  ', json.dumps(a, ensure_ascii=False))
    ev(SETCSS % (repr(CSSV['cand_cv_notrans_330']),))
    time.sleep(1.2)
    b = json.loads(ev(LAY))
    print('  加 cv ', json.dumps(b, ensure_ascii=False))
    ev(SETCSS % (repr(''),))
    d = abs(b['scroll'] - a['scroll']) / max(1, a['scroll'])
    print(f'\n  scrollHeight {a["scroll"]} → {b["scroll"]}（{d*100:+.2f}%）')
    print(f'  实测卡高 {a["cardH"]}px ｜ 落选用的估计值 330px ｜ 列数 {a["cols"]} ｜ '
          f'容器 {a["gridTag"]} display={a["display"]} 滚动容器 {a["scroller"]}')
    ok = d < 0.02
    print('  判据: ' + ('✅ 漂移 < 2%' if ok else f'❌ 漂移 {d*100:.2f}% ≥ 2%，估计值要改成贴着 {a["cardH"]}px'))
    return 0 if ok else 1


COMMIT_JS = r"""(()=>{
  /* 「一次合成提交有多贵」——全程不动鼠标，输入确定 ⇒ 各格直接可比。
     背景见 docs/TROUBLESHOOTING.md §143 补八~补十一：
     改 transform 会动合成器的 property tree ⇒ 触发一次完整提交；提交要遍历 main 里的子元素。
     本模式就是量「这次提交的代价 ∝ 什么」。 */
  const measure = ms => new Promise(res => {
    const t=[]; let last=performance.now(); const t0=last;
    (function f(now){ t.push(now-last); last=now;
      if(now-t0<ms) requestAnimationFrame(f);
      else { const s=t.slice(4).sort((a,b)=>a-b); res(s[s.length>>1]); } })(last);
  });
  const st=document.createElement('style'); document.head.appendChild(st);
  const d=document.createElement('div');
  d.style.cssText='position:fixed;left:10px;top:10px;width:154px;height:320px;z-index:99999;background:#4a90d9';
  document.body.appendChild(d);
  const cards=[...document.querySelectorAll('.card')];
  const showFirst=n=>cards.forEach((c,i)=>{ c.style.display = i<n ? '' : 'none'; });
  let stop=true, a=0;
  const loop=()=>{ if(stop) return; a=((a+1.7)%20)-10;
    d.style.transform='perspective(620px) rotateY('+a.toFixed(2)+'deg) rotateX('+(-a).toFixed(2)+'deg)';
    requestAnimationFrame(loop); };
  const out=[];
  const phase=(name,css,n,anim)=> (async()=>{
    stop=true; st.textContent=css; showFirst(n);
    await new Promise(r=>setTimeout(r,300));
    if(anim){ stop=false; requestAnimationFrame(loop); }
    await new Promise(r=>setTimeout(r,700));
    out.push([name, +(await measure(2200)).toFixed(2)]);
  })();
  return (async()=>{
    await phase('① 静止（壳不动）','',cards.length,false);
    await phase('② 每帧改 transform · 原状','',cards.length,true);
    await phase('③ ② + 卡片 transform:none','.card{transform:none!important}',cards.length,true);
    await phase('④ ② + 只留前 200 张卡','',200,true);
    await phase('⑤ ② + 只留前 20 张卡','',20,true);
    await phase('⑥ ② + 藏掉 main','main{display:none!important}',cards.length,true);
    stop=true; st.remove(); showFirst(cards.length); d.remove();
    return JSON.stringify({cards:cards.length, out:out});
  })();
})()"""


def mode_commit(evAw):
    """量「合成提交的代价 ∝ 什么」：全程不动鼠标（消除人手变量，见 §143 补七的教训）。"""
    print('\n── 合成提交的代价 ∝ 什么（全程不动鼠标）──')
    r = evAw(COMMIT_JS)
    if not isinstance(r, str) or r.startswith('EXC'):
        print('! 脚本失败：', r)
        return 1
    d = json.loads(r)
    print(f'  卡片总数 {d["cards"]}')
    base = None
    for name, ms in d['out']:
        if base is None:
            base = ms
        print(f'  {name:26} {ms:8.2f}ms   相对① {ms-base:+7.2f}ms')
    m = dict(d['out'])
    idle = m['① 静止（壳不动）']
    orig = m['② 每帧改 transform · 原状']
    t_none = m['③ ② + 卡片 transform:none']
    n200 = m['④ ② + 只留前 200 张卡']
    n20 = m['⑤ ② + 只留前 20 张卡']
    hidemain = m['⑥ ② + 藏掉 main']
    print(f'\n  提交的代价 = {orig - idle:+.2f}ms（原状 − 静止）')
    if hidemain <= idle * 2:
        print('  ✅ 藏掉 main 即回落地板 ⇒ 贵的是 main 的子元素数（本页 = 1021 张卡）')
    else:
        print('  ! 藏掉 main 也没回落地板 ⇒ 本机复现不出"main 是元凶"，与用户机器不同')
    print(f'  transform 节点数这一路：③ 卡片 transform:none = {t_none:.2f}ms'
          f'（{"有效" if t_none < (orig + idle) / 2 else "无效"}）')
    print(f'  元素数量这一路：④ 前200张 = {n200:.2f}ms  ⑤ 前20张 = {n20:.2f}ms')
    json.dump(d, open(os.path.join(ROOT, '.diag', 'commit_cost.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('  落盘 .diag/commit_cost.json')
    return 0

def mode_share(ev, dom, env):
    """量背景层**逐像素的可见占比**：冻结→灌满→两图相减。

    比 elementFromPoint 采样可靠：几何采样要自己推断"这层算不算挡住"，
    而这里直接问"把水面关掉/开到满，屏幕上哪些像素变了"。
    同态两张（A1/A2）量仪器噪声；噪声不为 0 就不许下结论。
    """
    from PIL import Image
    print('\n── 背景层可见占比 ──')
    print('  ', ev(STOP))
    ev(FLAT)
    a1 = shot(dom, ev, 'bgshare_A1.png')
    a2 = shot(dom, ev, 'bgshare_A2.png')
    ev(FLOOD)
    b = shot(dom, ev, 'bgshare_B.png')
    ev(FLAT)
    p1, p2, pb = a1.load(), a2.load(), b.load()
    w, h = a1.size
    rows = [0] * 50
    noise = sig = 0
    mask = Image.new('L', (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            c1, c2, cb = p1[x, y], p2[x, y], pb[x, y]
            if max(abs(c2[i] - c1[i]) for i in range(3)) > A.thr:
                noise += 1
            if max(abs(cb[i] - c2[i]) for i in range(3)) > A.thr:
                sig += 1
                rows[min(49, y * 50 // h)] += 1
                mp[x, y] = 255
    mask.save(os.path.join(ROOT, '.diag', 'bgshare_mask.png'))
    tot = w * h
    print(f'  视口 {w}x{h} = {tot}px  dpr={env["dpr"]}  画布 {env["canvas"]}')
    print(f'  仪器噪声（A2 vs A1）: {noise}px ({noise/tot*100:.4f}%)')
    print(f'  背景层可见占比      : {sig}px ({sig/tot*100:.2f}%)')
    if noise > sig * 0.02:
        print('  ! 噪声相对信号过大 ⇒ 仪器不可信，这组数字不能当结论')
    print('\n  逐 2% 高度带：')
    for j in range(50):
        v = rows[j] / (tot / 50)
        print(f'   {j*2:>3}%  {v*100:6.2f}%  ' + '#' * int(v * 50))
    print('\n  落盘 .diag/bgshare_{A1,A2,B,mask}.png')
    return 0


def shot(dom, ev, name):
    from PIL import Image
    d = dom('Page.captureScreenshot', {'format': 'png'})
    p = os.path.join(ROOT, '.diag', name)
    open(p, 'wb').write(base64.b64decode(d['data']))
    return Image.open(p).convert('RGB')


if __name__ == '__main__':
    sys.exit(main() or 0)
