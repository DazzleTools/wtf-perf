"""Roll processes up into application families.

A family is a root application plus everything it spawned. Task Manager
ranks processes one by one, so an application that runs as two hundred
small processes -- each under one percent -- never ranks, though together
it may be the largest consumer on the machine. Families make that visible.

The rule: from each process, walk up the parent chain and stop when the
next parent is

- a launcher (Explorer, a service host, the terminal: it starts many
  unrelated applications, so it is never anyone's family),
- missing (it already exited), or
- younger than the child (its process id was reused by a later process,
  so it is not the real parent).

The family is the highest ancestor reached that is not a shell or console
host. Shells are walked *through*, not stopped at: an application that runs
``cmd /c python hook.py`` owns that python, so the hook rolls up to the
application. A shell with nothing but shells and launchers above it (a
``pwsh`` you opened yourself) is its own family. A known application (one
with an alias below) claims everything under it: the walk stops there, so a
session manager that launches Claude Code (csb) does not absorb it. (A first version stopped at
shells; the live run on 2026-11-18 put 319 hook processes in a family called
"python" instead of under Claude Code.) Its label is that process's
image name without ``.exe`` and without a trailing build version, so
``claude-dcc-2.1.323+dcc0.2.9.exe`` and ``claude-dcc-2.1.327+dcc0.2.11.exe``
are one family, and a few well-known names get a friendlier alias.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from .sampler import Key, ProcRecord

# Processes that start many unrelated applications: the walk stops below
# them. Lower case, with .exe.
LAUNCHERS = frozenset({
    "explorer.exe", "services.exe", "svchost.exe", "wininit.exe", "winlogon.exe", "smss.exe",
    "csrss.exe", "userinit.exe", "sihost.exe", "runtimebroker.exe", "taskhostw.exe",
    "windowsterminal.exe", "system", "system idle process",
})

# Shells and console hosts: walked through, never the family while an
# application sits above them.
SHELLS = frozenset({
    "cmd.exe", "powershell.exe", "pwsh.exe", "bash.exe", "sh.exe", "conhost.exe", "openconsole.exe",
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


def is_known_application(image_name: str) -> bool:
    """A name with an alias claims everything it starts: the walk stops there,
    so Claude Code sessions are Claude Code whether a terminal or a session
    manager (csb) launched them."""
    name = image_name[:-4] if image_name.lower().endswith(".exe") else image_name
    return family_label(image_name) != _VERSION_SUFFIX.sub("", name)


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
        cur = r
        best = None if r.name.lower() in SHELLS else r   # highest non-shell ancestor so far
        seen = {r.key}
        for _ in range(MAX_DEPTH):
            if cur.name.lower() in LAUNCHERS or is_known_application(cur.name):
                break
            p = parent_of(cur)
            if p is None or p.key in seen or p.name.lower() in LAUNCHERS:
                break
            seen.add(p.key)
            cur = p
            if p.name.lower() not in SHELLS:
                best = p
        out[r.key] = family_label((best or r).name)
    return out
