#!/usr/bin/env python3
"""Thin wrapper: scrape a match into a data bundle (see football-match-report package).

    python scrape_match.py "<whoscored-url>" [--out DIR] [--fotmob-id ID] [--no-browser]
"""
import sys
from pathlib import Path

# Works both installed (pip/uv) and cloned standalone (repo src/ on sys.path)
try:
    from football_match_report.cli import cmd_scrape
except ImportError:
    repo_src = Path(__file__).resolve().parents[3] / "src"
    if repo_src.exists():
        sys.path.insert(0, str(repo_src))
        from football_match_report.cli import cmd_scrape
    else:
        sys.exit("football-match-report package not found. Run: uv sync && uv run python -m football_match_report")


class _Args:
    def __init__(self, url, out, fotmob_id, no_browser):
        self.url = url
        self.out = out
        self.fotmob_id = fotmob_id
        self.no_browser = no_browser


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    url = sys.argv[1]
    out = "data"
    fotmob_id = None
    no_browser = False
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--out" and i + 1 < len(sys.argv):
            out = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--fotmob-id" and i + 1 < len(sys.argv):
            fotmob_id = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--no-browser":
            no_browser = True
            i += 1
        else:
            i += 1
    sys.exit(cmd_scrape(_Args(url, out, fotmob_id, no_browser)))
