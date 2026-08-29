from __future__ import annotations

from wimhof.model import Phase
from wimhof.session import BreathingSession


def _make_session() -> BreathingSession:
    phases = [
        Phase("a", "expand", 1.0, "A", "S", "countdown", 1, 1),
        Phase("b", "shrink", 1.0, "B", "S", "countdown", 2, 1),
    ]
    return BreathingSession(phases, finish_duration=2.0)


def test_session_starts_at_first_phase():
    sess = _make_session()
    assert sess.index == 0
    assert sess.t == 0.0
    assert sess.current_phase.type == "a"
    assert sess.progress() == 0.0


def test_session_advance_moves_through_phases():
    sess = _make_session()
    sess.advance(0.5)
    assert sess.t == 0.5
    sess.advance(0.6)  # crosses duration 1.0 -> next phase, t reset to 0
    assert sess.index == 1
    assert sess.t == 0.0
    assert sess.current_phase.type == "b"


def test_session_enters_finishing_then_completes():
    sess = _make_session()
    sess.advance(1.0)  # -> phase b
    sess.advance(1.0)  # crosses end -> finishing, index clamped
    assert sess.finishing
    assert sess.index == 1
    assert not sess.completed
    sess.advance(2.0)  # finish_duration reached
    assert sess.completed
    assert sess.progress() == 1.0


def test_session_advance_is_noop_once_completed():
    sess = _make_session()
    sess.advance(1.0)
    sess.advance(1.0)
    sess.advance(2.0)
    assert sess.completed
    before = (sess.index, sess.t, sess.finish_t)
    sess.advance(5.0)
    assert (sess.index, sess.t, sess.finish_t) == before


def test_session_restart_resets_state():
    sess = _make_session()
    sess.advance(1.0)
    sess.advance(1.0)
    sess.advance(2.0)
    assert sess.completed
    sess.restart()
    assert sess.index == 0
    assert sess.t == 0.0
    assert not sess.finishing
    assert not sess.completed
    assert sess.progress() == 0.0


def test_session_progress_monotonic_sample():
    sess = _make_session()
    sess.advance(0.5)  # halfway through phase a (1.0s of 2.0s total)
    assert abs(sess.progress() - 0.25) < 1e-9


def test_session_from_preset_real_file():
    sess = BreathingSession.from_preset("src/wimhof/presets/wimhof.yaml")
    assert len(sess.phases) == 65
    assert sess.total_duration > 0
    assert sess.current_phase.type == "prepare"
