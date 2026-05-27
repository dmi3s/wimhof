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

# _HINTS_FONT_NAME = "Sans-serif"
_HINTS_FONT_NAME = "Monospace"

# _APP_DEFAULT_FONT_NAME = "Liberation Sans"
_APP_DEFAULT_FONT_NAME = "Sans"


# ============================================================
# TIMER
# ============================================================


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


# ============================================================
# DATA MODEL
# ============================================================


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


# ============================================================
# LOAD CONFIG HELPER
# ============================================================


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
                    merged_item = {
                        **base_sequence[i],
                        **item,
                    }
                else:
                    merged_item = item

                merged_sequence.append(merged_item)

            result["sequence"] = merged_sequence

        else:
            result[key] = value

    return result


# ============================================================
# LOAD CONFIG
# ============================================================


def load_config(path: str) -> tuple[dict, list[Phase]]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rounds = data["rounds"]

    phases: list[Phase] = []

    total_rounds = len(rounds)

    base_round: dict | None = None

    for ri, round_cfg in enumerate(rounds):
        if round_cfg.get("inherit", False):
            if base_round is None:
                raise ValueError(...)

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


# ============================================================
# EASING
# ============================================================


def ease(t: float) -> float:
    return QEasingCurve(QEasingCurve.Type.InOutSine).valueForProgress(t)


# ============================================================
# MAIN WIDGET
# ============================================================


class BreathingWidget(QWidget):
    MIN_R = 80
    MAX_R = 260

    def __init__(self, config_path: str):
        super().__init__()

        self.setWindowTitle("Breathing Trainer")

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.paused = False
        self.completed = False
        self.muted = False

        self.showFullScreen()

        cfg, self.phases = load_config(config_path)

        self.index = 0
        self.t = 0.0

        self.total_duration = sum(p.duration for p in self.phases)

        self.phase_start_times = []

        acc = 0.0

        for ph in self.phases:
            self.phase_start_times.append(acc)
            acc += ph.duration

        # ====================================================
        # CIRCLE RADIUS ANIMATION
        # ====================================================

        self.base_radius = self.MIN_R
        self.pulse_radius = 0
        self.radius = self.MIN_R
        self.phase_start_radius = self.MAX_R

        # ====================================================
        # BACKGROUND
        # ====================================================

        bg_path = files("wimhof").joinpath(cfg["background_image"])

        self.bg = QPixmap(str(bg_path))

        # ====================================================
        # FINISHING
        # ====================================================

        self.finishing = False
        self.finish_t = 0.0
        self.finish_duration = 6.0

        # ====================================================
        # TIMER
        # ====================================================

        self.timer = QTimerWithPause(self)

        self.timer.timeout.connect(self.tick)

        self.timer.start(16)

        # ====================================================
        # MUSIC
        # ====================================================

        self.audio_output = QAudioOutput()

        self.audio_output.setVolume(0.4)

        self.player = QMediaPlayer()

        self.player.setAudioOutput(self.audio_output)

        music_path = files("wimhof").joinpath(cfg["background_music"])

        self.player.setSource(QUrl.fromLocalFile(str(music_path)))

        self.player.setLoops(QMediaPlayer.Loops.Infinite)

        self.player.play()

    # --------------------------------------------------------

    @property
    def phase(self) -> Phase:
        return self.phases[self.index]

    # --------------------------------------------------------

    def next(self):
        self.index += 1

        self.phase_start_radius = self.base_radius + self.pulse_radius
        self.t = 0.0

        if self.index >= len(self.phases):
            self.index = len(self.phases) - 1

            self.finishing = True

            self.finish_t = 0.0

    # --------------------------------------------------------

    def finish_tick(self):
        dt = 0.016

        if not self.completed:
            self.finish_t += dt

        progress = min(
            self.finish_t / self.finish_duration,
            1.0,
        )

        progress = ease(progress)

        # ====================================================
        # audio fade
        # ====================================================

        volume = 0.4 * (1.0 - progress)

        self.audio_output.setVolume(volume)

        # ====================================================
        # ring dissolve
        # ====================================================

        self.pulse_radius *= 0.96

        # ====================================================
        # completed
        # ====================================================

        if progress >= 1.0:
            self.completed = True
            self.timer.stop()
            self.player.stop()

        self.update()

    # --------------------------------------------------------

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

        # ====================================================
        # reset pulse
        # ====================================================

        self.pulse_radius = 0

        # ====================================================
        # behavior engine
        # ====================================================

        if p.behavior == "expand":
            target = self.MAX_R
            # self.base_radius = self.MIN_R + (self.MAX_R - self.MIN_R) * progress

            self.base_radius = (
                self.phase_start_radius + (target - self.phase_start_radius) * progress
            )

        elif p.behavior == "shrink":
            target = self.MIN_R
            self.base_radius = (
                self.phase_start_radius - (self.phase_start_radius - target) * progress
            )

        elif p.behavior == "expand_big":
            target = above_max
            self.base_radius = (
                self.phase_start_radius + (target - self.phase_start_radius) * progress
            )

        elif p.behavior == "hold":
            pass

        elif p.behavior == "hold_big":
            self.base_radius = (
                self.phase_start_radius + (target - self.phase_start_radius) * progress
            )

        elif p.behavior == "prepare":
            target = self.MIN_R
            self.base_radius = (
                self.phase_start_radius - (self.phase_start_radius - target) * progress
            )

        elif p.behavior == "fade_out":
            self.base_radius = (
                self.base_radius - (self.base_radius - self.MAX_R) * progress / 4
            )

        # ====================================================
        # pulse modifiers
        # ====================================================

        if p.behavior == "pulse_small":
            self.pulse_radius = math.sin(self.t * 2.0) * 3.0

        elif p.behavior == "pulse_large":
            self.pulse_radius = math.sin(self.t * 2.0) * 4.0

        # ====================================================

        self.radius = self.base_radius + self.pulse_radius

        if self.t >= p.duration:
            self.next()

        self.update()

    # --------------------------------------------------------

    def current_progress(self) -> float:
        if self.completed or self.finishing:
            return 1.0

        phase_start = self.phase_start_times[self.index]

        current_time = phase_start + self.t

        return min(current_time / self.total_duration, 1.0)

    # --------------------------------------------------------

    def paintEvent(self, _):
        painter = QPainter(self)

        painter.setRenderHint(QPainter.Antialiasing)

        if not self.bg.isNull():
            painter.drawPixmap(self.rect(), self.bg)

        p = self.phase

        cx = self.width() / 2
        cy = self.height() / 2

        # ====================================================
        # OVERLAY
        # ====================================================

        overlay_alpha = 140

        if p.behavior == "prepare":
            fade = ease(min(self.t / p.duration, 1.0))

            overlay_alpha = int(140 * fade)

        elif p.behavior == "fade_out":
            fade = 1.0 - min(self.t / p.duration, 1.0)

            overlay_alpha = int(140 * ease(fade))

        if not self.finishing:
            painter.fillRect(
                self.rect(),
                QColor(0, 0, 0, overlay_alpha),
            )

        # ====================================================
        # TIMELINE
        # ====================================================

        self.draw_timeline(painter)

        # ====================================================
        # ROUND
        # ====================================================

        painter.setPen(QColor(200, 200, 200, 230))

        painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 22, QFont.Bold))

        space = 56

        # painter.drawText(
        #     self.rect().adjusted(space, space, -space, -space),
        #     Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
        #     f"Round {p.round_index}/{p.round_total}",
        # )
        painter.drawText(
            self.rect().adjusted(space, space, -space, -space),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            p.section,
        )

        # ====================================================
        # CENTER TEXT
        # ====================================================

        if not self.finishing and not self.completed:
            if p.display == "cycles":
                painter.setPen(QColor(120, 220, 255, 220))
                painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 44, QFont.Weight.Bold))

            elif p.display == "countdown":
                painter.setPen(QColor(255, 255, 255, 240))
                painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 44, QFont.Weight.Bold))

            else:
                painter.setPen(QColor(255, 255, 255, 180))
                painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 40))

            if p.display == "cycles":
                text = str(p.cycle_remaining)

            elif p.display == "countdown":
                text = str(max(0, math.ceil(p.duration - self.t)))

            else:
                text = ""

            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

        # ====================================================
        # LABEL
        # ====================================================

        painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 32, QFont.Weight.Bold))
        painter.setPen(QColor(255, 255, 255, 240))

        painter.drawText(
            QRectF(
                0,
                self.height() * 0.15,
                self.width(),
                100,
            ),
            Qt.AlignmentFlag.AlignHCenter,
            p.label,
        )

        # ====================================================
        # KEYBOARD HINTS
        # ====================================================

        painter.setFont(QFont(_HINTS_FONT_NAME, 16, QFont.Medium))
        painter.setPen(QColor(0x1C, 0x24, 0x65, 200))

        painter.drawText(
            self.rect().adjusted(space, space, -space, -space),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            "M - (un)mute\nSpace - pause\nQ or Esc - quit",
        )

        # ====================================================
        # RING
        # ====================================================

        self.draw_ring(painter, cx, cy)

        # ====================================================
        # PAUSE / FINISHING
        # ====================================================

        if self.paused:
            self.draw_shadow(painter, "Paused", "Press Space to continue", 220)
        elif self.finishing or self.completed:
            self.draw_completion_overlay(painter, 220)

        painter.end()

    # --------------------------------------------------------

    def draw_completion_overlay(self, painter, alpha=220):
        if self.completed:
            progress = 1.0
        else:
            progress = min(
                self.finish_t / self.finish_duration,
                1.0,
            )

            progress = ease(progress)

        progress_alpha = int(alpha * progress)

        self.draw_shadow(
            painter,
            "Completed",
            "Have a nice day!",
            progress_alpha,
        )

    # --------------------------------------------------------

    def draw_shadow(
        self,
        painter: QPainter,
        main_text: str,
        supplementary: str,
        shadow_alpha: int = 220,
    ):
        painter.fillRect(self.rect(), QColor(0, 0, 0, shadow_alpha))

        painter.setPen(QColor(255, 255, 255, shadow_alpha))

        painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 56, QFont.Weight.Bold))

        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, main_text)

        painter.setFont(QFont(_APP_DEFAULT_FONT_NAME, 22))

        painter.drawText(
            self.rect().adjusted(0, 180, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            supplementary,
        )

    # --------------------------------------------------------

    def draw_ring(self, painter, cx, cy):
        r = self.radius

        for i in range(4):
            pen = QPen(QColor(80, 200, 255, 20 - i * 4))

            pen.setWidth(18 - i * 3)

            painter.setPen(pen)

            painter.setBrush(Qt.NoBrush)

            painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        pen = QPen(QColor(120, 220, 255, 140))

        pen.setWidth(7)

        pen.setCapStyle(Qt.RoundCap)

        painter.setPen(pen)

        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

    # --------------------------------------------------------
    # TIMELINE
    # --------------------------------------------------------

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

        # ====================================================
        # background
        # ====================================================

        painter.setPen(Qt.NoPen)

        painter.setBrush(QColor(255, 255, 255, 28))

        painter.drawRoundedRect(rect, radius, radius)

        # ====================================================
        # fill
        # ====================================================

        painter.setBrush(QColor(0x5C, 0x14, 0x5C, 128))

        painter.drawRoundedRect(fill_rect, radius, radius)

        # ====================================================
        # glow
        # ====================================================

        glow_pen = QPen(QColor(0x5C, 0x14, 0x5C, 40))

        glow_pen.setWidth(10)

        painter.setPen(glow_pen)

        painter.setBrush(Qt.NoBrush)

        painter.drawRoundedRect(fill_rect, radius, radius)

        # ====================================================
        # section transition markers
        # ====================================================

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

        # ====================================================
        # markers
        # ====================================================

        for t in transitions:
            marker_progress = t / self.total_duration

            mx = x + w * marker_progress

            active = progress >= marker_progress

            if active:
                color = QColor(220, 240, 255, 120)
                size = 12
            else:
                color = QColor(255, 255, 255, 70)
                size = 10

            painter.setPen(Qt.NoPen)

            painter.setBrush(color)

            painter.drawEllipse(
                QRectF(
                    mx - size / 2,
                    y + h / 2 - size / 2,
                    size,
                    size,
                )
            )

    # --------------------------------------------------------

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
                if self.completed:
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


# ============================================================
# MAIN
# ============================================================


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-c",
        "--config",
        type=str,
        help="Path to YAML config",
    )

    args = parser.parse_args()

    app = QApplication(sys.argv)

    icon_path = files("wimhof") / "assets" / "app_icon.png"

    app.setWindowIcon(QIcon(str(icon_path)))

    if args.config:
        config_path = files("wimhof") / args.config
    else:
        config_path = files("wimhof") / "config.yaml"

    try:
        w = BreathingWidget(str(config_path))

    except Exception as e:
        print(f"Failed to load config: {e}")

        sys.exit(1)

    app.installEventFilter(w)

    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
