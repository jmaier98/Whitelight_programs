import time
import lockin_driver_v2 as lockin
# If your driver code is in a module named "lockin_driver", you can import like this:
# from lockin_driver import open_all_connections, readx1, close_all_connections
# For this example, we'll assume the functions are available in the current namespace.

def main():
    # Open the persistent GPIB connections to all lockin amplifiers.
    lockin.open_all_connections()
    
    try:
        while True:
            # Read the x channel of lockin 1 (the middle lockin amplifier).
            x_val = lockin.readx1()
            print(f"Lockin 1 x channel: {x_val}")
            
            # Wait for 0.1 seconds before reading again.
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Measurement stopped by user.")
    finally:
        # Close the connections when done.
        lockin.close_all_connections()

if __name__ == '__main__':
    main()
