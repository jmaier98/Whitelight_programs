import pyvisa
import time

def set_topgate_voltage(voltage):
    top_gate_address = "GPIB::24::INSTR"
    # Create a resource manager
    rm = pyvisa.ResourceManager()
    
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(top_gate_address)
        
        # Set the desired voltage level
        inst.write(f"SOUR:VOLT:LEV {voltage}")
        inst.write("OUTP ON")
    
        
        print(f"Voltage set to {voltage} V on {top_gate_address}.")
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()
            
def set_backgate_voltage(voltage):
    back_gate_address = "GPIB::22::INSTR"
    # Create a resource manager
    rm = pyvisa.ResourceManager()
    
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(back_gate_address)
        
        # Set the desired voltage level
        inst.write(f"SOUR:VOLT:LEV {voltage}")
        inst.write("OUTP ON")
    
        
        print(f"Voltage set to {voltage} V on {back_gate_address}.")
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()


set_topgate_voltage(0)
set_backgate_voltage(3)
time.sleep(0.5)
set_topgate_voltage(1)
set_backgate_voltage(1)
time.sleep(0.5)
set_topgate_voltage(2)
set_backgate_voltage(2)
time.sleep(0.5)
