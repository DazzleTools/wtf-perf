"""Command-line entry point for wtf-perf (the `wtf-perf` command)."""

import argparse

from ._version import __app_name__, get_display_version


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=__app_name__, description="Why is my Windows PC busy? Accounts for every point of CPU: processes, short-lived processes, interrupts and speed scaling")
    parser.add_argument("--version", action="version", version=f"{__app_name__} {get_display_version()}")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    del args  # nothing to do yet: replace this with the tool's work
    print(f"{__app_name__} {get_display_version()}")
    return 0
