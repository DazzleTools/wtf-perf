"""Windows providers: the process snapshot, the system counters, command lines, elevation.

Everything Windows-specific in wtf-perf lives here, moved unchanged from
``lib/sampler.py`` (the x64 ``SYSTEM_PROCESS_INFORMATION`` layout, its parsers
and ``NtSource``), ``lib/counters.py`` (``CtypesPdh``) and ``aiwire.py``
(``read_command_line``). Every ``WinDLL`` call sits inside a constructor or a
function, so this module imports on any OS -- which lets the parser tests run
in the Linux CI job.
"""
from __future__ import annotations

import ctypes
import os
import struct
import time
from typing import Callable, Dict, Optional, Tuple

from wtf_perf.lib.sampler import CpuTotals, Key, ProcRecord
from wtf_perf.platforms.base import Platform, Provider

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


class CtypesPdh:
    """The real backend: pdh.dll through ctypes. Reads only."""

    _PDH_FMT_DOUBLE = 0x00000200

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class _Value(ctypes.Structure):
            _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._Value = _Value
        pdh = ctypes.WinDLL("pdh")
        pdh.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(wintypes.HANDLE)]
        pdh.PdhAddEnglishCounterW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, ctypes.c_size_t,
                                              ctypes.POINTER(wintypes.HANDLE)]
        pdh.PdhCollectQueryData.argtypes = [wintypes.HANDLE]
        pdh.PdhGetFormattedCounterValue.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                    ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(_Value)]
        pdh.PdhCloseQuery.argtypes = [wintypes.HANDLE]
        self._pdh = pdh
        self._query = wintypes.HANDLE()
        if pdh.PdhOpenQueryW(None, 0, ctypes.byref(self._query)) != 0:
            raise OSError("PdhOpenQueryW failed")

    def add(self, path: str) -> Optional[object]:
        h = self._wintypes.HANDLE()
        if self._pdh.PdhAddEnglishCounterW(self._query, path, 0, self._ctypes.byref(h)) != 0:
            return None
        return h

    def collect(self) -> bool:
        return self._pdh.PdhCollectQueryData(self._query) == 0

    def value(self, handle: object) -> Optional[float]:
        v = self._Value()
        if self._pdh.PdhGetFormattedCounterValue(handle, self._PDH_FMT_DOUBLE, None, self._ctypes.byref(v)) != 0:
            return None
        return float(v.doubleValue)

    def close(self) -> None:
        self._pdh.PdhCloseQuery(self._query)


# --- command lines for --ai-detail full --------------------------------------

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_PROCESS_COMMAND_LINE_INFORMATION = 60
_STATUS_INFO_LENGTH_MISMATCH = 0xC0000004


def read_command_line(pid: int) -> Optional[str]:
    """The command line of a live process via NtQueryInformationProcess class 60.
    None when the process cannot be opened (another user's or a protected
    process without elevation, or gone)."""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll")
    except (AttributeError, OSError):
        return None
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    ntdll.NtQueryInformationProcess.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
                                                ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
    ntdll.NtQueryInformationProcess.restype = ctypes.c_long
    h = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
    if not h:
        return None
    try:
        size = 4096
        for _ in range(4):
            buf = ctypes.create_string_buffer(size)
            ret = ctypes.c_ulong(0)
            st = ntdll.NtQueryInformationProcess(h, _PROCESS_COMMAND_LINE_INFORMATION, buf, size,
                                                 ctypes.byref(ret)) & 0xFFFFFFFF
            if st == _STATUS_INFO_LENGTH_MISMATCH:
                size = max(size * 2, ret.value + 64)
                continue
            if st != 0:
                return None
            length, = struct.unpack_from("<H", buf.raw, 0)
            ptr, = struct.unpack_from("<Q", buf.raw, 8)
            start = ptr - ctypes.addressof(buf)
            if length == 0 or start < 0 or start + length > size:
                return ""
            return buf.raw[start:start + length].decode("utf-16-le", errors="replace")
        return None
    finally:
        kernel32.CloseHandle(h)


def counter_backend() -> Optional[CtypesPdh]:
    """PDH, or None when it cannot be opened -- every counter is then reported
    missing rather than failing the run (the degrade CounterWindow used to do)."""
    try:
        return CtypesPdh()
    except (OSError, AttributeError):    # AttributeError: no ctypes.WinDLL off Windows
        return None


def is_elevated() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


WINDOWS = Platform("windows", {
    "snapshot": Provider("snapshot", NtSource, host="win32",
                         note="NtQuerySystemInformation classes 5 and 8; no elevation needed"),
    "counters": Provider("counters", counter_backend, host="win32", note="PDH (pdh.dll)"),
    "command_line": Provider("command_line", lambda: read_command_line, host="win32",
                             note="NtQueryInformationProcess class 60; other users' processes need elevation"),
    "elevation": Provider("elevation", is_elevated, host="win32", note="shell32 IsUserAnAdmin"),
})
