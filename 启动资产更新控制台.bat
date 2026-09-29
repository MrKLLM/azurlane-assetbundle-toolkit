@echo off
chcp 936 >nul
title 资产更新控制台 (本地服务器)
set "SCRIPT=%~dp0scripts\pipeline_panel.py"
REM 参数会透传，例如：启动资产更新控制台.bat --port 8790 --no-open

REM 先找 py 再找 python。注意 `where py >nul && set "X=py"` 这种写法永远不触发，
REM 必须拆成两行用 `if not errorlevel 1` 判（本项目踩过）。
where py >nul 2>nul
if not errorlevel 1 (
  py "%SCRIPT%" %*
  goto end
)
where python >nul 2>nul
if not errorlevel 1 (
  python "%SCRIPT%" %*
  goto end
)
echo [错误] 没找到 py 或 python，请先安装 Python 并加入 PATH。

:end
REM 不管怎么退出都要停在这里，避免窗口一闪而过看不到报错。
pause
