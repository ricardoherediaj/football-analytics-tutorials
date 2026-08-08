"""Team report assembly: two 4x3 figures matching the Post-Match-Report-2.0 blueprint."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from .. import config
from ..core import events as core_events
from . import defensive_block as db
from . import match_stats as ms
from . import momentum as mom
from . import pass_network as pn
from . import progressive as prog
from . import shots as shots_viz
from . import zones


def load_report_data(data_dir: Path):
    """Load bundle: master event frame, teams, colors, meta."""
    matchdict_path = data_dir / "matchdict.json"
    matchdict = json.loads(matchdict_path.read_text()) if matchdict_path.exists() else {}
    meta_path = data_dir / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    xt = core_events.load_xt_grid(data_dir / "xt_grid.csv" if (data_dir / "xt_grid.csv").exists()
                                  else Path(__file__).resolve().parent.parent / "data" / "xt_grid.csv")
    df = core_events.build_master_df(matchdict, xt)

    home = matchdict.get("home", {}).get("name", (meta.get("teams", {}).get("home") or {}).get("name", "Home"))
    away = matchdict.get("away", {}).get("name", (meta.get("teams", {}).get("away") or {}).get("name", "Away"))

    colors = meta.get("colors") or {}
    colors = {int(k) if str(k).isdigit() else k: v for k, v in colors.items()}
    home_fm = (meta.get("teams", {}).get("home") or {}).get("fotmob_id")
    away_fm = (meta.get("teams", {}).get("away") or {}).get("fotmob_id")
    hcol = colors.get(home_fm) or config.FALLBACK_HOME
    acol = colors.get(away_fm) or config.FALLBACK_AWAY

    # FotMob xG per team (from shots.csv) for the shot-map stats bar
    fotmob_xg = {}
    shots_path = data_dir / "shots.csv"
    if shots_path.exists():
        shots = pd.read_csv(shots_path)
        if "expectedGoals" in shots.columns and "team_id" in shots.columns:
            for team_key, fm_id in (("home", home_fm), ("away", away_fm)):
                team_shots = shots[shots["team_id"] == fm_id] if fm_id is not None else pd.DataFrame()
                if len(team_shots):
                    team_name = (meta.get("teams", {}).get(team_key) or {}).get("name")
                    if team_name:
                        fotmob_xg[team_name] = {
                            "xg": float(team_shots["expectedGoals"].sum()),
                            "xgot": float(team_shots.get("expectedGoalsOnTarget", pd.Series(dtype=float)).sum()),
                        }

    return df, home, away, hcol, acol, meta, matchdict, fotmob_xg


def _score_str(meta: dict) -> str:
    for key in ("score", "ft_score"):
        s = meta.get(key)
        if isinstance(s, dict) and "home" in s:
            return f"{s['home']} - {s['away']}"
        if isinstance(s, (list, tuple)) and len(s) == 2:
            return f"{s[0]} - {s[1]}"
        if isinstance(s, str):
            import re
            m = re.findall(r"\d+", s)
            if len(m) >= 2:
                return f"{m[0]} - {m[1]}"
    return ""


def build_team_report_figures(df, home, away, hcol, acol, meta, fotmob_xg: dict | None = None) -> tuple[plt.Figure, plt.Figure]:
    """Figure 1 (core) and Figure 2 (advanced zones), 4x3 each."""
    passes_df = pn.get_passes_df(df)
    h_between, h_locs = pn.get_passes_between_df(home, passes_df, df)
    a_between, a_locs = pn.get_passes_between_df(away, passes_df, df)
    def_actions = db.get_defensive_action_df(df)
    h_da_locs = db.get_da_count_df(home, def_actions, df)
    a_da_locs = db.get_da_count_df(away, def_actions, df)
    h_actions = def_actions[def_actions["teamName"] == home]
    a_actions = def_actions[def_actions["teamName"] == away]

    cmap_h = LinearSegmentedColormap.from_list("h", [config.BG_COLOR, hcol], N=20)
    cmap_a = LinearSegmentedColormap.from_list("a", [config.BG_COLOR, acol], N=20)

    # ---------------- Figure 1: core team report ----------------
    fig1, axs1 = plt.subplots(4, 3, figsize=(35, 35), facecolor=config.BG_COLOR)

    pn.pass_network_visualization(axs1[0, 0], h_between, h_locs, hcol, home, away,
                                  home_name=home, passes_df=passes_df)
    shots_viz.shot_map(axs1[0, 1], df, home, away, hcol, acol, fotmob_xg=fotmob_xg)
    pn.pass_network_visualization(axs1[0, 2], a_between, a_locs, acol, away, away,
                                  invert=True, passes_df=passes_df)

    db.defensive_block(axs1[1, 0], h_da_locs, h_actions, home, hcol, home_name=home)
    shots_viz.goalpost(axs1[1, 1], df, home, away, hcol, acol)
    db.defensive_block(axs1[1, 2], a_da_locs, a_actions, away, acol, invert=True)

    prog.progressive_pass_map(axs1[2, 0], df, home, hcol, home_name=home)
    mom.plot_momentum(axs1[2, 1], df, home, away, hcol, acol)
    prog.progressive_pass_map(axs1[2, 2], df, away, acol, invert=True)

    prog.progressive_carry_map(axs1[3, 0], df, home, hcol, home_name=home)
    ms.plot_match_stats(axs1[3, 1], df, home, away, hcol, acol)
    prog.progressive_carry_map(axs1[3, 2], df, away, acol, invert=True)

    # Score header
    score = _score_str(meta)
    fig1.text(0.5, 0.98, f"{home} {score} {away}", color=config.LINE_COLOR, fontsize=70,
              fontweight="bold", ha="center", va="center")
    comp = meta.get("competition") or ""
    fig1.text(0.5, 0.945, f"{comp} | Post Match Report — Team", color=config.LINE_COLOR,
              fontsize=30, ha="center", va="center")
    fig1.text(0.5, 0.925, "Data from: WhoScored + FotMob", color=config.LINE_COLOR,
              fontsize=22.5, ha="center", va="center")
    fig1.text(0.125, 0.1, "Attacking Direction ------->", color=hcol, fontsize=25, ha="left", va="center")
    fig1.text(0.9, 0.1, "<------- Attacking Direction", color=acol, fontsize=25, ha="right", va="center")

    # ---------------- Figure 2: advanced zones ----------------
    fig2, axs2 = plt.subplots(4, 3, figsize=(35, 35), facecolor=config.BG_COLOR)

    zones.final_third_entry(axs2[0, 0], df, home, hcol, home_name=home)
    zones.box_entry(axs2[0, 1], df, home, away, hcol, acol)
    zones.final_third_entry(axs2[0, 2], df, away, acol, invert=True)

    zones.zone14hs(axs2[1, 0], df, home, hcol, home_name=home)
    zones.crosses(axs2[1, 1], df, home, away, hcol, acol)
    zones.zone14hs(axs2[1, 2], df, away, acol, invert=True)

    zones.pass_end_zone(axs2[2, 0], df, home, cmap_h, home_name=home)
    zones.high_turnovers(axs2[2, 1], df, home, away, hcol, acol)
    zones.pass_end_zone(axs2[2, 2], df, away, cmap_a, invert=True)

    zones.chance_creating_zone(axs2[3, 0], df, home, cmap_h, hcol, home_name=home)
    zones.congestion(axs2[3, 1], df, home, away, hcol, acol)
    zones.chance_creating_zone(axs2[3, 2], df, away, cmap_a, acol, invert=True)

    fig2.text(0.5, 0.98, f"{home} {score} {away}", color=config.LINE_COLOR, fontsize=70,
              fontweight="bold", ha="center", va="center")
    fig2.text(0.5, 0.945, f"{comp} | Post Match Report — Zones", color=config.LINE_COLOR,
              fontsize=30, ha="center", va="center")
    fig2.text(0.5, 0.925, "Data from: WhoScored + FotMob", color=config.LINE_COLOR,
              fontsize=22.5, ha="center", va="center")
    fig2.text(0.125, 0.1, "Attacking Direction ------->", color=hcol, fontsize=25, ha="left", va="center")
    fig2.text(0.9, 0.1, "<------- Attacking Direction", color=acol, fontsize=25, ha="right", va="center")

    return fig1, fig2


def save_report(data_dir: Path, out_dir: Path) -> list[Path]:
    """Render both figures to PNG (and return paths)."""
    df, home, away, hcol, acol, meta, matchdict, fotmob_xg = load_report_data(data_dir)
    fig1, fig2 = build_team_report_figures(df, home, away, hcol, acol, meta, fotmob_xg)

    out_dir.mkdir(parents=True, exist_ok=True)
    p1 = out_dir / "match_report_1.png"
    p2 = out_dir / "match_report_2.png"
    fig1.savefig(p1, bbox_inches="tight", facecolor=config.BG_COLOR)
    fig2.savefig(p2, bbox_inches="tight", facecolor=config.BG_COLOR)
    plt.close(fig1)
    plt.close(fig2)
    return [p1, p2]
