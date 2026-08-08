#!/usr/bin/env python3
"""Thin wrapper: render a scraped bundle into report PNGs (football-match-report package).

    python render_report.py --data ./data --out ./report
"""
import sys
from pathlib import Path

try:
    from football_match_report.cli import cmd_render
except ImportError:
    repo_src = Path(__file__).resolve().parents[3] / "src"
    if repo_src.exists():
        sys.path.insert(0, str(repo_src))
        from football_match_report.cli import cmd_render
    else:
        sys.exit("football-match-report package not found. Run: uv sync && uv run python -m football_match_report")


class _Args:
    def __init__(self, data, out):
        self.data = data
        self.out = out


if __name__ == "__main__":
    data = "data"
    out = "report"
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--data" and i + 1 < len(args):
            data = args[i + 1]
            i += 2
        elif args[i] == "--out" and i + 1 < len(args):
            out = args[i + 1]
            i += 2
        elif args[i] in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        else:
            i += 1
    sys.exit(cmd_render(_Args(data, out)))
