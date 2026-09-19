# -*- coding: utf-8 -*-
"""Robust Windows local http.server launcher (double-click safe).

Invoked by the generated .bat, e.g.:
    py _qw_server.py --root "D:\\proj" --page "web/index.html" --port 8777

Design goals (each one fixes a real failure mode):
  * allow_reuse_address  -> survive TIME_WAIT left by the previous window
  * probe before binding -> a second double-click reuses the running server
  * blocking tail        -> the console never closes silently on an error
  * ASCII markers        -> harness-verifiable regardless of codepage

NOTE: do not sys.stdout.reconfigure(); a real Windows console renders CJK
natively via WriteConsoleW and reconfiguring it produces mojibake.
"""
import argparse
import functools
import http.server
import os
import socket
import socketserver
import sys
import threading
import webbrowser

MARK = "[QW-LAUNCHER]"
PY2 = sys.version_info[0] < 3


def log(msg):
    sys.stdout.write("%s %s\n" % (MARK, msg))
    sys.stdout.flush()


def wait_after_error():
    try:
        input("\n按回车关闭窗口。")
    except Exception:
        pass


def port_in_use(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.6)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def open_browser(url):
    try:
        webbrowser.open(url)
    except Exception:
        try:
            os.startfile(url)  # Windows fallback
        except Exception as e:
            log("OPEN-FAIL %s" % e)


def normalize_page(page):
    return (page or "").strip().lstrip("/").replace("\\", "/")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Local http.server launcher")
    p.add_argument("--root", default=None,
                   help="Directory to serve. Default: parent of this script.")
    p.add_argument("--page", default="index.html",
                   help="Path opened in the browser, relative to --root.")
    p.add_argument("--port", type=int, default=8777)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-browser", action="store_true",
                   help="Do not auto-open the browser (used by tests).")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    root = os.path.abspath(args.root or os.path.dirname(os.path.abspath(__file__)))
    page = normalize_page(args.page)
    url = "http://%s:%d/%s" % (args.host, args.port, page)

    print("=" * 52)
    print("  本地服务器  根目录: %s" % root)
    print("  访问地址: %s" % url)
    print("  关闭本窗口即停止服务器。")
    print("=" * 52)

    # Harness / caller can suppress the browser without editing this file.
    no_browser = args.no_browser or os.environ.get("QW_LAUNCHER_NO_BROWSER") == "1"

    target = os.path.join(root, page.replace("/", os.sep)) if page else root
    if not os.path.exists(target):
        print("\n[警告] 页面不存在: %s" % target)

    if port_in_use(args.host, args.port):
        print("\n检测到 %d 端口已有服务在运行，直接为你打开浏览器。" % args.port)
        print("若想重启服务器，请先关闭那个正在运行的窗口。")
        log("REUSE url=%s port=%d" % (url, args.port))
        if not no_browser:
            open_browser(url)
        wait_after_error()
        return 0

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True      # defeats TIME_WAIT bind failures
        daemon_threads = True

    try:
        httpd = Server((args.host, args.port), handler)
    except OSError as e:
        log("BIND-FAIL host=%s port=%d err=%s" % (args.host, args.port, e))
        print("\n[错误] 无法在 %s:%d 启动服务器：%s" % (args.host, args.port, e))
        print("可稍等十几秒（等旧连接超时）后重试，或关闭占用该端口的程序。")
        wait_after_error()
        return 1

    if not no_browser:
        threading.Timer(1.5, open_browser, args=(url,)).start()
    log("SERVING url=%s root=%s port=%d" % (url, root, args.port))
    print("\n服务器已启动，正在打开浏览器…（按 Ctrl+C 或关闭本窗口可停止）")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never vanish: show it and block
        log("CRASH %r" % exc)
        wait_after_error()
        sys.exit(1)
