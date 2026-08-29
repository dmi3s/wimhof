from __future__ import annotations

import math

# Expansion overshoot factor for *big behaviors (expand_big / hold_big)
ABOVE_MAX_FACTOR = 1.25

# Pulse oscillation frequency (rad/s) and default amplitude (pixels)
_PULSE_FREQ = 8.0
_DEFAULT_PULSE_AMPLITUDE = 3.0


def target_radius(behavior: str, min_r: float, max_r: float) -> float | None:
    """Pure mapping from a phase behavior to its target ring radius.

    Returns ``None`` for behaviors that do not move the ring toward a
    target (``hold``, ``pulse``, ``fade_out`` are handled separately).
    """
    mapping = {
        "expand": max_r,
        "shrink": min_r,
        "expand_big": max_r * ABOVE_MAX_FACTOR,
        "prepare": min_r,
        "hold_big": max_r * ABOVE_MAX_FACTOR,
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


def pulse_offset(t: float, amplitude: float = _DEFAULT_PULSE_AMPLITUDE) -> float:
    """Subtle radius oscillation (sine), amplitude in pixels."""
    return math.sin(t * _PULSE_FREQ) * amplitude
