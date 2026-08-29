# Reconcile YAML ↔ real behavior (forward fix)

## Context
The circle animation is driven only by `Phase.behavior`. The YAML also carries a
`type` field that is (a) never read by the animation and (b) uses a *different*
vocabulary than `behavior` (`type: exhale` vs `behavior: outhale`,
`type: deep_inhale` vs `behavior: inhale`). So editing `type` does nothing, and
the YAML looks like it says one thing while the circle does another.

Separately, `animation.radius_at` hardcodes a `pulse_offset` applied to
`behavior == "hold"`. The YAML says `behavior: hold` (retention) and never
declares a pulse, so the circle does something the YAML does not say — a "made-up"
effect.

Goal: make the YAML the single, unambiguous source of truth for the circle. No
hidden code paths; no divergent vocabulary.

## A. Remove the hardcoded pulse — YAML becomes authoritative
Observed divergence (read-only trace, current code): `hold` phases MOVE
(`exp=HOLD act=MOVE`) — radius oscillates ±10–20px around the held value on every
retention (wimhof 45s/15s, 4-7-8 7s×8, box 4s×16, debug 3s). Because the pulse
ends off-center (sin(2π·duration/period) ≠ 0), there is also a visible RADIUS JUMP
at every `hold -> next phase` boundary. Both are artifacts of the hardcoded
`pulse_offset` added only for `behavior == "hold"`; YAML declares `hold` = retention.

Fix:
- `src/wimhof/animation.py`
  - Delete `pulse_offset`.
  - In `radius_at` remove params `pulse_amp`/`pulse_period` and the branch
    `if behavior == "hold": r += pulse_offset(...)`. Keep `behavior` (needed for
    grow/retain logic). `hold` -> clean static retention, exactly as YAML says.
    Boundaries become continuous again (next phase starts at the held radius).
- `src/wimhof/main.py` (~line 198): call
  `radius_at(start, end, self.session.t, p.duration, p.behavior)` (no pulse args).
- `tests/test_animation.py`: replace `test_radius_at_pulses_on_hold` with
  `test_radius_at_hold_is_static` — assert radius on `hold` is constant over `t`.
- `README.md`: drop "gentle, slow pulse" for `hold`; `hold` = holds a definite
  (static) radius.

## B. Unify `type` and `behavior` (kill the dual vocabulary)
- `src/wimhof/model.py`: when building phases, validate `type == behavior`
  (if `type` missing, default to `behavior`). Fail fast on divergence at load time.
- Presets (`wimhof.yaml`, `4-7-8.yaml`, `box_breathing.yaml`, `debug.yaml`): bring
  `type` in line with `behavior`:
  - `type: exhale` -> `type: outhale`
  - `type: deep_inhale` -> `type: inhale`
  - others (`inhale`, `hold`, `pass`, `release`, `prepare`, `relax`) already match.
- Tests `test_model.py` / `test_session.py` keep referencing `.type` (now == behavior),
  so they stay green.

## C. Guard test against future drift
- Add to `tests/test_model.py` (or `test_session.py`): for every preset
  (`wimhof`, `4-7-8`, `box_breathing`, `debug`):
  - `phase.behavior in {inhale, outhale, hold, pass, release, prepare, relax}`
  - `phase.type == phase.behavior`
  This guarantees YAML and reality cannot drift again.

## D. Verify
- `uv run ruff format --check src/wimhof tests && uv run ruff check src/wimhof tests`
- `uv run mypy src/wimhof`
- `uv run pytest -q` (expect 27 pass: rewritten hold-static + new guard test)
- `for p in wimhof 4-7-8 box_breathing debug; do uv run wimhof --simulate -b presets/$p.yaml; done`
- `uv run python scripts/check_doc_version.py --strict` (README edited -> self-heal)
- Optional offscreen trace: `hold`/`pass`/`prepare`/`relax` STATIC (min==max),
  `inhale`/`outhale`/`release` move; `max |widget.radius - pure projection| == 0`.

## Commit
`DEV:` / `REFAC:` "make YAML the single source of truth for circle behavior"
(remove hardcoded hold pulse; enforce type==behavior). Push only on request.
