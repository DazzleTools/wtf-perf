# Contributing to wtf-perf

Thank you for helping. wtf-perf runs on people's own machines to tell them what is using their CPU, so every contribution is held to one standard: it must report the truth, and it must not change anything or reach anywhere the user did not ask for.

## The promises every change keeps

- **Read-only.** wtf-perf changes nothing on the machine. The only files it writes are its own settings (`~/.wtf-perf/config.json`, with `--ai-save`) and, with `--ai prompt-only`, the prompt file it names.
- **Every point accounted for, honestly.** The ledger's lines add up to the headline. What cannot be attributed is printed as unexplained, never folded into another line, and the tool's own cost is reported, never hidden.
- **Nothing leaves the machine unless asked.** The report goes nowhere. `--ai` sends process names and figures to the backend the user names; command lines only with `--ai-detail full`, with a warning when that backend is off the machine.
- **Light on the machine it measures.** No WMI polling (it saturates WMI at the rates the sampler needs), no background services, and a self-cost that stays near 1% of the machine.
- **Platform-free core.** Operating-system code lives only in `wtf_perf/platforms/`; see [Platform support](docs/platform-support.md).

## Reporting a bug

Please include:
- the version (`python -m wtf_perf --version`), your Windows version, and whether the shell was elevated;
- the exact command and its output -- `wtf-perf cpu -s 15 --json` is the most useful;
- what you expected and what happened, and what Task Manager showed at the time if the numbers look wrong.

## Development setup

```bash
git clone https://github.com/DazzleTools/wtf-perf.git
cd wtf-perf
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
bash scripts/repokit-common/install-hooks.sh
python -m pytest -q              # the full suite
```

The version lives in one place and the pre-commit hook keeps every other copy in step:

```bash
python scripts/repokit-common/sync-versions.py --bump patch   # or minor, major
python scripts/repokit-common/sync-versions.py --check        # every copy agrees?
```

## Pull requests

AI-assisted contributions are welcome. The bar is the same for everyone, and so are the questions the [pull request template](.github/pull_request_template.md) asks. **A pull request that does not answer them will be closed unread.**

### Explain it in your own words

Write, yourself, what the change does and why. Do not paste a model's summary. If you cannot explain a line, do not submit it.

### Say which AI tools you used, and for what

Name each tool or model, and what it did: wrote code, wrote tests, suggested a design, reviewed, or nothing. "None" is a fine answer.

### Say how you vetted it

At the least:
- you read every changed line;
- the full test suite passes (`python -m pytest -q`);
- every new test fails without your change, and passes with it. Show it once, by reverting the behaviour (not the function signature) and running the test.

For a change to what the tool measures or reports, also:
- run `wtf-perf cpu -s 15` on a real machine and compare the headline with Task Manager over the same seconds;
- report `reconciliation.unexplained` and `window.self_cost_pct` from `wtf-perf cpu -s 15 --json`, before and after.

### What will be refused

A pull request is refused if it:
- writes, moves or deletes any file other than the two named above, or changes any system setting;
- reaches the network other than the AI backend the user named, or adds telemetry;
- polls WMI, starts a service, or leaves anything running after the command ends;
- runs code when a module is imported, or adds obfuscated or encoded code, or a binary;
- adds a test that can start a real sampling window longer than a second or a real AI call (stub the source or backend so it raises);
- adds a dependency, or changes the CI workflows or the release process, without discussing it in an issue first.

### Before you start

For anything larger than a small fix, open an issue first. Say what you want to change and how you will test it. Most work happens in `wtf_perf/lib/` (sampler, ledger, families, findings, rendering), `wtf_perf/platforms/` (the data sources), and `wtf_perf/tools/core/cpu/` (the command). Keep commits to one logical unit of work each, in the conventional commit format.

Each change also updates the [README](README.md) where users will see it, [Platform support](docs/platform-support.md) where a platform's coverage changes, and the [CHANGELOG](CHANGELOG.md) in plain language.

## Working with an AI agent

[AGENTS.md](AGENTS.md) is written for AI coding agents working in this repository. Point your agent at it.

## Code of Conduct

Be kind, and assume good faith. Maintainers may close pull requests that ignore the questions above, or that cannot be verified.
