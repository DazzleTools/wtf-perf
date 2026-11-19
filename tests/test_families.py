"""Tests for wtf_perf.lib.families -- the roll-up the user's question rests on."""
from wtf_perf.lib.families import assign_families, family_label
from wtf_perf.lib.sampler import ProcRecord


def _r(pid, ppid, name, create):
    return ProcRecord(pid=pid, ppid=ppid, create=create, name=name)


def test_a_hook_chain_rolls_up_to_the_application_not_the_terminal():
    """bash -> node -> claude build -> pwsh -> Windows Terminal: the hook
    plumbing belongs to Claude Code, and the shell/terminal stop the walk."""
    recs = [
        _r(1, 0, "WindowsTerminal.exe", 10),
        _r(2, 1, "pwsh.exe", 20),
        _r(3, 2, "claude-dcc-2.1.323+dcc0.2.9.exe", 30),
        _r(4, 3, "node.exe", 40),
        _r(5, 4, "bash.exe", 50),
        _r(6, 2, "claude-dcc-2.1.327+dcc0.2.11.exe", 35),
    ]
    fam = assign_families(recs)
    assert {fam[(p, c)] for p, c in [(3, 30), (4, 40), (5, 50), (6, 35)]} == {"Claude Code"}
    assert fam[(2, 20)] == "pwsh" and fam[(1, 10)] == "WindowsTerminal"


def test_a_parent_younger_than_its_child_is_a_reused_id_not_the_parent():
    recs = [
        _r(100, 0, "steam.exe", 500),       # holds pid 100 now, started after the child
        _r(7, 100, "orphan.exe", 200),      # its real parent (old pid 100) is gone
    ]
    assert assign_families(recs)[(7, 200)] == "orphan"


def test_a_child_whose_parent_exited_is_its_own_family():
    assert assign_families([_r(9, 12345, "helper.exe", 1)])[(9, 1)] == "helper"


def test_labels_drop_exe_and_build_versions():
    assert family_label("claude.exe") == "Claude Code"
    assert family_label("Code.exe") == "VS Code"
    assert family_label("dopus.exe") == "Directory Opus"
    assert family_label("steam.exe") == "steam"
    assert family_label("System") == "System"
