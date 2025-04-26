
import pyvisa

import time

LOCKIN_GPIB_ADDRESS = "GPIB0::7::INSTR"
LOCKIN_GPIB_ADDRESS2 = "GPIB0::8::INSTR"
LOCKIN_GPIB_ADDRESS3 = "GPIB0::26::INSTR"

def readR1():
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(LOCKIN_GPIB_ADDRESS2)
    try:

        # Read the magnitude of the signal (R)
        r_value = inst.query("OUTP? 3")  # Assuming "OUTP? 3" reads R; adjust as needed

        return float(r_value)

    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        inst.close()

def readx1():
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(LOCKIN_GPIB_ADDRESS2)
    try:

        # Read the magnitude of the signal (R)
        r_value = inst.query("OUTP? 1")  # Assuming "OUTP? 3" reads R; adjust as needed

        return float(r_value)

    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        inst.close()

def ready1():
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(LOCKIN_GPIB_ADDRESS2)
    try:

        # Read the magnitude of the signal (R)
        r_value = inst.query("OUTP? 2")  # Assuming "OUTP? 3" reads R; adjust as needed

        return float(r_value)

    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        inst.close()
        
def readR2():
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(LOCKIN_GPIB_ADDRESS)
    try:

        # Read the magnitude of the signal (R)
        r_value = inst.query("OUTP? 3")  # Assuming "OUTP? 3" reads R; adjust as needed

        return float(r_value)

    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        inst.close()

def readx2():
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(LOCKIN_GPIB_ADDRESS)
    try:

        # Read the magnitude of the signal (R)
        r_value = inst.query("OUTP? 1")  # Assuming "OUTP? 3" reads R; adjust as needed

        return float(r_value)

    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        inst.close()

def ready2():
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(LOCKIN_GPIB_ADDRESS)
    try:

        # Read the magnitude of the signal (R)
        r_value = inst.query("OUTP? 2")  # Assuming "OUTP? 3" reads R; adjust as needed

        return float(r_value)

    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        inst.close()

def readx3():
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(LOCKIN_GPIB_ADDRESS3)
    try:

        # Read the magnitude of the signal (R)
        r_value = inst.query("OUTP? 1")  # Assuming "OUTP? 3" reads R; adjust as needed

        return float(r_value)

    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        inst.close()

def ready3():
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(LOCKIN_GPIB_ADDRESS3)
    try:

        # Read the magnitude of the signal (R)
        r_value = inst.query("OUTP? 2")  # Assuming "OUTP? 3" reads R; adjust as needed

        return float(r_value)

    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        inst.close()
