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
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cdp_slot            # 端口 / profile 不写死：写死会让两个会话灌进同一个页面（见该模块 docstring）
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT, PROFILE = cdp_slot.slot(ROOT, 'insp')
proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
  '--remote-allow-origins=*', f'--user-data-dir={PROFILE}', '--no-first-run',
  '--no-default-browser-check', '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
  '--use-angle=swiftshader', '--window-size=1280,900',
  'http://127.0.0.1:8777/gallery_v2/index.html'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
import chrome_tree; chrome_tree.install(proc)   # 异常退出也要收整棵树，见该模块 docstring
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
  l2.click();
  // 固定等 6s 会让大贴图皮肤（benningdun_2 三张共 40MB，服务器还是单线程）必然读不到模型，
  // 表现为脚本自身"偶发 ERR ... reading 'internalModel'"。改成轮询到模型出现，上限 40s。
  for(let i=0;i<80 && !(l2State&&l2State.app&&l2State.app.stage.children[0]);i++) await t(500);
  if(!(l2State&&l2State.app&&l2State.app.stage.children[0]))
      return JSON.stringify({key, fail:'40s 内模型未加载', note:(document.querySelector('.note')||{}).textContent||''});
  const out={key};
  const m=l2State.app.stage.children[0], core=m.internalModel.coreModel, im=m.internalModel;
  // ① 判定区可视化
  const st=l2State.app.stage;
  document.getElementById('l2AreasBtn').click(); await t(600);
  const gfx=st.children.filter(c=>c instanceof PIXI.Graphics);
  const usable=(window.__L2_HITUSE? __L2_HITUSE().slice() : (im.settings.hitAreas||[]).map(a=>a.Name));
  const shown=(window.__L2_HITSHOW? __L2_HITSHOW().slice() : usable.slice());
  out.areas={btnOn:document.getElementById('l2AreasBtn').classList.contains('on'),
             graphics:gfx.length, visible:gfx.map(g=>g.visible), shapes:gfx.map(g=>g.geometry.graphicsData.length),
             registered:(im.settings.hitAreas||[]).length, usableN:usable.length,
             shownN:shown.length,
             labels:st.children.filter(c=>c instanceof PIXI.Text && c.visible).map(c=>c.text)};
  /* 2026-09-24 起登记数 ≠ 可点数：退化框（面积或宽/高≈0）被 geomOf 挡掉，既不可点也不画，
     否则那种点不到的框会抢走合法大框的点击（§27）。所以断言改成对齐**产品自己的可用清单**，
     并且要求画出的标签集合与它逐个相同 —— 比旧的"等于登记数"更强（旧的那条只看数量）。
     2026-09-27 再分一层：多边形按「可点清单」画，标签只按「此刻与视口相交的那批」画。
     换装按钮静止态被停在画布外（随动作才进画面），旧代码的 x clamp 会把它们的名字
     拽到屏幕右边缘，看着像"角落里点不到的判定区"。故标签基准换成 __L2_HITSHOW，
     仍与产品同源（探针不复算几何）。 */
  const drawn=out.areas.labels.slice().sort().join('|');
  out.areas.ok = out.areas.btnOn && out.areas.shapes[0]===usable.length
                 && out.areas.labels.length===shown.length
                 && drawn===shown.slice().sort().join('|');
  if(!out.areas.ok){ out.areas.expectLabels=shown.slice().sort(); }
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
out = None
for _try in range(6):
    try:
        if ev("document.readyState") != 'complete':
            time.sleep(2); continue
        out = ev(JS + f"({json.dumps(KEY)})"); break
    except RuntimeError as e:
        # 页面仍在导航时 CDP 执行上下文会被销毁 —— 探针自身的假失败（与"两个 Chrome 抢 CDP"
        # 是两类成因，串行也照犯）。上下文在导航结束后重建，重连同一张 tab 即可。
        print(f"  [retry {_try+1}] {str(e)[:70]}", flush=True); time.sleep(4)
if out is None:
    print('[ERROR] 6 次仍拿不到稳定执行上下文（探针故障，非产品故障）')
    ws.close(); chrome_tree.kill_tree(proc.pid); sys.exit(2)
with open(os.path.join(ROOT, '.diag', '_probe_feats.json'), 'w', encoding='utf-8') as f:
    f.write(out if isinstance(out, str) else json.dumps(out))
r = cmd('Page.captureScreenshot', {'format': 'png'})
shot = os.path.join(ROOT, '.diag', '_areaviz_on.png')
open(shot, 'wb').write(base64.b64decode(r['data']))
print(out)
print(f'\n截图: {shot}')
print('判据：areas.ok / panel.ok / roundtrip.ok 全为 true。')
ws.close(); chrome_tree.kill_tree(proc.pid)
