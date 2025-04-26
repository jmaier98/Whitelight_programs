import threading
import serial
import time
import re

com_port = 'COM6'
baud_rate = 9600
serial_lock = threading.Lock()

def get_nm():
    with serial_lock:  # Ensure only one thread accesses the port at a time
        with serial.Serial(com_port, baud_rate, timeout=1) as ser:
            print('?NM\r')
            ser.write('?NM\r'.encode())
            time.sleep(0.5)
            response = ser.read(100)
            print(response.decode())
    return float(re.findall("\d+\.\d+", response.decode())[0])

def set_nm_min(x):
    with serial_lock:
        with serial.Serial(com_port, baud_rate, timeout=1) as ser:
            cmd = f'{x} NM/MIN\r'
            print(cmd)
            ser.write(cmd.encode())
            time.sleep(0.5)
            response = ser.read(100)
            print(response.decode())
    return x

def set_nm(x):
    speed = 2000
    with serial_lock:
        with serial.Serial(com_port, baud_rate, timeout=1) as ser:
            cmd = f'{x:.2f} NM\r'
            print(cmd)
            ser.write(cmd.encode())
            time.sleep(0.5)
            attempts = 0
            timeout_attempts = 100
            while attempts < timeout_attempts:
                response = ser.read(100)
                print(response.decode())
                if 'ok' in response.decode():
                    print("Command executed successfully.")
                    break
                else:
                    print("waiting")
                    time.sleep(0.5)
                    attempts += 1
    return x

if __name__ == "__main__":
    print(get_nm())
    set_nm_min(5000)
    set_nm(0)




