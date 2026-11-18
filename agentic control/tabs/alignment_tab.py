# tabs/alignment_tab.py
"""
Active stabilisation (feature alignment) — the "Active Stabilization" tab of
the old TwoDscan program.

The stage sweeps slowly across a feature (an electrode) in X and then in Y
while lock-in 1 X is read continuously. Each cut is fitted with a hat
(double sigmoid) or a step (single sigmoid); the fitted centre gives the
feature position.

  Reset origin : record the feature position as the reference.
  Align        : measure again; the drift from the origin becomes the X/Y
                 offset that the controller adds to every later X/Y move.

Offsets and origin live in the shared state, so they are saved with the data.
"""
from __future__ import annotations

import math
import threading
import time

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QPushButton,
    QLineEdit, QLabel, QComboBox, QCheckBox, QMessageBox,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from drivers.ESP301 import x_um_to_raw, y_um_to_raw, x_raw_to_um, y_raw_to_um
from helpers import electrode_fitter

TAB_NAME = "Alignment"
X_CUT_VELOCITY = 0.005    # ESP raw units / s during the X cut
Y_CUT_VELOCITY = 0.0033   # ... and the Y cut
FIT_MODELS = ["double sigmoid (hat)", "single sigmoid (step)"]


class AlignmentTab(QWidget):
    cut_sig     = pyqtSignal(str, object, object, object)   # axis, xs, rs, fit (or None)
    history_sig = pyqtSignal()
    status_sig  = pyqtSignal(str)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.state = controller.state
        self.esp = controller.get_instrument("ESP")
        li = controller.get_instrument("Lockins")
        # Alignment reads lock-in 1; treat the lock-ins as absent without it.
        self.lockins = li if (li is not None and 1 in li.present) else None

        self._busy = threading.Lock()
        self._stop = [False]
        self.x_history: list[float] = []
        self.y_history: list[float] = []
        self.x_rmse: list[float] = []
        self.y_rmse: list[float] = []

        dv = QDoubleValidator(-1e9, 1e9, 6, self)
        st = self.state.settings

        # ── Controls ─────────────────────────────────────────────────────────
        cut_box = QGroupBox("Alignment cuts")
        f = QFormLayout(cut_box)
        self.x_init = QLineEdit(str(st.get("align_x_init_um", 0))); self.x_init.setValidator(dv)
        self.y_init = QLineEdit(str(st.get("align_y_init_um", 0))); self.y_init.setValidator(dv)
        self.x_dir = QComboBox(); self.x_dir.addItems(["right", "left"])
        self.y_dir = QComboBox(); self.y_dir.addItems(["down", "up"])
        self.x_dist = QLineEdit(str(st.get("align_x_dist_um", 10))); self.x_dist.setValidator(dv)
        self.y_dist = QLineEdit(str(st.get("align_y_dist_um", 10))); self.y_dist.setValidator(dv)
        self.fit_model = QComboBox(); self.fit_model.addItems(FIT_MODELS)
        self.hat_width = QLineEdit("5"); self.hat_width.setValidator(dv)
        self.hat_width.setToolTip("Starting guess for the hat width (µm) in the double-sigmoid fit.")
        self.settle_s = QLineEdit("3"); self.settle_s.setValidator(dv)
        self.settle_s.setToolTip("Wait after aligning before measuring again (lets the lock-in settle).")
        f.addRow("X initial pos (µm):", self.x_init)
        f.addRow("Y initial pos (µm):", self.y_init)
        f.addRow("X cut direction:", self.x_dir)
        f.addRow("Y cut direction:", self.y_dir)
        f.addRow("X distance (µm):", self.x_dist)
        f.addRow("Y distance (µm):", self.y_dist)
        f.addRow("Fit model:", self.fit_model)
        f.addRow("Hat width guess (µm):", self.hat_width)
        f.addRow("Settle after align (s):", self.settle_s)

        tgt_box = QGroupBox("After aligning")
        tf = QFormLayout(tgt_box)
        self.move_after = QCheckBox("Move to target position")
        self.x_target = QLineEdit("0"); self.x_target.setValidator(dv)
        self.y_target = QLineEdit("0"); self.y_target.setValidator(dv)
        tf.addRow(self.move_after)
        tf.addRow("X target (µm):", self.x_target)
        tf.addRow("Y target (µm):", self.y_target)

        btns = QHBoxLayout()
        self.origin_btn = QPushButton("Reset origin")
        self.align_btn = QPushButton("Align")
        self.reset_off_btn = QPushButton("Reset offsets")
        self.stop_btn = QPushButton("Stop")
        for b in (self.origin_btn, self.align_btn, self.reset_off_btn, self.stop_btn):
            btns.addWidget(b)
        self.origin_btn.clicked.connect(lambda: self._start(True))
        self.align_btn.clicked.connect(lambda: self._start(False))
        self.reset_off_btn.clicked.connect(self._reset_offsets)
        self.stop_btn.clicked.connect(self.stop)

        self.info_lbl = QLabel()
        self.info_lbl.setStyleSheet("font-family:Consolas; color:#333;")
        self.status_lbl = QLabel("Idle.")
        self.status_lbl.setWordWrap(True)

        ctrl = QVBoxLayout()
        ctrl.addWidget(cut_box)
        ctrl.addWidget(tgt_box)
        ctrl.addLayout(btns)
        ctrl.addWidget(self.info_lbl)
        ctrl.addWidget(self.status_lbl)
        ctrl.addStretch(1)

        # ── Plots ────────────────────────────────────────────────────────────
        self.fig = Figure(figsize=(7, 6), tight_layout=True, facecolor="#f5f5f5")
        self.ax = self.fig.subplots(2, 2)
        self.canvas = FigureCanvas(self.fig)

        outer = QHBoxLayout(self)
        outer.addLayout(ctrl, stretch=1)
        outer.addWidget(self.canvas, stretch=3)

        self.cut_sig.connect(self._on_cut, Qt.ConnectionType.QueuedConnection)
        self.history_sig.connect(self._on_history, Qt.ConnectionType.QueuedConnection)
        self.status_sig.connect(self.status_lbl.setText, Qt.ConnectionType.QueuedConnection)
        controller.scan_signals.stop_all.connect(self.stop, Qt.ConnectionType.DirectConnection)

        self._draw_cut("X", [], [], None)
        self._draw_cut("Y", [], [], None)
        self._on_history()

    # ── Settings ─────────────────────────────────────────────────────────────

    def _params(self) -> dict:
        try:
            return {
                "x0": float(self.x_init.text()), "y0": float(self.y_init.text()),
                "x_dist": abs(float(self.x_dist.text())), "y_dist": abs(float(self.y_dist.text())),
                "x_dir": self.x_dir.currentText(), "y_dir": self.y_dir.currentText(),
                "single": self.fit_model.currentIndex() == 1,
                "hat": float(self.hat_width.text()),
                "settle_s": max(0.0, float(self.settle_s.text())),
                "move_after": self.move_after.isChecked(),
                "x_target": float(self.x_target.text()), "y_target": float(self.y_target.text()),
            }
        except ValueError:
            raise ValueError("Alignment settings are not valid numbers.")

    def get_settings(self) -> dict:
        st = self.state.settings
        return {
            "x_init_um": self.x_init.text(), "y_init_um": self.y_init.text(),
            "x_direction": self.x_dir.currentText(), "y_direction": self.y_dir.currentText(),
            "x_distance_um": self.x_dist.text(), "y_distance_um": self.y_dist.text(),
            "fit_model": self.fit_model.currentText(), "fit_models_available": FIT_MODELS,
            "hat_width_um": self.hat_width.text(),
            "settle_s": self.settle_s.text(),
            "move_to_target": self.move_after.isChecked(),
            "x_target_um": self.x_target.text(), "y_target_um": self.y_target.text(),
            "x_origin_um": st.get("x_origin_um"), "y_origin_um": st.get("y_origin_um"),
            "x_offset_um": st.get("x_offset_um"), "y_offset_um": st.get("y_offset_um"),
            "alignments_this_session": len(self.x_history),
            "running": self._busy.locked(),
        }

    def apply_settings(self, s: dict) -> list[str]:
        warnings = []
        for key, w in (("x_init_um", self.x_init), ("y_init_um", self.y_init),
                       ("x_distance_um", self.x_dist), ("y_distance_um", self.y_dist),
                       ("hat_width_um", self.hat_width), ("settle_s", self.settle_s),
                       ("x_target_um", self.x_target), ("y_target_um", self.y_target)):
            if key in s:
                w.setText(str(s[key]))
        for key, combo in (("x_direction", self.x_dir), ("y_direction", self.y_dir),
                           ("fit_model", self.fit_model)):
            if key in s:
                idx = combo.findText(str(s[key]))
                if idx < 0:
                    warnings.append(f"'{s[key]}' is not valid for {key}: "
                                    f"{[combo.itemText(i) for i in range(combo.count())]}")
                else:
                    combo.setCurrentIndex(idx)
        if "move_to_target" in s:
            self.move_after.setChecked(bool(s["move_to_target"]))
        self.controller.scan_signals.activate_tab.emit(TAB_NAME)
        return warnings

    # ── Buttons ──────────────────────────────────────────────────────────────

    def _start(self, set_origin: bool):
        if self.esp is None or self.lockins is None:
            QMessageBox.warning(self, "Not connected", "Alignment needs the ESP301 and lock-in 1.")
            return
        if self._busy.locked():
            QMessageBox.information(self, "Busy", "An alignment is already running.")
            return
        threading.Thread(target=self.run_alignment_blocking, args=(set_origin,),
                         daemon=True).start()

    def stop(self):
        self._stop[0] = True

    def _reset_offsets(self):
        self.controller.reset_offsets()
        self.controller.save_state()
        self._on_history()

    # ── The alignment itself ─────────────────────────────────────────────────

    def _fit(self, xs, rs, p):
        if len(xs) < 5:
            return None
        try:
            if p["single"]:
                out = electrode_fitter.fit_single_sigmoid(xs, rs)
            else:
                out = electrode_fitter.fit_double_sigmoid(xs, rs, p["hat"])
        except Exception as e:
            self.controller.log(f"Alignment fit error: {e}")
            return None
        params, rmse, fit, popt, pcov, center = out
        if params is None:
            return None
        return float(center), float(rmse), np.asarray(fit)

    def run_alignment_blocking(self, set_origin: bool = False, stop_flag=None) -> dict:
        """Run both cuts and update origin/offsets. Safe to call from any thread.

        stop_flag (a one-element list) lets a running 2D scan abort it.
        """
        if self.esp is None or self.lockins is None:
            return {"error": "Alignment needs the ESP301 and lock-in 1"}
        if not self._busy.acquire(blocking=False):
            return {"error": "An alignment is already running"}
        self._stop[0] = False
        abort = (lambda: self._stop[0] or bool(stop_flag and stop_flag[0]))
        try:
            p = self._params()
            st = self.state.settings
            ox, oy = float(st.get("x_offset_um", 0.0)), float(st.get("y_offset_um", 0.0))
            self.controller.scan_signals.activate_tab.emit(TAB_NAME)
            self.status_sig.emit("Moving to the start position…")
            self.controller.move_xy(p["x0"], p["y0"], abort)

            x1 = p["x0"] + (p["x_dist"] if p["x_dir"] == "right" else -p["x_dist"])
            y1 = p["y0"] + (p["y_dist"] if p["y_dir"] == "up" else -p["y_dist"])
            read = lambda: self.lockins.read_x(1)

            # X cut
            self.status_sig.emit("X cut…")
            xs, rx = self.esp.streamed_cut(
                1, x_um_to_raw(x1 + ox), X_CUT_VELOCITY, read,
                to_user=lambda raw: x_raw_to_um(raw) - ox,
                on_point=lambda a, b: self.cut_sig.emit("X", list(a), list(b), None),
                abort_flag=abort)
            if abort():
                return {"error": "Alignment stopped by user"}
            fx = self._fit(xs, rx, p)
            self.cut_sig.emit("X", xs, rx, fx[2] if fx else None)

            # Y cut, from the X start position with the OLD offset (as before)
            self.status_sig.emit("Y cut…")
            self.controller.move_x(p["x0"], abort)
            ys, ry = self.esp.streamed_cut(
                2, y_um_to_raw(y1 + oy), Y_CUT_VELOCITY, read,
                to_user=lambda raw: y_raw_to_um(raw) - oy,
                on_point=lambda a, b: self.cut_sig.emit("Y", list(a), list(b), None),
                abort_flag=abort)
            if abort():
                return {"error": "Alignment stopped by user"}
            fy = self._fit(ys, ry, p)
            self.cut_sig.emit("Y", ys, ry, fy[2] if fy else None)

            result = {"x_fit_ok": fx is not None, "y_fit_ok": fy is not None}
            if set_origin:
                if fx is None or fy is None:
                    return {"error": "Fit failed — origin not changed", **result}
                st["x_origin_um"], st["y_origin_um"] = fx[0], fy[0]
                self.x_history.clear(); self.y_history.clear()
                self.x_rmse.clear(); self.y_rmse.clear()
                self.controller.log(f"Alignment origin set to ({fx[0]:.3f}, {fy[0]:.3f}) µm")
                result.update(origin_um=[fx[0], fy[0]])
            else:
                if fx is not None:
                    st["x_offset_um"] = ox - float(st.get("x_origin_um", 0.0)) + fx[0]
                if fy is not None:
                    st["y_offset_um"] = oy - float(st.get("y_origin_um", 0.0)) + fy[0]
                self.x_history.append(float(st["x_offset_um"]))
                self.y_history.append(float(st["y_offset_um"]))
                self.x_rmse.append(fx[1] if fx else 0.0)
                self.y_rmse.append(fy[1] if fy else 0.0)
                self.controller.log(
                    f"Aligned: offsets ({st['x_offset_um']:.3f}, {st['y_offset_um']:.3f}) µm")
            result.update(
                x_center_um=fx[0] if fx else None, y_center_um=fy[0] if fy else None,
                x_offset_um=st["x_offset_um"], y_offset_um=st["y_offset_um"],
                x_origin_um=st.get("x_origin_um"), y_origin_um=st.get("y_origin_um"),
                drift_um=math.hypot(st["x_offset_um"], st["y_offset_um"]))

            if not set_origin and p["move_after"]:
                self.status_sig.emit("Moving to target…")
                self.controller.move_xy(p["x_target"], p["y_target"], abort)
            if not set_origin and p["settle_s"] > 0:
                time.sleep(p["settle_s"])
            self.controller.save_state()
            self.history_sig.emit()
            self.status_sig.emit("Origin set." if set_origin else "Aligned.")
            return result
        except Exception as e:
            self.status_sig.emit(f"Alignment error: {e}")
            return {"error": f"Alignment failed: {e}"}
        finally:
            self._busy.release()

    # ── Plotting (GUI thread) ────────────────────────────────────────────────

    def _draw_cut(self, axis, xs, rs, fit):
        ax = self.ax[0, 0] if axis == "X" else self.ax[0, 1]
        ax.cla()
        ax.plot(xs, rs, color="#2980b9")
        if fit is not None and len(fit) == len(xs):
            ax.plot(xs, fit, color="#c0392b")
        ax.set_title(f"{axis} cut for alignment", fontsize=9)
        ax.set_xlabel(f"{axis} position (µm)", fontsize=8)
        ax.set_ylabel("Lock-in 1 X", fontsize=8)
        ax.tick_params(labelsize=7)

    def _on_cut(self, axis, xs, rs, fit):
        self._draw_cut(axis, xs, rs, fit)
        self.canvas.draw_idle()

    def _on_history(self):
        st = self.state.settings
        ax = self.ax[1, 0]
        ax.cla()
        ax.plot(self.x_rmse, label="x fit error")
        ax.plot(self.y_rmse, label="y fit error")
        ax.set_title("Fit errors (RMSE)", fontsize=9)
        ax.set_xlabel("Alignment number", fontsize=8)
        ax.legend(fontsize=7)
        ax.tick_params(labelsize=7)
        ax = self.ax[1, 1]
        ax.cla()
        ax.plot(self.x_history, self.y_history, "o-", markersize=3)
        ax.set_title("Displacement from origin (µm)", fontsize=9)
        ax.set_xlabel("X offset", fontsize=8)
        ax.set_ylabel("Y offset", fontsize=8)
        ax.tick_params(labelsize=7)
        self.canvas.draw_idle()
        xo, yo = float(st.get("x_offset_um", 0)), float(st.get("y_offset_um", 0))
        self.info_lbl.setText(
            f"Origin   : ({float(st.get('x_origin_um', 0)):.3f}, {float(st.get('y_origin_um', 0)):.3f}) µm\n"
            f"Offsets  : ({xo:.3f}, {yo:.3f}) µm\n"
            f"Drift    : {math.hypot(xo, yo):.3f} µm\n"
            f"Aligns   : {len(self.x_history)}")
