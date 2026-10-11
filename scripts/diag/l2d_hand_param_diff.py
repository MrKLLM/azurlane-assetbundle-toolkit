#!/usr/bin/env python3
"""l2d_hand_param_diff.py —— 源 AnimationClip 的关键帧 vs 我们导出的 motion3，逐参数对账。

为什么需要它（§123 追加-XXIII）：用户报「手在换姿势时消失一下」，而冻帧反查给出两条否定——
画面上那只手的美术**全程亮着**、灭着的那 415 片里也没有第二套手长在那个位置。
⇒ 症状不在"显隐"这条轴上，而在**形变**这条轴上（这个模型的手指是画在美术片里的，
   moc3 中根本没有手指参数，只有 ParamHand*Angle / *Change / *Stretch / *Animation / *Display28）。
那么下一个必须排除的就是：**这些形变参数我们导出的值，和游戏源里的是不是同一套**。
本脚本就是这条对账：同一个 clip，源侧逐键 (t, c4) 与导出侧逐键 (t, v) 一比一，
报出 ① 键数是否一致 ② 值域是否一致 ③ 在源侧每个键时刻上导出值偏多少（最大偏差）。

⚠️ 三条读法上的坑（都踩过）：
  · 帧 0 是 time≈-3.4e38 的"参考姿态帧"，一帧合法写完全部曲线 —— 它不是动画键，必须按
    REF_POSE_EPS 滤掉，否则每个参数都会冒出"源侧多一帧、值域被撑大"的假差异。
  · 导出侧 seg_walk 只取每段的 (t, v) 端点，贝塞尔控制点不参与 —— 所以**段中点**的偏差量不到，
    本脚本判的是"键在不在、值对不对"，不是"曲线形状完全一致"。要在段中点比，用
    l2d_snap_criterion_scan.py 那套按段求值。
  · 时间基不一致会让所有参数一起报偏差（那是另一个 bug），所以先单独打印两侧的 t0/t1 总区间。

用法：
    py -3 scripts/diag/l2d_hand_param_diff.py gezi_2 home
    py -3 scripts/diag/l2d_hand_param_diff.py gezi_2 home --params ParamHandLChange,ParamHandRStretch
    py -3 scripts/diag/l2d_hand_param_diff.py gezi_2 home --all --top 25      # 全参数按偏差排序
"""
import argparse
import json
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
sys.path.insert(0, HERE)
from l2d_streamed_key_forensics import raw_keys, seg_walk, deref   # 同一把尺子，别另写一份


def src_keys_by_index(streamed):
    """源侧 m_StreamedClip → {curve_index: [(t, value)]}，滤掉参考姿态帧。"""
    out = {}
    for t, idx, _c1, _c2, _c3, c4 in raw_keys(streamed):
        if t < -X.REF_POSE_EPS:
            continue
        out.setdefault(idx, []).append((t, c4))
    for v in out.values():
        v.sort()
    return out


def sample(keys, t):
    """(t,v) 升序键表上按线性取值（端点外取端点值）。"""
    if not keys:
        return None
    if t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    lo, hi = 0, len(keys) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if keys[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    t0, v0 = keys[lo]
    t1, v1 = keys[hi]
    d = t1 - t0
    return v0 if d <= 0 else v0 + (v1 - v0) * (t - t0) / d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("clip")
    ap.add_argument("--params", default="", help="逗号分隔的参数名（默认只报 Hand/Finger/Arm 这一族）")
    ap.add_argument("--all", action="store_true", help="对账这个 clip 驱动的全部参数")
    ap.add_argument("--top", type=int, default=20, help="按最大偏差排序打印前 N 行")
    ap.add_argument("--eps", type=float, default=1e-4, help="|Δ| 超过它算不一致")
    a = ap.parse_args()

    bp = os.path.join(X.LIVE2D_SRC if hasattr(X, "LIVE2D_SRC") else X.LIVE2D_DIR, a.key)
    if not os.path.isfile(bp):
        print("[FAIL] 源包不在盘上：%s" % bp)
        return 2
    mp = os.path.join(ROOT, "Output", "Live2D", a.key, "motion", "%s.motion3.json" % a.clip)
    if not os.path.isfile(mp):
        print("[FAIL] 导出产物不在盘上：%s" % mp)
        return 2

    env = UnityPy.load(bp)
    clips = {}
    for o in env.objects:
        if o.type.name == "AnimationClip":
            c = o.read()
            clips[getattr(c, "m_Name", "")] = c
    if a.clip not in clips:
        print("[FAIL] 源包里没有 clip `%s`（有 %d 个：%s）" % (a.clip, len(clips), sorted(clips)[:12]))
        return 2
    names = X.collect_go_name_hashes(env)
    clip = clips[a.clip]
    cd = deref(clip.m_MuscleClip.m_Clip)
    targets, _un = X.build_binding_targets(clip, names)
    src = src_keys_by_index(cd.m_StreamedClip)

    exp = json.load(open(mp, encoding="utf-8"))
    ecur = {}
    for c in exp.get("Curves") or []:
        if c.get("Target") == "Parameter":
            keys, _kinds = seg_walk(c.get("Segments") or [])
            ecur[c.get("Id")] = keys

    s_ts = [t for ks in src.values() for t, _ in ks]
    e_ts = [t for ks in ecur.values() for t, _ in ks]
    print("clip %s ｜ 源侧 %d 条曲线有键 / 导出侧 %d 条有曲线" % (a.clip, len(src), len(ecur)))
    if s_ts and e_ts:
        print("时间基：源 %.3f~%.3f s   导出 %.3f~%.3f s   （两端差 >0.05s 就是另一类 bug，先修它再谈逐参数）"
              % (min(s_ts), max(s_ts), min(e_ts), max(e_ts)))

    want = [p for p in a.params.split(",") if p.strip()]
    fam = ("Hand", "Finger", "Yubi", "Arm", "Shoulder", "Te")
    rows = []
    for idx, tgt in enumerate(targets):
        # 解析不到的绑定可能是整项 None（不只是 (None, None)），别按二元组硬解
        tg, nm = tgt if (isinstance(tgt, (tuple, list)) and len(tgt) == 2) else (None, None)
        if tg != "Parameter" or not nm:
            continue
        if not a.all and not want and not any(k in nm for k in fam):
            continue
        if want and nm not in want:
            continue
        sk, ek = src.get(idx, []), ecur.get(nm, [])
        svals = [v for _t, v in sk]
        evals = [v for _t, v in ek]
        smov = (max(svals) - min(svals)) if len(svals) > 1 else 0.0
        emov = (max(evals) - min(evals)) if len(evals) > 1 else 0.0
        dmax, dat = 0.0, None
        for t, v in sk:
            e = sample(ek, t)
            if e is None:
                continue
            d = abs(e - v)
            if d > dmax:
                dmax, dat = d, t
        flag = []
        if not ek:
            flag.append("导出侧没有这条曲线")
        if sk and len(ek) < len(sk):
            flag.append("导出少 %d 个键" % (len(sk) - len(ek)))
        if smov > 1e-6 and emov <= 1e-6:
            flag.append("**源在动、导出是常量**")
        if dmax > a.eps:
            flag.append("值对不上")
        rows.append((dmax, nm, len(sk), len(ek), smov, emov, dat, "; ".join(flag)))

    rows.sort(reverse=True)
    print("\n最大偏差 |Δ| 排序（阈值 %.0e 算不一致），共 %d 条参数：" % (a.eps, len(rows)))
    print("  %-26s %8s %5s %5s %10s %10s %s" % ("参数", "最大Δ", "源键", "导键", "源动程", "导出动程", "备注"))
    for dmax, nm, ns, ne, smov, emov, dat, fl in rows[:a.top]:
        print("  %-26s %8.4f %5d %5d %10.3f %10.3f %s%s"
              % (nm, dmax, ns, ne, smov, emov, ("@%.2fs " % dat) if dat is not None else "", fl))
    bad = [r for r in rows if r[7]]
    print("\n⇒ %d/%d 条有异常标记；其中「源在动、导出是常量」%d 条"
          % (len(bad), len(rows), sum(1 for r in bad if "常量" in r[7])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
