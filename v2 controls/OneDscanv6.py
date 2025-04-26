import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import matplotlib
import numpy as np
import threading
import time
import datetime
import ESP301
import lockin_driver_v2 as lockin
import SP2500
import Photon_counter_driver as PC
import z_stage_driver as Zstage

zstage = Zstage.Controller(which_port='COM8')
spec = SP2500.Spectrometer()
sr400 = PC.SR400(acquisition_time = 5, discriminator = -0.002)
ESP = ESP301.ESP301()
lockin.open_all_connections()
# Use the 'TkAgg' backend for matplotlib.
matplotlib.use("TkAgg")

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class ScanApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("1D Scan Application")
        self.geometry("1100x600")  # Adjust window size as needed
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # ----------------------------------------
        # Variables for scan configuration
        # ----------------------------------------
        self.scan_running = False
        
        # Scan type selection
        self.scan_type_var = tk.StringVar(value="Lock-In vs Time")
        
        # Independent/dependent variable labels
        self.independent_var = tk.StringVar(value="Time (s)")
        self.dependent_var   = tk.StringVar(value="Lock-In Reading")
        
        # Range definition
        self.start_var = tk.StringVar(value="0")
        self.end_var   = tk.StringVar(value="10")
        self.step_var  = tk.StringVar(value="1")
        
        # Number of averages (number of repeated scans)
        self.averages_var = tk.StringVar(value="1")
        
        # ---- New: Wait Time (seconds) ----
        self.wait_time_var = tk.StringVar(value="1.0")  # default 1 second

        # ---- New: Toggle for plot mode (Average vs All scans) ----
        # We'll use a BooleanVar. True => show average, False => show all scans.
        self.display_average_var = tk.BooleanVar(value=True)
        
        # Master data arrays
        self.scan_num_data = []  # Stores the scan number for each measurement
        self.x_data        = []
        self.y_data        = []
        self.y_data2       = []
        self.y_data3       = []
        self.y_data4       = []
        
        # Metadata variables
        self.fluence_var          = tk.StringVar(value="N/A")
        self.device_var           = tk.StringVar(value="Device1")
        self.wavelength_var       = tk.StringVar(value="650 nm")
        self.probe_power_var      = tk.StringVar(value="N/A")
        self.probe_wavelength_var = tk.StringVar(value="N/A")
        
        # Paragraph-style notes (multi-line)
        self.notes_text = None
        
        # File saving variables
        self.save_path_var = tk.StringVar(value="")
        self.filename_var  = tk.StringVar(value="scan_data.txt")

        # Create the GUI widgets
        self.create_widgets()
        
        # Create figure and axes for live plotting
        self.fig, self.ax = plt.subplots(figsize=(5, 4))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y")
        self.ax.set_title("Live Scan Plot")
        
        # Periodically update the plot
        self.update_plot()
        
    def on_closing(self):
        """
        Called when the GUI window is closed.
        Stops the scan loop, waits briefly for the scan thread to finish,
        closes GPIB connections, and then destroys the GUI.
        """
        # Stop any running scan loop
        self.scan_running = False
        # Optional: wait a bit to allow the scan thread to finish cleanly.
        time.sleep(0.2)
        # Close persistent lockin connections
        lockin.close_all_connections()
        # Destroy the GUI window
        self.destroy()
        
    def create_widgets(self):
        """Create and place all the widgets in the main window."""
        
        # Main frame on the left for controls, using grid layout
        control_frame = ttk.Frame(self)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        # Configure two columns in this control_frame
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        
        # Right side panel for the plot
        self.plot_frame = ttk.Frame(self)
        self.plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # --------------------------------------------------------
        # Sub-frame 1: Scan Configuration
        # --------------------------------------------------------
        scan_config_frame = ttk.LabelFrame(control_frame, text="Scan Configuration")
        scan_config_frame.grid(row=0, column=0, sticky="nw", padx=5, pady=5)
        
        
        
        # Independent and Dependent variable labels
        ttk.Label(scan_config_frame, text="Independent Variable:").pack(anchor=tk.W, padx=2, pady=2)
        independent_var_options = [
            "X pos",
            "Y pos",
            "Z pos",
            "Delay pos",
            "Delay time (ps)",
            "Waveplate angle",
            "Wavelength",
            "Dummy"
        ]
        independent_var_menu = ttk.OptionMenu(scan_config_frame, self.independent_var, independent_var_options[0], *independent_var_options)
        independent_var_menu.pack(fill=tk.X, padx=5, pady=2)
        #ttk.Label(scan_config_frame, text="Independent Label:").pack(anchor=tk.W, padx=2, pady=2)
        #ttk.Entry(scan_config_frame, textvariable=self.independent_var).pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(scan_config_frame, text="Independent Variable:").pack(anchor=tk.W, padx=2, pady=2)
        dependent_var_options = [
            "Photon counter",
            "deltaR/R",
            "lockin 1",
            "lockin 2",
            "lockin 3",
            "X and Y Current",
            "X+, Y+, and Y- Current"
        ]
        dependent_var_menu = ttk.OptionMenu(scan_config_frame, self.dependent_var, dependent_var_options[0], *dependent_var_options)
        dependent_var_menu.pack(fill=tk.X, padx=5, pady=2)

        # --------------------------------------------------------
        # Sub-frame 2: Range & Averages
        # --------------------------------------------------------
        range_frame = ttk.LabelFrame(control_frame, text="Range & Averages")
        range_frame.grid(row=1, column=0, sticky="nw", padx=5, pady=5)
        
        # Start point
        ttk.Label(range_frame, text="Start Point:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(range_frame, textvariable=self.start_var).pack(fill=tk.X, padx=5, pady=2)
        
        # End point
        ttk.Label(range_frame, text="End Point:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(range_frame, textvariable=self.end_var).pack(fill=tk.X, padx=5, pady=2)
        
        # Step
        ttk.Label(range_frame, text="Step:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(range_frame, textvariable=self.step_var).pack(fill=tk.X, padx=5, pady=2)
        
        # Averages
        ttk.Label(range_frame, text="Averages (# of scans):").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(range_frame, textvariable=self.averages_var).pack(fill=tk.X, padx=5, pady=2)

        # ---- New: Wait time (seconds) ----
        ttk.Label(range_frame, text="Wait Time (sec):").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(range_frame, textvariable=self.wait_time_var).pack(fill=tk.X, padx=5, pady=2)

        toggle_btn = ttk.Checkbutton(
            range_frame, 
            text="Display Averages Only",
            variable=self.display_average_var,
            onvalue=True,
            offvalue=False
        )
        toggle_btn.pack(anchor=tk.W, padx=5, pady=10)
        
        start_button = ttk.Button(range_frame, text="Start Scan", command=self.start_scan)
        start_button.pack(fill=tk.X, padx=5, pady=(10,2))
        
        stop_button = ttk.Button(range_frame, text="Stop Scan", command=self.stop_scan)
        stop_button.pack(fill=tk.X, padx=5, pady=2)

        # --------------------------------------------------------
        # Sub-frame for toggling plot mode
        # --------------------------------------------------------
        #plot_mode_frame = ttk.LabelFrame(control_frame, text="Plot Mode")
        #plot_mode_frame.grid(row=2, column=0, sticky="nw", padx=5, pady=5)

        # ---- New: Checkbutton to toggle between average or all scans ----
        

        # --------------------------------------------------------
        # Sub-frame 3: Metadata (column 1)
        # --------------------------------------------------------
        metadata_frame = ttk.LabelFrame(control_frame, text="Metadata")
        metadata_frame.grid(row=1, column=1, sticky="nw", padx=5, pady=5)

        # Device Name
        ttk.Label(metadata_frame, text="Device Name:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(metadata_frame, textvariable=self.device_var).pack(fill=tk.X, padx=5, pady=2)
        
        # Pump Power
        ttk.Label(metadata_frame, text="Pump Power:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(metadata_frame, textvariable=self.fluence_var).pack(fill=tk.X, padx=5, pady=2)
        
        # Pump Wavelength
        ttk.Label(metadata_frame, text="Pump Wavelength:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(metadata_frame, textvariable=self.wavelength_var).pack(fill=tk.X, padx=5, pady=2)
        
        # Probe Power
        ttk.Label(metadata_frame, text="Probe Power:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(metadata_frame, textvariable=self.probe_power_var).pack(fill=tk.X, padx=5, pady=2)
        
        # Probe Wavelength
        ttk.Label(metadata_frame, text="Probe Wavelength:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(metadata_frame, textvariable=self.probe_wavelength_var).pack(fill=tk.X, padx=5, pady=2)
        
        # Paragraph-style text box for Notes
        ttk.Label(metadata_frame, text="Additional Notes:").pack(anchor=tk.W, padx=2, pady=2)
        self.notes_text = ScrolledText(metadata_frame, wrap=tk.WORD, width=30, height=5)
        self.notes_text.pack(fill=tk.X, padx=5, pady=2)

        # --------------------------------------------------------
        # Sub-frame 5: File Saving (spans both columns)
        # --------------------------------------------------------
        file_save_frame = ttk.LabelFrame(control_frame, text="File Saving")
        file_save_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        ttk.Label(file_save_frame, text="Save Path:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(file_save_frame, textvariable=self.save_path_var).grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        file_save_frame.columnconfigure(1, weight=1)  # allow stretching
        
        browse_button = ttk.Button(file_save_frame, text="Browse", command=self.browse_path)
        browse_button.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        
        ttk.Label(file_save_frame, text="Filename:").grid(row=2, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(file_save_frame, textvariable=self.filename_var).grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        
        save_button = ttk.Button(file_save_frame, text="Save Data", command=self.save_data)
        save_button.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

    def browse_path(self):
        """Open a dialog to select a directory for saving data."""
        directory = filedialog.askdirectory()
        if directory:
            self.save_path_var.set(directory)

    def start_scan(self):
        """Start the scanning process in a separate thread."""
        if not self.scan_running:
            self.scan_running = True
            
            # Clear all data arrays
            self.scan_num_data.clear()
            self.x_data.clear()
            self.y_data.clear()
            self.y_data2.clear()
            self.y_data3.clear()
            self.y_data4.clear()
            
            scan_thread = threading.Thread(target=self.scan_loop, daemon=True)
            scan_thread.start()

    def stop_scan(self):
        """Signal the scanning thread to stop."""
        self.scan_running = False

    def scan_loop(self):
        """
        Perform the multi-scan loop over a specified range:
          - Parse the start, end, step, and number of averages.
          - For each scan in 1..averages:
             For each x in [start, end] stepping by 'step':
                Measure data (possibly 1 or 2 dependent variables).
                Store the data along with 'scan_number'.
                Wait user-specified seconds between points.
        """
        try:
            start_val = float(self.start_var.get())
            end_val   = float(self.end_var.get())
            step_val  = float(self.step_var.get())
            n_avg     = int(self.averages_var.get())
            wait_time = float(self.wait_time_var.get())
        except ValueError:
            print("Error: Could not parse start/end/step/averages/wait_time. Make sure they are numeric.")
            self.scan_running = False
            return
        
        # Build the list of X points (cautious about floating rounding issues)
        x_points = np.arange(start_val, end_val + 0.5*step_val, step_val)
        
        
        # Run multiple scans
        for scan_number in range(1, n_avg + 1):
            print(scan_number)
            if not self.scan_running:
                break










            
            for x_val in x_points:
                if not self.scan_running:
                    break
                if self.independent_var.get() == "Wavelength":
                    spec.set_nm(x_val)
                if self.independent_var.get() == "Waveplate angle":
                    moved = ESP.moveZ(x_val-36)
                    while moved != True:
                        time.sleep(2)
                        moved = ESP.moveZ(x_val)
                if self.independent_var.get() == "Delay pos":
                    moved = ESP.moveZ(x_val)
                    while moved != True:
                        time.sleep(2)
                        moved = ESP.moveZ(x_val)
                if self.independent_var.get() == "X pos":
                    moved = ESP.moveX(x_val)
                    while moved != True:
                        time.sleep(2)
                        moved = ESP.moveX(x_val)
                if self.independent_var.get() == "Y pos":
                    moved = ESP.moveY(x_val)
                    while moved != True:
                        time.sleep(2)
                        moved = ESP.moveY(x_val)
                if self.independent_var.get() == "Z pos":
                    zstage.move_mm(x_val, relative = False)
                if self.independent_var.get() == "Delay time (ps)":
                    target_pos = -39.4 + x_val*-.15
                    if target_pos < -105:
                        target_pos = -105
                    moved = ESP.moveZ(target_pos)
                    while moved != True:
                        time.sleep(2)
                        moved = ESP.moveZ(target_pos)
                if self.independent_var.get() == "Dummy":
                    print("stepped")
                time.sleep(wait_time)
                
                if self.dependent_var.get() == "X and Y Current":
                    xcurrval = lockin.readx1()
                    xcurrych = lockin.ready1()
                    ycurrval = lockin.readx2()
                    ycurrych = lockin.ready2()
                    result = x_val,xcurrval,ycurrval,xcurrych,ycurrych
                if self.dependent_var.get() == "X+, Y+, and Y- Current":
                    xcurpos = lockin.readx1()
                    ycurpos = lockin.readx2()
                    ycurneg = lockin.readx3()
                    result = x_val,xcurpos,(-1*(xcurpos+ycurpos+ycurneg)),ycurpos,ycurneg
                if self.dependent_var.get() == "Photon counter":
                    counts = sr400.acquire()
                    result = x_val,counts
                if self.dependent_var.get() == "lockin 1":
                    lockval = lockin.readx1()
                    result = x_val,lockval
                if self.dependent_var.get() == "lockin 2":
                    lockval = lockin.readx2()
                    result = x_val,lockval
                if self.dependent_var.get() == "lockin 3":
                    lockval = lockin.readx3()
                    result = x_val,lockval
                if self.dependent_var.get() == "deltaR/R":
                    R = lockin.readx1()
                    dR = lockin.readx2()
                    result = x_val,dR,R
                    

                if isinstance(result, tuple):
                    if len(result) == 5:
                        # x, y1, y2
                        x_meas, y_val1, y_val2, y_val3, y_val4 = result
                        self.scan_num_data.append(scan_number)
                        self.x_data.append(x_meas)
                        self.y_data.append(y_val1)
                        self.y_data2.append(y_val2)
                        self.y_data3.append(y_val3)
                        self.y_data4.append(y_val4)
                    elif len(result) == 3:
                        # x, y1, y2
                        x_meas, y_val1, y_val2 = result
                        self.scan_num_data.append(scan_number)
                        self.x_data.append(x_meas)
                        self.y_data.append(y_val1)
                        self.y_data2.append(y_val2)
                    else:
                        # x, y
                        x_meas, y_val = result
                        self.scan_num_data.append(scan_number)
                        self.x_data.append(x_meas)
                        self.y_data.append(y_val)
                        self.y_data2.append(None)
                else:
                    # Single value
                    self.scan_num_data.append(scan_number)
                    self.x_data.append(x_val)
                    self.y_data.append(result)
                    self.y_data2.append(None)
                
                    
        self.scan_running = False
        print("Scanning complete.")
        self.save_data()



    # -----------------------------------------------------------------
    # Plot updating
    # -----------------------------------------------------------------
    def update_plot(self):
        """ Periodically refresh the plot. Either display the averaged data
            or show all scans on the same plot based on self.display_average_var. 
        """
        self.ax.clear()
        
        # Are we displaying AVERAGE data or ALL scans?
        if self.display_average_var.get():
            # ----------------------
            # 1) Display Averages
            # ----------------------
            aggregator = {}
            for scan_num, x_val, y_val, y2_val in zip(self.scan_num_data, 
                                                      self.x_data, 
                                                      self.y_data, 
                                                      self.y_data2):
                # Round X to avoid floating mismatch
                x_key = round(x_val, 6)
                if x_key not in aggregator:
                    aggregator[x_key] = []
                aggregator[x_key].append((y_val, y2_val))
            
            # Build arrays of (x_unique, avg_y, avg_y2)
            x_plot = []
            y_plot = []
            y2_plot = []
            
            # Check if there is any Y2 data
            y2_present = any(y2 is not None for y2 in self.y_data2)
            
            for x_key in sorted(aggregator.keys()):
                pairs = aggregator[x_key]  # list of (y, y2)
                
                y_vals = [p[0] for p in pairs]
                y2_vals = [p[1] for p in pairs if p[1] is not None]
                
                avg_y = np.mean(y_vals) if len(y_vals) > 0 else 0
                if y2_present and len(y2_vals) > 0:
                    avg_y2 = np.mean(y2_vals)
                else:
                    avg_y2 = None
                
                x_plot.append(x_key)
                if self.dependent_var.get() == "deltaR/R":
                    y_plot.append(avg_y/avg_y2)
                else:
                    y_plot.append(avg_y)
                    y2_plot.append(avg_y2)
            
            '''# Plot the averaged data
            if y2_present:
                # We have two sets of data
                x_plot_1 = []
                y_plot_1 = []
                x_plot_2 = []
                y_plot_2 = []
                for xx, yy1, yy2 in zip(x_plot, y_plot, y2_plot):
                    if yy2 is None:
                        x_plot_1.append(xx)
                        y_plot_1.append(yy1)
                    else:
                        x_plot_2.append(xx)
                        y_plot_2.append(yy2)
                if x_plot_1:
                    self.ax.plot(x_plot_1, y_plot_1, 'o-', color='tab:blue', label='Dep Var 1 (avg)')
                if x_plot_2:
                    self.ax.plot(x_plot_2, y_plot_2, 's-', color='tab:orange', label='Dep Var 2 (avg)')
                #self.ax.legend(loc='best')'''

            # Only one dependent variable
            if x_plot and y_plot:
                self.ax.plot(x_plot, y_plot, 'o-', color='tab:blue', label='Dep Var (avg)')
                #self.ax.legend(loc='best')
            
        else:
            # ----------------------
            # 2) Display ALL Scans
            # ----------------------
            # Group data by scan number and plot each separately
            scans_dict = {}
            for scan_num, x_val, y_val, y2_val in zip(self.scan_num_data,
                                                      self.x_data, 
                                                      self.y_data, 
                                                      self.y_data2):
                if scan_num not in scans_dict:
                    scans_dict[scan_num] = {
                        "x": [],
                        "y": [],
                        "y2": []
                    }
                scans_dict[scan_num]["x"].append(x_val)
                scans_dict[scan_num]["y"].append(y_val)
                scans_dict[scan_num]["y2"].append(y2_val)
            
            # Check if there is any Y2 data
            y2_present = any(y2 is not None for y2 in self.y_data2)
            
            # Plot each scan
            for scan_num, scan_data in scans_dict.items():
                x_vals = scan_data["x"]
                y_vals = scan_data["y"]
                y2_vals = scan_data["y2"]
                
                '''if y2_present and any(y2 is not None for y2 in y2_vals):
                    # We'll plot y and y2 with different markers
                    # Filter out None for y2
                    y_data_points = [v for v in zip(x_vals, y_vals) if v[1] is not None]
                    y2_data_points = [v for v in zip(x_vals, y2_vals) if v[1] is not None]
                    
                    if y_data_points:
                        x_plot_1, y_plot_1 = zip(*y_data_points)
                        self.ax.plot(x_plot_1, y_plot_1, 'o-', label=f'Scan {scan_num} - Y1')
                    if y2_data_points:
                        x_plot_2, y_plot_2 = zip(*y2_data_points)
                        self.ax.plot(x_plot_2, y_plot_2, 's--', label=f'Scan {scan_num} - Y2')
                else:'''
                # Single dependent variable
                self.ax.plot(x_vals, y_vals, 'o-', label=f'Scan {scan_num}')
            
            #self.ax.legend(loc='best')
        
        # Set labels and title
        self.ax.set_xlabel(self.independent_var.get())
        self.ax.set_ylabel(self.dependent_var.get())
        self.ax.set_title(self.scan_type_var.get())
        
        self.canvas.draw()
        
        # Schedule the next update
        self.after(500, self.update_plot)
        
    # -----------------------------------------------------------------
    # Saving Data
    # -----------------------------------------------------------------
    def save_data(self):
        """
        Save the data with columns in the order:
          ScanNumber, X, Y (and Y2 if present).
        Includes date/time in the metadata.
        """
        if not self.x_data or not self.y_data:
            print("No data to save.")
            return
        
        directory = self.save_path_var.get() or "."
        filename = self.filename_var.get()
        if not filename.endswith(".txt"):
            filename += ".txt"
        
        full_filename = f"{directory}/{filename}"
        
        # Build date/time string
        date_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Grab the notes text
        notes = self.notes_text.get("1.0", tk.END).strip()
        
        # Check if there's any second dependent variable
        y2_present = any(y2 is not None for y2 in self.y_data2)
        
        # Build the header string
        header_lines = [
            f"# Date/Time: {date_time_str}",
            f"# Independent Variable: {self.independent_var.get()}",
            f"# Dependent Variable: {self.dependent_var.get()}",
            f"# Device Name: {self.device_var.get()}",
            f"# Pump Power: {self.fluence_var.get()}",
            f"# Pump Wavelength: {self.wavelength_var.get()}",
            f"# Probe Power: {self.probe_power_var.get()}",
            f"# Probe Wavelength: {self.probe_wavelength_var.get()}",
            f"# Additional Notes: {notes}"
        ]
        
        if self.independent_var.get() == "Waveplate angle" and self.dependent_var.get() == "X and Y Current":
            header_lines.append("# Columns: ScanNumber  WP angle  XcurXch  YcurXch  XcurYch  YcurYch")
            data_to_save = np.column_stack((
                self.scan_num_data, 
                self.x_data,
                self.y_data,
                self.y_data2,
                self.y_data3,
                self.y_data4,
                
            ))
        if self.independent_var.get() == "Delay time" and self.dependent_var.get() == "X+, Y+, and Y- Current":
            header_lines.append("# Columns: ScanNumber  measnum  Xcur+  Xcur-  Ycur+  Ycur-")
            data_to_save = np.column_stack((
                self.scan_num_data, 
                self.x_data,
                self.y_data,
                self.y_data2,
                self.y_data3,
                self.y_data4,
                
            ))
        if self.dependent_var.get() == "deltaR/R" and self.independent_var.get() == "Delay time (ps)":
            header_lines.append("# Columns: ScanNumber  delay_time  deltaR   R")
            data_to_save = np.column_stack((
                self.scan_num_data, 
                self.x_data,
                self.y_data,
                self.y_data2,

            ))
        else:
            header_lines.append("# Columns: ScanNumber  X  Y")
            data_to_save = np.column_stack((
                self.scan_num_data,
                self.x_data,
                self.y_data))
        header_str = "\n".join(header_lines)
        
        # Construct the data array in the order [scan_num, x, y, y2?]
        '''if y2_present:
            clean_y2 = [v if v is not None else np.nan for v in self.y_data2]
            data_to_save = np.column_stack((
                self.scan_num_data, 
                self.x_data,
                self.y_data,
                clean_y2
            ))
        else:
            
            ))
        '''
        try:
            np.savetxt(full_filename, data_to_save, header=header_str, comments="")
            print(f"Data saved to {full_filename}")
        except Exception as e:
            print(f"Error saving file: {e}")

def main():
    app = ScanApp()
    app.mainloop()

if __name__ == "__main__":
    main()
