"""SR400 gated photon counter (GPIB 23)."""
from __future__ import annotations

import threading
import time

import pyvisa

ADDRESS = "GPIB0::23::INSTR"
GATE_WIDTH_S = 10e-9
GATE_DELAY_S = 3.22e-7


class SR400:
    def __init__(self, state, rm: pyvisa.ResourceManager | None = None, address: str = ADDRESS):
        self.state = state
        rm = rm or pyvisa.ResourceManager()
        self.inst = rm.open_resource(address)
        self.inst.write_termination = "\r\n"
        self.inst.read_termination = "\r\n"
        self._lock = threading.Lock()
        # The SR400 has no *IDN?; reading counter A proves something is there.
        self.inst.timeout = 1500
        try:
            if not self.inst.query("QA").strip():
                raise RuntimeError("no reply")
        except Exception:
            self.inst.close()
            raise
        self.inst.timeout = 5000

        st = state.settings
        self.acquisition_time = float(st.get("pc_acquisition_time_s", 1.0))
        disc = float(st.get("pc_discriminator_v", -0.005))
        with self._lock:
            self.inst.write(f"GW 0,{GATE_WIDTH_S}"); time.sleep(0.1)
            self.inst.write(f"GD 0,{GATE_DELAY_S}"); time.sleep(0.05)
            self.inst.write(f"CP 2,{int(1e7 * self.acquisition_time)}"); time.sleep(0.05)
            self.inst.write(f"DL 0,{disc}"); time.sleep(0.05)
            self.inst.write("DT 0"); time.sleep(0.05)

    def set_t_and_disc(self, t: float, disc: float):
        """Set the dwell (acquisition) time in s and the channel-A discriminator in V."""
        if not (-0.3 <= float(disc) <= 0.3):
            raise ValueError("Discriminator must be between -0.3 and 0.3 V")
        with self._lock:
            self.inst.write(f"DL 0,{float(disc)}"); time.sleep(0.05)
            self.acquisition_time = float(t)
            self.inst.write(f"CP 2,{int(1e7 * float(t))}"); time.sleep(0.05)
        self.state.settings["pc_acquisition_time_s"] = float(t)
        self.state.settings["pc_discriminator_v"] = float(disc)

    def acquire(self) -> float:
        """Run one count period and return the counts on counter A."""
        with self._lock:
            self.inst.write("CR")
            self.inst.write("CS")
            time.sleep(self.acquisition_time + 0.1)
            reply = self.inst.query("QA")
        try:
            return float(int(reply.strip()))
        except ValueError:
            return float("nan")

    def close(self):
        try:
            self.inst.close()
        except Exception:
            pass
