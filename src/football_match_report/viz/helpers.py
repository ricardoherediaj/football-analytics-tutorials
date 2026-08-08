"""Shared pitch / styling helpers (black theme, blueprint conventions)."""

from __future__ import annotations

import matplotlib.patheffects as path_effects
from mplsoccer import Pitch

from .. import config


def make_pitch(pitch_color=None, line_color=None, **kwargs) -> Pitch:
    return Pitch(
        pitch_type=config.PITCH_TYPE,
        pitch_color=pitch_color or config.BG_COLOR,
        line_color=line_color or config.LINE_COLOR,
        linewidth=2,
        corner_arcs=True,
        **kwargs,
    )


def style_ax(ax, bg=None):
    ax.set_facecolor(bg or config.BG_COLOR)
    ax.set_xlim(-0.5, config.PITCH_X_MAX + 0.5)
    ax.set_ylim(-0.5, config.PITCH_Y_MAX + 0.5)


def path_eff():
    return [path_effects.Stroke(linewidth=3, foreground=config.BG_COLOR), path_effects.Normal()]


def path_eff_thin():
    return [path_effects.Stroke(linewidth=2, foreground=config.BG_COLOR), path_effects.Normal()]
