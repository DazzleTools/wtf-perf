"""Tests for the platform seam: detection, providers, stubs, and the refusals.

No test here can start a real sampler (Rule 1b): every path that could reach
``collect`` patches it to raise.
"""
from __future__ import annotations

import pytest

import wtf_perf.tools.core.cpu.cpu as cpu
from wtf_perf import platforms
from wtf_perf.platforms import KINDS, Platform, PlatformNotImplemented, Provider


def _refuse_sampling(monkeypatch):
    monkeypatch.setattr(cpu, "collect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sampled")))


@pytest.mark.parametrize("sp, name", [("win32", "windows"), ("cygwin", "windows"), ("linux", "linux"),
                                      ("darwin", "darwin"), ("freebsd14", "unknown")])
def test_detect_maps_sys_platform(sp, name):
    assert platforms.detect(sp) == name


@pytest.mark.parametrize("name", ["linux", "darwin", "freebsd"])
def test_stub_platforms_refuse_to_sample_and_name_what_is_missing(name):
    plat = platforms.load(name)
    with pytest.raises(PlatformNotImplemented) as exc:
        plat.snapshot_source()
    assert exc.value.missing[0][0] == "snapshot" and "not implemented" in exc.value.missing[0][1]
    assert plat.counter_backend() is None
    assert plat.command_line_reader()(1) is None
    assert plat.is_elevated() is False


def test_a_provider_for_another_host_is_unavailable(monkeypatch):
    monkeypatch.setattr(platforms.base.sys, "platform", "linux")
    plat = platforms.load("windows")
    missing = plat.unavailable()
    assert missing and "needs a win32 host" in missing[0][1]
    with pytest.raises(PlatformNotImplemented):
        plat.snapshot_source()


def test_every_windows_provider_kind_is_declared():
    plat = platforms.load("windows")
    assert set(plat.providers) == set(KINDS)


def test_windows_counters_degrade_to_none_when_pdh_cannot_open(monkeypatch):
    from wtf_perf.platforms import windows

    def broken():
        raise OSError("PdhOpenQueryW failed")

    monkeypatch.setattr(windows, "CtypesPdh", broken)
    assert windows.counter_backend() is None


def test_platform_flag_for_a_stub_exits_2_without_sampling(monkeypatch, capsys):
    _refuse_sampling(monkeypatch)
    assert cpu.main(["--platform", "linux", "-s", "1"]) == 2
    err = capsys.readouterr().err
    assert "linux providers cannot sample here" in err and "snapshot" in err


def test_providers_lists_every_kind_and_samples_nothing(monkeypatch, capsys):
    _refuse_sampling(monkeypatch)
    assert cpu.main(["--platform", "darwin", "--providers"]) == 0
    out = capsys.readouterr().out
    for kind in KINDS:
        assert kind in out
    assert "unavailable" in out and "libproc" in out


def test_a_host_mismatch_refuses_like_a_stub(monkeypatch, capsys):
    _refuse_sampling(monkeypatch)
    monkeypatch.setattr(platforms.base.sys, "platform", "linux")
    assert cpu.main(["--platform", "windows", "-s", "1"]) == 2
    assert "needs a win32 host" in capsys.readouterr().err


def test_collect_uses_only_the_platform_it_is_given():
    """A platform built from stubs drives collect end to end; provider_set records it."""
    from wtf_perf.lib.sampler import CpuTotals, ProcRecord

    class Src:
        def __init__(self):
            self.t = 0.0

        def processes(self):
            self.t += 1.0
            return self.t, {(4, 1): ProcRecord(pid=4, ppid=0, create=1, name="System", user=int(self.t * 1e6))}

        def cpus(self):
            return CpuTotals(idle=10**7, kernel=2 * 10**7, user=10**7, ncpu=2)

    plat = Platform("scripted", {"snapshot": Provider("snapshot", Src)})
    report = cpu.collect(1, 1, 5, plat)
    assert report["system"]["provider_set"] == "scripted"
    assert report["counters"]["utility"] is None          # no counters provider -> missing, not an error
