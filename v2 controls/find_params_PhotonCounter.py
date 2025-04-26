import time
import numpy as np
import matplotlib.pyplot as plt
import pyvisa

def main():
    # Connect to the SR400 over GPIB (address 23)
    rm = pyvisa.ResourceManager()
    sr400 = rm.open_resource("GPIB0::23::INSTR")
    sr400.timeout = 5000  # timeout in milliseconds
    # GPIB termination is always CR+LF
    sr400.write_termination = "\r\n"
    sr400.read_termination = "\r\n"
    
    # Set counter A input to INPUT 1 (PMT signal)
    sr400.write("CI 0,1")
    time.sleep(0.1)
    sr400.write(f"DL 0,-0.005")
    time.sleep(0.05)
    
    # Set a fixed gate width for A gate.
    # For example, set the gate width to 10 ns.
    gate_width = 10e-9  # seconds
    sr400.write(f"GW 0,{gate_width}")
    time.sleep(0.1)
    
    # Define scan parameters for the gate delay.
    # In your case the laser trigger is at 100 kHz (period ~10 µs),
    # so we scan the delay from 0 to 10 µs.
    integration_time = 2  # count for 1 second at each setting
    num_points = 50    # number of delay points to sample
    start_delay = 3.2e-7     # seconds
    stop_delay = 3.4e-7    # 10 microseconds
    
    delay_values = np.linspace(start_delay, stop_delay, num_points)
    counts_values = []
    
    # Set up live plotting using matplotlib
    plt.ion()
    fig, ax = plt.subplots()
    line, = ax.plot([], [], 'bo-')
    ax.set_xlabel("Gate Delay (s)")
    ax.set_ylabel("Counts")
    ax.set_title("Counts vs Gate Delay")
    ax.grid(True)
    
    # Loop over each delay setting
    for delay in delay_values:
        # Set the A gate delay (GD command; channel 0 for A gate)
        sr400.write(f"GD 0,{delay}")
        time.sleep(0.05)
        
        # Start a counting cycle with the CS command.

        sr400.write("CS")
        
        # Wait for the integration time plus a small margin.
        time.sleep(integration_time + 0.5)
        
        # Read counts from counter A using the QA command.
        response = sr400.query("QA")
        try:
            counts = int(response.strip())
        except ValueError:
            counts = 0
            print("eroor")
        counts_values.append(counts)
        
        # Update live plot with new data
        line.set_data(delay_values[:len(counts_values)], counts_values)
        ax.relim()
        ax.autoscale_view()
        plt.draw()
        plt.pause(0.01)
        
        print(f"Delay: {delay:.2e} s, Counts: {counts}")
        
        # Optionally, reset the counters for the next measurement (CR command)
        sr400.write("CR")
        time.sleep(0.05)
    
    plt.ioff()
    plt.show()
    
    # Determine which delay yielded the maximum counts
    max_index = np.argmax(counts_values)
    best_delay = delay_values[max_index]
    best_counts = counts_values[max_index]
    print(f"\nBest delay: {best_delay:.2e} s with {best_counts} counts")
    
if __name__ == "__main__":
    main()
