# AssetStudio 使用说明

> **AssetStudio** 是 Unity 资产提取/预览/导出工具，支持从碧蓝航线的 AssetBundle 中提取纹理、模型、音频等资源。

---

## 一、你有三个版本

| 版本 | 路径 | 特点 | 推荐用途 |
|------|------|------|----------|
| **v2.4.1** | `tools/AssetStudio-v2.4.1/` | 最新完整版，支持 Unity 2~6，13 种语言 | **主力工具** |
| **ModGUI.net8.0** | `tools/AssetStudioModGUI.net8.0/` | Mod 版，含加密密钥库 | 需要 Keys.json 时使用 |
| **ModGUI_net8_win64** | `tools/AssetStudioModGUI_net8_win64/` | 精简版，体积小 | 快速查看，不需要 CLI |

**简单说**：日常用 **v2.4.1**，它有 GUI 和 CLI 两种模式。

---

## 二、前提条件

需要安装 **.NET 8 Desktop Runtime**（或 .NET 10）：

1. 下载地址：https://dotnet.microsoft.com/download/dotnet/8.0
2. 选择 **.NET Desktop Runtime 8.0.x** → Windows x64
3. 下载安装即可

验证：
```powershell
dotnet --list-runtimes
# 应看到 Microsoft.NETCore.App 8.0.x 和 Microsoft.WindowsDesktop.App 8.0.x
```

---

## 三、GUI 模式（图形界面）

### 启动

```
双击 tools/AssetStudio-v2.4.1/AssetStudio.GUI.exe
```

### 基本操作

1. **加载文件**：`File` → `Load File`（单个文件）或 `Load Folder`（整个目录）
2. **浏览资源**：左侧面板按类型分类（Texture2D、Mesh、AudioClip 等）
3. **预览**：点击资源项，右侧显示预览
4. **导出**：
   - 右键单个资源 → `Export selected items`
   - 或 `Export` → `All assets` 导出全部

### 导出格式

| 资源类型 | 导出格式 | 说明 |
|----------|----------|------|
| Texture2D | PNG/JPEG/BMP/WebP | 纹理图片 |
| Mesh | FBX | 3D 模型 |
| AudioClip | WAV | 音频 |
| Shader | — | 着色器（不可直接导出） |
| TextAsset | 原始文件 | 文本/二进制 |

### 常用操作示例

**导出某个角色的所有资源**：
1. `File` → `Load File` → 选择 `painting/haifusi` 文件
2. 左侧筛选器选 `Texture2D`
3. `Export` → `Selected assets`
4. 选择输出目录

**批量导出整个 painting 目录**：
1. `File` → `Load Folder` → 选择 `files/AssetBundles/painting/`
2. 等待加载完成（可能需要几分钟）
3. `Export` → `All assets`
4. 选择 `Output/Raw/painting/`

---

## 四、CLI 模式（命令行）

CLI 模式适合批量处理和脚本集成。

### 基本用法

```powershell
# 导出单个文件的所有资源
.\AssetStudio.CLI.exe 输出目录 输入文件

# 示例
.\AssetStudio.CLI.exe "D:\Output\test" "D:\Azur Lane Assets\files\AssetBundles\painting\haifusi"
```

### 批量导出

```powershell
# 导出整个目录
$files = Get-ChildItem "D:\Azur Lane Assets\files\AssetBundles\painting\*" -File
foreach ($f in $files) {
    $outDir = "D:\Azur Lane Assets\Output\Raw\painting\$($f.Name)"
    .\AssetStudio.CLI.exe $outDir $f.FullName
}
```

### 在脚本中调用

```python
import subprocess

ASSETSTUDIO_CLI = r"D:\Azur Lane Assets\tools\AssetStudio-v2.4.1\AssetStudio.CLI.exe"

result = subprocess.run(
    [ASSETSTUDIO_CLI, output_dir, input_file],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"导出失败: {result.stderr}")
```

---

## 五、三个版本的区别

### v2.4.1（推荐）

- GUI + CLI 双模式
- 支持 Unity 2.x ~ Unity 6（6000.0+）
- 13 种语言界面
- HLSL 着色器反编译
- 多格式导出（PNG/JPEG/BMP/WebP/FBX/WAV）
- x64/x86/ARM64 多平台支持

### ModGUI.net8.0

- 与 v2.4.1 类似，基于 .NET 8
- 包含 **Keys.json** 加密密钥库（23 款游戏的密钥）
- 包含 MessagePack 序列化库
- 适合需要解密的场景

### ModGUI_net8_win64（精简版）

- 只有 GUI，没有 CLI
- 移除了本地化资源、着色器反编译、跨平台库
- 体积最小，启动最快
- 适合快速预览

---

## 六、常见问题

### Q1: 启动报错 "Could not find framework"

**原因**：未安装 .NET 8 Desktop Runtime

**解决**：安装 .NET 8 Desktop Runtime（见"前提条件"）

### Q2: 加载文件后看不到内容

**原因**：可能是加密的 AssetBundle

**解决**：
1. 尝试用 ModGUI.net8.0 版本（含 Keys.json）
2. 或先用 ALPA 解密后再导入

### Q3: 导出的纹理是黑的

**原因**：纹理格式不支持或 GPU 解码失败

**解决**：
1. 在设置中切换解码方式
2. 尝试导出为不同格式（WebP 通常更可靠）

### Q4: CLI 模式导出为空

**原因**：输出目录权限问题或文件路径包含中文

**解决**：
1. 确保输出目录存在且可写
2. 路径中避免中文和空格
3. 用引号包裹路径：`"D:\path with spaces"`

### Q5: 导出的 FBX 模型没有贴图

**原因**：AssetStudio 默认导出 FBX 时不包含贴图路径

**解决**：
1. 先导出 Texture2D 为 PNG
2. 再导出 Mesh 为 FBX
3. 在 Blender 中手动关联贴图

---

## 七、与本项目的配合

### 导出立绘

```powershell
# 用 CLI 批量导出 painting 目录
cd "D:\Azur Lane Assets\tools\AssetStudio-v2.4.1"
.\AssetStudio.CLI.exe "D:\Azur Lane Assets\Output\Raw\painting" "D:\Azur Lane Assets\files\AssetBundles\painting"
```

### 预览 Live2D 模型

1. 打开 GUI
2. `File` → `Load File` → 选择 `Output/Live2D/lingbo/lingbo.moc3` 同目录下的 bundle 文件
3. 在 Texture2D 分类下查看贴图

### 调试导出问题

当 UnityPy 导出失败时，用 AssetStudio 对比：
1. 用 AssetStudio 打开同一个 bundle
2. 检查资源是否能正常显示
3. 对比两种工具的导出结果

---

## 八、快捷参考

```powershell
# 验证安装
tools\AssetStudio-v2.4.1\AssetStudio.GUI.exe --help

# CLI 导出单文件
tools\AssetStudio-v2.4.1\AssetStudio.CLI.exe <输出目录> <输入文件>

# CLI 批量导出
tools\AssetStudio-v2.4.1\AssetStudio.CLI.exe <输出目录> <输入目录>
```
