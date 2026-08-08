"""xT momentum chart (blueprint: avg xT per minute, goal/card markers)."""

from __future__ import annotations

import pandas as pd

from .. import config
from ..core import stats as core_stats


def momentum_data(df: pd.DataFrame, home: str, away: str) -> pd.DataFrame:
    """Average xT per minute; away team values negated so they plot below zero."""
    mdf = df.copy()
    mdf.loc[mdf["teamName"] == away, "end_zone_value_xT"] *= -1
    mdf = mdf.groupby("minute")["end_zone_value_xT"].mean().reset_index()
    mdf.columns = ["minute", "average_xT"]
    mdf["average_xT"] = mdf["average_xT"].fillna(0)
    return mdf


def _markers(df: pd.DataFrame, home: str, away: str) -> dict:
    def minute_list(team, types=None, qual=None):
        m = df["teamName"] == team
        if types:
            m &= df["type"].isin(types)
        if qual:
            m &= df["qualifiers"].str.contains(qual, na=False)
        return df[m]["minute"].tolist()

    return {
        "home_goals": minute_list(home, ["Goal"], "OwnGoal"),
        "away_goals": minute_list(away, ["Goal"], "OwnGoal"),
        "home_og": minute_list(home, ["Goal"]),
        "away_og": minute_list(away, ["Goal"]),
        "home_red": minute_list(home, qual="Red|SecondYellow"),
        "away_red": minute_list(away, qual="Red|SecondYellow"),
    }


def plot_momentum(ax, df, home, away, hcol, acol) -> list[dict]:
    Momentumdf = momentum_data(df, home, away)
    hxt = core_stats.total_xt(df, home, away)[home]
    axt = core_stats.total_xt(df, home, away)[away]

    colors = [hcol if x > 0 else acol for x in Momentumdf["average_xT"]]
    mk = _markers(df, home, away)

    highest = Momentumdf["average_xT"].max()
    lowest = Momentumdf["average_xT"].min()
    highest_minute = Momentumdf["minute"].max()

    ax.text(45 / 2, lowest, "First Half", color="gray", fontsize=20, alpha=0.25, va="center", ha="center")
    ax.text(45 + 45 / 2, lowest, "Second Half", color="gray", fontsize=20, alpha=0.25, va="center", ha="center")

    # Goal / red card markers on the extremes
    def scatter_goals(goal_list, y):
        for m in goal_list:
            ax.scatter(m, y, s=250, c="None", edgecolor="green", hatch="////", marker="o")

    scatter_goals(mk["home_goals"], highest)
    scatter_goals(mk["away_goals"], lowest)
    for m in mk["home_red"]:
        ax.scatter(m, highest, s=250, c="None", edgecolor="red", hatch="////", marker="s")
    for m in mk["away_red"]:
        ax.scatter(m, lowest, s=250, c="None", edgecolor="red", hatch="////", marker="s")

    ax.bar(Momentumdf["minute"], Momentumdf["average_xT"], color=colors)
    ax.set_xticks(range(0, len(Momentumdf["minute"]) + 1, 5))
    ax.axvline(45, color="gray", linewidth=2, linestyle="dotted")
    ax.set_facecolor(config.BG_COLOR)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis="both", which="both", length=0)
    ax.tick_params(axis="x", colors=config.LINE_COLOR)
    ax.tick_params(axis="y", colors=config.LINE_COLOR)
    ax.set_xlabel("Minute", color=config.LINE_COLOR, fontsize=20)
    ax.set_ylabel("Avg. xT per minute", color=config.LINE_COLOR, fontsize=20)
    ax.axhline(y=0, color=config.LINE_COLOR, alpha=1, linewidth=2)

    ax.text(highest_minute + 1, highest, f"{home}\nxT: {hxt}", color=hcol, fontsize=20, va="bottom", ha="left")
    ax.text(highest_minute + 1, lowest, f"{away}\nxT: {axt}", color=acol, fontsize=20, va="top", ha="left")
    ax.set_title("Match Momentum by xT", color=config.LINE_COLOR, fontsize=30, fontweight="bold")

    return [{"Team_Name": home, "xT": hxt}, {"Team_Name": away, "xT": axt}]
