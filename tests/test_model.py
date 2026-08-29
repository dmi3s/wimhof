from __future__ import annotations

from pathlib import Path

import pytest

from wimhof.model import (
    compute_progress,
    load_scheme,
    merge_round,
)


# ----------------------------------------------------------------------
# merge_round
# ----------------------------------------------------------------------
def test_merge_round_overrides_scalars_and_merges_sequence_by_index():
    base = {"repeat": 1, "section": "A", "sequence": [{"a": 1, "b": 2}]}
    override = {
        "inherit": True,
        "repeat": 2,
        "section": "B",
        "sequence": [{"b": 3, "c": 4}],
    }
    result = merge_round(base, override)

    assert result["repeat"] == 2
    assert result["section"] == "B"
    # 'inherit' must be dropped
    assert "inherit" not in result
    # sequence item merged by index: base keys kept, override keys win
    assert result["sequence"] == [{"a": 1, "b": 3, "c": 4}]


def test_merge_round_keeps_base_when_override_has_no_sequence():
    base = {"repeat": 1, "sequence": [{"a": 1}]}
    result = merge_round(base, {"repeat": 5})
    assert result["repeat"] == 5
    assert result["sequence"] == [{"a": 1}]


# ----------------------------------------------------------------------
# load_scheme
# ----------------------------------------------------------------------
_SCHEME = """
rounds:
  - section: A
    repeat: 2
    sequence:
      - type: inhale
        behavior: expand
        duration: 2
        label: "INHALE"
  - section: B
    inherit: true
    repeat: 1
    sequence:
      - type: inhale
        display: "cycles"
"""


@pytest.fixture
def scheme_path(tmp_path: Path) -> Path:
    p = tmp_path / "scheme.yaml"
    p.write_text(_SCHEME, encoding="utf-8")
    return p


def test_load_scheme_flattens_rounds_into_phases(scheme_path: Path):
    _, phases = load_scheme(str(scheme_path))
    # round A (repeat 2) + round B (repeat 1) = 3 phases
    assert len(phases) == 3


def test_load_scheme_default_display_is_countdown(scheme_path: Path):
    _, phases = load_scheme(str(scheme_path))
    assert phases[0].display == "countdown"
    assert phases[1].display == "countdown"


def test_load_scheme_inherit_merges_behavior_from_base(scheme_path: Path):
    _, phases = load_scheme(str(scheme_path))
    # B inherits A's sequence -> behavior 'expand' should survive
    assert phases[2].behavior == "expand"
    assert phases[2].display == "cycles"
    assert phases[2].round_index == 2
    assert phases[2].round_total == 2


def test_load_scheme_cycle_metadata(scheme_path: Path):
    _, phases = load_scheme(str(scheme_path))
    # round A repeat 2 -> cycle_remaining 2 then 1
    assert phases[0].cycle_remaining == 2
    assert phases[1].cycle_remaining == 1
    assert phases[0].cycle_total == 2


def test_load_scheme_inherit_without_base_raises(tmp_path: Path):
    p = tmp_path / "bad.yaml"
    p.write_text(
        "rounds:\n  - section: X\n    inherit: true\n    sequence: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Inherit from undefined base round"):
        load_scheme(str(p))


def test_load_scheme_real_preset():
    _, phases = load_scheme("src/wimhof/presets/wimhof.yaml")
    assert len(phases) == 65
    assert phases[0].type == "prepare"
    assert phases[0].behavior == "prepare"


# ----------------------------------------------------------------------
# compute_progress
# ----------------------------------------------------------------------
def test_compute_progress_start_is_zero():
    assert compute_progress([0.0, 10.0], 20.0, 0, 0.0, False, False) == 0.0


def test_compute_progress_mid():
    assert compute_progress([0.0, 10.0], 20.0, 0, 5.0, False, False) == 0.25


def test_compute_progress_finishing_is_one():
    assert compute_progress([0.0, 10.0], 20.0, 0, 0.0, True, False) == 1.0


def test_compute_progress_completed_is_one():
    assert compute_progress([0.0, 10.0], 20.0, 0, 0.0, False, True) == 1.0


def test_compute_progress_clamped_to_one():
    assert compute_progress([0.0], 10.0, 0, 999.0, False, False) == 1.0
