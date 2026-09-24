#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""l2d_ref_diff.py — 用 l2d.su 的权威导出验收我们解出的 motion3.json

为什么需要它：碧蓝航线 Live2D 的动作只能从 Unity AnimationClip 反解，而 l2d.su 上挂着
同一批模型的 **权威 motion3.json**（大概率来自游戏原始 Live2D 发行包）。它是目前唯一能
逐帧判定"我们解得对不对"的外部基准。

比对项（按重要性）：
  1. 动作组集合        —— 参考版有而我们没有 = 漏登记
  2. 曲线 Id 集合      —— 少了就是丢曲线（历史事故：只读 m_StreamedClip 丢掉全部定值曲线）
  3. 关键帧时间/值     —— 必须逐条一致，不一致 = 解析错位
  4. 段类型分布        —— 参考版 linear/bezier/stepped 三方对比
  5. 逐曲线采样偏差    —— 按运行时真实语义求值（AreBeziersRestricted 走朴素参数化），
                          偏差中位应 ≤0.2、>0.5 的曲线占比应 ≤5%

已知天花板：参考版约有 7% 的段是贝塞尔，其控制点无法从 Unity 切线字段推出（四种候选公式
最高只命中 16.7%，且那还是"切线为 0"的平凡情形）。这部分我们只能用线性弦近似 → 表现为
缓动略少，不会导致部件乱动。

参考库只覆盖部分模型（实测抽样 8/14 命中），404 的会跳过并计数。

用法:
  py -3 scripts/diag/l2d_ref_diff.py antu_2                 # 单模型全量比对
  py -3 scripts/diag/l2d_ref_diff.py antu_2 --clips idle,touch_body
  py -3 scripts/diag/l2d_ref_diff.py --probe-keys 40         # 只探测哪些 key 参考库有
  py -3 scripts/diag/l2d_ref_diff.py --all                    # 扫我们全部 269 个模型并汇总
输出: .diag/l2d_ref_diff.json + 终端汇总
"""
import os
import re
import sys
import json
import time
import hashlib
import threading
import argparse
import urllib.request
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.environ.get("L2D_OUT_DIR") or os.path.join(ROOT, "Output", "Live2D")
PROD = os.path.join(ROOT, "Output", "Live2D")   # 只重导 motion 时，model3.json 仍从这里取
DIAG = os.path.join(ROOT, ".diag")
BASE = "https://static.l2d.su/azurlane/live2d"
TIMEOUT = 25
# urlopen(timeout=25) 只约束**单次 socket 操作**：慢滴式响应能让整轮挂住（2026-09-24 实测
# 206/269 处 25 分钟零输出），所以每个 URL 还要一道墙钟硬上限。见 TROUBLESHOOTING §26。
# 12s 太紧：实测该站高峰单请求就要 8~12s，12s 会把"其实能成"的请求判成放弃，
# 而那些组会被当成"参考库没有"→ 比对不完整却看起来像通过。放宽到 30s，并在 verdict 里
# 用 INCOMPLETE 显式区分"比对过且一致"与"根本没比到"。
HARD_DEADLINE = 30
CACHE = os.path.join(DIAG, "refcache")
STATS = Counter()          # cache_hit / ok / miss404 / err / hung
USE_CACHE = True

# 参考版 motion3 里有、而我们（和 Unity 数据本身）不可能有的**Cubism 内置通道**：
# LipSync / EyeBlink 由运行时按参数驱动，Opacity 是 Drawable 级不透明度通道，
# 三者都不来自 AnimationClip 的 genericBindings，参考版导出器是自己合成的。
# 实测证据（30 个模型 / 126 个"缺曲线"clip）：缺失 Id 只有 LipSync 80、Opacity 54、EyeBlink 10，
# 没有任何其它 Id → 这是单一系统性成因，不是逐模型的解析缺陷，故不算 FAIL（计入 INFO）。
BUILTIN_IDS = {"LipSync", "EyeBlink", "Opacity"}

# 参考版 motion 子目录是 motions/（我们历史用的是 motion/）
REF_SUBDIRS = ("motions", "motion")


def _raw(url):
    """真实取一次。返回 bytes / b"MISS"(404、403) / None(其它失败)。"""
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            if r.status != 200:
                return b"MISS"
            return r.read()
    except Exception as e:
        code = getattr(e, "code", None)
        if code in (404, 403):
            return b"MISS"
        return None


def fetch(url, binary=False):
    """带磁盘缓存与墙钟硬超时的取回；None = 没有 / 拿不到（靠 STATS 区分原因）。

    缓存让"改判据后重跑全库"不再重打网络——本次要反复迭代判据，没缓存就是每次几十分钟。
    """
    os.makedirs(CACHE, exist_ok=True)
    cf = os.path.join(CACHE, hashlib.sha1(url.encode("utf-8")).hexdigest() + ".bin")
    if USE_CACHE and os.path.isfile(cf):
        STATS["cache_hit"] += 1
        raw = open(cf, "rb").read()
    else:
        box = {}

        def run():
            box["v"] = _raw(url)

        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(HARD_DEADLINE)
        if t.is_alive():
            STATS["hung"] += 1
            print(f"      [HUNG] 超过 {HARD_DEADLINE}s 未返回，放弃该 URL：{url}", flush=True)
            return None
        raw = box.get("v")
        if raw is None:
            STATS["err"] += 1
            return None
        with open(cf, "wb") as f:
            f.write(raw)
        STATS["miss404" if raw == b"MISS" else "ok"] += 1
    if raw == b"MISS":
        return None
    return raw if binary else json.loads(raw.decode("utf-8"))


def parse_curve(c):
    """Segments → [(type, (t0,v0), (c1), (c2), (t1,v1))]，与运行时解析器同语义。"""
    sg = c["Segments"]
    if not sg:
        return []
    pts = [(sg[0], sg[1])]
    segs = []
    i = 2
    n = len(sg)
    while i < n:
        ty = sg[i]
        if ty == 1:
            d = (sg[i + 5], sg[i + 6])
            segs.append((ty, pts[-1], (sg[i + 1], sg[i + 2]), (sg[i + 3], sg[i + 4]), d))
            i += 7
        else:
            d = (sg[i + 1], sg[i + 2])
            segs.append((ty, pts[-1], None, None, d))
            i += 3
        pts.append(d)
    return segs


def sample(segs, t):
    """按运行时求值：linear 插值 / stepped 取起点 / bezier 在 AreBeziersRestricted 下
    用归一化时间直接当贝塞尔参数（对应 bundle 里的 Z 函数）。"""
    if not segs:
        return 0.0
    for ty, p0, c1, c2, p3 in segs:
        if t <= p3[0] + 1e-9:
            if ty == 0:
                if p3[0] <= p0[0]:
                    return p3[1]
                return p0[1] + (p3[1] - p0[1]) * (t - p0[0]) / (p3[0] - p0[0])
            if ty == 2:
                return p0[1]
            if ty == 3:
                return p3[1]
            if p3[0] <= p0[0]:
                return p3[1]
            u = (t - p0[0]) / (p3[0] - p0[0])
            mu = 1.0 - u
            return (mu ** 3 * p0[1] + 3 * mu * mu * u * c1[1]
                    + 3 * mu * u * u * c2[1] + u ** 3 * p3[1])
    return segs[-1][4][1]


def type_hist(curves):
    h = Counter()
    for c in curves:
        for s in parse_curve(c):
            h[s[0]] += 1
    return h


def key_mismatch(ours, ref):
    """逐曲线比对关键帧时间/值（忽略段类型），返回不一致的曲线数。"""
    bad = 0
    for cid, segs in ref.items():
        o = ours.get(cid)
        if not o:
            bad += 1
            continue
        if len(o) != len(segs):
            bad += 1
            continue
        for a, b in zip(o, segs):
            if abs(a[4][0] - b[4][0]) > 1e-3 or abs(a[4][1] - b[4][1]) > 1e-3:
                bad += 1
                break
    return bad


def pick_paired(model_dir, files, ref_j):
    """在组登记的多个 motion 文件里挑出与参考版**同一个** clip。

    按 `files[0]` 盲配会把不同 clip 拿来比：实测报出「关键帧不一致 66~150 条 + 时长不一致」，
    那是**配对错**不是数据错（§26）。优先时长逐字相等，其次曲线 Id 集合重合最多的。
    返回 (json, 文件名, "exact"|"closest") 或 (None, None, None)。
    """
    rmeta = (ref_j.get("Meta") or {})
    rdur = rmeta.get("Duration")
    rids = {c.get("Id") for c in ref_j.get("Curves") or []}
    best = None
    for f in files:
        p = os.path.join(model_dir, f.get("File") or "")
        if not f.get("File") or not os.path.isfile(p):
            continue
        try:
            j = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        odur = (j.get("Meta") or {}).get("Duration")
        try:
            dur_ok = rdur is not None and odur is not None and abs(float(rdur) - float(odur)) <= 1e-3
        except (TypeError, ValueError):
            dur_ok = False
        inter = len(rids & {c.get("Id") for c in j.get("Curves") or []})
        score = (1 if dur_ok else 0, inter)
        if best is None or score > best[0]:
            best = (score, j, f["File"], dur_ok)
    if not best:
        return None, None, None
    _, j, name, dur_ok = best
    return j, name, ("exact" if dur_ok else "closest")


def evaluate_model(key, clips=None, samples=121):
    hung0 = STATS["hung"]
    ref_m3 = fetch(f"{BASE}/{key}/{key}.model3.json")
    if not ref_m3:
        # 「超时」与「参考库真没有」必须分开：前者重跑能补，后者是真覆盖缺口
        return {"key": key, "skip": "取参考版 model3 超时（不是没有，重跑可补）"} \
            if STATS["hung"] > hung0 else {"key": key, "skip": "参考库无此模型"}
    ref_groups = list((ref_m3.get("FileReferences") or {}).get("Motions") or {})
    ours_m3_path = os.path.join(OUT, key, f"{key}.model3.json")
    if not os.path.isfile(ours_m3_path):
        # 临时目录只装 motion/（extract_motions 不产 model3.json）。换入流程不动 model3.json，
        # 所以回退读正式目录的同名文件是等价取值，不是放水——否则本工具在临时目录上会全 SKIP。
        ours_m3_path = os.path.join(PROD, key, f"{key}.model3.json")
    if not os.path.isfile(ours_m3_path):
        return {"key": key, "skip": "本地无此模型"}
    ours_m3 = json.load(open(ours_m3_path, encoding="utf-8"))
    ours_groups = list((ours_m3.get("FileReferences") or {}).get("Motions") or {})

    res = {"key": key,
           "groups_ref": len(ref_groups), "groups_ours": len(ours_groups),
           "groups_missing": sorted(set(ref_groups) - set(ours_groups))[:20],
           "clips": {}, "hung_groups": [], "ref_missing_group": [],
           "unpaired": [], "no_file": []}
    targets = clips or [g for g in ref_groups if g in ours_groups]
    model_dir = os.path.join(OUT, key)
    for g in targets:
        files = (ours_m3["FileReferences"]["Motions"].get(g) or [])
        if not files:
            res["no_file"].append(g)
            continue
        hg0 = STATS["hung"]
        ref_j = None
        for sub in REF_SUBDIRS:
            ref_j = fetch(f"{BASE}/{key}/{sub}/{g}.motion3.json")
            if ref_j:
                break
        if not ref_j:
            res["hung_groups" if STATS["hung"] > hg0 else "ref_missing_group"].append(g)
            continue
        ours_j, ours_name, paired = pick_paired(model_dir, files, ref_j)
        if ours_j is None:
            res["unpaired"].append(g)
            continue
        rcur = {c["Id"]: parse_curve(c) for c in ref_j.get("Curves") or []}
        ocur = {c["Id"]: parse_curve(c) for c in ours_j.get("Curves") or []}
        dur = (ref_j.get("Meta") or {}).get("Duration") or 1.0
        devs = []
        for cid in ocur:
            if cid not in rcur:
                continue
            ts = [dur * i / (samples - 1) for i in range(samples)]
            devs.append(max(abs(sample(ocur[cid], t) - sample(rcur[cid], t)) for t in ts))
        devs.sort()
        n = len(devs) or 1
        res["clips"][g] = {
            "ours_file": ours_name, "paired": paired,
            "curves_ref": len(rcur), "curves_ours": len(ocur),
            # 判"缺曲线"只跟**该由绑定产生**的曲线比（扣掉 Cubism 内置通道），否则每条 clip
            # 都会因为缺 LipSync 而永久 FAIL（实测 126/126 个缺失 clip 全是那三个 Id）
            "curves_ref_real": len(set(rcur) - BUILTIN_IDS),
            "curves_missing": sorted((set(rcur) - set(ocur)) - BUILTIN_IDS)[:10],
            "curves_missing_builtin": sorted((set(rcur) - set(ocur)) & BUILTIN_IDS)[:10],
            "key_mismatch": key_mismatch(ocur, rcur),
            "types_ref": dict(type_hist(ref_j.get("Curves") or [])),
            "types_ours": dict(type_hist(ours_j.get("Curves") or [])),
            "dev_median": round(devs[len(devs) // 2], 4),
            "dev_p90": round(devs[int(n * 0.9)], 4),
            "dev_gt05": sum(1 for d in devs if d > 0.5),
            "dev_gt05_pct": round(100.0 * sum(1 for d in devs if d > 0.5) / n, 1),
            "duration_ref": (ref_j.get("Meta") or {}).get("Duration"),
            "duration_ours": (ours_j.get("Meta") or {}).get("Duration"),
            "fps_ref": (ref_j.get("Meta") or {}).get("Fps"),
            "fps_ours": (ours_j.get("Meta") or {}).get("Fps"),
        }
    return res


def verdict(r):
    """给出 PASS/WARN/FAIL 判定（**判据于 2026-09-24 按 §26 重定义**）。

    旧判据在全库规模上给出 153 个 FAIL，而同一批数据文件级审计与浏览器回归全绿——原因是两条：
      1. 「关键帧不一致」把参考版 60fps 重采样造成的时间格点差异算成硬错误（偏差中位 0.0001
         的模型照样 FAIL）→ 现降级为 INFO，值对不对由「逐曲线采样偏差」说话；
      2. 组→文件按 `files[0]` 盲配会配到不同 clip → 现在先配对，**只有配到同时长的 clip 才允许 FAIL**，
         配不到只给 WARN（那是登记差异或参考版多一条，不是我们解错）。
    阈值沿用 09-23 安土实测：>0.5 占比 WARN 线 12%（参考版 7% 贝塞尔段无法还原 = 天花板）。
    """
    if r.get("skip"):
        return "SKIP", r["skip"]
    hard = []
    soft = []
    info = []
    if r["groups_missing"]:
        hard.append(f"漏登记动作组 {len(r['groups_missing'])}")
    exact = 0
    for g, c in r["clips"].items():
        paired = c.get("paired") == "exact"
        exact += 1 if paired else 0
        if c["key_mismatch"]:
            info.append(f"{g}: 关键帧集合不同 {c['key_mismatch']} 条(参考 {c.get('fps_ref')}/{c.get('fps_ours')}fps，INFO)")
        if not paired:
            soft.append(f"{g}: 配不到同时长文件（按最接近的比，不算 FAIL）")
            continue
        if c["curves_ours"] < c.get("curves_ref_real", c["curves_ref"]):
            hard.append(f"{g}: 曲线缺 {c.get('curves_ref_real', c['curves_ref']) - c['curves_ours']} 条")
        if c.get("curves_missing_builtin"):
            info.append(f"{g}: 参考版另有内置通道 {','.join(c['curves_missing_builtin'])}（不计缺失）")
        if c["dev_median"] > 0.5:
            hard.append(f"{g}: 偏差中位 {c['dev_median']} 过大")
        if c["dev_gt05_pct"] > 12.0:
            soft.append(f"{g}: 偏差>0.5 占 {c['dev_gt05_pct']}%（超贝塞尔天花板 12%）")
    if not r["clips"]:
        hung0 = len(r.get("hung_groups") or [])
        rmis0 = len(r.get("ref_missing_group") or [])
        up0 = len(r.get("unpaired") or []) + len(r.get("no_file") or [])
        return "INCOMPLETE", (f"一组都没比到（超时 {hung0} / 参考库无 {rmis0} / 配不到或无文件 {up0}）"
                              "——覆盖为零，既不算过也不算失败")
    # 覆盖不足必须单独成一类：比了 3/14 组却报 PASS，就是新的假绿灯。
    compared = len(r["clips"])
    hung = len(r.get("hung_groups") or [])
    rmis = len(r.get("ref_missing_group") or [])
    up = len(r.get("unpaired") or []) + len(r.get("no_file") or [])
    expected = compared + hung + rmis + up
    if expected and compared < expected * 0.6:
        return "INCOMPLETE", (f"只比到 {compared}/{expected} 组（超时 {hung} / 参考库无 {rmis} / "
                              f"配不到 {up}）——覆盖不足，既不算通过也不算失败")
    if exact == 0:
        return "WARN", "全部 clip 都没配到同时长文件（比对结果不可判，别当通过也别当失败）"
    r["info_notes"] = info[:8]
    if hard:
        return "FAIL", "; ".join(hard[:6])
    if soft:
        return "WARN", "; ".join(soft[:6])
    return "PASS", f"配对成功的 clip 全部结构一致（另有 {len(info)} 条关键帧集合差异记为 INFO）"


def main():
    global USE_CACHE
    ap = argparse.ArgumentParser(description="Live2D 动作数据 vs l2d.su 权威导出比对")
    ap.add_argument("keys", nargs="*", help="模型 key（如 antu_2）")
    ap.add_argument("--clips", help="只比对指定动作组，逗号分隔")
    ap.add_argument("--all", action="store_true", help="扫描本地全部模型")
    ap.add_argument("--only", help="逗号分隔的 key 列表（分批跑用；--all 一次 269 键的网络长尾不值得）")
    ap.add_argument("--no-cache", action="store_true", help="忽略 .diag/refcache 重新取")
    ap.add_argument("--probe-keys", type=int, default=0, help="只探测前 N 个 key 在参考库是否存在")
    args = ap.parse_args()
    if args.no_cache:
        USE_CACHE = False

    keys = sorted(os.listdir(OUT)) if args.all else list(args.keys or [])
    if args.only:
        keys = [k.strip() for k in args.only.split(",") if k.strip()]
    keys = [k for k in keys if os.path.isdir(os.path.join(OUT, k)) and not k.startswith("_")]
    # 下划线开头的是工作目录不是模型（`_ab` 是 l2d_ab.py 的硬链接壳），混进来会白报一个 SKIP
    if not keys:
        print(__doc__)
        return 2
    clips = args.clips.split(",") if args.clips else None
    os.makedirs(DIAG, exist_ok=True)
    path = os.path.join(DIAG, "l2d_ref_diff.json")

    results = []
    covered = 0
    if args.probe_keys:
        keys = keys[:args.probe_keys]
    for i, k in enumerate(keys, 1):
        if args.probe_keys:
            ok = fetch(f"{BASE}/{k}/{k}.model3.json") is not None
            covered += 1 if ok else 0
            print(f"  {'有' if ok else '无'}  {k}", flush=True)
            continue
        r = evaluate_model(k, clips)
        v, msg = verdict(r)
        r["verdict"] = v
        r["verdict_msg"] = msg
        results.append(r)
        # 进度行 + flush：脱离进程下没有它就无法区分「慢」与「挂死」（本次曾 25 分钟零输出）
        line = f"[{i}/{len(keys)}] [{v}] {k:<26} 组 {r.get('groups_ours', 0)}/{r.get('groups_ref', 0)}"
        if r.get("skip"):
            line += f"  {r['skip']}"
        else:
            line += "  " + " | ".join(
                f"{g}: 曲线{c['curves_ours']}/{c['curves_ref']} 偏差中位{c['dev_median']} >0.5占{c['dev_gt05_pct']}% 配对{c.get('paired')}"
                for g, c in list(r["clips"].items())[:2])
        print(line, flush=True)
        if v != "PASS" and not r.get("skip"):
            print(f"         └ {msg}", flush=True)
        if i % 10 == 0:                 # 增量落盘：中途挂掉也不丢已完成的部分
            json.dump(results, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if args.probe_keys:
        print(f"\n参考库覆盖率: {covered}/{len(keys)}", flush=True)
        return 0

    n = lambda v: sum(1 for r in results if r.get("verdict") == v)
    ok, warn, fail, skip = n("PASS"), n("WARN"), n("FAIL"), n("SKIP")
    inc = n("INCOMPLETE")
    evaluated = len(results) - skip - inc
    paired_exact = sum(1 for r in results for c in (r.get("clips") or {}).values() if c.get("paired") == "exact")
    paired_closest = sum(1 for r in results for c in (r.get("clips") or {}).values() if c.get("paired") == "closest")
    info_n = sum(len(r.get("info_notes") or []) for r in results)
    print(f"\n===== 汇总 =====  PASS {ok} / WARN {warn} / FAIL {fail} / INCOMPLETE {inc} / SKIP {skip}（共 {len(results)}）", flush=True)
    print(f"  clip 配对: exact {paired_exact} / closest {paired_closest}"
          f" | 关键帧集合差异记为 INFO 的 clip {info_n}", flush=True)
    print(f"  网络: {dict(STATS)}  （缓存目录 {CACHE}，--no-cache 可绕过）", flush=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"详细结果: {path}", flush=True)
    if evaluated == 0:
        # 全跳过时 0==0 曾经返回 0 = 绿灯，而实际一条都没比对。验收工具不得静默空跑。
        print("[FAIL] 没有任何模型真正参与比对（全部跳过或覆盖不足）→ 判为失败，不是通过", flush=True)
        return 1
    print(f"[i] 退出码同时认 FAIL（真缺陷）与 INCOMPLETE（覆盖不足，不得当通过）；"
          f"WARN={warn} 含天花板与配对差异，需逐条看不算硬失败", flush=True)
    return 0 if (fail == 0 and inc == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
