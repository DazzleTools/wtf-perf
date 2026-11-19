# Roadmap

The living roadmap for wtf-perf lives in the repository's first issue, kept pinned: https://github.com/DazzleTools/wtf-perf/issues/1. Notes and quick ideas go to the second: https://github.com/DazzleTools/wtf-perf/issues/2.

This file points there so a reader of the tree finds the plan; the issue holds the detail and its history.

## Now

- 0.2.0: `wtf-perf cpu` accounts for every point of the CPU headline on Windows, with an AI summary and a per-platform provider seam.

## Next

- Exit-event source (`--exits`): account for processes too short-lived to sample -- [#3](https://github.com/DazzleTools/wtf-perf/issues/3)
- Linux snapshot provider from `/proc` -- [#4](https://github.com/DazzleTools/wtf-perf/issues/4)

## Later

- Watch mode (a rolling window instead of one sample)
- A memory view
- File-path drill-down for I/O (which files, not only how many operations)
- More than 64 logical processors (multiple processor groups)
