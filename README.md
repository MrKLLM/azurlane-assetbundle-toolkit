# 碧蓝航线资产工具说明文档

## 工具概览

| 工具 | 用途 | 版本 |
|------|------|------|
| **ALPA** | 碧蓝航线立绘/头像注入工具 | 1.0.5.1 |
| **AssetStudio** | Unity 资产提取/预览/导出工具 | v2.4.1 |
| **AssetStudioModGUI (旧)** | Unity 资产提取工具 (Mod 版) | ModGUI .net8.0 |

---

## 1. ALPA (Azur Lane Painting Analysis)

**功能**: 将自定义角色立绘/头像 PNG 图片注入回碧蓝航线 Android 版的 Unity AssetBundle 文件。

**技术栈**: Java + JavaFX 17 + Kotlin + UnityKt

### 使用方法

1. 确保已安装 Java 17+
2. 修改 `alpa.yml` 配置文件中的路径
3. 运行 `launch.bat`

### 配置文件说明 (`alpa.yml`)

```yaml
pngCompressionLevel: 9                    # PNG 压缩级别 (0-9)
assetSystemRoot: '...'                    # 游戏 AssetBundle 根目录
importMainBundlePath: '...'               # 立绘 AssetBundle 路径
painting:
  autoImport: true                        # 是否自动导入立绘
  importImagePath: '...'                  # 自定义立绘图片目录
  imageNamePattern: '*{name}.png;...'     # 图片文件名匹配模式
face:
  autoImport: false                       # 是否自动导入头像
  importBundlePath: '...'                 # 头像 AssetBundle 路径
  importImagePath: '...'                  # 自定义头像图片目录
```

### 目录结构

```
ALPA-1.0.5.1/
├── ALPA-1.0.5.1.jar        # 主程序
├── alpa.yml                # 配置文件
├── launch.bat              # 启动脚本
└── javafx-sdk-17.0.11/     # JavaFX SDK
```

---

## 2. AssetStudio v2.4.1

**功能**: 从 Unity 游戏中提取/预览/导出资源（纹理、模型、音频等）。

**来源**: https://github.com/Razviar/assetstudio

### 支持的 Unity 版本

- Unity 2.x ~ Unity 6 (6000.0 - 6000.4+)
- 完整的纹理解码支持，包括 Unity 2023.2+ 格式变更

### 使用方法

1. 安装 [.NET 8 Desktop Runtime](https://dotnet.microsoft.com/download/dotnet/8.0)
2. 运行 `AssetStudio.GUI.exe` (图形界面) 或 `AssetStudio.CLI.exe` (命令行)

### 功能特性

- **资源浏览**: 实时预览纹理、音频、动画、着色器、网格等
- **资源导出**:
  - 纹理 → PNG/JPEG/BMP/WebP
  - 3D 模型 → FBX
  - 音频 → WAV
- **批量处理**: CLI 模式支持自动化提取
- **着色器反编译**: HLSL 着色器反编译 (DirectX)

### 目录结构

```
AssetStudio-v2.4.1/
├── AssetStudio.GUI.exe        # 图形界面
├── AssetStudio.CLI.exe        # 命令行工具
├── Keys.json                  # 加密密钥库
├── x64/                       # 64 位原生库
├── x86/                       # 32 位原生库
├── runtimes/                  # 跨平台运行时
└── [多语言资源目录]            # cs/de/es/fr/it/ja/ko/pl/pt-BR/ru/tr/zh-Hans/zh-Hant
```

---

## 3. AssetStudioModGUI (旧版)

**功能**: 同 AssetStudio，但包含额外的加密密钥支持。

**来源**: aelurum 的 ModGUI fork

### 与 v2.4.1 的区别

| 方面 | ModGUI (旧) | v2.4.1 (新) |
|------|-------------|-------------|
| 维护状态 | 已停止更新 | 活跃维护 |
| Unity 支持 | Unity 2.x ~ 2022 | Unity 2.x ~ Unity 6 |
| 导出格式 | PNG | PNG/JPEG/BMP/WebP |
| CLI 模式 | 无 | 有 |
| 着色器反编译 | 有限 | 完整 HLSL 反编译 |
| 多语言 | 部分 | 13 种语言 |

---

## 4. 为什么 AssetStudioModGUI.net8.0 文件比 _net8_win64 多？

**核心原因**: `_net8_win64` 是**精简裁剪版**，不是"更新版"。

### `.net8.0` 版 (完整版) 包含:

- GUI + CLI 两个可执行程序
- 13 种语言的本地化资源
- x64/x86/ARM64 多平台原生库
- HLSL 着色器反编译工具
- Keys.json 加密密钥库 (23 款游戏)
- MessagePack 序列化库
- Linux/macOS 跨平台 GLFW 库

### `_net8_win64` 版 (精简版) 移除了:

- CLI 命令行版本
- 所有本地化资源
- x86/ARM64/Linux/macOS 平台库
- 着色器反编译、DirectX 组件
- Keys.json、MessagePack 等非必需依赖

---

## 5. 推荐使用流程

```
1. 使用 AssetStudio 提取游戏资源
   └── AssetStudio.GUI.exe → File → Load → 选择 AssetBundle 文件
   └── 导出纹理/模型到本地目录

2. 使用 ALPA 注入自定义资源
   └── 修改 alpa.yml 配置路径
   └── 运行 launch.bat
   └── 导入自定义立绘/头像

3. 将修改后的 AssetBundle 放回游戏目录
```

---

## 6. 下载链接

| 工具 | 下载地址 |
|------|---------|
| ALPA v1.0.5.1 | https://github.com/Deficuet/AzurLanePaintingAnalysis-Kt/releases/download/v1.0.5.1/ALPA-1.0.5.1.7z |
| AssetStudio v2.4.1 (.NET 8) | https://github.com/Razviar/assetstudio/releases/download/v2.4.1/AssetStudio-net8.0-win.zip |
| AssetStudio v2.4.1 (.NET 10) | https://github.com/Razviar/assetstudio/releases/download/v2.4.1/AssetStudio-net10.0-win.zip |
| .NET 8 Runtime | https://dotnet.microsoft.com/download/dotnet/8.0 |

---

## 更新日志

### ALPA
- **v1.0.5.1** (2026-06-14): 修复 TextureDecoder.dll 编译问题
- **v1.0.5** (2026-05-24): 尝试修复 #28，优化 README
- **v1.0.3** (2024-11-10): 修复 #19
- **v1.0.2** (2024-06-02): 修复报错问题 (当前旧版)

### AssetStudio
- **v2.4.1** (2025-11-27): 最新稳定版
- **v2.4.0** (2025-11-27): 支持 Unity 6，新增 WebP 导出
