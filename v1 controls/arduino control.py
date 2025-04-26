import tkinter as tk
from tkinter import messagebox
import serial
import time
import threading

class MotorControlGUI:
    def __init__(self, master):
        self.master = master
        master.title("Arduino Motor Control")

        # Initialize serial communication
        try:
            self.ser = serial.Serial('COM3', 9600, timeout=1)  # Adjust 'COM8' to your port
            time.sleep(2)  # Wait for the connection to establish
        except serial.SerialException:
            messagebox.showerror("Serial Port Error", "Could not open serial port. Check the port name and ensure the Arduino is connected.")
            master.destroy()
            return

        # ---------------- Motor A Controls ----------------
        self.label_a = tk.Label(master, text="Motor A Steps:")
        self.label_a.grid(row=0, column=0, padx=10, pady=10)

        self.entry_a = tk.Entry(master)
        self.entry_a.grid(row=0, column=1, padx=10, pady=10)

        self.button_a = tk.Button(master, text="Send to Motor A", command=self.send_motor_a)
        self.button_a.grid(row=0, column=2, padx=10, pady=10)

        self.release_button_a = tk.Button(master, text="Release Motor A", command=self.release_motor_a)
        self.release_button_a.grid(row=0, column=3, padx=10, pady=10)

        # ---------------- Motor B Controls ----------------
        self.label_b = tk.Label(master, text="Motor B Steps:")
        self.label_b.grid(row=1, column=0, padx=10, pady=10)

        self.entry_b = tk.Entry(master)
        self.entry_b.grid(row=1, column=1, padx=10, pady=10)

        self.button_b = tk.Button(master, text="Send to Motor B", command=self.send_motor_b)
        self.button_b.grid(row=1, column=2, padx=10, pady=10)

        self.release_button_b = tk.Button(master, text="Release Motor B", command=self.release_motor_b)
        self.release_button_b.grid(row=1, column=3, padx=10, pady=10)

        # ---------------- Shutter Controls ----------------
        self.open_shutter_button = tk.Button(master, text="Open Shutter", command=self.open_shutter)
        self.open_shutter_button.grid(row=2, column=1, padx=10, pady=10)

        self.close_shutter_button = tk.Button(master, text="Close Shutter", command=self.close_shutter)
        self.close_shutter_button.grid(row=2, column=2, padx=10, pady=10)

        # ---------------- Pelical Controls ----------------
        self.insert_pelical_button = tk.Button(master, text="Insert Pelical", command=self.insert_pelical)
        self.insert_pelical_button.grid(row=3, column=1, padx=10, pady=10)

        self.remove_pelical_button = tk.Button(master, text="Remove Pelical", command=self.remove_pelical)
        self.remove_pelical_button.grid(row=3, column=2, padx=10, pady=10)

        # ---------------- BS Servo Controls ----------------
        self.button_bs_open = tk.Button(master, text="Insert BS", command=self.open_bs)
        self.button_bs_open.grid(row=4, column=1, padx=10, pady=10)

        self.button_bs_close = tk.Button(master, text="Remove BS", command=self.close_bs)
        self.button_bs_close.grid(row=4, column=2, padx=10, pady=10)

        # ---------------- LED Brightness Controls ----------------
        self.led_label = tk.Label(master, text="LED Brightness:")
        self.led_label.grid(row=5, column=0, padx=10, pady=10)

        self.led_slider = tk.Scale(master, from_=0, to=255, orient=tk.HORIZONTAL)
        self.led_slider.grid(row=5, column=1, padx=10, pady=10)

        self.set_light_button = tk.Button(master, text="Set Light", command=self.set_light)
        self.set_light_button.grid(row=5, column=2, padx=10, pady=10)

        # Close serial port when the window is closed
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ---------------- Motor A Handlers ----------------
    def send_motor_a(self):
        steps = self.entry_a.get()
        if self.validate_steps(steps):
            command = f"motorA{steps}\n"
            self.send_command(command)
        else:
            messagebox.showerror("Input Error", "Please enter a valid integer for Motor A steps.")

    def release_motor_a(self):
        command = "releaseA\n"
        self.send_command(command)

    # ---------------- Motor B Handlers ----------------
    def send_motor_b(self):
        steps = self.entry_b.get()
        if self.validate_steps(steps):
            command = f"motorB{steps}\n"
            self.send_command(command)
        else:
            messagebox.showerror("Input Error", "Please enter a valid integer for Motor B steps.")

    def release_motor_b(self):
        command = "releaseB\n"
        self.send_command(command)

    # ---------------- Shutter Handlers ----------------
    def open_shutter(self):
        command = "openShutter\n"
        self.send_command(command)

    def close_shutter(self):
        command = "closeShutter\n"
        self.send_command(command)

    # ---------------- Pelical Handlers ----------------
    def insert_pelical(self):
        command = "insertPelical\n"
        self.send_command(command)

    def remove_pelical(self):
        command = "removePelical\n"
        self.send_command(command)

    # ---------------- BS Servo Handlers ----------------
    def open_bs(self):
        command = "bsopen\n"
        self.send_command(command)

    def close_bs(self):
        command = "bsclose\n"
        self.send_command(command)

    # ---------------- LED Brightness Handler ----------------
    def set_light(self):
        brightness = self.led_slider.get()
        brightness = self.led_slider.get()
        command = f"led{brightness}\n"
        self.send_command(command)

    # ---------------- Utility Methods ----------------
    def validate_steps(self, steps):
        try:
            int(steps)
            return True
        except ValueError:
            return False

    def send_command(self, command):
        threading.Thread(target=self._send_command_thread, args=(command,)).start()

    def _send_command_thread(self, command):
        try:
            self.ser.write(command.encode('utf-8'))
            response = self.ser.readline().decode('utf-8').strip()
            if response:
                print(response)
        except serial.SerialException:
            self.master.after(0, lambda: messagebox.showerror("Serial Error", "Failed to send command. Check the serial connection."))

    def on_closing(self):
        if self.ser.is_open:
            self.ser.close()
        self.master.destroy()

# Run the GUI in the main thread
if __name__ == "__main__":
    root = tk.Tk()
    gui = MotorControlGUI(root)
    root.mainloop()
