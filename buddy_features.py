import time
from pynput import keyboard
from PyQt6.QtCore import QObject, pyqtSignal

class SystemActivityTracker(QObject):
    """
    Background listener that intercepts system-wide typing actions 
    to switch the desktop buddy's animations and track active idle times.
    """
    typing_detected = pyqtSignal()

    def __init__(self, idle_timeout=600):
        super().__init__()
        self.idle_timeout = idle_timeout
        self.last_activity_time = time.time()
        self.is_hustling = False
        self.last_keypress_time = 0
        
        # Start OS-level keyboard hook thread
        self.listener = keyboard.Listener(on_press=self._on_key_press)
        self.listener.daemon = True
        self.listener.start()


    def _on_key_press(self, key):
        now = time.time()
        self.last_activity_time = now
        self.typing_detected.emit()
        
        # If keys are pressed rapidly within 1.5 seconds of each other, activate 'Hustle'
        if now - self.last_keypress_time < 1.5:
            self.is_hustling = True
        self.last_keypress_time = now

    def evaluate_states(self, current_state):
        """Processes time differentials to compute current behavioral context."""
        now = time.time()
        
        # Cool down hustle if typing slows down for more than 3 seconds
        if self.is_hustling and (now - self.last_keypress_time > 3.0):
            self.is_hustling = False
            if current_state == "HUSTLING":
                return "HAPPY"

        # If system sits idle for the threshold, force sleep state
        if current_state in ["HAPPY", "HUSTLING"] and (now - self.last_activity_time >= self.idle_timeout):
            return "SLEEPING"
            
        if current_state == "SLEEPING" and (now - self.last_activity_time < self.idle_timeout):
            return "HAPPY"
            
        if self.is_hustling and current_state == "HAPPY":
            return "HUSTLING"
            
        return current_state

    def reset_activity(self):
        """Manually forces wake mechanics on physical click overlays."""
        self.last_activity_time = time.time()
        self.is_hustling = False
