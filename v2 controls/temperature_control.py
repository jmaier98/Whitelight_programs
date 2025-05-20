import tkinter as tk
from tkinter import ttk
import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pyvisa
import time
import datetime
import threading

# -------------------------------
# Lakeshore335 Instrument Control
# -------------------------------
class Lakeshore335:
    def __init__(self, gpib_address="GPIB0::12::INSTR"):
        rm = pyvisa.ResourceManager()
        self.inst = rm.open_resource(gpib_address)
        self.inst.read_termination = "\n"
        self.inst.write_termination = "\n"
        self.enable_heater()  # Automatically enable heater on startup


    def enable_heater(self):
        """Enable the heater output and set to PID mode (auto)."""
        try:
            # Command to enable heater output; adjust per your instrument's manual.
            self.inst.write("HTR 1,ON")
            # Set heater to PID (auto) mode by default.
            self.inst.write("HTRMODE 1")
        except Exception as e:
            print("Error enabling heater:", e)

    def read_temperature(self):
        """Query the temperature on channel A."""
        try:
            response = self.inst.query("KRDG? A")
            return float(response)
        except Exception as e:
            print("Error reading temperature:", e)
            return None

    def read_heater(self):
        """Query the heater output from channel 1."""
        try:
            response = self.inst.query("HTR? 1")
            return float(response)
        except Exception as e:
            print("Error reading heater:", e)
            return None

    def set_setpoint(self, value):
        """Set the temperature setpoint (for PID control)."""
        try:
            self.inst.write(f"SETP 1,{value}")
        except Exception as e:
            print("Error setting setpoint:", e)

    def set_heater_mode(self, manual):
        """
        Set heater mode:
          - manual = True: Forced (manual) heater output
          - manual = False: PID (auto) control
        """
        try:
            if manual:
                self.inst.write("HTRMODE 0")
            else:
                self.inst.write("HTRMODE 1")
        except Exception as e:
            print("Error setting heater mode:", e)

    def set_heater_output(self, value):
        """
        Force the heater output to a specific value.
        """
        try:
            self.inst.write(f"HTR 1,{value}")
        except Exception as e:
            print("Error setting heater output:", e)

    def close(self):
        """Close the instrument connection."""
        self.inst.close()

# -------------------------------
# Main Application Class
# -------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lakeshore Model 335 Control")
        self.geometry("1000x600")

        # Create the instrument instance.
        self.lakeshore = Lakeshore335()

        # Data lists for temperature and heater values.
        # Each element is a tuple: (timestamp, value)
        self.data = []         # Temperature data
        self.heater_data = []  # Heater output data

        # Flag to stop the background thread.
        self.running = True

        self.create_widgets()

        # Start a background thread to read temperature and heater values every second.
        self.read_thread = threading.Thread(target=self.read_loop, daemon=True)
        self.read_thread.start()

        # Start the live plot updater.
        self.update_plot()

        # Ensure a clean exit when closing the window.
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        """Set up the GUI controls and the live plot."""
        control_frame = ttk.Frame(self)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        # Temperature setpoint controls.
        ttk.Label(control_frame, text="Temperature Setpoint:").pack(side=tk.LEFT)
        self.setpoint_entry = ttk.Entry(control_frame, width=10)
        self.setpoint_entry.pack(side=tk.LEFT, padx=5)
        setpoint_button = ttk.Button(control_frame, text="Set Temp", command=self.set_setpoint)
        setpoint_button.pack(side=tk.LEFT, padx=5)

        # Heater controls.
        ttk.Label(control_frame, text="Heater Mode:").pack(side=tk.LEFT, padx=10)
        self.heater_manual_var = tk.BooleanVar(value=False)
        self.heater_mode_check = ttk.Checkbutton(
            control_frame,
            text="Manual",
            variable=self.heater_manual_var,
            command=self.on_heater_mode_change)
        self.heater_mode_check.pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="Forced Heater Value:").pack(side=tk.LEFT, padx=10)
        self.heater_entry = ttk.Entry(control_frame, width=10)
        self.heater_entry.pack(side=tk.LEFT, padx=5)
        # Disable the forced heater entry unless manual mode is active.
        self.heater_entry.config(state="disabled")
        heater_button = ttk.Button(control_frame, text="Set Heater", command=self.set_heater)
        heater_button.pack(side=tk.LEFT, padx=5)

        # Create the matplotlib figure and axes.
        self.fig = Figure(figsize=(8, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Temperature and Heater Output (Last Minute)")
        self.ax.set_xlabel("Time")
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        # Create a twin axis for heater output and store it.
        self.ax2 = self.ax.twinx()

        # Embed the figure in the Tkinter window.
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def read_loop(self):
        """Background loop that queries the temperature and heater values every second."""
        while self.running:
            current_time = time.time()
            temp = self.lakeshore.read_temperature()
            heater = self.lakeshore.read_heater()
            if temp is not None:
                self.data.append((current_time, temp))
            if heater is not None:
                self.heater_data.append((current_time, heater))
            time.sleep(1)

    def update_plot(self):
        """
        Update the live plot once per second.
        Only the last minute (60 seconds) of data is displayed.
        Temperature is plotted on the left y-axis (blue),
        while heater output is plotted on the right y-axis (red).
        """
        now = time.time()
        one_minute_ago = now - 60

        # Keep only data from the last minute.
        self.data = [(t, temp) for (t, temp) in self.data if t >= one_minute_ago]
        self.heater_data = [(t, heater) for (t, heater) in self.heater_data if t >= one_minute_ago]

        # Prepare temperature data.
        if self.data:
            times_temp, temps = zip(*self.data)
            dates_temp = mdates.date2num([datetime.datetime.utcfromtimestamp(t) for t in times_temp])
        else:
            dates_temp, temps = [], []

        # Prepare heater data.
        if self.heater_data:
            times_heater, heaters = zip(*self.heater_data)
            dates_heater = mdates.date2num([datetime.datetime.utcfromtimestamp(t) for t in times_heater])
        else:
            dates_heater, heaters = [], []

        # Clear both axes.
        self.ax.clear()
        self.ax2.clear()

        # Plot temperature on the left y-axis.
        self.ax.plot_date(dates_temp, temps, fmt="o-", markersize=5, color='blue', label="Temperature")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Temperature (K)", color="blue")
        self.ax.tick_params(axis='y', labelcolor='blue')
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

        # Plot heater output on the right y-axis.
        self.ax2.plot_date(dates_heater, heaters, fmt="s--", markersize=5, color='red', label="Heater")
        self.ax2.set_ylabel("Heater Output", color="red")
        self.ax2.tick_params(axis='y', labelcolor='red')

        self.fig.autofmt_xdate()
        self.canvas.draw()

        self.after(1000, self.update_plot)

    def set_setpoint(self):
        """Called when the Temperature Setpoint button is pressed."""
        try:
            value = float(self.setpoint_entry.get())
            self.lakeshore.set_setpoint(value)
            print(f"Temperature setpoint updated to {value}")
        except ValueError:
            print("Invalid temperature setpoint. Please enter a number.")

    def on_heater_mode_change(self):
        """
        Called when the heater mode checkbutton is toggled.
        Switches between manual (forced) mode and PID (auto) mode.
        """
        manual = self.heater_manual_var.get()
        self.lakeshore.set_heater_mode(manual)
        if manual:
            self.heater_entry.config(state="normal")
        else:
            self.heater_entry.config(state="disabled")

    def set_heater(self):
        """Called when the Set Heater button is pressed (only active in manual mode)."""
        try:
            value = float(self.heater_entry.get())
            self.lakeshore.set_heater_output(value)
            print(f"Heater forced value set to {value}")
        except ValueError:
            print("Invalid heater value. Please enter a number.")

    def on_close(self):
        """Stop the background thread, close the instrument, and exit."""
        self.running = False
        time.sleep(1.1)  # Give the thread a moment to finish
        self.lakeshore.close()
        self.destroy()

# -------------------------------
# Main Program Entry Point
# -------------------------------
if __name__ == '__main__':
    app = App()
    app.mainloop()

