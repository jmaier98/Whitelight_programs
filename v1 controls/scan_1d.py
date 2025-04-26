import tkinter as tk
from tkinter import filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import lockin_driver as lockin
import ESP_driver as stage
import threading
import time
import numpy as np
import os

# Replace these classes with your actual device control code
# For demonstration purposes, we're simulating the devices

class SHGExperimentApp:
    def __init__(self, master):
        self.master = master
        master.title("1D_scan")

        # Variables for GUI inputs
        self.angle_step = tk.DoubleVar(value=10.0)
        self.start_time = tk.DoubleVar(value=-5)
        self.end_time = tk.DoubleVar(value=10.0)
        self.wait_time = tk.DoubleVar(value=1.0)
        self.avgsnum = tk.IntVar(value=1)
        self.filename = tk.StringVar(value="data.txt")
        self.folder_path = tk.StringVar(value=os.getcwd())

        self.is_running = False
        self.angles = []
        self.readings = []

        self.create_widgets()
        self.create_plot()

    def create_widgets(self):
        # Main container frame
        main_frame = tk.Frame(self.master)
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Left frame for all controls and inputs
        left_frame = tk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="nw", padx=5, pady=5)

        # Right frame for the plot
        right_frame = tk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky="ne", padx=5, pady=5)

        # Input parameters frame
        params_frame = tk.LabelFrame(left_frame, text="Experiment Parameters", padx=10, pady=10)
        params_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        tk.Label(params_frame, text="Step size (ps):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        tk.Entry(params_frame, textvariable=self.angle_step, width=10).grid(row=0, column=1, padx=5, pady=5)

        tk.Label(params_frame, text="Start time:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        tk.Entry(params_frame, textvariable=self.start_time, width=10).grid(row=1, column=1, padx=5, pady=5)

        tk.Label(params_frame, text="End time:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        tk.Entry(params_frame, textvariable=self.end_time, width=10).grid(row=2, column=1, padx=5, pady=5)

        tk.Label(params_frame, text="Wait Time (s):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        tk.Entry(params_frame, textvariable=self.wait_time, width=10).grid(row=3, column=1, padx=5, pady=5)

        tk.Label(params_frame, text="Number of averages:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        tk.Entry(params_frame, textvariable=self.avgsnum, width=10).grid(row=4, column=1, padx=5, pady=5)

        tk.Label(params_frame, text="Filename:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        tk.Entry(params_frame, textvariable=self.filename, width=20).grid(row=5, column=1, padx=5, pady=5)

        # Folder selection frame
        folder_frame = tk.LabelFrame(left_frame, text="File Options", padx=10, pady=10)
        folder_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        tk.Label(folder_frame, text="Save Folder:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        tk.Entry(folder_frame, textvariable=self.folder_path, width=40).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(folder_frame, text="Browse", command=self.browse_folder).grid(row=0, column=2, padx=5, pady=5)

        # Control buttons frame
        button_frame = tk.LabelFrame(left_frame, text="Controls", padx=10, pady=10)
        button_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

        self.start_button = tk.Button(button_frame, text="Start Experiment", command=self.start_experiment)
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        self.stop_button = tk.Button(button_frame, text="Stop", command=self.stop_experiment)
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

        # Make columns in left_frame stretch if necessary
        left_frame.grid_columnconfigure(0, weight=1)

        # Plot frame (placed in right_frame)
        self.plot_frame = tk.LabelFrame(right_frame, text="Results Plot", padx=10, pady=10)
        self.plot_frame.pack(fill="both", expand=True)

    def create_plot(self):
        # Create a matplotlib figure and embed it in the tkinter window
        self.figure = plt.Figure(figsize=(6, 4), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel('Time (ps)')
        self.ax.set_ylabel('Lock-in Reading')
        self.ax.set_title('1D Scan')

        self.line, = self.ax.plot([], [], 'bo-')

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def browse_folder(self):
        # Open a dialog to select a folder
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path.set(folder_selected)

    def start_experiment(self):
        if not self.is_running:
            self.is_running = True
            self.start_button.config(state=tk.DISABLED)
            # Reset data lists
            self.angles = []
            self.readings = []
            # Start the experiment in a separate thread
            threading.Thread(target=self.run_experiment).start()

    def run_experiment(self):
        angle_step = self.angle_step.get()/6.67
        wait_time = self.wait_time.get()
        """







"""
        angles = np.arange(38,45 +angle_step, angle_step)
        avg_num = self.avgsnum.get()
        datay = np.zeros((avg_num,len(angles)))
        datax = np.zeros((avg_num,len(angles)))
        datay2 = np.zeros((avg_num,len(angles)))
        avgs = 0
        while avgs < avg_num:
            print("loop "+str(avgs))
            if not self.is_running:
                break
            x = 0
            while x < len(angles):
                if not self.is_running:
                    break
                # Rotate the stage

                stage.rotate(-1 * angles[x])

                # Wait for the specified time
                time.sleep(wait_time)

                # Read data from the lock-in amplifier
                reading1 = lockin.readx1()
                time.sleep(0.1)
                reading2 = lockin.readx2()
                datax[avgs,x] = 6.67*angles[x]
                datay[avgs,x] = reading1
                datay2[avgs,x] = reading2
                # Append data to lists
                if avgs == 0:
                    self.angles.append(angles[x]*6.67)
                    self.readings.append(reading1/max(1e-9,reading2))
                else:
                    self.readings[x] = np.sum(datay[:,x]/np.maximum(1e-9,datay2[:,x]))/(avgs+1)
                # Update the plot
                self.update_plot()
                x+=1
            avgs += 1
        # Save the collected data
        self.save_data(datax.flatten(),datay.flatten(),datay2.flatten())
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)

    def update_plot(self):
        # Update the data in the plot
        self.line.set_data(self.angles, self.readings)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def save_data(self,x,y,y2):
        # Save the data to a text file
        filename = self.filename.get()
        folder = self.folder_path.get()
        filepath = os.path.join(folder, filename)
        data = np.column_stack((x, y, y2))
        header = 'Angle(degrees)\tLock-in Reading\tLock-in2 Reading'
        np.savetxt(filepath, data, header=header, delimiter='\t')
        print(f"Data saved to {filepath}")

    def stop_experiment(self):
        # Stop the experiment
        self.is_running = False

if __name__ == "__main__":
    root = tk.Tk()
    app = SHGExperimentApp(root)
    root.mainloop()
