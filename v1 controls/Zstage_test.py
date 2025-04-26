import serial
import time

class StepperMotorDriver:
    def __init__(self, port, baudrate=9600, timeout=1):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)  # Give the serial connection time to initialize

    def move_motor(self, motor, direction, steps):
        """
        Control the stepper motor.
        :param motor: 'M1' for motor 1 or 'M2' for motor 2
        :param direction: 'F' for forward or 'B' for backward
        :param steps: Number of steps to move
        """
        command = f"{motor}{direction}{steps}\n"
        self.ser.write(command.encode())
        print(f"Sent command: {command.strip()}")

    def abort_movement(self):
        """Send abort command to stop motor movement."""
        self.ser.write(b"ABORT\n")
        print("Sent abort command.")

    def release_motor(self, motor):
        """Release the motor to allow manual rotation."""
        command = f"RELEASE{motor[-1]}\n"
        self.ser.write(command.encode())
        print(f"Sent release command for motor {motor}")

    def close(self):
        """Close the serial connection."""
        self.ser.close()


if __name__ == "__main__":
    # Replace 'COM3' with the correct port for your Arduino (on Linux it may be '/dev/ttyUSB0')
    driver = StepperMotorDriver(port='COM7')

    try:
        # Move motor 1 forward 100 steps
        driver.move_motor('M2', 'F', 100)

        # Wait for 2 seconds
        time.sleep(10)

        # Release motor 1 to allow manual rotation
        driver.release_motor('M2')

    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        driver.close()
