"""Roll processes up into application families.

A family is a root application plus everything it spawned. Task Manager
ranks processes one by one, so an application that runs as two hundred
small processes -- each under one percent -- never ranks, though together
it may be the largest consumer on the machine. Families make that visible.

The rule: from each process, walk up the parent chain and stop when the
next parent is

- a launcher (the shell, a terminal, a service host: it starts many
  unrelated applications, so it is never anyone's family),
- missing (it already exited), or
- younger than the child (its process id was reused by a later process,
  so it is not the real parent).

The family is the highest ancestor reached. Its label is that process's
image name without ``.exe`` and without a trailing build version, so
``claude-dcc-2.1.323+dcc0.2.9.exe`` and ``claude-dcc-2.1.327+dcc0.2.11.exe``
are one family, and a few well-known names get a friendlier alias.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from .sampler import Key, ProcRecord

# Processes that start many unrelated applications. Lower case, with .exe.
LAUNCHERS = frozenset({
    "explorer.exe", "services.exe", "svchost.exe", "wininit.exe", "winlogon.exe", "smss.exe",
    "csrss.exe", "userinit.exe", "sihost.exe", "runtimebroker.exe", "taskhostw.exe",
    "cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe", "openconsole.exe", "conhost.exe",
    "system", "system idle process",
})

# Families whose image names vary (versioned builds, helper executables).
# Prefix of the normalised label -> display name.
ALIASES = (
    ("claude", "Claude Code"),
    ("code", "VS Code"),
    ("dopus", "Directory Opus"),
)

_VERSION_SUFFIX = re.compile(r"[-_ ]v?\d+(\.\d+)+.*$")

MAX_DEPTH = 64


def family_label(image_name: str) -> str:
    """``claude-dcc-2.1.323+dcc0.2.9.exe`` -> ``Claude Code``; ``steam.exe`` -> ``steam``."""
    name = image_name[:-4] if image_name.lower().endswith(".exe") else image_name
    name = _VERSION_SUFFIX.sub("", name)
    low = name.lower()
    for prefix, display in ALIASES:
        if low == prefix or low.startswith(prefix + "-") or low.startswith(prefix + "_"):
            return display
    return name


def assign_families(records: Iterable[ProcRecord]) -> Dict[Key, str]:
    """Map every record's key to its family label."""
    recs: List[ProcRecord] = list(records)
    by_pid: Dict[int, List[ProcRecord]] = defaultdict(list)
    for r in recs:
        by_pid[r.pid].append(r)

    def parent_of(child: ProcRecord) -> Optional[ProcRecord]:
        if child.ppid == child.pid:
            return None
        # The real parent existed when the child was created: started no later.
        older = [p for p in by_pid.get(child.ppid, ()) if p.create <= child.create]
        return max(older, key=lambda p: p.create) if older else None

    out: Dict[Key, str] = {}
    for r in recs:
        root = r
        seen = {r.key}
        for _ in range(MAX_DEPTH):
            if root.name.lower() in LAUNCHERS:
                break
            p = parent_of(root)
            if p is None or p.key in seen or p.name.lower() in LAUNCHERS:
                break
            seen.add(p.key)
            root = p
        out[r.key] = family_label(root.name)
    return out
