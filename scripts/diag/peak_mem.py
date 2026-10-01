# -*- coding: utf-8 -*-
"""给一条命令量**峰值内存**：自己起的进程树（含子进程）WorkingSet 之和的最大值。

为什么要有这个：`update_pipeline.py` 的阶段是一批一批 spawn 子进程的，"跑一次要多少 G"
不能靠猜，也不能只看父进程 —— 父进程几百 KB，真正吃内存的是批里那个 UnityPy 子进程。

    py -3 scripts/diag/peak_mem.py --tag paintings -- py -3 scripts/compose_paintings_v2.py a,b --out .diag/x

判据：退出码 = 被采样命令的退出码（本工具不改写结论，只旁路记一行峰值）。
机器基线也要一起报 —— 峰值绝对值没意义，「跑之前剩多少 / 跑的时候最低剩多少」才有。
"""
import ctypes
import subprocess
import sys
import time
from ctypes import wintypes

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)

TH32CS_SNAPPROCESS = 0x2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
INVALID_HANDLE = ctypes.c_void_p(-1).value


class PE32(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', ctypes.c_long),
                ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]


class PMC(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [('dwLength', wintypes.DWORD), ('dwMemoryLoad', wintypes.DWORD),
                ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]


def free_gb():
    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullTotalPhys / 2**30, m.ullAvailPhys / 2**30


def snapshot_ppid():
    """一次进程快照：{pid: ppid}。用 CreateToolhelp32Snapshot，不依赖 pywin32/psutil。"""
    h = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    out = {}
    if h != INVALID_HANDLE:
        e = PE32()
        e.dwSize = ctypes.sizeof(PE32)
        if kernel32.Process32FirstW(h, ctypes.byref(e)):
            while True:
                out[e.th32ProcessID] = e.th32ParentProcessID
                if not kernel32.Process32NextW(h, ctypes.byref(e)):
                    break
        kernel32.CloseHandle(h)
    return out


def descendants(root, ppids):
    kids = {}
    for pid, ppid in ppids.items():
        kids.setdefault(ppid, []).append(pid)
    seen, stack = set(), [root]
    while stack:
        pid = stack.pop()
        for c in kids.get(pid, ()):
            if c not in seen:
                seen.add(c)
                stack.append(c)
    seen.discard(root)
    seen.add(root)
    return seen


def ws_gb(pid):
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return 0.0
    try:
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        if not psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
            return 0.0
        return c.WorkingSetSize / 2**30
    finally:
        kernel32.CloseHandle(h)


def main():
    argv = sys.argv[1:]
    tag = ''
    if '--tag' in argv:
        i = argv.index('--tag')
        tag = argv[i + 1]
        del argv[i:i + 2]
    if argv and argv[0] == '--':
        argv = argv[1:]
    if not argv:
        print(__doc__)
        return 2
    total, base_free = free_gb()
    t0 = time.time()
    peak = 0.0
    low_free = base_free
    peak_detail = ''
    p = subprocess.Popen(argv)
    while p.poll() is None:
        ppids = snapshot_ppid()
        tree = descendants(p.pid, ppids)
        s = 0.0
        for pid in tree:
            s += ws_gb(pid)
        _, af = free_gb()
        if s > peak:
            peak = s
            peak_detail = ' / '.join(f'{pid}:{ws_gb(pid):.2f}' for pid in sorted(tree)[:6])
        low_free = min(low_free, af)
        time.sleep(0.2)
    dt = time.time() - t0
    print(f'PEAK_MEM tag={tag or "-"} 峰值WS={peak:.2f} GB  用时={dt:.0f}s  '
          f'机器总内存={total:.1f} GB  跑前可用={base_free:.1f} GB  期间最低={low_free:.1f} GB  '
          f'退出码={p.returncode}  进程数={len(descendants(p.pid, snapshot_ppid()))}')
    print(f'  峰值时前几个: {peak_detail}')
    return p.returncode


if __name__ == '__main__':
    sys.exit(main())
