import clr  # pythonnet library to use .NET DLLs
import time
import sys
from System import String
from System.Collections.Generic import List

dll_path = r"C:\Program Files\Thorlabs\Kinesis"  # Adjust this to your actual Kinesis installation path
sys.path.append(dll_path)

# Load Thorlabs Motion Control libraries
clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")
clr.AddReference("Thorlabs.MotionControl.KCube.StepperMotorCLI")

# Import necessary namespaces
from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI
from Thorlabs.MotionControl.KCube.StepperMotorCLI import KCubeStepper




def initialize_device():
    # Build the device list to find connected devices
    DeviceManagerCLI.BuildDeviceList()

    # Get the list of available devices and convert to Python list
    available_devices = DeviceManagerCLI.GetDeviceList()
    available_devices_python = [str(device) for device in available_devices]

    # Print available devices
    print("Available devices:", available_devices_python)

    # Replace with your device serial number (e.g., "55000001")
    serial_no = "49875025"  # Your device serial number

    # Check if the desired device is in the available device list
    if serial_no not in available_devices_python:
        raise Exception(f"Device {serial_no} is not connected or not recognized.")

    try:
        # Create the device and connect to it
        device = KCubeStepper.CreateKCubeStepper(serial_no)
        device.Connect(serial_no)
    except Exception as e:
        raise Exception(f"Failed to connect to the device: {str(e)}")

    # Wait for the device to initialize
    if not device.IsSettingsInitialized():
        device.WaitForSettingsInitialized(5000)

    # Start polling and enable the device
    device.StartPolling(250)
    time.sleep(0.25)  # Allow time for polling to start

    # Enable the motor
    device.EnableDevice()
    time.sleep(0.25)  # Give it time to enable

    return device

def move_stage_to_position(device, position):
    """
    Move the stage to the specified position (in device units).
    """
    device.MoveTo(position, 60000)  # Move to 'position' with a timeout of 60s
    print(f"Moving to position: {position}")
    device.WaitForMessageQueue(1000)
    print("Move completed.")

def home_stage(device):
    """
    Home the stage (return to origin).
    """
    device.Home(60000)  # Home the device with a 60s timeout
    print("Homing...")
    device.WaitForMessageQueue(1000)
    print("Homing completed.")

def get_current_position(device):
    """
    Get the current position of the stage.
    """
    position = device.Position  # Retrieve the current position in device units
    print(f"Current position: {position}")
    return position

def disconnect_device(device):
    """
    Safely disconnect the device.
    """
    device.StopPolling()
    device.Disconnect(True)
    print("Device disconnected.")
