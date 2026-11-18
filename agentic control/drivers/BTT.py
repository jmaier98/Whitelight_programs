"""
BigTreeTech stepper board (COM4) driving the rotation mounts.

  rot 1  : X motor
  rot 2  : Y motor
  waveplate pair : rot 1 and rot 2 moved together — rot 1 at (offset + angle),
                   rot 2 at (-angle). 'offset' sets their relative zero.

Angles are degrees; the mounts move ROTATION_MOUNT degrees per mm of G-code.
Every move is recorded in the shared state.
"""
from __future__ import annotations

import threading
import time

import serial

ROTATION_MOUNT = 3.6    # degrees per mm of travel
DEFAULT_FEEDRATE = 5000


class BTT:
    def __init__(self, state, port: str = "COM4", baud: int = 115200):
        self.state = state
        self._lock = threading.Lock()
        self.d3 = serial.Serial(port, baud, timeout=1)
        time.sleep(0.5)
        self.send_gcode("M302 S0")   # allow 'cold extrusion' so E moves work
        self.send_gcode("M17 E")

    def send_gcode(self, cmd: str, wait: float = 0.05):
        with self._lock:
            self.d3.write((cmd + "\n").encode())
            time.sleep(wait)

    def rot_1(self, angle: float, feedrate: int = DEFAULT_FEEDRATE):
        self.send_gcode(f"G0 X{float(angle) / ROTATION_MOUNT:.3f} F{feedrate}")
        self.state.settings["rot_1_deg"] = float(angle)

    def rot_2(self, angle: float, feedrate: int = DEFAULT_FEEDRATE):
        self.send_gcode(f"G0 Y{float(angle) / ROTATION_MOUNT:.3f} F{feedrate}")
        self.state.settings["rot_2_deg"] = float(angle)

    def rot_1_2(self, angle_1: float, angle_2: float, feedrate: int = DEFAULT_FEEDRATE):
        self.send_gcode(f"G0 X{float(angle_1) / ROTATION_MOUNT:.3f} "
                        f"Y{float(angle_2) / ROTATION_MOUNT:.3f} F{feedrate}")
        self.state.settings["rot_1_deg"] = float(angle_1)
        self.state.settings["rot_2_deg"] = float(angle_2)

    def rot_12(self, angle: float, feedrate: int = DEFAULT_FEEDRATE, offset: float = 0.0):
        """Move the waveplate pair together (see module docstring)."""
        a1 = float(offset) + float(angle)
        a2 = -float(angle)
        self.send_gcode(f"G0 X{a1 / ROTATION_MOUNT:.3f} Y{a2 / ROTATION_MOUNT:.3f} F{feedrate}")
        st = self.state.settings
        st["waveplate_angle_deg"] = float(angle)
        st["waveplate_offset_deg"] = float(offset)
        st["rot_1_deg"] = a1
        st["rot_2_deg"] = a2

    def close(self):
        self.d3.close()
