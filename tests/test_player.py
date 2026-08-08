"""Player-level report tests: leaderboards, per-player stats, figures, CSV."""

import matplotlib

matplotlib.use("Agg")

import pandas as pd

from football_match_report.core import player_stats as core_player
from football_match_report.viz import player_individual as pind
from football_match_report.viz import player_report
from football_match_report.viz import player_top as ptop
from football_match_report.viz import report as report_viz


def _load(synthetic_bundle):
    return report_viz.load_report_data(synthetic_bundle)


# --- Leaderboards -------------------------------------------------------- #

def test_top_progressors_leaderboard(synthetic_bundle):
    df, home, away, *_ = _load(synthetic_bundle)
    lb = core_player.top_progressors(df, home, 5)
    assert len(lb) >= 1
    for col in ("name", "shortName", "Progressive Passes", "Progressive Carries",
                "LineBreaking Pass", "total"):
        assert col in lb.columns
    assert lb["total"].is_monotonic_decreasing
    # the home playmaker has at least 3 progressive passes (fixture)
    assert lb["Progressive Passes"].max() >= 3


def test_leaderboards_cover_all_facets(synthetic_bundle):
    df, home, away, *_ = _load(synthetic_bundle)
    assert len(core_player.top_threat(df, home, 5)) >= 1
    assert len(core_player.top_shot_sequence(df, home, 5)) >= 1
    assert len(core_player.top_defenders(df, home, 5)) >= 1
    combined = core_player.top_progressors(df, None, 10)
    assert len(combined) <= 10
    assert "P1A0" in combined["name"].tolist()


# --- Individual stats ---------------------------------------------------- #

def test_playing_time(synthetic_bundle):
    df, home, away, *_ = _load(synthetic_bundle)
    max_min = int(df["minute"].max())  # 25' in the fixture
    assert core_player.playing_time(df, "P1A0") == max_min   # starter, played full
    assert core_player.playing_time(df, "P1B0") == 0         # sub without sub-on event
    assert core_player.playing_time(df, "Nobody") == 0


def test_passing_stats(synthetic_bundle):
    df, home, away, *_ = _load(synthetic_bundle)
    s = core_player.passing_stats(df, "P1A0")
    assert s["Total_Passes"] == 6          # fixture: 6 successful passes
    assert s["Accurate_Passes"] == 6
    assert s["Passing_Accuracy"] == 100.0
    assert s["Chances_Created"] == 1       # the KeyPass qualifier
    assert s["Assists"] == 1               # IntentionalGoalAssist
    assert s["Total_xT_From_Pass"] > 0


def test_carrying_stats_no_crash(synthetic_bundle):
    df, home, away, *_ = _load(synthetic_bundle)
    s = core_player.carrying_stats(df, "P1A0")
    assert s["Total_Carries"] >= 0
    assert s["TakeOn_Attempts"] == 0
    assert "Progressive_Carries" in s and "Total_xT_From_Carries" in s


def test_shooting_stats_with_fotmob_xg(synthetic_bundle):
    df, home, away, *_ = _load(synthetic_bundle)
    shots_df = pd.read_csv(synthetic_bundle / "shots.csv")
    s = core_player.shooting_stats(df, "P1A0", shots_df)
    assert s["Total_Shots"] == 2
    assert s["Goals"] == 1
    assert s["xG"] == 0.6    # 0.5 goal + 0.1 miss (FotMob)
    assert s["xGOT"] == 0.6
    s2 = core_player.shooting_stats(df, "P2A0", shots_df)
    assert s2["Total_Shots"] == 3
    assert s2["xG"] == 0.3


def test_defensive_stats(synthetic_bundle):
    df, home, away, *_ = _load(synthetic_bundle)
    s = core_player.defensive_stats(df, "P1A0")
    assert s["Total_Tackles"] == 1
    assert s["Tackles_Won"] == 1
    assert s["Ball_Recoveries"] == 1
    # the sub (id 1104) made the interception
    s_sub = core_player.defensive_stats(df, "P1B0")
    assert s_sub["Interception"] == 1


def test_touches_stats_degenerate_player(synthetic_bundle):
    """A player with a single touch must not crash (convex hull guard)."""
    df, home, away, *_ = _load(synthetic_bundle)
    s = core_player.touches_stats(df, "P2B0")   # one pass only
    assert s["Total_Touches"] >= 1
    assert s["Total_Area_Covered"] == 0.0
    assert "Total_Distance_Covered(Km)" in s


def test_player_shot_frame(synthetic_bundle):
    df, home, away, *_ = _load(synthetic_bundle)
    shots_df = pd.read_csv(synthetic_bundle / "shots.csv")
    frame = core_player.player_shot_frame(df, "P1A0", shots_df)
    assert len(frame) == 2
    assert frame["x"].max() <= 105.5          # FotMob 0-100 -> UEFA scale
    assert "Goal" in frame["eventType"].tolist()
    # fallback: no FotMob -> WhoScored events, no xG
    fallback = core_player.player_shot_frame(df, "P2A0", None)
    assert len(fallback) == 3
    assert (fallback["expectedGoals"] == 0).all()


def test_player_stats_table(synthetic_bundle):
    df, home, away, *_ = _load(synthetic_bundle)
    shots_df = pd.read_csv(synthetic_bundle / "shots.csv")
    table = core_player.player_stats_table(df, shots_df)
    # only players who touched the ball appear (4 of the 10 roster players)
    assert len(table) == 4
    for col in ("Name", "Team", "Total_Passes", "Total_Carries", "Total_Shots",
                "Total_Passes_Received", "Total_Tackles", "Total_Touches"):
        assert col in table.columns
    assert set(table["Name"]) == {"P1A0", "P1B0", "P2A0", "P2B0"}
    assert set(table["Team"]) == {home, away}


# --- Figures ------------------------------------------------------------- #

def test_build_top_players_figure(synthetic_bundle):
    df, home, away, hcol, acol, meta, *_ = _load(synthetic_bundle)
    fig = ptop.build_top_players_figure(df, home, away, hcol, acol, meta)
    assert len(fig.axes) >= 12


def test_build_individual_figure(synthetic_bundle):
    df, home, away, hcol, acol, meta, *_ = _load(synthetic_bundle)
    shots_df = pd.read_csv(synthetic_bundle / "shots.csv")
    fig = pind.build_individual_figure(df, shots_df, "P1A0", home, hcol, meta)
    assert len(fig.axes) == 6


def test_build_individual_figure_no_shots(synthetic_bundle):
    """A player with zero shots must render (empty shot-map fallback)."""
    df, home, away, hcol, acol, meta, *_ = _load(synthetic_bundle)
    fig = pind.build_individual_figure(df, None, "P1B0", home, hcol, meta)
    assert len(fig.axes) == 6


def test_save_player_reports(synthetic_bundle, tmp_path):
    paths = player_report.save_player_reports(synthetic_bundle, tmp_path)
    p3 = tmp_path / "match_report_3.png"
    stats_csv = tmp_path / "player_stats.csv"
    assert p3 in paths and p3.exists() and p3.stat().st_size > 10_000
    assert stats_csv in paths and stats_csv.exists()
    players_dir = tmp_path / "players"
    pngs = sorted(players_dir.glob("*.png"))
    # fixture touches: only P1A0 / P2A0 are starters with events
    assert {p.stem for p in pngs} == {"P1A0", "P2A0"}
    for p in pngs:
        assert p.stat().st_size > 10_000


def test_save_player_reports_selected_players(synthetic_bundle, tmp_path):
    paths = player_report.save_player_reports(synthetic_bundle, tmp_path, players=["P1A0", "P2A0"])
    pngs = [p for p in paths if p.suffix == ".png" and p.parent.name == "players"]
    assert len(pngs) == 2
    names = {p.stem for p in pngs}
    assert names == {"P1A0", "P2A0"}
