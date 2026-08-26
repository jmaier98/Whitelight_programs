import sys
import numpy as np
import os
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QFileDialog, QSlider, QGroupBox, QGridLayout,
                             QMessageBox, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import pyqtgraph as pg
from pyqtgraph import ImageView
import ESP301
import seabreeze
from seabreeze.spectrometers import Spectrometer, list_devices
import time
import z_stage_driver as Zstage

class ScanWorker(QThread):
    """Worker thread for running the scan without freezing the GUI"""
    progress = pyqtSignal(int, int, int)  # x_idx, y_idx, total_points
    scan_complete = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, params, data_array, ESP, spec):
        super().__init__()
        self.params = params
        self.data_array = data_array
        self.is_running = True
        self.ESP = ESP
        self.spec = spec
        
    def run(self):
        try:
            x_positions = np.arange(self.params['x_start'], 
                                   self.params['x_stop'] + self.params['x_step']/2, 
                                   self.params['x_step'])
            y_positions = np.arange(self.params['y_start'], 
                                   self.params['y_stop'] + self.params['y_step']/2, 
                                   self.params['y_step'])
            
            total_points = len(x_positions) * len(y_positions)
            point_count = 0
            
            for i, y in enumerate(y_positions):
                if not self.is_running:
                    break
                
                self.set_y_pos(y)
                for j, x in enumerate(x_positions):
                    if not self.is_running:
                        break
                    self.set_x_pos(x)

                    # Wait for specified time
                    self.msleep(int(self.params['wait_time'] * 1000))
                    
                    # Read spectrum
                    spectrum = self.read_spectrometer()
                    self.data_array[i, j, :] = spectrum
                    
                    point_count += 1
                    self.progress.emit(i, j, point_count)
            
            if self.is_running:
                self.scan_complete.emit()
                
        except Exception as e:
            self.error.emit(str(e))
    
    def set_stage_position(self, x, y):
        """Placeholder for stage positioning"""
        # TODO: Implement actual stage control
        # Example: stage.move_to(x, y)
        pass
    def set_x_pos(self, x):
        self.ESP.moveX(x)
    def set_y_pos(self, y):
        self.ESP.moveY(y)
    def read_spectrometer(self):
        """Read spectrometer with averaging"""
        num_averages = self.params.get('averages', 1)
        
        spectra = []
        for i in range(num_averages):
            spectrum = self.spec.intensities()
            spectra.append(spectrum)
            
            # Wait 20ms between reads (except after the last one)
            if i < num_averages - 1:
                self.msleep(10)
        
        # Average all spectra
        averaged_spectrum = np.mean(spectra, axis=0)
        return averaged_spectrum
    
    def stop(self):
        self.is_running = False


class SpectralMicroscope(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spectral Microscopy Control System")
        self.setGeometry(100, 100, 1400, 800)
        
        # CONFIGURATION: Adjust these based on your spectrometer
        self.num_wavelength_points = 1024  # Change this to match your spectrometer
        self.wavelength_min = 400  # nm
        self.wavelength_max = 800  # nm
        self.ESP = ESP301.ESP301()  # Initialize stage controller here
        self.spec = Spectrometer.from_serial_number('QEB1723')
        self.zstage = Zstage.Controller(which_port='COM8')
        
        # Initialize data storage
        self.wavelengths = np.linspace(self.wavelength_min, self.wavelength_max, 
                                       self.num_wavelength_points)
        self.data_array = None
        self.scan_worker = None
        
        # Setup UI
        self.init_ui()
        
    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # Left panel - Controls
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel, stretch=1)
        
        # Right panel - Plots
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel, stretch=2)
        
    def create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Scan parameters group
        scan_group = QGroupBox("Scan Parameters")
        scan_layout = QGridLayout()
        
        row = 0
        # X parameters
        scan_layout.addWidget(QLabel("X Start:"), row, 0)
        self.x_start_edit = QLineEdit("0")
        scan_layout.addWidget(self.x_start_edit, row, 1)
        
        row += 1
        scan_layout.addWidget(QLabel("X Stop:"), row, 0)
        self.x_stop_edit = QLineEdit("100")
        scan_layout.addWidget(self.x_stop_edit, row, 1)
        
        row += 1
        scan_layout.addWidget(QLabel("X Step:"), row, 0)
        self.x_step_edit = QLineEdit("10")
        scan_layout.addWidget(self.x_step_edit, row, 1)
        
        row += 1
        # Y parameters
        scan_layout.addWidget(QLabel("Y Start:"), row, 0)
        self.y_start_edit = QLineEdit("0")
        scan_layout.addWidget(self.y_start_edit, row, 1)
        
        row += 1
        scan_layout.addWidget(QLabel("Y Stop:"), row, 0)
        self.y_stop_edit = QLineEdit("100")
        scan_layout.addWidget(self.y_stop_edit, row, 1)
        
        row += 1
        scan_layout.addWidget(QLabel("Y Step:"), row, 0)
        self.y_step_edit = QLineEdit("10")
        scan_layout.addWidget(self.y_step_edit, row, 1)
        
        row += 1
        scan_layout.addWidget(QLabel("Wait Time (s):"), row, 0)
        self.wait_time_edit = QLineEdit("0.1")
        scan_layout.addWidget(self.wait_time_edit, row, 1)
        
        row += 1
        scan_layout.addWidget(QLabel("Folder:"), row, 0)
        folder_layout = QHBoxLayout()
        self.folder_edit = QLineEdit(os.getcwd())
        folder_layout.addWidget(self.folder_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(browse_btn)
        scan_layout.addLayout(folder_layout, row, 1)
        
        row += 1
        scan_layout.addWidget(QLabel("Filename:"), row, 0)
        self.filename_edit = QLineEdit("spectral_scan")
        scan_layout.addWidget(self.filename_edit, row, 1)

        row += 1
        scan_layout.addWidget(QLabel("Averages:"), row, 0)
        self.averages_edit = QLineEdit("1")
        scan_layout.addWidget(self.averages_edit, row, 1)
        
        scan_group.setLayout(scan_layout)
        layout.addWidget(scan_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_scan)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_scan)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_data)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Stage control group
        stage_group = QGroupBox("Stage Control")
        stage_layout = QGridLayout()
        
        row = 0
        stage_layout.addWidget(QLabel("X Position (µm):"), row, 0)
        self.x_pos_edit = QLineEdit("0")
        stage_layout.addWidget(self.x_pos_edit, row, 1)
        x_set_btn = QPushButton("Set")
        x_set_btn.clicked.connect(lambda: self.set_position('x'))
        stage_layout.addWidget(x_set_btn, row, 2)
        
        row += 1
        stage_layout.addWidget(QLabel("Y Position (µm):"), row, 0)
        self.y_pos_edit = QLineEdit("0")
        stage_layout.addWidget(self.y_pos_edit, row, 1)
        y_set_btn = QPushButton("Set")
        y_set_btn.clicked.connect(lambda: self.set_position('y'))
        stage_layout.addWidget(y_set_btn, row, 2)
        
        row += 1
        stage_layout.addWidget(QLabel("Z Position (µm):"), row, 0)
        self.z_pos_edit = QLineEdit("0")
        stage_layout.addWidget(self.z_pos_edit, row, 1)
        z_set_btn = QPushButton("Set")
        z_set_btn.clicked.connect(lambda: self.set_position('z'))
        stage_layout.addWidget(z_set_btn, row, 2)
        
        row += 1
        stage_layout.addWidget(QLabel("Integration Time (ms):"), row, 0)
        self.integration_time_edit = QLineEdit("100")
        stage_layout.addWidget(self.integration_time_edit, row, 1)
        int_set_btn = QPushButton("Set")
        int_set_btn.clicked.connect(self.set_integration_time)
        stage_layout.addWidget(int_set_btn, row, 2)
        
        stage_group.setLayout(stage_layout)
        layout.addWidget(stage_group)
        
        layout.addStretch()
        
        return panel
    
    def create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 2D color map
        map_label = QLabel("Spectral Map (click pixel to view spectrum)")
        layout.addWidget(map_label)
        
        self.image_view = ImageView()
        self.image_view.ui.roiBtn.hide()
        self.image_view.ui.menuBtn.hide()
        # Set viridis colormap
        self.image_view.setColorMap(pg.colormap.get('viridis'))
        layout.addWidget(self.image_view, stretch=1)
        
        # Connect click event
        self.image_view.getImageItem().mouseClickEvent = self.image_clicked
        
        # Wavelength slider
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("Wavelength:"))
        self.wavelength_slider = QSlider(Qt.Horizontal)
        self.wavelength_slider.setMinimum(0)
        self.wavelength_slider.setMaximum(len(self.wavelengths) - 1)
        self.wavelength_slider.setValue(len(self.wavelengths) // 2)
        self.wavelength_slider.valueChanged.connect(self.update_map_display)
        slider_layout.addWidget(self.wavelength_slider)
        
        self.wavelength_label = QLabel(f"{self.wavelengths[self.wavelength_slider.value()]:.1f} nm")
        slider_layout.addWidget(self.wavelength_label)
        layout.addLayout(slider_layout)
        
        # Spectrum plot
        spectrum_label = QLabel("Spectrum at Selected Position")
        layout.addWidget(spectrum_label)
        
        self.spectrum_plot = pg.PlotWidget()
        self.spectrum_plot.setLabel('left', 'Counts')
        self.spectrum_plot.setLabel('bottom', 'Wavelength', units='nm')
        self.spectrum_plot.showGrid(x=True, y=True)
        layout.addWidget(self.spectrum_plot, stretch=1)
        
        return panel
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", self.folder_edit.text())
        if folder:
            self.folder_edit.setText(folder)
    
    def set_position(self, axis):
        """Placeholder for setting stage position"""
        try:
            if axis == 'x':
                pos = float(self.x_pos_edit.text())
                # TODO: Implement actual stage control
                # stage.set_x(pos)  # pos in micrometers
                self.ESP.moveX(pos)
                print(f"Setting X position to {pos} µm")
            elif axis == 'y':
                pos = float(self.y_pos_edit.text())
                # TODO: Implement actual stage control
                # stage.set_y(pos)  # pos in micrometers
                self.ESP.moveY(pos)
                print(f"Setting Y position to {pos} µm")
            elif axis == 'z':
                pos = float(self.z_pos_edit.text())
                self.zstage.move_mm(pos, relative = False)
                # TODO: Implement actual stage control
                # stage.set_z(pos)  # pos in micrometers
                print(f"Setting Z position to {pos} µm")
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid position value")
    
    def set_integration_time(self):
        """Placeholder for setting spectrometer integration time"""
        try:
            int_time = float(self.integration_time_edit.text())
            self.spec.integration_time_micros(int_time*1e3)
            print(f"Setting integration time to {int_time} ms")
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid integration time value")
    
    def start_scan(self):
        """Start the scanning process"""
        try:
            # Get parameters
            params = {
                'x_start': float(self.x_start_edit.text()),
                'x_stop': float(self.x_stop_edit.text()),
                'x_step': float(self.x_step_edit.text()),
                'y_start': float(self.y_start_edit.text()),
                'y_stop': float(self.y_stop_edit.text()),
                'y_step': float(self.y_step_edit.text()),
                'wait_time': float(self.wait_time_edit.text()),
                'integration_time': float(self.integration_time_edit.text()),
                'averages': int(self.averages_edit.text())
            }
            
            # Calculate array dimensions
            x_points = int((params['x_stop'] - params['x_start']) / params['x_step']) + 1
            y_points = int((params['y_stop'] - params['y_start']) / params['y_step']) + 1
            self.wavelengths = self.spec.wavelengths()
            # Initialize data array
            self.data_array = np.zeros((x_points, y_points, len(self.wavelengths)))
            
            # Update UI
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(x_points * y_points)
            
            # Start worker thread
            self.scan_worker = ScanWorker(params, self.data_array, self.ESP, self.spec)
            self.scan_worker.progress.connect(self.update_progress)
            self.scan_worker.scan_complete.connect(self.scan_finished)
            self.scan_worker.error.connect(self.scan_error)
            self.scan_worker.start()
            
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid parameter values")
    
    def stop_scan(self):
        """Stop the scanning process"""
        if self.scan_worker:
            self.scan_worker.stop()
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
    
    def update_progress(self, x_idx, y_idx, point_count):
        """Update progress bar and display"""
        self.progress_bar.setValue(point_count)
        
        # Update the 2D map display
        self.update_map_display()
    
    def scan_finished(self):
        """Handle scan completion"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.information(self, "Scan Complete", "Spectral scan completed successfully!")
        self.update_map_display()
    
    def scan_error(self, error_msg):
        """Handle scan errors"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "Scan Error", f"An error occurred during scanning:\n{error_msg}")
    
    def update_map_display(self):
        """Update the 2D color map based on current wavelength slider position"""
        if self.data_array is None:
            return
        
        wavelength_idx = self.wavelength_slider.value()
        self.wavelength_label.setText(f"{self.wavelengths[wavelength_idx]:.1f} nm")
        
        # Extract 2D slice at current wavelength - intensity at selected wavelength
        map_data = self.data_array[:, :, wavelength_idx][::-1,:]
        
        # Display the map with viridis colormap
        self.image_view.setImage(map_data.T, autoRange=False, autoLevels=False)

    def image_clicked(self, event):
        """Handle clicks on the 2D map to display spectrum"""
        if self.data_array is None:
            return
        
        pos = event.pos()
        x_idx = int(pos.x())
        y_idx = int(pos.y())
        
        # Check bounds
        if (0 <= y_idx < self.data_array.shape[0] and 
            0 <= x_idx < self.data_array.shape[1]):
            
            # Get spectrum at this position
            spectrum = self.data_array[self.data_array.shape[0]-y_idx-1, x_idx, :]
            
            # Plot spectrum
            self.spectrum_plot.clear()
            self.spectrum_plot.plot(self.wavelengths, spectrum, pen='b')
    
    def save_data(self):
        """Save the data with metadata header"""
        if self.data_array is None:
            QMessageBox.warning(self, "No Data", "No data to save. Run a scan first.")
            return
        
        try:
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.filename_edit.text()}_{timestamp}.txt"
            filepath = os.path.join(self.folder_edit.text(), filename)
            
            # Prepare metadata header
            header = f"""Spectral Microscopy Data
Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Units: X, Y, Z positions in micrometers (µm)
X Start: {self.x_start_edit.text()} µm
X Stop: {self.x_stop_edit.text()} µm
X Step: {self.x_step_edit.text()} µm
Y Start: {self.y_start_edit.text()} µm
Y Stop: {self.y_stop_edit.text()} µm
Y Step: {self.y_step_edit.text()} µm
Wait Time: {self.wait_time_edit.text()} s
Averages: {self.averages_edit.text()}
Integration Time: {self.integration_time_edit.text()} ms
Data Shape: {self.data_array.shape}
Wavelength Range: {self.wavelengths[0]:.2f} - {self.wavelengths[-1]:.2f} nm
Number of Wavelengths: {len(self.wavelengths)}

Data Format: 3D array flattened to 2D
Each row represents one (x, y) position
Columns represent wavelength index (0 to {len(self.wavelengths)-1})

Wavelengths (nm): {', '.join([f'{w:.2f}' for w in self.wavelengths[:10]])}... (showing first 10)
"""
            
            # Reshape data for saving (flatten first two dimensions)
            reshaped_data = self.data_array.reshape(-1, self.data_array.shape[2])
            
            # Save with numpy
            np.savetxt(filepath, reshaped_data, header=header, 
                      fmt='%.6e', delimiter='\t')
            
            # Also save the original 3D array as .npy for easier loading
            npy_filepath = filepath.replace('.txt', '.npy')
            np.save(npy_filepath, self.data_array)
            
            # Save wavelengths separately
            wavelength_filepath = filepath.replace('.txt', '_wavelengths.txt')
            np.savetxt(wavelength_filepath, self.wavelengths, 
                      header="Wavelengths (nm)", fmt='%.4f')
            
            QMessageBox.information(self, "Save Complete", 
                                   f"Data saved successfully:\n{filepath}\n{npy_filepath}\n{wavelength_filepath}")
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Error saving data:\n{str(e)}")


def main():
    app = QApplication(sys.argv)
    window = SpectralMicroscope()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
