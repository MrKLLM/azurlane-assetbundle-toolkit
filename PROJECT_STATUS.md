# 碧蓝航线 AssetBundles 解包项目 — 进度总结

> **生成时间**: 2026-08-02（调参工具 v4 — 逐层独立调整 + 磁吸对齐）
> **用途**: 跨会话对接，方便新会话快速了解项目状态

---

## 1. 项目概览

### 2.0 仓库治理 ✅

- 已将仓库忽略规则收敛为“保留源码与文档，忽略游戏资产与生成产物”。
- 现已忽略目录：`files/`、`Output/`、`tools/`、`.micode/`、`.mimocode/`。
- 已将生成产物与资产元数据从 Git 索引中移除，避免后续再次提交游戏资产。

---

## 2. 各部分进度

对碧蓝航线 (Azur Lane) 的 Unity AssetBundle 资源包进行解包、分类、导出和整理。

- **源路径**: `D:\Azur Lane Assets\files\AssetBundles`
- **规模**: 196 个子目录，~86,890 个文件，~26.6 GB
- **格式**: Unity AssetBundle（94.6% 无后缀二进制 blob）

---

## 2. 各部分进度

### 2.1 目录扫描 ✅ 已完成

| 指标 | 数值 |
|---|---|
| 扫描文件数 | 86,849 |
| 总大小 | 26.62 GB |
| 分类数 | ~30 个资源类别 |
| 输出文件 | `asset_manifest.json` (25 MB) |

**脚本**: `scripts/scan_assets.py`  
**状态**: 已验证通过

### 2.2 立绘导出 ✅ 已完成

| 指标 | 数值 |
|---|---|
| 导出文件数 | 43,520 |
| 失败数 | 0 |
| 耗时 | ~108 分钟 |
| 输出路径 | `Output/Raw/painting/` → 已清理（保留 Paintings_Synthesized） |

**脚本**: `scripts/export_assets.py`（使用 UnityPy，无需外部工具）  
**状态**: 全量导出成功

### 2.3 背景导出 ✅ 已完成

| 指标 | 数值 |
|---|---|
| 导出文件数 | 1,836（bg 1,254 + helpbg 353 + commonbg 111 + loadingbg 48 + 其他 70） |
| 失败数 | 0 |
| 输出路径 | `Output/Raw/bg/`, `commonbg/`, `loadingbg/`, `helpbg/` 等 |

### 2.4 音频导出 ✅ 已完成

| 指标 | 数值 |
|---|---|
| 扫描文件数 | 4,370 (.b 文件) |
| 导出文件数 | 4,370 WAV 文件 |
| 失败数 | 0 |
| 导出大小 | ~14 GB |
| 耗时 | ~160 秒 |
| 输出路径 | `Output/Audio/BGM/`, `CV/`, `Other/`, `SE/` |

**技术方案**: `.b` 文件是 CRIWARE ACB 格式（`@UTF` 头），需要复制为 `.acb` 扩展名后用 vgmstream 解码为 WAV。

**分类统计**:
| 类别 | 文件数 | 大小 |
|---|---|---|
| BGM | 536 | 12.0 GB |
| CV | 2,696 | 1.6 GB |
| Other | 1,136 | 700 MB |
| SE | 2 | 4.5 MB |

**脚本**: `scripts/export_cue_audio.py`  
**依赖**: vgmstream (已安装到 `%LOCALAPPDATA%\vgmstream`)

### 2.5 Live2D 模型还原 ⚠️ 大部分完成

| 指标 | 数值 |
|---|---|
| 还原模型数 | 256/256 |
| 纹理拼接正确 | 256/256 |
| HitAreas 交互 | ✅ 已修复（TouchHead/TouchBody/TouchSpecial + Tap 前缀）|
| 有真实动画数据 | 244/256 |
| 动画全部成功 | 26/256 |
| 部分动画失败 | 218/256 |
| 无动画数据 | 12/256 |
| 输出大小 | ~3.4 GB |
| 输出路径 | `Output/Live2D/{舰名}/` |

**脚本**:
- `scripts/reconstruct_live2d.py` — 从 AssetBundle 还原模型（已修复纹理顺序）
- `scripts/fix_model3.py` — 修复 model3.json 为 Live2DViewerEX 兼容格式
- `scripts/extract_motions.py` — 从 AnimationClip 提取真实动作数据

**每个模型包含**:
- `{name}.model3.json` — 模型配置（Live2D Cubism 3/4 兼容格式）
- `{name}.moc3` — 模型二进制（从 CubismMoc MonoBehaviour 提取）
- `{name}.physics3.json` — 物理数据（从 TextAsset 提取）
- `{name}.png` — 贴图（使用原始 m_Name 命名，1-7 张）
- `motion/*.motion3.json` — 动作（从 AnimationClip StreamedClip 提取）

**还原状态详细分类**:

| 类别 | 数量 | 说明 | 测试状态 |
|---|---|---|---|
| A1 类 | 26 | 画面完整 + 全部动画成功 | ✅ lingbo 已验证 |
| A2 类 | 218 | 画面完整 + 部分动画成功 | ⏳ 待抽样验证 |
| B 类 | 12 | 画面完整，动画完全失败 | ⏳ 待排查原因 |
| C 类 | 0 | 画面有问题 | — |
| D 类 | 0 | 无法还原 | — |

**B 类模型列表**（动画提取完全失败）:
- aerbien_3, aimierbeierding_2/3/3_hx, ankeleiqi_3
- banrenma_2, boyixi_2, genaisennao_2, heitaizi_2
- huonululu_3, qiye_9, tiancheng_cv_3

**已知限制**:
- HitAreas 为占位符（[{Id:HitArea,Name:Head},{Id:HitArea2,Name:Body}]），无真实交互区域
- 需要逆向 moc3 二进制格式才能提取真实 HitAreas
- Live2D 皮肤（有交互）vs 动态皮（只会动）：live2d 目录下均为 Live2D 皮肤

**纹理数量分布**:

| 纹理数 | 模型数 |
|---|---|
| 1 张 | 167 |
| 2 张 | 81 |
| 3 张 | 2 |
| 4 张 | 1 |
| 5+ 张 | 5 |
| 5 张 | 2 |
| 6 张 | 2 |
| 7 张 | 1 |

**已修复的问题**:
- ~~Live2DViewerEX 加载失败~~ → 修复 model3.json 格式
- ~~纹理顺序错乱~~ → 按原始 m_Name 排序
- ~~motion 文件为空~~ → 从 StreamedClip 提取真实数据
- ~~HitAreas 无交互~~ → TouchHead/TouchBody/TouchSpecial + Tap 前缀 motion groups
- ~~参数名未映射~~ → 从 moc3 提取 Param/PARAM 前缀参数名

**已知限制**:
- StreamedClip 二进制格式未完全逆向，部分模型动画质量有限
- HitAreas 使用 moc3 中的 Touch ID，非真实交互区域定义
- moc3 参数数量可能少于 motion 期望（版本不匹配时删除未映射参数）

### 2.6 Spine 动画 Viewer ⚠️ 严重问题

| 指标 | 数值 |
|---|---|
| 源 bundle 数 | 209（spinepainting）+ 6（spineitem） |
| 提取成功角色数 | 143 |
| 总变体数 | 185（含 B/M/T 等变体） |
| 输出路径 | `Output/Spine/spinepainting/{name}/` |
| 输出格式 | .skel + .atlas + .png（texture atlas） |
| Viewer | `tools/spine-viewer/index.html`（WebGL, spine 3.8） |
| Manifest | `Output/Spine/spine_manifest.json` |
| 合成立绘 | `Output/Paintings_Synthesized/{name}.png`（已有大部分角色） |

**脚本**: `scripts/extract_spine.py`（提取）、`scripts/compose_paintings.py`（合成）  
**状态**: 数据提取完成，Viewer 视觉效果完全不可用

#### ⚠️ 最新会话修复尝试（2026-06-24）

**本次会话做了以下修改，但用户反馈"完全静止了，背景倒过来了，角色和背景位置大小关系混乱"：**

1. **WebGL 透明化**：`alpha: false` → `alpha: true, premultipliedAlpha: true` + `gl.clearColor(0, 0, 0, 0)`
2. **render() 函数重写**：2D bg-canvas 优先绘制（静态背景 + fallback），WebGL 仅在 `!fallbackImg` 时绘制 spine
3. **fallback 搜索顺序**：`[_rw, _n_rw, _n, _bg]` → `[name, _rw, _n_rw, _n, _bg]`（优先 base name）
4. **安装 UnityPy 1.25.0** 到默认 Python 环境

**⚠️ 接手者注意：以上修改可能导致了新问题，需要回滚或重新审视。**

#### 1. 当前存在的问题 (Issue List)

目前动态立绘系统在合成与渲染逻辑上出现了以下偏差，导致视觉效果完全不可用：

**问题一：完全静止状态**
- 动画系统未能正确触发，或在修复 fallback 逻辑后陷入死循环/冻结状态
- 原本应有的动态效果消失，立绘呈现完全静止
- 动画名是数字（'0', '1', '2'...），多层变体动画不同步
- **最新状态（2026-06-24）**：修改 render() 后用户反馈"完全静止了"，可能是 fallback 逻辑导致所有 spine 层都被跳过

**问题二：背景图层倒置**
- 动态立绘合成逻辑错误，导致背景层（Background Layer）发生 180 度翻转
- 背景完全倒过来显示
- 典型案例：aisaikesi_7 的 `aisaikesi_7BG.png` 静态背景图显示时上下颠倒
- 原因：Unity 导出的 PNG 使用 Y 轴翻转坐标系，WebGL 绘制时未做逆变换
- **最新状态（2026-06-24）**：用户反馈"动态立绘合成也错了，背景完全倒过来了"，可能是 drawImage 或 spine 渲染的 Y 轴处理问题

**问题三：空间关系混乱**
- 角色（Character）与背景（Background）的位置坐标、缩放比例（Size）匹配失效
- 角色未能正确叠加在背景的预定位置，出现遮挡关系错误或比例失调
- 典型案例：beikaluolaina_3 需要将角色叠加到沙滩背景上，但位置/层次不对
- 部分角色 spine WebGL 渲染完全不显示（batch_check.js 显示 185/185 加载成功，但渲染不出来）
- **最新状态（2026-06-24）**：用户反馈"角色和背景的位置和大小关系"混乱，合成图叠加位置不正确

#### 2. 修复与优化目标 (Milestones)

后续接手的开发流程需重点达成以下目标：

**目标一：恢复动力学逻辑**
- 重新检查 Spine 渲染器的初始化生命周期，确保动画帧循环（requestAnimationFrame）正常运行
- 消除静止故障
- 确保多层变体（B/M/T/_bg）的动画同步播放
- **⚠️ 接手者需回滚 2026-06-24 的 render() 修改**，因为用户反馈修改后"完全静止了"

**目标二：校正合成坐标系**
- 修正 Canvas / WebGL 的坐标映射逻辑
- 确保背景图片采样方向正确，不再出现镜像或倒置
- Unity spine 使用 Y 轴向上坐标系，需在渲染时正确处理 Y 轴翻转
- **⚠️ 接手者需检查 drawImage 的 Y 轴处理**，以及 WebGL 的 coordinate system

**目标三：重构层级与比例算法**
- 建立统一的视口（Viewport）管理系统
- 根据角色锚点自动计算背景适配比例
- 确保角色与背景的相对位置符合美术设计原稿
- 多层变体按正确层序叠加：_bg(0) → B(1) → M(2) → T(3)
- **⚠️ 接手者需理解 spine 的 coordinate system**（Y 轴向上 vs 向下）

#### 已有可用资源

| 资源 | 路径 | 说明 |
|------|------|------|
| spine 3.8 runtime | `tools/spine-viewer/spine-runtime/3.8_spine-core.js` + `3.8_spine-webgl.js` | 已验证可解析 185/185 变体 |
| 合成立绘脚本 | `scripts/compose_paintings.py` | ALPA 算法，从 AssetBundle 提取 Mesh UV + 纹理合成 |
| 已有合成立绘 | `Output/Paintings_Synthesized/` | 大部分角色都有完整合成图 |
| 舰船数据 | `Output/Spine/ship_data.json` | 70/153 角色有阵营舰种数据 |
| Manifest | `Output/Spine/spine_manifest.json` | 143 角色，185 变体列表 |
| batch 诊断 | viewer 控制台 `runBatchDiagnostic()` | 可检查所有角色加载状态 |
| 交接文档 | `docs/SPEINE_VIEWER_HANDOFF.md` | 详细技术交接文档 |
| beikaluolaina_3 合成图 | `Output/Paintings_Synthesized/beikaluolaina_3.png` | 2248x1364, 89.4% 可见像素（含角色+背景） |
| beikaluolaina_3 角色剪影 | `Output/Paintings_Synthesized/beikaluolaina_3_n.png` | 2037x1013, 52.5% 可见像素（仅角色） |
| aisaikesi_7 合成图 | `Output/Paintings_Synthesized/aisaikesi_7.png` | 3368KB，完整合成图 |
| aisaikesi_7 背景 | `Output/Spine/spinepainting/aisaikesi_7/aisaikesi_7_bg.png` | 静态背景图 |

### 2.7 UI/图标导出 ⏳ 未处理

- `ui/` 有 4,059 文件（1,406 MB）
- 各种 icon 目录共有数万文件
- 可复用 `export_assets.py` 批量导出

### 2.8 资源分类整理 ⏳ 未处理

- `scripts/organize.py` 已编写但未运行
- 需要先完成所有导出后再整理

### 2.9 Wiki 舰船数据 ✅ 已完成

| 指标 | 数值 |
|---|---|
| 舰船总数 | 862 |
| 爬取耗时 | ~92 秒（8线程并行） |
| 数据格式 | JSON (name, faction, ship_type, rarity) |
| 输出路径 | `Output/WikiData/ship_data.json` |

**阵营分布**: 白鹰 167, 皇家 159, 重樱 148, 东煌 120, 铁血 96, 撒丁帝国 38, 自由鸢尾 37, 飓风 27, 北方联合 26, 维希教廷 24, 郁金王国 17
**舰种分布**: 驱逐 242, 轻巡 164, 重巡 111, 战列 106, 航母 80, 轻航 46, 潜艇 39, 战巡 35, 超巡 7, 风帆 16

**脚本**: `scripts/scrape_wiki_fast.py`（并行版，862 艘 92 秒）
**已知问题**: 148 艘缺少阵营信息（主要是联动舰船、布里、μ兵装等特殊舰船）

---

## 3. 已加工资产清单

### 已加工资产清单

| 类别 | 文件数 | 大小 | 说明 |
|---|---|---|---|
| Paintings_Synthesized | 16,588 | ~12 GB | 合成立绘(4,307) + 表情差分(12,281) |
| Paintingface | 13,120 | ~200 MB | 表情贴图原件 |
| Audio/BGM | 536 | 12.0 GB | 背景音乐 |
| Audio/CV | 2,696 | 1.6 GB | 角色语音 |
| Audio/Other | 1,136 | 700 MB | 其他音频 |
| Audio/SE | 2 | 4.5 MB | 音效 |
| Live2D | 256 | 3.5 GB | Live2D 模型 |
| Raw/bg 等 | 1,923 | 1.97 GB | 背景图等原始导出 |
| **合计** | **~12,000** | **~30 GB** | |

### 保留的原始资产

| 目录 | 文件数 | 大小 | 说明 |
|---|---|---|---|
| files/AssetBundles | 86,849 | 26.62 GB | 源数据（只读） |
```
D:\Azur Lane Assets\
├── AGENTS.md                    # agent 行为规则（每次对话自动加载）
├── PROJECT_STATUS.md            # 进度总结 / 跨会话对接
├── asset_manifest.json          # 资源清单（25MB，86,849 文件）
├── paintingface_mapping.json    # 表情映射关系
├── ERRORS.log                   # 导出/合成错误日志
├── files\                       # 源数据（只读）
│   └── AssetBundles\           # ~26.6GB，86,849 文件，196 子目录
├── Output\                      # 输出（~30GB）
│   ├── Raw\                     # 原始导出（bg/helpbg/commonbg/loadingbg/paintingface 等）
│   ├── Audio\                   # BGM / CV / Other / SE
│   ├── Live2D\                  # 256 个模型
│   ├── Paintingface\            # 表情贴图原件（13,120）
│   ├── Paintings_Synthesized\   # 合成立绘 + 表情差分（16,588）
│   ├── Spine\                   # spine 提取 + spine_manifest.json + spinepainting/
│   └── WikiData\                # 舰船 wiki 数据（ship_data.json）
├── scripts\                     # 87 个 .py（脚本库）+ debug\
│   ├── scan_assets.py / export_assets.py / export_cue_audio.py
│   ├── compose_paintings.py / synthesize_paintings.py
│   ├── reconstruct_live2d.py / fix_model3.py / extract_motions.py
│   ├── extract_spine.py / extract_paintingface.py / extract_cpk.py
│   ├── organize.py / scrape_wiki_fast.py / ship_name_map.py
│   └── debug\                   # 调试脚本
├── tools\                       # 外部工具
│   ├── ALPA-1.0.5.1\            # 立绘注入（Java 17）
│   ├── AssetStudio-v2.4.1\ / AssetStudioModGUI.net8.0\ / AssetStudioModGUI_net8_win64\
│   ├── CriPakTools\             # CPK 解包
│   └── spine-viewer\            # WebGL Viewer（index.html + spine-runtime）
└── docs\                        # 知识库
    ├── README.md / DEV_LOG.md / DEV_LOG_DRAFT.md
    ├── WORKFLOWS.md / TROUBLESHOOTING.md
    ├── SPEINE_VIEWER_HANDOFF.md # Spine 交接文档（文件名原拼写为 SPEINE）
    └── ALPA使用说明.md / AssetStudio使用说明.md / ERRORS.log
```

---

## 4. 工具链

### 已安装/可用

| 工具 | 版本 | 用途 | 状态 |
|---|---|---|---|
| Python | 3.13 | 运行脚本 | ✅ |
| UnityPy | 1.25.0 | 读取/导出 AssetBundle | ✅ |
| Pillow | 12.0.0 | 图像处理 | ✅ |
| Live2DViewerEX | — | 查看 Live2D 模型 | ✅ 已安装 |
| AssetStudioGUI | ModGUI.net8.0 / v2.4.1 | 可视化预览/导出 | ✅ 已安装（3 个版本共存） |
| ALPA | v1.0.5.1 | 立绘/头像注入 | ✅ 已安装（需 Java 17） |
| Java | 17.0.19 | ALPA 运行时 | ✅ 已安装 |
| ffmpeg | 7.1 | 音频/视频处理 | ✅ 已安装 |
| vgmstream | v2117 | CRIWARE 音频解码 | ✅ 已安装 |

### 需要安装/补充

| 工具 | 用途 | 下载地址 | 优先级 |
|---|---|---|---|
| Spine Viewer | 查看 Spine 动画 | https://esotericsoftware.com/spine-player | 中 |

---

## 5. 关键文件清单

### 脚本

| 文件 | 功能 | 状态 |
|---|---|---|
| `scripts/scan_assets.py` | 扫描 AssetBundles 生成 JSON 清单 | ✅ 已验证 |
| `scripts/export_assets.py` | UnityPy 批量导出 Texture2D/Mesh | ✅ 已验证 |
| `scripts/reconstruct_live2d.py` | 从 AssetBundle 还原 Live2D 模型 | ✅ 已验证（纹理顺序已修复）|
| `scripts/fix_model3.py` | 修复 model3.json 为 Live2DViewerEX 兼容格式 | ✅ 已验证 |
| `scripts/extract_motions.py` | 从 AnimationClip StreamedClip 提取 motion3.json | ✅ 已验证 |
| `scripts/diagnose_models.py` | 诊断所有模型还原状态（A/B/C/D 分类） | ✅ 已完成 |
| `scripts/organize.py` | 将 Raw 导出分类整理 | ⏳ 未运行 |
| `scripts/compose_paintings.py` | 多部件叠加合成完整立绘（ALPA 算法） | ✅ 已完成（4,307/4,319） |
| `scripts/_debug_streams.py` | 调试 VertexData m_Streams 布局 | ⏳ 待运行 |
| `scripts/_debug_uv.py` | 扫描 raw data 中的 UV 候选数据 | ⏳ 待确认 |
| `scripts/ship_name_map.py` | 拼音→中文舰名映射（812 条） | ✅ 已创建 |

### 文档

| 文件 | 内容 |
|---|---|
| `DEV_LOG_DRAFT.md` | 只读审计报告（目录结构、资源映射） |
| `DEV_LOG.md` | 完整操作手册（技术选型、工具链、步骤） |
| `PROJECT_STATUS.md` | 本文件（进度总结） |
| `TROUBLESHOOTING.md` | 踩坑记录（10 个已解决问题） |
| `WORKFLOWS.md` | 可复用工作流（8 条记录） |

### 数据

| 文件 | 内容 |
|---|---|
| `asset_manifest.json` | 86,849 个文件的完整清单（25 MB） |
| `ERRORS.log` | 导出/合成错误记录 |

---

## 6. 接下来的任务

### 优先级高

1. ✅ **Live2DViewerEX 兼容性修复** — 已完成
2. ✅ **HitAreas 交互修复** — 已完成（Tap 前缀 + Touch ID）
3. ✅ **纹理顺序修复** — 已完成
4. ✅ **动作数据提取** — 已完成（244/256 模型）

5. ⚠️ **立绘合成**（多部件叠加合成，ALPA 算法）— 脚本已修复，待全量运行
   - 历史基线: 4,307 个 PNG（12 失败 0.28%），输出到 `Output/Paintings_Synthesized/`
   - **2026-07-30 修复（样本已验证通过，详见 §6.1 末尾「2026-07-30 修复记录」）**:
     - 绘制顺序改为 **Unity 层级兄弟顺序**（父在下、子在上；同层后者盖前者），取代原面积排序 → 修复 aersasi_3 蕨叶盖人
     - 移除 `_bj` 不透明度 >30% 跳过规则 → 恢复 chaijun_4 等被误删的背景内容（马等）
     - Sprite `_tex`（无 mesh）按 `flip=True` 修正；Mesh `_tex` 用 `flip=False` + `FLIP_TOP_BOTTOM`
     - 圣光/光效层按内容（纯白像素占比 ≥80%）跳过；AABB 最小角修正；长宽比缩放不拉伸；bbox 裁边
   - **待办**: 全量运行（约 4300 文件）需用户确认后执行（先备份旧目录到 `_OLD_bak/`）

6. ✅ **表情差分提取** — 已完成
   - 2,160 个 paintingface bundle → 13,120 张表情贴图
   - 输出到 `Output/Paintingface/`（原件）+ `Output/Paintings_Synthesized/`（副本）
   - 映射关系：`paintingface_mapping.json`（2,114 个匹配到完整立绘）

### 优先级高（待修复）

7. ⚠️ **修复多部件立绘合成位置问题**（详见 §6.1）
   - Bug #2: Y轴翻转导致背景倒置
   - Bug #1: AABB 计算错误导致部分组件偏移
   - Bug #3: 名称匹配遗漏导致组件缺失
   - Bug #4: Pivot 未使用导致粘贴位置偏差

### 优先级中

7. **资源分类整理**
   ```bash
   python scripts/organize.py
   ```

8. **调查 B 类模型动作提取失败**（12 个模型）
   - StreamedClip 格式差异或 moc3 版本不同

### 优先级低

9. **StreamedClip 二进制格式深入研究**（已记录到 TROUBLESHOOTING.md）
10. ✅ **Spine 动画提取与 Viewer** — 已完成
    - 143 个角色，185 个变体，WebGL Viewer 验证通过
11. 3D 宿舍资源导出
12. **UI/图标批量导出**（~2 万个小图标，优先级最低）

---

## 6.1 多部件立绘合成 — 已知问题清单

### 问题概述

`compose_paintings.py` 的多部件叠加合成功能存在以下已知问题，需要后续会话修复。

**当前脚本状态**: 已回退到修复前版本（按面积排序 + AABB 原始算法），能正常运行但部分角色合成结果不正确。

**⚠️ 修复尝试记录（2026-06-24 会话）**:
1. AABB 修复（`out_w = 2 * extent` + 顶点偏移）：对单部件合成有效（`aerbien_3_n_tex` 偏移问题修复），但全量运行后用户反馈"角色本体和背景的大小和位置关系都错了"
2. Y-flip 修复（`y = canvas_h - pastePoint.y - offset_y - img.height`）：单部件测试时 `adiliao_2` 耳机位置正确，但全量运行后用户反馈"背景全是倒过来了"
3. 两个修复均已回退到原始版本

**⚠️ 接手者关键理解**:
- 不能简单翻转 Y 坐标 — 会导致背景倒置
- 不能简单修改 AABB 计算 — 会改变已有正确结果的位置关系
- 需要先分析 `synthesize_tex_bundle()` 输出的图像坐标系方向
- 需要理解 Unity Canvas 坐标系 → 图像坐标系的完整转换链

### Bug #1: AABB 画布尺寸计算错误

**文件**: `scripts/synthesize_paintings.py` 第 77-79 行；`scripts/compose_paintings.py` 第 78-96 行

**问题代码**:
```python
aabb = mesh_obj.m_LocalAABB
out_w = int(aabb.m_Center.x + aabb.m_Extent.x) + 1  # 仅当 AABB 从 (0,0) 开始时正确
out_h = int(aabb.m_Center.y + aabb.m_Extent.y) + 1
px = int(positions[i][0])  # 未减去 AABB 最小角偏移
py = int(positions[i][1])
```

**问题本质**: 公式 `center + extent` 计算的是 AABB 右/上边缘的坐标值，而非画布的宽度/高度。当 AABB 最小角不是 (0,0) 时（如 `aerbien_3_n_tex`），内容在画布内产生固定偏移。

**实测数据（aerbien_3_n_tex）**:
| 指标 | 值 |
|---|---|
| AABB center | (656.0, 834.0) |
| AABB extent | (464.0, 688.0) |
| AABB 范围 | (192, 146) → (1120, 1522) |
| 当前画布尺寸 | 1121 x 1523 |
| 实际内容尺寸 | 929 x 1377 |
| **左上角空白偏移** | **192px × 146px** |

**正确算法**:
```python
min_x = aabb.m_Center.x - aabb.m_Extent.x
min_y = aabb.m_Center.y - aabb.m_Extent.y
out_w = int(2 * aabb.m_Extent.x) + 1
out_h = int(2 * aabb.m_Extent.y) + 1
px = int(positions[i][0] - min_x)
py = int(positions[i][1] - min_y)
```

**注意**: 修复此 bug 后需重新运行全量合成，且需验证不影响已有正确结果（大多数 AABB 从 (0,0) 开始的 bundle 不受影响）。

### Bug #2: 多部件合成 Y 轴未翻转

**文件**: `scripts/compose_paintings.py` 第 244-246 行

**问题代码**:
```python
x = int(comp["pastePoint"][0]) + offset_x
y = int(comp["pastePoint"][1]) + offset_y  # 直接使用 Unity Y 坐标
canvas.paste(comp_img, (x, y), comp_img)
```

**问题本质**: `m_AnchoredPosition` 是 Unity UI 坐标系（Y 轴向上），而 PIL 图像坐标系 Y 轴向下。pastePoint 的 Y 值没有进行翻转。

**因果链（以 adiliao_2 为例）**:
1. `adiliao_2_bj`（耳机）pastePoint Y = -143.8（Unity 中位于角色下方）
2. 经过 `calculate_canvas_size` 的 offset_y=144 补偿后，画布坐标 y = -144 + 144 = 0
3. PIL 中 y=0 是画布顶部，但 Unity 中 Y=-143.8 应该是画布底部
4. 结果：耳机被粘贴到画布顶部，而非角色腿部位置

**尝试过的修复**: `y = canvas_h - pastePoint.y - offset_y - comp_img.height`，但导致背景倒置。说明单部件合成的 `_tex` bundle 输出本身可能已经有 Y 翻转，需要更仔细地分析坐标系。

**⚠️ 重要发现**: 简单翻转 Y 坐标会导致背景倒置。根源可能是 `synthesize_tex_bundle()` 输出的图像坐标系已经包含了某种 Y 翻转（UnityPy 默认 flip=True），需要分析单部件合成输出的坐标方向再决定合成时如何处理。

**正确修复方向**: 需要分析 Unity `synthesize_tex_bundle` 输出的图像坐标系，确定是否需要在合成阶段翻转。建议对比 ALPA (AzurLanePaintingAnalysis-Kt) 的 `groupPainting()` 函数中 `pasteExtension` 的 Y 坐标处理。

### Bug #3: 名称匹配遗漏

**文件**: `scripts/compose_paintings.py` 第 162 行

**问题**: base bundle 中的 RectTransform 名称与 `_tex` bundle 名称不完全对应。
- 例: `shop_hx` → 期望 `shop_hx_tex`，但实际 bundle 叫 `aerbien_3_shophx_tex`
- 导致该组件被遗漏

**修复方向**: 需要模糊匹配或维护名称映射表。

### Bug #4: m_Pivot 未被使用

**文件**: `scripts/compose_paintings.py` 和 `scripts/synthesize_paintings.py`

**问题**: 两个脚本都提取了 `m_Pivot`（通常为 (0.49, 0.67)），但合成时完全未考虑 pivot 对粘贴位置的影响。Pivot 不在 (0,0) 时，pastePoint 对应的锚点不在组件左下角，需要额外偏移 `pivot * size`。

### 已验证正确的功能

- ✅ `get_bundle_info()`: 正确提取 RectTransform 数据和 _tex bundle 对应关系
- ✅ `calculate_canvas_size()`: 正确计算所有组件的并集边界
- ✅ 图层排序: **按 Unity 层级兄弟顺序**（父在下、子在上；同层后者盖前者），取代原面积排序（见 2026-07-30 修复记录）
- ✅ 大多数单部件合成: 5,847/5,859 成功（0.2% 失败率）

### 2026-07-30 修复记录（多部件立绘合成）

**脚本**: `scripts/compose_paintings.py`（自包含，FIXTEST 验证用，未动正式 `Output/Paintings_Synthesized/`）

**本轮修复的 7 处问题（样本验证通过）**:
1. `PAINTING_DIR` 用绝对路径（避免误指向脚本目录）
2. `find_tex_path` 增加「去下划线」命名变体（`shop_hx`→`shophx` 等）+ 小写变体
3. 根 RectTransform（bundle 名）不再被跳过（背负主立绘）
4. 长宽比缩放用 `min(rect/mesh)`，不拉伸变形
5. 合成后 `crop(getbbox())` 裁掉透明边
6. Sprite 资源（无 mesh，GPU Y 向下存储）按 `flip=True`；Mesh 资源用 `flip=False` + `FLIP_TOP_BOTTOM`
7. 移除「`_bj` 不透明度 >30% 跳过」规则（误删了 chaijun_4 的马等真实内容）

**关键架构修正 — 绘制顺序**:
- 原脚本用「面积从大到小」排序决定 Z 序，导致背景 `bj`（面积大）画在人物 `rw` 之上（aersasi_3 蕨叶盖脸）。
- 改为 `build_draw_order()`：按 RectTransform 父子 + `m_Children` 兄弟顺序遍历，父先画（底层）、子后画（上层），同层后者盖前者。
- 这样 `bj`（背景）自然落在 `rw`（人物）之下，无需任何跳过规则；chaijun_4 的马（在 `bj` 内）也得以保留。

**本轮用户报告并修复的 bug**:
- `feiteliekaer_3.png` 少脸：经像素级诊断，脸在 `rw` 图层内且已正确渲染（中心偏上头部区域肤色占比 12.5%）。`face` 节点是全项目通用的 UI 热区节点（整个 painting 目录无任何 `_face_tex` 包），不含纹理，跳过它不影响脸；脸始终来自 `rw`。
- `chaijun_4.png` 少马：根因为第 7 条 `_bj` 跳过规则把含马的 `chaijun_4_bj_tex` 整层删掉（bj 不透明率 51.5% > 30%）。移除规则后马恢复（终图彩色像素 45.9%）。
- `aersasi_3.png` 蕨叶盖脸（连带发现）：根因是绘制顺序错（面积排序把 `bj` 画到 `rw` 上）。改兄弟顺序后蕨叶落人物后（头部区域蕨叶绿占比 0.1%）。

**验证样本（FIXTEST）**: feiteliekaer_3 / chaijun_4 / aersasi_3 / aerbien_2 / adiliao_2 / adaerbote_2 共 6 张，3 处 bug 均修复，3 张回归样本无异常。

**待办**: 全量运行（约 4300 文件）需用户确认（AGENTS.md 先确认后执行）。

### 2026-07-31 修复记录（face 纹理目录支持 — 修正上一轮"脸在 rw"误判）

**问题复盘**：
- 用户用截图再次报告 `feiteliekaer_3.png` 脸没填充 + 身体位置错。
- 上一轮我**错误诊断**为"脸在 rw 里、face 是 UI 热区无纹理"——因为我只看了 `painting/` 目录的 _tex 文件，**忽略了独立的 `paintingface/` 面部特写目录**。

**真实根因**：
- 碧蓝航线把面部特写纹理**单独存放在 `paintingface/` 目录**，命名约定为 `{bundle_name}`（无 `_tex` 后缀）。
- 整个 `paintingface/` 有 2160 个文件，覆盖几乎所有角色。
- `feiteliekaer_3` 的 `face` RectTransform（229×211）通过 MeshImage 的 `m_Sprite` 引用 `(file6, pid=-5996719416134721951)`，**该 Sprite 就住在 `paintingface/feiteliekaer_3` 包里**。
- 原脚本 `find_tex_path` 只搜索 `PAINTING_DIR = .../painting`，永远找不到 face 纹理 → `face` RectTransform 加载不到纹理被跳过。

**修复**：
- `compose_paintings.py::find_tex_path` 增加 `PAINTINGFACE_DIR` 常量与针对 `face` 节点的兜底分支：
  ```python
  if go_name == 'face':
      face_p = os.path.join(PAINTINGFACE_DIR, base_bundle)
      if os.path.exists(face_p):
          return face_p
  ```
- **关键约束**：兜底仅对 `go_name == 'face'` 生效，不对所有找不到 _tex 的组件兜底（否则 UI 热区会被错误匹配到 paintingface）。

**验证（FIXTEST）**：
- `feiteliekaer_3`：components 5→6，脸 RectTransform 加载 paintingface/feiteliekaer_3 成功，229×211 脸纹理按 RectTransform 锚点正确覆盖在角色脸上，无重复。
- `chaijun_4` / `aersasi_3` / `adiliao_2` / `aerbien_2` / `adaerbote_2` / `abuluqi_2`：全部 components +1（多了 face），无回归。
- 像素核对 feiteliekaer_3 脸区：彩色占比从 78% → 91%；face RectTransform 区域皮肤占比 9.1%（脸纹理确实在画）。

**脚本当前最终修复列表（8 项）**:
1. PAINTING_DIR 绝对路径化
2. find_tex_path 重写（去下划线变体 + 修未定义变量崩溃）
3. root 根节点不再被跳过
4. 等比缩放 `min(rect/mesh)`（不拉伸）
5. 画布 bbox 裁剪 + 纯白光效层跳过（按内容判断）
6. Sprite 资源自动用 flip=True（按是否含 mesh 选择）
7. 绘制顺序改为 Unity 层级兄弟顺序（`build_draw_order()`）
8. **face 纹理从 `paintingface/` 目录加载**（针对 `face` 节点的兜底分支）

### 2026-07-31 续：feiteliekaer_3「相对躺椅错位」根因定位（contain+居中修复）

**用户反馈**：`feiteliekaer_3.png` 身体「相对躺椅错位」（第 2 轮确认）；第 3 轮用户进一步纠正——躺椅应**平移**、不应**拉伸改比例**。

**两轮纠正记录**：
- 第 3 轮 A：曾误判为「rw 位置写死无法改」 → 推翻。
- 第 3 轮 B：曾尝试 `fill_rect`（把部件拉伸铺满 rect） → **用户否决**：躺椅比例被横向拉伸，改的不对。
- 第 3 轮 C（正确）：根因是**粘贴位置**，不是缩放。

**真正根因（contain + 贴左下角 → 应 contain + 居中）**：
- 旧脚本等比 contain 缩放**保住了部件比例**（正确），但缩放后图像若小于 rect，旧代码把它**贴到 rect 左下角**，而非在 rect 内**居中**。
- Unity Image「Preserve Aspect」默认在 rect 内居中显示；旧代码漏了居中 → 全幅背景层（如 `feiteliekaer_3_bj` 躺椅，contain 后图宽 4099 < rect 宽 6296）被甩到左侧，身体（画布绝对坐标、本就正确）就"悬"在躺椅右外。
- 对 mesh≈rect 的部件（rw/face/泳池背景），contain 后图=rect，居中=无偏移 → **不影响已有正确结果**。

**量化（feiteliekaer_3 单部件内容 bbox，`_test_center_align.py`）**：
| 方案 | 躺椅内容 x | 躺椅中心 | 身体中心−躺椅中心 | 身体右缘 vs 躺椅 | 比例 |
|---|---|---|---|---|---|
| contain+左下角（旧bug） | [1,3980] | 1990 | +1093 | 超出 82px | 不变 |
| fill（被否） | [5,6113] | — | — | 在内 | ✗拉伸 |
| **contain+居中（采用）** | [1098,5077] | 3087 | **−4px** | 在内 | 不变 |

→ 躺椅右移 ~1097px、比例不变，身体中心几乎正中落在躺椅上（差 4px），错位修复。

**代码改动**（`scripts/compose_paintings.py`，已落地）：
- 缩放仍为等比 contain（保持比例，`fill_rect` 参数保留仅作对比测试，默认 False）。
- **粘贴改为 rect 内居中**：
  ```python
  off_x = (rect_w - comp_img.width) / 2.0
  off_y = (rect_h - comp_img.height) / 2.0
  px = int(round(c['origin'][0] + off_x))
  py = int(round(canvas_h - (c['origin'][1] + off_y) - comp_img.height))
  ```
- 注释说明：对 mesh≈rect 部件 off≈0 无影响；只修正 contain 后小于 rect 的背景层。

**样本验证**（`Output/Paintings_Synthesized_FIXTEST/center`）：
feiteliekaer_3 / nubiyaren / gubixuefu / aerbien_2 / aerbien_3 / adiliao_2 全部 100% 覆盖。
其中 aerbien_2/3、adiliao_2 输出尺寸与旧版**完全一致**（居中为 no-op，无回归）；feiteliekaer_3、nubiyaren 等含"背景层 contain<rect"的角色被正确居中。

**次要问题（未改，待用户拍板）**：face 部件 rect/纹理均为 229×211，但 rw 中脸部占位框高 279（短 68px）→ 下半脸（嘴/下巴）缺失。居中/fill 均不改变（face 纹理=rect）。需用户给游戏原图或确认「把 face 拉伸到 279 高覆盖占位」是否可接受。

**待用户确认（按 AGENTS.md 先确认后执行）**：
1. 查看 FIXTEST/center/feiteliekaer_3.png，确认躺椅错位修复、比例正常；
2. 是否以此（contain+居中）**全量重跑（约 4300 文件）**？会先备份正式 `Output/Paintings_Synthesized/` 到 `_OLD_bak/`；
3. face 下半脸缺失是否一并处理。

**临时诊断脚本**（用完待清理）：`_diag_comp_info.py` `_diag_mesh_mapping.py` `_test_fill_align.py` `_test_center_align.py` `_scan_fill_risk.py` `_run_sample_fill.py` 及第 2 轮遗留 `_diag_rt_tree.py` `_diag_face_box3.py` `_diag_black_silhouette.py` `_test_no_face.py` `_test_face_stretched.py`。

### 2026-07-31 定稿：feiteliekaer_3 床层最终参数（S=0.844, dx=160, dy=-190）

**用户反馈链**：0.93 版"床大了一点"→ 0.767 版"偏小了"→ 像素优化 0.844 "仍不太对"→ 目视微调定稿。
**关键纠错（本轮复盘，避免重蹈）**：
1. **REF 缩放映射曾被误判**：UI 检测误以为绘画区域 (0,1,1750,1042)，实测为 **(83,33,1690,990)**（截图 1920×1086 内、映射 0.2553）。用 rw 模板匹配验证（score=0.933）暴露映射错误 → 所有旧"对照图"REF 侧缩放错 8%。
2. **锚点污染**：抱枕连通块米色占比仅 45.9%（严重粘连）→ 0.767 反推偏小；NCC 模板匹配对纯色块有尺度偏向，均不可用。
3. **最终方案 = 像素网格优化**（`_optimize_bj.py`）：固定非床层，网格搜索 (S,dx,dy) 最小化合成 vs REF 截图亮度中位差 → 起点 S=0.844/dx=370/dy=-270（角色区 median diff=4.2 验证映射正确）。
4. **用户目视微调定稿**（角色/泳池/脸不动，只动床层）：上移80(dy-190) → 左下120(dx250,dy-230) → 左上40(dx210,dy-190) → 左移40(dx170) → 左移10 → **S=0.844, dx=160, dy=-190**。

**代码**：`BUNDLE_BJ_SCALES={'feiteliekaer_3':0.844}`，`BUNDLE_BJ_OFFSETS={'feiteliekaer_3':(160,-190)}`。三旋钮说明：dx>0 右移 / dy_up>0 上移 / S 相对 contain(3.6585) 缩放，仅 bj 层生效。
**产物**：`Output/Paintings_Synthesized/feiteliekaer_3.png` 已更新（2026-07-31 20:51，旧版备份 `Output/_OLD_bak/feiteliekaer_3.png_20260624_contain版`）；FIXTEST 留 `feiteliekaer_3_定稿版.png` + `overlay/feiteliekaer_3_定稿对照.png`。
**待用户确认**：① 定稿版观感 OK？② 是否全量重跑（约 4300 文件，先备份 `_OLD_bak/`）；③ face 下半脸缺失（211<279 短 68px）是否一并处理。
**临时脚本待清理**：`_diag_bj_scale.py` `_diag_cc_pillow.py` `_solve_bj_params.py` `_match_pillow.py` `_optimize_bj.py` 及早期 `_diag_*`/`_test_*` 系列。

### 修复优先级建议

1. **Bug #2 (Y轴翻转)** — 最关键，影响所有多部件合成的位置正确性。⚠️ 但不能简单翻转，需要先分析单部件输出坐标系
2. **Bug #1 (AABB计算)** — 影响部分 `_tex` bundle 的单部件合成质量。⚠️ 修改后会影响已有正确结果的位置
3. **Bug #3 (名称匹配)** — 影响少数角色的组件完整性
4. **Bug #4 (Pivot处理)** — 影响粘贴位置精度

### 测试样本

| 角色 | Bundle | 参考图 | 问题 |
|---|---|---|---|
| 阿尔比恩换装2 | `aerbien_2` | `C:\Users\KLLM\Desktop\Temp File\525px-阿尔比恩换装2.jpg` | 角色位置正确，背景正确 |
| 阿尔比恩换装3 | `aerbien_3` | `C:\Users\KLLM\Desktop\Temp File\作业\aerbien_3.png` | 角色应坐在围栏上，当前位置有偏差 |
| 阿蒂利奥换装 | `adiliao_2` | `C:\Users\KLLM\Desktop\Temp File\525px-阿蒂利奥·雷戈洛换装.jpg` | 耳机应挂在腿上，当前在顶部 |
| 阿达伯特换装2 | `adaerbote_2` | — | 背景尺寸偏小 |

---

## 7. 新会话对接指南

在新会话中，发送以下内容即可快速对接：

```
我正在做碧蓝航线 AssetBundles 解包项目。
源路径: D:\Azur Lane Assets\files\AssetBundles
进度总结: D:\Azur Lane Assets\PROJECT_STATUS.md
踩坑记录: D:\Azur Lane Assets\TROUBLESHOOTING.md
工作流: D:\Azur Lane Assets\WORKFLOWS.md

当前状态:
- 256 个 Live2D 模型可正常显示、HitAreas 交互已修复
- 音频导出/UI导出/分类整理 待处理

下一步: [你的具体任务]
```

### ⚠️ Spine Viewer 接手者必读（2026-06-24 更新）

**当前 Viewer 文件**: `tools/spine-viewer/index.html`

**本次会话修改的内容（可能导致了新问题）**:
1. WebGL context: `alpha: true, premultipliedAlpha: true` + `gl.clearColor(0, 0, 0, 0)`
2. render() 函数：2D bg-canvas 优先绘制，WebGL 仅在 `!fallbackImg` 时绘制
3. fallback 搜索顺序：`[name, name + "_rw", name + "_n_rw", name + "_n", name + "_bg"]`

**用户反馈的问题**:
- "完全静止了" — 动画不再播放
- "背景完全倒过来了" — Y 轴翻转问题

### ⚠️ 多部件立绘合成接手者必读（2026-06-24 更新）

**核心文件**: `scripts/compose_paintings.py`（多部件合成）、`scripts/synthesize_paintings.py`（单部件合成）

**当前状态**: ⚠️ 本节（2026-06-24 写）称「两个修复已回退」已过时。实际脚本已落地 7-30/7-31 修复 + bj 绝对定位机制，**当前可正常运行**；详见 **§9（2026-08-02 更新）** 与 `HANDOFF.md`。

**已知问题**: 见 §6.1 多部件立绘合成 — 已知问题清单（仅剩 bj 背景层逐角色参数调优，见 §9）

**⚠️ 修复尝试失败记录**:
- AABB 修复（`2 * extent` + 顶点偏移）→ 全量运行后用户反馈"角色本体和背景的大小和位置关系都错了"
- Y-flip 修复（`canvas_h - pastePoint.y - offset_y - img.height`）→ 全量运行后用户反馈"背景全是倒过来了"
- **关键教训**: 不能孤立修复单个 bug，需要理解 Unity 坐标系到 PIL 图像坐标系的完整转换链

**ALPA 参考源码**:
- GitHub: `Deficuet/AzurLanePaintingAnalysis-Kt`
- 关键函数: `Functions.kt` 中的 `groupPainting()`
- 工具库: `Deficuet/AzurlanePaintingUtils` 中的 `alp` 包

**调试建议**:
1. 先用 `aerbien_2`（简单2层）、`adiliao_2`（3层+耳机）、`aerbien_3`（围栏位置）测试
2. 参考图在 `C:\Users\KLLM\Desktop\Temp File\` 目录
3. 单部件合成结果在 `Output/Paintings_Synthesized/` 中可以单独检查各 _tex 合成效果
4. Python 3.12 路径: `C:\Users\KLLM\AppData\Local\Programs\Python\Python312\python.exe`

**关键分析方向**:
1. 分析 `synthesize_tex_bundle()` 输出图像的坐标系方向（UnityPy flip=True 是否导致输出已翻转？）
2. 对比 ALPA 的 `pasteExtension` 如何处理 Y 坐标
3. 理解 `calculate_canvas_size()` 中 offset_x/offset_y 的含义
4. 确认 pastePoint 坐标在 Unity 中的实际含义（是左下角还是中心？）
- "角色和背景的位置和大小关系"混乱 — 合成图叠加位置不正确

**建议的排查方向**:
1. 回滚 render() 修改，恢复原来的 spine 渲染逻辑
2. 检查 WebGL 的 Y 轴方向（spine 使用 Y 向上，Canvas2D 使用 Y 向下）
3. 检查 drawImage 的坐标计算是否正确
4. 理解 spine coordinate system：spine 的 origin 在左下角，Canvas2D 在左上角

**关键文件**:
- `tools/spine-viewer/index.html` — Viewer 主文件（~735 行）
- `tools/spine-viewer/spine-runtime/3.8_spine-core.js` — spine core
- `tools/spine-viewer/spine-runtime/3.8_spine-webgl.js` — spine WebGL renderer
- `scripts/compose_paintings.py` — 合成立绘脚本
- `Output/Paintings_Synthesized/` — 已有合成立绘

**测试角色**:
- `beikaluolaina_3` — 有完整合成图（2248x1364），含角色+沙滩背景
- `aisaikesi_7` — 有完整合成图 + 静态背景图
- `lingbo` — spine 渲染正常的基础测试角色

---

## 8. 技术备忘

### 立绘文件命名规则
```
{舰名}           → 默认皮肤 bundle
{舰名}_2         → 第2套皮肤
{舰名}_tex       → 纹理数据
{舰名}_2_tex     → 第2套纹理
{舰名}_n         → 夜间变体
{舰名}_hx        → HX变体
{舰名}_rw_tex    → RW变体纹理
{舰名}_alter     → 改造皮肤
{舰名}_hei       → 黑化皮肤
```

### Live2D 模型结构
```
Output/Live2D/{name}/
├── {name}.model3.json     # 模型配置
├── {name}.moc3            # 模型二进制
├── {name}.physics3.json   # 物理数据
├── texture_*.png          # 贴图
└── motion/*.motion3.json  # 动作（占位符）
```

### MOC3 版本分布
- Version 1: lingbo, z23, bisimai_2 等
- Version 2: qiye_7, xinnong_3, abeikelongbi_3 等

---

## 9. 2026-08-02 进度更新（bj 背景层专项 — 接手必读）

> 本文件此前最后更新至 2026-07-31（feiteliekaer_3 床层定稿）。以下为 2026-08-02 新增工作。
> **更细的交接文档见 `D:\Azur Lane Assets\HANDOFF.md`**（2026-08-02 03:44 生成，含任务清单 / 开放问题 / 验证流程 / 文件路径）。

### 9.1 全量 bj 背景层筛查（只读分析）

- 脚本：`scripts/screen_bj_misalign.py`（18 秒扫 4315 个 bundle）
- 结论：**仅 172 个（4%）角色有 `bj` 层**；其余 4133 个用 `mainFullScreen` 全屏背景，无 bj 错位问题。
- 172 个 bj 角色按 mesh 占 rect 比例（mesh_ratio）分级：🔴 高风险 <0.10 共 **61 个**，🟠 0.10~0.20 共 33 个，🟡/🟢 >0.20 共 74 个。
- ⚠️ 重要认知：**mesh_ratio 小 ≠ 位置错位**。61 个高风险里多数 contain+居中就对了（feiteliekaer_3 是 bj 内容在 rect 内偏置的特例）。真正 bug 是「bj 被放大 6~16 倍铺满画布又画在角色上层」。
- 产物：`Output/bj_misalign_report.md` + `Output/bj_screen_full.csv`

### 9.2 bj 绝对定位机制（BUNDLE_BJ_ABSOLUTE）

- `compose_paintings.py` 顶部新增 `BUNDLE_BJ_ABSOLUTE = {(bundle): (S, px, py, below_rw)}`：
  - `S` = 缩放系数（<1 缩小 / 1 原尺寸 / 2-3 放大 / 10+ 铺满）
  - `(px,py)` = 画布绝对坐标（裁 content bbox 后贴到这）
  - `below_rw = True` 时 bj 绘制在 rw 之前（角色遮挡 bj）
- 与已有 `BUNDLE_BJ_OFFSETS` / `BUNDLE_BJ_SCALES`（feiteliekaer_3 用）并存，默认仍走 contain+居中。
- 自动求解器：`scripts/solve_bj_transform.py`（对照游戏原 CG 用 FFT 相位相关 + viewport 标定解参数）；解出的参数**必须目视复核**（纯色块尺度偏向、掩码粘连，早期被坑过）。

### 9.3 当前三个已定参角色状态

| 角色 | 状态 | 参数 |
|---|---|---|
| feiteliekaer_3 | ✅ 定稿 + 已同步正式目录 | `BUNDLE_BJ_SCALES=0.844` / `BUNDLE_BJ_OFFSETS=(160,-190)` |
| **hailunna_4** | ✅ 定稿 + 已同步正式目录（2026-08-02） | `BUNDLE_BJ_ABSOLUTE=(1.50, 1447.0, 1244.0, True)`。酒杯在栏杆后，栏杆横杆穿过酒身 |
| **xili_alter** | ✅ 定稿 + 已同步正式目录（2026-08-02） | `BUNDLE_BJ_ABSOLUTE=(2.6966, 1613.3, 2074.9, True)`。粉色漩涡铺满背景，在角色身后（已确认 `below_rw=True`） |

- 参考 CG：`Output/refs/hailunna_4_ref.jpg`、`Output/refs/xili_alter_ref.jpg`
- 三向对比图：`Output/Paintings_Synthesized_FIXTEST/final_handoff/samescale_*.png`（ref vs 定稿版）
- 旧版（6-24）已备份：`Output/_OLD_bak/hailunna_4.png_20260624_bj铺满盖角色`、`Output/_OLD_bak/xili_alter.png_20260624_bj铺满盖角色`
- 已知细节：xili_alter 漩涡相对角色比 ref 略大（ref 含游戏 UI 边距、我们合成的纯净画布更大）；如需更严格比例匹配可微调 S（当前 2.6966）和 (px, py)

### 9.4 待接手任务（详见 HANDOFF.md §7）

- ~~**A. hailunna_4 收尾**~~ ✅ 2026-08-02 完成：正式管线渲染通过、与 ref 一致（栏杆横杆穿过酒身）、旧版已备份并覆盖
- ~~**B. xili_alter 图层确认**~~ ✅ 2026-08-02 完成：`below_rw` 改为 `True`、渲染与 ref 空间关系一致（漩涡在角色身后）、旧版已备份并覆盖
- **C. 61 高风险角色批量策略**（待用户拍板：给 ref 自动解 / 全量自动解 / 直接全量重跑）
- **D. 全量重跑**（先备份 `Output/_OLD_bak/`）

### 9.5 关于 §6.1「脚本已回退到修复前版本」的更正

§6.1 开头称「当前脚本状态: 已回退到修复前版本（按面积排序 + AABB 原始算法）」——**此描述已过时**。实际 `compose_paintings.py` 已落地 2026-07-30 / 07-31 的多项修复（ALPA 自包含、face 从 `paintingface/` 加载、绘制顺序改 Unity 兄弟顺序、contain+居中、`BUNDLE_BJ_ABSOLUTE` 绝对定位），当前可正常运行；正在进行的是 bj 背景层的**逐角色参数调优**，不是坐标系重建。

### 9.6 坐标系统 / 历史坑（接手者不要重蹈）

- ❌ 不要用 `fill` 拉伸（改比例，用户否决过）
- ❌ 不要贴左下角，必须 rect 内居中
- ❌ 单角色 rw 偏移必须 **rw + face 一起移**，否则脸身脱节
- ❌ 不要加 pivot 对齐偏移——用户反馈 rw mesh < rect 时贴左下角是正确的，加 pivot 偏移导致回归
- 画布坐标 Y 向下（PIL 习惯）；配置表 `py` / `dy_up` 均为画布坐标（Y 向下）

### 9.7 2026-08-02 会话记录（pivot 偏移 → 回退）

- 用户报告 `alabama_3.png` rw 身体错位（mesh=1792 < rect=2048）。
- 我误判为 pivot 对齐问题，新增了 pivot 偏移逻辑（mesh 中心对齐 rect pivot）。
- 导致 feiteliekaer_3（mesh==rect）也被偏移 → 加条件排除 bj + 仅 mesh < rect 时生效。
- 进一步发现 hailunna_4/xili_alter 仍有差异 → 用户纠正"我上次是对的"，**全部回退，无净代码改动**。
- **教训**：rw mesh < rect 时直接贴 rect 左下角是正确行为（与 Unity 游戏内渲染一致），不要加 pivot 偏移。

### 9.8 2026-08-02 高风险 bj 批量渲染 + 交互式调参工具

- 批量渲染 58 个高风险 bj 角色（排除已定稿 3 个）到 `sample_highrisk/`。
- 用户反馈"大部分有问题，小部分没问题"，问题集中在 bj 组件的**大小比例**和**位置**。
- 因无参考 CG，自动求解不可行 → 制作**交互式调参网页**。

**交互式调参工具**：
- 位置：`Output/Paintings_Synthesized_FIXTEST/tuner_assets/tuner.html`
- 资源：`base/`（58 张无 bj 底图）+ `bj/`（58 张 bj 精灵图）+ `meta.json`
- 操作方式：
  - 🖱️ **鼠标拖拽**：移动 bj 位置
  - 🖱️ **滚轮**：缩放 bj（Ctrl+滚轮 = 视图缩放）
  - ⌨️ **方向键**：微调位置（Shift=大步 10px）
  - ⌨️ **W/S**：缩放 ±0.01
  - ⌨️ **Q/E**：上一个/下一个
  - ⌨️ **B**：切换 below_rw（bj 在角色上/下）
  - ⌨️ **空格**：切换显示/隐藏 bj
  - ⌨️ **Ctrl+S**：保存当前参数
- 参数自动保存到 `localStorage`，可一键导出 `bj_params.json`
- 调完后将参数写入 `compose_paintings.py` 的 `BUNDLE_BJ_ABSOLUTE`

**代码改动**：
- `compose_paintings.py` 新增 `skip_bj` 参数（供 base 图导出使用）
- 新增调试脚本：`export_tuner_assets*.py`、`gen_bj_report.py`、`analyze_bj_types.py`

### 9.9 2026-08-02 调参工具 v4 — 逐层独立调整 + 磁吸对齐

v3 工具只支持调整体 bj 层，用户反馈很多组件内部也存在错位 → 重写为逐层版本。

**新方案**：
- **资源提取**：通过 prefab RectTransform → GameObject 映射 + `find_tex_path()` 找到每个 GameObject 对应的 _tex bundle
- 成功提取 ~1200 个独立层（58 角色 × ~21 层/角色），包含 rw、bj、face、extra bg 等类型
- 每层单独导出 PNG 精灵图（已裁剪透明边缘），记录完整元数据（x,y,w,h,pivot,texture coords）

**v4 调参网页**：
- 位置：`Output/Paintings_Synthesized_FIXTEST/tuner_assets_v4/tuner.html`
- 资源：`base/`（合成底图）+ `layers/`（~1200 张逐层精灵图）+ `meta.json`
- **逐层选择器**：侧栏列出当前角色的所有层，带类型标记 [RW]🔵/[BJ]🟡/[BG]⚪，点击选中后可独立调整
- **单层控制**：scale/xpos/ypos/below_rw/visibility 全可独立设值
- **磁吸对齐**：拖动时检测其他可见层边界，距离 < 15px 自动吸附并显示虚线引导
- **锁定机制**：保存后自动锁定，防止误操作；再次点击锁定按钮解锁
- 全部快捷键与 v3 兼容（方向键/W/S/Q/E/B/空格/R/Ctrl+S）

**关键修复**：
- PPtr 引用读取：从 `get_obj()` 改为 `.read()` 才能正确获取 GameObject 名称
- JSON 序列化：numpy int64 需 `.item()` 转原生 Python 类型

**遗留问题**：
- 部分 GameObject 无对应 _tex 文件（如 build/pifu/biandui 等 UI 标记节点）→ 这些是热区/标签，不含纹理
- feiteliekaer 有额外 "3" 层（background 类型），mesh_w=2048/mesh_h=1220 但 rect_w=296/rect_h=194 → 比例悬殊
