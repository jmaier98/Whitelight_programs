import serial
import time
PELLICLE = 60
EMPTY = 20
POWERMETER = 92
ROTATION_MOUNT = 3.6
class BTT:
    def __init__(self):
        super().__init__()
        self.baud = 115200
        self.d3 = serial.Serial('COM4', self.baud, timeout=1) #4 rots
        time.sleep(0.5)
        self.d3.write(('M302 S0\n').encode())
        time.sleep(0.05)
        self.d3.write(('M17 E\n').encode())
        time.sleep(0.05)
        print("Stepper Controller 3 online")

    def send_gcode(self, driver, cmd, wait=0.05):
        if driver == 3:
            self.d3.write((cmd + '\n').encode())
        time.sleep(wait)

        
    def rot_1(self, angle_x, feedrate):
        travel_mm = angle_x / ROTATION_MOUNT
        self.send_gcode(3, f'G0 X{travel_mm:.3f} F{feedrate}')
        
    def rot_2(self, angle_x, feedrate):
        travel_mm = angle_x / ROTATION_MOUNT
        self.send_gcode(3, f'G0 Y{travel_mm:.3f} F{feedrate}')

    def rot_12(self, angle_x, feedrate, offset=324.0):
        # the two waveplates move together; offset (deg) sets their relative
        # zero, i.e. waveplate 2 sits at (offset - angle_x). offset=324 is the
        # old hard coded behaviour (90 mm of travel on the Y mount).
        travel_mm = angle_x / ROTATION_MOUNT
        travel_mmy = (offset - angle_x) / ROTATION_MOUNT
        self.send_gcode(3, f'G0 X{travel_mm:.3f} Y{travel_mmy:.3f} F{feedrate}')
        
    def rot_1_2(self, angle_x, angle_y, feedrate):
        travel_mmx = angle_x / ROTATION_MOUNT
        travel_mmy = angle_y / ROTATION_MOUNT
        self.send_gcode(3, f'G0 X{travel_mmx:.3f} Y{travel_mmy:.3f} F{feedrate}')
        
        
    def close(self):
        self.d3.close()
