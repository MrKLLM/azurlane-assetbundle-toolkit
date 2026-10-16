# -*- coding: utf-8 -*-
"""Live2D「重播中途打断」+「倍速标签点按回 1×」端到端验收（2026-10-16 修）。

背景（根因）：库 state.reserve() 对「同 group + 同 index」直接拒绝（"Motion is already
playing"，见 Output/gallery_v2/vendor/live2d/pixi-live2d-display-cubism4.min.js 里
`reserve(t,e,i){ if(t===this.currentGroup&&e===this.currentIndex) return false }`），旧实现
`l2Replay.onclick=()=>play(sel.value)` 在动作播完前点重播 ⇒ 动作原地不动、只有语音重播。
修法：重播键先 `try{ mm.stopAllMotions(); }catch(e){}`（内部 _stopAllMotions()+state.reset()，
state.reset() 清 currentGroup/currentIndex，reserve 不再拒绝）再 play(sel.value)。

⏱ 时钟策略：**全部走页面自然 ticker + 墙钟等待**。无头 swiftshader 下模型时钟比墙钟慢
（实测 ~3.75 拍/秒），但确实在走；不要用 m.update(120) 手推——本探针 v2 实测它推不动
（单拍参数变化 0），会把"动作真的重新起播了"误判成"冻住了"（假阴性）。

判据（全部走产品真入口，不直接调 startMotion —— 那是本项目探针的老反模式，见 §123 追加-XXI）：
  A 阳性对照：起播 home 后等一等，整帧参数确实在动（不然后面"冻住/没冻住"没有意义）
  B 重播后接近起点：先记「起播后立即」快照 Z（≈0s 处），再记「播了 2s」快照 A；
    点「重播」按钮后隔一小会儿记 B ⇒ B 应更接近 Z（= 真的从头起播）而不是 A（= 旧 bug：原地不动）
  C 重播后仍在走：点完再等 1.5s，参数继续变化（没被 stopAllMotions 掐死在空队列）
  D 倍速：拖滑杆到 2× ⇒ l2Speed=2、显示 2.0×、滑杆回显 2
  E 点「倍速」文字标签（新功能）⇒ 一键回 1×，滑杆 + 数值 + 内部 l2Speed 三者一致
  F 点倍率数字 1.0× 依旧回 1×（旧功能不回归）

用法: py -3 scripts/diag/l2d_replay_speed_e2e.py [皮肤key，默认 gezi_2]
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
  const sp=i=>{ const a=P.maximumValues[i]-P.minimumValues[i]; return a>0?a:0; };
  const snap=()=>Array.from(P.values);
  const relDist=(a,b)=>{ let mx=0, at=-1;
    for(let i=0;i<a.length;i++){ const s=sp(i); if(!s) continue;
      const d=Math.abs(a[i]-b[i])/s; if(d>mx){ mx=d; at=i; } }
    return {mx:+mx.toFixed(5), at:at>=0?String((core._parameterIds||[])[at]||at):null}; };
  const sel=document.getElementById('l2Motion');
  const pick=g=>{ if(![...sel.options].some(o=>o.value===g)) return false;
    sel.value=g; sel.dispatchEvent(new Event('change')); return true; };
  const st=()=>{ const s=mm.state||{}; return {group:s.currentGroup, index:s.currentIndex}; };
  const out={key, hasStopAll: typeof mm.stopAllMotions==='function'};
  if(!pick('home')) return JSON.stringify(Object.assign(out,{skip:'该皮肤没有 home 动作'}));
  /* Z：起播后等几拍（无头 ticker 慢，用墙钟等） */
  await t(700); const Z=snap();
  await t(1500); const A=snap();
  out.prelude={moved:relDist(Z,A).mx, stateNow:st()};
  /* 队列快照：queueManager._motions 里第一个在播 entry 的时钟（根因层判据，不碰参数距离） */
  const qSnap=()=>{ const arr=(mm.queueManager&&mm.queueManager._motions)||[];
    if(!arr.length) return {len:0};
    const e=arr[arr.length-1];
    return {len:arr.length, startTime:+(e._startTimeSeconds).toFixed(4),
            stateTime:+(e._stateTimeSeconds).toFixed(4), finished:e._finished}; };
  /* —— T2：点「重播」（产品真按钮） ——
     根因层判据：旧 bug 时 reserve 拒绝 ⇒ startMotion 直接 return false、队列 entry 不动
     （startTime 不变、动作继续原地播）；修复后 stopAllMotions 清 state ⇒ reserve 放行 ⇒
     队列重建新 entry，startTime 重置为当前模型时钟（= 真正从头起播）。 */
  const rp=document.getElementById('l2Replay');
  if(!rp) return JSON.stringify(Object.assign(out,{fail:'没有 #l2Replay'}));
  const st0=st(); const q0=qSnap();
  rp.click(); await t(400);
  const st1=st(); const q1=qSnap();
  await t(1000);
  const q2=qSnap();
  out.replay={before:st0, after:st1,
    qBefore:q0, qAfterClick:q1, qAfterWait:q2};
  out.replay.pass = out.hasStopAll && q1.len>=1 && q2.len>=1 &&
                    q1.startTime>q0.startTime &&          /* 队列条目被重建（时钟重置） */
                    q2.stateTime>q1.stateTime &&          /* 新动作在播（没被掐死） */
                    st1.group===st0.group;                 /* 没切到别的组 */
  /* —— T3：倍速滑杆 + 标签点按 —— */
  const spd=document.getElementById('l2Speed'), val=document.getElementById('l2SpeedVal'),
        lab=document.getElementById('l2SpeedLabel');
  const dbg=()=>{ const d=(window.__speedDbg?window.__speedDbg():{});
      return {speed:d.speed, label:val?val.textContent:null, slider:spd?spd.value:null}; };
  const speed={};
  if(spd && val && lab){
    spd.value='2'; spd.dispatchEvent(new Event('input')); await t(50);
    speed.to2x=dbg();
    lab.click(); await t(50);                     /* ★ 点「倍速」文字标签 = 新功能 */
    speed.afterLabelClick=dbg();
    spd.value='2'; spd.dispatchEvent(new Event('input')); await t(50);
    speed.to2xAgain=dbg();
    val.click(); await t(50);                     /* 旧功能：点倍率数字 */
    speed.afterValClick=dbg();
    const ok=v=>v.speed===1 && v.label==='1.0×' && v.slider==='1';
    speed.pass = speed.to2x.speed===2 &&
                 ok(speed.afterLabelClick) && ok(speed.afterValClick) &&
                 !!lab.getAttribute('title');
  } else speed.pass=false;
  out.speed=speed;
  out.pass = out.replay.pass && out.speed.pass;
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
    dport, profile = cdp_slot.slot(ROOT, "rs")
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
        print("\n[PASS] 重播中途打断 + 倍速标签点按回 1× 全部通过")
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
