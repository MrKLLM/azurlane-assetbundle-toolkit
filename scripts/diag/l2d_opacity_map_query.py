# -*- coding: utf-8 -*-
"""l2d_opacity_map_query.py — 读 `l2d_part_flicker_probe.py --mapall` 产的全量绑定台账
（`.diag/l2d_opacity_map_<model>.json`），离线回答「这块 mesh 的开关都有谁 / 这个参数管多少块 /
切到某条 clip 时哪些参数游戏会钉回默认而我们不会」。纯读盘，不起浏览器、不改任何产物。

台账里的每条关联是「参数 i 在量程第 q 个点（共 nstep 个点）时，drawable d 的透明度离开了基准」，
所以曲线可以整条重建：没列出来的点 = 基准值。

用法:
  py -3 scripts/diag/l2d_opacity_map_query.py gezi_2 --mesh ArtMesh42,ArtMesh36
  py -3 scripts/diag/l2d_opacity_map_query.py gezi_2 --param Param25,Paramfh
  py -3 scripts/diag/l2d_opacity_map_query.py gezi_2 --divergent home          # 从 idle 进 home 的 writeDefault 差集
  py -3 scripts/diag/l2d_opacity_map_query.py gezi_2 --ambient                 # 环境层（effect 非常量）管多少块 mesh
  py -3 scripts/diag/l2d_opacity_map_query.py gezi_2 --summary
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
L2D = os.path.join(ROOT, "Output", "Live2D")


def load_map(model):
    fp = os.path.join(ROOT, ".diag", "l2d_opacity_map_%s.json" % model)
    if not os.path.exists(fp):
        sys.exit("没有台账 %s —— 先跑 l2d_part_flicker_probe.py %s --mapall" % (fp, model))
    return json.load(open(fp, encoding="utf-8"))


def clip_curves(model):
    """{clip: {param: [(t, v), ...]}}，只取 Target==Parameter 的曲线。"""
    out = {}
    d = os.path.join(L2D, model, "motion")
    for fn in os.listdir(d):
        if not fn.endswith(".motion3.json"):
            continue
        clip = fn[:-len(".motion3.json")]
        j = json.load(open(os.path.join(d, fn), encoding="utf-8"))
        cs = {}
        for c in j.get("Curves", []):
            if c.get("Target") != "Parameter":
                continue
            seg, pts, i = c.get("Segments") or [], [], 0
            while i + 1 < len(seg):
                t = seg[i + 2] if i + 2 < len(seg) else None
                pts.append((seg[i], seg[i + 1]))
                if t in (2, 3):
                    i += 5
                elif t is None:
                    i += 2
                else:
                    i += 3
            cs[c["Id"]] = pts
        out[clip] = cs
    return out


def param_meta(model):
    fp = os.path.join(ROOT, ".diag", "_param_meta_%s.json" % model)
    if not os.path.exists(fp):
        return {}
    return json.load(open(fp, encoding="utf-8")).get("meta", {})


def drivers_for(mp, dname):
    names, out = mp["names"], []
    if dname not in names:
        return out
    d = names.index(dname)
    for e in mp["map"]:
        for dd, pts in e[7]:
            if dd == d:
                out.append((e[1], e[2], e[3], e[4], pts))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--mesh", default="", help="逗号分隔的 drawable 名 → 列出能改它透明度的全部参数与曲线")
    ap.add_argument("--param", default="", help="逗号分隔的参数名 → 列出它管住了哪些 mesh")
    ap.add_argument("--divergent", default="", help="目标 clip 名：idle 有曲线而它没有的参数，并标注是否管可视性")
    ap.add_argument("--ambient", action="store_true", help="effect 里非常量的参数管多少块 mesh")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()

    mp = load_map(a.model)
    nstep = mp["nstep"]
    idx_by_param = {e[1]: e for e in mp["map"]}
    print("台账: %s 参数 / %s mesh / 基准由 %d 点扫描构成 / 关联 %d 对"
          % (mp["params"], mp["drawables"], nstep + 1, mp["pairs"]))

    if a.summary:
        broad = sorted(mp["map"], key=lambda e: -e[6])[:a.limit]
        print("管得最宽的参数前 %d:" % len(broad))
        for e in broad:
            print("  %-24s 量程[%.3g,%.3g] default %.3g → %d 块 mesh" % (e[1], e[2], e[3], e[4], e[6]))
        return

    if a.mesh:
        for nm in [x.strip() for x in a.mesh.split(",") if x.strip()]:
            ds = drivers_for(mp, nm)
            print("\n== mesh `%s`：能改变它透明度的参数 %d 个（基准 %.3f）"
                  % (nm, len(ds), mp["ref"][mp["names"].index(nm)] if nm in mp["names"] else -1))
            for pname, mn, mx, defv, pts in ds:
                steps = " ".join("v%.3g→%.2f" % (mn + (mx - mn) * q / nstep, v) for q, v in pts[:8])
                print("   %-22s 量程[%.3g,%.3g] default %.3g | %s%s"
                      % (pname, mn, mx, defv, steps, " …" if len(pts) > 8 else ""))
        return

    if a.param:
        for nm in [x.strip() for x in a.param.split(",") if x.strip()]:
            e = idx_by_param.get(nm)
            if not e:
                print("\n== 参数 `%s`：扫遍量程 11 个点，**没有碰到任何 mesh 的透明度**"
                      "（它只管变形/其它输出）" % nm)
                continue
            print("\n== 参数 `%s` 量程[%.3g,%.3g] default %.3g rep%s → 管 %d 块 mesh"
                  % (nm, e[2], e[3], e[4], e[5], e[6]))
            for dd, pts in e[7][:a.limit]:
                steps = " ".join("%.2f" % v for _, v in pts)
                print("   %-20s 基准 %.2f | 变化点 %s%s"
                      % (mp["names"][dd], mp["ref"][dd], steps, " …" if len(pts) > 8 else ""))
            if e[6] > a.limit:
                print("   …另 %d 块见台账" % (e[6] - a.limit))
        return

    cs = clip_curves(a.model)
    meta = param_meta(a.model)
    idle, others = cs.get("idle", {}), cs.get(a.divergent or "home", {})

    if a.divergent:
        only = [p for p in idle if p not in others]
        print("\n== idle 有曲线而 `%s` 没有的参数 %d 个 —— 游戏进这个状态会把它们钉回 moc3 默认值，我们不会"
              % (a.divergent, len(only)))
        print("%-24s %-9s %-9s %-9s %s" % ("param", "default", "idle末值", "管几块mesh", "是否本来就有差"))
        ndiff = 0
        for p in sorted(only):
            dfl = meta.get(p, [None])[0]
            iv = idle[p][-1][1] if idle.get(p) else None
            e = idx_by_param.get(p)
            vis = e[6] if e else 0
            differs = (iv is not None and dfl is not None and abs(iv - dfl) > 1e-6)
            ndiff += 1 if (differs and vis) else 0
            print("%-24s %-9s %-9s %-9s %s"
                  % (p, dfl, None if iv is None else round(iv, 3), vis,
                     "有差(钉默认≠残留)" if (differs and vis) else ("差集但不管可视性" if not vis else "值相同,无差")))
        print("\n⇒ 既在差集、又管可视性、且 idle 值≠默认值的参数：**%d 个**（这些才是真正会看得出来的残留）" % ndiff)
        return

    if a.ambient:
        eff = cs.get("effect", {})
        nonconst = [p for p, pts in eff.items() if pts and max(v for _, v in pts) - min(v for _, v in pts) > 1e-6]
        tot, sample = 0, []
        for p in nonconst:
            e = idx_by_param.get(p)
            if e:
                tot += e[6]
                sample.append((p, e[6]))
        print("\n== 环境层（effect 里非常量的参数）共 %d 个，其中 %d 个会管 mesh 显隐，关联合计 %d 对"
              % (len(nonconst), len(sample), tot))
        for p, n in sorted(sample, key=lambda x: -x[1])[:a.limit]:
            print("   %-24s → %d 块 mesh" % (p, n))
        return

    print("（没给查询模式，见 --help）")


if __name__ == "__main__":
    main()
