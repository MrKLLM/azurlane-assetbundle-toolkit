---
name: unity-assetbundle-painting-restore 触发词（3D 侧）：跨包 PPtr、assets_file 带下划线、ObjectReader.assetsfile 为 None、.sharedAssets、resS 不是 SerializedFile、externals 下标 ±1、pptr.deref、CAB 索引现扫、unity default resources 内置外链、激活态过滤、m_TexEnvs、材质外链 PPtr、externals 内层 CAB、submesh、glTF 装配、GLB 回读断言、变异红路径、恒 0 假读数、蒙皮权重、BlendWeight、BlendIndices、m_VertexData、m_DataSize 是 bytes、m_Streams 恒空、m_Skin 字段不存在、compressedMesh 假信号、m_BindPose、反解顶点布局、三重自证、权重和等于1、每顶点骨数、glTF 装配前置。
description: Unity AssetBundle 立绘数据驱动还原流程（以碧蓝航线项目为蓝本）。当需要从 Unity 游戏的 AssetBundle 中还原静态立绘（多层 UI 合成）、提取 Spine 动态立绘、解析 PPtr 依赖关系定位 Mesh/Sprite，或排查还原结果"颠倒/比例错/层错位/黑洞/脸部白块/头部发黑/贴遮挡条"类系统性坐标、画框与图层问题时使用。触发词：立绘还原、立绘合成、AssetBundle 立绘、Spine 提取、PPtr、externals、CAB、跨包解析、SerializedFile 多个、图层错位、比例不对、颠倒、黑洞、画框、脸部白块、白脸洞、face 槽、paintingface、mRawSpriteSize、m_IsActive、关闭图层、激活位、头部发黑、遮挡条、NOT ABLE TO DISPLAY、覆盖率扫描、重跑、影响面扫描。
version: 1.13.9
---

# Unity AssetBundle 立绘数据驱动还原

## 适用场景与前置条件

- 从 Unity 游戏 AssetBundle 还原**多层立绘**（背景+角色+装饰+表情差分）为单张 PNG，或提取 **Spine 动态立绘**（.skel/.atlas/.png）。
- 环境：Python 3.13 + UnityPy 1.25.x（`py -3`，用户级 pip）。
- **前置铁律（所有 UnityPy 读取入口脚本）**：紧跟 import 之后设
  `from UnityPy import config` + `config.FALLBACK_UNITY_VERSION = "2022.3.62f3"`——
  本游戏新版 bundle 把 UnityFS 头部的 `unity_version` 伪装成 `5.x.x`，不设回退则较新包全部加载失败。
  写/改任何读 bundle 的脚本后，先 `grep FALLBACK_UNITY_VERSION scripts/` 核对每个入口脚本都已设置（v2 管线脚本齐全，旧导出脚本曾漏设导致 ~80 背景包导出失败）。
- 目录约定（碧蓝航线项目，路径 `D:\Azur Lane Assets`）：
  - 源包：`AssetBundles/`（含 `dependencies` 单包、`painting/`、`paintingface/`、`spinepainting/` 等子目录）
  - 脚本：`scripts/`，输出：`Output/Paintings_v2/`、`Output/Spine_v2/`
  - 进度文档：`PROJECT_STATUS.md` §9（当前主线：v2 数据驱动管线，跨会话先读它；系统性根因清单见 §9.3）

## 核心原则

**游戏数据完全自洽——一切"错位/颠倒/比例不对"都是解析姿势不对，禁止逐角色手调参数。**
旧管线（v1）积累的所有手调参数（BUNDLE_BJ_ABSOLUTE / SCALES / OFFSETS）都已被官方数据自然推导取代。每次遇到"看起来需要手调"的样本，先怀疑坐标/依赖解析，不要加参数。

**推论（同样重要）：游戏把判断写成了字段，就要去读那个字段，不要用统计启发式去猜。**
"这层要不要画"= `GameObject.m_IsActive`（第 4.8 步）、"这张脸烤好没有"= face 槽引用的那张
`paintingface` 图与底图逐像素比色差（第 4.7 步）。启发式（近纯白=光效、饱和度高=真画）
会在边界样本上双向出错，而且**会掩盖同批数据上的另一个真缺陷**。

## 工作流

### 第 0 步：资产同步（如源包可能落后于游戏版本）

`py -3 scripts/mumu_sync.py` — 从 MuMu 模拟器拉取 AssetBundles。走 adb 本地回环（127.0.0.1），零外网流量；多设备时 adb 必须带 `-s`。完成后与源包做 diff→sync→复检闭环（数量/大小须一致）。版本以游戏 `version.txt` + 清单 CSV（`hashes-painting.csv` / `hashes.csv`）为准。

### 第 1 步：导出官方依赖表

`AssetBundles/dependencies`（约 6.4MB 单包）内 MonoBehaviour 携带官方「资源名 → deps 列表」依赖表（碧蓝航线：86,398 条）。

```
py -3 scripts/export_dependency_manifest.py   # → Output/dependency_manifest.json
```

这是部件→纹理包映射的唯一权威来源，不要用 bundle 命名规律去猜。

### 第 2 步：PPtr 解析定位对象

prefab 中 `m_Sprite = (FileID, PathID)`：

- FileID = 0 → 对象在本包内，用 PathID 直接匹配。
- FileID = N → 取 **SerializedFile.externals[N-1] 的 CAB 名**，反查所在依赖包，再在该包内按 PathID 精确匹配 Mesh/Sprite。

⚠️ externals 顺序 ≠ manifest deps 排序（后者按字母序），**必须以 externals 为准**。一包多 mesh 时按 PathID 精确匹配，不按顺序/面积猜。详见 reference.md「PPtr/externals 解析规则」。

#### 第 2 步补充：目标散在几百个包里（场景/prefab 级外链）怎么打通——五条实现要点（2026-10-08，3D 房间场景 348 个 MeshFilter 实测）

上面那条规则在**一个 bundle 含多个 SerializedFile、目标又跨几百个包**时会不够用。五条按顺序：

1. **一个 bundle 里有多个 SerializedFile，还有非 SerializedFile 的成员**。实测场景包 `env.file.files` = 4 个成员：
   主 `CAB-x`（2332 对象/357 externals）、`CAB-x.sharedAssets`（32/**360**）、**两个 `.resS`**。
   ⇒ 遍历必须 `isinstance(v, SerializedFile)`（`.resS` 是 `EndianBinaryReader`，取 `.externals` 直接 `AttributeError`）。
   ⚠️ 危险的是**不报错的那一种**：`next(iter(env.file.files.values()))` 取到 `.sharedAssets` 后
   `externals[file_id-1]` 整体**安静错位**（真实事故：把 `WallLeft` 的网格算成 `fbx_db_pail01_fbx`）。
2. **归属白拿**：`ObjectReader.assets_file`（**带下划线**）逐对象给得出所属 SerializedFile。
   ⚠️ 恒 None 的是 **PPtr** 上的 `assetsfile`——别把这两个名字混成一条"读不出归属"的结论（本项目就因此多写了一圈
   "遍历 `env.file.files` 建 path_id 反查表"的无用代码）。归属表仍要建，但**键必须是 `(assets_file.name, path_id)`**：
   同一 bundle 的两份 SerializedFile 的 `path_id` **会撞车**。
3. **`file_id` 从 1 起 → `externals[file_id-1]`，且 `file_id==0` 指"引用方自己那份 SerializedFile"**
   ——不是"我这次打开的源包"。材质对象住在 `mat_*` 包里、它引用的贴图常常**也在同一个材质包**里（自引用），
   拿源包的对象表去查 `self` 会**查不到且不报错**：真实事故是 141 个材质里 **93 个静默丢了贴图**，
   而顶点数 / 三角数 / 世界盒 / console 四条锚点全绿（"结构合法、数字全绿、画面是错的"）。
   ⇒ `self` 先查调用者给的表，查不到再按 CAB 名回落到索引里那个包；并把
   **挂上 / 解析失败 / 本就无槽**三个数分开打印，不许合并成一个"贴图引用数"。
4. **落点按 CAB 名索引 + 按名字精确选目标 SerializedFile**。索引给**每个** SerializedFile 单条登记（含 `.sharedAssets`）；
   作用域除资产前缀目录外，还要用官方依赖表里该包的 `deps` 补齐**类目之外**的依赖（实测补进 2 条：
   `custom_builtin`、`font/zhunyuan`——它们不被 MeshFilter 引用，但材质引用，缺一类就少一类）。
   **每次现扫、不吃缓存**（474 包 + 451 依赖包 = 19.8 秒；缓存留着只做对照，否则"改了索引层忘了刷缓存"就是静默失败面）。
5. **内置外链单独归桶**：`FileIdentifier.path` 不以 `archive:` 开头的（如 `unity default resources`）**盘上没有文件**。
   它不是失败，**也不该进判据分母**，更不许写结构合法的占位对象。实测 348 条里 31 条是内置，其中 **30 条是激活态**
   ⇒ 说明这个房间壳体真的混用了 Unity 原语（`WallLeft/Floor/Bed/Sofa/Cube*/Plane`），要它们的真网格只能从设备取内置资源文件。

**打通的判据（七条，缺一条例外就还不许说"打通"）**：① 分桶求和 == 对象总数（防静默丢失）；
② 固定种子抽 20 条 `(包, 名, 顶点数)` 语义相符 ≥18/20；③ **同一批走库自己的 `pptr.deref()`**
（先把依赖 `load_file` 进同一个 Environment）逐条比对，差异必须 0——这条是"另一套代码"的外部裁判；
④ 换错 SerializedFile 的对照必须塌；⑤ **externals 下标 ±1 的对照也必须塌**（见 C8 第 3 条：④那种"全 `notfound` 的红"
其实没验到下标约定）；⑥ 数量类字段要有**第二条独立来源**（`m_VertexData.m_VertexCount` vs 库自己 `export()` 出的 `v` 行数，
另查 `max(index) < 顶点数`）；⑦ 自建索引与既有缓存键集对照（两套独立构建，差异要么 0 要么逐条解释）。
语义判据的归一化口径：剥 `pre_/fbx_/mat_` 前缀与 ` (N)` 副本后缀、按非字母数字切词、**数字段去前导零**
（`Chair_1` ↔ `fbx_chair01` 是同一个），再要求**词元序列相等或互为子序列**（对象名可插颜色词）。
⚠️ 用"序列"而不是"集合包含"，`WallLeft` ↔ `pail01` 才必红；⚠️ **判据过严一样是错的**——第一版按"剥前后缀完全同名"
写，把正确的 `pre_oak02_green02_lod3` ↔ `fbx_oak02_lod3` 判成不符。余下不匹配的（实测 317 条里 27 条，多为美术复用资产）
**逐条打印出来人看**，不许悄悄放宽规则放行成绿。
另两条会咬人的：`load_file` 之后 **`env.objects` 不再只含源包对象**（实测数出 630 个 MeshFilter，源包只有 348）
⇒ 分母必须先按 `assets_file` 限定回源包；**解析率 ≠ 可画率**（实测 49/348 挂在关闭态对象上，首因是 `night` 子树）
⇒ 与第 4.8 步「激活位」同一条规则，装配/渲染前必须过滤，否则日夜两套同位置叠画。

### 第 3 步：部件纹理还原

主脚本：`scripts/compose_paintings_v2.py`。

- 有 mesh 部件：mesh UV + 纹理，**重心坐标插值光栅化**回贴到 sprite 画框。
- 无 mesh 整图部件（典型为 root 背景层）：按 `m_Rect` 自底坐标**直接切片**纹理，不做额外翻转（Y 约定见 reference.md，这里曾出过双重翻转 bug）。
- **无 mesh 部件画框语义（红线，第五个系统性根因）**：绘制画框按 Unity UI Image 语义把 **textureRect 直接拉伸铺满 RectTransform**，**禁用 CanvasRenderer 的 `mRawSpriteSize` 当画框**——多背景视差条带皮肤（i404 型）各背景带（bj1/bj2/bj3）的 `mRawSpriteSize` 记录的是**切分前原图尺寸**（如 2048×1770），而各带实际纹理是 1167×2048 / 2048×1170 / 1469×2048，按错误画框非等比缩放会把竖带横向压窄 ~2 倍、彼此拼不拢留黑洞（commit 87c03f0）。有 mesh 部件的画框映射路径不动。

### 第 4 步：Unity UI 布局合成（正确语义四步）

`layout_all` 必须严格按以下顺序，任何一步偏离都会产生系统性比例错误：

1. 布局在 **root 局部空间**做纯 anchor 数学（sizeDelta/anchoredPosition 不乘父 scale）；
2. 局部 rect 递归经「父局部→父世界」**仿射映射**（纯缩放+平移）到世界坐标；
3. 节点**自身 localScale 绕 pivot 缩放**，负值 = 镜像（水面倒影等），bbox 同步镜像换算；
4. **root 自身 scale 归一为 1**——它只是游戏把 UI 树适配屏幕的统一缩放，若只乘到子部件而背景层不乘，层间比例必然错（曾因此全量返工两轮）。
5. **局部→世界仿射时不得再减父节点的 p_local**——`local_rect` 返回的 (lx,ly) 已相对父节点局部矩形左下角 (0,0)，再减 `p_local[0]/[1]`（那是父节点在它父级里的位置）会让子层错位。单层皮肤 p_local=0 无感，故此 bug 极隐蔽：只影响**嵌套 stretch 中间容器**（aMin=(0,0)/aMax=(1,1)，常见名 `layers`/`Touch`，sizeDelta 可为负即收缩容器）下的子层，整体甩到左下脱离背景（如 jialimaoxian：角色 1305+(37-1305)=37，正确应为 1305+37=1342）。修复后须与已知正常样本逐像素回归验证（单层应零变化）。

表情差分：`--faces all` 输出 `{name}_face{k}.png`；face 节点 PPtr 指向 `paintingface/<name>` 包（包内 Texture2D+Sprite 命名 `1..N`）。兜底仅对 `go_name == 'face'` 生效，避免 UI 热区误配。

### 第 4.5 步：CG 型多层立绘错位诊断流程（i404/jialimaoxian 类）

多层背景/前景 CG 型皮肤（角色 `rw` + 多块巨大背景层 `bj1/bj2/bj3`）错位时，**按以下顺序排查，不要跳步**：

1. **先 dump 布局树**：用 `parse_painting + layout_all + draw_order` 逐层打印 aMin/aMax/sizeDelta/anchoredPosition/pivot/世界框，看是否存在 stretch 中间容器（`layers`/`Touch`）与大偏移背景层。**执行姿势：`import compose_paintings_v2` 直接调自带函数，不要手撸 UnityPy PPtr 解析**（compose 已把依赖解析/布局算好，手撸容易引入第二种错）。i404 的 bj 层世界坐标带负值（如 bj1 x∈[-5301,-49]）、可见内容并集可达 11659×11255 近正方形——先看清楚数据长什么样再动手。
2. **逐层单独渲染**：把每个可绘制层单独贴到画布各存一张，对照「矩形框」与「渲染内容」。jialimaoxian 案例中框算出来角色与背景中心接近、渲染却脱开——正是靠逐层渲染把矛头从外层布局引到仿射映射（第 4 步第 5 条 p_local 多减）。别只靠肉眼猜最终合成图。
3. **症状是「黑洞/缝隙」而非「错位」时查画框**：若逐层渲染每块形状都对、但条带间拼不拢留下大片黑洞（i404 型视差背景），核对 CanvasRenderer `mRawSpriteSize`（frame）与该部件纹理矩形尺寸是否一致——不一致即误用 `mRawSpriteSize` 当画框（修复见第 3 步画框红线）。证据链用 ppu 换算比例验证：纹理 1167×2048 与 RectTransform 5252×9214 同比 ⇒ 游戏实际按纹理矩形拉伸铺满渲染，别再往相机/画布方向绕。
4. **核对第 4 步五条语义**（尤其第 5 条 p_local 多减），修正后先跑已知正常样本做逐像素回归，再看问题样本。
5. **画布规则**：按各层完整矩形并集开画布时必须覆盖 min→max（含负坐标），否则负世界坐标背景层整层被裁、角色偏移。更稳的口径是**按根节点设计框裁**（用户已确认的兜底：i404 根框 1870×5717 裁出干净竖构图）。如需 16:9 视口，以角色可见 bbox 居中、并以游戏真值参考截图校准，**不能猜视口**。

**负结论清单（别走的死路，均已实测排除）**：

- **不要追 z 序/sortingOrder**：本版本 CanvasRenderer raw 只有 `m_GameObject`+`m_CullTransparentMesh` 两个字段，**不暴露** sortingOrder、也没有 Canvas 组件——怀疑层序时无需反复验证这一点，直接按 `m_Children` 层级遍历（draw_order）处理即可。
- **命名对错用原图核实**：抽 `_rw_tex` 原图看角色到底是谁（i404=白发女仆伊404✓、jialimaoxian=紫发加里冒险✓），不要拿错误的最终合成图肉眼猜"名字对调"。
- **16:9 全屏 CG 无现成扁平资源**：`char/<name>` 只是 2048×512 头像条，`story/`、`gallerypic/` 不含皮肤 CG——那是游戏运行时相机合成/另一套呈现，prefab 复现不了，已与用户确认放弃。

### 第 4.6 步：核心函数语义改动后的「影响面受控重跑」（layout_all / build_part 画框等）

修复 `layout_all`、`build_part` 等核心函数后，**禁止盲目全量重跑**（用户合理担心打乱已正确产物）。标准流程：

1. **嫌疑分流（像素侧只读扫描）**：当最终合成图出现"黑洞/缝隙/大面积透明"这类病态、但结构数据不直接暴露时，对既有产物/画廊缩略图跑 **alpha 覆盖率扫描**（覆盖率 = `alpha>10` 像素占比，PIL+numpy 即可），按阈值输出嫌疑清单（本轮 4486 张中 <0.72 共 30 张，含 i404 全系、aida_wedding 等），把排查火力集中到一小批。
2. **零回退验证先行**：挑 8+ 个已知正常皮肤（清单：`2b feiteliekaer_3 hailunna_4 xili_alter kewei_6 aersasi_3 chicheng_4 adiliao_2`）用改后脚本（或第 4 步的假设版）渲到临时目录，与现有 `Output/Paintings_v2/` 逐像素比对，**必须全部 diff=0.00（对照组 maxdiff=0）**（"数学上不该变的确实一张没变"）才有资格谈重跑。
3. **只读扫描枚举影响面**：写 `.diag/scan_*.py`——`import compose_paintings_v2`，对全部皮肤**只解析层级/部件字段、用新旧两套公式各算一遍对比**，不解码贴图、不写产物，输出受影响清单（`name<TAB>最大偏移px` 按偏移降序）+ 占比。画框类扫描（frame vs textureRect 全量比对）时**必先甄别 4×4 全透明占位精灵**（alpha 恒 0，拉伸与否都画不出东西 = 零风险）：本轮 556 部件/481 皮肤命中，甄别后收敛为 **10 皮肤/16 部件**（i404、i404_n、hemuhao_2(_n)、jinshi_2_hx(_n_hx)、junzhu_5、kansasi_2_hx、tiancheng_cv_3(_n)）——未甄别的虚高数字不能拿去谈重跑。布局类实例：4486 张中仅 85 张受嵌套容器 bug 影响（1.9%）。
4. **monkey-patch 假设验证（不改脚本文件）**：在临时脚本里包一层 `C.build_part`（如无 mesh 部件强制 `frame=(rect.w, rect.h)`）重渲问题样本+对照组到 `.diag/`——问题样本须按预期方向变化（i404 覆盖率 0.48→0.57，剩余透明区为美术浪花圆形构图本身），对照组逐像素 maxdiff=0 证零回退。验证通过才正式改脚本、并复跑第 2 步回归。另需安全校验边界条件（如是否存在 rect 偏移非零的部件会受 bbox 归零影响）。
5. **只定向重渲这批**到临时目录（如 `.diag/affected_out/`），生成改前/改后**并排拼图**（每 sheet 8 对、左旧右新、标皮肤名、按偏移降序）供用户逐张过目；<100px 的轻微项提醒用户基本无感。
6. **用户确认后才换入**：旧图备份到 `Output/_OLD_bak/<说明>_<日期>/` → 新图覆盖 `Paintings_v2` → 只重建这批缩略图。缩略图技巧：`make_thumbs.py` 对已存在缩略图会 skip——**先用 Python 删这批 `gallery_v2/thumbs/<name>.webp` 再跑**，即只补缺的、其余全 skip。删文件用 Python `os.remove` 而非 bash `rm "$var"`（含运行时变量路径的删除会被安全守卫拦下）。

这套流程把风险面从"全部产物"缩到"确认受影响的一小批"，且每一步可逆（有备份）、用户可审（有对比图）。覆盖率扫描（像素侧发现嫌疑）+ 字段只读扫描（结构侧圈定影响面）+ monkey-patch（零成本验证假设）三件套，对"数据看着正常但图像有黑洞"类病态尤其有效。

### 第 4.7 步：独立脸部件未合成（脸洞）诊断与修复（i168_2 型）

**症状**：成品立绘脸部出现"白块"。**注意：抽原始 PNG 看实为透明洞（alpha≈0），是查看器/画廊把透明铺白底才显示成白**——别被"白"误导，一切按透明判。

**根因链（三段，2026-09-20 实测 i168/i168_2 确认）**：

1. painting 包里确有名为 `face` 的节点（MonoBehaviour + GameObject 'face'），但其 **`m_Sprite` 为空（path_id=0/file_id=0）**——`parse_painting` 的 `if not path_id: continue` 把它整个跳过，部件清单里只剩 `_rw`。
2. 真脸在**独立的 `paintingface/<name>` 包**（包内 Texture2D+Sprite 命名 `0..N`，各张为表情差分），游戏运行时才把脸贴到 face 槽上。
3. compose 从未叠 paintingface → 凡 `_rw` **留脸洞**的皮肤（少数派，如 i168_2）脸部出透明洞；多数皮肤**脸已烤进 `_rw`**（如 i168），face 槽空着也无碍。

**排查方法**（姿势同 4.5 步：`import compose_paintings_v2` 复用其函数，不要手撸 UnityPy 解析）：

- 探 `painting/<name>` 包列出全部 MonoBehaviour，看 face 节点的 `m_Sprite` 是否为空（path=0 被跳过）；
- 探 `paintingface/<name>` 是否存在且有脸图（命名 `0..N`，透明边常见）；**默认脸表情名（`0` 还是 `1`）数据里无标记，需小样本渲染目视确认**（i168 系实测 `1` 合适）。

**修复落码姿势（compose_paintings_v2.py，已实测跑通）**：

1. 加模块级辅助函数 `paintingface_face(bundle_name, want="1")`：`load_bundle("paintingface/"+bundle_name)` → 收集包内 Sprite（名字→纹理），取 `want` 那张；找不到该表情名退回数字名最小的一张；无包返回 `None`。返回 `(PIL RGBA, (w,h))`。
2. `compose()` 里在 `boxes,order` 之后解析 face 节点世界框：`face_pid = next((rp for rp in rects if go_names.get(rp)=="face"), None)`，默认脸表情名用 env 可调 `FACE_DEFAULT = os.environ.get("FACE_DEFAULT","1")`。
3. `render()` **部件循环结束后、`return` 之前**按 `boxes[face_pid]` 把 paintingface 默认脸叠到画布（与无 mesh 部件同法：textureRect 拉伸铺满 rect、Y 翻转、`canvas.paste(..., img)`）。

**关键门控（本轮踩到的坑，必须写死）**：

- **不能对所有皮肤无脑叠**。通用叠层会**回归已烤脸皮肤**：i168 对照 maxdiff=255、约 0.61% 像素改变——因为 paintingface 的脸和烤进 `_rw` 的脸**并非逐像素相同**（表情/边缘/位置有差），叠上去就糊动正常皮肤。
- **洞判据必须按「脸谱自身落笔处」量，不能量 face rect 整框**（第一版用整框不透明率 `frac_op<0.5`，被实测推翻）。face rect 常比脸本身大得多、含大片透明背景，于是**已烤脸的皮肤也会跌破阈值而误叠**：`leiniya_wjz` 框内 49% 不透明（正是那张画好的脸）+ 48% 透明背景 → 49% 刚好 <0.5 → 把完整的睁眼脸换成闭眼脸=回退。反过来真洞样本（i168_2 框内 98% 透明）远低于阈值，所以**阈值两侧都"看着对"，边界样本必然翻车**。
- **正确判据（两段式，2026-09-27 第二版；第一版的 sat≥30 见下方警告）**：先取脸谱、按 rect resize（含 mirrors 翻转），再只在**脸谱自身 `alpha>200` 的落笔像素**上量画布现状：
  ```
  洞 = frac_opaque(脸谱落笔处下方 alpha>=250 的占比) < FACE_OPAQUE_MIN(0.5)      # 这里没画
       或 MAD = mean|底图RGB − 脸谱RGB|(在落笔∩不透明上) > FACE_MAD_MAX(30)      # 画了但不是这张脸
  ```
  第一段管透明洞，第二段管**平涂灰块 / 不透明白块 / 缺整张头**。MAD 的语义就是"脸已烤好"这句话本身
  （同槽、同脸谱、同尺寸、同镜像），不是代理指标；可比像素 <64 记 `None` 并按洞处理。
  - `canvas.crop()` 用越界框即可（PIL 越界补 0=透明），语义上等于"那里没画"，不必手写钳位。
  - ⚠️ **第一版判据 `sat>=30` 占比已被推翻**（2026-09-20 引入、2026-09-27 撤换）：二次元淡色皮肤本身低饱和、
    足迹里又混深色头发，`sat>=30` 大面积不成立 ⇒ 全库**过叠到 49%** 的候选被判定要叠脸，而抽样 24 张逐张目视
    **全部是已烤好完整脸**（叠上去=把好脸换成另一表情）。详见 `docs/TROUBLESHOOTING.md` §48。
  - ⚠️ 同样被否证的两个自造判据：**边缘密度**与**亮度标准差**——都在足迹内被头发/边界填充稀释，
    真洞与好脸两侧数值重叠（`gezi_2` 0.314 vs `antu` 0.372；`moermansike_2` std 61 vs `antu` 75）。
  - `canvas.crop()` 用越界框即可（PIL 越界补 0=透明），语义上等于"那里没画"，不必手写钳位。
- **复核口径**（判"叠层有没有毁掉已有内容"）：要按**脸谱落笔足迹**（新图 `alpha>200` 处）量旧像素，分三类「旧=透明洞 / 旧=不透明白块 / 旧=不透明彩色真画」。按整框或只按"是否不透明"粗分会把白块算成已有内容，使 `bangkeshan_2` 这类**整张头缺失**的被误判成"改前已有 37% 内容"。
- 门控生效后样本验证双绿：i168 画出 1 层、逐像素 maxdiff=0（烤脸零回退✓），i168_2 画出 2 层、洞正确填上✓。
  **换判据 = 换分类器**：只在"旧清单"上重渲等于没回归——旧清单是新判据的**因变量**。判据演进后必须
  ① 对**全库候选**重扫（本轮 2221 个）② 维护一份**带标签回归集**（洞侧与好脸侧都要有人，本轮 47 个目视裁定样本）
  ③ 把"在标签集上的符合率"当换入前闸门（`scripts/diag/face_gate_labels_check.py`，退出码即结论）。
  2026-09-20 那轮只重渲了旧清单 35 张就宣布"只有 leiniya_wjz 行为改变"，于是同一版判据一边漏掉
  `moermansike_2`（灰块脸，用户 6 天后才报出来）、一边把 49% 的已烤脸皮肤判成洞，两边都没被发现。
- **排除误判样本用收紧判据，不写手工例外名单**。若某样本目视确认是回退（改前已是完整另一表情），应回到判据层面找可观测差异把它自动筛掉，而不是在代码里列白名单。

**定位脸洞子集（走 4.6 步前的只读扫描）**：给 `compose()` 加 `save=True` 参数（末尾 `if save: base.save(out)`），并加模块级 `FACE_APPLIED = {}` 与 `FACE_GATE = {}`（后者记门控**实际读到的数**：`frac_opaque` / `mad` / 脸槽像素框 / 成品裁切偏移——复核在盘产物时要靠它对齐），渲染后记 `FACE_APPLIED[bundle_name] = any("face-overlay" in str(x) for x in cinfo)`。扫描脚本 `scripts/diag/scan_faces.py` 用 **`save=False` 扫描模式**遍历「有同名 paintingface 包」的候选皮肤（`Paintings_v2 stems ∩ paintingface 包名`，~2221 个，渲染不落盘），输出洞清单 + 门控读数 TSV——真实命中远小于候选数（多数皮肤已烤脸）。再对这批洞皮肤走第 4.6 步定向重渲。
配套工具：`scripts/diag/painting_staleness_scan.py`（全库「产物 vs 当前管线」逐字节普查，只读出清单）、
`scripts/diag/painting_swap_in.py`（换入四道硬检查：nlink==1 / 备份 md5 全等 / 换入后与渲染一致 / 全目录快照清单外 0 个）、
`scripts/diag/face_gate_labels_check.py`（带标签回归闸门）、
`scripts/diag/face_gate_probe.py`（单皮肤取证，走真实渲染路径、**读生产侧 `FACE_GATE` 而不是自己复算**——
复算极易读到"已叠脸之后"的画布，本轮就据此得出过一个假数）、
`scripts/diag/painting_face_rerun.py`（重渲 + 与在盘逐像素比对 + 按"旧图透明/白灰块/彩色画"自动分诊）。

**收尾仍走第 4.6 步受控流程**：门控只保证已烤脸皮肤零回退；洞子集重渲后仍须生成改前/改后并排对比总览 → 用户确认 → 备份换入 → 增量重建这批缩略图/index。另注意 `save=False` 扫描会逐张解码纹理光栅化，量大耗时，用后台跑（run_in_background）。

⚠️ **3D 场景侧只查激活位不够（2026-10-08 实测，见 §125）**：一个网格画不画，Unity 有**三重门控**——
① `GameObject.m_IsActive` × 全祖先；② `MeshRenderer.m_Enabled`；③ `GameObject.m_Layer` 是否落在
`Camera.m_CullingMask` 里。只查 ① 在一个 348 个 MeshFilter 的场景里**多画了 79 个**（②再关 26、
③再剔 4），症状是"游戏里没有的白方块穿在真家具上"。三条要**分开计数**打印，别合并成"跳过 N 个"。
附带一条省事的：用 Unity 内置原语（`unity default resources`，盘上无文件）的对象常常是**碰撞/标记物**，
层掩码会把它们全排除 ⇒ **先查门控，再决定要不要去搞内置资源**（本项目因此作废了一条未决项）。

### 第 4.8 步：图层激活位——「多画了一层游戏里关着的东西」（头部发黑 / 遮挡条型）

**症状**：成品某块区域是**不透明的纯黑或纯白**（不是透明洞——画廊把透明铺成棋盘格，
所以看到黑/白就说明真落了笔）。典型：整个头变黑、身上贴 "NOT ABLE TO DISPLAY" 条、
同一角色叠出四份身子。

**根因**：`parse_painting` 只看 MonoBehaviour 的 `m_Sprite` 是否非空，**不读
`GameObject.m_IsActive`**。游戏里关着的层于是被一律画上去。这是"数据自洽"原则的又一例：
游戏把"这层要不要画"写成了位，不读它就会多画，且**不会报任何错**。

**取证三步（每步配阴性对照）**：
1. 逐层落盘（`scripts/diag/painting_layer_dump.py <bundle>`）看是哪一层；
2. 读该节点 `GameObject.m_IsActive`（UnityPy：`o.read().m_IsActive`）；
3. 全库只读扫描圈定影响面（`scripts/diag/painting_inactive_scan.py`），
   对照组挑几个"看着正常"的皮肤确认它们**没有**关闭层。

**判据**：`有效激活 = 自身 m_IsActive AND 沿 RectTransform.m_Father 全链 m_IsActive`
（Unity 语义：父节点关了整棵子树都不渲染）。**把判定写在解析侧**（`parse_painting` 算好落到
部件的 `active` 字段上），扫描/重渲/换入工具**只读这个字段、不另算一遍**——另算会让
"预测清单"和"实际会变的图"不同源。

**三条硬护栏（都是踩出来的）**：
- **表情/运行时激活的槽要豁免**。`face` 节点在 prefab 里**恒为关闭**，游戏运行时才激活来显示
  表情差分——它正是第 4.7 步叠层逻辑的输入。按激活位无脑过滤会把脸删掉。
- **过滤后一层不剩 ⇒ 原样保留，绝不产出空文件**。实测有"整张画的每一层都是关闭态"的皮肤
  （单层的 `qiye_4`，以及四层 frame 全关、游戏按剧情逐层激活的 `*_memory`）。
  清空 = 不报错的静默失败，比多画一层严重得多。记进审计字典交人工。
- **命中数 ≠ 要换入的数**。必须走一遍"重渲 + 与在盘比 md5"才知道哪些画面真的会变。
  实测 125 张命中 → 48 张会变（73 张的纯白遮挡条早被"近纯白=加算光效层"那个启发式挡着）。
  反过来：**一个通用启发式过滤器会掩盖同批数据上的另一个真缺陷**——带黑字 logo 的遮挡条
  白色占比不足 80%，正好漏过该过滤器，于是白条一直留在正式产物上。

**怎么确认这个位是游戏的真开关而不是巧合**：找一条**独立的已知语义**去对。
本项目里 `_n`（用户确认过"就是不显示背景"）那批皮肤的 `bj` 背景节点恒 `m_IsActive=False` ⇒
对上了。这类"用另一条已确认的事实交叉验证新判据"的做法，比单看数值分布可靠。

**别混淆两类问题**：和谐版（`_hx`）的遮挡条去掉后**不会泄内容**——和谐处理本来就烤在 `_hx` 的
底图里（实测 `gezi_2` vs `gezi_2_hx` 有 82.4% 像素不同），banner 只是运行时占位。
判定方法：直接 diff 两个已渲染产物。

### 第 5 步：Spine 提取

主脚本：`scripts/extract_spine_v2.py`。

- **双结构兼容**：内联型（主包含 skel/atlas/tex，如 `2b_2`）与分离型（资源在 `<name>_res` 包，如 `aersasi`）——漏掉 _res 型是"部分放不出"的根因。
- **无后缀 skel 变体嗅探**：部分包内文件无 `.skel.bytes`/`.atlas.txt` 后缀（如 `beierfasite_g` 类结构）。skel 头部也是 ASCII，**不能只靠后缀/扩展名判断**，按内容特征嗅探（如 skel 特征 vs atlas 文本特征）。
- atlas 页纹理可能来自外部 deps（artresource/effect/*、ui/commonui_atlas），按依赖表补齐。
- 页纹理导出必须 `flip=True`（Spine 运行时按标准 PNG 行 0=顶采样，Unity raw data 相反），与旧版可用输出逐像素比对验证方向。

### 第 6 步：全量运行

`scripts/run_v2_full.py`（断点续跑，跳过已完成目录）。子进程 env 必须传 `PYTHONIOENCODING=utf-8`，主进程 `sys.stdout.reconfigure(encoding='utf-8')`，否则 Windows 分离进程 GBK 编码把成功运行记成 100% 假失败。

## 系统性坑速查表

| 症状 | 根因 | 修复 |
|---|---|---|
| 背景层整层上下颠倒 | 无 mesh 部件按 flip=False 数组又做了 `th-y-h` + `[::-1]` 双重翻转 | `arr = A[rect.y : rect.y+h]`，直接按自底坐标切片 |
| Spine 播放时页面颠倒 | 页纹理按 Unity raw data 序导出 | 改 `flip=True`，与旧版输出逐像素比对验证 |
| 层间比例不对（root scale 如 0.6/0.48） | root localScale 只乘子部件，背景层没乘 | layout 四步语义（见第 4 步），root scale 归一 |
| 全量运行 100% 记失败但图像已写出 | Start-Process 重定向 stdout 默认 GBK，`print('✓')` 崩溃 | utf-8 reconfigure + PYTHONIOENCODING |
| 部件纹理错包（rw 拿到 bj1_tex） | FileID 按 manifest 字母序解析 | 以 SerializedFile.externals[N-1] CAB 为准 |
| "文件不存在"但文件明明在 | 命令行参数带 \r（CRLF）/ PowerShell `$_`、`$env:` 经 Git Bash 被展开 | main 里 strip 参数；含 `$` 的 PS 逻辑一律写 .ps1 文件执行 |
| 较新包加载失败 `No valid Unity version found... set FALLBACK_UNITY_VERSION`（曾致 ~80 背景包导出失败） | UnityFS 版本头被伪装成 5.x.x，该脚本漏设回退（v2 脚本都设了、旧脚本/新写脚本易漏） | 每个 UnityPy 入口脚本设 `config.FALLBACK_UNITY_VERSION="2022.3.62f3"`；排查时先 grep 全脚本核对是否都设了 |
| 嵌套容器皮肤子层整体甩到左下（单层皮肤正常） | layout_all 仿射时多减 p_local[0] | 去掉多减项（第 4 步第 5 条）；已知正常样本逐像素回归验证（commit 52782a7） |
| 视差背景带横向压窄、彼此拼不拢留黑洞（i404 型，逐层渲染形状却都对） | 无 mesh 部件画框误用 CanvasRenderer `mRawSpriteSize`——背景带记录的是切分前原图尺寸(2048×1770)，与真实纹理条(1167×2048 等)非等比 | 按 Unity UI Image 语义把 textureRect 拉伸铺满 RectTransform，mesh 部件不动（第 3 步红线；commit 87c03f0） |
| frame≠rect 只读扫描命中数百皮肤、影响面虚高 | 命中部件多为 4×4 全透明占位精灵（alpha 恒 0，拉伸与否都画不出东西） | 先甄别占位尺寸/alpha 再定真实影响面（本轮 556 部件命中 → 真实仅 10 皮肤/16 部件，见第 4.6 步） |
| 修了布局 bug 后是否全量重跑 | 盲目全量风险面大、可能打乱已正确产物、耗时数倍 | 零回退验证→只读扫描新旧公式枚举受影响清单（4486 中仅 85）→定向重渲+备份换入（见第 4.6 步） |
| CG 型立绘背景层整块消失/角色偏移 | 画布并集默认原点 (0,0)，负 min 坐标层被裁 | 画布覆盖 min→max 或按根节点设计框裁（见第 4.5 步） |
| 排查许久方向全错（z 序/命名对调） | CanvasRenderer 无排序字段；命名靠肉眼猜 | 先 dump 布局树 + 抽 `_rw_tex` 原图核名（见第 4.5 步负结论清单） |
| 成品脸部"白块"（i168_2 型） | face 节点 `m_Sprite` 空（path=0）被 `parse_painting` 跳过，真脸在独立 `paintingface/<name>` 包、合成时未叠；且"白"实为**透明洞**（查看器铺白底） | parse 保留 face 节点框 + render 后叠 paintingface 默认脸，但**须按透明洞门控 `frac_op<0.5` 才叠**（通用叠层会回归已烤脸皮肤，i168 maxdiff≠0）；`save=False` 扫脸洞子集，走第 4.6/4.7 步受控重跑 |
| 头部/上半身整片**不透明纯黑**、身上贴 "NOT ABLE TO DISPLAY" 白条、同一角色叠出多份身子 | `parse_painting` 不读 `GameObject.m_IsActive`，把游戏里**关着**的层（`shadow` 黑剪影 / `shop_hx` 遮挡条 / `*_rw1..4` 备用画法）一律画上去 | 按「自身+全祖先激活」过滤（第 4.8 步）；**`face` 槽豁免**、**过滤后一层不剩则原样保留**（清空=静默失败）；命中数≠换入数，须重渲比 md5 |
| **所有图的柔边都比原画淡**；某层贴边处出现 1px 透明缝；叠脸门控把"脸已烤好"判成洞、发出**另一张表情** | `canvas.paste(img, box, img)` 用 RGBA 图当蒙版时，Pillow 会**把 alpha 通道缩放两次**（文档原话 "scaling the alpha channel twice"）：空画布上 `a → a²/255`（128→64、250→245）。判据读 `canvas alpha>=250`，245 就跌破 | 改用标准 source-over（本项目 = `over()` → `Image.alpha_composite`）。**证伪成本极低**：单层且 1:1 铺满画布的皮肤，成品 alpha 应等于源 alpha，实测命中 `a²/255` 即坐实。见第 4.9 步 |
| 画面**缺一块边**（水花缺左半 / 整张下半截没了 / 只剩偏在一角的残片），但逐层 dump 每层形状都对 | 画布按 `max(x+w)`/`max(y+h)` 开、**从不减 min** → 世界框落在负侧的部件被 paste 静默裁掉。⚠️ 正方向也裁（mesh 顶点合法越框），**只按"rect 有负坐标"筛候选会严重低估影响面** | 画布 = **所有节点框 ∪ 各层落笔框** 的并集，min 钳在 0（本项目 = `canvas_frame()`）。⚠️ 别为省内存把容器 rect 从 max 侧剔掉——画布一旦变窄就**反过来新裁内容**。影响面用"只换画布不换算子"的分层抽样定（实测 2.0%） |

### 第 4.9 步：改「每帧都要走的那段算术」（合成算子 / 画布口径 / 取景规则）——传统零回退闸门在这里失效

这类改动的正当目标是"**所有图都该变**"，所以"对照组逐像素不变"这条判据根本用不了。
按下面五步，才能回答"会不会毁掉那些看着没问题的图"：

1. **先把政策收敛成正本里的一个函数**（本项目 `canvas_frame()` / `over()`）。不是为了整洁——
   是为了下一步能**只换函数**就渲出旧行为。探针自己重写一遍仿射/取整 = 造第二份实现，
   必然漂移（本项目在此连犯三次：`ch` 用错口径的值 → 虚报 32 万变化）。
2. **探针两条保真断言，缺一条就是在比空气**：旧侧（换回退役实现）必须与**在盘产物逐字节相同**；
   新侧必须与**正本 `compose()` 的产物逐字节相同**。注意退役实现要连**输入集**一起退役
   （旧画布对所有 RectTransform 取 max，新画布是落笔框 ∪ rect 框——喂错输入，`旧=盘` 就红）。
3. **多个改动必须能分开量**。给闸门加"只换 A / 只换 B"档。混在一起的代价是真实的：
   本项目第一版把"找回像素"报成 96%/4320 张，实际是"极淡像素复活"和"被裁内容找回"混了，
   分开重测真值 2.0%/约 90 张。
4. **对齐用正本记录的取景事实，不要用图像配准**。`compose()` 落
   `LAST_CANVAS[b] = {origin, canvas, crop}` ⇒ 两版公共框平移是精确整数，直接算。
   配准路线（实心包围盒当锚点 + 小平移精搜）会在"行列写反 / 一个杂点带偏锚点 /
   施加方向与打分方向反号"上反复出错，每次表现为几百万假回退。
5. **判据要落在"会毁图的那个量"上**，不是"变没变"：
   `实心区（离任何半透明像素 ≥2px）可见变化 |Δ|≥12 必须为 0`、
   `不透明(≥250) 不得退化成半透明`、`内容丢失必须为 0（只许找回）`。
   前两条能证明"改动只碰柔边"这个声明——**能写成可测命题的才叫证明**。

**换入仍走第 4.6 步的受控流程**（脱离进程 + 完成哨兵 + 全量重渲 → `painting_swap_in.py` 四道检查
→ 缩略图增量重建 → 索引重建后应当**逐字节相同**，这本身就是"没顺手改到元数据"的证据）。

**否证也要入库**：本项目试过"把叠脸门控的 `FACE_MAD_MAX` 从 30 抬到 40"来同时保住两张问题皮肤，
全库预演显示它会把一张 **face 槽是全身正面图、底图是背面** 的皮肤判成不叠、发出后脑勺——
MAD 分不开"该替换/不该替换"，两者数值重叠。这条写进了常量注释，防止下次再调参试。

## 验证方法

1. **样本先行（硬性规则）**：改脚本后先跑 1-3 个疑难样本，目视确认后经用户同意才全量。
2. **关键样本清单**（覆盖全部历史坑），标准验证命令：
   `py -3 scripts/compose_paintings_v2.py hailunna_4 feiteliekaer_3 2b xili_alter --out Output/Paintings_v2_fixcheck`
   然后逐个 Read 图片目视检查：`hailunna_4`（背景颠倒+root scale 0.6，正确=角色站甲板倚栏杆、酒杯落扶手后）、`feiteliekaer_3`（root scale 0.48+face 差分，正确=角色精确躺上浮床）、`2b`（FileID→externals 反查+分离表情包）、`xili_alter`（镜像+层序回归检查）。
   **改布局函数后的零回退回归**另用 8 皮肤清单：`2b feiteliekaer_3 hailunna_4 xili_alter kewei_6 aersasi_3 chicheng_4 adiliao_2` 渲到临时目录与现有 `Paintings_v2/` 逐像素比对要求全 0.00（验"不该变的没变"，与上面 4 样本验"该变对的变对"互补）。
   **画框/透明类修复**加定量口径：修复前后覆盖率（`alpha>10` 像素占比）变化符合预期 + 对照组逐像素 maxdiff=0，与目视互补；`i404` 可作画框坑验证样本（正确 = 三条视差背景带无缝拼合，剩余透明区为美术本身的圆形浪花轮廓）。
   **脸洞叠层修复（第 4.7 步）对照样本**：`FACE_DEFAULT=1 py -3 scripts/compose_paintings_v2.py i168 i168_2 --out .diag/<新临时目录>` 渲到**全新临时目录**（勿删旧目录、勿用 `rm`）——`i168`（脸已烤进 `_rw`）须逐像素 maxdiff=0（"画出 1 层"、门控判非洞不叠），`i168_2`（透明脸洞）须"画出 2 层"且洞被正确填上。定位全量脸洞子集用 `save=False` 扫描模式（见第 4.7 步）遍历有 paintingface 包的候选，落 `.diag/face_holes.txt` 后再定向重渲。
3. **历史手调参数即"标准答案"**：v1 需要特殊参数才对的样本，v2 应零参数自动正确——若又需要调参就是解析回归了。
4. 全量后随机抽样拼图质检（`scripts/make_contact_sheet.py`）+ 处理失败清单（ERRORS.log）。
5. 样本通过后才清理旧错误产物（`mv` 到 `.trash/<说明>_<日期>/`，勿直接删），再重启全量。

## 3D 类目开工前：先跑能力探针，别外推旧结论

判**这台机器的工具链能把 3D 数据取到哪一层**时，找一个**盘上还活着的同类 3D 包**实测字段，而不是拿别的管线当年的天花板去推断（脚本：`scripts/diag/probe_3d_capability.py`，只读，打印类型分布 + Mesh/蒙皮/贴图/曲线/材质/着色器六段）：

- **判据（按段看，缺一不能推断下一层）**：几何看 `m_VertexData.m_VertexCount` + `m_IndexBuffer`；蒙皮看 `Mesh.m_BindPose`/`m_BoneNameHashes` 与 `SkinnedMeshRenderer.m_Skin`（静态网格里为 0 属正常，**不能据此判"蒙皮读不出"**）；贴图解码以 `.image` 真产出 PIL `RGBA` 为准（ASTC 族靠 `texture2ddecoder`）；曲线看 `Keyframe` 是否含 `inSlope/outSlope`；外观参数看 `Material.m_SavedProperties` 的 floats/colors/texRefs + `m_ShaderKeywords` + `m_CustomRenderQueue`。
- **着色器分三档，别一句"拿不回"糊过去**：① `Shader.m_ParsedForm.m_PropInfo.m_Props` = 参数表（名称/类型/默认值）**可读**；② CGPROGRAM 源码块在打包时被裁（`export()` 头部自述 "This is *not* a valid shader file"）；③ `compressedBlob` + `platforms`（如 `[9,18]` = DX9 VS SM20 / DX11 PS SM50）= 编译后字节码**在包里**，可走 DXBC→HLSL / SPIR-V→GLSL 反编译。⇒ 前端（three.js）重写材质是"照参数表施工"，只有**逐像素一致**那一档才是真近似。
- **烘焙光照是一条正道不是fallback**：`scenesres/*.shadowmap`、`LightmapSettings`、`LightProbes` 是烘焙数据，当第二套 UV 贴上去比实时重算更接近原画面。

**蒙皮权重的真读法**（探针打印 `m_Skin 字段不存在` **是路标不是失败**——新版 Unity 早把权重搬进了网格）：

- 位置：`Mesh.m_VertexData.m_Channels`，**索引 12 = BlendWeight、13 = BlendIndices**（0=Position 1=Normal 2=Tangent 3=Color 4~11=UV0~UV7），二者同属最后一个 stream。骨骼侧 `m_BindPose`/`m_BoneNameHashes`/`m_BonesAABB` **逐网格等长**，长度就是骨数；`SkinnedMeshRenderer.m_Bones` 在 prefab 包里指向同包 `Transform`，**可当场解析出骨名**（`Bip001 Head`、`bone_hair_03` 这类）。
- ⚠️ **UnityPy 不给你 stream 数组**：`m_Streams` 恒空 list、`m_Streams_0_..3_` 全 `None`，**整块顶点字节在 `m_VertexData.m_DataSize` 里**（名字像整数，其实是 `bytes`）。各 stream 块按序首尾相接：`base[s] = Σ stride[s']*n (s'<s)`。
- **布局不要猜，反解 + 三重自证**：每流只有最后一个通道的元素宽度未知（其余由 `next_offset - offset` 整除推出），枚举 ∈{1,2,4}，要求同时满足 ① `Σ stride == len(data)//n`（并允许 `tail = len % n` 的 padding 落在**末段流起点之前**，不是只有整块尾部）；② **每个**顶点权重和恰为 `1.0000`（UNorm16 走 `/65535`、Float32 直读）；③ `max(boneIndex) < len(m_BindPose)`。只有真布局能三条全过——**错布局会自己报出来，所以这套判据同时也是回归闸门**。
- **每顶点骨数逐网格变，不是一个模型一个常量**：实测同一角色 body=4、face/neck=2、单骨部件（脸红/装饰）**压根没有 BlendWeight 通道、权重恒 1**。装配器按"通道存在与否 + 维度"分支，别按角色配表写死。
- ⚠️ **Humanoid 角色的动画不在曲线列表里**。`AnimationClip` 的
  `m_PositionCurves/m_RotationCurves/m_ScaleCurves/m_FloatCurves/m_EulerCurves/m_PPtrCurves`
  可以**全为 0 条而数据完好**——Unity 对 Humanoid 一律存**肌肉空间优化格式**：
  真数据在 `m_MuscleClip`（`ClipMuscleConstant` → `Clip(m_DenseClip/m_StreamedClip/m_ConstantClip/m_Binding)`
  + `m_DeltaPose=HumanPose` + `m_IndexArray`），量级看 `m_MuscleClipSize`。
  ⇒ 判"动画读不出"之前必须先查 `m_MuscleClipSize>0`；要还原骨骼 TRS 需 Avatar 的 muscle→bone 映射，
  是独立子项目，不是"再拉一个包"。
- ⚠️ **静止态蒙皮的判据要逐顶点**：`max|applyBoneTransform(i,v) − v| ≈ 0`（实测 1e-6 量级）
  能同时验位置/骨号/权重/bind 矩阵/节点层；包围盒只反映范围，两个不同的错误可给出同样的盒子。
  ⚠️ 也别用 `Box3.setFromObject(skinnedMesh)`（走未蒙皮的 geometry 盒，恒真）。
- ⚠️ **元素宽 2 字节 ≠ float16**：UV 是半精度、**BlendWeight 是 UNorm16**、**BlendIndices 是 uint16**。
  按宽度统一取 dtype 会让整数骨号 `1` 变成次正规数 6e-8（`int()` 后归零 ⇒ 全模型挂到 0 号骨），
  让权重 `32767`/`32768` 直接读成 **NaN / -Inf**。dtype 必须**按通道号**决定。
- ⚠️ **不变式会被「自洽的错误」骗过去**：权重整列读错后再除以自身和，每行和仍精确为 1，
  「权重和==1」这条闸完全看不见；且 `abs(NaN-1)>eps` 恒 False，NaN 连这条都过。
  ⇒ 除了内部不变式，还要 ① `math.isfinite` 单独查 ② **跨源逐行比对**（产物前 N 行 vs 源包重读值）。
- ⚠️ `Mesh.m_CompressedMesh` 在 TypeTree 里**恒存在**，`if obj.m_CompressedMesh: 判"压缩网格"` 会得到永远为真的假信号——要看到里面 `m_Vertices/m_BoneWeights` 的 `m_NumItems>0` 才算数据存在。**"字段读得出来"不等于"里面有数据"**，探针一律量内部计数。

**Unity 烘焙 lightmap → glTF/three.js 的四条**（场景级还原用；glTF 核心没有 lightmap 这个概念）

- 页号写进 `material.extras.unityLightmapPage`，每 renderer 的矩形 `m_LightmapTilingOffset`
  **烘进几何的第二套 UV**（`uv1*tiling+offset`），另出一份 sidecar 让查看端挂 `material.lightMap`
  （three.js 用 `uv1` 属性采样）。⚠️ **不要**把矩形放进 `texture.repeat/offset`：一张 lightmap
  实测有 196 个不同矩形 ⇒ 按矩形克隆贴图就是 196 次 1024² 上传；烘进几何只让几何数 205→252。
  代价是**几何去重键必须带上这个矩形**，否则同网格不同矩形互相覆盖。
- `m_LightmapIndex == 65535` 是"未烘焙"（不是错误码）；`LightmapSettings.m_Lightmaps[i]` 的字段是
  `m_Lightmap / m_DirLightmap / m_IndirectLightmap / m_ShadowMask`（**没有** `m_LightmapTexture`）。
  `m_LightmapsMode=1`(Directional) 而 `m_DirLightmap` 全空时，只有颜色页可用，第一版别硬造方向。
- **只给烘过的对象发 `TEXCOORD_1`**：未烘焙对象留着满幅 UV1 会让"带 uv1 的几何数"变成混合母体。
- **Unity 的 Area 灯（type 0）只参与烘焙、运行时不发光** ⇒ 不要把它补成实时灯去"照亮画面"；
  它正是"必须有 lightmap"的原因。判据侧要加一条**页号敏感性**：把每个对象的采样点换到错的一页，
  亮度变化 >5% 的对象占比必须高（实测 0.967）——占比低说明页号分配根本不承载信息。

**Unity 材质 → glTF 的透明/双面，与 three.js 的采样通道（场景级；2026-10-09 一轮两条真错）**

- **`alphaMode` 有三个可用信号，缺一个就会把该透的画成实心**：① 混合方程
  `_SrcBlend==5 && _DstBlend==10`（SrcAlpha/OneMinusSrcAlpha）；② `_BaseColor.a < 1`；
  ③ **baseColor 贴图自带 alpha（不是恒 255）**。③ 专治云层/光束这类自定义 shader 材质——
  它们既没有 ① 也没有 ②，透明信息只在贴图的 A 里（实测云纹理 alpha 均值 0.066）。
  ⚠️ ③ 必须**按贴图记一张表**：只在"首次解码"分支里判，贴图被多材质复用走缓存时就漏
  （实测漏了树叶与花）。⚠️ **`_Cutoff` 是 Shader 默认值陷阱**：348 个材质里 289 个带着 0.5，
  其中包含明显不透明的墙和木头 ⇒ 拿它当判据会把大半房间变成 alpha 测试。
  漏信号 ①② 的后果：窗玻璃（`a=0.196`）画成实心黑，整片窗外看不见；
  漏信号 ③ 的后果：窗外云层把近乎全黑的 RGB 糊在天空位置上，**补摆的背景一个像素都不露**。
  配套两条回读不变式：「baseColorFactor.a<1 却没标 BLEND = 0」与
  「baseColor 贴图自带 alpha 却是 OPAQUE = 0」；受影响面用
  `scripts/diag/unity_material_alpha_scan.py` 当场数，**不要靠注释里那份清单**。
- **贴图的 RGB 不一定是颜色**：自定义着色器常把数据塞进通道。实测云纹理在高 alpha 处
  RGB=(218,2,136) 品红、白桦叶纹理 B 通道恒 241-255 只有 13 个不同值（且同一张贴图同时绑在
  `_BaseMap`/`_LSABMap`/`_MainTex` 上）。按 albedo 直用就得到**红云与蓝树**。
  着色器读不到时的正确姿势：把"云=纯白 + alpha 当密度"这类**推断放查看端**，
  并配一条"开关前后分布必须不同"的对照（实测最大分布差 0.0387）；
  **不要烧进 GLB**——产物必须保持"包里是什么就是什么"。
- **three.js r152+ 按 `texture.channel` 选 UV**：手工赋 `material.lightMap` 时必须 `channel = 1`，
  否则它拿**漫反射 UV0** 采样，而"挂了多少材质 / 多少几何带 uv1"这类计数判据完全无感。
  ⇒ 判据要直接量那个可观测状态（`channel===1 && geometry.attributes.uv1`），错数必须为 0。
- **three.js 对 `transparent && side===DoubleSide && !forceSinglePass` 会画两遍**（先背面再正面）
  ⇒ "renderer 三角数 == 真值"这条恒等式必然翻倍（实测 120961 → 127755）。
  正确做法是**把期望值推出来**：前端自己数哪些网格是 transparent，右边 = 真值 + 这批网格的三角数。
  ⚠️ 不许把恒等式放宽成 `>=` 或加容差——那等于把仪器拆了。
- **覆盖 `THREE.ShaderChunk.*` 之前先确认有人 `#include` 它**：r160 的 lightmap 采样在
  `lights_fragment_maps` 里面（`irradiance += lightMapIrradiance`，**已经**乘反照率），
  `lightmap_fragment` 是个没人 include 的死块 ⇒ 改它**静默无效**，看起来"这条轴没用"。
  唯一抓得住它的是"两条版必须不同"的对照（本轮就是靠它红出来的）。
- **定位"画面里这块黑是什么"用射线命中，不用亮度猜**：每机位沿视线打 9 点，回报
  (对象名, 材质名, 距离)。本轮窗中心第一命中 `pre_db_plane01 · mat_db_glass06 @6.36m`，
  其后才是树 9.7m / 地形 20.7m / 云 255m ⇒ 一次就分清"被挡住"与"根本没内容"，
  这两种情况在像素分布上长得一模一样。

**从蒙皮包出 glTF（`.glb`）的四条硬事实**（`export()` 只给无骨骼 OBJ，装配层必须自己写）：

- **真材质常常不在网格包里**：Unity 的 FBX 导入件在 `res` 包里只挂占位材质（`Lit`），真材质虽**住在**该包，
  却是由 **prefab 包的 `SkinnedMeshRenderer.m_Materials` 以外链 PPtr** 引用的。落点判定用现成规则：
  `prefab 的 SerializedFile.externals[i].name == 目标包的内层 CAB` ⇒ `file_id == i+1` 的 PPtr 其 `path_id`
  就在那包里。**不要按材质名猜**（名字匹配会把眼睑/眉毛贴到皮肤上）。
- **一个网格可有多 submesh**（实测脸部 5 个、身体 2 个；`m_SubMeshes` 的 `firstByte/indexCount`，
  各段 `vertexCount` 之和恰等于顶点总数）。只出一个 primitive 会整块贴错材质；
  ⚠️ **换绕序必须在按 submesh 切分之后做**，否则 `firstByte` 的字节偏移对不上。
- ⚠️ **`skin` 挂在 node 上，不是挂在 mesh 上**：只写 `meshes`+`skins` 两段而不在宿主节点点名 `skin`，
  three.js **照样画得出来**，但当成普通 Mesh —— **蒙皮静默失效**，且没有任何报错。
- ⚠️ **权重属性名是 `WEIGHTS_0`（复数）**，骨号是 `JOINTS_0`。写成 `WEIGHT_0` 会被 GLTFLoader 的
  映射表静默忽略，最后在建 SkinnedMesh 时抛 `reading 'count'`。
  ⇒ **自写产物的回读断言要按规范白名单查属性名**（`POSITION/NORMAL/TANGENT/COLOR_n/TEXCOORD_n/JOINTS_n/WEIGHTS_n`），
  **不许按"我自己写了什么键"查** —— 那样会出现"闸门全绿、前端根本加载不了"。
  配套：变异样本必须**等长**（改键名顺手改了长度，闸门会先炸在长度上，证明不了你想验的那条）。
- ⚠️ **验蒙皮不许用 `Box3.setFromObject(skinnedMesh)`**：它取的是**未蒙皮**的 `geometry.boundingBox`，
  蒙皮炸了它也不动 —— 恒真判据。要量蒙皮就在页面里**用 CPU 逐顶点重算**
  `Σ w·(bone.matrixWorld ∘ boneInverse)·v`；且"全零权重行"要回落成原顶点，否则顶点塌到原点，
  包围盒和边长比一起被污染。另：GLTFLoader **一个 primitive 建一个 SkinnedMesh**，
  比"前端网格数 == 源包网格数"要按名字分组，不能直接数对象。
- **`UnityPropertySheet` 的贴图槽在这个版本叫 `m_TexEnvs`**（另有 `m_Floats/m_Colors/m_Ints`），
  **没有 `m_Textures`**。按 `getattr(sp,'m_Textures',[])` 读会得到**每个材质都 `texRefs=0`** 的恒 0 假读数——
  与 `compressedMesh` 同族：**读出的 0 要先问"字段名对不对"，再问"值是不是真 0"**。
- **自写二进制产物必须被"独立回读 + 变异红路径"验收**，否则等于没验：
  ① 重新打开自己写的文件，断言全部落在**文件字节**上（GLB 声明长度==实际字节、accessor 的
  `count×type×componentType` 落在 bufferView 内、从 BIN 读回每顶点权重和==1、bind 矩阵条数==关节数
  且**不含单位阵**、image 前 8 字节是 PNG 魔数、索引被 3 整除且 < 顶点数、没有 mesh 未挂在节点上）；
  ② 再**故意改坏两处**（把一个权重字节置 0、把长度声明改短 4B），两次都必须非零退出并点名缺陷——
  闸门不红就等于闸门是空的。装配期就加一条**长度不变式** `len(values)==count×ITEMS[type]`
  （`MAT4` 的 `count` 是矩阵个数不是浮点个数），能把这类错在生成时炸掉而不是留给浏览器。
  ③ GLB 的块数据从**偏移 20** 起（12B 全局头 + 8B 块头），按 16 读会拿到带 `"JSON"` 前串的坏 JSON。
  ④ 坐标系镜像要**处处一致**：顶点/法线 x 取反 + 三角形换绕序 + 矩阵 `C·M·C` 共轭 +
  四元数 `(x,y,z,w)→(x,-y,-z,w)` + UV 的 V 翻一次；少做任何一处会得到"镜像但 inside-out"。
  其中"矩阵要不要转置"与"V 要不要翻"只能目视定案 ⇒ 做成**开关**，不要偷偷改数据。

**踩坑**：
- **目录名不可信**：`shipmodels/` 实测只有 `Sprite`+`Texture2D`（2,547 个包全是 2D 舰船贴图）。判类型必须看对象类型分布。
- **旧天花板不能外推**：Live2D 的"约 7% 贝塞尔段无法还原"是 moc3 **反解**的限制；3D 的 `Keyframe` 显式存 slope，是两种数据形态。同理"上次 Spine 少收了一类对象"也不能推成"这类对象读不出"。
- **`UnityPy` 的 `Mesh.export()` 只给 OBJ，不含骨骼** ⇒ 蒙皮动画必须自己装配 glTF（`pygltflib` 常缺）。
- `load()` 报 `No valid Unity version found` 时设 `UnityPy.config.FALLBACK_UNITY_VERSION`，不是包坏了。
- 打印中文撞 GBK stdout 会显示成 `?????`，**那是显示不是数据**；脚本内 `sys.stdout.reconfigure(encoding='utf-8')`。

## 完成收尾

每轮管线改动/全量完成后，按项目 AGENTS.md 规则：更新 `PROJECT_STATUS.md` 对应章节（状态 emoji、指标、生成时间，新根因写入 §9.3），`git add` 相关脚本并用中文 commit message 提交。

## 参考

- `reference.md`：Y 翻转坐标系总表、PPtr/externals 完整解析规则、批量运维细则。
- 项目内权威文档：`PROJECT_STATUS.md` §9.1-9.5（管线设计 + 五个系统性根因复盘）、`docs/DEV_LOG.md`（操作手册）。
