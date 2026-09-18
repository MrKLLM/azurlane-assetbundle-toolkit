# 碧蓝航线 AssetBundles 解包项目 — 进度总结

> **生成时间**: 2026-09-18（v2 全量收官；修复嵌套容器错位 bug、换入 85 张受影响立绘；gallery_v2 上线）
> **用途**: 跨会话对接。**v1 时代历史已外迁 `docs/archive/PROJECT_STATUS_历史归档.md`**，本文只保留当前状态与主线。当前待办见 §6。

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

### 2.6 Spine 动态立绘 ⚠️（v2 提取完成，viewer 动画/层序待修，见 §6）
v1 的 WebGL Viewer 调试史已归档。当前 `scripts/extract_spine_v2.py` 双结构兼容提取到 `Output/Spine_v2/`，232 主包完成；gallery_v2 内用 `spine-all.js`(3.8) 分层实时播放。**已知问题**：仅 `normal` 动画会动、比例偏、部分「N 层失败」，待查（§6）。

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

（v1 旧产物与调试目录已归档/清理；`.trash` 内旧 bug 产物已于 2026-09-16 彻底删除，释放 8.9GB。）

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

**核心脚本**：`scan_assets.py`、`export_assets.py`、`export_cue_audio.py`、`reconstruct_live2d.py`/`fix_model3.py`/`extract_motions.py`、`compose_paintings_v2.py`(★v2)、`extract_spine_v2.py`(★v2)、`export_dependency_manifest.py`、`build_gallery_index.py`、`make_thumbs.py`、`mumu_sync.py`、`ship_name_map.py`、`scrape_wiki_fast.py`。

**文档**（导航见根目录 `README.md`，写入路由见 `AGENTS.md`）：
- `docs/DEV_LOG.md` 操作手册 · `docs/WORKFLOWS.md` 可复用工作流 · `docs/TROUBLESHOOTING.md` 踩坑 · `docs/ERRORS.log` 错误流水
- `docs/tools/` ALPA、AssetStudio 使用说明
- `docs/archive/` 历史归档（含 `PROJECT_STATUS_历史归档.md`、旧目录审计报告、旧 Spine 交接）

**数据**：`asset_manifest.json`、`Output/dependency_manifest.json`(86,398 条官方依赖表)、`Output/WikiData/ship_data.json`、`Output/gallery_v2/index.json`。

---

## 6. 接下来的任务

### ★ 2026-09-16~18 gallery_v2 质量复核

用户浏览 gallery_v2 发现一批还原问题，逐条排查进展：

1. ✅ **静态立绘「嵌套容器错位」——已修复并换入（2026-09-18）**
   根因（**非**此前猜的 sortingOrder）：`compose_paintings_v2.py::layout_all` 的仿射多减了 `p_local[0]/[1]`——`local_rect` 返回的 `(lx,ly)` 已是「相对父节点局部矩形左下角(0,0)」的偏移，不该再减父节点在其父级里的位置。单层皮肤 `p_local[0]=0` 不受影响；带中间容器（`layers`/`Touch`）的皮肤子层被整体甩偏（jialimaoxian 角色脱离克拉肯、fuluoxiluofu 角色甩到左下角）。
   修复提交 `52782a7`。只读扫描：4486 张中 **85 张受影响**（清单 `.diag/affected_skins.txt`，>500px 明显错位 32 张），逐张改前/改后对比确认均为改善 → **已换入 `Output/Paintings_v2/` 并重建这 85 张缩略图**（旧图备份 `Output/_OLD_bak/affected_20260918/`）。其余 4401 张逐像素不变。
2. ⚠️ **i404 型「背景大铺开/缝隙」——独立问题，未修**
   i404 的 `layers` 是 sd=(0,0) 满铺、`p_local[0]=0`，不受上面 bug 影响。它的背景层（`bj1/bj2/bj3`）在数据里就大范围铺开、拼不满有黑洞，是**另一类**问题。你给的 16:9 全屏 CG 是游戏运行时相机呈现（prefab 无扁平资源，已确认无法从立绘直接复现，放弃）。待查：是否需逆向游戏全屏 CG 相机/视口逻辑，或接受「角色居中视口裁切」的近似。
3. ⏸️ **missd（D小姐）「黑影」——用户暂搁置**（"先不管 missd"）。
4. ⚠️ **Spine 动态——未深入**：只有 `normal` 动画会动（下拉列 1/2/3/4/normal）、比例怪、i404 显示「1 层部件·1 层失败」。属 gallery 前端动画/分层逻辑 + `extract_spine_v2` 产物，另一条线。
5. ⏳ **元数据匹配——未做**：角色名/阵营/舰种有误或缺失，参考 l2d.su + 碧蓝 wiki 校正（联动/特殊舰尤甚，见 §10）。

> 诊断产物在 `.diag/`（不入库）。接手 agent 从第 2~5 条继续；第 1 条已闭环。

### 既有待办

**优先级高**
1. ⏳ Spine 动态立绘 viewer 验收（DeskSpine / gallery_v2 加载 Spine_v2 全量）。

**优先级中**
2. ⏳ 网络可用时补 Live2D Cubism 运行时，启用 gallery 的 Live2D 动作播放。
3. ⏳ 73 个联动/特殊舰中文名补录进 `ship_name_map`。
4. ⏳ 表情差分与游戏内表情 ID 对应表（可从 `AzurLaneData/ShareCfg/ship_skin_template.json` 补）。

**优先级低**
5. UI/图标批量导出（~2 万）、3D 宿舍资源、资源分类整理 `organize.py`。

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
- 部件→纹理包 = deps + externals；对象定位 = PathID 精确匹配（一包多 mesh 不再错拿）；放置 = 统一 Unity UI 数学（anchor/pivot/sizeDelta/anchoredPosition/localScale 全递归 + sprite 画框 `mRawSpriteSize` 非等比映射 rect）。
- 逆向关键：新版 bundle header `unity_version` 伪装成 `5.x.x`，真实 `2022.3.62f3` → 需 `UnityPy.config.FALLBACK_UNITY_VERSION="2022.3.62f3"`。静态立绘 = **纯 UI 结构**（RectTransform/CanvasRenderer，无 MeshRenderer），游戏把每个部件位置/大小/anchor/pivot 全写死，合成不需猜坐标。

### 9.2 静态立绘 v2（`scripts/compose_paintings_v2.py`）⚠️
零猜测、零手调。疑难样本 7/7 目视正确；v1 需手调的 feiteliekaer_3 / xili_alter / hailunna_4 现无参数自动正确。表情差分 `--faces all` 输出 `{name}_face{k}.png`。
> ✅ **嵌套容器错位已修（2026-09-18）**：带中间容器（`layers`/`Touch`）的皮肤子层曾被 `layout_all` 仿射多减 `p_local[0]` 甩偏（非 sortingOrder 问题），修复提交 `52782a7`，扫描 85/4486 受影响已全部换入。**仍遗留**：i404 型背景大铺开/缝隙（`p_local[0]=0` 不受该 bug 影响，另因，见 §6 第 2 条）。
**全量收官**：4300 → **4486**（补合成 190，成功 186 / 失败 4 为非主皮肤杂项包，已加过滤）。输出 `Output/Paintings_v2/`。

### 9.3 四个系统性根因修复 ★教训（全部代码级、零逐角色参数）
1. 无 mesh 整图部件**双重 Y 翻转** → root 背景层颠倒。修：`arr = A[rect.y : rect.y+h]`。
2. Spine atlas 页纹理需 **`flip=True`**（运行时按行0=顶采样）。
3. Windows 分离进程 stdout 默认 GBK，`print('✓')` 抛错致全量**假失败** → `sys.stdout.reconfigure('utf-8')` + 子进程 `PYTHONIOENCODING=utf-8`。
4. `layout_all` **root scale 只乘子层未乘 root 自身** → 层间比例错。修：局部空间纯 anchor 数学 + 仿射映射世界 + 自身 scale 绕 pivot（负=镜像）+ root 屏幕适配 scale 归一为 1。
> 结论再次印证：游戏数据自洽，所有错位都是解析姿势不对。（完整明细含文件行号与验证样本，见 `docs/archive/PROJECT_STATUS_历史归档.md` 末尾「完整明细存档」。）

### 9.4 Spine v2（`scripts/extract_spine_v2.py`）✅
双结构兼容（内联型 + 分离 `_res` 型）+ 外部页纹理按 deps 补齐 → `Output/Spine_v2/`。全量 **232 主包**完成。skel 3.8.99，皮肤为多部件骨骼（B/M/T）需分层合成。

### 9.5 Live2D 核查 ✅
266 个 live2d 包本地零缺失、自包含；旧提取无资产缺口，剩余仅 motion 质量（§2.5 B 类 12 模型）。

---

## 10. 本地资产浏览平台 `Output/gallery_v2` ✅（2026-09-15）

- **形态**：本地网页（源 28GB / Paintings 15GB，上线不现实），参照 l2d.su，中文名展示 静态立绘 + Spine + Live2D + 语音。
- **数据**：`build_gallery_index.py`（合并四类 + `ship_name_map` 拼音→中文 812 条 → `index.json/js`）+ `make_thumbs.py`（4300 张 380px WebP）。结果 954 船 / 4489 皮肤 / spine 231 / live2d 256 / 语音 268。
- **前端** `index.html`：网格懒加载 + 搜索/阵营/舰种/稀有度筛选；详情四标签，Spine 用 `vendor/spine/spine-all.js`(3.8) 按 `parts` 分层 WebGL 播放（170 单部件 / 61 多部件）。
- **运行**：`启动资产浏览器.bat`（→ `_gallery_server.py`：8777 端口 + `allow_reuse_address` + 端口占用即复用 + 结尾 `pause`，杜绝闪退）。file:// 下立绘/语音可看，Spine `fetch` 被 CORS 拦需走 .bat。
- **限制**：Live2D 暂只显示贴图（缺 Cubism Web 运行时 + 出网受限），预留 `vendor/live2d/`。

---

> **历史归档**：v1 时代攻关路线、多部件合成已知问题清单（Bug#1-#4）、7-30/7-31 修复记录、bj 背景层专项、调参工具 v3-v6 会话流水、旧 Spine Viewer 调试史 → 全部见 `docs/archive/PROJECT_STATUS_历史归档.md`。
