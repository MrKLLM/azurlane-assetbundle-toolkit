#!/usr/bin/env python3
"""l2d_diff_dirs.py — 对比两个 Live2D 产物目录的 motion3.json，给出换入决策依据。

只读。用法:
  py -3 scripts/diag/l2d_diff_dirs.py <OLD目录> <NEW目录> [模型数上限]

报告:
  - 每个模型的曲线数/目标类型/时长变化
  - 逐条 clip: gained(新增曲线) / changed(曲线名或数据变化) / lost(丢失曲线) ← lost 必须为 0 才可换入
  - 汇总: 有多少模型是纯新增(旧目录该 clip 为空壳/缺失)
"""
import os, sys, json, glob, collections

sys.stdout.reconfigure(encoding="utf-8")


def load(root, model):
    out = {}
    for f in glob.glob(os.path.join(root, model, "motion", "*.motion3.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            out[os.path.basename(f)[:-len(".motion3.json")]] = {"err": str(e)}
            continue
        cs = d.get("Curves", [])
        out[os.path.basename(f)[:-len(".motion3.json")]] = {
            "ids": [(c.get("Target"), c.get("Id")) for c in cs],
            "n": len(cs),
            "dur": (d.get("Meta") or {}).get("Duration"),
            "loop": (d.get("Meta") or {}).get("Loop"),
        }
    return out


def main():
    old_root, new_root = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9

    models = sorted(os.path.basename(os.path.dirname(f))
                    for f in glob.glob(os.path.join(new_root, "*", "motion", "*.motion3.json")))
    agg = collections.Counter()
    lost_report = []
    rows = []
    for m in models[:limit]:
        o, n = load(old_root, m), load(new_root, m)
        gained = changed = lost = same = 0
        lost_ids = []
        for clip, nv in n.items():
            ov = o.get(clip)
            if not ov or ov["n"] == 0:
                gained += 1
                continue
            if "err" in ov:
                gained += 1
                continue
            missing = set(ov["ids"]) - set(nv["ids"])
            if missing:
                lost += 1
                lost_ids.append((clip, sorted(missing)[:4]))
            elif ov["ids"] != nv["ids"] or ov["dur"] != nv["dur"]:
                changed += 1
            else:
                same += 1
        gone_clips = set(o) - set(n)
        agg["gained"] += gained
        agg["changed"] += changed
        agg["lost"] += lost
        agg["same"] += same
        agg["clips"] += len(n)
        if lost_ids:
            lost_report.append((m, lost_ids))
        nparts = sum(1 for v in n.values() for t, _ in v.get("ids", []) if t == "PartOpacity")
        rows.append((m, gained, changed, lost, same, len(n), nparts, len(gone_clips)))

    print("=== 汇总 ===")
    for k in ("clips", "gained", "changed", "lost", "same"):
        print(f"  {k:<8} {agg[k]}")
    print(f"  lost 必须为 0 才能换入 → {'✅ 可换入' if agg['lost'] == 0 else '⛔ 有回退，须人工确认'}")
    if agg["lost"]:
        print("\n丢失曲线明细（前 20）:")
        for m, li in lost_report[:20]:
            print(f"  {m}: {li}")
    gone = [r for r in rows if r[7]]
    if gone:
        print(f"\n新目录缺少旧目录存在的 clip（clip 未写出）: {len(gone)} 个模型")
        for r in gone[:15]:
            print(f"  {r[0]}: {r[7]} 条")
    print("\n=== 每模型（前 25）===")
    print(f"  {'model':<24}{'gained':>7}{'changed':>8}{'lost':>6}{'same':>6}{'clips':>7}{'partOpacity':>12}")
    for r in rows[:25]:
        print(f"  {r[0]:<24}{r[1]:>7}{r[2]:>8}{r[3]:>6}{r[4]:>6}{r[5]:>7}{r[6]:>12}")


if __name__ == "__main__":
    main()
