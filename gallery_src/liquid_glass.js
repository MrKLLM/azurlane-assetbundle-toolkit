/* 液态玻璃（真折射）共用模块 —— 目前由 bgm.html / backgrounds.html 引用。
   index.html 里是同一套算法的内联副本：那份文件常有并行会话在写，本轮不去动它，
   等它空下来再把首页也切到这里（切换点：删掉首页 <script> 里 LG 那一段 + 加一行 <script src>）。

   为什么非自己画法线图不可：挂在 backdrop-filter 上的 SVG 滤镜，它的 SourceGraphic 就是
   「身后那张已经合成好的背景图」——滤镜拿不到元素自己的形状。所以那一圈的坡度只能预先按
   元素的实测尺寸算成一张图（R=横向推多少、G=纵向推多少），再用 feImage 喂给 feDisplacementMap。
   CSS 模糊永远推不动像素，这就是"看着像毛玻璃不像玻璃"的物理原因。

   ⚠️ 两条硬约束（都是实测换来的，别绕过）：
   1) **被 3D 旋转的盒子里不许挂 mask + backdrop-filter**：祖先 rotateX/rotateY 一非 0，
      Chrome 就丢掉那层遮罩，模糊铺满整盒（§136）。本模块只往从不旋转的元素上挂；
      而且法线图中间是平的（不推像素），所以**整盒挂滤镜 = 只有边上一圈会动**，不需要遮罩。
   2) 成本单位是**同时存在几个不同的滤镜**，不是半径/面积/链长：桶数上限 max=2，
      按粗粒度归并（首页实测 5 桶 83ms vs 2 桶 30ms）。别改回精确分桶。 */
(function(){
'use strict';
var NS='http://www.w3.org/2000/svg', XLINK='http://www.w3.org/1999/xlink';
var LG={ on:!!(window.CSS&&CSS.supports&&CSS.supports('backdrop-filter','blur(1px) url(#lgprobe)')),
         svg:null, buckets:[], max:2, gen:0, cv:null, mpx:96, targets:[] };
if(LG.on) document.documentElement.classList.add('lg');

function tok(){
  var cs=getComputedStyle(document.documentElement);
  function num(n,d){ var v=parseFloat(cs.getPropertyValue(n)); return isFinite(v)?v:d; }
  LG.mpx=Math.max(16,num('--lg-mpx',96));
  return {depth:num('--lg-depth',26), ring:num('--lg-ring',12), rad:num('--r-card',16)};
}
/* 圆角矩形带符号距离场：中心原点，bx/by 是已扣掉圆角的半宽/半高；负值在内部 */
function sdf(x,y,bx,by,r){
  var dx=Math.abs(x)-bx, dy=Math.abs(y)-by;
  return Math.min(Math.max(dx,dy),0)+Math.sqrt(dx*dx+dy*dy)-r;   // Math.hypot 同值，取兼容性
}
function mapURI(w,h,rad,ring){
  w=Math.max(8,Math.round(w)); h=Math.max(8,Math.round(h));
  rad=Math.max(0,Math.min(rad,Math.min(w,h)/2-0.5));
  /* 图按 CSS 空间算、再降采样落盘：feImage 会把它拉伸铺满滤镜区，所以低分辨率不改变环的位置，
     只是让坡度更平滑。⚠️ 梯度必须在 CSS 单位下差分——先在图空间缩小坐标、再用 1 图像素当步长，
     会把坡度按缩放比一起缩小，等于偷偷改了折射强度。 */
  var s=Math.min(1, LG.mpx/Math.max(w,h));
  var mw=Math.max(8,Math.round(w*s)), mh=Math.max(8,Math.round(h*s));
  var cv=LG.cv||(LG.cv=document.createElement('canvas'));
  cv.width=mw; cv.height=mh;
  var ctx=cv.getContext('2d'), im=ctx.createImageData(mw,mh), px=im.data;
  var bx=w/2-rad, by=h/2-rad, inv=1/Math.max(1,ring);
  for(var j=0;j<mh;j++){ var cy=(j+0.5)/s-h/2;
    for(var i=0;i<mw;i++){ var cx=(i+0.5)/s-w/2;
      var e=-sdf(cx,cy,bx,by,rad);                 // 到边框的内距离
      var t=e<=0?0:(e<ring?1-e*inv:0);             // 环带内 1→0，带外不推
      var nx=0, ny=0;
      if(t>0){ nx=(sdf(cx+1,cy,bx,by,rad)-sdf(cx-1,cy,bx,by,rad))*0.5;
               ny=(sdf(cx,cy+1,bx,by,rad)-sdf(cx,cy-1,bx,by,rad))*0.5; }
      var k=((j*mw+i)<<2);
      px[k]=128+nx*t*127; px[k+1]=128+ny*t*127; px[k+2]=128; px[k+3]=255;
    } }
  ctx.putImageData(im,0,0);
  return cv.toDataURL('image/png');
}
function defs(){
  if(LG.svg) return LG.svg;
  var s=document.createElementNS(NS,'svg');
  s.setAttribute('aria-hidden','true');
  s.style.cssText='position:absolute;width:0;height:0;overflow:hidden';
  document.body.appendChild(s);
  return LG.svg=s;
}
function build(id,w,h,rad,ring,depth){
  var f=document.createElementNS(NS,'filter');
  f.setAttribute('id',id);
  /* 滤镜区域往外扩：位移要从元素外面取像素，贴着边取就会被裁成一条糊带 */
  f.setAttribute('x','-16%'); f.setAttribute('y','-16%');
  f.setAttribute('width','132%'); f.setAttribute('height','132%');
  var fi=document.createElementNS(NS,'feImage');
  fi.setAttribute('x','0'); fi.setAttribute('y','0');
  fi.setAttribute('width',String(w)); fi.setAttribute('height',String(h));
  fi.setAttribute('preserveAspectRatio','none'); fi.setAttribute('result','n');
  var uri=mapURI(w,h,rad,ring);
  fi.setAttribute('href',uri); fi.setAttributeNS(XLINK,'xlink:href',uri);
  var dm=document.createElementNS(NS,'feDisplacementMap');
  dm.setAttribute('in','SourceGraphic'); dm.setAttribute('in2','n');
  /* 位移 = scale×(通道/255 − 0.5)，图里峰值是 ±127 ⇒ 最大推开 scale/2 像素 */
  dm.setAttribute('scale',String(depth*2));
  dm.setAttribute('xChannelSelector','R'); dm.setAttribute('yChannelSelector','G');
  f.appendChild(fi); f.appendChild(dm); defs().appendChild(f);
}
/* 桶按粗粒度归并（见上面约束 2）：feImage 是拉伸铺满滤镜区的，尺寸差十几像素只会让环跟着
   缩放几个百分点，不会跑位。 */
function pick(kind,w,h,rad,ring,depth){
  var key=kind+'|'+Math.round(w/24)+'|'+Math.round(h/48)+'|'+Math.round(depth);
  for(var i=0;i<LG.buckets.length;i++) if(LG.buckets[i].key===key) return LG.buckets[i].id;
  if(LG.buckets.length>=LG.max){
    var best=null;
    for(var j=0;j<LG.buckets.length;j++){ var b=LG.buckets[j];
      var d=Math.abs(b.h-h)+Math.abs(b.w-w)*2;
      if(!best||d<best.d) best={d:d,id:b.id}; }
    return best?best.id:null;
  }
  var id='lg'+(++LG.gen);
  build(id,w,h,rad,ring,depth);
  LG.buckets.push({key:key,id:id,w:w,h:h});
  return id;
}
/* mount(el, o)：o.cls 是要加的类名（CSS 里那条 html.lg .xxx 规则消费 --lgf）；
   o.ring / o.radius 覆盖 token，按 el **自己的盒子**算。
   （原来还有一个 o.band 分支，按 el 的 ::before 高度算 —— 那是页头那条边墙用的，
     整条装置已于 §138 退役，所以分支一起删了，别照着 git 历史原样接回来。）
   ⚠️ 必须先写 --lgf 再加类：反了会让 backdrop-filter 在空变量上解析失败，
      而"自定义属性解析失败"是**整条声明作废**，那一圈会整个消失（不是退化成模糊）。 */
function mount(el,o){
  o=o||{};
  if(!LG.on||!el) return false;
  var T=tok(), r=el.getBoundingClientRect(), cls=o.cls||'lgr';
  var w=Math.round(r.width), h=Math.round(r.height);
  var rad=o.radius!=null?o.radius:T.rad, ring=o.ring!=null?o.ring:T.ring;
  if(w<8||h<8){ el.classList.remove(cls); return false; }
  var id=pick(o.kind||'p',w,h,rad,ring,T.depth);
  if(!id){ el.classList.remove(cls); return false; }
  el.style.setProperty('--lgf','url(#'+id+')');
  el.classList.add(cls);
  if(LG.targets.indexOf(el)<0) LG.targets.push(el);
  return true;
}
/* 尺寸变了（换窗口、播放器浮出/收起）就把挂过的元素重算一遍 */
function refresh(){
  LG.buckets.length=0;
  if(LG.svg) while(LG.svg.firstChild) LG.svg.removeChild(LG.svg.firstChild);
  var t=LG.targets.slice(); LG.targets.length=0;
  for(var j=0;j<t.length;j++){ if(t[j].isConnected) mount(t[j], t[j].__lg||null); }
}
function auto(el,o){ if(el){ el.__lg=o; mount(el,o); } return el; }

/* 这里原来还有一套 rim()：把页头那条边墙做成栏的**兄弟节点** `.navrim`
   （挂在栏的子元素上时实测不落像素 —— 栏体自己挂着 backdrop-filter，它本身就是 backdrop root，
   子元素的后备景进不到滚动的内容里；四档对照 V0/V1/V5/V6/V7 见 docs/TROUBLESHOOTING.md §136 补）。
   2026-10-11 整条退役：三页的用户实机反馈都是「横幅下面多了一条杠」——那条带子挂
   `blur(17px) saturate(2.2) brightness(1.14)`，身后是站用背景照片时暗部被抬亮 47/255 级、
   上沿一条硬接缝 ⇒ 读作多出来的一条杠，不读作玻璃截面。判死过程与逐行量法见 §138。
   要把这套代码捞回来：`git show b1655a5:gallery_src/liquid_glass.js`（别直接接回页头，先过 §138）。 */

var pend=0;
addEventListener('resize',function(){ if(pend) return;
  pend=requestAnimationFrame(function(){ pend=0; refresh(); }); });

window.LiquidGlass={ on:LG.on, mount:mount, auto:auto, refresh:refresh,
                     get buckets(){return LG.buckets.length;}, get filters(){
                       return LG.svg?LG.svg.querySelectorAll('filter').length:0; } };
})();
