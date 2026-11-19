"""Tests for wtf_perf.lib.sampler.

Parsing is tested against buffers packed here in the kernel's layout; the
polling loop is driven by scripted snapshot sources, so no test samples the
machine except the one bounded, read-only live check at the end.
"""
import os
import struct
import sys

import pytest

from wtf_perf.lib.sampler import CpuTotals, ProcRecord, sample
from wtf_perf.platforms.windows import IDLE_PROCESS_NAME, parse_cpu_buffer, parse_process_buffer

BASE = 0x1000_0000  # pretend address the buffer lived at


def _pack_processes(entries):
    """Pack SYSTEM_PROCESS_INFORMATION entries (x64 layout), names after them.

    Each entry: dict with pid, ppid, create, name (None for no name), and
    optional threads, handles, session, cycle, user, kernel, rd, wr, ot, rdb, wrb, otb.
    """
    n = len(entries)
    names_at = 256 * n
    buf = bytearray(names_at)
    name_blob = bytearray()
    for i, e in enumerate(entries):
        off = 256 * i
        nxt = 256 if i < n - 1 else 0
        struct.pack_into("<II", buf, off, nxt, e.get("threads", 1))
        struct.pack_into("<QqQQ", buf, off + 24, e.get("cycle", 0), e["create"], e.get("user", 0), e.get("kernel", 0))
        if e["name"] is None:
            struct.pack_into("<HHIQ", buf, off + 56, 0, 0, 0, 0)
        else:
            raw = e["name"].encode("utf-16-le")
            ptr = BASE + names_at + len(name_blob)
            struct.pack_into("<HHIQ", buf, off + 56, len(raw), len(raw) + 2, 0, ptr)
            name_blob += raw + b"\0\0"
        struct.pack_into("<QQ", buf, off + 80, e["pid"], e["ppid"])
        struct.pack_into("<II", buf, off + 96, e.get("handles", 0), e.get("session", 0))
        struct.pack_into("<6Q", buf, off + 208, e.get("rd", 0), e.get("wr", 0), e.get("ot", 0),
                         e.get("rdb", 0), e.get("wrb", 0), e.get("otb", 0))
    return bytes(buf + name_blob)


def test_parse_reads_every_field_of_every_entry():
    data = _pack_processes([
        dict(pid=0, ppid=0, create=0, name=None, kernel=999),
        dict(pid=4242, ppid=1000, create=1234567, name="claude.exe", threads=7, handles=321, session=1,
             cycle=55, user=10, kernel=20, rd=1, wr=2, ot=3, rdb=4, wrb=5, otb=6),
    ])
    procs = parse_process_buffer(data, BASE)
    assert set(procs) == {(0, 0), (4242, 1234567)}
    idle = procs[(0, 0)]
    assert idle.name == IDLE_PROCESS_NAME and idle.kernel == 999
    p = procs[(4242, 1234567)]
    assert (p.name, p.ppid, p.threads, p.handles, p.session) == ("claude.exe", 1000, 7, 321, 1)
    assert (p.cycle, p.user, p.kernel) == (55, 10, 20)
    assert (p.rd, p.wr, p.ot, p.rdb, p.wrb, p.otb) == (1, 2, 3, 4, 5, 6)


def test_parse_marks_a_name_pointing_outside_the_buffer_as_unknown():
    data = bytearray(_pack_processes([dict(pid=8, ppid=4, create=1, name="x.exe")]))
    struct.pack_into("<Q", data, 64, BASE + 10_000_000)
    assert parse_process_buffer(bytes(data), BASE)[(8, 1)].name == "?"


def test_parse_reads_an_entry_that_ends_exactly_at_the_buffer_end():
    """A buffer holding one unnamed entry is exactly one entry long."""
    data = _pack_processes([dict(pid=0, ppid=0, create=0, name=None, kernel=7)])
    assert len(data) == 256
    assert parse_process_buffer(data, BASE)[(0, 0)].kernel == 7


def test_parse_reads_a_name_that_ends_exactly_at_the_buffer_end():
    """The last name need not be followed by a terminator to be read."""
    data = _pack_processes([dict(pid=9, ppid=4, create=3, name="tail.exe")])
    assert data.endswith(b"\0\0")
    assert parse_process_buffer(data[:-2], BASE)[(9, 3)].name == "tail.exe"


def test_parse_treats_a_name_pointer_with_zero_length_as_unknown():
    data = bytearray(_pack_processes([dict(pid=8, ppid=4, create=1, name="x.exe")]))
    struct.pack_into("<H", data, 56, 0)
    assert parse_process_buffer(bytes(data), BASE)[(8, 1)].name == "?"


def test_parse_cpu_buffer_sums_every_processor():
    data = b"".join(struct.pack("<5qI4x", 100, 300, 50, 2, 3, 9) for _ in range(4))
    t = parse_cpu_buffer(data)
    assert (t.idle, t.kernel, t.user, t.dpc, t.intr, t.icount, t.ncpu) == (400, 1200, 200, 8, 12, 36, 4)


class ScriptedSource:
    """Returns pre-written snapshots, one per processes() call, 1 s apart."""

    def __init__(self, snapshots, cpus=(CpuTotals(ncpu=2), CpuTotals(ncpu=2))):
        self._snaps = list(snapshots)
        self._i = 0
        self._cpus = list(cpus)
        self.process_calls = 0

    def processes(self):
        self.process_calls += 1
        snap = self._snaps[min(self._i, len(self._snaps) - 1)]
        t = float(self._i)
        self._i += 1
        return t, {r.key: r for r in snap}

    def cpus(self):
        return self._cpus.pop(0) if len(self._cpus) > 1 else self._cpus[0]


def _rec(pid, create, name, user=0, kernel=0, ppid=1, **io):
    return ProcRecord(pid=pid, ppid=ppid, create=create, name=name, user=user, kernel=kernel, **io)


def _by_pid(result):
    return {(d.record.pid, d.record.create): d for d in result.deltas}


def _no_sleep(_):
    pass


def test_a_process_born_and_exited_inside_the_window_counts_all_its_time():
    src = ScriptedSource([
        [_rec(10, 1, "long.exe", user=100, kernel=50)],
        [_rec(10, 1, "long.exe", user=150, kernel=60), _rec(20, 7, "hook.exe", user=30, kernel=12)],
        [_rec(10, 1, "long.exe", user=200, kernel=70)],
    ])
    r = sample(2, interval=1, source=src, sleep=_no_sleep, self_pid=-1)
    d = _by_pid(r)
    assert d[(10, 1)].cpu == 120 and not d[(10, 1)].born and not d[(10, 1)].exited
    hook = d[(20, 7)]
    assert hook.born and hook.exited
    assert hook.cpu == 42 and hook.kernel == 12


def test_a_reused_process_id_is_two_records():
    src = ScriptedSource([
        [_rec(100, 1, "old.exe", user=5)],
        [_rec(100, 2, "new.exe", user=3)],
    ])
    r = sample(1, interval=1, source=src, sleep=_no_sleep, self_pid=-1)
    d = _by_pid(r)
    assert set(d) == {(100, 1), (100, 2)}
    assert d[(100, 1)].exited and d[(100, 1)].cpu == 0
    assert d[(100, 2)].born and d[(100, 2)].cpu == 3


def test_io_counts_and_cycles_are_deltas_over_the_window():
    src = ScriptedSource([
        [_rec(5, 1, "io.exe", rd=10, wr=4, ot=1000, rdb=100, wrb=40, cycle=5_000)],
        [_rec(5, 1, "io.exe", rd=15, wr=6, ot=1600, rdb=150, wrb=90, cycle=7_500)],
    ])
    d = _by_pid(sample(1, interval=1, source=src, sleep=_no_sleep, self_pid=-1))[(5, 1)]
    assert (d.rd, d.wr, d.ot, d.rdb, d.wrb) == (5, 2, 600, 50, 50)
    assert d.cycles == 2_500


def test_the_tools_own_cost_is_reported():
    src = ScriptedSource([
        [_rec(77, 1, "python.exe", user=10), _rec(5, 1, "other.exe", user=10)],
        [_rec(77, 1, "python.exe", user=25), _rec(5, 1, "other.exe", user=90)],
    ])
    assert sample(1, interval=1, source=src, sleep=_no_sleep, self_pid=77).self_cpu == 15


def test_window_length_and_capacity_come_from_the_snapshots():
    src = ScriptedSource([[_rec(1, 1, "a")]] * 4, cpus=(CpuTotals(ncpu=16), CpuTotals(ncpu=16)))
    r = sample(3, interval=1, source=src, sleep=_no_sleep, self_pid=-1)
    assert r.seconds == 3.0 and r.polls == 3
    assert r.capacity == 3 * 16 * 1e7


def test_a_stalled_clock_cannot_make_the_loop_run_forever():
    class Stalled(ScriptedSource):
        def processes(self):
            self.process_calls += 1
            return 0.0, {}

    src = Stalled([[]])
    r = sample(1, interval=0.1, source=src, sleep=_no_sleep, self_pid=-1, max_polls=25)
    assert r.polls == 25 and src.process_calls == 26


def test_rejects_a_non_positive_window():
    with pytest.raises(ValueError):
        sample(0, source=ScriptedSource([[]]), sleep=_no_sleep)


@pytest.mark.skipif(sys.platform != "win32", reason="reads the Windows kernel process table")
def test_live_snapshot_sees_this_process_and_every_processor():
    """Read-only, one call each: this process is in the table under its own
    name, and the processor totals cover every logical processor."""
    from wtf_perf.platforms.windows import NtSource

    src = NtSource()
    _, procs = src.processes()
    mine = [r for r in procs.values() if r.pid == os.getpid()]
    assert len(mine) == 1 and mine[0].name.lower().startswith("python")
    assert src.cpus().ncpu == os.cpu_count()
