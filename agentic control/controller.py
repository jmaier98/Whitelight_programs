"""
MicroscopeController — the single API used by the GUI tabs and the agent.

It owns:
  * high-level moves that know about the white-light microscope's quirks
    (alignment offsets on X/Y, the ps→mm delay conversion, gate ramps that
    watch the leakage current of BOTH gates)
  * AXES          — every scan axis, name → setter(value, value2=None, abort=None)
  * MEASUREMENTS  — every scan measurement, name → fn(wait_s, abort) → tuple
  * MEAS_COLUMNS  — column names for each measurement (used in file headers)
  * ScanSignals   — Qt signals that keep the tabs in step with agent actions
"""
from __future__ import annotations

import math
import random
import threading
import time
from datetime import datetime
from typing import Callable, Dict, List

from PyQt6.QtCore import QObject, pyqtSignal

from drivers.Keithley2400 import GateCurrentLimit

N_CH = 9   # data channels per scan point (the 4-channel dichroism needs 9)


class ScanSignals(QObject):
    # 2D scan driven by the agent — the 2D tab plots it live
    scan_2d_configured = pyqtSignal(object)          # settings dict
    scan_2d_started    = pyqtSignal(object)          # {'xs', 'ys', 'n_scans'}
    scan_2d_point      = pyqtSignal(int, int, int, object)   # scan, ix, iy, data tuple
    scan_2d_done       = pyqtSignal(int)             # scan index (1-based)

    # A control changed (by the agent or another tab): (label, value)
    control_set = pyqtSignal(str, float)

    # Stop everything that is running
    stop_all = pyqtSignal()

    # Ask the main window to show a tab
    activate_tab = pyqtSignal(str)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _nan(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return math.nan


class MicroscopeController:
    def __init__(self, instrument_manager, state):
        self.im = instrument_manager
        self.state = state
        self._log: list[str] = []
        self.scan_signals = ScanSignals()
        self._stop_requested = False
        self._axes: Dict[str, Callable] | None = None
        self._meas: Dict[str, Callable] | None = None
        # Serialises gate ramps: two tabs ramping the same Keithley at once
        # would fight over the setpoint.
        self._gate_lock = threading.Lock()

    # ── Logging / instruments / stop ─────────────────────────────────────────

    def log(self, msg: str):
        line = f"[{_ts()}] {msg}"
        self._log.append(line)
        try:
            print(line)
        except Exception:
            # A Windows console (cp1252) cannot print µ, →, … — logging must
            # never be what stops a scan.
            try:
                print(line.encode("ascii", "replace").decode())
            except Exception:
                pass

    def get_log(self, last_n: int = 50) -> list[str]:
        return self._log[-last_n:]

    def get_instrument(self, name: str):
        try:
            return self.im.get(name)
        except KeyError:
            return None

    def request_stop_all(self):
        self._stop_requested = True
        self.scan_signals.stop_all.emit()

    def clear_stop(self):
        self._stop_requested = False

    def stop_requested(self) -> bool:
        return self._stop_requested

    def get_state(self) -> dict:
        return {
            "instruments_connected": self.im.connected(),
            "instruments_missing": list(self.im.failures),
            "instruments_disabled_in_config": self.im.disabled(),
            "partial_problems": list(self.im.notes),
            "settings": dict(self.state.settings),
        }

    def save_state(self):
        try:
            self.state.save()
        except Exception as e:
            self.log(f"Could not save state file: {e}")

    def _need(self, name: str):
        inst = self.get_instrument(name)
        if inst is None:
            raise RuntimeError(f"{name} is not connected")
        return inst

    # ── Sample stage (µm, with alignment offset) ─────────────────────────────

    def move_x(self, x_um: float, abort=None):
        st = self.state.settings
        self._need("ESP").move_x(float(x_um) + float(st.get("x_offset_um", 0.0)), abort_flag=abort)
        st["x_pos_um"] = float(x_um)

    def move_y(self, y_um: float, abort=None):
        st = self.state.settings
        self._need("ESP").move_y(float(y_um) + float(st.get("y_offset_um", 0.0)), abort_flag=abort)
        st["y_pos_um"] = float(y_um)

    def move_xy(self, x_um: float, y_um: float, abort=None):
        self.move_x(x_um, abort)
        self.move_y(y_um, abort)

    def reset_offsets(self):
        self.state.settings["x_offset_um"] = 0.0
        self.state.settings["y_offset_um"] = 0.0
        self.log("Alignment offsets reset to 0")

    # ── Delay line ───────────────────────────────────────────────────────────

    def set_delay_ps(self, ps: float, wait: bool = False, abort=None):
        self._need("ESP").move_delay_ps(float(ps), wait=wait, abort_flag=abort)

    def set_delay_mm(self, mm: float, abort=None):
        self._need("ESP").move_delay_mm(float(mm), wait=True, abort_flag=abort)

    def set_time_zero(self, mm: float):
        self.state.settings["time_zero_pos_mm"] = float(mm)

    # ── Z stage, spectrometer, rotation mounts ───────────────────────────────

    def set_z(self, z_mm: float):
        self._need("ZStage").move_mm(float(z_mm))

    def set_wavelength(self, nm: float):
        self._need("SP2500").set_nm(float(nm))

    def rot_1(self, deg: float):
        self._need("BTT").rot_1(float(deg))

    def rot_2(self, deg: float):
        self._need("BTT").rot_2(float(deg))

    def set_waveplate(self, angle: float, offset: float | None = None):
        if offset is None:
            offset = float(self.state.settings.get("waveplate_offset_deg", 0.0))
        self._need("BTT").rot_12(float(angle), offset=float(offset))

    def set_waveplate_offset(self, offset: float):
        angle = float(self.state.settings.get("waveplate_angle_deg", 0.0))
        self._need("BTT").rot_12(angle, offset=float(offset))

    # ── Photon counter ───────────────────────────────────────────────────────

    def set_photon_counter(self, acq_time_s: float | None = None, disc_v: float | None = None):
        st = self.state.settings
        t = float(acq_time_s if acq_time_s is not None else st.get("pc_acquisition_time_s", 1.0))
        d = float(disc_v if disc_v is not None else st.get("pc_discriminator_v", -0.005))
        self._need("SR400").set_t_and_disc(t, d)

    # ── Gates ────────────────────────────────────────────────────────────────

    def _gates(self):
        return self.get_instrument("TopGate"), self.get_instrument("BackGate")

    def ramp_gate(self, which: str, volts: float, abort=None, current_limit: float | None = None):
        """Ramp the top or back gate, watching the leakage of BOTH gates.

        If either |I| exceeds the limit both gates are walked back to 0 V and
        GateCurrentLimit is raised (the scan that called this then stops),
        exactly as the original TwoDscan did.
        """
        which = which.lower()
        top, back = self._gates()
        gate, other = (top, back) if which.startswith("top") else (back, top)
        name = "Top gate" if gate is top else "Back gate"
        if gate is None:
            raise RuntimeError(f"{name} Keithley is not connected")
        limit = float(current_limit if current_limit is not None
                      else self.state.settings.get("gate_current_limit_a", 6e-10))

        def _check(i_this):
            i_other = other.read_current() if other is not None else 0.0
            if (math.isfinite(i_this) and abs(i_this) > limit) or \
               (math.isfinite(i_other) and abs(i_other) > limit):
                self.log(f"{name}: |I| over {limit:.2e} A (I={i_this:.3e}, other={i_other:.3e})"
                         " — ramping both gates to 0 V")
                self._ramp_both_to_zero()
                raise GateCurrentLimit(
                    f"Gate current limit {limit:.2e} A exceeded while setting {name} to "
                    f"{volts:g} V — both gates returned to 0 V")

        with self._gate_lock:
            gate.ramp_voltage(float(volts), abort_flag=abort, check=_check)
        self.save_state()

    def _ramp_both_to_zero(self):
        for g in self._gates():
            if g is not None:
                try:
                    g.ramp_voltage(0.0, step_V=0.05)
                except Exception as e:
                    self.log(f"Ramp to 0 V failed on {g.name}: {e}")

    def gate_line_cut(self, tg: float, bg: float, abort=None):
        self.ramp_gate("top", tg, abort)
        self.ramp_gate("back", bg, abort)

    # ── Scan axes ────────────────────────────────────────────────────────────

    @property
    def AXES(self) -> Dict[str, Callable]:
        if self._axes is None:
            self._axes = self._build_axes()
        return self._axes

    def _build_axes(self) -> Dict[str, Callable]:
        """name → setter(value, value2=None, abort=None).

        value2 is only used by 'Gate line cut (TG, BG)', where value is the top
        gate and value2 the back gate for the same point.
        """
        g = self.get_instrument
        a: Dict[str, Callable] = {}
        if g("ESP") is not None:
            a["X pos (µm)"]   = lambda v, v2=None, abort=None: self.move_x(v, abort)
            a["Y pos (µm)"]   = lambda v, v2=None, abort=None: self.move_y(v, abort)
            a["Delay pos (mm)"] = lambda v, v2=None, abort=None: self.set_delay_mm(v, abort)
            # Fire-and-forget like the original; the per-point wait covers settling.
            a["Delay time (ps)"] = lambda v, v2=None, abort=None: self.set_delay_ps(v, False, abort)
            a["Delay time (ps), wait for stage"] = \
                lambda v, v2=None, abort=None: self.set_delay_ps(v, True, abort)
        if g("ZStage") is not None:
            a["Z pos (mm)"] = lambda v, v2=None, abort=None: self.set_z(v)
        if g("BTT") is not None:
            a["Waveplate angle (°)"]  = lambda v, v2=None, abort=None: self.set_waveplate(v)
            a["Waveplate offset (°)"] = lambda v, v2=None, abort=None: self.set_waveplate_offset(v)
            a["Rot 1 (°)"] = lambda v, v2=None, abort=None: self.rot_1(v)
            a["Rot 2 (°)"] = lambda v, v2=None, abort=None: self.rot_2(v)
        if g("SP2500") is not None:
            a["Wavelength (nm)"] = lambda v, v2=None, abort=None: self.set_wavelength(v)
        if g("TopGate") is not None:
            a["Top gate (V)"] = lambda v, v2=None, abort=None: self.ramp_gate("top", v, abort)
        if g("BackGate") is not None:
            a["Back gate (V)"] = lambda v, v2=None, abort=None: self.ramp_gate("back", v, abort)
        if g("TopGate") is not None and g("BackGate") is not None:
            def _cut(v, v2=None, abort=None):
                if v2 is None:
                    raise ValueError("Gate line cut needs a back-gate value for every point")
                self.gate_line_cut(v, v2, abort)
            a["Gate line cut (TG, BG)"] = _cut
        a["dummy"] = lambda v, v2=None, abort=None: None
        return a

    # ── Measurements ─────────────────────────────────────────────────────────

    @property
    def MEASUREMENTS(self) -> Dict[str, Callable]:
        if self._meas is None:
            self._meas, self.MEAS_COLUMNS = self._build_measurements()
        return self._meas

    def measurement_columns(self, name: str) -> List[str]:
        _ = self.MEASUREMENTS
        cols = list(self.MEAS_COLUMNS.get(name, []))
        return cols + [f"data{i + 1}" for i in range(len(cols), N_CH)]

    def _build_measurements(self):
        """name → fn(wait_s, abort) returning up to N_CH values.

        wait_s is the scan's per-point wait, re-used as the settle time after
        each rotation in the dichroism measurements (as in the original).
        """
        li = self.get_instrument("Lockins")
        pc = self.get_instrument("SR400")
        btt = self.get_instrument("BTT")
        st = self.state.settings
        m: Dict[str, Callable] = {}
        cols: Dict[str, List[str]] = {}

        def _div(a, b, eps=1e-9):
            if not (math.isfinite(a) and math.isfinite(b)):
                return math.nan
            return a / (b if b != 0 else eps)

        def _sleep(wait_s, abort):
            t_end = time.time() + max(0.0, wait_s)
            while time.time() < t_end:
                if abort is not None and abort():
                    return
                time.sleep(max(0.0, min(0.05, t_end - time.time())))

        # Lock-ins that answered at startup; a measurement is offered only when
        # every lock-in it reads is present.
        have = set(li.present) if li is not None else set()

        def add(name, columns, fn, lockins=()):
            if not set(lockins) <= have:
                return
            m[name] = fn
            cols[name] = columns

        if pc is not None:
            add("Photon counter", ["counts"], lambda w, a: (pc.acquire(),))

        if li is not None:
            for n in (1, 2, 3):
                add(f"Lockin {n}", [f"X{n}", f"Y{n}"],
                    (lambda n: lambda w, a: (li.read_x(n), li.read_y(n)))(n), {n})

            def _drr(w, a):
                dr, r = li.read_x(2), li.read_x(1)
                return (dr, _div(dr, r), r)
            add("deltaR/R", ["dR", "dR/R", "R"], _drr, {1, 2})

            add("deltaR/R alternate", ["dR (lockin 3)", "R (lockin 1)"],
                lambda w, a: (li.read_x(3), li.read_x(1)), {1, 3})

            add("Photocurrent and R", ["I+ (lockin 2)", "I- (lockin 1)", "R (lockin 3)"],
                lambda w, a: (li.read_x(2), li.read_x(1), li.read_x(3)), {1, 2, 3})

            add("Record offsets", ["x_offset_um", "y_offset_um", "R (lockin 1)"],
                lambda w, a: (_nan(st.get("x_offset_um")), _nan(st.get("y_offset_um")),
                              li.read_x(1)), {1})

        if li is not None and pc is not None:
            def _counts_drr(w, a):
                counts = pc.acquire()
                dr, r = li.read_x(2), li.read_x(1)
                return (dr, r, _div(dr, r), _div(r, dr), counts)
            add("counts and dR/R", ["dR", "R", "dR/R", "R/dR", "counts"], _counts_drr, {1, 2})

        if li is not None and btt is not None:
            def _cd(rot, key):
                def fn(w, a):
                    dR1, R1 = li.read_x(2), li.read_x(1)
                    rot(float(st[f"{key}_pos_2_deg"]))
                    _sleep(w, a)
                    dR2, R2 = li.read_x(2), li.read_x(1)
                    rot(float(st[f"{key}_pos_1_deg"]))
                    return (dR1, dR2, R1, R2, dR1 - dR2, R1 - R2)
                return fn
            cd_cols = ["dR_1", "dR_2", "R_1", "R_2", "dR_diff", "R_diff"]
            add("Circular dichroism (rot 1)", cd_cols, _cd(btt.rot_1, "rot_1"), {1, 2})
            add("Circular dichroism (rot 2)", cd_cols, _cd(btt.rot_2, "rot_2"), {1, 2})

            def _four(fast):
                def fn(w, a):
                    p11, p12 = float(st["rot_1_pos_1_deg"]), float(st["rot_1_pos_2_deg"])
                    p21, p22 = float(st["rot_2_pos_1_deg"]), float(st["rot_2_pos_2_deg"])
                    vals = []
                    vals.append((li.read_x(2), li.read_x(1)))
                    if fast == 1:   # rot 1 fast, rot 2 slow
                        btt.rot_1(p12); _sleep(w, a); vals.append((li.read_x(2), li.read_x(1)))
                        btt.rot_1_2(p11, p22); _sleep(w, a); vals.append((li.read_x(2), li.read_x(1)))
                        btt.rot_1(p12); _sleep(w, a); vals.append((li.read_x(2), li.read_x(1)))
                    else:           # rot 2 fast, rot 1 slow
                        btt.rot_2(p22); _sleep(w, a); vals.append((li.read_x(2), li.read_x(1)))
                        btt.rot_1_2(p12, p21); _sleep(w, a); vals.append((li.read_x(2), li.read_x(1)))
                        btt.rot_2(p22); _sleep(w, a); vals.append((li.read_x(2), li.read_x(1)))
                    btt.rot_1_2(p11, p21)
                    dR = [v[0] for v in vals]
                    R = [v[1] for v in vals]
                    return (*dR, *R, dR[0] - dR[3])
                return fn
            four_cols = ["dR_1", "dR_2", "dR_3", "dR_4", "R_1", "R_2", "R_3", "R_4", "dR1-dR4"]
            add("4 channel dichroism (1 fast 2 slow)", four_cols, _four(1), {1, 2})
            add("4 channel dichroism (2 fast 1 slow)", four_cols, _four(2), {1, 2})

        if pc is not None and btt is not None:
            def _shg(w, a):
                # Starts (and ends) with rot 1 at the LCP angle.
                lcp = pc.acquire()
                btt.rot_1(float(st.get("shg_rcp_rot_1_deg", 212.0)))
                _sleep(w, a)
                rcp = pc.acquire()
                btt.rot_1(float(st.get("shg_lcp_rot_1_deg", 167.0)))
                return (lcp, rcp, lcp - rcp, _div(lcp - rcp, lcp + rcp))
            add("LCP RCP SHG", ["LCP", "RCP", "LCP-RCP", "(LCP-RCP)/(LCP+RCP)"], _shg)

        add("random", ["rand1", "rand2", "rand3"],
            lambda w, a: (random.random(), random.random(), 100 * random.random()))
        return m, cols
