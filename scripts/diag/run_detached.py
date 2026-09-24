#!/usr/bin/env python3
"""run_detached.py — 用完全脱离宿主的进程启动长任务，并把 PID/日志/退出码落盘。

为什么不用 PowerShell 的 Start-Process（2026-09-24 连吃三次）：
  * 含空格的路径塞进 `-ArgumentList` 会被它用空格拼接，子进程看到的路径在半路断开；
    改成一整条字符串又要面对 bash → PowerShell → 子进程三层引号转义。
  * Python 的 `subprocess.Popen(列表)` 没有这个问题：参数就是列表，不经 shell。

用法（`--` 之后整段原样作为子进程 argv）:
  py -3 scripts/diag/run_detached.py --log .diag/_run.log -- py -3 scripts/diag/l2d_ref_diff.py --all
判它跑完没跑完，用 scripts/diag/wait_for_detached.ps1（按命令行匹配工作进程 + 日志是否还在涨 + 汇总行）。

退出码只表示"有没有成功把进程丢出去"。<log>.exit **只在子进程 1.5 秒内就退出时才写**（那是命令没跑起来）；
长任务的 launcher 进程本身会先结束，没人替它写退出码——这正符合本项目的判据：**完成与否只认脚本自己打的
汇总行**，退出码不作为通过证据（见技能 windows-long-running-batch-detach 规则 4）。
"""
import os, sys, subprocess, argparse

sys.stdout.reconfigure(encoding='utf-8')
DETACHED = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
# 不要加 CREATE_NO_WINDOW(0x10)：它与 DETACHED_PROCESS 互斥，同时给会让
# CreateProcess 直接报 [WinError 87] 参数错误（实测）。


def main():
    ap = argparse.ArgumentParser(description='脱离宿主进程启动长任务')
    ap.add_argument('--log', required=True, help='stdout 落地路径；stderr 落到同名 .err，退出码落到 .exit')
    ap.add_argument('--cwd', default=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    ap.add_argument('--keep-env', action='store_true', help='透传当前环境变量（默认就透传，此旗标仅为对照）')
    ap.add_argument('cmd', nargs='+', help='-- 之后的完整命令行')
    args, child = ap.parse_known_args()
    if child and child[0] == '--':
        child = child[1:]
    cmd = args.cmd + child
    if not cmd:
        print('[ERROR] 没有子命令'); return 2

    log = os.path.abspath(args.log)
    err = log + '.err'
    code = log + '.exit'
    for p in (log, err, code):
        if os.path.exists(p):
            os.remove(p)          # 旧日志会被误读成本轮的进度
    os.makedirs(os.path.dirname(log), exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')

    with open(log, 'ab') as fo, open(err, 'ab') as fe:
        p = subprocess.Popen(cmd, cwd=args.cwd, stdout=fo, stderr=fe, env=env,
                             creationflags=DETACHED, close_fds=True, shell=False)
    pidfile = log + '.pid'
    open(pidfile, 'w').write(str(p.pid))

    # 起进程 ≠ 真的在跑：等 1 秒看它有没有立刻退出（例如脚本名拼错）
    try:
        rc = p.wait(timeout=1.5)
    except subprocess.TimeoutExpired:
        rc = None
    if rc is None:
        print(f'[OK] 已脱离启动 pid={p.pid}\n     日志 {log}\n     stderr {err}\n     PID 文件 {pidfile}')
        return 0
    open(code, 'w').write(str(rc))
    if rc == 0:
        print(f'[OK] 子进程 1 秒内就跑完且 rc=0（短任务属正常），退出码见 {code}')
        return 0
    print(f'[FAIL] 子进程立刻退出 rc={rc}，命令没跑起来。stderr 前几行：')
    print(open(err, encoding='utf-8', errors='replace').read()[:800])
    return 1


if __name__ == '__main__':
    sys.exit(main())
