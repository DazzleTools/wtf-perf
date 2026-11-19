"""Three-tier rendering for `wtf-perf cpu`, in the wtf family's style.

Tier 0: the verdict, the point-by-point ledger, the findings (and the AI
panel when asked for). Tier 1: families, top processes, churn, file
operations. Tier 2: every counter, the sampler's self-check, all processes.
Between tiers, on a terminal, a keypress continues and q or Esc stops.
"""
from __future__ import annotations

import sys
from typing import Callable, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

VERDICT_STYLES = {
    "DOES_NOT_ADD_UP": "bold red",
    "DOMINATED": "bold yellow",
    "MANY_SMALL": "bold yellow",
    "ADDS_UP": "bold green",
}
SEVERITY_STYLES = {"warning": "bold red", "notable": "yellow", "info": "dim"}


def _num(v, fmt="{:.1f}", none="--"):
    return none if v is None else fmt.format(v)


def render_tier0(console: Console, report: dict, ai_fetcher: Optional[Callable[[], None]] = None) -> None:
    w, h, rec, v = report["window"], report["headline"], report["reconciliation"], report["verdict"]
    console.print(Panel.fit("[bold]WTF-PERF[/bold] -- Where is the CPU going?", style="blue"))
    console.print(f"  Window: {w['seconds']:.1f} s, {w['polls']} samples, {w['logical_cpus']} logical CPUs"
                  f"   wtf-perf's own cost: {w['self_cost_pct']:.2f}%")
    style = VERDICT_STYLES.get(v["type"], "bold")
    lines = [f"[{style}]{v['summary']}[/{style}]"] + [f"  {d}" for d in v["details"]]
    console.print(Panel("\n".join(lines), title="VERDICT", border_style=style.split()[-1]))

    t = Table(title="Where every point of the headline went", show_lines=False)
    t.add_column("Part", style="bold")
    t.add_column("Points", justify="right")
    t.add_column("From", justify="right")
    if h.get("utility") is not None:
        t.add_row("Headline (what Task Manager shows)", _num(h["utility"]), "")
        t.add_row("  speed-scaling uplift (not extra work)", _num(h["uplift"]), f"ratio {_num(h['ratio'], '{:.2f}')}")
    t.add_row("Busy time", _num(rec["busy"]), "")
    for b in rec["buckets"]:
        t.add_row(f"  processes using {b['label']}", _num(b["points"]), f"{b['processes']} processes")
    t.add_row("  processes that exited during the window", _num(rec["exited_processes"]),
              f"{rec['exited_count']} processes")
    t.add_row("  hardware interrupts + DPCs", _num(rec["interrupts"] + rec["dpcs"]), "drivers")
    style_u = "bold red" if rec["unexplained"] >= 3 else ""
    t.add_row(f"[{style_u}]  unexplained[/{style_u}]" if style_u else "  unexplained", _num(rec["unexplained"]), "")
    console.print(t)

    findings = [f for f in report["findings"] if f["severity"] != "info"]
    if findings:
        console.print("[bold]Findings[/bold]")
        for f in findings:
            st = SEVERITY_STYLES[f["severity"]]
            console.print(f"  [{st}]{f['severity'].upper():8s}[/{st}] {f['summary']}")
    if ai_fetcher is not None:
        ai_fetcher()


def render_tier1(console: Console, report: dict, top: int = 12) -> None:
    t = Table(title="Applications (process families)")
    for col, j in (("Family", "left"), ("Points", "right"), ("Processes", "right"), ("Largest one", "right"),
                   ("Kernel", "right"), ("File ops/s", "right"), ("Started in window", "right")):
        t.add_column(col, justify=j)
    for f in report["families"][:top]:
        t.add_row(f["family"], _num(f["points"], "{:.2f}"), str(f["processes"]), _num(f["largest"], "{:.2f}"),
                  _num(f["kernel_points"], "{:.2f}"), f"{f['ops_per_sec']:,.0f}", str(f["born"]))
    console.print(t)

    p = Table(title="Top processes")
    for col, j in (("PID", "right"), ("Name", "left"), ("Family", "left"), ("Points", "right"),
                   ("Kernel", "right"), ("File ops/s", "right"), ("", "left")):
        p.add_column(col, justify=j)
    for r in report["processes"][:top]:
        flag = ("started " if r["born"] else "") + ("exited" if r["exited"] else "")
        p.add_row(str(r["pid"]), r["name"], r["family"], _num(r["points"], "{:.2f}"),
                  _num(r["kernel_points"], "{:.2f}"), f"{r['ops_per_sec']:,.0f}", flag)
    console.print(p)

    ch = report["churn"]
    console.print(f"[bold]Short-lived processes:[/bold] {ch['born_and_exited']} started and exited "
                  f"({ch['per_sec']:.1f}/s), {ch['points']:.2f} points")
    if ch["by_family"]:
        console.print("  started by: " + ", ".join(f"{r['family']} x{r['count']}" for r in ch["by_family"][:5]))
    if ch["by_image"]:
        console.print("  images:     " + ", ".join(f"{r['image']} x{r['count']}" for r in ch["by_image"][:6]))
    io = report["io"]
    console.print(f"[bold]File operations:[/bold] {io['read_ops_per_sec']:,.0f} reads/s, "
                  f"{io['write_ops_per_sec']:,.0f} writes/s, {io['other_ops_per_sec']:,.0f} other/s "
                  f"(listings, metadata); {io['read_mb_per_sec']:.2f} MB/s read, {io['write_mb_per_sec']:.2f} MB/s written")


def render_tier2(console: Console, report: dict) -> None:
    c = Table(title="System counters (averaged over the window)")
    c.add_column("Counter")
    c.add_column("Value", justify="right")
    for k, v in report["counters"].items():
        c.add_row(k, _num(v, "{:,.2f}", "unavailable"))
    console.print(c)
    w, rec = report["window"], report["reconciliation"]
    console.print(f"[bold]Sampler self-check:[/bold] per-CPU time covered {w['capacity_check_pct']:.2f}% of the window "
                  f"(expected 98-102%); cycle-based busy {_num(rec['cycle_busy'], '{:.2f}')}% vs time-based "
                  f"{rec['busy']:.2f}%; {rec['live_idle_processes']} live processes used no CPU")
    info = [f for f in report["findings"] if f["severity"] == "info"]
    for f in info:
        console.print(f"  [dim]INFO[/dim]     {f['summary']}")
    for f in report["findings"]:
        if f["evidence"] and f["severity"] != "info":
            console.print(f"[bold]{f['id']}[/bold]: " + "; ".join(f["evidence"]))


def _wait_for_keypress(console: Console, prompt: str) -> bool:
    """True to continue, False on q/Esc."""
    console.print(f"[dim]{prompt}[/dim]")
    try:
        import msvcrt
        ch = msvcrt.getwch()
    except Exception:
        ch = sys.stdin.read(1) if sys.stdin.isatty() else "\n"
    return ch not in ("q", "Q", "\x1b")


def render_report(report: dict, tiers: List[int], page: bool, top: int = 12,
                  ai_fetcher: Optional[Callable[[], None]] = None, console: Optional[Console] = None) -> None:
    console = console or Console()
    steps = [
        (0, lambda: render_tier0(console, report, ai_fetcher), None),
        (1, lambda: render_tier1(console, report, top), "Press any key for evidence details, q/Esc to quit..."),
        (2, lambda: render_tier2(console, report), "Press any key for full diagnostics, q/Esc to quit..."),
    ]
    selected = [s for s in steps if s[0] in tiers]
    paging = page and console.is_terminal and len(selected) > 1
    for i, (_, fn, prompt) in enumerate(selected):
        if i > 0 and paging and prompt and not _wait_for_keypress(console, prompt):
            return
        fn()
