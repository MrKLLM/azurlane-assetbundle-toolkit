# -*- coding: utf-8 -*-
"""A/B 取景回归：同一批皮肤分别用「旧版页面」和「新版页面」打开，量「内容占视口比例」。

判据 = 截图里 view 矩形内「落笔像素」（max(r,g,b)>40，与 Spine 取证同一把尺子）的包围盒，
除以视口宽高。棋盘格底色本身很暗（#12172a / #0d1120，亮度 <25），不会污染这个阈值。

  py -3 scripts/diag/gallery_framing_ab.py                 # 新旧都跑，出对比表
  py -3 scripts/diag/gallery_framing_ab.py --pages new     # 只跑新版（+ 视角记忆断言）
  py -3 scripts/diag/gallery_framing_ab.py --n 6

退出码：0=全部通过；1=有皮肤新版比旧版更小（回退）；2=记忆断言失败。
"""
import sys, os, json, time, base64, argparse, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import websocket, chrome_tree
from PIL import Image
import io as _io

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
BASE = 'http://127.0.0.1:8777/gallery_v2'
INK = 26          # 落笔阈值（底色已在 measure() 里刷成纯黑；棋盘亮格 max=42，不刷黑任何阈值都挡不住）
WAIT = {'painting': 3.5, 'live2d': 10.0, 'spine': 10.0}


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pages', default='both', choices=['both', 'new', 'old'])
    ap.add_argument('--n', type=int, default=10, help='每类（live2d / spine）取几个样本')
    ap.add_argument('--out', default=os.path.join(ROOT, '.diag', 'framing'))
    ap.add_argument('--port', type=int, default=9421)
    ap.add_argument('--win', default='2560,1600',
                    help='无头窗口尺寸，默认对齐用户实机 2560x1600（弹窗上限是按 vw/vh 算的，小窗口测不出收益）')
    ap.add_argument('--mem', type=int, default=1, help='0=跳过视角记忆断言')
    return ap.parse_args()


class Page:
    def __init__(self, port, profile, url, win=(1600, 1000)):
        # chrome_tree.install：漏了它，异常路径下会留一整棵 SwiftShader renderer 在吃内存
        self.proc = chrome_tree.install(subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={port}',
            '--remote-allow-origins=*', f'--user-data-dir={profile}', '--no-first-run',
            '--no-default-browser-check', '--disable-background-timer-throttling',
            '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
            f'--window-size={win[0]},{win[1]}', url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        ws = None
        for _ in range(100):
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

    def ev(self, expr):
        r = self.cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
        if r.get('exceptionDetails'):
            return 'EXC ' + str(r['exceptionDetails'].get('exception', {}).get('message'))[:160]
        return r.get('result', {}).get('value')

    def png(self):
        return Image.open(_io.BytesIO(base64.b64decode(self.cmd('Page.captureScreenshot', {'format': 'png'})['data']))).convert('RGB')

    def close(self):
        try:
            self.cmd('Browser.close')
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def open_skin(pg, key, tab):
    """按皮肤 key 打开对应船，选到该皮肤，切到 tab。"""
    r = pg.ev("""(()=>{const k=%r,t=%r;
      const hit=G.ships.find(s=>(s.live2dSkins||[]).includes(k)||(s.spineSkins||[]).includes(k)
                    ||s.skins.some(x=>x.key===k));
      if(!hit) return 'NO_SHIP';
      const sk=hit.skins.find(x=>x.key===k)||hit.skins[0];
      openShip(hit); setSkin(sk); buildSkinList(hit); tab=t; renderView();
      document.getElementById('mView').style.background='#000';   // 量「落笔」前要掉棋盘格底色
      return 'ok';})()""" % (key, tab))
    return r


def measure(pg, tab):
    """内容包围盒 ÷ 绘图区矩形。
    基准框按视图取：live2d=#l2wrap（本身已让开底部 44px 控制条）、spine=canvas 再去掉底部 48px
    控制条压字、painting=#imgStage 且直接用 img 的矩形（精确值，不用阈值猜）。
    ⚠️ 判「落笔」前必须把 .view 的棋盘格底色刷成纯黑 —— 棋盘亮格 #12172a 的 max 通道 =42，
    任何合理阈值都挡不住它，实测会把整屏算成内容（wf/hf 恒等 0.999）。"""
    g = pg.ev("""(()=>{const v=document.getElementById('mView'),vr=v.getBoundingClientRect();
      const el=document.getElementById('l2wrap')||document.getElementById('imgStage')||v.querySelector('canvas');
      const r=(el||v).getBoundingClientRect();
      const im=document.querySelector('#imgStage img');
      let ir=null; if(im){const b=im.getBoundingClientRect(); ir=[b.left-r.left,b.top-r.top,b.width,b.height];}
      return JSON.stringify({vx:r.left,vy:r.top,vw:r.width,vh:r.height,ir:ir});})()""")
    if isinstance(g, str) and g.startswith('EXC'):
        raise RuntimeError(g)
    d = json.loads(g)
    w, h = d['vw'], d['vh']
    if tab == 'painting' and d['ir']:
        ix, iy, iw, ih = d['ir']
        return {'vw': round(w), 'vh': round(h), 'pxw': round(iw), 'pxh': round(ih), 'pxa': round(iw * ih),
                'wf': round(iw / w, 3), 'hf': round(ih / h, 3),
                'area': round(iw * ih / (w * h), 4),
                'cx': round((ix + iw / 2) / w, 3), 'cy': round((iy + ih / 2) / h, 3)}
    top, left = int(d['vy']), int(d['vx'])
    hh = max(20, int(h - (48 if tab == 'spine' else 0)))     # 控制条上的浅色字会被算成落笔
    ww = max(20, int(w))
    box = pg.png().crop((left, top, left + ww, top + hh))
    px = box.load()
    x0, y0, x1, y1 = 10 ** 9, 10 ** 9, -1, -1
    for yy in range(0, box.height, 2):
        for xx in range(0, box.width, 2):
            r, gg, b = px[xx, yy]
            if (r if r > gg and r > b else (gg if gg > b else b)) > INK:
                if xx < x0: x0 = xx
                if xx > x1: x1 = xx
                if yy < y0: y0 = yy
                if yy > y1: y1 = yy
    if x1 < 0:
        return {'vw': ww, 'vh': hh, 'pxw': 0, 'pxh': 0, 'pxa': 0, 'wf': 0.0, 'hf': 0.0, 'area': 0.0, 'cx': 0.5, 'cy': 0.5}
    return {'vw': ww, 'vh': hh, 'pxw': x1 - x0 + 1, 'pxh': y1 - y0 + 1, 'pxa': (x1 - x0 + 1) * (y1 - y0 + 1),
            'wf': round((x1 - x0 + 1) / ww, 3), 'hf': round((y1 - y0 + 1) / hh, 3),
            'area': round((x1 - x0 + 1) * (y1 - y0 + 1) / (ww * hh), 4),
            'cx': round(((x0 + x1) / 2) / ww, 3), 'cy': round(((y0 + y1) / 2) / hh, 3)}


def samples(pg, n):
    r = pg.ev("""(()=>{const G=window.GALLERY,n=%d;
      const l2=[],sp=[];
      for(const s of G.ships){ for(const k of (s.live2dSkins||[])) l2.push(k);
                               for(const k of (s.spineSkins||[])) sp.push(k); }
      const take=(a)=>{const out=[],step=Math.max(1,Math.floor(a.length/n));
        for(let i=0;i<a.length&&out.length<n;i+=step) out.push(a[i]); return out;};
      return JSON.stringify({l2:take(l2),sp:take(sp)});})()""" % n)
    d = json.loads(r)
    force(d['l2'], 'ninghai_4')
    force(d['sp'], 'tansuoazhe_2')
    return [('live2d', k) for k in d['l2']] + [('spine', k) for k in d['sp']]


def force(lst, k):
    """把基线样本挪到最前（只在真的存在时）—— 两个页面跑的是同一份样本表，A/B 才可比。"""
    if k in lst:
        lst.insert(0, lst.pop(lst.index(k)))


def run_ab(pg, tag, n, out):
    rows = []
    for tab, key in samples(pg, n):
        if open_skin(pg, key, tab) != 'ok':
            print('  %-4s %s 跳过（打不开）' % (tag, key))
            continue
        time.sleep(WAIT[tab])
        m = measure(pg, tab)
        m.update({'tag': tag, 'tab': tab, 'key': key})
        pg.png().save(os.path.join(out, '%s_%s_%s.png' % (tag, tab, key)))
        rows.append(m)
        print('  %-4s %-22s %-7s 视口%5dx%-5d 内容 %5dx%-5d px  占宽 %.3f 占高 %.3f'
              % (tag, key, tab, m['vw'], m['vh'], m['pxw'], m['pxh'], m['wf'], m['hf']))
    return rows


def wheel(pg, kind, ctrl=False):
    """在 #mView 中心派发一次滚轮（新版 live2d 要 Ctrl，painting/spine 裸滚轮）。"""
    pg.ev("""(()=>{const v=document.getElementById('mView'),r=v.getBoundingClientRect();
      v.dispatchEvent(new WheelEvent('wheel',{bubbles:true,cancelable:true,
        clientX:r.left+r.width/2, clientY:r.top+r.height/2, deltaY:%r, ctrlKey:%s}));
      const c=v.querySelector('canvas'); if(c) c.dispatchEvent(new WheelEvent('wheel',
        {bubbles:true,cancelable:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2,
         deltaY:%r, ctrlKey:%s}));
      const st=document.getElementById('imgStage'); if(st) st.dispatchEvent(new WheelEvent('wheel',
        {bubbles:true,cancelable:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2,
         deltaY:%r, ctrlKey:%s}));
      return 'ok';})()""" % (-120 if kind == 'in' else 120, 'true' if ctrl else 'false',
                              -120 if kind == 'in' else 120, 'true' if ctrl else 'false',
                              -120 if kind == 'in' else 120, 'true' if ctrl else 'false'))


def memory_tests(pg, out):
    """视角记忆：改视角 → 关掉重开 → 应回到改后的位置；换窗口尺寸 → 不应错位。"""
    fails = []
    for tab, key, ctrl in [('live2d', 'ninghai_4', True), ('spine', 'tansuozhe_2', False),
                           ('painting', 'ninghai_4', False)]:
        pg.ev("localStorage.removeItem('gallery.view.v1')")
        open_skin(pg, key, tab)          # 无记忆状态打开 = 默认取景基线
        time.sleep(WAIT[tab])
        fresh = measure(pg, tab)
        # 放大 + 平移
        wheel(pg, 'in', ctrl)
        wheel(pg, 'in', ctrl)
        pg.ev("""(()=>{const v=document.getElementById('mView'),r=v.getBoundingClientRect();
          const t=v.querySelector('canvas')||document.getElementById('imgStage');
          t.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:r.left+40,clientY:r.top+40,pointerId:2,buttons:1}));
          t.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,clientX:r.left+120,clientY:r.top+90,pointerId:2,buttons:1}));
          t.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,clientX:r.left+120,clientY:r.top+90,pointerId:2}));
          const cv=v.querySelector('canvas'); if(cv){cv.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,clientX:r.left+40,clientY:r.top+40,button:0}));
            window.dispatchEvent(new MouseEvent('mousemove',{clientX:r.left+120,clientY:r.top+90}));
            window.dispatchEvent(new MouseEvent('mouseup',{clientX:r.left+120,clientY:r.top+90}));}
          return 'ok';})()""")
        wheel(pg, 'in', ctrl)
        time.sleep(1.2)
        moved = measure(pg, tab)
        stored = pg.ev("localStorage.getItem('gallery.view.v1')")
        nkey = '%s|%s' % (key, tab)
        if not stored or nkey not in str(stored):
            fails.append('%s: 没写进 localStorage（%s）' % (nkey, str(stored)[:60]))
            continue
        pg.ev("closeShip()")
        time.sleep(0.6)
        open_skin(pg, key, tab)
        time.sleep(WAIT[tab])
        back = measure(pg, tab)
        # 判据本身要能红：先确认「操作确实改变了取景」，否则 back==moved==fresh 是假绿灯
        tol = 0.02 if tab == 'painting' else 0.06      # live2d 在呼吸，像素包围盒天生 ±5% 噪声
        if abs(moved['area'] - fresh['area']) < 0.03:
            fails.append('%s: 滚轮/拖拽没改变取景（%.3f→%.3f），这条断言是空的' % (nkey, fresh['area'], moved['area']))
            continue
        ok = abs(back['area'] - moved['area']) < tol
        print('  记忆 %-7s %-14s 默认面积%.3f → 操作后%.3f → 重开%.3f  %s'
              % (tab, key, fresh['area'], moved['area'], back['area'], 'OK' if ok else 'FAIL'))
        if not ok:
            fails.append('%s: 重开没回到上次视角 (%.3f vs %.3f)' % (nkey, back['area'], moved['area']))
        # 换窗口尺寸应保持「同一个视角」而不是被抹掉
        pg.cmd('Emulation.setDeviceMetricsOverride', {'width': 1200, 'height': 800, 'deviceScaleFactor': 1, 'mobile': False})
        time.sleep(2.0)
        small = measure(pg, tab)
        pg.cmd('Emulation.clearDeviceMetricsOverride')
        time.sleep(2.0)
        again = measure(pg, tab)
        if abs(small['vw'] - back['vw']) < 8:
            fails.append('%s: setDeviceMetricsOverride 没生效（基准宽 %d vs %d），resize 断言是空的'
                         % (nkey, small['vw'], back['vw']))
        drift = abs(again['cx'] - back['cx']) + abs(again['cy'] - back['cy'])
        print('  尺寸   %-7s %-14s 基准宽 %d→%d→%d；往返后中心偏移 %.3f（阈值 0.12）%s'
              % (tab, key, back['vw'], small['vw'], again['vw'], drift, 'OK' if drift < 0.12 else 'FAIL'))
        if drift >= 0.12:
            fails.append('%s: resize 往返后中心偏移 %.3f' % (nkey, drift))
        # 关掉「记住视角」→ 应回到默认取景
        pg.ev("OPT.remember=false; saveOpt(); closeShip();")
        time.sleep(0.5)
        open_skin(pg, key, tab)
        time.sleep(WAIT[tab])
        off = measure(pg, tab)
        ok2 = abs(off['area'] - fresh['area']) < tol
        print('  开关   %-7s %-14s 关「记住视角」后面积%.3f（默认%.3f）%s'
              % (tab, key, off['area'], fresh['area'], 'OK' if ok2 else 'FAIL'))
        if not ok2:
            fails.append('%s: 关掉开关仍在使用记忆 (%.3f != %.3f)' % (nkey, off['area'], fresh['area']))
        pg.ev("OPT.remember=true; saveOpt();")
    return fails


def main():
    a = parse()
    os.makedirs(a.out, exist_ok=True)
    profile = os.path.join(ROOT, '.diag', 'chrome_framing')
    os.makedirs(profile, exist_ok=True)
    pages = {'new': f'{BASE}/index.html', 'old': f'{BASE}/index_old.html'}
    if a.pages == 'both':
        order = ['old', 'new']
    else:
        order = [a.pages]
    result = {}
    for tag in order:
        print(f'== {tag} 页 ==')
        pg = Page(a.port, profile, pages[tag], win=tuple(int(v) for v in a.win.split(',')))
        time.sleep(6)
        # 上一轮跑留下的视角记忆会让「新版」看起来取景怪异 —— 每轮都从干净状态开始
        pg.ev("localStorage.clear()")
        pg.cmd('Page.navigate', {'url': pages[tag]})
        time.sleep(6)
        pg.ev("document.querySelectorAll('.card').length")
        result[tag] = run_ab(pg, tag, a.n, a.out)
        if tag == 'new' and a.mem:
            print('-- 视角记忆断言 --')
            fails = memory_tests(pg, a.out)
        else:
            fails = []
        pg.close()
        time.sleep(1.5)
    json.dump(result, open(os.path.join(a.out, 'framing.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if 'old' in result and 'new' in result:
        old = {r['key'] + r['tab']: r for r in result['old']}
        # 判据用「内容绝对像素面积」而不是「占视口面积比」：新版视口自身变了形状
        # （16:10 宽窗里 Live2D 从宽受限变成高受限），比例会假报回退，绝对像素才是用户看到的。
        print('\n== 对比（内容绝对像素面积 新/旧）==')
        worse = 0
        for r in result['new']:
            o = old.get(r['key'] + r['tab'])
            if not o or not o.get('pxa'):
                continue
            g = r['pxa'] / o['pxa']
            flag = '  <-- 比旧版小' if g < 0.98 else ''
            if flag:
                worse += 1
            print('  %-7s %-16s %6dx%-6d -> %6dx%-6d  x%.3f%s'
                  % (r['tab'], r['key'], o['pxw'], o['pxh'], r['pxw'], r['pxh'], g, flag))
        print('回退样本数 =', worse)
        if fails:
            print('\n记忆断言 FAIL:'); [print('  -', x) for x in fails]
        sys.exit(2 if fails else (1 if worse else 0))


main()
