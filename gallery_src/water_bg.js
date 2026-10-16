/* 水面背景 —— 首页 / 音乐库 / 背景库共用的一个模块（2026-10-15 从 index.html 抽出）。
   为什么抽出来：这三页本来只有首页有这层水；用户要求"音乐库和背景库也还上水波背景"，
   而复制一份到另外两页 = 两份正本（本项目反复踩过的坑：改了忘同步、断链、双真相）。
   所以唯一正本在这里，三页各引一行 <script src="./water_bg.js"></script>。

   模块自己负责三件事，调用方什么都不用做：
     ① 注入样式（原来住在 index.html 的 <style> 里）；
     ② 建 #bgfx 宿主层（首页 HTML 里本来就有，这里复用它，不会重复建）；
     ③ 起停循环（跟随「减少动效」、站用背景、以及本页有没有模态框打开）。
   ⚠️ 主题切换后必须重取一次颜色（水面参数是 JS 一次性读进 BG.P 的）——
      这里用 MutationObserver 盯 documentElement 的 data-theme，各页的切主题代码不用改。

   三条硬约束（照抄 index.html 的原注）：pointer-events:none；z-index 低于内容；卡片是不透明面板。
   实现：CPU 上跑 240×N 的波动方程（Float32 三缓冲，一次遍历几千次加法），
   高度场当纹理上传，WebGL 只负责按法线画高光与泡沫。零噪声函数、零 fbm、零域扭曲。
   色块仍然纯 CSS、颜色全走 token ⇒ 切主题背景自己跟着换。 */
(function(){
'use strict';
if(window.WaterBg) return;                       // 防重复注入（同一页被引两次也不会建两层）

/* ---------- ① 样式 ---------- */
function css(){
  if(document.getElementById('waterbgcss')) return;
  var s=document.createElement('style'); s.id='waterbgcss';
  /* ⚠️ 这里**不留四周渐隐遮罩**（上一版留了，是错的）：#bgfx 是 inset:0 的固定层，
     它的四条边就是屏幕的四条边 —— 被裁在屏幕边上根本看不见，遮罩换不来任何东西；
     而它偏偏把**底部那条唯一露着背景的空带**淡掉了 9%，等于把浪藏起来不给看。 */
  /* closest-side + 中间停靠点 = 平滑衰减；不用 filter:blur（74vmax 的元素上那是白烧 GPU，
     而且径向渐变本身已经足够软）。**没有 animation**：静止就是这版的卖点。 */
  s.textContent=
    '#bgfx{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}'+
    '#bgfx .bfield{position:absolute;inset:-10%}'+
    '#bgfx .glow{position:absolute;width:74vmax;height:74vmax;border-radius:50%}'+
    '#bgfx .g1{left:-24vmax;top:-28vmax;'+
      'background:radial-gradient(closest-side,color-mix(in srgb,var(--brand) 80%,transparent) 0%,'+
        'color-mix(in srgb,var(--brand) 36%,transparent) 40%,transparent 100%)}'+
    '#bgfx .g2{right:-26vmax;bottom:-32vmax;width:68vmax;height:68vmax;'+
      'background:radial-gradient(closest-side,color-mix(in srgb,var(--pop) 66%,transparent) 0%,'+
        'color-mix(in srgb,var(--pop) 26%,transparent) 40%,transparent 100%)}'+
    '#bgfx .g3{right:2vmax;top:-26vmax;width:54vmax;height:54vmax;'+
      'background:radial-gradient(closest-side,color-mix(in srgb,var(--ok) 56%,transparent) 0%,'+
        'color-mix(in srgb,var(--ok) 22%,transparent) 40%,transparent 100%)}'+
    '[data-theme=light] #bgfx .glow{opacity:.8}'+
    '[data-theme=dark]  #bgfx .glow{opacity:.62}'+
    '#bgfx canvas{position:absolute;inset:0;width:100%;height:100%}';
  document.head.appendChild(s);
}

/* ---------- ② 宿主层 ---------- */
function host(){
  var h=document.getElementById('bgfx');
  if(!h){ h=document.createElement('div'); h.id='bgfx'; h.setAttribute('aria-hidden','true');
    h.innerHTML='<div class="bfield"><i class="glow g1"></i><i class="glow g2"></i><i class="glow g3"></i></div>';
    /* 插到 body 第一个子节点：与首页 HTML 里那层的位置一致（z-index:0，内容自己在上面） */
    document.body.insertBefore(h, document.body.firstChild); }
  return h;
}

const RM = matchMedia('(prefers-reduced-motion: reduce)');   // 动效总开关（系统设置）
/* 模态框打开时水面要停：首页的查看器遮罩是 #mask（子页没有这个元素，所以按需取） */
const maskOn = ()=>{ const m=document.getElementById('mask'); return !!(m&&m.classList.contains('on')); };

const BG = { mode:'none', err:'', cv:null, gl:null, prog:null, u:{}, tex:null, pack:null,
             raf:0, lastT:0, last:null, t0:0, w:0, h:0, sw:0, sh:0, cur:null, prv:null, buf:null,
             energy:0, peak:0, frames:0, strokes:0, rs:0.72, HS:620, P:null, texN:0 };
function bgHex(h){ h=(h||'').trim();
  if(h[0]!=='#'||(h.length!==7&&h.length!==4)) return [1,1,1];
  let s=h.slice(1); if(s.length===3) s=s.split('').map(c=>c+c).join('');
  return [parseInt(s.slice(0,2),16)/255, parseInt(s.slice(2,4),16)/255, parseInt(s.slice(4,6),16)/255]; }
function bgColors(){
  /* 颜色全部从 token 读 ⇒ 切主题只要重取一次，着色器不写死任何字面色。 */
  const cs=getComputedStyle(document.documentElement);
  BG.P = { foam:bgHex(cs.getPropertyValue('--w-foam')), glint:bgHex(cs.getPropertyValue('--w-glint')),
           deep:bgHex(cs.getPropertyValue('--w-deep')),
           gain:+(cs.getPropertyValue('--w-gain')||8), foamT:+(cs.getPropertyValue('--w-foamth')||0.010),
           alpha:+(cs.getPropertyValue('--w-alpha')||0.95) };
}
function bgResize(){
  if(!BG.cv) return;
  BG.w=innerWidth; BG.h=innerHeight;
  /* ⚠️ dpr 上限取 1，不是 1.5（2026-10-14 改，理由见 docs/TROUBLESHOOTING.md §143）：
     画布是 0.72× CSS 分辨率再被 CSS 拉满视口的软水，**dpr 提高买不到任何观感**，
     而填充率按像素数走 —— dpr=2 的屏上原式给到 1.08× CSS（1080p 视口 = 2.42Mpx，比 dpr=1 多 2.2 倍）。
     水面的实测帧时增量只有 0.8ms，但那是 dpr=1 的量；这条是把 HiDPI 那 2.2 倍提前掐掉。 */
  const k=Math.min(1, window.devicePixelRatio||1)*BG.rs;
  BG.cv.width=Math.max(2,Math.floor(BG.w*k)); BG.cv.height=Math.max(2,Math.floor(BG.h*k));
  /* 场按视口长宽比取格子：短边固定 240 格，够细到看不出方块、又少到 CPU 扛得住。 */
  BG.sw=240; BG.sh=Math.max(60, Math.round(240*BG.h/Math.max(1,BG.w)));
  const n=BG.sw*BG.sh;
  BG.cur=new Float32Array(n); BG.prv=new Float32Array(n); BG.buf=new Float32Array(n);
  BG.pack=new Uint8Array(n); BG.t0=0; BG.texN=0;   /* texN=0 ⇒ 下一帧重新分配纹理存储 */
  BG.last=null; BG.energy=0; BG.peak=0;
  if(BG.gl){ BG.gl.viewport(0,0,BG.cv.width,BG.cv.height); bgClear(); }
}
function bgClear(){ if(BG.gl){ const g=BG.gl; g.clearColor(0,0,0,0); g.clear(g.COLOR_BUFFER_BIT); } }
/* 帽形脉冲：比 exp 便宜得多，一圈内二次衰减，划出来的波源足够圆 */
function bgStamp(sx, sy, amt, rad){
  const sw=BG.sw, sh=BG.sh, cur=BG.cur, r2=rad*rad;
  const x0=Math.max(1,Math.floor(sx-rad)), x1=Math.min(sw-1,Math.ceil(sx+rad));
  const y0=Math.max(1,Math.floor(sy-rad)), y1=Math.min(sh-1,Math.ceil(sy+rad));
  for(let y=y0;y<y1;y++){ const row=y*sw, dy=y-sy;
    for(let x=x0;x<x1;x++){ const dx=x-sx, d2=dx*dx+dy*dy;
      if(d2<r2) cur[row+x]+=amt*(1-d2/r2); } }
}
/* ⚠️ 阻尼必须按**秒**算，不能按帧：写成"每帧乘 0.964"的话，浪多久平完全取决于帧率——
   60fps 下 2.4 秒平，挂上毛玻璃后无头只有十几帧，实测 20 秒还剩 0.015 不平（本轮撞到）。
   真机上低端设备同样会被判成"背景永远在动"，所以这不是探针的问题，是实现的问题。
   0.11 这个数是换算来的：0.964^60 ≈ 0.111，即"一秒衰减到 11%"，与原设计等价。 */
function bgStep(dt){
  const sw=BG.sw, sh=BG.sh, cur=BG.cur, prv=BG.prv, buf=BG.buf,
        damp=Math.pow(0.11, Math.min(0.1, Math.max(0.001, dt)));
  let e=0, pk=0;
  for(let y=1;y<sh-1;y++){ const row=y*sw;
    for(let x=1;x<sw-1;x++){ const i=row+x;
      const v=((cur[i-1]+cur[i+1]+cur[i-sw]+cur[i+sw])*0.5 - prv[i])*damp;
      buf[i]=v; e+=v*v; const a=v<0?-v:v; if(a>pk) pk=a; } }
  /* 边界留一圈静水（吸收而非反射），否则浪回到池边会反弹回来把整个池子搅浑。 */
  for(let x=0;x<sw;x++){ buf[x]=0; buf[(sh-1)*sw+x]=0; }
  for(let y=0;y<sh;y++){ buf[y*sw]=0; buf[y*sw+sw-1]=0; }
  BG.prv=cur; BG.cur=buf; BG.buf=prv;
  BG.energy=e/(sw*sh); BG.peak=pk;
}
function bgUpload(){
  const g=BG.gl, cur=BG.cur, pk=BG.pack, HS=BG.HS;
  for(let i=0;i<pk.length;i++){ let v=128+cur[i]*HS; pk[i]=v<0?0:(v>255?255:v|0); }
  g.bindTexture(g.TEXTURE_2D, BG.tex);
  /* ⚠️ 首帧 texImage2D 分配、之后一律 texSubImage2D 覆写（2026-10-14 改，§143）：
     原来每帧都调 texImage2D，等于**每帧重新分配整张纹理存储**。
     ⚠️ **别以为这条省了多少**：交替配对实测（A/B 各 3 轮）上传段中位 **+0.000ms/帧、三轮不同号**
     ⇒ CPU 侧**量不出差**。曾一度在这里写"上传 0.13→0.05、合计 −34%"，那是顺序 A/B 吃机器漂移
     造出来的假收益，已作废（§143 补）。保留理由是 **API 语义**——不再每帧重新分配存储，
     这是驱动层的已知隐患、本仪器的 CPU 侧读不到，**量不出来不等于不存在，但也不许说它省了多少**。
     判据：分配与否按像素数记（BG.texN），bgResize() 换尺寸时清 0 强制重分配。 */
  if(BG.texN !== pk.length){
    g.texImage2D(g.TEXTURE_2D,0,g.R8,BG.sw,BG.sh,0,g.RED,g.UNSIGNED_BYTE,pk);
    BG.texN = pk.length;
  } else {
    g.texSubImage2D(g.TEXTURE_2D,0,0,0,BG.sw,BG.sh,g.RED,g.UNSIGNED_BYTE,pk);
  }
}
const BG_VS = '#version 300 es\nin vec2 a_pos; out vec2 vUv;\nvoid main(){ vUv = a_pos*0.5+0.5; gl_Position = vec4(a_pos,0.0,1.0); }';
const BG_FS = [
'#version 300 es',
'precision mediump float;',
'in vec2 vUv;',
'uniform sampler2D u_h;',
'uniform vec2 u_tx;',
'uniform vec3 u_foam, u_glint, u_deep;',
'uniform float u_gain, u_foamT, u_alpha;',
'out vec4 frag;',
'void main(){',
'  float h = texture(u_h, vUv).r;',
'  float re= texture(u_h, vUv+vec2(u_tx.x,0.0)).r;',
'  float le= texture(u_h, vUv-vec2(u_tx.x,0.0)).r;',
'  float up= texture(u_h, vUv+vec2(0.0,u_tx.y)).r;',
'  float dn= texture(u_h, vUv-vec2(0.0,u_tx.y)).r;',
'  vec2 gr = vec2(re-le, up-dn);',
'  float gm = length(gr);',
'  vec3 nz = normalize(vec3(-gr.x*u_gain, -gr.y*u_gain, 1.0));',
'  vec3 L  = normalize(vec3(-0.42, 0.55, 0.72));',
'  float sp = pow(max(dot(reflect(-L,nz), vec3(0.0,0.0,1.0)),0.0), 28.0);',
'  float crest = smoothstep(0.545, 0.70, h);',
'  /* 两条来路取大：陡（梯度大）起沫 + 到了波顶也起沫。',
'     只留前一条的话缓坡那一大片根本不白，看着就是"水变蓝了"而不是"起了浪花"。 */',
'  float foam  = max(smoothstep(u_foamT, u_foamT*2.2, gm) * (0.30 + 0.70*crest), crest);',
'  float body  = abs(h-0.5)*2.0;',
'  float a = clamp(foam + sp*0.9 + body*0.06, 0.0, 1.0) * u_alpha;',
'  vec3 col = (u_foam*foam + u_glint*sp*0.9 + u_deep*body*0.06) / max(a, 1e-3);',
'  frag = vec4(clamp(col,0.0,1.0), a);',
'}'].join('\n');
function bgShader(ty, src){
  const g=BG.gl, s=g.createShader(ty); g.shaderSource(s,src); g.compileShader(s);
  if(!g.getShaderParameter(s,g.COMPILE_STATUS)){ BG.err=g.getShaderInfoLog(s)||'compile'; return null; }
  return s;
}
function bgInit(){
  const g=BG.gl=BG.cv.getContext('webgl2',{alpha:true, premultipliedAlpha:false, powerPreference:'low-power'});
  if(!g){ BG.mode='css'; BG.err='no webgl2'; return; }
  const vs=bgShader(g.VERTEX_SHADER,BG_VS), fs=bgShader(g.FRAGMENT_SHADER,BG_FS);
  if(!vs||!fs){ BG.mode='css'; return; }
  const pr=g.createProgram(); g.attachShader(pr,vs); g.attachShader(pr,fs); g.linkProgram(pr);
  if(!g.getProgramParameter(pr,g.LINK_STATUS)){ BG.mode='css'; BG.err=g.getProgramInfoLog(pr)||'link'; return; }
  BG.prog=pr; BG.mode='gl'; g.useProgram(pr);
  const vao=g.createVertexArray(); g.bindVertexArray(vao);
  const b=g.createBuffer(); g.bindBuffer(g.ARRAY_BUFFER,b);
  g.bufferData(g.ARRAY_BUFFER,new Float32Array([-1,-1, 3,-1, -1,3]),g.STATIC_DRAW);
  const loc=g.getAttribLocation(pr,'a_pos'); g.enableVertexAttribArray(loc);
  g.vertexAttribPointer(loc,2,g.FLOAT,false,0,0);
  ('u_h u_tx u_foam u_glint u_deep u_gain u_foamT u_alpha').split(' ')
    .forEach(n=>{ BG.u[n]=g.getUniformLocation(pr,n); });
  BG.tex=g.createTexture(); g.bindTexture(g.TEXTURE_2D,BG.tex);
  g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.LINEAR);
  g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.LINEAR);
  g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_S,g.CLAMP_TO_EDGE);
  g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_T,g.CLAMP_TO_EDGE);
  g.disable(g.DEPTH_TEST); g.enable(g.BLEND);
  g.blendFunc(g.SRC_ALPHA,g.ONE_MINUS_SRC_ALPHA);
}
function bgRender(){
  const g=BG.gl, P=BG.P;
  g.useProgram(BG.prog); g.activeTexture(g.TEXTURE0); g.bindTexture(g.TEXTURE_2D,BG.tex);
  g.uniform1i(BG.u.u_h,0);
  g.uniform2f(BG.u.u_tx, 1/BG.sw, 1/BG.sh);
  g.uniform3fv(BG.u.u_foam,P.foam); g.uniform3fv(BG.u.u_glint,P.glint); g.uniform3fv(BG.u.u_deep,P.deep);
  g.uniform1f(BG.u.u_gain,P.gain); g.uniform1f(BG.u.u_foamT,P.foamT); g.uniform1f(BG.u.u_alpha,P.alpha);
  g.drawArrays(g.TRIANGLES,0,3);
}
/* 收摊阈值定在**峰值高度**而不是平均能量：平均会被一大片微弱余波摊薄，
   而肉眼看到的从来只是最高的那道浪。
   ⚠️ 这个数**不能贴着衰减尾端定**：实测划满两笔后 peak 从 0.18 一路衰减，
   到第 5.7 秒是 0.00446 —— 而旧阈值正好是 0.0045，于是"能不能收到摊"
   取决于最后一帧的运气，探针 10 秒轮询直接读成"水永远不平"（本轮真实撞到）。
   现在按可见性反推：HS=620 ⇒ v=0.012 对应纹理里 58/255 的偏离，
   着色器里 body = |h-0.5|*2 = 0.116、alpha 上限 0.116×0.06 ≈ 0.007 —— 仍然不可见，
   但离衰减尾端有 2.7 倍余量。 */
const BG_EPS = 0.012;
function bgDraw(ts){
  if(RM.matches || maskOn()){ BG.raf=0; bgClear(); return; }
  const dt=BG.t0 ? Math.min(0.1,(ts-BG.t0)/1000) : 1/60; BG.t0=ts;
  bgStep(dt); bgUpload(); bgRender(); BG.frames++;
  if(BG.peak > BG_EPS){ BG.raf=requestAnimationFrame(bgDraw); }
  else { BG.raf=0; bgClear(); }          // 收摊：清成全透明，回到"逐像素静止"
}
function bgStart(){ if(!BG.raf && BG.mode==='gl') { BG.raf=requestAnimationFrame(bgDraw); } }
/* 指针 → 水高场。走 window 的 pointermove：卡片自己也要收 hover，不能抢事件。 */
function bgWake(x, y, down){
  if(RM.matches || siteBgOn() || BG.mode!=='gl' || maskOn()) return;
  const sx=x/innerWidth*BG.sw, sy=(1-y/innerHeight)*BG.sh;      // 纹理 y 轴翻转对齐 gl_FragCoord
  let lx=sx, ly=sy, dx=0, dy=0;
  if(BG.last){ lx=BG.last[0]; ly=BG.last[1]; dx=sx-lx; dy=sy-ly; }
  BG.last=[sx,sy]; BG.lastT=performance.now();
  const sp=Math.hypot(dx,dy);
  /* 指针「瞬移」不算划水：光标从窗口外进来、跨标签页回来、探针把光标一下挪到角落，
     都会给出一个几百格的位移 —— 按速度插值就等于**沿那条直线糊一道浪**，
     用户看到的是"我什么都没做，背景自己被划了一道"，而且这道浪正好落在底部空带里。
     （本轮就是靠"静止两帧必须逐像素相同"这条判据抓出来的。）超过阈值只挪锚点、不起浪。 */
  if(!down && sp>45) return;
  if(down || sp<0.3){
    bgStamp(sx, sy, down?0.028:0.0022, down?5.0:2.4);            // 按下 = 一颗水滴；慢速 = 微澜
  } else {
    const amt=Math.min(0.042, 0.009+sp*0.0040);                 // 上限必须有：不然划一下糊一屏白
    const rad=Math.max(2.2, Math.min(7.0, 2.0+sp*0.45));
    const steps=Math.max(1, Math.min(12, Math.round(sp/(rad*0.5))));
    /* 偶极注入：前进方向给正、身后给负 —— 才有"船头波"那种向外摊开的浪，
       只注正脉冲等于在原地搅水，波前是圆的不走方向。 */
    for(let k=1;k<=steps;k++){
      const f=k/steps, px=lx+dx*f, py=ly+dy*f;
      bgStamp(px+dx*0.12, py+dy*0.12,  amt,        rad);
      bgStamp(px-dx*0.16, py-dy*0.16, -amt*0.70,   rad*0.85);
    }
    BG.strokes++;
  }
  bgStart();
}
let bgPend=null;
window.addEventListener('pointermove',e=>{
  /* 节流到每帧一次：触摸板 pointermove 能到 120Hz，每次都写场就是白烧 CPU。
     但**不能丢坐标**——丢中间点会让快速拖动在场上留下断口，所以取最新值。 */
  if(RM.matches || siteBgOn() || BG.mode!=='gl') return;
  if(bgPend) return;
  bgPend=requestAnimationFrame(()=>{ bgPend=null; bgWake(e.clientX,e.clientY,false); });
},{passive:true});
window.addEventListener('pointerdown',e=>{ bgWake(e.clientX,e.clientY,true); },{passive:true});
window.addEventListener('blur',()=>{ BG.last=null; });
const siteBgOn=()=>!!(window.SiteBg&&SiteBg.get());
function bgSync(){
  const h=document.getElementById('bgfx'); if(!h) return;
  /* 「减少动效」与「设了站用背景」是同一种状态：水面不是当前的背景 ⇒ 停循环 + 清屏。
     水面 canvas 是不透明的（WebGL alpha:false），CSS 里已经把它 display:none 掉，
     但循环不停就是每帧白烧 3.3ms 画一张看不见的海。 */
  if(RM.matches || siteBgOn()){ if(BG.raf){ cancelAnimationFrame(BG.raf); BG.raf=0; } bgClear(); return; }
  if(!BG.cv){
    BG.cv=document.createElement('canvas'); h.appendChild(BG.cv);
    bgColors(); bgInit(); bgResize();
    window.addEventListener('resize',bgResize);
    if(BG.mode!=='gl'){ BG.cv.remove(); BG.cv=null; return; }
  }
  bgStart();
}

/* ---------- ③ 启动与联动 ---------- */
css(); host();
const boot=()=>{ bgSync(); };
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot); else boot();
RM.addEventListener('change',bgSync);
/* 设 / 取消站用背景时立刻切水面层的运行状态。不监听的话正在跑的循环会一直画到下一次
   bgSync（只有 resize、减少动效变化才触发），用户"取消背景"之后海面就不回来了。 */
document.addEventListener('sitebgchange',()=>bgSync());
/* 主题换了要重取颜色：水面参数是 JS 一次性读进 BG.P 的（泡沫色/斜率增益/起沫阈值），
   不重取就会"夜里还在用白天那套泡沫色"。用观察器而不是让三页各自记得调一次——
   本项目已经踩过"某页忘了同步"的坑，这里把它变成结构上不可能漏。 */
new MutationObserver(()=>{ if(BG.cv) bgColors(); })
  .observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});

/* 探针/调试用（无头验证"这一页水面有没有起来"就靠它）：
   mode=gl 说明 WebGL 起来了；frames 在涨说明循环真的在跑；strokes 是划过几笔。 */
window.WaterBg={ sync:bgSync, colors:bgColors,
  stats:()=>({mode:BG.mode, err:BG.err, hasCanvas:!!BG.cv, raf:!!BG.raf,
    frames:BG.frames, strokes:BG.strokes, peak:+BG.peak.toFixed(5), energy:+BG.energy.toFixed(6),
    sw:BG.sw, sh:BG.sh, siteBg:siteBgOn(), reduced:RM.matches, host:!!document.getElementById('bgfx')}) };
})();
