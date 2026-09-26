---
name: spine-web-runtime-integration
description: 在网页里集成 Spine 3.8 (spine-webgl) 运行时做动态立绘渲染与批量出图，覆盖 .skel/.json 骨架分流、atlas 多页加载、必须 setSkin（否则命名 skin 独有部件整块不显示）、setup pose 与动画第 0 帧是两种语义、相机视口与 fit 包围盒陷阱、0 秒占位动画过滤、TDZ 变量遮蔽、无头 CDP 验收判据。当需要让 .skel/.atlas 模型在浏览器里动起来、反馈"模型缺胳膊少腿/比例怪/层加载失败/导出出来是中间一小块四周全黑"、或要批量渲染 Spine 立绘成 PNG 时使用。触发词：Spine 网页播放、spine-webgl、spine-all.js、SkeletonBinary、SkeletonJson、atlas 图集页、setSkin、皮肤、SceneRenderer、比例怪、缺下半身、部件不显示、setup pose、CG 导出、层失败、动态立绘渲染、骨骼动画截图。不适用于 AssetBundle 侧的 Spine 资源还原与页纹理补齐（那是 unity-assetbundle-painting-restore），也不适用于 Live2D 网页集成（live2d-web-runtime-integration）。
version: 1.0.0
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
  ⇒ 自动选只能给默认值，**必须同时提供手动切换的 UI**（下拉含"不设 skin"项），
  让人能同视口对比。同视口对比也是零回退证据：设 skin 前后画面大小应一致，只是部件回来了。

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
- [ ] skin 选择用 `coverOf`（只量动画帧），平手有手动下拉可切
- [ ] 导出层若要补部件，用"动画第 0 帧"开关且默认关闭；开则全量重导，不只重导子集
- [ ] `scene.camera.setViewport(w, h)` 跟着 `scene.resize()` 一起调
- [ ] 过滤 0 秒占位动画，默认播 `normal`，分层取并集
- [ ] 状态对象与循环内局部变量不同名（查 TDZ 遮蔽）
- [ ] 停止时 `cancelled` 置位 + `cancelAnimationFrame` 都做
- [ ] 验收包含逐张看图 + 同视口对照，不以"加载成功/槽位数"收工

## 涉及文件与延伸

本项目实现与取证（技能正文只留方法，细节回文档，避免双份维护）：

- 前端渲染与皮肤下拉：`gallery_src/index.html`（与 `Output/gallery_v2/index.html` 同 inode 硬链，**只原地编辑**）
- 批量出图页：`gallery_src/cg_export.html`（`ANIM_FRAME` 开关）
- 出图驱动：`scripts/diag/run_cg_export.py`（`--only` / `--size` / `--extra 'animFrame=1'` / `--redo`）
- skin 影响面扫描：`scripts/diag/spine_skin_scan.py`（每 part 一行 JSON + `SUMMARY` 行；>8 分钟走 `run_detached.py`）
- 逐槽细节：`scripts/diag/spine_skin_probe.py <目录> <槽名正则>`
- 取景异常定位：`scripts/diag/spine_bounds_probe.py <目录>`
- 工作流与判据：`docs/WORKFLOWS.md` WF-14（含"CG 层光加 setSkin 不解决问题"）、WF-16
- 事故记录：`docs/TROUBLESHOOTING.md` §42（缺整块身体）、§44（含"mojibake 是我自己日志的假象"更正）
