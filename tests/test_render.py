"""Render tests: both report figures build from a synthetic bundle."""

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd

from football_match_report import config
from football_match_report.viz import report as report_viz
from football_match_report.viz import shots as shots_viz


def test_load_report_data(synthetic_bundle):
    df, home, away, hcol, acol, meta, matchdict, fotmob_xg = report_viz.load_report_data(synthetic_bundle)
    assert home == "Hometeam"
    assert away == "Awayteam"
    assert hcol == "#00a0de"
    assert acol == "#ff4b44"
    assert len(df) > 0


def test_build_team_report_figures(synthetic_bundle):
    df, home, away, hcol, acol, meta, matchdict, fotmob_xg = report_viz.load_report_data(synthetic_bundle)
    fig1, fig2 = report_viz.build_team_report_figures(df, home, away, hcol, acol, meta, fotmob_xg)
    # 4x3 grids
    assert fig1.axes  # has at least one axes
    assert len(fig1.axes) >= 12
    assert len(fig2.axes) >= 12


def test_save_report_writes_pngs(synthetic_bundle, tmp_path):
    paths = report_viz.save_report(synthetic_bundle, tmp_path)
    assert len(paths) == 2
    for p in paths:
        assert p.exists()
        assert p.stat().st_size > 10_000  # real PNG, not empty


# --- Regression tests: fix/visual-polish (v2.1.0) ---

def test_jitter_spreads_duplicate_goal_positions():
    """WhoScored marks several shots with the Z=19.0 'height not tracked'
    placeholder -> identical (gx, gy) pairs must be jittered apart so GK-save
    markers don't stack on top of each other."""
    n = 7
    out = pd.DataFrame({
        "gx": np.full(n, 43.5),   # goalMouthY=40 -> 43.5
        "gy": np.full(n, 5.7),    # goalMouthZ=19 -> 5.7
    })
    jittered = shots_viz.jitter_goal_positions(out)
    uniq = jittered[["gx", "gy"]].drop_duplicates()
    assert len(uniq) == n, f"expected {n} distinct positions, got {len(uniq)}"
    # jitter must stay small (within +/-1.2 of the original)
    assert np.abs(jittered["gx"] - 43.5).max() <= 1.2
    assert np.abs(jittered["gy"] - 5.7).max() <= 1.2
    # deterministic
    again = shots_viz.jitter_goal_positions(out)
    assert again["gx"].equals(jittered["gx"])
    assert again["gy"].equals(jittered["gy"])


def test_shot_map_stats_labels_white(synthetic_bundle):
    """Shot-map stats-bar titles/values must be white (LINE_COLOR) with the
    black outline — not black-on-blue-bar (the old light-theme leftover)."""
    from matplotlib import pyplot as plt

    df, home, away, hcol, acol, meta, matchdict, fotmob_xg = report_viz.load_report_data(synthetic_bundle)
    fig, ax = plt.subplots(figsize=(4, 4))
    try:
        shots_viz.shot_map(ax, df, home, away, hcol, acol, fotmob_xg)
        titles = {"Goals", "xG", "xGOT", "Shots", "On Target", "BigChance",
                  "BigC.Miss", "xG/Shot", "Avg.Dist."}
        bar_texts = [t for t in ax.texts if t.get_text() in titles]
        assert len(bar_texts) == len(titles), f"found {len(bar_texts)}/{len(titles)} titles"
        for t in bar_texts:
            assert t.get_color() == config.LINE_COLOR, f"title '{t.get_text()}' not white"
            assert t.get_path_effects(), f"title '{t.get_text()}' missing outline"
    finally:
        plt.close(fig)
