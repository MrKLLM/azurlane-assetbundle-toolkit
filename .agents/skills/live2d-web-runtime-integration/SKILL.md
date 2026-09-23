---
name: live2d-web-runtime-integration
description: 在网页里集成 Live2D Cubism Web 运行时做模型渲染与动作播放（pixi 6.5.2 + live2dcubismcore 5.1.0 + pixi-live2d-display 0.4.0 组合），覆盖 model3.json 加载、动作触发（startMotion 传参陷阱）、按部位点击触发（HitAreas 命中判定）、模型尺寸与 fit 基准、交互层反模式、内存销毁与无头 CDP 验证判据。当需要让 .moc3/.model3 模型在浏览器里"真的动起来"、或反馈"模型不动/乱抖/点不出动作/显示不全"、或要在国内网络下载 Live2D 运行时库时使用。触发词：Live2D 网页播放、Cubism 运行时、pixi-live2d-display、Live2DModel 动作、模型点不动、idle 不播、HitAreas 点击。不适用于 Live2D 模型文件的 AssetBundle 逆向还原（那是 unity-assetbundle-painting-restore）与纯截图导出（headless-chrome-cdp-batch-export）。
version: 1.0.0
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

## 3. 动作播放：三个必踩陷阱

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

### 3.2b 这个运行时的 Loop 是坏的：`_isLoop` 永远是 false（0.4.0 实测）

pixi-live2d-display 0.4.0 的 cubism4 模块里 `setIsLoop()` **只有定义、没有任何调用点**（对 min bundle 全文搜索证实），`Meta.Loop:true` 被完全无视——**每条 motion（含 idle）都只播一轮**，idle 播完即回静帧、参数回落基准。这不是数据问题，别去改 motion3.json。

前端兜底（看守者模式，已验证有效）：

```js
const armIdleLoop = () => { const tok = ++idleTok;
  motionMs(idleGroup).then(ms => {                    // 读 motion3 的 Meta.Duration
    setTimeout(() => {
      const cur = mm.state.currentGroup || null;
      if (cur === null || cur === idleGroup) {        // 没别的动作在播才重开
        mm.startMotion(idleGroup, 0, MP.FORCE);        // 提前 ~120ms 交叉淡入=无缝循环
        armIdleLoop();                                 // 自我再武装
      }                                               // 否则让该动作的回落定时器接管后重新武装
    }, Math.max(300, ms - 120));
  });
};
```

要点：① 每次 idle 启动（初始播放、动作回落）后都要重新武装；② 非 idle 动作的回落定时器（按时长+300ms 回 idle）保留，两者用 token 防重入、回落前检查 `currentGroup` 避免双启；③ 组件销毁时 token++ 作废全部挂起定时器；④ 每次 `startMotion` 都会重新 fetch+parse motion 文件（该库**无任何缓存**），轮换边界有短暂掉帧，真机可接受。

### 3.3 销毁与泄漏

`app.destroy(true,{children:true,baseTexture:true,texture:true})` 不会移除 `window` 级监听。把所有监听存进状态对象并提供 `off()`，切换标签/关闭弹窗时统一调用：

```js
state.off = () => { ro.disconnect(); wrap.removeEventListener(...); window.removeEventListener('pointermove', onMove); ... };
```

## 4. 按部位点击触发（HitAreas）

游戏里的 Live2D 是**点击部位**触发（不是悬停）。数据在 `model3.json` 顶层 `HitAreas`：

```json
[{"Id":"TouchHead","Name":"Head"}, {"Id":"TouchBody","Name":"Body"}, {"Id":"TouchSpecial","Name":"Special"}]
```

- **`HitAreas[].Name` 通常就是动作组名**（本项目 256 模型 768 个判定区对 `FileReferences.Motions` 键 **768/768 精确匹配**）。先跑一次全库统计验证这个假设，别凭直觉找 `tap*` 组——多数模型根本没有裸 `tap` 组，于是"点哪儿都不动"。
- 取判定几何：`idx = coreModel.getDrawableIndex(a.Id)`，再 `coreModel.getDrawableVertexPositions(idx)`（模型单位，x/y 交替）。**点击瞬间实时读，不要缓存**——框会随呼吸/物理每帧位移，缓存坐标会点空。
- 坐标换算：`const lp = mdl.toLocal(new PIXI.Point(屏幕x - wrapRect.left, 屏幕y - wrapRect.top)); const 单位 = lp.x / internalModel.pixelsPerUnit`。
- **用包围盒，别用三角面**：本项目实测改用 Cubism 原生"点在三角面内"后反而更差——部分模型的 Touch 三角面**连自己的顶点重心都不包含**（数据不规整）。包围盒实测 767/768。
- 多个框同时包含时（部位框常重叠/嵌套）取**归一化中心距离**最小者：`s = dist(点, 框中心) / max(半宽,半高)`。注意"按顺序取第一个"会让大框（如 Head）永远压住小框；"取最小框"在另一种模型上又错——两种规则各有反例，选一个并记录已知歧义，不要为个别样本过拟合。
- ⚠️ **必须先做「点在框内」包含判定，再谈就近取框**（2026-09-23 碧蓝航线实测踩坑）：曾写成「全图取最近框」而无包含判定 → 点画布任意位置（含视觉空白处）都触发最近部位动作，用户报"悬停/乱触发、动作赶着做完"（动作被反复打断的观感）。正确顺序：`|mx-cx|<=半宽+容差 && |my-cy|<=半高+容差` 才参与竞选，全不命中返回 null。
- 回归脚本断言键名必须与脚本实际输出键名一致：曾把输出 `noAction` 断言成不存在的 `noFallbackGroup` → 该项**恒不触发、永远绿灯**，"点空白不播"半年未被执行过。改判据后必须用一个已知失败样本验证断言确实会变红。
- 容差只给 **2%**（吸收测试派发延迟的几十毫秒位移）。给到 8% 会把视觉上明显空白的角落判成命中——Live2D 画布四周有大量透明边距，模型单位范围比可见内容大得多。
- **兜底动作只给没有 `HitAreas` 的模型**。有判定区却点框外，就什么都不播（与游戏一致）。否则点哪儿都蹦一个 `touch_drag*`，观感极差。

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
- **贝塞尔段序：`[1, c1x, c1y, c2x, c2y, 终点time, 终点value]` —— 终点在最后**，官方没有第 5 个"interpolation"字段。
  且 `segments` 数组是按 `Meta.TotalSegmentCount` **预分配**的：计数少算一位，浏览器里就抛
  `Cannot set properties of undefined (setting 'basePointIndex')`，而前端只表现为"这个模型点了没反应"。
  → 写完必须按运行时的消费方式重放一遍自检（首对 l+=2/点+1，线性 l+=3/点+1，贝塞尔 l+=7/点+3）。
- Unity 切线换 Cubism 归一化控制点时，`dv≈0` 会把控制点顶到 `by=14.9` 这种量级反而抖；
  `|dv| < 1e-3·max(1,|v0|,|v1|)` 或 `|by|>3` 时退化成线性段。
- 运行时**完全不读 `pose3.json` / model3 的 `Pose` 键**（该字符串在 pixi-live2d-display 里出现 0 次），
  但支持 motion3 的 `Target:"PartOpacity"` → 换装/部件可见性只能写进 motion3.json，出 pose3 是死路。

## 7. 无头验证判据（配合 CDP）

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

## 8. 落地检查清单

- [ ] 三件套版本成对且按序加载；vendor 相对路径在页面上下文里 `fetch` 验证过
- [ ] `startMotion` 显式 index + `MotionPriority.FORCE`
- [ ] 用 `state.currentGroup`（等待后）证明动作真的在播，不靠帧比对
- [ ] fit 基准取 `internalModel.width`，且 fit 幂等（ResizeObserver 多次触发不放大）
- [ ] 部位命中实时读框；**先做框内包含判定再就近取框**；兜底只给无 HitAreas 的模型；容差 2%
- [ ] idle 持续 Alive：看守者已武装且回归脚本能证明「加载 12s 后 currentGroup 仍为 idle」
- [ ] 裸滚轮不被劫持；`pointercancel`/`blur` 解除拖拽；平移钳制
- [ ] `stopLive2D()` 里 `app.destroy()` + `off()` 都做
- [ ] 无头批量验证：全量命中率与失败清单，含"无判定区"模型列表
