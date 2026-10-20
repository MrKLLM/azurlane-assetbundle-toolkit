---
name: spine-web-runtime-integration
description: 在网页里集成 Spine 3.8 (spine-webgl) 运行时做动态立绘渲染与批量出图，覆盖 .skel/.json 骨架分流、atlas 多页加载、必须 setSkin（否则命名 skin 独有部件整块不显示）、**多层之间的绘制序（层名后缀启发式必翻车，只能取引擎层级；含"某一层整块看不见"如何区分是没渲染还是被盖住）**、setup pose 与动画第 0 帧是两种语义、相机视口与 fit 包围盒陷阱（含"恒不渲染的巨幕遮罩撑爆取景"与"不透明纯色黑底撑爆取景"两类，以及判据必须落在取景那一刻）、readPixels 在实时 viewer 里不可用、0 秒占位动画过滤、TDZ 变量遮蔽、无头 CDP 验收判据，**以及把骨架当网站背景用（§14：七步绘制序列少一步就一帧不画、`camera.zoom` 存倒数、帧计数才是"在不在动"的唯一证据）**。当需要让 .skel/.atlas 模型在浏览器里动起来、反馈"模型缺胳膊少腿/比例怪/层加载失败/导出出来是中间一小块四周全黑/**少了个人/被另一块盖住**"、或要批量渲染 Spine 立绘成 PNG 时使用。触发词：Spine 网页播放、spine-webgl、spine-all.js、SkeletonBinary、SkeletonJson、atlas 图集页、setSkin、皮肤、SceneRenderer、比例怪、缺下半身、部件不显示、setup pose、CG 导出、层失败、动态立绘渲染、骨骼动画截图、取景、包围盒、画面太小、只占中间一小块、四周全黑、fit、层序、绘制序、遮挡、少了个人、谁压谁。不适用于 AssetBundle 侧的 Spine 资源还原与页纹理补齐（那是 unity-assetbundle-painting-restore），也不适用于 Live2D 网页集成（live2d-web-runtime-integration）。
version: 1.1.8
---

# Spine 网页运行时集成与批量出图

## Overview

用 spine-webgl（本项目为 vendored `spine-all.js` 3.8）在浏览器里渲染 `.skel` + `.atlas`
动态立绘，并可批量落盘 PNG。核心风险不在"渲染不出来"，而在**渲染出来但整块部件是空的**——
Spine 的附件解析依赖两个容易漏掉的前提（当前 skin、以及"看动画帧还是看 setup pose"），
两者都**不报错、不抛异常**，只静默缺一块。

## 适用判断

- 需要在网页里播放/截图 Spine 骨骼动画 → 用本技能
- 只需要静态图（不需要骨骼运动）→ 直接取 atlas 区域，别起 WebGL
- `.skel`/`.atlas` 本身怎么从 Unity AssetBundle 里解出来、页纹理怎么补齐 →
  走 `unity-assetbundle-painting-restore`，本技能假定资源已在盘上

## 1. 运行时加载

`spine-all.js` 用**普通 `<script src>` 同步标签**引入。

- ⚠️ 不要在探针里再 `loadScriptOnce('./vendor/spine/spine-all.js')` 补一份——
  已有全局时会加载**第二份**并覆盖，之后各种莫名失败。判断是否就绪只看
  `typeof spine !== 'undefined' && spine.webgl`。
- WebGL 上下文：`new spine.webgl.ManagedWebGLRenderingContext(canvas, {alpha:true, premultipliedAlpha:true})`，
  再 `new spine.webgl.SceneRenderer(canvas, ctx, false)`；混合自己开：
  `gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA)`，清屏 `gl.clearColor(0,0,0,0)`。

## 2. 骨架格式分流

```js
if (bytes[0] === 0x7B) {   // '{' → JSON 骨架（少数资源如 beierfasite_g）
  data = new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas))
             .readSkeletonData(new TextDecoder().decode(bytes));
} else {
  data = new spine.SkeletonBinary(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(bytes);
}
```
只按二进制写会把 JSON 骨架整批判成"加载失败"。

## 3. Atlas 多页

```js
// 页名行 = 顶格、非属性、以 .png/.jpg 结尾
const pageNames = [];
for (const ln of atlasTxt.split('\n')) {
  const t = (ln || '').replace(/\r$/, '');
  if (/^[A-Za-z0-9_].*\.(png|jpg)$/i.test(t) && !ln.startsWith(' ') && !ln.startsWith('\t') && !t.includes(':'))
    pageNames.push(t);
}
// 每页都要真的下载并建纹理，少一页就是那几页上的部件全空
const textures = {};
for (const pgn of pageNames) { /* await img.onload → new spine.webgl.GLTexture(gl, img, false) */ }
const texLoader = path => { for (const q in textures) {
    if (q === path || ('' + path).endsWith(q) || q.endsWith('' + path)) return textures[q]; }
  return textures[pageNames[0]]; };
const atlas = new spine.TextureAtlas(atlasTxt, texLoader);
// 区域名带首尾空白时兜底再查一次
const ofind = atlas.findRegion.bind(atlas);
atlas.findRegion = n => { let r = ofind(n); if (r) return r;
  const t = ('' + n).trim(); return t !== n ? ofind(t) : r; };
```

- ⚠️ `texLoader` 返回 `null` 会直接炸（`TextureAtlas.load` 要 `page.texture.setFilters/setWraps/getImage`）。
  纯结构分析（不真渲染）时给假对象 `{setFilters(){},setWraps(){},dispose(){},getImage(){return{width:1,height:1}}}`。
- ⚠️ **`Region not found in atlas` 未必是编码问题。** 本项目一次误判：日志里区域名是 mojibake，
  据此写了"`.skel` 与 `.atlas` 编码不一致"。hexdump 后证明两边**逐字节相同**
  （`0b e5 9b be e5 b1 82 20 36 36 34` = spine 的 len+1 存法 + 合法 UTF-8 `图层 664`），
  mojibake 是**Python stdout 按 GBK 解码**造出来的假象。
  ⇒ **下"编码/字节层"结论前必须直接 hexdump 原始字节，不能引用任何经过终端编码的字符串。**

## 4. 必须 `setSkin`（本技能最重要的一条）

spine-ts 3.8 里动画的附件时间线经 `Skeleton.setAttachment(slotIndex, name)`
→ **`当前 skin.getAttachment(slotIndex, name)`** 解析。**不设 skin ⇒
凡附件只存在于命名 skin 里的槽位一律解析成 `null`，整块部件不显示，且全程无报错。**

真实事故：用户报"某皮肤下半身不见了，静态立绘却是完整的"。全库扫描 331 个 part，
受影响 4 个，缺的槽位是 `datui*`(大腿) `xiaotui*`(小腿) `tui*`(腿) `jiaozhi*`(脚趾) `shenti*`(躯干)。

```js
const skeleton = new spine.Skeleton(data);
if (bestSkin !== null) skeleton.setSkin(data.findSkin(bestSkin));   // ⚠️ 传 Skin 对象，传字符串会炸
skeleton.setSlotsToSetupPose(); skeleton.setBonesToSetupPose();
```

**选哪个 skin：数据驱动，不写按角色名的例外表。** 判据 =
"把每条动画推进若干时刻后，**曾经挂上附件的槽位数**"，取最多者：

```js
const coverOf = (sk) => { const ever = new Set();
  const an = (data.animations || []).map(a => a && a.name).filter(Boolean).slice(0, 6);
  const asd = new spine.AnimationStateData(data);
  for (const n of (an.length ? an : [null])) {
    const t = new spine.Skeleton(data), st = new spine.AnimationState(asd);
    if (sk !== null) t.setSkin(data.findSkin(sk));
    t.setSlotsToSetupPose(); t.setBonesToSetupPose();
    if (n) st.setAnimation(0, n, true);
    for (const dt of [0.05, 0.5, 2.0]) { st.update(dt); st.apply(t);
      for (const sl of t.slots) if (sl.getAttachment()) ever.add(sl.data.name); } }
  return ever.size; };
let bestSkin = null, bestCov = coverOf(null);
for (const k of (data.skins || []).map(k => k.name)) {
  const c = coverOf(k); if (c > bestCov) { bestCov = c; bestSkin = k; } }   // 严格大于 → 平手取列表序第一个
```

- ⚠️ **判据陷阱（差点自证成功）**：`coverOf` 里如果把"纯 setup pose 的附件并集"也算进去，
  会**抹平所有差异**——setup 附件取自 `slotData.attachmentName`、与 skin 无关
  （实测该皮肤四种 skin 下恒为同一数）。判据只能量"动画跑起来之后实际挂上的附件"。
- ⚠️ 覆盖数**平手是常态**（该皮肤 skin `'1'` 与 `'2'` 都是 201，但补的不是同一批部件）。
  ⇒ 自动选只能给默认值，**必须同时提供手动切换的 UI**，让人能同视口对比。
  同视口对比也是零回退证据：设 skin 前后画面大小应一致，只是部件回来了。
- ⚠️ **但这个下拉绝不能把"不设 skin"做成可选项**（2026-10-05 用户实机踩坑）：
  `skin=null` 会让命名 skin 的附件**全灭**（实测 `tianjinfeng_2` 主层 **92 → 0**，
  角色主体整块消失、只剩其它层残件 —— 用户报"这肯定有问题呀"），而它还常常正是
  `layers.find(L=>L.skin)?.skin ?? '∅'` 算出来的**默认值**。
  下拉首项要做成「（自动）」并回退到 **`data.defaultSkin` 对象**（⚠️ 不是 `null`，
  也不是 `findSkin('default')` —— `defaultSkin` 只挂在 SkeletonData 上，未必能被名字找到）；
  裸 setup 只留给诊断入口（`?skin=none` / 探针 `--skin none`）。
- ⚠️ **换 skin 之后重算任何派生量（取景框 / 包围盒 / 画布尺寸）都必须先 `anim.update(0) + apply()`**：
  `setLayerSkin` 里通常紧跟 `setSlotsToSetupPose()/setBonesToSetupPose()`，状态被打回 setup，
  此刻量到的顶点与"动画跑起来之后"差很多（实测同一层 extents 计数 **0 vs 85**、框宽差近一倍）。
  初始化路径本来就是"先 apply 再算框" —— 两条路径必须一致，否则切一下皮肤画面尺寸就跳一档。
- ⚠️ **验证"用户报的画面不对"时，必须能重放用户的操作序列**（`--skin auto` 复现下拉路径、
  `--skin none` 复现裸态）。用自己默认路径的截反复"确认已修好"是自欺 —— 用户很可能在另一条路径上。

## 5. setup pose ≠ 动画第 0 帧（出图语义）

批量导出 PNG 时这是**两种不同产物**，别混：

| | 附件来源 | 结果 |
|---|---|---|
| 纯 setup pose | `slotData.attachmentName` | 与 skin 无关，命名 skin 独有的部件**不出现** |
| 动画第 0 帧 | `AttachmentTimeline` 经当前 skin 解析 | 部件齐全 |

⇒ 光把第 4 节的 skin 逻辑抄进导出脚本**不解决问题**，必须再补一步：

```js
if (USE_ANIM_FRAME) {
  const an = (data.animations || []).map(a => a && a.name).filter(Boolean);
  const pick = an.indexOf('normal') >= 0 ? 'normal' : an[0];
  if (pick) { const st = new spine.AnimationState(new spine.AnimationStateData(data));
    st.setAnimation(0, pick, true); st.update(0); st.apply(skeleton); } }
skeleton.updateWorldTransform();
```

- **开关默认关闭**：打开它会改**全部**产物的构图语义（实测连"没有 skin 问题"的皮肤
  画布高度都会从 821 挪到 824）。
- ⚠️ **要么全量重导、要么不动**。只重导受影响的那几个子集会在一批产物里留下两种语义，
  比原来更糟。重导前先备份并逐文件 md5 证备份与原件全等。

## 6. 相机视口与 fit

```js
function resize() { canvas.width = wrap.clientWidth; canvas.height = wrap.clientHeight;
  scene.resize();
  scene.camera.setViewport(canvas.width, canvas.height); }  // ⚠️ 关键
```
`SceneRenderer.resize()` **不更新相机视口**（恒初始 300×150）→ 渲染放大数倍、"比例怪"。

`fit()` 量各槽位附件的世界顶点包围盒：
- RegionAttachment：`computeWorldVertices(slot.bone, v, 0, 2)`，8 个浮点
- MeshAttachment：`computeWorldVertices(slot, 0, worldVerticesLength, v, 0, 2)`
- 跳过 `!slot.getAttachment()` 与 `!slot.bone.active`

⚠️ **包围盒会被"根本不会落笔"的巨幕遮罩带偏**：美术常在同层放整屏闪黑/闪白遮罩，
setup 色 alpha=0（本项目实测单片达 28284×18082、最大 32967×29970 单位），
一个像素都不画却能把包围盒撑到可见内容的近十倍 → 画面只占中间一小块、四周全黑。
- 该缺陷**与 skin 无关**（两种 skin 下 bbox 逐字相同），也**与"fit 的时机"无关**
  （把 `fit()` 挪到首帧 apply 之后实测无效）——只改时机是找错方向。
- 正确的过滤维度是"这一刻真的会被画出来"。⚠️ 若按 alpha 过滤，**读 `slot.data.color.a`（setup 色）
  而不是 `slot.color.a`（当前色）**：后者会被动画时间线改写，用它会让取景框随动画时刻跳动。
  落地即 `boundsOf()` 里一行 `if(slot.data.color.a<=0.001) continue;`。
- **判据必须落在"取景那一刻"的状态上，不是"这个部件一生中出现过的状态"**：改用
  "沿**所有**动画采样，只要曾 alpha>0 就算内容" 后，阳性对照（实测画面只占视口 1.2% 的那个皮肤）
  报"包围盒没变化"＝等于没修，因为闪黑幕在某条特殊动画里会亮一次。
  ⇒ 任何"筛选集合"类判据都要先拿一个已知坏样本验它会不会报警。
- **别用 `readPixels` 在实时 viewer 里收紧包围盒**。批量导出页可以（渲的是静止姿态 + `draw()` 后
  显式 `sleep(30)` 等 GPU），弹窗不行：动画从第一帧就在跑，且 spine 的页纹理是首次 `draw` 才上传，
  读回来的是"局部已就绪"的渲染 → 量到一个只含背景渐变小块的框，放大成一屏模糊色块。
- **第二类撑大源：不透明的纯色巨幕**（黑底/白底舞台板，实测单片 15899×11255）。它真的在渲染，
  所以"会不会落笔"为真、alpha 判据拦不住。判据 = **把区域纹素乘上 `slot.data.color` 之后**，
  "落笔里 `max(r,g,b)>40` 的占比" ≥0.05。**两侧都必须乘，只看一侧会漏掉一半**：
  `1heidi`/`heimu` 是黑贴图×白乘数，而 `yunlong_3` 的 `kkkkk*` 是**白贴图 × `rgb=0,0,0` 乘数**
  （只看贴图它亮度 255，完全不像黑底）。
  两条捷径都被实测否掉：① 按部件名（`hei`/`bai`/`heimu`/`1heidi`）会误伤真内容——
  2B 的整幅背景板就叫 `bj_1`；② 按纯黑乘数（`slot.color.rgb==0`）也不行（多数黑幕 setup 色是 `1,1,1`）。
  ⚠️ 同理，**"像素 alpha 包围盒占 0.83"这种自报指标会被纯黑巨幕骗过**：图看着"填满画布"，
  实际是一大片黑里嵌一小块舞台。**构图对不对只能看图。**
- **像素统计的开销要按"只有贴边的附件才撑得大框"来省**：逐个附件算 300~1000ms/part（中位 298ms），
  弹窗里不可接受；只测贴着当前包围盒某条边的附件、从外向里剥 ≤6 轮，结果按 `(页,区域,乘数)` 缓存，
  实测无感。⚠️ 剥到空框必须退回上一轮（`yunlong_3` 是全库唯一一个，会走到这条分支）。
  ⚠️ 读页图只能 `page.texture.getImage()`：`page.name` 存的是 atlas 里那一行原文（带路径），
  与自己解析出的裸文件名不相等，按名字回查拿到 undefined。
- 量取景要报**两个数**：`长轴占满 = max(内容宽/视口宽, 内容高/视口高)`（适配留 1.1 倍边，
  所以满分线是 0.91）与面积占比。只报面积会被宽高比失配稀释，把正常竖图误读成取景过小。
- 状态以 `docs/TROUBLESHOOTING.md` / `PROJECT_STATUS.md` 为准（本技能只记机制与判据，不记修复进度）。

## 7. 动画列表

```js
const anims = (data.animations || []).filter(a => a.duration > 0.01)
                .map(a => ({ name: a.name || a, dur: +a.duration.toFixed(1) }));
```
- 名字为 `1..N` 的多为 **0 秒空占位**（逐部件不同），真实动画是 `normal` / `touch_*` /
  `login` / `change_out` → 过滤空动画、默认播 `normal`、缺 `normal` 时回落列表首条。
- 多部件（分层合成）时取各层"有时长"动画名的**并集**；某层没有该动画就跳过该层，别整层报错。

## 8. 反模式

- **块内变量遮蔽外层状态对象**：渲染循环里写 `let my = 0`（鼠标坐标）会遮蔽外层的
  `const my`（状态对象），块内所有 `my` 进 TDZ → 部件明明加载成功却抛
  `Cannot access 'my'`，前端表现为假的"N 层失败"。状态对象与局部变量**必须不同名**。
- 只 `cancelAnimationFrame` 不设 `cancelled` 标志（或反之）→ 异步回调继续往已销毁的上下文里画。
  固定写法：状态对象带 `cancelled`，停止时先置位再 `cancelAnimationFrame`。
- 用 `document.querySelectorAll('audio')` 之类"数元素"的方式判"有没有在播"——
  库自建元素不入 DOM，恒为 0，会误判成"根本没播"。

## 9. 无头验收判据

- **视觉产物必须逐张看图**。"骨架解析成功 / 槽位数对 / 动画在播"都只是代理指标：
  缺整块部件时它们全部为真。看图工具要现成，否则会被代理指标顶替。
- **同视口对照**证零回退：改前后用同一窗口尺寸、同一 profile 新建，只比目标差异部分。
- **大资源要等够**：图集页可能十几 MB、`.skel` 可能上百 MB，固定几秒等待会让 UI
  还没建出来，误报成"没有皮肤下拉""该皮肤无资源"。改成轮询到目标元素出现。
- **CDP 连 target 要按 URL 过滤**：`/json` 里第一个带 `webSocketDebuggerUrl` 的不一定是目标页。
- **`Popen(chrome)` + `terminate()` 不回收浏览器进程**：下次用同一 `--user-data-dir`
  会直接复用那个旧实例，拿到**上一轮的页面**，于是出现"我改了也部署了，截图还是旧的"
  这种假矛盾。要么每次唯一 profile，要么收尾按 profile 精确清进程。

## 10. 落地检查清单

- [ ] `spine-all.js` 只加载一次；`typeof spine !== 'undefined' && spine.webgl` 为真
- [ ] 按首字节 `0x7B` 分流 JSON / 二进制骨架
- [ ] atlas 每个页名都真的下载并建了纹理；`findRegion` 有 trim 兜底
- [ ] `setSkin(data.findSkin(name))` 传对象不传字符串，且在 `setSlotsToSetupPose()` **之前**
- [ ] skin 下拉的"自动/不设"项回退到 `data.defaultSkin` **对象**（绝不传 `null`），见 §4
- [ ] 换 skin 后重算取景/包围盒前先 `anim.update(0)+apply()`（否则量的是 setup pose）
- [ ] 「画面散架/角色消失」先按 §12 查**动画相位**（`--seek`），别改取景
- [ ] 写采样脚本要复刻页面判据（`setToSetupPose` + `slot.data.color` 过滤 + 1/60s 小步）
- [ ] skin 选择用 `coverOf`（只量动画帧），平手有手动下拉可切
- [ ] 导出层若要补部件，用"动画第 0 帧"开关且默认关闭；开则全量重导，不只重导子集
- [ ] `scene.camera.setViewport(w, h)` 跟着 `scene.resize()` 一起调
- [ ] 过滤 0 秒占位动画，默认播 `normal`，分层取并集
- [ ] 状态对象与循环内局部变量不同名（查 TDZ 遮蔽）
- [ ] 停止时 `cancelled` 置位 + `cancelAnimationFrame` 都做
- [ ] 验收包含逐张看图 + 同视口对照，不以"加载成功/槽位数"收工
- [ ] 读骨架级 `x/y` 走官方 runtime（§11），不手搓二进制解析
- [ ] 多层错位先按 §12 三步判据否证，别直接当"偏移丢了"去补
- [ ] 多层问题**逐层出图**看（`?part=`+`?tag=`+`?animFrame=1`），别用顶点框/skeleton.x 下结论（§12）
- [ ] ~~像素级取景的判据含「不透明近黑 = 留白」~~ **已否证**（暗调皮肤 79.6% 像素 <40，误裁角色）；
      取景异常先量逐层世界框，按**层**剔背景巨幕（附件≤8 且面积≥其余并集 4 倍），见 §12
- [ ] 剔背景层要先做**全库影响面扫描**（`spine_backdrop_scan.js`）+ 逐层隔离截图核对，再谈部署
- [ ] 改完取景读页面自报的 `window.__frameInfo()`（`dropped/box/base1`）；`W:0` 说明弹窗没打开


## 11. 读 .skel 的骨架级信息：**用官方 runtime，别手搓二进制解析**

要拿 `skeletonData.x / y / width / height`（各层原点偏移），**不要**在 Python /
任意语言里手搓 Spine 二进制格式。手搓过一次，连错四处：

| 坑 | 现象 | 正解 |
|---|---|---|
| `readString` 长度字段是「真实字节数 **+1**」 | 版本串读成 `.8.99`（少首字符 `3`），后续每个 float 全错位 | 漏掉这个 ±1 整体偏移 1 字节 |
| `fps/imagesPath/audioPath` **只在 `nonessential==true` 时存在** | 无条件读 ⇒ 读到 bones 表字节 ⇒ `fps=1.28e19` | 先读 `nonessential` 再分支 |
| 要拿 x/y 必须走完整个 `readSkeletonData`，它需要**配套 atlas** 做 attachmentLoader | 只读文件头拿不到，或炸在 `Region not found in atlas` | 同名 `.atlas` 文本 + `spine.TextureAtlas` + `spine.FakeTexture({width,height})` |
| `readSkeletonData` 收的是 **Uint8Array 视图**不是裸 ArrayBuffer | `DataView(data.buffer)` 里 `.buffer` 为 undefined | 传 `Uint8Array` |

**正确做法**：在 node 里 `vm` 加载前端正在用的 `spine-all.js`（官方 UMD 之外的那种
`var spine; (function(spine){…})(spine||(spine={}))` 形态），然后调
`new spine.SkeletonBinary(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(view)`。
本项目实现：`scripts/diag/skel_header.js <目录|.skel>`。

⚠️ 若走 node `vm` 沙箱：**ArrayBuffer / DataView 必须同 realm**，整个读取要放在
沙箱内闭包里做（`vm.runInContext` 里定义读取函数，再把字节拷进沙箱自己的 ArrayBuffer）。
另外 `spine-all.js` 尾部给 three.js 的 mesh 做了 `THREE.Mesh` 继承，
要先摆一个 `THREE` 桩否则加载就 `ReferenceError`。

## 12. 多层的层间关系：**只能逐层出图看，坐标类判据全部会骗人**

**症状**：多层 Spine 画在一起，用户说「构图歪 / 挤在中间 / 背后还有一个身体」。

**先说三条会浪费时间的错误判据**（2026-10-04 全部实测否证）：

1. ❌ **「`skeletonData.x/y` 各层不同 ⇒ 错位」** —— `skeletonData.x/y` 是 **Spine 编辑器的
   画布尺寸元数据**，官方 `Skeleton` 构造时写死 `this.x = 0; this.y = 0`，
   **`data.x` 不会被拷进去**。`updateWorldTransform` 里那句 `worldX = x * sx + skeleton.x`
   里的 `skeleton.x` 恒为 0，所以偏移**从来没有**被自动应用。
   典型误读：看到 `data.x` 各层是 `-2957 / -995 / -6160` 就断定「层间错位」——
   A/B 两版（保留 vs 置零）渲染**逐字相同**。
2. ❌ **「用骨骼顶点框判断层间关系」** —— 骨骼里有大量**远端占位/隐藏骨骼**，
   顶点框会撑到整块画布。实测五层的 `bones[].worldX/Y` 框**几乎完全相同**
   （都 6008×5785、交叠 100%），而这五层实际画的东西完全不同。
   ⇒ 顶点框只能当「粗略外接」的 sanity check，**不能**当判据。
3. ⚠️ **「剔掉背景层再取景」—— 方向是对的，但必须带判据；凭直觉剔一定出错**。
   2026-10-04 试过一次、失败了（剔完取景收紧、画面被裁掉菱形一角），当时被记成"反例"。
   2026-10-05 查清失败原因：那时**没有任何判据**，是"看层名像背景就剔"，
   剔掉的实际是**有内容的层**。补上量化判据后（见下面「按层剔背景巨幕」），
   目标皮肤画面放大 2.28 倍，且全库 234 个目录只命中 2 个、逐层隔离看过都是真背景。
   ⇒ 教训不是"别剔"，而是**没有判据时不要动筛选集合**（同 §6 第一类判据的教训）。

**正解：逐层出图，人眼看。** 给 `cg_export.html` 加两个参数（可复用）：

    ?part=<层名>      只导出这一层（逗号分隔可多层）
    ?tag=<后缀>       输出文件名加后缀 —— **绝不能省**，否则诊断图覆盖正式产物
    ?animFrame=1      应用动画第 0 帧，否则 setup pose 下大量层附件数为 0

驱动脚本见 `scripts/diag/skel_layer_boxes.py`（层清单/落笔框/交叠比）与
逐层出图用法（本仓库 `run_cg_export.py --extra 'animFrame=1&part=X&tag=Y'`）。

### 逐层出图后怎么定案：按**层**剔背景巨幕（2026-10-05，同时否证 2026-10-04 的像素判据）

**先看这条否证**（别再往像素判据上改）：2026-10-04 把根因记成「像素二次构图只判 `alpha>8`、
漏掉不透明近黑」，修法是给它加 `max(r,g,b)<40` 算留白 —— **实装即翻车，两次都翻**：
- 「不透明近黑=留白」：整体暗调的皮肤 **79.6% 的像素都 <40**，角色暗部被一起判成留白 → 角色几乎消失；
- 换「连续 24 像素同色」（想抓"纯色填充"）：大片**平滑渐变**被判留白 → 框缩到只剩高光处。
⇒ ① **像素级判据区分不了「留白」与「深色内容」**；② 它压根回答不了「这条取景框是被谁撑大的」。

**真根因是层级几何**。量法：`node scripts/diag/skel_layers_report.js <Spine_v2 目录>`

| 层 | 附件数 | 世界框 | 尺寸 |
|---|---|---|---|
| 主层 | 85 | 1371×1659 | ← 角色 |
| `…B2` | **1** | **7000×7007** | ← 背景巨幕（五个槽以外全靠它撑） |

取景框 = 各层顶点框**取并集** = 7000×7007 ⇒ `fit()` 把画面缩到 0.184 ⇒ 角色成中间一小块，
看着像「躯干/下肢/尾巴整块没渲染」。

**判据（按层剔，两条 AND，缺一不可；宁可漏剔，不可错剔）**：
1. 该层附件数 ≤ 8 —— 角色层不可能只有几个附件；
2. 该层面积 ≥ 4 × 其余层并集面积 —— 它必须真的**包住**别人。

剔完至少剩一层才执行；被剔的层**照常渲染**，只是不计入取景框（UI 上要写明，否则用户以为没修）。

**为什么已有的三条判据都拦不住它**（也解释了为什么这个问题反复修不好）：
- `inksOf`（剥"不落笔的纯色板"，§6）：`…B2` **真的有内容**（一整个房间）；
- 离群剔除（剔"又远又大"的件）：`…B2` **包住一切、并不远离**，永远剔不掉；
- 像素二次构图：菱形不透明且铺满 ⇒ `frac≈1` ⇒ 直接跳过。
⇒ 筛"内容属性"的判据全都够不着「它是背景」这件事——那件事只写在**层名**里。

**门槛是「有没有实测收益」，不是「两页看起来一致」**：把同一判据搬到导出页，
实测产物 **md5 完全相同**（导出页的像素二次构图可靠，顶点框只决定**初始画布比例**）
⇒ 不引入。判据是**绑定取景机制**的，机制不同就不该一致。

**验收必须读平台自报的数，别靠看图**：页面 `window.__frameInfo()` 给
`dropped / box / base1 / didPixelFit / W,H`。⚠️ 读到 `W:0` = 弹窗**根本没打开**
（探针只等"索引就绪"会踩到这个中间态），此时截图再好看也不可信。

**「画面上这块东西是谁画的」只能逐层隔离截图**：
`py -3 scripts/diag/spine_layer_isolate.py <中文名> <key>`
（页面把层挂到 `window.__spLayers`，隔离靠渲染循环里的 `L.hidden` 开关）。
⚠️ **世界框 ≠ 画的是什么**：`…B2` 的顶点框是 7000×7007，但它**贴图本身**是块大画布，
真正不透明的内容（菱形）只有 ~3884。我据此断言「屏幕上那个菱形是 `…B2` 撑出来的」，
剔除后菱形照样铺满，白绕一圈 —— 顶点框只能说"框有多大"，说不了"画了什么"。

⚠️ **「实际内容框」从贴图 alpha 量不出来**（2026-10-05 晚实测否证）：spine atlas 导出时
贴图已做**留白裁切**（strip whitespace），每个 region 纹素基本都是内容 ⇒ alpha 框恒等于
整个区域 ⇒ "实际内容框"恒等于顶点框。菱形那圈透明**不在贴图里、在 mesh 顶点形状里**
（4 顶点 45° 方形），贴图是一整张矩形房间图。想拿"贴图 alpha 收紧 mesh 背景的取景"是死路。

⚠️ **官方立绘（`Paintings_v2/`）与 Spine 渲染是两条管线，构图可能根本不同**：合成器走
Unity sprite 路径（背景贴图**拉伸铺满 root 画框**，没有菱形 mesh），Spine 渲染（游戏内
动态立绘同款）才是菱形。用户拿立绘当"完整"基准时，先讲清这个差异再谈取景——
菱形 mesh（对角 d）的内接矩形 w+h ≤ d，横向弹窗里「房间铺满 + 边框出画 + 角色完整」
可能**数学上不可兼得**，别应承做不到的构图。**而且立绘永远"完整"**，因为它不播动画
（上面那条"动画后段散架"的病，立绘天然免疫）—— 所以拿立绘对照时别把"动画相位问题"
误判成"渲染缺件"。

⚠️ **「画面散架 / 角色主体消失」先查动画相位，别改取景**（2026-10-05 实测）：
有些 skel 的同名动画**中后段就是"退场/消散"演出**（角色被拉散或压没，只剩零星部件 + 光效），
而 prefab 的 `startingAnimation` 恰恰可能是它。实测某皮肤 `normal`（33.3s）：t=0.5~6s 主层框
1535×1571（正常）→ t≈8s 起 30316×46333 或 510×397（散架）。全库 234 个目录里 6 个有这现象。

**⚠️「截短播放区间」这个修法已于同日撤销（用户裁定），别再装回来**：查下来"少了人"的真因
**不是相位，而是层绘制序**（本体被不透明背景层盖住，见 §13）。截区间只是把另一个 bug 遮住，
代价是剪掉官方退场演出 ⇒ **产品行为一律完整播放**。
相位检查仍然有价值，但它是**取证手段**（`__seekAnim` 精确推进到某秒再截图），不是产品功能。
下面这段留着的唯一用途：当用户**主动**要"只看角色完整那段"时，知道怎么实现以及坑在哪。

**实现（若确实需要）**：对**主层**（层名===目录名那个，**不是** cov 最大的那个，见下）
用**独立 Skeleton** 沿动画采样 N 点，记录"可见附件数（挂着附件 且 `slot.color.a>0.001`）"，
取**最长的 `≥峰值×0.9` 区间**当播放区间；
帧循环里 `if(range && track.trackTime >= range[1]) track.trackTime = range[0]`。
⚠️ 字段是 **`trackTime`**（spine-ts 3.8 没有 `time`，写 `tr.time` 恒 undefined、回绕永不触发）。
全程稳定返回 `null` ⇒ 其它皮肤行为一字不变；换动画要重扫区间。

⚠️ **"主层"判据不能用 cov/附件数盲排**：前景特效层（如 `tianjinfeng_2` 的 `2T`）的覆盖附件
常常**比本体还多**（276 vs 92），按 cov 排会拿特效当角色。用"层名===目录名"优先，
否则排除 `_B/_B2` 后缀后取附件最多者。

⚠️ **前景特效层（T 后缀）只渲染不计取景**：它的特效（红光/光点）会把取景框拉高 52%、
角色被压小。判据按"T 后缀且非本体"剔除即可，但**配套必须做两件事**：
① 取景框计算时跳过它（与背景巨幕同一套 `dropBackdropLayers`）；
② **pixelFit 二次构图时临时把它藏起来再读像素**——否则它的 alpha 像素会把画面重新拉大、
   把"剔除"的效果整个抵消。

⚠️ **动画相位必须能精确控制才谈得上定案**：真实播放受帧率与 `dt` 钳制影响极大 ——
headless 里"等 16 秒"实际只推进约 2 秒动画。给页面加 `__seekAnim(sec)`（1/30s 小步推进）、
给探针加 `--anim/--at/--seek`，才是可信的时间控制；否则会拿"恰好稳定"的截图反复"确认已修好"。

⚠️ **写采样脚本必须逐条复刻页面的判据**，否则全是假象。本轮两次被自己的脚本误导：
① 漏 `setToSetupPose()` ⇒ 骨骼未初始化 ⇒ 顶点乱飞（虚报 2T 层 29780×15185，实际 1117×2311）；
② 漏 `slot.data.color` 的 alpha 过滤 ⇒ 把 setup alpha=0 的隐藏巨幕当成"在渲染"。
另外**小步推进**（1/60s）是必须的，且判据要落在**框面积**上、不能落在"可见附件数"上
（本病例附件数只掉到 61%，抓不住）。

## 13. 多层谁压谁：**顺序只能取自引擎层级**，名字后缀启发式必翻车（2026-10-05）

**症状**：多层 Spine 叠在一起，**某个部件整块看不见**（本项目：角色本体消失，只剩吊着的那份），
附件数 / alpha / skin / 取景框全部正常。

**先分清两件事**：「没渲染」和「渲染了但被盖住」是两种病，判据完全不同。
区分手段 = **逐层受控隐藏**：藏掉一层后目标内容**出现** ⇒ 是遮挡。
⚠️ 用共享开关字段（`L.hidden`）做隐藏前，先确认没有别的逻辑会写回它 ——
本项目的 `pixelFit()` 收尾无条件 `L.hidden=false`，恰好冲掉诊断工具刚设的隐藏
（被它冲掉的正是背景层，所以"全隐藏底片里房间还在"），据此得出的结论连续两轮是假的。
⇒ **共用一个字段的两套逻辑，必须按原值恢复，不许写死。**

**真权威只有一个：引擎自己的渲染顺序。** Unity UI = RectTransform 层级 **DFS 先序**
（父先于子、子按 `m_Children` 顺序），**先绘制者在下面**。读法：
`env.objects` 里收 `RectTransform/Transform` 的 `m_Father` / `m_Children`，从根 DFS 编号。

**三条会骗人的"证据"**（本轮全部实测踩到）：
1. ❌ **「反转层序数组后画面没变 ⇒ 不是层序问题」** —— 若在内容本来就散开的**动画相位**上做，
   谁压谁都看不出来。否证实验必须在**症状复现的那个相位**上做。
2. ❌ **「另一条渲染路径（CG 导出）看起来是对的 ⇒ 层序没问题」** —— 两条路径可能渲的**不是同一状态**
   （CG 页渲 setup pose，那一帧房间由另一层落笔）。跨路径的"正常"只说明它躲开了触发条件。
3. ❌ **「导出器给的层列表顺序就是绘制顺序」** —— 遍历 bundle 对象表得到的顺序是**序列化次序**，
   与层级无关。"权威清单"这类字段通常只保证了**集合成员**，先后要另外取。

**名字启发式的典型失败模式**：按后缀分桶（`B`→背景、`M`→中、`T`→前景）时，
**后缀带数字**的层（`2B2`、`T2`）会掉出桶外、和默认桶同序。写这类判据先问一句
「这个命名空间里有没有 `B2`/`B3`」。本轮就是 `tianjinfeng_2B2`（不 `endsWith('B')`）
掉进与本体同一个桶 ⇒ 本体先画、被 7000×7007 的不透明房间盖死。

**改代码前 5 分钟的端到端预验**：在浏览器里把层数组**原地重排**（`window.__spLayers.sort(...)`，
渲染循环迭代的是同一个数组对象）再截图。对了才动管线。

**零回退闸门放在数据层**：层序改动的影响面是"哪些目录的顺序数组变了"，这在生成物里
**精确可判**（本项目 `scripts/diag/spine_index_parts_diff.py`，还带一条
"除这个字段之外两份索引必须逐字相同"的防夹带断言）。
像素比对当不了闸门：取景若由 `readPixels` 二次构图决定，**同一份代码连拍两次**就会差
0.1%~2.6%（那一帧哪些贴图已上传是时序相关的）⇒ 要比图先量噪声底。

**取景与层序正交，别混成一个"看起来删了内容"的开关**：背景巨幕"算不算进默认取景框"
应该做成**显式可切换**（对准角色 ↔ 完整场景，两种模式都照常渲染所有层），
并且文案不许用"已剔除"这类像删了东西的词。切换后记得把 `zoom` 复位，
否则用户停在旧机位上，点了等于没点。

## 14. 把骨架当**背景**用：轻量版渲染 + 少一步就一帧不画 + 帧计数取证（2026-10-20 实测）

用途：让 Spine 动态皮肤像背景图那样"设为网站背景"。这和查看器是两件事，别复用查看器代码
（查看器要取景修正、背景巨幕剔除、skin 覆盖度循环选举、点击命中；背景只要全身居中、动起来、别抢戏）。

**绘制调用序列必须完整**（本项目逐字对齐首页 `frame()`）。少任何一步都**不报错、只是画面不动**：

```js
gl.clear(gl.COLOR_BUFFER_BIT);
scene.camera.position.set(cx, cy, 0);
scene.camera.zoom = 1 / baseScale;   // 存的是倒数，不是缩放比 ← 最容易写反
scene.camera.update();               // 漏了就不出画面
scene.begin();                       // 漏了 drawSkeleton 不落屏
scene.drawSkeleton(sk, true);
scene.end();
```

**判红形状**：canvas 挂上了、尺寸正常、`stats()` 里 `live:true`，但帧计数纹丝不动。
⇒ 直接照着上面七行对，别去怀疑 atlas / setSkin / 层级。

**"在不在动"只能用模块内的帧计数取证。** 从外部 `drawImage` 采样 canvas 读回的是空/旧缓冲
（`preserveDrawingBuffer:false`），两次采样必然相同 —— 这是**假阴性**，会把本来正确的渲染代码改坏。
做法：在动画循环里 `frames++`（背景模块暴露 `stats().frames`），探针要求 `f1 > f0 + 3`。

**背景模式的三层防交互**，缺一层用户就能摸到它：
`pointer-events:none` + `z-index:0` + 不接管任何鼠标事件。
验法：`document.elementFromPoint(内宽/2, 内高/2)` 必须命中内容元素，**不能**是背景宿主节点。

**只加载主层**：背景不需要分层全部 parts，`parts[0]` 即可；`pickSkin()` 只测 setup pose
（不跑"每动画 × 多个时间点"的覆盖度循环，那是查看器的活）。取景用「contain 到高度 94%、底部对齐」，
脚要踩在视口下沿，否则下半身被裁。

**资源前缀**：页在 `Output/gallery_v2/`，骨架在上一层 `Output/Spine_v2/` ⇒ 前缀必须由
`location.href` 派生 `../`，写死 `./` 必 404。

**别在每帧 `catch` 里 `console.warn`**：每帧一条会把控制台刷满、把真错误埋掉，只在第一次 warn。

涉及：`gallery_src/site_bg_live.js`、验收 `scripts/diag/site_live_bg_probe.py`、
判据 `docs/WORKFLOWS.md` WF-49、根因 `docs/TROUBLESHOOTING.md` §160。

## 涉及文件与延伸

本项目实现与取证（技能正文只留方法，细节回文档，避免双份维护）：

- 前端渲染与皮肤下拉：`gallery_src/index.html`（与 `Output/gallery_v2/index.html` 同 inode 硬链，**只原地编辑**）
- 动态背景模块（三页共用）：`gallery_src/site_bg_live.js` + `scripts/diag/site_live_bg_probe.py`（§14）
- 批量出图页：`gallery_src/cg_export.html`（`ANIM_FRAME` 开关）
- 出图驱动：`scripts/diag/run_cg_export.py`（`--only` / `--size` / `--extra 'animFrame=1'` / `--redo`）
- skin 影响面扫描：`scripts/diag/spine_skin_scan.py`（每 part 一行 JSON + `SUMMARY` 行；>8 分钟走 `run_detached.py`）
- 逐槽细节：`scripts/diag/spine_skin_probe.py <目录> <槽名正则>`
- 取景异常定位：`scripts/diag/spine_bounds_probe.py <目录>`
- 工作流与判据：`docs/WORKFLOWS.md` WF-14（含"CG 层光加 setSkin 不解决问题"）、WF-16、WF-26
- 骨架级偏移取证：`scripts/diag/skel_header.js`（node + 官方 runtime）+ `scripts/diag/spine_transform_tree.py`（prefab 父链）
- 层间落笔框与交叠比：`scripts/diag/skel_layer_boxes.py` + 测量页 `Output/gallery_v2/layer_boxes_probe.html`
- 文档编号体检：`scripts/diag/check_doc_numbering.py`（见 `docs/WORKFLOWS.md` WF-26）
- 逐层出图：`cg_export.html?part=<层>&tag=<后缀>&animFrame=1`（驱动 `scripts/diag/run_cg_export.py --extra ...`）
- 层间落笔框与交叠比：`scripts/diag/skel_layer_boxes.py`（浏览器逐层渲，**共享 glctx**）
- **逐层附件数 + 世界框（node，不开浏览器）**：`scripts/diag/skel_layers_report.js`
  （读 .skel 的公共库 `scripts/diag/spine_skel_lib.js`，与影响面扫描共用，别复制第二份）
- **全库影响面扫描**：`scripts/diag/spine_backdrop_scan.js`（`--only`/`--limit`/`--json`）
- **逐层隔离截图**（回答"这块是谁画的"）：`scripts/diag/spine_layer_isolate.py <中文名> <key>`
- 弹窗取值数值：`scripts/diag/spine_dialog_shot.py`（打印页面 `window.__frameInfo()`）
- 事故记录：`docs/TROUBLESHOOTING.md` §42（缺整块身体）、§44（含"mojibake 是我自己日志的假象"更正）、§98（弹窗缺像素级二次构图）、§99（多层坐标系不同源，附三条否证）、§100（其「真根因/修法/验证」三段**已被 §105 否证**）、**§105（真根因 = 背景巨幕层把取景框撑到 5 倍，按层剔除；含导出页为什么不套同判据）**
