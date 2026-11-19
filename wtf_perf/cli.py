"""wtf-perf CLI entry point (`wtf-perf`).

Built on dazzlecmd-lib's AggregatorEngine. Tools are dispatched from
``kits/core.kit.json`` -> ``tools/core/<tool>/.wtf-perf.json`` -> the Python
entry point named in each manifest's ``runtime``.

The first tool is ``cpu``: it accounts for every point of the CPU headline
(live processes, processes that exited, interrupts, speed scaling). Further
drill-downs attach as additional tools without changing this wiring.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from dazzlecmd_lib import AggregatorEngine
from dazzlecmd_lib.default_meta_commands import build_list_entries

from ._version import __app_name__, __version__, get_display_version

DESCRIPTION = "Why is my Windows PC busy? Accounts for every point of CPU (wtf-windows family)."

# Concrete "getting started" examples for the `wtf-perf -h` epilog.
_HELP_EXAMPLES = [
    ("wtf-perf cpu", "sample for a few seconds and account for the CPU headline"),
    ("wtf-perf list", "list the available tools"),
]


def _build_epilog(projects, engine) -> str:
    """Custom `wtf-perf -h` epilog: the tool inventory + getting-started examples.

    dazzlecmd-lib's default top-level help only shows program-level flags; end
    users expect the subcommand list and a couple of concrete examples. Tool
    rows come from ``build_list_entries`` so alias/kit behavior flows through
    automatically as wtf-perf grows.
    """
    width = shutil.get_terminal_size((80, 24)).columns
    out = []

    entries = build_list_entries(projects, engine, show_mode="default", kit_filter=None)
    if entries:
        label_w = max(len(e["name"]) for e in entries)
        avail = max(20, width - label_w - 4)
        out.append("")
        out.append("tools:")
        for e in entries:
            desc = e["description"]
            if len(desc) > avail:
                desc = desc[: avail - 3] + "..."
            out.append(f"  {e['name']:<{label_w}}  {desc}")

    ex_w = max(len(label) for label, _ in _HELP_EXAMPLES)
    out.append("")
    out.append("getting started:")
    for label, desc in _HELP_EXAMPLES:
        out.append(f"  {label:<{ex_w}}  {desc}")

    out.append("")
    out.append("run 'wtf-perf <tool> -h' for a tool's flags, or 'wtf-perf info <tool>' for details.")
    return "\n".join(out)


def build_engine() -> AggregatorEngine:
    """Build the aggregator. The root comes from this file's location, never the
    working directory, so the command works from anywhere and under the
    wtf-windows pass-through (which runs it with a different cwd)."""
    package_root = Path(__file__).resolve().parent

    engine = AggregatorEngine(
        name=__app_name__,
        command="wtf-perf",
        tools_dir="tools",
        kits_dir="kits",
        manifest=".wtf-perf.json",
        version_info=(get_display_version(), __version__),
        description=DESCRIPTION,
        project_root=str(package_root),
    )
    # Closure passes engine into the epilog so build_list_entries gets full
    # kit context (the lib's epilog_builder signature is one-arg).
    engine.epilog_builder = lambda projects: _build_epilog(projects, engine)
    return engine


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    return build_engine().run(argv)


if __name__ == "__main__":
    sys.exit(main())
