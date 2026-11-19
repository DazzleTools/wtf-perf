"""System-wide counters through PDH (pdh.dll), with no WMI and no PowerShell.

The process table (``sampler``) gives time per process. Some numbers only
exist system-wide: processor *utility* -- the figure Task Manager's headline
shows, which scales busy time by how fast the busy cores ran and cannot be
derived from the process table (measured 2026-11-18: utility/time 1.46 while
performance/100 read 1.11) -- plus context switches, page faults, interrupts
and disk activity.

Usage: open a window before sampling processes and close it after, so the
rates cover the same seconds::

    w = CounterWindow()
    w.start()
    ...sample processes...
    values = w.finish()      # {"utility": 37.8, "disk_idle": 92.5, ...}

A counter that cannot be added or read is reported as ``None`` -- never an
exception -- so a machine missing one counter still gets every other number.

Moved from ``tests/one-offs/probe_pdh_ctypes.py``.
"""
from __future__ import annotations

from typing import Dict, Optional, Protocol

# English counter paths (PdhAddEnglishCounterW), so they work on any locale.
COUNTERS: Dict[str, str] = {
    "utility": r"\Processor Information(_Total)\% Processor Utility",
    "processor_time": r"\Processor Information(_Total)\% Processor Time",
    "performance": r"\Processor Information(_Total)\% Processor Performance",
    "interrupts_per_sec": r"\Processor Information(_Total)\Interrupts/sec",
    "context_switches_per_sec": r"\System\Context Switches/sec",
    "page_faults_per_sec": r"\Memory\Page Faults/sec",
    "disk_transfers_per_sec": r"\PhysicalDisk(_Total)\Disk Transfers/sec",
    "disk_idle": r"\PhysicalDisk(_Total)\% Idle Time",
}


class PdhBackend(Protocol):
    """The four PDH operations the window needs. Handles are opaque."""

    def add(self, path: str) -> Optional[object]: ...

    def collect(self) -> bool: ...

    def value(self, handle: object) -> Optional[float]: ...

    def close(self) -> None: ...


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


class CounterWindow:
    """Rates and percentages averaged between ``start()`` and ``finish()``."""

    def __init__(self, backend: Optional[PdhBackend] = None, counters: Optional[Dict[str, str]] = None):
        self._backend = backend
        self._counters = dict(counters if counters is not None else COUNTERS)
        self._handles: Dict[str, Optional[object]] = {}
        self._started = False

    def start(self) -> None:
        if self._backend is None:
            try:
                self._backend = CtypesPdh()
            except (OSError, AttributeError):    # AttributeError: no ctypes.WinDLL off Windows
                self._backend = None
        if self._backend is not None:
            for name, path in self._counters.items():
                self._handles[name] = self._backend.add(path)
            self._started = self._backend.collect()

    def finish(self) -> Dict[str, Optional[float]]:
        """Second collection; every counter's value, ``None`` where unavailable."""
        values: Dict[str, Optional[float]] = {name: None for name in self._counters}
        if self._backend is None or not self._started:
            return values
        try:
            if self._backend.collect():
                for name, handle in self._handles.items():
                    if handle is not None:
                        values[name] = self._backend.value(handle)
        finally:
            self._backend.close()
        return values
