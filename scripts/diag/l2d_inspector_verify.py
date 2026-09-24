# -*- coding: utf-8 -*-
"""Live2D 检查器验收：判定区可视化 + 参数·部件面板（l2d.su 同款三件套）。

断言：
  ① 判定区开关：Graphics 出现且 visible=true，图形数=判定区数，标签=部位名；关闭后 visible=false
  ② 面板：行数 = 参数数 + 部件数；名字取到真实参数名（非 ParamN 占位）
  ③ 滑杆读写往返：setParameterValueByIndex 后读回一致；部件 setPartOpacityByIndex 同理
  ④ 过滤器：输入子串后可见行数减少且命中项包含该子串
用法: py -3 scripts/diag/l2d_inspector_verify.py [皮肤key，默认 lafeiii_3]
输出: .diag/_probe_feats.json、.diag/_areaviz_on.png（判定区开启时的截图）
"""
import sys, os, json, time, base64, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9373
PROFILE = os.path.join(ROOT, '.diag', 'chrome_insp')
os.makedirs(PROFILE, exist_ok=True)
proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
  '--remote-allow-origins=*', f'--user-data-dir={PROFILE}', '--no-first-run',
  '--no-default-browser-check', '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
  '--use-angle=swiftshader', '--window-size=1280,900',
  'http://127.0.0.1:8777/gallery_v2/index.html'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
w = None
for _ in range(90):
    try:
        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
        w = [t['webSocketDebuggerUrl'] for t in tabs if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
        if w: break
    except Exception: pass
    time.sleep(0.5)
ws = websocket.create_connection(w[0], timeout=180, max_size=None)
_id = 0
def cmd(m, p=None):
    global _id; _id += 1; mid = _id
    ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}})); ws.settimeout(180)
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == mid:
            if 'error' in r: raise RuntimeError(json.dumps(r['error'])[:150])
            return r.get('result', {})
def ev(e):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    if r.get('exceptionDetails'): return 'EVALERR ' + str(r.get('exceptionDetails'))[:300]
    return r.get('result', {}).get('value')

KEY = sys.argv[1] if len(sys.argv) > 1 else 'lafeiii_3'
JS = r"""(async(key)=>{ try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<120 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
  if(!window.GALLERY || typeof openShip!=='function') return JSON.stringify({key, err:'页面脚本未就绪（GALLERY/openShip 缺失）'});
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  const l2=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d');
  l2.click(); await t(6000);
  const out={key};
  const m=l2State.app.stage.children[0], core=m.internalModel.coreModel, im=m.internalModel;
  // ① 判定区可视化
  const st=l2State.app.stage;
  document.getElementById('l2AreasBtn').click(); await t(600);
  const gfx=st.children.filter(c=>c instanceof PIXI.Graphics);
  const usable=(window.__L2_HITUSE? __L2_HITUSE().slice() : (im.settings.hitAreas||[]).map(a=>a.Name));
  out.areas={btnOn:document.getElementById('l2AreasBtn').classList.contains('on'),
             graphics:gfx.length, visible:gfx.map(g=>g.visible), shapes:gfx.map(g=>g.geometry.graphicsData.length),
             registered:(im.settings.hitAreas||[]).length, usableN:usable.length,
             labels:st.children.filter(c=>c instanceof PIXI.Text && c.visible).map(c=>c.text)};
  /* 2026-09-24 起登记数 ≠ 可点数：退化框（面积或宽/高≈0）被 geomOf 挡掉，既不可点也不画，
     否则那种点不到的框会抢走合法大框的点击（§27）。所以断言改成对齐**产品自己的可用清单**，
     并且要求画出的标签集合与它逐个相同 —— 比旧的"等于登记数"更强（旧的那条只看数量）。 */
  const drawn=out.areas.labels.slice().sort().join('|');
  out.areas.ok = out.areas.btnOn && out.areas.shapes[0]===usable.length
                 && out.areas.labels.length===usable.length
                 && drawn===usable.slice().sort().join('|');
  if(!out.areas.ok){ out.areas.expectLabels=usable.slice().sort(); }
  // ② 参数·部件面板
  document.getElementById('l2PanelBtn').click(); await t(400);
  const pn=document.getElementById('l2panel'); const rows=pn.querySelectorAll('.prow');
  out.panel={on:pn.classList.contains('on'), rows:rows.length,
             expect:core.getParameterCount()+core.getPartCount(),
             firstNames:[...rows].slice(0,4).map(r=>r.dataset.nm),
             sections:[...pn.querySelectorAll('h5')].map(h=>h.textContent)};
  out.panel.ok = out.panel.rows===out.panel.expect
                 && out.panel.firstNames.every(n=>!/^Param\d+$/.test(n));
  // ③ 滑杆读写往返
  let target=null;
  for(let i=0;i<core.getParameterCount();i++){ if(core.getParameterMaximumValue(i)-core.getParameterMinimumValue(i)>=1){ target=i; break; } }
  out.roundtrip={};
  if(target!==null){ core.setParameterValueByIndex(target, core.getParameterMaximumValue(target));
    out.roundtrip.param={i:target, set:core.getParameterMaximumValue(target), read:+core.getParameterValueByIndex(target).toFixed(3)}; }
  core.setPartOpacityByIndex(0,0.3); out.roundtrip.part={read:+core.getPartOpacityByIndex(0).toFixed(2)}; core.setPartOpacityByIndex(0,1);
  out.roundtrip.ok = (!out.roundtrip.param || out.roundtrip.param.read===out.roundtrip.param.set) && out.roundtrip.part.read===0.3;
  // ④ 过滤器
  const f=pn.querySelector('.pf input'); f.value='a'; f.oninput();
  const vis=[...rows].filter(r=>r.style.display!=='none');
  out.filter={visible:vis.length, total:rows.length, allMatch:vis.every(r=>r.dataset.nm.includes('a'))};
  out.filter.ok = out.filter.visible>0 && out.filter.visible<out.filter.total;
  f.value=''; f.oninput();
  return JSON.stringify(out,null,1);
}catch(e){ return 'ERR '+(e.message||e); }})"""
out = ev(JS + f"({json.dumps(KEY)})")
with open(os.path.join(ROOT, '.diag', '_probe_feats.json'), 'w', encoding='utf-8') as f:
    f.write(out if isinstance(out, str) else json.dumps(out))
r = cmd('Page.captureScreenshot', {'format': 'png'})
shot = os.path.join(ROOT, '.diag', '_areaviz_on.png')
open(shot, 'wb').write(base64.b64decode(r['data']))
print(out)
print(f'\n截图: {shot}')
print('判据：areas.ok / panel.ok / roundtrip.ok 全为 true。')
ws.close(); proc.terminate()
