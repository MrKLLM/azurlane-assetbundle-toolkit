# -*- coding: utf-8 -*-
"""只读扫描：源包 AnimatorController 里 `effect` 到底是不是"独立常驻循环层"。

背景：画廊的 Live2D 只播 `idle` 一条 clip，于是 gezi_2 的花瓣（`Paramfh` 0→2000 的 90 秒
单向长坡）永远停在初始位。要判断"补播 effect"是全库正确还是只对一个模型正确，唯一权威
是源包里的 AnimatorController —— 不是 clip 名字，也不是我们的猜测：

  ① 层数、每层 `m_DefaultWeight` 与 `m_LayerBlendingMode`（0=Override / 1=Additive）；
  ② 每层状态机的**默认状态**解析到哪个 AnimationClip 名（`m_ClipID` → `m_AnimationClips`）；
  ③ 该 clip 是否 Loop=true。

只有"某层默认状态 = 名为 effect 的 clip"成立，才可以说"游戏里 effect 常驻播放"。
判红条件：解析不出层/默认状态，或 effect 不是任何层的默认状态。

用法:
  py -3 scripts/diag/l2d_effect_layer_scan.py                 # 扫全部有 effect.motion3.json 的模型
  py -3 scripts/diag/l2d_effect_layer_scan.py --keys gezi_2,aerbien_3
  py -3 scripts/diag/l2d_effect_layer_scan.py --out .diag/effect_layer_scan.json
"""
import argparse
import json
import os
import sys

import UnityPy
from PIL import Image  # noqa: F401  (仅确保依赖栈一致，本脚本不使用)

UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
L2D = os.path.join(ROOT, "Output", "Live2D")
BUNDLES = os.path.join(ROOT, "files", "AssetBundles", "live2d")


def deref(x):
    """UnityPy 把大量字段包成 OffsetPtr，统一取 .data。"""
    return x.data if hasattr(x, "data") else x


def clip_names(controller):
    """m_AnimationClips 是 PPtr 列表，按 path_id 反查 clip 名，保持控制器内的索引次序。"""
    env = controller.assets_file
    names = []
    for pptr in controller.m_AnimationClips or []:
        try:
            o = env.objects[pptr.path_id]
            names.append(str(o.read().m_Name))
        except Exception:
            names.append("?%s" % getattr(pptr, "path_id", "?"))
    return names


def state_clip_name(state):
    """StateConstant → BlendTree 根节点 → m_ClipID；Selector 状态没有自己的 clip。"""
    trees = deref_list(getattr(state, "m_BlendTreeConstantArray", None))
    if not trees:
        return None
    nodes = deref_list(getattr(trees[0], "m_NodeArray", None))
    if not nodes:
        return None
    return getattr(nodes[0], "m_ClipID", None)


def deref_list(seq):
    return [deref(x) for x in (seq or [])]


def scan_model(key):
    rec = {"key": key, "verdict": None, "note": ""}
    bundle = os.path.join(BUNDLES, key)
    if not os.path.exists(bundle):
        rec["verdict"] = "no-bundle"
        rec["note"] = "源包不在盘上（可能被 pruned.json 登记删除）"
        return rec
    try:
        env = UnityPy.load(bundle)
    except Exception as e:
        rec["verdict"] = "load-fail"
        rec["note"] = repr(e)[:160]
        return rec
    ac = None
    for o in env.objects:
        if o.type.name == "AnimatorController":
            ac = o.read()
            break
    if ac is None:
        rec["verdict"] = "no-controller"
        return rec
    names = clip_names(ac)
    rec["clips"] = len(names)
    cc = ac.m_Controller
    layers = []
    effect_default = False
    for li, lref in enumerate(deref_list(cc.m_LayerArray)):
        smi = getattr(lref, "m_StateMachineIndex", None)
        sm = None
        machines = deref_list(cc.m_StateMachineArray)
        if smi is not None and 0 <= smi < len(machines):
            sm = machines[smi]
        info = {
            "layer": li,
            "weight": getattr(lref, "m_DefaultWeight", None),
            "blend_mode": getattr(lref, "m_LayerBlendingMode", None),
            "sm": smi,
            "default_clip": None,
            "default_loop": None,
            "states": len(deref_list(getattr(sm, "m_StateConstantArray", None))) if sm else 0,
        }
        if sm is not None:
            states = deref_list(getattr(sm, "m_StateConstantArray", None))
            dflt = getattr(sm, "m_DefaultState", 0) or 0
            info["all_states"] = []
            for si, st in enumerate(states):
                cid = state_clip_name(st)
                cn = names[cid] if (cid is not None and 0 <= cid < len(names)) else None
                info["all_states"].append({
                    "i": si, "clip": cn,
                    "speed": getattr(st, "m_Speed", None),
                    "speed_param_active": getattr(st, "m_SpeedParameterActive", None),
                    "mirror_param_active": getattr(st, "m_MirrorParameterActive", None),
                    "loop": bool(getattr(st, "m_Loop", False)),
                    "write_default": getattr(st, "m_WriteDefaultValues", None),
                    "default": si == dflt,
                })
            if 0 <= dflt < len(states):
                cid = state_clip_name(states[dflt])
                if cid is not None and 0 <= cid < len(names):
                    info["default_clip"] = names[cid]
                    info["default_loop"] = bool(getattr(states[dflt], "m_Loop", False))
                    info["default_speed"] = getattr(states[dflt], "m_Speed", None)
                    if names[cid] == "effect" and info["default_loop"]:
                        effect_default = True
        layers.append(info)
    rec["layers"] = layers
    rec["verdict"] = "effect-is-resident-layer" if effect_default else "effect-not-default"
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", default="", help="逗号分隔的模型号，默认扫全部有 effect.motion3.json 的")
    ap.add_argument("--out", default="")
    ap.add_argument("--speeds", action="store_true",
                    help="逐层打印每个状态的 clip 名 / m_Speed / Loop（查「我们比游戏快」是不是倍速）")
    args = ap.parse_args()

    if args.keys:
        keys = [k for k in args.keys.split(",") if k]
    else:
        keys = sorted(
            d for d in os.listdir(L2D)
            if os.path.isdir(os.path.join(L2D, d))
            and os.path.exists(os.path.join(L2D, d, "motion", "effect.motion3.json"))
        )
    print("待扫模型 %d 个" % len(keys))
    out = []
    for i, k in enumerate(keys, 1):
        r = scan_model(k)
        out.append(r)
        if i % 10 == 0 or i == len(keys):
            print("  %d/%d %s" % (i, len(keys), r["verdict"]), flush=True)
    if args.speeds:
        for r in out:
            print("\\n== %s  层数 %d ==" % (r["key"], len(r.get("layers") or [])))
            for L in (r.get("layers") or []):
                print('   层%s weight=%s blend=%s(0=Override) 默认=%s loop=%s speed=%s'
                      % (L.get("layer"), L.get("weight"), L.get("blend_mode"),
                         L.get("default_clip"), L.get("default_loop"), L.get("default_speed")))
                for st in (L.get("all_states") or []):
                    print('      %s %-16s speed=%-5s loop=%-5s writeDefault=%-5s speedParam=%s mirrorParam=%s'
                          % ("*" if st["default"] else " ", st["clip"], st["speed"], st["loop"],
                             st["write_default"], st["speed_param_active"], st["mirror_param_active"]))
    import collections
    c = collections.Counter(r["verdict"] for r in out)
    print("\n== 判定分布 ==")
    for kk, vv in c.most_common():
        print("  %-24s %d" % (kk, vv))
    bad = [r for r in out if r["verdict"] != "effect-is-resident-layer"]
    if bad:
        print("\n== 不是「独立常驻层」的模型（前 20）==")
        for r in bad[:20]:
            print("  %-22s %-24s %s" % (r["key"], r["verdict"], json.dumps(r.get("layers"), ensure_ascii=False)[:180]))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print("\n已写 %s" % args.out)
    return 0 if not bad else 3


if __name__ == "__main__":
    sys.exit(main())
