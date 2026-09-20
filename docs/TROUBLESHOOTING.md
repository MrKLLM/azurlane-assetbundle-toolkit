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

## 9. Motion extraction quality issues

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

## 10. StreamedClip binary format not fully reverse-engineered

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

**Status**: Needs further research
**Reference**: AssetStudio source code at github.com/Perfare/AssetStudio
**Files**: scripts/extract_motions.py

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
