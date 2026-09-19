---
name: windows-local-server-launcher
name_en: Windows Local Server Launcher
name_zh: Windows 本地服务器双击启动器
description: Builds a robust Windows double-click launcher that starts a local http.server and auto-opens the browser without the console window flashing closed. Use when the user asks for a double-click start script / .bat launcher / 双击启动 / 启动脚本 / 本地服务器, or reports 窗口闪退, .bat 双击没反应, 端口被占用, 批处理中文乱码, or names the root causes directly - CRLF vs LF line endings, GBK(cp936) vs UTF-8 batch encoding and chcp, `where py >nul 2>nul && set` never firing versus `if not errorlevel 1`, TIME_WAIT leaving a port unbindable for ~30s, `%~dp0` relative roots, or a 404-on-assets page served from the wrong directory - or needs a local web page (asset gallery, Spine player, dashboard, report preview) served over http://127.0.0.1.
description_en: Builds a robust Windows double-click launcher that starts a local http.server and auto-opens the browser without the console window flashing closed. Use for .bat launchers, flash-closing consoles, occupied ports, batch mojibake, TIME_WAIT bind failures, CRLF/LF and GBK-vs-UTF-8 batch encoding, `where ... && set` not firing, wrong `%~dp0` roots serving 404 assets, or serving a local web page over http://127.0.0.1.
description_zh: 在 Windows 上做出稳健的“双击即启动本地 http.server 并自动打开浏览器、窗口不闪退”启动器。用于用户要双击启动脚本 / .bat 启动器 / 本地服务器，或遇到窗口闪退、双击没反应、端口被占用、批处理中文乱码；也用于用户直接点出根因时——CRLF/LF 换行、GBK(cp936) 与 UTF-8 及 chcp、`where py >nul 2>nul && set` 不触发（须用 `if not errorlevel 1`）、TIME_WAIT 导致端口约 30 秒绑不上、`%~dp0` 根目录选错导致资源全 404，以及需要把本地网页（资产库、Spine 播放器、看板、报告预览）通过 http://127.0.0.1 打开时。
argument-hint: Path to the local page to serve (e.g. C:\proj\web\index.html) and the port
argument-hint-en: Path to the local page to serve (e.g. C:\proj\web\index.html) and the port
argument-hint-zh: 给出要服务的本地页面路径（如 C:\proj\web\index.html）和端口
user-invocable: true
version: 1.1.0
---

# Windows Local Server Launcher

## When to use

The user needs a file they can **double-click on Windows** to get a local web page served over `http://127.0.0.1:<port>` with the default browser opening automatically.

Typical triggers: `双击启动`, `启动脚本`, `.bat 打不开`, `窗口闪退`, `闪退`, `端口被占用`, `批处理乱码`, or a page that must be served over http because `fetch()`/XHR is blocked by CORS under `file://`.

**Not for:** deploying to a real host, publishing pages online, non-Windows platforms, or servers more complex than a static file handler.

## Architecture — the one rule that matters

Put all logic in **Python**; the `.bat` is a dumb shell that only (1) finds `py`/`python`, (2) runs the Python launcher, (3) **always** ends in `pause`.

Pure batch will keep failing on encoding, port state, and error visibility. Every flash-close loop traced back to batch trying to own those three things.

```
启动XXX.bat          GBK(cp936) + CRLF, chcp 936, minimal shell, ends with pause
_qw_server.py        ThreadingTCPServer + allow_reuse_address, port probe, browser open
```

## Root cause chain (why batch alone always loses)

These four hit in sequence in a real debugging session; each one looks like a new, unrelated bug:

1. **LF endings** → window flashes closed, nothing seems to run. `cmd.exe` mis-parses LF-only batch and bails early.
2. **UTF-8 `.bat` with Chinese** → mojibake *plus* `系统找不到指定的路径` *plus* a false "未找到 Python". The parser desyncs on multi-byte sequences and executes garbage fragments; `chcp 65001` does not save it.
3. **`where py >nul 2>nul && set "PYEXE=py"`** → `PYEXE` stays empty even though `where py` is rc 0, so the launcher reports Python missing. `&&` does not fire after redirections.
4. **`TIME_WAIT`** → works once, then every double-click dies instantly, because the socket left by the closed window keeps the port unbindable for ~30 s and plain `http.server` exits on the failed bind — with no `pause`, you never see the error.

Stop-loss: do not debug these in batch one at a time. Hand 3 and 4 to Python (`allow_reuse_address`, port probe-and-reuse, blocking tail) and let the `.bat` own only 1 and 2 by being generated as GBK+CRLF.

## Workflow

### Step 1 — Create the Python launcher

Copy `scripts/server_launcher.py` next to the page directory. **Do not edit it** — everything is configured by CLI args:

```bash
python scripts/write_bat.py \
  --out "D:\proj\web\启动预览.bat" \
  --server-py _qw_server.py \
  --root "D:\proj" \
  --page "web/index.html" \
  --port 8777 \
  --title "项目预览 (本地服务器)"
```

`--root` is the served directory; `--page` is the path *relative to `--root`* that gets opened.

**Choose `--root` from the page's own references** — inspect before you pick:

```bash
grep -oE '(\.\./|src=|href=)[^"'"'"' ]+' index.html | sort -u | head -20
grep -nE "const +P *=|P *= *'[^']*'" index.html
```

Rule: `--root` must be high enough that **every** `../` in the page resolves. A page holding `P = '../'` (or `<img src="../paintings/x.png">`) has to be served from its **parent**, so `--root` = parent dir and `--page` = `<subdir>/index.html`; in batch terms that root is `%~dp0..`.

Wrong-root symptom: the page loads with HTTP 200 but every image/JSON/model 404s. That is a `--root` choice error, not a launcher bug — fix `--root`, do not touch the encoding or the port.

The launcher's hard requirements (already implemented — verify they survive any edit):

- `socketserver.ThreadingTCPServer` subclass with `allow_reuse_address = True` — without it, a `TIME_WAIT` socket left by the previous window makes the bind fail and the window dies instantly.
- **Port probe before binding** (`socket.connect_ex`): if something is already listening, print `[QW-LAUNCHER] REUSE url=...`, open the browser anyway, and `input()` instead of starting a second server.
- `threading.Timer(1.5, open_browser)` so the browser opens while the server is already accepting; `webbrowser.open` with `os.startfile` fallback.
- Every exit path is visible: `OSError` on bind prints `[QW-LAUNCHER] BIND-FAIL ...` then `input("按回车退出")`. Never let the script return to the shell without `pause`/`input()`.
- **Do not** `sys.stdout.reconfigure(...)`. A real Windows console renders Chinese natively through `WriteConsoleW`; reconfiguring it to utf-8 makes the console garble.
- Stable ASCII markers on stdout (`SERVING` / `REUSE` / `BIND-FAIL`) — verification depends on them, and they are immune to console codepage decoding.

### Step 2 — Generate the `.bat` with `scripts/write_bat.py`

`python scripts/write_bat.py --out <bat> --server-py <py name> --root <dir> --page <rel> --port <n> --title <text>`

It writes **GBK + CRLF** and emits the safe detection form. Never hand-write a `.bat` containing Chinese with the Write tool — it produces UTF-8/LF, which is the bug.

Generated shell shape:

```bat
@echo off
chcp 936 >nul
title <title>
where py >nul 2>nul
if not errorlevel 1 (
  py "<script>" --root "<root>" --page "<page>" --port <n>
  goto end
)
where python >nul 2>nul
if not errorlevel 1 (
  python "<script>" --root "<root>" --page "<page>" --port <n>
  goto end
)
echo [错误] 未找到 py 或 python，请先安装 Python 并加入 PATH。
:end
pause
```

If a title/echo cannot be encoded in GBK (emoji, rare CJK), the writer fails loudly — shorten to plain Chinese/ASCII rather than switching the file to UTF-8.

### Step 3 — Verify without double-clicking

```bash
python scripts/verify_bat.py --bat "<path>\启动预览.bat" --url "http://127.0.0.1:8777/web/index.html"
```

It drives the real `.bat` through `subprocess` + `cmd` and asserts three scenarios:

1. **Fresh start** → `[QW-LAUNCHER] SERVING` present, port `LISTENING`, `GET url` returns 200.
2. **Kill then immediately restart** → binds again (proves `allow_reuse_address` beat `TIME_WAIT`).
3. **Already running** → second run prints `REUSE`, does not crash, does not steal the port.

Then it kills leftover listeners and confirms the port is free.

**Judging rule:** only trust the ASCII markers and the HTTP status code. Chinese captured through a pipe looks like mojibake in your harness even when the file is perfect — that is a decoding artifact, not a bug. Do not "fix" encoding based on it.

**If `verify_bat.py` is not available**, drive it yourself:

```python
env = dict(os.environ, QW_LAUNCHER_NO_BROWSER="1")   # never pop browsers during tests
p = subprocess.Popen(["cmd", "/c", bat], cwd=os.path.dirname(bat),
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, env=env)
# the server line blocks by design -> read stdout in a thread, then poll
# netstat for LISTENING and assert urlopen(url).getcode() == 200
# finally taskkill /PID <pid> /T /F (argument list, not a shell string)
```

Two hard rules while verifying:

- Prove `py -m http.server <port> --directory <root>` serves the page with 200 **first**. If that fails, the page/`--root` is wrong, not the `.bat`.
- Never verify with `start` (GUI launch hangs or is unreliable unattended); use `cmd /c` with a timeout and read the output.

### Step 4 — Deliver

Tell the user: double-click the `.bat`; the console stays open while the server runs, closing it stops the server; first run may need right-click → Properties → "仍要打开" (SmartScreen); double-clicking again while one is open just reopens the browser.

## Windows pitfall quick reference

Debugging order: first prove the server itself works (`py -m http.server <port> --directory <root>`, page returns 200), only then suspect the `.bat`. Most "启动不了" reports are the batch layer, not Python.

| Symptom | Root cause | Fix |
|---|---|---|
| Window flashes, nothing runs | `.bat` saved with LF-only line endings | Write CRLF (`\r\n`) |
| Chinese mojibake **+** "系统找不到指定的路径" / bogus "未找到 Python" | `.bat` saved as UTF-8; cmd reads it as ANSI, parser desyncs and executes garbage fragments | Save the `.bat` as GBK(cp936) and `chcp 936 >nul` |
| `where py` is rc 0 yet the branch never runs | `where py >nul 2>nul && set "X=py"` — `&&` does **not** fire after redirections | Split: `where py >nul 2>nul` then `if not errorlevel 1 set "X=py"` |
| Works once, then every double-click dies instantly | `TIME_WAIT` on the port for ~30 s after closing the window; plain `http.server` fails to bind and the script ends | `allow_reuse_address = True` + probe-and-reuse + `pause` |
| Any error is invisible | No `pause`/`input()` after the blocking server line | End the `.bat` with `pause`; every launcher exit path blocks |
| Page loads 200 but images/JSON/models all 404 | `--root` is the page's own directory while the page references `../assets` | Serve the parent (`--root "%~dp0.."`) and keep the subdir prefix in the URL |
| Chinese garbled only when piped | Harness decodes cp936 bytes | Ignore; assert on ASCII markers / HTTP codes |

## Additional resources

- [reference.md](reference.md) — five-stage root-cause cascade, verified batch snippets, `file://` CORS rationale, wrong-root 404 counterexample, port-forensics commands, verification recipe, anti-patterns.
