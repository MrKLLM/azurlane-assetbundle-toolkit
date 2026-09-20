# 碧蓝航线 AssetBundles 解包项目 — 进度总结

> **生成时间**: 2026-09-20（**§6 交接点 B 完成**：`build_gallery_index.py` 元数据主源改 `ship_meta.json`（舰名/阵营/舰种/稀有度），旧 `SHIP_NAME_MAP`+Wiki 降级兜底。**根因修复**——`build_ship_meta.py` 舰名取错表(skin_template 皮肤名→改 statistics.name)，**237 个 ship 级 `{namecode}` 占位符归零(同时关闭既有待办#8)**；META/灰烬 56 形态 `_alter` 从本体船拆为**独立卡**(faction=META)。逐船四字段零回退：ships 954→1008 / with_cn 796→899 / 阵营 445→837 / category 已落(ship 816·story 192)。index 已换入正式，skin 层未动故 **thumbs 无需重建**。**交接点更新 = ~~D~~ 已关闭（2026-09-20 Live2D 动作播放接入完成，见 §6.7；当前唯一在途 = §6.9 脸洞重渲换入）**。**C 已完成（2026-09-20）**：`gallery_src/index.html` 顶部加「类别」分段控件（全部/舰船 816/剧情角色 192，带总数），主网格按 `category` 分区渲染（舰船段+剧情角色段各带小标题计数），与阵营/舰种/稀有度/内容/搜索/排序正交共存；无头 Chrome dump-dom + 截图校验分区与计数正确、缩略图全 200、META 独立卡呈现正常，已 `deploy_gallery.py` 同步。晶环联盟取 C 搁置标「其他」。前项：385 变更美术定向重建完成）
> **上一里程碑** 2026-09-20（385 变更美术定向重建）：换入 11 单位（立绘2/Spine3/Live2D4/表情2，全新增零覆盖，对照逐字节零回退）；根因修复=dependency_manifest 重生成(86449条)+两脚本补 UnityPy fallback；index/thumbs 已增量。遗留：3 个新 Spine 未做 CG_v2 全屏导出。
> **上上里程碑** 2026-09-19：§6 第5~6条 A 收尾完成，`Output/ship_meta.json` 已产出，Live2D 运行时已备妥。
> **用途**: 跨会话对接。**v1 时代历史已外迁 `docs/archive/PROJECT_STATUS_历史归档.md`**，本文只保留当前状态与主线。当前待办见 §6。
>
> **【2026-09-20 交接状态】唯一在途线索 = I-168 脸部白块的「重渲换入」**：`compose_paintings_v2.py` 叠脸修复已实现并双样本验证；**全量扫描已完成**（2221 候选 → **35 个脸洞皮肤**，清单 `.diag/face_holes.txt`，err=0，日志 `.diag/scan_faces.log`）。**下一步（需用户过目后才动正式产物）**：只对这 35 个重渲到临时目录 → 出改前后对比图交用户确认 → 备份换入 → 增量重建受影响缩略图（详 §6.9）。
> 本轮已完成并提交：① **story_review 勾选落地**——用户勾定自机 31 条进 `build_gallery_index.EXTRA_SHIP` 白名单且白名单优先于塞壬前缀分支（不再被清空属性），ship 850→881 / story 158→127，逐船 diff 非类别字段回退 0；② **交接点 D 关闭**——画廊 Live2D 动作播放接入 + 无头 CDP 抽样验证（§6.7）。

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

### 2.5 Live2D 模型还原 ⚠️ 大部分完成
256/256 还原、纹理拼接正确、HitAreas 已修复；有真实动画 244/256，全部成功 26/256，B 类 12 个动画完全失败（资产无缺口，属 motion 质量，见 §9.5）。输出 `Output/Live2D/{舰名}/`，~3.4GB。脚本 `reconstruct_live2d.py` / `fix_model3.py` / `extract_motions.py`。
已知限制：StreamedClip 未完全逆向；HitAreas 用 moc3 Touch ID，非真实交互区。

### 2.6 Spine 动态立绘 ✅（v2 提取 + 全屏 CG 导出 + viewer 修复，2026-09-19）
`scripts/extract_spine_v2.py` 双结构兼容提取到 `Output/Spine_v2/`，232 主包。gallery 内 `spine-all.js`(3.8) 分层实时播放。**2026-09-19 三修复**：①相机视口（`SceneRenderer.resize()` 不更新 viewport → 比例怪）②`my` 变量遮蔽 TDZ（假「N 层失败」+ 取消失效）③过滤 0 秒空占位动画、默认播 `normal`、缺动画层回落 normal；另支持 JSON 骨架（beierfasite_g）。**全屏 CG 导出**：`cg_export.html` 渲染 setup pose 批量落盘 `Output/CG_v2/` **231/231 成功**（含二次像素包围盒构图修正）。

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

（v1 旧产物与调试目录已归档/清理；`.trash` 内旧 bug 产物已于 2026-09-16 彻底删除，释放 8.9GB。**2026-09-20 清理**：`.diag` 内 17 个 headless Chrome profile 缓存 + 历次立绘修复的一次性调试输出目录 + 本次 B 会话临时文件、`Output/_OLD_bak`(三次修复换入前备份 918MB)、`Output/` 下 bj_*/layout_2b/run_v2_full.*.log 零散件，共 **126 项送回收站、释放 7.3GB**；errors 流水并入 `docs/ERRORS.log`。保留 azdata 权威缓存/`dependency_manifest_385.json`/`run_cg_export.py`。重复资产(Paintings_v2 50 个逐字节重复 252MB 等)因被画廊按文件名引用，本轮未动。**2026-09-20 硬链接去重**：Paintings_v2/Paintingface/CG_v2 内 519 组逐字节相同文件（`npcX`==`X`、部分`_asmr`/`_hx`==本体、`left/mid/rightchicheng_alter` 三视图同图等），531 个重复文件转 NTFS 硬链（`os.link`，失败回退 copy），物理实省 **~358MB**；路径与内容不变，逐文件 nlink+sha256 校验 + 起 http.server 对全部 531 路径 GET 200/长度/哈希三重核对全通过，画廊引用零破坏。）

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

**核心脚本**：`scan_assets.py`、`export_assets.py`、`export_cue_audio.py`、`reconstruct_live2d.py`/`fix_model3.py`/`extract_motions.py`、`compose_paintings_v2.py`(★v2)、`extract_spine_v2.py`(★v2)、`export_dependency_manifest.py`、`build_gallery_index.py`、`make_thumbs.py`、`deploy_gallery.py`(gallery_src→Output)、`mumu_sync.py`、`ship_name_map.py`、`scrape_wiki_fast.py`。

**文档**（导航见根目录 `README.md`，写入路由见 `AGENTS.md`）：
- `docs/DEV_LOG.md` 操作手册 · `docs/WORKFLOWS.md` 可复用工作流 · `docs/TROUBLESHOOTING.md` 踩坑 · `docs/ERRORS.log` 错误流水
- `docs/tools/` ALPA、AssetStudio 使用说明
- `docs/archive/` 历史归档（含 `PROJECT_STATUS_历史归档.md`、旧目录审计报告、旧 Spine 交接）

**数据**：`asset_manifest.json`、`Output/dependency_manifest.json`(86,398 条官方依赖表)、`Output/WikiData/ship_data.json`、`Output/gallery_v2/index.json`。

---

## 6. 接下来的任务

### ★ 2026-09-16~19 gallery_v2 质量复核（1~4 已闭环，5~7 为交接待办）

1. ✅ **静态立绘「嵌套容器错位」（2026-09-18）**：`layout_all` 仿射多减 `p_local[0]`，修 `52782a7`，85 张换入（备份 `Output/_OLD_bak/affected_20260918/`）。
2. ✅ **i404 型「背景缝隙」（2026-09-19）**：无 mesh 部件误用 `mRawSpriteSize` 当画框，改 textureRect 拉伸铺满 RectTransform，10 张换入（备份 `framefix_20260919/`）。painting 本身即半景特写，完整 CG 走 Spine 线（第 4 条）。
3. ✅ **mesh 越框裁头（2026-09-19，用户报「库尔斯克缺块」）**：`rasterize_mesh` 把内容钳在画框内，而 mesh 顶点可合法越框（kuersike_rw 头部伸出框顶 713px）→ 改按内容 AABB 输出（安全钳 ±2~3 倍框）。扫描 4490 包：84 皮肤越框、**55 张画面实际变化已换入**（29 张越框部分全透明逐像素同旧图；5 张画布按预期变大找回内容）；对照 5 皮肤 maxdiff=0。备份 `Output/_OLD_bak/meshfix_20260919/`，清单 `.diag/mesh_overflow.txt`，对比图 `.diag/cmp_meshfix/`。
4. ✅ **Spine 动态 + 全屏 CG 导出（2026-09-19）**：viewer 三修（相机视口 `camera.setViewport`、`my` 变量遮蔽 TDZ、0 秒空动画过滤+默认 normal）+ JSON 骨架支持；`cg_export.html` 两段式构图批量导出 **231/231** → `Output/CG_v2/`，画廊默认展示 CG 可切原件，缩略图 `<key>_cg.webp`。详见 WORKFLOWS WF-14。
5. 🟡 **元数据重建（A 收尾已完成：`Output/ship_meta.json` 已产出，交接点=B）**：
   - **脚本**：`scripts/build_ship_meta.py`（默认 `--diag` 只读，`--write` 产 `Output/ship_meta.json`）。运行：`PYTHONIOENCODING=utf-8 python scripts/build_ship_meta.py --write`。产物键=画廊 bundleID（Paintings_v2/Spine_v2/Live2D/CG_v2 目录名并集，共 4492），值=`{cn,en,faction,type,rarity,voice_actor,category,base_painting,source[,数值码]}`。
   - **桥接路径（⚠️已实测校正，覆盖 §6 旧假设）**：磁盘 stem —剥变体后缀(`_n/_hx/…/罗马数字紧跟`)→ 基 `painting` → `skin[painting].ship_group` →（`stats.skin_id` 命中皮肤的组，实测 4118/4119）→ 舰级 `nationality/rarity/type/english_name`。**旧记录里“用 `ship_group` 直接反查 stats”不成立**（1270 个 ship_group 仅 268 落在 stats 键）；**变体皮肤须经 `ship_group` 归并到舰**，不能靠自身 skin.id。
   - **成品实测**：source 分档 painting 2493 + suffix 1786 + fallback(ship_name_map) 136 + manual 2 = **4417 有中文 cn（98.3%）**；残 **75 unresolved** 全为剧情/NPC/测试（aijiang*、linghangyuan*、lingyangzhe*、npc*、error13、magician、2b/a2 联动变体）→ 归第 6 条 story。分类 **ship 4065 / story 427**。阵营分布 重樱824/白鹰729/皇家622/铁血492…，空阵营 0。
   - **数值码→中文标签表已写进脚本常量**（NATIONALITY/RARITY/TYPE，对齐游戏内筛选词表）：nationality 1白鹰 2皇家 3重樱 4铁血 5东煌 6撒丁帝国 7北方联合 8自由鸢尾 9维希教廷 11郁金王国 96飓风 97META 98其他(布里) 102~115各联动；rarity 2普通 3稀有 4精锐 5超稀有 6海上传奇 18超稀有；type 1驱逐…24风帆。游戏筛选里的「晶环联盟」本快照(9.7.381)无对应码 → 前端归「其他」。
   - **✅ 两个决策已定**：① `voice_actor` = **只存数字 id**（CV 姓名表未缓存，以后再补映射）；② 非核心码(98/111~115) = **经验名 + 兜底原样保留**，不逐个核。
   - **✅ B 已完成（2026-09-20）**：`build_gallery_index.py` 元数据主源切 `ship_meta.json`，舰名/阵营/舰种/稀有度取 ship_meta（未解析条目回落 `SHIP_NAME_MAP`+Wiki，如 `kelei`→可畏/皇家保住了），`category` 已落 index.json。**根因**：`build_ship_meta.py` 舰名原取 `ship_skin_template.name`（皮肤名，含 433 个 `{namecode}` 占位符 + 皮肤主题标题），改取 `ship_data_statistics.name`（实测 0 占位符），237 舰级占位符归零（`weizhang`→尾张、`linggu`→铃谷、`xinzexi`→新泽西、`antu`→安土，名称与阵营一致）；`META/灰烬`（`_alter` 形态）经 `normalize` 守卫拆为 56 独立卡。逐船四字段零回退。⏭️ **下一步 = C**：前端按 `category` 分「舰船/剧情角色」+ 筛选器；D Live2D 动作播放。
6. ✅ **剧情角色与舰船分级（已随 B/C 落地并经用户复核精修，2026-09-20）**：`category` 进 index.json，前端「类别」分段控件 + 网格分区。**分类精修**（`build_gallery_index.reclassify` 后处理，因单一字段不可靠）：塞壬/BOSS/NPC（名字含 `？` 或 id 前缀 unknown/sairen/npc/linghangyuan/…）→ 剧情且**清空阵营/舰种/稀有度**（修 `unknown1` 假俾斯麦误判舰船）；有阵营 / 命中维基名单 / 皮肤带 `_doa/_tolove/_idol` 联动偶像标记 / 白名单 → 舰船（把 U艇/Z驱/I潜/Hololive/SSSS/DOA/海王星/可畏/加斯科涅 等误判剧情船捞回）。精修后 **ship 850 / story 158**（→ 2026-09-20 用户勾选 31 条自机后 **ship 881 / story 127**，见 §6.9 末条）。`build_ship_meta` 加 `NAME_FIX`（贾斯科涅→加斯科涅 官方译名）。⏭️ 新发现遗留：**I-168 皮肤2 脸部白块**（paintingface 独立部件未叠，见 §6.9）。
7. ✅ **Live2D 动作播放接入（2026-09-20 完成，交接点 D 关闭）**：`gallery_src/index.html` 的 `renderLive2D` 由「只显示贴图」改为真实播放——懒加载 `vendor/live2d/` 三脚本（cubismcore 5.1.0 + pixi 6.5.2 + pixi-live2d-display 0.4.0）→ `PIXI.Application` + `Live2DModel.from(model3.json)` → 动作下拉（全组）+ 重播/复位/全屏 + 滚轮缩放(光标锚点)/拖拽平移/双击复位，默认播 `idle`、点击模型触发 `tap*`。`renderView`/`closeShip` 均加 `stopLive2D()` 销毁并解绑监听。**无头 Chrome+CDP 抽样验证**（`.diag/l2d_verify.py`、`.diag/l2d_click.py`，截图 `.diag/l2d_shots/`）：6 模型（lafeiii_3 50组/adaerbote_3 40/aersasi_2 34/abeikelongbi_3 20/ninghai_4/pinghai_4）加载与切动作全通过；真实点击路径 3 例断言标签高亮与「显示尺寸≤容器」；缺目录降级不崩、来回切换 `destroyed+reloaded` 正常。踩坑（vendor 路径误用 `P`、`fit()` 用含 scale 的 `mdl.width` 致正反馈放大、监听器泄漏、headless rAF 节流需手动 `app.render()` 才能测出动画）见 `docs/TROUBLESHOOTING.md` §13。磁盘 260 模型全部有 `idle` 与有效 motion（§2.5「B 类 12 个」是动作质量非缺文件），未做特判。
8. ⏸️ **missd（D小姐）「黑影」——用户暂搁置**。
9. ⚠️ **I-168 皮肤2 脸部白块（2026-09-20 用户报告，根因已定位，修复待实现）**：
   - **现象**：`Output/Paintings_v2/i168_2.png` 脸上是不透明白色矩形；默认 `i168.png` 正常（脸烤进 `_rw`）。
   - **根因链（已探包证实）**：painting 包里有个 GameObject 名为 `face` 的节点，但其 `MonoBehaviour.m_Sprite` 是**空的（path=0/file=0）**；`compose_paintings_v2.parse_painting` 第 268 行 `if not path_id: continue` 把它跳过了。真脸在**独立的 `paintingface/<name>` 包**（i168 有 5 张表情 `1`~`5`、i168_2 有 7 张 `0`~`6`，均 ~115×108 / 169×218），游戏运行时把它贴到 face 槽。凡 `_rw` 把脸留成白洞的皮肤（如 i168_2）合成后就缺脸→白块；`_rw` 已烤脸的（i168）不受影响。`paintingface/` 共 **2246 包**，受影响子集待扫描。
   - **✅ 修复已实现（2026-09-20，`compose_paintings_v2.py`）**：`parse` 后取 face 节点 rect（`go_names[pid]=='face'`）；`render()` 画完部件后，**仅当 face rect 区域是透明洞（`frac_op<0.5`）才**从 `paintingface/<name>` 取默认脸（`FACE_DEFAULT=1`，可 env 覆盖）按 rect 叠上。已加 `compose(save=False)` + `FACE_APPLIED` 全局供扫描判定。**样本双验证**：`i168`（已烤脸）判假不叠→对照 **maxdiff=0 零回退**；`i168_2`（脸洞）判真→脸正确填上（位置/表情对）。⚠️ 洞是**透明(alpha0)**不是白，早期按「不透明白」判据全错，改 frac_op 才对。
   - **✅ 全量扫描已完成（2026-09-20）**：`py -3 .diag/scan_faces.py`（env `FACE_DEFAULT=1`）扫完 **2221 候选 → 35 个脸洞皮肤**，err=0，用时 1954s；清单 `.diag/face_holes.txt`（含 `i168_2`、`beiqi`、`daleike`、`dunkeerke(_3)`、`huangjiafangzhou_alter`、`luodeni_alter`、`shuixingjinian_alter`、`yilishabai_alter`、`xipeier_idol(_ns)`、`daqinghuayu_idol`、`leiniya_wjz`、`z43` 等），日志 `.diag/scan_faces.log`。**注意 `missd` 也在洞清单内**（与 §6.8 用户暂搁置的「黑影」是同一皮肤，换入前需确认是否一并处理）。
   - **⏳ 待办（换入前必须用户过目，safe-pipeline 硬闸门）**：只对 35 个洞重渲到临时目录 → 出改前后对比图交用户确认 → 备份换入 `Output/Paintings_v2/` → 增量重建受影响缩略图（`make_thumbs.py`）。
   - **✅ 勾选已落地（2026-09-20）**：`story_review.md` 用户勾定 **31 条自机**（拉菲III/I 系潜艇 6 艘/伊织 hdn101·102/兰利III/绊爱系 5 条/Hololive 7 条/2b·a2/探索者/领航员3/羚羊者3/匆忙/苏维埃同盟new）→ 全部进 `build_gallery_index.EXTRA_SHIP`，并把白名单判定**提到塞壬前缀分支之前**（否则会被清空阵营/舰种/稀有度）。重建后 ship 850→**881** / story 158→**127**，逐船 diff 非类别字段回退 **0**（`congmang` 反而恢复出 皇家/驱逐/精锐）。用户备注：`npc*` 前缀者暂不确定，本轮未动。

> 诊断产物/缓存均在 `.diag/`（不入库，本机可继续用）。画廊前端改动走 `gallery_src/` → `scripts/deploy_gallery.py`。

### 既有待办

**优先级低**
5. UI/图标批量导出（~2 万）、3D 宿舍资源、资源分类整理 `organize.py`。
6. **声优中文姓名补全**：`ship_meta.json` 的 `voice_actor` 现为数字 id（皮肤表只给 id，CV 姓名表未缓存）。以后需要显示声优名时，从 azurlane-data 或游戏配置补一张 `voice_actor_id → 中文声优` 表回填（§6 第 5 条决策①）。
7. ⚠️ **阵营「晶环联盟」码待定——原方案前提已证伪，挂起待决策（2026-09-20）**：
   - ~~待资产同步后从游戏配置解析~~ → **同步已完成**（9.7.385，95 文件，2026-09-20，mumu_sync diff 归零）；但今日实测游戏 `sharecfgdata/*` 配置包为**自定义加密**（非 UnityFS，非常量 XOR，UnityPy 解析出 0 对象），本机无解法；azurlane-data 社区快照最新提交仍 **9.7.381**（无 385、无阵营名表）。→ **目前不存在任何可直读的 385 解密配置源**。
   - **挂起三选一待用户定**：**A** 逆向 sharecfgdata 加密（需从游戏二进制挖密钥，成本不确定）｜**B** 以 381 为基础走旁路（维基/其它社区数据/从美术包推断，省力但不完整）｜**C** 搁置（晶环联盟与新皮肤 `mile_3`/`aierdeliqi_9` 的归属均标「待补」，381 能解析的照常用）。
   - 现状维持：ship_meta 前端仍归「其他」。同理受影响：385 新皮肤在 381 快照无记录，归属也卡在同一决策上。
   - 不受影响、可独立推进：§6 交接点 B→C→D 主线；以及「385 变更美术的定向重建」（立绘/Spine/Live2D 包本身是明文 UnityFS，已同步在手）。**（2026-09-20 已完成，见头部）**
8. ✅ **ship_meta `{namecode:XX}` 占位符名（已于 2026-09-20 随 B 根因修复关闭）**：根因=`build_ship_meta.py` 舰名取 `ship_skin_template.name`（皮肤名，含占位符）——**改取 `ship_data_statistics.name`（0 占位符）**后，237 个 ship 级占位符全归零、名称与阵营自洽（`weizhang`→尾张、`xinzexi`→新泽西 等）。残余 ~52 占位符全为 `story` 类（NPC/剧情/2b 联动变体，本就无 stats 舰名，非缺漏）。详见 §6 第 5 条 B 已完成。

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
要点：静态立绘 / Spine 已由 v2 全量收官；接手前先读 §9 理解「游戏数据自洽、不要猜坐标」这一核心结论。历史 v1 调试见 `docs/archive/`，一般无需再读。

---

## 8. 技术备忘

**立绘命名**：`{舰名}`默认皮 / `_2`第2套 / `_tex`纹理 / `_n`夜战 / `_hx`换色 / `_rw`人物 / `_bj`背景 / `_front`前景 / `_jz`舰装 / `_alter`改造 / `_hei`黑化。多数脸烤进 `_rw`（仅 ~4% 有独立 face 部件）。

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

### 9.3 六个系统性根因修复 ★教训（全部代码级、零逐角色参数）
1. 无 mesh 整图部件**双重 Y 翻转** → root 背景层颠倒。修：`arr = A[rect.y : rect.y+h]`。
2. Spine atlas 页纹理需 **`flip=True`**（运行时按行0=顶采样）。
3. Windows 分离进程 stdout 默认 GBK，`print('✓')` 抛错致全量**假失败** → `sys.stdout.reconfigure('utf-8')` + 子进程 `PYTHONIOENCODING=utf-8`。
4. `layout_all` **root scale 只乘子层未乘 root 自身** → 层间比例错。修：局部空间纯 anchor 数学 + 仿射映射世界 + 自身 scale 绕 pivot（负=镜像）+ root 屏幕适配 scale 归一为 1。
5. 无 mesh 部件**误用 `mRawSpriteSize` 当画框** → i404 型视差背景带（记录切分前原图尺寸）被压窄留黑洞。修：按 UI Image 语义 textureRect 拉伸铺满 RectTransform；mesh 部件才用 frame。
6. `rasterize_mesh` **把内容钳死在画框内** → mesh 顶点合法越框的皮肤（kuersike_rw 头部伸出框顶 713px）被裁头、纹理矩形露缝。修：按内容实际 AABB 输出（±2~3 倍框安全钳），越框部分由 render() 仿射照常映射。
> 结论再次印证：游戏数据自洽，所有错位都是解析姿势不对。（完整明细含文件行号与验证样本，见 `docs/archive/PROJECT_STATUS_历史归档.md` 末尾「完整明细存档」。）

### 9.4 Spine v2（`scripts/extract_spine_v2.py`）✅
双结构兼容（内联型 + 分离 `_res` 型）+ 外部页纹理按 deps 补齐 → `Output/Spine_v2/`。全量 **232 主包**完成。skel 3.8.99，皮肤为多部件骨骼（B/M/T）需分层合成。

### 9.5 Live2D 核查 ✅
266 个 live2d 包本地零缺失、自包含；旧提取无资产缺口，剩余仅 motion 质量（§2.5 B 类 12 模型）。

---

## 10. 本地资产浏览平台 `Output/gallery_v2` ✅（2026-09-15）

- **形态**：本地网页（源 28GB / Paintings 15GB，上线不现实），参照 l2d.su，中文名展示 静态立绘 + Spine + Live2D + 语音。
- **数据**：`build_gallery_index.py`（合并四类 + `ship_name_map` 拼音→中文 812 条 → `index.json/js`；Spine 皮肤附 `cg` 字段指向 `CG_v2/`）+ `make_thumbs.py`（Paintings_v2 + CG_v2 → 380px WebP，CG 缩略图 `<stem>_cg.webp`）。结果 954 船 / 4489 皮肤 / spine 231 / CG 231 / live2d 256 / 语音 268。
- **前端** `index.html`：网格懒加载 + 搜索/阵营/舰种/稀有度筛选 + **类别分段（全部/舰船/剧情角色，主网格按 `category` 分区渲染各带小标题计数）**；详情四标签。「静态立绘」对 Spine 皮肤默认展示全屏 CG（可切换回 painting 原件），支持**滚轮缩放(光标锚点)/拖拽平移/双击100%/全屏浏览/复位**；Spine 标签 `vendor/spine/spine-all.js`(3.8) 分层 WebGL 播放（相机视口/动画过滤已修，**支持全屏**）。服务器统一响应 `Cache-Control: no-cache`，改版后浏览器不再吃旧缓存。
- **源码治理**：画廊前端源码在**仓库内 `gallery_src/`**（唯一权威版本），改完跑 `scripts/deploy_gallery.py` 同步到 `Output/gallery_v2/`（运行目录，gitignore）。CG 导出页 `cg_export.html` 同样入 `gallery_src/`；服务器 `_gallery_server.py` 提供 `POST /save_cg` 落盘接口，`--export` 参数直开导出页。
- **运行**：`启动资产浏览器.bat`（→ `_gallery_server.py`：8777 端口 + `allow_reuse_address` + 端口占用即复用 + 结尾 `pause`，杜绝闪退）。file:// 下立绘/语音可看，Spine `fetch` 被 CORS 拦需走 .bat。
- **限制**：~~Live2D 暂只显示贴图~~ **已接动作播放**（2026-09-20，`vendor/live2d/` 三脚本本地就位，见 §6.7）；Live2D/Spine 标签均需走本地服务器（file:// 下 fetch 被 CORS 拦）。

---

> **历史归档**：v1 时代攻关路线、多部件合成已知问题清单（Bug#1-#4）、7-30/7-31 修复记录、bj 背景层专项、调参工具 v3-v6 会话流水、旧 Spine Viewer 调试史 → 全部见 `docs/archive/PROJECT_STATUS_历史归档.md`。
