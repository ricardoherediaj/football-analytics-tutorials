"""Advanced zone charts (blueprint): final-third entry, Zone 14, pass-end zones,
chance creation, box entries, crosses, high turnovers, congestion."""

from __future__ import annotations

import matplotlib.patches as patches
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from .. import config
from .helpers import make_pitch, path_eff, style_ax


# --------------------------------------------------------------------------- #
# Final third entries
# --------------------------------------------------------------------------- #
def final_third_entry(ax, df, team_name, col, invert=False, home_name=None) -> dict:
    dfpass = df[
        (df["teamName"] == team_name) & (df["type"] == "Pass") & (df["x"] < config.FINAL_THIRD_X)
        & (df["endX"] >= config.FINAL_THIRD_X) & (df["outcomeType"] == "Successful")
        & (~df["qualifiers"].str.contains("Freekick", na=False))
    ]
    dfcarry = df[
        (df["teamName"] == team_name) & (df["type"] == "Carry")
        & (df["x"] < config.FINAL_THIRD_X) & (df["endX"] >= config.FINAL_THIRD_X)
    ]
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)
    if invert:
        ax.invert_xaxis()
        ax.invert_yaxis()

    total = len(dfpass) + len(dfcarry)
    left = len(dfpass[dfpass["y"] >= config.ZONE_TOP]) + len(dfcarry[dfcarry["y"] >= config.ZONE_TOP])
    mid = len(dfpass[(dfpass["y"] >= config.ZONE_BOT) & (dfpass["y"] < config.ZONE_TOP)]) \
        + len(dfcarry[(dfcarry["y"] >= config.ZONE_BOT) & (dfcarry["y"] < config.ZONE_TOP)])
    right = total - left - mid

    ax.hlines(config.ZONE_TOP, xmin=0, xmax=70, colors=config.LINE_COLOR, linestyle="dashed", alpha=0.35)
    ax.hlines(config.ZONE_BOT, xmin=0, xmax=70, colors=config.LINE_COLOR, linestyle="dashed", alpha=0.35)
    ax.vlines(70, ymin=-2, ymax=70, colors=config.LINE_COLOR, linestyle="dashed", alpha=0.55)

    bbox = dict(boxstyle="round,pad=0.3", edgecolor="None", facecolor=config.BG_COLOR, alpha=0.75)
    pcts = [round(c / total * 100) if total else 0 for c in (right, mid, left)]
    for count, pct, y in zip((right, mid, left), pcts, (11.335, 34, 56.675)):
        ax.text(8, y, f"{count}\n({pct}%)", color=col, fontsize=24, va="center", ha="center", bbox=bbox)

    if len(dfpass):
        pitch.lines(dfpass.x, dfpass.y, dfpass.endX, dfpass.endY, lw=3.5, comet=True, color=col, ax=ax, alpha=0.5)
        pitch.scatter(dfpass.endX, dfpass.endY, s=35, edgecolor=col, linewidth=1, color=config.BG_COLOR, zorder=2, ax=ax)
    for _, row in dfcarry.iterrows():
        ax.add_patch(patches.FancyArrowPatch(
            (row["x"], row["y"]), (row["endX"], row["endY"]), arrowstyle="->", color=col,
            zorder=4, mutation_scale=20, alpha=1, linewidth=2, linestyle="--"))

    ax.set_title(f"{team_name}\n{total} Final Third Entries", color=config.LINE_COLOR,
                 fontsize=25, fontweight="bold", path_effects=path_eff())
    if home_name and team_name == home_name:
        ax.text(87.5, 70, "<--------------- Final third --------------->", color=config.LINE_COLOR, ha="center", va="center")
        ax.text(63, -5, f"Entry by Pass: {len(dfpass)}", fontsize=15, color=config.LINE_COLOR, ha="center", va="center")
        ax.text(93, -5, f"Entry by Carry: {len(dfcarry)}", fontsize=15, color=config.LINE_COLOR, ha="center", va="center")
    else:
        ax.text(87.5, -2, "<--------------- Final third --------------->", color=config.LINE_COLOR, ha="center", va="center")
        ax.text(63, 73, f"Entry by Pass: {len(dfpass)}", fontsize=15, color=config.LINE_COLOR, ha="center", va="center")
        ax.text(93, 73, f"Entry by Carry: {len(dfcarry)}", fontsize=15, color=config.LINE_COLOR, ha="center", va="center")

    return {
        "Team_Name": team_name, "Total_Final_Third_Entries": total,
        "Final_Third_Entries_From_Left": left, "Final_Third_Entries_From_Center": mid,
        "Final_Third_Entries_From_Right": right, "Entry_By_Pass": len(dfpass), "Entry_By_Carry": len(dfcarry),
    }


# --------------------------------------------------------------------------- #
# Zone 14 & half-spaces
# --------------------------------------------------------------------------- #
def zone14hs(ax, df, team_name, col, invert=False, home_name=None) -> dict:
    dfhp = df[
        (df["teamName"] == team_name) & (df["type"] == "Pass") & (df["outcomeType"] == "Successful")
        & (~df["qualifiers"].str.contains("CornerTaken|Freekick", na=False))
    ]
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)
    if invert:
        ax.invert_xaxis()
        ax.invert_yaxis()

    z14 = hs = lhs = rhs = 0
    for _, row in dfhp.iterrows():
        ex, ey = row["endX"], row["endY"]
        if config.Z14_X_MIN <= ex <= config.Z14_X_MAX and config.Z14_Y_MIN <= ey <= config.Z14_Y_MAX:
            pitch.lines(row["x"], row["y"], ex, ey, color="orange", comet=True, lw=3, zorder=3, ax=ax, alpha=0.75)
            ax.scatter(ex, ey, s=35, linewidth=1, color=config.BG_COLOR, edgecolor="orange", zorder=4)
            z14 += 1
        if ex >= config.FINAL_THIRD_X and config.HS_Y1_MIN <= ey <= config.HS_Y1_MAX:
            pitch.lines(row["x"], row["y"], ex, ey, color=col, comet=True, lw=3, zorder=3, ax=ax, alpha=0.75)
            ax.scatter(ex, ey, s=35, linewidth=1, color=config.BG_COLOR, edgecolor=col, zorder=4)
            hs += 1
            rhs += 1
        if ex >= config.FINAL_THIRD_X and config.HS_Y2_MIN <= ey <= config.HS_Y2_MAX:
            pitch.lines(row["x"], row["y"], ex, ey, color=col, comet=True, lw=3, zorder=3, ax=ax, alpha=0.75)
            ax.scatter(ex, ey, s=35, linewidth=1, color=config.BG_COLOR, edgecolor=col, zorder=4)
            hs += 1
            lhs += 1

    ax.fill([70, 88.54, 88.54, 70], [22.66, 22.66, 45.32, 45.32], "orange", alpha=0.2)
    ax.fill([70, 105, 105, 70], [11.33, 11.33, 22.66, 22.66], col, alpha=0.2)
    ax.fill([70, 105, 105, 70], [45.32, 45.32, 56.95, 56.95], col, alpha=0.2)

    ax.scatter(16.46, 13.85, color=col, s=15000, edgecolor=config.LINE_COLOR, linewidth=2, alpha=1, marker="h")
    ax.scatter(16.46, 54.15, color="orange", s=15000, edgecolor=config.LINE_COLOR, linewidth=2, alpha=1, marker="h")
    ax.text(16.46, 9.85, "HalfSp", fontsize=20, color=config.LINE_COLOR, ha="center", va="center", path_effects=path_eff())
    ax.text(16.46, 50.15, "Zone14", fontsize=20, color=config.LINE_COLOR, ha="center", va="center", path_effects=path_eff())
    ax.text(16.46, 4, f"{hs}", fontsize=20, color=config.LINE_COLOR, ha="center", va="center", path_effects=path_eff())
    ax.text(16.46, 62, f"{z14}", fontsize=20, color=config.LINE_COLOR, ha="center", va="center", path_effects=path_eff())

    ax.set_title(f"{team_name}\nZone 14 & Half-Space Passes", color=config.LINE_COLOR,
                 fontsize=25, fontweight="bold", path_effects=path_eff())
    return {"Team_Name": team_name, "Zone14_Passes": z14, "HalfSpace_Passes": hs}


# --------------------------------------------------------------------------- #
# Pass end zone heatmap
# --------------------------------------------------------------------------- #
def pass_end_zone(ax, df, team_name, cm, invert=False, home_name=None) -> None:
    pez = df[(df["teamName"] == team_name) & (df["type"] == "Pass") & (df["outcomeType"] == "Successful")]
    pitch = make_pitch(goal_type="box", goal_alpha=0.5, line_zorder=2)
    pitch.draw(ax=ax)
    style_ax(ax)
    if invert:
        ax.invert_xaxis()
        ax.invert_yaxis()

    if len(pez):
        bin_stat = pitch.bin_statistic(pez.endX, pez.endY, bins=(6, 5), normalize=True)
        pitch.heatmap(bin_stat, ax=ax, cmap=cm, edgecolors=config.BG_COLOR)
        pitch.label_heatmap(bin_stat, color=config.LINE_COLOR, fontsize=25, ax=ax, ha="center",
                            va="center", str_format="{:.0%}", path_effects=path_eff())
    pitch.scatter(df[df["teamName"] == team_name].endX, df[df["teamName"] == team_name].endY,
                  c="gray", s=5, ax=ax)

    ax.set_title(f"{team_name}\nPass End Zone", color=config.LINE_COLOR, fontsize=25,
                 fontweight="bold", path_effects=path_eff())


# --------------------------------------------------------------------------- #
# Chance creating zone
# --------------------------------------------------------------------------- #
def chance_creating_zone(ax, df, team_name, cm, col, invert=False, home_name=None) -> dict:
    ccp = df[(df["qualifiers"].str.contains("KeyPass", na=False)) & (df["teamName"] == team_name)]
    pitch = make_pitch(line_zorder=2)
    pitch.draw(ax=ax)
    style_ax(ax)
    if invert:
        ax.invert_xaxis()
        ax.invert_yaxis()

    cc = 0
    if len(ccp):
        bin_stat = pitch.bin_statistic(ccp.x, ccp.y, bins=(6, 5), statistic="count", normalize=False)
        pitch.heatmap(bin_stat, ax=ax, cmap=cm, edgecolors="#f8f8f8")
        for _, row in ccp.iterrows():
            is_assist = "IntentionalGoalAssist" in row["qualifiers"]
            line_col = config.GREEN if is_assist else config.VIOLET
            pitch.lines(row["x"], row["y"], row["endX"], row["endY"], color=line_col, comet=True,
                        lw=3, zorder=3, ax=ax)
            ax.scatter(row["endX"], row["endY"], s=35, linewidth=1, color=config.BG_COLOR,
                       edgecolor=line_col, zorder=4)
            cc += 1
        pitch.label_heatmap(bin_stat, color=config.LINE_COLOR, fontsize=25, ax=ax, ha="center",
                            va="center", str_format="{:.0f}", path_effects=path_eff())

    if home_name and team_name == home_name:
        ax.text(105, -3.5, "violet = key pass\ngreen = assist", color=col, size=15, ha="right", va="center")
        ax.text(52.5, 70, f"Total Chances Created = {cc}", color=col, fontsize=15, ha="center", va="center")
    else:
        ax.text(105, 71.5, "violet = key pass\ngreen = assist", color=col, size=15, ha="left", va="center")
        ax.text(52.5, -2, f"Total Chances Created = {cc}", color=col, fontsize=15, ha="center", va="center")

    ax.set_title(f"{team_name}\nChance Creating Zone", color=config.LINE_COLOR, fontsize=25,
                 fontweight="bold", path_effects=path_eff())
    return {"Team_Name": team_name, "Chances_Created": cc}


# --------------------------------------------------------------------------- #
# Box entries
# --------------------------------------------------------------------------- #
def box_entry(ax, df, home, away, hcol, acol) -> dict:
    bentry = df[
        ((df["type"] == "Pass") | (df["type"] == "Carry")) & (df["outcomeType"] == "Successful")
        & (df["endX"] >= config.BOX_X)
        & ~((df["x"] >= config.BOX_X) & (df["y"] >= config.BOX_Y_MIN) & (df["y"] <= config.BOX_Y_MAX))
        & (df["endY"] >= config.BOX_Y_MIN) & (df["endY"] <= config.BOX_Y_MAX)
        & (~df["qualifiers"].str.contains("CornerTaken|Freekick|ThrowIn", na=False))
    ]
    hb = bentry[bentry["teamName"] == home]
    ab = bentry[bentry["teamName"] == away]

    pitch = make_pitch(line_zorder=2)
    pitch.draw(ax=ax)
    style_ax(ax)

    for _, row in bentry.iterrows():
        if row["teamName"] == away:
            c, x, y, ex, ey = acol, row["x"], row["y"], row["endX"], row["endY"]
        else:
            c, x, y, ex, ey = hcol, 105 - row["x"], 68 - row["y"], 105 - row["endX"], 68 - row["endY"]
        if row["type"] == "Pass":
            pitch.lines(x, y, ex, ey, lw=3.5, comet=True, color=c, ax=ax, alpha=0.5)
            pitch.scatter(ex, ey, s=35, edgecolor=c, linewidth=1, color=config.BG_COLOR, zorder=2, ax=ax)
        else:
            ax.add_patch(patches.FancyArrowPatch((x, y), (ex, ey), arrowstyle="->", color=c,
                                                 zorder=4, mutation_scale=20, alpha=1, linewidth=2, linestyle="--"))

    ax.text(0, 69, f"{home}\nBox Entries: {len(hb)}", color=hcol, fontsize=25, fontweight="bold", ha="left", va="bottom")
    ax.text(105, 69, f"{away}\nBox Entries: {len(ab)}", color=acol, fontsize=25, fontweight="bold", ha="right", va="bottom")

    def _zone_counts(bdf):
        r = len(bdf[bdf["y"] < 68 / 3])
        c_ = len(bdf[(bdf["y"] >= 68 / 3) & (bdf["y"] <= 136 / 3)])
        left = len(bdf[bdf["y"] > 136 / 3])
        return left, c_, r

    h_l, h_c, h_r = _zone_counts(hb)
    a_l, a_c, a_r = _zone_counts(ab)
    for y_pos, val, col in [(6, h_r, hcol), (34, h_c, hcol), (62, h_l, hcol)]:
        ax.scatter(46, y_pos, s=2000, marker="s", color=col, zorder=3)
        ax.text(46, y_pos, f"{val}", fontsize=30, fontweight="bold", color=config.BG_COLOR, ha="center", va="center")
    for y_pos, val, col in [(6, a_r, acol), (34, a_c, acol), (62, a_l, acol)]:
        ax.scatter(59, y_pos, s=2000, marker="s", color=col, zorder=3)
        ax.text(59, y_pos, f"{val}", fontsize=30, fontweight="bold", color=config.BG_COLOR, ha="center", va="center")

    return {"Team_Name": home, "Box_Entries": len(hb)}


# --------------------------------------------------------------------------- #
# Crosses
# --------------------------------------------------------------------------- #
def crosses(ax, df, home, away, hcol, acol) -> dict:
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)

    home_cross = df[(df["teamName"] == home) & (df["type"] == "Pass")
                    & df["qualifiers"].str.contains("Cross", na=False)
                    & (~df["qualifiers"].str.contains("Corner", na=False))]
    away_cross = df[(df["teamName"] == away) & (df["type"] == "Pass")
                    & df["qualifiers"].str.contains("Cross", na=False)
                    & (~df["qualifiers"].str.contains("Corner", na=False))]

    hsuc = hunsuc = asuc = aunsuc = 0
    for _, row in home_cross.iterrows():
        ok = row["outcomeType"] == "Successful"
        if ok:
            hsuc += 1
        else:
            hunsuc += 1
        ax.add_patch(patches.FancyArrowPatch(
            (105 - row["x"], 68 - row["y"]), (105 - row["endX"], 68 - row["endY"]),
            arrowstyle="->", mutation_scale=15 if ok else 10, color=hcol if ok else config.LINE_COLOR,
            linewidth=1.5, alpha=1 if ok else 0.25))
    for _, row in away_cross.iterrows():
        ok = row["outcomeType"] == "Successful"
        if ok:
            asuc += 1
        else:
            aunsuc += 1
        ax.add_patch(patches.FancyArrowPatch(
            (row["x"], row["y"]), (row["endX"], row["endY"]),
            arrowstyle="->", mutation_scale=15 if ok else 10, color=acol if ok else config.LINE_COLOR,
            linewidth=1.5, alpha=1 if ok else 0.25))

    ax.text(0, 69, f"{home} Crosses\n{hsuc} acc. / {hunsuc} unacc.", color=hcol, fontsize=22,
            fontweight="bold", ha="left", va="bottom")
    ax.text(105, 69, f"{away} Crosses\n{asuc} acc. / {aunsuc} unacc.", color=acol, fontsize=22,
            fontweight="bold", ha="right", va="bottom")
    return {"Home_Accurate_Crosses": hsuc, "Away_Accurate_Crosses": asuc}


# --------------------------------------------------------------------------- #
# High turnovers
# --------------------------------------------------------------------------- #
def high_turnovers(ax, df, home, away, hcol, acol) -> dict:
    pitch = make_pitch()
    pitch.draw(ax=ax)
    style_ax(ax)

    highTO = df.copy()
    highTO["Distance"] = ((highTO["x"] - 105) ** 2 + (highTO["y"] - 34) ** 2) ** 0.5

    def analyze(team, col):
        goal_count = shot_count = other_count = 0
        for i in range(len(highTO)):
            row = highTO.iloc[i]
            if row["type"] in ["BallRecovery", "Interception"] and row["teamName"] == team and row["Distance"] <= config.HIGH_TURNOVER_DIST:
                pid = row["possession_id"]
                j = i + 1
                led_goal = led_shot = False
                while j < len(highTO) and highTO.iloc[j]["possession_id"] == pid and highTO.iloc[j]["teamName"] == team:
                    nxt = highTO.iloc[j]
                    if nxt["type"] == "Goal":
                        ax.scatter(row["x"], row["y"], s=600, marker="*", color="green", edgecolor="k", zorder=3)
                        goal_count += 1
                        led_goal = True
                        break
                    if "Shot" in str(nxt["type"]):
                        led_shot = True
                        break
                    j += 1
                if not led_goal:
                    if led_shot:
                        ax.scatter(row["x"], row["y"], s=150, color=col, edgecolor=config.BG_COLOR, zorder=2)
                        shot_count += 1
                    else:
                        ax.scatter(row["x"], row["y"], s=100, color="None", edgecolor=col, zorder=2)
                        other_count += 1
        return goal_count, shot_count, other_count

    hg, hsh, ho = analyze(home, hcol)
    ag, ash, ao = analyze(away, acol)

    ax.text(0, 69, f"{home}\nHTO: {hg + hsh + ho} (Goal: {hg} · Shot: {hsh})", color=hcol,
            fontsize=18, fontweight="bold", ha="left", va="bottom")
    ax.text(105, 69, f"{away}\nHTO: {ag + ash + ao} (Goal: {ag} · Shot: {ash})", color=acol,
            fontsize=18, fontweight="bold", ha="right", va="bottom")
    return {"Home_High_Turnovers": hg + hsh + ho, "Away_High_Turnovers": ag + ash + ao}


# --------------------------------------------------------------------------- #
# Congestion
# --------------------------------------------------------------------------- #
def congestion(ax, df, home, away, hcol, acol) -> None:
    cmap = LinearSegmentedColormap.from_list("cong", [acol, "gray", hcol], N=20)
    df1 = df[(df["teamName"] == home) & (df["isTouch"] == 1)
             & (~df["qualifiers"].str.contains("CornerTaken|Freekick|ThrowIn", na=False))]
    df2 = df[(df["teamName"] == away) & (df["isTouch"] == 1)
             & (~df["qualifiers"].str.contains("CornerTaken|Freekick|ThrowIn", na=False))].copy()
    df2["x"] = 105 - df2["x"]
    df2["y"] = 68 - df2["y"]

    pitch = make_pitch(line_zorder=6)
    pitch.draw(ax=ax)
    style_ax(ax)

    bin1 = pitch.bin_statistic(df1.x, df1.y, bins=(6, 5), statistic="count", normalize=False)
    bin2 = pitch.bin_statistic(df2.x, df2.y, bins=(6, 5), statistic="count", normalize=False)

    cx = np.array([[8.75, 26.25, 43.75, 61.25, 78.75, 96.25]] * 5)
    cy = np.array([[61.2] * 6, [47.6] * 6, [34.0] * 6, [20.4] * 6, [6.8] * 6])

    values = []
    for i in range(bin1["statistic"].shape[0]):
        for j in range(bin1["statistic"].shape[1]):
            s1, s2 = bin1["statistic"][i, j], bin2["statistic"][i, j]
            if s1 + s2 == 0:
                values.append(0.5)
            elif (s1 / (s1 + s2)) > 0.55:
                values.append(1.0)
            elif (s2 / (s1 + s2)) > 0.55:
                values.append(0.0)
            else:
                values.append(0.5)

    pitch.scatter(cx.flatten(), cy.flatten(), s=1800, c=values, cmap=cmap,
                  edgecolors=config.LINE_COLOR, linewidth=1.5, ax=ax, zorder=5)
    for x, y, v in zip(cx.flatten(), cy.flatten(), values):
        pct = int(max(v, 1 - v) * 100) if v not in (0.5,) else 50
        ax.text(x, y, f"{pct}%", color=config.LINE_COLOR, fontsize=12, fontweight="bold",
                ha="center", va="center", zorder=7, path_effects=path_eff())

    ax.text(0, 69, f"{home} touches", color=hcol, fontsize=20, fontweight="bold", ha="left", va="bottom")
    ax.text(105, 69, f"{away} touches", color=acol, fontsize=20, fontweight="bold", ha="right", va="bottom")
    ax.set_title("Congestion Map (Open-Play Touches)", color=config.LINE_COLOR, fontsize=25,
                 fontweight="bold", path_effects=path_eff())
