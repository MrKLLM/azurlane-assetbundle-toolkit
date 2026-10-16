# -*- coding: utf-8 -*-
"""l2d_step_origin_probe.py — 判「stepped 语义」能不能从 Unity 源侧自己推出来。只读。

背景：参考版（l2d.su 权威导出）把 `Param25`/`Param27` 这类"状态选择器"参数写成 **stepped**
（值保持到下一键再跳），而 `extract_motions.py` 一律写 **线性**。要离线修就得知道源侧有没有可判信号。

做法：把 Unity `m_StreamedClip` 每键的 **4 个 float 全解出来**（现有 `parse_streamed_clip` 只用了
其中 3 个，且代码与它自己的 docstring 对字段序号的说法不一致，所以这里不猜、逐个 field 试），
对每个 field 试一条最简单的规则：

    段 i（从键 i 到键 i+1）是 stepped  ⟺  key i 的该 field ≈ 0

再与参考版逐曲线的 stepped 段数对齐，报"完全命中曲线数"与"总误差段数"。
**能对齐的那一个 field，就是能在导出层直接写 type=2 的信号**；全都对不齐 ⇒ 必须外部参照。

用法: py -3 scripts/diag/l2d_step_origin_probe.py gezi_2 home
      py -3 scripts/diag/l2d_step_origin_probe.py gezi_2 home --ids Param25,Param27,Param9
"""
import argparse
import os
import struct
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, HERE)

import UnityPy
from UnityPy import config as upy_config

upy_config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
import paths as P
import extract_motions as X
import l2d_ref_diff as R

REF_POSE_EPS = 1e30
EPS = 1e-6
FIELDS = ("f1", "f2", "f3", "f4")


def parse_streamed_raw(sc):
    """→ [(time, [(idx, f1, f2, f3, f4), ...]), ...]；无护栏，靠缓冲区边界与 +inf 停止。"""
    data = list(getattr(sc, "data", None) or [])
    if not data:
        return []
    buf = b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in data)
    frames, pos = [], 0
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
            f1, f2, f3, f4 = struct.unpack_from("<4f", buf, pos + 4)
            pos += 20
            keys.append((idx, f1, f2, f3, f4))
        frames.append((t, keys))
    return frames


def ref_segtypes(c):
    """参考版曲线的段类型列表（按时间序），用于逐段对齐。"""
    sg = c["Segments"]
    out, i, n = [], 2, len(sg)
    while i < n:
        ty = sg[i]
        out.append(ty)
        i += 7 if ty == 1 else 3
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("clip")
    ap.add_argument("--ids", default="", help="逗号分隔，打印这些 Id 的逐段明细")
    a = ap.parse_args()

    bp = os.path.join(P.LIVE2D_SRC, a.key)
    if not os.path.isfile(bp):
        print("[FAIL] 源包不在盘上: %s" % bp)
        return 2
    env = UnityPy.load(bp)
    clip_obj = next((o for o in env.objects if o.type.name == "AnimationClip"
                     and getattr(o.read(), "m_Name", "") == a.clip), None)
    if clip_obj is None:
        print("[FAIL] 源包里没有 clip %s" % a.clip)
        return 2
    clip = clip_obj.read()
    # 打包形态：若 Unity 保留了**未压缩**的 m_FloatCurves，其 Keyframe 结构里带 tangentMode
    # （= 权威插值模式，能精确判 stepped，不必靠斜率启发式）。
    try:
        tt = clip_obj.read_typetree()
        keys = [k for k in tt.keys()]
        print("[*] clip typetree 顶层字段(%d): %s" % (len(keys), ", ".join(sorted(keys))))
        for probe in ("m_Compressed", "m_Legacy", "m_UseHighQualityCurve", "m_MuscleClipSize"):
            if probe in tt:
                print("    %-22s = %s" % (probe, tt[probe]))
        for arr in ("m_FloatCurves", "m_PositionCurves", "m_ScaleCurves", "m_EulerCurves",
                    "m_RotationCurves", "m_PPtrCurves"):
            v = tt.get(arr)
            if isinstance(v, list) and v:
                e0 = v[0]
                cur = e0.get("curve") if isinstance(e0, dict) else None
                kc = len(cur.get("m_Curve") or []) if isinstance(cur, dict) else None
                k0 = (cur.get("m_Curve") or [{}])[0] if isinstance(cur, dict) else {}
                print("    %-22s %d 条  首条 key=%d  首键字段=%s"
                      % (arr, len(v), kc if kc is not None else -1,
                         list(k0.keys()) if isinstance(k0, dict) else k0))
    except Exception as e:
        print("    [typetree 读取失败] %s: %s" % (type(e).__name__, e))
    targets, _ = X.build_binding_targets(clip, X.collect_go_name_hashes(env))
    frames = parse_streamed_raw(clip.m_MuscleClip.m_Clip.data.m_StreamedClip)
    src = {}
    for t, keys in frames:
        if t < -REF_POSE_EPS:
            continue
        for idx, f1, f2, f3, f4 in keys:
            src.setdefault(idx, []).append((t, f1, f2, f3, f4))

    ref = None
    for sub in R.REF_SUBDIRS:
        ref = R.fetch("%s/%s/%s/%s.motion3.json" % (R.BASE, a.key, sub, a.clip))
        if ref:
            break
    if not ref:
        print("[FAIL] 参考库没有 %s/%s（网络统计 %s）" % (a.key, a.clip, dict(R.STATS)))
        return 2
    refmap = {c["Id"]: ref_segtypes(c) for c in ref.get("Curves") or []}

    want = [x.strip() for x in a.ids.split(",") if x.strip()] if a.ids else None
    stats = {f: {"hit": 0, "err": 0, "curves": 0} for f in FIELDS}
    per_curve = {}
    for i, tg in enumerate(targets):
        if not tg or tg[0] != "Parameter":
            continue
        pid = tg[1]
        ks = sorted(src.get(i, []))
        rt = refmap.get(pid)
        if not ks or not rt:
            continue
        nseg = min(len(ks) - 1, len(rt))
        per_curve[pid] = (ks, rt[:nseg])
        for fi, fname in enumerate(FIELDS):
            pred = [2 if abs(k[1 + fi]) <= EPS else 0 for k in ks[:nseg]]
            err = fp = fn = 0
            for x, y in zip(pred, rt[:nseg]):
                if (x == 2) != (y == 2):
                    err += 1
                    if x == 2:
                        fp += 1
                    else:
                        fn += 1
            stats[fname]["curves"] += 1
            stats[fname]["err"] += err
            stats[fname]["fp"] = stats[fname].get("fp", 0) + fp
            stats[fname]["fn"] = stats[fname].get("fn", 0) + fn
            stats[fname]["hit"] += 1 if err == 0 else 0

    print("[*] 规则「段 i 是 stepped ⟺ key i 的该字段≈0」逐曲线对齐（参考版为真值）:")
    print("   %-5s %-14s %-12s %-10s %-10s" % ("字段", "完全命中曲线", "总误差段数", "误判为stepped", "漏判stepped"))
    for fname in FIELDS:
        s = stats[fname]
        print("   %-5s %-14s %-12s %-10s %-10s"
              % (fname, "%d/%d" % (s["hit"], s["curves"]), s["err"], s.get("fp", 0), s.get("fn", 0)))
    # 复合规则：多个字段组合
    z = lambda v: abs(v) <= EPS
    combo = {"f1&f2": lambda k: z(k[1]) and z(k[2]),
             "f1&f3": lambda k: z(k[1]) and z(k[3]),
             "f2&f3": lambda k: z(k[2]) and z(k[3]),
             "f1&f2&f3": lambda k: z(k[1]) and z(k[2]) and z(k[3]),
             "f3": lambda k: z(k[3])}
    for cname, fn in combo.items():
        hit = err = n = 0
        for pid, (ks, rt) in per_curve.items():
            pred = [2 if fn(k) else 0 for k in ks[:len(rt)]]
            e = sum(1 for p, y in zip(pred, rt) if (p == 2) != (y == 2))
            hit += 1 if e == 0 else 0
            err += e
            n += 1
        print("   %-5s %-14s %-12s" % (cname, "%d/%d" % (hit, n), err))

    for fname in ("f1", "f2"):
        fi = FIELDS.index(fname)
        bad = []
        for pid, (ks, rt) in per_curve.items():
            pred = [2 if abs(k[1 + fi]) <= EPS else 0 for k in ks[:len(rt)]]
            errs = [j for j, (p, y) in enumerate(zip(pred, rt)) if (p == 2) != (y == 2)]
            if errs:
                bad.append((pid, errs, ks, rt))
        print("   [%s] 不一致曲线 %d 条:" % (fname, len(bad)))
        for pid, errs, ks, rt in bad[:10]:
            det = "; ".join("t=%.3f [f1=%.3g f2=%.3g f3=%.3g val=%.3g] ref=%d"
                            % (ks[j][0], ks[j][1], ks[j][2], ks[j][3], ks[j][4], rt[j])
                            for j in errs[:3])
            print("      %-24s err %d/%d  %s" % (pid, len(errs), len(rt), det))

    if want:
        print("\n[*] 逐段明细（pred=按 f2 规则预测，ref=参考版；. = 一致，X = 不一致）:")
        for pid in want:
            if pid not in per_curve:
                print("   %-20s （未命中）" % pid)
                continue
            ks, rt = per_curve[pid]
            pred = [2 if abs(k[2]) <= EPS else 0 for k in ks]
            marks = "".join("." if (p == 2) == (y == 2) else "X" for p, y in zip(pred, rt))
            print("   %-20s 段数 %2d  pred_stepped %2d  ref_stepped %2d  %s"
                  % (pid, len(rt), sum(1 for p in pred if p == 2),
                     sum(1 for y in rt if y == 2), marks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
