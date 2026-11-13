# Reference: Windows local server launcher

## Why http and not `file://`

Pages that call `fetch()`, XHR, or load local JSON/module assets are blocked by CORS under `file://` (origin `null`). A Spine player, an asset gallery, or any ES-module page therefore must be served over `http://127.0.0.1:<port>`. This is the usual reason a "just open the html" instruction fails.

## Failure cascade from a real session

A pure-batch launcher does not fail once; it fails in layers, and each fix reveals the next bug. This is the order they appeared, with what the user saw versus what was actually true:

| # | User sees | Actually true | Resolved by |
|---|---|---|---|
| 1 | Double-click, window flashes, nothing at all | `.bat` written with LF endings; `cmd.exe` bails early | CRLF |
| 2 | Window appears but Chinese is mojibake and it prints `系统找不到指定的路径` | `.bat` saved UTF-8; cmd reads it as ANSI and executes garbage byte fragments | GBK(cp936) + `chcp 936` |
| 3 | `[错误] 未找到 py 或 python`, although `where py` in the same shell is rc 0 | `where py >nul 2>nul && set "PYEXE=py"` — `&&` never fires after redirections | `if not errorlevel 1 set` |
| 4 | Works exactly once, then every double-click flashes closed | Previous window left a `TIME_WAIT` socket; `http.server` failed to bind and exited; no `pause`, so the error was never visible | `allow_reuse_address = True` + probe-and-reuse + blocking tail |
| 5 | Page opens, all assets 404 | `--root` was the page directory while the page uses `../` | move `--root` to the parent |

The cascade ended only at stage 4, when the logic moved into a Python launcher: stages 3–5 are all things batch should not own. Rewriting the batch script again at stage 3 or 4 is the trap — the fix is architectural, not incremental. (Stage 5 is independent of encoding/port trouble: it is a wrong `--root`, caught by reading the page's own references.)

## Path layout

The browser URL path is resolved against the served root, so relative references in the page decide the root:

- Page at `<root>/index.html` referencing `./assets/...` → serve the page's own directory.
- Page referencing `../paintings/x.png` (a common `P = '../'` pattern) → serve the **parent**, and open `http://127.0.0.1:<port>/<subdir>/index.html`.

In batch, `%~dp0` is the `.bat` directory **with** a trailing backslash, so `%~dp0..` means its parent — that is the value to pass as `--root`. `%~dp0script.py` correctly resolves to a sibling file.

Inspect the page before choosing the root:

```bash
grep -oE '(\.\./|src=|href=)[^"'"'"' ]+' index.html | sort -u | head -20
grep -nE "const +P *=|P *= *'[^']*'" index.html
```

Counterexample that costs a whole debugging round: the page at `Output/gallery_v2/index.html` holds `const P = '../'`, but the launcher serves `--root "...\gallery_v2"`. The page itself opens with HTTP 200 while every painting, thumbnail, and `index.json` request 404s. Nothing is wrong with the encoding, the detection, or the port — `--root` has to move up to `Output` and `--page` becomes `gallery_v2/index.html`. Rule of thumb: the served root is whatever directory makes the page's longest `../` chain resolve.

## Verified batch snippets

Detection — the only form that works. `&&` after redirections never fires, even at errorlevel 0:

```bat
where py >nul 2>nul
if not errorlevel 1 set "PYEXE=py"
if not defined PYEXE (
  where python >nul 2>nul
  if not errorlevel 1 set "PYEXE=python"
)
```

Diagnostic to prove which form broke (run under `cmd /c`):

```bat
@echo off
where py >nul 2>nul
echo     errorlevel=%errorlevel%
set "X="
where py >nul 2>nul && set "X=hit"
echo     X=[%X%]         REM empty, even though errorlevel=0
set "Y="
where py >nul 2>nul
if not errorlevel 1 set "Y=hit"
echo     Y=[%Y%]         REM hit
```

Port forensics (Windows):

```bat
netstat -ano | findstr :8777
taskkill /PID <pid> /T /F
```

Inside a `for /f` command, escape the pipes as `^|` and double the loop variable (`%%a`):

```bat
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8777" ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>nul
```

Prefer letting `allow_reuse_address` handle it over killing processes from batch: a `netstat`-driven `taskkill` can race and kill the wrong PID.

## Encoding rules

| File | Encoding | Line endings |
|---|---|---|
| `.bat` containing Chinese | GBK / cp936 | CRLF |
| `.py` launcher | UTF-8 with `# -*- coding: utf-8 -*-` | LF is fine |

Why GBK: `cmd.exe` reads batch files in the ANSI codepage. A UTF-8 `.bat` makes the parser desync on the multi-byte sequences and execute garbage fragments — the classic compound symptom is mojibake **plus** `系统找不到指定的路径` **plus** a bogus "未找到 Python" branch. `chcp 65001` does not rescue it.

Why CRLF: LF-only batch files make `cmd.exe` mis-parse and bail early, which looks exactly like "double-click, window flashes, gone".

Verify bytes, don't trust the editor:

```bash
python -c "d=open(r'D:\\x\\启动.bat','rb').read(); print(d[:14]); print(b'\\r\\n' in d, d.decode('gbk')[:40])"
```

`file` labels GBK content as `ISO-8859` — that is expected, not a problem.

## Console output of the Python launcher

Print Chinese directly. A real console renders it through `WriteConsoleW`, independent of `chcp`. Adding `sys.stdout.reconfigure(encoding='utf-8')` **breaks** the console while making the pipe look nicer — optimize for the user's console, not the harness.

## Verification playbook

`scripts/verify_bat.py` drives the real `.bat` with `subprocess` + `cmd /c`, `stdin=PIPE` (so `pause`/`input()` blocks harmlessly), and `QW_LAUNCHER_NO_BROWSER=1` (so no browser pops during tests).

Manual recipe when the script is not available:

```python
import os, subprocess, threading, time, urllib.request
bat = r"D:\proj\web\启动预览.bat"
env = dict(os.environ, QW_LAUNCHER_NO_BROWSER="1")
p = subprocess.Popen(["cmd", "/c", os.path.basename(bat)],
                     cwd=os.path.dirname(bat), stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
lines = []
threading.Thread(target=lambda: [lines.append(l.decode("gbk", "replace"))
                                 for l in iter(p.stdout.readline, b"")],
                 daemon=True).start()
time.sleep(4)                       # the server line blocks forever by design
code = urllib.request.urlopen("http://127.0.0.1:8777/web/index.html", timeout=5).getcode()
assert code == 200 and any("[QW-LAUNCHER] SERVING" in l for l in lines)
subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
```

- Never verify by `start` (GUI launch is unreliable unattended and can hang the caller).
- Never assert on captured Chinese; decode artifacts make correct files look broken.
- The server line blocks by design, so a run that "hangs" until you kill it is the **pass**; read output from a thread.
- Scenario 2 exists specifically to catch `TIME_WAIT`: kill abruptly, wait ~1 s, restart. A plain `python -m http.server` fails to bind there; `allow_reuse_address = True` succeeds.
- `//PID`-style arguments get rejected by some shells as UNC paths; call `taskkill` through `subprocess` argument lists.

## Anti-patterns

- Pure batch owning the port cleanup, the browser launch, and the error reporting.
- Nested-quote one-liners like `start "" cmd /c "timeout /t 2 & start """" ""%URL%"` — use `threading.Timer` + `webbrowser.open` in Python instead.
- Silently killing whatever listens on the port.
- Switching the `.bat` to UTF-8 to "fix" mojibake seen through a pipe.
- Debugging 404-on-assets as an encoding or port problem — it is the served `--root`.
- Iterating on the batch script once you reach the `&&`-or-TIME_WAIT stage; that is the signal to move the logic into Python.
- `python -m http.server` as the final line with nothing after it.
