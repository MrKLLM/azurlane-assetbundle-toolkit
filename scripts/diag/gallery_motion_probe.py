# -*- coding: utf-8 -*-
"""画廊动效 / 交互反馈探针：在**会真实出帧**的无头 Chrome 里，逐条证明新增交互动效
真的接上了、并且系统「减少动效」时确实全部退化。

为什么不能用一个普通前台标签页测：标签处于 hidden 时 Chrome 不出帧，
CSS 动画会**冻结在起始关键帧**、`loading=lazy` 的图一张都不加载 —— 于是
「transform 不是 matrix3d」「图没淡入」全是假红灯（2026-09-28 实测踩到）。

  py -3 scripts/diag/gallery_motion_probe.py
  py -3 scripts/diag/gallery_motion_probe.py --page index_q.html --win 1440,900

判据分两类：DOM / 计算样式断言（能红，是判据）+ 截图与像素统计（量出来的，也是判据）。
所有交互都走真实入口：悬停用 **CDP 可信鼠标事件**（合成 mousemove 不会命中 :hover 伪类，
那是假绿灯），点击用 element.click()，键盘用 Input.dispatchKeyEvent。

2026-09-28 背景与卡片悬停重做，判据同步换口径（旧口径已不可能成立）：
  · 旧「1 倾斜 / 1b 倾斜成本」→ 新「1 悬停三件套」，并**反向**断言倾斜已不存在
  · 旧「5b WebGL2 着色器 / 5c 海洋各向异性」→ 新「5b 三团 CSS 色块」+「5c 低频度」
    （绸缎皱褶的指纹就是逐像素梯度高，所以 5c 是那条"丑"的可量化反向判据）
  · 新增「9 键盘焦点环」「10 开关与动作形状可区分」——§6.18 的第 ④⑤ 条
"""
import sys, os, re, json, time, argparse, io, hashlib
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gallery_ui_shots import Page, BASE, preflight

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EV = lambda s: f"(()=>{{{s}}})()"


def band_stats(png_bytes, frac_y0=0.935, frac_y1=0.995, frac_x0=0.04, frac_x1=0.90, blur=12):
    """量「底部那条永远没有卡片盖着的空带」的像素统计：均值、标准差、高频能量。

    为什么必须用截图而不是 readPixels：背景现在是纯 CSS 合成层，没有 GL 上下文可读。

    `hp`（高频能量）= 每个像素与它的高斯模糊版之差，半径 12px。这是**那条"丑"的可量化
    反向判据**：上一版整屏 fbm 噪声着色器出来的"蓝色绸缎/水渍"皱褶，尺度就在几十像素，
    正好落在这个通带里；三团径向渐变色块理论上只有极缓的过渡。
    ⚠️ 实测教训（2026-09-28 标定）：**逐像素梯度分不开两者**（旧 1.05 vs 新 0.75），
    而 `hp` 能（旧 10.55 vs 新 2.77）。所以判据用 hp，不用梯度。
    ⚠️ 夜里 `hp` 有个**本来就存在的地板**（body 那条 linear-gradient 在接近纯黑时
    会量化出 banding：背景关掉反而 hp=3.954 > 开着 3.801）。所以绝对阈值只能当兜底，
    真正判"背景层有没有往里加肌理"要用**同一页开关两态的差值**——见 5c。
    """
    from PIL import Image, ImageFilter
    im = Image.open(io.BytesIO(png_bytes)).convert('L')
    w, h = im.size
    c = im.crop((int(w * frac_x0), int(h * frac_y0), int(w * frac_x1), int(h * frac_y1)))
    g = c.filter(ImageFilter.GaussianBlur(blur))
    px, gx = c.load(), g.load()
    n = 0
    s = ss = hp = 0.0
    gy = gx_ = 0.0
    ng = 0
    W, H = c.size
    for y in range(H):
        for x in range(W):
            v = px[x, y]
            s += v
            ss += v * v
            hp += abs(v - gx[x, y])
            n += 1
            if x + 1 < W:
                gx_ += abs(v - px[x + 1, y]); ng += 1
            if y + 1 < H:
                gy += abs(v - px[x, y + 1]); ng += 1
    mean = s / n
    return {'mean': round(mean, 2), 'sd': round(max(0.0, ss / n - mean * mean) ** .5, 2),
            'hp': round(hp / n, 3), 'grad': round(max(gx_, gy) / ng, 3),
            'box': [int(w * frac_x0), int(h * frac_y0), int(w * frac_x1), int(h * frac_y1)], 'n': n}


def _alpha(css_color):
    """从任意颜色字符串里取 alpha；取不到按不透明算（判据宁可误报不可漏报）。

    ⚠️ 必须同时认三种写法：`rgba(r,g,b,a)`、`rgb(r g b / a)`，以及 Chrome 把
    `color-mix()` 计算值序列化出来的 `color(srgb R G B / A)` / `oklab(... / A)`。
    只认 rgba 的话，`color-mix(... 13%, transparent)` 会被读成 a=1，
    "整块填色回来了"这条就会假红（本轮实测撞到）。
    """
    v = (css_color or '').strip()
    if not v:
        return 1.0
    m = re.search(r'rgba?\([^)]*,\s*([0-9.]+)\s*\)', v)
    if m:
        return float(m.group(1))
    m = re.search(r'/\s*([0-9.]+)\s*\)', v)
    if m:
        return float(m.group(1))
    m = re.search(r'rgb\(([^)]*)\)', v)
    if m and '/' in m.group(1):
        return float(m.group(1).split('/')[-1])
    return 1.0


def _matrix_pair(mat):
    """从 matrix(a,b,c,d,e,f) 里取 (scaleX, scaleY)。"""
    m = re.search(r'matrix\(([^)]*)\)', mat or '')
    if not m:
        return ()
    n = [float(v) for v in m.group(1).split(',')]
    return (n[0], n[3]) if len(n) >= 6 else ()


def n_layers(css_value):
    """数 box-shadow 这类「逗号分隔的多层」值有几层（括号内的逗号不算分隔）。

    为什么不数 'rgb' 子串：Chrome 现在把 `color-mix()` 的计算值序列化成 `oklab(...)`，
    按 'rgb' 数会把"环已经起来了"读成"只有一层阴影"（本轮实测假红灯）。
    """
    if not css_value or css_value == 'none':
        return 0
    depth = 0
    parts = 1
    for ch in css_value:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        elif ch == ',' and depth == 0:
            parts += 1
    return parts


def _m_ty(mat):
    """从 matrix(a,b,c,d,e,f) / matrix3d(...) 里取平移 Y（名称条滑出是否贴底）。"""
    try:
        nums = [float(x) for x in mat.replace('matrix3d(', '').replace('matrix(', '').replace(')', '').split(',')]
    except Exception:
        return 0.0
    if mat.startswith('matrix3d'):
        return nums[13]
    return nums[5] if len(nums) >= 6 else 0.0


def band_hash(png_bytes, frac_y0=0.15, frac_y1=0.95, frac_x0=0.001, frac_x1=0.011):
    """只哈希「`main` 左侧那条 16px 的留白」——背景静止态的可靠指纹。

    ⚠️ 为什么不能哈希整张截图（前两版都死在这条上）：
      ① 缩略图是 `loading=lazy` 的，页面放着放着会继续到货（实测 1008 张里先亮 56 张）；
      ② 卡片上的**镜面高光是持久状态**（跟着指针走过的地方），划过一串卡之后再截，
         那些卡的高光全换位置了 —— 这是设计行为，不是缺陷，但逐像素比一定不同。
    左留白在 `main` 的 padding 里，没有卡片、也没有任何交互状态，只受背景影响。
    """
    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes)).convert('RGB')
    w, h = im.size
    c = im.crop((int(w * frac_x0), int(h * frac_y0), int(w * frac_x1), int(h * frac_y1)))
    return hashlib.sha256(c.tobytes()).hexdigest()[:16]


def wait_images_stable(t, timeout=12.0, quiet=1.2):
    """等懒加载的缩略图停止到货，再拿来做逐像素比较。

    ⚠️ 这是"底部空带被删掉"之后必须补的一步：以前量的那条带子里没有卡片，
    缩略图爱到货不到货都不影响；现在卡片是半透明的、量区里就是卡片，
    而 `loading=lazy` 的图会**在页面放着放着的时候继续亮**（实测 1008 张里
    先亮 56 张）——不等它停，静止两帧的哈希必然不同，那是假红灯。
    返回 (最终到货张数, 是否稳定)。
    """
    def cnt():
        return t.j("return JSON.stringify([document.querySelectorAll('.card .thumb img.ld').length]);")[0]
    last, same_for = cnt(), 0.0
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.4)
        c = cnt()
        if c == last:
            same_for += 0.4
            if same_for >= quiet:
                return c, True
        else:
            same_for, last = 0.0, c
    return last, False


def white_px(before_png, after_png, thresh=244,
             frac_y0=0.935, frac_y1=0.995, frac_x0=0.04, frac_x1=0.90):
    """数「拖动之后新冒出来的近白像素」——泡沫的可证明形式。

    为什么要跟"静止那张"比而不是直接数白点：底色渐变与三团色块里本来就有一片
    接近白的区域（白天空带均值 235），直接数会把底当成泡沫，那条判据就是空的。
    """
    from PIL import Image, ImageChops
    a = Image.open(io.BytesIO(before_png)).convert('RGB')
    b = Image.open(io.BytesIO(after_png)).convert('RGB')
    if a.size != b.size:
        return {'n': -1, 'pct': 0.0}
    w, h = a.size
    box = (int(w * frac_x0), int(h * frac_y0), int(w * frac_x1), int(h * frac_y1))
    a = a.crop(box); b = b.crop(box)
    wa = a.convert('L').point(lambda v: 255 if v >= thresh else 0)
    wb = b.convert('L').point(lambda v: 255 if v >= thresh else 0)
    mask = ImageChops.subtract(wb, wa)          # 只在"划过之后"才变白的像素
    n = mask.histogram()[255]
    return {'n': n, 'pct': n / float(a.size[0] * a.size[1])}


class Tab:
    def __init__(self, pg):
        self.pg = pg

    def j(self, s):
        v = self.pg.ev(EV(s))
        if isinstance(v, str) and v.startswith('EXC'):
            # ⚠️ 只打印 exception.message 会输出 "EXC None"（SyntaxError 的信息在
            #    exceptionDetails.text / description 里，不在 message 里）——今天这条
            #    空错误信息白转了两轮。三个来源都带上，并且把出错的表达式尾巴打出来。
            raise SystemExit('! 探针表达式抛错：' + v[:400] + chr(10)
                             + '   表达式：' + s.strip()[:220])
        return json.loads(v)

    def raw(self, s):
        return self.pg.ev(s)

    def shot_bytes(self):
        import base64
        return base64.b64decode(self.pg.cmd('Page.captureScreenshot', {'format': 'png'})['data'])

    def move(self, x, y):
        """CDP 可信鼠标事件：只有这条路能让 :hover 伪类真的命中。"""
        self.pg.cmd('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y})

    def key(self, k):
        self.pg.cmd('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': k, 'code': k, 'windowsVirtualKeyCode': 0})
        self.pg.cmd('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': k, 'code': k, 'windowsVirtualKeyCode': 0})


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
    # 直接对报错会冤枉人：vendor 的 spine-all.js 本来就引用 THREE（正本同样报），
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
    # err_pass 结尾点开了弹层（那是它取报错的方式）。必须重新载入把弹层关掉再往下测：
    # .mask 是 position:fixed;inset:0，弹层开着的时候**真实**指针根本落不到卡片上，
    # :hover 恒不命中 —— 旧版探针用合成 mousemove 绕过了命中测试，所以从没暴露这一条。
    pg.cmd('Page.navigate', {'url': url})
    time.sleep(5)

    # ── 1. 卡片：悬停发光 + 跟随鼠标倾斜 + 毛玻璃按需挂载 ───────────────────
    # 必须走 CDP 可信鼠标事件：`el.dispatchEvent(new MouseEvent('mousemove'))` 不会让
    # :hover 伪类命中（伪类由浏览器的命中测试决定，不由事件决定），那样测到的永远是假绿。
    def card_state(idx=4):
        return t.j(f"""
          const c=document.querySelectorAll('.card')[{idx}], cs=getComputedStyle(c);
          const im=getComputedStyle(c.querySelector('.thumb img'));
          const d=(v)=>Math.abs(parseFloat(v)||0);
          return JSON.stringify({{hov:c.matches(':hover'), lift:cs.getPropertyValue('--lift').trim(),
            sc:cs.getPropertyValue('--sc').trim(), rx:cs.getPropertyValue('--rx').trim(),
            ry:cs.getPropertyValue('--ry').trim(), rxs:d(cs.getPropertyValue('--rx')),
            rys:d(cs.getPropertyValue('--ry')),
            rxv:(parseFloat(cs.getPropertyValue('--rx'))||0),
            ryv:(parseFloat(cs.getPropertyValue('--ry'))||0),
            border:cs.borderColor, shadow:cs.boxShadow,
            bw:cs.borderTopWidth, mat:cs.transform, imMat:im.transform,
            bar:!!c.querySelector('.nmbar'), glass:c.classList.contains('g'),
            bf:cs.backdropFilter||cs.webkitBackdropFilter||'none',
            rim:(()=>{{const r=getComputedStyle(c,'::before');
              return (r.backdropFilter||r.webkitBackdropFilter||'none')+' | '+r.maskImage.slice(0,26);}})(),
            spec:getComputedStyle(c,'::after').backgroundImage,
            specOp:+getComputedStyle(c,'::after').opacity,
            bodyBg:getComputedStyle(c.querySelector('.body')).backgroundImage.slice(0,70),
            mx:cs.getPropertyValue('--mx').trim(), my:cs.getPropertyValue('--my').trim(),
            fill:cs.backgroundColor,
            nm:((c.querySelector('.body .nm')||{{}}).textContent||'').trim()}});""")

    geo = t.j("""const c=document.querySelectorAll('.card')[4], r=c.getBoundingClientRect();
      return JSON.stringify([r.left,r.top,r.width,r.height]);""")
    bx, by, bw, bh = geo
    base = card_state()
    t.move(bx + bw * .5, by + bh * .5)
    time.sleep(0.7)
    t.move(bx + bw * .52, by + bh * .52)     # 再动一次：某些实现只在"移动"时刷新命中
    time.sleep(0.9)
    hov = card_state()
    # 倾斜：指针到**左上角**与**右下角**，两个分量必须都够大、且符号翻转
    t.move(bx + bw * .03, by + bh * .04); time.sleep(0.55)
    corner_a = card_state()
    t.move(bx + bw * .97, by + bh * .96); time.sleep(0.55)
    corner_b = card_state()
    t.move(4, 4)                              # 指针移开网格
    time.sleep(0.9)
    off = card_state()
    print(f'1 悬停  静止 lift={base["lift"]} sc={base["sc"]} 边框 {base["border"]} 宽 {base["bw"]}')
    print(f'1 悬停  悬停 :hover={hov["hov"]} lift={hov["lift"]} sc={hov["sc"]} '
          f'边框→{hov["border"]} 阴影层数 {n_layers(base["shadow"])}→{n_layers(hov["shadow"])} '
          f'缩略图 {hov["imMat"][:22]}')
    print(f'1 倾斜  左上 rx={corner_a["rx"]} ry={corner_a["ry"]} / 右下 rx={corner_b["rx"]} ry={corner_b["ry"]} '
          f'→ 幅度 |rx|={corner_b["rxs"]:.2f}° |ry|={corner_b["rys"]:.2f}°')
    print(f'1 玻璃  悬停卡 .g={hov["glass"]} backdrop-filter={hov["bf"][:38]!r}')
    if not hov['hov']:
        fails.append('1 悬停：CDP 真实指针移上去后 :hover 仍不命中，后面所有悬停断言都是空的')
    if abs(float(hov['lift'][:-2]) + 5) > 0.8:
        fails.append(f'1 悬停：--lift 没抬到 -5px（{hov["lift"]}）')
    if not (1.01 < float(hov['sc']) < 1.07):
        fails.append(f'1 悬停：--sc 不在 (1.01,1.07)（{hov["sc"]}）')
    if hov['border'] == base['border']:
        fails.append(f'1 悬停：描边颜色没变（{hov["border"]}）')
    # 悬停不再加发光环（用户要求），所以层数**不该变多**；但**绝不许变少** ——
    # 层数变少就是玻璃的厚度被吞了（上一版就出过：悬停把三条 inset 一起丢掉，玻璃塌成纸）。
    print(f'1 悬停  阴影层数 {n_layers(base["shadow"])}→{n_layers(hov["shadow"])}'
          f'（悬停不加环，但也不许丢厚度）')
    if n_layers(hov['shadow']) < n_layers(base['shadow']):
        fails.append(f'1 悬停：悬停把玻璃的厚度丢了（阴影层数 {n_layers(base["shadow"])}'
                     f'→{n_layers(hov["shadow"])}）—— 会塌成一张纸')
    if hov['shadow'] == base['shadow']:
        fails.append('1 悬停：悬停态与静止态的投影一字未变，等于没有任何反馈')
    # ── 玻璃拟态三特征（用户点名"不要毛玻璃，要玻璃拟态"）────────────────────
    # ① 面板必须**几乎全透**：磨砂白卡（上一版 52% 白 + 14px 模糊）就是被判"不像玻璃"的东西
    fa = float(re.search(r'rgba?\([^)]*?,\s*([0-9.]+)\)', hov['fill']).group(1)) if re.search(r'rgba?\(', hov['fill']) else 1.0
    print(f'1 玻璃  面板色 {hov["fill"]} → 不透明度 {fa:.2f}；边墙 {hov["rim"][:52]!r}')
    print(f'1 玻璃  反光 {hov["spec"][:46]!r}；卡上 --mx/--my={hov["mx"]!r}/{hov["my"]!r}（必须都为空）')
    if fa > 0.10:
        fails.append(f'1 玻璃：面板不透明度 {fa:.2f} —— 玻璃拟态要求近乎全透（>0.10 就又成白卡了）')
    # ④ 文字区不许再糊"奶膜"：上一版那里给到 60% 白，是"还是毛玻璃"的主因
    ba = [float(x) for x in re.findall(r'rgba?\([^)]*?,\s*[0-9.]+\s*,\s*([0-9.]+)\)', hov['bodyBg'])]
    print(f'1 玻璃  反光层 {hov["spec"][:60]!r} opacity={hov["specOp"]}')
    print(f'1 玻璃  文字区底色 {hov["bodyBg"][:56]!r}（最大不透明度 {max(ba) if ba else 0:.2f}）')
    if ba and max(ba) > 0.32:
        fails.append(f'1 玻璃：文字区那层底给到 {max(ba):.2f} 白 —— 那就是"奶膜"，卡片会发雾')
    # 反光只许有**常驻斜条**。跟随指针的圆斑已被用户否掉（2026-09-29"不要鼠标发光这个效果"），
    # 所以这条整方向翻面：出现 radial-gradient、或 JS 往卡上写了 --mx/--my，都算回退。
    if 'linear-gradient' not in hov['spec']:
        fails.append(f'1 玻璃：::after 缺常驻斜向反光（{hov["spec"][:60]}）')
    if 'radial-gradient' in hov['spec'] or hov['mx'] or hov['my']:
        has_rad = 'radial-gradient' in hov['spec']
        fails.append(f'1 玻璃：又长出"跟着鼠标发光"了（含 radial={has_rad}，'
                     f'--mx={hov["mx"]!r} --my={hov["my"]!r}）—— 用户明确不要这个效果')
    # ⑤ 悬停**不许发光**（用户点名）：发光 = 带扩散半径的彩色环。
    #    判据取"非 inset 层里不许出现第 4 个长度值（spread）"，中性投影只有 3 个长度。
    spreads = []
    for lay in hov['shadow'].split('),'):
        if 'inset' in lay:
            continue
        nums = re.findall(r'(-?[0-9.]+)px', lay)
        if len(nums) >= 4:
            spreads.append(lay.strip()[:44])
    print(f'1 玻璃  悬停投影里的"扩散环" {len(spreads)} 条 {spreads[:2]}')
    if spreads:
        fails.append(f'1 玻璃：悬停仍在发光 —— 出现了带扩散半径的彩色环 {spreads[0]!r}'
                     f'（用户："划过卡片不用发光"）')
    # ② 边墙：折射必须比面板强（同一层 blur 就没有"厚边"这件事）
    if 'blur' not in hov['rim']:
        fails.append(f'1 玻璃：::before 上没有 backdrop-filter，缺"厚边墙折射"这一特征（{hov["rim"][:44]}）')
    pb = re.search(r'blur\(([0-9.]+)px\)', hov['bf']); rb = re.search(r'blur\(([0-9.]+)px\)', hov['rim'])
    if pb and rb and float(rb.group(1)) <= float(pb.group(1)):
        fails.append(f'1 玻璃：边墙模糊 {rb.group(1)}px 不比面板 {pb.group(1)}px 强，看不出厚度差')
    # （原来这里判"高光坐标必须跟着指针换"，随那个发光效果一起删掉了）
    if 'matrix' not in hov['imMat']:
        fails.append(f'1 悬停：缩略图没跟随放大（{hov["imMat"]}）')
    if off['hov'] or abs(float(off['lift'][:-2] or 0)) > 0.6:
        fails.append(f"1 悬停：指针移开后没退回（:hover={off['hov']} lift={off['lift']}）")
    # 倾斜必须**看得见**：上一版 1.4°/1.8° 被判"约等于零"，但结论不是删掉而是加大。
    # ⚠️ 判据按两个角的**最大值**算，不能要求两个角都过线：指针推到角上时事件与
    #    过渡有半帧延迟，落在 3% 那个点量到的会比理论满偏小 10% 左右（本轮实测 5.24 vs 5.98），
    #    逐角判就会在阈值边缘随机红。满偏够大 = 两个角里至少有一个真的到了满偏。
    if max(corner_a['rxs'], corner_b['rxs']) < 5.5 or max(corner_a['rys'], corner_b['rys']) < 6.5:
        fails.append(f'1 倾斜：两个角的满偏 |rx|/|ry| 最大只有 '
                     f'{max(corner_a["rxs"], corner_b["rxs"]):.2f}°/{max(corner_a["rys"], corner_b["rys"]):.2f}°，'
                     f'肉眼约等于零（判过的失败模式）')
    if corner_a['rxv'] * corner_b['rxv'] >= 0 or corner_a['ryv'] * corner_b['ryv'] >= 0:
        fails.append(f'1 倾斜：换到对角符号没翻（rx {corner_a["rx"]}→{corner_b["rx"]}，'
                     f'ry {corner_a["ry"]}→{corner_b["ry"]}），角度没跟随鼠标')
    if 'matrix3d' not in hov['mat'] and 'matrix3d' not in corner_b['mat']:
        fails.append(f'1 倾斜：transform 里没有 matrix3d —— perspective/rotate 没被消费（{hov["mat"][:34]}）')
    if off['rxs'] > 0.2 or off['rys'] > 0.2:
        fails.append(f'1 倾斜：指针离开后倾角没归零（rx={off["rx"]} ry={off["ry"]}），卡片会歪着留下')
    # 反向判据：那条「点击查看」按用户要求整个去掉，舰名只在下方出现一次
    if hov['bar']:
        fails.append('1 悬停：卡面上又长出了 .nmbar（用户已点名不要那条）')
    if not hov['nm']:
        fails.append('1 悬停：卡面下方的舰名不见了（舰名必须常驻）')
    # 毛玻璃：进视口的卡必须有 backdrop-filter，**没进视口的卡必须没有** —— 这条是成本护栏
    far = t.j("""
      const cs=[...document.querySelectorAll('.card')];
      const vh=innerHeight;
      const outOf=cs.filter(c=>{const r=c.getBoundingClientRect();
        return r.top>vh+200;}).slice(0,40);
      return JSON.stringify({n:outOf.length, g:outOf.filter(c=>c.classList.contains('g')).length,
        inView:cs.filter(c=>c.classList.contains('g')).length,
        total:cs.length});""")
    print(f'1 玻璃  视口内挂了模糊的卡 {far["inView"]} / 共 {far["total"]} 张；'
          f'视口外取样 {far["n"]} 张里挂了 {far["g"]} 张（必须 0）')
    if far['g'] > 0:
        fails.append(f'1 玻璃：{far["g"]}/{far["n"]} 张**视口外**的卡还挂着 backdrop-filter —— '
                     f'IntersectionObserver 没摘，1008 张一起模糊必掉帧')
    if far['inView'] < 5:
        fails.append(f'1 玻璃：视口内只有 {far["inView"]} 张卡挂上了模糊，毛玻璃等于没做')

    # 1b. 倾斜的成本：每次事件都要「读矩形 + 写两个变量」。1008 张卡的网格上这玩意会掉帧，
    #     所以把成本量出来当判据；同时证明它真的在驱动倾斜（否则测的只是空转）。
    perf = t.j("""
      const cs=[...document.querySelectorAll('.card')].slice(0,12);
      const mk=(x,y)=>new MouseEvent('mousemove',{clientX:x,clientY:y,bubbles:true});
      const t0=performance.now();
      for(let i=0;i<120;i++){ const c=cs[i%cs.length], r=c.getBoundingClientRect();
        c.dispatchEvent(mk(r.left+r.width*(0.2+(i%5)/10), r.top+r.height*(0.15+(i%7)/10)));
        getComputedStyle(c).transform; }
      const ms=performance.now()-t0;
      const nz=cs.filter(c=>Math.abs(parseFloat(c.style.getPropertyValue('--ry'))||0)>0.8).length;
      const ry=parseFloat(cs[cs.length-1].style.getPropertyValue('--ry'))||0;
      return JSON.stringify({ms:+ms.toFixed(1), nz, ry:+ry.toFixed(2)});""")
    per = perf['ms'] / 120
    print(f'1b 成本 120 次 mousemove {perf["ms"]}ms（{per:.2f}ms/次，60fps 预算 16.7ms）'
          f'；带倾角的卡 {perf["nz"]}/12（设计上只允许 1 张）末卡 ry={perf["ry"]}')
    # 设计上只允许**一张**卡带倾角（换卡时上一张被归零），所以 nz 期望恒等于 1；
    # 幅度阈值按取样点算：这条循环里 dx 最大只有 0.3 ⇒ 满偏 4.8°，取 0.8° 当"确实在驱动"。
    if perf['nz'] != 1 or abs(perf['ry']) < 0.8:
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
    time.sleep(1.2)
    se1 = t.j("""const s=document.getElementById('search'), cs=getComputedStyle(s);
      return JSON.stringify([parseFloat(cs.width), s.matches(':focus'), cs.flexShrink,
        parseFloat(cs.width), 270]);""")
    t.raw("document.getElementById('search').blur()")
    print(f'2c 搜索  宽 {se0[0]} → 聚焦 {se1[0]}（:focus={se1[1]} flex-shrink={se1[2]} 规则值={se1[4]}）')
    if not se1[1]:
        fails.append('2c 搜索：:focus 没命中（焦点模拟没生效），这条测不到变宽')
    if se1[0] - se0[0] < 20:
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
    # 判据一律用 offset*：飞入动画的 scale 会污染 getBoundingClientRect。
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

    # ── 5b. 背景：静止的水面，划过才起浪（2026-09-28 第四版口径）──────────────
    # 这版最硬的一条判据不是"好不好看"，而是**静止时必须逐像素完全相同**。
    # 前三版（气泡+正弦线 / 2D 星野 / 噪声着色器 / 漂移色块）被否的共同原因不是配色，
    # 是"背景自己在动"——只要它不响应操作就只是一张装饰壁纸。所以"没人在划却一直在漂"
    # 这件事本身，就是要判死的缺陷。
    st = {'mean': 0.0, 'sd': 0.0, 'hp': 0.0, 'box': [], 'n': 0}   # 6 昼夜那节会引用，先兜底
    # ⚠️ 先等水面真的静下来再量"静止"：上面 §1 的悬停测试用的是**真实指针**，
    # 它自己就会 wake 水面（本轮实测带着 peak=0.019 / strokes=3 进测量，两帧必然不同）。
    t.move(6, 6)          # 指针停在 header 空处：别让某张卡带着 hover 进对比图（会假报"残留"）
    t.raw("document.getElementById('main').scrollTo(0,0)")
    time.sleep(0.5)
    for _ in range(60):
        time.sleep(0.2)
        if not t.j("return JSON.stringify([BG.raf>0]);")[0]:
            break
    img_n, img_stable = wait_images_stable(t)
    print(f'5b 前置  缩略图到货 {img_n} 张，'
          f'{"已停止到货（可以逐像素比）" if img_stable else "仍在到货 —— 比较不可信"}')
    if not img_stable:
        fails.append(f'5b 前置：等 12s 缩略图还在到货，静止比较不可信（当前 {img_n} 张）')
    time.sleep(0.6)
    bg = t.j("""
      const host=document.getElementById('bgfx');
      const cs=host?getComputedStyle(host):null, m=getComputedStyle(document.getElementById('main'));
      const gl=[...(host?host.querySelectorAll('.glow'):[])];
      const src=(typeof BG_FS!=='undefined'?BG_FS:'');
      return JSON.stringify({has:!!host, dis:cs&&cs.display, pe:cs&&cs.pointerEvents,
        z:cs&&cs.zIndex, mz:m.zIndex, mb:m.marginBottom,
        n:gl.length, canvas:host?host.querySelectorAll('canvas').length:0,
        anim:gl.map(g=>getComputedStyle(g).animationName),
        mode:(typeof BG!=='undefined'?BG.mode:'no BG'), err:(typeof BG!=='undefined'?BG.err:''),
        sw:(typeof BG!=='undefined'?BG.sw:0), sh:(typeof BG!=='undefined'?BG.sh:0),
        peak:(typeof BG!=='undefined'?BG.peak:-1), frames:(typeof BG!=='undefined'?BG.frames:-1),
        raf:(typeof BG!=='undefined'?BG.raf>0:false), strokes:(typeof BG!=='undefined'?BG.strokes:-1),
        noise:/\\b(noise|fbm|curl|hash)\\s*\\(/.test(src),
        foam:BG.P&&BG.P.foam, gain:BG.P&&BG.P.gain, foamT:BG.P&&BG.P.foamT});""")
    rest_a = t.shot_bytes()
    time.sleep(1.3)
    rest_b = t.shot_bytes()
    same = band_hash(rest_a) == band_hash(rest_b)
    st = band_stats(rest_a)
    open(os.path.join(a.out, 'bg_rest.png'), 'wb').write(rest_a)
    if not bg['has']:
        fails.append('5b 背景：#bgfx 不存在')
    else:
        print(f'5b 背景  mode={bg["mode"]} err={bg["err"][:46]!r} 场 {bg["sw"]}×{bg["sh"]} '
              f'色块 {bg["n"]} 团 canvas={bg["canvas"]} z={bg["z"]}/内容{bg["mz"]} pe={bg["pe"]} '
              f'main底部常驻空带={bg["mb"]}（应为 0px：卡片已悬空）')
        if bg['mb'] not in ('0px', ''):
            fails.append(f'5b 背景：main 还留着 {bg["mb"]} 的底部常驻空带 —— '
                         f'用户要求去掉的"底部的 bar"没去掉')
        print(f'5b 静止  隔 1.3s 的两帧 {"逐像素完全相同 ✓" if same else "不同 ✗ —— 背景自己在动"}  '
              f'帧计数={bg["frames"]} 循环在跑={bg["raf"]} 峰值={bg["peak"]:.5f}')
        if bg['pe'] != 'none':
            fails.append(f'5b 背景：pointer-events={bg["pe"]}，会吃掉卡片点击')
        if int(bg['z']) >= int(bg['mz']):
            fails.append(f'5b 背景：z-index {bg["z"]} 没低于内容 {bg["mz"]}，会盖画')
        if bg['mode'] != 'gl':
            fails.append(f'5b 背景：水面没起来（mode={bg["mode"]} err={bg["err"][:120]}）——只剩静态色块底')
        if bg['canvas'] < 1:
            fails.append('5b 背景：#bgfx 里没有水面画布')
        # 反向守卫：那层"蓝色绸缎"肌理是从噪声函数里长出来的，源码里不许再出现它们
        if bg['noise']:
            fails.append('5b 背景：着色器源码里又出现 noise/fbm/curl/hash —— 绸缎皱褶的源头')
        for k, an in enumerate(bg['anim']):
            if an != 'none':
                fails.append(f'5b 背景：第 {k+1} 团色块又自己动起来了（animation-name={an}）')
        if not same:
            fails.append('5b 静止：没人操作的两帧之间画面变了 —— 背景在自动漂（前三版就死在这条）')
        if bg['raf']:
            fails.append('5b 静止：能量为零时 rAF 还在排帧，循环没自己收摊（静止应当是零开销）')

        # ── 5c. 划过必须起浪，而且事后要回到**同一个**静止态 ─────────────────
        yy = win[1] * 0.62
        for i in range(26):
            t.move(win[0] * 0.12 + win[0] * 0.76 * i / 25, yy + (i % 3) * 7)
            time.sleep(0.022)
        # 再补一条**贴着底部空带**划：波从中间传到那条带子要 ~1.4s，
        # 只划中间就等 0.3s 去量空带，量到的是"还没到"，会被读成"浪没落到可见区"。
        yb = win[1] * 0.955
        for i in range(22):
            t.move(win[0] * 0.9 - win[0] * 0.78 * i / 21, yb)
            time.sleep(0.022)
        time.sleep(0.30)
        wake = t.j("""return JSON.stringify({peak:BG.peak,frames:BG.frames,raf:BG.raf>0,strokes:BG.strokes});""")
        wimg = t.shot_bytes()
        open(os.path.join(a.out, 'bg_wake.png'), 'wb').write(wimg)
        ws = band_stats(wimg)
        wp = white_px(rest_a, wimg)
        print(f'5c 起浪  峰值 {bg["peak"]:.5f}→{wake["peak"]:.5f} 帧 {bg["frames"]}→{wake["frames"]} '
              f'划动 {bg["strokes"]}→{wake["strokes"]} 次 循环在跑={wake["raf"]}')
        print(f'5c 起浪  空带均值 {st["mean"]}→{ws["mean"]} 标准差 {st["sd"]}→{ws["sd"]} '
              f'新增近白像素 {wp["n"]}（占 {wp["pct"]:.2%}）')
        if wake['strokes'] <= bg['strokes']:
            fails.append(f'5c 起浪：真实拖动一次，划动计数没增加（{bg["strokes"]}→{wake["strokes"]}）')
        if not wake['peak'] > 0.004:
            fails.append(f'5c 起浪：拖动后水高场峰值只有 {wake["peak"]:.5f}，等于没激起浪')
        if not wake['raf']:
            fails.append('5c 起浪：有能量时循环没在跑')
        if wake['frames'] - bg['frames'] < 5:
            fails.append(f'5c 起浪：只推进了 {wake["frames"]-bg["frames"]} 帧，波动没传播')
        if ws['mean'] == st['mean'] and ws['sd'] == st['sd']:
            fails.append('5c 起浪：空带像素统计一字未变 —— 浪画出来了但没落到看得见的地方')
        if wp['n'] < 200:
            fails.append(f'5c 起浪：浪里只数出 {wp["n"]} 个近白像素，泡沫没出来（浪花=白沫，不是色带）')
        back = False
        pk_last = -1.0
        for _ in range(100):          # 20 秒预算：给"衰减尾端"留余量，别把慢当成不平
            time.sleep(0.2)
            pk_last, running = t.j("return JSON.stringify([BG.peak,BG.raf>0]);")
            if not running:
                back = True
                break
        t.move(6, 6)
        time.sleep(0.5)
        settle = t.shot_bytes()
        same2 = band_hash(settle) == band_hash(rest_a)
        open(os.path.join(a.out, 'bg_settle.png'), 'wb').write(settle)
        print(f'5c 回落  循环自己停了={back}  回到同一个静止态 {"是 ✓" if same2 else "否 —— 留下永久痕迹"}')
        if not back:
            fails.append(f'5c 回落：20 秒后水还没平，最后观测 peak={pk_last:.5f}'
                         f'（收摊阈值 BG_EPS=0.012 —— 阈值贴着衰减尾端定就会这样）')
        if not same2:
            fails.append('5c 回落：浪停之后画面没回到初始静止态 —— 背景被划花了，回不去')

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
      const gl=[...document.querySelectorAll('#bgfx .glow')];
      return JSON.stringify({theme:h.dataset.theme, on:b.classList.contains('on'),
        ls:localStorage.getItem('gallery.theme'),
        anim:document.getAnimations().filter(x=>x.animationName==='vtwipe').length,
        imgs:gl.map(g=>getComputedStyle(g).backgroundImage.slice(0,44)),
        op:gl.map(g=>getComputedStyle(g).opacity)});""")
    print(f'6 昼夜  --cx {th["cx"]} --cy {th["cy"]}（按钮中心 {th["expectX"]:.1f}%）→ theme={th2["theme"]} 色块不透明度 {th2["op"]}')
    if not th['cx'] or abs(float(th['cx'][:-1]) - th['expectX']) > 1:
        fails.append(f'6 昼夜：--cx 没跟随开关位置（{th["cx"]} vs {th["expectX"]:.1f}%）')
    # ⚠️ theme/localStorage 是在 startViewTransition 的回调里写的，点击那一刻还没落，
    #    必须等快照换完再读（本轮在这里读到过"还是 light"的假红灯）。
    if th2['theme'] != 'dark' or th2['ls'] != 'dark':
        fails.append(f"6 昼夜：切换后主题没落到 dark（theme={th2['theme']} ls={th2['ls']}）")
    if not th2['on']:
        fails.append('6 昼夜：夜那颗胶囊没进入选中态')
    # 背景颜色是 color-mix 自 token 的 ⇒ 换主题必须真的换掉三团的 background-image
    if th2['imgs'] == bg.get('imgs'):
        fails.append(f'6 昼夜：换夜后三团色块的 background-image 逐字没变（{th2["imgs"]}）')
    # 夜里再走一遍同一套"静止"判据：深色底上任何残留动画都最容易被看见。
    # 换主题会重取 token ⇒ 水面参数必须跟着换档（foam 色 / 斜率增益 / 起沫阈值）。
    t.move(6, 6)
    time.sleep(0.5)
    for _ in range(60):        # 先等上一节的浪真正平掉，否则"静止"是假的
        time.sleep(0.2)
        if not t.j("return JSON.stringify([BG.raf>0]);")[0]:
            break
    dk_a = t.shot_bytes()
    time.sleep(1.3)
    dk_b = t.shot_bytes()
    dk_same = band_hash(dk_a) == band_hash(dk_b)
    st_dk = band_stats(dk_a)
    dkp = t.j("""return JSON.stringify({mode:BG.mode,gain:BG.P.gain,foamT:BG.P.foamT,
      foam:BG.P.foam,raf:BG.raf>0,peak:BG.peak});""")
    print(f'6 昼夜  夜里空带 均值={st_dk["mean"]} 标准差={st_dk["sd"]}；静止两帧 '
          f'{"相同 ✓" if dk_same else "不同 ✗ —— 夜里背景在自动漂"}；'
          f'水面 gain={dkp["gain"]} foamT={dkp["foamT"]} 峰值={dkp["peak"]:.5f} 循环={dkp["raf"]}')
    pg.shot(os.path.join(a.out, 'theme_dark.png'))
    if st_dk['mean'] > 140:
        fails.append(f'6 昼夜：夜里空带均值 {st_dk["mean"]}，"夜"没出来（应明显暗于白天 {st["mean"]}）')
    if not dk_same:
        fails.append('6 昼夜：夜里没人操作的两帧之间画面变了 —— 背景在自动漂')
    if dkp['raf']:
        fails.append('6 昼夜：夜里静止时 rAF 还在排帧')
    if dkp['foam'] == (bg.get('foam') if bg else None):
        fails.append(f'6 昼夜：换夜后水面泡沫色没换档（还是白天那套 {dkp["foam"]}）')

    t.raw("document.querySelector('#gTheme button[data-t=light]').click()")
    time.sleep(1.2)

    # ── 9. 键盘焦点可见性（§6.18 第 ④ 条：以前键盘导航零可见反馈）──────────
    # ⚠️ 必须**分两次 evaluate**：focus() 之后在同一次求值里读计算样式，量到的是 transition
    #    的**第 0 帧** —— border-color 还是旧值、box-shadow 是 "--sh1, transparent 0 0 0 0"
    #    （过渡时缺的层按透明零长度补齐），只有没参与过渡的自定义属性 --lift 已经跳到位。
    #    本轮就把这个读成了"焦点环没起来"的假红灯，差点去改本来正确的产品代码。
    t.j("""const c=document.querySelectorAll('.card')[8]; c.scrollIntoView({block:'center'});
      c.focus(); return JSON.stringify([c===document.activeElement]);""")
    time.sleep(0.8)          # 等 .18s/.24s 的过渡走完（无头出帧慢，留足余量）
    kb = t.j("""
      const c=document.querySelectorAll('.card')[8], cs=getComputedStyle(c);
      return JSON.stringify({af:c===document.activeElement, fv:c.matches(':focus-visible'),
        out:cs.outlineWidth+' '+cs.outlineStyle, shadow:cs.boxShadow,
        lift:cs.getPropertyValue('--lift').trim(), tab:c.tabIndex, role:c.getAttribute('role'),
        aria:(c.getAttribute('aria-label')||'').slice(0,20)});""")
    print(f'9 焦点  :focus-visible={kb["fv"]} outline={kb["out"]} lift={kb["lift"]} '
          f'tabindex={kb["tab"]} role={kb["role"]} aria={kb["aria"]!r}')
    if kb['tab'] != 0 or kb['role'] != 'button':
        fails.append(f'9 焦点：卡片没进 Tab 序列（tabIndex={kb["tab"]} role={kb["role"]}）')
    if not kb['fv']:
        fails.append('9 焦点：:focus-visible 没命中，键盘导航仍然零可见反馈')
    if n_layers(kb['shadow']) < 2:
        fails.append(f'9 焦点：焦点环没起来（box-shadow={kb["shadow"]}）')
    if abs(float(kb['lift'][:-2] or 0)) < 1:
        fails.append(f'9 焦点：聚焦时卡片没抬起（--lift={kb["lift"]}）')
    # Enter 必须真的能打开弹层（走 mainEl 上的委托监听器，不是每张卡各挂一个）
    t.key('Enter')
    time.sleep(0.9)
    ent = t.j("""return JSON.stringify({on:document.getElementById('mask').classList.contains('on'),
      name:(document.getElementById('mName')||{}).textContent});""")
    print(f'9 回车  mask.on={ent["on"]} 打开的是「{ent["name"]}」')
    if not ent['on']:
        fails.append('9 回车：Enter 没能激活焦点所在的卡片')
    t.raw("document.querySelector('.close').click()")
    time.sleep(0.9)
    # 焦点环不许在鼠标点击后留下（:focus-visible 的语义就是只在键盘时出现）
    clk = t.j("""const c=document.querySelectorAll('.card')[3]; c.click();
      return JSON.stringify({fv:c.matches(':focus-visible')});""")
    time.sleep(0.4)
    t.raw("document.querySelector('.close').click()")
    time.sleep(0.8)
    if clk['fv']:
        fails.append('9 焦点：鼠标点击后 :focus-visible 仍命中，会留下一圈不该有的环')

    # ── 10. 状态开关 vs 瞬时动作：外观必须靠**形状**区分（§6.18 第 ⑤ 条）─────
    tv = t.j("""
      const q=s=>document.querySelector(s);
      const cs=(s,p='::before')=>{const e=q(s); return e?getComputedStyle(e,p):null};
      const o=cs('#gOpt button'), oo=cs('#gOpt button.on'), g=cs('#gTheme button');
      const b=cs('.srcbar button:not(.tg)'), tg=cs('.spine-bar button.tg');
      return JSON.stringify({opt:o&&o.content, optOn:oo&&oo.content, theme:g&&g.content,
        optW:o&&o.width, themeW:g&&g.width});""")
    print(f'10 开关  .opt 开关 LED={tv["opt"]!r} 选中态={tv["optOn"]!r} 宽={tv["optW"]} / '
          f'昼夜分段={tv["theme"]!r} 宽={tv["themeW"]}')
    if tv['opt'] in (None, 'none', 'normal'):
        fails.append(f'10 开关：全局开关没有 LED 指示（::before content={tv["opt"]!r}）')
    if tv['optOn'] in (None, 'none', 'normal'):
        fails.append('10 开关：选中态的 LED 没换成实心')
    if tv['theme'] not in (None, 'none', 'normal') and float((tv['themeW'] or '0px')[:-2]) > 1:
        fails.append(f'10 开关：昼/夜那两个分段按钮也长了 LED（{tv["theme"]} {tv["themeW"]}），语义会糊')

    # ── 11. iOS 式丝滑：不许过冲、不许形变、导航栏也必须是玻璃 ──────────────
    # 用户 2026-09-28 第二次改口：先前那套"Q弹/果冻"（过冲曲线 + 按下压扁）被否——
    # "不要那种点击一下就弹一下的反应，要 iPhone 那种丝滑"。这条判据就是那句话的可执行形式。
    t.move(6, 6); time.sleep(0.5)
    silky = t.j("""
      const cs=(s,p)=>getComputedStyle(document.querySelector(s),p||null);
      const bez=[...document.styleSheets].flatMap(sh=>{try{return [...sh.cssRules].map(r=>r.cssText)}catch(e){return []}}).join('|');
      const all=(bez.match(/cubic-bezier\([^)]*\)/g)||[]);
      const over=all.filter(b=>{const n=b.replace('cubic-bezier(','').replace(')','').split(',').map(Number);
        return n[1]>1.001||n[3]>1.001;});
      const hi=cs('header'), hb=hi.backdropFilter||hi.webkitBackdropFilter||'none';
      const nb=getComputedStyle(document.querySelector('header'),'::before');
      const na=getComputedStyle(document.querySelector('header'),'::after');
      return JSON.stringify({nav_rim:(nb.backdropFilter||nb.webkitBackdropFilter||'none'),
        nav_spec:na.backgroundImage.slice(0,60),
        ease:cs(':root').getPropertyValue('--ease-ios').trim(),
        btnTf:cs('#gOpt button').transitionTimingFunction, over:over.slice(0,5), nOver:over.length,
        hdr:{bf:hb, bg:hi.backgroundColor, sh:hi.boxShadow.slice(0,70)},
        cardTf:cs('.card').transitionTimingFunction});""")
    m = re.findall(r'[-0-9.]+', silky['ease'])
    overs = [float(v) for k_, v in enumerate(m) if k_ % 2 == 1] if m else []
    print(f'11 丝滑  曲线 {silky["ease"]!r}（按钮实际用 {silky["btnTf"]}）')
    print(f'11 丝滑  全表里 y>1 的过冲曲线 {silky["nOver"]} 条 {silky["over"]}')
    print(f'11 导航栏 backdrop-filter={silky["hdr"]["bf"][:26]!r} 底色={silky["hdr"]["bg"]} '
          f'发光边={silky["hdr"]["sh"][:52]!r}')
    if not silky['ease']:
        fails.append('11 丝滑：没有 --ease-ios 这条曲线')
    elif len(overs) >= 4 and (overs[1] > 1.001 or overs[3] > 1.001):
        fails.append(f'11 丝滑：--ease-ios({silky["ease"]}) 自己带过冲，不是丝滑曲线')
    if silky['nOver']:
        fails.append(f'11 丝滑：样式表里又出现 {silky["nOver"]} 条带回弹的 cubic-bezier '
                     f'{silky["over"][:2]} —— 用户明确否掉了"弹一下"')
    # 按下/悬停必须**看不出形变**：悬停不许放大，按下只许轻压
    g = t.j("""const b=document.querySelector('#gOpt button[data-k=voice]'), r=b.getBoundingClientRect();
      return JSON.stringify([r.left+r.width/2, r.top+r.height/2]);""")
    def sc_of():
        return t.j("""const b=document.querySelector('#gOpt button[data-k=voice]');
          const m=getComputedStyle(b).transform;
          const n=(m.match(/matrix\(([^)]*)\)/)||[])[1];
          return JSON.stringify({m:m, a:n?parseFloat(n.split(',')[0]):1,
            d:n?parseFloat(n.split(',')[3]):1, act:b.matches(':active'), hov:b.matches(':hover')});""")
    t.move(g[0], g[1]); time.sleep(0.6)
    hov_b = sc_of()
    pg.cmd('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': g[0], 'y': g[1],
                                        'button': 'left', 'buttons': 1, 'clickCount': 1})
    # ⚠️ 不能睡固定时长就读：这条 .22s 的过渡在无头里要等**出帧**才走完，而挂了毛玻璃的
    #    网格上帧率只有十几 fps —— 固定 0.3s 会量到"还在起点"，读成"按下没压感"（假红灯）。
    #    一律轮询到落位（最长 2.5s），量的是"最终有没有压下去"，不是"这一瞬间压下去没有"。
    prs_b = sc_of()
    for _ in range(25):
        if prs_b['d'] < 0.995:
            break
        time.sleep(0.1)
        prs_b = sc_of()
    pg.cmd('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': g[0], 'y': g[1],
                                        'button': 'left', 'buttons': 0, 'clickCount': 1})
    t.move(6, 6); time.sleep(0.5)
    print(f'11 按压  悬停 {hov_b["m"][:30]}(act={hov_b["act"]}) → '
          f'按下 {prs_b["m"][:30]}（纵向比例 {prs_b["d"]:.3f} act={prs_b["act"]} hov={prs_b["hov"]}）')
    if max(hov_b['a'], hov_b['d']) > 1.02:
        fails.append(f'11 按压：悬停时按钮被放大到 {max(hov_b["a"], hov_b["d"]):.3f} —— 丝滑语言里不放大')
    if not (0.9 < prs_b['d'] < 1.0):
        fails.append(f'11 按压：按下时纵向比例 {prs_b["d"]:.3f} 不在 (0.9,1.0) —— '
                     f'要么没压感，要么又做成了"压扁形变"')
    if len(m) >= 4 and len(_matrix_pair(prs_b['m'])) >= 2 and abs(_matrix_pair(prs_b['m'])[0] - _matrix_pair(prs_b['m'])[1]) > 0.02:
        fails.append(f'11 按压：按下时横纵比例不等（{_matrix_pair(prs_b["m"])}）—— 那是"压扁"，不是 iOS 的等比轻压')
    # 导航栏玻璃
    # ⚠️ 2026-09-29 用户点名的第二条："尤其是导航栏，一眼看就是毛玻璃"。
    #    磨砂玻璃的配方特征就两条：**底色白 + 模糊大**（越大越像磨砂）。真玻璃反过来。
    #    所以这条判据从"模糊要够大"整条翻面：模糊 > 10px、底色不透明度 > .30 直接红。
    hb = silky['hdr']['bf']
    print(f'11 导航栏 backdrop={hb[:44]!r} 底色={silky["hdr"]["bg"]} '
          f'下沿边墙={silky["nav_rim"][:30]!r}')
    if 'blur' not in hb:
        fails.append(f'11 导航栏：没有 backdrop-filter，那是块不透明的板（{hb[:30]}）')
    else:
        bv = re.search(r'blur\(([0-9.]+)px\)', hb)
        if bv and float(bv.group(1)) > 10:
            fails.append(f'11 导航栏：背后模糊 {bv.group(1)}px —— 模糊越大越像磨砂，'
                         f'真玻璃只要够看出轮廓的 3~8px')
    ha = [float(x) for x in re.findall(r'rgba\([^)]*?,\s*[0-9.]+\s*,\s*([0-9.]+)\)', silky['hdr']['bg'])]
    if ha and max(ha) > 0.30:
        fails.append(f'11 导航栏：底色不透明度 {max(ha):.2f} —— 奶白配方，'
                     f'就是"一眼看是毛玻璃"的那个来源')
    if 'inset' not in silky['hdr']['sh']:
        fails.append(f'11 导航栏：没有那条亮截面（box-shadow={silky["hdr"]["sh"][:50]}）')
    if 'blur' not in silky['nav_rim']:
        fails.append('11 导航栏：下沿缺那条更厚的"边墙"（::before 的 backdrop-filter）')
    if 'linear-gradient' not in silky['nav_spec']:
        fails.append(f'11 导航栏：缺斜穿整条栏的反光（::after={silky["nav_spec"][:40]}）')

    # ── 12. 材质态：选中不靠整块填色，控件只有一个强调色，悬停不动位置 ──────────
    # 用户 2026-09-29："玻璃感还是不够高级，包括按钮的配色和交互"。
    # 三条改口落成三条判据：① 选中 = 更亮的玻璃 + 细彩边 + 彩字，不许实心块；
    # ② 控件上只允许一个强调色（pop 从此只出现在标签/角标这类内容上）；
    # ③ 悬停只改亮度，**不许位移**。
    mat = t.j("""
      const q=s=>document.querySelector(s);
      const cs=e=>getComputedStyle(e);
      const on=cs(q('#gOpt button.on')||q('#gOpt button'));
      const seg=cs(q('#fCat button.on'));
      const css=[...document.styleSheets].flatMap(sh=>{try{return [...sh.cssRules].map(r=>r.cssText)}catch(e){return []}}).join('|');
      const rim=cs(document.documentElement).getPropertyValue('--rim-hi');
      const al=(v)=>{const m=/rgba?\\([^)]*?,\\s*([0-9.]+)\\s*\\)/.exec(v); return m?parseFloat(m[1]):1;};
      return JSON.stringify({
        onBgImg:on.backgroundImage, onBgCol:on.backgroundColor, onColor:on.color,
        segColor:seg.color, segBgImg:seg.backgroundImage,
        popOnCtl:(css.match(/[^}]*\\.on[^}]*grad-pop/g)||[]).length,
        rim:rim, rimA:al(rim),
        spec2:(getComputedStyle(q('.card'),'::after').backgroundImage.match(/rgba\\(255, 255, 255, ([0-9.]+)\\)/g)||[]).slice(0,2)});""")
    print(f'12 材质  选中项 background-image={mat["onBgImg"][:26]!r} 底色a={_alpha(mat["onBgCol"]):.2f} '
          f'文字色={mat["onColor"]}')
    print(f'12 材质  亮边 --rim-hi={mat["rim"].strip()!r}（a={mat["rimA"]:.2f}）；'
          f'控件上残留的粉色实心渐变 {mat["popOnCtl"]} 处')
    if 'gradient' in mat['onBgImg']:
        fails.append(f'12 材质：选中项还是实心渐变填充（{mat["onBgImg"][:40]}）—— 那正是"不够高级"的来源')
    if _alpha(mat['onBgCol']) > 0.30:
        fails.append(f'12 材质：选中项底色不透明度 {_alpha(mat["onBgCol"]):.2f}，整块填色又回来了')
    if mat['popOnCtl']:
        fails.append(f'12 材质：控件上还有 {mat["popOnCtl"]} 处用粉色渐变当选中态 —— 强调色不止一个')
    # 白字压浅底：选中胶囊改成浅色材质后，原来写死的 #fff 会直接看不见（本轮真犯过）
    for nm, col in (('全局开关', mat['onColor']), ('类别胶囊', mat['segColor'])):
        v = re.findall(r'[0-9.]+', col or '')
        if len(v) >= 3 and min(float(v[0]), float(v[1]), float(v[2])) > 200:
            fails.append(f'12 材质：{nm}的选中文字还是近白色（{col}）—— 选中底已经压浅，白字会看不见')
    if mat['rimA'] > 0.25:
        fails.append(f'12 材质：玻璃亮边 a={mat["rimA"]:.2f} > 0.25 —— 太亮的白边读成塑料贴皮')
    # 悬停不许位移（只改亮度）
    # 用「显示台词」那颗：§11 点的是「点击出声」，复用同一颗会把上一步的状态带进来
    hv2 = t.j("""const b=document.querySelector('#gOpt button[data-k=lines]');
      const r=b.getBoundingClientRect(); return JSON.stringify([r.x+r.width/2,r.y+r.height/2]);""")
    # ⚠️ 命中测试不一定每轮都刷新（连发两次也偶发读不到 :hover），所以**边小幅挪边轮询**，
    #    直到 :hover 真命中为止。固定 sleep 会随机把"没测到"读成"产品没做亮度反馈"。
    for k in range(12):
        t.move(hv2[0] - 3 + k * 0.6, hv2[1] - 2 + k * 0.4)
        time.sleep(0.14)
        if t.j("const b=document.querySelector('#gOpt button[data-k=lines]');"
               "return JSON.stringify([b.matches(':hover')]);")[0]:
            break
    # 命中之后再轮询 filter 本身：无头挂了毛玻璃只有几帧每秒，:hover 刚成立的那一帧
    # 过渡还没起步，读到的就是恒等的 brightness(1)。判"最终亮起来了没有"，
    # 不判"这一瞬间亮没亮"——和 §11 按压、§5c 回落同一个教训。
    for _ in range(14):
        time.sleep(0.15)
        hv3 = t.j("""const b=document.querySelector('#gOpt button[data-k=lines]');
          const cs=getComputedStyle(b); return JSON.stringify({tf:cs.transform, f:cs.filter,
            hov:b.matches(':hover')});""")
        _bv = re.search(r'brightness\(\s*([0-9.]+)\s*\)', hv3['f'])
        if _bv and float(_bv.group(1)) > 1.02:
            break
    t.move(6, 6); time.sleep(0.4)
    print(f'12 材质  悬停 :hover={hv3["hov"]} transform={hv3["tf"][:26]!r} '
          f'filter={hv3["f"][:22]!r}（只许改亮度）')
    if hv3['tf'] not in ('none', 'matrix(1, 0, 0, 1, 0, 0)'):
        fails.append(f'12 材质：悬停时按钮被移动/缩放了（{hv3["tf"][:30]}）—— 用户要"只改亮度，不动位置"')
    # 只判"含 brightness"是**空判据**：brightness(1) 也算过。必须判它真的亮起来了。
    bv = re.search(r'brightness\(\s*([0-9.]+)\s*\)', hv3['f'])
    if not bv or not (1.02 <= float(bv.group(1)) <= 1.15):
        fails.append(f'12 材质：悬停的亮度反馈不在 (1.02,1.15)（filter={hv3["f"][:26]}）'
                     f'—— 不动位置就得靠亮度给反馈，brightness(1) 等于没反馈')


    # ── 13. 展开的下拉必须盖住 header 的其它内容（"混在一起了"的回归判据）──────────
    # 根因记牢：给 header 的直接子元素设 z-index，会让每个子元素各自生成层叠上下文，
    # 下拉面板那个 z-index:40 被关在自己那个 .ctl 里出不来，于是 DOM 里排在后面的
    # 提示文字就压在展开的面板之上（用户截图看到的"混在一起"）。
    dd_js = """
      const btn=document.querySelector('.dd-btn'); btn.click();
      const p=btn.closest('.dd').querySelector('.dd-panel');
      const r=p.getBoundingClientRect();
      /* 取面板里**低于 header 底边**的那一点：那里正压着第二行的提示文字，最容易露馅 */
      const hy=document.querySelector('header').getBoundingClientRect().bottom;
      const px=r.left+r.width/2, py=Math.min(r.bottom-4, hy+8);
      const hit=document.elementFromPoint(px,py);
      return JSON.stringify({open:btn.closest('.dd').classList.contains('open'),
        panel:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)],
        hy:Math.round(hy), pt:[Math.round(px),Math.round(py)],
        hit:hit?(hit.tagName+'.'+(typeof hit.className==='string'?hit.className.slice(0,24):'')):'null',
        inside:!!(hit&&hit.closest&&hit.closest('.dd-panel'))});"""
    dd = t.j(dd_js)
    print(f'13 下拉  面板 {dd["panel"]} header底 {dd["hy"]} 测点 {dd["pt"]} '
          f'命中 {dd["hit"]!r} 在面板内={dd["inside"]}')
    if not dd['open']:
        fails.append('13 下拉：点 .dd-btn 没展开面板，这条断言是空的')
    elif not dd['inside']:
        fails.append(f'13 下拉：面板下缘被别的元素盖住了，命中 {dd["hit"]!r} '
                     f'—— 就是用户说的"混在一起了"（层叠上下文被 z-index 切碎）')
    t.raw("document.querySelector('.dd-btn').click()")
    time.sleep(0.4)

    # ── 7. 反向证据：要求减少动效时全部退化 ──────────────────────────────
    pg.cmd('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
    time.sleep(0.5)
    # 减动效下必须**连水面都不初始化**，而且真拖动也不许起浪（只判 raf==0 会被
    # "恰好此刻没能量"骗过去，必须主动划一次当反向证据）。
    fr_pre = t.j("return JSON.stringify([BG.frames]);")[0]
    yy2 = win[1] * 0.5
    for i in range(18):
        t.move(win[0] * 0.2 + win[0] * 0.6 * i / 17, yy2)
        time.sleep(0.02)
    time.sleep(0.6)
    rm = t.j("""
      const c=document.querySelectorAll('.card')[6]; c.scrollIntoView({block:'center'}); c.click();
      const m=document.querySelector('.modal'), im=document.querySelector('.card .thumb img');
      const host=document.getElementById('bgfx');
      return JSON.stringify({fly:m.className, RM:matchMedia('(prefers-reduced-motion: reduce)').matches,
        op:im?getComputedStyle(im).opacity:'no-img',
        cv:host?host.querySelectorAll('canvas').length:-1, raf:BG.raf>0,
        frames:BG.frames, strokes:BG.strokes, peak:BG.peak, mode:BG.mode,
        tilt:document.querySelectorAll('.card')[6].style.cssText});""")
    print(f'7 减动效  class={rm["fly"]!r} RM={rm["RM"]} 图 opacity={rm["op"]} '
          f'水面 canvas={rm["cv"]} raf={rm["raf"]} 划动后 strokes={rm["strokes"]} peak={rm["peak"]:.5f} '
          f'卡内联样式={rm["tilt"]!r}')
    if not rm['RM']:
        fails.append('7 减动效：媒体模拟没生效，这条断言是空的')
    if 'fly' in rm['fly']:
        fails.append('7 减动效：仍播放飞入动画')
    if rm['op'] != '1':
        fails.append(f'7 减动效：缩略图仍依赖淡入（opacity={rm["op"]}），关掉动画后可能永久不可见')
    # 运行中切到"减少动效"时画布已经建好了，不该要求它消失——要判的是**它不再推进**。
    # （只有冷启动就带 reduce 才会走"根本不建画布"那条分支。）
    if rm['raf']:
        fails.append('7 减动效：水面循环还在排帧')
    if rm['frames'] != fr_pre:
        fails.append(f'7 减动效：真划了 18 下，水面帧数仍从 {fr_pre} 推进到 {rm["frames"]}')
    # 减动效下 JS 不许再写倾角（tilt 委托里第一件事就是 tiltReset + return）
    if '--r' in rm['tilt']:
        fails.append(f'7 减动效：减动效下 JS 仍在往卡片写倾角变量（{rm["tilt"]}）')
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
    print('通过：悬停发光+缩略图放大 / 跟随鼠标倾斜(满偏够大且对角翻符号、离手归零) / '
          '毛玻璃只挂在视口内的卡上 / 舰名不重复 / 淡入 / 类别胶囊 / 搜索 / 飞入 / 滑块 / 缩回 / '
          '水面静止可复现 / 划过起浪有白沫 / 浪停回到同一静止态 / 昼夜 / '
          '键盘焦点环 / 开关与动作区分 / iOS 式丝滑(无过冲·无压扁·只轻压) / 导航栏玻璃 / '
          '减少动效退化 全部落到位')


def _m_ty(mat):
    """从 matrix(a,b,c,d,e,f) / matrix3d(...) 里取平移 Y（名称条滑出是否贴底）。"""
    try:
        nums = [float(x) for x in mat.replace('matrix3d(', '').replace('matrix(', '').replace(')', '').split(',')]
    except Exception:
        return 0.0
    if mat.startswith('matrix3d'):
        return nums[13]
    return nums[5] if len(nums) >= 6 else 0.0


if __name__ == '__main__':
    main()
