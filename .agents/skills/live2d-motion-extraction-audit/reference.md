# reference — Live2D 动作提取完整性与保真审计

配合 [SKILL.md](SKILL.md) 使用。本文只放"照抄就能跑"的字节布局、代码骨架与实测数据表；方法论与判据在 SKILL.md。文中路径/环境变量一律用占位名，落到具体项目时替换。

## 1. Unity AnimationClip 三容器字节布局

入口链：`AnimationClip.m_MuscleClip.m_Clip.data` → 三个容器。

```
data.m_StreamedClip.data   : uint32[]   多键动画曲线（打包流）
data.m_DenseClip           : m_CurveCount, m_CurveCount 条等间隔曲线
data.m_ConstantClip.data   : float[]    每条一个定值
clip.m_ClipBindingConstant.genericBindings : 绑定表，顺序 [streamed][dense][constant]
```

### StreamedClip 帧流

小端，头部之后按帧循环：

```
偏移       内容
0          uint32[] 前导：哨兵 + curveCount（不同版本哨兵值不同，靠缓冲区边界容错更稳）
每帧:
  float    time            # 帧时间（秒）
  int32    numKeys         # 本帧键数
  每键 20 字节:
    int32  index           # 曲线索引（对齐 genericBindings 的 streamed 段）
    float  f1              # 入切线 inSlope
    float  f2              # 出切线 outSlope
    float  f3              # 未使用（常为 0；阶梯/线性切线模式下是垃圾值）
    float  f4              # 值 value
终止：time = +inf（0x7F800000）
特殊帧：time = -FLT_MAX ≈ -3.4e38 → Unity 参考姿态帧，一帧写完全部曲线的静止值
```

**参考姿态帧不是垃圾帧，绝不能当越界数据丢掉。** 大模型一帧可能有 380~520 个键；任何形如 `numKeys > 100` 的"防越界"护栏都会误杀它，导致整 clip 被判无数据。

无护栏解析骨架（靠缓冲区边界与 +inf 结束符停止）：

```python
import struct

def parse_streamed(buf):
    frames, pos = [], 0
    while pos + 8 <= len(buf):
        t = struct.unpack_from("<f", buf, pos)[0]; pos += 4
        n = struct.unpack_from("<i", buf, pos)[0]; pos += 4
        if n < 0 or pos + n * 20 > len(buf):
            break
        keys = []
        for _ in range(n):
            idx = struct.unpack_from("<i", buf, pos)[0]
            f1, f2, f3, f4 = struct.unpack_from("<4f", buf, pos + 4)
            pos += 20
            keys.append((idx, f4, f1, f2))   # (curve_index, value, inSlope, outSlope)
        frames.append((t, keys))
    return frames

REF_POSE_EPS = 1e30          # 判参考姿态帧：t < -REF_POSE_EPS
ref_pose = {i: v for t, ks in frames for i, v, _, _ in ks if t < -REF_POSE_EPS}
```

### 三容器 → 绑定表索引偏移与求和断言

```python
sc = clip.m_MuscleClip.m_Clip.data
n_stream = sc.m_StreamedClip.curveCount
n_dense  = sc.m_DenseClip.m_CurveCount
consts   = list(sc.m_ConstantClip.data or [])
gb       = list(clip.m_ClipBindingConstant.genericBindings)

assert n_stream + n_dense + len(consts) == len(gb), (
    f"{clip.m_Name}: 容器求和 {n_stream}+{n_dense}+{len(consts)} != 绑定 {len(gb)} → 有容器未读")

const_offset = n_stream + n_dense          # 定值曲线的绑定起始下标
```

绑定名解析（曲线索引 → 参数/部件名）：`genericBindings[i].path` 是 `crc32("<前缀>/<GameObject 名>")`，前缀 `Parameters/` → `Target: "Parameter"`，`Parts/` → `Target: "PartOpacity"`。注意 `CubismParameter` 组件的 `m_Name` 常为空，**真名挂在 GameObject 上**；`_unmanagedIndex` 才是 moc3 参数序号。别按位置猜名字。

## 2. 参数 (min, max, default) 表：无头 CDP 导出

用于第 2 步定值曲线判定和第 3 步量程核对。在已加载模型的页面上求值：

```js
(async () => {
  const core = /* 你的 internalModel.coreModel */;
  const ids = core._parameterIds || [];
  const out = {};
  for (let i = 0; i < core.getParameterCount(); i++) {
    const nm = (ids[i] && ids[i].string) || ids[i] || ("Param#" + i);
    out[nm] = [core.getParameterMinimumValue(i),
               core.getParameterMaximumValue(i),
               core.getParameterDefaultValue(i)];
  }
  return JSON.stringify({ count: core.getParameterCount(), ranges: out });
})()
```

判定：

```python
bad = [(cid, v) for cid, v in const_curves
       if abs(v - default_of(cid)) > 1e-6 and cid not in EXEMPT]
# EXEMPT 来自 MonoBehaviour 组件清单里的外部驱动组件（口型/眨眼/呼吸）
```

## 3. motion3.json 段格式与运行时直读语义

`Segments` 布局：首对 `(time, value)`，之后每段先一个类型码，`0=Linear`、`1=Bezier`、`2=Stepped`。

```
Linear/Stepped: [type, t, v]                 # 2 个后续值
Bezier:         [type, c1t, c1v, c2t, c2v, t, v]   # 6 个后续值
```

运行时解析器**按绝对 (时间, 值) 直读三个点，不做任何归一化还原**：

```js
case Bezier:
  points[a]   = new J(seg[l+1], seg[l+2])
  points[a+1] = new J(seg[l+3], seg[l+4])
  points[a+2] = new J(seg[l+5], seg[l+6])
```

**致命错法（真实事故）**：写归一化分数 `[1, 1/3, by1, 2/3, by2, t, v]`。运行时把控制点读成 `(t=0.333 秒, 值=0.667)`——对一个跨 7.5→8.983 秒的段，控制点落在区间之外且值接近 0，于是**每条贝塞尔都"先猛蹿到 ≈0 再跳到目标值"**。这是"部件各动各的"的最典型单点根因。

**规范写法**（Unity Hermite → 等价控制多边形，全部绝对坐标）：

```python
dt = t1 - t0
c1 = (t0 + dt / 3.0, v0 + out_slope * dt / 3.0)
c2 = (t1 - dt / 3.0, v1 - in_slope  * dt / 3.0)
segs += [1, c1[0], c1[1], c2[0], c2[1], t1, v1]
```

⚠️ 规范写法是**必要非充分**：密集键的切线字段当 Hermite 切线用会算出飞出的曲线。是否启用贝塞尔必须由第 4 步外部基准验收。

`Meta` 关键字段：`Duration`、`Fps`、`Loop`、`FadeInTime/FadeOutTime`（参考导出常**不写**，交给运行时默认：idle 2s／动作 0.5s；两侧都别硬写死）、`CurveCount`、`AreBeziersRestricted`（决定采样求值走朴素参数化还是解横向控制点）。`model3.json` 侧还常有 `Groups`（`EyeBlink`/`LipSync`）——缺了模型不眨眼、不做口型。

## 4. 字段布局锚点打分（第 3 步）

24 种字段排列全跑一遍，用**不可钻空子的锚点**排序：参考姿态帧字段值 vs 该曲线首键同字段值的一致率。

```python
CANDS = {  # 候选：把 4 个 float 里的哪一个当 value
    "f4": lambda f: f[3], "f3": lambda f: f[2],
    "f2": lambda f: f[1], "f1": lambda f: f[0],
}
for name, pick in CANDS.items():
    hit = sum(1 for idx in series
              if idx in ref_pose and series[idx]
              and abs(pick(ref_pose_key(idx)) - pick(series[idx][0])) < 1e-6)
    print(name, f"{hit}/{len(series)}")
# 实测：value 字段 98/98，其余斜率字段 46/98 量级 → 值字段唯一解
```

**不要**用这些当判据（都会被平凡命中或噪声主导）：

| 无效判据 | 为什么无效 |
|---|---|
| 重建曲线越出 `[min,max]` | Cubism 赋值时本就钳进合法量程，游戏侧同样越界；越界不证伪任何解释 |
| 密集 plateau 键上比差分导数与切线 | 1/60s 等值键 `dv≈0`，差分是噪声主导的垃圾数 |
| 某字段恒为 0 | 零字段能被任何候选解释平凡命中，是空判据 |

## 5. 外部权威基准比对器（第 4 步）

**找基准**：从参考查看器前端产物 grep 路径模板，反查静态目录规律：

```bash
# 页面 JS 里找 model3.json 模板，据此推出 motion 文件规律
curl -s <viewer>/assets/index-*.js | grep -o '[A-Za-z0-9_/.\-]*model3\.json' | sort -u
```

子目录候选枚举（我方常是 `motion/`，参考侧常是 `motions/`）：

```python
REF_SUBDIRS = ("motions", "motion")
```

**五级比对项实现要点**：

```python
# 1 组集合  set(ref.Motions) ^ set(ours)   —— 双向差集都要打印
# 2 曲线 Id  set((c.Target,c.Id)) 差集      —— 我方缺失 = 丢曲线（回 §1）
# 3 关键帧   逐条比 (time, value)，容差 1e-5；段总数也应相等（实测 1782 == 1782）
# 4 段类型   Counter(seg_type) 三方并排
# 5 采样偏差 按运行时语义求值后逐点比，报中位数 / >0.5 的曲线数 / 最甚值
```

实测对照表（某模型 `idle`，121 点采样，三种写法 vs 权威基准）：

| 写法 | 偏差中位 | 偏差>0.5 的曲线 | 最甚 |
|---|---|---|---|
| 归一化控制点（旧线上） | 1.376 | 92/98 | 9.35 |
| 绝对控制点·全贝塞尔 | 0 | **88/278** | **296** |
| **关键帧 + 线性（验收采用）** | 0 | 11/278 | 1.95 |

阈值校准依据：段类型不一致率实测落在 3.8%~9.6%，其中约 7% 是不可复原的贝塞尔控制点 → **WARN 线设 12%**（直觉的 5% 会把天花板误判成失败）。

## 6. 拆护栏 A/B 命令序列（第 5 步）

```bash
# 0) 基线：工作树干净，正式产物目录已有 N 个文件
# 1) 对照组（默认 env，必须复现现产出）
OUT_DIR=/tmp/l2d_ab/ctrl <extractor> --all
# 2) 实验组（打开待验证开关）
OUT_DIR=/tmp/l2d_ab/exp MOTION_BEZIER_CLIP=99 <extractor> --all
# 3) 红线闸门：对照组逐字节等于现产出，否则 A/B 作废
cd /tmp/l2d_ab/ctrl && find . -name '*.motion3.json' -exec sha256sum {} + > /tmp/ctrl.sha
cd <prod_dir>       && find . -name '*.motion3.json' -exec sha256sum {} + | sort > /tmp/prod.sha
diff <(sort /tmp/ctrl.sha | awk '{print $2, $1}') /tmp/prod.sha   # 必须无输出（实测 104/104 一致）
# 4) 实验组逐曲线采样偏差分布（用 §5 的求值器），报 P50/P90/max
```

开关命名约定（示例）：`MOTION_LINEAR`（强制线性）、`MOTION_ABSOLUTE_CP`（绝对坐标贝塞尔）、`MOTION_BEZIER_CLIP`（纵向裁剪阈值，默认保持旧值）、`MOTION_EMIT_CONST`（补定值曲线）。**默认值必须等于旧行为**；每个开关旁的注释要写明"哪个通过了验收、哪个只是实验"。

## 7. 实测数据表（一次完整审计该报的数字）

| 项 | 实测值 | 结论 |
|---|---|---|
| `idle` 绑定分布 | 98 streamed + 0 dense + 180 constant = 278 | 只读 streamed 丢 65% |
| 补定值后曲线总数 | 9441 → 29945 | 影响面是全模型级别 |
| 定值 == moc3 默认值 | 179/180 | 补入无损；1 条例外是口型 |
| 值字段锚点一致率 | 98/98 | 钉死字段布局 |
| 斜率字段锚点一致率 | 46/98 | 反证斜率不参与该锚点 |
| 段总数两侧对齐 | 1782 = 1782 | 差异纯在插值模式 |
| 阶梯段两端同值 | 1067/1070 | 补阶梯零收益 |
| 贝塞尔控制点候选拟合 | 最高 16.7%（平凡情形） | 判定为天花板 |
| 拆阈值护栏后偏差 | 63% 曲线 >0.15、最甚 205 | 收益为负 → 回退 |
| 对照组字节一致 | 104/104 sha256 | A/B 有效前提 |
| 静止态判定区在画布外 | 53/57 | "点了没反应"要先量几何，别改数据 |

## 8. 顺手记下的前端侧伴生坑

审计常顺带发现这些，属运行时侧（详见 `live2d-web-runtime-integration`），此处只留判定线索：

- 参考导出不写 `FadeInTime/FadeOutTime` → 我方硬写 0.5 会让"回落 idle 快 4 倍"，观感＝反应没收尾就被拽回去、像两个动作。库里 fade-in/fade-out 常**共用同一个 idle 默认值**，idle 曲线多时需要显式拆开（回落要柔、被打断要快）。
- `Meta.Loop` 可能被 display 层忽略（`setIsLoop()` 无调用点）→ 循环要靠本体设置，并配套关掉 loop 时的淡入重置。
- 整体位移参数若不在 `idle` 的绑定集里，clip 播完没有任何曲线写回 → 场景永久停在偏移位（游戏侧靠状态机复位）。候选修法：非 idle 动作前快照全参数，回落时把"idle 不驱动"的参数写回快照。
