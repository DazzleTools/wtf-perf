"""wtf-perf's copy of ailib -- the fork of record from 2026-11-18: purity and honesty.

Copied from git-repokit's tests/test_vendored_ailib.py (itself modelled on
ccs's), then the host names changed. Purity: the copy names nothing of its
host -- no import of wtf_perf, no relative import out of _vendor/ailib, no
host token, standard library only -- so it lifts unchanged into dazzle-ailib.
Honesty: every file matches the fingerprint it arrived with, or is named in
_VENDORED.md's "Changes in wtf-perf's copy".
"""
import ast
import hashlib
import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VENDOR = REPO / "wtf_perf" / "_vendor"
AILIB = VENDOR / "ailib"
RECORD = AILIB / "_VENDORED.md"
SECTION = "## wtf-perf's copy"

# Known leak "ai_merge_" (a ccs setting name in openai_compat.py) is not listed
# until phase L removes it; see _VENDORED.md.
_FORBIDDEN = ("wtf_perf", "wtf-perf", "dazzle_claude_config", "ccs_", "CCS_")


def _py():
    return sorted(p for p in AILIB.rglob("*.py") if "__pycache__" not in p.parts)


def _sha(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _section():
    text = RECORD.read_text(encoding="utf-8")
    return text[text.index(SECTION):]


def _received():
    rows = {}
    for line in _section().splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*\d+\s*\|\s*([0-9a-f]{64})\s*\|", line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def test_the_vendor_tree_is_a_package_with_its_record():
    assert (VENDOR / "__init__.py").is_file() and (AILIB / "__init__.py").is_file()
    assert RECORD.is_file() and SECTION in RECORD.read_text(encoding="utf-8")


def test_purity_nothing_under_vendor_knows_its_host():
    """Real import statements (read with ast, so docstring examples do not
    count) stay inside the copy or the standard library; no host token appears."""
    stdlib = set(sys.stdlib_module_names) | {"__future__"}
    bad = []
    for p in _py():
        rel = p.relative_to(AILIB).as_posix()
        sub = "" if p.parent == AILIB else "." + p.parent.relative_to(AILIB).as_posix().replace("/", ".")
        pkg = "wtf_perf._vendor.ailib" + sub
        text = p.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ImportFrom) and node.level:
                target = importlib.util.resolve_name("." * node.level + (node.module or ""), pkg)
                if not target.startswith("wtf_perf._vendor.ailib"):
                    bad.append(f"{rel}:{node.lineno}: relative import leaves _vendor/ailib")
            elif isinstance(node, ast.ImportFrom) and node.module.split(".")[0] not in stdlib:
                bad.append(f"{rel}:{node.lineno}: not the standard library: {node.module}")
            elif isinstance(node, ast.Import):
                bad += [f"{rel}:{node.lineno}: not the standard library: {a.name}"
                        for a in node.names if a.name.split(".")[0] not in stdlib]
        for n, line in enumerate(text.splitlines(), 1):
            for tok in _FORBIDDEN:
                if tok in line:
                    bad.append(f"{rel}:{n}: token {tok!r}")
    assert not bad, "\n".join(bad)


def test_every_file_is_as_received_or_named_in_the_changes():
    received = _received()
    files = {p.relative_to(AILIB).as_posix(): p for p in _py()}
    assert set(received) == set(files), "a vendored file has no row, or a row has no file"
    changes = _section().split("### Changes in wtf-perf's copy", 1)[1]
    undeclared = [rel for rel, p in files.items() if _sha(p) != received[rel] and f"`{rel}`" not in changes]
    assert undeclared == [], f"changed without a record entry: {undeclared}"


def test_the_copy_imports():
    from wtf_perf._vendor.ailib import backend, parsers  # noqa: F401
    from wtf_perf._vendor.ailib.transports import cli, openai_compat, prompt_file  # noqa: F401
    assert hasattr(backend, "build")
