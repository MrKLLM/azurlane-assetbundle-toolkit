# 碧蓝航线 AssetBundles 解包与整理 — 完整操作手册

> **版本**: v1.0  
> **日期**: 2026-06-19  
> **状态**: 可执行

---

## 目录

1. [概述](#1-概述)
2. [技术选型](#2-技术选型)
3. [环境准备](#3-环境准备)
4. [核心难点分析](#4-核心难点分析)
5. [操作步骤](#5-操作步骤)
6. [脚本说明](#6-脚本说明)
7. [AI 贡献声明](#7-ai-贡献声明)
8. [故障排除](#8-故障排除)

---

## 1. 概述

### 项目目标
从碧蓝航线 (Azur Lane) 的 Unity AssetBundle 资源包中提取、分类、合成各类游戏资源，包括：
- 立绘（静态 + 皮肤变体）
- 背景图（场景/通用/加载）
- Live2D 动态模型
- Spine 动画
- 音频（BGM/音效/语音）
- UI 与图标

### 源数据
- **路径**: `D:\Azur Lane Assets\files\AssetBundles`
- **规模**: 196 个子目录，~86,890 个文件，~26.6 GB
- **格式**: Unity AssetBundle（94.6% 无后缀二进制 blob）

### 输出目录
```
D:\Azur Lane Assets\Output\
├── Raw/                    # AssetStudio 原始导出
├── Paintings/              # 整理后的立绘（按舰名/皮肤）
├── Paintings_Synthesized/  # 合成后的完整立绘
├── Backgrounds/            # 背景图（场景/通用/加载）
├── Live2D/                 # Live2D 模型
├── Spine/                  # Spine 动画
├── Audio/                  # 音频（BGM/SE/CV）
├── UI/                     # UI 资源
├── Icons/                  # 图标资源
└── Others/                 # 其他资源
```

---

## 2. 技术选型

### 为什么选 AssetStudio 而非其他工具

| 工具 | 优点 | 缺点 | 适用场景 |
|---|---|---|---|
| **AssetStudio** | 支持 Unity 3.4-2022.1，Texture2D/Sprite/AudioClip/Mesh 全覆盖，CLI 支持批量 | 原版已归档，需用 Anatawa12 维护的 fork | **首选** — 主力导出工具 |
| **UABE** | 可编辑 AssetBundle，支持资源修改后重新打包 | 命令行体验差，批量导出需额外脚本 | AssetStudio 失败时的**备选** |
| **AssetRipper** | 一键拆包为 Unity 项目结构 | 体积大，处理慢，对碧蓝航线兼容性待验证 | 大规模反向工程 |
| **UnityPy** | Python 库，脚本化灵活 | 需要自己编写解析逻辑 | **脚本集成** — 立绘合成核心 |

### 选择 AssetStudio 的理由
1. **兼容性**: 碧蓝航线使用 Unity 2019-2022，AssetStudio 完全支持
2. **效率**: CLI 模式批量处理速度快，单文件 <1s
3. **完整性**: 导出 Texture2D 为 PNG，Mesh 为 OBJ，AudioClip 为 WAV
4. **社区**: GitHub 15.5k star，文档和问题解答丰富

### UnityPy 的角色
AssetStudio 负责「批量导出」，UnityPy 负责「精确合成」：
- AssetStudio 导出的纹理是完整图集（atlas）
- 立绘需要根据 Mesh UV 坐标裁剪
- UnityPy 可以同时提取 Texture2D 和 Mesh 数据

---

## 3. 环境准备

### 3.1 安装工具

```powershell
# 1. 安装 Python 3.10+
# 下载: https://www.python.org/downloads/
# 安装时勾选 "Add Python to PATH"

# 2. 安装 Python 依赖
pip install UnityPy Pillow

# 3. 下载 AssetStudio
# 下载: https://github.com/Anatawa12/AssetStudio/releases
# 解压到: D:\AzurLaneTools\AssetStudioCLI\
# 确保 D:\AzurLaneTools\AssetStudioCLI\AssetStudioCLI.exe 存在

# 4. 下载 UABE（备选）
# 下载: https://github.com/SerenityCode/UnityAssetBundleExtractor/releases
# 解压到: D:\AzurLaneTools\UABE\
```

### 3.2 验证安装

```powershell
# 验证 Python
python --version
# 应输出: Python 3.10+

# 验证依赖
python -c "import UnityPy; import PIL; print('OK')"

# 验证 AssetStudio
Test-Path "D:\AzurLaneTools\AssetStudioCLI\AssetStudioCLI.exe"
# 应输出: True
```

### 3.3 目录结构

确保以下目录存在：
```
D:\Azur Lane Assets\
├── files\AssetBundles\      # 源数据（只读）
├── scripts\                 # 脚本目录
│   ├── scan_assets.py       # 扫描清单
│   ├── export_assets.py     # 批量导出
│   ├── organize.py          # 分类整理
│   └── synthesize_paintings.py  # 立绘合成
├── Output\                  # 输出目录（自动创建）
├── DEV_LOG.md               # 本手册
├── DEV_LOG_DRAFT.md         # 审计报告
├── ERRORS.log               # 错误日志
└── asset_manifest.json      # 资源清单（scan 后生成）
```

---

## 4. 核心难点分析

### 4.1 立绘拆分资源的合成逻辑

**问题**: 碧蓝航线立绘不是单张图片，而是「纹理图集 + 网格数据」的组合：

```
painting/aidang      → Mesh 数据（UV 坐标定义裁剪区域）
painting/aidang_tex  → Texture2D（完整纹理图集，包含多个部件）
```

**合成流程**:
```
1. 从 _tex bundle 提取 Texture2D → 得到完整纹理图集 PNG
2. 从 base bundle 提取 Mesh → 得到 UV 坐标
3. UV 坐标 [0,1] 映射到纹理像素坐标
4. 根据 UV 包围盒裁剪出实际立绘区域
5. 保存为独立 PNG
```

**UV 坐标翻转注意**: Unity 的 UV V 轴与图片 Y 轴方向相反，需要翻转：
```python
# UV → 像素坐标
top = int((1 - max_v) * tex_height)
bottom = int((1 - min_v) * tex_height)
```

### 4.2 皮肤变体的命名规则

```
{舰名}                    → 默认皮肤
{舰名}_2                  → 第2套皮肤
{舰名}_3_hx               → 第3套皮肤 HX变体
{舰名}_alter              → 改造皮肤
{舰名}_6_n_tex            → 第6套皮肤 夜间纹理
```

后缀含义：
| 后缀 | 含义 | 后缀 | 含义 |
|---|---|---|---|
| `_tex` | 纹理数据 | `_n` | 夜间变体 |
| `_hx` | HX变体 | `_rw` | RW变体 |
| `_bj` | 背景层 | `_alter` | 改造 |
| `_hei` | 黑化 | `_idol` | 偶像 |
| `_younv` | 幼年 | `_memory` | 回忆 |
| `_g` | G变体 | `_h` | H变体 |

### 4.3 AssetStudio 导出失败的处理

**常见错误**: `Unsupported Unity version`

**原因**: AssetStudio v0.16.47 最高支持 Unity 2022.1，若碧蓝航线更新到更高版本会失败。

**解决方案**: 自动切换 UABE 重试（`export_assets.py` 已实现自动降级）

### 4.4 大文件内存问题

AssetStudio 加载 Bundle 时会将整个文件解压到内存。对于 `painting/` 目录下 ~7GB 的文件：
- 建议分批导出（`--target painting`）
- 或逐子目录处理
- 确保系统有足够内存（建议 16GB+）

---

## 5. 操作步骤

### 阶段 ① 扫描分类

```powershell
# 进入脚本目录
cd "D:\Azur Lane Assets\scripts"

# 运行扫描（生成 asset_manifest.json）
python scan_assets.py
```

**输出**:
- `asset_manifest.json` — 完整资源清单（含文件路径、大小、分类）
- 控制台输出统计摘要

**预计耗时**: 2-5 分钟

### 阶段 ② 批量导出

```powershell
# 导出全部资源（耗时较长）
python export_assets.py --target all

# 或分批导出
python export_assets.py --target painting   # 立绘（~7GB）
python export_assets.py --target bg          # 背景
python export_assets.py --target audio       # 音频
python export_assets.py --target live2d      # Live2D

# Dry Run 模式（只查看不导出）
python export_assets.py --target painting --dry-run
```

**输出**:
- `Output/Raw/{子目录}/` — 原始导出文件
- `ERRORS.log` — 导出失败记录

**预计耗时**: 1-4 小时（取决于目标和硬件）

### 阶段 ③ 立绘合成

```powershell
# 合成完整立绘（从 _tex + mesh 裁剪）
python synthesize_paintings.py
```

**输出**:
- `Output/Paintings_Synthesized/企业/默认.png`
- `Output/Paintings_Synthesized/爱宕/2.png`

**预计耗时**: 30-60 分钟

### 阶段 ④ 分类整理

```powershell
# 整理所有导出资源
python organize.py
```

**输出**:
- `Output/Paintings/` — 立绘（按舰名/皮肤）
- `Output/Backgrounds/Scene/` — 场景背景
- `Output/Audio/BGM/` — 背景音乐
- `Output/UI/` — UI 资源
- `Output/Icons/` — 图标

**预计耗时**: 10-30 分钟

### 阶段 ⑤ 验证

```powershell
# 检查输出目录
Get-ChildItem "D:\Azur Lane Assets\Output" -Directory

# 统计文件数
(Get-ChildItem "D:\Azur Lane Assets\Output" -Recurse -File).Count

# 检查错误日志
Get-Content "D:\Azur Lane Assets\ERRORS.log" | Select-Object -Last 20
```

---

## 6. 脚本说明

### 6.1 scan_assets.py

**功能**: 遍历 AssetBundles 目录，按资源类型生成 JSON 清单

**核心逻辑**:
- 递归扫描所有文件
- 根据子目录名自动分类（196 个目录映射到 ~30 个类别）
- 解析立绘文件名提取舰名、皮肤编号、变体类型
- 计算文件哈希用于去重
- 输出统计摘要

**输出**: `asset_manifest.json`

### 6.2 export_assets.py

**功能**: 调用 AssetStudioCLI 批量导出资源

**核心逻辑**:
- 读取 asset_manifest.json 确定导出目标
- 逐文件调用 AssetStudioCLI
- 若导出失败（Unsupported Unity version），自动切换 UABE
- 记录所有失败到 ERRORS.log
- 支持 `--target` 参数选择导出类别
- 支持 `--dry-run` 模式预览

**命令行参数**:
```
--target painting|bg|audio|live2d|spine|ui|icons|char|all
--tool assetstudio|uabe|auto
--dry-run
```

### 6.3 synthesize_paintings.py

**功能**: 将 painting 的 _mesh + _tex 合成为完整 PNG

**核心逻辑**:
- 使用 UnityPy 读取 AssetBundle
- 从 _tex bundle 提取 Texture2D
- 从 base bundle 提取 Mesh UV 坐标
- 根据 UV 包围盒裁剪纹理
- 无 Mesh 信息时直接保存完整纹理
- 支持从已导出的 Raw 文件提取

**输出**: `Output/Paintings_Synthesized/{中文舰名}/{皮肤名}.png`

### 6.4 organize.py

**功能**: 将 Raw 导出资源按类型分类整理

**核心逻辑**:
- 立绘: 按舰名拼音→中文名映射，按皮肤编号分类
- 背景: 按场景/通用/加载分类
- 音频: 按 BGM/SE/CV 前缀分类
- 图标: 按目录名分类
- 其他: 未分类资源归入 Others

**输出**: `Output/` 下的分类目录

---

## 7. AI 贡献声明

### AI 生成的部分
- **所有脚本框架和核心逻辑** — scan_assets.py、export_assets.py、organize.py、synthesize_paintings.py
- **舰名映射表** — 基于审计报告中的文件名分析自动提取
- **皮肤变体解析规则** — 正则表达式模式匹配
- **错误处理和降级逻辑** — AssetStudio → UABE 自动切换
- **文档结构** — DEV_LOG.md 的整体框架

### 需要手动调整的部分
1. **舰名映射表**: `SHIP_NAME_MAP` 需要根据实际游戏数据补充完整
2. **皮肤编号映射**: `SKIN_NUMBER_MAP` 需要添加已知皮肤的中文名
3. **AssetStudioCLI 参数**: 需要验证实际 CLI 的参数格式（不同版本可能不同）
4. **UABE 集成**: UABE CLI 的批处理模式需要根据实际安装版本调整
5. **Mesh UV 解析**: UnityPy 提取的 Mesh 数据格式可能需要调试
6. **导出验证**: 首次运行后需要人工检查导出结果是否正确

### 建议的验证步骤
1. 先用 `--dry-run` 模式确认文件列表
2. 选择一个小目录（如 `activitypainting`）测试完整流程
3. 检查导出的 PNG 是否正确
4. 确认无误后再全量执行

---

## 8. 故障排除

### 8.1 AssetStudio 导出失败

**症状**: 控制台输出 `Unsupported Unity version`

**解决**: `export_assets.py` 会自动切换 UABE。若 UABE 也失败：
1. 检查 AssetStudio 版本是否为 v0.16.47+
2. 检查 UABE 是否正确安装
3. 手动用 AssetStudioGUI 测试单个文件

### 8.2 立绘合成缺贴图

**症状**: `ERRORS.log` 中出现 `无法提取纹理`

**解决**:
1. 确认 `_tex` 文件存在且可读
2. 检查 UnityPy 版本（需 1.10+）
3. 手动用 AssetStudioGUI 打开该 Bundle 检查

### 8.3 内存不足

**症状**: Python 进程被 OOM Kill

**解决**:
1. 分批导出（`--target painting` 而非 `--target all`）
2. 关闭其他程序释放内存
3. 增加系统虚拟内存

### 8.4 中文路径问题

**症状**: 文件名乱码或路径错误

**解决**:
1. 确保 Python 使用 UTF-8 编码
2. 设置环境变量: `$env:PYTHONUTF8 = "1"`
3. 路径中避免特殊字符

---

## 附录

### A. 完整文件清单

| 脚本 | 功能 | 依赖 |
|---|---|---|
| `scan_assets.py` | 扫描生成 JSON 清单 | Python 标准库 |
| `export_assets.py` | 批量导出资源 | AssetStudioCLI / UABE |
| `synthesize_paintings.py` | 立绘合成 | UnityPy, Pillow |
| `organize.py` | 分类整理 | Python 标准库, shutil |

### B. 输出目录结构示例

```
Output/
├── Paintings_Synthesized/
│   ├── 企业/
│   │   ├── 默认.png
│   │   ├── 2.png
│   │   └── 3.png
│   ├── 爱宕/
│   │   ├── 默认.png
│   │   └── 2.png
│   └── ...
├── Paintings/
│   ├── 企业/
│   │   ├── 默认.png
│   │   └── 2_誓约.png
│   └── ...
├── Backgrounds/
│   ├── Scene/
│   │   ├── bg_daofeng_1.png
│   │   └── star_level_bg_100.png
│   ├── Common/
│   ├── Loading/
│   └── Help/
├── Audio/
│   ├── BGM/
│   ├── SE/
│   └── CV/
├── Live2D/
├── Spine/
├── UI/
├── Icons/
└── Others/
```

### C. 快速参考

```powershell
# 完整流程（一键执行）
cd "D:\Azur Lane Assets\scripts"
python scan_assets.py
python export_assets.py --target all
python synthesize_paintings.py
python organize.py

# 检查结果
Get-ChildItem "D:\Azur Lane Assets\Output" -Directory
```
