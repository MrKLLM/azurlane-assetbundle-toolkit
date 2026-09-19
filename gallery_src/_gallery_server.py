# -*- coding: utf-8 -*-
"""碧蓝航线资产浏览器 本地服务器启动器。

被 启动资产浏览器.bat 调用。负责：
  1. 在 8777 起一个本地 HTTP 服务器（根目录 = Output/，页面在 /gallery_v2/index.html），
     供 Spine 实时播放（file:// 下 fetch 会被 CORS 拦，必须走 http）。
  2. 自动用默认浏览器打开页面。传 --export 则打开 cg_export.html（Spine 全屏 CG 批量导出）。
  3. 提供 POST /save_cg 与 GET /cg_exists，供 cg_export.html 落盘 PNG 到 Output/CG_v2/。
  4. 稳健处理端口占用 / TIME_WAIT，避免窗口“闪退”。
"""
import functools
import http.server
import os
import re
import socket
import socketserver
import sys
import threading
import webbrowser

PORT = 8777
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                 # gallery_v2 的上一级 = Output/
CG_DIR = os.path.join(ROOT, "CG_v2")         # Spine setup-pose CG 导出目录
_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,80}$")
EXPORT = "--export" in sys.argv
URL = (f"http://127.0.0.1:{PORT}/gallery_v2/cg_export.html" if EXPORT
       else f"http://127.0.0.1:{PORT}/gallery_v2/index.html")


def port_in_use():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def open_browser():
    try:
        webbrowser.open(URL)
    except Exception:
        os.startfile(URL)  # noqa: S606 - Windows 兜底


def main():
    # 说明：Windows 真实控制台由 Python 原生按 Unicode(WriteConsoleW) 输出，
    # 中文无需改编码即可正常显示；这里不 reconfigure，避免反而破坏控制台渲染。
    print("=" * 52)
    print("  碧蓝航线 本地资产浏览器")
    print("  服务器根目录:", ROOT)
    print("  访问地址:", URL)
    print("  关闭本窗口即停止服务器。")
    print("=" * 52)

    if not os.path.isfile(os.path.join(HERE, "index.html")):
        print("\n[警告] 当前目录没找到 index.html，请确认脚本与 gallery_v2 同目录。")

    # 端口已被占用：多半是上一次没关掉的服务器还在跑 —— 直接复用，不再重复启动
    if port_in_use():
        print("\n检测到 8777 端口已有服务在运行，直接为你打开浏览器。")
        print("若想重启服务器，请先关闭那个正在运行的窗口。")
        open_browser()
        input("\n按回车关闭本提示窗口（后台服务器继续运行）。")
        return

    class Handler(http.server.SimpleHTTPRequestHandler):
        """静态文件 + CG 导出落盘接口。"""

        def do_POST(self):  # noqa: N802
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            name = (q.get("name") or [""])[0]
            if not urlparse(self.path).path == "/save_cg" or not _NAME_RE.match(name):
                self.send_error(400, "bad request")
                return
            n = int(self.headers.get("Content-Length", 0))
            if not (1000 < n < 300 * 1024 * 1024):
                self.send_error(400, "bad size")
                return
            os.makedirs(CG_DIR, exist_ok=True)
            with open(os.path.join(CG_DIR, name + ".png"), "wb") as f:
                remaining = n
                while remaining:
                    chunk = self.rfile.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            from urllib.parse import urlparse, parse_qs
            if urlparse(self.path).path == "/cg_exists":
                name = (parse_qs(urlparse(self.path).query).get("name") or [""])[0]
                ok = "1" if (_NAME_RE.match(name) and
                             os.path.isfile(os.path.join(CG_DIR, name + ".png"))) else "0"
                body = ok.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

        def log_message(self, fmt, *args):  # 只留导出相关日志，屏蔽静态文件刷屏
            s = fmt % args
            if "/save_cg" in s or "/cg_exists" in s:
                super().log_message(fmt, *args)

    handler = functools.partial(Handler, directory=ROOT)

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True            # 关键：规避 TIME_WAIT 导致的绑定失败
        daemon_threads = True

    try:
        httpd = Server(("127.0.0.1", PORT), handler)
    except OSError as e:
        print(f"\n[错误] 无法在 127.0.0.1:{PORT} 启动服务器：{e}")
        print("可稍等十几秒（等旧连接超时）后重试，或手动关闭占用该端口的程序。")
        input("\n按回车退出。")
        return

    threading.Timer(1.5, open_browser).start()
    print(f"\n服务器已启动，正在打开浏览器… {URL}\n（按 Ctrl+C 或关闭本窗口可停止）")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
