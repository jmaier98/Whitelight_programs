
import sys
import os
import shutil

import time
import numpy as np
import matplotlib.pyplot as plt
plt.ion()
import seabreeze
from seabreeze.spectrometers import Spectrometer, list_devices


print(list_devices())
# spec = Spectrometer.from_serial_number('JAZA0593')
# spec.integration_time_micros(100000)



def main():
    spec = Spectrometer.from_serial_number('QEB1723')
    intTime = 8
    # Set integration time
    spec.integration_time_micros(intTime*1e3)
    # Get wavelength axis
    wavelength = spec.wavelengths()
    idxLow = np.abs(wavelength-850).argmin()
    idxHigh = np.abs(wavelength-1000).argmin()
    
    # time reading out a spectrum once
    start = time.time()
    print(len(spec.intensities()))
    end = time.time()
    print(f"Time to read out spectrum once: {end-start}")

    fig = plt.figure()
    ax = plt.subplot(111)
    
    
    line, = ax.plot(wavelength[idxLow:idxHigh],spec.intensities()[idxLow:idxHigh])
    ax.set_ylim([0,65000])
    ax.set_xlabel("Wavelength (nm)")

 

    try:
        while True:
            line.set_ydata(spec.intensities()[idxLow:idxHigh])
            fig.canvas.draw()        
            fig.canvas.flush_events()
     
    except KeyboardInterrupt:
        pass
    line.set_ydata(spec.intensities()[idxLow:idxHigh])
    fig.canvas.draw()        
    fig.canvas.flush_events()
     
    
    spec.close()
     
     
     
    return




if __name__ == '__main__':
    main()

