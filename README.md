# Wim Hof Breathing Trainer

Atmospheric desktop breathing trainer inspired by the Wim Hof method.

Built with:

- Python 3.12+
- PySide6
- YAML-based breathing schedules
- Fullscreen meditation-style UI
- Ambient background music
- Smooth breathing animations

---

## Features

- Expanding / shrinking breathing ring
- Smooth easing animation
- Glow effects
- Fullscreen minimalistic UI
- Countdown breathing cycles
- Pause timer
- Round names
- YAML-configurable breathing schedule
- Background image support
- Looping background music

---

## Screenshot

_Add your screenshot here later._

---

## Installation

Clone repository:

```bash
git clone https://github.com/yourname/wimhof.git
cd wimhof

```

# Wim Hof Breathing Trainer

Atmospheric desktop breathing trainer inspired by the Wim Hof method.

Built with:

- Python 3.12+
- PySide6
- YAML-based breathing schedules
- Fullscreen meditation-style UI
- Ambient background music
- Smooth breathing animations

---

## Features

- Expanding / shrinking breathing ring
- Smooth easing animation
- Glow effects
- Fullscreen minimalistic UI
- Countdown breathing cycles
- Pause timer
- Round names
- YAML-configurable breathing schedule
- Background image support
- Looping background music

---

## Screenshot

_Add your screenshot here later._

---

## Installation

Clone repository:

```bash
git clone https://github.com/yourname/wimhof.git
cd wimhof
```

Install dependencies with uv:

```bash
uv sync
```

Run application:

```bash
uv run python main.py
```

## Project Structure

```
wimhof/
├── assets/
│   ├── background.jpg
│   └── music.mp3
├── main.py
├── config.yaml
├── pyproject.toml
├── README.md
├── .gitignore
└── .gitattributes
```

## Configuration

All breathing schedules are stored in config.yaml.

Example:

```yaml
background_image: assets/background.jpg
background_music: assets/music.mp3

rounds:
  - name: "Round 1"

    repetitions: 30

    inhale:
      duration: 2.2
      label: "INHALE"

    exhale:
      duration: 2.2
      label: "EXHALE"

    pause:
      duration: 60
      label: "PAUSE"
```

## Customization

You can easily customize:

- breathing speed
- number of cycles
- pause duration
- background image
- ambient music
- round presets

Possible breathing styles:

- Wim Hof
- Box Breathing
- 4-7-8
- Coherent Breathing
- Relaxation sessions
- Focus sessions

## Controls

| Key | Action           |
| --- | ---------------- |
| ESC | Exit application |

##Dependencies

Defined in pyproject.toml:

```toml
dependencies = [
    "pyside6>=6.11.1",
    "pyyaml>=6.0.3",
]
```

## Development

Run without activating virtualenv:

```bash
uv run python main.py
```

Add new dependency:

```bash
uv add package_name
```

Update lockfile:

```bash
uv lock
```

## Notes

This project was created as a lightweight atmospheric breathing trainer focused on simplicity and immersion rather than medical functionality.

Use responsibly and avoid intensive breathing exercises in unsafe situations.

## License

MIT
