# -*- coding: utf-8 -*-
"""l2d_step_ab.py — 段类型改动的零回退 A/B 对照（只读）。

用途：`extract_motions.py` 按 Unity 侧信号把「瞬切」段从 type=0 改成 type=2 之后，
逐曲线逐段证明**只有该改的那些段变了，其余端点逐位不动**。这是 §26 item 4 定下的
"推得出就发 type 2 并重导"那一步的验收闸——历史上重导曾顺手改坏别的东西，所以不能只看总曲线数。

判据（逐 clip、逐曲线、逐段）：
  1. 曲线 (Target, Id) 集合两侧完全相同（不许 lost / gained）
  2. 每条曲线的段数相同
  3. 每段的**终点 (t, v) 完全相同**（改段类型只改"值怎么走过去"，不改端点）
  4. 类型差异只允许 old=0 → new=2
任一不满足 ⇒ 计入「非期望差异」并打印样例。

用法: py -3 scripts/diag/l2d_step_ab.py <旧目录> <新目录> [模型名 ...]
      （不给模型名 = 新目录下的全部模型）
"""
import os
import sys
import json
import glob
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")


def seg_list(curve):
    """Segments → [(type, (t0,v0), (t1,v1))]，与运行时同语义（type=1 段占 7 个值）。"""
    sg = curve.get("Segments") or []
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


def load(root, model):
    out = {}
    for f in glob.glob(os.path.join(root, model, "motion", "*.motion3.json")):
        clip = os.path.basename(f)[:-len(".motion3.json")]
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            out[clip] = {"err": str(e)}
            continue
        out[clip] = {c.get("Id"): seg_list(c) for c in d.get("Curves") or []}
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    old_root, new_root = sys.argv[1], sys.argv[2]
    if len(sys.argv) > 3:
        models = sys.argv[3:]
    else:
        models = sorted(os.path.basename(os.path.dirname(f))
                        for f in glob.glob(os.path.join(new_root, "*", "motion", "*.motion3.json")))
    agg = Counter()
    bad_samples = []
    rows = []
    for m in models:
        o, n = load(old_root, m), load(new_root, m)
        acc = Counter()
        for clip, nv in n.items():
            ov = o.get(clip)
            if ov is None:
                acc["clip_gained"] += 1
                continue
            if "err" in ov or "err" in nv:
                acc["clip_err"] += 1
                continue
            lost = set(ov) - set(nv)
            gained = set(nv) - set(ov)
            acc["curve_lost"] += len(lost)
            acc["curve_gained"] += len(gained)
            for cid in set(ov) & set(nv):
                so, sn = ov[cid], nv[cid]
                if len(so) != len(sn):
                    acc["segcount_diff"] += 1
                    if len(bad_samples) < 12:
                        bad_samples.append((m, clip, cid, "段数 %d→%d" % (len(so), len(sn))))
                    continue
                for k, (eo, en) in enumerate(zip(so, sn)):
                    if aim_diff(eo[2], en[2]) > 1e-9:
                        acc["endpoint_diff"] += 1
                        if len(bad_samples) < 12:
                            bad_samples.append((m, clip, cid, "第%d段终点 %s→%s" % (k, eo[2], en[2])))
                        break
                    if eo[0] != en[0]:
                        if eo[0] == 0 and en[0] == 2:
                            acc["expected_step"] += 1
                        else:
                            acc["type_unexpected"] += 1
                            if len(bad_samples) < 12:
                                bad_samples.append((m, clip, cid, "第%d段类型 %d→%d" % (k, eo[0], en[0])))
        for k, v in acc.items():
            agg[k] += v
        rows.append((m, acc["expected_step"], sum(v for k, v in acc.items()
                                                  if k not in ("expected_step",))))

    print("=== 汇总（%d 个模型）===" % len(models))
    for k in ("expected_step", "endpoint_diff", "type_unexpected", "segcount_diff",
              "curve_lost", "curve_gained", "clip_gained", "clip_err"):
        print("  %-18s %d" % (k, agg[k]))
    bad = sum(v for k, v in agg.items() if k != "expected_step")
    print("  非期望差异合计 %d → %s" % (bad, "✅ 零回退（只有预期瞬切段变）" if bad == 0 else "⛔ 有非期望差异"))
    if bad_samples:
        print("\n非期望差异样例（前 12）:")
        for s in bad_samples:
            print("   %s / %s / %s : %s" % s)
    print("\n=== 每模型 ===")
    print("  %-24s %14s %14s" % ("model", "改为瞬切段", "非期望差异"))
    for m, exp, bd in rows:
        print("  %-24s %14d %14d" % (m, exp, bd))
    return 0 if bad == 0 else 1


def aim_diff(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


if __name__ == "__main__":
    sys.exit(main())
