# -*- coding: utf-8 -*-
"""Spine 标签的 parts.json 接线验收（黑盒：只点真实 DOM、只读页面上本来就有的显示）。

为什么单独要这一个：`interact_verify` 走的是 Live2D 那条分支，**根本不碰 startSpine**。
本轮改的正是 startSpine / cg_export 的取层与逐层起始动画，拿 Live2D 全绿当"改过的地方没问题"
就是拿代理指标冒充真观测。

判据全部落在页面上**已经存在的可观测量**，不往正本里加测试专用钩子：
  · 层数   → `.spine-bar` 里那句 "N 层部件" 的 pill（它直接由 layers.length 渲染）
  · 动画   → `#spAnim` 的 value（本轮改成按 prefab 逐层写的 startingAnimation 选默认）
  · 报错   → 页面上的 .note 文案 + 浏览器 console
  · 断链   → parts.json 404 时页面必须**明说**，不许静默按 glob 画
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = int(os.environ.get('SPINE_PROBE_PORT', '9351'))
PROFILE = os.path.join(ROOT, '.diag', 'chrome_spineprobe')
URL = 'http://127.0.0.1:8777/gallery_v2/index.html'

# (皮肤 key, 期望层数, 期望默认动画)  —— 期望值一律从 parts.json 现算，不写死在本脚本里
CASES = ['huajia_2', 'huajia_2_hx', 'buleisite', 'duyisibao_2', 'bailong', 'pulimaosi']

sys.path.insert(0, os.path.join(ROOT, 'scripts', 'diag'))
import websocket  # noqa: E402

proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
  '--remote-allow-origins=*', f'--user-data-dir={PROFILE}', '--no-first-run',
  '--no-default-browser-check', '--disable-background-timer-throttling',
  '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--window-size=1280,900', URL],
  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
import chrome_tree
chrome_tree.install(proc)

ws = None
for _ in range(90):
    try:
        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
        ws = [t['webSocketDebuggerUrl'] for t in tabs
              if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
        if ws:
            break
    except Exception:
        pass
    time.sleep(0.5)
if not ws:
    raise SystemExit('! 浏览器没起来或页面没打开')
ws = websocket.create_connection(ws[0], timeout=120, max_size=None)
_id = 0
console_errs = []


def cmd(m, p=None):
    global _id
    _id += 1
    ws.send(json.dumps({'id': _id, 'method': m, 'params': p or {}}))
    ws.settimeout(120)
    while True:
        r = json.loads(ws.recv())
        if r.get('method') == 'Runtime.consoleAPICalled' and r['params'].get('type') == 'error':
            console_errs.append(' '.join(str(a.get('value', a.get('description', '')))
                                         for a in r['params'].get('args', []))[:160])
        if r.get('id') == _id:
            if 'error' in r:
                raise RuntimeError(json.dumps(r['error'])[:160])
            return r.get('result', {})


def ev(e):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    if r.get('exceptionDetails'):
        return {'__err': str(r['exceptionDetails'].get('text'))[:200]}
    return r.get('result', {}).get('value')


cmd('Runtime.enable')

# 必须等页面脚本真的加载完再开始 —— 第一版没等，结果第一条案例读到
# `openShip is not defined` 被判成产品缺陷，而那只是探针跑太早（假红灯）。
for _ in range(120):
    ready = ev("(typeof openShip==='function' && typeof setSkin==='function'"
               " && !!(window.GALLERY&&window.GALLERY.ships))?1:0")
    if ready == 1:
        break
    time.sleep(0.5)
else:
    raise SystemExit('! 页面脚本 60s 内没就绪，探针作废（不要把这读成产品坏了）')
print('页面已就绪：GALLERY.ships =', ev('window.GALLERY.ships.length'))

EXPECT = {}
for k in CASES:
    p = os.path.join(ROOT, 'Output', 'Spine_v2', k, 'parts.json')
    L = json.load(open(p, encoding='utf-8'))['layers']
    EXPECT[k] = {'n': len(L), 'anims': sorted({l['startingAnimation'] for l in L}),
                 'scales': [l['localScale'] for l in L]}

JS_OPEN = r"""(async(key)=>{
  const G=window.GALLERY;
  let hit=null;
  for(const s of (G.ships||[])) for(const sk of (s.skins||[])){
    if(sk.key===key && sk.spine && sk.spine.folder){ hit={s,sk}; break; }
  }
  if(!hit) return {err:'索引里找不到该 Spine 皮肤'};
  openShip(hit.s); setSkin(hit.sk);
  const tb=[...document.querySelectorAll('.tab')].find(t=>/spine/i.test(t.textContent));
  if(!tb) return {err:'没有 Spine 标签'};
  if(/dis/.test(tb.className)) return {err:'Spine 标签是禁用态'};
  tb.click();
  for(let i=0;i<80;i++){ await new Promise(r=>setTimeout(r,250));
    const bar=document.querySelector('.spine-bar');
    if(bar && document.querySelector('#spAnim')) break;
    const n=document.querySelector('#mView .note'); if(n&&/失败|缺 parts/.test(n.textContent)) break; }
  await new Promise(r=>setTimeout(r,900));
  const bar=document.querySelector('.spine-bar');
  const pill=bar?[...bar.querySelectorAll('.span,.pill')].map(x=>x.textContent).join(' | '):'';
  const sel=document.querySelector('#spAnim');
  const note=document.querySelector('#mView .note');
  return {pill, anim: sel?sel.value:null,
          opts: sel?[...sel.options].map(o=>o.value):[],
          note: note?note.textContent.slice(0,120):'',
          canvas: !!document.querySelector('#mView canvas')};
})"""

print(f'{"皮肤":16s} {"期望层数":>6} {"页面报的层数":>10} {"期望动画":>16} {"实际默认":>8}  判定')
fails = []
for k in CASES:
    console_errs.clear()
    r = ev(f'{JS_OPEN}({json.dumps(k)})')
    if not isinstance(r, dict) or r.get('err'):
        fails.append((k, r.get('err') if isinstance(r, dict) else str(r)[:120]))
        print(f'{k:16s} {"-":>6} {"-":>10} {"-":>16} {"-":>8}  ✗ {fails[-1][1]}')
        continue
    exp = EXPECT[k]
    got_n = None
    import re
    m = re.search(r'(\d+)\s*层部件', r.get('pill') or '')
    if m:
        got_n = int(m.group(1))
    ok_n = got_n == exp['n']
    ok_a = (r.get('anim') in exp['anims']) or (r.get('anim') == '' and 'normal' in exp['anims'])
    ok_c = r.get('canvas') and not r.get('note')
    bad = [e for e in console_errs if 'parts.json' in e or 'Uncaught' in e or 'Error' in e]
    verdict = '✅' if (ok_n and ok_a and ok_c and not bad) else '❌'
    if verdict == '❌':
        fails.append((k, f'层数 {got_n}≠{exp["n"]}' if not ok_n else
                            (f'动画 {r.get("anim")}∉{exp["anims"]}' if not ok_a else
                             (f'note={r.get("note")!r}' if not ok_c else f'console={bad[:2]}'))))
    print(f'{k:16s} {exp["n"]:>6} {str(got_n):>10} {",".join(exp["anims"])[:16]:>16} '
          f'{str(r.get("anim")):>8}  {verdict}'
          + ('' if verdict == '✅' else f'   {r}'))
    ev("(function(){var c=[].slice.call(document.querySelectorAll('.tab'))"
       ".find(t=>/立绘|静态/.test(t.textContent));if(c)c.click();return 1})()")

print()
if fails:
    print('未通过:', fails)
    sys.exit(1)
print('全部通过：Spine 标签确实按 parts.json 取层、按 prefab 的 startingAnimation 选默认')
