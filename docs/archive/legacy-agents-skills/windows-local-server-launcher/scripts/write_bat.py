# -*- coding: utf-8 -*-
"""Generate the minimal Windows .bat shell for server_launcher.py.

Writes GBK(cp936) + CRLF -- the two things that make a Chinese .bat survive a
double-click -- and uses the `if not errorlevel 1` detection form because
`where py >nul 2>nul && set ...` silently never fires.

Usage:
    python write_bat.py --out "D:\\proj\\web\\启动预览.bat" --server-py _qw_server.py \
        --root "D:\\proj" --page "web/index.html" --port 8777 \
        --title "项目预览 (本地服务器)" [--codepage 936] [--no-reuse-marker]

Exit code 0 = written and self-checked (CRLF present, re-decodable, no BOM).
"""
import argparse
import os
import sys

TEMPLATE = """@echo off
chcp {codepage} >nul
title {title}
set "SCRIPT=%~dp0{server_py}"

REM 优先用 py 启动器，其次 python；找到即运行（前台，关窗口即停）
where py >nul 2>nul
if not errorlevel 1 (
  py "%SCRIPT%" --root "{root}" --page "{page}" --port {port}
  goto end
)
where python >nul 2>nul
if not errorlevel 1 (
  python "%SCRIPT%" --root "{root}" --page "{page}" --port {port}
  goto end
)
echo [错误] 未找到 py 或 python，请先安装 Python 并加入 PATH。

:end
REM 无论正常退出还是报错，都停在这里，避免窗口一闪而过
pause
"""


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Write a GBK+CRLF .bat launcher shell")
    p.add_argument("--out", required=True, help="Target .bat path")
    p.add_argument("--server-py", default="_qw_server.py",
                   help="Launcher script filename, resolved next to the .bat")
    p.add_argument("--root", required=True, help="Directory to serve")
    p.add_argument("--page", default="index.html", help="Page path relative to --root")
    p.add_argument("--port", type=int, default=8777)
    p.add_argument("--title", default="本地服务器 (Local Server)")
    p.add_argument("--codepage", default="936", help="chcp value, 936 = Simplified Chinese")
    return p.parse_args(argv)


def build(args):
    return TEMPLATE.format(
        codepage=args.codepage,
        title=args.title,
        server_py=args.server_py.replace("\\", "/"),
        root=args.root,
        page=args.page.replace("\\", "/"),
        port=args.port,
    )


def main(argv=None):
    args = parse_args(argv)
    text = build(args)
    encoding = "cp%s" % args.codepage if args.codepage.isdigit() else "gbk"

    try:
        raw = text.replace("\r\n", "\n").replace("\n", "\r\n").encode(encoding)
    except UnicodeEncodeError as e:
        sys.stderr.write(
            "FAIL: the .bat text cannot be encoded as %s (%s).\n"
            "Do NOT switch the file to UTF-8 -- cmd.exe reads Chinese batch files as "
            "ANSI and desyncs. Remove the offending characters (emoji, rare glyphs) "
            "from --title/--page and retry.\n" % (encoding, e))
        return 2

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(args.out, "wb") as f:
        f.write(raw)

    # Self-check the three invariants that break double-click launches.
    back = open(args.out, "rb").read()
    problems = []
    if b"\r\n" not in back:
        problems.append("no CRLF line endings")
    if b"\n" in back.replace(b"\r\n", b""):
        problems.append("mixed LF-only lines")
    if back[:3] == b"\xef\xbb\xbf":
        problems.append("UTF-8 BOM present")
    try:
        back.decode(encoding)
    except UnicodeDecodeError:
        problems.append("bytes do not round-trip as %s" % encoding)

    if problems:
        sys.stderr.write("FAIL: %s\n" % "; ".join(problems))
        return 3

    print("OK wrote %s (%d bytes, %s + CRLF)" % (args.out, len(back), encoding))
    print("URL: http://127.0.0.1:%d/%s" % (args.port, args.page.replace("\\", "/").lstrip("/")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
