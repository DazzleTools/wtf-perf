# wtf-perf

[![PyPI](https://img.shields.io/pypi/v/wtf-perf?color=green)](https://pypi.org/project/wtf-perf/)
[![Release Date](https://img.shields.io/github/release-date/DazzleTools/wtf-perf?color=green)](https://github.com/DazzleTools/wtf-perf/releases)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/wtf-perf?period=total&units=international_system&left_color=black&right_color=green&left_text=downloads)](https://pypistats.org/packages/wtf-perf)
[![CI](https://github.com/DazzleTools/wtf-perf/actions/workflows/ci-python.yml/badge.svg)](https://github.com/DazzleTools/wtf-perf/actions/workflows/ci-python.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/license-GPL%20v3-green.svg)](https://www.gnu.org/licenses/gpl-3.0.html)
[![GitHub Discussions](https://img.shields.io/github/discussions/DazzleTools/wtf-perf)](https://github.com/DazzleTools/wtf-perf/discussions)
[![Installs](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/djdarcy/PLACEHOLDER/raw/installs.json)](https://dazzletools.github.io/wtf-perf/stats/#installs)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://github.com/DazzleTools/wtf-perf)

Why is my Windows PC busy? Accounts for every point of CPU: processes, short-lived processes, interrupts and speed scaling

## Installation

```bash
pip install wtf-perf
```

From source:

```bash
git clone https://github.com/DazzleTools/wtf-perf.git
cd wtf-perf
pip install -e ".[dev]"
```

## Usage

```bash
wtf-perf --help          # the tools and some examples
wtf-perf list            # the available tools
wtf-perf                 # same as: wtf-perf cpu
wtf-perf cpu -s 15       # sample 15 s and account for every point of the CPU headline
wtf-perf cpu --json      # the same report as JSON
wtf-perf cpu --ai        # add an AI summary (claude by default; also codex, lmstudio, ollama, prompt-only)
python -m wtf_perf --version
```

wtf-perf is part of the wtf-windows family of diagnostics and is built on dazzlecmd-lib, so each drill-down is a tool under one command.

The AI summary sends process names and figures to the backend you choose -- never command lines unless you ask for them with `--ai-detail full` (with a warning when the backend runs off your machine). The agent CLIs run with no tools and one turn. `--ai-save` keeps your `--ai` backend and `--ai-detail` choice for later runs (in `~/.wtf-perf/config.json`). Without elevation, command lines of other users' and protected processes are reported as unavailable; everything else works the same.

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

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for:
- Development setup
- Running the tests
- Version management with `sync-versions.py`
- Pull request checklist

Like the project?

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/djdarcy)

## License

wtf-perf, Copyright (C) 2026 Dustin Darcy

Licensed under the GNU General Public License v3.0 or later (GPL-3.0-or-later) -- see [LICENSE](LICENSE).
