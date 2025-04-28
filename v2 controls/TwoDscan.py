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
import matplotlib.pyplot as plt
import keithley_driver as keithley
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

zstage = Zstage.Controller(which_port='COM8')
spec = SP2500.Spectrometer()
sr400 = PC.SR400(acquisition_time = 2, discriminator = -0.002)
ESP = ESP301.ESP301()
lockin.open_all_connections()
# Use the 'TkAgg' backend for matplotlib.
matplotlib.use("TkAgg")



class ScanningMicroscopeGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("2D Scan Application")
        self.geometry("1800x1000")  # Adjust as needed

        #self.esp = ESP301.ESP301()
        
        # --- Scanning state ---
        self.scan_running = False
        
        # --- Variables for axes selections ---
        self.x_axis_var = tk.StringVar(value="X pos")
        self.y_axis_var = tk.StringVar(value="Y pos")
        self.z_axis_var = tk.StringVar(value="Lockin 1")
        
        # --- Ranges for X and Y ---
        self.x_start_var = tk.StringVar(value="0")
        self.x_end_var   = tk.StringVar(value="10")
        self.x_step_var  = tk.StringVar(value="1")

        self.y_start_var = tk.StringVar(value="0")
        self.y_end_var   = tk.StringVar(value="5")
        self.y_step_var  = tk.StringVar(value="1")
        
        # --- Other scanning parameters ---
        self.averages_var   = tk.StringVar(value="1")
        self.wait_time_var  = tk.StringVar(value="0.5")

        # --- Metadata ---
        self.device_var           = tk.StringVar(value="Device1")
        self.fluence_var          = tk.StringVar(value="N/A")
        self.wavelength_var       = tk.StringVar(value="650 nm")
        self.probe_power_var      = tk.StringVar(value="N/A")
        self.probe_wavelength_var = tk.StringVar(value="N/A")
        
        # --- Notes and file-saving ---
        self.notes_text = None
        self.save_path_var = tk.StringVar(value="")
        self.filename_var  = tk.StringVar(value="scan2d_data.txt")

        # --- Motion Control ---
        self.wavelength_entry_var = tk.StringVar(value="0")
        self.delay_entry_var = tk.StringVar(value="0")
        self.zpos_entry_var = tk.StringVar(value="0")
        self.xpos_entry_var = tk.StringVar(value="0")
        self.ypos_entry_var = tk.StringVar(value="0")
        self.TG_entry_var = tk.StringVar(value="0")
        self.BG_entry_var = tk.StringVar(value="0")
        self.WP_entry_var = tk.StringVar(value="0")
        self.YD_entry_var = tk.StringVar(value="0")
        self.CL_entry_var = tk.StringVar(value="6e-10")
        self.BGS_entry_var = tk.StringVar(value="0")
        self.BGE_entry_var = tk.StringVar(value="0")

        # --- Initialize data---
        self.data = np.zeros((1,1,1,6))
        self.avg_data = np.zeros((1,1,6))

        # --- Initialize cursor for linecuts and positioning
        # (Physical coordinates)
        self.cursorX = 0.0
        self.cursorY = 0.0

        # (Array indices for linecuts)
        self.cursor_ix = 0
        self.cursor_iy = 0

        self.frame_clicked = 1

        self.x0 = np.arange(0,11,1)
        self.y0 = np.arange(0,6,1)

        self.row = 0
        self.column = 0
        self.currlimit = 6e-10

        # Initialize a dummy image

        # Setup the 2x2 grid of plots
        self.fig, self.ax = plt.subplots(nrows=2, ncols=2)
        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.canvas.mpl_connect("button_press_event", self.on_click)
        
        # Initialize dummy images for each subplot
        self.image_data_1 = np.random.rand(20, 20) * 10e-6
        self.image_plot_1 = self.ax[0, 0].imshow(self.image_data_1, cmap='bwr', origin='lower')
        self.ax[0, 0].set_title("Z data1")
        self.ax[0, 0].set_xlabel("X Axis")
        self.ax[0, 0].set_ylabel("Y Axis")
        self.fig.colorbar(self.image_plot_1, ax=self.ax[0, 0], orientation='vertical')

        self.linecutX = self.ax[0, 1].plot(self.image_data_1[0])
        self.ax[0, 1].set_title("X linecut")
        self.ax[0, 1].set_xlabel("X Axis")
        self.ax[0, 1].set_ylabel("Y Axis")

        self.linecutY = self.ax[1, 0].plot(self.image_data_1[:,0])
        self.ax[1, 0].set_title("Y linecut")
        self.ax[1, 0].set_xlabel("X Axis")
        self.ax[1, 0].set_ylabel("Y Axis")

        self.image_data_2 = np.random.rand(20, 20) * 10e-6
        self.image_plot_2 = self.ax[1, 1].imshow(self.image_data_2, cmap='viridis', origin='lower')
        self.ax[1, 1].set_title("Z data2")
        self.ax[1, 1].set_xlabel("X Axis")
        self.ax[1, 1].set_ylabel("Y Axis")
        self.fig.colorbar(self.image_plot_2, ax=self.ax[1, 1], orientation='vertical')



        # Control panel frame
        control_frame = ttk.Frame(self)
        control_frame.pack(side=tk.LEFT, fill=tk.X)

        # Configure the control_frame for two columns
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)

        # ------------------------------------------------------------
        # 1) Frame for selecting X, Y, and Z measurements
        # ------------------------------------------------------------
        axes_frame = ttk.LabelFrame(control_frame, text="Axes / Measurements")
        axes_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # X axis drop-down
        ttk.Label(axes_frame, text="X Axis:").pack(anchor=tk.W)
        x_options = ["X pos", "Y pos", "Z pos", "Delay pos", "Delay time (ps)", "Waveplate angle", "Wavelength", "Top gate", "Back gate", "Gate line cut (set TG)", "dummy", "Reverse delay time (ps)", "Delay time (ps)_yaxis", "Reverse Delay time (ps)_yaxis"]
        x_menu = ttk.OptionMenu(axes_frame, self.x_axis_var, x_options[0], *x_options)
        x_menu.pack(fill=tk.X)

        # Y axis drop-down
        ttk.Label(axes_frame, text="Y Axis:").pack(anchor=tk.W)
        y_options = ["X pos", "Y pos", "Z pos", "Delay pos", "Delay time (ps)", "Waveplate angle", "Wavelength", "Top gate", "Back gate", "Gate line cut (set TG)", "dummy", "Reverse delay time (ps)", "Delay time (ps)_yaxis", "Reverse Delay time (ps)_yaxis"]
        y_menu = ttk.OptionMenu(axes_frame, self.y_axis_var, y_options[1], *y_options)
        y_menu.pack(fill=tk.X)

        # Z measurement drop-down
        ttk.Label(axes_frame, text="Z Measurement:").pack(anchor=tk.W)
        z_options = [
            "Photon counter",
            "deltaR/R",
            "deltaR/R alternate",
            "lockin 1",
            "lockin 2",
            "lockin 3",
            "X and Y Current",
            "X+, Y+, and Y- Current",
            "random"
        ]
        z_menu = ttk.OptionMenu(axes_frame, self.z_axis_var, z_options[0], *z_options)
        z_menu.pack(fill=tk.X)
        
       
        # ------------------------------------------------------------
        # 2) Frame for defining X and Y ranges
        # ------------------------------------------------------------
        range_frame = ttk.LabelFrame(control_frame, text="Range & Averages")
        range_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # X Range
        ttk.Label(range_frame, text="X Start:").pack(anchor=tk.W)
        ttk.Entry(range_frame, textvariable=self.x_start_var).pack(fill=tk.X)
        
        ttk.Label(range_frame, text="X End:").pack(anchor=tk.W)
        ttk.Entry(range_frame, textvariable=self.x_end_var).pack(fill=tk.X)
        
        ttk.Label(range_frame, text="X Step:").pack(anchor=tk.W)
        ttk.Entry(range_frame, textvariable=self.x_step_var).pack(fill=tk.X)

        # Y Range
        ttk.Label(range_frame, text="Y Start:").pack(anchor=tk.W)
        ttk.Entry(range_frame, textvariable=self.y_start_var).pack(fill=tk.X)
        
        ttk.Label(range_frame, text="Y End:").pack(anchor=tk.W)
        ttk.Entry(range_frame, textvariable=self.y_end_var).pack(fill=tk.X)
        
        ttk.Label(range_frame, text="Y Step:").pack(anchor=tk.W)
        ttk.Entry(range_frame, textvariable=self.y_step_var).pack(fill=tk.X)
        
        # Averages & wait
        ttk.Label(range_frame, text="Averages (# of scans):").pack(anchor=tk.W)
        ttk.Entry(range_frame, textvariable=self.averages_var).pack(fill=tk.X)

        ttk.Label(range_frame, text="Wait Time (sec):").pack(anchor=tk.W)
        ttk.Entry(range_frame, textvariable=self.wait_time_var).pack(fill=tk.X)

        # Control buttons
        ttk.Button(range_frame, text="Start Scan", command=self.start_scan)\
            .pack(fill=tk.X, pady=(5,2))
        ttk.Button(range_frame, text="Stop Scan", command=self.stop_scan)\
            .pack(fill=tk.X, pady=2)

        # ------------------------------------------------------------
        # 3) Frame for metadata
        # ------------------------------------------------------------
        metadata_frame = ttk.LabelFrame(control_frame, text="Metadata")
        metadata_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        
        ttk.Label(metadata_frame, text="Device Name:").pack(anchor=tk.W)
        ttk.Entry(metadata_frame, textvariable=self.device_var).pack(fill=tk.X)
        
        ttk.Label(metadata_frame, text="Pump Power:").pack(anchor=tk.W)
        ttk.Entry(metadata_frame, textvariable=self.fluence_var).pack(fill=tk.X)
        
        ttk.Label(metadata_frame, text="Pump Wavelength:").pack(anchor=tk.W)
        ttk.Entry(metadata_frame, textvariable=self.wavelength_var).pack(fill=tk.X)
        
        ttk.Label(metadata_frame, text="Probe Power:").pack(anchor=tk.W)
        ttk.Entry(metadata_frame, textvariable=self.probe_power_var).pack(fill=tk.X)
        
        ttk.Label(metadata_frame, text="Probe Wavelength:").pack(anchor=tk.W)
        ttk.Entry(metadata_frame, textvariable=self.probe_wavelength_var).pack(fill=tk.X)
        
        ttk.Label(metadata_frame, text="Notes:").pack(anchor=tk.W)
        self.notes_text = ScrolledText(metadata_frame, wrap=tk.WORD, width=25, height=4)
        self.notes_text.pack(fill=tk.X)

        self.labelsf = ttk.Label(metadata_frame, text="Save Picture Off")
        self.labelsf.pack(fill=tk.X)

        self.switch_var = tk.BooleanVar(value=False)
        self.switch = ttk.Checkbutton(metadata_frame,
            text="",
            variable=self.switch_var,
            command=self.toggle_switch,
            style="Switch.TCheckbutton"
        )
        self.switch.pack(fill=tk.X)

        self.labelAS = ttk.Label(metadata_frame, text="Autosave Off")
        self.labelAS.pack(fill=tk.X)

        self.switch_var_autosave = tk.BooleanVar(value=False)
        self.switchAS = ttk.Checkbutton(metadata_frame,
            text="",
            variable=self.switch_var_autosave,
            command=self.toggle_switch_autosave,
            style="Switch.TCheckbutton"
        )
        self.switchAS.pack(fill=tk.X)

        # ------------------------------------------------------------
        # 4) Frame for file saving
        # ------------------------------------------------------------
        file_frame = ttk.LabelFrame(control_frame, text="File Saving")
        file_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        ttk.Label(file_frame, text="Save Path:").pack(anchor=tk.W)
        ttk.Entry(file_frame, textvariable=self.save_path_var).pack(fill=tk.X)
        
        ttk.Button(file_frame, text="Browse", command=self.browse_path).pack(fill=tk.X, pady=2)
        
        ttk.Label(file_frame, text="Filename:").pack(anchor=tk.W)
        ttk.Entry(file_frame, textvariable=self.filename_var).pack(fill=tk.X)
        
        ttk.Button(file_frame, text="Save Data", command=self.save_data).pack(fill=tk.X, pady=2)


        
        # ------------------------------------------------------------
        # 5) Frame for motion controls
        # ------------------------------------------------------------
        motion_frame = ttk.LabelFrame(control_frame, text="Motion Controls")
        motion_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        # Optionally configure additional columns for proper layout inside the motion_frame
        motion_frame.columnconfigure(0, weight=1)
        motion_frame.columnconfigure(1, weight=1)
        motion_frame.columnconfigure(2, weight=1)


        # Row 0: set Wavelength button and its entry box
        ttk.Button(motion_frame, text="set Wavelength", command=self.set_wavelength)\
            .grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Entry(motion_frame, textvariable=self.wavelength_entry_var)\
            .grid(row=0, column=1, padx=5, pady=5, sticky="ew", columnspan=2)

        # Row 1: set Delay (ps) button and its entry box
        ttk.Button(motion_frame, text="set Delay (ps)", command=self.set_delay)\
            .grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ttk.Entry(motion_frame, textvariable=self.delay_entry_var)\
            .grid(row=1, column=1, padx=5, pady=5, sticky="ew", columnspan=2)

        # Row 2: set z pos button and its entry box
        ttk.Button(motion_frame, text="set z pos", command=self.set_zpos)\
            .grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        ttk.Entry(motion_frame, textvariable=self.zpos_entry_var)\
            .grid(row=2, column=1, padx=5, pady=5, sticky="ew", columnspan=2)

        # Row 3: set x,y pos button and two entry boxes (one for x and one for y)
        ttk.Button(motion_frame, text="set x,y pos", command=self.set_xypos)\
            .grid(row=3, column=0, padx=5, pady=5, sticky="ew")
        ttk.Entry(motion_frame, textvariable=self.xpos_entry_var)\
            .grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        ttk.Entry(motion_frame, textvariable=self.ypos_entry_var)\
            .grid(row=3, column=2, padx=5, pady=5, sticky="ew")

        # Row 4: set TG voltage and its entry box
        ttk.Button(motion_frame, text="set TG voltage", command=self.set_TG)\
            .grid(row=4, column=0, padx=5, pady=5, sticky="ew")
        ttk.Entry(motion_frame, textvariable=self.TG_entry_var)\
            .grid(row=4, column=1, padx=5, pady=5, sticky="ew", columnspan=2)

        # Row 5: set BG voltage and its entry box
        ttk.Button(motion_frame, text="set BG voltage", command=self.set_BG)\
            .grid(row=5, column=0, padx=5, pady=5, sticky="ew")
        ttk.Entry(motion_frame, textvariable=self.BG_entry_var)\
            .grid(row=5, column=1, padx=5, pady=5, sticky="ew", columnspan=2)

        '''# Row 6: set Waveplate and its entry box
        ttk.Button(motion_frame, text="set Waveplate anngle", command=self.set_WP)\
            .grid(row=6, column=0, padx=5, pady=5, sticky="ew")
        ttk.Entry(motion_frame, textvariable=self.WP_entry_var)\
            .grid(row=6, column=1, padx=5, pady=5, sticky="ew", columnspan=2)'''

        '''# Row 7: set Reverse DT Yaxis and its entry box
        ttk.Button(motion_frame, text="set Yaxis Delay", command=self.set_YD)\
            .grid(row=7, column=0, padx=5, pady=5, sticky="ew")
        ttk.Entry(motion_frame, textvariable=self.YD_entry_var)\
            .grid(row=7, column=1, padx=5, pady=5, sticky="ew", columnspan=2)'''

        # Row 6: set gate current limit
        ttk.Button(motion_frame, text="set Current Limit", command=self.set_CL)\
            .grid(row=6, column=0, padx=5, pady=5, sticky="ew")
        ttk.Entry(motion_frame, textvariable=self.CL_entry_var)\
            .grid(row=6, column=1, padx=5, pady=5, sticky="ew", columnspan=2)

        # Row 7: set BG start and end for line gate cut
        ttk.Label(motion_frame, text="Cut BG start : end")\
            .grid(row=7, column=0, padx=5, pady=5, sticky="ew")
        ttk.Entry(motion_frame, textvariable=self.BGS_entry_var)\
            .grid(row=7, column=1, padx=5, pady=5, sticky="ew")
        ttk.Entry(motion_frame, textvariable=self.BGE_entry_var)\
            .grid(row=7, column=2, padx=5, pady=5, sticky="ew")
        
        self.scan_thread = None
        self.is_scanning = False
    def on_click(self, event):
        """
        Callback for mouse clicks in the figure.
        Updates self.cursor_ix, self.cursor_iy (array indices)
        and self.cursorX, self.cursorY (physical coords)
        if the click is in the top-left or bottom-right subplot.
        """
        # Only respond if the user clicked inside an Axes
        if event.inaxes is None:
            return

        # Check which axes were clicked:
        # top-left => self.ax[0,0], bottom-right => self.ax[1,1].
        if event.inaxes in [self.ax[0,0], self.ax[0,1]]:
            self.frame_clicked = 1
        if event.inaxes in [self.ax[1,0], self.ax[1,1]]:
            self.frame_clicked = 2
        if event.inaxes not in [self.ax[0,0], self.ax[1,1]]:
            return

        # Convert the click's x/y data into array indices
        # For imshow(..., origin='lower'), xdata = column index, ydata = row index
        self.cursorX = event.xdata
        self.cursorY = event.ydata
        self.xpos_entry_var.set(str(self.cursorX))
        self.ypos_entry_var.set(str(self.cursorY))
        '''# Make sure these indices are within bounds
        # (Your self.data might be shape: (nAvg, nY, nX, 6))
        n_avg, nY, nX, _ = self.data.shape
        if not (0 <= row < nY and 0 <= col < nX):
            return  # clicked out of the valid image area'''
        print(self.x0)
        # Update the array index cursor
        self.cursor_ix = np.abs(self.x0 - self.cursorX).argmin()
        self.cursor_iy = np.abs(self.y0 - self.cursorY).argmin()
        print(self.cursor_ix)



        # Now update linecuts with the *new indices*
        # We'll just reuse your same function that updates everything:
        self.update_image_data(scanNum=0,
                               x_var=self.x_axis_var.get(),
                               y_var=self.y_axis_var.get(),
                               z_var=self.z_axis_var.get())
    def set_wavelength(self):
        spec.set_nm(float(self.wavelength_entry_var.get()))
    def set_delay(self):
        x = float(self.delay_entry_var.get())
        target_pos = -1.45 + x*-.15
        if target_pos < -105:
            target_pos = -105
        if target_pos > 105:
            target_pos = 105
        moved = ESP.moveZ(target_pos)
        while moved != True:
            time.sleep(2)
            moved = ESP.moveZ(target_pos)
    def set_YD(self):
        x = float(self.YD_entry_var.get())
        target_pos = -1.45 + x*.15
        if target_pos < -105:
            target_pos = -105
        if target_pos > 105:
            target_pos = 105
        moved = ESP.moveZbut2(target_pos)
        while moved != True:
            time.sleep(2)
            moved = ESP.moveZbut2(target_pos)
    def set_WP(self):
        x = float(self.WP_entry_var.get())
        moved = ESP.moveZ(x)
        while moved != True:
            time.sleep(2)
            moved = ESP.moveZ(x)
    def set_CL(self):
        x = float(self.CL_entry_var.get())
        self.currlimit = x
    def set_zpos(self):
        zstage.move_mm(float(self.zpos_entry_var.get()), relative = False)
    def set_xypos(self):
        ESP.moveX(float(self.xpos_entry_var.get()))
        ESP.moveY(float(self.ypos_entry_var.get()))
    def set_TG(self):
        self.stepInd("Top gate",float(self.TG_entry_var.get()))
    def set_BG(self):
        self.stepInd("Back gate",float(self.BG_entry_var.get()))
    def browse_path(self):
        """Open a dialog to select a directory for saving data."""
        directory = filedialog.askdirectory()
        if directory:
            self.save_path_var.set(directory)
            
    def toggle_switch(self):
        # Update the label text based on the switch state
        if self.switch_var:
            self.labelsf.config(text="Save Picture On")
            self.switch_var = False
        else:
            self.labelsf.config(text="Save Picture Off")
            self.switch_var = True
            
    def toggle_switch_autosave(self):
        # Update the label text based on the switch state
        if self.switch_var_autosave:
            self.labelAS.config(text="Autosave On")
            self.switch_var_autosave = False
        else:
            self.labelAS.config(text="Autosave Off")
            self.switch_var_autosave = True

    def start_scan(self):
        """Start the scanning process in a separate thread."""
        if not self.scan_running:
            self.scan_running = True           
            scan_thread = threading.Thread(target=self.run_scan, daemon=True)
            scan_thread.start()
        
    def run_scan(self):
        # get values
        try:
            x_start = float(self.x_start_var.get())
            x_end = float(self.x_end_var.get())
            x_step = float(self.x_step_var.get())

            y_start = float(self.y_start_var.get())
            y_end = float(self.y_end_var.get())
            y_step = float(self.y_step_var.get())
            
            n_avg     = int(self.averages_var.get())
            wait_time = float(self.wait_time_var.get())

            x_var = self.x_axis_var.get()
            y_var = self.y_axis_var.get()
            z_var = self.z_axis_var.get()
        except ValueError:
            print("Error: Could not parse start/end/step/averages/wait_time. Make sure they are numeric.")
            self.scan_running = False
            return

        # make sure steps are correct sign
        if x_start > x_end :
            x_step = -1* abs(x_step)
        if y_start > y_end :
            y_step = -1* abs(y_step)

        # set up axes    
        x0 = np.arange(x_start,x_end+.1*x_step,x_step)
        y0 = np.arange(y_start,y_end+.1*y_step,y_step)
        x2 = []
        y2 = []
        if x_var == "Gate line cut (set TG)":
            BGS = float(self.BGS_entry_var.get())
            BGE = float(self.BGE_entry_var.get())
            x2 = np.linspace(BGS, BGE, len(x0))
        if y_var == "Gate line cut (set TG)":
            BGS = float(self.BGS_entry_var.get())
            BGE = float(self.BGE_entry_var.get())
            y2 = np.linspace(BGS, BGE, len(y0))
        self.x0 = x0
        self.y0 = y0
        X,Y = np.meshgrid(x0,y0)
        x_ticks = np.linspace(x0[0], x0[-1],5)
        y_ticks = np.linspace(y0[0], y0[-1],5)

        
        # set up data array
        self.data = np.zeros((n_avg,len(y0),len(x0),6))
        self.avg_data = np.zeros((len(y0),len(x0),6))
        self.avg_data[:,:,1] = Y
        self.avg_data[:,:,2] = X
        self.after(0, self.prepare_plot, x_var,y_var,z_var,x0,y0)
        for scanNum in range (n_avg):
            if not self.scan_running:
                break
            self.data[scanNum,:,:,0] = scanNum
            self.data[scanNum,:,:,1] = Y
            self.data[scanNum,:,:,2] = X
            #self.stepInd("Delay time (ps)",scanNum*10-50)
            for row in range(len(X)):
                self.row = row
                if not self.scan_running:
                    break
                if y_var == "Gate line cut (set TG)":
                    self.stepInd(y_var,Y[row,0],x_2 = y2[row])
                else:  
                    self.stepInd(y_var,Y[row,0])
                for column in range(len(X[0])):
                    self.column = column
                    if not self.scan_running:
                        break
                    if x_var == "Gate line cut (set TG)":
                        self.stepInd(x_var,X[row,column],x_2 = x2[column])
                    else:  
                        self.stepInd(x_var,X[row,column])
                    time.sleep(wait_time)
                    self.take_data(scanNum,row,column,z_var,X[row,column],Y[row,0])


                    # Update the image data in the main thread
                    self.after(0, self.update_image_data, scanNum, x_var, y_var, z_var)
        self.is_scanning = False
        self.scan_running = False
        if not self.switch_var_autosave:
            self.save_data()
    def take_data(self,scanNum,row,column,z_var,x,y):
        if z_var == "random":
            self.data[scanNum,row,column,3:] = [np.random.rand(),np.random.rand(),100*np.random.rand()]
        if z_var == "lockin 1":
            self.data[scanNum,row,column,3:5] = [lockin.readx1(),lockin.ready1()]
        if z_var == "lockin 2":
            self.data[scanNum,row,column,3:5] = [lockin.readx2(),lockin.ready2()]
        if z_var == "lockin 3":
            self.data[scanNum,row,column,3:5] = [lockin.readx3(),lockin.ready3()]
        if z_var == "deltaR/R":
            dr = lockin.readx2()
            r = lockin.readx1()
            if r == 0:
                r = 1e-9
            self.data[scanNum,row,column,3:] = [dr,r,dr/r]
        if z_var == "deltaR/R alternate":
            self.data[scanNum,row,column,3:5] = [lockin.readx3(),lockin.readx1()]
        if z_var == "Photon counter":
            counts = sr400.acquire()
            self.data[scanNum,row,column,3:] = [counts,counts,counts]
        self.avg_data[row,column,3] = np.mean(self.data[:scanNum+1,row,column,3])
        self.avg_data[row,column,4] = np.mean(self.data[:scanNum+1,row,column,4])
        self.avg_data[row,column,5] = np.mean(self.data[:scanNum+1,row,column,5])
    def stepInd(self, x_var, x, x_2 = 0):
        if x_var == "dummy":
            print("dummy = "+str(x))
        if x_var == "Wavelength":
            spec.set_nm(x)
        if x_var == "Waveplate angle":
            moved = ESP.moveZ(x)
            while moved != True:
                time.sleep(2)
                moved = ESP.moveZ(x)
        if x_var == "Delay time (ps)":
            target_pos = -1.45 + x*-.15
            if target_pos < -105:
                target_pos = -105
            if target_pos > 105:
                target_pos = 105
            ESP.moveZfast(target_pos)
        if x_var == "Delay time (ps)_yaxis":
            target_pos = -1.45 + x*-.15
            if target_pos < -105:
                target_pos = -105
            if target_pos > 105:
                target_pos = 105
            moved = ESP.moveZbut2(target_pos)
            while moved != True:
                time.sleep(2)
                moved = ESP.moveZbut2(target_pos)
        if x_var == "Reverse Delay time (ps)_yaxis":
            target_pos = -1.45 + x*.15
            if target_pos < -105:
                target_pos = -105
            if target_pos > 105:
                target_pos = 105
            moved = ESP.moveZbut2(target_pos)
            while moved != True:
                time.sleep(2)
                moved = ESP.moveZbut2(target_pos)
        if x_var == "Reverse delay time (ps)":
            target_pos = -1.45 + x*-.15
            if target_pos < -105:
                target_pos = -105
            if target_pos > 105:
                target_pos = 105
            moved = ESP.moveZ(target_pos)
            while moved != True:
                time.sleep(2)
                moved = ESP.moveZ(target_pos)
        if x_var == "Delay pos":
            if x < -105:
                x = -105
            if x > 105:
                x = 105
            moved = ESP.moveZ(x)
            while moved != True:
                time.sleep(2)
                moved = ESP.moveZ(x)
        if x_var == "X pos":
            moved = ESP.moveX(x)
            while moved != True:
                time.sleep(2)
                moved = ESP.moveX(x)
        if x_var == "Y pos":
            moved = ESP.moveY(x)
            while moved != True:
                time.sleep(2)
                moved = ESP.moveX(x)
        if x_var == "Z pos":
            zstage.move_mm(x, relative = False)
        if x_var == "Top gate":
            rate = .05
            curr1 = 0
            curr2 = 0
            initial = keithley.get_topgate_voltage()
            while x-initial > 0.0001:
                if not self.scan_running:
                    break
                initial += min(x-initial,rate)
                curr1 = keithley.set_topgate_voltage(initial)
                curr2 = keithley.get_backgate_current()
                    if (abs(curr1) > self.currlimit) or (abs(curr2) > self.currlimit):
                        keithley.ramp_topgate_voltage(0,.05)
                        keithley.ramp_backgate_voltage(0,.05)
                        self.scan_running = False
                        print(f"current limit exceeded when topgate set to {x}\nset both gates to 0V")
                        x = 0
                        initial = 0
                        self.save_data
                        break
                time.sleep(0.005)
            while x-initial < -0.0001:
                if not self.scan_running:
                    break
                initial -= min(initial-x,rate)
                curr1 = keithley.set_topgate_voltage(initial)
                curr2 = keithley.get_backgate_current()
                    if (abs(curr1) > self.currlimit) or (abs(curr2) > self.currlimit):
                        keithley.ramp_topgate_voltage(0,.05)
                        keithley.ramp_backgate_voltage(0,.05)
                        self.scan_running = False
                        print(f"current limit exceeded when topgate set to {x}\nset both gates to 0V")
                        x = 0
                        initial = 0
                        self.save_data
                        break
                time.sleep(0.005)

        if x_var == "Back gate":
            rate = .05
            curr1 = 0
            curr2 = 0
            initial = keithley.get_backgate_voltage()
            while x-initial > 0.0001:
                if not self.scan_running:
                    break
                initial += min(x-initial,rate)
                curr1 = keithley.set_backgate_voltage(initial)
                curr2 = keithley.get_topgate_current()
                    if (abs(curr1) > self.currlimit) or (abs(curr2) > self.currlimit):
                        keithley.ramp_topgate_voltage(0,.05)
                        keithley.ramp_backgate_voltage(0,.05)
                        self.scan_running = False
                        print(f"current limit exceeded when topgate set to {x}\nset both gates to 0V")
                        x = 0
                        initial = 0
                        self.save_data
                        break
                time.sleep(0.005)
            while x-initial < -0.0001:
                if not self.scan_running:
                    break
                initial -= min(initial-x,rate)
                curr1 = keithley.set_backgate_voltage(initial)
                curr2 = keithley.get_topgate_current()
                    if (abs(curr1) > self.currlimit) or (abs(curr2) > self.currlimit):
                        keithley.ramp_topgate_voltage(0,.05)
                        keithley.ramp_backgate_voltage(0,.05)
                        self.scan_running = False
                        print(f"current limit exceeded when topgate set to {x}\nset both gates to 0V")
                        x = 0
                        initial = 0
                        self.save_data
                        break
                time.sleep(0.005)
        if x_var == "Gate line cut (set TG)":
            self.stepInd("Top gate",x)
            self.stepInd("Back gate",x_2)

    def prepare_plot(self, x_var, y_var, z_var, x0, y0):
        """Prepare the plot layout, this runs in the main thread."""
        
        self.image_data_1 = self.data[0,:,:,3]
        self.image_plot_1.set_data(self.image_data_1)
        self.image_plot_1.set_extent([x0[0]-(x0[1]-x0[0])/2, max(x0)+(x0[1]-x0[0])/2, min(y0)-(y0[1]-y0[0])/2,max(y0)+(y0[1]-y0[0])/2])
        self.ax[0, 0].set_title(z_var)
        self.ax[0, 0].set_xlabel(x_var)
        self.ax[0, 0].set_ylabel(y_var)
        self.ax[0, 0].set_aspect('auto')
        self.image_data_2 = self.data[0,:,:,5]
        self.image_plot_2.set_data(self.image_data_2)
        self.image_plot_2.set_extent([x0[0]-(x0[1]-x0[0])/2, max(x0)+(x0[1]-x0[0])/2, min(y0)-(y0[1]-y0[0])/2,max(y0)+(y0[1]-y0[0])/2])
        self.ax[1, 1].set_title(z_var)
        self.ax[1, 1].set_xlabel(x_var)
        self.ax[1, 1].set_ylabel(y_var)
        self.ax[1, 1].set_aspect('auto')
        self.canvas.draw()
        


    def update_image_data(self, scanNum, x_var, y_var, z_var):
        """Update the image data in the plot, this runs in the main thread."""
        averages = True
        if averages:
            plot_data = self.avg_data
        else:
            plot_data = self.data[scanNum,:,:,:]
        self.image_plot_1.set_data(plot_data[:,:,3])
        self.image_plot_1.set_clim(vmin=plot_data[:,:,3].min(), vmax=plot_data[:,:,3].max())
        self.image_plot_2.set_data(plot_data[:,:,4])
        self.image_plot_2.set_clim(vmin=plot_data[:,:,4].min(), vmax=plot_data[:,:,4].max())
        if self.frame_clicked == 1:
            dataid = 3
        if self.frame_clicked == 2:
            dataid = 4
        self.ax[0,1].cla()
        self.linecutX = self.ax[0, 1].plot(plot_data[self.cursor_iy,:,2],plot_data[self.cursor_iy,:,dataid])
        self.ax[0, 1].plot(plot_data[self.cursor_iy,:,2],np.mean(plot_data[0:self.row,:,dataid], axis = 0))
        self.ax[0, 1].set_title("X linecut")
        self.ax[0, 1].set_xlabel(x_var)
        self.ax[0, 1].set_ylabel(z_var)
        self.ax[1,0].cla()
        self.linecutY = self.ax[1, 0].plot(plot_data[:,self.cursor_ix,1],plot_data[:,self.cursor_ix,dataid])
        self.ax[1, 0].set_title("Y linecut")
        self.ax[1, 0].set_xlabel(y_var)
        self.ax[1, 0].set_ylabel(z_var)
        self.canvas.draw()

    def browse_folder(self):
        """Open a file dialog to choose a folder and display the selected path."""
        folder_selected = filedialog.askdirectory()
        if folder_selected:  # If a folder is selected
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder_selected)
        

    def go_to_pos(self):
        x = float(self.Xentry.get())
        y = float(self.Yentry.get())
        ESP.moveX(x)
        ESP.moveY(y)
        print("going!")
    def stop_scan(self):
        """Stops the scanning process."""
        self.scan_running = False
        self.is_scanning = False
        print("Stopping scan...")

    def save_data(self):
        data_to_save = self.data.reshape(-1,6)
        filename = self.save_path_var.get()+'/'+self.filename_var.get()+".txt"
        date_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notes = self.notes_text.get("1.0", tk.END).strip()
        header_lines = [
            f"# Date/Time: {date_time_str}",
            f"# X Variable (fast axis): {self.x_axis_var.get()}",
            f"# Y Variable (slow axis): {self.y_axis_var.get()}",
            f"# Z Variable (measurement): {self.z_axis_var.get()}",
            f"# Device Name: {self.device_var.get()}",
            f"# Pump Power: {self.fluence_var.get()}",
            f"# Pump Wavelength: {self.wavelength_var.get()}",
            f"# Probe Power: {self.probe_power_var.get()}",
            f"# Probe Wavelength: {self.probe_wavelength_var.get()}",
            f"# Additional Notes: {notes}",
            f"#",
            f"# Wavelength Entry: {self.wavelength_entry_var.get()}",
            f"# Delay Entry: {self.delay_entry_var.get()}",
            f"# Z Position Entry: {self.zpos_entry_var.get()}",
            f"# X Position Entry: {self.xpos_entry_var.get()}",
            f"# Y Position Entry: {self.ypos_entry_var.get()}",
            f"# TG Entry: {self.TG_entry_var.get()}",
            f"# BG Entry: {self.BG_entry_var.get()}",
            f"# WP Entry: {self.WP_entry_var.get()}",
            f"# YD Entry: {self.YD_entry_var.get()}",
            f"# CL Entry: {self.CL_entry_var.get()}",
            f"# Back Gate Start: {self.BGS_entry_var.get()}",
            f"# Back Gate End: {self.BGE_entry_var.get()}",
            f"#"]
        if self.z_axis_var.get() == "random":
            header_lines.append(f"# Columns: Scan_Number {self.y_axis_var.get()} {self.x_axis_var.get()} lockin1 lockin2 lockin3")
        if self.z_axis_var.get() == "deltaR/R":
            header_lines.append(f"# Columns: Scan_Number {self.y_axis_var.get()} {self.x_axis_var.get()} deltaR     R     deltaR/R")
        if self.z_axis_var.get() == "deltaR/R alternate":
            header_lines.append(f"# Columns: Scan_Number {self.y_axis_var.get()} {self.x_axis_var.get()} deltaR     R     empty")
        header_str = "\n".join(header_lines)
        np.savetxt(filename, data_to_save, header=header_str, comments="")
        if not self.switch_var:
            picfilename = self.save_path_var.get()+'/'+self.filename_var.get()+".png"
            self.fig.savefig(picfilename)
        print("data saved to " +filename)


    def reset_parameters(self):
        """Resets the scan parameters."""
        self.parameter_entry.delete(0, tk.END)
        print("Scan parameters reset.")

if __name__ == "__main__":
    app = ScanningMicroscopeGUI()
    app.mainloop()
