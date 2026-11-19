# probe_exit_events.ps1 -- does the kernel's process-exit stream account for wtf-perf's ~3-point remainder?
# Read-only measurement; needs an elevated shell. Records Microsoft-Windows-Kernel-Process (process
# start/stop, keyword 0x10) with logman while wtf-perf samples for 15 s, then counts the processes that
# exited in the window and how many of them wtf-perf saw. Prediction written before running: most exits
# in the window were seen (wtf-perf polls every 100 ms), so the exit stream alone will NOT explain the
# remainder -- pointing at kernel time charged to no process.
param([int]$Seconds = 15)
$ErrorActionPreference = 'Stop'
$etl = Join-Path $env:TEMP 'wtfperf-kproc.etl'
if (Test-Path $etl) { Remove-Item $etl }
logman create trace wtfperf-kproc -p Microsoft-Windows-Kernel-Process 0x10 -o $etl -ets | Out-Null
try {
    $json = & python -m wtf_perf cpu --seconds $Seconds --json --top 2000 2>$null | Out-String
} finally {
    logman stop wtfperf-kproc -ets | Out-Null
}
$report = $json | ConvertFrom-Json
$stops = Get-WinEvent -Path $etl -Oldest | Where-Object { $_.Id -eq 2 }
$seenExited = @($report.processes | Where-Object { $_.exited }).Count
"window: {0:N1}s  busy {1:N2}  unexplained {2:N2}" -f $report.window.seconds, $report.reconciliation.busy, $report.reconciliation.unexplained
"kernel exit events in the window: {0}   exited processes wtf-perf saw: {1}   (exited count in ledger: {2})" -f $stops.Count, $seenExited, $report.reconciliation.exited_count
$missed = $stops.Count - $report.reconciliation.exited_count
"processes that exited without wtf-perf ever seeing them: {0}" -f $missed
# Cycles of the unseen exits, converted to points: cycles / (seconds * cpus * nominal Hz * perf%) * 100.
$seenPids = @{}; foreach ($p in $report.processes) { $seenPids[[int]$p.pid] = $true }
$cyc = [double]0; $n = 0
foreach ($e in $stops) {
    $x = [xml]$e.ToXml(); $d = @{}; foreach ($i in $x.Event.EventData.Data) { $d[$i.Name] = $i.'#text' }
    if (-not $seenPids.ContainsKey([int]$d['ProcessID']) -and $d['CPUCycleCount']) { $cyc += [double]$d['CPUCycleCount']; $n++ }
}
$hz = 4.201e9 * ([double]$report.counters.performance / 100)
$pts = 100 * $cyc / ($report.window.seconds * $report.window.logical_cpus * $hz)
"unseen exits with cycle counts: {0}   their CPU: {1:N2} points   vs unexplained {2:N2}" -f $n, $pts, $report.reconciliation.unexplained

# RESULT 1, 2026-11-18 ~23:05 (elevated, 15 s): busy 36.51, unexplained 0.56; kernel exit events 104,
# exited processes wtf-perf saw 59 -> 45 exited unseen (43%). Short-lived processes DO slip between polls;
# in this window they cost little. Next: sum the exit events' CPUCycleCount for the unseen ones and
# compare with the remainder across busy runs (decides adopting the stream vs relaxing the bar).
# RESULT 2-3, 2026-11-18 ~23:15 (15 s each): busy 28.46 / 28.26, unexplained 0.39 / 0.37; unseen exits
# 16 / 3 whose CPUCycleCount converts to 0.10 / 0.02 points -- about 5-25% of the remainder. The exit stream
# would not close the gap at this load; most of it is CPU charged to no process. A busy run (busy ~40,
# remainder ~3.4) is still owed to confirm the split under load. Conversion uses nominal Hz x perf%: approximate.
# RESULT 4-5, 2026-11-18 ~23:25 -- the controlled test. Quiet: busy 15.74, unexplained 0.25, 26 unseen exits =
# 0.18 points (72%). With a background `cmd /c exit` loop: busy 23.42, unexplained 4.01, 1017 of 1175 exits
# unseen, = 2.98 points (74%). So when the remainder is LARGE it is mostly short-lived processes the 100 ms
# poll never sees, and the exit stream would close most of it; at low churn the remainder is small either
# way. This REVERSES the reading of results 2-3 and of the 100-vs-50 ms comparison (a `cmd /c exit` lives
# far less than 50 ms, so halving the interval could not catch them). The prediction at the top was wrong.
