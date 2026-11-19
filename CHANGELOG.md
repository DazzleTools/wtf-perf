# Changelog

All notable changes to wtf-perf are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/DazzleTools/wtf-perf/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/DazzleTools/wtf-perf/releases/tag/v0.1.0
