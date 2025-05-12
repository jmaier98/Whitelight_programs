import pyvisa
import time

# GPIB addresses for your lockin amplifiers:
LOCKIN_GPIB_ADDRESS   = "GPIB0::7::INSTR"   # top lockin (x2 or y current)
LOCKIN_GPIB_ADDRESS2  = "GPIB0::8::INSTR"   # middle lockin (x1 or x current)
LOCKIN_GPIB_ADDRESS3  = "GPIB0::26::INSTR"  # bottom lockin (x3)

# Create a single ResourceManager instance.
rm = pyvisa.ResourceManager()

# delay between writing and reading
lockin_read_delay = .01
# Dictionary to hold persistent instrument connections.
_instruments = {
    'lockin1': None,  # Will refer to the middle lockin (address: LOCKIN_GPIB_ADDRESS2)
    'lockin2': None,  # Will refer to the top lockin (address: LOCKIN_GPIB_ADDRESS)
    'lockin3': None,  # Will refer to the bottom lockin (address: LOCKIN_GPIB_ADDRESS3)
}

def open_all_connections():
    """
    Open persistent GPIB connections to all lockin amplifiers.
    Call this once at the start of a scan.
    """
    global _instruments
    if _instruments['lockin1'] is None:
        _instruments['lockin1'] = rm.open_resource(LOCKIN_GPIB_ADDRESS2)
    if _instruments['lockin2'] is None:
        _instruments['lockin2'] = rm.open_resource(LOCKIN_GPIB_ADDRESS)
    if _instruments['lockin3'] is None:
        _instruments['lockin3'] = rm.open_resource(LOCKIN_GPIB_ADDRESS3)

def close_all_connections():
    """
    Close all persistent GPIB connections.
    Call this once when your scan (or measurement session) is complete.
    """
    global _instruments
    for key, inst in _instruments.items():
        if inst is not None:
            try:
                inst.close()
            except Exception as e:
                print(f"Error closing {key}: {e}")
            _instruments[key] = None
# --- Functions for the middle lockin amplifier (lockin1) ---
def readR1():
    try:
        _instruments['lockin1'].write("OUTP? 3")
        time.sleep(lockin_read_delay)
        return float(_instruments['lockin1'].read())
    except Exception as e:
        print(f"Error in readR1: {e}")
        return None

def readx1():
    try:
        _instruments['lockin1'].write("OUTP? 1")
        time.sleep(lockin_read_delay)
        return float(_instruments['lockin1'].read())
    except Exception as e:
        print(f"Error in readx1: {e}")
        return None

def readph1():
    try:
        _instruments['lockin1'].write("OUTP? 4")
        time.sleep(lockin_read_delay)
        return float(_instruments['lockin1'].read())
    except Exception as e:
        print(f"Error in readph1: {e}")
        return None

def ready1():
    try:
        _instruments['lockin1'].write("OUTP? 2")
        time.sleep(lockin_read_delay)
        return float(_instruments['lockin1'].read())
    except Exception as e:
        print(f"Error in ready1: {e}")
        return None

# --- Functions for the top lockin amplifier (lockin2) ---
def readR2():
    try:
        _instruments['lockin2'].write("OUTP? 3")
        time.sleep(lockin_read_delay)
        return float(_instruments['lockin2'].read())
    except Exception as e:
        print(f"Error in readR2: {e}")
        return None

def readx2():
    try:
        _instruments['lockin2'].write("OUTP? 1")
        time.sleep(lockin_read_delay)
        return float(_instruments['lockin2'].read())
    except Exception as e:
        print(f"Error in readx2: {e}")
        return None

def readph2():
    try:
        _instruments['lockin2'].write("OUTP? 4")
        time.sleep(lockin_read_delay)
        return float(_instruments['lockin2'].read())
    except Exception as e:
        print(f"Error in readph2: {e}")
        return None

def ready2():
    try:
        _instruments['lockin2'].write("OUTP? 2")
        time.sleep(lockin_read_delay)
        return float(_instruments['lockin2'].read())
    except Exception as e:
        print(f"Error in ready2: {e}")
        return None

# --- Functions for the bottom lockin amplifier (lockin3) ---
def readx3():
    try:
        _instruments['lockin3'].write("OUTP? 1")
        time.sleep(lockin_read_delay)
        return float(_instruments['lockin3'].read())
    except Exception as e:
        print(f"Error in readx3: {e}")
        return None

def ready3():
    try:
        _instruments['lockin3'].write("OUTP? 2")
        time.sleep(lockin_read_delay)
        return float(_instruments['lockin3'].read())
    except Exception as e:
        print(f"Error in ready3: {e}")
        return None
