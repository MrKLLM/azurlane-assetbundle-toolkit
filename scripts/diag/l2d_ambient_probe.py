# -*- coding: utf-8 -*-
"""l2d_ambient_probe.py — 用真实运行时证「effect 环境层叠加」这件事确实生效、且没把别的弄坏。

要判死的三件事（缺一不可，任何一条不成立就是假绿灯）：
  ① **正向**：环境层开着时，effect 的非常值参数在逐帧变化（花瓣真的在飘）。
  ② **阴性对照**：把 `window.__ambOff` 置 true（前端留的 A/B 开关，UI 上没有入口）之后，
     **同一批参数一动不动**。缺这条，就无法区分"是环境层在动"还是"本来就在动"。
  ③ **零回退**：idle 自己驱动的参数在两种状态下都照样动（环境层没把 pose 层盖死）。
另外顺带断言：模型加载成功、页面没有 EVALERR、下拉里 effect 组仍在（用户仍可单独播它）。

用法: py -3 scripts/diag/l2d_ambient_probe.py gezi_2,aerbien_3 --control biaoqiang
      （--control 是不带 effect 组的模型，断言"没有环境层也不该报错"）
输出: .diag/l2d_ambient_shots/<model>_{on,off}.png + 终端报告；全绿 exit 0。
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
PORT = 9341
SRV_PORT = 8793
DEBUG_DIR = os.path.join(ROOT, ".diag", "chrome_ambient")
SHOTS = os.path.join(ROOT, ".diag", "l2d_ambient_shots")
L2D = os.path.join(ROOT, "Output", "Live2D")
os.makedirs(SHOTS, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)

SAMPLES = 8
STEP_MS = 260


def ambient_params(key):
    """从产物本身算出「环境层会写哪些参数」——判据落在载荷上，不靠前端自述。
    另返回每条曲线的**段结构**：单段线性的（漂移类，如 Paramfh 0→2000/90s）可以拿
    运行时观测斜率对表，多段的只能判"动不动"。"""
    f = os.path.join(L2D, key, "motion", "effect.motion3.json")
    if not os.path.exists(f):
        return None
    j = json.load(open(f, encoding="utf-8"))
    ids = []
    info = {}
    for c in j.get("Curves", []):
        if c.get("Target") != "Parameter":
            continue
        s = c.get("Segments") or []
        pts = [s[1]] if len(s) > 1 else []
        kinds = []
        i = 2
        while i < len(s):
            if s[i] == 0:
                pts.append(s[i + 2]); kinds.append(("L", s[i + 1], s[i + 2])); i += 3
            elif s[i] == 1:
                pts.append(s[i + 6]); kinds.append(("B", s[i + 5], s[i + 6])); i += 7
            else:
                pts = []; break
        if len(pts) > 1 and max(pts) - min(pts) > 1e-6:
            cid = c.get("Id")
            pid = cid if isinstance(cid, str) else (cid or {}).get("string")
            if not pid:
                continue
            ids.append(pid)
            ramp = None
            if len(kinds) == 1 and kinds[0][0] == "L":
                t0, v0, t1, v1 = s[0], s[1], kinds[0][1], kinds[0][2]
                if t1 > t0:
                    ramp = (v1 - v0) / (t1 - t0)
            info[pid] = {"ramp": ramp, "span": (min(pts), max(pts))}
    return ids, j["Meta"]["Duration"], info


def idle_params(key, group="idle"):
    f = os.path.join(L2D, key, "motion", "%s.motion3.json" % group)
    if not os.path.exists(f):
        return []
    j = json.load(open(f, encoding="utf-8"))
    out = []
    for c in j.get("Curves", []):
        if c.get("Target") != "Parameter":
            continue
        s = c.get("Segments") or []
        pts = [s[1]] if len(s) > 1 else []
        i = 2
        while i < len(s):
            if s[i] == 0:
                pts.append(s[i + 2]); i += 3
            elif s[i] == 1:
                pts.append(s[i + 6]); i += 7
            else:
                pts = []; break
        if len(pts) > 1 and max(pts) - min(pts) > 1e-6:
            cid = c.get("Id")
            out.append(cid if isinstance(cid, str) else (cid or {}).get("string"))
    return [x for x in out if x]


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
    ap.add_argument("keys", nargs="?", default="gezi_2,aerbien_3")
    ap.add_argument("--control", default="biaoqiang", help="无 effect 组的对照模型")
    a = ap.parse_args()
    keys = [k for k in a.keys.split(",") if k]

    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(SRV_PORT), "-b", "127.0.0.1",
         "-d", os.path.join(ROOT, "Output")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    kill_stale_chrome(DEBUG_DIR)
    url = "http://127.0.0.1:%d/gallery_v2/index.html" % SRV_PORT
    for _ in range(40):
        try:
            if urllib.request.urlopen(url, timeout=2).status == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        raise RuntimeError("本地服务器未就绪 " + url)

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
            return "EVALERR " + str(r["exceptionDetails"].get("exception", {}).get("description"))[:200]
        return r.get("result", {}).get("value")

    cmd("Page.enable"); cmd("Runtime.enable")
    # GALLERY 来自 index.js，会先于页面内联脚本执行完 —— 只等它就撞上
    # 「openShip is not defined」的启动竞态（实测同一份代码两次跑一次成一次败）。
    for _ in range(80):
        if ev("typeof GALLERY!=='undefined' && typeof openShip==='function' "
              "&& typeof setSkin==='function' && typeof renderView==='function'") is True:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("页面脚本未就绪: " + str(ev(
            "JSON.stringify([typeof GALLERY,typeof openShip,typeof setSkin,typeof renderView])"))[:200])

    def load(key):
        js = """(async () => {
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          const KEY=%s;
          let ship=null, sk=null;
          for (const s of GALLERY.ships) { const k=s.skins.find(x=>x.key===KEY);
            if(k&&s.live2dSkins.includes(KEY)){ship=s;sk=k;break;} }
          if(!sk) return JSON.stringify({skip:'皮肤表里没有 '+KEY});
          openShip(ship); setSkin(sk); buildSkinList(ship);
          tab='live2d'; renderView();
          await t(9000);
          const app=l2State&&l2State.app; if(!app) return JSON.stringify({fail:'无 l2State'});
          const m0=app.stage.children[0]; if(!m0) return JSON.stringify({fail:'无模型'});
          window.__m=m0; window.__app=app;
          const mm=m0.internalModel.motionManager;
          return JSON.stringify({ok:true, groups:Object.keys(mm.definitions||{}).length,
                                 hasEffect:!!(mm.definitions||{})['effect']});
        })()""" % json.dumps(key)
        raw = ev(js)
        if not isinstance(raw, str) or raw.startswith("EVALERR") or not raw.strip().startswith("{"):
            return {"fail": "load 返回非 JSON", "raw": str(raw)[:400]}
        return json.loads(raw)

    def sample(ids, amb_off):
        js = """(async () => {
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          const m=window.__m; if(!m) return JSON.stringify({fail:'no model'});
          window.__ambOff=%s;
          await t(120);
          const core=m.internalModel.coreModel;
          const ids=%s;
          const series=ids.map(()=>[]);
          const stamps=[];
          const meta={};
          ids.forEach(id=>{ const o={};
            let ix=-1; try{ ix=core.getParameterIndex(id); }catch(e){}
            o.ix=ix;
            if(ix>=0){   /* 这个 core 只有 index 版量程访问器（ById 版不存在，试过是 None） */
              try{ o.min=core.getParameterMinimumValue(ix); }catch(e){}
              try{ o.max=core.getParameterMaximumValue(ix); }catch(e){}
              try{ o.def=core.getParameterDefaultValue(ix); }catch(e){}
            }
            meta[id]=o; });
          for(let k=0;k<%d;k++){
            try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
            try{ window.__app.render(); }catch(e){}
            stamps.push(performance.now());
            ids.forEach((id,i)=>{ let v=null; try{ v=core.getParameterValueById(id); }catch(e){}
              series[i].push(typeof v==='number'? +v.toFixed(4):null); });
            await t(%d);
          }
          const moved=[], still=[], missing=[];
          ids.forEach((id,i)=>{ const a=series[i].filter(x=>typeof x==='number');
            if(!a.length){ missing.push(id); return; }
            if(Math.max(...a)-Math.min(...a) > 1e-4) moved.push(id); else still.push(id); });
          return JSON.stringify({moved, still, missing, n:ids.length, stamps, series, meta,
                                 ambOff:!!window.__ambOff});
        })()""" % ("true" if amb_off else "false", json.dumps(ids), SAMPLES, STEP_MS)
        raw = ev(js)
        if not isinstance(raw, str) or not raw.strip().startswith("{"):
            return {"fail": "sample 返回非 JSON", "raw": str(raw)[:400]}
        return json.loads(raw)

    ok = True
    for key in keys + [a.control]:
        ctl = key == a.control
        info = ambient_params(key)
        print("\n===== %s =====" % key)
        if info is None:
            print("  无 effect.motion3.json ⇒ 只断言「加载不报错、运行时也没有该组」")
        else:
            ids, dur, einfo = info
            print("  环境层非常值参数 %d 个 / 时长 %.1fs" % (len(ids), dur))
        lr = load(key)
        if not lr.get("ok"):
            print("  [FAIL] 加载失败", lr); ok = False; continue
        print("  加载 ok：%d 组动作，含 effect=%s" % (lr["groups"], lr["hasEffect"]))
        if not lr["hasEffect"]:
            if not ctl and info is not None:
                print("  [FAIL] 盘上有 effect.motion3.json 但运行时没有该组"); ok = False
            continue
        # 判据必须落在「只有环境层会驱动」的差集上：effect 与 idle 的参数大量重叠
        # （gezi_2 62 个里 52 个 idle 也在动），拿全集做阴性对照必然假红灯。
        only = [p for p in ids if p not in set(idle_params(key))]
        print("  其中 idle 从不动、只有环境层会驱动的 %d 个: %s" % (len(only), only[:8]))
        if not only:
            print("  [SKIP] 该模型没有环境层独占参数，无从判据"); continue
        on = sample(only, False)
        off = sample(only, True)
        n_on, n_off = len(on.get("moved") or []), len(off.get("moved") or [])
        print("  ① 环境层开：%d/%d 个独占参数在动（花瓣该在这里）" % (n_on, len(only)))
        print("  ② 环境层关：%d/%d 个仍在动（阴性对照，必须是 0）" % (n_off, len(only)))
        if on.get("missing"):
            print("     运行时读不到的参数 %d 个: %s" % (len(on["missing"]), on["missing"][:6]))
        if n_off:
            print("  [FAIL] 阴性对照不成立：关掉后仍在动 ⇒ 动的不是环境层"); ok = False
        # 「动了」不等于「按对的速度动」：单段线性的漂移曲线（Paramfh 0→2000/90s 这类）
        # 斜率与相位无关，可以拿 JSON 独立算一遍跟运行时观测值对表。多段曲线斜率随相位变，
        # 只能判动不动，不列入硬断言。
        stamps = on.get("stamps") or []
        series = on.get("series") or []
        meta = on.get("meta") or {}
        ramps = [(p, einfo[p]["ramp"]) for p in only if einfo.get(p, {}).get("ramp") is not None]
        bad = []; sat = []
        print("  ④ 速率对表（单段线性漂移曲线，JSON 独立算 vs 运行时观测）:")
        for p, exp in ramps:
            i = only.index(p)
            vs = series[i] if i < len(series) else []
            lo, hi = einfo[p]["span"]
            m = meta.get(p) or {}
            legal = m.get("min") is not None and m.get("max") is not None
            clamped = legal and (lo < m["min"] - 1e-6 or hi > m["max"] + 1e-6)
            if len(vs) < 2 or stamps[-1] <= stamps[0]:
                bad.append(p); print("     %-26s 采样不足" % p); continue
            obs = (vs[-1] - vs[0]) / ((stamps[-1] - stamps[0]) / 1000.0)
            tol = max(0.2 * abs(exp), 1e-6)
            if clamped:
                sat.append(p)
                print("     %-26s JSON %+.2f..%+.2f 越出 moc3 合法量程 [%s, %s] ⇒ Cubism 钳位，"
                      "运行时恒读 %s（这条**不是**求值器错，是量程）"
                      % (p, lo, hi, m["min"], m["max"], round(vs[0], 3)))
                continue
            flag = "OK" if abs(obs - exp) <= tol else "FAIL"
            if flag == "FAIL":
                bad.append(p)
            print("     %-26s 期望 %+9.3f/s  观测 %+9.3f/s  %s" % (p, exp, obs, flag))
            if flag == "FAIL":
                print("        运行时序列: %s" % [None if v is None else round(v, 2) for v in vs])
        if ramps:
            print("     小结：在量程内必须对表的 %d 条里错 %d 条；越量程被钳位 %d 条"
                  % (len(ramps) - len(sat), len(bad), len(sat)))
            if bad and len(bad) > (len(ramps) - len(sat)) * 0.2:
                print("  [FAIL] 速率对表不成立: %s" % bad[:6]); ok = False
        else:
            print("     （该模型没有单段线性漂移曲线，跳过）")
        if n_on < max(1, int((len(only) - len(sat)) * 0.8)):
            print("  [FAIL] 正向不成立：量程内该动的没动够"); ok = False
        idle_ids = idle_params(key)[:40]
        if idle_ids:
            ip = sample(idle_ids, False)
            ir = sample(idle_ids, True)
            print("  ③ 零回退：idle 自驱动的 %d 个参数 开=%d 动 / 关=%d 动"
                  % (len(idle_ids), len(ip.get("moved") or []), len(ir.get("moved") or [])))
            # P2 的语义就是环境层盖住 pose 层，"开 ≤ 关"是设计如此。两个数都受 2 秒采样窗
            # 影响（斜率过零点的参数会在某一侧漏判），所以只断言"关掉后仍该动"这一侧。
            if len(ir.get("moved") or []) < len(idle_ids) // 2:
                print("  [FAIL] 关掉环境层后 idle 参数几乎不动 ⇒ 此前是环境层在替 pose 层驱动"); ok = False
            # ⑤ 环境层**不许改变 pose 轨迹**：同一批参数开/关逐点比，最大偏离必须≈0。
            #    上一版没有这条，环境层逐帧硬写 52 个与 idle 重叠的参数 ⇒ 换 clip 瞬间被拽到
            #    越量程极值，用户看到的"抽搐 + 僵硬"就是它。
            sa, sb = ip.get("series") or [], ir.get("series") or []
            worst = 0.0; worst_id = ""
            for i, idn in enumerate(idle_ids):
                if i >= len(sa) or i >= len(sb):
                    continue
                for x, y in zip(sa[i], sb[i]):
                    if isinstance(x, (int, float)) and isinstance(y, (int, float)) \
                            and abs(x - y) > worst:
                        worst, worst_id = abs(x - y), idn
            print("  ⑤ pose 轨迹不被改动：开/关逐点最大偏离 %.4f（%s，要求 <0.01）" % (worst, worst_id or "-"))
            if worst >= 0.01:
                print("  [FAIL] 环境层在抢 pose 参数"); ok = False
        for tag, flag in (("on", False), ("off", True)):
            sample(ids[:1], flag)
            r = cmd("Page.captureScreenshot", {"format": "png"})
            p = os.path.join(SHOTS, "%s_%s.png" % (key, tag))
            open(p, "wb").write(base64.b64decode(r["data"]))
        print("  截图 %s_{on,off}.png" % key)

    try:
        ws.close()
    except Exception:
        pass
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        srv.terminate()
    except Exception:
        pass
    kill_stale_chrome(DEBUG_DIR)
    print("\n== 结论:", "PASS" if ok else "FAIL")
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
