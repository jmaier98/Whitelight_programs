import serial
import time

# Open serial connection
ser = serial.Serial('COM5', baudrate=9600, timeout=1)
time.sleep(2)  # Wait for the device to initialize

# Try with different line endings
commands = [b'?\r', b'?\n', b'?\r\n']  # Try each format

for cmd in commands:
    ser.write(cmd)
    time.sleep(0.5)
    response = ser.readline().decode('utf-8').strip()
    print(f"Sent: {cmd}, Response: {response}")

ser.close()
