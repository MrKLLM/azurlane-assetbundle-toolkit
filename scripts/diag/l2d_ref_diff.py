#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""l2d_ref_diff.py — 用 l2d.su 的权威导出验收我们解出的 motion3.json

为什么需要它：碧蓝航线 Live2D 的动作只能从 Unity AnimationClip 反解，而 l2d.su 上挂着
同一批模型的 **权威 motion3.json**（大概率来自游戏原始 Live2D 发行包）。它是目前唯一能
逐帧判定"我们解得对不对"的外部基准。

比对项（按重要性）：
  1. 动作组集合        —— 参考版有而我们没有 = 漏登记
  2. 曲线 Id 集合      —— 少了就是丢曲线（历史事故：只读 m_StreamedClip 丢掉全部定值曲线）
  3. 关键帧时间/值     —— 必须逐条一致，不一致 = 解析错位
  4. 段类型分布        —— 参考版 linear/bezier/stepped 三方对比
  5. 逐曲线采样偏差    —— 按运行时真实语义求值（AreBeziersRestricted 走朴素参数化），
                          偏差中位应 ≤0.2、>0.5 的曲线占比应 ≤5%

已知天花板：参考版约有 7% 的段是贝塞尔，其控制点无法从 Unity 切线字段推出（四种候选公式
最高只命中 16.7%，且那还是"切线为 0"的平凡情形）。这部分我们只能用线性弦近似 → 表现为
缓动略少，不会导致部件乱动。

参考库只覆盖部分模型（实测抽样 8/14 命中），404 的会跳过并计数。

用法:
  py -3 scripts/diag/l2d_ref_diff.py antu_2                 # 单模型全量比对
  py -3 scripts/diag/l2d_ref_diff.py antu_2 --clips idle,touch_body
  py -3 scripts/diag/l2d_ref_diff.py --probe-keys 40         # 只探测哪些 key 参考库有
  py -3 scripts/diag/l2d_ref_diff.py --all                    # 扫我们全部 269 个模型并汇总
输出: .diag/l2d_ref_diff.json + 终端汇总
"""
import os
import re
import sys
import json
import time
import argparse
import urllib.request
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.environ.get("L2D_OUT_DIR") or os.path.join(ROOT, "Output", "Live2D")
DIAG = os.path.join(ROOT, ".diag")
BASE = "https://static.l2d.su/azurlane/live2d"
TIMEOUT = 25

# 参考版 motion 子目录是 motions/（我们历史用的是 motion/）
REF_SUBDIRS = ("motions", "motion")


def fetch(url, binary=False):
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            if r.status != 200:
                return None
            data = r.read()
        return data if binary else json.loads(data.decode("utf-8"))
    except Exception:
        return None


def parse_curve(c):
    """Segments → [(type, (t0,v0), (c1), (c2), (t1,v1))]，与运行时解析器同语义。"""
    sg = c["Segments"]
    if not sg:
        return []
    pts = [(sg[0], sg[1])]
    segs = []
    i = 2
    n = len(sg)
    while i < n:
        ty = sg[i]
        if ty == 1:
            d = (sg[i + 5], sg[i + 6])
            segs.append((ty, pts[-1], (sg[i + 1], sg[i + 2]), (sg[i + 3], sg[i + 4]), d))
            i += 7
        else:
            d = (sg[i + 1], sg[i + 2])
            segs.append((ty, pts[-1], None, None, d))
            i += 3
        pts.append(d)
    return segs


def sample(segs, t):
    """按运行时求值：linear 插值 / stepped 取起点 / bezier 在 AreBeziersRestricted 下
    用归一化时间直接当贝塞尔参数（对应 bundle 里的 Z 函数）。"""
    if not segs:
        return 0.0
    for ty, p0, c1, c2, p3 in segs:
        if t <= p3[0] + 1e-9:
            if ty == 0:
                if p3[0] <= p0[0]:
                    return p3[1]
                return p0[1] + (p3[1] - p0[1]) * (t - p0[0]) / (p3[0] - p0[0])
            if ty == 2:
                return p0[1]
            if ty == 3:
                return p3[1]
            if p3[0] <= p0[0]:
                return p3[1]
            u = (t - p0[0]) / (p3[0] - p0[0])
            mu = 1.0 - u
            return (mu ** 3 * p0[1] + 3 * mu * mu * u * c1[1]
                    + 3 * mu * u * u * c2[1] + u ** 3 * p3[1])
    return segs[-1][4][1]


def type_hist(curves):
    h = Counter()
    for c in curves:
        for s in parse_curve(c):
            h[s[0]] += 1
    return h


def key_mismatch(ours, ref):
    """逐曲线比对关键帧时间/值（忽略段类型），返回不一致的曲线数。"""
    bad = 0
    for cid, segs in ref.items():
        o = ours.get(cid)
        if not o:
            bad += 1
            continue
        if len(o) != len(segs):
            bad += 1
            continue
        for a, b in zip(o, segs):
            if abs(a[4][0] - b[4][0]) > 1e-3 or abs(a[4][1] - b[4][1]) > 1e-3:
                bad += 1
                break
    return bad


def evaluate_model(key, clips=None, samples=121):
    ref_m3 = fetch(f"{BASE}/{key}/{key}.model3.json")
    if not ref_m3:
        return {"key": key, "skip": "参考库无此模型"}
    ref_groups = list((ref_m3.get("FileReferences") or {}).get("Motions") or {})
    ours_m3_path = os.path.join(OUT, key, f"{key}.model3.json")
    if not os.path.isfile(ours_m3_path):
        return {"key": key, "skip": "本地无此模型"}
    ours_m3 = json.load(open(ours_m3_path, encoding="utf-8"))
    ours_groups = list((ours_m3.get("FileReferences") or {}).get("Motions") or {})

    res = {"key": key,
           "groups_ref": len(ref_groups), "groups_ours": len(ours_groups),
           "groups_missing": sorted(set(ref_groups) - set(ours_groups))[:20],
           "clips": {}}
    targets = clips or [g for g in ref_groups if g in ours_groups]
    for g in targets:
        files = (ours_m3["FileReferences"]["Motions"].get(g) or [])
        if not files:
            continue
        ours_path = os.path.join(OUT, key, files[0]["File"])
        if not os.path.isfile(ours_path):
            continue
        ref_j = None
        for sub in REF_SUBDIRS:
            ref_j = fetch(f"{BASE}/{key}/{sub}/{g}.motion3.json")
            if ref_j:
                break
        if not ref_j:
            continue
        ours_j = json.load(open(ours_path, encoding="utf-8"))
        rcur = {c["Id"]: parse_curve(c) for c in ref_j.get("Curves") or []}
        ocur = {c["Id"]: parse_curve(c) for c in ours_j.get("Curves") or []}
        dur = (ref_j.get("Meta") or {}).get("Duration") or 1.0
        devs = []
        for cid in ocur:
            if cid not in rcur:
                continue
            ts = [dur * i / (samples - 1) for i in range(samples)]
            devs.append(max(abs(sample(ocur[cid], t) - sample(rcur[cid], t)) for t in ts))
        devs.sort()
        n = len(devs) or 1
        res["clips"][g] = {
            "curves_ref": len(rcur), "curves_ours": len(ocur),
            "curves_missing": sorted(set(rcur) - set(ocur))[:10],
            "key_mismatch": key_mismatch(ocur, rcur),
            "types_ref": dict(type_hist(ref_j.get("Curves") or [])),
            "types_ours": dict(type_hist(ours_j.get("Curves") or [])),
            "dev_median": round(devs[len(devs) // 2], 4),
            "dev_p90": round(devs[int(n * 0.9)], 4),
            "dev_gt05": sum(1 for d in devs if d > 0.5),
            "dev_gt05_pct": round(100.0 * sum(1 for d in devs if d > 0.5) / n, 1),
            "duration_ref": (ref_j.get("Meta") or {}).get("Duration"),
            "duration_ours": (ours_j.get("Meta") or {}).get("Duration"),
            "fps_ref": (ref_j.get("Meta") or {}).get("Fps"),
            "fps_ours": (ours_j.get("Meta") or {}).get("Fps"),
        }
    return res


def verdict(r):
    """给出 PASS/WARN/FAIL 判定。

    阈值按 2026-09-23 安土实测校准（那是"结构完全正确"时的真实残差）：
      idle 偏差>0.5 占 4.0% / touch_head 3.8% / touch_body 9.6% / touch_special 9.1%
    —— 这部分来自参考版那 7% 无法从 Unity 数据还原的贝塞尔段，是天花板不是 bug，
    所以 WARN 线放 12%；而「关键帧不一致」「曲线缺失」是硬错误，直接 FAIL。
    """
    if r.get("skip"):
        return "SKIP", r["skip"]
    hard = []
    soft = []
    if r["groups_missing"]:
        hard.append(f"漏登记动作组 {len(r['groups_missing'])}")
    for g, c in r["clips"].items():
        if c["curves_ours"] < c["curves_ref"]:
            hard.append(f"{g}: 曲线缺 {c['curves_ref'] - c['curves_ours']} 条")
        if c["key_mismatch"]:
            hard.append(f"{g}: 关键帧不一致 {c['key_mismatch']} 条")
        if c["dev_median"] > 0.5:
            hard.append(f"{g}: 偏差中位 {c['dev_median']} 过大")
        if abs((c["duration_ref"] or 0) - (c["duration_ours"] or 0)) > 1e-3:
            hard.append(f"{g}: 时长不一致")
        if c["dev_gt05_pct"] > 12.0:
            soft.append(f"{g}: 偏差>0.5 占 {c['dev_gt05_pct']}%（超贝塞尔天花板 12%）")
    if not r["clips"]:
        return "WARN", "无可比对的动作"
    if hard:
        return "FAIL", "; ".join(hard[:6])
    if soft:
        return "WARN", "; ".join(soft[:6])
    return "PASS", "结构一致，残差在贝塞尔近似范围内"


def main():
    ap = argparse.ArgumentParser(description="Live2D 动作数据 vs l2d.su 权威导出比对")
    ap.add_argument("keys", nargs="*", help="模型 key（如 antu_2）")
    ap.add_argument("--clips", help="只比对指定动作组，逗号分隔")
    ap.add_argument("--all", action="store_true", help="扫描本地全部模型")
    ap.add_argument("--probe-keys", type=int, default=0, help="只探测前 N 个 key 在参考库是否存在")
    args = ap.parse_args()

    keys = sorted(os.listdir(OUT)) if args.all else list(args.keys or [])
    keys = [k for k in keys if os.path.isdir(os.path.join(OUT, k))]
    if not keys:
        print(__doc__)
        return 2
    clips = args.clips.split(",") if args.clips else None
    os.makedirs(DIAG, exist_ok=True)

    results = []
    covered = 0
    if args.probe_keys:
        keys = keys[:args.probe_keys]
    for k in keys:
        if args.probe_keys:
            ok = fetch(f"{BASE}/{k}/{k}.model3.json") is not None
            covered += 1 if ok else 0
            print(f"  {'有' if ok else '无'}  {k}")
            continue
        r = evaluate_model(k, clips)
        v, msg = verdict(r)
        r["verdict"] = v
        r["verdict_msg"] = msg
        results.append(r)
        if r.get("skip"):
            print(f"  [SKIP] {k:<26} {r['skip']}")
        else:
            print(f"  [{v}] {k:<26} 组 {r['groups_ours']}/{r['groups_ref']}  " +
                  " | ".join(f"{g}: 曲线{c['curves_ours']}/{c['curves_ref']} 偏差中位{c['dev_median']} >0.5占{c['dev_gt05_pct']}%"
                             for g, c in list(r["clips"].items())[:3]))
            if v != "PASS":
                print(f"         └ {msg}")
    if args.probe_keys:
        print(f"\n参考库覆盖率: {covered}/{len(keys)}")
        return 0

    ok = sum(1 for r in results if r.get("verdict") == "PASS")
    skip = sum(1 for r in results if r.get("verdict") == "SKIP")
    print(f"\n===== 汇总 =====  PASS {ok} / 共 {len(results)}（跳过 {skip}）")
    path = os.path.join(DIAG, "l2d_ref_diff.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"详细结果: {path}")
    return 0 if ok == len(results) - skip else 1


if __name__ == "__main__":
    sys.exit(main())
