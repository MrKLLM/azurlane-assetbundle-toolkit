# -*- coding: utf-8 -*-
"""画廊 UI 样板对比截图：同一批界面状态，在两个页面（改前 / 改后）各截一张。

用途：改视觉语言时，先看样板再铺开——判据是"人眼看图"，所以工具只负责
把两边拍成**完全同一视角、同一尺寸、同一等待时长**的成对图片。

  py -3 scripts/diag/gallery_ui_shots.py                       # 默认比 index.html vs index_b.html
  py -3 scripts/diag/gallery_ui_shots.py --pages a.html,b.html --out .diag/uishots

⚠️ 两个坑（本轮踩过）：
  1. 无头窗口尺寸必须对齐用户实机（默认 2560,1600）——弹窗上限按 vw/vh 算，小窗口看不出真实观感。
  2. 打开皮肤后**不要**给 .view 刷背景色（取景量具 gallery_framing_ab.py 会刷，那是为了量落笔像素）；
     这里要看的就是用户实际看到的底。
"""
import sys, os, json, time, base64, argparse, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import websocket, chrome_tree

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
BASE = 'http://127.0.0.1:8777/gallery_v2'
WAIT = {'painting': 4.0, 'live2d': 11.0, 'spine': 11.0, 'voice': 4.0}

# 界面状态清单：(文件名, tab, 皮肤 key)。覆盖「列表 + 三种查看器 + 语音页」
STATES = [('1_grid', None, None), ('2_live2d', 'live2d', 'ninghai_4'),
          ('3_painting', 'painting', 'ninghai_4'), ('4_spine', 'spine', 'tansuozhe_2'),
          ('5_voice', 'voice', 'ninghai_4')]


class Page:
    def __init__(self, port, profile, url, win):
        self.proc = chrome_tree.install(subprocess.Popen([CHROME, '--headless=new',
            f'--remote-debugging-port={port}', '--remote-allow-origins=*',
            f'--user-data-dir={profile}', '--no-first-run', '--no-default-browser-check',
            '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
            '--use-angle=swiftshader', f'--window-size={win[0]},{win[1]}', url],
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
        self.cmd('Page.enable'); self.cmd('Runtime.enable')

    def cmd(self, m, p=None):
        self._id += 1; mid = self._id
        self.ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}}))
        self.ws.settimeout(180)
        while True:
            r = json.loads(self.ws.recv())
            if r.get('id') == mid:
                return r.get('result', {})

    def ev(self, expr):
        r = self.cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
        if r.get('exceptionDetails'):
            return 'EXC ' + str(r['exceptionDetails'].get('exception', {}).get('message'))[:200]
        return r.get('result', {}).get('value')

    def shot(self, path):
        d = base64.b64decode(self.cmd('Page.captureScreenshot', {'format': 'png'})['data'])
        open(path, 'wb').write(d)

    def close(self):
        try: self.cmd('Browser.close')
        except Exception: pass
        try: self.proc.wait(timeout=10)
        except Exception: chrome_tree.kill_tree(self.proc.pid)


def open_state(pg, tab, key):
    if tab is None:
        return pg.ev("document.querySelectorAll('.card').length")
    return pg.ev("""(()=>{const k=%r,t=%r;
      const hit=G.ships.find(s=>(s.live2dSkins||[]).includes(k)||(s.spineSkins||[]).includes(k)
                    ||s.skins.some(x=>x.key===k));
      if(!hit) return 'NO_SHIP';
      const sk=hit.skins.find(x=>x.key===k)||hit.skins[0];
      openShip(hit); setSkin(sk); buildSkinList(hit); tab=t; renderView();
      [...document.getElementById('mTabs').children].forEach(c=>c.classList.toggle('on', c.dataset.k===t));
      return 'ok';})()""" % (key, tab))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pages', default='index.html,index_b.html', help='逗号分隔：改前页,改后页')
    ap.add_argument('--tags', default='before,after')
    ap.add_argument('--win', default='2560,1600')
    ap.add_argument('--out', default=os.path.join(ROOT, '.diag', 'uishots'))
    ap.add_argument('--port', type=int, default=9431)
    a = ap.parse_args()
    pages = a.pages.split(',')
    tags = a.tags.split(',')
    win = tuple(int(v) for v in a.win.split(','))
    os.makedirs(a.out, exist_ok=True)
    profile = os.path.join(ROOT, '.diag', 'chrome_uishots')
    os.makedirs(profile, exist_ok=True)
    for tag, page in zip(tags, pages):
        print(f'== {tag}  {page} ==')
        pg = Page(a.port, profile, f'{BASE}/{page}', win)
        time.sleep(7)
        pg.ev("localStorage.clear()")
        pg.cmd('Page.navigate', {'url': f'{BASE}/{page}'})
        time.sleep(6)
        for name, tab, key in STATES:
            r = open_state(pg, tab, key)
            if tab:
                time.sleep(WAIT[tab])
            out = os.path.join(a.out, f'{tag}_{name}.png')
            pg.shot(out)
            print(f'  {name:<12} {str(r):<8} -> {os.path.basename(out)}')
        pg.close()
        time.sleep(1.5)


if __name__ == '__main__':
    main()
