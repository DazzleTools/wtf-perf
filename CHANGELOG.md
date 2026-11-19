# Changelog

All notable changes to wtf-perf are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.14] - 2026-11-18

### Fixed
- Pressing Ctrl-C while an AI command-line backend is answering now stops that backend's process instead of leaving it running.

## [0.1.13] - 2026-11-18

### Fixed
- `--ai` finds the command-line backends Windows can actually run: an extension-less script on PATH named like the backend no longer makes the call fail with "not a valid Win32 application".

## [0.1.12] - 2026-11-18

### Fixed
- The vendored AI library no longer names another tool's setting in its warning about an unchosen model, and its documentation now records that LM Studio cancels a generation when the client times out (measured).

## [0.1.11] - 2026-11-18

### Fixed
- The vendored AI library's cache no longer deletes unrelated files that share its directory (it removed any JSON file without a timestamp), and its entries are written atomically. It also accepts a caller-supplied key so that an answer can be reused for the same facts.

## [0.1.10] - 2026-11-18

### Added
- The vendored AI library's own test suite (140 tests for its cache, parsers, types and transports), carried over from the project it came from, so the library can be developed here safely.

## [0.1.9] - 2026-11-18

### Added
- `--ai [BACKEND]` adds a four-part AI summary (what happened, why, what to do, confidence) to `wtf-perf cpu`, from claude, codex, a local LM Studio or Ollama server, or `prompt-only` (saves the prompt to a file). `--ai-only` shows just the summary; `--ai-verbose` streams it; `--ai-model` picks a model (required for Ollama).
- Process names and figures only by default; `--ai-detail full` adds the top processes' command lines, with a warning when the backend runs off the machine. `--ai-save` keeps the chosen backend and detail level.
- The agent CLIs run with no tools and a single turn: the summary is built from strings other programs chose, and the CLI gets nothing to act on.

## [0.1.8] - 2026-11-18

### Changed
- The ledger's size rows say what they measure ("processes each using 5% or more of the machine"), and a line under the table defines a point: 1% of the whole machine, the scale of Task Manager's headline.

## [0.1.7] - 2026-11-18

### Added
- `wtf-perf` with no arguments runs `wtf-perf cpu`.
- A root `.wtf.json` manifest, so wtf-windows can mount the repository and run it as `wtf perf`.
- A human test checklist, `tests/checklists/v0.1.7__Tool__wtf-perf-cpu.md`.

## [0.1.6] - 2026-11-18

### Added
- `wtf-perf cpu` works: it samples for a few seconds (`-s`, default 10) and prints a verdict, a table of where every point of the headline went, the findings, then (after a keypress) the application families, top processes, short-lived processes and file operations, and finally every system counter. `--json` prints the same report for scripts; `-t/--tier` picks tiers; `-np/--no-page` turns off the pauses; `--interval` sets the poll gap.

## [0.1.5] - 2026-11-18

### Added
- The reconciliation ledger: the CPU headline split point by point into busy time plus the uplift from cores running above nominal speed, and busy time split into live processes by size, processes that exited during the window, interrupts and an unexplained remainder that is always shown.
- Findings and a verdict that answers whether the headline adds up: one process dominating, many small consumers, an application hidden across many small processes, short-lived process churn, kernel-heavy processes, file-system call storms while the disk is idle, and large groups of idle processes (informational).

### Fixed
- Families: hooks run through a shell (`cmd /c python ...`) now count with the application that ran them, and a session launcher such as csb no longer absorbs the Claude Code sessions it starts.

## [0.1.4] - 2026-11-18

### Added
- Processes roll up into application families: each process is counted with the application that started it, so an application running as hundreds of small processes can be ranked as one. Shells, terminals and service hosts are never treated as a family, and versioned builds of the same program (such as several Claude Code builds) count as one.

## [0.1.3] - 2026-11-18

### Added
- System-wide counters read through Windows' performance-counter API without WMI: processor utility (the figure Task Manager's headline shows), processor time and performance, interrupts, context switches, page faults and disk activity. A counter the machine lacks is reported as missing instead of failing the run.

## [0.1.2] - 2026-11-18

### Added
- A process sampler that reads every process's CPU time and file-operation counts from the kernel about ten times a second, without WMI, and counts processes that start and exit between samples. `wtf-perf cpu` will report from it in a coming release.

## [0.1.1] - 2026-11-18

### Added
- `wtf-perf` is now a dazzlecmd-lib aggregator: `wtf-perf list` shows the tools, `wtf-perf -h` lists them with examples, and the command works from any directory.
- A first tool, `cpu`, registered and dispatchable (its measurements arrive in the next releases).

## [0.1.0] - 2026-11-18

### Added
- The project's structure, from git-repokit.

[Unreleased]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.14...HEAD
[0.1.14]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.13...v0.1.14
[0.1.13]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.12...v0.1.13
[0.1.12]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.11...v0.1.12
[0.1.11]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.10...v0.1.11
[0.1.10]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.9...v0.1.10
[0.1.9]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/DazzleTools/wtf-perf/releases/tag/v0.1.0
