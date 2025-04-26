import tkinter as tk
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText
import matplotlib
import numpy as np
import re
import os

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class DataViewerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Data Viewer")
        self.geometry("1200x500")  # Adjust as needed
        
        # Variables
        self.filename_var = tk.StringVar(value="")
        
        # Plot limit variables
        self.xmin_var = tk.StringVar(value="")
        self.xmax_var = tk.StringVar(value="")
        self.ymin_var = tk.StringVar(value="")
        self.ymax_var = tk.StringVar(value="")

        # Data storage
        self.scan_number = []
        self.x_data = []
        self.y_data = []
        self.y_data2 = []   # If present
        self.metadata_dict = {}  # store metadata from header

        # Create UI
        self.create_widgets()
        
        # Create the figure and axes
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Metadata display text (on the right)
        self.metadata_box = ScrolledText(self.plot_metadata_frame, wrap=tk.WORD, width=40, height=20)
        self.metadata_box.pack(fill=tk.BOTH, expand=True)
        
        self.update_plot()

    def create_widgets(self):
        """Create the left control panel and right plot area."""
        
        # Left Frame: controls
        control_frame = ttk.Frame(self)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        # Right Frame: plot + metadata
        right_frame = ttk.Frame(self)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Inside right_frame: plot on the left, metadata on the right
        self.plot_frame = ttk.Frame(right_frame)
        self.plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.plot_metadata_frame = ttk.Frame(right_frame)
        self.plot_metadata_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # -------------------------------
        # File selection
        # -------------------------------
        file_frame = ttk.LabelFrame(control_frame, text="Data File")
        file_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(file_frame, text="Filename:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(file_frame, textvariable=self.filename_var).pack(fill=tk.X, padx=5, pady=2)
        
        browse_btn = ttk.Button(file_frame, text="Browse", command=self.browse_file)
        browse_btn.pack(fill=tk.X, padx=5, pady=2)
        
        load_btn = ttk.Button(file_frame, text="Load File", command=self.load_file)
        load_btn.pack(fill=tk.X, padx=5, pady=2)
        
        # -------------------------------
        # Plot Controls
        # -------------------------------
        plot_ctrl_frame = ttk.LabelFrame(control_frame, text="Plot Controls")
        plot_ctrl_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Buttons to plot all scans or average
        all_scans_btn = ttk.Button(plot_ctrl_frame, text="Plot All Scans", command=self.plot_all_scans)
        all_scans_btn.pack(fill=tk.X, padx=5, pady=2)
        
        avg_scans_btn = ttk.Button(plot_ctrl_frame, text="Plot Average", command=self.plot_average)
        avg_scans_btn.pack(fill=tk.X, padx=5, pady=2)
        
        # X/Y limit entries
        ttk.Label(plot_ctrl_frame, text="X min:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(plot_ctrl_frame, textvariable=self.xmin_var).pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(plot_ctrl_frame, text="X max:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(plot_ctrl_frame, textvariable=self.xmax_var).pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(plot_ctrl_frame, text="Y min:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(plot_ctrl_frame, textvariable=self.ymin_var).pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(plot_ctrl_frame, text="Y max:").pack(anchor=tk.W, padx=2, pady=2)
        ttk.Entry(plot_ctrl_frame, textvariable=self.ymax_var).pack(fill=tk.X, padx=5, pady=2)
        
        # Button to refresh plot with chosen x/y limits
        apply_limits_btn = ttk.Button(plot_ctrl_frame, text="Apply Limits", command=self.update_plot)
        apply_limits_btn.pack(fill=tk.X, padx=5, pady=2)

        # Button to reset the axis limits (auto-scale)
        reset_limits_btn = ttk.Button(plot_ctrl_frame, text="Reset Limits", command=self.reset_limits)
        reset_limits_btn.pack(fill=tk.X, padx=5, pady=2)

    # -----------------------------------------------------------------
    # File handling
    # -----------------------------------------------------------------
    def browse_file(self):
        """Open a dialog to select a data file."""
        filetypes = [("Text Files", "*.txt"), ("All Files", "*.*")]
        f = filedialog.askopenfilename(filetypes=filetypes)
        if f:
            self.filename_var.set(f)

    def load_file(self):
        """Load data from the specified file, parse metadata and arrays (NumPy version)."""
        # Clear the metadata display
        self.metadata_box.delete("1.0", tk.END)
        
        # Clear metadata dictionary
        self.metadata_dict.clear()
        
        # Reassign empty NumPy arrays for new data
        self.scan_number = np.array([], dtype=float)
        self.x_data      = np.array([], dtype=float)
        self.y_data      = np.array([], dtype=float)
        self.y_data2     = np.array([], dtype=float)
        
        fname = self.filename_var.get()
        if not os.path.isfile(fname):
            self.metadata_box.insert(tk.END, "File not found.\n")
            return
        
        # Read the file
        with open(fname, "r") as f:
            lines = f.readlines()
        
        # Identify header lines (starting with '#')
        data_start_index = 0
        header_lines = []
        for i, line in enumerate(lines):
            if line.strip().startswith("#"):
                header_lines.append(line.strip())
            else:
                data_start_index = i
                break
        
        # Display header
        self.metadata_box.insert(tk.END, "File Header:\n")
        for hl in header_lines:
            self.metadata_box.insert(tk.END, hl + "\n")
        self.metadata_box.insert(tk.END, "\n")
        
        # Parse metadata from header lines
        for hl in header_lines:
            # e.g. "# Key: Value"
            match = re.match(r"#\s*(.*?):\s*(.*)", hl)
            if match:
                key = match.group(1).strip()
                val = match.group(2).strip()
                self.metadata_dict[key] = val
        
        # Load numeric data using numpy.loadtxt (ignoring lines starting with '#')
        try:
            data = np.loadtxt(fname, comments="#")
        except Exception as e:
            self.metadata_box.insert(tk.END, f"Error reading numeric data: {e}\n")
            return
        
        # If there's only one line of data, ensure it becomes 2D
        if data.ndim == 1:
            data = data.reshape(1, -1)
        
        num_cols = data.shape[1]
        if num_cols == 3:
            # Format: ScanNumber, X, Y
            self.scan_number = data[:, 0]
            self.x_data      = data[:, 1]
            self.y_data      = data[:, 2]
        elif num_cols == 4:
            # Format: ScanNumber, X, Y1, Y2
            self.scan_number = data[:, 0]
            self.x_data      = data[:, 1]
            self.y_data      = data[:, 2]
            self.y_data2     = data[:, 3]
        else:
            self.metadata_box.insert(tk.END, f"Unexpected number of columns: {num_cols}\n")
            return
        
        self.metadata_box.insert(tk.END, "Data loaded successfully.\n")
        
        # Update the plot
        self.update_plot()


    # -----------------------------------------------------------------
    # Plot Options
    # -----------------------------------------------------------------
    def plot_all_scans(self):
        """Plot all scans individually."""
        if len(self.scan_number) == 0:
            return
        
        self.ax.clear()
        
        # Distinguish scans by unique scan_number
        unique_scans = np.unique(self.scan_number)
        
        # Check if y2 is present (i.e., not all NaN if the array is allocated)
        y2_present = (len(self.y_data2) > 0) and (not np.all(np.isnan(self.y_data2)))
        
        for sc in unique_scans:
            idx = np.where(self.scan_number == sc)
            x_vals = self.x_data[idx]
            y_vals = self.y_data[idx]
            
            # If second dependent variable is present, we can choose to plot just y1 or both
            # For simplicity, let's just plot y1 here
            self.ax.plot(x_vals, y_vals, 'o-', label=f"Scan {int(sc)}")
        
        self.apply_metadata_and_limits()
        self.canvas.draw()

    def plot_average(self):
        """Plot the average across scans for each unique x."""
        if len(self.scan_number) == 0:
            return
        
        self.ax.clear()
        
        y2_present = (len(self.y_data2) > 0) and (not np.all(np.isnan(self.y_data2)))
        
        # Group data by x, ignoring scan_number for averaging
        aggregator = {}
        for sn, xx, yy, yy2 in zip(self.scan_number, self.x_data, self.y_data,
                                   self.y_data2 if y2_present else [None]*len(self.x_data)):
            x_key = round(xx, 6)
            if x_key not in aggregator:
                aggregator[x_key] = []
            aggregator[x_key].append((yy, yy2) if y2_present else (yy,))
        
        x_plot = []
        y_plot = []
        y2_plot = []
        
        for x_key in sorted(aggregator.keys()):
            arr = aggregator[x_key]
            if y2_present:
                ys = [v[0] for v in arr]
                y2s = [v[1] for v in arr if v[1] is not None]
                avg_y = np.mean(ys) if ys else 0
                avg_y2 = np.mean(y2s) if y2s else np.nan
                x_plot.append(x_key)
                y_plot.append(avg_y)
                y2_plot.append(avg_y2)
            else:
                ys = [v[0] for v in arr]
                avg_y = np.mean(ys) if ys else 0
                x_plot.append(x_key)
                y_plot.append(avg_y)
        
        if y2_present:
            self.ax.plot(x_plot, y_plot, 'o-', color='tab:blue', label='Avg Y1')
            self.ax.plot(x_plot, y2_plot, 's--', color='tab:orange', label='Avg Y2')
            self.ax.legend(loc='best')
        else:
            self.ax.plot(x_plot, y_plot, 'o-', label='Average')
            self.ax.legend(loc='best')
        
        self.apply_metadata_and_limits()
        self.canvas.draw()

    def update_plot(self):
        """
        Default method that re-draws the axes with no data, or applies
        the current x/y limits if data is present.
        """
        if len(self.scan_number) == 0:
            self.ax.clear()
            self.ax.set_title("No Data Loaded")
            self.canvas.draw()
            return
        
        # If data is loaded, just apply the metadata and axis limits
        self.apply_metadata_and_limits()
        self.canvas.draw()

    def apply_metadata_and_limits(self):
        """
        Apply metadata from the file (x-label, y-label, device name)
        and user-defined xlim/ylim if provided.
        """
        # Plot title from device name
        device_name = self.metadata_dict.get("Device Name", "Unknown Device")
        self.ax.set_title(device_name)
        
        # X/Y labels from metadata
        x_label = self.metadata_dict.get("Independent Variable", "X")
        y_label = self.metadata_dict.get("Dependent Variable", "Y")
        self.ax.set_xlabel(x_label)
        self.ax.set_ylabel(y_label)
        
        # Apply user-specified limits if valid, else auto
        def parse_limit(val):
            try:
                return float(val)
            except ValueError:
                return None
        
        xmin = parse_limit(self.xmin_var.get())
        xmax = parse_limit(self.xmax_var.get())
        ymin = parse_limit(self.ymin_var.get())
        ymax = parse_limit(self.ymax_var.get())
        
        if xmin is not None and xmax is not None and xmin < xmax:
            self.ax.set_xlim([xmin, xmax])
        else:
            self.ax.set_xlim(auto=True)
        
        if ymin is not None and ymax is not None and ymin < ymax:
            self.ax.set_ylim([ymin, ymax])
        else:
            self.ax.set_ylim(auto=True)

    def reset_limits(self):
        """Clear the x/y limit fields and revert to auto-scaling."""
        self.xmin_var.set("")
        self.xmax_var.set("")
        self.ymin_var.set("")
        self.ymax_var.set("")
        
        # Re-apply in update_plot
        self.update_plot()

def main():
    app = DataViewerApp()
    app.mainloop()

if __name__ == "__main__":
    main()
