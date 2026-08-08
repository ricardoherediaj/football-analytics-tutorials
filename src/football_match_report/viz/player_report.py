"""Player-level report assembly: Top Players dashboard (figure 3), per-player
dashboards (2x3 figures) and the merged player_stats.csv table.
"""

from __future__ import annotations

import pandas as pd
from matplotlib import pyplot as plt

from .. import config
from ..core import player_stats as core_player
from . import player_individual as pind
from . import player_top as ptop
from . import report as report_viz


def save_player_reports(data_dir, out_dir, players: list[str] | None = None) -> list:
    """Render the player-level reports for a scraped bundle.

    - ``match_report_3.png`` — Top Players dashboard (4x3).
    - ``players/<player>.png`` — one 2x3 dashboard per player
      (all starters by default, or the names in ``players``).
    - ``player_stats.csv`` — merged per-player stat table.

    Returns the list of written paths.
    """
    df, home, away, hcol, acol, meta, matchdict, fotmob_xg = report_viz.load_report_data(data_dir)
    shots_path = data_dir / "shots.csv"
    shots_df = pd.read_csv(shots_path) if shots_path.exists() else None

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list = []

    # Figure 3: Top Players dashboard
    fig3 = ptop.build_top_players_figure(df, home, away, hcol, acol, meta)
    p3 = out_dir / "match_report_3.png"
    fig3.savefig(p3, bbox_inches="tight", facecolor=config.BG_COLOR)
    plt.close(fig3)
    written.append(p3)

    # Per-player stat table
    table = core_player.player_stats_table(df, shots_df)
    stats_csv = out_dir / "player_stats.csv"
    table.to_csv(stats_csv, index=False)
    written.append(stats_csv)

    # Per-player dashboards
    if players is None:
        starters = df[df["isFirstEleven"] == True].dropna(subset=["name"])  # noqa: E712
        players = sorted(starters["name"].dropna().unique().tolist())
    players_dir = out_dir / "players"
    players_dir.mkdir(parents=True, exist_ok=True)

    team_of = df.dropna(subset=["name"]).drop_duplicates("name").set_index("name")["teamName"]
    for pname in players:
        team = team_of.get(pname, "")
        col = hcol if team == home else acol
        fig = pind.build_individual_figure(df, shots_df, pname, team, col, meta)
        p = players_dir / f"{core_player.slugify(pname)}.png"
        fig.savefig(p, bbox_inches="tight", facecolor=config.BG_COLOR)
        plt.close(fig)
        written.append(p)

    return written
