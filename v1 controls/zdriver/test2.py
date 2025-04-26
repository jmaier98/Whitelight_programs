import win32com.client
import time

# Create the COM object for the Kinesis stage
device_manager = win32com.client.Dispatch("Thorlabs.Kinesis.DeviceManager")
device_list = device_manager.GetDeviceList()

# Assuming the MLJ050 is the first device in the list
device_id = device_list[0]  # Adjust if needed
device = win32com.client.Dispatch("Thorlabs.Kinesis.MLJ050")
device.Connect(device_id)

# Example commands
device.MoveTo(10.0)
time.sleep(1)
position = device.GetPosition()
print(f"Current position: {position}")

device.Disconnect()
del device_manager
