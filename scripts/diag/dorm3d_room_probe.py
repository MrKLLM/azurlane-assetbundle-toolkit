"""room.glb 进 three.js 的验收探针：把画面变成**数**，并给每条 ✅ 配一条会红的对照。

为什么不写"加载没报错就算过"：GLB 解析成功只证明文件合法，证明不了摆位、朝向、光照
和"到底有没有东西画出来"。这一步量的每一条都落在**前端真实读数** vs **源包口径真值**
（`room.glb.truth.json`，由装配器从 Unity 声明字段算出，不是我写进 GLB 的那份字节）上。

    py -3 scripts/diag/dorm3d_room_probe.py
    py -3 scripts/diag/dorm3d_room_probe.py --glb .diag/dorm3d_room/sample80.glb

判据：
  J1 前端 Mesh 对象数 == 真值 primitive 数
  J2 前端 Σ position.count == 真值 position 计数
  J3 renderer 画的三角数 == 真值三角数（所有对象 frustumCulled=false，所以应当是恒等而非"至少"）
  J4 前端世界盒（只算非占位对象）vs 真值世界盒，逐轴相对差 < 0.5%
  J5 浏览器 console 零 error
  J6 游戏机位那张截图的落笔占比 >= 0.15（画面里真的有被照亮的内容）
反向对照（不是装饰，是把 J1..J6 从恒真里区分出来）：
  C1 指向不存在的 glb ⇒ J1/J2/J3 必须全为 0（否则计数判据根本没在量东西）
  C2 把所有灯摘掉再渲染 ⇒ J6 的落笔占比必须塌到 <0.05（否则"有像素"不等于"有内容"）
"""
import argparse
import base64
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "gallery_src"))

import cdp_slot                                  # noqa: E402
import chrome_tree                               # noqa: E402
import paths as AP                               # noqa: E402

WORK = os.path.join(ROOT, ".diag", "dorm3d_room")
CHROME = AP.tool("AL_CHROME", "chrome", r"C:/Program Files/Google/Chrome/Application/chrome.exe",
                 r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
PORT, PROFILE = cdp_slot.slot(ROOT, "d3droom")
FAIL = []


def say(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAIL.append(msg)
    return cond


HARNESS = r"""<!doctype html><html><head><meta charset="utf-8">
<script type="importmap">{"imports":{"three":"/three/three.module.min.js",
"three/addons/":"/three/jsm/"}}</script>
<style>html,body{margin:0;background:#101418}canvas{display:block}</style></head><body>
<script type="module">
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
const Q=new URLSearchParams(location.search);
const W=1280,H=960;
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setSize(W,H); renderer.setClearColor(0x101418,1); document.body.appendChild(renderer.domElement);
const scene=new THREE.Scene(); const camera=new THREE.PerspectiveCamera(60,W/H,0.02,3000);
window.__ERR=null; window.__DONE=false; window.__RESULT=null; window.__VIEWS=[]; window.__cur=0;
function ink(){ // 落笔占比：数**比背景亮**的采样像素。用「与背景不同」是错的——
  // 无光时模型是纯黑，纯黑与深色背景「不同」，会把一片漆黑读成画满了内容。
  const c=document.createElement('canvas'); c.width=W; c.height=H;
  const x=c.getContext('2d'); x.drawImage(renderer.domElement,0,0);
  const d=x.getImageData(0,0,W,H).data; let n=0,tot=0;
  for(let i=0;i<d.length;i+=4*11){ tot++; const r=d[i],g=d[i+1],b=d[i+2];
    if(Math.max(r,g,b)>40) n++; }
  return {ink:n/tot, sampled:tot};
}
function boxOf(list, onlyReal){
  const b=new THREE.Box3(); const t=new THREE.Box3();
  for(const o of list){ if(onlyReal && o.userData.ph) continue;
    t.setFromObject(o); if(!t.isEmpty()) b.union(t); }
  return b.isEmpty()?null:[ [b.min.x,b.min.y,b.min.z],[b.max.x,b.max.y,b.max.z] ];
}
fetch(Q.get('truth')).then(r=>r.json()).then(truth=>{
  window.__TRUTH=truth;
  new GLTFLoader().load(Q.get('m'), g=>{
    scene.add(g.scene);
    const clean=s=>String(s||'').replace(/__mesh_\d+$/,'');
    const phNames=new Set(truth.per_object.filter(p=>p.placeholder).map(p=>clean(p.mesh)));
    const meshes=[], names={}; let posTotal=0;
    g.scene.traverse(o=>{ if(o.isMesh){ meshes.push(o);
      const nm=clean(o.name)||clean(o.geometry&&o.geometry.name)||'';
      o.userData.ph = phNames.has(nm) || /__PLACEHOLDER$/.test(nm);
      posTotal += (o.geometry&&o.geometry.attributes.position)?o.geometry.attributes.position.count:0;
      names[nm]=(names[nm]||0)+1; } });
    let lights=0; g.scene.traverse(o=>{ if(o.isLight) lights++; });
    if(Q.get('nolight')==='1'){ const kill=[]; g.scene.traverse(o=>{ if(o.isLight) kill.push(o); });
      kill.forEach(o=>o.parent&&o.parent.remove(o)); }
    const amb=parseFloat(Q.get('amb')||'0');
    if(amb>0) scene.add(new THREE.AmbientLight(0xffffff, amb));   // 补光不是包里的数据，只用于对照观感
    g.scene.traverse(o=>{ o.frustumCulled=false; });
    g.scene.updateMatrixWorld(true);
    const inner=truth.per_object.filter(p=>p.center&&Math.max(...p.center.map(Math.abs))<=15);
    window.__VIEWS=[
      {name:'game', pos:truth.camera.pos, look:truth.camera.pos.map((v,i)=>v+truth.camera.fwd[i]*3.0), fov:60},
      {name:'az000', pos:[0, 6.5, -11], look:[0,1.2,0], fov:55},
      {name:'az090', pos:[11, 6.5, 0], look:[0,1.2,0], fov:55},
      {name:'az180', pos:[0, 6.5, 11], look:[0,1.2,0], fov:55},
      {name:'top', pos:[7.5, 12.5, 7.5], look:[0,0.6,0], fov:55}];
    window.__STATS={meshObjects:meshes.length, posTotal, lights,
                    renderedTris:renderer.info.render.triangles,
                    boxAll:boxOf(meshes,false), boxReal:boxOf(meshes,true),
                    innerCount:inner.length, distinctNames:Object.keys(names).length};
    renderer.render(scene,camera);
    window.__STATS.renderedTris=renderer.info.render.triangles;
    window.applyView=i=>{ const v=window.__VIEWS[i];
      camera.position.set(...v.pos); camera.up.set(0,1,0); camera.fov=v.fov;
      camera.lookAt(new THREE.Vector3(...v.look)); camera.updateProjectionMatrix();
      renderer.render(scene,camera); window.__cur=i; return ink(); };
    window.__DONE=true;
  }, undefined, e=>{ window.__ERR=String(e&&e.message||e).slice(0,300);
    window.__STATS={meshObjects:0,posTotal:0,lights:0,renderedTris:0,boxAll:null,boxReal:null,
                    innerCount:0,distinctNames:0};
    window.applyView=()=>({ink:0,sampled:0}); window.__DONE=true; });
}).catch(e=>{ window.__ERR='truth 读取失败 '+String(e).slice(0,120); window.__DONE=true; });
</script></body></html>"""


def serve(root_dir):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=root_dir, **kw)

        def log_message(self, *a):
            pass

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        p = s.getsockname()[1]
    httpd = socketserver_server(H, p)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, p


def socketserver_server(handler, port):
    import socketserver

    class S(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

        def handle_error(self, request, client_address):
            pass
    return S(("127.0.0.1", port), handler)


def build_variants(glb):
    """占位文件不参与装配；坏版只用于对照——这里直接造一个指向不存在文件的 URL。"""
    return {"game": glb, "bad": "dorm3d_room/__no_such__.glb"}


def run_case(browser, base, glb_url, truth_url, tag, shots, extra=""):
    cmd_id = [0]
    ws = browser["ws"]

    def cmd(m, p=None):
        cmd_id[0] += 1
        ws.send(json.dumps({"id": cmd_id[0], "method": m, "params": p or {}}))
        ws.settimeout(240)
        while True:
            r = json.loads(ws.recv())
            if r.get("method") == "Log.entryAdded":
                e = r["params"]["entry"]
                if e.get("level") == "error" and "favicon" not in (e.get("url") or ""):
                    browser["errs"].append("%s|%s" % ((e.get("text") or "")[:120],
                                                      (e.get("url") or "")[-60:]))
                continue
            if r.get("method") == "Runtime.consoleAPICalled" and r["params"].get("type") == "error":
                browser["errs"].append(" ".join(str(x.get("value", "")) for x in
                                                r["params"].get("args", []))[:160])
                continue
            if r.get("id") == cmd_id[0]:
                if "error" in r:
                    raise RuntimeError(json.dumps(r["error"])[:200])
                return r.get("result", {})

    def ev(e):
        r = cmd("Runtime.evaluate", {"expression": e, "awaitPromise": True})
        if r.get("exceptionDetails"):
            return {"__err": str(r["exceptionDetails"].get("text"))[:200]}
        return r.get("result", {}).get("value")

    url = "%sdorm3d_room/harness.html?m=%s&truth=%s%s" % (base, base + glb_url, base + truth_url, extra)
    if shots.get("nolight"):
        url += "&nolight=1"
    ev("location.href='%s'" % url)
    for _ in range(200):
        if ev("window.__DONE === true"):
            break
        time.sleep(0.5)
    else:
        say(False, "%s: 100 秒没跑完（harness 没置 __DONE）" % tag)
        return None
    stats = ev("JSON.stringify(window.__STATS)")
    stats = json.loads(stats) if isinstance(stats, str) else stats
    errtxt = ev("String(window.__ERR||'')")
    views = []
    n = ev("(window.__VIEWS||[]).length") or 0
    for i in range(int(n)):
        ink = ev("JSON.stringify(window.applyView(%d))" % i)
        ink = json.loads(ink) if isinstance(ink, str) else ink
        shot = cmd("Page.captureScreenshot", {"format": "png"}) or {}
        png = shot.get("data")
        if png:
            with open(os.path.join(WORK, "shot_%s_%s.png" % (tag, shots["names"][i])), "wb") as f:
                f.write(base64.b64decode(png))
        views.append({"name": shots["names"][i], "ink": (ink or {}).get("ink")})
    return {"stats": stats, "err": errtxt, "views": views}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", default=".diag/dorm3d_room/room.glb")
    ap.add_argument("--truth", default=".diag/dorm3d_room/room.glb.truth.json")
    ap.add_argument("--skip-controls", action="store_true", help="调试用；正式判定不许跳")
    a = ap.parse_args()
    glb = os.path.join(ROOT, a.glb) if not os.path.isabs(a.glb) else a.glb
    truth_p = os.path.join(ROOT, a.truth) if not os.path.isabs(a.truth) else a.truth
    if not os.path.isfile(glb) or not os.path.isfile(truth_p):
        print("[FAIL] 缺产物: %s / %s" % (a.glb, a.truth))
        return 2
    if not CHROME:
        print("[FAIL] 找不到 Chrome/Edge（设 AL_CHROME）")
        return 2
    if not os.path.isfile(os.path.join(ROOT, ".diag", "three", "three.module.min.js")):
        print("[FAIL] .diag/three/ 里没有 three.js —— 先按 WF-32 取库")
        return 2
    truth = json.load(open(truth_p, encoding="utf-8"))
    os.makedirs(WORK, exist_ok=True)
    open(os.path.join(WORK, "harness.html"), "w", encoding="utf-8").write(HARNESS)
    httpd, sport = serve(os.path.join(ROOT, ".diag"))
    base = "http://127.0.0.1:%d/" % sport
    names = [v for v in ("game", "az000", "az090", "az180", "top")]
    proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=%d" % PORT,
                             "--remote-allow-origins=*", "--user-data-dir=%s" % PROFILE,
                             "--no-first-run", "--no-default-browser-check",
                             "--disable-background-timer-throttling", "--use-angle=swiftshader",
                             "--window-size=%d,%d" % (1280, 960),
                             base + "dorm3d_room/harness.html?m=%s&truth=%s"
                             % (base + "dorm3d_room/" + os.path.basename(glb),
                                base + "dorm3d_room/" + os.path.basename(truth_p))],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(proc)
    try:
        import websocket
        ws = None
        for _ in range(120):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % PORT, timeout=5))
                u = [t["webSocketDebuggerUrl"] for t in tabs
                     if "harness.html" in t.get("url", "") and t.get("webSocketDebuggerUrl")]
                if u:
                    ws = websocket.create_connection(u[0], timeout=240, max_size=None)
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if ws is None:
            print("[FAIL] 连不上浏览器")
            return 2
        browser = {"ws": ws, "errs": []}
        for m in ("Runtime.enable", "Log.enable", "Page.enable"):
            cid = [0]

            def _c(mm):
                cid[0] += 1
                ws.send(json.dumps({"id": cid[0], "method": mm, "params": {}}))
                ws.settimeout(60)
                while True:
                    r = json.loads(ws.recv())
                    if r.get("id") == cid[0]:
                        return r
            _c(m)
        rel_glb = "dorm3d_room/" + os.path.basename(glb)
        rel_truth = "dorm3d_room/" + os.path.basename(truth_p)
        good = run_case(browser, base, rel_glb, rel_truth, "good", {"names": names})
        if not good:
            return 1
        st = good["stats"] or {}
        print("前端读数: Mesh 对象 %s / position 合计 %s / 三角 %s / 灯 %s / 非占位世界盒 %s"
              % (st.get("meshObjects"), st.get("posTotal"), st.get("renderedTris"),
                 st.get("lights"), [[round(v, 2) for v in ax] for ax in (st.get("boxReal") or [[], []])]))
        print("真值   : primitive %d / position %d / 三角 %d / 灯 %d / 世界盒 %s"
              % (truth["prim_total"], truth["pos_total"], truth["tri_total"], truth["lights"],
                 [[round(v, 2) for v in ax] for ax in truth["world_box"]]))
        say(st.get("meshObjects") == truth["prim_total"],
            "J1 Mesh 对象数 == 真值 primitive 数: %s vs %d" % (st.get("meshObjects"), truth["prim_total"]))
        say(st.get("posTotal") == truth["pos_total"],
            "J2 Σ position.count == 真值: %s vs %d" % (st.get("posTotal"), truth["pos_total"]))
        say(st.get("renderedTris") == truth["tri_total"],
            "J3 renderer 三角数 == 真值（frustumCulled 全关，应当恒等）: %s vs %d"
            % (st.get("renderedTris"), truth["tri_total"]))
        box = st.get("boxReal")
        ok_box = True
        if not box:
            ok_box = False
        else:
            span = max(truth["world_box"][1][k] - truth["world_box"][0][k] for k in range(3))
            for k in range(3):
                for sgn in (0, 1):
                    if abs(box[sgn][k] - truth["world_box"][sgn][k]) > 0.005 * max(span, 1.0):
                        ok_box = False
        say(ok_box, "J4 非占位世界盒逐轴 vs 真值（相对全场景跨度 <0.5%%）: 前端 %s vs 真值 %s"
            % (box, [[round(v, 2) for v in x] for x in truth["world_box"]]))
        say(len(browser["errs"]) == 0, "J5 console 零 error（实得 %d 条: %s）"
            % (len(browser["errs"]), browser["errs"][:2]))
        game_ink = next((v["ink"] for v in good["views"] if v["name"] == "game"), None)
        say(game_ink is not None and game_ink >= 0.15,
            "J6 游戏机位落笔占比 >= 0.15: 实得 %s（各机位 %s）"
            % (game_ink, {v["name"]: (round(v["ink"], 3) if v["ink"] is not None else None)
                          for v in good["views"]}))
        if not a.skip_controls:
            bad = run_case(browser, base, "dorm3d_room/__no_such__.glb", rel_truth, "bad",
                           {"names": names})
            bst = (bad or {}).get("stats") or {}
            say(bst.get("meshObjects") == 0 and bst.get("posTotal") == 0,
                "C1 坏版（指向不存在的 glb）计数必须归零: Mesh %s / position %s"
                % (bst.get("meshObjects"), bst.get("posTotal")))
            nl = run_case(browser, base, rel_glb, rel_truth, "nolight",
                          {"names": names, "nolight": True})
            nl_ink = next((v["ink"] for v in (nl or {}).get("views", []) if v["name"] == "game"), None)
            say(nl_ink is not None and nl_ink < 0.05,
                "C2 摘掉所有灯之后落笔占比必须塌（证明 J6 量的是被照亮的内容）: 实得 %s"
                % (None if nl_ink is None else round(nl_ink, 4)))
        amb = run_case(browser, base, rel_glb, rel_truth, "amb", {"names": names},
                       extra="&amb=0.6")
        aink = {v["name"]: (round(v["ink"], 3) if v["ink"] is not None else None)
                for v in (amb or {}).get("views", [])}
        print("  ℹ 补光版（scene 加 AmbientLight 0.6，**不是包里的数据**，只为看清明暗关系）: "
              "各机位落笔 %s；截图 shot_amb_*.png" % aink)
    finally:
        try:
            ws.close()
        except Exception:
            pass
        proc.kill()
        chrome_tree.cleanup(PROFILE) if hasattr(chrome_tree, "cleanup") else None
        httpd.shutdown()
    print("\n截图目录: %s" % P_rel(WORK))
    print("结论: %s" % ("全绿" if not FAIL else "%d 条红" % len(FAIL)))
    return 0 if not FAIL else 1


def P_rel(p):
    return p.replace("\\", "/").split(".diag/")[-1]


if __name__ == "__main__":
    sys.exit(main())
