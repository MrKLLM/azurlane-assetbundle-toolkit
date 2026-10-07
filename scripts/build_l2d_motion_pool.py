# -*- coding: utf-8 -*-
"""build_l2d_motion_pool.py — 从源包 AnimatorController 抽「主界面轮播池」，产出 L2D/motion_pool.json。

为什么要它：画廊此前把 Live2D 永远停在 `idle` 这一条 clip 上，而游戏侧是**多条 clip 轮播**的。
gezi_2 实测（scripts/diag/l2d_motion_param_probe.py，采样窗盖过整条 clip）：
    idle   → 14 个花瓣参数里 0 个会动
    main_1 → 10 个会动（且要到第 8.12 秒才开始）
    home   → 会动
所以"花瓣冻住"不是导出丢曲线，是**只播一条 clip**。

池子按控制器自己的命名定，不按我们的猜测：
  · 状态机里有一条子状态机就叫 `idle_list`（另有 `touch_idle_list`/`touch_drag`/`ex`），
    它的成员是"待机轮播"的权威清单；
  · 再并上顶层状态里名为 `idle` / `main_<n>` / `home` 的那几条 —— `main_*`/`home` 是主界面
    动作（花瓣/氛围球就靠它们），`touch_*` 是点击反应、`login`/`mail`/`mission`/`wedding`
    是场景专用，都不该进待机轮播；
  · 状态 → clip 名走 `m_StateConstantArray[i].m_FullPathID` ↔ `m_TOS` 实例号 ↔ 名字，
    clip 索引走 BlendTree 根节点的 `m_ClipID`（Selector 状态没有自己的 clip，跳过）。
只保留**盘上真有 motion3.json** 的组名，且必须与模型自己的 model3.json 的 Motions 键对得上
（对不上就是前端播不到，宁可不放进池）。

用法:
  py -3 scripts/build_l2d_motion_pool.py                 # 全量，写 Output/L2D/motion_pool.json
  py -3 scripts/build_l2d_motion_pool.py --keys gezi_2 --print
  py -3 scripts/build_l2d_motion_pool.py --out .diag/pool.json
"""
import argparse
import json
import os
import re
import sys

import UnityPy

UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L2D = os.path.join(ROOT, "Output", "Live2D")
BUNDLES = os.path.join(ROOT, "files", "AssetBundles", "live2d")
OUT = os.path.join(L2D, "motion_pool.json")

TOP_OK = re.compile(r"^(idle|home|main_\d+)$")
SUB_OK = re.compile(r"^idle_list$")


def deref(x):
    return x.data if hasattr(x, "data") else x


def deref_list(seq):
    return [deref(x) for x in (seq or [])]


def model_groups(key):
    """模型自己 model3.json 里真的有哪些动作组（前端只能播这些）。"""
    f = os.path.join(L2D, key, "%s.model3.json" % key)
    if not os.path.exists(f):
        return set()
    j = json.load(open(f, encoding="utf-8"))
    return set((j.get("FileReferences", {}) or {}).get("Motions", {}) or {})


def pool_for_model(key):
    """返回 (pool, note)。pool 是按"先 idle 再其余"排好的组名列表。"""
    bundle = os.path.join(BUNDLES, key)
    if not os.path.exists(bundle):
        return None, "无源包"
    try:
        env = UnityPy.load(bundle)
    except Exception as e:
        return None, "load 失败 %s" % repr(e)[:80]
    ac = None
    clip_names = {}
    for o in env.objects:
        if o.type.name == "AnimationClip":
            d = o.read()
            clip_names[o.path_id] = str(d.m_Name)
        elif o.type.name == "AnimatorController":
            ac = o.read()
    if ac is None:
        return None, "无 AnimatorController"
    id2name = {i: n for i, n in (ac.m_TOS or []) if isinstance(n, str)}
    cc = ac.m_Controller
    clips = [clip_names.get(p.path_id) for p in ac.m_AnimationClips or []]
    machines = deref_list(cc.m_StateMachineArray)
    if not machines:
        return None, "无状态机"
    # 层 0 才是 pose 层（层 1 是常驻 effect 环境层，不参与轮播）
    sm = machines[0]
    found = set()
    for st in deref_list(getattr(sm, "m_StateConstantArray", None)):
        fp = getattr(st, "m_FullPathID", None) or getattr(st, "m_PathID", None)
        path = id2name.get(fp)
        if not path:
            continue
        trees = deref_list(getattr(st, "m_BlendTreeConstantArray", None))
        if not trees:
            continue                       # Selector 状态没有自己的 clip
        nodes = deref_list(getattr(trees[0], "m_NodeArray", None))
        if not nodes:
            continue
        cid = getattr(nodes[0], "m_ClipID", None)
        clip = clips[cid] if cid is not None and 0 <= cid < len(clips) else None
        if not clip:
            continue
        parts = path.split(".")
        if len(parts) == 2 and TOP_OK.match(parts[1]):
            found.add(clip)
        elif len(parts) >= 3 and SUB_OK.match(parts[1]):
            found.add(clip)
    if not found:
        return None, "控制器里没匹配到 idle_list/main_*/home"
    have = model_groups(key)
    if not have:
        return None, "读不到 model3.json 的 Motions"
    pool = sorted(found & have)
    missing = sorted(found - have)
    note = ("池 %d 条" % len(pool)) + ("；控制器有但盘上没导出的组: %s" % missing if missing else "")
    if "idle" in pool:
        pool.remove("idle")
        pool.insert(0, "idle")
    return pool, note


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", default="", help="逗号分隔，默认扫全部 Output/Live2D 下的模型")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--print", dest="do_print", action="store_true")
    a = ap.parse_args()

    keys = [k for k in a.keys.split(",") if k] if a.keys else sorted(
        d for d in os.listdir(L2D)
        if os.path.isdir(os.path.join(L2D, d)) and not d.startswith("_")
        and os.path.exists(os.path.join(L2D, d, "%s.model3.json" % d)))
    out = {}
    stats = {}
    for i, k in enumerate(keys, 1):
        pool, note = pool_for_model(k)
        stats[note.split("；")[0].split(" ")[0]] = stats.get(note.split("；")[0].split(" ")[0], 0) + 1
        if pool:
            out[k] = pool
        if a.do_print:
            print("%-22s %-6s %s" % (k, len(pool or []), note))
        if i % 25 == 0:
            print("  ...%d/%d" % (i, len(keys)), flush=True)
    import collections
    sizes = collections.Counter(len(v) for v in out.values())
    print("\n模型 %d 个，产出池 %d 个" % (len(keys), len(out)))
    print("池大小分布:", sorted(sizes.items())[:12])
    n1 = sum(1 for v in out.values() if len(v) <= 1)
    print("池 <=1 条（等于没轮播）的模型: %d" % n1)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0, sort_keys=True)
    print("已写 %s (%.1f KB)" % (a.out, os.path.getsize(a.out) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
