from __future__ import annotations

from .model import Phase, compute_progress, load_scheme


class BreathingSession:
    """Pure (Qt-free) state machine driving phase progression over time.

    This is the "model of a run": given a list of phases it answers
    "what phase are we in" and "how far along are we" as real time is
    fed in via :meth:`advance`. No rendering, no timers, no audio.
    """

    def __init__(
        self,
        phases: list[Phase],
        finish_duration: float = 6.0,
        start_index: int = 0,
    ):
        self.phases = phases
        self.index = start_index
        self.t = 0.0
        self.finishing = False
        self.finish_t = 0.0
        self.finish_duration = finish_duration
        self.completed = False

        self.total_duration = sum(p.duration for p in self.phases)
        self.phase_start_times: list[float] = []
        acc = 0.0
        for ph in self.phases:
            self.phase_start_times.append(acc)
            acc += ph.duration

    @property
    def current_phase(self) -> Phase:
        return self.phases[self.index]

    def advance(self, dt: float) -> None:
        """Feed real elapsed time (seconds). Single phase step per call."""
        if self.completed:
            return
        if self.finishing:
            if not self.completed:
                self.finish_t += dt
            if self.finish_t >= self.finish_duration:
                self.completed = True
            return

        self.t += dt
        phase = self.current_phase
        if self.t >= phase.duration:
            self.index += 1
            self.t = 0.0
            if self.index >= len(self.phases):
                self.index = len(self.phases) - 1
                self.finishing = True
                self.finish_t = 0.0

    def progress(self) -> float:
        return compute_progress(
            self.phase_start_times,
            self.total_duration,
            self.index,
            self.t,
            self.finishing,
            self.completed,
        )

    def restart(self) -> None:
        self.index = 0
        self.t = 0.0
        self.finishing = False
        self.finish_t = 0.0
        self.completed = False

    @classmethod
    def from_preset(cls, path: str, finish_duration: float = 6.0) -> BreathingSession:
        _, phases = load_scheme(path)
        return cls(phases, finish_duration=finish_duration)
