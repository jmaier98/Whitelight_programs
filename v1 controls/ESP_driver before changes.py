import pyvisa
import time

ESP_GPIB_ADDRESS = "GPIB0::1::INSTR"

def moveXY(x,y):
    if abs(x) > 150 or abs(y) > 150:
        return False
    x = float(x)/175 + 6.1
    y = float(y)/240 + 6.1
    rm = pyvisa.ResourceManager()
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(ESP_GPIB_ADDRESS)
        
        # Set the desired voltage level
        inst.write("1PA{:.5f}".format(x))
        time.sleep(0.15)
        inst.write("2PA{:.5f}".format(y))
        time.sleep(0.15)
        xd=int(inst.query("1MD?"))
        time.sleep(0.05)
        yd=int(inst.query("2MD?"))
        while xd+yd < 2:
            time.sleep(.05)
            xd=int(inst.query("1MD?"))
            time.sleep(0.05)
            yd=int(inst.query("2MD?"))
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
        
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()
    return True

def moveX(x):
    if abs(x) > 150:
        return False
    x = float(x)/175 + 6.1
    rm = pyvisa.ResourceManager()
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(ESP_GPIB_ADDRESS)
        
        # Set the desired voltage level
        inst.write("1PA{:.5f}".format(x))
        time.sleep(.1)
        inst.write("1TP?")
        time.sleep(.1)
        xd = float(inst.read())
        while abs(xd - x) > .001:
            time.sleep(.05)
            inst.write("1PA{:.5f}".format(x))
            time.sleep(.5)
            inst.write("1TP?")
            time.sleep(.1)
            xd = float(inst.read())
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
        
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()
    return True

def moveY(y):
    if abs(y) > 150:
        return False
    y = float(y)/240 + 6.1
    rm = pyvisa.ResourceManager()
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(ESP_GPIB_ADDRESS)
        
        # Set the desired voltage level
        inst.write("2PA{:.5f}".format(y))
        time.sleep(.1)
        inst.write("2TP?")
        time.sleep(.1)
        yd = float(inst.read())
        while abs(yd - y) > .001:
            time.sleep(.05)
            inst.write("2PA{:.5f}".format(y))
            time.sleep(.5)
            inst.write("2TP?")
            time.sleep(.1)
            yd = float(inst.read())
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
        
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()
    return True

if __name__ == "__main__":
    moveXY(-50,-20)
    
    

