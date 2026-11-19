"""probe_reconcile_ntquery.py -- read-only measurement.

Question: does CPU time reconcile when read without WMI?
  processor busy time (per-CPU kernel+user-idle)  ==?  sum of per-process time
  + interrupt + DPC time, and how much belongs to processes that exited.

Method: NtQuerySystemInformation(SystemProcessInformation=5) gives every
process's kernel/user/cycle time in one call (one instant). Class 8
(SystemProcessorPerformanceInformation) gives per-CPU idle/kernel/user/DPC/
interrupt. Two samples N seconds apart, plus fast polls in between so that
processes that are born and die inside the window are still counted.

Prediction written before running: busy == processes + exited + (interrupt+DPC)
within about 1 percentage point. If it does not close, the remainder is the
finding.
"""
import ctypes
import struct
import sys
import time

ntdll = ctypes.WinDLL("ntdll")
NtQuerySystemInformation = ntdll.NtQuerySystemInformation
NtQuerySystemInformation.argtypes = [ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
NtQuerySystemInformation.restype = ctypes.c_long
STATUS_INFO_LENGTH_MISMATCH = ctypes.c_long(0xC0000004).value

_buf_size = 4 * 1024 * 1024


def snapshot_processes():
    """Return (qpc_time, {pid: dict}) from a single kernel call."""
    global _buf_size
    while True:
        buf = ctypes.create_string_buffer(_buf_size)
        ret = ctypes.c_ulong(0)
        st = NtQuerySystemInformation(5, buf, _buf_size, ctypes.byref(ret))
        t = time.perf_counter()
        if st == STATUS_INFO_LENGTH_MISMATCH:
            _buf_size = max(_buf_size * 2, ret.value + 65536)
            continue
        if st != 0:
            raise OSError("NtQuerySystemInformation(5) failed: 0x%08X" % (st & 0xFFFFFFFF))
        break
    base = ctypes.addressof(buf)
    procs = {}
    off = 0
    while True:
        nxt, nthreads = struct.unpack_from("<II", buf, off)
        cycle, create, user, kernel = struct.unpack_from("<QqQQ", buf, off + 24)
        name_len, = struct.unpack_from("<H", buf, off + 56)
        name_ptr, = struct.unpack_from("<Q", buf, off + 64)
        pid, ppid = struct.unpack_from("<QQ", buf, off + 80)
        rd, wr, ot, rdb, wrb, otb = struct.unpack_from("<6Q", buf, off + 208)
        if name_ptr and name_len:
            name = ctypes.wstring_at(name_ptr, name_len // 2)
        else:
            name = "System Idle Process" if pid == 0 else "?"
        # key on (pid, create time) so PID reuse cannot merge two processes
        procs[(pid, create)] = dict(pid=pid, ppid=ppid, name=name, threads=nthreads, cycle=cycle,
                                    user=user, kernel=kernel, rd=rd, wr=wr, ot=ot, rdb=rdb, wrb=wrb)
        if nxt == 0:
            break
        off += nxt
    return t, procs


def snapshot_cpus(ncpu):
    size = 48 * ncpu
    buf = ctypes.create_string_buffer(size)
    ret = ctypes.c_ulong(0)
    st = NtQuerySystemInformation(8, buf, size, ctypes.byref(ret))
    if st != 0:
        raise OSError("NtQuerySystemInformation(8) failed: 0x%08X" % (st & 0xFFFFFFFF))
    tot = dict(idle=0, kernel=0, user=0, dpc=0, intr=0, icount=0)
    for i in range(ret.value // 48):
        idle, kernel, user, dpc, intr, icount = struct.unpack_from("<5qI", buf, i * 48)
        tot["idle"] += idle; tot["kernel"] += kernel; tot["user"] += user
        tot["dpc"] += dpc; tot["intr"] += intr; tot["icount"] += icount
    return tot


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    poll = float(sys.argv[2]) if len(sys.argv) > 2 else 0.1
    import os
    ncpu = os.cpu_count()

    c0 = snapshot_cpus(ncpu)
    t0, first = snapshot_processes()
    last_seen = dict(first)       # most recent reading of every process ever seen
    first_seen = dict(first)      # first reading of every process ever seen
    polls = 0
    cost0 = time.process_time()
    while True:
        time.sleep(poll)
        t1, cur = snapshot_processes()
        polls += 1
        for k, v in cur.items():
            if k not in first_seen:
                # born in window: its time before first sight is all inside the window
                first_seen[k] = dict(v, user=0, kernel=0, cycle=0, rd=0, wr=0, ot=0, rdb=0, wrb=0)
            last_seen[k] = v
        if t1 - t0 >= seconds:
            break
    c1 = snapshot_cpus(ncpu)
    self_cost = time.process_time() - cost0
    dt = t1 - t0
    cap = dt * ncpu * 1e7  # 100ns units of CPU time available

    idle = c1["idle"] - c0["idle"]
    kern = c1["kernel"] - c0["kernel"]   # includes idle, dpc, interrupt
    user = c1["user"] - c0["user"]
    dpc = c1["dpc"] - c0["dpc"]
    intr = c1["intr"] - c0["intr"]
    total = kern + user
    busy = total - idle

    def pct(x):
        return 100.0 * x / cap

    rows = []
    for k, v1 in last_seen.items():
        v0 = first_seen[k]
        d = (v1["user"] - v0["user"]) + (v1["kernel"] - v0["kernel"])
        rows.append(dict(v1, d=d, dk=v1["kernel"] - v0["kernel"], dcyc=v1["cycle"] - v0["cycle"],
                         born=k not in first, gone=k not in cur,
                         ops=(v1["rd"] - v0["rd"]) + (v1["wr"] - v0["wr"]) + (v1["ot"] - v0["ot"])))
    idle_rows = [r for r in rows if r["pid"] == 0]
    live = [r for r in rows if r["pid"] != 0]
    proc_sum = sum(r["d"] for r in live)
    born = [r for r in live if r["born"]]
    gone = [r for r in live if r["gone"]]
    shortlived = [r for r in live if r["born"] and r["gone"]]

    print("window %.2fs  cpus=%d  polls=%d (every %.0f ms)  probe's own CPU: %.2f%% of machine"
          % (dt, ncpu, polls, poll * 1000, 100 * self_cost / (dt * ncpu)))
    print("clock check: per-CPU kernel+user accounts for %.2f%% of wall capacity" % pct(total))
    print()
    print("PROCESSOR VIEW")
    print("  busy (kernel+user-idle)      %6.2f %%" % pct(busy))
    print("  idle                         %6.2f %%" % pct(idle))
    print("  of busy: interrupt           %6.2f %%" % pct(intr))
    print("  of busy: DPC                 %6.2f %%" % pct(dpc))
    print("  interrupts/sec               %8.0f" % ((c1["icount"] - c0["icount"]) / dt))
    print()
    print("PROCESS VIEW (one kernel call per sample, no WMI)")
    print("  processes seen               %6d   born in window %d, exited in window %d, both %d"
          % (len(live), len(born), len(gone), len(shortlived)))
    print("  sum of all non-idle procs    %6.2f %%" % pct(proc_sum))
    print("    of which exited by the end %6.2f %%   <- invisible to an end-of-window process list"
          % pct(sum(r["d"] for r in gone)))
    print("    of which born AND exited   %6.2f %%" % pct(sum(r["d"] for r in shortlived)))
    print("  Idle process entry (pid 0)   %6.2f %%" % pct(sum(r["d"] for r in idle_rows)))
    print()
    print("RECONCILIATION")
    print("  busy - processes                         %6.2f %%" % pct(busy - proc_sum))
    print("  busy - processes - interrupt - DPC       %6.2f %%" % pct(busy - proc_sum - intr - dpc))
    cyc_live = sum(r["dcyc"] for r in live)
    cyc_idle = sum(r["dcyc"] for r in idle_rows)
    if cyc_live + cyc_idle:
        print("  cycle-based busy (non-idle cycles/all)   %6.2f %%" % (100.0 * cyc_live / (cyc_live + cyc_idle)))
    print()
    print("TOP 12 BY CPU")
    for r in sorted(live, key=lambda r: -r["d"])[:12]:
        flag = ("born " if r["born"] else "") + ("gone" if r["gone"] else "")
        print("  %7d %-36s %6.2f %%  kernel %5.2f %%  ops/s %7.0f  %s"
              % (r["pid"], r["name"][:36], pct(r["d"]), pct(r["dk"]), r["ops"] / dt, flag))
    print()
    print("SHORT-LIVED (born and exited inside window) BY IMAGE")
    agg = {}
    for r in shortlived:
        a = agg.setdefault(r["name"], [0, 0])
        a[0] += 1; a[1] += r["d"]
    for name, (n, d) in sorted(agg.items(), key=lambda kv: -kv[1][1])[:10]:
        print("  %-30s count %4d   cpu %5.2f %%" % (name[:30], n, pct(d)))


if __name__ == "__main__":
    main()
