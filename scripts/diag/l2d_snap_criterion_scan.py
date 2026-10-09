#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「哪些参数在交叉淡化里不该被平滑插值」的离线判据扫描 —— 不碰浏览器、不碰前端。

背景（§123 追加-IX/X）：源数据里存在「两套互斥美术的开关参数」（`Param25`：0=A 组手、≥0.2=B 组手，
中间约 0.1 宽两组全灭）。游戏是 `Animator.Play()` 瞬时切换 ⇒ 从不落在中间；我们走库的 2 秒淡入 ⇒
必穿死区 ⇒ 「切动作瞬间两只手一起没」。修法 (b) 要的是**只对这些开关参数 step 写入、其余照常混合**，
于是必须先有一个**能自动判定、且不会误伤**的判据。

判据（本脚本的结论）= **C2 selector-straddle**，三条同时成立：
  ① 该参数在探针臂 ⑤ 的「参数→mesh 显隐」台账里（= 它真的会改变某个 ArtMesh 的不透明度）；
  ② 切出去的那条 clip 在末尾 `--window` 秒内把它写成一个常量，切进来的那条在开头同样写成常量，且两值不同；
  ③ 这两个常量之间**跨过台账里至少一个翻转点**（= 这一淡会改变"哪些美术在画"）。
①把相位/口型类全部挡在门外（它们根本不碰显隐），③把"虽然是选择器但这次没换美术"的也挡在门外。

对照的三条候选：
  C1 blink    —— mesh 在两个端点都亮、中间灭（部件闪一下）。实测 gezi_2 全部 clip 配对 0 例。
  C2 selector —— 上面那三条。★采用。
  C3 boundary —— 只看曲线端点（①③都不要），上一轮的宽松判据，用来看它误伤多少。

⚠️ **不能用「屏幕面积覆盖」当判据**：Cubism 里不透明度为 0 的 ArtMesh，其顶点会塌到原点
   （`--dumpgeo` 实测：`ArtMesh325/331/335` 在两个姿态下都是 `[0,0,0,0]`，而亮着的 `ArtMesh42`
   有真实框）⇒ 从任何单一姿态导出都拿不到"灭着的那组"的尺寸，面积比不了。要量面积只能在
   该值真的点亮它的那一拍里读——本脚本因此完全不依赖几何。

判据成立的标准不是「抓到多少」，而是：**已知门参数必须在内，相位/口型类必须不在内**。
已知门（④/⑤ 实测会改变 mesh 透明度）：Param17/20/21/25/27/39/139/188、l2d_hx、shop_hx。
已知不该 snap：Param122/52/141/65/142/143、MB_*、GL*（相位类，靠 patch ⑤ 的 ModF 回绕）、
ParamMouthOpenY / ParamJTEyeOpen（口型/眼）。

用法: py -3 scripts/diag/l2d_snap_criterion_scan.py gezi_2
      py -3 scripts/diag/l2d_snap_criterion_scan.py gezi_2 --focus idle->home
      py -3 scripts/diag/l2d_snap_criterion_scan.py gezi_2 --emit   # 落前端用的开关表
输入: .diag/l2d_opacity_map_<model>.json  （探针臂 ⑤ `--mapall` 落盘）
输出: .diag/snap_criterion_<model>.txt（报告）、stdout 只打 ASCII 摘要
      --emit → Output/Live2D/<model>/<model>.snapswitch.json
"""
import argparse
import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

GATES = {"Param17", "Param20", "Param21", "Param25", "Param27", "Param39",
         "Param139", "Param188", "l2d_hx", "shop_hx"}
NOT_SNAP = {"Param122", "Param52", "Param141", "Param65", "Param142", "Param143",
             "ParamMouthOpenY", "ParamJTEyeOpen"}
ON = 0.5          # 「亮着」的不透明度阈值
OFF = 0.05        # 「灭掉」的阈值


def parse_segments(curve):
    """[t0,v0,ty0, (贝塞尔再 4 个控制点) t1,v1,ty1, … , tn,vn] → keys=[(t,v),…]"""
    s = curve.get("Segments", [])
    keys, i = [], 0
    while i + 1 < len(s):
        keys.append((s[i], s[i + 1]))
        if i + 2 < len(s):
            ty = int(s[i + 2])
            i += 3 + (4 if ty in (2, 3) else 0)
        else:
            i += 2
    return keys


def boundary_values(keys, dur, window):
    """返回 (头值, 头恒定秒数, 尾值, 尾恒定秒数… 见下)。结构判据，不做贝塞尔求值。
    恒定秒数 = **连续等值键段的跨度**（不是只看第二个键）：`home` 的 Param25 在 0/1.55/1.617/2.9
    四个键上都是 0.5，真正保持 2.9 秒 —— 只数到第二个键会把钉值时长算短，交叉淡化后段又漏回死区。"""
    if not keys:
        return None, 0.0, None, 0.0
    head_v = keys[0][1]
    j = 1
    while j < len(keys) and abs(keys[j][1] - head_v) < 1e-4:
        j += 1
    head_len = (keys[j][0] if j < len(keys) else dur) - keys[0][0]
    tail_v = keys[-1][1]
    k = len(keys) - 2
    while k >= 0 and abs(keys[k][1] - tail_v) < 1e-4:
        k -= 1
    tail_len = keys[-1][0] - (keys[k + 1][0] if k + 1 < len(keys) else 0.0)
    if len(keys) == 1:
        head_len = tail_len = dur
    return head_v, head_len >= window - 1e-6, tail_v, tail_len >= window - 1e-6, head_len, tail_len


def bvals(keys, dur, window):
    r = boundary_values(keys, dur, window)
    return r[0], r[1], r[2], r[3]


def load_clips(mdir):
    clips = {}
    for f in glob.glob(os.path.join(mdir, "*.motion3.json")):
        j = json.load(open(f, encoding="utf-8"))
        dur = j.get("Meta", {}).get("Duration", 0.0) or 0.0
        curves = {c["Id"]: parse_segments(c) for c in j.get("Curves", [])
                  if c.get("Target") == "Parameter"}
        clips[os.path.basename(f)[: -len(".motion3.json")]] = (dur, curves)
    return clips


def load_map(mfile):
    """台账 → {param: {'mn','mx','flips':[翻转值…],'grid':{mesh:[op_0..op_n]}}}"""
    d = json.load(open(mfile, encoding="utf-8"))
    n = int(d["nstep"])
    ref, names = d["ref"], d["names"]
    out = {}
    for e in d["map"]:
        mn, mx = float(e[2]), float(e[3])
        grid = {}
        for didx, pts in e[7]:
            curve = [ref[didx]] * (n + 1)
            for q, v in pts:
                curve[q] = v
            grid[names[didx]] = curve
        flips = []
        for q in range(n):                    # 相邻两个采样点之间「有 mesh 从亮变灭或反之」⇒ 记一个翻转点
            changed = any((a >= ON) != (b >= ON) for a, b in
                          zip((c[q] for c in grid.values()), (c[q + 1] for c in grid.values())))
            if changed:
                flips.append(round(mn + (mx - mn) * (q + 0.5) / n, 4))
        out[e[1]] = {"mn": mn, "mx": mx, "flips": flips, "grid": grid}
    return out, n, int(d["drawables"])


def straddle(vA, vB, flips, mn, mx):
    """(vA,vB) 开区间里跨过几个翻转点。"""
    lo, hi = min(vA, vB), max(vA, vB)
    if mx <= mn:
        return 0
    span = mx - mn
    return sum(1 for f in flips if lo + 1e-4 * span < f < hi - 1e-4 * span)


def load_deform(dfile):
    """⑨ 变形者闸台账 → {param: [第 q-1→q 步的几何位移…（下标 1..nstep）]}。缺文件返回 {}。"""
    if not os.path.exists(dfile):
        return {}
    d = json.load(open(dfile, encoding="utf-8"))
    out = {}
    for x in d.get("params", []):
        if "hist" not in x:
            continue
        arr = [0.0]
        for h in x["hist"]:
            arr.append(float(h[2]))
        out[x["name"]] = arr
    return out


def jump_shift(step, vA, vB, mn, mx):
    """snap 之后姿态会跳多远：把 (vA,vB) 之间各网格步的几何位移加起来（⑨ 的 hist）。"""
    if not step or mx <= mn:
        return 0.0
    n = len(step) - 1
    qa = (vA - mn) / (mx - mn) * n
    qb = (vB - mn) / (mx - mn) * n
    lo, hi = sorted((qa, qb))
    return sum(step[q] for q in range(1, n + 1) if lo < q - 1 < hi + 1e-9 or lo < q < hi) if False else \
        sum(step[q] for q in range(1, n + 1) if min(lo, hi) < q < max(lo, hi) or
            (lo <= q - 1 < hi and step[q] > 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--window", type=float, default=0.6, help="边界「恒定」窗口秒数")
    ap.add_argument("--maxjump", type=float, default=0.5,
                    help="snap 允许的「姿态跳变」上限（屏幕单位，全模型亮着 mesh 的 Σ(宽+高) 变化；"
                         "gezi_2 舞台约 8 单位 ⇒ 0.5 ≈ 6%）")
    ap.add_argument("--focus", default="", help="只详细看这一对，形如 idle->home")
    ap.add_argument("--emit", action="store_true", help="落前端用的 <model>.snapswitch.json")
    a = ap.parse_args()

    mfile = os.path.join(ROOT, ".diag", "l2d_opacity_map_%s.json" % a.model)
    mdir = os.path.join(ROOT, "Output", "Live2D", a.model, "motion")
    if not os.path.exists(mfile):
        print("MISSING %s  (run probe arm 5: --mapall)" % mfile)
        return 2
    opmap, n, ndraw = load_map(mfile)
    clips = load_clips(mdir)
    deform = load_deform(os.path.join(ROOT, ".diag", "l2d_deform_%s.json" % a.model))

    lines = []
    w = lines.append
    w("model=%s clips=%d ledger_params=%d drawables=%d window=%.2fs on>=%.2f off<%.2f "
      "deform-ledger=%s maxjump=%.3g"
      % (a.model, len(clips), len(opmap), ndraw, a.window, ON, OFF, deform or "缺(不做变形闸)", a.maxjump))

    allp = sorted({pid for _, curves in clips.values() for pid in curves})
    bv = {}
    for C, (dur, curves) in clips.items():
        bv[C] = {pid: bvals(curves[pid], dur, a.window) for pid in curves}

    stats = {}
    c3 = set()
    pairs_tested = 0
    for A in clips:
        for B in clips:
            if A == B:
                continue
            pairs_tested += 1
            rA, rB = bv[A], bv[B]
            for pid in rA:
                if pid not in rB:
                    continue
                _, _, va, tailA = rA[pid]          # 出去的那条：末尾恒定值
                vb, headB, _, _ = rB[pid]          # 进来的那条：开头恒定值
                if not (tailA and headB) or abs(vb - va) < 1e-6:
                    continue
                c3.add(pid)
                pm = opmap.get(pid)
                if pm is None:
                    continue
                st = stats.setdefault(pid, {"pairs": 0, "snap": 0, "ex": None, "blink": 0,
                                            "straddle": 0, "maxJump": 0.0})
                st["pairs"] += 1
                k = straddle(va, vb, pm["flips"], pm["mn"], pm["mx"])
                if not k:
                    continue
                st["straddle"] += 1
                if pid in opmap:               # C1 blink：两个端点都亮、中间灭（与 snap 与否无关，单独统计）
                    grid, mn, mx = pm["grid"], pm["mn"], pm["mx"]
                    lo, hi = min(va, vb), max(va, vb)
                    interior = [q for q in range(n + 1)
                                if lo + 1e-6 < mn + (mx - mn) * q / n < hi - 1e-6]
                    if interior and any(op_at(c, va, mn, mx) >= ON and op_at(c, vb, mn, mx) >= ON
                                        and any(c[q] < OFF for q in interior) for c in grid.values()):
                        st["blink"] += 1
                jump = jump_shift(deform.get(pid), va, vb, pm["mn"], pm["mx"]) if deform else 0.0
                st["maxJump"] = max(st["maxJump"], jump)
                if jump > a.maxjump:
                    continue
                st["snap"] += 1
                if st["ex"] is None:
                    st["ex"] = (A, B, va, vb, k, jump)
                if pid in opmap:               # C1 blink：两个端点都亮、中间灭
                    grid, mn, mx = pm["grid"], pm["mn"], pm["mx"]
                    lo, hi = min(va, vb), max(va, vb)
                    interior = [q for q in range(n + 1)
                                if lo + 1e-6 < mn + (mx - mn) * q / n < hi - 1e-6]
                    if interior and any(op_at(c, va, mn, mx) >= ON and op_at(c, vb, mn, mx) >= ON
                                        and any(c[q] < OFF for q in interior) for c in grid.values()):
                        st["blink"] += 1
                if a.focus:
                    fa_, fb_ = a.focus.split("->")
                    if A == fa_ and B == fb_:
                        w("  FOCUS %s->%s %-20s v %.3f->%.3f straddle=%d jump=%.4f"
                          % (A, B, pid, va, vb, k, jump))
                    continue

    w("pairs tested=%d  C3(boundary only)=%d  ledger=%d" % (pairs_tested, len(c3), len(opmap)))
    w("")
    w("%-24s %7s %7s %7s %8s  %s" % ("param", "pairs", "straddl", "SNAP", "noSnap", "example A->B  vA->vB  #flips  jump"))
    flagged = []
    for pid in sorted(stats, key=lambda p: (-stats[p]["snap"], p)):
        st = stats[pid]
        if not st["snap"]:
            continue
        flagged.append(pid)
        ex = ""
        if st["ex"]:
            A, B, va, vb, k, jm = st["ex"]
            ex = "%s->%s %.3f->%.3f %d  %.4f" % (A, B, va, vb, k, jm)
        mark = " GATE" if pid in GATES else (" FORBID" if pid in NOT_SNAP else "")
        w("%-24s %7d %7d %7d %8d  %s%s  maxJump=%.4f"
          % (pid, st["pairs"], st["straddle"], st["snap"], st["straddle"] - st["snap"], ex, mark, st["maxJump"]))
    w("")
    dropped = sorted(p for p in stats if stats[p]["straddle"] and not stats[p]["snap"])
    gates_in = sorted(p for p in GATES if p in flagged)
    gates_out = sorted(p for p in GATES if p not in flagged)
    bad = sorted(p for p in NOT_SNAP if p in flagged)
    w("C2 selector-straddle: flagged %d | gates in %d/10 %s" % (len(flagged), len(gates_in), gates_in))
    w("   gates NOT flagged %s  (逐个查：这些参数在所有 clip 边界是否恒为同一值)" % (gates_out,))
    w("   forbidden caught %d %s" % (len(bad), bad))
    w("   跨过翻转点但被变形闸挡下（一次都没 snap）的参数 %d: %s" % (len(dropped), dropped))
    w("C1 blink: params with >=1 blink pair = %d" % sum(1 for p in stats if stats[p]["blink"]))
    w("C3 boundary-only would flag %d params (of them %d touch mesh opacity at all)"
      % (len(c3), len(c3 & set(opmap))))

    if a.emit:
        out = os.path.join(ROOT, "Output", "Live2D", a.model, "%s.snapswitch.json" % a.model)
        # clips[clip][param] = [开头恒定值, 恒定秒数]：前端 switch 到这条 clip 时，把该参数逐帧钉在这个值上
        heads = {}
        for C, (dur, curves) in clips.items():
            row = {}
            for pid in flagged:
                k = curves.get(pid)
                if not k:
                    continue
                hv, hc, _, _, head_len, _ = boundary_values(k, dur, a.window)
                if not hc:
                    continue
                row[pid] = [round(hv, 4), round(max(0.0, min(head_len, dur)), 3)]
            heads[C] = row
        payload = {"model": a.model, "window": a.window, "maxjump": a.maxjump,
                   "generatedBy": os.path.basename(__file__),
                   "note": "cross-clip fade of these params changes WHICH ArtMeshes are drawn "
                           "(and the pose jump stays under maxjump) - gallery pins the incoming "
                           "clip's boundary value instead of blending them",
                   "params": {p: {"flips": opmap[p]["flips"], "mn": opmap[p]["mn"],
                                  "mx": opmap[p]["mx"], "stepShift": deform.get(p, [])}
                              for p in flagged},
                   "clips": heads}
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
        w("emit -> %s (%d params, %d clips, %d bytes)"
          % (out, len(flagged), len(heads), os.path.getsize(out)))

    rpt = os.path.join(ROOT, ".diag", "snap_criterion_%s.txt" % a.model)
    with open(rpt, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("report -> %s" % rpt)
    print("\n".join(l for l in lines if l.startswith(("C1 ", "C2 ", "C3 ", "pairs", "emit", "   "))))
    return 0


def op_at(curve, v, mn, mx):
    if mx <= mn:
        return curve[0]
    f = min(max((v - mn) / (mx - mn), 0.0), 1.0) * (len(curve) - 1)
    i = int(f)
    if i >= len(curve) - 1:
        return curve[-1]
    t = f - i
    return curve[i] * (1 - t) + curve[i + 1] * t


if __name__ == "__main__":
    sys.exit(main())
