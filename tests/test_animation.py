from __future__ import annotations

import math

from wimhof import animation

MIN_R = 80.0
MAX_R = 260.0


def test_target_radius_expanding_behaviors():
    assert animation.target_radius("expand", MIN_R, MAX_R) == MAX_R
    assert animation.target_radius("shrink", MIN_R, MAX_R) == MIN_R
    assert animation.target_radius("prepare", MIN_R, MAX_R) == MIN_R
    assert animation.target_radius("expand_big", MIN_R, MAX_R) == MAX_R * 1.25
    assert animation.target_radius("hold_big", MIN_R, MAX_R) == MAX_R * 1.25


def test_target_radius_non_target_behaviors_return_none():
    assert animation.target_radius("hold", MIN_R, MAX_R) is None
    assert animation.target_radius("pulse", MIN_R, MAX_R) is None
    assert animation.target_radius("fade_out", MIN_R, MAX_R) is None
    assert animation.target_radius("unknown", MIN_R, MAX_R) is None


def test_interpolate_linear():
    assert animation.interpolate(0.0, 10.0, 0.0, 1.0) == 0.0
    assert animation.interpolate(0.0, 10.0, 1.0, 1.0) == 10.0
    assert animation.interpolate(0.0, 10.0, 0.5, 1.0) == 5.0


def test_interpolate_alpha_shapes_curve():
    # alpha < 1 -> fast start (value above linear at t=0.5)
    assert animation.interpolate(0.0, 10.0, 0.5, 0.5) > 5.0
    # alpha > 1 -> slow start (value below linear at t=0.5)
    assert animation.interpolate(0.0, 10.0, 0.5, 2.0) < 5.0


def test_pulse_offset_bounds_and_periodicity():
    amp = 3.0
    for t in [0.0, 0.37, 1.9, 5.123]:
        assert abs(animation.pulse_offset(t, amp)) <= amp
    # frequency is 8 rad/s -> period 2*pi/8
    period = 2 * math.pi / 8.0
    assert animation.pulse_offset(1.0) == animation.pulse_offset(1.0 + period)
