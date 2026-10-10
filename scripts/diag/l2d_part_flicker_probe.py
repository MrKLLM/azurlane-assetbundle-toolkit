# -*- coding: utf-8 -*-
"""l2d_part_flicker_probe.py — 抓「部件闪一下」：把台阶定位到**具体哪一个参数**，并回答"谁写的"。

各臂（同一次运行按传入的开关依次出）：
  ① part / drawable 逐帧不透明度台阶（hard：`<0.05` 且前帧 `>0.5`；soft：单步降 ≥0.4 且 4 帧内回升 80%）。
  ② **全部参数逐帧**：从 wasm 实时缓冲 `parameters.values` 取全部参数，点名「与 ① 的台阶落在同一次
     update 里变化」的参数。cubism4 包里没有 `setDrawableOpacity`，能写 `drawables.opacities` 的只有
     wasm core 的 `update()`，而它的输入只有「参数值 + part 透明度」⇒ part 恒定时台阶**必然**出自
     某个参数经 moc3 的 ArtMeshOpacity 绑定，② 不是碰运气而是唯一出口。
  ③ **写入者归因**：对 ② 点名的参数包 `setParameterValueByIndex`，记「帧序 / 传入值 / weight /
     存值前→后 / 调用来源栈帧」。weight<1 = 交叉淡化；weight=2 参(未给)或 1 时靠栈帧区分
     复位层 `restTick`、环境层 `afterMotionUpdate`、framework 动作求值、物理。
  ④ `--drivers <drawable名>` **运行时驱动扫描**：逐个参数按量程写 `--nsweep`+1 个点 → `core.update()` →
     读目标 drawable 透明度，能改变它的就是这个 ArtMesh 的绑定驱动者，并给出**值→透明度映射**（阈值在哪）。
     不解析 moc3 字节（仓库里没有绑定表解析代码），用因果扫描代替反查。
     ⚠️ 扫描点数必须 >2：ArtMeshOpacity 绑定可以是非单调的，只测 min/中/max 会漏掉"只在量程中段显形"的驱动者。
  ⑤ `--mapall` **全量绑定表**：一次跑完「哪个参数在量程内哪些点上，会让哪几个 mesh 的透明度离开基准」，
     落 `.diag/l2d_opacity_map_<model>.json`（每条都带 11 点曲线，可离线复算）。回答"这批 mesh 的开关都有谁"
     "某些参数到底关不关可视性"——与逐个 `--drivers` 同样的 update 次数，但读的是全部 drawable，一次顶 N 次。
  ⑥ `--shot` 单参数 A/B 截图（只回答"这个参数管的是画面上哪一块"，不当验收判据）。
  ⑦ `--dumpgeo` 全部 mesh 的屏幕包围盒/面积/透明度（认"这个像素是哪几片"）。
     ⚠️ **不透明度为 0 的 ArtMesh 顶点会塌到原点**（实测灭着的片在两个姿态下都是 `[0,0,0,0]`）
     ⇒ 从任何单一姿态导出都拿不到"灭着那组"的尺寸，**不能用它算面积覆盖**。
  ⑧ `--hide/--hideclip/--hidewait` 藏掉指定 mesh 再截图（认画面身份）。
     ⚠️ base/hide 是两次独立播放 ⇒ 像素差主要来自相位与物理漂移，只可肉眼看同帧两图，不可当数值判据。
  ⑨ `--deform <名|@文件>` **变形者闸**：这个参数在自己量程内挪不挪几何？别的参数全钉在 setup 基准，
     只把它在第 q-1→q 点之间移动，比较**两点都亮着**的 mesh 的屏幕框 Σ(宽+高) —— 纯显隐开关应当一像素不动。
     落 `.diag/l2d_deform_<model>.json`。用途：把"既绑显隐又形变"的姿态参数（`ParamForearmLAngle`）
     从 snap 名单里挡出去（snap 它 = 手臂瞬移）。判据与下游见 `scripts/diag/l2d_snap_criterion_scan.py`。
  ⑩ `--snapab idle->home` **snap 修法的 A/B 时间轴**：同一趟跑 `window.__snapOff` 关/开两个模式，
     每次模型 update 记一行 [相对秒, currentGroup, 全模型亮着数, A 组峰值, B 组峰值, 台账集亮着数/峰值, 参数值…]。
     验收看的是**"该参数能影响的全部 mesh 里有几盏亮"**随帧的曲线（修法开时不得出现 0），不是截图。
     ⚠️ A/B 两组名要自己给对：在实态里从不亮的一组会让"A∧B 同时灭"变成常真、失去区分度。

⚠️ URL 必须带 cache-buster（`?v=<epoch>`）：headless 用固定 `--user-data-dir`，改过前端之后 Chrome 会端出
   磁盘缓存里的旧 `index.html` —— 症状是"补丁明明落盘了、跑出来的行为与改动前逐帧相同"。

⚠️ 采样基准是**每一次模型 update**（包 `CubismCoreModel.prototype.update`），不是墙钟 setTimeout：
   无头里动作时间推进极不均匀（`Ticker` 对 `dt` 有上限），按墙钟数台阶次数同一条 clip 会跑出 10 与 20
   两种结果（§123 追加-II 记过）。按帧对齐后绝对次数才第一次可比。
⚠️ 每条臂都自带「真的采到了」的自证（`arm` 字段）：行数 / 至少变过一次的参数个数 / 名字解析失败数，
   外加一条结构性矛盾 —— **有 drawable 在变而 0 个参数在变 = 不可能，判仪器坏了**。
   「0」只有在自证通过时才能读成「参数层没问题」。

用法: py -3 scripts/diag/l2d_part_flicker_probe.py gezi_2 --clips home --step 60 --hold 6
      NOREST=1 py -3 scripts/diag/l2d_part_flicker_probe.py gezi_2 --clips home     # A/B 关渐变复位
      py -3 scripts/diag/l2d_part_flicker_probe.py gezi_2 --clips __none__          # 阴性对照：不切动作
      py -3 scripts/diag/l2d_part_flicker_probe.py gezi_2 --clips home --nowriters --drivers ArtMesh42,case15
      py -3 scripts/diag/l2d_part_flicker_probe.py gezi_2 --clips home --trace ArtMesh42 \
              --wparams Param25,l2d_hx                                              # ③ 定向归因到指定参数
      py -3 scripts/diag/l2d_part_flicker_probe.py gezi_2 --clips __none__ --nowriters \
              --deform "@Output/Live2D/gezi_2/gezi_2.snapswitch.json"                # ⑨ 变形者闸
      py -3 scripts/diag/l2d_part_flicker_probe.py gezi_2 --clips __none__ --nowriters \
              --snapab "idle->home" --hold 6 --step 60                               # ⑩ snap A/B 时间轴
输出: 终端报告 + .diag/l2d_flicker_<model>_{rest,norest}.json
"""
import argparse
import base64
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


# ---------------------------------------------------------------- 运行时钩子（只装一次）
# 两个钩子都必须用 `this._model` 取缓冲，不许闭包捕获某个实例 —— 标志表/缓冲是逐模型的。
JS_INSTALL = r"""(() => {
  const core = window.__m.internalModel.coreModel;
  const CP = Object.getPrototypeOf(core);
  const stackTag = () => {
    try {
      const L = String(new Error().stack || '').split('\n'), out = [];
      for (let s of L) { s = s.trim();
        if (!s || s.indexOf('Error') === 0) continue;
        const m = /^at (?:async )?(.*?) ?\(([^)]*)\)$/.exec(s) || /^at (.*?)$/.exec(s);
        if (!m) continue;
        let f = m[2] || '', pos = '';
        const hp = /^(.*?):(\d+):\d+$/.exec(f); if (hp) { f = hp[1]; pos = ':' + hp[2]; }
        const seg = f.split('/'); f = seg[seg.length - 1];
        out.push((m[1] || '?') + '@' + f + pos);
        if (out.length >= 4) break;
      }
      return out.join(' <- ');
    } catch (e) { return 'n/a'; }
  };
  window.__stackTag = stackTag;
  if (!CP.__flickUpdate) {                              // 第二次运行必须复用原始实现，否则自递归
    const base = CP.update;
    CP.__baseUpdate = base;
    CP.update = function () {
      const r = base.apply(this, arguments);
      const M = this._model;
      // 藏 mesh 必须打在 core.update() **之后**：渲染读的就是这份缓冲，
      // 若在 update 之前写，会被按参数重算覆盖掉（实测写 0 读回还是 1，两张图逐像素相同）。
      if(window.__hideSet){ const O=M.drawables.opacities; window.__hideSet.forEach(j=>{ O[j]=0; }); }
      const c = window.__cap;
      if (c && c.rows.length < c.max) {
        c.rows.push(M.parameters.values.slice());
        c.partrows.push(M.parts.opacities.slice());
        c.drows.push(M.drawables.opacities.slice());
        c.ts.push(+((performance.now() - c.t0) / 1000).toFixed(3));
        let g = null; try { g = window.__m.internalModel.motionManager.state.currentGroup; } catch (e) {}
        c.groups.push(g || null);
      }
      return r;
    };
    CP.__flickUpdate = 1;
  }
  if (!CP.__flickSet) {
    const base = CP.setParameterValueByIndex;           // 这里拿到的已经是页面补丁 ⑤ 那一层
    CP.__baseSetBelow = base;
    CP.__baseSetSrc = String(base).slice(0, 200);
    CP.setParameterValueByIndex = function (i, v, w) {
      const W = window.__wset;
      if (!W || !W.has(i)) return base.apply(this, arguments);
      const PR = this._model.parameters, before = PR.values[i];
      const r = base.apply(this, arguments), after = PR.values[i];
      const last = window.__wlast[i];
      const moved = (last === undefined) || Math.abs(after - last) > 1e-4 || Math.abs(after - before) > 1e-4;
      if (moved && window.__wlog.length < window.__wcap) {
        window.__wlast[i] = after;
        const c = window.__cap;
        window.__wlog.push([(c ? c.rows.length : -1), i, +v.toFixed(4),
                            (w === undefined ? '无' : +w.toFixed(3)), +before.toFixed(4), +after.toFixed(4),
                            window.__stackTag()]);
      }
      return r;
    };
    CP.__flickSet = 1;
  }
  const M = core._model;
  return JSON.stringify({updateHook: !!CP.__flickUpdate, setHook: !!CP.__flickSet,
                         paramCount: M.parameters.count, partCount: M.parts.count,
                         drawableCount: M.drawables.count, baseSetSrc: CP.__baseSetSrc});
})()"""

JS_BOOT = r"""(async (key) => {
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
  window.__noRest=NOREST;                       // A/B 开关：true = 关掉「渐变回默认」那层
  window.__traceNames=TRACES; window.__traceGroups=[];
  window.__ofmReport='无';
  if(OFM && window.PIXI && PIXI.live2d && PIXI.live2d.CubismConfig){
    PIXI.live2d.CubismConfig.setOpacityFromMotion=true;
    window.__ofmReport=String(PIXI.live2d.CubismConfig.setOpacityFromMotion); }
  const core=m0.internalModel.coreModel;
  const M=core._model;
  const ids=[]; for(let i=0;i<core.getPartCount();i++){
    const raw=core._partIds; const x=Array.isArray(raw)?raw[i]:null;
    ids.push((typeof x==='string')?x:((x&&x.string)||('Part#'+i))); }
  window.__partIds=ids;
  const darr=[]; const draw=M.drawables; const rawIds=(draw&&draw.ids)||core._drawableIds||[];
  for(let i=0;i<core.getDrawableCount();i++){ const x=Array.isArray(rawIds)?rawIds[i]:null;
    darr.push((typeof x==='string')?x:((x&&x.string)||('Drawable#'+i))); }
  window.__drawableIds=darr;
  const pids=[]; const rawP=M.parameters.ids||[];
  let pnameFail=0;
  for(let i=0;i<M.parameters.count;i++){ const x=Array.isArray(rawP)?rawP[i]:null;
    const s=(typeof x==='string')?x:((x&&x.string)||null);
    if(!s){ pnameFail++; } pids.push(s||('Param#'+i)); }
  window.__pid=pids; window.__pnameFail=pnameFail;
  window.__wset=null; window.__wlog=[]; window.__wlast={}; window.__wcap=2500; window.__cap=null;
  const info=INSTALL;
  const js=JSON.parse(info);
  return JSON.stringify({ok:true, parts:core.getPartCount(), noRest:window.__noRest,
                         ofm:window.__ofmReport,
                         cubismConfigReachable: !!(window.PIXI&&PIXI.live2d&&PIXI.live2d.CubismConfig),
                         groups:Object.keys(m0.internalModel.motionManager.definitions||{}).length,
                         pnameFail:pnameFail, arm:js});
})(MODEL)
""".replace("NOREST", "%NOREST%").replace("TRACES", "%TRACES%") \
   .replace("OFM", "%OFM%").replace("MODEL", "%MODEL%").replace("INSTALL", "%INSTALL%")

# ---------------------------------------------------------------- ①+②：一个 clip 窗口
JS_PLAY = r"""(async (clip, holdSec, stepMs, maxRows) => {
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  const m=window.__m, core=m.internalModel.coreModel, mm=m.internalModel.motionManager;
  const M=core._model, P=M.parameters;
  const idle=(['idle','main','home'].find(g=>(mm.definitions||{})[g]))||'idle';
  window.__cap={t0:performance.now(), rows:[], partrows:[], drows:[], ts:[], groups:[], max:maxRows};
  if(clip!=='__none__'){ try{ mm.startMotion(clip,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){} }
  const half=Math.max(1, Math.round(holdSec*1000/stepMs/2));
  for(let k=0;k<half;k++){ try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
                           window.__app.render(); await t(stepMs); }
  const switchFrame=window.__cap.rows.length;
  try{ mm.startMotion(idle,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){}   // 逼出回落
  for(let k=0;k<half;k++){ try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
                           window.__app.render(); await t(stepMs); }
  const cap=window.__cap; window.__cap=null; window.__traceGroups=cap.groups;
  const n=M.parts.count, nd=M.drawables.count, np=P.count;
  const geo=[]; { const DP=M.drawables;
    for(let i=0;i<nd;i++){ const p=DP.vertexPositions[i]; let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
      for(let k=0;k+1<p.length;k+=2){ if(p[k]<x0)x0=p[k]; if(p[k]>x1)x1=p[k]; if(p[k+1]<y0)y0=p[k+1]; if(p[k+1]>y1)y1=p[k+1]; }
      geo.push([+x0.toFixed(2),+y0.toFixed(2),+x1.toFixed(2),+y1.toFixed(2),+((x1-x0)*(y1-y0)).toFixed(4)]); } }
  const scan=(mat, ids, kind, g)=>{
    const out=[]; let varying=0;
    if(!mat.length) return {dips:out, varying:0};
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
          const back=col.slice(k, Math.min(col.length, k+5)).reduce((a,x)=>Math.max(a,x), 0);
          if(back >= col[k-1]*0.8) soft={k, v:col[k], before:col[k-1]};
        }
      }
      const hit=hard||soft;
      if(hit) out.push([kind, (ids&&ids[i]!==undefined)?ids[i]:('#'+i),
                        hard?'hard':'soft', hit.v, hit.before, cap.ts[hit.k], +(hi-lo).toFixed(3), hit.k,
                        g?g[i]:null]);
    }
    return {dips:out, varying};
  };
  const A=scan(cap.partrows, window.__partIds, 'part', null),
        B=scan(cap.drows, window.__drawableIds, 'drawable', geo);
  const dips=A.dips.concat(B.dips).sort((x,y)=>x[5]-y[5]);
  const DF=new Set(); dips.forEach(d=>{ DF.add(d[7]); DF.add(d[7]-1); });
  // —— ② 全部参数逐帧：谁在台阶那些帧上变了
  const cand=[]; let nAny=0;
  if(cap.rows.length){
    // 「同帧变化」这个宽判据会命中 246 个一直在动的参数（物理/呼吸/环境层），必须收紧成**台阶形状**：
    //   该帧的 |Δ| ≥ 本参数窗口内 |Δ| 中位数的 4 倍，且前后一帧基本静止（≤0.35 倍）⇒ 是一次孤立跳变。
    // 只有孤立跳变才可能是 drawable 那个 1→0.52→0 台阶的因；连续缓慢推进的不可能一步跳一半。
    const Q=new Float32Array(cap.rows.length);
    for(let i=0;i<np;i++){
      const mn=P.minimumValues[i], mx=P.maximumValues[i];
      const eps=Math.max(1e-3, 0.002*(mx-mn));
      const R=cap.rows, nr=R.length;
      for(let k=1;k<nr;k++) Q[k]=Math.abs(R[k][i]-R[k-1][i]);
      let any=0; for(let k=1;k<nr;k++) if(Q[k]>eps) any++;
      if(any) nAny++;
      if(nr<5 || any===0) continue;
      const srt=Array.from(Q.slice(1)).sort((a,b)=>a-b);
      const med=srt[Math.floor(srt.length/2)]||0;
      const thr=Math.max(eps, med*4);
      const steps=[];
      for(let k=1;k<nr-1;k++){
        const q=Q[k]; if(q<thr) continue;
        if(Q[k+1] > q*0.35) continue;                     // 下一帧还在动 ⇒ 是斜坡不是台阶
        if(k>1 && Q[k-1] > q*0.35) continue;              // 上一帧就在动 ⇒ 同上
        steps.push([k, +R[k-1][i].toFixed(3), +R[k][i].toFixed(3)]);
      }
      const at=steps.filter(s=>DF.has(s[0]));
      if(steps.length) cand.push({i, nm:window.__pid[i], mn, mx, rep:P.repeats[i], any, med,
                                  steps, at});
    }
    cand.sort((a,b)=> (b.at.length-a.at.length) || (b.steps.length-a.steps.length) || (a.any-b.any));
    cand.slice(0,10).forEach(c=>{ c.col=cap.rows.slice(0,400).map(r=>+r[c.i].toFixed(3)); });
  }
  const tr=(window.__traceNames||[]).map(nm=>{
    let j=window.__drawableIds.indexOf(nm);
    if(j<0){ j=window.__partIds.indexOf(nm);
      return {name:nm, kind:'part', col:cap.partrows.map(r=>r[j]), groups:cap.groups}; }
    return {name:nm, kind:'drawable', col:cap.drows.map(r=>r[j]), groups:cap.groups}; });
  // —— 自证：这条臂到底采到了没有。有 drawable 在变而 0 个参数在变 = 结构性矛盾 = 仪器坏
  const alive=cap.rows.length>2;
  const contradicted=alive && (A.varying+B.varying)>0 && nAny===0;
  return JSON.stringify({frames:cap.rows.length, ts:[cap.ts[0], cap.ts[cap.ts.length-1]],
    switchFrame, partCount:n, drawableCount:nd, paramCount:np,
    partsVaried:A.varying, drawablesVaried:B.varying,
    arm:{alive, rows:cap.rows.length, nameFail:window.__pnameFail, nAnyChange:nAny, contradicted},
    dips, dipFrames:[...DF].sort((a,b)=>a-b),
    cand:cand.slice(0,10), candTotal:cand.length, trace:tr});
})"""

# ---------------------------------------------------------------- ③：写入者归因（重放同一切换序列）
JS_WRITERS = r"""(async (clip, holdSec, stepMs, nameList) => {
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  const m=window.__m, mm=m.internalModel.motionManager;
  const idle=(['idle','main','home'].find(g=>(mm.definitions||{})[g]))||'idle';
  const idxList=nameList.map(n=>window.__pid.indexOf(n)).filter(i=>i>=0);
  const unres=nameList.filter(n=>window.__pid.indexOf(n)<0);
  window.__wlog=[]; window.__wlast={}; window.__wset=new Set(idxList);
  window.__cap={t0:performance.now(), rows:[], partrows:[], drows:[], ts:[], groups:[], max:4000};
  if(clip!=='__none__'){ try{ mm.startMotion(clip,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){} }
  const half=Math.max(1, Math.round(holdSec*1000/stepMs/2));
  for(let k=0;k<half;k++){ try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
                           window.__app.render(); await t(stepMs); }
  const switchFrame=window.__cap.rows.length;
  try{ mm.startMotion(idle,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){}
  for(let k=0;k<half;k++){ try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
                           window.__app.render(); await t(stepMs); }
  const cap=window.__cap; window.__cap=null;
  const log=window.__wlog; window.__wset=null;
  return JSON.stringify({frames:cap.rows.length, ts:cap.ts.slice(-1)[0]||0, switchFrame,
                         unres, idx:idxList, names:idxList.map(i=>window.__pid[i]), log});
})"""

# ---------------------------------------------------------------- ④：运行时驱动扫描（代替 moc3 反查）
JS_DRIVERS = r"""(async (names, nstep, clip, waitMs, pin) => {
  const core=window.__m.internalModel.coreModel, mm=window.__m.internalModel.motionManager;
  const M=core._model, P=M.parameters, D=M.drawables;
  const di=names.map(n=>window.__drawableIds.indexOf(n));
  const miss=names.filter((n,j)=>di[j]<0);
  const ok=di.map((v,j)=>[names[j], v]).filter(x=>x[1]>=0);
  if(!ok.length) return JSON.stringify({fail:'目标 drawable 都不在模型里', miss});
  window.__cap=null; window.__wset=null;
  const ambWas=window.__ambOff; window.__ambOff=true;
  let grp=null;
  if(clip){                                  // 第二基准：先播这条 clip，跑到角色在画面内再定格
    try{ mm.startMotion(clip,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){}
    try{ window.__m.autoUpdate=true; window.__app.ticker.start(); }catch(e){}
    await new Promise(r=>setTimeout(r,waitMs));
    try{ mm.stopAllMotions(); }catch(e){}
    window.__m.autoUpdate=false; try{ window.__app.ticker.stop(); }catch(e){}
    try{ grp=(mm.state||{}).currentGroup; }catch(e){}
  } else { try{ mm.stopAllMotions(); }catch(e){} }
  const base=[]; for(let i=0;i<P.count;i++) base.push(P.values[i]);
  const read=()=>ok.map(x=>+D.opacities[x[1]].toFixed(3));
  // 可选：定格后把某几个参数钉成指定值再扫。查「第二道门」必须先把第一道门打开，
  // 否则在乘性门下任何单参数扫描都看不见效果（本轮 ArtMesh325 就是这么一直漏掉的）。
  if(pin&&pin.length){ for(const pv of pin){ const k=P.ids.indexOf(pv[0]);
    if(k>=0){ base[k]=pv[1]; P.values[k]=pv[1]; } } }
  core.update(); const ref=read();
  const pinEcho=(pin||[]).map(pv=>{ const k=P.ids.indexOf(pv[0]);
    return [pv[0], k, k>=0? +P.values[k].toFixed(3): null, k>=0? +P.minimumValues[k].toFixed(3): null,
            k>=0? +P.maximumValues[k].toFixed(3): null]; });
  const drv=[]; let updates=0;
  // ⚠️ 扫描点数必须 >2：moc3 的 ArtMeshOpacity 绑定**可以是非单调的**（花瓣那种只在量程中段显形，
  //   或 [0,a] 内从 1 掉到 0 之后恒 0）。只测 min/中/max 三点会把"只有中段才改变目标"的驱动者整个漏掉
  //   —— 本项目实测漏掉了 case13..18 的真正驱动者，只留下 l2d_hx 一个假完整答案。
  for(let i=0;i<P.count;i++){
    const mn=P.minimumValues[i], mx=P.maximumValues[i];
    const got=[]; let changed=false;
    for(let q=0;q<=nstep;q++){
      const v=mn+(mx-mn)*q/nstep;
      P.values[i]=v; core.update(); updates++;
      const r=read(); got.push([+v.toFixed(3), r]);
      if(r.some((x,j)=>Math.abs(x-ref[j])>1e-3)) changed=true;
    }
    P.values[i]=base[i];
    if(changed) drv.push([window.__pid[i], +mn.toFixed(3), +mx.toFixed(3), +P.defaultValues[i].toFixed(3),
                          P.repeats[i], got]);
  }
  // ⚠️ 探测一在**乘性多门**下会漏：目标被两道门同时关着时，单独动任何一个参数都抬不起来。
  //    探测二反过来问"谁在挡路"：其余参数全部保持此刻的实际值，只把第 i 个改回 moc3 默认值；
  //    目标因此亮起(>0.05) ⇒ 就是"i 在当前这个值"把它关着。这才找得到第二道门。
  const blockers=[];
  for(let i=0;i<P.count;i++){
    const dv=P.defaultValues[i];
    if(Math.abs(dv-base[i])<1e-6) continue;              // 默认值==当前值 ⇒ 不可能是挡路者
    P.values[i]=dv; core.update(); updates++;
    const r=read(); P.values[i]=base[i];
    if(r.some(x=>x>0.05)) blockers.push([window.__pid[i], +base[i].toFixed(3), +dv.toFixed(3), r]);
  }
  for(let i=0;i<P.count;i++) P.values[i]=base[i];
  core.update();
  // 恒等自检：扫完回到基线输入重读一次，必须与最初基线逐位相同。
  // 不等 ⇒ 系统里还有"只由历史写入、不随输入重算"的第二套状态（Live2D 里就是 part 透明度），
  // 这时**任何**基于该基线的结论都不作数（实测本项目就撞上过一次：ref 读两组全灭、扫描中同值却点亮）。
  const ref2=read(); let drift=0;
  for(let j=0;j<ref.length;j++) if(Math.abs(ref[j]-ref2[j])>1e-3) drift++;
  window.__ambOff=ambWas;
  return JSON.stringify({targets:ok.map(x=>x[0]), ref, ref2, drift, miss, pinEcho,
                         params:P.count, nstep, updates,
                         baseline:clip?('定格自 clip '+clip):'setup 默认姿态', group:grp,
                         drivers:drv, blockers});
})"""


# ---------------------------------------------------------------- ⑤ 全量「参数 → 哪个 mesh 显隐」绑定表
JS_MAPALL = r"""(async (nstep) => {
  const core=window.__m.internalModel.coreModel, mm=window.__m.internalModel.motionManager;
  const M=core._model, P=M.parameters, D=M.drawables;
  window.__cap=null; window.__wset=null;
  const ambWas=window.__ambOff; window.__ambOff=true;
  try{ mm.stopAllMotions(); }catch(e){}
  const nd=D.count, np=P.count;
  // 基准必须是**确定性姿态**：全部参数写 moc3 默认值后再采 ref。用"当前姿态"当基准会造出假阳性 ——
  // 实测 ArtMesh312 在当前基准里是关着的 0，结果 253 个参数各被扫出"11 个点全是 1.00"，
  // 看着像 253 条绑定，其实只是"动一下就开"，不是该参数决定的。
  try{ window.__app.ticker.stop(); }catch(e){}
  for(let i=0;i<np;i++) P.values[i]=P.defaultValues[i];
  core.update();
  const base=[]; for(let i=0;i<np;i++) base.push(P.values[i]);
  const ref=new Float32Array(nd);
  ref.set(D.opacities);
  const out=[]; let updates=0, pairs=0, flat=0;
  const touched=new Uint8Array(nd);
  for(let i=0;i<np;i++){
    const mn=P.minimumValues[i], mx=P.maximumValues[i], map=new Map();
    for(let q=0;q<=nstep;q++){
      P.values[i]=mn+(mx-mn)*q/nstep; core.update(); updates++;
      const O=D.opacities;
      for(let d=0;d<nd;d++){ const x=O[d];
        if(Math.abs(x-ref[d])>1e-3){
          let e=map.get(d); if(!e){ e={pts:[], mn:x, mx:x}; map.set(d,e); }
          e.pts.push([q,+x.toFixed(3)]); if(x<e.mn)e.mn=x; if(x>e.mx)e.mx=x;
        } }
    }
    P.values[i]=base[i];
    if(!map.size) continue;
    const aff=[];
    map.forEach((e,d)=>{
      // 真绑定 = 11 点序列非常量：要么有点等于基准（没被记进 pts），要么记录值本身有高低。
      // 11 点全等于同一个非基准值 ⇒ 假阳性（基准里关着、一动就开），丢掉。
      if(!(e.pts.length<nstep+1 || (e.mx-e.mn)>1e-3)){ flat++; return; }
      aff.push([d,e.pts]); touched[d]=1;
    });
    if(!aff.length) continue;
    pairs+=aff.length;
    out.push([i, window.__pid[i], +mn.toFixed(3), +mx.toFixed(3), +P.defaultValues[i].toFixed(3),
              P.repeats[i], aff.length, aff]);
  }
  for(let i=0;i<np;i++) P.values[i]=base[i];
  core.update(); window.__ambOff=ambWas;
  try{ window.__app.ticker.start(); }catch(e){}
  const un=[]; for(let d=0;d<nd;d++) if(!touched[d]) un.push(d);
  return JSON.stringify({nstep, params:np, drawables:nd, updates,
    nParamsWithEffect:out.length, pairs, nFlatRejected:flat, nUntouched:un.length, untouched:un,
    ref:Array.from(ref, x=>+x.toFixed(3)), names:window.__drawableIds, map:out});
})"""


# ---------------------------------------------------------------- ⑪ 部件门：这条 clip 里"该亮不亮"的片，是被哪个部件关着的？
# 为什么要它：`PartOpacity` **不随参数重算**——只有动画里带部件曲线的 clip 才会写它。
# 实测 gezi_2：`idle` 有 150 条部件曲线、`home` **一条都没有** ⇒ 切进 home 后部件停在 idle 最后写的值上。
# 游戏侧靠 Unity 的 `m_WriteDefaultValues=True`（所有状态都开着）在切换时把"这条状态不动画的属性"刷回默认值，
# 我们没有这一步 ⇒ "台账说该亮、实态读 0"和恒等自检的"同输入不同输出"都是它。
# 怎么读：播着目标 clip（不停运动、不冻结，避开上一轮那条"定格基线不自洽"），逐部件读
# 默认值 / 当前值 / 是否等于默认，并把目标 mesh 所属部件单独列出来。
JS_PARTCHECK = r"""(async (cfg) => {
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  const im=window.__m.internalModel, core=im.coreModel, mm=im.motionManager;
  const M=core._model, D=M.drawables, PT=M.parts;
  const frameN=()=>{ try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
                     try{ window.__app.render(); }catch(e){} };
  try{ mm.stopAllMotions(); }catch(e){}
  if(cfg.clip){ try{ mm.startMotion(cfg.clip,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){} }
  const nfr=Math.max(1,Math.round(cfg.wait*1000/cfg.stepMs));
  for(let k=0;k<nfr;k++){ frameN(); await t(cfg.stepMs); }
  const grp=(()=>{ try{ return mm.state.currentGroup; }catch(e){ return null; } })();
  const hasDef=!!(PT.defaultValues&&PT.defaultValues.length===PT.count);
  const off=[], same=[];
  for(let i=0;i<PT.count;i++){
    const o=PT.opacities[i], dv=hasDef?PT.defaultValues[i]:1;
    if(Math.abs(o-dv)>1e-3){ off.push([PT.ids[i], +o.toFixed(3), +dv.toFixed(3),
                                       +(PT.blendTypes?PT.blendTypes[i]:0)]); }
  }
  const targets=cfg.meshes.map(n=>{ const i=D.ids.indexOf(n);
    if(i<0) return {mesh:n, err:'no-such-drawable'};
    const pi=D.partMatch?D.partMatch[i]:-1;
    return {mesh:n, op:+D.opacities[i].toFixed(3), part:(pi>=0&&PT.ids)?PT.ids[pi]:null,
            partOp:pi>=0?+PT.opacities[pi].toFixed(3):null,
            partDef:(pi>=0&&hasDef)?+PT.defaultValues[pi].toFixed(3):null,
            partBlend:pi>=0&&PT.blendTypes?PT.blendTypes[pi]:null}; });
  return JSON.stringify({clip:cfg.clip, playing:grp, frames:nfr, partCount:PT.count,
    hasDefaults:hasDef, nonDefault:off.length, nonDefaultList:off.slice(0,60), targets});
})"""


# ---------------------------------------------------------------- ⑫ 找"合取门"：实态下灭着的片，是哪几个参数一起关着的？
# 为什么需要：探测一（逐个参数扫量程）在**合取门**下必然空手而归——两道门同时关着时，
# 单独打开任何一道都抬不起来。上一轮 191 个"挡路者"还是假象（判据写成 `读数>0.05`，
# 被本来就亮着的对照目标满足了）。这里改成二分：把"实态 vs moc3 默认态"里取值不同的参数集合折半，
# 只把一半还原成默认值，看目标是否亮起 ⇒ 门在那一半里；对半继续，直到只剩最小集合。
# 每一拍都只调一次 core.update，且全程不停动作、不冻结基线（避开"定格基线不自洽"那条坑）。
JS_GATEFIND = r"""(async (cfg) => {
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  const im=window.__m.internalModel, core=im.coreModel, mm=im.motionManager;
  const M=core._model, P=M.parameters, D=M.drawables;
  const ti=cfg.meshes.map(n=>P&&D.ids.indexOf(n)).filter(i=>i>=0);
  // 两套 drawable 名字数组必须一致，否则本臂读的是别的片（臂 ⑤ 用 window.__drawableIds，本臂用 D.ids）
  const idxCheck=cfg.meshes.map(n=>[n, D.ids.indexOf(n),
      (window.__drawableIds||[]).indexOf(n), D.ids.length, (window.__drawableIds||[]).length,
      (window.__drawableIds||[]).every((x,j)=>x===(D.ids[j]||'')) ? 'same' : 'DIFFER']);
  if(!ti.length) return JSON.stringify({fail:'目标都不在模型里', meshes:cfg.meshes});
  const frameN=()=>{ try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
                     try{ window.__app.render(); }catch(e){} };
  window.__cap=null; window.__wset=null;
  const ambWas=window.__ambOff; window.__ambOff=true;
  // ⚠️ 不配 --gclip 时基线必须先写 moc3 默认值：无头里页面停在 idle 的哪一帧是随机的，
  //    "停在当前姿态直接扫"同一条命令会给出 273 与 0 两种答案（本轮真实踩过，别拿它下结论）。
  if(!cfg.clip){ for(let i=0;i<P.count;i++) P.values[i]=P.defaultValues[i]; core.update(); }
  //    ↑ 且必须和臂 ⑤ 一样把渲染循环停掉：留着 ticker 时同一姿态下读到的显隐会不一样（本轮实测）。
  let tkWas=true; try{ tkWas=window.__app.ticker.started!==false; window.__app.ticker.stop(); }catch(e){}
  try{ window.__m.autoUpdate=false; }catch(e){}
  try{ mm.stopAllMotions(); }catch(e){}
  if(cfg.clip){ try{ mm.startMotion(cfg.clip,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){}
    window.__m.autoUpdate=true; try{ window.__app.ticker.start(); }catch(e){}
    await new Promise(r=>setTimeout(r,cfg.waitMs));
    try{ mm.stopAllMotions(); }catch(e){}
    window.__m.autoUpdate=false; try{ window.__app.ticker.stop(); }catch(e){} }
  const live=[]; for(let i=0;i<P.count;i++) live.push(P.values[i]);
  for(const pv of (cfg.pin||[])){ const k=P.ids.indexOf(pv[0]); if(k>=0) live[k]=pv[1]; }
  const read=(vals)=>{ for(let i=0;i<P.count;i++) if(Math.abs(P.values[i]-vals[i])>1e-9) P.values[i]=vals[i];
                       core.update(); return ti.map(j=>+D.opacities[j].toFixed(3)); };
  const dflt=P.defaultValues;
  const diff=[]; for(let i=0;i<P.count;i++) if(Math.abs(live[i]-dflt[i])>1e-6) diff.push(i);
  // 两个端点：① 全默认（保留 pin）② 全实态（保留 pin）
  const defPinned=Array.from(dflt); for(const pv of (cfg.pin||[])){ const k=P.ids.indexOf(pv[0]); if(k>=0) defPinned[k]=live[k]; }
  const atDefault=read(defPinned), atLive=read(live);
  let cur=diff.slice(), found=[];
  let steps=0;
  while(cur.length && steps<400){
    steps++;
    const half=Math.ceil(cur.length/2), A=cur.slice(0,half), B=cur.slice(half);
    let next=null;
    if(cur.length===1){ const r=read((()=>{const v=defPinned.slice(); v[cur[0]]=live[cur[0]]; return v;})());
      if(r.some(x=>x>0.5)) found.push([window.__pid[cur[0]], +live[cur[0]].toFixed(3), +dflt[cur[0]].toFixed(3), r]);
      break; }
    // 还原 A（A 用默认、其余候选用实态）能亮 ⇒ 门在 A；否则若在 B 同理；都不行 ⇒ 合取，两边都要留
    const vA=defPinned.slice(); for(const i of cur) vA[i]=live[i]; for(const i of A) vA[i]=dflt[i];
    const vB=defPinned.slice(); for(const i of cur) vB[i]=live[i]; for(const i of B) vB[i]=dflt[i];
    const rA=read(vA), rB=read(vB);
    const okA=rA.some(x=>x>0.5), okB=rB.some(x=>x>0.5);
    if(okA && !okB){ cur=A; }
    else if(okB && !okA){ cur=B; }
    else if(okA && okB){ break; }        // 两半各自都能开门 ⇒ 冗余门，保留现状并记下来
    else { break; }                       // 合取：必须两半同时还原才行 ⇒ 停止二分，报告当前集合
  }
  const finalSet=cur.slice();
  const vAll=defPinned.slice(); for(const i of finalSet) vAll[i]=live[i];
  const rAll=read(vAll);
  for(let i=0;i<P.count;i++) P.values[i]=live[i];
  core.update(); window.__ambOff=ambWas;
  try{ window.__m.autoUpdate=true; }catch(e){}
  try{ if(tkWas) window.__app.ticker.start(); }catch(e){}
  return JSON.stringify({clip:cfg.clip, meshes:cfg.meshes, targets:ti, idxCheck,
    nDiff:diff.length, atDefault:atDefault, atLive:atLive,
    minSet:finalSet.map(i=>[window.__pid[i], +live[i].toFixed(3), +dflt[i].toFixed(3)]),
    minSetRead:rAll, steps});
})"""


# ---------------------------------------------------------------- ⑨ 变形者闸：这个参数除了显隐，还挪不挪几何？
# 为什么要它：判据 C2「边界恒定 + 跨过美术翻转点」会把 `ParamForearmLAngle`（左前臂角）也捞进来 ——
# 它确实绑定着某些 ArtMesh 的显隐，但它同时是**姿态形变**参数。snap 它 = 手臂角度硬跳，
# 正好把 §6.35 治好的"姿态硬跳"从一个局部参数上放回来。⇒ 只 snap「不形变」的选择器。
# 怎么测（不解析 moc3，用因果对照）：别的参数一律钉在 setup 基准，只把这一个从第 q-1 点移到第 q 点；
# 取**两点都亮着**的 mesh（显隐翻转的那批要剔掉，否则"灭掉的片从有框变塌框"会被当成形变），
# 比较它们屏幕框的 Σ(宽+高)。纯显隐开关 ⇒ 这批片一个像素都不该动；动了就是形变者。
JS_DEFORM = r"""(async (names, nstep) => {
  const core=window.__m.internalModel.coreModel, mm=window.__m.internalModel.motionManager;
  const M=core._model, P=M.parameters, D=M.drawables;
  window.__cap=null; window.__wset=null;
  const ambWas=window.__ambOff; window.__ambOff=true;
  try{ mm.stopAllMotions(); }catch(e){}
  try{ window.__app.ticker.stop(); }catch(e){}
  for(let i=0;i<P.count;i++) P.values[i]=P.defaultValues[i];
  core.update();
  const base=[]; for(let i=0;i<P.count;i++) base.push(P.values[i]);
  const nd=D.count;
  // 每个 drawable 的顶点缓冲是 Float32Array 视图，取两次要重算框 —— 只为「两点都亮」的那批算，够快
  const boxOf=(d)=>{ const p=D.vertexPositions[d]; let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
    for(let k=0;k+1<p.length;k+=2){ const x=p[k],y=p[k+1];
      if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y; }
    return (x1<x0||y1<y0)? 0 : (x1-x0)+(y1-y0); };
  const litOf=()=>{ const O=D.opacities, a=new Float32Array(nd), s=new Float32Array(nd);
    for(let d=0;d<nd;d++){ const on=O[d]>=0.5; a[d]=on?1:0; s[d]=on?boxOf(d):0; }
    return {a,s}; };
  const out=[]; let updates=0;
  for(const nm of names){
    const i=P.ids.indexOf(nm); if(i<0){ out.push({name:nm, err:'no-such-param'}); continue; }
    const mn=P.minimumValues[i], mx=P.maximumValues[i];
    const hist=[]; let prev=null;
    for(let q=0;q<=nstep;q++){
      for(let k=0;k<P.count;k++) P.values[k]=base[k];
      P.values[i]=mn+(mx-mn)*q/nstep; core.update(); updates++;
      const cur=litOf();
      if(prev){ let both=0, dsum=0;
        for(let d=0;d<nd;d++) if(prev.a[d]&&cur.a[d]){ both++; dsum+=Math.abs(cur.s[d]-prev.s[d]); }
        hist.push([q, both, +dsum.toFixed(4)]);
      }
      prev=cur;
    }
    for(let k=0;k<P.count;k++) P.values[k]=base[k];
    core.update();
    const mxShift=hist.reduce((m,x)=>Math.max(m,x[2]),0);
    out.push({name:nm, mn:+mn.toFixed(3), mx:+mx.toFixed(3), maxBBoxShift:mxShift, hist});
  }
  try{ window.__app.ticker.start(); }catch(e){}
  window.__ambOff=ambWas;
  return JSON.stringify({nstep, drawables:nd, updates, params:out});
})"""


# ---------------------------------------------------------------- ⑩ snap 的 A/B 时间轴（修法 (b) 的验收判据）
# 同一趟里跑两个模式：window.__snapOff=true（修法关）→ false（修法开），每次都
# 「播 A 条 clip 进稳态 → 切到 B 条 → 逐次模型 update 采样」。
# 报的每一行 = 一次 update：[相对秒, 当时的 currentGroup, 全模型亮着的 mesh 数, A 组最大不透明度, B 组最大不透明度, 各参数值…]
# 判据不是截图，是**时间**：切换后「A 组和 B 组同时 <0.05」的累计秒数（修法开时应为 0）。
JS_SNAPAB = r"""(async (cfg) => {
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  const m=window.__m, im=m.internalModel, core=im.coreModel, mm=im.motionManager;
  const M=core._model, P=M.parameters, D=M.drawables;
  const ia=cfg.setA.map(n=>D.ids.indexOf(n)).filter(i=>i>=0);
  const ib=cfg.setB.map(n=>D.ids.indexOf(n)).filter(i=>i>=0);
  const ip=cfg.pnames.map(n=>P.ids.indexOf(n));
  const i25=cfg.set25.map(n=>D.ids.indexOf(n)).filter(i=>i>=0);
  const frameN=()=>{ try{ PIXI.Ticker.shared.tick(performance.now()); }catch(e){}
                     try{ window.__app.render(); }catch(e){} };
  const run=async(off)=>{
    window.__snapOff=off;
    try{ mm.stopAllMotions(); }catch(e){}
    try{ mm.startMotion(cfg.from,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){}
    for(let k=0;k<cfg.frames;k++){ frameN(); await t(cfg.stepMs); }
    const cap={t0:performance.now(), rows:[], partrows:[], drows:[], ts:[], groups:[], max:cfg.frames*3};
    window.__cap=cap;
    try{ mm.startMotion(cfg.to,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){}
    for(let k=0;k<cfg.frames;k++){ frameN(); await t(cfg.stepMs); }
    window.__cap=null;
    const rows=[];
    for(let r=0;r<cap.rows.length;r++){
      const O=cap.drows[r]; if(!O) continue;
      let nLit=0; for(let i=0;i<O.length;i++) if(O[i]>=0.5) nLit++;
      const mx=(ix)=>ix.length? Math.max.apply(null,ix.map(i=>O[i])) : -1;
      const row=[+(cap.ts[r]).toFixed(3), cap.groups[r]||null, nLit,
                 +mx(ia).toFixed(3), +mx(ib).toFixed(3),
                 i25.reduce((a,i)=>a+(O[i]>=0.5?1:0),0), +mx(i25).toFixed(3)];
      for(let j=0;j<ip.length;j++) row.push(ip[j]<0? null: +cap.rows[r][ip[j]].toFixed(3));
      rows.push(row);
    }
    return {off, rows};
  };
  const a=await run(true), b=await run(false);
  let dbg=null,dbgErr=null;
  try{ dbg = (typeof window.__snapDbg==='function')? window.__snapDbg() : 'NO-SUCH-FN(前端 snap 块没跑)'; }
  catch(e){ dbgErr=String(e&&e.message||e); }
  window.__snapOff=false;
  return JSON.stringify({cfg, snapDbg:dbg, snapDbgErr:dbgErr,
    marker:{snap:typeof window.__snapDbg, l2hit:typeof window.__L2_HIT,
            snapOff:typeof window.__snapOff, srcHash:(document.documentElement.innerHTML||'').length},
    off:a, on:b});
})"""


# ---------------------------------------------------------------- ⑥ 单参数 A/B 截图（只为"这块参数管的是画面上什么"）
JS_SHOT = r"""(async (name, v) => {
  const core=window.__m.internalModel.coreModel, mm=window.__m.internalModel.motionManager;
  const M=core._model, P=M.parameters;
  window.__cap=null; window.__wset=null; window.__ambOff=true;
  try{ mm.stopAllMotions(); }catch(e){}
  // 必须冻住 ticker：两张截图之间若继续跑物理/头发，姿态会漂几像素，
  // 差图就会全身轮廓亮 —— 那是漂移，不是显隐变化（本轮真实踩过）。
  try{ window.__app.ticker.stop(); }catch(e){}
  const i=P.ids.indexOf(name);
  if(i<0) return JSON.stringify({fail:'参数不在 moc3 里', name});
  if(window.__shotBase===undefined){ window.__shotBase=[]; for(let k=0;k<P.count;k++) window.__shotBase.push(P.values[k]); }
  for(let k=0;k<P.count;k++) P.values[k]=window.__shotBase[k];   // 每拍一张都从同一基准出发
  P.values[i]=v; core.update(); window.__app.render();
  return JSON.stringify({ok:true, name, v, idx:i, range:[P.minimumValues[i], P.maximumValues[i]],
                         tickerStopped:window.__app.ticker.started===false||true});
})"""


# ---------------------------------------------------------------- ⑦ 几何导出：把 ArtMesh 编号对应回画面位置
# 换算必须复用产品那套（gallery_src/index.html 的 P2V：Vx=Px-cux/2, Vy=cuy/2-Py），
# 不要在探针里另立一套坐标映射 —— 历史上"点胸口触发头部"就是两套空间混用造成的。
JS_GEO = r"""(async (dummy) => {
  const m=window.__m, im=m.internalModel, core=im.coreModel, M=core._model;
  const ppu=im.pixelsPerUnit||1, cux=im.width/ppu, cuy=im.height/ppu;
  const cv=document.querySelector('canvas'); const r=cv.getBoundingClientRect();
  const P=M.parameters, D=M.drawables;
  window.__cap=null; window.__wset=null;
  try{ im.motionManager.stopAllMotions(); }catch(e){}
  try{ window.__app.ticker.stop(); }catch(e){}          // 静止采样，别边采边动
  const grab=()=>{ const rows=[];
    for(let i=0;i<D.count;i++){ const p=D.vertexPositions[i];
      let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
      for(let k=0;k+1<p.length;k+=2){ if(p[k]<x0)x0=p[k]; if(p[k]>x1)x1=p[k]; if(p[k+1]<y0)y0=p[k+1]; if(p[k+1]>y1)y1=p[k+1]; }
      rows.push([window.__drawableIds[i], +x0.toFixed(4), +y0.toFixed(4), +x1.toFixed(4), +y1.toFixed(4),
                 +((x1-x0)*(y1-y0)).toFixed(6), +D.opacities[i].toFixed(3), D.renderOrders[i]]); }
    return rows; };
  const cur=grab();
  // setup 姿态：全部参数写 moc3 默认值。左右对称 ⇒ 成对的镜像框可以直接算出来（找"手"用）
  const base=[]; for(let i=0;i<P.count;i++) base.push(P.values[i]);
  for(let i=0;i<P.count;i++) P.values[i]=P.defaultValues[i];
  core.update(); const setup=grab();
  for(let i=0;i<P.count;i++) P.values[i]=base[i];
  core.update(); try{ window.__app.ticker.start(); }catch(e){}
  const mm=im.motionManager; const st={};
  try{ st.keys=Object.keys(mm.state||{});
    const it=(mm.state&&mm.state.items&&mm.state.items[0])||null;
    if(it){ st.itemKeys=Object.keys(it); const nums={};
      for(const k in it){ const v=it[k]; if(typeof v==='number'&&isFinite(v)) nums[k]=+v.toFixed(3); }
      st.itemNums=nums; }
    st.hasFadeTime=!!(mm.state&&mm.state.items&&mm.state.items[0]);
  }catch(e){ st.err=String(e); }
  return JSON.stringify({cux:+cux.toFixed(4), cuy:+cuy.toFixed(4),
                         rect:{left:r.left, top:r.top, w:r.width, h:r.height},
                         scale:+m.scale.x.toFixed(6), pos:[m.x,m.y],
                         rows:cur, setup, state:st});
})"""


# ---------------------------------------------------------------- ⑧ 藏起指定 mesh 后截图（用来确认"这几片是画面上的什么"）
JS_HIDE = r"""(async (names, clip, waitMs) => {
  const m=window.__m, im=m.internalModel, core=im.coreModel, M=core._model;
  const P=M.parameters, D=M.drawables;
  window.__cap=null; window.__ambOff=true;
  const live=!!clip;          // live=播着动作藏：setup 姿态下这些组多半被挡住/在画外，看不出身份
  if(!live){
    try{ im.motionManager.stopAllMotions(); }catch(e){}
    m.autoUpdate=false;                       // 页面自己的调度会把参数写回去
    try{ window.__app.ticker.stop(); }catch(e){}
    for(let i=0;i<P.count;i++) P.values[i]=P.defaultValues[i];   // setup 姿态，结果可复现
  } else {
    try{ im.motionManager.startMotion(clip,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){}
    await new Promise(r=>setTimeout(r,waitMs));              // 跑到"角色在画面内"的时刻再藏
    m.autoUpdate=false; try{ window.__app.ticker.stop(); }catch(e){}
  }
  const idx=[], miss=[];
  names.forEach(n=>{ const j=window.__drawableIds.indexOf(n); if(j<0) miss.push(n); else idx.push(j); });
  window.__hideSet = idx;                              // 由 update 钩子在 core.update() 之后落刀
  core.update();
  // WebGL 画布默认 preserveDrawingBuffer=false：不经过一次合成，Page.captureScreenshot
  // 截到的是上一帧 —— 实测这样截出来的两张图逐像素相同，会把"仪器坏"读成"这块参数没作用"。
  window.__app.render();
  await new Promise(r=>requestAnimationFrame(r));
  window.__app.render();
  await new Promise(r=>requestAnimationFrame(r));
  const after=idx.map(j=>+D.opacities[j].toFixed(2));
  // 自证：这一测到底播没播上那条 clip、被藏的片藏之前是不是亮着的。
  // 缺这两条就会把"clip 没播起来 ⇒ 那组本来就暗 ⇒ 藏了当然没变化"读成"这组不影响画面"。
  let grp=null, p25=null, openBefore=0, onScreen=0;
  try{ grp=im.motionManager.state.currentGroup; }catch(e){}
  try{ const i25=P.ids.indexOf('Param25'); if(i25>=0) p25=+P.values[i25].toFixed(3); }catch(e){}
  // 「藏了没变化」有两种成因：被藏的片全在画外/被遮挡（合法），或截图没反映改动（仪器坏）。
  // 不分这两条就会把前者误读成后者、或把后者误读成"这组不影响画面"。
  try{ const V=im.view||{}, hw=(V.Width||4)/2, hh=(V.Height||4)/2;
       onScreen=idx.filter(j=>{ const p=D.vertexPositions[j];
         let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
         for(let k=0;k+1<p.length;k+=2){ if(p[k]<x0)x0=p[k]; if(p[k]>x1)x1=p[k]; if(p[k+1]<y0)y0=p[k+1]; if(p[k+1]>y1)y1=p[k+1]; }
         return x1>-hw && x0<hw && y1>-hh && y0<hh; }).length; }catch(e){}
  try{ window.__hideSet=[]; core.update();
       openBefore=idx.filter(j=>D.opacities[j]>0.05).length; window.__hideSet=idx; core.update(); }catch(e){}
  return JSON.stringify({ok:true, live, clip:clip||null, group:grp, Param25:p25, openBefore, onScreen,
                         hidden:idx.length, miss, after,
                         stillZero:after.filter(x=>x===0).length});
})"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--clips", default="home,touch_head,mission_complete")
    ap.add_argument("--hold", type=float, default=4.0, help="每条窗口秒数（片段 + 回落各一段）")
    ap.add_argument("--step", type=int, default=120, help="墙钟推进间隔 ms（采样已改为按模型 update，此项只控窗口节奏）")
    ap.add_argument("--trace", default="", help="逗号分隔的 drawable/part 名，逐帧打印其透明度与当时的 currentGroup")
    ap.add_argument("--maxrows", type=int, default=1500, help="单次窗口最多记多少帧")
    ap.add_argument("--writers", type=int, default=10, help="③ 归因臂取 ② 的前 N 个候选参数，0 = 跳过")
    ap.add_argument("--wparams", default="", help="③ 改成按参数名归因（逗号分隔），用于扫中④的驱动者")
    ap.add_argument("--nowriters", action="store_true", help="跳过 ③")
    ap.add_argument("--drivers", default="", help="④ 驱动扫描的目标 drawable 名（逗号分隔），空 = 跳过")
    ap.add_argument("--nsweep", type=int, default=10, help="④/⑤ 每个参数在量程内扫多少个点（必须 >2，见头注释）")
    ap.add_argument("--drvclip", default="", help="④ 第二基准：先播这条 clip、等 --drvwait 秒定格后再扫（setup 基线下乘性门会漏）")
    ap.add_argument("--drvwait", type=float, default=10.0, help="④ 播 clip 后等几秒定格（要等到角色在画面内）")
    ap.add_argument("--gatefind", default="", help="⑫ 合取门二分：逗号分隔的 mesh 名（实态下灭着的那些）")
    ap.add_argument("--gclip", default="home", help="⑫ 定格自哪条 clip 的实态（空=用页面当前姿态）")
    ap.add_argument("--gwait", type=float, default=4.0, help="⑫ 播几秒后取实态")
    ap.add_argument("--gpin", default="", help="⑫ 两端都钉住的参数，形如 Param25:0.5（先打开第一道门）")
    ap.add_argument("--drvpin", default="", help="④ 定格后把参数钉成指定值再扫，形如 Param25:0.5（查第二道门时先打开第一道门）")
    ap.add_argument("--mapall", action="store_true", help="⑤ 全量「参数→哪些 mesh 显隐」绑定表（落 .diag/l2d_opacity_map_<model>.json）")
    ap.add_argument("--deform", default="", help="⑨ 变形者闸：逗号分隔参数名，或 @文件（每行一个/JSON 列表）。落 .diag/l2d_deform_<model>.json")
    ap.add_argument("--partcheck", default="", help="⑪ 部件门：逗号分隔的 mesh 名，读它们所属部件的默认值/当前值；配 --pcclip/--pcwait 决定播着哪条 clip 时读")
    ap.add_argument("--pcclip", default="home", help="⑪ 先看哪条 clip 的实态（默认 home）")
    ap.add_argument("--pcalso", default="idle", help="⑪ 对照组：再播这条 clip 读一遍（空=不读）")
    ap.add_argument("--pcwait", type=float, default=4.0, help="⑪ 播几秒后读（不停运动、不冻结）")
    ap.add_argument("--snapab", default="", help="⑩ snap A/B：形如 idle->home，同一趟跑 修法关/开 两个模式，逐次 update 记时间轴（验收判据用这个，不用截图）")
    ap.add_argument("--snapA", default="ArtMesh36,ArtMesh42,ArtMesh43,ArtMesh44,ArtMesh51",help="⑩ A 组 mesh 名（切换前应亮着的那组）")
    ap.add_argument("--snapB", default="ArtMesh325,ArtMesh326,ArtMesh327,ArtMesh328,ArtMesh329,ArtMesh330",help="⑩ B 组 mesh 名（切换后应亮着的那组）")
    ap.add_argument("--snapP", default="Param25,Param27", help="⑩ 时间轴里带上哪几个参数的值")
    ap.add_argument("--shot", default="", help="⑥ 单参数 A/B 截图，形如 Param25:0,0.5（只为认出画面上是哪一块）")
    ap.add_argument("--dumpgeo", action="store_true", help="⑦ 导出全部 mesh 的屏幕包围盒/面积/透明度，供离线反查「这个像素是哪几片」")
    ap.add_argument("--hide", default="", help="⑧ 逗号分隔的 drawable 名：setup 姿态下把这几片藏掉再截图（认画面身份用）")
    ap.add_argument("--hideclip", default="", help="⑧ 配 --hide：改成「播着这条 clip」时藏（setup 姿态下多半被挡住看不出）")
    ap.add_argument("--hidewait", type=float, default=3.0, help="⑧ 播 clip 后等几秒再藏（要等到角色在画面内的时刻，否则藏了必然零变化）")
    a = ap.parse_args()
    norest = os.environ.get("NOREST") == "1"
    tag = "norest" if norest else "rest"

    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(SRV_PORT),
                            "-b", "127.0.0.1", "-d", os.path.join(ROOT, "Output")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # 必须带 cache-buster：headless 用固定的 user-data-dir，改过 gallery 后 Chrome 会端出
    # 磁盘缓存里的旧 index.html —— 症状是"前端补丁明明改了、探针跑出来的行为和改动前一模一样"。
    url = "http://127.0.0.1:%d/gallery_v2/index.html?v=%d" % (SRV_PORT, int(time.time()))
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

    def loadjs(txt, raw=None):
        s = txt
        for k, v in (raw or {}).items():
            s = s.replace(k, v)
        return s

    cmd("Page.enable")
    boot_src = loadjs(JS_BOOT, {"%NOREST%": json.dumps(norest),
                                "%TRACES%": json.dumps([x for x in a.trace.split(",") if x]),
                                "%OFM%": json.dumps(os.environ.get("OFM") == "1"),
                                "%MODEL%": json.dumps(a.model),
                                "%INSTALL%": "window.__installHooks()"})
    # 先装钩子（独立求值，避免把整段 JS_INSTALL 塞进字符串字面量里转义）
    ev("window.__installHooks=function(){ return %s; }" % JS_INSTALL)
    raw = ev(boot_src)
    try:
        info = json.loads(raw) if isinstance(raw, str) and raw.strip().startswith("{") else (raw if isinstance(raw, dict) else {"fail": str(raw)[:400]})
    except Exception:
        info = {"fail": "boot 返回不是 JSON", "raw": str(raw)[:400]}
    if not info.get("ok"):
        print("[FAIL]", info)
        return 2
    arm = info.get("arm") or {}
    print("模型 %s：part %d / drawable %d / 参数 %d，%d 组动作，渐变复位=%s"
          % (a.model, arm.get("partCount", info["parts"]), arm.get("drawableCount", -1),
             arm.get("paramCount", -1), info["groups"], "关（NOREST=1）" if norest else "开（默认）"))
    print("钩子: update=%s set=%s 参数名解析失败=%d  CubismConfig可达=%s  setOpacityFromMotion=%s"
          % (arm.get("updateHook"), arm.get("setHook"), info.get("pnameFail", -1),
             info.get("cubismConfigReachable"), info.get("ofm")))
    if arm.get("baseSetSrc"):
        print("被包的 setter（补丁 ⑤ 是否在内）: %s" % arm["baseSetSrc"][:150])
    if not arm.get("updateHook") or not arm.get("setHook"):
        print("[FAIL] 钩子没装上，后面所有臂都不可信")
        return 2

    out = {"model": a.model, "norest": norest, "boot": info, "clips": {}}
    for clip in [c for c in a.clips.split(",") if c]:
        raw2 = ev(JS_PLAY + "(%s, %s, %s, %s)" % (json.dumps(clip), json.dumps(a.hold),
                                                  json.dumps(a.step), json.dumps(a.maxrows)))
        try:
            r = json.loads(raw2) if isinstance(raw2, str) and raw2.strip().startswith("{") else (raw2 if isinstance(raw2, dict) else {"dips": [], "err": str(raw2)[:400]})
        except Exception:
            r = {"dips": [], "err": str(raw2)[:300]}
        out["clips"][clip] = dict(r)
        if not isinstance(r, dict) or "dips" not in r:
            print("\n-- clip `%s`：探针返回不是 JSON → %s" % (clip, str(raw2)[:300]))
            continue
        ar = r.get("arm") or {}
        print("\n== clip `%s`：%.1fs 墙钟 / %d 次模型 update（切 idle 在第 %s 帧）"
              % (clip, r.get("ts", [0, 0])[1] or 0, r.get("frames", 0), r.get("switchFrame")))
        print("   自证: 行数 %s / 变过的参数 %s 个（共 %s）/ 参数名解析失败 %s / drawable 在变 %s、part 在变 %s ⇒ %s"
              % (ar.get("rows"), ar.get("nAnyChange"), r.get("paramCount"), ar.get("nameFail"),
                 r.get("drawablesVaried"), r.get("partsVaried"),
                 ("臂坏（有 drawable 在变而参数全不变，不可能）" if ar.get("contradicted")
                  else ("未采到（0 行 update）" if not ar.get("alive") else "采到了"))))
        ds = r.get("dips") or []
        print("   ① 闪一下的部件 %d 个" % len(ds))
        for d in ds[:14]:
            loc = ("  位置(%.2f,%.2f)-(%.2f,%.2f) 面积%.3f" % tuple(d[8])) if len(d) > 8 and d[8] else ""
            print("     [%s] %-26s %-4s 掉到 %.2f（前 %.2f）@第%s帧 t=%.2fs 幅度 %.3f%s"
                  % (d[0], str(d[1])[:26], d[2], d[3], d[4], d[7] if len(d) > 7 else "?", d[5], d[6], loc))
        if len(ds) > 14:
            print("     …另 %d 个见 JSON" % (len(ds) - 14))
        cs = r.get("cand") or []
        print("   ② 走出台阶形状（孤立跳变）的参数：%d 个有跳变，其中与 drawable 台阶同帧的 %d 个（打印前 %d）"
              % (len(cs), sum(1 for c in cs if c.get("at")), len(cs)))
        for c in cs:
            ats = " ".join("k%d:%.3f→%.3f" % (x[0], x[1], x[2]) for x in c["steps"][:8])
            print("     %-26s 量程[%.3g,%.3g] rep%s 变 %d 次 中位Δ%.4f 孤立跳变 %d 次（台阶同帧 %d） %s"
                  % (str(c["nm"])[:26], c["mn"], c["mx"], c["rep"], c["any"], c.get("med", 0),
                     len(c["steps"]), len(c["at"]), ats))
        if cs and cs[0].get("col"):
            print("     ── 头号候选 %s 逐帧值: %s"
                  % (cs[0]["nm"], " ".join("%.2f" % x for x in cs[0]["col"][:150])))
        for tr in (r.get("trace") or []):
            print("     ── trace %s/%s 逐帧（t, 透明度, 当时的 currentGroup）" % (tr["kind"], tr["name"]))
            tst = out["clips"][clip].get("ts") or [0, 0]
            print("        逐帧透明度: %s" % " ".join("%.2f" % x for x in tr["col"][:120]))
            print("        currentGroup: %s" % " ".join(str(x) for x in (tr.get("groups") or [])[:120]))

        # —— ③ 写入者归因
        wl = [x.strip() for x in a.wparams.split(",") if x.strip()]
        wnames = wl if wl else [c["nm"] for c in cs[:a.writers]]
        if not a.nowriters and wnames:
            raw3 = ev(JS_WRITERS + "(%s, %s, %s, %s)" % (json.dumps(clip), json.dumps(a.hold),
                                                         json.dumps(a.step), json.dumps(wnames)))
            try:
                w = json.loads(raw3) if isinstance(raw3, str) and raw3.strip().startswith("{") else {"err": str(raw3)[:300]}
            except Exception:
                w = {"err": str(raw3)[:300]}
            out["clips"][clip]["writers"] = w
            if "log" in w:
                nm_by_i = dict(zip(w.get("idx") or [], w.get("names") or []))
                print("   ③ 写入者归因（重放同一切换序列，%d 帧 / %.1fs，切 idle 在第 %s 帧，记录 %d 笔实际改动）"
                      % (w.get("frames", 0), w.get("ts", 0), w.get("switchFrame"), len(w["log"])))
                if w.get("unres"):
                    print("      ⚠️ 这些参数名不在 moc3 里: %s" % w["unres"])
                for row in w["log"][:45]:
                    k, i, vin, wt, bef, aft, st = row
                    print("     k=%-5s %-24s 传入 %-10s weight %-6s 存值 %-9s→%-9s %s"
                          % (k, str(nm_by_i.get(i, "?%s" % i))[:24], vin, wt, bef, aft, str(st)[:130]))
                if len(w["log"]) > 45:
                    print("     …另 %d 笔见 JSON" % (len(w["log"]) - 45))
            else:
                print("   ③ 归因臂未出结果: %s" % str(w)[:200])

    # —— ④ 驱动扫描
    dl = [x for x in a.drivers.split(",") if x]
    if dl:
        pin4 = [[x.split(":")[0], float(x.split(":")[1])]
                for x in re.split(r"[,\s]+", a.drvpin or "") if ":" in x]
        raw4 = ev(JS_DRIVERS + "(%s, %s, %s, %s, %s)" % (json.dumps(dl), json.dumps(max(3, a.nsweep)),
                                                     json.dumps(a.drvclip or ""),
                                                     json.dumps(int(a.drvwait * 1000)), json.dumps(pin4)))
        try:
            dv = json.loads(raw4) if isinstance(raw4, str) and raw4.strip().startswith("{") else {"err": str(raw4)[:300]}
        except Exception:
            dv = {"err": str(raw4)[:300]}
        out["drivers"] = dv
        if "drivers" in dv:
            tg = dv.get("targets") or []
            print("\n== ④ 驱动扫描：目标 %s（基准透明度 %s）" % (tg, dv.get("ref")))
            print("   能改变这些 drawable 透明度的参数：%d / %d（每参数量程内 %d 点，共 %s 次 core.update）"
                  % (len(dv["drivers"]), dv.get("params"), dv.get("nstep"), dv.get("updates")))
            for x in dv["drivers"][:25]:
                series_all = x[5]
                segs = []
                for j, tn in enumerate(tg):
                    series = [(v, r[j]) for v, r in series_all]
                    keep = [series[0]] + [p for k, p in enumerate(series[1:], 1)
                                          if abs(p[1] - series[k - 1][1]) > 1e-3]
                    if len(keep) > 1:
                        segs.append("%s: %s" % (tn, " ".join("%.3g→%.2f" % p for p in keep)))
                print("     %-24s 量程[%.3g,%.3g] default %.3g rep%s"
                      % (str(x[0])[:24], x[1], x[2], x[3], x[4]))
                for s in segs:
                    print("        %s" % s[:200])
            if dv.get("miss"):
                print("   ⚠️ 这些名字不在模型里: %s" % dv["miss"])
            print("   基线 = %s（在播=%s）目标基准透明度 %s"
                  % (dv.get("baseline"), dv.get("group"), dv.get("ref")))
            if dv.get("pinEcho") is not None:
                print("   钉值回显 [参数名, 索引, 钉后实际值, min, max]: %s" % dv.get("pinEcho"))
            print("   恒等自检: 扫完回到基线输入重读 = %s ⇒ %s"
                  % (dv.get("ref2"), ("一致 ✅" if not dv.get("drift")
                                      else "**漂移 %d 个目标 ⇒ 系统里还有不随输入重算的第二套状态，"
                                           "本基线的结论一律不作数** ❌" % dv.get("drift"))))
            bl = dv.get("blockers") or []
            print("   探测二『挡路者』（其余保持基线值、只把这个改回 moc3 默认 ⇒ 目标就亮）：%d 个" % len(bl))
            for x in bl[:20]:
                print("     %-24s 基线值 %-8s 默认 %-8s → 目标读数 %s" % (str(x[0])[:24], x[1], x[2], x[3]))
        else:
            print("\n== ④ 驱动扫描未出结果: %s" % str(dv)[:250])

    # —— ⑤ 全量绑定表
    if a.mapall:
        raw5 = ev(JS_MAPALL + "(%s)" % json.dumps(max(3, a.nsweep)))
        try:
            mp = json.loads(raw5) if isinstance(raw5, str) and raw5.strip().startswith("{") else {"err": str(raw5)[:300]}
        except Exception:
            mp = {"err": str(raw5)[:300]}
        if "map" in mp:
            fpm = os.path.join(ROOT, ".diag", "l2d_opacity_map_%s.json" % a.model)
            with open(fpm, "w", encoding="utf-8") as fh:
                json.dump(mp, fh, ensure_ascii=False)
            print("\n== ⑤ 全量绑定表：%d 个参数 × 量程内 %d 点 = %s 次 core.update，读全部 %d 个 drawable"
                  % (mp["params"], mp["nstep"], mp["updates"], mp["drawables"]))
            print("   能改变任何 mesh 透明度的参数 %d 个（另有 %d 个参数扫完全程都没碰到可见性）；"
                  "参数×mesh 关联 %d 对；**任何参数都碰不到的 mesh %d 个**；"
                  "剔掉假阳性关联 %d 条（11 点读数全等 = 基准里关着、一动就开，不是绑定）"
                  % (mp["nParamsWithEffect"], mp["params"] - mp["nParamsWithEffect"],
                     mp["pairs"], mp["nUntouched"], mp.get("nFlatRejected", -1)))
            print("   台账 → %s（含每个 mesh 的 11 点透明度曲线，可离线复算）" % fpm)
            print("   覆盖面最广的参数（前 12）：")
            for x in sorted(mp["map"], key=lambda y: -y[6])[:12]:
                print("     %-24s 量程[%.3g,%.3g] default %.3g → 影响 %d 个 mesh"
                      % (str(x[1])[:24], x[2], x[3], x[4], x[6]))
        else:
            print("\n== ⑤ 绑定表未出结果: %s" % str(mp)[:250])

    # —— ⑩ snap 的 A/B 时间轴（修法 (b) 的验收）
    if a.snapab and "->" in a.snapab:
        frm, to = [x.strip() for x in a.snapab.split("->", 1)]
        set25 = []
        lf = os.path.join(ROOT, ".diag", "l2d_opacity_map_%s.json" % a.model)
        if os.path.exists(lf):
            ld = json.load(open(lf, encoding="utf-8"))
            pn0 = [x.strip() for x in a.snapP.split(",") if x.strip()]
            tgt = pn0[0] if pn0 else ""
            for e in ld.get("map", []):
                if e[1] == tgt:
                    set25 = [ld["names"][x[0]] for x in e[7]]
                    break
        cfg = {"from": frm, "to": to,
               "setA": [x.strip() for x in a.snapA.split(",") if x.strip()],
               "setB": [x.strip() for x in a.snapB.split(",") if x.strip()],
               "set25": set25,
               "pnames": [x.strip() for x in a.snapP.split(",") if x.strip()],
               "frames": max(12, int(a.hold * 1000 / max(1, a.step))), "stepMs": max(16, a.step)}
        raw10 = ev(JS_SNAPAB + "(" + json.dumps(cfg) + ")")
        try:
            ab = json.loads(raw10) if isinstance(raw10, str) and raw10.strip().startswith("{") else {"err": str(raw10)[:400]}
        except Exception:
            ab = {"err": str(raw10)[:400]}
        if "off" in ab and "on" in ab:
            f10 = os.path.join(ROOT, ".diag", "l2d_snapab_%s.json" % a.model)
            with open(f10, "w", encoding="utf-8") as fh:
                json.dump(ab, fh, ensure_ascii=False)
            print("\n== ⑩ snap A/B：%s -> %s（A 组 %d 片 / B 组 %d 片，参数 %s）"                  % (frm, to, len(cfg["setA"]), len(cfg["setB"]), cfg["pnames"]))
            for mode in ("off", "on"):
                rows = ab[mode]["rows"]
                head = "切换" if not rows else rows[0][1]
                # 切换帧 = currentGroup 第一次变成 to 的那一帧
                k0 = next((i for i, r in enumerate(rows) if r[1] == to), 0)
                win = rows[k0:]
                darki = [i for i in range(len(win)) if win[i][3] < 0.05 and win[i][4] < 0.05]
                secs = round(sum(max(0.0, win[i + 1][0] - win[i][0]) for i in darki if i + 1 < len(win)), 3)
                print("   %-4s 采样 %d 帧（切换在第 %d 帧）；A∧B 同时灭 %d 帧 / 约 %.2fs；切换后 nLit 最低 %s；A 峰 %.2f B 峰 %.2f；台账集(该参数能影响的全部 mesh) 最低 %d/%d 亮、峰值 %.2f"
                      % ("修法关" if mode == "off" else "修法开", len(rows), k0, len(darki), secs,
                         min([r[2] for r in win]) if win else "-",
                         max([r[3] for r in win]) if win else -1, max([r[4] for r in win]) if win else -1,
                         min([r[5] for r in win]) if win else -1, len(cfg["set25"]),
                         max([r[6] for r in win]) if win else -1))
                tl = os.path.join(ROOT, ".diag", "l2d_snapab_%s_%s.txt" % (a.model, mode))
                with open(tl, "w", encoding="utf-8") as fh:
                    fh.write("ts group nLit maxA maxB nLedger25 maxLedger25 %s\n" % " ".join(cfg["pnames"]))
                    for r in rows:
                        fh.write("%.3f %s %d %.3f %.3f %s\n" % (r[0], r[1], r[2], r[3], r[4],
                                                                " ".join("-" if x is None else str(x) for x in r[5:])))
            print("   前端 snap 层自证: %s  (标记=%s)"
                  % (json.dumps(ab.get("snapDbg"), ensure_ascii=False),
                     json.dumps(ab.get("marker"), ensure_ascii=False)))
            print("   时间轴 → %s / .diag/l2d_snapab_%s_{off,on}.txt" % (f10, a.model))
        else:
            print("\n== ⑩ snap A/B 未出结果: %s" % str(ab)[:300])

    # —— ⑪ 部件门：同一趟里分别"播着 A 条 clip"与"播着 B 条 clip"读部件实态
    if a.partcheck:
        meshes = [x.strip() for x in a.partcheck.split(",") if x.strip()]
        pcs = []
        for c in [a.pcclip, a.pcalso]:
            if not c:
                continue
            raw11 = ev(JS_PARTCHECK + "({clip:%s, meshes:%s, wait:%s, stepMs:%s})"                       % (json.dumps(c), json.dumps(meshes), a.pcwait, max(16, a.step)))
            try:
                pcs.append(json.loads(raw11) if isinstance(raw11, str) and raw11.strip().startswith("{")
                             else {"clip": c, "err": str(raw11)[:300]})
            except Exception:
                pcs.append({"clip": c, "err": str(raw11)[:300]})
        f11 = os.path.join(ROOT, ".diag", "l2d_partcheck_%s.json" % a.model)
        with open(f11, "w", encoding="utf-8") as fh:
            json.dump({"meshes": meshes, "runs": pcs}, fh, ensure_ascii=False)
        print("\n== ⑪ 部件门（目标 %s）→ %s" % (",".join(meshes[:4]), f11))
        for r in pcs:
            if "err" in r:
                print("   clip=%s 未出结果: %s" % (r.get("clip"), r["err"]))
                continue
            print("   播 %s（在播=%s，%d 帧后读）部件 %d 个，非默认的 %d 个；默认值可读=%s"
                  % (r["clip"], r["playing"], r["frames"], r["partCount"], r["nonDefault"], r["hasDefaults"]))
            for x in r["targets"]:
                print("     %-14s op=%-6s 部件=%-22s 部件当前=%-6s 默认=%-6s blend=%s"
                      % (str(x.get("mesh"))[:14], x.get("op"), str(x.get("part"))[:22],
                         x.get("partOp"), x.get("partDef"), x.get("partBlend")))
            if r["nonDefaultList"]:
                print("     非默认部件前 12: %s" % ", ".join(
                    "%s(现%.2f/默%.2f)" % (n[0][:18], n[1], n[2]) for n in r["nonDefaultList"][:12]))

    # —— ⑫ 合取门二分：实态下灭着的片，是哪几个参数一起关着的（逐个扫量程在合取门下必然空手而归）
    if a.gatefind:
        meshes = [x.strip() for x in a.gatefind.split(",") if x.strip()]
        gpin = [[x.split(":")[0], float(x.split(":")[1])]
                for x in re.split(r"[,\s]+", a.gpin or "") if ":" in x]
        cfg12 = {"meshes": meshes, "clip": a.gclip or "", "waitMs": int(max(0.0, a.gwait) * 1000),
                 "pin": gpin}
        raw12 = ev(JS_GATEFIND + "(" + json.dumps(cfg12) + ")")
        try:
            g12 = json.loads(raw12) if isinstance(raw12, str) and raw12.strip().startswith("{") else {"err": str(raw12)[:300]}
        except Exception:
            g12 = {"err": str(raw12)[:300]}
        f12 = os.path.join(ROOT, ".diag", "l2d_gatefind_%s.json" % a.model)
        with open(f12, "w", encoding="utf-8") as fh:
            json.dump({"cfg": cfg12, "res": g12}, fh, ensure_ascii=False)
        if "err" in g12 or "fail" in g12:
            print("\n== ⑫ 合取门未出结果: %s" % str(g12)[:300])
        else:
            ok12 = max(g12["minSetRead"] or [0]) > 0.5
            print("\n== ⑫ 合取门二分（目标 %s，clip=%s，pin=%s）"
                  % (",".join(meshes), cfg12["clip"] or "setup", cfg12["pin"]))
            print("   名字数组自证 [名, D.ids 下标, __drawableIds 下标, 长度, 是否逐位相同]: %s"
                  % (g12.get("idxCheck"),))
            print("   与默认值不同的参数 %d 个 | 全默认+pin 读数 %s | 全实态+pin 读数 %s"
                  % (g12["nDiff"], g12["atDefault"], g12["atLive"]))
            print("   二分收敛到 %d 个参数（%d 步）；只还原这一组时读数 %s → %s"
                  % (len(g12["minSet"]), g12["steps"], g12["minSetRead"],
                     "门就在这组里" if ok12 else "仍不够 = 合取门，需要更多参数同时还原"))
            for x in g12["minSet"][:20]:
                print("     %-24s 实态 %-9s 默认 %-9s" % (str(x[0])[:24], x[1], x[2]))
            print("   台账 → %s" % f12)

    # —— ⑨ 变形者闸：这个参数在自己量程内挪不挪几何（挪 = 不能 snap，会把姿态硬跳放回来）
    if a.deform:
        spec = a.deform
        if spec.startswith("@"):
            txt = open(spec[1:], encoding="utf-8").read().strip()
            try:
                j = json.loads(txt)
                nm = list(j["params"]) if isinstance(j, dict) and "params" in j else j
            except Exception:
                nm = [x.strip() for x in txt.splitlines() if x.strip()]
        else:
            nm = [x.strip() for x in spec.split(",") if x.strip()]
        raw9 = ev(JS_DEFORM + "(%s, %d)" % (json.dumps(nm), max(3, a.nsweep)))
        try:
            df = json.loads(raw9) if isinstance(raw9, str) and raw9.strip().startswith("{") else {"err": str(raw9)[:300]}
        except Exception:
            df = {"err": str(raw9)[:300]}
        if "params" in df:
            f9 = os.path.join(ROOT, ".diag", "l2d_deform_%s.json" % a.model)
            with open(f9, "w", encoding="utf-8") as fh:
                json.dump(df, fh, ensure_ascii=False)
            print("\n== ⑨ 变形者闸：%d 个参数 × 量程内 %d 点 = %s 次 core.update（只比两点都亮着的 mesh 的屏幕框）"
                  % (len(df["params"]), df["nstep"], df["updates"]))
            for x in df["params"]:
                if "err" in x:
                    print("     %-24s %s" % (str(x["name"])[:24], x["err"]))
                    continue
                print("     %-24s 量程[%.3g,%.3g] 最大框位移 %.4f → %s"
                      % (str(x["name"])[:24], x["mn"], x["mx"], x["maxBBoxShift"],
                         "形变者(不可 snap)" if x["maxBBoxShift"] > 0.01 else "纯显隐选择器(可 snap)"))
            print("   台账 → %s" % f9)
        else:
            print("\n== ⑨ 变形者闸未出结果: %s" % str(df)[:250])

    # —— ⑥ 单参数 A/B 截图：只回答「这个参数管的是画面上哪一块」，不当验收判据
    sm = re.match(r"^([\w\-]+):(.+)$", a.shot or "")
    if sm:
        pname, vals = sm.group(1), [float(x) for x in sm.group(2).split(",") if x.strip() != ""]
        odir = os.path.join(ROOT, ".diag", "l2d_param_shot_%s" % a.model)
        os.makedirs(odir, exist_ok=True)
        shots = []
        for v in vals:
            r6 = ev(JS_SHOT + "(%s, %s)" % (json.dumps(pname), json.dumps(v)))
            print("\n⑥ 置 %s=%s → %s" % (pname, v, str(r6)[:160]))
            png = cmd("Page.captureScreenshot", {"format": "png"})
            fp6 = os.path.join(odir, "%s_%g.png" % (pname, v))
            with open(fp6, "wb") as fh:
                fh.write(base64.b64decode(png["data"]))
            shots.append((v, fp6))
        if len(shots) >= 2:
            try:
                from PIL import Image, ImageChops
                a1 = Image.open(shots[0][1]).convert("RGB")
                a2 = Image.open(shots[-1][1]).convert("RGB")
                if a1.size != a2.size:
                    a2 = a2.resize(a1.size)
                w = 620
                h1 = int(a1.size[1] * w / a1.size[0])
                ab = Image.new("RGB", (w * 2 + 12, h1), (255, 255, 255))
                ab.paste(a1.resize((w, h1)), (0, 0))
                ab.paste(a2.resize((w, h1)), (w + 12, 0))
                fpa = os.path.join(odir, "%s_ab.png" % pname)
                ab.save(fpa)
                print("   并排对照（左 %s / 右 %s）→ %s" % (shots[0][0], shots[-1][0], fpa))
                d = ImageChops.difference(a1, a2).convert("L")
                mask = d.point(lambda x: 255 if x > 18 else 0)
                box = mask.getbbox()
                npx = sum(1 for x in mask.getdata() if x)
                over = a2.convert("RGB").copy()
                over.putdata([(255, 0, 0) if m else p for p, m in zip(over.getdata(), mask.getdata())])
                fpd = os.path.join(odir, "%s_diff.png" % pname)
                over.save(fpd)
                print("   两档差 %s 像素（占画面 %.2f%%）包围盒 %s → %s"
                      % (npx, 100.0 * npx / (a1.size[0] * a1.size[1]), box, fpd))
            except Exception as e:
                print("   差图生成失败: %r" % (e,))

    # —— ⑦ 几何导出：把 ArtMesh 编号对应回画面位置
    if a.dumpgeo:
        r7 = ev(JS_GEO + "(0)")
        try:
            g7 = json.loads(r7) if isinstance(r7, str) and r7.strip().startswith("{") else {"err": str(r7)[:200]}
        except Exception:
            g7 = {"err": str(r7)[:200]}
        if "rows" in g7:
            fp7 = os.path.join(ROOT, ".diag", "l2d_geo_%s.json" % a.model)
            with open(fp7, "w", encoding="utf-8") as fh:
                json.dump(g7, fh, ensure_ascii=False)
            print("\n⑦ 几何导出 %d 个 mesh ×2 份（当前姿态 + setup 默认姿态；画布 %.2fx%.2f 单位，"
                  "canvas %.0fx%.0f px @(%0.f,%0.f)）→ %s"
                  % (len(g7["rows"]), g7["cux"], g7["cuy"], g7["rect"]["w"], g7["rect"]["h"],
                     g7["rect"]["left"], g7["rect"]["top"], fp7))
            print("   motion 状态字段: %s | 条目字段: %s | 数值: %s"
                  % ((g7.get("state") or {}).get("keys"), (g7.get("state") or {}).get("itemKeys"),
                     (g7.get("state") or {}).get("itemNums")))
        else:
            print("\n⑦ 几何导出失败: %s" % str(g7)[:200])

    # —— ⑧ 藏起指定 mesh 后截图（先拍一张同姿态基准，再拍藏掉的）
    hl = [x.strip() for x in a.hide.split(",") if x.strip()]
    if hl:
        shots8 = {}
        for tag, lst in (("base", []), ("hide", hl)):
            r8 = ev(JS_HIDE + "(%s, %s, %s)" % (json.dumps(lst), json.dumps(a.hideclip or ""),
                                       json.dumps(int(a.hidewait * 1000))))
            try:
                j8 = json.loads(r8) if isinstance(r8, str) else (r8 or {})
                print("   ⑧ %-5s clip=%s 在播=%s Param25=%s | 藏前亮着 %d/%d 片(其中在画面内 %s) stillZero=%s"
                      % (tag, j8.get("clip"), j8.get("group"), j8.get("Param25"),
                         j8.get("openBefore"), j8.get("hidden"), j8.get("stillZero"),
                         j8.get("onScreen")))
            except Exception:
                print("   ⑧ %s → %s" % (tag, str(r8)[:180]))
            png = cmd("Page.captureScreenshot", {"format": "png"})
            fp8 = os.path.join(ROOT, ".diag", "l2d_hide_%s_%s%s.png"
                               % (a.model, tag, ("_" + a.hideclip) if a.hideclip else ""))
            with open(fp8, "wb") as fh:
                fh.write(base64.b64decode(png["data"]))
            shots8[tag] = fp8
        try:
            from PIL import Image, ImageChops
            i1 = Image.open(shots8["base"]).convert("RGB")
            i2 = Image.open(shots8["hide"]).convert("RGB")
            d8 = ImageChops.difference(i1, i2).convert("L")
            npx8 = sum(1 for x in d8.getdata() if x > 12)
            if npx8 < 50:
                print("   ❌ 两张截图只差 %d 像素 ⇒ **截图没反映改动，这条臂坏了**，"
                      "不要根据它下任何结论（自检：藏 5 片以上必然看得见变化）" % npx8)
            else:
                print("   自检：base 与 hide 差 %d 像素（>50 ⇒ 截图确实反映了改动）" % npx8)
            w = 560; h = int(i1.size[1] * w / i1.size[0])
            ab = Image.new("RGB", (w * 2 + 12, h), (255, 255, 255))
            ab.paste(i1.resize((w, h)), (0, 0)); ab.paste(i2.resize((w, h)), (w + 12, 0))
            fpa = os.path.join(ROOT, ".diag", "l2d_hide_%s_ab%s.png"
                               % (a.model, ("_" + a.hideclip) if a.hideclip else ""))
            ab.save(fpa)
            print("   并排（左=基准 setup 姿态 / 右=藏起 %d 片）→ %s" % (len(hl), fpa))
        except Exception as e:
            print("   并排图失败: %r" % (e,))

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
