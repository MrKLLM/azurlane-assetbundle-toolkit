# 工作流记录

> 本文件记录跨会话可复用的工作流程，按时间顺序追加。

---

### WF-1: AssetBundles 扫描与清单生成

**日期**: 2026-06-19
**目标**: 扫描碧蓝航线 AssetBundles 目录，按资源类型生成 JSON 清单
**适用场景**: 需要了解大型 Unity AssetBundle 目录的资源分布时

**步骤**:
1. 编写 `scan_assets.py`，递归扫描目录并按子目录名分类（映射表约 30 个类别）
2. 对立绘文件解析舰名、皮肤编号、变体后缀（正则匹配）
3. 运行 `python scan_assets.py`，输出 `asset_manifest.json`
4. 验证：检查 JSON 文件大小和类别分布

**关键决策**:
- 分类方式 → 按子目录名映射（而非文件后缀），因为 AssetBundle 94.6% 无后缀
- 立绘解析 → 正则提取 `{舰名}_{皮肤编号}_{变体}_tex`

**踩坑记录**:
- 无

**涉及文件**: `scripts/scan_assets.py`, `asset_manifest.json`

---

### WF-2: AssetBundle 批量导出（UnityPy 方案）

**日期**: 2026-06-19
**目标**: 使用 UnityPy（Python 原生）批量导出 Texture2D/Mesh/AudioClip
**适用场景**: 无外部工具时的 AssetBundle 导出，或需要脚本化批量处理

**步骤**:
1. 安装依赖：`pip install UnityPy Pillow`
2. 编写 `export_assets.py`，核心逻辑：
   - `UnityPy.load(path)` 加载 Bundle
   - 遍历 `env.objects`，按 `obj.type.name` 分发导出函数
   - Texture2D → `data.image.save("name.png")`
   - Mesh → 生成 OBJ 格式文本
   - AudioClip → 提取 `data.samples`
3. 支持 `--target painting|bg|all` 参数选择导出类别
4. 支持 `--dry-run` 预览模式
5. 运行 `python export_assets.py --target painting`

**关键决策**:
- 主方案选 UnityPy（而非 AssetStudioCLI）→ 无需安装外部工具，Python 原生
- Texture2D 属性名 → `m_Name`（不是 `name`），UnityPy 的命名约定
- MOC3 数据提取 → 在 MonoBehaviour raw_data 中搜索 `MOC3` 魔数，偏移量因模型而异（40-52 字节）

**踩坑记录**:
- `data.name` 报错 → 应使用 `data.m_Name`
- AssetStudioCLI 未安装时脚本报错 → 改为 UnityPy 为主方案
- 导出日志累计计数误导 → 实际文件数需单独统计，不能直接用日志数字

**涉及文件**: `scripts/export_assets.py`, `scripts/scan_assets.py`

---

### WF-3: Live2D 模型从 AssetBundle 还原

**日期**: 2026-06-19
**目标**: 从 Unity AssetBundle 中提取 moc3 + textures + physics，重建标准 Live2D 目录结构
**适用场景**: 游戏资源解包后需要还原可播放的 Live2D 模型

**步骤**:
1. 编写 `reconstruct_live2d.py`
2. 提取 moc3：在 MonoBehaviour raw_data 中搜索 `MOC3` 魔数，截取到文件末尾
3. 提取贴图：遍历 Texture2D 对象，`data.image.save("texture_XX.png")`
4. 提取物理：TextAsset 中名称含 `physics` 的，导出为 `.physics3.json`
5. 提取动作名：AnimationClip 的 `m_Name` 属性
6. 生成 `model3.json` 配置文件
7. 运行 `python reconstruct_live2d.py --all`

**关键决策**:
- moc3 提取方式 → 搜索 raw_data 中的 MOC3 魔数（而非直接读属性），因为 CubismMoc 未暴露 Moc 字段
- model3.json 格式 → 遵循 Live2D Cubism SDK v3 规范
- motion 文件 → 生成占位符（真实动作需从 AnimationClip 曲线数据转换）

**踩坑记录**:
- MOC3 偏移量不固定（40-52 字节），必须用 `raw.find(b"MOC3")` 动态定位
- model3.json 缺少 `Pose`/`HitAreas`/`Expressions` 字段 → Live2DViewerEX 加载失败
- motion 文件是占位符 → 模型可静态显示但无动画
- MOC3 版本分布：version 1（lingbo 等）和 version 2（qiye_7 等）

**涉及文件**: `scripts/reconstruct_live2d.py`, `scripts/fix_model3.py`

---

### WF-4: Unity AssetBundle 导出的错误处理与降级策略

**日期**: 2026-06-19
**目标**: AssetStudio 导出失败时自动切换 UABE 重试
**适用场景**: 批量导出时部分 Bundle 格式不兼容

**步骤**:
1. 在 `export_assets.py` 中实现 `export_with_fallback()` 函数
2. 先尝试 AssetStudioCLI，检测返回码和错误输出
3. 若返回 `Unsupported Unity version`，切换 UABE
4. 记录所有失败到 `ERRORS.log`

**关键决策**:
- 降级策略 → AssetStudio 优先，UABE 兜底
- 错误检测 → 解析 stderr 中的 "Unsupported Unity version" 字符串

**涉及文件**: `scripts/export_assets.py`, `ERRORS.log`

---

### WF-5: 大批量导出的分批执行与断点续传

**日期**: 2026-06-19
**目标**: 处理超时问题，分批完成大规模导出
**适用场景**: 单次导出超过 10 分钟超时限制

**步骤**:
1. 先用 `--target painting` 单独导出立绘（12,397 文件）
2. 导出完成后检查实际文件数
3. 对其他类别（bg、audio、live2d）分别执行
4. 脚本支持跳过已存在文件（通过检查 model3.json 是否存在）

**关键决策**:
- 分批策略 → 按资源类别分别导出，而非全量一次
- 断点续传 → 检查输出目录中是否已有文件，有则跳过

**踩坑记录**:
- 单次导出 12,397 文件需 ~108 分钟（3.5 文件/秒）
- 超时 10 分钟被中断 → 需分批执行
- 256 个 Live2D 模型首次运行需 ~30 分钟，添加跳过逻辑后 <1 分钟

**涉及文件**: `scripts/reconstruct_live2d.py`, `scripts/export_assets.py`

---

### WF-6: Live2D 交互功能修复（HitAreas + Motion 映射）

**日期**: 2026-06-20
**目标**: 让还原的 Live2D 模型支持点击交互触发动画
**适用场景**: 从 Unity AssetBundle 还原的 Live2D 模型需要在 Live2DViewerEX 中可交互
> ⚠️ **两处过时**：第 3 步「按 64 字节条目偏移猜参数名」已被 2026-09-21 证伪并作废（改用 `genericBindings`/crc32 权威映射，见 WF-7）；第 4 步只提到搜 `Touch*` 字符串，**没写组名匹配规则** → 旧的一次性路径只覆盖了组名为 `Head/Body/Special` 的老模型（`TROUBLESHOOTING.md` §18 已于 2026-09-22 修复：`fix_model3.py` 现按「moc3 含 Touch<X> ∩ 真实存在的动作组」生成真判定区，13 个 `touch_*` 模型不再走占位）。

**步骤**:
1. 修复 model3.json 格式（fix_model3.py）:
   - 删除 `Pose`/`DisplayInfo` 对象字段（Live2DViewerEX 不接受）
   - `Groups` 用 `"Ids"` 数组（不是 `"Id"` + `"GroupIds"`）
   - `HitAreas` 移到顶层，格式 `[{"Id": "TouchHead", "Name": "Head"}]`
2. 添加 Tap 前缀 Motion Groups:
   - 在 model3.json 中添加 `"TapHead"` / `"TapBody"` / `"TapSpecial"` groups
   - 指向 `touch_head.motion3.json` 等文件
   - Live2DViewerEX 需要 Tap 前缀才能触发动画
3. 从 moc3 提取参数名映射:
   - moc3 中参数名存储在 64 字节条目中，偏移量因模型而异（0/32/48）
   - 支持 `Param` 和 `PARAM` 两种前缀格式
   - 用字符串搜索方式提取，处理参数名跨越条目边界的情况
4. 从 moc3 提取 HitArea ID:
   - 搜索 `TouchHead`/`TouchBody`/`TouchSpecial` 字符串
   - 或用 Part 名（`Part01Face001` 等）作为备选

**关键决策**:
- HitArea ID 格式 → 使用 `TouchHead`/`TouchBody`/`TouchSpecial`（moc3 中存在）
- `Part01Face001` 等作为 ID → 红框消失，不可用
- `HitArea`/`HitArea2` 简单 ID → 红框消失，不可用
- Tap 前缀 → 必需，Live2DViewerEX 用此匹配 HitArea 点击事件
- 纹理顺序 → 必须按名称字母序排列（moc3 按索引引用纹理）

**踩坑记录**:
- `Pose` 用对象格式 → Live2DViewerEX 不接受，需省略或 null
- `DisplayInfo` 用对象格式 → 同上
- `HitAreas` 在 `FileReferences` 内 → 需移到顶层
- 纹理顺序错乱 → moc3 按索引引用，需按名称排序
- 缺少 Tap 前缀 motion groups → 点击无反应
- moc3 参数提取只搜 `Param` 前缀 → 漏掉 `PARAM_` 前缀的参数

**涉及文件**: `scripts/fix_model3.py`, `scripts/extract_motions.py`, `scripts/reconstruct_live2d.py`, `TROUBLESHOOTING.md`

---

### WF-7: Live2D 动作提取与安全重建（权威映射 + 换入管线）

**日期**: 2026-06-20（旧版）→ **2026-09-21 重写**（旧版的参数映射是错的，见「禁止」）
**目标**: 从 Unity `AnimationClip` 还原可用的 Cubism `motion3.json`，并在**不毁掉既有正确产物**的前提下安全换入
**适用场景**: Live2D 动作"不动 / 乱飘 / 乱闪"排查、动作层重生成、新增 live2d bundle 补齐、游戏版本更新后动作重跑

#### 一、权威映射（先记事实，再谈步骤）

1. `m_StreamedClip` 的 **curve index 与 `AnimationClip.m_ClipBindingConstant.genericBindings[i]` 同序**。
2. `genericBindings[i].path = crc32("Parameters/<GameObject名>")`（参数）/ `crc32("Parts/<GameObject名>")`（部件）。
   实测跨模型 946,274 个绑定解析率 **99.77%**，不是 sdbm/djb2/FNV/CRC-16。
3. 属性哈希分目标类型：`3702945584`=`Parameter.Value` → `Target:"Parameter"`；
   `2353026298`=`Part.Opacity` → `Target:"PartOpacity"`（官方换装/部件可见性，**79 模型有**）；
   `4109387685`=疑 Drawable 颜色/透明度，Web 运行时无对应 target → 跳过并计数（占 0.226%）。
4. `CubismParameter` 组件 `m_Name` 为空，**真名挂在 GameObject 上**；`_unmanagedIndex` 才是 moc3 参数序号，
   且被动画化的序号**稀疏**（`lingbo/idle` = 0,1,2,8,9,12,13,14,15,18,21,22,23,26,27）。

#### 二、步骤（命令按序，均可直接复制）

1. **重生成到临时目录**（绝不可先写正式目录）：
   `L2D_OUT_DIR="D:\Azur Lane Assets\.diag\l2d_new" PYTHONIOENCODING=utf-8 py -3 scripts/extract_motions.py --all`
   → 退出码 1 是预期的，但**失败清单必须只包含资产层本就为空的 clip**（当前 7 条：`*_3/effect`、`wuqi_3/idle11` 等）。
   出现别的失败就是解析器又退化，先修再往下走。
2. **全量审计**（内容判据，不是状态标签）：
   `L2D_OUT_DIR="...\.diag\l2d_new" py -3 scripts/diag/l2d_motion_audit.py`
   → 要求 `misassign 0`；`shell` 只允许等于第 1 步的真空清单；顺带看 `part_opacity_curves`、`src_dur` 是否非 0。
3. **换入前做浏览器 A/B 对照**（此时 old=旧数据、new=新数据才有意义）：
   先在 Output 根起 `py -3 -m http.server 8791 -b 127.0.0.1 -d Output`，再
   `py -3 scripts/diag/l2d_ab.py <模型> --motion idle`
   → 至少选 1 个"全空壳"模型（应看到旧侧参数纹丝不动、新侧在动）+ 1 个带 PartOpacity 的模型。
   这一步是用来抓"文件看着合法但运行时拒收"的问题——贝塞尔段序 bug 就是这么发现的。
4. **备份换入**（只动 `motion/`，moc3/贴图/physics/model3 不碰）：
   `py -3 scripts/apply_live2d_motions.py`（干跑看曲线总数变化）→ 加 `--yes` 执行。
   旧数据按时间戳目录 **move** 到 `Output/_OLD_bak/l2d_motion_<ts>/`，回滚 = 把目录挪回去。
5. **对齐 model3 引用 + 生产复核**：
   `py -3 scripts/fix_model3.py`（剔除指向缺失文件的动作引用）
   然后三项必须为 0：空壳文件数、未被引用的 motion 文件数、被引用但不存在的文件数。
6. **同步前端**：改了 `gallery_src/` 就 `py -3 scripts/deploy_gallery.py`；
   用户侧用 `启动资产浏览器.bat`（自带 no-cache，避免"还是旧界面"）。
7. **补新 bundle / 新增模型**（例如尚未还原的 9 个）：
   `py -3 scripts/reconstruct_live2d.py --name X` → `py -3 scripts/extract_motions.py --name X`
   → `py -3 scripts/fix_model3.py` → 审计该模型 → `build_gallery_index.py` + `make_thumbs.py` 增量 → 抽验。
   ⚠️ index/thumbs 是全量重建产物，跑前确认没有在途改动（见 WF-15 白名单）。
   - **建议仍先写到临时目录**：`reconstruct_live2d.py --name X --out <tmp>` + `L2D_OUT_DIR=<tmp>` 跑后两步（`reconstruct` 用 `--out`、另两个用环境变量），验证过了再复制进 `Output/Live2D/`；新增模型没有旧数据，回滚 = 删目录。
   - ⚠️ **审计脚本对"部分目录"会给出假象**：`l2d_motion_audit.py` 按**源包目录 269 个**遍历，磁盘上没有的算 shell → 只建了 9 个时全量跑会报 `shell 7302/8154`。必须**逐模型** `py -3 scripts/diag/l2d_motion_audit.py <模型>`（只支持单模型参数）。
   - **`reconstruct_live2d.py` 两处已知副作用**（第 3 步的 `fix_model3.py` 会顺手补上，别漏跑）：① `model3.json` 的 `Physics` 引用判据是 `os.listdir(".")` 里有没有含 "physics" 的文件（不是模型目录！）→ 直接生成的新模型不带 Physics，靠 `fix_model3.py:70-74` 修；② `HitAreas`：`fix_model3.py` 过去只补占位 Id（`HitArea/HitArea2`）；**2026-09-22 起已升级为生成真判定区**（moc3 `Touch<X>` drawable ∩ 真实动作组，Name 用实际组名，只替换占位、不动既有正确值），新模型点部位按头/身/特精确命中，见 §18 / WF-7 第 3 步后段。
   - **2026-09-21 已做完到「换入前」这一步**（用户决定暂不换入）：9 个模型建在 `.diag/l2d_new9/`，**852 clip / 0 空壳 / 0 错位 / 87,266 曲线**（`shi_3` 含 365 条 PartOpacity），逐模型审计全绿；总计 467MB。⚠️ `.diag/` 是可清理区，**清理前先确认这批已换入**；若已被清，按本步命令重建（源包 `files/AssetBundles/live2d/` 269 个齐全，可重跑）。换入后还需：复制到 `Output/Live2D/` → `build_gallery_index.py`（9 张卡的 `live2d` 字段自动补上，`ship_meta.json` 无需改，中文名已在）→ `make_thumbs.py`（正图未变，预计全 skip）→ 浏览器内容判据抽验 + 截图。

#### 三、禁止（每条都对应一次真实事故）

- **禁止给 StreamedClip 的 `numKeys` 设上限**：帧 0 是 `time=-3.4e38` 的参考姿态帧，一帧写完全部曲线
  （大模型 380~520 key），护栏会在帧 0 崩掉整条动作 → 实测曾致 **5037/8154(61.8%) 空壳**。只能靠 `+inf` 结束符 + 缓冲区边界停。
- **禁止按"curve idx == 参数序号（从 0 连续）"或按组件枚举顺序取参数名**：必然错位（眼睛数据写进眉毛参数）。
- **禁止写 `"Curves": []` 之类占位产物**：它结构合法、能"播"，会把失败伪装成成功——这是本 bug 潜伏一年多的根因。
  缺失就让它显式缺失（404/报错），`reconstruct_live2d.py` 已按此改。
- **禁止用 `state.currentGroup` 判断动作是否有效**：空壳也能启动。要判 ① `curveCount>0` ② 曲线目标值随时间变化。
- **禁止出 `pose3.json` 承载换装逻辑**：`pixi-live2d-display 0.4.0` 不读它（`"Pose"` 出现 0 次），只能走 motion3 的 `Target:"PartOpacity"`。
- **贝塞尔段序必须是 `[1, c1x, c1y, c2x, c2y, 终点time, 终点value]`**（终点在最后，无第 5 个"interpolation"字段）；
  `segments` 按 `Meta.TotalSegmentCount` 预分配，计数少一位就抛 `basePointIndex of undefined`，前端只表现为"这模型不动"。
  `extract_motions.py` 已内置"按运行时消费方式重放"的结构自检，别绕过它。

#### 四、验证工具与已知遗留

| 工具 | 用途 |
|---|---|
| `scripts/diag/l2d_motion_audit.py` | 全量健康审计（空壳/错位/PartOpacity/时长），`L2D_OUT_DIR` 可指向任意产物目录 |
| `scripts/diag/l2d_ab.py` | 同一模型新旧 motion 的渲染级 A/B（**只在换入前构成对照**） |
| `scripts/diag/l2d_diff_dirs.py` | 两个产物目录逐 clip gained/changed/lost |
| `scripts/apply_live2d_motions.py` | 干跑/备份换入 |

遗留：`l2d_sweep.py` 判据已升级为内容判据，但它把整轮循环塞进**一次** `Runtime.evaluate`，换数据后会卡住 → 全量浏览器回归需改成 Python 侧逐条驱动；
0.226% 绑定（疑 Drawable 颜色）无 target 可映射，跳过；`HitAreas` 现库里全部按 `Touch*` drawable 生成（未用官方 `CubismRaycastable`）；`fix_model3.py` 于 2026-09-22 起在现役管线内生成真判定区（moc3 Touch<X> ∩ 真实动作组，覆盖 `Head/Body/Special` 与 `touch_*` 两种命名，13 模型已修，全库 806/807，唯 `z46_3` 嵌套框歧义），见 `TROUBLESHOOTING.md` §18；表情 `CubismExpressionController` 未还原。

**踩坑记录**: 详见 `docs/TROUBLESHOOTING.md` §17（空壳+错位双根因、crc32 破译过程、贝塞尔段序自伤与被 A/B 抓出）

**涉及文件**: `scripts/extract_motions.py`、`scripts/reconstruct_live2d.py`、`scripts/fix_model3.py`、`scripts/apply_live2d_motions.py`、`scripts/deploy_gallery.py`、`gallery_src/index.html`、`scripts/diag/l2d_motion_audit.py`、`scripts/diag/l2d_ab.py`

---

#### 附：旧版 WF-7 原文（2026-06-20，已作废，仅备查）

**（原标题）WF-7: Live2D 动作数据提取与参数映射**

**日期**: 2026-06-20
**目标**: 从 AnimationClip StreamedClip 提取真实 motion3.json 数据
**适用场景**: 将 Unity AnimationClip 转换为 Live2D Cubism motion3.json 格式

**步骤**:
1. 从 AnimationClip 的 `m_MuscleClip.m_Clip.m_StreamedClip` 提取数据
2. StreamedClip 格式：`sentinel(0xFF7FFFFF) + curveCount + frames`
3. 帧格式：`time(float) + numKeys(int) + keys[index(int) + coeff[4](float)]`
4. `coeff[2]` = outSlope，`coeff[3]` = value
5. 转换为 motion3.json 的 `Curves[].Segments` 格式
6. 从 moc3 提取参数名，建立索引→名称映射

**关键决策**:
- StreamedClip 解析 → 参考 AssetStudio 源码的 `ReadData()` 方法
- 参数名映射 → moc3 中参数名存储在 64 字节条目中，需自适应多种偏移
- 未映射参数 → 从 motion 文件中移除（moc3 版本不匹配时）

**踩坑记录**:
- StreamedClip 数据起始偏移 = sentinel(4B) + curveCount(4B) = 8 字节
- moc3 参数名偏移因模型而异：lingbo 在 offset 0，bisimai_2 在 offset 48，dafeng_2 在 offset 32
- 部分 moc3 有中文参数名（tongkongdaxiao 等），不以 Param/PARAM 开头
- moc3 参数数量可能少于 motion 期望的数量（版本不匹配）

**涉及文件**: `scripts/extract_motions.py`

---

> 作废理由：第 6 步「从 moc3 提取参数名建立索引→名称映射」+ 踩坑里按偏移猜参数名，是本次 3117 条曲线名全错位的根源；「sentinel+curveCount 8 字节头」实为参考姿态帧的 time+numKeys。

---

### WF-8: TROUBLESHOOTING.md 踩坑记录规范

**日期**: 2026-06-20
**目标**: 建立问题-解决方案文档，沉淀项目经验
**适用场景**: 任何技术项目中遇到并解决的问题

**步骤**:
1. 在项目根目录创建 `TROUBLESHOOTING.md`
2. 格式：`## N. 问题标题` + Date/Symptom/Root Cause/Solution
3. 每解决一个问题立即追加记录
4. 包含技术细节和涉及文件

**关键决策**:
- 独立文件而非分散在代码注释中 → 方便跨会话查阅
- 按编号递增 → 便于引用
- 包含代码片段 → 可直接复用解决方案

**踩坑记录**:
- 无

**涉及文件**: `TROUBLESHOOTING.md`

---

### WF-9: 立绘合成（Mesh UV 重建算法）

**日期**: 2026-06-20
**目标**: 从 `_tex` AssetBundle 正确提取并拼合立绘图像
**适用场景**: Unity AssetBundle 中的立绘使用 Mesh UV 将纹理切割为多个四边形块，需要按 UV 映射重新拼合

**步骤**:
1. 加载 `_tex` bundle，提取 Texture2D 和独立 Mesh 对象
2. 用 `MeshHandler` 解析顶点数据（自动处理 channel 描述符和 stride）:
   ```python
   from UnityPy.helpers.MeshHelper import MeshHandler
   handler = MeshHandler(mesh_obj)
   handler.process()
   positions = handler.m_Vertices  # List[(x,y,z)]
   uvs = handler.m_UV0            # List[(u,v)]
   ```
3. 获取未翻转纹理（UV 坐标为 bottom-up 设计）:
   ```python
   from UnityPy.export.Texture2DConverter import get_image_from_texture2d
   texture_img = get_image_from_texture2d(data, flip=False)
   ```
4. ALPA 算法拼合：每 4 个顶点 = 1 四边形，UV[i] 和 UV[i+2] 定义源纹理矩形，Position[i] 定义粘贴位置，从后向前遍历
5. 最终输出翻转一次（bottom-up → 标准 top-down）:
   ```python
   return Image.fromarray(out_arr).transpose(Image.FLIP_TOP_BOTTOM)
   ```
6. 无 Mesh 的 bundle 直接返回纹理（fallback）
7. 全量运行：multiprocessing 并行，8 进程

**关键决策**:
- 顶点解析 → `MeshHandler`（而非手动解析 raw bytes），因为不同 bundle 的 stride 和 channel 布局不同
- 纹理获取 → `flip=False` + 最终翻转输出（而非 `flip=True` 直接用），因为 UV 坐标为 bottom-up 纹理设计
- 输出目录 → 扁平结构（无子目录），方便批量处理

**踩坑记录**:
- 手动从 `m_VertexData.m_DataSize` 按固定偏移读 position/UV → 不同 bundle stride 不同，导致全部乱码
- `data.image` 默认 flip=True → UV 坐标与翻转纹理不匹配，拼出的图倒转
- 最初方案：翻转纹理 + 翻转 UV V 坐标 → 复杂且易出错
- 最终方案：unflipped 纹理 + 原始 UV + 最终翻转输出 → 简洁正确

**涉及文件**: `scripts/synthesize_paintings.py`, `TROUBLESHOOTING.md`

---

### WF-10: Spine 动画提取与 WebGL Viewer

**日期**: 2026-06-22
**目标**: 从 AssetBundle 提取 Spine 骨骼动画数据，构建 WebGL 查看器
**适用场景**: 游戏资源解包后需要查看/播放 Spine 动画

**步骤**:
1. 识别 .skel/.atlas/.png 三件套格式（spine 3.8.99 二进制，非标准 4.x）
2. 编写 `extract_spine.py` 用 UnityPy 提取 TextAsset（.skel/.atlas）和 Texture2D（.png）
3. 处理多变体命名：`{name}B.skel`、`{name}M.skel`、`{name}T.skel`
4. 从 GitHub 下载 spine 3.8 runtime 源码（`3.8_spine-core.js` + `3.8_spine-webgl.js`）
5. 构建 WebGL Viewer：`ManagedWebGLRenderingContext` + `SceneRenderer` + `OrthoCamera`
6. 生成 `spine_manifest.json` 供前端读取角色列表

**关键决策**:
- 二进制格式 → spine 3.8（非 4.x），需下载 3.8 分支 runtime
- 渲染方案 → 最初用 Canvas2D `drawTriangles`（clip-based），三角形缝隙严重 → 切换 WebGL
- 预乘 Alpha → Unity 导出纹理使用 PMA，需 `premultipliedAlpha=true` + `ONE,ONE_MINUS_SRC_ALPHA` 混合
- Y 轴方向 → 数据为 Unity Y-up，WebGL camera 默认 Y-up，不需要 `skeleton.scaleY=-1`

**踩坑记录**:
- `Object.keys(skeletonData.animations)` 返回数组索引 `["0","1",...]`，不是动画名 → 需遍历 `.name` 属性
- Canvas2D clip-based 三角形渲染产生大量视觉伪影（碎裂效果）→ 改用 WebGL
- `skeleton.scaleY=-1` 在 Canvas2D 中修正方向，但在 WebGL 中导致上下颠倒 → 坐标系不同
- 部分 `_hx` 变体无独立 `_res` bundle → 资源在父 bundle 中
- `talin_4` 只有 png 无 skel/atlas → 异常数据

**涉及文件**: `scripts/extract_spine.py`, `tools/spine-viewer/index.html`, `tools/spine-viewer/spine-runtime/`

---

### WF-11: 子智能体（Subagent）并行策略

**日期**: 2026-06-22
**目标**: 优化大型任务的执行效率，合理使用 agent 并行能力
**适用场景**: 耗时操作、多模块并行开发、格式逆向工程

**Agent 类型选择**:

| 类型 | 适用场景 | 特点 |
|---|---|---|
| `explore` | 代码探索、格式分析、查找定义 | 只读，快速 |
| `general` | 实际编码、多步任务、复杂分析 | 可读写，完整能力 |
| `spawn` (background) | 耗时脚本执行、大批量处理 | 后台运行，父对话继续 |
| `run` (blocking) | 需要立即拿到结果的短任务 | 阻塞等待，结果内联返回 |

**适合派生子智能体的场景**:
1. **耗时脚本执行**（>5 分钟）→ spawn background agent 跑，父对话继续做其他事
2. **格式逆向工程** → explore agent 并行分析多个格式/文件
3. **大范围代码修改** → 多个 general agent 并行处理不同模块
4. **调试验证** → 等 subagent 结果回来后再决定下一步

**不适合的场景**:
- 单文件简单修改
- 需要频繁交互确认的任务
- 需要读取父对话上下文的任务（子智能体看不到父对话历史）

**父子通信规则**:
- `run` 模式：结果直接返回父对话，内联显示
- `spawn` 模式：子智能体完成后发通知，父对话下次响应时看到
- 同级子智能体之间**完全隔离**，不能互相读取
- 工作流总结时，只要把子智能体发现写入主对话文本，workflow-recorder 就能捕获

**本次项目中的应用反思**:
- `extract_spine.py` 全量运行（15 分钟超时）→ 应 spawn background agent
- `.skel` 二进制格式分析（多轮手动 Python）→ 应 explore agent 并行
- Canvas2D→WebGL 切换（读源码+写代码）→ general agent 可并行

**涉及文件**: 无（策略文档）

---

### WF-12: v2 数据驱动立绘/Spine 还原管线

**日期**: 2026-09-15
**目标**: 用游戏本体权威数据（prefab 层级 + 官方依赖表）自动还原静态立绘与 Spine，取代 v1 时代逐条目手调参数
**适用场景**: Unity UI 布局语义正确还原多部件立绘；跨包引用解析；皮肤命名归组

**步骤**:
1. **立绘匹配机制**（核心突破）：解析 `painting/<name>` prefab 的 RectTransform 层级，部件命名规律 `_rw`(人物)/`_bj`(背景)/`_front`(前景)/`_jz`(舰装)/`_n`(夜战)/`_hx`(换色)；脸多数烤进 `_rw`，仅约 4% 皮肤有独立 `face` 部件（表情差分来自 `paintingface/<name>` 包）。
2. **跨包引用解析**：`PPtr.m_FileID` → `SerializedFile.externals[N-1]`（CAB 名反查 bundle），**不是** dependencies 清单的字母序；FileID=0 为本包。官方 `dependencies` 包即权威依赖表。
3. **layout_all 布局还原**（正确 Unity UI 语义）：`sizeDelta`/`anchoredPosition` 在父局部空间做纯 anchor 数学（不乘 scale）→ 仿射映射到世界；自身 scale 绕 pivot（负=镜像）；root scale 是屏幕适配可归一为 1。
4. **纹理方向**：UnityPy `flip=False` 时第 0 行 = v=0 = Unity 底部，`Sprite m_Rect.y` 自底计数直接切片即 Y-up；Spine 页纹理导出须 `flip=True`（运行时按行 0=顶采样）。
5. **Spine 提取**（`extract_spine_v2.py`）：一个 `Spine_v2/<皮肤>/` 目录内含 1~8 个部件骨骼（B/M/T 等），须整体保留供前端分层合成；兼容无后缀 skel/atlas 变体（按特征嗅探）。
6. **全量驱动**（`run_v2_full.py`）：两阶段（Spine→静态），断点续跑（输出已存在则跳过），错误落盘。

**关键决策**:
- 目标皮肤清单 → **以真实源包 `files/AssetBundles/painting/` 为准枚举**（滤 `_tex`/`_res`/`_dark_shadow`/`_face`），并与旧 v1 基线取并集。旧版只从 v1 基线取名 → v1 没有的联动舰（2b/a2 等约 190 个真实皮肤）永不合成。
- 一切层间比例/位置由官方数据自然推导，**零手调参数**（v1 的 BUNDLE_BJ_ABSOLUTE/SCALES/OFFSETS 全部废弃）。

**踩坑记录**:
- 背景层颠倒 → sprite 路径双重 Y 翻转；Spine 页纹理方向错 → flip 参数用反。
- root scale 只乘子层 → 层间比例错误真根因（§9.3）。
- Windows 分离进程 stdout 默认 GBK，`print('✓')` 抛 UnicodeEncodeError → 全量假失败；脚本头 `sys.stdout.reconfigure(encoding='utf-8')` + 子进程 env `PYTHONIOENCODING=utf-8`。
- 手动命令行跑 compose 也需 `PYTHONIOENCODING=utf-8`，否则 ✓/✗ 崩。

**涉及文件**: `scripts/compose_paintings_v2.py`, `scripts/extract_spine_v2.py`, `scripts/run_v2_full.py`, `PROJECT_STATUS.md §11–12`

---

### WF-13: 本地资产浏览平台搭建

**日期**: 2026-09-15
**目标**: 参照 l2d.su 做一个可本地浏览全部已还原资产（静态立绘/Spine/Live2D/语音）、中文名展示的平台
**适用场景**: 解包产物量大（源 28GB / 立绘 15GB 数千张）无法发布上线，需本地高效浏览

**步骤**:
1. **数据索引**（`build_gallery_index.py`）：复用 `ship_name_map.SHIP_NAME_MAP`（拼音→中文名，812 条）+ `generate_audio_doc.CV_MAP`（语音ID→中文名）；资产目录/文件名 ID = 中文舰名拼音，按「归一化基ID → 完整皮肤 stem」分组，合并 `ship_data.json`（舰种/稀有度/阵营）。同时输出 `index.json` 与 `index.js`（`window.GALLERY=`）。
2. **缩略图**（`make_thumbs.py`）：多进程为高清 PNG 生成 380px WebP（含透明），否则数千张 3.5MB 原图浏览器加载不动。
3. **前端**（`index.html` 单文件）：网格懒加载缩略图 + 搜索 + 阵营/舰种/稀有度/内容多维筛选 + 排序；详情弹层四标签（立绘全图 / Spine WebGL 实时 / Live2D 贴图 / 语音 `<audio>`）。
4. **Spine 实时播放**：复用本机 `tools/spine-viewer/spine-runtime/3.8_spine-all.js`（拷入 `vendor/spine/`，纯 JS 无 wasm）；`ManagedWebGLRenderingContext`+`SceneRenderer`+`SkeletonBinary`，**按皮肤目录内 B/M/T 部件列表分层合成绘制**，相机包围盒自适应 + 滚轮缩放/拖拽平移。
5. **启动器**（`启动资产浏览器.bat`）：`Output/` 起 `py -m http.server` 并开 `/gallery_v2/index.html`。

**关键决策**:
- 形态 → 本地网页（体量决定发布上线不现实）。
- 数据加载 → 另存 `index.js` 让 `file://` 双击也能读到数据。
- Spine 运行时 → 复用本机已有 viewer 的 3.8 runtime，离线可用，不依赖网络。

**踩坑记录**:
- `<img>`/`<audio>` 在 `file://` 可直读，但 `fetch/XHR` 读 `.skel/.atlas/.json` 被 CORS 拦 → **实时播放必须起 http 服务器**；页面按 `location.protocol` 提示。
- `.bat` 里 `start URL` 若抢在 `http.server` 监听前会连不上 → 后台起服务器 + `timeout /t 2` 延时再 `start URL`，并探测 `py`/`python`。
- Live2D 动作播放需 Cubism Web 运行时（`live2dcubismcore.min.js`+`pixi-live2d-display`），本机无且环境出网受限 → 暂只显示模型贴图，预留 `vendor/live2d/`。
- 个别 bundle 拼音与 `SHIP_NAME_MAP` 拼写不一致（如 daofeng/dafeng）→ 约 7% 未匹配中文名，按约定保留拼音 ID。

**涉及文件**: `scripts/build_gallery_index.py`, `scripts/make_thumbs.py`, `Output/gallery_v2/index.html`, `Output/gallery_v2/启动资产浏览器.bat`, `PROJECT_STATUS.md §13`

> 2026-09-19 更新：前端源码已迁至仓库内 `gallery_src/`（唯一权威版本），改完跑 `scripts/deploy_gallery.py` 同步到 `Output/gallery_v2/`；服务器 `_gallery_server.py` 统一发 `Cache-Control: no-cache`，杜绝改版后浏览器吃旧缓存。

---

### WF-14: Spine setup pose 全屏 CG 批量导出

**日期**: 2026-09-19
**目标**: 批量导出全部 Spine 皮肤的「游戏皮肤详情全屏」同款完整 CG 静态图（painting bundle 只有半景特写条带，完整场景只存在于 Spine 资源）
**适用场景**: 需要 Spine 骨架的静态高质量渲染图（封面/画廊/对比审查），且本机无头浏览器可用

**步骤**:
1. **渲染通道复用前端运行时**：不重造 Spine 解析器。`gallery_src/cg_export.html` 用 `spine-all.js` 加载 `Output/Spine_v2/<皮肤>/*.skel + .atlas + 页纹理`，`setSlotsToSetupPose/setBonesToSetupPose` 后绘制全部件（多部件按 B/M/T 层序）。
2. **两段式构图**：①顶点包围盒（Region/Mesh `computeWorldVertices` 联合）定相机；②首绘后 `gl.readPixels` 扫 alpha 非零像素包围盒，覆盖率 <82% 则把相机重定到真实内容区重绘（修正被超大半透明部件撑歪构图的情况，如冒险号 0.32→0.83）。
3. **落盘**：canvas `toBlob`（WebGL 上下文必须 `preserveDrawingBuffer:true`）→ `POST /save_cg?name=<皮肤>` → `_gallery_server.py` 写 `Output/CG_v2/<皮肤>.png`；`GET /cg_exists` 支持断点续跑；URL 参数 `autostart/only/size/redo` 供自动化。
4. **无头驱动**：`scripts/diag/run_cg_export.py`（Chrome `--headless=new --remote-allow-origins=* --enable-unsafe-swiftshader --use-angle=swiftshader` + websocket-client CDP 轮询 `#prog/#log`），231 皮肤约 5 分钟。每个皮肤导出后 `GLTexture.dispose()` 防 4096² 页纹理堆爆显存。
5. **接入画廊**：`build_gallery_index.py` 扫 `CG_v2/` 附 `sk.cg`；前端「静态立绘」默认 CG、可切回原件；`make_thumbs.py` 生成 `<stem>_cg.webp`。

**关键决策**:
- 渲染器选型 → 复用浏览器 spine-all.js（WebGL 处理 mesh/换色/预乘 alpha 全对），放弃纯 Python 重写 skel 解析。
- 长边 2400px（SwiftShader 下 ~2s/张；4096 上限保护）。

**踩坑记录**:
- `SceneRenderer.resize()` **不更新相机视口**（恒初始 300×150）→ 渲染放大数倍「比例怪」；必须 `scene.camera.setViewport(cv.width, cv.height)`。
- 同块内 `let my=0`（鼠标坐标）遮蔽外层 `const my`（状态对象）→ 块内所有 `my` 引用进 TDZ，部件加载成功也抛「Cannot access 'my'」→ 假「N 层失败」。变量命名冲突是隐形炸弹，前端也适用。
- 动画名 `1..N` 多为 0 秒空占位（逐部件不同），真实动画是 `normal/touch_*/login/change_out` → 下拉过滤空动画、默认 normal、缺层回落。
- `beierfasite_g` 的 .skel 实为 JSON → 按首字节 `{` 分流 `SkeletonJson`。
- 浏览器缓存旧 `index.js` 会让「数据已生成但页面看不到」→ 服务器发 `Cache-Control: no-cache` 根治。

**涉及文件**: `gallery_src/cg_export.html`, `gallery_src/_gallery_server.py`, `scripts/diag/run_cg_export.py`, `scripts/build_gallery_index.py`, `scripts/make_thumbs.py`, `PROJECT_STATUS.md §6/§10`

---

### WF-15: 游戏版本更新后的增量重跑（资产同步 → 定位受影响子集 → 定向重建 → 证零回退）

**日期**: 2026-09-20
**目标**: 游戏出新版本（如 9.7.381 → 9.7.385）后，**只重跑受影响的那部分产物**，不打乱已验证正确的 4400+ 立绘 / 232 Spine / 260 Live2D，并且能证明「没改坏任何原本正确的东西」。
**适用场景**: 收到新版本资源包；或换了权威元数据源；或改了批处理脚本后需要落地。

#### 承重文件白名单（**清理磁盘前先核对，删了就断链**）
| 文件 | 谁依赖它 | 丢了能否复原 |
|---|---|---|
| `scripts/`、`scripts/diag/`、`gallery_src/`、`docs/`、根 `*.md` | —— | ✅ 已入 Git，随时可取 |
| `.diag/azdata_ship_{skin_template,data_statistics,data_template}.json`、`azdata_{tree,version}.json` | **`scripts/build_ship_meta.py` 的唯一权威输入**（舰名/阵营/舰种/稀有度/CV id 全从这里来） | ⚠️ 半可再生：社区快照会滞后（385 时最新仍 381），且 `sharecfgdata/*` 是**自定义加密**、本机无解 → **务必当源文件保护** |
| `Output/dependency_manifest.json`（~15MB / 86k+ 条） | `compose_paintings_v2`、`extract_spine_v2`（PPtr→包 依赖表） | ✅ 可再生：`export_dependency_manifest.py` |
| `Output/ship_meta.json` | `build_gallery_index`（元数据主源） | ✅ 可再生：`build_ship_meta.py --write` |
| `Output/WikiData/ship_data.json` | `build_gallery_index` 兜底 | ✅ 可再生：`scrape_wiki_fast.py`（需外网） |
| `Output/Paintings_v2`、`Spine_v2`、`Live2D`、`CG_v2`、`Audio`、`gallery_v2/` | 画廊 | ✅ 全量可再生，但**耗时数十小时**，故按 WF-15 增量而非全量 |

> `.diag/` 已写入 `.gitignore`，定位是「临时产物区」；**可复用工具一律放 `scripts/diag/`（入库）**。清理 `.diag` 前必须先跑上表白名单核对。

#### 步骤
1. **只读差异，先不动手**：`python scripts/mumu_sync.py diff` → 输出三类：新增（模拟器有/本地无）、大小不一致（同名但本地旧）、本地独有。记下版本号与数量（385 那次 = 95 文件）。
2. **同步源包**：`mumu_sync.py sync`（或 `mumu_adb.py pull`）落到 `files/AssetBundles/`。
3. **重生成官方依赖表**（**最容易漏的一步**）：`python scripts/export_dependency_manifest.py --out Output/dependency_manifest.json`。不重生成 → 新包的 PPtr/externals 解析不到 → 新皮肤合成失败或层级缺失。
4. **Unity 版本伪装**：新包 header 可能仍伪装 `5.x.x`。若加载报错，更新脚本里的 `UnityPy.config.FALLBACK_UNITY_VERSION`（当前 `2022.3.62f3`）为游戏实际引擎版本。
5. **定位受影响子集**（不要全量重跑）：按新增/变更包所在顶层目录（`painting` / `paintingface` / `spine` / `live2d` / `bg`…）映射到磁盘 stem 集合，写进 `.diag/affected.txt`。
6. **元数据是否也要跟新**：若社区 azdata 快照已更新到新版本 → 重跑 `build_ship_meta.py --write`；若没更新（如 385 时社区仍 381）→ 新皮肤的名字/阵营会缺，按 §6 待办 7 的决策处理（标「待补」，不要瞎猜）。
7. **定向重跑到临时目录**：`python scripts/compose_paintings_v2.py <stems> --out .diag/rerun`（Spine 用 `extract_spine_v2.py`，Live2D 用 `reconstruct_live2d.py`+`extract_motions.py`，全屏 CG 用 `python scripts/diag/run_cg_export.py --only a,b,c`）。
8. **出对比图交人工确认**（硬闸门）：`python scripts/diag/make_face_cmp.py` / `make_review_sheet.py` 这类前后对照；未确认**不得**换入正式目录。
9. **备份换入**：先 `cp` 旧件到 `Output/_OLD_bak/<主题>_<日期>/`，再**确认 `st_nlink==1`**（Paintings_v2 有 519 组硬链，直接覆写会串改孪生文件）后 `os.remove` + copy 换入。
10. **派生产物增量重建**：删受影响 `gallery_v2/thumbs/<stem>.webp` 后跑 `make_thumbs.py`（它对已存在者 skip，天然增量；`<stem>_cg.webp` 来自 CG_v2，别误删）→ `build_gallery_index.py` → `deploy_gallery.py`。
11. **证零回退**（三件套，缺一不可）：
    - **逐字段 diff**：新旧 `index.json` 比 ship 集合/皮肤集合/每字段，期望「只有该变的变」（label 改动那次 = 1746 条 label 变化、非 label 变化 0）。
    - **未涉及文件 mtime 未变**：证明没误伤（脸洞换入那次 = 其余 4454 张 mtime 全未变）。
    - **端到端可达**：起 http.server 对全部受影响 URL（png + webp）GET 200 且长度与磁盘一致；前端渲染类改动再用无头 Chrome 断言（`scripts/diag/l2d_sweep.py` 全量 260 模型加载+动作启动；`l2d_verify.py`/`l2d_click.py` 抽样与真实点击路径）。

#### 关键决策
- **增量而非全量**：全量重跑 4486 张立绘会打乱已人工确认正确的结果，且无法逐张复核。
- **对比图必须人工过目**：机器指标（不透明率/差异像素）会误判——`leiniya_wjz` 就是指标说"有问题"但目视才确认是回退（见 TROUBLESHOOTING §14）。
- **规则修正优先于例外表**：误判靠收紧判据解决，不写死名单。

#### 踩坑记录
- 跳过第 3 步（依赖表）→ 新皮肤合成缺层，症状像"脚本 bug"，实为数据源过期（385 那次即如此）。
- 判"动画是否在播"不能只看帧哈希：headless 下 rAF 被节流会假阴性，而 physics/眨眼会让帧变化造成**假阳性**；必须读 `motionManager.state.currentGroup` 非空（且 `startMotion` 后要等 ~1.5s 让它 fetch motion3.json）。
- `make_thumbs.py` 遇已存在文件直接 skip → 换入新图后**不删旧 webp 就不会更新**（静默留旧图）。
- 硬链接未检查就覆写 → 孪生文件被一起改掉。

#### 涉及文件
`scripts/mumu_sync.py`, `scripts/mumu_adb.py`, `scripts/export_dependency_manifest.py`, `scripts/compose_paintings_v2.py`, `scripts/extract_spine_v2.py`, `scripts/reconstruct_live2d.py`, `scripts/extract_motions.py`, `scripts/build_ship_meta.py`, `scripts/build_gallery_index.py`, `scripts/make_thumbs.py`, `scripts/deploy_gallery.py`, `scripts/diag/run_cg_export.py`, `scripts/diag/l2d_sweep.py`, `scripts/diag/l2d_verify.py`, `scripts/diag/l2d_click.py`, `scripts/diag/hit_verify.py`, `scripts/diag/make_face_cmp.py`, `scripts/diag/make_review_sheet.py`, `scripts/diag/scan_faces.py`, `scripts/diag/dedup_*.py`, `PROJECT_STATUS.md §6/§9/§10`

---

### WF-16: Live2D 画廊前端交互改动与回归验证（改哪里 → 怎么验证才算过）

**日期**: 2026-09-23
**目标**: 改动 `gallery_src/index.html` 的 Live2D 交互层（命中判定、动作、检查器 UI）后，用「不循环论证」的方式证明改动真的对。
**适用场景**: 用户反馈「点部位触发错动作 / 动作被切 / 模型发死 / 判定框画错位置」，或要加 Live2D 相关 UI。

**改哪里**:
| 层 | 文件 | 说明 |
|---|---|---|
| 前端源码（唯一权威） | `gallery_src/index.html` | 改完必须部署 |
| 部署 | `scripts/deploy_gallery.py` | 同步到 `Output/gallery_v2/`（运行目录，gitignore）；幂等，改完核对哈希一致 |
| 服务器 | `Output/gallery_v2/_gallery_server.py`（8777，已在跑则复用） | 回归脚本都打 `http://127.0.0.1:8777/gallery_v2/index.html` |
| 模型数据 | `Output/Live2D/<key>/` | 前端直读（`P="..\/"`），无副本 |

**四条必须记住的硬规则（每条对应一次真实事故）**:
1. **坐标系必须换算**：`getDrawableVertexPositions()` 是 V（Cubism 原生：画布中心原点、y 向上），`toLocal()/pixelsPerUnit` 是 P（左上原点、y 向下）。换算 `Vx=Px-cux/2`、`Vy=cuy/2-Py`（`cux=im.width/ppu`）。混用 → 点胸口触发头部动作（TROUBLESHOOTING §20）。
2. **命中必须先做包含判定**再就近取框，框外返回 null（否则点空白/任意处都触发最近部位，动作被反复打断，用户感受=「做得快/赶」，§19）。
3. **idle 循环交给运行时，前端不许挂定时器**（2026-09-23 二次修订，旧"看守者"方案已废弃）：`Meta.Loop` 被 vendored 库忽略，但正确修法是给 CubismMotion 本体 `setIsLoop(true)` + `setIsLoopFadeIn(false)`，并把 `mm.groups.idle` 对齐成实际组名（库默认 `'Idle'`），让库自带的"播完自动回 idle"生效。旧方案用 `armIdleLoop` 定时器按 `Duration-120ms` 重开，而 `startMotion` 是 async → `!==false` 恒成立 → **被 `state.reserve` 拒绝时前端无感**，实测造成 idle 播 9.1s 后**冻结 9.2s**。改后 30s 内 `startMotion` 调用 0 次、`currentGroup=null` 采样 0 个（§21）。
4. **验证不能自洽闭环**：合成点击若用被测映射的逆生成，永远全绿。必须用独立锚点（可见语义点反查 / 截图目视）——`l2d_coord_forensics.py` 就是干这个的。
5. **动作数据必须有外部权威基准，别自证清白**：`motion3.json` 的贝塞尔控制点是**绝对 (时间,值)**，运行时直读不做归一化还原；写成归一化分数会让每条贝塞尔都先猛蹿到≈0 再跳目标值，而**曲线集合/时长/参数名全部校验都能通过**（§21）。唯一能抓出它的是同模型的权威导出：`scripts/diag/l2d_ref_diff.py` 拉 l2d.su 的 `motions/<group>.motion3.json` 逐曲线采样比对。

**回归五件套（按顺序跑）**:
```bash
# 0) 部署
py -3 scripts/deploy_gallery.py
# 1) 权威基准比对（数据层唯一硬判据；参考库只覆盖部分模型，404 自动跳过）
py -3 scripts/diag/l2d_ref_diff.py antu_2 --clips idle,touch_head,touch_body,touch_special
py -3 scripts/diag/l2d_ref_diff.py --all          # 全量验收
# 2) 坐标系取证：head→Head / chest→Special / hip→Body，identityHits 必须全空
py -3 scripts/diag/l2d_coord_forensics.py lafeiii_3
# 3) 检查器验收（判定区/参数面板/滑杆往返/过滤器）
py -3 scripts/diag/l2d_inspector_verify.py lafeiii_3
# 4) 交互五项（滚轮/缩放/取消拖拽/空白点击不播/点部位命中）
py -3 scripts/diag/interact_verify.py
# 5) 全量按部位点击（约 25 分钟，269 皮肤；基线 806/807，唯一 z46_3 框嵌框歧义）
py -3 scripts/diag/hit_verify.py
```

**改动作数据/交互层后的补充体检（都是只读，几十秒）**:
```bash
py -3 scripts/diag/l2d_after_fix_check.py antu_2 yingrui_3   # 四项体检：breath=0 / isLoop / 30s 不冻结 / 点部位回落 idle
py -3 scripts/diag/l2d_restart_cadence.py antu_2 30          # 看 startMotion 调用次数与 currentGroup=null 采样数
py -3 scripts/diag/l2d_hit_overlap.py antu_2                  # 判定区重叠 + 淡入淡出实际值 + eyeBlink 是否创建
py -3 scripts/diag/l2d_touchidle_probe.py antu_2 touch_idle1  # 参数残留复位是否生效：判据 after 出画数==before、位移>0.3 的框数=0
```
⚠️ 该探针**必须走页面自己的 `play()`**（`sel.value=grp; sel.onchange()`），直接 `mm.startMotion` 会绕过复位逻辑所在的
前端交互层，把正确的修复读成无效（2026-09-23 真实误判过一次）；且要回读 `mm.state.currentGroup` 区分「静默失败」与「没复位」。

**判据**:
- `l2d_ref_diff` 必须 **PASS**：组/曲线集合零缺失、**关键帧零不一致**、偏差中位 ≤0.5、偏差>0.5 占比 ≤12%（WARN 线按安土实测 3.8%~9.6% 的贝塞尔天花板校准）。
- 坐标系偏移即视为失败（张冠李戴比「不触发」更糟）。
- `interact_verify` 的空白点击断言：`after=null` 视为通过（=idle 看守者重取数据的间隙，不是触发动作）。
- `hit_verify` 全量期望 **806/807**；若掉到 800 以下，说明包含判定或坐标换算被改坏。
- 无头环境 fetch/parse 比真机慢（约 1.5s），idle 轮换间隙明显；**别把无头掉帧当成 bug**。
- `interact_verify` 偶发 `Execution context was destroyed` 是多个无头 Chrome 实例抢 profile 的假失败，**重跑一次即可**，不要当成回归。

**踩坑记录**:
- 无头验证脚本的 JS 以 `})` 结尾再在 Python 侧拼 `(key)` 调用；写成 `})()` 再拼会变成「调用返回值的返回值」报 `not a function`。
- 归档到 `scripts/diag/` 的脚本 `ROOT` 要三层 dirname（`.diag/` 里的是两层）。
- 页面脚本未就绪时先轮询 `window.GALLERY && typeof openShip==='function'`，只等 `GALLERY` 会在偶发时序下报 `openShip is not defined`。**轮询必须带 `await`**（同步空转循环等于没等）。
- ✅ **脚手架「日志开头若干行报 `GALLERY is not defined`」根因已定位（2026-09-23）：不是脚手架代码，是 `8777` 画廊服务器没在跑。**
  Chrome 连不上时把 tab 换成**自己的导航失败错误页**，于是页面全局永远不会出现。
  - **一刀切判别式**（比看异常文本可靠得多）：`document.title` 变成**主机名**（`127.0.0.1` 而不是「碧蓝航线资产浏览器」）、
    `document.scripts` 里**没有 `src=` 的标签**（只有 Chrome 自己的两个大内联脚本）、
    `readyState` 却是 `complete`、`typeof openShip==='undefined'`。
    四条同时成立 = **服务器不在**，别再查页面代码或 CDP。
  - **为什么容易误判成代码问题**：`readyState=complete` 会让人以为页面加载成功了；而错误页也是"完整文档"。
  - **已排除的假设（都实测过，别再重走）**：① 就绪等待写成同步空转 → 改成带 `await` 的轮询 + 对 `err` 重试 3 次**仍报同一错**；
    ② `ev()` 缺 `awaitPromise` → 核实**本来就有**；③ CDP 落在陈旧/隔离 context → `Page.navigate` 重新提交文档**也没救回来**。
  - **可复用的自查手法（这条站得住）**：先看失败行是否**恰好集中在日志开头**——是 → 环境/冷启动；分散 → 才怀疑产品。
    再核对「失败对象的输入侧数据是否真的缺」：本次靠查这 6 个模型 `model3.json` 的 HitAreas 数量（都是 3 个）
    一步排除了产品回退。
- ⚠️ **杀回归脚本必须连 Chrome 一起杀，且清理脚本要按整条命令行匹配。** `--user-data-dir` 的值**含空格且常不带引号**
  （`D:\Azur Lane Assets/.diag/chrome_hitv`），用正则去截 `--user-data-dir=(...|[^ ]*)` 只会截到 `D:\Azur` 而漏杀。
  正确做法：`CommandLine -match 'Azur Lane Assets' -and CommandLine -match 'chrome_hitv|chrome_galprobe|...'`。
  本次实测：只杀 python 主进程后残留 **4 组无头 Chrome 占着 CDP 端口 9342/9377/9378/9379**，
  正是「多个无头 Chrome 抢 profile → 偶发假失败」的来源。

**涉及文件**: `gallery_src/index.html`、`scripts/deploy_gallery.py`、`scripts/diag/{l2d_coord_forensics,l2d_inspector_verify,interact_verify,hit_verify}.py`、`TROUBLESHOOTING.md` §19/§20

---

### WF-17: Live2D 动作语音导出与接线（ACB cue → 动作组 → 浏览器出声）

**日期**: 2026-09-23
**目标**: 让 Live2D 动作带配音（同游戏），并把导出管线固化成可复用脚本。
**适用场景**: 用户反馈「动作没有声音 / 语音没接上 / 新皮肤缺语音」，或要给 Spine/静态皮肤补配音。

**关键事实（每条都踩过，别再重来）**:
- Live2D 包内**没有任何音频**（antu_2 对象统计 2671 MonoBehaviour / 104 AnimationClip / **0 AudioClip**）。语音在独立的 CRIWARE `files/AssetBundles/cue/cv-*.b` 里。
- **一个 `.b` = 一条船的全部语音 bank（45~170 条带名字的 cue）**。2026-06 那次 `export_cue_audio.py` 用 `vgmstream-cli -o x.wav file.acb` **只取了第 1 条**（`detail`），其余全丢 → 每船只剩 3 个 wav，还靠一张 719 条的社区 `CV_MAP` 归船名（安土都不在表里 → `voices=[]`）。**这是个潜伏已久的老 bug**，Spine/静态皮肤的配音也一直是缺的。
- **cue 名与 model3.json 的动作组名逐字同名**：`home/login/mail/main_1..4/mission_complete/touch_head` 全部精确命中，**不需要游戏配置**就能对上。
- 皮肤 → ACB：`.diag/azdata_ship_skin_template.json` 的 `painting` 字段 = 磁盘皮肤名 → skin id → **`cv-{skin_id // 10}.b`**。270 个 Live2D 皮肤里 **253 个**命中现有 ACB。
- 音频编码是 **CRI HCA**（不是 ATRAC9），vgmstream 可解；一个 ACB 里 `stream count` = cue 数，`stream name` = cue 名。

**怎么做**:
```bash
py -3 scripts/extract_live2d_voice.py --report --only antu_2   # 只列映射，不写任何文件
py -3 scripts/extract_live2d_voice.py --key antu_2             # 单皮肤小样本
L2D_VOICE_ALL=1 py -3 scripts/extract_live2d_voice.py          # 全量（必须显式开环境变量）
```
脚本**拒绝默认全量**。产物：`Output/Audio/L2D/<皮肤>/<cue>.ogg`（opus 48k）+ `Output/gallery_v2/l2d_voice.json`（`{皮肤: {动作组: [相对 P 的音频路径...]}}`，同组多条 = 随机变体）。

**前端接线**（`gallery_src/index.html`）：vendored `pixi-live2d-display` 0.4.0 **原生支持 motion 定义的 `Sound` 字段**（`startMotion` 里 `getSoundFile(def)` → `SoundManager.add/play`，并自动 dispose 上一条），**只需注入 `definitions[g][0].Sound`**，不要自己管 Audio 元素；`resolveURL` 的基准是 model3.json 所在目录，故注入**绝对 URL**。
> ⚠️ 该库**没有**音频驱动口型（全 bundle 无 `AnalyserNode`/`AudioContext`/`setLipSyncValue`）。要做口型得自己接 WebAudio 取包络写 `ParamMouthOpenY`。

**判据**（量真实可观测状态，别用代理指标）:
- 探针 `scripts/diag/l2d_voice_probe.py` 量的是：`definitions[g][0].Sound` 非空 + `mm.currentAudio` 存在 + **`paused=false` 且 `currentTime` 前进** + `err=null` + 无 `Failed to play audio` 警告。
- ⚠️ **无头 Chrome 是空声卡，`paused=false` 只证明 Audio 元素起来了，证明不了用户能听见** —— 真实出声必须靠用户耳朵验收，这一点不许拿探针结果顶替。
- 界面旁证：下拉框里有语音的组标「（语音）」，状态栏 pill 显示「语音 N 组」。

**踩坑记录**:
- **改完不部署等于没改**：语音接线代码写完没跑 `deploy_gallery.py`，用户复测仍报「一点声音都没有」，白查一轮。改 `gallery_src/index.html` 后**必须** `py -3 scripts/deploy_gallery.py` 并核对 md5 与源一致。
- **探针必须走页面真实入口**：直接调库的 `mm.startMotion` 会绕过页面自己的 `play()`，凡是挂在 `play` 上的逻辑（动作语音、参数复位）都测不到 → **假阴性**。要走下拉框 `sel.onchange()` 这类真实用户路径。
- **语音表异步加载的竞态**：模型刚就绪那一瞬播的动作（含 idle）会拿不到 `Sound`，表现成「第一个动作没声、之后才有」。修法是把开局 `play(def)` 挪到 `loadVoiceMap()` resolve 之后，并加 `!played.size && !mm.state.currentGroup` 守卫，避免覆盖用户已触发的动作。
- `touch_body → touch_1`、`touch_special → touch_2` 是**按「普通触摸 / 特殊触摸」语义推的**，不是从游戏配置读到的（配置包见 `TROUBLESHOOTING.md` §22）。同名匹配的 9 组可信；这两条要人工试听裁定。
- 后缀约定：`X` / `X_1` / `X_2` = 同一触发的随机变体；**`_exNNNN` 是活动限定台词、`vocal_*` 是歌曲人声，都不该在点模型时放**（脚本已排除）。
- 音量走库的 `SoundManager._volume` 默认 0.5。
- vgmstream 本机路径 `C:\Users\KLLM\AppData\Local\vgmstream\vgmstream-cli.exe`（2026-09-23 经 gh-proxy 镜像重装 r2117，含 `libatrac9.dll`）；**丢过一次**，导出脚本跑之前要先确认它在。
- 解压全部 cue 后只转码需要的那几个（一个 ACB 全解出 64 条 = 67MB PCM，全量 253 皮肤会到 17GB）→ 只导动作组对得上的，转 opus 48k。

**涉及文件**: `scripts/extract_live2d_voice.py`、`gallery_src/index.html`（Sound 注入 + 下拉「（语音）」标签 + 语音 pill + 开局播放竞态修复）、`scripts/diag/l2d_voice_probe.py`、`Output/Audio/L2D/`、`Output/gallery_v2/l2d_voice.json`、`TROUBLESHOOTING.md` §22
