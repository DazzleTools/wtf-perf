"""A platform is a named set of providers, keyed by kind.

Kinds today: ``snapshot`` (the process and processor snapshot, required),
``counters`` (system-wide counters, optional), ``command_line`` (a live
process's command line, for ``--ai-detail full``) and ``elevation``. A future
deep source -- the kernel's process-exit events, a heap view, a sensor -- is
another kind: present, it adds to the report; absent, the report says so.

Each provider knows whether it can run here and says why not, so a platform
that is not implemented and a platform that is implemented but not for this
host refuse the same way: one line, before anything is sampled.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable, List, Mapping, Optional, Tuple

KINDS = ("snapshot", "counters", "command_line", "elevation")
REQUIRED = ("snapshot",)


class PlatformNotImplemented(RuntimeError):
    """A required provider is missing or cannot run on this host."""

    def __init__(self, platform: str, missing: List[Tuple[str, str]]):
        self.platform = platform
        self.missing = missing
        parts = "; ".join(f"{kind}: {why}" for kind, why in missing)
        super().__init__(f"the {platform} providers cannot run here ({parts})")


@dataclass(frozen=True)
class Provider:
    """One kind of data for one platform.

    ``factory()`` returns the thing itself: a snapshot source, a counter
    backend (or None), a command-line reader function, an elevation bool.
    ``factory=None`` marks a stub. ``host`` is the ``sys.platform`` prefix the
    provider needs (None: any host).
    """

    kind: str
    factory: Optional[Callable[[], object]] = None
    note: str = ""
    host: Optional[str] = None

    def available(self) -> Tuple[bool, str]:
        if self.factory is None:
            return False, self.note or "not implemented"
        if self.host and not sys.platform.startswith(self.host):
            return False, f"needs a {self.host} host (this is {sys.platform})"
        return True, self.note


@dataclass(frozen=True)
class Platform:
    name: str
    providers: Mapping[str, Provider] = field(default_factory=dict)

    def provider(self, kind: str) -> Provider:
        return self.providers.get(kind) or Provider(kind, None, "not implemented")

    def unavailable(self, kinds=REQUIRED) -> List[Tuple[str, str]]:
        out = []
        for kind in kinds:
            ok, why = self.provider(kind).available()
            if not ok:
                out.append((kind, why))
        return out

    def _make(self, kind: str):
        p = self.provider(kind)
        ok, _ = p.available()
        return p.factory() if ok else None

    def snapshot_source(self):
        missing = self.unavailable(("snapshot",))
        if missing:
            raise PlatformNotImplemented(self.name, missing)
        return self.provider("snapshot").factory()

    def counter_backend(self):
        """The counter backend, or None (every counter then reads missing)."""
        return self._make("counters")

    def command_line_reader(self) -> Callable[[int], Optional[str]]:
        reader = self._make("command_line")
        return reader if reader is not None else (lambda pid: None)

    def is_elevated(self) -> bool:
        return bool(self._make("elevation"))


def stub(name: str, notes: Mapping[str, str]) -> Platform:
    """A platform whose every provider is a named, not-implemented stub."""
    return Platform(name, {kind: Provider(kind, None, f"not implemented ({notes.get(kind, 'no source chosen yet')})")
                           for kind in KINDS})
