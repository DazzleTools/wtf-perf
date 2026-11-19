# wtf-perf

[![PyPI](https://img.shields.io/pypi/v/wtf-perf?color=green)](https://pypi.org/project/wtf-perf/)
[![Release Date](https://img.shields.io/github/release-date/DazzleTools/wtf-perf?color=green)](https://github.com/DazzleTools/wtf-perf/releases)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/wtf-perf?period=total&units=international_system&left_color=black&right_color=green&left_text=downloads)](https://pypistats.org/packages/wtf-perf)
[![CI](https://github.com/DazzleTools/wtf-perf/actions/workflows/ci-python.yml/badge.svg)](https://github.com/DazzleTools/wtf-perf/actions/workflows/ci-python.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/license-GPL%20v3-green.svg)](https://www.gnu.org/licenses/gpl-3.0.html)
[![GitHub Discussions](https://img.shields.io/github/discussions/DazzleTools/wtf-perf)](https://github.com/DazzleTools/wtf-perf/discussions)
[![Installs](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/djdarcy/PLACEHOLDER/raw/installs.json)](https://dazzletools.github.io/wtf-perf/stats/#installs)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/DazzleTools/wtf-perf)

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
wtf-perf --help
python -m wtf_perf --version
```

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

wtf-perf, Copyright (C) 2026 Dustin

Licensed under the GNU General Public License v3.0 or later (GPL-3.0-or-later) -- see [LICENSE](LICENSE).
