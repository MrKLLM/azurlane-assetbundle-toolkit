# -*- coding: utf-8 -*-
"""l2d_bezier_oracle.py — 用外部权威参照反解「Unity 关键帧 → Cubism 贝塞尔控制点」的映射。

背景（docs/TROUBLESHOOTING.md §117 第三轮）：全库导出的 motion3.json 里 1833 万个 Parameter 段
**贝塞尔为 0**（入库配方是 `L2D_MOTION_LINEAR=1`），关键帧之间全是折角 ⇒ 观感"单个动作内部太僵"。
但直接翻 `L2D_MOTION_ABSOLUTE_CP=1` 实测会把贝塞尔占比顶到 54.6%（参照只有 7.9%），且
`Param156` 峰速 32→72、峰加速度 626→1201 —— 控制点过冲。所以**不能猜公式，要拿答案反推**。

答案在哪：`.diag/_ref/` 的 4 份参照（经参数集 Jaccard=1.00 且时长逐位相符，确认是 `antu_2` 的
idle / touch_body / touch_head / touch_special）。它们是第三方工具从**同一批 Unity 源数据**导出的。
对参照里的每个贝塞尔段 (t0,v0,c1,c2,t1,v1)，按 Hermite↔Bezier 等价式反解出它实际用的切线：

    out = 3·(c1y − v0)/(c1x − t0)      in = 3·(v1 − c2y)/(t1 − c2x)

再与源数据里那对相邻键自带的 (outSlope, inSlope) 对比 —— 比值就是被我们弄丢/弄错的那个尺度。
对齐靠"段数 + 每段的起止时间与值"三重同时成立，不是按名字猜。

用法: py -3 scripts/diag/l2d_bezier_oracle.py [antu_2] [idle]
"""
import json
import os
import sys

import UnityPy

UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REF = {"idle": ".diag/_ref/ref_idle.motion3.json",
       "touch_body": ".diag/_ref/ref_touch_body.motion3.json",
       "touch_head": ".diag/_ref/ref_touch_head.motion3.json",
       "touch_special": ".diag/_ref/ref_touch_special.motion3.json"}
BUNDLE = os.path.join(ROOT, "files", "AssetBundles", "live2d")
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def decode(s):
    """→ [(kind, t0, v0, t1, v1, c1x, c1y, c2x, c2y)]，kind ∈ {L,B}；线性段控制点取端点。"""
    out = []
    t0, v0 = s[0], s[1]
    i = 2
    while i < len(s):
        ty = s[i]
        if ty == 0:
            t1, v1 = s[i + 1], s[i + 2]
            out.append(("L", t0, v0, t1, v1, t0, v0, t1, v1))
            t0, v0 = t1, v1
            i += 3
        elif ty == 1:
            t1, v1 = s[i + 5], s[i + 6]
            out.append(("B", t0, v0, t1, v1, s[i + 1], s[i + 2], s[i + 3], s[i + 4]))
            t0, v0 = t1, v1
            i += 7
        else:
            return None
    return out or None


def ref_curves(path):
    j = json.load(open(path, encoding="utf-8"))
    out = {}
    for c in j.get("Curves", []):
        if c.get("Target") != "Parameter":
            continue
        cid = c.get("Id")
        pid = cid if isinstance(cid, str) else (cid or {}).get("string")
        sg = decode(c.get("Segments") or [])
        if pid and sg:
            out[pid] = sg
    return out, j["Meta"]["Duration"]


def src_series(key, clip):
    import extract_motions as EM
    env = UnityPy.load(os.path.join(BUNDLE, key))
    for o in env.objects:
        if o.type.name != "AnimationClip" or str(o.read().m_Name) != clip:
            continue
        d = o.read()
        # 正本路径是 m_MuscleClip.m_Clip**.data**.m_StreamedClip —— 少跳 .data 会读到 OffsetPtr，
        # 于是三个容器全是 None/0，看起来像"这 clip 没有键"（本项目第四次踩字段路径的坑）。
        mc = getattr(d, "m_MuscleClip", None)
        cd = getattr(getattr(mc, "m_Clip", None), "data", None) if mc else None
        st = getattr(cd, "m_StreamedClip", None) if cd else None
        if not st:
            return None
        series = {}
        for t, keys in EM.parse_streamed_clip(st):
            if t < -1e-4:
                continue
            tt = 0.0 if abs(t) < 1e-6 else t
            for idx, v, ins, outs in keys:
                series.setdefault(idx, []).append((tt, v, ins, outs))
        for idx in series:
            series[idx].sort(key=lambda x: x[0])
        return series
    return None


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "antu_2"
    clip = sys.argv[2] if len(sys.argv) > 2 else "idle"
    ref, dur = ref_curves(os.path.join(ROOT, REF[clip]))
    nb = sum(1 for sg in ref.values() for x in sg if x[0] == "B")
    ns = sum(len(sg) for sg in ref.values())
    print("参照 %s/%s: 曲线 %d 段 %d 贝塞尔 %d (%.1f%%) 时长 %s"
          % (key, clip, len(ref), ns, nb, 100.0 * nb / max(1, ns), dur))
    series = src_series(key, clip)
    if not series:
        print("源 clip 读不到"); return 2
    print("源 clip: 曲线索引 %d 个" % len(series))

    # 索引候选：按段数分档，再用「每段起止 (t,v) 全等」锁定
    by_len = {}
    for idx, ks in series.items():
        by_len.setdefault(len(ks) - 1, []).append((idx, ks))
    hits = []
    for pid, sg in ref.items():
        if not any(x[0] == "B" for x in sg):
            continue
        for idx, ks in by_len.get(len(sg), []):
            if len(ks) != len(sg) + 1:
                continue
            ok = all(abs(ks[i][0] - sg[i][1]) < 1e-3 and abs(ks[i][1] - sg[i][2]) < 1e-3
                     for i in range(len(sg))) and \
                abs(ks[-1][0] - sg[-1][3]) < 1e-3 and abs(ks[-1][1] - sg[-1][4]) < 1e-3
            if ok:
                hits.append((pid, idx, sg, ks))
                break
    print("可对齐且含贝塞尔的参照曲线: %d 条" % len(hits))
    if not hits:
        print("一条都对不上 ⇒ 时间/值不是同一批键，先确认参照确实出自同一源数据，别急着改公式")
        return 3

    ratios_o, ratios_i, tfrac = [], [], []
    ratios = {}
    for pid, idx, sg, ks in hits[:40]:
        for i, x in enumerate(sg):
            if x[0] != "B":
                continue
            _, t0, v0, t1, v1, c1x, c1y, c2x, c2y = x
            so = ks[i][3]           # 我们解析器标为 outSlope 的那个 float
            si = ks[i + 1][2]       # 我们解析器标为 inSlope 的那个 float
            if c1x - t0 <= 1e-9 or t1 - c2x <= 1e-9:
                continue
            out_ref = 3.0 * (c1y - v0) / (c1x - t0)
            in_ref = 3.0 * (v1 - c2y) / (t1 - c2x)
            tfrac.append((c1x - t0) / (t1 - t0))
            # 三种候选读法：正读 / in↔out 对调 / 同键取反
            for tag, a, b in (("正读", so, si), ("对调", ks[i][2], ks[i + 1][3]),
                              ("同键", ks[i][3], ks[i][2])):
                rec = ratios.setdefault(tag, {"o": [], "i": []})
                if abs(a) > 1e-3:
                    rec["o"].append(out_ref / a)
                if abs(b) > 1e-3:
                    rec["i"].append(in_ref / b)
            if abs(so) > 1e-3:
                ratios_o.append(out_ref / so)
            if abs(si) > 1e-3:
                ratios_i.append(in_ref / si)
            if len(ratios_o) <= 6 and pid in hits[0][0:1] + (pid,):
                print("   %-14s [%.2f→%.2f] 反解 out=%+.3f 源 out=%+.3f  比 %.3f | in=%+.3f 源 in=%+.3f 比 %.3f"
                      % (pid, t0, t1, out_ref, so, out_ref / so if so else 0,
                         in_ref, si, in_ref / si if si else 0))

    def st(v):
        v = sorted(v)
        return "n=%d 中位 %.3f  10-90%% [%.3f, %.3f]" % (
            len(v), v[len(v) // 2], v[int(len(v) * .1)], v[min(len(v) - 1, int(len(v) * .9))])
    print("\n== 汇总（参照实际切线 / 源数据自带切线）==")
    if ratios_o:
        print("  outSlope 比:", st(ratios_o))
    if ratios_i:
        print("  inSlope  比:", st(ratios_i))
    if tfrac:
        print("  控制点时间位 (c1x-t0)/dt:", st(tfrac), "（Hermite 等价应为 0.3333）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
