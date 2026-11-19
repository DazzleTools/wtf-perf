"""Linux providers -- stubs. Each names the source a port would read."""
from __future__ import annotations

from .base import stub

LINUX = stub("linux", {
    "snapshot": "/proc/<pid>/stat for utime, stime, start time and ppid; /proc/<pid>/io for I/O "
                "operations (root for other users); /proc/stat for per-CPU user/system/idle/irq/softirq",
    "counters": "/proc/stat irq and softirq, /proc/vmstat page faults; no utility counter",
    "command_line": "/proc/<pid>/cmdline",
    "elevation": "os.geteuid() == 0",
})
