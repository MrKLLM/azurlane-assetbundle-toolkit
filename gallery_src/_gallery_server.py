# -*- coding: utf-8 -*-
"""碧蓝航线资产浏览器 本地服务器启动器。

被 启动资产浏览器.bat 调用。负责：
  1. 在 8777 起一个本地 HTTP 服务器（根目录 = Output/，页面在 /gallery_v2/index.html），
     供 Spine 实时播放（file:// 下 fetch 会被 CORS 拦，必须走 http）。
  2. 自动用默认浏览器打开页面。传 --export 则打开 cg_export.html（Spine 全屏 CG 批量导出）。
  3. 提供 POST /save_cg 与 GET /cg_exists，供 cg_export.html 落盘 PNG 到 Output/CG_v2/。
  4. 提供 POST /l2d_freeze，供 Live2D 页的「暂停」把冻住那一帧的姿态向量落盘到 .diag/l2d_freeze/
     （临时取证区，不入库）。暂停本身是纯前端行为，这个接口只是把坏帧交出来的通道。
  5. 稳健处理端口占用 / TIME_WAIT，避免窗口“闪退”。
"""
import functools
import http.server
import json
import os
import re
import socket
import socketserver
import sys
import threading
import time
import webbrowser
from urllib.parse import urlparse, parse_qs

PORT = 8777
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                 # gallery_v2 的上一级 = Output/
CG_DIR = os.path.join(ROOT, "CG_v2")         # Spine setup-pose CG 导出目录
# Live2D 暂停帧的落盘目录：项目根下的 .diag/（临时产物区，已在 .gitignore 里）。
# 不在模块级算，见 Handler._freeze_dir —— 探针从 gallery_src/ 正本 import 这个模块时，
# 按模块路径算出来的"项目根"是错的，探针传进来的 root 才是事实。
FREEZE_SUB = os.path.join(".diag", "l2d_freeze")
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


class Handler(http.server.SimpleHTTPRequestHandler):
    """静态文件（含 Range 分段）+ CG 导出落盘接口。

    ⚠️ 为什么要自己实现 Range：`SimpleHTTPRequestHandler` 全量响应只发一个 `Content-Length`，
    Chrome 于是把音频/视频当成**不可 seek 的流** —— 实测 BGM 页
    `A.duration === Infinity`（时长显示成 `Infinity:NaN`）、进度条恒 0、拖动无效。
    补上 206 + `Content-Range` 之后这三件事一起好。
    """

    # ⚠️ MIME 也必须钉死：Python 的 mimetypes 把 `.flac` 判成 **`audio/x-flac`**（遗留写法），
    # 而 Chrome 的 `Audio.canPlayType('audio/x-flac')` 返回**空串**（`audio/flac` 才给 "probably"）
    # ⇒ 用 FLAC 做无损档时不改这里，页面可能整片播不出来（2026-10-06 实测三种类型）。
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        '.flac': 'audio/flac',
        '.ogg': 'audio/ogg',
        '.opus': 'audio/ogg',
        '.m4a': 'audio/mp4',
    }

    def do_GET(self):  # noqa: N802
        if urlparse(self.path).path == "/cg_exists":
            name = (parse_qs(urlparse(self.path).query).get("name") or [""])[0]
            ok = "1" if (_NAME_RE.match(name) and
                         os.path.isfile(os.path.join(CG_DIR, name + ".png"))) else "0"
            self._reply(ok.encode(), "text/plain")
            return
        if self._serve_range():
            return
        super().do_GET()

    def _reply(self, body, ctype, extra=None):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _serve_range(self):
        """处理 `Range: bytes=a-b` / `bytes=a-` / `bytes=-n`。返回 True 表示已应答。"""
        rng = self.headers.get("Range")
        if not rng:
            return False
        m = re.match(r"^bytes=(\d*)-(\d*)$", rng.strip())
        if not m:
            return False                       # 多区间/未知单位：交回全量应答
        path = self.translate_path(urlparse(self.path).path)
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if not os.path.isfile(path) or not os.access(path, os.R_OK):
            return False
        a, b = m.group(1), m.group(2)
        if a == "" and b == "":
            return False
        if a == "":                            # 后缀区间：最后 N 字节
            start = max(0, size - int(b))
            end = size - 1
        else:
            start = int(a)
            end = min(int(b), size - 1) if b else size - 1
        if start >= size or start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return True
        length = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining:
                    chunk = f.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except OSError:
            pass                               # 客户端中途掐断：本地 dev server 常态
        return True

    def do_POST(self):  # noqa: N802
        from urllib.parse import urlparse, parse_qs
        route = urlparse(self.path).path
        if route == "/l2d_freeze":
            return self._save_freeze()
        q = parse_qs(urlparse(self.path).query)
        name = (q.get("name") or [""])[0]
        if not route == "/save_cg" or not _NAME_RE.match(name):
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
        self._reply(b"ok", "text/plain")

    def _read_body(self, limit):
        n = int(self.headers.get("Content-Length", 0))
        if not (0 < n < limit):
            return None
        buf, remaining = bytearray(), n
        while remaining:
            chunk = self.rfile.read(min(1 << 20, remaining))
            if not chunk:
                break
            buf += chunk
            remaining -= len(chunk)
        return bytes(buf)

    def _freeze_dir(self):
        """暂停存档落在「这台服务器正在服务的这棵树」的上一级 .diag/ 里（服务根 = Output/ ⇒ 项目根下）。

        按 self.directory 而不是模块路径算：探针从 gallery_src/ 里的正本 import 本模块起临时服务器时，
        模块路径算出的"项目根"是仓库根，而探针传进来的 root 才是事实。
        """
        root = getattr(self, "directory", None) or ROOT
        return os.path.normpath(os.path.join(root, os.pardir, FREEZE_SUB))

    def _save_freeze(self):
        """Live2D「暂停」送来的姿态存档：JSON 原样落盘，文件名由服务端时间戳 + 白名单 tag 生成。

        不接受请求里带的任何路径/文件名 —— 页面只交数据，命名权在这边。
        响应体回文件名，页面上直接显示，用户念这一个字符串就能把坏帧交给我。
        """
        body = self._read_body(8 * 1024 * 1024)
        if body is None:
            self.send_error(400, "bad size")
            return
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self.send_error(400, "bad json")
            return
        if not isinstance(data, dict):
            self.send_error(400, "not an object")
            return
        tag = re.sub(r"[^A-Za-z0-9_.\-]", "", str(data.get("tag", "")))[:40] or "freeze"
        stem = time.strftime("%Y%m%d-%H%M%S") + "-" + tag
        fdir = self._freeze_dir()
        os.makedirs(fdir, exist_ok=True)
        name, k = stem + ".json", 2
        while os.path.exists(os.path.join(fdir, name)):
            name, k = f"{stem}-{k}.json", k + 1   # 同一秒内连按两次暂停：不覆盖前一份
        with open(os.path.join(fdir, name), "wb") as f:
            f.write(body)          # 原样落盘：解析只用来验合法与取 tag，不改写上送的内容
        self._reply(name.encode("utf-8"), "text/plain")

    def end_headers(self):
        # 本地工具页：每次强制回源校验，杜绝 index.html/index.js 改版后浏览器仍用旧缓存
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):  # 只留导出与暂停存档的日志，屏蔽静态文件刷屏
        s = fmt % args
        if "/save_cg" in s or "/cg_exists" in s or "/l2d_freeze" in s:
            super().log_message(fmt, *args)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True            # 关键：规避 TIME_WAIT 导致的绑定失败
    daemon_threads = True

    def handle_error(self, request, client_address):
        """客户端中途取消下载是本地 dev server 的常态，不能让它泄漏线程。

        socketserver 的默认实现会往 stderr 打 4 段 traceback，而它是在
        `finally: shutdown_request()` **之前** 被调用的。stderr 只要是个「慢消费者」
        （双击 bat 起的控制台被选中暂停、或父 shell 已退出留下没人读的管道），
        这个写就永久阻塞 ⇒ 每次取消泄漏一个线程且 socket 既不吐字节也不关。
        实测剂量学：stderr 接向从不读取的管道时，掐断 2600 次下载 ⇒
        线程 5→2605、句柄 113→18313；静默本函数后同剂量 5/113 纹丝不动。
        只吞这一类，其余异常照旧留痕。
        """
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                           BrokenPipeError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def make_server(port=PORT, root=ROOT):
    """起一份服务器对象。`port`/`root` 可注入 —— 抽出来是为了测试能原地起一份，
    不必占用 8777（那台可能正被另一个会话的探针用着）。"""
    return Server(("127.0.0.1", port), functools.partial(Handler, directory=root))



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

    try:
        httpd = make_server()
    except OSError as e:
        print(f"\n[错误] 无法在 127.0.0.1:{PORT} 启动服务器：{e}")
        print("可稍等十几秒（等旧连接超时）后重试，或手动关闭占用该端口的程序。")
        input("\n按回车退出。")
        return

    print(f"\n服务器已启动，正在打开浏览器… {URL}\n（按 Ctrl+C 或关闭本窗口可停止）")
    threading.Timer(1.5, open_browser).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
