# 碧蓝航线 AssetBundles 解包项目 — 进度总结

> **生成时间**: 2026-10-07 21:05
> 历轮会话流水（2026-09-20 ~ 09-27）已**逐字**外迁 `docs/archive/2026-09-26_PROJECT_STATUS_外迁归档.md`（A1~A15 段），§6 里已闭环的待办条目（★块第 1/2/3/4/6 条 + 既有待办第 9/11/16/17/18/19 条）于 2026-10-02 逐字外迁 **A21 段**（原位各留一行桩，编号不动）；2026-10-05 又把头部执行快照与 §6 第 13/14/22/25/26 条逐字外迁 **A22 / A22b 段**（`docs/archive/PROJECT_STATUS_条目13-26_逐字外迁_2026-10-05.md`），本文回到 400 行红线以内；2026-10-07（背景库 P2 收官轮）把 §6 已闭环的 ★块 1~4、待办 5 的 3D 宿舍流水、9/10/13/20/22/25/26/27/35 共 59 行逐字外迁 **A25 段**（`docs/archive/PROJECT_STATUS_已闭环条目_逐字外迁_2026-10-07.md`，四条核对由 `scripts/diag/doc_verbatim_archive.py` 自己跑），本文 399 行；
> 结论性知识在 `docs/TROUBLESHOOTING.md` §25~§67 与 `docs/WORKFLOWS.md` WF-14~WF-23。本文只留当前状态。
> **最近三轮**：天津风皮肤2「少了空中那份」真根因 = **层绘制序按名字后缀猜**（**§110** / **WF-27**）｜磁盘盘点定口径 + 换入备份闸落地（**§111** / **WF-28**）｜**静态立绘两处系统性偏差：Pillow 把 alpha 缩放两次（全库柔边偏淡 + 白雪皮肤2 细缝 + `gezi_2` 发错表情）、画布只取 max 不减 min（≈90 张被裁掉一块）** —— 4496 张全量重渲换入、换入四道检查全绿、索引逐字节不变（**§114** / **WF-29**）｜**背景库 P0~P4 收官**：导出层「同名覆盖」找回 15 种画面（**§118** / **WF-33**）+ 1,305 格人工标注落成页面默认「隐藏无角色」（**§119** / **WF-34**）。逐轮流水已逐字外迁 A22 / A22b 段。
> **用途**: 跨会话对接。**v1 时代历史已外迁 `docs/archive/PROJECT_STATUS_历史归档.md`**，本文只保留当前状态与主线。当前待办见 §6。
>
> **【其它待办】**~~§6.11 HitAreas 生成规则漏了 `touch_*` 组名~~ **已于 2026-09-22 修复落地**（13 模型真实判定区、全库 806/807）｜**官方交互层**：用 `CubismRaycastable` 真点击区替换现在猜的 `Touch*` drawable HitAreas、以及 `CubismExpressionController` 表情还原（注意运行时不读 pose3.json/exp 需验证）｜§6 待办 7「晶环联盟阵营码」三选一（A 逆向 sharecfgdata 加密 / B 走 381 旁路 / C 搁置）｜**剧情 CG 混进 `Paintings_v2/`** 的识别与分离（用户指出"脸黑的基本都是剧情 CG"，与缺脸是两类问题，见 §6.8）｜**结构隐患**：~~`azdata_*.json` 权威元数据源仍住在可被清理的 `.diag/`~~（**2026-09-24 已迁 `inputs/azdata/` + sha256 台账 `MANIFEST.json` + 校验 `scripts/diag/check_inputs.py`；数据本体仍不入库**，理由：9.2MB 游戏配置属资产、zlib 后 0.67MB 虽小但仓库原则是「只承载可复现的工具与知识」）——剩余一项：**21 个脚本硬编码 `D:\Azur Lane Assets` / `C:\Users\KLLM` 绝对路径**，其中 **13 阶段调用链上 9 个**
（`compose_paintings_v2`、`extract_spine_v2`、`reconstruct_live2d`、`extract_motions`、`fix_model3`、
`extract_cv_voice`、`export_dependency_manifest`、`mumu_sync`、`run_cg_export` 的 Chrome 路径，外加
vgmstream/ffmpeg 钉在 `C:\Users\KLLM\AppData\Local`）⇒ **换盘符或换用户名必炸，不是"迁移困难"**
（2026-10-01 应"这项目可迁移吗"实测；`update_pipeline.py`/`pipeline_panel.py` 自己走 `__file__` 推导，可迁；
数据 `files/` 28.9GB + `Output/` 约 45GB 不入库，需单独拷。建议：抽 `scripts/paths.py` 统一根目录 + 工具路径走 env 兜底）｜
**控制台执行侧（2026-10-01 体检，见 §71）**：13 阶段全串行、同一时刻 1 个子进程、**稳态约 0.7GB**，
跟 MuMu 不冲突（只有第 1 步要设备）；立绘 ≈1.25 秒/张 ⇒ 全量 4488 张 ≈1.5 小时、一把梭全量 4~6 小时
约 41GB 写入；`deps` 实测 3 秒 / 0.20GB（旧文档"依赖表 43 分钟"是报错的数）。§71~§75 那几轮的逐轮流水
已逐字外迁 **A18 段**，结论在 §71 / §74 / §75。
> **上一轮（2026-10-02）执行快照**：源包 92679 已同步、12 张新立绘已换入（4488→4500）、13 档全部有结论
> （`audio`/`cg` 只跑了只读半边）。逐轮叙述（§79~§85、控制台第五/六轮、§76 那条签字框接线缺失）已**逐字外迁 A22 段**。
> 仍要带的五条结论：① 权威皮肤表 = 设备侧 + 快照**逐字段合并**（`scripts/skin_table.py` 是唯一读取口）；
> ② 语音/台词归属只有**一份**三分类规则 `extract_cv_voice.row_candidates()`（`_hei` 不回退，它是剧情黑脸剪影）；
> ③ **画廊皮肤名不读 `ship_meta.json`**，label 回落与语音接不上同一个根因（§82）；
> ④ 跑流水线前先 `py -3 scripts/diag/test_pipeline_gating.py`（56 条判据）；
> ⑤ 语音产物**无需单独备份**（可确定性再生，体检 `scripts/diag/l2d_voice_inventory.py`），不可复原的只有 `inputs/azdata`。
跑之前先 `py -3 scripts/diag/test_pipeline_gating.py`（56 条判据）。**§76 又挖出一条接线缺失**：卡片上的「签字放行」复选框只有那颗「单独跑」会读，主按钮「重跑到待确认」发的 `approve` 永远是空的 ⇒ 用户勾了等于没勾。现在勾选存 `SIGNED`、主按钮带上并二次确认、主屏那行小字显示"已勾签字：…"；另外设备不可达且范围清单有效时 `pull` 判绿沿用清单，不再把已同步完的人卡在第 1 档。。**语音产物口径已定：无需单独备份**（可确定性再生，体检 `scripts/diag/l2d_voice_inventory.py`），不可复原的只有 `inputs/azdata`｜**控制台界面（2026-10-01 第五轮，见 §73 / WF-23 追加）**：用户否掉第四轮的「常驻漂移」（「我要的就是渐进式显影」）⇒ 星野**退回显影式**（静止全黑、划过才亮、约 520ms 淡净、淡净回**同一张**帧），配色保留 B 的**海军蓝 + 蓝白**（五个状态色 rgb 不动），光效回到 **conic 边框光束 + 控件内柔光 + 磁吸**；新增**三态自定义光标**（默认/可点/主行动，内联 SVG、深色描边打底）与**进度台**（只在真在跑时出现的一条细带：阶段 N/M · 已用 · 内存〔整棵进程树工作集〕· 剩余〔各阶段历史均值，缺样本报「≥」下限〕）；帮助抽屉里**为设计辩护的文案删掉**（用户要求别把提示词写进界面）。`scripts/diag/panel_ui_probe.py` 契约改回「渐进式显影」并新增 9 条进度台判据，**86 条全绿**。**控制台第六轮（2026-10-02，见 §82）**：说明书加「简洁 / 详细」两档（默认简洁只留 5 节、收起 7 节、选择写 `panel.helpmode`）；星空先量后改——量出来静止帧整屏只有 **67 个像素**亮着（占视口 **0.01%**），"常驻微光"这个开关是开着的但屏幕上没东西 ⇒ 常驻档改为按星型分抽（47→280 颗）、`AMB` 0.10→0.26、密度 2187→2843、显影半径 9→46/130→190、银河带从 30 个正圆改成沿带轴拉长的纤维 ⇒ 静止 3702 px（0.33%）而**淡净后与初始帧仍逐像素相同**；探针 103→**109 条**，并新增一道硬预检「served 页面必须与磁盘正本一致」（§72 烘死 HTML 那条坑本轮第三次撞上）。｜低优先：声优中文姓名回填、UI/图标批量导出。（背景侧已接线：画廊「背景库」页 + 配置表来的中文命名，见 §2.3 / 待办 8 / **WF-30**）

---

## 1. 项目概览

- 对碧蓝航线 Unity AssetBundle 解包、分类、导出、还原。
- 源路径 `D:\Azur Lane Assets\files\AssetBundles`，**196 类目 / 71,393 文件 / 21.89 GB**（2026-10-06 按类目清理：删 dorm3d/island/char/ui 共 **21,286 个源包 / 7.53 GB**，删除与登记同时落 `ledger/pruned.json` ⇒ `mumu_sync` 不再把它们报成"新增"；清理前 240 类 / 92,679 文件 / 29.42 GB。判据与过程 **§111 / WF-28**）；产物侧 `Output/` 48.5 GB，全仓约 **70 GB**（口径统一 = `scripts/diag/check_disk_footprint.py`，GiB）。
- **当前主线 = v2 数据驱动管线**（见 §9）：零猜测、零手调，已全量收官。

### 仓库治理 ✅
- 忽略规则收敛为「保留源码与文档，忽略游戏资产与生成产物」：忽略 `files/`、`Output/`、`tools/`、`.micode/`、`.mimocode/`。
- 生成产物与资产元数据已从 Git 索引移除，避免再次提交游戏资产。

---

## 2. 各部分进度

### 2.1 目录扫描 ✅
**71,393 文件 / 21.89 GB / 111 类**；输出 `asset_manifest.json`(20MB)。脚本 `scripts/scan_assets.py`。
> ✅ 2026-10-06 重建：上一份停在 06-19 的 86,849 / 26.62 GB（三个月没跑，且那批数里含已按类目删除的 dorm3d/island/char/ui）。新数与 `scripts/diag/check_disk_footprint.py` 独立量出的 71,393 **逐位吻合**（两套工具同一结论才算数）。⚠️ 顺带否掉我上一轮的一句话：这份 manifest **没有**"只扫一层"的缺陷（它的 `path` 用反斜杠，最深 9 层，20,407 条是嵌套包）——那条误判来自我用 `/` 数层级，属判据自身写错，见 §112。

### 2.2 立绘导出 ✅
43,520 导出 / 0 失败。脚本 `scripts/export_assets.py`（UnityPy）。（v1 合成产物已被 v2 取代，见 §9.2。）

### 2.3 背景导出 ✅
1,922 张（bg 1,305 + helpbg 364 + commonbg 111 + loadingbg 72 + loadingbg_hx 13 + newshipbg 14 + worldhelpbg 29 + lotterybg 12 + backyardbg 2）。输出 `Output/Raw/{bg,commonbg,loadingbg,helpbg,...}/`。
> 2026-09-16 随源包更新全量重导 1897/1897；修复 `export_assets.py` 漏设 `FALLBACK_UNITY_VERSION` 导致较新包加载失败的问题。**2026-10-07 补上缺的两张**：`bg_worldcruise_14` / `_tip` 源包是 09-24 拉进来的、比 09-16 那轮导出层新 8 天 ⇒ 不是解析失败，是**导出层比源包旧**；用新加的 `export_assets.py --target bg --only <包名>` 定点补导（`--target` 整目录重导会覆写 1,897 张已验证产物，不做），补完 2048×1260 / 684×156 与同系列 13 一致。⚠️ **`Output/Raw/` 现 = 纯背景层（1,922 png / 2.0 GB），不是 `files/` 的副本**：当前 5 档管线不写不读它，同日已删掉同一层里非背景的 87 件 / 80.1 MB v1 附属件。✅ **背景侧已接成画廊页**：`Output/gallery_v2/backgrounds.html`（主页「背景库」入口）读 `Output/gallery_v2/bg_meta.json`（1,922 条，缩略图 `bg_thumbs/<类目>/`，720px / 76 MB）。中文命名有**两条独立源、四档如实分开**：`exact 284 (15.0%)` 配置表字段整值等于文件名 / `baked 6 (0.3%)` **图内烤字**（`*_tip` 横幅，OCR 模板位 + 3× 目视双路径，`_11` 的「醺」字 OCR 读丢以目视为准）/ `inferred 420 (21.9%)` 同词根系列名 / `none 1,212 (63.1%)` 按类目中文说明；每条可回指"表.字段 行号"或取证方式，**背景不需要"还原"**（1 包 1 张 Texture2D 直出）。⚠️ 页面依赖 `Output/Raw/` ⇒ 已登记进 WF-15 承重白名单（删它=背景页全空，可 `export_assets.py` 重导）。判据 **WF-30** / 取证 **§115**（表引用那条源）+ **§116**（图内烤字这条源），含 §111 的 Raw 定性。✅ **2026-10-07 导出层「同名覆盖」已修（§118 / WF-33）**：`loadingbg` 22 个多图包里 **21 个装的是两张内容不同的画**（`bg_12` = 黑萌 / BSue 各一张 1920×1080，都带 ILLUST 署名），后写覆盖前写 ⇒ 每包静默丢一整张；另有 Sprite 的 tight-bounds 裁剪版顶掉整图（`bg_story_star0` 盘上 378×378 ← 包内 1280×720）与整包漏导（`login_260924`，两张 1920×1080）。修法是 `EXPORT_TARGETS["bg"]["dedupe"] = "distinct"` —— 按**解码像素指纹**分组，同内容只留最大的一份、**内容不同就全都留**（第 2 张起加 `__N` 后缀，配置表按名引用分不清是哪一张，所以 `__N` 不发「确定」名只发「推断」）；净增 23 张、5 张主图变大、缩略图 400→720px（76 MB）。⚠️ 源纹理天花板是包内 `ASTC_RGB_6x6`（`bg` 主力 1024×576），**「无损」只指 PNG 封装，重导不出更高清**。✅ **同日 P1 类目结构已落地**：一级只剩 **场景背景 1,305 / 登录·加载 72 / 其他 532** 三个类目（帮助/通用/世界地图说明/新舰登场/建造抽卡/后宅 6 类折进「其他」，点开走二级下拉）；`_hx` 并进登录类目（`dir` 是展示类目、`root_dir` 保留盘上真目录，详情层标「和谐版」）；⚠️ **合并制造出新重复**：登录类目 85 个文件里 13 个逐字节相同（`_hx` 那份 == 补回来的 `__N` 那份，甚至 == 另一名字的 `bg_8`）⇒ 索引按**内容**在合并后的类目内去重，**1,922 文件 → 1,909 条**（净增画面 15 种，不是 23 张）；场景背景的二级下拉按词根分（117 组 ≥2 张，**只有 13 组拿得出中文**，其余是拼音词根原文，等 P3 词典）。✅ **同日 P2「画面」筛选已落地**：1,305 张场景背景全部人工逐格标注（拼板 5×5、每格只印序号不印文件名，与 `_cg` 先验独立），加 17 格裁定 ⇒ **有角色 535 / 无角色 770**；登录与其他类目 **604 张从未标注 = 索引里不带 `has_char` 字段**（不是 0），默认视图照常显示、只藏"明确判过无角色"的那 770 张。发布件 `inputs/gamecfg/bg_char_flags.json`，标注正本入库 `annotations/bg_char_{adjudications,labels}.json`；`bg_meta.json` schema 3 + 五道闸门，`backgrounds.html` 默认档「隐藏无角色 1,139」+ 常驻「已隐藏 770 张」+ 详情层「画面」行（写明人工标注、非文件名规则）。判据 **§119** / 流程 **WF-34**。词根中文那条 **P3 已跑完**：拼音整值 18 组 / 150 张已发布 `inputs/gamecfg/bg_root_labels.json`，剩余 92 组（英文与缩写词根）**没有自动路**，只能人工词典或接外部维基。

### 2.4 音频导出 ✅
4,370 WAV / 0 失败 / ~14GB。`.b` 是 CRIWARE ACB，vgmstream 解码。分类 BGM 536 / CV 2,696 / Other 1,136 / SE 2。脚本 `scripts/export_cue_audio.py`。
✅ **2026-10-06 BGM 改档为 FLAC 无损**：`Output/Audio/BGM/` = 536 个 `.flac` / **6.87 GB（比 wav 省 41.5%）**，19.1 小时；逐条 `--verify-only`（产物 md5 对台账 + 整条解到 null）全绿，裸 PCM 回环抽 7 份（0.5→88.5 MB）逐字节相同。原 wav 与中途的 opus 版（1.06 GB）都已删，**净回收 12.81 GB**。三档实测对照：wav 11.75 / FLAC 6.87 / opus128k 1.06 GB。
✅ 新增画廊播放页 `gallery_v2/bgm.html`（潮汐进度条 + 雨后玻璃 + 三组筛选），**归属已补全**：355 首有出处（12 张配置表）、388 首有用途、40 首官方中文名（10 张专辑）、17 首连到舰名。⚠️ 两条硬教训：换格式必须重跑播放验收（`.flac` 默认 MIME 是 `audio/x-flac`，Chrome `canPlayType` 返回空串）；无损要靠裸 PCM 回环证明，不能靠格式名字。取证 **§112 / §113**。

### 2.5 Live2D 模型还原 ✅（2026-09-21 动作层重建；2026-09-22 补齐 9 个 bundle → 269 模型；2026-09-26 修 5 个贴图索引错绑）
269/269 还原、纹理拼接正确、HitAreas 已全库补登真判定区。输出 `Output/Live2D/{舰名}/`，**4.7GB**（2026-09-24 实测，曲线补齐后从 ~3.9GB 涨上来）。脚本 `reconstruct_live2d.py` / `fix_model3.py` / `extract_motions.py`。
| 指标 | 数值 |
|---|---|
| motion 文件 | **8154** 条（0 未引用 / 0 悬空引用；shell 仅剩 7 条资产层真为空，见下） |
| 曲线总数 | **2,662,615**（2026-09-24 全量重导：944,136 → 2,662,615，×2.82，与唯一人工验收样本 `antu_2` 98→278 的 ×2.83 同比例） |
| PartOpacity 换装曲线 | 79 模型（`gaoxiong_7` 3548 条、`kebensi_2` 2940 条、`chaijun_3` 2492 条等），此前整层丢弃 |
| 审计 | shell **7** / misassign **0** / `clips 8154`（`scripts/diag/l2d_motion_audit.py`，2026-09-24 全库） |
| HitAreas（model3） | min 3 / max 78 / mean 12.3，**无 0 判定区模型**（2026-09-24 `fix_model3.py` 全库补登 `Touch*`）。⚠️ 其中**多数框静止态落在画布外**（抽样 11 模型 323/379=85%）——那是**换装/互动按钮的停放位**，播对应动作时随部件进画面才可点，**不是脏数据、不得按几何批量删**（2026-09-27 逐动作组实测，见 §51 / `l2d_hit_offcanvas.py --sweep`） |
| 资产层真为空的 clip | 7（*_3 的 effect、wuqi_3 的 idle11 等），已从 model3 引用剔除 |
| 贴图索引顺序闸门 | **269/269 升序**（`scripts/diag/l2d_texorder_check.py`，退出码即判据；2026-09-26 修掉 5 个乱序，见 §40） |
| 贴图完整性对账 | **269/269 全绿**：源 bundle `Texture2D` 清单 vs 磁盘 PNG，missing 0 / extra 0 / 非 `texture_%02d` 命名 0（`scripts/diag/l2d_tex_completeness.py`）。⚠️ 其中 **51/269 源枚举序 ≠ 编号序**，全靠 `fix_model3.py` 归一化兜住——该步骤是承重的，不可省 |
| 目视覆盖（Live2D 画面） | **26/269**，按 `(moc3 版本 × 贴图数)` 15 桶**全覆盖**、零新增破损；⚠️ 只覆盖"贴图绑定"这一类，其余 243 个未目视 |
> **2026-09-21 根因重建**：旧产物 5037/8154 条是 `"Curves": []` 空壳、其余曲线名全部错位（按位置猜），现按 `genericBindings[i].path == crc32("Parameters/<名>")` 权威映射重建。见 §17。
已知限制：StreamedClip 未完全逆向；HitAreas 用 moc3 `Touch<X>` drawable 而非官方 `CubismRaycastable` 真点击区（**2026-09-22 §6.11 修后全部 269 模型均带真实 HitAreas**，仅 `z46_3` Special 框嵌 Body 属模型自带歧义）；0.226% 绑定（疑 Drawable 颜色）运行时无对应 target，跳过。
> **网页交互层状态（2026-09-23 §6.12 + §21）**：点击命中已修「四边形包含 + V/P 坐标系换算」，idle 循环已交回运行时（前端零定时器），动作切换恢复交叉淡化，运行时自加的假呼吸层已关闭，另有判定区可视化与参数·部件检查器；改前端前**必读 WF-16**（六条硬规则 + 回归六件套）。
> ✅ 四条已闭环事故注记（判定区幽灵标签 **§51**｜语音被掐 **§41**｜代理指标假绿灯 **§40**｜全量重导覆写事故 **§25**）已外迁 A15 段；目视覆盖 26/269 见上表同一行，不重复。
> ⚠️ **动效验证必须在播放窗口内高频采样**：运行时把每条 idle 解析成 `isLoop:false`（全 269 模型一致的既有特性），idle 只播一次即回静；等 ~12s 后两次快照比对会因短 idle(5~8s) 已播完而假报 `moved=0`。

### 2.6 Spine 动态立绘 ✅（v2 提取 + 全屏 CG 导出 + viewer 修复，2026-09-19）
> ✅ **2026-09-29 分层改认权威清单**：每个 `Output/Spine_v2/<目录>/parts.json` 由 prefab 的
> `SkeletonGraphic` 节点落盘（层名 + `localScale` + `startingAnimation` + `initialSkinName` + 位移），
> 索引与 viewer 与 `cg_export.html` **都只读它**，缺文件非零退出不回落 glob。
> 修掉 30 个目录多画 / 15 对本体与和谐版逐像素相同的 CG。做法 **WF-14 追加**、踩坑 **§64**。
`scripts/extract_spine_v2.py` 双结构兼容提取到 `Output/Spine_v2/`，232 主包。gallery 内 `spine-all.js`(3.8) 分层实时播放。**2026-09-19 三修复**：①相机视口（`SceneRenderer.resize()` 不更新 viewport → 比例怪）②`my` 变量遮蔽 TDZ（假「N 层失败」+ 取消失效）③过滤 0 秒空占位动画、默认播 `normal`、缺动画层回落 normal；另支持 JSON 骨架（beierfasite_g）。**全屏 CG 导出**：`cg_export.html` 渲染 setup pose 批量落盘 `Output/CG_v2/` **231/231 成功**（含二次像素包围盒构图修正）。
> ✅ **2026-09-26 Spine 三修**（补 `setSkin`｜CG 按 `animFrame` 全量重导｜弹窗取景 `boundsOf` 不再把"挂了附件"当成"会画出来"）结论与判据在 **§42 / §45 / §46** 与 WF-14 追加，流水外迁 A15 段。两条承重事实：**设 skin 前后画面大小不变、只是腿回来了**；**光加 `setSkin` 对 CG 导出无效**（CG 渲 setup pose，腿是动画第 0 帧的 AttachmentTimeline 挂上去的）。
> ⚠️ **遗留**：① 取景**第二类已修**（同日第三轮，见上方 §46 段与 WF-14 追加）：不透明纯色巨幕（`heimu`/`1heidi`）alpha=1、真的在渲染，"会不会落笔"拦不住；判据改为「区域纹素 × `slot.data.color` 后，落笔里 `max(r,g,b)>40` 的占比 ≥0.05」，全库 17/325 受影响（最大 2.79 倍），12 个对照指标逐字相同。✅ **CG_v2 已全量重导**（用户拍板后，参数与上一版一致 `--size 2400 --extra animFrame=1 --redo`）：234/234 完成 0 失败；与备份逐文件 md5 比对 **64 张变化、170 张逐字节相同**；逐张量"非近黑内容占画布长轴"→ **变好 19 / 持平 45 / 变差 0**（持平是画布收紧，如 qinli_2 2400×2125→2400×1342）；64 张缩略拼图 + 6 张改前/改后对照均目视过，无裁切。备份 `Output/_OLD_bak/CG_v2_pre_inkframing_20260926/`**（2026-09-26 已瘦身：其中 170 张与现网逐字节相同者删除、释放 659 MB，现存 64 张即全部"旧口径独一无二"的图，回滚能力未减）**。⚠️ 一个踩坑：扫描预测只有 24 个目录会变，实际 64——因为**扫描算 setup pose、CG 渲动画第 0 帧**，附件集合不同 ⇒ "子集式零误伤闸门"要求预测与产物走同一条渲染路径，否则只能直接量产物（§46 追加）。另有**第三类未修**（半透明确实在画的稀疏高亮面/雾：`weikesibao_3` 有效占满 0.387、`hu_2` 0.306、`mojiaduoer_5` 0.539、`z15_2` 0.629、`fage_2` 0.704）——再收要加"落笔覆盖率过低也不算内容"的第二阈值，会裁掉有意画在边缘的光束/雾，属审美判断，交人拍板。② `suweiaitongmeng_4` / `yuanchou` / `yuanchou_hx` 三个报 `Region not found in atlas`。归因**当天改了三次**，当前版本：文件两侧确实都是合法 UTF-8（`图层 664` 逐字节相同），但 mojibake **不是**我日志的 GBK 解码假象——直接读日志原始字节得 `ef bf a5…` = U+FFE5 U+FF9B… = **每个字符恰为 `0xFF00+原字节`**，即**浏览器内的 skel 字符串读取路径**在做单字节解码（cp932/shift_jis/euc_jp/big5 均抛错，latin-1 给 U+00E5，所以不是常见换码表，未查死）。另 `suweiaitongmeng_4` 缺的 `ab_sync_3_1_zuoxiong_1_2` 是**纯 ASCII**，与怨仇不同因。

### 2.7 UI/图标导出 ⏳ 未处理
`ui/` 4,059 文件 + 各 icon 目录数万，可复用 `export_assets.py`。优先级最低。
> ⚠️ **前置条件已变（2026-10-06）**：`ui/` 的 4,278 个源包按用户裁定删除，**只留 `ui/commonui_atlas`**（它是 `a2_2` / `2b_2` 两个已还原皮肤的 atlas 页依赖，删了重提取会缺页）⇒ 这条待办现在**必须先 `mumu_sync` 重拉 `ui` 类目**才能开工（`pruned.json` 已登记，diff 会把它们列成"归档"而不是"新增"，重拉要显式点名）。

### 2.8 资源分类整理 ❌ 裁定不补（2026-10-07）
`scripts/organize.py` 已写从未跑，现判定**不补**：它按 06-19 的 Raw 目录名写死（`Raw/painting` 单数已不存在→立绘整段 no-op；10 个背景类目只认 5 个，`backyardbg/newshipbg/worldhelpbg/lotterybg` 会被静默丢弃；`Raw/{metapainting,shoppainting,paintings}` 落进 `processed` 名单谁都不处理），而唯一真会执行的动作是 `organize_live2d` 把 7 张裸 `texture_0N.png` 复制进**生产目录** `Output/Live2D/`。它产出的分类结构也与 v2 产物（`Paintings_v2/Spine_v2/Paintingface/Audio`）重复。⇒ Raw 侧真实缺口已于同日接完：画廊「背景库」页 + 配置表来的中文命名（**WF-30** / **§115**），见 §2.3 与待办第 8 条。脚本本体留在 `scripts/` 未删。

### 2.9 Wiki 舰船数据 ✅
862 舰 / JSON(name,faction,ship_type,rarity) / `Output/WikiData/ship_data.json`。脚本 `scrape_wiki_fast.py`(8线程92秒)。已知：148 艘缺阵营（联动/特殊舰）。

---

## 3. 已加工资产清单

| 类别 | 文件数 | 大小 | 说明 |
|---|---|---|---|
| Paintings_v2 | 4,486 | ~15 GB | v2 静态立绘（当前正式产物） |
| Spine_v2 | 232 主包 | — | v2 Spine 提取 |
| Live2D | 256 | ~3.5 GB | Live2D 模型 |
| Audio | 4,370 | ~14 GB | BGM/CV/Other/SE |
| Raw/bg 等 | ~1,900 | ~2 GB | 背景/加载/帮助图原件 |
| gallery_v2 | ~4,500 | ~190 MB | 本地浏览平台 |
| files/AssetBundles | 86,849 | 26.6 GB | 源数据（只读） |

（v1 旧产物与历次调试目录已清理；**2026-09-20 磁盘清理 126 项/7.3GB 与硬链接去重 531 文件/~358MB 的完整流水**（含"重复资产被画廊按文件名引用故不能删"的判据）见归档 A3 段与 `windows-hardlink-dedup-verify` 技能。）

---

## 4. 工具链

| 工具 | 版本 | 用途 | 状态 |
|---|---|---|---|
| Python | 3.11 / 3.13 | 运行脚本 | ✅（v2 用 `py -3`） |
| UnityPy | 1.25.3 | 读取/导出 AssetBundle | ✅ 用户级 pip |
| Pillow | 12.x | 图像处理 | ✅ |
| ffmpeg | 7.1 | 音视频处理 | ✅ |
| vgmstream | v2117 | CRIWARE 音频解码 | ✅ |
| ALPA | 1.0.5.1 | 立绘注入/预览（参考真值） | ✅ 需 Java 17 |
| AssetStudio | v2.4.1 | 可视化预览/导出 | ✅ |
| spine-all.js | 3.8 | Spine 运行时（gallery 复用） | ✅ |

---

## 5. 关键文件清单

**核心脚本**：`scan_assets.py`、`export_assets.py`、`export_cue_audio.py`、`reconstruct_live2d.py`/`fix_model3.py`/`extract_motions.py`(★2026-09-21 权威映射重写)/`apply_live2d_motions.py`(★临时目录→备份换入)、`compose_paintings_v2.py`(★v2)、`extract_spine_v2.py`(★v2)、`export_dependency_manifest.py`、`build_gallery_index.py`、`make_thumbs.py`、`deploy_gallery.py`(gallery_src↔Output 硬链/漂移检查)、`fetch_gallery_vendor.py`(按 vendor 台账 sha256 补齐第三方库)、`mumu_sync.py`、`ship_name_map.py`、`scrape_wiki_fast.py`、**`run_v2_full.py`**(两阶段全量驱动)、**`update_pipeline.py`**(★2026-09-29 新增：WF-15 那条 runbook 的阶段机，一条命令跑到待确认、第二条命令签字换入，见 **WF-23**)。

**可复用诊断/验证工具 `scripts/diag/`**（68 个脚本，下面只列承重的；"18 件"是长期未更新的旧计数）：`scan_faces.py`(脸洞扫描)、`make_face_cmp.py`/`make_review_sheet.py`(改前后对比图/复核总表)、`l2d_motion_audit.py`(★全量动作健康审计：空壳/错位/PartOpacity/时长，`L2D_OUT_DIR` 可审任意产物目录)、`l2d_ab.py`(★同一模型新旧 motion 的渲染级 A/B，**只在换入前构成对照**)、`l2d_diff_dirs.py`(★两个产物目录逐 clip gained/changed/lost)、`l2d_sweep.py`(★全量加载+动作内容判据扫描；**2026-09-22 重写为 Python 侧逐条 evaluate + 每 N 模型重载页面**，修掉旧版「单次 evaluate 卡第一条不返回」与「单 Chrome ~110 后 WebGL 断连」，全库 269/269 一次跑通)、`l2d_verify.py`/`l2d_click.py`(抽样与真实点击路径无头校验)、`hit_verify.py`(按部位点击触发断言，支持 `--only`；2026-09-23 起合成点击经 V2P 走**真实路径**)、`interact_verify.py`(滚轮/拖拽/兜底/空白/部位五项交互断言)、`l2d_coord_forensics.py`(★**2026-09-23 新增**：坐标系取证——可见头/胸/髋三点反查应落 Head/Special/Body，专治「张冠李戴」且不构成自洽闭环)、`l2d_inspector_verify.py`(★**2026-09-23 新增**：判定区可视化+参数·部件面板+滑杆往返+过滤器四项验收)、`run_cg_export.py`(Spine CG 批量导出驱动)、`dedup_plan.py`/`dedup_apply.py`/`dedup_httpverify.py`(硬链去重三件套)、`gen_story_md.py`(复核清单生成)、`pipeline_panel.py` + 根目录 `启动资产更新控制台.bat`(★**2026-09-29 新增**：**资产更新控制台**——本地网页仪表盘，按钮驱动 `update_pipeline.py` 子进程；**一次只暴露下一步**（主屏=一句现状+一个行动+一行后果；13 张卡的写到/判据/上次、日志、对照表全在 `D` 抽屉）、状态色唯一、常驻「怎么用」抽屉；背景 = **显影式星野**（静止全黑、划过才亮、淡净回同一帧），控件 = **「指针携光」动效层**（边框光束/柔光/磁吸/点击把涟漪打进星野，`S` 关背景 `M` 关光效 `V` 新旧配色 `D` 开证据抽屉）；**常驻界面只留数据，为设计决定辩护的文案全部搬进抽屉**；版面 token 抄自公开设计系统的**禁止清单**（零投影 / 不拿薰衣草当卡片底 / 单一强调色 / 小标签不全大写），星体是预渲染精灵（高斯核 + 锥形衍射芒 + 幂律亮度 + 色温），主屏大字的可读性靠**星野避让矩形**而不是半透明纱，见 WF-23 三条追加与 §68~§71)、`peak_mem.py`(★**2026-10-01 新增**：给一条命令量**进程树峰值内存**——CreateToolhelp32Snapshot 走子进程 + psapi 采 WorkingSet，先拿已知 400MB 分配自测准头；回答"跑一次要多少 G"不再靠猜)、`test_pipeline_gating.py`(★**2026-10-01 新增 / 52 条**：控制台执行侧的闸门自测——**不看文案看行动**，只断言"未签字/缺范围时有没有 spawn 那个会覆写 `Output/` 的子进程"，含签字后的反向对照；它当场抓出 `_bj1` 躲过后缀表的映射洞，`[7]` 管住"0 变更被误判红 / 真清单被冲空"、`[8]` 管住依赖表闸门必须按**消费域**分级)、`panel_ui_probe.py`(★**2026-09-29 新增 / 09-30 三轮扩到 76 条**：该控制台的界面判据——结构计数 / 档位徽标不得借用状态色 / **静止不闪 3 条：带着 8 秒轮询跨一次 tick 整屏逐像素相同 + 节点未被重建 + `getAnimations()==0`** / 星野静止两帧逐像素相同、**划过才显影、只划一侧时另一侧必须 0 颗**、淡净回同一静止态 / **光效 10 条：边框光束真的在走、离开即收净回到同一张帧、柔光不进日志、M 键从简、指示条落位** / 数据面 alpha=1 且每个数据元素整张落在不透明面板内 / 键盘与日志筛选等 5 条交互 / "轮询不许把子进程杀掉"，见 §66~§70、`check_diag_hygiene.py`(★**2026-09-29 新增**：`.diag/` 顶层散落代码检查，退出码即结论，`--archive` 打包归档)、`server_wedge_probe.py`(★**2026-09-29 新增**：本地服务器"取消下载 ⇒ 泄漏 handler 线程"的剂量学探针，含真异常仍留痕的对照组，见 §63)、`precheck_red_test.py`(★**2026-09-29 新增**：给 WF-16 预检做红路径测试——用"照收连接、回 200 但 0 字节"的桩验闸门真的会红)。**游戏版本更新怎么跑 → WF-15**；**Live2D 动作重建怎么跑 → WF-7**；**Live2D 网页交互改动/回归怎么跑 → WF-16**。

**文档**（导航见根目录 `README.md`，写入路由见 `AGENTS.md`）：
- `docs/DEV_LOG.md` 操作手册 · `docs/WORKFLOWS.md` 可复用工作流 · `docs/TROUBLESHOOTING.md` 踩坑 · `docs/ERRORS.log` 错误流水
- `docs/tools/` ALPA、AssetStudio 使用说明
- **项目技能库 `.agents/skills/`**（8 个，入库）：`live2d-web-runtime-integration`(新建)、`unity-assetbundle-painting-restore`、`headless-chrome-cdp-batch-export`、`safe-pipeline-fix-targeted-rerun`、`windows-hardlink-dedup-verify`、`windows-local-server-launcher`、`cn-blocked-resource-mirror-fetch`、`project-doc-governance`——做同类任务前先查这里，别从零摸索
- `docs/archive/` 历史归档（含 `PROJECT_STATUS_历史归档.md`、旧目录审计报告、旧 Spine 交接）

**数据**：`asset_manifest.json`、`Output/dependency_manifest.json`(86,398 条官方依赖表)、`Output/WikiData/ship_data.json`、`Output/gallery_v2/index.json`。

---

## 6. 接下来的任务

### ★ 2026-09-29 画廊视觉（Q 轮）已定稿并刷进正本（新会话先读这条）

**已定（别再回头问）**：背景 = CPU 波动方程 + WebGL 着色的**水面**（静止一帧都不画，
划过才起浪，着色器里没有 noise/fbm/curl）；样板页**已刷进正本**（回滚锚点 = 换入前 `ee931aa`，
4/4 同 inode、探针打正本 24 条 `EXIT=0`）；底部 76px 空带**已删**（卡片改透玻璃悬空）；
§6.18 五条真缺陷全部关闭（含 ④`:focus-visible` 键盘焦点环、⑤开关用 LED 与瞬时动作区分）；
**不要**跟着鼠标发光、**不许**回弹/压扁（有回弹=果冻，只有亮度变化=iOS）、
弹层三个原生下拉不换自绘。做法与判据见 **WF-16 追加（2026-09-29）**，踩坑见 **§62**。

**待办（按序）**
1~4. ✅ 已闭环（① WF-16 全量回归六件套已过 ② 元数据兜底顺序换「配置优先」并换入 64 组 ③ `.diag/` 已清 + 散落代码债已还（防复发闸门 `scripts/diag/check_diag_hygiene.py`）④ 本文体量红线以 `wc -l` 为准、只有整段逐字外迁才压得下去，工具 `scripts/diag/doc_verbatim_archive.py`）。原文逐字见 **A25 段**。
5. 若视觉再被否：**要外部参照物**（参考站/录屏）逐帧对齐，不要自己猜第 7 版。
6. ✅ **服务器"半死"已取证到底并堵掉一条无界泄漏**（已证死 `socketserver.handle_error` 往 stderr 打 traceback 时**每次客户端取消永久楔死一个 handler 线程**：2600 次掐断 ⇒ 线程 5→2605；修法落 `_gallery_server.py` 并配对照组证明没咽掉真异常，预检红路径已桩测）。**剩余靠现场不靠赌**：预检判红时会打一行进程外部 `pid/threads/handles/parentAlive`。两条否证 + 剂量学在 **§63**，流水外迁 **A21 段**。

> 1~4、6~12. ✅ 已闭环，细节与结论在 `docs/archive/`（A4/A5 段）与 §13~§20；其中含 5 处手抄表错名纠正记录（hdn101/lafeiii/i13/missr/haixiao）。
5. ✅ **元数据重建（A/B/C/D 全部落地，2026-10-04 销账）**：
    - **脚本** `scripts/build_ship_meta.py`（`--diag` 只读 / `--write` 产 `Output/ship_meta.json`）；**闸门** `scripts/diag/ship_meta_authority_diff.py`（退出码即结论）。
    - 桥接路径、数值码→中文标签表（NATIONALITY/RARITY/TYPE）、`voice_actor` 只存数字 id 等决议已写进脚本常量与 docstring；A/B/C/D 四步与 `name_via=npc_table:*` 唯一放行口径见 docs/TROUBLESHOOTING.md §39。
> 6~12. ✅ 已闭环（细节见归档 A5 段、结论 §13~§20）。**接手前端先读 WF-16 六条硬规则**。

> 诊断产物/缓存均在 `.diag/`（不入库，本机可继续用）。画廊前端**直接改 `gallery_src/` 里的正本即生效**（与 `Output/gallery_v2/` 已硬链，2026-09-26 起 4/4）；`py -3 scripts/deploy_gallery.py --check` 查有没有静默断链，`--relink` 补链，默认模式是断链后的 copy 回退。换机器/清过 `Output/` 后先 `py -3 scripts/fetch_gallery_vendor.py` 补运行时库（只双击 `Output\gallery_v2\` 里的 bat）。


### 既有待办

**优先级低**
5. UI/图标批量导出（~2 万）、3D 宿舍资源、资源分类整理 `organize.py`。⚠️ 前两项的源包（`ui/` 除 `commonui_atlas`、`dorm3d`、`island`、`char`）已于 2026-10-06 按裁定删除 ⇒ 开工前要先重拉，且**必须先撤销 `pruned.json` 里的对应登记**（否则 `mumu_sync` 会按"已归档"跳过它们，`--only ui` 也拉不回来；工具还没有 `--revive`，见 WF-28 已知缺口）。🔎 2026-10-07 宿舍 3D 复刻已取证完毕：**数据层在手**（59 张 `dorm3d_*` / 5,425 条＝互动 1,041、角色 8、房间 12），表现层**可重写**（材质参数与曲线切线都在包里，我上一轮判否判错了），唯一未验证＝蒙皮权重 ⇒ 接手六步与判据见 `docs/archive/2026-10-07_3D宿舍复刻可行性取证.md`，能力探针 `scripts/diag/probe_3d_capability.py`（已在 `model/worldmap3d` 上跑通）。**当日 step 0/1 已推进（⏳→ 进行中）**：设备侧实见 **5,981 个包 / 3.44 GB 且尺寸零漂移**（§C「归档闸会 100% 吞包」已实证），`pruned.json` 撤掉 dorm3d 那 5,989 条（21,286→15,297，island/char/ui 逐条不动，六分对照全绿，判据 = 重跑 diff 得「已归档 0 / 新增 5,981」）⇒ ⚠️ **归档闸现已开着，期间不要跑不带 `--only` 的 `sync --apply` 或控制台拉取档**（会拉 3.44 GB）；step 3 判死就 `git checkout -- ledger/pruned.json` 关闸。§B 那句「两份清单差 8 条」方向已定：`hashes-dorm.csv` ⊂ pruned，那 8 条是**游戏更新自己删掉**的装饰道具包（设备 `stat=0`，1.46 MB，永久拿不到），csv 对可复原的 5,981 条**完备**。step 2 最小集已按实测改小：天津风 `prefabs`+`component` = **15 文件 / 606 KB**（正文「几百 KB」说错了，单角色子树实为 8.8~416 MB，几乎全在 `res/` 贴图）。流程 **WF-28 追加「撤销归档闸」**、全部数字 **取证文档追加 I~VI**。**step 2/3 ✅（同日 15:09）**：拉天津风 `prefabs`+`component`+单个 `res/tianlangxing_noshoes` 共 16 文件，逐文件 md5 **16/16 全等**；**真·蒙皮权重已证实完整可读**（`body` 13,412 顶点 **100% 有权重、权重和恰为 1.0000**、bindPose/骨哈希/骨骼 AABB 各 107 且 maxBoneIdx 106；每顶点骨数**逐网格变** 4/2/1，单骨网格压根没有权重通道；`hair` 数据尾部多 8 字节、padding 落在末段流之前）⇒ §F-1 那条生死判据 **通过**，布局是**反解 + 三重自证**出来的、不是猜的。附带证实：贴图 32/32 ASTC(`fmt=48`) 解码 OK、材质 118 floats/63 colors 全套旋钮到手（`_1stShiftStrength`/`_BackLightIOR`/Kajiya-Kay）、`Avatar` 在包内、骨骼可当场解析出名（`Bip001 Head`/`bone_hair_*`）。⚠️ 探针有**两个假信号**要修（`compressedMesh=Y` 判的是字段存在、`SKIN` 段只会喊不会读）⇒ 正确读法与四条已排除假设见 **§116**，完整数字 **取证文档追加 VII**。**重拉 3.5 GB 的前置条件已满足，但仍等 three.js 真播通（step 4/5）再动整批。** **step 4 ✅（同日）**：新增装配器 `scripts/dorm3d_to_gltf.py`（**手搓 GLB，不装 pygltflib**；已裁定**不动 `export_assets.py`**——装配器必须直读 bundle，扩那张类型表只会多产一份没人读的中间产物），天津风整角色出到 `.diag/dorm3d_gltf/tianlangxing.glb` = **9,653.9 KB / nodes 153 / meshes 5 / skins 5 / materials 10 / 内嵌 PNG 9 张**（ASTC 当场解码）；探针新增 `probe_weights` 反解段并修掉 `compressedMesh` 假信号。新查出三件事：`texRefs=0` 是**第三个恒 0 假读数**（该版本字段名是 `m_TexEnvs` 不是 `m_Textures`）、**真材质由 prefab 以外链 PPtr 引用**（res 包 SMR 只指占位 `Lit`；`prefab.externals[2].name == res 内层 CAB` 落回，不猜名字）、`face` 有 **5 个 submesh**（只出一个 primitive 会把眼睑贴错）。闸门：`--verify` 从文件字节回读断言全绿 + **两条变异红路径**（改坏一个权重字节、BIN 长度声明改短 4B）都 `exit 1` 并点名缺陷。未定案只剩两处语义，已做成开关不改数据：`m_BindPose` 是否需转置、UV 的 V 是否需翻 ⇒ 交 step 5 目视。step 5 另需下载 three.js + GLTFLoader（本地与 vendor 都没有）并补 vendor `MANIFEST.json`。做法 **WF-32**、字段坑 **§116 追加**、产物数字 **取证追加 VIII**。 **step 5 第一轮 ⚠️ 未过（15:45 后）**：three.js r160 已取到（`.diag/three/`，未进 vendor），探针 `scripts/diag/dorm3d_gltf_probe.py` 建好（量两条独立来源：前端几何盒 vs 源包 `m_LocalAABB`；页面内 CPU 逐顶点重算的蒙皮盒 vs 同一个 AABB）。修掉两个"产物看着正常、前端静默不蒙皮"的 bug：**glTF 的 `skin` 挂在 node 上**（漏了它 three.js 当普通 Mesh 画）与**属性名是 `WEIGHTS_0` 复数**（写错被 GLTFLoader 静默忽略；⚠️ 我的 `--verify` 当时是绿的，因为它查的就是那个错键 ⇒ 断言改按规范白名单查键名 + 加"宿主节点必须有 skin"，并配等长变异红路径）。现状：几何盒 4/5 逐轴吻合、顶点数 5/5 对、29,702 个三角被提交，**但四张截图全是背景色 = 画面里没有模型** ⇒ "通路成立"这句话现在不许说。头号嫌疑是取景（`Box3.setFromObject` 对 SkinnedMesh 取的是未蒙皮的盒，骨骼层可能把根节点顶远），次嫌疑是 `C·M·C`/四元数映射导致 Y-Z 换轴，且前端权重和读到 0 与 Python 侧读到 1.0000 矛盾——**这条必须先定案，否则包围盒数字都不可信**。全过程与四条待查见 **取证追加 IX**。 **第 2 条已定案并修好（16:40）**：根因在装配器不在前端——
   （step 0~5 全过程逐字见 **A25 段**：归档闸撤除与复验、16 文件 md5 全等、「真·蒙皮权重已证实完整可读」、手搓 GLB 装配器 `scripts/dorm3d_to_gltf.py`、两个「产物正常但前端静默不蒙皮」的 bug（`skin` 必须挂 node / 属性名是 `WEIGHTS_0` 复数）、`read_plain_channel` 把 UNorm16 与 uint16 按 float16 读导致骨号全 0 + NaN 权重（⇒ **内部不变式挡不住保持该不变式的系统性错误**）、静态部分 ✅ 通过（逐顶点偏差 1.2e-06~1.9e-06）、48/48 clip 是 Humanoid 肌肉优化格式属独立子项目、房间 1 已定界并拉完 453 包 md5 全等且**没有 shadowmap**。）⇒ **下一件事 = 跨包 PPtr 解析**（一个 bundle 多个 SerializedFile 含 `.sharedAssets`、`ObjectReader.assetsfile` 为 None、`deref()` 按同目录 CAB 名找文件），CAB→包索引已建（474 包 / 4.4 秒，缓存 `.diag/dorm3d_cab_index.json`）；交接正本 `docs/archive/2026-10-07_3D宿舍_交接给下一轮.md`、字段坑 §116、做法 WF-32。
6. ✅→⏳ **声优中文姓名补全（答案表已到手，回填待放行；2026-09-25）**：用新解析出的 `voice_actor_cn` 已拿到 **525 条 `code → 中文声优`**（`.diag/sharecfg_re/voice_actor_cn.json`）；对 `ship_skin_template` 实际用到的 499 个 `voice_actor` 值，**只缺哨兵 `-1`/`0`，真实 id 覆盖率 100%** ⇒ "CV 姓名表未缓存"这个前提作废。**已完成并写盘（2026-09-25 E1）**：`Output/ship_meta.json` 重写，逐字段比对 **既有值变化 0 / 字段消失 0**，**4041/4495 条带 `voice_actor_name`**（库尔斯克→衣川里佳、泛用型布里→下田麻美）；无名 454 = 427 剧情角色 + 27 个 voice_actor 为 0/-1。备份 `Output/_OLD_bak/ship_meta_pre_25.json`。见 §36。
7. ✅ **阵营「晶环联盟」= nationality 12 已定（2026-09-25）**；`12/99/101/104/117` 五个码已定名并写进 NATIONALITY。
   顺带把 `sharecfgdata` 整条线打通：**容器 = 记录帧 `ULEB(len)` + 假 LuaJIT BC 头 + 平铺 kgc 常量流；
   字符串 = `ULEB(长+5)` + 逐字节 `^(255-i)`，i 每串归零**。32 张表 140 MB / 220,568 条记录**帧覆盖残差 0**，
   `ship_skin_template` 标量一致率 **99.974%**（2863/2865 条 id 命中基准）、台词中文 **2601 行 / 40,897 个含中文字段值**到手。
   ⏭️ **剩余缺口 = 21 个容器字段**（`smoke`/`bound_bone`/`couple_encourage`）的装配关系在假 BC 指令区，二选一：
   **(a)** 解那套 4 字节栈码（一次通吃 21 个）或 **(b)** 只给要用的表人写字段表（便宜够用，参考实现走的正是 (b)）。
   攻关全过程（含 5 次改判、每条否证都配了对照）见归档 A6 段 + `TROUBLESHOOTING.md` §30~§37 + **WF-19 / WF-20**。
8. ✅ **磁盘优化收干 + 背景侧接线完成（2026-10-07）**：`Output/Raw/` 现只含背景家族 **1,922 png / 2.0 GB**（bg 1,305 + helpbg 364 + commonbg 111 + loadingbg 72 + loadingbg_hx 13 + newshipbg 14 + worldhelpbg 29 + lotterybg 12 + backyardbg 2）。⚠️ **它不是"还没处理的原料"**——`export_assets.py` 已把它解成成品（与源包 1:1，场景语义名就在文件名里），而且**背景不需要"还原"**（1 包 1 张 Texture2D 直出，无多层可拼，不同于立绘的 v2 合成）。✅ **已接成画廊「背景库」页**：`gallery_src/backgrounds.html`（主页顶部「背景库」入口）+ `Output/gallery_v2/bg_meta.json`（1,899 条）+ `bg_thumbs/`（1,899 张 webp / 32 MB）；中文命名**只认"某表背景语义字段整值 == 文件名"**这种精确引用（`activity_sp_story.change_background` / `expedition_data_by_map.default_background` 等），四档如实分开：**确定 284 (15.0%)**（配置表字段整值引用）/ **图内文字 6 (0.3%)**（`*_tip` 横幅把活动名烤在像素里，走 §116 的 OCR+目视双路径，是**第二条独立源**、不并进「确定」）/ **推断 419 (22.1%)**（只给系列名不冒充具体关卡）/ **类目中文说明 1,190 (62.7%)**，每条可回指"表.字段 行号"或取证方式。判据 **WF-30** / 取证 **§115**（含两条否证：`bgm` 名模板反推章节、`icon` 字段面）。✅ 同日补上两张缺图：`bg_worldcruise_14` / `_tip` 的源包是 09-24 拉进来的、比 09-16 那轮导出层新 8 天（不是解析失败），用新加的 `export_assets.py --target bg --only <包名>` 定点补导，索引与缩略图已跟着重建（1,897 → **1,899**）。✅ 同日已收：删掉 Raw 里非背景的 **87 件 / 80.1 MB**（v1 附属件，判据见 §111 追加；逐件 md5 清单 `.diag/cleanup/raw_v1_removed_20261007.json`）；`scripts/organize.py` **裁定不补**（目录前提已烂且会往生产目录 `Output/Live2D/` 复制垃圾）。✅ 前一轮已收：BGM 改 FLAC 无损档并删净 wav 与 opus（回收 12.81 GB，见 §113）。
   ✅ **上一轮那条「规模结论过期」已结案（2026-10-07 重量）**：立绘重渲的换前备份
     立绘重渲的换前备份（15.74 GiB，目录名与删前五项核对见 **§114**）与渲染中转目录，都已在用户画廊实见、
     确认不回滚后由归属会话删除，`check_disk_footprint.py` 实测 `_OLD_bak` **回到 2.99 GB**（= §111 的量）；
     另删闸门 scratch `.diag/fix_gate/` 3.42 GB。⏳ **`.diag/` 仍积压 21.52 GB**：235 个跨会话历史批次目录
     合计 21.32 GB（最大单项 `pipeline` 1.09 GB，无单一巨项），`check_disk_footprint.py` 不扫 `.diag` ⇒
     要清得单独一轮按批次核账，别顺手 `rm`。
   ✅ 本轮已做：① 按类目删 `dorm3d/island/char/ui` 共 **21,286 个源包 / 7.53 GB**，删除与登记同时落 `ledger/pruned.json`（依赖闭包闸门独立拦下 `ui/commonui_atlas`，与用户裁定一致；阴性对照 `--cat painting` 全拦、`artresource` 按深层传递依赖拦 105 个）；② **换入备份闸落地**：`extract_spine_v2.py` 写正式区必须带 `--bak`（覆写前逐份取前身字节 + md5 全等 + `MANIFEST.json`），顺带修掉 `main()` 丢返回值造成的"拒绝覆写也 exit 0"。判据 **WF-28** / 取证 **§111**。
8. ✅ **ship_meta `{namecode:XX}` 占位符名（已于 2026-09-20 随 B 根因修复关闭）**：根因=`build_ship_meta.py` 舰名取 `ship_skin_template.name`（皮肤名，含占位符）——**改取 `ship_data_statistics.name`（0 占位符）**后，237 个 ship 级占位符全归零、名称与阵营自洽（`weizhang`→尾张、`xinzexi`→新泽西 等）。残余 ~52 占位符全为 `story` 类（NPC/剧情/2b 联动变体，本就无 stats 舰名，非缺漏）。**2026-09-25 追加**：`name_code` 表已可读（456 行）**且 `{namecode:NNN}` ↔ `name_code.id` 已证成**（自称率 2.13% vs 随机重分配零假设 0.03% = 80×；1760/1760 码可查；替换后语义自洽：拉菲→[比叡]、布里→[明石]）⇒ 需要真名时可直接解占位符，不必再靠 stats 绕。见 §36。详见 §6 第 5 条 B 已完成。
9. ✅ **Live2D 动作数据全量重导落到 269 个模型**（clips 8154 / shell 7 / misassign 0 / PartOpacity 79 模型，曲线 944,136→2,662,615，`l2d_sweep` 269/269 失败 0；`hit_verify` 判据 = WIRING 必须为 0；⚠️ **约 7% 贝塞尔段是数据源天花板，别再攻**，见 §25 / WF-16）。原文逐字见 **A25 段**。
10. ✅ **Live2D 动作语音全线完成**（v1 270 皮肤 → 253 命中 ACB；v2 按船级包去重解码 889 包 / 41,193 音频 / 可定位 4140 皮肤；修掉的语义错 = cue 尾部 `_N` 是**皮肤序号**，§47；剩余 354 无解见 §57，「走设备补取」已否证 §49）。管线 **WF-17** / 证据 **§23**，原文逐字见 **A25 段**。
11. ✅ **已闭环**：摩尔曼斯克「皮肤2」脸上盖着不透明灰梯形（2026-09-26 用户报，09-27 查清并换入 13 张）—— 根因是**判据演进留下的隐形漏检**（旧判据下该值 1.000 → 判"已烤好"根本没进候选；收紧后只重渲了旧清单 35 张、全库从未重扫）。判据已换成两段式 `洞 = 脸谱落笔处不透明占比<0.5 或 MAD(底图 vs 脸谱)>30`，闸门 `scripts/diag/face_gate_labels_check.py` 在 47 个目视裁定样本上 **47/47 全对**；**全库 4488 张「盘上 == 当前管线」不变式已恢复，可当每次系统性修复的回归闸门**。全过程见 **§48 / §52**，流水外迁 **A13 / A21 段**。
12. ⏳ **一批"静止态就在画面内、却没登记"的判定区（2026-09-27 §51 顺带查出，另起一轮）**：
     `fix_model3.py` 登记 `Touch<X>` 的硬前提是"存在同名 `touch_<x>` 动作组"，于是**画面内、不透明度 1、
     但没有同名组**的标记被整批漏掉——实测 `yuanchou_3` 的 `TouchDrag20~23`、`qiershazhi_2` 的
     `TouchDrag7`（6.4×6.2 的大框压在角色身上）、`suweiaitongmeng_2` 的 5 个 `TouchDrag*`。
     游戏侧把这些按钮绑到哪条动作/哪个开关参数**没有权威依据**（`touch_drag20` 这类组根本不存在），
     不能猜着登记。取证工具已就位：`py -3 scripts/diag/l2d_hit_offcanvas.py <key>` 第 ② 段直接列全
     「moc3 里所有 `Touch*` drawable × 是否登记 × 此刻在不在视口内」。
     已知的相关机制（供下一轮起点）：换装状态是**各 clip 用定值曲线锁住 `TouchSiwa`/`Paramaixin` 这类开关参数**，
     所以只要找到"哪条 clip 锁成 1"，就能反推该按钮该播哪条。
13. ✅ **台词字幕 / 两个全局开关 / 索引新口径全部落地（2026-09-27 立项 → 10-03 换入）**：详情页底部字幕条 + 顶部「点击出声 / 显示台词」两开关（localStorage 持久化、互相独立）；换入后 `sibling-tier` 25→**0**、索引 counts 未动、WF-16 五件全绿 112s。原文逐字见 **A25 段**。
14. ✅ **天津风皮肤2「少了空中那份」真根因 = 层绘制序按名字后缀猜**（**§110** / **WF-27**，五条结论已并入该节）。原文逐字见 **A23 段**。

15. ⏳ **4 张「整张画的每一层都是关闭态」的皮肤**（2026-09-27 §55 顺带查出）：
     `qiye_4` / `kelifulan_4`（各只有一层且它是关的）、`qiye_dark_memory` / `unknown2_memory`
     （`frame_0..3` 四层全关，游戏按剧情逐层激活）。过滤会把它们**清空**，所以规则是"一层不剩就原样保留"
     并记进 `C.INACTIVE_ALL`。要修得先知道游戏在哪一刻激活哪一层，**没有权威依据不许猜**。
     取证：`py -3 scripts/diag/painting_inactive_scan.py`（只读全库扫）+ `painting_inactive_rerun.py`（定向重渲+对照表）。

16. ✅ **「有表行、主包未下发」的 44 张皮肤补上「仅台词」档 + `{namecode:NN}` 占位符展开**（2026-09-27 落地）—— 词表第二趟 44 张/565 条正文、索引 `voiceText`、前端 tab 判据 `voiceCount>0 || voiceText>0`、台词行不带播放器。见 **§60**、做法 **WF-22**、流水外迁 **A21 段**。
17. ✅ **Spine 分层不再按目录 glob 猜，改认 prefab 权威清单 `parts.json`**（2026-09-29 落地）—— 234 目录多画 30→0 / 少画 0 / 缺文件 0，15 对本体与 `_hx` 的 CG 全部拉开。见 **§64**、做法 **WF-14 追加**、原五步清单在 **A16 段**。

18. ✅ **画廊「按钮 / 交互反馈」层重做（2026-09-27 立项 → 2026-09-29 关闭）**：五条真缺陷（同一"选中"语义 5 种颜色 / 两条控制条其实是 UA 原生按钮 / 零 `:active` / 零 `:focus-visible` / toggle 与瞬时动作外观不可区分）**已全部关闭**，定稿见 §6 顶部 ★ 块与 **WF-16 追加（2026-09-29）**，踩坑 **§62**。⚠️ **一条否证别重走**：同日做过一整版**视觉语言重做**（暖墨底 + 单一铜金强调、字阶、卡片三行化、查看器底换掉棋盘格），样板页 `index_b.html` 给用户看过并**被否** ⇒ **整体换色这条路已试且被拒**，方向改为只动按钮与交互反馈。流水外迁 **A21 段**。
19. ✅ **WF-16 第 5 件 `hit_verify` 已补跑通过（2026-09-27 当晚）**：等并发会话的全库任务结束、端口空出后 `--only antu_2,ninghai_4,lafeiii_3` 干净跑：**85 部位 HIT 54 / INGROUP 25 / WIRING 0 / 不可点 6**，随机抽查 3 模型全合格 ⇒ 确认上一轮那 38 条 WIRING 是**探针侧污染**（§60 末段），不是产品回退。成因根治 = **第 20 条**；流水外迁 **A21 段**。
20. ✅ **CDP 探针的端口与 profile 走 env（根治第 19 条探针侧污染，§89）**：一份出口 `scripts/cdp_slot.py`——端口由 OS 挑空闲的、`AL_CDP_PORT` 可钉死但**被占即拒绝启动**，profile 变 `.diag/chrome_<tag>_<pid>`，已迁 7 个探针；验收三条（并发各自 exit 0 / 钉被占端口 exit 1 / 回归全绿），顺带回收旧固定名 profile 1.65 GiB。原文逐字见 **A25 段**。
21. ⏳ **变体包按条切分，让 44 张「仅台词」皮肤也能点播**（用户未拍板，先不做）：那 36 张的 `voiceExtra`
     是 v1 时代**整包**导出的单个 wav（`Audio/CV/cv-<n>-<battle|gift>.wav`），对不到具体类别 ⇒
     现在只能整包听、配不上逐句正文。要修得重新解码 `-battle/-gift` 包并按 cue 切分（约 10 分钟 + 一次零回退比对）。
22. ✅ **`yuanchou_2_hx` 的 CG 细条已修（2026-10-04，§96 / §97）**：根因 = 和谐版专有的 `BG_desk` 槽位顶点飞出（bbox 30593×4834428）⇒ 取景层加「离群槽位剔除」，**64×2400 → 2400×1331**，全库 234 个目录只有它命中、零误伤；三层取证法 **WF-25**。原文逐字见 **A25 段**。
23. ✅ **静默降级改成响亮失败（2026-10-03 傍晚，§91）**：新增降级台账 `scripts/diag/check_degradation.py` + `ledger/degradation.json`（四类：号段偏移不认识 / 借同船别人的包 / 档位靠空档分配 / 表里查无行；今天存量 `0/8/0/366`；**逐条点名、不记计数**，判据是"新增即红"，红路径实测过）。接进控制台 `audio` 档。同时修掉一条更坏的洞：`voice_gap_audit` 被标注"恒 exit 0 只作参考"之后**没人读它的 rc**，于是它 `ValueError` 崩了一整天、阶段照绿（崩因是我 `28cc193` 换三元组时漏改它一处解包）⇒ audio 档现在消费 `rcg/rc2/rc3`，`test_pipeline_gating` 56→63 条。
24. ✅ **画廊皮肤名已换成游戏真名（2026-10-04 换入）** —— label 变化 3891 条、非 label 字段零变化、键集合增删 0、counts 零变化；4368/4397 = 99.4% 有真名，残余 29 条 = 24 条 `npc` 前缀（用户拍板不管）+ 5 条真换不了（占位符指向别的实体 / 展开后等于舰名 / 表里只有本体）。根因三条（`NOT_A_NAME` 误杀英文真名 / 表盘 `painting` 键大小写不一致 1843 条 stem / 罗马数字二型）与占位符展开见 **§92–§94**、做法 **WF-24**；本条 22 行原文**逐字归档**在 `docs/archive/PROJECT_STATUS_条目24_逐字外迁_2026-10-04.md`。
25. ✅ **形态族（`_alter`/`_memory`/`_dark`）从皮肤区外迁**：判据是**归属**不是后缀（`E.form_root(key)` 剥完画法层仍带形态后缀且不等于卡 id 才搬，全库 147 条里 45 条属后者）。⚠️ 档位形态已被 §102 改判；10-05 用户点名 **`_dark` 一律进「其他」**（正本 `scripts/gallery_buckets.py` 的 `_dark(?:_memory)?$`，10 条全改），剩 27 条按各自 root 的自机与否落舰船/剧情角色。
26. ✅ **探索者连线关卡 NPC 迁到剧情剪影 → 已被 §102 改判**（三族 45 条 10-05 查明是**彩色皮肤、各有配音包**，已并回 3 张角色卡，见 §6.29/§6.30）。留下的可复用判据：族名正则须按**实际键完整形态**枚举（漏 `_1/_2/_3` 序号与 `npc` 前缀会静默匹配 0 条）。
27. ✅ **一个角色被拆成多张同名卡片已修（§95）**：标题重复 55 组 ⇒ 28 个**假组键**消除、32 张皮肤归位真船，`ships` 987→961 而 `skins` 恒 4397（键零增删、label 零变化）。根因两层：① `normalize()` 剥离白名单不含 `_tolove`/`_ger`/`_doa`；② 手抄表 `SHIP_NAME_MAP` 混着非舰名条目 ⇒ 加 `_is_real_entity()`，手抄表本身不动。剩 40 组 = 31 组 `npc*` 前缀 + 9 组中文名真相同。
（25~27 原文逐字见 **A25 段**）
28. ✅ **11 张已自机化的 META 卡「无阵营 + 无语音」已修（2026-10-05，§101 / §107 / §108）**：根因 = 皮肤表同一 painting 两行、`setdefault` 让迭代序首行胜出；四道闸与两轮追加修法见对应节。原文逐字见 **A23 段**。
29. ✅ **画廊改三档制 + 秘书舰三族并回 3 张卡（2026-10-05，§102）**：类别只留 舰船/剧情角色/其他，「其他」判据抽成唯一正本 `scripts/gallery_buckets.py`。原文逐字见 **A23 段**。
30. ✅ **秘书舰三族的语音与台词已接线（2026-10-05，§103）**：那 13 个包从未被解码过；修法 = 发 `npc_voice.json` + `extract_cv_voice.npc_entry()` + `merge_npc_words()`。原文逐字见 **A23 段**。
31. ✅ **配置表链并进资产更新台 = 台子五步主线（2026-10-05，§104 / WF-23 追加）**：`preflight` 加新鲜度判据、`cfg.disk` 新增行喂 `--expect-added`。原文逐字见 **A23 段**。

32. ✅ **静态立绘两处系统性偏差修复 + 4496 张全量重渲换入（2026-10-06，§114 / WF-29）**：
     两条真根因 = `paste(img,box,img)` 把 alpha 缩放两次 + 画布只取 max 不减 min（§9.3 第 8/9 条）；
     4496/4496 重渲换入全绿，换前备份已于 2026-10-07 删除（唯一回滚路径 = `git show 12eb0db^` 重渲）。原文逐字见 **A24 段**。

33. ⏳ **本轮查出来、与本轮改动无关的待办**：
     ① ~~`face_gate_labels_check.py` 那 4 条既有标签债~~ **已结案（2026-10-06 用户实见）**：
       `makeboluo`/`missd`/`feiteliedadi`/`dunkeerke` 四张对照图用户看过后判"没什么问题"
       ⇒ 维持现状（不叠），标签集不动、判据不动。
     ② **叠脸门控的判据本身有天花板**：MAD 量的是"底图这张脸是不是脸谱那张"，而正确动作要判的是
       "游戏在这里要不要换掉底图"——`yunlong_3`(该换，face 槽是 1924×2048 全身正面图、底图是背面)
       与 `xinzexi_h`(不该换，叠了切出矩形硬边) MAD 都是 32~34，这个量在原理上分不开，
       **抬阈值已否证**。要真修得去找 face 槽激活态的权威字段（`sharecfg` 侧？）。
     ③ ~~`gezi_2` Live2D 花瓣固定不动~~ **已结案（2026-10-07，§117 / WF-31）**：不是丢曲线，是
       **画廊只播 `idle` 一条 clip**（`idle` 里 14 个花瓣参数 0 个会动；`main_1` 里 10 个会动，
       要到第 8.12 秒才开始）。上一轮两条嫌疑都被证据收回，见 §117 开头。

35. ⛔ **Live2D「环境层 + 轮播池」已整体撤销（§117 第四轮）**——错在前提：源包 AnimatorController 实测 `effect` 是**独立一层的默认状态**（权重 1.0 / Override / Loop，全库 224/224 皆如此），网页不该拿它当「轮播池」。第二轮修掉的「抽搐 + 僵硬」：抽搐 = **交接塌帧**（等 motionFinish 才起下一条 ⇒ 旧 clip 淡出退回基准），改成当前 clip 保持循环 + 提前 1.2 秒交叉淡入 + 8 秒最短驻留；僵硬 = 「环境层别抢 pose 参数」做过头，源包那层本是 Override 权重 1.0。轮播权重量法改用**裁过 moc3 量程的可见位移**（`l2d_gallery_capture.py` + `l2d_motion_energy.py`，与游戏录像同一把尺子）。**仍差一截**：游戏角色区 125.8‰ vs 我们 45.5‰，调度器的挑条概率与间隔在 C#/Lua 里、**无权威依据**。原文逐字见 **A25 段**。

34. ⏳ **Spine 提取丢了 `MeshImage` 背景层 —— 14 个皮肤的 Spine 场景与 CG 缺背景（2026-10-06 查出，§114）**：
     `extract_spine_v2.py` 的 `skel_layers()` 只收 `SkeletonGraphic`，而游戏运行时这张 Spine 场景
     = `MeshImage` 背景 + `SkeletonGraphic` 角色。受影响 14 个：`aisaikesi_7` `banerwei_2`
     `bisimaiz` `gaoxiong_6`(BG1+BG2 两层) `haerbin_3` `haixiao_3_doa` `huanchang_2` `huben_2`
     `kaiersheng_2` `kalangshitade` `lundun_3` `luyisiweier_2` `masaiqu_2` `ougen_7`。
     另 12 个包的非骨架节点是 `*_shophx` 遮挡条，**本来就不该画**（§55），不要一起放过。
     ⚠ 别再用「依赖表名字含 `bg_tex`」筛——只捞出 3/14，其余 11 个背景住在 `_res` 包里、
     CAB 名不带 `bg`。权威信号 = 逐个 prefab 枚举 MonoBehaviour 类名 + `m_Sprite` 是否非空。
     修法：`skel_layers()` 一并输出这类节点（类名/CAB→bundle/世界框/绘制序），`parts.json`
     加一类 `image` 层，viewer 与 `cg_export.html` 在其上渲染骨架（复用 §110 的 DFS 先序绘制序）。
     做完这条之后，§6.33① 那个"画廊默认给 CG 还是给立绘"的取舍才不再是权衡问题。


36. ⏳ **Live2D 画廊里"花瓣不下落"的真相：它是场景侧粒子特效，不在模型里（2026-10-07 第五轮，§117 第五轮）**：
     `files/AssetBundles/effect/gezi_jiguang` 含 **17 个 ParticleSystem + 17 个 PSR + 3 张贴图**，而我们的
     管线只走 `live2d/*` 与 `painting/*`，**effect 类目从未提取**。模型侧三条假设已逐条判死
     （Unity 侧更宽的量程 ✗ / `m_DenseClip` 被丢的逐帧曲线 ✗ / 轮播或环境层能补出来 ✗，判据见 §117）
     ⇒ 再怎么调 motion 参数都不可能补出下落花瓣。**下一步**：读那 17 个粒子系统确认贴图是花瓣且挂在
     Live2D 界面 → 全库统计 `effect/*` 覆盖面 → 若要复刻需引入粒子渲染（新依赖，待你拍板）。


---

## 7. 新会话对接指南

新会话发送：
```
我在做碧蓝航线 AssetBundles 解包项目。
进度: D:\Azur Lane Assets\PROJECT_STATUS.md
规则: D:\Azur Lane Assets\AGENTS.md（含文档写入路由表）
当前主线: v2 数据驱动管线（§9）+ gallery_v2（§10）
下一步: [具体任务]
```
要点：**画廊视觉（Q 轮）的待用户拍板项与待办在 §6 顶部 ★ 块，接手先读它**。静态立绘 / Spine 已由 v2 全量收官，Live2D 动作层已于 2026-09-21 按权威映射重建完毕，**2026-09-23 网页交互层三个根因（命中包含判定 / idle 循环 / V-P 坐标系）已修并回归**。接手前先读 §9 理解「游戏数据自洽、不要猜坐标/不要按位置猜参数名」这一核心结论。**验动效一律看内容**（曲线条数、Id 是否命中参数表、值是否随时间变化），不要只看 `currentGroup`/组名标签——空壳也能"启动"，这个坑已踩过一次（`docs/TROUBLESHOOTING.md` §17、`docs/WORKFLOWS.md` WF-7）。**验交互一律用独立锚点**——合成点击若与被测映射同源会自洽闭环、全绿也说明不了对齐（§20、WF-16）。历史 v1 调试见 `docs/archive/`，一般无需再读。**背景库那条线（2026-10-07 交接，全文在 §115/§116 + WF-30）**：① **未决两件**——`*_tip` 同批 OCR 读到的奖励舰名 6 条里 3 条在 `ship_meta.json` 的 `cn` 查不到（读错 vs 译名口径不明 ⇒ 该字段故意不发布），以及 `exact > baked` 优先级**当前是空规则**（没有一张图同时有两种源，所以只打印不报绿，真出现冲突样本再升级为闸门）；② **别再走的路**——"把 OCR 铺到其余 1,190 张无名图"已抽样否证（48 张可用收益 **0/48**，那 4 条"像标题"全是奖励句子与机型名牌；工具 `scripts/diag/bg_ocr_yield_sample.py`），`helpbg` 那 364 张在 773 张表里**零引用**、连表 join 也没有；**词根中文名的两条自动路本轮都跑到天花板**——
      拼音整值（`lazy_pinyin` 比 773 张表的中文短名）✅ 已发布 `inputs/gamecfg/bg_root_labels.json`：
      213 根里唯一命中 **18 组 / 150 张**，多义（`yujin` = 余烬/浴巾）一律不发；
      把词根当字段整值反查同行中文名 ❌ 已否证（命中 12 组多为错配：`night`→「休息或其它」、`commander`→「装扮」），别再跑；
      ⇒ 英文与缩写词根（`star_level`/`project_tb`/`bsmre`/`worldcruise`）**没有自动路**，剩下 92 组只能人工词典或接外部维基；③ **换机器/清过盘之后要按序重跑**：`tools/sharecfg_re/41_export_lua_tables.py`（产 `.diag/sharecfg_re/lua_json/`）→ `49_publish_bg_scene.py` → `50_publish_bg_roots.py`（词根中文词典）→ `scripts/ocr_bg_tip_titles.py`（需 `rapidocr_onnxruntime`）→ `scripts/build_bg_meta.py` → `scripts/make_bg_thumbs.py`，然后 `deploy_gallery.py`；两份 `inputs/gamecfg/bg_*.json` 是 gitignore 的产物、**台账在 `MANIFEST.json`**，跑前先 `scripts/diag/check_inputs.py`；④ 页面依赖 `Output/Raw/`（已进 WF-15 承重白名单），个别包补导用 `export_assets.py --target <类目> --only <包名>`，别整类目重导覆写已验证产物；⑤ **探针瞬时红要重跑再判**：本机同时压着多个后台标注代理、或别的会话正在写 `gallery_src/index.html` 时，
     `原图真的解出像素`（等 2.5s 解码）与 `index.html 入口按钮` 会各红一次——实测三连跑 红/红/绿，
     **别把瞬时红当回归**，更不要在它红着的时候去改判据。
⑥ **背景库改造 P0~P4 全部收官（P2 于 2026-10-07 落地）**：四期现状见 **§2.3**；导出层取证 **§118** /
     流程 **WF-33**；P2 踩坑 **§119** / 流程 **WF-34**。P2 的口径：1,305 格人工逐格标注 + 17 格裁定
     （`#623`/`#624`→1、`#641`→0，由用户 2026-10-07 拍板）⇒ **有角色 535 / 无角色 770**；从没标注过的
     登录·其他 **604 张用「缺字段」表达**（用户拍板：照常显示，**绝不补 0**——补 0 就会被默认视图静默藏掉）。
     发布件 `inputs/gamecfg/bg_char_flags.json`（MANIFEST 已登记，`check_inputs.py gamecfg` 12 项全 OK）；
     **人工标注正本已迁出 `.diag/` 入库**：`annotations/bg_char_adjudications.json`（17 条裁定 + 每格 `why`）
     与 `annotations/bg_char_labels.json`（合并后的 1,305 条，keyed by `<dir>/<名>` 而非拼板序号）。
     索引 schema 3（`char` = 535/770/604，五道闸门）；页面默认档名叫 **「隐藏无角色」1,139**（描述行为而非
     结论，因为未标注的也在显示）+ 常驻「已隐藏 770 张」；探针 `scripts/diag/bg_page_probe.py` 新增三组判据
     （默认视图、五档计数反向对照、"搜索撞上筛选不许说库里没有"），连跑两遍 **67 PASS / 0 FAIL**。
     ⚠️ **两条别再走的路**：`_cg` 文件名规则只能当预筛（先验=0 而人工=1 有 **164** 格）；拼板 300px 判不出
     「人物极小」的边界格，那类裁定权在人（工具 `scripts/diag/make_bg_adjudicate_sheet.py` 可按原图出裁定板）。
⑦ **背景库 P5「源头低清子集 AI 超分」：数据层收官，页面接入未做（2026-10-07）**。
     取证先立住「糊在包里不在管线上」：抽样 130/130「导出即包内最大纹理」、源纹理 ASTC ≈3.5bpp、
     网格缩略图 720px 对 232px 卡片够用、详情/全屏本就走原生 PNG ⇒ 不是我们压的。
     产物 `Output/Raw_hd/` = **263 张 / 2.1 GB / 4096×2304**（anime6b ONNX + DirectML，31 分钟，失败 0）；
     独立复核 `py -3 scripts/diag/check_bg_hd.py` **四条全绿**（覆盖 / 尺寸正好 4 倍 / 尾部完整 / 无孤儿）。
     索引已重建 **schema 4**：263 条带 `img_hd`，`bg_page_probe.py` 全绿无回归、`deploy_gallery.py --check` 7/7。
     ⏳ **唯一未完成 = 页面**：`backgrounds.html` 的 `paint()`/`fsPaint()`/`fsDownload()` 三处仍写死 `it.img`，
     改成 `it.img_hd||it.img` 即可（改完必须走完「deploy 刷平 → 提交 → --relink → --check」，别停在中间）。
     判据 **WF-35**；⚠️ 本轮真实缺陷：IEND 完整性判据偏移写错（读在 `[-12:-4]` 永远 False），已修并给
     校验器配了「判据自身双向对照」（完整必判 True、故意截断必判 False），见 **§120**。

---

## 8. 技术备忘

**立绘命名**：`{舰名}`默认皮 / `_2`第2套 / `_tex`纹理 / `_n`夜战 / `_hx`换色 / `_rw`人物 / `_bj`背景 / `_front`前景 / `_jz`舰装 / `_alter`改造 / `_hei`黑化。多数脸烤进 `_rw`（仅 ~4% 有独立 face 部件）。
> **⚠️ 语义纠正（用户 2026-09-20 实测确认，别再按字面理解）**：**`_hx`「换色」实为和谐版**（内容被和谐处理后的立绘，不是调色变体）；**`_n`「夜战」实为不显示背景的立绘**（同一皮肤的无背景版，不是夜间场景）。二者都不是"另一套皮肤"。
> **⚠️ 又一处字面陷阱（用户 2026-10-03 纠正，见 **§88**）**：**`_hei`「黑化」实为剧情演出里的黑脸剪影**——不是另一套皮肤、**不是单独角色**、**本来就没有配音**（这 16 个键 `category` 全是 `story`、表内皮肤名是 `？？？`）。语音/台词层对它"不回退、归零算预期"是**对的**，但代码注释里"独立发声实体（用户裁定）"那句是错误转述，别当授权往下推。
> **✅ 画廊标签已改准（2026-09-20）**：`build_gallery_index.VARMAP` 由 `{'hx':'换色','n':'夜战'}` 改为 `{'hx':'和谐版','n':'无背景版'}`，重建 index 后 **1746 条皮肤 label 更新**，逐字段 diff 确认**非 label 字段变化 0**、船集合与皮肤集合完全不变、无「夜战/换色」残留。组合态形如 `皮肤2·无背景版·和谐版`。

**Live2D 结构**：`Output/Live2D/{name}/` = `{name}.model3.json` + `.moc3` + `.physics3.json` + `texture_*.png` + `motion/*.motion3.json`。

**PPtr 解析**：`m_Sprite=(FileID,PathID)`；FileID=0 本包，FileID=N → `SerializedFile.externals[N-1]` 的 CAB 名（≠ manifest deps 字母序）。

---

## 9. 当前主线：v2 数据驱动管线 ✅（2026-09-15，取代 v1 攻关路线）

### 9.1 匹配机制（游戏本体权威答案）★核心突破
- `AssetBundles/dependencies`(6.4MB 单包) 内 MonoBehaviour 携带 **86,398 条官方依赖表** → `Output/dependency_manifest.json`。
- 部件→纹理包 = deps + externals；对象定位 = PathID 精确匹配（一包多 mesh 不再错拿）；放置 = 统一 Unity UI 数学（anchor/pivot/sizeDelta/anchoredPosition/localScale 全递归；有 mesh 部件按画框 `mRawSpriteSize` 非等比映射 rect，无 mesh 部件 textureRect 直接拉伸铺满 rect）。
- 逆向关键：新版 bundle header `unity_version` 伪装成 `5.x.x`，真实 `2022.3.62f3` → 需 `UnityPy.config.FALLBACK_UNITY_VERSION="2022.3.62f3"`。静态立绘 = **纯 UI 结构**（RectTransform/CanvasRenderer，无 MeshRenderer），游戏把每个部件位置/大小/anchor/pivot 全写死，合成不需猜坐标。

### 9.2 静态立绘 v2（`scripts/compose_paintings_v2.py`）⚠️
零猜测、零手调。疑难样本 7/7 目视正确；v1 需手调的 feiteliekaer_3 / xili_alter / hailunna_4 现无参数自动正确。表情差分 `--faces all` 输出 `{name}_face{k}.png`。
> ✅ **嵌套容器错位已修（2026-09-18）**：带中间容器（`layers`/`Touch`）的皮肤子层曾被 `layout_all` 仿射多减 `p_local[0]` 甩偏（非 sortingOrder 问题），修复提交 `52782a7`，扫描 85/4486 受影响已全部换入。
> ✅ **i404 型背景缝隙已修（2026-09-19）**：无 mesh 部件误用 `mRawSpriteSize` 当画框致视差背景带压窄，改按 textureRect 拉伸铺满 RectTransform，10 张受影响已换入（见 §6 第 2 条）。注意 painting 本身即半景特写，完整 CG 走 Spine 线。
**全量收官**：4300 → **4486**（补合成 190，成功 186 / 失败 4 为非主皮肤杂项包，已加过滤）。输出 `Output/Paintings_v2/`。
> ✅ **2026-09-27 只画"游戏里开着的层"**（§9.3 第 7 条 / `TROUBLESHOOTING.md` §55）：`parse_painting`
> 现在把「自身 + 全祖先 `m_IsActive`」算进部件的 `active` 字段，`compose` 据此过滤。
> 全库 4488 张里 125 张有关闭层、48 张画面会变（26 张黑头 `shadow` + 14 张贴了 "NOT ABLE TO DISPLAY"
> 遮挡条 + 8 张赤城·改叠了四份画法），已备份换入并重建缩略图；12 张对照组逐字节零回退。
> 审计出口：`C.INACTIVE_SKIPPED`（跳过了哪些层）/ `C.INACTIVE_ALL`（4 张全层关闭、未过滤）。

### 9.3 九个系统性根因修复 ★教训（全部代码级、零逐角色参数）
1. 无 mesh 整图部件**双重 Y 翻转** → root 背景层颠倒。修：`arr = A[rect.y : rect.y+h]`。
2. Spine atlas 页纹理需 **`flip=True`**（运行时按行0=顶采样）。
3. Windows 分离进程 stdout 默认 GBK，`print('✓')` 抛错致全量**假失败** → `sys.stdout.reconfigure('utf-8')` + 子进程 `PYTHONIOENCODING=utf-8`。
4. `layout_all` **root scale 只乘子层未乘 root 自身** → 层间比例错。修：局部空间纯 anchor 数学 + 仿射映射世界 + 自身 scale 绕 pivot（负=镜像）+ root 屏幕适配 scale 归一为 1。
5. 无 mesh 部件**误用 `mRawSpriteSize` 当画框** → i404 型视差背景带（记录切分前原图尺寸）被压窄留黑洞。修：按 UI Image 语义 textureRect 拉伸铺满 RectTransform；mesh 部件才用 frame。
6. `rasterize_mesh` **把内容钳死在画框内** → mesh 顶点合法越框的皮肤（kuersike_rw 头部伸出框顶 713px）被裁头、纹理矩形露缝。修：按内容实际 AABB 输出（±2~3 倍框安全钳），越框部分由 render() 仿射照常映射。
7. **不读 `GameObject.m_IsActive`** → 游戏里**关着**的层被一律画上去：`shadow` 纯黑剪影压在头上
   （用户报的"头黑"）、`shop_hx`/`*_shophx` "NOT ABLE TO DISPLAY" 遮挡条贴在身上、
   `chicheng_alter_rw1..4` 四份备用画法叠成四个身子。修：`parse_painting` 把「自身 + 全祖先激活」
   算在部件的 `active` 字段上，`compose` 只画开着的层；**`face` 槽豁免**（恒关、运行时才激活，
   是 §48 叠层的输入）、**过滤后一层不剩则原样保留**（4 张全层关闭的皮肤清空=静默失败）。
   全库 4488 张命中 125、画面真会变 48、逐字节不变 73（白条早被 `is_lighting` 挡着）。见 **§55**。
8. **`canvas.paste(img, box, img)` 把 alpha 通道缩放两次**（Pillow 对 RGBA 蒙版的行为，
   文档原话 "scaling the alpha channel twice"）→ 铺在空画布上时 `a → a²/255`，
   **全部 4500 张的柔边系统性偏淡**（实测在盘成品 99.81% 半透明像素命中 a²/255）；
   并连带打出 1px 透明缝（用户报的"白雪皮肤2 脖子一条细空线"）、把叠脸门控的
   `alpha>=250` 读数压低 → `gezi_2` **正式产物一直在发被误叠的错表情**。
   修：`over()` = `Image.alpha_composite`（标准 source-over）。见 **§114** / **WF-29**。
9. **画布只取 `max(x+w)`/`max(y+h)`、从不减 min** → 世界框落在负侧的部件被 paste 静默裁掉
   （`beier_rw` 丢该层 15%、`jinluhao_2` **整张画下半截没了**、`i404` 只剩偏在一角的残片）。
   修：`canvas_frame()` = **所有节点框 ∪ 各层落笔框** 的并集，min 钳在 0。
   ⚠ 两个反例都进了判据：为省内存把容器 rect 从 max 侧剔掉 → `baixue` 画布**变窄**反而新裁
   2,771 像素；只按"负侧框"筛候选 → 影响面低估为 19 张（抽样实测 **2.0% ≈ 90 张**）。见 **§114**。
> 结论再次印证：游戏数据自洽，所有错位都是解析姿势不对。第 8/9 条补一句：**"姿势"也包括
> 用什么库函数落笔、画布边界取在哪**——数据读对了，落盘算子错一样全库错，且**不报任何错**。
> （完整明细含文件行号与验证样本，见 `docs/archive/PROJECT_STATUS_历史归档.md` 末尾「完整明细存档」。）

### 9.4 Spine v2（`scripts/extract_spine_v2.py`）✅
双结构兼容（内联型 + 分离 `_res` 型）+ 外部页纹理按 deps 补齐 → `Output/Spine_v2/`。全量 **232 主包**完成。skel 3.8.99，皮肤为多部件骨骼（B/M/T）需分层合成。

**失败语义已收口（2026-10-07）**：`main()` 现在 `失败 N>0 → exit 1`（以前掉出函数尾 ⇒ `sys.exit(None)` ⇒ 0），且整批路径下「提取成功但 `parts.json` 落不下」不再伪装成行首 `✓`（原 `parts.json ✗ 原因` 塞在行尾，而两个调用方 judge 都按行首匹配 ⇒ `run_v2_full` 连 `ERRORS.log` 都不写）。核实过两个程序化调用方（`run_v2_full.py:100` / `update_pipeline.py` `st_spine`）本来就不看退出码，故非零退出对它们是纯增益、无需放行。闸门 `py -3 scripts/diag/test_spine_exit_code.py`（桩驱动真实 `main()`，6 例含备份闸 exit 2 不退化）。取证 **§111 第 4 节** / 原则 **WF-15 第 1 条**（其余 8 个脚本仍未修，退出码依旧不作通过证据）。

### 9.5 Live2D 核查 ✅（2026-09-21 结论已更正）
266 个 live2d 包本地零缺失、自包含。**旧结论「剩余仅 motion 质量（§2.5 B 类 12 模型）」是错的**：
motion 大面积失效源于我们自己的解析器（帧 0 护栏 + 曲线名按位置猜），不是资产缺口；
已按 `genericBindings`/`crc32` 权威映射全量重建（见 §2.5 与 `docs/TROUBLESHOOTING.md` §17）。
资产层真为空的只有 7 条 clip（`effect` / `idle11` 一类占位动画）。

---

## 10. 本地资产浏览平台 `Output/gallery_v2` ✅（2026-09-15）

- **形态**：本地网页（源 28GB / Paintings 15GB，上线不现实），参照 l2d.su，中文名展示 静态立绘 + Spine + Live2D + 语音。**另有两张独立子页**：`bgm.html`「音乐库」（§112/§113）与 `backgrounds.html`「背景库」（§115/§116 / WF-30），主页顶部「页面」组两个按钮进；子页与主页共用 `theme.css`，各自有 CDP 探针（`bgm_page_probe.py` / `bg_page_probe.py`）。
- **数据**：`build_gallery_index.py`（合并四类 + `ship_name_map` 拼音→中文 812 条 → `index.json/js`；Spine 皮肤附 `cg` 字段指向 `CG_v2/`）+ `make_thumbs.py`（Paintings_v2 + CG_v2 → 380px WebP，CG 缩略图 `<stem>_cg.webp`）。结果 954 船 / 4489 皮肤 / spine 231 / CG 231 / live2d 256 / 语音 268。
- **前端** `index.html`：网格懒加载 + 搜索/阵营/舰种/稀有度筛选 + **类别分段（全部/舰船/剧情角色/剧情剪影 四档，主网格按 `category` 分区渲染各带小标题计数；「剧情剪影」是 2026-10-03 加的第 4 档，`_hei` 已不进皮肤区也不进主网格，见 §90）**；详情四标签。「静态立绘」对 Spine 皮肤默认展示全屏 CG（可切换回 painting 原件），支持**滚轮缩放(光标锚点)/拖拽平移/双击100%/全屏浏览/复位**；Spine 标签 `vendor/spine/spine-all.js`(3.8) 分层 WebGL 播放（相机视口/动画过滤已修，**支持全屏**）。服务器统一响应 `Cache-Control: no-cache`，改版后浏览器不再吃旧缓存。
- **前端取景与视角记忆 ✅（2026-09-27，§59 / WF-16 追加）**：修掉「打开皮肤缩得有点小」的两层根因——弹窗上限 1100×880 → `min(1900px,96vw)×min(1400px,96vh)`（2560×1600 上从占屏 43%×55% 到 74%×87%），Live2D 改按 **drawable 顶点框 ∩ 画布**的内容框取景（原来按 Cubism 正方形画布 fit，角色只占 6~8 成）、Spine 留白 1.1→1.05、静态立绘解除「永不放大」上限（双击仍是 1:1 像素）。**A/B 实测内容绝对像素 10/10 变大（x1.69~x3.89），零回退样本**，工具 `scripts/diag/gallery_framing_ab.py`。新增**视角记忆**：三个视图各自的缩放/平移按 `皮肤|标签页` 存 localStorage（只存尺度无关量 ⇒ 换窗口尺寸与进出全屏不错位；LRU 300 条），顶部第三个全局开关「记住视角」可关。顺带修一条老失效：**进一次全屏再退出会把调好的缩放抹掉**（`ResizeObserver` 直挂 `fit()`）→ 改 `refit(preserve)`。另加弹层内快捷键 `←/→` 换皮肤、`1-4` 切标签、`F` 全屏、`R` 复位。交互层零回退：`interact_verify` ALL PASS、`l2d_inspector_verify` 全绿、`hit_verify` **全量 269 模型 / 3309 部位 WIRING=0**（HIT 2330 / INGROUP 913 / NOTCLICKABLE 66 / 可点中率 97.1%，与 §27 那次全库基线 HIT 2338 / INGROUP 905 / WIRING 0 逐项对齐）。
- **视觉语言：定稿 = 水面背景 + 玻璃拟态 + iOS 丝滑（2026-09-29 刷进正本）**。
  前四版背景与两次"整体换风格"全被否，**共同败因是"背景自己在动"**——定稿版把"动"交还给用户：
  静止逐像素不动、划过才起浪；卡片/导航栏是透玻璃（alpha .05 + 折射边墙 + 常驻斜反光，模糊只挂
  进视口的卡）不是磨砂白卡；控件选中走材质态不整块填色；交互只改亮度、全表零过冲。
  验收 `gallery_motion_probe.py` 24 条判据，踩坑 **§62**、做法 **WF-16 追加（2026-09-29）**。
- **源码治理**：画廊前端源码在**仓库内 `gallery_src/`**（唯一权威版本），`Output/gallery_v2/` 是运行目录（gitignore）。**2026-09-26 起两边改成硬链接**（同一份磁盘数据两个路径名），**2026-10-07 起两边清单以 `scripts/deploy_gallery.py` 的 `FILES` 为准（现 7 项：`index.html` / `cg_export.html` / `bgm.html` / `backgrounds.html` / `theme.css` / `_gallery_server.py` / `启动资产浏览器.bat`），别在文档里抄个数**（这里曾长期写"4/4 已全部换链"，加了 `bgm.html` 与背景页之后早就对不上了）：改正本即刻生效、不需再部署。`deploy_gallery.py` 三态——默认 copy 修复（断链后的回退手段）/ `--check` **要求 `FILES` 全部同 inode，断链或漂移都 `exit 1`** / `--relink` 换链（要求两边逐字节相同，且正本有未提交改动者自动跳过，防打断并行会话）。⚠️ 断链的唯一现实成因是整文件写回式「写临时文件+改名」的原子保存：**16:52 真断过一次，而当时只比内容的 `--check` 给了 `exit 0`（判据漏洞，已改为结构性并写进 AGENTS.md 收尾清单第 1 条——改 `gallery_src/` 正本一律原地编辑）**。当前 `index.html` 因那条未提交改动处于"已断链、内容仍一致"态，待其提交后 `--relink` 补。见 §43 与 WF-16。CG 导出页 `cg_export.html` 同样入 `gallery_src/`；服务器 `_gallery_server.py` 提供 `POST /save_cg` 落盘接口，`--export` 参数直开导出页。⚠️ 服务器按自身所在目录算根，**只能双击 `Output\gallery_v2\` 里那份 bat**。
- **运行**：`启动资产浏览器.bat`（→ `_gallery_server.py`：8777 端口 + `allow_reuse_address` + 端口占用即复用 + 结尾 `pause`，杜绝闪退）。file:// 下立绘/语音可看，Spine `fetch` 被 CORS 拦需走 .bat。
- **运行时库台账**（2026-09-26）：`vendor/` 4 个第三方 JS 只在 gitignore 目录里，版本/来源/sha256 记进 **`gallery_src/vendor/MANIFEST.json`**（3 个的 URL 当日重新下载按哈希逐字节对拍命中），换机器跑 `py -3 scripts/fetch_gallery_vendor.py` 补齐（**哈希+字节数双对上才落盘**，`--check` 只校验）。⚠️ **唯一残留缺口**：`vendor/spine/spine-all.js`（实测 3.8.75，非旧文档写的 3.8.99）没有可按哈希校验的下载源——本机这份与上游官方 3.8 构建不同（499623B ≠ 501448B），只能从 `tools/spine-viewer/spine-runtime/` 取，而 `tools/` 也在 gitignore。要彻底封掉需二选一：把 501KB 提交进仓库（先确认 Spine Runtimes License 允许），或改用可哈希校验的上游构建并回归 Spine 播放。**未拍板**。
- **限制**：~~Live2D 暂只显示贴图~~ **已接动作播放**（2026-09-20，`vendor/live2d/` 三脚本本地就位，见 §6.7）；Live2D/Spine 标签均需走本地服务器（file:// 下 fetch 被 CORS 拦）。运行时库的可复现性与那条未拍板的残留缺口见上一条。

---

> **历史归档**：v1 时代攻关路线、多部件合成已知问题清单（Bug#1-#4）、7-30/7-31 修复记录、bj 背景层专项、调参工具 v3-v6 会话流水、旧 Spine Viewer 调试史 → 全部见 `docs/archive/PROJECT_STATUS_历史归档.md`。
