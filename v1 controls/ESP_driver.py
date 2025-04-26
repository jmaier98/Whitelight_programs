import pyvisa
import time

ESP_GPIB_ADDRESS = "GPIB0::1::INSTR"

def moveXY(x,y):
    if abs(x) > 150 or abs(y) > 150:
        return False
    x = -1*float(x)/175 + 6.1
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
def rotate(deg):
    rm = pyvisa.ResourceManager()
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(ESP_GPIB_ADDRESS)

        # Set the desired voltage level
        inst.write("3PA{:.2f}".format(deg))
        time.sleep(.1)
        inst.write("3TP?")
        time.sleep(.1)

        while True:
            try:
                # Attempt to read the value and convert it to float
                xd = float(inst.read())
                
                # Break the loop if the condition is met
                if abs(xd - deg) <= .001:
                    break
            except ValueError:
                # Handle bad reads and retry
                print("Received bad data, retrying...")
            
            # Reattempt setting the desired voltage
            time.sleep(.05)
            inst.write("3PA{:.2f}".format(deg))
            time.sleep(.5)
            inst.write("3TP?")
            time.sleep(.1)

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
    x = -1*float(x)/175 + 6.1
    rm = pyvisa.ResourceManager()
    '''try:
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
            inst.close()'''
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(ESP_GPIB_ADDRESS)

        # Set the desired voltage level
        inst.write("1PA{:.5f}".format(x))
        time.sleep(.1)
        inst.write("1TP?")
        time.sleep(.1)
        while True:
            try:
                # Attempt to read the value and convert it to float
                xd = float(inst.read())
                
                # Break the loop if the condition is met
                if abs(xd - x) <= .001:
                    break
            except ValueError:
                # Handle bad reads and retry
                print("Received bad data, retrying...")
            
            # Reattempt setting the desired voltage
            time.sleep(.05)
            inst.write("1PA{:.5f}".format(x))
            time.sleep(.5)
            inst.write("1TP?")
            time.sleep(.1)
        success = True 
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
        success = False
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()
    return success

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

        while True:
            try:
                # Attempt to read the value and convert it to float
                yd = float(inst.read())
                
                # Break the loop if the condition is met
                if abs(yd - y) <= .001:
                    break
            except ValueError:
                # Handle bad reads and retry
                print("Received bad data, retrying...")
            
            # Reattempt setting the desired voltage
            time.sleep(.05)
            inst.write("2PA{:.5f}".format(y))
            time.sleep(.5)
            inst.write("2TP?")
            time.sleep(.1)
        success = True
    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
        success = False
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()
    return success
def moveZ(z):
   
    rm = pyvisa.ResourceManager()
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(ESP_GPIB_ADDRESS)

        # Set the desired voltage level
        inst.write("3PA{:.5f}".format(z))
        time.sleep(.1)
        inst.write("3TP?")
        time.sleep(.1)

        while True:
            try:
                # Attempt to read the value and convert it to float
                zd = float(inst.read())
                
                # Break the loop if the condition is met
                if abs(zd - z) <= .001:
                    break
            except ValueError:
                # Handle bad reads and retry
                print("Received bad data, retrying...")
            
            # Reattempt setting the desired voltage
            time.sleep(.05)
            inst.write("3PA{:.5f}".format(z))
            time.sleep(.5)
            inst.write("3TP?")
            time.sleep(.1)

    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")

    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()
    return True
def moveZ1(z):
    rm = pyvisa.ResourceManager()
    try:
        # Open the connection to the instrument
        inst = rm.open_resource(ESP_GPIB_ADDRESS)
        
        # Set appropriate timeouts
        inst.timeout = 5000  # 5 seconds or adjust as needed

        # Send the move command
        inst.write("3PA{:.5f}".format(z))
        time.sleep(0.1)

        # Query position until it reaches the target
        while True:
            try:
                inst.write("3TP?")
                response = inst.read()
                zd = float(response)

                # Break the loop if position is within tolerance
                if abs(zd - z) <= 0.001:
                    break
            except ValueError:
                print("Received bad data, retrying...")
            except pyvisa.VisaIOError as e:
                print(f"Communication error: {e}")
                time.sleep(0.5)  # Add a small delay before retrying

            # Retry sending the position command if needed
            time.sleep(0.1)
            inst.write("3PA{:.5f}".format(z))

    except pyvisa.VisaIOError as e:
        print(f"Error communicating with the instrument: {e}")
    finally:
        # Close the connection
        if 'inst' in locals():
            inst.close()

if __name__ == "__main__":
    #moveXY(0,0)
    rotate(0)
    
    

