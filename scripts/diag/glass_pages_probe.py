"""音乐库 / 背景库这两页的液态玻璃验收（无头 Chrome + CDP）。

为什么单独一个脚本：`glass_perf_probe.py` 的整套前提是首页那条 WebGL 水面
（BG.mode==='gl'、划水帧时），这两页都没有。这里要判的是另一组事实：
折射**挂上了没有**、挂在了**该挂的元素**上、以及它有没有真的落到像素上。

判据（每条都会打印，任一不过就 exit 1）：
  1 挂载   header（两页）与 .bar（音乐库）各自带上类，且 --lgf=url(#lgN) 已写
  2 生效   计算后的 backdrop-filter 里确实含 url() —— 只看类名会骗人：
           自定义属性解析失败是**整条声明作废**，类在、滤镜却没挂上（§133 那条老坑）
  3 桶数   同时存在的滤镜个数 ≤ 2（成本主因是"几个不同滤镜"，不是复杂度，§134）
  4 像素   冻住画面、只切 html.lg 一个类，页头那条边墙的取景必须变 —— 不变就是白改
  5 反向   列表里的行/卡一张都不许挂 backdrop-filter（§136：被旋转的盒子里挂遮罩就整块糊）
  6 管道   音乐库进度条是胶囊管（圆角 = 半高、svg 被 clip-path 裁进管里、波仍在画）

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
A = AP.parse_args()
W, H = (int(x) for x in A.win.split(','))
SHOTD = os.path.join(ROOT, '.diag', 'glasspages')

PAGES = {
    'bgm.html': {'mount': [('header', 'hglg', '::before'), ('#bar', 'bglg', '')],
                 'rows': '.row', 'tube': '#tide'},
    'backgrounds.html': {'mount': [('header', 'hglg', '::before')], 'rows': '.card'},
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
  on:!!(window.LiquidGlass&&LiquidGlass.on), buckets:LiquidGlass?LiquidGlass.buckets:-1,
  filters:LiquidGlass?LiquidGlass.filters:-1, mounted:[]};
  %s
  return JSON.stringify(out);})()"""

MOUNT_JS = """const M=%s;   // [[sel,cls,pseudo],...]
  for(const [s,cls,ps] of M){const el=document.querySelector(s);
    if(!el){out.mounted.push({s,ok:false,why:'元素不存在'});continue;}
    const cs=getComputedStyle(el,ps||null);
    const bf=String(cs.backdropFilter||cs.webkitBackdropFilter||'none');
    out.mounted.push({s,ok:el.classList.contains(cls)&&/url\\(/.test(bf),cls:el.classList.contains(cls),
      lgf:String(el.style.getPropertyValue('--lgf')||'').slice(0,14), bf:bf.slice(0,52)});}"""

ROWS_JS = """(()=>{let n=0;document.querySelectorAll('%s').forEach(e=>{
    ['','::before','::after'].forEach(p=>{const v=getComputedStyle(e,p).backdropFilter;
      if(v&&v!=='none')n++;});});
  return JSON.stringify({rows:document.querySelectorAll('%s').length, boxes:n});})()"""

TUBE_JS = """(()=>{const t=document.querySelector('%s'), sv=t.querySelector('svg');
  const cs=getComputedStyle(t), ss=getComputedStyle(sv);
  const h=Math.round(t.getBoundingClientRect().height);
  const bd=document.getElementById('bead');
  return JSON.stringify({h, radius:cs.borderTopLeftRadius, clip:String(ss.clipPath||ss.webkitClipPath).slice(0,26),
    prog:bd?+(+bd.getAttribute('cx')/1000).toFixed(2):-1,
    w1:String((document.getElementById('w1')||{getAttribute:()=>''}).getAttribute('d')||'').length,
    crest:String((document.getElementById('crest')||{getAttribute:()=>''}).getAttribute('d')||'').length});})()"""

# 只切 html.lg 这一个类，取景钉在页头那条 14px 边墙上 —— 两版必须不同（判"落到像素上"）
CROP = """(()=>{const r=document.querySelector('header').getBoundingClientRect();
  return JSON.stringify({x:Math.max(0,r.left+r.width*0.28),y:Math.max(0,r.bottom-26),
    width:420,height:40,scale:3});})()"""


def shot(pg, name, clip=None):
    args = {'format': 'png'}
    if clip:
        args['clip'] = clip
    raw = base64.b64decode(pg.cmd('Page.captureScreenshot', args)['data'])
    open(os.path.join(SHOTD, name + '.png'), 'wb').write(raw)
    return hashlib.md5(raw).hexdigest()[:12]


def check(page, spec, fails):
    url = f'http://127.0.0.1:{A.port}/gallery_v2/{page}'
    prof = os.path.join(ROOT, '.diag', 'glasspages_profile')
    shutil.rmtree(prof, ignore_errors=True)
    os.makedirs(prof, exist_ok=True)
    print(f'\n──── {page} ────')
    pg = Page(9349, prof, url, (W, H))
    try:
        for _ in range(40):
            n = pg.ev("!!window.LiquidGlass")
            if n is True:
                break
            time.sleep(0.5)
        time.sleep(1.6)
        js = STATE % MOUNT_JS % json.dumps(spec['mount'])
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
        if st['buckets'] > 2 or st['filters'] > 2:
            fails.append(f"{page}: 滤镜桶 {st['buckets']}/滤镜 {st['filters']} > 2（成本主因，§134）")
        if not st['on']:
            fails.append(f'{page}: LiquidGlass.on=false —— 这台浏览器不支持 backdrop-filter+url()，下面全作废')

        rw = json.loads(pg.ev(ROWS_JS % (spec['rows'], spec['rows'])))
        print(f"  反向 {rw['rows']} 行里挂着 backdrop-filter 的 {rw['boxes']} 处（必须 0，§136）")
        if rw['boxes']:
            fails.append(f"{page}: {rw['boxes']} 处列表元素挂着 backdrop-filter —— 一转/一动就整块糊（§136）")

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

        clip = json.loads(pg.ev(CROP))
        pg.ev("document.documentElement.classList.remove('lg');'ok'"); time.sleep(0.9)
        off = shot(pg, f'{page[:-5]}_off', clip)
        pg.ev("document.documentElement.classList.add('lg');'ok'"); time.sleep(0.9)
        on = shot(pg, f'{page[:-5]}_on', clip)
        print(f'  像素对照(页头边墙): 关={off} 开={on} '
              f'{"✅ 只切一个类就换了画面" if off != on else "❌ 完全相同 —— 折射没落到画面上，白改"}')
        if off == on:
            fails.append(f'{page}: 取景两版逐字节相同 —— 折射没落到合成结果上')
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
    print('✅ 两页全过：折射挂上了、落到像素上了、列表零滤镜盒、进度条是胶囊管')


main()
