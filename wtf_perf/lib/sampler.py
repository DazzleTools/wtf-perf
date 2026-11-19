"""Sample every process's CPU time and I/O counts without WMI.

One kernel call (``NtQuerySystemInformation``, class 5) returns every
process at a single instant: its kernel, user and cycle time, parent, create
time, handle count and I/O operation counts. A second class (8) returns the
per-processor idle, kernel, user, DPC and interrupt times. Polling class 5
every ~100 ms and keeping every process ever seen lets a window account for
processes that are born and exit inside it -- the ones no end-of-window
process list can show.

Processes are keyed on (process id, create time), so a reused process id is
two records, never one.

Moved from ``tests/one-offs/probe_reconcile_ntquery.py`` (the probe the design
was measured with); the parsing offsets are unchanged.

Times are in 100 ns units, as the kernel reports them.
"""
from __future__ import annotations

import math
import os
import struct
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol, Tuple

# SYSTEM_PROCESS_INFORMATION (x64) field offsets used here.
_ENTRY_SIZE = 256
_OFF_NEXT = 0           # ULONG NextEntryOffset, ULONG NumberOfThreads
_OFF_TIMES = 24         # ULONGLONG CycleTime, LARGE_INTEGER Create/User/Kernel
_OFF_NAME_LEN = 56      # UNICODE_STRING.Length (bytes)
_OFF_NAME_PTR = 64      # UNICODE_STRING.Buffer
_OFF_PIDS = 80          # UniqueProcessId, InheritedFromUniqueProcessId
_OFF_HANDLES = 96       # ULONG HandleCount, ULONG SessionId
_OFF_IO = 208           # Read/Write/Other operation counts, then transfer counts

# SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION: Idle, Kernel, User, Dpc, Interrupt
# (LARGE_INTEGER each) and ULONG InterruptCount, padded to 48 bytes.
_CPU_ENTRY_SIZE = 48

IDLE_PROCESS_NAME = "System Idle Process"

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


def parse_process_buffer(data: bytes, base: int) -> Dict[Key, ProcRecord]:
    """Parse a class-5 buffer.

    ``base`` is the address the buffer lived at when the kernel filled it: the
    kernel writes each image name inside the same buffer and records its
    absolute address, so ``address - base`` is the name's offset in ``data``.
    """
    procs: Dict[Key, ProcRecord] = {}
    off = 0
    size = len(data)
    while off + _ENTRY_SIZE <= size:
        nxt, nthreads = struct.unpack_from("<II", data, off + _OFF_NEXT)
        cycle, create, user, kernel = struct.unpack_from("<QqQQ", data, off + _OFF_TIMES)
        (name_len,) = struct.unpack_from("<H", data, off + _OFF_NAME_LEN)
        (name_ptr,) = struct.unpack_from("<Q", data, off + _OFF_NAME_PTR)
        pid, ppid = struct.unpack_from("<QQ", data, off + _OFF_PIDS)
        handles, session = struct.unpack_from("<II", data, off + _OFF_HANDLES)
        rd, wr, ot, rdb, wrb, otb = struct.unpack_from("<6Q", data, off + _OFF_IO)
        name = _read_name(data, base, name_ptr, name_len, pid)
        rec = ProcRecord(pid=pid, ppid=ppid, create=create, name=name, threads=nthreads,
                         handles=handles, session=session, cycle=cycle, user=user, kernel=kernel,
                         rd=rd, wr=wr, ot=ot, rdb=rdb, wrb=wrb, otb=otb)
        procs[rec.key] = rec
        if nxt == 0:
            break
        off += nxt
    return procs


def _read_name(data: bytes, base: int, ptr: int, length: int, pid: int) -> str:
    if not ptr or not length:
        return IDLE_PROCESS_NAME if pid == 0 else "?"
    start = ptr - base
    if start < 0 or start + length > len(data):
        return "?"
    return data[start:start + length].decode("utf-16-le", errors="replace")


def parse_cpu_buffer(data: bytes) -> CpuTotals:
    """Sum a class-8 buffer over every processor entry in it."""
    idle = kernel = user = dpc = intr = icount = 0
    n = len(data) // _CPU_ENTRY_SIZE
    for i in range(n):
        i_, k, u, d, r, c = struct.unpack_from("<5qI", data, i * _CPU_ENTRY_SIZE)
        idle += i_; kernel += k; user += u; dpc += d; intr += r; icount += c
    return CpuTotals(idle=idle, kernel=kernel, user=user, dpc=dpc, intr=intr, icount=icount, ncpu=n)


class SnapshotSource(Protocol):
    def processes(self) -> Tuple[float, Dict[Key, ProcRecord]]: ...

    def cpus(self) -> CpuTotals: ...


class NtSource:
    """The real source: two ``NtQuerySystemInformation`` classes through ctypes.

    Reads only. Needs no elevation. Processor counts above 64 (more than one
    processor group) are not handled: class 8 returns the calling thread's
    group only, which ``CpuTotals.ncpu`` makes visible.
    """

    _STATUS_INFO_LENGTH_MISMATCH = 0xC0000004

    def __init__(self, clock: Callable[[], float] = time.perf_counter):
        import ctypes

        self._ctypes = ctypes
        ntdll = ctypes.WinDLL("ntdll")
        self._query = ntdll.NtQuerySystemInformation
        self._query.argtypes = [ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
        self._query.restype = ctypes.c_long
        self._clock = clock
        self._buf_size = 4 * 1024 * 1024
        self._ncpu = os.cpu_count() or 1

    def processes(self) -> Tuple[float, Dict[Key, ProcRecord]]:
        ctypes = self._ctypes
        for _ in range(8):
            buf = ctypes.create_string_buffer(self._buf_size)
            ret = ctypes.c_ulong(0)
            st = self._query(5, buf, self._buf_size, ctypes.byref(ret)) & 0xFFFFFFFF
            t = self._clock()
            if st == self._STATUS_INFO_LENGTH_MISMATCH:
                self._buf_size = max(self._buf_size * 2, ret.value + 65536)
                continue
            if st != 0:
                raise OSError("NtQuerySystemInformation(5) failed: 0x%08X" % st)
            return t, parse_process_buffer(buf.raw, ctypes.addressof(buf))
        raise OSError("NtQuerySystemInformation(5): buffer kept growing")

    def cpus(self) -> CpuTotals:
        ctypes = self._ctypes
        size = _CPU_ENTRY_SIZE * self._ncpu
        buf = ctypes.create_string_buffer(size)
        ret = ctypes.c_ulong(0)
        st = self._query(8, buf, size, ctypes.byref(ret)) & 0xFFFFFFFF
        if st != 0:
            raise OSError("NtQuerySystemInformation(8) failed: 0x%08X" % st)
        return parse_cpu_buffer(buf.raw[: ret.value])


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


def sample(seconds: float, interval: float = 0.1, source: Optional[SnapshotSource] = None,
           sleep: Callable[[float], None] = time.sleep, self_pid: Optional[int] = None,
           max_polls: Optional[int] = None) -> SampleResult:
    """Poll ``source`` for ``seconds`` and return every process's deltas.

    A process first seen after the window opened counts all of its time (it
    was born inside the window). A process missing at the end is marked
    exited; its last reading is what it used. The loop is bounded by
    ``max_polls`` (default: ten times the polls the window should need, plus
    100) so a stalled clock cannot make it run forever.
    """
    if seconds <= 0 or interval <= 0:
        raise ValueError("seconds and interval must be positive")
    src = source if source is not None else NtSource()
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
