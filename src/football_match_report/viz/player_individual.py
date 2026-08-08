"""Individual player dashboard (blueprint: pass map, carries & take-ons, shot map,
passes received, defensive actions, touches heatmap). 2x3 figure per player.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyArrowPatch

from .. import config
from ..core import events as core_events
from ..core import player_stats as core_player
from .helpers import make_pitch, path_eff, style_ax
from .player_top import _score_str, _stats_block

GREEN = "#00b300"


# --------------------------------------------------------------------------- #
# Pass map
# --------------------------------------------------------------------------- #

def individual_pass_map(ax, df, pname, col) -> dict:
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)

    d = df[(df["type"] == "Pass") & (df["name"] == pname)]
    acc = d[d["outcomeType"] == "Successful"]
    accuracy = round(len(acc) / len(d) * 100, 2) if len(d) else 0.0
    op = ~acc["qualifiers"].str.contains("CornerTaken|Freekick", na=False)
    pro = acc[(acc["prog_pass"] >= config.PROGRESSIVE_DIST) & (acc["x"] >= config.PROGRESSIVE_START_X) & op]
    key = d[d["qualifiers"].str.contains("KeyPass", na=False)]
    assists = d[d["qualifiers"].str.contains("IntentionalGoalAssist", na=False)]
    big_created = d[d["qualifiers"].str.contains("BigChanceCreated", na=False)]
    crosses = d[d["qualifiers"].str.contains("Cross", na=False) & ~d["qualifiers"].str.contains("CornerTaken|Freekick", na=False)]
    longballs = d[d["qualifiers"].str.contains("Longball", na=False) & ~d["qualifiers"].str.contains("CornerTaken|Freekick", na=False)]
    final_third = acc[(acc["endX"] >= config.FINAL_THIRD_X) & op]
    pen_box = acc[
        (acc["endX"] >= config.BOX_X) & (acc["endY"] >= config.BOX_Y_MIN)
        & (acc["endY"] <= config.BOX_Y_MAX) & op
    ]
    xt_by_pass = round(d["xT"].sum(), 2)

    no_carry = df[df["type"] != "Carry"].reset_index(drop=True)
    pre_assist = no_carry[
        (no_carry["name"] == pname) & (no_carry["type"] == "Pass")
        & (no_carry["outcomeType"] == "Successful")
        & (no_carry["qualifiers"].shift(-1).str.contains("IntentionalGoalAssist", na=False))
    ]
    buildup = no_carry[
        (no_carry["name"] == pname) & (no_carry["type"] == "Pass")
        & (no_carry["outcomeType"] == "Successful")
        & (no_carry["qualifiers"].shift(-1).str.contains("KeyPass", na=False))
    ]

    pitch.lines(d[d["outcomeType"] != "Successful"].x, d[d["outcomeType"] != "Successful"].y,
                d[d["outcomeType"] != "Successful"].endX, d[d["outcomeType"] != "Successful"].endY,
                color=config.LINE_COLOR, lw=4, alpha=0.15, comet=True, zorder=2, ax=ax)
    pitch.lines(acc.x, acc.y, acc.endX, acc.endY, color=config.LINE_COLOR, lw=2,
                alpha=0.15, comet=True, zorder=2, ax=ax)
    pitch.lines(pro.x, pro.y, pro.endX, pro.endY, color=col, lw=3, alpha=1,
                comet=True, zorder=3, ax=ax)
    pitch.lines(key.x, key.y, key.endX, key.endY, color=config.VIOLET, lw=4,
                alpha=1, comet=True, zorder=4, ax=ax)
    pitch.lines(assists.x, assists.y, assists.endX, assists.endY, color=GREEN, lw=4,
                alpha=1, comet=True, zorder=5, ax=ax)

    ax.scatter(acc.endX, acc.endY, s=30, color=config.BG_COLOR, edgecolor="gray", zorder=2)
    ax.scatter(pro.endX, pro.endY, s=40, color=config.BG_COLOR, edgecolor=col, zorder=3)
    ax.scatter(key.endX, key.endY, s=50, color=config.BG_COLOR, edgecolor=config.VIOLET, zorder=4)
    ax.scatter(assists.endX, assists.endY, s=50, color=config.BG_COLOR, edgecolor=GREEN, zorder=5)

    _stats_block(ax, [
        (f"Accurate Pass: {len(acc)}/{len(d)} ({accuracy}%) | Progressive Pass: {len(pro)} | Chances Created: {len(key)}", col),
        (f"Big Chances Created: {len(big_created)} | Assists: {len(assists)} | Pre-Assist: {len(pre_assist)} | Build-up to Shot: {len(buildup)}", None),
        (f"Final third Passes: {len(final_third)} | Passes into Penalty box: {len(pen_box)} | Crosses (Acc.): {len(crosses)} ({len(crosses[crosses['outcomeType'] == 'Successful'])})", None),
        (f"Longballs (Acc.): {len(longballs)} ({len(longballs[longballs['outcomeType'] == 'Successful'])}) | xT from Pass: {xt_by_pass}", None),
    ], 0, -3, size=15)

    ax.set_title("PassMap", color=config.LINE_COLOR, fontsize=25, fontweight="bold",
                 y=1.03, path_effects=path_eff())
    return {"player": pname, "passes": len(d), "accuracy": accuracy,
            "progressive_passes": len(pro), "chances_created": len(key)}


# --------------------------------------------------------------------------- #
# Carries & take-ons
# --------------------------------------------------------------------------- #

def individual_carries(ax, df, pname, col) -> dict:
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)

    d = df[(df["type"] == "Carry") & (df["name"] == pname)]
    qual_next = df["qualifiers"].shift(-1)
    type_next = df["type"].shift(-1)
    led_shot = d[
        qual_next.loc[d.index].fillna("").str.contains("KeyPass", na=False)
        | type_next.loc[d.index].fillna("").str.contains("Shot", na=False)
    ]
    led_goal = d[
        qual_next.loc[d.index].fillna("").str.contains("IntentionalGoalAssist", na=False)
        | (type_next.loc[d.index].fillna("") == "Goal")
    ]
    pro = d[(d["prog_carry"] >= config.PROGRESSIVE_DIST) & (d["x"] >= config.PROGRESSIVE_START_X)]
    final_third = d[(d["x"] < config.FINAL_THIRD_X) & (d["endX"] >= config.FINAL_THIRD_X)]
    in_box = (d["endX"] >= config.BOX_X) & (d["endY"] >= config.BOX_Y_MIN) & (d["endY"] <= config.BOX_Y_MAX)
    starts_in_box = (d["x"] >= config.BOX_X) & (d["y"] >= config.BOX_Y_MIN) & (d["y"] <= config.BOX_Y_MAX)
    box_entry = d[in_box & ~starts_in_box]
    dispossessed = df[
        (df["type"] == "Carry") & (df["name"] == pname) & (df["type"].shift(-1) == "Dispossessed")
    ]
    take_ons = df[(df["type"] == "TakeOn") & (df["name"] == pname)]
    t_ons = take_ons[take_ons["outcomeType"] == "Successful"]
    t_off = take_ons[take_ons["outcomeType"] != "Successful"]
    success_rate = round(len(t_ons) / len(take_ons) * 100, 2) if len(take_ons) else 0.0
    xt_by_carry = round(d["xT"].sum(), 2)

    d = d.copy()
    d["Length"] = np.sqrt((d["x"] - d["endX"]) ** 2 + (d["y"] - d["endY"]) ** 2)
    median_len = round(d["Length"].median(), 2) if len(d) else 0.0
    total_len = round(d["Length"].sum(), 2) if len(d) else 0.0

    for _, row in d.iterrows():
        ax.add_patch(FancyArrowPatch((row["x"], row["y"]), (row["endX"], row["endY"]),
                                     color=config.LINE_COLOR, alpha=0.25, arrowstyle="->",
                                     linestyle="--", linewidth=2, mutation_scale=15, zorder=2))
    for _, row in pro.iterrows():
        ax.add_patch(FancyArrowPatch((row["x"], row["y"]), (row["endX"], row["endY"]),
                                     color=col, alpha=1, arrowstyle="->", linestyle="--",
                                     linewidth=3, mutation_scale=20, zorder=3))
    for _, row in led_shot.iterrows():
        ax.add_patch(FancyArrowPatch((row["x"], row["y"]), (row["endX"], row["endY"]),
                                     color=config.VIOLET, alpha=1, arrowstyle="->",
                                     linestyle="--", linewidth=4, mutation_scale=20, zorder=4))
    for _, row in led_goal.iterrows():
        ax.add_patch(FancyArrowPatch((row["x"], row["y"]), (row["endX"], row["endY"]),
                                     color=GREEN, alpha=1, arrowstyle="->", linestyle="--",
                                     linewidth=4, mutation_scale=20, zorder=4))

    if len(t_ons):
        ax.scatter(t_ons.x, t_ons.y, s=250, color="orange", edgecolor=config.LINE_COLOR,
                   lw=2, zorder=5)
    if len(t_off):
        ax.scatter(t_off.x, t_off.y, s=250, color="None", edgecolor="orange",
                   hatch="/////", lw=2.5, zorder=5)

    _stats_block(ax, [
        (f"Total Carries: {len(d)} | Progressive Carries: {len(pro)} | Carries Led to Shot: {len(led_shot)}", col),
        (f"Carries Led to Goal: {len(led_goal)} | Carrier Dispossessed: {len(dispossessed)} | Carries into Final third: {len(final_third)}", None),
        (f"Carries into pen.box: {len(box_entry)} | Avg. Carry Length: {median_len} m | Total Carry: {total_len} m", None),
        (f"xT from Carries: {xt_by_carry} | Successful TakeOns: {len(t_ons)}/{len(take_ons)} ({success_rate}%)", "orange"),
    ], 0, -3, size=15)

    ax.set_title("Carries & TakeOns", color=config.LINE_COLOR, fontsize=25,
                 fontweight="bold", y=1.03, path_effects=path_eff())
    return {"player": pname, "carries": len(d), "progressive_carries": len(pro),
            "led_to_shot": len(led_shot), "take_on_attempts": len(take_ons)}


# --------------------------------------------------------------------------- #
# Shot map
# --------------------------------------------------------------------------- #

def individual_shot_map(ax, df, shots_df, pname, col) -> dict:
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)

    shots = core_player.player_shot_frame(df, pname, shots_df)
    if len(shots):
        size = shots["expectedGoals"].fillna(0) * 1000 + 100
        goal = shots[shots["eventType"] == "Goal"]
        post = shots[shots["eventType"] == "Post"]
        blocked = shots[(shots["eventType"] == "AttemptSaved") & (shots["isBlocked"] == 1)]
        saved = shots[(shots["eventType"] == "AttemptSaved") & (shots["isBlocked"] != 1)]
        missed = shots[shots["eventType"] == "Miss"]
        open_play = int((shots["situation"] == "RegularPlay").sum())
    else:
        size = pd.Series(dtype=float)
        empty = pd.DataFrame(columns=["x", "y", "eventType", "expectedGoals",
                                      "expectedGoalsOnTarget", "isBlocked",
                                      "isFromInsideBox", "situation"])
        goal = post = blocked = saved = missed = empty.copy()
        open_play = 0

    pitch.scatter(goal.x, goal.y, s=size.reindex(goal.index).fillna(100) if len(goal) else 100,
                  marker="football", c="None", edgecolors=GREEN, zorder=5, ax=ax)
    pitch.scatter(post.x, post.y, s=size.reindex(post.index).fillna(100) if len(post) else 100,
                  marker="o", c="None", edgecolors=col, hatch="+++", zorder=4, ax=ax)
    pitch.scatter(blocked.x, blocked.y, s=size.reindex(blocked.index).fillna(100) if len(blocked) else 100,
                  marker="o", c="None", edgecolors=col, hatch="/////", zorder=4, ax=ax)
    pitch.scatter(saved.x, saved.y, s=size.reindex(saved.index).fillna(100) if len(saved) else 100,
                  marker="o", c=col, edgecolors=config.LINE_COLOR, zorder=3, ax=ax)
    pitch.scatter(missed.x, missed.y, s=size.reindex(missed.index).fillna(100) if len(missed) else 100,
                  marker="o", c="None", edgecolors=col, zorder=2, ax=ax)

    # legend markers + stats text on the left half
    y0 = 58.0
    pitch.scatter(np.array([2.0]), np.array([y0]), s=200, marker="football", c="None",
                  edgecolors=GREEN, zorder=5, ax=ax)
    pitch.scatter(np.array([2.0]), np.array([y0 - 4]), s=150, marker="o", c="None",
                  edgecolors=col, hatch="+++", zorder=4, ax=ax)
    pitch.scatter(np.array([2.0]), np.array([y0 - 8]), s=150, marker="o", c=col,
                  edgecolors=config.LINE_COLOR, zorder=3, ax=ax)
    pitch.scatter(np.array([2.0]), np.array([y0 - 12]), s=130, marker="o", c="None",
                  edgecolors=col, zorder=2, ax=ax)
    pitch.scatter(np.array([2.0]), np.array([y0 - 16]), s=130, marker="o", c="None",
                  edgecolors=col, hatch="/////", zorder=2, ax=ax)

    xg = round(shots["expectedGoals"].fillna(0).sum(), 2) if len(shots) else 0.0
    xgot = round(shots["expectedGoalsOnTarget"].fillna(0).sum(), 2) if len(shots) else 0.0
    total = len(shots)
    if total:
        dist = np.sqrt((shots["x"] - config.PITCH_X_MAX) ** 2
                       + (shots["y"] - config.GOAL_CENTER[1]) ** 2)
        avg_dist = round(dist.mean(), 2)
    else:
        avg_dist = 0.0
    stats_rows = [
        (f"Total Shots: {total}", None),
        (f"Open-play Shots: {open_play}", None),
        (f"Goals: {len(goal)} | Shot on Post: {len(post)}", None),
        (f"Shots on Target: {len(saved)} | Off Target: {len(missed)} | Blocked: {len(blocked)}", None),
        (f"Inside Box: {len(shots[shots['isFromInsideBox'] == True])} | Outside Box: {len(shots[shots['isFromInsideBox'] != True])}", None),  # noqa: E712
        (f"Avg. Shot Distance: {avg_dist} m", None),
        (f"xG: {xg} | xGOT: {xgot}", col),
    ]
    _stats_block(ax, stats_rows, 7, 62, size=15, spacing=3.6)

    ax.text(80, 71, "Shot Map", color=config.LINE_COLOR, fontsize=25, fontweight="bold",
            ha="center", path_effects=path_eff())
    return {"player": pname, "shots": total, "goals": len(goal), "xG": xg, "xGOT": xgot}


# --------------------------------------------------------------------------- #
# Passes received
# --------------------------------------------------------------------------- #

def individual_passes_received(ax, df, pname, col) -> dict:
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)

    d = df[
        (df["type"] == "Pass") & (df["outcomeType"] == "Successful")
        & (df["name"].shift(-1) == pname)
    ]
    key_recv = d[d["qualifiers"].str.contains("KeyPass", na=False)]
    assist_recv = d[d["qualifiers"].str.contains("IntentionalGoalAssist", na=False)]
    final_third = d[d["endX"] >= config.FINAL_THIRD_X]
    pen_box = d[
        (d["endX"] >= config.BOX_X - 0.5) & (d["endY"] >= config.BOX_Y_MIN)
        & (d["endY"] <= config.BOX_Y_MAX)
    ]
    prog_recv = d[
        (d["x"] >= config.PROGRESSIVE_START_X) & (d["prog_pass"] >= config.PROGRESSIVE_DIST)
        & (~d["qualifiers"].str.contains("CornerTaken|Freekick", na=False))
    ]
    crosses_recv = d[d["qualifiers"].str.contains("Cross", na=False)]
    longballs_recv = d[d["qualifiers"].str.contains("Longball", na=False)]
    xt_recv = round(d[d["xT"] >= 0]["xT"].sum(), 2)

    next_act = df[
        (df["name"] == pname) & (df["type"].shift(1) == "Pass")
        & (df["outcomeType"].shift(1) == "Successful")
    ]
    retained = next_act[next_act["outcomeType"] == "Successful"]
    retention = round(len(retained) / len(next_act) * 100, 2) if len(next_act) else 0.0

    if len(d):
        passer_counts = d["name"].map(core_events.short_name).value_counts()
        most_from = f"{passer_counts.index[0]} ({int(passer_counts.iloc[0])})"
        avg_dist = round(105 - d["endX"].median(), 2)
    else:
        most_from, avg_dist = "-", 0.0

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
        ax.axvline(x=d["endX"].median(), color="gray", linestyle="--", alpha=0.6, linewidth=2)
        ax.axhline(y=d["endY"].median(), color="gray", linestyle="--", alpha=0.6, linewidth=2)

    _stats_block(ax, [
        (f"Passes Received: {len(d)} | Key Passes Received: {len(key_recv)} | Assists Received: {len(assist_recv)}", col),
        (f"Final third: {len(final_third)} | Opp. box: {len(pen_box)} | Progressive: {len(prog_recv)} | Crosses: {len(crosses_recv)} | Longballs: {len(longballs_recv)}", None),
        (f"Ball Retention: {retention} % | xT Received: {xt_recv} | Avg. Distance from Oppo. Goal line: {avg_dist} m", None),
        (f"Most Passes from: {most_from}", None),
    ], 0, -3, size=15)

    ax.set_title("Passes Received", color=config.LINE_COLOR, fontsize=25,
                 fontweight="bold", y=1.03, path_effects=path_eff())
    return {"player": pname, "passes_received": len(d)}


# --------------------------------------------------------------------------- #
# Defensive actions
# --------------------------------------------------------------------------- #

def individual_def_actions(ax, df, pname, col) -> dict:
    pitch = make_pitch(line_zorder=2)
    pitch.draw(ax=ax)
    style_ax(ax)

    d = df[df["name"] == pname]
    ball_wins = d[(d["type"] == "Interception") | (d["type"] == "BallRecovery")]
    f_third = ball_wins[ball_wins["x"] >= config.FINAL_THIRD_X]
    m_third = ball_wins[
        (ball_wins["x"] > config.PROGRESSIVE_START_X) & (ball_wins["x"] < config.FINAL_THIRD_X)
    ]
    d_third = ball_wins[ball_wins["x"] <= config.PROGRESSIVE_START_X]

    tk = d[d["type"] == "Tackle"]
    tk_u = tk[tk["outcomeType"] == "Unsuccessful"]
    intc = d[d["type"] == "Interception"]
    br = d[d["type"] == "BallRecovery"]
    cl = d[d["type"] == "Clearance"]
    fl = d[d["type"] == "Foul"]
    ar = d[(d["type"] == "Aerial") & d["qualifiers"].str.contains("Defensive", na=False)]
    ar_u = ar[ar["outcomeType"] == "Unsuccessful"]
    pass_bl = d[d["type"] == "BlockedPass"]
    shot_bl = d[d["type"].isin(config.SHOT_TYPES) & d["qualifiers"].str.contains("Blocked", na=False)]
    drb_pst = d[d["type"] == "Challenge"]
    drb_tkl = df[
        (df["name"] == pname) & (df["type"] == "Tackle")
        & (df["type"].shift(1) == "TakeOn") & (df["outcomeType"].shift(1) == "Unsuccessful")
    ]
    err_shot = d[d["qualifiers"].str.contains("LeadingToAttempt", na=False)]
    err_goal = d[d["qualifiers"].str.contains("LeadingToGoal", na=False)]
    dang_fouls = d[
        (d["type"] == "Foul") & (d["x"] > 16.5) & (d["x"] < config.PROGRESSIVE_START_X)
        & (d["y"] > config.BOX_Y_MIN) & (d["y"] < config.BOX_Y_MAX)
    ]

    pitch.scatter(tk.x, tk.y, s=250, c=col, lw=2.5, edgecolor=col, marker="+",
                  hatch="/////", ax=ax)
    pitch.scatter(tk_u.x, tk_u.y, s=250, c="gray", lw=2.5, edgecolor="gray", marker="+",
                  hatch="/////", ax=ax)
    pitch.scatter(intc.x, intc.y, s=250, c="None", lw=2.5, edgecolor=col, marker="s",
                  hatch="/////", ax=ax)
    pitch.scatter(br.x, br.y, s=250, c="None", lw=2.5, edgecolor=col, marker="o",
                  hatch="/////", ax=ax)
    pitch.scatter(cl.x, cl.y, s=250, c="None", lw=2.5, edgecolor=col, marker="d",
                  hatch="/////", ax=ax)
    pitch.scatter(fl.x, fl.y, s=250, c=col, lw=2.5, edgecolor=col, marker="x",
                  hatch="/////", ax=ax)
    pitch.scatter(ar.x, ar.y, s=250, c="None", lw=2.5, edgecolor=col, marker="^",
                  hatch="/////", ax=ax)
    pitch.scatter(ar_u.x, ar_u.y, s=250, c="None", lw=2.5, edgecolor="gray", marker="^",
                  hatch="/////", ax=ax)
    pitch.scatter(drb_pst.x, drb_pst.y, s=250, c="None", lw=2.5, edgecolor=col,
                  marker="h", hatch="|||||", ax=ax)

    stats = core_player.defensive_stats(df, pname)
    _stats_block(ax, [
        (f"Tackle (Win): {len(tk)} ({len(tk) - len(tk_u)}) | Dribblers Tackled: {len(drb_tkl)} | Dribble past: {len(drb_pst)} | Interception: {len(intc)}", col),
        (f"Ball Recovery: {len(br)} | Post Recovery Retention: {stats['Post_Recovery_Ball_Retention']} % | Pass Block: {len(pass_bl)}", None),
        (f"Clearances: {len(cl)} | Shots Blocked: {len(shot_bl)} | Aerial Duels (Win): {len(ar)} ({len(ar) - len(ar_u)}) | Fouls: {len(fl)}", None),
        (f"Dangerous Fouls: {len(dang_fouls)} | Error Led to Shot/Goal: {len(err_shot)}/{len(err_goal)}", None),
        (f"Poss. Win Final/Mid/Def third: {len(f_third)}/{len(m_third)}/{len(d_third)}", None),
    ], 0, -3, size=15)

    ax.set_title("Defensive Actions", color=config.LINE_COLOR, fontsize=25,
                 fontweight="bold", y=1.03, path_effects=path_eff())
    return {"player": pname, "tackles": len(tk), "interceptions": len(intc)}


# --------------------------------------------------------------------------- #
# Touches & heatmap
# --------------------------------------------------------------------------- #

def player_heatmap(ax, df, pname, col) -> dict:
    pitch = make_pitch(line_zorder=3)
    pitch.draw(ax=ax)
    style_ax(ax)

    d = df[df["name"] == pname]
    touches = d[
        (d["isTouch"] == True) & (~d["type"].str.contains("SubstitutionOff|SubstitutionOn|Card|Carry", na=False))  # noqa: E712
    ]

    cmap = LinearSegmentedColormap.from_list(
        "player_hm", [config.BG_COLOR, config.GREEN, config.YELLOW, col, "red"], N=500
    )
    heatmap, xedges, yedges = np.histogram2d(touches["x"], touches["y"], bins=(12, 12))
    extent = [xedges[0], xedges[-1], yedges[-1], yedges[0]]
    ax.imshow(heatmap.T, extent=extent, cmap=cmap, interpolation="bilinear", alpha=0.9)

    if len(touches):
        ax.scatter(touches.x, touches.y, marker="o", s=10, c="gray", zorder=4)
        pts = touches[["x", "y"]].dropna().values
        hull_area = 0.0
        if len(pts) >= 3:
            try:
                from scipy.spatial import ConvexHull
                hull = ConvexHull(pts)
                hull_area = round(hull.volume, 2)
            except Exception:
                hull_area = 0.0
    else:
        hull_area = 0.0

    final_third = touches[touches["x"] >= config.FINAL_THIRD_X]
    pen_box = touches[
        (touches["x"] >= config.BOX_X) & (touches["y"] >= config.BOX_Y_MIN)
        & (touches["y"] <= config.BOX_Y_MAX)
    ]

    pos = d[~d["type"].str.contains("CornerTaken|FreekickTaken|Card|CornerAwarded|SubstitutionOff|SubstitutionOn", na=False)]
    pos = pos[["x", "y", "period"]].copy()
    total_km = 0.0
    for period in (1, 2, 3, 4):
        half = pos[pos["period"] == period]
        if len(half) > 1:
            dist = np.sqrt((half["x"] - half["x"].shift(-1)) ** 2
                           + (half["y"] - half["y"].shift(-1)) ** 2).sum()
            total_km += dist / 1000
    total_km = round(total_km, 2)

    _stats_block(ax, [
        (f"Touches: {len(touches)} | Final third: {len(final_third)} | Penalty Area: {len(pen_box)}", None),
        (f"Distance Covered: {total_km} km | Area Covered: {hull_area} sq.m ({round(hull_area / (105 * 68) * 100, 2)}%)", col),
    ], 52.5, -3, size=15, ha="center", va="top")

    ax.set_title("Touches and Heatmap", color=config.LINE_COLOR, fontsize=25,
                 fontweight="bold", y=1.03, path_effects=path_eff())
    return {"player": pname, "touches": len(touches), "distance_km": total_km}


# --------------------------------------------------------------------------- #
# Figure assembly
# --------------------------------------------------------------------------- #

def build_individual_figure(df, shots_df, pname, team, col, meta) -> plt.Figure:
    """Per-player 2x3 dashboard (blueprint layout, black theme)."""
    fig, axs = plt.subplots(2, 3, figsize=(35, 18), facecolor=config.BG_COLOR)

    individual_pass_map(axs[0, 0], df, pname, col)
    individual_carries(axs[0, 1], df, pname, col)
    individual_shot_map(axs[0, 2], df, shots_df, pname, col)
    individual_passes_received(axs[1, 0], df, pname, col)
    individual_def_actions(axs[1, 1], df, pname, col)
    player_heatmap(axs[1, 2], df, pname, col)

    mins = core_player.playing_time(df, pname)
    pos = df[df["name"] == pname]["position"].dropna()
    position = pos.iloc[0] if len(pos) else ""
    score = _score_str(meta)
    comp = meta.get("competition") or ""

    fig.text(0.02, 0.99, pname, color=config.LINE_COLOR, fontsize=70, fontweight="bold",
             ha="left", va="center")
    fig.text(0.02, 0.94,
             f"{position} | {team} {score} | {comp} | Minutes played: {mins}",
             color=config.LINE_COLOR, fontsize=30, ha="left", va="center")
    return fig
