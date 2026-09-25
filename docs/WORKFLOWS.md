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
1. 安装依赖：`pip install UnityPy Pillow`（要解 Unity 中国版 AssetBundle 加密还需 `pip install pycryptodome`，
   UnityPy 的 `ArchiveStorageManager.decrypt_key` 依赖它；2026-09-25 实测）
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

#### WF-6 追加（2026-09-26）：贴图索引顺序从"纸面决策"变成有实现 + 有闸门

上面「纹理顺序 → 必须按名称字母序排列」这条决策**写了三个月但脚本里从未实现**，
老模型全靠 UnityPy 枚举序碰巧有序。新 bundle 换入后 5 个模型渲染成部件堆叠的碎片，
而当时的验收判据（"idle 驱动了多少条参数"）全绿。详见 `TROUBLESHOOTING.md` §40。

- **实现**：`fix_model3.py` 现按名中数字归一 `FileReferences.Textures`（幂等，只在有变化时写盘）。
- **判据（闸门）**：`py -3 scripts/diag/l2d_texorder_check.py`
  → 只读检查全库 `Textures` 是否升序，乱序即退出码 1 并逐条打印前后清单；
  `--apply` 才改写。**换入新 bundle 后必须跑到退出码 0。**
- **判据（看图，不可被代理指标顶替）**：`py -3 scripts/diag/l2d_shot_models.py <key> ...`
  走画廊真实入口逐个打开 Live2D 皮肤，按 canvas 的 `clip` 只截模型区，落 `.diag/l2d_shots_visual/`。
  前置：`127.0.0.1:8777` 已起（根 = `Output/`）。
  ⚠️ 视觉产物（立绘合成 / Live2D / Spine）的验收**必须包含目视截图这一步**；
  "加载成功""参数在动""帧哈希在变"都只是代理指标，贴图错绑这一类故障下它们全部为真。
- **踩坑**：moc3 头 offset 8 起的 `Format/Size/CanvasWidth/CanvasHeight` 在本项目全部为 0，
  照公开 moc3 规范硬解 `Textures` 段会读出 95/347 这种荒谬计数——索引→名字的映射
  **取不到**，只能靠命名约定（`texture_%02d` 编号即索引）+ 全库正常产物反证。
- **配套完整性审计**：`py -3 scripts/diag/l2d_tex_completeness.py`
  逐模型把源 bundle 的 `Texture2D` 清单与磁盘 PNG 对账（`missing`/`extra`/非 `texture_%02d` 命名/源缺失，
  任一非 0 退出码 1）。存在的理由是 `extract_textures()` 的 `except: continue` 会**静默少一张**。
  2026-09-26 全量基线：**269/269 全绿，missing 0 / extra 0 / 命名异常 0**。
  同一脚本顺带打印"源枚举序 ≠ 编号序"的模型（**51/269**）——**只提示不判红**，
  因为归一化已由 `fix_model3.py` 承担；这个数字的作用是说明**归一化是承重步骤，不是装饰**。
  新 bundle 换入后：先跑 `--apply` 归一 → 跑本审计对账 → 再用 `l2d_shot_models.py` 看图，三步缺一不可。
- **目视覆盖怎么抽**（全库数百个模型不可能逐个看，但"随便看几个"又不算证据）：
  按**结构自由度分桶，每桶至少一个**——本案取 `(moc3 版本 × 贴图数)` 共 15 桶，
  26 个样本即全覆盖；再单独把**最极端的桶成员**（贴图数最多、枚举序最乱）全看一遍。
  报告里必须写清"看了 N/M、覆盖哪些桶、没覆盖的部分结论边界在哪"，
  否则下一轮会把"26 个看过"读成"全库验过"。

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
| `inputs/azdata/azdata_ship_{skin_template,data_statistics,data_template}.json` + `azdata_version.json` | **`scripts/build_ship_meta.py` / `extract_live2d_voice.py` 的唯一权威输入**（舰名/阵营/舰种/稀有度/CV id 全从这里来），也是 `tools/sharecfg_re` 的已知明文基准 | ⚠️ 半可再生：社区快照会滞后（385 时最新仍 381），且 `sharecfgdata/*` 是**自定义加密**、本机无解 → **务必当源文件保护**。2026-09-24 从 `.diag/` 迁到此处；`sha256` 台账 = `inputs/azdata/MANIFEST.json`，跑前 `py -3 scripts/diag/check_inputs.py` 校验。旧 `.diag/azdata_tree.json` 经核实内容是 14 字节 `Invalid input.`（上游报错残留，非数据），已删不再列入白名单 |
| `Output/dependency_manifest.json`（~15MB / 86k+ 条） | `compose_paintings_v2`、`extract_spine_v2`（PPtr→包 依赖表） | ✅ 可再生：`export_dependency_manifest.py` |
| `Output/ship_meta.json` | `build_gallery_index`（元数据主源） | ✅ 可再生：`build_ship_meta.py --write` |
| `Output/WikiData/ship_data.json` | `build_gallery_index` 兜底 | ✅ 可再生：`scrape_wiki_fast.py`（需外网） |
| `Output/Paintings_v2`、`Spine_v2`、`Live2D`、`CG_v2`、`Audio`、`gallery_v2/` | 画廊 | ✅ 全量可再生，但**耗时数十小时**，故按 WF-15 增量而非全量 |

> `.diag/` 已写入 `.gitignore`，定位是「临时产物区」；**可复用工具一律放 `scripts/diag/`（入库）**。清理 `.diag` 前必须先跑上表白名单核对。
> **权威外部输入一律不得放进 `.diag/`**——2026-09-24 起它们住在 `inputs/<来源>/`（数据本体不入库、只入 `MANIFEST.json` 台账），
> 跑任何依赖它们的管线前先校验：`py -3 scripts/diag/check_inputs.py`（逐文件比 sha256/bytes，缺失或漂移即非零退出）。

#### 步骤
0. **先验权威输入**：`py -3 scripts/diag/check_inputs.py` 必须 `[PASS]`，再动任何元数据/语音管线。
1. **只读差异，先不动手**：`python scripts/mumu_sync.py diff` → 输出三类：新增（模拟器有/本地无）、大小不一致（同名但本地旧）、本地独有。记下版本号与数量（385 那次 = 95 文件）。
2. **同步源包**：`mumu_sync.py sync`（或 `mumu_adb.py pull`）落到 `files/AssetBundles/`。
3. **重生成官方依赖表**（**最容易漏的一步**）：`python scripts/export_dependency_manifest.py --out Output/dependency_manifest.json`。不重生成 → 新包的 PPtr/externals 解析不到 → 新皮肤合成失败或层级缺失。
4. **Unity 版本伪装**：新包 header 可能仍伪装 `5.x.x`。若加载报错，更新脚本里的 `UnityPy.config.FALLBACK_UNITY_VERSION`（当前 `2022.3.62f3`）为游戏实际引擎版本。
5. **定位受影响子集**（不要全量重跑）：按新增/变更包所在顶层目录（`painting` / `paintingface` / `spine` / `live2d` / `bg`…）映射到磁盘 stem 集合，写进 `.diag/affected.txt`。
6. **元数据是否也要跟新**：若社区 azdata 快照已更新到新版本 → 重跑 `build_ship_meta.py --write`；若没更新（如 385 时社区仍 381）→ 新皮肤的名字/阵营会缺，按 §6 待办 7 的决策处理（标「待补」，不要瞎猜）。
7. **定向重跑到临时目录**：`python scripts/compose_paintings_v2.py <stems> --out .diag/rerun`（Spine 用 `extract_spine_v2.py`，Live2D 用 `reconstruct_live2d.py`+`extract_motions.py --out .diag/<临时目录>`，全屏 CG 用 `python scripts/diag/run_cg_export.py --only a,b,c`）。
   > ⚠️ **脱离宿主进程跑的长任务里，"写到哪"必须走 argv（`--out`），不能只靠环境变量**：`Start-Process` 下
   > 子进程能否读到 `$env:X` **不可复现**（同一脚本同一启动方式，两个变量生效、输出目录那个没生效），
   > 2026-09-24 因此把 269 个模型的 `motion/` 跳过闸门原地覆写进了 `Output/Live2D`（见 `TROUBLESHOOTING.md` §25）。
   > `extract_motions.py --all` 现要求 `--out`，否则拒绝（确需直写正式目录才加 `--into-production`）。
8. **出对比图交人工确认**（硬闸门）：`python scripts/diag/make_face_cmp.py` / `make_review_sheet.py` 这类前后对照；未确认**不得**换入正式目录。
9. **备份换入**：先 `cp` 旧件到 `Output/_OLD_bak/<主题>_<日期>/`，再**确认 `st_nlink==1`**（Paintings_v2 有 519 组硬链，直接覆写会串改孪生文件）后 `os.remove` + copy 换入。
10. **派生产物增量重建**：删受影响 `gallery_v2/thumbs/<stem>.webp` 后跑 `make_thumbs.py`（它对已存在者 skip，天然增量；`<stem>_cg.webp` 来自 CG_v2，别误删）→ `build_gallery_index.py` → `deploy_gallery.py`。
11. **证零回退**（三件套，缺一不可）：
    - **逐字段 diff**：新旧 `index.json` 比 ship 集合/皮肤集合/每字段，期望「只有该变的变」（label 改动那次 = 1746 条 label 变化、非 label 变化 0）。
    - **未涉及文件 mtime 未变**：证明没误伤（脸洞换入那次 = 其余 4454 张 mtime 全未变）。
    - **端到端可达**：起 http.server 对全部受影响 URL（png + webp）GET 200 且长度与磁盘一致；前端渲染类改动再用无头 Chrome 断言（`scripts/diag/l2d_sweep.py` 全量 260 模型加载+动作启动；`l2d_verify.py`/`l2d_click.py` 抽样与真实点击路径）。
    - **改的是"解析优先级"而不只是某个字段时，先把「换档」整体枚举出来再定判据**：新档往往不只影响目标子集，还会**接管**别的兜底档（大小写不敏感回退那次，76 个无源目录之外还接管了 136 个手抄表 `SHIP_NAME_MAP` + 2 个 `manual` 条目）。闸门脚本 `scripts/diag/ship_meta_authority_diff.py`：① 受保护档（本来就走配置桥的 painting/suffix）7 字段改动必须 0；② 条目集合不得增减；③ 换档只允许落在白名单新档；④ 无源数等于期望。另附**第三方裁判**（只打印不判红）：改名条目拿 `Output/WikiData/ship_data.json` 的维基名表投票，看有没有"只有旧值命中"的反例。口径见 `TROUBLESHOOTING.md` §39。

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
    **现成工具**：`py -3 scripts/diag/page_sanity_check.py` 一次打印这四条 + 全部 CDP target，
    跑任何 CDP 回归前先扫它一眼，能省掉一整轮误查（本次就是靠它定位的）。
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

- ⚠️ **每一轮 CDP 批处理都会在 `.diag/` 留一个几百 MB 的无头 Chrome profile**（`--user-data-dir`），39 个就能吃掉 7.7 GB。
  收尾必跑：`py -3 scripts/diag/clean_diag_profiles.py`（干跑看清单）→ 加 `--yes` 删。三条硬判据全过才删：
  目录名 `chrome_*` / 无 chrome|msedge 进程命令行引用它 / 最后修改早于 `--min-age`（默认 30 分钟，防误删并发会话在写的）。
  它只碰 `chrome_*`，`.diag` 下其它产物一律不动——清理 `.diag` 仍要先核对 WF-15 白名单。
- **登记/新增 HitArea 必须做几何校验**（2026-09-24 §27）：`fix_model3.py` 早期只判断 `"Touch"+名` 这段字节是否出现在 moc3 里，于是**零面积标记、彼此重合的标记**也被登记成部位框；而前端「重叠取面积最小者」会让面积≈0 的框**永远抢赢**合法大框（真人又点不中它）。前端已在 `geomOf` 里挡掉退化框（判定与可视化同源），源头校验仍待补进 `fix_model3.py`。取证工具：`py -3 scripts/diag/l2d_hit_geom_forensics.py [key ...]`（逐框：自己是否接受自己的中心点 + 谁赢）与 `--scan-all`（全库退化/同几何统计，落 `.diag/l2d_hit_geom_scan.json`）。
- **A3（重叠即随机）之后 `hit_verify` 的断言口径**：断言对象从「必须等于自己」改成**「实播必须落在产品 `window.__L2_HITALL` 的候选集合内」**，只有落在集合外才是 `WIRING`（真 bug、非零退出码）；`HIT`（等于自己）与 `INGROUP`（同组另一条）都不算失败。另报两个总指标：**可点中率**与**静止态网格重叠统计**。
  测法两条硬规矩：① 候选集合**每次点击时重算**（模型在呼吸，旧集合会虚报「点了没反应」）；② 随机性必须在**冻结 `app.ticker`** 后测（不冻结则同一位置瞬时候选数会跳，`distinct=1` 是假信号），而点击测试又必须让 ticker 跑 → 所以分两阶段。见 §27「A3 实施记录」。
- **断言要区分「几何上本就该别人赢」与「链路真断」**：`hit_verify.py` 现给四类 `HIT / SHADOWED / WIRING / OUTSIDE`，**只有 WIRING（真实派发 ≠ 产品 `hitAt` 判定）算 bug、才给非零退出码**；`SHADOWED` 是多个 `Touch*` 标记几何重叠的必然结果（产品按最具体优先是设计）。几何判定一律调产品暴露的 `window.__L2_HIT`，**探针不许自己复算一份几何**（复算版实测与真实派发 4/38 条不一致，拿它下结论就是自证）。 同理 `l2d_inspector_verify.py` 的判定区那条：2026-09-24 起断「画出的框 == 产品 `window.__L2_HITUSE()` 可用清单（逐个标签相同）」，不再是「== 登记数」——退化框被 `geomOf` 挡掉后两者本就不等（§27）。
- **CDP 脚本每条退出路径都要回收 Chrome**（`try/finally` + 按父 PID 连子进程一起停）：泄漏的无头实例会与下一轮抢 profile，复现出 `Execution context was destroyed` 那类假失败（2026-09-24 亲测踩中，见 §27 末段）。
- ⚠️ **跑 `l2d_ref_diff.py` / `l2d_ab.py` 比对临时重导目录时，必须显式带 `L2D_OUT_DIR=<临时目录>`。** 不给的话
  ref_diff 比的是正式目录（自证清白），`l2d_ab.py` 的"新侧"会读默认的陈旧目录得出"新旧一致"的假结论；
  而 ref_diff 在只含 `motion/` 的临时目录上曾经**全部 SKIP 却退出 0**。三处假绿灯的根因与判据见 `TROUBLESHOOTING.md` §24。

**收尾**: 一轮 CDP 回归结束后 `py -3 scripts/diag/clean_diag_profiles.py --yes` 清 profile（见上），并确认 `.diag` 里没有本次新写的唯一副本代码（按 AGENTS.md 第 3 步移入 `scripts/diag/` 或删除）。
- **判活用 `powershell -File scripts\diag\wait_for_detached.ps1 -Pattern <脚本名> -Log .diag\_x.log`**，不要拿 `Start-Process -PassThru` 的 PID 去 `Wait-Process`：那只是 `py.exe` 启动器，且 `Wait-Process` 抛错会被 try/catch 读成"已退出"（2026-09-24 把还在跑的 269 模型回归误判成断了）。该工具按「命令行匹配 python.exe 工作进程 + 日志行数是否还在涨 + 有无汇总行/traceback」给三分法结论；加 `-StallRounds 2` 还能判出「进程活着但日志不涨」的**挂死**。
- **启动长任务用 `py -3 scripts/diag/run_detached.py --log .diag/_x.log -- py -3 <脚本> <参数...>`**，别再用 PowerShell `Start-Process`：含空格路径在「bash → PowerShell → 子进程」三层引号下会被拆断（实测三次）。`DETACHED_PROCESS` 与 `CREATE_NO_WINDOW` 互斥，同时给会 `[WinError 87]`。
- **含中文的 `.ps1` 必须存成 UTF-8 带 BOM**，否则 Windows PowerShell 5.1 按 GBK 解码会把引号错位成 `字符串缺少终止符`（`wait_for_detached.ps1` 首跑就是这么死的，`py -3` 写文件时用 `encoding='utf-8-sig'`）。

**涉及文件**: `gallery_src/index.html`、`scripts/deploy_gallery.py`、`scripts/diag/{l2d_coord_forensics,l2d_inspector_verify,interact_verify,hit_verify,page_sanity_check,clean_diag_profiles,l2d_ref_diff,l2d_ab}.py`、`TROUBLESHOOTING.md` §19/§20/§24

---

### WF-17: Live2D 动作语音导出与接线（ACB cue → 动作组 → 浏览器出声）

**日期**: 2026-09-23
**目标**: 让 Live2D 动作带配音（同游戏），并把导出管线固化成可复用脚本。
**适用场景**: 用户反馈「动作没有声音 / 语音没接上 / 新皮肤缺语音」，或要给 Spine/静态皮肤补配音。

**关键事实（每条都踩过，别再重来）**:
- Live2D 包内**没有任何音频**（antu_2 对象统计 2671 MonoBehaviour / 104 AnimationClip / **0 AudioClip**）。语音在独立的 CRIWARE `files/AssetBundles/cue/cv-*.b` 里。
- **一个 `.b` = 一条船的全部语音 bank（45~170 条带名字的 cue）**。2026-06 那次 `export_cue_audio.py` 用 `vgmstream-cli -o x.wav file.acb` **只取了第 1 条**（`detail`），其余全丢 → 每船只剩 3 个 wav，还靠一张 719 条的社区 `CV_MAP` 归船名（安土都不在表里 → `voices=[]`）。**这是个潜伏已久的老 bug**，Spine/静态皮肤的配音也一直是缺的。
- **cue 名与 model3.json 的动作组名逐字同名**：`home/login/mail/main_1..4/mission_complete/touch_head` 全部精确命中，**不需要游戏配置**就能对上。
- 皮肤 → ACB：`inputs/azdata/azdata_ship_skin_template.json` 的 `painting` 字段 = 磁盘皮肤名 → skin id → **`cv-{skin_id // 10}.b`**。270 个 Live2D 皮肤里 **253 个**命中现有 ACB。
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

**产物体检与备份口径**（只读，几秒）:
```bash
py -3 scripts/diag/l2d_voice_inventory.py            # 映射表 / 磁盘 ogg / 模型目录 三方对齐
py -3 scripts/diag/l2d_voice_inventory.py --verbose  # 列缺失引用与孤儿明细
```
2026-09-24 实测：映射表 **253 皮肤 / 2504 动作组条目 / 引用 5914** 条，磁盘 **5914** 个 ogg，**缺失引用 0、孤儿 0**，269 个模型里 16 个无语音映射（= `--report` 的 17 无 ACB 减去 `_ab` 这个非模型目录）。
**口径结论：语音产物不需要单独备份**——`l2d_voice.json` 与 ogg 都由「已入库脚本 + `files/AssetBundles/cue/cv-*.b` + `inputs/azdata` 权威快照」确定性再生（实测 `--report` 与全量导出均可重跑，映射逐条复现）。真正不可复原的是 `inputs/azdata/*.json`，所以口径落在**输入侧**：跑前 `check_inputs.py`（WF-15 步骤 0），产物本身随 `Output/` 大资产整体策略走。

**踩坑记录**:，用户复测仍报「一点声音都没有」，白查一轮。改 `gallery_src/index.html` 后**必须** `py -3 scripts/deploy_gallery.py` 并核对 md5 与源一致。
- **探针必须走页面真实入口**：直接调库的 `mm.startMotion` 会绕过页面自己的 `play()`，凡是挂在 `play` 上的逻辑（动作语音、参数复位）都测不到 → **假阴性**。要走下拉框 `sel.onchange()` 这类真实用户路径。
- **语音表异步加载的竞态**：模型刚就绪那一瞬播的动作（含 idle）会拿不到 `Sound`，表现成「第一个动作没声、之后才有」。修法是把开局 `play(def)` 挪到 `loadVoiceMap()` resolve 之后，并加 `!played.size && !mm.state.currentGroup` 守卫，避免覆盖用户已触发的动作。
- `touch_body → touch_1`、`touch_special → touch_2` 是**按「普通触摸 / 特殊触摸」语义推的**，不是从游戏配置读到的（配置包见 `TROUBLESHOOTING.md` §22）。同名匹配的 9 组可信；这两条要人工试听裁定。
- 后缀约定：`X` / `X_1` / `X_2` = 同一触发的随机变体；**`_exNNNN` 是活动限定台词、`vocal_*` 是歌曲人声，都不该在点模型时放**（脚本已排除）。
- 音量走库的 `SoundManager._volume` 默认 0.5。
- vgmstream 本机路径 `C:\Users\KLLM\AppData\Local\vgmstream\vgmstream-cli.exe`（2026-09-23 经 gh-proxy 镜像重装 r2117，含 `libatrac9.dll`）；**丢过一次**，导出脚本跑之前要先确认它在。
- 解压全部 cue 后只转码需要的那几个（一个 ACB 全解出 64 条 = 67MB PCM，全量 253 皮肤会到 17GB）→ 只导动作组对得上的，转 opus 48k。

**涉及文件**: `scripts/extract_live2d_voice.py`、`gallery_src/index.html`（Sound 注入 + 下拉「（语音）」标签 + 语音 pill + 开局播放竞态修复）、`scripts/diag/l2d_voice_probe.py`、`Output/Audio/L2D/`、`Output/gallery_v2/l2d_voice.json`、`TROUBLESHOOTING.md` §22

---

### WF-17 追加（2026-09-25）：动作组→cue 的别名不再靠猜，改由游戏本体表驱动

- **规则**：`scripts/extract_live2d_voice.py` 的 `ALIAS` 由 `inputs/gamecfg/character_voice.json` 生成
  （`l2d_action → resource_key`，只收不同名的那条），文件缺失时**退回原来两条猜测并打 stderr 警告**，
  不会静默变少。取表/发布：`tools/sharecfg_re/41 → 42`（带 4 条真值自检，自检不过不写台账）。
- **判据**：改别名表后，必须用**只读**的 `--report <皮肤key>` 做 A/B：
  把 `inputs/gamecfg/character_voice.json` 临时移走 = "改前"，放回 = "改后"，比 `(动作组数, 各 cue 文件名列表)`。
  ⚠️ **不要拿生产 `l2d_voice.json` 当"改前"基线**——它是旧日期、旧动作组集合下生成的，
  差异里混着别的变量的变化（本轮就差点据此把 `login/mission_complete` 的缺席记成自己引入的回退）。
- **踩坑**：`--report` 会逐个 cue 走 vgmstream，单皮肤也要几十秒 → **别在前台跑**，会被宿主超时打断。
- **零回退闸门（已入库为工具）**：`py -3 scripts/diag/l2d_voice_diff_check.py [旧表] [新表]`
  判据 = 丢掉的 (皮肤,组) 0 / 丢掉的皮肤 0 / 磁盘缺失音频 0 / `<2KB` 占位 0，退出码非 0 即不通过。
  ⚠️ 它按 **相对 `Output/`** 解析映射里的路径（`Audio/L2D/<皮肤>/<cue>.ogg`），拿 `gallery_v2/` 当根会误报"全部缺失"。
- **完成判定看条数不看退出码**：`grep -c '组=' 日志` 应等于映射表皮肤数；`grep -cE 'Traceback|Exception in thread'` 必须 0。

### WF-18: 逆向里给一个函数判"作用域"与把"否证"做成穷举级（调用方反查 + 自由度压缩 + 三条对照）

**日期**: 2026-09-24
**目标**: 对一个已读出算法的函数，判定它**到底作用在哪份数据上**，并把"这套算法产不出明文"从抽样结论升级为**穷举结论**。
**适用场景**: 逆向小项目卡在"算法拿到了但解不出明文"，正在纠结"要不要先弄密钥/是不是还差一层封装"。本 WF 出自 `tools/sharecfg_re/` 的 `www()` 线（一次方向性错误的完整回收过程）。

**怎么做（顺序即判据，跳步就还是猜）**:
1. **别从数据侧猜，从"谁调用它"反推作用域**：全库扫 `E8/E9 rel32` 求交叉引用，拿到宿主方法，再读宿主里
   **喂给它的那一行**（`ReadAllBytes` / 切片 / 解压 / 资源查询）以及**它的输出下游被谁消费**。
   输入来源 + 输出去向两头一夹，函数的合法作用域就是闭集，不需要猜。
2. **由输出去向反查"验收判据可不可达"**——但**必须先确认 callee 身份**，否则这一步会反向制造假结论。
   本轮真实教训：我看到 `www()` 输出附近一条 `call` 就断言它进 `luaL_loadbuffer`，于是宣布上一轮的判据
   "输出须含 `UnityFS`"不可达、并据此关掉整条分支。**那是错的**：`0x3D9C8F6` 处实际是 `mov rsi, r15`
   （把 www 的输出搬进 arg1），真正的 call 在 `0x3D9C8FC` = `LuaScriptMgr.LoadABFromBytes(byte[], Action<AssetBundle>)`，
   下一条就是 `MonoBehaviour.StartCoroutine` → **产物是 AssetBundle，`UnityFS` 恰恰是对的判据**。
   → 规则：**要用"输出去向"否定一条判据，必须把该调用点前后指令逐条贴出来引用（含 callee 的 `dump.cs` 签名），
   缺一条就不许写"定死"。** 判据可达性检查本身仍然值得做，只是它的结论强度等于你对 callee 的确定程度。
3. **算清算法的自由度，能压缩就压成穷举**：若输出某字节只取状态的少数几位、且状态递推**仿射且只向高位进位**，
   则整条密钥流只由状态低位决定 → 有效种子空间从 `2^32` 塌到 `2^16`。此时"起点穷举过但种子没穷举"这个漏洞可以**封死**。
4. **不扫种子，改反解**：目标前缀首字节直接钉死 `state₀` 的对应位段，候选从 65536 掉到 256，逐字节过滤。
   与全量检验完全等价，且每个目标可报出**期望假命中数** = 偏移数 × 2^(自由度-8×前缀长)，据此判定命中是否有意义。

**判据**:
- 报"已排除"之前，必须能说出**排除的是哪个自由度集合**（"试了 235 这个种子" ≠ "试了所有种子"）。
- 目标前缀 **≥5 字节**才有意义（<5 字节的命中一律按噪声带解释，且要在表里标出期望假命中数）。
- **三条对照任一不过就拒绝输出否证**（脚本内 `exit 3`）：
  ① 压缩假设本身要测（只改种子高位、输出须逐字节不变）；② 反解阳性对照（随机构造埋点须反出原值）；
  ③ **埋针灵敏度对照**（在真文件里种 N 处目标密文，须 N/N 抓到）。

**踩坑记录**:
- 只做 ①② 不够——本轮 ② 全绿（400/400）但 ③ 第一次 **0/5**。因为"数学可逆"和"读文件+扫偏移+报命中这整条链路会响"是两件事。
- 写**加密方向**时极易把状态推进用的字节弄反：解密侧 `c = buf[i]` 取的是**密文**，所以加密时 state 必须用
  **写下去的那个 c** 推进，不是明文。（本轮真实 bug，埋针对照抓出来的。）
- 过滤类循环里 append 回去的必须是**推进后的状态**，不能顺手 append 种子——本轮第一版就错在这，400/400 全挂。
- 反查调用方前先确认**索引覆盖率**：宿主方法名靠 VA 反查，若 dump 缺 `VA:` 字段会静默错归属。
  实测办法 = 数一下索引里 `VA` 缺失的条数，并验 `RVA == VA == Offset + 常数` 是否恒等。
- 结论是"这函数不管这份数据"**不等于**分支作废：它可能作用在**同一份数据的另一种形态**上
  （本轮：`www` 不碰磁盘 `sharecfgdata/<name>`，但内存里有 `sharecfg/<name>.lua` 清单 → 它可能正是那个 `.lua` 的解密封）。
  收口时要把"作废"写成"改接到哪去了"，否则下个会话会连这条线索一起丢。

**涉及文件**: `tools/sharecfg_re/08_disasm_method.py`（`--xref` / 反汇编 / 字面量解引用）、
`tools/sharecfg_re/26_www_wrapper.py`（封装谓词 + 反解器 + 三条对照）、`tools/sharecfg_re/README.md` (15)(16)。
相关：技能 `binary-container-vs-crypto`（零假设/阴性对照总则）、`TROUBLESHOOTING.md` §22。

### WF-19: 从 il2cpp metadata 的字段默认值堆里按**内容**取 `static readonly T[]` 真值（免 token→索引映射）+ 用已知明文把内联密钥判死

**日期**: 2026-09-25
**目标**: 游戏代码里 `static readonly byte[]/int[] X = new T[N]{...}` 这类**内联数组**（头部魔数、Footer、TEA 密钥表…）在二进制里没有符号、`dump.cs` 不给长度，但它们在 `global-metadata.dat` 里有一份**唯一真值**。本 WF 给出：不解 token 索引也能按内容把它们取出来，并把"这就是那张表"钉成行为证据。
**适用场景**: IL2CPP 逆向里"算法读全了、只差内联常量表"；或要判断某个容器封帧的头部/尾部真值。

**怎么做（顺序即判据）**:
1. **先重新对齐 metadata 头，不要用记忆里那张 v24–v29 节序表。** 把 `@8+8i` 处的 int32 两两读成 (offset,size) 打到 i=0..47，
   再拿**两个独立事实**去钉哪一对才是目标节：① 目标节的 `size % 记录步长 == 0`；② 内容侧（如某个已知 magic 在全文件的命中位置）必须**整段落在**该节区间内。
   v31 比 v24–29 的表多一对，直接照记会让整节错位（见 §29）。
2. **记录布局用自检验证，不用文档**：`(fieldIndex, typeIndex, dataIndex)` 三条同时成立才算认出来 —
   fieldIndex **逆序数须为 0**（表是排序的，因为运行时用二分）、dataIndex **100% 单调不减**、`max(dataIndex) + 最小 blob ≤ 堆大小`。
3. **blob 长度 = 相邻 dataIndex 之差**（堆是 packed 顺序写死的）。这一步直接免掉"必须先解 token→fieldIndex"这座山：
   数组长度不用猜、也不用 image 的 `fieldStart`。
4. **按内容定位，不按索引定位**：用**已知明文**（真实文件头几个字节）或**结构约束**（长度恰为 76B 且能读成 19 个高位非零 int32）当筛子。
   命中数本身就是强度：整堆 879KB 里长度恰为 76 的 blob 只有 2 个，其中一个显然是文本 → 候选只剩一个。
5. **归属由"用起来对不对"证明，不由索引推断证明**：把目标函数（`www()` Phase C）机器码**逐指令**落成一个纯函数，
   拿真文件跑，判据要是一个 **64 位以上的具体值**（本例：头 8 字节须等于 `UnityFS\0`）。命中即同时证明了密钥、算法、以及"这个 blob 就是那张表"。
6. **人口级旁证**：把判据铺到全库（91,642 个 AB）上看分布——只有 2 个文件头 8 字节是密文、其余 86,561 个是明文 `UnityFS`。
   分布本身排除了"统计巧合"和"我挑了两个特例"。
7. **三条对照缺一不出结论**（沿用 WF-18）：① 实现自洽（`inv_walk(walk(x))==x` 随机 5000 组）；② 阳性；③ **埋针**（把 `inv_walk(目标明文)` 种进**真文件头**，扫描器须找回偏移 0）。

**判据**:
- "取到真值"的唯一形式是**用它算出了别的已知量**；"从堆里读出一段像密钥的字节"不算。
- **优先挑"两边都能独立算出来"的量**（第 6 步之后追加的 A3 就是这么来的）：AB 文件头里自报的 `fileSize`
  是文件内字段，`filesize - 4 - L` 是外部算出来的，两者对上 = 一次命中即几乎零假阳的 proof；
  而**分布类统计量（可打印率、熵、字节直方图）一律不得当解密判据**——实测一段确定解真的载荷
  可打印率只有 0.216，比"随机水平"还低（见 §30）。
- 报"某个 blob 就是某个字段"时，必须同时报出：候选总数、筛子强度（多少位）、以及是否有行为验证。
- 数组**长度**只认机器码里的 `Array::New(N)`，不认 `dump.cs`（后者不输出数组长度）、也不认"相邻 blob 之差"（那只是上界）。
- 元素宽度由**同一 klass slot** 反推：`int[2]` 与 `int[19]` 都用 slot `0x717DB78` ⇒ 19 个 int32=76B，不是 19 字节。

**踩坑记录**:
- 见 §29（节序照记 → 整轮否证打在错区域）。
- **元素数 ≠ 字节数**：`Array::New(0x13)` 记成"19 字节密钥"直接把上一轮引到"找 19 字节数组"的内存盲扫上，白花一轮。
- 埋针的读数坑：把 `plain[:8] + stream(x)` 拼起来打印，会看到 `UnityFS\0UnityFS\0`，其实是拼接处重复了 8 字节。
  **先确认每段的偏移再断言内容**（本轮真踩到，差点据此宣布"8..15 也是 magic"）。
- 反馈流写 `out[i] = (state>>8) ^ c` 必须 `& 0xFF`：机器码用的是 `dl`，天然截断；Python 里忘了就 `ValueError`。
- 反汇编 il2cpp **内部调用**（`icxx_` thunk，`dump.cs` 里没符号）要按 VA 直接反汇编：`08_disasm_method.py --at 0x<VA>`，
  本轮 `InitializeArray` → `jmp 0x3585406` → `call 0x352a944` → `call 0x3532d4a` → `0x35b39a0` 整条链才把"句柄→blob 地址"的算术读出来
  （它内部就是二分 `fieldDefaultValues` + `堆基址 + dataIndex`，与第 2/3 步的自检互为印证）。

**涉及文件**: `tools/sharecfg_re/28_blob_heap_known_plaintext.py`（节序对齐 + 记录自检 + 内容定位 + blob 切分）、
`tools/sharecfg_re/29_www_xxtea_key_test.py`（Phase C 逐指令落地 + 三重对照 + 全配置扩围）、
`tools/sharecfg_re/30_www_endtoend_reproduce.py`（三段端到端复现 + A1~A5 自洽判据 + 产出参照明文载荷）、
`tools/sharecfg_re/08_disasm_method.py`（本轮新增 `--at` 反汇编 icxx_ thunk、`--xrefslot` 按**数据 VA** 反查
rip 相对引用——"同一把密钥/同一个静态槽还有谁在用"只能这么查；实测密钥槽全库仅 `www()` 一处引用）、
输入 `files/il2cpp/Metadata/global-metadata.dat`。
相关：`WF-18`（否证要做成穷举级 + 三条对照）、`TROUBLESHOOTING.md` §29 与 **§30**（字节序读反 + 可打印率当判据两件事故）、技能 `binary-container-vs-crypto`。

---

### WF-20: 私有容器攻文法——先查公开同族实现，再用「帧覆盖残差 0 + 字段集对拍 + 值级交叉验证」三连验收

**日期**: 2026-09-25
**适用场景**: 手上有一份"标准解析器读不出、统计特征暧昧"的私有二进制（自定义容器/序列化/混淆格式），要在不掌握源码的前提下把**文法**（记录帧 + 类型 tag + 字符串编码）钉死；尤其适用于已经做过若干轮熵/IC/差分签名/已知明文自撞却零进展的情况。

**怎么做（顺序即判据，第 0 步不许跳）**：
0. **先检索公开同族实现**（约 20 分钟，成本远低于一轮统计攻击）。用**代码里读到的符号名**当搜索词最有效：本例 `LuaConfDataReader`、`sharecfgdata`、`luabuilds`、`confNEO`、`1b4c4a` 一次命中 `Fernando2603/AzurLaneDataExtractor`。检索用 `mcp__github__search_code/search_repositories` + 只读 `get_file_contents`（**不要 clone、不要跑第三方二进制**；墙内 raw.githubusercontent 不稳时走 API）。
1. **拿它的"格式事实"，不要拿它的代码**：读它的 reader 源码 → 把规则写成**自己的**实现（本项目 `37_parse_sharecfgdata.py`）。先查 LICENSE；无 LICENSE 即默认保留全部权利，vendor 进来会把许可风险带进仓库。
2. **先取证再实现**：写一个 `--trace`（头部逐字段 + 常量区起点）和一个 `--kgc`（把常量区读成平铺条目列表并原样打印）模式。**平铺打印是最便宜的一步，它直接把"结构装配关系藏在哪儿"暴露出来**（本例：标量字段键值紧邻可读；嵌套字段被打散，装配在指令区）。
3. **三连验收（缺一条不得声称"文法已破"）**：
   - **帧覆盖残差 = 0**：所有记录长度相加必须**正好等于文件长**，空记录 0。这条不含任何主观阈值，且天然可证伪（帧模型错 → 必然残差非 0 或提前崩）。
   - **字段集对拍**：从数据里解出的高频键，与**独立来源**的字段表（另一个仓库人写的 schema、或社区 JSON 的键）逐项比。命中集合大小本身就是强度，不需要阈值。
   - **值级交叉验证**：挑一个"语义上应当与外部真值相等"的字段（本例 `ship_skin_words.drop_descrip` ↔ `azdata_ship_skin_template.desc`）做整串命中计数。**这是唯一能证明"解出来的值是对的"而不是"解出来的值自洽"的量。**
4. **同一份数据的两个来源做差分**（体积、比例、键集合）。比例无恒定关系即可当场排除"压缩/编码膨胀"这一整类解释。
5. **每条旧否证都要重问一次"它测的是哪个对象"**：格式类否证尤其容易打在错误的表示层上（本案两条：按标准 LuaJIT tag 走 ULEB → 判"不是 BC"，实际是 S-box 置换过的 BC；未解掩码直接按 GB18030 解 → 判"不是文字"，结论对但理由是"数据在掩码下"）。

**判据**:
- "文法已破" = 上面第 3 步三条**同时**成立；只有第 1、2 条只能说"帧和键名读对了"，值正确性未证。
- **残差 0 优先于任何分布统计量**（延续 WF-19 / §30：可打印率、熵一律不当解密判据）。
- 报"某个字节段是 X 编码"时，必须同时报：**用它解出来的一段可人手判读的真文本**（本例：`feeling3` → "虽然能让大家变强很高兴…"）。

**踩坑记录**:
- **掩码下标的"归零边界"必须实测**：`^(255-i)` 的 i 是**每串各自从 0 起**，不是全文件位置。当成全局下标时，我在同一份数据上跑过 256 相位穷举 + 全量可打印率扫描，一条都没有——**判据用"整串合法 UTF-8"而不是"可打印率"**才看得见命中。
- **不要在"顶层结构"上赌启发式**：常量区顶层实测是「前置特殊键 + 数组部分 + 行字典 + 环境尾巴(`pg`/`_G`/`<表名>`/`base`)」混排，按"键值严格交替"配对会把行字典错当成某个键的值（本例第一版就是这样，`ship_skin_template` 只解出 5 个键）。正确做法：**先把平铺条目原样打印出来看**，再定配对规则。
- `read_float` 一族的 varint 拼接容易写出 `0x70F` 这类笔误（对方源码里就有，只在 `serializer.decode_float` 这条不被主路径使用的函数里）——**浮点字段单独抽样复核**。
- 第三方仓库的 README/代码可能只覆盖到它自己那版游戏；**版号差（本例 385 vs 381）会伪装成"解析缺陷"**，值级交叉验证要按"命中率"读，不要按 0/100 读。

**追加判据（同日 B 段，本案已按此把验收做到 99.974%）**：
- **给常量流找一条可数的不变式当搜索预言机**。本案里容器头部有一个 `kgc` 字段 = **常量区顶层条目的精确条数**，
  加上"末条必须正好停在记录末尾"，就得到一个**不含任何阈值的判据**；用它能把"解码偏差"定位到
  "读完第 k 条之后"，比人眼对齐字节快一个数量级（本例第 20 条崩 → 直接指向 `01` 的语义歧义）。
- **同一个字节在不同位置可以有不同含义**：`01` 在顶层 = 表头、在值位 = bool false；`02` 在 bool 字段 = true、
  在整数字段 = varint。**遇到"某一条突然走飞"先怀疑位置语义，而不是怀疑密钥/加密**。
  定死它的办法 = 找一处"`01` 后面的字节恰好是下一条键的长度字节"的实例（本案 `01` + `19` = "spine_offset_profile"）。
- **缺键 ≠ 解析失败**。这类表**空值不落盘**（本案 31.9% 的字段对是"键不存在 = 取默认值"）；
  比对时必须按"基准要的是不是默认值"分桶，否则一致率会被假红灯压掉 30 个点。
- **验收按字段类型分桶报**，不要给一个总百分比：本案标量 138,669 对 **99.974%**，
  容器 15,933 对只有一层以内能读通（值不内联，需要指令装配）——混在一起报会同时掩盖两类缺陷。

**涉及文件**: `tools/sharecfg_re/37_parse_sharecfgdata.py`（`--trace` / `--kgc` / `--entries` 条目数判据 / `--solve` / `--table` / `--verify` / `--all --yes` / `--scalar-all --yes`）、`tools/sharecfg_re/38_grammar_walk.py`（从已知锚点逐条走、崩在第几条直接打印）、
`docs/TROUBLESHOOTING.md` §33（本案完整结论 + 需要更正的旧否证）、`inputs/azdata/`（值级交叉验证的独立基准）。
相关：`WF-18`（否证做成穷举级）、`WF-19`（判据优先挑两边可独立算的量）、技能 `binary-container-vs-crypto`（建议把"第 0 步先查公开实现"并进去）。
    - **展示层（画廊组名/卡片标签）的兜底必须写成"加法"**：新兜底排在既有来源之后，并限定来源档白名单，于是命题变成"只可能把无名的变成有名、既有名字一律不动"，可用逐字段 diff 机器核验（索引那次：1008 组 +74 有名、有名组 0 处被改、4491 皮肤 0 处变化）。若把新兜底排在旧来源之前，会顺带改动上百组显示名——那属于另一次需用户拍板的展示决策，不得夹在修 bug 里做掉。详见 `TROUBLESHOOTING.md` §39 追加。
