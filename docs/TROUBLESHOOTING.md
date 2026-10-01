# 踩坑记录 — 问题与解决方案

> 本文档记录项目中遇到的具体问题及其解决方案，供后续会话参考。
> 格式：问题描述 → 原因分析 → 解决方案 → 涉及文件

---

## 1. Live2D model3.json 格式不兼容 Live2DViewerEX

**日期**: 2026-06-19  
**现象**: Live2DViewerEX 无法加载还原的 Live2D 模型  
**原因**: model3.json 中多个字段格式与 Cubism SDK 标准不一致：

| 字段 | 错误格式 | 正确格式 |
|---|---|---|
| `Pose` | `{"Type": 0, "Id": "Pose"}` (对象) | 省略或 `null`（无 .pose3.json 文件）|
| `DisplayInfo` | `{"Size": {"Width": 2000, "Height": 2000}}` (对象) | 省略或 `null`（无 .cdi3.json 文件）|
| `Groups` | `"Id"` + `"GroupIds"` | `"Ids"` (数组) |
| `HitAreas` | 在 `FileReferences` 内, 空数组 | 在顶层, `[{"Id":"HitArea","Name":"Head"},...]` |
| `Motions` | `{"File":"..."}` | `{"File":"...","FadeInTime":0.5,"FadeOutTime":0.5}` |
| `Expressions` | 空数组 `[]` | 省略（无 .exp3.json 文件）|

**解决方案**: 重写 `scripts/fix_model3.py`，逐字段修正格式。  
**涉及文件**: `scripts/fix_model3.py`, `scripts/reconstruct_live2d.py`

---

## 2. Live2D 纹理拼接乱序（部件错位）

**日期**: 2026-06-19  
**现象**: 模型能加载但部件位置错乱（如 lingbo、jian_3），256 个模型中有 46 个受影响  
**原因**: model3.json 中 `Textures` 数组的顺序跟随了 bundle 中的存储顺序，但 moc3 文件按**纹理名称字母顺序**索引。

示例（lingbo）：
- Bundle 存储顺序: `texture_00, texture_02, texture_03, texture_01`
- moc3 期望顺序: `texture_00, texture_01, texture_02, texture_03`（字母序）
- 错误的 model3.json: `["texture_00.png", "texture_02.png", "texture_03.png", "texture_01.png"]`
- 正确的 model3.json: `["texture_00.png", "texture_01.png", "texture_02.png", "texture_03.png"]`

**解决方案**: model3.json 的 `Textures` 数组必须按纹理名称字母顺序排列。  
**修复命令**:
```python
# 对所有 model3.json 的 Textures 数组排序
import json, os
for name in os.listdir(OUTPUT_DIR):
    m3 = os.path.join(OUTPUT_DIR, name, f'{name}.model3.json')
    with open(m3, 'r') as f:
        model = json.load(f)
    model['FileReferences']['Textures'] = sorted(model['FileReferences']['Textures'])
    with open(m3, 'w') as f:
        json.dump(model, f, indent=2)
```

**涉及文件**: `scripts/fix_model3.py`（需在修复时自动排序 Textures）  
**受影响模型**: 46/256（adaerbote_3, aerbien_3, lingbo, jian_3, z23 等）

---

## 3. UnityPy AnimationClip StreamedClip 解析

**日期**: 2026-06-19  
**现象**: 提取的 motion3.json 为空占位符（CurveCount=0）  
**原因**: AnimationClip 的动画数据存储在 `m_MuscleClip.m_Clip.m_StreamedClip` 中，是 packed uint32 格式，传统 `m_FloatCurves` 为空。

**StreamedClip 格式** (参考 AssetStudio 源码):
```
data: uint32[] — 包含 sentinel + 帧数据

帧格式:
  time: float (4 bytes)
  numKeys: int (4 bytes)
  对每个 key:
    index: int (4 bytes) — 曲线索引
    coeff[0]: float — 未使用
    coeff[1]: float — 未使用
    coeff[2]: float — outSlope
    coeff[3]: float — value (当前值)

终止符: time = +infinity (0x7F800000)
初始帧: time = -float.MaxValue (跳过)
```

**解决方案**: 解析 StreamedClip 转换为 motion3.json 的 Segments 格式。  
**涉及文件**: `scripts/extract_motions.py`

---

## 4. fix_model3.py 被意外恢复为旧版本

**日期**: 2026-06-19  
**现象**: 运行 fix_model3.py 后 model3.json 仍有错误格式（DisplayInfo 对象、Pose 对象）  
**原因**: 脚本在某次操作中被覆盖为旧版本，旧版本在添加错误字段而非修复。  
**教训**: 修改脚本前先确认当前版本是否正确，避免覆盖已修复的版本。

---

## 经验总结

1. **Live2D Cubism SDK 的 model3.json 有严格格式要求**，字段类型（字符串 vs 对象）必须精确匹配
2. **moc3 文件按纹理名称字母顺序索引**，不是按 bundle 存储顺序
3. **UnityPy 的 AnimationClip 数据在 StreamedClip 中**，需要手动解析 packed uint32 格式
4. **修改脚本时注意版本管理**，避免意外覆盖已修复的版本

---

## 5. Live2D 无交互区域（HitAreas 占位符）

**日期**: 2026-06-19
**现象**: 模型能显示和微动，但开启可触发区域无红框，点击无交互动画
**原因**: HitAreas 使用占位符 ID（HitArea, HitArea2），不匹配 moc3 中的真实 drawable ID
**解决方案**: 从 moc3 文件提取真实的 Touch/Part ID 作为 HitArea Id

moc3 中的关键字符串:
- TouchHead / Part01Face001 -> Head 交互区域
- TouchBody / Part01Body -> Body 交互区域
- TouchSpecial -> Special 交互区域

**涉及文件**: 256 个 model3.json
**受影响范围**: 全部 256 个模型
> ⚠️ **2026-09-21 更正**：本条的解法当时**只对老模型（组名 `Head/Body/Special`）生效**，新皮肤用的是 `touch_*` 组名，于是被漏成「没有判定区」——实测 `chaijun_6/antu_2/baifeng_3/jinluhao_3` 和 9 个未还原 bundle 的 moc3 里都有 `TouchHead/TouchBody/TouchSpecial`。详见 §18。

---

## 6. HitArea click does not trigger interaction animation

**Date**: 2026-06-20
**Symptom**: HitArea red boxes show, but clicking does not trigger animation
**Root Cause**: Live2DViewerEX requires Tap-prefixed motion group names
**Solution**: Add TapHead/TapBody/TapSpecial motion groups in model3.json

Correct model3.json format:
  HitAreas with TouchHead/TouchBody/TouchSpecial IDs
  Motions must include both Head and TapHead groups pointing to touch_head.motion3.json

**Key finding**: HitArea Name must match Motion Group Name,
and Live2DViewerEX additionally requires Tap-prefixed groups to trigger interaction

**Files**: 256 model3.json files
**Scope**: All 256 models

---

## 7. Unmapped parameters causing eye bugs and white screen

**Date**: 2026-06-20
**Symptom**: Eye animations stick closed, white screen on some motions
**Root Cause**: Motion files contain Param_22-64 references that dont map to actual model parameters
**Solution**: Remove unmapped parameter curves from motion files

Root cause details:
- moc3 contains 22-140 parameters depending on model complexity
- Some moc3s use Chinese parameter names (e.g. tongkongdaxiao) not starting with Param
- Motion files reference Param_XX by index but moc3 has fewer params
- Result: broken animations, eyes stuck closed, white screen

**Fix**: Filter out curves with Param_ prefix that have no matching moc3 parameter
**Files**: motion3.json files across 36+ models

---

## 8. Moc3 parameter count mismatch with motion files

**Date**: 2026-06-20
**Symptom**: Some models have Param_14-86 in motion files that dont map to any moc3 parameter
**Root Cause**: moc3 and motion files from different model versions, or moc3 uses non-Param naming
**Solution**: Removed unmapped parameter curves from motion files

Details:
- moc3 stores parameters as 64-byte entries with names at varying offsets (0, 32, or 48)
- Some moc3s use Chinese parameter names (e.g. tongkongdaxiao)
- Motion files may reference more parameters than moc3 defines
- Removed curves with Param_ prefix that have no matching moc3 parameter

**Affected models**: 19 models with severe version mismatch
**Impact**: Reduced animation complexity but model still functions

---

## 9. Motion extraction quality issues（✅ 已解决，见 §17）

**Date**: 2026-06-20
**Symptom**: Eye animations stick, some models dont trigger, motion quality varies
**Root Cause**: StreamedClip parsing produces incomplete/corrupted motion data

Known issues:
- Eye parameters (ParamEyeROpen) end at 0.0 instead of returning to idle state
- Some models have 0 curves in extracted motions (extraction failed)
- Parameter value ranges may be incorrect
- The StreamedClip binary format is complex and not fully reverse-engineered

**Possible solutions**:
1. Use AssetStudioGUI to export motions directly (bypasses our parser)
2. Find a complete MOC3/motion parser library
3. Accept current quality and focus on other features

**Current state**:
- Models display correctly with textures
- HitAreas show red boxes
- Tap prefix triggers animations (but quality varies)
- Eye/mouth animations may have issues

---

## 10. StreamedClip binary format not fully reverse-engineered（✅ 已解决，见 §17）

**Date**: 2026-06-20
**Symptom**: Motion extraction produces empty or corrupted data for some models
**Root Cause**: StreamedClip binary format is complex and not fully understood

Technical details:
- StreamedClip stores animation curve data as packed uint32 array
- Format: sentinel(0xFF7FFFFF) + curveCount + frames
- Each frame: time(float) + numKeys(int) + keys[index(int) + coeff[4](float)]
- coeff[2] = outSlope, coeff[3] = value
- Different models have different data layouts (offset 0, 32, or 48 for parameter names)
- Some moc3s use Chinese parameter names not starting with Param/PARAM

Affected behavior:
- Eye animations may stick closed after touch motion
- Some models have 0 curves in extracted motions
- Motion quality varies between models

**Status**: ✅ 已于 2026-09-21 彻底解决，见 §17（护栏误杀帧 0 + 曲线名按位置猜）
**Reference**: AssetStudio source code at github.com/Perfare/AssetStudio
**Files**: scripts/extract_motions.py

---


## 17. Live2D「有的乱飘/有的乱闪/点了没反应」= 57% 动作是空壳 + 其余曲线名全部错位

**Date**: 2026-09-21
**Symptom**: 画廊 Live2D 部分模型乱飘、部分乱闪、部分点了没反应；而无头批量验证却报 260/260 全通过
**Root Cause**: 提取管线的两处**静默失败**（都不在前端；前端只是把坏数据如实渲染出来）

### 根因一：护栏误杀帧 0 → 整条动作退化成空壳

`extract_motions.py` 旧护栏 `if num_keys < 0 or num_keys > 100: break`。但 StreamedClip 的
**帧 0 是 time=-3.4e38 的「参考姿态帧」，一帧合法写完全部曲线** —— 碧蓝大模型 200~800 个参数，
实测帧 0 有 111~515 个 key（`aerbien_3` 为 381~515），必然触发护栏 → `frames=[]` →
`extract_motion()` 返回 None → **不覆盖** `reconstruct_live2d.py` 写好的 `"Curves": []` 占位文件。
占位文件结构完全合法（Duration 兜底 3.0、Loop True），运行时"能播"，但什么都不动。

实测规模：**8154 条 clip 里 5037 条（61.8%）是空壳**；260 个模型中 16 个全空壳、219 个半空壳。

### 根因二：曲线名靠位置猜，与真实参数对不上

旧逻辑假设 *curve index == moc3 参数序号（从 0 连续）*。真实关系是：

```
m_StreamedClip 的 curve index  <->  AnimationClip.m_ClipBindingConstant.genericBindings[i]
genericBindings[i].path = crc32("Parameters/<GameObject名>")  -> Target=Parameter
                          crc32("Parts/<GameObject名>")       -> Target=PartOpacity（部件可见性）
```

`CubismParameter` 组件的 `m_Name` 是**空**的（真名挂在 GameObject 上），`_unmanagedIndex` 才是
moc3 参数序号。于是被动画化的参数序号是**稀疏**的：`lingbo/idle` 真实为
`0,1,2,8,9,12,13,14,15,18,21,22,23,26,27`，旧实现却按 0..14 连续取名 →
**眼睛数据写进 `ParamBrowLY`、手臂数据写进 `PARAM_Smile_eye`**。
实测 **0/8154** 条 clip 满足 dense 前提，即 3117 个"非空壳"文件的曲线名**无一正确**。

独立裁判（不依赖我自己的映射）：用 Cubism 通用取值域查越域 —— 旧数据 **23.1%** 越域
（`ParamCheek` 78%、`ParamMouthOpenY` 61%、`ParamEyeLOpen` 47%），新数据 **2.9%**（仅眼开度，
说明这些模型眼开度合法上限 >1）。越域值在运行时被 clamp → 就是"点了没反应"。

跨模型验证：946274 个绑定用 crc32 解析，未解析仅 **0.226%**；**91.7%** 的 clip 解出的参数序号
严格递增（若 curve idx 与 binding 无关则概率约 1/n!，不可能）—— 映射链成立。

### 为什么无头验证没抓到

判据用错了：`l2d_sweep.py` 看 `motionManager.state.currentGroup` 变化 = "动作启动了"，
**空壳也会启动**；`hit_verify.py` 看 `currentGroup == 部位名`，同样只看标签。
两者都不看 Curves 条数与曲线名，于是"767/768 全中"与"数据全错"同时成立。
→ **动效类验证的判据必须是内容（Curves 条数、Id 是否命中 moc3 参数表），不是状态机标签。**

### 官方资产里确实有「拼接逻辑」，且有两处硬约束

bundle 内组件实测：`CubismPart`×12~363 + `CubismPartColorsEditor` + `CubismFadeController` +
`CubismPoseController` + `CubismExpressionController` + `CubismEyeBlinkController` +
`CubismMouthController`/`CubismCriSrcMouthInput` + `CubismLookParameter` + `CubismMaskController` +
`CubismRaycastable`（**真实点击区**；我们现在拿 `Touch*` drawable 猜）。

1. 运行时 pixi-live2d-display 0.4.0 **完全不读 model3.json 的 `Pose`/pose3.json**
   （字符串 `"Pose"` 在该 js 中出现 0 次），但**支持 motion3.json 的 `Target:"PartOpacity"`**
   → 换装/部件可见性**必须写进 motion3.json**，出 pose3.json 是死路。
   实测 79 个模型带这类曲线（`gaoxiong_7` 3548 条、`xukufu_2` 462、`bisimai_2` 351）。
2. 第三类绑定属性哈希 `4109387685`（疑 Drawable 颜色/透明度）运行时无对应 motion target，
   占全部绑定 **0.226%** → 按用户决策跳过并记录。

### 修法（三处，全部代码级、零逐角色调参）

1. `scripts/extract_motions.py` 重写映射核心：去护栏（靠 `+inf` 结束符 + 缓冲区边界）、
   参考姿态帧当 t=0 基准值、crc32 绑定解析定 Target/Id、真实 Duration/Loop、
   Unity 切线→Cubism 归一化贝塞尔（|dv| 过小或控制点 >3 时退化线性，防过冲抖动，
   实测未防护时 `by1=14.93`）、**解出 0 条曲线即报错退出，绝不静默**。
2. `scripts/reconstruct_live2d.py` **不再写 `"Curves": []` 占位文件** —— 缺文件应当显式 404，
   而不是伪装成合法数据（这是本次能潜伏一年多的根本原因）。
3. `gallery_src/index.html`：fit 基准改用 `internalModel.width/height`（`mdl.width` 是渲染包围盒，
   个别模型被巨型离屏 quad 撑爆 → 模型偏小/跑出视野，观感即"乱飘"）；
   非 idle 动作按其时长定时回落 idle —— **回落必须用 FORCE**，
   库的 `state.reserve()` 会直接拒绝低于当前优先级的请求（IDLE=1 < FORCE=3）。

### 附带踩坑：自己新写的贝塞尔段序也被 A/B 抓出来了

首次重跑后 A/B 显示新产物 `currentGroup=null`、参数纹丝不动 —— 运行时抛
`Cannot set properties of undefined (setting 'basePointIndex')`。原因：motion3.json 的贝塞尔段
**官方段序是 `[1, c1x, c1y, c2x, c2y, 终点time, 终点value]`（终点在最后）**，
运行时每段消费 `l+=7` 并把 3 个点对读成 `(c1, c2, dest)`、用 `basePointIndex+3` 定位下一段起点。
我按 `[1, c1x,c1y,c2x,c2y, interpolation=0, t, v]` 写（多塞一个"插值"字段）导致整体错位，
而 `segments` 数组是按 `Meta.TotalSegmentCount` **预分配**的 → 越界写成 undefined。
教训：**产物里凡有"运行时按 Meta 计数预分配数组"的字段，计数必须精确**；
已在 `extract_motions.py` 加结构自检（按运行时消费方式重放一遍，计数不符直接抛错）。

**Files**: scripts/extract_motions.py、scripts/reconstruct_live2d.py、scripts/fix_model3.py、gallery_src/index.html

**Tool**: `scripts/diag/l2d_motion_audit.py`（全量健康审计，`L2D_OUT_DIR` 可指向任意产物目录）、
`scripts/diag/l2d_ab.py`（同一模型旧/新 motion 的**渲染级 A/B**：搭 `_ab` 硬链接壳目录 + 无头 CDP，
        手动 `PIXI.Ticker.shared.tick()`+`app.render()` 后才能观测到动画；就是它抓出了上面那个段序 bug）
**Verification**: 新产物应 0 shell / 0 misassign；越域率 23.1% → 2.9%

---

## 11. 立绘合成输出全部乱码/倒转

**Date**: 2026-06-20
**Symptom**: 合成的立绘图像全部错乱，部件位置不对或上下颠倒
**Root Cause**: 两个问题叠加：

1. **手动解析顶点数据格式错误** — 脚本直接从 `m_VertexData.m_DataSize` 按固定偏移读取 position/UV，但 Unity 顶点格式由 Channel 描述符定义，不同 bundle 的 stride 和通道布局不同，固定偏移假设不成立
2. **纹理翻转不匹配** — `data.image` 默认翻转纹理（flip=True），但 Mesh UV 坐标是为 bottom-up 纹理设计的

**Solution**: 使用 UnityPy 内置的正确 API：

```python
# 正确解析顶点
from UnityPy.helpers.MeshHelper import MeshHandler
handler = MeshHandler(mesh_obj)
handler.process()
positions = handler.m_Vertices  # List[(x,y,z)]
uvs = handler.m_UV0            # List[(u,v)]

# 获取未翻转纹理（UV 坐标为 bottom-up 设计）
from UnityPy.export.Texture2DConverter import get_image_from_texture2d
texture_img = get_image_from_texture2d(data, flip=False)

# 最终输出翻转一次（从 bottom-up 转为标准 top-down）
return Image.fromarray(out_arr).transpose(Image.FLIP_TOP_BOTTOM)
```

**Key insight**: ALPA (AzurLanePaintingAnalysis-Kt) 的 `rebuildPainting()` 使用 `tex.getDecompressedData()`（unflipped BGRAB）+ mesh UV，拼完后再翻转输出。我们的 MeshHandler 方案等价。

**Files**: `scripts/synthesize_paintings.py`
**Scope**: 5,859 个 _tex bundle，修复后 5,847 个成功（12 个为 UI/背景等非标准格式）


---

## 12. 舰名显示成 {namecode:NN} 占位符 / 与阵营自相矛盾

**日期**: 2026-09-20  
**现象**: `ship_meta.json` 4494 条里 550 条 cn 是 `{namecode:295}` 之类占位符；`build_gallery_index` 用舰名优先旧 `SHIP_NAME_MAP` 兜底后，出现「weizhang→威尔士亲王 但 faction=重樱」这类名称与阵营打架的错乱。  
**原因（两层，别只修表面）**:
1. **取错表**：`build_ship_meta.py` 舰名取了 `ship_skin_template.name`——那是**皮肤名**，既含 `{namecode}` 未本地化占位符，又会把皮肤主题标题（如"午夜的瑰色电梯"）当舰名。而 `ship_data_statistics.name` 才是**舰名**，实测 4119 条 0 占位符。
2. **旧 SHIP_NAME_MAP 不可信**：手写拼音表有大量错名/截断——`yixian→一线`(实为逸仙)、`vtuber_mio→大空猫`(实为大神澪)、`beianpudun→贝尔法斯特`(en=USS Northampton，实为北安普敦)、`weizhang→威尔士亲王`(en=IJN Owari，实为尾张)。

**解决方案**:
- 舰名一律取 `statistics.name`（经 `painting→ship_group→stats_by_group` 桥，同舰变体共享），`skin_template.name` 另存 `skin_name` 字段备用。ship 级占位符 237→0。
- `build_gallery_index.ship_of`：**仅当 meta 条目已解析出 faction 时才信其 cn**，否则回落 `SHIP_NAME_MAP`+Wiki（保住 `kelei`→可畏/皇家这类 meta 未解析但旧表正确的船，避免反向回退）。
- 判「谁对」的系统性裁判：**磁盘 stem = 正确中文名的拼音**（pypinyin 比对），比逐条目视可靠。
- META/灰烬（`_alter` 形态，faction=META）是舰娘异格，`normalize` 加守卫：折叠前若 `_alter` 基名在 ship_meta 里确为 META 则独立成卡，不并入本体船。56 形态各携独立立绘。

**验证**: 逐船 diff 旧 index，四字段回退=0；ships 954→1008、with_cn 796→899、阵营 445→837。  
**涉及文件**: `scripts/build_ship_meta.py`, `scripts/build_gallery_index.py`


---

## 13. 画廊 Live2D 接入：脚本 404 / 模型放大成局部特写 / 监听器泄漏 / headless 测不出动画

**日期**: 2026-09-20
**现象**: ① Live2D 标签报「运行时加载失败：脚本加载失败 ../vendor/live2d/…」，但 `curl /gallery_v2/vendor/live2d/pixi.min.js` 是 200；② 模型加载成功却只显示一小块局部特写（越刷新越大）；③ 来回切标签后残留交互；④ 无头浏览器里帧哈希恒定，像是"不动"。
**原因**:
1. **`P` 前缀语义搞混**：`const P='../'` 是**资源**相对 `gallery_v2/` 的路径前缀（`Output/` 下其它目录），而 `vendor/` 就在 `gallery_v2/` **内部**（`deploy_gallery.py` 同步进去的）。用 `P+'vendor/…'` 等于 `../vendor/` → 404。curl 用绝对路径 200 属误导。
2. **`fit()` 用了含 scale 的尺寸**：pixi `DisplayObject.width` = 未缩放宽 × `scale.x`。首次 fit 设 `scale=k` 后，`ResizeObserver`（`app.resizeTo` 触发尺寸变化）再次调 fit 时 `min(cw/mdl.width, …)` 里的 `mdl.width` 已是**缩放后**的 187 → 算出 k≈1.79 → 再放大 → 正反馈，最终糊成局部特写。
3. **`window.addEventListener('pointermove'/'pointerup')` 每次 `renderLive2D` 都新绑一对**，且闭包引用旧 `mdl`，`app.destroy()` 不会移除 window 级监听 → 泄漏 + 旧模型被幽灵拖拽。
4. headless Chrome 后台标签 **rAF 被节流**（`app.ticker.count` 几乎不涨），`drawImage(canvas)` 两帧相同是**测试环境假阴性**，非代码不播动画。

**解决方案**:
- vendor 三脚本用 `./vendor/live2d/…`（与 `spine-all.js` 的引用方式一致），资源仍用 `P`。判定办法：在页面上下文 `fetch('../vendor/…')` 与 `fetch('/gallery_v2/vendor/…')` 对比状态码，别信 curl 的绝对路径。
- fit 改为**幂等**：加载后立刻缓存未缩放尺寸 `natW=mdl.width/mdl.scale.x`，维护 `baseK`(适配) × `z`(用户缩放) 与偏移 `ox/oy`，`apply()` 统一由这三者算 scale 与位置；`fit()` 只是把 `z/ox/oy` 归零后 `apply()`。
- 交互监听全部命名函数并存进 `l2State.off()`，由 `stopLive2D()` 统一 `ro.disconnect()` + `removeEventListener`；`renderView`/`closeShip` 开头都调 `stopLive2D()`。拖拽/点击合一：位移 <6px 视为 tap 触发 `tap*` 动作组（`autoInteract:false` 时 pixi 的 `pointertap` 不可靠，别依赖）。
- 验动画：`app.render()` 手动强制渲染 + `app.view` drawImage 取哈希，或直接 `mm.update(dt, core)` 推进时间轴；用 `core.getParameterCount()/getParameterValueByIndex(i)`（Cubism 4 core 私有字段是 `_parameterCount`，`core.parameters` 取不到）。

**验证**: 无头 CDP 6 模型（lafeiii_3/adaerbote_3/aersasi_2/abeikelongbi_3/ninghai_4/pinghai_4）加载+切动作全 OK；真实点击路径（搜索→卡片→皮肤→标签）断言 `activeTab==['live2d']` 且 `dispW/dispH ≤ wrapW/wrapH`；缺目录降级显示失败提示不崩；来回切换 `destroyed:true, reloaded:true`。
**涉及文件**: `gallery_src/index.html`（`renderLive2D`/`stopLive2D`/`loadLive2DRuntime`）


---

## 14. 叠脸门控误判：整框不透明率会被透明背景拉低，须按「脸谱落笔处」量

> **⚠️ 本节的 sat≥30 判据已于 2026-09-27 被 §48 取代**（它把"淡色真脸"整片误判成洞，全库过叠到 49%）。
> 本节仍然成立的部分：**度量必须落在脸谱自身的落笔足迹上**，不能按整框——这条被 §48 原样继承。

**日期**: 2026-09-20
**现象**: 2221 候选扫出 35 个「脸洞」，重渲对比后发现 `leiniya_wjz` 是**回退**——它改前的脸本就画得完整清晰（睁红眼、紧张微笑），叠层把它换成了另一表情（闭眼笑）。
**原因**: 门控用的是 `frac_op = (face rect 区域内 alpha>250 的像素占比) < 0.5`。但 face rect 往往比脸本身大得多，**框内大片是透明背景**：`leiniya_wjz` 框内 49% 不透明（正好是脸本身）+ 48% 透明背景 → 49% 跌破 0.5 阈值 → 误判成洞。反之真洞样本（`i168_2` 98% 透明、`dunkerke_3` 99%）远低于阈值，所以阈值两侧都"看着对"，边界样本必然翻车。
**解决方案**（改判据，不加手工例外表）:
- 先取脸谱、按 rect 尺寸 resize，再**只在脸谱自身 alpha>200 的落笔像素上**量画布现状：`frac_realart = (画布 alpha==255 且 饱和度 sat>=30 且 脸谱落笔).sum() / 脸谱落笔.sum()`，`frac_realart >= FACE_ART_MAX(默认 0.5)` 即判「脸已烤好」不叠。
- 「不透明」**且**「有彩色」两个条件缺一不可：老 bug 产物里的不透明白块（`xipeier_idol`/`gelunbiya`/`xukufu_2` 脸上那块）alpha==255 但 sat≈0，必须算作洞；而 `leiniya_wjz` 的彩色脸 sat>=30 才算真画。
- `canvas.crop()` 用越界框即可（PIL 越界补 0=透明），语义上等于「那里没画」，不必手写钳位。
**度量口径**（复核时别再踩）: 判「叠层是否毁掉已有内容」要按 **脸谱落笔足迹**（新图 alpha>200 处）量旧像素，分「旧=透明 / 旧=不透明白块 / 旧=不透明彩色真画」三类。按整框或按「不透明」粗分会把白块算成"已有内容"，`bangkeshan_2` 这类缺整张头的会被误判成"改前已有 37% 内容"。
**验证**: 改判据后重渲 35 张逐字节比对——**只有 `leiniya_wjz` 行为改变**且其输出与旧正式产物逐像素相同（=自动不叠），其余 34 张与改前临时渲染完全一致；`z43`(42.3%)、`bangkeshan_2`(36.5%)、`gelunbiya`(30.5%) 等高"彩色占比"者经目视确认改前是淡化半脸/白块/缺头，仍正确叠。
**涉及文件**: `scripts/compose_paintings_v2.py`（`FACE_ART_MAX`、`render()` 内叠脸段）


---

## 15. Live2D「怎么点都不触发」：只认 tap 组名 + 缓存坐标点空 + 部位框嵌套抢判

**日期**: 2026-09-20
**现象**: 用户反馈 Live2D 标签里点角色没有任何反应；接入部位点击后又出现「点 Body 播的是 Head / Special」。
**原因**（三层，逐层被实测推翻）:
1. **组名假设错**：首版实现写 `groups.find(g=>/^tap/i.test(g))`，以为动作组叫 `tap`。实测 260 模型里 **256 个用的是 `HitAreas[].Name`（`Head`/`Body`/`Special`）**，配套组名既有 `Head` 也有 `TapHead`/`touch_head`，而**根本没有裸 `tap` 组** → `tapG` 恒为 null → 点了当然不播。
2. **缓存坐标点空**：改成「按 HitArea 的 drawable 三角面做点在三角形内」后仍有漏。原因是**判定框会随呼吸/物理实时位移**，加载时算好的中心点在实际点击那一刻已经移走 → 命中不到。
3. **嵌套框抢判**：部分模型（如 `yingrui_3`）的 `Head` 框大到**压住 Body/Special**，且 `Special` 框嵌在 `Body` 框内。按 `HitAreas` 顺序取首个命中 → Body 永远点不到；改按「面积最小框」→ 点 Body 中心被更小的 Special 抢走。
**解决方案**:
- 组名一律取 `internalModel.settings.hitAreas[].Name`，**它本身就是动作组名**（全库 768 个判定区对 `FileReferences.Motions` 键 **768/768 精确匹配**，无需任何模糊映射）。
- 命中判定**在点击瞬间实时读** `coreModel.getDrawableVertexPositions(getDrawableIndex(Id))` 求包围盒，不缓存。坐标换算：`mdl.toLocal(屏幕点)` 得模型局部 px，再 `/ internalModel.pixelsPerUnit` 得 Cubism 单位（约定已用 `toGlobal(x*ppu, y*ppu)` 反查屏幕验证，头部框落在屏幕上方，无需额外翻转）。
- 多个包含框时取**归一化中心距离**最小者：`s = dist(click, boxCenter) / max(halfW, halfH)`（0=正中，1=边缘）。同时兼容重叠与嵌套。
- 无 `HitAreas` 的 4 个模型回落到 `tap*/touch*` 首个组。
**验证**: `scripts/diag/hit_verify.py` —— 无头 Chrome 里对每个部位算中心、派发 `pointerdown`/`pointerup`，断言 `motionManager.state.currentGroup === 部位名`：**40 模型 120/120 全中**；对比修复前的「按顺序+缓存坐标」只有 13/18。
**通用教训**: ① 别拿社区/直觉命名当权威，先跑一遍全库统计（`Head/Body/Special` 精确匹配 768/768 这条事实，一次统计就出来了）；② 交互判定的几何数据要么实时取、要么承认会失效，动画中的模型没有"静态坐标"可言；③ 重叠区域的选择规则要显式设计（顺序/最小/最近），默认"取第一个"往往是最坏选择。
**涉及文件**: `gallery_src/index.html`（`renderLive2D` 内 `hitAreas`/`hitAt`/`onUp`）


---

## 16. Live2D 交互层：滚轮劫持页面滚动导致"模型乱动"、兜底动作乱播、拖拽卡住

**日期**: 2026-09-20
**现象**: 用户反馈 ①「皮肤3 模型偏移、在乱动」② 截图里提示条显示 `touch_drag8` 且**没有**「部位 X →」前缀，画面是触手局部特写（安妮女王复仇号）。
**原因**（都是交互层设计错误，不是渲染/数据错误）:
1. **滚轮被 `preventDefault` 劫持**：鼠标经过模型时，用户本来在滚列表，页面不动、模型却一路放大（上限 12 倍）并随光标锚点累积平移 → 观感就是"模型自己乱动、位置不对"。
2. **点空白也播动作**：`fallbackG = groups.find(/^tap|^touch/)` 对**所有**模型生效，于是点哪儿都蹦一个 `touch_drag*`。而 `HitAreas` 判定失败时（当时还用了缓存坐标）就走这个兜底 → 用户看到"没有部位前缀的怪动作"。
3. **拖拽状态会卡住**：只处理了 `pointerup`，没处理 `pointercancel`/窗口失焦。浏览器在手势/滚动时发的是 cancel，`dragging` 一直为 true → 之后每次鼠标移动都在平移模型。
**解决方案**:
- 缩放改为 **Ctrl/⌘/Alt + 滚轮**才生效；裸滚轮不 `preventDefault`，还给页面滚动。
- 兜底**只给没有 `HitAreas` 的模型**（本库 4 个：chaijun_6/antu_2/baifeng_3/jinluhao_3）；有判定区的模型点框外就是什么都不播（与游戏一致）。
- 加 `pointercancel` + `window.blur` → `dragging=false`；平移量钳制在 `max(wrapW,wrapH)*0.6` 内，防止把模型拖丢。
- 命中判定加 **2% 容差**（只吸收"算探针点→派发事件→处理器读框"之间几十毫秒的呼吸/物理位移）。**不能给大**：画布四周有大量透明边距，8% 时实测把 wrap 左上角（视觉上明显空白）判成了 `Special` 命中。
**踩坑（测试侧，比产品侧更耗时间）**:
- **包围盒 vs 三角面**：改用 Cubism 原生"点在三角面内"精确判定后，`yingrui_3`/`z46_3` 反而更差——这两个模型 Touch 部件的三角面**连自己的顶点重心都不包含**（数据不规整）。包围盒方案实测 766/768，故保留包围盒。
- **探针坐标往返误差**：`m.toGlobal(单位*ppu)` → 拼 client 坐标 → 处理器再 `m.toLocal()` 反解，在极端坐标处（如模型单位 -9,-9）误差被放大到落回 Body 框内，导致"点空白不该播"这条断言恒失败。教训：**跨坐标空间的自动化探针，断言要落在产品语义上**（"不应播出兜底组 touch_*/tap*"），不要落在"我猜它不该命中"上。
- **判"有没有播"要读 `state.currentGroup` 且注意它会自动归 null**：idle 播完后 `currentGroup` 变 null（实测无操作 3 秒内恒 null），所以"变了"才说明有东西播了。
- 两个 chrome 实例并发跑 CDP 会互相抢，报 `Execution context was destroyed`；串行跑即可。
**验证**: `scripts/diag/interact_verify.py`（裸滚轮零影响 / Ctrl+滚轮才缩放 / cancel 后漂移 0 / 有判定区的模型不播兜底组 / 点头部播 Head）4 模型 **ALL PASS**，含用户报的 `aersasi_2`、`aersasi_3`、`anninvwang_2`；`hit_verify.py` 全量 260 皮肤复跑 **767/768**（`kelaimengsuo_2` 由 2% 容差修好，残留 `z46_3` 见下）。
**涉及文件**: `gallery_src/index.html`（`renderLive2D` 内 `hitAt`/`onWheel`/`onUp`/`onCancel`/`clampPan`）

---

## 18. 「4 个模型没有判定区」是误判：HitAreas 只认 `Head/Body/Special` 组名，新皮肤用的是 `touch_*`

**日期**: 2026-09-21 查出 → **2026-09-22 已实施并验收**　**状态**: ✅（规则已并入 `fix_model3.py`，13 模型真实判定区落地）

**现象**: 给 §2.5 那 9 个从未还原的 bundle 在临时目录重建后，发现它们和 `chaijun_6/antu_2/baifeng_3/jinluhao_3` 一样——`model3.json` 里的 `HitAreas` 是占位 Id（`HitArea`/`HitArea2`），前端 `core.getDrawableIndex("HitArea")` 取不到部件 → 判定区被过滤空 → 走 §16 的兜底（点哪儿都蹦一个 `touch_drag*`）。此前一直把这 4 个模型记成「资产本身没有判定区」。

**原因（是生成规则漏了一半，不是资产缺口）**:
1. `fix_model3.py` 不生成真实 HitAreas；真实 HitAreas（`TouchHead/TouchBody/TouchSpecial`）当初是另一条一次性路径写进 256 个 `model3.json` 的，**生成器只认组名 `Head`/`Body`/`Special`**。
2. 而这 13 个模型的 moc3 **同样带 `TouchHead`/`TouchBody`/`TouchSpecial` 部件**（逐字节扫 moc3 字符串可证），且动作组里**同样有** `touch_head`/`touch_body`/`touch_special` —— 只是命名风格是「新皮肤用 `touch_*`」，老模型用 `Head/Body/Special`（同一模型常两套并存）。
3. → 结论作废：`al-live2d-asset-quirks` 记忆与 §6.7/§16 里「无判定区的 4 个模型」「兜底只能给这 4 个」都不成立；兜底现在实际掩盖了 **13 个**本可以做按部位点击的模型（9 新 + 4 旧）。

**解决方案（待实施的方案，已验证前提）**: 把 HitAreas 生成为「moc3 里存在的 `Touch<X>` 部件 ↔ 该模型真实存在的动作组」配对，Name 取**实际组名**（`Head` 或 `touch_head` 皆可，前端 `index.html:458` 已按 `groups.includes(name)` 再小写回落匹配）；映射规则 `TouchHead → {Head, taphead, touch_head}` 逐个试。落地位置：`fix_model3.py` 新增该字段（当前它只补占位），或独立脚本 `scripts/diag/`。**改完必须证**：① 260 个既有 `model3.json` 除 `HitAreas` 外字段零变化；② `hit_verify.py` 全库复跑命中率不低于 767/768；③ 这 13 个模型点击头/身/特殊各自命中、点框外不播（兜底路径此后应为 0 个模型触发）。

**涉及文件**: `scripts/fix_model3.py`（占位 HitAreas 在 52-63 行）、`gallery_src/index.html`（`hitAreas` 过滤与 `fallbackG`）、`scripts/diag/hit_verify.py`（验证工具）

**落地（2026-09-22）**：`fix_model3.py` 新增真实 HitAreas 生成——`moc3 含 Touch<X> drawable` ∩ `模型真实存在的动作组`（候选 `X`/`tap_X`/`touch_x`/小写回落，Name 用实际组名），**且只替换占位 Id ⊆ {HitArea,HitArea2}**，256 个既有正确产物一律不动。跑 `scripts/fix_model3.py` → 逐字节 diff：**仅 13 个 model3.json 变、且只 HitAreas 字段变**（256 mtime 未动，回滚备份 `.diag/m3_snap/*.bak`）。`scripts/diag/hit_verify.py` 全库分块复跑覆盖 **269/269、806/807 命中**（较基线 767/768 净增 39=13×3 全中），13 模型点头/身/特各 **3/3**；点框外不播（`fallbackG` 因判定区非空自动关闭）。唯一残留 `z46_3` Special 框嵌 Body 属 §6.7/§16 已知歧义，未回退。占位段代码位置随本次改动迁移到 Motions 定稿之后（真实生成需最终动作组列表）。

## 19. 换入 9 模型后「bunao_3/guanghui_9 的 idle 不动」——是采样时机假阴性，不是数据缺陷

**日期**: 2026-09-22　**状态**: ✅ 已澄清（误报），并确立 Live2D 动画验证的正确判据

**现象**: 把 `.diag/l2d_new9` 的 9 个模型换入并重建 index 后，用无头浏览器做内容判据抽验，`bunao_3`、`guanghui_9` 的 `idle` 反复读出 `moved=0`（多次不同写法：5 个固定 id 采样、`startMotion('idle',FORCE)` 后采、等到 9~12s 后两次快照比对）。一度判定这 2 个 idle.motion3.json「结构合法但运行时不生效」。

**排查（逐层排除）**: ① moc3 参数成员——把 idle 全部 57/146 条 Parameter 曲线 Id 与该模型 `core._parameterIds`（moc3 派生）比对，`NOT_in_moc3=0`，映射没问题（审计 `misassign 0` 亦印证）。② 换别的动作组对照：同模型 `home`/`touch_head` 都能驱动 45/157 个参数 → **模型本身没问题**。③ 读运行时 motion 对象：`_isLoop:false`、`_loopDurationSeconds` 正常；关键——**运行时把每条 idle 都解析成非循环**（`isLoop:false`），idle 播完一遍即回静帧，这是**全 269 模型一致的既有管线特性**，不是本轮新模型特有。

**根因（判据缺陷，非数据缺陷）**: idle 非循环 ⇒ 短 idle（benningdun_2 5s / bunao_3 8s / wuzang_4 6s）在「载入后等 9s + 再采样」时**早已播完、参数回到静止基准**，于是两次快照逐参数相等 → 假报 `moved=0`；长 idle（feiteliekaer_4 15s、sebao_2 22s）还没播完才碰巧读到 `moved>0`。另外手动 `startMotion('idle',FORCE)` 与画廊自动播会相互打断，进一步放大假阴性。

**正确判据（务必照此验证 Live2D 动画）**: **在该 clip 时长内高频密采全参数**——载入后立刻进入采样循环（每 ~420ms 一帧、手动 `PIXI.Ticker.shared.tick(16.7)+app.render()` 推帧），**累积每个参数跨帧 min/max**，最后统计 `max-min>1e-3` 的参数个数。**判据 = 播放窗口内被 idle 驱动的参数条数**，而非某一时刻两点之差、更非 `state.currentGroup`/组名标签（空壳/播完都会给出误导性标签）。按此密采：9/9 全绿（benningdun_2 45 / bunao_3 57 / feiteliekaer_4 90 / gangyishawa_3 58 / guanghui_9 143 / pulimaosi_3 50 / sebao_2 29 / shi_3 75 / wuzang_4 144 条参数变化）。

**旁证坑**: 无头下画布 `toDataURL()` 帧哈希对这些模型恒 `frameChanged=false`（swiftshader 上 `app.render()` 未必即时回读，或透明边距使 200×200 缩采样看不出变化）——**别用帧哈希当动画真值**，读 `coreModel.getParameterValueById` 的参数轨迹才可靠。

**涉及文件**: 一次性验证脚本（未入库，`.diag/l2d9_diag*.py`）；权威判据已并入技能 `live2d-web-runtime-integration` §7。`scripts/diag/l2d_sweep.py` 已按本条重写（2026-09-22）：**Python 侧逐条 evaluate**（修掉旧版单次 evaluate 卡第一条不返回 + 单 Chrome ~110 后 WebGL 断连）、**每 60 模型重载页面**、内容判据改为**播放窗口内密采全参数取跨帧 min/max**，全库 **269/269 通过、0 静态**；并同法修 §6.11 里 bunao_3/guanghui_9 的「idle 不动」误判。


## §19. Live2D「动作做得快/赶着完成 + 悬停乱触发」双击根因（用户 2026-09-23 实测反馈）

**日期**: 2026-09-23　**状态**: ✅ 已修复并回归（前端层，不动任何 motion 数据）

**现象**: 用户反馈 Live2D 「点击一次后动作快快的，像是赶着完成；鼠标悬停其他部位自动触发其他动作，原来的动作还没做完就被切，也是做得赶赶的」，并怀疑网页端不适合做 Live2D（参照 l2d.su）。

**根因一（悬停/乱触发）**: `gallery_src/index.html` 的 `hitAt` **没有「点在框内」包含判定**，取的是「全图最近框」——点画布任意位置（含视觉空白处）都会触发最近部位的动作，动作被反复打断，观感即「做得赶/快/没做完就切」。而 §6.7 引以为据的回归脚本 `interact_verify.py` 有个致命笔误：输出键是 `noAction`，断言却查不存在的 `noFallbackGroup` → 该项**恒不触发、永远绿灯**，「点空白不播」半年未被真正验证过。

**根因二（idle 早夭，动画判据之外的体感元凶）**: vendored pixi-live2d-display 0.4.0 的 cubism4 模块 **`setIsLoop()` 只有定义、全 bundle 无调用点**（字符串搜索证实），`Meta.Loop:true` 被无视 → **任何动作只播一轮**，idle 4s 后模型回静帧（§18 已观察到此现象当时仅当作"验证判据注意项"）。用户打开皮肤看到的多是「静帧+物理」，点击后动作播完又回静帧，与游戏里 idle 常驻的观感差距巨大。

**排查要点（复现证据链）**: ① 无头探针给 `mm.startMotion` 打钩 + `currentGroup` 时间线：点部位后动作**完整播满自身时长**（12.7s 不早退），证明不是速度快而是被切；② 纯 `pointermove`（无按键）悬停**零触发**、`mdl.eventNames` 无库层监听（autoInteract 确已关）——「悬停」实为点空白处误触最近部位；③ 静默 12s 采样：初始 idle 只活一轮即 `currentGroup=null`；④ 运行时包内搜 `setIsLoop(` 仅 1 处=定义本身。

**修复**: ① `hitAt` 加包含判定（2% 容差，框外一律 null；框重叠时归一化中心距就近取框保留）；② 新增 **idle 看守者** `armIdleLoop`：idle 每次启动后按 `Meta.Duration-120ms` 重开一轮（交叉淡入无缝循环），与 `scheduleIdle`（非 idle 动作按时长回落）以 token 互锁、组件销毁时作废；③ `onDown`/`onUp` 加 `e.button!==0` 右键防误触；④ `interact_verify.py` 断言键改正为 `noAction`。

**验证**: 修复后无头复测——idle 看守者生效（12s 静默采样 `currentGroup` 全程 idle，参数持续驱动）、`interact_verify.py` 4 模型全过（**修正后的**空白点击断言 `noAction:true` 首次真正变绿）、`hit_verify.py` 全量 269 皮肤复跑（见 PROJECT_STATUS）。

**涉及文件**: `gallery_src/index.html`（部署 `scripts/deploy_gallery.py` 同步 `Output/gallery_v2/`）、`scripts/diag/interact_verify.py`；经验已并入技能 `live2d-web-runtime-integration` §3.2b/§4/§8。

## §20. Live2D 点击命中「张冠李戴」真根因：顶点坐标系与屏幕坐标系差一次「平移+Y翻转」

**日期**: 2026-09-23　**状态**: ✅ 已修复（前端换算 + 两个验证脚本坐标修正），全量回归见 PROJECT_STATUS

**背景**: §19 修复「全图最近框无包含判定」后，做 l2d.su 同款「判定区可视化」时发现框画在画布左上角而非模型上，深挖牵出更大的坑：

**两套坐标系（实测证据 `.diag/_probe_affine.json`）**：
- `coreModel.getDrawableVertexPositions()` 返回 **V = Cubism 原生坐标**：以画布中心为原点、**y 轴向上**，量纲为画布单位（本项目模型 = 18×18）。
- `mdl.toLocal()` 再除 `pixelsPerUnit` 得 **P 坐标**：左上角原点、**y 轴向下**，量纲同为画布单位。
- 换算：`Vx = Px - cux/2`，`Vy = cuy/2 - Py`（`cux=im.width/ppu`，`cuy=im.height/ppu`）。验证：可见头/胸/髋三点经翻转映射后分别落入 Head/Special/Body 框，恒等映射全部脱靶。

**为什么此前的命中系统「测试全绿但用户感受乱」**：旧代码把 V 框与 P 点当同一空间比较，而 hit_verify 的合成点击也用同一错误映射（`toGlobal(顶点*ppu)`），**自洽闭环**——点永远「命中」自己那份几何，却与屏幕上看得见的内容完全错位（lafeiii_3 上点胸口实际触发头部动作）。回归脚本全部自洽时，绿不代表对。**教训：验证点击路径必须有一个不经过被测映射的锚点（如截图目视/可见语义点反查），否则只是在验证自洽性。**

**修复**：产品侧 `hitAt` 入口统一 `P2V` 换算；判定区可视化 `V→P→stage` 手工仿射（`stage = mdl.pos + P*ppu*scale`，apply() 无旋转无锚点故安全）；`hit_verify.py`/`interact_verify.py` 合成点击改 `V2P` 后派发（与产品互逆，测的才是真路径）。

**连带发现**：无头下 idle 看守者轮换间隙（每次 startMotion 重 fetch 动作文件 ~1.5s）会使 `currentGroup` 短暂为 null——`interact_verify` 的「空白点击不播动作」断言须把 `after=null` 视为通过（null=重取数间隙，非动作触发）。

**涉及文件**: `gallery_src/index.html`、`scripts/diag/hit_verify.py`、`scripts/diag/interact_verify.py`；**可复用工具已入库**：`scripts/diag/l2d_coord_forensics.py`（坐标系取证，可见头/胸/髋三点反查）、`scripts/diag/l2d_inspector_verify.py`（判定区可视化+参数面板验收）；技能 `live2d-web-runtime-integration` §4 已补坐标系换算条目，流程见 `docs/WORKFLOWS.md` WF-16。

## §21. Live2D「部件各动各的、像刚学建模的人做的」总根因：motion3.json 贝塞尔控制点写成了归一化分数

**日期**: 2026-09-23　**状态**: ✅ 安土样本已修复并经权威基准验收（`l2d_ref_diff.py` PASS）；⚠️ **全量重导未执行**，见 PROJECT_STATUS §6 待办

**背景**: 用户报三症状——① 初始就一直在有点快地动；② 点击触发的动作不太准、有点穿模；③ 总体不自然、动作应该更慢。前两轮我先后误判为「呼吸层」和「by>3 拉直护栏」，都被实测否掉。**转折点：用户提供 l2d.su 参考查看器的录屏**，据此拿到同模型的权威 motion3.json 作外部基准，才把问题一次锁定。

### 权威基准怎么拿（下次直接用）
l2d.su 静态 CDN 挂着同批模型的原始导出，路径规律（从 `/assets/index-*.js` 里 grep `model3.json` 模板反查得到）：
```
https://static.l2d.su/azurlane/live2d/<key>/<key>.model3.json
https://static.l2d.su/azurlane/live2d/<key>/motions/<group>.motion3.json   # 注意是 motions/，我们是 motion/
```
只覆盖部分模型（抽样 8/14 命中）。验收工具已入库：`scripts/diag/l2d_ref_diff.py`。

### 根因①（主因，影响所有贝塞尔段）：控制点单位错了一个量级
`scripts/extract_motions.py` 旧实现把贝塞尔控制点按**归一化分数**写出：
`Segments: [1, 1/3, by1, 2/3, by2, t, v]`。但运行时解析器是**直读绝对坐标**、不做任何还原：
```js
case Bezier:
  points[a]   = new j(seg[l+1], seg[l+2])   // (时间, 值) —— 无归一化还原
  points[a+1] = new j(seg[l+3], seg[l+4])
  points[a+2] = new j(seg[l+5], seg[l+6])
```
于是控制点被读成「**t=0.333 秒、值=0.667**」。对一个跨 7.5→8.983 秒的段，控制点落在区间之外、值接近 0 → **每条贝塞尔都先猛蹿到≈0 再跳到目标值**。这就是"部件各动各的"的全部来源。
正确写法是 Unity Hermite 的等价控制多边形（绝对坐标）：`c1=(t0+dt/3, v0+out·dt/3)`、`c2=(t1−dt/3, v1−in·dt/3)`。

**⚠️ 但"格式正确"不等于"验收通过"。** 实测三种写法对参考版的逐曲线偏差（安土 idle，121 点采样）：
| 写法 | 偏差中位 | 偏差>0.5 的曲线 | 最甚 |
|---|---|---|---|
| ① 归一化控制点（旧线上） | 1.376 | 92/98 | ParamAngleZ 9.35 |
| ② 绝对控制点·全贝塞尔 | 0 | **88/278** | **296**（头发角参数） |
| ③ **关键帧+线性（已采用）** | 0 | 11/278 | 1.95 |

②虽然符合 Cubism 规范，但 Unity **密集键**的切线字段本就不该当 Hermite 切线用（算出的曲线会飞出去），
所以**最终验收配方是 `L2D_MOTION_LINEAR=1 L2D_MOTION_EMIT_CONST=1`**，不是 `ABSOLUTE_CP`。
`extract_motions.py` 里两个开关都留着，注释已标明哪个通过验收。

**量化验收（安土 idle，逐曲线 121 点采样比对参考版）**：线上旧版偏差中位 **1.376**、92/98 条曲线偏差>0.5、最甚 `ParamAngleZ` 差 **9.35°**；修正后偏差中位 **0.0**。

### 根因②：只读 `m_StreamedClip`，丢掉 `m_ConstantClip` 的定值曲线
Unity AnimationClip 的曲线分装在三处，`genericBindings` 顺序 = **[streamed][dense][constant]**（安土 idle 实测 98+0+180=278，且名字零冲突）。旧管线只读 streamed → **安土 idle 只导出 98/278 条曲线**。
定值曲线不是惰性的：Cubism 只对「本 clip 有曲线的」参数施权，缺曲线的参数在切动作时**停在上一个动作留下的值上**，于是被 `touch_*` 动过的手臂/身体回不到静止位 → 部件错位。参考版 idle 的 `CurveCount` 正是 **278**。
补全后：安土 104 个动作曲线总数 9441 → **29945**，`idle` 与参考版逐字段一致（278 条 / 1962 段）。

### 根因③：运行时三坑（前端侧，与数据无关但同样致命）
1. **`Meta.Loop` 被忽略**：vendored `pixi-live2d-display` 0.4.0 定义了 `setIsLoop()` 但全 bundle 无调用点。旧代码用前端定时器"假装循环"，而 `startMotion` 是 async（返回 Promise）→ `!==false` 恒成立 → **被 `state.reserve` 以"Motion is already playing"拒绝时前端毫无察觉**，实测 idle 播 9.1s 后**冻结 9.2s**（`currentGroup=null`、队列 0 条、参数纹丝不动）。修法：给 CubismMotion 本体 `setIsLoop(true)` + **`setIsLoopFadeIn(false)`**（不设后者则每次回绕重置淡入起点，权重归零重爬，观感=每隔 N 秒被拽回去）。
2. **`mm.groups.idle` 默认 `'Idle'`** 与我们的 `'idle'` 不匹配 → 库自带的"动作播完自动回 idle"一直静默失效（这才是需要①的原因）。对齐后前端**零定时器**，冻结消失。
3. **`_startMotion` 每次先 `queueManager.stopAllMotions()`** → 旧动作被瞬间掐死、**完全没有交叉淡化**。队列管理器 `startMotion` 内部本来就会给现存条目 `setFadeOut`，删掉那行 stop 即恢复官方行为。
实测：修复后 30s 内 `startMotion` 调用 **0 次**、`currentGroup=null` 采样 **0 个**。

### 根因④：运行时自加的 Cubism2 式呼吸层
`Cubism4InternalModel` 无条件挂 `CubismBreath`，每帧在动作**之后**再 ADD `ParamAngleX ±7.5°@6.5s / Y ±4°@3.5s / Z ±5°@5.5s / BodyAngleX ±2°@15.5s / ParamBreath ±0.25@3.2s`。而全库 74~85% 的 idle **本就自带动这些参数的曲线** → 头部双驱动。铁证：安土 bundle 的 MonoBehaviour 组件清单是官方 Unity Cubism SDK（`CubismMoc/Model/Parameter/PhysicsController/Raycaster/MouthController/CriSrcMouthInput/Live2dChar`），**没有任何 Breath 组件**。修法：`im.breath.setParameters([])`。

### 根因⑤：命中判定用包围盒，而标记四边形可以是斜的
游戏侧是 `CubismRaycaster` 对 `Touch*` 部件做**三角形 raycast**。这些标记是 4 顶点不可见 quad；安土是正矩形（四边形面积/包围盒=1.000，两种判定逐点等价），但 `yingrui_3` 只有 **0.489~0.755**、`z46_3` 0.645~0.942 → 包围盒把判定区放大最多 2 倍，点旁边空地也触发。修法：包围盒预筛 + 两三角包含（strip 序 `v0v1v2`+`v1v3v2`）、重叠取最小框。
**⚠️ 顶序必须按三角带处理**：直接 `drawPolygon(v0,v1,v2,v3)` 会画成自交蝴蝶结（顶点序是 TR,TL,BR,BL）；无自交环序是 `[0,1,3,2]`。已实测 5 个模型 `stripArea == 凸包面积`，证明带序假设成立。

### 根因⑥：判定区只登记 3 个 + 淡入淡出被硬写
moc3 里的 `Touch*` 标记远不止 Head/Body/Special——安土有 **76 个**（TouchDrag1-24、TouchIdle1-47）。`fix_model3.py` 原来只映射三个 → 点电梯按钮等区域毫无反应。现补登后安土 3 → **57 个**（实测与核心三框**零重叠**，不改判已有点击）。
另外旧版给 104 条动作全部硬写 `FadeInTime/FadeOutTime: 0.5`，而参考版一条都不写、交给运行时默认（**idle 2s / 动作 0.5s**）→ 回落 idle 快了 4 倍，反应没收尾就被拽回去。现已改为：非 idle 全删；**idle 显式拆开 `FadeInTime:2.0 / FadeOutTime:0.5`**（库里 fade-in/out 共用同一个 idle 默认值，而 idle 现在带 278 条曲线，淡出 2s 会在点击后继续拖尾 2 秒把参数往回拽 = 用户报的"手臂乱动一下"）。
参考版还有 `Groups: EyeBlink[ParamEyeLOpen,ParamEyeROpen] / LipSync[ParamMouthOpenY]`，我们缺 → `internalModel.eyeBlink` 一直是 undefined（模型不眨眼）。补上后 blink=true。

### 已排除的假设（别再走这些弯路）
- **参数映射错**：`l2d_motion_audit.py antu_2` = 104/104 ok、空壳 0%、错配 0%、时长与源一致。
- **假参数名**：`Param42`/`Param44` 这类看着像占位符的名字**是 moc3 里的真名**（美术自动生成），98/98 条曲线 Id 都能在 moc3 字符串表命中。
- **值被硬钳**：98/98 条曲线的动画范围都在 moc3 合法量程内。
- **重名/禁用参数**：425 个 CubismParameter 名字唯一、`m_Enabled` 全为 1。
- **阶梯段缺失**：参考版 1070 条阶梯段里 **1067 条两端值相同**（与线性完全等价），真跳变仅 3 条且都在 1 帧内 → 补它没有视觉收益。
- **切线字段读错**：`f1=入切线 / f2=出切线 / f4=值` 已由「首键值 == 参考帧基准 98/98」钉死；用它们算 Hermite 与导出文件里的贝塞尔可精确互推。
- **PartOpacity 丢失**：安土四个动作参考版与我们都是纯 Parameter，零 PartOpacity。
- **`ParamMouthOpenY=1` 这条定值曲线不该补成"张嘴"**：游戏口型由 `CubismMouthController`+`CubismCriSrcMouthInput` 音频驱动，补上只会让嘴一直张着。

### 天花板（不是 bug，别再去攻）
参考版比我们在插值上多出的只有 **642 条贝塞尔段**（约占段数 7%）。用四种候选切线公式拟合它的控制点，最高只命中 **16.7%**（且那是"切线=0"的平凡情形）——**它的控制点来自我们拿不到的数据**（l2d.su 大概率有游戏原始 Live2D 发行包里的 motion3.json，我们手上只有 Unity AssetBundle）。
所以可达上限 = 曲线集合 100% 一致 + 关键帧时间/值 100% 一致 + 约 93% 段类型一致，剩余用线性弦近似（表现为缓动略少）。`l2d_ref_diff.py` 的 WARN 线因此校准在 **12%**（安土实测 3.8%~9.6%）。

### ✅ 已解决（2026-09-23 补记）：播完 `touch_idle*` 后判定区集体出画、回 idle 不恢复

**根因**：Cubism 只对"本 clip 有曲线的"参数施权，**缺曲线的参数停在上一个动作留下的值上**。
`touch_idle1`（4.65s、252 条曲线、Loop=false）驱动的参数里有 **15 条是 `idle`（278 条绑定集）从不驱动的**，
其中含整体位移 → clip 末帧值永久残留 → 57 个判定区全部被甩出画布（核心三个一起到 `(-36.37,-52.81)`）。
静止态实测本就 53/57 在画布外（只有核心 3 个 + `touch_idle1` 真可点），
所以"进 1 层之后点哪儿都没反应"。游戏侧靠 `change_in`/`home` 状态机复位，Web 运行时没有状态机 → 同一份数据在游戏里不暴露。
> ⚠️ **2026-09-27 更正（本条原句）**：这里把出画原因写成「**编辑器遗留的停放标记**」是错的。
> 逐动作组实测（`l2d_hit_offcanvas.py --sweep`）证明：那些 `TouchIdle*/TouchDrag*` 是**换装/互动按钮的停放位**，
> 播对应动作时随部件一起进画面才可点（奇尔沙治皮肤2 静止态 4/26 在画布内，播 `idle1/main_*/mail` 时到 7~10 个）。
> 数据没问题，别去 `fix_model3.py` 里删它们；当时的"点不到"是参数残留把**核心三个**也甩出了画，与本句无关。
> 全条取证与修法见 **§51**。
**定位手段**：对 motion3.json 求 `{Curves[Target=="Parameter"].Id}` 的差集（该 clip 集 − idle 集），不靠猜。
⚠️ `Id` 有两种形态（纯字符串 / `{string:…}`），判据要兜两种。

**修法**（`gallery_src/index.html:428-493`）：在 §已有的 `createMotion` 补丁里顺手登记每组驱动的参数集（零额外请求），
`play()` 记 `played` 组名，回到 idle（或队列空）后由一个 ticker 把「播过的 clip 驱动、idle 不驱动」的参数
**线性写回 moc3 默认值**（`getParameterDefaultValue`）。三道防误伤约束：① 只碰这批参数，物理/眨眼/口型一律不动；
② 只在回 idle 时触发；③ 先等 `REST_DELAY=400ms` 让上一条 clip 淡出跑完，再 `REST_MS=700ms` 渐变（硬赋值会跳帧）。

**踩坑（两条，第二条更耗时间）**：
- **`paramSets[idleGroup]` 为空 ⇒ 复位永远不触发**，且是 `if (!idleS) return` 的**静默**失效。库的预加载分支为
  `switch(config.motionPreload){ default: e=[this.groups.idle] }`，`motionPreload:'ALL'` 或组名恰为库默认 `Idle` 的模型必踩
  （本项目组名是小写 `idle`、而 `mm.groups.idle` 要到补丁里才改成小写，默认路径不预加载故躲过）。
  对策：另 fetch 一次 idle 各条 json 登记参数集，顺带补 `Meta.Loop`；**判据必须显式断言 `paramSets[idleGroup].size>0`**。
- **验证脚本绕过页面入口会造出假阴性**：复位逻辑挂在页面的 `play()` 上，探针若直接 `mm.startMotion(g,0,FORCE)`
  就整层绕过它，于是"修复无效"其实是"根本没进被改的那段代码"——**曾据此把一个正确的修复误判成无效**。
  现 `l2d_touchidle_probe.py` 改成 `sel.value=grp; sel.onchange()`，并回读 `mm.state.currentGroup`
  以区分「静默失败」与「没复位」；入口不存在时**显式报错**，不许回落假路径。

**已排除的假设**：(a) 快照"进动作前的全部参数值"再回写 —— 不需要，这批参数在静止态本就没人动，
moc3 默认值 ≡ 静止位，且与快照时机无关；(b) 判定区几何回退到加载时快照 —— 治标，模型真被移走了画面仍错；
(c) 接受 —— 否决，游戏侧会复位，我们不做就是功能缺失。

**验证**：`scripts/diag/l2d_touchidle_probe.py antu_2 touch_idle1` → before 出画 53 / mid 57（clip 确实生效）/
after **53（与 before 相等）**，位移 >0.3 的判定区数 **0**；`interact_verify.py` 同期仍 ALL PASS。

**涉及文件**: `scripts/extract_motions.py`（新增 `L2D_MOTION_ABSOLUTE_CP` / `L2D_MOTION_EMIT_CONST` / `L2D_MOTION_BEZIER_CLIP` 开关）、`scripts/fix_model3.py`（淡入淡出/EyeBlink·LipSync 组/Touch* 判定区三项）、`gallery_src/index.html`（运行时四补丁 + 非 idle 参数残留复位 + 四边形命中 + 动作下拉排序）；新入库取证/验收工具 7 个：`l2d_ref_diff.py`（**权威基准比对，全量验收就靠它**）、`l2d_after_fix_check.py`、`l2d_restart_cadence.py`、`l2d_param_ranges.py`、`l2d_hit_overlap.py`、`l2d_touchidle_probe.py`、`l2d_fidelity_probe2.py`。流程更新见 WF-16。可复用做法见 `.agents/skills/live2d-web-runtime-integration/SKILL.md` §3.8 与 §7.2。

---

## §22. `sharecfgdata/*` 打不开：不是 UnityFS、也非混淆密码，而是「索引表 + 切片读」的自定义二进制容器

**症状**：34 张配置表（含字幕要的 **`ship_skin_words` 皮肤台词表**）UnityPy 解析出 0 对象；表名能猜到、文本拿不到。此前只能记一句「自定义加密、本机无解」，导致台词/声优名/阵营名表/385 新皮肤归属全部卡死。

**根因（2026-09-23 逆向确认，`tools/sharecfg_re/` 独立小项目）**：这套表**大概率不是加密**，而是走 `LuaConfDataReader` 的随机访问容器。证据来自 `libil2cpp.so` + `global-metadata.dat` 的 metadata（素材**全在本机 `files/il2cpp/`，不需要跑模拟器**）：

- 类 `LuaConfDataReader` 的字段直接暴露格式：`static readonly byte[] Header_32` / `Header_64` / `Footer`（`scripts32`/`scripts64` 的魔数与尾标）、`Dictionary<string, BinaryReader> readerDict`（每文件一个随机访问 reader）；
- **`ReadData(string configName, int startPos, int size)` 按 (偏移,长度) 取切片** → 正好解释密文里那段「4 字节一条记录、第二字节缓慢递减 `ff ff ff ff fe fd fc…`」是**索引表**；
- `ReadBufferFromCSharp(configName, startPos, size)` 是 C#→**Lua** 桥 → **解析/解码逻辑在 Lua 侧，C# 只交字节**；
- 上层入口是全局 `FileHelper.ReadCfgFile(string path)`（112 字节薄封装，旁有 `ReadBytes`）。

**已排除的假设（详细表在 `tools/sharecfg_re/README.md`，此处只留结论 + 判据）**：
UnityFS；单字节常量 XOR/加/减；短重复密钥 XOR（周期 1–32，按周期分组 IC **无尖峰**）；位置线性变换（`xor i` / `±i` / `i>>2` / `i>>8`）；前一字节自同步（`xor prev`/`~prev`/`sub prev`，滞后 1–8）；裸 zlib / raw deflate / bz2 / lz4.block（偏移 0–63）；UTF-16 明文；单字母表替换（IC 被打平）；**7 个 32-hex 串当 AES-128 密钥**（×4 偏移 ×4 模式 = 112 组合，最高可打印 0.385 ≈ 随机 0.37，全噪声）；**`scripts32`^`scripts64` 两时间垫**（零率正好 1/256，最长零段仅 32 字节，无从反推密钥流）。
关键实测数字：密文**熵 6.73**（真压缩/强加密 ≈ 8.0）、**IC 0.015**（明文 0.044 / 随机 0.0039）。

**误报纠偏（别再按这两个名字追）**：`XorShift64` 是 `Unity.Collections.xxHash3`（Unity 自带哈希）、`Decrypt128` 是 `System.Security.Cryptography.AesTransform`（.NET 自带 AES），都不是游戏的解密器。同理 `DecryptValue`/`DecryptKeyExchange`/`DecryptData` 全在 `System.Security.Cryptography`；`DecryptAcb`/`SetDecryptionKey` 属 `CriWare.*`（那是 ACB 音频线，见 WF-17）。

**解决方案 / 唯一验收判据**：见 `tools/sharecfg_re/`（README 含目标、判据、已排除假设、推进路线）。**判据只有一条：解出的 `ship_skin_template` 必须与 `inputs/azdata/azdata_ship_skin_template.json` 逐字段一致**——有一张已知明文在手，任何候选算法都要立刻拿它自证，不许「看起来像明文」就宣布成功。

**踩坑**：
- `libil2cpp.so` 的 `Machine` 是 **X86-64**（不是 ARM64）→ **本机 objdump 就能反汇编**，不用再装反汇编工具。
- Il2CppDumper v6.7.46 **原生支持 `Metadata Version: 31`**（此前担心只到 v29 是多虑）。跑完报 `Unhandled exception: Cannot read keys when either application does not have a console` 是「Press any key to exit」在 stdin 重定向下的**已知报错，产物已完整**，别当失败。
- dumper 同时报 `WARNING: find JNI_OnLoad` + `ERROR: This file may be protected.` → 可能有保护层，**方法 RVA 必须自检后再信**（实测 `LuaConfDataReader..cctor` 的 RVA 落在前置 thunk 上，真身在 +0x2D 处）。
- `Header_32/64/Footer` 在 so/metadata 里**没有连续字节串**（是 `.cctor` 用立即数逐字节构造的），只能靠反汇编取。
- **metadata 头 20 对 (offset,count) 全部自洽** = version 31 是正常的高版本，不是被改过头；别再花时间怀疑头被混淆。

**涉及文件**：`files/il2cpp/{libil2cpp.so,Metadata/global-metadata.dat}`、`files/AssetBundles/sharecfgdata/*`（34 张）、`tools/sharecfg_re/**`（独立小项目）、`tools/Il2CppDumper/`（第三方 dumper）、`.diag/sharecfg_re/dump/`（`dump.cs` 124.6 万行 / `script.json` / `il2cpp.h` / `DummyDll/`，在 gitignore）

### §22 追加（2026-09-24）：三条判据学 + 两处旧记录纠偏

本轮把"能不能不解密就读到明文"彻底判死，并纠正了本节两处旧记录。

- **纠偏 1（第 665 行"只能靠反汇编取"不准确）**：`LuaConfDataReader..cctor`（RVA `0x3C1577A`）不是用立即数逐字节构造，
  而是 `Array::New(5)/(5)/(0x1a)` + **`RuntimeHelpers.InitializeArray`**，三个 handle 全局各存一个 **FIELD 元数据 token**
  （`0x80000023` / `0x80000005` / `0x80000027`）。→ 字节真值**在 metadata 的 fieldDefaultValues 里**，
  这是"v31 索引法没解对"的问题，不是"只能反汇编"的问题。同一形态还出现在 Lua 包解密器 `www()` 里的 **19 字节密钥**。
- **纠偏 2**：`scripts32` 与 `scripts64` **头 32 字节完全相同** → `Header_32/Header_64` **不可能是各自文件的开头 5 字节**；
  且新发现的 `www()` 要求输入**末尾 4 字节 = 小端明文长度**，而盘上 `scripts64` 末 4 字节 = `0xB9A00799`（荒谬）
  → **盘上这份文件不是 `www()` 的直接输入**，中间还有一层封帧。别把"解 scripts64"当成一步就能做的事。

三条判据学（都是"看着像正信号、其实是自己造的"）：

1. **已知明文必须逐表自撞**。第一版拿 `ship_skin_template` 抽的 4634 个中文串去撞 `gametip`/`ship_skin_words`，
   0 命中就当成"加密证据"——**词表与表内容本来不同源，0 命中不说明任何问题**。重做后：3 张有基准的表用**自己的**词表
   （UTF-8 / UTF-16LE / UTF-16BE / GBK）自撞，仍 **0 命中**，这次的结论才立得住。
2. **相关性检验必须配零假设**。"32 张表两两 XOR 零率中位 1.84%（随机基线 0.391%）"当场被我判成"存在共密钥流"。
   实际：若各表只是**共享字节分布**，预测相等率 = 该分布的 IC = **1.904%**，实测完全落在预测值内；
   逐列共识度均值仅 0.102（真共享结构应 ≈1.0，实测 8192 列里只有 11 列 >0.9）→ **无共密钥流**。
   这是本项目 §24「假绿灯」家族的第 4 个实例：**阈值定松 + 没有对照 = 自己给自己发绿灯**。
3. **差分签名命中 0 也要读对照**。对 lag1/lag2 差分做 XOR/ADD/SUB 三视图搜已知明文串，命中 0 且
   **阴性对照（拿别表词表）也是 0**，才判"段内恒定密钥（含每条记录换 key）"整类出局。
   顺带暴露 lag-1 差分对**短周期密钥**不敏感 → 补做周期攻击（用 UTF-8 三字节区间约束做可分求解，p=2..12），仍否证。

净结果：**密文侧全部榨干**（明文 / 常量密钥 / 短周期密钥 / 共密钥流 / 替换 / 标准压缩 / ECB 逐条出局且均带对照），
定性收敛为"**明文索引 + 逐字段变换**"，而变换实现只可能在 **Lua 侧**或**待解出 key 的 C# 常量**里。
另：C# 侧"零解密"已由机器码证实（`ReadBufferFromCSharp` = `Path.Combine` + `FileStream` + `BinaryReader`，
`ReadData` = `Buffer.BlockCopy`；`PathUtil.ReadAllBytes` = `File.ReadAllBytes` 或 `BetterStreamingAssets.ReadAllBytes`），
并定位到唯一的 byte[]→byte[] 变换 `www()`（RVA `0x3D9CA20`，见 `tools/sharecfg_re/README.md` 调用链）。
新工具全部入库 `tools/sharecfg_re/`：`08_disasm_method.py`（dump.cs 符号→机器码，ELF 段表 / `.rela.dyn` / 字面量解析、
`--xref`、`--find`、136652 方法索引缓存）、`09`~`15` 号探针（已知明文自撞 / 共密钥流 / 共识密钥流 / 差分签名 /
按记录边界试解压 / FDV blob 提取 / 周期 XOR 攻击）。

## §23. CRIWARE ACB 语音导出静默丢数据：`-o x.wav` 对多子流容器只解 subsong 1（附 vgmstream flag 权威语义 + 全量映射统计）

**日期**: 2026-09-23　**状态**: ✅ 根因定位 + 正确命令实测，脚本 `scripts/extract_live2d_voice.py` 已入库；**全量导出已完成**（2026-09-24 体检实测 253 皮肤 / 5914 ogg / 缺失 0，见 WF-17「产物体检与备份口径」）

**流程与关键事实**（Live2D 包内 0 AudioClip、一个 `.b` = 一条船全部 cue、`painting`→`cv-{skin_id//10}.b`、cue 名 ≡ 动作组名、变体/排除规则、前端 `Sound` 接线与判据）**见 `docs/WORKFLOWS.md` WF-17**，此处只记 WF-17 没有的**证据、命令语义与统计数字**，避免两处漂移。

**现象**: `scripts/export_cue_audio.py`（2026-06-21）跑完全目录后每艘船只落 **1 个 wav**，文件名都叫 `detail`。当时当成"这些 ACB 里就一条语音"接受，实际是 **98% 的语音根本没解**。

**根因**: `vgmstream-cli` 对 ACB 这类多子流容器，**不给 `-S` 时只解码 subsong 1**；`-o` 不带 `?n` 通配时所有输出还会挤进同一文件名。全程**不报错、退出码 0、产物结构合法**——伪装成功型静默失败。同一文件 A/B 实测（`cv-30409.b` = 安土，容器内 64 个 cue）：

| 命令 | 产物 |
|---|---|
| `vgmstream-cli -o out.wav in.acb`（6 月写法） | **1 个** wav：`stream name: detail`，10.922 s，963,396 B |
| `vgmstream-cli -i -S 0 -o "dir/?n.wav" in.acb` | **64 个** wav，文件名即 cue 名（`home.wav`/`main_1.wav`/…） |

**各 flag 的权威含义（取自 `vgmstream-cli r2117` 自身 usage，别再靠试错猜）**：
- `-S N`：end subsong，**`-S 0` = 全部**。不给 = 只到第 1 条 —— 本次丢数据的唯一真凶。
- `-o` 通配：`?n`=stream name、`?s`=subsong、`?f`=infile。按 cue 名落盘才能后续按名匹配。
- `-i`：忽略 loop 信息、整条只播一遍（默认 `-l 2.0` 即循环两遍 → 时长翻倍）。**本批语音实测无 loop 点**：同一条 cue 加/不加 `-i` 输出均 963,396 B，但个别带 loop 点的条目会中招，故保留 `-i`。
- `-m` **不带参数**（只打印元数据不解码）：`-m3` 报 `unknown option`；要按流名遍历用 `-I`（打 JSON）。
- 编码实测 `encoding: CRI HCA`。`libatrac9.dll` 只是 r2117 构建里附带的库（当初拿它做可用性冒烟），**不代表本批语音是 ATRAC9**。

**否证一条常见找错地方的说法**: cue 名住在 **`CueNameTable`**（@UTF 表，`cv-30409.b` 实测含该串）；社区文档常说的 **`!CueName` 标记在 40 个抽样 `cv-*.b` 中 0 命中**。按 `!CueName` 找会得到"这包没有名字表"的假结论。

**全量只读扫描（`--report`，零写入，2026-09-23）**: 270 个 Live2D 皮肤 → **253 命中 ACB / 17 无 ACB / 解码异常 0**；cue 池共 **18,777** 条，单包 **29~169 条（中位 70）**；按动作组筛后计划导出 **5,914** 个文件。PCM 每船约 67 MB → 必须转 `libopus 48k`（约 1/10）。

**脚本自身的坑（复跑前必读）**: `--report` 后的**位置参数不生效**，只认 `--only k1,k2`——写成 `--report antu_2` 会**静默全扫 270 个 ACB**（数分钟；只读不写，但会覆盖 `.diag/_l2d_voice_report.json`）。

**待裁定**: `touch_body→touch_1`、`touch_special→touch_2` 仍是语义推断；`sharecfgdata/ship_skin_words` 一旦解出（见 §22，在途）即可给出权威映射，届时同步修 WF-17 与本条。

**涉及文件**: `scripts/extract_live2d_voice.py`（本次入库：`--report` 只读 / `--key` 样本 / `L2D_VOICE_ALL=1` 全量 → `Output/Audio/L2D/<皮肤>/<cue>.ogg` + `Output/gallery_v2/l2d_voice.json`）、`scripts/export_cue_audio.py`（中招的旧脚本，留作对照）、`inputs/azdata/azdata_ship_skin_template.json`（**承重文件勿删**，白名单与 sha256 台账见 WF-15 / `inputs/azdata/MANIFEST.json`）；vgmstream 在国内网络下的取工具/换源步骤见技能 `cn-blocked-resource-mirror-fetch`。

---

## §24. 三个「假绿灯」同类根因：工具默认值与退出码会让空跑看起来像通过（2026-09-24 全量重导前置排查）

**日期**: 2026-09-24　**状态**: ✅ 三处全部修好并实测

**共性**: 三处都不是算错，而是**默认值/退出码在替人说谎**。同属 §23 那类"伪装成功型静默失败"，但发生在**验收与换入侧**而非导出侧——一旦中招，坏数据会带着"全绿"记录进正式目录。

| # | 位置 | 症状 | 根因 | 修法 |
|---|---|---|---|---|
| 1 | `scripts/apply_live2d_motions.py` | 照文档 `L2D_OUT_DIR=<新目录> … --yes` 换入，实际换进去的是**默认目录里的旧数据** | docstring 写 `L2D_OUT_DIR`，代码读 `L2D_SRC_DIR`，两者都无则回落 `.diag/l2d_new`（09-21 修复前的 1.1G 陈旧产物）。**环境变量名写错＝静默用默认**，无任何提示 | ① 两个名字都认（`L2D_SRC_DIR` 优先）；② **不给源目录直接拒绝**（exit 2），取消默认回落；③ 换入前比曲线总数，`新 < 旧` 即判为陈旧产物拦下（exit 3，本次修的是"漏读 constant + 空壳占位"，只可能变多），确需强行换入才用 `L2D_ALLOW_CURVE_DROP=1` |
| 2 | `scripts/diag/l2d_ref_diff.py` | 在临时目录上跑权威基准比对 → **全部 `[SKIP] 本地无此模型`，退出码却是 0** | ① `evaluate_model` 要求 `<OUT>/<key>/<key>.model3.json`，而 `extract_motions` 只产 `motion/` → 临时目录必然全跳；② 汇总判据是 `ok == len(results) - skip`，全跳时 `0 == 0` 成立 | ① model3.json 缺失时回退读正式目录同名文件（motion 换入流程根本不动 model3.json，回退是**等价取值不是放水**）；② `evaluated == 0` 时打印 `[FAIL] 没有任何模型真正参与比对` 并 exit 1 |
| 3 | `scripts/diag/l2d_ab.py` | 换入前的新旧渲染 A/B「两侧一致」被当成没问题 | `NEW_ROOT` 硬编码 `.diag/l2d_new`（同一份 09-21 陈旧目录），"新侧"读的其实是旧数据 | `NEW_ROOT` 改跟管线开关 `L2D_OUT_DIR` 走；未显式给出时保留原默认但在文档标注风险 |

**判据（以后跑这条管线一律照此）**：
- 换入源目录**必须显式**给 `L2D_SRC_DIR`（或 `L2D_OUT_DIR`），并**先干跑**看末行 `曲线总数: 旧 N → 新 M`；M<N 说明源目录选错了，工具已会拦。
- 权威基准比对**必须看到 `PASS x / 共 y（跳过 z）` 里 `y-z > 0`**；`跳过 == 共` 一律视为没跑。参考库只覆盖约 8/14，`z>0` 正常，`y-z==0` 才是异常。
- 用 `l2d_ref_diff.py` 比对临时目录时**必须**带 `L2D_OUT_DIR=<临时目录>`，否则比的是正式目录（自证清白）。

**顺带纠正一处过期记录**: §23 头部写"全量导出尚未执行（磁盘上仅安土 1 个样本）"——2026-09-24 实测 `scripts/diag/l2d_voice_inventory.py` 得 **253 皮肤 / 2504 动作组条目 / 5914 ogg，缺失引用 0、孤儿 0**，全量早已落盘。判据以脚本输出为准，不以状态描述为准。

**样本重导实测（`.diag/l2d_fix`，配方 `L2D_MOTION_LINEAR=1 L2D_MOTION_EMIT_CONST=1`）**: `antu_2` 重导 104/104 文件与已换入的生产数据**逐字节一致**（配方确定性的证据）；`aerbien_3` idle 曲线 445/640→**640/640**、关键帧不一致 195→**0**、偏差中位 **2.8817→0.1279**、>0.5 占比 **95.1%→40.8%**（仍超 12% 线，但同模型换入前是 FAIL，属严格改善不是回退）。`gaoxiong_7`/`lingbo` PASS 且偏差中位 0.0。

---

## §25. 生产事故：`Start-Process` 下环境变量选输出目录不可复现 → 269 个模型的 motion 被跳过闸门原地覆写（2026-09-24）

**日期**: 2026-09-24　**状态**: ✅ 数据经核验可用（用户裁定保留），回滚备份已补齐，写向改为命令行旗标

**现象**: 按 WF-15「临时目录 → 审计 → 备份换入」准备全量重导，用 `.diag/_launch_reall.ps1`（先 `$env:L2D_OUT_DIR=.diag/l2d_fix` 再 `Start-Process py`）脱离启动。日志**头两行证明 `L2D_MOTION_LINEAR` 与 `L2D_MOTION_EMIT_CONST` 都生效了**，第一行却是 `[*] 输出目录: D:\Azur Lane Assets\Output\Live2D`（没有 `(临时)` 后缀）——`L2D_OUT_DIR` 单独没被子进程读到，269 个模型的 `motion/` 被原地覆写。

**根因判定（关键是"不可复现"而不是"哪个变量错了"）**:
- 同一条 ps1、同一个 `Start-Process` 机制，事后单模型复现实验里**三个变量全部被子进程读到**（`[*] 输出目录 ... (临时)`）。→ 这条路径的结果**依赖不可观测的启动上下文**，等于不可信。
- 本项目已是**第二次**同类：09-23 `L2D_VOICE_ALL=1` 在 `Start-Process` 下不继承，当时脚本"看起来起起来了"其实走用法分支 `exit 1`，修法是**加 `--all` 旗标**（commit `727fe04`）。
- 叠加缺陷：`extract_motions.py --all` 不指定输出时**默认目标就是正式目录**，没有 fail-closed，于是一个没生效的环境变量直接决定了写向。

**已排除的假设（都实测过，别重走）**: ① ps1 内容被改坏/写漏 → `cat -A` 核对 `$env:` 五行俱在；② 脚本读错变量名 → 同一脚本 `--out` 实测生效；③ 「lingbo 的 motion 文件 MISSING」→ 那是我探针**用了不存在的文件名**（motion 文件名不带模型前缀），是探针产物不是发现。

**修法（写向一律走命令行）**:
- `extract_motions.py` 新增 **`--out <目录>`**；`--all` 在既无 `--out` 又无 `L2D_OUT_DIR` 时**拒绝执行**（exit 2），确需直写正式目录必须显式 `--into-production`。环境变量降级为兜底，不再是唯一开关。
- 配套已有闸门：`apply_live2d_motions.py` 必须显式源目录 + 曲线总数变少即拦（§24）。
- **规则**：任何"决定写到哪/删哪"的参数，在需要脱离宿主进程的长任务里**必须是 argv**，不得只存在于环境变量。

**损失评估与补救**:
- 写进去的数据**就是已验收配方**（两个配方变量都确认生效），曲线总数 944,136 → **2,662,615**（×2.82，与唯一经人工目视验收的 `antu_2` 98→278 = ×2.83 同比例）；全库文件级审计 `clips 8154 / shell 7 / misassign 0 / PartOpacity 模型 79`，其中 shell 7 与 §2.5 记录的「资产层真为空的 7 条 clip」**逐一对上**（`aijier_2`/`dafeng_3`/`mojiaduoer_2`/`zhaohe_3` 的 effect、`wuqi_3`/`wuqi_3_hx` 的 idle11、`yingxianzuo_3` 的 idle1），无新增失败。
- 真正丢掉的是**换入前备份**与事后 A/B 对照能力。已核实 `.diag/l2d_new` 为 269 模型 / 曲线总数 **944,136**，与 §2.5 记录的覆写前总数**逐字相等** → 确认它就是覆写前的生产状态，已整目录复制为 `Output/_OLD_bak/l2d_motion_pre_swap_20260924/`（269 模型 / 1.1G），回滚能力恢复。
- 按用户裁定：不回滚，把闸门补跑在正式目录上（文件级审计 → 结构核验 → `l2d_ref_diff --all` → WF-16 回归）。

**另一条教训——基线必须打到字段级**: 本次为 `fix_model3.py` 打的 model3 基线只存了 `sha256 + 顶层键名`，跑完（269 个文件全变）后**无法做"只有预期字段变"的逐字段 diff**（`.diag/m3_snap/` 只有 09-22 那 13 个模型的 `.bak`）。只能退化成结构核验：269 个 model3 全部可解析、**0 悬空 motion 引用**、**0 未引用 motion 文件**、`HitAreas` min 3 / max 78 / mean 12.3、无 0 判定区模型。→ **下次改 model3 前先落字段级快照**（逐文件逐顶层键的 hash，或直接复制一份）。

---

## §26. 权威基准 `l2d_ref_diff --all` 为什么不能当全库闸门：153 个 FAIL 里大部分是判据失真，且工具会挂死（2026-09-24）

**日期**: 2026-09-24　**状态**: ✅ 判据已按本条重定义并实测（`PASS 3 / WARN 1 / FAIL 0 / SKIP 1` 于 5 个已知样本，与改前一致但不再误报 FAIL）；全库重跑进行中

**现象**: 全量重导后跑 `py -3 scripts/diag/l2d_ref_diff.py --all`，在 **206/269** 个键处日志停止增长、25 分钟零输出（手动停）。已打印结果：**PASS 5 / WARN 22 / FAIL 153 / SKIP 26**。而同一批数据在文件级审计（`clips 8154 / shell 7=资产层真为空 / misassign 0`）与浏览器回归（`l2d_sweep 269 | 失败 0 | 未启动 0 | 未生效 0`）下全绿。**同一个库两个工具给出相反结论 → 先怀疑判据，不是先怀疑数据。**

**三条失真实证**（从 `.diag/_refdiff_full.log` 的 `└` 说明行分类，类别有重叠）:
1. **「关键帧不一致」把参考版的重采样当成硬错误**。参考版是 60fps 采出来的（`fps_ref=60 / fps_ours=30`），我们写 Unity 原生关键帧时间 → 同一动作关键帧**集合**必然不同。实测 `siwanshi_3` 偏差中位 **0.0001**（几乎逐点相同）却仍被判 FAIL。28 个模型是"只有关键帧不一致"这一类。
2. **组→文件按 `files[0]` 盲配**。model3 的一个动作组可以登记多个文件，参考版登记顺序不保证一致 → 配错时报"关键帧不一致 66~150 条 + 时长不一致"（`abeikelongbi_3 main_2 关键帧不一致 150 条 + 时长不一致`、`aersasi_2 login 66 条 + 时长不一致`）。**这是配对错，不是数据错。**
3. ✅ **「曲线缺 1~3 条」已取证 = 单一系统性成因，不算缺失**（2026-09-24 补做）：对已缓存的 30 个模型 / 126 个"缺曲线"clip 统计缺失 Id，
   **只有三个**：`LipSync` 80 次、`Opacity` 54 次、`EyeBlink` 10 次，无任何其它 Id。三者都是 **Cubism 运行时内置通道**
   （口型/眨眼由运行时按参数驱动、`Opacity` 是 Drawable 级不透明度），**不经 `AnimationClip.genericBindings` 产生**，
   是参考版导出器自己合成的。已加 `BUILTIN_IDS` 从"缺曲线"里扣除、另计 INFO。
   **效果实测（同一批缓存数据零网络重判）**：FAIL 19 → 10、WARN 5 → 14 —— 印证这 9 个是判据误报。
4. ⏳ **剩余 10 个 FAIL 的成因已定位到一处、但"能不能修"未证**：15 次「偏差中位>0.5」里 **8 个模型都是 `effect` 组**
   （含 `antu_2`：`idle` 中位 0.0 而 `effect` 中位 **3.5567**）。段类型直方图给出机制：
   `antu_2/effect` 参考版 = 20 贝塞尔 + **36 阶跃(type 2)** + 21 线性，我们 = **77 段全线性**；
   `aerbien_3/effect` 参考版含 45 阶跃 + 661 贝塞尔，我们 6771 段全线性。
   即 **`L2D_MOTION_LINEAR=1` 把参考版用「阶跃」表达的特效开关写成了渐变**。
   ⚠️ 但**阶跃性未必能从 Unity 侧推出**：流式键只有切线值 `(t, v, ins, outs)`，没有 constant-tangent 标记。
   **禁止的修法**：照抄参考版的段类型数组（那是拿答案当依据，正是 §21/§26 反复踩的自证清白）。
   正确顺序：先做 Unity 侧取证判断可推出与否 → 推得出就发 type 2 并重导（全库约 25 分钟），
   推不出就把 `effect`/特效开关类归入天花板并对它们单列阈值，而不是让整库判据常年报 FAIL。
5. 另 1 个 FAIL「`aijier_2` 漏登记动作组 1」**已闭环**：那正是 §2.5 记录的资产层真为空的 7 条 clip 之一
   （`aijier_2` 的 `effect`），当初按 `fix_model3` 从 model3 引用里剔除，参考版仍登记 → 属预期差异。

**判据应该怎么改**（下次要用它当闸门，先做这三条）:
- FAIL 只保留：**曲线缺失**（且已排除定值口径）、**同一 clip 配对成功下的时长不一致**、**偏差中位 >0.5**；`关键帧不一致` 降级为 INFO 并在比对前把两侧统一到同一时间格（或只比"我们的关键帧处取值是否等于参考在其时刻的插值"）。
- **配对先对齐**：按（时长 + 曲线数 + 曲线 Id 集合）在组内多个文件里挑同一个 clip，找不到就 SKIP 并说明，而不是拿 `files[0]` 硬比。
- 分批跑：`--only k1,k2,...`，别指望 `--all` 一次过 269 键的长尾网络。

**工具侧挂死与修法（已落地）**: `fetch()` 原来只有 `urlopen(timeout=25)`，它**只约束单次 socket 操作**——慢滴式响应能让整轮无期限挂住（实测 25 分钟零输出）。现在：
- 每个 URL 加 **12s 墙钟硬上限**（取回放到 daemon 线程里 `join(HARD_DEADLINE)`，超时就放弃并计入 `STATS['hung']`，并打印 `[HUNG] <url>`），进程不会再无期限挂住；
- 加 **磁盘缓存 `.diag/refcache/`**（按 URL 的 sha1，404 也记 `MISS`）→ 迭代判据时重跑全库不再重打 13k 次网络（实测第二次跑 5 个样本 `cache_hit: 4`、秒级完成）；`--no-cache` 可绕过；
- 进度行 `[i/270]` 全部 `flush=True`，并**每 10 个模型增量写 `.diag/l2d_ref_diff.json`**，中途死掉不丢已完成部分；
- 汇总行改成 `PASS x / WARN y / FAIL z / SKIP s` 四段 + `exact/closest 配对数` + `STATS`；**退出码只认 FAIL**（漏组、配对成功下曲线缺失、偏差中位>0.5），WARN 需逐条看不算硬失败；`--only k1,k2` 支持分批。
- 成本要说清：`--all` 要遍历每个模型的**全部动作组**（`antu_2` 104 组），269 模型 ≈ 1.3 万次请求，**首轮就是 1~2 小时量级**，不是几分钟。

**✅ 全库定案（2026-09-24 跑完 269/269，`.diag/_refdiff_full4.log`）**：
`PASS 7 / WARN 54 / FAIL 16 / INCOMPLETE 4 / SKIP 188`。
- **参考库真实覆盖率 = 81/269 ≈ 30%**（不是我文档里那句"约 8/14"——那是 `--probe-keys` 抽样的说法，
  拿来当全库覆盖会高估；已按实测更正）。所以这条闸门**天生只能覆盖三成模型**，别当全量保证。
- 81 个可比模型里 **FAIL 只剩 16**，其中 **15 个是「偏差中位>0.5」且几乎都落在 `effect` 组**
  （见 §27/§26 的阶跃段结论），另 1 个 `aijier_2` 的「漏登记 1 组」= 资产层真为空那 7 条之一，属预期。
- **`INCOMPLETE 4` 全是参考库缺组**（如 `gaoxiong_7` 我们有 111 组、库里只有 15 组可比），
  是覆盖问题不是数据问题——把它单列成一类就是为了不混进 FAIL。
- `WARN 54` = 偏差>0.5 占比超 12% 天花板线，来自参考版那约 7% 无法从 Unity 还原的贝塞尔段（§21）。

**脱离启动器的坑（新工具 `scripts/diag/run_detached.py`）**: PowerShell `Start-Process` 在"含空格路径 + 三层引号"下连吃三次败（数组形式会按空格拆断路径；整条字符串又被 bash→PowerShell→子进程三层转义搞坏）。改用 Python `subprocess.Popen(列表)`：**参数是列表就不经 shell**。注意 `DETACHED_PROCESS(0x8)` 与 `CREATE_NO_WINDOW(0x10)` **互斥**，同时给会让 `CreateProcess` 直接 `[WinError 87] 参数错误`（四种组合实测：只给 0x8、0x8|0x200、只给 0x10 都能跑，三个一起就报错）。长任务的退出码不由启动器写（它自己会先结束），完成判据仍是脚本汇总行。

**已排除的假设**: ① 153 FAIL 不是本轮重导引入的回退——`antu_2` 重导产物与已人工验收并 PASS 的生产数据 **104/104 逐字节一致**，同一工具同一判据下它仍是 PASS；② 不是网络不通——206 个键里 26 个正常报"参考库无此模型"、180 个完成了比对。

**改判据过程中我自己引入的两个新缺陷（已修，记录以免被当成"改坏了"）**:
1. **墙钟硬超时设 12s 太紧**：该站高峰单请求实测就要 8~12s，于是"其实能成"的请求被放弃，而那些组会被记成"参考库无此模型"→ 一个模型可能只比了 3/14 组却被判 PASS（**新的假绿灯**）。放宽到 30s，且把「超时」与「真没有」分成两类记录。
2. **覆盖度不进判定**：verdict 只看"比到的那些组"，不看"该比的组比到了几组"。现在新增 **`INCOMPLETE`** 类：比到的组不足应比组的 60%（或一组都没比到）即判 INCOMPLETE，**汇总行与退出码都不许它当通过**（`return 0 if fail==0 and inc==0`）。
3. 顺带：`--all` 的键集合里混着 `_ab`（`l2d_ab.py` 的硬链接工作目录，不是模型），会白报一个 SKIP，已按下划线前缀过滤。

**全库规模的成本（要说清，别按"几分钟"规划）**: 覆盖到的模型每个要取 `1 + 动作组数` 个 URL（参考版典型 14~20 组、`antu_2` 104 组），首轮约 **2700+ 次请求**，按实测 3~12 s/次即 **2.5~6 小时**。因为 `.diag/refcache` 会留存（含 404 的 `MISS` 标记），**重跑几乎免费**，所以中断/续跑都无损；已完成的模型每 10 个增量写进 `.diag/l2d_ref_diff.json`。

---

## §27. 按部位点击「点不到身体」的真根因：判定区登记时压根没做几何校验（2026-09-24 取证）

**日期**: 2026-09-24　**状态**: ✅ 根因定位 + 退化框已过滤 + 断言已改诚实版；⚠️ 残留是**产品语义选择**，三条路待用户裁定

**现象**: 全量重导后 `fix_model3.py` 把判定区从 3 个补登到几十个（mean 12.3 / max 78），`hit_verify.py --limit 8` 给 **46/58**，12 个未命中当时被笼统记成"嵌套框歧义"。

**我先前给的两个诊断都是错的（记下来防止重走）**：
1. ~~"前端缺『包含点且面积最小』规则，加上就好"~~ → `gallery_src/index.html` 的 `hitAt` **早就是面积最小者胜**（2026-09-23 §21 那轮改的，注释写得很清楚）。
2. ~~"抽样 40/54"~~ → 实际工具打印 **46/58**（我口误后写进了状态文档两处，已改）。

**真根因**：`fix_model3.py:152` 判定"这个部位存在"的依据只有一行 —— `"Touch"+名` 这段字节**是否出现在 moc3 二进制里**，**完全不看几何**。于是 moc3 里那些**零面积/彼此重合的 `Touch*` 标记**也被登记成 HitArea。

**全库几何体检**（新工具 `scripts/diag/l2d_hit_geom_forensics.py --scan-all`，只读，269 模型）：

| 指标 | 数值 |
|---|---|
| 登记的判定框总数 | 3309 |
| **退化框**（面积 <1e-6 或宽/高 <1e-4） | **95 个，集中在 8 个模型**（`jinjiang_2` 30/39、`lafeiii_3` 18/25、`ankeleiqi_3` 18/34…） |
| 存在**完全相同几何**的框的模型 | **67/269** |
| 明细 | `.diag/l2d_hit_geom_scan.json` |

**为什么退化框是"抢点击"而不是"点不到就算了"**：它的面积≈0，在"取最小面积者胜"下**永远是最优解**；而它可命中的宽度只有包围盒 2% 容差（实测 `hw=max(1e-6,…)` → ±2e-6），**真人根本点不中**。组合效果 = 一个点不中的框持续劫持合法大框的点击 —— `lafeiii_3` 点 Body 播出 `touch_idle4` 即此。

**已修（两处）**：
1. **A｜前端 `geomOf` 过滤退化框**：面积或宽/高低于阈值直接 `return null`。选这个点改是因为 `geomOf` 只有两个消费者（`hitAt` 判定 + 判定区可视化），**一处生效两处同源**，不会出现"画出来却点不到"。阈值与本条扫描定义逐字一致。
2. **C｜`hit_verify` 断言四类化**：`HIT`（=自己）/ `SHADOWED`（播出的正是**产品自己的 `hitAt`** 判出的更小框 → 几何重叠，按设计，不算失败）/ `WIRING`（真实派发 ≠ 产品几何判定 → 事件链路真断，**只有这类算 bug**，退出码 1）/ `OUTSIDE`（中心点不在任何可用框）。为此在产品侧暴露 `window.__L2_HIT`（就是点击路径调用的那个 `hitAt`），**探针不再自己复算几何**——复算版实测与真实派发有 **4/38 条不一致**，复算不可信就不许拿它下结论。
3. 实测：同样 8 模型 → `HIT 32 / SHADOWED 20 / WIRING 0 / OUTSIDE 6`。**WIRING=0 是这轮最有价值的结论**：事件链路没有任何缺陷，每个未命中都能被几何解释。

**残留不是 bug，是产品语义，必须用户裁定（基线标定等定了再做，否则标两遍）**：
`lafeiii_3` 25 框 = `HIT 6 / SHADOWED 13 / OUTSIDE 6`。其中 **Body 被 `touch_idle4` 的「真实小框」合法遮住**（面积 0.854 的正常四边形），过滤退化框修不了它；`jianwu_2` 的 `drag2/4/8/10` 几何完全相同（同区域被登记成 4 个部位）。三条路：
- **A2 核心三框优先**：`Head/Body/Special` 与被遮部位冲突时核心框赢 → 点身体一定出身体动作，代价是那几处小标记彻底点不到。
- **A3 重叠标记合并**：同一几何/被遮的一组 `touch_*` 合并为"点这块区域随机播其中一条"（更接近游戏里"点一下出一条台词"的观感），代价是失去"点特定位置触发特定小动作"的精确性。
- **A4 维持现状**：承认"部位点击 = 点到的那块最具体的区域"，`SHADOWED` 与 `OUTSIDE` 就是事实，画廊里那几个小标记的动作只能从下拉框播。
- ~~A2/A3/A4 待裁定~~ → **2026-09-24 用户裁定走 A3（重叠即随机）并已落地**，见下方「A3 实施记录」。
- 另有 **B（同几何去重）**：A3 之后基本失去意义（同几何的框现在会被随机轮播，不再是"第一个独占"），只在让"判定区 N 个"这个数字诚实上还有价值。


**A3 实施记录（2026-09-24，用户裁定）**：`index.html` 的 `hitAt` 由「面积最小者独占」改为
`hitAll()` 取全部含点候选 → 在候选里**随机挑一条**，且**避开上一次刚播过的那条**（`_lastHit`，只剩一条时不避开）。
新增暴露 `window.__L2_HITALL(x,y)`（含点候选集合）给探针当断言基准，判定/可视化/探针仍然同源一份几何。

实测验收（`hit_verify.py --only jianwu_2,antu_2`）：
- 随机性：4 候选点上连调 `__L2_HIT` 8 次 → 出 **4 条**且**相邻不重复**（`jianwu_2` 的 `drag3/5/7/9`、
  `antu_2` 的 `touch_head/body/special/idle1`）；
- 链路：70 个部位 **WIRING=0**（实播全部落在候选集合内）；`jianwu_2`/`antu_2` **可点中率 100%**；
- **A3 的实际作用范围很小**：冻结态撒 24×24 网格统计，`jianwu_2` 只有 3 个多候选点、`antu_2` 4 个、
  `lafeiii_3` **0 个**。也就是说 `lafeiii_3` 当初「点 Body 播出 `touch_idle4`」**不是真重叠**，
  而是退化框抢点击 —— 已被 A（`geomOf` 挡退化框）解决；A3 是补在真重叠那一小块上的。

**测这个过程中我自己踩的三个测量坑（都写进代码注释了，别再踩）**：
1. 候选集合**必须逐次点击时重算**：模型在放 idle，循环前取的那一份到第 3 次点击已过期，
   会虚报「点了没反应」（实测 `offCand` 一度 3/6、1/6 乱跳）。修好后 `offCand=0`。
2. 随机性**必须在冻结 `app.ticker` 后测**：不冻结的话同一位置瞬时候选数在 1~2 之间跳，
   测出来 `distinct=1` 会误判成「随机没生效」——实际是那一刻只有一个候选，按设计本就不随机。
3. 但**冻结与点击测试互斥**（ticker 停了 `currentGroup` 不再前进），所以拆成阶段 1（跑着，测链路成员资格）
   与阶段 2（冻结，测重叠统计 + 随机序列）两轮。

**A3 断言上线后又被自己纠正两次（都值得记，因为都是"把工具缺陷当产品缺陷"）**：
- 全库标定第一轮报出 **WIRING 15 例**，逐条看全是 `实播='idle'` 而候选里就有它自己 →
  不是链路断，是**读结果的方式错了**：短的 `touch_idle*` / `drag*` 动作不到 700ms 就播完回落 idle，
  而探针是"点完等 700ms 再看一次 `currentGroup`"。这与 §6.10 那次 idle 假阴性同根，只是换了地方。
  改成：点完**立刻读状态栏 pill**（`play()` 成功时才写，同步且精确）+ 之后每 120ms 轮询 `currentGroup` 共 14 次。
  → 重测那 7 个模型 **WIRING 15 → 0**。
- 另有 18 例被算成 `OUTSIDE`，其实是**退化框部位**（`geomOf` 挡掉后本就不可点）→ 新增 `NOTCLICKABLE` 一类单列，
  不算异常。
- 还有个低级但真实的坑：我在 JS 注释里写 `touch_idle*/drag*`，那个 `*/` **提前闭合了注释块**，
  导致整段探针 JS 语法错、每个模型都 `Uncaught`、`nAreas=null`。→ **嵌在 Python 字符串里的 JS，注释内不能出现 `*/`**。
  这类错误只会以"工具全红"的形式出现，别顺手解读成产品坏了。

* **✅ 全库基线已标定（269 模型 / 3309 部位，`.diag/_hitv_base2.log`）**：
  `HIT 2338（70.7%）| INGROUP 905 | WIRING 0 | OUTSIDE 0 | NOTCLICKABLE 66`，166 个模型全部部位都能点出自己。
  **以后改命中/交互层，判据就是 WIRING 必须为 0**（旧口径「806/807 命中」作废：它建立在只有 3 个判定区、
  且把重叠当失败的断言上，断言总数都不同）。INGROUP/NOTCLICKABLE 是设计使然，不当中止信号。

**修正后实测（7 个原异常模型，194 部位）**：`HIT 124 / INGROUP 59 / WIRING 0 / OUTSIDE 0 / NOTCLICKABLE 11`，
可点中率 79.9%。随机性的强证据：某点有 **14 个候选框**，连调 `__L2_HIT` 8 次出 8 条不同；
两候选点严格交替（`touch_idle2`/`touch_idle5` 来回），说明"避开上一次刚播的"也生效。

4. 另外「面积相同」≠「位置相同」：全库扫描当初用 `(area,w,h)` 当几何签名报「67/269 模型有完全相同几何」，
   实际那只是同尺寸，可能在不同位置。真重叠要靠网格点重算候选才知道（上面的 multi 计数）。

**已排除的假设**：① 不是"缺面积最小规则"（已存在）；② 不是本轮重导引入（登记规则自 09-22 就在，只是当时只有 13 个模型带多个真实框，规模没暴露）；③ 不是事件链路问题（`WIRING=0`）；④ 不是探针坐标系问题（V/P 换算沿用 §20 的 `V2P`，且 `HIT` 的 32 条走的就是真实派发）。

**改完必须连带的第三个断言（差点漏掉）**：`l2d_inspector_verify.py` 原来断「画出的框数 == 登记的 HitAreas 数」，A 之后前提就不成立了（退化框既不画也不可点），跑出来 `areas.ok=false`。修法与 §27 的原则一致——**不让探针自己复算几何**，改由产品暴露 `window.__L2_HITUSE()`（= `hitAreas` 里 `geomOf` 非空的那批），断言对齐它，且**逐个标签集合相同**（旧断言只比数量，比集合更严）。对照实测：`lafeiii_3` 登记 25 → 可用 7（画 7，18 个退化被挡），`antu_2` **登记 57 → 可用 57**（一个都没误杀，证明阈值不是把合法斜框也过滤了）。另：`page_sanity_check` 健康、`interact_verify` 总判定 ALL PASS、`l2d_coord_forensics` head→Head / chest→Special / hip→Body 且 `identityHits` 全空。

**工具侧踩坑（会坑到下一个会话）**：CDP 脚本被宿主 `timeout` 掐掉时，`try/finally` 缺失就不回收 Chrome → 泄漏的无头实例与下一轮抢 profile，造出 `Execution context was destroyed`（WF-16 记过的那类假失败，本次真的复现了一次）。`l2d_hit_geom_forensics.py` 已加 `kill_tree()`（按父 PID 连子进程一起停）并在每条退出路径调用；清理时 `clean_diag_profiles.py` 的「进程仍引用就不删」判据也第一次真实生效（保住了并发会话正在用的 `chrome_galprobe3`）。

**涉及文件**: `gallery_src/index.html`（`geomOf` 退化框过滤、`window.__L2_HIT` 与 `window.__L2_HITUSE` 暴露）、`scripts/deploy_gallery.py`（改完必须部署，否则等于没改）、`scripts/diag/hit_verify.py`（四类断言 + 退出码）、`scripts/diag/l2d_hit_geom_forensics.py`（新增：逐框几何取证 + `--scan-all` 全库体检）、`scripts/fix_model3.py:152`（**待改**：登记前需几何校验）、`TROUBLESHOOTING.md` §18/§21/§24。

---

## §28. 一条**错误的**"判据不可达"结论是怎么造出来的：没读完 callee 就据此关分支（2026-09-24）

**日期**: 2026-09-24　**状态**: ✅ 同日自查推翻；`www()` 判据恢复为"输出须含 `UnityFS`"，分支未关闭

> ⚠️ **本条的标题在初版里是"真根因：验收判据本身不可达"，那是错的，已于同日改写。**
> 保留本条是因为**制造这条错结论的过程**比结论本身更值得记。

**现象**: `tools/sharecfg_re/` 连续几轮认为"`www()` 算法已完整拿到，但对配置表与盘面 `scripts64/32`
产不出明文"，堵点记为"输入侧还有一层封装"。

**本轮为查堵点做的事，以及其中错的那步**: `--xref www` → 全库**唯一**调用方 `LuaScriptMgr.Load`（这步没问题，
且已验索引 `VA` 零缺失、`RVA==VA==Offset+0x4000` 恒等）。问题出在接着**读宿主的收尾**时：
我看到 `0x3D9C8F6` 处像是一条 `call`，就认定 www 的输出进 `luaL_loadbuffer`，
于是推出"AB 永远不会进 loadbuffer ⇒ **判据'输出须含 UnityFS'在任何输入上都不可能成立**"，
并据此把 (6)–(15) 整条线判成"方向性错误"、建议关闭分支。

**真相（逐条重读后）**: `0x3D9C8F6` 是 `4c 89 fe  mov rsi, r15`（把 www 的输出搬进 arg1），
`0x3D9C8F9` 是 `mov rdx, rbx`，**真正的 call 在 `0x3D9C8FC` = `LuaScriptMgr.LoadABFromBytes`**
（`dump.cs`: `private IEnumerator LoadABFromBytes(byte[] bytes, Action<AssetBundle> callback)`），
下一条 `0x3D9C909` 就是 `MonoBehaviour.StartCoroutine`。所谓 `0x35ae110`、`test al,al`、
`"@"+filename` **全是我凭印象补出来的，机器码里不存在**。
→ **`www()` 的产物是 AssetBundle，"输出须含 `UnityFS`" 一直是正确且可达的判据。**(6) 当初画的链条从头到尾是对的。

**同一段里被一并带错的另外两处**（都是"没读完就下结论"）:
- ~~"19 字节数组只被读 byte[4] 当种子"~~ → `Array::New(0x13)` 是 **19 个 int32 元素**（不是 19 字节）：
  mode 1 读 `[r15+0x20/0x24/0x28/0x2c]` 四个 **dword** 当 TEA 子密钥，mode 0xd 还要求 `[r15+0x18] > 0xd`。
  它是 `www()` 的**内联密钥表（76 字节）**，(15) 的"19 字节密钥"只是把元素数当成了字节数。
- ~~"种子里另外两项逐文件变，公式是 235+byte[4]+末字节"~~ → 引用的 `0x3D9CC0C/0x3D9CC17/0x3D9CC5F`
  与真实的逐字节拷贝循环 `0x3D9CC12 mov cl,[r14+rbp]` / `0x3D9CC19 mov [rax+rdx+0x20],cl` **地址重叠**，
  即那几条是我记错的。`www()` 实为三段：① `L = LE32(buf[len-4..])`，取 `buf[len-4-L : len-4]`；
  ② 对这段跑 `state=235` 的反馈流；③ **另有一支 TEA 族 Feistel 解密缓冲区头 8 字节**
  （`sum₀=0x0DFF7A0A`、`delta=0xF90042FB`，非标准 XTEA 常量，密钥即上面那张 int32[]）。

**所以「否证」的正确形态**: 把每个偏移当候选缓冲区末尾，`L = LE32(e-4)`，只保留 `8 ≤ L ≤ 64MB`
且不越界的**自洽**候选，再按 235 递推解前 8 字节找 `UnityFS`。scripts64/32 + 6 张表共
**683,233 个自洽候选，0 命中**；而 (6) 独立注意到盘上 `scripts64` 末 4 字节 = `0xB9A00799`
当长度荒谬 → **盘面这份文件不是 `www()` 的输入**，两条证据互相独立。
另捡到一个新事实：**32 张配置表末 4 字节完全相同，且公共后缀恰 11 字节**（`09 9d 9f 8e 99 07 8f 99 07 a0 b9`）
→ 那是**固定 Footer 魔数不是长度**；表头 0/1 字节高散、2–31 位仅 3–8 种取值、第 4 位恒 `00`，
说明首尾都不在变换覆盖范围内，与既有"明文索引 + 逐字段变换"定性吻合，并给出变换的**区间边界**。

**踩坑记录（本条的真正价值所在）**:
- **假绿灯第 7 类：「我以为我读过那条机器码」。** 前 6 类是"拿局部巧合支撑结构结论"，
  这一类是**拿没读完的指令序列凭印象补全，还写成"一条机器码就能定死"**。
  对策：凡据此改判整条分支去留（尤其是否定一条判据的可达性），必须**贴出该调用点前后指令原文 + callee 的 dump.cs 签名**。
- **否定一条判据之前，先自问"我是不是已经把输出去向读到底了"。** "判据不可达"是一个**很强**的陈述，
  它的证明责任不低于"已破解"；本轮它带来的实际损害是把一条正确的主线判成了方向性错误。
- **一次错误结论会连带污染同一段里其它看起来"已核对"的数字**：同轮我还"读出"了两条种子公式相关指令，
  地址与真实拷贝循环重叠——错的是同一处阅读，不是一个点。发现一处凭印象，同段全部结论都要重读。
- **凭记忆写的结构假设一律先测再当判据**（本轮又踩：il2cpp 数组头 `max_length` 偏移按 64 位记成 +0x18，
  再用 `<2³²` 当指针闸，把 55,011 个候选全筛成 0；实测堆地址是 **47 位** `0x7d3f_xxxxxxxx`）。
  **0 命中先怀疑探针，别当成否证。**

**涉及文件**: `tools/sharecfg_re/08_disasm_method.py`（`--xref`）、`tools/sharecfg_re/README.md` (16) 顶部更正块、
`tools/sharecfg_re/26_www_wrapper.py`、`tools/sharecfg_re/27_find_key_array_v2.py`（新增，快照找密钥表；
**其指针闸待按 47 位地址修正后才可用**）、`docs/WORKFLOWS.md` **WF-18**、§22（编号冲突见该节注）。

## §29. 照记 `Il2CppGlobalMetadataHeader` 节序 → 整轮否证打在**错区域**（v31 比 v24–29 多一对，2026-09-25）

**日期**: 2026-09-25　**状态**: ✅ 已定位并纠正；同轮据此取到 `www()` 的 19×int32 密钥

**现象**: `tools/sharecfg_re/14_extract_field_blobs.py` 的注释与 README (14) 记着一条结论——
"按 v24–v29 的节序表解出 `fieldAndParameterDefaultValueData` = **21,388 字节**，在里面搜 `1b4c4a` **0 命中**，
所以 `Header_32/Header_64/Footer` 这些 `static readonly byte[]` 的默认值**不在这份 metadata 里**"。
本轮把同一段代码重跑时顺手做了区域自检，发现该结论的**搜索区间本身就是错的**。

**根因**: `global-metadata.dat` 的头是 `(offset,size)` 对的**顺序表**，而这张表**随 metadata 版本增删节**。
v31 在 `stringLiteral` 之后比旧表多一对，于是从第 1 对起整体右移一位：
按旧表读到的"21,388 字节堆"实际是 `parameterDefaultValues`（第 12 对，21,388 B）；
真正的 `fieldDefaultValues` = 第 **7** 对 `@9,515,896 / 224,340 B`（`224340 % 12 == 0`，18,695 条——
**这条数正是上一轮自己实测过的**，当时被安到了错的节名上），
`fieldAndParameterDefaultValueData` = 第 **8** 对 `@9,740,240 / **879,152 B**`。
把 `1b4c4a` 在**整份 18MB** 里搜：6 个命中，**全部落在这 879KB 内**。
⇒ "堆里没有头部魔数"是一条**打错靶的否证**，它把"Footer/Header 取不到"写成了既成事实，
连带让后面几轮只在"内存盲扫 19 字节数组"上绕路（工具 16/17/24/27）。

**怎么定位到的（不是靠读文档，是靠自检对不上）**: ① 把 `@8+8i` 的 48 对原始 (offset,size) 全打出来，
看哪些对首尾相接、哪段之后开始出负数/微小值（旧表在第 15 对之后就已经崩坏，只是崩坏点前看起来"合理"）；
② 对候选记录区做**布局自检**：12 字节步长下 `fieldIndex` 逆序数 **0**、`dataIndex` **100% 单调不减**、
`max(dataIndex)=879,148` 距堆尾仅 4 字节——三条同时成立才认下这个布局；
③ 再用**已知明文**（真实文件头 5 字节）验内容。

**由此得到的正面结果**（详见 `PROJECT_STATUS.md` §6 第 7 条 (18) 轮与 `WORKFLOWS.md` WF-19）：
默认值堆**按相邻 dataIndex 之差切就是 blob 真长度**，于是**不需要** token→fieldIndex 映射也能按内容取数组；
整堆里长度恰为 76 字节的 blob 只有 2 个（一个是文本），另一个正是 `www()` Phase C 的密钥表——
`scripts64`/`scripts32` 头 8 字节用逐指令落地的 XXTEA 解出 `UnityFS\0`（全库 91,642 个 AB 中仅这 2 个是密文头）。

**教训**:
- **凭记忆写的结构表（节序、字段偏移、指针宽度）一律先测再当判据**——本轮与 §28 是同一家族的第 8 种形态：
  "我以为我读过那张表"。区别只在于这次错在**偏移表**而不是**机器码**。
- **否证的强度 = 它所依据的区域/字段名的强度。** 写"X 不在 Y 里"之前，先独立证明 Y 的边界就是那段字节
  （本轮的独立证据 = 上一轮自己实测的 `224340 % 12 == 0` 与内容命中的区间包含关系）。
- 一条"取不到"的记录会被下游当公理：它已经在 (14)→(16) 三轮里把注意力从"读堆"引到"扫内存"上了。
  **作废它时要连带把基于它挂起的分支一起恢复**，否则损失是路径不是结论。

**涉及文件**: `tools/sharecfg_re/28_blob_heap_known_plaintext.py`（新增：节序对齐 + 布局自检 + 内容定位 + blob 切分）、
`tools/sharecfg_re/29_www_xxtea_key_test.py`（新增：Phase C 落地 + 三重对照）、
`tools/sharecfg_re/14_extract_field_blobs.py`（本条错结论的出处，注释待更正）、
`tools/sharecfg_re/README.md` (14) 与「已排除的假设汇总」表里 `v31 fieldDefaultValues 可按 token rid 索引` 一行、
`docs/WORKFLOWS.md` **WF-19**、§28（同一家族的假绿灯）。

## §30. 两个反向的判据事故：把 trailer 读成小端（否证打错对象）+ 拿"可打印率"当解密判据（真明文被判成密文）（2026-09-25）

**日期**: 2026-09-25　**状态**: ✅ 两条都已用不含未知量的自洽性质重做判据

**(1) `www()` 的 trailer 是**大端**，不是小端。**

`(17)` 轮与我本轮初都写成 `L = LE32(buf[len-4:])`，据此算出 `scripts64` 的 `L = 1,964,572,672 > 文件长`，
并下了否证："**盘上整份 scripts 文件不是 www 的输入**"。逐指令重读 `0x3D9CAAB-0x3D9CB04`：

```
0x3D9CAB9  edx  = byte[len-1]                       ; 落到 bit 0..7
0x3D9CACF  edi  = byte[len-2];  0x3D9CAF0 shl edi,8
0x3D9CAEB  eax  = byte[len-3];  0x3D9CAF5 shl eax,16
0x3D9CAFA  r14d = byte[len-4];  0x3D9CB00 shl r14d,24
→ word = b[len-4]<<24 | b[len-3]<<16 | b[len-2]<<8 | b[len-1]      = **BE32**
```
`scripts64`/`scripts32` 末 4 字节 = `00 00 19 75` → **L = 6517**（自洽）。返回缓冲长度取
`esi = (len-4) - L`（`0x3D9CB12 sub esi, r14d` 的 `esi` 低位此刻是 `len-4`，不是 `len`——
上一轮我把它当 `len` 也算错过一次）。

**(2) "可打印率 0.37~0.38 = 随机水平 ⇒ 该变换不适用"是一条坏判据。**

`(17)` 轮用它判死过"235 反馈流对配置表无效"。本轮拿到一段**确定被正确解出**的明文
（`scripts64` 末段 6517 字节过 235 流，开头就是容器魔数 `1b 4c 4a 02 0a`），它的**可打印率只有 0.216**。
⇒ **这种数据本来就是二进制记录流，可打印率低不是密文证据。** 拿统计量当解密判据，
既可能假阴（真明文被判成密文，本案）也可能假阳（文本区偶然高可打印）。

**取而代之的四条自洽判据（`30_www_endtoend_reproduce.py`，任一不过即 `exit 3`）**：
- A1 `L = BE32(末4)` 须 `0 < L < filesize-4`；
- A2 Phase C 逐 8 字节块 ECB 解出的**块 0 必须等于 `UnityFS\0`**；
- A3 **自报长度互校**：解出的前 64 字节里必须出现 `>i4(filesize-4-L)`
  —— AB 文件自己声明的 fileSize 恰好等于模型算出的返回缓冲长度。**两个文件各自命中**（`02 59 48 d4` / `02 59 17 e8`，均在偏移 34）；
- A4 Phase A+B：尾段过 235 流后必须以 `1b 4c 4a` 开头；
- A5 阴性对照：19 个字整体 +1 后 A2 必须失效（实测解出垃圾）。
A3 是本轮最有价值的一条：**它不含任何未知量**（一边是文件内字段、一边是文件长度与 L），
强度却远高于任何分布统计，且天然可证伪。

**顺带得到的正面结论（对"配置要不要解密"）**：A4 解出的 6512 字节载荷与
`sharecfgdata/aircraft_template` 的正文在**同一偏移**上骨架逐字节相同
（参照 `f5 01 05 05 00 00 01 0b 1d 4e ff 00 00 51` vs 表 `f1 04 05 05 00 00 00 17 21 4e ff 00 00 51`），
字符串区是同一种 `0x80-0xBF` 游程编码（参照 146 段/均长 8.42，`weapon_name` 7269 段/均长 6.33）
⇒ **配置表正文与一份"已确认解密成功"的同格式数据在字节层面对齐，容器层不需要解密**；
剩下的问题是**记录与字符串的编码文法**（单字节 XOR 全 256 扫描在两边都 0 命中，故不是常量 XOR）。
另：`scripts64` 尾段头部是 `...02 0a`、`scripts32` 尾段是 `...02 02`
⇒ 两个头部值都**第一次以真明文形式被看到**，但"哪个对应 Header_32 / 哪个对应 Header_64"
与 (18) 轮据堆内配对所作的推断**方向相反**，该配对仍需另找证据（见 [[al-sharecfg-container-format]]）。

**教训**：
- 字节序这种"两个候选里挑一个"的假设，**必须靠一个会因选错而必然崩掉的量来定**（本案：算出来的 L 要能让文件自报长度对上）。
- **解密判据只能是"解出来的东西里有一个我独立知道的值"**，不能是分布特征。选判据时优先挑
  **两边都能独立算出来**的量（自报字段 vs 外部计算），这类性质一次命中即接近零假阳。
- 一条错判据的下游代价是真实的：`(17)` 的"流不适用"结论让配置表分支被整体挂起，而真正缺的只是文法解析。

**涉及文件**: `tools/sharecfg_re/30_www_endtoend_reproduce.py`（新增，A1-A5）、
`tools/sharecfg_re/08_disasm_method.py`（新增 `--xrefslot`：按数据 VA 找 rip 相对引用；实测密钥槽
只被 `www()` 一处使用）、`tools/sharecfg_re/README.md` (17) 里 `LE32` 与"可打印率"两处表述待更正、
`docs/WORKFLOWS.md` WF-19 判据段、§29（同一族的"打错区域的否证"）。

## §31. `scripts64` 第 9 字节往后是哪一层：指纹区被单独改写 + 真身是 Unity 中国版 ASM 加密；UnityPy 的 `brute_force_key` 候选集太窄（2026-09-25）

**日期**: 2026-09-25　**状态**: ⏳ 层已定性，16 字节 ASM 密钥未取到（扫描进行中/待换语料）

**现象**: 30 号把 `www()` 三段判死之后，只补头 8 字节的副本仍打不开：
UnityPy 报 `No valid Unity version found`。

**定位过程（三个可复现的步骤，全部本地）**：
1. `31_www_…`→ 实际是 `31_decrypt_scripts_bundle.py`：按 ECB **全量**解（向量化，并与 30 号标量实现
   **逐块对比 8192 块 0 不一致** —— 向量化写错很容易，不对齐就不许出结论）。
   解出的 `>i4 @34` **正好等于 ALEN**（两个文件各自命中）⇒ **偏移 32 之后解对了**。
2. 剩下的垃圾只落在**偏移 8..31 这 24 字节**，其长度与内容正好是
   `formatVersion(4) + "5.x.x\0"(6) + "2022.3.51f1\0"(12) + i64 高 2 字节`
   = **"扫描器指纹区"**。用同构建明文包（实测取 `files/AssetBundles/ammo`）的这 24 字节补回去，
   UnityPy 立刻换了一条错误：**`The BundleFile is encrypted, but no key was provided!`**
   ⇒ **第 9 字节往后不是自研流密码，而是 Unity 中国版 ArchiveStorage 加密**
   （特征串 `#$unity3dchina!@`，即 UnityPy 注释里 PGRStudio/PGR 那一套）。
3. `32_asm_key_from_metadata.py` 把 `key_sig/data_sig` 从 UnityPy **自己的异常文本里解析出来**
   （不硬编码；`ast.literal_eval`，不用 `eval`），调官方 `brute_force_key` → 依赖缺失，
   `pip install pycryptodome` 后可跑，但**未找到密钥**。

**根因（为什么官方函数白跑）**：`brute_force_key` 的默认候选是
`re.compile(rb"(?=(\w{16}))")` —— **只试"16 个 word 字符"这一种形态**，
对本项目这种"密钥可能是任意二进制 16 字节"的情况会系统性漏掉。
预言机其实很便宜且极强：
`decrypt_key(K) = AES-ECB(K).encrypt(key_sig) XOR data_sig == SIGN`
⇒ 只需 `AES_K(key_sig) == data_sig XOR "#$unity3dchina!@"` = 一个**固定 16 字节目标**，
候选逐个滑窗验即可（128 位判定，~10^7 候选期望假命中 10^-27）。
`33_asm_key_scan.py` 就是把它做成**全窗口穷举**：
`global-metadata.dat` **逐字节 18,245,153 个窗口全扫 = 0 命中**
⇒ **密钥不在 metadata 里**（这条现在是带穷举范围的否证，不是抽样结论）。
下一步语料：`libil2cpp.so`（121.8MB，后台扫）、必要时 APK/内存快照。

**顺带钉死/纠正的**：
- 那 24 字节被**单独改写**是有意为之（防第三方扫描器），不是"我们解错了"——证据：同一段里
  `>i4 @34 == ALEN` 这种 32 位精确值能解出来。
- `data_sig` 尾部含 `B-andro` 明文（本厂包命名前缀），佐证读到了正确结构。
- 本轮新增依赖 **pycryptodome**（`docs/WORKFLOWS.md` 步骤 1 已记）。
- 产物 `.diag/sharecfg_re/{scripts64,scripts32}.ab`（ECB 全解，各 ~39MB）**不入库、可由 31 号一键再生**。

**教训**：
- 用第三方库的"暴力/搜索"函数前，**先看它的候选集是什么**——它写死 `\w{16}` 时，
  "跑完没找到"和"不存在"是两回事（本轮差点据此判死 metadata 这条路）。
- **报错文本是好输入**：`key_sig`/`data_sig` 是它自己算出来的，解析出来复用即可，
  不要手抄成常量（手抄会静默漂移）。

**涉及文件**: `tools/sharecfg_re/31_decrypt_scripts_bundle.py`、`32_asm_key_from_metadata.py`、
`33_asm_key_scan.py`（均新增）、`files/AssetBundles/ammo`（指纹区参照明文包）。
相关：§30（www 三段与 A1~A5）、WF-19。

**追加（同日，公开工具圈核查结果）**：
- 找到的对口工具 = GitHub `598597535/Azurlane-LuaHelper`（"encrypt and decrypt, decompile and recompile
  Azurlane's lua files"，含 `--decrypt` AssetBundle / `--unpack`，输出目录名 `CAB-android` 与我们
  `data_sig` 尾部的 `B-andro` 对得上）⇒ **确认这层是 AL 已知的 AssetBundle 方案，不是我们读错**。
  但它的密钥不落地：`AssetBundle.cs` 用 `Assembly.Load(Properties.Resources.Salt).GetType("LL.Salt")`
  再反射调 `Make(byte[], bool)` ⇒ 钥匙在嵌入的 .NET 程序集里**运行时派生**。
- 否证（带穷举范围，别重复劳动）：
  ① `global-metadata.dat` 逐字节 16 字节窗口 **18,245,153 个候选 0 命中**；
  ② `libil2cpp.so` 逐字节 **121,853,691 个候选 0 命中**（后台跑完，退出码 0）；
  ③ 该仓库的 `Resources/Salt`（17,408 B .NET DLL）里抽 ASCII + UTF-16 交错还原后的
     16 字节窗口 **1,880 个候选 0 命中**（2018 版工具，钥匙多半已换或为派生值）。
  ⇒ **"16 字节连续存在于本地静态文件里"这一整类假设已排除**；剩下的现实路径只有
  (a) 反编译/直接调用那个 .NET `LL.Salt::Make`（要跑第三方二进制，需用户点头），
  (b) 运行时内存里找派生后的密钥，(c) **绕开**：配置表侧已证容器层不加密，
      而台词中文串此前已在游戏内存里实测到（10.4 万条，只差归属）。

**⚠️ 上面"追加"里的 ASM 结论已被同日第三次观察推翻（降级为"很可能不成立"，密钥搜索线正式停）**：
第三方工具 `LL.Salt` 的反编译（只用 ILSpy 静态读，未执行该 DLL）给出决定性结构：

```csharp
public static void Init(uint[] key, uint delta) { uint_0 = key; uint_1 = delta; }   // 钥匙由调用方注入！
public static byte[] Make(byte[] bytes, bool enc) {
    uint num = 0;  uint n = bytes.Length - 8;
    for (uint i = 0; i < n; i += 8) { 小端打包 array[0..1];
        switch (num) { case 0: smethod_1(array, key); case 1: smethod_3(...); case 2: smethod_5(...);
                       default: smethod_7(array, key, i); }        // mode 3 额外吃**块偏移 i**
        写回 8 字节;  num = (num + 1) % 4;                          // ★ 模式按块号 4 循环
    } }
```
- **`LL.Salt` 里根本没有密钥**（`Init` 注入）⇒ §31 追加①②③那三处"全窗口穷举 0 命中"不是"钥匙藏在别处"，
  而是**根本没有这把钥匙可找**——该线正式停。
- 游戏侧同构：`www()` 里 `0x3D9D1E8 inc r11d; and r11d,3` = 同一个 `%4`；
  `r11d` 的三路分发 `je 0x3D9CF13`(mode0) / `cmp r11d,1 → 0x3D9D028`(mode1) / `cmp r11d,3 → 0x3D9CE87`+(sum>>11)&3(mode3)，
  以及 `0x3D9D0B9` 要求 `keylen>13`、用 `key[13]` 的一支(mode2)。**我此前只实现了 mode 0。**
- **这一条把 §30/§31 里全部异常一次解释干净**：块 0（mode0）解出 `UnityFS\0` ✓、
  块 4（4%4=0，仍 mode0）解出正确的 `>i4@34 == ALEN` ✓，块 1/2/3 是 mode1/2/3 → 我按 mode0 解 = 垃圾 ✗。
- 所以"**BundleFile is encrypted（Unity 中国 ASM）**"这条判定**很可能是半解密文件的假象**：
  UnityPy 从错位的字节里读出 ASM 头，而 `data_sig` 尾部出现 `B-andro` 明文正是"错位数据"的特征。
  ⇒ 教训：**"用第三方库的错误信息给格式定性"之前，必须先确认喂给它的数据是完整正确解码的**；
  否则库会替你的 bug 编一个看起来很专业的解释（本次连 `key_sig/data_sig` 都"打印"出来了，说服力反而更强）。
- 下一步：把 mode 1/2/3 按上述四个地址逐指令落成代码，按 `%4` 整文件解，再交 UnityPy 复验。

**✅ 同日收尾：四模式 %4 循环全部转写成功，`scripts64` 已能被 UnityPy 打开（45,740 个对象）**
`34_www_four_modes.py` 用**块 0/1/2 三组独立已知明文**（块 0=`UnityFS\0`、块 1=`\x00\x00\x00\x08"5.x."`、
块 2=`"x\02022.3"`，后两组来自同构建成文包逐列众数）作硬判定，结果**模式即恒等顺序**且转写全对：
```
块 0 -> m0(0x3D9CF13 XXTEA 2 轮)   ✓      块 1 -> m1(0x3D9D028 XTEA K0..K3 2 轮) ✓ 逐字节精确
块 2 -> m2(0x3D9D0B9 v^=块偏移^key[13]/key[2]) ✓ 逐字节精确（偏移 = 字节偏移 16）
块 3 -> m3(0x3D9CE87 key 下标 (sum>>11)&3 与 (sum+delta)&3) -> 解出 "2022.3.62f3"
```
⇒ 整文件解出的头部 = `UnityFS\0` + `00 00 00 08` + `5.x.x\0` + **`2022.3.62f3\0`** + i64 fileSize
= **39,405,780 == ALEN ✓**，UnityPy 打开成功、类型含 TextAsset(49)。**"Unity 中国 ASM 加密"确认是我半解密文件造成的假象**（§31 已降级）。
⚠️ 附带纠正：块 3 的 revision 不该拿其它包的众数（`51f1`）硬套——这批 Lua 包真是 `62f3`；
**"共识/多数"类参照只对同构建同批产物成立**，用它当判据前要先确认参照域。
**~~待做（机械活）~~ 已完成，见下面 §32 追加**：`m_Name` 为空，名字要从 bundle 的 container/source 取；下一步按 TextAsset 逐个导出再定位
`ship_skin_words` / `ship_skin_template`。

## §32. UnityPy 的 `TextAsset.m_Script` 是**有损** str：按 UTF-8 `errors=replace` 解码，导出会静默毁掉所有 ≥0x80 字节（2026-09-25）

**现象**：从已解开的 `scripts64` 里导 `sharecfg/ship_skin_words.lua.bytes`，`m_Script` 拿到 78,775 个字符、
写盘 80,505 B，但内容里大量 `0x3f('?')`，且紧跟容器魔数的字节"看着就不像数据"。

**根因**：`m_Script` 的类型是 **`str`**，UnityPy 读 TextAsset 时按 UTF-8 `errors=replace` 解码，
实测这 80,505 字节里有 **32,935 个字符 > 0xFF**（即每个非法字节被打成 U+FFFD）；
再用 `str.encode('utf8','replace')` 回写就是不可逆的破坏。**文件长度看着正常、不报错** ⇒ 典型静默失败。

**正确取法（`35_export_sharecfg_lua.py` 已按此实现）**：容器项 → `PPtr.m_PathID` →
`Object.get_raw_data()`（原始序列化字节）→ 按 **`int32 长度前缀 + 1b4c4a020a`** 定位切片。
实测 `raw[24..28] = 80505` 正是声明长度，取回体里 `>=0x80` 字节 **34,744 个**（有损路径下是 0）。

**判据（导出文本/二进制类资产时必须加）**：解出的字节流里 **`>=0x80` 的字节数为 0 就直接报错停止**——
本项目这类载荷本应含大量高字节（参照：`gametip` 237,333 / `ship_skin_template` 58,123 / `ship_skin_words` 34,744）。
比"文件非空/长度对"强得多，且零成本。

**顺带**：`35` 号里做了个**否证式**结构检查（能否按 LuaJIT BC dump 的 `tag + ULEB` 走通）——
紧跟 `1b4c4a02 0a` 的首字节是 `b0/fb/f0`，全部 > 0x10 ⇒ **不是标准 LuaJIT 字节码**，
"`\x1bLJ` 是容器魔数"这条旧结论在真数据上再次通过检验（此前它只在半解密数据上被"验证"过）。

**当前到手的东西**：`scripts64` 解开后容器条目 **45,739** 个，其中
`assets/luabuilds/android/arm64/sharecfg/*.lua.bytes` **774 个**（对上内存快照里 776 项清单），
另有 `gamecfg/` 38,178（技能/剧情 Lua）、`view/` 3,774、`mod/` 1,533、`controller/` 640、`model/` 447。
样本已无损落盘 `.diag/sharecfg_re/lua_out/`；**全量 774 个导出属批量操作，待用户确认后 `--limit 0` 再跑**。

**涉及文件**: `tools/sharecfg_re/35_export_sharecfg_lua.py`（新增，无损取法 + 高字节自检 + BC 否证检查）、
`docs/WORKFLOWS.md` WF-19 判据段。相关：技能 `safe-pipeline-fix-targeted-rerun`（"占位/降级产物伪装成功"一类）。

**§32 追加（同日，全量导出 + 两条判否）**：
- 全量导出已跑（用户确认）：`sharecfg/` **774 个**全部无损落盘 `.diag/sharecfg_re/lua_out/`（50MB）。
- **GB18030 线索判否**：`ship_skin_words` 整份按 gb18030 解出 10,692 个中日韩字，**但同内容随机打乱的零假设均值 = 9,724，比值 1.10**
  ⇒ 这就是 GB18030 对随机字节对的正常产出率，**不是文字**。别再拿"解出很多中文"当证据（CJK 区太大，任何 2 字节编码都过）。
- 形态旁证：整份数据里 `>=4` 连续高字节的游程**只有 9 段 / 87 字节** ⇒ 不是"文字流"形态，更像数值/编码流。
- ⚠️ **下一步最该注意的事实**：同一张表两个来源体积差 **70 倍** ——
  Lua 侧 `sharecfg/ship_skin_words.lua.bytes` = **80,505 B**，磁盘侧 `files/AssetBundles/sharecfgdata/ship_skin_words` = **5,615,904 B**。
  ⇒ 两者不是同一份内容（Lua 侧很可能是表结构/键，磁盘侧才是正文数据）；
  攻文法时要**两边对照**，不要只盯着 80KB 那份。参照载荷（scripts64 尾段 6,512 B）与磁盘侧同格式。

---

## §33. `sharecfgdata` 文法破了：假 LuaJIT 帧 + 平铺 kgc 常量流 + 字符串掩码 `^(255-i)`（2026-09-25）

**日期**: 2026-09-25　**状态**: ✅ 标量字段全通（台词中文已到手）　⏳ 嵌套字段待指令装配

**突破口不在本机**：二十轮统计攻击之后，决定性材料是 GitHub 上一个 0-star 仓库
`Fernando2603/AzurLaneDataExtractor`（Python，直接离线读 `sharecfgdata/<表>`）。本轮只做了一件事：
把它给出的格式事实**自研实现**并在我方真数据上验收（见"判据"）。

**文法（全部实测吻合）**：
- **记录帧**：记录首字节 = `ULEB(整条记录长 - 前缀自身长)`；`lock_next` 按此切窗，**逐条相加正好吃满文件**（见判据①）。
- **假 LuaJIT BC 头**：`ULEB rec_len` → 跳 3 字节（FrameSize/`<FrameSize+Flags>`/Flags）→ `ULEB(1B) upvalues` → `ULEB knum` → `ULEB kgc` → `ULEB 指令数` → `指令数×4` 字节 → `upvalues×2` → `knum` 个 `ULEB` ⇒ 之后才是常量区。
  实测 `ship_skin_template` 记录 1：`insn=54` → 常量区 @228，与手字节定位一致。
- **tag**：`00`=nil　`01 00 n 00`=数组(n−1 项)　`01 n 00`=字典(n 对)　`02`=true　`03`=ULEB int（32 位回绕）　`04`=double（两个 ULEB 拼 `<II`）　**其余一律是字符串**。
- **字符串** = `ULEB(字节长 + 5)` + 逐字节 `c ^ (255-i)`，**i 每串各自从 0 起**。⇒ `05` 就是空串；⇒ ASCII 过掩码正好落在 **0x80–0xBF**。
  这就是二十轮来所有「高字节游程 / 平均游程 6~8 字节 / 可打印率 0.216」的来源——**既不是压缩也不是文字编码，是 ASCII 套了递减掩码**。

**判据（三条各自独立）**：
1. **帧覆盖残差 = 0**：`ship_skin_words` 5,615,904/5,615,904、`ship_skin_template` 4,066,129/4,066,129，逐条记录长度相加正好等于文件长，空记录 0。这条不含任何主观阈值，是帧模型对错的直接证据。
2. **字段集合与外部人工 schema 对拍**：我方从数据里解出的高频字段（≥2000/2601 条）共 32 个 + `id`，与那个仓库里人写的 `ShipSkinWords` 字段表**逐项吻合**；连它注入的联动扩展键（`asmr_001..010`、`atelier_yumia_item_*`、`ryza_*`）也在我方数据里低覆盖出现——不是"我挑出来看着像"。
3. **值级交叉验证**：`ship_skin_words.drop_descrip` 非空 2565 条，其中 **93.6% 能在完全独立的社区基准 `inputs/azdata/azdata_ship_skin_template.json` 的 `desc` 里整串命中**（差异归因于设备侧 9.7.385 vs 快照 9.7.381 的版本差）。
产物：2601 行台词、40,897 个含中文字段值，落 `.diag/sharecfg_re/cfg_json/ship_skin_words.json`。

**「70 倍体积差」判明——原提问方式有误**：两侧**根本不是同一份内容的两种编码**。
- 用同一套掩码走 Lua 侧 `ship_skin_words.bytes`，解出的是 12 条串：`cs` `base` `all` `__namecode__` `__stream__` `confNEO` `__name` `ship_skin_words` `setmetatable` `rawget` `pg` ⇒ **Lua 侧是"读取桩"**（声明字段与 `(startPos,size)` 切片），磁盘侧才是数据本体。
- 磁盘侧只有 **32** 个文件，Lua 侧有 **774** 张表 ⇒ 只有 32 张流式大表外置。磁盘/Lua 比值从 3.0（`weapon_name`）到 496（`activity_coloring_template`）**无恒定关系** ⇒ 一切"压缩比/编码膨胀"解释当场出局。

**必须更正的旧结论（别在新会话里原样重跑）**：
- **§31「载荷不是 LuaJIT 字节码」**：只对**磁盘侧**成立（磁盘侧是**假** BC 帧，指令区是占位/自研栈码）。**Lua 侧很可能是真 LuaJIT BC**：`598597535/Azurlane-LuaHelper` 的 `Lua.cs` 说明 `1b 4c 4a 02 0a` 是真 BC，只是**指令首字节被 256 项 S-box（Resources 的 Lock/Unlock 表）置换、版本字节被改**。我方 `35` 号的 BC 探针按**标准 tag** 走 ULEB，必然 0 命中——那条否证打在"未改动的标准 dump"上，不是打在"游戏侧不是 BC"上。
- **§32 的 GB18030 判否**：**结论仍成立，但理由要换**——不是"随机字节的正常产出率"，而是**数据在掩码之下**，任何"直接按文字解"都必然失败。零假设对照本身做得对，只是它测的是未解掩码的字节。
- **§30「容器层不需要解密」**：对。当时缺的答案现在有了 = 上面那条文法。

**未闭环的缺口（下一步只做这件事）**：**嵌套字段的装配**。标量字段在常量流里是"键串紧邻值"，已全通；
但 `smoke` / `bound_bone` / `couple_encourage` 这类表/数组字段，在常量流里是**打散的分片**
（实测记录 1：`'smoke'`, `[-0.83,2.24,-0.59]`, `['smoke']`, `[30]`, `[-0.09,0.59,-0.15]`, `['smoke']`, `[70]`, `'bound_bone'`, … 对应基准里 `[[70,[["smoke",[…]]]],[30,[["smoke",[…]]]]]`），
装配关系写在假 BC 的**指令区**（4 字节/条，实测 `4e ff 00 00 | 51 ff 01 01 | 51 ff 02 02 | 09 fe 00 04 | 4d fd 04 05 …`，第 2 字节 `ff→fe→fd→fc` 递减 = 栈回引距离）。
两条路：**(a) 解这套栈码**（有 2863 条已知答案可当校验集，判据 = `--verify` 逐字段一致）；**(b) 走 LuaHelper 的 S-box 路线**。

**许可红线**：`AzurLaneDataExtractor` **无 LICENSE 文件、pyproject 也无 license 字段** ⇒ 默认保留全部权利，
**不得把它的源码 vendor 进本仓库**；本轮只采用其"格式事实"，reader 全部自写（`37` 号）。引用出处写进文档即可。

**方法论（下一轮该先做的第 0 步）**：遇到"标准解析器读不出的私有容器"，**先花 20 分钟检索有没有公开同族实现**
（本例关键词 `LuaConfDataReader` / `sharecfgdata` / `luabuilds` / `confNEO` 一次命中），
再做熵/IC/差分签名这类统计攻击——本项目为此多花了约二十轮。候选并入技能 `binary-container-vs-crypto` 第 0 步。

**涉及文件**: `tools/sharecfg_re/37_parse_sharecfgdata.py`（新增，自研 reader：`--trace` 头 / `--kgc` 常量流取证 / `--table` 单表出 JSON / `--verify` 与 azdata 基准逐字段比对 / `--all --yes` 全量）
相关：§30（www 三段）、§31（ASM 结论降级）、§32（TextAsset 有损解码）、WF-19、新 WF-20。

### §33 追加（同日 B 段）：帧模型在 32/32 张表成立 + 标量字段验收 99.974% + 三条新的硬判据

**帧模型扩到全库**：`--all` 跑完 32 张表 **140 MB / 220,568 条记录，帧覆盖残差全部为 0**（每张表逐条记录
长度相加正好等于文件长、空记录 0）。⇒ "记录帧 = `ULEB(len)`" 已经不是抽样结论。

**验收结果（原唯一判据）**：`ship_skin_template` **2863/2865 条记录的 id 命中基准**（多出的 2 条 = 385 新增皮肤），
**标量字段比对 138,669 对：一致 94,443 + 键缺失取默认 44,190 + 不一致 36 → 一致率 99.974%**。
36 处不一致逐条看过，全是 **381 快照 vs 385 设备** 的内容差：`name` `PINKLOVE★Heart Lancer`↔`标枪`、
`desc` `舷号CL-13`↔`CL-12`、`prefab` `jinluhao_4`↔`jinluhao_3`、`bg`/`shop_id`/`shop_type_id` 新增values。
⇒ **验收判据对标量字段已达标**，不需要再等密钥、不需要第三方工具。

**三条本轮新得到的硬判据（都比"看着像"强）**：
1. **`kgc` 字段 = 常量区顶层条目的精确条数**，且**最后一条必须正好停在记录末尾**。
   实测 `ship_skin_words` 记录 2：解出 6 条 == `kgc=6`，末条停在 @3676 == 记录末 ✓。
   这条能把我方解码偏差**定位到"读完第几条键值后错位"**（`ship_skin_template` 是第 20 条），
   而"条目数不对"本身就是判据，不需要人眼对齐字节。
2. **`01` 的含义按位置分**：在**常量流顶层** = 表头（`01 00 n 00` 数组 / `01 n 00` 字典），
   在**值的位置** = bool false。证据：@941 处 `01` 紧跟 `19`，而 `19` 正好是
   "spine_offset_profile"（20 字符）的长度字节 —— 若把 `01` 当表头，下一条必然崩。
   ⇒ 参考实现的 `read_bool`（`01`=false、`02`=true）与 `read_constant`（`01`=表）**不矛盾，是分工**。
   同类：`02` 在声明为 bool 的字段上是 `true`，在整数语境下是 varint（`spine_action_offset` 3 条即此）。
3. **空值不落盘**：字段键**不在记录里** = 该字段取默认值（`''`/0/false）。
   占比很大：44,190 / 138,669 = **31.9%** 的 (记录,字段) 对属于此类。
   ⇒ 把"未找到键"记成解析失败会假红灯；要按"基准要的是不是默认值"分桶。

**剩余缺口已被精确框定（下一步只做这一件）**：**容器字段的值不内联**。
21 个字段名（`bound_bone`/`fx_container`/`smoke`/`l2d_se`/`l2d_para_range`/`time`/`get_showing` …）
在基准里取 list/dict，占 **15,933 / 154,602 = 10.3%** 的字段对。失败形态高度一致：
只读到**第一片**（`smoke` → `[-0.83,2.24,-0.59]`，而基准是 `[[70,[["smoke",[…]]]],[30,[["smoke",[…]]]]]`；
`bound_bone` → `'antiaircraft'`）。⇒ 这些字段的**分片按后序平铺在常量流里，装配关系写在假 BC 指令区**
（4 字节/条，`4e ff 00 00 | 51 ff 01 01 | …`，第 2 字节 `ff→fe→fd→fc` 递减 = 栈回引距离）。
**别把这条当"已经快好了"**：参考实现自己也**没解指令区**（`SchemaReader` 注释原话
"SchemaReader is not gonna work with op codes, that for next time"），它靠的是**人写的 per-table schema + 按键定位取值**。

**已知产出缺陷（如实记录，别当已通过）**：`barrage_template_1/2/3` 三张表在"启发式配对"导出模式下
**解出 0 个字段名**（帧仍是对的，残差 0）；已另加 `--scalar-all`（键词表 + 只接受标量读）这条
与 `--verify` 同源的路径重导，两版逐表产出对比见 `docs/WORKFLOWS.md` WF-20 与本节末。

### §33 追加（导出层改前/改后逐表对比：启发式配对 → 键定位+只接受标量）

两种导出都在同一套已验证的帧模型上跑，产物各 32 份 JSON（`.diag/sharecfg_re/cfg_json` = 旧、
`cfg_json_scalar` = 新）。判据 = **没有任何一张表的"含中文行数"下降**（零回退），再比总量：

| 指标 | 旧（启发式配对） | 新（键定位） |
|---|---|---|
| 含中文行合计 | 42,959 | **69,435（+62%）** |
| 零字段表 | `barrage_template_1/2/3`（0 个字段名） | 3 张各 17 字段 / 26,914・211・903 条 |
| 从 0 救回的表 | — | `ship_skin_template` 0→2860 行、`expedition_data_template` 0→16133、`world_chapter_template` 0→643、`aircraft_template` 1616→4868 |
| 记录数 32/32 表 | 与帧模型一致（残差 0） | 同上（未变，说明只改了字段取法没动帧） |

`ship_skin_words` 专项对照：旧/新都是 **2601 行、2569 含中文、drop_descrip 非空 2565、整串命中基准 2400（93.6%）**
⇒ 新路径对已通过的表**逐字节同数**，不是"换个写法重新好看起来"。

**仍要如实记下的两条限制**（别让下游误用）：
1. **词表是超集**。字段名靠"全文能按掩码解成标识符 + 频次带 `2 ≤ c ≤ 1.6×记录数`"筛，
   所以 `ship_skin_template` 中位 63 字段 > 基准 54、`chapter_template` 110 > 实际——
   **多出来的是"跨记录共享的值串"（美术资源代号那类）**，下界不能抬高（`bg` 这类空值不落盘的字段频次很低）。
   ⇒ 要**权威字段表**只有两条路：用基准/社区 JSON 的键（`--verify` 就是这么做的），或像参考实现那样人写字段表。
2. **21 个容器字段名的值仍只读到第一片**（见上）。旧路径里那几张表连标量都取不全，新路径修好了标量，
   容器一律仍不完整。

---

## §34. 用新读到的表核对挂着的待办：4 项拿到权威答案、1 项只拿到一半；另抓到一处"只走第一条记录"的静默截断（2026-09-25）

**日期**: 2026-09-25　**状态**: ✅ 核对完成（只读，未改任何正式产物）　⏳ 回填动作待放行

**先更正 §33 的一处过度概括**：我当时写"Lua 侧是读取桩、磁盘侧才是数据本体"——
这句**只对那 32 张有磁盘副本的流式大表成立**。
另 **740 张只在 Lua 侧的表，数据是内联在同一容器里的**，用同一套 reader 直接可读。
证据：`voice_actor_cn` 解出 526 个字典常量、`character_voice` 85 条、`lover_nation` 16 条，
键值都是完整中文字段（`{'actor_name': '芳野由奈', 'code': 100}`）。
⇒ 以后问"某个名字在哪张表"，**先把 774 份 Lua 侧表当候选**，别再默认"文字只在 sharecfgdata"。

**★ 一条新的静默失败（假绿灯第 10 类）**：`load_lua()` 第一版**只解析第一条记录**就返回，
`voice_actor_cn` 因此报"**100 条**"（真值 **525 条**，文件里分了 7 条记录）。
记录分帧本身是对的（残差 0），但"文件里还有下一条"这件事**不会报错、也不会让长度对不上**，
只会让**计数偏小一个倍数**。
⇒ 规则：**任何按记录遍历的读取器，都必须走到 `pos >= len(buf)` 为止，并把"记录条数"当输出指标打印出来**
（本轮起 `load_lua` 返回 `nrec`，与文件长一起报）。
计数类结论（"表里有 N 条"）在没有"走完"断言前一律不可信。

**四项拿到权威答案（可直接当事实用）**：

1. **待办 #6 声优中文姓名** —— `voice_actor_cn` = **525 条 `code → actor_name`**（已导
   `.diag/sharecfg_re/voice_actor_cn.json`）。对 `ship_skin_template` 实际用到的 **499 个** `voice_actor` 值，
   只有 **2 个不在表里 = 哨兵值 `-1` 和 `0`**（未指派 CV），真实 id **覆盖率 100%**。⇒ "CV 姓名表未缓存"这个前提作废。
2. **待办 #10 ① 点击动作别名** —— `character_voice` 里三行直接给出答案，**不是语义推断**：
   `key=touch → resource_key=touch_1 → l2d_action=touch_body → spine_action=touch → voice_name=普通触摸`；
   `key=touch2 → touch_2 / touch_special / tuozhuai / 特殊触摸`；
   `key=headtouch → touch_head / touch_head / tuozhuai2 / 摸头`。
   ⇒ 之前"`touch_body→touch_1`、`touch_special→touch_2` 待按耳朵裁定"的两条别名**已被游戏自己的表证实**；
   且 `headtouch` 是第三条（此前画廊里没有对应认知）。
3. **待办 #10 ③ Spine/立绘配音触发名** —— 同一张表 **85 条全部带 `l2d_action` + `spine_action`**，
   `resource_key` 含 `detail/get/task/profile/feeling1-5/present_like/upgrade/login/main_1..7` 等
   ⇒ "数据在手未导出未接线"缺的正是这张对照表，现在不必猜了。
4. **待办 #7 的"385 新皮肤归属"** —— 盘上比 381 基准**多出 2 条**并已全部读出：
   `101267 金月桂香`（`painting=aierdeliqi_9`, `ship_group=10126`, `voice_actor=54`）、
   `101532 幽幽桥上，坏坏来袭！`（`painting=mile_3`, `ship_group=10153`, `voice_actor=446`）。

**一项只拿到一半（#7 阵营「晶环联盟」码）**：
- 阵营名**不是表字段**，而是 `gametip` 里一段**按数字 id 索引的短文案**：
  `1200 东煌 / 1201 撒丁帝国 / 1202 北方联合 / 1203 其他 / 1204 海王星 / 1205 自由鸢尾 / 1206 维希教廷 /
  1207 鸢尾教国 / 1208 哔哩哔哩 / 1209 传颂之物 / 1210 KizunaAI / 1211 hololive / 1212 维纳斯假期 /
  1213 偶像大师 / 1214 联动 / 1215 SSSS / 1216 飓风 / 1218 META / 1219 闪乱神乐 / 1221 郁金王国 /
  1224 danmachi /` **`1226 晶环联盟`**。
- 但 `nationality` 码 → 这段 id **不是位置对应**（码 1 是白鹰：杜威/卡辛/唐斯；码 3 是重樱：吹雪/白雪/绫波；
  码 97 = `·META` 后缀舰；码 101 = 涅普顿/诺瓦露 = 海王星…）。
- 已把 **32 个在用码各取 5 个舰名**列出来（`.diag` 里那次运行的输出），据此**大部分码能一眼定名**；
  剩下需要你一句话裁定的歧义码是 **98 / 99 / 111 / 112 / 113 / 12**（`晶环联盟` 大概率就在 113 这类"非联动原创阵营"里）。
- ⚠️ 边界：整串搜索 `0 命中` 只等于"不以整串形态存在"，**不等于概念不在数据里**（`塞壬`/`北联`/`极昼` 都是 0 命中，
  但显然存在——真名分别是 `北方联合`、且 `塞壬` 可能根本不叫这个写法）。
- **怎么一次定死**：`ship_data_statistics` 里每个码都有舰名，而阵营名清单已经拿到；
  要么你按舰名逐个认（10 分钟），要么继续找"哪个字段存 nationality→gametip id"（我还没找）。

**涉及文件**: `tools/sharecfg_re/39_find_string.py`（新增：给明文→全库定位，disk 32 + lua 772 共 159 MB）、
`tools/sharecfg_re/40_crosscheck_todos.py`（新增：五个待办的核对脚本，只读）、
`.diag/sharecfg_re/voice_actor_cn.json`（525 条映射，未入库的派生产物）。相关：§33、WF-19/WF-20、
[[量真实可观测状态]] 那条"假绿灯家族"再添一例（计数型结论必须有"走完"断言）。

---

## §35. 774 张 Lua 侧表全量落地 + 两张权威表接入管线；顺带复活了"三条路均已判否"的 namecode 表（2026-09-25）

**日期**: 2026-09-25　**状态**: ✅ 只读部分完成并自检　⏳ 三处写盘动作待放行

**① 774 张只在 Lua 侧的表已全量导成 JSON**（`41_export_lua_tables.py`，产物 `.diag/sharecfg_re/lua_json/`，
772 份，**未走完=0 张**）：判定 **DATA 639 / STUB 129 / 其它 4**。
⇒ 之后"某个东西在不在游戏里"这类问题，**先查这 639 张表**，比再逆向便宜一个数量级。

**② 顺带复活一条旧否证**：`name_code` 表现在读得开，**456 行** `{'code':'樱','id':1,'name':'峰风','nation':0,'type':1}`
= `{namecode:NN}` 占位符的码→舰名/级名对照表。
此前记的"邻近配对、指针扫描、BCDUMP 三条路均已判否"是**在没破文法的前提下**试的三条路，
不是"这张表拿不到"。⇒ 需要正式名时可走这张表（残余 ~52 个 story 类占位符有机会真解）。

**③ 两张权威表已发布进管线输入**（`42_publish_gamecfg.py`，不入库、台账 `inputs/gamecfg/MANIFEST.json`，
带 4 条真值自检）：
- `voice_actor_cn.json` 525 条：`voice_actor` 码 → 中文声优；
- `character_voice.json` 85 条：`key(台词字段) ↔ l2d_action(Live2D 动作组) ↔ resource_key(ACB cue) ↔ spine_action ↔ 中文语音名`。

**④ 消费方已改两处（都在读盘阶段，未跑写盘）**：
- `scripts/build_ship_meta.py`：新增 `entry['voice_actor_name']`（缺失时打警告不静默）。
  只读诊断实测：库尔斯克→`衣川里佳`、泛用型布里→`下田麻美`、阿布鲁齐公爵→`平田宏美` ✓。
- `scripts/extract_live2d_voice.py`：原来手写的 `ALIAS = {touch_body→touch_1, touch_special→touch_2}`
  （注释自承"语义推的，需人工试听确认"）**换成从 `character_voice` 生成**。结果两条猜测**被证实**，
  并且多认出 6 条此前根本不知道的别名：
  `battle→warcry`、`complete→expedition`、`hp_warning→hp`、`mission→task`、`wedding→propose`、`win_mvp→mvp`；
  `headtouch→touch_head` 是同名直配（第三条触摸键，画廊此前没有这个认知）。
  ⚠️ 生产映射表 `Output/gallery_v2/l2d_voice.json` 现状 = 253 皮肤 / 5914 条 (皮肤,动作组)，
  **重导才会拿到新 6 条别名** ⇒ 属"会影响已有正确结果"的批量写盘，**未跑，等放行**。

**⑤ 阵营码（#7）走到这里**：`gametip` 里 1200–1226 那段就是阵营名清单（**1226 = 晶环联盟**）。
试过两条自动对上码的路，**一条成一条否**：
- ❌ 否：`world_port_data.port_camp` + 文案里"…所属"反推 —— 实测 `port_camp=1` 同时给出
  皇家/白鹰/北方联合 ⇒ `port_camp` **不是** nationality 码，此路不通（阴性对照就是维基投票里码 1 干净的 732:1）。
- ✅ 成：`fleet_tech_ship_class`（含 `nation` + 中文舰级名）与 `ship_data_statistics` 双证，把未定码收窄成
  `101=海王星联动`（涅普顿/诺瓦露/布兰…）、`104=KizunaAI`（绊爱四种变体）、`117=尼尔`（2B/A2）、
  `12=只有"瓦尔帕莱索"一艘`、`99=构建者 + 仲裁者·提尔瑞特·VII`。
  **剩 12 / 99 两个码需要你按游戏内认知定名**（`晶环联盟` 最可能是 12，但这是推断，我不替你写死）。

**涉及文件**: `tools/sharecfg_re/41_export_lua_tables.py`、`42_publish_gamecfg.py`（均新增）、
`scripts/build_ship_meta.py`、`scripts/extract_live2d_voice.py`（各一处小改）。相关：§33、§34、WF-17。

**待放行清单（三项，都可单独退回）**：
1. `py -3 scripts/build_ship_meta.py --write` → 重写 `Output/ship_meta.json`（带 voice_actor_name）；
2. `L2D_VOICE_ALL=1 py -3 scripts/extract_live2d_voice.py` → 重导语音映射（拿 6 条新别名；先 1–3 个样本对照）；
3. 前端若要把声优名/新别名显示到画廊 → 需 `deploy_gallery.py` + WF-16 回归六件套。

**§35 补：别名改表驱动的 A/B 实测（只读，`--report`，写入=False）**
- 生产 `l2d_voice.json` 现状：253 皮肤 / **2504** 个 (皮肤,动作组) / 5914 个文件条目 / **20 种动作组**；
  其中 `complete`、`mission`、`wedding`、`hp_warning`、`battle`、`win_mvp` **各 0 个皮肤**（旧 2 条别名根本配不到）。
- 换成 `character_voice` 生成的 8 条别名后，抽样 16 个皮肤**全部**新出现 `complete / mission / wedding`，
  部分另得 `hp_warning / battle`；`无 ACB 17 / 有 ACB 但零交集 0`（与旧一致 ⇒ **没有皮肤因此改动丢掉原有配音**）。
- ⚠️ 度量口径教训：**5914 是"文件条目"数，2504 才是"(皮肤,动作组) 数"**，两者混用过一次；
  且首次 A/B 想用生产文件当"改前基线"是错的（它是 9-23 的旧动作组集合，见 WF-17 追加的判据）。
- 全量重导（会覆写 `Output/gallery_v2/l2d_voice.json`）**未跑**，等你放行；跑前按惯例先 1–3 个样本目视/试听。

---

## §36. E1/E2/E3 落地：声优名进正式文件、语音映射表驱动、`{namecode}` 对齐已证成（2026-09-25）

**E1 `Output/ship_meta.json` 已重写（带备份 `Output/_OLD_bak/ship_meta_pre_25.json`）**
逐字段比对（不是"跑成功了"）：**既有值变化 0 处、字段消失 0 处**；新增键 1 个 = `_ab`（本就 unresolved 的脏目录名），
新增字段实例 4281；**4041/4495 条目带 `voice_actor_name`**，无名 454 = 427 个剧情角色 + 27 个 `voice_actor` 为 0/-1 的船。
实测样本：库尔斯克→衣川里佳、泛用型布里→下田麻美、阿布鲁齐公爵→平田宏美。

**E2 语音映射改为表驱动并已重导**（备份 `Output/_OLD_bak/l2d_voice_pre_25.json`）
样本闸门（3 皮肤）实测：`antu_2` 11→14 组、`yibei_3`/`z23` 10→13 组，新增的都是
`complete→expedition.ogg`、`mission→task.ogg`、`wedding→propose.ogg`，**文件真实存在且非空**；
全库 253 皮肤**没有任何一个丢掉原有动作组映射**。
⚠️ **一条我自己制造的假红灯**：第一次校验拿 `Output/gallery_v2/` 当根去查那 32 个 ogg，报"全部缺失"——
映射表里的路径是**相对 `Output/`**（`Audio/L2D/<皮肤>/<cue>.ogg`），不是相对 `gallery_v2/`。
⇒ 校验路径类结论前先确认**前端实际用的那个根**（本例 `gallery_src/index.html` 用 `fetch('./l2d_voice.json')` + `Audio/...`）。

**E3 `{namecode:NNN}` ↔ `name_code.id` 已证成**（`tools/sharecfg_re/43_check_namecode_alignment.py`，只读，三条独立检验）
- T1 合法性：台词里 **1760/1760** 个占位符码都能在 `name_code` 查到（100%），其中 **90.5%** 解出的名字确为游戏内真实实体；
- T2 零假设对照：**自称率 20/941 = 2.13%**，而把码随机重分配给行的 200 次零假设 = **0.03%（区间 0~0.32%）⇒ 比值 80×**（判据线 ≥3）；
- T3 人眼：就地替换后语义自洽——拉菲(101170)"干掉[比叡]"、(101172)"从[绫波]那里拿来的"、
  (101173/101174)"被[Z23]说教"、布里(100021)"被[明石]欺负…保护指挥官的钱包"、(101041)"别告诉[明石]哦"。
⇒ §35 里那句"id 与占位符编号仍未对齐"的保守结论可以收掉了；**当年"38=克利夫兰"是错的（38=川内），
但那是"模板与成品不是同一行"造成的误配，不影响对齐本身**。
残余 9.5% 不是舰名（`name_code` 里 `type=2` 那类是装备/飞机名，如 id=10007 'F6F地狱猫（HVAR搭载型）'）。

**E4 阵营码辨认单**（`ship_data_statistics` 全部在用码里，`build_ship_meta.py` 的 `NATIONALITY` 还没中文名的只剩 5 个）

| 码 | 舰名（全部） | 我的推断 |
|---|---|---|
| 12 | 瓦尔帕莱索（该码下只有这一艘） | **晶环联盟**（=文案号 1226），未证实 |
| 99 | 构建者、仲裁者·提尔瑞特·VII | 塞壬系 Boss，界面可能显示"其他"，未证实 |
| 101 | 涅普顿、诺瓦露、布兰、贝露、绀紫之心、圣黑之心、群白之心、翡绿之心 | 联动-超次元游戏海王星（gametip 1204 '海王星'） |
| 104 | 绊爱、绊爱·Elegant、绊爱·Anniversary、绊爱·SuperGamer | 联动-KizunaAI（gametip 1210） |
| 117 | A2、2B | 联动-尼尔（自动再述）（A2/2B 同名） |

⚠️ 码 12/99 需按**船名**由用户裁定（用户明确说"单问编号我不确定"）；已否证的自动路：`world_port_data.port_camp`（见 §35）。

---

## §37. `subprocess(text=True)` 在 Windows 上按 GBK 解码子进程输出：一次全量重导在第 N 个皮肤上炸出线程异常（2026-09-25）

**现象**：`extract_live2d_voice.py --all` 跑到中途，日志里冒出
`Exception in thread Thread-255 (_readerthread): UnicodeDecodeError: 'gbk' codec can't decode byte 0xad`，
而 `--key antu_2,yibei_3,z23` 的**三皮肤样本完全正常** ⇒ 样本闸门没盖住这个缺陷。

**根因**：5 个脚本里的 `subprocess.run(..., capture_output=True, text=True)` **都没给 `encoding`**。
Windows 下 `text=True` 用**locale 编码**（这台机是 GBK）解码子进程输出。
`vgmstream -i` 会把 ACB 里的**日文/中文 cue 标签原样打进 stdout**，遇到非 GBK 字节 → 读线程抛异常 →
`r.stdout` 变 `None`。**只有内容里真出现那种字节的皮肤才触发**，所以小样本永远测不到。

**为什么危险**：`decode_all()` 不看 `r.stdout`（靠 glob 出来的 wav 文件），所以它**不会报错**；
但任何**解析 `r.stdout` 的路径**会拿到 `None` 并静默当成"零条" ⇒ 典型的"跑成功了但数据少了"。
（同项目的 `run_v2_full.py` 早就写了 `encoding="utf-8"`，说明这坑以前踩过一次但没扩散修。）

**修法（已改 6 处）**：所有 `text=True` 一律补 `encoding='utf-8', errors='replace'` ——
`scripts/extract_live2d_voice.py`(2)、`scripts/export_cue_audio.py`(2)、`scripts/extract_cpk.py`(2 命中 1 处新增)、`scripts/mumu_sync.py`(1)。

**判据/规则（新增，适用于本仓库所有脚本）**：
- **凡 `subprocess` 用 `text=True` 必须同时写 `encoding=`**；查法：`grep -rn "text=True" scripts/*.py | grep -v encoding=`。
- **子进程输出里可能带非 ASCII 的脚本，样本必须含"内容里真带非 ASCII"那一个**；
  只用 1–3 个"干净"样本过闸门，等于没测这类 bug。
- 校验"跑完了"不能只看有没有 traceback：以**处理条数**为准（本轮 `grep -c "组=" 日志` 对齐皮肤总数 270）。

**涉及文件**: `scripts/extract_live2d_voice.py`、`scripts/export_cue_audio.py`、`scripts/extract_cpk.py`、`scripts/mumu_sync.py`。
相关：§36（E2 样本闸门与"假红灯：路径根判错"）、技能 `safe-pipeline-fix-targeted-rerun`。

## §37 补：阵营码待办（§6 第 7 条）闭环
用户按舰名裁定：**码 12 = 晶环联盟**（旗下只有"瓦尔帕莱索"，战列/海上传奇）、**码 99 = 塞壬**
（构建者、仲裁者·提尔瑞特·VII）；另按舰名 + `gametip` 文案号对齐写死
**101 = 联动-超次元游戏海王星、104 = 联动-KizunaAI、117 = 联动-尼尔：自动再述**。
写进 `build_ship_meta.py` 的 `NATIONALITY` 后重写 `Output/ship_meta.json`：
逐字段比对 **删除 0 / 新增字段 0 / 仅 `faction` 变化 2 处**（`waerpalaisuo`、`waerpalaisuo_n` → `晶环联盟`）。
其余三个码在当前资产集里没有对应 bundleID（联动舰没有在画廊实体），**名字先进表、不影响现有条目**。
仍在「其他」的 14 条是布里系（码 98，无阵营），符合既有认知，不是缺陷。

## §38. E2 全量语音映射重导完成：+759 个动作组映射，浏览器实播四条全通过（2026-09-25）

**完成判定不看 exit code，看处理条数**：日志 `合计 270 个皮肤 | 无 ACB 17 | 有 ACB 但零交集 0 | 写入=True`，
`grep -c '组='` = **253** 与映射表皮肤数一致，`Traceback|Exception in thread` = **0**（§37 的编码修好之后）。

**逐皮肤零回退比对（对 `Output/_OLD_bak/l2d_voice_pre_25.json`）**：
| 指标 | 改前 | 改后 |
|---|---|---|
| (皮肤, 动作组) | 2504 | **3263**（+759 = 253×3） |
| 文件条目 | 5914 | 6948（+1034） |
| 丢掉动作组的皮肤 | — | **0** |
| 映射指向但磁盘缺失的音频 | — | **0**（6948 个全部存在，<2KB 的 0 个，合计 374.2 MB） |
新增分布恰好三种、每皮肤各一次：`complete`×253、`mission`×253、`wedding`×253。

**浏览器级实播验证**（`scripts/diag/l2d_voice_probe.py antu_2 complete,mission,wedding,touch_body`，
先在 8777 起 `Output/gallery_v2/_gallery_server.py`）：四组全部 `paused=False`、`cur` 在走、`readyState=4`、`err=null`
⇒ **前端一行代码没改就吃到新映射**（`index.html` 按动作组名通用查表，路径用 `new URL(P+p, location.href)` 解析）。
其中 `touch_body → touch_1.ogg` 实播成功 = 把 §35 那条"表驱动别名"从数据层面一路验到耳朵层面。
⚠️ 第一次探针报 `Cannot find default execution context`：**是本地服务器没在跑**，不是数据坏了——
探针依赖 8777，起服务后 `curl` 三个 200（页面/映射表/ogg）才继续。

**不需要重建索引**：`l2d_voice.json` 的读者只有 `gallery_src/index.html`（运行时 fetch）与两个 diag 探针，
`build_gallery_index.py` 不读它 ⇒ 无派生产物要跟着重跑。
**未跑 WF-16 六件套**：本轮**没有**修改 `gallery_src/index.html`，按 AGENTS 那条"改前端才必须先部署再跑回归"的触发条件不成立；
需要的话我可以补跑（`interact_verify`/`hit_verify` 等）。

---

## §39. 立绘名按大小写敏感比对：76 个目录被判"无源"，真无源只有 3 个（2026-09-25）

**症状**：`Output/ship_meta.json` 里 76 个 bundleID `source=unresolved`，画廊卡片显示拼音目录名
（`2b_2`、`aijiangdd`、`na_doa`、`linghangyuan1_2`、`npcbisimai_4_n`…）。上一轮的结论是
"社区快照缺数据 / 这些是无源剧情资源"——**两条都不成立**。

**根因（三条，按影响面排序）**：
1. **大小写**。配置里 `ship_skin_template.painting` 写 `2B_2` / `aijiangDD` / `npclafeiII_4` /
   `suweiaitongmengNew`，而磁盘 bundle 目录名一律小写；`build_ship_meta.py` 用 `s in painting2skin`
   精确比对 → 整批判成无源。**一个 `lower()` 就救回 27 个**（含 2B/A2/绊爱全系/雫/香迪/Z1改/苏维埃同盟）。
   顺带自证：这批取到的 `nationality` = 117/104/106/7/4，与上一轮人工认定的阵营码**逐条一致**。
2. **秘书舰 NPC 根本不在皮肤表里**（36 个）。`linghangyuan*`/`lingyangzhe*`/`tansuozhe*` 是指挥室换装立绘，
   `ship_skin_template` 无对应行 → 桥走不到。权威名在 `secretary_special_ship` 的 `head`/`painting` → `name`
   （领航员-TB / 领洋者-娜比娅 / 探索者-艾普洛），已发布为 `inputs/gamecfg/npc_painting_name.json`。
3. **同族资源**（10 个）：`npc<已知立绘名>`（剧情杂兵复制体）、以及"去掉最后一个 `_段`"就是已知立绘
   （`magedebao_pt_hx`→马格德堡、`nabulesi_blueprint`→那不勒斯）。

**结果**：`source` 分档 painting 2493 + suffix 1788 + painting_ci 119 + suffix_ci 46 + npc_table 36 +
npc_family 8 + family 2，**unresolved 76 → 3**（`_ab`、`unknown`、`tansuozhe21_2`，全 272.6 MB 已解出表里 0 命中）。

**已排除的假设 / 踩过的坑（三条都是本轮现场犯的）**：
- ❌「`painting_filte_map` 命中即算有来源」。它是 **2724 个立绘键的纯键表，不带任何名字**。
  第一版拿它当证据，虚报"65/76 有源"。**教训：判"有来源"必须要求来源能报出名字字段，不能只是"这个串出现过"。**
- ❌「区分大小写的精确等于就够了」。第二版仍漏 5 个（`aijiangDD`/`2B`/`Z1`）——表里是**混排大小写**。
- ⚠️「零回退」口径不能只挑自己改的那一档。第一版只比 `painting/suffix` 两档就宣布改动为 0，
  实际大小写回退**同时接管了 136 个原先靠手抄表 `SHIP_NAME_MAP` 兜底的条目**（外加 2 个 `manual`）。
  正确做法：把「换档」整体枚举出来（`旧档 -> 新档` 计数），再逐类找独立裁判。
- **歧义闸**：`painting.lower()` 做键时，只收"全表该键只有一种真实拼法"的，
  否则 `U556`/`u556` 这类同键多拼法会被悄悄猜走（全表实测仅 1 个键命中此闸）。

**独立裁判（防止"配置表说了算"的自证）**：76 处改名拿去查 `Output/WikiData/ship_data.json`（862 个维基舰名，
与配置表互相独立）——新值命中 70、旧值命中 13、**"只有旧值命中"0 条**，即没有一处是"手抄表本来更对"。
典型纠正：`hdn101` 伊织→涅普顿（en `HDN Neptune`，手抄表整条 hdn 系列错位一档）、`lafeiii` 拉菲III→拉菲II
（`USS Laffey II`）、`i13` I-13→伊13、`missr` R小姐→好人理查德、`haixiao` 海啸→海咲。

**闸门与涉及文件**：`scripts/diag/ship_meta_authority_diff.py`（四条硬判据，退出码即结论；另附维基投票只打印不判红）
→ `scripts/build_ship_meta.py`（四级解析优先级）→ `tools/sharecfg_re/45_publish_npc_painting.py`（发布 + 5 项自检）
→ `inputs/gamecfg/{npc_painting_name.json,MANIFEST.json}`（台账改为**按 path 合并**写回，`42` 号脚本同步改造，
否则两个发布脚本会互抹台账行）。**遗留**：`build_gallery_index.py` 组名查的是合成前缀 `linghangyuan1`，
ship_meta 里只有 `linghangyuan1_2` 等具体 stem ⇒ 36 个 NPC 名进了 ship_meta 但画廊卡片仍显示拼音（见 §6 第 5 条）。

### §39 追加：同一批残差的第二层根因——皮肤行的 `name` 是"皮肤标题"，不是实体名（2026-09-25）

接上文把 76→3 之后，`build_gallery_index.py` 仍有一截不对：组卡标题出现 `'TB'`、`'数据集：无数的我'` 这种值。

**根因**：5 个秘书舰换装立绘（`linghangyuan1_1`、`linghangyuan1_5`、`linghangyuan3_2`、`lingyangzhe3_2`、`tansuozhe_2`）
**先被皮肤表精确命中**，于是走的是 `cn = sk['name']`（皮肤标题），根本没轮到 NPC 表；
而 `secretary_special_ship` 里同一资源名的 `name` 是实体名（领航员-TB / 领洋者-娜比娅 / 探索者-艾普洛）。
两边都是配置原文，但语义不同层：**皮肤标题 ≠ 实体名**。

**修法（规则，不写例外名单）**：`build_ship_meta.py` 里"皮肤行没有对应舰级行"这一支，
若该立绘资源名同时出现在秘书舰 NPC 表里 → 实体名取表内 `name`，皮肤标题留在 `skin_name`，
并写 `name_via='npc_table:<命中的表键>'`（`_n` 变体记的是基资源名，便于事后逐条回查）。
影响 8 条（4 个实体 × 基图 + `_n`），`cn` 以外字段零变化。

**索引层的新兜底必须是"加法"**：`build_gallery_index.py` 组名兜底刻意排在 `SHIP_NAME_MAP` **之后**，
且要求来源档属于 `AUTHORITATIVE_CN` —— 于是它只可能把"当前显示拼音"的组变成有名，
**既有名字一律不动**。实测：画廊 1008 组里 +74 组有名（`with_cn` 910→984），
原本有名的组 0 处被改、皮肤集合 4491 条 0 处变化。这条判据形状比"改完看看对不对"强，因为它把
"我只做加法"变成了可机器核验的命题。
> 反面教材：若把该兜底排在手抄表**之前**，会连带改动 **112 组**已有显示名（`tbniang` TB娘→领航员-TB、
> `missr` R小姐→好人理查德、`strength` 力量→仲裁者·司特莲库斯·VIII…）——那不是不能做，而是
> **必须当作一次独立的、需用户拍板的展示层决策**，不能夹在修 bug 里顺手做掉。

**闸门随之收紧**：`scripts/diag/ship_meta_authority_diff.py` 的"受保护档必须 0 改动"多了一条**可审计例外**——
只放行 `name_via=npc_table:<key>` 且 `<key>` 确实存在于 `inputs/gamecfg/npc_painting_name.json`、
且 `skin_name` 仍等于旧 `cn`（证明皮肤标题没被丢弃）的 `cn` 改动；其余一律红。

**探针噪声记一条**：画廊页在 CDP 下恒有 1 条 JS 异常 `ReferenceError: THREE is not defined`
（`Output/gallery_v2/vendor/spine/spine-all.js:11216`，vendored 库的 three.js 可选依赖），
**与元数据无关**。写"页面无 JS 异常"这类判据时必须按 URL 把 vendor 库排除，否则每次都要重新查一遍。

---

## §40. Live2D 渲染成"部件堆叠的碎片"：贴图清单按枚举序落盘，而 moc3 只认索引（2026-09-26）

**症状**：用户报「本宁顿皮肤的 Live2D 是错乱的」。画面是几十个手臂/腿/脸的碎片互相叠成一堆，
背景却基本成形。同批 9-22 换入的 9 个 bundle 里，`benningdun_2` / `feiteliekaer_4` / `sebao_2` /
`shi_3` / `wuzang_4` 五个同样碎，另外四个（`bunao_3` / `gangyishawa_3` / `guanghui_9` / `pulimaosi_3`）完全正常。

**根因**：`model3.json` 的 `FileReferences.Textures` 是**按索引**被 moc3 消费的——数组第 i 项即索引 i。
而 `scripts/reconstruct_live2d.py` 落清单时用的是 UnityPy 的 `env.objects` **枚举顺序**，
枚举序 ≠ 索引序时整套贴图就整体错位，每个 art mesh 从别的图集里采样 → 碎片堆。
实测这 5 个的清单：`[02,01,00]` / `[01,00,02]` / `[01,00]` / `[00,02,01]` / `[02,01,00]`。

**为什么只有这 5 个**：全库 269 个模型扫下来，**乱序的恰好 5 个、坏的也恰好这 5 个**，
其余 264 个升序且画面正常。不是这 5 个特殊，是老模型**碰巧**枚举有序；新 bundle 只是把一个
一直存在的漏洞暴露出来。

**已排除的假设（都花过时间，别再走）**：
- ❌「moc3 版本 5 运行时读不了」。全库 moc3 头版本号分布 1/2/3/4/5 = 46/128/1/35/59，
  坏的 5 个和正常的 `bunao_3`、`pulimaosi_3` **同为版本 5**。版本不是分水岭。
- ❌「贴图文件缺了/多了」。269 个模型的 `Textures` 集合与磁盘 PNG 集合**逐个相等**，只有顺序不同。
- ❌「moc3 里能查到权威索引→贴图名」。查了，**269 个 moc3 里没有任何 `texture_*.png` 字符串**
  （只有 `Param*`/`Part*`/`Touch*`/`Glue__*` 这些）。索引→名字的约定只能来自命名本身
  （`texture_%02d` 的编号即索引），而 264 个正常模型正是这条约定的活证据。
- ⚠️ 顺带：moc3 头 offset 8 起的 `Format[8]/Size/CanvasWidth/CanvasHeight` 在本项目所有 moc3 里都是 0，
  按公开 moc3 规范去解 `Textures` 段会读出 95/347 这种荒谬计数——**别照规范硬解 moc3 头**，
  这条路上浪费过一轮。

**真正的过程根因（比 bug 本身更值钱）**：9-22 那轮换入后宣布的「9/9 全绿」，
判据是「idle 在播放窗口内驱动了多少条参数」（45/57/90/…条）。**参数动 ≠ 画面对**——
贴图错绑时参数照样动得很欢，代理指标全绿，而画面从第一天起就是碎的。
截图当时也拍了（`.diag/l2d9_shots/`），但只用来核对"有没有渲染出东西"，没人看内容。
⇒ **视觉产物的验收判据必须包含"看图"这一步**，且看图工具要现成，否则会被代理指标顶替。

**修法（改规则，不写 5 个名字的例外名单）**：
1. `scripts/fix_model3.py` 新增贴图清单归一段（按名中数字排序，无数字者排在带数字之后按名称序），
   WF-6 早就写着「纹理顺序 → 必须按名称字母序排列」这条决策，但**脚本里从未实现**——
   规则文档和实现脱节，老模型只是靠运气通过。
2. `scripts/reconstruct_live2d.py` 不改：它的产物由 `fix_model3.py` 统一规范化，单一职责。

**闸门**：`scripts/diag/l2d_texorder_check.py`——只读检查 269 个 `Textures` 是否升序，乱序退出码 1；
带 `--apply` 才改写并打印前后对比。改后复跑：`269/269 升序，乱序 0`。

**看图工具（本轮新增，补上过程根因缺的那块）**：`scripts/diag/l2d_shot_models.py <key> ...`
经画廊真实入口逐个打开 Live2D 皮肤，`Page.captureScreenshot` 带 canvas 的 `clip` 只截模型区，
落到 `.diag/l2d_shots_visual/`。

**验证**：5 个修复后逐个目视——本宁顿（海滩跑车）/ 瑟堡（棋盘格卧室）/ 菲特烈·卡尔（暗室桌面）/
诗（后巷）/ 武藏（演唱会舞台）全部成形；对照组 `bunao_3`、`pulimaosi_3` 截图与修复前一致
（这 2 个的文件本次**未被写入**，零回退由构造保证，截图只是复核）。
语义 diff 确认 5 个文件**除 `Textures` 顺序外无任何字段变化**，原件备份 `.diag/m3_snap/*.bak_texorder`。

**遗留（不在本次范围）**：画廊仍**没有**任何自动视觉判据；新 bundle 换入后的验收应把
`l2d_shot_models.py` 的截图列为必做项，而不是又用参数计数收工。

### §40 追加（同日）：顺手把「静默丢贴图」和「编号即索引」两件事一次查死

修完 5 个之后还剩两个没被证过的假设，各补一个全量只读审计：

**① `extract_textures()` 会不会静默少解一张？**
`reconstruct_live2d.py` 里是 `try: img = data.image / except Exception: continue`——
解码失败就**悄悄少一张**，产物结构照样合法，运行时不报错，只是引用该索引的部件采样到别的图集。
这和 motion 层曾经的 `"Curves": []` 空壳是同一类静默失败。
→ 新增 `scripts/diag/l2d_tex_completeness.py`：逐模型把源 bundle 的 `Texture2D` 清单与磁盘 PNG 对账。
全量 269 个结果：**missing 0 / extra 0 / 非 `texture_%02d` 命名 0 / 源 bundle 读不到 0**。这条假设排除。

**② 「贴图名里的编号 == moc3 索引」会不会只是从 5 个案例归纳出来的巧合？**
审计顺带打出一个更吓人的数字：**51/269 个模型的源枚举序 ≠ 编号序**（占 19%），
其中 `xuefeng` 是 `[02,05,00,03,04,01]`、`z23` 是 `[04,02,03,00,01]`。
也就是说：如果"编号即索引"是错的，这 51 个（尤其是乱得最狠的那几个）应该全都画成碎片——
而它们一直在画廊里、没人报过问题。
→ 拿乱序最狠的 5 个（`xuefeng` / `z23` / `weizhang_3` / `suweiaitongmeng_3` / `taiyuan_2`）逐个看图：
**全部成形无碎片**。约定在独立样本上成立，且**归一化那一步是承重的、不是装饰**
（46 个模型的历史产物已经是升序，说明早期某条导出路径排过序，但没人把它写进现在的脚本——
现在由 `fix_model3.py` 明确承担）。

**顺带修了看图工具自身两个会让它骗人的 bug**（都是本轮现场踩出来的）：
- 就绪门写成 `ev("typeof GALLERY!=='undefined'&&...&&GALLERY.ships.length") is True`——
  `A && B && C.length` 返回的是**数字**（ships 长度），`is True` 恒假，
  于是白等满 180 秒才继续，看起来像"工具很慢"而不是"门没生效"。改成 `String(...)=='true'`。
- 脚本启动时清空整个截图目录 → 第二次跑会把上一轮的证据删掉。改成只删本次要重拍的 key。
- ⚠️ 另记：`suweiaitongmeng_3` 首次看图时被判"姿势反常"（人躺在地板上、腿朝镜头）。
  拿 `Output/Paintings_v2/suweiaitongmeng_3.png` 一比即证伪——立绘本来就是道场倒地 + 前缩透视。
  **看图判据要说"和什么比"**，否则会像 §40 主因那样把代理指标当结论，反过来也会把正常画面当 bug。

---

## §41. Live2D「话没说完就被掐」：语音挂在 motion 的 `Sound` 字段上，生命周期属于动作不属于句子（2026-09-26）

**症状**：用户报「本宁顿的 Live2D 没做完动作和说完话就恢复回初始状态」。

**取证**（CDP 在文档创建前包住 `window.Audio` 录事件，见下方"探针"）：
```
t=0.0s  Audio 创建 + call:play
t=0.7s  loadeddata（dur=9.24s）
t=5.9s  call:pause ← currentTime=4.48s，同一刻 currentGroup 由 touch_head 翻回 idle
```

**根因**：语音是注入 `model3` 的 `definitions[g][0].Sound` 交给库的 SoundManager 播的，
而 SoundManager 的语义是"**下一条动作 startMotion 时 dispose 上一条**"。
idle 播完会由运行时自动回落 idle → 于是**动作结束 = 语音结束**。
只要 `语音时长 > 动作时长`，话必然被拦腰掐断。
碧蓝里这是常态不是例外（`benningdun_2` 实测 6 组超标：
`touch_head` 5.17s/9.24s、`touch_body` 5.07s/10.04s、`main_3` 7.82s/12.1s、
`mission` 9.23s/11.66s、`login` 9.48s/11.04s、`home` 10.62s/11.59s）。

**⚠️ 先排除掉的那个岔路**：一开始怀疑"动作导短了"。查下来
`Meta.Duration` == 全部曲线的最大时间戳 == 源 clip 末帧（`extract_motions.py` 的
`duration = max(real_t)`），**动作时长是忠实的**。5.17s 就是游戏里那条 touch 动画的长度。
→ 少这一步就会去改数据层，把正确产物改坏。

**修法**：语音不走 `Sound` 字段，改由页面自己持有一个 `Audio` 元素：
- **只有用户再次触发动作**（下拉 / 重播 / 点部位，都经 `play()`）才打断上一条；
- 运行时回落 idle **不打断**（回落不经过 `play()`，这就是解耦点）；
- 切标签 / 换皮肤经 `my.off()` → `stopVoice()` 打断，不留幽灵音。
非用户手势时 `el.play()` 会被浏览器拒（部分皮肤 `idleGroup` 落在 `home`，而 `home` 带语音），
`.catch()` 静默降级——与改动前行为一致，不是新问题。

**验证**：同探针复跑，`group` 在 dt=6.6 已翻回 `idle`，而音频 `paused:false`、
`currentTime` 一路推进到 4.52 ≈ `dur` 4.53，**完整放完**。

**探针（已入库）**：`scripts/diag/l2d_voice_lifecycle.py <皮肤key> <动作组> <采样秒>`；核心手法是
`Page.addScriptToEvaluateOnNewDocument` 里包住 `window.Audio`，记录
`play/pause/ended/loadeddata` + 每次事件的 `currentTime`。
⚠️ 事后在 console 里找"当前有哪些 Audio"是找不到的——库 new 完就藏进闭包，
且自建元素不入 DOM，`document.querySelectorAll('audio')` 恒为 0，会误判成"根本没播"）。

---

## §42. Spine 动态立绘缺整块身体：`setSkin` 一次都没调用过（2026-09-26）

**症状**：用户报「阿罗芒什的皮肤下半身不见了，立绘原件倒是显示完整的」。

**根因**：spine-ts 3.8 里动画的附件时间线经
`Skeleton.setAttachment(slotIndex, name)` → **`当前 skin.getAttachment(slotIndex, name)`** 解析。
不设 skin 时，凡附件只存在于命名 skin 里的槽位一律解析成 `null` → 整块不显示。
`gallery_src/index.html` 与 `cg_export.html` 里 `setSkin`/`findSkin` **零命中**
（index.html 中的 `setSkin(sk)` 是画廊自己的"切换舰皮"函数，与 Spine skin 同名不同物，**grep 时极易看错**）。

**影响面（全量扫描实测）**：`scripts/diag/spine_skin_scan.py`，331 个 part / 391.6MB，172s 跑完：

| part | 不设 skin | 最佳 skin | 缺失槽位 |
|---|---|---|---|
| `yunlong_2` | 262 | `1` → 331 | **69** |
| `feiteliedadi_5` | 242 | `2` → 294 | **52** |
| `aluomangshi_2` | 154 | `1`/`2` → 201（平手） | **47** |
| `yuekechengii_4` | 261 | `3` → 275 | **14** |

其余 324 个 part `gain=0`（只有 `default` skin 或命名 skin 不新增覆盖）→ **受影响 4/328 = 1.2%**。
阿罗芒什补回的 15 个槽正是 `datuiLA_2`(大腿) `xiaotuiLA_1`(小腿) `tuiRA_1/2`(腿)
`jiaozhiLA_1~4`+`jiaozhiRAb_1~4`(脚趾) `shentiA_1`(躯干)。

**⚠️ 这条判据差点自证成功**：第一版 `cover()` 把"纯 setup pose 的附件并集"也算进去，
而 setup 附件走 `slotData.attachmentName`、**与 skin 无关**（阿罗芒什每个 skin 都 145），
于是四个 skin 全相等、`gain` 恒为 0 —— 阳性对照（已知坏掉的 aluomangshi_2）当场报"没影响"才发现。
→ **判据必须只量"动画跑起来之后实际挂上的附件"**；并且任何全量扫描都要先拿一个已知阳性样本验判据会报警。

**修法（改规则，不写 4 个名字的例外表）**：`loadPart()` 内对 `∅` 与每个命名 skin
各算一次"推进若干动画后曾挂上附件的槽位数"，取最多者作默认；
控制条加「皮肤」下拉（含 `(不设 skin)` 项）可手动切着比。
平手时（阿罗芒什 `1` vs `2` 都是 201）按 skin 列表顺序取第一个，交给下拉人工判。

**验证**：同视口对照截图——`∅` 与 `1` 画面大小完全一致，`∅` 无腿、`1` 有腿
→ 部件补回且**不改变构图**。`2b_2`/`a2_2`/`adaerbote_4`（`gain=0` 的对照）渲染无变化。

**顺带查出的另一件事（未修，独立缺陷）**：这些骨架的 `fit()` 被
`hei1`/`hei2` 两片 **28284×18082 单位**的近透明黑色遮罩撑大，包围盒
`[-13750,-7851,14534,10231]` 远大于可见舞台 → 弹窗视图里整幅画面只占中间一小块。
实测**与 skin 无关**（两种 skin 下 bbox 逐字相同），是既有问题；
本轮试过"把 fit 挪到首帧 apply 之后"，无效，已退回（那会改掉全部 231 个皮肤的默认取景，
收益为零）。要修得让 `boundsOf` 排除超大遮罩层或按可见 alpha 过滤。

**扫描同时暴露 3 个另一类故障**（骨架压根建不起来，画廊显示"N 层失败"）：
`suweiaitongmeng_4`、`yuanchou/yuanchouB`、`yuanchou_hx/yuanchouB` —— `Region not found in atlas`。

> ⚠️ **本条上一轮写的"区域名编码不一致（mojibake）"结论作废**（同日更正，见 §44）：
> `yuanchouB.skel` 里那个名字的原始字节是 `0b e5 9b be e5 b1 82 20 36 36 34`
> （`0b`=spine 的 len+1，实取 10 字节）= **UTF-8 的 `图层 664`**，与 `yuanchouB.atlas` 里的区域名
> **逐字节相同**。两边都是合法 UTF-8，没有编码不匹配。那个 `￥ﾛﾾ￥ﾱﾂ` 是**我的扫描脚本
> stdout 被按 GBK 解码**打出来的假象（同一条日志用 UTF-8 打印时确实抛过
> `'gbk' codec can't encode`）。⇒ **报"编码/字节层"结论前必须直接 hexdump 原始字节，
> 不能引用任何经过终端编码的字符串**——§40 那条"工具自身会骗人"的教训当天以另一种形式重演。
>
> > ⚠️️ **上面这段"更正"本身又被更正了一次（同日第三次，见 §45 末）**：直接读日志文件的原始字节，
> > mojibake **确实写在文件里**（`ef bf a5…` = U+FFE5 U+FF9B… = `0xFF00+原字节`），
> > 所以它**不是** stdout 按 GBK 解码的假象，而是**浏览器内 skel 字符串读取路径**产出的。
> > 仍然成立的只有"两侧文件都是合法 UTF-8"这一半；"编码不匹配"这个方向因此重新成立，
> > 只是位置从文件挪到了运行时。哪一步在做单字节解码**仍未查死**。
>
> 已查清的事实：`图层 664` 是该 atlas **文件的最后一个区域**（440–446 行，447 为结尾空行），
> 解析后取不到。方向指向"页尾最后一个区域在 page 收尾时被丢"，
> 需真解析器打印 `pages[*].regions[*].name` 才能定死机制。`suweiaitongmeng_4` 是否同因未验。


**③ 目视覆盖到哪一步（防止下一轮把"26 个看过"读成"全库验过"）**
共逐个看图 **26 个 / 269**，抽样设计是**按 (moc3 版本 × 贴图数) 分桶全覆盖**（全库共 15 个桶）：

| 批次 | 模型 | 结果 |
|---|---|---|
| 修复的 5 个 | benningdun_2 / feiteliekaer_4 / sebao_2 / shi_3 / wuzang_4 | 全部恢复成形 |
| 对照组 2 个 | bunao_3 / pulimaosi_3 | 与修复前一致（文件未被写入） |
| 枚举序最乱 5 个 | xuefeng(6 张) / z23(5) / weizhang_3 / suweiaitongmeng_3 / taiyuan_2 | 全部成形 |
| 分桶抽样 14 个 | aidang_2 / aierdeliqi_5 / lingbo / lafei / biaoqiang / abeikelongbi_3 / adaerbote_3 / banerwei_3 / buleisite_3 / aersasi_2 / anninvwang_2 / aersasi_3 / gangyishawa_3 / guanghui_9 | 全部成形 |

**未发现新增破损**。⚠️ 边界要说清：这证的是"**贴图索引绑定**这一类故障在全库已无残留"
（另有 269/269 结构闸门 + 269/269 完整性对账兜底），**不等于** 269 个模型没有别的视觉缺陷——
其余 243 个未被目视覆盖，非贴图绑定类问题（部件错位、参数残留、判定区）仍需按个案报上来查。
截图目录 `.diag/l2d_shots_visual/`（已 gitignore，不进仓库）。

---

## §43. 画廊前端"看起来是两份重复副本、还双击打不开"，差点被当垃圾删掉（2026-09-26）

**症状**：用户看 `gallery_src/` 说「和 Output 里那个画廊重复了，而且这个还点不开，用不上吧」。
这句话若被执行，删掉的是画廊前端 65KB 逻辑的**唯一版本化正本**。

**根因（三条，逐条取证，不是推测）**：

1. **两边确实是两个独立副本**：`stat -c %h` 实测 `nlink=1` 各一份（不是硬链、不是引用），
   唯一连接是 `deploy_gallery.py` 里一行 `shutil.copy2`，单向 src→dst。
   → 所以「改了正本」和「运行目录生效」之间隔着一次手工部署，忘了就是**改了等于没改**（本项目已有先例）。
2. **"点不开"是路径基准按自身位置算的**：`_gallery_server.py:22` `ROOT = os.path.dirname(HERE)`，注释假设自己在 `gallery_v2` 里。
   从 `gallery_src\` 双击时 `ROOT` 变成仓库根，于是去请求 `/gallery_v2/index.html`（第 28 行）→ 不存在；
   同时第 54 行会打 `[警告] 当前目录没找到 index.html`。**这份 bat 是待部署文本，从设计上就不该被双击。**
3. **"重复"错觉背后是 `.gitignore` 的分工**：第 32-55 行的扩展名清单只挡二进制/媒体，**完全不含 `.json`**；
   而 `Output/` 下有 24,879 个 json（重导出的 motion3/model3 资产本体 + `_OLD_bak` 换前备份 15,560 个）。
   真正挡住这些的是第 13 行整目录规则——它挡的不是图片，且被它挡的东西**一个都不可复原为"远程仓库里的一份"**。

**处置**：把「两份副本」变成「一份数据两个名字」——硬链接。

- `deploy_gallery.py` 加三态：`--check`（只比对，漂移即 `exit 1`）/ `--relink`（换链）/ 默认（copy 修复，保留为断链后的回退手段）。
- `--relink` 前置闸门：两边 md5 必须逐字节相同才换链；**正本相对 HEAD 有未提交改动的文件自动跳过**
  （本次就靠这条守住了另一会话正在写的 `cg_export.html`，16:05 才落盘）。
- 换链 **4/4 已完成**：`index.html`、`_gallery_server.py`、`启动资产浏览器.bat` 首轮完成；`cg_export.html` 在脏文件闸门放行后（那会话 16:30 提交 f232d23）补跑 `--relink` 换好。**这道闸当场就值回票价**——首轮它挡住了另一会话 16:05 刚写、16:30 才提交的活跃文件。

**判据（每条都实测过，含失败分支）**：

| 要证的 | 怎么测 | 结果 |
|---|---|---|
| 换链真发生 | `stat -c 'nlink=%h ino=%i'` 两边 | `nlink=2`、inode 相同 |
| 改正本即刻生效 | 往 `gallery_src/index.html` 追加探针注释，读运行目录 | 两边 md5 同步变、运行目录侧 grep 到注释；随后按原字节还原，`git diff HEAD` 干净 |
| `--check` 会报红 | 人为把 bat 断链并改内容 | `! 启动资产浏览器.bat 漂移…`，`exit=1` |
| `--relink` 不覆盖差异 | 同一漂移态下换链 | `! 两边内容不同，拒绝换链`，`exit=1` |
| 修链路径通 | 默认部署刷平 → `--relink` → `--check` | 恢复 `nlink=2`，`exit=0` |
| 画廊照常可访问 | 用**真实部署的** `_gallery_server.py` 起 8777 回环取文件 | `index.html` 200/65066B、`vendor/live2d/pixi.min.js` 200/476988B、`index.json` 200/829010B、`Cache-Control: no-cache` |

**踩坑**：造漂移的测试脚本按 utf-8 读 `启动资产浏览器.bat`（**GBK**，`chcp 936`）→ `os.remove(dst)` 之后才抛 `UnicodeDecodeError`，
把运行目录副本留成 0 字节。**碰 bat/中文控制台文件的探针一律二进制读写**，且断链类操作先备份再动手
（本次备份在 `Output/_OLD_bak/gallery_hardlink_20260926/`，4 个文件齐全）。

**副作用要说清（硬链唯一的失效场景）**：编辑器若用「写临时文件 + `os.replace`」保存，会**静默断链**
（实测：rename 覆盖后两边 inode 立刻不同、`nlink` 回 1）。所以 `py -3 scripts/deploy_gallery.py --check`
是长期护栏，改过前端就跑一次；它也该进 WF-16 回归的第一步。

> **⏱ 上线 3 小时就真断了一次，并暴露判据本身的漏洞（同日 17:00 追加）**：另一会话 16:52 整文件写回
> `gallery_src/index.html` → 该条 `nlink` 回 1、与运行目录变回两份独立副本。当时 `--check` 只按
> **内容**判定，于是打印一行 `已一致（独立副本，可 --relink）` 后 **`exit 0`** ——
> **等于对唯一会真实发生的失效模式给绿灯**，用户一问"以后是不是很容易断"才被翻出来。
> 修法：`--check` 的判据从"内容一致"改成"**4 个文件都必须同 inode**"，断链（哪怕内容仍一致）即 `exit 1`，
> 并在消息里区分三种态：全绿 / 断链未漂移（`--relink`）/ 断链且漂移（先 copy 刷平再 `--relink`）。
> 两条一般性教训：① **护栏要盯住"会静默变坏的那个量"，而不是"最容易测的量"**——内容比对好测，
> 但失效是从"结构退化"开始的，只测内容就必然漏；② 断链**不丢数据、画廊照常打开**，退化的是"忘部署"
> 这个老失效模式，所以它天然不痛不痒，只能靠非零退出的检查拦。约定同步写进 AGENTS.md 收尾清单第 1 条：
> 改 `gallery_src/` 正本一律**原地编辑（Edit）**，不整文件写回。

**涉及文件**：`scripts/deploy_gallery.py`、`gallery_src/`（4 个正本，git 唯一跟踪路径）、`Output/gallery_v2/`（同一份数据的第二名字 + 生成物）、`.gitignore:13`、`.gitignore:32-55`




---

## §44. 画廊首屏是未排序的：启动只调 `renderGrid()`，从没调过 `apply()`（2026-09-26）

**症状**：用户报「现在打开网站默认界面好像不太对，都是我点一次其他按钮再回来才是初始界面，
比如我一打开，就将 meta 阵营排在上边」。
（这里的 "meta" 是游戏里的 **`-META` 变体舰**，不是页面元数据——第一版我理解错了，
按"DOM 顺序/筛选高亮"猜了两次，都被自己的取证否掉：`全部` 按钮确实带 `class="on"`、
`catFilter=''`，DOM 结构 HEADER→MAIN→mask 也正常。）

**根因**（一行代码）：
```js
let view = ships.slice();          // 161 行：初值 = 索引原序
function apply(){ ... view.sort(...)  renderGrid(); }   // 217/231-236：排序只在 apply 里
['fFaction','fType',...].forEach(id=>...addEventListener('change',apply));  // 只绑事件
...
renderGrid();                      // 855 行：启动直接渲染，绕过 apply()
```
⇒ 第一屏是 `index.js` 里的原始顺序（VTuber 联动角色与 `-META` 变体排在最前），
用户**随便点一个筛选控件**才触发 `apply()` → 排序 → "看起来正常了"。
由 `126e16e`（按 category 分「舰船/剧情角色」）引入，不是本轮改动造成
（本轮那六个 hunk 全在 `renderLive2D`/`startSpine` 内，落地页不走这两个函数）。

**修法**：启动改为调 `apply()`（它自己会 `renderGrid()`），并加注释说明为什么不能直接 `renderGrid()`。

**验证（两个独立观测，不靠"看起来对了"）**：
- 页面内读首屏 6 张卡名：改前 `夏色祭 / 大神澪 / 好人理查德 / 探索者 / 时乃空 / 海蕾`（原序）
  → 改后 `2B / 阿贝克隆比 / 阿布鲁齐公爵 / 阿达尔伯特亲王 / 阿蒂利奥·雷戈洛 / 阿尔贝托·迪·朱塞诺`
  （按名称正确排序），且再手动派发一次 `fSort` change 事件，序列不变（幂等）。
- 首屏截图目视：META 变体回到自己该在的位置。

**⚠️ 探针踩坑两条（都会把"工具坏了"当成"产品坏了"）**：
1. **CDP 连错 target**：`/json` 里第一个带 `webSocketDebuggerUrl` 的不一定是目标页。
   必须按 `'gallery_v2' in tab.url` 过滤，否则 `Runtime.evaluate` 直接超时。
2. **`subprocess.Popen(chrome...)` + `proc.terminate()` 不回收浏览器进程**：
   启动器进程被杀，Chrome 浏览器进程随 `--user-data-dir` 常驻。下一次用**同一个 profile**
   启动会直接复用那个旧实例（拿到的是**上一轮的页面**），于是出现
   "我已经改了并部署了，截图却还是旧的"这种假矛盾。
   ⇒ 探针要么每次用唯一 profile（`chrome_x_<timestamp>`），要么收尾按 profile 精确清进程。
   本轮就是这么被坑了一次，清掉 13 个泄漏实例后才拿到真结果。

---

## §45. Spine 弹窗"整幅只占中间一小块"：取景把"挂了附件"当成了"会画出来"（2026-09-26）

**症状**：部分皮肤的 Spine 动态立绘在弹窗里缩成中间一小块，四周全是空白。

**根因（一句话）**：`startSpine` 的 `boundsOf()` 只判断"这个槽位挂了附件"，不判断
**这个附件会不会真的落到像素上**。美术在同一层放的整屏闪黑/闪白遮罩根本不着笔，
却按自己的尺寸决定取景框。

**实测最坏的两个**（`.diag/l2d_shots_visual/`，走画廊真实入口打开、量"非背景像素占视口"）：

| 皮肤 | 撑爆取景的部件 | 世界尺寸 | setup/全程 alpha | 改前画面长轴占满 | 改后 |
|---|---|---|---|---|---|
| 四万十 `siwanshi_4` | `hei` `bai` `k` `wlk` | 21879×18909 | 0 / 0 | **0.157** | 0.842 |
| 法戈 `fage_2` | `Layer 267` | 32967×29970 | 0 / 0 | **0.165** | 0.706 |
| 摩尔加登摄政王 `mojiaduoer_5` | `bj2` | 37380×21450 | 0 / 0 | ≈0.11（由 5.01 倍反推，未单独留改前图） | 0.539 |

（"长轴占满"= 内容在较长那一轴上占视口多少；**满分线是 0.91**，因为适配本身留 1.1 倍边。
面积占比会被宽高比失配稀释，单独看会把正常竖图误读成取景过小 —— 所以两个数都要报。）

**全量影响面**：`scripts/diag/spine_framing_scan.py`（只读，331 part / 40s，
末尾 `SUMMARY` 一行）→ **13/328 受影响**（>1.05 倍），其中 5 个 >1.5 倍、3 个 >3 倍，最大 9.6 倍。
其余 315 个 `gainSetup=1.0`，即包围盒逐字不变。

**判据差点选错（阳性对照救回来）**：第一版用"沿**所有**动画采样，只要曾有过 alpha>0 就算内容"，
`siwanshi_4` 当场报 `gain=1.0` —— 闪黑幕在**某条**特殊动画里会亮一下，就永远算内容，
而取景只发生在 setup 那一刻。改成"**setup 时刻** alpha 是否为 0"后，同一对照立刻报 9.6 倍。
⇒ **凡"筛选集合"类判据，要问对象在判定时机上是什么状态，不要问它一生中出现过什么状态。**
另外必须读 `slot.data.color.a`（setup 色）而不是 `slot.color.a`（当前色）：
后者被动画时间线改写，用它会让用户按「复位」时取景框随动画时刻跳。

**修法（1 行，`gallery_src/index.html`）**：`boundsOf()` 里加
`if(slot.data&&slot.data.color&&slot.data.color.a<=0.001)continue;`。

**验证**：13 个受影响皮肤 + 3 个对照（`2b_2`/`a2_2`/`adaerbote_4`，`gain=1.0` 故包围盒逐字不变）
逐个打开弹窗截图**逐张看图**：无一处裁切回退；`qinli_2`/`molici_2`/`bojiateli_2`/`mosike_2`/`yunlong_2`/
`z15_2`/`baifeng` 构图正常，`siwanshi_4`/`fage_2` 从"一小块"变成满幅。
Live2D 侧未跑回归，依据是作用域：`boundsOf` 在 `startSpine` 内出现 2 次、函数外 0 次（grep 已核）。

**❌ 试过并否证的修法：按像素收紧（首帧 `readPixels`）**。CG 导出层就是这么做的，看着最"权威"，
但**在弹窗里不能用**：动画从第一帧就在跑，且 spine 的页纹理是首次 `draw` 时才上传，
读回来的是"局部已就绪"的渲染 —— `mojiaduoer_5` 被量成一个只含天空渐变小块的框，
放大成一屏模糊色块（截图见 `.diag/l2d_shots_visual/`，已回退）。
CG 层能做是因为它渲的是静止姿态、且 `draw()` 后显式 `sleep(30)` 等 GPU。
**"理论上更精确"的方案必须过全量实测**，这条又应验一次。

**⚠️ 残留的第二类，本轮未修 →（同日下一轮已修，见 §46）**：**不透明的纯色巨幕**同样撑爆取景，
但它真的在渲染，所以"是否落笔"这类判据对它无效。
判据换成"既要不透明、还要不是纯黑"后，扫已导出的 234 张 CG（离线 PIL，逐张比"含 alpha 包围盒"
与"去掉近黑像素后的包围盒"）：**12/234 受影响（5%）**，线性缩小 2.06~6.78 倍：
`suweiaitongmeng_4` 6.78、`yunlong_3` 6.06、`weikesibao_3` 3.46、`haichou_2`(+`_asmr`) 3.11、
`antu_3` 3.02、`maoxianhao_2` 2.82、`aluomangshi_2` 2.81、`hu_2`(+`_asmr`) 2.66、`aimudeng_5`(+`_asmr`) 2.08。
其余 222 张该比值中位 1.01、p90 1.06 —— 即这一类是**少数且可枚举**。
两条捷径都已排除：
1. **按部件名**（`hei`/`bai`/`heimu`/`1heidi`）不行 —— 2B 的**整幅背景板**就叫 `bj_1`（4513×2655），
   它是真内容，按名字排除会把 2B 裁掉。
2. **按纯黑乘数**（`slot.color.rgb==0`）不行 —— 这些黑幕的 setup 颜色实测是 `rgb=1,1,1 a=1`，
   黑色来自**贴图本身**；全库只有 `yunlong_3` 的 `kkkkk*` 与 `mojiaduoer_5` 的 `bj2` 是 `rgb=0,0,0`。
⇒ 剩下的唯一可靠判据是**读 atlas 页纹理**逐附件算"它落的像素里有没有非近黑颜色"。
确定性（与动画时刻无关）、但要在弹窗里为每个 part 做一次 `getImageData`，
且为与弹窗一致还得重导那 12 张 CG —— 故单开一轮，等确认。

**顺带更正 §42/§44 里我上一轮的"更正"**：怨仇那个 `￥ﾛﾾ￥ﾱﾂ 664`，我昨天写的是
"我的日志按 GBK 解码打出来的假象"——**这句也是错的**。直接读日志文件的原始字节：
`ef bf a5 ef be 9b ef be be ef bf a5 ef bf b1 ef bf 82`，按 UTF-8 解出的是
U+FFE5 U+FF9B U+FF9E U+FFE5 U+FFB1 U+FF82，**每个字符恰为 `0xFF00 + 原字节`**
（`图层` 的 UTF-8 = `e5 9b be e5 b1 82`）。而日志里的串是浏览器 `Runtime.evaluate` 返回值经
CDP JSON → websocket 送回来的，中间没有任何终端解码环节。
⇒ **mojibake 产生在浏览器内的 skel 字符串读取路径上，不在我的输出端**；
文件两侧都是合法 UTF-8 这件事仍然成立，但"编码不匹配"的方向因此**重新成立**，只是位置从
"`.skel` vs `.atlas` 文件"挪到了"skel 侧解码 vs atlas 侧 `Response.text()` 的 UTF-8 解码"。
具体是哪一步做的单字节解码**仍未查死**（cp932/shift_jis/euc_jp/big5 都抛错，latin-1 给 U+00E5 而非 U+FFE5，
所以不是常见的换码表）。另：`suweiaitongmeng_4` 缺的是 `ab_sync_3_1_zuoxiong_1_2`，**纯 ASCII**，
与怨仇不同因，属"atlas 里真没有这个区域"。

---

## §46. 取景第二类：不透明纯色巨幕——判据必须是"贴图 × slot 颜色"，不是 alpha（2026-09-26）

**承接 §45**：那条修掉了"setup alpha=0 的巨幕"（13/328）。同一轮末尾记的残留是另一类——
**它真的在渲染，所以任何"会不会落笔"的判据都拦不住**。本轮修掉。

**症状**：安土、阿罗芒什、维克斯堡三、海棠、埃姆登、北卡……弹窗与 CG 都是"一大片黑里嵌一小块画面"。

**根因**：美术在立绘层下面放了一整块**不透明纯色板**当黑底，尺寸远大于舞台内容。
它 alpha=1、真的往屏幕上画，于是顶点包围盒被它决定。

**为什么前一轮的判据不够，以及两条捷径为什么不行**（都是当场量出来的，不是推的）：
1. **黑色有两种来源**：`1heidi`/`heimu` 是**黑色贴图 × 白乘数**；而 `yunlong_3` 的 `kkkkk*`
   是**白色贴图 × `rgb=0,0,0` 乘数**——只看贴图它的亮度是 255，完全不像黑底。
   ⇒ 判据必须**把区域纹素乘上 slot 颜色之后**再统计，缺一侧都会漏掉一半。
2. **按部件名不行**：2B 的整幅真背景板就叫 `bj_1`（4513×2655，nonBlack=0.992）。
3. **按"纯黑乘数"不行**：见 1，多数黑幕的乘数是 `rgb=1,1,1`。
4. **CG 导出层原有的"像素 alpha 二次构图"也拦不住**：纯黑遮罩是**不透明像素**，
   `alpha>8` 判定把它当成内容。所以 `aluomangshi_2` 自报"覆盖 0.83"看着很健康，
   实际图是一大片黑里嵌一小块舞台。⇒ **alpha 包围盒 ≠ 构图对不对。**

**判据（最终版）**：附件参与取景 ⟺ 其区域纹素 × `slot.data.color` 后，
"落笔（`alpha×a>8`）里 `max(r,g,b)>40` 的占比" ≥ **0.05**。
阈值 0.05 不是拍的：全库面积前 8 的附件里，纯色板实测 nonBlack=0、`colors=1`，
而真内容最低也有 0.59（`yunlong_2` 的 `bj`）/0.731（海棠 `bj_1`），中间是空档。

**开销**：全量逐个附件算要 300~1000ms/part（中位 298ms，`yunlong_2` 1007ms），弹窗里不可接受。
⇒ 只测**贴着当前包围盒某条边**的附件（不贴边的撑不大了框），从外向里剥，≤6 轮，
结果按 `(页, 区域, 乘数)` 缓存。实测打开弹窗无感。

**全库影响面**（`scripts/diag/spine_region_ink_scan.py`，331 part / 325 可测）：
**17 个 part 取景框会缩小**（>1.05 倍），11 个 >1.3 倍，最大 2.79：
海棠 2.79 / 安土 2.67 / 冒险号 2.48 / 阿罗芒什 2.22 / 死亡主宰 2.14 / 埃姆登(+asmr) 2.04 /
北卡 1.98 / 北卡bg 1.53 / 切尔沙茨基 1.39 / 苏维埃同盟 1.30 / 狐(+asmr) 1.26 / 月城II 1.15 / 卡山 1.09 / 莫尔曼西克 1.08。
其余 308 个 `gainInk=1.0`，即包围盒逐字不变。

**边界：剥到空框**。`yunlong_3` 的黑幕是"白贴图×黑乘数"，剥完它之后**没有附件剩下** →
必须退回上一轮的框（代码里 `if(!nb)break;`）。这条不是理论构造，是全库扫出来的唯一一个，
保留旧行为（该皮肤仍是"一大片黑"，有效占满 0.241），不崩不裁。

**验证**：
- 弹窗：28 个皮肤（17 受影响 + 11 对照）逐个开真实弹窗截图，**逐张看图**。
  受影响者画面显著铺满（安土、阿罗芒什、死亡主宰、海棠、北卡、切尔沙茨基、冒险号 7 张细看，无一处裁切）；
  12 个对照的"长轴占满/面积占比"与 §45 那一轮**逐字相同**（`2b_2 0.909 / a2_2 0.910 / molici 0.910 /
  yunlong_2 0.911 / qinli 0.901 / siwanshi 0.842 / fage 0.704 / mojiaduoer 0.539 / z15 0.629 /
  baifeng 0.952 / adaerbote 0.815`）⇒ 零误伤。
- 指标自身补了一个口径：`fill`（非背景棋盘像素）会被纯黑巨幕顶成满分，**必须同时看 `fillInk`**
  （其中非近黑的那部分）。这一轮差点又踩成"指标绿了、图还是一大片黑"。
- CG 导出：先备份 234 张（逐文件 md5 全等，`Output/_OLD_bak/CG_v2_pre_inkframing_20260926/`），
  再按改前参数（`--size 2400 --extra animFrame=1 --redo`）跑 3 个样本：
  `2b_2` **逐字节相同**、安土内容占满 0.372→0.917（画布 2400×2294→2400×1545）、
  阿罗芒什 0.351→0.826。A/B 图 `.diag/cg_ab_inkframing.png`。
- ⚠️ 样本跑第一次就抓到真 bug：`framingBox` 里 `const cur=[]` 却被 `cur=rest` 重新赋值 →
  三个样本全报 `Assignment to constant variable`。**没跑样本就直接全量，这 17 张会被静默跳过。**

**仍未修（第三类，量出来了）**：包围盒被**半透明但确实在画的东西**撑大——
`weikesibao_3` 有效占满 0.387、`hu_2` 0.306、`mojiaduoer_5` 0.539、`z15_2` 0.629、`fage_2` 0.704。
它们的"外扩部件"是稀疏高亮面（如 `s1_053` 只有 6.2% 纹素落笔、亮度 243）或半透明渐变云
（`yun_feisu*` ink=0.109），按"有没有非近黑落笔"判它们算内容。
要再收就得引入第二个阈值"落笔覆盖率 too low 也不算内容"，
但那会裁掉有意画在边缘的光束/雾，**属于审美判断，交人拍板**，不自动做。

### §46 追加：全量重导实际变了 64 张，而扫描只预测到 24 个目录（2026-09-26）

用户拍板后按改前参数（`--size 2400 --extra animFrame=1 --redo`）全量重导：**234/234 完成 0 失败**。
与备份逐文件 md5 比对：**64 张内容变化、170 张逐字节相同**。

**"零误伤闸门"当场报了 42 张意外**：`spine_region_ink_scan.py` 预测会变的是 24 个目录，
而实际变化里有 42 个不在其中（含 `qinli_2`/`fage_2`/`siwanshi_4`/`molici_2`/`z15_2`/`baifeng`
这些我在**弹窗**里验过"指标逐字相同"的皮肤）。第一反应是"判据在 CG 侧误伤了"。

**真正的原因：预测与产物走的不是同一条渲染路径。**
扫描算的是 **setup pose**（与弹窗 `fit()` 同一时刻），而 CG 带 `animFrame=1`，
渲的是**默认动画第 0 帧**——那一帧的附件集合与颜色都和 setup 不同
（这正是 §42 那条"腿要靠动画第 0 帧才挂上"的同一件事）。所以"哪些附件贴边、哪些被剥掉"
两边本来就不一致，`gainInk` 不能用来预测 CG 的变化集。

**判定实际是好是坏，只能量产物**：对 64 张逐张比"改前/改后的非近黑内容占画布长轴比例"——
**变好 19、持平 45、变差 0**。持平那 45 张字节不同是因为**画布被收紧**
（如 `qinli_2` 2400×2125→2400×1342，内容占满不变但透明边没了）。
变好里最意外的三个：`yunlong_3` +0.569、`suweiaitongmeng_4` +0.519、`weikesibao_3` +0.404——
后两个正是 §46 末尾列为"第三类、判据修不动"的，它们在 CG 路径下被修好了，
同样因为第 0 帧的附件集合不同。
目视：64 张缩略拼图 `.diag/cg_new64_sheet.png` + 比例变化最大的 6 张改前/改后对照
`.diag/cg_ab_aspect_sheet.png`，无一处裁切。

⇒ **两条规则**：① **子集式零误伤闸门只在"预测与产物同一渲染路径"时才成立**；
不满足时它会把正常的额外变化报成误伤，此时判据必须换成直接量产物（这里 = 内容占满比例）。
② 反过来，**"弹窗里逐字不变"不能拿来担保 CG 也不变**——两者取景时刻本来就不同。
备份留在 `Output/_OLD_bak/CG_v2_pre_inkframing_20260926/`（234 张，逐文件 md5 已核对全等）。

---

## §47. 「按理说人人都有语音，怎么点出来只有一小部分响」：四层独立根因，其中一层是取词语义错（2026-09-26）

**现象**（用户报）：画廊里只有部分皮肤点击出声，静态立绘和一部分皮肤点了完全没声。

### 根因是四层叠在一起的，缺一个都修不好

1. **接线只有一格**：点模型出声的代码只存在于 Live2D 标签（播放动作组时按组名查 `l2d_voice.json`）。
   静态立绘标签只有缩放/拖拽，Spine 标签只播动画，**两处没有任何语音代码**。
   ⇒ 全库 4491 个皮肤里能出声的 **253 个（5.6%）**，不是数据缺，是功能没做。
2. **旧管线按 Live2D 目录起跑**：271 个 Live2D 目录里 17 个查不到语音包被**整体跳过**（`aidang_2`、`z46_2/3/4`、`qiye_9/10`、`lafei*`…）。
   根因是包号路线单一：只认 `painting` 字段精确匹配，同船兄弟皮肤（`z46_6/7` 在表里）能推出来却没去推。
3. **「语音」标签是坏的**：数据来自 6 月 `export_cue_audio.py`——**每个语音包只取了第 1 条 cue**。
   归到舰船要靠 `generate_audio_doc.py` 里硬编码的 `CV_MAP`（719 条）→ 中文名 → 拼音，一路漏到
   `index.json` 只剩 **268/1008 组船 `voiceCount>0`，740 组显示「语音 0」**；而磁盘实有 **938 个船级语音包**。
4. **取词语义错（最隐蔽，也最伤信任）**：cue 名尾部的 `_N` 是**皮肤序号**（= skin id 末位），
   旧脚本 `VARIANT_SUF=['','_1','_2']` 把它当"同一条台词的随机变体"三条一起导，前端再 `Math.random()` 抽一条。

### `_N` = 皮肤序号的取证（不是猜的）

| 语音包 | 船的皮肤（id 末位即序号） | 包内实际 cue |
|---|---|---|
| cv-10000 | `gin`(0) `gin_2`(1) `gin_3`(2) | `detail` `detail_1` `detail_2` / `home_1` `home_2` |
| cv-10001 | `kin`(0) `kin_2`(1) | `detail` `detail_1`（**没有** `_2`） |
| cv-10501 | `neihuada`(0) `neihuada_2`(1) **`neihuada_g`(9)** | `detail` `detail_1` **`detail_9`** `home_1` `home_9` |
| cv-30301 | `guying`(0) `guying_g`(9) | `detail` `main_1_9` `touch_1_9`（`detail` 无 `_9` → 只能逐类别回退基础档） |

`_9` 不可能来自"第三条随机台词"，只可能是序号 9 的改造皮肤。**后果**：三皮肤船有 2/3 概率播到别的皮肤的台词；
`_g` 改造皮肤永远拿不到自己的档，只能播基础版。

### 由此确定的取词规则

`cue(类别, 本皮肤序号) = 类别_序号 若存在，否则 类别`，且**必须逐类别独立判定**（cv-30301 就是混合档：
`main_1_9` 有、`detail_9` 无）。整档二选一（"有任一 `_9` 就全用 `_9`"）会丢台词。

### 已排除的假设（别再走一遍）

- **「类别名尾部数字 = 皮肤序号」的朴素正则**：`main_1`、`touch_1`、`touch_2` 本身就是类别名（`character_voice.resource_key`）。
  直接 `^(.+?)_(\d+)$` 会把"类别 main_1 的 1 号皮肤 `main_1_2`"切成类别 `main` + 序号 1。
  ⇒ 必须按**最长已知类别前缀**切分，类别表来自 `character_voice.json` + 表未覆盖的实测类别名。
- **「目录名尾缀 `_N` → 序号 N-1」**：对配置表已知行只有 **78% 正确**（`lafei_8` 实际 idx=5、`ladefute_3` 实际 idx=1）。
  ⇒ 序号要么取表里的行（权威），要么按"包内实存序号档 − 同船已被占用的档"分配，不得按名字硬算。
- **`_g`/`_meta`/`_asmr` 是"画法变体"**：不是。`guying_g` 在皮肤表里有自己的行、序号=9，是**独立皮肤**；
  只有 `_hx`（和谐版）/`_n`（无背景版）这类才是同一张皮肤的另一幅画法，剥它们不影响语音。
- **`voice_name` 中文标签是坏的**：不是。JSON 里就是合法 UTF-8（`detail`=查看台词、`touch`=普通触摸），
  先前看到的乱码是**终端输出编码**，不是数据。教训：判"数据坏了"之前先打 codepoint。
- **48 个 cv 号缺包是本地解析 bug**：不是。`files/hashes-cv.csv` 与磁盘 1:1（938/938，0 缺），
  这些包**根本没被下载过**，只能走设备补取。

### 验证（真实可观测状态，不是"结构对了"）

- 静态立绘格点「普通触摸」→ 页面自持的 `Audio` 元素 `paused=false`、`currentTime` 0→4.22s 连续 291 帧，源 `cv-10000/touch_1.ogg`。
- Live2D 格选 `touch_head` 触发 → `play()` resolved，源 `cv-10720/touch_head_1.ogg`（**本皮肤**序号档，旧表此处是两条混抽）。
- 新旧映射对拉（同皮肤同动作组）：`abeikelongbi_3` 12→19 组、`benningdun_2` 13→20 组，**丢组 0**，
  每组由"全船各皮肤台词混列"收敛为"只剩本皮肤那一条"。
- ⚠️ 换数据文件后**必须重验 Live2D 那一格**：前端只读新表，样本表只 5 个皮肤时，Live2D 出声面从 253 掉到 2 ——
  这是"半程部署"型自伤，收尾前若不停线就得先把运行目录刷回旧行为（本轮做法：`git diff` 存补丁 → `git checkout` 回退 → `deploy_gallery.py` 刷平 → `--relink` 补链 → `--check` 4/4 绿）。

**涉及文件**：`scripts/extract_cv_voice.py`（新，按包去重导出 + 生成 `skin_voice.json`）、
`scripts/diag/voice-v2-frontend.patch`（挂起的前端接线）、`scripts/extract_live2d_voice.py`（被取代，`VARIANT_SUF` 即本条语义错）、
`inputs/gamecfg/character_voice.json`（类别 / `resource_key` / `l2d_action` / `spine_action` / 中文标签的唯一权威）、
`inputs/azdata/azdata_ship_skin_template.json`（`painting` → cv=id//10、序号=id%10）。相关：§41、§35/§36、WF-17、WF-21。


---

## §48. 叠脸门控两版判据都不对：该问的是"底图这里画的是不是这张脸"（2026-09-27）

**日期**: 2026-09-27
**现象（用户报）**: 画廊 `moermansike_2`（摩尔曼斯克「皮肤2」）脸上盖着一块硬边不透明灰梯形。

**取证链（每一环都改过一次结论，按顺序记）**
1. 待办列的三条假设里 ②③ 先排除：face 槽矩形 `(542,830,242,146)` 与灰块外接框重合；
   逐层单独落盘核对（`scripts/diag/painting_layer_dump.py`，量「这一层在脸槽里落了多少笔」）：
   底图 `moermansike_2` 在脸槽内落笔 **35332/35332（满）**，`_front` 只有 **1825/35332（5%，且是边缘发丝）**
   ⇒ 那块灰是**底图自己画的**，不是别的部件盖上去 ⇒ 槽位不重合、遮挡顺序两条都排除。
2. 门控读数 `frac_opaque=1.000` / `frac_realart(sat≥30)=0.004` ⇒ **当前判据其实判它"洞"并且叠了脸**，
   叠完画面正常 ⇒ 在盘产物是**过期的**（09-15 渲染，从未进 09-20 那 34 张换入）。
3. 为什么当初没进清单：09-20 那轮扫的是**旧判据**（face 框整框不透明率），`frac_opaque=1.000` 判"已烤好"；
   同日收紧成"不透明**且** sat≥30"之后**只重渲了旧清单里的 35 张，全库 2221 候选从未重扫**
   ⇒ 待办假设 ① 的精确版：**判据演进留下的隐形漏检**，不是扫描漏了个体。
4. 灰块是不是我们光栅化造出来的？把源纹理 `painting/moermansike_2_tex` 原样导出、按 face 槽框裁出来看
   —— **灰梯形在源纹理里本来就有**，游戏运行时靠 face 槽叠真脸 ⇒ 叠脸方向正确（不是遮丑）。

**第二个发现（比原问题更要紧）**
用当前(sat≥30)判据全库重扫，前 200 候选报 **98 个"脸洞"= 49%**，而旧判据全库只有 1.6%。
抽样 24 张逐张目视：**24 张全部是底图已烤好完整脸**（`antu`/`beierfasite_7`/`canglong_g`/`jialimaoxian`/`lieren_alter`…）
⇒ §14 那次收紧把错误方向从"漏叠"换成了"**大面积过叠**"，且从没在"旧清单外"的人群上回归过。
机理：二次元淡色皮肤本身 sat 就低，足迹里又混着深色头发，`sat≥30` 大面积不成立，与"没画脸"无关。

**自造判据里被数据否证掉的两个（别再试）**
- 边缘密度 `frac_edge`：`gezi_2`(真洞) 0.314 vs `antu`(好脸) 0.372 —— 重叠不干净。
  原因：足迹含头发，两类都有边缘；且透明洞被 crop 的 (0,0,0) 填充在边界上**伪造**出边缘。
- 亮度标准差 `std_l`：`moermansike_2`(平涂灰块) 61.1 vs `antu`(好脸) 75.3 —— 同因，被足迹内非脸像素稀释。

**解决方案（判据直接问语义，不再用代理指标）**
```
洞 = 脸谱落笔处不透明占比 frac_opaque < FACE_OPAQUE_MIN(0.5)      # 这里没画
     或 MAD = mean|底图RGB − 脸谱RGB| > FACE_MAD_MAX(30)          # 画了但不是这张脸
```
MAD 比的是同一槽、同一张脸谱、已按 rect resize 且已按 mirrors 翻转之后的两块像素
—— 它就是"脸已烤好"这句话的定义本身，不是它的代理。可比像素 <64 时 MAD 记 `None` 并按洞处理（底图这里几乎没落笔）。

**带标签回归闸门**：`scripts/diag/face_gate_labels_check.py`（退出码即结论）——47 个人工目视裁定过的样本，
新判据 **47/47 全对**（23 洞全召回 / 24 好脸全不叠）；同一批样本上旧 sat 判据把 24 个好脸判成洞。
分离度：好脸侧 MAD 最大 **12.3**（`jialimaoxian`），真洞侧最小 **62.6**（`moermansike_2`），阈值 30 落在空档里。
`leiniya_wjz`（§14 的标杆误叠）MAD=2.2 → 仍不叠；`z43`（§14 目视判过要叠）MAD=2.6 → 底图与脸谱几乎同一张画，
叠与不叠无可见差异，已移出断言集并注明原因。

**教训（可复用）**：**换判据 = 换分类器**，只在"旧清单"上回归等于没回归——旧清单是新判据的**因变量**。
判据演进后必须 ① 全库重扫（对 population 重跑）② 建带标签回归集（**两侧都要有人**），
并把"在标签集上的符合率"当换入前的闸门。同型前例：§14 的度量口径、WF-15 的"预测与产物必须走同一条渲染路径"。

**全库重扫与换入结果（2026-09-27）**：2221 候选重扫 → **46 个洞 / err 0 / 未参与判定 0**（56 分钟）；
其中 **13 个是旧判据完全看不见的「不透明但画的不是这张脸」类**（`moermansike_2`/`baixue_2`/`bisimaiz`/
`boyixi_3`/`fuerban_h`/`gelunbiya_3`/`haiwangxing_2`/`mingniabolisi_3`/`salatuojia_6`/`shanfeng`/`shanfeng_2`/
`yunlong_3` + 全图差异的 `haman_4`）。`scripts/diag/painting_face_rerun.py` 逐张重渲并与在盘比 md5：
**33/46 与在盘逐字节相同**（= 新判据精确复现 09-20 已验收产物，零回退硬证据），13 张有差异。
13 张**逐张目视**（`make_face_cmp.py` 出改前|改后|差异区放大）：全部是"改前没脸/糊成一团、改后正常"，
其中 `haman_4` 改前**整条角色身子都不在**（差异覆盖全图、成品高 65px），属另一类陈旧产物而非叠脸。
换入前逐文件确认 `st_nlink==1`、备份 `Output/_OLD_bak/painting_facefix_20260927/`（13 个，md5 全等）→
覆盖 → 逐张校验新内容 == 临时渲染 → **全目录快照证明只有这 13 个文件 mtime 变了** → 只删这 13 张的
`thumbs/<stem>.webp` 后 `make_thumbs.py` 增量重建（ok=16 / err=0）。
⚠️ 分诊标签的教训：**「旧图该处彩色占比」不能用来判"已有脸"**——`boyixi_3`/`haiwangxing_2`/
`mingniabolisi_3` 彩色占比 0.80~0.98 却全是真洞，那里画的是绿叶/夜空/背景块。
所以 `painting_face_rerun.py` 的分诊已改成**以 MAD 为准**、三类占比只作提示。
由 `haman_4` 引出的更大问题：**「盘上产物过期」不止脸这一类** ⇒ 新增
`scripts/diag/painting_staleness_scan.py` 对全库 4488 张做「当前管线重渲 vs 在盘 md5」普查（只出清单不动产物）。

**涉及文件**: `scripts/compose_paintings_v2.py`（`FACE_OPAQUE_MIN`/`FACE_MAD_MAX`/`FACE_GATE`、`render()` 内叠脸段）、
`scripts/diag/face_gate_probe.py`（单皮肤取证：走真实渲染路径 + 读生产侧门控日志）、
`scripts/diag/face_gate_labels_check.py`（标签闸门）、`scripts/diag/scan_faces.py`（全库重扫，出门控读数 TSV）、
`scripts/diag/painting_face_rerun.py`（重渲 + 与在盘逐像素比对 + 按"旧图透明/白灰块/彩色画"自动分诊）。
相关：§14（被本条取代的那版判据）、§9.3。


---

## §49. 语音缺包「走设备补取」已否证：设备侧同样没有这批包（2026-09-27）

**日期**: 2026-09-27
**前提（上一轮拍板的计划）**: 66 个船级 cv 包在 `files/AssetBundles/cue` 里不存在，
而 `hashes-cv.csv` 与磁盘 938/938 全等 ⇒ 判为"没下载过"，于是安排 `mumu_sync.py diff → sync --apply`
从 MuMu 设备补取，覆盖 234 张今天无解的皮肤。
**实测否证（只读，未下载任何文件）**:
- 设备 `AssetBundles/cue` 共 **4958** 个文件，本地 **4726** 个；设备独有 **232** 个。
- 这 232 个只属于 **cv-970113 一个号**（`cv-970113.b` 及其 `-battle/-gift`）+ 一批 `bgm-*` / `dorm3d_implacable_telephone*`。
- **与那 66 个缺号的交集 = 0**。66 个里 **59 个在设备侧连 `cv-N-*` 前缀文件都没有**；
  剩下 7 个（`10117/20401/20404/30312/30507/30702/…`）只有 `-battle/-gift` 变体、**且本地同样有这些变体**，
  真正缺的是主包 `cv-N.b` —— 两侧都不存在。
- 缺号里 `90017~90056` 是连续段（40 个），形态上就是"配置表已收录、音频尚未随包下发"。
**结论**: 这 66 包在**本地与设备两个源上都不存在**，"走设备补取"不是省事的捷径而是死路；
对应的 234 张皮肤在现有资产下**无解**，只能等游戏下发或走 CDN（**未拍板，暂不做**）。
画廊侧的正确姿势是**显式标"无语音源"**，不是静默留空让人以为漏接线。
**顺带查出一个承重 bug**: `scripts/mumu_sync.py` 的 `_candidate_ports()` 里
`subprocess.run(..., encoding='utf-8', errors='replace', encoding="utf-8", errors="replace", timeout=30)`
—— **`encoding` 关键字重复 → SyntaxError**，该脚本自写下起从未成功运行过（连 `--help` 都起不来）。
这说明**此前没有任何环节编译过全部脚本**：已把 `py -3 -m compileall -q scripts gallery_src`（退出码即判据）
纳入收尾验证。
**复核命令**:
`py -3 scripts/mumu_sync.py diff`（只读对比）；设备侧清单核对见 WF-21 末段。
**涉及文件**: `scripts/mumu_sync.py`（修 SyntaxError）、`scripts/extract_cv_voice.py`（缺包口径）、
`docs/WORKFLOWS.md` WF-21。相关：§47。


---



---

## §50. 验收脚本把 headless Chrome 漏在机器上，把用户机器压到只剩 1.1GB（2026-09-27）

**日期**: 2026-09-27
**现象（用户直接反馈）**: 「你到底跑了多少个后台？怎么这么卡」。
**两个洞（第二个才是主因）**:
1. `subprocess.Popen([CHROME, ...])` 的 `proc.terminate()` **只杀启动器**，下面的
   crashpad / gpu(SwiftShader) / network / 若干 renderer 不打整棵树就继续活着。
2. 多数诊断脚本把 `proc.terminate()` 写在**最后一行**，脚本一抛异常就永远走不到——
   本轮 `interact_verify.py` 与 `l2d_inspector_verify.py` 各撞了一次
   `RuntimeError: Execution context was destroyed`，于是各漏一棵树，**共 16 个 chrome 进程**，
   叠加同时跑的语音全量导出（jobs=3）与立绘全库重扫，空闲内存被压到 1.1GB。
**修法**: 新增 `scripts/diag/chrome_tree.py`（`install(proc)` 注册 atexit 整树 `taskkill /T /F`，
异常退出也会执行；`kill_tree(pid)` 供正常收尾调用），已接进
`interact_verify.py` / `l2d_inspector_verify.py` / `hit_verify.py` / `voice_v2_verify.py`。
其余 24 个起 Chrome 的脚本按同一形状逐步迁移（`spine_*` 那几个早就自己写了 taskkill，只是没成惯例）。
**判据（收尾必查，别只信"脚本跑完了"）**:
`powershell -NoProfile -Command '@((Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "chrome.exe" -and $_.CommandLine -match "headless=new" }).Count)'` 必须为 0。
⚠️ 用 `CommandLine -match` 找残留时，**模式串会匹配到执行查询的 powershell/bash 自己**
（本轮就误判成"还有 4 个残留"，差点去 kill 自己的 shell）——按 `Name -eq "chrome.exe"` 先过滤。
**调度教训（我的失误，不是代码的）**: 把「语音全量导出（多进程解码）」和「立绘全库重扫（单进程但常驻 ~1GB）」
并跑，又把浏览器验收压在扫描上 ⇒ 扫描 ETA 从 43 分钟被拖到 79 分钟，还挤到了用户正在跑的游戏/ALA。
本机只有 15.4GB 内存且常开着游戏与模拟器：**重活串行跑，别把并行当免费**。
**涉及文件**: `scripts/diag/chrome_tree.py`（新）及上述四个验收脚本。相关：WF-16、§48、§49。

---

## §51. 判定区可视化里"贴在屏幕角落、根本点不到"的标签：是标签 clamp，不是数据坏了（2026-09-27）

**日期**: 2026-09-27　**状态**: ✅（前端只改标签可见性；数据与命中链路一律未动）

**现象（用户直接反馈）**: 奇尔沙治皮肤2 开「判定区」后，屏幕右上角黑幕里贴着 `touch_idle5`、`touch_idle7` 两个标签，
那里既没有框也点不到；"其他皮肤也是，有一些判定区都已经跑到皮肤外的黑幕里了"。

**直接根因**（`gallery_src/index.html` 的 `drawAreas`）：标签坐标把 x **无条件夹进视口**：

```js
tx.position.set(Math.max(2, Math.min(gx0, wrap.clientWidth-72)), gy0-15>=2?gy0-15:gy1+3)
```

框本身在 stage 横坐标 3800~4600 像素处（多边形画到画布外，看不见），但标签被这条 clamp 拽到右边缘；
y 方向不夹，所以只有"纵坐标离画布中心最近"的那一两个会落进屏幕 → 就成了角落里的幽灵标签。
且 `TouchIdle4/5` 同高、`6/7` 同高，x 又夹到同一处，**看着 2 个其实是 4 个框叠成一行**。
探针实测：所有幽灵标签的 x 恰为 `clientWidth-72`（868 视口下 = 796）。

### ⚠️ 先记一条我上一轮的错误结论（否则会重犯）

我第一轮判定："这些出画框是 `fix_model3.py` 不做几何校验登记进来的**编辑器遗留停放标记**，
建议在 `geomOf` 里按『框与画布矩形不相交 → return null』过滤掉（一处生效三处同源）"。
**被用户的领域记忆否证**——他记得"有一个垂电线下来，然后可以改皮肤的配置：丝袜、猫耳兔耳猫尾巴兔尾巴、爱心眼"。
于是做了反证实验：

**反证实验**（`scripts/diag/l2d_hit_offcanvas.py --sweep`，走页面自己的 `play()`，逐组播完全部动作组，
每组播放中重新量 26 个 `Touch*` 标记有几个落回画布内）：

| 模型 | 静止态在画布内 | 播某些动作组时 |
|---|---|---|
| `qiershazhi_2`（画布 28×28 单位） | **4 / 26** | `idle1/idle3/idle5/idle6` 带入 `TouchDrag6/9/10`+`TouchIdle9~13`；`main_1~5/mail/mission/wedding` 再带 `TouchIdle1`；`touch_idle2` 时达 **10 个** |
| `yuanchou_3` | 9 / 31 | `touch_drag2/3/4` 带入 `TouchIdle3/6/7/8`+`TouchDrag2`+`TouchIdle38`，同时 Head/Body/Special 出画 |

⇒ **"出画"是换装按钮的停放位，动画一开它随部件进画面**，不是数据坏了。按"不相交就过滤"改 `geomOf`
会把可视化变成随动作闪烁的框集，且没有任何命中收益（出画的框本来就包不住可见的点击点）。方案作废。

**换装开关在数据里长什么样**（`yuanchou_3` 实测）：moc3 里有 **Parameter** `TouchSiwa`(丝袜)、
`TouchPijian/2/3`(皮鞭)、`TouchFa`(发)、`Touch_zi`(字)，以及 `Paramaixin`(爱心)、`ParamMAOBI`、`Paramtushe*`；
各 clip 用**定值曲线**锁住它们（例：`touch_idle31` → `Paramaixin=1.6 / ParamMAOBI=-1` 即爱心眼；
`touch_drag6` → `TouchPijian2=1`）。所以**"换装 = 播某条把开关参数锁成 1 的动作"**，
而 `HitAreas[].Name` 本身就是那条组名 → 与 §27 的 A3 随机命中天然兼容，不需要新机制。
（注意 `TouchSiwa` 这类只作为 Parameter 存在，`core.getDrawableIds()` 里没有同名 drawable。）

**修法**（只此一处）：`drawAreas` 里把 `toStage/ptsOf/rectOf/inView` 抽成共用小函数，
**多边形仍按 `__L2_HITUSE()` 全画，标签只在框与视口相交时画**（贴边可见的框保留原 clamp，那是它需要的）。
另暴露 `window.__L2_HITSHOW()` = 「此刻画得出标签」的清单，与 `drawAreas` 同一组判据 ——
`l2d_inspector_verify.py` 的标签基准由 USE 换成 SHOW（多边形那条仍对齐 USE），仍是"探针不复算几何"。

**判据**: 场景图里可见标签数 == `__L2_HITSHOW()` 数 == 与视口相交的框数；
且**全部框都在画面内的模型标签数一字不变**（对照组，防误杀）。
实测：`qiershazhi_2` 16→3、`wuzang_4` 78→4、`antu_2` 57→4、`chuyue_2` 8→**8**、`lafeiii_3` 10→**10**；
`hit_verify` 抽样 6 模型 201 个部位 **WIRING 0 / OUTSIDE 0**（HIT 104 + INGROUP 91 + NOTCLICKABLE 6，随机性抽查 3/3 合格）。
目视：`.diag/l2d_shots_visual/{qiershazhi_2,chuyue_2}.png`（前者角落标签消失、只剩身上 3 个；后者 8 个标签含
腿上的 `touch_drag1`、撑地的 `touch_drag3` 全部保留）。

**踩坑（三条）**:
1. **JS 块注释里不能写 `TouchIdle*/TouchDrag*`** —— 那个 `*/` 会**提前闭合注释**，把后半句当代码解析。
   本条初稿就踩了，改成"TouchIdle 与 TouchDrag 系列"。
2. **Edit 类原地编辑同样会断硬链**（实测）。AGENTS.md 原话是"不要整文件写回 / 原子保存"，
   但本轮用 Edit 改 `gallery_src/index.html` 之后 `--check` 就报了"既断链又漂移"。
   ⇒ 收尾**一律以 `deploy_gallery.py --check` 为准**，红了按提示"默认模式刷平 → 提交 → `--relink`"。
   （`--relink` 会跳过"正本有未提交改动"的文件，所以必须先提交再补链。）
3. **`Execution context was destroyed` 这次不是两个 Chrome 抢 CDP**（§50 记的那一类），
   而是**探针在页面还在导航时就 evaluate**。同一张 tab 的上下文在导航结束后会重建，
   `document.readyState==='complete'` + 最多 6 次重试即可（已加进 `l2d_coord_forensics.py` / `interact_verify.py`，
   同日复测判定区时 `l2d_inspector_verify.py` 又被打红一次——**三个脚本都装了才算修完**，
   拿不到稳定上下文一律显式 `exit 2` 并报"探针故障，非产品故障"）。
   另：`page_sanity_check.py` 此前完全不清理 Chrome（连 `proc` 都没接住），本轮漏了 8 个进程，已补 `chrome_tree.install`。

**残留待办（本轮明确不修，另起一轮）**: 有一批标记**静止态就在画面内、不透明度 1、却压根没登记**，
因为 `fix_model3.py` 硬性要求存在同名动作组：`yuanchou_3` 的 `TouchDrag20~23`、
`qiershazhi_2` 的 `TouchDrag7`（6.4×6.2 的大框压在角色身上）、`suweiaitongmeng_2` 的 5 个 `TouchDrag*`。
这些组（`touch_drag20` 等）确实不存在，游戏侧究竟把它们绑到哪条动作没有权威依据，不能猜着登记。

**涉及文件**: `gallery_src/index.html`（`drawAreas` + `__L2_HITSHOW`）、`scripts/diag/l2d_inspector_verify.py`（标签基准）、
`scripts/diag/l2d_hit_offcanvas.py`（**新，入库**：① 幽灵标签/出画对账 ② `--sweep` 逐动作组量在画布数）、
`scripts/diag/l2d_shot_models.py`（加 `L2D_AREAS=1` 开判定区后再截）、`scripts/diag/l2d_coord_forensics.py`、
`scripts/diag/interact_verify.py`（②③ 两条重试）、`scripts/diag/page_sanity_check.py`（补 chrome_tree）。
更正 §21 与技能 `live2d-web-runtime-integration` §3.8 里"编辑器遗留的停放标记"那句。相关：§21、§27、WF-16。


---

## §52. 「盘上产物过期」的第二类：后续修复从没落到它们身上（2026-09-27）

**日期**: 2026-09-27
**起因**: §48 查 moermansike_2 时发现该文件 mtime 还是 09-15、从没进过任何一次定向换入。
于是对全库 4488 张做「当前管线重渲 vs 在盘 md5」普查（`scripts/diag/painting_staleness_scan.py`，
只出清单不动产物、逐条落盘可续跑，实测 1.9s/张 ≈ 94 分钟）。
**结果**: **9 张与当前管线不一致，0 张渲染失败**；且**没有一张是叠脸引起的**（门控对 9 张全判"不叠"）。
**因果判定法（这一步才是关键，别停在"发现不一致"）**：把历代脚本从 git 里取出来分别重渲，
看在盘文件能被**哪一个提交**逐字节复现：
| 在盘文件能被复现的提交 | 张数 | 含义 |
|---|---|---|
| `b6683c8`(09-15) 与 `52782a7`(09-18 嵌套容器) 都复现、但 `95321ef`(09-19 mesh 越框) 不复现 | 7 | **漏掉了 09-19 的 mesh 越框修复** |
| `b6683c8` 复现、`52782a7` 不复现 | 2（`moli_g`/`moli_g_n`） | **漏掉了 09-18 的嵌套容器修复** |
| 三个都不复现 | 1（`z43`） | 09-20 换入过叠脸，新判据不再叠它（MAD 2.6，两版视觉近乎相同） |
**⇒ 结论**：当年那两批"受影响子集扫描"（09-18 换入 85 张 / 09-19 换入 55 张）**各自漏了 2 张和 7 张**。
失效方向和 §48 同一条：**定向重跑的"受影响集合"是预测量，预测漏了就永久静默**。
只有"全库逐字节比对当前产物 vs 磁盘"才能兜住，这个普查应当并入每次系统性修复的收尾。
**差异长什么样（先量后看，别一上来逐张盯图）**：按「视觉上看不看得见」分型
（差异像素里 `max(α_旧,α_新) ≥ 40` 才算可见）——
`anninvwang`/`dengken` 可见差异 3~4% 但**最大色差只有 5~6/255**（重采样舍入级，肉眼不可能看见）；
`moli_g` 系列与 `u2501` 系列是半透明光效/软阴影层的真实变化（色差 156~255），放大 1:1 看是
金属渐变与底部粉色辉光的浓淡，两版都完整、无缺失。
⚠️ 第一版分型把 4 张全报成 0.0%——因为 loss/gain/仅颜色/半透明四个桶**都不收"低 alpha 像素的颜色差异"**。
教训：**指标一片 0 先怀疑量尺**，不要当成"没差异"（同 §48 的代理指标陷阱）。
**处置（2026-09-27 用户拍板"全换"）**：9 张全部按当前管线换入。
换入走新工具 `scripts/diag/painting_swap_in.py`，四道硬检查全绿：
① 目标 `st_nlink==1`（硬链目标绝不覆盖）；② 备份与原文件 md5 全等
（`Output/_OLD_bak/painting_stalefix_20260927/`，9 份）；③ 换入后与临时渲染 md5 全等；
④ **全目录快照**：mtime/nlink 变化正好 9 个、清单外被动的 0 个。
缩略图只删这 9 张的 `<stem>.webp` 后 `make_thumbs.py` 增量重建（ok=9 / err=0）。
**换入后复测 9/9 与当前管线逐字节相同 ⇒ 全库 4488 张"盘上 == 当前管线输出"这条不变式已恢复**，
这条普查从此可以当每次系统性修复的回归闸门用。
**涉及文件**: `scripts/diag/painting_staleness_scan.py`（普查）、`scripts/diag/painting_swap_in.py`（换入四道检查）、
`.diag/stale_20260927.tsv`（明细）、`.diag/stale_20260927.diff.txt`（9 张清单）。相关：§48、§9.3、WF-15。


---

## §53. 语音"265 张因快照滞后无解"是误判：真因是查表大小写敏感（2026-09-27）

**日期**: 2026-09-27
**原口径（§47 / §6.10 待办）**: 499 个无解皮肤 = 234（缺包，两侧都无源）+ 265（本地 azdata 快照查不到 `painting` 行）。
**先做证伪检查**：本地 sharecfg 已解出的 `ship_skin_template`（`.diag/sharecfg_re/cfg_json_scalar/`，
2865 行、每行都带 `painting`）与 azdata 快照的 painting 集合**几乎同一份**（2692 vs 2691，只差 2 个），
"只有 sharecfg 有、azdata 缺、且正好是无解皮肤"的交集 = **0 个**
⇒ **"换更新的配置表就能救"这条路根本不成立**，设备侧 `ship_skin_template` 虽比本地新 7KB 也不是原因。
**真因（逐张算卡点分布算出来的）**：499 里
- **224 张**：包号能推出，但 `cue/cv-<n>.b` 确实不在盘上（= §49 那批两侧都无源）；
- **150 张**：**语音包就在盘上，是本脚本查不到**——皮肤表里 `painting` 写成 `2B`/`A2`/`HDN101`（大写），
  而磁盘目录名是小写，`load_skin_rows()` 按原样建键、`resolve()` 按原样查 ⇒ 永不命中。
  修法 = 表键与候选**一律小写归一**；实测新定位 **145 张**（`2b`/`a2` 全家等）。
- **16 张**：`voice_actor` 为 0/-1（该角色本就没有 CV）；
- **109 张**：后缀没被剥（`_memory`/`_rank`/`_heihua`/`_ex`/`_wjz`/`_idolns`…）。
  ⚠️ **这一类故意没修**：它们可能是**另一个发声实体**（回忆剧情、排行榜立绘、黑化形态），
  盲剥后缀会把别人的台词派给它 —— 按 §47 的定性，那是"不报错的语义错"，比沉默更糟。
  ✅ **用户决议（2026-09-27）：这一类不再追**，画廊侧维持"🔇 该皮肤无语音"的显式留空口径。
  **别再把它当待办重新提出**。剩余 354 无解 = 224 两侧都无源（§49）+ 84 已决定不做 + 16 无 CV + 30 其它。
**修后口径**: 可定位 3995 → **4140**，无解 499 → **354**；新增要解的包只有 46 个。
零回退闸门通过：真丢组 0 / 磁盘缺失 0 / <2KB 占位 0（41193 个音频 / 2424.5MB）；
映射表逐字段比对 **消失 0 / 新增 145 / 变化 79**，而那 79 处全是 `sibling-tier → row`
（包号与序号都没变，只是来源从"猜同船"升级成"表里直接命中"）。
**顺带加的能力**: `--skip-done`（磁盘上已解过的包直接复用 `cv-<n>/<cue>.ogg`，文件名即 cue 名），
把"改定位器 → 重建映射"的成本从 75 分钟降到几分钟；用它之后仍必须过一遍"磁盘缺失/占位 = 0"闸门，
防止半截包被当成完整包。
**又犯一次的老坑**：`voice_v2_verify.py` 点完只等 1.5s 读一次 `currentTime`，
把 `cv-1170002/touch_1.ogg`（ffprobe 实测 3.47s 的正常文件）读成 `cur=0` 报 ❌。
先量产品再定罪：文件没问题 ⇒ 是**固定等待**型假失败（WF-16 已记过一次），改成轮询到真的走秒。
**涉及文件**: `scripts/extract_cv_voice.py`（小写归一 + `--skip-done`）、`scripts/diag/voice_v2_verify.py`（轮询）、
`.diag/_cv_miss_after.json`（修后 354 无解清单）。相关：§47、§49、WF-21。

---

## §54. 「点立绘还是没台词弹出来」= 三层原因叠在一起，其中两层各自都有假绿灯（2026-09-27）

**日期**: 2026-09-27　**状态**: ✅ 三层全部落地并实播验收（索引换入待用户放行）

**症状**：语音 v2（§47/§49/§53）已经"点得出声"，用户仍报"没有台词弹出来"。

**三层原因，逐层都要有对照，否则每层都能给自己造一个绿灯**：

1. **正文从来没进过前端**（主因）。`skin_voice.json` 的 `lines[].label` 是**类别名**
   （"普通触摸""查看详情"），不是角色说的话；台词中文正文在 `ship_skin_words`（2601 行 / 2569 行有词）。
   ⇒ 全库任何皮肤都不会弹正文，这不是偶发。
   **钥匙**：`皮肤行 id = cv*10 + idx`（`cv`/`idx` 是语音 v2 已经算好的两字段）正是这张表的主键 ⇒
   **音频与正文取自同一行**，天然同皮肤同档位，不需要再匹配一次。
   **类别名 → 正文字段**查 `character_voice` 的 `key ↔ resource_key ↔ l2d_action`（16 条别名，表驱动不猜）；
   `main1..7` 表里常缺，游戏把三条合并在 `main` 字段用 `|` 分隔 ⇒ 按序号拆。
2. **索引口径陈旧**。`index.json` 的 `voiceCount`/`voices` 还是 v1 那条
   「社区 CV_MAP(719 条) → 中文名 → 拼音」链算的 ⇒ 1008 组船里 **740 组显示"语音 0"、语音标签直接置灰**，
   而其中 **590 组在 `skin_voice.json` 里真有 20~27 条**。角标 🔊N 与"含语音"筛选同源同错。
3. **353 张真无源**（224 两侧无包 + 84 后缀待裁定 + 16 无 CV + 30 其它，见 §49/§53）⇒ 只能显式标 🔇。

**四条踩坑（两条是判据自身的假绿灯）**：
- **闸门把"允许变化的字段"从比较里整个剔掉 ⇒ 它最关心的那条判据永远不会触发**。
  首版 `gallery_index_diff_check.py` 用 `scalars(d, skip=allow|...)`，`voiceCount` 进了 skip，
  于是"归零"分支不可达，输出 PASS。通用形状：**白名单 = 期望变化，不是不比较**。
- **"归零"有两种，别用船名例外名单区分**。旧口径 `voiceCount` 归零既可能是丢了本船语音（回退），
  也可能是旧语音本来就属于别的船（修正）。判据用游戏自己的表：
  旧文件里的包号 `cv-<N>` 若在该船任何皮肤的游戏表行（`painting → id//10`）里**一个都不出现** ⇒ 修正。
  实测：`柯蕾` 旧 3 条来自 `cv-20705`（= 可畏），归零是修正；
  `拉菲` 的 `cv-10117-gift` 包号能对上 ⇒ 归零是回退，于是给它保留了 `voiceExtra`（见下）。
- **换行符让台账校验长期报假红灯**。`42/45_publish_*.py` 用文本模式写盘，Windows 下 `\n`→`\r\n`，
  而台账里的 `bytes`/`sha256` 是 LF 版本算的 ⇒ 只要产物带换行，`check_inputs.py` 必报 DRIFT
  （`npc_painting_name.json` 4923B vs 台账 4670B 就是这么来的，不是数据漂移）。改成二进制写。
- **`flex:1` 在列向 flex 容器里把 `<audio>` 压成 0 高**（实测 24 行全 `h=0`）：
  `flex:1` = `flex-basis:0%`，容器高度又由内容决定 ⇒ 没有剩余空间可长。改 `flex:none` + 固定高。
  **这条是"行数/正文数都对得上"的判据放过去的** ⇒ 语音页的本职是"能播"，判据必须量 `audio` 的
  存在**与可见高度**，不能只数行。

**验收（`scripts/diag/talk_verify.py`，全部走真实 UI 路径）**：三格各点一次 + 直接点立绘 +
开关矩阵两条反向证据 + 阴性对照 + 语音页逐行比对 + 持久化，全 ✅。
- **阴性对照必须点到那个槽位**：首版一律点第一个按钮，于是"摸头无正文"这条实际点的是普通触摸，
  报了个假失败。挑样本时把 `slot` 一起带下去。
- **探针不许依赖上一轮的 localStorage**：无头 Chrome 被 kill 时不保证落盘，
  下一轮开局 `OPT={voice:false,lines:false}` ⇒ 三格全"没出声"。每轮先把开关按回基线。
- **持久化要设成非常规组合再重开**（voice=on/lines=off）：全 true 时"读默认值"也能过。

**涉及文件**: `scripts/build_skin_words.py`（新）、`scripts/diag/gallery_index_diff_check.py`（新）、
`scripts/diag/talk_verify.py`（新）、`scripts/build_gallery_index.py`（语音口径换源 + `voiceExtra`）、
`gallery_src/index.html`（字幕条 / 语音页 / 两个全局开关）、`tools/sharecfg_re/42_publish_gamecfg.py`
（发布 `ship_skin_words` + 二进制写）、`Output/gallery_v2/skin_words.json`、`inputs/gamecfg/`。
相关：§47、§49、§53、WF-21、WF-22。

---

## §55. 头部整片发黑 / 身上贴着 "NOT ABLE TO DISPLAY"：合成从没读过图层的激活位（2026-09-27）

**症状**：用户一次报 12 张卡——水星纪念·META、敦刻尔克「除了脸，头部其他地方是黑的」；
宁海、平海、飞龙、纽卡斯尔、让·巴尔「整个头都是黑的」。
用户当时的猜测是"你用到了剧情立绘"——**这条是错的**，但方向对（确实是"多画了一层不该画的东西"）。

**先排除"缺层"**：画廊把透明铺成棋盘格，截图里那些黑是**不透明的真像素**，
不是层没画。所以问题在"多"不在"少"。

**根因**：`parse_painting` 只认 MonoBehaviour 的 `m_Sprite` 非空，**从不读 `GameObject.m_IsActive`**。
游戏里关着的层，我们一律画上去。

取证链（三步，每步都有阴性对照）：
1. `scripts/diag/painting_layer_dump.py ninghai` 逐层落盘 → 最后一层 `shadow`
   （画布 260,1,436×317，不透明处 mean RGB=(68,57,63)）正压在头上；
2. 该节点 `GameObject.m_IsActive = False`（同包 `face` 节点也是 False，但那是另一回事，见踩坑 1）；
3. 全库只读扫描 `scripts/diag/painting_inactive_scan.py` → **4488 张里 125 张 / 150 个部件**命中，
   用户点名的 7 艘全在里面，对照组（tianjinfeng_2 / moermansike_2 / antu / 2b）一个都没有。

**三类被多画的层**：

| 层名 | 部件数 | 内容（实测） | 画上去的后果 |
|---|---|---|---|
| `shadow` | 26 | 纯黑剪影，mean RGB=(0,0,0)，不透明率 4~7% | 头部/上半身发黑 |
| `shop_hx` / `*_shophx` / `*_buildhx` | 60+ | **"NOT ABLE TO DISPLAY" 遮挡条** | 身上贴白条/黄条 |
| `chicheng_alter_rw1..4` / `frame_0..3` | 24 | 同一角色的备用画法 / 4 个相框 | 赤城·改四个身子叠在一起 |

**旁证（这个位是游戏的真开关，不是我们的启发式）**：`_n`（无背景版）皮肤的 `bj` 背景节点
恒为 `m_IsActive=False` —— 与用户 2026-09-20 纠正的「`_n` 就是不显示背景」完全对上。

**三条踩坑**：

1. **`face` 槽必须豁免**。face 节点在 prefab 里恒为关闭，游戏运行时才激活来显示表情差分——
   它正是 §48 叠层逻辑的输入。首版重渲工具没豁免，把 `gezi_2_hx` 的 face 层删了。
   豁免表 `FACE_SLOT_EXEMPT` 放在 compose 模块里，**扫描脚本只读 `parse_painting` 写进部件的
   `active` 字段、不另算一遍判据**——另算会让"预测清单"和"实际会变的图"不同源（§46 那条教训）。
2. **「全层都是关闭态」不能一律过滤**。`qiye_4` / `kelifulan_4` 整张只有一个部件且它是关的；
   `qiye_dark_memory` / `unknown2_memory` 的 `frame_0..3` 四层全关（游戏按剧情逐层激活）。
   一律过滤会把整张画**清空**——典型的不报错的静默失败。规则：过滤后一层不剩 ⇒ 原样保留 +
   记进 `INACTIVE_ALL` 交人工，绝不产出空文件。
3. **一批 shophx 早就被 `is_lighting` 挡着 ⇒ "命中 125" ≠ "要换 125"**。纯白 ≥80% 的遮挡条
   本来就被"加算光效层"判据跳过，所以 125 张里只有 **48 张画面真的会变，73 张逐字节不变**。
   反过来，**带黑字 logo 的遮挡条**（`z15_2` / `shenxue_4` / `u2501_2` / `gezi_2_hx`）
   白色占比不足 80%，正好漏过 `is_lighting` ⇒ 正式产物上现在能看到两条斜贴的大黄条。
   教训：一个"看起来通用"的启发式过滤器（近纯白=光效）会**掩盖**同一批数据上的另一个真缺陷。

**`_hx` 语义确认**（防"去掉遮挡条 = 泄了和谐内容"这条担心）：和谐处理本来就烤在 `_hx` 的底图里
——`gezi_2` vs `gezi_2_hx` 有 **82.4%** 像素不同（`dingan_3` 0.26% / `kansasi_2` 2.6% /
`jinshi_2` 1.3%）。那条 banner 只是运行时占位，去掉不影响和谐语义。

**验证**：
- 零回退对照 12 张（`2b antu hailunna_4 xili_alter kewei_6 aersasi_3 chicheng_4 adiliao_2
  i168 i168_2 tianjinfeng_2 moermansike_2`）在过滤开启下逐字节 md5 全等；
- 125 张定向重渲 → **48 变 / 73 逐字节相同 / 4 全层关闭跳过 / 0 err**；
- 6 页「改前|改后」对照总表逐页目视，全是变好（海天、让·巴尔、伊利沙伯、平海3、z15_2 尤其明显）；
- **落码后**再把 125 张重渲一遍，与"已验证的那批"逐字节比对 ⇒ 证落码路径 == 被批准的路径。

**涉及文件**: `scripts/compose_paintings_v2.py`（`parse_painting` 记 `active` + `compose` 过滤 +
`INACTIVE_SKIPPED`/`INACTIVE_ALL` 两个审计字典）、`scripts/diag/painting_inactive_scan.py`（新）、
`scripts/diag/painting_inactive_rerun.py`（新）。相关：§48、§46、§14、WF-15。

---

## §56. 敦刻尔克被标成「皇家·驱逐」：配置表里的脏行钻了「组内取最小 id」的空子（2026-09-27）

**症状**：画廊卡片 `dunkeerke` 显示 阵营=皇家、舰种=驱逐、英文名 HMS Vampire；
而同一家的 `dunkeerke_alter`（META）显示的是正确的 维希教廷·战巡。用户只报了舰种。

**根因**（两层叠在一起）：`ship_data_statistics` 里有一行 **id=900106**，
`name` 写着「敦刻尔克」，但 `english_name=MNF Dunkerque` 位上填的是 **HMS Vampire**、
`nationality=2`(皇家)、`type=1`(驱逐)、`skin_id=904011`。
- `904011` 是敦刻尔克的**皮肤2**（不是基皮肤 904010），所以这行被归进了组 90401；
- 而 `build_ship_meta.stats_by_group` 用「组内取 `min(stats.id)`」选行，900106 < 904011 ⇒ 脏行胜出。
正确的 4 行是 904011~904014（`MNF Dunkerque` / nat 9 维希教廷 / type 4 战巡），`skin_id` 都指向基皮肤 904010。

**修法（改规则，不写例外名单）**：选行时**先要求该行的 `skin_id` 正是组内基皮肤**（id 最小的皮肤行），
再在候选里取最小 id。全库 **970 组里只有 1 组改判**，就是敦刻尔克——影响 3 张卡。

**闸门配套**：`ship_meta_authority_diff.py` 原来要求"受保护档（painting/suffix）字段改动必须为 0"，
这条会把正确的修正也拦成红。加的是**方向性判据** `base_fix` 而不是白名单：
> 只有「从 `skin_id ≠ 基皮肤` 的行 换成 `skin_id == 基皮肤` 的行」才放行，且新行的 `name` 必须等于成品 `cn`。
反向改动（从基皮肤行换走）仍然是红。这样任何组都能套这条规则，敦刻尔克不是特例。

**顺带**：给 `build_ship_meta.py` 补了 `--out`（写向可走 argv），此前只有硬编码的 `Output/`，
比对时只能覆写正式产物——那是 §25 那次覆写事故的同一种形状。

**涉及文件**: `scripts/build_ship_meta.py`、`scripts/diag/ship_meta_authority_diff.py`、
`Output/ship_meta.json`、`Output/gallery_v2/index.{json,js}`。相关：§39、WF-15。

---

## §58. Spine 的 parts 列表是按目录 glob 猜的：15 个和谐版 CG 与本体逐像素完全相同（2026-09-27，**未修**）

**发现路径**：用户报「天津风皮肤2 动态有问题（躯干/狐尾不显示）」。查这条时顺带查出下面这个更大、
且可量化的缺陷。

**根因**：`build_gallery_index.py:187` 用
`parts = sorted(glob('Output/Spine_v2/<folder>/*.skel'))` 决定"这个 Spine 立绘由哪几层合成"。
但**同一个目录里除了分层，还躺着 `_hx`（和谐版）等变体的 skel**——它们不是层，是**另一张画**。
于是 viewer 与 `cg_export.html`（共用同一份 parts）把本体与和谐版**叠在一起画**。

**权威答案在 prefab 里**：`AssetBundles/spinepainting/<name>` 是个 UI 容器，
每个 `SkeletonGraphic` 组件对应一个真实图层节点（实测 14 个 RectTransform + 5 个 SkeletonGraphic
+ 6 个 Canvas 这类构成）。逐皮肤比对：

| glob 出来的 parts | prefab 里真正挂着的 SkeletonGraphic |
|---|---|
| `aersasi` → `[aersasi, aersasi_hx]` | `aersasi` → `[aersasi]`；`aersasi_hx` → `[aersasi_hx]` |
| `huajia_2` → `[2B, 2M, 2T, 2T_hx]` | `huajia_2` → `[2B, 2M, 2T]`；`huajia_2_hx` → `[2B, 2M, **2T_hx**]` |
| `buleisite` → `[B, T, T_hx]` | `buleisite` → `[B, T]`；`buleisite_hx` → `[B, T]` |

⇒ **`_hx` 是"替换某一层"，不是"多加一层"**。glob 把两种语义都画了。

**可量化的后果（零人工判断的硬指标）**：全库 234 个 Spine 目录里 **30 个**的 parts 含
「变体后缀且基名也在列表里」；`Output/CG_v2/` 里 **15 对**本体/`_hx` 的导出图
**逐像素完全相同**（`aersasi / bawu_2 / buleisite / dahuangfengii_2 / digaiteluyin_2 /
feiteliedadi / huajia_2 / kuangsan_2 / weizhang_2 / wuzang / xili_g / yanusi_4 /
yuanchou / yuanchou_2 / zhaohe_4`）。和谐版卡片显示的是未和谐的合成图。

**判据（怎么区分"真分层"与"误叠变体"）**：健康的多 part 皮肤，各 part 的**槽位名互不相交**——
对照组 `bailong` / `aimudeng_4` 重名率 0%、`lafeier` 3.4%；而被误叠的
`yuanchou` 48.4%、`weizhang_2` 45.2%、`huajia_2` 44.6%、`wuzang` 30.4%。
`wuzang` 的 8 个"层"里有一个是 `wuzang3_hx`。

**天津风皮肤2 本身另案**：它的 prefab 确实列了 5 个 SkeletonGraphic
（`tianjinfeng_2 / 2B / 2B2 / 2M / 2T`），且**全部单位变换**（anchoredPosition 0,0 / scale 1 /
四元数无旋转）⇒ 游戏是把 5 层画在同一原点。所以它**不属于**上面这个 bug。
但它 5 个 part 的槽位名重名率 17.5%，且 `2B` 的 44 个槽是 `2T` 的 390 个槽的**真子集**，
`data.width×height` 分别是 `0×0 / 0×0 / 5063×5501 / 927×720 / 7087×3449`
（对照 `bailong` 是 `2940×2179 / 2691×1458 / 1837×1647`）⇒ 结构本身异常，尚未定性。
**两条已否证**：不是换肤（5 个 part 都只有 `default` skin，`gain=0`）、不是缺贴图
（atlas 页与 png 一一对应、viewer 报 5 层零失败）。

**修法（待放行，未开工）**：把 parts 的来源从"目录 glob"换成"读 `spinepainting/<name>` prefab 的
SkeletonGraphic 列表 + 各自 RectTransform"，与静态立绘第 9.1 节"部件位置全由 prefab 写死"同一条路子。
连带要重导 `CG_v2` 里受影响的 30 张。

**修法（待放行，未开工）**：把 parts 的来源从"目录 glob"换成"读 `spinepainting/<name>` prefab 的
SkeletonGraphic 列表 + 各自 RectTransform"，与静态立绘第 9.1 节"部件位置全由 prefab 写死"同一条路子。
连带要重导 `CG_v2` 里受影响的 30 张。

---

### §58.1 全库比对结果（2026-09-27 同日续，工具 `scripts/diag/spine_parts_prefab_diff.py`）

把上面那条从"8 个样本"升级成"234 个目录全量"，并顺带量出**另外两类画廊从没读过的 prefab 字段**。

| 指标 | 数值 | 含义 |
|---|---|---|
| 多画（glob 有、prefab 没挂） | **30 目录** | 就是上面那个 bug，全部是 `_hx` 变体被当成分层 |
| 少画（prefab 挂了、glob 没有） | **0** | ⇒ glob 是**纯过包含**，修法=过滤到 prefab 列表，**不会丢内容** |
| prefab 指到的层在导出目录里找不到 | **0** | 解析链（`skeletonDataAsset` → `<层名>_SkeletonData` → 剥后缀）全库零失败 |
| 含非单位变换（缩放/位移）的目录 | **9** | 画廊把所有层画在同一原点 ⇒ 这些层被画成错误大小 |
| 起始动画不是 `normal` 的目录 | **3** | 弹窗硬编码优先播 `normal` |
| 层数分布 | 1 层 191 / 2 层 29 / 3 层 11 / 5 层 1 / 7 层 2 | 绝大多数是单层，不受影响 |

**类二：层缩放/位移被忽略**——⚠️ **原始数字 9 是虚高的，必须再筛一层**：
统一缩放/统一位移作用在**整个画面**上会被取景归一化（`fit()` 按内容包围盒算相机）吃掉，**看不出差别**；
只有**同目录各层之间不一致**才真的改变画面。按这条重算：

| | 数量 | 名单 |
|---|---|---|
| 各层缩放不一致（**真缺陷**） | **5** | `duyisibao_2` `guandao` `moermansike_3` `qiershazhi_3` `xinzexi_4`（都是 `B` 层 2.0~2.5×、`T` 层 1.0×） |
| 各层位移不一致 | 2 | `duyisibao_2`(差 2,5) `guandao`(差 0.4,2.6)——UI 像素级，在 ~2000px 立绘上**可忽略** |
| 单层目录但缩放≠1（无可见影响） | 1 | `banerwei_2` 0.3× |
| 单层目录但位移≠0（无可见影响） | 2 | `huben_2`(-207,66) `luyisiweier_2`(-15,-137) |

⇒ **类二真正的范围是 5 个目录，不是 9 个。**
⚠️ 缩放可直接用（SkeletonGraphic 生成的 mesh 受节点 localScale 支配），但**位移不能照抄**——
`anchoredPosition` 是 UI 像素，要先经 anchors/pivot/sizeDelta 换算到骨架单位，
即静态立绘 §9.1 那套统一 UI 数学。

**类三：每层该播的动画不一样**：`buleisite`/`buleisite_hx` 的 prefab 写 `idle`（画廊播 `normal`）；
`pulimaosi` **两层各有各的**（`idle2` + `normal`）。`initialSkinName` 也一并可读
（`yuekechengii` 的节点名是 `yukechengIIT/M/B`——游戏自己拼错了个字母，
按 `skeletonDataAsset` 解析不受影响，按节点名匹配就会漏）。

**天津风皮肤2 明确排除在本节三条之外**：prefab 权威列表 = glob 列表（5 层完全一致）、
全单位变换、起始动画都是 `normal` ⇒ 它不是"层数错/位置错/动画错"。
它的异常在骨架内部：`2B` 的 44 槽是 `2T` 的 390 槽的真子集、槽位重名率 17.5%
（健康对照 `bailong`/`aimudeng_4` 为 0%）。下一步只剩"逐 part 单独渲染看哪层没落笔"。

**涉及文件**: `scripts/diag/spine_parts_prefab_diff.py`（新，只读比对）、
`scripts/build_gallery_index.py`、`scripts/extract_spine_v2.py`、`gallery_src/index.html`、
`gallery_src/cg_export.html`、`Output/CG_v2/`（后五项**待改**）。相关：§42、§45、§46、§9.1、WF-14。

---

## §57. 「354 张无解语音」按可救性拆开：两条路否证、一条是产品口径缺口（2026-09-27）

**日期**: 2026-09-27　**状态**: ✅ 分解与裁定完成；补口子的实现口径待用户拍板

**为什么要再查**：§53 留下的 354 只有一句「只能显式标 🔇」，看不出哪些是「等游戏下发」、
哪些是「剥个后缀就有」、哪些是「正文其实在手只是没声音」。三者的下一步动作完全不同，
混在一个数字里没法拍板，也就会被当成"待办"反复重提。

**工具**：`scripts/diag/voice_gap_audit.py`（只读；**复用 `extract_cv_voice.resolve()` 同一套解析器**，
判据不允许在审计工具里另写一份，否则审的是另一个东西）。

**分解结果（354 张，逐类给"能不能救"）**

| 类别 | 张数 | 其中正文可得 | 判定 |
|---|---|---|---|
| 缺主包、盘上连变体包都没有（43 个包号） | 196 | 7 | 只能等游戏下发（§49 已证设备侧同样没有） |
| 只有 `-battle`/`-gift` 变体包 | 36 | 36 | 音频已用 `voiceExtra` 挂上；**正文齐全却没进前端**（见下） |
| 剥身份后缀才命中皮肤表 | 55 | 55（是基础行的） | **不能做**，见「已排除的假设」1 |
| 皮肤表里查无此名 | 54 | 0 | 领航员/指挥官等 NPC 皮肤，不在这套 CV 表里 |
| 该船本就无 CV | 13 | 2 | 结构性无解 |

**已排除的假设（三条，各自都配了正向证据）**
1. **「剥掉 `_wjz`/`_ex`/`_heihua`/`_idolns`/`_pt`/`_blueprint` 就能继承基础皮肤的语音」——否证**：
   - 游戏**确实会把这类画法单独立行**：`ship_skin_template` 里 `_wjz` 24 行、`_idolns` 5 行
     （`vtuber_fubuki_wjz` id 900209、`chicheng_idolns` id 900204…），azdata 快照与设备侧 sharecfg 两份表都有；
     而这 29 行**既没有主包也没有正文行**（0/24、0/5）⇒ 游戏自己就没给这类画法配音、配词。
   - 我这 55 个名字在两份表里**一行都没有**；盘上 55/55 **只有静态立绘、没有 Live2D/Spine 模型**；
     而它们要继承的那个表行本来就已经挂着 4~5 张画法（`banjiu` + `_n` + `_hx` + `_ex` + `_wjz`）。
   ⇒ 它们既不是「有自己语音的另一张皮肤」，也不是「能安全继承的另一张画法」——游戏数据里就没有它们的台词条目。
   剥后缀等于拿基础皮肤的台词冒充它的，正是 §53 警告的「不报错的语义错」。
   **§53 当时定的"故意没修"是对的，现在补上了它缺的理由。**
2. **「`voice_actor = -1` 表示这艘船没有 CV」——否证**：35 张**已解析出声、`skin_voice.json` 里能播**的皮肤，
   其表行就是 `-1`（含义是"本行未单独配置，继承"）。按 `-1` 判会把 140 张「缺包（可等下发）」错标成
   「结构性无解」——**这是自己造一条否证**，比漏修更糟。判据收紧成只认 `0` 后，无 CV 从 183 回落到 13。

3. **「54 张查无此名 = 我们漏接线」——否证（C 项，2026-09-27 用户拍板排查）**：它们是领航员/领洋者/
   探索者等秘书舰换装与 `npc*` 剧情立绘（28 族；36 张命中 42 行的 NPC 图名表）。决定性证据：
   **NPC 族在皮肤表里真有行的那 62 行，`voice_actor` 全是 -1、主包在盘上 0/62、台词行 0/62**
   （`voice_gap_audit.py --drill` 逐族列出）⇒ 整族在本机数据里零线索，不是解析器漏了它们。
   ⚠️ 边界：这只证"本机推不出包号、没有台词行"，**不证**"游戏里永远不会有"——
   `cv-90017~90056` 那段连续缺号（§49）说明 9004xx 这一段更像"配置已收录、音频未随包下发"。
   ⇒ 画廊显式 🔇 是正确显示，**不改代码**；若哪天游戏下发了这批包，重跑 `extract_cv_voice.py --skip-done` 即可吃到。

**一条判据自身的踩坑（循环判据）**：第一次问「无解皮肤有没有正文」时查的是 `skin_words.json` 的 `m`，
而 `m` 正是 `build_skin_words.py` **只遍历 `skin_voice.json` 里已解析出声的皮肤**建出来的
⇒ 答案恒为 0 张，看起来像"它们连台词也没有"，其实是同一筛选条件的自我复述。
换成直接查权威表 `inputs/gamecfg/ship_skin_words.json`（键 = 皮肤行 id）后是 **100/354 有正文**。
**判据：要问一个子集的性质，必须去比它更上游的源，不能用由同一个筛选派生出来的产物。**

**剩下的唯一真口子（待拍板，不动那条 75 分钟管线）**：36 张「有变体包音频 + 正文齐全」的皮肤
不在 `skin_voice.json` 里 ⇒ `m` 收不到 ⇒ 语音页整页不显示（`index.html` 的 tab 判据是 `s.voiceCount>0`），
而爱宕(`aidang`)这类送礼语音恰恰最容易被点进来看。修法：`build_skin_words.py` 再补一遍
「盘上有表行但没语音」的键，前端加一节「仅台词（无音频）」。

**涉及文件**: `scripts/diag/voice_gap_audit.py`（新）、`.diag/voice_gap_audit.json`（逐张明细）。
相关：§47、§49、§53、§54、WF-21、WF-22。

---

## §60. 台词层两处内容缺陷：`{namecode:98}` 直接端给用户 + 44 张有词却没地方显示（2026-09-27）

**日期**: 2026-09-27　**状态**: ✅ 两处都已修并实播复验（截图逐张看过）

**发现方式**：给 §57 那 44 张做「仅台词」页时截图目视，最后一行「资料」写着
`我是{namecode:66}级重型巡洋舰二号舰、第二舰队旗舰——{namecode:67}…`。
回头查在盘产物：**884 个皮肤行、3272 处正文带占位符，其中 862 行是有音频、现在每天都在播的**
——上一轮接台词层时我把结构判据（逐字对齐、行数、可播）全跑绿了，唯独没看图，
所以这缺陷已经上线一天。**教训：文本类产物的判据必须含一条"内容形状"断言，结构全绿不代表内容能读。**

### 缺陷一：运行时占位符没展开（862 个皮肤行的字幕）

- **根因**：游戏配置里的台词**自带** `{namecode:NN}`，运行时才由 `name_code` 表换成实体名；
  我把原始字符串直接端给了前端。
- **修法**：`tools/sharecfg_re/46_publish_name_code.py` 把 `name_code`（456 行，id→中文名+单字代号）
  发布进 `inputs/gamecfg/name_code.json` 并记台账；`scripts/build_skin_words.py` 在生成侧就地展开。
- **对齐关系不是猜的**：`43_check_namecode_alignment.py` 三条独立检验（T1 码 100% 可查、
  T2 自称率 2.13% vs 随机重分配零假设 0.03% = **80×**、T3 整行人读自洽：拉菲→[比叡]、布琳→[明石]）。
  发布脚本再钉一条**下游够用**的硬断言：`ship_skin_words` 里用到的 310 个码 100% 能展开，否则不写盘。
- **零容忍闸门**：产物里仍含 `{namecode` → `build_skin_words.py` 直接 `SystemExit`；
  `talk_verify` 两条语音页判据各加 `residue`（页面上出现占位符即红）。
- **不编名字**：查不到的码**原样留着并计数**——宁可看见占位符，不许拿语义猜一个填进去。

### 缺陷二：44 张「有表行、主包未下发」的皮肤正文齐全却没地方显示

- 判据链：`build_skin_words.m` 只遍历 `skin_voice.json` ⇒ 这 44 张（爱宕 11 / 拉菲 17 / 加贺 11 / 其它 5）
  进不了词表；而语音页 tab 的放行判据是 `s.voiceCount>0` ⇒ **整页不显示**。
- 修法（全加法，不动那条 75 分钟语音管线）：
  ① 词表加第二趟（键=字段名本身，中文类别名照 `character_voice` 取，`drop_descrip` 这类非台词字段排除）；
  ② 索引加 `voiceText`（皮肤级/船级，**只在无音频皮肤上写**，`voiceCount` 语义不变）；
  ③ 前端 tab 判据换成 `voiceCount>0 || voiceText>0`，语音页加「仅台词」一节 + `talkCount` 兜底。
- **不许伪造播放器**：台词行 `src` 传空 ⇒ 不生成 `<audio>`；页面 audio 数只允许等于
  「变体包整包」那一节的条数。探针把这条当反向证据（`audio == extra` 且 `textRowsWithoutPlayer == 台词数`）。
- **闸门**：`gallery_index_diff_check` 声明 `voiceText` 为预期变化 ⇒ 皮肤标量 31000 项、船标量 9072 项逐字未变；
  词表产物 `m`/`L` 完全相同、值变化 3272 处**全部**含占位符（非占位符改动 0 处）。

### 顺带：并发会话抢同一个 CDP 端口 = 探针假红灯

跑 WF-16 第 5 件时 `hit_verify` 报 `WIRING=38`、`antu_2` 加载失败，形状是**每条 `played` 恰好等于上一个部位的动组**
（整体滞后一位）——查进程发现另一会话正在跑全库 `hit_verify`（pid 52308），而探针的
`PORT=9342` 与 `--user-data-dir=.diag/chrome_hitv` 都是**写死的** ⇒ 两个 CDP 驱动附着到同一个浏览器，
读到的就是交错的状态。
⇒ ①"整序列统一偏移一位"这种形状是**探针侧污染**，不是产品坏了，别照着它去改产品；
②共享工作树里跑 CDP 探针前，先看那个 `PORT` 上有没有别的 python 在跑；根治要给探针加 env 端口/profile
（本轮没有代那个会话改它正在用的工具，记成待办）。

**涉及文件**: `tools/sharecfg_re/46_publish_name_code.py`（新）、`scripts/build_skin_words.py`、
`scripts/build_gallery_index.py`、`gallery_src/index.html`、`scripts/diag/talk_verify.py`、
`inputs/gamecfg/name_code.json`（数据本体不入库，台账 `inputs/gamecfg/MANIFEST.json`）。
相关：§54、§57、WF-22、WF-15、WF-16。


---



---


### §59 画廊「打开皮肤缩得有点小」：两层根因 + 一条自伤（2026-09-27）

**现象**：用户报「现在打开某个皮肤时，总是缩得有点小」，且「不是默认上次的位置」。
这是**主观观感**，没有报错、没有异常产物 ⇒ 不能靠"跑一遍没崩"结案，必须先把它变成能红的数。

**根因分两层，混在一起谈会各修一半**：

| 层 | 事实 | 定位 |
|---|---|---|
| 外层容器 | 弹窗硬上限 `min(1100px,96vw)×min(880px,96vh)`，在 2560×1600 上只占屏 **43%×55%** | `.modal` |
| 内层取景 | Live2D 按 **Cubism 画布**适配（画布是模型自带的正方形安全框，角色只占 6~8 成高）；Spine 按包围盒 **+1.1 留白**，实测内容只占视口高 **65%** | `renderLive2D()` 的 `fit()` / `startSpine()` 的 `fit()` |
| 内层取景（静态立绘） | 适配函数带 `Math.min(..., 1)` = **永不放大**；原件多为 800~1100px 宽，弹窗放大后只能画到自然尺寸 ⇒ 四周大片留白 | `mountImageViewer()` 的 `relayout()` |

**修法**：弹窗 `min(1900px,96vw)×min(1400px,96vh)`；Live2D 改按「drawable 顶点框 ∩ 画布」的内容框取景（两条护栏 + 有效件 <3 则退回画布 fit，方向上单调放大 ⇒ 零回退可证明）；Spine 留白 1.1→1.05；静态立绘放大上限 1→2 倍（像素保真没丢，**双击仍是 1:1**）。

**⚠️ 一条自伤，是小窗口对照抓出来的**：把 `96vh` 写成 `94vh`（以为"数值更宽松"），于是在 `innerHeight < ~917` 的机器上 `94vh` **小于**原来的 880px 硬上限 ⇒ 弹窗反而变矮，而 Live2D/Spine 是高度受限的 ⇒ 直接回退。**改任何 `min(px, vw/vh)` 常量，交叉点两侧都要各测一档**（`--win 1600,1000` 与 `--win 2560,1600`）。

**⚠️ 判据用错会假报回退 5/10**：按「内容占视口面积比」比对，新版有 5 个样本"变小"；按「内容绝对像素」则是 10/10 变大（x1.69~x3.89）。原因是视口形状本身被这次改动改了（16:10 宽窗里 Live2D 从宽受限变成高受限），**比例是代理指标，用户看到的是像素**。工具与全部判据见 WF-16 追加段。

**顺带修掉一条老失效**：Live2D 的 `ResizeObserver` 直接挂 `fit()`，而 `fit()` 会把 `z/ox/oy` 清零 ⇒ **进一次全屏再退出，用户调好的缩放就没了**。改为 `refit(preserve=true)`：只按新视口重算基准缩放，偏移随 `baseK` 同比换算。

**已排除的假设**：① "是 Live2D 模型自身包围盒太小" —— 不是，`xuefeng`/`huonululu_5` 的内容框 ≈ 整张画布，收益全部来自外层容器放大；② "静态立绘的图本身分辨率不够" —— 不是，`ninghai_4` 的 CG 是 818×1018，在旧弹窗里已经 100% 填满视口高，"小"来自 880px 上限。

**涉及文件**: `gallery_src/index.html`、`scripts/diag/gallery_framing_ab.py`（新，A/B 取景 + 视角记忆回归）、`.diag/framing/`（对比截图与 `framing.json`）。
相关：WF-16、§20、§45/§46（Spine 巨幕遮罩那两类撑歪取景的件）。

---

## §61. 动效改动的四条假红灯（2026-09-28）

**日期**: 2026-09-28　**状态**: ✅ 四条全部定位并改掉判据本身，工具 `scripts/diag/gallery_motion_probe.py` 入库

给画廊样板页加「卡片微倾斜 / 缩略图淡入 / 弹层从卡片飞入 / 会滚的选中胶囊 / 昼夜圆形擦除」后，
第一版探针跑出 4 红 1 疑。**四条都不是产品缺陷，而是判据测错了东西**——但每一条都能让
下一轮把对的东西当成错的，所以逐条记下修法。

| # | 现象（我以为坏了） | 真实原因 | 改后的判据 |
|---|---|---|---|
| 1 | `transform` 不含 `matrix3d`、1008 张缩略图**一张都没加载**（`complete=false`） | 我用的是**前台但被切到后台的标签页**：`document.visibilityState==='hidden'` 时 Chrome 不出帧，CSS 动画**冻结在起始关键帧**（`getAnimations()` 返回 1008 条全停在 0），`loading=lazy` 的图也一张不取 | 动效断言只能在**会出帧**的环境跑：无头 `--headless=new` + `setDeviceMetricsOverride`，并**先断言 `visibilityState==='visible'`**，不对就直接判失败，不再往下比 |
| 2 | 选中胶囊落位「偏差 8.3/68.3px」、宽度只有 9.97px | 我在弹层**正播飞入动画**时量 `getBoundingClientRect()`——弹层当时被 `scale(0.116)`，rect 连内容一起缩了。产品落位其实是对的（10/83px） | 落位一律用 **`offsetLeft/offsetWidth`（布局值，不受 transform 影响）**，`placeTab`/`slidePill` 也改成同一套；探针再拿 rect 比对就是探针自己的错 |
| 3 | 点「夜」之后 `documentElement.dataset.theme` 和 localStorage 都还是 light | `startViewTransition(apply)` 的回调是**异步**的（先做整页快照才执行），点击那一刻读必然还是旧值 | 主题落值改到**切换后 1.3s** 再读；点击那一刻只断言同步写入的 `--cx/--cy` |
| 4 | 页面抛 `Uncaught ReferenceError: THREE is not defined` | `vendor/spine/spine-all.js` 自带的 three.js 集成代码，**正本同样报**，与本次改动无关 | 报错断言改成**与改前页做差集**（`--baseline index.html`），只有「样板比正本多出来的」才判失败 |
| 5（疑） | 「定格中间帧」截图里弹层已经是满尺寸，看不出在飞 | `--spring-slow` 曲线前段极陡：45% 时长处进度已到 ~0.96 | 定格取 **12% / 30%** 两个点，并顺手把 `matrix(...)` 打进日志（0.627 / 0.959）——弹性曲线的"什么时候到位"是要量出来的，不是猜的 |

**顺带量到的一条成本**：卡片倾斜是「读矩形 → 写两个 CSS 变量」，每个 mousemove 都构成一次
强制回流。改成**按卡缓存矩形 + 滚动时作废**后，无头实测 120 次事件 65ms（**0.55ms/次**，
60fps 预算 16.7ms），所以不需要 rAF 批处理。**但这条计时断言必须同时证明它真的在驱动倾斜**
（末卡 `--ry` 非零、且全场只有 1 张带倾角），否则测的只是 `getBoundingClientRect` 的空转。

**已排除的假设**：① 以为是 `clip-path`/`backdrop-filter` 与 View Transition 冲突——圆形擦除一次就过；
② 以为是 `will-change` 缺失导致掉帧——实测成本 0.55ms/事件，没加 `will-change`；
③ 以为 `.tslide` 没显示是 z-index 问题——实际是选中标签自己的 `background` 没清成 `transparent`，
和胶囊叠成两层（这条**是真缺陷**，探针的 `onbg==='none'` 断言抓到的）。

### 补（同日第二轮，加背景层时又撞三条）

| # | 现象 | 真实原因 | 改后的判据 |
|---|---|---|---|
| 6 | 「搜索框聚焦变宽」上一轮还测到 190→270，这轮恒 190→190，而 `activeElement` 明明是它 | 无头实例**没有真窗口焦点**：`document.activeElement` 设得上，但 `:focus` 不匹配 ⇒ 规则整条不生效。上一轮能过是因为那次恰好有焦点 | `Emulation.setFocusEmulationEnabled{enabled:true}`，且断言读 `el.matches(':focus')` 而不是 `activeElement`（后者是代理指标） |
| 7 | 同上，开了焦点模拟后仍 190→190 | 无头出帧约 8fps，0.28s 的宽度过渡在 0.45s 窗口里可能**一帧都没走**，量到的是起始值 | 等待按"够走完这条过渡"给（1.2s），并把 `flex-shrink` 一起打印 —— 指定宽度能被 flex 压回，两种失败要能一眼分开（顺手给 `#search` 加 `flex:none`） |
| 8 | 背景层判据全绿（canvas 铺上、rAF 在跑、z-index 正确），截图却和没加背景**几乎一模一样** | 卡片/面板是不透明的，铺满视口的背景 95% 被盖住 ⇒ "接上了"不等于"看得见" | 加一条**出图对照**：同一视角拍「背景开 / 背景关」两张，肉眼比差别；差别看不出就算失败。落地上给滚动容器留一条**不滚动**的空带（`main{margin-bottom:76px}`，`padding-bottom` 只在滚到底时露出来，等于平时看不见），并把 header 改成 `color-mix(... transparent)+backdrop-filter` 让辉光透出来 |

顺带：`0.5s 推进 4 帧` 这种"帧数判据"在无头里天然偏低，会把环境当缺陷。改成量**动画时钟**
（每帧 `clock += dt`），断言墙钟 0.5s 内落在 `(0.15, 0.55]` —— 下界证明 dt 真接上，
上界证明没快过真实时间（dt 单位写成 ms 这类事故会立刻爆掉上界）。

### 再补（用户判"这背景劣质"，重做成粒子星野）

**第一条是本轮唯一真正的产品 bug，而且是反向证据那条判据抓到的**：`bgFrame()` 开头无条件
`requestAnimationFrame(bgFrame)` 续帧 ⇒ 关掉「背景动效」或系统要求减少动效之后，`bgApply()` 里
`cancelAnimationFrame` 只取消了**当前排队的那一帧**，而已经排在队列里的回调又会把自己重新接上，
循环**永远停不下来**（reduce 场景下 `#bgfx` 已经 `display:none` 了，rAF 还在跑）。
修法：续帧判断放到函数**开头**，`if(!OPT.bgfx || RM.matches){ BG.raf=0; return; }`。
⇒ 通用形状：**任何自续的 rAF 循环都必须在自己内部检查 kill switch**，外部 cancel 一次是不够的；
而这条只有"关掉之后再量一次它还在不在跑"才测得出来，所以反向证据判据不是形式主义。

**第二条是"劣质感"的技术根因**（不是玄学）：用 `ctx.arc()` + `ctx.stroke()` 画圆点，得到的是
**描边小圆圈**，尺寸一致、亮度一致、没有光晕 —— 这正是"廉价粒子"的样子。换成：
① 预渲染 **径向渐变精灵**（64px，中心实 → 0.16 处 0.92 → 0.42 处 0.24 → 边缘 0），
`drawImage` 出来每个点自带光晕；② 三档视差层（远的更小更暗更慢、近的不但更大而且漂移与
指针视差都更大）；③ 每颗独立相位闪烁 `0.55+0.45*sin(t*tw+ph)`；④ 夜里用
`globalCompositeOperation='lighter'` 叠加出辉光，**浅色底反过来必须 `source-over` + 比底深的颜色**
（浅底上叠加只会糊成一片白雾）；⑤ 偶发流星（头亮尾消的一条渐变线，寿命 ~0.85s）。
成本实测单帧 0.13ms（帧预算 16.7ms），320 颗封顶也毫无压力。

### 再补（用户仍判"low"，最后发现是**实现层次**不对，不是参数不对）

**根因**：前两版都在 2D canvas 上画点，而参考页 `deepseek.com/harness` 打开的是
`getContext('webgl2', {alpha:true, premultipliedAlpha:false, powerPreference:'low-power'})`
+ 三段着色器：**值噪声 fbm → 对 fbm 取旋度做域扭曲 → 五色渐变 → 鼠标 flowmap 扰动 →
自发光 bloom → 活颗粒 → 暗角**（默认参数就写在那份 JS 里：`swirlIterations:12`、
`distortion:18`、`colors:["#000","#1A3870","#204a7e","#eed8aa","#000"]`、`bloomStrength:.4`、
`grain:.005`、`vignette:.38`）。**2D 描边圆点在这个层次上追不上，调参也调不出来。**
⇒ 判"看起来高级不高级"之前，先把参照物**拆开读**：`curl` 拿 HTML/JS，
grep `getContext(` / `uniform ` / 默认参数对象，十分钟就能确定"它是着色器还是画点"——
比反复猜三轮便宜得多。

**换成 WebGL2 着色器后又撞三条判据层面的坑：**

| # | 现象 | 原因 | 改后 |
|---|---|---|---|
| 9 | `readPixels` 读回来全黑，以为着色器没画 | `preserveDrawingBuffer:false`（默认）下，**跨一次 CDP 调用**再读，缓冲已经还给合成器了 | `draw` 与 `readPixels` 必须写在**同一次 evaluate** 里；判据改成"同块区域两次读的差异" |
| 10 | 单帧成本量出 0.01ms（假便宜）↔ 47ms（假贵） | WebGL 是异步的：只计提交 → 0.01ms；每帧补一次同步 `readPixels` → 把**软件光栅 + 读回**全算进去 → 47ms。两个都不是真机 GPU 成本 | 成本判据降级为"只抓病态"（>100ms 才红），并在输出里写明它是软件光栅上限；真帧预算要上真 GPU 量（无头量不出来就别声称量得出） |
| 11 | 动画时钟 0.5s 只走 0.05s，判"dt 尺度错" | 无头里 **rAF 时间戳推进得比墙钟慢**（本轮实测墙钟 0.5s 对应帧时间线 0.77s、时钟 0.05s），拿墙钟当参照系必然错 | 时钟判据换成对**帧时间线**：`BG.clock` 必须 >0 且**不快过 `tlast-ts0`**；画面是否真在动改由第 9 条的逐像素 MAD 判 |

**顺带被反向证据抓出来的两个真 bug**（都不是环境造成的）：
① 弹层在飞入动画播到一半时被关闭 ⇒ 元素 `display:none` 让 CSS 动画停摆、`animationend`
永不触发 ⇒ `.fly` 类永久挂着，下次以"减少动效"打开时它还在。修法：开合两侧都
`classList.remove('flyout','fly')`，**不能只靠动画结束回调摘类**。
② `dt=(ts-BG.last)/1000` 可能为负（探针用未来时间戳手动驱动过 `bgDraw`，真实场景里
rAF 时间戳也不保证单调）⇒ 时钟倒退。修法：`Math.max(0, …)` 夹住，并且**探针自己**要把
`BG.last` 掰回 `performance.now()`，否则它污染被测对象的状态。

### 再补（"像大海一样"：一条判据抓出白天整屏死白）

把着色器改成海洋构图（上浅下深 + 光柱 + 海面亮带 + 横向洋流 + 焦散网纹）后，
夜里正常，**白天的 `readPixels` 读回来是均值 255、标准差 0** —— 整屏纯白，
所有"画面在变 / 鼠标有影响 / 有结构"的判据一起变成 0 差异。

- **根因**：白天底色三段本身就接近白（`#bcdcf0 → #e6f4fd → #ffffff`），
  上面又叠了光柱 + 海面亮带 + 焦散三束加性光，输出直接**削顶到 1.0**。
  夜里同一套数值没问题，所以这是**只在浅色主题暴露**的缺陷。
- **教训（判据层面）**：判"画面有没有内容"**必须看标准差，不能只看均值** ——
  纯白和纯黑都是均值极值、方差为零，而人眼看到的"什么都没有"正是这两种。
  本轮就是 `sd > 3` 这条把它抓住的；如果当时只判"均值在合理区间"就会放行。
- **修法**：白天底色压回浅蓝（三段最高只到 `#eaf6ff`）、三束光的系数从
  `0.10/0.22/0.26` 收到 `0.06/0.10/0.10`、bloom 阈值抬到 0.92 强度降到 0.08。
  改完实测均值 247、标准差 4.8、横向/纵向各向异性 1.57×、上段 250 vs 下段 234。

### 再补（用户判"鼠标划过约等于 0 / 白天太亮"：判据绿着而人眼否了）

- **鼠标那条判据的门槛定错了**：探针量到"指针进出采样区差 9 个亮度单位"就判通过，
  用户肉眼判"约等于 0"。9/255 在一片浅蓝上确实看不出来 ⇒ **门槛必须按"人眼可见"校准，
  不能按"非零"校准**。改法：白天 `mstr` 0.55→0.90、在场感 0.35→0.55、推开/绕旋/提亮系数翻倍，
  门槛提到 ≥6 且**固定在最弱的那套主题（浅色）下量**——改完实测差 46 个单位。
  通用形状：凡是"有没有效果"的判据，先问"这个差值在最终显示介质上人眼分得出来吗"，
  分不出来就把门槛抬到分得出来为止，而不是记一个"非零即过"。
- **白天太亮 = 又一次削顶，只是没削到全白**：底色三段最高 `#eaf6ff` 时中心均值 247，
  人眼判"太亮"。压到 `#cfe7f7` 后中心 206。⇒ 亮度类判据要**给区间**（本轮定 120~240），
  只判"有内容/没削顶到 255"会放过"整体过曝"这一档。
- 顺带修了探针自己的污染：读"底图"前必须先把指针停到角落，否则量到的是鼠标光斑
  （本轮曾把白天均值量成 253，误以为又削顶）。

## §62. 背景第四版「划过起浪」+ 玻璃拟态：本轮 8 处红，3 条是真缺陷（2026-09-29）

**日期**: 2026-09-29　**状态**: ✅ 全部定位；真缺陷 3 条已改产品，判据自身 5 条已改判据
**工具**: `scripts/diag/gallery_motion_probe.py`（24 条判据）+ `scripts/diag/gallery_ui_shots.py`

背景动效被连否五版（气泡 / 2D 星野 / WebGL 噪声着色器 / 漂移色块 / 磨砂白卡），
用户的两句话点出了真正的分界：**「装饰性动效不许自己动——动必须是对操作的响应」**
和 **「毛玻璃 ≠ 玻璃拟态」**。于是背景换成 CPU 波动方程 + WebGL 着色的水面
（静止时一帧都不画、划过才起浪），卡片与导航栏改成透玻璃 + 折射边墙 + 常驻斜反光。
过程中 8 处红，逐条分清是产品错还是判据错：

### 真产品缺陷（3 条）

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 1 | 白沫**一个像素都没有**，浪过之处只是"水变蓝了" | 高度场打包成 8bit 纹理时标度给太大（`HS=1400`）：波顶直接冲到 255 **削顶**，削顶区相邻纹素全等 ⇒ **梯度 = 0** ⇒ 泡沫项恒 0。梯度正是泡沫的唯一来路 | `HS` 降到 620（满偏映射到 ~208/255 不削顶），并给泡沫加第二条来路「到波顶也起沫」，不只依赖梯度 |
| 2 | 指针**瞬移**（从窗口外进来、探针把光标挪到角落）会在背景上糊出一道浪，用户看到的是"我什么都没做，背景自己被划了一道" | 瞬移给出几百格的位移，代码按速度插值注入脉冲，等于沿那条直线划了一笔 | 超过阈值（45 格）只挪锚点、不起浪 |
| 3 | 浪**永远不平**：无头里 20 秒还剩 peak=0.015 | 阻尼写成"**每帧**乘 0.964" ⇒ 浪多久平**取决于帧率**。挂上毛玻璃后无头只有十几帧每秒，真机低端设备同样会被判成"背景永远在动" | 改成按秒衰减 `damp=0.11^dt`（与原设计等价但与帧率解耦）；收摊阈值也从"贴着衰减尾端"的 0.0045 抬到 0.012（换算过仍肉眼不可见，但留 2.7 倍余量） |

另有两条同批修掉：**悬停规则整条替换 `box-shadow`**，把玻璃的镜面亮边与外投影一起丢掉，
悬停瞬间玻璃"塌成一张没厚度的纸"（判据：阴影层数只许持平或变多，且不许出现带 spread 的彩色环）；
**给 `header` 的直接子元素统一设 `z-index:1`**，让每个子元素各自生成层叠上下文，
下拉面板的 `z-index:40` 被关在自己那个 `.ctl` 里出不来，提示文字压在展开的面板上
（用户截图："混在一起了"）——子元素只留 `position:relative`，两道玻璃伪元素改用 `z-index:-1`。

### 判据自身的假灯（5 条，都是"测错了东西"）

| # | 我以为坏了 | 真实原因 | 改后的判据 |
|---|---|---|---|
| 1 | `:hover` 恒不命中、"焦点环没起来" | ① 用 `dispatchEvent(new MouseEvent)` 测伪类——伪类由**命中测试**决定，不由事件决定；② 上一节 `err_pass` 结尾点开了弹层，`.mask{position:fixed;inset:0}` 挡住真实指针 | 一律走 `Input.dispatchMouseEvent`；测悬停前先重载页面；`focus()` 后**分两次求值**并轮询到 `matches(':hover')` 为真 |
| 2 | "按下没有压感"（`filter=brightness(1)`） | ① 按压事件类型写成 `mouseDown`，CDP 要的是 `mousePressed`/`mouseReleased`，写错**静默忽略**；② `:hover` 刚成立那一帧过渡还没起步 | 事件类型改对；命中后**轮询 filter 落位**，不判"这一瞬间" |
| 3 | "焦点环没起来：`--lift` 生效但 border/box-shadow 没变" | `focus()` 之后同一次求值里读计算样式 = 过渡**第 0 帧**：`box-shadow` 显示成 `旧值, transparent 0 0 0 0`（缺的层按透明零长度补齐），只有没参与过渡的自定义属性跳到位 | 分两次求值 + 等过渡走完；顺手把 `EXC None` 改成带 `exceptionDetails.text/description`（SyntaxError 的信息不在 `message` 里） |
| 4 | "浪停之后画面回不去" | 整图哈希被两件事污染：`loading=lazy` 的缩略图**放着放着继续到货**；以及卡片上的**镜面高光坐标是持久状态**（划过一串卡之后每张卡高光都停在最后经过处）。后者其实是真缺陷，改成"指针离开即复位" | 比对区改成 `main` 左侧那条**永远没有卡片**的 16px 留白；比较前先轮询到图片停止到货 |
| 5 | "倾斜只有 1.4°/1.8°，肉眼约等于零" → 我据此**删掉了整条动效** | 取样点在卡面 68%/32% 处，而满偏有 4.5°。把"取样点偏小"当成了"设计幅度小"；用户要的其实是**看得见**，不是不要 | 判"看不见/没效果"一律按**满偏**（指针推到角上、取两个角的 max）；动效被否掉之前先确认是不是量错了地方 |

### 把主观反馈翻译成能红的判据

「还是毛玻璃」→ 背景模糊 >10px **或** 面板底色 alpha >0.30 即红；
「不要发光」→ 非 `inset` 的 shadow 层出现第 4 个长度值（spread）即红；
「不要整块填色」→ 选中项 `background-image` 含 gradient 或底色 alpha >0.30 即红；
「不许自己动」→ 静止两帧（隔 1.3s）比对区**逐像素必须相同**，且能量归零时 `rAF` 必须不再排队。
每条都拿**旧版本当阳性对照**（削顶那版、磨砂那版确实都会被判红），否则判据可能是空的。

### 补：全库 hit_verify 整批报"GALLERY is not defined"是服务器半死，不是产品坏了

第 5 件跑到一半，几乎每个皮肤都报 `err: "GALLERY is not defined"` ⇒ `没有 nAreas` ⇒ FAIL。
**决定性对照**：拿换入前的正本（`git show ee931aa:gallery_src/index.html`）当页面跑同一段，
症状**一模一样**且两页都没有任何脚本报错 ⇒ 排除本轮改动。真因是本地服务器进入了一种
半死状态：**连接照收，但每个请求恰好 2.00s 返回 0 字节**（`index.js` 实际 857KB）。
重启服务器后立刻恢复（857836B / 4ms），把报错那 6 个皮肤单独重跑 ⇒
`WIRING=0`、可点中率 65/65、`EXIT=0`。

⚠️ 两个教训：① 我第一反应是"单线程服务器被大贴图堵死"，**没验证就写进了回复**——
实际它本来就是 `ThreadingTCPServer`；grep 到 handler 类不等于看到全貌，判机制要读到
`serve_forever` 那一行。② 验收脚本的服务器预检**不能只看连得上或 HTTP 200**，
要量真吐出的字节数（`wf16_regression.py` 已按此升级）。

### 一条方法论

⚠️ 取 alpha 必须同时认 `rgba()`、`rgb(r g b / a)`、以及 Chrome 把 `color-mix()`
序列化出来的 `color(srgb R G B / A)` / `oklab(...)`——只写 `rgba()` 正则会把 13% 半透明
读成"不透明实心块"，逼着人去改本来正确的代码。


## §63. 画廊服务器：每次「客户端取消下载」永久泄漏一个 handler 线程（2026-09-29 证死并堵掉）

§62 末段那次"半死"只查到了现象（连接照收、返回 0 字节），根因当时挂着。本轮用
**定向剂量学**代替"再跑一次 30 分钟大负载赌复现"，三轮下来结论如下。

### 已证死的机制

`socketserver.ThreadingMixIn.process_request_thread` 在 `finally: shutdown_request()`
**之前** 调 `self.handle_error()`，而默认实现要往 **stderr** 打 4 段 traceback。
Chrome 换页/关标签会取消在传的贴图，服务端就是 `sendall` 抛 `WinError 10053/10054`
（`.diag/` 里三份历史 stderr 日志共 30 次这类 traceback，是常态不是意外）。
⇒ **只要 stderr 是个慢消费者**（双击 bat 起的控制台被选中暂停、或父 shell 已退出
留下没人读的管道），每次取消就楔死一个线程，且它在 `shutdown_request` 之前 ⇒
socket 既不吐字节也不关。

**剂量学（D 格 vs E 格，唯一变量是 `Server.handle_error` 静默与否）：**

| 格 | stderr 去向 | 掐断 2600 次后 threads | handles |
|---|---|---|---|
| A | 真文件 | 5（不变） | 113 |
| D | 从不读取的管道 | **2605** | **18313** |
| E | 同 D，但静默 `handle_error` | 5 | 113 |

线性、无界、每次取消恰好 1 线程 + 7 句柄。修法已落 `gallery_src/_gallery_server.py`：
`Server.handle_error` 只吞 `ConnectionReset/ConnectionAborted/BrokenPipe/Timeout` 四类。
**改后复测**：同剂量 2600 次 ⇒ 泄漏 0；对照组一条真异常（URL 塞 `%00` ⇒ `os.stat`
抛 `ValueError`）stderr 仍写 1526B，取消类写 0B ⇒ 不是把错误全咽了。

### 两条否证（都配了对照，别重走）

1. **"客户端停读但不 RST 会永久卡住 handler"——本机不成立。** 看着像真：无 `timeout` 时
   线程停在 8 长达 40s，加 `timeout=8` 后 10s 内回落。但 t=70 时前者也回落到 5 而
   handles 仍是 137（socket 还开着）⇒ **环回口的接收窗口能自动长到吞下整个 18MB 响应体**，
   `sendall` 直接发完了。第一版更假：用 858KB 测，`SO_RCVBUF` 还设在 connect 之后
   （Windows 不认），窗口没锁住 ⇒ 那不是"卡不住"的证据，是无效测试。
   ⇒ 不必给 handler 加 `timeout`（本机场景不存在）。
2. **"泄漏到拐点 ⇒ 整站 0 字节"没量到。** 2600 个泄漏线程时正常请求仍能 5ms 拿到 858KB。
   所以**不能声称本机制就是 09-29 那次的成因**，只能声称它是个方向唯一的无界泄漏。
   "恰好 2.0s" 这个指纹至今没解释。

### 剩下的靠现场，不靠赌复现

预检判红时现在会顺带从进程外部打一行
`pid=… threads=… handles=… parentAlive=… parent=…`（`wf16_regression.py:server_forensics`）。
下次再半死，这一行足以三分：线程/句柄暴涨 = 本机制；进程不在 = 静默死掉；两者都正常 = 另有其因。
红路径本身是测过的（`.diag` 里起一个"照收连接、回 200 但 Content-Length: 0"的桩，
断言判红 + 归因成"半死" + 现场非空）——**一个从没红过的闸门等于没有闸门**。

## §64. Spine 分层改认 prefab：`parts.json` 一条链，以及"去重过的产物会吞掉修复"（2026-09-29）

§58 那条"parts 列表按目录 glob 猜"的账本轮结掉：234 个 Spine 目录里 **30 个多画、15 对本体/`_hx`
的 CG 逐像素完全相同**。做法见 WF-14 追加，这里记两件不显然的事。

### 一、最大的坑：那 15 对"相同"已经被硬链成同一个 inode，不断链就永远修不出来

第一次重导 36 个目录，机器判据全绿（34 张内容变了），但"15 对不再相同"这条**判据红**——
每对的两个名字仍然指向同一份数据。原因：09-20 那次硬链去重把它们当重复文件链在了一起
（**它们之所以重复，正是本条 glob bug 造成的**）。往任何一个名字里写，两个一起变，最后一个赢。

⇒ **可复用的判据**：重导一批产物之前，先查这批里有没有 `st_nlink>1` 的；有就先断链
（读出来 → 写临时文件 → `os.replace` 回同名，内容不变、各自一份数据），再重导。
否则症状是"改动明明生效了，成对判据却怎么都不过"，而且**看起来像修复失败**。
本轮断 15 个，之后 15 对全部拉开。

⚠️ 反过来也提醒：任何"逐字节相同"的历史结论，如果那批文件被去重过，就**不能只比哈希**——
哈希相同可能只是同一个 inode。比之前先看 `st_nlink`。

### 二、分层的权威只有一份 `parts.json`，读写都只认它

- **谁写**：`scripts/extract_spine_v2.py`（`--parts-only` 可只补清单不重解码贴图）。内容取自
  `spinepainting/<name>` prefab 里每个 `SkeletonGraphic` 节点，层名 = `skeletonDataAsset`
  解析到的 `SkeletonDataAsset.m_Name` 剥 `_SkeletonData` 后缀，**不受节点名与文件名错配影响**。
  顺带落 `startingAnimation` / `initialSkinName` / `localScale` / `anchoredPosition` / `rotZ`。
- **谁读**：`build_gallery_index.py`（层集合）、viewer 与 `cg_export.html`（层集合 + 逐层缩放 + 逐层起始动画）。
- **缺文件必须大声报错，不许回落 glob** —— 回落等于把这个 bug 换个地方留着，只是没人再看得见。
  解析函数抽在 `compose_paintings_v2.skel_layers()`，`spine_parts_prefab_diff.py` 也改成调它，
  避免"谁写谁读各一份实现"。
- 唯一不写 `parts.json` 的目录是 `fulangxisike_2`：它本来就是个只有散 PNG、没有任何 `.skel`
  的空壳导出目录，索引一直跳过它。**这是空壳，不是缺清单**，两者不能混成一个报错。

### 三、两条"没变"要分开说，别一起算成战果

- **`pulimaosi` 画面未变**：机制本身由 `buleisite` / `buleisite_hx` 两张变了而证明
  （页面上 `#spAnim` 默认值确实从 `normal` 变成 prefab 写的 `idle`）。`pulimaosi` 不变的原因
  **没有查死**——它的 `T` 层写的 `idle2` 与该层动画列表里第一个动画名可能本来就重合。
  下一步要证它，就在 `cg_export` 的日志里带出每层**实际选中**的动画名，别拿"应该一样"当结论。
- **`yuanchou_2_hx` 的 CG 是 64×2400 的细长条**，新旧都是 ⇒ **先前就存在的取景塌缩，本轮没弄坏也没修好**。
  同目录的 `yuanchou_2` 却从同样的 64×2400 被修成了 2400×1332。两者都是单层皮肤，差别只在 skel。
  已另立待办（§6 第 22 条），别和 §45/§46 那两类混：那两类是"框撑太大画面缩中间"，
  这里是长宽比直接塌成一条。

### 涉及文件

`scripts/compose_paintings_v2.py`（`skel_layers`）、`scripts/extract_spine_v2.py`（`--parts-only`）、
`scripts/build_gallery_index.py`、`gallery_src/index.html`、`gallery_src/cg_export.html`、
`scripts/diag/spine_parts_prefab_diff.py`、`scripts/diag/spine_parts_wiring.py`（★新增，Spine 标签黑盒验收）、
`scripts/diag/make_pair_sheet.py`（★新增，改前|改后成对总表）。

## §65. 做本地网页控制台撞上两个 Windows 坑（2026-09-29）

`scripts/pipeline_panel.py`（资产更新控制台）第一次自测就撞上两条，都跟项目无关、换任何
Windows 本地服务都会中：

### 一、`allow_reuse_address` 在 Windows 上**允许两个进程绑同一个端口**

POSIX 的 `SO_REUSEADDR` 只放行 `TIME_WAIT`；**Windows 的语义是"随便绑"**。于是面板起了两个实例
都 `bind(8788)` 成功、都不报错，而连接被**随机分给其中一个** —— 表现是"同一个页面，任务列表
一会儿有一个儿没有"，极难查。发现方式很偶然：`Get-CimInstance` 数了数 `pipeline_panel` 的 python 进程，
**两个**。

⇒ **凡是自己写 `allow_reuse_address = True` 的本地服务，绑之前必须先探端口**：
`socket.connect_ex(('127.0.0.1', PORT)) == 0` 就说明已经有人在跑，直接复用/退出，不要继续 bind。
画廊那个 `_gallery_server.py` 早就有 `port_in_use()` 预检（§43 写的），新写的这个漏了 ——
**同一个坑在同一个仓库里第二次踩，是因为没去看已有的同类实现怎么写。**

### 二、通过 Git Bash 写 .bat 时，`>nul` 会被改写成 `>/dev/null`

用 heredoc 把批处理内容喂给 python 写盘，结果落盘的是
`where py >/dev/null 2>nul` —— cmd 里根本没这个设备，**启动器直接坏掉**。
这是 MSYS 的路径自动转换在作怪（它把看起来像设备/路径的参数翻译成 POSIX 形式）。

⇒ 写 .bat 时**不要让 `nul` 以字面形式经过 shell**，在 Python 里拼出来：`NUL = 'n' + 'ul'`；
写完必须回读断言 `'/dev/null' not in 内容`。这条断言比"我看了一眼觉得对"可靠。

### 三、★ 最狠的一条：Windows 上 `os.kill(pid, 0)` **不是探活，是杀进程**

面板用"pid 还在不在"判断任务是否结束，写的是最常见的
`try: os.kill(pid, 0); alive = True / except OSError: alive = False`。
**CPython 在 Windows 上把 `os.kill` 实现成 `OpenProcess(...) + TerminateProcess(handle, sig)`**
—— 传 0 也一样，它真的会去终止那个进程。而这个面板每 8 秒轮一次 `/api/state`，
于是**第一次轮询就把正在跑的流水线子进程当场杀掉**。

一次真更新要跑几十分钟，症状会是"任务莫名结束、日志停在半路"，而且**退出码看着正常**。
发现过程纯属偶然：给面板做端到端检查时发现 `--plan` 的日志永远不含收尾行、
状态永远卡在 `running`（进程被杀后第二次轮询才被判 done）。

⇒ 只读探活要走 `kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` +
`GetExitCodeProcess`，判 `== STILL_ACTIVE(259)`（已抽成 `pipeline_panel.pid_alive()`）。
⇒ **凡是"轮询别人活没活"的代码，写完必须配一条"任务必须跑到自然收尾"的判据**：
只测"进程死了能被判出来"是测不出这条的 —— 探活函数自己就是凶手。

### 涉及文件
`scripts/pipeline_panel.py`（`pid_alive()`）、`scripts/diag/panel_ui_probe.py`（★新增，
含"轮询不许把子进程杀掉"这条回归判据）、`启动一条龙控制台.bat`（现已改名 `启动资产更新控制台.bat`）。

## §66. 装饰性背景与「看得懂的仪表盘」：三条只有量了才知道的账（2026-09-29）

给 `scripts/pipeline_panel.py` 换视觉（13 行表格 → 四步主线 + 星辰大海主题）时撞到的三条。
都跟这个界面本身无关，任何「本地网页 + 动态背景 + 要读数据」的组合都会中。

### 一、半透明面板 + 会动的背景 = 背景渗进文字区（实测 36 级）

第一版 `.pane` 用 `rgba(…, .90)` 想要毛玻璃质感。把背景开/关两态拿来比，卡片**内部**最大差 **36**：
一颗星正好落在某个字下面。alpha 0.90 意味着还有 10% 的背景参与成像 ——
肉眼说「很淡」，量出来是「看得见」。

⇒ **数据承载面（阶段卡、日志、对照图底）必须完全不透明**，主题只留在没有数据的带里
（这里是顶部 hero 与底部海平面）。改完同一判据 = **0**。
另一头也要防：面板全不透明之后，装饰区如果没有**一块真的能看见的地方**，
主题会被挤到只剩栏缝 —— 实测浪在背景可见区只剩 68 个像素，等于没有主题（判据却照样全绿）。
**「不遮挡」和「存在感」是两条独立的判据，都要量。**

### 二、整屏逐像素比对会假红三次，每次都不是产品问题

「静止时两帧逐像素相同」是从画廊搬来的老判据，直接照搬到这个界面连红三轮：

| 症状 | 真实原因 | 改后的判据 |
|---|---|---|
| 浪散完最大差 2、4727 个点，全落在半透明层覆盖处 | 半透明层在 WebGL 活动后重新合成，**渐变 dither 变了** | 按「画了背景的元素的矩形」把屏幕**分区**：背景可见区 / 不透明内容区 / 纱区，分别判 |
| 划水那张内容区差 209 | CDP 可信鼠标停在谁身上，谁就点亮 `:hover`（卡片被抬 1px ⇒ 文字逐通道差 209） | 拍照前把指针**停回同一个无 hover 角落**，静止帧与浪帧同一指针位 |
| 「背景不渗进卡片」判红 133 | 被裁一半的卡 `getBoundingClientRect` 仍越过滚动容器底边，量到了下面**故意露背景**的海平面带 | 取样框与 `.col` 及视口**求交** |

⇒ 三条通用的：**分区比对**、**固定指针位**、**取样框求交**。
外加一条**正向对照**：「关掉背景后整屏确实变了」——没有它，
把背景整层删掉也能在「不渗进卡片」上拿满分（本项目最容易犯的假绿灯那一类）。

### 三、`/api/state` 每次轮询都去 `os.walk` 9 万个源包

输入指纹 = 源包文件数 + 依赖表 md5，`os.walk(files/AssetBundles)` 要几秒。
前端 8 秒轮一次 ⇒ 每 8 秒白扫一遍盘，而且**首屏空十几秒，看着像程序坏了**（截图为证：
左轨与中间全空，只有图例渲染出来了）。

⇒ 面板侧给指纹/范围加 30s TTL 缓存；`render()` 必须扛得住 `S === null`；
并把「首屏在算（要扫 9 万个源包）」当成一句话显示出来，而不是留一个 `—`。

### 涉及文件
`scripts/pipeline_panel.py`、`scripts/diag/panel_ui_probe.py`（★新增，22 条判据）、
`启动资产更新控制台.bat`。

## §67. 把背景从"水面"换成"会散开会聚回的星野"，撞上四条（2026-09-29）

用户改口："别大海了，做星辰，鼠标划过散开再聚集回来，色调东京夜。" 换引擎之后连红四轮，
**四条都是产品问题，但第三条是判据本身错了**。

### 一、"指针瞬移不算划过"不能按固定像素判 —— 按了等于整层背景对鼠标没反应

从画廊搬来那条护栏时写成 `位移 > 45px 就当瞬移、不起浪`。星野这边照抄，结果探针划 40 笔、
`strokes=0`、画面零变化：正常**快扫一步就是 48~58px**，全被当成瞬移丢掉了。
⇒ 改成按**速度**判：`>4200 px/s` 或距上一拍 `>250ms`（跨标签回来、首次进入）才算瞬移。
画廊那边当时没暴露，是因为水面还有一条"按下=水滴"的路径兜着，而星野只有这一条。

### 二、冲量的单位是 px/s，不是位移 —— 给 11 等于没推

`st.vx += 方向 * imp` 里 `imp` 是**速度增量**。上一版给 11，而弹簧刚度 34 ⇒ ω=√34≈5.8/s，
稳态让位 ≈ v/ω ≈ 2px，肉眼与像素判据双双为 0（`strokes=40` 却"什么都没动"就是这么来的）。
⇒ 按 ω 反推：要 50px 的让位就得给 ~300 px/s。调完峰值 45~58px、约 3 秒聚回、残留 0.0000px。
**同一行代码里"推到了"和"推得动"是两件事**：`strokes` 只证前者。

### 三、★ 逐像素比对在这个页面上量的是合成器，不是产品（这条判据得换掉）

"背景渗不渗进数据面"原本用「开/关背景两态，卡片内部逐像素比对」。它测不动了，两个原因：
- 切 `body.plain` 会改变合成层，Chrome **重新光栅化整页**，全站文字边缘都能差 ±209
  （实测 20 万个差异点，散布在明明不透明的面板内部）；
- 画布每重绘一次也有同样的效应。于是"星野散开那张 vs 静止那张"在卡片内部量到 154。

⇒ 换成两条**结构性**判据，它们不受光栅化影响且更可证：
① 数据面计算样式 `backgroundColor` 的 alpha 必须 = 1（直接量"透不透明"）；
② 每个数据元素（卡 / 日志 / 缩略图 / 指标 pill / 表格单元）的矩形必须**整张落在某个不透明面板内**。
逐像素那条只保留在**背景可见区**（那里没有文字层，比的就是星点本身），
并保留"关掉背景后背景可见区必须空掉 ~20 万像素"作正向对照。
⚠️ 教训：**判据失效方向要查**——这次是"测得太严"导致假红，但如果反过来"测得太松"就会假绿；
所以换判据时必须同时留一条能红的正向对照。

### 四、`.pane{overflow:hidden}` + flex 列 = 把内容切掉

为了画那条霓虹顶边给 `.pane` 加了 `overflow:hidden`，而 `.col` 是 flex 列、面板默认可压缩
⇒ **面板被压扁、内容被裁**：第二张卡下沿被切 45px，日志格塌成 28px 只剩标题条、`pre` 顶出面板 170px。
⇒ 列里的面板一律 `flex:0 0 auto`（要滚的是列本身）；日志格给**确定的视口高度**而不是 `flex:1` 去"填满剩余"。
这条是判据②替我抓出来的——它本来是设计来查"背景渗漏"，顺带把裁切 bug 也逮住了。

### 五、用户给的参照页要先把机制量清楚，别按自己以为的动词去实现

第一版按"划过散开再聚回来"做成了**弹簧推开**，做完用户补了一句"我要那种很多星星，
但是只有经过才显示，像 mimo.xiaomi.com/coder"。抓了那页的说明才知道根本不是"推开"，
是**擦除式显影**：遮罩被光标擦出洞、洞随划速从 8px 长到 128px、亮点约 520ms 淡完不残留。
⇒ 同一个"划过有反应"，"移动已有物体"和"点亮已有物体"是两种完全不同的实现，
先问清/查清是哪一种，比先写出来再改省一半时间。

配套多出一条判据：**locality**。只划屏幕左半边，然后断言右半边亮着的星必须为 0 颗——
这是唯一能挡住"整片一起亮"那种看着热闹、其实完全不是显影的实现的办法。
（只判"划过之后亮了多少颗"是判不出来的，整片亮也能过。）

### 涉及文件
`scripts/pipeline_panel.py`（星野引擎 v2 → 显影版 + 布局）、
`scripts/diag/panel_ui_probe.py`（判据 25→30→32 条）。

---

## §68. 界面每 8 秒整屏闪一次，而验收全绿了三天（2026-09-30）

用户问"为什么每过一段时间就闪一次？是定时刷新吗？"——是，`setInterval(apiState, 8000)`。
但**数据刷新本身不是闪的原因**，而且这条缺陷早就被观测到了：探针里写着
`window.__probe.stop()`，注释明说"逐像素比对期间必须停掉 8 秒轮询，否则卡片入场动画会把
比对带歪（实测假红 75）"。**当时的处置是让验收绕开它**，于是"32 条判据全绿"和
"用户屏幕上每 8 秒整屏淡入一次"并存了三天。

### 一、根因：入场动画挂在元素的基础类上，而 `render()` 是 `innerHTML` 整片重建

`.step{animation:rise .46s backwards}` + `.stage{animation:rise .4s backwards}`，
每次 `render()` 把 `rail.innerHTML=''` / `cards.innerHTML=''` 清掉重建 ⇒ **新建节点 = 动画从头播**，
还带 26ms 递增的 `animationDelay`，于是一张接一张淡入。哪怕服务端返回的内容一个字节都没变。
切步骤、任务收尾回读、日志筛选走的都是同一个全量重建。

⇒ 两条修法，**第二条才是根因修复**：
① payload 签名没变就根本不 `render()`；
② 动画只挂在 `.in` 上，而 `.in` 只在**该 key 首次挂载**时加（切步骤时清空 `mounted` 重来）。
只写①会漏：状态真的变了（某卡转绿）照样整屏淡入一次，那同样是要不得的。

### 二、★ 验收脚本自带的"绕道开关"是最危险的一类假绿灯

判据本身没错（"静止两帧逐像素相同"），错在**跑之前先按下了一个把被测机制关掉的按钮**。
⇒ 新增一节**带着轮询跑**的判据，并放在旧判据之前：跨一次 8s tick 比整屏逐像素、
断言 `.step/.stage` **节点对象没被换过**（pin 住再比 `includes`）、`document.getAnimations()===0`。
旧的 `stop()` 钩子保留（比对背景时仍要用），但它**不再决定结论**。

通用形式：任何"为了比图先把 X 停掉"的钩子，都必须回答一句**"X 在真实运行里会不会触发？"**
会 ⇒ 那条判据验的是你的开关，不是产品。

### 三、判"某个动效真的在动"，要先掐掉同屏其它动画源（否则背景白送你一个绿灯）

新加的"光束是在走的"这条，第一版直接比悬停中的两帧，`最大差 233` 通过——**但那是假绿**：
真鼠标划过页面会把星点亮起来并持续衰减，即使边框光一动不动，两帧之间也必然有差。
⇒ 这一段**先把星野关掉**再量（关掉之后所有像素差只能来自光效本身），
并补一条"跑完已把星野交还给下一节"的断言，防止这个开关状态漏到后面的背景判据里。

### 四、"回到同一张帧"抓到一条真留痕：收缩原点没复位

卡片左光条静止时是 `scaleY(.34)`、悬停展开到 1，`transform-origin` 跟着指针进入的高度走。
离开后 scaleY 回到 .34，但 `--oy` 还留在内联样式里 ⇒ 那条 2px 的竖条**永久偏在指针进来过的
那个高度**。判据报 `最大差 22`，把差异点按列做直方图：**104 个点全部落在 321~322 两列**，
正好是卡片左边缘——所以不是重光栅化噪声（那种散布在文字边缘、量级也是 ±20 但铺满整屏）。

⇒ `pointerout` 时 `removeProperty('--oy')`，并把这条判据从"scaleY 回来了没"
扩成"scaleY **和 transform-origin** 都回来了"。
教训：**凡是"跟着指针改几何"的效果，离开时要把每一个变量都复位**——只回主属性、漏回原点或
角度，肉眼看不出来但逐像素看得出来。（技能第 12 条"跟指针走的持久样式"的同一条纪律，
这次是它的一个具体形态，而且**只在元素自身不透明度不变时才会露出来**。）

### 五、"把提示词写进界面"是同一类毛病的文案版

第一版把设计论证直接印在常驻界面上：底部一条 176px 的"夜空"带在解释星野怎么衰减、
图例下面一段在论证"红色永远只等于判红"、对照表下面一句在说"图放在不透明的底上背景渗不进来"、
判据里带"（这三个可信）"、按钮上带"（不下载）"。这些是**我写代码时的理由**，
不是用户读界面时要的信息——用户判"界面太多说明性文字，很不美观"。
⇒ 判据：**一句界面文案如果是在为某个设计决定辩护，它就该进 `怎么用` 抽屉或 `docs/`，
不该进常驻界面**。本轮据此删掉整条底部带 + 四段脚注，并把所有按钮/标签压到动宾式短语；
必要解释搬进抽屉新增的「颜色与档位怎么读」。

### 涉及文件
`scripts/pipeline_panel.py`（签名守卫 + `.in` 首挂载 + 光效引擎 + `--oy` 复位 + 文案削减）、
`scripts/update_pipeline.py`（`STEPS` / `Stage.title|judge_desc|writes` / 未签字 verdict 精简）、
`scripts/diag/panel_ui_probe.py`（判据 32→52 条：新增"静止不闪"3 条 + 光效 10 条，
背景节改为**先落到静止再量**，见 §67 三）。

---

## §69. 「还是太丑了，星星画得敷衍」：拿公开设计系统的禁止清单当判据（2026-09-30 第二轮）

上一轮删完说明性文字、加完光效，用户仍判**「还是太丑了，你借鉴一下大厂的优秀 UI，
星星画得有点敷衍」**。这次不再自己猜第 7 版（§6 待办第 5 条就是为这一刻写的：
**再被否要外部参照物，不要自己猜**），改成把两个公开设计系统的 token 取回来当判据。

### 一、参照物给的不是灵感，是**禁止清单**，而我三条全犯了

取到 Linear / Raycast 的成文规则，逐条对上我上一版的所作所为：

| 参照物的原话 | 我上一版在干什么 |
|---|---|
| Don't use lavender as a section background or card fill | `--pane:#12101f / --card:#181527 / --deep:#150d1f` 全是薰衣草底 |
| The brand **resists drop shadows** almost entirely, leaning on tonal lifts and subtle top-edge highlights | 每块面板挂 `0 22px 46px -32px`，卡片 hover 再来一条 |
| Don't introduce a second chromatic accent / Don't add atmospheric gradients | 紫+品红+青三彩并用；每块面板顶边一道紫→品红渐变"灯管"；hero 带渐变纱 |
| 小标签：caption 12px / letter-spacing 0，没有全大写 | `.ph` 用 `uppercase + .18em`，`.runs th` 同 |

⇒ 病根不是"配色不好看"，是**我用装饰去冒充层级**。改法：中性五档表面阶梯
（`#07080b→#0b0c10→#101116→#15161b→#1b1d23`，通道极差 ≤8）、发丝线三档实色
（`#24262c/#33363e/#454954`）、**投影全部换成 `inset 0 1px 0 rgba(255,255,255,.045)`**、
圆角按 4/6/8/12 分档、间距走 4 的倍数、chrome 强调色只留一个品牌紫
（主动作用它，签字按钮借用「等你签字」的琥珀，语义自洽）。
**氛围全部退回背景那片星野**，面板一分都不给。五个状态色一个都没动。

⚠️ 这四条**写成了判据**而不是"我改好了"：面板/卡片底色通道极差 ≤8、外投影层数必须为 0、
`.ph/.runs th` 的 `textTransform` 不得为 uppercase、chrome 元素的 `backgroundImage`
不得含 gradient。**每一条旧版面都会红**——不写成这样，下一轮换配色又会把病带回来。

### 二、"星星敷衍"的真身：每颗星外面套着一个看得见的**正方形**

放大显影带才看清：星不是"画得糙"，是**每个精灵四边不透明**，被硬切成方块，
再经 `rotate()` 变成菱形，满屏像撒了一把风车。根因是 canvas 的一条冷知识：

> `createRadialGradient` **超出 r1 之后会一直沿用最后一个色标**，而高斯
> `exp(-t²/σ²)` 在 t=1 处还剩 5~19% ⇒ 精灵边缘不是 0。

我上一版外晕还写成 `stop(gr,0.055,(i/14)*0.30)`（t 只走到 0.30），边缘 alpha 高达 48。
⇒ 所有精灵一律乘 `(1-t²)` 窗口，让 t=1 严格归零；判据直接读精灵位图：
**四角 + 四边中点的 alpha 必须 ≤8**。这条比截图便宜，而且不会漏。

顺带修掉另外两处"敷衍"：亮星比例从 ~5% 降到 **0.47%**（幂律，暗尘占 90%），
星色从糖果四色改成**按色温**（蓝白→冷白→淡金，暗星偏蓝白），
芒改成从核向外锥形衰减、**每颗星随机旋向**，星座连线 alpha 上限从 0.52 压到 **0.16**。

### 三、星云要单独一张**永不重绘**的画布

把星云烘进星点画布、每帧 `drawImage` 一次，等于每帧白拷 6MB；
在无头 SwiftShader 上把一次 `Page.captureScreenshot` 拖到 **2.16s**，
而且每帧重合成会带 dither 抖动。⇒ 独立 `<canvas id="nebula">`，只在 resize 时重画，
`body.plain` 下整张隐藏。静止帧天然逐像素相同。

### 四、本轮三条假红灯全在**测量通道**，不在产品（记下来免得去改正确的代码）

1. **截图耗时 > 动画时长**：判"光束在走"用 `sleep(0.26)` 抓两帧，而一次截图就要 2.16s、
   光束全长只有 0.78s ⇒ 两张都落在动画结束后，量到 0 差。
   ⇒ 用 WAAPI 把动画**钉在确定时刻**（`a.pause(); a.currentTime=120 / 520`）再各拍一张，
   与截图耗时无关。钉帧后差值 239，光确实在走。
2. **Chrome 把 `inset` 序列化在 box-shadow 的末尾**
   （`rgba(...) 0px 1px 0px 0px inset`），`startswith('inset')` 会把内阴影误判成外投影。
   ⇒ 判据要 `'inset' in layer.split()`。
3. **自己造的哨兵串把自己判红**：JS 侧写 `className||'(none)'`，Python 侧比
   `cls in ('','none')` ⇒ 永远红。⇒ 判"切回新版面"要落在**语义**上
   （`classList.contains('legacy') === false`），不要比字面串。

而"V 切回来像素最大差 2"是**整页渐变重新合成的 dither 地板**（§67 三记过）。
处理不是把阈值从 0 放宽到 2 了事——那正是"测得太松 = 假绿"的方向——而是
**换成结构断言钉死**（类名回位 / 星位残留位移 0 / 显影场清零 / 节点未被重建），
像素只保留">8 级的像素必须为 0"这一条有理由的地板。

### 涉及文件
`scripts/pipeline_panel.py`（token 层重写 + `body.legacy` 对照 + 精灵图集 + 星云独立画布）、
`scripts/diag/panel_ui_probe.py`（判据 52→66 条：版面 token 5 条 + 星野画法 5 条 + V 键 3 条，
其中"精灵边缘必须透明"与"零外投影"两条旧版面必红）。
做法与借来的 token 见 **WF-23 追加（2026-09-30 第二轮）**。

---

## §70. 「一次只暴露下一步」重做主屏，撞上五条（2026-09-30 第三轮）

用户仍判「整个界面看着还是不是很懂；UI 还是不够好看，想要简约但交互特效要足」，
并选定方向：**主屏只回答"现在该做什么"**，13 个阶段/日志/对照表全部收进「细节」抽屉。
版面重做之后探针从 66 涨到 76 条，中间撞的五条都记在这里。

### 一、状态落定**不能依赖动画跑完**：抽屉遮罩赖在屏上，把一半判据带崩

`closeDetail()` 原本在弹簧回调里判 `if(v>=1.015) 摘掉 .on`。探针只 `sleep(0.5)` 就往下量。
一旦那一帧没跑到位，`position:fixed;inset:0` 且带 `backdrop-filter` 的遮罩就一直盖着整屏，
连带三个看起来毫不相关的后果：

- 「背景可见区」被遮罩算成内容 → `region_diff` 拿 **999 / 0 像素** 判红（像掩码写错，其实是没关严）；
- `backdrop-filter` 在无头里拖垮帧率 → 划动的相邻两拍间隔超过 250ms → **全被当成瞬移丢掉**
  （实测"笔画"从 41 掉到 4，看着像"背景对鼠标没反应"）；
- 抽屉停在 `translateX(100%)` → 里面 `.stage` 的矩形在视口外 → 悬停判据量不到，
  报成"光条不展开"。

⇒ 摘 `.on` 交给 **`setTimeout(260ms)` 兜底**，弹簧只负责好看；
并且探针侧 `open_detail/close_detail` 一律**轮询到 `.on` 真的换态**再往下走，
另加一条前置判据：「量背景前屏幕上没有全屏遮罩」。
通用形式：**任何"覆盖层 + 动画关闭"都必须有一个与动画无关的状态落定路径。**

### 二、一行拼写打死整条弹簧循环

`magPaint()` 里 y 轴写成 `y.y` —— 弹簧条目只有 `{x,v,t,k,d,apply}`，**位移是 `x`、速度是 `v`**，
`y.y` 是不存在的字段 ⇒ `undefined.toFixed()` 抛 `TypeError`。
而 `apply` 是在 rAF 的 `tick` 里被调用的，异常一抛**整个循环终止**，之后所有弹簧
（含抽屉进出、进度线）全部停摆。症状出现在离根因很远的三个判据上。

⇒ `apply` 回调必须自己保证不抛；探针那条「全程无 JS 异常」以前只收
`Runtime.exceptionThrown` **事件**，抓不到 `evaluate` 响应里回来的错误 —— 已补，
并且现在带**栈顶三帧**（不然 `undefined.toFixed` 这种消息根本定位不到是谁）。

### 三、类名撞车：`.act` 既是顶栏按钮组容器，又成了"主行动按钮"

新写的主行动用了 `.act`，而 header 里早就有 `.act{display:flex}` 是**按钮组容器**。
结果整条顶栏右侧被涂成实心紫（截图一眼可见）。⇒ 改名 `.pact`，并在注释里记下这次撞名。
**给新组件起类名前，先在文件里 grep 一遍同名。**

### 四、「星野避让」矩形必须贴着字，不能横跨整列

主屏大字不坐面板，可读性改靠**让星点不在文字区显影**（比"给文字蒙一层半透明纱"干净：
纱那条路实测 alpha .90 仍会被顶出 36 级差异）。
但 `.eyebrow/.do/.foot` 是 block，默认拉满 `.now` 的 1060px ⇒ 避让区变成一整块横盖半屏的板砖，
"划过才显影"直接被判成"对鼠标没反应"。⇒ `align-self:flex-start;max-width:fit-content`。
配套判据写成**成对**的：横扫之后总亮数必须 >0（证明真划了）且落在字底下必须 ==0
（只判后者会退化成"什么都没亮也算通过"的假绿灯）。

### 五、本轮三条假红灯全在测量通道（产品一处没错）

1. 探针 JS 串里写 `/act/`：Python 普通字符串把 `` 吃成**退格符**，
   正则永远不匹配 ⇒ "主屏只有一个实心行动"报 0 个。⇒ 改用 `classList.contains('act')`。
2. 固定 `sleep(0.55)` 读 CSS 过渡：光条 `.38s` 在抽屉开着 + 画布在跑时无头里起步很晚，
   实测只走到 `scaleY 0.886` ⇒ 报"没展开"。**这正是技能第 11 条写过的坑，我自己新加的判据又犯了一遍。**
   ⇒ 一律轮询到落位或超时。
3. 探针自己的启动轮询表达式 `panelState().stages` 在 `S` 还没到时抛异常，
   被新的异常计入机制记成"页面有 JS 异常" ⇒ 改可选链，探针自己的竞态不该算到产品头上。

### 涉及文件
`scripts/pipeline_panel.py`（主屏 + 底部步骤条 + `#detail` 抽屉 + `SPRG` 弹簧 + `avoid` 避让）、
`scripts/diag/panel_ui_probe.py`（判据 66→76：主屏 7 条 + 遮罩前置 1 条 + `settle()`；
并修掉探针自身三处假绿灯）。做法见 **WF-23 追加（2026-09-30 第三轮）**。

---

## §71. 「增量」从来不存在、签字门有两道是空的、前台进度被憋死——一次执行侧体检（2026-10-01）

**起因（用户提问，不是报错）**: 「跑一次要多少 G 内存？每一次跑都要全覆盖写入？一次只能开一个大型任务，那我还要开 MuMu 打开碧蓝航线，这还怎么跑？」
为了回答"多少 G"去量真实峰值，顺手把"每次都全覆盖写吗"拿去对着代码核 —— **五条全是真缺陷**，
其中三条会让一轮真更新悄悄覆写整片正式区：

1. **`affected.txt` 从来没有人写**（最严重）。`st_pull` 只写了配套的 `affected.meta`，清单本体
   一次都没落过盘；读侧 `affected_stems()` 读不到就 `return None`，而 **None 在下游的含义恰好是
   "全量"** ⇒ 所谓增量静默等于全库重跑，`--plan` 还印着「增量：尚未 detect」把人往安全方向骗。
   根因不是漏写一行，是**用一个哨兵值同时表示"没范围"和"全范围"**——这两种语义的失效方向完全相反，
   必须分成两个返回值（现在：`scope_state()` → `full/ok/missing/stale` 四态）。
2. **退化出来的"全量"路径当场炸**：`run_v2_full.baseline_targets()` 无条件 `listdir`
   `Output/Paintings_Synthesized`，而产物早在某次改名后叫 `Paintings_v2` ⇒ `FileNotFoundError`。
   所以真实状态比"覆盖写"更糟：**默认跑到立绘那一步就判红停住，整条线根本跑不完**。
   （判据面：一条"看起来在工作"的路径连续几天判红，没人去看它是炸在哪个目录上。）
3. **`audio` / `cg` 两道 live 档的签字门是空的**：函数收了 `approved` 参数**却一行都没检查它**，
   `st_cg` 还带 `--redo` ⇒ 单独点一次就把 231 张 CG 全量重导进 `Output/CG_v2`（无暂存通道）。
   面板上"未签字只跑读半边"这句话对这两个阶段是假的。
4. **前台看不到进度**：`run()` 用 `subprocess.run(capture_output=True)`，子进程输出要等它整个跑完
   才一次性可见，而面板只看得到本进程的 stdout ⇒ 子进程跑动期间**界面一个字都不动**，
   看着就是死掉（`PYTHONUNBUFFERED=1` 救不了——不是缓冲，是 `capture_output` 本来就要等结束）。
5. **超时只杀直接子进程**：`subprocess.run(timeout=)` 到期杀的是 python，起 Chrome 的那些脚本
   会漏整棵树（§50 那次把可用内存压到 1.1GB 的就是这个形状）。

**修法**（全在 `update_pipeline.py` + `scripts/mumu_sync.py`，前端一行没动）:
- `mumu_sync.py diff --list-out <path>`：把「新增+大小不一致」的**相对路径**落盘（屏幕输出只有
  按顶层目录聚合的计数，名字拿不到 —— 这就是当初清单没法自动生成的直接原因）。
- `write_scope()` 一次写 `affected.txt` + `affected.meta` 两份，**拉完包后重盖一次指纹**
  （`bundles=` 变了，不重盖下一轮就把它判成过期）。
- `scope_or_stop()`：范围 missing/stale ⇒ 阶段判红并写明「拒绝按全量兜底」，**一个子进程都不起**。
- 导出阶段**按域过滤** stem（`stems_for(top, …)`），"是不是主皮肤"最终由
  **磁盘上有没有那个不带后缀的主包**裁判，不靠后缀表。
- `st_audio`/`st_cg` 补门：未签字只跑只读审计，结论保留 `未签字，请 --approve` 给前端 `statusOf()` 认。
- `run()` 改两条流各一读者线程：边跑边转（`echo` 命中必转，其余按 2.5s 限速 + 抑制计数），
  全文照旧返回给判据数行；超时走 `taskkill /T /F` 后照旧抛 `TimeoutExpired` 让阶段判红。

**实测数据**（新工具 `scripts/diag/peak_mem.py`，按进程树采峰值 WorkingSet，先用 400MB 自测准头）:
立绘 50 包一批 **0.63GB / 17s**、8 个真主皮肤 **0.64GB / 13s**（≈1.25 秒/张）、Spine 3 个 0.50GB / 5s；
13 个阶段全串行、同一时刻只有 1 个子进程 ⇒ **这条线稳态约 0.7GB**，"跑一次几个 G"是错的担心，
真正挤内存的是同时开着的 IDE/浏览器（15.4GB 的机器实测只剩 2~3.5GB）与 CG 那步的 Chrome 树。
按 1.25 秒/张外推，全量立绘 4488 张 ≈ **1.5 小时** —— `WORKFLOWS.md` 白名单里那句
「全量可再生，但耗时**数十小时**」是老 AssetStudio 时代的数，已就地改掉。

**闸门自测抓到的两个自伤**（`scripts/diag/test_pipeline_gating.py`，40 条）:
- 它先抓到**我自己的映射有洞**：`a2_n_bj1_tex` 归并成 `a2_n_bj1` 后躲过了 `_bj` 后缀检查
  （真后缀是 `_bj1`），会被当成立绘去渲染 ⇒ 报 ✗ ⇒ 整条线判红停住。⇒ 后缀表只能当预筛，
  最终裁判必须是磁盘上有没有那个主包。**这条是"测试比代码先对"的样本**。
- fixture 用了编造的包名（`haitian_3` 之类），被正确的磁盘过滤器滤光 ⇒ 4 条假红。
  **测"按盘上事实裁判"的逻辑，样本必须取自盘上真名**。
- 还有一次 `GATE_EXIT=0` 的假绿：`py … | tail` 让 `$?` 量的是 tail 的退出码（同 §70 那类
  "壳命令遮蔽退出码"）。⇒ 先 `>log 2>&1; E=$?`，再读 `E`。

**判据（新增，别再退回原样）**: `py -3 scripts/diag/test_pipeline_gating.py` 必须 `[PASS]`。
它不看文案看**行动**——只断言"有没有 spawn 那个会覆写 `Output/` 的子进程"，因为
签字提示文字会改，会不会去写盘不会说谎。

**涉及文件**: `scripts/update_pipeline.py`（`scope_state`/`stems_for`/`scope_or_stop`/`write_scope`/
`kill_tree`/`run` 重写，`st_pull`/`st_paintings`/`st_spine`/`st_live2d`/`st_audio`/`st_cg`/`cmd_plan`）、
`scripts/mumu_sync.py`（`diff --list-out`）、`scripts/run_v2_full.py`（`BASELINE_DIR` 可缺）、
`scripts/diag/peak_mem.py` + `scripts/diag/test_pipeline_gating.py`（新）。相关：WF-15、WF-23、§25、§37、§50、§64。

## §72. 探针验的却是**旧页面**（控制台进程 import 时把 HTML 烘死）＋ 设计意图一变、旧判据必红（2026-10-01）

**症状**：把「夜航」方向落进 `scripts/pipeline_panel.py` 后跑 `panel_ui_probe.py`，光效一节炸
`KeyError: 'k'`（读 `__probe.fx().k`）—— 而磁盘上 `fx(){ … k:FX.k||null … }` 明明在。
同时「V 节前弹簧停机 + 星野已冻结」「跨一次轮询整屏逐像素相同」等一批判据集体红。

**根因（两条叠在一起）**：

1. **控制台进程在 import 那一刻就把 HTML 烘进内存**，请求处理器用的是模块加载时生成的页面串；
   改文件不影响**已经在跑的那个进程**。⇒ 探针连的是 8791 上那个老进程，验的是**上一版页面**。
   看起来像"探针读了个不存在的字段"，其实是被测对象过期。
   **判据**：探针一报"页面缺某个钩子/字段"，先别改探针 ——
   `(Invoke-WebRequest http://127.0.0.1:<port>/).Content | Select-String <新钩子名>`，
   服务出来的 HTML 里没有就重启服务。
   ⚠️ 重启前先确认端口真的空了：本项目的 `Server(allow_reuse_address=True)` 在 Windows 上
   **允许两个进程绑同一端口**（请求被随机分给其中一个），起第二个会得到"状态忽左忽右"的鬼故事。
2. **旧判据保护的是已作废的设计意图**。B2 方向要背景**常驻漂移**，而旧契约里"静止时零动画
   （`ST.raf==0`）、两帧逐像素相同、淡净后回到同一静止态"三条必然红 —— 它们守的是"背景不许自己走"。

**修法（两条各自不同，别混）**：

- 服务端：重启（`py -3 scripts/pipeline_panel.py --port 8791 --no-open`）后再跑探针。
- 探针：把旧三条**逐条替换**成新契约，每条注释写明"替代了旧的哪一条、为什么旧的那条现在必红"：
  旧「静止两帧相同」→ 新「常驻 + 漂移有界且慢（位移 ≤ DRIFT上限×Δt+0.6px，且确实有位移）」；
  旧「淡净后回到同一静止态」→ 新「冻结态可复现（`__probe.freeze(true)` 后隔 1.4s 两帧逐像素相同）」；
  新增「天是状态面」（信标列对准当前步节点、列内亮度 > 全屏均值、判绿荡波）。
  ⚠️ 跨段像素比对必须**先冻结再钉相位**（`pin_sky`）：只冻结，两次冻结落在不同相位上仍会差一整片天
  （本轮实测假红 149 级）。

**两条临界判据的处置不同 —— 这是「重写契约」与「放宽判据」的分界**：

- 「V 切回来像素只允许 dither 地板级差异」实测最大差 4、**>8 级的像素 0 个**。夜航底色是**两层**
  `linear-gradient`（天 + 地平线雾），切 body 类让 Chrome 重合成时 dither 能到 ±4。
  ⇒ 把兜底的 `bmax` 从 3 放到 6，**但咬人的 `nbig==0` 一个字没动**。
- 「信标列亮度 > 全屏均值 1.25×」实测 1.239×，差一点。这条**没有放宽阈值**，而是**把提亮系数
  从 0.85 提到 1.20**（列心 2.2×、列内均值 ~1.5×）—— 低于这个量级信标只是"碰巧有几颗亮星"，
  读不出"天在告诉你现在走到第几步"。改完实测 1.37×。

**已排除的假设**：

- ~~"`KeyError: 'k'` 是探针与页面钩子不同步，去改探针"~~ —— 否证：磁盘上钩子在，**服务出来的 HTML 里没有**。
- ~~"V 切回来差 117 是真留痕"~~ —— 否证：那次是星野没冻结（漂移相位差）；冻结 + 钉相位后
  结构性断言全绿、`nbig==0`。
- ~~"信标不够亮是采样口径错（取样窗偏大/偏小）"~~ —— 否证：口径是列心 `0.6×half` 内，与设计意图一致；
  是系数本身偏小。

**环境**：`AGENTS.md` 写 Python 3.13，但本机 `py -3` 解析到 **3.11.9**（`py -0p` 只有 3.11 / 3.12.14）。
⇒ 探针里 f-string 内嵌反斜杠（`f"…{ev('…\"x\"…')}"`，3.12 才允许）直接 `SyntaxError`，
`py -m py_compile` 一跑就现形。写探针时把嵌套求值先落成局部变量，别塞进 f-string。

**判据（新增，别再退回原样）**：`py -3 scripts/diag/panel_ui_probe.py --port 8791` 必须
`[PASS] 界面判据全绿`（78 条，退出码即结论）。

**涉及文件**：`scripts/pipeline_panel.py`（token / 背景 / 光效 / `__probe` 钩子）、
`scripts/diag/panel_ui_probe.py`。相关：§67、§69、§70、WF-23。

## §73. 用户否掉「常驻漂移」→ 星野退回显影式；进度台与自绘光标落地时撞上的四条（2026-10-01 第五轮）

**背景**：第四轮把「夜航」落成正本（海军蓝 + **常驻**星野 + 指针携光）。用户否掉两处：
① 星野要的是**渐进式显影**（划过才亮），不是常驻漂移；② 按钮与光效**不如更早那版**。
同时提三条新要求：换鼠标样式、加**进度台 + 预估剩余**（并问"跑一次吃多少内存 / 多久"）、
**别把我给你的提示词写进界面**。

**处置**：
- 星野：退回**显影式**（静止全黑、划过才亮、约 520ms 淡净、淡净回**同一张**帧）。
  **保留** B 的海军蓝 + 蓝白（五个状态色 rgb 一个不动），光效**回到** conic 边框光束 + 控件内柔光 + 磁吸。
- 探针契约**逐条改回**：撤掉第四轮为漂移加的三条（有界漂移 / 冻结态可复现 / 天是状态面），
  恢复「静止两帧逐像素相同」「淡净后回同一张帧」。
- 新增**进度台**（只在真在跑时出现的一条细带：阶段 N/M · 已用 · 内存 · 剩余）与**三态自定义光标**。
- 帮助抽屉里为设计辩护的整段文案删掉（用户明确要求）。

**四条踩坑**（症状都指向错的地方，所以值得记）：

1. **`EV()` 把片段包成不 `return` 的箭头函数 ⇒ `awaitPromise` 拿到 `undefined`**。
   片段必须以 `return` 开头把 async IIFE 的 Promise 交出去。症状：进度台一批判据**齐刷刷 `None`**，
   而同一节「全程无 JS 异常」**还是绿的** —— 空判据不会报错，只会静默地什么都验不到。
   **判据**：新增一段判据后先看**回读值**是不是真的非空，别只看 PASS/FAIL 计数。
2. **「剩余」在两次 8 秒轮询之间是死的**。前端要按本地时钟往下走，就得记住"这份数据什么时候到的"：
   收数据时补 `g.at=Date.now()/1000`，再算 `eta-(now-G.at)`。**不记 `at` 则 `(G.at||now)` 恒等于 `now`、
   减数恒为 0** —— 一个永真表达式。（「已用」不受影响，它本来就走本地时钟。）
3. **进度台不能挂在 `render()` 里**。`render()` 会重建 13 张阶段卡，进度台跟着每 8 秒重建一次，
   会让探针「轮询没有重建 `.stage` 节点」这条**当场红**。⇒ 进度台单独走 `gaugeSet()`，
   与 `render()` 完全分离。**这是"动态数据面板不许进主渲染路径"的一个具体判例。**
4. **主按钮 hover 白底白字**。`.pact:hover` 只改了底色，`color` 从 `button:hover` 继承来的是
   `var(--txt)`（近白），落在近白底上等于隐形。修法：hover 规则里**显式写死深色** `color:#0a0b10`。
   ⚠️ 自绘控件的配套坑：**光标必须先用深色描一道底** —— 主按钮底色近白，
   只画亮线的十字光标在那儿整根看不见（这是自定义光标最常见的翻车方式）。

**已排除的假设**：

- ~~"用户说的『渐进式显影』是要更慢的漂移"~~ —— 否证：要的是**划过才亮**（显影），
  第四轮的常驻漂移方向整个作废。**别再提议"天活着"当卖点。**
- ~~"进度台数字不准是服务端 `_stage_means()` 算错"~~ —— 否证：直接对真实日志调 `gauge_safe()`，
  返回 `mem_mb=26.3 / total=13 / eta=36 / missing=11 / n=2`，口径正确；样本少时按设计报「≥」下限。

**环境**：同上条（`py -3` 解析到 3.11.9）。探针里 `import` 面板模块会触发 `sys.stdout.reconfigure`，
但模块有 `__main__` 保护、import 无副作用 —— 所以能在探针进程里直接调服务端函数做对账。

**判据（新增，别再退回原样）**：`py -3 scripts/diag/panel_ui_probe.py --port 8791` 必须
`[PASS] 界面判据全绿`（**86 条**，含进度台一节 10 条，退出码即结论）。

**涉及文件**：`scripts/pipeline_panel.py`（token / 背景 / 光效 / 光标 / `gauge_safe`）、
`scripts/diag/panel_ui_probe.py`。相关：§67、§70、§72、WF-23。

---

## §74. 第一次真跑撞上的五条：我把"已经最新"判成红、报错了耗时、闸门拦了不该拦的、进度台首次必盲、以及**自己把范围清单冲没了**（2026-10-01 下午）

**背景**: §71 修完当天用户就真跑了（14:45 签字拉包 1036 个 → 91643 包变 92679 → 14:49 再点一次检查）。
四条里第一条是我今早**自己引入的回归**，后三条是"没真跑过就不会知道"的那类。

1. **`diff` 报"新增 0 / 变更 0"被我判红**（文案还是"没拿到路径清单"）。
   0 变更是**合法状态**——刚拉完包再查一次当然没变化，diff 本身 rc=0。更危险的是修法：
   如果只把判红改成判绿然后 `write_scope([])`，就会**把 14:49 那份 1154 条的真清单冲成空**，
   于是"无事可做"和"范围丢了"长得一模一样，下一次跑整条线静默空转。
   ⇒ 空 diff 时先看有没有**当前指纹下的有效清单**：有就沿用并在结论里写明沿用了几条；
   没有才写空清单 + 说"本轮没有要重算的东西"。判据 `test_pipeline_gating.py [7]`（含"清单内容一字未改"）。
2. **我上午报的"deps 要 43 分钟"是错的**，实测 **3 秒 / 0.20GB**（`export_dependency_manifest.py`
   只读 `dependencies` 这一个包、取第一个 MonoBehaviour 就 break）。43 分钟来自 §50 的
   **立绘全库重扫**，我把它安到了 deps 头上，还据此告诉用户"增量一轮 1 小时出头、deps 是地板"。
   ⇒ 教训：**每个数字都要带来源**，跨条目引用别人的数时必须回到那条代码看一眼它到底读什么。
   错数字的代价不是难看，是用户会据此决定"要不要现在跑、能不能同时开别的"。
3. **依赖表"新表必须是旧表超集"这道闸门被游戏自己删掉的条目卡死**：
   `新表丢了 4 个旧包` ⇒ 判红停线，而那 4 条全是 `iconframe/*_skeletondata`，**本管线一个都不消费**。
   原判据把"保护我们消费的依赖"写成了"保护整张表"，于是每次版本更新都要人工放行一次无关噪声。
   ⇒ 改成按**消费域**分级（`CONSUMED_TOPS` = painting / paintingface / spinepainting / live2d / cue / dependencies，
   按 key 与 `file` 两个来源同时判）：消费域丢包照旧判红，非消费域**打出来但不拦**。
   判据 `[8]`，含"只丢 iconframe 时不得算 fatal"这条阴性对照。
4. **进度台的「剩余」第一次跑必然是未知**：它只认 `run_*.log` 的历史均值，而 13 个阶段里 9 个从没真跑过
   ⇒ 均值表为空 ⇒ 用户看到的永远是"样本不足"，这正是他抱怨的"不知道进行到什么程度"。
   ⇒ 阶段自带 `est`（固定耗时实测秒数）与 `rate/unit`（秒/项 × 本次范围项数）**两个来源，且只填量过的**；
   没量过的计入 `eta_missing`，前端只报 `≥` 不报 `~`，并把来源写出来（历史均值 / 速率×项数 / 实测常量）。
   流水线侧同步在阶段头打 `[i/N]` + 预计 + 每阶段实际耗时，日志和界面两处都能对上。

**一次虚惊（值得记，因为它吃掉一轮排查）**: 探针报红时文本里出现
「阶段 **3/11** · `export_cue_audio` · 已用 **1:02:05** · 内存 1.50 GB」——这三个量没有一个属于我起的任务，
我第一反应是"有别的会话在并发跑真更新"，去查了 `runs.json`、进程表、端口。真相是
**`panel_ui_probe.py` 自己注入的假 gauge**（它用合成数据单测进度台渲染）。
⇒ 合成数据必须一眼可辨：探针注入的假阶段名/假耗时不能和真实字段的取值域重叠
（`export_cue_audio` 是脚本名、不是阶段 key；11 也不是阶段总数），否则下一次还会误判成事故。

**涉及文件**: `scripts/update_pipeline.py`（`st_pull` 空 diff 分支、`deps_classify`/`CONSUMED_TOPS`、
`Stage.est/rate/unit`、`stage_units`/`fmt_dur`、阶段头 `[i/N]`+预计、每阶段实际耗时、`run()` 25 秒静默心跳）、
`scripts/pipeline_panel.py`（`_scope_units`、`est_sec` 三源估算、`eta_src` 来源标注）、
`scripts/diag/test_pipeline_gating.py`（判据 40→48：`[7]` 空 diff、`[8]` 依赖表分级）。相关：§71、§50、WF-15、WF-23。

### 第五条（最严重，是第五条而不是第一条的续集）：我把 1154 条真范围清单**冲没了**

用户 15:52 那次运行（拉包已完成、依赖表 15:51 刚换入）走完 `pull` 之后，
`.diag/pipeline/affected.txt` 从 1154 条变成 **0 条**，于是后面所有导出阶段都报告
「本次增量没有立绘源包 ⇒ 跳过」并**判绿**——14 张新立绘就这么静默消失了。三个条件叠加才成立，
缺一条都不会炸，所以它躲过了当天上午那一整轮自测：

1. 包已经拉完 ⇒ `diff` 报 0 变更 ⇒ 走进我上午刚加的"零结果"分支；
2. 依赖表 15:51 换入 ⇒ `fingerprint()` 里的 `deps=<哈希>` 变了；
3. 我上午把"清单是否新鲜"判在**整条指纹**上 ⇒ 旧清单被判 `stale` ⇒ 零结果分支落进
   `write_scope([])` ⇒ **空清单覆盖了非空清单**。

两条根因、两条修法：

- **新鲜度判据必须只看待它保护的那个量。** 范围清单描述的是"哪些**源包**变了"，
  它的有效期就该只看 `bundles=`；把派生产物（依赖表哈希）算进去，等于规定
  「拉包 → 换入依赖表 → 跑导出」这条**唯一正确的顺序**必然自我作废。
  ⇒ `bundles_of(fp)` 只取源包那半，`scope_state` 的 `stale` 只比它，并把两边 `bundles=` 打出来。
- **零结果分支不得覆盖非空产物**（上午那条教训的强化版：我写了"先看有没有有效清单"，
  但只在 `mode=='ok'` 时看，`stale` 时照样写空）。⇒ `write_scope` 自己兜底：
  新清单为空而旧清单非空 ⇒ **原样保住旧的**、只重盖指纹戳，并在 meta 里记
  `kept_from_prev: true`；两者不同且都非空 ⇒ 先备份成 `affected.prev.txt` 再写。

**被删的东西没有 git 兜底**（`.diag/` 在 `.gitignore` 里），只能靠盘上另外的独立证据复原。
两条各自成立、取并集：① **依赖表新旧两版的键差**（`.diag/pipeline/dependency_manifest.prev.json`
是换入前的自动备份）⇒ 797 条，但它看不见"同名而内容变了"的包；
② **有源包却没有产物 png** 的主皮肤 ⇒ 12 张，这是确定要补的下限；
③ 再加一层保守网：源包 mtime ≥ 2026-08 的主皮肤（179 个里的 167 个不在①里）。
⇒ 复原成 972 条 / 立绘 179 张（约 4 分钟），比原清单宽，但不会漏。

**判据**：`test_pipeline_gating.py` 48→**52 条**，新增 `[9]` 四断言——
"源包没变、只换依赖表 ⇒ 仍算 ok"、"清单内容一条没丢"、"源包数变了才 stale 且报出两边"、
"空结果不得覆盖非空清单"。**这四条正是这次事故的四个条件**，逐条钉住。

**界面侧同时改了三处**（用户："进度提示还是不够明显，要有进度条才行"）：
- 进度台从 `96×3` 的细线换成**整幅宽 + 9px 高 + 每阶段一道刻度**的条，分子允许带上
  本阶段内的比例（日志里有 `a/b` 才算，没有就明写"本阶段无项级进度"，**不拿旧值假装在动**）；
- 主屏那句大字下面会带出**跨步的判红**（"另有 1 步判红（第 4 步）"）与**上一轮用了多久**——
  进度台按契约跑完就收起（静止帧判据在守），所以这两个数必须由主屏带出来；
- `regress` 判红的文案改成说清真因：这次红的是**8777 画廊服务器没起**（前置环境），
  不是产物回归，两者的下一步完全不同。
- ⚠️ 顺带修掉一个会让"进度看起来卡死"的性能洞：一次 `/api/state` 里输入指纹被各处各算
  4~6 遍（每遍 walk 9 万多个源包），冷缓存那一拍实测 **5.8 秒** ⇒ 前端轮询超时。
  现在 `fingerprint()` 一次算完往下传（`scope_state`/`affected_stems`/`stage_units` 都收 `fp`），
  实测降到 **1.6 秒**（热缓存 0.03 秒）。

**涉及文件**（含上一段）: `scripts/update_pipeline.py`（`bundles_of`、`scope_state`、`write_scope` 兜底、
`st_pull` 零结果分支、`deps_classify`/`CONSUMED_TOPS`、`Stage.est/rate/unit`、`stage_units`/`fmt_dur`、
阶段头 `[i/N]`+预计、每阶段实际耗时、`run()` 25 秒静默心跳、`st_regress` 说清真因）、
`scripts/pipeline_panel.py`（`_unit_progress`/`_log_secs`/`_last_run`、`est_sec` 三源估算、整幅进度条、
跨步判红与用时上主屏、指纹一次算完往下传）、`scripts/mumu_sync.py`（`diff --list-out`）、
`scripts/run_v2_full.py`（`BASELINE_DIR` 可缺）、`scripts/diag/peak_mem.py` +
`scripts/diag/test_pipeline_gating.py`（40→52 条）。相关：§71、§50、§72、§73、WF-15、WF-23。
