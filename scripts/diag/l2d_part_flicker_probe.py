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
  ⑪ `--partcheck` 部件门：读目标片所属部件的当前值。**⚠️ 本臂已判定不可信**：`D.partMatch` 这个键名
     在 wasm 视图里不存在（真名是 `parentPartIndices`）、`parts.defaultValues` 也不存在，
     所以它报的"非默认部件 0 个"是 `undefined` 参与减法的产物 —— 那次"部件门否证"不算数（由 ⑬ 重做）。
  ⑫ `--gatefind` 合取门二分。⚠️ 它的 `atDefault` 与 ⑤ 的台账在同参数下读出不同值 ⇒ 见 ⑬/⑮/⑯。
  ⑬ `--recon` **台账矛盾判定**：同一趟同一套索引里对读「⑤ 的逐档扫」与「⑫ 的整数组钉」，
     外加四把排除：part 是输入还是输出、core 有没有派生参数链、三种读法（旧视图/重取视图/框架 getter）
     是否一致、直写缓冲与走框架 setter 是否一致。全部一致 ⇒ 结论只能是**历史依赖**。
  ⑭ `--reconshot` 同参数两历史各截一张图比像素（分「引擎真锁存」与「读错缓冲」两种落法）。
     ⚠️ 只调 `core.update()+app.render()` 时"像素不变"证明不了"缓冲不管渲染"——每片 alpha 是在
     **`model.update()`** 里同步的，所以两种驱动都要跑（`via=model` 那趟必须排在前面，否则不冷）。
  ⑮ `--reconcold` **冷态逐拍**：一次跳到目标值后逐拍读 ⇒ 判"显隐是第几拍才结算"。
  ⑯ `--coldmap Param25:0,0.1,0.2` **冷态逐值全模型图**：每个值都从 moc3 默认**一次跳到**，
     正序 + 倒序各一遍。**两遍不一致 = 有滞回 ⇒ ⑤ 的台账不能当函数表**（本项目实测：正序爬完再回默认，
     那 29 片仍是 1，复位不回滚）。`--focus` 只盯指定片，否则打印每档新亮/新灭名单。
  ⑰ `--coldmapall auto` **冷态全量台账 + 阈值二分**：把 ⑯ 的形状铺到整批参数，并且
     ⑴ 每次探测前先复位、把「复位后仍不等于冷基线」的片数记成 `drift`（滞回的直接计数，不用事后再对拍）；
     ⑵ 每 20 个参数**换一次新页面**（滞回跨参数累积，冷基线只能靠新会话保证；跨会话冷基线是否逐位相同由 `--coldmerge` 验）；
     ⑶ 阈值不再取 11 点网格的中点：对每个「相邻网格签名不同」的区间**二分到 eps**，两侧各收一遍；
        区间里还夹着第三种签名的记 `tertiary`（不发布该阈值）。
     正序与倒序**各起一次进程**（`--coldmapall auto` / `--coldmapall auto --coldrev`），
     再 `--coldmerge`（不开浏览器）按三条判据发布 `.diag/l2d_cold_ledger_<model>.json`，
     下游 `l2d_snap_criterion_scan.py --ledger @该文件`。
  ⑱ `--latchreset Param25` **棘轮能不能复位**：⑰ 实跑发现 `drift`/`nChg` **只增不减**、还跨参数带着走
     ⇒ 一页里只有**第一次**探测是冷的。这一臂先做一次干净单读当基准，再故意污染，然后逐个试复位手段
     （直写片缓冲 / 直写+update / 只写参数默认 / 框架 setter / 写 part 默认 / 组合），
     复位成功还要**再探同一值、签名须与干净单读逐位相同**才算数；同时列出 core 上真实存在的 reset 类 API。
     它决定 ⑰ 的代价：能复位 ⇒ 按组扫；不能复位 ⇒ 一页一探测，全库批量当场判死。
     ★实测：**六种复位全部打不掉、连打 200 拍也不回、同值重探幂等、不同值钉住的是不同的片**
       ⇒ 显隐是**路径函数**而不是参数的函数（§123 追加-XV）⇒ ⑰ 那种「重生成函数表」的路整体作废。
  ⑲ `--latchlaw Param25` **锁存律**：既然不存在函数表，唯一还能拿到的对应关系是「一次边沿写了什么」。
     **一页只探一个值**：冷基线 → 一次跳到 v（= 该值的干净响应 R(v)）→ 回默认打一拍并连打 N 拍
     （仍不等于冷基线的那些 = 该值留下的锁存写入 L(v)，带读数，分得清"钉在亮"还是"钉在灭"）。
     值表就是成本（每页 20~40s）⇒ 必须跑在脱离宿主的进程里；每页即时落盘，中途崩了留半成品。
     产物 `.diag/l2d_latchlaw_<model>_<param>.json`，用法 `--latchlaw Param25`（默认 12 个值）
     或 `--latchlaw "Param25:0,0.05,0.1"`。

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


# ---------------------------------------------------------------- ⑭ 状态定格 + 截图（把"缓冲读数"与"屏幕像素"对上）
# 为什么要它：⑬ 证到「同一份参数数组，29 片的透明度冷态读 0、暖态读 1，且回不去」。
# 这句话有两种截然不同的落法：**(引擎真的按历史决定可见性**（那台账就不是函数表，snapswitch 的前提塌），
# 还是 **我们读的这块缓冲根本不是渲染用的那份**（那从台账起的所有结论都作废）。
# 只有一种办法分开它们：同参数、两种历史，各截一张图比像素。
JS_SET_STATE = r"""(async (cfg) => {
  const core=window.__m.internalModel.coreModel, mm=window.__m.internalModel.motionManager;
  const M=core._model, P=M.parameters, D=M.drawables, PT=M.parts;
  window.__cap=null; window.__wset=null; window.__hideSet=null;
  window.__ambOff=true; window.__snapOff=true;          // 环境层与 snap 层都会写参数，定格期间全关
  try{ window.__app.ticker.stop(); }catch(e){}
  try{ window.__m.autoUpdate=false; }catch(e){}
  try{ mm.stopAllMotions(); }catch(e){}
  const DEF=Array.from(P.defaultValues);
  const withPin=(src)=>{ const v=src.slice();
    for(const pv of cfg.pin){ const k=P.ids.indexOf(pv[0]); if(k>=0) v[k]=pv[1]; } return v; };
  const target=(cfg.state==='B')? withPin(DEF): DEF;
  let wrote=0; for(let i=0;i<P.count;i++) if(Math.abs(P.values[i]-target[i])>1e-9){ P.values[i]=target[i]; wrote++; }
  // 两种驱动必须分开测：pixi 侧每片的 alpha 是在 **model.update()** 里从 core 缓冲同步过去的，
  // 只调 core.update() + app.render() 时"像素不变"只能证明"没触发同步"，不能证明"缓冲不管渲染"。
  const used=(cfg.via==='model' && typeof window.__m.update==='function')? 'model' : 'core';
  for(let k=0;k<(cfg.repeat||1);k++){
    if(used==='model'){ try{ window.__m.update(1/60); }catch(e){ core.update(); } }
    else core.update();
  }
  try{ window.__app.render(); }catch(e){}
  let litPixi=null;
  try{ litPixi=window.__m.children.filter(c=>c.visible!==false && (c.alpha||0)>0.05).length; }catch(e){}
  return JSON.stringify({state:cfg.state, via:used, wrote, updates:cfg.repeat||1,
    litPixi,
    pin:(()=>{ const o={}; for(const pv of cfg.pin){ const k=P.ids.indexOf(pv[0]);
      o[pv[0]]=(k<0? null: +P.values[k].toFixed(4)); } return o; })(),
    targets:cfg.meshes.map(n=>{ const j=D.ids.indexOf(n); return j<0? null : +D.opacities[j].toFixed(3); }),
    partNon1:(()=>{ let c=0; for(let i=0;i<PT.count;i++) if(Math.abs(PT.opacities[i]-1)>1e-6) c++; return c; })()});
})"""


# ---------------------------------------------------------------- ⑮ 冷态逐拍：一次跳变之后，显隐要第几拍才结算？
# 为什么单独一条臂：⑬/⑭ 的读数全都建立在"每档扫完就打一拍"的时序上，而冷态实测出现
# 「同一份参数，1 拍读 0、多拍读 1」⇒ 台账记的**阈值位置**可能是"第几拍"的假象，不是绑定阈值。
# 这条臂在**全新页面**上只做一件事：冻住 → 全默认 → 一次跳到 pin → 逐拍读 N 拍 → 一次跳回默认 → 再逐拍读 N 拍。
# 中途绝不"先扫一遍"，所以没有预热污染；判据是「第几拍才变」而不是「变不变」。
JS_RECONCOLD = r"""(async (cfg) => {
  const im=window.__m.internalModel, core=im.coreModel, mm=im.motionManager;
  const M=core._model, P=M.parameters, D=M.drawables, PT=M.parts;
  window.__cap=null; window.__wset=null; window.__hideSet=null;
  window.__ambOff=true; window.__snapOff=true;
  try{ window.__app.ticker.stop(); }catch(e){}
  try{ window.__m.autoUpdate=false; }catch(e){}
  try{ mm.stopAllMotions(); }catch(e){}
  const ti=cfg.meshes.map(n=>D.ids.indexOf(n));
  const DEF=Array.from(P.defaultValues);
  const pinIx=cfg.pin.map(pv=>[pv[0], P.ids.indexOf(pv[0]), pv[1]]);
  const withPin=(src)=>{ const v=src.slice(); for(const e of pinIx) if(e[1]>=0) v[e[1]]=e[2]; return v; };
  const rd=()=>ti.map(j=>j<0? null : +D.opacities[j].toFixed(3));
  const pinv=()=>pinIx.map(e=>e[1]<0? null : +P.values[e[1]].toFixed(4));
  const setv=(vals)=>{ let w=0; for(let i=0;i<P.count;i++) if(Math.abs(P.values[i]-vals[i])>1e-9){ P.values[i]=vals[i]; w++; } return w; };
  const seq=[];
  setv(DEF); core.update(); seq.push(['base', 0, rd(), pinv()]);
  const want=withPin(DEF); setv(want);
  for(let k=1;k<=cfg.n;k++){ core.update(); seq.push(['up', k, rd(), pinv()]); }
  setv(DEF);
  for(let k=1;k<=cfg.n;k++){ core.update(); seq.push(['down', k, rd(), pinv()]); }
  // 第二拍之后若才变 ⇒ 台账的"阈值"里混着"第几拍"；若从第一拍起就可逆 ⇒ ⑬ 的多拍扫没问题，
  // 而之前的冷/暖差异是别的东西（那时才回头找）。
  window.__hideSet=null; window.__ambOff=cfg.ambOff||false;
  try{ window.__m.autoUpdate=true; }catch(e){}
  try{ window.__app.ticker.start(); }catch(e){}
  return JSON.stringify({meshes:cfg.meshes, idx:ti, pin:cfg.pin, n:cfg.n, seq});
})"""


# ---------------------------------------------------------------- ⑯ 冷态逐值全模型图：每个值都从默认**一次跳到**，绝不分档爬
# 为什么必须要它：⑮ 证到「一次跳到 0.5 只灭掉 ArtMesh36，B 组手全程不动」，
# 而臂 ⑤ 的台账（逐档 0→0.1→0.2…爬上去）却说 Param25 是 A/B 两组的互斥开关、还带 0.1 宽的"死区"。
# 两者只差在**到达路径**：爬档会留下滞回。⇒ 台账不能当函数表用，按它生成的 snapswitch 表前提也塌了。
# 这一臂只做"每个值都从 moc3 默认一次跳到、读全模型"，并且**正序+倒序各跑一遍**：
# 两遍结果一致才叫函数表；不一致就是滞回，且滞回本身就是"中途一闪"的来源。
JS_COLDMAP = r"""(async (cfg) => {
  const im=window.__m.internalModel, core=im.coreModel, mm=im.motionManager;
  const M=core._model, P=M.parameters, D=M.drawables, PT=M.parts;
  window.__cap=null; window.__wset=null; window.__hideSet=null;
  window.__ambOff=true; window.__snapOff=true;
  try{ window.__app.ticker.stop(); }catch(e){}
  try{ window.__m.autoUpdate=false; }catch(e){}
  try{ mm.stopAllMotions(); }catch(e){}
  const DEF=Array.from(P.defaultValues);
  const k=P.ids.indexOf(cfg.param);
  if(k<0) return JSON.stringify({fail:'参数不在 moc3 里', param:cfg.param});
  const nd=D.count, ids=Array.from(D.ids);
  const setv=(vals)=>{ let w=0; for(let i=0;i<P.count;i++) if(Math.abs(P.values[i]-vals[i])>1e-9){ P.values[i]=vals[i]; w++; } core.update(); return w; };
  const snap=()=>{ const a=new Float32Array(nd); a.set(D.opacities); return a; };
  const passes=[];
  for(const order of [cfg.values, cfg.values.slice().reverse()]){
    const rows=[]; let base=null;
    for(const v of order){
      setv(DEF); base=snap();                      // 每次先回默认（一跳的起点必须相同）
      const vals=DEF.slice(); vals[k]=v; setv(vals);
      const cur=snap();
      const on=[], off=[];
      for(let j=0;j<nd;j++){
        if(cur[j]>0.5 && base[j]<=0.5) on.push(ids[j]);
        if(cur[j]<=0.5 && base[j]>0.5) off.push(ids[j]);
      }
      let lit=0; for(let j=0;j<nd;j++) if(cur[j]>0.5) lit++;
      rows.push({v, lit, nOn:on.length, nOff:off.length,
                 on:cfg.focus? on.filter(x=>cfg.focus.some(f=>x===f)) : on.slice(0,20),
                 off:cfg.focus? off.filter(x=>cfg.focus.some(f=>x===f)) : off.slice(0,20),
                 focus:cfg.focus.map(n=>{ const j=ids.indexOf(n); return j<0? null : +cur[j].toFixed(2); })});
    }
    passes.push(rows);
  }
  const same=JSON.stringify(passes[0].map(r=>[r.lit,r.nOn,r.nOff]))
            ===JSON.stringify(passes[1].slice().reverse().map(r=>[r.lit,r.nOn,r.nOff]));
  window.__hideSet=null; try{ window.__m.autoUpdate=true; }catch(e){}
  try{ window.__app.ticker.start(); }catch(e){}
  return JSON.stringify({param:cfg.param, idx:k, values:cfg.values, focus:cfg.focus,
                         drawables:nd, passes, forwardBackwardAgree:same});
})"""


# ---------------------------------------------------------------- ⑰ 冷态全量台账：把 ⑯ 的形状铺到整批参数，并做阈值二分
# 为什么必须新做一条而不是复用 ⑤：⑤ 的台账是**逐档爬**出来的（0→0.1→0.2…），⑬/⑯ 已证它带不可逆滞回，
# 于是 ⑤ 的「翻转点」只是 11 点网格的中点、不是绑定阈值（§123 追加-XIV）。这一臂的形状是：
#   每一次读数都先把**全部参数写回 moc3 默认**、再把目标参数**一跳**到位（绝不分档爬）；
#   每次探测前先读一次「复位后的状态」——它若还不等于冷基线，就是**滞回污染的直接计数**（`drift`），
#   这条臂因此自带"这一格能不能发布"的判据，而不是靠事后两遍对拍才发现；
#   阈值不再取网格中点：对每个「相邻网格签名不同」的区间做**二分**（从两侧各自收敛），
#   落到 eps 以内记成真阈值；两侧收敛到同一个第三种签名 ⇒ 标 `tertiary`（区间里还有第三个状态）。
# 发布口径（在 Python 侧的 `--coldmerge` 里判）：**正序与倒序两次独立页面会话逐格签名一致、且 drift 恒 0** 才收。
JS_COLDMAPALL = r"""(async (cfg) => {
  const im=window.__m.internalModel, core=im.coreModel, M=core._model;
  const P=M.parameters, D=M.drawables;
  window.__cap=null; window.__wset=null; window.__hideSet=null;
  window.__ambOff=true; window.__snapOff=true;
  try{ window.__app.ticker.stop(); }catch(e){}
  try{ im.autoUpdate=false; }catch(e){}
  try{ im.motionManager.stopAllMotions(); }catch(e){}
  const nd=D.count, DEF=Array.from(P.defaultValues);
  const setv=(vals)=>{ for(let i=0;i<P.count;i++) if(Math.abs(P.values[i]-vals[i])>1e-9) P.values[i]=vals[i];
                       core.update(); };
  const snap=()=>{ const a=new Float32Array(nd); a.set(D.opacities); return a; };
  if(!window.__cold0){ setv(DEF.slice()); window.__cold0=snap(); }
  const cold0=window.__cold0, EPS=5e-4, CAP=cfg.cap||240;
  const litOf=(a)=>{ let c=0; for(let j=0;j<nd;j++) if(a[j]>0.5) c++; return c; };
  const chgOf=(a)=>{ const s=[]; let h=2166136261>>>0;
    for(let j=0;j<nd;j++) if(Math.abs(a[j]-cold0[j])>EPS){
      const o=+a[j].toFixed(3); s.push([j,o]);
      h=(h^j)>>>0; h=Math.imul(h,16777619)>>>0; h=(h^o)>>>0; h=Math.imul(h,16777619)>>>0; }
    return {s:s.slice(0,CAP), n:s.length, h:h}; };
  let updates=0;
  const probe=(k,v)=>{ setv(DEF.slice()); updates++;
    const drift=chgOf(snap()).n;                     // 复位后仍不等于冷基线 = 滞回污染
    const d=DEF.slice(); d[k]=v; setv(d); updates++;
    const a=snap(); const c=chgOf(a);
    setv(DEF.slice()); updates++;
    return {v:+v.toFixed(6), lit:litOf(a), chg:c, drift}; };
  const results=[];
  for(const pname of cfg.params){
    const k=P.ids.indexOf(pname);
    if(k<0){ results.push({param:pname, fail:'不在 moc3'}); continue; }
    const mn=P.minimumValues[k], mx=P.maximumValues[k];
    if(!(mx>mn)){ results.push({param:pname, fail:'量程退化'}); continue; }
    const n=cfg.nstep, order=[]; for(let q=0;q<=n;q++) order.push(q);
    if(cfg.reverse) order.reverse();
    const byq={}, seq=[];
    for(const q of order){ const v=mn+(mx-mn)*q/n; const r=probe(k,v); r.q=q;
                           byq[q]=r; seq.push(q); }
    const bounds=[];
    const epsMin=Math.max(cfg.epsAbs||(mx-mn)/1024, (mx-mn)/Math.pow(2,cfg.maxBis));
    // 二分到 eps；区间中点若落进**第三种签名**（本项目实测：0.05 那档是「半透明手」，既不是 A 也不是 B），
    // 就把它当成一条真边界、左右两半各自再收 —— 不是停下来报错，因为「中间那个状态」正是闪烁的本体。
    // 但递归会炸成本 ⇒ 每个参数一个总探针预算，用完就把当区间原样记下（`budget:true`，不发布该阈值）。
    let budget=cfg.maxProbes||90;
    const bisect=(lo,hi,slo,shi,depth)=>{
      let a=lo, ha=slo, b=hi, hb=shi, it=0;
      while(b-a>epsMin && it<cfg.maxBis && budget>0){ it++; budget--;
        const mid=0.5*(a+b), hm=probe(k,mid).chg.h;
        if(hm===ha){ a=mid; ha=hm; }
        else if(hm===hb){ b=mid; hb=hm; }
        else {
          bounds.push({lo:+mid.toFixed(6), hi:+mid.toFixed(6), eps:0, probes:it,
                       tertiary:[+mid.toFixed(6), hm]});
          if(depth<3){ bisect(lo,mid,ha,hm,depth+1); bisect(mid,hi,hm,hb,depth+1); }
          return;
        }
      }
      bounds.push({lo:a, hi:b, eps:+epsMin.toFixed(6), probes:it, tertiary:null,
                   budget:(b-a>epsMin)});
    };
    for(let q=0;q<n;q++){
      const A=byq[q], B=byq[q+1];
      if(!A||!B||A.chg.h===B.chg.h) continue;
      bisect(A.v, B.v, A.chg.h, B.chg.h, 0);
    }
    const grid=[]; for(let q=0;q<=n;q++){ const r=byq[q];
      grid.push({v:r.v, lit:r.lit, drift:r.drift, nChg:r.chg.n, chg:r.chg.s, h:r.chg.h}); }
    results.push({param:pname, idx:k, mn, mx, dflt:+P.defaultValues[k].toFixed(4),
                  maxDrift:Math.max.apply(null, grid.map(g=>g.drift)), grid, bounds});
  }
  window.__hideSet=null; window.__ambOff=false;
  try{ im.autoUpdate=true; }catch(e){}
  try{ window.__app.ticker.start(); }catch(e){}
  return JSON.stringify({cold0lit:litOf(cold0), cold0:Array.from(cold0, x=>+x.toFixed(3)),
                         drawables:nd, names:window.__drawableIds, params:results.length,
                         updates, reverse:!!cfg.reverse, nstep:cfg.nstep, results});
})"""


# ---------------------------------------------------------------- ⑱ 棘轮能不能复位（⑰ 的代价判死之前必须先答这一题）
# 为什么必须先答：⑰ 第一次实跑就看见 `drift` 与 `nChg` **只增不减**、还跨参数往下带
#   （Param25 0→29 ⇒ Param27 29→53 ⇒ Param52 恒 53）。若这个累加**没有任何复位手段**，
#   那"冷态台账"在一页里只成立于第一次探测 ⇒ 99 参数 × 11 点 = 一千多次换页，全库批量当场判死；
#   反之只要有一种复位能把缓冲打回冷基线，⑰ 就能照原方案跑。所以这一臂只问一件事：**复位手段有没有、哪种有**。
# 一趟之内做完（每步都读全模型签名，签名 = 与冷基线差 >5e-4 的片号与读数）：
#   P1 干净单读：本会话**第一次**探测就取目标值 → 这份签名当作"该值的冷读数"基准（之后所有对比都对着它）
#   P2 故意污染：把同一参数打到高值再回默认
#   P3 复位候选逐个试，每个都读"复位后是否等于冷基线"：
#      A 直写 `drawables.opacities` 回冷基线（不 update）
#      B 直写回冷基线 **再** core.update()（看 update 会不会把它重新加回去 = 累加式的直接证据）
#      C 只写全参数回 moc3 默认 + update（⑰ 现在用的那种，已知不管用）
#      D 走框架 setter `core.setParameterValue` 逐个写默认 + update
#      E 写 part 缓冲回默认（若 part 也参与这条链）
#   P4 复测：在每种"看起来复位成功"的状态下再探一次同一目标值，签名须等于 P1 才算函数值可复现
#   另：把 core/model 上真实存在的 reset 类 API 名列出来（不猜着调，只报告有什么）
JS_LATCHRESET = r"""(async (cfg) => {
  const im=window.__m.internalModel, core=im.coreModel, M=core._model;
  const P=M.parameters, D=M.drawables, PT=M.parts;
  window.__cap=null; window.__wset=null; window.__hideSet=null;
  window.__ambOff=true; window.__snapOff=true;
  try{ window.__app.ticker.stop(); }catch(e){}
  try{ im.autoUpdate=false; }catch(e){}
  try{ im.motionManager.stopAllMotions(); }catch(e){}
  const nd=D.count, DEF=Array.from(P.defaultValues);
  const upd=()=>{ core.update(); };
  const setP=(vals)=>{ for(let i=0;i<P.count;i++) if(Math.abs(P.values[i]-vals[i])>1e-9) P.values[i]=vals[i]; };
  const snap=()=>{ const a=new Float32Array(nd); a.set(D.opacities); return a; };
  setP(DEF.slice()); upd();
  const cold0=snap();
  const EPS=5e-4;
  const sig=(a)=>{ const s=[]; for(let j=0;j<nd;j++) if(Math.abs(a[j]-cold0[j])>EPS) s.push(j+':'+a[j].toFixed(3)); return s; };
  const lit=(a)=>{ let c=0; for(let j=0;j<nd;j++) if(a[j]>0.5) c++; return c; };
  const k=P.ids.indexOf(cfg.param);
  if(k<0) return JSON.stringify({fail:'参数不在 moc3'});
  const mn=P.minimumValues[k], mx=P.maximumValues[k];
  const at=(v)=>{ setP(DEF.slice()); P.values[k]=v; upd(); return snap(); };
  const steps=[];
  const CAPS=cfg.cap||40;                       // ⑲ 要整份名单，默认 40 是给人看的
  const rec=(tag,a,extra)=>{ steps.push(Object.assign({tag, lit:lit(a), nSig:sig(a).length,
                                                       sig:sig(a).slice(0,CAPS)}, extra||{})); };

  // —— mode='seq'：协议 A/B。同一批值、同一条复位路径，只换「一次探测打几拍 core.update()」：
  //    two = 先写全默认打一拍、再写目标值打一拍（⑰ 现在的做法）
  //    one = 直接把参数数组写成「全默认 + 目标值」，只打一拍（⑱ 现在的做法）
  //    每步之后都复位并读"还差几片" ⇒ 若 one 全程 0 而 two 递增，棘轮就是**多打一拍造出来的**，台账可救；
  //    若两者一样递增，棘轮与协议无关 ⇒ 真锁存，一页只有第一次探测可信。
  if(cfg.mode==='seq'){
    const seq=(cfg.seq&&cfg.seq.length)?cfg.seq.slice(0,24):[0,0.05,0.1,0.2,0.5,1.0];
    const proto=cfg.protocol==='one'?'one':'two';
    for(const sv of seq){
      const v=Math.max(mn,Math.min(mx, sv));
      let a;
      if(proto==='two'){ setP(DEF.slice()); upd(); P.values[k]=v; upd(); a=snap(); }
      else { setP(DEF.slice()); P.values[k]=v; upd(); a=snap(); }
      const s1=sig(a);
      setP(DEF.slice()); upd();
      const s2=sig(snap());
      // 复位后再连打 N 拍：若残留随拍数消失，那是**慢收敛**不是锁存；恒在才叫锁存
      for(let z=0;z<(cfg.pump||0);z++) upd();
      const s3=sig(snap());
      rec('probe v=' + v, a, {value:v});
      rec('reset v=' + v, snap(), {afterOf:v, proto:proto, pump:cfg.pump||0});
      steps[steps.length-1].sig=s2.slice(0,CAPS);
      steps[steps.length-1].nOn=s2.length;
      steps[steps.length-1].nSig=s2.length;
      steps[steps.length-1].afterPump=s3.length;
      steps[steps.length-1].pumpSig=s3.slice(0,CAPS);
      steps[steps.length-2].nOn=s1.length;
    }
    window.__hideSet=null; window.__ambOff=false;
    try{ im.autoUpdate=true; }catch(e){}
    try{ window.__app.ticker.start(); }catch(e){}
    return JSON.stringify({mode:'seq', protocol:proto, param:cfg.param, mn, mx,
                           cold0lit:lit(cold0), names:window.__drawableIds, steps, seq});
  }

  rec('P1 本会话第一次探测（当作该值的冷读数）', at(cfg.target), {v:cfg.target});
  const clean=sig(at(cfg.target)).join('|');        // 同值第二读：已经带上了 P1 之后回默认的痕迹
  rec('P1b 回默认后再读同一值（第二读）', at(cfg.target), {secondOf:clean});
  rec('P1c 只回默认、不探值', (()=>{ setP(DEF.slice()); upd(); return snap(); })());
  rec('P2 污染：打到 cfg.hot 再回默认', (()=>{ at(cfg.hot); setP(DEF.slice()); upd(); return snap(); })());
  const afterHot=sig(snap()).length;
  rec('R-A 直写片缓冲回冷基线（不 update）', (()=>{ for(let j=0;j<nd;j++) D.opacities[j]=cold0[j]; return snap(); })(),
      {restoresTo:cold0.length});
  rec('R-B 直写片缓冲回冷基线 + update', (()=>{ for(let j=0;j<nd;j++) D.opacities[j]=cold0[j]; upd(); return snap(); })());
  rec('R-C 只写全参数回默认 + update', (()=>{ setP(DEF.slice()); upd(); return snap(); })());
  rec('R-D 框架 setter 逐个写默认 + update', (()=>{ for(let i=0;i<P.count;i++){ try{ core.setParameterValue(i, DEF[i]); }catch(e){ return snap(); } } upd(); return snap(); })());
  rec('R-E 写 part 缓冲回默认 + update', (()=>{ try{ for(let i=0;i<PT.count;i++) PT.opacities[i]=1; }catch(e){} upd(); return snap(); })());
  rec('R-F A+B+C 组合', (()=>{ setP(DEF.slice()); for(let j=0;j<nd;j++) D.opacities[j]=cold0[j]; upd(); return snap(); })());
  const okReset=[];
  for(const s of steps){ if(s.tag.startsWith('R-') && s.nSig===0) okReset.push(s.tag); }
  const p4=[];
  for(const t of okReset){                                  // 复位成功后再探同一值，签名必须等于 P1
    const a=at(cfg.target); p4.push({after:t, sameAsP1: sig(a).join('|')===clean, lit:lit(a), nSig:sig(a).length});
    setP(DEF.slice()); for(let j=0;j<nd;j++) D.opacities[j]=cold0[j]; upd();
  }
  const api=(()=>{ const o={};
    const dump=(n,obj)=>{ try{ o[n]=Object.getOwnPropertyNames(obj||{}).filter(x=>/reset|clear|init|default/i.test(x)); }catch(e){ o[n]=['<读不到>']; } };
    dump('coreModel', Object.getPrototypeOf(core)); dump('model', Object.getPrototypeOf(M));
    dump('coreCtor', window.CubismCore&&window.CubismCore.Model&&window.CubismCore.Model.prototype);
    o.coreStatic = window.CubismCore? Object.getOwnPropertyNames(window.CubismCore).filter(x=>/reset|clean|delete/i.test(x)) : null;
    return o; })();
  window.__hideSet=null; window.__ambOff=false;
  try{ im.autoUpdate=true; }catch(e){}
  try{ window.__app.ticker.start(); }catch(e){}
  return JSON.stringify({param:cfg.param, idx:k, target:cfg.target, hot:cfg.hot, cold0lit:lit(cold0),
                         afterHotNSig:afterHot, steps, okReset, p4, api});
})"""


# ---------------------------------------------------------------- ㉑ 预路过（补丁 ⑧）的 A/B：切换首帧"该亮的那几组手"亮了几片
# 为什么要它：⑲ 量出锁存律之后，修法 (a) 是"载入后把开关参数的键全路过一遍"。
#   它到底改变了什么，只能按**组**量：冷态律给出六组（0.1→331-335、0.2→325-330、0.3→355/379、
#   0.4→356-360、0.5→364/380/381/593/594、0.6→365-370）+ 可逆的 A 组手（36/42/43/44/51）。
#   判据（两条都要过）：① **预路过开** 时，idle 稳定态下这六组**至少各亮一片**（关 ⇒ 只有被跳不到的那些不亮）；
#   ② 切到 `home` 之后**不再出现"整组从亮变灭"**（闪烁的指纹）。
# ⚠️ 补丁在**表 fetch 完成时**就跑，所以 A/B 必须在页面加载**之前**关掉开关 —— 用
#   CDP `Page.addScriptToEvaluateOnNewDocument` 注入 `window.__preRoll=false`，不能加载完再设。
JS_PREROLL = r"""(async (cfg) => {
  const im=window.__m.internalModel, core=im.coreModel, M=core._model, D=M.drawables;
  const ids=Array.from(D.ids);
  const grp=(names)=>names.map(n=>{ const j=ids.indexOf(n); return j<0? null : +D.opacities[j].toFixed(2); });
  const G={A:['ArtMesh36','ArtMesh42','ArtMesh43','ArtMesh44','ArtMesh51'],
           g01:['ArtMesh331','ArtMesh332','ArtMesh333','ArtMesh334','ArtMesh335'],
           g02:['ArtMesh325','ArtMesh326','ArtMesh327','ArtMesh328','ArtMesh329','ArtMesh330'],
           g03:['ArtMesh355','ArtMesh379'],
           g04:['ArtMesh356','ArtMesh357','ArtMesh358','ArtMesh359','ArtMesh360'],
           g05:['ArtMesh364','ArtMesh380','ArtMesh381','ArtMesh593','ArtMesh594'],
           g06:['ArtMesh365','ArtMesh366','ArtMesh367','ArtMesh368','ArtMesh369','ArtMesh370']};
  const shot=()=>{ let lit=0; for(let j=0;j<D.count;j++) if(D.opacities[j]>0.5) lit++;
    const o={lit}; for(const k in G){ const v=grp(G[k]); o[k]=v.filter(x=>x!==null);
      o[k+'_on']=v.filter(x=>x!==null&&x>0.5).length; } return o; };
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  const dbg=(()=>{ try{ return {pre:window.__preRollDbg?window.__preRollDbg():null,
                                last:window.__preRollLast||null, err:window.__preRollErr||null,
                                snap:window.__snapDbg?window.__snapDbg():null}; }catch(e){ return {err:String(e)}; } })();
  const seq=[];
  /* ⚠️ 这一档是专门用来分「锁存是真的」还是「⑲ 那套冻结协议造出来的假象」：
     预路过跑完**当拍**就读（中间一帧动作都没有），再等 1 秒动作后读一次。
     当拍亮、1 秒后灭 ⇒ 真实播放管线每帧重算显隐、根本不存在"点亮就不灭"，
     ⑲/追加-XV 那条"锁存律"要按**仪器假象**更正；当拍就不亮 ⇒ 预路过这条路本身没走通（写的不是同一条通道）。*/
  if(cfg.prerun && window.__preRoll!==false && typeof window.__preRollRun==='function'){
    let h=null; try{ h=window.__preRollRun(); }catch(e){}
    seq.push(Object.assign({tag:"预路过跑完·当拍（未经任何动作帧）", clip:(()=>{ try{ return im.motionManager.state.currentGroup; }catch(e){ return null; } })()}, shot()));
    for(let k=0;k<60;k++){ await t(16); }
    seq.push(Object.assign({tag:"再跑 1 秒动作之后", clip:(()=>{ try{ return im.motionManager.state.currentGroup; }catch(e){ return null; } })()}, shot()));
  }
  for(const st of cfg.steps){
    if(st.clip){ try{ im.motionManager.startMotion(st.clip,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){} }
    const nfr=Math.max(1,Math.round(st.wait*1000/16));
    for(let k=0;k<nfr;k++){ await t(16); }
    seq.push(Object.assign({tag:st.tag, clip:(()=>{ try{ return im.motionManager.state.currentGroup; }catch(e){ return null; } })()},
                            shot()));
  }
  return JSON.stringify({preroll:(window.__preRoll!==false), dbg, seq,
                         groups:Object.keys(G).map(k=>[k,G[k].length])});
})"""


# ---------------------------------------------------------------- ㉒ 手部并集**逐拍**（只记变化与全灭，不受截图速度限制）
#   为什么再来一趟：⑩/⑳ 的采样被 swiftshader 的渲染拖到 ~5 拍/秒（200ms 一拍），
#   「手闪了一下」这种 1~3 拍（几十毫秒）的窗口**在 200ms 网格上根本量不到** —— 上一趟
#   `--trace` 跑满 20s 只拿到 200 拍，且并集从头到尾没为 0 过，这个"没为 0"**不能当判死证据**。
#   本臂改成：① 只记「手部名单里发生翻转的片」与「并集为 0 的拍」⇒ 高频也不会爆内存；
#   ② 时钟原点是 `startMotion` 那一刻（不是页面加载、也不是帧号）；
#   ③ 先量**实测拍率**（upd/秒）并随结果一起发布 —— 拍率不到 30/s 就明确说"仍测不到"，不许拿它判死。
JS_HANDDARK = r"""(async (cfg) => {
  const m=window.__m, im=m.internalModel, core=im.coreModel, CP=Object.getPrototypeOf(core);
  const M=core._model, D=M.drawables, P=M.parameters;
  const ids=Array.from(D.ids);
  const hand=cfg.names.map(n=>ids.indexOf(n)).filter(j=>j>=0);
  const handNames=hand.map(j=>ids[j]);
  const watch=cfg.params.map(n=>(window.__pid||[]).indexOf(n)).filter(j=>j>=0);
  const watchNames=watch.map(j=>(window.__pid||[])[j]);
  /* 「面积=0」有两种，含义完全不同，必须分开：
       ① vertexCount 本身就是 0 ⇒ moc3 里这块美术**没有几何**，opacity 再怎么改都不会有一个像素；
       ② 有顶点但全等 ⇒ 被绑定缩放压成了一个点（状态相关，跟着姿态变）。
     上一轮 ⑲ 的"锁存律/键位分组"是**只读 opacity** 分出来的组，若组里混着①，那些结论
     是在给看不见的美术记账 —— 这正好是"改了十几轮、用户还是说手没了"能同时成立的那扇门。 */
  const VC=M.drawables.vertexCounts||[];
  const vshot=()=>hand.map((j,q)=>{ const p=D.vertexPositions[j];
    return [handNames[q], (VC.length? +VC[j] : null), p.length,
            p.length? +p[0].toFixed(3):null, p.length? +p[1].toFixed(3):null]; });
  const v0count=(()=>{ let z=0; for(let i=0;i<D.count;i++) if(VC.length && +VC[i]===0) z++;
                       return z; })();
  if(!window.__hdHook){
    const base=CP.update;
    CP.update=function(){ const r=base.apply(this,arguments); const H=window.__hd;
      if(!H) return r;
      const MM=this._model, O=MM.drawables.opacities, n=MM.drawables.count;
      const VP=MM.drawables.vertexPositions;
      const t=(performance.now()-H.t0)/1000;
      /* 「亮」= opacity>0.5，「看得见」= 亮 **且** 顶点没塌成一个点。
         为什么要加第二栏（本轮的新发现）：台账里 g01~g06 那 29 片手的包围盒**全是 0**，
         也就是说它们亮着却在画面上不存在 —— 十几轮只读 opacity 的判据把这类"亮着的空壳"
         当成"手还在"，所以每一轮的"并集没为 0"都是虚的。Live2D 藏一套美术有两条通道
         （透明度 / 绑定缩放归零 ⇒ 顶点坍缩），只读前者必然漏后者。 */
      let lit=0, vis=H.visCache;
      H.n=(H.n||0)+1;
      if(H.n % (cfg.every||4) === 1){        // 全模型逐顶点扫描太贵（会把拍率从 14/s 拖到 9/s），按 --hdevery 抽稀
        vis=0;
        for(let i=0;i<n;i++){ if(O[i]<=0.5) continue; lit++;
          const p=VP[i]; let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
          for(let k=0;k+1<p.length;k+=2){ const a=p[k],b=p[k+1];
            if(a<x0)x0=a; else if(a>x1)x1=a; if(b<y0)y0=b; else if(b>y1)y1=b; }
          if((x1-x0)*(y1-y0) > H.eps) vis++; }
        H.visCache=vis; H.litCache=lit;
      } else { lit=H.litCache||0; }
      let hl=0, hv=0, ha=0;
      const st=new Array(hand.length);
      for(let q=0;q<hand.length;q++){ st[q]=O[hand[q]]>0.5?1:0;
        if(st[q]){ hl++; const p=VP[hand[q]]; let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
          for(let k=0;k+1<p.length;k+=2){ const a=p[k],b=p[k+1];
            if(a<x0)x0=a; else if(a>x1)x1=a; if(b<y0)y0=b; else if(b>y1)y1=b; }
          const ar=(x1-x0)*(y1-y0);
          if(ar > H.eps){ hv++; ha+=ar; H.handArea[q]=+ar.toFixed(4); }
          else H.handArea[q]=0; }
        else H.handArea[q]=0; }
      H.rows.push([+t.toFixed(3),lit,vis,hl,hv,+ha.toFixed(4),H.handArea.slice(),
                   (()=>{ try{ return im.motionManager.state.currentGroup||''; }catch(e){ return ''; } })()]);
      if(vis<H.minVis) H.minVis=vis; if(vis>H.maxVis) H.maxVis=vis;
      if(hv<H.minHv) H.minHv=hv; if(hv>H.maxHv2) H.maxHv2=hv;
      H.upd++;
      if(hl<H.minHl) H.minHl=hl; if(hl>H.maxHl) H.maxHl=hl;
      if(H.lastSt){ const add=[],del=[],dim=[];
        for(let q=0;q<hand.length;q++){ if(st[q]!==H.lastSt[q]){ if(st[q]) add.push(handNames[q]); else del.push(handNames[q]); }
          else if(st[q] && +(O[hand[q]].toFixed(2))!==H.lastOp[q]) dim.push([handNames[q],H.lastOp[q],+O[hand[q]].toFixed(2)]); }
        if(add.length||del.length)
          H.changes.push([+t.toFixed(3),lit,hl,add,del, watch.length? watch.map(j=>+P.values[j].toFixed(3)):null]);
        if(dim.length&&H.dimming.length<200) H.dimming.push([+t.toFixed(3),hl,dim]); }
      H.lastSt=st; H.lastOp=hand.map(j=>+O[j].toFixed(2));
      if(hl===0){ if(H.winStart===null) H.winStart=+t.toFixed(3);
                  if(H.zero.length<400) H.zero.push([+t.toFixed(3),lit]); }
      else if(H.winStart!==null){ if(H.windows.length<200) H.windows.push([H.winStart,+t.toFixed(3)]); H.winStart=null; }
      /* 第二套窗口判据：亮片数没问题、但**有面积的手**为 0 —— 这才是"画面上手没了"。 */
      if(hv===0){ if(H.vwinStart===null) H.vwinStart=+t.toFixed(3); }
      else if(H.vwinStart!==null){ if(H.vwindows.length<200) H.vwindows.push([H.vwinStart,+t.toFixed(3)]); H.vwinStart=null; }
      return r; };
    CP.__hdHook=1; window.__hdHook=1;
  }
  window.__hd={t0:performance.now(), upd:0, changes:[], zero:[], windows:[], dimming:[], rows:[],
               winStart:null, vwinStart:null, vwindows:[], lastSt:null, lastOp:[],
               minHl:999, maxHl:0, minVis:1e9, maxVis:0, minHv:999, maxHv2:0,
               eps:(cfg.eps!==undefined? cfg.eps:1e-4), visCache:0, litCache:0, n:0,
               handArea:new Array(hand.length)};
  if(cfg.small){ try{ window.__app.renderer.resize(cfg.w||360, cfg.h||260); }catch(e){} }
  /* ⚠️ 默认走**页面自己的入口**（下拉选 + 点「重播」），不是直接调 motionManager。
     理由（AGENTS「验证脚本不得绕过被测入口」+ 本轮的关键发现）：`play()` 除了 startMotion 还会
     `played.add(g)` —— 那是「残留复位层 restTick」唯一的装填条件。十几轮探针全部直接调
     startMotion ⇒ `played` 永远为空 ⇒ 复位层从来没被 armed 过，之前"关/开复位层都一样"的 A/B
     等于两台都关着做。用户报的"手消失"若落在回落 idle 那 700ms 渐变里，旧仪器**结构上看不见**。 */
  window.__uiFail=null;
  if(cfg.ui){ const s=document.getElementById('l2Motion'), b=document.getElementById('l2Replay');
    if(s&&b){ s.value=cfg.clip; s.dispatchEvent(new Event('change')); b.click(); }
    else window.__uiFail='页面上找不到 #l2Motion / #l2Replay'; }
  else { try{ im.motionManager.startMotion(cfg.clip,0,PIXI.live2d.MotionPriority.FORCE); }catch(e){} }
  window.__hd.t0=performance.now();                 // 时钟原点 = 切换那一刻（不是页面加载）
  /* 定点抓拍走 `renderer.extract`（不是 CDP 截图）：CDP 那张一次要 0.8~1.2s，模型跟着停摆，
     抓回来的"第几秒"根本不是模型的第几秒（§123 追加-XIX 那个 7~34 倍时钟错就是这么来的）。
     extract 在页面里同步跑，几十毫秒级，拍完立刻把**当时的逐拍读数**一起存下来 ⇒
     每张图都自带它的状态签名，事后不必信时钟。 */
  window.__shots=[]; const shots=(cfg.shots||[]).slice().sort((a,b)=>a-b); let si=0;
  /* 场景快照：判"角色跑哪去了"到底是**容器变换**（画廊的 fit/缩放/平移）还是**参数**（模型自己的
     顶点动了）。两者的修法完全不同，所以每拍都同时记 pixi 的 transform 与模型空间可见包围盒。
     顺带把补丁 ⑤ 的回绕名单 `__phaseSet` 与"离默认值最远"的参数一起打出来 —— §123 里
     "一律回绕会让右前臂从 -59° 瞬跳到 +1°，用户症状是选 home 时手会消失"这条线索从没被关过。 */
  const snapAt=(cfg.snapAt||[]).slice().sort((a,b)=>a-b); let ki=0; const snaps=[];
  const takeSnap=(tt)=>{ const o={t:+tt.toFixed(3)};
    try{ o.g=im.motionManager.state.currentGroup||''; }catch(e){ o.g='?'; }
    try{ const s=m.scale,p=m.position; o.tr=[+s.x.toFixed(4),+s.y.toFixed(4),+p.x.toFixed(1),+p.y.toFixed(1),+((m.rotation||0)).toFixed(4)]; }catch(e){ o.tr=null; }
    try{ let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
      for(let i=0;i<D.count;i++){ if(D.opacities[i]<=0.5) continue; const q=D.vertexPositions[i];
        for(let k=0;k+1<q.length;k+=2){ const a=q[k],b=q[k+1]; if(a<x0)x0=a; if(a>x1)x1=a; if(b<y0)y0=b; if(b>y1)y1=b; } }
      o.bb=[+x0.toFixed(2),+y0.toFixed(2),+x1.toFixed(2),+y1.toFixed(2)]; }catch(e){ o.bb=null; }
    try{ o.phase=[...(core.__phaseSet||[])].map(j=>window.__pid[j]).filter(Boolean); }catch(e){ o.phase='n/a'; }
    try{ const far=[];
      for(let j=0;j<P.count;j++){ const sp=P.maximumValues[j]-P.minimumValues[j]; if(!(sp>0)) continue;
        const dev=Math.abs(P.values[j]-P.defaultValues[j])/sp;
        if(dev>0.3) far.push([window.__pid[j],+dev.toFixed(2),+P.values[j].toFixed(2),
                              +P.defaultValues[j].toFixed(2),+P.minimumValues[j].toFixed(1),+P.maximumValues[j].toFixed(1)]); }
      far.sort((a,b)=>b[1]-a[1]); o.far=far.slice(0,14); }catch(e){ o.far='n/a'; }
    o.row=(window.__hd? window.__hd.rows.slice(-1)[0]||[] : []).slice(0,6);
    return o; };
  let unphased=null;
  const until=performance.now()+cfg.secs*1000;
  while(performance.now()<until){
    const tt=(performance.now()-window.__hd.t0)/1000;
    if(si<shots.length && tt>=shots[si]){
      const want=shots[si]; si++;
      try{ const b64=await window.__app.renderer.extract.base64(window.__app.stage,"image/png");
        const rec={t:+tt.toFixed(3), want, row:(window.__hd.rows.slice(-1)[0]||[]).slice(0,6), b64};
        /* 「手到底在不在画面里」只能这样量：把**除手部片以外**的所有 drawable 透明度打 0
           （复用钩子已有的 __hideSet，它打在 core.update 之后 ⇒ 渲染读的就是这份缓冲），
           再抓一张带 alpha 的 PNG。画布本身 backgroundAlpha=0，所以剩下的不透明像素
           **就是手在屏幕上的实际落点** —— 越界与否从此不必靠肉眼猜。 */
        if((cfg.onlyAt||[]).some(x=>Math.abs(x-want)<0.6)){
          const keep=new Set(hand), other=[];
          for(let i=0;i<D.count;i++) if(!keep.has(i)) other.push(i);
          window.__hideSet=new Set(other);
          await new Promise(r=>setTimeout(r,140));
          try{ rec.handsB64=await window.__app.renderer.extract.base64(window.__app.stage,"image/png"); }catch(e){ rec.handsErr=String(e).slice(0,100); }
          window.__hideSet=null;
          await new Promise(r=>setTimeout(r,140));
        }
        /* ⚠️ 名单本身必须先验，否则上面量到的"手不在画面里"可能只是"我叫错了名字"。
           做法：同一时刻**逐组只 hide 这一组**，抓 7 张图 —— 画面上哪一块没了，
           这组才真的是那块美术。这是本臂的阳性对照。 */
        if(cfg.grpAt!==undefined && Math.abs(cfg.grpAt-want)<0.6 && cfg.groups){
          /* 必须**冻住 ticker** 再逐组 hide：两张图之间只要动画走过 0.3s，差异就被位移吃掉，
             实测七组的差异包围盒一模一样（= 全画面位移），对照等于没做。 */
          try{ window.__app.ticker.stop(); }catch(e){}
          await new Promise(r=>setTimeout(r,80));
          rec.grp=[];
          try{ rec.grpBase=await window.__app.renderer.extract.base64(window.__app.stage,"image/png"); }catch(e){}
          for(let gi=0; gi<cfg.groups.length; gi++){
            const idx=(cfg.groups[gi]||[]).map(n=>ids.indexOf(n)).filter(j=>j>=0);
            window.__hideSet=new Set(idx);
            await new Promise(r=>setTimeout(r,60));
            try{ rec.grp.push({name:cfg.grpNames[gi], n:idx.length,
                               b64:await window.__app.renderer.extract.base64(window.__app.stage,"image/png")}); }
            catch(e){ rec.grp.push({name:cfg.grpNames[gi], n:idx.length, err:String(e).slice(0,90)}); }
            window.__hideSet=null;
            await new Promise(r=>setTimeout(r,60));
          }
          try{ window.__app.ticker.start(); }catch(e){}
        }
        window.__shots.push(rec);
      }catch(e){ window.__shots.push({t:+tt.toFixed(3), want, err:String(e).slice(0,120)}); }
    }
    if(ki<snapAt.length && tt>=snapAt[ki]){ const w=snapAt[ki]; ki++; snaps.push(takeSnap(tt)); }
    if(cfg.unphaseAt && unphased===null && tt>=cfg.unphaseAt){
      try{ const S=core.__phaseSet; unphased={had:S?S.size:-1};
        if(S) S.clear(); unphased.at=+tt.toFixed(3); }catch(e){ unphased={err:String(e).slice(0,100)}; }
    }
    await new Promise(r=>setTimeout(r,100));
  }
  const H=window.__hd; window.__hd=null;
  if(H.winStart!==null) H.windows.push([H.winStart,+cfg.secs.toFixed(3)]);
  if(H.vwinStart!==null) H.vwindows.push([H.vwinStart,+cfg.secs.toFixed(3)]);
  return JSON.stringify({clip:cfg.clip, secs:cfg.secs, small:!!cfg.small, eps:H.eps,
    ui:!!cfg.ui, uiFail:window.__uiFail||null, snaps:snaps, unphased:unphased,
    played:(()=>{ try{ return (im.motionManager.state&&im.motionManager.state.currentGroup)||null; }catch(e){ return null; } })(),
    upd:H.upd, updPerSec:+(H.upd/cfg.secs).toFixed(1),
    minHl:H.minHl===999?null:H.minHl, maxHl:H.maxHl, windows:H.windows,
    minVis:H.minVis===1e9?null:H.minVis, maxVis:H.maxVis,
    minHv:H.minHv===999?null:H.minHv, maxHv2:H.maxHv2, vwindows:H.vwindows,
    handCount:hand.length, missing:cfg.names.filter(n=>ids.indexOf(n)<0),
    handNames:handNames, zeroVertexDrawables:v0count, totalDrawables:D.count,
    vcStart:vshot(), vcEnd:vshot(),
    watch:watchNames, changesTotal:H.changes.length, rows:H.rows,
    changes:H.changes.slice(0,400), zero:H.zero.slice(0,60), dimming:H.dimming.slice(0,40)});
})"""


# ---------------------------------------------------------------- ⑬ 台账矛盾判定：同一趟里把「扫 Param25」与「钉 Param25」合进同一次运行、同一套索引
# 为什么要它（§6.37 交接的第一件事）：臂 ⑤ 的显隐台账说「全默认 + Param25=0.5 ⇒ ArtMesh325=1.0」，
# 臂 ⑫ 用**逐位相同**的参数数组直读同一个下标(378) 得 **0**，且三个目标全灭（不是单片偶发）。
# ⑫ 自己报 `nDiff:1` ⇒ 输入侧只差 Param25，所以差异只能来自**参数之外、不随 core.update() 重算的那套输入**，
# 而 Live2D 里只有一个候选：part 透明度。⚠️ 上一轮"部件门已否证"用的是**坏仪器**（臂 ⑪ 那次
# `hasDefaults=False`、每个目标 `part:null`、"非默认部件 0 个"是 `undefined` 参与减法比较的产物），
# 所以部件门从来没被真正测过。这一臂在同一次运行、同一套索引里做四件事：
#   ① 自证 part 缓冲到底可不可读、`core.update()` 会不会把我们写进去的值覆盖掉（part 是输入还是输出）；
#   ② 四档状态对读：全默认 / 全默认+pin / 全默认+pin 且 part 全写 1 / 复刻 ⑤ 的 11 点扫；
#   ③ **写路径粘性判定**：终态参数数组完全相同，只换"到达它的路径"（⑫ 的整数组写 vs ⑤ 的单参数写），
#      两次读数不同 ⇒ 状态里确有第二套输入；相同 ⇒ 矛盾在别处（回到索引/缓冲假设）；
#   ④ 每个目标的 drawable→part 归属链（wasm 视图暴露得出哪条就用哪条，暴露不出就如实报"读不到"）。
# ⚠️ 目标名单必须自带一条阳性对照：台账说 Param25=0.5 时 A 组(ArtMesh36)=0、B 组=1，
#    再放一片"两条 clip 里都恒定亮着"的 ArtMesh364 —— 它若也读 0，说明整模型都被挡，不是这道门。
JS_RECON = r"""(async (cfg) => {
  const im=window.__m.internalModel, core=im.coreModel, mm=im.motionManager;
  const M=core._model, P=M.parameters, D=M.drawables, PT=M.parts;
  // 先清掉别的臂留下的钩子：__hideSet 会在每次 core.update() 之后把指定片写成 0（[] 也是 truthy）
  window.__cap=null; window.__wset=null; window.__hideSet=null;
  const ambWas=window.__ambOff; window.__ambOff=true;
  const snapWas=window.__snapOff; window.__snapOff=true;      // 修法 (b) 那层会写参数，判定期间关掉
  let tkWas=true; try{ tkWas=window.__app.ticker.started!==false; window.__app.ticker.stop(); }catch(e){}
  try{ window.__m.autoUpdate=false; }catch(e){}
  try{ mm.stopAllMotions(); }catch(e){}
  const ti=cfg.meshes.map(n=>D.ids.indexOf(n));
  const miss=cfg.meshes.filter((n,j)=>ti[j]<0);
  if(ti.every(x=>x<0)) return JSON.stringify({fail:'目标都不在模型里', meshes:cfg.meshes});
  const pinIx=cfg.pin.map(pv=>[pv[0], P.ids.indexOf(pv[0]), pv[1]]);
  const rows=[]; const reads=[];
  const tgt=()=>ti.map(j=>j<0? null : +D.opacities[j].toFixed(3));
  const pstats=()=>{ const O=PT.opacities;
    if(!O||!O.length||typeof O[0]!=='number') return {readable:false, type:String(O&&O.constructor&&O.constructor.name)};
    let non1=0, mn=Infinity, mx=-Infinity;
    for(let i=0;i<PT.count;i++){ const v=O[i]; if(Math.abs(v-1)>1e-6) non1++; if(v<mn)mn=v; if(v>mx)mx=v; }
    return {readable:true, n:PT.count, non1, mn:+mn.toFixed(3), mx:+mx.toFixed(3)}; };
  const writeAll=(vals)=>{ let d=0;
    for(let i=0;i<P.count;i++) if(Math.abs(P.values[i]-vals[i])>1e-9){ P.values[i]=vals[i]; d++; }
    core.update(); return d; };
  const DEF=Array.from(P.defaultValues);
  const withPin=(src)=>{ const v=src.slice(); for(const e of pinIx) if(e[1]>=0) v[e[1]]=e[2]; return v; };
  // 归属链：wasm 视图里带 part 字样的数组有哪些
  const partKeys=Object.keys(D).filter(k=>/part/i.test(k));
  const chain=partKeys.length? partKeys.map(k=>({key:k, vals:ti.map(j=>D[k]?D[k][j]:null)})) : null;
  const protoMeth=Object.getOwnPropertyNames(Object.getPrototypeOf(core)).filter(n=>/part/i.test(n));
  const push=(tag,vals)=>{ const d=writeAll(vals);
    rows.push({tag, wrote:d, part:pstats(), op:tgt(),
               pin:(()=>{ const o={}; for(const e of pinIx) o[e[0]]=e[1]<0?null:+P.values[e[1]].toFixed(4); return o; })()}); };

  push('S1 全默认', DEF);
  const coldVec=Array.from(D.opacities);          // 冷态全模型显隐快照（S14 的基准）
  // 目标片的结构属性：core 里唯一带脏标记的通道是**蒙版**，先确认这些片是不是蒙版相关片
  const dkeys=Object.keys(D);
  const pick=(k)=>ti.map(j=>{ const a=D[k]; if(!a) return null;
    const v=a[j]; return (typeof v==='number')? +v.toFixed(3) : v; });
  const attrs=cfg.meshes.map((n,q)=>({name:n, idx:ti[q],
    type:pick('types')[q], blend:pick('blendTypes')[q]!==null?pick('blendTypes')[q]:pick('blendModes')[q],
    maskCounts:pick('maskCounts')[q], maskRef:pick('maskReferenceCounts')[q],
    part:pick('parentPartIndices')[q], tex:pick('textures')[q],
    verts:(D.vertexPositions&&D.vertexPositions[ti[q]])?D.vertexPositions[ti[q]].length/2:null,
    indices:(D.indices&&D.indices[ti[q]])?D.indices[ti[q]].length:null}));
  push('S2 全默认+pin', withPin(DEF));
  // S3：把全部 part 写成 1 再 update —— 同时回答"core 会不会把它覆盖回去"
  { const before=pstats(); const O=PT.opacities;
    if(O&&O.length) for(let i=0;i<PT.count;i++) O[i]=1;
    const mid=pstats(); core.update(); const after=pstats();
    rows.push({tag:'S3 part 全写 1 后', wrote:0, part:after, op:tgt(),
               partProbe:{before, afterWrite:mid, afterUpdate:after, overwritten:after.non1!==0},
               pin:(()=>{ const o={}; for(const e of pinIx) o[e[0]]=e[1]<0?null:+P.values[e[1]].toFixed(4); return o; })()}); }
  // S4：复刻臂 ⑤ 的扫法（先归全默认，再只动这一个参数，逐档扫**该参数自己的量程**）
  //     ⚠️ 第一版把扫点写成 `pin 值 × q/nstep`，等于只扫了 [0, pin]，坐标标签全错 ⇒ 按量程重扫。
  writeAll(DEF); { const s=[]; const e0=pinIx[0];
      for(let q=0;q<=cfg.nstep;q++){
        for(const e of pinIx) if(e[1]>=0)
          P.values[e[1]]=P.minimumValues[e[1]]+(P.maximumValues[e[1]]-P.minimumValues[e[1]])*q/cfg.nstep;
        core.update();
        s.push([+(P.minimumValues[e0[1]]+(P.maximumValues[e0[1]]-P.minimumValues[e0[1]])*q/cfg.nstep).toFixed(3), tgt()]); }
    reads.push({tag:'S4 ⑤ 式按量程扫', s}); }
  // S5/S6：终态参数数组**逐位相同**，只换写路径 —— 这一步才是矛盾的判生死线
  push('S5 ⑫ 式整数组写(同 S2)', withPin(DEF));
  writeAll(DEF); { let d=0; for(const e of pinIx) if(e[1]>=0){ P.values[e[1]]=e[2]; d++; }
    core.update();
    rows.push({tag:'S6 ⑤ 式单参数写', wrote:d, part:pstats(), op:tgt(),
               pin:(()=>{ const o={}; for(const e of pinIx) o[e[0]]=e[1]<0?null:+P.values[e[1]].toFixed(4); return o; })()}); }
  // S7：**逐拍结算**判据 —— S2 与 S5/S6 的输入已证逐位相同、读数却不同，而两者唯一的差别是
  //     S5/S6 之前这个模型已经被 update 过很多拍 ⇒ 假设「有一条 core 在 update 里自己写的参数，
  //     它滞后一拍，而目标片的显隐是 Param25 与它的合取」。这里从零基线**一次跳到 pin**，
  //     每拍除了读目标，还把「我们写进去的值」与「update 之后缓冲里的值」逐位对比 ⇒ 点名谁被改写。
  const diffAfterUpdate=(want)=>{ const out=[];
    for(let i=0;i<P.count;i++){ const v=P.values[i];
      if(Math.abs(v-want[i])>1e-4){ out.push([P.ids[i], +want[i].toFixed(3), +v.toFixed(3)]); } }
    return out; };
  writeAll(DEF); { const seq=[]; const want=withPin(DEF);
    for(const e of pinIx) if(e[1]>=0) P.values[e[1]]=e[2];
    for(let k=0;k<cfg.settle;k++){ core.update();
      seq.push([k+1, tgt(), pstats().non1, diffAfterUpdate(withPin(DEF))]); }
    reads.push({tag:'S7 一次跳到 pin 后逐拍读（第 3 列=update 之后被 core 改写的参数）', s:seq}); }
  // S8：反方向（一次跳回默认）逐拍读 —— 只测上升沿会把"单向滞后"当成对称结论
  writeAll(withPin(DEF)); { const seq=[];
    for(let k=0;k<cfg.settle;k++){
      for(const e of pinIx) if(e[1]>=0) P.values[e[1]]=DEF[e[1]];
      core.update(); seq.push([k+1, tgt(), pstats().non1, diffAfterUpdate(DEF)]); }
    reads.push({tag:'S8 一次跳回默认后逐拍读', s:seq}); }
  // S9：**纯函数判定**（最硬的一条）—— A=全默认 与 B=全默认+pin 交替来回，每拍读目标。
  //     若 325 只取决于参数数组，A 每次都读同一个值、B 也同理；
  //     若同一状态在交替中读出不同值 ⇒ `core.update()` 对显隐**不是**参数的纯函数，
  //     台账与直读的矛盾就不是"谁写错了"，而是这类扫描本身带历史依赖 ⇒ 修法必须换一层。
  //     同时逐位比对第 k 次与第 1 次的参数数组（`arrDrift`），排除"数组其实在漂"这条解释。
  { const seq=[]; let firstA=null, firstB=null, arrDriftA=0, arrDriftB=0;
    for(let k=0;k<cfg.settle;k++){
      writeAll(DEF); const a=Array.from(P.values);
      if(k===0) firstA=a.slice(); else for(let i=0;i<P.count;i++) if(Math.abs(a[i]-firstA[i])>1e-9) arrDriftA++;
      const ra=tgt();
      writeAll(withPin(DEF)); const b=Array.from(P.values);
      if(k===0) firstB=b.slice(); else for(let i=0;i<P.count;i++) if(Math.abs(b[i]-firstB[i])>1e-9) arrDriftB++;
      seq.push([k, ra, tgt()]);
    }
    reads.push({tag:'S9 A/B 交替对读（A=全默认 / B=全默认+pin）', s:seq,
                arrDriftA, arrDriftB}); }
  // S10：**读数来源三分对照** —— S9 已证「同一份参数数组、冷态读 0 / 暖态读 1」，只剩两种解释：
  //     (i) 真有一套装在 core 里、不随参数重算的状态；(ii) **我们手里这个视图是旧的**——
  //     live2dcubismcore 的 `Model.sync()` 在 wasm 内存增长后会**重建** typed-array 视图，
  //     我们是在 ⑬ 开头一次性抓的 `D/M/PT`，之后每次 update 都可能拿着指向已释放内存的旧视图，
  //     读出来的是"上一次的残留"而不是当前值 ⇒ 台账整条线都建在坏仪器上。
  //     三种读法：旧视图 `D.opacities` / **每拍重新取** `core._model.drawables.opacities` /
  //     框架自己的 getter（`getDrawableOpacityByIndex` 一类）。只要有一处不同 ⇒ 仪器问题，
  //     三处全同 ⇒ (i) 成立，才继续找那套状态。
  const apiName=['getDrawableOpacityByIndex','getDrawableOpacity'].find(n=>typeof core[n]==='function');
  const rawFresh=()=>{ const M2=core._model;
    return ti.map(j=>j<0? null : +M2.drawables.opacities[j].toFixed(3)); };
  const apiRead=apiName? (()=>ti.map(j=>j<0? null : +core[apiName](j).toFixed(3))) : null;
  { const seq=[]; let mismatch=0;
    for(let k=0;k<cfg.settle;k++){
      writeAll(DEF);
      const r=[tgt(), rawFresh(), apiRead? apiRead(): null];
      if(apiRead){ if(JSON.stringify(r[0])!==JSON.stringify(r[1])||JSON.stringify(r[1])!==JSON.stringify(r[2])) mismatch++; }
      else if(JSON.stringify(r[0])!==JSON.stringify(r[1])) mismatch++;
      seq.push(['A'+k, r]);
      writeAll(withPin(DEF));
      const r2=[tgt(), rawFresh(), apiRead? apiRead(): null];
      seq.push(['B'+k, r2]);
    }
    reads.push({tag:'S10 三种读法对照（旧视图 / 每拍重取视图 / 框架 getter）', s:seq,
                api:apiName||'无此方法', mismatch}); }
  // S12：**同一条交替，但改用框架 setter**（`core.setParameterValueByIndex`）而不是直写 wasm 缓冲。
  //     真实播放走的就是这条（motion 求值器逐参数调它，还要过页面补丁 ⑤/⑦）。
  //     若 S12 可逆、而 S9/S10 带单向锁存 ⇒ 之前所有「参数→显隐」台账都是**绕过框架**测出来的，
  //     不代表播放路径 ⇒ 按它生成的 snapswitch 表与修法 (b) 的前提就都站不住。
  const setByApi=(vals)=>{ let d=0;
    for(let i=0;i<P.count;i++) if(Math.abs(P.values[i]-vals[i])>1e-9){ d++;
      try{ core.setParameterValueByIndex(i, vals[i]); }catch(e){} }
    core.update(); return d; };
  { const seq=[]; let firstA=null, firstB=null, driftA=0, driftB=0;
    for(let k=0;k<cfg.settle;k++){
      const wa=setByApi(DEF); const a=Array.from(P.values);
      if(k===0) firstA=a.slice(); else for(let i=0;i<P.count;i++) if(Math.abs(a[i]-firstA[i])>1e-9) driftA++;
      const ra=tgt();
      const wb=setByApi(withPin(DEF)); const b=Array.from(P.values);
      if(k===0) firstB=b.slice(); else for(let i=0;i<P.count;i++) if(Math.abs(b[i]-firstB[i])>1e-9) driftB++;
      seq.push([k, ra, tgt(), wa, wb]);
    }
    reads.push({tag:'S12 A/B 交替但走框架 setter（第 4/5 列=本次实际写了几格）', s:seq,
                apiSetter:true, driftA, driftB}); }
  // 输入侧自证：S5 与 S6 之后参数数组必须逐位相同，否则上面两行根本不可比
  const vA=Array.from(P.values); writeAll(withPin(DEF)); const vB=Array.from(P.values);
  let pdiff=0; for(let i=0;i<P.count;i++) if(Math.abs(vA[i]-vB[i])>1e-9) pdiff++;
  // 全默认写完之后 update 自己会改写哪些参数（= moc3 里的派生参数/key-assign 算子清单）
  writeAll(DEF); const rewr=diffAfterUpdate(DEF);
  // S14：**冷/暖全模型对照** —— S9~S12 已证"同一份参数数组、显隐读不出来"。这里把范围放大到全部片：
  //     冷态（第一次全默认）与暖态（被扫过之后再次全默认）逐片比 ⇒ 锁存究竟只是个别片的状态，
  //     还是一大片"脏标记没被重算"。这个数直接决定台账能不能当**函数表**用。
  const warmVec=Array.from(D.opacities); const cwd=[];
  for(let j=0;j<D.count;j++) if(Math.abs(warmVec[j]-coldVec[j])>1e-3)
    cwd.push([D.ids[j], +coldVec[j].toFixed(2), +warmVec[j].toFixed(2)]);
  window.__hideSet=null; window.__ambOff=ambWas; window.__snapOff=snapWas;
  try{ window.__m.autoUpdate=true; }catch(e){}
  try{ if(tkWas) window.__app.ticker.start(); }catch(e){}
  return JSON.stringify({meshes:cfg.meshes, idx:ti, miss, pinIx, nstep:cfg.nstep,
    idEcho:pinIx.map(e=>[e[0], e[1], e[1]>=0?P.ids[e[1]]:null]),
    partsKeyNames:Object.keys(PT), drawablePartKeys:partKeys, chain, protoPartMeth:protoMeth,
    coreRewrittenFromDefaults:rewr, finalParamDiffBetweenPaths:pdiff, rows, reads,
    attrs, drawableKeyNames:dkeys, drawables:D.count, params:P.count,
    coldWarmDiffCount:cwd.length, coldWarmDiff:cwd.slice(0,60)});
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
  // 全部开关家族（来自 <model>.snapswitch.json 的 params[].meshes）：每帧量"有几个家族整族全灭"
  const fams=(cfg.fams||[]).map(a=>a.map(n=>D.ids.indexOf(n)).filter(i=>i>=0)).filter(a=>a.length);
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
                 i25.reduce((a,i)=>a+(O[i]>=0.5?1:0),0), +mx(i25).toFixed(3),
                 fams.reduce((a,mi)=>a+(mi.some(j=>O[j]>=0.5)?0:1),0)];
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


def sig2pairs(s):
    """JS 侧签名 ['idx:op', …] → [[idx, op], …]（解析不了的条目直接丢，不拿 None 参与比较）。"""
    out = []
    for x in (s or []):
        try:
            i, o = str(x).split(":")
            out.append([int(i), float(o)])
        except Exception:
            pass
    return out


def cold_merge(model):
    """⑰ 合并正序/倒序两遍冷态读数 → 可发布的台账。发布判据三条，缺一不收：
      ① **逐格签名一致**：同一个 (参数, 网格点) 在两次独立页面会话里读到的「哪些片变成多少」完全相同；
      ② **复位 drift 恒 0**：每次探测前都先把全部参数写回 moc3 默认，若复位后仍不等于冷基线，
         这一格就是滞回污染下的读数，不能当函数值；
      ③ **两遍二分收敛到同一个阈值**：边界条数相同、且每对边界的中点相差不超过两遍里较大的 eps。
    产物与 ⑤ 的台账同形状（`nstep/ref/names/map`），另带 `bounds`（二分到 eps 的**真阈值**，
    不是网格中点）与 `rejected`（没收的参数和原因）。下游：`l2d_snap_criterion_scan.py --ledger @该文件`。"""
    base = os.path.join(ROOT, ".diag")
    fF = os.path.join(base, "l2d_coldmapall_%s_fwd.json" % model)
    fR = os.path.join(base, "l2d_coldmapall_%s_rev.json" % model)
    miss = [f for f in (fF, fR) if not os.path.exists(f)]
    if miss:
        print("MISSING\n  %s" % "\n  ".join(miss))
        print("⇒ 先跑 --coldmapall auto（正序）与 --coldmapall auto --coldrev（倒序），两次独立进程 = 两次独立页面会话")
        return 2
    F = json.load(open(fF, encoding="utf-8"))
    R = json.load(open(fR, encoding="utf-8"))
    dF = {r["param"]: r for r in F.get("results", []) if r.get("param")}
    dR = {r["param"]: r for r in R.get("results", []) if r.get("param")}
    cold0 = F.get("cold0") or []
    dnames = F.get("names") or []
    nd = F.get("drawables") or len(cold0)
    nstep = int(F.get("nstep", 10))

    # 每换一次页面就是一次新的冷会话 ⇒ 各组的冷基线必须相同，否则"冷"这个前提根本不成立
    for side, D17 in (("正序", F), ("倒序", R)):
        gs = [g for g in D17.get("groups", []) if g.get("cold0")]
        if len(gs) > 1:
            b0 = gs[0]["cold0"]
            diff = [g["group"] for g in gs[1:] if g["cold0"] != b0]
            if diff:
                print("[FAIL] %s第 %s 组的新页面冷基线与第 1 组不同 ⇒ 冷基线不可复现，这次扫描整体不发布"
                      % (side, diff))
                return 1
            print("%s：跨 %d 次新会话的冷基线**逐位相同**（亮 %s 片）" % (side, len(gs), gs[0].get("cold0lit")))

    def gridops(res):
        g = {}
        for row in res["grid"]:
            g[row["q"]] = {int(j): float(v) for j, v in row["chg"]}
        return g

    def bkey(b):
        return None if (b.get("tertiary") or b.get("budget")) else (b["lo"] + b["hi"]) / 2.0

    published, rejected = [], []
    for p in sorted(set(dF) | set(dR)):
        if p not in dF or p not in dR:
            rejected.append([p, "只有一遍里有（另一遍在这一批之前就中断了）"])
            continue
        A, B = dF[p], dR[p]
        if A.get("fail") or B.get("fail"):
            rejected.append([p, "扫描失败：%s" % (A.get("fail") or B.get("fail"))])
            continue
        ga, gb = gridops(A), gridops(B)
        bad = [q for q in range(nstep + 1)
               if sorted(ga.get(q, {}).items()) != sorted(gb.get(q, {}).items())]
        if bad:
            rejected.append([p, "两遍逐格签名不一致（%d/%d 格）⇒ 有滞回" % (len(bad), nstep + 1)])
            continue
        drA = max([row["drift"] for row in A["grid"]] or [0])
        drB = max([row["drift"] for row in B["grid"]] or [0])
        if drA or drB:
            rejected.append([p, "复位不回滚：drift 正序最大 %d / 倒序最大 %d" % (drA, drB)])
            continue
        ba, bb = A.get("bounds", []), B.get("bounds", [])
        if len(ba) != len(bb):
            rejected.append([p, "两遍找到的边界条数不同（%d vs %d）" % (len(ba), len(bb))])
            continue
        far = [(x["lo"], x["hi"], y["lo"], y["hi"]) for x, y in zip(ba, bb)
               if bkey(x) is not None and bkey(y) is not None
               and abs(bkey(x) - bkey(y)) > max(x.get("eps", 0), y.get("eps", 0))]
        if far:
            rejected.append([p, "两遍二分收敛到不同阈值 %s" % (far[:3],)])
            continue
        changed = {}
        for q in range(nstep + 1):
            for j, op in ga[q].items():
                changed.setdefault(j, {})[q] = op
        aff = []
        for j, cur in sorted(changed.items()):
            ops = [cur.get(q, cold0[j] if j < len(cold0) else 0.0) for q in range(nstep + 1)]
            if len(set(ops)) == 1:
                continue                       # 全格常量 ⇒ 量不出阈值，不算翻转绑定
            aff.append([j, [[q, ops[q]] for q in range(nstep + 1)]])
        if not aff:
            rejected.append([p, "两遍一致但没有任何片在网格内变化过"])
            continue
        published.append({"param": p, "idx": A["idx"], "mn": A["mn"], "mx": A["mx"], "dflt": A["dflt"],
                          "aff": aff,
                          "bounds": [{"lo": b["lo"], "hi": b["hi"], "eps": b.get("eps"),
                                      "mid": (None if bkey(b) is None else round(bkey(b), 5)),
                                      "budget": bool(b.get("budget")),
                                      "tertiary": b.get("tertiary")} for b in ba]})

    ledger = {"model": model, "schema": "cold-17", "nstep": nstep, "drawables": nd,
              "ref": cold0, "names": dnames,
              "generatedBy": "l2d_part_flicker_probe.py --coldmerge",
              "note": "每格都从 moc3 默认一跳；正序/倒序两次独立页面会话逐格一致 + 复位 drift 恒 0 + 两遍二分同阈值 才发布；"
                      "bounds.mid 是真阈值（不是网格中点），tertiary 表示区间里还有第三个状态",
              "map": [[i, p["param"], round(p["mn"], 3), round(p["mx"], 3), p["dflt"], 0,
                       len(p["aff"]), p["aff"]] for i, p in enumerate(published)],
              "bounds": {p["param"]: p["bounds"] for p in published},
              "rejected": rejected,
              "stats": {"scanned": len(set(dF) | set(dR)), "published": len(published),
                        "rejected": len(rejected), "updates": [F.get("updates"), R.get("updates")]}}
    out = os.path.join(base, "l2d_cold_ledger_%s.json" % model)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False)

    print("\n== ⑰ 冷态台账合并：扫过 %d 个参数 → **发布 %d 个**、退回 %d 个"
          % (ledger["stats"]["scanned"], len(published), len(rejected)))
    print("   两遍各自 update 次数 %s；冷基线亮着 %s 片；台账 → %s"
          % (ledger["stats"]["updates"], F.get("cold0lit"), out))
    for p in published[:40]:
        fl = [b["mid"] for b in ledger["bounds"][p["param"]] if b["mid"] is not None]
        ter = sum(1 for b in ledger["bounds"][p["param"]] if b["tertiary"])
        print("   %-22s 量程[%.3g,%.3g] 会翻的片 %3d  真阈值 %s%s"
              % (p["param"], p["mn"], p["mx"], len(p["aff"]),
                 [round(x, 4) for x in fl][:8], ("  +tertiary %d" % ter if ter else "")))
    if len(published) > 40:
        print("   …另 %d 个参数只在台账文件里" % (len(published) - 40,))
    if rejected:
        print("   退回（不进台账）:")
        for r in rejected[:40]:
            print("     %-22s %s" % (r[0][:22], r[1]))
        if len(rejected) > 40:
            print("     …另 %d 条" % (len(rejected) - 40,))
    old = os.path.join(ROOT, "Output", "Live2D", model, "%s.snapswitch.json" % model)
    if published and os.path.exists(old):
        oj = json.load(open(old, encoding="utf-8"))
        print("   —— 与现役表（⑤ 的网格中点阈值）对照:")
        for name, spec in sorted((oj.get("params") or {}).items()):
            new = ledger["bounds"].get(name)
            nf = [b["mid"] for b in new if b["mid"] is not None] if new else None
            print("     %-22s 旧 %s → 新 %s" % (name, [round(x, 3) for x in (spec.get("flips") or [])][:8],
                                              ("不在新台账" if nf is None else [round(x, 4) for x in nf][:8])))
    return 0 if published else 1


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
    ap.add_argument("--recon", default="", help="⑬ 台账矛盾判定：逗号分隔的 mesh 名（必须自带一条阳性对照片），在同一趟里对读 ⑤ 的扫法与 ⑫ 的钉法")
    ap.add_argument("--reconshot", default="", help="⑭ 同参数两历史比像素：逗号分隔的 mesh 名（分「引擎真锁存」与「读错缓冲」）")
    ap.add_argument("--reconcold", default="", help="⑮ 冷态逐拍：逗号分隔的 mesh 名；全新页面上一次跳到 --rpin 再逐拍读，判「显隐是第几拍才结算」")
    ap.add_argument("--coldmap", default="", help="⑯ 冷态逐值全模型图：形如 Param25:0,0.1,0.2,0.4,0.6（每个值都从默认一次跳到，正序+倒序各一遍）")
    ap.add_argument("--focus", default="", help="⑯ 只盯这几片（逗号分隔 mesh 名），否则打印每档新亮/新灭名单前 10")
    ap.add_argument("--coldmapall", default="", help="⑰ 冷态全量台账：auto=取 ⑤ 台账里会改显隐的那批参数当**候选名单**（不用它的阈值）；"
                                                    "或逗号分隔参数名；或 @文件。每点从 moc3 默认一跳 + 阈值二分。配 --coldrev 跑倒序那遍")
    ap.add_argument("--coldrev", action="store_true", help="⑰ 跑**倒序**那一遍（要另起一次进程 = 独立页面会话）")
    ap.add_argument("--coldnstep", type=int, default=10, help="⑰ 网格段数（默认 10 段 = 11 点，与 ⑤ 同网格便于对照）")
    ap.add_argument("--coldreload", type=int, default=20, help="⑰ 每这么多个参数重载一次页面：滞回会跨参数累积，冷基线只能靠新会话保证")
    ap.add_argument("--coldbis", type=int, default=12, help="⑰ 每个边界最多二分几刀（eps = 量程/2^此值，且不低于 --coldeps）")
    ap.add_argument("--coldeps", type=float, default=0.0, help="⑰ 阈值绝对容差，0 = 用 量程/2^--coldbis")
    ap.add_argument("--coldprobes", type=int, default=90, help="⑰ 每个参数二分最多花多少次探测（预算用完则该阈值不发布）")
    ap.add_argument("--coldmerge", action="store_true", help="⑰ 只合并：读 _fwd/_rev 两遍，逐格签名一致且 drift 恒 0 才发布 → .diag/l2d_cold_ledger_<model>.json（不开浏览器）")
    ap.add_argument("--latchreset", default="", help="⑱ 棘轮能不能复位：参数名（先换新页面，P1 必须是本会话第一次探测）")
    ap.add_argument("--lrtarget", type=float, default=0.05, help="⑱ 冷读数目标值（默认 0.05 = 实测『半透明手』那一档）")
    ap.add_argument("--lrhot", type=float, default=1.0, help="⑱ 污染用的高值")
    ap.add_argument("--lrmode", default="reset", choices=["reset", "seq"], help="⑱ reset=逐个试复位手段；seq=同一批值只换「一次探测打几拍 update」做 A/B")
    ap.add_argument("--lrprotocol", default="two", choices=["one", "two"], help="⑱ seq 模式：two=先复位打一拍再打目标值一拍（⑰ 现做法）；one=写成目标状态只打一拍")
    ap.add_argument("--lrseq", default="0,0.05,0.1,0.2,0.5,1.0", help="⑱ seq 模式扫的值（按参数量程钳）")
    ap.add_argument("--lrpump", type=int, default=60, help="⑱ seq 模式：复位后再连打几拍（分「锁存」与「慢收敛」）")
    ap.add_argument("--preroll", action="store_true", help="㉑ 预路过（补丁 ⑧）A/B：开/关各跑一遍全新页面，逐组量六组手亮几片")
    ap.add_argument("--handdark", action="store_true", help="㉒ 手部并集**逐拍**只记翻转与全灭窗口（不受截图速度限制）；"
                                                            "配 --hdclip/--hdsecs/--hdsmall/--hdparams")
    ap.add_argument("--hdclip", default="home", help="㉒ 从 idle 强切到哪条 clip（时钟原点=切换那一刻）")
    ap.add_argument("--hdsecs", type=float, default=20.0, help="㉒ 切换后连续测多少秒")
    ap.add_argument("--hdsmall", type=int, default=1, help="㉒ 1=先把渲染器缩到 360x260 换拍率（0=不缩）；拍率会随结果发布")
    ap.add_argument("--hdparams", default="Param25,Param27,Param28,Param145,Param144",
                    help="㉒ 每次翻转随行的参数读数（逗号分隔参数名）")
    ap.add_argument("--hdevery", type=int, default=4, help="㉒ 全模型逐顶点扫描每几拍做一次（1=每拍，拍率会掉一半）")
    ap.add_argument("--hdshots", default="", help="㉒ 在这些秒数各抓一张页面内截图（逗号分隔，走 renderer.extract 不冻结时钟）")
    ap.add_argument("--hdonlyat", default="", help="㉒ 在这些秒数额外抓一张「只留手部片」的图，并直接量手的**屏幕**包围盒（判手有没有被裁到画面外）")
    ap.add_argument("--hdgrpat", type=float, default=0, help="㉒ 在这一秒做**阳性对照**：逐组只 hide 一组各抓一张，认出名单里每组到底是画面上哪一块（0=不做）")
    ap.add_argument("--hdw", type=int, default=360, help="㉒ 缩渲染器的宽（要和手看得清，抓图时建议 720 以上）")
    ap.add_argument("--hdh", type=int, default=260, help="㉒ 缩渲染器的高")
    ap.add_argument("--hdui", action="store_true", help="㉒ 走页面入口（下拉选动作 + 点「重播」）而不是直接 startMotion —— "
                                                        "只有这条路会装填「残留复位层」，见 JS_HANDDARK 注释")
    ap.add_argument("--hdsnapat", default="", help="㉒ 在这些秒数各打一次场景快照（容器变换 / 模型空间可见包围盒 / 回绕名单 / 离默认最远的参数）")
    ap.add_argument("--hdunphase", type=float, default=0, help="㉒ >0 则在该秒把补丁 ⑤ 的回绕集合**清空**（同一次运行内的 A/B，判"
                                                                "「角色跑掉是不是回绕造成的」）")
    ap.add_argument("--latchlaw", default="", help="⑲ 锁存律：参数名（可写成 Param25:0,0.05,0.1 指定值表），**每个值换一次新页面**")
    ap.add_argument("--lawseq", default="0,0.02,0.05,0.08,0.1,0.15,0.2,0.3,0.4,0.5,0.6,1.0",
                    help="⑲ 默认值表（覆盖不到具体形状时自己加值，一页一值 ⇒ 值表就是成本）")
    ap.add_argument("--rpin", default="Param25:0.5", help="⑬ 钉住的参数，形如 Param25:0.5")
    ap.add_argument("--settle", type=int, default=4, help="⑬ S7/S8 逐拍读几拍（判「显隐是不是滞后一拍才结算」）")
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

    if a.coldmerge:
        return cold_merge(a.model)

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

    def reload_boot():
        """重载页面并重新装钩子 + boot。⑰ 专用：滞回会**跨参数累积**，冷基线只能靠新会话保证。"""
        cmd("Page.navigate", {"url": url + "&r=%d" % int(time.time() * 1000)})
        href = ""
        for _ in range(120):
            try:
                href = str(ev("String(location.href)"))
                if href.startswith(url) and str(ev("String(document.readyState)")) == "complete":
                    break
            except Exception:
                pass
            time.sleep(0.5)
        ev("window.__installHooks=function(){ return %s; }" % JS_INSTALL)
        rb = ev(boot_src)
        try:
            j = json.loads(rb) if isinstance(rb, str) and rb.strip().startswith("{") else {"fail": str(rb)[:220]}
        except Exception:
            j = {"fail": "boot 返回不是 JSON", "raw": str(rb)[:220]}
        return j

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
        fams = []
        sf = os.path.join(ROOT, "Output", "Live2D", a.model, "%s.snapswitch.json" % a.model)
        if os.path.exists(sf):
            sj = json.load(open(sf, encoding="utf-8"))
            fams = [v.get("meshes") or [] for v in (sj.get("params") or {}).values()]
        cfg = {"from": frm, "to": to,
               "setA": [x.strip() for x in a.snapA.split(",") if x.strip()],
               "setB": [x.strip() for x in a.snapB.split(",") if x.strip()],
               "set25": set25, "fams": fams,
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
                darkFam = [i for i in range(len(win)) if len(win[i]) > 7 and win[i][7] > 0]
                print("   %-4s 采样 %d 帧（切换在第 %d 帧）；A∧B 同时灭 %d 帧 / 约 %.2fs；切换后 nLit 最低 %s；A 峰 %.2f B 峰 %.2f；台账集(该参数能影响的全部 mesh) 最低 %d/%d 亮、峰值 %.2f"
                      % ("修法关" if mode == "off" else "修法开", len(rows), k0, len(darki), secs,
                         min([r[2] for r in win]) if win else "-",
                         max([r[3] for r in win]) if win else -1, max([r[4] for r in win]) if win else -1,
                         min([r[5] for r in win]) if win else -1, len(cfg["set25"]),
                         max([r[6] for r in win]) if win else -1))
                print("        「整族全灭」的帧 %d/%d；单帧最多同时灭 %d 个家族；切换后仍全灭的家族 %s"
                      % (len(darkFam), len(win),
                         max([r[7] for r in win]) if win and len(win[0]) > 7 else -1,
                         sorted({(win[i][1]) for i in darkFam})))
                tl = os.path.join(ROOT, ".diag", "l2d_snapab_%s_%s.txt" % (a.model, mode))
                with open(tl, "w", encoding="utf-8") as fh:
                    fh.write("ts group nLit maxA maxB nLedger25 maxLedger25 famDark %s\n" % " ".join(cfg["pnames"]))
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

    # —— ⑯ 冷态逐值全模型图（放在最前：这一臂要求"每个值都从默认一次跳到"，前面不能有爬档）
    if a.coldmap:
        pname16, _, vlist = a.coldmap.partition(":")
        vs16 = [float(x) for x in vlist.split(",") if x.strip() != ""]
        focus16 = [x.strip() for x in a.focus.split(",") if x.strip()]
        raw16 = ev(JS_COLDMAP + "({param:%s, values:%s, focus:%s})"
                   % (json.dumps(pname16), json.dumps(vs16), json.dumps(focus16)))
        try:
            r16 = json.loads(raw16) if isinstance(raw16, str) and raw16.strip().startswith("{") else {"err": str(raw16)[:300]}
        except Exception:
            r16 = {"err": str(raw16)[:300]}
        f16 = os.path.join(ROOT, ".diag", "l2d_coldmap_%s_%s.json" % (a.model, pname16))
        with open(f16, "w", encoding="utf-8") as fh:
            json.dump({"cfg": {"param": pname16, "values": vs16, "focus": focus16}, "res": r16}, fh, ensure_ascii=False)
        if "passes" not in r16:
            print("\n== ⑯ 冷态逐值图未出结果: %s" % str(r16)[:300])
        else:
            print("\n== ⑯ 冷态逐值图：`%s`(下标 %s) 每个值都从 moc3 默认**一次跳到**，读全部 %d 片"
                  % (pname16, r16.get("idx"), r16.get("drawables")))
            print("   正序与倒序两遍是否一致: %s（不一致 ⇒ 台账那类逐档扫描带滞回，不能当函数表）"
                  % ("**一致**" if r16.get("forwardBackwardAgree") else "**不一致 ⇒ 有滞回**"))
            for pi, rows in enumerate(r16["passes"]):
                print("   第 %d 遍（%s）" % (pi + 1, "正序" if pi == 0 else "倒序"))
                for r in rows:
                    print("     %-7s 亮着 %4d 片 | 相对默认 新亮 %d / 新灭 %d%s"
                          % (r["v"], r["lit"], r["nOn"], r["nOff"],
                             ("  关注片读数 %s" % dict(zip(focus16, r["focus"])) if focus16 else "")))
                    if not focus16:
                        print("        新亮 %s | 新灭 %s" % (r["on"][:10], r["off"][:10]))
            print("   台账 → %s" % f16)

    # —— ⑱ 棘轮复位判定（先换新页面：P1 必须是本会话的第一次探测，否则"冷读数"这个说法不成立）
    if a.latchreset:
        j18 = reload_boot()
        if not j18.get("ok"):
            print("   [FAIL] ⑱ 重载后启动失败：%s" % str(j18)[:180])
        else:
            raw18 = ev(JS_LATCHRESET + "({param:%s, target:%s, hot:%s, mode:%s, protocol:%s, seq:%s, pump:%d})"
                       % (json.dumps(a.latchreset), json.dumps(a.lrtarget), json.dumps(a.lrhot),
                          json.dumps(a.lrmode), json.dumps(a.lrprotocol),
                          json.dumps([float(x) for x in a.lrseq.split(",") if x.strip() != ""]),
                          max(0, a.lrpump)))
            try:
                r18 = json.loads(raw18) if isinstance(raw18, str) and raw18.strip().startswith("{") else {"err": str(raw18)[:280]}
            except Exception:
                r18 = {"err": str(raw18)[:280]}
            f18 = os.path.join(ROOT, ".diag", "l2d_latchreset_%s_%s%s.json"
                               % (a.model, a.lrmode, "_%s" % a.lrprotocol if a.lrmode == "seq" else ""))
            with open(f18, "w", encoding="utf-8") as fh:
                json.dump({"cfg": {"param": a.latchreset, "target": a.lrtarget, "hot": a.lrhot,
                                   "mode": a.lrmode, "protocol": a.lrprotocol, "seq": a.lrseq},
                           "res": r18}, fh, ensure_ascii=False)
            if "steps" not in r18:
                print("\n== ⑱ 未出结果：%s" % str(r18)[:280])
            elif a.lrmode == "seq":
                print("\n== ⑱ seq 协议 A/B：`%s` 量程[%.3g,%.3g] 协议=%s，冷基线亮 %s 片"
                      % (a.latchreset, r18.get("mn", 0), r18.get("mx", 0), r18.get("protocol"), r18.get("cold0lit")))
                st18 = r18["steps"]
                for i in range(0, len(st18) - 1, 2):
                    p, q = st18[i], st18[i + 1]
                    print("   v=%-8s 探测：亮 %-5s 差异 %-4s | 复位后：亮 %-5s 残留 %-4d → 连打 %d 拍后残留 %s %s"
                          % (p["value"], p["lit"], p.get("nOn"), q["lit"], q["nSig"], r18.get("pump", a.lrpump),
                             q.get("afterPump"), (q["sig"][:6] if q["nSig"] else "")))
                res = [s["nSig"] for s in st18 if s["tag"].startswith("reset")]
                pmp = [s.get("afterPump") for s in st18 if s["tag"].startswith("reset")]
                print("   ⇒ 协议 %s 复位残留 %s；连打 %d 拍之后 %s  %s"
                      % (r18.get("protocol"), res, a.lrpump, pmp,
                         ("残留随拍数归零 ⇒ 是慢收敛，不是锁存"
                          if any(res) and not any(pmp) else
                          ("全程 0 ⇒ 没有锁存" if not any(res) else
                           "拍数打不掉 ⇒ 锁存成立（对本引擎而言显隐不是参数的函数）"))))
            else:
                print("\n== ⑱ 棘轮复位判定：`%s` 目标值 %s、污染值 %s，冷基线亮 %s 片"
                      % (a.latchreset, a.lrtarget, a.lrhot, r18.get("cold0lit")))
                print("   %-42s %-6s %-6s %s" % ("步骤", "亮着", "差异片", "备注"))
                for s in r18["steps"]:
                    print("   %-42s %-6s %-6d %s" % (s["tag"], s["lit"], s["nSig"],
                          ("sig %s" % s["sig"][:4]) if s["nSig"] else ""))
                print("   打到 %s 再回默认之后，仍不等于冷基线的片数：%s" % (r18.get("hot"), r18.get("afterHotNSig")))
                print("   ⇒ 能把缓冲打回冷基线的复位手段：%s" % (r18.get("okReset") or "一个都没有"))
                for x in r18.get("p4", []):
                    print("      复位[%s] 后再探同一值：与 P1 冷读数%s（亮 %s 片，差异 %s）"
                          % (x["after"], "**相同 ⇒ 可复现**" if x["sameAsP1"] else "**不同 ⇒ 仍被历史决定**",
                             x["lit"], x["nSig"]))
                print("   core/model 上真实存在的 reset 类 API：%s" % json.dumps(r18.get("api"), ensure_ascii=False)[:300])
                print("   结论要看：没有任何复位成功 ⇒ ⑰ 只能「一页一探测」，全库批量判死；"
                      "有且签名可复现 ⇒ ⑰ 按原方案跑，复位步骤写进 probe。")

    # —— ㉑ 预路过（补丁 ⑧）的 A/B：必须各跑一遍全新页面（补丁在表到手那一刻就生效，事后开关无效）
    if a.preroll:
        steps21 = [{"tag": "idle 稳态", "clip": "idle", "wait": 4.0},
                   {"tag": "切到 home 首帧", "clip": "home", "wait": 0.25},
                   {"tag": "home +3s", "clip": "", "wait": 3.0},
                   {"tag": "home +9s（已过第一段过渡）", "clip": "", "wait": 6.0},
                   {"tag": "home +15s", "clip": "", "wait": 6.0}]
        res21 = {}
        for mode in ("off", "on"):
            if mode == "off":
                cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__preRoll=false;"})
            j21 = reload_boot()
            if not j21.get("ok"):
                print("   [FAIL] ㉑ %s 那遍重载失败：%s" % (mode, str(j21)[:160]))
                break
            raw21 = ev(JS_PREROLL + "({steps:%s})" % json.dumps(steps21))
            try:
                res21[mode] = json.loads(raw21) if isinstance(raw21, str) and raw21.strip().startswith("{") else {"err": str(raw21)[:240]}
            except Exception:
                res21[mode] = {"err": str(raw21)[:240]}
            if mode == "off":
                try:
                    cmd("Page.removeScriptToEvaluateOnNewDocument", {"identifier": "1"})
                except Exception:
                    pass
        f21 = os.path.join(ROOT, ".diag", "l2d_preroll_ab_%s.json" % a.model)
        with open(f21, "w", encoding="utf-8") as fh:
            json.dump(res21, fh, ensure_ascii=False)
        print("\n== ㉑ 预路过 A/B（六组手 = ⑲ 冷态律给的键位分组；on = 载入后把所有键路过一遍）")
        for mode in ("off", "on"):
            r = res21.get(mode) or {}
            if "seq" not in r:
                print("   %s 那遍未出结果：%s" % (mode, str(r)[:200]))
                continue
            last = (r["dbg"].get("last") or {})
            print("   %s：preRoll=%s 预路过 hits=%s 耗时=%sms 表=%s"
                  % (mode, r.get("preroll"), last.get("hits"), last.get("ms"),
                     (r["dbg"].get("snap") or {}).get("state")))
            for st in r["seq"]:
                print("     %-30s 亮 %-5s  %s" % (st["tag"], st["lit"],
                      "  ".join("%s %d/%d" % (g, st.get(g + "_on", 0), n) for g, n in r["groups"])))
        if all("seq" in (res21.get(m) or {}) for m in ("off", "on")):
            print("\n   判据①（idle 稳态下六组各至少亮一片）：")
            for mode in ("off", "on"):
                st = next((x for x in res21[mode]["seq"] if x["tag"] == "idle 稳态"), None)
                if not st:
                    continue
                bad = [g for g, n in res21[mode]["groups"] if g != "A" and st.get(g + "_on", 0) == 0]
                print("     %s：%s" % (mode, "六组全有亮的" if not bad else "仍整组全灭 %s" % bad))
            print("   判据②（切到 home 之后不得出现「整组从亮变灭」）：")
            for mode in ("off", "on"):
                seq = res21[mode]["seq"]
                hits = []
                for x, y in zip(seq, seq[1:]):
                    for g, n in res21[mode]["groups"]:
                        if x.get(g + "_on", 0) > 0 and y.get(g + "_on", 0) == 0:
                            hits.append("%s→%s %s" % (x["tag"], y["tag"], g))
                print("     %s：%s" % (mode, hits or "无整组熄灭"))
        print("   逐组读数 → %s" % f21)

    # —— ㉒ 手部并集逐拍：上一趟 `--trace` 20s 只拿到 200 拍（swiftshader 渲染 200ms/拍），
    #    "并集从没为 0"这个结论的**时间分辨率不够**，不能拿来判死。本臂把采样提到拍率自证 ≥25/s，
    #    并且只记翻转与全灭窗口，所以高频也不会把结果撑爆。
    if a.handdark:
        HD34 = ["ArtMesh36", "ArtMesh42", "ArtMesh43", "ArtMesh44", "ArtMesh51",
                "ArtMesh331", "ArtMesh332", "ArtMesh333", "ArtMesh334", "ArtMesh335",
                "ArtMesh325", "ArtMesh326", "ArtMesh327", "ArtMesh328", "ArtMesh329", "ArtMesh330",
                "ArtMesh355", "ArtMesh379",
                "ArtMesh356", "ArtMesh357", "ArtMesh358", "ArtMesh359", "ArtMesh360",
                "ArtMesh364", "ArtMesh380", "ArtMesh381", "ArtMesh593", "ArtMesh594",
                "ArtMesh365", "ArtMesh366", "ArtMesh367", "ArtMesh368", "ArtMesh369", "ArtMesh370"]
        j22 = reload_boot()
        if not j22.get("ok"):
            print("   [FAIL] ㉒ 重载失败：%s" % str(j22)[:160])
        else:
            cfg22 = {"clip": a.hdclip, "secs": a.hdsecs, "small": bool(a.hdsmall), "names": HD34,
                     "every": max(1, a.hdevery), "w": a.hdw, "h": a.hdh, "ui": bool(a.hdui),
                     "groups": [HD34[0:5], HD34[5:10], HD34[10:16], HD34[16:18],
                                HD34[18:23], HD34[23:28], HD34[28:34]],
                     "grpNames": ["A", "g01", "g02", "g03", "g04", "g05", "g06"],
                     "grpAt": (a.hdgrpat if a.hdgrpat > 0 else None),
                     "snapAt": [float(x) for x in a.hdsnapat.split(",") if x.strip()],
                     "onlyAt": [float(x) for x in a.hdonlyat.split(",") if x.strip()],
                     "unphaseAt": (a.hdunphase if a.hdunphase > 0 else 0),
                     "shots": [float(x) for x in a.hdshots.split(",") if x.strip()],
                     "params": [x.strip() for x in a.hdparams.split(",") if x.strip()]}
            raw22 = ev(JS_HANDDARK + "(%s)" % json.dumps(cfg22))
            try:
                r22 = json.loads(raw22) if isinstance(raw22, str) and raw22.strip().startswith("{") else {"err": str(raw22)[:300]}
            except Exception:
                r22 = {"err": str(raw22)[:300]}
            f22 = os.path.join(ROOT, ".diag", "l2d_handdark_%s_%s.json" % (a.model, a.hdclip))
            with open(f22, "w", encoding="utf-8") as fh:
                json.dump(r22, fh, ensure_ascii=False)
            print("\n== ㉒ 手部并集逐拍（%d 片，切换→`%s`，测 %.1fs）" % (len(HD34), a.hdclip, a.hdsecs))
            if "upd" not in r22:
                print("   [FAIL] %s" % str(r22)[:300])
            else:
                print("   自证：upd=%d 拍率=%.1f/s（缩渲染器=%s） 名单命中=%d/%d 缺=%s"
                      % (r22["upd"], r22["updPerSec"], r22["small"], r22["handCount"],
                         len(HD34), r22["missing"] or "无"))
                print("   全模型：亮(opacity>0.5) 最少%s/最多%s ｜ 看得见(亮且面积>%.0e) 最少%s/最多%s"
                      % ("-", r22["maxVis"], r22["eps"], r22["minVis"], r22["maxVis"]))
                print("   手部名单：亮片数 %s~%s ｜ **看得见**的片数 %s~%s"
                      % (r22["minHl"], r22["maxHl"], r22["minHv"], r22["maxHv2"]))
                print("   亮片全灭窗口 %d 个 ｜ **看得见=0** 的窗口 %d 个：%s"
                      % (len(r22["windows"]), len(r22["vwindows"]),
                         ("  ".join("[%.2f→%.2f] %.2fs" % (w[0], w[1], w[1] - w[0])
                                    for w in r22["vwindows"][:12])) or "无"))
                print("   翻转事件 %d 次（前 40）：t 并集亮数 [新亮]/[新灭] 随行参数%s"
                      % (r22["changesTotal"], r22["watch"]))
                for ch in r22["changes"][:40]:
                    print("     %7.3fs 亮%-3d  +%-28s -%-28s %s"
                          % (ch[0], ch[2], ",".join(x.replace("ArtMesh", "") for x in ch[3])[:28],
                             ",".join(x.replace("ArtMesh", "") for x in ch[4])[:28], ch[5]))
                rows22 = r22.get("rows") or []
                if rows22:
                    print("   逐拍时间轴（t 全模型亮/看得见 手亮/手看得见 手面积合计）每 %d 拍取一拍："
                          % max(1, len(rows22) // 24))
                    for x in rows22[::max(1, len(rows22) // 24)]:
                        print("     %7.3fs %-6s %4d/%4d   手 %2d/%2d  面积 %8.3f"
                              % (x[0], (x[7] if len(x) > 7 else ""), x[1], x[2], x[3], x[4], x[5]))
                    gseq, glast = [], None
                    for x in rows22:
                        g = x[7] if len(x) > 7 else ""
                        if g != glast:
                            gseq.append((x[0], g)); glast = g
                    print("   currentGroup 变化：%s" % ("  ".join("%.2fs→%s" % (a_, b_ or "空") for a_, b_ in gseq[:14])))
                    for sn in (r22.get("snaps") or []):
                        print("   [snap] t=%-7.2f group=%-6s 容器变换(sx,sy,px,py,rot)=%s 可见包围盒=%s"
                              % (sn.get("t", -1), sn.get("g"), sn.get("tr"), sn.get("bb")))
                        ph = sn.get("phase")
                        if isinstance(ph, list):
                            print("          回绕名单 %d 个：%s" % (len(ph), ",".join(ph[:16])))
                        for fr in (sn.get("far") or [])[:8]:
                            print("          偏离默认 %-12s dev=%-5s 值=%-7s 默认=%-7s 量程[%s,%s]" % tuple(fr))
                    if r22.get("unphased"):
                        print("   中途清空回绕集合（同页 A/B）：%s" % r22["unphased"])
                    hn22 = r22.get("handNames") or HD34
                    if rows22 and len(rows22[0]) > 6:
                        cols = list(zip(*[x[6] for x in rows22]))
                        print("   逐片面积（最大/最小/最小出现的时刻；最小不到最大的 20% 记 COLLAPSE）：")
                        for j, nm in enumerate(hn22[:len(cols)]):
                            c = list(cols[j])
                            if not c:
                                continue
                            mx = max(c); mi = min(c); mni = c.index(mi)
                            coll = "COLLAPSE" if mx > 1e-3 and mi < 0.2 * mx else ""
                            print("     %-12s 最大%8.3f 最小%8.3f @%6.2fs 首%8.3f 末%8.3f %s"
                                  % (nm, mx, mi, rows22[mni][0], c[0], c[-1], coll))
                    vcs = r22.get("vcEnd") or []
                    if vcs:
                        print("   顶点体检（收尾那一拍）：片名 / vertexCount / 顶点数组长度 / 首顶点坐标")
                        for row in vcs:
                            print("     %-12s vc=%-5s 长度=%-5s 首顶点=(%s, %s)"
                                  % (row[0], row[1], row[2], row[3], row[4]))
                        print("   全模型 vertexCount==0 的 drawable：%s / %s"
                              % (r22.get("zeroVertexDrawables"), r22.get("totalDrawables")))
                if r22.get("dimming"):
                    print("   半途变淡（同一拍没灭但透明度变了，前 8）：%s"
                          % json.dumps(r22["dimming"][:8], ensure_ascii=False)[:400])
                if r22["updPerSec"] < 25:
                    print("   ⚠️ 拍率 %.1f/s 不够（<25/s）：这趟**测不到**几十毫秒级的闪没，"
                          "只够证明 %.0fms 以上的窗口不存在" % (r22["updPerSec"], 1000.0 / r22["updPerSec"]))
                print("   逐拍明细 → %s" % f22)
                idx22 = ev("JSON.stringify((window.__shots||[]).map(s=>({t:s.t,want:s.want,err:s.err||null,row:s.row,hands:!!s.handsB64,handsErr:s.handsErr||null,grp:(s.grp||[]).length,gbase:!!s.grpBase})))") or "[]"
                try:
                    lst22 = json.loads(idx22)
                except Exception:
                    lst22 = []
                for q, s in enumerate(lst22):
                    if s.get("err"):
                        print("   [shot] t=%s 抓失败：%s" % (s.get("want"), s["err"]))
                        continue
                    b64 = ev("window.__shots[%d].b64||''" % q) or ""
                    if isinstance(b64, dict):
                        b64 = b64.get("value", "")
                    b64 = (b64 or "").split(",", 1)[-1]
                    if not b64:
                        print("   [shot] t=%s 没取到 base64" % s.get("want"))
                        continue
                    fp22 = os.path.join(ROOT, ".diag", "l2d_handdark_%s_%s_t%s.png"
                                        % (a.model, a.hdclip, ("%5.2f" % s.get("t", 0)).replace(" ", "0")))
                    with open(fp22, "wb") as fh:
                        fh.write(base64.b64decode(b64))
                    print("   [shot] t=%.2fs 逐拍签名(手 亮/看得见/面积)=%s → %s"
                          % (s.get("t", 0), (s.get("row") or [])[3:], os.path.basename(fp22)))
                    if s.get("hands"):
                        hb = ev("window.__shots[%d].handsB64||''" % q) or ""
                        hb = (hb or "").split(",", 1)[-1]
                        if not hb:
                            print("          只留手：没取到 base64（%s）" % (s.get("handsErr") or "?"))
                            continue
                        fp23 = fp22[:-4] + "_handsonly.png"
                        with open(fp23, "wb") as fh:
                            fh.write(base64.b64decode(hb))
                        try:
                            from PIL import Image as _Im
                            im23 = _Im.open(fp23).convert("RGBA")
                            bb = im23.split()[3].getbbox()
                            W23, H23 = im23.size
                            if not bb:
                                print("          只留手：画布上**一个不透明像素都没有** ⇒ 手整体在画面外 (%dx%d)" % (W23, H23))
                            else:
                                x0, y0, x1, y1 = bb
                                edge = "".join(n for n, c in (("左", x0 <= 1), ("上", y0 <= 1),
                                                               ("右", x1 >= W23 - 2), ("下", y1 >= H23 - 2)) if c)
                                print("          只留手：屏幕包围盒(%d,%d)-(%d,%d) 画布%dx%d 贴边=%s 占屏%.1f%%"
                                      % (x0, y0, x1, y1, W23, H23, edge or "无",
                                         100.0 * (x1 - x0) * (y1 - y0) / (W23 * H23)))
                        except Exception as e23:
                            print("          只留手：算包围盒失败 %s" % str(e23)[:120])
                    gp_base = fp22
                    if s.get("gbase"):
                        gbz = (ev("window.__shots[%d].grpBase||''" % q) or "").split(",", 1)[-1]
                        if gbz:
                            gp_base = fp22[:-4] + "_frozen.png"
                            with open(gp_base, "wb") as fh:
                                fh.write(base64.b64decode(gbz))
                    for gz in range(int(s.get("grp") or 0)):
                        meta = ev("JSON.stringify({name:window.__shots[%d].grp[%d].name,n:window.__shots[%d].grp[%d].n,"
                                  "err:window.__shots[%d].grp[%d].err||null})" % (q, gz, q, gz, q, gz))
                        try:
                            mm23 = json.loads(meta)
                        except Exception:
                            mm23 = {"name": "?", "n": 0, "err": str(meta)[:80]}
                        gb = ev("window.__shots[%d].grp[%d].b64||''" % (q, gz)) or ""
                        gb = (gb or "").split(",", 1)[-1]
                        if not gb:
                            print("          [阳性对照] hide %s 抓图失败：%s" % (mm23.get("name"), mm23.get("err")))
                            continue
                        fp24 = fp22[:-4] + "_hide-%s.png" % mm23.get("name")
                        with open(fp24, "wb") as fh:
                            fh.write(base64.b64decode(gb))
                        try:
                            from PIL import Image as _Im, ImageChops as _C
                            a1 = _Im.open(gp_base).convert("RGB")
                            a2 = _Im.open(fp24).convert("RGB")
                            dif = _C.difference(a1, a2).convert("L")
                            bb = dif.getbbox()
                            nd = sum(1 for v in list(dif.getdata()) if v > 24)
                            print("          [阳性对照] 只 hide %-4s(%2d 片) → 画面差异 %7d 像素 区域 %s → %s"
                                  % (mm23.get("name"), mm23.get("n") or 0, nd, bb, os.path.basename(fp24)))
                        except Exception as e24:
                            print("          [阳性对照] hide %s 存图成功，比差异失败 %s"
                                  % (mm23.get("name"), str(e24)[:100]))

    # —— ⑲ 锁存律：**一页只探一个值**（⑱ 证了显隐是路径函数之后，这是唯一还能拿到「边沿→写入」对应关系的形状）
    #    每页做三件事：冷基线 → 一次跳到 v（这份签名 = 该值的**干净响应** R(v)）→ 回默认打一拍 + 连打 pump 拍
    #    （仍不等于冷基线的那些 = 该值留下的**锁存写入** L(v)，逐条带读数，能分清"钉在亮"还是"钉在灭"）。
    #    值表就是成本：一页 ~20~40s，12 个值 ≈ 5~8 分钟，所以要跑在脱离宿主的进程里。
    if a.latchlaw:
        pname19 = a.latchlaw.split(":")[0]
        vs19 = ([float(x) for x in a.latchlaw.partition(":")[2].split(",") if x.strip()]
                if ":" in a.latchlaw else [float(x) for x in a.lawseq.split(",") if x.strip()])
        out19 = os.path.join(ROOT, ".diag", "l2d_latchlaw_%s_%s.json" % (a.model, pname19))
        law19 = {"model": a.model, "param": pname19, "values": vs19, "pump": max(0, a.lrpump),
                 "protocol": "one（写成目标状态只打一拍）", "names": None, "rows": []}
        print("\n== ⑲ 锁存律：`%s` 一页一个值，共 %d 页（约 %d 分钟）"
              % (pname19, len(vs19), max(1, len(vs19) * 30 // 60)))
        for vi, vv in enumerate(vs19):
            j19 = reload_boot()
            if not j19.get("ok"):
                print("   [FAIL] 第 %d/%d 页（v=%s）重载失败：%s" % (vi + 1, len(vs19), vv, str(j19)[:160]))
                break
            raw19 = ev(JS_LATCHRESET + "({param:%s, mode:'seq', protocol:'one', seq:[%s], pump:%d, cap:400})"
                       % (json.dumps(pname19), json.dumps(vv), max(0, a.lrpump)))
            try:
                r19 = json.loads(raw19) if isinstance(raw19, str) and raw19.strip().startswith("{") else {"err": str(raw19)[:240]}
            except Exception:
                r19 = {"err": str(raw19)[:240]}
            if "steps" not in r19 or len(r19["steps"]) < 2:
                print("   [FAIL] 第 %d/%d 页未出结果：%s" % (vi + 1, len(vs19), str(r19)[:240]))
                break
            if law19["names"] is None:
                law19["names"] = r19.get("names")
            p19, q19 = r19["steps"][0], r19["steps"][1]
            cold19 = r19.get("cold0lit")
            pr = sig2pairs(p19["sig"])
            on19 = [[i, o] for i, o in pr if o > 0.5]
            off19 = [[i, o] for i, o in pr if o <= 0.5]
            lat19 = sig2pairs(q19["sig"])
            law19["rows"].append({"v": vv, "cold0lit": cold19, "lit": p19["lit"],
                                  "on": on19, "off": off19, "nOn": len(on19), "nOff": len(off19),
                                  "latch": lat19, "latchN": q19["nSig"],
                                  "latchAfterPump": q19.get("afterPump"),
                                  "latchPumpList": sig2pairs(q19.get("pumpSig"))})
            with open(out19, "w", encoding="utf-8") as fh:
                json.dump(law19, fh, ensure_ascii=False)
            nm = law19["names"] or []
            ld = ["%s=%s" % ((nm[i] if i < len(nm) else "#%d" % i), o) for i, o in lat19[:6]]
            print("   v=%-7s 亮 %-4s（冷基线 %s）点亮 %-4d 灭掉 %-4d | 复位残留 %-4d（连打 %d 拍后 %s）%s"
                  % (vv, p19["lit"], cold19, len(on19), len(off19), q19["nSig"], a.lrpump,
                     q19.get("afterPump"), ("  " + ", ".join(ld) if ld else "")))
        print("   台账 → %s（每页都即时落盘，中途崩了也留已完成的部分）" % out19)
        if len(law19["rows"]) >= 2:
            mono = all(law19["rows"][i]["latchN"] <= law19["rows"][i + 1]["latchN"]
                       for i in range(len(law19["rows"]) - 1))
            print("   ⇒ 每页都是新会话，残留只可能是**该值自己**写的；残留随 v 单调不减：%s（%s）"
                  % ("是" if mono else "否", "单调 ⇒ 高值把低值该灭的也钉住" if mono else "非单调 ⇒ 锁存集合不是包含关系"))

    # —— ⑰ 冷态全量台账（把 ⑯ 的形状铺到整批参数；跑这条时**不要**同时传别的会改状态的臂）
    if a.coldmapall:
        spec17 = a.coldmapall.strip()
        lf5 = os.path.join(ROOT, ".diag", "l2d_opacity_map_%s.json" % a.model)
        if spec17 in ("auto", "@auto"):
            if not os.path.exists(lf5):
                print("\n== ⑰ auto 的候选名单来自 ⑤ 的台账（只借它挑「哪些参数碰得到显隐」，不借它的阈值）：先跑 --mapall")
                return 2
            cand17 = [e[1] for e in json.load(open(lf5, encoding="utf-8")).get("map", [])]
        elif spec17.startswith("@") and os.path.exists(spec17[1:]):
            tx17 = open(spec17[1:], encoding="utf-8").read().strip()
            cand17 = list(json.loads(tx17)) if tx17.startswith("[") else \
                [x.strip() for x in tx17.replace(",", "\n").splitlines() if x.strip()]
        else:
            cand17 = [x.strip() for x in spec17.split(",") if x.strip()]
        sfx17 = "rev" if a.coldrev else "fwd"
        out17 = os.path.join(ROOT, ".diag", "l2d_coldmapall_%s_%s.json" % (a.model, sfx17))
        agg17 = {"model": a.model, "reverse": bool(a.coldrev), "nstep": a.coldnstep,
                 "cold0": None, "names": None, "drawables": None, "cold0lit": None,
                 "updates": 0, "groups": [], "results": []}
        CH17 = max(1, a.coldreload)
        ng17 = (len(cand17) + CH17 - 1) // CH17
        print("\n== ⑰ 冷态全量台账（%s序）：候选 %d 个参数，每 %d 个换一次新页面 ⇒ %d 组"
              % ("倒" if a.coldrev else "正", len(cand17), CH17, ng17))
        for gi in range(ng17):
            grp = cand17[gi * CH17:(gi + 1) * CH17]
            j17 = reload_boot()          # **每组都换新页面**，第一组也不例外：boot 之前那些臂已经播过动作
            if not j17.get("ok"):
                print("   [FAIL] 第 %d 组重载后启动失败：%s ⇒ 已扫的部分原样落盘"
                      % (gi + 1, str(j17)[:180]))
                break
            tg17 = time.time()
            raw17 = ev(JS_COLDMAPALL + "({params:%s, nstep:%d, reverse:%s, maxBis:%d, epsAbs:%g, cap:240, maxProbes:%d})"
                       % (json.dumps(grp), a.coldnstep, json.dumps(bool(a.coldrev)),
                          max(4, a.coldbis), a.coldeps, max(8, a.coldprobes)))
            try:
                r17 = json.loads(raw17) if isinstance(raw17, str) and raw17.strip().startswith("{") else {"err": str(raw17)[:280]}
            except Exception:
                r17 = {"err": str(raw17)[:280]}
            if "results" not in r17:
                print("   [FAIL] 第 %d/%d 组未出结果：%s" % (gi + 1, ng17, str(r17)[:280]))
                break
            if agg17["cold0"] is None:
                agg17["cold0"], agg17["names"] = r17.get("cold0"), r17.get("names")
                agg17["drawables"], agg17["cold0lit"] = r17.get("drawables"), r17.get("cold0lit")
            agg17["groups"].append({"group": gi + 1, "cold0": r17.get("cold0"),
                                    "cold0lit": r17.get("cold0lit"), "updates": r17.get("updates")})
            dirty = [x["param"] for x in r17["results"] if x.get("maxDrift")]
            touched = [x["param"] for x in r17["results"]
                       if any(g["nChg"] for g in x.get("grid", []))]
            agg17["results"] += r17["results"]
            agg17["updates"] += r17.get("updates", 0)
            with open(out17, "w", encoding="utf-8") as fh:
                json.dump(agg17, fh, ensure_ascii=False)
            print("   ⑰ 第 %d/%d 组：参数 %d，updates=%d，会改显隐 %d 个，冷基线亮 %s 片，"
                  "复位不回滚的参数 %d%s  本组 %.0fs"
                  % (gi + 1, ng17, len(grp), r17.get("updates", 0), len(touched),
                     r17.get("cold0lit"), len(dirty), (" 例 %s" % dirty[:4] if dirty else ""),
                     time.time() - tg17))
        print("   半成品/成品 → %s（合并判据另跑 --coldmerge）" % out17)

    # —— ⑮ 冷态逐拍（放在所有会改状态的臂**之前**，否则"冷"字不成立）
    if a.reconcold:
        ms15 = [x.strip() for x in a.reconcold.split(",") if x.strip()]
        pin15 = [[x.split(":")[0], float(x.split(":")[1])]
                 for x in re.split(r"[,\s]+", a.rpin or "") if ":" in x]
        raw15 = ev(JS_RECONCOLD + "({meshes:%s, pin:%s, n:%s})"
                   % (json.dumps(ms15), json.dumps(pin15), json.dumps(max(2, a.settle))))
        try:
            r15 = json.loads(raw15) if isinstance(raw15, str) and raw15.strip().startswith("{") else {"err": str(raw15)[:300]}
        except Exception:
            r15 = {"err": str(raw15)[:300]}
        f15 = os.path.join(ROOT, ".diag", "l2d_coldstep_%s.json" % a.model)
        with open(f15, "w", encoding="utf-8") as fh:
            json.dump({"cfg": {"meshes": ms15, "pin": pin15}, "res": r15}, fh, ensure_ascii=False)
        if "seq" not in r15:
            print("\n== ⑮ 冷态逐拍未出结果: %s" % str(r15)[:300])
        else:
            print("\n== ⑮ 冷态逐拍：一次跳到 %s 之后逐拍读（全新页面、中途绝不预热）" % (pin15,))
            print("   %-6s %-4s %-8s %s" % ("方向", "拍", "参数实值", "  ".join("%-12s" % m for m in ms15)))
            for row in r15["seq"]:
                print("   %-6s %-4s %-8s %s" % (row[0], row[1], row[3],
                                                "  ".join("%-12s" % v for v in row[2])))
            up = [r for r in r15["seq"] if r[0] == "up"]
            dn = [r for r in r15["seq"] if r[0] == "down"]
            base = r15["seq"][0][2]
            for j, m in enumerate(ms15):
                ku = next((r[1] for r in up if abs((r[2][j] or 0) - (base[j] or 0)) > 1e-3), None)
                kd = next((r[1] for r in dn if abs((r[2][j] or 0) - (up[-1][2][j] or 0)) > 1e-3), None)
                print("   %-12s 基线 %-6s 跳变后第 %s 拍才变 | 跳回后第 %s 拍才变 ⇒ %s"
                      % (m, base[j], ku if ku else "不变", kd if kd else "不变",
                         ("滞后 %d 拍 ⇒ 台账阈值里混进了『第几拍』" % ku) if ku else "该片不受这次跳变影响"))
            print("   台账 → %s" % f15)

    # —— ⑭ 状态定格截图：同参数、两种历史，比像素（分"引擎真锁存"与"读错缓冲"）
    if a.reconshot:
        ms14 = [x.strip() for x in a.reconshot.split(",") if x.strip()]
        pin14 = [[x.split(":")[0], float(x.split(":")[1])]
                 for x in re.split(r"[,\s]+", a.rpin or "") if ":" in x]
        shots = {}

        def setstate(tag, state, via, repeat=1):
            raw = ev(JS_SET_STATE + "({state:%s, pin:%s, meshes:%s, repeat:%s, via:%s})"
                     % (json.dumps(state), json.dumps(pin14), json.dumps(ms14),
                        json.dumps(repeat), json.dumps(via)))
            try:
                j14 = json.loads(raw) if isinstance(raw, str) and raw.strip().startswith("{") else {"err": str(raw)[:200]}
            except Exception:
                j14 = {"err": str(raw)[:200]}
            png = cmd("Page.captureScreenshot", {"format": "png"})
            fp = os.path.join(ROOT, ".diag", "l2d_state_%s_%s.png" % (a.model, tag))
            with open(fp, "wb") as fh:
                fh.write(base64.b64decode(png["data"]))
            shots[tag] = fp
            print("   %-12s state=%s 驱动=%-6s 写 %s 格 ×%s 拍 | 读数 %s | pin %s | 亮着的片 %s | part非1=%s"
                  % (tag, j14.get("state"), j14.get("via"), j14.get("wrote"), j14.get("updates"),
                     j14.get("targets"), json.dumps(j14.get("pin"), ensure_ascii=False),
                     j14.get("litPixi"), j14.get("partNon1")))
            return j14

        print("\n== ⑭ 同参数两历史比像素（目标 %s，pin %s）" % (",".join(ms14), pin14))
        try:
            from PIL import Image, ImageChops

            def npix(p, q):
                i1 = Image.open(p).convert("RGB"); i2 = Image.open(q).convert("RGB")
                if i1.size != i2.size:
                    i2 = i2.resize(i1.size)
                dm = ImageChops.difference(i1, i2).convert("L")
                return sum(1 for x in dm.getdata() if x > 12), dm.getbbox()

            for via in ("model", "core"):   # model 先跑：core 那趟的 coldA 已被上一趟扫过，只当复现
                p = "%s_" % via
                c1 = setstate(p + "coldA", "A", via)
                setstate(p + "coldA2", "A", via)
                setstate(p + "B", "B", via)
                w1 = setstate(p + "warmA", "A", via)
                n1, bx1 = npix(shots[p + "coldA"], shots[p + "warmA"])
                n2, _ = npix(shots[p + "B"], shots[p + "warmA"])
                same_read = (c1.get("targets") or []) == (w1.get("targets") or [])
                print("   [%s] coldA vs warmA（参数逐位相同）差 %d 像素 包围盒 %s | B vs warmA 差 %d 像素 | 两档读数%s"
                      % (via, n1, bx1, n2, "相同" if same_read else "**不同**"))
                print("   [%s] ⇒ %s" % (via, (
                    "读数变、像素也变 ⇒ 引擎确实按历史决定可见性（台账不是函数表）" if n1 >= 50 and not same_read
                    else "读数变、像素不变 ⇒ 这块缓冲没进渲染（该档差异与画面无关），台账的「该亮」不成立于像素"
                    if not same_read else "读数不变 ⇒ 这种驱动下没有锁存")))
            print("   注意：coldA 是「本会话第一次把参数写成全默认」，warmA 是「被扫过之后回到全默认」——"
                  "两者参数数组逐位相同，只有历史不同。")
        except Exception as e:
            print("   像素对照失败: %r" % (e,))

    # —— ⑬ 台账矛盾判定（§6.37 第一件事：同一趟里对读 ⑤ 的扫法与 ⑫ 的钉法）
    if a.recon:
        meshes13 = [x.strip() for x in a.recon.split(",") if x.strip()]
        pin13 = [[x.split(":")[0], float(x.split(":")[1])]
                 for x in re.split(r"[,\s]+", a.rpin or "") if ":" in x]
        raw13 = ev(JS_RECON + "({meshes:%s, pin:%s, nstep:%s, settle:%s})"
                   % (json.dumps(meshes13), json.dumps(pin13), json.dumps(max(4, a.nsweep)),
                      json.dumps(max(2, a.settle))))
        try:
            r13 = json.loads(raw13) if isinstance(raw13, str) and raw13.strip().startswith("{") else {"err": str(raw13)[:300]}
        except Exception:
            r13 = {"err": str(raw13)[:300]}
        f13 = os.path.join(ROOT, ".diag", "l2d_recon_%s.json" % a.model)
        with open(f13, "w", encoding="utf-8") as fh:
            json.dump({"cfg": {"meshes": meshes13, "pin": pin13}, "res": r13}, fh, ensure_ascii=False)
        if "rows" not in r13:
            print("\n== ⑬ 台账矛盾判定未出结果: %s" % str(r13)[:300])
        else:
            print("\n== ⑬ 台账矛盾判定（目标 %s，pin %s）" % (",".join(meshes13), pin13))
            print("   下标 %s | 名字数组自证 %s | 扫完后两条写路径的参数数组差异 %d 个（必须为 0 才可比）"
                  % (r13.get("idx"), r13.get("idEcho"), r13.get("finalParamDiffBetweenPaths")))
            if r13.get("miss"):
                print("   ⚠️ 这些名字不在模型里: %s" % r13["miss"])
            print("   parts 视图字段: %s | drawables 里带 part 字样的字段: %s | core 原型上的 part 方法: %s"
                  % (r13.get("partsKeyNames"), r13.get("drawablePartKeys"), r13.get("protoPartMeth")))
            if r13.get("chain"):
                for c in r13["chain"]:
                    print("     归属 %s → %s" % (c["key"], c["vals"]))
            hdr = "   %-26s %-8s %s" % ("状态", "写了几格", "  ".join("%-11s" % m for m in meshes13))
            print(hdr)
            for x in r13["rows"]:
                pp = x.get("part") or {}
                print("   %-26s %-8s %s  part:%s非1=%s 区间[%s,%s] pin实值=%s"
                      % (x["tag"], x["wrote"],
                         "  ".join("%-11s" % ("-" if v is None else ("%.3f" % v)) for v in x["op"]),
                         ("可读" if pp.get("readable") else "**读不到(%s)**" % pp.get("type")),
                         pp.get("non1"), pp.get("mn"), pp.get("mx"),
                         json.dumps(x.get("pin"), ensure_ascii=False)))
            for s13 in r13.get("reads") or []:
                print("   %s:" % s13["tag"])
                if "api" in s13:            # S10 的形状：[标签, [旧视图, 新视图, 框架 getter]]
                    print("      框架 getter: %s | **三种读法不一致的次数 = %d**（>0 ⇒ 台账建在失效视图上）"
                          % (s13["api"], s13["mismatch"]))
                    for row in s13["s"]:
                        r = row[1]
                        print("      %-4s 旧视图 %-28s 重取视图 %-28s getter %s"
                              % (row[0], r[0], r[1], r[2] if len(r) > 2 else "-"))
                    continue
                if s13.get("apiSetter"):    # S12 的形状：[k, A 读数, B 读数, A 写了几格, B 写了几格]
                    print("      参数数组漂移自证: A %d 格 / B %d 格（应为 0）" % (s13["driftA"], s13["driftB"]))
                    for row in s13["s"]:
                        print("      第%-3s A %-28s | B %-28s   写格数 A=%s B=%s"
                              % (row[0], row[1], row[2], row[3], row[4]))
                    continue
                if "arrDriftA" in s13:      # S9 的 A/B 交替形状：[k, A 读数, B 读数]
                    print("      参数数组漂移自证: 第 %d 次起 A %d 格 / B %d 格（应为 0，否则两列不可比）"
                          % (len(s13["s"]), s13["arrDriftA"], s13["arrDriftB"]))
                    for row in s13["s"]:
                        print("      第%-3s A %-28s | B %s" % (row[0], row[1], row[2]))
                    continue
                for row in s13["s"]:
                    line = "      %-8s %s" % (row[0], "  ".join(
                        "%s=%s" % (m, ov) for m, ov in zip(meshes13, row[1])))
                    if len(row) > 2:
                        line += "   part非1=%s" % row[2]
                    if len(row) > 3:
                        line += "   update 改写了 %s" % (", ".join(
                            "%s(%s→%s)" % (nm, a, b) for nm, a, b in row[3][:8]) or "无")
                    print(line)
            rw = r13.get("coreRewrittenFromDefaults") or []
            print("   全默认写完后 core 在 update 里自己改写的参数：%d 个 %s"
                  % (len(rw), ", ".join("%s(%s→%s)" % (nm, a, b) for nm, a, b in rw[:12]) or "（无 ⇒ 没有派生参数链）"))
            for x in (r13.get("attrs") or []):
                print("   属性 %-12s idx=%-4s 类型=%s 混合=%s 掩膜数=%s 被掩膜引用=%s 归属part=%s 顶点=%s 索引=%s"
                      % (x["name"], x["idx"], x.get("type"), x.get("blend"), x.get("maskCounts"),
                         x.get("maskRef"), x.get("part"), x.get("verts"), x.get("indices")))
            cwd13 = r13.get("coldWarmDiff") or []
            print("   冷/暖全模型对照（两次都是「全默认」，差别只在中间被扫过）：读数不同的片 **%d / %d**"
                  % (r13.get("coldWarmDiffCount", -1), r13.get("drawables", -1)))
            print("      %s" % ", ".join("%s(%s→%s)" % (nm, a, b) for nm, a, b in cwd13[:26]))
            s3 = next((x for x in r13["rows"] if x["tag"].startswith("S3")), None)
            if s3 and s3.get("partProbe"):
                pb = s3["partProbe"]
                print("   part 是输入还是输出：写 1 之后非 1 的个数 %s → update 之后 %s ⇒ %s"
                      % (pb["afterWrite"]["non1"] if pb["afterWrite"].get("readable") else "?",
                         pb["afterUpdate"]["non1"] if pb["afterUpdate"].get("readable") else "?",
                         "core 会覆盖我们写的值（part 是输出）" if pb["overwritten"]
                         else "core 不动它（part 是不随参数重算的第二套输入）"))
            print("   台账 → %s" % f13)

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
