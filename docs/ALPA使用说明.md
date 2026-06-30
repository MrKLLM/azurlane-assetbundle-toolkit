# ALPA 使用说明（傻瓜式教程）

> **ALPA** (Azur Lane Painting Analysis) 是碧蓝航线立绘/头像注入工具，可以将自定义立绘图片注入到游戏的 AssetBundle 文件中。

---

## 一、安装 Java（必须）

ALPA 是用 Java 编写的，需要先安装 Java 才能运行。

### 方法一：直接下载（推荐）

1. **下载地址**：
   - https://adoptium.net/temurin/releases/?version=17&os=windows&arch=x64&package=jdk
   - 点击页面上蓝色的 **`.msi`** 下载按钮

2. **安装步骤**：
   - 双击下载好的 `.msi` 文件
   - 一路点 **Next**
   - **最重要的一步**：在安装向导中找到 **"Add to PATH"** 选项，**一定要勾选**！
   - 点击 **Install** 完成安装

3. **验证安装**：
   - 按 `Win + R`，输入 `cmd`，回车
   - 在弹出的黑色窗口中输入：
   ```
   java -version
   ```
   - 如果显示类似 `openjdk version "17.0.19"` 的信息，说明安装成功

### 方法二：让 AI 帮你装

如果你懒得自己装，可以让我帮你装（就像刚才那样）。

---

## 二、ALPA 文件说明

下载并解压 ALPA 后，你会看到以下文件：

```
ALPA-1.0.5.1/
├── ALPA-1.0.5.1.jar    ← 主程序（不要删除！）
├── alpa.yml            ← 配置文件（需要修改这个！）
├── launch.bat          ← 启动脚本（双击运行）
└── javafx-sdk-17.0.11/ ← JavaFX 运行库（不要删除！）
```

---

## 三、配置 alpa.yml（最关键的一步）

用记事本或任意文本编辑器打开 `alpa.yml`，按下面的说明修改：

```yaml
# PNG 压缩级别（0-9），数字越大文件越小，建议保持 9
pngCompressionLevel: 9

# 【重要】游戏 AssetBundle 根目录
# 这是你手机上碧蓝航线游戏的资源文件夹
# 通常路径是：手机存储/Android/data/com.bilibili.azurlane/files/AssetBundles
# 你需要先把游戏资源从手机复制到电脑上
assetSystemRoot: 'D:\sdcard\Android\data\com.bilibili.azurlane\files\AssetBundles'

# 【重要】立绘 AssetBundle 路径
# 在上面路径的基础上加上 \painting
importMainBundlePath: 'D:\sdcard\Android\data\com.bilibili.azurlane\files\AssetBundles\painting'

# 立绘注入设置
painting:
  autoImport: true                    # 是否自动导入立绘（保持 true）
  importImagePath: 'D:\我的立绘图片'  # 【重要】你的自定义立绘图片放在哪里
  imageNamePattern: '*{name}.png;*{name}_dec.png;*{name}_group.png;*{name}_exp.png'

# 头像注入设置
face:
  autoImport: false                   # 是否自动导入头像（先设为 false，需要时改成 true）
  importBundlePath: 'D:\...\paintingface'  # 头像 AssetBundle 路径
  bundleNamePattern: '{name}'
  importImagePath: 'D:\我的头像图片'  # 你的自定义头像图片放在哪里
  imageNamePattern: '?.png'
```

### 路径设置说明

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `assetSystemRoot` | 游戏资源根目录 | `D:\游戏资源\AssetBundles` |
| `importMainBundlePath` | 立绘资源目录 | `D:\游戏资源\AssetBundles\painting` |
| `importImagePath` (painting) | 你的自定义立绘图片目录 | `D:\我的立绘\花园` |
| `importImagePath` (face) | 你的自定义头像图片目录 | `D:\我的头像\花园` |

### 注意事项

1. **路径要用单引号包裹**：`'D:\path\to\folder'`
2. **路径中的反斜杠**：Windows 路径使用 `\`，保持原样即可
3. **路径不要有中文空格**：最好用纯英文路径，或者路径中不要有空格

---

## 四、图片命名规则

ALPA 会根据图片文件名匹配对应的角色。图片命名格式：

| 类型 | 命名格式 | 示例 |
|------|----------|------|
| 普通立绘 | `{角色名}.png` | `hanyuan.png` |
| 立绘（解包格式） | `{角色名}_dec.png` | `hanyuan_dec.png` |
| 集体立绘 | `{角色名}_group.png` | `hanyuan_group.png` |
| 特殊立绘 | `{角色名}_exp.png` | `hanyuan_exp.png` |
| 头像 | `?.png` | `0.png`, `1.png` |

> **提示**：`{name}` 是通配符，ALPA 会自动替换成角色文件夹名。

---

## 五、使用步骤

### 第一步：准备游戏资源

1. 手机连接电脑，或者使用文件管理器
2. 找到碧蓝航线的资源文件夹：
   ```
   Android/data/com.bilibili.azurlane/files/AssetBundles/
   ```
3. 把整个 `AssetBundles` 文件夹复制到电脑上（大约 10-20GB）

### 第二步：准备自定义立绘图片

1. 把你的自定义立绘 PNG 图片放到一个文件夹里
2. 图片文件名要符合上面的命名规则
3. 例如：`D:\我的立绘\花园\hanyuan.png`

### 第三步：修改配置文件

1. 打开 `alpa.yml`
2. 修改 `assetSystemRoot` 为你复制到电脑上的 AssetBundles 路径
3. 修改 `importMainBundlePath` 为上面路径 + `\painting`
4. 修改 `painting.importImagePath` 为你的自定义立绘图片目录
5. 保存文件

### 第四步：运行 ALPA

1. 双击 `launch.bat`
2. 等待 ALPA 启动（可能需要几秒到十几秒）
3. ALPA 界面会显示出来

### 第五步：注入立绘

1. 在 ALPA 界面中，选择你要注入的角色
2. 点击 **"注入"** 按钮
3. 等待处理完成
4. 修改后的 AssetBundle 文件会覆盖原文件

### 第六步：将修改后的文件放回手机

1. 把修改后的 `painting` 文件夹（或整个 AssetBundles 文件夹）复制回手机
2. 覆盖原来的文件
3. 启动游戏，查看效果

---

## 六、常见问题

### Q1: 双击 launch.bat 后一闪而过？

**原因**：Java 没有正确安装或没有添加到 PATH。

**解决**：
1. 按 `Win + R`，输入 `cmd`，回车
2. 输入 `java -version`，看看有没有反应
3. 如果没有，说明 Java 没装好，重新安装并确保勾选了 "Add to PATH"

### Q2: 提示 "'java' 不是内部或外部命令"？

**原因**：Java 没有添加到系统 PATH。

**解决**：
1. 重新安装 Java，在安装向导中勾选 **"Add to PATH"**
2. 或者手动添加：
   - 右键点击"此电脑" → 属性 → 高级系统设置 → 环境变量
   - 在"用户变量"中找到 `Path`，点击编辑
   - 点击"新建"，添加 Java 的 bin 目录路径，例如：
     ```
     C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot\bin
     ```
   - 重启 cmd 窗口

### Q3: ALPA 启动后报错 "Could not find or load main class"？

**原因**：`alpa.yml` 路径配置错误。

**解决**：
1. 检查 `assetSystemRoot` 路径是否正确
2. 检查 `importMainBundlePath` 路径是否正确
3. 确保路径用单引号包裹
4. 确保路径存在且可访问

### Q4: 注入后游戏闪退？

**原因**：可能是文件损坏或版本不匹配。

**解决**：
1. 确保使用的是最新版本的 ALPA (v1.0.5.1)
2. 确保游戏资源是最新的
3. 重新复制一份干净的游戏资源再试

### Q5: 如何恢复原版立绘？

**解决**：
1. 只要你保留了原始的 AssetBundles 文件夹备份
2. 把备份的文件覆盖回去即可

---

## 七、进阶用法

### 批量注入多个角色

在 `importImagePath` 指向的文件夹中放入多个角色的立绘图片：
```
D:\我的立绘\
├── hanyuan.png
├── haiyan.png
├── linbo.png
└── ...
```

ALPA 会自动匹配所有图片并注入。

### 同时注入立绘和头像

1. 把 `face.autoImport` 改为 `true`
2. 设置好 `face.importBundlePath` 和 `face.importImagePath`
3. 运行 ALPA 时会同时注入立绘和头像

---

## 八、技术说明（可跳过）

ALPA 使用以下技术：
- **Java 17+**：运行环境
- **JavaFX 17**：图形界面框架
- **Kotlin**：主要编程语言
- **UnityKt**：Unity 资产处理库

注入原理：
1. 读取原始 AssetBundle 文件
2. 解析 Unity 资产结构
3. 用自定义 PNG 图片替换原始纹理
4. 重新打包 AssetBundle
5. 覆盖原文件

---

## 九、相关资源

- **ALPA 下载**：https://github.com/Deficuet/AzurLanePaintingAnalysis-Kt/releases
- **Java 下载**：https://adoptium.net/temurin/releases/?version=17
- **碧蓝航线 Wiki**：https://wiki.biligame.com/azurlane/

---

> **最后提醒**：修改游戏文件有风险，建议先备份原始文件！
