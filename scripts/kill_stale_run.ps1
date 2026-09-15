# 终止所有 run_v2_full / extract_spine_v2 python 进程
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'run_v2_full|extract_spine_v2' }
foreach ($p in $procs) {
    Write-Output ("killing PID " + $p.ProcessId + " : " + $p.CommandLine)
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
if (-not $procs) { Write-Output "no matching processes" }
