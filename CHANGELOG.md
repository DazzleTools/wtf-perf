# Changelog

All notable changes to wtf-perf are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.6...HEAD
[0.1.6]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/DazzleTools/wtf-perf/releases/tag/v0.1.0
