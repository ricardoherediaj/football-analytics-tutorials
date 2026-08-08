"""Progressive pass & carry maps (blueprint: comet lines / dashed arrows + zone split)."""

from __future__ import annotations

import matplotlib.patches as patches

from .. import config
from .helpers import make_pitch, path_eff, style_ax


def _zone_split(df, y_col="y"):
    left = len(df[df[y_col] >= config.ZONE_TOP])
    mid = len(df[(df[y_col] >= config.ZONE_BOT) & (df[y_col] < config.ZONE_TOP)])
    right = len(df[df[y_col] < config.ZONE_BOT])
    return left, mid, right


def _draw_zone_counts(ax, counts, col):
    left, mid, right = counts
    total = left + mid + right
    pcts = [round(c / total * 100) if total else 0 for c in (left, mid, right)]
    bbox = dict(boxstyle="round,pad=0.3", edgecolor="None", facecolor=config.BG_COLOR, alpha=0.75)
    labels = [(right, pcts[2], 11.335), (mid, pcts[1], 34), (left, pcts[0], 56.675)]
    for count, pct, y in labels:
        ax.text(8, y, f"{count}\n({pct}%)", color=col, fontsize=24, va="center", ha="center", bbox=bbox)


def progressive_pass_map(ax, df, team_name, col, invert=False, home_name=None) -> dict:
    dfpro = df[
        (df["teamName"] == team_name)
        & (df["prog_pass"] >= config.PROGRESSIVE_DIST)
        & (~df["qualifiers"].str.contains("CornerTaken|Freekick", na=False))
        & (df["x"] >= config.PROGRESSIVE_START_X)
        & (df["outcomeType"] == "Successful")
    ]
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)
    if invert:
        ax.invert_xaxis()
        ax.invert_yaxis()

    pro_count = len(dfpro)
    left, mid, right = _zone_split(dfpro)
    ax.hlines(config.ZONE_TOP, xmin=0, xmax=105, colors=config.LINE_COLOR, linestyle="dashed", alpha=0.35)
    ax.hlines(config.ZONE_BOT, xmin=0, xmax=105, colors=config.LINE_COLOR, linestyle="dashed", alpha=0.35)
    _draw_zone_counts(ax, (left, mid, right), col)

    if pro_count:
        pitch.lines(dfpro.x, dfpro.y, dfpro.endX, dfpro.endY, lw=3.5, comet=True, color=col, ax=ax, alpha=0.5)
        pitch.scatter(dfpro.endX, dfpro.endY, s=35, edgecolor=col, linewidth=1, color=config.BG_COLOR, zorder=2, ax=ax)

    ax.set_title(f"{team_name}\n{pro_count} Progressive Passes", color=config.LINE_COLOR,
                 fontsize=25, fontweight="bold", path_effects=path_eff())
    return {
        "Team_Name": team_name,
        "Total_Progressive_Passes": pro_count,
        "Progressive_Passes_From_Left": left,
        "Progressive_Passes_From_Center": mid,
        "Progressive_Passes_From_Right": right,
    }


def progressive_carry_map(ax, df, team_name, col, invert=False, home_name=None) -> dict:
    dfpro = df[
        (df["teamName"] == team_name)
        & (df["prog_carry"] >= config.PROGRESSIVE_DIST)
        & (df["endX"] >= config.PROGRESSIVE_START_X)
    ]
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)
    if invert:
        ax.invert_xaxis()
        ax.invert_yaxis()

    pro_count = len(dfpro)
    left, mid, right = _zone_split(dfpro)
    ax.hlines(config.ZONE_TOP, xmin=0, xmax=105, colors=config.LINE_COLOR, linestyle="dashed", alpha=0.35)
    ax.hlines(config.ZONE_BOT, xmin=0, xmax=105, colors=config.LINE_COLOR, linestyle="dashed", alpha=0.35)
    _draw_zone_counts(ax, (left, mid, right), col)

    # Dashed arrows, clipped to the pitch so none point outside the field
    for _, row in dfpro.iterrows():
        arrow = patches.FancyArrowPatch(
            (row["x"], row["y"]), (row["endX"], row["endY"]), arrowstyle="->", color=col,
            zorder=4, mutation_scale=20, alpha=0.9, linewidth=2, linestyle="--",
        )
        ax.add_patch(arrow)

    ax.set_title(f"{team_name}\n{pro_count} Progressive Carries", color=config.LINE_COLOR,
                 fontsize=25, fontweight="bold", path_effects=path_eff())
    return {
        "Team_Name": team_name,
        "Total_Progressive_Carries": pro_count,
        "Progressive_Carries_From_Left": left,
        "Progressive_Carries_From_Center": mid,
        "Progressive_Carries_From_Right": right,
    }
