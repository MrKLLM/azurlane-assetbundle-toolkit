# -*- coding: utf-8 -*-
"""l2d_gallery_capture.py — 按固定帧率把画廊的 Live2D 抓成一串 PNG，交给
scripts/diag/l2d_motion_energy.py 与**游戏录像**做同一把尺子的比较。

为什么需要它：「动作僵硬/抽搐」是观感，观感不能当判据。游戏侧能量（录像逐帧差），
画廊侧也必须能量，两边用同一个脚本、同一组参数，才谈得上"像不像"。

⚠️ 无头 Chrome 的 rAF 被节流，所以每帧必须手动 `PIXI.Ticker.shared.tick(now)` + `app.render()`
   再截图 —— 不驱动的话抓到的一串全是同一帧，运动能量恒为 0，会得到"画廊完全静止"的假结论。
⚠️ **但抓出来的帧序列，时间轴不是帧号**：动作时间跟着**真实时间**走，而无头里每帧截图要 0.7~1.2 秒真实
   时间 ⇒ 帧号与模型时间脱钩 **7~34 倍**（实测 18.25s 的 clip 在 `--fps 30` 的**第 16 帧**就播完，后面
   500 多帧全是"动作结束后"的状态；据此得出的"某个姿势只持续 1.5 秒"全是仪器假象，§123 追加-XIX）。
   试过"自己造 `window.__tnow` 传给 `Ticker.tick()`" —— **不管用**，动作时间不由我们喂的 now 决定。
   正解已内置：逐帧记 `time.monotonic()` → `timeline.json` 第 3 列 = 相对首帧的**真实秒数**，
   收尾拿该 clip 的 `Param25` 曲线算"第一次到 0 的期望时刻"与这条轴比做**时间轴自证**；
   不 PASS 的帧不许用于时序判据（单帧目视仍可用）。`--fps` 只决定抓多少帧，不决定时间刻度。

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
    ap.add_argument("--clip", default="", help="抓之前用 FORCE 播这条 clip（如 home）；不给就按页面自己播的抓")
    ap.add_argument("--amb", choices=["yield", "mask", "off"], default="yield",
                    help="环境层三臂（A/B 对照用）：yield=只写 pose 不碰的参数（前端默认）；"
                         "mask=照源包整层盖住 pose；off=完全关掉环境层")
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
      window.__m=m0; window.__app=app;
      window.__ambOff=%s; window.__ambMask=%s;
      if(CLIPV){ try{ m0.internalModel.motionManager.startMotion(CLIPV,0,PIXI.live2d.MotionPriority.FORCE);
                    window.__clipStarted=true; }catch(e){ window.__clipErr=String(e); } }
      const cv=document.querySelector('#l2wrap canvas');
      const r=cv.getBoundingClientRect();
      window.__box=[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)];
      return JSON.stringify({ok:true, box:window.__box, pool:window.__poolDbg||null,
                             clip:CLIPV, clipStarted:!!window.__clipStarted, clipErr:window.__clipErr||null,
                             groups:Object.keys(m0.internalModel.motionManager.definitions||{}).length});
    })()""" % (json.dumps(a.model), json.dumps(a.amb == "off"), json.dumps(a.amb == "mask"))
    js = js.replace("CLIPV", json.dumps(a.clip or ""))
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
    n = int(a.secs * a.fps)
    # ⚠️ 无头抓帧的时间轴**不能用帧号**。实测（§123 追加-XIX）：动作时间跟着**真实时间**走，
    #    而每帧截图要 0.7~1.2 秒真实时间 ⇒ 帧号与模型时间脱钩 7~34 倍，18.25s 的 clip 在 `--fps 30`
    #    的第 16 帧就播完，后面全是"动作结束后"的状态。
    #    试过"自己造 window.__tnow 传给 Ticker.tick()" —— **不管用**：动作时间不由我们喂的 now 决定
    #    （自证直接报 FAIL，别再把这条路当修法）。正解：既然模型按真实时间推进，
    #    **每帧的墙钟间隔就是它的时间步长** ⇒ 逐帧记 time.monotonic()，时间轴 = 相对首帧的秒数；
    #    收尾拿该 clip 的 Param25 曲线算"第一次到 0 的期望时刻"与这条轴比 —— 自证不 PASS 的帧
    #    不许用于任何时序判据（单帧目视仍可用）。`--fps` 从此只决定"抓多少帧"，不决定时间刻度。
    t0 = time.monotonic()
    ev("window.__capTl=[]; 1")
    wall = [t0]
    for i in range(1, n + 1):
        ev("(async()=>{"
           "try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}"
           "try{ window.__app.render(); }catch(e){}"
           "let v=null; try{ const M=window.__m.internalModel.coreModel._model;"
           " const k=M.parameters.ids.indexOf('Param25'); if(k>=0) v=M.parameters.values[k]; }catch(e){}"
           "window.__capTl.push([%d,v]); return 1;})()" % i)
        r = cmd("Page.captureScreenshot", {"format": "png", "clip": {
            "x": info["box"][0], "y": info["box"][1],
            "width": info["box"][2], "height": info["box"][3], "scale": 1.0}})
        open(os.path.join(out, "f%03d.png" % i), "wb").write(base64.b64decode(r["data"]))
        wall.append(time.monotonic())
        if i % 12 == 0:
            print("  %d/%d" % (i, n), flush=True)
    tl = json.loads(ev("JSON.stringify(window.__capTl||[])") or "[]")
    rows = [[i, (tl[i][1] if i < len(tl) else None), round(wall[i] - t0, 4)] for i in range(n)]
    with open(os.path.join(out, "timeline.json"), "w", encoding="utf-8") as fh:
        json.dump({"model": a.model, "clip": a.clip, "fps_nominal": a.fps,
                   "axis": "第 3 列 = 相对首帧的真实秒数（= 模型时间轴；帧号不是时间）", "rows": rows}, fh)
    med = (wall[-1] - wall[0]) / max(1, n - 1)
    exp = obs = None
    try:
        mp = os.path.join(ROOT, "Output", "Live2D", a.model, "motion", "%s.motion3.json" % a.clip)
        seg = next((c["Segments"] for c in json.load(open(mp, encoding="utf-8"))["Curves"]
                    if c.get("Target") == "Parameter" and c.get("Id") == "Param25"), None)
        if seg:
            for j in range(0, len(seg) - 1, 3):
                if abs(seg[j + 1]) < 1e-6 and (j == 0 or abs(seg[j - 2]) > 1e-6):
                    exp = seg[j]; break
    except Exception as e:
        print("时间轴自证：算期望值失败 %s" % str(e)[:120])
    obs = next((w for _i, v, w in rows if v is not None and abs(v) < 1e-3), None)
    if exp is not None and obs is not None:
        ok = abs(obs - exp) <= max(0.5, 0.05 * float(exp))
        print("时间轴自证：每帧真实步长 %.3fs（按帧号当 1/%.0f 秒用会错 %.0f 倍）；"
              "Param25 第一次到 0 —— 期望 %.2fs  真实轴 %.2fs  ⇒ %s"
              % (med, a.fps, med * a.fps, exp, obs,
                 "PASS（时序判据请用 timeline.json 第 3 列，别用帧号）"
                 if ok else "**FAIL：真实轴也对不上，这批帧不许用于时序判据（只可用于单帧目视）**"))
    else:
        print("时间轴自证：缺期望值(%s) 或实测值(%s) ⇒ 未判定，按不可用于时序处理" % (exp, obs))
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
