# Contributing to wtf-perf

Thank you for considering contributing to wtf-perf!

## Development Setup

### Prerequisites

- Python 3.10+
- Git

### Clone and set up

```bash
git clone https://github.com/DazzleTools/wtf-perf.git
cd wtf-perf
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
bash scripts/repokit-common/install-hooks.sh
```

### Run the tests

```bash
python -m pytest tests/ -v
```

## Version Management

The version lives in one place and the pre-commit hook keeps every other copy in step. To bump it:

```bash
python scripts/repokit-common/sync-versions.py --bump patch   # or minor, major
python scripts/repokit-common/sync-versions.py --check        # every copy agrees?
```

## Key Design Principles

1. **Tests are important** -- write tests for new features
2. **One-offs graduate** -- quick checks in `tests/one-offs/` can be promoted to proper tests
3. **Cross-platform** -- works on Windows, Linux and macOS
4. **Clean commits** -- use the conventional commit format

## Pull Requests

1. Fork the repository and create a branch
2. Make your change, with tests
3. Run the tests
4. Open a pull request describing what changed and why
