#!/usr/bin/env python3
"""
render_report.py — turn a scraped match bundle into a modern match report.

Reads the bundle produced by scrape_match.py (events.csv, shots.csv, meta.json,
xt_grid.csv) and renders:

  * report.png  — a dark, editorial-style dashboard (passing networks, shot map,
                  defensive actions, progressive passes, xG timeline + momentum,
                  match stats) with each team's real colors.
  * report.html — a self-contained page embedding the dashboard plus stat tables
                  and auto-generated takeaways.

Usage
-----
    python render_report.py --data ./data --out ./report
    python render_report.py --data ./data --out ./report --theme cobalt
    python render_report.py --data ./data --no-html          # PNG only

The report is generated from the scraped data only — no network access needed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, to_rgba
from mplsoccer import Pitch

# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #
THEMES = {
    "cobalt": {  # deep navy editorial (default)
        "bg": "#0A0E1A",
        "panel": "#101828",
        "line": "#CBD5E1",
        "muted": "#94A3B8",
        "accent": "#38BDF8",
        "text": "#F8FAFC",
    },
    "midnight": {
        "bg": "#0C0D0E",
        "panel": "#16181D",
        "line": "#FFFFFF",
        "muted": "#9CA3AF",
        "accent": "#43A1D5",
        "text": "#FFFFFF",
    },
    "paper": {  # light editorial
        "bg": "#F6F5F1",
        "panel": "#FFFFFF",
        "line": "#1F2937",
        "muted": "#6B7280",
        "accent": "#111827",
        "text": "#111827",
    },
}

FALLBACK_COLORS = {"home": "#38BDF8", "away": "#F87171"}


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def load_bundle(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict, np.ndarray]:
    events = pd.read_csv(data_dir / "events.csv")
    # Auto-convert legacy WhoScored 0-100 coordinates to StatsBomb 120x80
    if "x" in events.columns and events["x"].dropna().max() > 120.5:
        for col, scale in (("x", 1.2), ("y", 0.8), ("end_x", 1.2), ("end_y", 0.8)):
            if col in events.columns:
                events[col] = events[col].astype(float) * scale
    shots = pd.read_csv(data_dir / "shots.csv") if (data_dir / "shots.csv").exists() else pd.DataFrame()
    meta = json.loads((data_dir / "meta.json").read_text()) if (data_dir / "meta.json").exists() else {}
    xt = pd.read_csv(data_dir / "xt_grid.csv", header=None).values if (data_dir / "xt_grid.csv").exists() else None
    return events, shots, meta, xt


def team_colors(meta: dict, events: pd.DataFrame) -> tuple[str, str]:
    """Real team colors from FotMob shotmap; fall back to a data-driven guess."""
    colors = meta.get("colors") or {}
    # JSON round-trip makes numeric ids strings; normalize to int keys.
    colors = {int(k) if str(k).isdigit() else k: v for k, v in colors.items()}
    home_fm = (meta.get("teams", {}).get("home") or {}).get("fotmob_id")
    away_fm = (meta.get("teams", {}).get("away") or {}).get("fotmob_id")
    home_c = colors.get(home_fm) if home_fm in colors else None
    away_c = colors.get(away_fm) if away_fm in colors else None

    # Last resort: derive from shot colors already present in events-shots merge
    if not home_c and "team_color" in events.columns:
        pass  # handled in shot map directly

    return home_c or FALLBACK_COLORS["home"], away_c or FALLBACK_COLORS["away"]


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def qualifier_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add boolean qualifier flags (Longball, BigChance, CornerTaken, OwnGoal, ...)."""
    df = df.copy()
    if "qualifiers" in df.columns:
        q = df["qualifiers"].fillna("").astype(str)
        for name in ("Longball", "BigChance", "CornerTaken", "Freekick", "OwnGoal", "Head"):
            df[f"q_{name}"] = q.str.contains(name, na=False)
    return df


def calculate_match_stats(events: pd.DataFrame, hteam_id, ateam_id) -> dict:
    """Core match stats from the WhoScored event stream (data-driven, no hardcoding)."""
    df = qualifier_flags(events)
    st = {}

    def has(team, types, outcome=None):
        mask = df["team_id"] == team
        mask &= df["type_display_name"].isin(types)
        if outcome:
            mask &= df["outcome_type_display_name"] == outcome
        return len(df[mask])

    home_passes = has(hteam_id, ["Pass"])
    away_passes = has(ateam_id, ["Pass"])
    total = home_passes + away_passes
    st["Possession"] = {
        "home": round(home_passes / total * 100, 1) if total else 50.0,
        "away": round(away_passes / total * 100, 1) if total else 50.0,
    }

    st["Passes (Acc.)"] = {
        "home": has(hteam_id, ["Pass"], "Successful"),
        "away": has(ateam_id, ["Pass"], "Successful"),
    }
    st["LongBalls (Acc.)"] = {
        "home": len(df[(df.team_id == hteam_id) & df.q_Longball & (df.outcome_type_display_name == "Successful")]),
        "away": len(df[(df.team_id == ateam_id) & df.q_Longball & (df.outcome_type_display_name == "Successful")]),
    }
    st["Tackles (Wins)"] = {
        "home": has(hteam_id, ["Tackle"], "Successful"),
        "away": has(ateam_id, ["Tackle"], "Successful"),
    }
    st["Interceptions"] = {"home": has(hteam_id, ["Interception"]), "away": has(ateam_id, ["Interception"])}
    st["Clearances"] = {"home": has(hteam_id, ["Clearance"]), "away": has(ateam_id, ["Clearance"])}
    st["Aerials (Wins)"] = {
        "home": has(hteam_id, ["Aerial"], "Successful"),
        "away": has(hteam_id, ["Aerial"], "Successful"),
    }

    # PPDA: opponent passes in own 60% / defensive actions in opponent 40%
    def ppda(def_team, opp_team):
        opp_passes = len(
            df[(df.team_id == opp_team) & (df.type_display_name == "Pass")
               & (df.outcome_type_display_name == "Successful") & (df.x < 72)]
        )
        def_actions = len(
            df[(df.team_id == def_team)
               & df.type_display_name.isin(["Interception", "Tackle", "Foul", "Challenge"])
               & (df.x > 48)]
        )
        return round(opp_passes / def_actions, 2) if def_actions else None

    st["PPDA"] = {"home": ppda(hteam_id, ateam_id), "away": ppda(ateam_id, hteam_id)}

    # Field tilt: touches in final third (x > 96 on StatsBomb pitch)
    def tilt(team):
        return len(df[(df.team_id == team) & df.is_touch & (df.x > 96)])

    h_t, a_t = tilt(hteam_id), tilt(ateam_id)
    total_t = h_t + a_t
    st["Field Tilt"] = {
        "home": round(h_t / total_t * 100, 1) if total_t else 50.0,
        "away": round(a_t / total_t * 100, 1) if total_t else 50.0,
    }

    # High turnovers: recoveries in the attacking third (x > 80)
    st["High Turnovers"] = {
        "home": len(df[(df.team_id == hteam_id)
                       & df.type_display_name.isin(["BallRecovery", "Interception"])
                       & (df.x > 80)]),
        "away": len(df[(df.team_id == ateam_id)
                       & df.type_display_name.isin(["BallRecovery", "Interception"])
                       & (df.x > 80)]),
    }

    # Progressive passes (successful passes that move play ≥10m toward the goal
    # the team attacks, starting from the middle third)
    def progressive(team):
        team_df = df[(df.team_id == team) & (df.type_display_name == "Pass")
                     & (df.outcome_type_display_name == "Successful")
                     & ~df.q_CornerTaken & ~df.q_Freekick & (df.x >= 42)].copy()
        team_df["prog_dist"] = team_df["end_x"] - team_df["x"]
        return len(team_df[team_df.prog_dist >= 10])

    st["Progressive Passes"] = {"home": progressive(hteam_id), "away": progressive(ateam_id)}

    # Passing accuracy
    def acc(team):
        p = has(team, ["Pass"])
        return round(has(team, ["Pass"], "Successful") / p * 100, 1) if p else None

    st["Pass Accuracy %"] = {"home": acc(hteam_id), "away": acc(ateam_id)}

    return st


def shot_stats(shots: pd.DataFrame, hteam_id, ateam_id) -> dict:
    """xG/shots summary per team from the FotMob shot map."""
    out = {}
    for key, tid in (("home", hteam_id), ("away", ateam_id)):
        team = shots[shots["team_id"] == tid] if "team_id" in shots.columns else pd.DataFrame()
        if len(team) == 0:
            team = shots[shots["teamId"] == tid] if "teamId" in shots.columns else pd.DataFrame()
        goals = int(((team.get("eventType") == "Goal") & ~team.get("isOwnGoal", False)).sum()) if len(team) else 0
        out[key] = {
            "goals": goals,
            "xg": round(float(team["expectedGoals"].sum()), 2) if len(team) and "expectedGoals" in team else 0.0,
            "shots": len(team),
            "on_target": int(team.get("isOnTarget", pd.Series(dtype=bool)).sum()) if len(team) else 0,
            "big_chances": int(team.get("is_big_chance", pd.Series(dtype=bool)).sum()) if len(team) else 0,
            "inside_box": int(team.get("isFromInsideBox", pd.Series(dtype=bool)).sum()) if len(team) else 0,
        }
    return out


def xg_timeline(shots: pd.DataFrame, hteam_id, ateam_id, max_minute: int = 120) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cumulative xG per team across match minutes (for the xG line chart)."""
    minutes = np.arange(0, max_minute + 1)
    home_xg = np.zeros_like(minutes, dtype=float)
    away_xg = np.zeros_like(minutes, dtype=float)
    if len(shots) == 0 or "expectedGoals" not in shots.columns:
        return minutes, home_xg, away_xg

    for _, s in shots.iterrows():
        m = int(s.get("min", 0) or 0)
        if m > max_minute:
            continue
        xg = float(s.get("expectedGoals", 0) or 0)
        if s.get("team_id", s.get("teamId")) == hteam_id:
            home_xg[m:] += xg
        elif s.get("team_id", s.get("teamId")) == ateam_id:
            away_xg[m:] += xg
    return minutes, home_xg, away_xg


# --------------------------------------------------------------------------- #
# Pitch helpers
# --------------------------------------------------------------------------- #
def make_pitch(theme: dict) -> Pitch:
    return Pitch(
        pitch_type="statsbomb",
        pitch_color=theme["bg"],
        line_color=theme["line"],
        linewidth=1.5,
        line_zorder=2,
        corner_arcs=True,
    )


def style_ax(ax, theme: dict, title: str, sub: str = ""):
    ax.set_facecolor(theme["bg"])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    title_txt = f"{title}\n{sub}" if sub else title
    ax.set_title(title_txt, color=theme["text"], fontsize=13, fontweight="bold", pad=12)


# --------------------------------------------------------------------------- #
# Panels
# --------------------------------------------------------------------------- #
def panel_passing_network(ax, events, team_id, players_info, team_color, theme, title):
    """Passing network: nodes at avg positions, edges by completed-pass count."""
    pitch = make_pitch(theme)
    pitch.draw(ax=ax)

    passes = events[
        (events["team_id"] == team_id)
        & (events["type_display_name"] == "Pass")
        & (events["outcome_type_display_name"] == "Successful")
    ].copy()

    if len(passes) == 0 or "player_id" not in passes.columns:
        style_ax(ax, theme, title, "no pass data")
        return

    passes["receiver"] = passes["player_id"].shift(-1)
    passes = passes.dropna(subset=["player_id", "receiver"])
    passes = passes[passes["receiver"] != passes["player_id"]]

    locs = passes.groupby("player_id").agg(x=("x", "median"), y=("y", "median"), n=("player_id", "count"))
    locs = locs[locs["n"] >= 5]

    comb = (
        passes.merge(locs[["x", "y"]], left_on="player_id", right_index=True)
        .merge(locs[["x", "y"]], left_on="receiver", right_index=True, suffixes=("", "_end"))
        .groupby(["player_id", "receiver"])
        .size()
        .reset_index(name="count")
    )
    comb = comb[comb["count"] >= 3]

    # Edges
    max_count = comb["count"].max()
    for _, row in comb.iterrows():
        if row["player_id"] not in locs.index or row["receiver"] not in locs.index:
            continue
        x1, y1 = locs.loc[row["player_id"], "x"], locs.loc[row["player_id"], "y"]
        x2, y2 = locs.loc[row["receiver"], "x"], locs.loc[row["receiver"], "y"]
        alpha = min(0.18 + row["count"] / max_count * 0.6, 0.9)
        ax.plot([x1, x2], [y1, y2], color=team_color, alpha=alpha, lw=1.2, zorder=2)

    # Nodes
    sizes = 180 + (locs["n"] / locs["n"].max()) * 700
    ax.scatter(locs["x"], locs["y"], s=sizes, color=team_color, edgecolors=theme["bg"],
               linewidth=1.5, alpha=0.92, zorder=3)

    # Names for starters with most touches
    top = locs.nlargest(6, "n")
    for pid, row in top.iterrows():
        name = (players_info.get(str(pid)) or {}).get("name")
        if not name:
            continue
        ax.text(row["x"], row["y"] + 2.8, name.split()[-1], ha="center", va="bottom",
                color=theme["text"], fontsize=7.5, fontweight="bold", zorder=4)

    style_ax(ax, theme, title, f"{len(comb)} connections · {len(locs)} players")


def panel_shot_map(ax, shots, meta, home_color, away_color, theme):
    """Combined shot map for both teams with xG-scaled markers."""
    pitch = make_pitch(theme)
    pitch.draw(ax=ax)

    if len(shots) == 0 or "x" not in shots.columns:
        style_ax(ax, theme, "Shot Map", "no shot data")
        return

    h_id = (meta.get("teams", {}).get("home") or {}).get("fotmob_id")
    a_id = (meta.get("teams", {}).get("away") or {}).get("fotmob_id")
    # FotMob x/y are 0-100 (% of pitch); scale to StatsBomb 120x80
    shots = shots.copy()
    shots["x_sb"] = shots["x"] / 100 * 120
    shots["y_sb"] = shots["y"] / 100 * 80

    def plot_team(team_df, color, goal_side):
        if len(team_df) == 0:
            return
        for _, s in team_df.iterrows():
            x, y = s["x_sb"], s["y_sb"]
            if goal_side == "left":  # home attacks left goal -> flip
                x, y = 120 - x, 80 - y
            is_goal = s.get("eventType") == "Goal" and not s.get("isOwnGoal", False)
            xg = float(s.get("expectedGoals", 0) or 0)
            size = 120 + xg * 900
            if is_goal:
                ax.scatter(x, y, s=size, color=color, edgecolors="white", linewidth=2, zorder=4)
                ax.text(x, y - 2.5, "⚽", ha="center", va="center", color="white", fontsize=11, zorder=5)
            else:
                face = "none" if not s.get("isOnTarget", False) else color
                ax.scatter(x, y, s=size, facecolors=face, edgecolors=color,
                           linewidth=1.6, zorder=3)
                if xg >= 0.25:
                    ax.text(x, y, f"{xg:.2f}", ha="center", va="center",
                            color="white" if s.get("isOnTarget", False) else color,
                            fontsize=6.5, fontweight="bold", zorder=5)

    plot_team(shots[shots["team_id"] == h_id] if "team_id" in shots.columns else shots, home_color, "left")
    plot_team(shots[shots["team_id"] == a_id] if "team_id" in shots.columns else shots, away_color, "right")

    hname = (meta.get("teams", {}).get("home") or {}).get("name", "Home")
    aname = (meta.get("teams", {}).get("away") or {}).get("name", "Away")
    # Team labels at each end
    ax.text(5, 75, f"{hname}", color=home_color, fontsize=11, fontweight="bold", ha="left")
    ax.text(115, 75, f"{aname}", color=away_color, fontsize=11, fontweight="bold", ha="right")
    # Legend box (top center)
    leg_x, leg_y = 60, 75
    ax.scatter(leg_x - 11, leg_y, s=110, facecolors="none", edgecolors=theme["muted"], linewidth=1.4)
    ax.scatter(leg_x - 5, leg_y, s=260, facecolors="none", edgecolors=theme["muted"], linewidth=1.4)
    ax.scatter(leg_x + 2, leg_y, s=110, facecolors=theme["muted"], edgecolors=theme["muted"], linewidth=1.4)
    ax.text(leg_x + 7, leg_y + 2.5, "xG", color=theme["muted"], fontsize=8, fontweight="bold")
    ax.text(leg_x + 7, leg_y - 2.5, "on target", color=theme["muted"], fontsize=7.5)
    style_ax(ax, theme, "Shot Map")


def panel_defensive_actions(ax, events, team_id, team_color, theme, title):
    """KDE heatmap of defensive actions + player nodes sized by action count."""
    pitch = make_pitch(theme)
    pitch.draw(ax=ax)

    types = ["Tackle", "Interception", "BallRecovery", "BlockedPass", "Challenge", "Clearance", "Foul", "Aerial"]
    actions = events[(events["team_id"] == team_id) & (events["type_display_name"].isin(types))]

    if len(actions) == 0:
        style_ax(ax, theme, title, "no defensive actions")
        return

    cmap = LinearSegmentedColormap.from_list("team", [theme["bg"], team_color], N=256)
    pitch.kdeplot(actions["x"], actions["y"], ax=ax, fill=True, levels=60,
                  thresh=0.02, cut=4, cmap=cmap, zorder=1)

    pos = actions.groupby("player_id").agg(x=("x", "median"), y=("y", "median"), n=("player_id", "count"))
    sizes = 200 + (pos["n"] / pos["n"].max()) * 1200
    ax.scatter(pos["x"], pos["y"], s=sizes, color=theme["bg"], edgecolors=team_color,
               linewidth=1.8, alpha=0.95, zorder=3)
    style_ax(ax, theme, title, f"{len(actions)} defensive actions")


def panel_progressive_passes(ax, events, team_id, team_color, theme, title):
    """Progressive passes with comet arrows + final-third zone split."""
    pitch = make_pitch(theme)
    pitch.draw(ax=ax)

    df = qualifier_flags(events)
    prog = df[
        (df["team_id"] == team_id)
        & (df["type_display_name"] == "Pass")
        & (df["outcome_type_display_name"] == "Successful")
        & ~df.q_CornerTaken & ~df.q_Freekick
        & (df["x"] >= 42)
    ].copy()
    if len(prog):
        prog["prog_dist"] = prog["end_x"] - prog["x"]
        prog = prog[prog["prog_dist"] >= 10]

    if len(prog) == 0:
        style_ax(ax, theme, title, "no progressive passes")
        return

    pitch.lines(prog["x"], prog["y"], prog["end_x"], prog["end_y"], ax=ax,
                lw=2.2, comet=True, color=team_color, alpha=0.55, zorder=2)
    pitch.scatter(prog["end_x"], prog["end_y"], s=18, ax=ax, color=team_color,
                  edgecolors=theme["bg"], linewidth=0.8, zorder=3)

    # Final-third zone split (attack direction assumed left->right)
    final_third = prog[prog["end_x"] >= 80]
    left = int((final_third["end_y"] >= 53.33).sum())
    mid = int(((final_third["end_y"] >= 26.67) & (final_third["end_y"] < 53.33)).sum())
    right = int((final_third["end_y"] < 26.67).sum())
    style_ax(ax, theme, title, f"{len(prog)} progressive passes · final ⅓: {left}L/{mid}C/{right}R")


def panel_momentum(ax, events, meta, hteam_id, ateam_id, home_color, away_color, theme):
    """Match momentum: native FotMob series when available, else xT-based."""
    ax.set_facecolor(theme["bg"])
    for s in ax.spines.values():
        s.set_color(theme["line"])
    ax.tick_params(colors=theme["muted"], labelsize=8)

    minutes, home_xg, away_xg = xg_timeline(
        pd.read_csv(meta.get("_shots_path", "")) if meta.get("_shots_path") else pd.DataFrame(),
        hteam_id, ateam_id,
    )

    momentum = meta.get("momentum") or []
    if momentum:
        mins = [m["minute"] for m in momentum]
        vals = [m["value"] for m in momentum]
        ax.axhline(0, color=theme["line"], lw=0.8, alpha=0.5)
        ax.fill_between(mins, vals, where=(np.array(vals) > 0), color=home_color, alpha=0.45, interpolate=True)
        ax.fill_between(mins, vals, where=(np.array(vals) < 0), color=away_color, alpha=0.45, interpolate=True)
        ax.plot(mins, vals, color=theme["text"], lw=1.4)
        ax.set_title("Match Momentum (FotMob)", color=theme["text"], fontsize=13, fontweight="bold", pad=12)
        ax.set_xlabel("Minute", color=theme["muted"], fontsize=9)
        ax.set_ylabel("Home − Away", color=theme["muted"], fontsize=9)
    else:
        ax.text(0.5, 0.5, "no momentum data", transform=ax.transAxes,
                ha="center", va="center", color=theme["muted"], fontsize=12)
        ax.set_title("Match Momentum", color=theme["text"], fontsize=13, fontweight="bold", pad=12)


def panel_stats(ax, stats, hname, aname, home_color, away_color, theme):
    """Center-out comparison bars, The-Athletic style."""
    ax.set_facecolor(theme["bg"])
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    rows = [k for k in stats if stats[k].get("home") is not None or stats[k].get("away") is not None]
    rows = rows[:9]
    n = len(rows)
    y = np.linspace(0.92, 0.12, n) if n else [0.5]

    # Team headers
    ax.text(0.18, 0.98, hname, ha="center", va="center", color=home_color, fontsize=12, fontweight="bold")
    ax.text(0.82, 0.98, aname, ha="center", va="center", color=away_color, fontsize=12, fontweight="bold")

    for yi, key in zip(y, rows):
        h = stats[key].get("home") or 0
        a = stats[key].get("away") or 0
        total = h + a
        hw = (h / total * 0.6) if total else 0.3
        aw = (a / total * 0.6) if total else 0.3
        ax.barh(yi, hw, left=0.2 - hw, height=0.028, color=home_color, alpha=0.9)
        ax.barh(yi, aw, left=0.8, height=0.028, color=away_color, alpha=0.9)
        # values outside the bars
        ax.text(0.2 - hw - 0.015, yi, str(h), ha="right", va="center", color=theme["text"],
                fontsize=10, fontweight="bold")
        ax.text(0.8 + aw + 0.015, yi, str(a), ha="left", va="center", color=theme["text"],
                fontsize=10, fontweight="bold")
        # centered label below bars
        ax.text(0.5, yi - 0.045, key, ha="center", va="top", color=theme["muted"],
                fontsize=8.5, fontweight="bold")


def panel_xg_timeline(ax, shots, hteam_id, ateam_id, home_color, away_color, theme):
    """Cumulative xG lines over the match."""
    ax.set_facecolor(theme["bg"])
    for s in ax.spines.values():
        s.set_color(theme["line"])
    ax.tick_params(colors=theme["muted"], labelsize=8)

    minutes, home_xg, away_xg = xg_timeline(shots, hteam_id, ateam_id)
    if home_xg.max() == 0 and away_xg.max() == 0:
        ax.text(0.5, 0.5, "no xG data", transform=ax.transAxes, ha="center",
                va="center", color=theme["muted"], fontsize=12)
    else:
        ax.plot(minutes, home_xg, color=home_color, lw=2.2, label="Home xG")
        ax.plot(minutes, away_xg, color=away_color, lw=2.2, label="Away xG")
        ax.fill_between(minutes, home_xg, color=home_color, alpha=0.12)
        ax.fill_between(minutes, away_xg, color=away_color, alpha=0.12)
        ax.legend(loc="upper left", fontsize=8, facecolor=theme["bg"], edgecolor=theme["line"],
                  labelcolor=theme["text"])
    ax.set_title("xG Timeline", color=theme["text"], fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Minute", color=theme["muted"], fontsize=9)
    ax.set_ylabel("Cumulative xG", color=theme["muted"], fontsize=9)


# --------------------------------------------------------------------------- #
# Dashboard assembly
# --------------------------------------------------------------------------- #
def parse_score(raw) -> tuple | None:
    """Normalize WhoScored score formats (dict, list, or '0 : 3' string)."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        h, a = raw.get("home"), raw.get("away")
        return (h, a) if h is not None and a is not None else None
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return (raw[0], raw[1])
    if isinstance(raw, str):
        import re
        m = re.findall(r"\d+", raw)
        return (int(m[0]), int(m[1])) if len(m) >= 2 else None
    return None


def fotmob_stats_to_panel(meta: dict) -> dict:
    """Build the stats-panel dict from FotMob's own stats (FotMob-only mode)."""
    periods = meta.get("stats") or {}
    block = periods.get("All") or next(iter(periods.values()), {})
    by_key = {k: v for k, v in block.items()}
    out = {}

    def val(key):
        v = by_key.get(key)
        if not v or not v.get("values"):
            return None
        vals = v["values"]
        return (vals[0], vals[1]) if len(vals) >= 2 else (None, None)

    def num(x):
        if x is None:
            return None
        s = str(x)
        m = re.search(r"[\d.]+", s)
        return float(m.group()) if m else None

    def pct_pair(key):
        pair = val(key)
        if pair is None:
            return {"home": None, "away": None}
        h, a = pair
        if h is None or a is None:
            return {"home": None, "away": None}
        return {"home": num(h), "away": num(a)}

    def int_pair(key):
        pair = val(key)
        if pair is None:
            return {"home": None, "away": None}
        h, a = pair
        if h is None or a is None:
            return {"home": None, "away": None}
        return {"home": int(num(h) or 0), "away": int(num(a) or 0)}

    out["Possession"] = pct_pair("BallPossesion")
    out["Expected Goals (xG)"] = pct_pair("expected_goals")
    out["Shots"] = int_pair("total_shots")
    out["Shots on Target"] = int_pair("ShotsOnTarget")
    out["Touches (Opp. Box)"] = int_pair("touches_opp_box")
    out["Big Chances"] = int_pair("big_chance")
    out["Accurate Passes"] = {
        "home": by_key.get("accurate_passes", {}).get("values", [None, None])[0] if by_key.get("accurate_passes") else None,
        "away": by_key.get("accurate_passes", {}).get("values", [None, None])[1] if by_key.get("accurate_passes") else None,
    }
    out["Corners"] = int_pair("corners")
    out["Yellow Cards"] = int_pair("yellow_cards")
    out["xG Open Play"] = pct_pair("expected_goals_open_play")
    out["xG Set Play"] = pct_pair("expected_goals_set_play")
    out["xGOT"] = pct_pair("expected_goals_on_target")
    out["Long Balls (Acc.)"] = {
        "home": by_key.get("long_balls_accurate", {}).get("values", [None, None])[0] if by_key.get("long_balls_accurate") else None,
        "away": by_key.get("long_balls_accurate", {}).get("values", [None, None])[1] if by_key.get("long_balls_accurate") else None,
    }
    # drop empty rows
    return {k: v for k, v in out.items() if v.get("home") is not None or v.get("away") is not None}


def build_dashboard(events, shots, meta, xt, theme: dict) -> plt.Figure:
    teams = meta.get("teams", {})
    hname = (teams.get("home") or {}).get("name", "Home")
    aname = (teams.get("away") or {}).get("name", "Away")
    hteam_id = (teams.get("home") or {}).get("who_scored_id")
    ateam_id = (teams.get("away") or {}).get("who_scored_id")
    home_color, away_color = team_colors(meta, events)

    score = parse_score(meta.get("score")) or parse_score(meta.get("ft_score")) or (0, 0)
    hg, ag = score

    stats = calculate_match_stats(events, hteam_id, ateam_id)
    if not stats or all(v.get("home") is None and v.get("away") is None for v in stats.values()):
        stats = fotmob_stats_to_panel(meta)  # FotMob-only bundle
    sstats = shot_stats(shots, (teams.get("home") or {}).get("fotmob_id"),
                        (teams.get("away") or {}).get("fotmob_id"))

    # Player name lookup from raw matchdict if available (passed via meta._players)
    players_info = meta.get("_players") or {}

    fig = plt.figure(figsize=(22, 15), facecolor=theme["bg"])
    gs = fig.add_gridspec(4, 6, height_ratios=[0.55, 1, 1, 1], hspace=0.42, wspace=0.30,
                          left=0.03, right=0.97, top=0.90, bottom=0.03)

    # --- Header ---
    header = fig.add_subplot(gs[0, :])
    header.set_facecolor(theme["bg"])
    header.axis("off")
    header.set_xlim(0, 1)
    header.set_ylim(0, 1)

    # Score line (center, big)
    header.text(0.5, 0.62, f"{hg}  –  {ag}", ha="center", va="center",
                color=theme["text"], fontsize=44, fontweight="bold")
    # Competition / venue / date (above score)
    sub = meta.get("competition") or ""
    if meta.get("start_date"):
        sub = (sub + "  ·  " if sub else "") + str(meta["start_date"])[:10]
    header.text(0.5, 0.90, sub.strip(), ha="center", va="center", color=theme["muted"],
                fontsize=12, fontweight="bold")
    # Team names + colors (left / right)
    header.text(0.18, 0.62, hname, ha="center", va="center", color=home_color,
                fontsize=19, fontweight="bold")
    header.text(0.82, 0.62, aname, ha="center", va="center", color=away_color,
                fontsize=19, fontweight="bold")
    # Venue + attendance (bottom center)
    foot = []
    if meta.get("venue"):
        foot.append(str(meta["venue"]))
    if meta.get("attendance"):
        foot.append(f"att. {meta['attendance']:,}")
    if meta.get("referee"):
        ref = meta["referee"]
        if isinstance(ref, dict):
            ref = ref.get("name") or f"{ref.get('firstName', '')} {ref.get('lastName', '')}".strip()
        if ref:
            foot.append(f"ref. {ref}")
    if foot:
        header.text(0.5, 0.10, "  ·  ".join(foot), ha="center", va="center",
                    color=theme["muted"], fontsize=10)

    # --- Row 1: passing networks + shot map ---
    panel_passing_network(fig.add_subplot(gs[1, 0:2]), events, hteam_id, players_info, home_color, theme, f"{hname} Passing Network")
    panel_shot_map(fig.add_subplot(gs[1, 2:4]), shots, meta, home_color, away_color, theme)
    panel_passing_network(fig.add_subplot(gs[1, 4:6]), events, ateam_id, players_info, away_color, theme, f"{aname} Passing Network")

    # --- Row 2: defensive actions + xG timeline + momentum ---
    panel_defensive_actions(fig.add_subplot(gs[2, 0:2]), events, hteam_id, home_color, theme, f"{hname} Defensive Actions")
    panel_xg_timeline(fig.add_subplot(gs[2, 2:4]), shots, (teams.get("home") or {}).get("fotmob_id"),
                      (teams.get("away") or {}).get("fotmob_id"), home_color, away_color, theme)
    panel_defensive_actions(fig.add_subplot(gs[2, 4:6]), events, ateam_id, away_color, theme, f"{aname} Defensive Actions")

    # --- Row 3: progressive passes + stats + momentum ---
    panel_progressive_passes(fig.add_subplot(gs[3, 0:2]), events, hteam_id, home_color, theme, f"{hname} Progressive Passes")
    panel_stats(fig.add_subplot(gs[3, 2:4]), stats, hname, aname, home_color, away_color, theme)
    panel_progressive_passes(fig.add_subplot(gs[3, 4:6]), events, ateam_id, away_color, theme, f"{aname} Progressive Passes")

    # Keep stats + xG for the HTML report
    fig._report_data = {"stats": stats, "shot_stats": sstats}
    return fig


# --------------------------------------------------------------------------- #
# HTML report
# --------------------------------------------------------------------------- #
def build_html(out_png: Path, events, shots, meta, theme_name: str) -> str:
    teams = meta.get("teams", {})
    hname = (teams.get("home") or {}).get("name", "Home")
    aname = (teams.get("away") or {}).get("name", "Away")
    score = parse_score(meta.get("score")) or parse_score(meta.get("ft_score")) or (0, 0)
    hg, ag = score

    stats = calculate_match_stats(events, (teams.get("home") or {}).get("who_scored_id"),
                                  (teams.get("away") or {}).get("who_scored_id"))
    if not stats or all(v.get("home") is None and v.get("away") is None for v in stats.values()):
        stats = fotmob_stats_to_panel(meta)  # FotMob-only bundle
    sstats = shot_stats(shots, (teams.get("home") or {}).get("fotmob_id"),
                        (teams.get("away") or {}).get("fotmob_id"))

    # Stats table rows
    stat_rows = []
    for key, vals in stats.items():
        h = vals.get("home")
        a = vals.get("away")
        h_disp = "–" if h is None else h
        a_disp = "–" if a is None else a
        stat_rows.append(f"<tr><td class='h'>{h_disp}</td><td class='k'>{key}</td><td class='a'>{a_disp}</td></tr>")

    # Shot/xG table
    shot_rows = []
    for key, label in (("home", hname), ("away", aname)):
        s = sstats.get(key, {})
        shot_rows.append(
            f"<tr><td class='k'>{label}</td><td>{s.get('goals', 0)}</td><td>{s.get('xg', 0)}</td>"
            f"<td>{s.get('shots', 0)}</td><td>{s.get('on_target', 0)}</td><td>{s.get('big_chances', 0)}</td></tr>"
        )

    # Takeaways
    takes = []
    hs, as_ = sstats.get("home", {}), sstats.get("away", {})
    if hs.get("shots") or as_.get("shots"):
        leader = hname if hs.get("xg", 0) >= as_.get("xg", 0) else aname
        takes.append(f"<b>{leader}</b> led expected goals ({max(hs.get('xg',0), as_.get('xg',0)):.2f} xG) — "
                     f"vs {min(hs.get('xg',0), as_.get('xg',0)):.2f} for the opponent.")
    pom = meta.get("player_of_match")
    if pom:
        takes.append(f"Player of the match: <b>{pom.get('name')}</b> "
                     f"({pom.get('team')}, rating {pom.get('rating')}).")
    if stats.get("High Turnovers"):
        ht = stats["High Turnovers"]
        if ht.get("home") or ht.get("away"):
            h_t, a_t = ht["home"], ht["away"]
            takes.append(f"High turnovers (recoveries in the attacking third): {hname} {h_t} — {aname} {a_t}.")
    if not takes:
        takes.append("Scrape with the FotMob match id to unlock xG, momentum and player-of-the-match insights.")

    pom_block = ""
    if pom:
        pom_block = f"<div class='pom'><span class='tag'>POTM</span> {pom.get('name')} · {pom.get('team')} · ⭐ {pom.get('rating')}</div>"

    img_b64 = "data:image/png;base64," + _b64(out_png)
    dark = theme_name != "paper"

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Match Report — {hname} vs {aname}</title>
<style>
  :root {{ --bg: {'#0A0E1A' if dark else '#F6F5F1'}; --panel: {'#101828' if dark else '#fff'};
           --text: {'#F8FAFC' if dark else '#111827'}; --muted: {'#94A3B8' if dark else '#6B7280'};
           --line: {'#1E293B' if dark else '#E5E7EB'}; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding: 32px 24px; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{ font-size: 28px; margin-bottom: 4px; }}
  .sub {{ color: var(--muted); font-size: 14px; margin-bottom: 24px; }}
  .pom {{ display:inline-block; background: #F59E0B22; border: 1px solid #F59E0B55; color: #FBBF24;
         padding: 6px 14px; border-radius: 999px; font-size: 13px; margin-bottom: 18px; }}
  .tag {{ font-weight: 700; letter-spacing: .5px; }}
  img.dash {{ width: 100%; border-radius: 14px; border: 1px solid var(--line); margin-bottom: 28px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  @media (max-width: 800px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 20px; }}
  h2 {{ font-size: 16px; margin-bottom: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  td {{ padding: 8px 6px; border-bottom: 1px solid var(--line); }}
  td.k {{ text-align: center; font-weight: 600; }}
  td.h {{ color: #38BDF8; font-weight: 700; text-align: right; }}
  td.a {{ color: #F87171; font-weight: 700; }}
  .take {{ margin: 6px 0 6px 18px; color: var(--text); font-size: 14px; line-height: 1.5; }}
  .foot {{ color: var(--muted); font-size: 12px; margin-top: 28px; text-align: center; }}
</style></head><body><div class="wrap">
  <h1>{hname} {hg} – {ag} {aname}</h1>
  <div class="sub">{meta.get('competition') or ''}{' · ' + meta['venue'] if meta.get('venue') else ''}{' · ' + str(meta.get('start_date'))[:10] if meta.get('start_date') else ''}</div>
  {pom_block}
  <img class="dash" src="{img_b64}" alt="match dashboard">
  <div class="grid">
    <div class="card"><h2>Match Stats</h2><table>{''.join(stat_rows)}</table></div>
    <div class="card"><h2>Shots &amp; xG</h2>
      <table><tr><th></th><th>Goals</th><th>xG</th><th>Shots</th><th>On Tgt</th><th>Big Ch.</th></tr>{''.join(shot_rows)}</table>
      <h2 style="margin-top:22px">Key Takeaways</h2>
      {''.join(f'<div class="take">• {t}</div>' for t in takes)}
    </div>
  </div>
  <div class="foot">Generated by the football-match-report skill · data © WhoScored / FotMob</div>
</div></body></html>"""


def _b64(path: Path) -> str:
    import base64
    return base64.b64encode(path.read_bytes()).decode()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data", help="scraped bundle directory (default: ./data)")
    ap.add_argument("--out", default="report", help="output directory (default: ./report)")
    ap.add_argument("--theme", default="cobalt", choices=list(THEMES), help="color theme (default: cobalt)")
    ap.add_argument("--no-html", action="store_true", help="skip the HTML report")
    args = ap.parse_args()

    data_dir = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    events, shots, meta, xt = load_bundle(data_dir)
    theme = THEMES[args.theme]

    # Pass raw player names through for network labels
    if (data_dir / "matchdict.json").exists():
        try:
            md = json.loads((data_dir / "matchdict.json").read_text())
            players = md.get("playerIdNameDictionary") or {}
            meta["_players"] = players
            meta.setdefault("teams", {}).setdefault("home", {}).setdefault("who_scored_id",
                                                                           (md.get("home") or {}).get("teamId"))
            meta.setdefault("teams", {}).setdefault("away", {}).setdefault("who_scored_id",
                                                                           (md.get("away") or {}).get("teamId"))
        except Exception:
            pass

    meta["_shots_path"] = str(data_dir / "shots.csv")

    fig = build_dashboard(events, shots, meta, xt, theme)
    png_path = out_dir / "match_report.png"
    fig.savefig(png_path, dpi=140, facecolor=theme["bg"])
    plt.close(fig)
    print(f"✅ Dashboard -> {png_path}")

    if not args.no_html:
        html = build_html(png_path, events, shots, meta, args.theme)
        html_path = out_dir / "match_report.html"
        html_path.write_text(html)
        print(f"✅ HTML report -> {html_path}")


if __name__ == "__main__":
    main()
