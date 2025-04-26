import tkinter as tk
from tkinter import filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import lockin_driver as lockin
import spec_driver as spec
import threading
import time
import numpy as np
import os

# Replace these classes with your actual device control code
# For demonstration purposes, we're simulating the devices

class SHGExperimentApp:
    def __init__(self, master):
        self.master = master
        master.title("Polarization Dependent SHG Experiment")

        # Variables for GUI inputs
        self.angle_step = tk.DoubleVar(value=10.0)
        self.wait_time = tk.DoubleVar(value=1.0)
        self.filename = tk.StringVar(value="data.txt")
        self.folder_path = tk.StringVar(value=os.getcwd())

        self.is_running = False
        self.angles = []
        self.readings = []

        self.create_widgets()
        self.create_plot()

    def create_widgets(self):
        # Angle step size input
        tk.Label(self.master, text="Angle Step Size (degrees):").grid(row=0, column=0, sticky=tk.W)
        tk.Entry(self.master, textvariable=self.angle_step).grid(row=0, column=1)

        # Wait time input
        tk.Label(self.master, text="Wait Time at Each Point (s):").grid(row=1, column=0, sticky=tk.W)
        tk.Entry(self.master, textvariable=self.wait_time).grid(row=1, column=1)

        # Filename input
        tk.Label(self.master, text="Filename:").grid(row=2, column=0, sticky=tk.W)
        tk.Entry(self.master, textvariable=self.filename).grid(row=2, column=1)

        # Folder selection
        tk.Label(self.master, text="Save Folder:").grid(row=3, column=0, sticky=tk.W)
        tk.Entry(self.master, textvariable=self.folder_path, width=40).grid(row=3, column=1)
        tk.Button(self.master, text="Browse", command=self.browse_folder).grid(row=3, column=2)

        # Start button
        self.start_button = tk.Button(self.master, text="Start Experiment", command=self.start_experiment)
        self.start_button.grid(row=4, column=0, columnspan=3, pady=10)
        
        # top button
        self.stop_button = tk.Button(self.master, text="Stop", command=self.stop_experiment)
        self.stop_button.grid(row=4, column=2, columnspan=3, pady=10)

    def create_plot(self):
        # Create a matplotlib figure and embed it in the tkinter window
        self.figure = plt.Figure(figsize=(6, 4), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel('Wavelength')
        self.ax.set_ylabel('Lock-in Reading')
        self.ax.set_title('Wavelength scan')

        self.line, = self.ax.plot([], [], 'bo-')

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.master)
        self.canvas.get_tk_widget().grid(row=5, column=0, columnspan=3)

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
        angle_step = self.angle_step.get()
        wait_time = self.wait_time.get()
        angles = np.arange(700, 1100, angle_step)
        for angle in angles:
            if not self.is_running:
                break
            # Rotate the stage
            attempt = 0
            while attempt < 5:
                try:
                    spec.set_nm(angle)
                    break
                except Exception as e:
                    attempt +=1
                    print("encountered error trying again")
                    time.sleep(5)
            # Wait for the specified time
            time.sleep(wait_time)
            # Read data from the lock-in amplifier
            reading = lockin.readx1()
            # Append data to lists
            self.angles.append(angle)
            self.readings.append(reading)
            # Update the plot
            self.update_plot()
        # Save the collected data
        self.save_data()
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)

    def update_plot(self):
        # Update the data in the plot
        self.line.set_data(self.angles, self.readings)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def save_data(self):
        # Save the data to a text file
        filename = self.filename.get()
        folder = self.folder_path.get()
        filepath = os.path.join(folder, filename)
        data = np.column_stack((self.angles, self.readings))
        header = 'Angle(degrees)\tLock-in Reading'
        np.savetxt(filepath, data, header=header, delimiter='\t')
        print(f"Data saved to {filepath}")

    def stop_experiment(self):
        # Stop the experiment
        self.is_running = False

if __name__ == "__main__":
    root = tk.Tk()
    app = SHGExperimentApp(root)
    root.mainloop()
