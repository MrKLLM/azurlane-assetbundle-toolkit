# scripts/diag/wait_for_detached.ps1 —— 判定 Start-Process 脱离任务是否真的跑完（只读，不动任何文件）
#
# 为什么需要它（2026-09-24 两次误判）：
#   * `Start-Process -PassThru` 拿到的是 **启动器**（`py.exe`）的 PID，不是干活的 `python.exe`；
#   * `Wait-Process -Id <启动器>` 抛错（权限/句柄）会被 try/catch 读成「进程已退出」，
#     于是还在跑的长任务被误判成断了；反之启动器早退而工作进程还在跑也会误判。
#   * 判活的正确对象 = 命令行里带该脚本名的 **python.exe**；再配日志行数是否还在涨 + stderr 有无 traceback。
#
# 用法（PowerShell，不要在 bash 里拼引号）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\diag\wait_for_detached.ps1 -Pattern l2d_sweep
#   ... -Pattern hit_verify -MaxSeconds 1800 -Log .diag\_run.log -SummaryRegex '总计|SUMMARY|汇总'
param(
  [Parameter(Mandatory = $true)][string]$Pattern,
  [int]$MaxSeconds = 1800,
  [int]$StallRounds = 0,
  [string]$Log = '',
  [string]$SummaryRegex = '总计|SUMMARY|汇总|总判定'
)
$ErrorActionPreference = 'SilentlyContinue'
$still = 0

function Worker {
  Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq 'python.exe') -and ($_.CommandLine -match $Pattern)
  } | Select-Object -First 1
}

function Lines([string]$f) {
  if ($f -and (Test-Path $f)) { (Get-Content $f | Measure-Object -Line).Lines } else { -1 }
}

$deadline = (Get-Date).AddSeconds($MaxSeconds)
$last = Lines $Log
$w = Worker
while ($w -and (Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 20
  $now = Lines $Log
  $proc = Get-Process -Id $w.ProcessId -ErrorAction SilentlyContinue
  $age = if ($proc) { [int](((Get-Date) - $proc.StartTime).TotalSeconds) } else { -1 }
  if ($now -eq $last) { $still++ } else { $still = 0 }
  Write-Output ("... running pid=" + $w.ProcessId + " age=" + $age + "s loglines=" + $now +
                " 未增长轮数=" + $still)
  if ($StallRounds -gt 0 -and $still -ge $StallRounds) {
    Write-Output "RESULT=HUNG  进程活着但日志连续 $still 轮不增长 —— 按「崩溃/截断」处理，不要等它收尾"
    exit 3
  }
  $last = $now
  $w = Worker
}

Write-Output "----- 三分法判定 -----"
if ($w) {
  Write-Output "RESULT=STILL_RUNNING  （超过本次等待上限，继续用同一命令轮询；不要当完成）"
  exit 0
}
$sum = if ($Log -and (Test-Path $Log)) { Get-Content $Log | Select-String -Pattern $SummaryRegex | Select-Object -Last 3 } else { $null }
if ($sum) {
  Write-Output "RESULT=DONE_WITH_SUMMARY"
  $sum | ForEach-Object { Write-Output ("  " + $_.Line) }
  exit 0
}
$errFile = if ($Log) { $Log -replace '\.log$', '.err' } else { '' }
if ($errFile -and (Test-Path $errFile) -and (Get-Content $errFile | Select-String -Pattern 'Traceback|Error')) {
  Write-Output "RESULT=CRASHED （读 err 文件取异常类型与最后一条进度行）"
  exit 1
}
Write-Output "RESULT=TRUNCATED 无汇总行且无异常 —— 这一轮作废，不得记为通过"
exit 2
