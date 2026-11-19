"""The reconciliation ledger: account for every point of the CPU headline.

All CPU figures are *points*: percent of the whole machine over the window,
the unit Task Manager's headline uses. The ledger reads

    headline (processor utility)  = busy time + speed-scaling uplift
    busy time                     = live processes, by size bucket
                                  + processes that exited during the window
                                  + hardware interrupts + DPCs
                                  + unexplained

and the unexplained remainder is printed, never hidden. Families, churn and
file-operation rates are built alongside, in one JSON-ready dict -- the shape
`--json` prints and the AI prompt reads.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from .families import assign_families, family_label
from .sampler import SampleResult

# Live-process size buckets, in points: (label, lower bound inclusive, upper bound exclusive).
BUCKETS = (
    ("5% or more of the machine", 5.0, float("inf")),
    ("1% to 5% of the machine", 1.0, 5.0),
    ("0.1% to 1% of the machine", 0.1, 1.0),
    ("under 0.1% of the machine", 0.0, 0.1),
)


def build_ledger(sample: SampleResult, counters: Optional[Dict[str, Optional[float]]] = None,
                 top: int = 12) -> dict:
    counters = counters or {}
    cap = sample.capacity or 1.0

    def pts(units: float) -> float:
        return 100.0 * units / cap

    c0, c1 = sample.cpu_before, sample.cpu_after
    kernel = c1.kernel - c0.kernel
    user = c1.user - c0.user
    idle = c1.idle - c0.idle
    busy = pts(kernel + user - idle)
    intr = pts(c1.intr - c0.intr)
    dpc = pts(c1.dpc - c0.dpc)
    capacity_check = pts(kernel + user)

    procs = [d for d in sample.deltas if d.record.pid != 0]
    idle_rows = [d for d in sample.deltas if d.record.pid == 0]
    fam_of = assign_families(d.record for d in sample.deltas)

    live = [d for d in procs if not d.exited]
    exited = [d for d in procs if d.exited]
    buckets = []
    for label, lo, hi in BUCKETS:
        rows = [d for d in live if pts(d.cpu) > 0 and lo <= pts(d.cpu) < hi]
        buckets.append({"label": label, "points": sum(pts(d.cpu) for d in rows), "processes": len(rows)})
    exited_points = sum(pts(d.cpu) for d in exited)
    process_points = sum(pts(d.cpu) for d in procs)
    unexplained = busy - process_points - intr - dpc

    cyc_proc = sum(d.cycles for d in procs)
    cyc_idle = sum(d.cycles for d in idle_rows)
    cycle_busy = 100.0 * cyc_proc / (cyc_proc + cyc_idle) if (cyc_proc + cyc_idle) else None

    utility = counters.get("utility")
    headline = {
        "utility": utility,
        "busy": busy,
        "uplift": (utility - busy) if utility is not None else None,
        "ratio": (utility / busy) if utility is not None and busy > 0 else None,
        "processor_time_counter": counters.get("processor_time"),
    }

    secs = sample.seconds or 1.0
    fams: Dict[str, dict] = defaultdict(lambda: {"points": 0.0, "processes": 0, "largest": 0.0, "largest_name": "",
                                               "kernel_points": 0.0, "ops_per_sec": 0.0, "born": 0, "idle_processes": 0})
    images: Dict[str, dict] = defaultdict(lambda: {"points": 0.0, "processes": 0, "idle_processes": 0})
    for d in procs:
        p = pts(d.cpu)
        f = fams[fam_of[d.record.key]]
        f["points"] += p
        f["processes"] += 1
        f["kernel_points"] += pts(d.kernel)
        f["ops_per_sec"] += (d.rd + d.wr + d.ot) / secs
        f["born"] += int(d.born)
        if p > f["largest"]:
            f["largest"], f["largest_name"] = p, d.record.name
        img = images[d.record.name.lower()]
        img["points"] += p
        img["processes"] += 1
        if d.cpu <= 0 and not d.born:
            f["idle_processes"] += 1
            img["idle_processes"] += 1

    families = sorted(({"family": k, **v} for k, v in fams.items()), key=lambda r: -r["points"])
    image_rows = sorted(({"image": k, **v} for k, v in images.items()), key=lambda r: -r["points"])

    def proc_row(d):
        return {"pid": d.record.pid, "name": d.record.name, "family": fam_of[d.record.key],
                "points": pts(d.cpu), "kernel_points": pts(d.kernel),
                "ops_per_sec": (d.rd + d.wr + d.ot) / secs, "other_ops_per_sec": d.ot / secs,
                "born": d.born, "exited": d.exited}

    processes = [proc_row(d) for d in sorted(procs, key=lambda d: -d.cpu)]

    short = [d for d in procs if d.born and d.exited]
    born = [d for d in procs if d.born]
    churn_img: Dict[str, List[float]] = defaultdict(lambda: [0, 0.0])
    churn_fam: Dict[str, List[float]] = defaultdict(lambda: [0, 0.0])
    for d in short:
        churn_img[family_label(d.record.name)][0] += 1
        churn_img[family_label(d.record.name)][1] += pts(d.cpu)
        churn_fam[fam_of[d.record.key]][0] += 1
        churn_fam[fam_of[d.record.key]][1] += pts(d.cpu)

    def churn_rows(m, key):
        return [{key: k, "count": int(v[0]), "points": v[1]} for k, v in sorted(m.items(), key=lambda kv: -kv[1][0])]

    io = {
        "read_ops_per_sec": sum(d.rd for d in procs) / secs,
        "write_ops_per_sec": sum(d.wr for d in procs) / secs,
        "other_ops_per_sec": sum(d.ot for d in procs) / secs,
        "read_mb_per_sec": sum(d.rdb for d in procs) / secs / 1048576,
        "write_mb_per_sec": sum(d.wrb for d in procs) / secs / 1048576,
    }

    return {
        "window": {"seconds": sample.seconds, "polls": sample.polls, "interval": sample.interval,
                   "logical_cpus": c1.ncpu, "self_cost_pct": pts(sample.self_cpu),
                   "capacity_check_pct": capacity_check},
        "headline": headline,
        "reconciliation": {"busy": busy, "buckets": buckets, "exited_processes": exited_points,
                           "exited_count": len(exited), "interrupts": intr, "dpcs": dpc,
                           "unexplained": unexplained, "cycle_busy": cycle_busy,
                           "live_idle_processes": sum(1 for d in live if d.cpu <= 0)},
        "families": families,
        "images": image_rows,
        "processes": processes[:top] if top else processes,
        "churn": {"born": len(born), "born_and_exited": len(short), "per_sec": len(born) / secs,
                  "points": sum(pts(d.cpu) for d in short),
                  "by_image": churn_rows(churn_img, "image"), "by_family": churn_rows(churn_fam, "family")},
        "io": io,
        "counters": counters,
    }
