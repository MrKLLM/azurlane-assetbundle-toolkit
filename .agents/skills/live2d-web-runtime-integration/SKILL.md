---
name: live2d-web-runtime-integration
description: 在网页里集成 Live2D Cubism Web 运行时做模型渲染与动作播放（pixi 6.5.2 + live2dcubismcore 5.1.0 + pixi-live2d-display 0.4.0 组合），覆盖 model3.json 加载、动作触发（startMotion 传参陷阱）、按部位点击触发（HitAreas 命中判定）、模型尺寸与 fit 基准、交互层反模式、内存销毁与无头 CDP 验证判据。当需要让 .moc3/.model3 模型在浏览器里"真的动起来"、或反馈"模型不动/乱抖/点不出动作/显示不全"、或要在国内网络下载 Live2D 运行时库时使用。触发词：Live2D 网页播放、Cubism 运行时、pixi-live2d-display、Live2DModel 动作、模型点不动、idle 不播、HitAreas 点击、播完动作就卡死、判定区全丢、参数残留复位、模型画面是碎片堆、部件乱叠在一起、贴图错绑、Textures 顺序、加载成功但画面错乱。不适用于 Live2D 模型文件的 AssetBundle 逆向还原（那是 unity-assetbundle-painting-restore）与纯截图导出（headless-chrome-cdp-batch-export）。
version: 1.3.0
---

# Live2D 网页运行时集成

## Overview

把 Cubism 4 的 `.model3.json` 模型在浏览器里渲染成可交互、会播动作的 Live2D。核心难点不在"加载出来"，而在**动作真的在播**、**点击部位触发对应反应**、**构图不越界**——这三处各有一个会静默失败的陷阱。

## 适用判断

- 页面里已有/可放 `live2dcubismcore.min.js` 等运行时，要让模型动起来 → 用本流程
- 只是把模型贴图当静态图展示 → 不需要运行时，直接 `<img src="texture_00.png">`
- 要产出的不是"网页里的模型"而是从游戏包还原模型文件本身 → 先走 `unity-assetbundle-painting-restore`

## 1. 运行时三件套与版本组合

必须**按序**加载，且版本要成对（新 pixi 会破坏 display 适配层）：

1. `live2dcubismcore.min.js`（Cubism Core，实测 5.1.0）
2. `pixi.min.js`（实测 **6.5.2**）
3. `pixi-live2d-display-cubism4.min.js`（实测 **0.4.0**）

- **别用 pixi 7 / display 0.5**：本项目实测 pixi 6.5.2 + display 0.4.0 是可用组合。
- 国内网络：`live2dcubismcore.min.js` 可从 l2d 系站点直链取；pixi 与 display 走 npmmirror 的 **tgz 下载后解包取 `dist/`**（registry 元数据接口可能被拦）。下载细节见 `cn-blocked-resource-mirror-fetch`。
- 全部放本地 `vendor/live2d/`，**别用 `P`（资源相对路径前缀）拼 vendor**：若 vendor 与页面同目录，用 `./vendor/live2d/…`。判定办法是在页面里 `fetch('../vendor/…')` 与 `fetch('/<页面目录>/vendor/…')` 对比状态码，**别信 curl 的绝对路径**（curl 的 200 会掩盖相对路径错误）。
- 懒加载（点标签才加载）比顶部 `<script>` 好：用 `loadScriptOnce(src)`（按 `script[data-x]` 去重并缓存 Promise），避免首屏拖慢与重复注入。

## 2. 加载模型

```js
const mdl = await PIXI.live2d.Live2DModel.from('<dir>/<name>.model3.json', { autoInteract: false });
app.stage.addChild(mdl);
```

- `autoInteract: false` 时库自带的 hit test/视线跟随都关掉，交互自己实现（见 §4）。
- 需要 `FileReferences.Motions` 的组名列表：`mdl.internalModel.motionManager.definitions`（键即组名）。

## 3. 动作播放：八个必踩陷阱（3.1–3.8）

### 3.1 `startMotion` 的 index 不能传 `null`

```js
mm.startMotion(group, null, false)   // ✗ 静默失败，什么都不播
mm.startMotion(group, 0, MP.FORCE)   // ✓
```

库内部会取 `motion[group][index]`；传 `null` 得到 `undefined` 后**直接 return false，不报错**。`priority` 也不能传 `false`——会被当成 0，低于当前优先级同样被拒。用 `PIXI.live2d.MotionPriority.FORCE`（枚举 NONE/IDLE/NORMAL/FORCE = 0/1/2/3）。

### 3.2 判"有没有在播"要读运行时状态，且要等一拍

`startMotion` 内部要 `fetch` 动作 JSON，调用后立刻读会拿到空值：

```js
mm.startMotion(g, 0, MP.FORCE);
await new Promise(r => setTimeout(r, 1500));
const playing = mm.state.currentGroup === g;   // 唯一可靠判据
```

**帧哈希/drawImage 比对不能当判据**：无头环境 rAF 被节流会**假阴性**；而 physics 与眨眼会让画面逐帧变化，造成"动作在播"的**假阳性**。另外注意：idle 播完后 `state.currentGroup` 会**自动归 null**，所以"值变了"才说明有东西被触发。

### 3.3 `Meta.Loop` 被忽略 → 但**不要**用前端定时器假装循环

vendored 0.4.0 的 cubism4 模块里 `setIsLoop()` **有定义、全 bundle 无调用点**，`Meta.Loop:true` 被无视，
动作播完即停。用定时器"到点重开"是**陷阱**：`startMotion` 是 async（返回 Promise），
`mm.startMotion(...) !== false` **恒成立**，于是被 `state.reserve()` 以
`"Motion is already playing"` 拒绝时前端完全无感，而重开定时器又照原周期重新武装 →
实测 idle 播 9.1s 后**冻结 9.2s**（`currentGroup=null`、队列 0 条、参数纹丝不动），50% 占空比。

正确修法（三行，交回运行时）：
```js
// ① 把 Meta.Loop 灌进 CubismMotion 本体（核心会自己做时间回绕：f>duration 就减 duration）
const orig = mm.createMotion.bind(mm);
mm.createMotion = (json, group, def) => { const m = orig(json, group, def);
  if (group === idleGroup && json?.Meta?.Loop && m.setIsLoop) {
    m.setIsLoop(true); m.setIsLoopFadeIn?.(false); }   // ← 后者必须设！
  return m; };
// ② 对齐库自带的"播完自动回 idle"：默认值是 'Idle'，与我们的 'idle' 不匹配 → 一直静默失效
mm.groups.idle = idleGroup;
```
⚠️ **`setIsLoopFadeIn(false)` 不能漏**：否则每次回绕都会 `setFadeInStartTime(now)`，
淡入权重每循环归零重爬一遍，观感 = "每隔 N 秒身子被拽回去"。
设了 ①② 之后**前端不需要任何动作计时器**，回落 idle 由库逐帧接管。

### 3.4 `_startMotion` 里的 `stopAllMotions()` 让动作切换**完全没有交叉淡化**

库的 cubism4 管理器每次起动作都先 `queueManager.stopAllMotions()` → 旧动作被瞬间掐死，
姿态硬跳（观感 = "动作不对、身子拧着、穿模"）。而队列管理器自己的 `startMotion`
**本来就会给现存条目 `setFadeOut()`** —— 所以只要不再调 stop 就恢复官方交叉淡化：
```js
mm._startMotion = (m, onFinished) => { try{ m.setFinishedMotionHandler(onFinished); }catch(e){}
  return mm.queueManager.startMotion(m, false, performance.now()); };
```
配合 3.3 的循环动作要注意：`_isLoop=true` 时 `getDuration()` 返回 −1 → `endTime=-1` →
淡出权重恒 1；但条目被 `setFadeOut` 触发淡出时 `startFadeOut` 会把 `endTime<0` 改成
`now+fadeOut`，所以**循环动作仍能正常淡出退场**，不会赖着不走。

### 3.5 运行时自加的 Cubism2 式「呼吸层」——Cubism4 模型必须关掉

`Cubism4InternalModel` **无条件**挂 `CubismBreath`，每帧在动作**之后**再 ADD 五个参数：
`ParamAngleX ±7.5°@6.5s / Y ±4°@3.5s / Z ±5°@5.5s / ParamBodyAngleX ±2°@15.5s / ParamBreath ±0.25@3.2s`。
而 Cubism4 模型的动作**本来就自带**这些参数的动画（碧蓝全库 74~85% 的 idle 有）→ **头部双驱动**，
观感 = "一直在有点快地动、不自然"。铁证：游戏侧 bundle 的 MonoBehaviour 组件清单
（`CubismMoc/Model/Parameter/PhysicsController/Raycaster/MouthController/Live2dChar`）里**根本没有 Breath**。
```js
internalModel.breath?.setParameters([]);   // 关掉，播放完全等于动作数据本身
```
（`updateFocus()` 也是每帧 ADD，但 `autoInteract:false` 时 focusController 恒为 0，无害。）

### 3.6 判定区/淡入淡出/Groups 别自己拍脑袋，跟权威实现对齐

model3.json 里三处最容易自以为是：
- **淡入淡出**：给每条动作硬写 `FadeInTime/FadeOutTime:0.5` 会让"回落 idle"比运行时默认
  （idle 组 **2s**、其余 0.5s）快 4 倍 → 反应没收尾就被拽回去。**不写**才交给运行时默认。
  若 idle 带大量定值曲线，2s 淡出会在点击后继续拖尾 2 秒把参数往回拽 → 显式拆开
  `FadeInTime:2.0, FadeOutTime:0.5`（库里这两值默认共用同一个 idle 常量，只能显式覆盖）。
- **`Groups`** 缺 `EyeBlink`/`LipSync` 时 `internalModel.eyeBlink` 直接是 undefined（模型不眨眼）。
- **`HitAreas` 不止 Head/Body/Special**：moc3 里可能有几十个 `Touch*` 标记（碧蓝安土有 76 个：
  `TouchDrag1-24`、`TouchIdle1-47`）。只登记三个 → 点其它区域毫无反应。
  补登时务必实测**新框与核心框是否重叠**（安土实测零重叠才敢上）。

### 3.7 销毁与泄漏

`app.destroy(true,{children:true,baseTexture:true,texture:true})` 不会移除 `window` 级监听。把所有监听存进状态对象并提供 `off()`，切换标签/关闭弹窗时统一调用：

```js
state.off = () => { ro.disconnect(); wrap.removeEventListener(...); window.removeEventListener('pointermove', onMove); ... };
```

### 3.8 clip 驱动过的参数无人回写 → 模型整体移位、判定区全丢（"进去就出不来"）

**症状**：某个动作（安土 `touch_idle1`）播完之后判定区集体失效。实测画布 20×16 模型单位，静止态 57 个判定区已有 53 个在画布外（编辑器遗留的停放标记，只有核心 3 个 + `touch_idle1` 真可点）；播完这条 clip 后 **57 个全部出画**，核心三个一起被甩到同一点 `(-36.37,-52.81)`，回到 idle 也不恢复。

**根因**：Cubism 只对"本 clip 有曲线的"参数施权，**缺曲线的参数停在上一个动作留下的值上**。该 clip 252 条曲线里 **15 条 `idle` 从不驱动**（含整体位移）→ clip 末帧值永久残留。游戏侧靠 `change_in`/`home` 状态机复位，Web 运行时没有状态机，所以同一份数据在游戏里不暴露。（导出侧同一条机制见 §6.5「`m_ConstantClip` 定值曲线不是惰性的」。）

**定位 = 参数集求差，不靠猜**：对 motion3.json 取 `{c.Id | c.Target=="Parameter"}`，算 `clip集 − idle集`。
⚠️ `Id` 有两种形态，纯字符串 或 `{string:"ParamX"}`，判据要兜两种：
```js
const curveId = c => typeof c.Id === 'string' ? c.Id : (c.Id && c.Id.string) || null;
```
差集非空即锁定嫌疑人。

**修法**：复用 §3.3 那个 `createMotion` 补丁顺手登记每组参数集（零额外请求），`play()` 里 `if (g !== idleGroup) played.add(g)`，再用一个 ticker 回写：

```js
const restTick = () => { const cg = mm.state?.currentGroup;
  if (cg && cg !== idleGroup) { rest = null; return; }               // ② 只在回 idle/队列空时才动
  if (!rest) { const idleS = paramSets[idleGroup]; if (!idleS || !played.size) return;
    const want = new Set();                                          // ① 只碰播过的 clip 驱动过的参数
    played.forEach(g => (paramSets[g] || new Set()).forEach(p => { if (!idleS.has(p)) want.add(p); }));
    played.clear(); const items = [];
    want.forEach(p => { let i = -1; try { i = cm.getParameterIndex(p); } catch (e) {}
      if (i >= 0) try { items.push([i, cm.getParameterValueByIndex(i), cm.getParameterDefaultValue(i)]); } catch (e) {} });
    if (!items.length) return;
    rest = { items, t0: performance.now() + REST_DELAY }; return; }  // ③ 先等上一条淡出跑完
  const el = performance.now() - rest.t0; if (el < 0) return;
  const k = Math.min(1, el / REST_MS);
  for (const it of rest.items) try { cm.setParameterValueByIndex(it[0], it[1] + (it[2] - it[1]) * k); } catch (e) {}
  if (k >= 1) rest = null; };
app.ticker.add(restTick);   // REST_DELAY=400, REST_MS=700
```

三道防误伤约束：① 只处理「播过的 clip 驱动、idle 不驱动」的参数，物理/眨眼/口型等 clip 无关参数一律不动；
② 只在回到 idle（或队列空）时触发；③ 先等 `REST_DELAY` 让淡出跑完，再线性渐变过去（硬赋值会跳帧）。
目标值取 **moc3 默认值**（`getParameterDefaultValue`）而非"进动作前的快照"：这些参数在静止态本就没人动，
默认值 ≡ 静止位，且与快照时机无关。

**坑：`paramSets[idleGroup]` 为空 ⇒ 复位永远不触发**（那个 `if (!idleS) return` 是静默的）。
当 idle 的 motion 在补丁挂上**之前**就被创建时发生——库的预加载分支是
`switch (config.motionPreload) { default: e = [this.groups.idle] }`，所以 `motionPreload:'ALL'`
或组名恰为库默认的 `Idle` 时必踩。本项目组名是小写 `idle` 而 `mm.groups.idle` 要到 §3.3 的补丁里才被改成小写，
默认路径不预加载、侥幸躲过——但**判据必须显式断言 `paramSets[idleGroup]?.size > 0`**。
兜底做法：另 fetch 一次 idle 各条 json 登记参数集，顺带补 `Meta.Loop`（同一份 json，别开第二条管线）。

## 4. 按部位点击触发（HitAreas）

游戏里的 Live2D 是**点击部位**触发（不是悬停）。数据在 `model3.json` 顶层 `HitAreas`：

```json
[{"Id":"TouchHead","Name":"Head"}, {"Id":"TouchBody","Name":"Body"}, {"Id":"TouchSpecial","Name":"Special"}]
```

- **`HitAreas[].Name` 通常就是动作组名**（本项目 256 模型 768 个判定区对 `FileReferences.Motions` 键 **768/768 精确匹配**）。先跑一次全库统计验证这个假设，别凭直觉找 `tap*` 组——多数模型根本没有裸 `tap` 组，于是"点哪儿都不动"。
- 取判定几何：`idx = coreModel.getDrawableIndex(a.Id)`，再 `coreModel.getDrawableVertexPositions(idx)`（模型单位，x/y 交替）。**点击瞬间实时读，不要缓存**——框会随呼吸/物理每帧位移，缓存坐标会点空。
- 坐标换算：`const lp = mdl.toLocal(new PIXI.Point(屏幕x - wrapRect.left, 屏幕y - wrapRect.top)); const 单位 = lp.x / internalModel.pixelsPerUnit`。
- **判定形状 = 部件的真实四边形（两三角），不是它的轴对齐包围盒**（2026-09-23 二次修订，推翻本条旧结论）。
  游戏侧 `CubismRaycaster` 就是对 `Touch*` 部件做三角形 raycast。这些标记是 4 顶点不可见 quad，
  **部分模型的 quad 是斜的**：四边形面积/包围盒面积比 = `yingrui_3` 0.489~0.755、`z46_3` 0.645~0.942，
  用包围盒等于把判定区放大最多 2 倍 → 点旁边空地也触发（用户报"有些点击不准"）。
  正矩形模型（碧蓝安土 `antu_2` 等，比值 1.000）两种判定**逐点等价**，零行为变化。
  ⚠️ **本条旧结论"三角面反而更差、包围盒 767/768"是错的**：那次实测是在**坐标系换算还没修对**时做的，
  且试图用 `coreModel.getDrawableIndices()` —— **该方法在 live2dcubismcore 的 Model 包装上根本不存在**
  （只有 `core.drawables.indices[i]`），拿到 undefined 后判定全崩，被误当成"三角面数据不规整"。
  正确做法：4 顶点按**三角带序**拆成 `(v0,v1,v2)+(v1,v3,v2)`，无需索引缓冲；实测 5 个模型
  `带序面积 == 凸包面积`，证明带序假设成立。包围盒只当**快速预筛**用。
- **顶点序是三角带，画多边形必须换环序**：`getDrawableVertexPositions` 给的是 `(TR,TL,BR,BL)` 带序，
  直接 `drawPolygon(v0,v1,v2,v3)` 会连成**自交蝴蝶结**。无自交环序是 `[0,1,3,2]`。
- 多个框同时包含时（部位框常重叠/嵌套）取**面积最小的框**（最具体的部位优先）。
  旧的"归一化中心距离就近取"在嵌套框上会选到大框；改最小面积后安土等正矩形模型行为不变，
  `yingrui_3`/`z46_3` 的斜框误伤被剔掉（实测收窄 26.4%）。
- 容差只给 **2%**（吸收测试派发延迟的几十毫秒位移）。给到 8% 会把视觉上明显空白的角落判成命中——Live2D 画布四周有大量透明边距，模型单位范围比可见内容大得多。
- **兜底动作只给没有 `HitAreas` 的模型**。有判定区却点框外，就什么都不播（与游戏一致）。否则点哪儿都蹦一个 `touch_drag*`，观感极差。前端配套：`fallbackG = hitAreas.length ? null : <兜底组>`——`hitAreas` 非空时把兜底组设为 `null`，才会出现"点框外不播"；否则形同空壳。

## 4.5 生成真实 HitAreas（修补占位 Id，2026-09-22 碧蓝航线实测）

§4 讲的是**消费**已有 HitAreas；本节讲**如何为占位模型批量生成正确 HitAreas**（`fix_model3.py` 一类管线）。典型根因：还原管线早期只往 `model3.json` 补占位 Id `HitArea/HitArea2`，而前端 `getDrawableIndex("HitArea")` 取不到 drawable → 判定区被过滤成空 → 点部位退化成兜底乱播。

- **保守只替换占位 Id**：仅当某模型现有 `HitAreas[].Id ⊆ {HitArea, HitArea2}` 时才改写；已带正确 Id 的模型**一律不动**。这样"256 个既有模型零回退"是**构造性保证**（压根不进改写分支），不靠事后校验兜底。
- **`Id`**：碧蓝统一用 `TouchHead/TouchBody/TouchSpecial`，须能被 `getDrawableIndex(a.Id)` 解析（返回值 `≥0`）。**改写前先逐字节探针确认该 drawable 真的在 moc3 里**——判据是 `getDrawableIndex("TouchHead") >= 0` **且** `getDrawableVertexPositions(idx)` 非空（如 4 点 = `vlen=8`）。只有**部件名**（Part）不算，必须是**drawable**，否则前端仍取不到框。
- **`Name`**：必须是**该模型真实存在的动作组**，即能在 `FileReferences.Motions` 的键里找到。按候选顺序取第一个命中的（小写回落，兼容不同命名世代）：
  - `Head → [Head, head, tapHead, taphead, tap_head, touch_head, TapHead]`
  - `Body → [Body, body, tapBody, tapbody, tap_body, touch_body, TapBody]`
  - `Special → [Special, special, tapSpecial, tapspecial, tap_special, touch_special, TapSpecial]`
  经验：老模型组名是 `Head/Body/Special`，新换入模型是 `touch_head/touch_body/touch_special`——两代都要覆盖，只认其一就是"点哪儿都不动"的来源。
- **改后必须证"仅该字段变"**：跑前对全部 `model3.json` 快照 `(path, mtime, sha256)` 清单，跑 `fix_model3` 后 diff → 断言"**仅 N 个文件变、且每个文件仅 `HitAreas` 字段变**"（顶层键集合不变、`changed_fields == ['HitAreas']`）。任何其它字段被顺带改动 = 回退，立即排查。
- **收尾**：`hit_verify --only <这批 key>` 逐个证 **3/3 命中**（点击各 drawable 框中心 → `state.currentGroup == HitAreas[].Name`）；再全库复跑确认命中数增量 == 新启用的判定区数（本项目 13 模型 × 3 = +39，768→807、767→806，同一 `z46_3` 嵌套框歧义为既有非回退项）。

## 5. 构图与 fit 的两个陷阱

1. **别用 `mdl.width` 当模型尺寸**：pixi-live2d-display 下它可能返回 1 或被污染的包围盒（个别模型被巨型离屏 quad 撑到百万像素）。可靠基准是 `internalModel.width / internalModel.height`（= Cubism 画布单位 × `pixelsPerUnit`，如 8000×8000）。
2. **`fit()` 必须幂等**：`DisplayObject.width` 已含 `scale`。若在 fit 里用 `mdl.width` 算缩放，`ResizeObserver` 二次触发时会**正反馈放大**，画面糊成局部特写。做法：加载后缓存未缩放尺寸（或直接用 `internalModel.width`），维护 `baseK(适配) × z(用户缩放)` 与偏移 `ox/oy`，`apply()` 统一由这三者算 scale 与位置；`fit()` 只是把 `z/ox/oy` 归零后 `apply()`。

## 6. 交互层反模式

- **不要 `preventDefault` 劫持裸滚轮**。鼠标经过模型时用户可能正在滚页面，被劫持后页面不动、模型一路放大并累积平移，看起来像"模型自己乱动、位置不对"。改成 **Ctrl/⌘/Alt + 滚轮**才缩放，并在提示文案里写明。
- 拖拽必须处理 `pointercancel` 与 `window blur`，否则拖拽态卡住，之后每次鼠标移动都在平移模型。
- 平移量要钳制（如 `max(wrapW,wrapH)*0.6`），防止把模型拖出视野再也找不回。
- 位移 < 6px 视为"点击"而非"拖拽"，用来触发动作。

## 6.5 motion 数据从哪来：Unity AnimationClip → motion3.json 的权威映射

（从 Unity AssetBundle 侧还原动作时的正确姿势，2026-09-21 碧蓝航线实测）

- **curve index ↔ `m_ClipBindingConstant.genericBindings[i]` 同序**；且
  `genericBindings[i].path = crc32("Parameters/<GameObject名>")`，部件是 `crc32("Parts/"+名)`。
  实测 946274 个绑定的解析率 99.77%（未解析的 0.226% 是第三类属性哈希，运行时无对应 motion target，只能跳过）。
  不是 sdbm/djb2/FNV——别再试别的哈希函数。
- `CubismParameter` 组件的 `m_Name` 是**空**的：真名挂在 **GameObject** 上，`_unmanagedIndex` 才是
  moc3 参数序号。被动画化的序号是**稀疏**的（实测 `lingbo/idle` = 0,1,2,8,9,12,13,14,15,18,…），
  所以**绝不能假设 "curve idx == 参数序号（从 0 连续）"**——这是"眼睛数据写进眉毛参数"的来源，
  模型会照常动，只是动得面目全非（乱飘/乱闪/个别没反应）。按组件枚举顺序取参数名同样是错的。
- StreamedClip 的**帧 0 是 `time=-3.4e38` 的参考姿态帧，一帧合法写完全部曲线**（大模型一帧 380~520 个 key）。
  任何 `if numKeys > N: break` 之类的"合理性护栏"都会在帧 0 崩掉整条动作；
  只能靠 `+inf` 结束符 + 缓冲区边界停。该帧要当作各曲线 t=0 的基准值，而不是当普通关键帧丢掉。
- **⚠️⚠️ 贝塞尔控制点是「绝对 (时间, 值)」，不是归一化分数**（2026-09-23 血泪根因）。
  段序仍是 `[1, c1x, c1y, c2x, c2y, 终点time, 终点value]`（终点在最后，官方没有第 5 个
  "interpolation" 字段），但运行时解析器是**直读不做任何还原**：
  ```js
  case Bezier:
    points[a]   = new j(seg[l+1], seg[l+2])   // (时间, 值) —— 绝对坐标
    points[a+1] = new j(seg[l+3], seg[l+4])
    points[a+2] = new j(seg[l+5], seg[l+6])
  ```
  若按归一化写 `[1, 1/3, by1, 2/3, by2, t, v]`，控制点会被读成「t=0.333 **秒**、值=0.667」——
  落在段外且值接近 0 → **每条贝塞尔都先猛蹿到≈0 再跳到目标值**。表现为"部件各动各的、
  像刚学建模的人做的、穿模"，而**曲线数/时长/参数名/量程全部校验都能通过**，极难自察。
  正确写法 = Unity 三次 Hermite 的等价控制多边形：
  `c1=(t0+dt/3, v0+outSlope·dt/3)`、`c2=(t1−dt/3, v1−inSlope·dt/3)`。
- **但"格式正确"≠"效果正确"**：Unity **密集键**（相邻键 ≪ 周期）的那对切线字段本就不该当 Hermite
  切线用，照上面算会飞出几百个参数单位。碧蓝实测三种写法对权威基准的逐曲线偏差（121 点采样）：
  | 写法 | 偏差中位 | 偏差>0.5 的曲线 | 最甚 |
  |---|---|---|---|
  | 归一化控制点 | 1.376 | 92/98 | 9.35 |
  | 绝对控制点·全贝塞尔 | 0 | 88/278 | **296** |
  | **关键帧 + 线性**（采用） | 0 | 11/278 | 1.95 |
  → 从 Unity AnimationClip 反解时，**默认就该发线性段**；`|dv|<1e-3·max(1,|v0|,|v1|)` 的退化线性
  与 `|by|>3` 拉直都是掩盖格式错误的权宜，别当成优化保留。
- **`Meta` 要对齐**：`Fps` 取 `AnimationClip.m_SampleRate`（别硬编码 30）；`AreBeziersRestricted:true`
  的含义是"控制点横向恒在 1/3、2/3"→ 运行时走朴素参数化求值（不解三次方程），与上面的发法自洽。
- **⚠️ Unity 曲线分装在三个容器，只读 `m_StreamedClip` 会丢数据**：
  `m_Clip.data` 有 `m_StreamedClip` / `m_DenseClip` / `m_ConstantClip`，
  而 `genericBindings` 的顺序 = **[streamed][dense][constant]**（实测 98+0+180=278 且名字零冲突）。
  `m_ConstantClip` 是"整段保持定值"的曲线，**不是惰性的**：Cubism 只对"本 clip 有曲线的"参数施权，
  缺曲线的参数在切动作时**停在上一个动作留下的值上** → 被 `touch_*` 动过的手臂回不到静止位 → 部件错位。
  参考实现的 `idle` 曲线数正是 streamed+constant 之和。**务必一并导出定值曲线**
  （`Segments:[0, v, 0, duration, v]`，每条 1 段 2 点）。
- 运行时**完全不读 `pose3.json` / model3 的 `Pose` 键**（该字符串在 pixi-live2d-display 里出现 0 次），
  但支持 motion3 的 `Target:"PartOpacity"` → 换装/部件可见性只能写进 motion3.json，出 pose3 是死路。

### 6.6 `Textures` 清单是**按索引**消费的：枚举序必须显式归一 + 闸门 + 看图

`model3.json` 的 `FileReferences.Textures` 数组，运行时把第 i 项绑给 moc3 的**纹理索引 i**。
moc3 文件里**不含任何贴图名**（碧蓝 269 个 moc3 全量搜不到 `texture_*.png` 字符串），
所以"哪张图是索引 0"这件事**只能由清单顺序决定**，错了不会报错、只会画面碎。

- **典型症状**：模型加载成功、动作在播、参数在动，但画面是"几十个部件碎片叠一堆"
  ——每个 art mesh 从别的图集里采样。背景层（往往集中在某一张图）看起来还大体成形，
  这反而最容易骗人："渲染出东西了"被当成"渲染对了"。
- **导出侧的坑**：从 Unity bundle 落贴图时用的是序列化对象的**枚举顺序**，
  它 ≠ 索引顺序。碧蓝实测 **51/269 个模型两者不一致**（最狠的一个 6 张图枚举成 `[02,05,00,03,04,01]`）。
  也就是说这一步**必须在写完后显式归一**，不能指望生产方的迭代顺序；
  归一化是承重步骤，不是装饰。
- **归一规则**：按名中数字排（`texture_%02d` 的编号即索引），无数字者排在带数字之后按名称序。
  前提是先全量确认命名齐整（碧蓝：`非 texture_%02d 命名 = 0`），否则"编号即索引"这条约定不成立。
- **闸门**（退出码即判据，只读检查、`--apply` 才写）：`l2d_texorder_check.py`。
- **完整性对账**（另一类静默失败：解码 `except: continue` 悄悄少一张，结构仍合法）：
  逐模型比 源 bundle 的 `Texture2D` 清单 vs 磁盘 PNG，报 `missing / extra / 命名异常`。
- **⚠️ 验收必须包含"逐张看图"**：加载成功、`getDrawableCount()`、参数跨帧 min/max、帧哈希在变——
  在错绑这一类故障下**全部为真**。代理指标只能证"没死"，不能证"对"。
  看图工具要现成（否则它自然被代理指标顶替），且**判据要写明"和什么比"**：
  本技能实测把一张"人躺在地上、腿朝镜头"的正常前缩透视误判过一次"姿势反常"，
  拿同皮肤的静态立绘一比即证伪。可比对象优先级：同皮肤静态立绘 > 同批未改动对照组 > 权威外部实现。

## 7. 无头验证判据（配合 CDP）

### 7.0 自研管线必须找**外部权威实现**做基准，自证清白一定会漏

**教训**：碧蓝 Live2D 的 motion3.json 控制点格式错了整整一个量级（见 §6.5），但
曲线数、时长、参数名映射、量程、空壳率**全部校验通过**，`hit_verify` 也是 806/807 全绿——
因为这些都只验证"结构自洽"，不验证"和原作一样"。用户反馈"部件各动各的、像刚学建模的人做的"
持续了好几轮，我先后误判成呼吸层、误判成插值护栏，**直到拿到同模型的权威导出才一次锁定**。

可用的外部基准（同一批游戏模型、成熟 Cubism 实现）：
```
https://static.l2d.su/azurlane/live2d/<key>/<key>.model3.json
https://static.l2d.su/azurlane/live2d/<key>/motions/<组>.motion3.json   # 注意 motions/ 复数
```
路径规律是从它的 SPA bundle（`/assets/index-*.js`）里 grep `model3.json` 模板反查出来的；
只覆盖部分模型（抽样 8/14），404 就跳过。比对**逐曲线按运行时真实语义采样求值**
（linear 插值 / stepped 取起点 / bezier 在 `AreBeziersRestricted` 下用归一化时间直接当贝塞尔参数），
判据：组与曲线集合零缺失、**关键帧零不一致**、偏差中位 ≤0.5、偏差>0.5 占比 ≤12%
（12% 是按"结构完全正确时的真实残差"校准的，不是拍脑袋）。

**没有外部基准时的次优锚点**：① 目标实现的录屏/截图做目视基准；② 用**不经过被测映射**的
可见语义点反查（如"屏幕上的头/胸/髋三点应分别落入对应判定框"）；③ 逐字段 diff 对照组证零回退。
只做"自己算一遍再和自己比"的回归 = 验证自洽性，不是验证正确性。

- **判"动作真的有效"要同时满足两条**：① 正在播的 motion 的 `_motionData.curveCount > 0`；
  ② 取该 motion 自己的曲线 Id，`getParameterValueById` / `getPartOpacityById` 的值随时间变化。
  只看 `state.currentGroup` 变了没有，会让 `"Curves": []` 的空壳全部绿灯通过
  （本项目就曾因此报出"260/260 全通过"，而实际 57% 是空壳、其余曲线名全错）。
  按部位点击的断言同理：别只断言组名标签，要断言内容。
- **采样必须在 clip 时长内高频密采，不能在载入若干秒后才比对两点**：本项目运行时把**每条 idle 都解析成 `isLoop:false`**（与 motion3 的 `Meta.Loop:true` 无关），idle 播完一遍即回静帧、`state.currentGroup` 归 null、参数回落到基准。若"载入→等 9~12s→两次快照逐参数相减"，短 idle（5~8s）早已播完 ⇒ 假报 `moved=0`（曾据此误判新换入的 `bunao_3`/`guanghui_9` 坏了）。**正确做法**：载入并进入该 clip 后，每 ~420ms 推一帧（手动 `PIXI.Ticker.shared.tick()+app.render()`）、**累积每个参数跨帧 min/max**，判据=「播放窗口内 `max-min>1e-3` 的参数条数 > 0」。另注意手动 `startMotion(group,0,FORCE)` 会与页面自动播相互打断，验证"用户打开即所见"时**别再手动 startMotion**，直接密采。

批量验证 260 个模型时的做法（驱动细节见 `headless-chrome-cdp-batch-export`）：

- 页面内串行遍历：`await renderLive2D(ship, sk)` → 等 1.5~2s → 读 `state.currentGroup` 与 `motionManager.definitions` 数。每轮先 `stopLive2D()` 释放，否则 WebGL 上下文/纹理堆积。
- 断言落在**产品语义**上，不要落在"我猜它不该命中"上。例：断言"有判定区的模型任何点击都不该播出 `touch_*/tap*` 兜底组"，而不是"点某个自算的空白点不该有反应"——后者会因 `toGlobal → 屏幕坐标 → toLocal` 往返误差在极端点被放大而恒失败。
- 冷启动（删过 profile 后）页面里访问 `window.GALLERY` 之类全局数据要先轮询等待，否则 `ReferenceError`。
- **两个 chrome 实例并发跑 CDP 会互相抢**，报 `Execution context was destroyed`；批量验证要串行。
- 清理残留 chrome 必须按 `--user-data-dir` 精确匹配进程命令行再 kill，**绝不能按进程名全杀**（会误杀用户自己的浏览器）。

### 7.1 全库规模（数百模型）必须分批起新 Chrome

上面"每轮 `stopLive2D()` 释放"只能撑一小段：**单个 headless Chrome 顺序加载约 110 个模型后 WebGL 上下文耗尽**，CDP 连接断，报 `Connection to remote host was lost`（标签崩溃），与 `l2d_sweep` 的"单次 evaluate 卡住/断连"同类。靠单进程 + 手动释放扛不住全库，必须**换成分批新进程**：

- **切批**：用 `--only "k1,k2,..."` 逗号清单把模型切成 **~40 个一批**（本项目 269 → 4 批），**每批一个全新 Chrome**（每次调用只起一次进程），而不是一个长循环从头跑到尾。
- **冷启动首模型易报错**：每批新进程加载的第一个模型常撞 `window.GALLERY 未就绪` / `stopLive2D is not defined`（harness artifact，非模型问题）。对策：给每批 `--only` 清单**头部塞一个已知良好的预热模型**（如 `lingbo`，不计入统计），或对报错的首项单独复跑；一旦 warm 起来同模型即 3/3。
- **汇总口径 = 按 key 去重取最优**：合并所有分批日志，同一模型 key 在任一批 `ok` 即算 `ok`，避免某批崩溃漏记被误判成回退。
- 实测：分批后 **269/269 覆盖、806/807 命中**，唯一 miss `z46_3`（Special 框嵌套在 Body 内）是 §4 记录的既有"归一化中心距离"歧义，非本轮回退。

### 7.2 验证前端自己挂的逻辑，必须驱动页面的真实入口

复位、淡出、随机变体这类逻辑挂在页面的 `play()` 上（下拉框 onchange / 点击 handler / 按钮）。
探针直接 `mm.startMotion(g,0,FORCE)` 会**整层绕过它**，于是"复位没生效"其实是"根本没进被改的那段代码"——
2026-09-23 本项目就据此把一个**正确的**修复误判成无效。

```js
const sel = document.getElementById('l2Motion');
if (!sel) return JSON.stringify({ err: '动作下拉框不存在，无法走真实播放路径' });  // 不许回落假路径
sel.value = grp; sel.onchange();                        // ✓ 真实路径
// mm.startMotion(grp, 0, MP.FORCE);                    // ✗ 绕过前端交互层
const started = mm.state.currentGroup;                  // 必须回读：区分「静默失败」与「没复位」
```

handler 缺失时探针要**显式报错**，绝不回落到 `mm.startMotion` 继续测——回落等于自造假阴性。
验收判据（工具 `scripts/diag/l2d_touchidle_probe.py`）：before 出画 53 → mid 57（clip 生效）→
after **53（与 before 相等）**，且位移 >0.3 的判定区数 = **0**。

## 8. 落地检查清单

- [ ] 三件套版本成对且按序加载；vendor 相对路径在页面上下文里 `fetch` 验证过
- [ ] `startMotion` 显式 index + `MotionPriority.FORCE`
- [ ] 用 `state.currentGroup`（等待后）证明动作真的在播，不靠帧比对
- [ ] fit 基准取 `internalModel.width`，且 fit 幂等（ResizeObserver 多次触发不放大）
- [ ] 部位命中实时读框；兜底只给无 HitAreas 的模型；容差 2%
- [ ] 裸滚轮不被劫持；`pointercancel`/`blur` 解除拖拽；平移钳制
- [ ] `stopLive2D()` 里 `app.destroy()` + `off()` 都做
- [ ] 无头批量验证：全量命中率与失败清单，含"无判定区"模型列表
- [ ] 参数残留复位：断言 `paramSets[idleGroup]` 非空；「clip 驱动 − idle 驱动」差集写回 moc3 默认值；复位探针走页面 `play()` 入口，after 出画数 == before 出画数
- [ ] 全库规模（数百模型）分批起新 Chrome（~40/批），首模型预热重跑、各批日志按 key 去重取最优
- [ ] 补占位 HitAreas：Id 逐字节确认是 moc3 drawable、Name 取该模型真实存在的组（候选小写回落）、仅替换 Id⊆{HitArea,HitArea2}、改后 sha256 清单证"仅 N 文件且仅 HitAreas 字段变"
- [ ] `Textures` 清单按名中数字归一 + 闸门跑到退出码 0；源 bundle `Texture2D` 清单与磁盘 PNG 对账 missing/extra/命名异常全为 0
- [ ] **逐张看图**（走页面真实入口、按 canvas 裁剪只截模型区）：新 bundle 换入后必做，且指明"和什么比"；代理指标全绿不构成完成证据
