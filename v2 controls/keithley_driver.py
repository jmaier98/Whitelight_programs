import pyvisa
import time

def ramp_topgate_voltage(target, rate):
    curr = 0
    initial = get_topgate_voltage()
    while target-initial > 0.0001:
        initial += min(target-initial,rate)
        curr = set_topgate_voltage(initial)
        time.sleep(0.005)
    while target-initial < -0.0001:
        initial -= min(initial-target,rate)
        curr = set_topgate_voltage(initial)
        time.sleep(0.005)
    return curr
def ramp_backgate_voltage(target, rate):
    curr = 0
    initial = get_backgate_voltage()
    while target-initial > 0.0001:
        initial += min(target-initial,rate)
        curr = set_backgate_voltage(initial)
        time.sleep(0.005)
    while target-initial < -0.0001:
        initial -= min(initial-target,rate)
        curr = set_backgate_voltage(initial)
        time.sleep(0.005)
    return curr
def set_topgate_voltage(voltage):
    top_gate_address = "GPIB::24::INSTR"
    # Create a resource manager
    rm = pyvisa.ResourceManager()
    
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(top_gate_address)
        
        # Set the desired voltage level
        inst.write("SOUR:VOLT:LEV {:.4f}".format(voltage))
        inst.write("OUTP ON")
        current = float(inst.query("MEAS:CURR?"))
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()
    return current

def get_topgate_voltage():
    top_gate_address = "GPIB::24::INSTR"
    # Create a resource manager
    rm = pyvisa.ResourceManager()
    
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(top_gate_address)
        
        # Set the desired voltage level
        inst.write("SOUR:VOLT?")
        voltage = inst.read()
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()
    return float(voltage)
def get_backgate_voltage():
    top_gate_address = "GPIB::22::INSTR"
    # Create a resource manager
    rm = pyvisa.ResourceManager()
    
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(top_gate_address)
        
        # Set the desired voltage level
        inst.write("SOUR:VOLT?")
        voltage = inst.read()
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()
    return float(voltage)
def set_backgate_voltage(voltage):
    back_gate_address = "GPIB::22::INSTR"
    # Create a resource manager
    rm = pyvisa.ResourceManager()
    
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(back_gate_address)
        
        # Set the desired voltage level
        inst.write("SOUR:VOLT:LEV {:.4f}".format(voltage))
        inst.write("OUTP ON")
        current = float(inst.query("MEAS:CURR?"))
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()
    return current
if __name__ == "__main__":
    print(set_backgate_voltage(0))
    print(set_topgate_voltage(0))
    

