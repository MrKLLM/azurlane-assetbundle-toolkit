# -*- coding: utf-8 -*-
"""l2d_source_curve_dump.py — 从**源包 AnimationClip** 直接取指定参数的曲线，与磁盘
`Output/Live2D/<key>/motion/<clip>.motion3.json` 逐键比对。只读，不改任何产物。

为什么要它：`l2d_motion_audit.py` 的 `curves auth=` **只数了 `m_StreamedClip` 一个容器**，
它给的 `ok / misassign 0` 只覆盖 streamed 部分曲线的**名字**，既不覆盖 dense/constant 的名字，
也不覆盖任何曲线的**取值**。要判"磁盘上 `Param25` 这条 0.5 起点是不是源包那条"，必须绕开审计器，
直接从源包取。

三道断言，缺一不能结案：
  A **名字↔索引**：每个 `CubismParameter` 组件的 GameObject 名（我们拿它当曲线 Id）
    必须等于 moc3 参数表里 `_unmanagedIndex` 位置上的名字。不等 ⇒ Id 与 moc3 错位（错绑的一种）。
  B **绑定数求和**：`len(genericBindings) == streamed.curveCount + dense.m_CurveCount + constant 曲线数`
    （§23 实测分段序 = [streamed][dense][constant]）。不等 ⇒ 位置映射不成立，磁盘曲线名整体可疑。
  C **逐键取值**：源侧曲线（按时间线性插值）与磁盘 `Segments` 的键值逐点比，报最大偏差。

用法: py -3 scripts/diag/l2d_source_curve_dump.py gezi_2 home Param25,Param27,Param17,l2d_hx
      py -3 scripts/diag/l2d_source_curve_dump.py gezi_2 home Param25 --meta .diag/_param_meta_gezi_2.json
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, HERE)

import UnityPy
from UnityPy import config as upy_config

upy_config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
import extract_motions as X    # 复用它的三容器解析与 genericBindings 反查，不自己推导格式


def deref(x):
    return x.data if hasattr(x, "data") else x


def seg_keys(seg):
    """motion3.json 的 Segments → [(t, v)]。步长：[t,v,type]，type∈{2,3} 再跟 4 个控制点，
    最后一个键只有 (t,v)。与 scripts/diag/l2d_curve_shape.py 同一条规则。"""
    out, i = [], 0
    while i + 1 < len(seg):
        t = seg[i + 2] if i + 2 < len(seg) else None
        out.append((seg[i], seg[i + 1]))
        if t in (2, 3):
            i += 5
        elif t is None:
            i += 2
        else:
            i += 3
    return out


def interp(keys, t):
    if not keys:
        return None
    if t <= keys[0][0]:
        return keys[0][1]
    for a, b in zip(keys, keys[1:]):
        if a[0] <= t <= b[0]:
            d = b[0] - a[0]
            return a[1] if d <= 0 else a[1] + (b[1] - a[1]) * (t - a[0]) / d
    return keys[-1][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("clip")
    ap.add_argument("params", help="逗号分隔的参数名")
    ap.add_argument("--meta", default="", help="moc3 参数序列表（运行时 dump，用于断言 A）")
    ap.add_argument("--allnames", action="store_true", help="打印该 clip 全部绑定名（核对用）")
    ap.add_argument("--keys", action="store_true",
                    help="把源侧与磁盘的键**并排列出**（断言 C 只在磁盘键时刻采样，"
                         "源侧多出来的键——Unity 表示瞬切用的同刻双键——它看不见）")
    a = ap.parse_args()
    want = [p for p in a.params.split(",") if p]

    bp = os.path.join(X.LIVE2D_DIR, a.key)
    if not os.path.isfile(bp):
        print("[FAIL] 源包不在盘上: %s" % bp)
        return 2
    env = UnityPy.load(bp)

    goname = {}
    for o in env.objects:
        if o.type.name == "GameObject":
            try:
                goname[o.path_id] = o.read().m_Name
            except Exception:
                pass
    # —— 断言 A：CubismParameter 的 GameObject 名 vs moc3 表里 _unmanagedIndex 位置上的名字
    comp = []
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            d = o.read()
            sr = getattr(d, "m_Script", None)
            if not sr or getattr(sr.read(), "m_Name", "") != "CubismParameter":
                continue
            tt = o.read_typetree()
            gname = goname.get(tt.get("m_GameObject", {}).get("m_PathID"))
            comp.append((gname, tt.get("_unmanagedIndex")))
        except Exception:
            continue
    mp = a.meta or os.path.join(ROOT, ".diag", "_param_meta_%s.json" % a.key)
    moc3_order = None
    if os.path.isfile(mp):
        moc3_order = list(json.load(open(mp, encoding="utf-8")).get("meta", {}).keys())
    print("断言 A（名字↔moc3 索引）: 组件 %d 个, moc3 序列表 %s"
          % (len(comp), "无（跳过）" if not moc3_order else "%d 个" % len(moc3_order)))
    if moc3_order:
        bad = [(g, ix, moc3_order[ix] if ix is not None and 0 <= ix < len(moc3_order) else "?")
               for g, ix in comp
               if ix is None or ix >= len(moc3_order) or moc3_order[ix] != g]
        print("   %s 不一致 %d 个%s" % ("✅" if not bad else "❌", len(bad),
                                        "" if not bad else " 例: %s" % bad[:5]))

    clips = [o.read() for o in env.objects if o.type.name == "AnimationClip"]
    clip = next((c for c in clips if getattr(c, "m_Name", "") == a.clip), None)
    if clip is None:
        print("[FAIL] 源包里没有名为 %s 的 AnimationClip（现有 %d 个）" % (a.clip, len(clips)))
        return 2
    cd = clip.m_MuscleClip.m_Clip.data
    st, dn, ct = cd.m_StreamedClip, cd.m_DenseClip, cd.m_ConstantClip
    n_gb = len(list(getattr(clip.m_ClipBindingConstant, "genericBindings", []) or []))
    n_const = len(list(ct.data or []))
    print("\n断言 B（绑定数求和）: genericBindings=%d  streamed.curveCount=%s  dense.m_CurveCount=%s  "
          "constant.data=%d 项" % (n_gb, st.curveCount, dn.m_CurveCount, n_const))
    print("   [streamed][dense][constant] 分段序下，constant 段应占 %d 项 ⇒ 三段合计 %s vs 绑定 %d"
          % (n_const, "%s+%s+%d" % (st.curveCount, dn.m_CurveCount, n_const), n_gb))
    if dn.m_CurveCount:
        print("   ⚠️ dense 容器非空（%s 条）：本脚本只解 streamed+constant，dense 未比对" % dn.m_CurveCount)

    targets, unres = X.build_binding_targets(clip, X.collect_go_name_hashes(env))
    off_c = (st.curveCount or 0) + (dn.m_CurveCount or 0)
    frames = X.parse_streamed_clip(st)
    series = {}
    tans = {}          # 切线：断言 C 只在键时刻采样 ⇒ 端点值相同、形状不同（陡切 vs 线性）它看不见
    for t, keys in frames:
        for idx, val, i_t, o_t in keys:
            series.setdefault(idx, []).append((t, val))
            tans.setdefault(idx, []).append((t, val, i_t, o_t))
    if a.allnames:
        print("\n绑定名清单（下标=curve index）:")
        for i, tg in enumerate(targets):
            print("   %-4d %s" % (i, tg[1] if tg else None))

    fp = os.path.join(ROOT, "Output", "Live2D", a.key, "motion", "%s.motion3.json" % a.clip)
    disk = {c["Id"]: c for c in json.load(open(fp, encoding="utf-8")).get("Curves", [])
            if c.get("Target") == "Parameter"}
    print("\n断言 C（逐键取值）: 磁盘 %s 条参数曲线" % len(disk))
    for p in want:
        gi = next((i for i, tg in enumerate(targets) if tg and tg[1] == p), None)
        src = None
        tsrc = []
        where = None
        if gi is not None and gi in series:
            src = sorted(series[gi])
            tsrc = sorted(tans.get(gi, []))
            where = "streamed[%d]" % gi
        elif gi is not None and gi >= off_c and (gi - off_c) < n_const:
            v = float(list(ct.data)[gi - off_c])
            src = [(0.0, v)]
            where = "constant[%d]" % (gi - off_c)
        elif gi is not None and off_c <= gi < off_c + n_const:
            v = float(list(ct.data)[gi - off_c])
            src = [(0.0, v)]
            where = "constant[%d]" % (gi - off_c)
        d = disk.get(p)
        dk = seg_keys(d["Segments"]) if d else None
        if src is None:
            print("   %-14s 源侧: 绑定 %s 未取到曲线; 磁盘: %s"
                  % (p, ("idx %d" % gi) if gi is not None else "无此名",
                     "无此曲线" if not dk else "有 %d 键" % len(dk)))
            continue
        if dk is None:
            print("   %-14s 源侧 %s 有曲线（%d 键），磁盘上没有这条 ⇒ 漏导出" % (p, where, len(src)))
            continue
        diffs = [(t, v, interp(src, t)) for t, v in dk]
        bad = [x for x in diffs if x[2] is None or abs(x[1] - x[2]) > 1e-4]
        mx = max((abs(x[1] - x[2]) for x in diffs if x[2] is not None), default=0.0)
        print("   %-14s 源侧 %-13s %d 键 (v0=%.4f, %.3f..%.3f) | 磁盘 %d 键 (v0=%.4f, %.3f..%.3f) "
              "⇒ 最大偏差 %.5f，超阈值键 %d/%d %s"
              % (p, where, len(src), src[0][1], min(v for _, v in src), max(v for _, v in src),
                 len(dk), dk[0][1], min(v for _, v in dk), max(v for _, v in dk),
                 mx, len(bad), len(diffs), "✅" if not bad else "❌"))
        if bad:
            for t, dv, sv in bad[:6]:
                print("       t=%-8.3f 磁盘 %-9s 源 %-9s" % (t, round(dv, 4), "None" if sv is None else round(sv, 4)))
        if a.keys:
            raw = d["Segments"]
            tk, j = [], 0
            while j + 1 < len(raw):
                ty = raw[j + 2] if j + 2 < len(raw) else None
                tk.append((raw[j], raw[j + 1], ty))
                j += 5 if ty in (2, 3) else (2 if ty is None else 3)
            print("       键并排（源 %d 键 / 磁盘 %d 键；磁盘段类型 0=线性 2/3=贝塞尔）"
                  % (len(src), len(dk)))
            print("       源侧切线 = in/out（Unity 的 dv/dt）；陡度 = |out 切线| ÷ 到下一键的平均斜率")
            for i in range(len(src)):
                t, v = src[i]
                it = tans_i = None
                if i < len(tsrc):
                    _, _, it, tans_i = tsrc[i]
                avg = None
                if i + 1 < len(src) and src[i + 1][0] > t:
                    avg = (src[i + 1][1] - v) / (src[i + 1][0] - t)
                k = next((x for x in tk if abs(x[0] - t) < 1e-4), None)
                steep = ""
                if avg not in (None, 0) and tans_i is not None:
                    steep = "  陡度=%.1f" % (abs(tans_i) / abs(avg))
                print("       #%02d 源 t=%8.3f v=%6.3f  in=%-10.3g out=%-10.3g%s   磁盘[%s]"
                      % (i, t, v, -3.4e38 if it is None else it,
                         -3.4e38 if tans_i is None else tans_i, steep,
                         "t=%.3f v=%.3f 类型=%s" % k if k else "无对应键"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
