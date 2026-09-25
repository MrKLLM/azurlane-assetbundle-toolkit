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
