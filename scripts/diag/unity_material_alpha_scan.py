# -*- coding: utf-8 -*-
"""扫一个 Unity 场景包引用的所有材质实例的**渲染状态**，用来决定 glTF 的 alphaMode 怎么推。

为什么需要它：`_Cutoff` 看着像"alpha 测试"的依据，其实是 Shader 的默认值——
碧蓝航线宿舍场景 348 个材质里 289 个带 `_Cutoff=0.5`，其中包含明显不透明的墙和木头。
拿它当判据会把大半房间变成 alpha 测试。真正可用的只有两个信号：
混合方程 `_SrcBlend==5 && _DstBlend==10`（SrcAlpha/OneMinusSrcAlpha）与 `_BaseColor.a < 1`。

    py -3 scripts/diag/unity_material_alpha_scan.py                 # 默认天狼星宿舍场景
    py -3 scripts/diag/unity_material_alpha_scan.py --scene <包>    # 换场景

输出：取值分布 + 按上面规则判成 BLEND 的材质清单（装配器改动的受影响面）。
"""
import argparse
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, HERE)

KEYS = ("_Surface", "_Mode", "_Blend", "_SrcBlend", "_DstBlend", "_Cutoff", "_AlphaClip",
        "_ZWrite", "_Cull", "_BaseColor")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default=None, help="场景包（默认 dorm3d_pptr_resolve.DEF_SCENE）")
    ap.add_argument("--blend-only", action="store_true", help="只列会被判成 BLEND 的材质")
    a = ap.parse_args()

    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
    import dorm3d_pptr_resolve as P
    import dorm3d_room_to_gltf as A

    scene = a.scene or P.DEF_SCENE
    ctx = A.scene_ctx(scene)
    own, res = ctx["own"], ctx["res"]
    rows, seen = [], set()
    for o in ctx["env"].objects:
        if o.type.name not in ("MeshRenderer", "SkinnedMeshRenderer"):
            continue
        for pp in list(getattr(o.read(), "m_Materials", None) or []):
            pid = getattr(pp, "path_id", 0) or 0
            if not pid:
                continue
            b, cab, p2 = res.classify(o.assets_file, pp)
            t, _e = res.fetch(own, b, cab, p2)
            if t is None or t.type.name != "Material":
                continue
            key = (P.cab_key(t.assets_file.name), p2)
            if key in seen:
                continue
            seen.add(key)
            sp = t.read().m_SavedProperties
            fl = dict(list(getattr(sp, "m_Floats", None) or []))
            co = dict(list(getattr(sp, "m_Colors", None) or []))
            base = co.get("_BaseColor") or co.get("_Color")
            alpha = float(getattr(base, "a", 1.0)) if base is not None else 1.0
            blend_eq = (fl.get("_SrcBlend") is not None and fl.get("_DstBlend") is not None
                        and abs(float(fl["_SrcBlend"]) - 5.0) < 1e-4
                        and abs(float(fl["_DstBlend"]) - 10.0) < 1e-4)
            rows.append({"name": t.read().m_Name, "alpha": alpha, "blend_eq": blend_eq,
                         "cutoff": fl.get("_Cutoff"),
                         "present": {k: fl.get(k) for k in KEYS if k in fl}})

    if not a.blend_only:
        print("材质实例 %d 个（去重后）" % len(rows))
        for k in ("_Surface", "_Mode", "_Cutoff", "_AlphaClip", "_SrcBlend"):
            print("  %-11s 分布: %s" % (k, Counter(str(r["present"].get(k)) for r in rows).most_common(6)))
        print("  baseColor.a<1: %d 个 | 混合方程=SrcAlpha/OneMinusSrcAlpha: %d 个"
              % (sum(1 for r in rows if r["alpha"] < 0.999), sum(1 for r in rows if r["blend_eq"])))
        print("  ⚠ 若按 _Cutoff 判 alpha 测试，会误伤 %d 个材质（含不透明的墙/木头）"
              % sum(1 for r in rows if r["cutoff"] not in (None, 0.0)))
    hit = [r for r in rows if r["blend_eq"] or r["alpha"] < 0.999]
    print("\n按「混合方程 或 baseColor.a<1」判成 BLEND 的：%d 个" % len(hit))
    for r in sorted(hit, key=lambda x: x["name"]):
        print("   %-40s a=%-6s 混合方程=%s  _Cutoff=%s"
              % (r["name"][:40], round(r["alpha"], 3), r["blend_eq"], r["cutoff"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
