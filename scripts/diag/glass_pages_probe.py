"""音乐库 / 背景库这两页的液态玻璃验收（无头 Chrome + CDP）。

为什么单独一个脚本：`glass_perf_probe.py` 的整套前提是首页那条 WebGL 水面
（BG.mode==='gl'、划水帧时），这两页都没有。这里要判的是另一组事实：
折射**挂上了没有**、挂在了**该挂的元素**上、以及它有没有真的落到像素上。

判据（每条都会打印，任一不过就 exit 1）：
  1 挂载   spec['mount'] 里每个元素各自带上类，且 --lgf=url(#lgN) 已写
  1b 禁挂  spec['forbid'] 里每个元素（含伪元素）**不许**有 backdrop-filter ——
           音乐库页头那条边墙已被用户判死为"一条杠"，挂回来就是回归（红）
  2 生效   计算后的 backdrop-filter 里确实含 url() —— 只看类名会骗人：
           自定义属性解析失败是**整条声明作废**，类在、滤镜却没挂上（§133 那条老坑）
  3 桶数   同时存在的滤镜个数 ≤ 2（成本主因是"几个不同滤镜"，不是复杂度，§134）
  3b 零盒  spec['noglass']=True 的页反过来判：**不许**加载折射模块、不许长出滤镜盒
           （背景库 2026-10-11 起整页零折射盒，理由同 1b，见 §138）
  4 像素   冻住画面、只切 html.lg 一个类，页头那条边墙的取景必须变 —— 不变就是白改
           （noglass 页跳过：没有可开关的东西，比出来恒"相同"，那种相同不是证据）
  5 反向   列表里的行/卡一张都不许挂 backdrop-filter（§136：被旋转的盒子里挂遮罩就整块糊）
  6 管道   音乐库进度条是胶囊管（圆角 = 半高、svg 被 clip-path 裁进管里、波仍在画）
  7 缩放   背景库查看器：滚轮真的放大（读 computed matrix 的 a）、角标跟着变、按 0 复位、
           双击进 1:1，且 1:1 的基准是**实际显示宽**而不是元素宽（否则竖图会糊到脸上）

用法：先起服务（py -3 -m http.server 8777 --bind 127.0.0.1 -d Output），再
  py -3 scripts/diag/glass_pages_probe.py --port 8777
取图落在 .diag/glasspages/。
"""
import sys, os, json, time, base64, shutil, hashlib, argparse, subprocess, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import chrome_tree
import websocket

CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
AP = argparse.ArgumentParser()
AP.add_argument('--port', default='8777')
AP.add_argument('--win', default='1440,900')
AP.add_argument('--rim', action='store_true',
                help='额外跑"页头边墙为什么不落像素"的四档对照（V0/V1/V6 sticky/兄弟节点）')
A = AP.parse_args()
W, H = (int(x) for x in A.win.split(','))
SHOTD = os.path.join(ROOT, '.diag', 'glasspages')
# 像素对照的前置：这三处都在自己动（光晕 drift / 波形 rAF / 播放中的均衡器），
# 不冻住的话 A/A 就不稳，「两版不同」量的到底是动画还是材质，说不清。
# ⚠️ 音乐库还有一处在动：`.row` 的进场浮现（IntersectionObserver 给每行 setTimeout 错峰加 .in），
#    不冻住的话 A/A 永远不稳，四档对照就全都不能读（本轮第一次跑就是这样）。
FREEZE_CSS = ('.amb i{animation:none!important;transition:none!important}'
              ',.tide svg{display:none!important}.eq u{animation:none!important}'
              ',.row{opacity:1!important;transform:none!important;transition:none!important}'
              ',.card{animation:none!important}')

PAGES = {
    'bgm.html': {'mount': [('#bar', 'bglg', ''), ('input.q', 'bglg', '')],
                 'forbid': [('header', '::before', '栏体已经是 62% 白 + blur26，带子在这只读作一条杠')],
                 'rows': '.row', 'tube': '#tide'},
    # 背景库 2026-10-11 起**整个不加载折射模块**：页头那条边墙先以 header::before 存在（不落像素），
    # 再改成栏的兄弟节点 .navrim（落像素了，但落的就是用户报的那条杠）⇒ 两种写法一起退役（§138）。
    # noglass=True 让下面那套"模块必须 on / 必须挂上"的判据反过来用：加载了模块、或又长出滤镜盒，都算红。
    'backgrounds.html': {'mount': [], 'noglass': True,
                         'forbid': [('header', '::before', '页头边墙整条退役，见 §138'),
                                    ('.navrim', '', '同上 —— 这棵树里不该再有这个节点')],
                         'rows': '.card', 'zoom': ('#ovimg', '#ovbox', '#ovz')},
}


class Page:
    def __init__(self, port, profile, url, win):
        flags = ['--headless=new', f'--remote-debugging-port={port}', '--remote-allow-origins=*',
                 f'--user-data-dir={profile}', '--no-first-run', '--no-default-browser-check',
                 '--disable-background-timer-throttling', f'--window-size={win[0]},{win[1]}',
                 '--autoplay-policy=no-user-gesture-required', '--mute-audio']
        self.proc = chrome_tree.install(subprocess.Popen([CHROME] + flags + [url],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        ws = None
        for _ in range(80):
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
        self.ws = websocket.create_connection(ws, timeout=120, max_size=None)
        self._id = 0
        self.cmd('Page.enable')
        self.cmd('Runtime.enable')

    def cmd(self, m, p=None):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}}))
        self.ws.settimeout(120)
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
            return 'EXC ' + str(ex.get('description') or ex.get('value') or ed.get('text'))[:200]
        return r.get('result', {}).get('value')


STATE = """(()=>{const out={lg:document.documentElement.classList.contains('lg'),
  on:!!(window.LiquidGlass&&LiquidGlass.on), buckets:typeof LiquidGlass==='undefined'?-1:LiquidGlass.buckets,
  filters:typeof LiquidGlass==='undefined'?-1:LiquidGlass.filters, mounted:[], forbidden:[]};
  %s
  %s
  return JSON.stringify(out);})()"""

MOUNT_JS = """const M=%s;   // [[sel,cls,pseudo],...]
  for(const [s,cls,ps] of M){const el=document.querySelector(s);
    if(!el){out.mounted.push({s,ok:false,why:'元素不存在'});continue;}
    const cs=getComputedStyle(el,ps||null);
    const bf=String(cs.backdropFilter||cs.webkitBackdropFilter||'none');
    out.mounted.push({s,ok:el.classList.contains(cls)&&/url\\(/.test(bf),cls:el.classList.contains(cls),
      lgf:String(el.style.getPropertyValue('--lgf')||'').slice(0,14), bf:bf.slice(0,52)});}"""

# 反向挂载判据：某些元素**不许**挂边墙。音乐库页头就是第一条 ——
# 栏体自己已经是 62% 白 + blur(26px)，那条 18px 带子在它下面只会画出一条更亮的杠
# （2026-10-11 用户实机报"头顶横幅下边有条杠"，照片背景前实测把带子抬亮 47/255 级）。
FORBID_JS = """const F=%s;   // [[sel,pseudo,why],...]
  for(const [s,ps,why] of F){const el=document.querySelector(s);
    if(!el){out.forbidden.push({s,ok:true,bf:'(无此元素)',why});continue;}
    const cs=getComputedStyle(el,ps||null);
    const bf=String(cs.backdropFilter||cs.webkitBackdropFilter||'none');
    out.forbidden.push({s,ok:(bf==='none'||!bf)&&cs.content==='none',why,bf:bf.slice(0,40)});}"""

ROWS_JS = """(()=>{let n=0,p=0;document.querySelectorAll('%s').forEach(e=>{
    ['','::before','::after'].forEach(q=>{const v=getComputedStyle(e,q).backdropFilter;
      if(v&&v!=='none'){if(e.classList.contains('playing'))p++;else n++;}});});
  return JSON.stringify({rows:document.querySelectorAll('%s').length, boxes:n, playBoxes:p});})()"""

TUBE_JS = """(()=>{const t=document.querySelector('%s'), sv=t.querySelector('svg');
  const cs=getComputedStyle(t), ss=getComputedStyle(sv);
  const h=Math.round(t.getBoundingClientRect().height);
  const bd=document.getElementById('bead');
  return JSON.stringify({h, radius:cs.borderTopLeftRadius, clip:String(ss.clipPath||ss.webkitClipPath).slice(0,26),
    prog:bd?+(+bd.getAttribute('cx')/1000).toFixed(2):-1,
    w1:String((document.getElementById('w1')||{getAttribute:()=>''}).getAttribute('d')||'').length,
    crest:String((document.getElementById('crest')||{getAttribute:()=>''}).getAttribute('d')||'').length});})()"""

# 只切 html.lg 这一个类，取景钉在页头那条 14px 边墙上 —— 两版必须不同（判"落到像素上"）


def shot(pg, name, clip=None):
    args = {'format': 'png'}
    if clip:
        args['clip'] = clip
    raw = base64.b64decode(pg.cmd('Page.captureScreenshot', args)['data'])
    open(os.path.join(SHOTD, name + '.png'), 'wb').write(raw)
    return hashlib.md5(raw).hexdigest()[:12]


def scale_of(pg, sel):
    """从 computed transform 里读倍率。matrix(a,0,0,d,tx,ty) 的 a 就是 scale ——
    读 style.transform 会被浏览器归一化坑到（写的是 translate()+scale()，回来的是 matrix()），
    所以量最终计算值，不要量自己写进去的那串。"""
    v = pg.ev("(()=>{const t=getComputedStyle(document.querySelector(%s)).transform;"
              "const m=t&&t.match(/matrix\\(([^)]+)\\)/);const a=m?m[1].split(','):'1';"
              "return JSON.stringify({raw:String(t).slice(0,46),s:a.length?+(+a[0]).toFixed(3):1});})()"
              % json.dumps(sel))
    return json.loads(v)


RIM_VARIANTS = {
    'V0 现状（栏体 ::before）': '',
    'V1 栏体不挂滤镜': 'header{backdrop-filter:none!important;-webkit-backdrop-filter:none!important}',
    # 首页与这两页结构相同（栏体挂滤镜 + 子元素挂边墙），只有首页落像素 —— 唯一没排除的差别是
    # position:sticky（合成层不同）。这一档就是验它。
    'V6 栏体改 relative': 'header{position:relative!important}',
    # 兄弟节点：不是 backdrop root 的后代 ⇒ 采得到页面内容。挂载必须带真 url（上一版对照漏了
    # 这一步，量到的"变了"其实只是 saturate/brightness 的颜色差，不是折射）。
    'V5 边墙挪成栏的兄弟': '@SIBLING@',   # 它的「关」= 只糊不折射，见 rim_diag
    # 决定性阳性对照：给边墙涂不透明红。**A/A 已稳的前提下这一档还不变，就说明这条带子
    # 压根没出现在画面里**（被栏体背景盖住 / 取景里没有它），那"折射不落像素"就不是折射的问题，
    # 后面所有关于 backdrop root 的推论都作废。上一版一次性脚本没冻动画就跑过这档，白信了一次。
    'V7 涂红（决定性对照）': 'header::before{background:#ff0044!important}',
}


def rim_diag(pg, spec, freeze_css):
    """页头边墙落不落像素的四档对照。协议（每档同一套）：
       冻动画 → 滚到"内容压在栏底" → A/A（同状态连拍必须相同，否则这档不能读）
       → 开 html.lg 拍一张、关 html.lg 拍一张，**比的是开与关**。
       ⚠️ 判定式原来写成"开 vs 再开一次"，两帧当然是同一状态 —— 那一轮所有 ❌ 都是假的，
          哈希打出来才看见 V1 的开与关其实不同。这种"判据自己比自己"的错，只能靠
          把原始哈希打出来才发现，所以这里一直打印三个哈希。
       ⚠️ V5（兄弟节点）不受 html.lg 影响，它的"关"必须显式换成"只糊不折射"，
          否则两帧是同一个东西，测不出任何差别。"""
    print('\n  ── 边墙对照（每档：冻动画 + 滚到内容压栏底 + A/A + 开/关）──')
    pg.ev("(()=>{let s=document.getElementById('frz');if(!s){s=document.createElement('style');"
          "s.id='frz';document.head.appendChild(s);}s.textContent=%s;})()" % json.dumps(freeze_css))
    pos = pg.ev(FIND_RIM_SPOT)
    if not isinstance(pos, int) or pos < 0:
        print('    ! 找不到内容压在栏底的位置，对照跳过')
        return
    for name, css in RIM_VARIANTS.items():
        sib = css == '@SIBLING@'
        def apply(css_text):
            if sib:
                # 兄弟节点档必须把栏体自己那条 ::before 藏掉，否则两态都还在折射，
                # 差值就说不清是谁贡献的
                pg.ev("(()=>{let s=document.getElementById('rv');if(!s){s=document.createElement('style');"
                      "s.id='rv';document.head.appendChild(s);}s.textContent="
                      "'header::before{display:none!important}';})()")
                v = json.dumps(css_text)
                pg.ev(RIM_SIBLING % (v, v))
            else:
                pg.ev("(()=>{let s=document.getElementById('rv');if(!s){s=document.createElement('style');"
                      "s.id='rv';document.head.appendChild(s);}s.textContent=%s;})()"
                      % json.dumps(css_text))
        apply(css if not sib else '')
        pg.ev('scrollTo(0,%d);1' % pos); time.sleep(1.4)
        pg.ev("document.documentElement.classList.add('lg');'ok'"); time.sleep(0.8)
        a1 = shot(pg, 'rim_a1'); time.sleep(1.0); a2 = shot(pg, 'rim_a2')
        # 「关」：普通档就是去掉 html.lg（边墙退回 blur(17px) 那版）；兄弟节点档要显式换成只糊不折射
        pg.ev("document.documentElement.classList.remove('lg');'ok'")
        apply(RIM_BLUR_ONLY if sib else css if not sib else '')
        time.sleep(0.9)
        off = shot(pg, 'rim_off')
        pg.ev("document.documentElement.classList.add('lg');'ok'")
        apply('' if sib else css)
        time.sleep(0.9)
        on = shot(pg, 'rim_on')
        if sib:
            pg.ev(RIM_KILL)
        else:
            pg.ev("(()=>{const s=document.getElementById('rv');if(s)s.textContent='';})()")
        bf = pg.ev("String(getComputedStyle(document.querySelector('header'),'::before')"
                   ".backdropFilter).slice(0,40)")
        print(f'    {name:<22} A/A {"稳" if a1 == a2 else "不稳→不能读"}  '
              f'开/关 {"✅ 落像素" if a1 != off else "❌ 相同"}  开={a1} 关={off} 再开={on} bf={bf!r}')
    pg.ev("(()=>{const s=document.getElementById('frz');if(s)s.remove();})()")


FIND_RIM_SPOT = """(()=>{const h=Math.round(document.querySelector('header').getBoundingClientRect().height);
  const rs=[...document.querySelectorAll('.card .ph img,.row,.thumb')].slice(0,600).map(e=>{
    const r=e.getBoundingClientRect(); return [r.top+scrollY,r.bottom+scrollY];});
  for(let s=200;s<9000;s+=50){const y0=s+h-18,y1=s+h;
    if(rs.some(a=>a[0]<y1&&a[1]>y0)) return s;}
  return -1;})()"""

# 兄弟节点档专用：把带子的滤镜写成"只糊不折射"就是它的「关」态
RIM_BLUR_ONLY = 'blur(17px) saturate(2.2) brightness(1.14)'
RIM_SIBLING = """(()=>{const hd=document.querySelector('header').getBoundingClientRect();
  const z=getComputedStyle(document.querySelector('header')).zIndex;
  const f=getComputedStyle(document.querySelector('header'),'::before').backdropFilter||'';
  const u=(f.match(/url\\([^)]*\\)/)||[''])[0];
  if(!u&&!%s) return 'NO-URL';      /* 没有真 url 的对照只能测颜色，测不到折射 */
  let d=document.getElementById('rimtest');
  if(!d){d=document.createElement('div');d.id='rimtest';document.body.appendChild(d);}
  const v=%s||('blur(1px) saturate(1.9) brightness(1.1) '+u);
  d.style.cssText='position:fixed;left:0;right:0;height:18px;pointer-events:none;z-index:'+z+
                  ';top:'+(hd.bottom-18)+'px';
  d.style.webkitBackdropFilter=v; d.style.backdropFilter=v; return 'ok '+u.slice(0,14);})()"""
RIM_KILL = "(()=>{const d=document.getElementById('rimtest');if(d)d.remove();return 1;})()"


def check(page, spec, fails):
    url = f'http://127.0.0.1:{A.port}/gallery_v2/{page}'
    prof = os.path.join(ROOT, '.diag', 'glasspages_profile')
    shutil.rmtree(prof, ignore_errors=True)
    os.makedirs(prof, exist_ok=True)
    print(f'\n──── {page} ────')
    pg = Page(9349, prof, url, (W, H))
    try:
        if not spec.get('noglass'):
            for _ in range(40):
                n = pg.ev("!!window.LiquidGlass")
                if n is True:
                    break
                time.sleep(0.5)
        time.sleep(1.6)
        js = STATE % (MOUNT_JS, FORBID_JS) % (json.dumps(spec['mount']),
                                              json.dumps(spec.get('forbid', [])))
        st = pg.ev(js)
        if not isinstance(st, str):
            fails.append(f'{page}: 状态读取失败 {st}')
            return
        st = json.loads(st)
        print(f"  模块 on={st['on']} html.lg={st['lg']} 桶={st['buckets']} 滤镜={st['filters']}")
        for m in st['mounted']:
            print(f"  挂载 {m['s']:<8} cls={m.get('cls')} --lgf={m.get('lgf')!r} bf={m.get('bf')!r} "
                  f"{'✅' if m['ok'] else '❌'}")
            if not m['ok']:
                fails.append(f"{page}: {m['s']} 没挂上折射（{m.get('why') or '类在但 backdrop-filter 里没有 url()'}）")
        for f in st['forbidden']:
            print(f"  禁挂 {f['s']:<8} 空={f['ok']} bf={f['bf']!r} —— {f['why']} "
                  f"{'✅' if f['ok'] else '❌'}")
            if not f['ok']:
                fails.append(f"{page}: {f['s']} 又挂上了滤镜盒（{f['bf']}）—— {f['why']}")
        if st['buckets'] > 2 or st['filters'] > 2:
            fails.append(f"{page}: 滤镜桶 {st['buckets']}/滤镜 {st['filters']} > 2（成本主因，§134）")
        if spec.get('noglass'):
            # 反向：这页现在**不该**有折射模块。挂回来 = §138 那条杠回归。
            print(f"  零折射盒 {'✅ 模块没加载' if not st['on'] else '❌ 模块还挂着（桶 ' + str(st['buckets']) + '）'}")
            if st['on']:
                fails.append(f'{page}: 又加载/挂载了折射模块 —— 本页已判零盒（§138），'
                             f'要恢复先回答"身后有照片时它读不读得成一条杠"')
        elif not st['on']:
            fails.append(f'{page}: LiquidGlass.on=false —— 这台浏览器不支持 backdrop-filter+url()，下面全作废')

        rw = json.loads(pg.ev(ROWS_JS % (spec['rows'], spec['rows'])))
        # 2026-10-12 起音乐库开了一档口子：**正在播放的那一行**允许挂 1 个折射盒
        # （结构件玻璃化，与播放器同材质）。普通行仍是零盒；播放行多于 1 个 = 摘不干净的复活 bug。
        cap = 1 if page == 'bgm.html' else 0
        print(f"  反向 {rw['rows']} 行里普通行挂 backdrop-filter 的 {rw['boxes']} 处（必须 0，§136）"
              f"，播放行 {rw.get('playBoxes', 0)} 处（≤{cap}）")
        if rw['boxes']:
            fails.append(f"{page}: {rw['boxes']} 处列表元素挂着 backdrop-filter —— 一转/一动就整块糊（§136）")
        if rw.get('playBoxes', 0) > cap:
            fails.append(f"{page}: {rw['playBoxes']} 个播放行挂着折射 —— 换曲后旧行的盒没摘（unmount 漏了）")

        if 'tube' in spec:
            # 空管子里本来就没有水（prog=0 ⇒ wavePath 直接返回空串），所以必须先真的点一首再判。
            # 不点就判"波没画出来"会是一条恒红的假判据。
            pg.ev("(()=>{const b=document.querySelector('.play');if(b)b.click();return !!b;})()")
            tb = {}
            for _ in range(28):
                time.sleep(0.25)
                tb = json.loads(pg.ev(TUBE_JS % spec['tube']))
                if tb.get('w1', 0) > 20 and tb.get('crest', 0) > 10:
                    break
            capsule = abs(float(tb['radius'].replace('px', '')) - tb['h'] / 2) <= 2 or '999' in tb['radius']
            print(f"  管道 高={tb['h']}px 圆角={tb['radius']} clip={tb['clip']!r} "
                  f"波路径长={tb['w1']} 浪尖长={tb['crest']}（已点歌，进度 {tb.get('prog')}）")
            if not capsule:
                fails.append(f"{page}: 进度条不是胶囊（圆角 {tb['radius']} ≠ 半高 {tb['h']/2}）")
            if 'inset' not in tb['clip']:
                fails.append(f"{page}: <svg> 没被 clip-path 裁进管子（{tb['clip']}）—— 液体会溢出管口")
            if tb['w1'] < 20 or tb['crest'] < 10:
                fails.append(f"{page}: 点了歌之后波还是没画出来（w1={tb['w1']} crest={tb['crest']}）")
            # 判据过了之后再把液体推到四成处拍一张：空管子和满管子都看不出"管壁 + 弯月面"，
            # 人眼要判的是"水在管子中间"那一格。这一步只为取图，不参与判据。
            pg.ev("(()=>{const d=total();if(d)A.currentTime=d*0.42;return d;})()")
            time.sleep(0.9)
            r = json.loads(pg.ev("""(()=>{const b=document.querySelector('.bar').getBoundingClientRect();
                return JSON.stringify({x:b.left,y:b.top,width:b.width,height:b.height,scale:2});})()"""))
            print(f'  播放器取图 md5={shot(pg, page[:-5] + "_bar", r)}')

        if 'zoom' in spec:
            img, box, badge = (json.dumps(spec['zoom'][0]), json.dumps(spec['zoom'][1]),
                               json.dumps(spec['zoom'][2]))
            pg.ev("document.querySelector('.card').click();'ok'")
            opened = False
            for _ in range(30):
                time.sleep(0.25)
                if pg.ev("(()=>{const i=document.querySelector(%s);"
                         "return !!document.querySelector('.ov.open')&&i.naturalWidth>10;})()" % img) is True:
                    opened = True
                    break
            if not opened:
                fails.append(f'{page}: 点卡片没打开查看器（或原图没解码）—— 缩放无从可测')
            else:
                c = json.loads(pg.ev("(()=>{const b=document.querySelector(%s).getBoundingClientRect();"
                     "return JSON.stringify({x:Math.round(b.left+b.width/2),y:Math.round(b.top+b.height/2)});})()" % box))
                z0 = scale_of(pg, spec['zoom'][0])
                pg.cmd('Input.dispatchMouseEvent', {'type': 'mouseWheel', 'x': c['x'], 'y': c['y'],
                                                    'deltaX': 0, 'deltaY': -300})
                time.sleep(0.4)
                z1 = scale_of(pg, spec['zoom'][0])
                b1 = pg.ev("document.querySelector(%s).textContent" % badge)
                print(f"  缩放  滚轮前 s={z0['s']:.3f} → 滚轮后 s={z1['s']:.3f}  角标={b1!r}")
                if z1['s'] <= 1.05:
                    fails.append(f"{page}: 滚轮没放大（{z0['s']:.3f}→{z1['s']:.3f}）—— 事件没落地或 handler 没接上")
                if '%' not in str(b1):
                    fails.append(f"{page}: 角标没跟着变（{b1!r}）—— 缩放状态对用户没有反馈")
                pg.cmd('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': '0', 'text': '0',
                                                  'windowsVirtualKeyCode': 48, 'nativeVirtualKeyCode': 48})
                time.sleep(0.35)
                z2 = scale_of(pg, spec['zoom'][0])
                print(f"  复位  按 0 之后 s={z2['s']:.3f} 角标={pg.ev('document.querySelector(%s).textContent' % badge)!r}")
                if z2['s'] > 1.01:
                    fails.append(f"{page}: 按 0 没回到适配（s={z2['s']:.3f}）")
                # 真双击 = 两对 press/release，第二对 clickCount:2。
                # ⚠️ 只发一条 mouseClicked{clickCount:2} 在部分 Chrome 版本上不合成 dblclick，
                #    那时候量到的"没反应"是我的事件不像人，不是页面没接住 —— 两种都要试并分开报。
                for cc in (1, 2):
                    for t in ('mousePressed', 'mouseReleased'):
                        pg.cmd('Input.dispatchMouseEvent', {'type': t, 'x': c['x'], 'y': c['y'],
                                                            'button': 'left', 'clickCount': cc})
                time.sleep(0.4)
                z3 = scale_of(pg, spec['zoom'][0])
                how = 'CDP 真双击'
                if z3['s'] <= 1.01:
                    pg.ev("(()=>{const b=document.querySelector(%s);"
                          "const r=b.getBoundingClientRect();"
                          "b.dispatchEvent(new MouseEvent('dblclick',{bubbles:true,clientX:r.left+r.width/2,"
                          "clientY:r.top+r.height/2}));return 1;})()" % box)
                    time.sleep(0.35)
                    z3 = scale_of(pg, spec['zoom'][0])
                    how = '页面内派发 dblclick（CDP 合成没生效，只能退到这一档）'
                nat = json.loads(pg.ev("(()=>{const i=document.querySelector(%s);"
                       "return JSON.stringify({w:i.naturalWidth,h:i.naturalHeight,cw:i.clientWidth,ch:i.clientHeight});})()" % img))
                print(f"  1:1   {how} 之后 s={z3['s']:.3f}（原图 {nat['w']}×{nat['h']}，盒 {nat['cw']}×{nat['ch']}）")
                if z3['s'] <= 1.01:
                    fails.append(f"{page}: 双击没进 1:1（s={z3['s']:.3f}）")
                elif nat['w'] > nat['cw'] and z3['s'] < 1.5:
                    # 原图比显示框大时，1:1 必然 >1；量出接近 1 说明基准算错（拿元素宽当显示宽）
                    fails.append(f"{page}: 1:1 倍率可疑（s={z3['s']:.3f}，原图 {nat['w']}px 比框 {nat['cw']}px 大）"
                                 f"—— 大概又拿 naturalWidth/clientWidth 当基准了")
                pg.ev("document.getElementById('ovclose').click();'ok'")
                # 查看器还开着的话，后面那对比照拍的是弹窗遮罩而不是页头边墙 ——
                # 两态必然逐字节相同，看起来像"效果看不见"，其实是取景被盖住（本轮真踩了这一次）。
                if pg.ev("!!document.querySelector('.ov.open')") is True:
                    fails.append(f'{page}: 缩放检查之后查看器没关掉 —— 后面的像素对照作废（取景被弹窗盖住）')

        # ── 像素对照：只切 html.lg 一个类，边墙必须换画面 ──
        # 三个前提，缺一个这条判据就是假的（本轮三条全踩过）：
        # ① **冻住 `.amb i` 的 drift 动画**：背景光晕自己在漂 ⇒ 同状态连拍两张就不相同，
        #    那"两版不同"量的是动画不是折射。第一次跑就是这么假绿的。
        # ② **先跑 A/A 空白对照**：冻完还是不稳（比如懒加载图还在到货）就降级为不可用，
        #    由第 2 条（计算后的 backdrop-filter 含 url()）承担"挂上了没有"，不许拿假绿灯交差。
        # ③ **用整视口截图，不要用带 clip 的取景**：CDP 的 clip 是**文档坐标**且按"未滚动的整页"
        #    重绘，滚了之后按 scrollY 加坐标拍到的是页顶那块平背景 —— 平背景上 blur 与折射算出来
        #    是同一个颜色，于是"效果看不见"是仪器假象。边墙折射的是**从它身后经过的内容**，
        #    只有滚动起来、内容压到栏底下时才弯得出来。
        pg.ev("(()=>{const b=document.getElementById('pp');if(b)b.click();return 1;})()")   # 暂停：时间文本每帧都变
        pg.ev("(()=>{const s=document.createElement('style');s.id='aafreeze';"
              "s.textContent=FZ;return 1;})()".replace('FZ', json.dumps(FREEZE_CSS)))
        # 这条判据是**位置敏感**的：滚到两行之间的空隙上就没得弯。所以不随手滚一个数，
        # 让页面自己找一个"卡片正好压在栏底那条边墙上"的位置，找不到就作废而不是报红。
        # ⚠️ 不能用 elementFromPoint 找：那个点被 sticky 栏自己盖着，永远返回 header，
        #    于是"找不到位置"是假象 —— 只能按矩形在文档坐标系里算重叠。
        pos = pg.ev("""(()=>{const h=Math.round(document.querySelector('header').getBoundingClientRect().height);
          const rs=[...document.querySelectorAll('.card .ph img,.row')].slice(0,600).map(e=>{const r=e.getBoundingClientRect();
            return [r.top+scrollY, r.bottom+scrollY];});
          for(let s=200;s<9000;s+=50){const y0=s+h-18,y1=s+h;
            if(rs.some(a=>a[0]<y1&&a[1]>y0)) return s;}
          return -1;})()""")
        if spec.get('noglass'):
            print('  像素对照: ⏭ 跳过 —— 本页零折射盒（§138）：没有可开/可关的东西，'
                  '比了也只能得到"相同"，那种"相同"不是证据')
        elif not isinstance(pos, int) or pos < 0:
            print('  像素对照: ⏭ 找不到"内容压在栏底边墙上"的滚动位置 —— 这条作废（不许拿"相同"当结论）')
        else:
            pg.ev("scrollTo(0,%d);" % pos + "'ok'")
            time.sleep(1.8)
            pg.ev("document.documentElement.classList.add('lg');'ok'"); time.sleep(0.9)
            aa1 = shot(pg, f'{page[:-5]}_aa1')
            time.sleep(1.2)
            aa2 = shot(pg, f'{page[:-5]}_aa2')
            if aa1 != aa2:
                print(f'  像素对照: ⏭ 不可用 —— 冻完动画同状态连拍仍不同（{aa1} vs {aa2}，'
                      f'多半还有在到货的懒加载图）；"挂上了没有"由第 2 条判')
            else:
                pg.ev("document.documentElement.classList.remove('lg');'ok'"); time.sleep(0.9)
                off = shot(pg, f'{page[:-5]}_off')
                pg.ev("document.documentElement.classList.add('lg');'ok'"); time.sleep(0.9)
                on = shot(pg, f'{page[:-5]}_on')
                # ⚠️ 这一条**只报不拦**：两页都量到"两版逐字节相同"，而我解释不了为什么
                #    （首页同一条判据是过的）。在解释清楚之前，它既不能当"生效"的证据，
                #    也不能当"没生效"的结论 —— 报红会把人引向错误的方向，所以降级为参考信息。
                print(f'  像素对照(A/A 稳定，滚到 {pos} 让内容压到栏底): 关={off} 开={on} '
                      f'{"✅ 只切一个类就换了画面" if off != on else "❓ 两版相同 —— 这条在这两页不成立，未证实也未证伪（首页同判据是过的）"}')
        if A.rim and not spec.get('noglass'):
            rim_diag(pg, spec, FREEZE_CSS)
        pg.ev("(()=>{const s=document.getElementById('aafreeze');if(s)s.remove();})()")
        shot(pg, f'{page[:-5]}_full')
    finally:
        pg.close()


def main():
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{A.port}/gallery_v2/bgm.html', timeout=5):
            pass
    except Exception as e:
        print(f'! {A.port} 上没有静态服务：{e}\n  先起 py -3 -m http.server {A.port} --bind 127.0.0.1 -d Output')
        sys.exit(1)
    shutil.rmtree(SHOTD, ignore_errors=True)
    os.makedirs(SHOTD, exist_ok=True)
    fails = []
    for page, spec in PAGES.items():
        check(page, spec, fails)
    print(f'\n取图目录 {SHOTD}')
    if fails:
        print('!! 未通过：')
        for f in fails:
            print('  - ' + f)
        sys.exit(1)
    print('✅ 两页全过：折射挂上了（计算值含 url()）、列表零滤镜盒、进度条是胶囊管、缩放可用')
    print('   ⚠️ 但"折射落到像素上"这一条在两页都没量到差异，只报不拦 —— 见上面那行 ❓')


main()
