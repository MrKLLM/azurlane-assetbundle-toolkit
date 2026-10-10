# -*- coding: utf-8 -*-
"""l2d_streamed_key_forensics.py — 源包 `m_StreamedClip` 的**逐键四列**取证：判「阶梯键被我们导出成斜坡」这条嫌疑。

为什么要它（§6.37 交接项 C）：磁盘上 `home` 的 `Param25` 有三段 0.6→0 的过渡（333/584/333ms），
每键的两列斜率都是 0。这句有两种截然不同的落法：
  (a) 源数据本来就是真实插值 ⇒ 游戏也要经过「半透明手」那一段 ⇒ 我们的闪烁不是导出层造成的；
  (b) 源数据是**阶梯**，只是被我们的导出压成了插值 ⇒ 游戏从不落进中间值 ⇒ 是我们的 bug。
阶梯在 Unity 侧可能的落法，本脚本逐条扫（S1~S3），再对账我们有没有跳键（S4）：
  S1 **重复键**：同一时刻写两条不同值的键（多数引擎表示 step 的通用做法）。
  S2 **哨兵切线**：`CalcHermiteStationaryInfTangents` 那条路线 —— 阶梯键把 in/out 切线写成 ±inf / ±FLT_MAX。
  S3 **被丢弃的那一列是位掩码**：每键 4 个 float，生产解析器只用 值 + 两列切线，第 3 列丢掉；
     若它是 `tangentMode`，取值应是一小撮整数。
外加 S4：**我们有没有跳键**（`extract_motions.build_motion` 的 `dt<=1e-6` 会跳掉同刻键）——
   源侧真实键数（去掉参考姿态帧 t=-FLT_MAX）与磁盘键时刻逐一对齐。
四条全为否 ⇒ 源数据里根本没有阶梯的痕迹，(b) 判死。

⚠️ 段格式按**运行时真正的解码规则**读（`pixi-live2d-display` 的 `CubismMotionSegmentType`）：
   平铺为 `t0,v0, TYPE, [贝塞尔再 4 个控制浮点], t1,v1, TYPE, …`，type 在**每对 (时间,值) 之后**；
   `0=线性 1=贝塞尔 2=阶梯 3=反向阶梯`（运行时对 2 用 `points[0].value` 求值 ⇒ 表达阶梯是可行的）。
   ⚠️ `l2d_snap_criterion_scan.parse_segments` 把「带 4 个额外浮点」的条件写成 `ty in (2,3)` ——
   运行时里 2/3 是阶梯（只跟 1 对），贝塞尔才是 1（跟 3 对）。当前产物清一色 type=0 所以没暴露，
   本脚本用的是修正后的规则，别再照抄那一条。

只读：不写任何产物、不改前端。

用法: py -3 scripts/diag/l2d_streamed_key_forensics.py gezi_2 home
      py -3 scripts/diag/l2d_streamed_key_forensics.py gezi_2 home --params Param25,ParamBodyAngleX
      py -3 scripts/diag/l2d_streamed_key_forensics.py gezi_2 home idle main_1 --allclips-stats
输出: stdout（中文报告，无落盘）
"""
import argparse
import json
import math
import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import UnityPy
from UnityPy import config as upy_config

upy_config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
import extract_motions as X

FLT_MAX = 3.4028235e38
COLS = ("c1", "c2", "c3", "c4")


def deref(x):
    return x.data if hasattr(x, "data") else x


def raw_keys(streamed):
    """按生产解析器同一条 20 字节键步长走一遍，但**保留四列**：[(t, idx, c1, c2, c3, c4)]。"""
    data = getattr(streamed, "data", None) or []
    if not data:
        return []
    buf = b"".join(struct.pack("<I", int(v) & 0xFFFFFFFF) for v in data)
    out, pos = [], 0
    while pos + 8 <= len(buf):
        t = struct.unpack_from("<f", buf, pos)[0]
        pos += 4
        if t == float("inf"):
            break
        n = struct.unpack_from("<i", buf, pos)[0]
        pos += 4
        if n < 0 or pos + n * 20 > len(buf):
            break
        for _ in range(n):
            idx = struct.unpack_from("<i", buf, pos)[0]
            c1, c2, c3, c4 = struct.unpack_from("<4f", buf, pos + 4)
            pos += 20
            out.append((t, idx, c1, c2, c3, c4))
    return out


def seg_walk(seg):
    """motion3.json 的 Segments → ([(t,v)…], {段类型: 个数})，按运行时解码规则：
    平铺为 `t0,v0, TYPE, [贝塞尔再 4 个控制浮点], t1,v1, TYPE, …`（线性/阶梯只跟一对）。"""
    keys, kinds, i, n = [], {}, 0, len(seg)
    while i + 1 < n:
        keys.append((seg[i], seg[i + 1]))
        i += 2
        if i >= n:
            break
        ty = int(seg[i])
        kinds[ty] = kinds.get(ty, 0) + 1
        i += 1 + (4 if ty == 1 else 0)
    return keys, kinds


def col_stats(all_keys):
    st = {c: dict(n=0, zero=0, nan=0, inf=0, huge=0, sentinel=0, mx=0.0, distinct=set()) for c in COLS}
    for row in all_keys:
        for j, c in enumerate(COLS):
            v = row[2 + j]
            s = st[c]
            s["n"] += 1
            if math.isnan(v):
                s["nan"] += 1
                continue
            if math.isinf(v):
                s["inf"] += 1
                continue
            if abs(v) > 1e20:
                s["huge"] += 1
            if abs(v) > 1e30:
                s["sentinel"] += 1
            if abs(v) < 1e-9:
                s["zero"] += 1
            if abs(v) > s["mx"]:
                s["mx"] = v
            s["distinct"].add(round(v, 6))
    return st


def step_trace(real):
    """S1 同刻不同值重复键：返回 (涉及曲线数, 键对数, 例子)。"""
    byc = {}
    for r in real:
        byc.setdefault(r[1], []).append(r)
    curves, pairs, ex = 0, 0, []
    for idx, rows in byc.items():
        rows.sort()
        d = 0
        for a, b in zip(rows, rows[1:]):
            if abs(b[0] - a[0]) <= 1e-6 and abs(b[5] - a[5]) > 1e-4:
                d += 1
                if len(ex) < 5:
                    ex.append((idx, round(a[0], 4), a[5], b[5]))
        if d:
            curves += 1
            pairs += d
    return curves, pairs, ex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("clips", nargs="*")
    ap.add_argument("--params", default="", help="逗号分隔的参数名，逐键摊开四列")
    ap.add_argument("--allclips-stats", action="store_true", help="S1/S2/S3 扫这个模型的**全部** clip")
    a = ap.parse_args()
    want = [p for p in a.params.split(",") if p]

    src = getattr(X, "LIVE2D_SRC", None) or X.LIVE2D_DIR
    bp = os.path.join(src, a.key)
    if not os.path.isfile(bp):
        print("[FAIL] 源包不在盘上: %s" % bp)
        return 2
    env = UnityPy.load(bp)
    clips = {}
    for o in env.objects:
        if o.type.name == "AnimationClip":
            c = o.read()
            clips[getattr(c, "m_Name", "")] = c
    names = X.collect_go_name_hashes(env)
    scan = sorted(clips) if a.allclips_stats else None
    print("源包 %s  AnimationClip %d 个%s" % (os.path.basename(bp), len(clips),
          ("（统计扫全部）" if scan else "")))

    # —— 全局 S1/S2/S3
    pool, dup_by_clip = [], {}
    for cn in (scan or a.clips):
        clip = clips.get(cn)
        if clip is None:
            print("[SKIP] 没有 clip `%s`" % cn)
            continue
        ks = raw_keys(deref(clip.m_MuscleClip.m_Clip).m_StreamedClip)
        real = [k for k in ks if k[0] >= -X.REF_POSE_EPS]
        pool += real
        dup_by_clip[cn] = step_trace(real)
    dupc = sum(v[1] for v in dup_by_clip.values())
    print("\nS1 同一时刻两条不同值的键（阶梯的通用编码）: 全扫描 %d 处，逐 clip %s"
          % (dupc, {k: v[1] for k, v in list(dup_by_clip.items())[:8]}))
    st = col_stats(pool)
    for c in COLS:
        s = st[c]
        if not s["n"]:
            continue
        print("S2/S3 [%s] 键 %d  零 %.1f%%  NaN %d  Inf %d  |v|>1e20 %d  |v|>1e30 %d  有限值绝对最大 %.4g  不同取值 %d"
              % (c, s["n"], 100.0 * s["zero"] / s["n"], s["nan"], s["inf"], s["huge"], s["sentinel"], s["mx"],
                 len(s["distinct"])))
    print("   （c4 = 生产解析器当「值」用的那一列，c3 = 我们丢掉的那一列；c1/c2 = 两列切线）")
    c3 = st["c3"]
    looks_bitfield = c3["n"] and len(c3["distinct"]) < 64 and all(abs(v - round(v)) < 1e-6 for v in c3["distinct"])
    print("   ⇒ 第 3 列%s是位掩码/tangentMode" % ("" if looks_bitfield else " 不"))

    # —— 逐 clip：S4 跳键对账 + 指定参数逐键
    for cn in a.clips:
        clip = clips.get(cn)
        if clip is None:
            continue
        cd = deref(clip.m_MuscleClip.m_Clip)
        stt = cd.m_StreamedClip
        targets, _u = X.build_binding_targets(clip, names)
        ks = raw_keys(stt)
        real = [k for k in ks if k[0] >= -X.REF_POSE_EPS]
        ref = [k for k in ks if k[0] < -X.REF_POSE_EPS]
        byc = {}
        for r in real:
            byc.setdefault(r[1], []).append(r)
        dupc_, _, ex_ = step_trace(real)
        const_n = len(list(cd.m_ConstantClip.data or []))
        print("\n== clip `%s`  streamed.curveCount=%s dense=%s constant=%d 项  键 %d（参考帧 %d / 真实 %d）"
              % (cn, stt.curveCount, getattr(cd.m_DenseClip, "m_CurveCount", 0), const_n, len(ks), len(ref), len(real)))
        print("   S1 本 clip 同刻重复键 %d 处 %s" % (dupc_, ("例: %s" % ex_[:3] if ex_ else "")))

        for p in want:
            gi = next((i for i, tg in enumerate(targets) if tg and tg[1] == p), None)
            if gi is None:
                print("   [WARN] 绑定表里没有 %s" % p)
                continue
            rows = sorted(byc.get(gi, []), key=lambda r: r[0])
            fp = os.path.join(ROOT, "Output", "Live2D", a.key, "motion", "%s.motion3.json" % cn)
            seg = None
            if os.path.isfile(fp):
                for cc in json.load(open(fp, encoding="utf-8")).get("Curves", []):
                    if cc.get("Target") == "Parameter" and cc.get("Id") == p:
                        seg = cc["Segments"]
            print("   —— %s  曲线 idx=%d  源侧真实键 %d 个  斜率两列全为 0 的键 %d/%d"
                  % (p, gi, len(rows), sum(1 for r in rows if abs(r[2]) < 1e-6 and abs(r[3]) < 1e-6), len(rows)))
            print("      %-9s %-10s %-10s %-10s %-10s %s" % ("time", "c1(inS)", "c2(outS)", "c3(丢)", "c4(值)", "与上一键"))
            prev = None
            for t, idx, c1, c2, c3v, c4 in rows:
                note = ""
                if prev is not None:
                    dt, dv = t - prev[0], c4 - prev[5]
                    note = "dt=%+.3f dv=%+.3f" % (dt, dv)
                    if abs(dt) <= 1e-6:
                        note += "  ← 同刻（生产解析器会跳键）"
                    elif abs(dv) > 1e-4 and abs(c1) < 1e-6 and abs(c2) < 1e-6:
                        note += "  ← 真实过渡段，两列斜率均为 0"
                print("      %-9.4f %-10.4f %-10.4f %-10.4f %-10.4f %s" % (t, c1, c2, c3v, c4, note))
                prev = (t, idx, c1, c2, c3v, c4)
            if seg is None:
                print("      磁盘: 无这条曲线")
                continue
            dkeys, kinds = seg_walk(seg)
            st_ = {round(r[0], 4) for r in rows}
            dt_ = {round(x[0], 4) for x in dkeys}
            print("      磁盘: 键 %d 个，段类型 %s；时刻集合差 %s"
                  % (len(dkeys), kinds, sorted(st_ ^ dt_)[:8] or "无（S4 没跳键、也没多键）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
