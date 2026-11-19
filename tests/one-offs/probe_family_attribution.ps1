# probe_family_attribution.ps1 -- read-only measurement, no changes to the system.
# Question: how much CPU and file I/O belongs to the Claude Code family
# (claude*, csb, codex and everything they spawn), counting short-lived children?
# Method: full process snapshot A, poll for new PIDs every ~1s, full snapshot B,
# then attribute every process to a family by walking its parent chain.
param([int]$Seconds = 30)
$ErrorActionPreference = 'SilentlyContinue'
$lp = [Environment]::ProcessorCount
$props = 'ProcessId','ParentProcessId','Name','CommandLine','KernelModeTime','UserModeTime','ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount'
$elev = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
"Elevated: $elev   logical CPUs: $lp"

# transcript files: sizes now
$proj = Join-Path $env:USERPROFILE '.claude\projects'
$j0 = @{}
$jfiles = Get-ChildItem $proj -Recurse -Filter *.jsonl -File
foreach ($f in $jfiles) { $j0[$f.FullName] = $f.Length }

$sw = [Diagnostics.Stopwatch]::StartNew()
$A = @{}; Get-CimInstance Win32_Process -Property $props | ForEach-Object { $A[[int]$_.ProcessId] = $_ }
$tA = $sw.Elapsed.TotalSeconds
$seen = @{}; foreach ($k in $A.Keys) { $seen[$k] = $true }
$born = @{}          # pid -> info for processes first seen during the window
$polls = 0
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    $polls++
    $new = @()
    foreach ($p in [Diagnostics.Process]::GetProcesses()) {
        if (-not $seen.ContainsKey($p.Id)) { $seen[$p.Id] = $true; $new += $p.Id; $born[$p.Id] = [pscustomobject]@{ PID = $p.Id; Name = $p.ProcessName; Parent = $null; Cmd = $null } }
    }
    if ($new.Count -gt 0) {
        $flt = ($new | ForEach-Object { "ProcessId=$_" }) -join ' OR '
        Get-CimInstance Win32_Process -Filter $flt -Property ProcessId,ParentProcessId,Name,CommandLine | ForEach-Object {
            $born[[int]$_.ProcessId].Parent = [int]$_.ParentProcessId; $born[[int]$_.ProcessId].Cmd = $_.CommandLine; $born[[int]$_.ProcessId].Name = $_.Name
        }
    }
    Start-Sleep -Milliseconds 700
}
$tB0 = $sw.Elapsed.TotalSeconds
$B = @{}; Get-CimInstance Win32_Process -Property $props | ForEach-Object { $B[[int]$_.ProcessId] = $_ }
$tB = $sw.Elapsed.TotalSeconds
$secs = (($tB0 + $tB) / 2) - ($tA / 2)
"Window ~{0:N1}s (snapshot A took {1:N2}s, B took {2:N2}s), polls={3}" -f $secs, $tA, ($tB - $tB0), $polls

# parent map from everything we know
$parent = @{}; $name = @{}; $cmd = @{}
foreach ($s in @($A, $B)) { foreach ($k in $s.Keys) { $parent[$k] = [int]$s[$k].ParentProcessId; $name[$k] = $s[$k].Name; $cmd[$k] = $s[$k].CommandLine } }
foreach ($k in $born.Keys) { if ($null -ne $born[$k].Parent) { $parent[$k] = $born[$k].Parent }; if (-not $name.ContainsKey($k)) { $name[$k] = $born[$k].Name }; if ($born[$k].Cmd) { $cmd[$k] = $born[$k].Cmd } }

function Get-Family([int]$id) {
    $c = $id; $d = 0
    while ($d -lt 25) {
        $n = $name[$c]
        if ($n -match '^claude') { return 'claude-code' }
        if ($n -match '^csb')    { return 'csb' }
        if ($n -match '^codex')  { return 'codex' }
        if ($cmd[$c] -match 'session-logger|Claude-Session-Backup|claude-bookmarks') { return 'claude-tooling(cmdline)' }
        if (-not $parent.ContainsKey($c) -or $parent[$c] -eq $c -or $parent[$c] -eq 0) { break }
        $c = $parent[$c]; $d++
    }
    $n0 = $name[$id]
    if ($n0 -match '^dopus') { return 'directory-opus' }
    if ($n0 -match '^(System Idle Process)$') { return 'IDLE' }
    return 'other'
}

$rows = foreach ($id in $B.Keys) {
    $y = $B[$id]; $x = $A[$id]
    $k0 = 0; $u0 = 0; $r0 = 0; $w0 = 0; $o0 = 0; $wb0 = 0
    if ($x) { $k0 = $x.KernelModeTime; $u0 = $x.UserModeTime; $r0 = $x.ReadOperationCount; $w0 = $x.WriteOperationCount; $o0 = $x.OtherOperationCount; $wb0 = $x.WriteTransferCount }
    [pscustomobject]@{
        PID = $id; Name = $y.Name; Family = (Get-Family $id); New = (-not $x)
        Cpu = ((($y.KernelModeTime + $y.UserModeTime) - ($k0 + $u0)) / 1e7) / $secs / $lp * 100
        Ops = (($y.ReadOperationCount - $r0) + ($y.WriteOperationCount - $w0) + ($y.OtherOperationCount - $o0)) / $secs
        WrMB = ($y.WriteTransferCount - $wb0) / 1MB / $secs
    }
}
""
"===== By family: CPU (pct of machine), file ops/sec, write MB/s ====="
$rows | Group-Object Family | ForEach-Object {
    [pscustomobject]@{ Family = $_.Name; Procs = $_.Count; Cpu = ($_.Group | Measure-Object Cpu -Sum).Sum; Ops = ($_.Group | Measure-Object Ops -Sum).Sum; WrMB = ($_.Group | Measure-Object WrMB -Sum).Sum }
} | Sort-Object Cpu -Descending | ForEach-Object { "{0,-26} procs={1,4}  cpu={2,6:N2}%  ops/s={3,9:N0}  wrMB/s={4,7:N2}" -f $_.Family, $_.Procs, $_.Cpu, $_.Ops, $_.WrMB }
$nonIdle = ($rows | Where-Object { $_.Family -ne 'IDLE' } | Measure-Object Cpu -Sum).Sum
$idle = ($rows | Where-Object { $_.Family -eq 'IDLE' } | Measure-Object Cpu -Sum).Sum
"Non-idle sum={0:N2}%  idle={1:N2}%  total={2:N2}%  (unattributed={3:N2}%)" -f $nonIdle, $idle, ($nonIdle + $idle), (100 - $nonIdle - $idle)

""
"===== Churn: processes first seen during the window ====="
$bornList = @($born.Values)
$gone = @($bornList | Where-Object { -not $B.ContainsKey($_.PID) })
"born={0} ({1:N1}/s)   of which already gone at end={2}   with no parent/cmdline captured (too short-lived)={3}" -f $bornList.Count, ($bornList.Count / $secs), $gone.Count, @($bornList | Where-Object { $null -eq $_.Parent }).Count
"By family of the born processes:"
$bornList | Group-Object { Get-Family $_.PID } | Sort-Object Count -Descending | ForEach-Object { "  {0,-26} {1,4}" -f $_.Name, $_.Count }
"By image name:"
$bornList | Group-Object Name | Sort-Object Count -Descending | Select-Object -First 10 | ForEach-Object { "  {0,-30} {1,4}" -f $_.Name, $_.Count }
"Sample command lines of born processes (first 12 distinct):"
$bornList | Where-Object { $_.Cmd } | ForEach-Object { $_.Cmd.Substring(0, [Math]::Min(160, $_.Cmd.Length)) } | Select-Object -Unique -First 12 | ForEach-Object { "  $_" }

""
"===== Top 10 claude-family processes by CPU ====="
$rows | Where-Object { $_.Family -in 'claude-code','csb','codex','claude-tooling(cmdline)' } | Sort-Object Cpu -Descending | Select-Object -First 10 | ForEach-Object { "{0,6} {1,-36} {2,-22} cpu={3,5:N2}% ops/s={4,7:N0} wrMB/s={5,6:N2} new={6}" -f $_.PID, $_.Name, $_.Family, $_.Cpu, $_.Ops, $_.WrMB, $_.New }

""
"===== Transcript (.jsonl) files under .claude\projects ====="
$jfiles2 = Get-ChildItem $proj -Recurse -Filter *.jsonl -File
$tot = ($jfiles2 | Measure-Object Length -Sum).Sum
"files={0}  total={1:N1} GB   over 50MB: {2}   over 200MB: {3}   largest={4:N0} MB" -f $jfiles2.Count, ($tot / 1GB), @($jfiles2 | Where-Object { $_.Length -gt 50MB }).Count, @($jfiles2 | Where-Object { $_.Length -gt 200MB }).Count, (($jfiles2 | Measure-Object Length -Maximum).Maximum / 1MB)
$grew = foreach ($f in $jfiles2) { $d = $f.Length - [long]$j0[$f.FullName]; if ($d -ne 0) { [pscustomobject]@{ MB = $f.Length / 1MB; DeltaKB = $d / 1KB; Name = $f.Name } } }
"files that changed size during the window: {0}   total growth: {1:N0} KB ({2:N1} KB/s)" -f @($grew).Count, (($grew | Measure-Object DeltaKB -Sum).Sum), ((($grew | Measure-Object DeltaKB -Sum).Sum) / $secs)
$grew | Sort-Object DeltaKB -Descending | Select-Object -First 8 | ForEach-Object { "  size={0,7:N1} MB  grew={1,8:N1} KB  {2}" -f $_.MB, $_.DeltaKB, $_.Name }
