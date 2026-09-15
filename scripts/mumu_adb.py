"""
MuMu 模拟器 ADB 文件操作工具 —— 不用在模拟器界面里点来点去。

用法:
  python mumu_adb.py info                          连接模拟器，扫描碧蓝航线相关目录并报告大小
  python mumu_adb.py ls  <模拟器路径>               列出目录内容
  python mumu_adb.py du  <模拟器路径>               查看目录大小
  python mumu_adb.py scan <模拟器路径>              列出目录下所有文件及大小（用于 dry-run）
  python mumu_adb.py pull <模拟器路径> <本地路径>    整目录拉取到本地

前置条件：MuMu 模拟器必须已启动（本工具只做读取和拉取，不修改模拟器内任何数据）。
"""
import argparse
import subprocess
import sys
import time

ADB = r"C:\Program Files\Netease\MuMuPlayer\nx_main\adb.exe"
HOST = "127.0.0.1:16384"
PKG = "com.bilibili.azurlane"

# 碧蓝航线资源常见落点（按可能性排序）
CANDIDATES = [
    f"/sdcard/Android/data/{PKG}/files",
    f"/sdcard/Android/obb/{PKG}",
    f"/sdcard/Android/data/{PKG}",
    f"/data/data/{PKG}",
    f"/sdcard/{PKG}",
]


def run(args, timeout=120):
    """执行 adb 命令，返回 (returncode, stdout, stderr)。"""
    try:
        proc = subprocess.run(
            [ADB] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"命令超时（>{timeout}s）"
    except FileNotFoundError:
        return -2, "", f"找不到 adb: {ADB}"


def human(n):
    """字节数转人类可读。"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024
    return f"{n:.1f}PB"


def connect():
    """确保 adb 已连上模拟器，返回是否成功。"""
    rc, out, _ = run(["devices"], timeout=30)
    if rc == 0 and HOST in out:
        for line in out.splitlines():
            if line.startswith(HOST) and "\tdevice" in line:
                return True
    rc, out, err = run(["connect", HOST], timeout=30)
    if rc == 0 and "connected" in out.lower():
        return True
    return False


def shell(cmd, timeout=120):
    """在模拟器上执行 shell 命令。"""
    return run(["shell", cmd], timeout=timeout)


def dir_exists(path):
    rc, out, _ = shell(f"ls -d {path} 2>/dev/null")
    return rc == 0 and path in out


def cmd_info(args):
    print("== 连接模拟器 ==")
    if not connect():
        print(f"✗ 连不上 {HOST}")
        print("  请确认 MuMu 模拟器已经完全启动（能看到 Android 桌面），然后重试。")
        return 1
    print(f"✓ 已连接 {HOST}\n")

    print("== 扫描 /sdcard/Android/data ==")
    rc, out, err = shell("ls /sdcard/Android/data 2>/dev/null")
    if rc != 0 or not out.strip():
        print("  （读不到 /sdcard/Android/data，可能需要 root；尝试 adb root 或开启模拟器 root 开关）")
        if err.strip():
            print(f"  错误: {err.strip()}")
    else:
        for name in sorted(out.split()):
            mark = "  ← 目标" if PKG in name else ""
            print(f"  {name}{mark}")

    print("\n== 碧蓝航线相关目录探测 ==")
    found = []
    for path in CANDIDATES:
        if dir_exists(path):
            rc, out, _ = shell(f"du -sk {path} 2>/dev/null")
            size_kb = int(out.split()[0]) if rc == 0 and out.split() else 0
            rc2, cnt, _ = shell(f"find {path} -type f 2>/dev/null | wc -l")
            n_files = int(cnt.strip()) if rc2 == 0 and cnt.strip().isdigit() else -1
            found.append((path, size_kb * 1024, n_files))
            print(f"  ✓ {path}")
            print(f"      大小={human(size_kb * 1024)}  文件数={n_files if n_files >= 0 else '未知'}")
        else:
            print(f"  ✗ {path}（不存在）")

    if found:
        print("\n== 可直接拉取 ==")
        for path, size, _ in found:
            print(f'  python mumu_adb.py pull {path} "D:\\Azur Lane Assets\\files"')
    return 0


def cmd_ls(args):
    if not connect():
        print(f"✗ 连不上 {HOST}，请先启动模拟器")
        return 1
    rc, out, err = shell(f"ls -la '{args.path}'")
    if rc != 0:
        print(f"✗ 读取失败: {err.strip() or out.strip()}")
        return 1
    print(out.rstrip())
    return 0


def cmd_du(args):
    if not connect():
        print(f"✗ 连不上 {HOST}，请先启动模拟器")
        return 1
    rc, out, err = shell(f"du -sh '{args.path}' 2>/dev/null")
    if rc != 0:
        print(f"✗ 读取失败: {err.strip() or out.strip()}")
        return 1
    print(f"{out.split()[0] if out.split() else '?'}  {args.path}")
    return 0


def cmd_scan(args):
    """列出目录下所有文件及大小，用于拉取前的 dry-run 评估。"""
    if not connect():
        print(f"✗ 连不上 {HOST}，请先启动模拟器")
        return 1
    print("扫描中（文件多时可能较慢）...")
    t0 = time.time()
    rc, out, err = shell(
        f"find '{args.path}' -type f -exec {{}} ls -l \\; 2>/dev/null", timeout=600
    )
    if rc != 0:
        # 退回到逐行 stat
        rc, names, _ = shell(f"find '{args.path}' -type f 2>/dev/null", timeout=600)
        if rc != 0:
            print(f"✗ 扫描失败: {err.strip()}")
            return 1
        files = []
        total = 0
        for line in names.splitlines():
            line = line.strip()
            if not line:
                continue
            rc2, sz, _ = shell(f"stat -c %s '{line}' 2>/dev/null", timeout=30)
            size = int(sz.strip()) if rc2 == 0 and sz.strip().isdigit() else 0
            files.append((size, line))
            total += size
    else:
        files = []
        total = 0
        for line in out.splitlines():
            parts = line.split()
            # toybox ls -l 输出: perms links owner group size date time name
            if len(parts) >= 8:
                try:
                    size = int(parts[4])
                except ValueError:
                    continue
                files.append((size, parts[7] if len(parts) > 7 else "?"))
                total += size

    files.sort(key=lambda x: -x[0])
    limit = args.top if args.top > 0 else len(files)
    print(f"\n共 {len(files)} 个文件，合计 {human(total)}（耗时 {time.time() - t0:.1f}s）\n")
    print(f"最大的 {min(limit, len(files))} 个文件：")
    for size, name in files[:limit]:
        print(f"  {human(size):>10}  {name}")
    return 0


def cmd_pull(args):
    if not connect():
        print(f"✗ 连不上 {HOST}，请先启动模拟器")
        return 1

    if args.dry_run:
        print(f"[dry-run] 源  : {args.src}")
        print(f"[dry-run] 目标: {args.dst}")
        rc, out, _ = shell(f"du -sk '{args.src}' 2>/dev/null")
        size_kb = int(out.split()[0]) if rc == 0 and out.split() else 0
        rc2, cnt, _ = shell(f"find '{args.src}' -type f 2>/dev/null | wc -l")
        n = cnt.strip() if rc2 == 0 else "未知"
        print(f"[dry-run] 将拉取约 {human(size_kb * 1024)} / {n} 个文件（未实际下载）")
        return 0

    print(f"拉取中: {args.src}")
    print(f"     → {args.dst}")
    print("（文件多时请耐心等待，不要关闭窗口）\n")
    t0 = time.time()
    rc, out, err = run(
        ["pull", "-a", args.src, args.dst], timeout=args.timeout
    )
    print(out.rstrip())
    if rc != 0:
        print(f"\n✗ 拉取失败: {err.strip()}")
        return 1
    print(f"\n✓ 完成，耗时 {time.time() - t0:.1f}s")
    return 0


def main():
    p = argparse.ArgumentParser(description="MuMu 模拟器 ADB 文件工具")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="连接并扫描碧蓝航线目录").set_defaults(func=cmd_info)

    sp = sub.add_parser("ls", help="列目录")
    sp.add_argument("path")
    sp.set_defaults(func=cmd_ls)

    sp = sub.add_parser("du", help="看目录大小")
    sp.add_argument("path")
    sp.set_defaults(func=cmd_du)

    sp = sub.add_parser("scan", help="列出所有文件及大小")
    sp.add_argument("path")
    sp.add_argument("--top", type=int, default=20, help="显示最大的 N 个，0=全部")
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("pull", help="拉取目录到本地")
    sp.add_argument("src")
    sp.add_argument("dst")
    sp.add_argument("--dry-run", action="store_true", help="只评估不下载")
    sp.add_argument("--timeout", type=int, default=7200, help="超时秒数，默认 2 小时")
    sp.set_defaults(func=cmd_pull)

    args = p.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
