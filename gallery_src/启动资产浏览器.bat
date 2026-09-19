@echo off
chcp 936 >/dev/null
title 碧蓝航线资产浏览器 (本地服务器)
set "SCRIPT=%~dp0_gallery_server.py"

REM 优先用 py 启动器，其次 python；找到即运行（前台，关窗口即停）
where py >/dev/null 2>/dev/null
if not errorlevel 1 (
  py "%SCRIPT%"
  goto end
)
where python >/dev/null 2>/dev/null
if not errorlevel 1 (
  python "%SCRIPT%"
  goto end
)
echo [错误] 未找到 py 或 python，请先安装 Python 并加入 PATH。

:end
REM 无论正常退出还是报错，都停在这里，避免窗口一闪而过
pause
