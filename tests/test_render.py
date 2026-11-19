"""Tests for `wtf-perf cpu` output: the rendered tiers and the --json shape.

Driven by scripted samples and a fake counter backend -- nothing samples
the machine.
"""
import io
import json

from rich.console import Console

from wtf_perf.lib.render import render_report
from wtf_perf.lib.sampler import CpuTotals, ProcRecord
from wtf_perf.tools.core.cpu.cpu import collect, main

JSON_KEYS = {"system", "window", "headline", "reconciliation", "families", "images", "processes",
             "churn", "io", "counters", "findings", "verdict"}


class _Source:
    """Two snapshots 2 s apart on 4 CPUs: one busy process, one that comes and goes."""

    def __init__(self):
        self.calls = 0

    def processes(self):
        self.calls += 1
        a = ProcRecord(pid=10, ppid=0, create=1, name="busy.exe", user=0, kernel=0)
        if self.calls == 1:
            return 0.0, {a.key: a}
        a2 = ProcRecord(pid=10, ppid=0, create=1, name="busy.exe", user=2 * 10**7, kernel=10**7)
        b = ProcRecord(pid=11, ppid=10, create=5, name="hook.exe", user=10**6)
        snap = {a2.key: a2} if self.calls > 2 else {a2.key: a2, b.key: b}
        return float(self.calls - 1), snap

    def cpus(self):
        if self.calls == 0:
            return CpuTotals(ncpu=4)
        total = 2 * 4 * 10**7
        return CpuTotals(idle=total - 3_200_000 - 3 * 10**7, kernel=total // 2, user=total - total // 2, ncpu=4)


class _Pdh:
    def add(self, path):
        return path

    def collect(self):
        return True

    def value(self, handle):
        return 45.0 if "Utility" in handle else 30.0

    def close(self):
        pass


def _report():
    # 1 ms poll gap: the scripted source supplies its own 1 s timestamps.
    return collect(2, 1, 12, source=_Source(), counter_backend=_Pdh())


def test_the_report_has_every_documented_key_and_serialises():
    report = _report()
    assert JSON_KEYS <= set(report)
    data = json.loads(json.dumps(report, default=str))
    assert data["headline"]["utility"] == 45.0
    assert data["churn"]["born_and_exited"] == 1


def test_tier0_shows_the_verdict_and_every_ledger_line():
    console = Console(file=io.StringIO(), width=140, record=True)
    render_report(_report(), [0], page=False, console=console)
    text = console.export_text()
    for needle in ("VERDICT", "Headline (what Task Manager shows)", "speed-scaling uplift",
                   "processes that exited during the window", "unexplained"):
        assert needle in text, needle


def test_main_rejects_a_bad_tier_without_sampling(capsys):
    assert main(["--tier", "7"]) == 2
    assert "tiers" in capsys.readouterr().err
