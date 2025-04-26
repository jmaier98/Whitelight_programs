import pyvisa

def list_gpib_devices():
    # Initialize the VISA resource manager
    rm = pyvisa.ResourceManager()
    
    # List all available resources
    resources = rm.list_resources()
    
    if resources:
        print("Connected VISA resources:")
        for resource in resources:
            print(resource)
    else:
        print("No VISA resources found.")
    
    # Clean up
    rm.close()

if __name__ == "__main__":
    list_gpib_devices()
