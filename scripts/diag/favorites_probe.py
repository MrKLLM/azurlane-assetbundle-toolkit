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
"""
import sys, os, json, time, base64, shutil, argparse, subprocess, urllib.request

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
                help='跑完判据后再取两张人眼判图：背景图(cover 铺满) 与 皮肤立绘(contain 贴底)，'
                     '落在 .diag/favshots/。判据只说"生效了"，铺得对不对只能看')
A = AP.parse_args()
W, H = (int(x) for x in A.win.split(','))
BASE = f'http://127.0.0.1:{A.port}/gallery_v2'
CDP = 9381
fails = []


class Br:
    def __init__(self):
        prof = os.path.abspath('.diag/fav_profile')
        shutil.rmtree(prof, ignore_errors=True)
        for _ in range(20):
            try:
                os.makedirs(prof); break
            except FileExistsError:
                time.sleep(0.4)
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
    print('\n---- 人眼判图（.diag/favshots/）----')
    shotd = os.path.join(ROOT, '.diag', 'favshots')
    shutil.rmtree(shotd, ignore_errors=True); os.makedirs(shotd, exist_ok=True)
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
        b.ev('SiteBg.clear();1')

b.close()
print('\n' + ('!! 未通过：\n  - ' + '\n  - '.join(fails) if fails else '✅ 收藏与网站背景：六组判据全过'))
sys.exit(1 if fails else 0)
