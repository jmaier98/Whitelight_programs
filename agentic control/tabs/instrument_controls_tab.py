# tabs/instrument_controls_tab.py
"""
Instrument Controls — every single-value setting on the microscope as a
(label · entry · Go) row, plus command buttons and a live view of the state.

This replaces the "Motion Controls" box and the rotation / photon-counter
fields of the old TwoDscan program, and is what the agent uses through
list_instrument_controls / set_instrument_control / press_instrument_button.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QPushButton,
    QLineEdit, QLabel, QScrollArea, QFrame, QTextEdit,
)

from helpers.state_header import instrument_state_lines

TAB_NAME = "Instrument Controls"


class InstrumentControlsTab(QWidget):
    done_sig = pyqtSignal(str)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.state = controller.state
        c = controller
        st = self.state.settings

        def setting(key, scale=1.0):
            def f(v):
                st[key] = float(v) * scale
            return f

        # (label, state key shown in the field, setter, needs instrument)
        self._controls = [
            ("X pos (µm)",                   "x_pos_um",        c.move_x,              "ESP"),
            ("Y pos (µm)",                   "y_pos_um",        c.move_y,              "ESP"),
            ("Delay (ps)",                   "delay_ps",        lambda v: c.set_delay_ps(v, wait=True), "ESP"),
            ("Delay pos (mm)",               "delay_pos_mm",    c.set_delay_mm,        "ESP"),
            ("Time-zero pos (mm)",           "time_zero_pos_mm", c.set_time_zero,      None),
            ("Z pos (mm)",                   "z_pos_mm",        c.set_z,               "ZStage"),
            ("Wavelength (nm)",              "wavelength_nm",   c.set_wavelength,      "SP2500"),
            ("Waveplate angle (°)",          "waveplate_angle_deg", c.set_waveplate,   "BTT"),
            ("Waveplate offset (°)",         "waveplate_offset_deg", c.set_waveplate_offset, "BTT"),
            ("Rot 1 (°)",                    "rot_1_deg",       c.rot_1,               "BTT"),
            ("Rot 2 (°)",                    "rot_2_deg",       c.rot_2,               "BTT"),
            ("Rot 1 pos 1 (°) [dichroism]",  "rot_1_pos_1_deg", setting("rot_1_pos_1_deg"), None),
            ("Rot 1 pos 2 (°) [dichroism]",  "rot_1_pos_2_deg", setting("rot_1_pos_2_deg"), None),
            ("Rot 2 pos 1 (°) [dichroism]",  "rot_2_pos_1_deg", setting("rot_2_pos_1_deg"), None),
            ("Rot 2 pos 2 (°) [dichroism]",  "rot_2_pos_2_deg", setting("rot_2_pos_2_deg"), None),
            ("SHG LCP rot 1 angle (°)",      "shg_lcp_rot_1_deg", setting("shg_lcp_rot_1_deg"), None),
            ("SHG RCP rot 1 angle (°)",      "shg_rcp_rot_1_deg", setting("shg_rcp_rot_1_deg"), None),
            ("Top gate (V)",                 "top_gate_v",      lambda v: c.ramp_gate("top", v), "TopGate"),
            ("Back gate (V)",                "back_gate_v",     lambda v: c.ramp_gate("back", v), "BackGate"),
            ("Gate current limit (A)",       "gate_current_limit_a", setting("gate_current_limit_a"), None),
            ("Keithley ramp step (V)",       "keithley_ramp_step_v", setting("keithley_ramp_step_v"), None),
            ("Keithley ramp wait (ms)",      "keithley_ramp_dwell_s", setting("keithley_ramp_dwell_s", 1e-3), None),
            ("Photon counter acq time (s)",  "pc_acquisition_time_s",
             lambda v: c.set_photon_counter(acq_time_s=v), "SR400"),
            ("Photon counter discriminator (V)", "pc_discriminator_v",
             lambda v: c.set_photon_counter(disc_v=v), "SR400"),
        ]
        self._buttons = [
            ("Reset alignment offsets", c.reset_offsets, None),
            ("Enable ESP motors",       lambda: c.get_instrument("ESP").enable_motors(), "ESP"),
            ("Top gate output ON",      lambda: c.get_instrument("TopGate").output_on(), "TopGate"),
            ("Top gate output OFF",     lambda: c.get_instrument("TopGate").output_off(), "TopGate"),
            ("Back gate output ON",     lambda: c.get_instrument("BackGate").output_on(), "BackGate"),
            ("Back gate output OFF",    lambda: c.get_instrument("BackGate").output_off(), "BackGate"),
            ("Ramp both gates to 0 V",  self._zero_gates, None),
            ("Read Z stage position",   self._read_z, "ZStage"),
            ("Read spectrometer wavelength", self._read_wl, "SP2500"),
        ]

        # ── UI ───────────────────────────────────────────────────────────────
        dv = QDoubleValidator(-1e300, 1e300, 12, self)
        ctrl_box = QGroupBox("Controls (type a value, press Go)")
        grid = QGridLayout(ctrl_box)
        self._entries: dict[str, QLineEdit] = {}
        for i, (label, key, _, need) in enumerate(self._controls):
            r, col = i % 12, (i // 12) * 3
            e = QLineEdit(self._fmt(key)); e.setValidator(dv)
            go = QPushButton("Go"); go.setFixedWidth(40)
            go.clicked.connect(lambda _, l=label: self._go_clicked(l))
            e.returnPressed.connect(lambda l=label: self._go_clicked(l))
            ok = need is None or c.get_instrument(need) is not None
            for w in (e, go):
                w.setEnabled(ok)
            if not ok:
                e.setToolTip(f"{need} not connected")
            grid.addWidget(QLabel(label), r, col)
            grid.addWidget(e, r, col + 1)
            grid.addWidget(go, r, col + 2)
            self._entries[label] = e

        btn_box = QGroupBox("Commands")
        bg = QGridLayout(btn_box)
        for i, (label, _, need) in enumerate(self._buttons):
            b = QPushButton(label)
            b.setEnabled(need is None or c.get_instrument(need) is not None)
            b.clicked.connect(lambda _, l=label: self._button_clicked(l))
            bg.addWidget(b, i // 3, i % 3)

        state_box = QGroupBox("Current instrument state (saved with every data file)")
        sv = QVBoxLayout(state_box)
        self.state_view = QTextEdit(); self.state_view.setReadOnly(True)
        self.state_view.setFont(QFont("Consolas", 9))
        sv.addWidget(self.state_view)

        self.status_lbl = QLabel("Ready.")
        self.status_lbl.setStyleSheet("background:#e8f4fd; padding:4px; border:1px solid #aed6f1;")
        self.status_lbl.setWordWrap(True)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.addWidget(ctrl_box); cl.addWidget(btn_box); cl.addWidget(state_box, 1)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame); scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.addWidget(scroll, 1)
        outer.addWidget(self.status_lbl)

        self.done_sig.connect(self._on_done, Qt.ConnectionType.QueuedConnection)
        c.scan_signals.control_set.connect(self._on_control_set, Qt.ConnectionType.QueuedConnection)
        self._refresh()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _fmt(self, key) -> str:
        v = self.state.settings.get(key)
        if v is None:
            return ""
        if key == "keithley_ramp_dwell_s":
            v = float(v) * 1000
        return f"{v:g}" if isinstance(v, (int, float)) else str(v)

    def _refresh(self):
        for label, key, _, _ in self._controls:
            e = self._entries[label]
            if not e.hasFocus():
                e.setText(self._fmt(key))
        self.state_view.setPlainText("\n".join(instrument_state_lines(self.controller)))

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()

    def _find(self, items, label):
        want = label.strip().lower()
        for it in items:
            if it[0].lower() == want:
                return it
        matches = [it for it in items if want in it[0].lower()]
        if len(matches) == 1:
            return matches[0]
        names = [it[0] for it in items]
        raise KeyError(f"No unique match for '{label}'. Options: {names}")

    # ── GUI actions (run off the GUI thread — moves block) ───────────────────

    def _go_clicked(self, label):
        try:
            v = float(self._entries[label].text())
        except ValueError:
            self.status_lbl.setText(f"{label}: not a number")
            return
        self.status_lbl.setText(f"{label} → {v:g} …")
        self._async(lambda: self.set_control(label, v))

    def _button_clicked(self, label):
        self.status_lbl.setText(f"{label} …")
        self._async(lambda: self.press_button(label))

    def _async(self, fn):
        def run():
            try:
                fn()
            except Exception as e:
                self.done_sig.emit(f"Error: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _on_done(self, msg):
        self.status_lbl.setText(msg)
        self._refresh()

    def _on_control_set(self, label, value):
        if label in self._entries:
            self._entries[label].setText(f"{value:g}")
        self._refresh()

    def _zero_gates(self):
        for g in ("top", "back"):
            if self.controller.get_instrument("TopGate" if g == "top" else "BackGate") is not None:
                self.controller.ramp_gate(g, 0.0)

    def _read_z(self):
        z = self.controller.get_instrument("ZStage").get_position_mm()
        self.state.settings["z_pos_mm"] = z
        return z

    def _read_wl(self):
        nm = self.controller.get_instrument("SP2500").get_nm()
        if nm is not None:
            self.state.settings["wavelength_nm"] = nm
        return nm

    # ── Agent / programmatic API (blocking) ──────────────────────────────────

    def list_controls(self) -> list[dict]:
        out = []
        for label, key, _, need in self._controls:
            ok = need is None or self.controller.get_instrument(need) is not None
            out.append({"control": label, "current": self.state.settings.get(key),
                        "available": ok})
        return out

    def list_buttons(self) -> list[dict]:
        return [{"button": l, "available": n is None or self.controller.get_instrument(n) is not None}
                for l, _, n in self._buttons]

    def set_control(self, label: str, value: float):
        lab, key, fn, need = self._find(self._controls, label)
        if need is not None and self.controller.get_instrument(need) is None:
            raise RuntimeError(f"{need} is not connected")
        fn(float(value))
        self.controller.save_state()
        self.controller.log(f"{lab} set to {float(value):g}")
        self.controller.scan_signals.control_set.emit(lab, float(value))
        self.done_sig.emit(f"{lab} = {float(value):g}")
        return lab

    def press_button(self, label: str):
        lab, fn, need = self._find(self._buttons, label)
        if need is not None and self.controller.get_instrument(need) is None:
            raise RuntimeError(f"{need} is not connected")
        result = fn()
        self.controller.save_state()
        self.controller.log(f"Pressed: {lab}")
        self.done_sig.emit(f"{lab}: done" + (f" ({result})" if result is not None else ""))
        return {"button": lab, "result": result}
