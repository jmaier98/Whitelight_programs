import pyvisa

rm = pyvisa.ResourceManager()
devices = rm.list_resources()
print("Connected GPIB Devices:", devices)
