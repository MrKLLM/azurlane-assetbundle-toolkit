# -*- coding: utf-8 -*-
"""l2d_motion_param_probe.py — 「播这条 clip，画面里那批参数到底动不动、动在哪块像素上」。

用途：判死"某个部件（花瓣/光量/飘带）是被哪条 clip 驱动的"。只看参数值不够——参数动了
也可能被 moc3 量程钳住、或它根本不映射到可见部件；只看截图也不够——呼吸会让全屏都在变。
所以三条一起出：
  ① 参数轨迹（含 moc3 合法量程，越量程会标 `钳位`）；
  ② 播这条 clip 前后两张截图的**变化像素数**；
  ③ 变化像素的**包围盒**（花瓣在画面边缘，包围盒能把它和"全身都在呼吸"区分开）。

用法: py -3 scripts/diag/l2d_motion_param_probe.py gezi_2 --clips idle,main_1,home \\
        --params '^(hxhb|uibh|Paramfh)'
输出: .diag/l2d_param_probe_shots/<model>_<clip>_{a,b}.png + 终端报告
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
PORT = 9342
SRV_PORT = 8794
DEBUG_DIR = os.path.join(ROOT, ".diag", "chrome_pprobe")
SHOTS = os.path.join(ROOT, ".diag", "l2d_param_probe_shots")
os.makedirs(SHOTS, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)

SAMPLES = 10
STEP_MS = 300


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
    ap.add_argument("--clips", default="idle,main_1,home")
    ap.add_argument("--params", default="^(hxhb|uibh|Paramfh)")
    ap.add_argument("--samples", type=int, default=SAMPLES,
                    help="采样次数；⚠️ 窗口必须盖过整条 clip——main_1 的 hxhb 要到 8.12s 才动，"
                         "采 3 秒会得到「这条 clip 不动花瓣」的假结论")
    ap.add_argument("--step", type=int, default=STEP_MS, help="采样间隔 ms")
    ap.add_argument("--dump", action="store_true",
                    help="把逐帧轨迹写进 .diag/l2d_param_probe_shots/<model>_<clip>_series.json，"
                         "供改前/改后逐样本比对（终端只有 min..max，看不出平台）")
    a = ap.parse_args()
    pat = re.compile(a.params)

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
    ws = websocket.create_connection(wait_ws(), timeout=90)
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
        if r.get("exceptionDetails"):
            return "EVALERR " + str(r["exceptionDetails"].get("exception", {}).get("description"))[:220]
        return r.get("result", {}).get("value")

    cmd("Page.enable"); cmd("Runtime.enable")
    for _ in range(80):
        if ev("typeof GALLERY!=='undefined' && typeof openShip==='function' "
              "&& typeof setSkin==='function' && typeof renderView==='function'") is True:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("页面脚本未就绪")

    js_load = """(async () => {
      const t=ms=>new Promise(r=>setTimeout(r,ms)); const KEY=%s;
      let ship=null, sk=null;
      for (const s of GALLERY.ships) { const k=s.skins.find(x=>x.key===KEY);
        if(k&&s.live2dSkins.includes(KEY)){ship=s;sk=k;break;} }
      if(!sk) return JSON.stringify({skip:'没有 '+KEY});
      openShip(ship); setSkin(sk); buildSkinList(ship); tab='live2d'; renderView();
      await t(9000);
      const app=l2State&&l2State.app; if(!app) return JSON.stringify({fail:'无 l2State'});
      const m0=app.stage.children[0]; if(!m0) return JSON.stringify({fail:'无模型'});
      window.__m=m0; window.__app=app;
      const core=m0.internalModel.coreModel;
      const acc=new Set(); let o=core;
      while(o && o!==Object.prototype){ Object.getOwnPropertyNames(o).forEach(n=>{
          if(/Param|index/i.test(n) && typeof core[n]==='function') acc.add(n); });
        o=Object.getPrototypeOf(o); }
      let npar=null; try{ npar=core.getParameterCount(); }catch(e){}
      return JSON.stringify({ok:true, accessors:[...acc].sort(), npar,
                             groups:Object.keys(m0.internalModel.motionManager.definitions||{})});
    })()""" % (json.dumps(a.model),)
    lr = json.loads(ev(js_load) or "{}")
    if not lr.get("ok"):
        print("[FAIL] 加载失败", lr)
        return 2
    print("模型 %s：%d 组动作；参数数 %s" % (a.model, len(lr["groups"]), lr.get("npar")))
    print("  coreModel 上参数相关访问器: %s" % ", ".join(lr.get("accessors") or []))
    # 候选参数名从**产物本身**取（motion3.json 的曲线 Id），不猜 coreModel 的内部字段名
    ids = set()
    mdir = os.path.join(ROOT, "Output", "Live2D", a.model, "motion")
    for fn in os.listdir(mdir):
        if not fn.endswith(".motion3.json"):
            continue
        for c in json.load(open(os.path.join(mdir, fn), encoding="utf-8")).get("Curves", []):
            if c.get("Target") != "Parameter":
                continue
            cid = c.get("Id")
            pid = cid if isinstance(cid, str) else (cid or {}).get("string")
            if pid and pat.search(pid):
                ids.add(pid)
    ids = sorted(ids)
    print("匹配参数 %d 个: %s" % (len(ids), ids[:14]))
    if not ids:
        print("  匹配到 0 个参数 ⇒ 判据落空，检查 --params")
        return 2

    for clip in [c for c in a.clips.split(",") if c]:
        js = """(async () => {
          const t=ms=>new Promise(r=>setTimeout(r,ms)); const CLIP=%s;
          const m=window.__m; const core=m.internalModel.coreModel;
          const mm=m.internalModel.motionManager;
          window.__ambOff=true;                       // 只测这一条 clip 自己，别把环境层混进来
          if(!(mm.definitions||{})[CLIP]) return JSON.stringify({skip:'无该组'});
          mm.startMotion(CLIP,0,PIXI.live2d.MotionPriority.FORCE);
          await t(1500);
          const ids=%s, series=ids.map(()=>[]), meta={};
          ids.forEach(id=>{ const o={};
            let ix=-1; try{ ix=core.getParameterIndex(id); }catch(e){}
            o.ix=ix;
            if(ix>=0){
              try{ o.min=core.getParameterMinimumValue(ix); }catch(e){}
              try{ o.max=core.getParameterMaximumValue(ix); }catch(e){}
              try{ o.def=core.getParameterDefaultValue(ix); }catch(e){}
            }
            meta[id]=o; });
          for(let k=0;k<%d;k++){
            try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
            try{ window.__app.render(); }catch(e){}
            ids.forEach((id,i)=>{ const ix=(meta[id]||{}).ix; let v=null;
              if(ix>=0){ try{ v=core.getParameterValueByIndex(ix); }catch(e){} }
              series[i].push(typeof v==='number'? +v.toFixed(3):null); });
            await t(%d);
          }
          return JSON.stringify({ids, series, meta, curGroup:(mm.state&&mm.state.currentGroup)||null});
        })()""" % (json.dumps(clip), json.dumps(ids), a.samples, a.step)
        r = json.loads(ev(js) or "{}")
        if r.get("skip"):
            print("\n-- %s: %s" % (clip, r["skip"])); continue
        moved = list(zip(r["ids"], r["series"]))
        series_dump = {}
        print("\n-- clip `%s`（currentGroup=%s）" % (clip, r.get("curGroup")))
        n_move = 0
        for i, s in moved:
            v = [x for x in s if isinstance(x, (int, float))]
            m = r["meta"].get(i) or {}
            if not v:
                print("   %-26s 运行时读不到 ⇒ 这个 Id 不在 moc3 参数表里 (getParameterIndex=%s)"
                      % (i, m.get("ix")))
                continue
            span = max(v) - min(v)
            if span > 1e-3:
                n_move += 1
            clamp = ""
            if m.get("max") is None or m.get("min") is None:
                shape = ""
            else:
                # 「触到量程」不等于「被钳死」：合法的曲线末帧也会刚好碰到 max。
                # 真正的失真特征是**在 max 上停一段平台**（moc3 repeat 参数被硬钳时的表现），
                # 以及锯齿回绕应有的**下降次数**（每循环一次下降一次）。
                mx, mn, span_q = m["max"], m["min"], (m["max"] - m["min"]) or 1.0
                run = best = 0
                for x in v:
                    run = run + 1 if abs(x - mx) <= 1e-3 * max(1.0, abs(mx)) else 0
                    best = max(best, run)
                hold_s = best * a.step / 1000.0
                drops = sum(1 for k in range(1, len(v)) if v[k] < v[k - 1] - 1e-3)
                shape = "  平台%.1fs/占%.0f%% 下降%d次" % (
                    hold_s, 100.0 * best / max(1, len(v)), drops)
                if best >= 3:
                    clamp = "  ← 被钳死在 max=%s（停 %.1fs）" % (m["max"], hold_s)
                elif max(v) >= mx - 1e-6:
                    clamp = "  ← 触到量程上沿"
                step_ = max(1, len(s) // 46)
                spark = "".join(" ▁▂▃▄▅▆▇█"[min(7, max(0, int(round((x - mn) / span_q * 7))))]
                                for x in v[::step_])
                shape += "  [" + spark + "]"
            print("   %-26s %+.3f..%+.3f  Δ=%.3f  量程[%s,%s]%s%s"
                  % (i, min(v), max(v), span, m.get("min"), m.get("max"), shape, clamp))
            if a.dump:
                series_dump[i] = {"meta": m, "series": s}
        print("   会动的参数 %d / %d" % (n_move, len(r["ids"])))
        if a.dump:
            fp = os.path.join(SHOTS, "%s_%s_series.json" % (a.model, clip))
            with open(fp, "w", encoding="utf-8") as fh:
                json.dump({"model": a.model, "clip": clip, "step_ms": a.step,
                           "sample_ms": 1500, "series": series_dump}, fh, ensure_ascii=False)
            print("   轨迹已落盘 →", fp)
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
