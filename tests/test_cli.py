"""CLI surface tests for wtf-perf.

These validate the pure-Python wiring -- kit registration, tool-manifest
integrity, packaging of the dotfile manifests, and dispatch from a foreign
working directory. Nothing here samples the machine or calls an AI backend.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "wtf_perf"

# The tools the core kit is expected to register, and the script each dispatches to.
EXPECTED_TOOLS = {
    "cpu": "cpu.py",
}


def _kit():
    return json.loads((PKG / "kits" / "core.kit.json").read_text(encoding="utf-8"))


def _run(args, cwd):
    """Run `python -m wtf_perf <args>` from `cwd`, with the repo root importable.

    The tool is not required to be pip-installed for the tests, so the root goes
    on PYTHONPATH; the working directory is deliberately somewhere else.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "wtf_perf", *args],
        cwd=str(cwd), env=env, capture_output=True, text=True, timeout=60,
    )


def test_kit_registers_every_expected_tool():
    listed = {t.split(":", 1)[1] for t in _kit()["tools"]}
    assert listed == set(EXPECTED_TOOLS), f"kit tools {listed} != expected {set(EXPECTED_TOOLS)}"


@pytest.mark.parametrize("tool,script", sorted(EXPECTED_TOOLS.items()))
def test_tool_manifest_and_script_exist(tool, script):
    tdir = PKG / "tools" / "core" / tool
    manifest = tdir / ".wtf-perf.json"
    assert manifest.is_file(), f"missing manifest for {tool}"
    m = json.loads(manifest.read_text(encoding="utf-8"))
    assert m["name"] == tool
    assert m["namespace"] == "core"
    rt = m["runtime"]
    assert rt["type"] == "python"
    assert rt["entry_point"] == "main"
    assert rt["script_path"] == script
    assert (tdir / script).is_file(), f"missing {script} for {tool}"


def test_pyproject_packages_the_dotfile_manifests():
    """Regression guard (inherited from wtf-rdp's 0.3.1 packaging bug): the
    per-tool manifests are named `.wtf-perf.json` (leading dot), and setuptools'
    `*` glob skips dotfiles, so `tools/**/*` alone drops every manifest from the
    wheel and the installed CLI reports "No tools found". package-data MUST list
    the dotfile explicitly."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "tools/**/.wtf-perf.json" in text, (
        "pyproject package-data must explicitly include the leading-dot "
        ".wtf-perf.json manifests, or the built wheel ships no tool manifests."
    )


@pytest.mark.skipif(not (ROOT / ".git").exists(), reason="needs the git checkout")
def test_no_package_source_is_git_ignored():
    """Regression guard: the template's unanchored `lib/` rule once ignored
    the whole wtf_perf/lib package, so the sampler would have been left out
    of the commit and the wheel without a word (2026-11-18)."""
    sources = [str(p.relative_to(ROOT)) for p in PKG.rglob("*.py") if "__pycache__" not in p.parts]
    result = subprocess.run(["git", "check-ignore", "--no-index", *sources], cwd=str(ROOT),
                            capture_output=True, text=True)
    assert result.stdout.strip() == "", f"git-ignored package sources:\n{result.stdout}"


def test_list_finds_tools_from_a_foreign_working_directory(tmp_path):
    """The aggregator root comes from the package location, not the cwd: this is
    what makes `wtf-perf` work from anywhere and under the wtf-windows
    pass-through."""
    result = _run(["list"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "cpu" in result.stdout, f"`list` did not show cpu:\n{result.stdout}\n{result.stderr}"


def test_cpu_dispatches_from_a_foreign_working_directory(tmp_path):
    result = _run(["cpu"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "wtf-perf cpu" in result.stdout


def _epilog(monkeypatch, capsys, columns):
    """Return `wtf-perf -h` output lines at a fixed terminal width."""
    from wtf_perf.cli import main

    monkeypatch.setenv("COLUMNS", str(columns))
    with pytest.raises(SystemExit):
        main(["-h"])
    return capsys.readouterr().out.splitlines()


def _section(lines, header):
    start = lines.index(header) + 1
    out = []
    for line in lines[start:]:
        if not line.strip():
            break
        out.append(line)
    return out


def test_epilog_tool_rows_fit_the_terminal_width(monkeypatch, capsys):
    """Long descriptions are truncated so each tools: row fits the width."""
    width = 80
    rows = _section(_epilog(monkeypatch, capsys, width), "tools:")
    for row in rows:
        assert len(row) <= width, f"row overruns {width} columns: {row!r}"
    # cpu's description is longer than 80 columns allow, so its row is cut --
    # and a cut description is marked, never silently shortened.
    cpu_row = next(r for r in rows if r.split()[0] == "cpu")
    assert cpu_row.endswith("..."), cpu_row


def test_epilog_shows_the_full_description_when_wide(monkeypatch, capsys):
    """With room to spare, a tool's description is printed whole."""
    manifest = json.loads((PKG / "tools" / "core" / "cpu" / ".wtf-perf.json").read_text(encoding="utf-8"))
    rows = _section(_epilog(monkeypatch, capsys, 300), "tools:")
    assert any(manifest["description"] in row for row in rows), rows


def test_epilog_getting_started_descriptions_share_one_column(monkeypatch, capsys):
    """Every getting-started description starts in the same column."""
    from wtf_perf.cli import _HELP_EXAMPLES

    rows = _section(_epilog(monkeypatch, capsys, 120), "getting started:")
    starts = {row.index(desc) for row, (_, desc) in zip(rows, _HELP_EXAMPLES)}
    assert len(starts) == 1, rows


def test_version_shows_the_display_version_then_the_build_string(tmp_path):
    """`--version` reads `wtf-perf <display> (<build>)`: the short version a
    person quotes comes first, the hook-written build string in parentheses."""
    from wtf_perf._version import __version__, get_display_version

    result = _run(["--version"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert f"{get_display_version()} ({__version__})" in result.stdout, result.stdout


def test_main_hands_its_argv_to_the_engine_unchanged(monkeypatch):
    """main(argv) dispatches exactly argv -- an explicit empty list included --
    and never falls back to the process's own command line."""
    import wtf_perf.cli as cli

    seen = []

    class FakeEngine:
        def run(self, argv):
            seen.append(argv)
            return 0

    monkeypatch.setattr(cli, "build_engine", lambda: FakeEngine())
    monkeypatch.setattr(sys, "argv", ["wtf-perf", "sentinel-from-sys-argv"])
    assert cli.main([]) == 0
    assert cli.main(["list"]) == 0
    assert seen == [[], ["list"]]


def test_cli_epilog_lists_all_tools(capsys):
    """`wtf-perf -h` epilog should enumerate every registered tool in its
    `tools:` section. The check reads only that section: the hard-coded
    "getting started" examples also mention `cpu`, so a whole-output search
    would pass even with no tools registered (red-green audit, 2026-11-18)."""
    from wtf_perf.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["-h"])
    assert exc.value.code == 0
    lines = capsys.readouterr().out.splitlines()
    assert "tools:" in lines, "`wtf-perf -h` has no tools: section"
    section = []
    for line in lines[lines.index("tools:") + 1:]:
        if not line.strip():
            break
        section.append(line.split()[0])
    for tool in EXPECTED_TOOLS:
        assert tool in section, f"{tool} missing from the tools: section of `wtf-perf -h`"
