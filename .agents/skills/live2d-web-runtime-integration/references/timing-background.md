<!-- live2d-web-runtime-integration 参考件 · §18-21 倍速时钟/重播连点/背景层限帧/用户背景 · 按需加载，正本见 SKILL.md -->

## 18. 倍速 / 时间缩放：动作时钟吃的是 `update()` 的**第二个参数**（2026-10-16 实测）

**需求形状**：给播放器加 0.1×–2× 倍速滑杆（或任何"让动作快/慢下来"的改动）。

**先查清库的时钟，再动手**。pixi-live2d-display 0.4.0（cubism4）的链条是：
```
onTickerUpdate(){ this.update(Ticker.shared.deltaMS) }      // Live2DModel：只做累加
update(t){ this.deltaTime+=t; this.elapsedTime+=t }          // 两个累加器
_render(){ this.deltaTime && (this.internalModel.update(this.deltaTime, this.elapsedTime), this.deltaTime=0) }
Cubism4InternalModel.update(t,e){ super.update(t,e); t/=1e3; e/=1e3;
  this.motionManager.update(this.coreModel, e) }              // ← 动作时钟 = **e（绝对时间）**
```

- **缩放 dt（第一个参数）对动作完全无效** —— 实测包住 `im.update` 把 `a[0]*=2`，
  用长坡参数当尺子量出来仍是 **1.02×**。dt 只喂物理/眨眼那几条。
- 库里**没有** `speed` 属性（整包 `grep -c speed` = 0），别去猜这个入口。
- **正解 = 自建虚拟时钟**：把「缩放后的 dt」和「自己累出来的绝对时间」一起喂回去：
  `im.update=function(dt,el){ const d=dt*k; vEl+=d; return orig(d, vEl); }`。
  虚拟钟从 0 起算没问题（管理器只吃差值，起播起点也来自同一条钟）；
  `autoUpdate=false`（暂停）时 `update()` 不被调用 ⇒ 虚拟钟也不走，**恢复不跳**。
- **范围要说清**：页面自己的外挂层（环境层/残留复位/开关钉住）若按 `performance.now()` 计时，
  它们**不随倍速变**。这是设计选择（环境层在源包里本就是独立 loop），但必须在注释与文档里写明，
  否则下一轮会被当成漏改。

**验收必须用比值，不能用绝对速率**：无头 swiftshader 下渲染慢，PIXI ticker 把 `deltaMS`
钳在 100ms（`_maxElapsedMS`）⇒ 模型时钟本来就只按墙钟的 ~0.6 倍推进（实测 1× = 0.59）。
钳位对各倍速一视同仁，所以：① 量 `vEl` 斜率之比 ≈ 倍速；② 量一个**离散事件**——
`Meta.Loop=false` 的整条动作「播完」那一刻的虚拟秒（1× 应当正好≈ clip 时长）。

**⚠️ 别拿"某个参数的轨迹"当时间尺子**（本页实测否证）：`GL1` 在 motion3 里只有首末两个作者键、
看着是天赐的线性斜坡，但它的**活值不是原始曲线** —— 用它反推时间，clip/虚拟钟 偏 **2.83 倍**，
把环境层关掉（`__ambOff`）反而偏到 **4.12 倍**。⇒ 凡是要用参数轨迹反推时间的判据，
**先证它的活值真的跟曲线走**（同一页里可能有别的写入者/插值路径）。
同理，**墙钟比值也不能断言 2.0**：无头停帧对 2× 的伤害比 1× 小，比值会被压扁（实测 1.46），
只可作方向性断言。

**探针自身的两个坑**：① 别靠"每趟之间等参数回落到起点"来重置（重播是从上一条动作淡过来的，
不等就两段门槛在同一拍一起越过 → 测得 0，探针还除零崩过）⇒ 判据要选**与重播无关**的量；
② CDP 在页面导航时会 `Execution context was destroyed`，要退避重试，别当成产品失败。

**配套**：给页面留一个 `window.__speedDbg=()=>({speed, vEl, real})` 钩子 —— 它把
"我的钟没按倍速走"和"库不吃这个时间参数"两种完全不同的失败分开，省掉一轮盲猜。

## 19. 重播 / 连点同一部位：`reserve()` 拒绝 × snapPending 误钉（2026-10-16 实测）

**需求形状**：播放中连点同一部位 / 点重播键，期望"立刻从头重播"，实际动作原地不动
（只重播语音）；或重播后出现"手势短暂错误 / 手消失一闪"。

**两条独立机制，先分清再修**：

1. **`reserve()` 拒绝"正在播的同一组"**：pixi-live2d-display 的 MotionManager 在
   `reserve(t,e,i)` 里 `if(t===this.currentGroup&&e===this.currentIndex) return false`
   （"Motion is already playing"）→ `startMotion` 直接返回 `ok=false`，**不真正起播**。
   `startMotion` 还是 async 的（`yield loadMotion` 之后才走 `state.start()`），
   拒绝发生在早于任何起播动作的位置。
2. **重播键要自走 `stopAllMotions()`**：先 `mm.stopAllMotions()`（内部 `_stopAllMotions()`
   + `state.reset()` 清掉 currentGroup/currentIndex）再 `play(sel)`，reserve 才不会拒绝。
   只重新走 `startMotion` 会被库拦下，看起来就是"只有语音重播、动作不重播"。

**核心坑：把"起播"记错的置位点**。包装器若无条件在自己开头置 `snapPending=true`（本页体系里
"下个 beforeMotionUpdate 执行某次钉值/回贴"的标志），reserve 拒绝时实际**不会**重新起播，
但标志已经置上 ⇒ 后续 beforeMotionUpdate 误判"动作变了" ⇒ snapHold 把**正在播的**动作的
关键参数（如手上 Param27/25）钉回 clip 起点值约 2 秒 ⇒ 手势短暂错误 + 手消失一闪。
**修法**：置位点必须移入对 `_startMotion` 的重写（真正走到起播才置），包装器只保留预载。
判据：连点后 `__snapDbg().held` 必须恒空。

**无头判据的落点（本页第 4 条重播类教训）**：判据必须落在**机制本身**——队列 entry 的
`_startTimeSeconds` / `_stateTimeSeconds`（点重播后 startTime 重置＝新起播、stateTime 继续涨）、
以及 snapHold 的 held 状态；**不能拿"参数值 ≠ clip 起点"当"动作中段"的标志**（gezi_2 的 home
曲线 Param27 有长时间 0.7 平台段，无头永远等不到"离开起点" ⇒ 探针误报 FAIL）。

**倍速键顺手规则**：倍速切换后用户想立刻回 1× 是高频动作——倍速标签本身做成可点
（title 提示"点一下回到 1×"），点击即 `setSpeed(1)`。

## 20. 把 Live2D 当"网站背景层"：限帧与成本量法（2026-10-20 实测）

**需求形状**：用户问"Live2D / Spine 能不能设为网页背景、会不会卡"。这个问题**不能用 fps 回答**，
也不能凭"看起来流畅"下结论 —— 两处都会给出错误结论。

### 20.1 限帧到 24fps（不是因为跑不动，是因为没必要）

背景层是装饰，不是主角；跟浏览器合成器跑到刷新率纯属浪费电和风扇。

- **Live2D（pixi）**：用 `app.ticker.maxFPS = 24`。
  **不要自己写 `setTimeout` 节流** —— pixi 是按 `_minElapsedMS` 对齐**时间戳**的，
  自己节流会让传进 `ticker` 的 delta 抖动 ⇒ 动作速度忽快忽慢。
  写完用 `try{}catch(e){}` 包住（老版本 ticker 可能没有 maxFPS 属性）。
- **Spine（rAF 裸循环）**：跳帧时**必须"提前 return 再排一帧"**：
  ```js
  if (ts - loop._lastDraw < 1000/24 - 1) { raf = requestAnimationFrame(loop); return; }
  ```
  只 `return` 不排下一帧 ⇒ 循环永久停住，症状是"模型定住不动且无报错"。

### 20.2 "会不会卡"的正确量法

| 指标 | 为什么不能用别的代替 |
|---|---|
| `Performance.getMetrics()` 的 `TaskDuration` 差分 ÷ 帧数 | **fps 是余量指标，不是成本指标**。实测打满 300fps（= 240Hz 屏的采样上限），四个场景全是 300，看不出差别 |
| `longtask` 计数（>50ms） | 决定"会不会卡顿感"，比平均耗时更能反映用户体感 |
| 进程 CPU% | 决定"会不会烧风扇"，fps 完全反映不出 |

实测（RTX 5060 Laptop / 240Hz，背景层 24fps）：

| 场景 | fps | 背景模块 | CPU | 每帧主线程 | 长任务 |
|---|---|---|---|---|---|
| 仅水面 | 300 | — | 3.1% | 0.10 ms | 0 |
| Live2D 背景 | 299.5 | 23.7fps | 7.1% | 0.24 ms | 0 |
| Spine 背景 | 299.8 | 23fps | 5.7% | 0.19 ms | 0 |
| Live2D + 水面（最坏） | 300 | 23.7fps | 6.0% | 0.20 ms | 0 |

⇒ 判据：**每帧主线程 < 0.3ms、零长任务、页面 fps 不掉**才算"不卡"。

### 20.3 量具有效性必须先自检（否则整组数据作废）

- **`--use-angle=swiftshader` 会毁掉整组数据**：那是纯 CPU 软渲染，实测只有 15.3fps ——
  量到的是软件光栅化的代价，与用户机器无关。
- **`--headless=new` 常常拿不到 GPU**：同样的坑。改成**真实窗口 + 摆到屏幕外**：
  `--window-position=-2400,0`（不在 headless 下，但用户看不见）。
- **必须打印显卡型号做自检**：读 `WEBGL_debug_renderer_info` 的 `UNMASKED_RENDERER_WEBGL`，
  **看到 `SwiftShader` 就整组作废重测**；看到真实卡名（如
  `ANGLE (NVIDIA, GeForce RTX 5060 Laptop GPU, D3D11)`）才算有效。
- **`preserveDrawingBuffer:false` ⇒ 不能靠外部 `drawImage` 采样 canvas 判断"是否在绘制"**
  （读到的是空缓冲）。要在模块内部挂 `frames` 计数器。

### 20.4 内存记录与"刷新后恢复"

动态背景的记录**本来就不带 `url`**（带 `url` 会写出 `url("")` 产生 404）。
所以 `sload()` 这类"读回校验"的判据必须是
`o.url || o.kind==='spine' || o.kind==='live2d'`，
**不能写成 `if (!o.url) return null`** —— 那个 bug 的症状是"设置成功、刷新就丢"，
而设置那一瞬间是完全正常的（本轮 12 项验收里就因为少写"刷新"这一条而漏掉）。

**涉及文件**：`gallery_src/site_bg_live.js`（背景层本体）、
`scripts/diag/perf_cost.py`（成本量法）、`scripts/diag/perf_livebg_gpu.py`（硬件后端 fps 对照）、
`scripts/diag/site_live_bg_probe.py`（12 项功能验收）。

## 21. 把模型暴露成“用户能设的网站背景”：入口、身份、暂停（2026-10-21）

§20 解决“渲染器在不在、卡不卡”；这一节解决“用户能不能点到、换得动”。

- **入口必须走页面自己的入口函数**：首页 `renderActs` 的 `bgTarget()` 决定当前皮肤默认设哪种背景
  （Live2D → Spine → 静态图），静态图保留成旁边的次级键。回滚按**文件**进行时，
  渲染器 `site_bg_live.js` 可能在、入口却没了；只调 `SiteBg.set()` 的探针会全绿，
  但用户根本点不到。验收必须点卡片 → 皮肤 →「设为网站背景」。
- **动态记录没有 `url`**：身份判等必须按 `kind+key`（`same(a,b)` / `SiteBg.is(url,kind,key)`）。
  若只比 `url`，两个动态模型都是空串，点第二个会被判成“再点一次取消”。
- **`sapply()` 要分动态/静态**：动态类型只加 `has-sitebg`，绝不写 `url("")`；
  静态图才设置 `--site-bg`、`--site-fit`、`--site-pos`。
- **生命周期**：`visibilitychange` 时暂停 ticker / Spine 绘制；Live2D 背景渲染分辨率上限 1.5 DPR
  （背景不是查看器）；失败必须退回静态底并把错误显示出来，不能留黑屏。
- **验收**：`scripts/diag/livebg_ui_probe.py` 走真 UI，测角标/挂载/帧推进/pointer-events/
  静态次级键/取消/切换/刷新恢复；同时记录 base/Live2D/static/Spine 四档进程树 WorkingSet。
  本机实测 Live2D ΔWS ≈ +0.01 GB、Spine ΔWS ≈ +0.18 GB，24fps 限帧；成本结论仍按 §20，
  不要只看 fps。
- **跨技能**：Spine 侧的绘制序列/取景见 `spine-web-runtime-integration` §14；
  入口与身份坑的根因见 `docs/TROUBLESHOOTING.md` §173。
