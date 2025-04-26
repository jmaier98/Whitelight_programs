import ESP_driver as esp
import lockin_driver as lockin
import stage_driver as stage
import time
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class ScanningMicroscopeGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Scanning Photocurrent Microscope")
        self.geometry("1200x900")


        # Initialize a dummy image

        # Setup the 2x2 grid of plots
        self.fig, self.ax = plt.subplots(nrows=2, ncols=2)
        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Initialize dummy images for each subplot
        self.image_data_x = np.random.rand(5, 5) * 10e-6
        self.image_plot_x = self.ax[0, 0].imshow(self.image_data_x, cmap='viridis', origin='lower')
        self.ax[0, 0].set_title("X Current Map")
        self.ax[0, 0].set_xlabel("X Axis")
        self.ax[0, 0].set_ylabel("Y Axis")
        self.fig.colorbar(self.image_plot_x, ax=self.ax[0, 0], orientation='vertical')

        self.image_data_y = np.random.rand(5, 5) * 10e-6
        self.image_plot_y = self.ax[0, 1].imshow(self.image_data_y, cmap='viridis', origin='lower')
        self.ax[0, 1].set_title("Y Current Map")
        self.ax[0, 1].set_xlabel("X Axis")
        self.ax[0, 1].set_ylabel("Y Axis")
        self.fig.colorbar(self.image_plot_y, ax=self.ax[0, 1], orientation='vertical')

        x = np.linspace(-1, 1, 10)
        y = np.linspace(-1, 1, 10)
        X, Y = np.meshgrid(x, y)
        U = -Y
        V = X
        self.X = X
        self.Y = Y
        self.quiver_plot = self.ax[1, 0].quiver(X, Y, U, V)
        self.ax[1, 0].set_title("Current Map")
        self.ax[1, 0].set_xlabel("X Axis")
        self.ax[1, 0].set_ylabel("Y Axis")

        self.image_data_m = np.random.rand(5, 5) * 10e-6
        self.image_plot_m = self.ax[1, 1].imshow(self.image_data_m, cmap='viridis', origin='lower')
        self.ax[1, 1].set_title("Reflection Imaging")
        self.ax[1, 1].set_xlabel("X Axis")
        self.ax[1, 1].set_ylabel("Y Axis")
        self.fig.colorbar(self.image_plot_m, ax=self.ax[1, 1], orientation='vertical')



        # Control panel frame
        control_frame = ttk.Frame(self)
        control_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # First row of buttons
        button_row_1 = ttk.Frame(control_frame)
        button_row_1.pack(side=tk.TOP, fill=tk.X)

        self.Xpos = ttk.Label(button_row_1, text="gotoX:")
        self.Xpos.pack(side=tk.LEFT, padx=10, pady=5)

        self.Xentry = ttk.Entry(button_row_1,width = 10)
        self.Xentry.pack(side=tk.LEFT, padx=10, pady=5)

        self.XstartLabel = ttk.Label(button_row_1, text="Xstart:")
        self.XstartLabel.pack(side=tk.LEFT, padx=10, pady=5)

        self.Xstart = ttk.Entry(button_row_1,width = 10)
        self.Xstart.insert(0,'-10')
        self.Xstart.pack(side=tk.LEFT, padx=10, pady=5)

        self.XendLabel = ttk.Label(button_row_1, text="Xend:")
        self.XendLabel.pack(side=tk.LEFT, padx=10, pady=5)

        self.Xend = ttk.Entry(button_row_1,width = 10)
        self.Xend.insert(0,'10')
        self.Xend.pack(side=tk.LEFT, padx=10, pady=5)

        self.start_button = ttk.Button(button_row_1, text="Start Scan", command=self.start_scan)
        self.start_button.pack(side=tk.LEFT, padx=10, pady=5)

        self.folder_entry = ttk.Entry(button_row_1, width=50)
        self.folder_entry.insert(0,'C:/Users/Whitelight/Desktop/plasmonic emitters/calibration and prep')
        self.folder_entry.pack(side=tk.LEFT, padx=10, pady=5)

        self.save_button = ttk.Button(button_row_1, text="Save Data", command=self.save_data)
        self.save_button.pack(side=tk.LEFT, padx=10, pady=5)

        self.scaleEntry = ttk.Entry(button_row_1,width = 10)
        self.scaleEntry.insert(0,'1e-4')
        self.scaleEntry.pack(side=tk.RIGHT, padx=10, pady=5)
        
        self.scalelabel = ttk.Label(button_row_1, text="Quiver Scale:")
        self.scalelabel.pack(side=tk.RIGHT, padx=10, pady=5)



        

        # Second row of buttons
        button_row_2 = ttk.Frame(control_frame)
        button_row_2.pack(side=tk.TOP, fill=tk.X)

        self.entry_label = ttk.Label(button_row_2, text="gotoY:")
        self.entry_label.pack(side=tk.LEFT, padx=10, pady=5)

        self.Yentry = ttk.Entry(button_row_2,width = 10)
        self.Yentry.pack(side=tk.LEFT, padx=10, pady=5)

        self.YstartLabel = ttk.Label(button_row_2, text="Ystart:")
        self.YstartLabel.pack(side=tk.LEFT, padx=10, pady=5)

        self.Ystart = ttk.Entry(button_row_2,width = 10)
        self.Ystart.insert(0,'-10')
        self.Ystart.pack(side=tk.LEFT, padx=10, pady=5)

        self.YendLabel = ttk.Label(button_row_2, text="Yend:")
        self.YendLabel.pack(side=tk.LEFT, padx=10, pady=5)

        self.Yend = ttk.Entry(button_row_2,width = 10)
        self.Yend.insert(0,'10')
        self.Yend.pack(side=tk.LEFT, padx=10, pady=5)

        self.stop_button = ttk.Button(button_row_2, text="Stop Scan", command=self.stop_scan)
        self.stop_button.pack(side=tk.LEFT, padx=10, pady=5)


        
        self.browse_button = ttk.Button(button_row_2, text="Browse", command=self.browse_folder)
        self.browse_button.pack(side=tk.LEFT, padx=10, pady=5)

        self.labelsf = ttk.Label(button_row_2, text="Save Picture Off")
        self.labelsf.pack(side=tk.LEFT, padx=10, pady=5)

        self.switch_var = tk.BooleanVar(value=False)
        self.switch = ttk.Checkbutton(button_row_2,
            text="",
            variable=self.switch_var,
            command=self.toggle_switch,
            style="Switch.TCheckbutton"
        )
        self.switch.pack(side=tk.LEFT, padx=10, pady=5)

        self.xstepEntry = ttk.Entry(button_row_2,width = 10)
        self.xstepEntry.insert(0,'5')
        self.xstepEntry.pack(side=tk.RIGHT, padx=10, pady=5)
        
        self.xstep_button = ttk.Button(button_row_2, text="Step X stage", command=self.stepX)
        self.xstep_button.pack(side=tk.RIGHT, padx=10, pady=5)

        self.release = ttk.Button(button_row_2, text="Release motors", command=self.release)
        self.release.pack(side=tk.RIGHT, padx=10, pady=5)

        # third row of buttons
        button_row_3 = ttk.Frame(control_frame)
        button_row_3.pack(side=tk.TOP, fill=tk.X)

        self.reset_button = ttk.Button(button_row_3, text="Go to pos", command=self.go_to_pos)
        self.reset_button.pack(side=tk.LEFT, padx=33, pady=5)

        self.resLabel = ttk.Label(button_row_3, text="Res(um):")
        self.resLabel.pack(side=tk.LEFT, padx=5, pady=5)

        self.res = ttk.Entry(button_row_3,width = 10)
        self.res.insert(0,'4')
        self.res.pack(side=tk.LEFT, padx=10, pady=5)

        self.timerLabel = ttk.Label(button_row_3, text="Wait (s):")
        self.timerLabel.pack(side=tk.LEFT, padx=3, pady=5)

        self.timer = ttk.Entry(button_row_3,width = 10)
        self.timer.insert(0,'1')
        self.timer.pack(side=tk.LEFT, padx=10, pady=5)

        self.reset_button = ttk.Button(button_row_3, text="Reset", command=self.reset_parameters)
        self.reset_button.pack(side=tk.LEFT, padx=10, pady=5)

        self.fileLabel = ttk.Label(button_row_3, text="filename:")
        self.fileLabel.pack(side=tk.LEFT, padx=5, pady=5)

        self.filename = ttk.Entry(button_row_3,width = 30)
        self.filename.insert(0,'replace_me')
        self.filename.pack(side=tk.LEFT, padx=10, pady=5)

        self.ystepEntry = ttk.Entry(button_row_3,width = 10)
        self.ystepEntry.insert(0,'5')
        self.ystepEntry.pack(side=tk.RIGHT, padx=10, pady=5)
        
        self.ystep_button = ttk.Button(button_row_3, text="Step Y stage", command=self.stepY)
        self.ystep_button.pack(side=tk.RIGHT, padx=10, pady=5)

        self.stop_motors_button = ttk.Button(button_row_3, text="STOP MOTORS", command=self.abort_move)
        self.stop_motors_button.pack(side=tk.RIGHT, padx=10, pady=5)

        self.scan_thread = None
        self.is_scanning = False

    def toggle_switch(self):
        # Update the label text based on the switch state
        if self.switch_var:
            self.labelsf.config(text="Save Picture On")
            self.switch_var = False
        else:
            self.labelsf.config(text="Save Picture Off")
            self.switch_var = True

    def start_scan(self):
        """Starts the scanning process in a separate thread."""
        if not self.is_scanning:
            self.is_scanning = True
            self.scan_thread = threading.Thread(target=self.run_scan)
            self.scan_thread.start()
        
    def run_scan(self):
        print("Starting scan...")
        x0 = np.arange(float(self.Xstart.get()),float(self.Xend.get()),float(self.res.get()))
        x0 = x0 + float(self.res.get())/2
        y0 = np.arange(float(self.Ystart.get()),float(self.Yend.get()),float(self.res.get()))
        y0 = y0 + float(self.res.get())/2
        X,Y = np.meshgrid(x0,y0)
        self.X = X
        self.Y = Y
        wait_time = float(self.timer.get())
        x_ticks = np.linspace(x0[0], x0[-1],5)
        y_ticks = np.linspace(y0[0], y0[-1],5)


        
        
        # define data type
        dataxcur = np.zeros((len(x0), len(y0)))
        dataycur = np.zeros((len(x0), len(y0)))
        datareflection = np.zeros((len(x0), len(y0)))

        # Prepare the plot updates in the main thread
        self.after(0, self.prepare_plot, x0, y0, x_ticks, y_ticks,X,Y)
        
        for row in range(len(X)):
            goty = esp.moveY(Y[row,0])
            while goty != True:
                time.sleep(2)
                goty = esp.moveY(Y[row,0])
            if not self.is_scanning:
                break
            for column in range(len(X[0])):
                if not self.is_scanning:
                    break
                print(str(X[row,column]) + "," + str(Y[row,column]))
                print("we_good")
                gotx = esp.moveX(X[row,column])
                while gotx != True:
                    time.sleep(2)
                    gotx = esp.moveX(X[row,column])
                print("done with x move")
                time.sleep(wait_time)


                """*************
                This is where you define how data is taken at each point
                *************"""
                dataxcur[column,row] = lockin.readx1()
                dataycur[column,row] = lockin.readx2()
                datareflection[column,row] = lockin.readx3()





                # Update the image data in the main thread
                self.after(0, self.update_image_data, dataxcur, dataycur,X,Y,datareflection)

        self.is_scanning = False

    def prepare_plot(self, x0, y0, x_ticks, y_ticks,X,Y):
        """Prepare the plot layout, this runs in the main thread."""
        #self.ax.clear()
        self.ax[0,0].set_xticks(np.linspace(-.5+2.5/len(x0), 4.5-2.5/len(x0), num=5))
        self.ax[0,0].set_xticklabels([f"{int(tick)}" for tick in x_ticks])
        self.ax[0,0].set_yticks(np.linspace(-.5+2.5/len(y0), 4.5-2.5/len(y0), num=5))
        self.ax[0,0].set_yticklabels([f"{int(tick)}" for tick in y_ticks])
        self.ax[0,1].set_xticks(np.linspace(-.5+2.5/len(x0), 4.5-2.5/len(x0), num=5))
        self.ax[0,1].set_xticklabels([f"{int(tick)}" for tick in x_ticks])
        self.ax[0,1].set_yticks(np.linspace(-.5+2.5/len(y0), 4.5-2.5/len(y0), num=5))
        self.ax[0,1].set_yticklabels([f"{int(tick)}" for tick in y_ticks])
        self.ax[1,1].set_xticks(np.linspace(-.5+2.5/len(x0), 4.5-2.5/len(x0), num=5))
        self.ax[1,1].set_xticklabels([f"{int(tick)}" for tick in x_ticks])
        self.ax[1,1].set_yticks(np.linspace(-.5+2.5/len(y0), 4.5-2.5/len(y0), num=5))
        self.ax[1,1].set_yticklabels([f"{int(tick)}" for tick in y_ticks])
        self.image_data_x = np.zeros((len(x0), len(y0)))
        self.image_plot_x.set_data(self.image_data_x)
        self.image_data_y = np.zeros((len(x0), len(y0)))
        self.image_plot_y.set_data(self.image_data_y)
        self.image_data_m = np.zeros((len(x0), len(y0)))
        self.image_plot_m.set_data(self.image_data_m)
        self.ax[1, 0].cla()
        self.quiver_plot = self.ax[1, 0].quiver(X, Y, np.zeros((len(x0), len(y0))),
                                                np.zeros((len(x0), len(y0))),scale = 1e-6, scale_units = 'xy')
        self.ax[1, 0].set_title("Plot 3: Quiver Plot")
        self.ax[1, 0].set_xlabel("X Axis")
        self.ax[1, 0].set_ylabel("Y Axis")
        
    def stepX(self):
        motor = stage.StepperMotorDriver(port='COM7')
        xsteps = int(self.xstepEntry.get())
        try:
            # Move motor 1 forward 100 steps
            if xsteps > 0:
                motor.move_motor('M2', 'F', xsteps)
            elif xsteps < 0:
                xsteps = -1*xsteps
                motor.move_motor('M2', 'B', xsteps)

        except Exception as e:
            print(f"Error: {e}")
        
        finally:
            motor.close()
    def stepY(self):
        motor = stage.StepperMotorDriver(port='COM7')
        ysteps = int(self.ystepEntry.get())
        try:
            # Move motor 1 forward 100 steps
            if ysteps > 0:
                motor.move_motor('M1', 'F', ysteps)
            elif ysteps < 0:
                ysteps = -1*ysteps
                motor.move_motor('M1', 'B', ysteps)

        except Exception as e:
            print(f"Error: {e}")
        
        finally:
            motor.close()
    def release(self):
        motor = stage.StepperMotorDriver(port='COM7')

        try:
            # Move motor 1 forward 100 steps
            motor.release_motor('M2')
            time.sleep(.1)
            motor.release_motor('M1')

        except Exception as e:
            print(f"Error: {e}")
        
        finally:
            motor.close()
    def abort_move(self):
        motor = stage.StepperMotorDriver(port='COM7')

        try:
            motor.abort_movement()

        except Exception as e:
            print(f"Error: {e}")
        
        finally:
            motor.close()

    def update_image_data(self, dataxcur, dataycur,X,Y,datareflection):
        """Update the image data in the plot, this runs in the main thread."""
        self.image_data_x = dataxcur.transpose()
        self.image_plot_x.set_data(self.image_data_x)
        self.image_plot_x.set_clim(vmin=self.image_data_x.min(), vmax=self.image_data_x.max())
        self.image_data_y = dataycur.transpose()
        self.image_plot_y.set_data(self.image_data_y)
        self.image_plot_y.set_clim(vmin=self.image_data_y.min(), vmax=self.image_data_y.max())
        self.image_data_m = datareflection.transpose()
        self.image_plot_m.set_data(self.image_data_m)
        self.image_plot_m.set_clim(vmin=self.image_data_m.min(), vmax=self.image_data_m.max())
        self.ax[1, 0].cla()
        self.quiver_plot = self.ax[1, 0].quiver(X, Y, dataxcur.transpose()-np.mean(dataxcur[dataxcur != 0]),dataycur.transpose()-np.mean(dataycur[dataycur != 0]),
                                                scale=float(self.scaleEntry.get()), scale_units='xy')
        self.ax[1, 0].set_title("Quiver Plot")
        self.ax[1, 0].set_xlabel("X Axis")
        self.ax[1, 0].set_ylabel("Y Axis")
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
        esp.moveXY(x,y)
        print("going!")
    def stop_scan(self):
        """Stops the scanning process."""
        self.is_scanning = False
        print("Stopping scan...")

    def save_data(self):
        xflat = self.X.flatten()
        yflat = self.Y.flatten()
        xdataflat = self.image_data_x.flatten()
        ydataflat = self.image_data_y.flatten()
        reflectionflat = self.image_data_m.flatten()
        data_to_save = np.column_stack((xflat, yflat, xdataflat, ydataflat,reflectionflat))
        filename = self.folder_entry.get()+'/'+self.filename.get()+".txt"
        np.savetxt(filename, data_to_save, fmt='%.6e', delimiter='\t', header='\tx\t\ty\txcurrent\tycurrent')
        if not self.switch_var:
            picfilename = self.folder_entry.get()+'/'+self.filename.get()+".png"
            self.fig.savefig(picfilename)
        print("data saved to " +filename)


    def reset_parameters(self):
        """Resets the scan parameters."""
        self.parameter_entry.delete(0, tk.END)
        print("Scan parameters reset.")

if __name__ == "__main__":
    app = ScanningMicroscopeGUI()
    app.mainloop()

