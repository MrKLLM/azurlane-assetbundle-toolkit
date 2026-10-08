# -*- coding: utf-8 -*-
"""l2d_part_flicker_probe.py — 抓「部件闪一下」：逐帧采样每个 part 的不透明度，
把「中途掉下去又回来」的部件点名出来，并对「动作播完把参数渐变回默认」那层补丁做 A/B。

为什么要按 part 不透明度量：用户说"选 home 时手的组件会消失一下"，这是**观感**，
观感不能当判据；而"整个部件短暂变透明/被隐藏"在 Cubism 里就是 part opacity 掉下去，
是可以逐帧采的。三条一起出才算判死：
  ① 该 part 在窗口内**掉到 <0.5 又回到 >0.8**（= 闪一下），并给出掉下去的时刻与幅度；
  ② 全程为 0 的 part 单独归类（那是本皮肤本来就不显示的部件，不是 bug）；
  ③ 同一序列在 `NOREST=1`（关掉渐变复位）下重跑一遍，看 ① 是否消失 —— 只有这一步
     能区分"是复位补丁干的"还是"交叉淡化/物理/环境层干的"。

用法: py -3 scripts/diag/l2d_part_flicker_probe.py gezi_2 --clips home,touch_head,mission_complete
      NOREST=1 py -3 scripts/diag/l2d_part_flicker_probe.py gezi_2 --clips home
输出: 终端报告 + .diag/l2d_flicker_<model>_{rest,norest}.json
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
PORT = 9357
SRV_PORT = 8807
DEBUG_DIR = os.path.join(ROOT, ".diag", "chrome_flicker")
os.makedirs(DEBUG_DIR, exist_ok=True)


def kill_stale(profile_dir):
    ps = ("$ErrorActionPreference='SilentlyContinue';"
          "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
          "Where-Object { $_.CommandLine -like '*%s*' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % profile_dir)
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--clips", default="home,touch_head,mission_complete")
    ap.add_argument("--hold", type=float, default=4.0, help="每条窗口秒数（片段 + 回落各一段）")
    ap.add_argument("--step", type=int, default=120, help="采样间隔 ms")
    ap.add_argument("--trace", default="", help="逗号分隔的 drawable/part 名，逐帧打印其透明度与当时的 currentGroup")
    a = ap.parse_args()
    norest = os.environ.get("NOREST") == "1"
    tag = "norest" if norest else "rest"

    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(SRV_PORT),
                            "-b", "127.0.0.1", "-d", os.path.join(ROOT, "Output")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = "http://127.0.0.1:%d/gallery_v2/index.html" % SRV_PORT
    for _ in range(60):
        try:
            if urllib.request.urlopen(url, timeout=2).status == 200:
                break
        except Exception:
            time.sleep(0.5)
    kill_stale(DEBUG_DIR)
    proc = subprocess.Popen([
        CHROME, "--headless=new", "--remote-debugging-port=%d" % PORT,
        "--remote-allow-origins=*", "--user-data-dir=%s" % DEBUG_DIR,
        "--no-first-run", "--no-default-browser-check",
        "--disable-background-timer-throttling", "--enable-unsafe-swiftshader",
        "--use-angle=swiftshader", "--window-size=1280,900", url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws = None
    for _ in range(90):
        try:
            tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % PORT))
            c = [t["webSocketDebuggerUrl"] for t in tabs if "gallery_v2" in t.get("url", "")
                 and t.get("webSocketDebuggerUrl")]
            if c:
                import websocket
                ws = websocket.create_connection(c[0], timeout=300, max_size=None)
                break
        except Exception:
            pass
        time.sleep(0.5)
    if ws is None:
        print("[FAIL] DevTools 连不上（多半是残留 chrome 占了同一个 user-data-dir）")
        return 2
    nid = [0]

    def cmd(method, params=None):
        nid[0] += 1
        ws.send(json.dumps({"id": nid[0], "method": method, "params": params or {}}))
        ws.settimeout(300)
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == nid[0]:
                if "error" in m:
                    raise RuntimeError(json.dumps(m["error"])[:200])
                return m.get("result", {})

    def ev(expr):
        r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        if r.get("exceptionDetails"):
            return "EVALERR " + str(r["exceptionDetails"])[:260]
        return r.get("result", {}).get("value")

    cmd("Page.enable")
    js_boot = """(async (key) => {
      const t=ms=>new Promise(r=>setTimeout(r,ms));
      for(let i=0;i<160 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
      if(!(window.GALLERY && typeof openShip==='function'))
        return JSON.stringify({fail:'页面脚本没就绪', href:location.href,
                               body:(document.body&&document.body.innerText||'').slice(0,140)});
      let ship=null, sk=null;
      for (const s of GALLERY.ships) { const k=s.skins.find(x=>x.key===key);
        if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
      if(!sk) return JSON.stringify({fail:'没有皮肤 '+key});
      openShip(ship); setSkin(sk); buildSkinList(ship);
      const l2=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d');
      l2.click();
      const t0=performance.now();
      while(!l2State||!l2State.app||!l2State.app.stage.children.length){
        if(performance.now()-t0>60000) break; await t(200); }
      const m0=l2State.app.stage.children[0];
      window.__m=m0; window.__app=l2State.app;
      window.__noRest=%s;                       // A/B 开关：true = 关掉「渐变回默认」那层
      window.__traceNames=%s; window.__traceGroups=[];
      window.__ofmReport='无';
      if(%s && window.PIXI && PIXI.live2d && PIXI.live2d.CubismConfig){
        PIXI.live2d.CubismConfig.setOpacityFromMotion=true;
        window.__ofmReport=String(PIXI.live2d.CubismConfig.setOpacityFromMotion); }
      const core=m0.internalModel.coreModel;
      const ids=[]; for(let i=0;i<core.getPartCount();i++){
        const raw=core._partIds; const x=Array.isArray(raw)?raw[i]:null;
        ids.push((typeof x==='string')?x:((x&&x.string)||('Part#'+i))); }
      window.__partIds=ids;
      const darr=[]; const draw=core._model&&core._model.drawables;
      const rawIds=(draw&&draw.ids)||core._drawableIds||[];
      for(let i=0;i<core.getDrawableCount();i++){ const x=Array.isArray(rawIds)?rawIds[i]:null;
        darr.push((typeof x==='string')?x:((x&&x.string)||('Drawable#'+i))); }
      window.__drawableIds=darr;
      return JSON.stringify({ok:true, parts:core.getPartCount(), noRest:window.__noRest, ofm:window.__ofmReport, cubismConfigReachable: !!(window.PIXI&&PIXI.live2d&&PIXI.live2d.CubismConfig),
                             groups:Object.keys(m0.internalModel.motionManager.definitions||{}).length});
    })(%s)""" % (json.dumps(norest), json.dumps([x for x in a.trace.split(",") if x]),
                       json.dumps(os.environ.get("OFM") == "1"), json.dumps(a.model))
    raw = ev(js_boot)
    try:
        info = json.loads(raw) if isinstance(raw, str) and raw.strip().startswith("{") else (raw if isinstance(raw, dict) else {"fail": str(raw)[:400]})
    except Exception:
        info = {"fail": "boot 返回不是 JSON", "raw": str(raw)[:400]}
    if not info.get("ok"):
        print("[FAIL]", info)
        return 2
    print("模型 %s：part %d 个，%d 组动作，渐变复位=%s"
          % (a.model, info["parts"], info["groups"], "关（NOREST=1）" if norest else "开（默认）"))

    js_play = """(async (clip, holdSec, stepMs) => {
      const t=ms=>new Promise(r=>setTimeout(r,ms));
      const m=window.__m, core=m.internalModel.coreModel;
      const mm=m.internalModel.motionManager;
      const idle=(['idle','main','home'].find(g=>(mm.definitions||{})[g]))||'idle';
      const pg=(core._partGroups||[]).map(g=>g.parameterIndex).filter(i=>typeof i==='number'&&i>=0);
      window.__pgIdx=[...new Set(pg)];
      const n=core.getPartCount(), nd=core.getDrawableCount();
      const ser=[], dser=[], gser=[], ts=[];
      const snap=()=>{ const row=[]; for(let i=0;i<n;i++) row.push(+core.getPartOpacityByIndex(i).toFixed(3));
                       const drow=[]; for(let i=0;i<nd;i++) drow.push(+core.getDrawableOpacity(i).toFixed(3));
                       const grow=[]; for(const i of window.__pgIdx) grow.push(+core.getParameterValueByIndex(i).toFixed(3));
                       ts.push(+((performance.now()-t0)/1000).toFixed(2)); ser.push(row); dser.push(drow); gser.push(grow); };
      const t0=performance.now();
      if(clip!=='__none__'){ try{ mm.startMotion(clip,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){} }
      const half=Math.max(1, Math.round(holdSec*1000/stepMs/2));
      for(let k=0;k<half;k++){ try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
                               window.__app.render(); snap(); await t(stepMs); }
      try{ mm.startMotion(idle,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){}   // 逼出回落 ⇒ 复位层会动
      for(let k=0;k<half;k++){ try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
                               window.__app.render(); snap(); await t(stepMs); }
      const scan=(mat, ids, kind)=>{
        const out=[]; let varying=0;
        for(let i=0;i<mat[0].length;i++){
          const col=mat.map(r=>r[i]);
          const lo=Math.min(...col), hi=Math.max(...col);
          if(hi-lo>1e-3) varying++;
          if(hi<0.05) continue;
          let hard=null, soft=null;
          for(let k=1;k<col.length;k++){
            const drop=col[k-1]-col[k];
            if(col[k]<0.05 && col[k-1]>0.5){ if(!hard||col[k]<hard.v) hard={k, v:col[k], before:col[k-1]}; }
            if(drop>=0.4 && !soft){
              const back=col.slice(k, Math.min(col.length, k+5)).reduce((m,x)=>Math.max(m,x), 0);
              if(back >= col[k-1]*0.8) soft={k, v:col[k], before:col[k-1]};
            }
          }
          const hit=hard||soft;
          if(hit) out.push([kind, (ids&&ids[i]!==undefined)?ids[i]:('#'+i),
                            hard?'hard':'soft', hit.v, hit.before, ts[hit.k], +(hi-lo).toFixed(3)]);
        }
        return {dips:out, varying};
      };
      const A=scan(ser, window.__partIds, 'part'), B=scan(dser, window.__drawableIds, 'drawable');
      const tr=(window.__traceNames||[]).map(nm=>{
        let j=window.__drawableIds.indexOf(nm); if(j<0){ j=window.__partIds.indexOf(nm);
          return {name:nm, kind:'part', col:ser.map(r=>r[j]), groups:window.__traceGroups}; }
        return {name:nm, kind:'drawable', col:dser.map(r=>r[j]), groups:window.__traceGroups}; });
      const gscan=[];
      const list=window.__pgIdx;      // TODO(未做)：全参数逐帧版本还没接通，别当成「参数没跳变」
      for(let j=0;j<list.length;j++){ const ix=list[j];
        const col=gser.map(r=>r[ix]); if(col.length<3) continue;
        const hi=Math.max(...col), lo=Math.min(...col);
        if(hi-lo<1e-3) continue;
        let steps=0, prev=col[0];
        for(const x of col){ if(Math.abs(x-prev)>0.02) steps++; prev=x; }
        gscan.push([(core._parameterIds[window.__pgIdx[j]]||("?"+window.__pgIdx[j])), +(hi).toFixed(2), +(lo).toFixed(2), steps, col]);
      }
      return JSON.stringify({frames:ser.length, ts:[ts[0], ts[ts.length-1]], partCount:n, drawableCount:nd,
        partsVaried:A.varying, drawablesVaried:B.varying, groupParams:gscan.length,
        groups:gscan.filter(g=>g[3]>=2).map(g=>[g[0],g[1],g[2],g[3],g[4]]),
        dips:A.dips.concat(B.dips).sort((x,y)=>x[5]-y[5]), trace:tr});
    })"""
    out = {"model": a.model, "norest": norest, "clips": {}}
    for clip in [c for c in a.clips.split(",") if c]:
        raw2 = ev(js_play + "(%s, %s, %s)" % (json.dumps(clip), json.dumps(a.hold),
                                              json.dumps(a.step)))
        try:
            r = json.loads(raw2) if isinstance(raw2, str) and raw2.strip().startswith("{") else (raw2 if isinstance(raw2, dict) else {"dips": [], "err": str(raw2)[:400]})
        except Exception:
            r = {"dips": [], "err": str(raw2)[:300]}
        out["clips"][clip] = r
        ds = r.get("dips") or []
        print("\n-- clip `%s`：窗口 %.1fs / %d 帧 ⇒ 闪一下的部件 %d 个" % (clip, r.get("frames", 0) * a.step / 1000.0, r.get("frames", 0), len(ds)))
        for d in ds[:14]:
            print("     [%s] %-26s %-4s 掉到 %.2f（前 %.2f）@t=%.2fs 序列幅度 %.3f"
                  % (d[0], str(d[1])[:26], d[2], d[3], d[4], d[5], d[6]))
        for tr in (r.get("trace") or []):
            print("     ── trace %s/%s 逐帧（t, 透明度, 当时的 currentGroup）" % (tr["kind"], tr["name"]))
            for k in range(0, len(tr["col"])):
                g = (tr.get("groups") or [None] * len(tr["col"]))[k]
                print("       %5.2fs  %.2f  %s" % (r["ts"][0] + k * a.step / 1000.0, tr["col"][k], g))
    fp = os.path.join(ROOT, ".diag", "l2d_flicker_%s_%s.json" % (a.model, tag))
    with open(fp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    tot = sum(len((v or {}).get("dips") or []) for v in out["clips"].values())
    print("\n合计闪没事件 %d 次 → %s" % (tot, fp))
    try:
        ws.close()
    except Exception:
        pass
    for p in (proc, srv):
        try:
            p.terminate()
        except Exception:
            pass
    kill_stale(DEBUG_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
