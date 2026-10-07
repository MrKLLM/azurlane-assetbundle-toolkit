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


def clip_weight(key, group, cap=40.0):
    """返回 (运动量, 时长)。运动量 = 每个被非常值驱动的参数的 |max-min| 之和 / 时长。
    ⚠️ 单个参数的位移要**封顶**（默认 40）：moc3 合法量程多在 [-30,30]/[0,10]/[0,1]，
       而曲线写 0→2000 的那种会被 Cubism 钳位（实测 `Paramfh` 恒读 10），不封顶就会让
       一条根本不动的斜坡把权重顶上天。这个量只用来**排轮播概率**，不是保真判据。
    ⚠️ 权重取**每秒位移**（这条 clip 有多活），但前端必须配一个**最短驻留**：gezi_2 池里
       idle13 只有 3.72 秒、idle5 3.35 秒，按每秒算它们 748/734 霸榜，不压住就是每 3 秒一切，
       比不切还像抽搐。总位移（idle 2650 / home 3440 / main_1 4600）实测会把画面压回
       均值 32.6‰，追不上游戏录像的 72.9‰ —— 长慢镜并不"活"，只是"长"。
       时长是给前端的：轮播要"在当前 clip 还在循环时提前淡入下一条"，否则旧 clip 先淡出
       塌回基准姿态、新 clip 才淡入 —— 实测那一帧是 8‰ 骤停接 201‰ 暴跳，观感就是抽搐。"""
    f = os.path.join(L2D, key, "motion", "%s.motion3.json" % group)
    if not os.path.exists(f):
        return 0.0, 0.0
    j = json.load(open(f, encoding="utf-8"))
    dur = float((j.get("Meta", {}) or {}).get("Duration") or 0.0)
    tot = 0.0
    for c in j.get("Curves", []):
        if c.get("Target") != "Parameter":
            continue
        s = c.get("Segments") or []
        vals = [s[1]] if len(s) > 1 else []
        i = 2
        while i < len(s):
            if s[i] == 0:
                vals.append(s[i + 2]); i += 3
            elif s[i] == 1:
                vals.append(s[i + 6]); i += 7
            else:
                break
        if len(vals) < 2:
            continue
        d = max(vals) - min(vals)
        if d > 1e-6:
            tot += min(d, cap)
    w = round(tot / dur, 1) if dur > 0 else 0.0
    return w, round(dur, 2)


def reweight(path):
    """只重算权重：读旧的 {key:[组名]} 或 {key:{组:权重}}，写 {key:{组:权重}}。
    不碰成员判定（那要扫 269 个源包，5 分钟；权重只读导出产物，几秒）。"""
    old = json.load(open(path, encoding="utf-8"))
    out = {}
    for k, v in old.items():
        groups = v if isinstance(v, list) else list(v.keys())
        out[k] = {g: list(clip_weight(k, g)) for g in groups}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, sort_keys=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", default="", help="逗号分隔，默认扫全部 Output/Live2D 下的模型")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--print", dest="do_print", action="store_true")
    ap.add_argument("--reweight", default="",
                    help="只给既有的池文件补权重（不重扫源包），传池 json 路径")
    a = ap.parse_args()

    if a.reweight:
        out = reweight(a.reweight)
        sample = out.get("gezi_2") or next(iter(out.values()))
        print("已就地补权重：%d 个模型；样例 gezi_2 = %s" % (len(out), json.dumps(sample, ensure_ascii=False)))
        return 0

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
            out[k] = {g: list(clip_weight(k, g)) for g in pool}
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
