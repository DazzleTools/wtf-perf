"""Tests for wtf_perf.lib.counters.

The PDH layer is replaced by a fake for every test except one bounded,
read-only live check.
"""
import os
import sys

import pytest

from wtf_perf.lib.counters import COUNTERS, CounterWindow


class FakePdh:
    """Scripted PDH: per-path values for the second collection; paths in
    `refuse` cannot be added; `unreadable` paths add but never read."""

    def __init__(self, values, refuse=(), unreadable=(), collect_ok=(True, True)):
        self.values = values
        self.refuse = set(refuse)
        self.unreadable = set(unreadable)
        self.collect_ok = list(collect_ok)
        self.collects = 0
        self.closed = False

    def add(self, path):
        return None if path in self.refuse else path

    def collect(self):
        self.collects += 1
        return self.collect_ok[min(self.collects - 1, len(self.collect_ok) - 1)]

    def value(self, handle):
        return None if handle in self.unreadable else self.values.get(handle)

    def close(self):
        self.closed = True


def _window(fake):
    w = CounterWindow(backend=fake)
    w.start()
    return w.finish()


def test_every_counter_is_read_by_its_name():
    fake = FakePdh({path: float(i) for i, path in enumerate(COUNTERS.values())})
    values = _window(fake)
    assert values == {name: float(i) for i, name in enumerate(COUNTERS)}
    assert fake.collects == 2 and fake.closed


def test_a_counter_that_cannot_be_added_or_read_is_absent_not_an_error():
    """One missing counter never costs the others."""
    utility, disk = COUNTERS["utility"], COUNTERS["disk_idle"]
    values = _window(FakePdh({p: 1.0 for p in COUNTERS.values()}, refuse={utility}, unreadable={disk}))
    assert values["utility"] is None and values["disk_idle"] is None
    assert all(v == 1.0 for k, v in values.items() if k not in ("utility", "disk_idle"))


@pytest.mark.parametrize("collect_ok", [(False, True), (True, False)], ids=["first-fails", "second-fails"])
def test_a_failed_collection_leaves_every_value_absent(collect_ok):
    values = _window(FakePdh({p: 3.0 for p in COUNTERS.values()}, collect_ok=collect_ok))
    assert all(v is None for v in values.values())


@pytest.mark.skipif(sys.platform != "win32", reason="reads Windows performance counters")
def test_live_counters_read_plausible_values():
    """Read-only, about 0.3 s: utility and processor time are present and in range."""
    import time

    from wtf_perf.platforms.windows import counter_backend

    w = CounterWindow(backend=counter_backend())
    w.start()
    time.sleep(0.3)
    values = w.finish()
    assert values["processor_time"] is not None and 0 <= values["processor_time"] <= 100
    assert values["utility"] is not None and 0 <= values["utility"] <= 100 * os.cpu_count()
    assert values["disk_idle"] is None or 0 <= values["disk_idle"] <= 100
