# main.py
#
# Wim Hof breathing trainer (PySide6)
#
# Features:
# - Expanding/shrinking breathing circle
# - Breath counter
# - Pause timer
# - Background image
# - Looping background music
# - Schedule loaded from YAML
#
# Install:
#   pip install PySide6 pyyaml
#
# Run:
#   python main.py
#
# Files:
#   config.yaml
#   assets/background.jpg
#   assets/music.mp3

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPixmap,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QApplication, QWidget

# ============================================================
# CONFIG
# ============================================================


@dataclass
class Phase:
    type: str
    duration: float
    label: str


@dataclass
class Config:
    background_image: str
    background_music: str
    phases: list[Phase]


def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    phases = [
        Phase(
            type=item["type"],
            duration=float(item["duration"]),
            label=item["label"],
        )
        for item in data["schedule"]
    ]

    return Config(
        background_image=data["background_image"],
        background_music=data["background_music"],
        phases=phases,
    )


# ============================================================
# GUI
# ============================================================


class BreathingWidget(QWidget):
    MIN_RADIUS = 80
    MAX_RADIUS = 260

    def __init__(self, config: Config):
        super().__init__()

        self.config = config

        self.setWindowTitle("Wim Hof Breathing")
        self.setMinimumSize(1000, 700)

        self.phase_index = 0
        self.phase_elapsed = 0.0

        self.breath_counter = 0

        self.current_radius = self.MIN_RADIUS

        self.background = QPixmap(config.background_image)

        # 60 FPS timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)

        # media player
        self.audio_output = QAudioOutput()
        self.player = QMediaPlayer()

        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.4)

        music_path = Path(config.background_music).absolute()
        self.player.setSource(f"file://{music_path}")
        self.player.mediaStatusChanged.connect(self.loop_music)

        self.player.play()

    # --------------------------------------------------------

    @property
    def phase(self) -> Phase:
        return self.config.phases[self.phase_index]

    # --------------------------------------------------------

    def loop_music(self, status):
        # Loop forever
        if status == QMediaPlayer.EndOfMedia:
            self.player.setPosition(0)
            self.player.play()

    # --------------------------------------------------------

    def next_phase(self):
        prev = self.phase

        if prev.type == "exhale":
            self.breath_counter += 1

        self.phase_index += 1

        if self.phase_index >= len(self.config.phases):
            self.phase_index = 0

        self.phase_elapsed = 0.0

    # --------------------------------------------------------

    def update_animation(self):
        dt = 0.016
        self.phase_elapsed += dt

        phase = self.phase

        progress = min(self.phase_elapsed / phase.duration, 1.0)

        if phase.type == "inhale":
            self.current_radius = (
                self.MIN_RADIUS + (self.MAX_RADIUS - self.MIN_RADIUS) * progress
            )

        elif phase.type == "exhale":
            self.current_radius = (
                self.MAX_RADIUS - (self.MAX_RADIUS - self.MIN_RADIUS) * progress
            )

        elif phase.type == "pause":
            self.current_radius = self.MIN_RADIUS

        if self.phase_elapsed >= phase.duration:
            self.next_phase()

        self.update()

    # --------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(QPainter.Antialiasing)

        # background
        if not self.background.isNull():
            painter.drawPixmap(self.rect(), self.background)

        # dark overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))

        center_x = self.width() / 2
        center_y = self.height() / 2

        # breathing circle
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(80, 200, 255, 180))

        r = self.current_radius

        painter.drawEllipse(
            QRectF(
                center_x - r,
                center_y - r,
                r * 2,
                r * 2,
            )
        )

        # center text
        painter.setPen(QColor("white"))

        counter_font = QFont("Arial", 48, QFont.Bold)
        painter.setFont(counter_font)

        phase = self.phase

        if phase.type == "pause":
            remaining = max(
                0,
                math.ceil(phase.duration - self.phase_elapsed),
            )
            text = str(remaining)
        else:
            text = str(self.breath_counter)

        painter.drawText(
            self.rect(),
            Qt.AlignCenter,
            text,
        )

        # bottom label
        label_font = QFont("Arial", 30)
        painter.setFont(label_font)

        painter.drawText(
            QRectF(
                0,
                self.height() - 120,
                self.width(),
                60,
            ),
            Qt.AlignCenter,
            phase.label,
        )


# ============================================================
# MAIN
# ============================================================


def main():
    app = QApplication(sys.argv)

    config = load_config("config.yaml")

    window = BreathingWidget(config)
    window.showFullScreen()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
