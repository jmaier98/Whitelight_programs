"""Princeton Instruments SP2500 spectrometer / monochromator (RS-232, COM5)."""
from __future__ import annotations

import re
import threading
import time

import serial


class SP2500:
    def __init__(self, state, port: str = "COM5", baudrate: int = 9600, timeout: float = 1):
        self.state = state
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)
        self._lock = threading.Lock()
        nm = self.get_nm()
        if nm is None:
            self.ser.close()
            raise RuntimeError(f"nothing answered on {port} (SP2500 off or on another port?)")
        state.settings["wavelength_nm"] = nm

    def send_command(self, command: str, wait: float = 0.5, read_bytes: int = 100) -> str:
        with self._lock:
            self.ser.write(f"{command}\r".encode())
            time.sleep(wait)
            return self.ser.read(read_bytes).decode(errors="replace")

    def get_nm(self) -> float | None:
        m = re.findall(r"\d+\.\d+", self.send_command("?NM"))
        return float(m[0]) if m else None

    def set_nm_min(self, rate: float):
        self.send_command(f"{rate} NM/MIN")

    def set_nm(self, nm: float, timeout_attempts: int = 100) -> float:
        """Go to a wavelength and block until the controller answers 'ok'."""
        with self._lock:
            self.ser.write(f"{float(nm):.2f} NM\r".encode())
            time.sleep(0.5)
            for _ in range(timeout_attempts):
                if "ok" in self.ser.read(100).decode(errors="replace").lower():
                    break
                time.sleep(0.5)
            else:
                raise TimeoutError(f"SP2500 did not confirm the move to {nm} nm")
        self.state.settings["wavelength_nm"] = float(nm)
        return float(nm)

    def switch_grating(self, grating: int):
        self.send_command(f"{int(grating)} GRATING")
        time.sleep(5)

    def close(self):
        self.ser.close()
