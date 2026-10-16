# -*- coding: utf-8 -*-
"""Live2D「播放中连点同一部位 → reserve 拒绝 → 不得误触发 snapHold」防回归探针（2026-10-16 修）。

背景（根因 II，2026-10-16）：旧实现 `mm.startMotion=(g,i,mode,opt)=>{ snapPending=true; ... }`
**无条件**置位 snapPending。但库的 startMotion 是 async：`yield loadMotion` 后才走
`state.start()`（内部 reserve() 对「同 group+index 正在播」直接 return false，见
Output/gallery_v2/vendor/live2d/pixi-live2d-display-cubism4.min.js），reserve 拒绝时
`_startMotion` 根本不会执行 —— 队列不重建、动作原地继续播。此时 snapPending 仍为 true ⇒
下一拍 beforeMotionUpdate 误判 changed ⇒ snapHold 把正在播动作的 Param27/Param25
钉回 clip 起点 0.7/0.5（持续淡化窗口 ~2s）⇒ 用户看到的「手势短暂错误 + 手消失」瞬态。
重播键那条路径（T2 stopAllMotions）修的是连点重播；本探针防的是连点部位。

修法：snapPending 置位移到真正起播的 `_startMotion` 重写里（gallery_src/index.html
1531 行附近），startMotion 包装器只保留快照键预载。reserve 拒绝 ⇒ _startMotion 不执行
⇒ snapPending 恒 false ⇒ beforeMotionUpdate changed=false ⇒ 不钉值，动作自然继续。

判据（行为层，不读内部变量）：
  A 阳性对照：起播 home 后整帧参数确实在动。
  B 起播后等到中段（P27 明显离开 clip 起点 0.7），记队列时钟与 P27。
  C 模拟「连点同一部位」：再次 mm.startMotion('home',0,3) —— 与产品 play() 的 motion
    语义完全一致（play 只多包一层 playVoice，语音播放与否不影响 reserve/snap；此处测的
    正是 reserve×snap 交互）。期望：被 reject（queue entry 未重建、startTime 不变）。
  D 关键：连点后 2s 内采样 P27 多次 ⇒ 必须持续自然波动（不被钉住）；且任意采样点
    不落入「接近 clip 起点 0.7」的平台（修复前会被钉在 ~0.7 长达 hold 窗口）。
  E 对照（不同部位切换仍要真起播）：改起播 touch_idle1（若皮肤有）⇒ queue 重建、
    startTime 重置 ⇒ snap 层照常工作（这本来就是设计行为，测回归不误伤）。

用法: py -3 scripts/diag/l2d_replay_reject_probe.py [皮肤key，默认 gezi_2]
退出码: 0 = 全过；1 = 有判据未过；2 = 探针没跑起来。
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "diag"))
sys.path.insert(0, os.path.join(ROOT, "gallery_src"))
import cdp_slot  # noqa: E402
import chrome_tree  # noqa: E402
import _gallery_server as GS  # noqa: E402

CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"

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
  const mm=im.motionManager;
  const P=core._model.parameters; if(!P||!P.count) return JSON.stringify({fail:'读不到参数缓冲'});
  const ids=core._parameterIds||[];
  const snap=()=>Array.from(P.values);
  const sp=i=>{ const a=P.maximumValues[i]-P.minimumValues[i]; return a>0?a:0; };
  const relDist=(a,b)=>{ let mx=0;
    for(let i=0;i<a.length;i++){ const s=sp(i); if(!s) continue;
      const d=Math.abs(a[i]-b[i])/s; if(d>mx) mx=d; }
    return +mx.toFixed(5); };
  const sel=document.getElementById('l2Motion');
  const pick=async g=>{ if(![...sel.options].some(o=>o.value===g)) return false;
    sel.value=g; sel.dispatchEvent(new Event('change')); await t(200); return true; };
  const out={key};
  const qSnap=()=>{ const arr=(mm.queueManager&&mm.queueManager._motions)||[];
    if(!arr.length) return {len:0};
    const e=arr[arr.length-1];
    return {len:arr.length, startTime:+(e._startTimeSeconds).toFixed(4),
            stateTime:+(e._stateTimeSeconds).toFixed(4)}; };
  const isP27=i=>ids[i]==='Param27';
  const isP25=i=>ids[i]==='Param25';
  const sample=()=>{ const v=snap(); const r={};
    v.forEach((x,i)=>{ if(isP27(i)) r.p27=+x.toFixed(4); if(isP25(i)) r.p25=+x.toFixed(4); });
    r.state=+(P.values.length?1:0); return r; };
  if(!await pick('home')) return JSON.stringify(Object.assign(out,{skip:'该皮肤没有 home 动作'}));
  await t(700); const Z=snap();
  await t(1500); const A=snap();
  out.prelude={moved:relDist(Z,A).mx};
  if(out.prelude.moved<0.01) return JSON.stringify(Object.assign(out,{fail:'起播后参数不动，对照无效'}));
  /* 等起播自带的 snapHold 自然过期（hold 窗口 ≈ fade 大者+0.2 ≈ 2.2s），再测连点。
     ⚠️ 不要用「P27 离开 0.7」当中段标志：gezi_2 的 home 曲线 P27 有长时间 0.7 平台段，
     本皮肤永远等不到离开 —— 判据必须落在 snapHold 本身（__snapDbg().held）。 */
  const heldOf=()=>{ try{ const d=window.__snapDbg&&window.__snapDbg();
      return (d&&Array.isArray(d.held))? d.held:[null]; }catch(e){ return [null]; } };
  let heldWait=0;
  for(let i=0;i<50;i++){ if(heldOf().length===0) break; await t(120); heldWait+=120; }
  const qBefore=qSnap();
  const before={held:heldOf(), q:qBefore, heldWait,
                p27:(sample().p27), p25:(sample().p25), state:1};
  const t0=performance.now();
  out.reject={before};
  /* —— 模拟连点同一部位：产品 play() 的 motion 语义（FORCE=3），此处专测 reserve×snap。
       库 startMotion 是 async：reserve 拒绝时 resolve false（state.start 未执行）——
       这个返回值就是「是否被拒」的最直接证据。 —— */
  let ok=null, okErr=null;
  try{ ok=await mm.startMotion('home',0,3); }catch(e){ okErr=String(e); }
  out.reject.ok=ok; out.reject.okErr=okErr;
  await t(120);
  out.reject.qAfter= qSnap();
  out.reject.heldAfter= heldOf();
  /* D：连点被拒后 snapHold 保持空（修复前这里会被误触发成非空 items），且参数继续自然走 */
  const trail=[];
  for(let i=0;i<6;i++){ const s=sample(); trail.push({t:Math.round(performance.now()-t0),
                                                       p27:s.p27, p25:s.p25,
                                                       st:qSnap().stateTime,
                                                       held:heldOf().length}); await t(220); }
  out.reject.trail=trail;
  const sameEntry = out.reject.qAfter.len===before.q.len &&
                    Math.abs(out.reject.qAfter.startTime-before.q.startTime)<1e-3;
  out.reject.reserveRejected = sameEntry;    /* 队列没重建 ⇒ 真被 reserve 拒了 */
  const noHoldAfter = out.reject.heldAfter.length===0 &&
                      trail.every(x=>x.held===0);
  /* ⚠️ 2026-10-16：「动作还在走」这条判据不能再拿 p25 变不变当标志 —— 那个会话把
     `snapMidGate` 扩到 `['Param25','Param27']` 后，这两个**多状态选择器**会被逐帧钉到状态值上，
     p25 在 0.44s 内可以合法地一直是 0.5（实测：本判据因此报假红灯）。
     改用队列时钟（stateTime）推进当"活着"的证据 —— 它与任何参数钉值都无关。 */
  const stillAlive = trail.some(x=> x.st!=null && Math.abs(x.st-trail[0].st)>1e-3);
  out.reject.pass = out.reject.reserveRejected && noHoldAfter && stillAlive;
  /* E：不同部位切换仍要真起播（回归不误伤 snap 层） */
  const alt=out;
  const other=['touch_idle1','touch_head','touch_body','touch_chest','touch_belly','touch_neck',
               'touch_leg','touch_hand','touch_arm','touch_ear','home','idle']
    .find(g=>g!=='home' && [...sel.options].some(o=>o.value===g));
  if(!other){ out.switchPass=false; out.explain='该皮肤只有 home，跳过切换对照'; }
  else{
    const q0=qSnap();
    try{ mm.startMotion(other,0,3); }catch(e){ out.switchErr=String(e); }
    await t(300);
    const q1=qSnap();
    out.switch={other, qBefore:q0, qAfter:q1};
    out.switchPass = q1.len>=1 && q1.startTime>q0.startTime+0.01;
  }
  out.pass = out.reject.pass && out.switchPass!==false;
  return JSON.stringify(out,null,1);
}catch(e){ return 'ERR '+(e.message||e)+' @ '+String(e.stack||'').split('\n')[1]; }})"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "gezi_2"
    port = free_port()
    httpd = GS.make_server(port=port, root=os.path.join(ROOT, "Output"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/gallery_v2/index.html?v={int(time.time())}"
    print(f"服务器（正本 _gallery_server）: {url}", flush=True)
    for _ in range(60):
        try:
            if urllib.request.urlopen(url, timeout=2).status == 200:
                break
        except Exception:
            time.sleep(0.3)
    dport, profile = cdp_slot.slot(ROOT, "rr")
    proc = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            f"--remote-debugging-port={dport}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            "--enable-unsafe-swiftshader",
            "--use-angle=swiftshader",
            "--window-size=1280,900",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    chrome_tree.install(proc)
    ws = None
    try:
        for _ in range(90):
            try:
                tabs = json.load(
                    urllib.request.urlopen(f"http://127.0.0.1:{dport}/json")
                )
                w = [
                    t["webSocketDebuggerUrl"]
                    for t in tabs
                    if "gallery_v2" in t.get("url", "")
                    and t.get("webSocketDebuggerUrl")
                ]
                if w:
                    import websocket

                    ws = websocket.create_connection(w[0], timeout=240, max_size=None)
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if ws is None:
            print("[ERROR 2] DevTools 连不上（残留 chrome 占了同一个 user-data-dir？）")
            chrome_tree.kill_tree(proc.pid)
            httpd.shutdown()
            return 2
        nid = [0]

        def cmd(method, params=None):
            nid[0] += 1
            ws.send(
                json.dumps({"id": nid[0], "method": method, "params": params or {}})
            )
            ws.settimeout(240)
            while True:
                r = json.loads(ws.recv())
                if r.get("id") == nid[0]:
                    if "error" in r:
                        raise RuntimeError(json.dumps(r["error"])[:150])
                    return r.get("result", {})

        def ev(expr):
            r = cmd(
                "Runtime.evaluate",
                {"expression": expr, "returnByValue": True, "awaitPromise": True},
            )
            if r.get("exceptionDetails"):
                return "EVALERR " + str(r.get("exceptionDetails"))[:300]
            return r.get("result", {}).get("value")

        cmd("Runtime.enable")
        time.sleep(1)
        res = ev(f"({JS})({json.dumps(key)})")
        out = json.loads(res) if isinstance(res, str) else res
        if not isinstance(out, dict):
            print("JS 异常返回:", str(out)[:500])
            return 2
        if out.get("err"):
            print("JS 错误:", out)
            return 2
        if out.get("skip"):
            print(f"[SKIP] {out.get('skip')}")
            return 0
        print(json.dumps(out, ensure_ascii=False, indent=1))
        if not out.get("pass"):
            print("\n[FAIL] 判据未过，以上是现场")
            return 1
        print("\n[PASS] 连点同部位被拒不误触发 snapHold；异部位切换仍正常")
        return 0
    finally:
        try:
            ws and ws.close()
        except Exception:
            pass
        chrome_tree.kill_tree(proc.pid)
        httpd.shutdown()


if __name__ == "__main__":
    sys.exit(main())
