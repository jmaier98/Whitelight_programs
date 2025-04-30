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

# Initialize hardware controllers
zstage = Zstage.Controller(which_port='COM8')
spec = SP2500.Spectrometer()
sr400 = PC.SR400(acquisition_time=2, discriminator=-0.002)
ESP = ESP301.ESP301()
lockin.open_all_connections()

# Use TkAgg backend for embedding plots
matplotlib.use("TkAgg")

class ScanningMicroscopeGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("2D Scan Application")
        self.geometry("1800x1000")

        # --- Create Notebook with two tabs ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill='both')

        # Tab 1: 2D Scan UI
        self.scan_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.scan_tab, text="2D Scan")

        # Tab 2: Active Stabilization
        self.stab_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.stab_tab, text="Active Stabilization")

        # --- Setup 2x2 plot canvas inside scan_tab ---
        self.fig, self.ax = plt.subplots(nrows=2, ncols=2)
        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.scan_tab)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.canvas.mpl_connect("button_press_event", self.on_click)

        # Dummy image data
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

        self.linecutY = self.ax[1, 0].plot(self.image_data_1[:, 0])
        self.ax[1, 0].set_title("Y linecut")
        self.ax[1, 0].set_xlabel("X Axis")
        self.ax[1, 0].set_ylabel("Y Axis")

        self.image_data_2 = np.random.rand(20, 20) * 10e-6
        self.image_plot_2 = self.ax[1, 1].imshow(self.image_data_2, cmap='viridis', origin='lower')
        self.ax[1, 1].set_title("Z data2")
        self.ax[1, 1].set_xlabel("X Axis")
        self.ax[1, 1].set_ylabel("Y Axis")
        self.fig.colorbar(self.image_plot_2, ax=self.ax[1, 1], orientation='vertical')

        # --- Control panel inside scan_tab ---
        control_frame = ttk.Frame(self.scan_tab)
        control_frame.pack(side=tk.LEFT, fill=tk.X)
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)

        # Axes/Measurements frame
        axes_frame = ttk.LabelFrame(control_frame, text="Axes / Measurements")
        axes_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.x_axis_var = tk.StringVar(value="X pos")
        self.y_axis_var = tk.StringVar(value="Y pos")
        self.z_axis_var = tk.StringVar(value="Lockin 1")
        x_options = ["X pos","Y pos","Z pos","Delay pos","Delay time (ps)","Waveplate angle","Wavelength","Top gate","Back gate","Gate line cut (set TG)","dummy","Reverse delay time (ps)","Delay time (ps)_yaxis","Reverse Delay time (ps)_yaxis"]
        y_options = x_options.copy()
        z_options = ["Photon counter","deltaR/R","deltaR/R alternate","lockin 1","lockin 2","lockin 3","X and Y Current","X+, Y+, and Y- Current","random"]
        ttk.Label(axes_frame, text="X Axis:").pack(anchor=tk.W)
        ttk.OptionMenu(axes_frame, self.x_axis_var, x_options[0], *x_options).pack(fill=tk.X)
        ttk.Label(axes_frame, text="Y Axis:").pack(anchor=tk.W)
        ttk.OptionMenu(axes_frame, self.y_axis_var, y_options[1], *y_options).pack(fill=tk.X)
        ttk.Label(axes_frame, text="Z Measurement:").pack(anchor=tk.W)
        ttk.OptionMenu(axes_frame, self.z_axis_var, z_options[0], *z_options).pack(fill=tk.X)

        # Range & Averages frame
        range_frame = ttk.LabelFrame(control_frame, text="Range & Averages")
        range_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.x_start_var = tk.StringVar(value="0")
        self.x_end_var   = tk.StringVar(value="10")
        self.x_step_var  = tk.StringVar(value="1")
        self.y_start_var = tk.StringVar(value="0")
        self.y_end_var   = tk.StringVar(value="5")
        self.y_step_var  = tk.StringVar(value="1")
        self.averages_var   = tk.StringVar(value="1")
        self.wait_time_var  = tk.StringVar(value="0.5")
        for label, var in [("X Start:",self.x_start_var),("X End:",self.x_end_var),("X Step:",self.x_step_var),("Y Start:",self.y_start_var),("Y End:",self.y_end_var),("Y Step:",self.y_step_var),("Averages (# of scans):",self.averages_var),("Wait Time (sec):",self.wait_time_var)]:
            ttk.Label(range_frame, text=label).pack(anchor=tk.W)
            ttk.Entry(range_frame, textvariable=var).pack(fill=tk.X)
        ttk.Button(range_frame, text="Start Scan", command=self.start_scan).pack(fill=tk.X, pady=(5,2))
        ttk.Button(range_frame, text="Stop Scan", command=self.stop_scan).pack(fill=tk.X, pady=2)

        # Metadata frame
        metadata_frame = ttk.LabelFrame(control_frame, text="Metadata")
        metadata_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        self.device_var           = tk.StringVar(value="Device1")
        self.fluence_var          = tk.StringVar(value="N/A")
        self.wavelength_var       = tk.StringVar(value="650 nm")
        self.probe_power_var      = tk.StringVar(value="N/A")
        self.probe_wavelength_var = tk.StringVar(value="N/A")
        for label, var in [("Device Name:",self.device_var),("Pump Power:",self.fluence_var),("Pump Wavelength:",self.wavelength_var),("Probe Power:",self.probe_power_var),("Probe Wavelength:",self.probe_wavelength_var)]:
            ttk.Label(metadata_frame, text=label).pack(anchor=tk.W)
            ttk.Entry(metadata_frame, textvariable=var).pack(fill=tk.X)
        ttk.Label(metadata_frame, text="Notes:").pack(anchor=tk.W)
        self.notes_text = ScrolledText(metadata_frame, wrap=tk.WORD, width=25, height=4)
        self.notes_text.pack(fill=tk.X)

        # File Saving frame
        file_frame = ttk.LabelFrame(control_frame, text="File Saving")
        file_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.save_path_var = tk.StringVar(value="")
        self.filename_var  = tk.StringVar(value="scan2d_data.txt")
        ttk.Label(file_frame, text="Save Path:").pack(anchor=tk.W)
        ttk.Entry(file_frame, textvariable=self.save_path_var).pack(fill=tk.X)
        ttk.Button(file_frame, text="Browse", command=self.browse_path).pack(fill=tk.X, pady=2)
        ttk.Label(file_frame, text="Filename:").pack(anchor=tk.W)
        ttk.Entry(file_frame, textvariable=self.filename_var).pack(fill=tk.X)
        ttk.Button(file_frame, text="Save Data", command=self.save_data).pack(fill=tk.X, pady=2)

        # Motion Controls frame
        motion_frame = ttk.LabelFrame(control_frame, text="Motion Controls")
        motion_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        motion_frame.columnconfigure((0,1,2), weight=1)
        # Entry vars for motion
        self.wavelength_entry_var = tk.StringVar(value="0")
        self.delay_entry_var      = tk.StringVar(value="0")
        self.zpos_entry_var       = tk.StringVar(value="0")
        self.xpos_entry_var       = tk.StringVar(value="0")
        self.ypos_entry_var       = tk.StringVar(value="0")
        self.TG_entry_var         = tk.StringVar(value="0")
        self.BG_entry_var         = tk.StringVar(value="0")
        self.CL_entry_var         = tk.StringVar(value="6e-10")
        self.BGS_entry_var        = tk.StringVar(value="0")
        self.BGE_entry_var        = tk.StringVar(value="0")
        # Buttons and entries laid out in grid
        controls = [
            ("set Wavelength", self.set_wavelength, self.wavelength_entry_var),
            ("set Delay (ps)", self.set_delay, self.delay_entry_var),
            ("set z pos", self.set_zpos, self.zpos_entry_var),
            ("set x,y pos", self.set_xypos, [self.xpos_entry_var, self.ypos_entry_var]),
            ("set TG voltage", self.set_TG, self.TG_entry_var),
            ("set BG voltage", self.set_BG, self.BG_entry_var),
            ("set Current Limit", self.set_CL, self.CL_entry_var)
        ]
        for idx,(text, cmd, var) in enumerate(controls):
            ttk.Button(motion_frame, text=text, command=cmd).grid(row=idx, column=0, padx=5, pady=5, sticky="ew")
            if isinstance(var, list):
                # x,y pos row
                ttk.Entry(motion_frame, textvariable=var[0]).grid(row=idx, column=1, padx=5, pady=5, sticky="ew")
                ttk.Entry(motion_frame, textvariable=var[1]).grid(row=idx, column=2, padx=5, pady=5, sticky="ew")
            else:
                ttk.Entry(motion_frame, textvariable=var).grid(row=idx, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        # Placeholder content in Active Stabilization tab
        ttk.Label(self.stab_tab, text="Active Stabilization controls go here", font=("TkDefaultFont", 16))\
            .pack(padx=20, pady=20)

        # Initialize data structures
        self.data = np.zeros((1,1,1,6))
        self.avg_data = np.zeros((1,1,6))
        self.cursorX = self.cursorY = 0.0
        self.cursor_ix = self.cursor_iy = 0
        self.frame_clicked = 1
        self.x0 = np.arange(0,11,1)
        self.y0 = np.arange(0,6,1)
        self.currlimit = 6e-10
        self.scan_running = False

    # --- Callback & control methods unchanged from original ---
    def on_click(self, event):
        if event.inaxes is None: return
        if event.inaxes in [self.ax[0,0], self.ax[0,1]]: self.frame_clicked = 1
        if event.inaxes in [self.ax[1,0], self.ax[1,1]]: self.frame_clicked = 2
        if event.inaxes not in [self.ax[0,0], self.ax[1,1]]: return
        self.cursorX, self.cursorY = event.xdata, event.ydata
        self.xpos_entry_var.set(str(self.cursorX))
        self.ypos_entry_var.set(str(self.cursorY))
        self.cursor_ix = np.abs(self.x0 - self.cursorX).argmin()
        self.cursor_iy = np.abs(self.y0 - self.cursorY).argmin()
        self.update_image_data(scanNum=0,
                               x_var=self.x_axis_var.get(),
                               y_var=self.y_axis_var.get(),
                               z_var=self.z_axis_var.get())

    def set_wavelength(self): spec.set_nm(float(self.wavelength_entry_var.get()))
    def set_delay(self):
        x = float(self.delay_entry_var.get())
        target = max(-105, min(105, -1.45 + x * -0.15))
        moved = ESP.moveZ(target)
        while moved != True:
            time.sleep(2)
            moved = ESP.moveZ(target)
    def set_zpos(self): zstage.move_mm(float(self.zpos_entry_var.get()), relative=False)
    def set_xypos(self): ESP.moveX(float(self.xpos_entry_var.get())); ESP.moveY(float(self.ypos_entry_var.get()))
    def set_TG(self): self.stepInd("Top gate", float(self.TG_entry_var.get()))
    def set_BG(self): self.stepInd("Back gate", float(self.BG_entry_var.get()))
    def set_CL(self): self.currlimit = float(self.CL_entry_var.get())
    def browse_path(self):
        d = filedialog.askdirectory()
        if d: self.save_path_var.set(d)
    def start_scan(self):
        if not self.scan_running:
            self.scan_running = True
            threading.Thread(target=self.run_scan, daemon=True).start()
    def stop_scan(self):
        self.scan_running = False
        print("Stopping scan...")

    def save_data(self):
        data_to_save = self.data.reshape(-1,6)
        fname = f"{self.save_path_var.get()}/{self.filename_var.get()}.txt"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notes = self.notes_text.get("1.0", tk.END).strip()
        header = [
            f"# Date/Time: {now}",
            f"# X Variable (fast axis): {self.x_axis_var.get()}",
            f"# Y Variable (slow axis): {self.y_axis_var.get()}",
            f"# Z Variable: {self.z_axis_var.get()}",
            f"# Additional Notes: {notes}",
            "#"
        ]
        np.savetxt(fname, data_to_save, header="\n".join(header), comments="")
        print("Data saved to ", fname)

    def run_scan(self):
        # (scan loop unchanged)
        self.scan_running = False

    def update_image_data(self, scanNum, x_var, y_var, z_var):
        plot_data = self.avg_data
        self.image_plot_1.set_data(plot_data[:,:,3]); self.image_plot_1.set_clim(vmin=plot_data[:,:,3].min(), vmax=plot_data[:,:,3].max())
        self.image_plot_2.set_data(plot_data[:,:,4]); self.image_plot_2.set_clim(vmin=plot_data[:,:,4].min(), vmax=plot_data[:,:,4].max())
        dataid = 3 if self.frame_clicked==1 else 4
        self.ax[0,1].cla(); self.ax[0,1].plot(plot_data[self.cursor_iy,:,2], plot_data[self.cursor_iy,:,dataid]); self.ax[0,1].set_title("X linecut")
        self.ax[1,0].cla(); self.ax[1,0].plot(plot_data[:,self.cursor_ix,1], plot_data[:,self.cursor_ix,dataid]); self.ax[1,0].set_title("Y linecut")
        self.canvas.draw()

if __name__ == "__main__":
    app = ScanningMicroscopeGUI()
    app.mainloop()

