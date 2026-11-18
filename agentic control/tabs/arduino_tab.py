# tabs/arduino_tab.py
"""
Arduino control — the old arduino_control_v2 program.

Steering motors A (vertical) and B (horizontal), the shutter, the pellicle,
the beam-splitter servo, the illumination LED, and the sample camera
(mirrored and rotated 90° like before).
"""
from __future__ import annotations

import base64
import threading

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QIntValidator
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QPushButton,
    QLineEdit, QLabel, QSlider, QMessageBox,
)

TAB_NAME = "Arduino"
CAMERA_INDEX = 0


def _open_camera():
    """Open the camera with DirectShow, as the new microscope's webcam tab does.

    OpenCV's Windows default backend (Media Foundation) takes 10-15 s to open
    this camera; DirectShow opens it in about a second.
    """
    import cv2
    return cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

ACTIONS = {
    "open_shutter": "Open shutter", "close_shutter": "Close shutter",
    "insert_pellicle": "Insert pellicle", "remove_pellicle": "Remove pellicle",
    "insert_bs": "Insert beam splitter", "remove_bs": "Remove beam splitter",
    "release_a": "Release motor A", "release_b": "Release motor B",
}


def _prepare_frame(frame):
    """Mirror, rotate 90° CCW and convert BGR→RGB, as the old program did."""
    import cv2
    frame = cv2.flip(frame, 1)
    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


class ArduinoTab(QWidget):
    status_sig = pyqtSignal(str)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.state = controller.state
        self.ard = controller.get_instrument("Arduino")
        self._cap = None
        self._cam_lock = threading.Lock()
        self._last_rgb = None

        iv = QIntValidator(-10_000_000, 10_000_000, self)

        mot = QGroupBox("Steering motors")
        mg = QGridLayout(mot)
        self.steps = {}
        for row, (m, label) in enumerate((("B", "Horizontal (motor B) steps:"),
                                          ("A", "Vertical (motor A) steps:"))):
            self.steps[m] = QLineEdit("0"); self.steps[m].setValidator(iv)
            send = QPushButton(f"Send to motor {m}")
            send.clicked.connect(lambda _, m=m: self._async(self.move_motor, m, self.steps[m].text()))
            rel = QPushButton(f"Release motor {m}")
            rel.clicked.connect(lambda _, a=f"release_{m.lower()}": self._async(self.run_action, a))
            mg.addWidget(QLabel(label), row, 0); mg.addWidget(self.steps[m], row, 1)
            mg.addWidget(send, row, 2); mg.addWidget(rel, row, 3)

        beam = QGroupBox("Beam path")
        bg = QGridLayout(beam)
        for row, pair in enumerate((("open_shutter", "close_shutter"),
                                    ("insert_pellicle", "remove_pellicle"),
                                    ("insert_bs", "remove_bs"))):
            for col, action in enumerate(pair):
                b = QPushButton(ACTIONS[action])
                b.clicked.connect(lambda _, a=action: self._async(self.run_action, a))
                bg.addWidget(b, row, col)

        led = QGroupBox("LED brightness")
        lh = QHBoxLayout(led)
        self.led = QSlider(Qt.Orientation.Horizontal); self.led.setRange(0, 255)
        self.led.setValue(int(self.state.settings.get("led_brightness") or 0))
        self.led_val = QLabel(str(self.led.value()))
        self.led.valueChanged.connect(lambda v: self.led_val.setText(str(v)))
        set_led = QPushButton("Set light")
        set_led.clicked.connect(lambda: self._async(self.set_led, self.led.value()))
        lh.addWidget(self.led, 1); lh.addWidget(self.led_val); lh.addWidget(set_led)

        self.state_lbl = QLabel(); self.state_lbl.setStyleSheet("font-family:Consolas;")
        self.status_lbl = QLabel("Arduino connected." if self.ard else "Arduino NOT connected.")
        self.status_lbl.setWordWrap(True)

        left = QVBoxLayout()
        for w in (mot, beam, led, self.state_lbl, self.status_lbl):
            left.addWidget(w)
        left.addStretch(1)

        # Camera
        right = QVBoxLayout()
        self.cam_lbl = QLabel("Camera off")
        self.cam_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_lbl.setMinimumSize(480, 480)
        self.cam_lbl.setStyleSheet("background:#222; color:#aaa;")
        self.cam_btn = QPushButton("Turn camera on")
        self.cam_btn.clicked.connect(self.toggle_camera)
        right.addWidget(self.cam_lbl, 1)
        right.addWidget(self.cam_btn)

        outer = QHBoxLayout(self)
        outer.addLayout(left, 1)
        outer.addLayout(right, 1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_frame)
        self.status_sig.connect(self._on_status, Qt.ConnectionType.QueuedConnection)
        self._refresh_state()

    # ── Hardware actions (any thread) ────────────────────────────────────────

    def _require(self):
        if self.ard is None:
            raise RuntimeError("Arduino is not connected")

    def run_action(self, action: str) -> dict:
        self._require()
        reply = self.ard.command(action)
        self.controller.log(f"Arduino: {ACTIONS.get(action, action)} (reply: {reply!r})")
        self.controller.save_state()
        self.status_sig.emit(f"{ACTIONS.get(action, action)} — reply: {reply or '(none)'}")
        return {"status": "ok", "action": action, "reply": reply}

    def move_motor(self, motor: str, steps) -> dict:
        self._require()
        reply = self.ard.move_motor(motor, int(steps))
        self.controller.log(f"Arduino: motor {motor} {int(steps)} steps (reply: {reply!r})")
        self.controller.save_state()
        self.status_sig.emit(f"Motor {motor}: {int(steps)} steps — reply: {reply or '(none)'}")
        return {"status": "ok", "motor": motor, "steps": int(steps), "reply": reply}

    def set_led(self, brightness) -> dict:
        self._require()
        reply = self.ard.set_led(int(brightness))
        self.controller.save_state()
        self.status_sig.emit(f"LED set to {int(brightness)}")
        return {"status": "ok", "led_brightness": int(brightness), "reply": reply}

    def _async(self, fn, *args):
        def run():
            try:
                fn(*args)
            except Exception as e:
                self.status_sig.emit(f"Error: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _on_status(self, msg):
        self.status_lbl.setText(msg)
        self._refresh_state()

    def _refresh_state(self):
        st = self.state.settings
        fmt = lambda v: "unknown" if v is None else str(v)
        self.state_lbl.setText(
            f"Shutter open      : {fmt(st.get('arduino_shutter_open'))}\n"
            f"Pellicle inserted : {fmt(st.get('pellicle_inserted'))}\n"
            f"Beam splitter in  : {fmt(st.get('beamsplitter_inserted'))}\n"
            f"LED brightness    : {fmt(st.get('led_brightness'))}\n"
            f"Motor A net steps : {st.get('motor_a_net_steps', 0)}\n"
            f"Motor B net steps : {st.get('motor_b_net_steps', 0)}")

    # ── Camera ───────────────────────────────────────────────────────────────

    def camera_on(self) -> bool:
        return self._timer.isActive()

    def toggle_camera(self):
        if self._timer.isActive():
            self._timer.stop()
            with self._cam_lock:
                if self._cap is not None:
                    self._cap.release()
                    self._cap = None
            self.cam_lbl.setText("Camera off")
            self.cam_btn.setText("Turn camera on")
            return
        import cv2
        with self._cam_lock:
            self._cap = _open_camera()
            ok = self._cap.isOpened()
        if not ok:
            QMessageBox.warning(self, "Camera", "Could not open the camera.")
            return
        self._timer.start(30)
        self.cam_btn.setText("Turn camera off")

    def _update_frame(self):
        with self._cam_lock:
            if self._cap is None:
                return
            ok, frame = self._cap.read()
        if not ok:
            return
        rgb = _prepare_frame(frame)
        self._last_rgb = rgb
        h, w, _ = rgb.shape
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        self.cam_lbl.setPixmap(QPixmap.fromImage(img).scaled(
            self.cam_lbl.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation))

    def capture_frame_b64(self) -> str | None:
        """One camera frame as base64 PNG (opens the camera briefly if it is off)."""
        import cv2
        rgb = None
        if self._timer.isActive() and self._last_rgb is not None:
            rgb = self._last_rgb
        else:
            with self._cam_lock:
                cap = _open_camera()
                try:
                    for _ in range(5):          # first frames are often dark
                        ok, frame = cap.read()
                finally:
                    cap.release()
            if ok:
                rgb = _prepare_frame(frame)
        if rgb is None:
            return None
        ok, buf = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        return base64.standard_b64encode(buf.tobytes()).decode() if ok else None

    # ── Agent API ────────────────────────────────────────────────────────────

    def get_settings(self) -> dict:
        st = self.state.settings
        return {
            "arduino_connected": self.ard is not None,
            "actions_available": list(ACTIONS),
            "shutter_open": st.get("arduino_shutter_open"),
            "pellicle_inserted": st.get("pellicle_inserted"),
            "beamsplitter_inserted": st.get("beamsplitter_inserted"),
            "led_brightness": st.get("led_brightness"),
            "motor_a_net_steps": st.get("motor_a_net_steps"),
            "motor_b_net_steps": st.get("motor_b_net_steps"),
            "camera_on": self.camera_on(),
            "note": "State is what this program last commanded; the Arduino does not report it back.",
        }

    def closeEvent(self, event):
        self._timer.stop()
        with self._cam_lock:
            if self._cap is not None:
                self._cap.release()
        event.accept()
