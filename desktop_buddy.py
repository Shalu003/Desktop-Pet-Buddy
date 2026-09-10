import sys
import os
import time
import random
import json

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPoint,
    QRectF,
    QObject,
    pyqtSignal,
    QEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QFileDialog,
    QInputDialog,
)
from PyQt6.QtGui import (
    QPixmap,
    QPainter,
    QColor,
    QBrush,
    QCursor,
    QFont,
)


class SystemActivityTracker(QObject):
    """
    Lightweight activity tracker.

    Tracks:
    - Mouse movement across the desktop
    - Keyboard and mouse activity received by this application
    - Short bursts of activity for HUSTLING mode
    - Inactivity for SLEEPING mode

    This does not install a global keyboard hook.
    """

    typing_detected = pyqtSignal()
    activity_detected = pyqtSignal()

    def __init__(self, idle_timeout=600, parent=None):
        super().__init__(parent)
        self.speed = 0
        self.idle_timeout = idle_timeout
        self.last_activity_time = time.time()
        self.last_cursor_position = QCursor.pos()

        self.activity_timestamps = []
        self.hustle_window = 8
        self.hustle_threshold = 12

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_desktop_activity)
        self.poll_timer.start(500)

        # Track how long the buddy should move when speaking
        self.movement_timeout_timer = QTimer(self)
        self.movement_timeout_timer.setSingleShot(True)
        self.movement_timeout_timer.timeout.connect(parent.stop_text_movement)


        app = QApplication.instance()

        if app is not None:
            app.installEventFilter(self)

    def record_activity(self, typing=False):
        current_time = time.time()
        self.last_activity_time = current_time
        self.activity_timestamps.append(current_time)

        cutoff = current_time - self.hustle_window
        self.activity_timestamps = [
            timestamp
            for timestamp in self.activity_timestamps
            if timestamp >= cutoff
        ]

        if typing:
            self.typing_detected.emit()

        self.activity_detected.emit()

    def poll_desktop_activity(self):
        current_position = QCursor.pos()

        if current_position != self.last_cursor_position:
            self.last_cursor_position = current_position
            self.record_activity()

    def eventFilter(self, watched, event):
        event_type = event.type()

        if event_type in (
            QEvent.Type.KeyPress,
            QEvent.Type.KeyRelease,
        ):
            self.record_activity(typing=True)

        elif event_type in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonDblClick,
            QEvent.Type.Wheel,
            QEvent.Type.TouchBegin,
            QEvent.Type.TouchUpdate,
        ):
            self.record_activity()

        return super().eventFilter(watched, event)

    def seconds_idle(self):
        return time.time() - self.last_activity_time

    def is_hustling(self):
        current_time = time.time()
        cutoff = current_time - self.hustle_window

        self.activity_timestamps = [
            timestamp
            for timestamp in self.activity_timestamps
            if timestamp >= cutoff
        ]

        return len(self.activity_timestamps) >= self.hustle_threshold

    def evaluate_state(self, current_state):
        idle_seconds = self.seconds_idle()

        if idle_seconds >= self.idle_timeout:
            return "SLEEPING"

        if current_state in ("THIRSTY", "DEHYDRATED"):
            return current_state

        if self.is_hustling():
            return "HUSTLING"

        return "HAPPY"

def stop_text_movement(self):
    """Brings the buddy to a complete halt once the text cycle finishes."""
    if self.state in ["HAPPY", "HUSTLING"]:
        self.speed = 0
        self.update()


class UltimateFeatureBuddy(QWidget):

    def __init__(self):
        super().__init__()

        # 1. Window configuration
        self.setWindowTitle("Ultimate Feature Buddy")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.width_size = 200
        self.height_size = 180
        self.resize(self.width_size, self.height_size)

        # Allow the widget to receive keyboard focus after clicking it.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 2. Runtime settings
        user_minutes, ok = QInputDialog.getInt(
            None,
            "Buddy Settings",
            "Minutes between water breaks "
            "(Type 0 for 5-second Test Mode):",
            60,
            0,
            240,
        )

        if ok and user_minutes == 0:
            self.water_interval = 5
            self.grace_period = 5
            self.note_interval = 4
            self.idle_timeout = 8

            print(
                "Developer Mode active. "
                "Fast transitions are enabled."
            )
        else:
            selected_minutes = user_minutes if ok else 60

            self.water_interval = selected_minutes * 60
            self.grace_period = 15
            self.note_interval = 300
            self.idle_timeout = 600

        # 3. Initial state
        self.state = "HAPPY"
        self.previous_active_state = "HAPPY"

        self.speed = 2
        self.direction = 1

        current_time = time.time()

        self.last_drink = current_time
        self.last_note_time = current_time
        self.thirsty_since = 0

        self.is_dragging = False
        self.drag_position = QPoint()

        self.state_message_visible = False

        # 4. Activity tracker
        self.tracker = SystemActivityTracker(
            idle_timeout=self.idle_timeout,
            parent=self,
        )

        self.tracker.typing_detected.connect(self.update)
        self.tracker.activity_detected.connect(
            self.handle_activity_detected
        )

        # 5. Optional avatar selection
        selected_file, _ = QFileDialog.getOpenFileName(
            None,
            "Upload Custom Image "
            "(or Cancel for Default Slime)",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )

        self.avatar_pixmap = None

        if selected_file and os.path.exists(selected_file):
            raw_pixmap = QPixmap(selected_file)

            if not raw_pixmap.isNull():
                self.avatar_pixmap = raw_pixmap.scaled(
                    110,
                    100,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            else:
                print(
                    "The selected image could not be loaded. "
                    "Using the default buddy."
                )

        # 6. Manifest notes
        self.manifest_notes = []
        self.load_manifest_notes()

        # 7. Garden progress
        self.water_points = 0
        self.load_user_progress()

        # 8. Speech bubble
        self.bubble = QLabel(self)
        self.bubble.setGeometry(5, 5, 190, 48)
        self.bubble.setWordWrap(True)
        self.bubble.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.bubble.setStyleSheet(
            """
            QLabel {
                background-color: white;
                border: 2px solid #2C3E50;
                border-radius: 6px;
                font-weight: bold;
                font-family: Arial;
                font-size: 10px;
                color: #2C3E50;
                padding: 3px;
            }
            """
        )

        self.bubble.hide()

        # Small state label
        self.status_label = QLabel(self)
        self.status_label.setGeometry(30, 158, 110, 18)
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.status_label.setStyleSheet(
            """
            QLabel {
                color: white;
                background-color: rgba(44, 62, 80, 175);
                border-radius: 5px;
                font-size: 9px;
                font-weight: bold;
                padding: 1px;
            }
            """
        )
        self.status_label.setText("Happy")

        # Garden points label
        self.points_label = QLabel(self)
        self.points_label.setGeometry(140, 150, 55, 20)
        self.points_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.points_label.setStyleSheet(
            """
            QLabel {
                color: #1E8449;
                background-color: rgba(255, 255, 255, 210);
                border-radius: 5px;
                font-size: 9px;
                font-weight: bold;
            }
            """
        )
        self.update_points_label()

        # 9. Position buddy on primary screen
        screen = QApplication.primaryScreen()

        if screen is not None:
            screen_geometry = screen.availableGeometry()

            minimum_x = screen_geometry.x()
            maximum_x = (
                screen_geometry.x()
                + screen_geometry.width()
                - self.width_size
            )

            self.x_pos = random.randint(
                minimum_x,
                max(minimum_x, maximum_x),
            )

            self.y_pos = (
                screen_geometry.y()
                + screen_geometry.height()
                - self.height_size
            )
        else:
            self.x_pos = 0
            self.y_pos = 0

        self.move(
            int(self.x_pos),
            int(self.y_pos),
        )

        # 10. Timers
        self.physics_timer = QTimer(self)
        self.physics_timer.timeout.connect(
            self.update_physics_loop
        )
        self.physics_timer.start(45)

        self.lifecycle_timer = QTimer(self)
        self.lifecycle_timer.timeout.connect(
            self.monitor_lifecycle
        )
        self.lifecycle_timer.start(1000)

        self.show_temporary_message(
            "👋 Buddy is ready! "
            "Left-click to drag, click when thirsty, "
            "and right-double-click to quit.",
            5000,
        )

    def load_manifest_notes(self):
        file_name = "manifest.txt"

        if os.path.exists(file_name):
            try:
                with open(
                    file_name,
                    "r",
                    encoding="utf-8",
                ) as file:
                    self.manifest_notes = [
                        line.strip()
                        for line in file
                        if line.strip()
                    ]

                print(
                    f"Loaded {len(self.manifest_notes)} "
                    "custom message templates."
                )

            except (OSError, UnicodeError) as error:
                print(
                    f"Error loading manifest notes: {error}"
                )

        if not self.manifest_notes:
            self.manifest_notes = [
                "Relax your shoulders and breathe! 🧘",
                "You are crushing this coding session! 🚀",
                "Look away and rest your eyes for 20 seconds! 👀",
                "Hydration fuels major brainpower! 💡",
                "Check your posture before the next bug checks you! 💻",
                "Small progress is still progress! 🌱",
            ]

    def load_user_progress(self):
        file_name = "buddy_progress.json"

        if not os.path.exists(file_name):
            return

        try:
            with open(
                file_name,
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            loaded_points = data.get("water_points", 0)

            if isinstance(loaded_points, int):
                self.water_points = max(0, loaded_points)
            else:
                self.water_points = 0

            print(
                "Loaded progress. Current garden points: "
                f"{self.water_points}"
            )

        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as error:
            print(
                f"Error reading progress file: {error}"
            )

    def save_user_progress(self):
        file_name = "buddy_progress.json"

        try:
            with open(
                file_name,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    {
                        "water_points": self.water_points,
                        "last_saved": time.time(),
                    },
                    file,
                    indent=4,
                )

        except OSError as error:
            print(
                f"Failed to save progress: {error}"
            )

    def update_points_label(self):
        if hasattr(self, "points_label"):
            self.points_label.setText(
                f"🌱 {self.water_points}"
            )

    def show_temporary_message(
        self,
        message,
        duration=4000,
        allowed_states=None,
    ):
        self.bubble.setText(message)
        self.bubble.show()

        expected_message = message

        def hide_message():
            if self.bubble.text() != expected_message:
                return

            if (
                allowed_states is None
                or self.state in allowed_states
            ):
                self.bubble.hide()

        QTimer.singleShot(
            duration,
            hide_message,
        )

    def trigger_random_note(self):
        """Picks a random reminder from your notes array, activates crawl speed, and fires the stop timer."""
        # Safeguard state check
        if self.state not in ["HAPPY", "HUSTLING"]:
            return

        if hasattr(self, 'manifest_notes') and self.manifest_notes:
            random_quote = random.choice(self.manifest_notes)
            self.bubble.setText(random_quote)
            self.bubble.show()
            
            # Wake the buddy up to crawl/roll while talking
            self.speed = 2 
            self.update()

            # Tell the tracker's countdown timer to stop movement after 4 seconds
            if hasattr(self, 'tracker') and hasattr(self.tracker, 'movement_timeout_timer'):
                self.tracker.movement_timeout_timer.start(4000)



        def trigger_random_note(self):
            if self.state != "HAPPY":
                return

        random_quote = random.choice(self.manifest_notes)
        self.bubble.setText(random_quote)
        self.bubble.show()
        
        # Start crawling/rolling when showing text
        self.speed = 2 

        # Keep moving for 4 seconds, then hide the text and stop moving
        QTimer.singleShot(
            4000,
            lambda: (
                self.bubble.hide()
                if self.state in ["HAPPY", "HUSTLING"]
                else None
            ),
        )
           
        self.tracker.movement_timeout_timer.start(4000)


    def stop_text_movement(self):
        """Brings the buddy to a complete halt once the text cycle finishes."""
        if self.state in ["HAPPY", "HUSTLING"]:
            self.speed = 0
            self.update()


    def set_state(self, new_state):
        if self.state == new_state:
            return

        old_state = self.state
        self.state = new_state

        if new_state in ("HAPPY", "HUSTLING"):
            self.previous_active_state = new_state

        if new_state == "HAPPY":
            self.speed = 2
            self.status_label.setText("Happy")

            if old_state in ("SLEEPING", "HUSTLING"):
                self.show_temporary_message(
                    "😊 Back to a steady rhythm!",
                    2500,
                    allowed_states=("HAPPY",),
                )

        elif new_state == "HUSTLING":
            self.speed = 4
            self.status_label.setText("Hustling")

            self.show_temporary_message(
                "💻 Working hard together! "
                "Let's match this hustle! 🔥",
                3000,
                allowed_states=("HUSTLING",),
            )

        elif new_state == "THIRSTY":
            self.speed = 1
            self.thirsty_since = time.time()
            self.status_label.setText("Thirsty")

            self.bubble.setText(
                "💧 I'm thirsty! Drink some water, "
                "then click your buddy."
            )
            self.bubble.show()

        elif new_state == "DEHYDRATED":
            self.speed = 0
            self.status_label.setText("Dehydrated")

            self.bubble.setText(
                "💀 Dehydrated! Drink water and "
                "click your buddy to recover."
            )
            self.bubble.show()

        elif new_state == "SLEEPING":
            self.speed = 0
            self.status_label.setText("Sleeping")

            self.bubble.setText(
                "💤 Your buddy fell asleep. "
                "Click to wake it up!"
            )
            self.bubble.show()

        self.update()

    def handle_activity_detected(self):
        if self.state == "SLEEPING":
            # Activity alone does not wake the buddy.
            # The user must click the buddy intentionally.
            self.update()

    def paintEvent(self, event):
        del event

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        current_time = time.time()

        if self.state == "SLEEPING":
            pulse = (
                abs(
                    int(current_time * 2) % 4 - 2
                )
                * 1.5
            )
        elif self.state == "HUSTLING":
            pulse = (
                abs(
                    int(current_time * 8) % 4 - 2
                )
                * 2.5
            )
        else:
            pulse = (
                abs(
                    int(current_time * 4) % 4 - 2
                )
                * 2
            )

        body_rect = QRectF(
            30,
            55 + pulse,
            110,
            100,
        )

        if self.avatar_pixmap is not None:
            avatar_x = 30
            avatar_y = int(55 + pulse)

            painter.drawPixmap(
                avatar_x,
                avatar_y,
                self.avatar_pixmap,
            )

            overlay_rect = QRectF(
                avatar_x,
                avatar_y,
                self.avatar_pixmap.width(),
                self.avatar_pixmap.height(),
            )

            if self.state == "THIRSTY":
                alpha = (
                    90
                    if int(current_time * 2) % 2 == 0
                    else 40
                )

                painter.fillRect(
                    overlay_rect,
                    QColor(230, 126, 34, alpha),
                )

            elif self.state == "DEHYDRATED":
                painter.fillRect(
                    overlay_rect,
                    QColor(44, 62, 80, 180),
                )

            elif self.state == "SLEEPING":
                painter.fillRect(
                    overlay_rect,
                    QColor(155, 89, 182, 80),
                )

            elif self.state == "HUSTLING":
                painter.fillRect(
                    overlay_rect,
                    QColor(46, 204, 113, 55),
                )

        else:
            self.draw_default_buddy(
                painter,
                body_rect,
                current_time,
            )

        self.draw_buddy_face(
            painter,
            body_rect,
        )

        self.draw_garden(
            painter,
            plant_x=165,
            plant_y=145,
        )

        if self.state == "SLEEPING":
            self.draw_sleep_symbols(painter)

        elif self.state == "HUSTLING":
            self.draw_hustle_symbols(painter)

    def draw_default_buddy(
        self,
        painter,
        body_rect,
        current_time,
    ):
        painter.setPen(Qt.PenStyle.NoPen)

        if self.state == "HAPPY":
            painter.setBrush(
                QBrush(QColor("#3498DB"))
            )
            painter.drawEllipse(body_rect)

        elif self.state == "HUSTLING":
            hustle_color = (
                "#2ECC71"
                if int(current_time * 4) % 2 == 0
                else "#16A085"
            )

            painter.setBrush(
                QBrush(QColor(hustle_color))
            )
            painter.drawEllipse(body_rect)

        elif self.state == "THIRSTY":
            flash_color = (
                "#F1C40F"
                if int(current_time * 2) % 2 == 0
                else "#E67E22"
            )

            painter.setBrush(
                QBrush(QColor(flash_color))
            )
            painter.drawEllipse(body_rect)

        elif self.state == "DEHYDRATED":
            painter.setBrush(
                QBrush(QColor("#7F8C8D"))
            )

            painter.drawEllipse(
                QRectF(20, 125, 130, 30)
            )

        elif self.state == "SLEEPING":
            painter.setBrush(
                QBrush(QColor("#9B59B6"))
            )
            painter.drawEllipse(body_rect)

    def draw_buddy_face(self, painter, body_rect):
        if self.avatar_pixmap is not None:
            return

        if self.state == "DEHYDRATED":
            return

        center_x = body_rect.center().x()
        center_y = body_rect.center().y()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#FFFFFF")))

        left_eye = QRectF(
            center_x - 25,
            center_y - 14,
            12,
            16,
        )

        right_eye = QRectF(
            center_x + 13,
            center_y - 14,
            12,
            16,
        )

        if self.state == "SLEEPING":
            painter.setPen(QColor("#2C3E50"))
            painter.drawLine(
                int(left_eye.left()),
                int(left_eye.center().y()),
                int(left_eye.right()),
                int(left_eye.center().y()),
            )
            painter.drawLine(
                int(right_eye.left()),
                int(right_eye.center().y()),
                int(right_eye.right()),
                int(right_eye.center().y()),
            )
        else:
            painter.drawEllipse(left_eye)
            painter.drawEllipse(right_eye)

            painter.setBrush(QBrush(QColor("#2C3E50")))

            painter.drawEllipse(
                QRectF(
                    left_eye.center().x() - 2,
                    left_eye.center().y() - 2,
                    5,
                    5,
                )
            )

            painter.drawEllipse(
                QRectF(
                    right_eye.center().x() - 2,
                    right_eye.center().y() - 2,
                    5,
                    5,
                )
            )

        painter.setPen(QColor("#2C3E50"))

        if self.state in ("HAPPY", "HUSTLING"):
            painter.drawArc(
                QRectF(
                    center_x - 15,
                    center_y + 5,
                    30,
                    20,
                ),
                0,
                -180 * 16,
            )

        elif self.state == "THIRSTY":
            painter.drawEllipse(
                QRectF(
                    center_x - 6,
                    center_y + 10,
                    12,
                    8,
                )
            )

        elif self.state == "SLEEPING":
            painter.drawLine(
                int(center_x - 8),
                int(center_y + 13),
                int(center_x + 8),
                int(center_y + 13),
            )

    def draw_garden(
        self,
        painter,
        plant_x,
        plant_y,
    ):
        painter.setPen(Qt.PenStyle.NoPen)

        # Soil
        painter.setBrush(
            QBrush(QColor("#8E5A2B"))
        )
        painter.drawEllipse(
            QRectF(
                plant_x - 13,
                plant_y - 2,
                26,
                8,
            )
        )

        if self.water_points < 3:
            painter.setBrush(
                QBrush(QColor("#795548"))
            )
            painter.drawEllipse(
                QRectF(
                    plant_x - 2,
                    plant_y - 5,
                    4,
                    4,
                )
            )

        elif 3 <= self.water_points < 6:
            painter.setBrush(
                QBrush(QColor("#27AE60"))
            )
            painter.drawRect(
                plant_x - 2,
                plant_y - 12,
                4,
                12,
            )
            painter.drawEllipse(
                plant_x + 1,
                plant_y - 10,
                7,
                4,
            )

        elif 6 <= self.water_points <= 8:
            painter.setBrush(
                QBrush(QColor("#27AE60"))
            )
            painter.drawRect(
                plant_x - 2,
                plant_y - 20,
                4,
                20,
            )
            painter.drawEllipse(
                plant_x - 8,
                plant_y - 16,
                7,
                5,
            )
            painter.drawEllipse(
                plant_x + 1,
                plant_y - 11,
                7,
                5,
            )

        else:
            painter.setBrush(
                QBrush(QColor("#27AE60"))
            )
            painter.drawRect(
                plant_x - 2,
                plant_y - 25,
                4,
                25,
            )

            painter.setBrush(
                QBrush(QColor("#F1C40F"))
            )
            painter.drawEllipse(
                plant_x - 9,
                plant_y - 34,
                18,
                18,
            )

            painter.setBrush(
                QBrush(QColor("#E74C3C"))
            )
            painter.drawEllipse(
                plant_x - 3,
                plant_y - 29,
                6,
                6,
            )

    def draw_sleep_symbols(self, painter):
        painter.setPen(QColor("#5B2C6F"))
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(140, 80, "Z")
        painter.drawText(153, 66, "Z")
        painter.drawText(168, 50, "Z")

    def draw_hustle_symbols(self, painter):
        painter.setPen(QColor("#F39C12"))
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        painter.drawText(12, 90, "⚡")
        painter.drawText(145, 100, "⚡")

    def mousePressEvent(self, event):
        self.tracker.record_activity()

        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()

            self.is_dragging = True
            self.drag_position = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )

            event.accept()

            if self.state == "SLEEPING":
                self.last_drink = time.time()
                self.last_note_time = time.time()

                self.set_state("HAPPY")

                self.show_temporary_message(
                    "☀️ Good morning! Let's work!",
                    3000,
                    allowed_states=("HAPPY",),
                )

            elif self.state in (
                "THIRSTY",
                "DEHYDRATED",
            ):
                self.water_points += 1
                self.last_drink = time.time()
                self.last_note_time = time.time()
                self.thirsty_since = 0

                self.save_user_progress()
                self.update_points_label()

                self.set_state("HAPPY")

                self.show_temporary_message(
                    "✨ Hydrated! +1 Garden Point "
                    f"(Total: {self.water_points})! 🌱",
                    4000,
                    allowed_states=("HAPPY",),
                )

    def mouseMoveEvent(self, event):
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self.is_dragging
        ):
            new_position = (
                event.globalPosition().toPoint()
                - self.drag_position
            )

            self.move(new_position)

            self.x_pos = new_position.x()
            self.y_pos = new_position.y()

            self.tracker.record_activity()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False

            self.x_pos = self.pos().x()
            self.y_pos = self.pos().y()

            self.tracker.record_activity()
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.save_user_progress()
            QApplication.quit()
            event.accept()

    def closeEvent(self, event):
        self.save_user_progress()
        event.accept()

    def update_physics_loop(self):
         if not self.is_dragging and self.state not in ["DEHYDRATED", "SLEEPING"] and self.speed > 0:
            current_screen = QApplication.screenAt(self.pos())
            if not current_screen:
                current_screen = QApplication.primaryScreen()
            monitor_geo = current_screen.geometry()
            
            self.x_pos += self.speed * self.direction
            left_boundary = monitor_geo.x()
            right_boundary = monitor_geo.x() + monitor_geo.width() - self.width_size
            
            if self.x_pos >= right_boundary:
                self.x_pos = right_boundary
                self.direction = -1
            elif self.x_pos <= left_boundary:
                self.x_pos = left_boundary
                self.direction = 1
                
            self.move(self.x_pos, self.y_pos)
            self.update()

    def monitor_lifecycle(self):
        # FIXED: Define 'now' at the very beginning of the function
        now = time.time()
        
        # Compute external behavioral context from our secondary file layer
        old_state = self.state
        self.state = self.tracker.evaluate_state(self.state)
        
        if old_state != self.state:
            if self.state == "SLEEPING":
                self.bubble.setText("💤 Your buddy fell asleep... Click to wake!")
                self.bubble.show()
            elif self.state == "HUSTLING":
                self.bubble.setText("💻 Working hard together! Let's match this hustle! 🔥")
                self.bubble.show()
                QTimer.singleShot(3000, lambda: self.bubble.hide() if self.state == "HUSTLING" else None)
            self.update()

        # Handle periodic notification manifest notes
        if self.state == "HAPPY" and (now - self.last_note_time >= self.note_interval):
            if hasattr(self, 'manifest_notes') and self.manifest_notes:
                random_quote = random.choice(self.manifest_notes)
                self.show_temporary_message(random_quote) 
            self.last_note_time = now

        # Standard health framework validations
        if self.state in ["HAPPY", "HUSTLING"]:
            if now - self.last_drink >= self.water_interval:
                self.state = "THIRSTY"
                self.thirsty_since = now
                self.bubble.setText("💧 I'm thirsty! Click your buddy once you drink water!")
                self.bubble.show()
                self.update()
        elif self.state == "THIRSTY":
            if now - self.thirsty_since >= self.grace_period:
                self.state = "DEHYDRATED"
                self.speed = 0
                self.bubble.setText("💀 Dehydrated! Click your character to revive your score!")
                self.bubble.show()
                self.update()




def main():
    app = QApplication(sys.argv)

    buddy = UltimateFeatureBuddy()
    buddy.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()