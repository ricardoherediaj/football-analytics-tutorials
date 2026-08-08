"""Top Players dashboard (blueprint: pass maps, passes received, defender actions,
GK pass maps + leaderboard bar charts). Black theme, team colors, 4x3 figure 3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.patches import FancyArrowPatch

from .. import config
from ..core import events as core_events
from ..core import player_stats as core_player
from .helpers import make_pitch, path_eff, path_eff_thin, style_ax
from .report import _score_str

GREEN = "#00b300"


def _stats_block(ax, rows, x, y, size=15, spacing=3.4, ha="left", va="top"):
    """Multi-line colored stats block (blueprint highlight-text replacement)."""
    for i, (text, color) in enumerate(rows):
        ax.text(x, y - i * spacing, text, color=color or config.LINE_COLOR, fontsize=size,
                ha=ha, va=va, path_effects=path_eff_thin())


def _pick_forward(df: pd.DataFrame, team: str) -> str:
    """Best pass-receiving target: starter FW with most touches, else top receiver."""
    starters = df[(df["teamName"] == team) & (df["isFirstEleven"] == True)]  # noqa: E712
    fw = starters[starters["position"] == "FW"]
    if len(fw):
        counts = fw.groupby("name").size()
        return counts.idxmax()
    received = df[(df["type"] == "Pass") & (df["outcomeType"] == "Successful")]
    received = received.assign(receiver=received["name"].shift(-1))
    received = received[received["receiver"].isin(starters["name"])]
    counts = received["receiver"].value_counts()
    return counts.idxmax() if len(counts) else ""


# --------------------------------------------------------------------------- #
# Panel charts
# --------------------------------------------------------------------------- #

def top_passmap(ax, df, team, col, top_df, invert=False) -> dict:
    """Pass map of the top ball progressor: all passes + progressive/key/assist
    lines, progressive carries as dashed arrows."""
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)

    stats: dict = {}
    if len(top_df):
        pname = top_df.iloc[0]["name"]
        acc = df[(df["name"] == pname) & (df["type"] == "Pass") & (df["outcomeType"] == "Successful")]
        open_play = ~acc["qualifiers"].str.contains("CornerTaken|Freekick", na=False)
        pro = acc[(acc["prog_pass"] >= config.PROGRESSIVE_DIST) & (acc["x"] >= config.PROGRESSIVE_START_X) & open_play]
        pro_carry = df[
            (df["name"] == pname) & (df["prog_carry"] >= config.PROGRESSIVE_DIST)
            & (df["endX"] >= config.PROGRESSIVE_START_X)
        ]
        key = acc[acc["qualifiers"].str.contains("KeyPass", na=False)]
        assist = acc[acc["qualifiers"].str.contains("IntentionalGoalAssist", na=False)]

        pitch.lines(acc.x, acc.y, acc.endX, acc.endY, color=config.LINE_COLOR, lw=2,
                    alpha=0.15, comet=True, zorder=2, ax=ax)
        pitch.lines(pro.x, pro.y, pro.endX, pro.endY, color=col, lw=3, alpha=1,
                    comet=True, zorder=3, ax=ax)
        pitch.lines(key.x, key.y, key.endX, key.endY, color=config.VIOLET, lw=4,
                    alpha=1, comet=True, zorder=4, ax=ax)
        pitch.lines(assist.x, assist.y, assist.endX, assist.endY, color=GREEN, lw=4,
                    alpha=1, comet=True, zorder=5, ax=ax)

        ax.scatter(acc.endX, acc.endY, s=30, color=config.BG_COLOR, edgecolor="gray", zorder=2)
        ax.scatter(pro.endX, pro.endY, s=40, color=config.BG_COLOR, edgecolor=col, zorder=3)
        ax.scatter(key.endX, key.endY, s=50, color=config.BG_COLOR, edgecolor=config.VIOLET, zorder=4)
        ax.scatter(assist.endX, assist.endY, s=50, color=config.BG_COLOR, edgecolor=GREEN, zorder=5)

        for _, row in pro_carry.iterrows():
            ax.add_patch(FancyArrowPatch((row["x"], row["y"]), (row["endX"], row["endY"]),
                                         arrowstyle="->", color=col, zorder=4, mutation_scale=20,
                                         alpha=0.9, linewidth=2, linestyle="--"))

        stats = {"player": pname, "progressive_passes": len(pro),
                 "progressive_carries": len(pro_carry), "key_passes": len(key),
                 "assists": len(assist)}
        title = f"{core_events.short_name(pname)} PassMap"
        if invert:
            ax.text(0, 71, f"Prog. Pass: {len(pro)}    Prog. Carry: {len(pro_carry)}",
                    color=col, fontsize=15, ha="right", va="center")
            ax.text(105, 71, f"Key Pass: {len(key)}    Assist: {len(assist)}",
                    color=config.VIOLET, fontsize=15, ha="left", va="center",
                    path_effects=path_eff_thin())
        else:
            ax.text(0, -3, f"Prog. Pass: {len(pro)}    Prog. Carry: {len(pro_carry)}",
                    color=col, fontsize=15, ha="left", va="center")
            ax.text(105, -3, f"Key Pass: {len(key)}    Assist: {len(assist)}",
                    color=config.VIOLET, fontsize=15, ha="right", va="center",
                    path_effects=path_eff_thin())
    else:
        title = "Top Progressor PassMap"

    if invert:
        ax.invert_xaxis()
        ax.invert_yaxis()
    ax.set_title(title, color=col, fontsize=25, fontweight="bold", y=1.03,
                 path_effects=path_eff())
    return stats


def passes_received(ax, df, team, col, invert=False) -> dict:
    """Passes received by the team's center-forward (or top receiver)."""
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)

    target = _pick_forward(df, team)
    if not target:
        ax.set_title("Passes Received", color=col, fontsize=25, fontweight="bold", y=1.03,
                     path_effects=path_eff())
        return {}
    name_show = core_events.short_name(target)

    d = df[
        (df["type"] == "Pass") & (df["outcomeType"] == "Successful")
        & (df["name"].shift(-1) == target)
    ]
    key_recv = d[d["qualifiers"].str.contains("KeyPass", na=False)]
    assist_recv = d[d["qualifiers"].str.contains("IntentionalGoalAssist", na=False)]

    pitch.lines(d.x, d.y, d.endX, d.endY, lw=3, transparent=True, comet=True,
                color=col, ax=ax, alpha=0.5)
    pitch.lines(key_recv.x, key_recv.y, key_recv.endX, key_recv.endY, lw=4,
                transparent=True, comet=True, color=config.VIOLET, ax=ax, alpha=0.75)
    pitch.lines(assist_recv.x, assist_recv.y, assist_recv.endX, assist_recv.endY,
                lw=4, transparent=True, comet=True, color=GREEN, ax=ax, alpha=0.75)
    pitch.scatter(d.endX, d.endY, s=30, edgecolor=col, linewidth=1, color=config.BG_COLOR,
                  zorder=2, ax=ax)
    pitch.scatter(key_recv.endX, key_recv.endY, s=40, edgecolor=config.VIOLET,
                  linewidth=1.5, color=config.BG_COLOR, zorder=2, ax=ax)
    pitch.scatter(assist_recv.endX, assist_recv.endY, s=50, edgecolors=GREEN,
                  linewidths=1, marker="football", c=config.BG_COLOR, zorder=2, ax=ax)

    if len(d):
        avg_end_x = d["endX"].median()
        avg_end_y = d["endY"].median()
        ax.axvline(x=avg_end_x, color="gray", linestyle="--", alpha=0.6, linewidth=2)
        ax.axhline(y=avg_end_y, color="gray", linestyle="--", alpha=0.6, linewidth=2)
        passer_counts = d["name"].map(core_events.short_name).value_counts()
        most_from = f"{passer_counts.index[0]} ({int(passer_counts.iloc[0])})"
    else:
        most_from = "-"

    y = 71 if invert else -3
    _stats_block(ax, [
        (f"Passes Received: {len(d)} | Key Passes Received: {len(key_recv)} | Assists Received: {len(assist_recv)}", None),
        (f"Most Passes from: {most_from}", col),
    ], 52.5, y, size=15, ha="center", va="top" if not invert else "center")

    if invert:
        ax.invert_xaxis()
        ax.invert_yaxis()
    ax.set_title(f"{name_show} Passes Received", color=col, fontsize=25, fontweight="bold",
                 y=1.03, path_effects=path_eff())
    return {"target": target, "passes_received": len(d)}


def top_defender_actions(ax, df, team, col, top_df, invert=False) -> dict:
    """Defensive actions of the top defender (tackle/interception/recovery/
    clearance/foul/aerial markers + legend)."""
    pitch = make_pitch(line_zorder=2)
    pitch.draw(ax=ax)
    style_ax(ax)

    def _scatter(x, y, marker, filled, size=250):
        pitch.scatter(x, y, s=size, c=col if filled else "None", lw=2.5,
                      edgecolor=col, marker=marker, hatch="/////", ax=ax)

    stats: dict = {}
    if len(top_df):
        pname = top_df.iloc[0]["name"]
        d = df[df["name"] == pname]
        tk = d[d["type"] == "Tackle"]
        intc = d[(d["type"] == "Interception") | (d["type"] == "BlockedPass")]
        br = d[d["type"] == "BallRecovery"]
        cl = d[d["type"] == "Clearance"]
        fl = d[d["type"] == "Foul"]
        ar = d[(d["type"] == "Aerial") & d["qualifiers"].str.contains("Defensive", na=False)]

        _scatter(tk.x, tk.y, "+", True)
        _scatter(intc.x, intc.y, "s", False)
        _scatter(br.x, br.y, "o", False)
        _scatter(cl.x, cl.y, "d", False)
        _scatter(fl.x, fl.y, "x", True)
        _scatter(ar.x, ar.y, "^", False)

        # legend markers + counts along the bottom/top edge
        y0 = -4 if not invert else 71
        _scatter(np.array([2.0]), np.array([y0]), "+", True, size=150)
        _scatter(np.array([2.0]), np.array([y0 - 6]), "s", False, size=150)
        _scatter(np.array([41.0]), np.array([y0]), "o", False, size=150)
        _scatter(np.array([41.0]), np.array([y0 - 6]), "d", False, size=150)
        _scatter(np.array([103.0]), np.array([y0]), "x", True, size=150)
        _scatter(np.array([103.0]), np.array([y0 - 6]), "^", False, size=150)

        ax.text(5, y0, f"Tackle: {len(tk)}\n\nInterception: {len(intc)}",
                color=col, ha="left", va="top", fontsize=13)
        ax.text(43, y0, f"BallRecovery: {len(br)}\n\nClearance: {len(cl)}",
                color=col, ha="left", va="top", fontsize=13)
        ax.text(100, y0, f"{len(fl)} Fouls\n\n{len(ar)} Aerials",
                color=col, ha="right", va="top", fontsize=13)

        stats = {"player": pname, "tackles": len(tk), "interceptions": len(intc),
                 "recoveries": len(br), "clearances": len(cl), "fouls": len(fl),
                 "aerials": len(ar)}
        title = f"{core_events.short_name(pname)} Defensive Actions"
    else:
        title = "Top Defender Actions"

    if not invert:
        ax.set_ylim(-12, 68.5)
    else:
        ax.set_ylim(-0.5, 80)
        ax.invert_xaxis()
        ax.invert_yaxis()
    ax.set_title(title, color=col, fontsize=25, fontweight="bold", path_effects=path_eff())
    return stats


def gk_passmap(ax, df, team, col, invert=False) -> dict:
    """GK distribution: open-play passes (team color) vs goal kicks/free kicks
    (violet); filled = accurate, hollow = inaccurate."""
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)

    d = df[(df["teamName"] == team) & (df["position"] == "GK")]
    gk_pass = d[d["type"] == "Pass"]
    op = gk_pass[~gk_pass["qualifiers"].str.contains("GoalKick|FreekickTaken", na=False)]
    sp = gk_pass[gk_pass["qualifiers"].str.contains("GoalKick|FreekickTaken", na=False)]

    for sub, sub_col in ((op, col), (sp, config.VIOLET)):
        ok = sub[sub["outcomeType"] == "Successful"]
        bad = sub[sub["outcomeType"] != "Successful"]
        pitch.lines(ok.x, ok.y, ok.endX, ok.endY, color=sub_col, lw=4, comet=True,
                    alpha=0.5, zorder=2, ax=ax)
        pitch.lines(bad.x, bad.y, bad.endX, bad.endY, color=sub_col, lw=4, comet=True,
                    alpha=0.35, zorder=2, ax=ax)
        pitch.scatter(ok.endX, ok.endY, s=40, color=sub_col, edgecolor=config.LINE_COLOR, zorder=3, ax=ax)
        pitch.scatter(bad.endX, bad.endY, s=40, color=config.BG_COLOR, edgecolor=sub_col, zorder=3, ax=ax)

    if len(gk_pass):
        length = np.sqrt((gk_pass["x"] - gk_pass["endX"]) ** 2 + (gk_pass["y"] - gk_pass["endY"]) ** 2)
        avg_len = round(length.mean(), 2)
        avg_hgt = round(gk_pass["endX"].mean(), 2)
        gk_name = core_events.short_name(gk_pass["name"].iloc[0])
    else:
        avg_len = avg_hgt = 0.0
        gk_name = "GK"

    y = 71 if invert else -3
    _stats_block(ax, [
        (f"Avg. Passing Length: {avg_len}   |   Avg. Passing Height: {avg_hgt}", None),
        (f"Open-play (Acc.): {len(op)} ({len(op[op['outcomeType'] == 'Successful'])})", col),
        (f"GoalKick/Freekick (Acc.): {len(sp)} ({len(sp[sp['outcomeType'] == 'Successful'])})", config.VIOLET),
    ], 52.5, y, size=15, ha="center", va="top" if not invert else "center")

    if invert:
        ax.invert_xaxis()
        ax.invert_yaxis()
    ax.set_title(f"{gk_name} PassMap", color=col, fontsize=25, fontweight="bold",
                 y=1.07, path_effects=path_eff())
    return {"gk": gk_name, "open_play": len(op), "set_pieces": len(sp)}


# --------------------------------------------------------------------------- #
# Bar charts
# --------------------------------------------------------------------------- #

def _style_bar_ax(ax, title):
    ax.set_facecolor(config.BG_COLOR)
    ax.tick_params(axis="x", colors=config.LINE_COLOR, labelsize=15)
    ax.tick_params(axis="y", colors=config.LINE_COLOR, labelsize=15)
    for spine in ax.spines.values():
        spine.set_edgecolor(config.BG_COLOR)
    ax.legend(facecolor=config.BG_COLOR, edgecolor="none", labelcolor=config.LINE_COLOR,
              fontsize=15, loc="upper right")
    ax.set_title(title, color=config.LINE_COLOR, fontsize=25, fontweight="bold",
                 path_effects=path_eff())


def _gridlines(ax, max_x):
    for x in range(2, int(max_x // 2) * 2 + 1, 2):
        ax.axvline(x=x, color="gray", linestyle="--", zorder=2, alpha=0.5)


def _stacked_barh(ax, top_df, segments, text_color=config.BG_COLOR):
    """top_df (ascending by total) -> stacked horizontal bars, counts inside."""
    names = top_df["shortName"].tolist()
    widths = [[seg[1](top_df)[i] for i in range(len(names))] for seg in segments]
    offsets = np.zeros(len(names))
    for i, (_, widths_i) in enumerate(zip(segments, widths)):
        ax.barh(names, widths_i, label=segments[i][0], color=segments[i][2],
                left=offsets, height=0.65)
        for j, w in enumerate(widths_i):
            if w > 0:
                ax.text(offsets[j] + w / 2, j, str(int(w)) if float(w).is_integer() else str(w),
                        ha="center", va="center", color=text_color, fontsize=13,
                        fontweight="bold")
        offsets += widths_i
    _gridlines(ax, float(offsets.max()) if len(offsets) else 0)
    _style_bar_ax(ax, segments[0][3])


def progressor_bar(ax, top_df, hcol, acol):
    if len(top_df):
        _stacked_barh(ax, top_df, [
            ("Prog. Pass", lambda t: t["Progressive Passes"], hcol, "Top10 Ball Progressors"),
            ("Prog. Carries", lambda t: t["Progressive Carries"], acol, ""),
            ("Through Pass", lambda t: t["LineBreaking Pass"], config.VIOLET, ""),
        ])
    else:
        _style_bar_ax(ax, "Top10 Ball Progressors")


def shot_seq_bar(ax, top_df, hcol, acol):
    if len(top_df):
        _stacked_barh(ax, top_df, [
            ("Shot", lambda t: t["Shots"], hcol, "Shot Sequence Involvement"),
            ("Shot Assist", lambda t: t["Shot Assist"], config.VIOLET, ""),
            ("Buildup to Shot", lambda t: t["Buildup to shot"], acol, ""),
        ])
    else:
        _style_bar_ax(ax, "Shot Sequence Involvement")


def defender_bar(ax, top_df, hcol, acol):
    if len(top_df):
        _stacked_barh(ax, top_df, [
            ("Tackle", lambda t: t["Tackles"], hcol, "Top10 Defenders"),
            ("Interception", lambda t: t["Interceptions"], config.VIOLET, ""),
            ("Clearance", lambda t: t["Clearance"], acol, ""),
        ])
    else:
        _style_bar_ax(ax, "Top10 Defenders")


def threat_bar(ax, top_df, hcol):
    if len(top_df):
        _stacked_barh(ax, top_df, [
            ("xT_pass", lambda t: t["xT from Pass"], hcol, "Top10 Threatening Players"),
            ("xT_carry", lambda t: t["xT from Carry"], config.VIOLET, ""),
        ], text_color=config.LINE_COLOR)
    else:
        _style_bar_ax(ax, "Top10 Threatening Players")


# --------------------------------------------------------------------------- #
# Figure assembly
# --------------------------------------------------------------------------- #

def build_top_players_figure(df, home, away, hcol, acol, meta) -> plt.Figure:
    """Figure 3: 4x3 Top Players dashboard (blueprint layout)."""
    h_prog, a_prog = core_player.top_progressors(df, home, 5), core_player.top_progressors(df, away, 5)
    h_def, a_def = core_player.top_defenders(df, home, 5), core_player.top_defenders(df, away, 5)
    all_prog = core_player.top_progressors(df, None, 10)
    all_threat = core_player.top_threat(df, None, 10)
    all_shsq = core_player.top_shot_sequence(df, None, 10)
    all_def = core_player.top_defenders(df, None, 10)

    fig3, axs3 = plt.subplots(4, 3, figsize=(35, 35), facecolor=config.BG_COLOR)

    top_passmap(axs3[0, 0], df, home, hcol, h_prog)
    progressor_bar(axs3[0, 1], all_prog, hcol, acol)
    top_passmap(axs3[0, 2], df, away, acol, a_prog, invert=True)

    passes_received(axs3[1, 0], df, home, hcol)
    shot_seq_bar(axs3[1, 1], all_shsq, hcol, acol)
    passes_received(axs3[1, 2], df, away, acol, invert=True)

    top_defender_actions(axs3[2, 0], df, home, hcol, h_def)
    defender_bar(axs3[2, 1], all_def, hcol, acol)
    top_defender_actions(axs3[2, 2], df, away, acol, a_def, invert=True)

    gk_passmap(axs3[3, 0], df, home, hcol)
    threat_bar(axs3[3, 1], all_threat, hcol)
    gk_passmap(axs3[3, 2], df, away, acol, invert=True)

    score = _score_str(meta)
    comp = meta.get("competition") or ""
    fig3.text(0.5, 0.98, f"{home} {score} {away}", color=config.LINE_COLOR, fontsize=70,
              fontweight="bold", ha="center", va="center")
    fig3.text(0.5, 0.945, f"{comp} | Post Match Report — Top Players", color=config.LINE_COLOR,
              fontsize=30, ha="center", va="center")
    fig3.text(0.5, 0.925, "Data from: WhoScored + FotMob", color=config.LINE_COLOR,
              fontsize=22.5, ha="center", va="center")
    fig3.text(0.125, 0.1, "Attacking Direction ------->", color=hcol, fontsize=25,
              ha="left", va="center")
    fig3.text(0.9, 0.1, "<------- Attacking Direction", color=acol, fontsize=25,
              ha="right", va="center")

    return fig3
