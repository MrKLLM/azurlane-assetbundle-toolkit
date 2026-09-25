"""
增量同步 MuMu 模拟器内碧蓝航线资源到本地。

与 mumu_adb.py 的整目录拉取不同，本工具只拉「本地没有」的文件，
避免每次更新都重传几十 GB。

用法:
  python mumu_sync.py diff                 只读对比，列出新增/缺失文件（不下载）
  python mumu_sync.py sync                 dry-run，只报告将要下载什么
  python mumu_sync.py sync --apply         实际下载
  python mumu_sync.py sync --apply --limit 20   先拉 20 个做样本测试

前置条件：MuMu 模拟器已启动。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

# 中国版 MuMu 12 装在 Netease\MuMu，旧版 / 国际版装在 Netease\MuMuPlayer。
# 两个都列出来，谁存在就用谁，避免升级后路径失效。
ADB_CANDIDATES = [
    r"C:\Program Files\Netease\MuMu\nx_main\adb.exe",
    r"C:\Program Files\Netease\MuMuPlayer\nx_main\adb.exe",
]
ADB = next((p for p in ADB_CANDIDATES if os.path.exists(p)), ADB_CANDIDATES[0])

MUMU_MANAGER_CANDIDATES = [
    p.replace("adb.exe", "MuMuManager.exe") for p in ADB_CANDIDATES
]
MUMU_MANAGER = next(
    (p for p in MUMU_MANAGER_CANDIDATES if os.path.exists(p)), None)

# MuMu 12 的 adb 端口是动态分配的：同一个模拟器重启后会变（实测 index 0
# 在 16384 / 16385 之间跳），多开时还按 16384 + index * 32 排布
# （index 1 是 16416），扫小范围会漏掉多开实例。
# 所以优先从 MuMuManager 读真实端口，读不到再兜底扫描。
ADB_PORT_RANGE = range(16384, 16500)
HOST = None
REMOTE_ROOT = "/sdcard/Android/data/com.bilibili.azurlane/files"
LOCAL_ROOT = r"D:\Azur Lane Assets\files"

# 只同步这些顶层子目录；留空表示全部
ONLY_TOP = ["AssetBundles", "hashes", "version"]


def run(args, timeout=300):
    # 多设备并存时必须用 -s 指定目标，否则 adb 报 "more than one device"。
    # devices/connect/disconnect 本身不需要（也不能）带 -s。
    cmd = [ADB]
    if HOST and args and args[0] not in ("devices", "connect", "disconnect"):
        cmd += ["-s", HOST]
    try:
        proc = subprocess.run(
            cmd + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"超时(>{timeout}s)"
    except FileNotFoundError:
        return -2, "", f"找不到 adb: {ADB}"


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024
    return f"{n:.1f}PB"


def _candidate_ports():
    """优先从 MuMuManager 读各实例真实的 adb 端口，读不到再退回扫描段。

    MuMu 多开时端口按 16384 + index * 32 排布（index 1 是 16416），
    盲扫一小段会漏掉多开实例，所以先问 MuMuManager 要准确答案。
    """
    if MUMU_MANAGER:
        try:
            proc = subprocess.run(
                [MUMU_MANAGER, "info", "-v", "all"],
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                encoding="utf-8", errors="replace", timeout=30,
            )
            data = json.loads(proc.stdout)
            ports = {int(v["adb_port"])
                     for v in data.values()
                     if isinstance(v, dict) and "adb_port" in v}
            if ports:
                return sorted(ports)
        except Exception:
            pass
    return list(ADB_PORT_RANGE)


def connect():
    """自动探测并连接 MuMu 模拟器，成功后把地址回填到全局 HOST。

    MuMu 12 每次启动分配的 adb 端口都可能变，写死必然踩坑。
    策略：先看有没有现成的已连接设备，没有就按候选端口逐个试。
    """
    global HOST

    # 1. 已经有连上的设备就直接用
    rc, out, _ = run(["devices"], timeout=30)
    if rc == 0:
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1].strip() == "device" \
                    and parts[0].startswith("127.0.0.1:"):
                HOST = parts[0].strip()
                return True

    # 2. 逐个端口试探，取第一个真正可用的
    for port in _candidate_ports():
        host = f"127.0.0.1:{port}"
        rc, out, _ = run(["connect", host], timeout=15)
        if rc != 0 or "connected" not in out.lower():
            continue
        # connect 成功也可能是 unauthorized / offline，再确认一次状态
        rc2, out2, _ = run(["devices"], timeout=15)
        if rc2 == 0 and re.search(
                r"^" + re.escape(host) + r"\s+device\s*$", out2, re.M):
            HOST = host
            return True
        run(["disconnect", host], timeout=10)

    return False


def remote_files(root):
    """获取模拟器内全部文件的 {相对路径: 大小} 字典。

    adb shell stdout 会被 buffer 截断（实测 ~20KB），所以不能一次 ls -lR。
    策略：ls -1 拿顶层 + for 循环 stat 顶层（类型+大小），再对每个子目录单独
    find -exec stat -c "%s %n" {} + 一次拿。
    """
    sizes = {}

    # 1. ls -1 拿顶层名
    rc, out, err = run(["shell", f"ls -1 '{root}' 2>/dev/null"], timeout=60)
    if rc != 0:
        raise RuntimeError(f"ls 顶层失败: {err.strip()}")
    top_names = [n.strip() for n in out.split() if n.strip()]

    # 2. 一次 adb 调用：用 for 循环 stat 顶层（避免 ARG_MAX）
    if top_names:
        rc, out, _ = run(
            ["shell",
             f"cd '{root}' && for f in *; do stat -c '%F|%s' \"$f\"; done 2>/dev/null"],
            timeout=120,
        )
        if rc == 0:
            lines = out.splitlines()
            for name, line in zip(top_names, lines):
                line = line.strip()
                if '|' not in line:
                    continue
                ftype, sz = line.split('|', 1)
                # 目录本身不记录，它下面的文件由第 3 步 find 收集
                if 'directory' in ftype:
                    continue
                if sz.isdigit():
                    sizes[name] = int(sz)

    # 3. 对每个顶层目录递归拿所有文件
    #    adb shell stdout 会被 buffer 截断，所以子项过多时分块拉取
    for name in top_names:
        sub_root = f"{root}/{name}"
        rc, _, _ = run(["shell", f"[ -d '{sub_root}' ] && echo Y"], timeout=10)
        if rc != 0:
            continue
        rc, out, _ = run(["shell", f"ls -1 '{sub_root}' 2>/dev/null"], timeout=30)
        if rc != 0:
            continue
        sub_names = [s.strip() for s in out.split() if s.strip()]
        if not sub_names:
            continue
        # 超过 30 个子项就分块，避免单次输出过大被截断
        blocks = ([sub_names] if len(sub_names) <= 30
                  else [sub_names[i:i + 30] for i in range(0, len(sub_names), 30)])
        for block in blocks:
            for ss in block:
                rc, out, _ = run(
                    ["shell",
                     f"find '{sub_root}/{ss}' -type f -exec stat -c '%s %n' {{}} + 2>/dev/null"],
                    timeout=120,
                )
                if rc != 0:
                    continue
                for line in out.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    # 输出格式是 "<size> <path>"，必须先切开再比对路径前缀
                    sp = line.split(None, 1)
                    if len(sp) != 2 or not sp[0].isdigit():
                        continue
                    path = sp[1].replace("\\", "/")
                    if not path.startswith(root + "/"):
                        continue
                    sizes[path[len(root) + 1:]] = int(sp[0])

    return sizes


def local_files(root):
    """获取本地全部文件的 {相对路径: 大小} 字典。"""
    sizes = {}
    root_p = Path(root)
    if not root_p.exists():
        return sizes
    for dirpath, _, filenames in os.walk(root):
        dp = Path(dirpath)
        for fn in filenames:
            fp = dp / fn
            try:
                size = fp.stat().st_size
            except OSError:
                continue
            rel = fp.relative_to(root_p).as_posix()
            sizes[rel] = size
    return sizes


def wanted(rel, only_top):
    """判断该文件是否在关注范围内。"""
    if not only_top:
        return True
    top = rel.split("/")[0]
    return any(top.startswith(t) for t in only_top)


def stat_remote(rel):
    """获取单个模拟器文件大小。"""
    rc, out, _ = run(["shell", f"stat -c %s '{REMOTE_ROOT}/{rel}' 2>/dev/null"], timeout=30)
    if rc == 0 and out.strip().isdigit():
        return int(out.strip())
    return 0


def cmd_diff(args):
    if not connect():
        print(f"✗ 连不上模拟器（已扫端口 {ADB_PORT_RANGE.start}-{ADB_PORT_RANGE.stop - 1}），"
              f"请先启动 MuMu 再试")
        return 1

    print("读取模拟器文件列表...")
    r_files = remote_files(REMOTE_ROOT)
    print(f"  模拟器: {len(r_files)} 个文件")

    print("扫描本地文件...")
    l_files = local_files(LOCAL_ROOT)
    print(f"  本地  : {len(l_files)} 个文件")

    # 三类差异：新增 / 大小不一致（同名但本地旧）/ 本地独有
    added = sorted(x for x in r_files.keys() - l_files.keys() if wanted(x, ONLY_TOP))
    size_diff = sorted(
        x for x in r_files.keys() & l_files.keys()
        if wanted(x, ONLY_TOP) and r_files[x] != l_files[x]
    )
    missing = sorted(x for x in l_files.keys() - r_files.keys() if wanted(x, ONLY_TOP))

    by_top = defaultdict(int)
    for f in added:
        by_top[f.split("/")[0]] += 1
    by_top_diff = defaultdict(int)
    for f in size_diff:
        by_top_diff[f.split("/")[0]] += 1

    print(f"\n== 新增（模拟器有，本地没有）: {len(added)} 个 ==")
    for top, n in sorted(by_top.items(), key=lambda x: -x[1]):
        print(f"  {top:<20} {n}")

    if size_diff:
        print(f"\n== 大小不一致（同名同路径但本地旧版本）: {len(size_diff)} 个 ==")
        for top, n in sorted(by_top_diff.items(), key=lambda x: -x[1]):
            print(f"  {top:<20} {n}")
        # 列出大小差异最大的前 10 个（最值得关注）
        size_diff_with_delta = sorted(
            size_diff, key=lambda x: -abs(r_files[x] - l_files[x])
        )[:10]
        print("\n差异最大的 10 个（建议优先同步）:")
        for f in size_diff_with_delta:
            print(f"  本地 {l_files[f]:>12,} B  →  模拟器 {r_files[f]:>12,} B  "
                  f"  Δ {r_files[f] - l_files[f]:>+,} B  {f}")

    if missing:
        print(f"\n== 本地独有（模拟器已删除）: {len(missing)} 个 ==")
        for f in missing[:10]:
            print(f"  {f}")
        if len(missing) > 10:
            print(f"  ... 还有 {len(missing) - 10} 个")
    else:
        print("\n== 本地独有: 0 个 ==")

    if added or size_diff:
        print(f"\n下一步：python mumu_sync.py sync --apply   # 同步新增+更新")
    return 0


def cmd_sync(args):
    if not connect():
        print(f"✗ 连不上模拟器（已扫端口 {ADB_PORT_RANGE.start}-{ADB_PORT_RANGE.stop - 1}），"
              f"请先启动 MuMu 再试")
        return 1

    r_files = remote_files(REMOTE_ROOT)
    l_files = local_files(LOCAL_ROOT)

    # 同步 = 新增 ∪ 大小不一致
    added = sorted(x for x in r_files.keys() - l_files.keys() if wanted(x, ONLY_TOP))
    size_diff = sorted(
        x for x in r_files.keys() & l_files.keys()
        if wanted(x, ONLY_TOP) and r_files[x] != l_files[x]
    )
    targets = sorted(set(added) | set(size_diff))

    if not targets:
        print("✓ 本地已是最新（路径+大小全部一致）")
        return 0

    if args.limit > 0:
        targets = targets[: args.limit]

    if not args.apply:
        total = sum(r_files[x] for x in targets)
        print(f"[dry-run] 待下载 {len(targets)} 个文件，总计 {human(total)}")
        # 按大小降序列出最大的几个
        largest = sorted(targets, key=lambda x: -r_files[x])[:10]
        for f in largest:
            print(f"  {human(r_files[f]):>10}  {f}")
        print("[dry-run] 加 --apply 才会真正下载")
        return 0

    print(f"开始下载 {len(targets)} 个文件 → {LOCAL_ROOT}")
    ok, fail = 0, 0
    t0 = time.time()
    for i, rel in enumerate(targets, 1):
        local_path = Path(LOCAL_ROOT) / rel
        # 本地若误建了同名空目录（旧版同步的 bug），尝试清掉；
        # 沙箱环境下删除可能被安全策略拒绝，失败就跳过，不影响 pull 覆盖文件
        if local_path.is_dir():
            try:
                import shutil
                shutil.rmtree(local_path)
            except Exception:
                pass
        local_path.parent.mkdir(parents=True, exist_ok=True)
        # 不预先删除本地旧文件：adb pull 会直接覆盖，删除反而可能被安全策略拦截
        rc, out, err = run(["pull", "-a", f"{REMOTE_ROOT}/{rel}", str(local_path)], timeout=900)
        if rc == 0:
            ok += 1
        else:
            fail += 1
            print(f"  ✗ {rel}: {err.strip()[:100]}")
        if i % 50 == 0 or i == len(targets):
            elapsed = time.time() - t0
            speed = i / elapsed if elapsed > 0 else 0
            print(f"  进度 {i}/{len(targets)}  成功={ok} 失败={fail}  "
                  f"({speed:.1f} 文件/秒)")

    print(f"\n✓ 完成: 成功 {ok}，失败 {fail}，耗时 {time.time() - t0:.1f}s")
    return 0 if fail == 0 else 1


def main():
    global REMOTE_ROOT, LOCAL_ROOT
    p = argparse.ArgumentParser(description="增量同步模拟器碧蓝航线资源到本地")
    p.add_argument("--remote", default=REMOTE_ROOT, help="模拟器源目录")
    p.add_argument("--local", default=LOCAL_ROOT, help="本地目标目录")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("diff", help="只读对比").set_defaults(func=cmd_diff)

    sp = sub.add_parser("sync", help="同步新增文件")
    sp.add_argument("--apply", action="store_true", help="实际下载（默认 dry-run）")
    sp.add_argument("--limit", type=int, default=0, help="只处理前 N 个，0=全部")
    sp.set_defaults(func=cmd_sync)

    args = p.parse_args()
    REMOTE_ROOT = args.remote
    LOCAL_ROOT = args.local
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
