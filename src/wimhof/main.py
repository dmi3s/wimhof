from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from importlib.resources import files

import yaml
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
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
    duration: float
    label: str
    round_index: int
    round_total: int
    cycle_remaining: int = 0
    cycle_total: int = 0


# ============================================================
# CONFIG LOADER
# ============================================================


def load_config(path: str) -> list[Phase]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rounds = data["rounds"]
    total_rounds = len(rounds)

    phases: list[Phase] = []

    base_round = None

    for ri, r in enumerate(rounds):
        # ====================================================
        # inherit safe merge
        # ====================================================

        if r.get("inherit", False):
            if base_round is None:
                raise ValueError(f"Round {ri + 1}: inherit without base round")

            cfg = {**base_round, **{k: v for k, v in r.items() if k != "inherit"}}
        else:
            cfg = r
            base_round = r

        reps = cfg["repetitions"]

        prepare = cfg.get("prepare", {})
        inhale = cfg["inhale"]
        exhale = cfg["exhale"]

        # ====================================================
        # 1. PREPARE PHASE
        # ====================================================

        if prepare:
            phases.append(
                Phase(
                    type="prepare",
                    duration=prepare["duration"],
                    label=prepare["label"],
                    round_index=ri + 1,
                    round_total=total_rounds,
                )
            )

        # ====================================================
        # 1. BREATHING CYCLES
        # ====================================================

        for i in range(reps):
            remaining = reps - i

            phases.append(
                Phase(
                    type="inhale",
                    duration=inhale["duration"],
                    label=inhale["label"],
                    round_index=ri + 1,
                    round_total=total_rounds,
                    cycle_remaining=remaining,
                    cycle_total=reps,
                )
            )

            phases.append(
                Phase(
                    type="exhale",
                    duration=exhale["duration"],
                    label=exhale["label"],
                    round_index=ri + 1,
                    round_total=total_rounds,
                    cycle_remaining=remaining,
                    cycle_total=reps,
                )
            )

        # ====================================================
        # 2. HOLD (LONG BEFORE BREATHWORK BREAK)
        # ====================================================

        phases.append(
            Phase(
                type="hold",
                duration=cfg["hold"]["duration"],
                label=cfg["hold"]["label"],
                round_index=ri + 1,
                round_total=total_rounds,
            )
        )

        # ====================================================
        # 3. DEEP INHALE
        # ====================================================

        phases.append(
            Phase(
                type="deep_inhale",
                duration=cfg["deep_inhale"]["duration"],
                label=cfg["deep_inhale"]["label"],
                round_index=ri + 1,
                round_total=total_rounds,
            )
        )

        # ====================================================
        # 4. FINAL HOLD (POST BREATHWORK)
        # ====================================================

        phases.append(
            Phase(
                type="final_hold",
                duration=cfg["final_hold"]["duration"],
                label=cfg["final_hold"]["label"],
                round_index=ri + 1,
                round_total=total_rounds,
            )
        )

        # ====================================================
        # 5. RELAX COUNTDOWN (NO RING)
        # ====================================================

        phases.append(
            Phase(
                type="relax_countdown",
                duration=cfg["relax_countdown"]["duration"],
                label=cfg["relax_countdown"]["label"],
                round_index=ri + 1,
                round_total=total_rounds,
            )
        )

    return phases


# ============================================================
# EASING
# ============================================================


def ease(t: float) -> float:
    return QEasingCurve(QEasingCurve.InOutSine).valueForProgress(t)


# ============================================================
# MAIN WIDGET
# ============================================================


class BreathingWidget(QWidget):
    MIN_R = 80
    MAX_R = 260

    def __init__(self, config_path: str):
        super().__init__()

        self.setWindowTitle("Wim Hof Breathing")
        self.setWindowFlags(Qt.FramelessWindowHint)

        self.paused = False
        self.completed = False
        self.muted = False

        self.showFullScreen()

        self.phases = load_config(config_path)
        self.index = 0
        self.t = 0.0

        self.total_duration = sum(p.duration for p in self.phases)

        self.phase_start_times = []

        acc = 0.0

        for ph in self.phases:
            self.phase_start_times.append(acc)
            acc += ph.duration

        self.radius = self.MIN_R

        bg_path = files("wimhof.assets").joinpath("background.jpg")
        self.bg = QPixmap(str(bg_path))

        self.timer = QTimerWithPause(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

        # Music
        # keep references (IMPORTANT)
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.4)

        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)

        music_path = files("wimhof.assets").joinpath("music.mp3")
        self.player.setSource(QUrl.fromLocalFile(str(music_path)))

        self.player.setLoops(QMediaPlayer.Loops.Infinite)
        self.player.play()

        print(self.player.mediaStatus())
        print(self.player.errorString())

    # --------------------------------------------------------

    @property
    def phase(self) -> Phase:
        return self.phases[self.index]

    # --------------------------------------------------------

    def next(self):
        self.index += 1
        self.t = 0.0

        if self.index >= len(self.phases):
            self.index = len(self.phases) - 1

            self.completed = True

            self.timer.stop()
            self.player.stop()

            return

    # --------------------------------------------------------

    def tick(self):
        dt = 0.016
        self.t += dt

        p = self.phase
        progress = min(self.t / p.duration, 1.0)
        progress = ease(progress)

        above_max = self.MAX_R * 1.25  # <- немного "выше нормы"

        if p.type == "inhale":
            self.radius = self.MIN_R + (self.MAX_R - self.MIN_R) * progress

        elif p.type == "exhale":
            self.radius = self.MAX_R - (self.MAX_R - self.MIN_R) * progress

        elif p.type == "deep_inhale":
            base = self.MIN_R
            deep_max = above_max

            self.radius = base + (deep_max - base) * progress

        elif p.type == "hold":
            pulse = math.sin(self.t * 2.0) * 3.0
            self.radius = self.MIN_R + pulse

        elif p.type == "final_hold":
            pulse = math.sin(self.t * 2.0) * 3.0
            self.radius = above_max + pulse

        elif p.type == "relax_countdown":
            self.radius = self.radius - (self.radius - self.MAX_R) * progress / 4
            # was: self.radius = 0

        elif p.type == "prepare":
            start_r = self.MAX_R * 0.9
            end_r = self.MIN_R

            self.radius = start_r - (start_r - end_r) * progress

        if self.t >= p.duration:
            self.next()

        self.update()

    # --------------------------------------------------------
    #
    def current_progress(self) -> float:
        if self.completed:
            return 1.0

        phase_start = self.phase_start_times[self.index]

        current_time = phase_start + self.t

        return min(current_time / self.total_duration, 1.0)

    # --------------------------------------------------------

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # background
        if not self.bg.isNull():
            painter.drawPixmap(self.rect(), self.bg)

        p = self.phase

        cx = self.width() / 2
        cy = self.height() / 2

        # ====================================================
        # BACKGROUND
        # ====================================================

        NORMAL_OVERLAY = 140

        overlay_alpha = NORMAL_OVERLAY

        # ====================================================
        # PREPARE -> FADE IN
        # ====================================================

        if p.type == "prepare":
            progress = min(self.t / p.duration, 1.0)
            progress = ease(progress)
            overlay_alpha = int(NORMAL_OVERLAY * progress)

        # ====================================================
        # RELAX -> FADE OUT
        # ====================================================

        elif p.type == "relax_countdown":
            fade = 1.0 - min(self.t / p.duration, 1.0)
            fade = ease(fade)
            overlay_alpha = int(NORMAL_OVERLAY * fade)

        painter.fillRect(self.rect(), QColor(0, 0, 0, overlay_alpha))

        # ====================================================
        # DRAW TIMELINE
        # ====================================================

        self.draw_timeline(painter)

        # ====================================================
        # ROUND LABEL
        # ====================================================

        painter.setPen(QColor(255, 255, 255, 230))

        painter.setFont(QFont("Arial", 22, QFont.Bold))

        space = 56

        painter.drawText(
            self.rect().adjusted(space, space, -space, -space),
            Qt.AlignTop | Qt.AlignHCenter,
            f"Round {p.round_index}/{p.round_total}",
        )

        # ====================================================
        # CENTER TEXT
        # ====================================================

        painter.setPen(QColor(255, 255, 255, 240))
        painter.setFont(QFont("Comic Sans", 44, QFont.Bold))

        if p.type in ("inhale", "exhale"):
            text = str(p.cycle_remaining)

        elif p.type in ("hold", "deep_inhale", "final_hold"):
            text = str(max(0, math.ceil(p.duration - self.t)))

        elif p.type == "relax_countdown":
            text = str(max(0, math.ceil(p.duration - self.t)))
        elif p.type == "prepare":
            text = str(max(1, math.ceil(p.duration - self.t)))
        else:
            text = ""

        painter.drawText(self.rect(), Qt.AlignCenter, text)

        # ====================================================
        # LABEL
        # ====================================================

        # label_alpha = 230

        # if p.type == "relax_countdown":
        #     fade = 1.0 - min(self.t / p.duration, 1.0)
        #     label_alpha = int(230 * fade)

        painter.setFont(QFont("Arial", 32, QFont.Bold))

        painter.drawText(
            QRectF(0, self.height() * 0.15, self.width(), 100), Qt.AlignHCenter, p.label
        )

        # ====================================================
        # ESC HINT
        # ====================================================

        painter.setFont(QFont("Sans-serif", 16, QFont.Medium))
        painter.setPen(QColor(0x0C, 0x14, 0x55, 200))

        mute_text = "M to mute" if not self.muted else "M to unmute"

        painter.drawText(
            self.rect().adjusted(space, space, -space, -space),
            Qt.AlignTop | Qt.AlignLeft,
            f"Q or Esc to exit\nSpace to pause\n{mute_text}",
        )

        # ====================================================
        # RING ONLY FOR BREATHING
        # ====================================================

        if p.type == "prepare":
            self.draw_prepare_ring(painter, cx, cy)

        elif p.type == "relax_countdown":
            self.draw_relax_ring(painter, cx, cy)

        else:
            self.draw_ring(painter, cx, cy)

        if self.paused:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 220))

            painter.setPen(QColor(255, 255, 255))

            painter.setFont(QFont("Arial", 44, QFont.Bold))

            painter.drawText(self.rect(), Qt.AlignCenter, "Press Space to continue")

        elif self.completed:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 235))

            painter.setPen(QColor(255, 255, 255))

            painter.setFont(QFont("Arial", 56, QFont.Bold))

            painter.drawText(self.rect(), Qt.AlignCenter, "Completed")

            painter.setFont(QFont("Arial", 22))

            painter.drawText(
                self.rect().adjusted(0, 140, 0, 0),
                Qt.AlignCenter,
                "Press Space to restart",
            )

        painter.end()

    # --------------------------------------------------------

    def draw_ring(self, painter, cx, cy):
        r = self.radius

        # glow
        for i in range(4):
            pen = QPen(QColor(80, 200, 255, 20 - i * 4))
            pen.setWidth(18 - i * 3)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)

            painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # main ring
        pen = QPen(QColor(120, 220, 255, 140))
        pen.setWidth(7)
        pen.setCapStyle(Qt.RoundCap)

        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

    # --------------------------------------------------------

    def draw_relax_ring(self, painter, cx, cy):
        r = self.radius

        progress = min(self.t / self.phase.duration, 1.0)

        remaining = 1.0 - progress

        # ====================================================
        # subtle fading background ring
        # ====================================================

        bg_alpha = int(40 * remaining)

        bg_pen = QPen(QColor(255, 255, 255, bg_alpha))
        bg_pen.setWidth(6)

        painter.setPen(bg_pen)
        painter.setBrush(Qt.NoBrush)

        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # ====================================================
        # animated disappearing arc
        # ====================================================

        glow_alpha = int(120 * remaining)

        for i in range(3):
            pen = QPen(QColor(80, 200, 255, glow_alpha // (i + 2)))
            pen.setWidth(max(1, 14 - i * 4))

            painter.setPen(pen)

            start_angle = 90 * 16
            span_angle = -(360 * remaining) * 16

            painter.drawArc(
                QRectF(cx - r, cy - r, r * 2, r * 2),
                start_angle,
                int(span_angle),
            )

        # ====================================================
        # main arc
        # ====================================================

        main_alpha = int(220 * remaining)

        pen = QPen(QColor(120, 220, 255, main_alpha))
        pen.setWidth(max(2, int(8 * remaining)))
        pen.setCapStyle(Qt.RoundCap)

        painter.setPen(pen)

        painter.drawArc(
            QRectF(cx - r, cy - r, r * 2, r * 2),
            90 * 16,
            int(-(360 * remaining) * 16),
        )

    # --------------------------------------------------------

    def draw_prepare_ring(self, painter, cx, cy):
        progress = min(self.t / self.phase.duration, 1.0)

        # ====================================================
        # smooth radius shrink
        # ====================================================

        # start_r = self.MAX_R * 0.9
        # end_r = self.MIN_R

        # r = start_r - (start_r - end_r) * progress
        r = self.radius

        # ====================================================
        # fade-in alpha
        # ====================================================

        alpha = int(220 * progress)

        # ====================================================
        # background ring
        # ====================================================

        bg_pen = QPen(QColor(255, 255, 255, int(40 * progress)))
        bg_pen.setWidth(8)

        painter.setPen(bg_pen)
        painter.setBrush(Qt.NoBrush)

        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # ====================================================
        # animated arc
        # ====================================================

        arc_pen = QPen(QColor(120, 220, 255, alpha))
        arc_pen.setWidth(8)
        arc_pen.setCapStyle(Qt.RoundCap)

        painter.setPen(arc_pen)

        start_angle = 90 * 16
        span_angle = -(360 * progress) * 16

        painter.drawArc(
            QRectF(cx - r, cy - r, r * 2, r * 2),
            start_angle,
            int(span_angle),
        )

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
        # background bar
        # ====================================================

        painter.setPen(Qt.NoPen)

        painter.setBrush(QColor(255, 255, 255, 28))

        painter.drawRoundedRect(rect, radius, radius)

        # ====================================================
        # progress fill
        # ====================================================

        painter.setBrush(QColor(120, 220, 255, 90))

        painter.drawRoundedRect(fill_rect, radius, radius)

        # ====================================================
        # subtle glow
        # ====================================================

        glow_pen = QPen(QColor(120, 220, 255, 40))
        glow_pen.setWidth(10)

        painter.setPen(glow_pen)
        painter.setBrush(Qt.NoBrush)

        painter.drawRoundedRect(fill_rect, radius, radius)

        # ====================================================
        # round markers only
        # ====================================================

        round_positions = {}

        for i, ph in enumerate(self.phases):
            if ph.round_index not in round_positions:
                round_positions[ph.round_index] = i

        total = len(self.phases)

        for _, idx in round_positions.items():
            marker_progress = idx / max(1, total - 1)

            mx = x + w * marker_progress

            active = progress >= marker_progress

            if active:
                color = QColor(220, 240, 255, 180)
                size = 10
            else:
                color = QColor(255, 255, 255, 70)
                size = 8

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

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key = QKeyEvent(event)

            if key.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
                QApplication.quit()
                return True

            elif key.key() == Qt.Key.Key_M:
                self.muted = not self.muted

                if self.muted and not self.paused and not self.completed:
                    self.player.pause()
                else:
                    if not (self.paused or self.completed or self.muted):
                        self.player.play()

                return True

            elif key.key() == Qt.Key.Key_Space:
                # ====================================================
                # completed session restart
                # ====================================================

                if self.completed:
                    self.completed = False

                    self.index = 0
                    self.t = 0.0

                    self.timer.reset()
                    if not self.muted:
                        self.player.play()

                elif not self.paused:
                    self.paused = True

                    self.timer.pause()
                    if not self.muted:
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
    app = QApplication(sys.argv)

    icon_path = files("wimhof") / "assets" / "app_icon.png"
    app.setWindowIcon(QIcon(str(icon_path)))

    config_path = files("wimhof") / "config.yaml"
    w = BreathingWidget(str(config_path))

    app.installEventFilter(w)

    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
