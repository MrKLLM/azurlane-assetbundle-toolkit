# -*- coding: utf-8 -*-
"""
v2 全量批处理驱动：先 Spine 全量提取，再静态立绘全量合成。
支持断点续跑（输出已存在则跳过），错误写入日志，进度实时落盘。

用法（建议后台分离进程运行）:
  py -3 scripts/run_v2_full.py               # 两阶段全量
  py -3 scripts/run_v2_full.py --only spine  # 只跑 Spine
  py -3 scripts/run_v2_full.py --only static # 只跑静态
"""
import argparse
import os
import subprocess
import sys
import time

# Windows 分离进程 stdout 默认 GBK，print('✓') 会 UnicodeEncodeError 导致全量假失败
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
_SUBPROC_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
STATIC_OUT = os.path.join(ROOT, "Output", "Paintings_v2")
SPINE_OUT = os.path.join(ROOT, "Output", "Spine_v2")
BASELINE_DIR = os.path.join(ROOT, "Output", "Paintings_Synthesized")
PAINTING_DIR = os.path.join(ROOT, "files", "AssetBundles", "painting")
PROGRESS_LOG = os.path.join(ROOT, "Output", "run_v2_full.progress.log")
ERROR_LOG = os.path.join(ROOT, "Output", "run_v2_full.errors.log")


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def baseline_targets():
    """合成目标主皮肤名。

    根因修复：旧版只从 v1 基线目录取名，导致 v1 里没有的皮肤（联动舰 2b/a2 等
    约 180 个真实主皮肤）永远不会被合成。改为以真实源包
    files/AssetBundles/painting/ 为准枚举主皮肤包（排除部件纹理包 _tex、资源包
    _res、投影层 _dark_shadow、表情差分 _face），并与旧基线取并集，保证不回退。
    """
    names = set()
    # 非主皮肤的部件/材质/杂项 bundle 名后缀（不带 _tex 但仍是子部件）
    PART_SUFFIX = ("_rw", "_bj", "_front", "_jz", "_bg", "_shadow", "_shophx", "_mat")
    def is_main(fn):
        if fn.endswith("_tex") or fn.endswith("_res"):
            return False
        if "_dark_shadow" in fn or "_face" in fn:
            return False
        if fn == "mat" or fn.startswith("mat_"):
            return False
        if any(fn.endswith(s) for s in PART_SUFFIX):
            return False
        return True
    # 1) 真实源包：painting/<name>（不带 _tex/_res 后缀的即主皮肤包）
    if os.path.isdir(PAINTING_DIR):
        for fn in os.listdir(PAINTING_DIR):
            if not os.path.isfile(os.path.join(PAINTING_DIR, fn)):
                continue
            if is_main(fn):
                names.add(fn)
    # 2) 旧基线并集（兜底，防源包命名差异导致遗漏）
    for fn in os.listdir(BASELINE_DIR):
        if not fn.endswith(".png"):
            continue
        base = fn[:-4]
        if "_dark_shadow" in base or "_face" in base:
            continue
        names.add(base)
    return sorted(names)


def run_spine():
    log("== 阶段1：Spine 全量提取 ==")
    d = os.path.join(ROOT, "files", "AssetBundles", "spinepainting")
    names = sorted(f for f in os.listdir(d)
                   if os.path.isfile(os.path.join(d, f)) and not f.endswith("_res"))
    todo = [n for n in names
            if not (os.path.isdir(os.path.join(SPINE_OUT, n))
                    and os.listdir(os.path.join(SPINE_OUT, n)))]
    log(f"spine 主包 {len(names)}，待提取 {len(todo)}")
    t0 = time.time()
    # 分批传给 extract_spine_v2（每批 25 个，避免单进程内存累积）
    for i in range(0, len(todo), 25):
        batch = todo[i:i + 25]
        p = subprocess.run([PY, os.path.join(HERE, "extract_spine_v2.py")] + batch,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=_SUBPROC_ENV)
        for ln in (p.stdout or "").splitlines():
            if ln.startswith("✗"):
                with open(ERROR_LOG, "a", encoding="utf-8") as f:
                    f.write(f"[spine] {ln}\n")
        done = min(i + 25, len(todo))
        if done % 100 < 25 or done == len(todo):
            el = time.time() - t0
            log(f"spine 进度 {done}/{len(todo)}  用时 {el:.0f}s")
    log("Spine 阶段完成")


def run_static():
    log("== 阶段2：静态立绘全量合成 ==")
    targets = baseline_targets()
    todo = [n for n in targets
            if not os.path.isfile(os.path.join(STATIC_OUT, n + ".png"))]
    log(f"目标 {len(targets)}，待合成 {len(todo)}")
    os.makedirs(STATIC_OUT, exist_ok=True)
    sys.path.insert(0, HERE)
    import compose_paintings_v2 as v2
    t0 = time.time()
    ok = fail = 0
    for i, n in enumerate(todo, 1):
        try:
            good = v2.compose(n, STATIC_OUT)
        except Exception as e:
            good = False
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(f"[static] {n}: {type(e).__name__}: {e}\n")
        if good:
            ok += 1
        else:
            fail += 1
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(f"[static] {n}: 失败（无异常，部件为空或渲染全跳过）\n")
        if i % 50 == 0 or i == len(todo):
            el = time.time() - t0
            eta = el / i * (len(todo) - i)
            log(f"static 进度 {i}/{len(todo)}  ok={ok} fail={fail}  "
                f"用时 {el:.0f}s  预计剩余 {eta:.0f}s")
    log(f"静态阶段完成：ok={ok} fail={fail}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["spine", "static"])
    args = ap.parse_args()
    if args.only != "static":
        run_spine()
    if args.only != "spine":
        run_static()
    log("== 全部完成 ==")


if __name__ == "__main__":
    main()
