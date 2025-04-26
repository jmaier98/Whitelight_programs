import threading
import time
import numpy as np
import pyvisa
import tkinter as tk
from tkinter import messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# ==== USER CONFIGURATION ====
TOP_GATE_ADDR = 'GPIB0::24::INSTR'
BOT_GATE_ADDR = 'GPIB0::22::INSTR'
VOLT_STEP    = 0.01     # V per step
DELAY_SEC    = .02       # s between steps
# ============================

class GateTester:
    def __init__(self, master):
        self.master = master
        master.title("Gate Breakdown Voltage Tester")

        # --- VISA setup ---
        rm = pyvisa.ResourceManager()
        try:
            self.top_meter = rm.open_resource(TOP_GATE_ADDR)
            self.bot_meter = rm.open_resource(BOT_GATE_ADDR)
        except Exception as e:
            messagebox.showerror("VISA Error", f"Could not open instruments:\n{e}")
            master.destroy()
            return

        # Configure both meters to:
        #  * reset
        #  * source voltage, start at 0 V
        #  * measure current
        #  * only return the current value
        #  * output ON (at 0 V)
        for inst in (self.top_meter, self.bot_meter):
            inst.write("SOUR:FUNC VOLT")
            #inst.write("SOUR:VOLT 0")         # start at zero volts
            inst.write("SENS:FUNC 'CURR'")
            inst.write("FORM:ELEM CURR")      # only return current
            inst.write("OUTP ON")             # keep output ON at 0 V

        # … rest of your GUI setup (unchanged) …

        # --- GUI controls ---
        ctrl = tk.Frame(master)
        ctrl.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Gate selection
        self.gate_var = tk.StringVar(value='top')
        tk.Label(ctrl, text="Sweep Gate:").pack(anchor='w')
        tk.Radiobutton(ctrl, text="Top Gate",    variable=self.gate_var, value='top').pack(anchor='w')
        tk.Radiobutton(ctrl, text="Bottom Gate", variable=self.gate_var, value='bot').pack(anchor='w')

        # Static set controls
        tk.Label(ctrl, text="Top Gate V (V):").pack(anchor='w', pady=(10,0))
        self.top_voltage_entry = tk.Entry(ctrl); self.top_voltage_entry.pack(anchor='w')
        tk.Button(ctrl, text="Set Top Gate", command=self.set_top_voltage).pack(anchor='w', pady=(0,5))

        tk.Label(ctrl, text="Bot Gate V (V):").pack(anchor='w', pady=(5,0))
        self.bot_voltage_entry = tk.Entry(ctrl); self.bot_voltage_entry.pack(anchor='w')
        tk.Button(ctrl, text="Set Bot Gate", command=self.set_bot_voltage).pack(anchor='w', pady=(0,10))

        # Sweep parameters
        tk.Label(ctrl, text="Start V (V):").pack(anchor='w')
        self.start_entry = tk.Entry(ctrl); self.start_entry.pack(anchor='w')
        tk.Label(ctrl, text="End V (V):").pack(anchor='w')
        self.end_entry   = tk.Entry(ctrl); self.end_entry.pack(anchor='w')
        tk.Label(ctrl, text="Max I (A):").pack(anchor='w', pady=(5,0))
        self.max_i_entry = tk.Entry(ctrl); self.max_i_entry.pack(anchor='w')

        tk.Button(ctrl, text="Start Sweep", command=self.start_sweep).pack(anchor='w', pady=(10,5))
        tk.Button(ctrl, text="Stop Sweep", command=self.stop_sweep).pack(anchor='w', pady=(10,5))

        # --- Plot area ---
        fig = Figure(figsize=(6,4))
        self.ax = fig.add_subplot(111)
        self.ax.set_xlabel("Voltage (V)")
        self.ax.set_ylabel("Current (A)")
        self.line_top, = self.ax.plot([], [], label="Top Gate")
        self.line_bot, = self.ax.plot([], [], label="Bot Gate")
        self.ax.legend(loc='upper left')

        canvas = FigureCanvasTkAgg(fig, master=master)
        canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.canvas = canvas

        # Data buffers & state
        self.xdata = []
        self.y_top = []
        self.y_bot = []
        self.sweeping = False

    def set_top_voltage(self):
        try:
            target = float(self.top_voltage_entry.get())
            # turn on output if it isn’t already
            #self.top_meter.write("OUTP ON")
            # query the current source voltage
            current = float(self.top_meter.query("SOUR:VOLT?"))

            # build a ramp from current→target
            step = VOLT_STEP if target > current else -VOLT_STEP
            voltages = list(np.arange(current + step, target, step)) + [target]

            for v in voltages:
                self.top_meter.write(f"SOUR:VOLT {v}")
                time.sleep(DELAY_SEC)

            # final measurement
            i = float(self.top_meter.query("MEAS:CURR?"))
            print(f"[Top] V={target:.3f} V → I={i:.3e} A")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to set top gate:\n{e}")

    def set_bot_voltage(self):
        try:
            target = float(self.bot_voltage_entry.get())
            #self.bot_meter.write("OUTP ON")
            current = float(self.bot_meter.query("SOUR:VOLT?"))

            step = VOLT_STEP if target > current else -VOLT_STEP
            voltages = list(np.arange(current + step, target, step)) + [target]

            for v in voltages:
                self.bot_meter.write(f"SOUR:VOLT {v}")
                time.sleep(DELAY_SEC)

            i = float(self.bot_meter.query("MEAS:CURR?"))
            print(f"[Bot] V={target:.3f} V → I={i:.3e} A")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to set bottom gate:\n{e}")
    def stop_sweep(self):
        self.sweeping = False
    def start_sweep(self):
        if self.sweeping:
            return
        try:
            vs = float(self.start_entry.get())
            ve = float(self.end_entry.get())
            imax = float(self.max_i_entry.get())
        except ValueError:
            messagebox.showwarning("Input Error", "Please enter numeric start/end/max current.")
            return

        # build sweep array
        direction = 1 if ve > vs else -1
        voltages = np.append(np.arange(vs, ve, direction*VOLT_STEP), ve)

        # clear old data
        self.xdata.clear()
        self.y_top.clear()
        self.y_bot.clear()

        self.sweeping = True
        t = threading.Thread(target=self._do_sweep, args=(voltages, imax))
        t.daemon = True
        t.start()

    def _do_sweep(self, voltages, imax):
        gate = self.gate_var.get()
        sweep_meter = self.top_meter if gate=='top' else self.bot_meter

        # turn both outputs on
        #self.top_meter.write("OUTP ON")
        #self.bot_meter.write("OUTP ON")

        # ramp from 0 to first voltage
        sweep_meter.write("SOUR:VOLT?")
        voltage0 = float(sweep_meter.read())
        first = voltages[0]
        step  = VOLT_STEP if first>voltage0 else -VOLT_STEP
        ramp_up = list(np.arange(voltage0, first, step)) + [first]
        for v0 in ramp_up:
            sweep_meter.write(f"SOUR:VOLT {v0}")
            time.sleep(DELAY_SEC)

        try:
            for v in voltages:
                if not self.sweeping:
                    break
                sweep_meter.write(f"SOUR:VOLT {v}")
                time.sleep(DELAY_SEC)

                itop = float(self.top_meter.query("MEAS:CURR?"))
                ibot = float(self.bot_meter.query("MEAS:CURR?"))

                self.xdata.append(v)
                self.y_top.append(itop)
                self.y_bot.append(ibot)

                self.line_top.set_data(self.xdata, self.y_top)
                self.line_bot.set_data(self.xdata, self.y_bot)
                self.ax.relim(); self.ax.autoscale_view()
                self.canvas.draw_idle()

                if abs(itop) > imax or abs(ibot) > imax:
                    print(f"Overcurrent at V={v:.3f} V  I_top={itop:.3e} A  I_bot={ibot:.3e} A")
                    break

        finally:
            # ramp down back to 0
            last = self.xdata[-1] if self.xdata else voltages[0]
            step_down = -VOLT_STEP if last>0 else VOLT_STEP
            ramp_dn = list(np.arange(last, 0, step_down)) + [0]
            
            sweep_meter.write(f"SOUR:VOLT {ramp_dn[0]}")
            time.sleep(DELAY_SEC)

            # leave outputs ON at 0 V
            self.sweeping = False
            print("Sweep finished.")

if __name__ == "__main__":
    root = tk.Tk()
    app = GateTester(root)
    root.mainloop()
