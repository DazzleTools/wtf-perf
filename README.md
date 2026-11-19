# wtf-perf

[![PyPI](https://img.shields.io/pypi/v/wtf-perf?color=green)](https://pypi.org/project/wtf-perf/)
[![Release Date](https://img.shields.io/github/release-date/DazzleTools/wtf-perf?color=green)](https://github.com/DazzleTools/wtf-perf/releases)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/wtf-perf?period=total&units=international_system&left_color=black&right_color=green&left_text=downloads)](https://pypistats.org/packages/wtf-perf)
[![CI](https://github.com/DazzleTools/wtf-perf/actions/workflows/ci-python.yml/badge.svg)](https://github.com/DazzleTools/wtf-perf/actions/workflows/ci-python.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/license-GPL%20v3-green.svg)](https://www.gnu.org/licenses/gpl-3.0.html)
[![GitHub Discussions](https://img.shields.io/github/discussions/DazzleTools/wtf-perf)](https://github.com/DazzleTools/wtf-perf/discussions)
[![Installs](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/djdarcy/dbb1670b6ecd1aef7d32abc62a5098bd/raw/installs.json)](https://dazzletools.github.io/wtf-perf/stats/#installs)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://github.com/DazzleTools/wtf-perf/blob/main/docs/platform-support.md)

Why TF is my Windows PC slow? Accounts for every point of CPU: processes, short-lived processes, interrupts and speed scaling

Task Manager can show 45% CPU while its biggest process reads 3%. `wtf-perf` answers the question that leaves- is something hiding CPU, or are many small things adding up? It samples every process (including the ones that start and exit in under a second), reads the system counters over the same window, and accounts for the headline point by point.

## Installation

```bash
pip install wtf-perf        # once the first release is on PyPI
```

From source:

```bash
git clone https://github.com/DazzleTools/wtf-perf.git
cd wtf-perf
pip install -e ".[dev]"
```

## Usage

```bash
wtf-perf                 # same as: wtf-perf cpu (10-second sample)
wtf-perf cpu -s 15       # sample 15 s and account for every point of the CPU headline
wtf-perf cpu --json      # the same report as JSON, for scripts
wtf-perf cpu --ai        # add an AI summary (claude by default; also codex, lmstudio, ollama, prompt-only)
wtf-perf cpu --providers # this platform's data sources, and whether each can run here
wtf-perf --help          # the tools and some examples
wtf-perf list            # the available tools
python -m wtf_perf --version
```

Read-only throughout, and no elevation needed. Through [wtf-windows](https://github.com/djdarcy/wtf-windows) the same tool runs as `wtf perf`.

### What the report shows

Every figure is in **points**: one point is 1% of the whole machine over the sampling window, the unit of Task Manager's headline.

- **The verdict** -- one line answering the question: it adds up (dominated by one application, or many small consumers), or it does not add up, with the points left unexplained.
- **The ledger** -- `headline = busy time + speed-scaling uplift`, then `busy time = live processes (by size) + processes that exited during the window + interrupts/DPCs + unexplained`. The uplift is real: Task Manager's figure scales busy time by how fast the busy cores ran, so it reads higher than the time actually spent.
- **Applications** -- processes rolled up into families (an editor, an agent, a browser and all their helpers), because an application made of hundreds of small processes never ranks in Task Manager.
- **Short-lived processes** -- how many started and exited during the window, and which images.
- **File operations** -- read, write and other I/O operation rates per application.
- **Findings** -- warnings for odd or hidden consumers: one process hogging, many small consumers, a family hidden behind small processes, heavy process churn, an inflated headline, interrupt or kernel-heavy load, metadata storms.

The output pages in three tiers (summary, evidence, detail). Press a key for the next tier, `q` or Esc to stop.

### Options

| Option | What it does |
|---|---|
| `-s, --seconds N` | sampling window (default 10) |
| `--interval MS` | poll gap (default 100); shorter catches shorter-lived processes and costs more |
| `--top N` | rows per table (default 12) |
| `-t, --tier 0,1,2` | which tiers to show (`all` for every tier) |
| `-np, --no-page` | print the tiers without pausing |
| `--json` | the full report as JSON |
| `--platform NAME` | the provider set (`auto`, the detected platform, by default) |
| `--providers` | list the platform's data sources and whether each can run here |
| `--ai [BACKEND]` | add an AI summary; `--ai-only` shows only that, `--ai-verbose` streams it |
| `--ai-detail names\|full` | `names` (default) sends process names and figures; `full` adds the top processes' command lines |
| `--ai-model NAME` | the model to ask for (required for ollama) |
| `--ai-save` | keep `--ai` and `--ai-detail` as the defaults (in `~/.wtf-perf/config.json`) |

### The AI summary

The AI summary sends process names and figures to the backend you choose -- never command lines unless you ask for them with `--ai-detail full`, and then with a warning when the backend runs off your machine. The agent CLIs (claude, codex) run with no tools and one turn; lmstudio and ollama run locally; `prompt-only` writes the prompt to a file and calls nothing. Without elevation, command lines of other users' and protected processes are reported as unavailable; everything else works the same.

### Platforms

Windows is the supported platform and it's detailed. It reads the kernel's process table directly (no WMI, no PowerShell), plus the performance counters. The data sources sit behind a per-platform provider set; Linux and macOS have named stubs today, so on those systems `wtf-perf cpu` says which source is missing instead of sampling. What works where, provider by provider: [Platform support](https://github.com/DazzleTools/wtf-perf/blob/main/docs/platform-support.md). A Linux provider is tracked in [#4](https://github.com/DazzleTools/wtf-perf/issues/4).

### Known limits

- **Processes shorter than the poll gap** are never seen, so their CPU lands in the unexplained line. On a machine with heavy process churn (editor and agent hooks) that line can reach 3-4 points; measured, about three quarters of it is such processes. Recording the kernel's process-exit events would account for them: [#3](https://github.com/DazzleTools/wtf-perf/issues/3).
- **More than 64 logical processors** (more than one processor group) are not handled yet.
- The thresholds behind the findings were set on one machine; each finding prints its evidence so you can judge it.

wtf-perf is part of the [wtf-windows](https://github.com/djdarcy/wtf-windows) family of diagnostics and is built on [dazzlecmd-lib](https://github.com/DazzleLib/dazzlecmd-lib), so each drill-down is a tool under one command.

## Development

Prerequisites:

- Python 3.10+
- Git

Setup:

```bash
git clone https://github.com/DazzleTools/wtf-perf.git
cd wtf-perf
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
bash scripts/repokit-common/install-hooks.sh
```

Tests:

```bash
python -m pytest tests/ -v
```

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

See **[CONTRIBUTING.md](https://github.com/DazzleTools/wtf-perf/blob/main/CONTRIBUTING.md)** for:
- Development setup
- Running the tests
- Version management with `sync-versions.py`
- Pull request checklist

Like the project?

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/djdarcy)

## License

wtf-perf, Copyright (C) 2026 Dustin Darcy

Licensed under the GNU General Public License v3.0 or later (GPL-3.0-or-later) -- see [LICENSE](https://github.com/DazzleTools/wtf-perf/blob/main/LICENSE).
