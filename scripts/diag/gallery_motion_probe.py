# -*- coding: utf-8 -*-
"""画廊动效探针：在**会真实出帧**的无头 Chrome 里，逐条证明新增交互动效真的接上了、
并且系统「减少动效」时确实全部退化。

为什么不能用一个普通前台标签页测：标签处于 hidden 时 Chrome 不出帧，
CSS 动画会**冻结在起始关键帧**、`loading=lazy` 的图一张都不加载 —— 于是
「transform 不是 matrix3d」「图没淡入」全是假红灯（2026-09-28 实测踩到）。

  py -3 scripts/diag/gallery_motion_probe.py
  py -3 scripts/diag/gallery_motion_probe.py --page index_q.html --win 1440,900

判据分两类：DOM / 计算样式断言（能红，是判据）+ burst 截图（给我自己肉眼看的，不作判据）。
所有交互都走真实入口（点卡片 / 点标签 / 点开关），不直接调内部函数。
"""
import sys, os, json, time, argparse
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gallery_ui_shots import Page, BASE, preflight

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EV = lambda s: f"(()=>{{{s}}})()"


class Tab:
    def __init__(self, pg):
        self.pg = pg

    def j(self, s):
        v = self.pg.ev(EV(s))
        if isinstance(v, str) and v.startswith('EXC'):
            raise SystemExit('! 探针表达式抛错：' + v[:200])
        return json.loads(v)

    def raw(self, s):
        return self.pg.ev(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--page', default='index_q.html')
    ap.add_argument('--baseline', default='index.html',
                    help='改前页：只用它来区分「本次新引入的页面报错」和本来就有的')
    ap.add_argument('--win', default='1440,900')
    ap.add_argument('--port', type=int, default=9441)
    ap.add_argument('--out', default=os.path.join(ROOT, '.diag', 'motion'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    fails = []
    url = preflight(a.page)
    win = tuple(int(v) for v in a.win.split(','))
    profile = os.path.join(ROOT, '.diag', 'chrome_motion')
    os.makedirs(profile, exist_ok=True)

    pg = Page(a.port, profile, url, win)
    t = Tab(pg)
    pg.cmd('Page.addScriptToEvaluateOnNewDocument', {'source':
        "window.__errs=[];addEventListener('error',e=>window.__errs.push(String(e.message).slice(0,140)));"
        "addEventListener('unhandledrejection',e=>window.__errs.push('rej '+String(e.reason).slice(0,140)));"})
    pg.cmd('Emulation.setDeviceMetricsOverride',
           {'width': win[0], 'height': win[1], 'deviceScaleFactor': 1, 'mobile': False})
    # 无头实例没有真窗口焦点：document.activeElement 会设上，但 :focus 不匹配，
    # 于是「聚焦变宽」这类判据恒假（本轮实测 190→190 的假红灯）。
    pg.cmd('Emulation.setFocusEmulationEnabled', {'enabled': True})
    pg.cmd('Page.navigate', {'url': url})
    time.sleep(6)
    cards, vis, hasvt = t.j("""return JSON.stringify([document.querySelectorAll('.card').length,
      document.visibilityState, !!document.startViewTransition]);""")
    print(f'页面 {a.page}  卡片 {cards}  visibility={vis}  ViewTransition={hasvt}')
    if cards == 0:
        raise SystemExit('! 网格没渲染，后面全部无意义')
    if vis == 'hidden':
        fails.append(f'visibility={vis}：不出帧，动画冻结在起始帧，本次动效断言不可信')
    if not hasvt:
        fails.append('document.startViewTransition 不存在：圆形擦除这条只能测退化分支')

    # ── 0. 页面报错要先取基线 ────────────────────────────────────────────
    # 直接对报错断言会冤枉人：vendor 的 spine-all.js 本来就引用 THREE（正本同样报），
    # 只有「样板比正本多出来的」才是本次改动引入的。
    def err_pass(page):
        pg.ev("window.__errs=[]")
        pg.cmd('Page.navigate', {'url': f'{BASE}/{page}'})
        time.sleep(5)
        pg.ev("(()=>{const c=document.querySelectorAll('.card'); if(c[6]) c[6].click(); return 1})()")
        time.sleep(3)
        return set(json.loads(pg.ev("JSON.stringify(window.__errs)")))

    errs_base = err_pass(a.baseline)
    errs_page = err_pass(a.page)
    print(f'0 报错  正本 {len(errs_base)} 条 {sorted(errs_base)[:2]} / 样板 {len(errs_page)} 条 {sorted(errs_page)[:2]}')
    fresh = sorted(errs_page - errs_base)
    if fresh:
        fails.append(f'0 报错：样板比正本多出 {fresh}')

    # ── 1. 卡片微倾斜：变量真的被 transform 消费，且跟随鼠标两侧翻转 ──────
    tilt = t.j("""
      const c=document.querySelectorAll('.card')[4], r=c.getBoundingClientRect();
      const mk=(x,y)=>new MouseEvent('mousemove',{clientX:x,clientY:y,bubbles:true});
      c.dispatchEvent(mk(r.left+r.width*.15, r.top+r.height*.10));
      const a=[+c.style.getPropertyValue('--rx').slice(0,-3),+c.style.getPropertyValue('--ry').slice(0,-3)];
      c.dispatchEvent(mk(r.left+r.width*.85, r.top+r.height*.90));
      const b=[+c.style.getPropertyValue('--rx').slice(0,-3),+c.style.getPropertyValue('--ry').slice(0,-3)];
      return JSON.stringify({a,b,mat3d:/matrix3d/.test(getComputedStyle(c).transform)});""")
    if not (abs(tilt['a'][0]) > 1 and abs(tilt['a'][1]) > 1):
        fails.append(f'1 倾斜：鼠标在角落时 --rx/--ry 幅度太小 {tilt["a"][:2]}')
    if tilt['a'][0] * tilt['b'][0] >= 0:
        fails.append(f'1 倾斜：换到另一侧符号没翻（{tilt["a"][0]} → {tilt["b"][0]}），角度没跟随鼠标')
    if not tilt['mat3d']:
        fails.append('1 倾斜：transform 不含 matrix3d —— perspective 规则没生效或被入场动画占住')
    print(f'1 倾斜  左上 rx/ry={tilt["a"][:2]} 右下={tilt["b"][:2]} matrix3d={tilt["mat3d"]}')

    # 1b. 倾斜的成本：鼠标扫过网格时每次事件都要「读矩形 + 写两个变量 + 触发重算」。
    #     1008 张卡的网格上这玩意儿是会掉帧的，所以把成本量出来当判据看。
    perf = t.j("""
      const cs=[...document.querySelectorAll('.card')].slice(0,12);
      const mk=(x,y)=>new MouseEvent('mousemove',{clientX:x,clientY:y,bubbles:true});
      const t0=performance.now();
      for(let i=0;i<120;i++){ const c=cs[i%cs.length], r=c.getBoundingClientRect();
        c.dispatchEvent(mk(r.left+r.width*(0.2+(i%5)/10), r.top+r.height*(0.15+(i%7)/10)));
        getComputedStyle(c).transform; }
      const nz=cs.filter(c=>Math.abs(+c.style.getPropertyValue('--ry').slice(0,-3))>0.5).length;
      return JSON.stringify({ms:+(performance.now()-t0).toFixed(1), nz,
        ry:+cs[cs.length-1].style.getPropertyValue('--ry').slice(0,-3)});""")
    per = perf['ms'] / 120
    print(f'1b 成本 120 次事件 {perf["ms"]}ms（{per:.2f}ms/次，60fps 预算 16.7ms）非零卡面 {perf["nz"]}/12 末卡 ry={perf["ry"]}')
    # 计时必须证明它真的在驱动倾斜，否则测的只是 getBoundingClientRect 的空转。
    # 注意设计上是「只有一张卡带倾角」：换卡时上一张会被归零，所以 nz 期望是 1。
    if perf['nz'] != 1 or abs(perf['ry']) < 0.5:
        fails.append(f'1b 成本：循环后带倾角的卡 {perf["nz"]} 张 / 末卡 ry={perf["ry"]}，没在驱动倾斜')
    if per > 4:
        fails.append(f'1b 成本：{per:.2f}ms/次事件，鼠标一动就吃掉 {per/16.7*100:.0f}% 帧预算，太贵')

    # ── 1c. 掠过高光必须已经拿掉（用户嫌闪，2026-09-28 明确否掉）──────────
    sheen = t.j("""
      const th=document.querySelector('.card .thumb');
      const cs=getComputedStyle(th,'::after');
      const css=[...document.styleSheets].flatMap(s=>{try{return [...s.cssRules].map(r=>r.cssText)}catch(e){return []}})
        .join('|');
      return JSON.stringify({anim:cs.animationName, content:cs.content, keyframes:/@keyframes sheen/.test(css)});""")
    print(f'1c 高光  animation={sheen["anim"]} content={sheen["content"]} 还留着@keyframes sheen={sheen["keyframes"]}')
    if sheen['keyframes'] or sheen['anim'] != 'none' or sheen['content'] not in ('none', 'normal'):
        fails.append(f'1c 高光：掠过高光没删干净（{sheen}）')

    # ── 2. 缩略图淡入：load 接线（图不淡入 = 永远透明，属于改坏）──────────
    fade = t.j("""
      const im=[...document.querySelectorAll('.card .thumb img')];
      return JSON.stringify({n:im.length, ld:im.filter(i=>i.classList.contains('ld')).length,
        cmp:im.filter(i=>i.complete).length,
        stuck:im.filter(i=>i.complete && !i.classList.contains('ld')).length});""")
    if fade['ld'] == 0:
        fails.append(f'2 淡入：没有一张图加上 .ld（complete={fade["cmp"]}）→ 图会一直透明')
    # 判据是「到货了却没亮」，不是「还没到货」：懒加载的图本来就该是透明的
    if fade['stuck']:
        fails.append(f'2 淡入：{fade["stuck"]} 张图已 complete 但仍 opacity:0（load 接线漏了）')
    print(f'2 淡入  图 {fade["n"]}  已淡入 {fade["ld"]}  已到货未亮 {fade["stuck"]}')

    # ── 2b. 头部类别胶囊：同一套「会滚的选中态」，且点击仍然真的在筛选 ────
    seg = t.j("""
      const seg=document.getElementById('fCat'), sl=seg.querySelector('.segslide');
      if(!sl) return JSON.stringify({err:'NO_SEG_SLIDE'});
      const num=v=>+String(v).slice(0,-2);
      const o0=seg.querySelector('button.on');
      const v0=[num(sl.style.getPropertyValue('--x')),num(sl.style.getPropertyValue('--w'))];
      const n0=document.querySelectorAll('.card').length;
      seg.querySelectorAll('button')[1].click();
      const o1=seg.querySelector('button.on');
      return JSON.stringify({v0, w0:[o0.offsetLeft,o0.offsetWidth],
        v1:[num(sl.style.getPropertyValue('--x')),num(sl.style.getPropertyValue('--w'))],
        w1:[o1.offsetLeft,o1.offsetWidth], n0, n1:document.querySelectorAll('.card').length,
        onbg:getComputedStyle(o1).backgroundImage, label:o1.textContent});""")
    if seg.get('err'):
        fails.append('2b 类别胶囊：#fCat 里没有 .segslide 节点')
    else:
        print(f'2b 类别  落位 {seg["v0"]}→{seg["v1"]}（应为 {seg["w0"]}→{seg["w1"]}）'
              f' 卡片 {seg["n0"]}→{seg["n1"]} 选中「{seg["label"]}」')
        for k in range(2):
            if abs(seg['v0'][k] - seg['w0'][k]) > 1.5:
                fails.append(f'2b 类别：初始落位偏差 >1.5px（{seg["v0"]} vs {seg["w0"]}）')
            if abs(seg['v1'][k] - seg['w1'][k]) > 1.5:
                fails.append(f'2b 类别：切换后落位偏差 >1.5px（{seg["v1"]} vs {seg["w1"]}）')
        if abs(seg['v1'][0] - seg['v0'][0]) < 20:
            fails.append(f'2b 类别：胶囊位移只有 {seg["v1"][0]-seg["v0"][0]}px，这条断言是空的')
        if seg['n1'] == seg['n0']:
            fails.append(f'2b 类别：点「{seg["label"]}」后卡片数没变（{seg["n0"]}）——筛选被改坏了')
        if seg['onbg'] != 'none':
            fails.append(f'2b 类别：选中那颗自己还留着背景 {seg["onbg"][:40]}')
        t.raw("document.querySelector('#fCat button').click()")
        time.sleep(0.4)

    # ── 2c. 搜索框聚焦变宽 ───────────────────────────────────────────────
    se0 = t.j("""const s=document.getElementById('search');
      return JSON.stringify([parseFloat(getComputedStyle(s).width), document.hasFocus()]);""")
    t.raw("document.getElementById('search').focus()")
    # 无头出帧慢（实测 ~8fps），0.28s 的宽度过渡要等**足够多帧**才会走完；
    # 等 1.2s 是给这条判据留出真实余量，否则量到的是"动画还没开始"而不是"没接线"。
    time.sleep(1.2)
    se1 = t.j("""const s=document.getElementById('search'), cs=getComputedStyle(s);
      return JSON.stringify([parseFloat(cs.width), s.matches(':focus'), cs.flexShrink,
        parseFloat(cs.width) /* 实际用值 */, 270 /* 规则里写的值 */]);""")
    t.raw("document.getElementById('search').blur()")
    print(f'2c 搜索  宽 {se0[0]} → 聚焦 {se1[0]}（:focus={se1[1]} flex-shrink={se1[2]} 规则值={se1[4]}）')
    if not se1[1]:
        fails.append('2c 搜索：:focus 没命中（焦点模拟没生效），这条测不到变宽')
    if se1[0] - se0[0] < 20:
        # flex-shrink 会把"指定宽度"压回"实际用值"，这两种失败要能一眼分开
        fails.append(f'2c 搜索：聚焦后没变宽（{se0[0]} → {se1[0]}，:focus={se1[1]}，'
                     f'flex-shrink={se1[2]}；若 :focus=True 而宽度仍小，是被 flex 压掉了）')


    # ── 3. 弹层从卡片飞入 + 关闭按原路缩回（一次开合测两条）───────────────
    fly = t.j("""
      const c=document.querySelectorAll('.card')[6]; c.scrollIntoView({block:'center'});
      const tr=c.querySelector('.thumb').getBoundingClientRect();
      c.click();
      const m=document.querySelector('.modal'), b=m.getBoundingClientRect();
      return JSON.stringify({cls:m.className, on:document.getElementById('mask').classList.contains('on'),
        fx:m.style.getPropertyValue('--fx'), fy:m.style.getPropertyValue('--fy'),
        fs:m.style.getPropertyValue('--fs'), mw:b.width, cardw:tr.width});""")
    print(f'3 飞入  class={fly["cls"]!r} --fx {fly["fx"]} --fy {fly["fy"]} --fs {fly["fs"]}')
    if 'fly' not in fly['cls']:
        fails.append(f'3 飞入：点卡片后 .modal 没有 fly 类（{fly["cls"]!r}）')
    if not fly['fx'] or not fly['fy'] or abs(float(fly['fx'][:-2])) < 20:
        fails.append(f'3 飞入：起点位移没量出来 fx={fly["fx"]} fy={fly["fy"]}')
    if not (0 < float(fly['fs'] or 0) < 0.6):
        fails.append(f'3 飞入：起始缩放比不合理 fs={fly["fs"]}（卡片宽/弹层宽）')

    # 滑块落位（弹层已开）：--x/--y/--w/--h 必须等于选中那颗的**布局**尺寸。
    # 判据一律用 offset*：飞入动画的 scale 会污染 getBoundingClientRect，
    # 用 rect 比对就是把「探针自己的错」当成「产品的错」（本轮真实踩过）。
    sl0 = t.j("""
      const tl=document.getElementById('mTabs'), s=tl.querySelector('.tslide'), on=tl.querySelector('.tab.on');
      if(!s) return JSON.stringify({err:'NO_SLIDE'});
      return JSON.stringify({v:[s.style.getPropertyValue('--x'),s.style.getPropertyValue('--y'),
        s.style.getPropertyValue('--w'),s.style.getPropertyValue('--h')],
        want:[on.offsetLeft,on.offsetTop,on.offsetWidth,on.offsetHeight], txt:on.textContent});""")
    if sl0.get('err'):
        fails.append('4 滑块：#mTabs 里没有 .tslide 节点')
    else:
        dev = [round(abs(float(sl0['v'][k][:-2]) - sl0['want'][k]), 1) for k in range(4)]
        print(f'4 滑块  打开时落在「{sl0["txt"]}」 v={sl0["v"]} 偏差 {dev}')
        if max(dev) > 1.5:
            fails.append(f'4 滑块：落位与选中标签布局偏差 >1.5px（{sl0["v"]} vs {sl0["want"]}）')
        if sl0['want'][2] < 40:
            fails.append(f'4 滑块：选中标签宽度 {sl0["want"][2]} < 40px，这条落位断言是空的')

    # 切标签：滑块得飞过去
    sl1 = t.j("""
      const tl=document.getElementById('mTabs'), s=tl.querySelector('.tslide');
      const tabs=[...tl.querySelectorAll('.tab')].filter(x=>!x.classList.contains('dis'));
      if(tabs.length<2) return JSON.stringify({err:'ONLY_ONE_TAB'});
      const target=tabs[tabs.length-1];
      target.click();
      return JSON.stringify({v:[+s.style.getPropertyValue('--x').slice(0,-2),+s.style.getPropertyValue('--w').slice(0,-2)],
        want:[target.offsetLeft,target.offsetWidth], moved:Math.abs(+s.style.getPropertyValue('--x').slice(0,-2)-%s),
        onbg:getComputedStyle(target).backgroundImage,
        still:[...tl.querySelectorAll('.tab.on')].map(x=>x.textContent)});"""
               % (sl0['want'][0] if not sl0.get('err') else 0))
    if sl1.get('err'):
        print(f'4 滑块  跳过切标签（{sl1["err"]}）')
    else:
        print(f'4 滑块  切到「{sl1["still"]}」后 v={sl1["v"]}（应为 {sl1["want"]}，位移 {sl1["moved"]:.1f}px）')
        if abs(sl1['v'][0] - sl1['want'][0]) > 1.5 or abs(sl1['v'][1] - sl1['want'][1]) > 1.5:
            fails.append(f'4 滑块：切标签后没跟到 {sl1["want"]}（实测 {sl1["v"]}）')
        if sl1['moved'] < 20:
            fails.append(f'4 滑块：切标签位移只有 {sl1["moved"]:.1f}px，这条断言是空的')
        if sl1['onbg'] != 'none':
            fails.append(f'4 滑块：选中标签自己还留着背景 {sl1["onbg"][:50]} —— 会和滑块叠成两层')
        pg.shot(os.path.join(a.out, 'tab_slide.png'))
        t.j("""document.querySelector('.close').click();
          const m=document.querySelector('.modal');
          return JSON.stringify({cls:m.className,
            closing:document.getElementById('mask').classList.contains('closing')});""")
        fo = t.raw("""JSON.stringify([document.querySelector('.modal').className,
          document.getElementById('mask').classList.contains('closing'),
          document.querySelector('.modal').style.getPropertyValue('--fx')])""")
        cls, closing, fx2 = json.loads(fo)
        print(f'5 缩回  class={cls!r} closing={closing} --fx={fx2}')
        if 'flyout' not in cls or not closing:
            fails.append(f'5 缩回：点关闭后没进 flyout/closing（{cls!r} / {closing}）')
        time.sleep(1.0)
        gone = t.raw("""JSON.stringify([document.getElementById('mask').classList.contains('on'),
          document.querySelector('.modal').classList.contains('flyout')])""")
        if any(json.loads(gone)):
            fails.append(f'5 缩回：1s 后弹层仍开着或 flyout 未清 {gone}')
    after = t.j("""const m=document.querySelector('.modal');
      return JSON.stringify({cls:m.className, mat:getComputedStyle(m).transform});""")
    if 'fly' in after['cls']:
        fails.append('3 飞入：动画结束后 fly 类没摘掉（会盖住下一次关闭动画）')
    if after['mat'] != 'none':
        fails.append(f'3 飞入：动画结束后弹层仍带 transform {after["mat"]}')

    # ── 5b. 背景着色器：WebGL2 真编译上了、画面真在动、鼠标真在影响它 ──────
    bg = t.j("""
      const host=document.getElementById('bgfx'), cv=host&&host.querySelector('canvas');
      const cs=host?getComputedStyle(host):null, m=getComputedStyle(document.getElementById('main'));
      return JSON.stringify({has:!!host, dis:cs&&cs.display, pe:cs&&cs.pointerEvents,
        z:cs&&cs.zIndex, mz:m.zIndex, cvw:cv?cv.width:0, cvh:cv?cv.height:0,
        mode:BG.mode, err:BG.err, uni:Object.keys(BG.u).length, rs:BG.rs,
        P:BG.P, frames:BG.frames, raf:BG.raf>0,
        glow:getComputedStyle(host.querySelector('.glow')).display});""")
    if not bg['has'] or bg['dis'] == 'none':
        fails.append(f'5b 背景：#bgfx 不存在或默认就是关的（display={bg.get("dis")}）')
    else:
        P = bg['P'] or {}
        print(f'5b 背景  mode={bg["mode"]} err={bg["err"][:60]!r} canvas {bg["cvw"]}x{bg["cvh"]} '
              f'渲染缩放={bg["rs"]} uniform {bg["uni"]} 个 z={bg["z"]}/内容{bg["mz"]} pe={bg["pe"]} '
              f'CSS辉光={bg["glow"]}')
        if bg['pe'] != 'none':
            fails.append(f'5b 背景：pointer-events={bg["pe"]}，会吃掉卡片点击')
        if int(bg['z']) >= int(bg['mz']):
            fails.append(f'5b 背景：z-index {bg["z"]} 没低于内容 {bg["mz"]}，会盖画')
        if bg['mode'] != 'gl':
            fails.append(f'5b 背景：没走成 WebGL2（mode={bg["mode"]} err={bg["err"][:120]}）')
        elif bg['uni'] < 23:
            fails.append(f'5b 背景：只取到 {bg["uni"]} 个 uniform 位置，着色器接口对不上')
        elif bg['cvw'] < 100 or bg['cvh'] < 100:
            fails.append(f'5b 背景：canvas 尺寸 {bg["cvw"]}x{bg["cvh"]} 没铺上')
        elif bg['glow'] != 'none':
            fails.append('5b 背景：着色器起来了但 CSS 辉光没退休，两层会叠')
        elif not 0.4 < bg['rs'] < 1.0:
            fails.append(f'5b 背景：渲染缩放 {bg["rs"]} 没起作用（成本主要靠它）')
        # 「画面里真有东西」判据：必须**同一次 evaluate 里 draw 完立刻 readPixels**，
        # 跨调用读会拿到空缓冲（preserveDrawingBuffer=false）——那是假黑屏。
        px = t.j("""
          const gl=BG.gl, w=gl.drawingBufferWidth, h=gl.drawingBufferHeight, N=160;
          /* 先把指针停到角落再读：否则量到的是"鼠标光斑"而不是底图，
             均值/标准差/时间差全被光斑带偏（本轮就是这么把白天量成 253 的） */
          BG.ux=0.02; BG.uy=0.02; BG.vel=0; bgDraw(performance.now()+40);
          const grab=()=>{ BG.clock+=0.9; bgDraw(performance.now()+50);
            const b=new Uint8Array(N*N*4);
            gl.readPixels((w-N)>>1,(h-N)>>1,N,N,gl.RGBA,gl.UNSIGNED_BYTE,b);
            let s=0,ss=0; for(let i=0;i<b.length;i+=4){ const L=0.299*b[i]+0.587*b[i+1]+0.114*b[i+2];
              s+=L; ss+=L*L; }
            const n=b.length>>2; return {b, mean:s/n, sd:Math.sqrt(Math.max(0,ss/n-(s/n)*(s/n)))}; };
          const A=grab(), B=grab();
          let mad=0; for(let i=0;i<A.b.length;i+=4)
            mad+=Math.abs(A.b[i]-B.b[i])+Math.abs(A.b[i+1]-B.b[i+1])+Math.abs(A.b[i+2]-B.b[i+2]);
          return JSON.stringify({mA:+A.mean.toFixed(2), sdA:+A.sd.toFixed(2),
            sdB:+B.sd.toFixed(2), mad:+(mad/(A.b.length/4*3)).toFixed(2)});""")
        print(f'5b 画面  中心块 均值={px["mA"]} 标准差={px["sdA"]}→{px["sdB"]} 两帧逐通道平均差={px["mad"]}')
        if px['sdA'] < 3:
            fails.append(f'5b 画面：中心块标准差只有 {px["sdA"]}，等于一片纯色（着色器没画出结构）')
        # 亮度带：用户判过"白天整体太亮"（整屏削顶到 255）与"太暗"两种失败，
        # 所以白天均值必须落在一个区间里，而不是只判"有内容"。
        if not 120 < px['mA'] < 240:
            fails.append(f'5b 画面：白天中心均值 {px["mA"]} 不在 (120,240) —— 过曝或过暗')
        if px['mad'] < 1.0:
            fails.append(f'5b 画面：推进时钟后逐像素平均差只有 {px["mad"]}，时间没真接进着色器')
        # 鼠标影响：**固定采同一块区域**，只换鼠标位置（换位置又换采样区就分不开是谁变的）
        mo = t.j("""
          const gl=BG.gl, w=gl.drawingBufferWidth, h=gl.drawingBufferHeight, N=140;
          const at=(mx,my)=>{ BG.ux=mx; BG.uy=my; BG.vel=1; bgDraw(performance.now()+60);
            const b=new Uint8Array(N*N*4); gl.readPixels((w-N)>>1,(h-N)>>1,N,N,gl.RGBA,gl.UNSIGNED_BYTE,b);
            let s=0; for(let i=0;i<b.length;i+=4) s+=0.299*b[i]+0.587*b[i+1]+0.114*b[i+2];
            return s/(b.length>>2); };
          return JSON.stringify({inC:+at(0.5,0.5).toFixed(2), out:+at(0.03,0.03).toFixed(2),
            again:+at(0.5,0.5).toFixed(2)});""")
        print(f'5b 鼠标  指针在采样区里 {mo["inC"]} / 移开 {mo["out"]} / 移回来 {mo["again"]}')
        # 门槛按"用户真能看见"定：上一版量到 9 个亮度单位，用户肉眼判"约等于 0"。
        # 所以这里要 ≥6 且**在浅色主题**（效果最弱的那套）下量。
        if abs(mo['inC'] - mo['out']) < 6:
            fails.append(f'5b 鼠标：指针进出采样区只差 {abs(mo["inC"]-mo["out"]):.1f} 亮度，肉眼约等于没反应（{mo}）')
        if abs(mo['inC'] - mo['again']) > 0.8:
            fails.append(f'5b 鼠标：同一位置两次读数差 {abs(mo["inC"]-mo["again"])}，测的不是鼠标而是漂移')
        # 「像大海」的两条结构判据：横向特征比竖向宽（洋流是横着走的）、上浅下深（有深度）
        oc = t.j("""
          const gl=BG.gl, w=gl.drawingBufferWidth, h=gl.drawingBufferHeight;
          BG.clock+=0.5; bgDraw(performance.now()+80);
          const SW=Math.min(360,w-8), SH=Math.min(240,h-8), x0=(w-SW)>>1, y0=(h-SH)>>1;
          const raw=new Uint8Array(SW*SH*4); gl.readPixels(x0,y0,SW,SH,gl.RGBA,gl.UNSIGNED_BYTE,raw);
          const L=new Float32Array(SW*SH);
          for(let i=0;i<SW*SH;i++) L[i]=0.299*raw[i*4]+0.587*raw[i*4+1]+0.114*raw[i*4+2];
          let hx=0,vy=0;
          for(let y=1;y<SH-1;y++) for(let x=1;x<SW-1;x++){
            hx+=Math.abs(L[y*SW+x+1]-L[y*SW+x]);
            vy+=Math.abs(L[(y+1)*SW+x]-L[y*SW+x]); }
          const N=(SW-2)*(SH-2);
          const band=(a,b)=>{ let s=0,c=0; for(let y=a;y<b;y++) for(let x=1;x<SW-1;x+=3){ s+=L[y*SW+x]; c++; } return s/c; };
          /* readPixels 的 y=0 是画面底部，所以"海面"取高 y 段 */
          return JSON.stringify({ahx:+(hx/N).toFixed(3), avy:+(vy/N).toFixed(3),
            top:+band(SH-40,SH-6).toFixed(1), bot:+band(6,40).toFixed(1)});""")
        ratio = oc['avy'] / max(oc['ahx'], 1e-3)
        print(f'5c 海洋  横向梯度={oc["ahx"]} 纵向梯度={oc["avy"]}（各向异性 {ratio:.2f}×） '
              f'上段亮度 {oc["top"]} vs 下段 {oc["bot"]}')
        if ratio < 1.25:
            fails.append(f'5c 海洋：横向/纵向特征各向异性只有 {ratio:.2f}×，看不出"横着走的海流"')
        if oc['top'] - oc['bot'] < 6:
            fails.append(f'5c 海洋：上段 {oc["top"]} 没比下段 {oc["bot"]} 亮，深度感（上浅下深）没成立')
        # 单帧成本：手动 20 帧，每帧后补一次 1x1 readPixels **强制同步等待** ——
        # WebGL 是异步的，只计"提交"会量出 0.0x ms 的假便宜数字。
        cost = t.j("""
          cancelAnimationFrame(BG.raf); BG.raf=0;
          const gl=BG.gl, t0=performance.now(), px1=new Uint8Array(4);
          for(let i=0;i<20;i++){ BG.clock+=0.016; bgDraw(performance.now()+i*16.7);
            gl.readPixels(0,0,1,1,gl.RGBA,gl.UNSIGNED_BYTE,px1); }
          const ms=(performance.now()-t0)/20;
          BG.raf=0; BG.last=performance.now(); bgApply();     // 上面喂的是未来时间戳，必须掰回现在
          return JSON.stringify({ms:+ms.toFixed(2), raf:BG.raf>0});""")
        print(f'5b 成本  单帧 {cost["ms"]}ms（**软件光栅 + 每帧同步读回的上限**，无头量不出真机 GPU 成本，'
              f'只用来抓"病态地贵"）；计时后循环已恢复={cost["raf"]}')
        # 阈值按"病态"定，不按"贵"定：无头 swiftshader 下这个数字比真机高一个量级，
        # 拿它当帧预算判据会把环境当缺陷（真要判帧预算得在真 GPU 上量）。
        if cost['ms'] > 100:
            fails.append(f'5b 成本：单帧 {cost["ms"]}ms，已经病态（正常软件光栅也在几十 ms 量级）')
        if not cost['raf']:
            fails.append('5b 成本：计时之后 rAF 没恢复，后面的断言会全测到静止画面')
        f0 = t.j("return JSON.stringify([BG.frames,BG.clock,BG.tlast-BG.ts0]);")
        time.sleep(0.5)
        f1 = t.j("return JSON.stringify([BG.frames,BG.clock,BG.tlast-BG.ts0]);")
        dfr, dcl, dts = f1[0] - f0[0], f1[1] - f0[1], (f1[2] - f0[2]) / 1000
        # 动画时钟的正确参照是**帧时间线**（rAF 时间戳），不是墙钟：无头里 rAF 时间戳
        # 推进得远慢于墙钟（本轮实测墙钟 0.5s 只走了 ~0.05s 的帧时间线），拿墙钟判会把
        # 环境当缺陷。所以判两件事：时钟在走，且**不快过帧时间线**（dt 单位/累加写错会爆）。
        print(f'5b 时钟  0.5s 推进 {dfr} 帧，帧时间线走 {dts:.3f}s，动画时钟走 {dcl:.3f}s（墙钟不作判据）')
        if dfr < 1:
            fails.append('5b 时钟：rAF 一帧都没推进')
        if dcl <= 0:
            fails.append('5b 时钟：动画时钟没走')
        if dcl > dts + 0.03:
            fails.append(f'5b 时钟：动画时钟 {dcl:.3f}s 快过帧时间线 {dts:.3f}s，dt 尺度错了')
        # 弹层几乎铺满视口，挡着的时候不许白画
        t.j("document.querySelectorAll('.card')[6].click(); return JSON.stringify([1]);")
        time.sleep(0.35)
        g0 = t.j("return JSON.stringify(BG.frames);"); time.sleep(0.5)
        g1 = t.j("return JSON.stringify(BG.frames);")
        print(f'5b 背景  弹层开着 0.5s 推进 {g1-g0} 帧（应≈0）')
        if g1 - g0 > 3:
            fails.append(f'5b 背景：弹层挡着仍在画（0.5s {g1-g0} 帧）')
        t.raw("document.querySelector('.close').click()")
        time.sleep(0.7)
        tg = t.j("""document.querySelector('#gOpt button[data-k=bgfx]').click();
          return JSON.stringify({dis:getComputedStyle(document.getElementById('bgfx')).display,
            raf:BG.raf, ls:JSON.parse(localStorage.getItem('gallery.opt.v1')||'{}').bgfx});""")
        print(f'5b 背景  关掉开关 → {tg}')
        pg.shot(os.path.join(a.out, 'bg_off.png'))      # 出图供肉眼比"加不加背景差多少"
        if tg['dis'] != 'none' or tg['raf'] != 0 or tg['ls'] is not False:
            fails.append(f'5b 背景：开关没把整块关掉（含辉光）：{tg}')
        t.raw("document.querySelector('#gOpt button[data-k=bgfx]').click()")
        time.sleep(0.35)
        pg.shot(os.path.join(a.out, 'bg_on.png'))
        bk = t.j("""return JSON.stringify([getComputedStyle(document.getElementById('bgfx')).display, BG.raf>0]);""")
        if bk[0] == 'none' or not bk[1]:
            fails.append(f'5b 背景：重新打开后没恢复（{bk}）')

    # ── 6. 昼夜圆形擦除：圆心取自被点的开关 ──────────────────────────────
    th = t.j("""
      const b=document.querySelector('#gTheme button[data-t=dark]'), r=b.getBoundingClientRect();
      b.click();
      const h=document.documentElement;
      return JSON.stringify({cx:h.style.getPropertyValue('--cx'), cy:h.style.getPropertyValue('--cy'),
        theme:h.dataset.theme, ls:localStorage.getItem('gallery.theme'),
        expectX:(r.left+r.width/2)/h.clientWidth*100});""")
    time.sleep(0.16)
    pg.shot(os.path.join(a.out, 'theme_wipe.png'))       # 可能落在擦除中途，只作肉眼参考
    time.sleep(1.3)
    th2 = t.j("""const h=document.documentElement, b=document.querySelector('#gTheme button[data-t=dark]');
      return JSON.stringify({theme:h.dataset.theme, on:b.classList.contains('on'),
        ls:localStorage.getItem('gallery.theme'),
        anim:document.getAnimations().filter(x=>x.animationName==='vtwipe').length});""")
    print(f'6 昼夜  --cx {th["cx"]} --cy {th["cy"]}（按钮中心 {th["expectX"]:.1f}%）→ {th2}')
    if not th['cx'] or abs(float(th['cx'][:-1]) - th['expectX']) > 1:
        fails.append(f'6 昼夜：--cx 没跟随开关位置（{th["cx"]} vs {th["expectX"]:.1f}%）')
    # ⚠️ theme/localStorage 是在 startViewTransition 的回调里写的，点击那一刻还没落，
    #    必须等快照换完再读（本轮在这里读到过"还是 light"的假红灯）。
    if th2['theme'] != 'dark' or th2['ls'] != 'dark':
        fails.append(f"6 昼夜：切换后主题没落到 dark（theme={th2['theme']} ls={th2['ls']}）")
    if not th2['on']:
        fails.append('6 昼夜：夜那颗胶囊没进入选中态')
    # 夜里着色器要换档：更深的色带、更强的暗角与自发光、整体更暗
    dk = t.j("""
      const gl=BG.gl, w=gl.drawingBufferWidth, h=gl.drawingBufferHeight, N=140;
      BG.clock+=1.3; bgDraw(performance.now()+70);
      const b=new Uint8Array(N*N*4); gl.readPixels((w-N)>>1,(h-N)>>1,N,N,gl.RGBA,gl.UNSIGNED_BYTE,b);
      let s=0; for(let i=0;i<b.length;i+=4) s+=0.299*b[i]+0.587*b[i+1]+0.114*b[i+2];
      const SW=300, SH=200, raw=new Uint8Array(SW*SH*4);
      gl.readPixels((w-SW)>>1,(h-SH)>>1,SW,SH,gl.RGBA,gl.UNSIGNED_BYTE,raw);
      const L=i=>0.299*raw[i*4]+0.587*raw[i*4+1]+0.114*raw[i*4+2];
      const band=(a,bb)=>{ let t=0,c=0; for(let y=a;y<bb;y++) for(let x=1;x<SW-1;x+=3){ t+=L(y*SW+x); c++; } return t/c; };
      return JSON.stringify({P:BG.P, mean:+(s/(b.length>>2)).toFixed(2),
        top:+band(SH-34,SH-6).toFixed(1), bot:+band(6,34).toFixed(1)});""")
    dP = dk['P']
    print(f'6 昼夜  夜里 alpha={dP["alpha"]} vig={dP["vig"]} bloom={dP["bS"]} 色带 {dP["c"][1]}→{dP["c"][3]} '
          f'中心亮度={dk["mean"]} 上段 {dk["top"]} vs 下段 {dk["bot"]}（白天 vig={bg["P"]["vig"]} bloom={bg["P"]["bS"]}）')
    if dP['c'] == bg['P']['c']:
        fails.append('6 昼夜：换夜后着色器色带没换（还是白天那套浅色）')
    if not (dP['vig'] > bg['P']['vig'] and dP['bS'] > bg['P']['bS']):
        fails.append(f'6 昼夜：夜里暗角/自发光没加强（vig {bg["P"]["vig"]}→{dP["vig"]}, bloom {bg["P"]["bS"]}→{dP["bS"]}）')
    if dk['mean'] > 110:
        fails.append(f'6 昼夜：夜里画面中心亮度 {dk["mean"]}，"深海"没出来（应明显暗于白天）')
    if dk['top'] - dk['bot'] < 6:
        fails.append(f'6 昼夜：夜里上段 {dk["top"]} 没比下段 {dk["bot"]} 亮，海面的光没进来')
    pg.shot(os.path.join(a.out, 'theme_dark.png'))
    t.raw("document.querySelector('#gTheme button[data-t=light]').click()")
    time.sleep(1.2)

    # ── 7. 反向证据：要求减少动效时全部退化 ──────────────────────────────
    pg.cmd('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
    time.sleep(0.5)
    rm = t.j("""
      const c=document.querySelectorAll('.card')[6]; c.scrollIntoView({block:'center'}); c.click();
      const m=document.querySelector('.modal'), im=document.querySelector('.card .thumb img');
      return JSON.stringify({fly:m.className, RM:matchMedia('(prefers-reduced-motion: reduce)').matches,
        op:im?getComputedStyle(im).opacity:'no-img',
        bg:getComputedStyle(document.getElementById('bgfx')).display, raf:BG.raf});""")
    print(f'7 减动效  class={rm["fly"]!r} RM={rm["RM"]} 图 opacity={rm["op"]} 背景 display={rm["bg"]}')
    if not rm['RM']:
        fails.append('7 减动效：媒体模拟没生效，这条断言是空的')
    if 'fly' in rm['fly']:
        fails.append('7 减动效：仍播放飞入动画')
    if rm['op'] != '1':
        fails.append(f'7 减动效：缩略图仍依赖淡入（opacity={rm["op"]}），关掉动画后可能永久不可见')
    if rm['bg'] != 'none' or rm['raf'] != 0:
        fails.append(f'7 减动效：背景层没整块停掉（display={rm["bg"]} rAF={rm["raf"]}）')
    t.raw("document.querySelector('.close').click()")
    time.sleep(0.8)
    if t.j("return JSON.stringify([document.getElementById('mask').classList.contains('on')]);")[0]:
        fails.append('7 减动效：关闭动画被跳过后弹层没能真关上')

    # ── 8. 定格飞入中间帧（纯出图，放在最后：会篡改动画状态）─────────────
    # 必须先把 reduce 模拟撤掉，否则 flyGeom 走退化分支、根本不会有 flyin 动画
    pg.cmd('Emulation.setEmulatedMedia', {'features': []})
    time.sleep(0.4)
    t.raw("localStorage.clear()")
    pg.cmd('Page.navigate', {'url': url})
    time.sleep(5)
    for frac in ('0.12', '0.3'):
        mid = t.j("""
          const c=document.querySelectorAll('.card')[6]; c.scrollIntoView({block:'center'}); c.click();
          const a=document.getAnimations().filter(x=>x.animationName==='flyin');
          if(!a.length) return JSON.stringify({r:'NO_ANIM'});
          a[0].pause(); a[0].currentTime=a[0].effect.getTiming().duration*%s;
          return JSON.stringify({r:'paused', dur:a[0].effect.getTiming().duration,
            mat:getComputedStyle(document.querySelector('.modal')).transform.slice(0,28)});""" % frac)
        print(f'8 中间帧 {frac}  {mid}')
        if mid['r'] == 'paused':
            pg.shot(os.path.join(a.out, f'fly_mid_{frac}.png'))
        else:
            fails.append(f'8 中间帧 {frac}：拿不到 flyin 动画对象，飞入可能根本没跑')
        t.raw("(()=>{const a=document.getAnimations().filter(x=>x.animationName==='flyin');"
              "a.forEach(x=>x.cancel());document.querySelector('.modal').classList.remove('fly');})()")
        time.sleep(0.3)

    pg.close()
    print('\n截图：', a.out)
    if fails:
        print('!! 未通过：')
        for f in fails:
            print('  -', f)
        sys.exit(1)
    print('通过：倾斜 / 淡入 / 飞入 / 滑块 / 缩回 / 圆形擦除 / 减少动效退化 全部落到位')


if __name__ == '__main__':
    main()
