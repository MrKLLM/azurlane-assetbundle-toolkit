# Spine Viewer 开发交接文档

## 当前状态

Spine Viewer (`tools/spine-viewer/index.html`) 已有基础框架，但 **视觉效果完全不可用**。

---

## 1. 当前存在的问题 (Issue List)

目前动态立绘系统在合成与渲染逻辑上出现了以下偏差，导致视觉效果完全不可用：

### 问题一：完全静止状态
- 动画系统未能正确触发，或在修复 fallback 逻辑后陷入死循环/冻结状态
- 原本应有的动态效果消失，立绘呈现完全静止
- 动画名是数字（'0', '1', '2'...），多层变体动画不同步

### 问题二：背景图层倒置
- 动态立绘合成逻辑错误，导致背景层（Background Layer）发生 180 度翻转
- 背景完全倒过来显示
- 典型案例：aisaikesi_7 的 `aisaikesi_7BG.png` 静态背景图显示时上下颠倒
- 原因：Unity 导出的 PNG 使用 Y 轴翻转坐标系，WebGL 绘制时未做逆变换

### 问题三：空间关系混乱
- 角色（Character）与背景（Background）的位置坐标、缩放比例（Size）匹配失效
- 角色未能正确叠加在背景的预定位置，出现遮挡关系错误或比例失调
- 典型案例：beikaluolaina_3 需要将角色叠加到沙滩背景上，但位置/层次不对
- 部分角色 spine WebGL 渲染完全不显示（batch_check.js 显示 185/185 加载成功，但渲染不出来）

---

## 2. 修复与优化目标 (Milestones)

### 目标一：恢复动力学逻辑
- 重新检查 Spine 渲染器的初始化生命周期，确保动画帧循环（requestAnimationFrame）正常运行
- 消除静止故障
- 确保多层变体（B/M/T/_bg）的动画同步播放

### 目标二：校正合成坐标系
- 修正 Canvas / WebGL 的坐标映射逻辑
- 确保背景图片采样方向正确，不再出现镜像或倒置
- Unity spine 使用 Y 轴向上坐标系，需在渲染时正确处理 Y 轴翻转

### 目标三：重构层级与比例算法
- 建立统一的视口（Viewport）管理系统
- 根据角色锚点自动计算背景适配比例
- 确保角色与背景的相对位置符合美术设计原稿
- 多层变体按正确层序叠加：_bg(0) → B(1) → M(2) → T(3)

---

## 架构

```
tools/spine-viewer/
├── index.html                    # 主 Viewer（WebGL + 2D canvas 双层）
└── spine-runtime/
    ├── 3.8_spine-core.js         # spine 3.8 核心运行时
    └── 3.8_spine-webgl.js        # spine 3.8 WebGL 渲染器
```

### 双层 Canvas 架构
- **bg-canvas**（z-index:0）：2D canvas，用于绘制静态背景图和合成立绘 PNG
- **spine-canvas**（z-index:1）：WebGL canvas，用于绘制 spine 动画（需要透明背景）

## 数据文件

### Spine 数据
```
Output/Spine/spinepainting/{name}/
├── {name}.skel          # spine 骨骼数据（binary，spine 3.8.99 格式）
├── {name}.atlas         # 纹理图集描述
├── {name}.png           # 纹理图集（散落的部件图）
├── {name}BG.png         # 静态背景图（部分角色有）
├── {name}B.skel/.atlas/.png  # B 层（身体）
├── {name}M.skel/.atlas/.png  # M 层（中间）
├── {name}T.skel/.atlas/.png  # T 层（装饰）
└── {name}_bg.skel/.atlas/.png # _bg 层（背景 spine 动画）
```

### 合成立绘
```
Output/Paintings_Synthesized/
├── {name}.png           # 完整合成图（角色+背景）
├── {name}_n.png         # 角色剪影（无背景）
├── {name}_rw.png        # 另一种合成版本
└── ...
```

### 舰船数据
```
Output/Spine/ship_data.json      # spine_name → {name, faction, ship_type, rarity}
Output/Spine/spine_manifest.json # 所有角色和变体列表
```

## 🔴 核心问题

### 问题 1：Spine WebGL 渲染不显示角色

**现象**：大量角色 spine 渲染不出来（如 beikaluolaina_3），但 `batch_check.js` 显示所有 185 个变体加载成功。

**可能原因**：
1. **Y 轴翻转**：Unity spine 使用 Y 轴向上，WebGL spine 可能需要 `skeleton.scaleY = -1`
2. **纹理坐标问题**：atlas 中的 UV 坐标可能需要翻转
3. **骨骼位置偏移**：spine 数据中的骨骼位置可能不在可见区域
4. **premultiplied alpha**：Unity 纹理使用预乘 alpha，blend 函数需要 `gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA)`

**排查建议**：
- 在 `loadSingleLayer()` 中添加日志，检查 skeleton 的 width/height 和 bone 位置
- 尝试 `skeleton.scaleY = -1` 翻转 Y 轴
- 检查 `drawSkeleton` 调用时是否有异常

### 问题 2：合成立绘与背景叠加

**目标**：部分角色需要将角色合成图叠加到背景上。

**示例 - beikaluolaina_3**：
- 背景：`beikaluolaina_3_bg.skel`（spine 动画，沙滩/太阳伞场景）
- 角色：`beikaluolaina_3.skel`（spine 动画，人物）
- 合成图：`Output/Paintings_Synthesized/beikaluolaina_3.png`（2248x1364）
- **需求**：将角色正确叠加到背景上，保持层次和位置关系

**示例 - aisaikesi_7**：
- 背景：`aisaikesi_7BG.png`（静态图，但显示时 Y 轴倒置）
- 角色：`aisaikesi_7B.skel` + `aisaikesi_7T.skel`
- 合成图：`Output/Paintings_Synthesized/aisaikesi_7.png`

### 问题 3：静态背景 Y 轴翻转

**现象**：静态背景图（如 aisaikesi_7BG.png）显示时上下颠倒。

**原因**：Unity 导出的 PNG 是 Y 轴翻转的（从下到上），需要在绘制时翻转。

**修复**：在 bgCanvas 绘制时使用 `ctx.scale(1, -1)` 或 `ctx.drawImage()` 配合翻转变换。

### 问题 4：多层变体分组

**变体命名规则**：
- `nameB` / `name_B` = B 层（身体，底层）
- `nameM` / `name_M` = M 层（中间层）
- `nameT` / `name_T` = T 层（装饰，顶层）
- `name_bg` = 背景层（最底层）
- `name_hx` = 换装变体

**层序**：_bg(0) → B(1) → M(2) → T(3)

**当前代码** `getLayerVariants()` 的分组逻辑可能不正确，需要修复。

## 已有代码参考

### 合成立绘脚本
`scripts/compose_paintings.py` - ALPA 算法：
1. 从 base bundle 提取各组件的 `pastePoint` 和 `declaredSize`
2. 从 `_tex` bundle 提取纹理和 Mesh UV 数据
3. 按面积从大到小排序（背景先绘制）
4. 每个组件按 pastePoint + offset 位置粘贴
5. 裁剪输出

### Spine 数据格式
- 二进制格式：spine 3.8.99（签名 0x1C）
- 字符串有尾部空格问题（已通过 `findRegion` trim 修复）
- 动画名是数字（'0', '1', '2'...），不是描述性名称
- 多层变体的动画可能不同（如 _bg 层只有动画 '0'）

## 修复建议

1. **优先修复 spine 渲染**：排查 Y 轴翻转问题，这是最根本的问题
2. **静态背景翻转**：在 bgCanvas 绘制时翻转 Y 轴
3. **多层叠加**：正确分组 B/M/T/_bg 变体，按层序渲染
4. **fallback 机制**：spine 渲染失败时用合成立绘 PNG 作为 fallback（当前已实现）
