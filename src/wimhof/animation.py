from __future__ import annotations

import math


def ease(t: float) -> float:
    """InOutSine easing, identical to ``QEasingCurve.InOutSine``."""
    return 0.5 - 0.5 * math.cos(math.pi * t)


def target_radius(behavior: str, min_r: float, max_r: float) -> float | None:
    """Target ring radius at the END of a phase, or ``None`` to retain.

    Moving behaviors target a radius; retention behaviors
    (``hold``, ``pass``, ``prepare``, ``relax``) return ``None`` so the
    ring keeps its current (definite) radius.
    """
    mapping = {
        "inhale": max_r,
        "outhale": min_r,
        "release": min_r,
    }
    return mapping.get(behavior)


def interpolate(start: float, target: float, t: float, alpha: float = 1.0) -> float:
    """Non-linear interpolation using a power curve.

    ``t`` in [0,1]; applies ``t = t ** alpha``.
    ``alpha == 1.0`` -> linear, ``alpha < 1`` -> fast start,
    ``alpha > 1`` -> slow start.
    """
    t = t**alpha
    return start + (target - start) * t


def precompute_phase_radii(
    phases, min_r: float, max_r: float
) -> list[tuple[float, float]]:
    """Deterministic ``(start, end)`` radius for each phase, folded over the list.

    The radius of a phase is purely determined by the declared behaviors:
    moving phases target MAX/MIN, retention phases keep the entry radius.
    ``end`` of phase ``i`` equals ``start`` of phase ``i+1``, so the circle
    is continuous and has no state of its own.
    """
    radii: list[tuple[float, float]] = []
    prev_end = min_r
    for p in phases:
        start = prev_end
        target = target_radius(p.behavior, min_r, max_r)
        end = target if target is not None else start
        radii.append((start, end))
        prev_end = end
    return radii


def radius_at(
    start: float,
    end: float,
    t: float,
    duration: float,
    behavior: str | None = None,
    alpha: float = 1.0,
) -> float:
    """Pure ring radius at time ``t`` within a phase of ``duration`` seconds.

    This is a direct projection of the phase state: the view holds no
    mutable radius memory of its own. Moving behaviors interpolate toward
    their target radius; retention behaviors (``hold``, ``pass``,
    ``prepare``, ``relax``) keep the entry radius exactly, as declared.
    """
    progress = min(t / duration, 1.0) if duration > 0 else 1.0
    progress = ease(progress)
    return interpolate(start, end, progress, alpha)
