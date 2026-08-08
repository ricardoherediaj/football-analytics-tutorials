"""Defensive block chart (blueprint: KDE heatmap + shirt-number nodes)."""

from __future__ import annotations

import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from .. import config
from .helpers import make_pitch, path_eff, style_ax


def get_defensive_action_df(df: pd.DataFrame) -> pd.DataFrame:
    mask = (
        ((df["type"] == "Aerial") & df["qualifiers"].str.contains("Defensive", na=False))
        | (df["type"] == "BallRecovery")
        | (df["type"] == "BlockedPass")
        | (df["type"] == "Challenge")
        | (df["type"] == "Clearance")
        | (df["type"] == "Error")
        | (df["type"] == "Foul")
        | (df["type"] == "Interception")
        | (df["type"] == "Tackle")
    )
    return df[mask].copy()


def get_da_count_df(team: str, defensive_actions_df: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    team_actions = defensive_actions_df[defensive_actions_df["teamName"] == team]
    avg = team_actions.groupby("playerId").agg({"x": ["median"], "y": ["median", "count"]})
    avg.columns = ["x", "y", "count"]
    avg = avg.merge(df[["playerId", "name", "shirtNo", "position", "isFirstEleven"]].drop_duplicates("playerId"),
                    on="playerId", how="left").set_index("playerId")
    return avg


def defensive_block(ax, average_locs_and_count_df, team_actions, team_name, col, away_name=None,
                    invert=False, home_name=None) -> dict:
    team_df = average_locs_and_count_df[average_locs_and_count_df["position"] != "GK"] if "position" in average_locs_and_count_df.columns else average_locs_and_count_df
    pitch = make_pitch(line_zorder=2)
    pitch.draw(ax=ax)
    style_ax(ax)

    MAX_MARKER_SIZE = 3500
    team_df = team_df.copy()
    if len(team_df):
        team_df["marker_size"] = team_df["count"] / team_df["count"].max() * MAX_MARKER_SIZE

    cmap = LinearSegmentedColormap.from_list("team", [config.BG_COLOR, col], N=500)

    # KDE heatmap of the team's defensive actions
    if len(team_df) and len(team_actions):
        pitch.kdeplot(team_actions["x"], team_actions["y"], ax=ax, fill=True, levels=5000,
                      thresh=0.02, cut=4, cmap=cmap, zorder=1)

    # Player nodes: circle = starter, square = sub; shirt number inside
    for _, row in team_df.iterrows():
        marker = "o" if row["isFirstEleven"] else "s"
        pitch.scatter(row["x"], row["y"], s=row["marker_size"] + 100, marker=marker,
                      color=config.BG_COLOR, edgecolor=config.LINE_COLOR, linewidth=1,
                      alpha=1, zorder=3, ax=ax)
    for _, row in team_df.iterrows():
        pitch.annotate(int(row["shirtNo"]), xy=(row.x, row.y), c=config.LINE_COLOR,
                       ha="center", va="center", size=14, ax=ax)

    # Defensive action height lines + compactness
    dah = round(team_df["x"].mean(), 2) if len(team_df) else 0
    dah_show = round(dah * 1.05, 2)
    ax.axvline(x=dah, color="gray", linestyle="--", alpha=0.75, linewidth=2)

    cbs = team_df[team_df["position"] == "DC"] if "position" in team_df.columns else pd.DataFrame()
    def_line_h = round(cbs["x"].median(), 2) if len(cbs) else dah
    ax.axvline(x=def_line_h, color="gray", linestyle="dotted", alpha=0.5, linewidth=2)

    forwards = team_df[team_df["isFirstEleven"] == 1].sort_values("x", ascending=False).head(2) if len(team_df) else pd.DataFrame()
    fwd_line_h = round(forwards["x"].mean(), 2) if len(forwards) else dah
    ax.axvline(x=fwd_line_h, color="gray", linestyle="dotted", alpha=0.5, linewidth=2)

    compactness = round((1 - ((fwd_line_h - def_line_h) / 105)) * 100, 2) if len(team_df) else 0

    if invert:
        ax.invert_xaxis()
        ax.invert_yaxis()
        ax.text(dah - 1, 73, f"{dah_show}m", fontsize=15, color=config.LINE_COLOR, ha="left", va="center")
    else:
        ax.text(dah - 1, -5, f"{dah_show}m", fontsize=15, color=config.LINE_COLOR, ha="right", va="center")

    if home_name and team_name == home_name:
        ax.text(105, -5, f"Compact:{compactness}%", fontsize=15, color=config.LINE_COLOR, ha="right", va="center")
        ax.text(2, 66, "circle = starter\nbox = sub", color="gray", size=12, ha="left", va="top")
        ax.set_title(f"{team_name}\nDefensive Block", color=config.LINE_COLOR, fontsize=25, fontweight="bold", path_effects=path_eff())
    else:
        ax.text(105, 73, f"Compact:{compactness}%", fontsize=15, color=config.LINE_COLOR, ha="left", va="center")
        ax.text(2, 2, "circle = starter\nbox = sub", color="gray", size=12, ha="right", va="top")
        ax.set_title(f"{team_name}\nDefensive Block", color=config.LINE_COLOR, fontsize=25, fontweight="bold", path_effects=path_eff())

    return {
        "Team_Name": team_name,
        "Average_Defensive_Action_Height": dah,
        "Forward_Line_Pressing_Height": fwd_line_h,
    }
