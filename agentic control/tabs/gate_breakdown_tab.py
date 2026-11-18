# tabs/gate_breakdown_tab.py
"""
Gate breakdown tester — the old Gate_testing_breakdown program.

One gate (top or back Keithley 2400) is swept while the leakage current of
BOTH gates is read at every step. The sweep stops when either |I| reaches the
abort current or a source hits compliance, and ALWAYS walks the swept gate
back to 0 V afterwards (finished, breakdown, stop or error).

(The old program's ramp-down only wrote the first point of the ramp, so it
left the gate biased; this version really returns it to 0 V.)
"""
from __future__ import annotations

import base64
import io
import math
import os
import threading
import time

import numpy as np
from PyQt6.QtCore import QThread, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDoubleValidator, QIntValidator, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QGroupBox,
    QPushButton, QLineEdit, QLabel, QComboBox, QCheckBox, QMessageBox, QFileDialog,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from helpers.state_header import instrument_state_lines

TAB_NAME = "Gate Breakdown"
GATES = {"top": "TopGate", "back": "BackGate"}


class GateBreakdownTab(QWidget):
    point_sig     = pyqtSignal(float, float, float)     # V, I_top, I_back
    started_sig   = pyqtSignal(str)                     # swept gate
    finished_sig  = pyqtSignal(bool, str, float)        # aborted, message, breakdown V
    status_sig    = pyqtSignal(str)
    _gui_call_sig = pyqtSignal(object)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.state = controller.state
        self.k = {g: controller.get_instrument(n) for g, n in GATES.items()}

        self._stop = [False]
        self._thread: threading.Thread | None = None
        self.vs: list[float] = []
        self.i_top: list[float] = []
        self.i_back: list[float] = []
        self.breakdown_v = math.nan
        self._swept = "top"

        dv = QDoubleValidator(-1e300, 1e300, 9, self)
        dv_pos = QDoubleValidator(0.0, 1e300, 12, self)

        # ── Static gate control ──────────────────────────────────────────────
        gate_box = QGroupBox("Gates")
        gf = QGridLayout(gate_box)
        self.v_entry, self.comp_entry = {}, {}
        for row, g in enumerate(("top", "back")):
            self.v_entry[g] = QLineEdit("0"); self.v_entry[g].setValidator(dv)
            self.comp_entry[g] = QLineEdit("1e-6"); self.comp_entry[g].setValidator(dv_pos)
            go = QPushButton("Ramp"); go.clicked.connect(lambda _, g=g: self._ramp_clicked(g))
            cset = QPushButton("Set"); cset.clicked.connect(lambda _, g=g: self._set_compliance(g))
            gf.addWidget(QLabel(f"{g.capitalize()} gate V:"), row * 2, 0)
            gf.addWidget(self.v_entry[g], row * 2, 1)
            gf.addWidget(go, row * 2, 2)
            gf.addWidget(QLabel("  compliance (A):"), row * 2 + 1, 0)
            gf.addWidget(self.comp_entry[g], row * 2 + 1, 1)
            gf.addWidget(cset, row * 2 + 1, 2)
        self.ramp_step = QLineEdit(f"{self.state.settings.get('keithley_ramp_step_v', 0.05):g}")
        self.ramp_dwell = QLineEdit(f"{float(self.state.settings.get('keithley_ramp_dwell_s', 0.005)) * 1000:g}")
        for w in (self.ramp_step, self.ramp_dwell):
            w.setValidator(dv_pos)
            w.editingFinished.connect(self._apply_ramp_params)
        gf.addWidget(QLabel("Ramp step (V):"), 4, 0); gf.addWidget(self.ramp_step, 4, 1)
        gf.addWidget(QLabel("Ramp wait (ms):"), 5, 0); gf.addWidget(self.ramp_dwell, 5, 1)
        gate_box.setToolTip("Ramp step / wait apply to every gate change in the program "
                            "(not to the breakdown sweep below, which uses its own step).")

        # ── Sweep ────────────────────────────────────────────────────────────
        sweep_box = QGroupBox("Breakdown sweep")
        sf = QFormLayout(sweep_box)
        self.gate_combo = QComboBox(); self.gate_combo.addItems(["top", "back"])
        self.v_start = QLineEdit("0"); self.v_start.setValidator(dv)
        self.v_end = QLineEdit("5"); self.v_end.setValidator(dv)
        self.v_step = QLineEdit("0.01"); self.v_step.setValidator(dv_pos)
        self.dwell_ms = QLineEdit("20"); self.dwell_ms.setValidator(QIntValidator(0, 600000, self))
        self.i_abort = QLineEdit("1e-7"); self.i_abort.setValidator(dv_pos)
        self.down_rate = QLineEdit("7"); self.down_rate.setValidator(dv_pos)
        sf.addRow("Sweep gate:", self.gate_combo)
        sf.addRow("Start V:", self.v_start)
        sf.addRow("End V:", self.v_end)
        sf.addRow("Step V:", self.v_step)
        sf.addRow("Dwell (ms):", self.dwell_ms)
        sf.addRow("Abort at |I| (A):", self.i_abort)
        sf.addRow("Ramp down (V/s):", self.down_rate)
        row = QHBoxLayout()
        self.start_btn = QPushButton("Start sweep"); self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("Stop"); self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setEnabled(False)
        row.addWidget(self.start_btn); row.addWidget(self.stop_btn)
        sf.addRow(row)

        # ── Save ─────────────────────────────────────────────────────────────
        save_box = QGroupBox("Save")
        sg = QGridLayout(save_box)
        self.folder = QLineEdit(os.path.expanduser("~/gate_breakdown"))
        self.filename = QLineEdit("gate_sweep")
        browse = QPushButton("Browse…"); browse.clicked.connect(self._browse)
        save = QPushButton("Save"); save.clicked.connect(self._save)
        sg.addWidget(QLabel("Folder:"), 0, 0); sg.addWidget(self.folder, 0, 1); sg.addWidget(browse, 0, 2)
        sg.addWidget(QLabel("File (no ext):"), 1, 0); sg.addWidget(self.filename, 1, 1); sg.addWidget(save, 1, 2)

        big = QFont(); big.setPointSize(16); big.setBold(True)
        self.readout = QLabel("–"); self.readout.setFont(big)
        self.result_lbl = QLabel(""); self.result_lbl.setStyleSheet("color:#c0392b; font-weight:bold;")
        self.status_lbl = QLabel("Idle."); self.status_lbl.setWordWrap(True)

        ctrl = QVBoxLayout()
        for w in (gate_box, sweep_box, save_box, self.readout, self.result_lbl, self.status_lbl):
            ctrl.addWidget(w)
        ctrl.addStretch(1)

        # ── Plot ─────────────────────────────────────────────────────────────
        right = QVBoxLayout()
        self.log_chk = QCheckBox("Log |I|"); self.log_chk.setChecked(True)
        self.log_chk.stateChanged.connect(self._redraw)
        right.addWidget(self.log_chk)
        self.fig = Figure(figsize=(6, 5), tight_layout=True, facecolor="#f5f5f5")
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        right.addWidget(self.canvas, stretch=1)

        outer = QHBoxLayout(self)
        outer.addLayout(ctrl, stretch=1)
        outer.addLayout(right, stretch=2)

        self.point_sig.connect(self._on_point, Qt.ConnectionType.QueuedConnection)
        self.started_sig.connect(self._on_started, Qt.ConnectionType.QueuedConnection)
        self.finished_sig.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)
        self.status_sig.connect(self.status_lbl.setText, Qt.ConnectionType.QueuedConnection)
        self._gui_call_sig.connect(self._on_gui_call, Qt.ConnectionType.QueuedConnection)
        controller.scan_signals.stop_all.connect(self.stop, Qt.ConnectionType.DirectConnection)
        self._redraw()

    # ── GUI marshalling ──────────────────────────────────────────────────────

    def _run_on_gui(self, fn):
        if QThread.currentThread() is self.thread():
            return fn()
        req = {"fn": fn, "done": threading.Event()}
        self._gui_call_sig.emit(req)
        if not req["done"].wait(120.0):
            raise RuntimeError("Timed out waiting for the GUI thread.")
        if "error" in req:
            raise RuntimeError(req["error"])
        return req.get("result")

    @pyqtSlot(object)
    def _on_gui_call(self, req):
        try:
            req["result"] = req["fn"]()
        except Exception as e:
            req["error"] = str(e)
        finally:
            req["done"].set()

    # ── Static controls ──────────────────────────────────────────────────────

    def _busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _apply_ramp_params(self):
        try:
            step = abs(float(self.ramp_step.text()))
            dwell = abs(float(self.ramp_dwell.text())) / 1000.0
        except ValueError:
            return
        if step <= 0:
            return
        self.state.settings["keithley_ramp_step_v"] = step
        self.state.settings["keithley_ramp_dwell_s"] = dwell
        self.controller.save_state()

    def _set_compliance(self, g):
        k = self.k[g]
        if k is None:
            QMessageBox.warning(self, "Not connected", f"{g} gate Keithley is not connected.")
            return
        try:
            k.set_current_compliance(float(self.comp_entry[g].text()))
            self.status_lbl.setText(f"{g} gate compliance set.")
        except Exception as e:
            QMessageBox.warning(self, "Compliance", str(e))

    def _ramp_clicked(self, g):
        if self.k[g] is None:
            QMessageBox.warning(self, "Not connected", f"{g} gate Keithley is not connected.")
            return
        if self._busy():
            QMessageBox.information(self, "Busy", "A gate is already moving — stop it first.")
            return
        try:
            v = float(self.v_entry[g].text())
        except ValueError:
            return
        self._thread = threading.Thread(target=self.set_gate_voltage_blocking, args=(g, v), daemon=True)
        self._thread.start()

    def set_gate_voltage_blocking(self, gate: str, volts: float) -> dict:
        """Ramp one gate (global ramp step/wait, gate current limit enforced)."""
        gate = "top" if str(gate).lower().startswith("top") else "back"
        if self.k[gate] is None:
            return {"error": f"{gate} gate Keithley is not connected"}
        self._stop[0] = False
        self.status_sig.emit(f"Ramping {gate} gate to {volts:g} V…")
        try:
            self.controller.ramp_gate(gate, float(volts), abort=lambda: self._stop[0])
        except Exception as e:
            self.status_sig.emit(f"Ramp stopped: {e}")
            return {"error": str(e)}
        if self._stop[0]:
            self.status_sig.emit("Ramp stopped by user.")
            return {"error": "Ramp stopped by user"}
        i = self.k[gate].read_current()
        self.status_sig.emit(f"{gate} gate at {volts:g} V, I = {i:.3e} A")
        self.controller.log(f"{gate} gate ramped to {volts:g} V (I={i:.3e} A)")
        return {"status": "ok", "gate": gate, "volts": float(volts), "current_a": i}

    # ── Sweep ────────────────────────────────────────────────────────────────

    def _collect(self) -> dict:
        try:
            p = {"gate": self.gate_combo.currentText(),
                 "v_start": float(self.v_start.text()), "v_end": float(self.v_end.text()),
                 "v_step": abs(float(self.v_step.text())),
                 "dwell_s": int(self.dwell_ms.text()) / 1000.0,
                 "i_abort": abs(float(self.i_abort.text())),
                 "down_rate": abs(float(self.down_rate.text()))}
        except ValueError:
            raise ValueError("Sweep parameters are not valid numbers.")
        if p["v_step"] <= 0 or p["i_abort"] <= 0 or p["down_rate"] <= 0:
            raise ValueError("Step, abort current and ramp-down rate must be > 0.")
        if p["v_start"] == p["v_end"]:
            raise ValueError("Start and end voltage are equal.")
        if self.k[p["gate"]] is None:
            raise ValueError(f"{p['gate']} gate Keithley is not connected.")
        return p

    def _start(self):
        if self._busy():
            return
        try:
            p = self._collect()
        except ValueError as e:
            QMessageBox.warning(self, "Input error", str(e))
            return
        self._thread = threading.Thread(target=self._sweep, args=(p,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop[0] = True

    def _sweep(self, p) -> tuple[bool, str, float]:
        k = self.k[p["gate"]]
        other = self.k["back" if p["gate"] == "top" else "top"]
        self._stop[0] = False
        abort = lambda: self._stop[0]
        span = p["v_end"] - p["v_start"]
        n = int(np.floor(abs(span) / p["v_step"] + 1e-9)) + 1
        volts = p["v_start"] + np.sign(span) * p["v_step"] * np.arange(n)
        if abs(volts[-1] - p["v_end"]) > 1e-9:
            volts = np.append(volts, p["v_end"])
        self.started_sig.emit(p["gate"])
        self.controller.log(f"Gate sweep ({p['gate']}): {p['v_start']:g} → {p['v_end']:g} V, "
                            f"step {p['v_step']:g} V, abort |I| ≥ {p['i_abort']:.2e} A")
        aborted, msg, bd = False, "Sweep complete — no breakdown detected.", math.nan
        try:
            try:
                comp = k.get_current_compliance()
            except Exception:
                comp = math.inf
            self.status_sig.emit(f"Ramping to {p['v_start']:g} V…")
            k.ramp_voltage(p["v_start"], step_V=p["v_step"], dwell_s=p["dwell_s"], abort_flag=abort)
            self.status_sig.emit("Sweeping…")
            for v in volts:
                if abort():
                    aborted, msg = True, f"Stopped by user at {v:g} V."
                    break
                i_sw = k.set_voltage_immediate(float(v))
                if p["dwell_s"]:
                    time.sleep(p["dwell_s"])
                i_sw = k.read_current()
                i_ot = other.read_current() if other is not None else math.nan
                i_top, i_back = (i_sw, i_ot) if p["gate"] == "top" else (i_ot, i_sw)
                self.point_sig.emit(float(v), i_top, i_back)
                over = [abs(x) for x in (i_top, i_back) if math.isfinite(x)]
                if over and max(over) >= p["i_abort"]:
                    bd = float(v)
                    msg = (f"Breakdown at {v:g} V — I_top = {i_top:.3e} A, "
                           f"I_back = {i_back:.3e} A (limit {p['i_abort']:.2e} A).")
                    break
                if math.isfinite(i_sw) and abs(i_sw) >= 0.95 * comp and k.in_compliance():
                    bd = float(v)
                    msg = f"Breakdown at {v:g} V — source hit its {comp:.2e} A compliance."
                    break
        except Exception as e:
            aborted, msg = True, f"Sweep error: {e}"
        finally:
            self.status_sig.emit(f"Ramping back to 0 V at {p['down_rate']:g} V/s…")
            try:
                k.ramp_to_zero_fast(p["down_rate"])
            except Exception as e:
                msg += f"  (Ramp back to 0 V FAILED: {e})"
        if math.isfinite(bd):
            self.state.settings["gate_breakdown_voltage"] = bd
        self.controller.save_state()
        self.controller.log(f"Gate sweep: {msg}")
        self.finished_sig.emit(aborted, msg, bd)
        return aborted, msg, bd

    # ── Live display ─────────────────────────────────────────────────────────

    def _on_started(self, gate):
        self._swept = gate
        self.vs, self.i_top, self.i_back = [], [], []
        self.breakdown_v = math.nan
        self.result_lbl.setText("")
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.controller.scan_signals.activate_tab.emit(TAB_NAME)
        self._redraw()

    def _on_point(self, v, it, ib):
        self.vs.append(v); self.i_top.append(it); self.i_back.append(ib)
        self.readout.setText(f"{v:g} V · top {it:.2e} A · back {ib:.2e} A")
        self._redraw()

    def _on_finished(self, aborted, msg, bd):
        self.breakdown_v = bd
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.status_lbl.setText(msg)
        self.result_lbl.setText(f"Breakdown: {bd:g} V" if math.isfinite(bd) else "")
        self._redraw()

    def _draw(self, ax, log):
        v = np.asarray(self.vs, float)
        for ys, lab in ((self.i_top, "Top gate"), (self.i_back, "Back gate")):
            y = np.asarray(ys, float)
            ax.plot(v, np.abs(y) if log else y, "o-", markersize=2, linewidth=1.2, label=lab)
        if log:
            ax.set_yscale("log")
        if math.isfinite(self.breakdown_v):
            ax.axvline(self.breakdown_v, color="#c0392b", linestyle="--")
        ax.set_xlabel(f"{self._swept.capitalize()} gate voltage (V)")
        ax.set_ylabel("|I| (A)" if log else "Current (A)")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left", fontsize=8)

    def _redraw(self):
        self.ax.cla()
        self._draw(self.ax, self.log_chk.isChecked())
        self.canvas.draw_idle()

    # ── Save ─────────────────────────────────────────────────────────────────

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Choose folder", self.folder.text())
        if path:
            self.folder.setText(path)

    def save_data(self, filename: str | None = None) -> str:
        return self._run_on_gui(lambda: self._save_gui(filename))

    def _save_gui(self, filename=None) -> str:
        if not self.vs:
            raise RuntimeError("No sweep data to save — run a sweep first.")
        folder = self.folder.text().strip()
        if filename:
            self.filename.setText(filename.strip())
        base = self.filename.text().strip() or "gate_sweep"
        os.makedirs(folder, exist_ok=True)
        used = {os.path.splitext(f)[0] for f in os.listdir(folder)}
        name, i = base, 1
        while name in used:
            name, i = f"{base}_{i}", i + 1
        self.filename.setText(name)
        txt = os.path.join(folder, name + ".txt")
        self.fig.savefig(os.path.join(folder, name + ".png"), dpi=150)
        bd = f"{self.breakdown_v:g}" if math.isfinite(self.breakdown_v) else "none detected"
        lines = [
            "Gate breakdown sweep — white-light microscope",
            f"Date/Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Swept gate: {self._swept}",
            f"Start V: {self.v_start.text()}  End V: {self.v_end.text()}  Step V: {self.v_step.text()}",
            f"Dwell (ms): {self.dwell_ms.text()}  Abort |I| (A): {self.i_abort.text()}  "
            f"Ramp down (V/s): {self.down_rate.text()}",
            f"Breakdown voltage (V): {bd}",
            "",
            *instrument_state_lines(self.controller),
            "",
            "Columns: V_swept I_top(A) I_back(A)",
        ]
        header = "\n".join("# " + l if l else "#" for l in lines)
        np.savetxt(txt, np.column_stack([self.vs, self.i_top, self.i_back]),
                   header=header, comments="", fmt="%.10g", delimiter="\t", encoding="utf-8")
        self.controller.log(f"Gate sweep saved: {txt}")
        return txt

    def _save(self):
        try:
            path = self._save_gui()
        except Exception as e:
            QMessageBox.information(self, "Save", str(e))
            return
        QMessageBox.information(self, "Saved", f"Saved:\n{path}")

    # ── Agent API ────────────────────────────────────────────────────────────

    def get_settings(self) -> dict:
        def _get():
            out = {"sweep_gate": self.gate_combo.currentText(),
                   "v_start": self.v_start.text(), "v_end": self.v_end.text(),
                   "v_step": self.v_step.text(), "dwell_ms": self.dwell_ms.text(),
                   "abort_current_a": self.i_abort.text(),
                   "ramp_down_v_per_s": self.down_rate.text(),
                   "top_compliance_a": self.comp_entry["top"].text(),
                   "back_compliance_a": self.comp_entry["back"].text(),
                   "log_scale": self.log_chk.isChecked(),
                   "folder": self.folder.text(), "filename": self.filename.text(),
                   "running": self._busy(),
                   "last_breakdown_v": self.breakdown_v if math.isfinite(self.breakdown_v) else None,
                   "gate_current_limit_a_for_scans": self.state.settings.get("gate_current_limit_a")}
            for g, k in self.k.items():
                out[f"{g}_gate_connected"] = k is not None
                if k is not None:
                    try:
                        out[f"{g}_gate_v_now"] = k.get_voltage_setpoint()
                        out[f"{g}_gate_output_on"] = k.is_output_on()
                    except Exception as e:
                        out[f"{g}_gate_v_now"] = f"read failed: {e}"
            return out
        return self._run_on_gui(_get)

    def apply_settings(self, s: dict) -> list[str]:
        def _apply():
            warnings = []
            if "sweep_gate" in s:
                g = str(s["sweep_gate"]).lower()
                if g not in ("top", "back"):
                    warnings.append("sweep_gate must be 'top' or 'back'")
                else:
                    self.gate_combo.setCurrentText(g)
            for key, w in (("v_start", self.v_start), ("v_end", self.v_end),
                           ("v_step", self.v_step), ("dwell_ms", self.dwell_ms),
                           ("abort_current_a", self.i_abort), ("ramp_down_v_per_s", self.down_rate),
                           ("folder", self.folder), ("filename", self.filename)):
                if key in s:
                    w.setText(str(s[key]))
            if "log_scale" in s:
                self.log_chk.setChecked(bool(s["log_scale"]))
            for g in ("top", "back"):
                key = f"{g}_compliance_a"
                if key in s:
                    self.comp_entry[g].setText(str(s[key]))
                    if self.k[g] is None:
                        warnings.append(f"{g} gate not connected — compliance not applied")
                    else:
                        try:
                            self.k[g].set_current_compliance(float(s[key]))
                        except Exception as e:
                            warnings.append(f"{key}: {e}")
            self.controller.scan_signals.activate_tab.emit(TAB_NAME)
            return warnings
        return self._run_on_gui(_apply)

    def run_sweep_blocking(self) -> dict:
        if self._busy():
            return {"error": "The gate is already moving"}
        try:
            p = self._run_on_gui(self._collect)
        except Exception as e:
            return {"error": str(e)}
        self._thread = threading.current_thread()
        try:
            aborted, msg, bd = self._sweep(p)
        finally:
            self._thread = None
        self._run_on_gui(lambda: None)      # let queued points land
        if not self.vs:
            return {"error": msg}
        it, ib = np.asarray(self.i_top, float), np.asarray(self.i_back, float)
        stats = {"message": msg, "aborted": aborted, "swept_gate": p["gate"],
                 "n_points": len(self.vs), "v_last": self.vs[-1],
                 "breakdown_v": bd if math.isfinite(bd) else None,
                 "max_abs_top_current_a": float(f"{np.nanmax(np.abs(it)):.3e}") if np.isfinite(it).any() else None,
                 "max_abs_back_current_a": float(f"{np.nanmax(np.abs(ib)):.3e}") if np.isfinite(ib).any() else None}

        def _png():
            fig = Figure(figsize=(5, 3.5), dpi=90)
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            FigureCanvasAgg(fig)
            self._draw(fig.add_subplot(111), self.log_chk.isChecked())
            fig.tight_layout()
            buf = io.BytesIO(); fig.savefig(buf, format="png")
            return base64.standard_b64encode(buf.getvalue()).decode()
        return {"stats": stats, "png_b64": self._run_on_gui(_png)}
