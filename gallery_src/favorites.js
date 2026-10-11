/* 收藏 + 设为网站背景 —— 四个页面共用的两个小模块（window.Fav / window.SiteBg）。
   由 index.html / bgm.html / backgrounds.html / room3d.html 引用。

   ── 为什么存"键"而不是存"整条记录" ──
   每页手里都有全量索引（index.json / bgm.json / bg_meta.json），存键就能在任意页还原出
   标题、缩略图、路径；存副本则会遇到"源数据改了、收藏里还是旧的"这类二次真相。
   ⚠️ 键必须是**稳定标识**，不能是数组下标：换筛选、换排序、重新生成索引之后下标全会错位。
      音乐 = bgm.json 的 slug；首页条目 = 舰船/角色的 id（注意：收藏单位是"一张卡"，
      也就是一个角色，不是它下面的某个皮肤）；背景 = bg_meta.json 的 key。

   ── 背景为什么画在 body 上、而不是插一个 #sitebg 层 ──
   插层要打 z-index（首页 #bgfx 是 0、其余页是 .amb，内容层各页又不一样），
   而 position:fixed + z-index:-1 在 body 自带背景色的页面上会被 body 背景盖掉 —— 四处特判
   不如一层全局真相。第一版把它放在 `html` 上，结果四页全都"设了但看不见"：
   四页都写着 `body{background:linear-gradient(...) fixed}`，body 那层不透明渐变在 html 之上。
   所以规则是：**画在 body 的 background-image 上，并把原渐变保留成第二层**（立绘 contain
   时四周露出的是配色，不是白屏）。
   ⚠️ 首页还有一层不透明的水面 canvas（WebGL alpha:false）会盖住一切 ⇒ 有站用背景时
      CSS 把它 display:none，并靠 sitebgchange 事件停掉它的每帧绘制（不然白烧 3.3ms）。
   ⚠️ 用户已定：皮肤立绘做背景时**原图清楚铺满**，不加模糊也不压暗（2026-10-11 拍板）。
      立绘是透明 PNG ⇒ 用 contain + 贴底（角色"站"在屏幕下沿），壁纸图用 cover 铺满。
*/
(function(){
'use strict';

/* ───────────────────── 收藏 ───────────────────── */
var FKEY='gallery.fav';
function empty(){ return {bgm:[],skin:[],bg:[]}; }
function load(){
  try{ var o=JSON.parse(localStorage.getItem(FKEY)||'null');
       if(!o||typeof o!=='object') return empty();
       var d=empty();
       for(var k in d) if(Array.isArray(o[k])) d[k]=o[k].slice();
       return d; }catch(e){ return empty(); }
}
var D=load();
function save(){ try{ localStorage.setItem(FKEY, JSON.stringify(D)); }catch(e){} }
function has(kind,key){ return (D[kind]||[]).indexOf(key)>=0; }
function list(kind){ return (D[kind]||[]).slice(); }
function count(kind){ return kind? (D[kind]||[]).length
                                : (D.bgm.length+D.skin.length+D.bg.length); }
/* 点一下：加进去就返回 true。label 只用于 aria/标题，不参与判等。 */
function toggle(kind,key,label){
  var a=D[kind]||(D[kind]=[]), i=a.indexOf(key), on;
  if(i<0){ a.push(key); on=true; } else { a.splice(i,1); on=false; }
  save(); paint();
  document.dispatchEvent(new CustomEvent('favchange',{detail:{kind:kind,key:key,on:on}}));
  return on;
}
/* 星标按钮的 HTML：调用方把它拼进自己模板里，事件由 bind() 的委托统一接。
   ⚠️ 卡片整张是可点的（首页卡 = 打开弹窗），所以按钮必须 stopPropagation —— 这个
      在 bind() 里做，不指望每个调用方记得。 */
function btn(kind,key,label,cls){
  return '<button class="favbtn '+(cls||'')+(has(kind,key)?' on':'')+'" data-fk="'+kind+
         '" data-fv="'+String(key).replace(/"/g,'&quot;')+'"'+
         ' data-fl="'+String(label||'').replace(/"/g,'&quot;')+
         '" aria-pressed="'+(has(kind,key)?'true':'false')+
         '" title="'+(has(kind,key)?'取消收藏':'收藏')+'"><svg viewBox="0 0 24 24" aria-hidden="true">'+
         '<path d="M12 17.3l-6.2 3.7 1.6-7-5.4-4.7 7.1-.6L12 2l2.8 6.1 7.1.6-5.4 4.7 1.6 7z"/></svg></button>';
}
/* 重画页面上所有星标（筛选/重排之后调用方自己会重建 DOM，这里只处理"原地改状态"） */
function paint(root){
  (root||document).querySelectorAll('.favbtn').forEach(function(b){
    var on=has(b.dataset.fk,b.dataset.fv);
    b.classList.toggle('on',on); b.setAttribute('aria-pressed',on?'true':'false');
  });
  (root||document).querySelectorAll('[data-fcount]').forEach(function(e){
    e.textContent=count(e.dataset.fcount);
  });
}
function bind(){
  document.addEventListener('click',function(e){
    var b=e.target.closest && e.target.closest('.favbtn'); if(!b) return;
    e.preventDefault(); e.stopPropagation();      // 别让"收藏"顺手把卡片/那一行也点开
    toggle(b.dataset.fk,b.dataset.fv,b.dataset.fl);
  },true);
}

/* ───────────────────── 网站背景 ───────────────────── */
var SKEY='gallery.sitebg';
var S={ v:null };
function sload(){
  try{ var o=JSON.parse(localStorage.getItem(SKEY)||'null');
       return (o&&o.url)?o:null; }catch(e){ return null; }
}
function sapply(){
  var r=document.documentElement;
  if(!S.v){ r.classList.remove('has-sitebg');
            r.style.removeProperty('--site-bg'); r.style.removeProperty('--site-fit');
            r.style.removeProperty('--site-pos'); return; }
  var skin=S.v.kind==='skin';
  r.style.setProperty('--site-bg','url("'+S.v.url.replace(/"/g,'%22')+'")');
  r.style.setProperty('--site-fit', skin?'contain':'cover');
  r.style.setProperty('--site-pos', skin?'50% 100%':'50% 50%');
  r.classList.add('has-sitebg');
}
/* 事件是给首页水面层用的：CSS 只能把它藏起来，停掉每帧绘制要 JS 自己收工，
   不然设了背景还在烧 3.3ms/帧画一张看不见的海面。 */
function fired(){ document.dispatchEvent(new CustomEvent('sitebgchange',{detail:S.v})); }
S.set=function(o){ S.v=o; try{ localStorage.setItem(SKEY,JSON.stringify(o)); }catch(e){} sapply(); fired(); };
S.clear=function(){ S.v=null; try{ localStorage.removeItem(SKEY); }catch(e){} sapply(); fired(); };
S.get=function(){ return S.v; };
/* 同一个东西再点一次 = 取消（比"设为背景 / 取消背景"两个按钮省地方，也不会出现两个真相） */
S.toggle=function(o){ if(S.v&&S.v.url===o.url) S.clear(); else S.set(o); return !!S.v; };
S.is=function(url){ return !!(S.v&&S.v.url===url); };

/* 样式由模块自己注入：漏一页就会变成"那页没背景"这种最难查的差别 */
function css(){
  if(document.getElementById('favcss')) return;
  var s=document.createElement('style'); s.id='favcss';
  s.textContent=
   /* 星标：默认空心，收藏了填实心 —— 不靠颜色区分（色盲友好），靠填充 */
   '.favbtn{width:26px;height:26px;padding:0;border:1px solid var(--chip-line);border-radius:50%;'+
   'background:color-mix(in srgb,var(--panel) 72%,transparent);color:var(--dim);cursor:pointer;'+
   'display:grid;place-items:center;flex:none;transition:transform var(--t-col) var(--ease-ios),'+
   'color var(--t-col) var(--ease-ios),background var(--t-col) var(--ease-ios)}'+
   '.favbtn svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:1.9;'+
   'stroke-linejoin:round}'+
   '.favbtn:hover{transform:scale(1.12);color:var(--brand-d)}'+
   '.favbtn:active{transform:scale(.94)}'+
   '.favbtn.on{color:var(--brand-d);background:color-mix(in srgb,var(--brand-l) 70%,transparent);'+
   'border-color:transparent}'+
   '.favbtn.on svg{fill:currentColor;stroke:currentColor}'+
   /* ⚠️ 站用背景要画在 **body** 上，不是 html：四页都写着
        `body{background:linear-gradient(...) fixed}` —— body 自己那层不透明渐变
        盖在 html 背景之上，图放 html 上等于没放（实测两张截图一模一样）。
      两层并列：图在上、原来的渐变仍在下 ⇒ 立绘是 contain 时，四周露出来的是配色而不是白屏。
      用 !important：room3d 的 <style> 排在本模块之后，简写 background 会把 background-image 重置成 none。 */
   'html.has-sitebg body{background-image:var(--site-bg),'+
   'linear-gradient(180deg,var(--bg) 0%,var(--bg2) 100%)!important;'+
   'background-repeat:no-repeat,no-repeat!important;'+
   'background-size:var(--site-fit),cover!important;'+
   'background-position:var(--site-pos),50% 50%!important;'+
   'background-attachment:fixed,fixed!important}'+
   /* 可读性兜底：站用背景是高对比的立绘/照片，卡片平时那层半透面板底压不住它 ⇒ 名字读不清。
      ⚠️ 只压"放字的那一条"，不动图本身 —— 用户 2026-10-11 明确要"原图清楚铺满"，
         给整页加模糊/压暗就是把那个决定推翻掉。 */
   'html.has-sitebg .card .body{background:linear-gradient(180deg,'+
   'color-mix(in srgb,var(--panel) 74%,transparent),'+
   'color-mix(in srgb,var(--panel) 95%,transparent) 46%)}'+
   'html.has-sitebg .row{background:color-mix(in srgb,var(--panel) 88%,transparent)}'+
   'html.has-sitebg .card .nm{background:color-mix(in srgb,var(--panel) 90%,transparent)}';
   /* 光晕在背景图之上会把图洗白 ⇒ 有站用背景时压到两成（图本身不加模糊、不加压暗） */
   'html.has-sitebg #bgfx .glow,html.has-sitebg .amb i{opacity:.2}'+
   /* ⚠️ 首页那层水面 canvas 是**不透明**的（WebGL 默认 alpha:false），整层铺满视口 ⇒
      设了站用背景必须把它藏掉，否则背景图 100% 被盖住（实测两张截图一模一样）。
      光晕反而要留一点：它是"海边的感觉"，压在图上当氛围。 */
   'html.has-sitebg #bgfx canvas{display:none}'+
   /* 卡片上的星标位置：各页容器不同，这里只给"右上角浮标"这一种通用摆法 */
   '.favbtn.corner{position:absolute;top:7px;z-index:6;left:7px}'+
   /* 首页徽章在右上、背景库徽章在左上 ⇒ 同一个角标要能翻边 */
   '.favbtn.tr{left:auto;right:7px}';
  document.head.appendChild(s);
}

window.Fav={has:has,toggle:toggle,list:list,count:count,btn:btn,paint:paint,bind:bind};
window.SiteBg=S;
css();
S.v=sload();
if(document.readyState==='loading')
  document.addEventListener('DOMContentLoaded',function(){ sapply(); });
else sapply();
})();
