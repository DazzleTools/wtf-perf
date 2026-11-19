## In your own words

<!-- What does this change do, and why? Write it yourself; do not paste an AI summary. If you cannot explain a line, do not submit it. -->

## AI tools used

<!-- Name each tool or model and what it did (wrote code, wrote tests, suggested a design, reviewed). "None" is a fine answer. -->

## How you vetted it

- [ ] I read every changed line
- [ ] `python -m pytest -q` passes (paste the last line):
- [ ] Each new test fails without the change and passes with it (say how you checked):
- [ ] For a change to what is measured or reported: `wtf-perf cpu -s 15` compared with Task Manager, and `unexplained` / `self_cost_pct` from `--json` before and after:

## Type of change

- [ ] Bug fix
- [ ] New or changed measurement, finding or output
- [ ] Platform provider
- [ ] Documentation
- [ ] Other (say what):

## Checklist

- [ ] Read-only: nothing written except `~/.wtf-perf/config.json` (with `--ai-save`) and the `prompt-only` file; no system setting changed
- [ ] No network access other than the AI backend the user names, no telemetry, no WMI polling, nothing left running
- [ ] No code run at import, obfuscated code or binaries
- [ ] No test can start a real sampling window longer than a second or a real AI call
- [ ] Operating-system code only in `wtf_perf/platforms/`
- [ ] README, `docs/platform-support.md` and `CHANGELOG.md` updated in plain language, if users will see the change
