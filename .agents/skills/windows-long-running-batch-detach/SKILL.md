---
name: windows-long-running-batch-detach
description: 在 Windows 上用完全脱离宿主的分离进程跑长时本地批处理与回归脚本（数据导出、批量渲染、全量校验、CDP 回归），并正确判定它是否真的跑完。当单轮预计超过约 8 分钟，或出现「completed exit code 0 但输出行异常少」「跑一半没了」「后台任务自己结束」「批量任务超时被杀」时使用。覆盖宿主超时上限、shell 复合命令退出码遮蔽、Start-Process 隐藏窗口重定向、进度行轮询、崩溃/截断/完成的三分法判定。触发词：长时批处理、跑一半断了、后台超时、脱离进程、Start-Process、轮询日志、退出码 0 但没跑完。
---

# Windows 长时批处理：脱离宿主 + 真实完成判定

## Overview

宿主端命令执行器对单条命令有硬性时长上限（默认 2 分钟，最大 10 分钟），后台执行同样受该上限约束。超过上限的任务会被静默终止；而 `cmd > log; tail log` 这类复合命令的整体退出码取自最后一条命令（恒 0），于是「completed exit code 0」可以完全掩盖一次中断。本技能规定：长任务怎么真正脱离出去，以及用什么证据判定它跑完了。

## 何时用 / 何时不用

- 用：单轮预计 > 8 分钟；无头浏览器或 CDP 全量回归；> 1000 文件的批量导出或渲染；任何要在结果上签「通过」的校验。
- 不用：秒级到几分钟的命令，直接前台跑并读真实退出码——detach 只会让你丢掉实时输出。

## 规则 1：先估时，再决定执行方式

跑之前先答一句「这一轮预计多少分钟」，依据是历史同类日志耗时、或条目数 × 单条耗时。拿不准按最坏估。超过 8 分钟即按规则 2、3 走，**不要**把超时参数拉到上限来凑——上限到点就杀，不给你收尾的机会。

## 规则 2：禁止用 shell 复合命令的退出码判定成败

反模式（退出码其实是 `tail` 的，脚本怎么死的看不出来）：

```bash
py scripts/diag/verify.py > .diag/_run.log; echo EXIT=$?; tail .diag/_run.log
```

同理 `a && b`、`a; b`、管道 `a | tee`（取到的是 tee 的码）——末尾命令说了算。要真退出码，只能单独跑那一条并读它自己的退出码，或用规则 3 的 wrapper 读 `ExitCode`。

## 规则 3：完全脱离宿主启动

用 PowerShell `Start-Process`，stdout 与 stderr 各指独立文件（**不能指向同一个**，PowerShell 会直接报错），`-PassThru` 拿到 PID 落盘：

```bash
powershell -NoProfile -Command 'Start-Process -FilePath py -ArgumentList "scripts/diag/verify.py","--all" -WorkingDirectory "D:\proj" -WindowStyle Hidden -RedirectStandardOutput "D:\proj\.diag\_run.log" -RedirectStandardError "D:\proj\.diag\_run.err" -PassThru | ForEach-Object { $_.Id } | Set-Content "D:\proj\.diag\_run.pid"'
```

- `-WindowStyle Hidden` 避免弹控制台；日志路径写绝对路径，相对路径参数才和 `-WorkingDirectory` 对得上。
- PID 必须落盘，否则下一次会话无从判断有没有旧进程在跑。
- detach 后你看不到实时输出、也不能靠宿主中断它——所以规则 6 的进度行是前置条件。

需要真退出码时，用 wrapper 等待后读进程对象（退出码只用来区分「崩了」与「正常结束」，仍不作为完成判据）：

```powershell
$p = Start-Process -FilePath py -ArgumentList "scripts/diag/verify.py" -WorkingDirectory "D:\proj" -WindowStyle Hidden -RedirectStandardOutput "D:\proj\.diag\_run.log" -RedirectStandardError "D:\proj\.diag\_run.err" -PassThru
$p.Id | Set-Content "D:\proj\.diag\_run.pid"
$p.WaitForExit()
$p.ExitCode | Set-Content "D:\proj\.diag\_run.code"
```

## 规则 4：判定「跑完」的唯一依据是脚本自己打印的汇总行

汇总/终判行（如 `总判定: ALL PASS`、`完成 269/269`）是真实可观测状态。以下都是代理指标，**不得单独作为通过证据**：退出码 0、日志行数、文件大小、mtime 停止变化、后台任务状态显示 completed。

因此长任务脚本本身必须：正常结束时打印一条**固定可 grep** 的汇总行（成功与失败都打，用不同字面量）；并以真实退出码退出。

## 规则 5：日志三分法，别把中断读成通过

轮询节奏 60–120 秒一次，每次都是独立的一条短命令（`tail`/`grep` + 查进程），不要在一个 sleep 循环里等：

```bash
grep -c "总判定" .diag/_run.log; tail -3 .diag/_run.log; tail -5 .diag/_run.err
powershell -NoProfile -Command 'Get-Process -Id (Get-Content "D:\proj\.diag\_run.pid") -ErrorAction SilentlyContinue | Select-Object Id,ProcessName'
```

| 汇总行 | 进程 | err 日志 | 结论与处置 |
|---|---|---|---|
| 在 | 已退 | 任意 | 按汇总行内容判定通过/失败 |
| 不在 | 在 | — | 还在跑，继续轮询，报「进行中 + 最后一条进度行」 |
| 不在 | 已退 | 有 traceback | 崩了。报告异常类型 + 最后一条进度行指示跑到第几条 |
| 不在 | 已退 | 干净无 traceback | 被外部截断或杀掉。这一轮**作废**，不得记为通过 |

## 规则 6：长跑必须可重入、按条目推进

- 每条处理完 `print(..., flush=True)` 输出进度行，例如 `[213/269] name`。没有 flush，脱离后日志会长时间空着，你就无法区分「慢」和「死」。
- 按条目独立推进并落盘已完成集合，支持跳过续跑；不要把整轮当原子操作。
- 连接类故障（CDP/WebSocket 的 `WinError 10054`、端口占用、目标页被刷新）在长轮里是**常态而非意外**，脚本侧要能跳过单条继续或明确报断点，而不是整轮崩在 254/269。
- 长跑期间**不得改动被回归的输入**（页面、产物、配置）。改了，这一轮结果即刻作废并如实说明，不要拿旧日志的局部通过交差。
- 重跑前先读 PID 确认旧进程已终止：双进程并发写同一输出目录会静默互相污染。

## Windows 编码硬约束

`Start-Process` 重定向的 stdout 默认按本地代码页（GBK）写，脚本里任何非 ASCII `print`（哪怕一个勾号 `✓`）都会 `UnicodeEncodeError`，把正常跑完的一轮记成失败——而图像/产物其实已写出。主进程 `sys.stdout.reconfigure(encoding="utf-8")` 加子进程环境 `PYTHONIOENCODING=utf-8`，双保险。细节见 `unity-assetbundle-painting-restore`。

## 向用户报告时

引用可核对的证据：日志实际行数、最后一条进度行、汇总行原文、进程是否存活。**不要**引用「后台任务 completed / exit code 0」当作跑完的证明。截断或作废就直说截断或作废。

## 相关技能（避免重复展开）

- `headless-chrome-cdp-batch-export`：浏览器端批量渲染导出，本技能管宿主端时长与判定。
- `unity-assetbundle-painting-restore`：全量合成的分离进程与编码踩坑细节。
- `safe-pipeline-fix-targeted-rerun`：全量前先小样本验证与零回退闸门。
