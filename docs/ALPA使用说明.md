# ALPA 使用说明（GUI 图形界面版）

> **ALPA** (Azur Lane Painting Analysis) 是碧蓝航线立绘分析工具：直接读取游戏的 painting 资产包，**按官方布局实时合成预览**，并可将合成结果**导出为 PNG**，也支持把自定义立绘注入回游戏。
>
> 本项目的主要用途：**导出官方合成的立绘作为「标准答案」**，用于验收我们自己的合成脚本（`scripts/compose_paintings.py`）。

---

## 一、启动

双击：`tools/ALPA-1.0.5.1/launch.bat`

前提：已安装 Java 17+（本项目电脑已装，`java -version` 可验证）。
界面是 JavaFX 图形窗口，**所有路径都可以在界面里点「浏览...」选择，不需要手动改 alpa.yml**（界面设置会自动持久化回 alpa.yml）。

---

## 二、界面说明

```
┌─ 设置 ──────────────────────────────────────────────┐
│ 保存图片压缩等级(0-9)   ← 导出 PNG 的压缩级别，保持 9     │
│ 立绘根目录        [路径] [浏览...]   ← painting 目录     │
│ 素材文件根目录     [路径] [浏览...]   ← AssetBundles 目录  │
│ 差分表情根目录     [路径] [浏览...]   ← paintingface 目录  │
│ 自动导入: ☑立绘 ☑差分表情文件（注入功能用的，导出可不管）  │
├─ 分析文件 ──────────┐  ┌─ 总体预览 ──────────────────┐
│ [导入文件]           │  │                            │
│ 当前任务: 空闲中      │  │   合成立绘显示在这里         │
│ 依赖项列表           │  │                            │
├─ 导入图像 ──────────┤  └────────────────────────────┘
│ （注入自定义图用，     │
│   导出用不到）        │
├─ [保存] [为所有表情保存] [打开保存文件夹] ──────────────┘
```

### 三个路径分别填什么（本项目实际路径）

| 界面字段 | 填什么 | 本项目路径 |
|---|---|---|
| **立绘根目录** | AssetBundles 下的 `painting` 目录 | `D:\Azur Lane Assets\files\AssetBundles\painting` |
| **素材文件根目录** | **AssetBundles 总目录**（用于解析 bundle 之间的依赖） | `D:\Azur Lane Assets\files\AssetBundles` |
| **差分表情根目录** | AssetBundles 下的 `paintingface` 目录 | `D:\Azur Lane Assets\files\AssetBundles\paintingface` |

> ⚠️ 三个路径任一不对，点「导入文件」后会报红字 **「目标文件夹不存在」**。

---

## 三、快速上手：导出一张立绘（完整点击流程）

1. **设置三个路径**（见上表，各点一次「浏览...」选中对应文件夹）
2. 点 **「导入文件」**
3. 在文件选择框里进入 `painting` 目录，选一个**无后缀的资源包文件**
   - 例如：`painting\chicheng_4`、`painting\kewei_6`（文件没有扩展名是正常的）
4. 等待「当前任务」从 *导入中* 变回 *空闲中*，「依赖项」列表会列出它引用的 `*_tex` 包
   - 如果报 `DependencyMissing`，检查「素材文件根目录」是否填的是 AssetBundles 总目录
5. 右侧 **「总体预览」** 会显示官方布局合成的完整立绘 —— **这就是正确答案**
6. 点 **「保存」** → 立绘导出为 PNG（压缩等级用「设置」里的值）
7. 点 **「打开保存文件夹」** 找到导出的图片

表情差分（脸图）：导入的皮肤如有表情包，「为所有表情保存」可一次导出全部表情版本。

---

## 四、批量导出的现状

- 「导入文件」一次处理**一个**皮肤；逐个导 4300+ 张不现实
- **适用场景**：只导出关键样本/问题皮肤当验收基准（如 `chicheng_4`、`kewei_6`、`bulvxieer_3`、`zhaohe_4`…）
- 是否支持多选/文件夹拖放待实测；若要全量真值，更现实的路线是把 ALPA 的定位算法（jar 内 `PaintingTransform` / `TextureTransform` / `ExtendedTransform` 类）移植进我们的 Python 批量脚本

---

## 五、导出结果怎么用（本项目工作流）

```
ALPA 导出的 PNG（官方效果）
        │  逐张对比（像素差/NCC）
        ▼
我们 compose_paintings.py 的输出
        │
        ├─ 一致 → 该皮肤合成正确 ✅
        └─ 不一致 → 差异就是明确的待修项（背景大小/位置/翻转/遮挡）
```

建议导出后统一放到 `Output/refs/`（与合成输出同名，如 `chicheng_4.png`），方便写脚本自动比对。

---

## 六、注入自定义立绘（进阶，导出用不到）

ALPA 原本的核心功能是把自定义立绘**替换进游戏**：

1. 准备自定义 PNG，命名符合：`{角色名}.png` / `{角色名}_dec.png` / `{角色名}_group.png` / `{角色名}_exp.png`
2. 「导入图像」区 → 「添加图像」加入图片
3. 点「保存」→ 会生成修改后的 bundle → 放回手机覆盖原文件即可在游戏里看到自定义立绘

> ⚠️ 注入会**改写 AssetBundles 源文件**！本项目里务必别点「保存」时误选覆盖 `files/` 下的原始包；注入实验请复制一份到别的目录再操作。

---

## 七、alpa.yml 和界面是什么关系

`alpa.yml` 就是界面里那些设置的**持久化存储**。界面里点「浏览...」选完路径后，配置会写回 yml。
手动编辑 yml 也可以（等价），但推荐直接用界面。

字段对应关系：

| yml 字段 | 界面字段 |
|---|---|
| `importMainBundlePath` | 立绘根目录 |
| `assetSystemRoot` | 素材文件根目录 |
| `face.importBundlePath` | 差分表情根目录 |
| `pngCompressionLevel` | 保存图片压缩等级 |
| `painting.importImagePath` | 「添加图像」的图片来源目录（注入用） |

---

## 八、ALPA 和 AssetStudio 的关系

| | ALPA | AssetStudio |
|---|---|---|
| 本质 | 立绘**专用**分析/预览/导出/注入工具 | Unity 资产**通用**浏览器/提取器 |
| 内部也解析 Unity bundle？ | ✅（内置 UnityKt，不需要 AssetStudio 配合） | — |
| 能看什么 | 仅 painting / paintingface（立绘） | 任何 bundle：纹理、网格、音频、TextAsset… |
| 能按官方布局合成完整立绘？ | ✅（这就是它的预览） | ❌ 只能看单个纹理/网格 |
| 本项目用途 | 出「标准答案」对照验收 | 手动查包、导原始资源、交叉验证 |

结论：**在立绘这件事上 ALPA 自带解析，不需要 AssetStudio 参与**；但看音频/Live2D/其他类型资产时仍然用 AssetStudio。

---

## 九、常见问题

### Q1: 点「导入文件」后报红字「目标文件夹不存在」
三个根目录至少有一个没设或指向了不存在的旧路径。按第二节表格重设三个路径。

### Q2: 依赖项出现 DependencyMissing
「素材文件根目录」必须填 **AssetBundles 总目录**（不是 painting 子目录），否则找不到依赖的 `*_tex` 包。

### Q3: 双击 launch.bat 一闪而过
Java 未安装或未加入 PATH。命令行运行 `java -version` 验证。

### Q4: 预览显示 "Preview not available"
还没成功导入文件，或导入失败。看「当前任务」与「依赖项」的状态。

### Q5: 导出的图和游戏里不完全一样？
个别皮肤游戏运行时会动态调整布局（这正是我们项目踩坑的根源）。ALPA 用的是静态 prefab + 官方算法，绝大多数皮肤与游戏一致；发现不一致的皮肤本身就是有价值的研究样本。

---

## 十、相关链接

- ALPA 项目（Deficuet/AzurLanePaintingAnalysis-Kt）：https://github.com/Deficuet/AzurLanePaintingAnalysis-Kt
- Java 下载：https://adoptium.net/temurin/releases/?version=17
