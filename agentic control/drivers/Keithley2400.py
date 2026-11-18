"""
Keithley 2400 SourceMeter used as a gate (GPIB).

The white-light microscope has two of them:
  top gate  : GPIB 24
  back gate : GPIB 22

Both are run as voltage sources measuring current. The connection is kept open
for the life of the program (the old keithley_driver re-opened it on every
call). The output is NOT switched on or re-zeroed when the program starts, so
a gate that is biased when the program opens stays where it is.
"""
from __future__ import annotations

import math
import threading
import time

import numpy as np
import pyvisa

TOP_GATE_ADDR = "GPIB0::24::INSTR"
BACK_GATE_ADDR = "GPIB0::22::INSTR"


class GateCurrentLimit(RuntimeError):
    """Raised when a gate ramp trips the leakage-current limit."""


def _first_value(raw: str) -> float:
    """Keithley replies may be 'V,I,R,t,status' — return the first number."""
    return float(raw.strip().split(",")[0])


class Keithley2400:
    def __init__(self, state, address: str, name: str,
                 rm: pyvisa.ResourceManager | None = None):
        self.state = state
        self.name = name                 # "top_gate" or "back_gate"
        self._lock = threading.RLock()
        rm = rm or pyvisa.ResourceManager()
        self.inst = rm.open_resource(address)
        # Opening a GPIB address succeeds even with nothing there, so make the
        # meter identify itself before counting it as present.
        self.inst.timeout = 1500
        try:
            self.idn = self.inst.query("*IDN?").strip()
            if not self.idn:
                raise RuntimeError("no reply to *IDN?")
        except Exception:
            self.inst.close()
            raise
        self.inst.timeout = 5000
        with self._lock:
            self.inst.write("SOUR:FUNC VOLT")
            self.inst.write("SENS:FUNC 'CURR'")
            self.inst.write("FORM:ELEM CURR")   # replies hold only the current

    # ── Basic I/O ────────────────────────────────────────────────────────────

    def get_voltage_setpoint(self) -> float:
        with self._lock:
            return _first_value(self.inst.query("SOUR:VOLT?"))

    def read_current(self) -> float:
        try:
            with self._lock:
                return _first_value(self.inst.query("MEAS:CURR?"))
        except Exception as e:
            print(f"[{self.name}] current read failed: {e}")
            return math.nan

    def set_voltage_immediate(self, volts: float) -> float:
        """Jump straight to a voltage (output on) and return the measured current.

        Only for callers that already step in small increments — everything
        else should use ramp_voltage().
        """
        with self._lock:
            self.inst.write(f"SOUR:VOLT:LEV {float(volts):.4f}")
            self.inst.write("OUTP ON")
            i = self.read_current()
        self.state.settings[f"{self.name}_v"] = float(volts)
        return i

    def output_on(self):
        with self._lock:
            self.inst.write("OUTP ON")

    def output_off(self):
        with self._lock:
            self.inst.write("OUTP OFF")

    def is_output_on(self) -> bool | None:
        try:
            with self._lock:
                return bool(int(_first_value(self.inst.query("OUTP?"))))
        except Exception:
            return None

    # ── Compliance ───────────────────────────────────────────────────────────

    def set_current_compliance(self, amps: float):
        if amps <= 0:
            raise ValueError("Compliance must be > 0 A")
        with self._lock:
            self.inst.write(f"SENS:CURR:PROT {float(amps):.6g}")
        self.state.settings[f"{self.name}_compliance_a"] = float(amps)

    def get_current_compliance(self) -> float:
        with self._lock:
            return _first_value(self.inst.query("SENS:CURR:PROT?"))

    def in_compliance(self) -> bool:
        try:
            with self._lock:
                return bool(int(_first_value(self.inst.query("SENS:CURR:PROT:TRIP?"))))
        except Exception:
            return False

    # ── Ramping ──────────────────────────────────────────────────────────────

    def ramp_voltage(self, target: float, step_V: float | None = None,
                     dwell_s: float | None = None, abort_flag=None,
                     check=None) -> float:
        """Walk to target in steps, never jumping the gate.

        step_V / dwell_s default to the global ramp settings in the state.
        check(i_this) is called after every step with this gate's current and
        may raise (e.g. GateCurrentLimit) to stop the ramp. Returns the last
        measured current.
        """
        st = self.state.settings
        step = abs(float(step_V if step_V is not None else st.get("keithley_ramp_step_v", 0.05)))
        dwell = max(0.0, float(dwell_s if dwell_s is not None else st.get("keithley_ramp_dwell_s", 0.005)))
        if step <= 0:
            raise ValueError("Ramp step must be > 0 V")

        v = self.get_voltage_setpoint()
        target = float(target)
        i = math.nan
        while abs(target - v) > 1e-4:
            if abort_flag is not None and abort_flag():
                break
            v += math.copysign(min(step, abs(target - v)), target - v)
            i = self.set_voltage_immediate(v)
            if check is not None:
                check(i)
            if dwell:
                time.sleep(dwell)
        return i

    def ramp_to_zero_fast(self, rate_V_per_s: float = 7.0, step_V: float = 0.05):
        """Measurement-free ramp back to 0 V at a fixed rate (cannot be aborted)."""
        v0 = self.get_voltage_setpoint()
        if abs(v0) < 1e-6:
            return
        n = max(1, int(math.ceil(abs(v0) / abs(step_V))))
        dt = abs(v0) / abs(rate_V_per_s) / n
        with self._lock:
            for v in np.linspace(v0, 0.0, n + 1)[1:]:
                self.inst.write(f"SOUR:VOLT:LEV {float(v):.4f}")
                time.sleep(dt)
        self.state.settings[f"{self.name}_v"] = 0.0

    def close(self):
        try:
            self.inst.close()
        except Exception:
            pass
