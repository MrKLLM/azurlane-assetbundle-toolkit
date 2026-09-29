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
- ~~Live2D 动作播放需 Cubism Web 运行时（`live2dcubismcore.min.js`+`pixi-live2d-display`），本机无且环境出网受限 → 暂只显示模型贴图，预留 `vendor/live2d/`。~~ **已过时**（2026-09-20 起动作播放已接通）；当年"出网受限拿不到库"这件事本身仍是真风险，所以 2026-09-26 给这 4 个库立了台账 `gallery_src/vendor/MANIFEST.json` + `scripts/fetch_gallery_vendor.py`，见本文 WF-16「运行时库台账」。
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

#### WF-14 追加（2026-09-26）：Spine 必须 `setSkin`，否则命名 skin 里的部件整块不显示

- **规则**：spine-ts 3.8 的附件时间线经 `Skeleton.setAttachment` → **`当前 skin.getAttachment(slotIndex,name)`**
  解析。**不设 skin ⇒ 凡附件只在命名 skin 里的槽位一律 null**。画廊 Spine 标签与 `cg_export.html`
  此前都从未调用 `setSkin`（grep 命中 0；注意 index.html 里的 `setSkin(sk)` 是画廊"切换舰皮"函数，**同名不同物，grep 时极易看错**）。
- **选法（改规则不写例外表）**：对 `∅` 与每个命名 skin 各算一次
  「推进若干动画后**曾挂上附件**的槽位数」，取最多者作默认；控制条加「皮肤」下拉（含 `(不设 skin)`）可人工比。
  平手（阿罗芒什 `1` vs `2` 都是 201）按 skin 列表顺序取第一个。
- **判据（全量扫描）**：`py -3 scripts/diag/spine_skin_scan.py [--only a,b] [--limit N]`
  → 每 part 一行 JSON + 末尾 `SUMMARY {...}`。2026-09-26 基线：**331 part / 受影响 4 / gain 合计 182 槽**。
  ⚠️ 超过 8 分钟，走 `scripts/diag/run_detached.py`。
  逐槽细节：`scripts/diag/spine_skin_probe.py <folder> <槽名正则>`（列每个槽的 setup 附件名 / 各 skin 下挂到什么 / 所属图集页）；
  `fit` 取景异常用 `scripts/diag/spine_bounds_probe.py <folder>` 列撑大包围盒的槽位。
- **踩坑（判据差点自证成功）**：`cover()` 里如果把"纯 setup pose 的附件并集"也算进去，
  而 setup 附件走 `slotData.attachmentName`、**与 skin 无关**，四个 skin 会全相等、`gain` 恒 0。
  本轮就是**阳性对照（已知坏掉的 aluomangshi_2）报"没影响"**才发现判据写错。
  → 判据只量"动画跑起来之后实际挂上的附件"；任何全量扫描先拿一个已知阳性样本验它确实会报警。
- **踩坑（headless 里 spine 判据的等待）**：`--tab spine` 截图要等图集页下载完
  （阿罗芒什 4 页共 18MB、`yunlong_2` 的 skel 单只 81MB），固定 5s/6.5s 等待会让 `#spSkin` 下拉还没建出来，
  误报成"该皮肤没有 skin"。→ 轮询到元素出现，别用固定等待。
- **未修的两件事**：① `fit()` 被 `hei1/hei2` 这类 28000 单位宽的近透明遮罩撑大 → 弹窗里画面只占中间一小块
  （实测与 skin 无关，两种 skin 下 bbox 逐字相同；试过把 fit 挪到首帧 apply 后，无效已退回）；
  ② `suweiaitongmeng_4` / `yuanchou` / `yuanchou_hx` 三个报 `Region not found in atlas`，
  缺失区域名是 `￥ﾛﾾ￥ﾱﾂ 664` 这种 mojibake → 指向 `.skel` 与 `.atlas` 区域名编码不一致（参 §32）。
- **⚠️ CG 导出层：光加 `setSkin` 不解决问题**（2026-09-26 实测，别照 viewer 的修法抄）。
  `cg_export.html` 渲染的是 **setup pose**，而 setup 附件取自 `slotData.attachmentName`、**与 skin 无关**
  （`aluomangshi_2` 四种 skin 下 setup 附件数恒为 145，腿一条不回来；设 skin + 应用动画后才 201）。
  腿是**动画第 0 帧的 AttachmentTimeline** 挂上去的 ⇒ 导出要多一步
  `?animFrame=1` → `setAnimation(0,'normal',true); update(0); apply(skeleton)` 再渲染。
  已实现为**默认关闭**的开关（`gallery_src/cg_export.html` 的 `ANIM_FRAME`）：开着它会改**全部 231 张**的
  构图语义——对照皮肤 `2b_2` 在 1400 下画布高度 821→824，即"没有皮肤问题的也会跟着挪几像素"。
  ⇒ 要开就得整体重导 231 张，不能只重导 4 张留下混合语义。
  不开 `animFrame` 时 `bestSkin` 仅在"命名 skin 覆盖严格大于 ∅"时生效 → 327 个 part 走**原代码路径**，
  那 4 个 part 的 setup pose 输出也与改前相同（145 附件不变）。
  跑法：`py -3 scripts/diag/run_cg_export.py --only aluomangshi_2 --size 1600 --extra 'animFrame=1' --redo`
  （`--extra` 是本轮给该 runner 加的透传参数）。
- 详见 `TROUBLESHOOTING.md` §42。

#### WF-14 追加（2026-09-26）：取景判据 = "这一刻会不会落笔"，两套工具与两条否证

- **弹窗侧已修**：`gallery_src/index.html` 的 `boundsOf()` 里
  `if(slot.data&&slot.data.color&&slot.data.color.a<=0.001)continue;`
  —— setup alpha=0 的整屏遮罩不参与取景。判据必须用 **`slot.data.color`（setup 色）**，
  不能用 `slot.color`（当前色，会被动画时间线改写 → 按「复位」时框会随动画时刻跳）。
- **量取景的两个工具（都是只读，成对使用）**：
  - `scripts/diag/spine_framing_scan.py` —— 全库算三个包围盒（`boxAll` / `boxSetup` / `boxEver`）
    并给 `gainSetup=sqrt(areaAll/areaSetup)`；331 part 约 40s。**开跑前自带 8777 预检**
    （服务器会静默死掉，没预检就会刷几百行"spine 运行时未就绪"的假故障）。
  - `scripts/diag/spine_view_framing.py` —— 量**真实弹窗截图**里"非背景像素占视口"。
    报两个数：`长轴占满`（满分线 0.91，因为适配留 1.1 倍边）与 `面积占比`
    （会被宽高比失配稀释，单看会把正常竖图误读成取景过小）。
  - 前置：`py -3 scripts/diag/l2d_shot_models.py --tab spine <key...>` 先出图。
- **两条已否证的方案，别再试**：
  1. **"沿所有动画采样曾 alpha>0 就算内容"** —— 闪黑幕只要在某条动画里亮一次就永远算内容，
     阳性对照 `siwanshi_4` 报 `gain=1.0`（等于没修）。判据要落在**取景那一刻**。
  2. **首帧 `readPixels` 求非透明像素包围盒**（CG 导出层的做法）—— 弹窗里动画一直在跑、
     页纹理又是首次 `draw` 才上传，读回来的是"局部已就绪"的渲染：`mojiaduoer_5` 被量成
     只含天空渐变小块 → 放大成一屏模糊色块。**CG 层能用是因为它渲静止姿态且 `draw()` 后显式 `sleep(30)`。**
- **第二类已修（同日下一轮，见 §46）**：**不透明纯色巨幕**（黑底板 `heimu`/`1heidi`）真的在渲染，
  "会不会落笔"对它无效。判据 = **区域纹素 × `slot.data.color` 之后**，
  "落笔（`alpha×a>8`）里 `max(r,g,b)>40` 的占比" ≥0.05。
  **两侧都必须乘**：`1heidi` 是黑贴图×白乘数，而 `yunlong_3` 的 `kkkkk*` 是**白贴图 × `rgb=0,0,0` 乘数**
  （只看贴图它亮度 255，完全不像黑底）。两条捷径已排除：按部件名会误伤 2B 的真背景板 `bj_1`
  （4513×2655，nonBlack=0.992）；按纯黑乘数也不行（多数黑幕 setup 色是 `rgb=1,1,1`）。
  开销：逐个附件全算 300~1000ms/part（中位 298ms）不可接受 ⇒ **只测贴着当前包围盒某条边的附件**，
  从外向里剥 ≤6 轮，结果按 `(页,区域,乘数)` 缓存。剥到空框必须退回上一轮（`yunlong_3` 实测会走到）。
  工具 `scripts/diag/spine_region_ink_scan.py`（全库 331 part；`--dump` 可打运行时结构）。
  影响面 **17/325**（最大 2.79 倍），其余 308 个包围盒逐字不变；对照皮肤指标逐字相同。
  ⚠️ **指标要同时看 `fillInk`**：`spine_view_framing.py` 的 `fill`（非背景棋盘像素）会被纯黑巨幕顶成满分。
- ⚠️ **CG 侧原有的"二次构图按 alpha>8"会被纯黑巨幕骗过**：`aluomangshi_2` 的 CG 自报"覆盖 0.83"看着健康，
  实际打开是"一大片纯黑里嵌一小块舞台"。**alpha 包围盒 ≠ 构图对不对**，这一类必须看图。
  （现 `cg_export.html` 的取景已换成与弹窗同一套 `framingBox`；样本已验、全量重导待确认。）

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
| `inputs/gamecfg/name_code.json`（456 行） | 台词正文里 `{namecode:NN}` 的**唯一展开表**，`build_skin_words.py` 的第二个输入 | ⚠️ 半可再生：`41_export_lua_tables.py` 从设备侧 sharecfgdata 重导 lua 表 → `46_publish_name_code.py`；对齐关系由 `43_check_namecode_alignment.py`（带零假设）证成。2026-09-27 从 `.diag/sharecfg_re/lua_json/` 迁到此处，`sha256` 台账同 `MANIFEST.json` | | **台词中文正文的唯一副本**，`scripts/build_skin_words.py` 的唯一输入 | ⚠️ 半可再生：要能跑通 `sharecfgdata` 容器文法（§33/§36，`37_parse_sharecfgdata.py --scalar-all`）。2026-09-27 从 `.diag/sharecfg_re/cfg_json/` 迁到此处（原先只住在那儿，清盘即永久丢失）；`sha256` 台账 = `inputs/gamecfg/MANIFEST.json` |
| `Output/dependency_manifest.json`（~15MB / 86k+ 条） | `compose_paintings_v2`、`extract_spine_v2`（PPtr→包 依赖表） | ✅ 可再生：`export_dependency_manifest.py` |
| `Output/ship_meta.json` | `build_gallery_index`（元数据主源） | ✅ 可再生：`build_ship_meta.py --write` |
| `Output/WikiData/ship_data.json` | `build_gallery_index` 兜底 | ✅ 可再生：`scrape_wiki_fast.py`（需外网） |
| `Output/Paintings_v2`、`Spine_v2`、`Live2D`、`CG_v2`、`Audio`、`gallery_v2/` | 画廊 | ✅ 全量可再生，但**耗时数十小时**，故按 WF-15 增量而非全量 |
| `Output/gallery_v2/vendor/`（4 个第三方 JS，1.3MB） | 画廊 Live2D/Spine 标签的运行时 | ✅ 可再生（2026-09-26 起）：台账 `gallery_src/vendor/MANIFEST.json`（版本+字节+sha256+来源）+ `py -3 scripts/fetch_gallery_vendor.py`。**库本体不入库**（含 Live2D 专有许可的 Redistributable Code）。⚠️ 唯 `spine/spine-all.js`(3.8.75) 无可按哈希校验的下载源（本机这份与上游官方构建不同），只能从 `tools/spine-viewer/spine-runtime/` 取——**它也在 gitignore，别清** |
| `gallery_src/` 4 个前端正本 ↔ `Output/gallery_v2/` 同名 4 文件 | 画廊前端 | ✅ 同一份数据两个路径名（硬链，2026-09-26 起 4/4）。断链探测器：`py -3 scripts/deploy_gallery.py --check` |

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
9. **备份换入**：`py -3 scripts/diag/painting_swap_in.py --list <清单> --from <临时目录> --bak Output/_OLD_bak/<主题>_<日期>/`
   —— 四道硬检查（① 换入后 `st_nlink==1` ② 备份与原文件 md5 全等 ③ 换入后与临时渲染 md5 全等
   ④ **全目录快照**：mtime/nlink 变化集合必须正好等于清单）。
   > ⚠️ **硬链组必须显式断链**（2026-09-27 实测）：`Paintings_v2` 有历史去重留下的共享 inode，
   > `shutil.copyfile` 是**顺 inode 写**的，会把这些孪生文件一起改掉。默认模式直接拒绝覆盖；
   > 只有当本次重渲让共享者**彼此不再相同**时才加 `--break-hardlink`（逐名字 `os.remove` 再写，
   > 并打印每个目标的同 inode 兄弟，清单外的兄弟留在旧 inode = 内容不变）。
   > 实例：赤城·改 `chicheng_alter{,_n}` × 左/中/右 共 8 个文件原本两两共享 2 个 inode，
   > 过滤关闭层后 8 份渲染**全不相同** ⇒ 必须断链，否则 8 张会塌回同一张。
10. **派生产物增量重建**：删受影响 `gallery_v2/thumbs/<stem>.webp` 后跑 `make_thumbs.py`（它对已存在者 skip，天然增量；`<stem>_cg.webp` 来自 CG_v2，别误删）→ `build_gallery_index.py` → `deploy_gallery.py`。
11. **证零回退**（三件套，缺一不可）：
    - **逐字段 diff**：新旧 `index.json` 比 ship 集合/皮肤集合/每字段，期望「只有该变的变」（label 改动那次 = 1746 条 label 变化、非 label 变化 0）。
    - **未涉及文件 mtime 未变**：证明没误伤（脸洞换入那次 = 其余 4454 张 mtime 全未变）。
    - **端到端可达**：起 http.server 对全部受影响 URL（png + webp）GET 200 且长度与磁盘一致；前端渲染类改动再用无头 Chrome 断言（`scripts/diag/l2d_sweep.py` 全量 260 模型加载+动作启动；`l2d_verify.py`/`l2d_click.py` 抽样与真实点击路径）。
    - **改的是"解析优先级"而不只是某个字段时，先把「换档」整体枚举出来再定判据**：新档往往不只影响目标子集，还会**接管**别的兜底档（大小写不敏感回退那次，76 个无源目录之外还接管了 136 个手抄表 `SHIP_NAME_MAP` + 2 个 `manual` 条目）。闸门脚本 `scripts/diag/ship_meta_authority_diff.py`：① 受保护档（本来就走配置桥的 painting/suffix）7 字段改动必须 0，
仅两类可**自动裁判**放行（都必须回查表，不许凭空放行、也不写名字例外）：
`name_via=npc_table:*` 的「皮肤标题→秘书舰实体名」，以及 **方向性判据 `base_fix`**——
该组 stats 选行从「`skin_id` ≠ 组内基皮肤」换成「`skin_id` == 基皮肤」且新行 `name` 等于成品 `cn`
（用来吃掉配置表里的脏行，见 §56；**反向改动仍判红**）；② 条目集合不得增减；③ 换档只允许落在白名单新档；④ 无源数等于期望。另附**第三方裁判**（只打印不判红）：改名条目拿 `Output/WikiData/ship_data.json` 的维基名表投票，看有没有"只有旧值命中"的反例。口径见 `TROUBLESHOOTING.md` §39。

#### 关键决策
- **增量而非全量**：全量重跑 4486 张立绘会打乱已人工确认正确的结果，且无法逐张复核。
- **对比图必须人工过目**：机器指标（不透明率/差异像素）会误判——`leiniya_wjz` 就是指标说"有问题"但目视才确认是回退（见 TROUBLESHOOTING §14）。
- **规则修正优先于例外表**：误判靠收紧判据解决，不写死名单。

#### 踩坑记录
- 跳过第 3 步（依赖表）→ 新皮肤合成缺层，症状像"脚本 bug"，实为数据源过期（385 那次即如此）。
- 判"动画是否在播"不能只看帧哈希：headless 下 rAF 被节流会假阴性，而 physics/眨眼会让帧变化造成**假阳性**；必须读 `motionManager.state.currentGroup` 非空（且 `startMotion` 后要等 ~1.5s 让它 fetch motion3.json）。
- `make_thumbs.py` 遇已存在文件直接 skip → 换入新图后**不删旧 webp 就不会更新**（静默留旧图）。
- 硬链接未检查就覆写 → 孪生文件被一起改掉。
- **"受影响清单的条数"不等于"要换入的条数"**（2026-09-27 §55）：全库扫出 125 张有关闭层，
  但定向重渲后只有 **48 张画面真的会变**，73 张逐字节不变——因为那批纯白遮挡条早就被
  `is_lighting`（近纯白=加算光效层）挡着。**拿 125 去谈换入范围会虚高 2.6 倍**。
  反过来这条也提醒：一个"看起来通用"的启发式过滤器会**掩盖**同一批数据上的另一个真缺陷——
  带黑字 logo 的遮挡条白色占比不足 80%，正好漏过 `is_lighting`，于是正式产物上贴了两条大黄条。
  ⇒ 受影响子集必须走一遍"重渲 + 与在盘比 md5"才算数，只读扫描只用来圈定候选。

#### 收尾必做：全库「产物 vs 当前管线」逐字节普查（2026-09-27 补，§52）

**为什么**：本 WF 的"定位受影响子集"是**预测量**——预测漏了就永久静默。
实证：09-18 换入 85 张、09-19 换入 55 张，两次各自的受影响扫描**分别漏了 2 张和 7 张**，
直到 09-27 用全库逐字节比对才发现（9 张在盘产物仍停留在旧提交的行为上）。

**怎么做**（只读，不动正式产物）：
```bash
py -3 scripts/diag/painting_staleness_scan.py --stamp 20260927        # 4488 张 ≈ 94 分钟，逐条落盘
py -3 scripts/diag/painting_staleness_scan.py --stamp 20260927 --resume   # 中断后续跑
```
判据：`差异清单` 应为空；非空则逐张定性——**先量再盯图**：
按「差异像素里 `max(α_旧,α_新) ≥ 40` 才算可见」+ 可见处最大色差分档，
色差 ≤6/255 的是重采样舍入级（肉眼不可能看见），色差上百的才需要人工过目。
**因果判定**：把历代脚本从 git 取出分别重渲，看在盘文件能被哪个提交逐字节复现，
即可指认"它漏掉了哪一次修复"（`git show <c>:scripts/compose_paintings_v2.py > .diag/oc_<c>.py`）。
⚠️ 分型指标**一片 0 时先怀疑量尺**：第一版四个桶都不收"低 alpha 像素的颜色差异"，把 4 张真差异报成 0.0%。

#### 涉及文件
`scripts/mumu_sync.py`, `scripts/mumu_adb.py`, `scripts/export_dependency_manifest.py`, `scripts/compose_paintings_v2.py`, `scripts/extract_spine_v2.py`, `scripts/reconstruct_live2d.py`, `scripts/extract_motions.py`, `scripts/build_ship_meta.py`, `scripts/build_gallery_index.py`, `scripts/make_thumbs.py`, `scripts/deploy_gallery.py`, `scripts/diag/run_cg_export.py`, `scripts/diag/l2d_sweep.py`, `scripts/diag/l2d_verify.py`, `scripts/diag/l2d_click.py`, `scripts/diag/hit_verify.py`, `scripts/diag/make_face_cmp.py`, `scripts/diag/make_review_sheet.py`, `scripts/diag/scan_faces.py`, `scripts/diag/painting_staleness_scan.py`, `scripts/diag/painting_face_rerun.py`, `scripts/diag/painting_layer_dump.py`, `scripts/diag/painting_inactive_scan.py`, `scripts/diag/painting_inactive_rerun.py`, `scripts/diag/painting_swap_in.py`, `scripts/diag/dedup_*.py`, `PROJECT_STATUS.md §6/§9/§10`

---

### WF-16: Live2D 画廊前端交互改动与回归验证（改哪里 → 怎么验证才算过）

**日期**: 2026-09-23
**目标**: 改动 `gallery_src/index.html` 的 Live2D 交互层（命中判定、动作、检查器 UI）后，用「不循环论证」的方式证明改动真的对。
**适用场景**: 用户反馈「点部位触发错动作 / 动作被切 / 模型发死 / 判定框画错位置」，或要加 Live2D 相关 UI。

**改哪里**:
| 层 | 文件 | 说明 |
|---|---|---|
| 前端源码（唯一权威） | `gallery_src/index.html` | **2026-09-26 起与运行目录是硬链接**（同一份 inode），改正本即刻生效、不需部署；4 个文件（含 `cg_export.html`）已全部换链 |
| 部署 / 漂移检查 | `scripts/deploy_gallery.py` | `--check`=只比对不写盘，**要求 4 个文件全部同 inode**，断链或内容漂移都 `exit 1`（改完前端/提交前必跑）；`--relink`=补链（要求两边逐字节相同，且正本无未提交改动才动手，防打断并行会话）；默认模式=用正本 copy 刷平（断链后回退用，刷平要再 `--relink`）。⚠️ 改正本**必须原地编辑**：整文件写回 / 「临时文件+改名」的原子保存会静默断链。**实测（2026-09-26）：agent 的 Edit 工具就是"写临时文件+改名"，每改一次必断链**（`os.stat().st_nlink` 两边都掉回 1）⇒ 所以真实节奏是「改 → `--check` 必红 → 默认模式刷平 → 提交 → `--relink` → `--check` 绿」，不要指望改完还是绿的 |
| 服务器 | `Output/gallery_v2/_gallery_server.py`（8777，已在跑则复用） | 回归脚本都打 `http://127.0.0.1:8777/gallery_v2/index.html`。⚠️ 它按**自身所在目录**算根（`ROOT=dirname(HERE)`），所以**只能双击 `Output\gallery_v2\` 里那份**；双击 `gallery_src\` 那份会把根算成仓库目录 → 404 + 「当前目录没找到 index.html」 |
| 模型数据 | `Output/Live2D/<key>/` | 前端直读（`P="..\/"`），无副本 |
| 运行时库台账 | `gallery_src/vendor/MANIFEST.json` + `scripts/fetch_gallery_vendor.py` | `vendor/` 4 个第三方 JS 只在 gitignore 目录里，故版本/来源/sha256 全记在台账。**换机器或清过 `Output/` 后跑一次 `fetch_gallery_vendor.py` 即补齐**；`--check` 只校验（缺件/漂移 exit 1），可并进下面的回归清单 |

**六条必须记住的硬规则（每条对应一次真实事故）**:
1. **坐标系必须换算**：`getDrawableVertexPositions()` 是 V（Cubism 原生：画布中心原点、y 向上），`toLocal()/pixelsPerUnit` 是 P（左上原点、y 向下）。换算 `Vx=Px-cux/2`、`Vy=cuy/2-Py`（`cux=im.width/ppu`）。混用 → 点胸口触发头部动作（TROUBLESHOOTING §20）。
2. **命中必须先做包含判定**再就近取框，框外返回 null（否则点空白/任意处都触发最近部位，动作被反复打断，用户感受=「做得快/赶」，§19）。
3. **idle 循环交给运行时，前端不许挂定时器**（2026-09-23 二次修订，旧"看守者"方案已废弃）：`Meta.Loop` 被 vendored 库忽略，但正确修法是给 CubismMotion 本体 `setIsLoop(true)` + `setIsLoopFadeIn(false)`，并把 `mm.groups.idle` 对齐成实际组名（库默认 `'Idle'`），让库自带的"播完自动回 idle"生效。旧方案用 `armIdleLoop` 定时器按 `Duration-120ms` 重开，而 `startMotion` 是 async → `!==false` 恒成立 → **被 `state.reserve` 拒绝时前端无感**，实测造成 idle 播 9.1s 后**冻结 9.2s**。改后 30s 内 `startMotion` 调用 0 次、`currentGroup=null` 采样 0 个（§21）。
4. **验证不能自洽闭环**：合成点击若用被测映射的逆生成，永远全绿。必须用独立锚点（可见语义点反查 / 截图目视）——`l2d_coord_forensics.py` 就是干这个的。
5. **动作数据必须有外部权威基准，别自证清白**：`motion3.json` 的贝塞尔控制点是**绝对 (时间,值)**，运行时直读不做归一化还原；写成归一化分数会让每条贝塞尔都先猛蹿到≈0 再跳目标值，而**曲线集合/时长/参数名全部校验都能通过**（§21）。唯一能抓出它的是同模型的权威导出：`scripts/diag/l2d_ref_diff.py` 拉 l2d.su 的 `motions/<group>.motion3.json` 逐曲线采样比对。
6. **启动序列必须走 `apply()`，不能直接 `renderGrid()`**（2026-09-26，§44）：`view` 的初值是 `ships.slice()`（索引原序），排序只发生在 `apply()` 里，而 `apply()` 只绑在筛选控件的 change/input 事件上。启动直接 `renderGrid()` ⇒ 首屏未排序（VTuber 联动与 `-META` 变体排最前），用户"随便点一个筛选再回来才正常"就是这个。改法一行：结尾 `renderGrid();` → `apply();`。**通用形状**：凡"初始状态是某个函数算出的派生状态"，启动就必须调那个函数，不能既初始化一份原始数据、又指望事件来补。

**回归六件套（按顺序跑；2026-09-27 起第 6 件是台词/开关验收）**:
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
# 6) 台词/字幕与两个全局开关（2026-09-27 加：改过语音条、字幕、语音页或 skin_words/skin_voice 之后必跑）
py -3 scripts/diag/talk_verify.py --shots
```

> **一条命令跑完六件**：`py -3 scripts/diag/wf16_regression.py`
> （长任务用 `py -3 scripts/diag/run_detached.py --log .diag/_wf16.log -- py -3 scripts/diag/wf16_regression.py` 起）。
> 它存在的理由是两件具体的事：① 六件里五件是 CDP 探针、`PORT`/`--user-data-dir` 写死，
> **并发跑会静默附着到同一个浏览器**，症状是数据整齐地偏移一位而不是报错（§6 第 19/20 条），
> 所以必须串行；② 汇总退出码**绝不许写成 `... | tail -25`**——`tail` 吞明细且 `$?` 是它的退出码，
> 本轮之前就是这么把一个 WIRING=2 读成 EXIT=0 的。`--skip hit_verify` 跳过 25 分钟那件，
> `--full-ref` 把第 1 件换成 `--all`（只改前端视觉时不必，动过 motion 数据才要）。
>
> ⚠️ **回归工具自身的两类假失败（2026-09-26 全踩了一遍，各修一处）**——工具红了不代表产品坏了，先证探针再定罪：
> 1. **固定等待**：`l2d_inspector_verify.py` 等 6s、`interact_verify.py` 等 6.5s 就取
>    `l2State.app.stage.children[0]`。大贴图皮肤（`benningdun_2` 三张共 40MB，且服务器单线程）
>    根本来不及 → 报 `Cannot read properties of undefined (reading 'internalModel')`，
>    一度表现为"四个皮肤全挂"。已改成轮询到模型出现（上限 40s），改后 4/4 一次过。
> 2. **异步生效前读状态**：`interact_verify.py` 点部位后只等 900ms 就读 `currentGroup`，
>    而 `startMotion` 是 async → 读到 `idle` 判成"点击没触发"（`lafeiii_3` 偶发）。
>    已按本文档 §硬规则 3 对齐到 1600ms。
> 另：`Execution context was destroyed` 多为**同时有两个 Chrome 在抢 CDP**（比如 detached 的
> `hit_verify.py` 还在跑时再起一个探针）。串行跑，或确保端口/profile 完全隔离。
> 3. **`hit_verify.py` 会把 skip / JS 异常打成"通过"**（2026-09-26 修）：`bad=0` 直接进"全绿"分支，
>    而 skip 或异常返回的对象里根本没有 `nAreas`，于是打印成 `命中自己 0 / 共 None`——
>    那一行看着像通过，实际那个皮肤**一条都没测**。`pinghai_6` 就是这么被吞掉的。
>    → **规则：汇总类判据必须能区分"测了且没问题"和"没测成"，缺字段一律打 FAIL。**
>    顺带：跑 detached 全量时不要再起第二个 CDP 探针——单线程 http.server 会被抢，
>    表现是 `await loadLive2DRuntime()` 永不返回（页面停在"正在加载 Live2D 运行时…"）。
>
> 服务器（8777）掉了要重启：`py -3 scripts/diag/run_detached.py --log .diag/gallery_server.log -- py -3 Output/gallery_v2/_gallery_server.py`
> （它不自动开浏览器，适合无人值守；双击 `启动资产浏览器.bat` 会顺带打开页面）。

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
- **断言要区分「几何上本就该别人赢」与「链路真断」**：`hit_verify.py` 现给四类 `HIT / SHADOWED / WIRING / OUTSIDE`，**只有 WIRING（真实派发 ≠ 产品 `hitAt` 判定）算 bug、才给非零退出码**；`SHADOWED` 是多个 `Touch*` 标记几何重叠的必然结果（产品按最具体优先是设计）。几何判定一律调产品暴露的 `window.__L2_HIT`，**探针不许自己复算一份几何**（复算版实测与真实派发 4/38 条不一致，拿它下结论就是自证）。 同理 `l2d_inspector_verify.py` 的判定区那条：2026-09-24 起断「画出的框 == 产品 `window.__L2_HITUSE()` 可用清单（逐个标签相同）」，不再是「== 登记数」——退化框被 `geomOf` 挡掉后两者本就不等（§27）。**2026-09-27 再分两层**：多边形仍对齐 `__L2_HITUSE()`，但**标签**那条改对齐 `window.__L2_HITSHOW()`（= USE 里此刻与视口相交的那批），见 §51。
- ⚠️ **「判定区在画布外」不等于脏数据，删之前先量一遍"它会不会随动作进画面"**（2026-09-27 §51，我第一轮就是据此提了个错方案）：换装/互动按钮（`TouchIdle*`/`TouchDrag*`）挂在会动的道具上，静止态被停在画布外几千像素处，播对应动作时才随部件进画面。
  判别式：`py -3 scripts/diag/l2d_hit_offcanvas.py <key...>`（① 逐框量 V 坐标/stage 矩形/是否相交视口，并**从 PIXI 场景图直接读标签实际坐标**，标签在视口内而框在外 = 幽灵标签）；
  `py -3 scripts/diag/l2d_hit_offcanvas.py --sweep <key...>`（② 走页面自己的 `play()` 逐组播完**全部**动作组，每组重新量"落回画布内"的标记数，输出移入/移出清单）。
  实测 `qiershazhi_2` 静止态 4/26 在画布内、播 `idle1/main_*/mail/touch_idle2` 时 7~10 个 → 动画驱动，**不许按几何批量删**。
  换装状态的落地形态：各 clip 用**定值曲线**锁住 `TouchSiwa`/`TouchPijian`/`Paramaixin` 这类开关参数（`yuanchou_3` 实测），所以按钮的 `HitAreas[].Name` 就是那条组名，与 A3 随机命中天然兼容、不需要新机制。
- **可视化"点不到的框"先查标签定位有没有被 clamp 拽回屏幕**（§51）：`drawAreas` 旧代码把 x 无条件夹进 `[2, clientWidth-72]`，于是画布外几千像素处的框把**名字**贴到了屏幕右边缘（框本身看不见）→ 用户报"角落里有判定区却点不到"。修法：抽 `toStage/ptsOf/rectOf/inView` 共用，**多边形照画、标签只在框与视口相交时画**；判据是"场景图可见标签数 == `__L2_HITSHOW()` == 相交框数"，且**全部框都在画面内的模型标签数一字不变**（对照组防误杀）。截图目视用 `L2D_AREAS=1 py -3 scripts/diag/l2d_shot_models.py <key>`。
- **三条会静默吃掉结论的工具坑**（§51 本轮各踩一次）：① JS 块注释里写 `TouchIdle*/TouchDrag*` 那个 `*/` 会**提前闭合注释**；② **Edit 类原地编辑也会断硬链**（AGENTS.md 原以为只有整文件写回会断，2026-09-27 已把那句改成"一律以 `--check` 为准"）→ 改完 `gallery_src/` 一律以 `deploy_gallery.py --check` 为准，红了按"默认模式刷平 → 提交 → `--relink` → 再 `--check`"（`--relink` 会跳过正本有未提交改动的文件，故必须先提交）；③ `Execution context was destroyed` 有**两类**成因——两个 Chrome 抢 CDP（§50）之外，还有"探针在页面还在导航时就 evaluate"，后者按 `document.readyState==='complete'` + 重试解决，别去查产品。
- **CDP 脚本每条退出路径都要回收 Chrome**（`try/finally` + 按父 PID 连子进程一起停）：泄漏的无头实例会与下一轮抢 profile，复现出 `Execution context was destroyed` 那类假失败（2026-09-24 亲测踩中，见 §27 末段）。
- ⚠️ **跑 `l2d_ref_diff.py` / `l2d_ab.py` 比对临时重导目录时，必须显式带 `L2D_OUT_DIR=<临时目录>`。** 不给的话
  ref_diff 比的是正式目录（自证清白），`l2d_ab.py` 的"新侧"会读默认的陈旧目录得出"新旧一致"的假结论；
  而 ref_diff 在只含 `motion/` 的临时目录上曾经**全部 SKIP 却退出 0**。三处假绿灯的根因与判据见 `TROUBLESHOOTING.md` §24。

**收尾**: 一轮 CDP 回归结束后 `py -3 scripts/diag/clean_diag_profiles.py --yes` 清 profile（见上），并确认 `.diag` 里没有本次新写的唯一副本代码（按 AGENTS.md 第 4 步移入 `scripts/diag/` 或删除）。
- **共享长文档收尾必做机械核对**：`py -3 scripts/diag/shared_doc_anchor_check.py` —— 逐条断言本轮写进
  `PROJECT_STATUS.md` / `docs/*.md` / `AGENTS.md` / `gallery_src/` 的正话仍在盘上（台账
  `scripts/diag/shared_doc_anchors.json`，本轮落新内容用 `--add` 灌一条）。它专抓两种并发失效：
  `DROPPED`=被别人的整文件写回静默吞掉；`RIDER`=内容还在但字节是别人的提交重新落的（归属对不上）。
  **`git status` 干净与 `git diff` 为空都发现不了这两种**（2026-09-27 实测：查过 status 仍丢一条）。详见技能 `shared-worktree-takeover-commit` 第 3c 步。
- **判活用 `powershell -File scripts\diag\wait_for_detached.ps1 -Pattern <脚本名> -Log .diag\_x.log`**，不要拿 `Start-Process -PassThru` 的 PID 去 `Wait-Process`：那只是 `py.exe` 启动器，且 `Wait-Process` 抛错会被 try/catch 读成"已退出"（2026-09-24 把还在跑的 269 模型回归误判成断了）。该工具按「命令行匹配 python.exe 工作进程 + 日志行数是否还在涨 + 有无汇总行/traceback」给三分法结论；加 `-StallRounds 2` 还能判出「进程活着但日志不涨」的**挂死**。
- **启动长任务用 `py -3 scripts/diag/run_detached.py --log .diag/_x.log -- py -3 <脚本> <参数...>`**，别再用 PowerShell `Start-Process`：含空格路径在「bash → PowerShell → 子进程」三层引号下会被拆断（实测三次）。`DETACHED_PROCESS` 与 `CREATE_NO_WINDOW` 互斥，同时给会 `[WinError 87]`。
- **含中文的 `.ps1` 必须存成 UTF-8 带 BOM**，否则 Windows PowerShell 5.1 按 GBK 解码会把引号错位成 `字符串缺少终止符`（`wait_for_detached.ps1` 首跑就是这么死的，`py -3` 写文件时用 `encoding='utf-8-sig'`）。

**涉及文件**: `gallery_src/index.html`、`scripts/deploy_gallery.py`（默认 copy / `--check` / `--relink`）、`gallery_src/vendor/MANIFEST.json`、`scripts/fetch_gallery_vendor.py`、`scripts/diag/{l2d_coord_forensics,l2d_inspector_verify,interact_verify,hit_verify,page_sanity_check,clean_diag_profiles,l2d_ref_diff,l2d_ab}.py`、`TROUBLESHOOTING.md` §19/§20/§24

**WF-16 追加（2026-09-27）：默认取景与视角记忆——「看起来变小了」这类视觉改动怎么做对照组**

用户反馈两条：① 打开皮肤「缩得有点小」；② 重开不回上次的位置/缩放。落地面是 `gallery_src/index.html` 的三个视图（静态立绘 / Live2D / Spine）。**这类改动没有功能断言可跑**（不报错 ≠ 尺寸对），所以整套做法围绕「把观感变成能红的数」。

- **先把"小"拆成两层再动手**：外层容器尺寸（弹窗 `min(1100px,96vw)×min(880px,96vh)` 在 2560×1600 上只占屏 43%×55%）与内层取景（Live2D 按 Cubism **画布**适配、Spine 按包围盒 +1.1 留白）。两层混在一起谈会各修一半、两边都不够。**量法**：无头截图 → 在绘图区矩形内找"落笔像素"包围盒 → 报绝对像素，而不是报比例（见下条）。
- ⚠️ **判据必须用「内容绝对像素面积」，不能用「占视口比例」**：视口形状本身会被这次改动改掉（宽窗里 Live2D 从**宽受限**变成**高受限**），于是比例会**假报回退**——实测同一批样本按面积比给出 5/10 "比旧版小"，按绝对像素则是 10/10 变大（x1.69~x3.89）。这是"代理指标骗人"的第 N 个实例：**用户看到的是多少像素，不是多少比例**。
- ⚠️ **改 `min(px, vw/vh)` 这类常量时，"数值更大=更宽松"是错的**：把 `96vh` 写成 `94vh` 想让上限更松，结果在 `innerHeight < ~917` 的窗口里 `94vh` 反而**小于**原来的 880px 硬上限，弹窗变矮、高度受限的 Live2D/Spine 直接回退。⇒ 视口百分比与像素上限的**交叉点两侧都要各测一次**（本轮用 `--win 1600,1000` 与 `--win 2560,1600` 两档，前者当场抓出这条自伤）。
- **A/B 对照页用 `git show HEAD:gallery_src/index.html > Output/gallery_v2/index_old.html`**：同一台服务器、同一份数据、同一次运行里跑新旧两页 ⇒ 排掉了模型加载时序与机器状态这两个混淆源；跑完删掉临时页（它在 gitignore 的 `Output/` 里，不会污染仓库）。工具 `py -3 -u scripts/diag/gallery_framing_ab.py --pages both --n 5 --win 2560,1600`。
- ⚠️ **无头量"落笔"前必须把 `.view` 的棋盘格底色刷成纯黑**：`#12172a` 的 max 通道 = 42，任何合理阈值都挡不住它，实测 `wf/hf` 恒为 0.999（整屏都算内容）。同时**基准框要按视图取**（Live2D 用 `#l2wrap` 它本身已让开底部控制条；Spine 的 canvas 得再减掉底部 48px，否则条上的浅色字会被算成内容、把高度顶满）。
- **断言必须能红**（两条空断言各加一条前置守卫）：① 记忆类断言先确认"操作确实改变了取景"（`|moved−fresh| > 0.03`），否则 `back==moved==fresh` 是永真式；② resize 类断言先确认 `Emulation.setDeviceMetricsOverride` 真的生效（基准宽 1233→874→1233），否则"偏移 0.000"只是没测到东西。
- **Live2D 按内容取景的实现约束**：不能用渲染包围盒（`mdl.width`，会被巨型离屏 quad 撑到几百万像素，§20 那条老坑），也不能直接并集 drawable 顶点框（停放件会把框甩出画布）。落地形态 = **各 drawable 顶点框 ∩ 画布 的并集**，另加两条护栏（单边 >画布 4 倍丢弃；与画布完全不相交丢弃；有效 drawable <3 个则整体退回画布 fit）。方向上这是**单调放大**（内容框 ⊆ 画布 ⇒ 只会比原来大），所以"零回退"是可证明的而不是抽样的。
- **视角记忆只存尺度无关量**，否则换窗口尺寸/进出全屏就错位：图片存 `s` + 偏移÷视口宽高；Live2D 存 `z` + 偏移÷`baseK`（= 模型本地像素）；Spine 的 `camX/camY` 是世界坐标、`zoom` 无量纲，原样存。皮肤有 1000+ 个 ⇒ LRU 截断 300 条防顶穿 localStorage 配额；写盘走 350ms 合并 + 切视图/关弹层时强制 flush（否则最后一次滚轮丢失）。
- **顺带修掉一条老失效**：Live2D 的 `ResizeObserver` 原来直接挂 `fit()`，而 `fit()` 会把 `z/ox/oy` 清零 ⇒ **进一次全屏再退出，用户调好的缩放就没了**。改成 `refit(preserve)`：只按新视口重算基准缩放、偏移随 `baseK` 同比换算。
- 交互层零回退靠现成三件套：`interact_verify`（裸滚轮不劫持 / Ctrl+滚轮才缩放 / 点部位触发）ALL PASS、`l2d_inspector_verify`（判定区 + 参数·部件面板 + 过滤）全绿、`hit_verify` 四类判定。**注意 `py -u … | tail -25` 会让 `tail` 把中间输出全吞掉**（`tail` 只在 EOF 才吐），要轮询进度就别在管道里接 `tail`。

**涉及文件（追加）**: `gallery_src/index.html`（`.modal` 尺寸 / `contentBox()` / `refit()` / `vmemCommitter()` / 弹层快捷键）、`scripts/diag/gallery_framing_ab.py`（A/B 取景与视角记忆回归）、`TROUBLESHOOTING.md` §59

---

### WF-16 追加（2026-09-28）：动效 / 观感类改动怎么验（`gallery_motion_probe.py`）

**目标**: 「加了动画」和「动画真的接在用户那一下操作上、且系统关掉动效时能退化」是两件事，后者要能红。
**适用场景**: 改 `gallery_src/index.html` 的 hover / 入场 / 弹层开合 / 主题切换 / 选中态胶囊一类。

```bash
py -3 scripts/diag/gallery_motion_probe.py --page index_q.html --baseline index.html --win 1440,900
```

**十六条判据（脚本里逐条实现，全部走真实入口：点卡片 / 点标签 / 点开关，不直接调内部函数）**
1. 环境自证：`visibilityState==='visible'` + `document.startViewTransition` 存在，否则整轮不可信；
2. 倾斜：`--rx/--ry` 幅度 >1°、**换到卡面另一半后符号必须翻**（不翻就是角度没跟随鼠标）、`transform` 含 `matrix3d`；
3. 倾斜成本：120 次 mousemove 的 ms/次，>4ms 判太贵；同时断言末卡角度非零（防止"计时测了个空转"）；
4. 淡入：判据是「**已 `complete` 却没亮**」= 0，不是「还没到货」= 0（懒加载的图本来就该透明）；
5. 会滚的选中胶囊：`--x/--y/--w/--h` 与选中标签的 `offset*` 偏差 ≤1.5px，**切标签位移 >20px**（位移不到 20px 说明这条断言是空的），且选中那颗自身 `background-image==='none'`（否则和胶囊叠成两层）；
6. 飞入：点卡片后 `.modal` 立刻带 `fly` 类、`--fx/--fy` 位移非零、`--fs` 在 (0,0.6)；动画结束后 `fly` 必须摘掉且 `transform==='none'`（不摘会盖住下一次关闭动画）；
7. 缩回：点关闭后同时出现 `flyout` + `closing`，1s 后弹层真关上且 `flyout` 已清；
8. 主题：`--cx/--cy` 落在被点开关的几何中心（±1%），**切换后 1.3s** 才读 `data-theme`/localStorage（见 §61 第 3 条）；
9. 反向证据：`Emulation.setEmulatedMedia` 打开 `prefers-reduced-motion: reduce` 后——不再有 `fly` 类、缩略图 `opacity` 必须已经是 1（淡入靠 load 事件，关动画后不许依赖它）、弹层仍能关上；
10. 报错：与 `--baseline` 页取**差集**，只有样板多出来的才判失败。
11. 背景"是不是着色器那一档"：`BG.mode==='gl'` 且 `BG.err===''`（WebGL2 + 编译链接都过）、
    uniform 位置取满（19 个）、CSS 兜底辉光在着色器起来后必须 `display:none`（两层会叠）、
    渲染缩放 `rs∈(0.4,1)`（成本主要靠它）；
12. **画面里真有东西且在变**：同一块区域连读两帧算逐通道 MAD（>1）与标准差（>3）——
    均值高不等于有内容，纯色一片也是高均值。⚠️ `draw` 与 `readPixels` 必须在**同一次 evaluate** 里
    （`preserveDrawingBuffer:false` 下跨调用读到的是空缓冲）；
13. 交互是真的：**固定采样区、只换鼠标位置**，采样区亮度必须变（**≥6 个亮度单位**，门槛按人眼可见校准，不是非零即过），且同位置两次读数必须一致
    （<0.8）——换位置又换采样区就分不清是鼠标变的还是漂移；
14. 时钟判据对**帧时间线**而不是墙钟（`clock>0` 且 `clock <= tlast-ts0`）；成本判据降级为
    "只抓病态"（无头量不出真机 GPU 成本，见 §61 第 10 条），别拿软件光栅的几十 ms 当帧预算超标。
    另有两条通用判据：`reduce` 之后 `BG.raf` 必须归 0（自续循环的 kill switch 在函数内部），
    弹层开着时帧数不推进。
15. 「像海」的结构判据（不是口味，是可量）：**横向特征必须比竖向宽** —— 同一帧内比较
    相邻列差与相邻行差，各向异性 `纵向/横向 ≥1.25`（着色器里靠 `p.x*=0.62 / p.y*=1.35` 做到）；
    **上浅下深** —— `readPixels` 顶段亮度减底段 ≥6（注意 y=0 是画面底部，别把方向搞反）；
16. 判"有没有内容"看**标准差**不看均值；亮度还要给**区间**（白天中心均值须落在 120~240，过曝/过暗都红）：纯白与纯黑都是均值极值、方差 0。
    本轮白天底色三段接近白 + 三束加性光 ⇒ 整屏削顶到 255，`sd>3` 这条把它抓住了（§61 第四补）。

**出图**（只给我自己肉眼判，不作判据）：`fly_mid_0.12.png` / `fly_mid_0.3.png`（定格飞入中间帧）、
`tab_slide.png`、`theme_wipe.png`、`theme_dark.png`。**定格要放在最后一步**——它会 `pause()/cancel()`
动画并手动摘类，属于篡改状态，早跑会污染后面的断言；而且它必须先撤掉第 9 条的 reduce 模拟，
否则 `flyGeom` 走退化分支，根本不会有 `flyin` 动画可定格。

**踩坑记录**: 见 §61（四条假红灯：隐藏标签页不出帧、rect 被动画缩放、VT 回调异步、vendor 本来就报错）。

**涉及文件**: `scripts/diag/gallery_motion_probe.py`（新）、`scripts/diag/gallery_ui_shots.py`
（复用它的 `Page`/`BASE`/`preflight`）、`gallery_src/index.html`。
相关：`WF-16` 六件套（动效过了之后仍要跑那六件）、`WF-15` 换入闸门。

### WF-16 追加（2026-09-29）：视觉语言改版怎么验，样板页怎么刷进正本

**目标**: 上一节第 11~16 条是围着"WebGL2 噪声着色器背景"写的，那一版已被推翻；
本节给新口径（水面 + 玻璃拟态 + 丝滑交互），并把"样板页 → 正本"这条换入路径写成硬流程。
**适用场景**: 改背景层 / 卡片与导航栏材质 / 控件选中态与悬停按压反馈。

```bash
py -3 scripts/diag/gallery_motion_probe.py --page index.html --win 1440,900   # 24 条，退出码即结论
```

**新口径的判据分组**（旧的 11~16 条作废：背景不再是着色器，也就没有 readPixels / 各向异性那套）

| 组 | 判什么 | 关键一条 |
|---|---|---|
| 1 悬停三件套 | 描边提亮、上浮、缩略图放大、**离手必须退回** | 阴影层数只许**持平或变多**——变少就是悬停把玻璃厚度吞了 |
| 1 倾斜 | 满偏够大、对角翻符号、离手归零 | 按**满偏**判（指针推到角上、取两角 max），别拿随手取样点当上限 |
| 1 玻璃纯度 | 面板 alpha ≤0.10、文字区底 ≤0.32、边墙 blur 必须比面板强、反光只许常驻斜条 | 出现 `radial-gradient` 或卡上有 `--mx/--my` = "跟着鼠标发光"回退 |
| 1 发光反向 | 非 `inset` 的 shadow 层里**不许出现第 4 个长度值（spread）** | 这就是"不要发光"的可执行形式 |
| 1 成本护栏 | `backdrop-filter` 只许挂在**进过视口**的卡上 | 视口外取样 40 张里挂模糊的必须是 0 张 |
| 5b 静止 | 隔 1.3s 两帧比对区**逐像素相同** + 能量归零时 `rAF` 不再排队 | "装饰性动效不许自己动"这条审美要求的量化形式 |
| 5c 起浪 | 真实拖动后峰值 >0.004、帧推进、空带新增近白像素 ≥200、**事后回到同一个静止态** | 泡沫=白沫，不是色带；只数白点会拿底色当泡沫，必须与静止帧做差 |
| 11 丝滑 | 全表 `cubic-bezier` 的 y **不许 >1**；按下横纵比例必须**相等** | 有回弹/有形变=果冻，只有亮度变化=iOS |
| 11 导航栏 | 模糊 >10px 或底色 alpha >0.30 即红；必须有亮截面 + 厚边墙 + 斜反光 | "一眼毛玻璃"的配方特征就这两条 |
| 12 材质态 | 选中项 `background-image` 不许含 gradient、底色 alpha ≤0.30、控件上不许出现第二个强调色、**选中文字不许是近白色** | 最后一条防"材质压浅之后白字看不见" |
| 13 层叠 | 展开面板后取一个**低于 header 底边**的点做 `elementFromPoint`，命中必须在面板内 | 比 z-index 数值测不出层叠上下文被切碎 |

**样板页 → 正本 的换入流程**（本轮走通，顺序是硬性的）

1. **先证无损**：比对两页的 `id` / `function` / `class` / 选择器 / `window.*` / 资源路径**集合**，
   要求样板页是正本的功能超集。⚠️ 选择器一项必有假阳性（分组选择器 `.a,.b{}` 匹不到 `.a`），
   报缺必须逐条回查——本轮两条"缺失"一条是分组写法、一条是正本里的**死规则**（全文无人生成该 class）。
2. 记下换入前的 `HEAD`（回滚锚点），然后 `cp 样板页 gallery_src/index.html`。
   ⚠️ 用 `cp`（就地截断写入）而**不是**任何"写临时文件 + 改名"的编辑器保存：前者保住硬链，
   后者当场断链（AGENTS.md 收尾清单第 1 条）。本轮 `cp` 之后 `--check` 仍是 4/4 同 inode。
3. `py -3 scripts/deploy_gallery.py` → 再 `--check`。
4. **探针打正本**跑一遍（`--page index.html`），全绿才继续。
5. 提交（中文 message，带 `技能:` 行）→ `--relink` → `--check` 收尾。
   ⚠️ `--relink` 会跳过"正本有未提交改动"的文件，所以提交必须在它前面。
6. WF-16 六件套全量回归（`hit_verify` 全库约 25 分钟，**必须走脱离宿主进程**）。

**踩坑记录**: 见 §62（3 条真缺陷：纹理削顶吃掉泡沫 / 指针瞬移被当成快速划动 / 阻尼按帧算导致低帧率永不平；
5 条假红灯：合成事件不点亮伪类、`mouseDown` 被静默忽略、过渡第 0 帧、整图哈希被懒加载与持久高光污染、
把取样点偏小当成设计幅度小）。

**涉及文件**: `scripts/diag/gallery_motion_probe.py`（判据 16→24）、`scripts/diag/gallery_ui_shots.py`
（`EXC` 现在带 `text/description`）、`gallery_src/index.html`、
技能 `headless-chrome-cdp-batch-export` §「视觉/交互态专用」。
相关：`WF-16` 六件套（本节过了仍要跑那六件）、`WF-15` 换入闸门。

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

### WF-17 追加（2026-09-26）：语音的生命周期属于"句子"，不能挂在"动作"上

- **规则**：**不要**把语音注入 `model3` 的 `definitions[g][0].Sound`。那条通道由库的 SoundManager 托管，
  语义是"下一条动作 startMotion 时 dispose 上一条"，而 idle 播完会由运行时自动回落 idle
  → 于是**动作结束 = 语音结束**。只要 `语音时长 > 动作时长` 就必然拦腰掐断。
  碧蓝实测这是常态：`benningdun_2` 有 6 组超标（`touch_head` 动作 5.17s / 语音 9.24s 等）。
- **正确接法**：页面自己持有一个 `Audio` 元素（`gallery_src/index.html` 的 `playVoice()/stopVoice()`）。
  打断点只有两处，且都是**用户主动**的：① 再次 `play()`（下拉 / 重播 / 点部位）；
  ② `my.off()`（切标签 / 换皮肤 / 销毁模型）。运行时回落 idle 不经过 `play()`，因此不打断——**这就是解耦点**。
  非用户手势下 `el.play()` 会被浏览器拒（部分皮肤 `idleGroup` 落在带语音的 `home`），`.catch()` 静默降级。
- **判据（必须实测音频元素，不能只听）**：`py -3 scripts/diag/l2d_voice_lifecycle.py <皮肤key> <动作组> <采样秒>`——
  用 `Page.addScriptToEvaluateOnNewDocument` 在页面脚本执行前包住 `window.Audio`，
  录 `play/pause/ended/loadeddata` + 每次事件的 `currentTime`；
  判据 = **`currentGroup` 翻回 `idle` 之后音频仍 `paused:false` 且 `currentTime` 继续推进到 ≈ `duration`**。
  ⚠️ 事后在 console 里找"当前有哪些 Audio"是找不到的：库 new 完就藏进闭包，自建元素也不入 DOM，
  `document.querySelectorAll('audio')` 恒为 0 —— 会误判成"根本没播"（本轮就这么绕了一圈）。
- **踩坑（先排除岔路再改代码）**：症状像"动作导短了"，但 `Meta.Duration` == 曲线最大时间 == 源 clip 末帧，
  动作时长是忠实的。**不查这一步就会去改数据层，把正确产物改坏。**
- 详见 `TROUBLESHOOTING.md` §41。

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

---

### WF-21: 皮肤级语音接线——按「船级语音包」去重导出，取词按皮肤序号，验收要量"真的出声"

**适用**：把 CRIWARE 语音包接成"点任意一种立绘都能出声"，或给已有语音层换权威数据源。
核心是三条：**去重单位选对、取词键选对、判据落在出声那一刻**。

**步骤**

1. **先量覆盖面，再动手**。四个独立数字必须分开测，混成一个"有语音 253"会盖掉三层问题：
   ① 前端有点击出声代码的**视图格数**；② 该格覆盖多少皮肤 / 全库多少皮肤；
   ③ 磁盘实有语音包数 vs 索引里 `voiceCount>0` 的组数（差值 = 归并链在漏）；④ 每包平均 cue 数（= 未导出的量）。
2. **解析皮肤 → (语音包号, 皮肤序号)**，来源优先级写死成可枚举的三档并在产物里留 `src` 字段：
   权威行（`painting` 精确匹配，cv=id//10、idx=id%10）→ 剥画法变体（只剥 `_hx`/`_n` 这类"同一张图的另一幅画法"）
   → 同船兄弟回退（包号可用，**序号必须另推**）。缺行的序号按"包内实存序号档 − 同船已占用档"分配，
   分不到就退回基础档并标 `sibling-base`；**不许**用目录名 `_N` 硬算（实测 78% 正确 = 22% 串皮肤）。
3. **去重单位 = 语音包，不是皮肤**。产物 `Audio/CV2/cv-<n>/<cue>.ogg` 一份，皮肤表里只写引用。
   按皮肤去重会让 `_hx`/`_n` 变体各存一份（旧 L2D 导出就是这么把 25 条存成 50 条）。
4. **cue 名切分按「最长已知类别前缀」**，类别 / 动作名 / 中文标签全部取游戏自己的 `character_voice` 表
   （`resource_key` = cue 基名，`l2d_action` = Live2D 动作组名，`spine_action` 供 Spine 侧用）。
   表未覆盖的类别名单独补标签，**切不出类别的名字要打印出来**（本轮 5 包 0 未识别，才是真过）。
5. **取词逐类别独立回退**：`类别_序号` 存在用它，否则用 `类别`。同一皮肤常常是混合档（改造皮肤 `main_1_9` 有、`detail_9` 无），
   整档二选一会丢台词。活动台词（`_exNNNN`）导出并列出但**不进点击/动作触发**；`vocal_*` 是歌，不导。
6. **规模与跑法**：单包耗时实测（jobs=4 约 1.9s/包），据此报总时与磁盘量；>8 分钟一律脱离宿主进程 + 进度行轮询，
   完成用三分法判定（真跑完 / 崩了 / 被截断），不得拿 `exit 0` 当完成证据。
7. **判据落在"出声那一刻"**：产物表和结构都不等于响。验收 = 真实用户手势（CDP 点击按钮，不是 JS `.click()`）
   触发后，读页面自持的 `Audio` 元素 `paused=false` 且 `currentTime` 递增，并核对 `currentSrc` 尾部是**本皮肤序号档**的文件名。
   JS 里 `dispatchEvent`/`.click()` 无用户激活，`play()` 会被策略拒 —— 那类失败长得和数据缺陷一模一样。
8. **零回退闸门**：换权威源后，旧表每一条 `(皮肤,动作组)` 必须仍在新表里（丢组必须为 0），
   并抽样打印"旧=多条混抽 / 新=本皮肤一条"的逐组对照，让改动方向肉眼可见。
   - 新旧表形不同也要能用同一个闸门：`l2d_voice_diff_check.py` 已兼容 v2 的
     `{皮肤:{cv,idx,src,l2d,tap,lines}}`（比对取 `l2d` 子表，音频清单把 `tap`+`lines` 一起算存在性/占位）。
   - **"丢组"要按规则裁定，不要按名字放行**：cue 尾部 `_N` 是皮肤序号 ⇒ 旧表里存在
     "本皮肤拿到别的皮肤序号台词"的条目，新表删掉它是**修正**。判据 = 旧文件名尾部 `_N` 存在且 ≠ 本皮肤 `idx`
     （2026-09-27 这样查掉 4 条，全是 `touch_head`，逐条回看包内文件确认序号各归其主）。
9. **出声验收必须走真实 UI 路径 + 包住 `window.Audio`**：`scripts/diag/voice_v2_verify.py`
   （CDP `Page.addScriptToEvaluateOnNewDocument` 在页面脚本执行前包 Audio，录 src/play/pause/ended/error）。
   断言三件：新实例的 `paused=false` 且 `currentTime>0.1`、`error=null`、**src 尾部文件名属于本皮肤序号档**。
   ⚠️ 探针取页面状态的两个假绿灯坑（本轮真踩）：`let SV` **不挂 window**（`window.SV` 恒 undefined），
   且表是 `mountSkinVoice` 里异步拉的 ⇒ 不 `await loadVoiceMap()` 就"谁都无语音"，
   于是三个视图一个都没测到、只有"无语音"那条空洞通过，**输出却一片 ✅**。
   通用形状：探针取不到被测状态时必须硬失败，不能让"没测到"长得像"测过了"。

**踩坑**

- 语义错最伤信任且不报错：把"皮肤序号后缀"当"随机变体"再 `Math.random()`，三皮肤船 2/3 概率播错人的台词，
  而所有结构校验、文件计数、播放器都全绿。详见 §47。
- 48/66 两个数不是笔误：报"缺多少包"必须同时给两个口径——**包号级**（皮肤表要引用而磁盘没有的包）与
  **皮肤级**（连同船兄弟皮肤也推不出包号、因此真的拿不到语音的皮肤数）。只报前者会低估，只报后者会以为"解析 bug"。
- 想证明"包是**没下载**而不是解析不出"：拿 `files/hashes-cv.csv` 与磁盘做 1:1 比对（清单里有的全在盘上 ⇒ 缺失项根本不在清单里 = 没取过）。
  **但"再去设备侧补取"这条已否证，别再排进计划**：2026-09-27 只读核对，设备 `cue` 4958 vs 本地 4726，
  设备独有 232 个只属于 `cv-970113` 一个号，与那 66 个缺号**交集为 0**（59 个连前缀文件都没有）。
  复核命令：`py -3 scripts/mumu_sync.py diff`（只读），逐号比对用
  `adb -s <host> shell "ls <REMOTE>/AssetBundles/cue | grep '^cv-<n>'"`。详见 §49。
- 换数据文件 = 半程部署风险。前端只读新表时，若新表只覆盖了样本，出声面会**倒退**（253→2）。
  安全暂停配方：`git diff -- <前端正本> > scripts/diag/<名>.patch` →（`git apply --check` 验可回放）→ `git checkout -- <正本>`
  → `deploy_gallery.py`（刷平运行目录）→ `--relink`（补硬链）→ `--check` 要求 4/4 同 inode。
- 终端打印的中文乱码不是数据坏：判"字段坏了"之前先打 codepoint（`[hex(ord(c))]`）或看原始字节的 UTF-8 序列。
- **报"某批数据查不到"之前，先怀疑查表姿势而不是数据缺失**：`azdata` 皮肤表里 `painting` 有 `2B`/`A2`/`HDN101`
  这种大写，而磁盘目录名一律小写 ⇒ 按原样建键 + 按原样查 = 145 张明明有语音包的皮肤被判"无解"。
  表键与候选**都小写归一**。发现"无解"数量异常时按可观测口径拆开算一遍（包在不在盘上 / `voice_actor` 是不是 0 /
  表里到底有没有这一行），别笼统写成"快照滞后"——本次"265 张因快照滞后无解"整条是误判，见 §53。
- **后缀剥离要分两类，身份后缀绝不盲剥**：`_n/_hx/_rw/_bj/_jz/_alter/_hei` 是同一皮肤的画法变体（剥了不影响归属），
  而 `_memory`（回忆剧情）/`_rank`（排行榜立绘）/`_heihua`（黑化）/`_ex`/`_wjz`/`_g`/`_meta` 可能是
  **另一个发声实体或另一张独立皮肤**。剥错的后果是把别人的台词派给它——按 §47 的定性属"不报错的语义错"，
  比"没声音"更糟。宁可留空待裁定。
- 只改定位逻辑、不改音频时，用 `--skip-done` 复用磁盘上已解过的 `cv-<n>/<cue>.ogg`（文件名即 cue 名），
  把"重建映射"从 75 分钟降到几分钟；**用完仍必须过"磁盘缺失 / <2KB 占位 = 0"闸门**，否则半截包会被当成完整包。
- 验证 Live2D 那一格要用**换数据文件之后**的表：Live2D 侧唯一风险是动作组键对不上（`l2d_action` 恰好等于组名，
  旧表靠这个成立），不重跑一次就是没验。

**涉及文件**：`scripts/extract_cv_voice.py`（`--probe` 只解码选词 / `--sample` 临时目录落盘 / `--all [--jobs N]`），
产物 `Output/Audio/CV2/cv-<n>/<cue>.ogg` + `Output/gallery_v2/skin_voice.json`；
`scripts/diag/voice-v2-frontend.patch`（三格接线的挂起补丁，**2026-09-27 已 `git apply` 落地**）；
`scripts/diag/voice_v2_verify.py`（三格实播验收：真实 UI 路径 + CDP 包 `window.Audio`）；
`scripts/diag/l2d_voice_diff_check.py`（零回退闸门，兼容 v1/v2 两种表形 + 按皮肤序号裁定"丢组"）；
`inputs/gamecfg/character_voice.json`、`inputs/azdata/azdata_ship_skin_template.json`、`files/hashes-cv.csv`（判断"包没下载"而非"解析不出"的对照）。
相关：`WF-17`（Live2D 动作语音旧管线，被本 WF 的取词规则取代）、`WF-15`/`WF-16`（换入闸门与回归六件套）、`WF-19`（判据优先挑两边可独立算的量）、技能 `live2d-web-runtime-integration` / `spine-web-runtime-integration`。

---

### WF-22: 把「台词正文」接进画廊——皮肤行 id 当钥匙、别名查表不猜、验收量"逐字 + 可播 + 反向证据"

**目标**: 语音只有声音、没有中文台词时，把 `ship_skin_words` 的正文接到画廊三格与语音页上，
并让「点击出声 / 显示台词」成为两个互相独立的全局开关。
**适用场景**: 新增一类"文本 ↔ 已导出音频"的配对；或要给画廊加全局交互开关。

**数据链（每一步都可单独重跑，谁也不挡谁）**：
```
files/AssetBundles/sharecfgdata/ship_skin_words
  → tools/sharecfg_re/37_parse_sharecfgdata.py --scalar-all   （容器文法，§33/§36）
  → .diag/sharecfg_re/cfg_json/ship_skin_words.json
  → tools/sharecfg_re/42_publish_gamecfg.py                   （清洗成标量表 + sha256 台账）
  → inputs/gamecfg/ship_skin_words.json                       ← 正文唯一副本，**不许再放回 .diag/**
  → tools/sharecfg_re/46_publish_name_code.py                 （{namecode:NN} 的展开表 + 台账，§60）
  → inputs/gamecfg/name_code.json
  → scripts/build_skin_words.py                               （两趟：① 按 cv*10+idx join 语音表 ② 有表行无音频的皮肤按字段出词；就地展开占位符）
  → Output/gallery_v2/skin_words.json  {m:皮肤→行id, w:行id→{运行时名:正文}, L:运行时名→中文类别名}
  → scripts/build_gallery_index.py                            （voiceCount 换权威源 + voiceText）
  → gallery_src/index.html                                    （字幕条 + 语音页 + 仅台词档 + 两个开关）
```
⚠️ **建索引前必须先有 `skin_words.json`**：`build_gallery_index.py` 缺这份会直接 `SystemExit`
（要跳过用 `GALLERY_ALLOW_NO_WORDS=1` 显式放行）——静默当 0 就是 §60 那种"结构合法但内容缺"。

**三条可复用的做法**：
1. **钥匙要用"上游已经算好的字段"，不要新造匹配**。`skin_voice.json` 里每条皮肤带 `cv`(语音包号) 与
   `idx`(皮肤序号)，`cv*10+idx` 正好是台词表主键 ⇒ 音频与正文取自**同一行**，同皮肤同档位是结构性保证，
   不需要第二套对齐逻辑（也就不存在两套逻辑各自漂移的风险）。
2. **类别名之间的映射一律查游戏自己的表**：`character_voice` 的 `key`(正文字段) ↔ `resource_key`(cue 类别)
   ↔ `l2d_action`(动作组/触摸槽) 三条链覆盖 93 个运行时名，且**先断言"一个运行时名不对多个字段"**
   （实测 0 冲突）。表没覆盖的才回退同名直取。
3. **产物拆两份、别改已验收的那份**：`skin_voice.json` 是 75 分钟全量导出的已验收产物（零回退闸门以它为基准），
   正文单独落 `skin_words.json`，前端两次 fetch、各自可重生。

**判据（`py -3 scripts/diag/talk_verify.py --shots`，退出码即结论）**：
- 三格各点一次 + **直接点立绘**（用户说的"点击有声音"是这条，不是点按钮）；
- 字幕**逐字**等于表里该槽位正文，且"谁在说"那行必须是**中文类别名**（不是 `complete`/`touch_body` 这种内部键）；
- 开关矩阵要拿到**反向证据**：关显示台词 ⇒ 仍出声且字幕为空；关点击出声 ⇒ 新 Audio 数=0 且仍上字幕；
- **阴性对照**：挑"有音频但游戏本来没写词"的槽位（部分船的摸头），必须出声且**不弹空字幕**；
- 语音页逐行比对行数 / 正文数 / **每行 `<audio>` 的可见高度**（只数行会放过"播放器被压成 0 高"）；
- **内容形状断言**：页面上不许出现 `{namecode:NN}`（`residue`）——结构判据全绿也可能把运行时占位符端给用户（§60）；
- 「有表行、主包未下发」那一档：语音标签必须放行、台词行必须逐字对齐，且
  **audio 元素数 == 变体包条数**（台词行一律不带播放器；造个点了不响的假控件比不给更糟，§60）；
- 无语音皮肤必须显式 🔇，不许静默空白；
- 持久化用**非常规组合**（on/off）验证，全 on 时"读默认值"也能过。

**踩坑记录**：见 §54（闸门把白名单字段剔出比较 = 假绿灯；`flex:1` 压扁 audio；
探针依赖上一轮 localStorage；阴性对照没点到那个槽位；CRLF 让台账校验长期报假红灯）。

**缺口审计**：「🔇 无语音」的 354 张到底缺什么，用 `scripts/diag/voice_gap_audit.py` 按**可救性**分类，
别拿一个总数当结论——196 缺包（本地+设备两侧都无）/ 36 只有变体包（**正文齐全却没进前端**）/
55 剥后缀才命中（**不能做**：游戏把画法单独立行的那 29 行既无包也无词）/ 54 表里查无此名（NPC 皮肤）/
13 该船无 CV。工具必须复用 `extract_cv_voice.resolve()`，判据不许另写一份；否证细节见 §57。

**涉及文件**：`scripts/build_skin_words.py`、`scripts/diag/gallery_index_diff_check.py`（索引零回退闸门）、
`scripts/diag/talk_verify.py`、`scripts/build_gallery_index.py`、`gallery_src/index.html`、
`tools/sharecfg_re/42_publish_gamecfg.py`、`inputs/gamecfg/{ship_skin_words,character_voice}.json`。
相关：`WF-21`（语音 v2 导出）、`WF-16`（回归六件套，第 6 件就是本 WF 的 `talk_verify`）、`WF-15`（换入闸门）、§47/§49/§53/§54。
