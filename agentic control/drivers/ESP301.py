"""
Newport ESP301 motion controller (RS-232) — sample X/Y stage and delay line.

Axis layout on the white-light microscope
-----------------------------------------
  axis 1 : sample X   (user units µm:  raw = -x/175 + 6.1)
  axis 2 : sample Y   (user units µm:  raw =  y/240 + 6.1)
  axis 3 : delay line (mm, travel clamped to ±105 mm)

Delay in ps is converted with the time-zero position kept in the state file:
    delay_mm = time_zero_mm + ps * PS_TO_MM          (PS_TO_MM = -0.15)

Every move updates the shared state so the position is saved with the data.
All serial traffic is serialised with a lock because the GUI, scans and the
agent can all talk to the controller from different threads.
"""
from __future__ import annotations

import threading
import time

import serial

X_SCALE = -175.0      # µm per raw unit (sign flips the axis)
Y_SCALE = 240.0
XY_CENTER = 6.1       # raw position of the user-unit origin
DELAY_LIMIT_MM = 105.0
PS_TO_MM = -0.15      # mm of delay-stage travel per ps
FAST_VELOCITY = 0.2   # normal axis 1/2 velocity restored after an alignment cut


def x_um_to_raw(x_um: float) -> float:
    return float(x_um) / X_SCALE + XY_CENTER


def y_um_to_raw(y_um: float) -> float:
    return float(y_um) / Y_SCALE + XY_CENTER


def x_raw_to_um(raw: float) -> float:
    return (float(raw) - XY_CENTER) * X_SCALE


def y_raw_to_um(raw: float) -> float:
    return (float(raw) - XY_CENTER) * Y_SCALE


class ESP301:
    def __init__(self, state, port: str = "COM7", baudrate: int = 19200, timeout: float = 1):
        self.state = state
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)  # controller needs a moment after the port opens
        self._lock = threading.RLock()
        # The COM port can exist with the controller switched off; make sure
        # something answers before counting the stage as present.
        self.ser.reset_input_buffer()
        self.version = self.send_command("VE?")
        if not self.version:
            self.ser.close()
            raise RuntimeError(f"nothing answered on {port} (ESP301 off or on another port?)")

    # ── Low level ────────────────────────────────────────────────────────────

    def send_command(self, command: str) -> str:
        with self._lock:
            self.ser.write(f"{command}\r\n".encode())
            time.sleep(0.1)
            return self.ser.readline().decode(errors="replace").strip()

    def quick_command(self, command: str):
        with self._lock:
            self.ser.write(f"{command}\r".encode())
            time.sleep(0.01)

    def quick_read(self) -> str:
        with self._lock:
            time.sleep(0.02)
            return self.ser.readline().decode(errors="replace").strip()

    def query_position(self, axis: int) -> float:
        with self._lock:
            return float(self.send_command(f"{axis}TP"))

    def enable_motors(self):
        for axis in (1, 2, 3):
            self.send_command(f"{axis}MO")

    def move_axis(self, axis: int, target: float, tolerance: float = 0.001,
                  abort_flag=None, timeout_s: float = 120.0) -> bool:
        """Absolute move; blocks until within tolerance (or abort/timeout)."""
        self.send_command(f"{axis}PA{target}")
        t0 = time.time()
        while True:
            try:
                pos = self.query_position(axis)
                if abs(pos - target) <= tolerance:
                    return True
            except ValueError:
                pass  # garbled reply — poll again
            if abort_flag is not None and abort_flag():
                return False
            if time.time() - t0 > timeout_s:
                raise TimeoutError(f"ESP axis {axis} did not reach {target}")
            time.sleep(0.05)

    # ── Sample X / Y (µm) ────────────────────────────────────────────────────

    def move_x(self, x_um: float, abort_flag=None) -> bool:
        ok = self.move_axis(1, x_um_to_raw(x_um), abort_flag=abort_flag)
        self.state.settings["x_stage_um"] = float(x_um)
        return ok

    def move_y(self, y_um: float, abort_flag=None) -> bool:
        ok = self.move_axis(2, y_um_to_raw(y_um), abort_flag=abort_flag)
        self.state.settings["y_stage_um"] = float(y_um)
        return ok

    # ── Delay line ───────────────────────────────────────────────────────────

    @staticmethod
    def clamp_delay(mm: float) -> float:
        return max(-DELAY_LIMIT_MM, min(DELAY_LIMIT_MM, float(mm)))

    def ps_to_mm(self, ps: float) -> float:
        t0 = float(self.state.settings.get("time_zero_pos_mm", -57.2))
        return self.clamp_delay(t0 + float(ps) * PS_TO_MM)

    def move_delay_mm(self, mm: float, wait: bool = True, abort_flag=None) -> float:
        mm = self.clamp_delay(mm)
        if wait:
            self.move_axis(3, mm, abort_flag=abort_flag)
        else:
            # Fire-and-forget, as the original 'Delay time (ps)' scan axis did:
            # the per-point wait time covers the settling.
            self.send_command(f"3PA{mm}")
        self.state.settings["delay_pos_mm"] = mm
        return mm

    def move_delay_ps(self, ps: float, wait: bool = False, abort_flag=None) -> float:
        mm = self.move_delay_mm(self.ps_to_mm(ps), wait=wait, abort_flag=abort_flag)
        self.state.settings["delay_ps"] = float(ps)
        return mm

    # ── Streamed cut (alignment) ─────────────────────────────────────────────

    def streamed_cut(self, axis: int, target_raw: float, velocity: float,
                     read_fn, to_user, on_point=None, abort_flag=None,
                     max_points: int = 1000):
        """Move one axis slowly to target_raw, reading read_fn() as it goes.

        Returns (positions_user_units, readings). The axis velocity is put
        back to FAST_VELOCITY afterwards whatever happens.
        """
        xs, rs = [], []
        with self._lock:
            try:
                self.quick_command(f"{axis}VA{velocity}")
                self.quick_command(f"{axis}PA{target_raw}")
                for _ in range(max_points):
                    if abort_flag is not None and abort_flag():
                        break
                    self.quick_command(f"{axis}TP?")
                    reply = self.quick_read()
                    try:
                        pos = float(reply)
                    except ValueError:
                        time.sleep(0.01)
                        continue
                    r = read_fn()
                    xs.append(to_user(pos))
                    rs.append(float("nan") if r is None else float(r))
                    if on_point is not None:
                        on_point(xs, rs)
                    if abs(pos - target_raw) < 1e-4:
                        break
                    time.sleep(0.01)
            finally:
                self.quick_command(f"{axis}VA{FAST_VELOCITY}")
        return xs, rs

    def close(self):
        self.ser.close()
