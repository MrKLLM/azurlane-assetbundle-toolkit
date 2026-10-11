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

#### WF-14 追加（2026-09-29）：分层这类事实必须落盘成**一份**权威清单，读写都只认它

**适用**：任何"前端/索引靠命名规则或目录 glob 猜游戏侧结构"的场景（本轮是 Spine 分层，
§9.3 那七条根因全是同一类）。

**步骤**（顺序不能换，每一步都自带判据）：

1. **只读审计先跑，拿到"权威 vs 现状"的差集**。`scripts/diag/spine_parts_prefab_diff.py`
   → 多画 30 / 少画 0 / 层文件缺失 0。**少画为 0 是关键**：它证明 glob 是纯过包含，
   修法可以是"过滤"而不是"补"，于是不可能丢内容。
2. **把权威清单落盘到资产自己旁边**，而不是让每个消费方各自去解析 26GB 源包：
   `py -3 scripts/extract_spine_v2.py --parts-only` → 每个 `Output/Spine_v2/<目录>/parts.json`。
   `--parts-only` 这个模式是必要的：不补它就等于为了写一个小 json 去重解码 234 个目录的贴图。
3. **解析函数只允许有一份**。抽到 `compose_paintings_v2.skel_layers()`，
   审计工具与导出脚本都调它 —— 否则"谁写"和"谁读"会各自漂移，而这正是本类 bug 的成因。
4. **消费方改读清单，缺文件必须非零退出，不许回落旧逻辑**。回落 glob = 把 bug 留着且没人看得见。
   `build_gallery_index.py` 攒够一批再统一 `sys.exit(1)`，这样一次能看全缺哪些。
5. **重导之前先查 `st_nlink`**：这批产物如果历史上被硬链去重过，必须先断链再重导，
   否则两个名字共享同一个 inode，写完最后一个赢，成对判据永远不过（本轮真实撞上，见 §64）。
6. **验收三件套，缺一不可**：
   - 机器判据：审计工具重跑必须 `多画 0 / 少画 0`；
   - 零回退：`gallery_index_diff_check.py` 白名单外零差异 + **按 mtime** 证明只有目标文件被写
     （"我只传了这些名字"是说法，mtime 是凭据）；
   - **逐张看改前|改后总表**：`scripts/diag/make_pair_sheet.py`。本轮 34 张里 3 张差异 50~98%
     且都是"旧图塌成一条/裁成小块"，不看图根本不知道修复顺带救回了什么。
7. **前端那条分支要单独验**。`interact_verify` 走 Live2D，**不碰 `startSpine`**——
   拿它全绿当"Spine 改对了"就是代理指标冒充观测。新增 `scripts/diag/spine_parts_wiring.py`：
   只点真实 DOM、只读页面上本来就有的显示（`.spine-bar` 那句 "N 层部件" + `#spAnim` 的 value），
   期望值现从 `parts.json` 算，不写死在探针里。

**判据**：`spine_parts_wiring.py` 退出码 0 且 6/6 案例过；`spine_parts_prefab_diff.py` 报 `多画 0 少画 0`。

**踩坑**：
- ⚠️ 探针第一次求值跑在页面脚本加载完之前 ⇒ `openShip is not defined` 被读成产品缺陷。
  **必须先轮询 `typeof openShip==='function'` 再开测。**
- ⚠️ 报错文案要说准：`fulangxisike_2` 第一次被报成"读不到 prefab 层列表"，实际是
  "prefab 挂了 1 层但目录里没有任何 `.skel`"（空壳导出）。两种错的处理方式完全不同。
- ⚠️ 别把"画面没变"一律算成没生效：`buleisite` 变了证明机制通，`pulimaosi` 没变的原因**没查死**，
  要留在文档里而不是并进战果。

**涉及文件**：`scripts/compose_paintings_v2.py`、`scripts/extract_spine_v2.py`、
`scripts/build_gallery_index.py`、`gallery_src/index.html`、`gallery_src/cg_export.html`、
`scripts/diag/{spine_parts_prefab_diff,spine_parts_wiring,make_pair_sheet,gallery_index_diff_check}.py`。

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
| `Output/Paintings_v2`、`Spine_v2`、`Live2D`、`CG_v2`、`Audio`、`gallery_v2/` | 画廊 | ✅ 全量可再生。**耗时按 2026-10-01 实测外推：立绘 4488 张 ≈ 1.5 小时（1.25 秒/张）、Spine 269 个 ≈ 8 分钟、CG 231 张 ≈ 5 分钟、Live2D ≈ 30 分钟、音频全量 ≈ 75 分钟 ⇒ 一把梭全量 4~6 小时，共约 41GB 写入**（旧版这里写的"数十小时"是老 AssetStudio 时代的数，已纠正）。正因为它不再是"跑不起"，**才更要把范围收窄成增量**——见步骤 5 与 §71 |
| `Output/gallery_v2/vendor/`（19 个第三方 JS，约 2.2MB） | 画廊 Live2D/Spine 标签 + **3D 宿舍页**（`room3d.html` 用 three.js r160 + GLTFLoader + postprocessing）的运行时 | ✅ 可再生（2026-09-26 起）：台账 `gallery_src/vendor/MANIFEST.json`（版本+字节+sha256+来源）+ `py -3 scripts/fetch_gallery_vendor.py`；**条目本身怎么生成的**在 `scripts/diag/build_vendor_three_entries.py`（逐个从上游重新下载、按 sha256 对拍，只有命中才标 `verified: true`——台账的纪律是不写没验证过的来源）。**库本体不入库**（含 Live2D 专有许可的 Redistributable Code）。⚠️ 唯 `spine/spine-all.js`(3.8.75) 无可按哈希校验的下载源（本机这份与上游官方构建不同），只能从 `tools/spine-viewer/spine-runtime/` 取——**它也在 gitignore，别清**。⚠️ **台账列全 ≠ import 闭包完整**：ES module 缺一个相对 import 会让整页**静默不初始化**（2026-10-10 真实事故：`GLTFLoader.js` 依赖 `../utils/BufferGeometryUtils.js`，18/18 全绿而页面空白，见 §128）⇒ 改 vendor 后必跑 `py -3 scripts/diag/check_vendor_closure.py`（含 `--break-demo` 自测） |
| `Output/gallery_v2/dorm3d/`（`room.glb` 31MB + `lightmaps/` 3MB + 四张 sidecar） | **画廊「3D 宿舍」页**（`room3d.html` 用相对路径 `./dorm3d/…` 直引）+ 验收探针 `room3d_page_probe.py` | ✅ 可再生：`py -3 scripts/dorm3d_room_to_gltf.py`（默认就写到这里，19 秒）+ lightmap 页由同一次构建落盘。sidecar 各自的作用见 **WF-38 追加（2026-10-10）** |
| `files/AssetBundles/dorm3d/`（474 个包 / 146MB，gitignore） | 上面那次重建的**唯一输入**（场景包 + 它跨包引用的家具/贴图/光照包），也是 `dorm3d_pptr_resolve.py` 建 CAB 索引的根 | ⚠️ 半可再生：要从设备侧重新拉（MuMu `mumu_sync --only`，见 `al-device-forensics-mumu`），且**必须与 `Output/dependency_manifest.json` 同时刻的版本**才对得上——清单换了版本而这里没换，跨包 PPtr 会指到别的包上。删之前先确认还能拉回来 |
| `Output/Raw/`（背景层 1,899 png / 2.0 GB） | **画廊「背景库」页**（`backgrounds.html` 直链 `../Raw/<类目>/<名>.png`）+ `Output/gallery_v2/bg_meta.json` 的 `img` 字段 | ⚠️ **2026-10-07 起从"可删的悬空层"升级为页面依赖**：删它 = 背景库全空（缩略图 `bg_thumbs/` 还在，点进去才是空）。可再生：`py -3 scripts/export_assets.py --target <类目>`；**只补个别包用 `--only <包名>`**（整类目重导会覆写已验证产物，为个别缺口不划算）。⚠️ 这层是**冻结导出层**，源包更新后不会自动跟上（实测两张 09-24 拉进来的包到 10-07 还没出图，见 §115 第 6 条）。命名源不在这层里，在 `inputs/gamecfg/bg_scene_refs.json`。见 **§115 / WF-30** |
| `gallery_src/` 前端正本 ↔ `Output/gallery_v2/` 同名副本 | 画廊前端 | ✅ 同一份数据两个路径名（硬链）。**清单以 `scripts/deploy_gallery.py` 的 `FILES` 为准，别在这里抄数字**（2026-09-26 那版写死"4 个"，之后加 `bgm.html`、`backgrounds.html` 都没回来改，早就对不上了）。断链探测器：`py -3 scripts/deploy_gallery.py --check`；**新增子页必须同时进 `FILES`**，否则它既不被硬链也不被漂移检查看见（= 回到"改了忘部署"那个老静默失效，见 §115 第 5 条） |

> `.diag/` 已写入 `.gitignore`，定位是「临时产物区」；**可复用工具一律放 `scripts/diag/`（入库）**。清理 `.diag` 前必须先跑上表白名单核对。
> **权威外部输入一律不得放进 `.diag/`**——2026-09-24 起它们住在 `inputs/<来源>/`（数据本体不入库、只入 `MANIFEST.json` 台账），
> 跑任何依赖它们的管线前先校验：`py -3 scripts/diag/check_inputs.py`（逐文件比 sha256/bytes，缺失或漂移即非零退出）。

#### 步骤
0. **先验权威输入**：`py -3 scripts/diag/check_inputs.py` 必须 `[PASS]`，再动任何元数据/语音管线。
1. **只读差异，先不动手**：`python scripts/mumu_sync.py diff` → 输出三类：新增（模拟器有/本地无）、大小不一致（同名但本地旧）、本地独有。记下版本号与数量（385 那次 = 95 文件）。
2. **同步源包**：`mumu_sync.py sync`（或 `mumu_adb.py pull`）落到 `files/AssetBundles/`。
3. **重生成官方依赖表**（**最容易漏的一步**）：`python scripts/export_dependency_manifest.py --out Output/dependency_manifest.json`。不重生成 → 新包的 PPtr/externals 解析不到 → 新皮肤合成失败或层级缺失。
4. **Unity 版本伪装**：新包 header 可能仍伪装 `5.x.x`。若加载报错，更新脚本里的 `UnityPy.config.FALLBACK_UNITY_VERSION`（当前 `2022.3.62f3`）为游戏实际引擎版本。
5. **定位受影响子集**（不要全量重跑）：2026-10-01 起这一步是**自动的**——`update_pipeline.py` 的
   `pull` 阶段跑 `mumu_sync.py diff --list-out` 把「新增+大小不一致」的相对路径落成
   `.diag/pipeline/affected.txt`，并盖上**当前输入指纹**（`affected.meta`，两份必须一起写）。
   各导出阶段再按自己的域过滤成 stem（`stems_for(top,…)`，"是不是主皮肤"由**磁盘上有没有那个
   不带后缀的主包**裁判，后缀表只当预筛——`_bj1` 躲得过 `_bj`，见 §71）。
   ⚠️ **清单缺失/过期一律判红停下，不会退化成全量**：曾经 `None` 一个值同时表示"没范围"和
   "全范围"，于是"增量"静默等于全库重跑。手动路径依然可用：自己写 `affected.txt` 时**必须同时**
   写一份 `affected.meta`（`{"fingerprint": "<update_pipeline.fingerprint()>", "at": …}`），
   只写清单没有配套指纹 = 会被判过期。
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

#### 资源占用 / 进度可见性 / 签字门（2026-10-01 实测，回答"跑一次要多少 G、要多久、前台看得到吗"）
- **占用**：13 个阶段**全串行**，阶段内部也是 for 循环一批一批 spawn ⇒ 同一时刻只有 1 个子进程。
  按进程树采峰值 WorkingSet（`py -3 scripts/diag/peak_mem.py --tag x -- <命令>`，
  先用已知 400MB 分配自测过准头）：立绘 50 包一批 **0.63GB/17s**、8 个真主皮肤 **0.64GB/13s**、
  Spine 3 个 **0.50GB/5s**、依赖表 **3 秒 / 0.20GB**（它只读 `dependencies` 一个包，
  ⚠️ 别把 §50 那句"立绘全库重扫 43 分钟"安到它头上——我 2026-10-01 上午就这么错过一次，见 §74）。
  ⇒ **整条线稳态 ≈ 0.7GB**；这台机 15.4GB 里真正的大头是同时开着的 IDE/浏览器（实测只剩 2~3.5GB）
  和 CG 那步的 headless Chrome 树。**"一次一个重活"防的是 jobs=3 并跑 + 漏 Chrome，不是防这条线+模拟器。**
- **一轮真更新的实测规模**（2026-10-01，1036 个新包 + 118 个变更 = 1154 条路径）：
  `--plan` 报「立绘 14 张 / Spine 2 个皮肤 / Live2D 4 个模型」⇒ 导出侧几乎是零头，
  大头全在**设备侧**（diff 实测 42~69 秒、拉 1036 个包数分钟）。
  所以"跑一次要多久"的真实答案是：**拉包那一两步分钟级，导出侧按变更面从秒到十几分钟，
  只有 `--full` 才会要 4~6 小时**。

- **和 MuMu 共存**：只有第 1 步（diff / 拉包）要模拟器，且它是 adb 文件比对与拷贝（IO 型、几乎不吃内存）；
  其余 12 个阶段全是本地文件活。⇒ 顺序是「开模拟器 → 跑 detect → 签字拉包 → **关模拟器** → 跑导出」，
  不存在"必须同时开着"的冲突。
- **进度**：`run()` 必须**边跑边把子进程输出转给自己的 stdout**（两条流各一线程读，`echo` 命中必转、
  其余按 2.5s 限速并计"抑制 N 行"），否则面板在子进程整个跑动期间一个字都不动，看着就是死掉
  （实测：`mumu_sync diff` 那 69 秒里零输出，靠 `run()` 的 25 秒静默心跳才看得出"还在跑"；
  ⚠️ 我一度把这件事写成"依赖表那 43 分钟"——那是 §50 的**立绘全库重扫**，`deps` 只读一个 dependencies 包、实测 3 秒）。
  `PYTHONUNBUFFERED=1` 救不了这件事——不是缓冲，是 `capture_output=True` 本来就要等进程结束。
- **超时**：走 `taskkill /T /F` 杀整棵树后再抛 `TimeoutExpired` 让阶段判红（§50 那个形状）。
- **签字门**：`live` 档未签字时**不得起任何会写 `Output/` 的子进程**，只跑只读审计，并在结论里保留
  `未签字，请 --approve`（前端 `statusOf()` 按这个正则认状态）。`audio`/`cg` 没有暂存通道，
  所以它们的门比别的阶段更要紧。
- **判据**：`py -3 scripts/diag/test_pipeline_gating.py` 必须 `[PASS]`（40 条）。它不看文案看**行动**——
  只断言"有没有 spawn 那个会覆写正式区的子进程"，因为提示文字会改、会不会去写盘不会说谎。
  ⚠️ 别用 `py … | tail` 判它的退出码（`$?` 量的是 tail）：先 `>log 2>&1; E=$?`。

#### 换机器 / 换用户名（2026-10-01 起路径可迁移，见 §77）
- 仓库根由 `scripts/paths.py` 统一推导；不在默认位置时**只需设一个环境变量**：
  `set AL_ASSETS_ROOT=D:\新位置\Azur Lane Assets`（.bat 里 set 或系统环境变量都行）。推导不出会直接抛错，不会猜。
- 外部工具各有一个 env：`AL_VGMSTREAM` / `AL_FFMPEG` / `AL_CHROME` / `AL_ADB`；不设则走 PATH 再走已知安装位置。
- 数据不在 git 里，换机器要单独拷：`files/AssetBundles`（源包 28.9GB，**diff 的唯一本地依据**）、
  `Output/`（产物约 45GB，可再生但要 4~6 小时）、`inputs/azdata`+`inputs/gamecfg`（**不可复原，见上面的白名单**）。
- 收尾必跑：`py -3 scripts/diag/check_paths.py`（调用链上不许再有写死的绝对路径）。
- 只想拉某几类包：`py -3 scripts/mumu_sync.py diff --only painting,cue`（**带 `--only` 的比对不能生成范围清单**，
  与 `--list-out` 硬互斥——范围清单必须来自一次完整比对，否则"0 差异"会被下游读成"别处都没变"）。

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
> **动手前先 `--precheck-only`**（1 秒）：它量的不是"连得上"而是"真吐出 ≥200KB 字节"，
> 判红时会顺带打一行进程外部现场（pid/threads/handles/父进程是否活着）——
> 2026-09-29 全库跑就是被"连接照收但每个请求 0 字节"的半死态白坑掉 20 分钟，见 §63。
>
> ⚠️ **回归工具自身的两类假失败（2026-09-26 全踩了一遍，各修一处）**——工具红了不代表产品坏了，先证探针再定罪：
> 1. **固定等待**：`l2d_inspector_verify.py` 等 6s、`interact_verify.py` 等 6.5s 就取
>    `l2State.app.stage.children[0]`。大贴图皮肤（`benningdun_2` 三张共 40MB，而服务器
>    是 `ThreadingTCPServer`——**不是**单线程，那句旧结论已在 §62 否证）根本来不及
>    → 报 `Cannot read properties of undefined (reading 'internalModel')`，
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
  - **2026-10-03 更新（§89）**：探针的端口与 profile 已收成一份出口 `scripts/cdp_slot.py`——
    端口由 OS 挑空闲的（`AL_CDP_PORT` 可钉死，被占即拒绝启动），profile 变成
    **`.diag/chrome_<tag>_<pid>`**。所以①上面那条按命令行匹配**仍然有效**（`-match 'chrome_hitv'`
    是子串匹配，命中 `chrome_hitv_85972`），但**别把名单当全集**——按前缀 `'chrome_'` 匹配才不会漏掉新 tag；
    ②"残留 Chrome 占着固定端口"这一类偶发假失败从结构上消失了，代价是 profile 目录数量变多，
    收尾照旧跑 `clean_diag_profiles.py`（它有"30 分钟内修改的保留"窗口，不会误杀并发会话正在用的那份）。

- ⚠️ **每一轮 CDP 批处理都会在 `.diag/` 留一个几百 MB 的无头 Chrome profile**（`--user-data-dir`），39 个就能吃掉 7.7 GB。
  收尾必跑：`py -3 scripts/diag/clean_diag_profiles.py`（干跑看清单）→ 加 `--yes` 删。三条硬判据全过才删：
  目录名 `chrome_*` / 无 chrome|msedge 进程命令行引用它 / 最后修改早于 `--min-age`（默认 30 分钟，防误删并发会话在写的）。
  它只碰 `chrome_*`，`.diag` 下其它产物一律不动——清理 `.diag` 仍要先核对 WF-15 白名单。
  ⚠️ **共享工作树下必须带 `--only <自己这条线的片段>`**（2026-10-10 加）：不带过滤的 `--yes`
  会把别的会话留下的 profile 一起删掉（实测 `.diag` 下 301 个 / 26.7 GB 属于十几个不同会话，
  一轮 3D 宿舍探针自己就留了 18 个 / 1.35 GB）。`--only` 只缩小候选集，三条硬判据一条不放松。
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
py -3 scripts/diag/gallery_motion_probe.py --page index.html --win 1440,900   # 09-29 起样板页已刷进正本
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

### WF-16 追加（2026-10-06）：往画廊里**新增一个页面级文件**要过哪几道

**适用**：新建 `gallery_src/<某页>.html`（本轮 `bgm.html`），或把正本里的共享内容抽成
`theme.css` 这类被多页引用的文件。这类改动不会被六件套里的任何一件"顺带"覆盖到。

1. **`deploy_gallery.py` 的 `FILES` 必须加进来**（本轮 4 → 6：`bgm.html`、`theme.css`）。
   判据：`deploy_gallery.py --check` 打印的「同 inode N/N」里 **N 要等于 FILES 长度**，
   且新页在 `Output/gallery_v2/` 里存在。漏了它的后果就是"正本改了、运行目录那份还是旧的"——
   本项目已经为这个失效模式专门写过 `--relink`。
2. **抽共享 token 只能按字节搬**，三条硬要求：
   - 用 `open(p,'wb')` **原地写**（截断同一 inode ⇒ 硬链不断）；编辑工具走"临时文件+改名"必断链。
   - **不改行尾**：`index.html` 全文件 CRLF，按文本读写会把 2,360 行全标成改动，评审时看不出真正改了什么。
   - **还原比对**：把 `theme.css` 塞回 `@import` 那一行后与 `git show HEAD:` 比，
     归一行尾后必须**逐字节相同**（本轮 187,622 == 187,622）。做不到就不许说"只是搬动"。
3. **页面里放音频/视频 ⇒ 服务器必须应答 `Range`**。`SimpleHTTPRequestHandler` 只发全量
   `Content-Length`，Chrome 就把整条媒体当**不可 seek 的流**：`A.duration === Infinity`、
   进度条恒 0、拖动无效，而"点了能响"一切正常 —— 所以它不会被任何只看响不响的验收发现。
   两条判据（缺一不可）：
   - 零浏览器：`scripts/diag/gallery_server_range_test.py`（首/中/后缀/开区间/越界 416/畸形回落 200 +
     既有 `/cg_exists` 回归，12 条）。
   - 真浏览器：拖到 50% 后 `#t0` 必须落到 ≈ 曲长一半（实测 1:48 → `0:56`）。
4. **探针自己起一份服务器**（`make_server(空闲端口, root)`），不要复用 8777 上那台：
   它跑的可能是**改动前的代码**（改了不重启就不生效），而且另一个会话的探针可能正在用它。
   ⇒ 这就是把 `Handler`/`Server` 从 `main()` 里提到模块级的唯一理由。
5. **动过 `index.html` 就要跑六件套**（本轮 `--skip hit_verify`，五件全绿 EXIT=0）。
   节奏仍是：改 → `deploy_gallery.py`（刷平）→ 提交 → `--relink` → `--check` 6/6 同 inode。

**踩坑记录**：判据自身写错会造出**假红灯**，本轮两条 ——
① 用 `backgroundColor` 判 body 背景（body 用的是 `linear-gradient`，恒 `rgba(0,0,0,0)`）；
② 用 `/` 数 `asset_manifest.json` 的路径层级（它的分隔符是 `\`），于是"≥2 层 0 条"，
   我据此断言那份 manifest 只扫了一层 —— **错的**，它最深 9 层。
⇒ 任何"0 命中 / 恒为默认值"的结论，先证探针与数据的口径对得上，再定罪被测对象。

**涉及文件**: `gallery_src/bgm.html`、`gallery_src/theme.css`、`gallery_src/_gallery_server.py`
（`_serve_range` / `make_server`）、`scripts/deploy_gallery.py`（`FILES`）、
`scripts/diag/bgm_page_probe.py`、`scripts/diag/gallery_server_range_test.py`。
取证全过程 **§112**；省空间口径 **WF-28**。

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

---

### WF-22 追加（2026-10-02）：台词钥匙必须是**查出来的表主键**，且正文要与音频**同档**

`m[皮肤] = cv*10+idx` 这条钥匙在皮肤序号 ≥10 处会进位撞进**下一艘船**的行（`10709*10+10=107100` = 约克城II，
而埃塞克斯皮肤10 的真行是 `137090`）。整页台词派错船，只有"字幕比语音短"这种人耳判得住的矛盾会露出来。
做法与三条根因见 §86。这里只记**下次照做**的部分：

**步骤**：① `scripts/diag/voice_remap_check.py` 只读重算整份语音映射（复用已解码目录的文件名当 cue 名，
零子进程零写入，直接给出"哪些皮肤的 (cv,idx) 会变"）；② `build_skin_words.py --voice <临时映射> --out <临时词表>
--audit <tsv>` 在 `.diag/` 里出改后产物；③ `scripts/diag/voice_words_diff.py` 判零回退；④ 绿了才跑正式区。

**判据**：
- **正文与音频同档**：从 cue 文件名反查档位（`E.split_cue(basename)`）。音频取的是**本皮肤档**文件的槽位，
  正文**不许**回退到本体行（那是同一个错派的另一副面孔）；只有音频落在基础档的**船级**类别
  （誓约/资料/委托/强化）才回本体行——因为皮肤行里根本没这些字段，不回退就是 432 条"修好触摸、弄没誓约"。
- **台词与音频同一个语音包**：同一 painting 在表里可能有多行（META/联动另开一档，如 `aerjiliya`
  同时有 900419/903020）。取行时要 `prefer_cv=` 这条皮肤实际用的包号，否则 262 条台词被判无词。
- **画法变体不占语音档位**：`X_n`/`X_hx` 是同一张皮肤的另一幅画 ⇒ 从 `art_root()` 继承，
  不参与 `assign_pending_idx` 的分配（否则 15 个变体各占一档，还挤掉 24 个真皮肤）。
- **零回退闸门必须会把"旧有新无"拆开归因**，四档：`错派回收`（旧行属别的实体 = 修对了）/
  `不可见回收`（新旧都不渲染那一格）/ `音频改档待补`（A0 换对了音频、那一档表里没词）/
  **只有 `真回退` 判红**。并跑一次**反向对照**（新旧对调必须红）——否则"0 红"可能只是闸门根本没在比。
- 活动变体（`_ex<code>`）**没有**正文来源（全表只有 6 行带 `*_replace`）⇒ 只留音频 + 标「活动版」+
  一行解释；不解释一句，用户会当成"字幕坏了"（15319 行的可见变化，必须主动说明）。

**踩坑记录**：见 §86（三次改坏：没加船级回退 → 回退不限档 → 多行同名取第一行）。
**关键教训**：`row_id_for()` 这类"从两个命名空间反推主键"的算式，一旦写进 join 就会伪装成"永远成功"——
`107100` 那行**存在且有正文**，所以旧代码的 `if not row: 皮肤无正文行` 这条护栏永远不会响。
⇒ 凡是"算术式算出来的键"都要问一句：**这个等式是哪来的、什么时候会不成立**。

**涉及文件**：`scripts/extract_cv_voice.py`（`row_id_for()`/`art_root()`/`assign_pending_idx()`）、
`scripts/build_skin_words.py`、`scripts/diag/voice_remap_check.py`、`scripts/diag/voice_words_diff.py`、
`scripts/diag/test_voice_owner.py`（24 例，含反向对照）、`gallery_src/index.html`。
相关：`WF-21`、`WF-15`（换入闸门）、`WF-16`（回归六件套）、§47/§57/§84/§85/§86。

---

### WF-23: 资产更新流水线 —— `scripts/update_pipeline.py` 阶段机 + `pipeline_panel.py` 控制台（把 WF-15 变成一条命令）

**日期**: 2026-09-29
**目标**: 游戏出新版本后，不用人对着 WF-15 那 11 步手敲十几个命令。**一条命令跑到「待你确认」**
（所有重活只写临时区），看过对照表再**第二条命令签字换入**。

```bash
py -3 scripts/update_pipeline.py --plan                 # 只读：这次会动什么、哪些档要签字
py -3 scripts/update_pipeline.py                        # preflight→…→review，live 档一律不放行
py -3 scripts/update_pipeline.py --approve deps meta    # 点名放行指定 live 档
py -3 scripts/update_pipeline.py --approve swap-in derive   # 看过对照表后换入
py -3 scripts/update_pipeline.py --full                 # 全量（先报规模、要手输 FULL 才动）
py -3 scripts/update_pipeline.py --only spine --force   # 只重跑某阶段，绕过"本指纹已完成"缓存
```

**阶段三档**（决定它能不能自动跑）：

| 档 | 含义 | 行为 |
|---|---|---|
| `read` | 只读检查 | 永远自动跑，**永不缓存** |
| `staged` | 只写 `.diag/pipeline/` | 自动跑，按输入指纹缓存 |
| `live` | 写 `Output/` 或 `files/` | **必须 `--approve` 点名**，否则只做该阶段的只读那半并告诉你怎么放行 |

`pull deps meta audio cg swap-in derive` 是 live 档。

**三条设计约束（改这个文件前先读，都是踩出来的）**：

1. **退出码不作通过证据。** 盘点出来的事实是：`export_cue_audio` / `make_thumbs` /
   `fix_model3` / `compose_paintings_v2` / `l2d_motion_audit` /
   `spine_parts_prefab_diff` / `voice_gap_audit` / `run_cg_export` 这 8 个 **失败时照样 exit 0**。
   （`extract_spine_v2` 原属此类，2026-10-07 已改为失败即非零退出，并让「parts.json 落不下」这类
   行尾失败顶到行首 `✗` —— 判据 `py -3 scripts/diag/test_spine_exit_code.py`，取证 §111 第 4 节。
   ⚠️ 但**本条原则不要跟着松**：其余 8 个仍未修，退出码依旧不是通过证据。）
   所以每个阶段自带判据：数 `✗` 行、数 `完成N 跳过N 失败N`、要求 `[SUMMARY] 模型 i/n 处理完`
   这种收尾行、或直接跑对应的 gate 脚本（`l2d_texorder_check` / `l2d_tex_completeness` /
   `ship_meta_authority_diff` / `gallery_index_diff_check` / `deploy_gallery --check`）。
   **没有判据的阶段不许算通过。**
2. **写向优先 argv；只有 env 通道的脚本必须把注入值打出来。**
   `build_gallery_index.py`（只有 `GALLERY_OUT_DIR`，无任何 argv）、`fix_model3.py`
   （只有 `L2D_OUT_DIR`）、`make_thumbs.py`、`deploy_gallery.py` 属此类。
   2026-09-24 那次 269 个模型被原地覆写（§25），根因就是脱离进程下 env 能不能被子进程读到
   **不可复现**。⇒ 编排器对这几个显式注入并回读打印；也因此"用新元数据预览索引"
   这一步**没法只落临时区**（`ship_meta.json` 路径写死），只能归进 live 档。
3. **覆写一批产物之前先扫 `st_nlink`。** 历史上做过逐字节去重，共享 inode 的两个名字
   「写一个变两个」，会让修复看起来完全失效（§64）。`review` 阶段把待断清单写
   `.diag/pipeline/hardlinks.txt`，`swap-in` 据此决定是否带 `--break-hardlink`。

**状态与续跑**：`.diag/pipeline/pipeline_state.json` 记输入指纹（源包文件数 + 依赖表 md5）
与每个 staged 阶段的结论。**只缓存判绿的 staged 档** —— 把失败或 `read` 档缓存下来，
等于下次不再检查，正是这类工具最容易造的静默失效。输入指纹变了自动全部作废重判。

**判据（怎么确认编排器本身没坏）**：
- `--plan` 退出码 0 且列出 13 个阶段与 live 档清单；
- `--only preflight,review` 在**没有任何临时产物**时也必须优雅判绿（不能抛异常）——
  第一版就是 `chg` 未初始化直接崩，被这条抓到；
- `--only spine` 配一个 2 行的 `.diag/pipeline/affected.txt`，应只处理这 2 个 stem、
  产物落 `.diag/pipeline/Spine_v2/`、`Output/` 一字不动；
- 再跑一次同一命令应打 `⏭ 本指纹下已完成…要重跑请加 --force`；加 `--force` 应真的重跑；
- `--only deps`（live、未签字）应**跑完只读那半**（重生成到临时区 + 比出丢失数）再停下要签字。

**踩坑**：
- ⚠️ f-string 里嵌同种引号在 Python 3.11 直接 SyntaxError（3.12 才允许）。第一版
  `f"增量 {len(todo) if todo else "未 detect"}"` 就是这么写的，编译期才炸。
- ⚠️ `--only` 是**过滤器**不是"强制重跑"。第一版的跳过提示写成"要重跑请用 --only <key>"，
  自相矛盾、照着做会以为缓存没生效 —— 另加 `--force` 才说清楚。
- ⚠️ 别把这条流水线做成"一键覆写一切"：AGENTS.md 要求全量运行前经确认，而换入不可逆。
  两档命令（跑到待确认 / 签字换入）是这套东西能安全存在的前提。

**涉及文件**：`scripts/update_pipeline.py`（★新增，阶段机 + `STEPS`/`writes` 定义）、
`scripts/pipeline_panel.py`（★新增，控制台）、`scripts/diag/panel_ui_probe.py`（★新增，界面验收）、
`启动资产更新控制台.bat`；被编排的
`mumu_sync.py`、`export_dependency_manifest.py`、`build_ship_meta.py`、`compose_paintings_v2.py`、
`extract_spine_v2.py`、`reconstruct_live2d.py`/`extract_motions.py`/`fix_model3.py`、
`extract_cv_voice.py`、`run_cg_export.py`、`painting_swap_in.py`、`make_thumbs.py`、
`build_gallery_index.py`、`deploy_gallery.py`、`wf16_regression.py`，
以及闸门 `diag/{check_inputs,ship_meta_authority_diff,gallery_index_diff_check,l2d_texorder_check,l2d_tex_completeness,l2d_motion_audit,voice_gap_audit,l2d_voice_inventory,make_pair_sheet}.py`。
相关：`WF-15`（本 WF 想替掉的那份手工 runbook，仍是权威细节来源）、`WF-16`（回归六件套）、
`WF-22`/`WF-21`（语音与台词链路）、§25（写向走 argv）、§64（硬链吞修复）。

#### WF-23 追加（2026-09-29）：可视化控制台 `scripts/pipeline_panel.py`

命令行编排器之外补了一个**本地网页控制台**——它**不重新实现任何逻辑**，每个按钮都是去起
`update_pipeline.py` 子进程、把它写的日志实时读回来显示。所以界面和命令行永远是同一套代码，
不存在两份逻辑各自漂移。

```
双击  启动资产更新控制台.bat          ← 起服务 + 自动开浏览器（跟开画廊一模一样的习惯）
或    py -3 scripts/pipeline_panel.py [--port 8788] [--no-open]
```

**界面按「四步主线」组织，不是把 13 个阶段平铺成一张表**（第一版就是平铺，用户判"看不懂"）：

| 步骤 | 阶段 | 主按钮（2026-09-30 起为短语式，原「（不下载）」那类安心话已删） |
|---|---|---|
| ① 接模拟器 | `preflight` `pull` | ▶ 预检 + 看差异／⚑ 拉包进 `files/` |
| ② 重新导出 | `deps` `meta` `paintings` `spine` `live2d` `audio` `cg` | ▶ 跑到待确认 |
| ③ 看图对比 | `review` | ▶ 出对照表 |
| ④ 签字换入 | `swap-in` `derive` `regress` | ⚑ 换入正式区（confirm 二次确认） |

步骤归属与「写到哪儿」定义在 `update_pipeline.STEPS` 与 `Stage.writes` 里，**面板只读不抄**；
新加阶段忘了写 `step` 会在界面上显式挂一条「未归组 · 判红」，不静默藏起来。

**颜色只表示状态，不表示档位**（上一版把 read 蓝 / staged 绿 / live 红 拿来标档位，
于是"红色"同时意味着「写正式产物」和「出错了」，用户就不敢点）：
未跑=灰、判绿=绿、等你签字=琥珀、判红=红、在跑=青闪；档位一律用中性文字徽标
`ⓘ 只读` `▣ 暂存` `⚑ 写正式`。左轨常驻这块图例。

每张阶段卡写四件事：**写到哪儿**（未签字写到哪、签字后写到哪）、**判据**（它自己那条，
用户可以核对机器到底判了什么）、**上次结论**、**签字框 + 单独跑**。
顶栏常驻 `输入指纹` / `本次范围` / `阶段 N/13 判绿` / 任务状态，右上角常驻**「怎么用」抽屉**
（这是什么、动手之前的前置条件、四步各自会动/不会动、签字到底签什么、为什么不信退出码、
判红了怎么办、以及**全量重跑故意不在这个界面里**）。

**安全边界（这是个能起子进程的本地服务，所以写死三条）**：只绑 `127.0.0.1`；
能跑什么由 `update_pipeline.STAGES` 的**阶段名白名单**决定，前端传来的名字不在白名单直接拒
（所以不存在"把输入拼进命令行"这条路）；图片只从 `.diag/pipeline/` 出，`realpath` 前缀校验防穿越。
`--full` 在网页上**故意不做** —— 它要手输 `FULL` 二次确认，那种确认不该是一个 click。

**背景层：东京夜的星野，显影式**（2026-09-29 两次改口：先"别大海了，做星辰，
划过散开再聚集回来，色调要东京夜"，再"很多星星，但只有经过才显示，像 mimo.xiaomi.com/coder"）。
**先把参照物的机制量清楚再动手**：那页不是"推开"，是**擦除式显影**——遮罩被光标擦出洞，
洞随笔画速度从约 8px 长到约 128px，亮点约 520ms 淡完、不残留。照这个做成：
一张 2D 画布 + 每颗星一个 `home/位移/速度/亮度`，约 1800 颗（`w*h/620`，上限 2800）；
**静止时 `lit` 全为 0 ⇒ 一颗都不画**；划过 ⇒ 半径 `9 + 速度×1.5`（封顶 130px）内
`lit = max(lit, (1-d²/R²)^1.15)`；每帧 `lit *= exp(-4.6·dt)`（520ms 剩 9%）。
连线在建表时算好，**两端都亮才画** ⇒ 划过时"连出"一片星座、走开整片淡掉。
点击 = 更大半径 + 冲击环。收摊时把 `lit` 写回 0、位置写回 home 再画一帧
⇒ 与初始静止帧逐像素相同（这条从画廊那三轮继承下来，一次都没松）。
色板：偏紫的黑底 + 钠灯橙 / 霓虹品红 / 高架青三团不动光晕；**五个状态色一个都没动**。
沿用画廊的三条：阻尼按秒不按帧、瞬移不算划过（但**要按速度判**，见 §67 一）、数据面全不透明。
顶栏「星辰 · 开/关」停用整层并记住选择。本轮新撞的四条见 §67。

**交互（用户要"交互性高的"）**：`1`–`4` 切步骤、`R` 跑当前步主动作、`P` 只看计划、
`H` 开关说明抽屉、`S` 开关背景、`Esc` 关弹层；日志上方可按
「全部 / 只看红 / 等你签字 / 只看阶段行」筛；勾签字框会把该框点亮；悬停阶段卡会点亮
左轨对应的状态点。一条纪律：**实心品红只用于"当前步的主动作"**，`怎么用` 走描边霓虹——
一个填充色同时代表"主操作"和"帮助"就又回到"一个颜色两件事"。

**面板自身的验收（★ `scripts/diag/panel_ui_probe.py`，32 条，退出码即结论）**：
结构类（6）—— 13 阶段 / 4 步骤读全、每阶段都有 `writes`、左轨恰好四步且 13 个状态点全覆盖、
逐步数签字框 == 该步 live 档数、**档位徽标不得与任何状态色同色**（并反向断言状态色确实在用，
防空判据）、抽屉可用可关；
背景类（10）—— 星野够密（>1200 颗）、**静止时显影场为空（亮着 0 颗）**、静止不排帧、
**背景可见区两帧逐像素相同**、不透明内容区相同、划过才显影（亮着 >150 颗 + 笔画数 +
背景可见区出现星点，三者一起判）、**locality：只划左半边时右半边必须仍为 0 颗**
（防"整片一起亮"这种看着热闹其实错的实现）、淡净后回到**同一张**静止帧
（背景区严格 0 **且残留位移 0 且显影场清零**）、关掉背景后背景可见区必须空掉 >3000 像素
（正向对照）、`prefers-reduced-motion` 时全部退化；
结构性（2，替代"卡片内部逐像素"，理由见 §67 三）—— 数据面计算样式 alpha 必须 = 1、
每个数据元素（卡/日志/缩略图/指标 pill/表格单元）整张落在某个不透明面板内
（这条顺带逮住一个裁切 bug，见 §67 四）；
交互类（5）—— 键盘 `3`/`H`/`Esc` 真生效（⚠️ 要发**完整** key 事件：只给 `text` 时 `e.key`
是 undefined，页面按 `e.key` 分派的键位全不触发，那是探针没模拟到位不是产品坏了）、
日志筛选只留红行、勾签字框会点亮、悬停卡会点亮左轨状态点；
外加任务生命周期 3 条与全程无 JS 异常。
⚠️ 三条通用手法（分区比对 / 固定指针位 / 取样框与滚动容器求交）见 §66 第二条；
第四条「画布会重绘的页面不能拿逐像素当结论」见 §67 三。
另外命令行侧原有几条继续有效：`/api/state` 要报出 13 个阶段与正确的 tier/scope/指纹；
`POST /api/run {"plan":true}` 起任务且日志能读回；未知阶段名 → 400；
`/file?path=../../...` → 403；`{"full":true}` → 400 并给出命令行替代；
**任务结束后 `/api/log` 的 state 必须变成 done**（第一版不会变 —— 前端追日志期间停掉了
8 秒一次的 `/api/state` 轮询，而状态只在 `/api/state` 里刷新，于是面板永远显示"运行中"）；
再起第二个实例必须拒绝（Windows 的 `SO_REUSEADDR` 允许同端口重复 bind，见 §65）；
无头浏览器截图 + 数 DOM：13 行、7 个签字框、档位序列正确。

**踩坑**：
- ⚠️ `.bat` 里的 `>nul` 经 Git Bash 写盘会被改成 `>/dev/null`，启动器直接坏 —— 拼字符串绕开，
  写完回读断言（§65）。
- ⚠️ 控制台读阶段清单用 `importlib.reload(update_pipeline)`，**不要把阶段名/分组再抄一份到面板里** ——
  抄了就会漂移。本轮把「四步分组」也放进了 `update_pipeline.STEPS` 而不是面板，就是这个理由。
- ⚠️ 界面别只改好看：用户说的"看不懂"落在三件事上 —— 13 行平铺没有主线、一个颜色代表两件事、
  以及**没告诉他每一步会动哪个目录**。三条都改才算改对，光换配色是白做。
- ⚠️ 首屏要扫 9 万个源包：`/api/state` 不缓存 + `render()` 不扛空态 ⇒ 打开像坏了（§66 第三条）。

---

#### WF-23 追加（2026-09-30）：把说明性文字请出界面 + 「指针携光」动效层 + 修掉 8 秒闪屏

用户两条反馈：**「界面太多说明性文字了，你把我给你的提示词都写进页面了，很不美观；
按钮和鼠标的交互动画要与众不同」**，以及**「为什么每过一段时间就闪一次？」**。
分别落到三件事上，缺一件他都会说另一件还是不行。

**一、常驻界面上只留数据，理由搬进抽屉**

判据（本轮定下的一条硬规矩）：**一句界面文案如果是在为某个设计决定辩护，
它就该进 `怎么用` 抽屉或 `docs/`，不该进常驻界面。** 据此删掉的：

| 删掉的东西 | 为什么算"提示词" |
|---|---|
| 底部 176px「夜空」带整块 | 在解释星野怎么衰减、怎么"渗不进去"——那是实现说明 |
| 图例下「红色永远只等于判红」那段 | 在为"一色一义"这个决定辩护 |
| 对照表下「图放在不透明的底上…」 | 同上 |
| 判据里的「（这三个可信）」「退出码可信」 | 论证，不是判据内容 |
| 按钮上的「（不下载）」「（正式区不动）」 | 安心话，签字闸门已经管着 |
| 日志占位两行长句、指纹占位「（要扫 9 万个源包）」 | 教程式解说 |

搬进抽屉的：新增「**颜色与档位怎么读**」一节，收留图例那段被删的语义解释。
留下的都是**读界面时要的信息**：每张卡的 `写到` / `判据` / `上次` 三行**一行都不藏**
（可检查性优先于美观，hover 才显示 = 退回旧毛病），只是把措辞压成短语。
按钮标签一律动宾式：`▶ 预检 + 看差异` / `⚑ 拉包进 files/` / `▶ 跑到待确认` / `⚑ 换入正式区` /
`签字放行` / `单独跑`。

**二、光效层：全站只有一条动效语言——「光由指针携带」**

| 手势 | 反馈 |
|---|---|
| 指针进入控件 | 一道光沿**边框**从进入那一点起跑，绕一圈回到它，然后消失（0.78s，无 fill） |
| 指针停留 | 控件内一团柔光跟着走（`mix-blend-mode:screen` 只提亮不压暗）；主操作与左轨朝指针让出 2px |
| 指针按下 | 往背景星野打一圈**该控件自己的颜色**的涟漪 ⇒ 界面和那片天共用一套物理 |
| 悬停阶段卡 | 左光条从进入高度向上下**点燃**到全高，离开收回原位 |
| 切步骤 / 切筛选 | **一根**光条从旧项走到新项（不是每项各画一根） |

实现与纪律（这三条决定了它能不能被验收）：
- **两个全局单例浮层** `#fxbeam` / `#fxpool` 搬到目标控件的矩形上，不给每个控件加子节点
  —— 控件全是 `render()` 重建出来的，往节点里塞东西就会跟着抖。
- 边框光用 `conic-gradient(from var(--ang))` + `@property --ang` 注册成 `<angle>` 才能插值，
  再用 `mask-composite:exclude` 把渐变裁成 1.5px 的环。**不用 fill-mode**：
  播完 `opacity` 自己回 0，"光走了不留痕"才是可断言的，而不是靠 JS 掐表清类。
- **全部指针驱动，零常驻循环**（背景那层同一条要求）⇒ 静止时 `getAnimations()===0`。
- **装饰不进数据面**：日志 `pre` 不挂柔光；对照图只吃边框光（screen 混合会改变立绘像素值，
  而这张界面第一用途是验资产正确性）。
- `M` 键 = 「动效从简」（`body.calm`，与 `S` 关背景各自独立、都记住）。
  ⚠️ 关掉的是**动**，不是**信息**：`#railmark`（当前在哪一步）在从简模式下必须照样落位，
  只是不再位移动画。
- ⚠️ 凡是"跟着指针改几何"的效果，离开时**每一个变量都要复位**。本轮漏复位了
  `transform-origin`（`--oy`），光条就永久偏在指针进来过的高度——肉眼看不出，
  逐像素量出 104 个点全落在同一列（§68 四）。

**三、验收（`scripts/diag/panel_ui_probe.py`，判据 32 → 52 条，退出码即结论）**

新增两节，**顺序有讲究**：

- **静止不闪（3 条）**：`__probe.poll(true)` 之后跨一次 8s tick 比整屏逐像素 == 0、
  `pinned()` 断言 `.step/.stage` **节点对象没被换过**、`getAnimations()===0`。
  ★ 这一节**必须带着轮询跑**，且必须排在旧的静止判据之前——旧判据依赖 `__probe.stop()`，
  正是那个开关把闪屏移出观测范围三天的（§68 二）。
- **光效（10 条）**：悬停时边框光束 `getAnimations()` 非空 + 柔光 display 非 none；
  **两帧之间边框光位置变了**（证"在走"而不是"亮了个框"）；离开后动画归零且
  **回到同一张帧 == 逐像素 0**；日志面上方不得挂柔光；`M` 关掉后浮层 `display:none`
  且悬停不触发；`#railmark` / `#chipmark` 落位 == 目标项 `offsetTop/offsetLeft`。
- ⚠️ 判"动效在动"要**先掐掉同屏其它动画源**：这段先把星野关掉再量，否则指针划过点亮的
  星点持续衰减会白送一个"两帧有差"的假绿灯；并补一条"跑完已把星野交还给下一节"，
  防止开关状态漏到后面的背景判据里。
- ⚠️ 背景节那两条"静止时显影场为空 / 静止时不排帧"现在改成**先 park + 轮询到 `raf==0`
  再量**：上一节用真鼠标划过页面，不先落到静止就量，量的就是衰减中的场（实测假红 30 颗）。
- 计算样式断言**不要写死字面值**：`transform-origin:50% 50%` 会被解析成 `1px 67.32px`，
  拿字面串比会得到假红灯——正确形式是跟"进入前的基线"比。

**涉及文件**：`scripts/pipeline_panel.py`（PAGE 的 CSS/HTML/JS 三层 + 光效引擎 + 签名守卫）、
`scripts/update_pipeline.py`（`STEPS` 与 `Stage.title|judge_desc|writes`、未签字 verdict 文案）、
`scripts/diag/panel_ui_probe.py`。踩坑与判据教训见 **§68**。

---

#### WF-23 追加（2026-09-30 第二轮）：拿公开设计系统的禁止清单当版面判据 + 星体重做

用户仍判「还是太丑了，你借鉴一下大厂的优秀 UI，星星画得有点敷衍」。
**流程上唯一的新东西是：不再自己猜下一版**（§6 待办第 5 条），而是把公开设计系统的
成文 token 取回来，**把其中的"禁止项"直接翻译成判据**。

**取参照物的手法**（可复用到任何"要像大厂"的需求）：
`VoltAgent/awesome-design-md` 仓库按 `design-md/<slug>/DESIGN.md` 收了 70+ 家品牌的
成文 token（`linear.app` / `raycast` / `sentry` / `posthog` / `cursor` 都在）。
raw 域名在本机不通，走 WebFetch 取；先取目录列表拿准 slug，再取正文。
要问的是**具体数值与禁止清单**，不是"给我点灵感"。

**借来的那套值**（落到 `:root`，旧版面整套挂在 `body.legacy` 上，`V` 键当场对照）：

| 维度 | 借来的规则 | 落地 |
|---|---|---|
| 分层 | 零 drop shadow，纵深只靠色阶 + 描边 + 顶边微高光 | `--elev` 归零，`--edge:inset 0 1px 0 rgba(255,255,255,.045)` |
| 表面 | 五档阶梯，**别拿薰衣草色当分区/卡片填充** | `#07080b→#0b0c10→#101116→#15161b→#1b1d23`（通道极差 ≤8） |
| 描边 | 1px 实色三档 | `#24262c / #33363e / #454954` |
| 文字 | 中性冷灰坡 | `#f1f2f4 / #c9cdd4 / #9096a0 / #666b75` |
| 强调 | **不许有第二种 chrome 强调色**、不许大气渐变 | 只留 `--brand:#8b8cf5`；签字按钮借用 await 琥珀（语义自洽）；撤掉面板顶边那道渐变灯管 |
| 圆角 | chip 4 / tag 6 / control 8 / card 12 | `--r-tag/--r-chip/--r-ctl/--r-card` |
| 间距 | 4 的倍数栅格 | `--s1..--s6 = 4/8/12/16/24/32` |
| 小标签 | caption 12px、字距 ~0，**不全大写** | `--tt:none`、`--ph-ls:.2px`（旧版是 `uppercase + .18em`） |

⚠️ **五个状态色一个都不动**——换版面不许顺手改语义色，这是上一轮就立的纪律。

**四条翻译成会红的判据**（不写成判据，下一轮换配色就会把病带回来）：
面板/卡片底色通道极差 ≤8 且卡片比面板高一档；`.pane/.stage/header/button.go` 的
**外投影层数必须为 0**（`inset` 不算）；`.ph/.runs th` 的 `textTransform` 不得为 `uppercase`；
chrome 元素 `backgroundImage` 不得含 `gradient`。

**星体重做**（"敷衍"的真身见 §69 二）：
`arc()` + 手绘十字 → **预渲染精灵图集**（`dust/star/hero/cloud` × 4 档色温 = 16 张离屏画布），
每帧只 `drawImage`（星/亮星额外 `rotate` 一个每颗随机的旋向）。
- 核 = 收紧的高斯（`exp(-t²/0.02)`），芒 = 从核向外**锥形衰减**的三角形渐变，
  hero 六芒 + 极淡外环；`cloud` 是摊到边缘的纯高斯，用来铺银河带的**星云**。
- ⚠️ 每个外层渐变必须乘 `(1-t²)` 窗口让 t=1 严格归零 —— 否则 radial gradient
  超出 r1 后沿用最后色标，**每颗星外面套一圈看得见的正方形**。
  判据：读精灵位图，**四角 + 四边中点 alpha ≤8**。
- 亮度按**幂律**：hero 0.47% / star 9.4% / dust 90.2%（旧版亮星 ~5% ⇒ 像撒图钉）。
- 颜色按**色温**（蓝白→冷白→淡金），暗星偏蓝白，只有亮星走暖端。
- 星座连线 alpha 上限 `ST.LINK_A=0.16`（旧版 0.52 是"连点图"观感主因）。
- 闪烁只调制 `lit` 那一项（`vis = amb + f(lit)`），常驻项绝不吃时间 ⇒ 静止帧仍逐像素相同。
- 星云单独一张**永不重绘**的 `<canvas id="nebula">`：跟着星点画布每帧 blit 等于每帧拷 6MB，
  在无头里把一次截图拖到 2.16s，还每帧重合成带 dither。

**验收（`panel_ui_probe.py`，判据 52 → 66 条，退出码即结论）**，新增三节：
版面 token（5）/ 星野画法（5，含"精灵边缘必须透明"与"幂律占比"）/
V 键正向对照（3：切旧版面整屏必须明显变化 >24 级，切回来靠**结构断言**判无副作用）。
⚠️ 本轮三条假红灯全部出在测量通道（截图耗时 vs 动画时长、`inset` 序列化在末尾、
自造哨兵串），产品一处没错 —— 见 §69 四。**判"动画在动"必须用 WAAPI 钉 `currentTime`，
不能靠 `sleep`。**

**涉及文件**：`scripts/pipeline_panel.py`（`:root` + `body.legacy` 对照层 + `gaussSprite`/
`spriteBake`/`nebBake` + `#nebula`）、`scripts/diag/panel_ui_probe.py`。
踩坑见 **§69**。

---

#### WF-23 追加（2026-09-30 第三轮）：主屏改成「一次只暴露下一步」

用户判「整个界面看着还是不是很懂」+「想要简约但交互特效要足」。
给的两个方向里他选了**一次只暴露下一步**。这一轮改的是**信息架构**，不是配色。

**新结构（三层）**

| 层 | 内容 | 承载什么 |
|---|---|---|
| 主屏 `.now` | 一句现状（超大字）+ **一个**实心行动 + 一行"点下去会发生什么" | 决策 |
| 底部 `.steps` | 一根会长过去的进度线 + 四个节点，节点上带该步全部阶段的状态方块 | 全局位置 |
| 抽屉 `#detail`（`D`） | 13 张阶段卡的 写到/判据/上次、日志、对照表、最近任务、指纹 | 证据 |

主屏那句话由**写死的优先级**推出，不是把 13 条结论各印一遍：
`正在跑 > 卡住了 > 等你签字 > 还没做 > 这一步过了`（见 `askOf(n)`，每步一张分支表）。
⚠️ 可检查性没被削弱：`写到/判据/上次` 三行照旧全量呈现，只是从常驻界面挪进一次 `D`。
13 个阶段一个都不许被折叠这条判据，改由底部节点上的 `.dot` 数量继续把住。

**「简约静态 + 丰富动态」怎么落地**
- 静态时**几乎什么都没有**：主屏没有面板、没有描边、没有底色，只有一行小字 + 一句大字 + 一个按钮。
- 表现力全部放在被操作那一瞬，且**只有一条语言**：
  弹簧磁吸与按压回弹（`SPRG`，阻尼谐振子，收敛即停机）、数字滚动（odometer）、
  换句过场（只在内容真的变了时加类）、进度线**长**到当前节点、抽屉弹簧推入、
  边框光束 + 指针柔光 + 点击把涟漪打进星野（沿用第二轮）。
- ⚠️ 弹簧的代价是它靠 rAF 跑，而本项目硬约束是「静止时零个动画在跑」⇒
  每条弹簧在 `|位移|<0.0012 且 |速度|<0.012` 时写死终点，全部停了就关 rAF；
  判据 `__probe.live()==0` 把住。
- **右侧抽屉不许过冲**：过冲会在屏幕右缘闪出一条缝，那是 bug 不是物理 ⇒ 用高阻尼（ζ≈0.85）。

**可读性换做法**：主屏大字不再"蒙一层半透明纱"，改成**星野在文字区主动避让**
（`ST.avoid` 矩形，`starsLight` 里落在其中的星不充能）。让装饰让步，不是给数据蒙膜。
判据成对写：横扫主句区后「总亮数 >0」**且**「落在字底下 ==0」。

**验收（`panel_ui_probe.py`，判据 66 → 76 条，退出码即结论）**
新增主屏 7 条（只有一个实心行动 / 主屏无面板 / 有一句人话 / 四步各一句不重复 /
避让矩形已登记 / 横扫后字底下零颗星 / 弹簧会自己停机）、
遮罩前置 1 条，并把 `settle()`（轮询到 `ST.raf==0` 且弹簧停机）接到所有拍照之前。
⚠️ 抽屉开合改为**轮询 `.on` 真的换态**，不再 `sleep(0.5)` 了事 —— 理由见 §70 一。

**涉及文件**：`scripts/pipeline_panel.py`（`.now`/`.steps`/`#detail` 三层 + `askOf()` 决策表 +
`SPRG` 弹簧 + `avoidRefresh()`）、`scripts/diag/panel_ui_probe.py`。撞到的五条见 **§70**。

#### WF-23 追加（2026-10-01 第四轮）：夜航版落地（海军蓝 + 常驻星野 + 指针携光）与探针契约改写

用户判「资产还原的 UI 去一下 AI 味、UI 特效再优化」。给了三个方向（仪表台 / 夜航 / 海图），
他选 **B 夜航**，配色要 **B 的海军蓝 + 蓝白**，"天活着"的漂移取 **B2 漂移常开**。
⚠️ 漂移常开是**主动付的代价**：上一版"静止时零个动画、两帧逐像素相同"那三条护栏从此必红。

**落地清单（全在 `scripts/pipeline_panel.py`）**

| 层 | 旧 | 新 |
|---|---|---|
| token | 中性冷灰 + 品牌紫（~262°） | 海军蓝表面阶梯（215° 一带，5 档）+ 蓝白强调（~219°）；**五个状态色 rgb 一个不动** |
| 背景 | 显影式星野（静止全黑、划过才亮、~520ms 淡净）+ 三团城市光晕 | 常驻星野（幂律亮度、三层视差 0.35/0.7/1.4 px·s⁻¹、20 帧限流、`DIM` 封顶 0.62）+ 地平线雾；**天是状态面**：信标列对准当前步 + 判绿荡波 |
| 光效 | 边框 conic 光束 + 磁吸位移 + 控件内柔光 | **指针携光**：冷白光晕 `#pool`（压在 `.app` 之下，数据面天然吃不到）+ hover 时**离指针最近那条棱**亮 1px（`#fxedge`，颜色跟语义走） |
| 可读性 | 主屏大字蒙半透明纱 | 星野在文字区**避让**（`ST.avoid`，落在矩形里的星 `v=0`） |

**判据（`scripts/diag/panel_ui_probe.py`，78 条，退出码即结论）**
- 换掉的四条 + 新增两条，每条都写明"替代了旧的哪一条、为什么旧的那条现在必红"：见 **§72**。
- 光效判据**成对**：`k`（页面自算的最近棱）与 `edge_axis()`（CSS 里那道光的走向）必须自洽 ——
  一个说方向、一个说画出来的走向；单独信 `k` 等于让被测者自己判分。
- 避让判据**成对**：矩形里一颗没画 **且** 矩形外一颗没被误杀（后半句防"把整片天关掉"冒充通过）。
- 跨段像素比对一律先 `pin_sky`（冻结 + 钉相位），否则量到的是漂移相位差（假红 149 级）。

**踩坑**：① 控制台进程 **import 时就把 HTML 烘死**，改完不重启 ⇒ 探针验的是旧页面，
症状是 `KeyError: 'k'`（像探针写错，其实是被测对象过期）；② `py -3` 在本机是 3.11，
f-string 内嵌反斜杠直接 `SyntaxError`。两条详见 **§72**。

**涉及文件**：`scripts/pipeline_panel.py`、`scripts/diag/panel_ui_probe.py`。

#### WF-23 追加（2026-10-01 第五轮）：星野退回显影式 + 进度台 + 三态光标

用户否掉第四轮的「常驻漂移」（"我要的就是渐进式显影"）与"不如之前"的按钮/光效，
并新提三条：换鼠标样式、加进度台与预估剩余、别把提示词写进界面。

**落地清单（全在 `scripts/pipeline_panel.py`）**

| 层 | 第四轮 | 第五轮 |
|---|---|---|
| 背景 | 常驻星野 + 三层视差漂移 + 地平线雾 | **退回显影式**：静止全黑、划过才亮、约 520ms 淡净、淡净回**同一张**帧 |
| 光效 | 指针携光（`#pool` + `#fxedge` 最近棱 1px） | **回到** conic 边框光束（`#fxbeam`）+ 控件内柔光（`#fxpool`）+ 磁吸（`.mag`） |
| 配色 | 海军蓝 + 蓝白 | **不变**（五个状态色 rgb 一个不动） |
| 光标 | 系统 cursor | **三态自绘**：默认 / 可点 / 主行动，内联 SVG data-URI，深色描边打底 |
| 进度 | 无 | **进度台**：真在跑才出现的一条细带 —— 阶段 N/M · 已用 · 内存 · 剩余 |
| 帮助 | 含"为设计辩护"整段 | **删掉**（用户要求别把提示词写进界面） |

**进度台的口径（四个量都必须是可核对的事实）**
- 已用 = 子进程启动时刻（`runs.json` 的 `started`），不是"界面刷新了多久"。
- 内存 = **整棵进程树**的工作集之和（ctypes 走 `CreateToolhelp32Snapshot`）—— 只算编排器自己会漏掉真正吃内存的导出子进程。
- 阶段 = 当前日志最后一条 `== key` 行；N/M 的 M 来自**本次 argv 的范围**（`--only` 会缩小它）。
- 剩余 = 各阶段**历史均值**之和（吃 `.diag/pipeline/panel/run_*.log` 的时间戳）；有阶段没样本时**不装作知道**，
  改报「≥」下限，不拿百分比糊一个数。
- 没在跑 ⇒ `gauge=null`，界面一分都不多 —— 这也是"静止时逐像素相同"能继续成立的前提。

**判据（`scripts/diag/panel_ui_probe.py`，86 条，退出码即结论）**
- 撤掉第四轮为漂移加的三条，恢复「静止两帧逐像素相同」「淡净后回同一张帧」。
- 新增进度台一节 10 条：字段存在（没跑时为 null）· 不跑不占位 · 四个量都渲染 · 分母随 argv 缩 ·
  已用走本地时钟 · 内存是整棵树 · 剩余注明"按 N 段历史均值" · 进度条按 done/total 落宽 ·
  缺样本报「≥」下限 · 收工后收干净。
- 服务端口径**单独对账**：直接 import 面板模块、对真实日志调 `gauge_safe()`（import 有 `__main__` 保护，无副作用）。

**踩坑**：① 探针 `EV()` 包 async IIFE 不 `return` ⇒ 一批判据静默全 `None`，而"无 JS 异常"仍绿；
② 「剩余」不记"数据到达时刻"就是死的；③ 进度台不能进 `render()`（否则探针"轮询没重建节点"必红）；
④ 主按钮 hover 白底白字 + 自绘光标在主按钮上整根看不见。四条详见 **§73**。

**涉及文件**：`scripts/pipeline_panel.py`、`scripts/diag/panel_ui_probe.py`。


### WF-24: 从「目录名推的标签」换成「游戏官方真名」

**日期**: 2026-10-04
**目标**: 画廊卡片上的皮肤名从 `皮肤N`（从目录名猜的）换成游戏里真正的皮肤标题
（例：`haixiao_2_doa` 从「皮肤2·doa」改成「金色的特别摄影」）。
**适用场景**: 任何「本地资产显示名」与「上游权威表里的真名」并存、且两边对不上的场景。
不限于皮肤名 —— 只要**显示名是从文件名/目录名反推的**，就适用这套做法。

### 步骤

1. **先量化覆盖率，别先写代码**。用探针统计「按 `painting` 能查到真名的条数」，
   把**查不到的那些按末尾后缀分组**。这一步会直接告诉你真凶是哪几条判据/哪一类键。
   ⚠️ 第一次统计的结果**很可能是错的**（本轮第一次就因判据误杀得出「覆盖率仅 53.8%」的假象），
   对每个「查不到」的类别都要抽 3~5 条**反查表里到底有没有这一行**再下结论。

2. **键的大小写必须归一**。表与盘的键常不一致（表 `haixiao_DOA` vs 盘 `haixiao_doa`）。
   查表**每层都先精确、后小写不敏感**，不要「精确走完再回退」——
   回退式写法会在多层键里先撞上一个不该用的名字。
   追加判据：ci 命中还要**该行的 `ship_group` 在舰级统计里存在**才算终，
   否则「没舰级字段的剧情资源行」会赢过「同一实体带舰级字段的那行」。

3. **区分「变体后缀」与「皮肤序号」，只剥前者**。
   画法变体（`_n` 无背景版 / `_hx` 和谐版 / `_wjz` 无舰装 / `_doa` 联动标记 / `_ex` / `_tolove` / `_ger`）
   可以剥掉去查基名；**数字 `_N` 是皮肤序号，剥了只会拿到船名**。
   本轮实测：为提覆盖率把数字也剥掉，45 条 `qiye_7`/`haman_6` 这类全变成裸船名。
   ⇒ 覆盖率 100% 与 45 条错名二选一，选后者。

4. **「像不像真名」要按形态分判，别用一条字符类**。
   挡十六进制回显用 `^[0-9A-Fa-f]{8,}$`；**不要**用 `^[A-Za-z0-9_\-\.\s]{5,}$`——
   那会把 `Wind Catcher` 这类正常英文皮肤名一起杀掉（本轮 55 行）。
   问号串、遮蔽块字符（U+2580–U+259F）、空值另判，各有各的形态。

5. **配套的正反对照组**。每条新判据至少配一组「该挡的」和「该放的」：
   本轮 14 例（`544845544F574552`/`？？？`/`▅海▊▇洛▅■芬特▇▆` 挡；
   `2B`/`Wind Catcher`/`DEAD MASTER`/`ladyE` 放）。判据是"像不像"型的，没有对照就会静默回归。

6. **换入前四道闸门**：
   - ① `GALLERY_OUT_DIR=<临时目录> py -3 scripts/build_gallery_index.py` 出候选（**注意 `build_ship_meta.py --write` 不认这个变量**）
   - ② 非目标字段**零变化**比对（本轮：`label` 之外全部零变化才算过）
   - ③ `py -3 scripts/diag/ship_meta_authority_diff.py`（元数据闸门，退出码即结论）
   - ④ `py -3 scripts/diag/wf16_regression.py`（六件套，本轮 40 分钟全绿）

7. **⚠️ 别 `import` 会写盘的脚本做只读探查**。`build_gallery_index.py` 在 import 时就
   重建并写盘 `Output/gallery_v2/index.json`；`build_ship_meta.py --write` 只认自己的
   `OUT` 常量。探查走 `skin_table.load()` 单独读表，或复制到临时目录跑。

### 判据速查

| 现象 | 真凶 | 修法 |
|---|---|---|
| 表里有行却查不到 | 键大小写不一致 | 每层先精确后 ci，ci 命中再验 `ship_group` |
| 英文皮肤名整批消失 | `NOT_A_NAME` 用字符类挡 ASCII | 收窄成 `^[0-9A-Fa-f]{8,}$` |
| 标签变成裸船名 | 剥了皮肤序号 `_N` | 数字不剥，只剥画法变体 |
| 同一实体两条都对不齐 | 表盘两边字段不一致 | 查权威表原值，别急着当脏值清 |

### 踩坑记录

- **覆盖率数字会骗人**：第一版探针因判据误杀报 53.8%，修完是 97.5%。
  差的那 43.7% 里大部分不是"游戏没下发"，是**我们自己的判据在挡**。
  ⇒ 报覆盖率之前，先抽样本反查表里到底有没有那一行。
- **`（后排）` 这类后缀**：`ship_data_statistics` 里 8 个 NPC 行的官方名**本来就带**它
  （`马可波罗（后排 原皮）`），而 `ship_skin_template` 那侧没有 —— 两边不一致时
  别急着当"历史脏值"清，先确认哪边是权威（看 `english_name` 干不干净）。
- **子进程被杀掉**：`build_gallery_index.py` 源码里的注释写「13 阶段全串行、稳态约 0.7GB」，
  实际跑索引时内存峰值远高于此，别照着那个数字做规划。

### 涉及文件

- `scripts/build_gallery_index.py` —— `NOT_A_NAME` / `_looks_like_echo()`；`GALLERY_OUT_DIR` 出口
- `scripts/build_ship_meta.py` —— `resolve_base(stem, painting2skin, painting_ci, stats_by_group)`
- `scripts/extract_cv_voice.py` —— `ART_SUF` / `FORM_SUF` / `art_root` / `form_root`（后缀语义的**唯一**定义处）
- `scripts/skin_table.py` —— 权威表唯一读取口
- `scripts/diag/ship_meta_authority_diff.py` —— 元数据闸门
- `scripts/diag/wf16_regression.py` —— 六件套
- `scripts/diag/gallery_index_diff_check.py` —— 索引零回退
- `docs/TROUBLESHOOTING.md` §92

相关：WF-15（承重文件白名单）、WF-16（改前端后必跑回归六件套）、WF-22（台词数据链）。


#### WF-24 追加（2026-10-04 换入那一轮补的三个判据）

**「防错判据本身也会错」——把它收窄到真正成立的那一层**

写"看起来很安全的兜底"时最容易犯的错：把判据套在最外层。
本轮实例：`true_label` 里写了「剥出来的名字 == 这张卡的舰名 ⇒ 那是裸船名，丢掉」。
这对**剥皮肤序号**那层是对的（`qiye_7` → 企业），但套到所有层就出事 ——
`haixiao_doa` 剥掉 `doa` 命中的正是它自己的皮肤名「海咲」，而这张卡恰好也叫海咲，
于是被自己的防错判据毙掉，**58 条 `_doa` 全打回原形**（仍显示「doa」）。
修法：让解析函数返回"这一层是怎么命中的"标志（`from_strip_num`），
**只有该标志为真时才做"等于舰名就丢掉"的检查**。

⇒ 通用做法：兜底判据要**带作用域**，别让它跨层生效。

**闸门的判据会随产品形态变化而失效**

同一轮里闸门自己被改了三处，都是"产品长出新形态、旧判据没跟上"：

| 旧判据 | 为什么不适用了 | 改成 |
|---|---|---|
| 剪影清单里必须都是 `_hei` | 探索者连线 NPC（`tansuozhe*` 等 45 条）也合法住进剪影区（§93） | 「`_hei` **或**探索者 NPC 形态」 |
| 船掉出索引 = 真删除 | 卡上**所有皮肤**都搬进剪影时，那张卡自己也没皮肤可显示了 | 新增「因皮肤全部外迁而摘掉」，判据=至少一条皮肤确实进了新版剪影 |
| 「不在皮肤区」= 两边都不认识 | 一直待在剪影区的条目每轮报 ghost（实测 16→16 零变化却红） | 补上「旧剪影区也没有」 |

**闸门的反向对照，必须先确认 `new` 真的是换入后那份**

本轮自测踩了：验"篡改船名会报红"时，我把新版临时区当 `new` 传闸门、却拿它跟**现网旧版**比 ——
用例报 PASS，害我以为船级 `--expect` 坏了。真实原因是我比的对象不对。
⇒ 反向对照报 PASS 时，先怀疑**比对基准**，别急着判闸门坏。

**`--expect` 的键空间可能重叠**

`kelaimengsuo` / `birui_alter` 既是船 id 又是皮肤 key。
用 `k in o_k` 判"这是皮肤声明"会让它只走皮肤那条、**船级声明永不被检查**。
⇒ 区分两套语义要靠**字段名**（`'label' in v` 判皮肤、`'name' in v` 判船），不靠键本身。

**涉及文件**: `scripts/diag/gallery_index_diff_check.py`、`scripts/build_gallery_index.py`（`true_label`/`_real_name`）

#### WF-15 追加（2026-10-04）：`.diag` 清理判据 —— 哪些能删、哪些是承重

`.diag` 在 `.gitignore` 里，**名字叫"临时区"但里面混着承重数据**。这条追加把实测结论固定下来，
免得下个会话按"临时区"的字面理解把它清空 —— 那会断掉皮肤真名链路的**输入源**。

**判据：`.diag` 下按"能否重取"分三类，不按目录名猜。**

| 路径 | 体积（2026-10-04） | 能不能删 | 理由 |
|---|---|---|---|
| `.diag/chrome_*`、`panel_ui*` | **4.58 GiB**（30 个） | ✅ 用现成脚本 | `py -3 scripts/diag/clean_diag_profiles.py --yes`。三道判据：`chrome_*` 前缀 + **无活跃 chrome/msedge 进程引用**（PowerShell CIM 查 CommandLine）+ 最后修改早于 `--min-age`（默认 30 分钟）。每跑一次 CDP 探针就多留一份几百 MB，**跑完就清** |
| `.diag/sharecfg_re/memdump/` | **2.31 GiB**（1471 个 .bin） | ✅ 已删 | `16_mem_lunt.py dump` 从模拟器重取。逆向早已完结（密钥已找到、32 张表已解出），11 个脚本只把它当**输入**读，没有谁依赖它常驻 |
| `.diag/sharecfg_re/dump/` | **304 MiB**（Il2CppDumper 产物：`dump.cs`/`il2cpp.h`/`script.json`） | ✅ 已删 | 同上，从 `global-metadata.dat` + `libil2cpp.so` 重新跑 Il2CppDumper 即可 |
| **`.diag/sharecfg_re/{lua_json,cfg_json,cfg_json_scalar}`** | **289 MiB**（772/32/32 文件） | ⛔ **承重，别删** | **是 `42_publish_gamecfg.py` 的 `SRC`（唯一输入源）**。删了就得重新从模拟器跑 `34→35→37→41` 逆向才能取皮肤名 |
| `.diag/sharecfg_re/lua_out/` | 47.6 MiB（778 项） | ⚠️ 可清但先确认 | `35_export_sharecfg_lua.py` 的中间产物；`41` 的输入是 `lua_json` 不是它 |
| `inputs/azdata/*.json`、`inputs/gamecfg/*.json` | — | ⛔ 承重 | 见上方白名单表 |

**⚠️ 这条判据为什么重要**：`.diag/sharecfg_re` 3.0 GiB 里，**只有 289 MiB 是承重的**，
其余 2.7 GiB 是可重取的中间产物。原先"`.diag` 整个目录名都在 gitignore ⇒ 可以清"
的直觉会**同时清掉皮肤真名的输入源**。

**验证方式（清理后必跑）**：

```bash
py -3 -c "import sys; sys.path.insert(0,'scripts'); import skin_table; skin_table.load(verbose=True)"
# 期望：azdata N 行 + 设备侧 M 行 → K 行（丢行 0）
```

**回收量参考**：2026-10-04 一次清理 `.diag` 从 **14.6 GiB → 7.5 GiB**（chrome profile 4.58 + memdump/dump 2.55）。
剩下的 7.5 GiB 大头是 `l2d_new*`（1.6 GiB）、`inactivefix_*`（1.1 GiB）、`pipeline`（1.0 GiB）——
那些是**立绘/Live2D 的重跑暂存区**，是否可清要按"对应产物已换入"逐条判，本轮未动。

**涉及文件**: `scripts/diag/clean_diag_profiles.py`、`tools/sharecfg_re/42_publish_gamecfg.py`（`SRC` 路径）
---

### WF-25 定位「某个 Spine 皮肤渲染异常」：三层取证法

**日期**: 2026-10-04（为 §6 第 22 条 `yuanchou_2_hx` 的 CG 细条而建）

### 适用场景

某张 Spine 皮肤渲出来不对 —— 画面缩成中间一小块、偏心、或者长宽比塌成一条。
`docs/TROUBLESHOOTING.md` §45/§46 记过两类成因（框撑太大 / 不落笔附件），
§96 查出**第三类：mesh 顶点数据本身坏**。三类要用同一套判据分开。

### 判据：一层异常对应三个不同的「层」

| 层 | 怎么量 | 异常长什么样 | 该谁负责 |
|---|---|---|---|
| **附件** | `region` / `hasPage` / UV / 贴图区像素 | `hasPage=false`、UV 非法、贴图区空白 | 取景层 `inksOf` 判「不落笔」 |
| **骨骼** | `boneChain` 逐级 `x/y/worldX/worldY` | 某一级 world 坐标离谱，链上其他级正常 | 动画/骨骼数据 |
| **顶点** | mesh `localV`（局部顶点包围盒 + 尺寸） | `localV.far` 巨大而 `w/h` 正常 | **资产本身坏，改不了** |

**关键**：只看**世界坐标**分不出后两种。`yuanchou_2_hx` 的 `BG_desk`
世界坐标 (-29638, 4833859)、骨骼链三级全正常（worldY 只 -78/-153），
但**局部顶点 (-294184, 48339368)、尺寸 320×513 正常** ⇒ 顶点整体被平移。

### 步骤

1. **先定位是谁**：`py -3 scripts/diag/spine_bounds_probe.py <stem>`
   看 `bbox` 与 `farthest`（按 `far` 降序）—— 元凶必然在 `farthest` 前几名。
2. **再定哪一层坏**：同一份输出的每个条目现在带
   `attType` / `hasPage` / `boneChain` / `localV`，对着上表判。
   ⚠️ `localV.w=0` 是**正常**的 —— 那是 `a.vertices` 里只有一组坐标、
   包围盒由缩放后的 `computeWorldVertices` 给出，不是数据缺失。
3. **对照本体**：同一个角色的非 `_hx` 版本跑一遍。**只有和谐版有 ⇒ 数据异常，不是代码问题。**
4. **别急着改判据**：若坏的是顶点，在取景层剔除只是**掩盖坏数据**。
   按 `AGENTS.md`「没有权威依据不许猜」，判为资产缺陷 + 记录不改
   （同 `_hei` 剪影 / `yinggelahan_3` 缺行 / §6 第 12/15 条的先例）。

### 踩过的坑

- ⚠️ **`inksOf` 的缺省方向不要动**。曾把 `if(!reg||!reg.page) return true` 改成
  `return false`，想剥掉「取不到贴图」的附件 —— 实测有害：`BG_desk` 的
  `region` 解析完全正常（`hasPage=true`、UV 合法、贴图区有内容），
  改成 `false` 只会**掩盖真因**并可能误伤真有贴图的附件。判据原样保留，
  否证结论以注释形式留在 `gallery_src/cg_export.html` 里。
- ⚠️ **项目里没有 puppeteer**，所有 CDP 探针都是 Python + websocket
  （`scripts/cdp_slot.py` + `scripts/diag/*.py`）。写新探针照抄
  `spine_bounds_probe.py` 的连接方式，别去找 node 包。
- ⚠️ `spine_bounds_probe.py` 的第二个参数是**皮肤名**（`data.skins` 的名字），
  不是数字 id；多皮肤角色要自己挑对。

### 涉及文件

- `scripts/diag/spine_bounds_probe.py` —— 本轮增强：每个条目多输出
  `attType` / `hasPage` / `boneChain` / `localV`，一次运行即可定位到层。
- `gallery_src/cg_export.html` —— `inksOf` **判据未变**，只加否证结论注释。
- 诊断案例与三条否证假设：`docs/TROUBLESHOOTING.md` §96。
- 相关：§45 / §46（`inksOf` 判据原始出处）、§22 条待办、`PROJECT_STATUS.md` §6 第 22 条。### 操作坑（本轮新增）：无头 Chrome 卡在启动早期，报「not ready」但等多久都没用

**症状**: CDP 探针报 `Chrome not ready (等 300s 仍无 page tab)`，但手动起同样的 Chrome 完全正常
（`/json` 1 秒内返回 5 个 tab）。

**根因**（stderr 里才有，不报的话只能靠猜）：Chrome 卡在启动早期，stderr 只有两类错误：

```
Failed to open persistent cache files in directory
  "...\.diag\chrome_xxx\GPUPersistentCache\DawnGraphiteCache\H6POM..."  error: 0: 另一个程序正在使用此文件
Failed to open named pipe server process 48100: 拒绝访问 (0x5)
```

0x20 = 文件被上一个未退净的 Chrome 占着 ⇒ GPU 持久缓存建不起来 ⇒ **page tab 根本不出现**。
`cdp_slot.profile()` 按 `os.getpid()` 分配目录，每次跑都新建 profile，
前一个 Chrome 没退净就撞上（实测 `.diag/` 堆到 **62 个** `chrome_*` 目录）。

**修法**: 加三个开关，**禁用 GPU**，同一命令 1 秒就绪：

```python
CHROME_FLAGS = ['--disable-gpu', '--disable-gpu-compositing',
                '--disable-features=Vulkan,DawnGraphiteCache']
```

截图走 `--enable-unsafe-swiftshader` 软件光栅，禁 GPU 不影响画面正确性。

**⇒ 教训（两条，都很贵）**：
1. **`run_cg_export.py` / `spine_bounds_probe.py` 那批既有探针也该加这三个开关** ——
   它们没加，所以本轮第 22 条与第 14 条各撞过一次「Chrome not ready」。
   现象极具误导性：**给足超时也没用**（不是慢，是根本没起来），
   而手动起 Chrome 一切正常 ⇒ 容易误判成「探针写错了」。
2. **探针报「环境没就绪」时，一定要把子进程 stderr 打出来**。
   本轮最初只报 `Chrome not ready`，导致连续 4 次重跑都在改无关的地方
   （放宽超时、加固定 sleep、换等待逻辑）—— 真正的线索一直在 stderr 里。

配套改动：
- 等待逻辑从「查不到就重试 240×0.5s」改成「**先固定 `sleep(5)`** 再查」，
  并把重试上限提到 600 次（300s）。理由：新建 profile 时 tab 会短暂消失，
  「查不到就重试」的循环可能正好错过那个窗口。
- `stdout/stderr` 从 `DEVNULL` 改成 `PIPE`，并在失败分支里 `communicate()` 取
  最后 1500 字节打出来 —— 否则诊断信息全丢。
- 清理后 `.diag/chrome_*` 从 62 降到 14（用现成的
  `scripts/diag/clean_diag_profiles.py --yes`，它自带「无活跃进程引用」判据）。---

### 操作事故：`PROJECT_STATUS.md` 压行数时**丢了一整条**（2026-10-04）

**症状**：为把状态文档压回 400 行红线，反复用
`lines[i:j] = new_lines`（j = 「从 i 起直到空行」）替换条目块。
压完后行数达标、**看起来正常**，但**第 27 条整条消失**（记录「一个角色被拆成多张同名卡片」
那个已完成的工作，§95 + 28 个假组键消除）—— **两个提交都没发现**。

**根因**：`j` 的定义错了。条目块内部**可以有空行**，用「直到空行」当结束条件会
**越过后面的条目**，把相邻条目一起替换掉。
更糟的是我压完后只核对了「行数没变」，**没核对条目编号序列**。

**已确认的连带发现**：§6 的编号序列本来就不连续 —— 有子编号复用（`5,6,5,5,6`）、
且 **15/16/17 缺失**（HEAD 里就缺，历史上某次同类压缩丢的，不是我今天造成的）。
⇒ 「编号看起来连续」这个健康检查在本文档上**不可靠**，要用**逐条标题**核对。

**修法（本次已做）**：
1. 从 `git show 64ac022:PROJECT_STATUS.md` **逐字取回**第 27 条原文，放回原位。
2. 核对方式从「行数」换成 **9 条内容断言**（27 条首句+末句、14 条瘦身版、22/24/25/26 条首句、
   §96/§97 引用、TROUBLESHOOTING 的 §92–§95/§97/§98、WORKFLOWS 的 WF-24/25）——全部 OK。

### ⇒ 结论：`PROJECT_STATUS.md` **不做硬压缩**（AGENTS.md 红线规则的正解是「归档」）

`AGENTS.md` 写的是「超 400 行即触发**归档**：把溢出内容**移入 `docs/archive/`**」，
而我今天做的是**压缩**—— 这是两件不同的事：

| 做法 | 行数 | 信息 | 问题 |
|---|---|---|---|
| **硬压缩**（我今天做的） | 达标 | **丢** | 静默、不可逆、无痕迹 ⇒ **最坏** |
| **放行** | 超标 | 全 | 违反红线，但**至少不丢东西** |
| **归档**（正解） | 达标 | 全（逐字外迁） | 需按四条核对，但可验证 |

**根子在于我把细节写进了状态文档**。第 14 条那 21 行里，五层 bbox、修法、验证、健康对照
**全都在 `docs/TROUBLESHOOTING.md` §98 里已有** —— 状态文档那份是**重复副本**。
删重复不叫压缩，**那才叫瘦身**；重复没了行数自然就下来了，不需要任何技巧。

**今后写条目**：
- 每条 **3–5 行封顶**：`状态 + 一句话结论 + 指向 §xx / WF-xx`
- 根因、判据、踩坑、验证数据 → **只写进 `docs/`**（追加地，不受行数限制）
- 状态文档里**不重复** docs 已有的内容
- 真要超 400 行 ⇒ **归档**（逐字外迁 + 溯源注释 + AGENTS.md 那四条核对），**永不压缩**

**涉及文件**: `PROJECT_STATUS.md`（恢复第 27 条 + 第 14 条瘦身 21→5 行，391 行）。
相关：§92–§98（本轮六条）、WF-24/WF-25、`AGENTS.md`「PROJECT_STATUS.md 体量红线」。
把 PROJECT_STATUS §6 断掉的编号 15/16/17 补回（逐字取回 + 一行桩），并加一条机械体检

## 问题

§6 的编号序列长期是 `1..14, 18..27` —— **15/16/17 三条整段缺失**。
查提交历史（`git log -- PROJECT_STATUS.md`）确认：
- **第 15 条是真丢了**：`⏳ 4 张「整张画的每一层都是关闭态」的皮肤`（`qiye_4`/`kelifulan_4`/
  `qiye_dark_memory`/`unknown2_memory`）—— 这是**唯一还没关闭的待办**，丢了就等于静默取消。
- **第 16/17 条是已完成项**，结论已由别处承载（`仅台词`、`parts.json`、`namecode` 占位符），
  缺的只是编号本身。

另有**重号 `5,6,5,5,6`**：第 5/6 号是顶格的**子条目**（「若视觉再被否」「UI/图标批量导出」等），
和主条目 5/6 撞号。这是文档原有问题，不是本轮造成。

## 修法

**从提交 `496871a`（最后一个含三条的版本）`git show` 逐字取回**，用**文本锚定**插入
（找 `^18\. ` 行首，插在它前面），不用行号运算。

第 15 条逐字放回（5 行）；第 16/17 条写成**一行桩 + 指针**（结论已在他处，不重复搬运）：

| 条 | 处置 | 理由 |
|---|---|---|
| 15 | **逐字放回** | 唯一未关闭待办，丢了= 静默取消工作项 |
| 16 | 一行桩 + 指向 §60/WF-22/A21 | 结论已由 `仅台词`、`namecode` 承载 |
| 17 | 一行桩 + 指向 §64/WF-14/A16 | 结论已由 `parts.json`、`15 对` 承载 |

## 为什么不用行号

本轮之前那次事故的根因就是 `lines[i:j]=` 的 `j` 定义成「直到空行」，而条目块内部可以有空行
⇒ 越过了后面的条目。**文本锚定**（`re.search(r'(?m)^18\. ', s)`）不依赖块内空行分布。

## 关键判据：编号连续性是机械体检项

编号断裂是**静默**的 —— 少一条不会报错，只会让下次压缩误判「第 27 条之后还有 19 条」而删错。
所以它必须是一条**能跑的断言**，不是靠人眼扫。已加进
`py -3 scripts/diag/check_doc_numbering.py`（退出码即结论）。

## 涉及文件

- `PROJECT_STATUS.md` —— 补回 15/16/17（+7 行，391 → 400，仍在 400 行红线内）
- `scripts/diag/check_doc_numbering.py` —— 新增编号连续性体检
- `docs/WORKFLOWS.md` —— WF-25 追加本条

## WF-26 状态文档的编号连续性要当**机械体检项**，不是靠人眼扫

**判据**：§6 的顶层条目编号必须 1..N 连续（缺号即红）；同编号多次出现时，
首行**完全相同**才是真重复（红），首行不同 = 顶格子条目复用编号（黄，放行但要报出来）。
跑 `py -3 scripts/diag/check_doc_numbering.py`，退出码即结论。

**为什么不能靠人眼**：编号断裂是**静默**的 —— §6 少一条不会报错、不会告警，
只让下一次「压行数 / 逐字外迁」误判条目边界而删错邻居。真实事故：2026-10-04
压第 26 条时把第 27 条一起吃掉，**两个提交都没发现**，因为当时只核对了「行数没变」。

### ⚠️ 三个已踩过的坑（都在本轮）

1. **别用行号运算定位条目块**。`j = i+1; while lines[j].strip(): j+=1`
   在条目块内部有空行时会越过邻居。**用文本锚定**：`^(\d+)\. ` 行首正则找边界。
   同理，`block_of(s, n)` 的结束边界要取「**下一个真实存在的编号**」，
   不能写死 `n+1` —— 补缺号时 `n+1` 恰好不存在，边界会一路找到 18 条。

2. **别用 `re.sub` 改 Markdown**。替换串里的反斜杠会被当模板转义，
   本轮一次 `re.sub` 把文件从 383 行撑到 **1145 行**（后续正文全被打散）。
   **用切片 `s[:a] + new + s[b:]` 或 `split/join`**。

3. **bash 会吃掉反引号**。`py -3 -c "...\`npc\`..."` 里的反引号被当命令替换，
   写进文件就变成空字符串（本轮把 `` `npc` `` 写成了 `\`，`NOT_A_NAME` 整个消失）。
   **要写含反引号的 Markdown，用 Write 工具或临时 .py 文件，别塞进 `bash -c` 的双引号里。**

### 正确姿势：超红线就归档，不是硬压缩

`PROJECT_STATUS.md` 超 400 行时的正解是**逐字外迁到 `docs/archive/`**，
主文档留「状态 + 一句话 + 指向 §xx」。**硬压缩会静默丢信息**（同一轮里我丢了第 27 条）。
归档必须做四条核对：① 原文每个非空行都能在归档里查到；② 取回的块与原文逐字相同
（两侧同样 `rstrip('\n')` 再比，否则会因末尾换行差一个字符而误报）；③ 主文档引用断链为 0；
④ 写盘前重取 md5 与读入时一致（防并行会话在中间落盘）。

**归档前的顺序不能反**：先写归档 + 核对通过，**再**替换主文档；核对不过就别动主文档。

### 恢复手段：重放脚本比逐条 Edit 可靠

主文档被改坏时（`re.sub` 事故），`git show HEAD:PROJECT_STATUS.md` 回到基线，
再用**一个临时 .py 脚本**重放本轮全部编辑（每步都带内容断言）。
比开编辑器一条条改安全：断言会告诉你哪条丢了，而肉眼看不出文档已被打散。

### WF-26: 元数据「取行规则」类改动 —— 方向性判据 + 两头同源核对（2026-10-05）

**目标**：改 `build_ship_meta.py` 里「同一 painting 多行 / 同一组多 stats 行」这类**选行规则**时，
既能一次修掉一批卡，又不把另一批卡改坏。判据不是"什么都不能变"，而是
**"每一处变化都必须落到一条只放行正确方向的判据上"**。

**四步（顺序是硬性的）**
1. **只读影响面探针**：先把冲突集数出来（`diag/painting_dup_probe.py`：142 组 / 309 行），
   并让探针跑**候选规则**，打印"改判多少 / 补回多少 / 回退多少"，退出码即结论。
2. **临时区重跑 + 逐字段 diff**：`build_ship_meta.py --write --out .diag/pipeline/meta_afterN/`，
   与正式区比 `条目增删 / 每字段变化数 / 字段变空数`——**变空数必须为 0**（`''`/`-1`/`0`/`？`/
   `{namecode:` 都算空）。
3. **闸门加"方向性判据"，不是加例外名单**：`ship_meta_authority_diff` 的受保护档
   （`source ∈ {painting, suffix}`）每多一类合法改动，就加一条**任何组都能套、反向必拦**的判据
   （`base_fix` / `row_backed` / `dup_row_fix` / `majority_fix`），并给它配反向对照样本
   （`test_meta_gate_proofs.py`，现 26 例）。判据函数必须放**模块级**——闸门里的判据没法测就等于橡皮章。
4. **下游索引做"两头同源核对"**：`gallery_index_diff_check --meta-old A --meta-new B` 要求索引里
   每个变化的值**同时**等于改前与改后的元数据。只核对新值 = 给"索引器自己漂了"开门。

**判据**
- 探针复算的代表行必须与正本 `build_indexes` 实际选中的行**逐组相同**（`stats_majority_probe.py`
  里是硬断言，不一致直接判红）；
- 元数据闸门：`其余 N 处（须为 0）` + `条目集合增删 0` + `仍无源 == 期望值`；
- 索引闸门：白名单外零差异，且无掉船/掉皮肤/丢本船语音；
- 目视：新独立成卡的 16 个皮肤位 `voiceCount` 必须 23~24（语音包早就在 `Output/Audio/CV2/`，
  这类改动**不需要**重跑 `audio` 档）。

**踩坑**
- ⚠️ **别拿"号段更大 = 更新"当 tie-break**：`qiye_dark`(企业→`？？？？？`)、`linghangyuan1_5`
  (超级AI-TC→`？？`)、`unknown5`(构建者→仲裁者) 都是**不同实体复用同一 painting**，
  加 `id` 取大就把它们一起改判了。⇒ 只放行「cv 与 stats 同时从无到有」这一种。
- ⚠️ 众数代表行会选中 `english_name='simulation'` 的行（全表 44 行占位），卡片英文名直接显示
  `simulation` ⇒ 族内还要避开占位名。
- ⚠️ 换入前必查 `git status`：`Output/gallery_v2/index.json` 是**共享产物**，重建它会同时把
  别的会话遗留在 `CG_v2/` 的取证中间图变成 11 张假船卡（本轮顺手把这条改成"跳过并点名打印"）。
- ⚠️ 整档 `derive` 会跑 `deploy_gallery.py` 用正本刷平运行目录 ⇒ 工作树里有**别人未提交**的
  `gallery_src/*` 时不能跑整档，只能手工做「换入 + 重建索引 + 只读 `--check`」。

**涉及文件**：`scripts/build_ship_meta.py`、`scripts/build_gallery_index.py`、
`scripts/diag/{painting_dup_probe,stats_majority_probe,ship_meta_authority_diff,gallery_index_diff_check,test_meta_gate_proofs}.py`。
相关：§56、§82、§95、§101、WF-15、WF-23。

### WF-26 追加（2026-10-05）：跨表「同号配对」信号 —— 说"游戏里没有"之前先做未归属产物清点

**什么时候用**：某个实体在管线里"查不到舰级字段 / 无阵营 / 无语音"，而你打算把它写成"游戏没给"。
本轮就是先写了"这几张 META 卡没有自己的配音"，被用户否证后重查，发现 **2.3MB 的包一直躺在盘上**。

**四步（顺序是硬性的）**
1. **量原始产物集与已归属集的差**：`files/AssetBundles/cue/` 有 950 个 `cv-<号>`，`Output/Audio/CV2/`
   只有 902 ⇒ 48 个包从来没导出。**差集非空就说明"没有"这个结论下早了。**
2. **差集里每个号按四种身份回查全部权威表**：作为皮肤行 id / 作为 `ship_group` / 作为 `stats.id` /
   作为 `ship_data_group.group_type`。⚠️ 已发布的 `inputs/gamecfg/` 只有 8 个文件，**全量证据在
   `.diag/sharecfg_re/lua_json/`（773 张，那是可清理区）** —— 查完必须把结论落进 docs 或补发布脚本，
   不许只留在临时区。
3. **看号段邻居**：META 组是 `970` + 三位系列号，9701 系列在我们表里排到 `970112`，
   于是 `970113` 就是"下一位新 META"——`fleet_tech_ship_class.json` 里直接写着 **`灵敏·META`**。
   号段邻居能告诉你"缺的是哪一格"，而不只是"缺"。
4. **把结论分成三类，别混**：① 数据在、我们的桥走不到（本轮：缺 `ship_skin_template` 一行）；
   ② 数据在我们手上根本没有（要重新拉）；③ 游戏里真没有（要给出反向证据，比如整号段无邻居空位）。

**配对信号本身怎么用**（本轮的修法）：900xxx 段游戏约定 **`ship_data_statistics.id == ship_skin_template.id`**
（`qiye_dark` 两侧都是 900072/900135）。它当两个用途：组查不到 stats 时的**救援**、众数并列时的 **tie-break**。
两条都是单向判据（`pair_rescue` / `pair_tiebreak`），且必须放模块级供反向对照测试跑（`test_meta_gate_proofs.py`）。

**判据**
- **救援集 ≠ 落到元数据**：本轮救援集 53 条，其中 51 条**惰性**（同一 painting 另有被 `painting2skin`
  选中的行）。分档判据是「该 painting 被选中的正是这一行」；探针要给 `--max-gain`（生效条数上限），
  只报总数等于没报。
- 探针必须带**逐条放宽的阴性对照**：`nationality` 那条放宽后 53→53（冗余，只是保险），
  真在裁的是「同名」198→53 与「组内无 stats」111→53 —— 写出来才知道哪条判据在干活。

**踩坑**
- ⚠️ 别把"我们的表里没有"讲成"游戏里没有"。说这句话之前先跑第 1 步的差集，成本 5 秒。
- ⚠️ 判据函数在探针/闸门里**手抄一份**，那条"复算 == 正本"的自检就变橡皮章 ⇒ 抽成
  `pick_stats_row()` 让两边 import（本轮把 `stats_majority_probe` 与 `ship_meta_authority_diff` 都改了）。
- ⚠️ 新增独立成卡会把**借来的语音**一起带过去（新卡显示 33 条其实是本体台词）。
  卡片结构一变，就要顺手查 `src='strip'`（剥后缀借包）的归属是否还合理。

**涉及文件**：`scripts/build_ship_meta.py`、`scripts/diag/meta_idpair_probe.py`、
`scripts/diag/{ship_meta_authority_diff,test_meta_gate_proofs,stats_majority_probe,gallery_cat3_probe}.py`、
`scripts/gallery_buckets.py`。相关：§101、§107、WF-23、WF-15。

### WF-26 追加第二轮（2026-10-05）：桥的起点行缺失 —— 发一张「补桥表」，别改优先级顺序

**什么时候用**：上一节那句"按差集发现原始产物比归属表新"查出实锤之后 ——
某个实体**船行有、包也有，唯独管线起点那一行没有**（本项目：灵敏·META，`ship_data_group`
有 `group_type=970113/nationality=97`、`cv-970113.b` 2.3MB 在盘上，皮肤表 2865 行里没有这一组）。

**四步**
1. **先找"表里已有的另一列"，不要发明命名规则**。她的自机立绘资源名不需要猜：
   她的**剧情皮肤行**里 `prefab = 'lingmin_alter'` 就是答案，且 `Output/Paintings_v2/lingmin_alter.png` 在盘上。
2. **连接键的强度全押在"唯一性"上**：`fleet_tech_ship_class.name` ↔ 皮肤行 `name`（清洗后精确相等）
   ⇒ 候选 **必须恰好 1 条**；0 条=没有出处，≥2 条=同名不同实体，两种一律不接管，不许"挑一条看起来更对的"。
   再加三条反向对照进发布脚本自检：已有皮肤行的组不得进补表、补表指向的 painting 不得已是别行的 painting、
   包不在 cue 里就不进补表。
3. **消费侧一次补齐三处，缺一个就是半截桥**：① 发布脚本 + 台账条目；② 元数据侧的查找优先级
   —— **表命中之后、继续剥后缀之前**（先剥后缀就会把 META 实体并进本体船，那正是 bug 本身）；
   ③ 取包侧 —— 同一候选名上**先认桥再认行**，并给来源打标（`src='bridge'`），
   这样 `借同船别人的包` 那一类降级会自动消失而不是被掩盖。
4. **闸门加一条允许"去错贴值"的方向判据**：这类改动里 `en`/`rarity`/`voice_actor` **会变空**，
   因为那些值原本是从本体船错贴过来的（`灵敏·META` 去掉「·META」就是本体：北方联合/精锐/花井美春）。
   ⇒ 判据必须显式写明"允许变空"，同时拦住反方向（META → 本体）与无出处接管（`bridge_fix`）。

**踩坑**
- ⚠️ **`open(台账,'w')` 一执行就把文件截成 0 字节**。把"读旧台账并合并"写成 `json.dump(merge_ledger(e), f)`
  的参数 ⇒ 打开时旧内容已经没了。本轮真的清空过 `inputs/gamecfg/MANIFEST.json`，靠它入库才恢复。
  ⇒ 规则：**先算完新对象，再开写句柄**；凡是"读同一个文件再写同一个文件"，顺序是硬性的。
- ⚠️ **按中文名兜底在这类实体上反向有害**：维基/本体兜底命中的是**本体船**，会把阵营/稀有度/CV 全部贴错。
  宁可留空，并把它写成"待游戏内核实"的显式声明。
- ⚠️ 新加的 HTTP 判据报 404 而文件在盘上：画廊页在 `gallery_v2/`、音频在服务器根的 `Audio/`，
  已有判据用的是 `{BASE}/../{f}`。**判据写错就改判据，不要改产品去迁就判据。**
- ⚠️ **新增来源档必须同时加进闸门的"受保护档"名单**。本轮第一版把补桥条目的 `source` 定成 `bridge`，
  而闸门 `PROTECTED` 只列 `painting/suffix` ⇒ 第二次"往补桥条目里填值"的改动**闸门一个字都没看**，
  打印出来是"字段改动 0 处"——**这是假绿灯最体面的一种**：闸门没错，是它的地盘画小了。
  ⇒ 加档位时同批改 `PROTECTED` 与方向判据，并给新子句配反向对照。
- ⚠️ **人工裁定的值要写进发布脚本，不要只写进产物**：`inputs/*/*.json` 不入库（体积/可再生），
  只改产物会在下一次重发布时被静默抹掉。本项目落在 48 号的 `CONFIRMED` 表 + `confirmed_via` 出处串，
  并让发布脚本的自检要求"填了值就必须带出处"。
- ⚠️ 补桥条目里 `SR` 这类**玩家口径的档位词**要先翻译成码表值再填（本项目 `SR`=码 4=精锐，
  `5` 才是 SSR/超稀有），并把这句翻译写进 `confirmed_via`，否则下一个会话会当成 5。

**涉及文件**：`tools/sharecfg_re/48_publish_meta_group_bridge.py`、`scripts/build_ship_meta.py`、
`scripts/extract_cv_voice.py`、`scripts/build_gallery_index.py`、
`scripts/diag/{ship_meta_authority_diff,test_meta_gate_proofs,gallery_cat3_probe}.py`。
相关：§107、**§108**、WF-26、WF-23、WF-15。

#### WF-23 追加（2026-10-05）：配置表链进台子 —— 步骤重排为五步主线

`preflight → pull →` **`cfg.decrypt → cfg.lua → cfg.disk → cfg.publish`** `→ deps → meta → …`
（`STEPS` 重排：1 接模拟器 / 2 同步配置表 / 3 重新导出 / 4 看图对比 / 5 签字换入；
面板的步骤节点与 `stagesOf()` 本来就是从 `STEPS` 动态生成的，所以只改了文案与键位 `1-4`→`1-5`）。

| 档 | 干什么 | 档 | 判据 |
|---|---|---|---|
| `cfg.decrypt` | 34 号解 `scripts32/64` | staged | **逐文件**：该文件段内有 UnityPy 复验成功 + 产物 mtime 不早于输入包 |
| `cfg.lua` | 35 `--limit 0` + 41 `--all --yes` | staged | `lua_json ≥700` 张 + 41 号 rc=0 + 落盘比源包新 |
| `cfg.disk` | 37 `--all --yes` 解 32 张 sharecfgdata | staged | 32 张齐 + **报皮肤行新增数**写 `.diag/pipeline/cfg_delta.json` |
| `cfg.publish` | 42/45/46/47 发布 `inputs/gamecfg` | **live** | 未签字只跑各脚本 `--check`；签字后 4 个全绿 + `check_inputs gamecfg` 绿 |

**两条设计上的硬要求**
1. `preflight` 现在带**新鲜度判据**：`max(mtime of sharecfgdata|scripts32|scripts64)` 的日期
   晚于台账 `landed_at` ⇒ **判红**并点名要跑 cfg 四档。sha256 绿只等于"文件没被改过"，
   不等于"文件跟游戏一样"——这条就是把那个假绿灯堵死的。
2. `cfg.disk` 的新增行数会作为 `--expect-added` 传给 `ship_meta_authority_diff`：
   闸门原来硬要求"条目集合增删为 0"，那等于**把"游戏出新角色"本身判成回退**，
   每次真更新都必红。现在丢失仍零容忍，新增上限取自差分实测。

**踩坑**：见 §104（34 号丢尾字节 ⇒ 下游 LZMA 报 corrupt；判据整块 grep 成功字样 ⇒ 假绿灯）。
**唯一留给人的一步**：在游戏里把更新下载下来（`cfg.disk` 报"新增 0 行"时不要往下跑）。

---

### WF-27: 多层资产的「谁画在谁上面」——取引擎自己的层级，别按名字猜（2026-10-05）

**适用**：一个视觉产物由 N 个同构子资产叠出来（Spine 多 SkeletonGraphic 层、Unity UI 多层、
PSD/SVG 图层、前端多层 canvas），出现「某个部件整块看不见 / 被另一块盖住 / 顺序看起来不对」，
或要把层序换成另一套权威来源。

**五步**：

1. **先证"是没渲染，还是被盖住"**——这一步决定后面全部方向，别跳。
   做法：逐层受控隐藏（藏一层拍一张），**不要**只看"隐藏全部"的底片。
   判据：某一层单独隐藏后目标内容**出现** ⇒ 是遮挡，不是渲染缺失。
   ⚠️ 用共享开关字段（如 `L.hidden`）做隐藏时，先确认没有别的逻辑（取景、二次构图）
   会把它写回去 —— 本项目就有一条 `pixelFit` 收尾无条件 `hidden=false`，
   专门冲掉诊断工具的设置，导致连续两轮拿它的输出当证据（§110）。
2. **去引擎里取权威顺序，不要给启发式打补丁**。
   Unity UI = RectTransform 层级 **DFS 先序**（父先于子、子按 `m_Children` 顺序），先绘制者在下面。
   取到之后**必须和一个已知正确的产物对一下**（本项目 = 官方立绘 / 另一条渲染路径的输出）。
3. **改代码前先在运行时端到端验一次**：把内存里的层数组原地重排，截图看对不对。
   成本 5 分钟，能挡掉"判据对了但顺序理解反了"这类整轮白工。
4. **影响面用全库扫描定量，不用抽样**：把现行判据（那份名字启发式）**原样抄进扫描脚本**，
   逐目录比对"现行序 vs 真实序"，打印差异清单。
   ⚠️ 抄的那份要和正本同源（`import` 同一个函数），否则扫描在量一个不存在的东西。
5. **零回退闸门放在数据层，不放在像素层**：比对改动前后的**生成物里的顺序字段**
   （本项目 = `index.json` 的 `spine.parts` 数组，脚本 `scripts/diag/spine_index_parts_diff.py`，
   含"除这个字段之外两份索引必须逐字相同"这条防夹带断言）。
   像素比对当不了闸门，除非先量出噪声底：本项目 `pixelFit` 的机位取决于
   "那一帧哪些贴图已上传"，**同一份代码连拍两次**差 0.13%~2.59% —— 比多数改动还大。
   要用人眼看图时，用 `spine_dialog_fingerprint.py --selfcheck` 先定噪声底，再 `--cmp` 比改动。

**判据（本轮实际用的三条，缺一不算修完）**：
- 数据层：变化目录集合 == 扫描预测的集合（本轮样本 = 仅 `tianjinfeng_2`）；
- 画面：目标内容在**症状复现的那个相位**上出现，且与权威参照逐位对得上；
- 反向：没有可剔/没有背景层的皮肤，行为一字不变（按钮不出现、取景数值不变）。

**踩坑**：
- 「反转层序数组后画面没变」**不能**否证遮挡 —— 若在内容本来就散开的相位上做，谁压谁都看不出（§109→§110）。
- 「另一条渲染路径看起来正常」**不能**否证层序错 —— 两条路径可能渲的是不同相位
  （本项目 CG 页渲 setup pose，房间由另一层画，所以碰巧对）。
- 名字启发式的失败模式是**后缀带数字**（`2B2` 不 endsWith `B`）。写后缀分桶时先问一句
  「这个命名空间里有没有 `B2`/`B3`/`T2`」。
- 权威顺序的**来源**要一路传到产物：`skel_layers()` 读到 → `parts.json` 落字段 → 索引按它排。
  中间任何一环"读不到就猜"都必须在产物里点名，不许静默回落。

**涉及文件**：`scripts/compose_paintings_v2.py`、`scripts/extract_spine_v2.py`、
`scripts/build_gallery_index.py`、`gallery_src/index.html`；
`scripts/diag/spine_render_order_scan.py`、`spine_index_parts_diff.py`、`spine_dialog_fingerprint.py`。
相关：§110、§109、§105、§58、WF-15（换入闸门）、WF-16（前端回归）。

### WF-28: 磁盘「能不能删」必须三段分问，去重上限不许当结论报（2026-10-06）

**适用**：仓库膨胀到几十 GB 后被问"这两个文件夹是不是重复了 / 这个备份目录能不能清 / 还有没有优化空间"；
或要给"删某批资产"找证据。也适用于换入前的**备份闸**设计。

**四步（谁也不替谁，缺一段就得不出"能删"）**：

1. **体量**：逐顶层目录数文件数与字节，别用目录名推断角色。
   `py -3 scripts/diag/check_disk_footprint.py`（纯 stat，分钟级）。
   判据：能一句话答出"全仓多少 GB、被哪 3 个目录吃掉多少"，且数字带口径（GiB/GB 差 7%）。
2. **角色（谁写它、谁读它）**：grep 管线与前端，不猜。
   - 写向：`grep -n "writes=" scripts/update_pipeline.py` + `STAGES` 全表搜目标目录名 —— **0 命中就是不在当前管线里**。
   - 消费方：`grep -o "Audio/[A-Za-z0-9_]*" Output/gallery_v2/index.js`、`grep -c -i bgm Output/gallery_v2/index.json`、`grep -rn "Raw/" gallery_src/`。
   - 拉取落点看 UI/脚本原文的 `writes`，不是看哪个目录"像源"。
   判据：**零引用**要说"引用 0 处"并给出被 grep 的文件，不能说"应该没人用"。
3. **可再生性**：产物能否由「git 里的脚本 + 盘上源包」重跑出来。
   ⚠️ **`Output/` 整个在 `.gitignore` 里** ⇒ git 只兜得住脚本，兜不住产物字节。
   所以换入前的那一版旧字节**只存在于 `Output/_OLD_bak/`**，删了就没了；
   "重跑旧脚本能再生"是有条件的（源包会被后续 pull 覆盖），不得当成无条件安全。
   现成机制是 `asset_ledger.py`（§78）：`已还原 = 产物存在 且 台账源包大小/md5 与盘上一致`。
   判据：`asset_ledger.py status` 打印的「当前可安全删除 X 个 / Y GB」——
   **产物溯源记录数**（本项目曾长期停在 14 条 ⇒ 只能删 0.02 GB）才是真闸门，没记账就没得删。
4. **重复实证（两级）**：先按 `(size, nlink)` 分组算**嫌疑上限**（纯 stat），
   再对嫌疑组走 **前 1 MB 采样哈希 → 全文件 md5** 两级确认，`--confirm` 一条旗标。
   判据：**只有第二级的数字能写进结论**。本项目实测虚高两个极端：
   `Output/Audio` 嫌疑 1.90 GB → 真重复 **0.09 GB**（21 倍）；
   `files/AssetBundles` 嫌疑 0.73 GB → 真重复 **0.00 GB（0 组）**（92,679 个包两两互不相同）。
   全仓实证重复 ≈1.3 GB / 84 GB = **1.5%** ⇒ 去重类问题基本都是"看着像"。

**备份闸的判据（✅ 已落地 2026-10-06，形状可复制到任何"直写正式区"的导出脚本）**：
换入必须**逐文件**在覆写前取走前身字节，而不是"目录里有个备份"。
- ⚠️ **不能用"备份目录非空"当判据**：纯新增（如 4488 → 4500 那 12 张）**没有前身可备份**，
  空目录是正确行为（§80 的 `pipeline_20261001_2248/` 就是这种），拿非空当闸会把合法换入拦死。
- **备份范围 = 本次覆写范围**，不是"整个目录拍一份"：`extract_spine_v2.py --parts-only` 只写 `parts.json`
  ⇒ 只取那一份（每皮肤几十 KB）；整批重提取会连 skel/atlas/png 一起重写 ⇒ 整目录现有文件全取。
  这样"要备份多少"由脚本自己按写向决定，不留给操作者判断 ⇒ 没有例外名单。
- 正解四道（`painting_swap_in.py` 早就这么写，新闸门照它抄）：目标 `nlink==1` →
  **备份与原文件 md5 全等**（不等就抛错，什么都不写）→ 换入后与临时渲染 md5 全等 → 全目录快照。
- 落点要**当场声明**：写向在 `Output/` 之下而没给 `--bak` ⇒ 直接 `exit 2`，并打印三种补救命令。
  写临时区（`.diag/pipeline/`）不拦 —— 正式区还没动。
- ⚠️ **拒绝路径必须真的非零退出**：`if __name__ == '__main__': main()` 会**丢掉返回值**，
  于是 `[FAIL]` 打成乱码一样没人看、上层 judge 只看退出码就把"什么都没写"当成通过。
  ⇒ 一律写 `sys.exit(main())`。（本项目第 N 次撞这个坑，这次撞在自己的新闸门上。）
- ⚠️ **报错文案里给的补救命令，不许指向一条没有备份的直写正式区路径**：本轮的缺口正是
  `build_gallery_index.py` 引导人跑 `--parts-only`（默认写向 = `Output/Spine_v2`）造成的。
  引导文案属于闸门的一部分，改脚本时要一起改。

**踩坑记录**：
- "同尺寸就是重复"是错的，且**错的数量级足以误导决策**（见第 4 步两个实测值）。
- 按**文件名**配对备份↔线上也是错的：`l2d_motion_pre_swap` 里 268 个"与线上相同"全是跨模型同名假配对。
  要判"能不能删这一份"，得比**完整相对路径**；只能按名字时，结论写成"待按路径重证"。
- 省空间的大头往往不是重复，而是**没人读的大产物导出**：本项目 `Output/Audio/BGM/` 536 个 wav 独占 12.6 GB、
  全库零引用（前端/index.json 均 0 命中）；另有 ~9 GB 源包类目（dorm3d/island/ui/originsource/char）从未被任何环节处理。
  这类处置要的是"转格式 / 归档 / 删了重导"的**决策**，不是去重。
- `PROJECT_STATUS.md` 里的历史体量数字会过期（本轮就有一条 26.6 GB / 86,890 文件停在 09 月），
  盘点时**就地改数字**，不要再追加一条新口径。

**按类目清源包（`prune-category`）的四条硬要求**：
1. **删除与登记同一次落**：`mumu_sync` 比的是"设备路径+大小 vs 本地目录树"，删了不写
   `ledger/pruned.json` ⇒ 下次 diff 把整批报成**新增**、白下一遍（§78 立台账就是为了这一条）。
2. **删前先过已还原产物的传递依赖闭包**（`dependency_manifest.json`，从有产物的类目根 BFS）。
   ⚠️ 只看第一层 deps 会漏：立绘根常只挂 `_tex`，公共图集/材质在第二三层。
   闸门必须**自证是活的**——拿一个承重类目跑对照（`--cat painting` 应全拦、`artresource` 应拦下带深链的若干）。
3. **每个类目的"待删数"要和递归文件数对账**：`dorm3d` 第一层 0 个文件、5,989 个包全埋在子目录里，
   第一版按 `os.listdir` 只扫一层 ⇒ 报"待删 0 个"却一声不响，3.5 GB 静默放过。
4. **两套相对路径口径别混**：依赖表用 `painting/xxx`（AB 相对），`pruned.json`/`mumu_sync` 用
   `AssetBundles/dorm3d/a/b`（同步根是 `files/`）。登记键写错前缀 = **看起来登记成功但永不生效**。
   验证登记真的生效（不连设备）：进程内 `import mumu_sync`，喂合成 `r_files` 做三分对照——
   同尺寸 ⇒ 归档；大小 +1 ⇒ 真新版本要重拉；未登记的承重包 ⇒ 仍要拉（阴性对照）。
   ⚠️ 已知缺口：没有 `--revive`，想拉回被删类目**必须先撤销 `pruned.json` 里的对应条目**，
   否则 `--only ui --apply` 会把它们全判成"已归档"而静默跳过（撤销命令见 §111 第 5 节）。
   **✅ 2026-10-07 首次真执行**（靶子 = `dorm3d` 5,989 条），带护栏的步骤见本节末「撤销归档闸」——
   §111 那条手工一行流**别照抄**：它没有断言、没有并发写闸门、也没有回归判据。

**有损转码这一档（第 3 步里"能再生"的那类才允许走；本轮 = BGM 12.6 GB → 1.06 GB）**：
上限是**格式**给的，不是去重给的 —— 零引用的大产物导出（背景音乐 / 未压缩音频）往往一挡就回收九成。
**别把"无损"说成"省不下"**：实测同一批 19.1 小时音乐三档 = wav 11.75 GB / **FLAC 7.51 GB（省 36.1%）**
/ opus 128k 1.06 GB（省 91.0%）。FLAC 在 Chrome/Edge 原生可播，所以"要无损"也有中间档可选，
只是收益小得多 —— 报数给用户时三档一起报，别只报有损那一档。
五步，顺序不能换：
1. **先确认它真的没人消费**（grep 索引与前端，0 命中），否则转码=改内容，要走对照验收而不是这条。
2. **跟着现有格式走，不要引入第二条播放路径**：`Audio/CV2/*.ogg` 实测 `codec_name=opus` +
   `new Audio(path)` ⇒ BGM 也转 opus/ogg，前端零新依赖。选格式前先量源：536 首 / 44.1kHz 立体声 /
   **19.1 小时**，opus 128k 预估 1.0 GB（实测 1.06 GB，误差 3%）。
3. **逐份校验再谈删除**，三条硬判据任一不过该文件判失败：产物 >1 KB、
   `ffprobe` 时长与源差 **<0.25 s**、源 md5 落台账。工具**不删源文件** —— 删除是另一步、要另放行。
4. **台账必须入库**（`ledger/bgm_transcode.json`，不放 `.diag`）：删掉 wav 之后，
   它是唯一能逐份证明"这个 ogg 当时由那个 md5 的 wav 转出来"的东西。
   派生产物要**自包含**（时长/中文名烘进 `bgm.json`），这样临时区被清也不破坏页面。
5. **删源前先把产物换进最终位置**（`BGM_ogg/` → `BGM/`），别让引用路径长期指向临时名。
   实操顺序要留回滚：`BGM/`(源) → 改名 `_BGM_wav_to_delete/` → 产物目录顶上 `BGM/` →
   重建索引 → **跑一遍真播放验收** → 绿了才真删改名那份。

**无损档（FLAC）另有三条专属坑**（2026-10-06 用户从 opus 改选 FLAC 时全踩到）：
- **MIME**：Python `mimetypes` 给 `.flac` 的是遗留的 `audio/x-flac`，Chrome
  `canPlayType('audio/x-flac')` 返回**空串**（`audio/flac` 才是 "probably"）
  ⇒ 服务器要钉 `extensions_map`。**换格式必须重跑播放验收**，"文件在、路径对"不等于能播。
- **无损要回环证明**，不能靠格式名字：把产物与源**都解成裸 PCM** 再比 md5
  （`ffmpeg -i X -f s16le`）。⚠️ 别比"解回来的 .wav 整文件"——重新封装的 wav 头与源不同，
  样本相同而文件不同，会把真无损判成 7/7 失败。
- **删源前的总闸**：`--verify-only` 逐条重算产物 md5 对台账 + 整条解到 null
  （FLAC 每帧带 CRC、STREAMINFO 存整条原始 MD5，坏帧只在全解码时露）。
  台账**按 codec 分文件**、续跑判据**含 codec**，否则新档那轮会覆盖旧档溯源或整批假跳过。

**踩坑记录**：
- 有损转码的**唯一硬证据是"能播 + 时长对"**，不是"文件变小了"。浏览器侧还要单独验一次
  （`bgm_page_probe.py`：进度在走、拖到 50% 真跳、标题跟随、筛选与搜索）——
  见 WF-16 追加第 3 条：**服务器不应答 `Range` 时音频"能响但不可拖"，`duration` 恒 `Infinity`**。
- 转码台账的可续跑判据要**含源 md5**，不能只看产物存在：产物存在但源换了版本时必须重转。

**涉及文件**：新增 `scripts/diag/check_disk_footprint.py`；`scripts/asset_ledger.py`
（`prune-category` / `dep_closure()` / `pruned.json` 登记）、`scripts/mumu_sync.py:247-270`（`load_pruned` / `split_archived`）；
`scripts/export_assets.py`（Raw 的写方）、`scripts/organize.py`（Raw 的唯一读者，已写未跑）；
`scripts/pipeline_panel.py:2418`、`scripts/update_pipeline.py` `STAGES`（拉取落点原文）；
`scripts/extract_spine_v2.py`、`scripts/diag/painting_swap_in.py`（备份闸正反两例）、
`scripts/build_gallery_index.py`、`scripts/run_v2_full.py`（引导文案与批调用）。取证全过程 **§111**。
相关：WF-15（第 9 步备份换入）、WF-16（回归六件套）、§78（台账）、§46（备份瘦身先例）、§110。

#### 撤销归档闸拉回被删类目（2026-10-07 首次真执行，靶子 = `dorm3d` 5,989 条 / 3.44 GB）

上面第 4 条那个"没有 `--revive`"的缺口，真要用时只有一条路：**撤台账登记**。§111 第 5 节留的手工一行流
能跑，但它把三件必须的事都省了（断言 / 并发闸门 / 回归判据）。按下面五步走，顺序不能换：

1. **先跑只读 `diff --only <类目>`，让 `已归档` 那行同时当"版本漂移体检"**：`split_archived()` 判归档的
   条件是 `pruned[路径] == 设备上的大小`，所以 **`archived` 计数 = 设备上与删除时逐字节同尺寸的包数**。
   `archived + added == 清单全量` 且 `added == 0` ⇒ 设备侧一个包都没更新过，重拉的 md5 校验才有希望通过；
   一旦有包落进 `added`，那是**真版本漂移**，先停下核对，不要往下拉。
2. **验 HEAD == 工作区**（`git diff --stat HEAD -- ledger/pruned.json` 必须为空）再动手。台账是 git 追踪文件，
   HEAD 那份就是永久回滚锚点（`git checkout -- ledger/pruned.json` 一键关闸）；另存一份到 `.diag/` 只为当场对账。
   写盘前**重取原文件 sha256 与读入时比对**——共享工作树里别的会话可能正在写它。
3. **只撤一个前缀，且断言写在代码里、不靠眼睛**：撤前逐前缀计数并钉死（本次
   `21,286 = dorm3d 5,989 + island 7,755 + char 3,264 + ui 4,278`），撤后必须
   `被删键数 == 该前缀条数` 且 `其余每一条 value 全等`；格式要跟原文件一致（这份是
   `ensure_ascii=False` + `separators=(',',':')` 单行，用默认分隔符会炸出整文件重写）。
   落盘走 临时文件 → 回读断言 → `os.replace`。
4. **进程内三分对照**（不连设备，`import mumu_sync` 喂合成 `r_files` 调 `split_archived`）：
   目标类目同尺寸 ⇒ `KEEP`（闸开了）；**`island`/`char`/`ui` 同尺寸 ⇒ 仍 `ARCH`**（阴性对照，证明没多放闸）；
   两类各自 size+1 ⇒ 都 `KEEP`（真新版本仍能拉）。少了第二条就是"我以为只撤了一个前缀"。
5. **判据 = 重跑第 1 步那条只读 diff**：`已归档` 整行消失、`新增` 等于设备侧真实存量。

⚠️ **窗口期副作用（这条最容易忘）**：闸门一开，任何**不带 `--only` 的** `sync --apply`
（含资产更新台第 1 档 `pull`）就会开始把这批包当新增拉下来（dorm3d = 3.44 GB）。⇒ 窗口要短，
期间别跑控制台拉取档；后续判据若判死，立刻按第 2 步关闸。

**按依赖闭包定向拉一小撮包（不重开归档闸）**：只想拉某个房间/某个角色的传递依赖时，
用 `scripts/diag/mumu_pull_closure.py`（`--seed <AB相对路径>` × N + `--include/--exclude` 前缀 + `--dry`），
它直接 `adb pull`、**不读也不写 `pruned.json`** ⇒ 归档闸保持关闭。
起点清单来自 `Output/dependency_manifest.json` 的 BFS（跳过 `custom_builtin`）。
**三类结果必须分开计，不许混成一个"成功"**：`md5 全等` / `不符` / **幻影包**（设备侧 `stat=0`，
游戏更新自己删的，台账里还挂着登记）/ `无校验依据`（清单里没这条 ⇒ 只能说"拉到了"不能说"验过了"）/ `拉失败`。
实测：房间 1 闭包 464 → 过滤后 455 → 待拉 453 / 89.9 MB，**453/453 md5 全等**，91.3 秒（5.0 文件/秒）。
⚠️ 拉完台账仍说这批"已归档"——这是**有意的不一致**：台账记的是"用户裁定不留"，
不是"盘上没有"；要恢复一致就按上面五步把登记撤掉，或反过来把这批重新登记。

**踩坑记录**：
- **`--only` 只能选目录、选不到单个文件**：`set_only()` 无论传什么都补一个 `/`（`mumu_sync.py:291`），
  传 `AssetBundles/dorm3d/character/tianlangxing_db/res/tianlangxing_noshoes` 会变成 `.../noshoes/`
  ⇒ `wanted()` 的前缀匹配对**那个文件本身**恒为假。要单包粒度只能直接用 `mumu_sync.run(['pull','-a',远,近])`。
  深前缀选目录是好用的：`--only <...>/prefabs,<...>/component` 实测精确命中 15 个文件 / 606 KB。
- **"两份清单差 N 条"要先定方向、再定性**：`pruned.json` 的键带 `AssetBundles/` 前缀、
  `files/hashes-dorm.csv` 不带，不归一直接比会报成"5,989 条全不同"（本次差点这么判）。归一后是
  `csv ⊂ pruned`，差 8 条，逐个 `adb stat` 得 **0** ⇒ 是**游戏自己更新掉了这 8 个包**，不是台账记错。
  判据：这类落差必须用设备侧实测区分"我没登记对"和"设备侧真没有"，光比两份盘上清单永远分不出来。
- **台账独有项不会出现在 diff 的任何一行**：设备上既没有它、本地也没有 ⇒ `archived` 和 `新增` 都不含它。
  所以"台账 5,989 / diff 5,981"这种落差**本身是信号**，不是噪声；可复原上限要按 diff 那个数报。
- `--only` 的横幅打印按 `x.split('/')[1]` 取类目名，深前缀会显示成重复的 `dorm3d, dorm3d`——纯显示，别误判成过滤器生效了两次。

**涉及文件**：`ledger/pruned.json`（唯一副本、已入库）、当场备份 `.diag/pruned_backup_step1_20261007/`、
`scripts/mumu_sync.py:247-295`（`load_pruned` / `split_archived` / `wanted` / `set_only`）、
`files/hashes-dorm.csv`（5,981 行逐包 md5，对可复原集是完备的）、`scripts/asset_ledger.py`（`prune-category` 是登记写方）。
取证与数字 **`docs/archive/2026-10-07_3D宿舍复刻可行性取证.md` 追加一节**。

---

### WF-29: 改「渲染政策函数」（合成算子 / 画布口径 / 取景规则）怎么验到能放心全量（2026-10-06）

适用：改动不是"某个皮肤的数据读错了"，而是**每一张图都要走的那段算术本身错了**。
这类改动没有"对照组逐像素不变"可用——因为**所有图都该变**，传统零回退闸门直接失效。

#### 第 0 步：先把政策收敛成正本里的**一个函数**，否则后面全做不了

`compose_paintings_v2.canvas_frame()`（画布口径）与 `.over()`（合成算子）。
不是为了整洁，是为了下一步：探针只要**临时替换这两个函数**就能渲出"旧行为"，
不必复刻任何仿射/取整算术。

> 反面教训（同一轮里连犯三次）：探针自己重写一遍 `py = round(ch - (wy+wh))`，
> 结果 `ch` 用了旧口径的值 → 与正本产物不一致 → 虚报 32 万"实心区变化"。
> **探针复刻被测算术 = 造出第二份实现，两份必然漂移**（§85、§110 同一类错）。

#### 第 1 步：让探针自证保真，两条都要

- **旧侧**：用退役实现渲出来必须与**在盘产物逐字节相同**。不过这条，闸门在比空气。
  （本轮 `baixue` 一度 `旧=盘❌`，查出来是退役规则的**输入集**也不同——旧口径对所有
  RectTransform 取 max，新口径是"落笔框 ∪ rect 框"，探针喂错了输入。退役实现要连输入一起退役。）
- **新侧**：探针算出的"新"必须与**正本产物逐字节相同**，否则你验的是自己想象的新实现。
  这条上一版缺，`aersasi_3` 的行号算歪没被发现。

#### 第 2 步：两个改动必须能**分开量**

`--f1only`（只换画布、两版都用退役算子）。不能分开会怎样：我第一版普查把
"找回像素"报成 **96% / 约 4320 张**，因为那一列把 F2 让极淡像素复活（源 alpha≈50
从"平方成 0"变成留下来）和 F1 找回被裁内容混成了一谈。分开重测后真实值是 **2.0% / ≈90 张**。

#### 第 3 步：对齐用**正本记录的取景事实**，不要用图像配准

`compose()` 落 `LAST_CANVAS[bundle] = {origin, canvas, crop}`，公共框里的平移就是
`行差 = (ch_n + oy_n - crop_n) - (ch_o + oy_o - crop_o)`、`列差 = ox_o - ox_n`，精确整数。

> 配准版（`painting_fix_regression.py`）在这条上连踩三次：行列写反 → 锚点被一个杂点带偏
> 1 行 → 精搜的施加方向与打分方向反号。每次都表现为"几百万实心区变化"的假回退。
> 结论：**能拿到精确原点就别去猜像素**；配准版保留作反例。

#### 判据（红 = 不许换入）

| 判据 | 为什么是它 |
|---|---|
| 实心区（离任何半透明像素 ≥2px）可见变化 `|Δ|≥12` 必须 **0** | 政策改动的正当影响域只有柔边；实心区变了才是毁图 |
| 不透明(≥250) 退化成半透明 必须 **0** | 抓"画布缩小反而新裁内容"这类反向伤害（`baixue` 2427→2426 就是这么抓到的） |
| 内容丢失 必须 **0**（只许找回） | 新画布按构造是旧画布的超集，一旦不成立说明口径写错了 |
| 全库贴脸/门控类判定翻转 **逐条点名 + 每条配叠/不叠对照图** | 换测量口径 = 换分类器；只在带标签样本上验等于没验（§48 老教训） |

#### 第 4 步：抽样定影响面 → 全量脱离跑 → 换入四道检查

- 影响面用**分层抽样**给置信数（本轮 stride 抽 300 张 ≈ 20 分钟），不要拿"筛候选"的数当影响面——
  候选筛子本身会漏（负侧筛法漏掉了正方向裁切）。
- 全量必须脱离宿主（`.diag/rerun.bat` + `Start-Process -WindowStyle Hidden`），
  并落**完成哨兵**（`STATIC-DONE`）。`Start-Process -ArgumentList` 对含空格路径的引号不可靠
  （本仓库根就是 `D:\Azur Lane Assets`），改成 .bat 自己管引号、PowerShell 只负责脱离。
- 换入走 `diag/painting_swap_in.py`（四道检查 + 断硬链 + 增量重建缩略图），
  再 `build_gallery_index.py` + `gallery_index_diff_check`；本轮只动图像字节 ⇒
  **索引应当逐字节相同**，这本身就是"没顺手改到元数据"的证据。

#### 踩坑记录

- **否证也要入库**：`FACE_MAD_MAX` 抬到 40 能保住 `xinzexi_h`，但会把 `yunlong_3`
  的全身正面图判成"不叠"、发一张后脑勺出去（**§114**）。写进常量注释，防下次再试。
- **代理指标会自我强化**：第一版普查的 96% 看起来很"有发现"，实际是两件事混在一起的假信号。
  判据必须能单独开关每一项改动。
- **改动的正当影响域要能证明，不能只声明**："只碰柔边"这句话的正确形式是
  `两版 alpha∈{0,255} 的像素逐位相同` 这个可测命题，不是形容词。

**涉及文件**：`scripts/compose_paintings_v2.py`（`canvas_frame` / `over` / `LAST_CANVAS`）、
`scripts/run_v2_full.py`（`--out/--redo/--limit/--manifest`）、
`scripts/diag/painting_fix_gate.py`（本 WF 的闸门实现）、
`painting_canvas_extent_scan` / `painting_offcanvas_content` / `painting_alpha_blast_radius` /
`face_gate_flip_scan` / `face_overlay_cmp` / `painting_swap_in`。
相关：**§114**（本轮取证全过程）、WF-15（备份换入 runbook）、WF-27（层序取引擎层级）、
§48（判据演进必须配带标签回归集）、§85（两份语义必然漂移）。

---

### WF-30: 给画廊加一个「带权威命名的资产浏览子页」（数据 json + 页面 + 部署清单 + CDP 探针）

**日期**: 2026-10-07
**目标**: 把一类"已经导出、但没人消费"的资产（本轮是 `Output/Raw/` 的 1,897 张背景图）
变成能看、能搜、能回指到配置表出处的画廊子页，且**中文名是可核对的事实而不是猜的**。
**适用场景**: 用户说"这堆图/表能不能做个页面看"、"给它加个中文名"、"背景/场景/图鉴类资产想留档"。
不适用于 Live2D/Spine 那种要运行时渲染的页（那些走 WF-16 与对应技能）。

#### 步骤（顺序是硬的，每步都有"不绿就不许进下一步"的判据）

1. **先量"名字取不取得到"，再决定做不做页面**。检索面要写死成**字段整值相等**：
   某表的背景语义字段（`*_bg` / `*background*` / `pic` / `illustration` / `login_static` / `scene` /
   `image` / `banner`）整值 == 资产文件名，中文标签取同一行的 `name`/`title`。
   **判据**：报出"有引用的资产数 / 其中那行真带中文名的资产数"两个数，别只报一个百分比。
   **踩坑**：`icon` / `battle_character` / `prefab` / `ani_*` / `*suffix` 这类字段也可能装资源名，
   但语义不是"这张图用在哪"，一律排除；本轮为 15 张图放宽过一次，判否后收回。
   **表拿不到时先问"还有没有第二条源"**，而不是直接放弃或开始猜：横幅类图会把中文名**烤在像素里**
   （`*_tip` 那一族，见 §116）⇒ OCR 能取，但要三条硬要求：① 提取规则用**版式锚点/模板位**而不是引号
   （装饰引号是美术字形，OCR 认不出来）；② **双路径**——OCR + 放大目视定稿，并断言两者字符重合度有地板，
   字典打错字和 OCR 漂移都会红；③ **没核过的字段不发布**（同批读到的舰名 6 条里 3 条在权威表查不到 ⇒ 不进产物）。
   第二条源在页面上**单列一档**，不与表引用混；两源冲突时的优先级若在当前数据上从未被触发，
   就只打印观察量、**不要写成一条 ✅ 断言**（空转的判据比没有更坏）。
2. **权威输入落 `inputs/`，配 `MANIFEST.json` 台账**，脚本**不读 `.diag/`**。
   发布器照 `tools/sharecfg_re/48_publish_meta_group_bridge.py` 的形状写：
   断言不全过就 `exit 1` 且**不写文件**；二进制写产物（文本模式在 Windows 会把 `n` 变 CRLF，台账哈希对不上）。
   跑完必须 `py -3 scripts/diag/check_inputs.py` 绿。
3. **建索引脚本**：三档口径（确定 / 推断 / 无）写进产物，每条带 `src`（表/字段/行标识）；
   断言里必须有一条**"页面上不许出现查不到的名字"**（本轮：系列名必须逐字出现在该图证据里，
   否则把那条出处补进证据，而不是把断言放宽）。
   **判据**：记录键用 `<类目>/<名>`，**同名跨类目实测会撞**（`bg_1` 在 3 个类目里且内容不同）。
4. **缩略图按类目分目录**（`bg_thumbs/<类目>/<名>.webp`），扁平目录会让同名互相覆盖；
   先 `--limit 30` 小样本估时间与体积，再全量；收尾 `--check` 要求"索引里每条都有缩略图"。
5. **页面**：配色/圆角/动效只引用 `theme.css` 的 token（组件规则里不许出现字面颜色，否则昼夜只有一边对）；
   懒加载**不要挂 IntersectionObserver**（见踩坑）；缺图要打可见标记，不许留空格子伪装成功。
6. **接线两处，漏一处就是静默失效**：
   `scripts/deploy_gallery.py` 的 `FILES` 加新页（否则硬链与漂移检查永远看不见它）；
   `docs/WORKFLOWS.md` WF-15 承重白名单登记新依赖的资产目录（页面一上线，那层就从"可删"变成"在用"）。
7. **验收按顺序**：`py -3 scripts/deploy_gallery.py` → `py -3 scripts/diag/<新页>_probe.py` →
   提交 → `deploy_gallery.py --relink` → `deploy_gallery.py --check`（要求 FILES 全部同 inode）→
   动过 `index.html` 就要跑 `py -3 scripts/diag/wf16_regression.py --skip hit_verify`。

#### 判据（这一轮真正立住的几条）

- **视觉页的第一条判据是"图片对象解出像素"**：`img.complete && naturalWidth>0`，
  不是"卡片数量对不对"。本轮第一版 1897 个卡片全在、全空，只量 DOM 会报绿。
- **反向对照必须有**：故意请求一张不存在的缩略图，看缺失标记会不会亮。不亮 ⇒ 上面那条 ✅ 是空集给的。
- **浏览器视口尺寸要先量**（`innerHeight>400` 才继续判懒加载类断言）。
  连着的应用内浏览器页在侧边栏未展开时是 **0×0**，此时 IO 与原生懒加载都不触发，是**假红灯**；
  无头 Chrome 必须带 `--window-size=1440,1000`。
- **量字节用 `arrayBuffer().byteLength`**，`text().length` 是 UTF-16 单元数，中文页会自造假红灯。
- **筛选控件要就地改状态**：每次点击重建整组节点会让调用方的旧引用变死节点，
  表现为"上一个筛选没解开"，而且真用户点的是活节点、测不出来。

#### 踩坑记录

- 覆盖率三个数混报：任何字段命中 432 / 收窄到背景字段 406 / **那行带中文名 284（15.1%）**，
  我中途拿 432 说过"23% 有中文名"，差一倍。
- `bgm` 名模板（`story-<root>-stageN`）反推章节：99 行里只有 16 行是这个形状、只剩 4 个词根能用 ⇒ 否。
- 详情层没关就拍网格图、`.grid` 特写夹了 39 万像素高的整张网格 ⇒ 截图判据要"先复位再拍"，
  clip 高度要夹到视口。
- 探针假设"再点一次取消筛选"，而这页 chip 是单选组 ⇒ 产品没错、判据错（先证探针再定罪，同 WF-16）。

#### 涉及文件

`tools/sharecfg_re/49_publish_bg_scene.py`、`inputs/gamecfg/bg_scene_refs.json`（+ `MANIFEST.json` 台账）、
`scripts/build_bg_meta.py`、`scripts/make_bg_thumbs.py`、`gallery_src/backgrounds.html`、
`scripts/diag/bg_page_probe.py`、`scripts/deploy_gallery.py`（`FILES`）、`gallery_src/index.html`（入口）。
相关：**§115**（本轮取证与否证全文）、WF-15（承重白名单与换入闸门）、WF-16（画廊前端回归六件套）、
§111（`Output/Raw` 定性为纯背景层）。
### WF-31: 判「Live2D 某个部件为什么不动」——三层归因（源包控制器 → 参数轨迹+量程 → 运行时开关对照）

适用于"游戏里会动、我们这里冻着"这一类报告（花瓣、飘带、光量、尾巴）。**不要从参数名猜语义。**

**第 1 层｜源包 AnimatorController 才是"该播什么"的权威**（`scripts/diag/l2d_effect_layer_scan.py`
的读法）：层数、每层 `m_DefaultWeight` 与 `m_LayerBlendingMode`（0=Override）、每层状态机
`m_DefaultState` 解析到哪个 clip（`StateConstant` → BlendTree 根 `m_ClipID` → `m_AnimationClips`），
以及状态名走 `m_FullPathID` ↔ `m_TOS` 实例号。UnityPy 的字段都包在 `OffsetPtr` 里，统一 `.data` 解包。
判据：**只有"某层默认状态 = 该 clip 且 Loop"才允许说"游戏里它常驻播"**；clip 名字像不算证据。
子状态机的名字（`idle_list` / `touch_idle_list` / `touch_drag` / `ex`）就是游戏自己的分组，
轮播池按它抽，不要自己按 `idle\d+` 正则猜。

**第 2 层｜参数轨迹 + 合法量程**（`scripts/diag/l2d_motion_param_probe.py`）：在真实运行时逐条 clip
采样 `getParameterValueByIndex`，同时用 `getParameterIndex` / `getParameterMinimumValue` /
`getParameterMaximumValue` 把量程一起打出来。三条硬规矩：
- **采样窗必须盖过整条 clip**（gezi_1 的 `hxhb` 到第 8.12 秒才动，采 3 秒会得假阴性）；
- **`motion3.json` 的段格式**：首点 `(t0,v0)`，其后每段 `[type,...]`，`type=0` 线性 3 值 `[0,t,v]`、
  `type=1` 贝塞尔 7 值 `[1,c1x,c1y,c2x,c2y,t,v]`，**终点在最后**。以正本 `scripts/extract_motions.py`
  第 263-268 行的自述为准，别照"每 3 个数取第 3 个"这类想当然的步长——同一个错本项目已犯三次；
- **越出 moc3 量程的曲线会被 Cubism 钳死**（`Paramfh` 0→2000 撞 [0,10]）。所以"曲线幅度大"
  ≠"部件位移大"，量程只能问运行时。

**第 3 层｜改播放策略要有开关对照**（`scripts/diag/l2d_ambient_probe.py`）：判据落在
**"只有新机制会驱动、原 clip 从不动"的差集**上——全集做阴性对照必然假红灯（gezi_2 环境层 62 个
参数里 52 个 idle 也在动）。开关用 `window.__ambOff`（前端留钩子、UI 不暴露），
断言 = 开时差集在动 **且** 关时差集一动不动 **且** idle 自驱动的参数两侧都在动。

**踩坑记录**：① 造合成动作组（`mm.definitions['__pool']`）会让 `loadMotion` 永不 settle，
`reservedGroup` 挂着、`currentGroup` 恒 undefined——只用真实组名；② 装池前不掐 `groups.idle`，
库会先把带 Loop 的单条 idle 起播，之后所有请求被 `reservePriority >= priority` 挡成重复预约；
③ `motionFinish` 在 `state.complete()` **之前** emit，当场发 IDLE 请求必被拒，要 `setTimeout(0)`；
④ 该 build 的 manager 上只有复数 `stopAllMotions()`，单数 `stopAllMotion` 是队列管理器的；
⑤ 无头 Chrome 里 rAF 被节流，采样循环必须手动 `PIXI.Ticker.shared.tick(now)` + `app.render()`，
否则参数轨迹与帧哈希双双假阴性；⑥ 页面就绪判据不能只看 `typeof GALLERY`（它来自 index.js，
早于内联脚本），要等 `typeof openShip==='function'`，否则同一份代码一次成一次败。

**涉及文件**：`gallery_src/index.html`（`afterMotionUpdate` 环境层叠加、`motionFinish` 轮播、
`#l2Pool` 计数）、`scripts/build_l2d_motion_pool.py`、上面三个 `scripts/diag/l2d_*` 探针。
真实结论与收回的两条错判见 **§117**。

---

### WF-32: Unity 蒙皮包 → glTF（手搓 GLB）怎么装配、怎么验到能在浏览器里播（2026-10-07）

适用：要把 Unity AssetBundle 里的**带骨架蒙皮网格**（`Mesh` + `SkinnedMeshRenderer` + `Transform` 层 +
`Material`/`Texture2D`）变成前端能加载的 `.glb`。前提已经证完：**权重读得出来**（§116），
`UnityPy.export()` 只给不含骨骼的 OBJ，所以装配层必须自己写。

**第 0 步：先决定要不要引库。** 本条走的是**不装 `pygltflib`、手写 GLB 容器**：
GLB = 12B 头（magic/version/totalLength）+ 8B 块头 + JSON 块 + 8B 块头 + BIN 块，
只需要 `nodes/skins/meshes/accessors/bufferViews/images/textures/materials` 八段。
装库省不了多少事，却多一个 pip 依赖与版本面。**两条硬坑先记下**：
- ⚠️ **块数据从偏移 20 开始，不是 16**：12B 全局头 **加** 8B 块头 = 20。
  按 16 读会拿到 `"JSON{...` 这种带块头的串，`json.loads` 直接抛 `Expecting value: line 1 column 1`。
- 所有 bufferView 4 字节对齐（JSON 补空格、BIN 补 `\0`），否则 three.js 的 `Float32Array` 视图会错。

**五步，顺序不能换（每步都有判据）**：

1. **节点层用 `path_id` 建，不用对象 `id()`**：UnityPy 每次 `read()` 可能新建对象，
   按 `id()` 比对会**静默匹不上**（表现为骨骼全掉到根节点、蒙皮不炸但姿势散）。
   要 `by = {o.path_id: o}`，父子用 `m_Father.path_id`，GameObject 名用 `Transform.m_GameObject.path_id` 反查。
2. **顶点布局复用 §116 的反解 + 三重自证**，不要在装配器里再写一套宽度常量。
   解不成立就 `die`，**拒绝出图**——硬凑出来的模型在浏览器里"能显示"，只是姿势是错的，比报错更坏。
3. **材质按 PPtr 外链落回网格所在包**（`externals[i].name == 目标包内层 CAB` ⇒ `file_id == i+1` 的
   PPtr 的 `path_id` 就在那包里），**不要按材质名猜**；res 包 SMR 自己引用的常是占位 `Lit`。
   按 `m_SubMeshes` 的 `firstByte/indexCount` 切 primitive（一个网格可以有 5 个 submesh），
   **换绕序要在切分之后做**。
4. **左手系 → 右手系按镜像 X 处处一致地转**：顶点/法线 `x` 取反、三角形换绕序、
   矩阵做 `C·M·C` 共轭（`C=diag(-1,1,1,1)`）、四元数 `(x,y,z,w)→(x,-y,-z,w)`、UV 的 `V` 翻一次。
   ⚠️ 其中**矩阵元素序**与 **UV 翻转**这两处只能靠浏览器目视定案，所以装配器把它们做成
   开关（`--transpose-ibm` / `--no-flipuv`）——**不要**为了"看起来对"去偷偷改数据。
5. **产物必须被独立回读断言，并配红路径自测**（这一步才是"装配完成"的定义）：
   `--verify <glb>` 重新打开自己写的文件，判据全部落在**文件字节**上，不看装配过程的中间变量：
   GLB 声明长度 == 实际字节、每个 accessor 的 `count×type×componentType` 落在它的 bufferView 内、
   **从 BIN 里读回**每个顶点权重和 == 1、最大关节索引 < `skins[j].joints` 数、
   `inverseBindMatrices` 条数 == 关节数**且不含单位阵**（含单位阵 = 共轭没做或读错）、
   image 起始 8 字节是 PNG 魔数、索引数被 3 整除且 < 顶点数、**没有 mesh 没挂在节点上**（orphan 不会被渲染）。
   然后**必须做变异测试**：把一个权重字节改成 0、把 BIN 长度声明改短 4B ——
   两次都要 `exit 1` 且点名缺陷。**闸门不红就等于闸门是空的。**
   ⚠️ 量退出码时别让 shell 复合命令把它遮蔽（`... | tail` 拿到的永远是 `tail` 的 0；
   要么单独跑一次重定向到 `/dev/null` 再取 `$?`）。

**判据（什么才算通路成立）**：不是"three.js 加载没报错"，而是
① 站姿对（头朝上、脸朝前、比例对）② **没有三角面炸开/翻面**（这是权重 + bind 矩阵正确的直接证据）
③ 贴图不上下颠倒。①②③都要**截图目视**，无头 CDP 截图即可。

**踩坑记录**：
- ⚠️ **glTF 的 `skin` 挂在 node 上，不是挂在 mesh 上**。只写 `meshes` + `skins` 两段而不在节点上点名
  `skin`，three.js **照样画得出来**，但当成普通 Mesh —— 蒙皮静默失效。回读断言必须有这一条：
  "每个 mesh 的宿主节点都写了 skin"。
- ⚠️ **蒙皮权重属性名是 `WEIGHTS_0`（复数）**，`JOINTS_0` 才是单数前缀。写成 `WEIGHT_0` 时
  GLTFLoader 的映射表（`WEIGHTS_0:'skinWeight'` / `JOINTS_0:'skinIndex'`）**静默忽略**它，
  最后建 SkinnedMesh 时抛 `reading 'count'`。
  ⇒ **回读断言不许按"我自己写了什么键"查，要按规范白名单查键名**
  （`POSITION/NORMAL/TANGENT/COLOR_n/TEXCOORD_n/JOINTS_n/WEIGHTS_n`）——
  本轮就是 `--verify` 全绿而前端根本加载不了，因为它查的就是那个错键。
- ⚠️ 验蒙皮**不许用 `Box3.setFromObject(skinnedMesh)`**：它取的是**未蒙皮**的 `geometry.boundingBox`，
  蒙皮炸了它也不动，是条恒真判据。要量蒙皮就得在页面里**用 CPU 逐顶点重算**
  `Σ w·(bone.matrixWorld ∘ boneInverse)·v`；且"全零权重行"必须回落成原顶点，
  否则顶点塌到原点，包围盒与边长比一起被污染。
- ⚠️ **元素宽 2 字节不等于 float16**。Unity 顶点缓冲里同一个宽度在不同通道上含义不同：
  UV 是半精度浮点、**BlendWeight 是 UNorm16**、**BlendIndices 是 uint16**。
  一律按 `'<%de'` 读的后果：整数 `1` 变成次正规数 6e-8 → `int()` 归零 ⇒
  **GLB 里所有骨号都是 0，每个顶点都挂到 0 号骨**；权重 `32767` 按半精度直接是 **NaN**、
  `32768` 是 **-Inf**。⇒ 通道必须按**通道号**决定 dtype，不能按宽度查表。
- ⚠️ **内部不变式挡不住「保持该不变式的系统性错误」**：权重被整列读错之后，
  再除以自身和，**每行和照样精确等于 1**，所以「权重和==1」这条闸一路绿灯。
  而且 `abs(NaN-1)>eps` 恒为 False，NaN 连这条都过得去。
  ⇒ 自写产物除了内部不变式，必须再加 ① `math.isfinite` 单独查
  ② **跨源逐行比对**（产物里的前 N 行 vs 从源包重读的值）。
- GLTFLoader **一个 primitive 建一个 SkinnedMesh**（共享同一套 attributes）⇒
  "前端网格数 == Unity 网格数"这条判据要按网格名分组，不能按对象数直接比。
- ⚠️ **静止态蒙皮的判据必须是逐顶点偏差**，不是包围盒：
  `max|applyBoneTransform(i,v) − v| ≈ 0`（实测 1e-6 量级）能同时验位置/骨号/权重/bind 矩阵/节点层
  五者的互相自洽；包围盒只反映范围，**两个不同的错误可以给出同样的盒子**。
- ⚠️ **变异样本要证明它真的改变了被测物理量**。把所有权重整列改成 `(1,0,0,0)`
  （全模型只跟 0 号骨）在静止态下**偏差不变**（`B0·inv0·bind ≈ bind`），对照形同虚设；
  改成"每顶点首骨换成中段骨并独占权重"才爆开。
  同理，收集"偏差>阈值"的谓词写反（收集了 `<阈值`）会让一条 FAIL 看起来像 PASS
  ⇒ **判据的极性本身也要有对照**。
- 变异样本要**等长**：直接改 JSON 里的键名会顺带改掉长度，于是闸门先炸在
  "声明长度 != 实际字节"上，**证明不了你想验的那条判据**。正确做法：解析 → 改对象 →
  用同一个 writer 重新落盘。
- `accessor.count` 对 `MAT4` 是**矩阵个数**，不是浮点个数——传 `len(扁平数组)` 会让 `count×16×4` 超出
  bufferView，回读断言直接崩在越界上。修法：加一条**长度不变式**
  `len(values) == count × ITEMS[type]`，任何 accessor 传错都在生成时当场 `die`，而不是留给浏览器。
- 装配器的 `--check`（只装配不落盘）与 `--verify`（读回已落盘文件）是两件事：前者验**读得对**，
  后者验**写得对**。只做前者会漏掉全部序列化 bug。
- `roots` 要按节点序号去重排序（多个 Transform 的 `m_Father.path_id == 0`），只出一个会把
  多余骨骼子树整个丢在场景外。

**涉及文件**：新增 `scripts/dorm3d_to_gltf.py`（装配器 + `--verify` 回读闸门）；
`scripts/diag/probe_3d_capability.py`（新增 `probe_weights`、`compressedItems` 真读数、`SKIN` 段改报骨名）；
靶子 `files/AssetBundles/dorm3d/character/tianlangxing_db/{res/tianlangxing_noshoes,prefabs/tianlangxing_noshoes}`；
产物试装区 `.diag/dorm3d_gltf/`（未进 `Output/`）。
真材质外链落点与三个恒 0 假读数见 **§116 追加**，蒙皮权重数字与判据结论见
**`docs/archive/2026-10-07_3D宿舍复刻可行性取证.md` 追加-VII**。
相关：WF-28（撤销归档闸 / `--only` 粒度）、§8（PPtr/externals 规则）、WF-16（无头 CDP 验收）。


### WF-33: 批量导出器的「静默覆盖」审计 + 定向重导落地（改导出器后怎么证明只改了该改的）

适用：改了 `export_assets.py` 这类**按名字落盘的批量导出器**，或怀疑导出层比源包旧 / 比源包少。
核心难点不是修，是**修完怎么证明没有顺手改坏 1,800 张已验证的产物**——整类目重导本身就是风险。

**第 0 步：先分清缺的是"质量"还是"完整性"。** 用户说"图糊/图小"时，三层要各自量，别一起答：
源纹理天花板（`m_TextureFormat` / `m_Width`，本项目背景 = ASTC_RGB_6x6 @1024×576，**不可复原**）、
展示层缩略图档位（`MAXW`/`quality`，可修）、导出层覆盖与漏导（可修）。
判据：报"已无损"之前必须能说出**每张图的 `w×h` 等于包内最大同名对象的真实解码尺寸**。

**五步管线**：

1. **枚举包内对象，按输出文件名分组**（不是按包分组——覆盖发生在名字上）。
   量尺寸**只能真解码** `.image.size`：`m_Rect` 是图集声明尺寸、`m_Bounds` 在部分 UnityPy 版本是 None，
   两者都会让你把"裁剪版顶掉整图"读成"同尺寸没变化"。
2. **内容指纹定生死**：同名多对象先算解码像素 sha 分组。
   ⚠️ 别用"面积最大者胜"当裁决——同尺寸的两张不同画（本项目 `loadingbg` 13 对）照样丢一张；
   也别用"跨尺寸必是缩放版"当假设——把大的缩到小的尺寸后平均色差 23~92/255 就是不同图。
   规则：**同内容留最大的一份，不同内容全留**（第 2 张起加 `__N` 后缀），组间按 `(-面积, path_id)` 定序保证可重跑。
3. **只读预演算变更集**：用**生产代码本身**（import 进来调 `_resolve_same_name`）对全类目跑一遍，
   产出「会改哪些文件 / 会新增哪些 / 会删哪些（应为 0）」，于是"全量重导 N 千个包"缩成
   "只重导命中的 N 十个包"，其余一字节不碰。
   ⚠️ 预演比的是**内容**不是尺寸——比尺寸会漏报"同尺寸换图"这类改动（本项目实测漏 6 个）。
4. **对照臂 + 定点重导**：`--only` 前先看会不会跨目录串包（`bg_1` 在 3 个目录里都有），
   串了就停下让人限定目录，不要"顺手多写几个文件"。重导后逐文件 sha 比对预演集。
5. **双闸收尾**：① 变更集 == 预演集、删除数 == 0；② **像素级全覆盖**——每个受影响包里
   每一种不同内容都能在盘上找到（这才证明"换主文件名"没丢画）。
   然后才轮到派生产物：缩略图（改了档位必须 `--rebuild`，增量会跳过旧图）、索引、页面探针。

**判据**：
- 对照臂（关掉新策略跑一遍）产物必须与盘上现文件**逐字节相同** ⇒ 证明重构没改无关行为；
- 断言必须走**与被测代码不同的量法**（真解码 vs `m_Rect`），否则只是复述实现；
- 恒真断言不算判据：`--check` 里"缩略图缺 0 张"要和"索引条数 == 盘上张数"配成一对，单向数不报错；
- **验收脚本的期望值不得与被测数据同源**："页面卡片数 == 索引条数"只能证明前端没写错，
  证明不了索引归类对 ⇒ 另配一条从**独立事实**算出来的核对（本项目用盘上目录 `root_dir`
  数出来的张数，去比映射表 `GROUP_OF_DIR` 算出来的张数，两条码路不同源）；
- **报"找回多少"必须区分文件数与内容数**。合并/去重之后这两个数会分叉（本项目：文件 +23、
  索引 +10、**净增画面 15 种**）。只报最大的那个数，下一轮就会拿着它做决策。

**去重范围的坑**：把两个类目**合并**成一个展示类目，会制造出合并前不存在的重复
（`_hx` 那份和补回来的 `__N` 那份同内容）。⇒ 去重必须按**内容**在**合并后的类目内**做，
不能按"同名配对"（`bg_3__2` 的重复对象叫 `bg_8`，按名字永远配不上）；
每条丢弃都要记 `same_as` 并可断言"同内容那条确实在保留集里"。

**踩坑记录**：
- "取最大"看着无害，实际把 21 张完整插画继续留在丢失状态——**策略必须按内容而不是按尺寸**（§118）；
- 预演只比面积 → 报 5 个改动、实际 11 个，**假绿**由收尾的 sha 比对抓到；
- `--only` 不带目录限定会跨类目串包重写已验证产物；
- 导出层比源包旧是**会复发**的机制（本项目已中两次），补导前先比 `files/` 与 `Output/Raw/` 的时间戳。

**涉及文件**：`scripts/export_assets.py`（`dedupe` / `_resolve_same_name` / `--only-dir`）、
`scripts/diag/check_bg_export_dedupe.py`（两臂 + 独立裁判）、`scripts/make_bg_thumbs.py`（`--rebuild`）、
`scripts/build_bg_meta.py`（`__N` 剥后缀查表、同名第 2 张不发确定名）。
相关：**§118**（本轮取证全文）、WF-15（承重文件白名单 / 换入备份闸）、WF-28（`--only` 粒度）、
WF-16（无头 CDP 验收六件套）。

---

### WF-34: 人工视觉标注落成"默认视图筛选"的安全管线（标注 → 裁定 → 发布 → 索引 → 页面）

适用：要给图库/资产列表加一个**只能靠人眼看**的维度（有没有角色、是不是夜景、画的是不是战斗），
并让这个维度成为**默认视图**。核心风险不是标注本身，而是"默认视图"会把判错/没判的资产**静默藏起来**。

**五步**：

1. **标注与先验必须互相独立**。拼板每格只印全局序号，**故意不印文件名**——文件名里的
   `_cg` 就是那条待核对的规则，印出来等于把答案写在考卷上。规则预测另存 `prior_<NN>.json`，
   只做**事后交叉核对**。
2. **交叉核对给出"规则能不能用"的量化答案**，而不是"标注对不对"：本项目先验=0 而标注=1 有
   164 格、先验=1 而标注≠1 只有 24 格 ⇒ 规则的**漏报**才是致命方向（会被默认视图藏掉），
   所以规则只能当预筛。
3. **`不确定` 格必须升分辨率重看，且边界格交人拍板**。工具：`make_bg_adjudicate_sheet.py`
   （按原图导出 + 指定区域放大）。判"有人"要有**结构级证据**（头发/衣领/肢体），
   剪影轮廓不算；口径（局部身体算不算、只有手算不算）要写进发布件的 `scale` 字段，
   否则下一会话按另一套口径重判同一批数据。
4. **标注正本人库，临时区只留可再生产物**。`.diag/` 会被清盘：1,305 格人工结论 = 不可再生劳动，
   必须住 `annotations/`（裁定表带 `why`、合并正本 keyed by 资产键而不是序号——
   序号依赖拼板顺序，类目一重排就全错位）。发布件（`inputs/gamecfg/*.json`）走
   gitignore + `MANIFEST.json` 台账 + `check_inputs.py` 的 sha256 校验，与既有 gamecfg 同构。
5. **"没判过"要是一个独立状态，不能塌成 0**。三态编码取"**缺字段 = 没判过**"（不用 0/1/null 占位），
   因为下游任何一处 `if not has_char` 都会把没判过的当无角色。索引断言"未标注的类目不得带这个字段"。

**判据**：
- 发布前闸门四断言：值域只有 0/1（还有 `2` 就不许发）、**覆盖 == 索引里该组全集**、
  标注里没有索引已不存在的键（改名/重排要能响）、每条裁定带凭据文本；
- 页面侧必须有一条**按当前搜索范围算**的"藏了多少"常驻条：`pool(其余筛选) - pool(全部筛选)`。
  只报全库固定数会在用户搜索时空态写成"没有结果"，而真相是"被默认视图藏了 1 张"——
  这条判据的反面就是 §119 里那个空态归因；
- 探针要配**反向对照**：故意选一个"判过=无角色"的资产名去搜，必须看到空态与常驻条
  都写明是被这个维度挡的（判据 `0c`）；五档 chip 的计数要逐条等于索引 `META.char` 的数，
  而不是等于页面自己数出来的数（同源即自证）；
- 默认档的**名字要描述行为**：叫「隐藏无角色」而不是「有角色」——后者含 604 张没判过的，
  名字会在用户读到那一颗 chip 时撒谎。

**踩坑记录**：
- 新探针的第一处 DOM 断言没 poll boot ⇒ 首跑连红 4 条、二跑全绿（§119，与 §6 第 2 条同族）；
- 物件冒充人（木桶/岩石/军帽）与局部身体被判无人，**两个方向的错在同一次裁定里同时出现**，
  所以"代理判 `2`"要按格升分辨率逐格看，不能整批信任也不能整批推翻；
- 把标注只留在 `.diag/`：清盘即丢，且发布件也是 gitignore 的 ⇒ 两份都不在 git 里时无人知晓丢了什么；
- 用序号当标注主键：拼板顺序来自索引排序，类目一改就错位（本项目 keyed by `<dir>/<name>`）。

**涉及文件**：`scripts/diag/make_bg_label_sheets.py`（拼板 + 先验 + manifest）、
`scripts/diag/make_bg_adjudicate_sheet.py`（`2` 格裁定用图）、
`annotations/bg_char_adjudications.json` / `annotations/bg_char_labels.json`（入库正本）、
`scripts/publish_bg_char_flags.py`（闸门 + 发布）、`scripts/build_bg_meta.py`（透传 + 断言）、
`gallery_src/backgrounds.html`（chip 组 + 常驻条 + 空态归因）、`scripts/diag/bg_page_probe.py`（0/0b/0c）。
相关：**§119**（本轮裁定全文与两类陷阱）、**WF-33**（同一批背景图的导出层审计）、
WF-15（承重白名单：标注正本属于"丢了不可复原"那一类）、WF-16（无头 CDP 验收）。

### WF-35: 资产库「源头低清」子集的 AI 超分落地（选型 → 派生层 → 断点续跑 → 索引接入）

> ⚠️ **本流程已于同日整体停用**（用户裁定「细节被超分得不像原画」，见 §121）。三个脚本
> `scripts/upscale_bg_hd.py` / `scripts/diag/check_bg_hd.py` / `scripts/diag/bg_hd_model_cmp.py`
> **已删除**，需要时用 `git show b86825b:scripts/upscale_bg_hd.py > scripts/upscale_bg_hd.py` 取回；
> `tools/upscale/`（venv + ONNX 权重，310 MB）也已删，重装方法见第 4 步。
> 本条**保留**是因为里面有几条与超分无关、换个任务还成立的判据（派生层不碰权威层、
> 续跑判据要查文件尾部、选型要同图并排看、样张要按消费形态给）。

适用：图库里一部分图**源头分辨率就是低的**（游戏包只有 1024×576），用户反馈"看着糊"，
要在不动导出层的前提下补一层高清产物。核心风险不是超分本身，而是**派生层被当成权威源**、
以及**断电/中断留下头部合法的截断文件被续跑当成已完成**。

**六步**：

1. **先证明"糊"不是自己压的**，再谈补救。三条独立取证：① 抽样回源包比对
   （`导出即包内最大纹理 130/130`，见 `.diag/` 一次性探针）；② 页面链路核对
   （详情/全屏走原生 PNG，缩略图 720px 对 232px 卡片够用 ⇒ 网格不是瓶颈）；
   ③ 读源纹理真实参数（`m_Width/m_Height/m_MipCount` + 压缩格式，ASTC ≈3.5bpp 说明包里已损耗）。
   ⇒ 没有这一步，很容易去优化一个根本不是瓶颈的环节。
2. **只挑"源头低清 ∧ 用户真会点开"的子集**，不要全库。本项目口径 = 宽 ≤1280 ∧（有角色 ∨ 登录/加载）
   = 263/1909 张。判据写在 `pick_targets()`，**has_char 缺失（没判过）不算有角色**——
   这条和三态编码的"缺字段 ≠ 0"是同一条纪律。
3. **模型选型必须同图并排看，不许凭 README 的名字选**。工具 `scripts/diag/bg_hd_model_cmp.py`：
   同一张图的同一块区域喂进 3 个模型，全部**下采样到同一显示宽度**再并排（显示宽度才是用户
   真正看到的尺度；按原生 1:1 比只会放大各模型的伪影）。四条判据：平涂线稿有没有断裂/凭空多线、
   厚涂笔触有没有被抹成塑料面、小字有没有糊、单张耗时。本项目结论：anime6b 线稿最好但最贵，
   general-x4v3 快 10 倍但对平涂略平，UltraSharp 保纹理但慢到不可接受（30~63s/张）。
4. **运行时隔离**：新建 `tools/` 下的 venv 装 `onnxruntime-directml`，**绝不装进全局 python**
   （全局那份 onnxruntime 是 OCR 脚本在用，`onnxruntime-directml` 会覆盖同名包）。
   DirectML 在 NVIDIA 上免装 CUDA、免下 3GB torch，且 `get_available_providers()` 能当场自证走的是 GPU。
   国内网络：GitHub 直连不通时走 hf-mirror 拉权重，PyPI 走清华源。
5. **派生层独立目录 + 可整目录删掉重来**：产物写 `Output/Raw_hd/<类目>/<名>.png`，
   **不碰** `Output/Raw/`（WF-15 承重白名单）。索引侧只在"文件在 ∧ 尺寸正好 4 倍 ∧ 尾部完整"
   三条同时成立时才发 `img_hd` 字段，任一不满足就**不发**（页面自动回落原图），
   并把对不上的键打印出来 —— 不许静默挂一张错位图。
6. **续跑判据必须查文件尾部，不能只看尺寸头**。PNG 的 IHDR 在最前面，进程被杀/断电留下的
   半截文件**头部尺寸完全合法**，`png_size(dst)==exp` 会把它判成"已完成"而永久留下坏图。
   ⇒ 跳过条件 = 尺寸对 **且** 末 8 字节是 `IEND\xaeB\`\x82`；截断的删掉重跑。
   同理 `build_bg_meta.py` 挂字段前也要查尾部（两层都要防，索引层防的是"批处理还在跑就重建索引"）。

**判据（收尾要自证的）**：
- 日志末行 `完成 N / 跳过 M / 失败 0` 且 N+M == 目标数；中途崩溃时**直接重跑同一条命令**即可续，
  并把 `截断，删掉重来` 那几行留作断电证据。
- `build_bg_meta.py --check` 两条新闸门绿：`img_hd 逐张回盘核对（4 倍 + 在位）`、
  `img_hd 只挂在低清子集上（宽 ≤1280）`。
- 页面：有 `img_hd` 的条目详情/全屏/下载走高清，没有的必须**照样能打开**（回落路径要单独测）。

**踩坑**：
- 整图 4x 的中间张量在 8GB 显存上会顶不住（1280 宽 → 5120×2880），必须分块；
  分块正确性**不能靠目视**，用「同一块区域 整块 vs 分块」逐像素比对（本项目平均差 0.0009、
  差异 >0.02 的像素 0.77%，且都落在块边界 ⇒ 接缝逻辑对）。
- fp16 权重要喂 fp16，喂错 dtype 在 DirectML 侧直接抛；脚本按 `inputs[0].type` 自动转。
- 模型块尺寸必须凑 4 的倍数（x4 网络），贴边凑不齐就 `np.pad(edge)` 再裁回，别缩块。

**涉及文件**：`scripts/upscale_bg_hd.py`（批处理 + 续跑 + 分块）、
`scripts/diag/bg_hd_model_cmp.py`（选型对比条）、`scripts/build_bg_meta.py`（`img_hd` 挂载 + 两条闸门）、
`Output/Raw_hd/`（派生层，不入库）、`tools/upscale/`（venv + ONNX 权重，不入库）。
相关：**WF-15**（承重白名单：Raw 不可覆写）、**WF-34**（has_char 三态口径）、
**WF-16**（前端改完的硬链接部署链）。

**补（同日跑完 263 张之后加的两条，都是当时缺的）**：

7. **估时按稳态、不按首条**：GPU/带 JIT 的运行时前 10 条是冷启动价（本项目 23.4s → 稳态 4~5s，差 6 倍），
   用首条耗时乘总数会估出 2 小时而真值 31 分钟。已开跑就按"累计 ÷ 已完成"滚动修正。
   同批条目不等价 ⇒ 稳态值要按尺寸分组再看（1024×576 中位 5.0s / 1280×720 中位 18.4s）。
8. **完整性判据自身要有双向对照**。`check_bg_hd.py::selftest()`：拿一张在盘真产物断言判 True、
   把它前半截写进临时文件断言判 False，任一不符 `exit 2` 并声明"后面数字都不可信"。
   本轮真实缺陷就是判据偏移写错（IEND 只有 8 字节，读在 `[-12:-4]` 会永远 False）——
   这次错成**假红**（fail-safe，看得见）；反过来错成永远 True 就是**假绿**，截断文件会被
   当成已完成永久留下坏产物。**同一条判据被抄了几份就要一起改**（本轮 3 份：批处理 / 索引 / 复核器）。

**第 9 条（本流程被整体否决后补的，比前 8 条重要）**：

9. **先问"这活儿该不该做"，再问"怎么做好"**。本流程 263 张全部跑完后被用户否掉，理由是
   「细节被超分得不像样」——而这不是画质问题，是**AI 补出来的像素属于推断**，资产库掺进去
   就不再是原资产（详见 **§121**）。⇒ 动手前先确认任务的**底线是"还原"还是"变好"**：
   要"还原"就不能上任何生成式加工；要"变好"才轮到本流程。
   - **样张必须按最终消费形态给**：整图 + 全屏 + 1:1 细节三样都要，不能只给下采样后的对比条。
     本轮真实失误：样张只给了缩放到显示宽度的对比条，那正是"看不见缺陷的尺度"，
     用户在这个尺度上点了头，看到成图才发现不对——等于**把裁定放在了一个无法裁定的样本上**。
   - 被否之后要做的是**默认关闭 + 把裁定写进文档**（`--with-hd` 才启用），
     而不是换个模型重跑；同时把"试过并排除的路"列进 §121 的「已排除的假设」。
   - 唯一不涉及生成的提清晰度手段：**按内容（dHash + 随机不同图做对照）在库里找同图不同尺寸的孪生**，
     把条目指向已有的那份大的。这是"指向"不是"加工"，零编造 —— 但**本项目实测下来此路不通**：
     数值全过的 6 对候选，人眼过一遍后 5 对是"同场景的另一版"（多烤 UI 字 / 故意虚化 / 细节元素不同），
     0 对可用。⇒ 判据必须加第三关（见 `scripts/diag/bg_twin_scan.py` 脚本头第 4 条），
     且它的输出字段叫 `candidates` 不叫 `accepted`。全文见 **§121 的「更正」段**。

### WF-36: 判「Live2D 观感与游戏不一致」是不是**运行时语义差异**——moc3 参数标志级取证 → 前端最小补丁 → 四道判据（2026-10-08）

**日期**: 2026-10-08
**目标**: 当"某个部件不动 / 动作后半段冻住 / 越界的曲线看起来不对劲"已经排除了丢曲线与选错 clip（WF-31 的三层归因），
再往下只剩一种可能：**我们用的运行时与游戏用的运行时对同一份 moc3 的解释不同**。本 WF 给出这一类的取证与落地做法。
**适用场景**: 参数轨迹在 moc3 量程内就饱和、曲线却明显写着要跑到量程外；或反过来"游戏里连续、我们掉到一半停住"。

**四步管线**：

1. **先把"越界"这件事量化到曲线级**，不要只看一条参数。
   `py -3 scripts/diag/l2d_curve_shape.py <key> '^MB_'` → 逐 clip 打印每条曲线的
   键数 / 贝塞尔段数 / **复位(下降)次数** / min…max / 是否越界及"越界后多久被钳"。
   ⚠️ `Segments` 的正确步长：三元组 `[t,v,type]`，`type∈{2,3}` 再跟 4 个控制点，
   **最后一个键只有 `(t,v)` 没有 type**（`len%3==0` 的整除去解会错位或 IndexError）。
2. **读 moc3 的逐参数标志表**（量程 + `repeat`），这是唯一能区分"美术写错"与"运行时没实现"的证据：
   `py -3 scripts/diag/l2d_param_meta_probe.py <key> <某参数> 0 1 2 3 3.5 4.5`
   它做三件事：① dump `parameters.{minimumValues,maximumValues,defaultValues,repeats}` 全表落盘；
   ② 扫值并读回，区分「硬钳到 max」与「回绕」；③ 传 `@inrange` 跑**量程内恒等自检**。
   ⚠️ Core(Web) 的 Model **没有 `setParameterValue`**：写值只能走 framework 的
   `setParameterValueByIndex(ix, val, weight)`，raw wasm 视图在 `coreModel._model.parameters.values`。
3. **用"越界只发生在带标志的参数上"当阴性对照**。本项目实测 `gezi_2`：27,865 条曲线中越界 580 条，
   **580 条全部 repeat=1、repeat=0 越界 0 条** ⇒ 一次同时否证"美术失控"和"数据导出坏了"。
   反过来若两者都有，就不是运行时语义问题，回去查导出。
4. **补丁只打在那一个写入函数上，并且先证明它对量程内是恒等变换**：
   原型包装 → 严格越界才取模 → 用 52 个 repeat 参数 × 5 档共 260 次写入做恒等自检（必须 0 失配）。
   恒等自检不是形式主义：它当场抓出"官方 ModF 把 `val==max` 折成 min"会打掉本皮肤 75 个刻意钉在 max
   的键点（`Param81` 整段 =1.0、`hxhb5`=10.0），于是把条件收紧成 `val>mx||val<mn`。

**判据（改后必须四条齐全，缺一条不许说"修好了"）**：
① 直写超量程值读回 = 期望的回绕值；② **真实播放路径**上记录到"交给 setter 的原始值确实越界过"
（用监视器包住同一个函数，统计 `calls / maxIn / over`），别用直写代替——直写绕过了动作求值；
③ 接缝处 `传入→存值` 一对一实例（本项目：3.0483 → 0.0216）；④ 量程内恒等自检 0 失配。

**踩坑记录**（每条都会单独造出假结论，全文见 §123 第五节）：
- 无头 Chrome 里 `Ticker` 对 `dt` 有上限，运动相位推进远慢于墙钟 ⇒ **采样窗口按墙钟算不够长**，
  第一次"改后探针"就是这样被读成"补丁没用"的；合成时钟 `Ticker.shared.tick(sim)` 也推不动。
- 两次独立抓帧**不能**逐像素对照（起播相位与物理积分步数不同，t=0 就差 2.7 万像素）；
  要定位改动面请用参数级判据，或同一次会话内扫值截图。
- 探针不许写死外部服务器地址；自带 `http.server` 并在启动 Chrome 前轮询 200，失败时打印
  `location.href` + `document.body.innerText`，否则「GALLERY is not defined」会被误读成"页面被改坏"。
- 原型上挂第二层监视器前必须先存**原始**实现引用（`CP.__origSet||CP.setParameterValueByIndex`），
  否则第二次运行会把监视器自己当基类，`return base.call(...)` 立即自递归。
- 共享工作树里 `Edit` 改 `gallery_src/index.html` 必断硬链，收尾按 AGENTS.md 的四步顺序走
  （默认模式刷平 → 提交 → `--relink` → `--check`）。

5. **如果"某个部件在任何动作里都不动"，先查它是不是属于**另一条常驻 clip**（源包 AnimatorController
   的独立层），而不是继续在这条 clip 的曲线里找**。查法：`l2d_effect_layer_scan.py --keys <key> --speeds`
   逐层打印 `weight / blend / 默认状态 clip / m_Speed / Loop`（本轮实测 gezi_2（葛兹）所有状态 `m_Speed=1.0`
   ⇒ "我们比游戏快"不是倍速问题，这条排除项要留着别重猜）。落地成前端的**环境层**时三条硬约束：
   - **默认让位**：环境层只写「自己非常值、且任何 pose clip 都不动」的参数（`poseDriven` 之外）。
     上一版默认"照源包语义盖住 pose 层"，运动量是更接近游戏（47.7‰ vs 35.6‰，游戏 125.8‰），
     但会把 pose 正在动的参数逐帧硬写到环境层的值上 ⇒ 用户症状"组件蠢蠢欲动/突然消失一下"。
     盖住行为留 `window.__ambMask=true` 做反向 A/B。
   - **常量曲线一律不写**（会把 pose 正在动的参数钉死，实测 15 个模型受影响、mingji_2 达 70 个）。
   - **不进队列管理器**、写在 `afterMotionUpdate`：进了队列，播一次 `touch_*` 就把环境层挤到末位，
     回落时反过来盖住它。`window.__ambOff=true` 是给无头探针的关闭开关（`l2d_motion_param_probe.py`
     默认带着它，要测环境层得 `AMB=1`）。

**判据（环境层这一支）**：装载后读 `window.__ambDbg()` 看 `loaded / held / yieldToPose`；
再 `AMB=1 … --params '^(Paramfh|MB_wutixialuoxunhuangz2|bowen)$'`，要求这些"只有环境层会动"的参数
出现**锯齿**（下降次数 ≥1、平台 0%），而不是常量 0。

⚠️ **解析器只许有一份**：本轮在前端新写 `motionSegs` 时又按"每三元组第三个是 type"错过一次
（后果是 effect 曲线全部解析失败、环境层静默不装载、探针读出"参数恒为 0"，看起来像"改法无效"）。
同一个坑本项目已犯三次 ⇒ 前端与 `scripts/diag/*.py` 都各自只留一个解析函数，改步长先改注释里那句
格式自述，再让所有调用方共用（现在前端的 `markPhase` / `curveMoves` 都走同一个 `motionSegs`）。

**三臂运动能量对照（2026-10-08 实测，用来定"让位还是盖住"）**：`l2d_gallery_capture.py --amb {off,yield,mask}` 各抓 12 秒 @6fps，再用 `l2d_motion_energy.py` 量。

| 角色带 均值‰ / 峰值‰（全画面中部） | 101.7/146 | 107.4/137 | **129.5/231** | 93.7/167 |
| 自上而下 4 条 ‰（限内容范围） | 0/70.8/71.7/0 | 0/76.0/73.3/0 | 0/94.7/83.5/0 | **50.3/94.7/85.7/28.2** |

读出来的三件事：① **盖住把角色带推到游戏之上**（129.5 vs 游戏 93.7），且单帧峰值 231‰ ≈ 让位的 1.7 倍
——大面积单帧突变正是"部件闪一下"的形状 ⇒ **默认保持让位**；② ⚠️ **全画面能量看不见花瓣**：花瓣是小面积
物件，让位臂相对 off 臂只涨 5.6%，但 `Paramfh` 实际已经 17 次回绕 ⇒ 判"花瓣有没有掉"必须用**参数级**
判据或局部放大，不能用能量 ‰；③ ⚠️ 我一度把"上下两条 ‰=0"读成**黑边**，那是错的：逐行取最大值证明有效内容覆盖整帧（0..679/680），
   上下两条是**静止内容**。把测量限制在内容范围内、自上而下切 4 条后：
   我们 off/yield/mask 都是 `0.0 / 70~95 / 72~84 / 0.0`，而游戏是 `50.3 / 94.7 / 85.7 / 28.2`——
   **游戏画面上下两半一直在动，我们那里是死的**。⇒ 真正的差距不在"让位还是盖住"，
   而在场景侧那层常驻动效（光带/星点/飘落）我们整层没有；绝对 ‰ 跨源仍受缩放影响，
   但"运动分布"（各条占总量的百分比）是可比的：我们 100% 挤在中间两条，游戏是 19/37/33/11。

6. **观感是"闪一下 / 消失一下"而不是"冻住"时，先分层再猜原因，最后用因果扫描点名参数**
   （工具 `scripts/diag/l2d_part_flicker_probe.py`，四臂一条命令全出）。本项目八轮的完整链条见 §123 追加/II/III，
   这里只留做法与判据：

   - **臂① 分层**：逐帧同时采全部 part 与全部 drawable 的不透明度，按两档筛台阶（hard：`<0.05` 且前帧 `>0.5`；
     soft：单步降 ≥0.4 且 4 帧内回升 80%）。实测 **195 个 part 全程恒定 / 770 个 drawable 有 188 个在变**
     ⇒ 隐藏落在**逐个 ArtMesh 自己的透明度**上。**不做这一步就会在错误的层上找正确的 bug。**
   - **臂② 全参数逐帧 + 台阶形状**：从 wasm 实时缓冲 `parameters.values` 取全部参数，找"孤立跳变"
     （`|Δ| ≥ 4× 本参数窗口内 |Δ| 中位数`，且前后一帧 ≤0.35 倍）。⚠️ **不要用"与台阶同帧变化"当判据**——
     物理/呼吸/环境层一直在动，实测命中 246/532，等于没有判据。
   - **臂③ 写入者归因**：包 `setParameterValueByIndex`，只记"存值真的变了"的行，附调用栈前 4 帧
     （`restTick@index.html` = 复位层、`afterMotionUpdate` = 环境层、`doUpdateParameters@cubism4.min.js` = 动作求值）。
     ⚠️ **`weight` 不能用来判"是不是交叉淡化"**：框架会把混合后的结果当值传入、weight 恒 1；
     只有**存值序列**能当证据（本轮就是靠"每帧两笔 + 淡出条目交出的不是它自己 clip 的值"认出交叉淡化中间态）。
   - **臂④ 反查绑定：用运行时因果扫描，不要解 moc3**（仓库里没有绑定表解析代码）：
     `stopAllMotions()` + `__ambOff=true` → 逐个参数在量程内写 **N≥10 个点** → `core.update()` → 读目标
     drawable 透明度，得到**值→透明度映射**（隐藏阈/显形带在哪）。532 参数 × 11 点 ≈ 5,852 次 update、约 30s。
     ⚠️ **点数必须 >2**：ArtMeshOpacity 是**乘性带门**，只测 min/中/max 会把"只在量程中段显形"的驱动者
     整个漏掉（3 点那轮只答出 `l2d_hx`，10 点才扫出 `Param25` 的硬阈 v≥0.1→0 与 `MB_wutixialuoxunhuangz2` 的带门）。
   - **采样基准必须是「每一次模型 update」而不是墙钟**：包 `CubismCoreModel.prototype.update`
     （打补丁前先存 `CP.__baseUpdate`，第二次运行才不会把监视器自己当基类递归）。无头里 update 只有
     ~2.6 次/秒，按墙钟数台阶次数同一条 clip 会跑出 10 与 20 两种结果；按帧对齐后绝对次数才第一次可比。
   - **每条臂都要自证"采到了"**：输出里必须带 `行数 / 至少变过一次的参数个数 / 名字解析失败数`，
     并内置一条结构性矛盾 —— **有 drawable 在变而 0 个参数在变 = 不可能 = 仪器坏**（`--allparams` 上一轮
     就是报了一个"没采到"的 0，被读成了"参数层没问题"）。

   **判据（点名一个参数要四件同时成立，缺一不许说"锁定了"）**：drawable 台阶所在帧 = 该参数的孤立跳变帧；
   扫描映射里该参数确实能产生这个透明度值；setter 日志里那一刻有人写它；clip 数据侧的曲线值能解释台阶的**终值**。

   - **臂⑤ 全量绑定表（一次顶 N 次单点问答）**：`... --mapall --nsweep 10` 把「哪个参数在量程哪些点上
     会让哪些 mesh 离开基准」整张跑出来（532×11 点 = 5,852 次 `core.update()`，约 1 分钟），
     落 `.diag/l2d_opacity_map_<model>.json`；查询器 `scripts/diag/l2d_opacity_map_query.py`
     （`--mesh` 反查一块 mesh 的全部开关 / `--param` 正查一个参数管几块 / `--divergent <clip>` 算
     「idle 动画了但目标 clip 不动画」的 writeDefault 差集并交叉可视性 / `--ambient` 环境层管几块）。
     **这张表真正的用途是"差集 × 可视性"交叉**：runtime 语义缺失类问题（游戏钉默认、我们留残留）
     只有在这种交叉下才现形，逐帧采样是看不见的——它不是瞬态，是**持续状态差**。
     ⚠️ 台账的 `#mesh` 计数是**下界**：ArtMesh 透明度是乘性带门，扫描基准里已经关着的 mesh
     对任何参数都不响应 ⇒ 换基准状态会多出驱动者。要当完备清单用必须先做第二基准复扫。
     ⚠️️ **更要紧的是它同时会造出假阳性**（2026-10-09 实测，本项目这条把结论灌错了 95%）：
     以"当前状态"为基线做扰动测试时，凡基线里为 0 的对象，对**任何**输入的扰动都报"变了"——
     那不是"输入改变输出"，只是"基线为 0、一动就离开 0"。两条一起用才成立：
     ① **基线取确定性姿态**（全部参数写格式声明的默认值后再采基线，而不是拿运行中恰好停住的状态）；
     ② **一条关联只有在"各采样点读数不是全等"时才算真绑定**（全等 = 与输入无关）。
     加这两条后：真绑定 22,028 → **1,061** 对，"会管显隐的参数" 504 → **99** 个。
     **通用形状：任何"谁影响谁"的扰动扫描，都要先问基线是不是该对象的关闭态。**
   - ⚠️ **截图类 A/B 有三道会各自独立造成"两张图一样"，缺一就误判"没作用"**：
     ① 写产物缓冲必须打在**引擎重算之后**（在 `core.update()` 之前写会被按参数重算覆盖，写 0 读回 1）；
     ② WebGL 画布默认 `preserveDrawingBuffer=false`，不经过一次合成（`render()` →
        `await requestAnimationFrame` → `render()`）截图取到的是**上一帧**；
     ③ 页面自己的调度循环会把参数写回去（要关 autoUpdate / 停调度）。
     ⇒ **截图对必须自带像素差自检**：两图差 <50 像素就打印"仪器坏"，绝不允许把"没截到"读成"没作用"。

   - **臂⑥ 单参数 A/B 截图（只为"这个参数管的是画面上哪一块"，不是验收判据）**：
     `--shot Param25:0,0.5` 各拍一张 + 差图 + 并排图。
     ⚠️ **两拍之间必须冻住 ticker**（`app.ticker.stop()`）并把全部参数恢复到同一基准：否则物理/头发继续跑、
     姿态漂几像素，差图会**全身轮廓亮**——实测不冻 3.49% 像素、冻了只剩 0.08%，差 43 倍，
     而那 3.49% 会被读成"这块参数管一大片"。（本轮真实踩到）
     ⚠️ 用途要说死：它是**身份识别**工具（把 `ArtMesh42` 对应回"哦，是花瓣"），不能当"改好了"的证据。
   - **臂⑦ 几何导出**：`--dumpgeo` 导出全部 mesh 的屏幕包围盒/面积/透明度/绘制序，换算**复用产品那套
     `P2V`**（`Vx=Px-cux/2, Vy=cuy/2-Py`，见 `gallery_src/index.html` 里那段两套坐标系的注释），
     探针里绝不另立一套坐标映射——历史上"点胸口触发头部动作"就是两套空间混用的结果。
     配好之后 ① 的每条台阶会自动带**位置与面积**，"消失的是手还是花瓣"从此可离线算，不靠猜。
   - ⚠️ **拿抓帧序列跟游戏录像对比之前，必须先钉住动作时间**：`l2d_gallery_capture.py` 手动推 ticker 时
     动作时间与墙钟不成 1:1，本项目实测同一张对照图里两边差了约 10 秒的 clip 进度（游戏在跳舞、我们已在片尾
     飞走）。**时间没对齐的帧对比一律不作数**——它看起来像"内容不一致"，其实只是相位不一致。
     （该工具已加 `--clip` 用 FORCE 播指定 clip，但动作时间戳仍待补，见 §123 追加-V。）

   **两条阴性对照怎么配**：① 结构性排除优先于测量排除——`model3.json` 有没有 `FileReferences.Pose`
   一句话就能判死部件组假设；cubism4 包里没有任何 `setDrawableOpacity` 就锁死"台阶必出自参数绑定"。
   ② ⚠️ **"不切动作的对照组 = 0 次"没有否证力**：带门开合是周期性的，窗口相位决定 0 次还是 1 次
   （实测同一条 `__none__` 跑出过 0 与 1）；要判"绑事件"，对照组必须覆盖 ≥1 个完整周期。

7. **判「参数 → 哪片 ArtMesh 显隐」之前，先证这张表是函数表**（新臂 ⑯ `--coldmap` / ⑮ `--reconcold` / ⑬ `--recon`）：
   **逐档爬的因果扫描（0→0.1→0.2…）带不可逆滞回**——本项目实测：爬完之后再回全默认，被点亮的那 29 片**仍是 1**，
   于是"阈值"其实是**扫描网格的中点**（`snapswitch.json` 里 `flips=[0.05,0.15,…]` 就是这么来的），
   连"哪几片算一组"都是同一假象。正确形状：**每个测量点都从基线一次跳到**，且**正序 + 倒序各跑一遍**，
   两遍一致才允许发布成表；不一致就只许说"有滞回"，不许说阈值。
   配套三把仪器自证（缺一把就可能把仪器故障读成"这条路无效"）：
   ① 同一状态用**三种读法**对照——手里的旧视图 / 每拍重取的 `core._model.drawables.*` / 框架 getter
   （不一致 ⇒ wasm 内存增长后 typed-array 视图失效）；
   ② 写值分**两条路径**各跑一遍——直写 wasm 缓冲 vs `core.setParameterValueByIndex`（不同 ⇒ 绕过了真实播放路径）；
   ③ 把参数写成基线后 update，再**逐位 diff 参数数组**（非 0 ⇒ moc3 里有派生参数链，扫出的"阈值"是派生值的运动）。
   ⚠️ 任何"像素有没有变"的对照都必须调 **`model.update()`**：pixi 每片的 alpha 是在 `model.update()` 里
   从 core 缓冲同步的，只做 `core.update()+app.render()` 的截图对"缓冲变了而像素没变"**不构成证据**（本轮真实踩过）。

**涉及文件**：`gallery_src/index.html`（运行时补丁 ⑤ + 环境层 + `motionSegs`/`poseDriven`/`markPhase`）、
`scripts/diag/l2d_curve_shape.py`、`scripts/diag/l2d_param_meta_probe.py`、`scripts/diag/l2d_motion_param_probe.py`（`--dump` + 平台/下降判据 + `AMB=1`）、
`scripts/diag/l2d_part_flicker_probe.py`（逐帧 part/drawable 不透明度 + `--trace` + `window.__noRest` 两臂）、
`scripts/diag/l2d_gallery_capture.py`（`--amb off|yield|mask` 三臂）、
`scripts/diag/l2d_motion_energy.py`（分带/热区）、
`scripts/diag/l2d_effect_layer_scan.py`（`--speeds` 逐层倍速/默认状态）、
`.diag/_param_meta_<key>.json`（标志表产物）。相关：WF-31（三层归因，本 WF 是它的第四层）、
WF-16 六件套（前端改动的回归闸门）。

---

**WF-36 追加（2026-10-09）：第 7 步——只把「互斥美术开关」在切换时钉住，其余照常交叉淡化**

第 6 步找到死区与"游戏是瞬时切换"之后，修法 (b) 的全部难点是**自动判定哪些参数算开关**，
判错的方向不对称：漏判 = 手还是会闪一下（用户已见过的病），误判 = 把某个姿态参数变成瞬移（§6.35 治过的病）。
所以判据必须**因果**（来自"这个参数到底管不管显隐"的实测），不能来自曲线形状或名字。

**三条判据（`scripts/diag/l2d_snap_criterion_scan.py`，全离线，不碰前端）**：
1. **在显隐台账里**：探针臂 ⑤ `--mapall` 落的 `.diag/l2d_opacity_map_<model>.json` —— 只有它真的能把某个
   ArtMesh 的不透明度写出基准，才有资格当"美术开关"。gezi_2 实测 **99/532** 个参数有这个能力，
   这一条就把相位/口型/角度类全部自动挡掉（"边界恒定且值不同"的宽松判据会放进来 **296** 个）。
2. **跨过翻转点**：出去的那条 clip 末尾恒定、进来的那条开头恒定、两值不同，且两值之间跨过台账里
   至少一个**翻转点**（相邻采样点上"有 mesh 从亮变灭或反之"）⇒ 这一淡确实会改变"哪些美术在画"。
3. **几何位移够小**（探针**新臂 ⑨** `--deform`）：别的参数全钉在基准，只把这一个在第 q-1→q 点之间移动，
   比较**两点都亮着**的 mesh 的屏幕框 Σ(宽+高)；纯显隐开关应当一像素不动。
   实测分布是**双峰**：23 个参数恰为 0.0000 → 0.041~0.20 → 直接跳到 1.52 / 3.0 / 4.2 / 27.8 / 35.8 / 39.8 ⇒
   阈值取 0.5（舞台约 8 单位）落在空档里。被这条挡下的 `ParamForearmLAngle`（左前臂角，量程 [-30,30]）
   就是"既绑显隐又形变"的典型：它确实控制某些美术，但它同时是姿态 ⇒ snap 它 = 手臂瞬移。

**判据怎么算才算成立**（不是"抓到多少"）：**已知门参数必须在内，相位/口型类必须不在内**。
gezi_2 定案 33 个参数：6 个"clip 边界真会动"的门（Param20/21/25/27/39/l2d_hx）全在内、
相位/口型（Param122/52/65/141-143/ParamMouthOpenY）0 误伤、形变者 6 个被 ③ 挡下。
（⚠️ 这条"0 误伤"是**第 1、2 条**给的；第 3 条的位移阈值只决定"形变者进不进"，
`ParamJTEyeOpen` 在**恒定段算宽之后**会进表 —— 它进表也无害，因为眨眼层排在钩子之后会盖掉钉值，见踩坑第 4 条。）
另 4 个已知门（Param17/139/188/shop_hx）**在所有 clip 的头尾都是同一个值 0** ⇒ 根本没有跨 clip 的过渡，
不需要 snap —— "漏了它们"是正确结果，不是判据缺陷。

**怎么做**:
1. `--mapall` 落显隐台账 → `--deform @表` 落变形者闸 → `l2d_snap_criterion_scan.py <model> --emit` 落
   `Output/Live2D/<model>/<model>.snapswitch.json`（`params{flips,mn,mx,stepShift}` + `clips{边界值,恒定秒数}`）。
2. 前端补丁 ⑦（`gallery_src/index.html`）：`beforeMotionUpdate` 抓"切换前的实际值"（**只能在 before 抓**，
   afterMotionUpdate 之后缓冲里已是混合值），`afterMotionUpdate` 逐帧把参数写回进来的 clip 的边界值，
   钉到淡化窗口结束。**表不存在 = 这层完全不存在** ⇒ 没跑过判据的模型逐帧行为与改动前相同。

**判据（验收，不用截图）**：探针**新臂 ⑩** `--snapab idle->home` 同一趟跑 `window.__snapOff` 关/开，
逐次模型 update 记时间轴。看的是**"该参数能影响的全部 mesh 里有几盏亮"（台账集）**随帧的曲线：
修法关 ⇒ `Param25` 用 ~1.5s 穿过死区、台账集在 t=1.6~2.6s 掉到 **0/34**；修法开 ⇒ 首帧即目标值、最低 5/34。
`window.__snapDbg()` 必须报 `state:"ok"`，否则整轮 A/B 不作数（表没加载 = 没在测这个补丁）。

**踩坑记录**：
- **"屏幕面积"当判据是死的**：Cubism 里不透明度 0 的 ArtMesh **顶点塌到原点**（灭着的片在任何姿态导出里都是
  `[0,0,0,0]`）⇒ 拿不到灭着那组的尺寸，面积/个数都比不了。要量几何只能在真的点亮它的那一拍读。
- **"亮着的 mesh 个数"也不够**：`Param25` 0→0.1 时 A 组 5 片灭、另一组 5 片正好亮 ⇒ 个数不变。
- **钉值时长的上限是"该值在源 clip 里真正恒定的秒数"**，算法是**连续等值键段的跨度**，不是"第二个键在哪"：
  `home` 的 `Param25` 在 0/1.55/1.617/2.9 四个键上都是 0.5，只数到第二个键会把窗口算成 1.55s，
  而实测淡化要跑满 ~2s ⇒ 后段漏回死区（本轮真实返工一次，改完最低 5/34 才稳定）。
- **排在钩子之后的写入层会盖掉钉值**：库的次序是 motions → (我们) → saveParameters → expression → **eyeBlink**
  → focus → naturalMovements → physics → core.update ⇒ 眨眼/口型/物理类参数用这层钉不住
  （`ParamJTEyeOpen` 进了表但无效，就是这个原因）。
- **headless Chrome 的磁盘缓存会伪装成"补丁没生效"**：固定 `--user-data-dir` 下改过前端后，探针端出的是
  旧 `index.html`，症状是"行为与改动前逐帧相同"，而且调试函数报 `NO-SUCH-FN` 看着像代码没跑。
  ⇒ 探针 URL 一律带 `?v=<epoch>`；判"前端补丁无效"之前先证页面是新的。

**涉及文件**：`scripts/diag/l2d_snap_criterion_scan.py`（新）、`scripts/diag/l2d_part_flicker_probe.py`
（新臂 ⑨ `--deform` / 新臂 ⑩ `--snapab`、URL cache-buster）、`gallery_src/index.html`（补丁 ⑦ +
`window.__snapDbg`/`__snapOff`）、`Output/Live2D/gezi_2/gezi_2.snapswitch.json`。
根因与证据链见 `docs/TROUBLESHOOTING.md` §123 追加-IX/X/XI。


### WF-37: UnityPy 跨包 PPtr 解析怎么打通、怎么验到敢拿去装配房间（2026-10-08）

适用：一个包里的对象大量**外链**到别的包（`MeshFilter.m_Mesh`、`MeshRenderer.m_Materials`、
prefab→res 材质），必须按 `(file_id, path_id)` 跨包取回真实对象。§8 那条「FileID=N →
`externals[N-1]` 的 CAB 名」是同一件事的**单包版**；本条是**一个 bundle 多个 SerializedFile +
目标散在几百个包里**的通用版。靶子 = `dorm3d/scenesres/scenes/tianlangxing_db/siriushostel/map_siriushostel_01_scene`
（348 个 MeshFilter 全是外链）。

**五条实现要点（顺序即依赖）**

1. **一个 bundle 里有多个 SerializedFile**。该场景包 `env.file.files` 是 **4 个成员**：
   主包 `CAB-x`（2332 对象 / 357 externals）、`CAB-x.sharedAssets`（32 / 360）、**两个 `.resS`**。
   ⇒ 遍历必须 `isinstance(v, SerializedFile)`：`.resS` 是 `EndianBinaryReader`，取 `.externals` 直接
   `AttributeError`；而 `.sharedAssets` **不报错、安静地给一份错位表**（上一轮就是这么把 `WallLeft`
   算成 `fbx_db_pail01_fbx` 的）。
2. **归属白拿**：`ObjectReader.assets_file`（**带下划线**）逐对象给得出所属 SerializedFile，
   实测 2332 + 32 = 2364 与两份文件的对象数完全吻合。
   ⚠️ 恒 None 的是 **PPtr** 上的 `assetsfile`，两者不是一个东西——交接文档据此写的"要自己遍历建
   path_id 归属表"是不必要的。归属表仍要建，但**键必须是 `(assets_file.name, path_id)`**，
   因为两个 SerializedFile 的 `path_id` 会撞车。
3. **externals 只取引用方自己那份 SerializedFile 的**，`file_id` **从 1 起** ⇒ `externals[file_id-1]`；
   `file_id == 0` 是**同一份 SerializedFile**（不是"同一个 bundle"）。
4. **落点按 CAB 名索引本地包，并且按名字精确选目标 SerializedFile**（绝不 `next(iter(...))`）。
   索引要给**每个** SerializedFile 单条登记（含 `.sharedAssets`）；作用域除资产前缀目录外，
   还要用 `Output/dependency_manifest.json` 里该包的 `deps` 补齐**类目之外**的依赖
   （本例补进 `files/AssetBundles/custom_builtin` 与 `font/zhunyuan`，各 1 条 CAB）。
   实测：474 个 dorm3d 包 + 451 个依赖包，现扫 **19.8 秒 / 479 条**——**每次都现扫，不吃缓存**
   （吃缓存就是"改了索引层忘了刷缓存"的静默失败面）；旧缓存只作对照用。
5. **内置外链单独归桶**：`FileIdentifier.path` 不以 `archive:` 开头的（如 `unity default resources`）
   **盘上没有对应文件**。它既不是失败也不该进判据分母，更不许留结构合法的占位对象。

**判据（七条同时绿，`exit 0` 即打通）**
| 判 | 内容 | 实测（房间 1） |
|---|---|---|
| J1 | 分桶求和 == MeshFilter 总数（无静默丢失） | 348/348：外链命中 315 / 本包 2 / 内置 31 / 未命中 0 |
| J2 | 固定种子抽 20 条解析出 `(包, 网格名, 顶点数)` 且语义相符 ≥18/20 | **20/20**（`--seed 20261008`） |
| J3 | 同批走 UnityPy 原生 `pptr.deref()`（先把依赖 `load_file` 进同一个 Environment）逐条比对 | 不一致 **0/20**，装载 20 包 0.8 秒 |
| J4 | 反向对照：换**错的那份** SerializedFile 的 externals ⇒ 必须塌 | **0/20**（20 条全 `notfound`） |
| J4b | 反向对照：同一份 externals 下标 **±1** ⇒ 必须塌（钉住"`file_id` 从 1 起"） | +1 得 0、−1 得 0 |
| J5 | 顶点数两条独立锚点：`m_VertexData.m_VertexCount` == UnityPy 自己 `export()` 出的 `v` 行数，且 `max(index) < 顶点数` | 不符 **0/20** |
| J6 | 自建索引与缓存索引键集对照（两套独立构建） | 仅缓存 0 / 同键不同包 0 / 仅自建 2（即依赖补齐那两条） |

资源口径：整轮 **34 秒 / 峰值 0.32 GB**（`scripts/diag/peak_mem.py` 量的），
180 个去重外链包、跨包加载 4.4 秒。

**踩坑记录**
- ⚠️ **语义判据吃命名约定 ⇒ 两头都会翻车**。规则 = 剥 `pre_/fbx_/mat_` 前缀与 ` (N)` 副本后缀、
  按非字母数字切词、**数字段去前导零**（`Chair_1` ↔ `fbx_chair01` 是同一个）、再要求
  **词元序列相等或互为子序列**（对象名里可插颜色词：`pre_oak02_green02_lod3` ↔ `fbx_oak02_lod3`）。
  用"序列"而不是"集合包含"，`WallLeft` ↔ `pail01` 这类真错位才必红。
  第一版按"剥前后缀完全同名"写，把正确的 `pre_oak02_green02_lod3` 判成不符 ⇒ **判据过严一样是错的**。
  全量 317 条里 27 条语义不符（`fbx_sence_xyd_tree_04_lod0` ↔ `fbx_oak01`、`fbx_Cloud_Layer_Top` ↔
  `CloudMesh_Top`、`pre_db_decoration03a` ↔ `fbx_db_decoration03`、两条指向场景 `Combined Mesh`），
  逐条打印出来看过：是**美术复用资产 + 实例名不同**，不是解析错 ⇒ 这类"命名差异"要列出来人判，
  不许悄悄放宽规则把它放行成绿。
- ⚠️ **一条反向对照不够，要两条**：J4（换错 SF）20/20 全 `notfound`，看着"塌得干净"，
  其实只证明了"错表会连包都找不到"；真正把 **1-based 下标约定**钉死的是 J4b（±1）。
  与 §116 那批"变异样本必须真的改变被测物理量"同族——**对照的强度要按它排除了什么来写，不按它红了没有来写**。
- ⚠️ **`load_file` 之后 `env.objects` 不再只含源包对象**：装进 359 个依赖包后直接遍历数出 **630 个
  MeshFilter**（源包只有 348）。取样/计数必须先按 `assets_file` 限定回源包，否则连分母都是别人的。
- **解析率 ≠ 可画率**：只按激活位过滤会多画东西。348 个 MeshFilter 里 49 个对象关着（首因 39 个在
  `night` 子树）、26 个 `MeshRenderer.m_Enabled=0`、4 个所在层不在相机 `cullingMask` 里
  ⇒ **该画的只有 269 个**，三条要分开计数打印（**§125**）。
- ⚠️ 本 WF 早先那句"31 条内置外链里 30 条是激活态 ⇒ 房间壳体混了 Unity 原语，要真网格只能从设备取
  `unity default resources`（新的未决项）"**已于同日改判（§125）**：补全三重门控后那 31 个内置原语
  **一个都不画**（全在 layer 16/28、其中 26 个渲染器禁用）⇒ 它们是碰撞/标记物，
  "取内置资源"这条未决项**作废**；当时判错正是因为只查了 `m_IsActive` 这一条。

**涉及文件**：`scripts/diag/dorm3d_pptr_resolve.py`（本 WF 正本，只读；`--scene/--root/--sample/--seed/--out`），
产物 `.diag/dorm3d_pptr/resolve_report.json`（不入库），对照缓存 `.diag/dorm3d_cab_index.json`（不入库），
`scripts/diag/peak_mem.py`（资源口径），`Output/dependency_manifest.json`（依赖清单）。
相关：**WF-32**（单包版材质 PPtr + 装配验收）、**WF-28**（定向拉依赖闭包）、**§116**（假读数族，本轮追加一条否证）。

---

### WF-38: Unity 场景包 → `room.glb`：房间级装配怎么落地、怎么验到能交人目视（2026-10-08）

适用：把一个**场景包**（几百个 `GameObject` + `MeshFilter`/`MeshRenderer` + 灯 + 外链网格/材质/贴图）
装配成前端可显示的 glTF。与 **WF-32**（单个蒙皮角色）的区别：这里几何是**静态网格 + 跨包外链 + 实例复用**，
所以新增三件事——激活态过滤、材质/贴图的跨包解析、以及"画面到底有没有东西"的可测判据。

**六步（顺序即依赖）**

1. **解析层直接复用 WF-37**（`diag/dorm3d_pptr_resolve.py` 的 `Resolver` + 现扫 CAB 索引），
   不要在新装配器里再写一套 externals 处理。⚠️ `file_id==0` 的"本包"是**引用方自己的 SerializedFile**，
   不是"这次打开的源包"——材质自引用贴图就在材质包里，查错表会**静默丢贴图**（§124）。
2. **几何用 UnityPy 自己的 `MeshHelper.MeshHandler` 解码**，不要用 §116 的反解路径：
   房间 FBX 网格的 `ChannelInfo.dimension` 是打包字节（实测读到 52，UnityPy 按 `& 0xF` 用），
   反解的"非末段通道宽度可整除推出"前提不成立 ⇒ `KeyError`。
   换解码器**必须先做跨实现对齐**：在天狼星 `body` 上比 `MeshHandler` 与反解结果
   （13,412 顶点 / 首顶点权重 `(32768,32767,0,0)` / 骨号 `(27,31)`）逐位相同才允许换。
   `MeshHandler` 还顺手覆盖了 `.resS` 流式顶点数据（角色包是内联、房间包是流式，两种都有）。
3. **"画不画"要过三重门控**（§55 那条只查激活位的规则在 3D 侧不够用，见 **§125**）：
   ① `GameObject.m_IsActive` × 全祖先；② `MeshRenderer.m_Enabled`；③ `GameObject.m_Layer` 是否落在
   `Camera.m_CullingMask` 里。房间 1 实测 348 → **该画 269**（49 关着 / 26 渲染器禁用 / 4 层被剔除），
   三条**分开计数**打印；合并成"跳过 N 个"就看不出漏了哪一条。
4. **实例去重按 `(网格, 材质序列)` 组合键**，不是按网格名：一个网格可被多个节点复用（吊灯 8 盏共用 1 份几何），
   而同一网格在不同对象上可挂不同材质序列。299 个对象 → 205 个 glTF 网格 / 219 个 primitive。
5. **坐标系沿用 WF-32 的镜像 X**（顶点/法线 x 取反 + 换绕序 + 节点 TRS 同一套），
   并把它做成可关的 `--no-mirror`，**专门用来给判据做反向对照**（见下）。
6. **产物交人看之前，先把它变成数**：装配器另写一份 `room.glb.truth.json`——
   里面的 primitive 数 / position 计数 / 三角数 / 世界盒 / 每对象中心与尺寸 **全部来自 Unity 声明字段**
   （`m_VertexData.m_VertexCount`、`m_SubMeshes.indexCount`、`m_LocalAABB`、Transform 链），
   **不是**我写进 GLB 的那份字节。前端探针（`diag/dorm3d_room_probe.py`）拿 GLTFLoader 的真实读数去对这份真值。

**判据（`exit 0` 即通路成立）**
| 判 | 内容 | 房间 1 实测 |
|---|---|---|
| V0 | 门控口径求和：`348 = 该画 269 + inactive 49 + renderer_off 26 + layer 4` | ✅ 269/49/26/4 |
| V1 | 装配期锚点：解码顶点数 == 源包声明、submesh 数 == `m_SubMeshes`、实算顶点盒 vs 声明 `m_LocalAABB` 偏差 <3% | 不符 0 / 0 / 0 |
| V2 | 字节级回读（`--verify`）：bufferViews 挂上、accessor 不越界、属性名按规范白名单、索引 < 顶点数、PNG 魔数、无 orphan mesh | 全过 |
| V3 | **镜像锚点**：glTF 世界盒（文件字节算）vs Unity 世界盒（源包算），应 x 反号、y/z 相等 | 有效 264 条，最大相对差 **7.4e-08** |
| V4 | 前端 Mesh 对象数 == 真值 primitive 数 | 329 vs 329 |
| V5 | 前端 Σ `position.count` == 真值 | 219,964 vs 219,964 |
| V6 | `renderer.info.render.triangles` == 真值（所有对象 `frustumCulled=false` ⇒ 恒等而非"至少"） | 121,321 vs 121,321 |
| V7 | 前端非占位世界盒 vs 真值世界盒，逐轴相对全场景跨度 <0.5% | 逐轴吻合 |
| V8 | console 零 error；游戏机位落笔占比 ≥0.15 | 0 条；0.546 |
| C1 | 反向对照：指向不存在的 glb ⇒ V4/V5 计数必须归零 | Mesh 0 / position 0 ✅ 红得对 |
| C2 | 反向对照：摘掉所有灯 ⇒ 落笔占比必须塌 | 0 ✅（改判据前它报 1.0，见 §124） |
| C3 | 反向对照：`--no-mirror` 版必须被 V3 判红 | 最大相对差 5.8e-02 ✅ |

**踩坑记录**
- ⚠️ **三条"结构合法、数字全绿、画面是错的"同族假绿灯**（详见 §124）：`self` 解释错 ⇒ 93/141 材质静默丢贴图；
  落笔占比按"与背景不同"数 ⇒ 一片漆黑报 1.0；镜像锚点在几何中心含原点时**退化恒真** ⇒ 反向对照假通过。
  ⇒ 每条锚点都要**自带敏感度声明**（剔除给不出证据的样本并打印剔除数，有效分母不足就判红）。
- **世界盒会被户外布景撑爆**：房间 1 的场景里 `pre_ship01` 在 280 单位外、`fbx_Cloud_Layer_*` 在 ±200 的 y 上，
  全场景盒跨 1400 单位 ⇒ 取景/截图必须按**室内子集**（对象中心距 ≤15，实测 247 个）来定，
  否则相机一退就退到太空外面（与 Spine 那条"恒不渲染的巨幕遮罩撑爆取景"同族）。
- **场景里那台 `Camera` 不能当取景权威**：它的 TypeTree 里没有 `m_FieldOfView/m_Near/m_Far`（只有镜头/物理相机类字段），
  位置与朝向可用（机位 (-2.32,1.38,-2.67) 看向 +Z，眼高 1.38 m 合理），**FOV 只能由观看者定**并在报告里写明。
- **Unity 内置原语（`unity default resources`）盘上没有文件**：31 个对象（含 `WallLeft/Floor/Bed/Sofa`）
  只能用带 `extras.placeholder` 标记的单位立方体占位，**不算已还原**；它们按 path_id 只分 3 组
  （10202×28 / 10206×2 / 10209×1），要真网格得从设备取内置资源文件。占位对象的 24 顶点/12 三角
  会计入总数（真值里用 `placeholder_basis` 注明），但**不进世界盒**。
- **观感 ≠ 通路**：以上全绿只证明"几何/材质/贴图/摆位搬对了"。画面与游戏差的是**光照模型**——
  包里 21 盏灯只有 5 盏是激活态（12 盏属夜版、4 盏是 glTF 没有的 Area 面光源），
  且 Unity 光强与 glTF 量纲不同。补 `AmbientLight` 只是给对照看明暗关系用的，**不是包里的数据**，
  截图文件名用 `shot_amb_*` 与 `shot_good_*` 分开。

**涉及文件**：`scripts/dorm3d_room_to_gltf.py`（装配器 + `--verify` + `--truth-out` + `--no-mirror/--include-inactive` 对照开关）、
`scripts/diag/dorm3d_room_probe.py`（three.js 验收 + CDP 截图 + C1/C2 对照）、
`scripts/diag/dorm3d_pptr_resolve.py`（WF-37 解析层，本轮修 `self` 语义）、
产物 `.diag/dorm3d_room/{room.glb,room.glb.truth.json,harness.html,shot_*.png}`（不入库）。
相关：**WF-37**（跨包 PPtr）、**WF-32**（角色级 GLB 装配与回读纪律）、§124、§116、§55。

**追加（2026-10-08 光照轮）：Unity 烘焙 lightmap 怎么接进 glTF/three.js**

- **glTF 核心没有 lightmap**（只有 occlusion/emissive），所以：页号写进 `material.extras.unityLightmapPage`、
  每 renderer 的矩形 `m_LightmapTilingOffset` **烘进几何的第二套 UV**（`uv1*tiling+offset`），
  另出一份 sidecar（`room.lightmaps.json`：页清单 + 材质→页 + 每对象 ST 与 UV1 包围盒），
  由查看端 `material.lightMap = pages[page]` 挂上（three.js 用 `uv1` 属性采样）。
  ⚠️ **不要把 ST 放进 `texture.repeat/offset`**：一张 lightmap 在本房间有 **196 个不同矩形**，
  按矩形克隆贴图 = 196 次 1024² 上传；烘进几何只让几何数从 205 涨到 252。
  ⚠️ 代价是**几何去重键必须带上 ST**（否则同网格不同矩形会互相覆盖）。
- **只给烘过的对象发 `TEXCOORD_1`**：没挂 lightmap 的对象留着满幅 UV1 会让"带 uv1 的几何数"
  变成混合母体（本房间 117 个对象未烘焙）。
- **Unity 侧 `m_LightmapIndex == 65535` 表示"未烘焙"**（不是错误码）；`LightmapSettings.m_Lightmaps[i]`
  的字段是 `m_Lightmap / m_DirLightmap / m_IndirectLightmap / m_ShadowMask`（**不是** `m_LightmapTexture`）。
  本房间 `m_LightmapsMode=1`(Directional) 但 `m_DirLightmap` 全空 ⇒ 只有颜色页，第一版不补方向。
- **Area 灯（Unity type 0）不进 glTF 也不该补成实时灯**：Unity 的面光源只参与烘焙、运行时不发光，
  这正是"必须有 lightmap"的原因。实测 21 盏 = Point 7 / Spot 4 / Directional 6 / Area 4，
  激活且可映射的只有 5 盏。
- **判据加三条**（L1 去重材质数 / L2 带 uv1 的 primitive 数 / C3 页号敏感性 ≥0.6），
  加 `--verify` 里的**逐点** lightmap 锚点；三条新踩坑（异步贴图未等待、相对路径叠目录、
  无引用材质让母体差一个）记 **§124 追加**。

**追加（2026-10-09 透明与光照轮）：材质透明、泛光这条轴、以及"亮度对上了但东西不对"**

- **Unity 材质 → glTF `alphaMode` 只有两个可用信号**：混合方程 `_SrcBlend==5 && _DstBlend==10`
  （SrcAlpha/OneMinusSrcAlpha）与 `_BaseColor.a < 1`。⚠️ **`_Cutoff` 是陷阱**：本场景 348 个材质里
  289 个带着默认值 0.5（包括明显不透明的墙和木头），拿它当依据会把大半房间变成 alpha 测试。
  漏掉透明这条的真实后果见 **§126**。
- **回读断言里加一条结构性的**："baseColorFactor.a<1 却没标 alphaMode" 必须为 0 个——
  把这类错变成文件级红，而不是靠人眼在截图里发现。
- **three.js 对 `transparent + DoubleSide` 会画两遍**（源码里 `transparent && side===DoubleSide &&
  !forceSinglePass` 那个分支先背面再正面），于是"renderer 三角数 == 真值"这条恒等式必然翻倍。
  正确做法是**把期望值推出来**：前端自己数"哪些网格的材质是 transparent"，恒等式右边 =
  真值 + 这批网格的三角数。⚠️ 不许把恒等式放宽成 `>=` 或加容差——那是把仪器拆了。
- **three.js r152+ 按 `texture.channel` 选 UV**：手工赋 `material.lightMap` 时没设 `channel=1`，
  lightmap 会拿**漫反射 UV0** 采样，而"挂了多少材质/多少几何带 uv1"这类计数判据**完全无感**
  （本轮真实踩过：L1/L2 全绿而通路是错的）。⇒ 判据要直接量那个可观测状态：
  `channel===1 && geometry.attributes.uv1`，错的数量必须为 0（判据 L3）。
- **亮度对齐的度量必须含"形状"，不能是逐键绝对误差平均**：一个把整幅糊成白的档位
  在 9 键平均距离下拿过最小值 0.086（mean 0.549 已越过参照 0.473，却因其它键补偿而得分好）。
  改成 **分位数距离 (p05/p25/p50/p75/p95，Wasserstein-1 代理) + 饱和度误差**，再加一条
  **过曝闸**：亮部(>0.6)占比超过参照 1.6 倍直接判红（C7）。饱和度这项是最后才发现的：
  亮度分布逐位对上时 sat 仍只有参照的 44%（0.078 vs 0.178）——**度量对颜色是瞎的**。
- **轴之间有交互，"这条轴没用"的结论带前提**：单扫"灯×π / 去掉 1/d² 衰减"时 mean 0.184 vs
  基线 0.186（当时结论：调灯没用）；把泛光打开后同一组参数 0.316 → 0.549。
  ⇒ 端点+中点式的单轴扫描会漏掉非单调/有交互的映射，跨轴组合必须真的扫进网格里。
- **泛光是渲染端近似，不是包里的数据**（别把它写成"还原了游戏的光"）：本场景 109 个粒子系统
  只有 14 个激活，且激活那批全是交互标记（`vfx_cross01` ＋号、`vfx_tubiao*` 图标、`vfx_number01`
  数字、`vfx_trail/line` 轨迹）；`vfx_guangxian02`（光线）是**激活的空容器**，无子节点无渲染器。
  ⇒ 参照图窗边那道斜射光不在资产里，是屏幕空间后处理。
- **补光要有据**：把 `RenderSettings` 的三向环境光（`m_AmbientSky/Equator/GroundColor` +
  `m_AmbientIntensity` + `m_AmbientMode`）与灯的强度统计抄成一份 `room.render.json` 交给前端，
  别把猜的白色 `AmbientLight 0.6` 当数据（判据 R1/R2 保证读到了）。
  ⚠️ 这些颜色**按 sRGB 还是按线性进渲染器**是一条会改变结果的轴（本轮线性入明显更贴参照），
  别默认。Unity 的 trilight 在朝上的面会衰减到 sky 色（本包 sky=0），所以 `flat` 取 equator、
  `hemi` 取 sky/ground 两种都摆出来对比，并写清两者都不是 trilight 本身。
- **判据表新增**：R1/R2（包里读到环境光与灯统计）、L3（lightmap 通道）、
  C4（UV1 vs UV0 的**分布**差 >0.01——整页均值测不出来，实测 mean 只差 0.0046 而 med 差 0.021）、
  C5（灯=0 且无 lightmap 且无环境光时 mean 必须 ≈0）、C6（泛光必须抬升高光占比且不降 mean）、
  C7（过曝闸）。
- **已排除的假设（别重跑）**：① 方向性 lightmap —— 逐页核对 `m_DirLightmap` 全是 `PPtr(0,0)`、
  `m_ShadowMask` 空，确认前一轮"只有颜色页"的判断；② ASTC 解码坏掉（云发洋红、树发蓝）——
  逐通道数唯一值：云纹理 R/G/B = 247/227/168 级，室内墙贴图 R51-239/G47-228/B41-215 正常，
  全量扫描"带真实 alpha 且某通道几乎恒定"只有 2 张且本就是平色材质；③ "窗外海面在场景里只是
  被剔除"——`mat_db_sea01` / `WaterDepth_sh_day` / `WaterShoreSDF_sh_day` / `Sh_day_water_RampMap`
  全是**激活但无渲染器的空容器**，海面资产在 `scenesres/res/water/`（`watersurface_single`、
  `cloud`、`tex_water_*`）与 `res/rooms/*/water_system/`（`rampmap`、`waterdepthsdfmap`）单独成包，
  运行时才拼进来 ⇒ 那部分**不是还原而是补摆**。
- **依赖取法**：three 的 postprocessing 走 npm tarball
  （`https://registry.npmjs.org/three/-/three-0.160.0.tgz`；npmmirror 的 `dist.tarball` 是跳转页，
  `curl` 必须带 `-L` 否则只拿到 82 字节的 "Redirecting to..."），只取
  `examples/jsm/postprocessing/{EffectComposer,RenderPass,ShaderPass,MaskPass,ClearPass,UnrealBloomPass,OutputPass,Pass}.js`
  与 `examples/jsm/shaders/{CopyShader,LuminosityHighPassShader,OutputShader}.js`，版本必须与
  已 vendored 的 `three.module.min.js` 的 REVISION 对齐（本轮 r160）。
  ⚠️ 这批文件目前只在 `.diag/three/jsm/`，**未进 vendor 台账**（与 three.js 正本同一欠账）。

**再追加（同日 15:40-16:20）：透明其实有三个信号，窗外背景只能"补摆"**

- ⚠️ **上一条里"透明只有两个可用信号"这句话是错的**，被 C9 抓出来：加了补摆穹顶之后
  **像素一个都没变**，定位发现窗外云层 quad 被当成实心画，把近乎全黑的 RGB 糊在天空位置上。
  `mat_Layer_Day_*` 既没有 `_SrcBlend/_DstBlend`，`_BaseColor.a` 也是 1 ⇒ 前两个信号都抓不到，
  但它的 **baseColor 贴图自带 alpha**（云纹理 alpha 均值 0.066）。
  ⇒ 第三个信号：**贴图的 alpha 不是恒 255 就是混合材质**。补上后 BLEND 从 12 涨到 33 个。
  ⚠️ 这条判定必须**在贴图复用时也算**：只在"首次解码"分支里算会让走缓存的材质漏判
  （实测漏了树叶与花两种），所以要把"这张贴图带不带 alpha"记成一张按贴图键的表。
  回读侧配不变式：「baseColor 贴图自带 alpha 却是 OPAQUE」必须为 0 个。
- **贴图的 RGB 不一定是颜色**：`tex_Cloud_*` 在高 alpha 处 RGB=(218,2,136) 品红、
  `tex_birch04_leaf_diff` 的 B 通道恒 241-255 只有 13 个不同值 ⇒ 这类是自定义着色器的
  **分通道数据**（云密度/叶片次表面之类），按 albedo 用就得到红云与蓝树。
  着色器读不到时，做法是：**把推断放在查看端**（云按"纯白 + alpha 当密度"重绘贴图），
  并且配一条"开关前后分布必须不同"的对照（实测最大分布差 0.0387）——
  **不要把它烧进 GLB**，产物必须保持"包里是什么就是什么"。
- **窗外那片天海只能补摆**：本场景 `m_SkyboxMaterial` 是空引用，`res/water/` 里
  **全是贴图没有网格**（`watersurface_single`/`cloud`/`WaterDepthSDFMap` 都是 Texture2D），
  `RampMap`(256×2) 几乎全黑、是水深遮条不是海的颜色 ⇒ 海的颜色也只能从参照截图逐行取色。
  落地：查看端加一个半径 1500 的 `BackSide` 球面，纵向渐变（天顶 162,207,237 /
  地平线 198,223,243 / 海平线 120,196,223 / 近岸 171,229,233），`toneMapped:false`
  让它落在取到的数上；亮度高于泛光阈值 ⇒ 窗边自然溢出光晕，与参照一致。
- **加了查看端几何，模型侧计数判据要显式扣掉它**：护栏"换档位不许改几何计数"原本比的是
  `renderer.info` 的三角数，补摆穹顶一进（720 个三角）就把 `sky=1` 的档位全判成"改了模型"。
  ⇒ 计数母体改成 `renderedTris - backdropTris`，同时 J3 的期望值加上 `backdropTris`。
  这是"仪器要跟着语义改动重推"的又一例，不是放宽阈值。
- ⚠️ **面积类统计量受取景影响，取景不同就不可比**：参照截图里窗占画面近一半，
  而我们的分区机位是"站在房间中央朝家具簇看"，窗只占一小条 ⇒ `亮部>0.6 占比` 这类
  **面积量**的差距里混着取景差，不能全算成"光不够"。
  ⇒ 要继续逼近参照，先把验收机位对齐到游戏那台相机的构图（或反过来按截图摆机位），
  再谈亮度对齐；否则是在拿两个不同问题比数。

**再追加（同日 16:40）：取景要能被量，过曝闸要能约束选择**

- **"窗在不在画面里"要变成一个数**：JS 侧 `frameStats()` 与 Python 侧 `ref_stats()` 用
  **逐字相同的规则**数同一件事（`b>r+0.08 && b>0.55 && 亮度>0.5` ⇒ 天空/海面占比 `skyf`）。
  两侧同一把尺子是硬要求：不同规则的"占比"相减没有意义。
  量出来参照 1.9 / 6.2 / 11.2 / 14.5%，我们补摆天海之后只有 1.3~4.8%
  ⇒ 之前"C9 说天海没抬动饱和度"这句话从此有了可查的原因，而不是再去猜一档参数。
- **机位不要手调，也不要凭"看起来差不多"**：用窗外内容（船/地形/云/树/礁石）的世界质心定
  "外面在哪一侧"，在**留在屋内**的候选点里选视线与朝外方向点积最大的那个；点积 <0.3 时
  放宽 fov 到 80 并把点积打印出来。这样"厨房机位拍不到窗"会变成一行 `dot=-0.893, skyf=0`
  的量化事实，而不是看图时的一句"感觉不对"。
  ⚠️ 本场景那台 `MainCamera` 是 `active=false` 且 **TypeTree 里没有 m_FieldOfView/m_Near/m_Far**
  ⇒ 游戏相机参数不在包里，任何"对齐构图"都只能是按截图反推的近似，必须这么标注。
- **闸门必须约束选择，不能只是抱怨**：过曝/褪色判据要**先取消候选资格**（最差机位亮部 >1.6 倍
  参照，或 sat < 参照 60%），再在合格档位里挑最近。本轮的反例：一个 living 已经
  `hi6 74.5% / sat 0.046`（整幅糊白）的档位，在三机位平均下距离仍然最小而成为"最近档位"。
  ⇒ 两条同源教训：**聚合平均会藏掉单幅的失败**（要按最差机位判）；
  **只报红的闸门不改变输出，等于没有闸门**。

**再追加（同日 17:10）：我给一个统计量起了个它撑不起的名字，被参照图否证**

- `skyf`（"亮且偏蓝像素占比"）被我当成"窗在画面里占多少"用了，据此写下"kitchen skyf=0
  ⇒ 我们的机位没拍到窗"。**两头都错**：厨房参照图那 14.5% 根本不是窗，是**冷白色方格瓷砖墙**
  （厨房压根没有窗）；我们那侧的 0% 真正说的是"我们的瓷砖画得偏暗偏暖"。
  ⇒ 教训：**给统计量起名字之前，先拿一张"已知不含该物体"的样本量一遍**。
  一张反例样本就能判死"这个量在量我想量的东西"这句话，成本远低于事后纠错。
  现在这个量只作诊断（打印名改成"冷亮"），**不挂判据**。
- **机位改动必须自带"目标还在不在画面里"的自证**：为了把窗弄进画面，我把视线取成
  "簇方向"与"窗外方向"的角平分线——厨房这两方向相差 149°，一劈就把簇劈出了画面
  （`shot_zone_kitchen` 拍到的是壁炉墙与起居区）。
  ⇒ 加判据 **F1**：算完机位立刻反算"视线与该簇方向的夹角 ≤ 半视场"，越界即红；
  并且给角平分线设可用区间（`20° < ang ≤ 52°`，即两个目标都装得下才许劈），
  装不下就老实朝簇看。这类"生成器自己检查自己"的判据，比事后看图早一步。
- 修完之后三个分区机位的落笔占比 0.633 / 0.598 / 0.453（此前游戏机位只有 0.277），
  验收判据全绿。

**再追加（同日 18:30）：两条"通道语义"推断都要各自自证；旋钮写成互斥会让第二个静默失效**

- 窗外两处色差结案，依据都是"**这个通道的数据不像颜色**"：
  云纹理在高 alpha 处 RGB=(218,2,136) 品红；叶贴图 B 恒 241-255（只有 13 个不同值）
  且这三张叶材质**根本没有 `_BaseColor`**（`baseColorFactor` 为空 ⇒ 没有任何 tint 能解释蓝色）。
  做法：查看端按规则重画贴图（云=纯白 + alpha 当密度；叶=B 压到 `min(R,G)×0.25`），
  **不写进 GLB**。出图与参照同构（白云、绿树、蓝海、深红沙发）。
- ⚠️ **两个旋钮写成互斥条件，第二个就静默失效**：第一版 `LEAF = leafw && cloudw!=='1'`，
  于是"云和叶同时开"的档位里叶子纹丝不动。是 **C11（开关前后分布必须不同）** 报出来的
  （逐位相同 → 差 0.0000）。⇒ 每条"通道语义"规则要各自一条正则、各自计数
  （`cloudwMats` / `leafwMats`），并且**同一材质只改一次**（叶子重复改会越改越暗）。
- 打印旋钮生效数（`[旋钮自证] cloudw 换掉 N 个材质槽 / leafw 换掉 M 个`）时，
  **要说清这行是哪个档位打的**——只给 `pick=1` 的档位打印，就会拿"云档位的 M=0"
  去解释"叶档位"，读的人（包括我）一定误读。
- 饱和度这项仍未达标（最好档 sat 0.119 vs 参照 0.178），且**加叶子反而降了一点**
  （0.114 → 0.108）：参照的高饱和主要在**红沙发与暖木**上，我们那部分被泛光与白色环境光冲淡。
  这条不是通道语义问题，是"亮面面积与光色"问题，与 §127 那条平行光一起继续追。

**再追加（同日 19:10）：饱和度差不是泛光与环境光——两个候选原因都撞在"没有 TypeTree"这堵墙上**

- **否证：降泛光/降环境光修不好饱和度，而且剂量反应不单调。** 实测 sat：
  无泛光 0.114、泛光 0.2 → 0.112、0.35 → 0.111、0.6 → 0.108；把包内三向环境光乘到 0.6
  反而掉到 0.100。参照是 **0.178**。⇒ "白色泛光把红沙发冲淡了"这句话是我上一轮的猜测，
  被自己扫出来的曲线否证（**单调性都不成立，就更不是"再降一点"能解决的**）。
- **为什么追不下去（这是天花板，不是没努力）**：剩下两个候选原因都在 MonoBehaviour 里，
  而本场景包 **65 个 MonoBehaviour 带 TypeTree 的为 0 个**：
  ① `Skylight` / `BakerySkyLight`（第三方烘焙器 Bakery 的天光组件，决定烘焙时"天"有多亮多蓝）；
  ② URP `Volume` 后期调色（参照图那种高饱和 + 泛光乳白正是 color grading 的产物）。
  没有 TypeTree 就只能拿到裸字节，要读它等于逆向 Bakery/URP 的版本相关二进制布局——
  **不可验证**，不做。⇒ 结论写成限制：**室内亮度已经贴住参照（mean 0.463 vs 0.473、
  med 0.500 vs 0.500），饱和度差 0.12 vs 0.178 是当前技术路线的天花板**，
  不许再用"再调个常数"伪装成已还原。
- **分区亮度分布反转**（同一轮量出来）：平行光修好后 kitchen mean 0.567~0.628（亮部 43~55%）
  已**超过**参照厨房（0.437 / 26.4%），而 bedroom 0.351、living 0.369 仍低于各自参照。
  ⇒ 单一全局曝光修不好它（往上厨房更糊、往下卧室更黑），这是"哪些面吃到哪盏光"的分布问题，
  而它的答案同样在 Skylight 里 ⇒ 一并归到上面那条限制。
- 顺手记一条**取数陷阱**：`GameObject.m_Name` 会带尾随空格（本场景有 `"Skylight "` 与 `"Skylight"`
  两个），按名字等值匹配组件会静默漏掉一半；要么 `strip()` 要么用 path_id。


**追加（2026-10-10）：把 `room.glb` 接进画廊——机位表要在构建期落盘，vendor 台账全绿 ≠ import 闭包完整**

**目标**：房间不再是"我这边跑脚本才看得见"的产物，而是画廊里一页能转能看的场景。

**产物正本迁址**：装配器的 `--out` 默认值就是 `Output/gallery_v2/dorm3d/room.glb`。
`.diag/` 是临时区，**不能住唯一副本**——房间产物与四张 sidecar 全部落在运行目录的
`dorm3d/` 子目录下，页面用与自身同级的相对路径引它们：

| 文件 | 谁生成 | 页面拿它做什么 |
|---|---|---|
| `room.glb` | `dorm3d_room_to_gltf.py` | 几何/贴图/材质/灯 |
| `room.glb.truth.json` | 同上 | 页面自报计数与 Unity 侧台账对账（对不上直接抛错，不停在"看着能跑"） |
| `room.lightmaps.json` | 同上 | 5 页 lightmap 文件名 + 材质→页号 |
| `room.render.json` | 同上（`render_settings()`） | **包内** RenderSettings 三向环境光（trilight mode 3 / equator 色 / ×1.5）—— 环境光不许硬写进页面 |
| `room.views.json` | 同上（`zone_views()`） | 三个分区域机位（卧室/起居室/厨房），构建期算好落盘 |

⚠️ **机位表必须在构建期落盘**：`zone_views()` 原先只住在诊断脚本里，页面要用它就得反向依赖
`scripts/diag/`——那等于"产物本身跑不起来"。⇒ 算法正本迁到装配器，诊断脚本转调，构建时写 sidecar。
包里那台 Camera 的位置（`truth.camera.pos`）贴着一面墙，当默认机位第一屏会糊成一片白，
所以它只保留成「包内机位」按钮，**不冒充"游戏里就是这个视角"**。

**页面形状**（`gallery_src/room3d.html`，单文件，照 `backgrounds.html` 的规矩）：
- 只引 `theme.css` 的 token，组件规则里不写字面颜色；**WebGL 清屏色也从 token 取**
  （`themeColor()` 读 `body` 的 computed background），否则切「夜」时画布外围不跟着变，
  等于第二份配色真相。
- importmap 用**页面相对路径**：`"three":"./vendor/three/three.module.min.js"`、
  `"three/addons/":"./vendor/three/jsm/"`（与 vendor 台账里 Live2D 那条"不能用资源前缀拼 vendor"
  同一条规则）。
- 承重的一行仍是 `t.channel=1`（lightmap 走第二套 UV），且页面**自己量给自己看**：
  每个挂上 lightMap 的槽位都当场核对 `channel===1 && geometry.attributes.uv1`，
  把 `chanOk/chanBad` 导出到 `window.__ROOM3D` 并印在 HUD 上。
- 三条"推断"（窗外天海 / 白云 / 绿叶）**默认全关**，按钮上带 `推断` 角标，开着时 HUD 明写
  "当前画面含手摆窗外天海 —— 非包内数据"。重画只活在查看端，**不烧进 GLB**；
  且关掉必须还原原图（`origMap` 存原始 `m.map`），否则"开关"是单向滤镜、自证就假了。
- 泛光滑杆恒走 composer（`strength=0` 也只是不加光），否则"泛光拉到 0"会同时换掉色调路径，
  那个开关就自证不了。

**必须同时改的三处登记**（漏一处就回到老静默失效）：
1. `scripts/deploy_gallery.py` 的 `FILES`（新页不进这里 ⇒ 既不被硬链也不被漂移检查看见）。
2. `gallery_src/index.html` 顶部「页面」按钮组加入口。
3. `gallery_src/vendor/MANIFEST.json` + 跑 `check_vendor_closure.py`（见 §128：
   **台账列全 ≠ import 闭包完整**，缺一个相对 import 会让整页静默不初始化）。

**验收判据**（`scripts/diag/room3d_page_probe.py`，34 条，打在真实页面上而不是 harness）：
- 字节级可达（含 `Range` 206 分段）——服务器"活着但半死"会吐 0 字节，光看 200 不够。
- **三方一致**：页面自报 ↔ 按 glTF 规范独立解析 GLB 本体 ↔ Unity 侧台账。
  ⚠️ GLB 本体那一栏必须按 **GLTFLoader 的实例化口径**算：单 primitive 的 mesh 直接挂节点，
  多 primitive 拆成子 Mesh，**同一 mesh 被多个节点引用会各实例化一份**。
  实测本产物 primitive 本体只有 279 个，按节点展开是 299 个 Mesh / 219244 顶点，
  正好等于台账的 `prim_total/pos_total`——拿 279 去比会**假红灯**，
  红到一定程度人就会去放松判据（那才是真正的失效）。两种口径同时报出来。
- lightmap：`channel===1`、`chanBad===0`、`lmSlots===chanOk`（没有漏量的槽位）、
  `lmMats`（唯一材质数 112）与槽位数（212，因材质复用而更大）**不许混用**。
- 机位表：sidecar 三个分区齐、`ang_cluster ≤ half_fov`（这一簇真的在画面里）、
  页面相机落在 sidecar 声明的坐标（偏差 <1e-3）、点每个机位画面都改变。
- 三个推断开关：先判"点击真的落地"（`S.on[k]` 由 False 翻 True），再判"画面改变"，
  再判"关回去逐字节相同（可逆）"——见 §129，少了第一条，"开关无效"与"探针没点到"同形。
- 反向对照：关 lightmap、泛光 0.6→0、曝光 1.2→2.0 都必须改变画面；不改变的旋钮是死块。
- 取样必须落在稳定帧上：`stable()` 重试到连续两次逐字节相同，取不到就显式判红并停
  （**绝不允许 `None` 参与比较**，那会同时造出假红与假绿）。

**涉及文件**：`gallery_src/room3d.html`、`gallery_src/index.html`、`scripts/deploy_gallery.py`、
`scripts/dorm3d_room_to_gltf.py`（`--out` 默认值、`render_settings()`、`zone_views()`、
构建期落 `room.render.json` / `room.views.json`）、`scripts/diag/dorm3d_room_probe.py`
（改从产品目录取产物、机位算法转调装配器）、`scripts/diag/room3d_page_probe.py`、
`scripts/diag/check_vendor_closure.py`、`gallery_src/vendor/MANIFEST.json`。
调试截图：`.diag/dorm3d_room/view_*.png`、`page_with_inference.png`。


**追加（2026-10-10 第二轮）：行走漫游 + 角色接进页面——两条"包里读不出来"的东西要分开标注**

### 行走漫游

实测轨道操作三条都通（左键旋转 / 右键平移 / 滚轮缩放，逐条用真实鼠标事件量过画面变化），
所以"想移动机位"要的是**走进屋里**，不是换一种环绕方式。

- **手搓，不用 `PointerLockControls`**：① 那要多纳管一个 vendor 文件，而"按名字挑文件、
  没验 import 闭包"正是同一天刚踩的整页静默不初始化（§128）；② 指针锁定在无头浏览器与
  内嵌视图里不可靠，验收会退化成"我没法测"。⇒ 按住左键拖动转向 + WASD/QE + Shift 加速 +
  滚轮调速度，零新依赖、每条行为都可测。
- **朝向只从一个来源推**：先把 `yaw/pitch` 写进 `camera.rotation`（`'YXZ'` 序），
  再问 `camera.getWorldDirection()` 拿前方、与世界上方向叉乘出右方。
  自己按三角函数推轴就是 §127 那个灯朝向 bug 的形状。
- **`dt` 上限给 0.1 不是 0.05**：无头浏览器 rAF 稀疏，夹太狠会让"按住 0.8 秒"只走出**一个 tick**
  （实测位移 0.110 m = 恰好一帧），移动速度就随帧率下降而变慢——那是产品 bug，不是测试该迁就的行为。
- **判据必须落在"帧数确实推进了"上**：页面导出 `S.frames`，探针先断言按住期间 ≥3 帧，
  再谈位移。否则"没位移"到底是产品坏了还是根本没跑帧，两者同形。
- 反向对照：**切回环绕后按住 W 相机必须不动**（证明行走监听器没有常驻生效）。

### 角色（天狼星）

**她不在房间场景包里**：`map_siriushostel_01_scene` 的 623 个命名对象里一个角色都没有，
只有两盏叫 `CharacterLight` 的**后期体积**（挂在 `Settings/…/VolumesWithLights/GlobalVolume` 下）
——按名字把它当角色锚点就会把她摆到错地方。真正的东西分两处：

| 内容 | 来源 | 落到哪 |
|---|---|---|
| 模型（153 节点 / 5 网格 / 5 蒙皮 / 10 primitive / 9 内嵌贴图，9,654 KB） | `dorm3d/character/tianlangxing_db/{res,prefabs}/tianlangxing_noshoes` | `Output/gallery_v2/dorm3d/tianlangxing.glb`（`dorm3d_to_gltf.py`，与房间同一套镜像约定） |
| 摆位：根节点 `Player` + 四个 `PlayerPoint`（父节点 `Bed`/`Chair`/`DormLvPerfomance01`/`Default`） | `map_siriushostel_01_base_scene`（1,025 个对象，**不是** `_scene`） | `room.character.json`，构建期由 `character_placement()` 落盘 |

- **镜像与全项目一致**：`M_gltf = C·M_unity·C`（`C=diag(-1,1,1)`）是**每个节点局部 TRS 上的对合**，
  所以"逐级镜像后再复合"与"整体镜像"等价：位置 x 取反、四元数 `(x,y,z,w)→(x,-y,-z,w)`、缩放不变。
  ⚠️ 复合完之后再翻一次 x 等于镜像两遍 = 没镜像（本轮差点写进去）。
  矩阵是**行向量约定**（点写成 `p·M`），"+Z 的像"取**第三行**，不是第三列。
- **摆位有跨源锚点，不用目视赌**：`床边` 的 `PlayerPoint`（从 `_base_scene` 的 Transform 链复算）
  与房间 GLB 里 `Bed` 节点的世界位置（从 GLB 节点 TRS 复算）相距 **1.63 m**——
  正是"站在床边"的量级；x 镜像若算错会差 4 m 以上。两条路径独立，一个错了就对不上。
- **顶点必须报两个口径**：Unity 子网格是"同一份顶点缓冲 + 各自索引区间"，
  装配器为每个 submesh 出一个 primitive、都指向同一个 POSITION accessor ⇒
  按 primitive 求和 45,058（face 2260 被数 5 遍），唯一 accessor 求和 22,606
  （= 源包逐网格声明值之和，`--verify` 那条腿守的就是这个）。只报一个必然报假红。
- **两处"包里读不出来"的东西要分开标注，不许混进"包内数据"**：
  ① **动画**：48 个 `AnimationClip` 曲线全为 0 条、数据在 `m_MuscleClipSize`（Humanoid 肌肉格式）
  ⇒ 页面只能是 setup pose，HUD 直接写"setup pose（动画未导出，Humanoid 肌肉格式）"；
  ② **模型自身前轴**：没有任何字段声明她的局部前方是 +Z 还是 -Z ⇒ 留一个 `MODEL_YAW_FIX` 常量，
  初值 0，靠目视定；非 0 时 HUD 要打印"含目视校正 X rad，非包内数据"。
  本轮目视结果：`默认` 站位正面朝镜头 ⇒ 与场景约定一致，校正量保持 0。
- **站位各自带朝向**：第一版只抄了 `pos`，坐椅子会面朝错方向；补抄每个 `PlayerPoint` 的 `+Z` 后
  yaw 是 `[0.0, 0.0, 2.2396, 2.4391]`。判据跟着加两条：站位 yaw 不得全相同、
  页面落点与朝向必须逐个等于 sidecar 声明值。详见 **§131**。

### 判据（这一轮新增的几条）

- 角色开/关必须**逐字节可逆**（证明没有残影），且"开角色 ⇒ 画面里真的多了一个人"。
- 切站位时"画面必须改变"这条**只在她于画面内时**成立——页面把她的位置投影到 NDC 导出
  `onScreen`，画面外就打印一句"不要求画面改变"。判据的红/绿必须能区分
  "产品坏了"与"这次本来就不该有反应"。
- `GLB ↔ 源包` 这条腿**当场跑**（探针起 `dorm3d_to_gltf.py --verify … --against …` 要求 exit 0），
  不引用上一轮的结论。

### 涉及文件（本轮）

`gallery_src/room3d.html`（行走模式 + 角色组）、`scripts/dorm3d_room_to_gltf.py`
（`character_placement()` / `base_scene_path()` / 构建期落 `room.character.json`）、
`scripts/diag/room3d_page_probe.py`（§5c 行走 13 条 + §5d 角色 15 条）、
`Output/gallery_v2/dorm3d/tianlangxing.glb` + `room.character.json`。
根因与踩坑见 **§131**。

---

### WF-39: 状态文档「重条目现场外迁」——先按字符量定位、再逐条验指针、一次多段落盘（2026-10-10）

**适用**：`PROJECT_STATUS.md` 破体量红线，而破线原因不是模块变多，是少数几条待办变成了多轮攻关流水。
与 `project-doc-governance` 技能的四步管线（路由表→分层归档→逐字抽取→提交）配套；本 WF 专管**第三步的定位与核验**。

**六步**

1. **量字符量，别只量行数**：按条目累加 `length($0)` 排序，找出"肥条目"。本项目实测 §6 的 265 行里
   4 条占 152 行（57%），其余 30 条平均 3.7 行且都带指针——**后者是健康的，别去动它**。
2. **核实归档闸门可用**：`grep` 逐字比对工具的行尾归一化是否落盘（本仓库 `core.autocrlf=true`，见 **§130**）。
   闸门不可用时"逐字无损"无法自证，整个动作不能开始。
3. **逐条验指针**：对每段拟删文本取 1~2 个特征串（数字 / 专名 / 报错原文）`grep -rl "<串>" docs/`。
   命中 ⇒ 已有孪生，可放心搬；不命中 ⇒ 按唯一副本处理（整段逐字进归档 + 桩里写**真路径**）。
   桩里原有的「逐字见 A2x 段」是手写断言，**必须实测**（本轮就抓到一条指错的，见 §132 根因 2）。
4. **一段 manifest 装多段，只干跑一次**：`segments` 支持任意多段（行区间为 `git show HEAD:doc` 的 1-based 闭区间、不得重叠）。
   先 `--manifest X.json` 干跑看「基线 N 行 → 新 M 行」，确认后 `--apply`，最后 `--verify`。
   **分几次写 = 几次基线漂移风险**；合并成一次写完再统一核对。
5. **桩的写法**：保留 ①条目标题+状态 ②**仍未解决/待拍板** ③**仍然生效的硬闸与警告**（如"归档闸开着不要跑 sync"）
   ④**唯一副本的数字**（如背景库四档命名比例 284/6/419/1190）⑤指向归档段号。
   过程叙述、已闭环的取证细节、溯源说明一律走人。
6. **补索引再收工**：`docs/archive/README.md` 的段号表加一行（A2x → 文件 → 内容），主文档头部膨胀台账压成指向它的单行。

**判据（没满足就不许说"已瘦身"）**

- `git diff --numstat PROJECT_STATUS.md` 必须是**局部**形状（本轮 `22  106`）；出现上千行 = 行尾归一化把全文件重写了，回滚重来。
- 工具四条核对全绿：① 基线每条非空行在"新主文档 + 归档"里逐行可查（缺失 0）② 每个归档块与 `git show HEAD:doc` 对应区间整块逐字相同 ③ 新增断链 0 ④ 写盘前 md5 与基线一致。
- 搬走的行数 + 留桩的行数 == 原区间行数（工具会打印，肉眼再对一次）。
- 桩里每个 `docs/…` 与 `A2x 段` 都能被 `grep` 到实体文件/实体内容。

**踩坑记录**

- 行数红线对**单物理行内的追加**完全失效（待办 5 是一行 5,681 字）⇒ 收尾要两把尺子一起看。
- `--apply` **之后**再手改主文档（更新生成时间、就地标记完成）会让本次 manifest 的 `--verify` 失效；
  ⇒ 顺序固定：干跑 → apply → **verify** → 然后才做头部/状态行的手改，且手改只用单点 Edit。
- 新建归档文件这条路工具支持（自带「逐字保留，勿编辑」文件头），但**别手工编辑已归档的段**——
  下一轮的整块逐字比对会红。

**涉及文件**

- `scripts/diag/doc_verbatim_archive.py`（干跑 / `--apply` / `--verify`）
- `PROJECT_STATUS.md`、`docs/archive/README.md`、`docs/archive/PROJECT_STATUS_*_逐字外迁_*.md`
- 本轮清单样例：`.diag/s6_heavy_archive_manifest_20261010.json`（7 段）
- 相关：**§130**（autocrlf 守卫）、**§132**（字符量定位与指针核验的由来）、AGENTS.md「归档 = 逐字外迁」四条核对


### WF-40: 网页液态玻璃——把「折射」做出来，并且诚实地量它（2026-10-10）

适用：给一个已有 CSS 站加"苹果同款液态玻璃"，或任何需要**背景像素被推开**而不只是变糊的前端效果。
方法论部分（怎么证明效果真的落到像素上、怎么量帧时不骗自己）比碧蓝航线这条业务更可复用，换项目直接用。

#### 一、先分清"糊"和"折射"，别在错的层上调参

`backdrop-filter: blur()` 在数学上只做邻域平均，**不产生像素位移**。所以"看起来还是毛玻璃"
不是参数没调好，是这一层根本给不出折射——再调十轮也是零。真折射只有两条路：

1. **SVG 位移滤镜挂在 `backdrop-filter` 上**：`backdrop-filter: blur(1px) url(#f)`，
   `#f` 是 `feImage`(法线图) + `feDisplacementMap`。Chromium 支持，Safari/Firefox 静默丢弃只留模糊。
   优点是折射对象是**身后整张合成好的画面**（含其它 DOM 元素）。
2. **WebGL 自己画**：把背景整幅搬进着色器，按元素矩形实时算位移。全浏览器一致，
   但只能折射"你自己画的那一层"，折射不了 DOM。

本地自用站选 1；要给别人看且在意 Safari 才考虑 2。

#### 二、法线图为什么必须自己生成

挂在 `backdrop-filter` 上的滤镜，它的 `SourceGraphic` 就是那张背景图——**滤镜拿不到元素自己的形状**。
所以圆角矩形那一圈的坡度只能预先算成一张图（R=横向位移、G=纵向位移，128 为零点），
再用 `feImage` 喂进去。三个必须记住的性质：

- **`feImage` 是拉伸铺满滤镜区的**，所以一张图可以给全网格用：卡片尺寸差十几像素只会让环跟着
  缩放几个百分点，**不会跑位**。按精确尺寸分桶是白做的过度设计，而且很贵（见踩坑）。
- 位移量 = `scale × (通道/255 − 0.5)`，图里峰值 ±127 ⇒ **最大推开 = scale/2 像素**。要 depth 像素就给 `scale=2*depth`。
- **梯度必须在 CSS 单位下差分**。先降采样坐标再用 1 图像素当步长，会把坡度按缩放比一起缩小，
  等于偷偷改了折射强度。正确做法：在 CSS 空间算 SDF，只是采样点落在低分辨率网格上。
- 滤镜区域要往外扩（本项目 132%），否则位移从元素外取像素会被裁成一条糊带。

#### 三、挂载时机：只在元素进视口、尺寸确定的那一刻

尺寸是滤镜的输入，所以只能在 `IntersectionObserver` 回调里量 `getBoundingClientRect()` 并建图；
出视口摘掉。**先 `style.setProperty('--lgf', url(#id))` 再加类**——顺序反了会让那条规则在空变量上
解析失败（见踩坑一）。切换主题/窗口尺寸要重建（本项目 `lgRefresh()` 清桶重挂）。

#### 判据（缺一条就不许说"效果做好了"）

1. **单变量渲染对照**：冻住动画（把模拟函数打桩成空，让循环继续画同一帧）、取景钉在某张卡的边墙上，
   然后**只切那一个开关类**，两帧必须不同。
   - ⚠️ 对照不许同时改两件事。「摘掉全部滤镜」vs「加折射」这种配法在任何实现下都恒绿。
   - ⚠️ 取景不许写死坐标。没人核对过那块区域里到底有没有边墙，"截图相同"就成了薛定谔的结论。
2. **几何对照**：给元素背后临时铺一层**棋盘格**（不许用单向条纹——竖边的位移是水平的，
   用横条纹测左/右边缘等于没测；也不许用两层 `repeating-linear-gradient` 叠——上层不透明会把下层整个盖掉），
   再把强度参数拉到"不可能看不见"的量级（本项目 80px）。看得见弯 = 几何对；看不见 = 实现错，与美观无关。
3. **结构闸门**：`getComputedStyle(el,'::before').backdropFilter` 必须含 `url(`，且每个 CSS token
   必须读到非空。这两条要在**跑测量之前**断言，不能靠事后看图。
4. **成本必须对着 vsync 预算读**：无头 `rAF` 不锁 60（静止能跑出 300fps），所以只有 ms 有意义、
   打印出来的"fps"要换算成 `16.7ms 预算` 去读。
5. **视觉语言的老判据要跟着换线索，但换完必须仍然能红**。`gallery_motion_probe.py` 第 ① 条原来拿
   "边墙 blur 半径 > 面板 blur 半径"当厚度线索——折射上线后它报红了，而**它报得对**（1px < 2.5px），
   只是前提作废：厚度改由像素位移承担。改成"挂 `url()` 折射 **或** 更强的 blur，至少占一条"，
   两条都没了照样报红。⇒ 改判据时要在代码里写清"这是重新表述还是放宽阈值"；放宽阈值等于作废判据。

#### 踩坑记录

- **CSS 变量解析失败 = 整条声明作废，不是只丢那一项**。`blur(var(--x))` 里 `--x` 读空 ⇒ 整个
  `backdrop-filter` 退化成 `none`，连原来的模糊都没了，且**零报错**。⇒ 每个 `var()` 写兜底值，
  滤镜那个变量的兜底故意写成"上一版的普通模糊"。详见 §133 坑一。
- **无头探针复用 profile = 吃磁盘缓存**，改了 CSS token 也读不到旧值。每轮 `rmtree` 换全新目录。
- **从 Python 逐条 `Input.dispatchMouseEvent` 并等 CDP 回复，只能跑到 ~30–40 次/秒**。若被测动画
  是由指针事件驱动的，这个速率就成了帧率上限，测出来的"渲染成本"是**你发事件的速度**。
  ⇒ 改在页面 rAF 里 `window.dispatchEvent(new PointerEvent(...))`：仍是页面自己的入口，但不受
  CDP 往返限制。本项目同一条件因此从 26.7ms 纠正为 6.6ms，"水面很卡"整条结论作废。详见 §133 坑三。
- **同时存在的"不同滤镜个数"是成本主因**，不是滤镜复杂度：5 张不同尺寸的法线图 = 83.4ms，
  2 张 = 30.1ms。宁可用一张略不准的图，也不要按精确尺寸分桶。
- **带 `mask-composite:exclude` 的那圈边墙滤镜本身就贵**（本项目 70 张卡 16.6ms），这个成本在
  换折射之前就存在。别把"卡"的锅甩给新加的折射——先量旧版同位置值多少钱。
- **折射的宿主必须选"背后是低频内容"的元素**（本项目最贵的教训，上线半天就撤）。卡片四周只有
  14px 缝隙、缝隙外就是邻卡的高对比立绘 ⇒ 折射把那些画面拽进边墙一圈，**读起来是污渍不是玻璃**；
  同一套滤镜挂在导航栏下沿（背后是滚动网格 + 天空渐变）就干净。⇒ 决定"给谁加折射"之前先看
  它背后有什么细节，这一步比调强度参数重要得多。详见 §133 四。
- **backdrop-filter 的成本单位是「盒子个数」，不是像素量**（§134 一）。同一批卡：改模糊半径 17→5、
  去掉遮罩、把面积砍到 1/26、把滤镜链缩成只剩 blur —— **四种改法一帧时都没动**；而"少挂一层"
  和"少挂 30 张卡"立刻见效。⇒ 排查这类卡顿先数有几个元素挂了 backdrop-filter，别去调半径。
  真正的结构性解法是**把 N 个盒子合成 1 个**（一层覆盖网格、用一张遮罩同时画出所有环）。
- **声称"某项删减无视觉代价"之前，必须把被删的东西原样注回去做一次像素比对**（§134 二，本轮自己
  抓自己一次）。删掉 `blur(2.5px)` 后我写了"这是免费的 10ms"，S 条件把它注回、卡片取景哈希立刻变
  ⇒ 只许说"省 3.3ms，代价是像素变了，交人眼判"。这和"对照不许同时改两件事"同源：**恒真的对照等于没对照**。
- **跨轮绝对值不可比，收益必须同轮内留对照**（§134 三）。同一份代码同一台机器，中位帧时在不同轮
  漂过 13.3 / 20 / 23.3 / 30ms。⇒ 每次测量都要在同一轮里带上"应当等价"的两条自洽校验
  （本项目是 B≡L、M≡C），它们过了才读别的数。

#### 涉及文件
- `gallery_src/theme.css` —— 几何旋钮与成本红线注释
- `gallery_src/index.html` —— `LG` 模块 + 两条 ②-b 规则 + `GLASS_IO` 挂载点
- `scripts/diag/glass_perf_probe.py` —— 四种模式：默认全条件对比 / `--phases` 拆四段耗时 /
  `--shots [--bend] [--depth N]` 成对取图 / `--caps` 写法隔离矩阵
- 成本账与被推翻的结论：**§133**
