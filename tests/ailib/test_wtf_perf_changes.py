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


def test_an_entry_without_a_format_still_reads(tmp_path):
    stub = _Stub()
    first = cache.run(stub, Request(prompt="p"), cache_dir=tmp_path)
    path = next(tmp_path.iterdir())
    body = json.loads(path.read_text(encoding="utf-8"))
    body.pop("format")
    path.write_text(json.dumps(body), encoding="utf-8")
    again = cache.run(stub, Request(prompt="p"), cache_dir=tmp_path)
    assert again.cached and again.text == first.text and stub.calls == 1
