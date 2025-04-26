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
            self.ser = serial.Serial('COM8', 9600, timeout=1)  # Adjust 'COM3' to your port
            time.sleep(2)  # Wait for the connection to establish
        except serial.SerialException:
            messagebox.showerror("Serial Port Error", "Could not open serial port. Check the port name and ensure the Arduino is connected.")
            master.destroy()
            return

        # Create labels and entry fields for Motor A
        self.label_a = tk.Label(master, text="Motor A Steps:")
        self.label_a.grid(row=0, column=0, padx=10, pady=10)

        self.entry_a = tk.Entry(master)
        self.entry_a.grid(row=0, column=1, padx=10, pady=10)

        self.button_a = tk.Button(master, text="Send to Motor A", command=self.send_motor_a)
        self.button_a.grid(row=0, column=2, padx=10, pady=10)

        # Release Motor A button
        self.release_button_a = tk.Button(master, text="Release Motor A", command=self.release_motor_a)
        self.release_button_a.grid(row=0, column=3, padx=10, pady=10)

        # Create labels and entry fields for Motor B
        self.label_b = tk.Label(master, text="Motor B Steps:")
        self.label_b.grid(row=1, column=0, padx=10, pady=10)

        self.entry_b = tk.Entry(master)
        self.entry_b.grid(row=1, column=1, padx=10, pady=10)

        self.button_b = tk.Button(master, text="Send to Motor B", command=self.send_motor_b)
        self.button_b.grid(row=1, column=2, padx=10, pady=10)

        # Release Motor B button
        self.release_button_b = tk.Button(master, text="Release Motor B", command=self.release_motor_b)
        self.release_button_b.grid(row=1, column=3, padx=10, pady=10)

        # Open Shutter button
        self.open_shutter_button = tk.Button(master, text="Open Shutter", command=self.open_shutter)
        self.open_shutter_button.grid(row=2, column=1, padx=10, pady=10)

        # Close Shutter button
        self.close_shutter_button = tk.Button(master, text="Close Shutter", command=self.close_shutter)
        self.close_shutter_button.grid(row=2, column=2, padx=10, pady=10)

        # Insert Pelical button
        self.open_shutter_button = tk.Button(master, text="Insert Pelical", command=self.insert_pelical)
        self.open_shutter_button.grid(row=3, column=1, padx=10, pady=10)

        # Remove Pelical button
        self.close_shutter_button = tk.Button(master, text="Remove Pelical", command=self.remove_pelical)
        self.close_shutter_button.grid(row=3, column=2, padx=10, pady=10)

        # Close serial port when the window is closed
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def send_motor_a(self):
        steps = self.entry_a.get()
        if self.validate_steps(steps):
            command = f"motorA{steps}\n"
            self.send_command(command)
        else:
            messagebox.showerror("Input Error", "Please enter a valid integer for Motor A steps.")

    def send_motor_b(self):
        steps = self.entry_b.get()
        if self.validate_steps(steps):
            command = f"motorB{steps}\n"
            self.send_command(command)
        else:
            messagebox.showerror("Input Error", "Please enter a valid integer for Motor B steps.")

    def release_motor_a(self):
        command = "releaseA\n"
        self.send_command(command)

    def release_motor_b(self):
        command = "releaseB\n"
        self.send_command(command)

    def open_shutter(self):
        command = "openShutter\n"
        self.send_command(command)

    def close_shutter(self):
        command = "closeShutter\n"
        self.send_command(command)

    def insert_pelical(self):
        command = "insertPelical\n"
        self.send_command(command)

    def remove_pelical(self):
        command = "removePelical\n"
        self.send_command(command)

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



