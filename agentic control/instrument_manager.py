"""
Opens every instrument on the white-light microscope.

The hardware on this microscope changes over time, so:
  * every instrument is opened on its own; one that is missing, switched off
    or on another port is reported and left out, and the program still starts
  * each instrument must answer before it counts as present (a GPIB address
    or COM port can "open" with nothing behind it)
  * tabs leave out the controls, axes and measurements of missing instruments
  * startup prints a table of what was found, and the same list appears in
    the agent log and the window's status bar

To move an instrument to a new port, or to skip one that is not installed,
edit INSTRUMENTS below.
"""
from __future__ import annotations

import time

from drivers import ESP301, Lockins, SR400, SP2500, BTT, MLJ050, Keithley2400, Arduino

# name: (enabled, port/address, description)
# Set enabled to False for hardware that is not installed: it is then listed as
# "disabled" at startup and not probed at all, which makes startup faster.
INSTRUMENTS = {
    "ESP":      (True, "COM7",  "Newport ESP301: sample X/Y stage + delay line"),
    "BTT":      (True, "COM4",  "BTT board: rotation mounts / waveplates"),
    "SP2500":   (True, "COM5",  "SP2500 spectrometer"),
    "ZStage":   (True, "COM8",  "Thorlabs MLJ050 Z stage"),
    "Arduino":  (True, "COM3",  "Arduino: steering motors, shutter, pellicle, BS, LED"),
    "Lockins":  (True, {1: "GPIB0::8::INSTR", 2: "GPIB0::7::INSTR", 3: "GPIB0::26::INSTR"},
                 "SR830 lock-ins 1, 2, 3"),
    "SR400":    (True, "GPIB0::23::INSTR", "SR400 photon counter"),
    "TopGate":  (True, "GPIB0::24::INSTR", "Keithley 2400 top gate"),
    "BackGate": (True, "GPIB0::22::INSTR", "Keithley 2400 back gate"),
}


class InstrumentManager:
    def __init__(self, state):
        self._instruments = {}
        self.state = state
        self.failures: list[str] = []      # instruments that should be there but are not
        self.notes: list[str] = []         # partial problems (e.g. one lock-in of three)
        self.report: list[tuple[str, str, str, str]] = []   # (name, status, where, detail)

    def _open(self, name, factory):
        enabled, where, desc = INSTRUMENTS[name]
        where_s = ", ".join(where.values()) if isinstance(where, dict) else str(where)
        if not enabled:
            self._instruments[name] = None
            self.report.append((name, "disabled", where_s, desc))
            return
        t0 = time.time()
        try:
            self._instruments[name] = factory(where)
            detail = desc
            if name == "Lockins":
                detail = self._instruments[name].describe()
                for n, why in self._instruments[name].missing.items():
                    self.notes.append(f"Lock-in {n} missing ({why})")
            self.report.append((name, "OK", where_s, f"{detail}  [{time.time() - t0:.1f} s]"))
        except Exception as e:
            self._instruments[name] = None
            msg = f"{type(e).__name__}: {e}".strip()
            self.failures.append(f"{name} ({desc}, {where_s}): {msg}")
            self.report.append((name, "MISSING", where_s, f"{msg}  [{time.time() - t0:.1f} s]"))

    def open_all(self):
        s = self.state
        rm, rm_error = None, None
        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
        except Exception as e:
            rm_error = f"no VISA backend: {e}"

        def gpib(factory):
            def f(where):
                if rm is None:
                    raise RuntimeError(rm_error)
                return factory(where)
            return f

        self._open("ESP",      lambda p: ESP301.ESP301(s, port=p))
        self._open("BTT",      lambda p: BTT.BTT(s, port=p))
        self._open("SP2500",   lambda p: SP2500.SP2500(s, port=p))
        self._open("ZStage",   lambda p: MLJ050.ZStage(s, port=p))
        self._open("Arduino",  lambda p: Arduino.Arduino(s, port=p))
        self._open("Lockins",  gpib(lambda a: Lockins.Lockins(rm, a)))
        self._open("SR400",    gpib(lambda a: SR400.SR400(s, rm, a)))
        self._open("TopGate",  gpib(lambda a: Keithley2400.Keithley2400(s, a, "top_gate", rm)))
        self._open("BackGate", gpib(lambda a: Keithley2400.Keithley2400(s, a, "back_gate", rm)))
        self.print_report()

    def print_report(self):
        lines = ["", "Instruments at startup:"]
        for name, status, where, detail in self.report:
            lines.append(f"  {status:<8} {name:<9} {where:<44} {detail}")
        lines.append("")
        text = "\n".join(lines)
        try:
            print(text)
        except Exception:          # Windows console that cannot print µ etc.
            print(text.encode("ascii", "replace").decode())

    def get(self, name):
        return self._instruments[name]

    def connected(self) -> list[str]:
        return [k for k, v in self._instruments.items() if v is not None]

    def missing(self) -> list[str]:
        return [n for n, st, _, _ in self.report if st == "MISSING"]

    def disabled(self) -> list[str]:
        return [n for n, st, _, _ in self.report if st == "disabled"]

    def close_all(self):
        print("closing instruments")
        for inst in self._instruments.values():
            if inst is not None:
                try:
                    inst.close()
                except Exception:
                    pass
