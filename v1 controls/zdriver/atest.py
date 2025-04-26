import clr
import sys
import time
# Path to Kinesis DLLs
dll_path = r"C:\Program Files\Thorlabs\Kinesis"  # Adjust as needed
sys.path.append(dll_path)

# Add references to the required Kinesis DLLs
clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")
clr.AddReference("Thorlabs.MotionControl.KCube.StepperMotorCLI")
from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI
from Thorlabs.MotionControl.KCube.StepperMotorCLI import KCubeStepper
from System import String

def initialize_device():
    # Path to Kinesis DLLs
    
    # Initialize the device manager
    DeviceManagerCLI.BuildDeviceList()
    time.sleep(2)  # Wait for devices to be detected

    # Get the list of available devices
    available_devices = DeviceManagerCLI.GetDeviceList()
    available_devices_python = [str(device) for device in available_devices]

    # Print available devices
    print("Available devices:", available_devices_python)

    # Replace with your device serial number
    serial_no = "49875025"

    if serial_no not in available_devices_python:
        raise Exception(f"Device {serial_no} is not connected or not recognized.")

    try:
        # Create and connect to the device
        device = KCubeStepper.CreateKCubeStepper(serial_no)
        if not device.IsConnected:
            device.Connect(serial_no)

        # Wait for settings initialization
        if not device.IsSettingsInitialized():
            device.WaitForSettingsInitialized(5000)

        # Start polling and enable the device
        device.StartPolling(250)
        time.sleep(0.25)
        device.EnableDevice()
        time.sleep(0.25)

    except Exception as e:
        raise Exception(f"Failed to connect to the device: {str(e)}")

    return device

# Example usage
try:
    stage = initialize_device()
    print("Device initialized successfully.")
except Exception as e:
    print(f"Error: {str(e)}")
