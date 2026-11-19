"""probe_point_account.py -- read-only. Account for every point of the CPU headline.

Headline (Task Manager) = processor utility. This prints, for one window:
  headline points = busy time + scaling uplift
  busy time       = size buckets of live processes + exited processes
                    + interrupt/DPC + unexplained
and the same busy time split by application family (parent-chain walk).
Reuses the snapshot functions of probe_reconcile_ntquery.py (same folder).
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_reconcile_ntquery import snapshot_cpus, snapshot_processes  # noqa: E402

pdh = ctypes.WinDLL("pdh")


class PDH_FMT_COUNTERVALUE(ctypes.Structure):
    _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]


pdh.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(wintypes.HANDLE)]
pdh.PdhAddEnglishCounterW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(wintypes.HANDLE)]
pdh.PdhCollectQueryData.argtypes = [wintypes.HANDLE]
pdh.PdhGetFormattedCounterValue.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(PDH_FMT_COUNTERVALUE)]

LAUNCHERS = {"explorer.exe", "services.exe", "svchost.exe", "wininit.exe", "winlogon.exe", "system",
             "smss.exe", "csrss.exe", "userinit.exe", "sihost.exe", "runtimebroker.exe", "?"}
NAMED = (("claude", "Claude Code (+children)"), ("csb", "csb (+children)"), ("codex", "codex (+children)"),
         ("code.exe", "VS Code (+children)"), ("windowsterminal", "Windows Terminal (+children)"),
         ("dopus", "Directory Opus (+children)"))


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    ncpu = os.cpu_count()
    q = wintypes.HANDLE()
    pdh.PdhOpenQueryW(None, 0, ctypes.byref(q))
    hu = wintypes.HANDLE(); ht = wintypes.HANDLE()
    pdh.PdhAddEnglishCounterW(q, r"\Processor Information(_Total)\% Processor Utility", 0, ctypes.byref(hu))
    pdh.PdhAddEnglishCounterW(q, r"\Processor Information(_Total)\% Processor Time", 0, ctypes.byref(ht))
    pdh.PdhCollectQueryData(q)

    c0 = snapshot_cpus(ncpu)
    t0, first = snapshot_processes()
    first_seen = dict(first); last_seen = dict(first)
    while True:
        time.sleep(0.1)
        t1, cur = snapshot_processes()
        for k, v in cur.items():
            if k not in first_seen:
                first_seen[k] = dict(v, user=0, kernel=0)
            last_seen[k] = v
        if t1 - t0 >= seconds:
            break
    c1 = snapshot_cpus(ncpu)
    pdh.PdhCollectQueryData(q)
    vu = PDH_FMT_COUNTERVALUE(); vt = PDH_FMT_COUNTERVALUE()
    pdh.PdhGetFormattedCounterValue(hu, 0x200, None, ctypes.byref(vu))
    pdh.PdhGetFormattedCounterValue(ht, 0x200, None, ctypes.byref(vt))
    utility = vu.doubleValue

    dt = t1 - t0
    cap = dt * ncpu * 1e7
    pct = lambda x: 100.0 * x / cap
    busy = pct((c1["kernel"] - c0["kernel"]) + (c1["user"] - c0["user"]) - (c1["idle"] - c0["idle"]))
    intr = pct(c1["intr"] - c0["intr"]); dpc = pct(c1["dpc"] - c0["dpc"])

    rows = []
    for k, v1 in last_seen.items():
        if v1["pid"] == 0:
            continue
        v0 = first_seen[k]
        rows.append(dict(v1, cpu=pct((v1["user"] - v0["user"]) + (v1["kernel"] - v0["kernel"])), gone=k not in cur))
    live = [r for r in rows if not r["gone"]]
    gone = [r for r in rows if r["gone"]]
    psum = sum(r["cpu"] for r in rows)
    unexplained = busy - psum - intr - dpc

    print("window %.1fs, %d logical CPUs, %d processes seen (%d exited during the window)" % (dt, ncpu, len(rows), len(gone)))
    print()
    print("HEADLINE (what Task Manager shows)       %6.2f points   [PDH time counter cross-check: %.2f]" % (utility, vt.doubleValue))
    print("  = busy time                            %6.2f" % busy)
    print("  + speed scaling uplift                 %6.2f   (cores ran above nominal speed; ratio %.2f)" % (utility - busy, utility / busy if busy else 0))
    print()
    print("BUSY TIME %.2f, point by point" % busy)
    buckets = [("processes using >= 5.0 each", 5.0, 1e9), ("processes using 1.0 - 5.0 each", 1.0, 5.0),
               ("processes using 0.1 - 1.0 each", 0.1, 1.0), ("processes using < 0.1 each (but > 0)", 1e-9, 0.1)]
    for label, lo, hi in buckets:
        b = [r for r in live if lo <= r["cpu"] < hi]
        print("  %-38s %6.2f   from %4d processes" % (label, sum(r["cpu"] for r in b), len(b)))
    print("  %-38s %6.2f   from %4d processes (never in an end-of-window list)" % ("processes that exited", sum(r["cpu"] for r in gone), len(gone)))
    print("  %-38s %6.2f" % ("hardware interrupts", intr))
    print("  %-38s %6.2f" % ("deferred procedure calls (drivers)", dpc))
    print("  %-38s %6.2f" % ("UNEXPLAINED", unexplained))
    print("  %-38s %6.2f" % ("total", psum + intr + dpc + unexplained))
    idle_live = len([r for r in live if r["cpu"] <= 0])
    print("  (%d live processes used no CPU at all in the window)" % idle_live)

    # family attribution
    by_pid = {}
    for r in rows:
        by_pid.setdefault(r["pid"], r)

    def family(r):
        c = r; depth = 0; top = r
        while depth < 30:
            n = c["name"].lower()
            for key, label in NAMED:
                if n.startswith(key):
                    return label
            p = by_pid.get(c["ppid"])
            if p is None or p is c or p["name"].lower() in LAUNCHERS:
                break
            top = p; c = p; depth += 1
        return top["name"] + (" (+children)" if top is not r else "")

    fam = {}
    for r in rows:
        f = fam.setdefault(family(r), [0.0, 0, 0.0])
        f[0] += r["cpu"]; f[1] += 1; f[2] = max(f[2], r["cpu"])
    print()
    print("SAME BUSY TIME BY APPLICATION FAMILY (top 12)")
    print("  %-36s %7s %6s %14s" % ("family", "points", "procs", "largest member"))
    for name, (c, n, mx) in sorted(fam.items(), key=lambda kv: -kv[1][0])[:12]:
        print("  %-36s %7.2f %6d %14.2f" % (name[:36], c, n, mx))
    print()
    print("TOP 8 SINGLE PROCESSES")
    for r in sorted(rows, key=lambda r: -r["cpu"])[:8]:
        print("  %7d %-34s %6.2f  family: %s%s" % (r["pid"], r["name"][:34], r["cpu"], family(r)[:30], "  (exited)" if r["gone"] else ""))


if __name__ == "__main__":
    main()
