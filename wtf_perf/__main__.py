"""Allow running as: python -m wtf_perf"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
