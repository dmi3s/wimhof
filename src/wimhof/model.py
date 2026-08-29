from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import yaml


# ----------------------------------------------------------------------
# Data model for a single breathing phase
# ----------------------------------------------------------------------
@dataclass(slots=True)
class Phase:
    type: str
    behavior: str
    duration: float
    label: str
    section: str
    display: str
    round_index: int
    round_total: int
    cycle_index: int = 0
    cycle_remaining: int = 0
    cycle_total: int = 0


# ----------------------------------------------------------------------
# Helpers for merging round configurations (YAML inheritance)
# ----------------------------------------------------------------------
def merge_round(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if key == "inherit":
            continue
        elif key == "sequence":
            merged_sequence = []
            base_sequence = result.get("sequence", [])
            for i, item in enumerate(value):
                if i < len(base_sequence):
                    merged_item = {**base_sequence[i], **item}
                else:
                    merged_item = item
                merged_sequence.append(merged_item)
            result["sequence"] = merged_sequence
        else:
            result[key] = value
    return result


# ----------------------------------------------------------------------
# Load a breathing scheme (preset) – contains only 'rounds'
# ----------------------------------------------------------------------
def load_scheme(path: str) -> tuple[dict, list[Phase]]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    rounds = data["rounds"]
    phases: list[Phase] = []
    total_rounds = len(rounds)
    base_round: dict | None = None
    for ri, round_cfg in enumerate(rounds):
        if round_cfg.get("inherit", False):
            if base_round is None:
                raise ValueError("Inherit from undefined base round")
            cfg = merge_round(base_round, round_cfg)
        else:
            cfg = deepcopy(round_cfg)
        base_round = cfg
        repeat = cfg.get("repeat", 1)
        section = cfg.get("section", "default")
        sequence = cfg["sequence"]
        for cycle in range(repeat):
            remaining = repeat - cycle
            for item in sequence:
                phases.append(
                    Phase(
                        type=item["type"],
                        behavior=item["behavior"],
                        duration=item["duration"],
                        label=item["label"],
                        section=section,
                        display=item.get("display", "countdown"),
                        round_index=ri + 1,
                        round_total=total_rounds,
                        cycle_index=cycle + 1,
                        cycle_remaining=remaining,
                        cycle_total=repeat,
                    )
                )
    return data, phases


# ----------------------------------------------------------------------
# Load a theme (colors, background image, background music)
# ----------------------------------------------------------------------
def load_theme(path: str):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ----------------------------------------------------------------------
# Overall session progress (0..1) – pure computation
# ----------------------------------------------------------------------
def compute_progress(
    phase_start_times: list[float],
    total_duration: float,
    index: int,
    t: float,
    finishing: bool,
    completed: bool,
) -> float:
    if completed or finishing:
        return 1.0
    phase_start = phase_start_times[index]
    current_time = phase_start + t
    return min(current_time / total_duration, 1.0)
