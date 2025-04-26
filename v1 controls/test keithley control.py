import pyvisa
def set_source_voltage(gpib_address, voltage):
    # Create a resource manager
    rm = pyvisa.ResourceManager()
    
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(gpib_address)
        
        # Reset the instrument to a known state
        inst.write("*RST")
        
        # Set the instrument to source voltage
        inst.write("SOUR:FUNC VOLT")
        
        # Set the desired voltage level
        inst.write(f"SOUR:VOLT:LEV {voltage}")
        
        # Output on
        inst.write("OUTP ON")
        
        print(f"Voltage set to {voltage} V on {gpib_address}.")
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()

if __name__ == "__main__":
    GPIB_ADDRESS = "GPIB::24::INSTR"  # Example GPIB address, adjust to your instrument's address
    VOLTAGE = 5  # Voltage level to set, adjust as needed
    
    set_source_voltage(GPIB_ADDRESS, VOLTAGE)
