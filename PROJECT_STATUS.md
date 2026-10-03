# 碧蓝航线 AssetBundles 解包项目 — 进度总结

> **生成时间**: 2026-10-03 12:19
> 历轮会话流水（2026-09-20 ~ 09-27）已**逐字**外迁 `docs/archive/2026-09-26_PROJECT_STATUS_外迁归档.md`（A1~A15 段），§6 里已闭环的待办条目（★块第 1/2/3/4/6 条 + 既有待办第 9/11/16/17/18/19 条）于 2026-10-02 逐字外迁 **A21 段**（原位各留一行桩，编号不动）；
> 结论性知识在 `docs/TROUBLESHOOTING.md` §25~§67 与 `docs/WORKFLOWS.md` WF-14~WF-23。本文只留当前状态。
> **最近三轮**：画廊视觉定稿刷进正本（见 **§6 顶部 ★ 块** + §62 + WF-16 追加）｜354 张「🔇 无语音」按可救性拆细并裁定关闭（**§57**）｜静态立绘「只画游戏里开着的层」根因修掉、换入 48 张（**§55**）+ 敦刻尔克改判（**§56**）。逐轮流水已逐字外迁归档 A15 段。
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
**当前状态（2026-10-02 15:00）**：源包 92679 已同步；本轮更新的真实新内容 12 张立绘**已换入正式区**（4488→4500），
`meta`/`deps`/`derive`/`regress` 全绿，画廊索引 4503 皮肤零增减。逐轮叙述（§79 换入 → §81 审计分档 → §82 derive
否证 + 星空/说明书两档 → §83 权威源切换 → §84 后缀三分类 → §85 台词层同源）已**逐字外迁 A20 段**，结论在
docs/TROUBLESHOOTING.md §79~§85。三句话版：① 权威皮肤表换成"设备侧 + 快照逐字段合并"（`scripts/skin_table.py`，
唯一读取口）；② 语音/台词归属改成**一份**三分类规则 `extract_cv_voice.row_candidates()`（画法逐层剥、改造=同角色
可回退、`_hei` 后缀不回退——注意它是**剧情黑脸剪影**、不是"独立实体"，措辞纠正见 **§88**），49 个皮肤的归属被纠正、
12 个 `_hei` 键错派全部撤回（16 个 `_hei` 全部**有**自己那一行、包号 9002x~9005x 段两侧都不在盘上，
且它们 `category` 全是 `story` ⇒ 无声无词是正确状态，判据与探针见 **§87**）；③ 闸门补了方向判据与"无从判定"独立档，
并配 24 例反向对照（`test_voice_owner.py`，2026-10-02 实测 24/24）+ 8 例判据对照（`test_meta_gate_proofs.py`）。
**执行状态（2026-10-01 23:40）**：13 档**全部有本轮结论**（`.diag/pipeline/pipeline_state.json`，
指纹 `bundles=92679 deps=30fe6261e7`、范围章 `b885a9477f` 三处一致）——`preflight`/`pull`（签字拉完 1036 个新包）/
`deps`/`meta`（换入 + 权威闸门绿）/`paintings`（179 张）/`spine`/`live2d`/`review`/`swap-in`（12 张）/`derive`/`regress`
**已真跑**；`audio`/`cg` 只跑了**只读半边**（两条结论都以"未签字，请 --approve …"结尾：`--approve audio` 会解码 CV 包、
`--approve cg` 会直接覆写 `Output/CG_v2`）。设备侧已同步完（新增 0 / 变更 0）。
⚠️ ~~一处顺序性欠账：`derive` 跑在 `meta` 换入之前 ⇒ 重跑 `derive` 让索引吃到新 `ship_meta.json`~~
**这条已否证**（10-02 实测）：重跑 `derive` 产出的 index 与上一版 **md5 完全相同**，那 12 行的 `label`
仍是回落值（`h`、`皮肤9（无背景版）`、`alter`、`皮肤3`）、`voiceCount` 仍空 ⇒ **画廊皮肤名不读
`ship_meta.json`**，"label 回落"与"语音接不上"是同一个根因（权威皮肤表里没有这些行），见 **§82**。
（15:53 前那批"只换入暂存区 4 张"与首轮 1154 条规模、§74 五条明细已逐字外迁 A17 段。）
跑之前先 `py -3 scripts/diag/test_pipeline_gating.py`（56 条判据）。**§76 又挖出一条接线缺失**：卡片上的「签字放行」复选框只有那颗「单独跑」会读，主按钮「重跑到待确认」发的 `approve` 永远是空的 ⇒ 用户勾了等于没勾。现在勾选存 `SIGNED`、主按钮带上并二次确认、主屏那行小字显示"已勾签字：…"；另外设备不可达且范围清单有效时 `pull` 判绿沿用清单，不再把已同步完的人卡在第 1 档。。**语音产物口径已定：无需单独备份**（可确定性再生，体检 `scripts/diag/l2d_voice_inventory.py`），不可复原的只有 `inputs/azdata`｜**控制台界面（2026-10-01 第五轮，见 §73 / WF-23 追加）**：用户否掉第四轮的「常驻漂移」（「我要的就是渐进式显影」）⇒ 星野**退回显影式**（静止全黑、划过才亮、约 520ms 淡净、淡净回**同一张**帧），配色保留 B 的**海军蓝 + 蓝白**（五个状态色 rgb 不动），光效回到 **conic 边框光束 + 控件内柔光 + 磁吸**；新增**三态自定义光标**（默认/可点/主行动，内联 SVG、深色描边打底）与**进度台**（只在真在跑时出现的一条细带：阶段 N/M · 已用 · 内存〔整棵进程树工作集〕· 剩余〔各阶段历史均值，缺样本报「≥」下限〕）；帮助抽屉里**为设计辩护的文案删掉**（用户要求别把提示词写进界面）。`scripts/diag/panel_ui_probe.py` 契约改回「渐进式显影」并新增 9 条进度台判据，**86 条全绿**。**控制台第六轮（2026-10-02，见 §82）**：说明书加「简洁 / 详细」两档（默认简洁只留 5 节、收起 7 节、选择写 `panel.helpmode`）；星空先量后改——量出来静止帧整屏只有 **67 个像素**亮着（占视口 **0.01%**），"常驻微光"这个开关是开着的但屏幕上没东西 ⇒ 常驻档改为按星型分抽（47→280 颗）、`AMB` 0.10→0.26、密度 2187→2843、显影半径 9→46/130→190、银河带从 30 个正圆改成沿带轴拉长的纤维 ⇒ 静止 3702 px（0.33%）而**淡净后与初始帧仍逐像素相同**；探针 103→**109 条**，并新增一道硬预检「served 页面必须与磁盘正本一致」（§72 烘死 HTML 那条坑本轮第三次撞上）。｜低优先：声优中文姓名回填、UI/图标批量导出、`organize.py`。

---

## 1. 项目概览

- 对碧蓝航线 Unity AssetBundle 解包、分类、导出、还原。
- 源路径 `D:\Azur Lane Assets\files\AssetBundles`，196 子目录 / ~86,890 文件 / ~26.6 GB（94.6% 无后缀二进制 blob）。
- **当前主线 = v2 数据驱动管线**（见 §9）：零猜测、零手调，已全量收官。

### 仓库治理 ✅
- 忽略规则收敛为「保留源码与文档，忽略游戏资产与生成产物」：忽略 `files/`、`Output/`、`tools/`、`.micode/`、`.mimocode/`。
- 生成产物与资产元数据已从 Git 索引移除，避免再次提交游戏资产。

---

## 2. 各部分进度

### 2.1 目录扫描 ✅
86,849 文件 / 26.62 GB / ~30 类；输出 `asset_manifest.json`(25MB)。脚本 `scripts/scan_assets.py`。

### 2.2 立绘导出 ✅
43,520 导出 / 0 失败。脚本 `scripts/export_assets.py`（UnityPy）。（v1 合成产物已被 v2 取代，见 §9.2。）

### 2.3 背景导出 ✅
1,897 张（bg 1,302 + helpbg 364 + commonbg 111 + loadingbg 50 + loadingbg_hx 13 + newshipbg 14 + worldhelpbg 29 + lotterybg 12 + backyardbg 2）。输出 `Output/Raw/{bg,commonbg,loadingbg,helpbg,...}/`。
> 2026-09-16 随源包更新全量重导 1897/1897；修复 `export_assets.py` 漏设 `FALLBACK_UNITY_VERSION` 导致较新包加载失败的问题。

### 2.4 音频导出 ✅
4,370 WAV / 0 失败 / ~14GB。`.b` 是 CRIWARE ACB，vgmstream 解码。分类 BGM 536 / CV 2,696 / Other 1,136 / SE 2。脚本 `scripts/export_cue_audio.py`。

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

### 2.8 资源分类整理 ⏳ 未处理
`scripts/organize.py` 已写未跑，需所有导出完成后进行。

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
1. ✅ **WF-16 全量回归六件套已过**（2026-09-29 串行 runner `wf16_regression.py`，六件退出码全 0；全库 269 模型 / 3309 部位 **WIRING=0 / OUTSIDE=0**、可点中率 97.1%，与 §27 基线差在抖动量级、总数不变）—— 流水外迁 **A21 段**。
2. ✅ **元数据兜底顺序已换成"配置优先"并换入**（原记"112 组"是错的：实测 84 组两名不同、其中 **49 组配置名属另一实体**、被零回退不变式自动挡下，最终换入 **64 组 = 45 真换名 + 10 去尾空格 + 9 占位符回落**，`with_cn` 984→975；占位垃圾按"像不像真名"写判据挡掉、不开例外名单）—— 全过程 `docs/name_review_20260929.md`，闸门 `--expect` 按值钉死，流水外迁 **A21 段**。
3. ✅ **`.diag/` 已清 + 那笔散落代码债已还**（2026-09-29：删 49 个 profile / **释放 4.42 GiB**；67 个代码文件里 10 个零损失直删、57 个独有的打包，顶层散落代码现 **0**）。⚠️ `.diag` 在 `.gitignore` 里 ⇒ **删了没有 git 兜底**，而那份 zip 也住在 `.diag/` —— 只保证能反悔一次，**不是永久备份**；要长留某个探针只能移进 `scripts/diag/` 入库。防复发闸门 `py -3 scripts/diag/check_diag_hygiene.py`（AGENTS.md 收尾第 4 条），流水外迁 **A21 段**。
4. ✅ **本文档体量红线**：红线以 `wc -l` 实测为准（>400 触发）。⚠️ **"写得更省"压不住**——那一轮净增 3 行，只有整段逐字外迁才回到阈值内；溢出内容按轮次搬家（A15/A20/A21 段），工具 `py -3 scripts/diag/doc_verbatim_archive.py`（四条核对它自己跑）。
5. 若视觉再被否：**要外部参照物**（参考站/录屏）逐帧对齐，不要自己猜第 7 版。
6. ✅ **服务器"半死"已取证到底并堵掉一条无界泄漏**（已证死 `socketserver.handle_error` 往 stderr 打 traceback 时**每次客户端取消永久楔死一个 handler 线程**：2600 次掐断 ⇒ 线程 5→2605；修法落 `_gallery_server.py` 并配对照组证明没咽掉真异常，预检红路径已桩测）。**剩余靠现场不靠赌**：预检判红时会打一行进程外部 `pid/threads/handles/parentAlive`。两条否证 + 剂量学在 **§63**，流水外迁 **A21 段**。

> 1~4、6~12. ✅ 已闭环，细节与结论在 `docs/archive/`（A4/A5 段）与 §13~§20；其中含 5 处手抄表错名纠正记录（hdn101/lafeiii/i13/missr/haixiao）。
5. 🟡 **元数据重建（A/B 均已完成，交接点=C 之后）**：
   - **脚本**：`scripts/build_ship_meta.py`（默认 `--diag` 只读，`--write` 产 `Output/ship_meta.json`）。运行：`PYTHONIOENCODING=utf-8 python scripts/build_ship_meta.py --write`。产物键=画廊 bundleID（Paintings_v2/Spine_v2/Live2D/CG_v2 目录名并集，共 4492），值=`{cn,en,faction,type,rarity,voice_actor,category,base_painting,source[,数值码]}`。
   - **桥接路径（⚠️实测校正，覆盖旧假设）**：磁盘 stem →剥变体后缀→ 基 `painting` → `skin[painting].ship_group` →（`stats.skin_id` 命中，实测 4118/4119）→ 舰级四字段。**「用 `ship_group` 直接反查 stats」不成立**（1270 个 ship_group 仅 268 落在 stats 键），变体皮肤须经 `ship_group` 归并到舰。成品 **4492 有名字（99.93%）/ 仅 3 真无源**。解析优先级改造、76 处手抄表错名纠正、索引层加法兜底（`with_cn` 899→910→984）的流水外迁 **A15 段**。
   - **闸门**：`py -3 scripts/diag/ship_meta_authority_diff.py`（退出码即结论）——受保护档 `painting/suffix` 字段改动必须为 0，**唯一可放行的是逐条回查秘书舰表通过的 `name_via=npc_table:*` 皮肤标题→实体名**（要求原皮肤标题仍留在 `skin_name`）；条目集合不得增减；换档只允许落在白名单新档；无源数须等于期望。见 `TROUBLESHOOTING.md` §39。
   - **数值码→中文标签表已写进脚本常量**（NATIONALITY/RARITY/TYPE，对齐游戏内筛选词表）：nationality 1白鹰 2皇家 3重樱 4铁血 5东煌 6撒丁帝国 7北方联合 8自由鸢尾 9维希教廷 11郁金王国 96飓风 97META 98其他(布里) 102~115各联动；rarity 2普通 3稀有 4精锐 5超稀有 6海上传奇 18超稀有；type 1驱逐…24风帆。游戏筛选里的「晶环联盟」本快照(9.7.381)无对应码 → 前端归「其他」。
   - **✅ 两个决策已定**：① `voice_actor` = **只存数字 id**（CV 姓名表未缓存，以后再补映射）；② 非核心码(98/111~115) = **经验名 + 兜底原样保留**，不逐个核。
   - ✅ **B 已完成（2026-09-20）**：`build_gallery_index.py` 元数据主源切 `ship_meta.json`，根因（舰名原取皮肤名 → 改取 `ship_data_statistics.name`，237 个舰级占位符归零）见本条第 8 项。**⚠️ 该条决议里"下一步 = C（前端按 `category` 分区）/ D（Live2D 动作播放）"两项均已落地**（C 见 §10 前端行、D 见 §2.5），此待办作废。
> 6~12. ✅ 已闭环（细节见归档 A5 段、结论 §13~§20）。**接手前端先读 WF-16 六条硬规则**。

> 诊断产物/缓存均在 `.diag/`（不入库，本机可继续用）。画廊前端**直接改 `gallery_src/` 里的正本即生效**（与 `Output/gallery_v2/` 已硬链，2026-09-26 起 4/4）；`py -3 scripts/deploy_gallery.py --check` 查有没有静默断链，`--relink` 补链，默认模式是断链后的 copy 回退。换机器/清过 `Output/` 后先 `py -3 scripts/fetch_gallery_vendor.py` 补运行时库（只双击 `Output\gallery_v2\` 里的 bat）。


### 既有待办

**优先级低**
5. UI/图标批量导出（~2 万）、3D 宿舍资源、资源分类整理 `organize.py`。
6. ✅→⏳ **声优中文姓名补全（答案表已到手，回填待放行；2026-09-25）**：用新解析出的 `voice_actor_cn` 已拿到 **525 条 `code → 中文声优`**（`.diag/sharecfg_re/voice_actor_cn.json`）；对 `ship_skin_template` 实际用到的 499 个 `voice_actor` 值，**只缺哨兵 `-1`/`0`，真实 id 覆盖率 100%** ⇒ "CV 姓名表未缓存"这个前提作废。**已完成并写盘（2026-09-25 E1）**：`Output/ship_meta.json` 重写，逐字段比对 **既有值变化 0 / 字段消失 0**，**4041/4495 条带 `voice_actor_name`**（库尔斯克→衣川里佳、泛用型布里→下田麻美）；无名 454 = 427 剧情角色 + 27 个 voice_actor 为 0/-1。备份 `Output/_OLD_bak/ship_meta_pre_25.json`。见 §36。
7. ✅ **阵营「晶环联盟」= nationality 12 已定（2026-09-25）**；`12/99/101/104/117` 五个码已定名并写进 NATIONALITY。
   顺带把 `sharecfgdata` 整条线打通：**容器 = 记录帧 `ULEB(len)` + 假 LuaJIT BC 头 + 平铺 kgc 常量流；
   字符串 = `ULEB(长+5)` + 逐字节 `^(255-i)`，i 每串归零**。32 张表 140 MB / 220,568 条记录**帧覆盖残差 0**，
   `ship_skin_template` 标量一致率 **99.974%**（2863/2865 条 id 命中基准）、台词中文 **2601 行 / 40,897 个含中文字段值**到手。
   ⏭️ **剩余缺口 = 21 个容器字段**（`smoke`/`bound_bone`/`couple_encourage`）的装配关系在假 BC 指令区，二选一：
   **(a)** 解那套 4 字节栈码（一次通吃 21 个）或 **(b)** 只给要用的表人写字段表（便宜够用，参考实现走的正是 (b)）。
   攻关全过程（含 5 次改判、每条否证都配了对照）见归档 A6 段 + `TROUBLESHOOTING.md` §30~§37 + **WF-19 / WF-20**。
8. ✅ **ship_meta `{namecode:XX}` 占位符名（已于 2026-09-20 随 B 根因修复关闭）**：根因=`build_ship_meta.py` 舰名取 `ship_skin_template.name`（皮肤名，含占位符）——**改取 `ship_data_statistics.name`（0 占位符）**后，237 个 ship 级占位符全归零、名称与阵营自洽（`weizhang`→尾张、`xinzexi`→新泽西 等）。残余 ~52 占位符全为 `story` 类（NPC/剧情/2b 联动变体，本就无 stats 舰名，非缺漏）。**2026-09-25 追加**：`name_code` 表已可读（456 行）**且 `{namecode:NNN}` ↔ `name_code.id` 已证成**（自称率 2.13% vs 随机重分配零假设 0.03% = 80×；1760/1760 码可查；替换后语义自洽：拉菲→[比叡]、布里→[明石]）⇒ 需要真名时可直接解占位符，不必再靠 stats 绕。见 §36。详见 §6 第 5 条 B 已完成。
9. ✅ **Live2D 动作数据全量重导已落到 269 个模型（2026-09-24）**：`clips 8154 / shell 7（=资产层真为空的 7 条）/ misassign 0 / PartOpacity 79 模型`、曲线总数 **944,136→2,662,615**、`l2d_sweep` 全量 **269/269 失败 0**；`hit_verify` 全库基线已重标定（269 模型 / 3309 部位，**判据 = WIRING 必须为 0**，旧「806/807」口径作废，见 §27）。⚠️ **数据源天花板（别再攻）**：约 **7% 的贝塞尔段无法从 Unity 数据还原**（四种切线候选最高只拟合 16.7%，且那是平凡情形）→ 只能用线性弦近似。过程含一次原地覆写事故与三道闸门加装 → **§25** 与 WF-16；已完成 runbook 与旧基线讨论见归档 **A7 段**，本轮流水 **A21 段**。
10. ⏳ **Live2D 动作语音：全量导出 + 出声验收 + 技能沉淀（2026-09-23）**
   管线与判据见 **`docs/WORKFLOWS.md` WF-17**，命令语义与实测证据见 **`docs/TROUBLESHOOTING.md` §23**。
   **✅ 全线完成**：v1 `--all` 覆盖 270 皮肤 → 253 命中 ACB（5914 ogg / 323 MB）；**语音 v2（2026-09-27）**按船级包去重解码 → `Audio/CV2/` + `skin_voice.json`，**889 包 / 41,193 音频 / 2424.5 MB / 可定位 4140 皮肤**，零回退闸门 + 三格实播全过。
   修掉的系统性语义错：cue 尾部 `_N` 是**皮肤序号**（旧脚本当随机变体全导、前端 `Math.random()` 抽一条 ⇒ 三皮肤船 2/3 概率播到**别的皮肤**的台词，§47）。剩余 354 无解的构成与裁定见 **§57**，「走设备补取」已否证（§49）。过程流水外迁 **A15 段**。
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
13. ✅ **台词字幕 / 两个全局开关 / 索引新口径全部落地（2026-09-27，含换入）**
     代码：详情页三格共用的**底部字幕条** + 顶部「点击出声 / 显示台词」两个开关（localStorage 持久化，互相独立）、
     语音页改为按皮肤列「类别名 + 中文正文 + 播放器」、`scripts/build_skin_words.py`（产 `skin_words.json`，
     **不动**已验收的 `skin_voice.json`；钥匙 = **查出来的皮肤行主键**（⚠️ 不是 `cv*10+idx`，那条算式在皮肤序号≥10 处进位撞进隔壁船，见 **§86**），别名全查 `character_voice` 不猜）、
     `build_gallery_index.py` 语音口径换权威源（`voiceCount` 268→860 组船）、`scripts/diag/gallery_index_diff_check.py`
     （索引零回退闸门）、`scripts/diag/talk_verify.py`（实播验收）。数据链与判据见 **WF-22**，根因与踩坑见 **§54**。
     - ✅ 覆盖面 **4129/4140** 皮肤 / **73,705** 条正文；**已换入**（2026-09-27 19:05 用户放行，备份 `Output/_OLD_bak/gallery_index_pre_talk_20260927/`，sha256 `e79ed546bb41`/`58b78bf27249`），换入后复验 + `talk_verify` 12 条判据全绿。
     - 验收明细（"全屏没字幕"的 `#mView` 修法与 CDP 可信事件量法、`flex:1` 把播放器压成 0 高这类反向证据、`lafei`/`kelei` 换口径对照、并行会话接管提交的经过）外迁 **A15 段**；根因 **§54**、做法 **WF-22**。
     - ⚠️→✅ **2026-10-02 三条静默错派已修并换入（§86 / WF-22 追加）**：台词钥匙改用查出来的表主键（59 处，其中 48 处原本派给**别的实体**）、画法变体不再占语音档位（39 个皮肤音频归属变对）、活动版行不再顶用本句字幕（15319 行只留音频）。正文按「与音频同档」两层取值后覆盖面 **4140/4140 皮肤 · 113,671 条正文**（原 4129 / 73,705）。闸门 `scripts/diag/voice_words_diff.py` 真回退 0（新旧对调则报 32552 红 ⇒ 闸门会红）、`l2d_voice_inventory` 缺失 0/孤儿 0、索引 counts 一字未动。遗留 26 格「音频改档·正文待补」+ 档位分配仍是位置猜测。
14. ⏳ **天津风皮肤2（`tianjinfeng_2`）Spine 动态缺部件 + CG 导出渲成 45° 菱形**（2026-09-27 用户报，**根因未定**）：
     弹窗里躯干、下肢、大狐尾整块不显示，只剩椅子+两条腿+头+一只袖子；同一套运行时的
     `CG_v2/tianjinfeng_2.png` 渲成了 45° 菱形（房间占满、角色缩成中间一小点）。
     **两条已否证**：① 不是换肤问题——5 个 part（本体/`2B`/`2B2`/`2M`/`2T`）都只有 `default` skin，
     `spine_skin_scan.py --only tianjinfeng_2` 报 `gain=0 / parts_affected=0`，§42 那条 `setSkin` 修法在这里不成立；
     ② 不是缺贴图——每个 part 的 atlas 页与同名 png 一一对应，viewer 也报「5 层部件」零失败。
     下一步起点：按 part 逐个单独渲染看**哪一层没落笔**，
     再判是"该层的附件没挂上"还是"同名槽在两个骨架里指不同区域"。
     **具体做法**：给 `gallery_src/cg_export.html` 加 `?parts=` 过滤（只渲指定层）逐 part 出图；
     再对 `2B`/`2T` 比「槽位名 → 附件 → atlas 区域」的映射，看重名的那 44 个槽在两个骨架里
     是不是指同一块图。⚠️ 改 `cg_export.html` 前先看第 17 条的 ⏸️（同目录文件可能仍被并行会话占着）。
     ⚠️ 别和 §45/§46 那两类取景问题混——那两类是"框撑太大画面缩中间"，
     这里是"内容整块缺失 + 形状被转 45°"。
     **同日续查**：其 prefab 确实列了 5 个 SkeletonGraphic 且**全是单位变换**（游戏把 5 层画在同一
     原点）⇒ 不属于下面第 17 条那个 `_hx` 误叠 bug；但它 5 个 part 槽位重名率 17.5%、
     `2B` 的 44 槽是 `2T` 的 390 槽的**真子集**、`data.width×height` 为
     `0×0 / 0×0 / 5063×5501 / 927×720 / 7087×3449`（健康对照 `bailong` 是三个都不为 0 的尺寸）
     ⇒ 结构本身异常，仍未定性。
15. ⏳ **4 张「整张画的每一层都是关闭态」的皮肤**（2026-09-27 §55 顺带查出）：
     `qiye_4` / `kelifulan_4`（各只有一层且它是关的）、`qiye_dark_memory` / `unknown2_memory`
     （`frame_0..3` 四层全关，游戏按剧情逐层激活）。过滤会把它们**清空**，所以规则是"一层不剩就原样保留"
     并记进 `C.INACTIVE_ALL`。要修得先知道游戏在哪一刻激活哪一层，**没有权威依据不许猜**。
     取证：`py -3 scripts/diag/painting_inactive_scan.py`（只读全库扫）+ `painting_inactive_rerun.py`（定向重渲+对照表）。
16. ✅ **「有表行、主包未下发」的 44 张皮肤补上「仅台词」档（2026-09-27 用户拍板 A 后落地，全加法、没动那条 75 分钟语音管线）**：词表第二趟 **44 张 / 565 条正文** + 索引 `voiceText`（皮肤级+船级，只在无音频皮肤上写）+ 前端 tab 判据 `voiceCount>0 || voiceText>0`；台词行**不带播放器**（反向证据：`audio == 变体包条数`）。顺带修掉一个已上线一天的内容缺陷：`{namecode:NN}` 从没展开（**862 个能播皮肤的字幕在显示 `{namecode:98}`**）。见 **§60**、做法 **WF-22**；探针 `PORT`/profile 写死那条另立为**第 20 条**，流水与复核命令外迁 **A21 段**。
17. ✅ **Spine 的分层不再按目录 glob 猜，改认 prefab 权威清单 `parts.json`（2026-09-29 落地并换入）**：全库 234 个目录**多画 30→0 / 少画 0 / 层文件缺失 0**，**15 对本体与 `_hx` 的 CG 全部拉开**（0 对仍逐像素相同）；权威清单由 `extract_spine_v2.py --parts-only` 写、`build_gallery_index.py` 与 viewer/`cg_export.html` 读，**缺文件非零退出不回落 glob**，解析函数只有一份（`compose_paintings_v2.skel_layers`）。⚠️ **本轮最大的坑不是 glob 是硬链接**：那 15 对早在 09-20 去重时被链成同一个 inode，不断链则成对判据永远不过（**§64**）。做法与判据 **WF-14 追加（2026-09-29）**；原第 17 条全文（含五步实施清单）在 **A16 段**，本轮流水 **A21 段**。

18. ✅ **画廊「按钮 / 交互反馈」层重做（2026-09-27 立项 → 2026-09-29 关闭）**：五条真缺陷（同一"选中"语义 5 种颜色 / 两条控制条其实是 UA 原生按钮 / 零 `:active` / 零 `:focus-visible` / toggle 与瞬时动作外观不可区分）**已全部关闭**，定稿见 §6 顶部 ★ 块与 **WF-16 追加（2026-09-29）**，踩坑 **§62**。⚠️ **一条否证别重走**：同日做过一整版**视觉语言重做**（暖墨底 + 单一铜金强调、字阶、卡片三行化、查看器底换掉棋盘格），样板页 `index_b.html` 给用户看过并**被否** ⇒ **整体换色这条路已试且被拒**，方向改为只动按钮与交互反馈。流水外迁 **A21 段**。
19. ✅ **WF-16 第 5 件 `hit_verify` 已补跑通过（2026-09-27 当晚）**：等并发会话的全库任务结束、端口空出后 `--only antu_2,ninghai_4,lafeiii_3` 干净跑：**85 部位 HIT 54 / INGROUP 25 / WIRING 0 / 不可点 6**，随机抽查 3 模型全合格 ⇒ 确认上一轮那 38 条 WIRING 是**探针侧污染**（§60 末段），不是产品回退。成因根治 = **第 20 条**；流水外迁 **A21 段**。
20. ⏳ **CDP 探针的端口与 profile 走 env（根治第 19 条的成因）**：`hit_verify`/`talk_verify`/`interact_verify`
     的 `PORT` 与 `--user-data-dir` 写死，共享工作树里两个会话同时跑必撞（症状是"整序列统一偏移一位"的假数据，
     不是报错）。改成 env/CLI 可覆盖 + 启动前探测端口占用；**改之前先确认没有会话正在跑它**。
21. ⏳ **变体包按条切分，让 44 张「仅台词」皮肤也能点播**（用户未拍板，先不做）：那 36 张的 `voiceExtra`
     是 v1 时代**整包**导出的单个 wav（`Audio/CV/cv-<n>-<battle|gift>.wav`），对不到具体类别 ⇒
     现在只能整包听、配不上逐句正文。要修得重新解码 `-battle/-gift` 包并按 cue 切分（约 10 分钟 + 一次零回退比对）。
22. ⏳ **`yuanchou_2_hx` 的 CG 是 64×2400 的细长条（取景长宽比直接塌成一条）**（2026-09-29 做第 17 条时顺带查出，**先前就存在、本轮没弄坏也没修好**）：新旧两份都是 64×2400，而同目录的 `yuanchou_2` 却从同样的细条被 `localScale` 修复救回成 2400×1332。两者都是单层皮肤，差别只在 skel 本身。⚠️ 别和 §45/§46 那两类混——那两类是"框撑太大画面缩中间"，这里是长宽比直接塌成一条。取证起点：单层皮肤跑 `framingBox` 时 `bw/bh` 为什么是 0.027。


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
要点：**画廊视觉（Q 轮）的待用户拍板项与待办在 §6 顶部 ★ 块，接手先读它**。静态立绘 / Spine 已由 v2 全量收官，Live2D 动作层已于 2026-09-21 按权威映射重建完毕，**2026-09-23 网页交互层三个根因（命中包含判定 / idle 循环 / V-P 坐标系）已修并回归**。接手前先读 §9 理解「游戏数据自洽、不要猜坐标/不要按位置猜参数名」这一核心结论。**验动效一律看内容**（曲线条数、Id 是否命中参数表、值是否随时间变化），不要只看 `currentGroup`/组名标签——空壳也能"启动"，这个坑已踩过一次（`docs/TROUBLESHOOTING.md` §17、`docs/WORKFLOWS.md` WF-7）。**验交互一律用独立锚点**——合成点击若与被测映射同源会自洽闭环、全绿也说明不了对齐（§20、WF-16）。历史 v1 调试见 `docs/archive/`，一般无需再读。

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

### 9.3 七个系统性根因修复 ★教训（全部代码级、零逐角色参数）
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
> 结论再次印证：游戏数据自洽，所有错位都是解析姿势不对。（完整明细含文件行号与验证样本，见 `docs/archive/PROJECT_STATUS_历史归档.md` 末尾「完整明细存档」。）

### 9.4 Spine v2（`scripts/extract_spine_v2.py`）✅
双结构兼容（内联型 + 分离 `_res` 型）+ 外部页纹理按 deps 补齐 → `Output/Spine_v2/`。全量 **232 主包**完成。skel 3.8.99，皮肤为多部件骨骼（B/M/T）需分层合成。

### 9.5 Live2D 核查 ✅（2026-09-21 结论已更正）
266 个 live2d 包本地零缺失、自包含。**旧结论「剩余仅 motion 质量（§2.5 B 类 12 模型）」是错的**：
motion 大面积失效源于我们自己的解析器（帧 0 护栏 + 曲线名按位置猜），不是资产缺口；
已按 `genericBindings`/`crc32` 权威映射全量重建（见 §2.5 与 `docs/TROUBLESHOOTING.md` §17）。
资产层真为空的只有 7 条 clip（`effect` / `idle11` 一类占位动画）。

---

## 10. 本地资产浏览平台 `Output/gallery_v2` ✅（2026-09-15）

- **形态**：本地网页（源 28GB / Paintings 15GB，上线不现实），参照 l2d.su，中文名展示 静态立绘 + Spine + Live2D + 语音。
- **数据**：`build_gallery_index.py`（合并四类 + `ship_name_map` 拼音→中文 812 条 → `index.json/js`；Spine 皮肤附 `cg` 字段指向 `CG_v2/`）+ `make_thumbs.py`（Paintings_v2 + CG_v2 → 380px WebP，CG 缩略图 `<stem>_cg.webp`）。结果 954 船 / 4489 皮肤 / spine 231 / CG 231 / live2d 256 / 语音 268。
- **前端** `index.html`：网格懒加载 + 搜索/阵营/舰种/稀有度筛选 + **类别分段（全部/舰船/剧情角色，主网格按 `category` 分区渲染各带小标题计数）**；详情四标签。「静态立绘」对 Spine 皮肤默认展示全屏 CG（可切换回 painting 原件），支持**滚轮缩放(光标锚点)/拖拽平移/双击100%/全屏浏览/复位**；Spine 标签 `vendor/spine/spine-all.js`(3.8) 分层 WebGL 播放（相机视口/动画过滤已修，**支持全屏**）。服务器统一响应 `Cache-Control: no-cache`，改版后浏览器不再吃旧缓存。
- **前端取景与视角记忆 ✅（2026-09-27，§59 / WF-16 追加）**：修掉「打开皮肤缩得有点小」的两层根因——弹窗上限 1100×880 → `min(1900px,96vw)×min(1400px,96vh)`（2560×1600 上从占屏 43%×55% 到 74%×87%），Live2D 改按 **drawable 顶点框 ∩ 画布**的内容框取景（原来按 Cubism 正方形画布 fit，角色只占 6~8 成）、Spine 留白 1.1→1.05、静态立绘解除「永不放大」上限（双击仍是 1:1 像素）。**A/B 实测内容绝对像素 10/10 变大（x1.69~x3.89），零回退样本**，工具 `scripts/diag/gallery_framing_ab.py`。新增**视角记忆**：三个视图各自的缩放/平移按 `皮肤|标签页` 存 localStorage（只存尺度无关量 ⇒ 换窗口尺寸与进出全屏不错位；LRU 300 条），顶部第三个全局开关「记住视角」可关。顺带修一条老失效：**进一次全屏再退出会把调好的缩放抹掉**（`ResizeObserver` 直挂 `fit()`）→ 改 `refit(preserve)`。另加弹层内快捷键 `←/→` 换皮肤、`1-4` 切标签、`F` 全屏、`R` 复位。交互层零回退：`interact_verify` ALL PASS、`l2d_inspector_verify` 全绿、`hit_verify` **全量 269 模型 / 3309 部位 WIRING=0**（HIT 2330 / INGROUP 913 / NOTCLICKABLE 66 / 可点中率 97.1%，与 §27 那次全库基线 HIT 2338 / INGROUP 905 / WIRING 0 逐项对齐）。
- **视觉语言：定稿 = 水面背景 + 玻璃拟态 + iOS 丝滑（2026-09-29 刷进正本）**。
  前四版背景与两次"整体换风格"全被否，**共同败因是"背景自己在动"**——定稿版把"动"交还给用户：
  静止逐像素不动、划过才起浪；卡片/导航栏是透玻璃（alpha .05 + 折射边墙 + 常驻斜反光，模糊只挂
  进视口的卡）不是磨砂白卡；控件选中走材质态不整块填色；交互只改亮度、全表零过冲。
  验收 `gallery_motion_probe.py` 24 条判据，踩坑 **§62**、做法 **WF-16 追加（2026-09-29）**。
- **源码治理**：画廊前端源码在**仓库内 `gallery_src/`**（唯一权威版本），`Output/gallery_v2/` 是运行目录（gitignore）。**2026-09-26 起两边改成硬链接**（同一份磁盘数据两个路径名），**4/4 已全部换链**（`index.html` / `cg_export.html` / `_gallery_server.py` / `启动资产浏览器.bat`）：改正本即刻生效、不需再部署。`deploy_gallery.py` 三态——默认 copy 修复（断链后的回退手段）/ `--check` **要求 4 个文件全部同 inode，断链或漂移都 `exit 1`** / `--relink` 换链（要求两边逐字节相同，且正本有未提交改动者自动跳过，防打断并行会话）。⚠️ 断链的唯一现实成因是整文件写回式「写临时文件+改名」的原子保存：**16:52 真断过一次，而当时只比内容的 `--check` 给了 `exit 0`（判据漏洞，已改为结构性并写进 AGENTS.md 收尾清单第 1 条——改 `gallery_src/` 正本一律原地编辑）**。当前 `index.html` 因那条未提交改动处于"已断链、内容仍一致"态，待其提交后 `--relink` 补。见 §43 与 WF-16。CG 导出页 `cg_export.html` 同样入 `gallery_src/`；服务器 `_gallery_server.py` 提供 `POST /save_cg` 落盘接口，`--export` 参数直开导出页。⚠️ 服务器按自身所在目录算根，**只能双击 `Output\gallery_v2\` 里那份 bat**。
- **运行**：`启动资产浏览器.bat`（→ `_gallery_server.py`：8777 端口 + `allow_reuse_address` + 端口占用即复用 + 结尾 `pause`，杜绝闪退）。file:// 下立绘/语音可看，Spine `fetch` 被 CORS 拦需走 .bat。
- **运行时库台账**（2026-09-26）：`vendor/` 4 个第三方 JS 只在 gitignore 目录里，版本/来源/sha256 记进 **`gallery_src/vendor/MANIFEST.json`**（3 个的 URL 当日重新下载按哈希逐字节对拍命中），换机器跑 `py -3 scripts/fetch_gallery_vendor.py` 补齐（**哈希+字节数双对上才落盘**，`--check` 只校验）。⚠️ **唯一残留缺口**：`vendor/spine/spine-all.js`（实测 3.8.75，非旧文档写的 3.8.99）没有可按哈希校验的下载源——本机这份与上游官方 3.8 构建不同（499623B ≠ 501448B），只能从 `tools/spine-viewer/spine-runtime/` 取，而 `tools/` 也在 gitignore。要彻底封掉需二选一：把 501KB 提交进仓库（先确认 Spine Runtimes License 允许），或改用可哈希校验的上游构建并回归 Spine 播放。**未拍板**。
- **限制**：~~Live2D 暂只显示贴图~~ **已接动作播放**（2026-09-20，`vendor/live2d/` 三脚本本地就位，见 §6.7）；Live2D/Spine 标签均需走本地服务器（file:// 下 fetch 被 CORS 拦）。运行时库的可复现性与那条未拍板的残留缺口见上一条。

---

> **历史归档**：v1 时代攻关路线、多部件合成已知问题清单（Bug#1-#4）、7-30/7-31 修复记录、bj 背景层专项、调参工具 v3-v6 会话流水、旧 Spine Viewer 调试史 → 全部见 `docs/archive/PROJECT_STATUS_历史归档.md`。
