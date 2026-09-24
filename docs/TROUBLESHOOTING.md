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
静止态实测本就 53/57 在画布外（编辑器遗留的停放标记，只有核心 3 个 + `touch_idle1` 真可点），
所以"进 1 层之后点哪儿都没反应"。游戏侧靠 `change_in`/`home` 状态机复位，Web 运行时没有状态机 → 同一份数据在游戏里不暴露。
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

**日期**: 2026-09-24　**状态**: ⚠️ 结论=**该工具在全库规模上"不可判"**，判据需按本条重定义后再用

**现象**: 全量重导后跑 `py -3 scripts/diag/l2d_ref_diff.py --all`，在 **206/269** 个键处日志停止增长、25 分钟零输出（手动停）。已打印结果：**PASS 5 / WARN 22 / FAIL 153 / SKIP 26**。而同一批数据在文件级审计（`clips 8154 / shell 7=资产层真为空 / misassign 0`）与浏览器回归（`l2d_sweep 269 | 失败 0 | 未启动 0 | 未生效 0`）下全绿。**同一个库两个工具给出相反结论 → 先怀疑判据，不是先怀疑数据。**

**三条失真实证**（从 `.diag/_refdiff_full.log` 的 `└` 说明行分类，类别有重叠）:
1. **「关键帧不一致」把参考版的重采样当成硬错误**。参考版是 60fps 采出来的（`fps_ref=60 / fps_ours=30`），我们写 Unity 原生关键帧时间 → 同一动作关键帧**集合**必然不同。实测 `siwanshi_3` 偏差中位 **0.0001**（几乎逐点相同）却仍被判 FAIL。28 个模型是"只有关键帧不一致"这一类。
2. **组→文件按 `files[0]` 盲配**。model3 的一个动作组可以登记多个文件，参考版登记顺序不保证一致 → 配错时报"关键帧不一致 66~150 条 + 时长不一致"（`abeikelongbi_3 main_2 关键帧不一致 150 条 + 时长不一致`、`aersasi_2 login 66 条 + 时长不一致`）。**这是配对错，不是数据错。**
3. **「曲线缺 1~3 条」113 个模型有**，这一类**待查**：量级远小于真正的漏读缺陷（`aerbien_3` 换入前是缺 **195** 条），疑似定值曲线的表达方式不同（我们把 `m_ConstantClip` 显式写成曲线，参考版可能不写），但**尚未取证**，别当结论用。

**判据应该怎么改**（下次要用它当闸门，先做这三条）:
- FAIL 只保留：**曲线缺失**（且已排除定值口径）、**同一 clip 配对成功下的时长不一致**、**偏差中位 >0.5**；`关键帧不一致` 降级为 INFO 并在比对前把两侧统一到同一时间格（或只比"我们的关键帧处取值是否等于参考在其时刻的插值"）。
- **配对先对齐**：按（时长 + 曲线数 + 曲线 Id 集合）在组内多个文件里挑同一个 clip，找不到就 SKIP 并说明，而不是拿 `files[0]` 硬比。
- 分批跑：`--only k1,k2,...`，别指望 `--all` 一次过 269 键的长尾网络。

**工具侧挂死**: `fetch()` 只有 `urlopen(timeout=25)`，连接被半开/慢滴时不触发 → 整轮无期限挂住（实测 25 分钟零输出）。已把「进程活着但日志连续 N 轮不增长 = HUNG」的检测加进 `scripts/diag/wait_for_detached.ps1 -StallRounds 2`（实测正确判出本次挂死），**不要再拿 `Wait-Process`/退出码判活**。

**已排除的假设**: ① 153 FAIL 不是本轮重导引入的回退——`antu_2` 重导产物与已人工验收并 PASS 的生产数据 **104/104 逐字节一致**，同一工具同一判据下它仍是 PASS；② 不是网络不通——206 个键里 26 个正常报"参考库无此模型"、180 个完成了比对。
