# main.py
# Main application for the EV Charging Station Monitor

import sys
import time
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, 
                            QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget, QTextBrowser, QLabel, QToolButton, QFrame)
from PyQt5.QtCore import QTimer, Qt, QSize
from PyQt5.QtGui import QPixmap, QIcon
import argparse

# Import custom modules
from data_simulator import DataSimulator
from data_logger import DataLogger
from config_manager import ConfigManager
from ui_components import GraphWidget, TableWidget, FixedButtonWidget, EnergyHubWidget, GaugeGridWidget

from unified_udp import initialize_unified_udp, get_unified_udp

from network_config import (
    DEFAULT_SERVER_IP, DEFAULT_SERVER_PORT, DEFAULT_CLIENT_PORT, DEFAULT_TIME_WINDOW, DEFAULT_UI_UPDATE_INTERVAL
)

class EVChargingMonitor(QMainWindow):
    """Main application window for EV Charging Station Monitor"""
    
    def __init__(self, use_real_data=False, udp_ip=DEFAULT_SERVER_IP, udp_port=DEFAULT_SERVER_PORT):
        super().__init__()
        
        # Store communication parameters
        self.use_real_data = use_real_data
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        
        # THEN initialize components with real data option AND the unified UDP handler
        self.data_simulator = DataSimulator(
            use_real_data=use_real_data, 
            udp_ip=udp_ip, 
            udp_port=udp_port,
            unified_udp=self.unified_udp if use_real_data and hasattr(self, 'unified_udp') else None
        )

        self.data_logger = DataLogger()
        self.config_manager = ConfigManager()
        
        # Initialize communications based on mode
        self.initialize_communication(use_real_data, udp_ip, udp_port)

        # Dictionary to track widgets for layout management
        self.widgets = {}
        
        # Set up the UI
        self.setupUI()
        
        # Set up update timer (50ms update rate = 20 FPS)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(DEFAULT_UI_UPDATE_INTERVAL) # Update interval in milliseconds (100ms)
        
        # Apply fixed positions to all widgets
        self.apply_fixed_positions()
    
    def initialize_communication(self, use_real_data=False, udp_ip=DEFAULT_SERVER_IP, udp_port=DEFAULT_SERVER_PORT):
        """
        Initialize communication system based on selected mode.
        
        Parameters:
        -----------
        use_real_data : bool
            If True, use the unified UDP handler for real hardware communication.
            If False, use simulated data only.
        udp_ip : str
            The IP address of the server to communicate with.
        udp_port : int
            The port on the server to communicate with.
        """
        if use_real_data:
            print("Initializing unified UDP handler for real data...")
            
            # Initialize the unified UDP handler
            # Use system-assigned local port (0) to avoid conflicts
            initialize_unified_udp(server_ip=udp_ip, server_port=udp_port, local_port=DEFAULT_CLIENT_PORT)
            
            # Get the UDP handler instance
            self.unified_udp = get_unified_udp()
            
            if not self.unified_udp:
                print("Failed to initialize unified UDP handler")
                return False
            
            # Connect the data logger to the UDP handler for raw data logging
            self.unified_udp.set_data_logger(self.data_logger)

            print("Unified UDP handler initialized for bidirectional communication")
            return True
        else:
            print("Using simulated data")
            return True

    def setupUI(self):
        """Set up the main UI components"""
        # Set window properties
        self.setWindowTitle("EV Charging Station Monitor")
        self.setGeometry(100, 100, 1280, 800)
        
        # Create tab widget as central widget
        self.tab_widget = QTabWidget(self)
        self.setCentralWidget(self.tab_widget)
        
        # Main tab for monitoring
        self.monitoring_tab = QWidget()
        self.tab_widget.addTab(self.monitoring_tab, "Monitoring")
        
        # About tab
        self.about_tab = QWidget()
        self.tab_widget.addTab(self.about_tab, "About")
        
        # Set the monitoring tab as our central widget for existing code
        self.central_widget = self.monitoring_tab
        
        # Create all UI elements on the monitoring tab
        self.setup_graphs()
        self.setup_tables()
        self.setup_gauges()
        self.setup_control_buttons()
                
        # Create timestamp display widget above the control buttons
        # -----------------------------------------------------
        # Create a frame with a border for the timestamp
        self.timestamp_frame = QFrame(self.central_widget)
        self.timestamp_frame.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.timestamp_frame.setLineWidth(2)
        self.timestamp_frame.setGeometry(0, 32, 240, 30)
        self.timestamp_frame.setStyleSheet('background-color: #90D5FF')

        # Create the timestamp label with tight margins
        self.timestamp_label = QLabel(self.timestamp_frame)
        self.timestamp_label.setStyleSheet(
            "font-weight: bold; color: #333333; font-size: 14px; padding: 2px;"
        )
        self.timestamp_label.setAlignment(Qt.AlignCenter)
        self.timestamp_label.setContentsMargins(0, 0, 0, 0)  # Very small margins

        # Initial size, will be updated with text content
        self.timestamp_label.setGeometry(2, 2, 236, 26)  # Tight within frame

        # Update the timestamp immediately
        self.update_timestamp()

        # Create timer to update timestamp every second
        self.timestamp_timer = QTimer(self)
        self.timestamp_timer.timeout.connect(self.update_timestamp)
        self.timestamp_timer.start(1000)  # Update every 1000ms (1 second)
        # -----------------------------------------------------

        # Add the QEERI logo to the monitoring tab
        self.logo_label = QLabel(self.central_widget)
        self.logo_label.setGeometry(1611, 20, 300, 100)  # Large logo size
        logo_pixmap = QPixmap("imgs/QEERI_logo.png")
        self.logo_label.setPixmap(logo_pixmap.scaled(300, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.logo_label.show()
        
        # Setup the About tab
        self.setup_about_tab()
        
        # setup the energy hub widget
        self.setup_energy_hub()

        # Create fullscreen toggle button in top-right corner
        self.fs_button = QPushButton(self)
        self.fs_button.setIcon(QIcon("imgs/full.png"))
        self.fs_button.setIconSize(QSize(50, 50))  # Adjust size as needed
        self.fs_button.setFixedSize(50, 50)  # Make the button itself a reasonable size
        self.fs_button.setToolTip("Toggle Fullscreen")  # Add tooltip since there's no text
        self.fs_button.setGeometry(250, 100, 50, 50)  # Position in top-right
        self.fs_button.clicked.connect(self.toggle_fullscreen)
        self.fs_button.raise_()  # Bring to front

        # Create pause/play button with toggle functionality
        self.graph_control_button = QToolButton(self.central_widget)
        self.graph_control_button.setIcon(QIcon("imgs/pause.png"))
        self.graph_control_button.setIconSize(QSize(50, 50))
        self.graph_control_button.setFixedSize(50, 50)
        self.graph_control_button.setToolTip("Pause/Resume All Graphs")
        self.graph_control_button.setCursor(Qt.PointingHandCursor)
        self.graph_control_button.setCheckable(True)
        self.graph_control_button.toggled.connect(self.toggle_graphs_pause)
        self.graph_control_button.setGeometry(310, 67, 50, 50)  # Position in top right area
        
        # Track paused state
        self.graphs_paused = False

    def toggle_graphs_pause(self, checked):
        """Toggle pause/resume state of all graphs"""
        self.graphs_paused = checked
        
        # Update button icon
        icon = QIcon("imgs/play.png" if checked else "imgs/pause.png")
        self.graph_control_button.setIcon(icon)
        
        # Update all graphs
        if hasattr(self, 'voltage_graph'):
            if checked:
                self.voltage_graph.pause_graph()
            else:
                self.voltage_graph.resume_graph()
            
        if hasattr(self, 'current_graph'):
            if checked:
                self.current_graph.pause_graph()
            else:
                self.current_graph.resume_graph()
            
        if hasattr(self, 'power_graph'):
            if checked:
                self.power_graph.pause_graph()
            else:
                self.power_graph.resume_graph()
    
    def setup_about_tab(self):
        """Set up the About tab with project information"""
        layout = QVBoxLayout(self.about_tab)
        
        # Add logo at the top
        logo_label = QLabel()
        logo_pixmap = QPixmap("imgs/QEERI_logo.png")
        logo_label.setPixmap(logo_pixmap.scaled(350, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)
        
        # Add text content
        about_text = QTextBrowser()
        about_text.setOpenExternalLinks(True)
        about_text.setHtml("""
        <div style="text-align: center;">
            <h2>EV Charging Station Monitoring System</h2>
            <p>Version 1.0</p>
            <p>&copy; 2025 QEERI</p>
            <br>
            <h3>Developed by:</h3>
            <p>Eng. Abdulaziz Alswiti</p>
            <p>a.alswiti@hotmail.com</p>
            <br>
            <h3>Under the supervision of:</h3>
            <p>Dr. Ali Sharida</p>
            <br>
            <h3>About This Project:</h3>
            <p>This advanced monitoring system provides real-time visualization and analysis of electric vehicle charging infrastructure, 
            integrating renewable energy sources with grid and battery storage solutions.</p>
            
            <h4>System Architecture:</h4>
            <p>Built on a modular Python framework, the system collects data via UDP communication from hardware interfaces, 
            processes it in real-time, and presents actionable information through an intuitive dashboard.</p>
            
            <p>The system features:</p>
            <ul style="text-align: left; margin-left: 80px; margin-right: 80px;">
                <li><strong>Advanced Visualization:</strong> Dynamic three-phase voltage and current waveforms with precise oscilloscope-like functionality</li>
                <li><strong>Comprehensive Power Flow Analysis:</strong> Real-time monitoring of bidirectional energy transfer between grid, photovoltaic system, electric vehicle, and battery storage</li>
                <li><strong>Intelligent Parameter Display:</strong> Key electrical parameters including voltage, current, power factor, THD, and frequency</li>
                <li><strong>Smart Energy Hub:</strong> Visual representation of system topology and status indicators</li>
                <li><strong>Dual-mode Data Logging:</strong> Both processed data for analysis and raw data for debugging with CSV export</li>
                <li><strong>Vehicle-to-Grid (V2G) Support:</strong> Monitoring and control of bidirectional power flow capabilities</li>
                <li><strong>Demand Response Integration:</strong> Support for smart grid demand response scenarios</li>
            </ul>
            <br>
            <p><strong>Applications:</strong> Research, development, and demonstration of EV charging solutions that optimize renewable energy integration, 
            grid stabilization, and energy cost management.</p>
            <br>
            <p>Qatar Environment and Energy Research Institute (QEERI)</p>
            <p>Current Date: %s</p>
        </div>
        """ % (time.strftime("%Y-%m-%d")))  # Add current date
        
        # Set a nice font size
        about_text.setStyleSheet("font-size: 20px;")
        
        layout.addWidget(about_text)

    def setup_graphs(self):
        """Create and configure graph widgets"""
        # Voltage graph
        self.voltage_graph = GraphWidget(self.central_widget, "Voltage Graph", "voltage_graph")
        self.voltage_graph.setup_voltage_graph()
        self.voltage_graph.show()
        self.widgets["voltage_graph"] = self.voltage_graph
        
        # Current graph
        self.current_graph = GraphWidget(self.central_widget, "Current Graph", "current_graph")
        self.current_graph.setup_current_graph()
        self.current_graph.show()
        self.widgets["current_graph"] = self.current_graph
        
        # Power graph
        self.power_graph = GraphWidget(self.central_widget, "Power Graph", "power_graph")
        self.power_graph.setup_power_graph()
        self.power_graph.show()
        self.widgets["power_graph"] = self.power_graph
    
    def setup_tables(self):
        """Create and configure table widgets"""
        # Charging Setting table
        self.charging_setting_table = TableWidget(self.central_widget, "Charging Setting", "charging_table")
        # Initial position and size will be set by apply_fixed_positions
        self.charging_setting_table.setup_charging_setting_table()
        self.charging_setting_table.save_clicked.connect(self.on_table_save)
        self.widgets["charging_table"] = self.charging_setting_table
        
        # EV Charging Setting table
        self.ev_charging_table = TableWidget(self.central_widget, "EV Charging Setting", "ev_charging_table")
        self.ev_charging_table.setup_ev_charging_setting_table()
        self.ev_charging_table.save_clicked.connect(self.on_table_save)
        self.widgets["ev_charging_table"] = self.ev_charging_table
        
        # Grid Settings table
        self.grid_settings_table = TableWidget(self.central_widget, "Grid Settings", "grid_settings_table")
        self.grid_settings_table.setup_grid_settings_table()
        self.grid_settings_table.save_clicked.connect(self.on_table_save)
        self.widgets["grid_settings_table"] = self.grid_settings_table
        
        # Show all tables after they're set up
        self.charging_setting_table.show()
        self.ev_charging_table.show()
        self.grid_settings_table.show()
    
    def setup_gauges(self):
        """
        Create and configure gauge widgets in a fixed grid layout.
        
        This method creates a single fixed widget that contains all gauges
        arranged in a 3x2 grid at position x=749, y=408 with size 581x290.
        """
        # Create the gauge grid container widget
        self.gauge_grid = GaugeGridWidget(self.central_widget, "gauge_grid")
        
        # Define gauge configurations - these determine the properties of each gauge
        gauge_configs = [
            {"title": "Frequency", "min": 49, "max": 51, "units": "Hz", "id": "frequency_gauge"},
            {"title": "Voltage RMS", "min": 0, "max": 240, "units": "V", "id": "voltage_gauge"},
            {"title": "THD", "min": 0, "max": 10, "units": "%", "id": "thd_gauge"},
            {"title": "Active Power", "min": 0, "max": 4000, "units": "W", "id": "active_power_gauge"},
            {"title": "Reactive Power", "min": 0, "max": 2000, "units": "VAr", "id": "reactive_power_gauge"},
            {"title": "Current RMS", "min": 0, "max": 20, "units": "A", "id": "current_gauge"}
        ]
        
        # Create gauges and add them to the grid
        # They will be automatically positioned in a 3x2 grid (top to bottom, left to right)
        self.gauges = []
        for config in gauge_configs:
            gauge = self.gauge_grid.add_gauge(
                config["title"], 
                config["min"], 
                config["max"],
                config["units"],
                config["id"]
            )
            self.gauges.append(gauge)  # Keep reference for updating values
        
        # Display the gauge grid
        self.gauge_grid.show()
        
        # Add to widgets dictionary - this enables saving/restoring layouts
        # Use a string ID for the entire grid rather than individual gauges
        self.widgets["gauge_grid"] = self.gauge_grid
    
    def setup_control_buttons(self):
        """Create fixed-position logging buttons at the position from config"""
        # Create non-draggable button container
        self.button_widget = FixedButtonWidget(self.central_widget, widget_id="control_buttons")
        
        # Add buttons to the widget
        start_btn = self.button_widget.add_button("Start Logging", "green", self.start_logging)
        stop_btn = self.button_widget.add_button("Stop Logging", "red", self.stop_logging)
        
        # Set initial state
        stop_btn.setEnabled(False)  # Stop button initially disabled
        
        # It will be positioned later by the apply_fixed_positions method
        
        self.button_widget.show()
        self.widgets["control_buttons"] = self.button_widget

    def setup_energy_hub(self):
        """Create and configure the Smart Energy Hub widget"""
        self.energy_hub = EnergyHubWidget(self.central_widget, "energy_hub")
        self.energy_hub.show()
        self.widgets["energy_hub"] = self.energy_hub

    
    def update_timestamp(self):
        """
        Updates the timestamp label with current date and time.
        Format: YYYY-MM-DD HH:MM:SS
        
        This shows the current system time, updating every second.
        """
        # Get current time in YYYY-MM-DD HH:MM:SS format
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        text = f"{current_time}"
        self.timestamp_label.setText(text)
        
        # Option for tighter frame around text:
        # Calculate text width and resize frame if needed
        fm = self.timestamp_label.fontMetrics()
        text_width = fm.width(text) + 20  # Add some padding
        
        # Don't make it smaller than minimum width
        frame_width = max(140, min(240, text_width))  # Between 140-240px
        
        # Center the frame
        #x_pos = max(0, (240 - frame_width) // 2)
        self.timestamp_frame.setGeometry(2, 36, frame_width, 30)
        self.timestamp_label.setGeometry(2, 2, frame_width - 4, 26)

    def update_data(self):
        """Update all UI components with new data from the simulator or real hardware"""
        
        # Use real data if available, otherwise use simulator
        if self.use_real_data and hasattr(self, 'unified_udp') and self.unified_udp:
            # Check if we're connected
            if not self.unified_udp.is_connected():
                # Temporarily fallback to simulator if connection is lost
                print("Warning: No real data available, using simulated data")
                self._update_from_simulator()
                return
                
            try:
                # Try to use real data
                self._update_from_real_data()
            except Exception as e:
                print(f"Error updating from real data: {e}")
                # Fallback to simulator on error
                self._update_from_simulator()
        else:
            # Use simulator data
            self._update_from_simulator()
            
        # If logging is active, log the data
        if self.data_logger.is_logging:
            self.data_logger.log_data(self.data_simulator)

    def _update_from_simulator(self):
        """Update UI components using simulator data"""
        # Update voltage graph
        time_data, va_data, vb_data, vc_data = self.data_simulator.get_voltage_data()
        self.voltage_graph.update_voltage_data(time_data, va_data, vb_data, vc_data)
        
        # Update current graph
        time_data, ia_data, ib_data, ic_data = self.data_simulator.get_current_data()
        self.current_graph.update_current_data(time_data, ia_data, ib_data, ic_data)
        
        # Update power graph
        time_data, p_grid, p_pv, p_ev, p_battery = self.data_simulator.get_power_data()
        self.power_graph.update_power_data(time_data, p_grid, p_pv, p_ev, p_battery)
        
        # Update tables
        table_data = self.data_simulator.get_table_data()
        self.charging_setting_table.update_values(table_data["charging_setting"])
        self.ev_charging_table.update_values(table_data["ev_charging_setting"])
        self.grid_settings_table.update_values(table_data["grid_settings"])
        
        # Update gauges
        gauge_data = self.data_simulator.get_gauge_data()
        self.gauges[0].set_value(gauge_data["frequency"])
        self.gauges[1].set_value(gauge_data["voltage_rms"])
        self.gauges[2].set_value(gauge_data["thd"])
        self.gauges[3].set_value(gauge_data["active_power"])
        self.gauges[4].set_value(gauge_data["reactive_power"])
        self.gauges[5].set_value(gauge_data["current_rms"])
        
        # Update Smart Energy Hub
        hub_data = self.data_simulator.get_hub_data()
        self.energy_hub.update_pv_status(hub_data["s1_status"])
        self.energy_hub.update_ev_status(hub_data["s2_status"])
        self.energy_hub.update_grid_status(hub_data["s3_status"])
        self.energy_hub.update_battery_status(hub_data["s4_status"])
        self.energy_hub.update_ev_soc(hub_data["ev_soc"])
        self.energy_hub.update_battery_soc(hub_data["battery_soc"])

    def _update_from_real_data(self):
        """Update UI components using real data from unified UDP handler"""
        # Get the latest data from unified UDP handler
        latest_data = self.unified_udp.get_latest_data()
        
        # Update voltage graph
        time_data, va_data, vb_data, vc_data = self.unified_udp.get_waveform_data('Grid_Voltage', time_window=DEFAULT_TIME_WINDOW)
        self.voltage_graph.update_voltage_data(time_data, va_data, vb_data, vc_data)
        
        # Update current graph
        time_data, ia_data, ib_data, ic_data = self.unified_udp.get_waveform_data('Grid_Current', time_window=DEFAULT_TIME_WINDOW)
        self.current_graph.update_current_data(time_data, ia_data, ib_data, ic_data)
        
        # Update power graph
        time_data, p_grid, p_pv, p_ev, p_battery = self.unified_udp.get_power_data(time_window=DEFAULT_TIME_WINDOW)
        self.power_graph.update_power_data(time_data, p_grid, p_pv, p_ev, p_battery)
        
        # Create table data structures from latest_data
        table_data = {
            "grid_settings": {
                "Vg_rms": latest_data.get('Grid_Voltage', 0),
                "Ig_rms": latest_data.get('Grid_Current', 0),
                "Frequency": latest_data.get('Frequency', 50.0),
                "THD": latest_data.get('THD', 0),
                "Power factor": latest_data.get('Power_Factor', 0.95)
            },
            "charging_setting": {
                "PV power": latest_data.get('PhotoVoltaic_Power', 0),
                "EV power": latest_data.get('ElectricVehicle_Power', 0),
                "Battery power": latest_data.get('Battery_Power', 0),
                "Grid power": latest_data.get('Grid_Power', 0),
                "Grid reactive power": latest_data.get('Grid_Reactive_Power', 0),
                "V_dc": latest_data.get('DCLink_Voltage', 0)
            },
            "ev_charging_setting": {
                "EV voltage": latest_data.get('ElectricVehicle_Voltage', 0),
                "EV current": latest_data.get('ElectricVehicle_Current', 0),
                "EV SoC": latest_data.get('EV_SoC', 0),
                "EV_Charging": latest_data.get('ElectricVehicle_Power', 0) < 0  # Boolean: true if charging
            }
        }
        
        # Update the tables with the real data values
        self.charging_setting_table.update_values(table_data["charging_setting"])
        self.ev_charging_table.update_values(table_data["ev_charging_setting"])
        self.grid_settings_table.update_values(table_data["grid_settings"])
        
        # Update gauges with the latest values
        self.gauges[0].set_value(latest_data.get('Frequency', 50.0))
        self.gauges[1].set_value(latest_data.get('Grid_Voltage', 0))
        self.gauges[2].set_value(latest_data.get('THD', 0))
        self.gauges[3].set_value(latest_data.get('Grid_Power', 0))
        self.gauges[4].set_value(latest_data.get('Grid_Reactive_Power', 0))
        self.gauges[5].set_value(latest_data.get('Grid_Current', 0))
        
        # Update Smart Energy Hub
        self.energy_hub.update_pv_status(latest_data.get('S1_Status', 0))
        self.energy_hub.update_ev_status(latest_data.get('S2_Status', 0))
        self.energy_hub.update_grid_status(latest_data.get('S3_Status', 0))
        self.energy_hub.update_battery_status(latest_data.get('S4_Status', 0))
        self.energy_hub.update_ev_soc(latest_data.get('EV_SoC', 0))
        self.energy_hub.update_battery_soc(latest_data.get('Battery_SoC', 0))
    
    def on_table_save(self, table_type, input_values):
        """Handle save button click from tables"""
        print(f"Saving values from {table_type}: {input_values}")
        
        # Update simulator with new values
        for param_name, value in input_values.items():
            # Map param_name to simulator attribute name
            attr_name = param_name.lower().replace(" ", "_")
            self.data_simulator.update_parameters(attr_name, value)
            
            # Force refresh of the tables in the next update cycle
            self.data_simulator.update_parameter_applied = True
        
        # Send parameter updates via unified UDP handler if in real data mode
        if self.use_real_data and hasattr(self, 'unified_udp') and self.unified_udp:
            print(f"Sending {table_type} updates via UDP: {input_values}")
            self.unified_udp.send_parameter_update(table_type, input_values)
    
    def start_logging(self):
        """Start data logging"""
        self.data_logger.start_logging()
        self.button_widget.get_button(0).setEnabled(False)  # Start button
        self.button_widget.get_button(1).setEnabled(True)   # Stop button
    
    def stop_logging(self):
        """Stop data logging"""
        log_file = self.data_logger.stop_logging()
        self.button_widget.get_button(0).setEnabled(True)   # Start button
        self.button_widget.get_button(1).setEnabled(False)  # Stop button
        
        print(f"Data logged to: {log_file}")
    
    def apply_fixed_positions(self):
        """
        Apply fixed positions and sizes to all widgets from the layout configuration file.
        This ensures all widgets are positioned exactly as specified.
        """
        # Load the configuration file
        configs = self.config_manager.load_all_configs()
        
        # Exit if no configurations found
        if not configs:
            print("No layout configuration file found.")
            return
        
        # Apply position and size to each widget
        for widget_id, widget in self.widgets.items():
            if widget_id in configs:
                config = configs[widget_id]
                
                # Extract position and size from config
                x = config["pos"]["x"]
                y = config["pos"]["y"]
                width = config["size"]["width"]
                height = config["size"]["height"]
                
                # Apply fixed position and size
                widget.setGeometry(x, y, width, height)
                widget.setFixedSize(width, height)
                
                # Special handling for table widgets to refresh layouts
                if isinstance(widget, TableWidget):
                    # Force tables to recalculate their layouts with the new size
                    if widget_id == "charging_table":
                        widget.setup_charging_setting_table()
                    elif widget_id == "ev_charging_table":
                        widget.setup_ev_charging_setting_table()
                    elif widget_id == "grid_settings_table":
                        widget.setup_grid_settings_table()
                
    def keyPressEvent(self, event):
        """Handle key press events"""
        # Press F11 to toggle fullscreen
        if event.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        # Escape key exits fullscreen but doesn't close
        elif event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
        else:
            super().keyPressEvent(event)

    def toggle_fullscreen(self):
        """Toggle between fullscreen and normal window"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def showEvent(self, event):
        """Called when the window is shown"""
        super().showEvent(event)
        
        # If fullscreen argument was provided, ensure we go fullscreen
        # after the window is properly initialized
        if hasattr(self, 'should_fullscreen') and self.should_fullscreen:
            # Use a timer to ensure window is fully loaded before fullscreen
            QTimer.singleShot(1000, self.showFullScreen)

    def closeEvent(self, event):
        """Handle window close event with graceful shutdown of all components"""
        print("Starting application shutdown sequence...")
        
        # Stop the timestamp timer
        if hasattr(self, 'timestamp_timer') and self.timestamp_timer.isActive():
            print("Stopping timestamp timer...")
            self.timestamp_timer.stop()

        # Stop logging if active
        if self.data_logger.is_logging:
            print("Stopping data logger...")
            self.data_logger.stop_logging()
        
        # Stop the update timer first to prevent accessing data during cleanup
        if hasattr(self, 'timer') and self.timer.isActive():
            print("Stopping update timer...")
            self.timer.stop()
        
        # Allow some time for threads to notice the timer has stopped
        import time
        time.sleep(0.2)
        
        # Clean shutdown of data simulator
        print("Shutting down data simulator...")
        self.data_simulator.shutdown()
        
        # Clean up unified UDP handler if it exists
        if hasattr(self, 'unified_udp') and self.unified_udp:
            print("Shutting down unified UDP handler...")
            self.unified_udp.close()
        
        print("Shutdown complete.")
        event.accept()

# Update the main block to add command line arguments:
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='EV Charging Station Monitor')
    parser.add_argument('--real-data', action='store_true', help='Use real data from UDP')
    parser.add_argument('--udp-ip', type=str, default=DEFAULT_SERVER_IP, help='UDP IP address')
    parser.add_argument('--udp-port', type=int, default=DEFAULT_SERVER_PORT, help='UDP port')
    parser.add_argument('--fullscreen', action='store_true', help='Start in fullscreen mode')
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = EVChargingMonitor(use_real_data=args.real_data, 
                              udp_ip=args.udp_ip, 
                              udp_port=args.udp_port)

    window.should_fullscreen = args.fullscreen
    
    if args.fullscreen:
        # First show normal to make sure window is created
        window.show()
        # Add a small delay to make sure window manager registers it
        QTimer.singleShot(500, window.showFullScreen)
    else:
        window.show()

    sys.exit(app.exec_())