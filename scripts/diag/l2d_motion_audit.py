#!/usr/bin/env python3
"""l2d_motion_audit.py — Live2D 动作文件全量健康审计（只读，不改任何产物）

对每个模型的每个 clip 分类：
  shell     : 磁盘 motion3.json 的 Curves 为空（extract 静默失败留下的占位壳）
  misassign : 磁盘曲线 Id 与「权威映射」不一致（权威 = AnimationClip.genericBindings[i]
              的 path 哈希 crc32("Parameters/<GameObject名>") / crc32("Parts/<名>") 反查）
  losspart  : 该 clip 官方含 PartOpacity（部件可见性/换装拼接）曲线而磁盘没有
  ok        : 曲线名与权威映射一致

用法:
  PYTHONIOENCODING=utf-8 py -3 scripts/diag/l2d_motion_audit.py            # 全量
  PYTHONIOENCODING=utf-8 py -3 scripts/diag/l2d_motion_audit.py lingbo idle # 指定模型/动作
输出: .diag/l2d_motion_audit.json + 终端汇总
"""
import os, sys, json, struct, binascii, glob
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")

import UnityPy
from UnityPy import config
config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIVE2D = os.path.join(ROOT, "files", "AssetBundles", "live2d")
OUT = os.environ.get("L2D_OUT_DIR") or os.path.join(ROOT, "Output", "Live2D")
DIAG = os.path.join(ROOT, ".diag")

PARAM_PREFIX = "Parameters/"
PART_PREFIX = "Parts/"
ATTR_PARAM = 3702945584
ATTR_PART = 2353026298


def crc(s):
    return binascii.crc32(s.encode("utf-8")) & 0xFFFFFFFF


def parse_frames(buf, cap=None):
    """无护栏解析：靠缓冲区边界与 +inf 结束符停止。"""
    frames = []
    pos = 0
    while pos + 8 <= len(buf):
        t = struct.unpack_from("<f", buf, pos)[0]; pos += 4
        if t == float("inf"):
            break
        n = struct.unpack_from("<i", buf, pos)[0]; pos += 4
        if n < 0 or pos + n * 20 > len(buf):
            break
        keys = []
        for _ in range(n):
            ci = struct.unpack_from("<i", buf, pos)[0]
            c = struct.unpack_from("<4f", buf, pos + 4)
            pos += 20
            keys.append((ci, c[3], c[1], c[2]))
        frames.append((t, keys))
        if cap and len(frames) >= cap:
            break
    return frames


def audit_model(name, only_clip=None):
    bp = os.path.join(LIVE2D, name)
    if not os.path.isfile(bp):
        return None
    env = UnityPy.load(bp)

    goname = {}
    for o in env.objects:
        if o.type.name == "GameObject":
            try:
                goname[o.path_id] = o.read().m_Name
            except Exception:
                pass

    hash2 = {}          # path hash -> (kind, id)
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            d = o.read()
            sr = getattr(d, "m_Script", None)
            if not sr:
                continue
            sn = getattr(sr.read(), "m_Name", "")
            if sn not in ("CubismParameter", "CubismPart"):
                continue
            tt = o.read_typetree()
            gname = goname.get(tt.get("m_GameObject", {}).get("m_PathID"))
            if not gname:
                continue
            kind = "Parameter" if sn == "CubismParameter" else "PartOpacity"
            pre = PARAM_PREFIX if kind == "Parameter" else PART_PREFIX
            hash2[crc(pre + gname)] = (kind, gname, tt.get("_unmanagedIndex"))
        except Exception:
            continue

    clips = []
    for o in env.objects:
        if o.type.name == "AnimationClip":
            try:
                clips.append(o.read())
            except Exception:
                pass

    rows = []
    for c in clips:
        if only_clip and c.m_Name != only_clip:
            continue
        gb = list(c.m_ClipBindingConstant.genericBindings)
        auth = []
        for b in gb:
            auth.append(hash2.get(getattr(b, "path", 0) & 0xFFFFFFFF))
        sc = getattr(c.m_MuscleClip, "m_Clip", None)
        sd = getattr(sc.data.m_StreamedClip, "data", None) if sc and sc.data else None
        buf = b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in sd) if sd else b""
        frames = parse_frames(buf) if buf else []
        idxs = sorted({k[0] for _, ks in frames for k in ks})
        auth_ids = {i: auth[i] for i in idxs if i < len(auth) and auth[i]}
        n_part = sum(1 for v in auth_ids.values() if v[0] == "PartOpacity")

        fp = os.path.join(OUT, name, "motion", f"{c.m_Name}.motion3.json")
        disk = {}
        disk_seq = []
        disk_meta = None
        if os.path.isfile(fp):
            try:
                m = json.load(open(fp, encoding="utf-8"))
                disk_seq = [cur["Id"] for cur in m.get("Curves", [])]
                disk = {cur["Id"]: cur for cur in m.get("Curves", [])}
                disk_meta = m.get("Meta")
            except Exception:
                disk = {"<unreadable>": {}}
        else:
            disk = {"<missing file>": {}}

        # 位置级比对：磁盘第 rank 条曲线是否等于权威名。
        # 注意只数「可解析」的曲线——提取器会跳过不可解析目标，按全量 idx 排 rank 会整体错位。
        ordered_idx = sorted(auth_ids.keys())
        n_pos_diff = 0
        for rank, i in enumerate(ordered_idx):
            a = auth_ids.get(i)
            d = disk_seq[rank] if rank < len(disk_seq) else None
            if a and a[1] != d:
                n_pos_diff += 1

        # 旧生成器假设 curve idx == moc3 参数序号(从 0 连续)；只有恰好 dense 时才对
        ui = [v[2] for _k, v in sorted(auth_ids.items()) if v[2] is not None]
        dense = bool(ui) and ui == list(range(len(ui))) and \
            all(v[0] == "Parameter" for v in auth_ids.values())
        ascending = bool(ui) and all(x <= y for x, y in zip(ui, ui[1:]))

        # 不可解析目标：越界，或该绑定的 path 哈希不属于任何 Parameter/Part 组件
        n_unres = sum(1 for i in idxs if i >= len(auth) or auth[i] is None)

        if len(disk_seq) == 0:
            status = "shell"
        elif n_pos_diff == 0 and n_unres == 0:
            status = "ok"          # 每条曲线名都等于权威名（与是否 dense 无关）
        elif n_pos_diff == 0:
            status = "ok_partial"  # 名字全对，但有不可解析目标被跳过（预期行为）
        else:
            status = "misassign"
        rows.append({
            "clip": c.m_Name,
            "status": status,
            "frames": len(frames),
            "curves_real": len(idxs),
            "curves_disk": len(disk_seq) if "<missing file>" not in disk else -1,
            "part_opacity_curves": n_part,
            "unresolved_bindings": n_unres,
            "pos_diff": n_pos_diff,
            "dense": dense,
            "ascending": ascending,
            "disk_dur": (disk_meta or {}).get("Duration"),
            "src_dur": round(max([t for t, _ in frames if t >= 0], default=0.0), 3),
        })
    return rows


def main():
    args = [a for a in sys.argv[1:]]
    only_model = args[0] if args else None
    only_clip = args[1] if len(args) > 1 else None

    models = [only_model] if only_model else sorted(
        d for d in os.listdir(LIVE2D) if os.path.isfile(os.path.join(LIVE2D, d)))
    summary = Counter()
    per_model = {}
    part_models = []
    n_dense = n_asc = n_notasc = 0
    for i, m in enumerate(models):
        try:
            rows = audit_model(m, only_clip)
        except Exception as e:
            summary["error"] += 1
            print(f"[!] {m}: {type(e).__name__}: {e}")
            continue
        if rows is None:
            continue
        st = Counter(r["status"] for r in rows)
        summary.update(st)
        summary["clips"] += len(rows)
        n_dense += sum(1 for r in rows if r.get("dense"))
        asc_ok = all(r.get("ascending", True) for r in rows)
        n_asc += asc_ok
        if not asc_ok:
            n_notasc += 1
            summary["clip_order_not_ascending"] += sum(1 for r in rows if not r.get("ascending", True))
        per_model[m] = rows
        np_ = sum(r["part_opacity_curves"] for r in rows)
        if np_:
            part_models.append((m, np_, st.get("shell", 0), st.get("misassign", 0)))
        if only_model:
            for r in sorted(rows, key=lambda x: x["clip"]):
                print(f"  {r['clip']:<20} {r['status']:<10} frames={r['frames']:<6} "
                      f"curves auth={r['curves_real']:<5} disk={r['curves_disk']:<5} "
                      f"partOpacity={r['part_opacity_curves']:<4} unresolved={r['unresolved_bindings']:<4} "
                      f"dur disk={r['disk_dur']} src={r['src_dur']}")
        elif (i + 1) % 25 == 0:
            print(f"... {i+1}/{len(models)} audited  {dict(summary)}")

    print("\n===== SUMMARY =====")
    for k, v in summary.items():
        print(f"  {k:<24} {v}")
    if summary.get("clips"):
        print(f"  shell  {100*summary.get('shell',0)/summary['clips']:.1f}%   "
              f"misassign {100*summary.get('misassign',0)/summary['clips']:.1f}%   "
              f"ok {100*summary.get('ok',0)/summary['clips']:.1f}%")
    print(f"  clips whose binding set is dense(0..n-1) 旧映射碰巧可能对: {n_dense} ({100*n_dense/max(1,summary['clips']):.1f}%)")
    print(f"  models where 所有 clip 的绑定序单调递增(=curve idx↔binding i 成立): {n_asc}/{len(per_model)}  "
          f"非递增 clip 数: {summary.get('clip_order_not_ascending',0)}")
    print(f"  models with PartOpacity (换装/拼接) curves: {len(part_models)}")
    for m, n, s, mi in sorted(part_models, key=lambda x: -x[1])[:15]:
        print(f"    {m:<22} partOpacityCurves={n:<6} shell={s} misassign={mi}")

    os.makedirs(DIAG, exist_ok=True)
    out = os.path.join(DIAG, "l2d_motion_audit.json")
    json.dump({"summary": dict(summary), "models": per_model}, open(out, "w", encoding="utf-8"))
    print(f"\n详细结果: {out}")


if __name__ == "__main__":
    main()
