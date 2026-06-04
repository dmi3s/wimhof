from __future__ import annotations

import argparse
import math
import sys
from copy import deepcopy
from dataclasses import dataclass
from importlib.resources import files

import yaml
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QRectF,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QKeyEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QApplication, QWidget

# ----------------------------------------------------------------------
# Constants for fonts
# ----------------------------------------------------------------------
_HINTS_FONT_NAME = "Monospace"
_APP_DEFAULT_FONT_NAME = "Sans"


# ----------------------------------------------------------------------
# Timer with pause/resume capability
# ----------------------------------------------------------------------
class QTimerWithPause(QTimer):
    def __init__(self, parent=None, interval=0, singleShot=False):
        super().__init__(parent)
        self.setInterval(interval)
        self.setSingleShot(singleShot)
        self.remaining = 0

    def pause(self):
        self.remaining = self.remainingTime()
        self.stop()

    def resume(self):
        self.start(self.remaining)

    def reset(self):
        self.start(self.interval())


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
def load_theme(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ----------------------------------------------------------------------
# Easing curve for smooth animations
# ----------------------------------------------------------------------
def ease(t: float) -> float:
    return QEasingCurve(QEasingCurve.Type.InOutSine).valueForProgress(t)


# ----------------------------------------------------------------------
# Main breathing widget
# ----------------------------------------------------------------------
class BreathingWidget(QWidget):
    MIN_R = 80  # minimum ring radius
    MAX_R = 260  # maximum ring radius

    def __init__(self, scheme_path: str, theme_path: str):
        super().__init__()
        self.setWindowTitle("Breathing Trainer")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.paused = False
        self.completed = False
        self.muted = False
        self.showFullScreen()

        # Load the breathing practice (only rounds, no background/music)
        scheme_data, self.phases = load_scheme(scheme_path)
        # Load theme (colors + background image + background music)
        self.theme = load_theme(theme_path)

        # Phase progression
        self.index = 0
        self.t = 0.0
        self.total_duration = sum(p.duration for p in self.phases)
        self.phase_start_times = []
        acc = 0.0
        for ph in self.phases:
            self.phase_start_times.append(acc)
            acc += ph.duration

        # Animation state
        self.base_radius: float = self.MIN_R
        self.pulse_radius: float = 0
        self.radius: float = self.MIN_R
        self.phase_start_radius: float = self.MAX_R

        # Background image (from theme)
        bg_rel = self.theme.get("background_image", "assets/background.jpg")
        bg_path = files("wimhof").joinpath(bg_rel)
        self.bg = QPixmap(str(bg_path))

        # Finishing sequence
        self.finishing = False
        self.finish_t = 0.0
        self.finish_duration = 6.0

        # Animation timer
        self.timer = QTimerWithPause(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

        # Background music (from theme)
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.4)
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        music_rel = self.theme.get("background_music", "assets/music.mp3")
        music_path = files("wimhof").joinpath(music_rel)
        self.player.setSource(QUrl.fromLocalFile(str(music_path)))
        self.player.setLoops(QMediaPlayer.Loops.Infinite)
        self.player.play()

    # ------------------------------------------------------------------
    # Theme color lookup with optional alpha override
    # ------------------------------------------------------------------
    def color(self, name: str, alpha: int = 128) -> QColor:
        """
        Returns a QColor from the theme's 'colors' dictionary.
        Expects theme structure: theme['theme']['colors'][name]
        """
        c = self.theme["theme"]["colors"][name]
        if len(c) == 4:
            r, g, b, a = c
            return QColor(r, g, b, a)
        else:  # len(c) == 3
            r, g, b = c
            a = alpha if alpha is not None else 255
            return QColor(r, g, b, a)

    # ------------------------------------------------------------------
    # Non‑linear interpolation helper
    # ------------------------------------------------------------------
    def _interpolate(
        self, start: float, target: float, t: float, alpha: float = 1.0
    ) -> float:
        """
        Non-linear interpolation using power curve.
        t in [0,1]; applies t = t ** alpha.
        alpha = 1.0 → linear, alpha < 1 → slow start, alpha > 1 → fast start.
        """
        t = t**alpha
        return start + (target - start) * t

    @property
    def phase(self) -> Phase:
        return self.phases[self.index]

    # ------------------------------------------------------------------
    # Phase transition
    # ------------------------------------------------------------------
    def next(self):
        self.index += 1
        self.phase_start_radius = self.base_radius + self.pulse_radius
        self.t = 0.0
        if self.index >= len(self.phases):
            self.index = len(self.phases) - 1
            self.finishing = True
            self.finish_t = 0.0

    # ------------------------------------------------------------------
    # Finishing / fade out animation
    # ------------------------------------------------------------------
    def finish_tick(self):
        dt = 0.016
        if not self.completed:
            self.finish_t += dt
        progress = min(self.finish_t / self.finish_duration, 1.0)
        progress = ease(progress)
        volume = 0.4 * (1.0 - progress)
        self.audio_output.setVolume(volume)
        self.pulse_radius *= 0.96
        if progress >= 1.0:
            self.completed = True
            self.timer.stop()
            self.player.stop()
        self.update()

    # ------------------------------------------------------------------
    # Main animation tick (called every ~16 ms)
    # ------------------------------------------------------------------
    def tick(self):
        if self.finishing:
            self.finish_tick()
            return

        dt = 0.016
        self.t += dt
        p = self.phase
        progress = min(self.t / p.duration, 1.0)
        progress = ease(progress)
        above_max = self.MAX_R * 1.25
        self.pulse_radius = 0

        # ----- Update base_radius according to behavior -----
        if p.behavior in ("expand", "shrink", "expand_big", "prepare", "hold_big"):
            target_map = {
                "expand": self.MAX_R,
                "shrink": self.MIN_R,
                "expand_big": above_max,
                "prepare": self.MIN_R,
                "hold_big": above_max,
            }
            target = target_map[p.behavior]
            self.base_radius = self._interpolate(
                self.phase_start_radius, target, progress, alpha=1.0
            )
        elif p.behavior == "fade_out":
            target = self.MAX_R
            self.base_radius = self._interpolate(
                self.base_radius, target, progress / 4, alpha=0.5
            )
        elif p.behavior == "hold":
            pass  # radius unchanged
        elif p.behavior == "pulse":
            # Subtle oscillation, amplitude 3 pixels
            self.pulse_radius = math.sin(self.t * 8.0) * 3.0

        self.radius = self.base_radius + self.pulse_radius

        if self.t >= p.duration:
            self.next()
        self.update()

    # ------------------------------------------------------------------
    # Overall session progress (0..1)
    # ------------------------------------------------------------------
    def current_progress(self) -> float:
        if self.completed or self.finishing:
            return 1.0
        phase_start = self.phase_start_times[self.index]
        current_time = phase_start + self.t
        return min(current_time / self.total_duration, 1.0)

    # ------------------------------------------------------------------
    # Paint everything
    # ------------------------------------------------------------------
    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        if not self.bg.isNull():
            painter.drawPixmap(self.rect(), self.bg)

        p = self.phase
        cx = self.width() / 2
        cy = self.height() / 2

        # ----- Overlay (dimming effect for prepare/fade_out) -----
        overlay_alpha = 140
        if p.behavior == "prepare":
            fade = ease(min(self.t / p.duration, 1.0))
            overlay_alpha = int(140 * ease(fade))
        elif p.behavior == "fade_out":
            fade = 1.0 - min(self.t / p.duration, 1.0)
            overlay_alpha = int(140 * ease(fade))
        if not self.finishing:
            painter.fillRect(self.rect(), self.color("overlay_black", overlay_alpha))

        # ----- Progress timeline -----
        self.draw_timeline(painter)

        # ----- Section name (top) -----
        painter.setPen(self.color("round_section_text"))
        painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 22, QFont.Weight.Bold))
        space = 56
        painter.drawText(
            self.rect().adjusted(space, space, -space, -space),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            p.section,
        )

        # ----- Central text (cycles or countdown) -----
        if not self.finishing and not self.completed:
            if p.display == "cycles":
                painter.setPen(self.color("center_text"))
                painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 44, QFont.Weight.Bold))
                text = str(p.cycle_remaining)
            elif p.display == "countdown":
                painter.setPen(self.color("center_text"))
                painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 44, QFont.Weight.Bold))
                text = str(max(0, math.ceil(p.duration - self.t)))
            else:
                painter.setPen(self.color("center_text"))
                painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 40))
                text = ""
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

        # ----- Phase label (e.g., "Inhale", "Exhale") -----
        painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 32, QFont.Weight.Bold))
        painter.setPen(self.color("center_text"))
        painter.drawText(
            QRectF(0, self.height() * 0.15, self.width(), 100),
            Qt.AlignmentFlag.AlignHCenter,
            p.label,
        )

        # ----- Keyboard hints (lower left) -----
        painter.setFont(QFont(_HINTS_FONT_NAME, 16, QFont.Weight.Medium))
        painter.setPen(self.color("hints_text"))
        painter.drawText(
            self.rect().adjusted(space, space, -space, -space),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            "  M   - mute/unmute\n Esc  - quit\nSpace - pause or restart",
        )

        # ----- Breathing ring -----
        self.draw_ring(painter, cx, cy)

        # ----- Pause / completion overlay -----
        if self.paused:
            self.draw_shadow(painter, "Paused", "Press Space to continue", 220)
        elif self.finishing or self.completed:
            self.draw_completion_overlay(painter, 220)

        painter.end()

    # ------------------------------------------------------------------
    # Completion overlay (fades in at the end)
    # ------------------------------------------------------------------
    def draw_completion_overlay(self, painter, alpha=220):
        if self.completed:
            progress = 1.0
        else:
            progress = min(self.finish_t / self.finish_duration, 1.0)
            progress = ease(progress)
        progress_alpha = int(alpha * progress)
        self.draw_shadow(painter, "Completed", "Have a nice day!", progress_alpha)

    # ------------------------------------------------------------------
    # Generic shadow/pause overlay
    # ------------------------------------------------------------------
    def draw_shadow(
        self, painter, main_text: str, supplementary: str, shadow_alpha: int = 220
    ):
        painter.fillRect(self.rect(), self.color("overlay_black", shadow_alpha))
        painter.setPen(self.color("shadow_main_text", shadow_alpha))
        painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 56, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, main_text)
        painter.setPen(self.color("shadow_suppl_text", shadow_alpha))
        painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 22))
        painter.drawText(
            self.rect().adjusted(0, 180, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            supplementary,
        )

    # ------------------------------------------------------------------
    # Draw the breathing ring (4 outer layers + main inner layer)
    # ------------------------------------------------------------------
    def draw_ring(self, painter, cx, cy):
        r = self.radius
        # Outer layers: decreasing alpha and width
        for i in range(4):
            pen = QPen(self.color("ring_base", 20 - i * 4))
            pen.setWidth(18 - i * 3)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        # Main inner layer
        pen = QPen(self.color("ring_main"))
        pen.setWidth(7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

    # ------------------------------------------------------------------
    # Draw the progress timeline bar with section markers
    # ------------------------------------------------------------------
    def draw_timeline(self, painter):
        margin = 140
        x = margin
        y = self.height() - 90
        w = self.width() - margin * 2
        h = 16
        radius = h / 2
        rect = QRectF(x, y, w, h)
        progress = self.current_progress()
        fill_w = w * progress
        fill_rect = QRectF(x, y, fill_w, h)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.color("timeline_background"))
        painter.drawRoundedRect(rect, radius, radius)

        painter.setBrush(self.color("timeline_fill"))
        painter.drawRoundedRect(fill_rect, radius, radius)

        glow_pen = QPen(self.color("timeline_glow"))
        glow_pen.setWidth(10)
        painter.setPen(glow_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(fill_rect, radius, radius)

        # Markers for section transitions
        transitions = []
        acc = 0.0
        prev_section = None
        for ph in self.phases:
            section = getattr(ph, "section", None)
            if prev_section is None:
                prev_section = section
            elif section != prev_section:
                transitions.append(acc)
                prev_section = section
            acc += ph.duration

        for t in transitions:
            marker_progress = t / self.total_duration
            mx = x + w * marker_progress
            active = progress >= marker_progress
            if active:
                color = self.color("marker_active")
                size = 12
            else:
                color = self.color("marker_inactive")
                size = 10
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QRectF(mx - size / 2, y + h / 2 - size / 2, size, size))

    # ------------------------------------------------------------------
    # Keyboard event handler (Esc, M, Space)
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            key = QKeyEvent(event)
            if key.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
                QApplication.quit()
                return True
            elif key.key() == Qt.Key.Key_M:
                self.muted = not self.muted
                if self.muted:
                    self.player.pause()
                else:
                    if not self.paused and not self.completed:
                        self.player.play()
                return True
            elif key.key() == Qt.Key.Key_Space:
                if self.finishing or self.completed:
                    # Restart session
                    self.completed = False
                    self.finishing = False
                    self.finish_t = 0.0
                    self.index = 0
                    self.t = 0.0
                    self.base_radius = self.MIN_R
                    self.pulse_radius = 0
                    self.radius = self.MIN_R
                    self.audio_output.setVolume(0.4)
                    self.timer.reset()
                    if not self.muted:
                        self.player.play()
                elif not self.paused:
                    self.paused = True
                    self.timer.pause()
                    self.player.pause()
                else:
                    self.paused = False
                    self.timer.resume()
                    if not self.muted:
                        self.player.play()
                self.update()
                return True
        return super().eventFilter(obj, event)


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config.yaml",
        help="Main configuration file (contains theme and breathing paths)",
    )
    parser.add_argument(
        "-t",
        "--theme",
        type=str,
        help="Override theme file (e.g., themes/default.yaml)",
    )
    parser.add_argument(
        "-b",
        "--breathing",
        type=str,
        help="Override breathing practice file (e.g., presets/wimhof.yaml)",
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)
    wimhof_path = files("wimhof")
    icon_path = wimhof_path.joinpath("assets", "app_icon.png")
    app.setWindowIcon(QIcon(str(icon_path)))

    # Read main config file
    config_path = wimhof_path.joinpath(args.config)
    try:
        with open(config_path, encoding="utf-8") as f:
            main_cfg = yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to load main config {config_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Get paths from config, then override with command line if provided
    theme_rel = main_cfg.get("theme", "themes/default.yaml")
    breathing_rel = main_cfg.get("breathing", "presets/wimhof.yaml")

    if args.theme:
        theme_rel = args.theme
    if args.breathing:
        breathing_rel = args.breathing

    theme_path = wimhof_path.joinpath(theme_rel)
    breathing_path = wimhof_path.joinpath(breathing_rel)

    try:
        w = BreathingWidget(str(breathing_path), str(theme_path))
    except Exception as e:
        print(f"Failed to load breathing practice or theme: {e}", file=sys.stderr)
        sys.exit(1)

    app.installEventFilter(w)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
