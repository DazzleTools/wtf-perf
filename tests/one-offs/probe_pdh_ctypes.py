"""probe_pdh_ctypes.py -- read-only. Can system-wide counters (processor utility,
processor performance, disk transfers) be read through pdh.dll with ctypes,
with no WMI and no PowerShell? Prediction: yes, and utility/time ~= performance/100.
"""
import ctypes
import time
from ctypes import wintypes

pdh = ctypes.WinDLL("pdh")
PDH_FMT_DOUBLE = 0x00000200


class PDH_FMT_COUNTERVALUE(ctypes.Structure):
    _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]


pdh.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(wintypes.HANDLE)]
pdh.PdhAddEnglishCounterW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(wintypes.HANDLE)]
pdh.PdhCollectQueryData.argtypes = [wintypes.HANDLE]
pdh.PdhGetFormattedCounterValue.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(PDH_FMT_COUNTERVALUE)]
pdh.PdhCloseQuery.argtypes = [wintypes.HANDLE]

paths = [
    r"\Processor Information(_Total)\% Processor Time",
    r"\Processor Information(_Total)\% Processor Utility",
    r"\Processor Information(_Total)\% Processor Performance",
    r"\Processor Information(_Total)\% Privileged Utility",
    r"\PhysicalDisk(_Total)\Disk Transfers/sec",
    r"\System\Context Switches/sec",
    r"\Memory\Page Faults/sec",
]
q = wintypes.HANDLE()
st = pdh.PdhOpenQueryW(None, 0, ctypes.byref(q))
print("PdhOpenQueryW status 0x%08X" % (st & 0xFFFFFFFF))
counters = []
for p in paths:
    h = wintypes.HANDLE()
    st = pdh.PdhAddEnglishCounterW(q, p, 0, ctypes.byref(h))
    counters.append((p, h, st))
t0 = time.perf_counter()
pdh.PdhCollectQueryData(q)
time.sleep(3)
pdh.PdhCollectQueryData(q)
vals = {}
for p, h, st in counters:
    v = PDH_FMT_COUNTERVALUE()
    s2 = pdh.PdhGetFormattedCounterValue(h, PDH_FMT_DOUBLE, None, ctypes.byref(v))
    vals[p] = v.doubleValue
    print("%-62s add=0x%08X get=0x%08X  %12.2f" % (p, st & 0xFFFFFFFF, s2 & 0xFFFFFFFF, v.doubleValue))
pdh.PdhCloseQuery(q)
t = vals[paths[0]]; u = vals[paths[1]]; perf = vals[paths[2]]
if t:
    print("utility/time = %.3f   performance/100 = %.3f" % (u / t, perf / 100))
