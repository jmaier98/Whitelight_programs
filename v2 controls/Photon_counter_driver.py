import time
import pyvisa

class SR400:
    def __init__(self, acquisition_time=1.0, discriminator=-0.005):
        """
        Initialize the SR400 photon counter.
        
        :param resource_name: The VISA resource string, e.g. "GPIB0::10::INSTR".
        :param acquisition_time: The default acquisition (dwell) time in seconds.
        """
        rm = pyvisa.ResourceManager()
        self.inst = rm.open_resource("GPIB0::23::INSTR")
        self.inst.timeout = 5000  # timeout in ms
        # For GPIB the SR400 always uses <CR><LF> terminators.
        self.inst.write_termination = "\r\n"
        self.inst.read_termination = "\r\n"
        self.acquisition_time = acquisition_time
        # Set a fixed gate width for A gate.
        # For example, set the gate width to 10 ns.
        gate_width = 10e-9  # seconds
        self.inst.write(f"GW 0,{gate_width}")
        time.sleep(0.1)
        delay = 3.23e-7
        self.inst.write(f"GD 0,{delay}")
        time.sleep(0.05)
        nacquisition = 1e7*acquisition_time
        self.inst.write(f"CP 2,{nacquisition}")
        time.sleep(0.05)
        self.inst.write(f"DL 0,{discriminator}")
        time.sleep(0.05)
        self.inst.write(f"DT 0")
        time.sleep(0.05)
    

    def set_discriminator(self, level, channel=0):
        """
        Set the discriminator level for a given channel.
        
        For channel A, use channel=0. The level (in Volts) must lie between -0.3000 and 0.3000.
        This uses the DL command.
        
        :param level: The discriminator level in Volts.
        :param channel: 0 for channel A (default), 1 for channel B, etc.
        """
        cmd = f"DL {channel},{level}"
        self.inst.write(cmd)
        # Optionally, verify by reading back:
        # response = self.inst.query(f"DL {channel}")
        # print("Discriminator level set to:", response.strip())

    def start_acquisition(self):
        """
        Start a new count period.
        
        This sends the CS command to start counting.
        """
        self.inst.write("CR")
        #time.sleep(1)
        self.inst.write("CS")
    def set_gate(self, level, channel = 0):
        cmd = f"GM {channel},{level}"
        self.inst.write(cmd)

    def read_counts(self):
        """
        Read the most recent complete count from counter A.
        
        This sends the QA command and returns the integer count.
        If data is not ready, the SR400 returns -1.
        
        :return: The counts as an integer.
        """
        response = self.inst.query("QA")
        try:
            return int(response.strip())
        except ValueError:
            return None

    def acquire(self):
        """
        Perform a complete acquisition cycle.
        
        This method sends the start command (CS), waits for the dwell time plus a short margin,
        then reads and returns the counts.
        
        :return: The count value from counter A.
        """
        self.start_acquisition()
        # Wait for the count period to finish.
        time.sleep(self.acquisition_time + 0.1)
        return self.read_counts()
    def set_t_and_disc(self,t,disc):
        self.inst.write(f"GM 0,0")
        time.sleep(0.05)
        self.set_discriminator(disc, channel=0)
        time.sleep(0.05)

        # 2) Update the dwell time
        self.acquisition_time = t
        # SR400 expects CP 2,<N> where N = 1e7 × acquisition_time
        nacq = int(1e7 * acquisition_time)
        self.inst.write(f"CP 2,{nacq}")
        time.sleep(0.05)
        print("set acquisition time and disc")


# Example usage:
if __name__ == "__main__":
    # Replace with the correct GPIB address for your SR400.
    sr400 = SR400(acquisition_time=5, discriminator=-0.01)
    
    # Set acquisition time to 1 second.
    #sr400.set_acquisition_time(1.0)
    #sr400.set_gate(1)
    # Set discriminator level to 0.05 V on channel A.
    sr400.set_discriminator(-0.005, channel=0)
    
    # Execute an acquisition and print the result.
    counts = sr400.acquire()
    print("Counts:", counts)
    '''counts = sr400.acquire()
    print("Counts:", counts)
    counts = sr400.acquire()
    print("Counts:", counts)'''

