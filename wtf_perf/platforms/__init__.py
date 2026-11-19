"""Per-platform providers: pick one by detection, or name one with ``--platform``.

Windows is the detailed one. Linux and macOS are stubs that name what they
would read, so a port fills in a known shape instead of a rewrite. The ledger,
families, findings and rendering never branch on the platform: a provider that
cannot supply something returns nothing, and the report says it is missing.

Naming a platform other than the host's cannot sample that platform -- each
provider checks the host -- so the override is for listing providers and for
future alternative provider sets on one OS.
"""
from __future__ import annotations

import importlib
import sys
from typing import Optional

from .base import KINDS, REQUIRED, Platform, PlatformNotImplemented, Provider, stub

NAMES = ("windows", "linux", "darwin")

__all__ = ["KINDS", "NAMES", "REQUIRED", "Platform", "PlatformNotImplemented", "Provider", "detect", "load"]


def detect(sys_platform: Optional[str] = None) -> str:
    sp = sys_platform if sys_platform is not None else sys.platform
    if sp.startswith(("win32", "cygwin")):
        return "windows"
    if sp.startswith("linux"):
        return "linux"
    if sp.startswith("darwin"):
        return "darwin"
    return "unknown"


def load(name: str) -> Platform:
    """The named platform; an unknown name gets an all-stub platform."""
    if name in NAMES:
        module = importlib.import_module(f"{__name__}.{name}")
        return getattr(module, name.upper())
    return stub(name, {})
