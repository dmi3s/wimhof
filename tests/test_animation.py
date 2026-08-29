from __future__ import annotations

from wimhof import animation

MIN_R = 80.0
MAX_R = 260.0


def test_target_radius_moving_behaviors():
    assert animation.target_radius("inhale", MIN_R, MAX_R) == MAX_R
    assert animation.target_radius("outhale", MIN_R, MAX_R) == MIN_R
    assert animation.target_radius("release", MIN_R, MAX_R) == MIN_R


def test_target_radius_retain_behaviors_return_none():
    for beh in ("pass", "prepare", "relax", "unknown"):
        assert animation.target_radius(beh, MIN_R, MAX_R) is None


def test_interpolate_linear():
    assert animation.interpolate(0.0, 10.0, 0.0, 1.0) == 0.0
    assert animation.interpolate(0.0, 10.0, 1.0, 1.0) == 10.0
    assert animation.interpolate(0.0, 10.0, 0.5, 1.0) == 5.0


def test_interpolate_alpha_shapes_curve():
    # alpha < 1 -> fast start (value above linear at t=0.5)
    assert animation.interpolate(0.0, 10.0, 0.5, 0.5) > 5.0
    # alpha > 1 -> slow start (value below linear at t=0.5)
    assert animation.interpolate(0.0, 10.0, 0.5, 2.0) < 5.0
