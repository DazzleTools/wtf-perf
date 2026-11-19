"""Tests for the changes made in wtf-perf's copy of the AI library (the fork of
record from 2026-11-18). Each is listed under "Changes in wtf-perf's copy" in
wtf_perf/_vendor/ailib/_VENDORED.md. Every backend here is a stub; nothing
touches a real home directory (all cache directories are tmp_path).
"""
import json

from wtf_perf._vendor.ailib import cache
from wtf_perf._vendor.ailib.backend import build
from wtf_perf._vendor.ailib.types import Request, Response, Spec


class _Stub:
    def __init__(self):
        self.calls = 0
        self.spec = Spec("prompt-file", name="stub", endpoint="x")
        self.identity = "stub-identity"

    def invoke(self, req):
        self.calls += 1
        return Response("answered", text=f"answer {self.calls}")


def test_the_sweep_leaves_a_host_config_file_alone(tmp_path):
    """The defect: a config.json (no cached_at) in the cache directory was
    deleted on the first answered call."""
    (tmp_path / "config.json").write_text(json.dumps({"ai": {"detail": "full"}}), encoding="utf-8")
    cache.run(_Stub(), Request(prompt="p"), cache_dir=tmp_path)
    assert (tmp_path / "config.json").is_file()


def test_the_sweep_still_removes_a_stale_entry_under_any_name(tmp_path):
    stale = tmp_path / "anything_at_all.json"
    stale.write_text(json.dumps({"cached_at": 1.0, "response": {"text": "old"}}), encoding="utf-8")
    cache.run(_Stub(), Request(prompt="p"), cache_dir=tmp_path)
    assert not stale.exists()


def test_a_caller_key_reuses_an_answer_across_changing_prompts(tmp_path):
    stub = _Stub()
    a = cache.run(stub, Request(prompt="busy 41.2"), cache_dir=tmp_path, key="same-facts")
    b = cache.run(stub, Request(prompt="busy 41.7"), cache_dir=tmp_path, key="same-facts")
    assert stub.calls == 1 and b.cached and b.text == a.text


def test_entries_carry_a_format_and_writes_leave_no_temp_files(tmp_path):
    cache.run(_Stub(), Request(prompt="p"), cache_dir=tmp_path)
    entries = [p for p in tmp_path.iterdir()]
    assert len(entries) == 1 and not entries[0].name.startswith(".tmp-")
    assert json.loads(entries[0].read_text(encoding="utf-8"))["format"] == cache.CACHE_FORMAT


def test_every_request_field_is_keyed_or_deliberately_not():
    """A new Request field must be decided: in the cache fingerprint, or left
    out on purpose. Forgetting it would give two different requests one key."""
    import dataclasses
    keyed = {"prompt", "schema", "max_tokens", "temperature"}
    not_keyed = {"timeout", "stream_to", "workdir", "idle"}   # how to ask, not what is asked
    fields = {f.name for f in dataclasses.fields(Request)}
    assert fields == keyed | not_keyed, f"undecided Request fields: {fields - keyed - not_keyed}"
    base = Request(prompt="p")
    for name in keyed:
        changed = dataclasses.replace(base, **{name: {"schema": {"x": 1}, "max_tokens": 9,
                                                       "temperature": 0.5, "prompt": "q"}[name]})
        assert changed.fingerprint() != base.fingerprint(), f"{name} is not in the fingerprint"


def test_every_response_field_is_cached_or_deliberately_not(tmp_path):
    """A new Response field must be decided: carried by a cache entry, or
    rebuilt on a hit. Forgetting it would make it vanish on a cache hit."""
    import dataclasses
    stored = {"text", "model_used", "honoured", "elapsed"}
    rebuilt = {"status", "error", "artifact", "cached", "cached_at", "key"}   # set by run() or meaningless cached
    fields = {f.name for f in dataclasses.fields(Response)}
    assert fields == stored | rebuilt, f"undecided Response fields: {fields - stored - rebuilt}"
    cache.run(_Stub(), Request(prompt="p"), cache_dir=tmp_path)
    entry = json.loads(next(tmp_path.iterdir()).read_text(encoding="utf-8"))["response"]
    assert set(entry) == stored


def test_windows_lookup_prefers_a_runnable_extension_over_a_posix_shim(tmp_path, monkeypatch):
    """A bare `tool` shim sits on PATH beside `tool.cmd`: the lookup must
    return the .cmd, which Windows can run (the WinError 193 defect)."""
    import sys
    from wtf_perf._vendor.ailib.transports import cli as cli_mod
    (tmp_path / "tool").write_text("#!/bin/sh\n", encoding="utf-8")
    (tmp_path / "tool.cmd").write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("PATHEXT", ".EXE;.CMD")
    monkeypatch.setattr(sys, "platform", "win32")
    assert cli_mod.find_exe("tool").lower().endswith("tool.cmd")


def test_an_interrupt_in_the_reader_kills_the_child(tmp_path, monkeypatch):
    """Ctrl-C while waiting must not leave the CLI child running. The child is
    a harmless sleeping Python; the interrupt is simulated in time.sleep."""
    import subprocess
    import sys
    import pytest
    from wtf_perf._vendor.ailib.transports import cli as cli_mod
    procs = []
    real_popen = subprocess.Popen

    def recording_popen(*a, **kw):
        p = real_popen(*a, **kw)
        procs.append(p)
        return p

    calls = {"n": 0}

    def interrupting_sleep(_):
        calls["n"] += 1
        if calls["n"] > 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli_mod.subprocess, "Popen", recording_popen)
    monkeypatch.setattr(cli_mod.time, "sleep", interrupting_sleep)
    t = cli_mod.CliTransport() if hasattr(cli_mod, "CliTransport") else None
    if t is None:
        from wtf_perf._vendor.ailib.backend import transport_for
        t = transport_for("cli")
    with pytest.raises(KeyboardInterrupt):
        t._stream("sleeper", [sys.executable, "-c", "import time; time.sleep(30)"], None, tmp_path, None,
                  Request(prompt="", idle=0, timeout=0))
    assert procs and procs[0].poll() is not None, "the child was left running"


def test_an_entry_without_a_format_still_reads(tmp_path):
    stub = _Stub()
    first = cache.run(stub, Request(prompt="p"), cache_dir=tmp_path)
    path = next(tmp_path.iterdir())
    body = json.loads(path.read_text(encoding="utf-8"))
    body.pop("format")
    path.write_text(json.dumps(body), encoding="utf-8")
    again = cache.run(stub, Request(prompt="p"), cache_dir=tmp_path)
    assert again.cached and again.text == first.text and stub.calls == 1
