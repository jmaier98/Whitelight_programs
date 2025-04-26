import pyvisa

# Function to log all settings from Keithley 2400
def log_keithley2400_settings():
    # Initialize VISA resource manager
    rm = pyvisa.ResourceManager()
    # Connect to Keithley 2400 (adjust the address as necessary)
    keithley = rm.open_resource('GPIB0::22::INSTR')

    # Ensure the device is in a known state
    keithley.write('*RST')
    keithley.write('*CLS')

    # List of commands to query settings; add more according to your needs
    settings_commands = [
        '*IDN?',          # Queries the device identification
        ':SOUR:FUNC?',    # Source function
        ':SOUR:VOLT?',    # Source voltage
        ':SOUR:CURR?',    # Source current
        ':SENS:FUNC?',    # Sense function
        ':SENS:VOLT:PROT?', # Voltage protection level
        ':SENS:CURR:PROT?', # Current protection level
        ':OUTP?',         # Output state
        # Add more settings queries as required
    ]

    # Dictionary to hold the settings
    settings = {}

    # Query each setting and store the response
    for cmd in settings_commands:
        keithley.write(cmd)
        response = keithley.read()
        settings[cmd] = response.strip()

    # Close the connection
    keithley.close()

    # Return the gathered settings
    return settings

# Logging all settings
settings = log_keithley2400_settings()

# Print the settings
for cmd, value in settings.items():
    print(f"{cmd}: {value}")
