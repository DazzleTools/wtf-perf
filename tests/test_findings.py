"""Tests for the ledger and the verdict -- the answer to "does the headline add up?"."""
import pytest

from wtf_perf.lib.findings import find, verdict
from wtf_perf.lib.ledger import build_ledger
from wtf_perf.lib.sampler import CpuTotals, ProcDelta, ProcRecord, SampleResult

PT = 10**7          # one point when the window is 10 s on 10 CPUs (capacity 1e9)


def _d(pid, name, points, ppid=1, create=None, kernel_share=0.0, born=False, exited=False, ot=0):
    rec = ProcRecord(pid=pid, ppid=ppid, create=create if create is not None else pid, name=name)
    cpu = int(points * PT)
    return ProcDelta(record=rec, cpu=cpu, kernel=int(cpu * kernel_share), cycles=cpu, rd=0, wr=0, ot=ot,
                     rdb=0, wrb=0, born=born, exited=exited)


def _sample(deltas, busy, intr=0.0, dpc=0.0):
    total = 10 * 10 * 10**7
    idle = int(total - busy * PT)
    after = CpuTotals(idle=idle, kernel=int(total * 0.6), user=total - int(total * 0.6),
                      intr=int(intr * PT), dpc=int(dpc * PT), ncpu=10)
    return SampleResult(seconds=10.0, polls=100, interval=0.1, cpu_before=CpuTotals(ncpu=10),
                        cpu_after=after, deltas=deltas, self_pid=-1)


def _many_small_machine():
    """The 2026-11-18 shape: a Claude Code family of many small processes plus
    hook churn, no process above 1.5 points."""
    d = [_d(1, "WindowsTerminal.exe", 0.5), _d(2, "pwsh.exe", 0.2, ppid=1)]
    pid = 10
    for i in range(8):                        # eight Claude Code sessions, ~1.2 each
        d.append(_d(pid, f"claude-dcc-2.1.32{i}.exe", 1.2, ppid=2)); pid += 1
    for i in range(40):                       # short-lived hook plumbing under a session
        d.append(_d(pid, "bash.exe", 0.05, ppid=10, create=1000 + i, born=True, exited=True)); pid += 1
    for i in range(60):                       # unrelated small background processes
        d.append(_d(pid, f"svc{i}.exe", 0.15, ppid=0)); pid += 1
    d.append(_d(pid, "dopus.exe", 1.4, ppid=0))
    return d


def test_the_ledger_accounts_for_every_point():
    deltas = _many_small_machine()
    explained = sum(x.cpu for x in deltas) / PT
    led = build_ledger(_sample(deltas, busy=explained + 1.0 + 0.5, intr=0.8, dpc=0.2), {"utility": 26.0})
    rec, head = led["reconciliation"], led["headline"]
    parts = sum(b["points"] for b in rec["buckets"]) + rec["exited_processes"] + rec["interrupts"] + rec["dpcs"] + rec["unexplained"]
    assert parts == pytest.approx(rec["busy"], abs=0.01)
    assert rec["unexplained"] == pytest.approx(0.5, abs=0.01)
    assert rec["exited_processes"] == pytest.approx(2.0, abs=0.01)
    assert head["utility"] == pytest.approx(head["busy"] + head["uplift"], abs=0.01)


def test_many_small_consumers_adds_up_and_names_the_family():
    deltas = _many_small_machine()
    busy = sum(x.cpu for x in deltas) / PT + 0.5
    led = build_ledger(_sample(deltas, busy=busy, intr=0.4), {"utility": busy * 1.38})
    fs = find(led)
    ids = {f["id"] for f in fs}
    v = verdict(led, fs)
    assert v["type"] == "MANY_SMALL"
    assert "Claude Code" in v["summary"]
    assert {"many_small_consumers", "hidden_family", "process_churn", "headline_inflated"} <= ids
    assert led["families"][0]["family"] == "Claude Code"


def test_one_process_at_most_of_the_load_is_dominated_not_many_small():
    deltas = [_d(1, "render.exe", 30.0, ppid=0)] + [_d(10 + i, f"s{i}.exe", 0.2, ppid=0) for i in range(30)]
    led = build_ledger(_sample(deltas, busy=36.5))
    fs = find(led)
    assert verdict(led, fs)["type"] == "DOMINATED"
    assert "many_small_consumers" not in {f["id"] for f in fs}


def test_a_large_remainder_does_not_add_up():
    deltas = [_d(10 + i, f"s{i}.exe", 0.5, ppid=0) for i in range(30)]
    led = build_ledger(_sample(deltas, busy=15.0 + 6.0))
    assert verdict(led, find(led))["type"] == "DOES_NOT_ADD_UP"


def test_idle_processes_are_informational_and_never_the_verdict():
    deltas = [_d(10 + i, "csb.exe", 0.0, ppid=0) for i in range(56)] + [_d(100, "work.exe", 3.0, ppid=0)]
    led = build_ledger(_sample(deltas, busy=3.0))
    fs = find(led)
    idle = [f for f in fs if f["id"] == "idle_processes"]
    assert idle and idle[0]["severity"] == "info" and "56 csb.exe" in idle[0]["summary"]
    assert verdict(led, fs)["type"] != "IDLE"
