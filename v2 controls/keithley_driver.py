import pyvisa
import time

def clear_topgate_buffer():
    top_gate_address = "GPIB::24::INSTR"
    rm = pyvisa.ResourceManager()
    try:
        inst = rm.open_resource(top_gate_address)
        inst.write("*CLS")          # Clear status registers and output queue
        inst.write("TRAC:CLE")      # Clear the data buffer
        inst.clear()                # VISA-level interface clear
    except pyvisa.VisaIOError as e:
        print(f"Error clearing topgate buffer: {e}")
    finally:
        if 'inst' in locals():
            inst.close()

def clear_backgate_buffer():
    back_gate_address = "GPIB::22::INSTR"
    rm = pyvisa.ResourceManager()
    try:
        inst = rm.open_resource(back_gate_address)
        inst.write("*CLS")
        inst.write("TRAC:CLE")
        inst.clear()
    except pyvisa.VisaIOError as e:
        print(f"Error clearing backgate buffer: {e}")
    finally:
        if 'inst' in locals():
            inst.close()

def parse_keithley_reading(raw):
    """
    Keithley instruments often return compound strings like:
      '+0.000000E+00,-5.516362E-11,+9.910000E+37,+1.082812E+02,+2.150800E+04'
    This extracts only the first (primary) value.
    """
    return float(raw.strip().split(",")[0])

def ramp_topgate_voltage(target, rate):
    curr = 0
    initial = get_topgate_voltage()
    while target - initial > 0.0001:
        initial += min(target - initial, rate)
        curr = set_topgate_voltage(initial)
        time.sleep(0.005)
    while target - initial < -0.0001:
        initial -= min(initial - target, rate)
        curr = set_topgate_voltage(initial)
        time.sleep(0.005)
    return curr

def ramp_backgate_voltage(target, rate):
    curr = 0
    initial = get_backgate_voltage()
    while target - initial > 0.0001:
        initial += min(target - initial, rate)
        curr = set_backgate_voltage(initial)
        time.sleep(0.005)
    while target - initial < -0.0001:
        initial -= min(initial - target, rate)
        curr = set_backgate_voltage(initial)
        time.sleep(0.005)
    return curr

def set_topgate_voltage(voltage):
    top_gate_address = "GPIB::24::INSTR"
    rm = pyvisa.ResourceManager()
    current = None
    try:
        inst = rm.open_resource(top_gate_address)
        inst.write("SOUR:VOLT:LEV {:.4f}".format(voltage))
        inst.write("OUTP ON")
        raw = inst.query("MEAS:CURR?")
        current = parse_keithley_reading(raw)
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        if 'inst' in locals():
            inst.close()
    return current

def get_topgate_current():
    top_gate_address = "GPIB::24::INSTR"
    rm = pyvisa.ResourceManager()
    current = None
    try:
        inst = rm.open_resource(top_gate_address)
        raw = inst.query("MEAS:CURR?")
        current = parse_keithley_reading(raw)
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        if 'inst' in locals():
            inst.close()
    return current

def get_topgate_voltage():
    top_gate_address = "GPIB::24::INSTR"
    rm = pyvisa.ResourceManager()
    voltage = None
    try:
        inst = rm.open_resource(top_gate_address)
        inst.write("SOUR:VOLT?")
        voltage = inst.read()
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        if 'inst' in locals():
            inst.close()
    return float(voltage)

def get_backgate_voltage():
    back_gate_address = "GPIB::22::INSTR"
    rm = pyvisa.ResourceManager()
    voltage = None
    try:
        inst = rm.open_resource(back_gate_address)
        inst.write("SOUR:VOLT?")
        voltage = inst.read()
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        if 'inst' in locals():
            inst.close()
    return float(voltage)

def set_backgate_voltage(voltage):
    back_gate_address = "GPIB::22::INSTR"
    rm = pyvisa.ResourceManager()
    current = None
    try:
        inst = rm.open_resource(back_gate_address)
        inst.write("SOUR:VOLT:LEV {:.4f}".format(voltage))
        inst.write("OUTP ON")
        raw = inst.query("MEAS:CURR?")
        current = parse_keithley_reading(raw)
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        if 'inst' in locals():
            inst.close()
    return current

def get_backgate_current():
    back_gate_address = "GPIB::22::INSTR"
    rm = pyvisa.ResourceManager()
    current = None
    try:
        inst = rm.open_resource(back_gate_address)
        raw = inst.query("MEAS:CURR?")
        current = parse_keithley_reading(raw)
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        if 'inst' in locals():
            inst.close()
    return current

if __name__ == "__main__":
    clear_backgate_buffer()
    clear_topgate_buffer()
    print(set_backgate_voltage(0))
    print(set_topgate_voltage(0))
