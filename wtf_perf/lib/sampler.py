"""Sample every process's CPU time and I/O counts -- the platform-free part.

A ``SnapshotSource`` returns every process at a single instant (kernel, user
and cycle time, parent, create time, handle count, I/O operation counts) and
the per-processor idle, kernel, user, DPC and interrupt times. Polling it
every ~100 ms and keeping every process ever seen lets a window account for
processes that are born and exit inside it -- the ones no end-of-window
process list can show. The sources themselves live in ``wtf_perf.platforms``
(Windows: ``NtQuerySystemInformation`` classes 5 and 8).

Processes are keyed on (process id, create time), so a reused process id is
two records, never one.

Times are in 100 ns units, as the Windows kernel reports them; a source on
another platform converts to them.
"""
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol, Tuple

Key = Tuple[int, int]  # (pid, create time)


@dataclass(frozen=True)
class ProcRecord:
    """One process as one snapshot saw it. Times in 100 ns units."""

    pid: int
    ppid: int
    create: int
    name: str
    threads: int = 0
    handles: int = 0
    session: int = 0
    cycle: int = 0
    user: int = 0
    kernel: int = 0
    rd: int = 0
    wr: int = 0
    ot: int = 0
    rdb: int = 0
    wrb: int = 0
    otb: int = 0

    @property
    def key(self) -> Key:
        return (self.pid, self.create)


@dataclass(frozen=True)
class CpuTotals:
    """Per-processor times summed over every processor the call returned.

    ``kernel`` includes idle, DPC and interrupt time, as the kernel reports it.
    """

    idle: int = 0
    kernel: int = 0
    user: int = 0
    dpc: int = 0
    intr: int = 0
    icount: int = 0
    ncpu: int = 0


class SnapshotSource(Protocol):
    """What a platform's process snapshot must supply.

    Contract: ``processes()`` returns (a monotonic time in seconds, every
    process keyed by (pid, create time)), times in 100 ns units; pid 0 is the
    idle row (the ledger reads it as idle time, ``ledger.py``), so a source
    whose platform has no such process must not report one under pid 0.
    ``cpus()`` returns per-processor totals summed, with ``ncpu`` set.
    """

    def processes(self) -> Tuple[float, Dict[Key, ProcRecord]]: ...

    def cpus(self) -> CpuTotals: ...



@dataclass(frozen=True)
class ProcDelta:
    """What one process did during the window. Times in 100 ns units."""

    record: ProcRecord        # the last reading of the process
    cpu: int                  # kernel + user time used inside the window
    kernel: int
    cycles: int
    rd: int
    wr: int
    ot: int
    rdb: int
    wrb: int
    born: bool                # first seen after the window opened
    exited: bool              # not present when the window closed


@dataclass
class SampleResult:
    seconds: float
    polls: int
    interval: float
    cpu_before: CpuTotals
    cpu_after: CpuTotals
    deltas: List[ProcDelta] = field(default_factory=list)
    self_pid: Optional[int] = None

    @property
    def capacity(self) -> float:
        """CPU time available in the window, 100 ns units."""
        return self.seconds * max(self.cpu_after.ncpu, 1) * 1e7

    @property
    def self_cpu(self) -> int:
        """CPU time this process used inside the window (the tool's own cost)."""
        return sum(d.cpu for d in self.deltas if d.record.pid == self.self_pid and not d.born)


_ZERO_COUNTERS = dict(user=0, kernel=0, cycle=0, rd=0, wr=0, ot=0, rdb=0, wrb=0)


def sample(seconds: float, interval: float = 0.1, *, source: SnapshotSource,
           sleep: Callable[[float], None] = time.sleep, self_pid: Optional[int] = None,
           max_polls: Optional[int] = None) -> SampleResult:
    """Poll ``source`` for ``seconds`` and return every process's deltas.

    ``source`` is required: the caller picks the platform's source, so no
    call can reach a real sampler by omission.

    A process first seen after the window opened counts all of its time (it
    was born inside the window). A process missing at the end is marked
    exited; its last reading is what it used. The loop is bounded by
    ``max_polls`` (default: ten times the polls the window should need, plus
    100) so a stalled clock cannot make it run forever.
    """
    if seconds <= 0 or interval <= 0:
        raise ValueError("seconds and interval must be positive")
    src = source
    if self_pid is None:
        self_pid = os.getpid()
    cap = max_polls if max_polls is not None else int(math.ceil(seconds / interval)) * 10 + 100

    c0 = src.cpus()
    t0, current = src.processes()
    first: Dict[Key, ProcRecord] = dict(current)
    born_keys = set()
    last: Dict[Key, ProcRecord] = dict(current)
    t = t0
    polls = 0
    while polls < cap:
        sleep(interval)
        t, current = src.processes()
        polls += 1
        for k, rec in current.items():
            if k not in first:
                first[k] = rec
                born_keys.add(k)
            last[k] = rec
        if t - t0 >= seconds:
            break
    c1 = src.cpus()

    deltas: List[ProcDelta] = []
    for k, rec in last.items():
        born = k in born_keys
        base = _ZERO_COUNTERS if born else first[k].__dict__
        deltas.append(ProcDelta(
            record=rec,
            cpu=(rec.user - base["user"]) + (rec.kernel - base["kernel"]),
            kernel=rec.kernel - base["kernel"],
            cycles=rec.cycle - base["cycle"],
            rd=rec.rd - base["rd"], wr=rec.wr - base["wr"], ot=rec.ot - base["ot"],
            rdb=rec.rdb - base["rdb"], wrb=rec.wrb - base["wrb"],
            born=born, exited=k not in current,
        ))
    return SampleResult(seconds=t - t0, polls=polls, interval=interval, cpu_before=c0, cpu_after=c1,
                        deltas=deltas, self_pid=self_pid)
