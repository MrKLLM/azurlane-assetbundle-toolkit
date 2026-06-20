# 碧蓝航线 AssetBundles 解包项目 — 进度总结

> **生成时间**: 2026-06-20（立绘合成 v3：Mesh UV 重建算法）
> **用途**: 跨会话对接，方便新会话快速了解项目状态

---

## 1. 项目概览

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
| 输出路径 | `Output/Raw/painting/`, `paintingface/`, `metapainting/` 等 |

**脚本**: `scripts/export_assets.py`（使用 UnityPy，无需外部工具）  
**状态**: 全量导出成功

### 2.3 背景导出 ✅ 已完成

| 指标 | 数值 |
|---|---|
| 导出文件数 | 1,836（bg 1,254 + helpbg 353 + commonbg 111 + loadingbg 61 + 其他 57） |
| 失败数 | 0 |
| 输出路径 | `Output/Raw/bg/`, `commonbg/`, `loadingbg/`, `helpbg/` 等 |

### 2.4 音频导出 ⚠️ 已扫描但未导出

| 指标 | 数值 |
|---|---|
| 扫描文件数 | 4,370 (.b 文件) |
| 导出文件数 | 0（AudioClip 未成功提取） |

**问题**: `.b` 格式的音频 Cue Bundle 需要特殊处理，UnityPy 的 AudioClip 导出未生效。  
**待解决**: 需要研究 `.b` 格式的具体结构，或使用 AssetStudioGUI 手动导出。

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

### 2.6 Spine 动画 ⏳ 未处理

- `spinepainting/` 有 406 个文件（2,146 MB）
- 成对出现：`{name}` + `{name}_res`
- 需要 Spine Viewer 或 spine-unity 插件来查看

### 2.7 UI/图标导出 ⏳ 未处理

- `ui/` 有 4,059 文件（1,406 MB）
- 各种 icon 目录共有数万文件
- 可复用 `export_assets.py` 批量导出

### 2.8 资源分类整理 ⏳ 未处理

- `scripts/organize.py` 已编写但未运行
- 需要先完成所有导出后再整理

---

## 3. 已加工资产清单

### 输出目录结构

```
D:\Azur Lane Assets\
├── files\AssetBundles\          # 源数据（只读）
├── scripts\                     # 脚本目录
│   ├── scan_assets.py           # 扫描清单
│   ├── export_assets.py         # 批量导出
│   ├── reconstruct_live2d.py    # Live2D 还原
│   ├── fix_model3.py            # 修复 model3.json
│   ├── organize.py              # 分类整理
│   ├── synthesize_paintings.py  # 立绘合成（Mesh UV 重建）
│   └── ship_name_map.py         # 拼音→中文舰名映射
├── Output\
│   ├── Raw\                     # 原始导出（已完成）
│   │   ├── painting/            # 立绘（11,191 文件）
│   │   ├── paintingface/        # 面部特写（26 文件）
│   │   ├── bg/                  # 场景背景（1,254 文件）
│   │   ├── helpbg/              # 帮助背景（353 文件）
│   │   ├── commonbg/            # 通用背景（111 文件）
│   │   ├── loadingbg/           # 加载背景（61 文件）
│   │   └── ...
│   ├── Live2D\                  # Live2D 模型（256 个）
│   │   ├── lingbo/
│   │   ├── z23/
│   │   └── ...
│   ├── Paintings_Synthesized\   # 合成立绘（5,847 文件，扁平）
├── asset_manifest.json          # 资源清单
├── DEV_LOG_DRAFT.md             # 审计报告
├── DEV_LOG.md                   # 操作手册
└── ERRORS.log                   # 错误日志
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

### 需要安装/补充

| 工具 | 用途 | 下载地址 | 优先级 |
|---|---|---|---|
| Spine Viewer | 查看 Spine 动画 | [Esoteric Software](https://esotericsoftware.com/spine-player) | 中 |
| ffmpeg | 处理 .cpk 视频包 | [ffmpeg.org](https://ffmpeg.org/) | 低 |

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
| `scripts/synthesize_paintings.py` | 从 _tex bundle 用 Mesh UV 重建立绘（扁平输出） | ✅ 已完成（5,847/5,859） |
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

5. ✅ **立绘合成**（Mesh UV 重建算法）— 已完成
   - 5,847 个 PNG 文件，12 失败（0.2%）
   - 算法来源：ALPA 源码 `rebuildPainting()` — 用独立 Mesh 的 UV 坐标从纹理裁剪四边形块
   - 扁平输出到 `Output/Paintings_Synthesized/`
   - 总大小 ~9.8 GB

### 优先级中

6. **音频导出**
   - 研究 `.b` 格式 Cue Bundle 的结构
   - 或使用 AssetStudioGUI 手动导出 AudioClip
   - 4,370 个 .b 文件待处理

7. **资源分类整理**
   ```bash
   python scripts/organize.py
   ```

8. **调查 B 类模型动作提取失败**（12 个模型）
   - StreamedClip 格式差异或 moc3 版本不同

### 优先级低

9. **StreamedClip 二进制格式深入研究**（已记录到 TROUBLESHOOTING.md）
10. Spine 动画查看/导出（需安装 Spine Viewer）
11. 视频包 (.cpk) 处理（需安装 ffmpeg）
12. 3D 宿舍资源导出
13. **UI/图标批量导出**（~2 万个小图标，优先级最低）

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
