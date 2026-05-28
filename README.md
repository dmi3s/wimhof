[logo]: src/wimhof/assets/app_icon.png
[demo]: demo/demo.jpg
[demo-thumbnail]: demo/demo.thumbnail.jpg
[demo.webm]: demo/demo.webm

# ![logo][logo] Wim Hof Breathing Trainer

_Atmospheric desktop breathing trainer inspired by the
[Wim Hof breathing method](https://www.wimhofmethod.com/)
and other structured breathing techniques._

Built with Python, PySide6, and YAML-driven session configuration.

The application focuses on smooth pacing, minimal UI distractions,
and configurable breathing protocols.

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
uv run wimhof --config presets/4-7-8.yaml
```

Short form:

```bash
uv run wimhof -c presets/box_breathing.yaml
```

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
      behavior: expand
      duration: 4
      label: "INHALE"

    - type: hold
      behavior: pulse_small
      duration: 7
      label: "HOLD"

    - type: exhale
      behavior: shrink
      duration: 8
      label: "EXHALE"

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
│       └── ci.yml                  -- GitHub CI workflow
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
│       └── presets/
│           ├── 4-7-8.yaml          -- Preset for 4-7-8 breathing sequence
│           └── box_breathing.yaml  -- Preset for box breathing sequence
│       ├── __init__.py             -- Package marker
│       ├── config.yaml             -- Wim Hof breathing configuration
│       └── main.py                 -- Application code
├── LICENSE
├── pyproject.toml
├── README.md
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

_Developed using Python and PySide6 with assistance from ChatGPT._
