# -*- coding: utf-8 -*-
"""l2d_part_flicker_probe.py — 抓「部件闪一下」：把台阶定位到**具体哪一个参数**，并回答"谁写的"。

四条臂（同一次运行按顺序出）：
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
      const c = window.__cap;
      if (c && c.rows.length < c.max) {
        const M = this._model;
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
  const scan=(mat, ids, kind)=>{
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
                        hard?'hard':'soft', hit.v, hit.before, cap.ts[hit.k], +(hi-lo).toFixed(3), hit.k]);
    }
    return {dips:out, varying};
  };
  const A=scan(cap.partrows, window.__partIds, 'part'), B=scan(cap.drows, window.__drawableIds, 'drawable');
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
JS_DRIVERS = r"""(async (names, nstep) => {
  const core=window.__m.internalModel.coreModel, mm=window.__m.internalModel.motionManager;
  const M=core._model, P=M.parameters, D=M.drawables;
  const di=names.map(n=>window.__drawableIds.indexOf(n));
  const miss=names.filter((n,j)=>di[j]<0);
  const ok=di.map((v,j)=>[names[j], v]).filter(x=>x[1]>=0);
  if(!ok.length) return JSON.stringify({fail:'目标 drawable 都不在模型里', miss});
  window.__cap=null; window.__wset=null;
  const ambWas=window.__ambOff; window.__ambOff=true;
  try{ mm.stopAllMotions(); }catch(e){}
  const base=[]; for(let i=0;i<P.count;i++) base.push(P.values[i]);
  const read=()=>ok.map(x=>+D.opacities[x[1]].toFixed(3));
  core.update(); const ref=read();
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
  for(let i=0;i<P.count;i++) P.values[i]=base[i];
  core.update(); window.__ambOff=ambWas;
  return JSON.stringify({targets:ok.map(x=>x[0]), ref, miss, params:P.count, nstep, updates, drivers:drv});
})"""


# ---------------------------------------------------------------- ⑤ 全量「参数 → 哪个 mesh 显隐」绑定表
JS_MAPALL = r"""(async (nstep) => {
  const core=window.__m.internalModel.coreModel, mm=window.__m.internalModel.motionManager;
  const M=core._model, P=M.parameters, D=M.drawables;
  window.__cap=null; window.__wset=null;
  const ambWas=window.__ambOff; window.__ambOff=true;
  try{ mm.stopAllMotions(); }catch(e){}
  const nd=D.count, np=P.count;
  const base=[]; for(let i=0;i<np;i++) base.push(P.values[i]);
  const ref=new Float32Array(nd);
  core.update(); ref.set(D.opacities);
  const out=[]; let updates=0, pairs=0;
  const touched=new Uint8Array(nd);
  for(let i=0;i<np;i++){
    const mn=P.minimumValues[i], mx=P.maximumValues[i], map=new Map();
    for(let q=0;q<=nstep;q++){
      P.values[i]=mn+(mx-mn)*q/nstep; core.update(); updates++;
      const O=D.opacities;
      for(let d=0;d<nd;d++){ const x=O[d];
        if(Math.abs(x-ref[d])>1e-3){
          const cur=map.get(d);
          if(cur) cur.push([q,+x.toFixed(3)]); else map.set(d,[[q,+x.toFixed(3)]]);
        } }
    }
    P.values[i]=base[i];
    if(!map.size) continue;
    const aff=[]; map.forEach((arr,d)=>{ aff.push([d,arr]); touched[d]=1; });
    pairs+=aff.length;
    out.push([i, window.__pid[i], +mn.toFixed(3), +mx.toFixed(3), +P.defaultValues[i].toFixed(3),
              P.repeats[i], aff.length, aff]);
  }
  for(let i=0;i<np;i++) P.values[i]=base[i];
  core.update(); window.__ambOff=ambWas;
  const un=[]; for(let d=0;d<nd;d++) if(!touched[d]) un.push(d);
  return JSON.stringify({nstep, params:np, drawables:nd, updates,
    nParamsWithEffect:out.length, pairs, nUntouched:un.length, untouched:un,
    ref:Array.from(ref, x=>+x.toFixed(3)), names:window.__drawableIds, map:out});
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
    ap.add_argument("--mapall", action="store_true", help="⑤ 全量「参数→哪些 mesh 显隐」绑定表（落 .diag/l2d_opacity_map_<model>.json）")
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
            print("     [%s] %-26s %-4s 掉到 %.2f（前 %.2f）@第%s帧 t=%.2fs 幅度 %.3f"
                  % (d[0], str(d[1])[:26], d[2], d[3], d[4], d[7] if len(d) > 7 else "?", d[5], d[6]))
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
        raw4 = ev(JS_DRIVERS + "(%s, %s)" % (json.dumps(dl), json.dumps(max(3, a.nsweep))))
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
                  "参数×mesh 关联 %d 对；**任何参数都碰不到的 mesh %d 个**"
                  % (mp["nParamsWithEffect"], mp["params"] - mp["nParamsWithEffect"],
                     mp["pairs"], mp["nUntouched"]))
            print("   台账 → %s（含每个 mesh 的 11 点透明度曲线，可离线复算）" % fpm)
            print("   覆盖面最广的参数（前 12）：")
            for x in sorted(mp["map"], key=lambda y: -y[6])[:12]:
                print("     %-24s 量程[%.3g,%.3g] default %.3g → 影响 %d 个 mesh"
                      % (str(x[1])[:24], x[2], x[3], x[4], x[6]))
        else:
            print("\n== ⑤ 绑定表未出结果: %s" % str(mp)[:250])

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
