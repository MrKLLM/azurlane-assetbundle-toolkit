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
window.__ERR=null; window.__DONE=false;
fetch(Q.get('side')||'').then(r=>r.json()).then(j=>{window.__SIDE=j;}).catch(()=>{window.__SIDE=null;}); window.__RESULT=null; window.__VIEWS=[]; window.__cur=0;
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
function loadTex(u){ return new Promise((res,rej)=>{
  new THREE.TextureLoader().load(u, t=>res(t), undefined, e=>rej(e&&e.message||u)); }); }
async function applyLightmaps(root, side, mode){
  // 贴图是异步解码的：不等它们落地就截图，拍到的是**没有 lightmap 的那一帧**
  // （本轮真实踩过：五个机位的落笔占比与未挂 lightmap 版**逐位相同**才发现）。
  const pages={};
  for(const p of side.pages){
    // 绝对路径：harness 自己就在 /dorm3d_room/ 下，相对写法会把目录叠成
    // /dorm3d_room/dorm3d_room/lightmaps/... 而 404（TextureLoader 的 onError 会 reject，
    // 正好被上面的 catch 抓住 —— 之前用不 await 的 tl.load() 时它静默返回占位贴图，
    // 于是"挂了 lightMap 的版"与"没挂的版"落笔占比逐位相同）
    const t=await loadTex('/dorm3d_room/lightmaps/'+p.file);
    t.colorSpace = (mode==='srgb')?THREE.SRGBColorSpace:THREE.NoColorSpace;
    t.flipY=false;                     // Unity lightmap 与我们的 UV 同向，多翻一次就上下错位
    pages[p.index]=t;
  }
  let n=0; const uniq=new Set();
  root.traverse(o=>{ if(!o.isMesh||!o.material) return;
    const ms=Array.isArray(o.material)?o.material:[o.material];
    for(const m of ms){ const pg=(m.userData&&m.userData.lmPage);
      if(pg===undefined||!pages[pg]) continue;
      m.lightMap=pages[pg]; m.lightMapIntensity=1.0; m.needsUpdate=true; n++; uniq.add(m.uuid); } });
  return {mats:n, uniqMats:uniq.size, pages:Object.keys(pages).length};
}
fetch(Q.get('truth')).then(r=>r.json()).then(truth=>{
  window.__TRUTH=truth;
  new GLTFLoader().load(Q.get('m'), async g=>{
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
    let uv1geoms=0, pagemats=0;
    g.scene.traverse(o=>{ o.frustumCulled=false;
      if(o.isMesh&&o.geometry&&o.geometry.attributes.uv1) uv1geoms++;
      const ms=o.isMesh?(Array.isArray(o.material)?o.material:[o.material]):[];
      for(const m of ms){ const pg=m&&m.userData&&m.userData.unityLightmapPage;
        if(pg!==undefined&&pg!==null){ m.userData.lmPage=pg; pagemats++; } } });
    window.__UV1={geoms:uv1geoms, pagemats};
    let lmApplied={mats:0,uniqMats:0,pages:0};
    if(Q.get('lm')==='1'){
      try {
        // sidecar 与模型是两条并发请求，谁先到不确定 ⇒ 这里**自己等它**，不赌时序
        if(!window.__SIDE && Q.get('side')){
          window.__SIDE = await fetch(Q.get('side')).then(r=>r.json());
        }
        lmApplied=await applyLightmaps(g.scene, window.__SIDE||{pages:[]}, Q.get('lmc')||'linear');
      } catch(e){ window.__ERR=(window.__ERR||'')+' lightmap 载入失败 '+String(e).slice(0,140); }
    }
    window.__LM=lmApplied;

    g.scene.updateMatrixWorld(true);
    const inner=truth.per_object.filter(p=>p.center&&Math.max(...p.center.map(Math.abs))<=15);
    window.__VIEWS=[
      {name:'game', pos:truth.camera.pos, look:truth.camera.pos.map((v,i)=>v+truth.camera.fwd[i]*3.0), fov:60},
      {name:'az000', pos:[0, 6.5, -11], look:[0,1.2,0], fov:55},
      {name:'az090', pos:[11, 6.5, 0], look:[0,1.2,0], fov:55},
      {name:'az180', pos:[0, 6.5, 11], look:[0,1.2,0], fov:55},
      {name:'top', pos:[7.5, 12.5, 7.5], look:[0,0.6,0], fov:55}];
    window.__STATS={meshObjects:meshes.length, posTotal, lights,
                    lmMats:(window.__LM||{}).uniqMats||0, lmSlots:(window.__LM||{}).mats||0,
                    lmPages:(window.__LM||{}).pages||0, sideOk:!!window.__SIDE,
                    uv1Geoms:(window.__UV1||{}).geoms||0,
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


def page_sensitivity(side, work=WORK):
    """对照：把每个对象采样的 lightmap  texel 换到"错的一页"，看亮度变不变。

    变的比例高 ⇒ 页号分配是**承载信息**的（烘错页就会看出来）；几乎不变 ⇒ 这条通路是装饰。
    """
    from PIL import Image
    objs = side.get("objects") or []
    pages = {p["index"]: p for p in side.get("pages", [])}
    if not objs or len(pages) < 2:
        return None
    imgs = {}
    for i, p in pages.items():
        fp = os.path.join(work, "lightmaps", p["file"])
        if os.path.isfile(fp):
            imgs[i] = Image.open(fp).convert("RGB")
    keys = sorted(imgs)
    if len(imgs) < 2:
        return None

    def lum(pg, cx, cy):
        im = imgs[pg]
        x = min(im.width - 1, max(0, int(cx * im.width)))
        y = min(im.height - 1, max(0, int(cy * im.height)))
        box = 3
        tot = [0, 0, 0]
        n = 0
        for dx in range(-box, box + 1):
            for dy in range(-box, box + 1):
                px = min(im.width - 1, max(0, x + dx))
                py = min(im.height - 1, max(0, y + dy))
                r, g, b = im.getpixel((px, py))
                tot[0] += r; tot[1] += g; tot[2] += b; n += 1
        return 0.2126 * tot[0] / n + 0.7152 * tot[1] / n + 0.0722 * tot[2] / n

    diff = 0
    tot = 0
    samples = []
    for o in objs:
        bb = o.get("uv1_bbox")
        if not bb or o["page"] not in imgs:
            continue
        cx = (bb[0][0] + bb[0][1]) / 2.0
        cy = (bb[1][0] + bb[1][1]) / 2.0
        a = lum(o["page"], cx, cy)
        wrong = [k for k in keys if k != o["page"]][0]
        b = lum(wrong, cx, cy)
        tot += 1
        if abs(a - b) > 0.05 * max(a, b, 1.0):
            diff += 1
        if len(samples) < 3:
            samples.append((o["object"], round(a, 1), round(b, 1)))
    return {"tot": tot, "diff": diff, "ratio": (diff / tot) if tot else 0.0,
            "samples": samples}


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
        rel_side = "dorm3d_room/" + os.path.splitext(os.path.basename(glb))[0] + ".lightmaps.json"
        side_p = os.path.join(WORK, os.path.basename(rel_side))
        side = json.load(open(side_p, encoding="utf-8")) if os.path.isfile(side_p) else None
        if side:
            lmcase = run_case(browser, base, rel_glb, rel_truth, "lm", {"names": names},
                              extra="&lm=1&side=%s" % (base + rel_side))
            lst = (lmcase or {}).get("stats") or {}
            say(lst.get("lmMats", 0) == len(side.get("material_pages", {})),
                "L1 前端挂上 lightMap 的**去重材质数** == sidecar 声明: %s vs %d"
                "（槽位数 %s 是 primitive 级的另一个母体，别混）"
                % (lst.get("lmMats"), len(side.get("material_pages", {})), lst.get("lmSlots")))
            say(lst.get("uv1Geoms", 0) == side.get("lm_prims", -1),
                "L2 前端带 uv1 属性的几何数 == 真值烘焙 primitive 数: %s vs %d"
                "（GLTFLoader 一个 primitive 建一个 geometry，所以母体是 primitive 不是对象）"
                % (lst.get("uv1Geoms"), side.get("lm_prims", -1)))
            ps = page_sensitivity(side)
            say(ps and ps["ratio"] >= 0.6,
                "C3 页号敏感性：把每个对象换到**错的一页**后，亮度变化 >5%% 的对象占比 "
                "%s（%s/%s）—— 占比太低说明页号分配不影响画面，这条通路是装饰"
                % (None if not ps else round(ps["ratio"], 3),
                   None if not ps else ps["diff"], None if not ps else ps["tot"]))
            lmk = {v["name"]: (round(v["ink"], 3) if v["ink"] is not None else None)
                   for v in (lmcase or {}).get("views", [])}
            print("  ℹ lightmap 版各机位落笔 %s；截图 shot_lm_*.png" % lmk)
            print("     lm 版 stats=%s err=%r" % (json.dumps(lst, ensure_ascii=False)[:260],
                                                  ((lmcase or {}).get('err') or '')[:260]))
        else:
            print("  ⚠ 没有 sidecar（%s）—— L1/L2/C3 无从判起" % rel_side)
            FAIL.append("缺 lightmap sidecar")
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
