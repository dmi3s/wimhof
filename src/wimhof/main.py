from __future__ import annotations

import argparse
import math
import sys
import time
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

from .animation import interpolate, target_radius
from .model import Phase, load_theme
from .session import BreathingSession

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
        self.muted = False
        self.showFullScreen()

        # Load the breathing practice (only rounds, no background/music)
        self.session = BreathingSession.from_preset(scheme_path)
        # Load theme (colors + background image + background music)
        self.theme = load_theme(theme_path)

        # Animation state
        self.base_radius: float = self.MIN_R
        self.radius: float = self.MIN_R
        self.phase_start_radius: float = self.MIN_R

        # Background image (from theme)
        bg_rel = self.theme.get("background_image", "assets/background.jpg")
        bg_path = files("wimhof").joinpath(bg_rel)
        self.bg = QPixmap(str(bg_path))

        # Animation timer
        self.timer = QTimerWithPause(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        self._last_tick = time.monotonic()

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
    # Session state mirrors (read-only views over self.session)
    # ------------------------------------------------------------------
    @property
    def phase(self) -> Phase:
        return self.session.current_phase

    @property
    def phases(self) -> list[Phase]:
        return self.session.phases

    @property
    def index(self) -> int:
        return self.session.index

    @property
    def t(self) -> float:
        return self.session.t

    @property
    def finishing(self) -> bool:
        return self.session.finishing

    @property
    def completed(self) -> bool:
        return self.session.completed

    @property
    def finish_t(self) -> float:
        return self.session.finish_t

    @property
    def finish_duration(self) -> float:
        return self.session.finish_duration

    @property
    def total_duration(self) -> float:
        return self.session.total_duration

    # ------------------------------------------------------------------
    # Finishing animation (audio fade-out)
    # ------------------------------------------------------------------
    def finish_tick(self):
        now = time.monotonic()
        dt = min(now - self._last_tick, 0.1)
        self._last_tick = now
        self.session.advance(dt)
        progress = min(self.session.finish_t / self.session.finish_duration, 1.0)
        progress = ease(progress)
        volume = 0.4 * (1.0 - progress)
        self.audio_output.setVolume(volume)
        if self.session.completed:
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

        now = time.monotonic()
        dt = min(now - self._last_tick, 0.1)
        self._last_tick = now

        prev_index = self.session.index
        prev_finishing = self.session.finishing
        self.session.advance(dt)

        # A phase boundary (or entry into finishing) just happened:
        # start the next radius interpolation from the current radius.
        if self.session.index != prev_index or (
            self.session.finishing and not prev_finishing
        ):
            self.phase_start_radius = self.base_radius

        p = self.phase
        progress = min(self.session.t / p.duration, 1.0)
        progress = ease(progress)

        # ----- Update base_radius according to behavior (pure math) -----
        target = target_radius(p.behavior, self.MIN_R, self.MAX_R)
        if target is not None:
            self.base_radius = interpolate(
                self.phase_start_radius, target, progress, alpha=1.0
            )
        # hold (target is None): radius unchanged

        self.radius = self.base_radius

        self.update()

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

        # ----- Overlay (constant dimming for focus) -----
        if not self.finishing:
            painter.fillRect(self.rect(), self.color("overlay_black", 140))

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
                text = str(max(0, math.ceil(p.duration - self.session.t)))
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
        if self.session.completed:
            progress = 1.0
        else:
            progress = min(self.session.finish_t / self.session.finish_duration, 1.0)
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
        progress = self.session.progress()
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
                    self.session.restart()
                    self.base_radius = self.MIN_R
                    self.radius = self.MIN_R
                    self.audio_output.setVolume(0.4)
                    self.timer.reset()
                    self._last_tick = time.monotonic()
                    if not self.muted:
                        self.player.play()
                elif not self.paused:
                    self.paused = True
                    self.timer.pause()
                    self.player.pause()
                else:
                    self.paused = False
                    self.timer.resume()
                    self._last_tick = time.monotonic()
                    if not self.muted:
                        self.player.play()
                self.update()
                return True
        return super().eventFilter(obj, event)


# ----------------------------------------------------------------------
# Headless simulation (no Qt, no audio) – the "eval" of a breathing run
# ----------------------------------------------------------------------
def run_simulation(scheme_path: str, dt: float = 0.25) -> None:
    sess = BreathingSession.from_preset(scheme_path)
    clock = 0.0
    prev_index = sess.index
    was_finishing = sess.finishing
    print(
        f"Headless simulation: {len(sess.phases)} phases, "
        f"total {sess.total_duration:.1f}s (dt={dt}s)\n"
    )
    print(
        f"  t={clock:6.2f}s  start  -> "
        f"{sess.current_phase.label} [{sess.current_phase.section}]"
    )
    while not sess.completed:
        sess.advance(dt)
        clock += dt
        if sess.index != prev_index:
            print(
                f"  t={clock:6.2f}s  phase  -> "
                f"{sess.current_phase.label} [{sess.current_phase.section}]"
            )
            prev_index = sess.index
        elif sess.finishing and not was_finishing:
            print(
                f"  t={clock:6.2f}s  finish -> "
                f"{sess.current_phase.label} [{sess.current_phase.section}]"
            )
        was_finishing = sess.finishing
    print(f"\nSession completed at t={clock:.2f}s.")


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
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
    parser.add_argument(
        "-s",
        "--simulate",
        action="store_true",
        help="Run a headless simulation of the session (no GUI/audio)",
    )
    args = parser.parse_args()

    wimhof_path = files("wimhof")

    # Read main config file to resolve default breathing/theme paths
    config_path = wimhof_path.joinpath("config.yaml")
    try:
        with open(str(config_path), encoding="utf-8") as f:
            main_cfg = yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to load main config {config_path}: {e}", file=sys.stderr)
        sys.exit(1)

    theme_rel = main_cfg.get("theme", "themes/default.yaml")
    breathing_rel = main_cfg.get("breathing", "presets/wimhof.yaml")
    if args.theme:
        theme_rel = args.theme
    if args.breathing:
        breathing_rel = args.breathing

    breathing_path = wimhof_path.joinpath(breathing_rel)
    theme_path = wimhof_path.joinpath(theme_rel)

    # Headless mode: no Qt application needed
    if args.simulate:
        try:
            run_simulation(str(breathing_path))
        except Exception as e:
            print(f"Failed to simulate: {e}", file=sys.stderr)
            sys.exit(1)
        return

    app = QApplication(sys.argv)
    icon_path = wimhof_path.joinpath("assets", "app_icon.png")
    app.setWindowIcon(QIcon(str(icon_path)))

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
