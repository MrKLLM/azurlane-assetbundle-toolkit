# -*- coding: utf-8 -*-
"""l2d_gallery_capture.py — 按固定帧率把画廊的 Live2D 抓成一串 PNG，交给
scripts/diag/l2d_motion_energy.py 与**游戏录像**做同一把尺子的比较。

为什么需要它：「动作僵硬/抽搐」是观感，观感不能当判据。游戏侧能量（录像逐帧差），
画廊侧也必须能量，两边用同一个脚本、同一组参数，才谈得上"像不像"。

⚠️ 无头 Chrome 的 rAF 被节流，所以每帧必须手动 `PIXI.Ticker.shared.tick(now)` + `app.render()`
   再截图 —— 不驱动的话抓到的一串全是同一帧，运动能量恒为 0，会得到"画廊完全静止"的假结论。

用法: py -3 scripts/diag/l2d_gallery_capture.py gezi_2 --fps 6 --secs 10
输出: .diag/gallery_vid/<model>/f###.png
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
PORT = 9344
SRV_PORT = 8796
DEBUG_DIR = os.path.join(ROOT, ".diag", "chrome_capture")


def kill_stale_chrome(user_data_dir):
    ps = ("$ErrorActionPreference='SilentlyContinue';"
          "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
          "Where-Object { $_.CommandLine -like '*%s*' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % user_data_dir)
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--fps", type=int, default=6)
    ap.add_argument("--secs", type=int, default=10)
    ap.add_argument("--out", default="")
    ap.add_argument("--no-mask", action="store_true",
                    help="关掉环境层对 pose 参数的覆盖（A/B 用），默认按源包覆盖")
    a = ap.parse_args()
    out = a.out or os.path.join(ROOT, ".diag", "gallery_vid", a.model)
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        os.remove(os.path.join(out, f))

    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(SRV_PORT),
                            "-b", "127.0.0.1", "-d", os.path.join(ROOT, "Output")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    kill_stale_chrome(DEBUG_DIR)
    url = "http://127.0.0.1:%d/gallery_v2/index.html" % SRV_PORT
    for _ in range(40):
        try:
            if urllib.request.urlopen(url, timeout=2).status == 200:
                break
        except Exception:
            time.sleep(0.5)
    proc = subprocess.Popen([
        CHROME, "--headless=new", "--remote-debugging-port=%d" % PORT,
        "--remote-allow-origins=*", "--user-data-dir=%s" % DEBUG_DIR,
        "--no-first-run", "--no-default-browser-check",
        "--disable-background-timer-throttling", "--enable-unsafe-swiftshader",
        "--use-angle=swiftshader", "--window-size=900,900", url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def wait_ws():
        for _ in range(60):
            try:
                for t in json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % PORT)):
                    if "gallery_v2" in t.get("url", "") and t.get("webSocketDebuggerUrl"):
                        return t["webSocketDebuggerUrl"]
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError("CDP 未就绪")

    import websocket
    ws = websocket.create_connection(wait_ws(), timeout=120)
    nid = [0]

    def cmd(method, params=None):
        nid[0] += 1
        ws.send(json.dumps({"id": nid[0], "method": method, "params": params or {}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == nid[0]:
                if "error" in m:
                    raise RuntimeError(json.dumps(m["error"])[:200])
                return m.get("result", {})

    def ev(expr):
        r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")

    cmd("Page.enable"); cmd("Runtime.enable")
    for _ in range(80):
        if ev("typeof GALLERY!=='undefined' && typeof openShip==='function'") is True:
            break
        time.sleep(0.5)
    js = """(async () => {
      const t=ms=>new Promise(r=>setTimeout(r,ms)); const KEY=%s;
      let ship=null, sk=null;
      for (const s of GALLERY.ships) { const k=s.skins.find(x=>x.key===KEY);
        if(k&&s.live2dSkins.includes(KEY)){ship=s;sk=k;break;} }
      if(!sk) return JSON.stringify({skip:'没有 '+KEY});
      openShip(ship); setSkin(sk); buildSkinList(ship); tab='live2d'; renderView();
      await t(12000);
      const app=l2State&&l2State.app; if(!app) return JSON.stringify({fail:'无 l2State'});
      const m0=app.stage.children[0]; if(!m0) return JSON.stringify({fail:'无模型'});
      window.__m=m0; window.__app=app; window.__ambNoMask=%s;
      const cv=document.querySelector('#l2wrap canvas');
      const r=cv.getBoundingClientRect();
      window.__box=[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)];
      return JSON.stringify({ok:true, box:window.__box, pool:window.__poolDbg||null,
                             groups:Object.keys(m0.internalModel.motionManager.definitions||{}).length});
    })()""" % (json.dumps(a.model), "true" if a.no_mask else "false")
    info = json.loads(ev(js) or "{}")
    print("装载:", {k: v for k, v in info.items() if k != "box"})
    pw = (info.get("pool") or {}).get("poolW") or []
    pg = (info.get("pool") or {}).get("poolGroups") or []
    if pw:
        tot = sum(pw) or 1
        print("  实际权重（可见位移/秒 → 抽中概率）: " + ", ".join(
            "%s %.0f(%.0f%%)" % (g, w, 100.0 * w / tot) for g, w in zip(pg, pw)))
    if not info.get("ok"):
        for p in (proc, srv):
            try:
                p.terminate()
            except Exception:
                pass
        return 2
    step = 1.0 / a.fps
    n = int(a.secs * a.fps)
    for i in range(1, n + 1):
        ev("(async()=>{ const t=ms=>new Promise(r=>setTimeout(r,ms));"
           "try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}"
           "try{ window.__app.render(); }catch(e){} return 1;})()")
        r = cmd("Page.captureScreenshot", {"format": "png", "clip": {
            "x": info["box"][0], "y": info["box"][1],
            "width": info["box"][2], "height": info["box"][3], "scale": 1.0}})
        open(os.path.join(out, "f%03d.png" % i), "wb").write(base64.b64decode(r["data"]))
        time.sleep(step)
        if i % 12 == 0:
            print("  %d/%d" % (i, n), flush=True)
    try:
        ws.close()
    except Exception:
        pass
    for p in (proc, srv):
        try:
            p.terminate()
        except Exception:
            pass
    kill_stale_chrome(DEBUG_DIR)
    print("已抓 %d 帧 → %s" % (n, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
