"""Shot map (blueprint) + goalpost (goalkeeper) charts."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config
from ..core import stats as core_stats
from .helpers import make_pitch, path_eff, style_ax


def shot_map(ax, df, home, away, hcol, acol, fotmob_xg: dict | None = None) -> list[dict]:
    """Shot map with football markers for goals, hatched saves, big chances."""
    mask = df["type"].isin(config.SHOT_TYPES)
    Shotsdf = df[mask].copy()
    hShotsdf = Shotsdf[Shotsdf["teamName"] == home]
    aShotsdf = Shotsdf[Shotsdf["teamName"] == away]

    # Big chance / own goal flags
    hShotsdf = hShotsdf.copy()
    aShotsdf = aShotsdf.copy()
    hShotsdf["is_big"] = hShotsdf["qualifiers"].str.contains("BigChance", na=False)
    aShotsdf["is_big"] = aShotsdf["qualifiers"].str.contains("BigChance", na=False)
    hShotsdf["is_og"] = hShotsdf["qualifiers"].str.contains("OwnGoal", na=False)
    aShotsdf["is_og"] = aShotsdf["qualifiers"].str.contains("OwnGoal", na=False)

    stats = core_stats.shot_stats_from_events(df, home, away)
    # Enrich with FotMob xG when available
    if fotmob_xg:
        for team, xg in fotmob_xg.items():
            if team in stats:
                stats[team]["xg"] = round(xg.get("xg", 0), 2)
                stats[team]["xgot"] = round(xg.get("xgot", 0), 2)
                stats[team]["xg_per_shot"] = (
                    round(xg.get("xg", 0) / stats[team]["shots"], 2) if stats[team]["shots"] else 0
                )

    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)

    def scatter_team(team_df, col, flip):
        if len(team_df) == 0:
            return
        x, y = (105 - team_df["x"], 68 - team_df["y"]) if flip else (team_df["x"], team_df["y"])
        goals = team_df[team_df["type"] == "Goal"]
        posts = team_df[team_df["type"] == "ShotOnPost"]
        saved = team_df[team_df["type"] == "SavedShot"]
        missed = team_df[team_df["type"] == "MissedShots"]

        # normal shots
        pitch.scatter(x[missed.index], y[missed.index], s=200, edgecolors=col, c="None", marker="o", ax=ax)
        pitch.scatter(x[saved.index], y[saved.index], s=200, edgecolors=col, c="None", hatch="///////", marker="o", ax=ax)
        pitch.scatter(x[posts.index], y[posts.index], s=200, edgecolors=col, c=col, marker="o", ax=ax)
        pitch.scatter(x[goals.index], y[goals.index], s=350, edgecolors="green", linewidths=0.6,
                      c="None", marker="football", zorder=3, ax=ax)

        # big chances (bigger markers)
        big = team_df[team_df["is_big"] & (team_df["type"] != "Goal")]
        if len(big):
            pitch.scatter(x[big.index], y[big.index], s=500, edgecolors=col,
                          c="None", marker="o", ax=ax)
        big_goals = team_df[team_df["is_big"] & (team_df["type"] == "Goal")]
        if len(big_goals):
            pitch.scatter(x[big_goals.index], y[big_goals.index], s=650, edgecolors="green",
                          linewidths=0.6, c="None", marker="football", ax=ax)

    scatter_team(hShotsdf, hcol, flip=True)   # home attacks left goal
    scatter_team(aShotsdf, acol, flip=False)  # away attacks right goal

    # ---- stats bar strip ----
    titles = ["Goals", "xG", "xGOT", "Shots", "On Target", "BigChance", "BigC.Miss", "xG/Shot", "Avg.Dist."]
    y_positions = [62 - i * 7 for i in range(9)]
    h_vals = [stats[home].get("goals", 0), stats[home].get("xg", 0), stats[home].get("xgot", 0),
              stats[home].get("shots", 0), stats[home].get("on_target", 0),
              stats[home].get("big_chances", 0), stats[home].get("big_chances_missed", 0),
              stats[home].get("xg_per_shot", 0), stats[home].get("avg_distance", 0)]
    a_vals = [stats[away].get("goals", 0), stats[away].get("xg", 0), stats[away].get("xgot", 0),
              stats[away].get("shots", 0), stats[away].get("on_target", 0),
              stats[away].get("big_chances", 0), stats[away].get("big_chances_missed", 0),
              stats[away].get("xg_per_shot", 0), stats[away].get("avg_distance", 0)]

    def norm(vals_h, vals_a, i):
        h, a = vals_h[i], vals_a[i]
        if h + a == 0:
            return 10.0, 10.0
        return (h / (h + a)) * 20, (a / (h + a)) * 20

    start_x = 42.5
    for i, y in enumerate(y_positions):
        hw, aw = norm(h_vals, a_vals, i)
        ax.barh(y, hw, height=5, color=hcol, left=start_x - hw)
        ax.barh(y, aw, height=5, left=start_x, color=acol)

    for i, (y, title) in enumerate(zip(y_positions, titles)):
        # white text with black outline so labels stay readable over team-color bars
        ax.text(52.5, y, title, color=config.LINE_COLOR, fontsize=17, ha="center", va="center",
                fontweight="bold", path_effects=path_eff())
        ax.text(41.5, y, str(h_vals[i]), color=config.LINE_COLOR, fontsize=17,
                ha="right", va="center", fontweight="bold", path_effects=path_eff())
        ax.text(63.5, y, str(a_vals[i]), color=config.LINE_COLOR, fontsize=17,
                ha="left", va="center", fontweight="bold", path_effects=path_eff())

    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis="both", which="both", bottom=False, top=False, left=False, right=False)
    ax.set_xticks([])
    ax.set_yticks([])

    ax.text(0, 70, f"{home}\n<---shots", color=hcol, size=25, ha="left", fontweight="bold")
    ax.text(105, 70, f"{away}\nshots--->", color=acol, size=25, ha="right", fontweight="bold")

    return [
        {"Team_Name": home, **stats[home]},
        {"Team_Name": away, **stats[away]},
    ]


def jitter_goal_positions(out: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """Spread near-duplicate goal-mouth positions by a tiny seeded jitter.

    WhoScored uses goalMouthZ=19.0 as a "height not tracked" placeholder, so
    several shots can map to identical (gx, gy) and stack perfectly on top of
    each other in the goal view. Rows that share a rounded position get a
    uniform jitter of +/-1.2 (goal-mouth units) so every shot stays visible.
    """
    rng = np.random.default_rng(seed)
    key = out["gx"].round(0).astype(str) + "|" + out["gy"].round(0).astype(str)
    for _, sub in out.groupby(key.values):
        if len(sub) > 1:
            out.loc[sub.index, "gx"] += rng.uniform(-1.2, 1.2, len(sub))
            out.loc[sub.index, "gy"] += rng.uniform(-1.2, 1.2, len(sub))
    return out


def goalpost(ax, df, home, away, hcol, acol) -> list[dict]:
    """Goal view: where each team's shots went against the keeper.

    WhoScored goalMouthY/goalMouthZ are 0-100 percentages of the goal mouth
    (50 = center of goal; 0/100 = posts; Z 0 = ground, 100 = crossbar).
    They are normalized into the two goal frames: bottom = home GK facing
    away shots, top = away GK facing home shots.
    """
    mask = df["type"].isin(config.SHOT_TYPES)
    Shotsdf = df[mask].copy()
    hShotsdf = Shotsdf[Shotsdf["teamName"] == home].copy()
    aShotsdf = Shotsdf[Shotsdf["teamName"] == away].copy()

    def norm_goal(df_side, base_y):
        out = pd.DataFrame(index=df_side.index)
        out["gx"] = 7.5 + np.clip(pd.to_numeric(df_side["goalMouthY"], errors="coerce") / 100, 0, 1) * 90
        out["gy"] = base_y + np.clip(pd.to_numeric(df_side["goalMouthZ"], errors="coerce") / 100, 0, 1) * 30
        out = out.dropna()
        # WhoScored uses Z=19.0 as a "height not tracked" placeholder, so several
        # shots can map to identical positions -> spread them with seeded jitter.
        return jitter_goal_positions(out)

    h_norm = norm_goal(hShotsdf, 0.0)    # home shots -> bottom frame (away GK)
    a_norm = norm_goal(aShotsdf, 38.0)   # away shots -> top frame (home GK)

    pitch = make_pitch(line_color=config.BG_COLOR, pitch_color=config.BG_COLOR)
    pitch.draw(ax=ax)
    style_ax(ax)

    # goal frames (invisible pitch, drawn as plain lines)
    for y0 in (0.0, 38.0):
        ax.plot([7.5, 7.5], [y0, y0 + 30], color=config.LINE_COLOR, linewidth=5)
        ax.plot([7.5, 97.5], [y0 + 30, y0 + 30], color=config.LINE_COLOR, linewidth=5)
        ax.plot([97.5, 97.5], [y0 + 30, y0], color=config.LINE_COLOR, linewidth=5)
        ax.plot([0, 105], [y0, y0], color=config.LINE_COLOR, linewidth=3)
        for gy in np.arange(y0, y0 + 30, 6):
            ax.plot([7.5, 97.5], [gy, gy], color=config.LINE_COLOR, linewidth=2, alpha=0.2)
        for gx in np.arange(7.5, 97.5, 9):
            ax.plot([gx, gx], [y0, y0 + 30], color=config.LINE_COLOR, linewidth=2, alpha=0.2)

    def scatter_gk(norm_df, team_df, edge_col):
        if len(norm_df) == 0:
            return
        for sub_type, marker, edge, hatch in (
            ("SavedShot", "o", edge_col, "/////"),
            ("Goal", "football", "green", None),
            ("ShotOnPost", "o", "orange", "/////"),
        ):
            idx = norm_df.index.intersection(team_df.index[team_df["type"] == sub_type])
            if len(idx):
                pitch.scatter(norm_df.loc[idx, "gx"], norm_df.loc[idx, "gy"],
                              marker=marker, c=config.BG_COLOR, zorder=3, edgecolors=edge,
                              hatch=hatch, s=350, ax=ax)

    scatter_gk(h_norm, hShotsdf, acol)   # home shots -> away GK (bottom frame)
    scatter_gk(a_norm, aShotsdf, hcol)   # away shots -> home GK (top frame)

    ax.text(52.5, 70, f"{home} GK saves", color=hcol, fontsize=30, ha="center", fontweight="bold")
    ax.text(52.5, -2, f"{away} GK saves", color=acol, fontsize=30, ha="center", va="top", fontweight="bold")

    return []
