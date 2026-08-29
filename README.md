[logo]: src/wimhof/assets/app_icon.png
[demo]: demo/demo.jpg
[demo-thumbnail]: demo/demo.thumbnail.jpg
[demo.webm]: demo/demo.webm

# ![logo][logo] Wim Hof Breathing Trainer

_Atmospheric desktop breathing trainer inspired by the
[Wim Hof breathing method](https://www.wimhofmethod.com/)
and other structured breathing techniques._

**Wimhof** – Visual Breathing Trainer

A desktop tool that guides you through the Wim Hof breathing method using a pulsing circle on screen.

- The circle grows on `inhale`, shrinks on `outhale` and `release`, and holds on `pass` (breath retention). `prepare` and `relax` are technical start/finish states.
- No counting – just follow the rhythm.
- Fully customizable: colors, background music, and phase durations are stored in YAML configs.
- Minimalistic interface, controlled by keyboard (Space, M, Esc).

Why it works:

The method combines controlled hyperventilation and breath retention, triggering the Bohr effect – improved oxygen delivery, vasodilation, and autonomic balance. Regular practice may reduce cortisol and enhance stress resilience. This tool simply helps you keep the rhythm, while the physiology stays natural.

## Features

- Fullscreen breathing trainer
- Smooth breathing ring animation
- YAML-configurable breathing protocols
- Multiple breathing techniques support
- Timeline visualization
- Countdown and cycle-based displays
- Ambient background image and music
- Pause / resume support
- Fade-out completion sequence
- Config inheritance system
- Protocol presets support
- Headless simulation mode (`--simulate`)
- Unit-tested core logic (model + session)

## Supported Breathing Styles

The application is protocol-driven and can describe different
breathing techniques entirely through YAML configuration.

Current examples include:

- Wim Hof style breathing
- 4-7-8 breathing
- Box breathing

## Design Goals

#### This project intentionally avoids:

- excessive UI complexity
- account systems
- online services
- unnecessary gamification

#### The focus is:

- calm pacing
- smooth visual transitions
- readable structure
- extensible protocol configuration
- layered architecture: data model → session state machine → Qt view

## Demo

![demo-thumbnail.jpg][demo-thumbnail]

Big picture: [demo/demo.jpg][demo]

Video preview:

[demo/demo.webm][demo.webm] ~ 3.4 Mb

## Installation

- For a quick local run:

```bash
git clone --depth 1 git@github.com:dmi3s/wimhof.git
cd wimhof
uv sync
```

- For development with full dependency groups (including dev extras):

```bash
git clone git@github.com:dmi3s/wimhof.git
cd wimhof
uv sync --all-groups
```

Run the application:

```bash
uv run wimhof
```

## Using Custom Presets

Run with a custom configuration file:

```bash
uv run wimhof --breathing presets/4-7-8.yaml
```

Short form:

```bash
uv run wimhof -b presets/box_breathing.yaml
```

You can also run a **headless simulation** (no GUI/audio) that prints the
phase transitions of a protocol over time — handy for inspecting a preset:

```bash
uv run wimhof --simulate -b presets/4-7-8.yaml
```

All CLI options:

| Flag                  | Description                          |
| --------------------- | ------------------------------------ |
| `-b, --breathing FILE` | Breathing protocol YAML              |
| `-t, --theme FILE`     | Theme YAML                           |
| `-s, --simulate`       | Headless simulation (no GUI/audio)   |

## Configuration System

Breathing protocols are described using YAML timelines.
The breathing engine is intentionally data-driven.
Protocols are described as timelines rather than hardcoded logic.

Each section may contain:

- repeated sequences
- arbitrary phase ordering
- different display modes
- animation behaviors
- inherited configuration

Example:

```yaml
rounds:
  # ==========================================================
  # PREPARATION
  # ==========================================================

  - section: Preparation
    repeat: 1

    sequence:
      - type: prepare
        behavior: prepare
        duration: 3
        label: "PREPARE"
```

The configuration system supports partial overrides
of inherited sequences:

- sequence inheritance
- partial sequence overrides

### Example Protocol

Example 4-7-8 breathing sequence:

```yaml
- section: breathing
  repeat: 8

  sequence:
    - type: inhale
      behavior: inhale
      duration: 4
      label: "INHALE"

    - type: pass
      behavior: pass
      duration: 7
      label: "HOLD"

    - type: outhale
      behavior: outhale
      duration: 8
      label: "OUTHALE"

- section: breathing
  repeat: 6
  inherit: true

  sequence:
    - type: inhale
      display: "cycles"

    - type: hold
      display: "cycles"

    - type: exhale
      display: "cycles"
```

## Controls

|    Key    | Action                   |
| :-------: | :----------------------- |
|   **M**   | Mute / Unmute            |
| **Space** | Pause / Resume / Restart |
|  **ESC**  | Quit application         |

## Project Structure

```text
wimhof/
├──.github/
│   └── workflows/
│       └── ci.yml                  -- GitHub CI workflow (ruff, mypy, pytest)
├──.zed/
│   └── tasks.json                  -- Zed tasks (Run, Ruff, Mypy, Audit, Build)
├── demo/
│   ├── demo.thumbnail.jpg
│   ├── demo.jpg
│   └── demo.webm
├── src/
│   └── wimhof/
│       ├── assets/
│       │   ├── app_icon.png
│       │   ├── background.jpg
│       │   ├── music.mp3
│       │   └── sources.md          -- Sources for music, background, icon
│       ├── presets/
│       │   ├── 4-7-8.yaml          -- Preset for 4-7-8 breathing sequence
│       │   ├── box_breathing.yaml  -- Preset for box breathing sequence
│       │   └── wimhof.yaml         -- Preset for Wim Hof breathing sequence
│       ├── themes/
│       │   └── default.yaml        -- Default theme. Just one for now.
│       ├── __init__.py             -- Package marker (empty)
│       ├── __main__.py             -- Entry point. Runs the application.
│       ├── model.py                -- Data model: Phase, YAML loading, progress
│       ├── session.py              -- Qt-free session state machine
│       ├── main.py                 -- Qt view: rendering, input, audio, CLI
│       └── config.yaml             -- Wim Hof breathing configuration
├── tests/
│   ├── test_model.py               -- Tests for model (load_scheme/merge_round/progress)
│   └── test_session.py            -- Tests for session state machine
├── LICENSE
├── pyproject.toml
├── README.md
├── config.yaml                     -- Configuration file for the default
│                                   --   Wim Hof breathing application
└── uv.lock
```

## Dependencies

Main dependencies:

```toml
requires-python = ">=3.12"
dependencies = [
  "pyside6>=6.11.1",
  "pyyaml>=6.0.3",
]
```

## Development

The core logic (data model and session state machine) is Qt-free and unit-tested.

Run the test suite:

```bash
uv run pytest
```

Headless simulation — print phase transitions over time without launching the GUI:

```bash
uv run wimhof --simulate -b presets/4-7-8.yaml
```

CI (`.github/workflows/ci.yml`) runs `ruff format/check`, `mypy`, and `pytest`
on every push and pull request.

## Future Ideas

#### Possible future additions:

- logging
- Sessions statistics

#### Icebox:

- Local analytics database
- Audio guidance
- Breathing protocol sharing
- Mobile version
- Wearable integration

## Safety Notice

This application is intended for relaxation and controlled breathing exercises.

Do not use while:

- driving
- swimming
- operating machinery
- performing activities requiring full attention

## Media Sources

Background image and music are used under free licenses.

Full attribution information is available in
[src/wimhof/assets/sources.md](src/wimhof/assets/sources.md).

## License

MIT License.

© 2026 dmi3s

---

_Developed using Python and PySide6 (Qt) with assistance from ChatGPT and DeepSeek._
<!-- doc-sha256: c8655c28afa9391a06c9be58ec0bb5f475e4dc6f2cf71b389e91cb2364efcbc6 -->
