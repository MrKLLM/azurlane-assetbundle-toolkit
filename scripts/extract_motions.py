#!/usr/bin/env python3
"""
extract_motions.py - 从 Unity AnimationClip 提取真实动作数据到 motion3.json

权威映射（2026-09-21 重新逆向确定，见 docs/TROUBLESHOOTING.md §17）:
    m_StreamedClip 的 curve index 与 AnimationClip.m_ClipBindingConstant.genericBindings
    **同序**；genericBindings[i].path = crc32("<前缀>/<GameObject 名>")，
    前缀 Parameters/ → Target=Parameter，Parts/ → Target=PartOpacity（部件可见性=官方换装拼接逻辑）。
    CubismParameter 组件的 m_Name 为空，真名挂在 GameObject 上；_unmanagedIndex 是 moc3 参数序号。

历史教训（本文件旧实现的两处致命错误）:
    1. 护栏 `num_keys > 100` 误杀帧 0。帧 0 是 time=-3.4e38 的“参考姿态帧”，一帧合法写完
       全部曲线（碧蓝大模型 200~800 参数 → 一帧 380~520 个 key），于是整条 clip 被判无数据，
       调用方静默保留 reconstruct 生成的 "Curves":[] 空壳 → 5037/8154 clip 是空壳。
    2. 用 env.objects 顺序 + 组件 m_Name 当参数名（实际为空）→ 回落成假 ID `Param_N`；
       旧产物另有一版按「curve idx == moc3 参数序号（从 0 连续）」取名，实测 0/8154 clip 满足
       dense 前提 → 3117 个“非空壳”文件的曲线名**全部错位**（眼睛数据写进眉毛参数等）。

用法:
    py -3 scripts/extract_motions.py --test lingbo          # 单模型（打印每条 clip 结果）
    py -3 scripts/extract_motions.py --all                  # 全量（写入 Output/Live2D）
    L2D_OUT_DIR=<目录> ... --all                             # 全量写到临时目录，不动正式产物
    L2D_MOTION_LINEAR=1 ...                                 # 强制线性插值（关闭贝塞尔）

退出码: 0 全部成功；1 存在“解出 0 条曲线”的 clip（绝不静默）。
"""

import os
import sys
import json
import struct
import binascii
import argparse
from datetime import datetime

try:
    import UnityPy
    from UnityPy import config
    config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
except ImportError:
    print("[ERROR] 需要安装 UnityPy: pip install UnityPy")
    sys.exit(2)

LIVE2D_DIR = r"D:\Azur Lane Assets\files\AssetBundles\live2d"
OUTPUT_DIR = os.environ.get("L2D_OUT_DIR") or r"D:\Azur Lane Assets\Output\Live2D"
ERROR_LOG = r"D:\Azur Lane Assets\docs\ERRORS.log"

USE_LINEAR = bool(os.environ.get("L2D_MOTION_LINEAR"))
# 贝塞尔控制点裁剪阈值（历史护栏，2026-09-23 定性：**它是在掩盖下面的格式错误，不是优化**）
#   旧实现把控制点写成归一化分数，运行时按绝对(时间,值)直读 → 每个贝塞尔都失控；
#   当时观察到"贝塞尔抖"，于是加这条 >3 拉直的护栏，误打误撞把大部分坏段降级成了线性。
#   现状：默认仍保持 3.0（保证既有产物逐字节不变，对照组实测 104/104 一致），
#   但**已验收的正确配方是 L2D_MOTION_LINEAR=1（关键帧+线性）**，见下面 ABSOLUTE_CP 的说明。
BEZIER_CLIP = float(os.environ.get("L2D_MOTION_BEZIER_CLIP", "3.0"))
# 绝对控制点开关：置 1 时按 Cubism 规范写**绝对 (时间,值)** 控制点并忽略上面的裁剪护栏。
# ⚠️ 格式上这才是对的写法，但**未通过权威基准验收**：安土实测它对参考版有 88/278 条曲线
#    偏差>0.5、最甚 296 个参数单位（Unity 密集键的切线本身就不该当 Hermite 切线用）。
#    已验收并换入的是 L2D_MOTION_LINEAR=1（关键帧+线性）。本开关仅留作后续实验。
ABSOLUTE_CP = bool(os.environ.get("L2D_MOTION_ABSOLUTE_CP"))
# 是否把 m_ConstantClip 里的「整段定值」曲线也导出（参考版 idle 曲线数 278 = 98 动画 + 180 定值）。
# 作用：切动作时这些参数会被显式拉回该 clip 的定值，而不是停在上一个动作留下的值上。
EMIT_CONST = bool(os.environ.get("L2D_MOTION_EMIT_CONST"))

PARAM_PREFIX = "Parameters/"
PART_PREFIX = "Parts/"

# Unity 参考姿态帧的时间是 -FLT_MAX（约 -3.4e38），不是真实时间
REF_POSE_EPS = 1e30


def log_warn(name, msg):
    try:
        os.makedirs(os.path.dirname(ERROR_LOG), exist_ok=True)
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] [MOTION] {name}: {msg}\n")
    except Exception:
        pass


def _crc(s):
    return binascii.crc32(s.encode("utf-8")) & 0xFFFFFFFF


# ============================================================
# genericBindings → 权威目标表
# ============================================================

def build_binding_targets(clip, go_names_by_pathid):
    """返回 [(Target, Id), ...]，下标即 m_StreamedClip 的 curve index。

    解析不到的绑定返回 (None, None) 并计数——这类目标（实测为某第三类属性哈希，
    疑 Drawable 颜色/透明度）Cubism Web 运行时无对应 motion target，跳过并记录。
    """
    targets = []
    unresolved = 0
    bc = getattr(clip, "m_ClipBindingConstant", None)
    gb = list(getattr(bc, "genericBindings", None) or []) if bc else []
    for b in gb:
        ph = getattr(b, "path", 0) & 0xFFFFFFFF
        nm = go_names_by_pathid.get(ph)
        if nm:
            targets.append(nm)
        else:
            targets.append(None)
            unresolved += 1
    return targets, unresolved


def collect_go_name_hashes(env):
    """GameObject 名 → 两种前缀的 crc32 路径哈希 → (Target, Id)。

    只认真的挂了 CubismParameter / CubismPart 组件的对象，避免与同名 Drawable/Transform 混淆。
    """
    go_pathid_to_name = {}
    for obj in env.objects:
        if obj.type.name == "GameObject":
            try:
                go_pathid_to_name[obj.path_id] = obj.read().m_Name
            except Exception:
                pass

    comp_go = {"CubismParameter": set(), "CubismPart": set()}
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            data = obj.read()
        except Exception:
            continue
        sr = getattr(data, "m_Script", None)
        if not sr:
            continue
        try:
            sname = getattr(sr.read(), "m_Name", "")
        except Exception:
            continue
        if sname not in comp_go:
            continue
        try:
            tt = obj.read_typetree()
        except Exception:
            continue
        goid = tt.get("m_GameObject", {}).get("m_PathID")
        nm = go_pathid_to_name.get(goid)
        if nm:
            comp_go[sname].add(nm)

    lookup = {}
    for nm in comp_go["CubismParameter"]:
        lookup[_crc(PARAM_PREFIX + nm)] = ("Parameter", nm)
    for nm in comp_go["CubismPart"]:
        lookup[_crc(PART_PREFIX + nm)] = ("PartOpacity", nm)
    return lookup


# ============================================================
# StreamedClip 解析（无护栏版）
# ============================================================

def parse_streamed_clip(streamed_clip):
    """解 m_StreamedClip.data → 帧列表。

    帧格式: time(f32) + numKeys(i32) + numKeys × [index(i32) + 4×f32]
    4 个 float 依次为 [unused, inSlope, outSlope, value]（对齐 AssetStudio 的
    Keyframe(time, value[3], value[1], value[2])）。
    终止符: time = +inf。缓冲区越界即停，**不设 numKeys 上限**。
    """
    data = getattr(streamed_clip, "data", None) or []
    if not data:
        return []
    buf = b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in data)

    frames = []
    pos = 0
    while pos + 8 <= len(buf):
        t = struct.unpack_from("<f", buf, pos)[0]
        pos += 4
        if t == float("inf"):
            break
        n = struct.unpack_from("<i", buf, pos)[0]
        pos += 4
        if n < 0 or pos + n * 20 > len(buf):
            break
        keys = []
        for _ in range(n):
            idx = struct.unpack_from("<i", buf, pos)[0]
            c1, c2, c3, c4 = struct.unpack_from("<4f", buf, pos + 4)
            pos += 20
            keys.append((idx, c4, c1, c2))  # (curve_index, value, inSlope, outSlope)
        frames.append((t, keys))
    return frames


def build_motion(clip, targets, verbose=False, const_info=None):
    """AnimationClip → motion3.json dict；解不出任何曲线返回 None（调用方必须报错）。

    const_info = (起始下标, 定值列表)：m_ConstantClip 里的「整段保持定值」曲线。
    参考实现（l2d.su 权威导出）把它们一并写入 motion3.json —— 它们不是惰性的：
    切动作时 Cubism 只对「本 clip 有曲线的」参数施加权重，缺曲线就**停在上一个
    动作留下的值上**，于是被 touch_* 动过的手臂等参数回不到静止位 → 部件互相错位。
    """
    muscle = getattr(clip, "m_MuscleClip", None)
    if not muscle or not getattr(muscle, "m_Clip", None):
        return None
    cdata = muscle.m_Clip.data
    streamed = getattr(cdata, "m_StreamedClip", None)
    frames = parse_streamed_clip(streamed) if streamed else []
    if not frames:
        return None

    base = {}     # curve idx -> 参考姿态值（帧 time=-FLT_MAX）
    series = {}   # curve idx -> [(t, value, inSlope, outSlope), ...]
    for t, keys in frames:
        if t < -REF_POSE_EPS:
            for idx, v, _i, _o in keys:
                base.setdefault(idx, v)
            continue
        tt = 0.0 if abs(t) < 1e-6 else t
        for idx, v, ins, outs in keys:
            series.setdefault(idx, []).append((tt, v, ins, outs))

    curves = []
    total_seg = total_pts = total_bezier = 0
    for idx in sorted(series.keys()):
        tgt = targets[idx] if idx < len(targets) else None
        if tgt is None:
            continue
        target, pid = tgt
        pts = sorted(series[idx], key=lambda x: x[0])
        if not pts:
            continue

        # 参考姿态值作为 t=0 起点（若真实关键帧未覆盖 t=0）
        if pts[0][0] > 1e-6 and idx in base:
            v0 = base[idx]
            pts.insert(0, (0.0, v0, pts[0][2], 0.0))

        segs = []
        n_pts = 1          # 曲线首对 (time,value) 也占一个 point 槽
        for i, (t, v, ins, outs) in enumerate(pts):
            if i == 0:
                segs.extend([t, v])
                continue
            t0, v0, _, outs0 = pts[i - 1]
            dt, dv = t - t0, v - v0
            if dt <= 1e-6:
                continue
            # dv≈0 时贝塞尔控制点会飞到天上（实测 by1=14.93），反而抖 → 退化成线性
            scale = max(1.0, abs(v0), abs(v))
            by1 = (outs0 * dt / 3.0) / dv if abs(dv) > 1e-3 * scale else None
            by2 = 1.0 - (ins * dt / 3.0) / dv if by1 is not None else None
            clipped = (not ABSOLUTE_CP) and BEZIER_CLIP > 0 and by1 is not None and max(abs(by1), abs(by2)) > BEZIER_CLIP
            if USE_LINEAR or by1 is None or clipped:
                # 线性: [type=0, time, value]
                segs.extend([0, t, v])
                total_seg += 1
                n_pts += 1
                continue
            # Unity 切线(值/秒) → Cubism 归一化贝塞尔控制点。
            # ⚠️ 官方段序（实测校验运行时 pixi-live2d-display 的解析器）：
            #    [type=1, 控制点1x, 控制点1y, 控制点2x, 控制点2y, 终点time, 终点value]
            #    运行时按 points[base+1..base+3] = (c1, c2, dest) 取 3 个点对、l+=7，
            #    并用 basePointIndex+3 定位下一段起点 → 终点必须在**最后**。
            #    多插一个"interpolation=0"或把终点写前面，都会整体错位并撑爆按
            #    TotalSegmentCount 预分配的 segments 数组（报 basePointIndex undefined）。
            # ⚠️⚠️ 段格式（2026-09-23 用 l2d.su 权威导出反查 + 运行时解析器源码双重证实）：
            #    Cubism motion3.json 的贝塞尔控制点是**绝对 (时间, 值)**，运行时
            #    `points[a]=new j(seg[l+1],seg[l+2])` 直读、不做任何归一化还原。
            #    旧实现写的是归一化分数（0.333/by1/0.667/by2），于是控制点被当成
            #    「t=0.333 秒、值=0.667」——落在段外且值接近 0，每条贝塞尔都先猛蹿到 0
            #    再跳到目标值 → 部件乱摆、互相不协调（用户报的「像刚学建模的人做的」）。
            #    正确写法 = Unity 三次 Hermite 的精确等价控制多边形：
            #        c1 = (t0 + dt/3, v0 + outSlope0*dt/3)
            #        c2 = (t1 - dt/3, v1 - inSlope1 *dt/3)
            if ABSOLUTE_CP:
                c1x = t0 + dt / 3.0
                c1y = v0 + outs0 * dt / 3.0
                c2x = t - dt / 3.0
                c2y = v - ins * dt / 3.0
                if not (-1e-6 <= (c1x - t0) <= dt + 1e-6 and -1e-6 <= (c2x - t0) <= dt + 1e-6):
                    segs.extend([0, t, v])   # 时间轴出格 → 退回线性（运行时要求 x 单调）
                    total_seg += 1
                    n_pts += 1
                    continue
                segs.extend([1, c1x, c1y, c2x, c2y, t, v])
                total_seg += 1
                n_pts += 3
                total_bezier += 1
                continue
            bx1 = min(0.999, max(0.001, 1.0 / 3.0))
            bx2 = min(0.999, max(0.001, 2.0 / 3.0))
            segs.extend([1, bx1, by1, bx2, by2, t, v])
            total_seg += 1
            n_pts += 3
            total_bezier += 1

        if len(segs) < 4:
            continue
        total_pts += n_pts
        curves.append({"Target": target, "Id": pid, "Segments": segs})

    if not curves:
        return None

    # 结构自检：按运行时的消费方式重放一遍（segments 是按 TotalSegmentCount 预分配的，
    # 少算一位就会在浏览器里炸成 "basePointIndex of undefined"，且只表现为"这个模型不动"）。
    o = a = 0
    for c in curves:
        segs = c["Segments"]
        l = 0
        while l < len(segs):
            if l == 0:
                o_seg_base, a = a, a + 1
                l += 2
            else:
                o_seg_base = a - 1
            typ = segs[l]
            if typ == 1:
                l += 7
                a += 3
            else:
                l += 3
                a += 1
            o += 1
        if o > total_seg or a > total_pts:
            raise ValueError(f"Meta 计数不足: segments {o}>{total_seg} points {a}>{total_pts} @ {c['Id']}")
    if o != total_seg or a != total_pts:
        raise ValueError(f"Meta 计数与曲线不符: {o}!={total_seg} / {a}!={total_pts}")

    real_t = [t for t, _ in frames if t >= -REF_POSE_EPS]
    duration = round(max(real_t) if real_t else 0.0, 3)
    if duration <= 0:
        st = getattr(muscle, "m_StartTime", 0.0) or 0.0
        sp = getattr(muscle, "m_StopTime", 0.0) or 0.0
        duration = round(sp - st, 3) if sp > st else 0.0

    # 定值曲线：整段保持该 clip 指定的值（1 段线性 = 2 点），让参数在切换动作时回到静止位
    n_const = 0
    if EMIT_CONST and const_info and duration > 0:
        ci, cvals = const_info
        for k, val in enumerate(cvals):
            gi = ci + k
            tgt = targets[gi] if gi < len(targets) else None
            if not tgt:
                continue
            target, pid = tgt
            curves.append({"Target": target, "Id": pid,
                           "Segments": [0.0, float(val), 0, duration, float(val)]})
            total_seg += 1
            total_pts += 2
            n_const += 1

    sample_rate = getattr(clip, "m_SampleRate", 0.0) or 30.0
    return {
        "Version": 3,
        "Meta": {
            "Duration": duration,
            "Fps": float(sample_rate),
            "Loop": bool(getattr(muscle, "m_LoopTime", False)),
            "AreBeziersRestricted": True,
            "CurveCount": len(curves),
            "TotalSegmentCount": total_seg,
            "TotalPointCount": total_pts,
            "UserDataCount": 0,
            "TotalUserDataSize": 0,
        },
        "Curves": curves,
        "UserData": [],
        "Physics": None,
    }


def process_model(model_name, verbose=False):
    """返回 (ok, 摘要, 失败 clip 列表)"""
    bundle_path = os.path.join(LIVE2D_DIR, model_name)
    if not os.path.isfile(bundle_path):
        bundle_path = os.path.join(LIVE2D_DIR, model_name + ".bundle")
    if not os.path.isfile(bundle_path):
        return False, "Bundle 文件不存在", []

    model_dir = os.path.join(OUTPUT_DIR, model_name)
    motion_dir = os.path.join(model_dir, "motion")

    try:
        env = UnityPy.load(bundle_path)
    except Exception as e:
        return False, f"加载失败: {e}", []

    targets_lookup = collect_go_name_hashes(env)

    clips = []
    for obj in env.objects:
        if obj.type.name == "AnimationClip":
            try:
                clips.append(obj.read())
            except Exception:
                pass
    if not clips:
        return False, "无 AnimationClip", []

    os.makedirs(motion_dir, exist_ok=True)
    ok = fail = 0
    failed = []
    skipped_targets = 0
    dense_curves = 0
    n_part = 0
    for clip in clips:
        name = getattr(clip, "m_Name", "")
        if not name:
            continue
        targets, unresolved = build_binding_targets(clip, targets_lookup)
        skipped_targets += unresolved
        # genericBindings 的分段顺序 = [streamed][dense][constant]（实测 98+0+180=278 且名字零冲突）
        const_info = None
        if EMIT_CONST:
            try:
                _cd = clip.m_MuscleClip.m_Clip.data
                _off = _cd.m_StreamedClip.curveCount + _cd.m_DenseClip.m_CurveCount
                _vals = list(_cd.m_ConstantClip.data or [])
                if _vals:
                    const_info = (_off, _vals)
                if _cd.m_DenseClip.m_CurveCount:
                    dense_curves += _cd.m_DenseClip.m_CurveCount
            except Exception:
                pass
        try:
            motion = build_motion(clip, targets, verbose=verbose, const_info=const_info)
        except Exception as e:
            motion = None
            detail = f"{type(e).__name__}: {e}"
            log_warn(f"{model_name}/{name}", f"build_motion 异常: {detail}")
            if verbose:
                print(f"    [!] {name}: build_motion 异常 {detail}")
        if not motion:
            fail += 1
            failed.append(name)
            log_warn(f"{model_name}/{name}", "解出 0 条曲线（不再写空壳占位文件）")
            continue
        n_part += sum(1 for c in motion["Curves"] if c["Target"] == "PartOpacity")
        with open(os.path.join(motion_dir, f"{name}.motion3.json"), "w", encoding="utf-8") as f:
            json.dump(motion, f, ensure_ascii=False)
        ok += 1
        if verbose:
            m = motion["Meta"]
            print(f"    {name:<22} curves={m['CurveCount']:<5} dur={m['Duration']:<8} loop={m['Loop']}")

    msg = f"成功 {ok} / 失败 {fail}" + (f" / PartOpacity曲线 {n_part}" if n_part else "")
    if dense_curves:
        msg += f" / ⚠️未导出的 dense 曲线 {dense_curves}"
    if skipped_targets:
        msg += f" / 跳过不可解析绑定 {skipped_targets}"
    return (fail == 0 and ok > 0), msg, failed


def main():
    ap = argparse.ArgumentParser(description="提取 Live2D 动作数据（权威 genericBindings 映射）")
    ap.add_argument("--name", help="指定模型名称")
    ap.add_argument("--test", help="单模型，打印每条 clip 明细")
    ap.add_argument("--all", action="store_true", help="处理全部模型")
    args = ap.parse_args()

    if not os.path.isdir(LIVE2D_DIR):
        print(f"[ERROR] Live2D 目录不存在: {LIVE2D_DIR}")
        return 2

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"[*] 输出目录: {OUTPUT_DIR}" + ("  (临时)" if os.environ.get("L2D_OUT_DIR") else ""))
    if USE_LINEAR:
        print("[*] L2D_MOTION_LINEAR=1 → 线性插值")
    if ABSOLUTE_CP:
        print("[*] L2D_MOTION_ABSOLUTE_CP=1 → 贝塞尔控制点写绝对(时间,值)【Cubism 规范】")
    if EMIT_CONST:
        print("[*] L2D_MOTION_EMIT_CONST=1 → 一并导出 m_ConstantClip 定值曲线")

    if args.test:
        models, verbose = [args.test], True
    elif args.name:
        models, verbose = [args.name], True
    elif args.all:
        models, verbose = sorted(os.listdir(LIVE2D_DIR)), False
    else:
        print(__doc__)
        return 2

    bad_models = []
    for m in models:
        if not os.path.isfile(os.path.join(LIVE2D_DIR, m)):
            continue
        ok, msg, failed = process_model(m, verbose=verbose)
        print(("  [+]" if ok else "  [-]") + f" {m:<24} {msg}")
        if not ok or failed:
            bad_models.append((m, failed))

    print("\n" + "=" * 46)
    if bad_models:
        print(f"[!] {len(bad_models)} 个模型存在解不出的 clip:")
        for m, fl in bad_models[:20]:
            print(f"    {m}: {fl}")
        return 1
    print("[+] 全部 clip 均解出非空曲线")
    return 0


if __name__ == "__main__":
    sys.exit(main())
