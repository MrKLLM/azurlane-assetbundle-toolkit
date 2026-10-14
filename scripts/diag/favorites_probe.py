"""收藏 + 网站背景的功能验收（无头 Chrome + CDP，一次浏览器会话里跨四页跑）。

为什么必须真驱动：这两个功能全是"点了没反应也不会报错"那一类——委托监听没挂上、
stopPropagation 漏了、localStorage 键写错，页面看起来都完全正常。

判据（任一不过 exit 1）：
  1 首页点星 → 键进 localStorage，且**卡片没被打开**（委托监听里的 stopPropagation 是唯一防线）
  2 首页「已收藏」档 → 卡片数 == 收藏数（不是"筛出全部"，那是模块没加载时的假通过）
  3 弹窗动作条 → 星标 + 「设为网站背景」；点下去 html.has-sitebg 有、--site-bg 含 url
  4 音乐库点星 → 角标计数跟着涨；开「只看收藏」只剩收藏的那几行
  5 跨页持久 → 换页 / reload 之后收藏与背景都还在（同源 localStorage 是唯一真相）
  6 取消 → 收藏清空后「只看收藏」是空态而不是全量；清除背景后 has-sitebg 掉掉

用法：先起服务（py -3 -m http.server 8777 --bind 127.0.0.1 -d Output），再
  py -3 scripts/diag/favorites_probe.py --port 8777
带 --shots 时用 --shots-dir 指定前缀；脚本会自动追加 PID/时间戳，绝不覆写既有截图。
"""
import sys, os, json, time, base64, argparse, subprocess, urllib.request

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
AP.add_argument('--shots', action='store_true',
                help='跑完判据后再取人眼判图：主页、音乐库与背景库站用背景态，落在 .diag/<shots-dir>/')
AP.add_argument('--shots-dir', default='favshots',
                help='截图输出子目录（.diag 下；用于保留已有判图，默认 favshots）')
A = AP.parse_args()
W, H = (int(x) for x in A.win.split(','))
BASE = f'http://127.0.0.1:{A.port}/gallery_v2'
CDP = 9381
fails = []


class Br:
    def __init__(self):
        # 每次用全新 profile，避免清理旧缓存目录触发批量删除闸，也不碰其它会话的 Chrome 数据。
        prof = os.path.abspath(os.path.join(ROOT, '.diag', f'fav_profile_{os.getpid()}_{time.time_ns()}'))
        os.makedirs(prof, exist_ok=False)
        self.proc = chrome_tree.install(subprocess.Popen(
            [CHROME, '--headless=new', f'--remote-debugging-port={CDP}', '--remote-allow-origins=*',
             f'--user-data-dir={prof}', '--no-first-run', '--window-size=%d,%d' % (W, H),
             BASE + '/index.html'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        ws = None
        for _ in range(80):
            try:
                t = json.load(urllib.request.urlopen(f'http://127.0.0.1:{CDP}/json'))
                m = [x for x in t if 'gallery_v2' in x.get('url', '') and x.get('webSocketDebuggerUrl')]
                if m:
                    ws = m[0]['webSocketDebuggerUrl']; break
            except Exception:
                pass
            time.sleep(0.5)
        if not ws:
            raise SystemExit('! 没连上 CDP')
        self.ws = websocket.create_connection(ws, timeout=90, max_size=None)
        self.n = 0
        self.cmd('Page.enable'); self.cmd('Runtime.enable')

    def cmd(self, m, pr=None):
        self.n += 1; i = self.n
        self.ws.send(json.dumps({'id': i, 'method': m, 'params': pr or {}}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get('id') == i:
                if r.get('error'):
                    return {'__err': r['error']}
                return r.get('result', {})

    def ev(self, e, aw=False):
        pr = {'expression': e, 'returnByValue': True}
        if aw:
            pr['awaitPromise'] = True
        r = self.cmd('Runtime.evaluate', pr)
        if r.get('exceptionDetails'):
            ed = r['exceptionDetails']
            ex = ed.get('exception', {}) or {}
            return 'EXC ' + str(ex.get('description') or ed.get('text'))[:180]
        return (r.get('result') or {}).get('value')

    def go(self, page, settle=2.0):
        self.cmd('Page.navigate', {'url': BASE + '/' + page})
        for _ in range(40):
            time.sleep(0.5)
            if self.ev('document.readyState') == 'complete':
                break
        time.sleep(settle)

    def close(self):
        try:
            self.cmd('Browser.close')
        except Exception:
            chrome_tree.kill_tree(self.proc.pid)


def ck(name, ok, detail=''):
    print(f'  {"✅" if ok else "❌"} {name}' + (f'  {detail}' if detail else ''))
    if not ok:
        fails.append(name + ('：' + detail if detail else ''))


b = Br()

# ── 1 / 2 / 3：首页 ──
b.go('index.html', 3.0)
print('\n---- index.html ----')
ck('模块加载', b.ev('!!(window.Fav&&window.SiteBg)') is True, str(b.ev('typeof Fav')))
n0 = b.ev('document.querySelectorAll(".card").length')
b.ev('document.querySelectorAll(".card .favbtn")[2].click();1')
time.sleep(0.5)
st = b.ev('JSON.stringify({mask:!!document.querySelector("#mask.on"),'
           'fav:JSON.parse(localStorage.getItem("gallery.fav")||"{}"),'
           'on:document.querySelectorAll(".card .favbtn.on").length})')
st = json.loads(st) if isinstance(st, str) else {}
ck('点星不顺手打开卡片（stopPropagation）', not st.get('mask'), 'mask.on=' + str(st.get('mask')))
ck('收藏写进 localStorage', len(st.get('fav', {}).get('skin', [])) == 1,
   'skin=' + str(st.get('fav', {}).get('skin')))
ck('星标原地变实心', st.get('on') == 1, 'on=' + str(st.get('on')))
b.ev('document.getElementById("fHas").value="fav";'
     'document.getElementById("fHas").dispatchEvent(new Event("change",{bubbles:true}));1')
time.sleep(0.8)
nFav = b.ev('document.querySelectorAll(".card").length')
ck('「已收藏」筛出 1 张（不是全量）', nFav == 1, f'收藏后 {nFav} 张 / 原本 {n0} 张')
b.ev('document.querySelector(".card").click();1'); time.sleep(1.4)
acts = b.ev('JSON.stringify({star:!!document.querySelector("#mActs .favbtn"),'
            'bg:!!document.getElementById("mSetBg"),txt:(document.getElementById("mSetBg")||{}).textContent})')
acts = json.loads(acts) if isinstance(acts, str) else {}
ck('弹窗动作条有星标 + 设为背景按钮', acts.get('star') and acts.get('bg'), str(acts))
b.ev('document.getElementById("mSetBg").click();1'); time.sleep(0.7)
sb = b.ev('JSON.stringify({cls:document.documentElement.classList.contains("has-sitebg"),'
          'v:(document.documentElement.style.getPropertyValue("--site-bg")||"").slice(0,26),'
          'fit:document.documentElement.style.getPropertyValue("--site-fit")})')
sb = json.loads(sb) if isinstance(sb, str) else {}
ck('设为网站背景生效', sb.get('cls') is True and 'url(' in str(sb.get('v')), str(sb))
nav = b.ev('JSON.stringify((()=>{const h=getComputedStyle(document.querySelector("header.main-toolbar"));'
          'const s=document.querySelector("#search"),o=document.querySelector("#gOpt"),seg=document.querySelector(".seg");'
          'const bf=e=>{const c=getComputedStyle(e);return c.backdropFilter||c.webkitBackdropFilter||"none"};'
          'return {headerBg:h.backgroundColor,headerFilter:h.backdropFilter||h.webkitBackdropFilter||"none",'
          'search:bf(s),option:bf(o),segment:bf(seg),toolsBg:getComputedStyle(document.querySelector("header.main-toolbar")).backgroundColor}})())')
nav = json.loads(nav) if isinstance(nav, str) else {}
ck('主页空白顶栏与控件容器无整条底色，玻璃只落在实际按钮/搜索框',
   'none' in str(nav.get('headerFilter')) and 'blur(' in str(nav.get('search'))
   and 'blur(' in str(nav.get('option')) and 'blur(' in str(nav.get('segment')),
   str(nav))

# ── 4：音乐库（跨页持久，同一浏览器会话）──
b.go('bgm.html', 2.6)
print('\n---- bgm.html ----')
ck('模块加载', b.ev('!!(window.Fav&&window.SiteBg)') is True)
ck('背景跨页仍在（同一 localStorage）',
   b.ev('document.documentElement.classList.contains("has-sitebg")') is True)
b.ev('document.querySelectorAll(".row .favbtn")[1].click();1'); time.sleep(0.5)
cnt = b.ev('JSON.stringify({n:document.getElementById("favN").textContent,'
           'on:document.querySelectorAll(".row .favbtn.on").length,'
           'stored:JSON.parse(localStorage.getItem("gallery.fav")||"{}").bgm})')
cnt = json.loads(cnt) if isinstance(cnt, str) else {}
ck('音乐收藏计数角标 + 落盘', cnt.get('n') == '1' and len(cnt.get('stored') or []) == 1, str(cnt))
b.ev('document.getElementById("cFav").click();1'); time.sleep(0.7)
rows = b.ev('document.querySelectorAll(".row").length')
ck('「只看收藏」只剩 1 行', rows == 1, f'{rows} 行')
b.go('bgm.html', 2.4)
ck('刷新之后收藏与筛选状态仍在（持久化）',
   b.ev('JSON.parse(localStorage.getItem("gallery.fav")||"{}").bgm.length') == 1)

# ── 5：背景库 ──
b.go('backgrounds.html', 2.6)
print('\n---- backgrounds.html ----')
ck('模块加载', b.ev('!!(window.Fav&&window.SiteBg)') is True)
b.ev('document.querySelectorAll(".card .favbtn")[0].click();1'); time.sleep(0.5)
ck('背景卡点星落盘',
   b.ev('JSON.parse(localStorage.getItem("gallery.fav")||"{}").bg.length') == 1)
b.ev('document.getElementById("cFav").click();1'); time.sleep(0.3)
ui = b.ev(r"""JSON.stringify((()=>{const q=document.querySelector('.q'),c=document.querySelector('#cFav');
  const qs=getComputedStyle(q),cs=getComputedStyle(c),ts=getComputedStyle(document.querySelector('.tools')),
    fg=cs.color,bg=cs.backgroundColor,toolsBg=ts.backgroundColor;
  const rgb=s=>{let m=s.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)/i);
    if(m)return [+m[1],+m[2],+m[3]];m=s.match(/rgba?\(([^)]+)\)/i);
    if(m)return m[1].replace(/\//g,' ').split(/[ ,]+/).filter(Boolean).slice(0,3).map(Number);
    m=s.match(/oklab\(\s*([\d.]+)\s+([-\d.]+)\s+([-\d.]+)/i);if(!m)return null;
    const L=+m[1],a=+m[2],b=+m[3],l=L+.3963377774*a+.2158037573*b,
      m0=L-.1055613458*a-.0638541728*b,n=L-.0894841775*a-1.291485548*b;
    return [4.0767416621*l**3-3.3077115913*m0**3+.2309699292*n**3,
      -1.2684380046*l**3+2.6097574011*m0**3-.3413193965*n**3,
      -.0041960863*l**3-.7034186147*m0**3+1.707614701*n**3].map(x=>Math.max(0,Math.min(1,x<=.0031308?12.92*x:1.055*x**(1/2.4)-.055))*255)};
  const lum=a=>{if(!a)return NaN;const x=a.map(v=>v>1?v/255:v).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);
    return .2126*x[0]+.7152*x[1]+.0722*x[2]};
  const l1=lum(rgb(fg)),l2=lum(rgb(bg)),contrast=Number.isFinite(l1+l2)?(Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05):0;
  const am=bg.match(/\/\s*([\d.]+)\s*\)/)||bg.match(/rgba?\([^,]+,[^,]+,[^,]+,\s*([\d.]+)\)/i);
  return {filter:qs.backdropFilter||qs.webkitBackdropFilter||'none',bg,fg,toolsBg,
    alpha:am?+am[1]:1,contrast,on:c.classList.contains('on')}})())""")
ui = json.loads(ui) if isinstance(ui, str) else {}
ck('站用背景下搜索框烟熏模糊生效', 'blur(' in str(ui.get('filter')), str(ui.get('filter')))
ck('背景库工具行本身无满宽底色', ui.get('toolsBg') == 'rgba(0, 0, 0, 0)', str(ui.get('toolsBg')))
ck('「只看收藏」选中底色不透图且文字对比度达标', ui.get('on') and ui.get('alpha', 0) >= 0.98
   and ui.get('contrast', 0) >= 4.5,
   f"contrast={ui.get('contrast')} alpha={ui.get('alpha')} fg/bg={ui.get('fg')} / {ui.get('bg')}")
b.ev('document.getElementById("cFav").click();1')
b.ev('document.querySelector(".card").click();1'); time.sleep(1.2)
b.ev('document.getElementById("ovbg").click();1'); time.sleep(0.7)
ck('查看器「设为网站背景」生效',
   b.ev('document.documentElement.classList.contains("has-sitebg")') is True)
ck('按钮文案跟着真相走',
   '已设为背景' in str(b.ev('document.getElementById("ovbg").textContent')),
   str(b.ev('document.getElementById("ovbg").textContent')))
b.ev('document.getElementById("ovbg").click();1'); time.sleep(0.6)
ck('再点一次取消背景',
   b.ev('document.documentElement.classList.contains("has-sitebg")') is False)

# ── 6：反向 —— 清空收藏后是空态而不是全量 ──
b.go('bgm.html', 2.4)
print('\n---- 反向：清空与空态 ----')
b.ev('document.getElementById("cFav").click();1'); time.sleep(0.6)
b.ev('document.querySelectorAll(".row .favbtn")[0].click();1'); time.sleep(0.6)
empt = b.ev('JSON.stringify({rows:document.querySelectorAll(".row").length,'
            'none:!!document.querySelector(".empty"),n:document.getElementById("favN").textContent})')
empt = json.loads(empt) if isinstance(empt, str) else {}
ck('取消最后一项后「只看收藏」是空态（不是把全部放出来）',
   empt.get('rows') == 0 and empt.get('none') is True, str(empt))
ck('角标归零', empt.get('n') == '0', 'n=' + str(empt.get('n')))

if A.shots:
    shotname = f'{A.shots_dir}_{os.getpid()}_{time.time_ns()}'
    print(f'\n---- 人眼判图（.diag/{shotname}/）----')
    shotd = os.path.join(ROOT, '.diag', shotname)
    os.makedirs(shotd, exist_ok=False)
    b.go('backgrounds.html', 2.6)
    # 挑一张真图：第一张有缩略图且非"缺失"占位的卡
    pick = b.ev("""(()=>{for(const c of document.querySelectorAll('.card')){
        const im=c.querySelector('img'); if(c.classList.contains('miss')||!im||im.naturalWidth<40) continue;
        const it=(typeof view!=='undefined'?view:[]).find(x=>x.thumb===im.getAttribute('src'));
        if(it) return JSON.stringify({url:it.img,label:it.name});}
      return '';})()""")
    if not isinstance(pick, str) or not pick.startswith('{'):
        ck('取图需要一张能加载的背景图', False, str(pick)[:60])
    else:
        p = json.loads(pick)
        for kind, url, label in (('bg', p['url'], p['label']),
                                 ('skin', '../Paintings_v2/abuluqi.png', 'abuluqi')):
            b.go('index.html', 2.4)
            b.ev('SiteBg.set(%s);1' % json.dumps({'url': url, 'kind': kind, 'key': label, 'label': label}))
            time.sleep(1.6)
            raw = base64.b64decode(b.cmd('Page.captureScreenshot', {'format': 'png'})['data'])
            f = os.path.join(shotd, f'sitebg_{kind}.png')
            open(f, 'wb').write(raw)
            print('  写了 sitebg_%s.png  fit=%s' % (kind, b.ev(
                'document.documentElement.style.getPropertyValue("--site-fit")')))
            # 对照改成"设了背景 vs 没设背景"两版必须不同 —— 这才是这条功能真正要证的：
            # 图落到屏幕上了。（原来那版是"藏掉 #bgfx 再拍"，它只能定位"被谁盖住"，
            #  而 #bgfx 里的光晕本来就该留着，所以那版对照现在会恒不同，读不出任何东西。）
            b.ev('SiteBg.clear();1'); time.sleep(1.0)
            raw0 = base64.b64decode(b.cmd('Page.captureScreenshot', {'format': 'png'})['data'])
            b.ev('SiteBg.set(%s);1' % json.dumps({'url': url, 'kind': kind, 'key': label, 'label': label}))
            time.sleep(1.0)
            print('  对照「设 / 不设」: %s' % ('✅ 画面确实换了 ⇒ 背景图落屏'
                                               if raw0 != raw else '❌ 两版逐字节相同 ⇒ 图没画出来（又被哪层盖住了）'))
            if raw0 == raw:
                fails.append(f'index.html: 站用背景 {kind} 设了但画面没变')
            # 音乐库昼间也拍一张：用户就是在这页报"字看不清"的（筛选 chip 压在亮色立绘上）。
            # 只拍首页等于把用户报的那一页漏在验收外面。
            b.go('bgm.html', 2.2)
            b.ev('SiteBg.set(%s);1' % json.dumps({'url': url, 'kind': kind, 'key': label, 'label': label}))
            time.sleep(1.4)
            open(os.path.join(shotd, f'bgm_{kind}.png'), 'wb').write(
                base64.b64decode(b.cmd('Page.captureScreenshot', {'format': 'png'})['data']))
            b.ev("document.documentElement.dataset.theme='light';1"); time.sleep(0.8)
            open(os.path.join(shotd, f'bgm_{kind}_light.png'), 'wb').write(
                base64.b64decode(b.cmd('Page.captureScreenshot', {'format': 'png'})['data']))
            # 本轮追加背景库判图：搜索与「只看收藏」正是用户反馈的两处透底控件。
            b.go('backgrounds.html', 2.2)
            b.ev('SiteBg.set(%s);1' % json.dumps({'url': url, 'kind': kind, 'key': label, 'label': label}))
            b.ev("document.getElementById('cFav').click();1")
            b.ev("document.documentElement.dataset.theme='light';1"); time.sleep(1.0)
            open(os.path.join(shotd, f'backgrounds_{kind}_light.png'), 'wb').write(
                base64.b64decode(b.cmd('Page.captureScreenshot', {'format': 'png'})['data']))
            b.ev("document.documentElement.dataset.theme='dark';1"); time.sleep(0.8)
            open(os.path.join(shotd, f'backgrounds_{kind}_dark.png'), 'wb').write(
                base64.b64decode(b.cmd('Page.captureScreenshot', {'format': 'png'})['data']))
        b.ev('SiteBg.clear();1')

b.close()
print('\n' + ('!! 未通过：\n  - ' + '\n  - '.join(fails) if fails else '✅ 收藏与网站背景：六组判据全过'))
sys.exit(1 if fails else 0)
