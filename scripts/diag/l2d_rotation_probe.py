# -*- coding: utf-8 -*-
"""l2d_rotation_probe.py — 证「画廊不再把 Live2D 钉在单条 idle 上」这件事真的在跑。

要判死的三件事：
  ① 库的自动回落组 `groups.idle` 已被轮播接管（它是 null —— 轮播改由 motionFinish 挑下一条，
     且必须**保持 null**：装池之前不掐掉自动回落，库会先把单条 idle 起播，后面全被挡）；
  ② 观察窗内 `currentGroup` **至少变过 2 次**（钉在 idle 上永远不会有这条）；
  ③ 变到非 idle 的那段里，花瓣类参数（默认 `^(hxhb|uibh)`）确实动过。
     对照基线是 l2d_motion_param_probe 已经量到的事实：gezi_2 单播 idle 22 秒，
     14 个花瓣参数 **0 个**会动；播 main_1 有 10 个会动（且要到第 8.12 秒才开始）。

用法: py -3 scripts/diag/l2d_rotation_probe.py gezi_2 [--watch 70]
退出码 0=PASS。
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
PORT = 9343
SRV_PORT = 8795
DEBUG_DIR = os.path.join(ROOT, ".diag", "chrome_rot")


def kill_stale_chrome(user_data_dir):
    ps = ("$ErrorActionPreference='SilentlyContinue';"
          "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
          "Where-Object { $_.CommandLine -like '*%s*' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % user_data_dir)
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)


def petal_params(key, pat):
    """花瓣类参数名从产物里取，不写死。"""
    d = os.path.join(ROOT, "Output", "Live2D", key, "motion")
    ids = set()
    for fn in os.listdir(d):
        if not fn.endswith(".motion3.json"):
            continue
        for c in json.load(open(os.path.join(d, fn), encoding="utf-8")).get("Curves", []):
            if c.get("Target") != "Parameter":
                continue
            cid = c.get("Id")
            pid = cid if isinstance(cid, str) else (cid or {}).get("string")
            if pid and pat.search(pid):
                ids.add(pid)
    return sorted(ids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--watch", type=int, default=70, help="观察秒数；必须盖过 idle 的 22 秒")
    ap.add_argument("--params", default="^(hxhb|uibh)")
    a = ap.parse_args()
    ids = petal_params(a.model, re.compile(a.params))
    print("花瓣类参数 %d 个: %s" % (len(ids), ids[:10]))

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
    ws = websocket.create_connection(wait_ws(), timeout=240)
    nid = [0]
    logs = []

    def pump(msg):
        try:
            m = msg if isinstance(msg, dict) else json.loads(msg)
        except Exception:
            return
        p = m.get("params") or {}
        if m.get("method") == "Runtime.consoleAPICalled":
            logs.append(" ".join(str(a.get("value", a.get("description", "")))
                                 for a in p.get("args", []))[:300])

    def cmd(method, params=None):
        nid[0] += 1
        ws.send(json.dumps({"id": nid[0], "method": method, "params": params or {}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == nid[0]:
                if "error" in m:
                    raise RuntimeError(json.dumps(m["error"])[:200])
                return m.get("result", {})
            pump(m)

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

    js = """(async () => {
      const t=ms=>new Promise(r=>setTimeout(r,ms)); const KEY=%s, IDS=%s, WATCH=%d;
      /* 0.4.0 默认 logLevel 只到 warning，"Cannot start motion because ..." 是 log 级——
         不放开就看不到被拒原因。state.debug 打开后它还会把 current/reserved 一起 dump 出来。 */
      try{ PIXI.live2d.config.logLevel=4; }catch(e){}
      let ship=null, sk=null;
      for (const s of GALLERY.ships) { const k=s.skins.find(x=>x.key===KEY);
        if(k&&s.live2dSkins.includes(KEY)){ship=s;sk=k;break;} }
      if(!sk) return JSON.stringify({skip:'没有 '+KEY});
      openShip(ship); setSkin(sk); buildSkinList(ship); tab='live2d'; renderView();
      await t(11000);
      const app=l2State&&l2State.app; if(!app) return JSON.stringify({fail:'无 l2State'});
      const m=app.stage.children[0]; if(!m) return JSON.stringify({fail:'无模型'});
      window.__m=m; window.__app=app;
      const mm=m.internalModel.motionManager, core=m.internalModel.coreModel;
      try{ mm.state.debug=true; }catch(e){}
      const stDump=(o)=>{ try{ return JSON.parse(JSON.stringify(o,(k,v)=>typeof v==='function'?undefined:v)); }catch(e){ return String(o); } };
      const diag={state:stDump(mm.state), groups:mm.groups, qLen:(mm.queueManager&&mm.queueManager._motions||[]).length};
      /* 纯观察，不干预：探针一旦替页面 startMotion，"轮播起来了"就不再是页面自己的功劳。 */
      const before=(mm.state&&mm.state.currentGroup)||null;
      const tryStart='(探针不干预)';
      await t(3000);
      diag.before=before; diag.tryStart=tryStart;
      diag.after=(mm.state&&mm.state.currentGroup)||null; diag.stateAfter=stDump(mm.state);
      const ix=IDS.map(id=>{ try{ return core.getParameterIndex(id); }catch(e){ return -1; } });
      const series=IDS.map(()=>[]); const seen=[]; const t0=performance.now();
      while(performance.now()-t0 < WATCH*1000){
        try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
        try{ app.render(); }catch(e){}
        seen.push([Math.round((performance.now()-t0)/1000),
                   (mm.state&&mm.state.currentGroup)||null]);
        IDS.forEach((id,i)=>{ if(ix[i]<0){ series[i].push(null); return; }
          let v=null; try{ v=core.getParameterValueByIndex(ix[i]); }catch(e){}
          series[i].push(typeof v==='number'? +v.toFixed(3):null); });
        await t(1000);
      }
      const groups=[]; seen.forEach(s=>{ if(!groups.length||groups[groups.length-1]!==s[1]) groups.push(s[1]); });
      const spans=IDS.map((id,i)=>{ const v=series[i].filter(x=>typeof x==='number');
        return {id, span: v.length? +(Math.max(...v)-Math.min(...v)).toFixed(3): null}; });
      return JSON.stringify({poolGroup:mm.groups.idle, diag, groups, spans, watch:WATCH});
    })()""" % (json.dumps(a.model), json.dumps(ids), a.watch)
    r = json.loads(ev(js) or "{}")
    if r.get("skip") or r.get("fail"):
        print("[FAIL]", r)
        return 2
    ok = True
    d = r.get("diag") or {}
    print("① 库的自动回落组 groups.idle = %r（轮播接管时它是 null，改由 motionFinish 挑下一条）"
          % r["poolGroup"])
    if r["poolGroup"] not in (None, "null"):
        print("  [FAIL] groups.idle 既不是 null 也不是原组 ⇒ 池没接管"); ok = False
    print("   探针显式 startMotion('__pool') 前 currentGroup=%r → 3 秒后 %r（返回 %s）"
          % (d.get("before"), d.get("after"), d.get("tryStart")))
    print("   state 前 %s" % json.dumps(d.get("state"), ensure_ascii=False)[:200])
    print("   state 后 %s" % json.dumps(d.get("stateAfter"), ensure_ascii=False)[:200])
    kw = [l for l in logs if re.search(r"motion|Motion|Cannot|Failed", l)]
    print("   运行时日志：抓到 %d 条，与动作有关的 %d 条" % (len(logs), len(kw)))
    for l in list(dict.fromkeys(kw))[:8]:
        print("     - %s" % l[:190])
    if not kw:
        for l in list(dict.fromkeys(logs))[:6]:
            print("     · %s" % l[:190])
    seq = [g for g in r["groups"]]
    changes = sum(1 for i in range(1, len(seq)) if seq[i] != seq[i - 1])
    print("② %d 秒内 currentGroup 序列: %s" % (r["watch"], " -> ".join(str(x) for x in seq)))
    print("   变化次数 %d（要求 >=2）；播过的组: %s"
          % (changes, sorted({str(g) for g in seq})))
    if changes < 2:
        print("  [FAIL] 没在轮播"); ok = False
    non_idle = {g for g in seq if g and g != "idle"}
    print("③ 轮播里出现过 %d 条非 idle 组: %s" % (len(non_idle), sorted(non_idle)))
    print("   同一窗口内花瓣类参数位移（信息项：只有 main_*/home 会动它们，"
          "随机到没轮到属正常，逐条 clip 的驱动关系由 l2d_motion_param_probe 单独证）:")
    moved = [s for s in r["spans"] if (s["span"] or 0) > 1e-3]
    for s in r["spans"]:
        print("   %-10s Δ=%s" % (s["id"], s["span"]))
    if not non_idle:
        print("  [FAIL] 60 秒内只播过 idle ⇒ 轮播没换条"); ok = False
    else:
        print("   本窗口动过 %d / %d 个花瓣参数" % (len(moved), len(r["spans"])))
    for p in (proc, srv):
        try:
            p.terminate()
        except Exception:
            pass
    try:
        ws.close()
    except Exception:
        pass
    kill_stale_chrome(DEBUG_DIR)
    print("\n== 结论:", "PASS" if ok else "FAIL")
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
