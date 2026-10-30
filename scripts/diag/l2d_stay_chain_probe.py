# -*- coding: utf-8 -*-
"""验证 Live2D「进入动作 → 循环停留 → 继续点击 → 切回默认」互动链。

默认样本只覆盖已核对末帧/首帧的 gezi_2 两条规则，不据此推断其他编号：
  py -3 scripts/diag/l2d_stay_chain_probe.py
  py -3 scripts/diag/l2d_stay_chain_probe.py --key gezi_2 --cases touch_idle12:idle12,touch_idle1:idle7

判据：真实下拉入口起播；进入动作完成后不经过基础 idle 而到目标；目标 _isLoop=true，
且完整越过一次 Duration 仍保持；停留中真实部位点击能触发候选动作；再选 idle 能回默认。
"""
import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import cdp_slot
import chrome_tree

CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
OUT = os.path.join(ROOT, ".diag", "l2d_stay_chain")


def free_port():
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="gezi_2")
    ap.add_argument("--cases", default="touch_idle12:idle12,touch_idle1:idle7")
    ap.add_argument("--control", default="benningdun_2")
    ap.add_argument("--full-loop", action="store_true", help="等待越过整个停留 Duration；默认只等 1.5 秒")
    a = ap.parse_args()
    cases = [tuple(x.split(":", 1)) for x in a.cases.split(",") if ":" in x]
    os.makedirs(OUT, exist_ok=True)
    srv_port = free_port()
    port, profile = cdp_slot.slot(ROOT, "staychain")
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(srv_port), "-b", "127.0.0.1",
                            "-d", os.path.join(ROOT, "Output")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = "http://127.0.0.1:%d/gallery_v2/index.html?v=%d" % (srv_port, time.time_ns())
    for _ in range(40):
        try:
            if urllib.request.urlopen(url, timeout=2).status == 200:
                break
        except Exception:
            time.sleep(.25)
    proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=%d" % port,
                             "--remote-allow-origins=*", "--user-data-dir=" + profile,
                             "--no-first-run", "--no-default-browser-check",
                             "--disable-background-timer-throttling", "--enable-unsafe-swiftshader",
                             "--use-angle=swiftshader", "--window-size=1100,1000", url],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    report = {"key": a.key, "cases": [], "control": None}
    ok = True
    try:
        import websocket
        for _ in range(80):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % port, timeout=2))
                hit = next((t for t in tabs if "gallery_v2" in t.get("url", "") and t.get("webSocketDebuggerUrl")), None)
                if hit:
                    ws = websocket.create_connection(hit["webSocketDebuggerUrl"], timeout=120)
                    break
            except Exception:
                pass
            time.sleep(.25)
        if ws is None:
            raise RuntimeError("CDP 未就绪")
        nid = [0]

        def cmd(method, params=None):
            nid[0] += 1
            ws.send(json.dumps({"id": nid[0], "method": method, "params": params or {}}))
            while True:
                m = json.loads(ws.recv())
                if m.get("id") == nid[0]:
                    if "error" in m:
                        raise RuntimeError(m["error"])
                    return m.get("result", {})

        def ev(expr):
            r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
            if r.get("exceptionDetails"):
                raise RuntimeError(str(r["exceptionDetails"])[:800])
            return r.get("result", {}).get("value")

        cmd("Page.enable")
        cmd("Runtime.enable")
        for _ in range(100):
            if ev("typeof GALLERY!=='undefined'&&typeof openShip==='function'&&typeof renderView==='function'") is True:
                break
            time.sleep(.2)

        def load(key):
            raw = ev("""(async()=>{const t=ms=>new Promise(r=>setTimeout(r,ms));const KEY=%s;
              try{if(typeof stopLive2D==='function')stopLive2D();}catch(e){}
              let ship=null,sk=null;
              for(const s of GALLERY.ships){const k=s.skins.find(x=>x.key===KEY);if(k&&s.live2dSkins.includes(KEY)){ship=s;sk=k;break;}}
              if(!sk)return JSON.stringify({fail:'no skin'});openShip(ship);setSkin(sk);buildSkinList(ship);tab='live2d';renderView();await t(12000);
              const app=l2State&&l2State.app,m=app&&app.stage.children[0];if(!m)return JSON.stringify({fail:'no model'});
              window.__m=m;window.__app=app;
              window.__chainState=()=>{const mm=window.__m.internalModel.motionManager,g=mm.state.currentGroup;
                const mo=(mm.motionGroups[g]||[])[0];return{group:g,loop:!!(mo&&mo._isLoop),reserved:mm.state.reservedGroup};};
              window.__chainSelect=(g)=>{const sel=document.getElementById('l2Motion');if(!sel)return{fail:'no selector'};
                if(!Array.from(sel.options).some(o=>o.value===g))return{fail:'no option '+g};sel.value=g;sel.onchange();return{ok:true};};
              const r=document.querySelector('#l2wrap canvas').getBoundingClientRect();window.__chainBox={x:r.left,y:r.top,width:r.width,height:r.height,scale:1};
              return JSON.stringify({ok:true,state:window.__chainState()});})()""" % json.dumps(key))
            info = json.loads(raw)
            if not info.get("ok"):
                raise RuntimeError(info)
            return info

        def state():
            return ev("window.__chainState()") or {}

        def select(group):
            r = ev("window.__chainSelect(%s)" % json.dumps(group))
            if not r or r.get("fail"):
                raise RuntimeError((group, r))

        def wait_group(target, timeout, entry=None):
            deadline = time.time() + timeout
            seen_entry = False
            unexpected_idle = False
            while time.time() < deadline:
                st = state()
                g = st.get("group")
                if entry and g == entry:
                    seen_entry = True
                if seen_entry and g == "idle" and target != "idle":
                    unexpected_idle = True
                if g == target and (target != "idle" or seen_entry or entry is None):
                    return st, {"seen_entry": seen_entry, "unexpected_idle": unexpected_idle}
                time.sleep(.12)
            return state(), {"seen_entry": seen_entry, "unexpected_idle": unexpected_idle, "timeout": True}

        def shot(name):
            data = cmd("Page.captureScreenshot", {"format": "png", "clip": ev("window.__chainBox")})
            path = os.path.join(OUT, name + ".png")
            open(path, "wb").write(base64.b64decode(data["data"]))
            return path

        def click_core(current_target):
            pt = ev("""(()=>{const m=window.__m,im=m.internalModel,c=im.coreModel,ppu=im.pixelsPerUnit||1;
              const wrap=document.getElementById('l2wrap'),r=wrap.getBoundingClientRect();
              for(const a of im.settings.hitAreas||[]){
                let ix=-1;try{ix=c.getDrawableIndex(a.Id)}catch(e){}if(ix<0)continue;const p=c.getDrawableVertexPositions(ix);
                if(!p||p.length<8)continue;let sx=0,sy=0,n=0;for(let k=0;k+1<p.length;k+=2){sx+=p[k];sy+=p[k+1];n++;}
                const vx=sx/n,vy=sy/n,cand=window.__L2_HITALL?__L2_HITALL(vx,vy):[];if(!cand.length)continue;
                const g=m.toGlobal(new PIXI.Point((vx+im.width/ppu/2)*ppu,(im.height/ppu/2-vy)*ppu));
                const x=r.left+g.x,y=r.top+g.y;if(x<r.left||x>r.right||y<r.top||y>r.bottom)continue;
                const opt={bubbles:true,cancelable:true,pointerId:1,clientX:x,clientY:y,button:0};
                wrap.dispatchEvent(new PointerEvent('pointerdown',opt));window.dispatchEvent(new PointerEvent('pointerup',opt));
                return{area:a.Name,cand,x,y};}
              return null;})()""")
            if not pt:
                return None, {"fail": "当前没有任何中心点可点击的判定区"}
            deadline = time.time() + 3
            played = None
            while time.time() < deadline:
                g = state().get("group")
                if g and g != "idle" and g != current_target:
                    played = g
                    break
                time.sleep(.1)
            return played, pt

        load(a.key)
        for entry, target in cases:
            mp = os.path.join(ROOT, "Output", "Live2D", a.key, "motion", target + ".motion3.json")
            dur = float(json.load(open(mp, encoding="utf-8"))["Meta"]["Duration"])
            select(entry)
            st, trace = wait_group(target, 18, entry=entry)
            rec = {"entry": entry, "target": target, "trace": trace, "arrived": st.get("group") == target,
                   "loop": st.get("loop") is True}
            if not rec["arrived"] or not rec["loop"] or trace.get("unexpected_idle"):
                rec["state"] = st
                report["cases"].append(rec)
                ok = False
                print("[FAIL]", rec, flush=True)
                continue
            wait_s = dur + 1.0 if a.full_loop else 1.5
            time.sleep(wait_s)
            st = state()
            rec["held_seconds"] = round(wait_s, 2)
            rec["held"] = st.get("group") == target
            rec["state_after_hold"] = st
            rec["stay_shot"] = shot(a.key + "_" + entry + "_stay")
            played, click = click_core(target)
            rec["click"] = click
            rec["click_played"] = played
            rec["click_ok"] = bool(played and played in (click.get("cand") or []))
            if played:
                rec["next_shot"] = shot(a.key + "_" + entry + "_next")
            select("idle")
            st, _ = wait_group("idle", 5, entry=played)
            rec["back_idle"] = st.get("group") == "idle" and st.get("loop") is True
            good = rec["held"] and rec["click_ok"] and rec["back_idle"]
            rec["ok"] = good
            ok = ok and good
            report["cases"].append(rec)
            print("[%s] %s → %s：保持 %.1fs=%s，继续点击=%s(%s)，回默认=%s" %
                  ("PASS" if good else "FAIL", entry, target, wait_s, rec["held"],
                   played, click.get("area"), rec["back_idle"]), flush=True)

        if a.control:
            load(a.control)
            select("touch_head")
            st, trace = wait_group("idle", 16, entry="touch_head")
            ctl = {"key": a.control, "returned_idle": st.get("group") == "idle" and trace.get("seen_entry"),
                   "state": st, "trace": trace}
            report["control"] = ctl
            ok = ok and ctl["returned_idle"]
            print("[%s] 对照 %s / touch_head 播完回基础 idle" %
                  ("PASS" if ctl["returned_idle"] else "FAIL", a.control), flush=True)
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        try:
            chrome_tree.kill_tree(proc.pid)
        except Exception:
            pass
        srv.terminate()
        shutil.rmtree(profile, ignore_errors=True)
    json.dump(report, open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("报告", os.path.join(OUT, "summary.json"), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
