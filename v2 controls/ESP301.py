import serial
import time

class ESP301:
    """
    Python driver for Newport ESP301 Motion Controller over RS-232.
    Provides methods to control motors, home axes, and move with position verification.
    """

    def __init__(self, port="COM7", baudrate=19200, timeout=1):
        """
        Initialize the serial connection to ESP301.
        """
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)  # Allow some time for the connection to establish
        self.axis_map = {'X': 1, 'Y': 2, 'Z': 3}  # Mapping for convenience

    def send_command(self, command):
        """
        Send a command to the ESP301 and read the response.
        """
        self.ser.write(f"{command}\r\n".encode())  # Send command
        time.sleep(0.1)  # Short delay for processing
        response = self.ser.readline().decode().strip()  # Read response
        return response
    
    def quick_command(self, command):
        self.ser.write(f"{command}\r".encode())
        time.sleep(0.01)
        
    def quick_read(self):
        time.sleep(0.02)
        response = self.ser.readline().decode().strip()
        return response

    def enable_motors(self):
        """
        Enable all three motors.
        """
        for axis in range(1, 4):  # ESP301 axes are 1, 2, 3
            self.send_command(f"{axis}MO")  # Motor ON

    def home_axis(self, axis):
        """
        Home a specific axis.
        """
        self.send_command(f"{axis}OR")  # Start homing
        time.sleep(2)
        while True:
            current_position = float(self.send_command(f"{axis}TP"))  # Check if homing is complete
            if abs(current_position) < .1:
                break
            time.sleep(0.5)  # Check every 500ms
        print(f"Axis {axis} homed.")

    def move_axis(self, axis, target_position, tolerance=0.001):
        """
        Move a given axis to a target position and wait until it reaches within a tolerance.
        """
        self.send_command(f"{axis}PA{target_position}")  # Send move command
        #self.send_command(f"{axis}BG")  # Begin motion

        while True:
            current_position = float(self.send_command(f"{axis}TP"))  # Read position
            if abs(current_position - target_position) <= tolerance:
                return True
            time.sleep(0.05)  # Poll every 200ms

    def moveX(self, x):
        """Move X-axis to specified position."""
        position = -1*float(x)/175 + 6.1
        return self.move_axis(self.axis_map['X'], position)

    def moveY(self, y):
        """Move Y-axis to specified position."""
        position = float(y)/240 + 6.1
        return self.move_axis(self.axis_map['Y'], position)

    def moveZ(self, position):
        """Move Z-axis to specified position."""
        return self.move_axis(self.axis_map['Z'], position)

    def moveZbut2(self, position):
        """Move Z-axis to specified position."""
        return self.move_axis(self.axis_map['Y'], position)
    def moveZfast(self,position):
        self.send_command(f"3PA{position}")
    def close(self):
        """
        Close the serial connection.
        """
        self.ser.close()


# Example usage when running the script directly
if __name__ == "__main__":
    esp = ESP301()
    esp.enable_motors()
    esp.home_axis(3)
    #esp.home_axis(1)
    #esp.home_axis(2)
    #esp.moveX(0)
    #esp.moveY(0)
    esp.moveZ(0)    # Move Z to 2.5

    esp.close()
