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

    def set_heater_range(self, range_setting):
        """
        Set heater range: 'off'=0, 'low'=1, 'mid'=2, 'high'=3
        """
        try:
            range_dict = {'off': 0, 'low': 1, 'mid': 2, 'high': 3}
            if range_setting.lower() in range_dict:
                range_number = range_dict[range_setting.lower()]
                self.inst.write(f"RANGE 1,{range_number}")
            else:
                print(f"Invalid range setting: {range_setting}")
        except Exception as e:
            print("Error setting heater range:", e)

    def get_heater_range(self):
        """Get current heater range setting."""
        try:
            response = self.inst.query("RANGE? 1")
            range_dict = {0: 'off', 1: 'low', 2: 'mid', 3: 'high'}
            return range_dict.get(int(response), 'unknown')
        except Exception as e:
            print("Error reading heater range:", e)
            return 'unknown'

    def set_pid_p(self, p_value):
        """Set only the P value of the PID controller, keeping I and D unchanged."""
        try:
            # Get current PID values
            current_pid = self.inst.query("PID? 1")
            p_current, i_current, d_current = map(float, current_pid.split(','))
            # Set new P value while keeping I and D the same
            self.inst.write(f"PID 1,{p_value},{i_current},{d_current}")
        except Exception as e:
            print("Error setting PID P value:", e)

    def set_pid_i(self, i_value):
        """Set only the I value of the PID controller, keeping P and D unchanged."""
        try:
            # Get current PID values
            current_pid = self.inst.query("PID? 1")
            p_current, i_current, d_current = map(float, current_pid.split(','))
            # Set new I value while keeping P and D the same
            self.inst.write(f"PID 1,{p_current},{i_value},{d_current}")
        except Exception as e:
            print("Error setting PID I value:", e)

    def set_pid_d(self, d_value):
        """Set only the D value of the PID controller, keeping P and I unchanged."""
        try:
            # Get current PID values
            current_pid = self.inst.query("PID? 1")
            p_current, i_current, d_current = map(float, current_pid.split(','))
            # Set new D value while keeping P and I the same
            self.inst.write(f"PID 1,{p_current},{i_current},{d_value}")
        except Exception as e:
            print("Error setting PID D value:", e)

    def set_full_pid(self, p_value, i_value, d_value):
        """Set all PID values at once."""
        try:
            self.inst.write(f"PID 1,{p_value},{i_value},{d_value}")
        except Exception as e:
            print("Error setting PID values:", e)

    def get_pid_values(self):
        """Get current PID values."""
        try:
            response = self.inst.query("PID? 1")
            p, i, d = map(float, response.split(','))
            return p, i, d
        except Exception as e:
            print("Error reading PID values:", e)
            return 0.0, 0.0, 0.0

    def close(self):
        """Close the instrument connection."""
        self.inst.close()

# -------------------------------
# Main Application Class
# -------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lakeshore Model 335 Control - Enhanced")
        self.geometry("1200x700")

        # Create the instrument instance.
        self.lakeshore = Lakeshore335()

        # Data lists for temperature and heater values.
        # Each element is a tuple: (timestamp, value)
        self.data = []         # Temperature data
        self.heater_data = []  # Heater output data

        # Display time window (in seconds) - default 60 seconds
        self.time_window = 60
        
        # Update interval (in seconds) - default 1 second
        self.update_interval = 1.0

        # Flag to stop the background thread.
        self.running = True

        self.create_widgets()

        # Start a background thread to read temperature and heater values every second.
        self.read_thread = threading.Thread(target=self.read_loop, daemon=True)
        self.read_thread.start()

        # Start the live plot updater.
        self.update_plot()

        # Update PID display initially
        self.update_pid_display()

        # Ensure a clean exit when closing the window.
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        """Set up the GUI controls and the live plot."""
        # Main control frame
        main_control_frame = ttk.Frame(self)
        main_control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        # First row of controls
        control_frame1 = ttk.Frame(main_control_frame)
        control_frame1.pack(fill=tk.X, pady=2)

        # Temperature setpoint controls.
        ttk.Label(control_frame1, text="Temperature Setpoint:").pack(side=tk.LEFT)
        self.setpoint_entry = ttk.Entry(control_frame1, width=10)
        self.setpoint_entry.pack(side=tk.LEFT, padx=5)
        setpoint_button = ttk.Button(control_frame1, text="Set Temp", command=self.set_setpoint)
        setpoint_button.pack(side=tk.LEFT, padx=5)

        # Time window controls
        ttk.Label(control_frame1, text="Display Window:").pack(side=tk.LEFT, padx=(20,0))
        self.time_window_var = tk.StringVar(value="60")
        time_window_combo = ttk.Combobox(control_frame1, textvariable=self.time_window_var, 
                                        values=["30", "60", "120", "300", "600"], width=8)
        time_window_combo.pack(side=tk.LEFT, padx=5)
        time_window_combo.bind("<<ComboboxSelected>>", self.on_time_window_change)
        time_window_combo.bind("<Return>", self.on_time_window_change)  # Allow manual entry
        ttk.Label(control_frame1, text="sec").pack(side=tk.LEFT)
        time_window_button = ttk.Button(control_frame1, text="Set", command=self.on_time_window_change)
        time_window_button.pack(side=tk.LEFT, padx=2)

        # Update interval controls
        ttk.Label(control_frame1, text="Update Interval:").pack(side=tk.LEFT, padx=(20,0))
        self.update_interval_var = tk.StringVar(value="1.0")
        update_interval_combo = ttk.Combobox(control_frame1, textvariable=self.update_interval_var,
                                           values=["0.5", "1.0", "2.0", "5.0"], width=6)
        update_interval_combo.pack(side=tk.LEFT, padx=5)
        update_interval_combo.bind("<<ComboboxSelected>>", self.on_update_interval_change)
        update_interval_combo.bind("<Return>", self.on_update_interval_change)
        ttk.Label(control_frame1, text="sec").pack(side=tk.LEFT)
        update_interval_button = ttk.Button(control_frame1, text="Set", command=self.on_update_interval_change)
        update_interval_button.pack(side=tk.LEFT, padx=2)

        # Second row of controls
        control_frame2 = ttk.Frame(main_control_frame)
        control_frame2.pack(fill=tk.X, pady=2)

        # Heater controls.
        ttk.Label(control_frame2, text="Heater Mode:").pack(side=tk.LEFT)
        self.heater_manual_var = tk.BooleanVar(value=False)
        self.heater_mode_check = ttk.Checkbutton(
            control_frame2,
            text="Manual",
            variable=self.heater_manual_var,
            command=self.on_heater_mode_change)
        self.heater_mode_check.pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame2, text="Forced Heater Value:").pack(side=tk.LEFT, padx=(10,0))
        self.heater_entry = ttk.Entry(control_frame2, width=10)
        self.heater_entry.pack(side=tk.LEFT, padx=5)
        # Disable the forced heater entry unless manual mode is active.
        self.heater_entry.config(state="disabled")
        heater_button = ttk.Button(control_frame2, text="Set Heater", command=self.set_heater)
        heater_button.pack(side=tk.LEFT, padx=5)

        # Heater range controls
        ttk.Label(control_frame2, text="Heater Range:").pack(side=tk.LEFT, padx=(20,0))
        self.heater_range_var = tk.StringVar(value="low")
        heater_range_combo = ttk.Combobox(control_frame2, textvariable=self.heater_range_var,
                                         values=["off", "low", "mid", "high"], width=8)
        heater_range_combo.pack(side=tk.LEFT, padx=5)
        heater_range_combo.bind("<<ComboboxSelected>>", self.on_heater_range_change)

        # Third row of controls - PID controls
        control_frame3 = ttk.Frame(main_control_frame)
        control_frame3.pack(fill=tk.X, pady=2)

        # PID P value controls
        ttk.Label(control_frame3, text="PID P:").pack(side=tk.LEFT)
        self.pid_p_entry = ttk.Entry(control_frame3, width=8)
        self.pid_p_entry.pack(side=tk.LEFT, padx=2)
        pid_p_button = ttk.Button(control_frame3, text="Set P", command=self.set_pid_p)
        pid_p_button.pack(side=tk.LEFT, padx=2)

        # PID I value controls
        ttk.Label(control_frame3, text="I:").pack(side=tk.LEFT, padx=(10,0))
        self.pid_i_entry = ttk.Entry(control_frame3, width=8)
        self.pid_i_entry.pack(side=tk.LEFT, padx=2)
        pid_i_button = ttk.Button(control_frame3, text="Set I", command=self.set_pid_i)
        pid_i_button.pack(side=tk.LEFT, padx=2)

        # PID D value controls
        ttk.Label(control_frame3, text="D:").pack(side=tk.LEFT, padx=(10,0))
        self.pid_d_entry = ttk.Entry(control_frame3, width=8)
        self.pid_d_entry.pack(side=tk.LEFT, padx=2)
        pid_d_button = ttk.Button(control_frame3, text="Set D", command=self.set_pid_d)
        pid_d_button.pack(side=tk.LEFT, padx=2)

        # Set all PID values at once
        pid_all_button = ttk.Button(control_frame3, text="Set All PID", command=self.set_all_pid)
        pid_all_button.pack(side=tk.LEFT, padx=(10,2))

        # Fourth row - PID display and status
        control_frame4 = ttk.Frame(main_control_frame)
        control_frame4.pack(fill=tk.X, pady=2)

        # PID display (read-only)
        ttk.Label(control_frame4, text="Current PID:").pack(side=tk.LEFT)
        self.pid_display_var = tk.StringVar(value="P=0, I=0, D=0")
        ttk.Label(control_frame4, textvariable=self.pid_display_var, 
                 relief=tk.SUNKEN, width=25).pack(side=tk.LEFT, padx=5)

        # Status frame
        status_frame = ttk.Frame(main_control_frame)
        status_frame.pack(fill=tk.X, pady=2)

        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.status_var, 
                 relief=tk.SUNKEN, width=60).pack(side=tk.LEFT, padx=5)

        # Create the matplotlib figure and axes.
        self.fig = Figure(figsize=(10, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Temperature and Heater Output")
        self.ax.set_xlabel("Time")
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        # Create a twin axis for heater output and store it.
        self.ax2 = self.ax.twinx()

        # Embed the figure in the Tkinter window.
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def read_loop(self):
        """Background loop that queries the temperature and heater values at the specified interval."""
        while self.running:
            current_time = time.time()
            temp = self.lakeshore.read_temperature()
            heater = self.lakeshore.read_heater()
            if temp is not None:
                self.data.append((current_time, temp))
            if heater is not None:
                self.heater_data.append((current_time, heater))
            time.sleep(self.update_interval)

    def update_plot(self):
        """
        Update the live plot once per second.
        Only the last time_window seconds of data is displayed.
        Temperature is plotted on the left y-axis (blue),
        while heater output is plotted on the right y-axis (red).
        """
        now = time.time()
        time_cutoff = now - self.time_window

        # Keep only data from the specified time window.
        self.data = [(t, temp) for (t, temp) in self.data if t >= time_cutoff]
        self.heater_data = [(t, heater) for (t, heater) in self.heater_data if t >= time_cutoff]

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
        if len(dates_temp) > 0 and len(temps) > 0:
            self.ax.plot_date(dates_temp, temps, fmt="o-", markersize=3, color='blue', label="Temperature")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Temperature (K)", color="blue")
        self.ax.tick_params(axis='y', labelcolor='blue')
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

        # Plot heater output on the right y-axis.
        if len(dates_heater) > 0 and len(heaters) > 0:
            self.ax2.plot_date(dates_heater, heaters, fmt="s--", markersize=3, color='red', label="Heater")
        self.ax2.set_ylabel("Heater Output (%)", color="red")
        self.ax2.tick_params(axis='y', labelcolor='red')

        # Update title with time window info
        self.ax.set_title(f"Temperature and Heater Output (Last {self.time_window} seconds)")

        self.fig.autofmt_xdate()
        self.canvas.draw()

        self.after(1000, self.update_plot)

    def update_pid_display(self):
        """Update the PID display every 1 minute."""
        try:
            p, i, d = self.lakeshore.get_pid_values()
            self.pid_display_var.set(f"P={p:.2f}, I={i:.2f}, D={d:.2f}")
        except Exception as e:
            self.pid_display_var.set("PID read error")
            print("Error reading PID values:", e)
        
        # Schedule next update
        self.after(60000, self.update_pid_display)

    def on_update_interval_change(self, event=None):
        """Called when the update interval changes."""
        try:
            interval_value = float(self.update_interval_var.get())
            if interval_value <= 0:
                self.status_var.set("Update interval must be positive")
                return
            if interval_value < 0.1:
                self.status_var.set("Update interval should be at least 0.1 seconds to avoid communication issues")
                return
            self.update_interval = interval_value
            self.status_var.set(f"Update interval changed to {self.update_interval} seconds")
        except ValueError:
            self.status_var.set("Invalid update interval. Please enter a positive number.")

    def on_time_window_change(self, event=None):
        """Called when the time window combobox selection changes or button is pressed."""
        try:
            time_value = float(self.time_window_var.get())
            if time_value <= 0:
                self.status_var.set("Time window must be positive")
                return
            self.time_window = int(time_value)
            self.status_var.set(f"Display window changed to {self.time_window} seconds")
        except ValueError:
            self.status_var.set("Invalid time window value. Please enter a positive number.")

    def on_heater_range_change(self, event=None):
        """Called when the heater range combobox selection changes."""
        try:
            range_setting = self.heater_range_var.get()
            self.lakeshore.set_heater_range(range_setting)
            self.status_var.set(f"Heater range set to {range_setting}")
        except Exception as e:
            self.status_var.set(f"Error setting heater range: {e}")

    def set_setpoint(self):
        """Called when the Temperature Setpoint button is pressed."""
        try:
            value = float(self.setpoint_entry.get())
            self.lakeshore.set_setpoint(value)
            self.status_var.set(f"Temperature setpoint set to {value} K")
        except ValueError:
            self.status_var.set("Invalid temperature setpoint. Please enter a number.")
        except Exception as e:
            self.status_var.set(f"Error setting setpoint: {e}")

    def on_heater_mode_change(self):
        """
        Called when the heater mode checkbutton is toggled.
        Switches between manual (forced) mode and PID (auto) mode.
        """
        try:
            manual = self.heater_manual_var.get()
            self.lakeshore.set_heater_mode(manual)
            if manual:
                self.heater_entry.config(state="normal")
                self.status_var.set("Heater mode set to Manual")
            else:
                self.heater_entry.config(state="disabled")
                self.status_var.set("Heater mode set to PID (Auto)")
        except Exception as e:
            self.status_var.set(f"Error setting heater mode: {e}")

    def set_heater(self):
        """Called when the Set Heater button is pressed (only active in manual mode)."""
        try:
            value = float(self.heater_entry.get())
            self.lakeshore.set_heater_output(value)
            self.status_var.set(f"Heater output forced to {value}%")
        except ValueError:
            self.status_var.set("Invalid heater value. Please enter a number.")
        except Exception as e:
            self.status_var.set(f"Error setting heater output: {e}")

    def set_pid_p(self):
        """Called when the Set P button is pressed."""
        try:
            p_value = float(self.pid_p_entry.get())
            # Validate P value range (0.1 to 1000 based on your driver document)
            if not (0.1 <= p_value <= 1000):
                self.status_var.set("P value must be between 0.1 and 1000")
                return
            
            self.lakeshore.set_pid_p(p_value)
            self.status_var.set(f"PID P value set to {p_value}")
            
            # Update the PID display immediately
            self.after(500, self.update_pid_display)  # Short delay to allow instrument to update
            
        except ValueError:
            self.status_var.set("Invalid P value. Please enter a number.")
        except Exception as e:
            self.status_var.set(f"Error setting PID P value: {e}")

    def set_pid_i(self):
        """Called when the Set I button is pressed."""
        try:
            i_value = float(self.pid_i_entry.get())
            # Validate I value range (0.1 to 1000 based on your driver document)
            if not (0.1 <= i_value <= 1000):
                self.status_var.set("I value must be between 0.1 and 1000")
                return
            
            self.lakeshore.set_pid_i(i_value)
            self.status_var.set(f"PID I value set to {i_value}")
            
            # Update the PID display immediately
            self.after(500, self.update_pid_display)
            
        except ValueError:
            self.status_var.set("Invalid I value. Please enter a number.")
        except Exception as e:
            self.status_var.set(f"Error setting PID I value: {e}")

    def set_pid_d(self):
        """Called when the Set D button is pressed."""
        try:
            d_value = float(self.pid_d_entry.get())
            # Validate D value range (0 to 200 based on your driver document)
            if not (0 <= d_value <= 200):
                self.status_var.set("D value must be between 0 and 200")
                return
            
            self.lakeshore.set_pid_d(d_value)
            self.status_var.set(f"PID D value set to {d_value}")
            
            # Update the PID display immediately
            self.after(500, self.update_pid_display)
            
        except ValueError:
            self.status_var.set("Invalid D value. Please enter a number.")
        except Exception as e:
            self.status_var.set(f"Error setting PID D value: {e}")

    def set_all_pid(self):
        """Called when the Set All PID button is pressed."""
        try:
            p_value = float(self.pid_p_entry.get())
            i_value = float(self.pid_i_entry.get())
            d_value = float(self.pid_d_entry.get())
            
            # Validate all PID values
            if not (0.1 <= p_value <= 1000):
                self.status_var.set("P value must be between 0.1 and 1000")
                return
            if not (0.1 <= i_value <= 1000):
                self.status_var.set("I value must be between 0.1 and 1000")
                return
            if not (0 <= d_value <= 200):
                self.status_var.set("D value must be between 0 and 200")
                return
            
            self.lakeshore.set_full_pid(p_value, i_value, d_value)
            self.status_var.set(f"All PID values set: P={p_value}, I={i_value}, D={d_value}")
            
            # Update the PID display immediately
            self.after(500, self.update_pid_display)
            
        except ValueError:
            self.status_var.set("Invalid PID values. Please enter numbers in all fields.")
        except Exception as e:
            self.status_var.set(f"Error setting PID values: {e}")

    def on_close(self):
        """Stop the background thread, close the instrument, and exit."""
        self.running = False
        time.sleep(1.1)  # Give the thread a moment to finish
        try:
            self.lakeshore.close()
        except:
            pass  # Ignore errors during cleanup
        self.destroy()

# -------------------------------
# Main Program Entry Point
# -------------------------------
if __name__ == '__main__':
    app = App()
    app.mainloop()