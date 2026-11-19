"""cpu - account for every point of the CPU headline.

Samples every process (and every process that starts and exits) for a few
seconds, reads the system counters over the same window, and prints where
each point of Task Manager's figure went: a verdict, the point-by-point
ledger, the application families, short-lived process churn and file
operations. Read-only; needs no elevation.
"""
from __future__ import annotations

import argparse
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
    plat = p.add_argument_group("platform")
    plat.add_argument("--platform", choices=("auto", "windows", "linux", "darwin"), default="auto",
                      help="provider set to use (default: auto, the detected platform). Naming another "
                           "platform cannot sample it; it lists or tries that platform's providers")
    plat.add_argument("--providers", action="store_true",
                      help="list each provider of the platform and whether it can run here, then exit")
    out = p.add_argument_group("output")
    out.add_argument("--json", dest="json_output", action="store_true", help="print the report as JSON")
    out.add_argument("-t", "--tier", default="0,1,2", help="tiers to show: 0, 1, 2, comma-separated, or 'all'")
    out.add_argument("-np", "--no-page", action="store_true", help="do not pause between tiers")
    ai = p.add_argument_group("AI summary")
    ai.add_argument("--ai", nargs="?", const="", default=None, metavar="BACKEND",
                    help="add an AI summary (claude, codex, lmstudio, ollama, prompt-only; default: the saved "
                         "backend, else claude)")
    ai.add_argument("--ai-only", action="store_true", help="show only the AI summary (implies --ai)")
    ai.add_argument("--ai-verbose", action="store_true", help="stream the backend's output as it arrives")
    ai.add_argument("--ai-detail", choices=("names", "full"), default=None,
                    help="names (default): process names and figures only; full: also the top processes' "
                         "command lines")
    ai.add_argument("--ai-model", default="", help="model to ask for (required for ollama)")
    ai.add_argument("--ai-save", action="store_true",
                    help="save --ai and --ai-detail as the defaults for later runs")
    return p


def _config():
    from dazzlecmd_lib.config import ConfigManager

    from wtf_perf.paths import settings_dir

    return ConfigManager(config_dir=str(settings_dir()))


def save_ai_settings(updates: dict) -> None:
    cfg = _config()
    current = cfg.get_dict("ai", {}) or {}
    current.update({k: v for k, v in updates.items() if v})
    cfg.write({"ai": current})


def resolve_ai(flag_backend: Optional[str], flag_detail: Optional[str]):
    """Flag over saved setting over default, for the backend and the detail level."""
    from wtf_perf import aiwire

    saved = _config().get_dict("ai", {}) or {}
    backend = flag_backend or saved.get("backend") or aiwire.DEFAULT_BACKEND
    detail = flag_detail or saved.get("detail") or aiwire.DEFAULT_DETAIL
    return backend, detail


def _parse_tiers(spec: str) -> List[int]:
    if spec.strip().lower() == "all":
        return [0, 1, 2]
    tiers = sorted({int(x) for x in spec.split(",") if x.strip()})
    if not tiers or any(t not in (0, 1, 2) for t in tiers):
        raise ValueError("tiers must be 0, 1 and/or 2")
    return tiers


def resolve_platform(name: str):
    from wtf_perf import platforms

    return platforms.load(platforms.detect() if name == "auto" else name)


def print_providers(platform) -> None:
    from wtf_perf.platforms import KINDS, REQUIRED

    print(f"Providers for {platform.name} (this host: {sys.platform})")
    for kind in KINDS:
        ok, why = platform.provider(kind).available()
        need = " (required)" if kind in REQUIRED else ""
        print(f"  {kind:<13} {'available' if ok else 'unavailable':<12} {why}{need}")


def collect(seconds: float, interval_ms: int, top: int, platform) -> dict:
    """Sample, reconcile and judge on ``platform``'s providers. Returns the report dict.

    Tests pass a platform built from stub providers; nothing here picks a real
    source by default.
    """
    from wtf_perf.lib.counters import CounterWindow
    from wtf_perf.lib.findings import find, verdict
    from wtf_perf.lib.ledger import build_ledger
    from wtf_perf.lib.sampler import sample

    source = platform.snapshot_source()
    window = CounterWindow(backend=platform.counter_backend())
    window.start()
    result = sample(seconds, interval_ms / 1000.0, source=source)
    counters = window.finish()
    report = build_ledger(result, counters, top=top)
    report["findings"] = find(report)
    report["verdict"] = verdict(report, report["findings"])
    report["system"] = {"logical_cpus": os.cpu_count(), "elevated": platform.is_elevated(),
                        "platform": sys.platform, "provider_set": platform.name}
    return report


def tolerate_unencodable_output(*streams) -> None:
    """Replace characters the output encoding cannot hold, instead of crashing.

    Redirecting to a file on a console whose code page is not UTF-8 (cp437,
    cp1252) otherwise fails on the first ellipsis or box-drawing character
    with UnicodeEncodeError -- found by the 0.2.0 checklist sweep.
    """
    for stream in streams or (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: Optional[List[str]] = None) -> int:
    tolerate_unencodable_output()
    args = build_parser().parse_args(argv)
    try:
        tiers = _parse_tiers(args.tier)
    except ValueError as exc:
        print(f"wtf-perf cpu: {exc}", file=sys.stderr)
        return 2
    if args.seconds <= 0 or args.interval <= 0:
        print("wtf-perf cpu: --seconds and --interval must be positive", file=sys.stderr)
        return 2
    platform = resolve_platform(args.platform)
    if args.providers:
        print_providers(platform)
        return 0
    missing = platform.unavailable()
    if missing:
        why = "; ".join(f"{kind} {reason}" for kind, reason in missing)
        print(f"wtf-perf cpu: the {platform.name} providers cannot sample here -- {why}. "
              f"See --providers.", file=sys.stderr)
        return 2

    want_ai = args.ai is not None or args.ai_only
    backend, detail = resolve_ai(args.ai or None, args.ai_detail)
    if args.ai_save:
        save_ai_settings({"backend": args.ai or None, "detail": args.ai_detail})

    def sample_and_read():
        report = collect(args.seconds, args.interval, args.top, platform)
        cmdlines = {}
        if want_ai and detail == "full":
            from wtf_perf import aiwire
            cmdlines = aiwire.read_command_lines((p["pid"] for p in report["processes"] if not p["exited"]),
                                                 platform.command_line_reader())
        return report, cmdlines

    def run_ai(report, cmdlines, stream_to=None):
        from wtf_perf import aiwire
        return aiwire.run_ai(report, backend, detail, model=args.ai_model, command_lines=cmdlines,
                             stream_to=stream_to)

    if args.json_output:
        report, cmdlines = sample_and_read()
        if want_ai:
            report["ai_analysis"] = run_ai(report, cmdlines)
        print(json.dumps(report, indent=2, default=str))
        return 0

    from rich.console import Console

    from wtf_perf.lib.render import render_ai, render_report

    console = Console()
    with console.status(f"Sampling every process for {args.seconds:g} s...", spinner="dots"):
        report, cmdlines = sample_and_read()

    def ai_fetcher():
        if args.ai_verbose:
            result = run_ai(report, cmdlines, stream_to=sys.stdout)
        else:
            with console.status(f"Asking {backend} for a summary...", spinner="dots"):
                result = run_ai(report, cmdlines)
        render_ai(console, result)
        return result

    if args.ai_only:
        result = ai_fetcher()
        return 0 if result["success"] or result.get("deferred_to") else 1
    render_report(report, tiers, page=not args.no_page, top=args.top, console=console,
                  ai_fetcher=ai_fetcher if want_ai else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
