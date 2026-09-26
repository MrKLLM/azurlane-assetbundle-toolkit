# -*- coding: utf-8 -*-
"""无头 Chrome + CDP 逐个打开画廊 Live2D 皮肤，裁出模型画布截图供**目视**判定。

存在的理由：参数变化条数、加载成功与否都是代理指标，「画面对不对」只能看。
贴图索引错绑这类故障（部件堆叠成碎片）在代理指标下全是绿的。

用法:
    py -3 scripts/diag/l2d_shot_models.py benningdun_2 sebao_2
    py -3 scripts/diag/l2d_shot_models.py --tab spine aluomangshi_2 yunlong_2
    py -3 scripts/diag/l2d_shot_models.py            # 用内置默认清单
输出: .diag/l2d_shots_visual/<key>.png + 终端每模型一行状态
前置: 本地服务器 127.0.0.1:8777 已起（根目录 = Output/）
"""
import sys, os, json, time, base64, subprocess, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9337
DEBUG_DIR = os.path.join(ROOT, '.diag', 'chrome_l2d_shot')
SHOTS = os.path.join(ROOT, '.diag', 'l2d_shots_visual')
BASE = 'http://127.0.0.1:8777/gallery_v2/index.html'
DEFAULT = ['benningdun_2', 'feiteliekaer_4', 'sebao_2', 'shi_3', 'wuzang_4',
           'bunao_3', 'pulimaosi_3']

TAB = 'live2d'
SKIN = None
for i, a in enumerate(sys.argv):
    if a == '--tab' and i + 1 < len(sys.argv):
        TAB = sys.argv[i + 1]
    if a == '--skin' and i + 1 < len(sys.argv):
        SKIN = sys.argv[i + 1]   # Spine 皮肤下拉的目标值；'none' = 不设 skin
keys = [a for i2, a in enumerate(sys.argv[1:])
        if not a.startswith('--') and sys.argv[i2] not in ('--tab', '--skin')] or DEFAULT
if TAB not in ('live2d', 'spine'):
    sys.exit('--tab 只支持 live2d / spine')
os.makedirs(SHOTS, exist_ok=True)
for key in keys:                      # 只清本次要重拍的，保留历史证据
    p = os.path.join(SHOTS, key + '.png')
    if os.path.isfile(p):
        os.remove(p)

proc = subprocess.Popen([
    CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
    '--remote-allow-origins=*', f'--user-data-dir={DEBUG_DIR}',
    '--no-first-run', '--no-default-browser-check',
    '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
    '--use-angle=swiftshader', '--window-size=1400,1000', BASE,
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_ws():
    for _ in range(80):
        try:
            for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')):
                if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl'):
                    return t['webSocketDebuggerUrl']
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError('CDP 未就绪')


ws = websocket.create_connection(wait_ws(), timeout=60)
_id = 0


def cmd(method, params=None):
    global _id
    _id += 1
    ws.send(json.dumps({'id': _id, 'method': method, 'params': params or {}}))
    while True:
        m = json.loads(ws.recv())
        if m.get('id') == _id:
            if 'error' in m:
                raise RuntimeError(json.dumps(m['error'])[:200])
            return m.get('result', {})


def ev(expr, awaitp=False):
    r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': awaitp})
    if r.get('exceptionDetails'):
        ex = r['exceptionDetails']
        return 'EVALERR ' + str(ex.get('exception', {}).get('description') or ex.get('text'))[:200]
    res = r.get('result', {})
    return res.get('value') if res.get('type') == 'string' else res.get('value')


def open_view(key, settle_ms):
    """走画廊真实入口打开该皮肤的 live2d / spine 标签，返回状态 + canvas 的 clip。"""
    js = ("""(async () => { try {
      const t=ms=>new Promise(r=>setTimeout(r,ms)), KEY=__KEY__, TAB=__TAB__;
      let ship=null, sk=null;
      for (const s of GALLERY.ships) { const k=s.skins.find(x=>x.key===KEY);
        if(!k) continue;
        const has = TAB==='spine' ? !!k.spine : (s.live2dSkins||[]).includes(KEY);
        if(has){ ship=s; sk=k; break; } }
      if(!sk) return JSON.stringify({key:KEY, skip:'index 里该皮肤没有 ' + TAB + ' 资源'});
      openShip(ship); setSkin(sk); buildSkinList(ship);
      tab=TAB; renderView();
      await t(__SETTLE__);
      if (__WANTSKIN__ !== null && TAB === 'spine') {
        const sp0 = document.getElementById('spSkin');
        if (!sp0) return JSON.stringify({key:KEY, fail:'没有皮肤下拉（该骨架无命名 skin？）'});
        sp0.value = __WANTSKIN__; sp0.onchange();
        await t(1200);
      }
      const sel = TAB==='spine' ? '#spcwrap canvas' : '#l2wrap canvas';
      let extra={};
      if (TAB==='spine') {
        const sp=document.getElementById('spSkin');
        extra={ skinSel: sp ? {value:sp.value, opts:[...sp.options].map(o=>o.value)} : null,
                animSel:(document.getElementById('spAnim')||{}).value||null };
      } else {
        const app=l2State&&l2State.app, m=app&&app.stage.children[0];
        if(!m) return JSON.stringify({key:KEY, fail:'no model',
                                      note:(document.querySelector('.note')||{}).textContent||''});
        extra={ drawables: m.internalModel.coreModel.getDrawableCount
                             ? m.internalModel.coreModel.getDrawableCount() : -1 };
      }
      const cv=document.querySelector(sel);
      if(!cv) return JSON.stringify({key:KEY, fail:'no canvas', sel,
                                     note:(document.querySelector('.note')||{}).textContent||''});
      const r=cv.getBoundingClientRect();
      return JSON.stringify(Object.assign({key:KEY, ok:true,
        clip:{x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height)}}, extra));
    } catch(e) { return JSON.stringify({key:__KEY__, fail:'JSERR '+(e&&e.message||String(e)).slice(0,150)}); }
    })()""").replace('__KEY__', json.dumps(key)).replace('__TAB__', json.dumps(TAB)) \
             .replace('__SETTLE__', str(settle_ms)) \
             .replace('__WANTSKIN__', json.dumps('∅' if SKIN == 'none' else SKIN))
    return ev(js, awaitp=True)



try:
    cmd('Page.enable')
    # 全新 profile 无缓存：index.js 近 1MB + index.json 0.8MB，且服务器是单线程 http.server，
    # 冷启动可达 2 分钟。首个 eval 抢跑会拿到 'GALLERY is not defined'（实测首模型偶发失败）。
    for _ in range(180):
        # 必须显式转字符串比较：`A && B && C.length` 返回的是**数字**（ships 长度），
        # 拿它 `is True` 恒为假，就绪门会退化成白等 180 秒。
        if ev('String(typeof GALLERY!=="undefined"&&Array.isArray(GALLERY.ships)&&GALLERY.ships.length>0)') == 'true':
            break
        time.sleep(1.0)
    else:
        print("页面 180s 内未就绪（GALLERY.ships 仍为空）", flush=True)
    for key in keys:
        try:
            r = json.loads(open_view(key, 9000 if TAB == 'live2d' else 16000))
        except Exception as e:
            r = {'key': key, 'fail': 'driver ' + str(e)[:80]}
        if r.get('ok') and r.get('clip'):
            c = r.pop('clip')
            shot = cmd('Page.captureScreenshot', {'format': 'png', 'clip': {
                'x': c['x'], 'y': c['y'], 'width': c['w'], 'height': c['h'], 'scale': 1}})
            open(os.path.join(SHOTS, key + '.png'), 'wb').write(base64.b64decode(shot['data']))
        print(json.dumps(r, ensure_ascii=False), flush=True)
finally:
    ws.close()
    proc.terminate()
print('截图目录:', SHOTS)
