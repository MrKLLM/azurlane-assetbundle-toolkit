---
name: live2d-motion-extraction-audit
name_en: Live2D Motion Extraction Audit
name_zh: Live2D 动作提取完整性与保真审计
description: Integrity and fidelity audit for re-exporting Live2D motions from Unity AssetBundles (AnimationClip to motion3.json). Covers enumerating all three clip containers (m_StreamedClip / m_DenseClip / m_ConstantClip) with a binding-count assertion, constant-curve emission checks against moc3 defaults with audio-driven exemptions, unfalsifiable-anchor tests for key field layout, diffing against an external authoritative motion3.json baseline with ceiling-calibrated thresholds, and an env-switch plus byte-identical control-group protocol for removing legacy guardrails. Use when extracting or re-exporting Live2D motion data, when curves go missing, or when users report parts moving independently, unnatural transitions, jittering limbs, wrong easing. Trigger words include motion3.json audit, ConstantClip, genericBindings, bezier control point, tangent field layout, guardrail removal. Not for browser runtime playback (live2d-web-runtime-integration) or static painting restoration (unity-assetbundle-painting-restore).
description_en: Integrity and fidelity audit for re-exporting Live2D motions from Unity AssetBundles (AnimationClip to motion3.json), covering three-container curve enumeration, constant-curve decisions, field-layout anchor tests, authoritative baseline diffing, and byte-identical control-group guardrail removal.
description_zh: 从 Unity AssetBundle 重导 Live2D 动作（AnimationClip → motion3.json）时的完整性与保真审计流程。覆盖三容器曲线枚举（m_StreamedClip / m_DenseClip / m_ConstantClip，只读 streamed 会丢 60%+ 绑定）+ 绑定数求和断言、定值曲线可否补入（逐条比 moc3 默认值，音频驱动参数一律豁免）、键记录字段布局的不可钻空子锚点自证（附两个已被推翻的无效判据）、外部权威 motion3.json 基准比对与天花板校准阈值、以及拆历史护栏的 env 开关 + 逐字节对照组协议。当需要重导/校验 Live2D 动作数据、或用户反馈"部件各动各的/过渡像刚学建模的/小臂乱摆/动作太快/曲线少了/像抽一帧"时使用。触发词：Live2D 动作重导、motion3.json 审计、AnimationClip 丢曲线、ConstantClip、DenseClip、genericBindings、贝塞尔控制点、切线字段、参考版比对、拆护栏、A/B 逐字节、空壳动作。不适用：网页侧运行时播放集成（live2d-web-runtime-integration）、静态立绘/Spine 还原（unity-assetbundle-painting-restore）、通用管线安全落地方法论（safe-pipeline-fix-targeted-rerun，本技能第 5 步是它在动作数据场景的特化）。
version: 1.0.0
argument-hint: Point at the model/motion output directory and the clips to audit
argument-hint-en: Point at the model/motion output directory and the clips to audit
argument-hint-zh: 给出模型/动作产物目录与要审计的 clip 名
user-invocable: true
---

# Live2D 动作提取完整性与保真审计

## Overview

从 Unity AssetBundle 反解 Live2D 动作时，**完整性**和**保真**是两个独立失败面，判据完全不同，必须分开审计：

- **完整性**：这个 clip 的绑定里，我该导出的曲线有没有一条都不少？（少曲线的典型症状是"部件回不到静止位、各动各的"）
- **保真**：导出的曲线，关键帧和插值形状是否还原了源数据的意图？（形状错的典型症状是"乱摆/抽一帧/像刚学建模的人做的"）

顺序不能颠倒：先做完整性，因为丢曲线会让所有保真比对的分母都错；再做保真，因为曲线齐了才能判定"剩余差异是不是天花板"。

## 适用判断

- 从游戏 Unity 包重导 `.motion3.json`，或用户反馈"动作少了 / 不动 / 乱动 / 过渡不自然 / 太快" → 用本流程
- 只是网页里动作播不出来、点击不触发、idle 冻结 → 走 `live2d-web-runtime-integration`（运行时侧）
- 已经拿到官方原始 `.motion3.json`（不必反解）→ 不需要本流程，直接核对文件

## 第 1 步：完整性——三容器必须枚举 + 绑定数求和断言

Unity `AnimationClip` 把曲线**分装在三个容器**里，只读 `m_StreamedClip` 是最常见的系统性丢数据来源：

| 容器 | 内容 | 取数量字段 |
|---|---|---|
| `m_StreamedClip` | 多关键帧动画曲线（packed uint32 流） | `.curveCount` |
| `m_DenseClip` | 等间隔采样曲线 | `.m_CurveCount` |
| `m_ConstantClip` | 整段保持定值的曲线 | `len(.data)` |

**硬断言（每个 clip 都跑，不过就报错，绝不静默继续）**：

```
streamed.curveCount + dense.m_CurveCount + len(constant.data) == len(genericBindings)
```

三条曲线的字节布局与索引偏移推导见 [reference.md](reference.md) §1。关键点：`m_ClipBindingConstant.genericBindings` 的**分段顺序 = [streamed][dense][constant]**，所以定值曲线的目标名要从下标 `streamed.curveCount + dense.m_CurveCount` 开始数（实测某样本 `98 + 0 + 180 = 278`，且三段的绑定名零冲突）。

**定值曲线不是惰性的**：Cubism 只对"本 clip 有曲线的"参数施加权重，缺曲线的参数在切换动作时**停在上一个动作留下的值上**。于是被交互动作（`touch_*` 类）动过的手臂/身体参数，在回到 `idle` 时没有任何曲线把它写回静止位 → 观感就是"部件错位、各动各的"。丢弃前必须量化影响：某样本只读 streamed 时 `idle` 只导出 98/278 条，整模型 104 个动作曲线总数 9441 → 补全后 29945（丢 68%）。

⚠️ 该样本 dense 曲线数为 0，**不代表通用**：遇到 `dense.m_CurveCount > 0` 而管线没解 dense 时，必须显式告警并报数，不得当成 0 略过。

## 第 2 步：定值曲线可否补入——两级判定

补定值曲线本身有风险（可能把参数钉死在错误值上），所以逐条判：

1. **与 moc3 默认值比对**。从运行时导出全参数 `(min, max, default)` 表（Cubism Core 的 `getParameterMinimumValue / getParameterMaximumValue / getParameterDefaultValue`，CDP 片段见 reference.md §2），逐条比"定值 == 默认值"。实测某样本 **179/180 条等于默认值** → 补入无损且必要（作用正是复位）。
2. **例外清单来自组件清单，不靠猜**。不等默认值的那条必须单独审：查 bundle 里的 MonoBehaviour 组件清单，找出**所有由外部驱动的参数**并一律豁免。典型：口型 `ParamMouthOpenY` 的定值是 1，但游戏侧由 `CubismMouthController` + 音频输入组件驱动——补成常量会让嘴一直张着。同理 `ParamEyeLOpen/ROpen`（眨眼）、`ParamAngle*`/`ParamBreath`（若运行时挂了呼吸层）。

写进口径："补进来的每一条定值曲线，要么等于 moc3 默认值，要么在显式豁免清单里并写明驱动方"。豁免清单为 0 也要打印，否则下一位不知道你有没有查过。

## 第 3 步：字段布局自证——只认不可钻空子的锚点

StreamedClip 的每条键记录是 `index(int32) + 4×float`。**谁是值、谁是入/出切线**只能由数据自证，猜错一个字段，整段贝塞尔全飞。

✅ **唯一可用的锚点**：帧 `time ≈ -3.4e38`（`-FLT_MAX`）是 Unity 的**参考姿态帧**，它一帧合法写完全部曲线的静止值。取"参考姿态帧字段 X 的值"与"该曲线第一个真实键字段 X 的值"做**同字段一致率**。静止值应当等于起始值：

- 实测值字段 **98/98 命中**，斜率字段仅 **46/98** → 值字段钉死，其余两个为入/出切线。
- 用钉死后的三元组反算 Hermite，与已导出文件里的贝塞尔控制点应能**精确互推**（自洽旁证）。

❌ **两个已被推翻的无效判据，别再走**：

1. **"重建曲线越出参数合法量程"不能证伪字段解释**。Cubism 给参数赋值时本就钳进 `[min, max]`，游戏侧同样会越界再被钳——越界只说明"会被钳"，不说明"解错了"。
2. **在密集 plateau 键上用差分导数比切线无效**。游戏动作常有 1/60 秒间隔的等值键，此时 `dv ≈ 0`，差分斜率是噪声主导的垃圾数，拿它当"正确答案"会把对的解释判成错的。

补充：也别把"某个字段恒为 0"当判据——零字段能被任何候选解释平凡命中，是空判据。

⚠️ **字段解释自洽 ≠ 拿它算 Hermite 就保真**。Unity 密集键的切线字段本就不该直接当 Hermite 切线用（算出的控制点会飞出段外）。切线该不该用，交第 4 步的外部基准裁决。

## 第 4 步：外部权威基准——找、比、按天花板校准阈值

**触发条件**：本地推断穷尽（第 3 步之后仍有"该不该贝塞尔"这类两难）→ **向用户要游戏内实录或参考查看器的录屏当基准，不要继续猜**。真实成本账：本轮在此之前的两次根因误判都靠本地推演收场，全部作废；拿到同模型的权威 `motion3.json` 后一次锁定。

**找权威导出**：第三方 Live2D 参考查看器常挂着同一批模型的原始 `motion3.json`（大概率来自游戏原始 Live2D 发行包，而不是 AssetBundle 反解）。方法是从查看器前端产物（`/assets/index-*.js`）里 grep `model3.json` 路径模板，反查其静态资源目录规律，再逐 clip 拉取。**注意目录名可能是 `motions/` 而我们的产物是 `motion/`**，比对前先做子目录候选枚举；参考库通常只覆盖部分模型，404 的跳过并计数，够当抽样基准即可。

**比对项，按重要性排序**（前三项必须 100%，否则不是"精度差异"而是解析 bug）：

1. 动作组集合 —— 参考有我们没有 = 漏登记
2. 曲线 `Id` 集合 —— 少了就是丢曲线（回到第 1 步）
3. 关键帧时间与值 —— 逐条必须一致，不一致 = 解析错位
4. 段类型分布（linear / bezier / stepped 三方对比）
5. 逐曲线采样偏差 —— **必须按运行时真实语义求值**（如 `Meta.AreBeziersRestricted` 决定贝塞尔走朴素参数化还是解出横向控制点），否则你在拿自己的错误求值判自己对

**阈值按实测天花板校准，不要拍脑袋**（本轮把 WARN 线从直觉的 5% 改成实测可达上限对应的 12%，实测落 3.8%~9.6%）：

- **"阶梯段缺失"不是缺陷**：参考版 1070 条阶梯段里 1067 条两端值相同（与线性完全等价），真跳变仅 3 条且都在 1 帧内完成 → 补它零视觉收益。
- **"源数据里的 1 帧硬翻"不是我们的偏差**：某参数一帧内 +10 → −10，参考版 27 处同类硬翻只把 2 处标阶梯，其余照样线性——游戏也做这一下。
- **贝塞尔控制点推不出来就是天花板**：四种候选切线公式拟合参考控制点，最高命中 16.7%（且那是"切线 = 0"的平凡情形）。可达上限 = 曲线集合 100% 一致 + 关键帧时间/值 100% 一致 + 约 93% 段类型一致，剩余约 7% 用线性弦近似（表现为缓动略少，不会导致部件乱动）。**这一项别再攻**。

## 第 5 步：拆历史护栏——env 开关 + 逐字节对照组

历史护栏（如"控制点纵向偏出 3.0 就把该段降级成线性"）常常在**掩盖另一个格式错误**，而不是在做优化。看到"护栏牺牲了 48% 的段"就直接拆，是本轮第二大坑。安全拆法：

1. **加 env 开关，默认保持旧行为**——保证不带任何 env 的一跑能复现现产出。开关示例：`MOTION_BEZIER_CLIP`（阈值）、`MOTION_ABSOLUTE_CP`（按规范写绝对坐标控制点）、`MOTION_LINEAR`（强制线性）、`MOTION_EMIT_CONST`（补定值曲线）、以及一个输出目录开关把产物写到临时目录。
2. **临时目录分别跑对照组与实验组**，绝不直接写正式产物目录。
3. **对照组必须与现产出逐字节一致**（实测 104/104 文件 sha256 全等）。不一致说明有别的改动混进来了，本次 A/B 作废，先清理变量再来。
4. **逐曲线采样算偏差分布**再判收益。实测拆掉阈值护栏后 **63% 曲线偏差 > 0.15、最甚 205 个参数单位** → 立即回退，不得全量换入。
5. 结论口径固定为三选一：**收益为正**（可换入）／**收益为负**（回退，且去查它在掩盖什么）／**收益不可判**（判据本身有缺陷，回第 3/4 步补判据）。

通用的"定位受影响子集 → 证零回退 → 备份换入"流程见 `safe-pipeline-fix-targeted-rerun`，本步只补动作数据特有的偏差度量。

## 第 6 步：结论归档与交接口径

审计产出必须四分类，**每类分开写，混在一起下一位就会去攻天花板**：

1. **根因（已修）** —— 附修前/修后量化数字（某样本：偏差中位 1.376 → 0.0；92/98 条曲线偏差 > 0.5 → 11/278）。
2. **已排除假设** —— 逐条写"查过、判据是什么、为什么排除"，防止下一位重走。
3. **天花板** —— 明确"不是 bug，别再去攻"，并给出可达上限的百分比构成。
4. **未决（交接）** —— 现象 + 已量化数据 + 候选修法（列 2~3 条，注明各自代价）。

⚠️ **交接命令里的 env 配方必须是"实际通过验收的那一条"**，不是"格式上更正确的那一条"。真实返工案例：交接文档写的是绝对坐标贝塞尔开关（符合 Cubism 规范但未过基准验收，对参考版偏差最甚 296），而实际换入并验收通过的是"关键帧 + 线性 + 补定值曲线"。按错的命令重跑 = 全量返工。

## Pitfalls

- **只读 `m_StreamedClip`**：本技能针对的头号系统性错误，一次丢掉 60%+ 绑定，且症状（部件不复位）极易被误判成"插值不对"。
- **把定值曲线当惰性噪声丢掉**：它是切动作时的复位指令。
- **给音频/外部驱动参数补常量**：口型补成 1 = 嘴永久张开。豁免清单必须来自 MonoBehaviour 组件清单。
- **用无效判据自证**：越量程判据、密集 plateau 差分斜率判据、恒零字段判据——三者都会把正确解释判成错误。
- **护栏未验先拆 / 拆了就全量换入**：护栏可能在掩盖格式错误；跳过逐字节对照组 = 拿全量产物赌运气。
- **拿自己的求值器判自己的保真度**：采样求值必须复刻运行时语义（`AreBeziersRestricted` 等）。
- **把天花板当 bug 长期攻**：阶梯段、源数据硬翻、不可推的贝塞尔控制点这三项都无收益。
- **阈值拍脑袋**：判据阈值要从实测可达上限反推，不要默认 5%。
- **本地一直猜而不要基准**：第 3 步之后仍两难就该向用户要实录，别连开第三条猜想。
- **"列表少了"往往是排序不是缺失**：动作组集合 104 vs 104 零差异，只因参考版按字母排而 bundle 里是乱序，主动作沉在下面。先比集合再谈缺失，前端排序即可，不要动数据。
- **无头验证偶发 `Execution context was destroyed`**：多为无头实例冲突的假失败，重跑一次再下结论（同批次探针已通过时尤其可疑）。
- **解析失败时留占位空壳**：结构合法的 `"Curves": []` 会让下游"能播但不动"，且能通过一切外壳检查。失败必须显式报错 + 非零退出（见 `safe-pipeline-fix-targeted-rerun` 分支 C）。

## Verification

复制这份清单，逐项给数字，不接受"看起来对了"：

```
完整性
- [ ] 每个 clip：streamed + dense + constant == len(genericBindings)（列出违例数，须为 0）
- [ ] dense.m_CurveCount > 0 的 clip 数量已报出并处理（不得静默为 0）
- [ ] 补入的定值曲线：等于 moc3 默认值的条数 / 总条数，豁免清单逐条附驱动方
保真
- [ ] 字段布局锚点：值字段一致率（实测应为 100%）；斜率字段不作为判据
- [ ] 权威基准：动作组集合零差异；曲线 Id 集合零缺失；关键帧时间/值零不一致
- [ ] 采样偏差：中位 ≤ 阈值、超阈曲线占比 ≤ WARN 线（阈值注明"按实测天花板校准"）
拆护栏
- [ ] 对照组与现产出逐字节一致（sha256 全等，报 N/N）
- [ ] 实验组逐曲线偏差分布已给出，结论明示收益正/负/不可判
交付
- [ ] 根因 / 已排除假设 / 天花板 / 未决 四类分开归档
- [ ] 交接命令里的 env 配方 == 实际换入并通过验收的配方
```

## Additional Resources

- 三容器字节布局与索引偏移、参数默认值导出 CDP 片段、锚点打分脚本骨架、A/B 命令序列、实测数据表：[reference.md](reference.md)
