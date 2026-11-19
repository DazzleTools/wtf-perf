"""Tests for wtf-perf's AI layer (wtf_perf/aiwire.py) and the cpu tool's --ai flags.

No test reaches a real AI backend: every backend is a stub, and the stub's
invoke raises unless a test opts in. (Critical Safety Rule 1b.)
"""
import os
import tempfile
from pathlib import Path

import pytest

from wtf_perf import aiwire
from wtf_perf._vendor.ailib.backend import transport_for
from wtf_perf._vendor.ailib.types import ON_PREM, Readiness, Request, Response

REPORT = {
    "window": {"seconds": 10}, "headline": {"utility": 70.0}, "reconciliation": {"busy": 58.0},
    "families": [{"family": "Claude Code", "points": 16.9, "processes": 316}],
    "processes": [
        {"pid": 101, "name": "Everything.exe", "family": "Everything", "points": 18.9, "born": False, "exited": False},
        {"pid": 102, "name": "git.exe", "family": "Claude Code", "points": 0.4, "born": True, "exited": True},
    ],
    "churn": {}, "io": {}, "counters": {}, "findings": [], "verdict": {"type": "ADDS_UP"},
}
ANSWER = "What Happened: busy.\nWhy: Everything.\nWhat To Do: 1. close it\nConfidence: High - measured."


class StubBackend:
    def __init__(self, ok=True, answer=ANSWER, on_prem=False, allow_invoke=True):
        self._ok, self._answer, self._allow = ok, answer, allow_invoke
        self.capabilities = frozenset({ON_PREM}) if on_prem else frozenset()
        self.prompts = []

    def probe(self):
        return Readiness(self._ok, "" if self._ok else "not installed")

    def invoke(self, req):
        if not self._allow:
            raise AssertionError("invoke must not be reached")
        self.prompts.append(req.prompt)
        return Response(status="answered", text=self._answer, model_used="stub")


def _builder(stub):
    return lambda spec: stub


def test_the_default_payload_carries_names_and_no_command_lines():
    stub = StubBackend()
    out = aiwire.run_ai(REPORT, "claude", command_lines={101: r"C:\x\Everything.exe -token SECRET"},
                        builder=_builder(stub))
    assert out["success"] and out["sections"]["what_to_do"].startswith("1.")
    assert "SECRET" not in stub.prompts[0] and "Everything.exe" in stub.prompts[0]


def test_full_detail_adds_command_lines_marks_exited_ones_and_warns_off_machine():
    stub = StubBackend(on_prem=False)
    out = aiwire.run_ai(REPORT, "claude", detail="full", command_lines={101: "Everything.exe -startup"},
                        builder=_builder(stub))
    assert "Everything.exe -startup" in stub.prompts[0]
    assert "exited before it could be read" in stub.prompts[0]
    assert any("command lines" in w for w in out["warnings"])


def test_full_detail_to_a_local_backend_does_not_warn():
    out = aiwire.run_ai(REPORT, "lmstudio", detail="full", builder=_builder(StubBackend(on_prem=True)))
    assert not any("command lines" in w for w in out["warnings"])


def test_an_unavailable_backend_is_an_error_not_an_exception():
    out = aiwire.run_ai(REPORT, "codex", builder=_builder(StubBackend(ok=False, allow_invoke=False)))
    assert not out["success"] and "not available" in out["error"]


def test_ollama_without_a_model_is_refused_before_any_probe():
    out = aiwire.run_ai(REPORT, "ollama", builder=_builder(StubBackend(allow_invoke=False)))
    assert "needs a model" in out["error"]


def test_the_agent_cli_presets_have_no_tools_and_one_turn():
    t = transport_for("cli")
    claude = aiwire.presets()["claude"]
    argv, _, _ = t._argv(claude, Request(prompt="x"), "claude", Path(tempfile.mkdtemp()))
    assert argv[argv.index("--tools") + 1] == "" and argv[argv.index("--max-turns") + 1] == "1"
    codex = aiwire.presets()["codex"]
    argv, _, _ = t._argv(codex, Request(prompt="x"), "codex", Path(tempfile.mkdtemp()))
    assert argv[argv.index("-s") + 1] == "read-only"


def test_saved_detail_is_used_and_the_flag_overrides_it(tmp_path, monkeypatch):
    from wtf_perf.tools.core.cpu import cpu

    monkeypatch.setenv("WTF_PERF_CONFIG_DIR", str(tmp_path))
    cpu.save_ai_settings({"detail": "full", "backend": "codex"})
    assert cpu.resolve_ai(None, None) == ("codex", "full")
    assert cpu.resolve_ai("claude", "names") == ("claude", "names")
    assert cpu.resolve_ai(None, "names") == ("codex", "names")


def test_command_line_of_this_process_is_readable():
    from wtf_perf.platforms.windows import read_command_line

    cl = read_command_line(os.getpid())
    assert cl is None or "python" in cl.lower()
