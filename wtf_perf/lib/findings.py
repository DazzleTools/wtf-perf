"""Findings and the verdict, from a ledger (see ``ledger.build_ledger``).

Every threshold below was set from one machine on one afternoon
(PLZWORK, 2026-11-18). They live in one table so they can be tuned, and each
finding prints the evidence it fired on.

The verdict answers the maintainer's question directly: does the headline add
up, and if it does, is it one consumer or many small ones?
"""
from __future__ import annotations

from collections import Counter
from typing import List

THRESHOLDS = {
    "headline_ratio": 1.15,          # utility / busy at or above this: headline inflated by core speed
    "many_small_busy": 20.0,         # busy at or above this ...
    "many_small_share": 0.2,         # ... and the largest process under this share of busy
    "hidden_family_ratio": 3.0,      # family total at least this many times its largest member
    "hidden_family_points": 2.0,     # ... and at least this many points
    "churn_per_sec": 2.0,            # births per second at or above this ...
    "churn_points": 1.0,             # ... and short-lived CPU at or above this
    "kernel_heavy_points": 2.0,      # a process at or above this ...
    "kernel_heavy_share": 0.6,       # ... with more than this share in kernel mode
    "interrupt_points": 5.0,         # interrupts + DPCs at or above this
    "metadata_ops_per_sec": 10000.0,  # "other" file operations at or above this ...
    "metadata_disk_idle": 80.0,      # ... while the disk is more idle than this
    "idle_hoard_count": 20,          # this many processes of one image using no CPU
    "unexplained_points": 3.0,       # remainder at or above this: a warning finding
    "unexplained_share": 0.10,       # ... and at least this share of busy: the verdict says it does not add up
    "single_hog_share": 0.5,         # one process at or above this share of busy
    "capacity_low": 98.0,            # sampler self-check: per-CPU time must cover ~100% of the wall clock
    "capacity_high": 102.0,
}


def _f(id_, severity, points, summary, evidence):
    return {"id": id_, "severity": severity, "points": points, "summary": summary, "evidence": evidence}


def find(ledger: dict, t: dict = THRESHOLDS) -> List[dict]:
    """Return findings, most consequential first."""
    out: List[dict] = []
    rec, head, win = ledger["reconciliation"], ledger["headline"], ledger["window"]
    busy = rec["busy"]
    procs, fams = ledger["processes"], ledger["families"]
    top_proc = procs[0] if procs else None

    cap = win.get("capacity_check_pct")
    if cap is not None and not (t["capacity_low"] <= cap <= t["capacity_high"]):
        out.append(_f("sampler_unreliable", "warning", 0.0,
                      "Processor totals do not cover the wall clock; process figures may be unreliable.",
                      [f"per-CPU time covered {cap:.1f}% of the window (expected 98-102%)"]))

    if rec["unexplained"] >= t["unexplained_points"]:
        out.append(_f("unexplained_time", "warning", rec["unexplained"],
                      f"{rec['unexplained']:.1f} points of busy time are not attributed to any process.",
                      ["likely processes shorter than the poll interval, or a hypervisor/driver taking time"]))

    if top_proc and busy > 0 and top_proc["points"] >= t["single_hog_share"] * busy:
        out.append(_f("single_hog", "notable", top_proc["points"],
                      f"{top_proc['name']} alone uses {top_proc['points']:.1f} of {busy:.1f} busy points.",
                      [f"pid {top_proc['pid']}, family {top_proc['family']}"]))
    elif top_proc and busy >= t["many_small_busy"] and top_proc["points"] < t["many_small_share"] * busy:
        counted = sum(b["processes"] for b in rec["buckets"])
        out.append(_f("many_small_consumers", "notable", busy,
                      f"No process stands out: the largest uses {top_proc['points']:.1f} points while "
                      f"{counted} processes share {busy:.1f}.",
                      [f"{b['processes']} processes using {b['label']}: {b['points']:.1f} points" for b in rec["buckets"]]))

    for rank, fam in enumerate(fams[:3]):
        if fam["points"] >= t["hidden_family_points"] and fam["largest"] > 0 \
                and fam["points"] >= t["hidden_family_ratio"] * fam["largest"]:
            out.append(_f("hidden_family", "notable", fam["points"],
                          f"{fam['family']} uses {fam['points']:.1f} points across {fam['processes']} processes; "
                          f"its largest single process uses {fam['largest']:.1f}.",
                          [f"rank {rank + 1} family; {fam['born']} of its processes started during the window"]))

    ch = ledger["churn"]
    if ch["per_sec"] >= t["churn_per_sec"] and ch["points"] >= t["churn_points"]:
        top_imgs = ", ".join(f"{r['image']} x{r['count']}" for r in ch["by_image"][:4])
        top_fams = ", ".join(f"{r['family']} x{r['count']}" for r in ch["by_family"][:3])
        out.append(_f("process_churn", "notable", ch["points"],
                      f"{ch['born_and_exited']} processes started and exited during the window "
                      f"({ch['per_sec']:.1f}/s), using {ch['points']:.1f} points no process list shows.",
                      [f"by image: {top_imgs}", f"started by: {top_fams}"]))

    if head.get("ratio") is not None and head["ratio"] >= t["headline_ratio"]:
        out.append(_f("headline_inflated", "notable", head["uplift"],
                      f"Task Manager's figure ({head['utility']:.1f}) reads {head['ratio']:.2f}x the busy time "
                      f"({busy:.1f}) because busy cores ran above nominal speed.",
                      ["processor utility scales busy time by core frequency; it is not extra work"]))

    irq = rec["interrupts"] + rec["dpcs"]
    if irq >= t["interrupt_points"]:
        out.append(_f("interrupt_load", "warning", irq,
                      f"Hardware interrupts and DPCs use {irq:.1f} points -- usually a driver.",
                      [f"interrupts {rec['interrupts']:.1f}, DPCs {rec['dpcs']:.1f}"]))

    for p in procs:
        if p["points"] >= t["kernel_heavy_points"] and p["points"] > 0 \
                and p["kernel_points"] / p["points"] > t["kernel_heavy_share"]:
            out.append(_f("kernel_heavy", "notable", p["points"],
                          f"{p['name']} spends {100 * p['kernel_points'] / p['points']:.0f}% of its "
                          f"{p['points']:.1f} points in kernel mode.",
                          [f"{p['ops_per_sec']:,.0f} file operations/s"]))

    other = ledger["io"]["other_ops_per_sec"]
    disk_idle = (ledger.get("counters") or {}).get("disk_idle")
    if other >= t["metadata_ops_per_sec"] and disk_idle is not None and disk_idle > t["metadata_disk_idle"]:
        heavy = sorted(procs, key=lambda p: -p["other_ops_per_sec"])[:3]
        out.append(_f("metadata_storm", "notable", 0.0,
                      f"{other:,.0f} file-system calls per second (listings, metadata) while the disk is "
                      f"{disk_idle:.0f}% idle: the load is CPU and kernel time, not disk.",
                      [f"{p['name']}: {p['other_ops_per_sec']:,.0f}/s" for p in heavy]))

    idle_counts = Counter()
    for img in ledger["images"]:
        if img["idle_processes"] >= t["idle_hoard_count"]:
            idle_counts[img["image"]] = img["idle_processes"]
    for image, n in idle_counts.most_common():
        out.append(_f("idle_processes", "info", 0.0,
                      f"{n} {image} processes used no CPU during the window.",
                      ["informational: some tools keep processes open on purpose"]))

    order = {"warning": 0, "notable": 1, "info": 2}
    out.sort(key=lambda f: (order[f["severity"]], -f["points"]))
    return out


def verdict(ledger: dict, findings: List[dict], t: dict = THRESHOLDS) -> dict:
    """Does the headline add up, and to what?"""
    rec, head = ledger["reconciliation"], ledger["headline"]
    busy = rec["busy"]
    fams = ledger["families"]
    details = []
    if head.get("utility") is not None:
        details.append(f"headline {head['utility']:.1f} = busy {busy:.1f} + speed-scaling uplift {head['uplift']:.1f}")
    details.append(
        "busy {:.1f} = live processes {:.1f} + exited processes {:.1f} + interrupts/DPCs {:.1f} + unexplained {:.1f}".format(
            busy, sum(b["points"] for b in rec["buckets"]), rec["exited_processes"],
            rec["interrupts"] + rec["dpcs"], rec["unexplained"]))
    ids = {f["id"] for f in findings}
    if rec["unexplained"] >= t["unexplained_points"] and busy > 0 \
            and rec["unexplained"] >= t["unexplained_share"] * busy:
        return {"type": "DOES_NOT_ADD_UP",
                "summary": f"Does not add up: {rec['unexplained']:.1f} points of busy time are unattributed.",
                "details": details}
    if "single_hog" in ids:
        hog = next(f for f in findings if f["id"] == "single_hog")
        return {"type": "DOMINATED", "summary": "Adds up: dominated by one process. " + hog["summary"],
                "details": details}
    leads = "; ".join(f"{f['family']} {f['points']:.1f} points across {f['processes']} "
                      f"process{'es' if f['processes'] != 1 else ''}" for f in fams[:2])
    lead_text = f" Largest: {leads}." if leads else ""
    if "many_small_consumers" in ids:
        return {"type": "MANY_SMALL", "summary": "Adds up: many small consumers, no single culprit." + lead_text,
                "details": details}
    return {"type": "ADDS_UP", "summary": "Adds up." + lead_text, "details": details}
