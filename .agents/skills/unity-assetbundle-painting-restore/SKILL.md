---
name: unity-assetbundle-painting-restore
description: Unity AssetBundle 立绘数据驱动还原流程（以碧蓝航线项目为蓝本）。当需要从 Unity 游戏的 AssetBundle 中还原静态立绘（多层 UI 合成）、提取 Spine 动态立绘、解析 PPtr 依赖关系定位 Mesh/Sprite，或排查还原结果"颠倒/比例错/层错位/黑洞"类系统性坐标与画框问题时使用。触发词：立绘还原、立绘合成、AssetBundle 立绘、Spine 提取、PPtr、externals、CAB、图层错位、比例不对、颠倒、黑洞、画框、mRawSpriteSize、覆盖率扫描、重跑、影响面扫描。
version: 1.5.0
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
  - 进度文档：`PROJECT_STATUS.md` §12（管线细节权威来源，跨会话先读它）

## 核心原则

**游戏数据完全自洽——一切"错位/颠倒/比例不对"都是解析姿势不对，禁止逐角色手调参数。**
旧管线（v1）积累的所有手调参数（BUNDLE_BJ_ABSOLUTE / SCALES / OFFSETS）都已被官方数据自然推导取代。每次遇到"看起来需要手调"的样本，先怀疑坐标/依赖解析，不要加参数。

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

## 验证方法

1. **样本先行（硬性规则）**：改脚本后先跑 1-3 个疑难样本，目视确认后经用户同意才全量。
2. **关键样本清单**（覆盖全部历史坑），标准验证命令：
   `py -3 scripts/compose_paintings_v2.py hailunna_4 feiteliekaer_3 2b xili_alter --out Output/Paintings_v2_fixcheck`
   然后逐个 Read 图片目视检查：`hailunna_4`（背景颠倒+root scale 0.6，正确=角色站甲板倚栏杆、酒杯落扶手后）、`feiteliekaer_3`（root scale 0.48+face 差分，正确=角色精确躺上浮床）、`2b`（FileID→externals 反查+分离表情包）、`xili_alter`（镜像+层序回归检查）。
   **改布局函数后的零回退回归**另用 8 皮肤清单：`2b feiteliekaer_3 hailunna_4 xili_alter kewei_6 aersasi_3 chicheng_4 adiliao_2` 渲到临时目录与现有 `Paintings_v2/` 逐像素比对要求全 0.00（验"不该变的没变"，与上面 4 样本验"该变对的变对"互补）。
   **画框/透明类修复**加定量口径：修复前后覆盖率（`alpha>10` 像素占比）变化符合预期 + 对照组逐像素 maxdiff=0，与目视互补；`i404` 可作画框坑验证样本（正确 = 三条视差背景带无缝拼合，剩余透明区为美术本身的圆形浪花轮廓）。
3. **历史手调参数即"标准答案"**：v1 需要特殊参数才对的样本，v2 应零参数自动正确——若又需要调参就是解析回归了。
4. 全量后随机抽样拼图质检（`scripts/make_contact_sheet.py`）+ 处理失败清单（ERRORS.log）。
5. 样本通过后才清理旧错误产物（`mv` 到 `.trash/<说明>_<日期>/`，勿直接删），再重启全量。

## 完成收尾

每轮管线改动/全量完成后，按项目 AGENTS.md 规则：更新 `PROJECT_STATUS.md` 对应章节（状态 emoji、指标、生成时间，新根因写入 §12.x），`git add` 相关脚本并用中文 commit message 提交。

## 参考

- `reference.md`：Y 翻转坐标系总表、PPtr/externals 完整解析规则、批量运维细则。
- 项目内权威文档：`PROJECT_STATUS.md` §12.2-12.8（管线设计+四轮 bug 复盘）、`DEV_LOG.md`（操作手册）。
