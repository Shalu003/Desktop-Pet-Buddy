import sys
import os
import time
import random
from PyQt6.QtCore import Qt, QTimer, QPoint, QRectF
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QFileDialog, QInputDialog
from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush

class UltimateProductionBuddy(QWidget):
    def __init__(self):
        super().__init__()
        
        # 1. WINDOW INTERFACE CONFIGURATIONS
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.width_size, self.height_size = 180, 160
        self.resize(self.width_size, self.height_size)

        # 2. CONFIGURATION PROMPTS
        # TIP: Type 0 here to unlock the 5-second ultra test mode!
        user_minutes, ok = QInputDialog.getInt(
            None, "Buddy Settings", 
            "Minutes between breaks (Type 0 for 5-second Test Mode):", 
            60, 0, 240
        )
        
        # If user types 0, drop interval to 5 seconds. Otherwise, calculate minutes to seconds.
        if ok and user_minutes == 0:
            self.water_interval = 5
            self.grace_period = 5
            print("🚀 Developer Test Mode Activated: State transitions every 5 seconds!")
        else:
            self.water_interval = (user_minutes if ok else 60) * 60
            self.grace_period = 15 # Normal 15-second grace period

        # File selection dialog
        selected_file, _ = QFileDialog.getOpenFileName(
            None, "Upload Custom Image (Or Cancel for Default Slime)", "", "Images (*.png *.jpg *.jpeg *.gif)"
        )

        # 3. CORE STATE VARIABLES
        self.state = "HAPPY"
        self.speed = 2
        self.direction = 1
        self.last_drink = time.time()
        self.thirsty_since = 0
        self.is_dragging = False
        self.drag_position = QPoint()

        # 4. IMAGE STORAGE RETRIEVAL
        self.avatar_pixmap = None
        if selected_file and os.path.exists(selected_file):
            raw_pixmap = QPixmap(selected_file)
            self.avatar_pixmap = raw_pixmap.scaled(120, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        # 5. UI CONTAINER PACKAGING
        # Text Bubble
        self.bubble = QLabel(self)
        self.bubble.setGeometry(5, 5, 170, 40)
        self.bubble.setWordWrap(True)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bubble.setStyleSheet("background-color: white; border: 2px solid #2C3E50; border-radius: 5px; font-weight: bold; font-family: Arial; font-size: 10px; color: #2C3E50;")
        self.bubble.hide()

        # Custom Drawing Canvas Component
        self.canvas_label = QLabel(self)
        self.canvas_label.setGeometry(30, 50, 120, 110)

        # Screen coordinates init
        screen = QApplication.primaryScreen()
        screen_geo = screen.geometry()
        self.x_pos = random.randint(screen_geo.x(), screen_geo.x() + screen_geo.width() - self.width_size)
        self.y_pos = screen_geo.y() + screen_geo.height() - self.height_size - 60
        self.move(self.x_pos, self.y_pos)

        # 6. APP TIMERS
        self.physics_timer = QTimer(self)
        self.physics_timer.timeout.connect(self.update_physics_loop)
        self.physics_timer.start(45) 

        self.lifecycle_timer = QTimer(self)
        self.lifecycle_timer.timeout.connect(self.monitor_lifecycle)
        self.lifecycle_timer.start(1000) 

    # --- GRAPHICS PAINTER OVERRIDE ---
    def paintEvent(self, event):
        """Hardware paint pipeline that draws our avatars and dynamic color masks cleanly."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate tiny idle breathing bounce
        pulse = abs(int(time.time() * 4) % 4 - 2) * 2
        body_rect = QRectF(30, 50 + pulse, 120, 110)

        # Case A: If user chose an image file, render it onto the screen context
        if self.avatar_pixmap:
            painter.drawPixmap(30, 50, self.avatar_pixmap)
            
            # INJECT HARDWARE MASKS OVER THE PHOTO
            if self.state == "THIRSTY":
                # Flash transparent orange color over their photo
                alpha = 80 if int(time.time() * 2) % 2 == 0 else 40
                painter.fillRect(30, 50, self.avatar_pixmap.width(), self.avatar_pixmap.height(), QColor(230, 126, 34, alpha))
            elif self.state == "DEHYDRATED":
                # Layer heavy dark gray filter when collapsed
                painter.fillRect(30, 50, self.avatar_pixmap.width(), self.avatar_pixmap.height(), QColor(44, 62, 80, 180))

        # Case B: Default Template Slime Asset
        else:
            if self.state == "HAPPY":
                painter.setBrush(QBrush(QColor("#3498DB"))) # Electric Blue
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(body_rect)
            elif self.state == "THIRSTY":
                flash_color = "#F1C40F" if int(time.time() * 2) % 2 == 0 else "#E67E22"
                painter.setBrush(QBrush(QColor(flash_color)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(body_rect)
            elif self.state == "DEHYDRATED":
                painter.setBrush(QBrush(QColor("#7F8C8D"))) # Sad Slate Gray
                painter.setPen(Qt.PenStyle.NoPen)
                # Flatten the slime circle down into a sad puddle shape
                puddle_rect = QRectF(20, 120, 140, 30)
                painter.drawEllipse(puddle_rect)

            # Draw moving eyes on our default asset
            if self.state != "DEHYDRATED":
                eye_y = 90 + pulse
                look = 35 if self.direction == 1 else 0
                painter.setBrush(QBrush(QColor("white")))
                painter.drawEllipse(50 + look, eye_y, 12, 12)
                painter.drawEllipse(70 + look, eye_y, 12, 12)
                painter.setBrush(QBrush(QColor("black")))
                painter.drawEllipse(54 + look, eye_y + 3, 5, 5)
                painter.drawEllipse(74 + look, eye_y + 3, 5, 5)

    # --- LOGGING & DRAG INTERACTIONS ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

            if self.state in ["THIRSTY", "DEHYDRATED"]:
                self.state = "HAPPY"
                self.speed = 2
                self.bubble.setText("✨ Hydrated! Thank you! 🥰")
                self.last_drink = time.time()
                self.update() # Refresh graphics layer immediately
                QTimer.singleShot(3000, lambda: self.bubble.hide() if self.state == "HAPPY" else None)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.x_pos = self.pos().x()
            self.y_pos = self.pos().y()
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            QApplication.quit()

    # --- PHYSIC CALCULATIONS ---
    def update_physics_loop(self):
        if not self.is_dragging and self.state != "DEHYDRATED":
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
        
        self.update() # Triggers paintEvent to animate breathing frame loops continuously

    def monitor_lifecycle(self):
        now = time.time()
        
        if self.state == "HAPPY":
            if now - self.last_drink >= self.water_interval:
                self.state = "THIRSTY"
                self.thirsty_since = now
                self.bubble.setText("💧 I'm thirsty! Click me once you log water!")
                self.bubble.show()
                
        elif self.state == "THIRSTY":
            if now - self.thirsty_since >= self.grace_period: 
                self.state = "DEHYDRATED"
                self.speed = 0
                self.bubble.setText("💀 Dehydrated... click to revive me!")
                self.bubble.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    buddy = UltimateProductionBuddy()
    buddy.show()
    sys.exit(app.exec())
