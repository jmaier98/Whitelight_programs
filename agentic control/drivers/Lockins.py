"""
The SR830 lock-in amplifiers on the white-light microscope (GPIB).

  lockin 1 : GPIB 8  (middle rack position) — usually R / I-
  lockin 2 : GPIB 7  (top)                  — usually dR / I+
  lockin 3 : GPIB 26 (bottom)

Each lock-in is opened on its own and must answer *IDN? to count as present,
so one missing unit does not take the others down. `present` lists the ones
that answered. Reads from a missing lock-in, or a failed read, return NaN.
"""
from __future__ import annotations

import math
import threading

import pyvisa

ADDRESSES = {
    1: "GPIB0::8::INSTR",
    2: "GPIB0::7::INSTR",
    3: "GPIB0::26::INSTR",
}


class Lockins:
    def __init__(self, rm: pyvisa.ResourceManager | None = None, addresses: dict | None = None):
        self.rm = rm or pyvisa.ResourceManager()
        self.addresses = dict(addresses or ADDRESSES)
        self._inst = {}
        self._lock = threading.Lock()
        self.missing: dict[int, str] = {}
        for n, addr in self.addresses.items():
            inst = None
            try:
                inst = self.rm.open_resource(addr)
                inst.read_termination = "\n"
                inst.write_termination = "\n"
                inst.timeout = 1500          # short while probing
                try:
                    inst.clear()
                except Exception:
                    pass
                idn = inst.query("*IDN?").strip()
                if not idn:
                    raise RuntimeError("no reply to *IDN?")
                inst.timeout = 5000
                self._inst[n] = inst
            except Exception as e:
                self.missing[n] = f"{addr}: {type(e).__name__}: {e}"
                if inst is not None:
                    try:
                        inst.close()
                    except Exception:
                        pass
        if not self._inst:
            raise RuntimeError("no lock-in answered (" + "; ".join(self.missing.values()) + ")")

    @property
    def present(self) -> list[int]:
        return sorted(self._inst)

    def describe(self) -> str:
        parts = [f"lock-in {n} OK" for n in self.present]
        parts += [f"lock-in {n} MISSING" for n in sorted(self.missing)]
        return ", ".join(parts)

    def _query(self, n: int, cmd: str) -> str:
        if n not in self._inst:
            raise RuntimeError(f"lock-in {n} is not connected")
        with self._lock:
            return self._inst[n].query(cmd)

    def read_xy(self, n: int) -> tuple[float, float]:
        """Simultaneous X and Y snapshot from lock-in n."""
        try:
            x, y = self._query(n, "SNAP? 1,2").strip().split(",")
            return float(x), float(y)
        except Exception as e:
            print(f"[Lockins] read_xy({n}) failed: {e}")
            return math.nan, math.nan

    def read_x(self, n: int) -> float:
        return self.read_xy(n)[0]

    def _outp(self, n: int, i: int) -> float:
        try:
            return float(self._query(n, f"OUTP? {i}"))
        except Exception as e:
            print(f"[Lockins] OUTP? {i} on lock-in {n} failed: {e}")
            return math.nan

    def read_y(self, n: int) -> float:
        return self._outp(n, 2)

    def read_r(self, n: int) -> float:
        return self._outp(n, 3)

    def read_theta(self, n: int) -> float:
        return self._outp(n, 4)

    def close(self):
        for inst in self._inst.values():
            try:
                inst.close()
            except Exception:
                pass
