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

    # ── 5b. 背景粒子：星野在动、真有景深、不遮内容、弹层挡着时不画、开关整块关 ──
    bg = t.j("""
      const host=document.getElementById('bgfx'), cv=host&&host.querySelector('canvas');
      const cs=host?getComputedStyle(host):null, m=getComputedStyle(document.getElementById('main'));
      return JSON.stringify({has:!!host, dis:cs&&cs.display, pe:cs&&cs.pointerEvents,
        z:cs&&cs.zIndex, mz:m.zIndex, cvw:cv?cv.width:0, cvh:cv?cv.height:0,
        frames:BG.frames, n:BG.p.length, layers:[...new Set(BG.p.map(q=>q.L))].sort(),
        sp:BG.sp.length, rad:[...new Set(BG.p.map(q=>+q.r.toFixed(1)))].length,
        blend:BG.col&&BG.col.blend, shoot:BG.col&&BG.col.shoot,
        depths:BG_L.map(l=>l.d), raf:BG.raf>0});""")
    if not bg['has'] or bg['dis'] == 'none':
        fails.append(f'5b 背景：#bgfx 不存在或默认就是关的（display={bg.get("dis")}）')
    else:
        print(f'5b 星野  canvas {bg["cvw"]}x{bg["cvh"]} 粒子 {bg["n"]} 层 {bg["layers"]} 半径档 {bg["rad"]} '
              f'精灵 {bg["sp"]} 混合={bg["blend"]} 流星={bg["shoot"]} z={bg["z"]}/内容{bg["mz"]} pe={bg["pe"]}')
        if bg['pe'] != 'none':
            fails.append(f'5b 星野：pointer-events={bg["pe"]}，会吃掉卡片点击')
        if int(bg['z']) >= int(bg['mz']):
            fails.append(f'5b 星野：z-index {bg["z"]} 没低于内容 {bg["mz"]}，会盖画')
        if bg['cvw'] < 100 or bg['cvh'] < 100:
            fails.append(f'5b 星野：canvas 尺寸 {bg["cvw"]}x{bg["cvh"]} 没铺上')
        if not 40 <= bg['n'] <= 340:
            fails.append(f'5b 星野：粒子数 {bg["n"]} 不在 40~340（按面积算并封顶这条没生效）')
        # 「星辰」的质感来自三件事，逐件量：多层景深、多种尺寸、软精灵而不是描边圆
        if bg['layers'] != [0, 1, 2]:
            fails.append(f'5b 星野：视差层只有 {bg["layers"]}，不是一远一近三层')
        if bg['rad'] < 6:
            fails.append(f'5b 星野：半径只有 {bg["rad"]} 档，等于所有星一样大')
        if bg['sp'] != 3:
            fails.append(f'5b 星野：精灵 {bg["sp"]} 张（应为白/冰蓝/樱粉三张预渲染图）')
        if bg['depths'] != sorted(bg['depths']) or bg['depths'][0] >= bg['depths'][-1]:
            fails.append(f'5b 星野：层深度没递增 {bg["depths"]}，视差不会分层次')
        if bg['blend'] != 'source-over':
            fails.append(f'5b 星野：浅色底用了 {bg["blend"]} 叠加，会糊成白雾')
        f0 = t.j("return JSON.stringify([BG.frames,BG.clock]);")
        time.sleep(0.5)
        f1 = t.j("return JSON.stringify([BG.frames,BG.clock]);")
        dfr, dcl = f1[0] - f0[0], f1[1] - f0[1]
        # 无头的 rAF 节奏远慢于真机（本轮实测 ~4 帧/0.5s ≈ 8fps），而每帧 dt 上限 0.05s
        # 是防"标签页切回来一次性跳一大段"的保险 —— 两者叠加会让无头里动画时钟走得比墙钟慢，
        # 这**不是缺陷**（真机 60fps 时 dt≈0.016 用不到上限）。所以判据取两侧：
        #   下界：确实在按 dt 累计（不是恒 0）；上界：**不许快过真实时间**（dt 单位写错成 ms
        #   这类事故会立刻爆掉上界，那才是要抓的）。
        print(f'5b 背景  0.5s 推进 {dfr} 帧（无头节奏不代表真机 fps）动画时钟走 {dcl:.2f}s')
        if dfr < 1:
            fails.append('5b 背景：rAF 一帧都没推进')
        # 下界要留余量：无头 3~4 帧 × 每帧 dt 上限 0.05 = 0.15，正好压在边界上会随机抖
        if not 0.1 < dcl <= 0.55:
            fails.append(f'5b 背景：动画时钟 0.5s 走了 {dcl:.2f}s，不在 (0.1, 0.55] —— dt 尺度可疑')
        # 指针视差：把指针甩到左上角，BG.px/py 要缓动跟过去（"活"的主要来源之一）
        t.j("""window.dispatchEvent(new PointerEvent('pointermove',{clientX:2,clientY:2,bubbles:true}));
          return JSON.stringify([BG.px,BG.py]);""")
        time.sleep(1.4)
        par = t.j("return JSON.stringify([BG.px,BG.py]);")
        # 无头 ~8fps，缓动系数 dt*2.4 每帧只走 ~12%，所以门槛按"确实动了"定，不按真机速度定
        print(f'5b 视差  px/py → {par[0]:.2f},{par[1]:.2f}（目标 0,0）')
        if par[0] > 0.42 or par[1] > 0.42:
            fails.append(f'5b 视差：指针移到左上角 1.4s 后 px/py 仍是 {par[0]:.2f},{par[1]:.2f}，没跟上')
        # 单帧绘制成本：无头 rAF 节奏测不出真机成本，只能手动跑 40 帧计时
        cost = t.j("""
          cancelAnimationFrame(BG.raf); BG.raf=0;
          const t0=performance.now();
          for(let i=0;i<40;i++) bgFrame(t0+i*16.7);
          const ms=performance.now()-t0;
          cancelAnimationFrame(BG.raf); BG.raf=0; bgApply();
          return JSON.stringify({ms:+(ms/40).toFixed(2), raf:BG.raf>0});""")
        print(f'5b 成本  单帧绘制 {cost["ms"]}ms（帧预算 16.7ms），计时后循环已恢复={cost["raf"]}')
        if cost['ms'] > 4:
            fails.append(f'5b 成本：单帧 {cost["ms"]}ms，背景吃掉 {cost["ms"]/16.7*100:.0f}% 帧预算，太贵')
        if not cost['raf']:
            fails.append('5b 成本：计时之后 rAF 没恢复，后面的断言会全测到静止画面')
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
    # 夜里背景必须换档：叠加发光 + 开流星 + 密度回升；流星排程要真的能排出来
    dk = t.j("""BG.next=0.001;
      return JSON.stringify({blend:BG.col.blend, shoot:BG.col.shoot, n:BG.p.length, k:BG.col.k});""")
    time.sleep(0.6)
    mk = t.j("return JSON.stringify(!!BG.shoot);")
    print(f'6 昼夜  夜里 blend={dk["blend"]} 流星={dk["shoot"]} 粒子 {bg.get("n")}→{dk["n"]} '
          f'已排出流星={mk}')
    if dk['blend'] != 'lighter':
        fails.append(f'6 昼夜：夜里背景仍是 {dk["blend"]}，没换成叠加发光')
    if not dk['shoot']:
        fails.append('6 昼夜：夜里没开流星排程')
    if dk['n'] <= bg.get('n', 0):
        fails.append(f'6 昼夜：换夜后粒子数 {bg.get("n")}→{dk["n"]} 没回升，密度没跟主题走')
    if not mk:
        fails.append('6 昼夜：把排程归零后 0.6s 仍没有流星，这条是死的')
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
