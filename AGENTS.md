# AGENTS.md

Guidance for AI coding agents working in this repository. Read [CONTRIBUTING.md](CONTRIBUTING.md) as well: everything there applies to you.

## What this project is

`wtf-perf` (package `wtf_perf`) accounts for every point of the CPU figure Task Manager shows: live processes, processes that started and exited during the window, interrupts, speed scaling, and an honest unexplained remainder. People run it on their own machines to find out what is using their CPU. A wrong number here sends them after the wrong program.

## Commands

```bash
python -m pytest -q                 # the full suite; it must pass before you finish
python -m wtf_perf cpu -s 5 -np     # a real 5-second sample (Windows)
python -m wtf_perf cpu --providers  # the platform's data sources
pip install -e ".[dev]"             # an editable install with the test tools
```

## Where things are

- `wtf_perf/platforms/`: everything operating-system-specific, one module per platform (`windows.py` implemented; `linux.py` and `darwin.py` are stubs). `base.py` defines providers and platforms.
- `wtf_perf/lib/sampler.py`: the platform-free sampling loop and the `SnapshotSource` contract.
- `wtf_perf/lib/ledger.py`, `findings.py`, `families.py`, `render.py`: the account, the warnings and verdict, the application roll-up, the output.
- `wtf_perf/tools/core/cpu/cpu.py`: the command and its flags.
- `wtf_perf/_vendor/ailib/`: a vendored AI library; every change to it is recorded in its `_VENDORED.md`.
- `tests/`: stub sources and fake counters; `tests/one-offs/` holds probes, each with its results in its own comments.
- `docs/platform-support.md`: what works on which platform.

## Rules you must follow

1. **Read-only.** Never write outside `~/.wtf-perf/` and the `prompt-only` file; never change a system setting.
2. **The ledger must add up.** Every line of busy time sums to the total; what cannot be attributed is shown as unexplained, and the tool's own cost is reported.
3. **No WMI polling, no services, nothing left running.** Read the kernel and the counters directly.
4. **Operating-system code only in `wtf_perf/platforms/`.** The rest of the package must import and run its tests on Linux.
5. **No network access except the AI backend the user names, no telemetry, no code that runs at import, no new dependencies** without an issue first.
6. **Tests must be able to fail, and must not be able to do the real thing.** Each new test must fail when the change is reverted (revert the behaviour, never the API; say which tests failed and which passed either way). No test may start a real sampling window longer than a second or a real AI call: stub the source or patch the entry point to raise.
7. **A change to what is measured needs a real run** by the human you work for: `wtf-perf cpu -s 15` compared with Task Manager, and `unexplained` and `self_cost_pct` from `--json` before and after. Say plainly if this was not done.

## When you open a pull request

The human you work for must write the summary in their own words, and fill in the template's AI-tools and vetting sections truthfully. Do not write those sections for them, but you can help them edit if they are having difficulties expressing themselves or there is a language barrier -- and say you did the edits: the human is responsible for what is written, and the maintainer wants to know what they are trying to do in their own words. List what you changed and what you ran, so they can check it.
