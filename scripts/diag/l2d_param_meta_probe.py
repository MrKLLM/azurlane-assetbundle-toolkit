# -*- coding: utf-8 -*-
"""l2d_param_meta_probe.py — 从**运行时**读回 moc3 的逐参数量程与 `repeat` 回绕标志，
并在同一份页面上一笔笔验证「值超出量程时 Core / framework 各怎么处理」。四种模式：

  ① 默认：dump `.diag/_param_meta_<key>.json` = {参数名: [min, max, default, repeat]} 全表，
     并按 NEEDLES（逗号分隔）打印这些参数的标志行 —— `l2d_curve_shape.py` 的「越界」要靠这张表判语义。
  ② 扫值：给一串值，逐个 `setParameterValueByIndex` 写入后读回，判「硬钳到 max」还是「回绕」；
     `RAW=1` 改成直写 wasm 缓冲 `parameters.values[i]`（证明 Core 自己既不钳也不绕）。
  ③ `PARAM=@inrange`：**量程内恒等自检** —— 全部 repeat 参数 × 5 档（min / +25% / +50% / +99.9% / max）
     写入并读回，要求 0 失配。任何一处失配就说明补丁会动到不该动的写入（§123 就是靠它抓出
     「官方 ModF 把 val==max 折成 min」会打掉 75 个刻意钉在 max 的键点）。
  ④ `WATCH=1 [WATCH_SECS=110]`：在**真实播放路径**上把同一个函数包一层监视器，统计
     动作层交给 setter 的原始值（calls / maxIn / over）与接缝处的「传入→存值」实例。
     ⚠️ 判越界语义必须走这个模式——②③ 都是直写，绕过了动作求值。

用法: py -3 scripts/diag/l2d_param_meta_probe.py gezi_2 MB_wutixialuoxunhuangz 0 1 2 3 3.5 4.5
      py -3 scripts/diag/l2d_param_meta_probe.py gezi_2 @inrange
      WATCH=1 WATCH_SECS=110 py -3 scripts/diag/l2d_param_meta_probe.py gezi_2 MB_wutixialuoxunhuangz

API 实测（Cubism Core for Web 5.1 + pixi-live2d-display 0.4）：raw Model **没有 setParameterValue**，
写值只有 framework 的 `coreModel.setParameterValueByIndex(ix, val, weight)`；raw 缓冲在
`coreModel._model.parameters.{values,repeats,minimumValues,maximumValues,defaultValues,ids}`，
其中 `ids` 是**纯字符串数组**（不是 csmString 对象，按 `.string` 取会全部落空）。

踩坑：① 探针自带 http.server 并在开 Chrome 前轮询 200 —— 写死外部端口一旦没人起服务器，
  页面停在错误页，症状是「GALLERY is not defined」，会被误读成"前端被我改坏了"；
  ② 同 user-data-dir 的残留 Chrome 会让新实例开完标签就退出，DevTools 永远等不到；
  ③ 无头里 Ticker 对 dt 有上限，运动相位推进远慢于墙钟（实测约 3 帧/秒），
     WATCH 的窗口要按**墙钟**给到 100s 以上才够走到 11.25s 的接缝；合成时钟推不动，别试。
"""
import sys, os, json, time, base64, subprocess, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9391
PROFILE = os.path.join(ROOT, '.diag', 'chrome_sweep2')
os.makedirs(PROFILE, exist_ok=True)
SRV_PORT = int(os.environ.get('SRV_PORT', '8799'))
SRV = f'http://127.0.0.1:{SRV_PORT}/gallery_v2/index.html'
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(SRV_PORT),
                        '-b', '127.0.0.1', '-d', os.path.join(ROOT, 'Output')],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def kill_stale(profile_dir):
    """同 user-data-dir 的残留 chrome 会让新实例「开个标签就退出」，DevTools 端口永远等不到。"""
    ps = ("$ErrorActionPreference='SilentlyContinue';"
          "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
          "Where-Object { $_.CommandLine -like '*%s*' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % profile_dir)
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)


kill_stale(PROFILE)

KEY = sys.argv[1]
PARAM = sys.argv[2]
VALS = [float(x) for x in sys.argv[3:] if not x.startswith('--')]
NEEDLES = os.environ.get('NEEDLES', 'wutixialuo,wutijiaodugz,wutidaxiaogz,shiliang').split(',')

for _ in range(60):                      # 服务器没起来就开 Chrome，页面会停在错误页 → 「GALLERY is not defined」
    try:
        if urllib.request.urlopen(SRV, timeout=2).status == 200:
            break
    except Exception:
        time.sleep(0.5)
proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
  '--remote-allow-origins=*', f'--user-data-dir={PROFILE}', '--no-first-run',
  '--no-default-browser-check', '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
  '--use-angle=swiftshader', '--window-size=1280,900',
  SRV], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ws = None
for _ in range(90):
    try:
        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
        c = [t['webSocketDebuggerUrl'] for t in tabs if 'gallery_v2' in t.get('url', '')
             and t.get('webSocketDebuggerUrl')]
        if c:
            ws = websocket.create_connection(c[0], timeout=240, max_size=None); break
    except Exception:
        pass
    time.sleep(0.5)
_id = 0
def cmd(m, p=None):
    global _id; _id += 1; mid = _id
    ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}})); ws.settimeout(240)
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == mid:
            if 'error' in r: raise RuntimeError(json.dumps(r['error'])[:300])
            return r.get('result', {})
def ev(e):
    r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    if r.get('exceptionDetails'):
        return 'EVALERR ' + str(r.get('exceptionDetails'))[:400]
    return r.get('result', {}).get('value')
def ev_retry(e, tries=6):
    for k in range(tries):
        try:
            out = ev(e)
            if isinstance(out, str) and 'destroyed' in out:
                raise RuntimeError('context destroyed')
            return out
        except Exception as ex:
            print(f'  [重试 {k + 1}/{tries}] {str(ex)[:90]}')
            time.sleep(3.0)
            try:
                cmd('Page.enable'); ev('document.readyState')
            except Exception:
                pass
    raise RuntimeError('CDP 上下文反复失效')

JS_BOOT = r"""(async(key)=>{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<160 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
  if(!(window.GALLERY&&typeof openShip==='function')) return JSON.stringify({fail:'页面脚本没就绪',
     href:location.href, ready:document.readyState, title:document.title,
     hasRenderView:typeof renderView, body:(document.body&&document.body.innerText||'').slice(0,160)});
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key);
    if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({skip:'no skin '+key});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  const l2=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d');
  l2.click();
  const t0=performance.now();
  while(!l2State||!l2State.app||!l2State.app.stage.children.length){
    if(performance.now()-t0>40000) break; await t(200); }
  const mdl=l2State.app.stage.children[0], im=mdl.internalModel, core=im.coreModel;
  window.__S={app:l2State.app, core, mdl, im, raw:core._model, P:core._model.parameters};
  try{ im.motionManager.stopAllMotions(); }catch(e){}
  const P=window.__S.P;
  const ids=[]; for(let i=0;i<P.count;i++){ const s=P.ids[i];
    ids.push((typeof s==='string')? s : ((s&&s.string)||('Param#'+i))); }
  window.__S.ids=ids;
  const rpt=Array.from(P.repeats);
  const on= []; for(let i=0;i<rpt.length;i++) if(rpt[i]) on.push([ids[i], rpt[i]]);
  const pSrc=String(Object.getPrototypeOf(core).setParameterValueByIndex).slice(0,300);
  return JSON.stringify({n:P.count, repeatOnCount:on.length,
     patchLive:/repeats/.test(pSrc), patchSrc:pSrc,
     typesSample:Array.from(P.types.slice(0,8)),
     sampleBuf:Array.from(P.values.slice(0,4))});
})"""
print('BOOT →', ev_retry(JS_BOOT + f"({json.dumps(KEY)})"))

# —— ① repeat 标志逐参数（按 needle 过滤）
JS_REP = r"""(async(needles)=>{
  const {P,ids}=window.__S; const out=[];
  ids.forEach((nm,i)=>{ if(needles.some(n=>nm.includes(n)))
     out.push([nm, P.repeats[i], P.minimumValues[i], P.maximumValues[i],
               P.defaultValues[i], P.values[i], P.types[i]]); });
  return JSON.stringify(out);
})"""
rep = ev_retry(JS_REP + f"({json.dumps(NEEDLES)})")
print('\n① moc3 repeat 标志（name, repeat, min, max, default, 当前值, type）')
if isinstance(rep, str) and not rep.startswith('EVALERR'):
    for row in json.loads(rep):
        print('  ', row)
else:
    print('  ', rep)

JS_DUMP = r"""(()=>{
  const {P,ids}=window.__S; const out={};
  for(let i=0;i<P.count;i++) out[ids[i]]=P.values[i]===undefined? null :
     [P.minimumValues[i], P.maximumValues[i], P.defaultValues[i], P.repeats[i]];
  return JSON.stringify({key:%KEY%, count:P.count, meta:out});
})()""".replace('%KEY%', json.dumps(KEY))
meta = ev_retry(JS_DUMP)
if isinstance(meta, str) and not meta.startswith('EVALERR'):
    fp = os.path.join(ROOT, '.diag', f'_param_meta_{KEY}.json')
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(meta)
    md = json.loads(meta)
    nonempty = [k for k, v in md['meta'].items() if v and v[3]]
    print(f'\n①b 量程+repeat 全表 → {fp}（{md["count"]} 个参数，其中 repeat=1 共 {len(nonempty)} 个）')
else:
    print('\n①b repeat 全表 dump 失败:', str(meta)[:120])

JS_SET = r"""(async(p,v)=>{
  const {app,core,P}=window.__S;
  const i=window.__S.ids.indexOf(p);
  if(i<0) return {err:'param not in moc3', p};
  try{ window.__S.im.motionManager.stopAllMotions(); }catch(e){}
  const RAW = %RAWMODE%;
  if(RAW){ P.values[i]=v; }                      // 绕过 framework，直写 wasm 参数缓冲
  else { core.setParameterValueByIndex(i, v, 1.0); }
  const after_set=P.values[i];
  if(RAW){ window.__S.raw.update(); }            // 只跑 Core 自己的 update（含 repeat 归一）
  else { core.update(); }
  app.render();
  return {mode:RAW?'raw':'framework', idx:i, sent:v, after_set, after_update:P.values[i],
     repeat:P.repeats[i], min:P.minimumValues[i], max:P.maximumValues[i]};
})""".replace('%RAWMODE%', '1' if os.environ.get('RAW') == '1' else '0')
OUT = os.path.join(ROOT, '.diag', 'effect_scan', 'sweep')
os.makedirs(OUT, exist_ok=True)

# —— 量程内恒等自检：证明补丁对「没越界」的写入是恒等变换（零回退的写入路径级证据）
if PARAM == '@inrange':
    JS_ID = r"""(()=>{
      const {core,P}=window.__S; const ids=window.__S.ids; const bad=[]; let tested=0;
      const reps=[]; for(let i=0;i<P.count;i++) if(P.repeats[i]) reps.push(i);
      const pick=reps.concat(reps.slice(0,0));
      for(const i of pick){
        const mn=P.minimumValues[i], mx=P.maximumValues[i], sp=mx-mn;
        const cand=[mn, mn+sp*0.25, mn+sp*0.5, mn+sp*0.999, mx];
        for(const v of cand){
          core.setParameterValueByIndex(i, v, 1.0); tested++;
          const got=P.values[i];
          if(Math.abs(got-v) > 1e-4*Math.max(1,Math.abs(v)))
            bad.push([ids[i], v, +got.toFixed(5)]);
        }
      }
      return {repeatParams:reps.length, writes:tested, mismatches:bad.slice(0,12), nBad:bad.length};
    })()"""
    print("\n量程内恒等自检 →", json.dumps(ev_retry(JS_ID), ensure_ascii=False)[:900])
    ws.close()
    try:
        proc.terminate(); srv.terminate()
    except Exception:
        pass
    raise SystemExit(0)

# —— WATCH 模式：在**真实播放路径**上记录动作层交给 setter 的原始值，判死钳位在哪个层
if os.environ.get('WATCH'):
    JS_WATCH = r"""(async(p,secs)=>{
      const {core,im,P}=window.__S; const ids=window.__S.ids;
      try{ const mm=im.motionManager; mm.stopAllMotions&&mm.stopAllMotions();
           mm.update&&mm.update(0.001); mm.update&&mm.update(100000); }catch(e){}
      const ix=ids.indexOf(p); if(ix<0) return {err:'no param',p};
      const CP=Object.getPrototypeOf(core);
      const rec={calls:0,maxIn:-1e9,minIn:1e9,over:0,samples:[]};
      if(true){
        const base=CP.__origSet||CP.setParameterValueByIndex;
        CP.__origSet=base;
        CP.setParameterValueByIndex=function(i,v,w){
          if(i===ix){ rec.calls++; if(v>rec.maxIn)rec.maxIn=v; if(v<rec.minIn)rec.minIn=v;
            if(v>P.maximumValues[i]) rec.over++;
            if(rec.samples.length<400) rec.samples.push([+performance.now().toFixed(0), +v.toFixed(4),
                                                        +(P.values[i]).toFixed(4)]); }
          return base.call(this,i,v,w); };
        CP.__watcher=1;
      }
      try{ im.motionManager.startMotion('idle',0,PIXI.live2d.MotionPriority.FORCE); }catch(e){}
      // 无头里 rAF 被节流 + 运行时对 dt 有上限 ⇒ 动作时间跑得比墙钟慢得多，
      // 16 秒墙钟只走到曲线 4.6s 处，压根到不了越界区。用合成时钟按 30fps 推完整条 clip。
      const t0=performance.now();                      // 用真实墙钟：合成时钟推不动 pixi 的 dt 钳制
      while(performance.now()-t0 < secs*1000){
        try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
        await new Promise(r=>setTimeout(r,40));
      }
      CP.setParameterValueByIndex=CP.__origSet;      // 摘掉记录器，只留补丁本身
      rec.patchLive=/repeats/.test(String(CP.__origSet));
      rec.baseSrc=String(CP.__origSet).slice(0,170);
      return {ix, patchLive:rec.patchLive, baseSrc:rec.baseSrc,
              max:P.maximumValues[ix], min:P.minimumValues[ix], repeat:P.repeats[ix],
              storedNow:P.values[ix], calls:rec.calls, maxIn:+rec.maxIn.toFixed(4),
              minIn:+rec.minIn.toFixed(4), over:rec.over,
              first:rec.samples.slice(0,3), nearWrap:rec.samples.filter(s=>s[1]>2.9).slice(0,6),
              tail:rec.samples.slice(-6)};
    })"""
    d = ev_retry(JS_WATCH + f"({json.dumps(PARAM)}, {float(os.environ.get('WATCH_SECS','16'))})")
    print('\nWATCH →', json.dumps(d, ensure_ascii=False)[:1600])
    ws.close()
    try:
        proc.terminate(); srv.terminate()
    except Exception:
        pass
    raise SystemExit(0)
print(f'\n②/③ 参数 {PARAM} 扫值（写→core.update() 前/后读回）')
print(f'{"设定值":>9} {"写入后":>10} {"update后":>10}  {"量程":>13} repeat  判定')
rows = []
for v in VALS:
    d = ev_retry(JS_SET + f"({json.dumps(PARAM)}, {v})")
    if not isinstance(d, dict):
        print(f'{v:>9}  →  {d}'); continue
    if 'err' in d:
        print(f'{v:>9}  →  {d}'); continue
    rb = d['after_update']
    verdict = ('原值保留' if abs(rb - v) < 1e-6 else
               '硬钳到 max' if abs(rb - d['max']) < 1e-6 else
               '硬钳到 min' if abs(rb - d['min']) < 1e-6 else '回绕/其它')
    print(f'{v:>9.3f} {d["after_set"]:>10.4f} {rb:>10.4f}  [{d["min"]}, {d["max"]}] '
          f'{d["repeat"]:>6}   {verdict}')
    shot = cmd('Page.captureScreenshot', {'format': 'png'})
    tag = 'raw' if os.environ.get('RAW') == '1' else 'fw'
    fp = os.path.join(OUT, f'{PARAM}_{tag}_{v:g}.png')
    with open(fp, 'wb') as f:
        f.write(base64.b64decode(shot['data']))
    rows.append((v, rb, fp))
json.dump(rows, open(os.path.join(OUT, f'{PARAM}_sweep.json'), 'w'), ensure_ascii=False)
print('\n截图 →', OUT)
ws.close(); proc.terminate()
try:
    srv.terminate()
except Exception:
    pass
