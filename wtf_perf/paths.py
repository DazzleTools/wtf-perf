"""Where wtf-perf keeps its own files: settings and saved AI prompts.

``WTF_PERF_CONFIG_DIR`` overrides the default ``~/.wtf-perf`` -- for tests and
for anyone who keeps settings elsewhere. Everything wtf-perf writes lives
under this one folder.
"""
from __future__ import annotations

import os
from pathlib import Path


def settings_dir() -> Path:
    override = os.environ.get("WTF_PERF_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".wtf-perf"
