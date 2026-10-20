/* 动态网站背景 —— 把 Spine 动态皮肤 / Live2D 模型铺成整页背景（2026-10-20 新增）。
   三页共用一份正本，各页引一行 <script src="./site_bg_live.js"></script>。

   ── 它是什么、不是什么 ──
   *是*：`SiteBg` 的**动态类型渲染器**。用户点「设为网站背景」选了动态皮肤时，
   `favorites.js` 把 `kind:'spine'|'live2d'` 存进 localStorage，本模块负责把那个模型
   画到一层全屏 canvas 上，读 `sitebgchange` 事件自动起停。
   *不是*：第二套弹窗渲染器。首页 `index.html` 里那 600 行 Spine/Live2D 代码是**查看器**，
   有滚轮缩放、拖拽机位、背景巨幕剔除、skin 覆盖度选举、motion 保真三补丁 —— 那是为了
   让人**细看一个模型**。背景不需要这些：背景只要"全身居中、动起来、别抢戏"。
   ⚠️ 所以这里**刻意不复制**那套取景修正。真要改查看器，改 index.html；要改背景构图，
   改本文件。两份代码职责不同，不是双真相。

   ── 三条硬约束（照抄 water_bg.js 的同款决定）──
   ① `pointer-events:none`：背景层永远不吃鼠标。用户原话「live2d 作为背景没有交互」——
      同时 `autoInteract:false` 关掉 pixi-live2d-display 的命中检测，连"看着能动一下"
      都不给，避免"背景里的模型抢走了本该点按钮的那一下"。
   ② `z-index:0`：内容层全部在它上面（各页 z-index 从 1 起）。
   ③ **按需挂载**：只有 kind 是 spine/live2d 才创建 canvas 与 WebGL 上下文。
      静态图背景（kind:'bg'|'skin'）完全不经过本模块，零开销。

   ── 为什么不用 CSS 盖一层遮罩做"柔和铺底" ──
   用户要的是"全身居中、柔和铺底"，但遮罩会连模型一起压暗。这里改成：
   canvas 自己画一层从下沿向上淡出的取景暗角（gl 里画 quad），
   模型本身保持原色 —— 这和 favorites.js 给立绘背景"原图清楚铺满"的决定一致。

   ── 生命周期 ──
   sitebgchange → 若 kind 是动态：确保 canvas 在、加载新模型、销毁旧模型；
                 若 kind 不是动态：销毁一切、摘掉 canvas。
   页面卸载 / 切走时同样销毁。Spine 与 Live2D 的销毁路径分开写，因为
   pixi 的 Application.destroy(true,...) 会连带销毁 stage 子节点的纹理，
   而 Spine 的 GLTexture 要自己 dispose（首页那句 `GLTexture.dispose()` 的教训）。 */
(function(){
'use strict';
if(window.SiteBgLive) return;                    // 防重复注入

/* ───────────────────── 样式 ───────────────────── */
function css(){
  if(document.getElementById('sitebglivecss')) return;
  var s=document.createElement('style'); s.id='sitebglivecss';
  /* #sitelive 固定全屏、最底层、不吃鼠标。
     fade-in 让"从静态图切到动态"不是硬跳：新模型首帧到了才加 .on。 */
  s.textContent=
    '#sitelive{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden;'+
      'opacity:0;transition:opacity .7s var(--ease-ios,ease)}'+
    '#sitelive.on{opacity:1}'+
    /* 模型画布：铺满宿主层。**不加 filter** —— 背景是全屏最大的元素，
       任何 filter 都会让整块区域每帧重绘（§134 的成本逻辑同样适用于滤镜链）。 */
    '#sitelive canvas{position:absolute;inset:0;width:100%;height:100%;display:block}'+
    /* 下沿柔化：只在底部 26% 铺一层从透明到背景色的渐变，
       让"人物站在页面下沿"这件事读起来像景深，而不是像被裁掉。
       ⚠️ 用 --bg（页面底色 token）而不是字面色，昼夜两套主题自动跟着走。 */
    '#sitelive::after{content:"";position:absolute;left:0;right:0;bottom:0;height:26%;'+
      'pointer-events:none;background:linear-gradient(180deg,transparent,'+
      'color-mix(in srgb,var(--bg) 88%,transparent))}'+
    /* 上沿同理但更浅：顶栏是玻璃的，模型从头顶穿过去会让标题读不清 */
    '#sitelive::before{content:"";position:absolute;left:0;right:0;top:0;height:18%;'+
      'pointer-events:none;background:linear-gradient(0deg,transparent,'+
      'color-mix(in srgb,var(--bg) 72%,transparent))}'+
    /* 有动态背景时，水面层与光晕让位（与 has-sitebg 同一套逻辑，但不新增类名：
       复用 has-sitebg 会让 body 的 background-image 规则也生效，那是静态图的路径）。
       ⇒ 这里单独给一个 has-livebg，只做"藏水面 canvas + 压光晕"两件事。 */
    'html.has-livebg #bgfx canvas{display:none}'+
    'html.has-livebg #bgfx .glow,html.has-livebg .amb i{opacity:.2}';
  document.head.appendChild(s);
}

/* ───────────────────── 脚本懒加载 ───────────────────── */
function loadOnce(src){
  var hit=document.querySelector('script[data-sbl="'+src+'"]');
  if(hit) return hit._p;
  var el=document.createElement('script'); el.src=src; el.dataset.sbl=src;
  el._p=new Promise(function(rs,rj){ el.onload=rs; el.onerror=function(){ rj(new Error('脚本加载失败 '+src)); }; });
  document.body.appendChild(el);
  return el._p;
}

/* ───────────────────── 宿主层 ───────────────────── */
var host=null, cvs=null;
function ensureHost(){
  if(host&&host.isConnected) return host;
  host=document.getElementById('sitelive');
  if(!host){
    host=document.createElement('div');
    host.id='sitelive'; host.setAttribute('aria-hidden','true');
    /* 插到 body 最前面：比 #bgfx 还早，这样水面（若还在）也在它上面，
       视觉顺序 = 动态背景 < 水面 < 内容。有动态背景时水面本来就被藏了，
       这个顺序只是防"将来水面恢复了又盖住动态背景"。 */
    document.body.insertBefore(host, document.body.firstChild||null);
  }
  return host;
}
function ensureCanvas(){
  ensureHost();
  if(cvs&&cvs.isConnected) return cvs;
  cvs=document.createElement('canvas');
  cvs.setAttribute('aria-hidden','true');
  host.appendChild(cvs);
  return cvs;
}
function show(){
  if(host) requestAnimationFrame(function(){ host.classList.add('on'); });
}
function hide(){ if(host) host.classList.remove('on'); }

/* ───────────────────── 实例管理 ───────────────────── */
/* 单一活动实例。换背景 = 先 stop() 再起新的；两条路径都必须可重入，
   因为 sitebgchange 可能在模型还在加载时就又触发一次（用户连点两下换背景）。 */
var cur=null;      // {kind, cancelled, stop()}
var seq=0;
var lastErr=null;  // 最近一次失败原因（诊断出口，探针/控制台都能读）
/* 帧计数：判断"画布真的在动"唯一可靠的证据。
   ⚠️ 别用「从外面 drawImage 采样两次比像素」—— WebGL 的 preserveDrawingBuffer 默认是 false，
      drawImage 读到的往往是**空的或旧的**后备缓冲，两次采样当然一样 ⇒ 假的"没在画"（本轮踩过）。
      这里由渲染循环自己累加，探针读前后差值即可。 */
var frames=0;

function stop(){
  var c=cur; cur=null;
  if(!c) return;
  c.cancelled=true;
  try{ c.stop(); }catch(e){ console.warn('[SiteBgLive] 销毁失败', e); }
  if(cvs){ try{ cvs.remove(); }catch(e){} cvs=null; }
  hide();
  document.documentElement.classList.remove('has-livebg');
}

/* ───────────────────── Live2D ─────────────────────
   取景：用 internalModel.width/height（Cubism 画布单位），**不用 mdl.width**
   （那是渲染包围盒，个别模型有巨型离屏 quad 会把它撑到几百万像素）。
   居中对齐，缩放 = contain 到视口高度 × 0.94，让人物"站满"而不是"缩在中间"。
   ⚠️ 不调 contentBox()：那是弹窗查看器为了"去掉画布留白"写的，依赖逐 drawable
      读顶点，269 个模型里有些在首帧还没算好。背景只要"整张画布居中"就够，
      画布自带的留白反而让构图更松弛 —— 这正是"柔和铺底"要的效果。 */
async function startLive2D(v, myseq){
  var vdir='./vendor/live2d/';
  await loadOnce(vdir+'live2dcubismcore.min.js');
  await loadOnce(vdir+'pixi.min.js');
  await loadOnce(vdir+'pixi-live2d-display-cubism4.min.js');
  if(seq!==myseq) return;
  if(!(window.PIXI&&window.Live2DCubismCore&&PIXI.live2d&&PIXI.live2d.Live2DModel))
    throw new Error('Live2D 运行时未就绪');

  var cv=ensureCanvas();
  var app=new PIXI.Application({ view:cv, backgroundAlpha:0, antialias:true,
    width:window.innerWidth, height:window.innerHeight, resolution:Math.min(2,window.devicePixelRatio||1),
    autoDensity:true });
  /* ⚠️ 模型路径必须带 PREFIX（= 页面上一层的 Output/），否则 404 会被库报成
     "Network error" 而不告诉你是哪个文件 —— 见 PREFIX() 那段注释。 */
  var modelUrl=PREFIX()+v.model+'/'+v.base+'.model3.json';
  var mdl=await PIXI.live2d.Live2DModel.from(modelUrl,
    { autoInteract:false });                    // ← 用户明确要求：背景没有交互
  if(seq!==myseq){ try{ app.destroy(true,{children:true,baseTexture:true,texture:true}); }catch(e){} return; }

  app.stage.addChild(mdl);
  /* pixi 自带 ticker 在跑：用一个轻量回调数帧（比探针从外面采样可靠，见 frames 注释） */
  app.ticker.add(function(){ frames++; });

  /* Cubism 画布尺寸（像素空间，与 model 本地坐标同尺度） */
  var im=mdl.internalModel;
  var natW=(im&&im.width>1?im.width:1), natH=(im&&im.height>1?im.height:1);

  function fit(){
    var cw=window.innerWidth, ch=window.innerHeight;
    app.renderer.resize(cw,ch);
    /* contain 到高度、留 6% 余量；宽度不够时改用宽度基准（横屏极窄的情况） */
    var k=Math.min(ch*0.94/natH, cw*1.1/natW);
    mdl.scale.set(k);
    /* 底部对齐 + 水平居中：人物"站"在屏幕下沿，头顶留白给顶栏。
       ⚠️ pixi 的 y 轴向下，模型本地原点在**左上**，所以锚点用 natH 而不是 natH/2。 */
    mdl.x=cw/2 - (natW/2)*k;
    mdl.y=ch - natH*k*1.02;
  }
  fit();
  var onR=fit; window.addEventListener('resize', onR);

  /* idle 动作：让模型"活着"。取第一个存在的组，不指定具体动画 ——
     各模型的动作表差异极大，硬编码名字必然有一半放不出来。
     ⚠️ 这条要让库自己循环：pixi-live2d-display 的 startRandomMotion 带循环参数，
        默认 true。失败就算了（静态站姿也是合格的背景）。 */
  try{
    var mm=im.motionManager;
    var groups=Object.keys((mm&&mm.definitions)||{});
    var idle=['idle','main','home'].filter(function(g){ return groups.indexOf(g)>=0; })[0];
    if(idle) mm.startRandomMotion(idle, 3);
  }catch(e){ /* 没有动作组：站姿即成品 */ }

  show();
  document.documentElement.classList.add('has-livebg');

  return {
    cancelled:false,
    stop:function(){
      window.removeEventListener('resize', onR);
      try{ app.destroy(true,{children:true,baseTexture:true,texture:true}); }catch(e){}
    }
  };
}

/* ───────────────────── Spine ─────────────────────
   与弹窗查看器的取舍不同：
     · **只加载主层**（parts[0]），不加载全部 parts —— 背景不需要背景层/前景层的分层细节，
       而每多加载一层就多一次 skel 解析 + 若干页纹理上传。首页 `__spLayers` 的教训：
       分层是为"诊断哪一层画了什么"服务的，背景没有这个问题。
     · **不做 skin 覆盖度选举**：那要跑 6 个动画 × 3 个时间点 × 全槽位，约 100~300ms。
       背景用 data.skins[0] 或默认 skin 就够 —— 除非模型只有命名 skin（这时附件会是 null），
       所以退而求其次：选**附件覆盖槽位最多**的那一个，但只测 setup pose（一次，不循环动画），
       成本降到几毫秒。
     · **不做背景巨幕剔除**：全身居中铺底，巨幕如果存在，正好当它的"氛围底"，
       只是缩放基准要按**画布可见内容**算，所以这里用 setup pose 的附件并集，
       并丢掉"面积大得离谱且附件数极少"的层（复用 §105 的两条 AND 判据，但只在单层内判）。 */
async function startSpine(v, myseq){
  await loadOnce('./vendor/spine/spine-all.js');
  if(seq!==myseq) return;
  if(!window.spine) throw new Error('Spine 运行时未就绪');

  var cv=ensureCanvas();
  var base=v.folder+'/';
  var path=PREFIX()+'Spine_v2/'+base;

  var glctx=new spine.webgl.ManagedWebGLRenderingContext(cv,{alpha:true,premultipliedAlpha:true});
  var scene=new spine.webgl.SceneRenderer(cv,glctx,false);
  var gl=glctx.gl;
  gl.clearColor(0,0,0,0); gl.enable(gl.BLEND); gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);

  /* ── 加载一个部件 ── */
  async function loadPart(pn){
    var skelR=await fetch(path+pn+'.skel'); if(!skelR.ok) throw new Error('skel '+pn+' 404');
    var bytes=new Uint8Array(await skelR.arrayBuffer());
    var atlasR=await fetch(path+pn+'.atlas'); if(!atlasR.ok) throw new Error('atlas '+pn+' 404');
    var atlasTxt=await atlasR.text();
    var pageNames=[];
    atlasTxt.split('\n').forEach(function(ln){
      var t=(ln||'').replace(/\r$/,'');
      if(/^[A-Za-z0-9_].*\.(png|jpg)$/i.test(t)&&!ln.startsWith(' ')&&!ln.startsWith('\t')&&!t.includes(':'))
        pageNames.push(t);
    });
    var textures={};
    for(var i=0;i<pageNames.length;i++){
      var pgn=pageNames[i], img=new Image(); img.crossOrigin='anonymous';
      await new Promise(function(rs,rj){ img.onload=rs; img.onerror=function(){ rj(new Error('tex '+pgn)); }; img.src=path+pgn; });
      textures[pgn]=new spine.webgl.GLTexture(glctx,img,false);
    }
    var texLoader=function(p){
      for(var q in textures) if(q===p||(''+p).endsWith(q)||q.endsWith(''+p)) return textures[q];
      return textures[pageNames[0]];
    };
    var atlas=new spine.TextureAtlas(atlasTxt,texLoader);
    var ofind=atlas.findRegion.bind(atlas);
    atlas.findRegion=function(n){ var r=ofind(n); if(r) return r; var t=(''+n).trim(); return t!==n?ofind(t):r; };

    var loader=new spine.AtlasAttachmentLoader(atlas);
    var data = bytes[0]===0x7B
      ? new spine.SkeletonJson(loader).readSkeletonData(new TextDecoder().decode(bytes))
      : new spine.SkeletonBinary(loader).readSkeletonData(bytes);
    return { data:data, textures:textures };
  }

  /* ── 选 skin：只要 setup pose 下附件最多的那一个（几毫秒） ── */
  function pickSkin(data){
    var names=(data.skins||[]).map(function(k){ return k.name; });
    if(!names.length) return null;
    var best=null, bestN=-1;
    var probe=names.slice(0,24);                 // 上限 24 个：极少数模型 skin 表很长
    for(var i=0;i<probe.length;i++){
      try{
        var t=new spine.Skeleton(data);
        t.setSkin(data.findSkin(probe[i]));
        t.setSlotsToSetupPose(); t.setBonesToSetupPose(); t.updateWorldTransform();
        var n=0;
        for(var j=0;j<t.slots.length;j++) if(t.slots[j].getAttachment()) n++;
        if(n>bestN){ bestN=n; best=probe[i]; }
      }catch(e){}
    }
    return best;
  }

  /* ── 附件并集（世界坐标）：用来定缩放，同一套"剔除巨幕"判据 ── */
  function extents(sk){
    var arr=[];
    for(var i=0;i<sk.slots.length;i++){
      var slot=sk.slots[i], a=slot.getAttachment();
      if(!a||!slot.bone||!slot.bone.active) continue;
      var col=(slot.data&&slot.data.color)||{r:1,g:1,b:1,a:1};
      if(col.a<=0.001) continue;
      var vtt,c;
      try{
        if(a instanceof spine.RegionAttachment){ vtt=spine.Utils.newFloatArray(8); c=8; a.computeWorldVertices(slot.bone,vtt,0,2); }
        else if(a instanceof spine.MeshAttachment&&a.worldVerticesLength){ c=a.worldVerticesLength; vtt=spine.Utils.newFloatArray(c); a.computeWorldVertices(slot,0,c,vtt,0,2); }
        else continue;
      }catch(e){ continue; }
      var x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;
      for(var j=0;j<c;j+=2){ if(vtt[j]<x0)x0=vtt[j]; if(vtt[j]>x1)x1=vtt[j]; if(vtt[j+1]<y0)y0=vtt[j+1]; if(vtt[j+1]>y1)y1=vtt[j+1]; }
      if(x1<x0||y1<y0) continue;
      arr.push([x0,y0,x1,y1]);
    }
    return arr;
  }
  function unionOf(list){
    if(!list.length) return null;
    var r=[1e9,1e9,-1e9,-1e9];
    list.forEach(function(b){
      if(b[0]<r[0])r[0]=b[0]; if(b[1]<r[1])r[1]=b[1];
      if(b[2]>r[2])r[2]=b[2]; if(b[3]>r[3])r[3]=b[3];
    });
    return r;
  }

  var parts=(v.parts&&v.parts.length)?v.parts:[v.folder];
  var main=await loadPart(parts[0]);
  if(seq!==myseq){ Object.keys(main.textures).forEach(function(k){ try{ main.textures[k].dispose(); }catch(e){} }); return; }

  var data=main.data;
  var skinName=pickSkin(data);
  var sk=new spine.Skeleton(data);
  try{ if(skinName!==null) sk.setSkin(data.findSkin(skinName)); }catch(e){}
  sk.setSlotsToSetupPose(); sk.setBonesToSetupPose(); sk.updateWorldTransform();

  var anims=(data.animations||[]).filter(function(a){ return a.duration>0.05; });
  var st=new spine.AnimationState(new spine.AnimationStateData(data));

  /* 选一个"入场/常态"动作：优先 normal → idle → home → 第一个非空。
     ⚠️ 首页注释里的教训：动画名 `1..N` 多是 0 秒空占位，所以上面先按 duration 过滤掉了。 */
  var prefer=['normal','idle','home','login'];
  var pick=null;
  for(var pi=0;pi<prefer.length&&!pick;pi++)
    pick=anims.filter(function(a){ return (a.name||'')===prefer[pi]; })[0];
  if(!pick&&anims.length) pick=anims[0];
  if(pick){ try{ st.setAnimation(0, pick.name||pick, true); }catch(e){} }

  /* ── 定缩放：按附件并集，但剔掉"又大又空"的巨幕后重算 ── */
  var boxes=extents(sk);
  var all=unionOf(boxes);
  var useBox=all;
  if(boxes.length>2&&all){
    var allArea=Math.max(1,(all[2]-all[0])*(all[3]-all[1]));
    var kept=boxes.filter(function(b){
      var a=(b[2]-b[0])*(b[3]-b[1]);
      /* 单个附件占全图面积 70% 以上 ⇒ 它要么是背景板、要么是整屏色板 */
      return a < allArea*0.7;
    });
    if(kept.length>=1){
      var u=unionOf(kept);
      if(u&&(u[2]-u[0])>1&&(u[3]-u[1])>1) useBox=u;
    }
  }
  var bw=(useBox?useBox[2]-useBox[0]:600), bh=(useBox?useBox[3]-useBox[1]:900);
  var cx=(useBox?(useBox[0]+useBox[2])/2:0), cy=(useBox?(useBox[1]+useBox[3])/2:0);

  var baseScale=1;
  function fit(){
    var cw=window.innerWidth, ch=window.innerHeight;
    cv.width=cw; cv.height=ch;
    scene.resize(); scene.camera.setViewport(cw,ch);   // ⚠️ scene.resize() 不更新相机视口（WF-14 踩过）
    /* 高度占视口 92%，宽度留 8% 余量；Spine 世界 y 轴向上 ⇒ cy 用「上边」计算 */
    baseScale=Math.min(ch*0.92/bh, cw*0.94/bw);
  }
  fit();
  var onR=fit; window.addEventListener('resize', onR);

  var raf=0, last=performance.now();
  var cancelled=false;
  /* ⚠️ 这段调用序列是**逐字对齐首页 `frame()`** 的（index.html 约 2609 行），少一步就黑屏：
       gl.clear → camera.position.set → camera.zoom → **camera.update()** → **scene.begin()**
       → drawSkeleton → **scene.end()**
     三个最容易漏的点：
       ① `camera.zoom` 存的是**倒数**（首页 `scene.camera.zoom=1/(base1*zoom)`），
          直接塞正数会让画面缩成一个点或胀到看不见；
       ② `camera.update()` 不调的话相机矩阵还是上一帧的（首帧是单位矩阵）；
       ③ `scene.begin()/end()` 是 SceneRenderer 的批处理边界，不包起来 drawSkeleton 什么都不画。
     ——2026-10-20 实测：漏掉 ②③ 时 canvas 会正常挂载、`has-livebg` 也生效，
       但一帧都不推进（rAF 里 scene.render 抛错被外层吞掉），症状是"背景是空的但没报错"。 */
  function loop(ts){
    if(cancelled) return;
    var dt=Math.min(0.05,(ts-last)/1000||0); last=ts;
    try{
      st.update(dt); st.apply(sk); sk.updateWorldTransform();
      gl.clear(gl.COLOR_BUFFER_BIT);
      scene.camera.position.set(cx, cy, 0);
      scene.camera.zoom = 1/baseScale;
      scene.camera.update();
      scene.begin();
      scene.drawSkeleton(sk, true);
      scene.end();
      frames++;
    }catch(e){
      /* 只在第一次报：每帧都 warn 会把控制台刷满，反而掩盖真正的原因 */
      if(!loop._err){ loop._err=true; console.warn('[SiteBgLive] Spine 绘制失败：', e); }
    }
    raf=requestAnimationFrame(loop);
  }
  raf=requestAnimationFrame(loop);
  show();
  document.documentElement.classList.add('has-livebg');

  return {
    cancelled:false,
    stop:function(){
      cancelled=true;
      if(raf) cancelAnimationFrame(raf);
      window.removeEventListener('resize', onR);
      Object.keys(main.textures).forEach(function(k){ try{ main.textures[k].dispose(); }catch(e){} });
    }
  };
}

/* ───────────────────── 资源前缀 ─────────────────────
   ⚠️ 这个前缀**不能瞎猜**，也不能写成 './'：
   页面住在 `Output/gallery_v2/`，而 `Live2D/` `Spine_v2/` 这些资源目录在**上一层** `Output/`
   （首页 index.html 里写死的就是 `const P='../'`）。写成 './' 会让
   `./Live2D/x/x.model3.json` → `/gallery_v2/Live2D/x/x.model3.json` → 404，
   而 pixi 的 XHRLoader 把 404 报成一句极其含糊的 `Network error`（不说是哪个文件），
   排查时会一路怀疑到库、wasm、跨域上去。
   ⇒ 派生方式：取当前页面 URL 的目录，再拼 '../'。这样无论页面放在哪层都对；
      `file:` 协议下同样成立（同一套相对路径语义）。
   `vendor/` 是例外：它在页面同级（`gallery_v2/vendor/`），所以脚本加载用 './vendor/'。 */
var _prefix=null;
function PREFIX(){
  if(_prefix!=null) return _prefix;
  try{
    var u=new URL('.', location.href);
    _prefix=new URL('../', u).href;
  }catch(e){ _prefix='../'; }
  return _prefix;
}

/* ───────────────────── 入口 ───────────────────── */
/* 判断当前值是不是动态类型。`v.kind` 由 favorites.js 写入。 */
function isLive(v){ return !!v && (v.kind==='spine'||v.kind==='live2d'); }

async function sync(){
  var v = (window.SiteBg&&SiteBg.get)?SiteBg.get():null;
  stop();
  if(!isLive(v)) return;

  /* 站用背景是 id 唯一标识：kind+key 相同就不重建（避免 renderActs 反复触发时闪一下） */
  var myseq=++seq;
  ensureHost();
  lastErr=null;
  var my={ cancelled:false, stop:function(){} };
  cur=my;                                  // 先占位，避免加载期间又一次 sync 起两份
  try{
    var inst = v.kind==='live2d' ? await startLive2D(v,myseq) : await startSpine(v,myseq);
    if(seq!==myseq||!inst){ if(inst)try{inst.stop()}catch(e){} return; }
    cur=inst;
  }catch(e){
    lastErr=String((e&&e.stack)||e||'unknown');
    if(seq===myseq){
      console.warn('[SiteBgLive] 动态背景加载失败，退回静态底：', e);
      /* 失败要可见地退回，不能留一块黑屏。摘掉 canvas + 去掉 has-livebg，
         页面自然回到原来的渐变/水面。 */
      try{ if(cvs){ cvs.remove(); cvs=null; } }catch(_){}
      document.documentElement.classList.remove('has-livebg');
      hide();
      cur=null;
    }
  }
}

/* 事件：favorites.js 的 SiteBg.set/clear 都会派发 sitebgchange */
document.addEventListener('sitebgchange', sync);
/* 首屏：脚本可能在 DOMContentLoaded 之后才执行，直接跑一次 */
function boot(){
  css();
  if(document.body) sync();
  else document.addEventListener('DOMContentLoaded', function(){ css(); sync(); });
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', boot);
else boot();

window.SiteBgLive={ sync:sync, stop:stop, isLive:isLive,
  stats:function(){ return { kind:cur?(SiteBg.get()||{}).kind:null, hasCanvas:!!(cvs&&cvs.isConnected),
    host:!!(host&&host.isConnected), live:document.documentElement.classList.contains('has-livebg'),
    err:lastErr, frames:frames }; } };
})();
