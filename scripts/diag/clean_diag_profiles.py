#!/usr/bin/env python3
"""clean_diag_profiles.py — 清掉 .diag 下无头 Chrome 留下的 user-data-dir（每个几百 MB）。

规则（不是例外名单，三条硬判据全过才删）：
  1. 目录名匹配 `chrome_*`（只此一类，其它 .diag 内容一律不碰）；
  2. 没有任何 chrome/msedge 进程的命令行引用它 —— 用 PowerShell CIM 查 CommandLine，
     注意路径含空格，只能按「仓库名 + profile 名」双条件匹配（见 WORKFLOWS WF-16 踩坑）；
  3. 最后修改时间早于 --min-age 分钟（默认 30），避免误删并发会话正在写的 profile。

用法:
  py -3 scripts/diag/clean_diag_profiles.py            # 干跑，列清单与可回收量
  py -3 scripts/diag/clean_diag_profiles.py --yes      # 真删
"""
import os, sys, time, shutil, stat, argparse, subprocess

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DIAG = os.path.join(ROOT, '.diag')


def dir_bytes(path):
    total = 0
    for dirpath, _, names in os.walk(path):
        for n in names:
            try:
                total += os.path.getsize(os.path.join(dirpath, n))
            except OSError:
                pass
    return total


def running_profile_names():
    """返回被活跃浏览器进程引用的 profile 目录名集合。"""
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe' or Name='msedge.exe'\" "
        "| ForEach-Object { $_.CommandLine } "
        f"| Where-Object {{ $_ -and $_ -match 'Azur Lane Assets' }} "
        "| ForEach-Object { if ($_ -match 'chrome_[A-Za-z0-9_]+') { $matches[0] } }"
    )
    try:
        out = subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps],
                             capture_output=True, text=True, timeout=60).stdout
    except Exception as e:
        print(f'[WARN] 进程查询失败（{e}）→ 保守起见本轮什么都不删')
        return {'*'}
    return {ln.strip() for ln in out.splitlines() if ln.strip()}


def rm_ro(path):
    def onerr(func, p, exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=onerr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--yes', action='store_true', help='真正删除（默认干跑）')
    ap.add_argument('--min-age', type=int, default=30, help='只删最后修改早于 N 分钟前的 profile，默认 30')
    args = ap.parse_args()

    if not os.path.isdir(DIAG):
        print(f'[ERROR] 没有 .diag: {DIAG}')
        return 2
    live = running_profile_names()
    now = time.time()
    victims, kept_busy, kept_young = [], [], []
    for d in sorted(os.listdir(DIAG)):
        p = os.path.join(DIAG, d)
        if not (d.startswith('chrome_') and os.path.isdir(p)):
            continue
        if d in live or '*' in live:
            kept_busy.append(d)
            continue
        age_min = (now - os.path.getmtime(p)) / 60
        if age_min < args.min_age:
            kept_young.append((d, round(age_min)))
            continue
        victims.append((d, p))

    total = 0
    for d, p in victims:
        b = dir_bytes(p)
        total += b
        print(f'  [{"DEL" if args.yes else "DRY"}] {d}  {b / (1 << 30):.2f} GiB')
        if args.yes:
            rm_ro(p)
    print(f'\n.diag = {DIAG}')
    print(f'  可删 {len(victims)} 个 / {(total) / (1 << 30):.2f} GiB'
          + ('（已删除）' if args.yes else '（干跑，未删）'))
    if kept_busy:
        print(f'  保留（进程仍引用）: {kept_busy}')
    if kept_young:
        print(f'  保留（修改于 {args.min_age} 分钟内）: {kept_young}')
    if not args.yes and victims:
        print('  加 --yes 执行')
    return 0


if __name__ == '__main__':
    sys.exit(main())
