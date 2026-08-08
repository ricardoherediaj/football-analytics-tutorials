"""Football Match Report — post-match team report from WhoScored + FotMob.

Two commands:

    football-match-report scrape <whoscored-url> --out ./data
    football-match-report render --data ./data --out ./report

Charts follow the Post-Match-Report-2.0 blueprint (Adnan Ahmed): UEFA pitch,
black background, shirt numbers inside player nodes, xT momentum, and a
2x4x3 grid of team-level charts.
"""

__version__ = "2.0.0"
