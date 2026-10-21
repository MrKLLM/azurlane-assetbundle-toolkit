/* 三页共用的加载/等待层：主页、背景库、音乐库。
   目标不是再做一个转圈图标，而是把"现在在等什么、等到哪一步"说清楚：
   · 首屏：一张静态的纸面遮罩 + 墨滴呼吸，数据就绪后由页面调用 bootDone() 收起；
   · 取数据：顶部 3px 墨线，有 Content-Length 时按真实字节推进，没有才退化为不定态；
   · 局部等待：waitHTML() 生成三颗墨滴 + 文案，嵌在查看器/播放器自己的提示位里。

   ⚠️ 约定：本模块**不猜**进度。拿不到总字节/N 时宁可显示不定态，也不拿假百分比糊。
   页面必须自己调用 bootDone()（成功或失败都要），否则遮罩会挡住错误信息。 */
(function(){
'use strict';
if(window.InkLoad) return;

var bootEl=null, bootTimer=null;
var bar=null, fill=null, lab=null, barT=null;

function css(){
  if(document.getElementById('inkloadcss')) return;
  var s=document.createElement('style'); s.id='inkloadcss';
  s.textContent=
    /* ── 首屏遮罩：纸面 + 三滴逐渐洇开的墨。z-index 高于顶栏、低于弹窗。 ── */
    '#bootveil{position:fixed;inset:0;z-index:200;display:flex;align-items:center;justify-content:center;'+
      'background:color-mix(in srgb,var(--bg,#f3f6fa) 90%,transparent);'+
      '-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);'+
      'transition:opacity .5s var(--ease-ios,ease)}'+
    '#bootveil.off{opacity:0;pointer-events:none}'+
    '.bv-inner{display:flex;flex-direction:column;align-items:center;gap:12px;text-align:center}'+
    '.bv-ink{display:flex;align-items:flex-end;gap:9px;height:22px}'+
    '.bv-ink i{width:9px;height:9px;border-radius:50%;background:var(--brand-d,#3d87d4);'+
      'opacity:.35;animation:inkbreathe 1.45s var(--ease-ios,ease) infinite}'+
    '.bv-ink i:nth-child(2){animation-delay:.16s;width:12px;height:12px;opacity:.55}'+
    '.bv-ink i:nth-child(3){animation-delay:.32s}'+
    '@keyframes inkbreathe{0%,100%{transform:translateY(0) scale(.82);opacity:.28}'+
      '45%{transform:translateY(-9px) scale(1.08);opacity:.95}}'+
    '.bv-t{font:600 15px/1.4 "Noto Serif SC",serif;color:var(--title,var(--txt,#243040));'+
      'letter-spacing:.04em;margin:0}'+
    '.bv-s{font:11px/1.6 "Segoe UI","Microsoft YaHei",sans-serif;color:var(--dim,#7c8da4);margin:0}'+
    '.bv-line{width:150px;height:1px;background:color-mix(in srgb,var(--brand,#5fb0ef) 18%,transparent);'+
      'position:relative;overflow:hidden;margin-top:2px}'+
    '.bv-line::after{content:"";position:absolute;inset:0;transform:translateX(-100%);'+
      'background:linear-gradient(90deg,transparent,var(--brand-d,#3d87d4),transparent);'+
      'animation:inksweep 1.8s var(--ease-ios,ease) infinite}'+
    '@keyframes inksweep{to{transform:translateX(100%)}}'+
    '.bv-skip{display:none;margin-top:4px;padding:5px 12px;border:1px solid var(--chip-line,#d9e2ee);'+
      'border-radius:999px;background:transparent;color:var(--txt2,#4a5a70);'+
      'font:11px/1.4 "Segoe UI","Microsoft YaHei",sans-serif;cursor:pointer}'+
    '.bv-skip.on{display:inline-block}'+
    '.bv-skip:hover{border-color:var(--brand,#5fb0ef);color:var(--brand-d,#3d87d4)}'+
    /* ── 顶部真实进度：一根墨线 + 一枚小玻璃牌。 ── */
    '#inkbar{position:fixed;top:0;left:0;right:0;height:3px;z-index:150;pointer-events:none;'+
      'opacity:0;transition:opacity .22s ease}'+
    '#inkbar.on{opacity:1}'+
    '#inkbar .fill{height:100%;transform:scaleX(0);transform-origin:0 50%;'+
      'background:linear-gradient(90deg,var(--brand,#5fb0ef),var(--brand-d,#3d87d4));'+
      'box-shadow:0 0 12px color-mix(in srgb,var(--brand,#5fb0ef) 55%,transparent);'+
      'transition:transform .18s ease}'+
    '#inkbar.indet .fill{width:34%;transform:none;animation:inkslide 1.15s var(--ease-ios,ease) infinite}'+
    '@keyframes inkslide{from{transform:translateX(-110%)}to{transform:translateX(330%)}}'+
    '#inkbar .lab{position:fixed;top:9px;left:50%;transform:translateX(-50%);'+
      'font:11px/1.4 "Segoe UI","Microsoft YaHei",sans-serif;color:var(--txt2,#4a5a70);'+
      'background:color-mix(in srgb,var(--panel,#fff) 78%,transparent);'+
      'border:1px solid color-mix(in srgb,var(--glass-line,#fff) 85%,transparent);'+
      'border-radius:999px;padding:4px 11px;white-space:nowrap;'+
      '-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);'+
      'box-shadow:0 3px 14px color-mix(in srgb,var(--brand,#5fb0ef) 10%,transparent)}'+
    '#inkbar.bad .fill{background:var(--fail,#d04444)}'+
    '#inkbar.bad .lab{color:var(--fail,#d04444)}'+
    /* ── 局部等待：三颗墨滴 + 文案，可直接塞进 .note / .spine-bar。 ── */
    '.inkwait{display:inline-flex;align-items:center;gap:7px;vertical-align:middle}'+
    '.inkwait i{width:5px;height:5px;border-radius:50%;background:currentColor;opacity:.35;'+
      'animation:inkdot 1.2s var(--ease-ios,ease) infinite}'+
    '.inkwait i:nth-child(2){animation-delay:.14s}.inkwait i:nth-child(3){animation-delay:.28s}'+
    '@keyframes inkdot{0%,100%{transform:translateY(0);opacity:.3}45%{transform:translateY(-4px);opacity:.95}}'+
    '.inkwait em{font-style:normal}'+
    '@media (prefers-reduced-motion:reduce){'+
      '.bv-ink i,.inkwait i{animation:none;opacity:.7}'+
      '.bv-line::after,#inkbar.indet .fill{animation:none}}';
  document.head.appendChild(s);
}

function ensureBoot(){
  if(bootEl) return bootEl;
  bootEl=document.getElementById('bootveil');
  if(!bootEl){
    bootEl=document.createElement('div'); bootEl.id='bootveil';
    bootEl.innerHTML='<div class="bv-inner"><div class="bv-ink"><i></i><i></i><i></i></div>'+
      '<p class="bv-t">正在展开资产…</p><p class="bv-s">读取索引与缩略图</p>'+
      '<span class="bv-line"></span>'+
      '<button class="bv-skip" type="button">仍然进入</button></div>';
    (document.body||document.documentElement).appendChild(bootEl);
  }
  /* 5 秒后给一个显式出口：首屏再重，也不该让用户只能盯着遮罩。
     ⚠️ 页面里的 #bootveil 是静态 HTML，不保证带 .bv-skip；必须在这里补，不能只在
     “创建遮罩”的分支里生成（2026-10-22 实测：静态遮罩上按钮永远不出现）。 */
  if(!bootEl.dataset.skipWired){
    bootEl.dataset.skipWired='1';
    var skip=bootEl.querySelector('.bv-skip');
    if(!skip){
      skip=document.createElement('button');
      skip.type='button'; skip.className='bv-skip'; skip.textContent='仍然进入';
      (bootEl.querySelector('.bv-inner')||bootEl).appendChild(skip);
    }
    skip.onclick=function(){ bootDone(); };
    setTimeout(function(){ if(bootEl&&!bootEl.classList.contains('off')) skip.classList.add('on'); },5000);
  }
  return bootEl;
}

function ensureBar(){
  if(bar) return bar;
  bar=document.createElement('div'); bar.id='inkbar';
  bar.innerHTML='<i class="fill"></i><span class="lab"></span>';
  (document.body||document.documentElement).appendChild(bar);
  fill=bar.querySelector('.fill'); lab=bar.querySelector('.lab');
  return bar;
}

function bootDone(){
  var el=ensureBoot();
  if(bootTimer){ clearTimeout(bootTimer); bootTimer=null; }
  if(el.classList.contains('off')) return;
  el.classList.add('off');
  setTimeout(function(){ try{ el.remove(); }catch(e){} bootEl=null; }, 700);
}

function start(text){
  ensureBar(); clearTimeout(barT);
  bar.classList.add('on'); bar.classList.remove('bad','indet');
  bar.classList.toggle('indet',true);
  fill.style.transform='scaleX(0)'; lab.textContent=text||'读取中…';
}

function progress(frac,text){
  ensureBar(); clearTimeout(barT);
  bar.classList.add('on'); bar.classList.remove('bad');
  if(frac==null){ bar.classList.add('indet'); fill.style.transform='scaleX(0)'; }
  else{
    bar.classList.remove('indet');
    frac=Math.max(0,Math.min(1,frac));
    fill.style.transform='scaleX('+frac.toFixed(4)+')';
    if(text) lab.textContent=text+' '+Math.round(frac*100)+'%';
    else lab.textContent=Math.round(frac*100)+'%';
  }
}

function done(text){
  ensureBar(); clearTimeout(barT);
  bar.classList.remove('indet');
  fill.style.transform='scaleX(1)';
  lab.textContent=text||'就绪';
  barT=setTimeout(function(){ bar.classList.remove('on','bad'); }, 520);
}

function fail(text){
  ensureBar(); clearTimeout(barT);
  bar.classList.remove('indet'); bar.classList.add('on','bad');
  lab.textContent=text||'读取失败';
  barT=setTimeout(function(){ bar.classList.remove('on','bad'); }, 4200);
}

function esc(t){
  return String(t).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
  });
}
function waitHTML(text){
  return '<span class="inkwait"><i></i><i></i><i></i><em>'+esc(text||'加载中…')+'</em></span>';
}

/* 只统计"首屏附近"的缩略图：下面的图是 loading=lazy，本来就不该在首屏等。
   complete 的图直接计数；未完成的挂一次 load/error。全部落定后收起墨线。 */
function trackThumbs(root,text){
  if(!root) return;
  var vh=window.innerHeight||800;
  var imgs=[].slice.call(root.querySelectorAll('img')).filter(function(img){
    var r=img.getBoundingClientRect();
    return r.top<vh*1.35&&r.bottom>-vh*.35;
  });
  if(!imgs.length){ done(); return; }
  var total=imgs.length, got=0, seen=new Set();
  start(text||'铺开缩略图');
  progress(0,text||'铺开缩略图');
  /* 懒加载图可能迟迟不触发；8 秒后收起进度，页面本身继续加载，不让顶栏永久挂着。 */
  var guard=setTimeout(function(){ if(got<total) done('缩略图稍后继续'); },8000);
  function one(img){
    if(seen.has(img)) return; seen.add(img); got++;
    progress(got/total,text||'铺开缩略图');
    if(got>=total){ clearTimeout(guard); done('缩略图就绪'); }
  }
  imgs.forEach(function(img){
    if(img.complete){ one(img); return; }
    img.addEventListener('load',function(){one(img);},{once:true});
    img.addEventListener('error',function(){one(img);},{once:true});
  });
}

async function fetchJSON(url,text){
  start(text||'读取索引…');
  try{
    var r=await fetch(url,{cache:'no-store'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    var total=+(r.headers.get('Content-Length')||0);
    var body=r.body;
    if(!body||!total||!body.getReader){
      var j=await r.json(); done(); return j;
    }
    var reader=body.getReader(), chunks=[], got=0;
    for(;;){
      var x=await reader.read();
      if(x.done) break;
      chunks.push(x.value); got+=x.value.length;
      progress(got/total,text||'读取索引');
    }
    var buf=new Uint8Array(got), off=0;
    chunks.forEach(function(c){ buf.set(c,off); off+=c.length; });
    var j2=JSON.parse(new TextDecoder().decode(buf));
    done(); return j2;
  }catch(e){
    fail((text||'读取')+'失败');
    throw e;
  }
}

css();
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',function(){ ensureBoot(); });
else ensureBoot();
/* 兜底：页面脚本真挂了也不能让遮罩永远盖住错误。 */
/* 兜底：页面脚本真挂了也不能让遮罩永远盖住错误。12 秒自动收起，另有一个 5 秒出现的
   「仍然进入」按钮（手动更快）；两个出口都不依赖页面自己的初始化。 */
bootTimer=setTimeout(function(){ if(bootEl&&!bootEl.classList.contains('off')) bootDone(); },12000);

window.InkLoad={bootDone:bootDone,start:start,progress:progress,done:done,fail:fail,
  waitHTML:waitHTML,fetchJSON:fetchJSON,trackThumbs:trackThumbs,el:function(){return bootEl;}};
})();
