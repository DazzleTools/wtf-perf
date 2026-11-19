"""cpu - account for every point of the CPU headline.

Samples every process (and every process that starts and exits) for a few
seconds, reads the system counters over the same window, and prints where
each point of Task Manager's figure went: a verdict, the point-by-point
ledger, the application families, short-lived process churn and file
operations. Read-only; needs no elevation.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
from typing import List, Optional


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wtf-perf cpu",
        description="Account for every point of the CPU headline: processes, short-lived processes, "
                    "interrupts and speed scaling.")
    p.add_argument("-s", "--seconds", type=float, default=10.0, help="sampling window in seconds (default 10)")
    p.add_argument("--interval", type=int, default=100, metavar="MS",
                   help="poll gap in milliseconds (default 100; shorter catches shorter-lived processes, costs more)")
    p.add_argument("--top", type=int, default=12, help="rows per table (default 12)")
    out = p.add_argument_group("output")
    out.add_argument("--json", dest="json_output", action="store_true", help="print the report as JSON")
    out.add_argument("-t", "--tier", default="0,1,2", help="tiers to show: 0, 1, 2, comma-separated, or 'all'")
    out.add_argument("-np", "--no-page", action="store_true", help="do not pause between tiers")
    return p


def _parse_tiers(spec: str) -> List[int]:
    if spec.strip().lower() == "all":
        return [0, 1, 2]
    tiers = sorted({int(x) for x in spec.split(",") if x.strip()})
    if not tiers or any(t not in (0, 1, 2) for t in tiers):
        raise ValueError("tiers must be 0, 1 and/or 2")
    return tiers


def _is_elevated() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def collect(seconds: float, interval_ms: int, top: int, source=None, counter_backend=None) -> dict:
    """Sample, reconcile and judge. Returns the full report dict."""
    from wtf_perf.lib.counters import CounterWindow
    from wtf_perf.lib.findings import find, verdict
    from wtf_perf.lib.ledger import build_ledger
    from wtf_perf.lib.sampler import sample

    window = CounterWindow(backend=counter_backend)
    window.start()
    result = sample(seconds, interval_ms / 1000.0, source=source)
    counters = window.finish()
    report = build_ledger(result, counters, top=top)
    report["findings"] = find(report)
    report["verdict"] = verdict(report, report["findings"])
    report["system"] = {"logical_cpus": os.cpu_count(), "elevated": _is_elevated(), "platform": sys.platform}
    return report


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        tiers = _parse_tiers(args.tier)
    except ValueError as exc:
        print(f"wtf-perf cpu: {exc}", file=sys.stderr)
        return 2
    if args.seconds <= 0 or args.interval <= 0:
        print("wtf-perf cpu: --seconds and --interval must be positive", file=sys.stderr)
        return 2
    if sys.platform != "win32":
        print("wtf-perf cpu: Windows only", file=sys.stderr)
        return 2

    if args.json_output:
        report = collect(args.seconds, args.interval, args.top)
        print(json.dumps(report, indent=2, default=str))
        return 0

    from rich.console import Console

    from wtf_perf.lib.render import render_report

    console = Console()
    with console.status(f"Sampling every process for {args.seconds:g} s...", spinner="dots"):
        report = collect(args.seconds, args.interval, args.top)
    render_report(report, tiers, page=not args.no_page, top=args.top, console=console)
    return 0


if __name__ == "__main__":
    sys.exit(main())
