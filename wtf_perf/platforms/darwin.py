"""macOS providers -- stubs. Each names the source a port would read."""
from __future__ import annotations

from .base import stub

DARWIN = stub("darwin", {
    "snapshot": "libproc proc_listpids and proc_pidinfo(PROC_PIDTASKINFO); host_processor_info for per-CPU ticks",
    "counters": "host_statistics64; no utility counter",
    "command_line": "sysctl KERN_PROCARGS2",
    "elevation": "os.geteuid() == 0",
})
