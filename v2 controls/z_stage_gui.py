import tkinter as tk
from tkinter import font
import threading
import time
import serial  # needed for exception handling

# Import your z stage driver (make sure it's in your PYTHONPATH or same directory)
from z_stage_driver import Controller

# Create an instance of the stage controller (adjust the COM port as needed)
controller = Controller(which_port='COM8', verbose=True, very_verbose=False)

# Create a lock to ensure that only one move command runs at a time.
driver_lock = threading.Lock()

# Set up the Tkinter window.
root = tk.Tk()
root.title("Z Stage Jog Controller")

# Create a label to display the current position in a large font.
position_font = font.Font(size=36)
position_label = tk.Label(root, text="0.000 mm", font=position_font)
position_label.pack(pady=20)

def update_position_once():
    """Update the displayed stage position once after a command completes."""
    try:
        pos = controller.get_position_mm()  # Assumes a method to retrieve position in mm
        position_label.config(text="{:.3f} mm".format(pos))
    except Exception as e:
        position_label.config(text="Error: " + str(e))

def home_stage():
    """Call the home function in a separate thread and update position when done."""
    def thread_home():
        try:
            with driver_lock:
                # Start homing without blocking on the read.
                controller._home(block=False)
            # Now poll for homed status with a timeout.
            timeout = 60  # seconds
            start_time = time.time()
            while True:
                if controller._get_homed_status():
                    break
                if time.time() - start_time > timeout:
                    raise Exception("Timeout while homing")
                time.sleep(0.1)
            # Once homing is complete, update the position on the GUI thread.
            root.after(0, update_position_once)
        except Exception as e:
            print("Error in homing:", e)
    threading.Thread(target=thread_home, daemon=True).start()

def jog(amount):
    """Jog the stage by a relative amount (in mm) and update position on completion."""
    def thread_jog():
        try:
            with driver_lock:
                # This blocking call waits for move confirmation.
                controller.move_mm(amount, relative=True)
            # Once the move is complete, update the position on the GUI thread.
            root.after(0, update_position_once)
        except Exception as e:
            print("Jog error:", e)
    threading.Thread(target=thread_jog, daemon=True).start()

# Create a Home button.
home_button = tk.Button(root, text="Home", command=home_stage, width=15, height=2)
home_button.pack(pady=10)

# Create a frame to hold all jog button rows.
jog_frame = tk.Frame(root)
jog_frame.pack(pady=10)

# Define the jog increments (in mm)
increments = [5, 1, 0.1, 0.01, 0.001]

# For each increment, create a row with a label and two buttons (+ and -).
for inc in increments:
    row = tk.Frame(jog_frame)
    row.pack(pady=5)
    
    label = tk.Label(row, text="Jog ±{} mm".format(inc), width=15)
    label.pack(side=tk.LEFT)
    
    # Use lambda with default parameter to capture the current increment value.
    btn_plus = tk.Button(row, text="+", width=5, command=lambda i=inc: jog(i))
    btn_plus.pack(side=tk.LEFT, padx=5)
    
    btn_minus = tk.Button(row, text="-", width=5, command=lambda i=inc: jog(-i))
    btn_minus.pack(side=tk.LEFT, padx=5)

# Initialize the position label once at startup.
update_position_once()

# Start the Tkinter event loop.
root.mainloop()
