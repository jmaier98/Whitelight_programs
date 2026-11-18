"""
Persistent instrument state for the white-light microscope.

Every driver writes the position/setting it just changed into
``state.settings``; the whole dict is written to microscope_state.json and
copied into the header of every saved data file, so each dataset records how
the instrument was set when it was taken.
"""
import json
import os
import tempfile
from pathlib import Path

STATE_FILE = Path(__file__).parent / "microscope_state.json"

DEFAULTS = {
    # ESP301 — sample stage (µm) and delay line
    # x/y_pos_um is the requested position; x/y_stage_um is where the stage
    # actually went (requested position + alignment offset).
    "x_pos_um": 0.0,
    "y_pos_um": 0.0,
    "x_stage_um": 0.0,
    "y_stage_um": 0.0,
    "delay_pos_mm": 0.0,
    "delay_ps": 0.0,
    "time_zero_pos_mm": -57.2,
    # Feature-tracking offsets added to every X/Y move (from the Alignment tab)
    "x_offset_um": 0.0,
    "y_offset_um": 0.0,
    "x_origin_um": 0.0,
    "y_origin_um": 0.0,
    # MLJ050 objective / sample Z stage
    "z_pos_mm": 0.0,
    # SP2500
    "wavelength_nm": 0.0,
    # BTT rotation mounts
    "rot_1_deg": 0.0,
    "rot_2_deg": 0.0,
    "waveplate_angle_deg": 0.0,
    "waveplate_offset_deg": 0.0,
    # Rotation positions used by the dichroism measurements
    "rot_1_pos_1_deg": 0.0,
    "rot_1_pos_2_deg": 90.0,
    "rot_2_pos_1_deg": 0.0,
    "rot_2_pos_2_deg": 90.0,
    "shg_lcp_rot_1_deg": 167.0,       # LCP RCP SHG: rot 1 angle for LCP...
    "shg_rcp_rot_1_deg": 212.0,       # ...and for RCP
    # SR400 photon counter
    "pc_acquisition_time_s": 1.0,
    "pc_discriminator_v": -0.005,
    # Keithley gates
    "top_gate_v": 0.0,
    "back_gate_v": 0.0,
    "top_gate_compliance_a": None,
    "back_gate_compliance_a": None,
    "keithley_ramp_step_v": 0.05,     # every gate change walks in steps of this
    "keithley_ramp_dwell_s": 0.005,   # ...waiting this long per step
    "gate_current_limit_a": 6e-10,    # scan-axis gate moves abort above this |I|
    "gate_breakdown_voltage": None,
    # Arduino
    "arduino_shutter_open": None,
    "pellicle_inserted": None,
    "beamsplitter_inserted": None,
    "led_brightness": None,
    "motor_a_net_steps": 0,
    "motor_b_net_steps": 0,
}


class MicroscopeState:
    def __init__(self, path=STATE_FILE):
        self._path = Path(path)
        self.settings = dict(DEFAULTS)
        self.load()

    def load(self):
        if self._path.exists():
            try:
                with open(self._path, "r") as f:
                    self.settings.update(json.load(f))
            except Exception as e:
                print(f"[state] could not read {self._path}: {e} — using defaults")
        else:
            print(f"[state] no state file yet — it will be created at {self._path}")

    def save(self):
        """Atomic write so a crash mid-save cannot leave a truncated file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self._path.parent), prefix=".state-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self.settings, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
