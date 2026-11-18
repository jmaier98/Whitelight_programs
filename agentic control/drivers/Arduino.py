"""
Arduino board (COM3, 9600 baud) running the beam-path hardware:

  motor A  : vertical steps        'motorA<n>' / 'releaseA'
  motor B  : horizontal steps      'motorB<n>' / 'releaseB'
  shutter  : 'openShutter' / 'closeShutter'
  pellicle : 'insertPelical' / 'removePelical'   (spelling is the firmware's)
  beam splitter servo : 'bsopen' (insert) / 'bsclose' (remove)
  LED      : 'led<0-255>'

Commands are sent synchronously and the firmware's one-line reply returned.
"""
from __future__ import annotations

import threading
import time

import serial

COMMANDS = {
    "open_shutter":    "openShutter",
    "close_shutter":   "closeShutter",
    "insert_pellicle": "insertPelical",
    "remove_pellicle": "removePelical",
    "insert_bs":       "bsopen",
    "remove_bs":       "bsclose",
    "release_a":       "releaseA",
    "release_b":       "releaseB",
}

# State keys updated by each named command
_STATE_EFFECTS = {
    "open_shutter":    ("arduino_shutter_open", True),
    "close_shutter":   ("arduino_shutter_open", False),
    "insert_pellicle": ("pellicle_inserted", True),
    "remove_pellicle": ("pellicle_inserted", False),
    "insert_bs":       ("beamsplitter_inserted", True),
    "remove_bs":       ("beamsplitter_inserted", False),
}


class Arduino:
    def __init__(self, state, port: str = "COM3", baud: int = 9600):
        self.state = state
        self._lock = threading.Lock()
        self.ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2)   # the board resets when the port opens

    def _send(self, command: str) -> str:
        with self._lock:
            self.ser.write((command + "\n").encode("utf-8"))
            return self.ser.readline().decode("utf-8", errors="replace").strip()

    def command(self, name: str) -> str:
        if name not in COMMANDS:
            raise ValueError(f"Unknown Arduino command '{name}'. Options: {list(COMMANDS)}")
        reply = self._send(COMMANDS[name])
        if name in _STATE_EFFECTS:
            key, val = _STATE_EFFECTS[name]
            self.state.settings[key] = val
        return reply

    def move_motor(self, motor: str, steps: int) -> str:
        motor = motor.upper()
        if motor not in ("A", "B"):
            raise ValueError("motor must be 'A' (vertical) or 'B' (horizontal)")
        steps = int(steps)
        reply = self._send(f"motor{motor}{steps}")
        key = f"motor_{motor.lower()}_net_steps"
        self.state.settings[key] = int(self.state.settings.get(key, 0)) + steps
        return reply

    def set_led(self, brightness: int) -> str:
        b = int(brightness)
        if not 0 <= b <= 255:
            raise ValueError("LED brightness must be 0-255")
        reply = self._send(f"led{b}")
        self.state.settings["led_brightness"] = b
        return reply

    def close(self):
        if self.ser.is_open:
            self.ser.close()
