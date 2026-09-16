# 碧蓝航线 AssetBundles 解包与资产还原

> 从《碧蓝航线》(Azur Lane) Unity AssetBundle 中解包、还原**静态立绘 / Spine 动态立绘 / Live2D / 语音 / 背景**等资产的数据驱动工具链与研究记录。

## ⚠️ 关于本仓库

- 本仓库**只包含脚本与文档，不含任何游戏资产**。
- 游戏源包 `files/`、导出产物 `Output/`、第三方工具 `tools/` 均已被 `.gitignore` 排除（体积数十 GB + 版权原因）。
- Clone 后需自备游戏 AssetBundle 放到 `files/AssetBundles/`，脚本按此路径读取。
- 仅供个人学习研究，请遵守游戏服务条款与相关版权。

## 成果概览

| 资产 | 数量 | 说明 |
|---|---|---|
| 静态立绘 | 4,486 张 | v2 数据驱动合成，零手调 |
| Spine 动态立绘 | 232 主包 | 多部件骨骼分层 |
| Live2D | 256 模型 | 纹理/物理/motion |
| 语音 | 4,370 WAV | BGM/CV/Other/SE |
| 背景族 | ~1,900 张 | bg/helpbg/commonbg/loadingbg 等 |

另有一个本地资产浏览平台 `Output/gallery_v2`（由脚本生成，产物不入库）。完整进度见 [`PROJECT_STATUS.md`](PROJECT_STATUS.md)。

## 核心方法（一句话）

游戏把每个部件的位置 / 大小 / anchor / pivot / 依赖**全写死在资产里**：用 `dependencies` 官方依赖表 + `PPtr→SerializedFile.externals` 解析定位纹理包，再用统一的 Unity UI 布局数学放置 → **无需猜坐标**。

关键坑：新版 bundle header 的 `unity_version` 被伪装成 `5.x.x`，真实为 `2022.3.62f3`，需设 `UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"`，否则 UnityPy/ALPA 全部解析失败。

## 仓库结构

```
AGENTS.md            # agent 协作规则（含文档写入路由表）
PROJECT_STATUS.md    # 当前进度快照（跨会话对接入口）
IDEA.md              # 想法备忘
scripts/             # 数据驱动还原管线与工具脚本
docs/                # 操作手册 / 工作流 / 踩坑 / 工具说明 / 归档
```

## 主要脚本（`scripts/`）

| 脚本 | 作用 |
|---|---|
| `scan_assets.py` | 扫描 AssetBundles 生成清单 |
| `export_assets.py` | UnityPy 批量导出纹理/网格（背景族等） |
| `export_cue_audio.py` | CRIWARE `.b` → WAV 音频导出 |
| `export_dependency_manifest.py` | 导出 86k 条官方依赖表 |
| `compose_paintings_v2.py` | ★ 静态立绘 v2 合成（数据驱动） |
| `extract_spine_v2.py` | ★ Spine 动态立绘 v2 提取 |
| `run_v2_full.py` | v2 全量批跑编排 |
| `reconstruct_live2d.py` / `fix_model3.py` / `extract_motions.py` | Live2D 还原 |
| `build_gallery_index.py` / `make_thumbs.py` | 生成本地浏览平台数据与缩略图 |
| `scrape_wiki_fast.py` / `generate_ship_database.py` / `ship_name_map.py` | 舰船 wiki 数据与中文名映射 |
| `mumu_sync.py` / `mumu_adb.py` | 与模拟器增量同步资产 |

## 快速上手

```bash
pip install UnityPy Pillow          # 依赖（UnityPy 1.25.x）
python scripts/scan_assets.py       # 生成资产清单
python scripts/export_dependency_manifest.py
python scripts/compose_paintings_v2.py <皮肤名>   # 合成单张样本
```

> 环境为 Windows + Python 3.11/3.13。批量脚本遵循「先样本确认后全量」原则。

## 文档导航（`docs/`）

| 文档 | 内容 |
|---|---|
| [`docs/DEV_LOG.md`](docs/DEV_LOG.md) | 完整操作手册（技术选型、步骤、故障排除） |
| [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) | 可复用工作流 |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | 踩坑记录（问题 → 原因 → 解决） |
| [`docs/tools/`](docs/tools/) | ALPA、AssetStudio 工具使用说明 |
| [`docs/archive/`](docs/archive/) | 历史归档（旧审计报告、旧 Spine 交接、PROJECT_STATUS 历史全文） |

> 新增长尾内容前，先看 [`AGENTS.md`](AGENTS.md) 的「文档写入路由表」确认归属文件，避免往状态文档堆流水。
