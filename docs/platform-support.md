# Platform support

What wtf-perf runs on today, what is tested where, and how the other platforms fit in. Like most DazzleTools, wtf-perf aims to be platform-agnostic over time; today it is focused on Windows, which is also the detailed platform.

| Platform | Status | Notes |
|---|---|---|
| Windows 10/11 (x64) | tested | the development platform; the full suite and live tests run here, and `wtf-perf cpu` samples |
| Linux | stub, suite tested | the full suite runs on Ubuntu in CI (live Windows tests skip themselves); `wtf-perf cpu` refuses with one line naming the missing source. Provider work: [#4](https://github.com/DazzleTools/wtf-perf/issues/4) |
| macOS | stub | `wtf-perf cpu` refuses with one line naming the missing source; not tested routinely |

Status words: **tested** means the suite runs there on every push; **stub** means the platform has a named provider set whose sources are not implemented yet, so the tool says what is missing instead of sampling; **unsupported** means a known gap, named in Notes.

## How platforms are organised

Everything operating-system-specific lives in `wtf_perf/platforms/`, one module per platform. A platform is a set of **providers**, one per kind of data; the ledger, families, findings and rendering never branch on the platform. A provider that cannot supply something returns nothing, and the report says it is missing.

`wtf-perf cpu --providers` lists the current platform's providers and whether each can run on this machine. `--platform NAME` picks a provider set (the detected platform by default). Naming another operating system's set cannot sample it -- every provider checks the host -- so the flag is for listing providers and, later, for alternative provider sets on one OS.

## Providers by platform

| Provider kind | Windows | Linux (stub) | macOS (stub) |
|---|---|---|---|
| `snapshot` -- every process and processor at one instant (required) | `NtQuerySystemInformation` classes 5 and 8: per-process kernel, user and cycle time, I/O operation counts; per-processor idle, DPC and interrupt time. No elevation needed | `/proc/<pid>/stat`, `/proc/<pid>/io` (root for other users), `/proc/stat` | `libproc` (`proc_pidinfo`), `host_processor_info` |
| `counters` -- system-wide rates | PDH: processor utility (Task Manager's headline), processor time, performance, interrupts, context switches, page faults, disk | `/proc/stat` irq and softirq, `/proc/vmstat`; no utility counter, so no speed-scaling uplift | `host_statistics64`; no utility counter |
| `command_line` -- for `--ai-detail full` | `NtQueryInformationProcess` class 60; other users' processes need elevation | `/proc/<pid>/cmdline` | `sysctl KERN_PROCARGS2` |
| `elevation` | `IsUserAnAdmin` | `os.geteuid() == 0` | `os.geteuid() == 0` |
| `exit_events` -- processes too short-lived to sample (planned) | kernel process-exit events, elevated only: [#3](https://github.com/DazzleTools/wtf-perf/issues/3) | -- | -- |

## Windows notes

- **No elevation needed** for the report. Elevation adds the command lines of other users' and protected processes (for `--ai-detail full`).
- **No WMI and no PowerShell.** The process table and counters are read through `ctypes` directly. Polling WMI's process class every 100 ms saturates WMI, which is why it is not used.
- **More than 64 logical processors** (more than one processor group) are not handled yet: the processor totals cover the calling thread's group only.
- **The x64 structure layout** of the kernel's process table is undocumented; a self-check flags the process data as unreliable if the per-process times stop adding up to the machine's capacity.

## Adding a platform

A port fills in one module in `wtf_perf/platforms/` and nothing else:

1. Implement a `snapshot` source with `processes()` and `cpus()`, in 100 ns units (see the `SnapshotSource` contract in `wtf_perf/lib/sampler.py`, including that pid 0 is reserved for the idle row).
2. Add `counters`, `command_line` and `elevation` providers where the platform can supply them; leave the rest as stubs with a note.
3. Test the parsers on recorded data, in the Linux CI job or its equivalent; no test may read live system data for more than a second.
4. Add the platform to the manifests' `platforms` list and to the table at the top of this page.
