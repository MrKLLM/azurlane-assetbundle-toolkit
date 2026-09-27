# -*- coding: utf-8 -*-
"""headless Chrome 的可靠清理——补上 `proc.terminate()` 的两个洞。

1. **只杀启动器**：`Popen([CHROME, ...])` 拿到的 pid 下面还挂着 crashpad/gpu/网络/若干 renderer，
   `terminate()` 不打整棵树，SwiftShader 软 GPU 的渲染进程会**继续活着吃 CPU 和内存**。
2. **异常时压根不执行**：多数诊断脚本把 `proc.terminate()` 写在最后一行，脚本一抛异常
   （典型：`RuntimeError: Execution context was destroyed`）就永远走不到那一行。

2026-09-27 实测：两个验收脚本各漏一棵树、共 16 个 chrome 进程，把用户机器压到只剩 1.1GB 空闲。

用法（一行）：`proc = chrome_tree.install(subprocess.Popen([...]))`
"""
import atexit
import subprocess


def kill_tree(pid):
    subprocess.call(['taskkill', '/T', '/F', '/PID', str(pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def install(proc):
    """注册 atexit 整树清理（异常退出也会执行），原样返回 proc。"""
    atexit.register(kill_tree, proc.pid)
    return proc
