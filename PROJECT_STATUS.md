# 碧蓝航线 AssetBundles 解包项目 — 进度总结

> **生成时间**: 2026-09-27 21:40（同日续：**静态立绘「头部发黑」根因修掉并换入 48 张** ——
> `parse_painting` 从不读 `GameObject.m_IsActive`，于是把游戏里**关着**的层一律画上去：
> `shadow` 纯黑剪影 26 处（= 用户报的头黑）、`shop_hx`/`*_shophx` "NOT ABLE TO DISPLAY" 遮挡条 60+ 处、
> `chicheng_alter_rw1..4` 备用画法 16 处。全库 4488 张里 **125 张命中 → 只有 48 张画面真的会变**
> （73 张的白条本就被 `is_lighting` 挡着 ⇒ **命中数 ≠ 换入数**）。旁证：`_n`（无背景版）的 `bj` 节点
> 恒 `m_IsActive=False`，与用户 09-20 纠正的语义完全对上 ⇒ 这是游戏的真开关，不是启发式。
> 两条硬护栏：**`face` 槽豁免**（它恒关、运行时才激活，是 §48 叠层的输入）、
> **全层关闭的 4 张不清空**（`qiye_4`/`kelifulan_4`/`qiye_dark_memory`/`unknown2_memory`，见 §6 第 15 条）。
> 零回退对照 12 张逐字节全等；换入走 `painting_swap_in.py --break-hardlink`（赤城·改 8 个文件原本
> 两两共享 2 个 inode，过滤后 8 份渲染全不同 ⇒ 必须断链，否则顺 inode 串改共享者），
> 四道硬检查全绿、附带伤害 0、缩略图 ok=48 err=0；**落码后**再把 125 张重渲一遍与已验证结果逐字节比对。
> 同日另修 **敦刻尔克被标成「皇家·驱逐」**：配置表脏行 `stats.id=900106`（name 写敦刻尔克、
> english_name 却是 HMS Vampire）钻了「组内取 min(id)」的空子；改成「先要求 `skin_id` == 组内基皮肤」后
> **970 组只有 1 组改判**，闸门加的是**方向性判据**而非例外名单。见 **§55 / §56 / §9.3 第 7 条**。
> 历轮（2026-09-20 ~ 09-26 上午）会话流水已**逐字**外迁 `docs/archive/2026-09-26_PROJECT_STATUS_外迁归档.md`（A1/A2 段）；
> 结论性知识在 `docs/TROUBLESHOOTING.md` §25~§44 与 `docs/WORKFLOWS.md` WF-14/15/16/17。本文只留当前状态。
> **用途**: 跨会话对接。**v1 时代历史已外迁 `docs/archive/PROJECT_STATUS_历史归档.md`**，本文只保留当前状态与主线。当前待办见 §6。
>
> **【其它待办】**~~§6.11 HitAreas 生成规则漏了 `touch_*` 组名~~ **已于 2026-09-22 修复落地**（13 模型真实判定区、全库 806/807）｜**官方交互层**：用 `CubismRaycastable` 真点击区替换现在猜的 `Touch*` drawable HitAreas、以及 `CubismExpressionController` 表情还原（注意运行时不读 pose3.json/exp 需验证）｜§6 待办 7「晶环联盟阵营码」三选一（A 逆向 sharecfgdata 加密 / B 走 381 旁路 / C 搁置）｜**剧情 CG 混进 `Paintings_v2/`** 的识别与分离（用户指出"脸黑的基本都是剧情 CG"，与缺脸是两类问题，见 §6.8）｜**结构隐患**：~~`azdata_*.json` 权威元数据源仍住在可被清理的 `.diag/`~~（**2026-09-24 已迁 `inputs/azdata/` + sha256 台账 `MANIFEST.json` + 校验 `scripts/diag/check_inputs.py`；数据本体仍不入库**，理由：9.2MB 游戏配置属资产、zlib 后 0.67MB 虽小但仓库原则是「只承载可复现的工具与知识」）——剩余一项：18 个核心脚本硬编码 `D:\Azur Lane Assets` 绝对路径（建议改 `__file__` 推导）｜**语音产物口径已定：无需单独备份**（可确定性再生，体检 `scripts/diag/l2d_voice_inventory.py`），不可复原的只有 `inputs/azdata`｜低优先：声优中文姓名回填、UI/图标批量导出、`organize.py`。

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
> **2026-09-21 根因重建**：旧产物 5037/8154 条动作是 `"Curves": []` 空壳（`num_keys>100` 护栏误杀帧 0），
> 其余 3117 条**曲线名全部错位**（按"curve idx==参数序号从0连续"取名，实际稀疏）→ 就是"乱飘/乱闪/没反应"。
> 现改为 `genericBindings[i].path == crc32("Parameters/<GameObject名>")` 权威映射 + 贝塞尔 + 结构自检。
> 旧数据备份 `Output/_OLD_bak/l2d_motion_20260921_141226/`。详见 `docs/TROUBLESHOOTING.md` §17。
> ⚠️ 旧结论「B 类 12 模型属 motion 质量、资产无缺口」作废：除上述 7 条外均可解出，是解析器缺陷不是资产缺陷。
已知限制：StreamedClip 未完全逆向；HitAreas 用 moc3 `Touch<X>` drawable 而非官方 `CubismRaycastable` 真点击区（**2026-09-22 §6.11 修后全部 269 模型均带真实 HitAreas**，仅 `z46_3` Special 框嵌 Body 属模型自带歧义）；0.226% 绑定（疑 Drawable 颜色）运行时无对应 target，跳过。
> **网页交互层状态（2026-09-23 §6.12 + §21）**：点击命中已修「四边形包含 + V/P 坐标系换算」，idle 循环已交回运行时（前端零定时器），动作切换恢复交叉淡化，运行时自加的假呼吸层已关闭，另有判定区可视化与参数·部件检查器；改前端前**必读 WF-16**（六条硬规则 + 回归六件套）。
> ✅ **2026-09-27 判定区可视化的"幽灵标签"已修**：`drawAreas` 旧代码把标签 x 无条件夹进视口，于是画布外几千像素处的换装按钮把**名字**贴到了屏幕右边缘（框本身看不见）→ 用户报"角落里有判定区却点不到"。现**多边形仍按 `__L2_HITUSE()` 全画，标签只在框与视口相交时画**（另暴露 `__L2_HITSHOW()` 供探针同源比对）。命中链路与 `model3.json` 数据**一字未动**。判据：`qiershazhi_2` 标签 16→3、`wuzang_4` 78→4、`antu_2` 57→4，对照组 `chuyue_2` 8→8、`lafeiii_3` 10→10（零误杀）；`hit_verify` **全量 269 模型 / 3309 部位 WIRING 0 / OUTSIDE 0**（可点中率 97.1%，随机抽查 202 模型 0 不合格）。详见 **§51**。
> ✅ **2026-09-26 语音被掐已修**：语音原先注入 `definitions[g][0].Sound`，被库的 SoundManager 按"下一条动作 dispose 上一条"托管 → 动作一结束话就断（实测 `benningdun_2/touch_head` 在 `currentTime=4.48s` 处被 `pause`，而该 ogg 长 9.24s；该皮肤有 6 组超标）。现改由页面自持 `Audio` 元素，只有用户再次触发或切标签/换皮肤才打断，运行时回落 idle 不打断。**动作时长本身是忠实的**（`Meta.Duration` == 曲线末帧 == 源 clip），不要往数据层找原因。详见 §41 / WF-17 追加。
> ~~⚠️ §21 的根因修复目前只在 `antu_2` 一个模型上换入验证、其余 268 个模型仍是旧数据~~ → **2026-09-24 已全量落到 269 个模型**（覆写过程有事故，见下一条与 `TROUBLESHOOTING.md` §25）。当时判定的两个系统性错误（贝塞尔控制点写成归一化分数 → 部件各动各的；只读 `m_StreamedClip` 丢定值曲线 → 切动作时参数回不到静止位）现已在全库消除，`aerbien_3` 这类曲线数从 445/640 补齐到 640/640。
> **✅ 2026-09-24 全量重导已落到 269 个模型（含事故记录）**：`antu_2` 样本 104/104 与已验收生产数据逐字节一致 → 全量 `clips 8154 / shell 7（=资产层真为空的 7 条）/ misassign 0 / PartOpacity 79 模型`、曲线总数 **944,136→2,662,615**。**过程有事故**：脱离启动时 `L2D_OUT_DIR` 未被子进程读到，重导**跳过了「临时目录→审计→备份换入」直接原地覆写** `Output/Live2D`（同一条 ps1 里另两个配方变量都生效，机制不可复现）；已核实 `.diag/l2d_new`（269 模型 / 曲线 944,136，与本文档记录的覆写前总数逐字相等）即覆写前状态并复制为 `Output/_OLD_bak/l2d_motion_pre_swap_20260924/` 恢复回滚，闸门补跑在正式目录上，并按「写向一律走 argv」给 `extract_motions.py` 加了 `--out`（不给即拒绝 `--all`）。根因与教训见 **`TROUBLESHOOTING.md` §25**。
⏳ **9 个 bundle 已于 2026-09-22 换入**：benningdun_2 / bunao_3 / feiteliekaer_4 / gangyishawa_3 / guanghui_9 / pulimaosi_3 / sebao_2 / shi_3 / wuzang_4——9 张卡的 `live2d` 字段已进 index.json，`Output/Live2D` 现 **269 个模型**。换入后逐字段 diff 证**非 live2d 字段零变化**（ship/skin 集合不变、仅 9 卡 +9 live2d 项）。
> ✅ **2026-09-26 更正：上面那句「内容判据全绿：9/9 模型加载 + idle 驱动参数」是代理指标假绿灯，作废。** 当时唯一没做的检查是**看画面**，而这 9 个里有 5 个（benningdun_2 / feiteliekaer_4 / sebao_2 / shi_3 / wuzang_4）从换入第一天起就渲染成"几十个部件碎片叠一堆"，用户于 2026-09-26 才报出来。
> **根因**：`model3.json` 的 `Textures` 按 UnityPy 对象**枚举序**落盘，而 moc3 只按**索引**消费它 → 整套贴图错位。全库扫描：乱序的恰好 5 个、坏的也恰好这 5 个，其余 264 个碰巧枚举有序。
> **修法**：`fix_model3.py` 补上归一段（WF-6 三个月前就写了这条决策但从未实现）；闸门 `scripts/diag/l2d_texorder_check.py`（只读检查，乱序退出码 1，`--apply` 才写）现 **269/269 升序**。看图工具 `scripts/diag/l2d_shot_models.py` 新增（走画廊真实入口按 canvas clip 截图）。
> **验证**：5 个修复后逐个目视全部成形（海滩跑车 / 棋盘格卧室 / 暗室桌面 / 后巷 / 演唱会舞台）；对照 `bunao_3`、`pulimaosi_3` 未被写入、截图与修复前一致；语义 diff 证 5 个文件除 `Textures` 顺序外零字段变化，原件备份 `.diag/m3_snap/*.bak_texorder`。详见 `TROUBLESHOOTING.md` §40。
> **目视覆盖 26/269**，按 `(moc3 版本 × 贴图数)` **15 个分桶全覆盖**（修复 5 + 对照 2 + 枚举序最乱 5 + 分桶抽样 14），未发现新增破损。⚠️ 结论边界：这只证"贴图索引绑定这一类故障全库已无残留"，**不等于** 269 个模型没有别的视觉缺陷（其余 243 个未被目视覆盖，非绑定类问题仍按个案查）。
> ⚠️ 另记一条当时的真教训（与画面无关，仍有效）：运行时把每条 idle 解析成 `isLoop:false`（全 269 模型一致的既有管线特性），idle 只播一次即回静；故**动效验证必须在播放窗口内高频采样**，等 ~12s 后两次快照比对会因短 idle(5~8s) 已播完回到静帧而假报 `moved=0`（本轮曾据此误判 bunao_3/guanghui_9，密采证伪）。临时产物 `.diag/l2d_new9/`（467MB）已冗余可清理。

### 2.6 Spine 动态立绘 ✅（v2 提取 + 全屏 CG 导出 + viewer 修复，2026-09-19）
`scripts/extract_spine_v2.py` 双结构兼容提取到 `Output/Spine_v2/`，232 主包。gallery 内 `spine-all.js`(3.8) 分层实时播放。**2026-09-19 三修复**：①相机视口（`SceneRenderer.resize()` 不更新 viewport → 比例怪）②`my` 变量遮蔽 TDZ（假「N 层失败」+ 取消失效）③过滤 0 秒空占位动画、默认播 `normal`、缺动画层回落 normal；另支持 JSON 骨架（beierfasite_g）。**全屏 CG 导出**：`cg_export.html` 渲染 setup pose 批量落盘 `Output/CG_v2/` **231/231 成功**（含二次像素包围盒构图修正）。
> ✅ **2026-09-26 补 `setSkin`（此前 viewer 与 CG 导出一次都没调过）**：spine-ts 3.8 的附件时间线经**当前 skin** 解析，不设 skin ⇒ 命名 skin 独有的部件整块不显示。用户报「阿罗芒什缺下半身」即此。全量扫描 `scripts/diag/spine_skin_scan.py`：**331 part 中受影响 4 个**（`yunlong_2` 缺 69 槽 / `feiteliedadi_5` 52 / `aluomangshi_2` 47 / `yuekechengii_4` 14，补回的是大腿/小腿/脚趾/躯干）。viewer 现按「动画跑起来后曾挂上附件的槽位数」自动选 skin，并加「皮肤」下拉可人工比（阿罗芒什 `1` vs `2` 覆盖数打平 201/201）。同视口对照证：设 skin 前后**画面大小不变**，只是腿回来了。详见 §42 / WF-14 追加。
> ✅ **2026-09-26 CG_v2 已按 `animFrame` 全量重导**：`cg_export.html` 加上与 viewer 同一套 skin 选择 + 新增默认关闭的 `?animFrame=1`（取默认动画第 0 帧）。**关键取证**：光加 `setSkin` 对 CG 导出**无效**——CG 渲染 setup pose，而 setup 附件取自 `slotData.attachmentName`、与 skin 无关（`aluomangshi_2` 四种 skin 下 setup 附件恒为 145，腿一条不回来）；腿是动画第 0 帧的 AttachmentTimeline 挂上去的（设 skin + apply 后 201）。备份 `Output/_OLD_bak/CG_v2_pre_animframe_20260926/`（231 张逐文件 md5 全等）→ detached 全量重导 **234/234 完成 0 失败**（含 3 张以前没有的：`jinluhao_4`/`xianghe_4`/`yueke_ger_4`），229/231 内容变化、未变的正是 `yuanchou_2`/`yuanchou_2_hx`（怨仇，符合预期）。逐张看图：`aluomangshi_2` 下半身回来、控制组 `2b_2` 仍满幅无回退。
> ✅ **2026-09-26 修弹窗取景：`boundsOf` 不再把"挂了附件"当成"会画出来"**（§45 / WF-14 追加）。整屏闪黑/闪白遮罩（实测最大 32967×29970 单位）setup alpha=0、一个像素不落，却决定取景框 → 弹窗里画面缩成中间一小块。全量扫描 `scripts/diag/spine_framing_scan.py`：**328 part 中受影响 13 个**（>1.05 倍），5 个 >1.5 倍、3 个 >3 倍，最大 9.6 倍；其余 315 个包围盒逐字不变。修法 1 行（用 `slot.data.color.a`，不能用会被动画改写的 `slot.color.a`）。**逐张看图 13+3 全部无裁切回退**：四万十长轴占满 0.157→0.842、法戈 0.165→0.706。两条否证已入库：「沿所有动画采样曾 alpha>0」在阳性对照上等于没修；首帧 `readPixels` 收紧在弹窗里会把 `mojiaduoer_5` 放大成一屏模糊色块（纹理首帧未上传完）。
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

**核心脚本**：`scan_assets.py`、`export_assets.py`、`export_cue_audio.py`、`reconstruct_live2d.py`/`fix_model3.py`/`extract_motions.py`(★2026-09-21 权威映射重写)/`apply_live2d_motions.py`(★临时目录→备份换入)、`compose_paintings_v2.py`(★v2)、`extract_spine_v2.py`(★v2)、`export_dependency_manifest.py`、`build_gallery_index.py`、`make_thumbs.py`、`deploy_gallery.py`(gallery_src↔Output 硬链/漂移检查)、`fetch_gallery_vendor.py`(按 vendor 台账 sha256 补齐第三方库)、`mumu_sync.py`、`ship_name_map.py`、`scrape_wiki_fast.py`。

**可复用诊断/验证工具 `scripts/diag/`**（18 件）：`scan_faces.py`(脸洞扫描)、`make_face_cmp.py`/`make_review_sheet.py`(改前后对比图/复核总表)、`l2d_motion_audit.py`(★全量动作健康审计：空壳/错位/PartOpacity/时长，`L2D_OUT_DIR` 可审任意产物目录)、`l2d_ab.py`(★同一模型新旧 motion 的渲染级 A/B，**只在换入前构成对照**)、`l2d_diff_dirs.py`(★两个产物目录逐 clip gained/changed/lost)、`l2d_sweep.py`(★全量加载+动作内容判据扫描；**2026-09-22 重写为 Python 侧逐条 evaluate + 每 N 模型重载页面**，修掉旧版「单次 evaluate 卡第一条不返回」与「单 Chrome ~110 后 WebGL 断连」，全库 269/269 一次跑通)、`l2d_verify.py`/`l2d_click.py`(抽样与真实点击路径无头校验)、`hit_verify.py`(按部位点击触发断言，支持 `--only`；2026-09-23 起合成点击经 V2P 走**真实路径**)、`interact_verify.py`(滚轮/拖拽/兜底/空白/部位五项交互断言)、`l2d_coord_forensics.py`(★**2026-09-23 新增**：坐标系取证——可见头/胸/髋三点反查应落 Head/Special/Body，专治「张冠李戴」且不构成自洽闭环)、`l2d_inspector_verify.py`(★**2026-09-23 新增**：判定区可视化+参数·部件面板+滑杆往返+过滤器四项验收)、`run_cg_export.py`(Spine CG 批量导出驱动)、`dedup_plan.py`/`dedup_apply.py`/`dedup_httpverify.py`(硬链去重三件套)、`gen_story_md.py`(复核清单生成)。**游戏版本更新怎么跑 → WF-15**；**Live2D 动作重建怎么跑 → WF-7**；**Live2D 网页交互改动/回归怎么跑 → WF-16**。

**文档**（导航见根目录 `README.md`，写入路由见 `AGENTS.md`）：
- `docs/DEV_LOG.md` 操作手册 · `docs/WORKFLOWS.md` 可复用工作流 · `docs/TROUBLESHOOTING.md` 踩坑 · `docs/ERRORS.log` 错误流水
- `docs/tools/` ALPA、AssetStudio 使用说明
- **项目技能库 `.agents/skills/`**（8 个，入库）：`live2d-web-runtime-integration`(新建)、`unity-assetbundle-painting-restore`、`headless-chrome-cdp-batch-export`、`safe-pipeline-fix-targeted-rerun`、`windows-hardlink-dedup-verify`、`windows-local-server-launcher`、`cn-blocked-resource-mirror-fetch`、`project-doc-governance`——做同类任务前先查这里，别从零摸索
- `docs/archive/` 历史归档（含 `PROJECT_STATUS_历史归档.md`、旧目录审计报告、旧 Spine 交接）

**数据**：`asset_manifest.json`、`Output/dependency_manifest.json`(86,398 条官方依赖表)、`Output/WikiData/ship_data.json`、`Output/gallery_v2/index.json`。

---

## 6. 接下来的任务

### ★ 2026-09-16~21 gallery_v2 质量复核（1~10 全部闭环；11 为 09-21 新查出、用户决定暂缓；换入待发项见头部）

> 1~4. ✅ **已闭环**（细节见归档 A4 段）：静态立绘嵌套容器错位（`52782a7`，85 张换入）/ i404 型背景缝隙（10 张）/
>    mesh 越框裁头（55 张换入，见 §9.3 第 6 条）/ Spine 动态 + 全屏 CG 导出 231/231（WF-14）。
5. 🟡 **元数据重建（A 收尾已完成：`Output/ship_meta.json` 已产出，交接点=B）**：
   - **脚本**：`scripts/build_ship_meta.py`（默认 `--diag` 只读，`--write` 产 `Output/ship_meta.json`）。运行：`PYTHONIOENCODING=utf-8 python scripts/build_ship_meta.py --write`。产物键=画廊 bundleID（Paintings_v2/Spine_v2/Live2D/CG_v2 目录名并集，共 4492），值=`{cn,en,faction,type,rarity,voice_actor,category,base_painting,source[,数值码]}`。
   - **桥接路径（⚠️已实测校正，覆盖 §6 旧假设）**：磁盘 stem —剥变体后缀(`_n/_hx/…/罗马数字紧跟`)→ 基 `painting` → `skin[painting].ship_group` →（`stats.skin_id` 命中皮肤的组，实测 4118/4119）→ 舰级 `nationality/rarity/type/english_name`。**旧记录里“用 `ship_group` 直接反查 stats”不成立**（1270 个 ship_group 仅 268 落在 stats 键）；**变体皮肤须经 `ship_group` 归并到舰**，不能靠自身 skin.id。
   - **成品实测（2026-09-25 解析优先级改造后）**：bundleID 4495 条，source 分档 painting 2493 + suffix 1788 + **painting_ci 119 + suffix_ci 46**（大小写不敏感回退）+ **npc_table 36 + npc_family 8 + family 2**（秘书舰 NPC 表 / 同族前缀）= **4492 有名字（99.93%）**，仅剩 **3 个真无源**：`_ab`、`unknown`、`tansuozhe21_2`。改造前是 painting 2493 + suffix 1788 + fallback(手抄表) 136 + manual 2 + unresolved 76。分类 ship 4221 / story 274；阵营分布 重樱824/白鹰729/皇家622/铁血492…，空阵营 0。
   - **顺带纠正 76 处手抄表错名**（`SHIP_NAME_MAP` 被配置表接管）：`hdn101` 伊织→涅普顿（整条 hdn 系列原错位一档）、`lafeiii` 拉菲III→拉菲II、`i13` I-13→伊13、`missr` R小姐→好人理查德、`haixiao` 海啸→海咲。第三方裁判：新值命中维基名表 70/76、旧值 13/76、**「只有旧值命中」0 条**。画廊侧已生效：组名修正 24 组、补阵营 38 组、组/皮肤集合零丢失（`with_cn` 899→910）。
   - **✅ 索引层那一截已接上（2026-09-25 同日第二轮）**：`build_gallery_index.py` 的组名新增**最后一级加法兜底**——`base` 是合成前缀（`linghangyuan1`/`nabulesi` 这类不是任何 stem 的组键）时，取同 base 兄弟里来源档属于 `AUTHORITATIVE_CN` 的那条 cn；刻意排在 `SHIP_NAME_MAP` 之后 ⇒ **只可能把"当前显示拼音"的组变成有名，既有名字一律不动**。画廊组 `with_cn` 910→**984**（+74 组），组/皮肤集合零变化、已有名组四字段零改动（逐条比对过）。顺带查出**第二层根因**：5 个秘书舰换装（`linghangyuan1_1/_5`、`linghangyuan3_2`、`lingyangzhe3_2`、`tansuozhe_2`）本来被皮肤表精确命中，而皮肤行 `name` 是**皮肤标题**（TB / 超级AI-TC / 数据集：无数的我 / 入浴的小恶魔 / 悠悠假日私语时）→ `build_ship_meta` 改为：该立绘同时在秘书舰 NPC 表里时实体名取表内 `name`，皮肤标题留在 `skin_name`，并记 `name_via=npc_table:<表键>` 供审计（8 条含 `_n` 变体）。
   - **⏭️ 新的可选待办**：索引层还有 **112 组**显示的是手抄表名而配置权威名不同（`missr` R小姐/好人理查德、`tbniang` TB娘/领航员-TB、`strength` 力量/仲裁者·司特莲库斯·VIII、`ryouko` 凉子/天原凉子…）。把兜底顺序换成"配置优先"是一次影响 112 张卡的可见改动，**未经用户拍板不得动**。
   - **闸门**：`py -3 scripts/diag/ship_meta_authority_diff.py`（退出码即结论）——受保护档 `painting/suffix` 字段改动必须为 0，**唯一可放行的是逐条回查秘书舰表通过的 `name_via=npc_table:*` 皮肤标题→实体名**（要求原皮肤标题仍留在 `skin_name`）；条目集合不得增减；换档只允许落在白名单新档；无源数须等于期望。见 `TROUBLESHOOTING.md` §39。
   - **数值码→中文标签表已写进脚本常量**（NATIONALITY/RARITY/TYPE，对齐游戏内筛选词表）：nationality 1白鹰 2皇家 3重樱 4铁血 5东煌 6撒丁帝国 7北方联合 8自由鸢尾 9维希教廷 11郁金王国 96飓风 97META 98其他(布里) 102~115各联动；rarity 2普通 3稀有 4精锐 5超稀有 6海上传奇 18超稀有；type 1驱逐…24风帆。游戏筛选里的「晶环联盟」本快照(9.7.381)无对应码 → 前端归「其他」。
   - **✅ 两个决策已定**：① `voice_actor` = **只存数字 id**（CV 姓名表未缓存，以后再补映射）；② 非核心码(98/111~115) = **经验名 + 兜底原样保留**，不逐个核。
   - **✅ B 已完成（2026-09-20）**：`build_gallery_index.py` 元数据主源切 `ship_meta.json`，舰名/阵营/舰种/稀有度取 ship_meta（未解析条目回落 `SHIP_NAME_MAP`+Wiki，如 `kelei`→可畏/皇家保住了），`category` 已落 index.json。**根因**：`build_ship_meta.py` 舰名原取 `ship_skin_template.name`（皮肤名，含 433 个 `{namecode}` 占位符 + 皮肤主题标题），改取 `ship_data_statistics.name`（实测 0 占位符），237 舰级占位符归零（`weizhang`→尾张、`linggu`→铃谷、`xinzexi`→新泽西、`antu`→安土，名称与阵营一致）；`META/灰烬`（`_alter` 形态）经 `normalize` 守卫拆为 56 独立卡。逐船四字段零回退。⏭️ **下一步 = C**：前端按 `category` 分「舰船/剧情角色」+ 筛选器；D Live2D 动作播放。
> 6~12. ✅ **已闭环**（细节见归档 A5 段，结论在 §13~§20）：剧情角色与舰船分级（ship 881 / story 127）/
>    Live2D 动作播放 + 按部位点击（`HitAreas` 区名与动作组 768/768 精确匹配）/ missd 黑影（属真缺脸，已随第 9 条修）/
>    I-168 皮肤2 脸部白块（34 张换入；`leiniya_wjz` 靠**收紧门控**自动排除，不写例外名单）/ Live2D 动作层根因重建
>    （曲线 179,072→856,870）/ HitAreas 生成规则修正（13 模型）/ 网页交互三连修
>    （包含判定 + idle 循环交回运行时 + V/P 坐标系换算 → **接手前端先读 WF-16 六条硬规则**）。

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
9. ✅ **Live2D 动作数据全量重导已落到 269 个模型（2026-09-24）**：`clips 8154 / shell 7（=资产层真为空的 7 条）/
   misassign 0 / PartOpacity 79 模型`、曲线总数 **944,136→2,662,615**、`l2d_sweep` 全量 **269/269 失败 0**。
   `hit_verify` 全库基线已重标定：269 模型 / 3309 部位，**判据 = WIRING 必须为 0**（旧「806/807」口径作废，见 §27）。
   过程含一次原地覆写事故与三道闸门加装 → 见 **§25** 与 WF-16；已完成的 runbook 与旧基线讨论见归档 A7 段。
   ⚠️ **数据源天花板（别再攻）**：参考版约 **7% 的贝塞尔段无法从 Unity 数据还原**（四种切线候选最高只拟合 16.7%，
   且那是平凡情形）→ 只能用线性弦近似，表现为缓动略少。
   ~~播完 `touch_idle*` 后判定区集体出画不恢复~~ → **2026-09-23 已修**：非 idle 参数残留复位（`gallery_src/index.html` 的 `paramSets` 登记 + 回 idle 后写回 moc3 默认值），探针 after 出画数回到 53 == before、位移 0；根因与两条踩坑见 §21 末段，可复用做法见技能 `live2d-web-runtime-integration` §3.8/§7.2。
10. ⏳ **Live2D 动作语音：全量导出 + 出声验收 + 技能沉淀（2026-09-23）**
   管线与判据见 **`docs/WORKFLOWS.md` WF-17**，命令语义与实测证据见 **`docs/TROUBLESHOOTING.md` §23**。
   **✅ 2026-09-23 两个闸门都已过**：
   1. **耳朵验收已过**：用户实听确认「点动作有声音」（此前一轮报"完全无声"实为**改完没部署**，见 WF-17 踩坑首条）。
   2. **全量已跑完**：`--all` 覆盖 270 个 Live2D 皮肤 → **253 个命中 ACB 并导出**、**17 个无 ACB**、**0 个"有 ACB 但动作组零交集"**；产物 **5914 个 ogg / 323 MB**，映射表 `Output/gallery_v2/l2d_voice.json` 含 **253 个皮肤**。
   脚本已入库（commit `727fe04`）：`scripts/extract_live2d_voice.py`（新增 `--all` 旗标——原先只认 `L2D_VOICE_ALL=1` 环境变量，用 `Start-Process` 脱离进程起时不继承环境变量，导致第一次"看起来起起来了"实际直接走用法分支 `exit 1`）、`scripts/diag/l2d_voice_probe.py`。
   **仍待办**：① ~~两条别名仍是语义推断，待按耳朵裁定~~ **2026-09-25 已由游戏自己的表证实并升级为表驱动**（`extract_live2d_voice.py` 的 `ALIAS` 改读 `inputs/gamecfg/character_voice.json`）：`character_voice` 给出 `touch→resource_key=touch_1 / l2d_action=touch_body`、`touch2→touch_2 / touch_special`，另有第三条 `headtouch→touch_head / l2d_action=touch_head`（此前画廊无此认知）⇒ 且**同一张表又认出 6 条此前不知道的别名**(`battle→warcry`/`complete→expedition`/`hp_warning→hp`/`mission→task`/`wedding→propose`/`win_mvp→mvp`)，要重导语音映射才吃得到（单皮肤 `--report` A/B 已过，写盘待放行）。见 §35 与 WF-17 追加。② **口型未做**（vendored 库无音频驱动口型，需自接 WebAudio 包络写 `ParamMouthOpenY`）；③ **Spine 与静态立绘的配音仍缺** ⚠️ 2026-09-26 已定位四层根因并备好管线（**全量导出待放行**，见下方"语音 v2 暂停点"）；④ 详情页语音归并还依赖那张 719 条的社区 `CV_MAP`（安土都不在表里 → `voices=[]`），可改用 skin id 推导一并修掉 —— 同日取证：`index.json` 里 **740/1008 组船 `voiceCount=0`**，链条 `CV_MAP(719)→中文名→拼音` 一路漏，而磁盘实有 **938 个船级语音包**（平均 ~35 条 cue/包）。

   **语音 v2 已落地（2026-09-27：①②③ 完成并验收，④ 否证）**：
   - **新脚本已入库**：`scripts/extract_cv_voice.py` —— 按**船级语音包去重**解码（`Audio/CV2/cv-<n>/<cue>.ogg`，皮肤只写引用，不再一份皮肤一份音频），覆盖全部皮肤而非仅 Live2D 目录；产 `Output/gallery_v2/skin_voice.json` = `{皮肤:{cv,idx,src,l2d:{动作组:[路径]},tap:{touch_body|touch_special|touch_head},lines:[{cat,label,f,ev}]}}`。
   - **修掉的系统性语义错**：cue 名尾部 `_N` 是**皮肤序号**（= skin id 末位），旧脚本 `VARIANT_SUF=['','_1','_2']` 当成随机变体全导、前端 `Math.random()` 抽一条 ⇒ 三皮肤船 2/3 概率播到**别的皮肤**的台词，`_9`（改造皮肤）永远取不到。取证见 §47。
   - ✅ **① 前端接线已应用并部署**（2026-09-27）：`git apply scripts/diag/voice-v2-frontend.patch` → 64 增 24 删，
     三格（静态立绘 / Spine / Live2D）共用一条语音条；前端不再 `Math.random()` 抽条目，改为按导出侧选好的本皮肤序号直取。
     `deploy_gallery.py` 已 copy 刷平（改正本必断链，提交后 `--relink` 补回）。
   - ✅ **② 全量导出已跑完**（脱离宿主进程 + 进度行轮询，实测约 75 分钟 / jobs=3）：
     解码 **843 包**（0 失败），产物 `Output/Audio/CV2/cv-<n>/*.ogg` + `Output/gallery_v2/skin_voice.json`。
   - ✅ **②b 定位器修复后增量重跑（2026-09-27 下午）**：原口径"499 无解 = 234 缺包 + 265 快照滞后"
     **整条是误判**——真因是 `azdata` 皮肤表里 `painting` 有大写（`2B`/`A2`/`HDN101`）而磁盘目录名小写，
     查表大小写敏感导致 145 张明明有包的皮肤被判无解（§53）。修完：
     **可定位 3995 → 4140、无解 499 → 354、包 843 → 889、音频 41,193 个 / 2424.5 MB**；
     闸门通过（真丢组 0 / 磁盘缺失 0 / <2KB 占位 0），映射逐字段比对 **消失 0 / 新增 145 / 变化 79**
     （79 全是 `sibling-tier → row`，包号与序号未变）。新工具 `--skip-done` 让这种重跑从 75 分钟降到几分钟。
   - ✅ **已裁定关闭（2026-09-27 用户："可以不用管它了"）**：剩余 354 无解里 **84 张是身份后缀没剥**
     （`_memory` 回忆剧情 / `_rank` 排行榜立绘 / `_heihua` 黑化 / `_ex` / `_wjz` / `_idolns`）。
     刻意没修：它们可能是**另一个发声实体**，剥后缀 = 把别人的台词派给它（§47 型"不报错的语义错"）。
     画廊侧维持"🔇 该皮肤无语音"的显式留空口径，**别再当待办重提**。其余：224 张两侧都无源（§49）+ 16 张 `voice_actor=0/-1`。
   - ✅ **③ 零回退闸门通过**（`scripts/diag/l2d_voice_diff_check.py`，退出码即结论）：
     (皮肤,组) **3263 → 79323**、皮肤 253 → 3995、**磁盘缺失 0 / <2KB 占位 0**；
     闸门抓到 **4 个"丢组"（全是 `touch_head`）**，逐条查证是**旧表把别的皮肤序号的台词派给了本皮肤**
     （如 `bulaimodun_2`(序号3) 拿到 `touch_head_2.ogg`，那其实是 `bulaimodun_4` 的）⇒ 新表删掉属**修正**；
     已把这条裁定写成**规则**（按 cue 尾部 `_N` 与本皮肤 `idx` 比对）而不是例外名单 ⇒ **真丢组 0**。
     另新增 7 个类别各 252 皮肤（`detail/feeling1-5/upgrade`）。
     **浏览器实播验收**（新工具 `scripts/diag/voice_v2_verify.py`，走真实 UI 路径 + CDP 包住 `window.Audio`）：
     静态立绘 `congmang_2_hei` / Live2D `ninghai_4` / Spine `huanchang_2` 三格各点一次，
     全部 `paused=false` + `currentTime` 在涨 + `err=null`，且**文件名正是本皮肤序号档**
     （`touch_1_1.ogg` / `expedition_3.ogg`）；无语音皮肤 `sairenboss14_jz` 显式显示 🔇。
     WF-16 回归子集同跑：`interact_verify` ALL PASS、`l2d_inspector_verify` 判据全 true、
     `hit_verify --only antu_2,ninghai_4,lafeiii_3` **WIRING=0**。
   - ⚠️ **验收脚本自身差点报假绿灯（已修）**：`let SV` 不挂到 `window` 上，探针用 `window.SV` 取恒为 `undefined`
     ⇒ 三个视图一个都没挑到样本、只有"无语音"那条空洞通过，输出却是一片 ✅。
     通用形状：**探针取不到页面状态时必须让它硬失败，不能让"没测到"长得像"测过了"**。
   - 原计划四步（09-26 记）：① 接补丁 → ② 起全量 → ③ 零回退闸门 + WF-16 → ④ 走设备补取缺包。**①②③ 已完成（上三条），④ 已否证（下条）**。

   - **④ 已否证（2026-09-27，设备侧也没有 ⇒ 这条路是死的）**：那 66 个缺号里 **59 个在设备上连 `cv-N-*` 前缀文件都没有**；
     7 个只有 `-battle/-gift` 变体（本地同样有），真正缺的主包 `cv-N.b` **两侧都不存在**。
     设备 `AssetBundles/cue` 4958 个 vs 本地 4726，设备独有 232 个只属于 `cv-970113` 一个号（+ 一批 bgm/宿舍音），
     **与 66 个缺号交集为 0**。⇒ 对应 234 张皮肤在现有资产下真的无解，只能等游戏下发或走 CDN（**未拍板，暂不做**）；
     画廊侧应显式标"无语音源"而不是静默留空。全过程与否证台账见 **§49**。
     顺带修掉一个承重 bug：`scripts/mumu_sync.py` 里 `subprocess.run(...)` 的 `encoding=` 关键字重复
     → **SyntaxError，该脚本自写下起从未成功运行过**（连 `--help` 都起不来）；
     已把 `py -3 -m compileall -q scripts gallery_src` 纳入收尾验证（此前没有任何环节编译过全部脚本）。
     另有 **265 张**是本地 azdata 快照查不到 `painting` 行（2b/a2 等联动），要靠设备侧更新后的皮肤表才能定位，与补包是两件事。
   - ~~已知缺口 499 = 234 + 265（快照滞后）~~ → **265 那条已作废**（§53）；现为 **354 = 224 缺包（两侧无源）+ 84 待裁定后缀 + 16 无 CV + 30 其它**；289 张只能同船回退取包号，其皮肤序号按"包内实存序号档 − 已被同船占用的"分配（`src=sibling-tier/-base`），分不到退回基础档。
   **顺带待裁定 → ✅ 2026-09-25 全部闭环**：`ALIAS` 已改读游戏自己的 `character_voice` 表（§35/§36），并**全量重导完成**：(皮肤,动作组) **2504→3263（+759 = 253×3）**、文件条目 5914→6948、**丢组 0 / 磁盘缺失 0 / <2KB 占位 0**（374.2 MB）；浏览器实播 `complete/mission/wedding/touch_body` 四组全部真出声（`paused=false`+`cur` 在走+`err=null`，§38）。新增到皮肤的语音类别：`complete`(→expedition)、`mission`(→task)、`wedding`(→propose)。
   **技能沉淀决议（勿再新建）**：自动推荐连发 4 条（`criware-acb-live2d-voice-extraction` / `criware-acb-voice-extraction` / `criware-acb-voice-bank-extraction` / `criware-voice-cue-extraction`）实为**同一份内容的四个副本**，相对 WF-17 净新增仅三点（库原生 `definitions[g][0].Sound` 注入、本库无音频驱动口型、语音表异步到达的首播竞态）。闸门过了之后**并进 `live2d-web-runtime-integration` 新开 §9「动作语音」**，与 WF-17/§23 重复的段落一律改为引用；若坚持独立技能，命名取 #3。⚠️ 该技能住在项目 `.agents/skills/`，而 `skill_manage` 只认用户技能目录 → **须直接改文件**。落笔时修掉两处事实：`-i` 不是"不给就时长翻倍"（本批语音实测无 loop 点），以及探针脚本要先入库才能被技能引用。
11. ✅ **已闭环**：摩尔曼斯克「皮肤2」脸上盖着不透明灰梯形（2026-09-26 用户报，2026-09-27 查清并换入 13 张）
   - **根因不是待办猜的 ②③**：face 槽矩形与灰块外接框重合、`_front` 层在脸区一个像素都没画（逐层单独落盘核对）。
     真因是待办假设 ① 的精确版——**判据演进留下的隐形漏检**：09-20 那轮扫的 2221 候选用旧判据（整框不透明率），
     `moermansike_2` 该值 1.000 → 判"已烤好"根本没进候选；同日收紧成"不透明**且** sat≥30"后
     **只重渲了旧清单里那 35 张，全库从未重扫**。
   - **灰块是源纹理本来就有**（导出 `painting/moermansike_2_tex` 按 face 槽框裁出来目视确认），
     游戏运行时靠 face 槽叠真脸 ⇒ 叠脸方向正确，不是遮丑。当前管线重渲该皮肤 → 脸正常。
   - **顺带查出更大的问题**：用 sat≥30 判据全库重扫，前 200 候选报 **98 个"脸洞"=49%**（旧判据全库仅 1.6%），
     抽样 24 张逐张目视**全部是底图已烤好完整脸** ⇒ §14 那次收紧把错误方向从"漏叠"换成"大面积过叠"，
     且从没在"旧清单外"人群上回归过。**判据已换**成两段式：
     `洞 = 脸谱落笔处不透明占比<0.5 或 MAD(底图 vs 脸谱逐像素色差)>30`；
     闸门 `scripts/diag/face_gate_labels_check.py` 在 47 个目视裁定样本上 **47/47 全对**
     （好脸侧 MAD 最大 12.3 / 真洞侧最小 62.6，阈值 30 落在空档），`leiniya_wjz` 仍不叠。全过程见 **§48**。
   - ✅ **已换入（2026-09-27）**：全库重扫 2221 候选 → **46 洞**（其中 **13 个是旧判据完全看不见的"不透明灰块"类**）；
     `painting_face_rerun.py` 逐张重渲与在盘比 md5 → **33 张逐字节相同（零回退硬证据）/ 13 张有差异**；
     13 张逐张目视全是"改前没脸、改后正常" → 备份 `Output/_OLD_bak/painting_facefix_20260927/` 后换入
     （逐文件 `st_nlink==1`、逐张校验 == 临时渲染、全目录快照证明只有这 13 个 mtime 变了）→
     只删这 13 张缩略图后 `make_thumbs.py` 增量重建（ok=16 err=0）。结果与逐张对比图见 **§48 末段**。
   - ✅ **陈旧普查已跑完（2026-09-27，4488 张 / 94 分钟 / 0 渲染失败）**：全库只有 **9 张**与当前管线不一致，
     且**没有一张是叠脸引起的**。用"历代脚本分别重渲、看在盘能被哪个提交逐字节复现"定因：
     **7 张漏掉了 09-19 的 mesh 越框修复、2 张（`moli_g`/`moli_g_n`）漏掉了 09-18 的嵌套容器修复**
     ⇒ 当年那两批定向换入（85 张 / 55 张）各自漏了 7 张和 2 张；`z43` 是 09-20 叠过脸、新判据不再叠（两版近乎相同）。
     全过程与否证见 **§52**；`anninvwang`/`dengken` 的最大色差只有 5~6/255（重采样舍入级，肉眼不可见）。
     ✅ **已全数换入（2026-09-27 用户拍板"全换"）**：走新工具 `scripts/diag/painting_swap_in.py`，
     四道硬检查全绿（nlink=1 / 备份 md5 全等 / 换入后与渲染一致 / 全目录快照清单外 0 个），
     备份 `Output/_OLD_bak/painting_stalefix_20260927/`，缩略图增量重建 ok=9 err=0。
     **复测 9/9 与当前管线逐字节相同 ⇒ 全库 4488 张"盘上 == 当前管线"不变式已恢复**，
     这条普查从此可当每次系统性修复的回归闸门。
   - ✅ **另三条管线查过、都干净**：Spine_v2 抽 9 个包（跨 09-15 与 09-20 两批）重抽后**逐文件哈希全一致**；
     CG_v2 产物 09-26 21:39 晚于 `cg_export.html` 最后提交 21:29；Live2D 的 `extract_motions.py`
     在 09-24 全量重导之后的那次提交（`4ec3274`）**只加了 CLI 安全闸与进度 flush、没动曲线逻辑**。
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
     **不动**已验收的 `skin_voice.json`；钥匙 `皮肤行id = cv*10+idx`，别名全查 `character_voice` 不猜）、
     `build_gallery_index.py` 语音口径换权威源（`voiceCount` 268→860 组船）、`scripts/diag/gallery_index_diff_check.py`
     （索引零回退闸门）、`scripts/diag/talk_verify.py`（实播验收）。数据链与判据见 **WF-22**，根因与踩坑见 **§54**。
     - ✅ 覆盖面：**4129/4140** 皮肤配上正文、**73,705** 条（语音表 12.4 万条槽位里约 61% 游戏本来没写词）。
     - ✅ 验收全绿：三格各点一次 + **直接点立绘** + 开关矩阵两条反向证据 + 阴性对照（摸头有声无词⇒不弹空框）
       + 语音页逐行比对（含"每行 `<audio>` 可见高度"，光数行放过了一次 `flex:1` 把播放器压成 0 高）
       + 无语音皮肤显式 🔇 + 持久化（用非常规组合验）。
     - ✅ **全屏没字幕已修**：三格「全屏」按钮 `requestFullscreen()` 的是 `#mView`，字幕原先挂在 `.content` 上
       ⇒ 全屏时不在被渲染的那棵子树里。现挂进 `#mView`；并用 CDP **可信鼠标事件**真进一次全屏量到
       `fullscreenElement=mView` + 字幕 282×62 可见（直接 evaluate 调 `requestFullscreen` 会被权限拒，不算测过）。
     - ✅ **已换入（2026-09-27 19:05 用户放行）**：备份 `Output/_OLD_bak/gallery_index_pre_talk_20260927/index.{json,js}`
       （sha256 `e79ed546bb41` / `58b78bf27249`）→ 覆盖 `Output/gallery_v2/index.{json,js}`（943,728B / 857,039B，
       与构建产物逐字节相同）。换入后复验：`congmang_2_hei` 语音标签从置灰变可用，语音页 **32 行 / 16 条正文**逐行对齐、
       每行播放器可见；`lafei`（主包缺失、只有变体包）走「其它已导出语音」分支 1 行可播 ⇒ 换口径没把旧导出弄丢；
       `kelei` 语音 0（旧口径把可畏的包派给它，属修正）。全套 `talk_verify` 12 条判据全绿。
     - 提交 `52e2797`/`92bef91` 由并行会话**接管快照入库**（当时本会话仍在写 `talk_verify.py`），文档债已在本次补齐。
14. ⏳ **天津风皮肤2（`tianjinfeng_2`）Spine 动态缺部件 + CG 导出渲成 45° 菱形**（2026-09-27 用户报，**根因未定**）：
     弹窗里躯干、下肢、大狐尾整块不显示，只剩椅子+两条腿+头+一只袖子；同一套运行时的
     `CG_v2/tianjinfeng_2.png` 渲成了 45° 菱形（房间占满、角色缩成中间一小点）。
     **两条已否证**：① 不是换肤问题——5 个 part（本体/`2B`/`2B2`/`2M`/`2T`）都只有 `default` skin，
     `spine_skin_scan.py --only tianjinfeng_2` 报 `gain=0 / parts_affected=0`，§42 那条 `setSkin` 修法在这里不成立；
     ② 不是缺贴图——每个 part 的 atlas 页与同名 png 一一对应，viewer 也报「5 层部件」零失败。
     下一步起点：按 part 逐个单独渲染（CG 导出页加 `?only=`/`?part=`）看**哪一层没落笔**，
     再判是"该层的附件没挂上"还是"多层合成时各层坐标系不一致"。⚠️ 别和 §45/§46 那两类取景问题混——
     那两类是"框撑太大画面缩中间"，这里是"内容整块缺失 + 形状被转 45°"。
15. ⏳ **4 张「整张画的每一层都是关闭态」的皮肤**（2026-09-27 §55 顺带查出）：
     `qiye_4` / `kelifulan_4`（各只有一层且它是关的）、`qiye_dark_memory` / `unknown2_memory`
     （`frame_0..3` 四层全关，游戏按剧情逐层激活）。过滤会把它们**清空**，所以规则是"一层不剩就原样保留"
     并记进 `C.INACTIVE_ALL`。要修得先知道游戏在哪一刻激活哪一层，**没有权威依据不许猜**。
     取证：`py -3 scripts/diag/painting_inactive_scan.py`（只读全库扫）+ `painting_inactive_rerun.py`（定向重渲+对照表）。

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
要点：静态立绘 / Spine 已由 v2 全量收官，Live2D 动作层已于 2026-09-21 按权威映射重建完毕，**2026-09-23 网页交互层三个根因（命中包含判定 / idle 循环 / V-P 坐标系）已修并回归**。接手前先读 §9 理解「游戏数据自洽、不要猜坐标/不要按位置猜参数名」这一核心结论。**验动效一律看内容**（曲线条数、Id 是否命中参数表、值是否随时间变化），不要只看 `currentGroup`/组名标签——空壳也能"启动"，这个坑已踩过一次（`docs/TROUBLESHOOTING.md` §17、`docs/WORKFLOWS.md` WF-7）。**验交互一律用独立锚点**——合成点击若与被测映射同源会自洽闭环、全绿也说明不了对齐（§20、WF-16）。历史 v1 调试见 `docs/archive/`，一般无需再读。

---

## 8. 技术备忘

**立绘命名**：`{舰名}`默认皮 / `_2`第2套 / `_tex`纹理 / `_n`夜战 / `_hx`换色 / `_rw`人物 / `_bj`背景 / `_front`前景 / `_jz`舰装 / `_alter`改造 / `_hei`黑化。多数脸烤进 `_rw`（仅 ~4% 有独立 face 部件）。
> **⚠️ 语义纠正（用户 2026-09-20 实测确认，别再按字面理解）**：**`_hx`「换色」实为和谐版**（内容被和谐处理后的立绘，不是调色变体）；**`_n`「夜战」实为不显示背景的立绘**（同一皮肤的无背景版，不是夜间场景）。二者都不是"另一套皮肤"。
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
- **源码治理**：画廊前端源码在**仓库内 `gallery_src/`**（唯一权威版本），`Output/gallery_v2/` 是运行目录（gitignore）。**2026-09-26 起两边改成硬链接**（同一份磁盘数据两个路径名），**4/4 已全部换链**（`index.html` / `cg_export.html` / `_gallery_server.py` / `启动资产浏览器.bat`）：改正本即刻生效、不需再部署。`deploy_gallery.py` 三态——默认 copy 修复（断链后的回退手段）/ `--check` **要求 4 个文件全部同 inode，断链或漂移都 `exit 1`** / `--relink` 换链（要求两边逐字节相同，且正本有未提交改动者自动跳过，防打断并行会话）。⚠️ 断链的唯一现实成因是整文件写回式「写临时文件+改名」的原子保存：**16:52 真断过一次，而当时只比内容的 `--check` 给了 `exit 0`（判据漏洞，已改为结构性并写进 AGENTS.md 收尾清单第 1 条——改 `gallery_src/` 正本一律原地编辑）**。当前 `index.html` 因那条未提交改动处于"已断链、内容仍一致"态，待其提交后 `--relink` 补。见 §43 与 WF-16。CG 导出页 `cg_export.html` 同样入 `gallery_src/`；服务器 `_gallery_server.py` 提供 `POST /save_cg` 落盘接口，`--export` 参数直开导出页。⚠️ 服务器按自身所在目录算根，**只能双击 `Output\gallery_v2\` 里那份 bat**。
- **运行**：`启动资产浏览器.bat`（→ `_gallery_server.py`：8777 端口 + `allow_reuse_address` + 端口占用即复用 + 结尾 `pause`，杜绝闪退）。file:// 下立绘/语音可看，Spine `fetch` 被 CORS 拦需走 .bat。
- **运行时库台账**（2026-09-26）：`vendor/` 4 个第三方 JS 只在 gitignore 目录里，版本/来源/sha256 记进 **`gallery_src/vendor/MANIFEST.json`**（3 个的 URL 当日重新下载按哈希逐字节对拍命中），换机器跑 `py -3 scripts/fetch_gallery_vendor.py` 补齐（**哈希+字节数双对上才落盘**，`--check` 只校验）。⚠️ **唯一残留缺口**：`vendor/spine/spine-all.js`（实测 3.8.75，非旧文档写的 3.8.99）没有可按哈希校验的下载源——本机这份与上游官方 3.8 构建不同（499623B ≠ 501448B），只能从 `tools/spine-viewer/spine-runtime/` 取，而 `tools/` 也在 gitignore。要彻底封掉需二选一：把 501KB 提交进仓库（先确认 Spine Runtimes License 允许），或改用可哈希校验的上游构建并回归 Spine 播放。**未拍板**。
- **限制**：~~Live2D 暂只显示贴图~~ **已接动作播放**（2026-09-20，`vendor/live2d/` 三脚本本地就位，见 §6.7）；Live2D/Spine 标签均需走本地服务器（file:// 下 fetch 被 CORS 拦）。运行时库的可复现性与那条未拍板的残留缺口见上一条。

---

> **历史归档**：v1 时代攻关路线、多部件合成已知问题清单（Bug#1-#4）、7-30/7-31 修复记录、bj 背景层专项、调参工具 v3-v6 会话流水、旧 Spine Viewer 调试史 → 全部见 `docs/archive/PROJECT_STATUS_历史归档.md`。
