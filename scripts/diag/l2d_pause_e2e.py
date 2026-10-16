# -*- coding: utf-8 -*-
"""Live2D「暂停」按钮的端到端验收：点真按钮 ⇒ 画面冻住 + 姿态存档真的落盘。

为什么要自己起一台服务器：这条判据要 `/l2d_freeze`，而 8777 上那台可能是别的会话按旧代码起的
（POST 只会拿到 501）⇒ 按 `_gallery_server.make_server(port, root)` 在空闲端口起一份，
不重启也不占用 8777（与 gallery_server_range_test.py 同一个理由）。

六条判据（每条可单独失败，探针自己的问题用 exit 2 和产品问题分开）：
  ① 播着动作时逐拍确实有变化（runMax>0，且至少跑到 3 拍）—— 阳性对照：不先证明"会动"，
     后面"不动"就没有意义（这条是本项目反复踩过的：拿一张静止页证明"冻住了"）
  ② 点「暂停」后 mdl.autoUpdate=false、按钮变「继续」、条上 class on
  ③ 暂停期间隔 400ms 连读两次完整参数向量**逐位相同**（drift=0），条上出现「已暂停 · <组> 第 N s」
  ④ 存档真的落在项目根 .diag/l2d_freeze/：文件名来自条上，字段齐、art 行数=counts.lit、
     且 flags.noRest 必须是 false（证明这份姿态来自产品原路径，不是探针自己搭的旁路）
  ⑤ 暂停期间 afterMotionUpdate ≤1 拍（库在 _render 里读 `deltaTime && update(...)`，
     点下去那一瞬可能已攒了半拍）
  ⑥ 点「继续」后按钮回到「暂停」、autoUpdate=true、参数向量又开始动
  ⑦ 恢复后的**第一拍**相对跳变 ≤ max(0.2, 3×runMax)
     —— 治的是"暂停期间 wall-clock 那三层（残留复位 / 环境层 / 开关钉住）继续爬，恢复瞬间姿态跳"。
     按「一拍对一拍」比而不是按秒，是因为 swiftshader 下模型只有 5~14 拍/秒，
     按固定毫秒数比会把物理与眨眼的正常位移也算成跳变（假阳性）。
  ⑧ 暂停中换动作 ⇒ 产品自己放开冻结（`play()` 里那一行；运行时自己回落 idle 不算用户意图，不许放开）
  ⑨ 残留复位渐变**在飞的时候**再测一遍 ③+⑦：这一层挂在 app.ticker 上、按 performance.now() 爬，
     是暂停期间唯一还会偷偷写参数的一层，必须单独测（渐变没装填上就判 FAIL，不许静默跳过）
  ⑩ 焦点停在「重播」按钮上按空格：只许暂停、不许把重播也点一次（产品里那句 blur()；
     必须用 CDP 发真键盘事件才测得到这条浏览器行为，页面里 dispatchEvent 测不到）
  ⑪ 再按一次空格放开冻结
  ⑫ 暂停后**画布仍有内容**（取图非空白、合法 PNG）
     —— 2026-10-15 前这条查的是"交出画布 PNG"（存档通道）；通道按用户要求摘掉后，
     判据换成它真正要保的东西：冻结态不是黑屏。

用法: py -3 scripts/diag/l2d_pause_e2e.py [皮肤key，默认 gez_2]
      判据 ⑨ 要换 antu_2 才装得出来（gezi_2 上它合法 SKIP，见下）。
退出码: 0 = 全过（SKIP 会明写在末行，不当成通过）；1 = 有判据未过；2 = 探针没跑起来。

⚠️ 2026-10-15 起「暂停」**不再存档**（`.diag/l2d_freeze/` 那条交接通道已按用户要求下线）：
   判据 ④ 由"存档落盘并可解析"改为"条上不含「存档」字样、且存档目录本轮不新增任何文件"。
"""
import base64
import json
import os
import socket
import io
import re
import subprocess
import sys
import threading
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, os.path.join(ROOT, 'gallery_src'))
import cdp_slot            # noqa: E402  端口/profile 不写死，见该模块 docstring
import chrome_tree         # noqa: E402  异常退出也要收整棵 chrome 树
import _gallery_server as GS   # noqa: E402

CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'

JS = r"""(async(key)=>{ try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<120 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
  if(!window.GALLERY || typeof openShip!=='function') return JSON.stringify({err:'页面脚本未就绪'});
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  [...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d').click();
  for(let i=0;i<80 && !(l2State&&l2State.app&&l2State.app.stage.children[0]);i++) await t(500);
  if(!(l2State&&l2State.app&&l2State.app.stage.children[0]))
      return JSON.stringify({key, fail:'40s 内模型未加载'});
  const m=l2State.app.stage.children[0], im=m.internalModel, core=im.coreModel;
  const P=core._model.parameters; if(!P||!P.count) return JSON.stringify({fail:'读不到参数缓冲'});
  const sp=i=>{ const a=P.maximumValues[i]-P.minimumValues[i]; return a>0?a:0; };
  const vec=()=>Array.from(P.values);
  /* 逐拍差：挂在 afterMotionUpdate 上（暂停期间根本不触发 ⇒ 恢复后的第一条就是"第一拍"）。
     记录的是**相对量程**，不同参数不同量程才可比。 */
  let prev=null; const rel=[]; const marks={}; const trace=[];
  im.on('afterMotionUpdate',()=>{ const v=vec();
    if(prev){ let mx=0; for(let i=0;i<v.length;i++){ const s=sp(i); if(!s) continue;
        const d=Math.abs(v[i]-prev[i])/s; if(d>mx) mx=d; } rel.push(+mx.toFixed(5)); }
    prev=v; });
  /* 走页面自己的入口挑一条真动作（不直接调 startMotion —— 那是本项目探针的老反模式，§123 追加-XXI）。
     用户报的是 home，暂停就该在 home 跑着的时候测。 */
  const sel=document.getElementById('l2Motion');
  if([...sel.options].some(o=>o.value==='home')){ sel.value='home';
    sel.dispatchEvent(new Event('change')); await t(1500); }
  await t(1200); marks.run0=rel.length; await t(1200); marks.run1=rel.length;
  const runRel=rel.slice(marks.run0, marks.run1);
  const out={key, params:P.count, runN:runRel.length,
             runMax:runRel.length?Math.max.apply(null,runRel):null};
  const pb=document.getElementById('l2Pause'), info=document.getElementById('l2PauseInfo');
  if(!pb||!info) return JSON.stringify(Object.assign(out,{fail:'没有 #l2Pause / #l2PauseInfo'}));
  pb.click(); await t(250);
  marks.paused=rel.length;
  out.atPause={autoUpdate:m.autoUpdate, label:pb.textContent,
               on:pb.classList.contains('on')};
  const vA=vec(); await t(400); const vB=vec();
  let drift=0, at=-1;
  for(let i=0;i<vA.length;i++){ const d=Math.abs(vA[i]-vB[i]); if(d>drift){ drift=d; at=i; } }
  out.frozen={drift:+drift.toFixed(6),
              driftParam:at>=0?String((core._parameterIds||[])[at]||at):null};
  /* 2026-10-15：暂停不再存档 ⇒ 不再轮询等文件名，直接把条上文案原样交出去，
     由 Python 侧断言它**不含**「存档」字样（判据 ④）。 */
  await t(400);
  out.pill=info.textContent||'';
  out.mentionsArchive=/存档/.test(out.pill);
  await t(1200);
  marks.preResume=rel.length;
  out.pauseRelCount=marks.preResume-marks.paused;
  pb.click(); await t(700);
  out.atResume={autoUpdate:m.autoUpdate, label:pb.textContent,
                on:pb.classList.contains('on'), pillHidden:info.style.display==='none'};
  const after=rel.slice(marks.preResume);
  out.jumpRel=after.length?+after[0].toFixed(5):null;
  out.resumeRelN=after.length;
  const vC=vec(); let moved=0;
  for(let i=0;i<vC.length;i++) moved+=Math.abs(vC[i]-vB[i]);
  out.movedAfterResume=+moved.toFixed(4);
  out.snapDbg=(window.__snapDbg?window.__snapDbg():null);
  const so=document.getElementById('l2Motion');
  const cg=()=>{ const s=l2State.app.stage.children[0].internalModel.motionManager.state;
    return (s && s.currentGroup) || '-'; };
  /* ⑧ 暂停中用户重新挑动作 ⇒ 产品自己放开冻结（play() 里那一行；运行时自己回落不算用户意图）。 */
  pb.click(); await t(250);
  out.playRelease={wasPaused:(m.autoUpdate===false), labelBefore:pb.textContent};
  /* ⑨ 唯一"暂停期间还会爬"的那层：残留复位 restTick 挂在 app.ticker 上、按 performance.now() 渐变。
     装填条件 = 刚播过一条非 idle 的 clip，而 currentGroup 已经是 idleGroup。
     ⚠️ 无头的模型时钟比墙钟慢（实测 ~3.75 拍/秒 × 每拍 deltaMS 只有几十毫秒 ⇒ 一条 18.25s 的 home
     要 80 秒墙钟才自然播完），所以这里分片调 `m.update(300)` 把**模型自己的时钟**推过去：
     每片之间让出主线程，走的还是那条 internalModel.update，不是另造一份时钟。
     推完仍没自然回落就改用下拉选 idle —— 那同样是页面自己的 play() 入口，不是绕过它。 */
  const ff=async sec=>{ let left=sec; while(left>0){ m.update(120); left-=0.12; await t(16);
      const r=window.__restDbg?__restDbg():null;         // 渐变只有 ~1.1 秒墙钟窗口，
      if(r){ trace.push(['推时钟途中回落:'+cg(), r.items, r.el]); return r; } }   // 必须在推的过程中抓
    return null; };
  const waitRest=async ms=>{ for(let i=0;i<Math.round(ms/200);i++){ await t(200);
      const r=window.__restDbg?__restDbg():null;
      trace.push([cg(), r?r.items:'-', r?r.el:'-']);
      if(r) return r; } return null; };
  out.restPass={clip:null, armed:false};
  try{
    for(const g of ['touch_idle1', 'touch_head', 'home']){
      if(![...so.options].some(o=>o.value===g)) continue;
      so.value=g; so.dispatchEvent(new Event('change'));
      if(!out.playRelease.clip){ out.playRelease.clip=g;
        out.playRelease.autoUpdateAfterPlay=(m.autoUpdate===true);
        out.playRelease.labelAfter=pb.textContent; }
      out.restPass.clip=g;
      let r=await ff(30);                                 // clip 自己播完 ⇒ 运行时回落 idle ⇒ 渐变在飞
      if(!r){ const idle=[...so.options].map(o=>o.value).find(v=>/^idle$/i.test(v));
        if(idle){ so.value=idle; so.dispatchEvent(new Event('change')); r=await waitRest(3000); } }
      if(r){ out.restPass.armed=true; out.restPass.dbg=r; break; }
    }
  }catch(e){ out.restPass.err=String(e&&e.message||e); }
  if(out.restPass.armed){
    const n0=rel.length; pb.click(); await t(300);
    const rvA=vec(); await t(1500); const rvB=vec();
    let rd=0; for(let i=0;i<rvA.length;i++) rd=Math.max(rd,Math.abs(rvA[i]-rvB[i]));
    out.restPass.driftWhilePaused=+rd.toFixed(6);
    out.restPass.updatesWhilePaused=rel.length-n0;
    const n1=rel.length; pb.click(); await t(900);
    const seg=rel.slice(n1);
    out.restPass.jump=seg.length?+seg[0].toFixed(5):null;
    out.restPass.resumeUpdates=seg.length;
  }
  out.restPass.trace=trace.slice(-16);
  return JSON.stringify(out,null,1);
}catch(e){ return 'ERR '+(e.message||e)+' @ '+String(e.stack||'').split('\n')[1]; }})"""


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else 'gez_2'
    port = free_port()
    httpd = GS.make_server(port=port, root=os.path.join(ROOT, 'Output'))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{port}/gallery_v2/index.html?v={int(time.time())}'
    print(f'服务器（正本 _gallery_server，带 /l2d_freeze）: {url}', flush=True)
    for _ in range(60):
        try:
            if urllib.request.urlopen(url, timeout=2).status == 200:
                break
        except Exception:
            time.sleep(0.3)
    dport, profile = cdp_slot.slot(ROOT, 'pause')
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={dport}',
                             '--remote-allow-origins=*', f'--user-data-dir={profile}',
                             '--no-first-run', '--no-default-browser-check',
                             '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
                             '--use-angle=swiftshader', '--window-size=1280,900', url],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(proc)
    ws = None
    for _ in range(90):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{dport}/json'))
            w = [t['webSocketDebuggerUrl'] for t in tabs
                 if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
            if w:
                import websocket
                ws = websocket.create_connection(w[0], timeout=240, max_size=None)
                break
        except Exception:
            pass
        time.sleep(0.5)
    if ws is None:
        print('[ERROR 2] DevTools 连不上（残留 chrome 占了同一个 user-data-dir？）')
        chrome_tree.kill_tree(proc.pid)
        httpd.shutdown()
        return 2
    nid = [0]

    def cmd(method, params=None):
        nid[0] += 1
        ws.send(json.dumps({'id': nid[0], 'method': method, 'params': params or {}}))
        ws.settimeout(240)
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == nid[0]:
                if 'error' in r:
                    raise RuntimeError(json.dumps(r['error'])[:150])
                return r.get('result', {})

    def ev(expr):
        r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True,
                                     'awaitPromise': True})
        if r.get('exceptionDetails'):
            return 'EVALERR ' + str(r.get('exceptionDetails'))[:300]
        return r.get('result', {}).get('value')

    def space():
        """CDP 发真键盘事件。页面里 dispatchEvent 测不到"焦点停在按钮上时空格会在 keyup
        再点一次那个按钮"这条浏览器行为 —— 而那正是产品里 blur() 要挡的那一下。"""
        for typ in ('keyDown', 'keyUp'):
            cmd('Input.dispatchKeyEvent', {'type': typ, 'code': 'Space', 'key': ' ',
                                           'windowsVirtualKeyCode': 32,
                                           'nativeVirtualKeyCode': 32})

    PAUSE_STATE = ("(()=>{const b=document.getElementById('l2Pause');"
                   "const m=l2State&&l2State.app&&l2State.app.stage.children[0];"
                   "return JSON.stringify({on:b.classList.contains('on'),label:b.textContent,"
                   "autoUpdate:m?m.autoUpdate:null})})()")

    bad = []
    SKIP = []

    def say(cond, msg):
        print(('  PASS  ' if cond else '  FAIL  ') + msg, flush=True)
        if not cond:
            bad.append(msg)

    try:
        # 2026-10-15：暂停**不再存档**（交接通道已按用户要求摘掉）⇒ 先给存档目录拍个快照，
        # 跑完比对"有没有新文件"，这是"真的没发"最直接的证据（比看代码可靠）。
        fdir = os.path.join(ROOT, '.diag', 'l2d_freeze')
        before_files = set(os.listdir(fdir)) if os.path.isdir(fdir) else set()
        raw = None
        for _try in range(6):
            if ev("document.readyState") != 'complete':
                time.sleep(2)
                continue
            raw = ev(JS + f"({json.dumps(key)})")
            break
        if raw is None or isinstance(raw, str) and not str(raw).strip().startswith('{'):
            print(f'[ERROR 2] 浏览器侧没跑通（探针故障）：{str(raw)[:300]}')
            return 2
        o = json.loads(raw)
        with open(os.path.join(ROOT, '.diag', '_l2d_pause_e2e.json'), 'w', encoding='utf-8') as f:
            json.dump(o, f, ensure_ascii=False, indent=1)
        print(json.dumps(o, ensure_ascii=False, indent=1), flush=True)

        say(o.get('runN', 0) >= 3 and (o.get('runMax') or 0) > 1e-4,
            f"① 播着动作时逐拍有变化：{o.get('runN')} 拍，最大相对位移 {o.get('runMax')}")
        ap = o.get('atPause') or {}
        say(ap.get('autoUpdate') is False and ap.get('label') == '继续' and ap.get('on') is True,
            f"② 点暂停：autoUpdate={ap.get('autoUpdate')} 按钮={ap.get('label')!r} class on={ap.get('on')}")
        fz = o.get('frozen') or {}
        say(fz.get('drift') == 0 and o.get('pill','').startswith('已暂停'),
            f"③ 暂停 400ms 里参数向量逐位相同：drift={fz.get('drift')}"
            f"（{fz.get('driftParam')}）· 条上「{o.get('pill','')[:48]}」")

        # ④ 暂停**不再存档**（2026-10-15 用户要求摘掉交接通道）。两条一起看：
        #    ① 条上文案不许出现「存档」字样；② 存档目录里不许多出任何文件。
        after_files = set(os.listdir(fdir)) if os.path.isdir(fdir) else set()
        new_files = sorted(after_files - before_files)
        say(not o.get('mentionsArchive') and not new_files,
            f"④ 暂停不再存档：条上含「存档」字样={o.get('mentionsArchive')} · "
            f"本轮新增文件 {len(new_files)} 个 {new_files[:3]}（都必须是 0）")
        prc = o.get('pauseRelCount')
        say(prc is not None and prc <= 1,
            f"⑤ 暂停期间 afterMotionUpdate 只走了 {prc} 拍（≤1：点暂停那一瞬可能已攒了半拍 deltaTime）")
        ar = o.get('atResume') or {}
        say(ar.get('autoUpdate') is True and ar.get('label') == '暂停'
            and (o.get('movedAfterResume') or 0) > 0,
            f"⑥ 点继续：autoUpdate={ar.get('autoUpdate')} 按钮={ar.get('label')!r} "
            f"· 之后累计位移 {o.get('movedAfterResume')}")
        run_max = o.get('runMax') or 0
        say(o.get('jumpRel') is not None and o.get('jumpRel') <= max(0.2, 3 * run_max),
            f"⑦ 恢复第一拍跳变 {o.get('jumpRel')} ≤ max(0.2, 3×正常拍 {run_max})")

        pr = o.get('playRelease') or {}
        say(pr.get('wasPaused') is True and pr.get('autoUpdateAfterPlay') is True
            and pr.get('labelAfter') == '暂停',
            f"⑧ 暂停中换动作 ⇒ 产品自己放开冻结：{pr}")
        rp = o.get('restPass') or {}
        if rp.get('armed'):
            say(rp.get('driftWhilePaused') == 0 and rp.get('jump') is not None
                and rp['jump'] <= max(0.2, 3 * run_max),
                f"⑨ 渐变在飞时冻住：drift={rp.get('driftWhilePaused')} · 暂停期间 "
                f"afterMotionUpdate {rp.get('updatesWhilePaused')} 拍 · 恢复第一拍 "
                f"{rp.get('jump')} ≤ {max(0.2, 3 * run_max):.4f}")
        else:
            # 装不出来 = restTick 里 items 为空就直接 return，rest 永远是 null（这块皮肤没有
            # 「非 idle 驱动而 idle 不动」的参数），或者它根本没回落。不是产品缺陷，但不许冒充测过。
            print(f"  SKIP  ⑨ 残留复位渐变没装出来（试过 clip={rp.get('clip')}，"
                  f"尾部现场 {rp.get('trace')}；err={rp.get('err')}）"
                  f" —— 要 exercise 这条换 antu_2 那类有残留参数的皮肤", flush=True)
            SKIP.append('⑨ 残留复位渐变（该皮肤没装出来）')

        # ⑩⑪ 空格快捷键：焦点停在「重播」按钮上按空格，浏览器会在 keyup 再把那条按钮点一次
        #     ——产品里那句 blur() 就是挡它的，必须用真键盘事件才测得到。
        ev("(()=>{const b=document.getElementById('l2Replay');window.__rep=0;"
           "b.addEventListener('click',()=>{window.__rep++;});b.focus();return 1})()")
        space()
        time.sleep(1.3)
        rep = ev("window.__rep")
        st1 = json.loads(ev(PAUSE_STATE))
        say(rep == 0 and st1['on'] is True and st1['autoUpdate'] is False
            and st1['label'] == '继续',
            f"⑩ 焦点在「重播」上按空格：只暂停、不重播（重播被点 {rep} 次）：{st1}")
        space()
        time.sleep(1.3)
        st2 = json.loads(ev(PAUSE_STATE))
        say(st2['on'] is False and st2['autoUpdate'] is True and st2['label'] == '暂停',
            f"⑪ 再按一次空格放开冻结：{st2}")

        # ⑫ 暂停要**真的冻在画面上**：2026-10-15 之前这条查的是"交出画布 PNG"（存档通道），
        #    通道摘掉后判据换成它真正要保的东西 —— 冻结态的画布**有内容**（不是被清空的黑图）。
        #    WebGL 不保留绘制缓冲 ⇒ 取图前必须同步 render 一次，否则拿到的是空白。
        ev("document.getElementById('l2Pause').click()")
        time.sleep(1.6)
        pill = ev("document.getElementById('l2PauseInfo').textContent") or ''
        durl = ev("(()=>{const a=l2State.app; try{ a.render(); return a.view.toDataURL('image/png'); }"
                  "catch(e){ return 'ERR '+(e.message||e); }})()")
        px_ok = blank = px = None
        if isinstance(durl, str) and durl.startswith('data:image/png;base64,'):
            raw = base64.b64decode(durl.split(',', 1)[1])
            try:
                from PIL import Image
                im = Image.open(io.BytesIO(raw)).convert('RGB')
                px = im.size
                px_ok = True
                blank = len(set(im.resize((64, 64)).getdata())) <= 2   # ≤2 种颜色 ⇒ 空白
            except Exception:
                px_ok = False
        say(px_ok and blank is False,
            f"⑫ 暂停后画布仍有内容：{px} 合法PNG={px_ok} 空白={blank} · 条上「{pill[:48]}」")
        ev("document.getElementById('l2Pause').click()")   # 放开，别把现场留在冻结态
    except Exception as e:
        print(f'[ERROR 2] 探针异常：{e}')
        return 2
    finally:
        try:
            ws.close()
        except Exception:
            pass
        chrome_tree.kill_tree(proc.pid)
        httpd.shutdown()
        httpd.server_close()

    print()
    if bad:
        print(f'[FAIL] {len(bad)} 条未过' + (f'（另有 {len(SKIP)} 条 SKIP）' if SKIP else ''))
        return 1
    print('[PASS] 暂停按钮端到端判据全过'
          + (f'；SKIP {len(SKIP)} 条：{SKIP}' if SKIP else '（无 SKIP）'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
