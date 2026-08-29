from __future__ import annotations

from wimhof import animation
from wimhof.model import Phase

MIN_R = 80.0
MAX_R = 260.0


def test_target_radius_moving_behaviors():
    assert animation.target_radius("inhale", MIN_R, MAX_R) == MAX_R
    assert animation.target_radius("outhale", MIN_R, MAX_R) == MIN_R
    assert animation.target_radius("release", MIN_R, MAX_R) == MIN_R


def test_target_radius_retain_behaviors_return_none():
    for beh in ("hold", "pass", "prepare", "relax", "unknown"):
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


def _mk(behavior, duration):
    return Phase(
        type="t",
        behavior=behavior,
        duration=duration,
        label="label",
        section="sec",
        display="countdown",
        round_index=0,
        round_total=1,
    )


def test_precompute_phase_radii_is_pure_chain():
    phases = [
        _mk("prepare", 1),
        _mk("inhale", 2),
        _mk("hold", 3),
        _mk("outhale", 2),
        _mk("release", 2),
    ]
    radii = animation.precompute_phase_radii(phases, MIN_R, MAX_R)
    assert radii[0] == (MIN_R, MIN_R)  # prepare: retain small
    assert radii[1] == (MIN_R, MAX_R)  # inhale: grow to max
    assert radii[2] == (MAX_R, MAX_R)  # hold: keep max
    assert radii[3] == (MAX_R, MIN_R)  # outhale: shrink to min
    assert radii[4] == (MIN_R, MIN_R)  # release: already min
    # continuity: end of phase i == start of phase i+1
    for (_, e), (s, _) in zip(radii, radii[1:], strict=False):
        assert e == s


def test_radius_at_follows_state():
    # hold at a definite radius: constant for any t
    for t in (0.0, 0.7, 2.0):
        assert animation.radius_at(200.0, 200.0, t, 2.0) == 200.0
    # inhale-like motion hits endpoints and stays within bounds
    assert animation.radius_at(80.0, 260.0, 0.0, 2.0) == 80.0
    assert animation.radius_at(80.0, 260.0, 2.0, 2.0) == 260.0
    mid = animation.radius_at(80.0, 260.0, 1.0, 2.0)
    assert 80.0 < mid < 260.0


def test_radius_at_hold_is_static():
    center = 200.0
    # breath retention keeps the held radius exactly, as declared in YAML
    vals = [
        animation.radius_at(center, center, t, 45.0, "hold")
        for t in (0.0, 1.5, 3.0, 22.5, 45.0)
    ]
    assert all(v == center for v in vals)
    # a plain pause also keeps the radius exactly constant
    assert animation.radius_at(center, center, 12.3, 45.0, "pass") == center
    # any retention behavior (prepare/relax) is static too
    assert animation.radius_at(center, center, 1.0, 3.0, "prepare") == center
    assert animation.radius_at(center, center, 1.0, 3.0, "relax") == center
