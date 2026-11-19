# Mutation survivors triaged as equivalent or don't-care

Entries are bound to the file's `git hash-object` (first 12). When the hash no longer matches, every entry under that heading is stale and must be re-triaged before reuse.

## wtf_perf/cli.py @ 86dd5e2b706b

| Original -> mutated | Label | Reason | Date | Mode |
|---|---|---|---|---|
| `{e['name']:<{label_w}}` -> `{e['name']:>{label_w}}` | equivalent (conditional) | With one registered tool, `label_w` equals the name's length, so left and right alignment print the same row. Reopen when the kit has a second tool of a different name length. | 2026-11-18 | 1 (fresh subagent) |
| `version_info=(get_display_version(), __version__)` -> swapped | ~~equivalent (conditional)~~ killed | Was equivalent while both strings read `0.1.0`. Reopened the same day when the 0.1.1 bump wrote build metadata into `__version__`; now killed by `test_version_shows_the_display_version_then_the_build_string` (shown red under the mutant). | 2026-11-18 | 1 (fresh subagent) |
| `manifest=".wtf-perf.json"` -> `"wtf-perf.json"` | equivalent (conditional) | The kit file's own `"manifest": ".wtf-perf.json"` field shadows the engine's setting. Measured: with that kit field removed, the mutant prints "No tools found." Reopen if the kit stops declaring its manifest. | 2026-11-18 | 1 (fresh subagent) |
| `show_mode="default"` -> `"all"` | equivalent (conditional) | No tool is hidden, so both modes list the same rows. Reopen when a hidden or internal tool is added. | 2026-11-18 | 1 (fresh subagent) |
| `kit_filter=None` -> `"core"` | equivalent (conditional) | There is one kit, `core`, so filtering to it lists everything. Reopen when a second kit exists. | 2026-11-18 | 1 (fresh subagent) |
| `if len(desc) > avail:` -> `>=` | don't-care | Differs only for a description exactly `avail` characters long, where it would add an ellipsis one character early. Cosmetic; not worth a width-tuned fixture. | 2026-11-18 | 1 (fresh subagent) |
