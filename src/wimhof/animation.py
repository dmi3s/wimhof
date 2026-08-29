from __future__ import annotations


def target_radius(behavior: str, min_r: float, max_r: float) -> float | None:
    """Pure mapping from a phase behavior to its target ring radius.

    Returns ``None`` for behaviors that do not move the ring toward a
    target (``hold`` keeps the current radius).
    """
    mapping = {
        "inhale": max_r,
        "exhale": min_r,
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
