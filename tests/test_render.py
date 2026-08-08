"""Render tests: both report figures build from a synthetic bundle."""

import matplotlib

matplotlib.use("Agg")

from football_match_report.viz import report as report_viz


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
