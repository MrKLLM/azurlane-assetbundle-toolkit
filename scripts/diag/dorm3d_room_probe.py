"""room.glb 进 three.js 的验收探针：把画面变成**数**，并给每条 ✅ 配一条会红的对照。

为什么不写"加载没报错就算过"：GLB 解析成功只证明文件合法，证明不了摆位、朝向、光照
和"到底有没有东西画出来"。这一步量的每一条都落在**前端真实读数** vs **源包口径真值**
（`room.glb.truth.json`，由装配器从 Unity 声明字段算出，不是我写进 GLB 的那份字节）上。

    py -3 scripts/diag/dorm3d_room_probe.py
    py -3 scripts/diag/dorm3d_room_probe.py --glb .diag/dorm3d_room/sample80.glb

判据：
  J1 前端 Mesh 对象数 == 真值 primitive 数
  J2 前端 Σ position.count == 真值 position 计数
  J3 renderer 画的三角数 == 真值三角数 + 半透明双面网格的两遍绘制（期望值自己从文件推，
     不靠放宽阈值；three.js 对 transparent+DoubleSide 先画背面再画正面）
  J4 前端世界盒（只算非占位对象）vs 真值世界盒，逐轴相对差 < 0.5%
  J5 浏览器 console 零 error
  J6 游戏机位那张截图的落笔占比 >= 0.15（画面里真的有被照亮的内容）
  L1/L2 挂上 lightMap 的去重材质数、带 uv1 的几何数 vs sidecar/真值
  L3 每个挂 lightMap 的槽位：texture.channel 必须为 1 且几何带 uv1（r152+ 按 channel 选 UV）
  R1/R2 补光与灯的统计来自**场景包里的 RenderSettings**，不是手填常数
反向对照（不是装饰，是把 J1..J6 从恒真里区分出来）：
  C1 指向不存在的 glb ⇒ J1/J2/J3 必须全为 0（否则计数判据根本没在量东西）
  C2 把所有灯摘掉再渲染 ⇒ J6 的落笔占比必须塌到 <0.05（否则"有像素"不等于"有内容"）
  C3 把每个对象换到错的一页 lightmap ⇒ 亮度必须大面积变化（否则页号是装饰）
  C4 lightmap 走 UV1 vs 走 UV0 ⇒ 分布必须不同（**用 med 等分布量，整页均值测不出来**）
  C5 灯=0 且无 lightmap 且无环境光 ⇒ mean 必须 ≈0（否则"亮"是渲染器白送的）
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
import urllib.error
import urllib.parse
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
LAST_TABS = None


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
// 色调映射与曝光：游戏那侧明显有 tonemap（窗光渐变/木地板高光都不是线性直出的样子）
const TONES={none:THREE.NoToneMapping, linear:THREE.LinearToneMapping, reinhard:THREE.ReinhardToneMapping,
             cineon:THREE.CineonToneMapping, aces:THREE.ACESFilmicToneMapping};
renderer.toneMapping = TONES[Q.get('tone')||'none'];
renderer.toneMappingExposure = parseFloat(Q.get('exp')||'1');
const scene=new THREE.Scene(); const camera=new THREE.PerspectiveCamera(60,W/H,0.02,3000);
// 泛光：参照图窗边那道斜射光与整幅的乳白感是**屏幕空间后处理**，不在资产里
// （本场景的 109 个粒子只有 14 个激活，全是＋标记/图标/数字/轨迹，见 §126），
// 所以它是渲染端的一条轴，而不是"包里的数据没导出来"。
renderer.info.autoReset=false;      // 自己管计数，见下面 draw()
let sceneTris=0;
const _origRender=renderer.render.bind(renderer);
renderer.render=function(sc,ca){ _origRender(sc,ca); if(sc===scene) sceneTris=renderer.info.render.triangles; };
let composer=null, bloomPass=null;
const BLOOM=parseFloat(Q.get('bloom')||'0');
if(BLOOM>0){
  const [EC,RP,UB,OP]=await Promise.all([
    import('three/addons/postprocessing/EffectComposer.js'),
    import('three/addons/postprocessing/RenderPass.js'),
    import('three/addons/postprocessing/UnrealBloomPass.js'),
    import('three/addons/postprocessing/OutputPass.js')]);
  composer=new EC.EffectComposer(renderer);
  composer.addPass(new RP.RenderPass(scene,camera));
  bloomPass=new UB.UnrealBloomPass(new THREE.Vector2(W,H), BLOOM,
                                   parseFloat(Q.get('bloomr')||'0.6'),
                                   parseFloat(Q.get('bloomt')||'0.85'));
  composer.addPass(bloomPass);
  composer.addPass(new OP.OutputPass());   // 色调映射与 sRGB 输出改由这一道做
}
function draw(){ renderer.info.reset(); if(composer) composer.render(); else renderer.render(scene,camera); }
window.__ERR=null; window.__DONE=false;
fetch(Q.get('side')||'').then(r=>r.json()).then(j=>{window.__SIDE=j;}).catch(()=>{window.__SIDE=null;}); window.__RESULT=null; window.__VIEWS=[]; window.__cur=0;
window.__RENDER=null;
if(Q.get('render')) fetch(Q.get('render')).then(r=>r.json()).then(j=>{window.__RENDER=j;}).catch(()=>{window.__RENDER=null;});
function frameStats(){ // 与参照截图**同一套**裁剪(左右 8%、上 14%、下 15%)与亮度算法
  const c=document.createElement('canvas'); c.width=W; c.height=H;
  const x=c.getContext('2d'); x.drawImage(renderer.domElement,0,0);
  const x0=Math.floor(W*0.08), x1=Math.floor(W*0.92), y0=Math.floor(H*0.14), y1=Math.floor(H*0.85);
  const d=x.getImageData(x0,y0,x1-x0,y1-y0).data;
  const L=[]; let sat=0;
  for(let i=0;i<d.length;i+=4*7){ const r=d[i],g=d[i+1],b=d[i+2];
    L.push((0.2126*r+0.7152*g+0.0722*b)/255); sat+=(Math.max(r,g,b)-Math.min(r,g,b))/255; }
  L.sort((a,b)=>a-b); const n=L.length;
  const q=t=>L[Math.min(n-1,Math.floor(n*t))];
  const bs=L.filter(v=>v<=0.6);
  return {mean:L.reduce((a,b)=>a+b,0)/n, med:q(0.5), p05:q(0.05), p25:q(0.25), p75:q(0.75), p95:q(0.95),
          hi:L.filter(v=>v>0.75).length/n, lo:L.filter(v=>v<0.25).length/n, sat:sat/n,
          hi6:L.filter(v=>v>0.6).length/n, base6:bs.length?bs.reduce((a,b)=>a+b,0)/bs.length:0,
          samples:n};
}
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
async function applyLightmaps(root, side, mode, inten, chan){
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
    // **承重的一行**：three.js r152+ 的贴图通道由 `texture.channel` 决定，默认 0 ⇒
    // `vLightMapUv` 取的是 `uv`（漫反射 UV），而 Unity 的烘焙矩形在第二套 UV。
    // 我们手工赋 material.lightMap 时绕过了 GLTFLoader 的 assignLightmapOnMaterial
    // （它会显式设 channel=1），于是 lightmap 一直按错的 UV 采样，而计数类判据看不出来。
    t.channel = chan;
    pages[p.index]=t;
  }
  let n=0; const uniq=new Set(); let chanOk=0, chanBad=0;
  root.traverse(o=>{ if(!o.isMesh||!o.material) return;
    const ms=Array.isArray(o.material)?o.material:[o.material];
    for(const m of ms){ const pg=(m.userData&&m.userData.lmPage);
      if(pg===undefined||!pages[pg]) continue;
      m.lightMap=pages[pg]; m.lightMapIntensity=inten; m.needsUpdate=true; n++; uniq.add(m.uuid);
      // 直接量「采样用的是哪套 UV」这个可观测状态，而不是等亮度自己去暴露
      if(pages[pg].channel===1 && o.geometry && o.geometry.attributes.uv1) chanOk++; else chanBad++; } });
  return {mats:n, uniqMats:uniq.size, pages:Object.keys(pages).length, channel:chan,
          chanOk:chanOk, chanBad:chanBad};
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
    // 数一遍「会被 two-sided 透明两遍绘制」的三角数：J3 的期望值要用它自己推，
    // 不能靠把恒等式改成不等式来糊过去。
    let blendTris=0;
    for(const o of meshes){ const gi=o.geometry; if(!gi) continue;
      const tr = gi.index ? gi.index.count/3
               : (gi.attributes.position ? gi.attributes.position.count/3 : 0);
      const ms=Array.isArray(o.material)?o.material:[o.material];
      if(ms.some(m=>m&&m.transparent)) blendTris+=tr; }
    // hidekw=<正则>：把材质名命中的网格藏掉。消融用——"这块黑到底是玻璃挡着，
    // 还是外面压根没东西"这类问题，只有把它藏起来看后果才能区分。
    let hidden=0;
    if(Q.get('hidekw')){ const re=new RegExp(Q.get('hidekw'),'i');
      g.scene.traverse(o=>{ if(!o.isMesh||!o.material) return;
        const ms=Array.isArray(o.material)?o.material:[o.material];
        if(ms.some(m=>m&&re.test(m.name||''))){ o.visible=false; hidden++; } }); }
    if(Q.get('nolight')==='1'){ const kill=[]; g.scene.traverse(o=>{ if(o.isLight) kill.push(o); });
      kill.forEach(o=>o.parent&&o.parent.remove(o)); }
    // 灯的量纲：Unity 的 m_Intensity 是「倍数」，three.js r160 默认 useLegacyLights=false
    // ⇒ 点/聚光按**坎德拉**走 1/d² 衰减，平行光的漫反射又额外除了一个 π。
    // 直接照搬数值会系统性偏暗，所以这里把「乘多少」当成一条可扫的轴，而不是猜一个常数。
    const LI=parseFloat(Q.get('li')||'1'), LD=parseFloat(Q.get('ld')||'1');
    const dcRaw=Q.get('dc');
    let lightTouched=0;
    g.scene.traverse(o=>{ if(!o.isLight) return;
      if(o.isPointLight||o.isSpotLight){ o.intensity*=LI;
        if(dcRaw!==null) o.decay=parseFloat(dcRaw); }
      else if(o.isDirectionalLight){ o.intensity*=LD; }
      lightTouched++; });
    // 补光：优先用**包里的** RenderSettings 三向环境光（m_AmbientMode/EIntensity/Equator/Ground），
    // 而不是随手给的白色 AmbientLight。颜色按 sRGB→线性换不换，也是一条轴（ambsrgb）。
    const AMBM=Q.get('ambm')||'';
    const ambInfo={mode:AMBM||'none', used:0};
    if(AMBM==='flat'||AMBM==='hemi'){
      // 与 sidecar 同理：这条 fetch 与模型加载并发，谁先到不确定 ⇒ 自己等它
      if(!window.__RENDER && Q.get('render')){
        window.__RENDER = await fetch(Q.get('render')).then(r=>r.json()).catch(()=>null);
      }
      const A=((window.__RENDER||{}).ambient)||{};
      if(!A.equator||!A.ground){ window.__ERR=(window.__ERR||'')+' 环境光数据缺失（room.render.json 没读到）'; }
      const conv=(Q.get('ambsrgb')==='1')?(c=>c<=0.04045?c/12.92:Math.pow((c+0.055)/1.055,2.4)):(c=>c);
      const mul=parseFloat(Q.get('ambk')||'1')*(parseFloat(A.intensity)||1);
      const C=a=>new THREE.Color(conv(a[0]),conv(a[1]),conv(a[2]));
      // flat 取 equator（Unity trilight 在水平朝上的面上给的就是 equator 这一项），
      // hemi 取 sky/ground 两端（sky 本包里是 0，会把上半球压成纯黑 —— 两种都摆出来对比）
      const col=(AMBM==='flat')?(A.equator||[1,1,1]):(A.sky||[1,1,1]);
      const lc=(AMBM==='flat')?null:(A.ground||[0,0,0]);
      const L=(AMBM==='flat')?new THREE.AmbientLight(C(col),mul)
                             :new THREE.HemisphereLight(C(col),C(lc),mul);
      scene.add(L); ambInfo.used=1; ambInfo.color=col; ambInfo.intensity=mul;
    } else if(parseFloat(Q.get('amb')||'0')>0){
      scene.add(new THREE.AmbientLight(0xffffff, parseFloat(Q.get('amb'))));   // 旧的手工补光，仅对照
      ambInfo.mode='white'; ambInfo.used=1;
    }
    let uv1geoms=0, pagemats=0;
    g.scene.traverse(o=>{ o.frustumCulled=false;
      if(o.isMesh&&o.geometry&&o.geometry.attributes.uv1) uv1geoms++;
      const ms=o.isMesh?(Array.isArray(o.material)?o.material:[o.material]):[];
      for(const m of ms){ const pg=m&&m.userData&&m.userData.unityLightmapPage;
        if(pg!==undefined&&pg!==null){ m.userData.lmPage=pg; pagemats++; } } });
    window.__UV1={geoms:uv1geoms, pagemats};
    let lmApplied={mats:0,uniqMats:0,pages:0,channel:0};
    if(Q.get('lm')==='1'){
      try {
        // sidecar 与模型是两条并发请求，谁先到不确定 ⇒ 这里**自己等它**，不赌时序
        if(!window.__SIDE && Q.get('side')){
          window.__SIDE = await fetch(Q.get('side')).then(r=>r.json());
        }
        lmApplied=await applyLightmaps(g.scene, window.__SIDE||{pages:[]},
                                       Q.get('lmc')||'linear',
                                       parseFloat(Q.get('lmi')||'1'),
                                       parseInt(Q.get('lmch')||'1',10));
      } catch(e){ window.__ERR=(window.__ERR||'')+' lightmap 载入失败 '+String(e).slice(0,140); }
    }
    window.__LM=lmApplied;

    g.scene.updateMatrixWorld(true);
    const inner=truth.per_object.filter(p=>p.center&&Math.max(...p.center.map(Math.abs))<=15);
    const ext=Q.get('views');
    if(ext){ window.__VIEWS=JSON.parse(decodeURIComponent(ext)); }
    else window.__VIEWS=[
      {name:'game', pos:truth.camera.pos, look:truth.camera.pos.map((v,i)=>v+truth.camera.fwd[i]*3.0), fov:60},
      {name:'az000', pos:[0, 6.5, -11], look:[0,1.2,0], fov:55},
      {name:'az090', pos:[11, 6.5, 0], look:[0,1.2,0], fov:55},
      {name:'az180', pos:[0, 6.5, 11], look:[0,1.2,0], fov:55},
      {name:'top', pos:[7.5, 12.5, 7.5], look:[0,0.6,0], fov:55}];
    window.__STATS={meshObjects:meshes.length, posTotal, lights, blendTris,
                    tone:Q.get('tone')||'none', exp:parseFloat(Q.get('exp')||'1'),
                    lmMats:(window.__LM||{}).uniqMats||0, lmSlots:(window.__LM||{}).mats||0,
                    lmPages:(window.__LM||{}).pages||0, sideOk:!!window.__SIDE,
                    lmChannel:(window.__LM||{}).channel,
                    lmChanOk:(window.__LM||{}).chanOk||0, lmChanBad:(window.__LM||{}).chanBad||0,
                    lmIntensity:parseFloat(Q.get('lmi')||'1'),
                    lmColor:(Q.get('lmc')||'linear'), lightsTouched:lightTouched,
                    amb:ambInfo, ambSrgb:(Q.get('ambsrgb')==='1'),
                    renderOk:!!window.__RENDER, li:LI, ld:LD, decay:dcRaw,
                    hidden:hidden, hidekw:Q.get('hidekw')||'',

                    uv1Geoms:(window.__UV1||{}).geoms||0,
                    renderedTris:0, bloom:BLOOM,
                    boxAll:boxOf(meshes,false), boxReal:boxOf(meshes,true),
                    innerCount:inner.length, distinctNames:Object.keys(names).length};
    draw();
    window.__STATS.renderedTris=sceneTris;
    const rc=new THREE.Raycaster();
    // 每个机位沿视线打 9 个采样点，回报"这个像素上到底是哪个对象/哪个材质"——
    // 窗那片黑用亮度测不出来源，只有把命中对象列出来才能区分"玻璃挡着"与"外面没东西"。
    const PICKPTS=[[-0.5,0.35],[0,0.35],[0.5,0.35],[-0.5,0],[0,0],[0.5,0],[-0.5,-0.35],[0,-0.35],[0.5,-0.35]];
    function picksAt(){ return PICKPTS.map(p=>{ rc.setFromCamera(new THREE.Vector2(p[0],p[1]),camera);
      const h=rc.intersectObjects(scene.children,true).filter(x=>x.object.visible).slice(0,3);
      return {ndc:p.map(v=>+v.toFixed(2)), hits:h.map(x=>({n:String(x.object.name||'').slice(0,26),
              m:String((x.object.material&&x.object.material.name)||'').slice(0,26),
              d:+x.distance.toFixed(2)}))}; }); }
    window.applyView=i=>{ const v=window.__VIEWS[i];
      camera.position.set(...v.pos); camera.up.set(0,1,0); camera.fov=v.fov;
      camera.lookAt(new THREE.Vector3(...v.look)); camera.updateProjectionMatrix();
      draw(); window.__cur=i;
      const k=ink(); const f=frameStats();
      let pk=[]; try{ pk=picksAt(); }catch(e){ pk=[{err:String(e).slice(0,80)}]; }
      return {ink:k.ink, mean:f.mean, med:f.med, p05:f.p05, p25:f.p25, p75:f.p75, p95:f.p95, hi:f.hi, lo:f.lo,
              hi6:f.hi6, base6:f.base6, sat:f.sat, picks:pk}; };
    window.__DONE=true;
  }, undefined, e=>{ window.__ERR=String(e&&e.message||e).slice(0,300);
    window.__STATS={meshObjects:0,posTotal:0,lights:0,renderedTris:0,boxAll:null,boxReal:null,
                    innerCount:0,distinctNames:0};
    window.applyView=()=>({ink:0}); window.__DONE=true; });
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


ZONE_ANCHORS = {
    "bedroom": ["Bed", "Cabinet", "ChairFrontDesk", "FittingRoom"],
    "living": ["Sofa", "Table", "Chair_1", "Chair_2", "Fireplace", "Lamp"],
    "kitchen": ["Kitchen", "TableKitchen", "ChairKitchen"],
}


def zone_views(glb_path):
    """按**场景里按名字命名的锚点**算分区域机位（不是手调坐标）。

    相机放在"簇中心 -> 房间中心"这条线上、退到簇外 3.2 单位，眼高 1.45，看向簇心 0.8 高处。
    锚点世界位置从 GLB 的节点 TRS 复算（与 --verify 的镜像锚点同一套矩阵代码）。
    """
    import struct
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import dorm3d_room_to_gltf as A
    raw = open(glb_path, "rb").read()
    jl, _t = struct.unpack_from("<II", raw, 12)
    g = json.loads(raw[20:20 + jl].decode("utf-8"))
    nodes = g["nodes"]
    kids = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            kids[c] = i

    def world(i, memo={}):
        if i in memo:
            return memo[i]
        n = nodes[i]
        M = A._quat_mat(n.get("translation", [0, 0, 0]), n.get("rotation", [0, 0, 0, 1]),
                        n.get("scale", [1, 1, 1]))
        p = kids.get(i)
        if p is not None:
            PM = world(p)
            M = A._mul(PM[0], PM[1], M[0], M[1])
        memo[i] = M
        return M

    pos_of = {}
    for i, n in enumerate(nodes):
        if n.get("name") in sum(ZONE_ANCHORS.values(), []):
            pos_of.setdefault(n["name"], []).append(world(i)[1])
    allp = [q for v in pos_of.values() for q in v]
    centre = [sum(q[k] for q in allp) / len(allp) for k in range(3)]
    views = []
    for zone, names in ZONE_ANCHORS.items():
        pts = [q for nm in names for q in pos_of.get(nm, [])]
        if not pts:
            continue
        c = [sum(q[k] for q in pts) / len(pts) for k in range(3)]
        # 相机放在簇中心**朝房间中心那一侧**（放反就穿到墙外，会被墙挡住）
        dx, dz = centre[0] - c[0], centre[2] - c[2]
        L = max(1e-6, (dx * dx + dz * dz) ** 0.5)
        back = min(3.2, max(1.6, L * 0.9))
        views.append({"name": zone, "n": len(pts),
                      "pos": [round(c[0] + dx / L * back, 3), 1.45, round(c[2] + dz / L * back, 3)],
                      "look": [round(c[0], 3), 0.8, round(c[2], 3)], "fov": 62})
    return views, {k: [round(x, 2) for x in centre] for k in ["_centre"]}


REF_CROP = (0.08, 0.14, 0.92, 0.85)   # 与 harness 的 frameStats 同一套裁剪


def ref_stats(ref_dir):
    """游戏内截图的亮度分布（裁掉 UI），当作可调档位的量化目标。"""
    import glob
    from PIL import Image
    out = []
    for f in sorted(glob.glob(os.path.join(ref_dir, "*.png")) + glob.glob(os.path.join(ref_dir, "*.jpg"))):
        im = Image.open(f).convert("RGB")
        w, h = im.size
        c = im.crop((int(w * REF_CROP[0]), int(h * REF_CROP[1]),
                     int(w * REF_CROP[2]), int(h * REF_CROP[3])))
        px = list(c.getdata())[::7]
        L = sorted((0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0 for r, g, b in px)
        n = len(L)
        q = lambda t: L[min(n - 1, int(n * t))]
        sat = sum(max(p) - min(p) for p in px) / 255.0 / n
        out.append({"file": os.path.basename(f)[:10], "mean": sum(L) / n, "med": q(0.5),
                    "p05": q(0.05), "p25": q(0.25), "p75": q(0.75), "p95": q(0.95),
                    "hi": sum(1 for v in L if v > 0.75) / n, "lo": sum(1 for v in L if v < 0.25) / n,
                    # hi6/base6：把"亮部面积不够"与"室内中间调偏暗"这两半**分开量**，
                    # 否则一个 mean 把两件事混在一起，会误判成"再抬点亮度就行"
                    "hi6": sum(1 for v in L if v > 0.6) / n,
                    "base6": (sum(v for v in L if v <= 0.6) / max(1, sum(1 for v in L if v <= 0.6))),
                    "sat": sat})
    return out


def grade_sweep(browser, base, rel_glb, rel_truth, rel_side, rel_render, views, target, presets):
    """逐档扫亮度相关的轴（tonemap/曝光/环境光/灯量纲/lightmap 通道与色彩空间），
    比与参照图的亮度距离；几何计数不许变（那是护栏）。"""
    vq = urllib.parse.quote(json.dumps(views, ensure_ascii=False))
    rows = []
    keys = ("mean", "med", "p05", "p25", "p75", "p95", "hi", "lo", "hi6", "base6", "sat")
    for p in presets:
        q = preset_query(p, base, rel_side, rel_render, vq)
        tag = p.get("tag") or ("%s/%s" % (p.get("tone", "none"), p.get("exp", 1)))
        # 带 shot=<短名> 的档位顺手出图：哪几档值得人眼看，是档位自己的属性
        shot = p.get("shot")
        st = run_case(browser, base, rel_glb, rel_truth,
                      "grade" + ("_" + str(shot) if shot else ""),
                      {"names": [v["name"] for v in views]}, capture=bool(shot), extra=q)
        if not st:
            continue
        stt = st["stats"] or {}
        avg = {k: sum(v.get(k, 0.0) for v in st["views"]) / max(1, len(st["views"])) for k in keys}
        # 排序用**分位数距离**（p05/p25/p50/p75/p95，Wasserstein-1 的代理）：
        # 逐键绝对误差平均的那种距离，会被"整幅一起变亮"骗过去——本轮真实踩过，
        # 一个把画面糊成白的档位拿到过最小距离 0.086。均值距离只留着当对照展示。
        QS = ("p05", "p25", "med", "p75", "p95")
        qd = sum(abs(avg[k] - target[k]) for k in QS) / len(QS)
        # 饱和度必须进距离：只量亮度的话，"白色泛光糊一遍"和"画面里真有一块蓝天碧海"
        # 在分位数上几乎同分（本轮实测前者 sat 0.078 vs 参照 0.178）。
        qd += abs(avg["sat"] - target["sat"])
        md = sum(abs(avg[k] - target[k]) for k in keys) / len(keys)
        rows.append({"tag": tag, "preset": dict(p), "avg": avg, "dist": qd, "mean_dist": md,
                     "stats": {k: stt.get(k) for k in ("lmChannel", "amb", "lightsTouched",
                                                       "renderOk", "sideOk", "lmMats")},
                     "counts": (stt.get("meshObjects"), stt.get("posTotal"), stt.get("renderedTris")),
                     "per_view": {v["name"]: round(v.get("mean", 0), 3) for v in st["views"]}})
    return rows


def preset_query(p, base, rel_side, rel_render, vq):
    q = "&lm=%s&side=%s&views=%s" % (p.get("lm", 1), base + rel_side, vq)
    if rel_render:
        q += "&render=%s" % (base + rel_render)
    for k in ("tone", "exp", "lmc", "lmi", "lmch", "ambm", "ambk", "ambsrgb", "li", "ld", "dc",
              "bloom", "bloomr", "bloomt"):
        if p.get(k) is not None:
            q += "&%s=%s" % (k, p[k])
    if p.get("nolight"):
        q += "&nolight=1"
    return q


def render_settings(scene, out_path):
    """把场景包里的 RenderSettings（三向环境光）与灯的强度/射程抄成一份 json 给前端用。

    为什么单独出这份文件：环境光颜色是**包里的数据**，把它硬写进 harness 就等于
    用我的猜测当事实；前端读数与源包口径必须能对上同一张表。
    """
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    sys.path.insert(0, os.path.join(ROOT, "scripts", "diag"))
    import dorm3d_pptr_resolve as P
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
    scene = scene or P.DEF_SCENE
    env = UnityPy.load(scene)
    out = {"scene": os.path.basename(scene), "ambient": None, "lights": {}, "notes": []}
    _LT = {0: "spot", 1: "directional", 2: "point", 3: "area"}
    hist = {}
    for o in env.objects:
        tn = o.type.name
        if tn == "RenderSettings":
            rs = o.read()

            def rgb(v):
                return [round(float(getattr(v, k, 0.0)), 5) for k in ("r", "g", "b")]
            out["ambient"] = {
                "mode": int(getattr(rs, "m_AmbientMode", 0) or 0),
                "intensity": float(getattr(rs, "m_AmbientIntensity", 1.0) or 1.0),
                "sky": rgb(getattr(rs, "m_AmbientSkyColor", None)),
                "equator": rgb(getattr(rs, "m_AmbientEquatorColor", None)),
                "ground": rgb(getattr(rs, "m_AmbientGroundColor", None)),
                "probe_nonzero": any(abs(float(getattr(rs.m_AmbientProbe, "sh_%02d_" % s, 0.0) or 0.0)) > 1e-6
                                     for s in range(27)),
                "sun": bool(getattr(rs.m_Sun, "path_id", 0)),
                "fog": bool(getattr(rs, "m_Fog", False)),
            }
        elif tn == "Light":
            L = o.read()
            tv = getattr(L, "m_Type", 0)
            kind = _LT.get(int(tv.value) if hasattr(tv, "value") else int(tv), "other")
            h = hist.setdefault(kind, {"n": 0, "intensity": []})
            h["n"] += 1
            try:
                h["intensity"].append(round(float(getattr(L, "m_Intensity", 0) or 0.0), 3))
            except Exception:
                pass
    for k, h in hist.items():
        h["intensity"] = {"min": min(h["intensity"]), "max": max(h["intensity"]),
                          "sum": round(sum(h["intensity"]), 3)}
    out["lights"] = hist
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out



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


def run_case(browser, base, glb_url, truth_url, tag, shots, extra="", capture=True):
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
    names = shots.get("names") or []
    for i in range(int(n)):
        ink = ev("JSON.stringify(window.applyView(%d))" % i)
        ink = json.loads(ink) if isinstance(ink, str) else ink
        shot = cmd("Page.captureScreenshot", {"format": "png"}) or {}
        png = shot.get("data")
        if png:
            with open(os.path.join(WORK, "shot_%s_%s.png" % (tag, names[i] if i < len(names) else i)), "wb") as f:
                f.write(base64.b64decode(png))
        views.append({"name": names[i] if i < len(names) else str(i),
                      **{k: v for k, v in (ink or {}).items() if k != "sampled"}})
    return {"stats": stats, "err": errtxt, "views": views}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", default=".diag/dorm3d_room/room.glb")
    ap.add_argument("--truth", default=None,
                    help="真值 json；缺省按 --glb 同名推导（不推导会拿旧版真值比新版模型）")
    ap.add_argument("--skip-controls", action="store_true", help="调试用；正式判定不许跳")
    ap.add_argument("--grade", action="store_true", help="扫色调映射档位，与游戏截图比亮度")
    ap.add_argument("--grade-limit", type=int, default=0,
                    help="只跑前 N 个档位（先验证接线再跑全网格，省一整轮）")
    ap.add_argument("--grade-tags", default="",
                    help="只跑标签含这些子串的档位（逗号分隔），如 泛光,包内环境光")
    ap.add_argument("--peek", action="store_true",
                    help="朝窗外看的消融机位（配合 hidekw 判断窗那片黑的原因）")
    ap.add_argument("--scene", default=None,
                    help="场景包（默认取 dorm3d_pptr_resolve.DEF_SCENE，用来抄 RenderSettings 环境光）")


    ap.add_argument("--ref-dir", default=r"C:/Users/KLLM/.qoder-cn/tmp/D--Azur-Lane-Assets/images/"
                                         "b19275a3-b2ab-4186-a6a1-5a07525583dd")
    ap.add_argument("--zones", action="store_true",
                    help="按场景锚点补拍三个分区域机位（卧室/起居/厨房），不参与判定，只出图")
    a = ap.parse_args()
    glb = os.path.join(ROOT, a.glb) if not os.path.isabs(a.glb) else a.glb
    if a.truth is None:
        # 装配器落的是 "<glb>.truth.json"（在 .glb 之后追加），不是换掉扩展名
        a.truth = a.glb + ".truth.json"

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
    if os.environ.get("AL_DEBUG"):
        print("[dbg] argv=%r" % (proc.args,))
        print("[dbg] chrome pid=%s profile=%s port=%d" % (proc.pid, PROFILE, PORT))
    try:
        import websocket
        ws = None
        for _try in range(120):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % PORT, timeout=5))
                globals()["LAST_TABS"] = [(t.get("type"), (t.get("url") or "")[:70]) for t in tabs][:5]
                u = [t["webSocketDebuggerUrl"] for t in tabs
                     if "harness.html" in t.get("url", "") and t.get("webSocketDebuggerUrl")]
                if u:
                    ws = websocket.create_connection(u[0], timeout=240, max_size=None)
                    break
            except (OSError, urllib.error.URLError, ValueError) as e:
                if os.environ.get("AL_DEBUG") and _try in (0, 4, 12, 30):
                    print("[dbg] /json 第 %d 次没连上 %s %s" % (_try, type(e).__name__, str(e)[:90]))
            except Exception as e:
                # 连不上可以等；NameError/UnboundLocalError 这类是**探针自己坏了**，
                # 继续静默重试只会把"脚本写错"伪装成"浏览器起不来"（本轮真实踩过 4 次）
                print("[FAIL] 轮询 /json 时探针自身出错: %s: %s" % (type(e).__name__, e))
                return 3
            time.sleep(0.5)
        if ws is None:
            print("[FAIL] 连不上浏览器：端口 %d 的 /json 最后一次 = %r；chrome rc=%s"
                  % (PORT, LAST_TABS, proc.poll()))
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
        # 半透明 + DoubleSide 的材质，three.js r160 会**画两遍**（先背面再正面，见 WebGLRenderer
        # 里 `transparent && side===DoubleSide && !forceSinglePass` 那个分支），
        # 所以恒等式右边必须是「真值 + 这批网格的三角数」，而不是把阈值放宽。
        # 期望值从文件里自己推：哪张网格用了 transparent 材质，就数它的索引三角形。
        blend = int(st.get("blendTris") or 0)
        say(st.get("renderedTris") == truth["tri_total"] + blend,
            "J3 renderer 三角数 == 真值 + 半透明双面二次绘制（frustumCulled 全关，应当恒等）: "
            "%s vs %d + %d" % (st.get("renderedTris"), truth["tri_total"], blend))
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
            say(lst.get("lmChanBad", 0) == 0 and lst.get("lmChanOk", 0) == lst.get("lmSlots", -1),
                "L3 每个挂了 lightMap 的槽位，其 channel 必须是 1 且几何带 uv1: 对 %s / 错 %s（母体 %s）"
                "—— three.js r152+ 按 texture.channel 选 UV，手工赋图时漏设就会拿漫反射 UV 采样"
                % (lst.get("lmChanOk"), lst.get("lmChanBad"), lst.get("lmSlots")))
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
        zone_v, _zc = zone_views(glb)
        if a.zones and side:
            views = zone_v
            zn = [v["name"] for v in views]
            zq = ("&lm=1&side=%s&views=%s"
                  % (base + rel_side, urllib.parse.quote(json.dumps(views, ensure_ascii=False))))
            zc = run_case(browser, base, rel_glb, rel_truth, "zone", {"names": zn}, extra=zq)
            print("  ℹ 分区域机位（相机放在房间中央朝各簇看，眼高 1.45；锚点来自场景命名物体）:")
            for v in views:
                print("     %s: %d 个锚点，相机 %s 看 %s" % (v["name"], v["n"], v["pos"], v["look"]))
            print("     各机位落笔 %s；截图 shot_zone_*.png"
                  % {v["name"]: (round(v["ink"], 3) if v["ink"] is not None else None)
                     for v in (zc or {}).get("views", [])})
        if a.peek:
            pk = [{"name": "out_sea", "pos": [0.0, 1.6, 2.0], "look": [0.0, 1.4, -30.0], "fov": 60},
                  {"name": "out_side", "pos": [-4.0, 1.6, 0.0], "look": [-30.0, 1.4, 0.0], "fov": 60}]
            pq = urllib.parse.quote(json.dumps(pk, ensure_ascii=False))
            print("  ℹ 朝窗外看的消融机位（判断窗那片黑是玻璃挡住还是外面没东西）:")
            for kw in ("", "glass", "curtain"):
                ex = "&views=%s" % pq + (("&hidekw=%s" % urllib.parse.quote(kw)) if kw else "")
                pc = run_case(browser, base, rel_glb, rel_truth, "peek" + (kw or "all"),
                              {"names": [v["name"] for v in pk]}, extra=ex)
                st2 = (pc or {}).get("stats") or {}
                print("     hidekw=%-8s 藏掉 %3s 个网格；各机位 mean=%s"
                      % (kw or "(不藏)", st2.get("hidden"),
                         {v["name"]: round(v.get("mean", 0), 3) for v in (pc or {}).get("views", [])}))
                for v in (pc or {}).get("views", []) if not kw else []:
                    for p in (v.get("picks") or []):
                        if p.get("hits"):
                            print("        %s ndc%-10s %s" % (v["name"], p["ndc"],
                                                              " | ".join("%s·%s@%s" % (h["n"], h["m"], h["d"])
                                                                        for h in p["hits"])))
        if a.grade and side:
            refs = ref_stats(a.ref_dir)
            if not refs:
                print("  ⚠ 参照图目录没有图：%s" % a.ref_dir)
            else:
                keys = ("mean", "med", "p05", "p25", "p75", "p95", "hi", "lo", "hi6", "base6", "sat")
                target = {k: sorted(r[k] for r in refs)[len(refs) // 2] for k in keys}
                print("  参照图（游戏内截图，裁掉 UI）%d 张：" % len(refs))
                for r in refs:
                    print("     %s mean=%.3f med=%.3f p95=%.3f 高光>0.75=%.1f%% 亮部>0.6=%.1f%% "
                          "其余均值=%.3f 暗部=%.1f%% 饱和=%.3f"
                          % (r["file"], r["mean"], r["med"], r["p95"], 100 * r["hi"], 100 * r["hi6"],
                             r["base6"], 100 * r["lo"], r["sat"]))
                print("     目标(取中位) " + " ".join("%s=%.3f" % (k, target[k]) for k in keys))
                rel_render = None
                rs_p = os.path.join(WORK, "room.render.json")
                try:
                    info = render_settings(a.scene, rs_p)
                    rel_render = "dorm3d_room/room.render.json"
                    print("  包里的环境光: %s" % json.dumps(info.get("ambient"), ensure_ascii=False))
                    print("  包里的灯: %s" % json.dumps(info.get("lights"), ensure_ascii=False))
                    say(bool(info.get("ambient")), "R1 场景包里读到了 RenderSettings 环境光（补光有据可依）")
                    say(bool(info.get("lights")), "R2 场景包里读到了灯统计（%d 类）" % len(info.get("lights") or {}))
                except Exception as ex:
                    print("  ⚠ RenderSettings 抄录失败: %s: %s" % (type(ex).__name__, ex))
                PI = 3.141592653589793
                presets = [
                    {"tag": "旧最优(纯tonemap)", "tone": "aces", "exp": "2.3"},
                    {"tag": "对照:lightmap走UV0", "tone": "aces", "exp": "2.3", "lmch": "0"},
                    {"tag": "对照:全关", "tone": "none", "exp": "1", "lm": "0",
                     "ambm": "", "li": "0", "ld": "0"},
                    {"tag": "包内环境光(sRGB入)", "tone": "aces", "exp": "1", "ambm": "flat", "ambsrgb": "1"},
                    {"tag": "包内环境光(线性入)", "tone": "aces", "exp": "1", "ambm": "flat"},
                    {"tag": "只把灯×π", "tone": "aces", "exp": "1", "li": PI, "ld": PI},
                    {"tag": "灯×π+去1/d²", "tone": "aces", "exp": "1", "li": PI, "ld": PI, "dc": "0"},
                    {"tag": "环境光+灯×π+去衰减", "tone": "aces", "exp": "1", "ambm": "flat",
                     "ambsrgb": "1", "li": PI, "ld": PI, "dc": "0"},
                    {"tag": "同上但线性tonemap", "tone": "none", "exp": "1", "ambm": "flat",
                     "ambsrgb": "1", "li": PI, "ld": PI, "dc": "0"},
                    {"tag": "同上但曝光1.4", "tone": "aces", "exp": "1.4", "ambm": "flat",
                     "ambsrgb": "1", "li": PI, "ld": PI, "dc": "0"},
                    {"tag": "同上但lightmap×2", "tone": "aces", "exp": "1", "ambm": "flat",
                     "ambsrgb": "1", "li": PI, "ld": PI, "dc": "0", "lmi": "2"},
                    {"tag": "同上但lightmap按sRGB", "tone": "aces", "exp": "1", "ambm": "flat",
                     "ambsrgb": "1", "li": PI, "ld": PI, "dc": "0", "lmc": "srgb"},
                    {"tag": "半球环境光(sky=0)", "tone": "aces", "exp": "1", "ambm": "hemi",
                     "ambsrgb": "1", "li": PI, "ld": PI, "dc": "0"},
                    # 泛光这条轴补的是"亮部面积"，不是"室内打光"——参照图高光占比 15~45%，我们 2~18%
                    {"tag": "环境光+泛光0.35", "tone": "aces", "exp": "1", "ambm": "flat",
                     "bloom": "0.35"},
                    {"tag": "环境光+泛光0.6", "tone": "aces", "exp": "1", "ambm": "flat",
                     "bloom": "0.6"},
                    {"tag": "环境光+泛光0.9", "tone": "aces", "exp": "1", "ambm": "flat",
                     "bloom": "0.9"},
                    {"tag": "泛光0.6+阈0.7", "tone": "aces", "exp": "1", "ambm": "flat",
                     "bloom": "0.6", "bloomt": "0.7"},
                    {"tag": "泛光0.6+曝光1.2", "tone": "aces", "exp": "1.2", "ambm": "flat",
                     "bloom": "0.6"},
                    {"tag": "泛光0.9+灯×π去衰减", "tone": "aces", "exp": "1", "ambm": "flat",
                     "bloom": "0.9", "li": PI, "ld": PI, "dc": "0"},
                    # 泛光与"灯×π/去衰减"**有交互**：单独扫灯几乎不动，配上泛光就暴涨
                    # （本轮实测 mean 0.316 → 0.549）。所以中间这些组合必须真的扫，
                    # 不能拿"单轴扫过、没用"结论省掉。
                    {"tag": "泛光0.35+灯×π去衰减", "tone": "aces", "exp": "1", "ambm": "flat",
                     "bloom": "0.35", "li": PI, "ld": PI, "dc": "0", "shot": "b35"},
                    {"tag": "泛光0.45+灯×π去衰减", "tone": "aces", "exp": "1", "ambm": "flat",
                     "bloom": "0.45", "li": PI, "ld": PI, "dc": "0", "shot": "b45"},
                    {"tag": "泛光0.6+灯×π去衰减", "tone": "aces", "exp": "1", "ambm": "flat",
                     "bloom": "0.6", "li": PI, "ld": PI, "dc": "0", "shot": "b60"},
                    {"tag": "泛光0.9+灯×π留衰减", "tone": "aces", "exp": "1", "ambm": "flat",
                     "bloom": "0.9", "li": PI, "ld": PI},
                ]
                if a.grade_tags:
                    want = [t.strip() for t in a.grade_tags.split(",") if t.strip()]
                    presets = [p for p in presets if any(w in (p.get("tag") or "") for w in want)]
                    print("  ℹ 按 --grade-tags %s 选了 %d 个档位" % (want, len(presets)))
                if a.grade_limit:
                    presets = presets[:a.grade_limit]
                    print("  ⚠ 只跑前 %d 个档位（--grade-limit），下面的对照/护栏可能没有母体" % len(presets))
                rows = grade_sweep(browser, base, rel_glb, rel_truth, rel_side, rel_render,
                                   zone_v, target, presets)
                print("  档位扫描（三个分区机位取平均）:")
                for r in sorted(rows, key=lambda x: x["dist"]):
                    a2 = r["avg"]
                    print("     %-24s 分位+饱和 %.3f (均值距离 %.3f) | mean %.3f med %.3f p05 %.3f "
                          "p95 %.3f 亮部>0.6 %.1f%% 其余 %.3f 暗部 %.1f%% sat %.3f"
                          % (r["tag"], r["dist"], r.get("mean_dist", 0), a2["mean"], a2["med"],
                             a2["p05"], a2["p95"], 100 * a2["hi6"], a2["base6"], 100 * a2["lo"], a2["sat"]))
                by_tag = {r["tag"]: r for r in rows}
                counts = set(r["counts"] for r in rows)
                say(len(counts) == 1 and rows and rows[0]["counts"] == (st.get("meshObjects"),
                                                                        st.get("posTotal"),
                                                                        st.get("renderedTris")),
                    "护栏：换档位**只许改亮度、不许改几何计数** %s" % (sorted(counts)[:2],))
                lum = set(round(r["avg"]["mean"], 3) for r in rows)
                say(len(lum) > 1, "护栏：档位之间亮度确实动了（实得 %d 个不同均值）" % len(lum))
                # C4：lightmap 走 UV1 与走 UV0 必须**不一样**——一样就说明这条通路
                # 根本没吃到第二套 UV（前一轮的计数判据对这种错是无感的）。
                # 注意只能用**分布**量：整页 lightmap 的均值本来就 ≈ 任一子矩形的均值，
                # 拿 mean 当仪器会测不出错（本轮实测 mean 只差 0.0046，med 差 0.021）。
                if "旧最优(纯tonemap)" in by_tag and "对照:lightmap走UV0" in by_tag:
                    a1, a0 = by_tag["旧最优(纯tonemap)"]["avg"], by_tag["对照:lightmap走UV0"]["avg"]
                    worst = max(keys, key=lambda k: abs(a1[k] - a0[k]))
                    say(abs(a1[worst] - a0[worst]) > 0.01,
                        "C4 lightmap 通道敏感性：UV1 vs UV0 的分布差 %.4f（在 %s 上；须 >0.01）"
                        % (abs(a1[worst] - a0[worst]), worst))
                if "对照:全关" in by_tag:
                    m0 = by_tag["对照:全关"]["avg"]["mean"]
                    say(m0 < 0.02, "C5 全关闭环底噪：灯=0 且无 lightmap 且无环境光时 mean=%.4f（须 <0.02）" % m0)
                # C6：泛光只许"把亮处铺开"，不许没反应。与同参数的无泛光档逐量比。
                if "包内环境光(线性入)" in by_tag and "环境光+泛光0.6" in by_tag:
                    b0 = by_tag["包内环境光(线性入)"]["avg"]
                    b1 = by_tag["环境光+泛光0.6"]["avg"]
                    say(b1["hi"] > b0["hi"] + 0.005 and b1["mean"] >= b0["mean"] - 0.005,
                        "C6 泛光敏感性：高光占比 %.1f%% → %.1f%%（必须升），mean %.3f → %.3f（不许降）"
                        % (100 * b0["hi"], 100 * b1["hi"], b0["mean"], b1["mean"]))
                # C7：过曝闸。分位数距离仍可能被"整幅一起提亮"讨好一部分，
                # 亮部面积超过参照 1.6 倍就直接判红——那是糊白，不是还原。
                if rows:
                    best = min(rows, key=lambda x: x["dist"])
                    over = best["avg"]["hi6"] / max(1e-6, target["hi6"])
                    say(over <= 1.6,
                        "C7 过曝闸：最近档亮部(>0.6)占比 %.1f%% vs 参照 %.1f%% = %.2f 倍（须 ≤1.6）"
                        % (100 * best["avg"]["hi6"], 100 * target["hi6"], over))
                    print("  最近档位: %s（分位+饱和距离 %.3f）参数 %s —— 出图 shot_best_*.png"
                          % (best["tag"], best["dist"], json.dumps(best["preset"], ensure_ascii=False)))
                    run_case(browser, base, rel_glb, rel_truth, "best",
                             {"names": [v["name"] for v in zone_v]},
                             extra=preset_query(best["preset"], base, rel_side, rel_render,
                                                urllib.parse.quote(json.dumps(zone_v, ensure_ascii=False))))
                    with open(os.path.join(WORK, "grade_sweep.json"), "w", encoding="utf-8") as f:
                        json.dump({"target": target, "rows": rows}, f, ensure_ascii=False, indent=1)

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
