from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

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
    QKeyEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QApplication, QWidget

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
        self.showFullScreen()

        self.phases = load_config(config_path)
        self.index = 0
        self.t = 0.0

        self.radius = self.MIN_R

        self.bg = QPixmap("assets/background.jpg")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

        # Music
        # keep references (IMPORTANT)
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.4)

        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)

        music_path = Path("assets/music.mp3").resolve()
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
            self.index = 0

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
            self.radius = 0

        if self.t >= p.duration:
            self.next()

        self.update()

    # --------------------------------------------------------

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # background
        if not self.bg.isNull():
            painter.drawPixmap(self.rect(), self.bg)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 140))

        p = self.phase

        cx = self.width() / 2
        cy = self.height() / 2

        # ====================================================
        # ROUND LABEL
        # ====================================================

        painter.setPen(QColor(255, 255, 255, 220))
        painter.setFont(QFont("Arial", 22, QFont.Bold))

        painter.drawText(
            self.rect(),
            Qt.AlignTop | Qt.AlignHCenter,
            f"Round {p.round_index}/{p.round_total}",
        )

        # ====================================================
        # CENTER TEXT
        # ====================================================

        painter.setPen(QColor(255, 255, 255, 240))
        painter.setFont(QFont("Arial", 44, QFont.Bold))

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

        painter.setPen(QColor(255, 255, 255, 230))
        painter.setFont(QFont("Arial", 32, QFont.Bold))

        painter.drawText(
            QRectF(0, self.height() * 0.70, self.width(), 100), Qt.AlignHCenter, p.label
        )

        # ====================================================
        # ESC HINT
        # ====================================================

        painter.setFont(QFont("Arial", 13, QFont.Medium))
        painter.setPen(QColor(230, 200, 90, 200))  # мягкий янтарный

        painter.drawText(20, self.height() - 30, "Q or Esc to exit")

        # ====================================================
        # RING ONLY FOR BREATHING
        # ====================================================

        if p.type == "prepare":
            self.draw_prepare_ring(painter, cx, cy)

        elif p.type not in ("relax_countdown",):
            self.draw_ring(painter, cx, cy)

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

    def draw_prepare_ring(self, painter, cx, cy):
        r = self.MAX_R * 0.9

        progress = min(self.t / self.phase.duration, 1.0)

        # background circle
        bg_pen = QPen(QColor(255, 255, 255, 40))
        bg_pen.setWidth(8)

        painter.setPen(bg_pen)
        painter.setBrush(Qt.NoBrush)

        painter.drawEllipse(
            QRectF(cx - r, cy - r, r * 2, r * 2)
        )

        # animated arc
        arc_pen = QPen(QColor(120, 220, 255, 220))
        arc_pen.setWidth(8)
        arc_pen.setCapStyle(Qt.RoundCap)

        painter.setPen(arc_pen)

        start_angle = 90 * 16
        span_angle = -360 * progress * 16

        painter.drawArc(
            QRectF(cx - r, cy - r, r * 2, r * 2),
            start_angle,
            span_angle,
        )

    # --------------------------------------------------------

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key = QKeyEvent(event)

            if key.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
                QApplication.quit()
                return True

        return super().eventFilter(obj, event)


# ============================================================
# MAIN
# ============================================================


def main():
    app = QApplication(sys.argv)

    w = BreathingWidget("config.yaml")
    app.installEventFilter(w)

    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
