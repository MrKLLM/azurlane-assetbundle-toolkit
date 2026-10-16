# -*- coding: utf-8 -*-
"""l2d_ref_curve_types.py — 从 l2d.su 权威参考导出里，看**每条曲线用的是哪种段类型**。
只读、走磁盘缓存（复用 `l2d_ref_diff.py` 的 fetch）。

为什么需要它：`extract_motions.py` 把 Unity 关键帧一律写成**线性**（type=0），而参考版
同一 clip 里有大量 **stepped**（type=2）段 —— 说明"瞬切"是源侧就有的语义，不是运行时能补的。
本脚本把"参考版里到底哪些参数是 stepped"摊开，用来判定：该在**导出层**保留步进，而不是
在页面里逐帧打补丁（见 docs/WORKFLOWS.md / TROUBLESHOOTING.md 对应条目）。

用法:
  py -3 scripts/diag/l2d_ref_curve_types.py gezi_2 home                 # 打印段类型分布 + each Id
  py -3 scripts/diag/l2d_ref_curve_types.py gezi_2 home --stepped-only  # 只列有 stepped 段的曲线
  py -3 scripts/diag/l2d_ref_curve_types.py gezi_2 home --ids Param25,Param27
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import l2d_ref_diff as R


def parse_curve(c):
    """Segments → [(type, (t0,v0), (t1,v1))]，只留端点（控制点对判类型无意义）。"""
    sg = c["Segments"]
    out = []
    if not sg:
        return out
    p0 = (sg[0], sg[1])
    i, n = 2, len(sg)
    while i < n:
        ty = sg[i]
        if ty == 1:
            d = (sg[i + 5], sg[i + 6])
            i += 7
        else:
            d = (sg[i + 1], sg[i + 2])
            i += 3
        out.append((ty, p0, d))
        p0 = d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("clip")
    ap.add_argument("--ids", default="", help="逗号分隔，只看这些 Id")
    ap.add_argument("--stepped-only", action="store_true")
    ap.add_argument("--ours", default="", help="改为读**本地**目录而不是参考库（如 .diag/l2d_step_sample）")
    a = ap.parse_args()

    if a.ours:
        p = os.path.join(a.ours, a.key, "motion", "%s.motion3.json" % a.clip)
        if not os.path.isfile(p):
            print("[FAIL] 本地文件不存在: %s" % p)
            return 2
        j = json.load(open(p, encoding="utf-8"))
        print("[*] 本地源: %s" % p)
    else:
        j = None
        for sub in R.REF_SUBDIRS:
            j = R.fetch("%s/%s/%s/%s.motion3.json" % (R.BASE, a.key, sub, a.clip))
            if j:
                print("[*] 参考源: %s/%s/%s/%s.motion3.json" % (R.BASE, a.key, sub, a.clip))
                break
        if not j:
            print("[FAIL] 参考库没有 %s/%s（或取不到；网络统计 %s）" % (a.key, a.clip, dict(R.STATS)))
            return 2

    curves = j.get("Curves") or []
    print("[*] %s: %d 条曲线  Meta=%s" % (a.clip, len(curves), j.get("Meta")))
    hist = Counter()
    per = []
    for c in curves:
        segs = parse_curve(c)
        h = Counter(s[0] for s in segs)
        hist.update(h)
        per.append((c.get("Id"), c.get("Target"), h, segs))
    print("[*] 段类型总计: " + ", ".join("%d=%d" % (k, v) for k, v in sorted(hist.items()))
          + "   （0=线性 1=贝塞尔 2=步进 3=?）")

    want = [x.strip() for x in a.ids.split(",") if x.strip()] if a.ids else None
    n_shown = 0
    for cid, tgt, h, segs in per:
        if want and cid not in want:
            continue
        if a.stepped_only and not h.get(2):
            continue
        n_shown += 1
        tag = " ".join("%d×%d" % (k, v) for k, v in sorted(h.items()))
        print("   %-26s %-11s %s" % (cid, tgt, tag))
        if want:
            for ty, p0, p1 in segs:
                print("        t=%8.3f→%8.3f  v=%7.3f→%7.3f  类型=%d%s"
                      % (p0[0], p1[0], p0[1], p1[1], ty, "  ← 步进" if ty == 2 else ""))
    print("[*] 命中 %d 条曲线（全库 %d）" % (n_shown, len(curves)))
    if a.stepped_only:
        stepped_ids = [cid for cid, _t, h, _s in per if h.get(2)]
        print("[*] 有 stepped 段的 Id（共 %d）: %s" % (len(stepped_ids), ",".join(stepped_ids)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
