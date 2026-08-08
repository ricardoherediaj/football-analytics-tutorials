"""Football Match Report — post-match team report from WhoScored + FotMob.

Two commands:

    football-match-report scrape <whoscored-url> --out ./data
    football-match-report render --data ./data --out ./report

Charts follow the Post-Match-Report-2.0 blueprint (Adnan Ahmed): UEFA pitch,
black background, shirt numbers inside player nodes, xT momentum, and a
2x4x3 grid of team-level charts.
"""

__version__ = "2.0.0"

# pandas >=3.0 has Copy-on-Write always on; older 2.x needs it enabled to avoid
# chained-assignment warnings on plain column writes.
import pandas as _pd

if _pd.__version__.startswith("2."):
    _pd.set_option("mode.copy_on_write", True)
