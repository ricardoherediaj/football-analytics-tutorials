"""Passing network chart (blueprint: fixed-size nodes, shirt numbers, line heights)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.colors import to_rgba

from .. import config
from .helpers import make_pitch, path_eff, style_ax


def get_passes_df(df: pd.DataFrame) -> pd.DataFrame:
    df1 = df[~df["type"].str.contains("SubstitutionOn|FormationChange|FormationSet|Card", na=False)]
    df1 = df1.copy()
    df1["receiver"] = df1["playerId"].shift(-1)
    passes_ids = df1.index[df1["type"] == "Pass"]
    return df1.loc[passes_ids, ["index", "x", "y", "endX", "endY", "teamName",
                                "playerId", "receiver", "type", "outcomeType", "pass_or_carry_angle"]]


def get_passes_between_df(team: str, passes_df: pd.DataFrame, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    passes_df = passes_df[passes_df["teamName"] == team]
    dfteam = df[(df["teamName"] == team) & (~df["type"].str.contains("SubstitutionOn|FormationChange|FormationSet|Card", na=False))]

    avg = dfteam.groupby("playerId").agg({"x": ["median"], "y": ["median", "count"]})
    avg.columns = ["pass_avg_x", "pass_avg_y", "count"]
    avg = avg.merge(df[["playerId", "name", "shirtNo", "position", "isFirstEleven"]].drop_duplicates("playerId"),
                    on="playerId", how="left").set_index("playerId")

    pp = passes_df.loc[:, ["index", "playerId", "receiver", "teamName"]]
    pp["pos_max"] = pp[["playerId", "receiver"]].max(axis="columns")
    pp["pos_min"] = pp[["playerId", "receiver"]].min(axis="columns")
    between = pp.groupby(["pos_min", "pos_max"]).index.count().reset_index()
    between.rename({"index": "pass_count"}, axis="columns", inplace=True)
    between = between.merge(avg, left_on="pos_min", right_index=True)
    between = between.merge(avg, left_on="pos_max", right_index=True, suffixes=["", "_end"])
    return between, avg


def pass_network_visualization(ax, passes_between_df, avg_locs, col, team_name, away_name,
                               invert=False, home_name=None, passes_df=None) -> dict:
    MAX_LINE_WIDTH = 15
    MIN_TRANSPARENCY = 0.05
    MAX_TRANSPARENCY = 0.85

    passes_between_df = passes_between_df.copy()
    passes_between_df["width"] = passes_between_df.pass_count / passes_between_df.pass_count.max() * MAX_LINE_WIDTH

    color = np.array(to_rgba(col))
    color = np.tile(color, (len(passes_between_df), 1))
    c_transparency = passes_between_df.pass_count / passes_between_df.pass_count.max()
    c_transparency = c_transparency * (MAX_TRANSPARENCY - MIN_TRANSPARENCY) + MIN_TRANSPARENCY
    color[:, 3] = c_transparency

    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)

    pitch.lines(passes_between_df.pass_avg_x, passes_between_df.pass_avg_y,
                passes_between_df.pass_avg_x_end, passes_between_df.pass_avg_y_end,
                lw=passes_between_df.width, color=color, zorder=1, ax=ax)

    # Nodes: circle = starter, square = sub, fixed size, shirt number inside
    for _, row in avg_locs.iterrows():
        marker = "o" if row["isFirstEleven"] else "s"
        alpha = 1.0 if row["isFirstEleven"] else 0.75
        pitch.scatter(row["pass_avg_x"], row["pass_avg_y"], s=1000, marker=marker,
                      color=config.BG_COLOR, edgecolor=config.LINE_COLOR, linewidth=2,
                      alpha=alpha, ax=ax)
    for _, row in avg_locs.iterrows():
        pitch.annotate(int(row["shirtNo"]), xy=(row.pass_avg_x, row.pass_avg_y), c=col,
                       ha="center", va="center", size=18, ax=ax)

    # Line heights: median pass x (solid), CB line (dotted), forward line (dotted)
    avgph = round(avg_locs["pass_avg_x"].median(), 2)
    ax.axvline(x=avgph, color="gray", linestyle="--", alpha=0.75, linewidth=2)

    cbs = avg_locs[avg_locs["position"] == "DC"]
    def_line_h = round(cbs["pass_avg_x"].median(), 2) if len(cbs) else avgph
    ax.axvline(x=def_line_h, color="gray", linestyle="dotted", alpha=0.5, linewidth=2)

    forwards = avg_locs[avg_locs["isFirstEleven"] == 1].sort_values("pass_avg_x", ascending=False).head(2)
    fwd_line_h = round(forwards["pass_avg_x"].mean(), 2) if len(forwards) else avgph
    ax.axvline(x=fwd_line_h, color="gray", linestyle="dotted", alpha=0.5, linewidth=2)

    ax.fill([def_line_h, fwd_line_h, fwd_line_h, def_line_h], [0, 0, 68, 68], col, alpha=0.1)

    # Verticality from the raw pass rows (angle data)
    verticality = 0.0
    if passes_df is not None and len(passes_df):
        team_pass = passes_df[passes_df["teamName"] == team_name]
        ang = team_pass["pass_or_carry_angle"].abs()
        ang = ang[(ang >= 0) & (ang <= 90)]
        if len(ang):
            verticality = round((1 - ang.median() / 90) * 100, 2)

    top_combo = passes_between_df.sort_values("pass_count", ascending=False).head(1)
    most_from = top_combo["name"].iloc[0] if len(top_combo) else "-"
    most_to = top_combo["name_end"].iloc[0] if len(top_combo) else "-"
    most_count = int(top_combo["pass_count"].iloc[0]) if len(top_combo) else 0

    if invert:
        ax.invert_xaxis()
        ax.invert_yaxis()
        ax.text(avgph - 1, 73, f"{avgph}m", fontsize=15, color=config.LINE_COLOR, ha="left")
        ax.text(105, 73, f"verticality: {verticality}%", fontsize=15, color=config.LINE_COLOR, ha="left")
    else:
        ax.text(avgph - 1, -5, f"{avgph}m", fontsize=15, color=config.LINE_COLOR, ha="right")
        ax.text(105, -5, f"verticality: {verticality}%", fontsize=15, color=config.LINE_COLOR, ha="right")

    if home_name and team_name == home_name:
        ax.text(2, 66, "circle = starter\nbox = sub", color=col, size=12, ha="left", va="top")
        ax.set_title(f"{team_name}\nPassing Network", color=config.LINE_COLOR, size=25, fontweight="bold", path_effects=path_eff())
    else:
        ax.text(2, 2, "circle = starter\nbox = sub", color=col, size=12, ha="right", va="top")
        ax.set_title(f"{team_name}\nPassing Network", color=config.LINE_COLOR, size=25, fontweight="bold", path_effects=path_eff())

    return {
        "Team_Name": team_name,
        "Defense_Line_Height": def_line_h,
        "Vericality_%": verticality,
        "Most_pass_combination_from": most_from,
        "Most_pass_combination_to": most_to,
        "Most_passes_in_combination": most_count,
    }

