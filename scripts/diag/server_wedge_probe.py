# -*- coding: utf-8 -*-
"""本地服务器「取消下载 ⇒ 泄漏 handler 线程」的剂量学探针。跑法：`py -3 scripts/diag/server_wedge_probe.py`

结论与判据见 docs/TROUBLESHOOTING.md §63。验证 _gallery_server.py 那处 handle_error 改动。

三格，缺一不可：
  ① 剂量学（正向）：stderr 接向**从不读取的管道** + 掐断 2600 次大文件下载
     ⇒ 改前会 5→2605 线程 / 113→18313 句柄；改后必须纹丝不动。
  ② 对照（防"全吞"）：一个**不属于**客户端取消类的真异常（URL 里塞 NUL ⇒
     os.stat 抛 ValueError）必须**照样**往 stderr 打 traceback。
     没有这格，①红了也可能只是因为把错误全咽了。
  ③ 现场取证函数本身能出数（对活的 8777 跑一次，只读）。
"""
import http.client
import os
import socket
import struct
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/diag/ -> 项目根
OUT = os.path.join(ROOT, "Output")
WORK = os.path.join(ROOT, ".diag", "wedge")
SRC = os.path.join(ROOT, "gallery_src", "_gallery_server.py")
PORT = 8798
BIG = "gallery_v2/index.js"
N = 2600

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def make_variant():
    src = open(SRC, encoding="utf-8").read()
    assert "ConnectionAbortedError" in src, "正本里没有本次改动，先确认改上了"
    src = src.replace("PORT = 8777", f"PORT = {PORT}")
    src = src.replace("ROOT = os.path.dirname(HERE)                 # gallery_v2 的上一级 = Output/",
                      f'ROOT = {OUT!r}')
    src = src.replace("threading.Timer(1.5, open_browser).start()", "pass")
    path = os.path.join(WORK, "_server_v.py")
    open(path, "w", encoding="utf-8").write(src)
    return path


def th_hd(pid):
    ps = ("$p=Get-Process -Id %d -ErrorAction SilentlyContinue;"
          "if($p){''+$p.Threads.Count+' '+$p.HandleCount}else{'gone 0'}" % pid)
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, timeout=25)
    a, b = (r.stdout.strip() or "0 0").split()[:2]
    return int(a), int(b)


def normal_ok(timeout=6.0):
    """一次请求 = 一个连接（HTTP/1.0 服务端回完就关），别重复发请求。"""
    got = 0
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=timeout)
        s.sendall(f"GET /{BIG} HTTP/1.0\r\nHost: x\r\n\r\n".encode())
        while True:
            b = s.recv(1 << 16)
            if not b:
                break
            got += len(b)
        s.close()
        return got
    except Exception as e:
        return f"{type(e).__name__}"


def abort_once():
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=5)
        s.sendall(f"GET /{BIG} HTTP/1.0\r\nHost: x\r\n\r\n".encode())
        s.recv(4096)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        s.close()
    except OSError:
        pass


print("=" * 72)
print("① + ② 改后正本：stderr 走没人读的管道")
server_py = make_variant()
reader, writer = os.pipe()
errfile = os.path.join(WORK, "verify_stderr.txt")
open(errfile, "wb").close()
p = subprocess.Popen([sys.executable, server_py], stdout=subprocess.DEVNULL,
                     stderr=writer, cwd=ROOT, creationflags=0x00000008)
try:
    for _ in range(80):
        r0 = normal_ok(5)
        if isinstance(r0, int) and r0 > 500_000:
            break
        time.sleep(0.5)
    b_th, b_hd = th_hd(p.pid)
    print(f"  pid={p.pid} 基线 threads/handles = {b_th}/{b_hd}")
    for _ in range(N):
        abort_once()
    time.sleep(2.0)
    a_th, a_hd = th_hd(p.pid)
    ok = normal_ok()
    print(f"  掐断 {N} 次后 threads/handles = {a_th}/{a_hd}   正常请求 = {ok}")
    leak = a_th - b_th
    print(f"  ⇒ 泄漏线程 {leak} 个  {'✅ 已堵住' if leak <= 2 else '❌ 仍在泄漏'}")

    # ② 对照：真异常必须照样留痕。改用**文件**做 stderr 才看得见写没写进去。
    p.kill(); p.wait(timeout=15)
    os.close(reader); os.close(writer)
    ef = open(errfile, "wb")
    p = subprocess.Popen([sys.executable, server_py], stdout=subprocess.DEVNULL,
                         stderr=ef, cwd=ROOT, creationflags=0x00000008)
    for _ in range(80):
        r1 = normal_ok(5)
        if isinstance(r1, int) and r1 > 500_000:
            break
        time.sleep(0.5)
    before = os.path.getsize(errfile)
    for probe, label in ((f"/{BIG}%00x", "ValueError 类（URL 含 NUL）"),
                         ("/gallery_v2/index.html", "取消类对照：立刻 RST")):
        try:
            s = socket.create_connection(("127.0.0.1", PORT), timeout=5)
            s.sendall(f"GET {probe} HTTP/1.0\r\nHost: x\r\n\r\n".encode())
            s.recv(4096)
            if "00" in probe:
                s.recv(4096)
            else:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            s.close()
        except OSError:
            pass
        time.sleep(1.5)
        print(f"  {label}: stderr 增量 {os.path.getsize(errfile) - before}B")
        before = os.path.getsize(errfile)
    txt = open(errfile, encoding="utf-8", errors="replace").read()
    print(f"  stderr 里出现 ValueError = {'ValueError' in txt}")
    print(f"  stderr 里出现 10054/10053 = {('10054' in txt) or ('10053' in txt)}")
    print("  ⇒ 期望：ValueError True（真异常照旧打）、1005x False（取消类已静默）")
    p.kill(); p.wait(timeout=15)
    ef.close()
finally:
    try:
        p.kill()
    except Exception:
        pass
    for fd in (reader, writer):
        try:
            os.close(fd)
        except OSError:
            pass

print("\n" + "=" * 72)
print("③ 现场取证函数（对活的 8777，只读）")
sys.path.insert(0, os.path.join(ROOT, "scripts", "diag"))
import wf16_regression as w  # noqa: E402
print("  " + w.server_forensics())
