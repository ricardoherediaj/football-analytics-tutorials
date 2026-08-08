"""Match stats bar chart (blueprint: center-out normalized bars)."""

from __future__ import annotations

from .. import config
from ..core import stats as core_stats
from .helpers import path_eff_thin


def plot_match_stats(ax, df, home, away, hcol, acol) -> None:
    stats = core_stats.calculate_match_stats(df, home, away)
    titles = list(stats.keys())
    home_vals = [stats[k]["home"] for k in titles]
    away_vals = [stats[k]["away"] for k in titles]

    y_positions = [58 - i * 6 for i in range(len(titles))]
    start_x = 52.5

    def safe(v):
        return v if v is not None else 0

    home_norm = [-(safe(h) / (safe(h) + safe(a))) * 50 if safe(h) + safe(a) else 0
                 for h, a in zip(home_vals, away_vals)]
    away_norm = [(safe(a) / (safe(h) + safe(a))) * 50 if safe(h) + safe(a) else 0
                 for h, a in zip(home_vals, away_vals)]

    ax.barh(y_positions, home_norm, height=4, color=hcol, left=start_x)
    ax.barh(y_positions, away_norm, height=4, left=start_x, color=acol)

    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis="both", which="both", bottom=False, top=False, left=False, right=False)
    ax.set_xticks([])
    ax.set_yticks([])

    for y, title in zip(y_positions, titles):
        ax.text(52.5, y, title, color=config.BG_COLOR, fontsize=17, ha="center", va="center",
                fontweight="bold", path_effects=path_eff_thin())
    for y, h, a in zip(y_positions, home_vals, away_vals):
        ax.text(0, y, str(safe(h)), color=config.LINE_COLOR, fontsize=17, ha="left", va="center", fontweight="bold")
        ax.text(105, y, str(safe(a)), color=config.LINE_COLOR, fontsize=17, ha="right", va="center", fontweight="bold")

    ax.set_facecolor(config.BG_COLOR)
    ax.set_xlim(-0.5, 105.5)
    ax.set_ylim(-5, 68.5)
