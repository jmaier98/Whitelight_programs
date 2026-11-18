# tabs/two_d_scan_tab.py
"""
2D scan — the "2D Scan" tab of the old TwoDscan program.

X is the fast axis, Y the slow axis. Any axis can be scanned against any
other (stage X/Y, delay, Z, waveplates, rotation mounts, wavelength, gates,
gate line cut). Every point stores up to 9 data channels.

Display (as before): two images (choose the channel for each), an X linecut
and a Y linecut through the cursor. Click an image to move the cursor.

Saved file format matches the old program so existing analysis scripts
(datavisualizerv2 etc.) still load it with np.loadtxt(comments="#"):
    columns  Scan_Number  Y  X  data1 … data9
with every header line starting with '#'. The header also records every
instrument setting from the shared state.
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
from PyQt6.QtGui import QDoubleValidator, QIntValidator
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QGroupBox,
    QPushButton, QLineEdit, QLabel, QComboBox, QCheckBox, QMessageBox,
    QFileDialog, QTextEdit, QScrollArea, QFrame,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from controller import N_CH
from drivers.Keithley2400 import GateCurrentLimit
from helpers.state_header import instrument_state_lines

TAB_NAME = "2D Scan"
GATE_CUT = "Gate line cut (TG, BG)"


def _parse_list(text: str) -> np.ndarray:
    vals = [v for v in text.replace(";", ",").split(",") if v.strip()]
    return np.asarray([float(v) for v in vals], float)


def _axis_values(start: float, end: float, step: float) -> np.ndarray:
    step = abs(step)
    if step == 0:
        raise ValueError("step must be > 0")
    if start == end:
        return np.asarray([start], float)
    n = int(np.floor(abs(end - start) / step + 1e-9)) + 1
    return start + np.sign(end - start) * step * np.arange(n)


class TwoDScanTab(QWidget):
    point_sig     = pyqtSignal(int, int, int, object)   # scan, ix, iy, values
    started_sig   = pyqtSignal(object)                  # params
    scan_done_sig = pyqtSignal(int)
    finished_sig  = pyqtSignal(bool, str)               # aborted, message
    status_sig    = pyqtSignal(str)
    _gui_call_sig = pyqtSignal(object)

    def __init__(self, controller, alignment_tab=None):
        super().__init__()
        self.controller = controller
        self.state = controller.state
        self.alignment_tab = alignment_tab
        self.AXES = controller.AXES
        self.MEASUREMENTS = controller.MEASUREMENTS

        self._stop = [False]
        self._thread: threading.Thread | None = None
        self.data: np.ndarray | None = None      # (n_avg, Ny, Nx, N_CH)
        self.xs = np.arange(0, 11, 1.0)
        self.ys = np.arange(0, 6, 1.0)
        self._scan_idx = 0
        self._row = 0
        self._cursor = (0, 0)                    # (ix, iy)
        self._cursor_img = 0                     # which image the linecuts follow
        self._last_params: dict | None = None

        dv = QDoubleValidator(-1e300, 1e300, 9, self)
        dv_pos = QDoubleValidator(0.0, 1e300, 9, self)

        # ── Axes / measurement ───────────────────────────────────────────────
        axes_box = QGroupBox("Axes / measurement")
        af = QFormLayout(axes_box)
        self.x_axis = QComboBox(); self.x_axis.addItems(self.AXES)
        self.y_axis = QComboBox(); self.y_axis.addItems(self.AXES)
        for combo, want in ((self.x_axis, "X pos (µm)"), (self.y_axis, "Y pos (µm)")):
            if combo.findText(want) >= 0:
                combo.setCurrentText(want)
        self.meas = QComboBox(); self.meas.addItems(self.MEASUREMENTS)
        af.addRow("X axis (fast):", self.x_axis)
        af.addRow("Y axis (slow):", self.y_axis)
        af.addRow("Measurement:", self.meas)

        # ── Ranges ───────────────────────────────────────────────────────────
        rng_box = QGroupBox("Range & averages")
        rf = QFormLayout(rng_box)
        self.x_start = QLineEdit("0");  self.x_start.setValidator(dv)
        self.x_end   = QLineEdit("10"); self.x_end.setValidator(dv)
        self.x_step  = QLineEdit("1");  self.x_step.setValidator(dv_pos)
        self.y_start = QLineEdit("0");  self.y_start.setValidator(dv)
        self.y_end   = QLineEdit("5");  self.y_end.setValidator(dv)
        self.y_step  = QLineEdit("1");  self.y_step.setValidator(dv_pos)
        self.averages = QLineEdit("1"); self.averages.setValidator(QIntValidator(1, 100000, self))
        self.wait_s = QLineEdit("0.5"); self.wait_s.setValidator(dv_pos)
        rf.addRow("X start:", self.x_start)
        rf.addRow("X end:", self.x_end)
        rf.addRow("X step:", self.x_step)
        rf.addRow("Y start:", self.y_start)
        rf.addRow("Y end:", self.y_end)
        rf.addRow("Y step:", self.y_step)
        rf.addRow("Averages (# scans):", self.averages)
        rf.addRow("Wait per point (s):", self.wait_s)

        # ── Custom values / gate line cut ────────────────────────────────────
        cust_box = QGroupBox("Custom values / gate line cut")
        cf = QFormLayout(cust_box)
        self.custom_x = QCheckBox("Use custom X values")
        self.custom_x0 = QLineEdit("1,0.5,0.25,0,-1")
        self.custom_x2 = QLineEdit("1,0.5,0.25,0,-1")
        self.custom_y = QCheckBox("Use custom Y values")
        self.custom_y0 = QLineEdit("1,0.5,0.25,0,-1")
        self.custom_y2 = QLineEdit("1,0.5,0.25,0,-1")
        self.bg_start = QLineEdit("0"); self.bg_start.setValidator(dv)
        self.bg_end = QLineEdit("0"); self.bg_end.setValidator(dv)
        cf.addRow(self.custom_x)
        cf.addRow("X values:", self.custom_x0)
        cf.addRow("X back-gate values:", self.custom_x2)
        cf.addRow(self.custom_y)
        cf.addRow("Y values:", self.custom_y0)
        cf.addRow("Y back-gate values:", self.custom_y2)
        bg_row = QHBoxLayout(); bg_row.addWidget(self.bg_start); bg_row.addWidget(self.bg_end)
        cf.addRow("Line cut BG start : end:", bg_row)
        cust_box.setToolTip(
            f"'{GATE_CUT}': the axis values are the top gate; the back gate runs from "
            "BG start to BG end over the same points (or uses the back-gate list when "
            "custom values are on).")

        # ── Alignment during scan ────────────────────────────────────────────
        al_box = QGroupBox("Alignment during scan")
        alf = QFormLayout(al_box)
        self.align_each_scan = QCheckBox("Align before each scan")
        self.align_rows = QCheckBox("Align every N rows")
        self.align_n = QLineEdit("1"); self.align_n.setValidator(QIntValidator(1, 100000, self))
        alf.addRow(self.align_each_scan)
        alf.addRow(self.align_rows, self.align_n)

        # ── Display ──────────────────────────────────────────────────────────
        disp_box = QGroupBox("Display")
        df = QFormLayout(disp_box)
        self.plot1 = QComboBox(); self.plot2 = QComboBox()
        self.show_avg = QCheckBox("Display average of scans"); self.show_avg.setChecked(True)
        df.addRow("Image 1:", self.plot1)
        df.addRow("Image 2:", self.plot2)
        df.addRow(self.show_avg)
        self.goto_btn = QPushButton("Move axes to cursor")
        self.goto_btn.clicked.connect(self._goto_cursor)
        self.cursor_lbl = QLabel("Cursor: –")
        df.addRow(self.goto_btn)
        df.addRow(self.cursor_lbl)

        # ── Metadata ─────────────────────────────────────────────────────────
        meta_box = QGroupBox("Metadata")
        mf = QFormLayout(meta_box)
        self.device = QLineEdit("Device1")
        self.pump_power = QLineEdit("N/A")
        self.pump_wl = QLineEdit("650 nm")
        self.probe_power = QLineEdit("N/A")
        self.probe_wl = QLineEdit("N/A")
        self.notes = QTextEdit(); self.notes.setFixedHeight(60)
        mf.addRow("Device:", self.device)
        mf.addRow("Pump power:", self.pump_power)
        mf.addRow("Pump wavelength:", self.pump_wl)
        mf.addRow("Probe power:", self.probe_power)
        mf.addRow("Probe wavelength:", self.probe_wl)
        mf.addRow("Notes:", self.notes)

        # ── Save ─────────────────────────────────────────────────────────────
        save_box = QGroupBox("File saving")
        sg = QGridLayout(save_box)
        self.folder = QLineEdit(os.path.expanduser("~/two_d_scans"))
        self.filename = QLineEdit("scan2d_data")
        browse = QPushButton("Browse…"); browse.clicked.connect(self._browse)
        self.autosave = QCheckBox("Autosave when done"); self.autosave.setChecked(True)
        self.save_pic = QCheckBox("Save picture"); self.save_pic.setChecked(True)
        self.save_btn = QPushButton("Save data"); self.save_btn.clicked.connect(self._save)
        sg.addWidget(QLabel("Folder:"), 0, 0); sg.addWidget(self.folder, 0, 1); sg.addWidget(browse, 0, 2)
        sg.addWidget(QLabel("File (no ext):"), 1, 0); sg.addWidget(self.filename, 1, 1)
        sg.addWidget(self.save_btn, 1, 2)
        sg.addWidget(self.autosave, 2, 0, 1, 2); sg.addWidget(self.save_pic, 2, 2)

        # ── Run ──────────────────────────────────────────────────────────────
        self.start_btn = QPushButton("Start scan"); self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("Stop scan"); self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setEnabled(False)
        run_row = QHBoxLayout(); run_row.addWidget(self.start_btn); run_row.addWidget(self.stop_btn)
        self.progress_lbl = QLabel("Scan – · row – · col –")
        self.status_lbl = QLabel("Idle."); self.status_lbl.setWordWrap(True)

        ctrl_w = QWidget()
        ctrl = QVBoxLayout(ctrl_w)
        for w in (axes_box, rng_box, cust_box, al_box, disp_box, meta_box, save_box):
            ctrl.addWidget(w)
        ctrl.addLayout(run_row)
        ctrl.addWidget(self.progress_lbl)
        ctrl.addWidget(self.status_lbl)
        ctrl.addStretch(1)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame); scroll.setWidget(ctrl_w)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(ctrl_w.sizeHint().width() + 20)

        # ── Plots ────────────────────────────────────────────────────────────
        self.fig = Figure(figsize=(9, 8), tight_layout=True, facecolor="#f5f5f5")
        self.ax = self.fig.subplots(2, 2)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.mpl_connect("button_press_event", self._on_click)
        self._img = [None, None]
        self._cbar = [None, None]

        outer = QHBoxLayout(self)
        outer.addWidget(scroll, stretch=0)
        outer.addWidget(self.canvas, stretch=1)

        # ── Signals ──────────────────────────────────────────────────────────
        self.meas.currentIndexChanged.connect(self._refresh_channel_names)
        self.plot1.currentIndexChanged.connect(self._redraw)
        self.plot2.currentIndexChanged.connect(self._redraw)
        self.show_avg.stateChanged.connect(self._redraw)
        self.point_sig.connect(self._on_point, Qt.ConnectionType.QueuedConnection)
        self.started_sig.connect(self._on_started, Qt.ConnectionType.QueuedConnection)
        self.scan_done_sig.connect(self._on_scan_done, Qt.ConnectionType.QueuedConnection)
        self.finished_sig.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)
        self.status_sig.connect(self.status_lbl.setText, Qt.ConnectionType.QueuedConnection)
        self._gui_call_sig.connect(self._on_gui_call, Qt.ConnectionType.QueuedConnection)
        controller.scan_signals.stop_all.connect(self.stop, Qt.ConnectionType.DirectConnection)

        self._refresh_channel_names()
        self.plot2.setCurrentIndex(2)
        self._redraw()

    # ── GUI-thread marshalling (agent calls arrive on another thread) ────────

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

    # ── Channel names ────────────────────────────────────────────────────────

    def _channel_names(self, meas: str | None = None) -> list[str]:
        cols = self.controller.measurement_columns(meas or self.meas.currentText())
        return [f"data{i + 1}: {c}" if not c.startswith("data") else c for i, c in enumerate(cols)]

    def _refresh_channel_names(self):
        names = self._channel_names()
        for combo in (self.plot1, self.plot2):
            i = combo.currentIndex()
            combo.blockSignals(True)
            combo.clear(); combo.addItems(names)
            combo.setCurrentIndex(max(0, i))
            combo.blockSignals(False)
        self._redraw()

    # ── Parameters ───────────────────────────────────────────────────────────

    def _collect(self) -> dict:
        """Read and validate every field. Raises ValueError with a clear message."""
        x_axis, y_axis = self.x_axis.currentText(), self.y_axis.currentText()
        meas = self.meas.currentText()
        if x_axis not in self.AXES or y_axis not in self.AXES:
            raise ValueError("Choose an X and a Y axis.")
        if meas not in self.MEASUREMENTS:
            raise ValueError("Choose a measurement.")
        try:
            if self.custom_x.isChecked():
                xs = _parse_list(self.custom_x0.text())
            else:
                xs = _axis_values(float(self.x_start.text()), float(self.x_end.text()),
                                  float(self.x_step.text()))
            if self.custom_y.isChecked():
                ys = _parse_list(self.custom_y0.text())
            else:
                ys = _axis_values(float(self.y_start.text()), float(self.y_end.text()),
                                  float(self.y_step.text()))
            n_avg = int(self.averages.text())
            wait = float(self.wait_s.text())
            align_n = max(1, int(self.align_n.text()))
        except ValueError as e:
            raise ValueError(f"Range / averages / wait are not valid: {e}")
        if len(xs) == 0 or len(ys) == 0:
            raise ValueError("Axis value lists are empty.")
        if n_avg < 1:
            raise ValueError("Averages must be at least 1.")

        def _second(axis, vals, custom_chk, custom2):
            if axis != GATE_CUT:
                return [None] * len(vals)
            if custom_chk.isChecked():
                v2 = _parse_list(custom2.text())
                if len(v2) != len(vals):
                    raise ValueError("Back-gate list must be as long as the top-gate list.")
                return list(v2)
            return list(np.linspace(float(self.bg_start.text()), float(self.bg_end.text()), len(vals)))

        return {
            "x_axis": x_axis, "y_axis": y_axis, "measurement": meas,
            "xs": xs, "ys": ys,
            "xs2": _second(x_axis, xs, self.custom_x, self.custom_x2),
            "ys2": _second(y_axis, ys, self.custom_y, self.custom_y2),
            "n_avg": n_avg, "wait_s": max(0.0, wait),
            "align_each_scan": self.align_each_scan.isChecked(),
            "align_rows": self.align_rows.isChecked(), "align_n": align_n,
            "autosave": self.autosave.isChecked(),
        }

    # ── Running ──────────────────────────────────────────────────────────────

    def _busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _start(self):
        if self._busy():
            return
        try:
            p = self._collect()
        except ValueError as e:
            QMessageBox.warning(self, "Input error", str(e))
            return
        self._thread = threading.Thread(target=self._run, args=(p,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop[0] = True

    def _align(self, p) -> str | None:
        """Run an alignment mid-scan. Returns an error message, or None."""
        if self.alignment_tab is None:
            return "Alignment tab not available"
        res = self.alignment_tab.run_alignment_blocking(False, stop_flag=self._stop)
        self.controller.scan_signals.activate_tab.emit(TAB_NAME)
        if "error" in res and not self._stop[0]:
            self.controller.log(f"Alignment during scan failed: {res['error']} — continuing")
        return None

    def _run(self, p: dict) -> tuple[bool, str]:
        """The scan loop. Runs in a worker thread (GUI) or the agent thread."""
        self._stop[0] = False
        abort = lambda: self._stop[0]
        set_x, set_y = self.AXES[p["x_axis"]], self.AXES[p["y_axis"]]
        measure = self.MEASUREMENTS[p["measurement"]]
        xs, ys = p["xs"], p["ys"]
        self.started_sig.emit(p)
        self.controller.log(
            f"2D scan: X={p['x_axis']} ({len(xs)}) Y={p['y_axis']} ({len(ys)}) "
            f"meas={p['measurement']} avg={p['n_avg']}")
        aborted, msg = False, "2D scan complete."
        try:
            for s in range(p["n_avg"]):
                if abort():
                    break
                if p["align_each_scan"]:
                    self._align(p)
                for iy in range(len(ys)):
                    if abort():
                        break
                    if p["align_rows"] and iy % p["align_n"] == 0:
                        self._align(p)
                    set_y(float(ys[iy]), p["ys2"][iy], abort)
                    for ix in range(len(xs)):
                        if abort():
                            break
                        set_x(float(xs[ix]), p["xs2"][ix], abort)
                        if p["wait_s"]:
                            time.sleep(p["wait_s"])
                        if abort():
                            break
                        vals = measure(p["wait_s"], abort)
                        vals = [float(v) if v is not None else math.nan for v in vals]
                        self.point_sig.emit(s, ix, iy, tuple((vals + [math.nan] * N_CH)[:N_CH]))
                if not abort():
                    self.scan_done_sig.emit(s + 1)
            if abort():
                aborted, msg = True, "Scan stopped by user."
        except GateCurrentLimit as e:
            aborted, msg = True, f"Scan stopped: {e}"
        except Exception as e:
            aborted, msg = True, f"Scan error: {type(e).__name__}: {e}"
        self.controller.save_state()
        self.controller.log(f"2D scan finished: {msg}")
        self.finished_sig.emit(aborted, msg)
        return aborted, msg

    # ── Live updates (GUI thread) ────────────────────────────────────────────

    def _on_started(self, p):
        self._last_params = p
        self.xs, self.ys = np.asarray(p["xs"], float), np.asarray(p["ys"], float)
        self.data = np.full((p["n_avg"], len(self.ys), len(self.xs), N_CH), np.nan)
        self._scan_idx, self._row = 0, 0
        self._cursor = (0, 0)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_lbl.setText("Scanning…")
        self.controller.scan_signals.activate_tab.emit(TAB_NAME)
        self._redraw()

    def _on_point(self, s, ix, iy, vals):
        if self.data is None or s >= self.data.shape[0]:
            return
        self.data[s, iy, ix, :] = vals
        self._scan_idx, self._row = s, iy
        self.progress_lbl.setText(f"Scan {s + 1}/{self.data.shape[0]} · row {iy} · col {ix}")
        self._redraw()

    def _on_scan_done(self, n):
        self.status_lbl.setText(f"Completed scan {n}.")

    def _on_finished(self, aborted, msg):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_lbl.setText(msg)
        self._redraw()
        if self.autosave.isChecked() and self.data is not None and np.isfinite(self.data).any():
            try:
                path = self._save_gui()
                self.status_lbl.setText(f"{msg}  Saved {os.path.basename(path)}.")
            except Exception as e:
                self.status_lbl.setText(f"{msg}  Autosave failed: {e}")

    # ── Plotting ─────────────────────────────────────────────────────────────

    def _display(self) -> np.ndarray:
        if self.data is None:
            return np.full((len(self.ys), len(self.xs), N_CH), np.nan)
        if self.show_avg.isChecked():
            with np.errstate(invalid="ignore"), _quiet():
                return np.nanmean(self.data[: self._scan_idx + 1], axis=0)
        return self.data[self._scan_idx]

    def _extent(self):
        def edges(v):
            if len(v) == 1:
                return v[0] - 0.5, v[0] + 0.5
            d = (v[1] - v[0]) / 2
            return v[0] - d, v[-1] + d
        x0, x1 = edges(self.xs); y0, y1 = edges(self.ys)
        return [x0, x1, y0, y1]

    def _redraw(self):
        if not hasattr(self, "ax"):
            return
        d = self._display()
        chans = (max(0, self.plot1.currentIndex()), max(0, self.plot2.currentIndex()))
        names = [self.plot1.currentText(), self.plot2.currentText()]
        x_lab, y_lab = self.x_axis.currentText(), self.y_axis.currentText()
        if self._last_params:
            x_lab, y_lab = self._last_params["x_axis"], self._last_params["y_axis"]
        for k, (ax, cmap) in enumerate(((self.ax[0, 0], "bwr"), (self.ax[1, 1], "viridis"))):
            img = d[:, :, chans[k]]
            vals = img[np.isfinite(img)]
            lo, hi = (float(vals.min()), float(vals.max())) if vals.size else (0.0, 1.0)
            if lo == hi:
                lo, hi = lo - 0.5, hi + 0.5
            if self._img[k] is None:
                self._img[k] = ax.imshow(img, origin="lower", cmap=cmap, aspect="auto",
                                         extent=self._extent())
                self._cbar[k] = self.fig.colorbar(self._img[k], ax=ax)
            else:
                self._img[k].set_data(img)
                self._img[k].set_extent(self._extent())
            self._img[k].set_clim(lo, hi)
            ax.set_title(names[k], fontsize=9)
            ax.set_xlabel(x_lab, fontsize=8); ax.set_ylabel(y_lab, fontsize=8)
            ax.tick_params(labelsize=7)

        ch = chans[self._cursor_img]
        ix = min(self._cursor[0], len(self.xs) - 1)
        iy = min(self._cursor[1], len(self.ys) - 1)
        ax = self.ax[0, 1]; ax.cla()
        ax.plot(self.xs, d[iy, :, ch], label=f"row {iy}")
        if self._row > 0:
            with np.errstate(invalid="ignore"), _quiet():
                ax.plot(self.xs, np.nanmean(d[: self._row, :, ch], axis=0), label="mean of rows")
            ax.legend(fontsize=7)
        ax.set_title("X linecut", fontsize=9); ax.set_xlabel(x_lab, fontsize=8)
        ax.tick_params(labelsize=7)
        ax = self.ax[1, 0]; ax.cla()
        ax.plot(self.ys, d[:, ix, ch])
        ax.set_title("Y linecut", fontsize=9); ax.set_xlabel(y_lab, fontsize=8)
        ax.tick_params(labelsize=7)
        self.canvas.draw_idle()

    def _on_click(self, event):
        if event.inaxes not in (self.ax[0, 0], self.ax[1, 1]) or event.xdata is None:
            return
        self._cursor_img = 0 if event.inaxes is self.ax[0, 0] else 1
        ix = int(np.abs(self.xs - event.xdata).argmin())
        iy = int(np.abs(self.ys - event.ydata).argmin())
        self._cursor = (ix, iy)
        self.cursor_lbl.setText(f"Cursor: X={self.xs[ix]:.6g}, Y={self.ys[iy]:.6g}")
        self._redraw()

    def _goto_cursor(self):
        if self._busy():
            QMessageBox.information(self, "Busy", "Stop the scan first.")
            return
        p = self._last_params
        x_axis = p["x_axis"] if p else self.x_axis.currentText()
        y_axis = p["y_axis"] if p else self.y_axis.currentText()
        if GATE_CUT in (x_axis, y_axis):
            QMessageBox.information(self, "Not available", "Use the gate controls for line cuts.")
            return
        ix, iy = self._cursor
        x, y = float(self.xs[ix]), float(self.ys[iy])

        def _go():
            try:
                self.AXES[y_axis](y, None, None)
                self.AXES[x_axis](x, None, None)
                self.status_sig.emit(f"Moved to X={x:.6g}, Y={y:.6g}.")
            except Exception as e:
                self.status_sig.emit(f"Move failed: {e}")
        threading.Thread(target=_go, daemon=True).start()

    # ── Saving ───────────────────────────────────────────────────────────────

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Choose folder", self.folder.text())
        if path:
            self.folder.setText(path)

    @staticmethod
    def _unique_name(folder: str, base: str) -> str:
        used = {os.path.splitext(f)[0] for f in os.listdir(folder)} if os.path.isdir(folder) else set()
        if base not in used:
            return base
        i = 1
        while f"{base}_{i}" in used:
            i += 1
        return f"{base}_{i}"

    def set_filename(self, name: str):
        self.filename.setText(name.strip())

    def save_data(self, filename: str | None = None) -> str:
        return self._run_on_gui(lambda: self._save_gui(filename))

    def _save_gui(self, filename: str | None = None) -> str:
        if self.data is None or self._last_params is None:
            raise RuntimeError("No scan data to save — run a scan first.")
        p = self._last_params
        folder = self.folder.text().strip()
        if filename:
            self.filename.setText(filename.strip())
        base = self.filename.text().strip() or "scan2d_data"
        if base.lower().endswith(".txt"):
            base = base[:-4]
        os.makedirs(folder, exist_ok=True)
        base = self._unique_name(folder, base)
        self.filename.setText(base)
        txt_path = os.path.join(folder, base + ".txt")

        def rng(axis, vals, custom):
            if custom:
                return f"custom values {list(np.round(vals, 9))}"
            return f"{vals[0]:g} to {vals[-1]:g}, {len(vals)} points"

        notes = self.notes.toPlainText().strip().replace("\n", " | ")
        cols = self.controller.measurement_columns(p["measurement"])
        lines = [
            "2D Scan — white-light microscope (agentic control)",
            f"Date/Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"X Variable (fast axis): {p['x_axis']}",
            f"Y Variable (slow axis): {p['y_axis']}",
            f"Z Variable (measurement): {p['measurement']}",
            f"X range: {rng(p['x_axis'], p['xs'], self.custom_x.isChecked())}",
            f"Y range: {rng(p['y_axis'], p['ys'], self.custom_y.isChecked())}",
        ]
        if GATE_CUT in (p["x_axis"], p["y_axis"]):
            v2 = p["xs2"] if p["x_axis"] == GATE_CUT else p["ys2"]
            lines.append(f"Line cut back-gate values: {list(np.round(v2, 6))}")
        lines += [
            f"Averages: {p['n_avg']}   Wait per point (s): {p['wait_s']}",
            f"Align before each scan: {p['align_each_scan']}   "
            f"Align every N rows: {p['align_rows']} (N={p['align_n']})",
            f"Device Name: {self.device.text()}",
            f"Pump Power: {self.pump_power.text()}",
            f"Pump Wavelength: {self.pump_wl.text()}",
            f"Probe Power: {self.probe_power.text()}",
            f"Probe Wavelength: {self.probe_wl.text()}",
            f"Additional Notes: {notes}",
            "",
            *instrument_state_lines(self.controller),
            "",
            f"Data shape: {self.data.shape} (n_scans, Ny, Nx, channels)",
            "Columns: Scan_Number Y X " + " ".join(c.replace(" ", "_") for c in cols),
        ]
        header = "\n".join("# " + l if l else "#" for l in lines)

        n, ny, nx, _ = self.data.shape
        S, Y, X = np.meshgrid(np.arange(n), self.ys, self.xs, indexing="ij")
        table = np.column_stack([S.ravel(), Y.ravel(), X.ravel(), self.data.reshape(-1, N_CH)])
        np.savetxt(txt_path, table, header=header, comments="", fmt="%.10g", encoding="utf-8")
        if self.save_pic.isChecked():
            self.fig.savefig(os.path.join(folder, base + ".png"), dpi=150)
        self.controller.log(f"2D scan saved: {txt_path}")
        return txt_path

    def _save(self):
        try:
            path = self._save_gui()
        except Exception as e:
            QMessageBox.warning(self, "Save", str(e))
            return
        QMessageBox.information(self, "Saved", f"Saved:\n{path}")

    # ── Agent API ────────────────────────────────────────────────────────────

    def get_settings(self) -> dict:
        def _get():
            return {
                "x_axis": self.x_axis.currentText(), "y_axis": self.y_axis.currentText(),
                "measurement": self.meas.currentText(),
                "x_start": self.x_start.text(), "x_end": self.x_end.text(), "x_step": self.x_step.text(),
                "y_start": self.y_start.text(), "y_end": self.y_end.text(), "y_step": self.y_step.text(),
                "averages": self.averages.text(), "wait_s": self.wait_s.text(),
                "custom_x": self.custom_x.isChecked(), "custom_x_values": self.custom_x0.text(),
                "custom_x_backgate_values": self.custom_x2.text(),
                "custom_y": self.custom_y.isChecked(), "custom_y_values": self.custom_y0.text(),
                "custom_y_backgate_values": self.custom_y2.text(),
                "line_cut_bg_start": self.bg_start.text(), "line_cut_bg_end": self.bg_end.text(),
                "align_before_each_scan": self.align_each_scan.isChecked(),
                "align_every_n_rows": self.align_rows.isChecked(), "align_n": self.align_n.text(),
                "image_1_channel": self.plot1.currentText(), "image_2_channel": self.plot2.currentText(),
                "show_average": self.show_avg.isChecked(),
                "device": self.device.text(), "pump_power": self.pump_power.text(),
                "pump_wavelength": self.pump_wl.text(), "probe_power": self.probe_power.text(),
                "probe_wavelength": self.probe_wl.text(), "notes": self.notes.toPlainText(),
                "folder": self.folder.text(), "filename": self.filename.text(),
                "autosave": self.autosave.isChecked(), "save_picture": self.save_pic.isChecked(),
                "running": self._busy(),
                "axes_available": list(self.AXES),
                "measurements_available": list(self.MEASUREMENTS),
                "channels_for_measurement": self._channel_names(),
            }
        return self._run_on_gui(_get)

    def apply_settings(self, s: dict) -> list[str]:
        def _apply():
            warnings = []
            for key, combo in (("x_axis", self.x_axis), ("y_axis", self.y_axis),
                               ("measurement", self.meas)):
                if key in s:
                    idx = combo.findText(str(s[key]))
                    if idx < 0:
                        warnings.append(f"'{s[key]}' is not valid for {key}. Options: "
                                        f"{[combo.itemText(i) for i in range(combo.count())]}")
                    else:
                        combo.setCurrentIndex(idx)
            for key, combo in (("image_1_channel", self.plot1), ("image_2_channel", self.plot2)):
                if key in s:
                    idx = _channel_index(combo, s[key])
                    if idx < 0:
                        warnings.append(f"'{s[key]}' is not a channel. Options: "
                                        f"{[combo.itemText(i) for i in range(combo.count())]}")
                    else:
                        combo.setCurrentIndex(idx)
            texts = {"x_start": self.x_start, "x_end": self.x_end, "x_step": self.x_step,
                     "y_start": self.y_start, "y_end": self.y_end, "y_step": self.y_step,
                     "averages": self.averages, "wait_s": self.wait_s,
                     "custom_x_values": self.custom_x0, "custom_x_backgate_values": self.custom_x2,
                     "custom_y_values": self.custom_y0, "custom_y_backgate_values": self.custom_y2,
                     "line_cut_bg_start": self.bg_start, "line_cut_bg_end": self.bg_end,
                     "align_n": self.align_n, "device": self.device,
                     "pump_power": self.pump_power, "pump_wavelength": self.pump_wl,
                     "probe_power": self.probe_power, "probe_wavelength": self.probe_wl,
                     "folder": self.folder, "filename": self.filename}
            for key, w in texts.items():
                if key in s:
                    w.setText(str(s[key]))
            if "notes" in s:
                self.notes.setPlainText(str(s["notes"]))
            checks = {"custom_x": self.custom_x, "custom_y": self.custom_y,
                      "align_before_each_scan": self.align_each_scan,
                      "align_every_n_rows": self.align_rows, "show_average": self.show_avg,
                      "autosave": self.autosave, "save_picture": self.save_pic}
            for key, w in checks.items():
                if key in s:
                    w.setChecked(bool(s[key]))
            self.controller.scan_signals.activate_tab.emit(TAB_NAME)
            return warnings
        return self._run_on_gui(_apply)

    def run_scan_blocking(self) -> dict:
        """Run the scan with the current settings in the calling (agent) thread."""
        if self._busy():
            return {"error": "A 2D scan is already running"}
        try:
            p = self._run_on_gui(self._collect)
        except Exception as e:
            return {"error": str(e)}
        self._thread = threading.current_thread()
        try:
            aborted, msg = self._run(p)
        finally:
            self._thread = None
        # Wait until the GUI has applied every queued point before reading data.
        self._run_on_gui(lambda: None)
        if self.data is None:
            return {"error": msg}
        d = self._run_on_gui(self._display)
        stats = {"message": msg, "aborted": aborted,
                 "nx": len(self.xs), "ny": len(self.ys), "n_scans": int(p["n_avg"]),
                 "channels": self._channel_names(p["measurement"])}
        for k in range(N_CH):
            v = d[:, :, k][np.isfinite(d[:, :, k])]
            if v.size:
                stats[f"data{k + 1}"] = {"min": float(f"{v.min():.6g}"),
                                         "max": float(f"{v.max():.6g}"),
                                         "mean": float(f"{v.mean():.6g}")}
        png = self._run_on_gui(self._png_b64)
        out = {"stats": stats, "png_b64": png}
        if aborted:
            out["warning"] = msg
        return out

    def _png_b64(self) -> str:
        buf = io.BytesIO()
        self.fig.savefig(buf, format="png", dpi=70)
        self._redraw()
        return base64.standard_b64encode(buf.getvalue()).decode()


def _channel_index(combo: QComboBox, want) -> int:
    """Accept 'data3', '3', or the full item text."""
    w = str(want).strip().lower()
    if w.isdigit():
        w = f"data{w}"
    for i in range(combo.count()):
        t = combo.itemText(i).lower()
        if t == w or t.split(":")[0] == w:
            return i
    return -1


class _quiet:
    """Silence numpy's 'mean of empty slice' warning for unfilled pixels."""
    def __enter__(self):
        import warnings
        self._w = warnings.catch_warnings()
        self._w.__enter__()
        warnings.simplefilter("ignore", category=RuntimeWarning)

    def __exit__(self, *a):
        return self._w.__exit__(*a)
