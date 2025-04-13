"""
Unified UDP communication handler for EV Charging Station Monitor.
Implements bidirectional communication on a single port like the mentor's Node.js code.
Combines functionality from both udp_client.py and udp_helper.py into a single class.

This module provides:
1. Real-time data reception from the EV charging hardware controller
2. Parameter update transmission to the hardware controller
3. Thread-safe data storage and access mechanisms
4. Time window filtering for graph display
5. Waveform generation for three-phase visualization

Flow of operation:
1. Initialize socket on any available port (bind to 0.0.0.0 to listen on all interfaces)
2. Start background thread to continuously receive data packets
3. Parse incoming data into structured format and store in history collections
4. Generate three-phase waveforms based on received parameters
5. Provide methods to fetch latest data and historical trends
6. Allow sending parameter updates in simplified CSV format
"""

import socket
import threading
import time
import numpy as np
from collections import deque

from network_config import (
    DEFAULT_SERVER_IP, DEFAULT_SERVER_PORT, DEFAULT_CLIENT_PORT, DEFAULT_BROADCAST_IP,
    DEFAULT_BUFFER_SIZE, DEFAULT_SOCKET_TIMEOUT, DEFAULT_HISTORY_LENGTH, TABLE_ID_GRID, TABLE_ID_CHARGING, TABLE_ID_EV,
    DEFAULT_TIME_WINDOW
)

class UnifiedUDPHandler:
    """
    Combined UDP handler that uses a single port for both sending and receiving,
    matching the mentor's Node.js server approach.
    
    This class handles:
    - Socket initialization and management
    - Background thread for continuous data reception
    - Thread-safe data storage with history tracking
    - Parameter transmission in CSV format
    - Waveform generation for three-phase visualization
    - Time window filtering for display purposes
    
    Data flow:
    1. Socket receives UDP packets from hardware controller
    2. Packets are parsed into individual parameters
    3. Parameters are stored in latest_data dict and historical collections
    4. Background calculations (like waveforms) are performed
    5. Application accesses data through thread-safe getter methods
    6. Parameter updates are formatted and sent back to hardware
    
    Thread safety is implemented with separate locks for:
    - data_lock: Protects parameter values and histories
    - time_lock: Protects timestamp history
    """
    
    def __init__(self, server_ip=DEFAULT_SERVER_IP, server_port=DEFAULT_SERVER_PORT, 
                local_port=DEFAULT_CLIENT_PORT, buffer_size=DEFAULT_BUFFER_SIZE, 
                history_length=DEFAULT_HISTORY_LENGTH):        
        """
        Initialize the unified UDP handler.
        
        Performs the following setup:
        1. Stores configuration parameters
        2. Initializes data storage collections
        3. Sets up thread synchronization locks
        4. Creates UDP socket for bidirectional communication
        5. Starts background receive thread
        
        Parameters:
        -----------
        server_ip : str
            The server IP address to communicate with. Default is '127.0.0.1' for localhost.
        server_port : int
            The server port to communicate with. Default is 8888 to match mentor's code.
        local_port : int
            Local port to bind for receiving data. Set to 0 for system-assigned port.
        buffer_size : int
            Size of the receive buffer in bytes.
        history_length : int
            Number of historical data points to store for each parameter.
        """
        # ------ Network Configuration ------
        # Server connection details - where to send data to
        self.server_ip = server_ip        # IP address of hardware controller
        self.server_port = server_port    # Port number of hardware controller (fixed at 8888)
        self.local_port = local_port      # Local port for binding (0 = system-assigned)
        self.buffer_size = buffer_size    # Maximum size of UDP packet to receive (bytes)
        self.history_length = history_length  # How many historical values to keep
        
        # ------ Socket and Thread Control ------
        self.socket = None                # UDP socket for bidirectional communication
        self.is_running = False           # Flag to control background thread
        self.receive_thread = None        # Background thread for receiving data
        
        self.data_logger = None  # Will be set by main.py
        
        # ------ Parameter Table Mapping ------
        # Maps settings screen types to table IDs expected by hardware
        self.table_ids = {
            "grid_settings": TABLE_ID_GRID,         # Table ID 1: Grid parameters
            "charging_setting": TABLE_ID_CHARGING,  # Table ID 2: Charging parameters
            "ev_charging_setting": TABLE_ID_EV      # Table ID 3: EV charging parameters
        }
        
        # ------ Real-Time Data Storage ------
        # Latest values for all parameters - updated continuously
        self.latest_data = {
            # Grid parameters
            'Grid_Voltage': 0.0,          # Grid voltage (V)
            'Grid_Current': 0.0,          # Grid current (A)
            'DCLink_Voltage': 0.0,        # DC link voltage (V)
            
            # EV parameters
            'ElectricVehicle_Voltage': 0.0,  # EV voltage (V)
            'ElectricVehicle_Current': 0.0,  # EV current (A)
            'ElectricVehicle_Power': 0.0,    # EV power (W)
            
            # PV parameters
            'PhotoVoltaic_Voltage': 0.0,  # PV voltage (V) 
            'PhotoVoltaic_Current': 0.0,  # PV current (A)
            'PhotoVoltaic_Power': 0.0,    # PV power (W)
            
            # Battery parameters
            'Battery_Power': 0.0,         # Battery power (W)
            'Battery_SoC': 0.0,           # Battery state of charge (%)
            
            # Grid quality parameters
            'Grid_Power': 0.0,            # Grid power (W)
            'Grid_Reactive_Power': 0.0,   # Grid reactive power (VAR)
            'Power_Factor': 0.0,          # Power factor (0.0-1.0)
            'Frequency': 50.0,            # Grid frequency (Hz)
            'THD': 0.0,                   # Total harmonic distortion (%)
            
            # Component status indicators
            'S1_Status': 0,               # PV panel status (0-3)
            'S2_Status': 0,               # EV status (0-3) 
            'S3_Status': 0,               # Grid status (0-3)
            'S4_Status': 0,               # Battery status (0-3)
            
            # EV charging status
            'EV_SoC': 0.0                 # EV state of charge (%)
        }
        
        # ------ Historical Data Storage ------
        # Timestamp history - synced with all parameter histories
        self.time_history = deque(maxlen=history_length)  # Timestamps for all data points
        
        # Per-parameter value histories - for trend visualization
        self.data_history = {
            # Initialize empty history deques for each parameter
            # Each will store up to history_length values
            'Grid_Voltage': deque(maxlen=history_length),
            'Grid_Current': deque(maxlen=history_length),
            'DCLink_Voltage': deque(maxlen=history_length),
            'ElectricVehicle_Voltage': deque(maxlen=history_length),
            'PhotoVoltaic_Voltage': deque(maxlen=history_length),
            'ElectricVehicle_Current': deque(maxlen=history_length),
            'PhotoVoltaic_Current': deque(maxlen=history_length),
            'PhotoVoltaic_Power': deque(maxlen=history_length),
            'ElectricVehicle_Power': deque(maxlen=history_length),
            'Battery_Power': deque(maxlen=history_length),
            'Grid_Power': deque(maxlen=history_length),
            'Grid_Reactive_Power': deque(maxlen=history_length),
            'Power_Factor': deque(maxlen=history_length),
            'Frequency': deque(maxlen=history_length),
            'THD': deque(maxlen=history_length),
            'Battery_SoC': deque(maxlen=history_length),
            'EV_SoC': deque(maxlen=history_length)
        }
        
        # ------ Waveform Data Storage ------
        # Three-phase waveform data for voltage and current visualization
        self.waveform_data = {
            'Grid_Voltage': {  # Three phases of voltage
                'phaseA': deque(maxlen=history_length),
                'phaseB': deque(maxlen=history_length),
                'phaseC': deque(maxlen=history_length),
            },
            'Grid_Current': {  # Three phases of current
                'phaseA': deque(maxlen=history_length),
                'phaseB': deque(maxlen=history_length),
                'phaseC': deque(maxlen=history_length),
            }
        }
        
        # ------ Waveform Generation Parameters ------
        self.frequency = 50.0             # Base frequency for waveform generation (Hz)
        self.phase_shift = (2 * np.pi) / 3  # 120° phase shift in radians
        self.last_waveform_time = 0       # Last timestamp when waveform was generated
        
        # ------ Thread Synchronization ------
        self.data_lock = threading.Lock()  # Protects data collections from race conditions
        self.time_lock = threading.Lock()  # Protects time_history from race conditions
        
        # ------ Initialize Communication ------
        # Create UDP socket and start receive thread
        self._initialize_socket()        # Set up the UDP socket
        self._start_receive_thread()     # Start background processing
    
    def set_data_logger(self, logger):
        """
        Set a data logger instance to receive raw packets.
        
        Parameters:
        -----------
        logger : DataLogger
            DataLogger instance that will receive raw packets
        """
        self.data_logger = logger

    def _initialize_socket(self):
        """
        Initialize the UDP socket for bidirectional communication.
        Handles potential errors during socket creation.
        
        This method:
        1. Creates a UDP socket
        2. Configures socket options (timeout, address reuse)
        3. Binds to specified interface and port
        4. Reports successful initialization
        
        Socket is bound to 0.0.0.0 (all interfaces) to receive packets
        from any network interface.
        
        Returns:
        --------
        bool
            True if initialized successfully, False otherwise.
        """
        try:
            # Create a standard UDP (SOCK_DGRAM) socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Enable address reuse to avoid "Address already in use" errors
            # when restarting application
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Set timeout to prevent blocking indefinitely on receive operations
            # This ensures the receive loop can check shutdown flag periodically
            self.socket.settimeout(DEFAULT_SOCKET_TIMEOUT)  # 500ms timeout
            
            # Bind to all interfaces (0.0.0.0) and the specified port
            # If local_port is 0, the OS will assign an available port
            self.socket.bind((DEFAULT_BROADCAST_IP, self.local_port))
            
            # Get the actual port assigned by the system (important when using port 0)
            _, self.local_port = self.socket.getsockname()
            
            print(f"UDP socket initialized on port {self.local_port} for bidirectional communication")
            print(f"Configured to communicate with server at {self.server_ip}:{self.server_port}")
            
            # This can be removed if real hardware doesn't require it
            # if self.socket:
            #     try:
            #         # Just send table ID 1 to request grid settings
            #         init_message = "1"
            #         self.socket.sendto(init_message.encode('utf-8'), (self.server_ip, self.server_port))
            #         print("Sent initial parameter request to establish connection")
            #     except:
            #         pass  # Fail silently if this doesn't work
            #     # No hello packet needed per mentor's guidance
            
            return True
            
        except Exception as e:
            # Log error and handle socket creation failure
            print(f"Failed to initialize UDP socket: {e}")
            self.socket = None
            return False
    
    def _start_receive_thread(self):
        """
        Start a background thread to receive UDP responses.
        
        The thread will:
        1. Run the _receive_loop method in the background
        2. Process incoming packets as they arrive
        3. Continue until is_running is set to False
        
        The thread is created as daemon=True so it will automatically
        terminate when the main program exits.
        
        Returns:
        --------
        bool
            True if thread started successfully, False otherwise.
        """
        # Ensure socket is initialized before starting thread
        if self.socket is None:
            print("Cannot start receive thread: Socket not initialized")
            return False
        
        # Set the running flag to indicate thread should continue
        self.is_running = True
        
        # Create and start the receive thread
        # daemon=True ensures the thread will exit when the main program exits
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        
        return True
    
    def _receive_loop(self):
        """
        Background thread method to continuously receive and process UDP packets.
        
        Main processing steps:
        1. Wait for incoming UDP packets
        2. Parse data when packets arrive
        3. Process packets as real-time data
        4. Handle errors and timeouts gracefully
        5. Continue until is_running flag is set to False
        
        This method runs in its own thread to avoid blocking the UI.
        """
        print("Started receive thread - listening for messages")
        start_time = time.time()  # Reference time for relative timestamps
        packet_count = 0          # Counter for received packets (for logging)
        
        # Main receive loop - continues until shutdown is signaled
        while self.is_running and self.socket:
            try:
                # Wait for incoming packet (blocks until timeout or packet arrives)
                # recvfrom returns both data and sender's address
                data, addr = self.socket.recvfrom(self.buffer_size)
                
                if data:
                    # Convert received bytes to string using UTF-8 encoding
                    # strip() removes any whitespace/newlines at start/end
                    data_str = data.decode('utf-8').strip()

                    # Log raw packet if logger is available
                    if self.data_logger and hasattr(self.data_logger, 'log_raw_packet'):
                        self.data_logger.log_raw_packet(data_str, addr)
                    
                    # Skip parameter messages (legacy format no longer needed)
                    if data_str.startswith("PARAM"):
                        print(f"Received parameter message (skipping): {data_str[:40]}...")
                        continue  # Skip to next iteration
                        
                    # Increment packet counter and log every 100 packets
                    packet_count += 1
                    if packet_count % 100 == 0:
                        print(f"UDP packets received: {packet_count}")
                    
                    # Calculate time relative to start for consistent timestamps
                    # This creates a time axis starting at 0 when the program begins
                    current_time = time.time() - start_time
                    
                    # Process this packet as real-time data
                    self._process_data_packet(data_str, current_time)
                    
            except socket.timeout:
                # Socket timeout - this is normal and expected
                # Timeouts allow checking the is_running flag periodically
                pass
                    
            except Exception as e:
                # Only log errors if we're supposed to be running
                # Prevents error spam during shutdown
                if self.is_running:
                    print(f"Error in receive loop: {e}")
                    # Small delay to prevent tight loop consuming CPU if there's
                    # a persistent error condition
                    time.sleep(0.1)
    
    def _process_data_packet(self, data_str, timestamp):
        """
        Process a data packet from the server.
        Parses CSV data into individual parameters and stores in history.
        
        Processing steps:
        1. Split CSV string into individual values
        2. Validate number of fields
        3. Parse values into appropriate types
        4. Store values in latest_data and history collections
        5. Generate three-phase waveforms based on values
        
        Parameters:
        -----------
        data_str : str
            The data packet as a CSV string from the hardware
            Format: Vd,Id,Vdc,Vev,Vpv,Iev,Ipv,Ppv,Pev,Pbattery,Pg,Qg,PF,Fg,THD,s1,s2,s3,s4,SoC_battery,SoC_EV
        timestamp : float
            The timestamp when the data was received (seconds since start)
        """
        try:
            # Split the CSV string into individual value strings
            values = data_str.split(',')
            
            # Ensure we have the expected number of values
            # According to hardware protocol, we expect 21 values:
            # - 15 measurement values (voltages, currents, powers, etc.)
            # - 4 status indicators (s1-s4)
            # - 2 state of charge values (battery, EV)
            expected_values = 21
            if len(values) != expected_values:
                print(f"Warning: Expected {expected_values} values, got {len(values)}")
                return  # Return without processing invalid data
            
            # Now we know this is valid data - ADD TIMESTAMP TO HISTORY
            # Using lock to prevent race conditions with time_history access
            with self.time_lock:
                self.time_history.append(timestamp)
            
            # Parse the values into proper numeric types
            try:
                # Grid parameters
                vd = float(values[0])         # Grid Voltage (V)
                id_val = float(values[1])     # Grid Current (A)
                vdc = float(values[2])        # DC Link Voltage (V)
                
                # EV parameters
                vev = float(values[3])        # EV Voltage (V)
                iev = float(values[5])        # EV Current (A)
                pev = float(values[8])        # EV Power (W)
                
                # PV parameters
                vpv = float(values[4])        # PV Voltage (V)
                ipv = float(values[6])        # PV Current (A)
                ppv = float(values[7])        # PV Power (W)
                
                # New parameters:
                pbattery = float(values[9])   # Battery Power (W)
                pgrid = float(values[10])     # Grid Power (W)
                qgrid = float(values[11])     # Grid Reactive Power (VAR)
                power_factor = float(values[12])  # Power Factor (0-1)
                frequency = float(values[13]) # Grid Frequency (Hz)
                thd = float(values[14])       # Total Harmonic Distortion (%)
                
                # Status indicators (0=Off, 1=onn, 2=right, 3=left)
                s1 = int(float(values[15]))   # PV panel status
                s2 = int(float(values[16]))   # EV status
                s3 = int(float(values[17]))   # Grid status
                s4 = int(float(values[18]))   # Battery status
                
                # State of charge values
                soc_battery = float(values[19])  # Battery SoC percentage (0-100%)
                soc_ev = float(values[20])       # EV SoC percentage (0-100%)
                
                # Ensure status values are within valid range (0-3)
                # 0: Off, 1: Standby, 2: Active, 3: Fault
                s1 = max(0, min(s1, 3))  # Clamp to range 0-3
                s2 = max(0, min(s2, 3))
                s3 = max(0, min(s3, 3))
                s4 = max(0, min(s4, 3))
                
            except ValueError as e:
                # Handle numeric conversion errors
                print(f"Error parsing data values: {e}")
                print(f"Raw data: {data_str}")
                return  # Skip processing this packet
                
            # Update latest data with all parameters - with thread safety
            # Using lock to prevent race conditions with data access from UI thread
            with self.data_lock:
                # Store values in the latest_data dictionary
                self.latest_data['Grid_Voltage'] = vd
                self.latest_data['Grid_Current'] = id_val
                self.latest_data['DCLink_Voltage'] = vdc
                self.latest_data['ElectricVehicle_Voltage'] = vev
                self.latest_data['PhotoVoltaic_Voltage'] = vpv
                self.latest_data['ElectricVehicle_Current'] = iev
                self.latest_data['PhotoVoltaic_Current'] = ipv
                self.latest_data['PhotoVoltaic_Power'] = ppv
                self.latest_data['ElectricVehicle_Power'] = pev
                self.latest_data['Battery_Power'] = pbattery
                self.latest_data['Grid_Power'] = pgrid
                self.latest_data['Grid_Reactive_Power'] = qgrid
                self.latest_data['Power_Factor'] = power_factor
                self.latest_data['Frequency'] = frequency
                self.latest_data['THD'] = thd
                self.latest_data['S1_Status'] = s1
                self.latest_data['S2_Status'] = s2
                self.latest_data['S3_Status'] = s3
                self.latest_data['S4_Status'] = s4
                self.latest_data['Battery_SoC'] = soc_battery
                self.latest_data['EV_SoC'] = soc_ev
                
                # Also update historical data collections for trending
                self.data_history['Grid_Voltage'].append(vd)
                self.data_history['Grid_Current'].append(id_val)
                self.data_history['DCLink_Voltage'].append(vdc)
                self.data_history['ElectricVehicle_Voltage'].append(vev)
                self.data_history['PhotoVoltaic_Voltage'].append(vpv)
                self.data_history['ElectricVehicle_Current'].append(iev)
                self.data_history['PhotoVoltaic_Current'].append(ipv)
                self.data_history['PhotoVoltaic_Power'].append(ppv)
                self.data_history['ElectricVehicle_Power'].append(pev)
                self.data_history['Battery_Power'].append(pbattery)
                self.data_history['Grid_Power'].append(pgrid)
                self.data_history['Grid_Reactive_Power'].append(qgrid)
                self.data_history['Power_Factor'].append(power_factor)
                self.data_history['Frequency'].append(frequency)
                self.data_history['THD'].append(thd)
                self.data_history['Battery_SoC'].append(soc_battery)
                self.data_history['EV_SoC'].append(soc_ev)
            
            # Generate three-phase waveforms for visualization based on the latest data
            self._generate_waveforms(vd, id_val, timestamp)
            
        except Exception as e:
            # Catch-all for any other errors in processing
            print(f"Error processing data packet: {e}")
    
    def send_parameter_update(self, table_type, params):
        """
        Send parameter updates over UDP using the simplified CSV format.
        
        Process:
        1. Determine the correct table ID based on table_type
        2. Format parameter values in the correct order
        3. Create a CSV string with table ID followed by values
        4. Send the CSV string to the hardware controller via UDP
        
        CSV Format:
        - For grid_settings: 1,vg_rms,ig_rms,frequency,thd,power_factor
        - For charging_setting: 2,pv_power,ev_power,battery_power
        - For ev_charging_setting: 3,ev_voltage,ev_soc,demand_response,v2g
        
        Parameters:
        -----------
        table_type : str
            Type of table being updated (e.g., 'charging_setting')
        params : dict
            Dictionary of parameter names and their new values
                
        Returns:
        --------
        bool
            True if sending was successful, False otherwise
        """
        # Check if socket is available
        if self.socket is None:
            print("Cannot send: Socket not initialized")
            return False
            
        try:
            # Determine table ID based on the table type
            table_id = 0
            if table_type == "grid_settings":
                table_id = 1
            elif table_type == "charging_setting":
                table_id = 2
            elif table_type == "ev_charging_setting":
                table_id = 3
                
            # Return if table type is not recognized
            if table_id == 0:
                print(f"Unknown table type: {table_type}")
                return False
            
            # Start building CSV string with the table ID
            csv_parts = [str(int(table_id))]
            
            # Build CSV parts based on table type
            # Important: order must match hardware controller's expectations
            
            # Table 1: Grid Settings
            if table_id == 1:  # grid_settings
                # Order: vg_rms, ig_rms, frequency, thd, power_factor
                # Default values are provided as fallbacks if parameters are missing
                csv_parts.append(str(params.get("Vg_rms", "0")))      # Grid voltage (V)
                csv_parts.append(str(params.get("Ig_rms", "0")))      # Grid current (A)
                csv_parts.append(str(params.get("Frequency", "50")))  # Grid frequency (Hz)
                csv_parts.append(str(params.get("THD", "0")))         # THD (%)
                csv_parts.append(str(params.get("Power factor", "0.95")))  # Power factor
                
            # Table 2: Charging Settings
            elif table_id == 2:  # charging_setting
                # Order: pv_power, ev_power, battery_power
                csv_parts.append(str(params.get("PV power", "0")))      # PV power (W)
                csv_parts.append(str(params.get("EV power", "0")))      # EV power (W) 
                csv_parts.append(str(params.get("Battery power", "0"))) # Battery power (W)
                
            # Table 3: EV Charging Settings
            elif table_id == 3:  # ev_charging_setting
                # Order: ev_voltage, ev_soc, demand_response, v2g
                csv_parts.append(str(params.get("EV voltage", "0")))  # EV voltage (V)
                csv_parts.append(str(params.get("EV SoC", "0")))      # EV SoC (%)
                
                # Convert boolean values to 0/1 integers for transmission
                # Hardware expects 1=true, 0=false
                dr_val = "1" if params.get("Demand Response", False) else "0"  # Demand response mode
                v2g_val = "1" if params.get("V2G", False) else "0"  # Vehicle-to-grid mode
                csv_parts.append(dr_val)
                csv_parts.append(v2g_val)
            
            # Join parts with commas to create the final CSV string
            csv_data = ",".join(csv_parts)
            
            # Send the CSV data to the hardware controller
            bytes_sent = self.socket.sendto(csv_data.encode('utf-8'), 
                                        (self.server_ip, self.server_port))
            
            # Log the sent data
            print(f"Sent {bytes_sent} bytes to {self.server_ip}:{self.server_port}: {csv_data}")
            print(f"Sent UDP update for {table_type}: {params}")
            return True
            
        except Exception as e:
            print(f"Error sending parameter update: {e}")
            return False
    
    def get_latest_data(self):
        """
        Get the most recent data point for all parameters.
        Thread-safe method to access the current state of all parameters.
        
        Returns:
        --------
        dict
            Dictionary containing the latest value for each parameter.
            Keys are parameter names, values are the most recent measurements.
        """
        # Use lock to ensure thread safety when accessing data
        with self.data_lock:
            # Return a copy to prevent external modification of internal state
            return self.latest_data.copy()
    
    def filter_by_time_window(self, time_data, *data_series, time_window=DEFAULT_TIME_WINDOW):
        """
        Filter data to only include points within the specified time window from the most recent point.
        Enhanced with race condition protection and defensive programming.
        
        How it works:
        1. Makes safe copies of all input arrays
        2. Finds the latest timestamp in the data
        3. Calculates the cutoff time (latest - window)
        4. Filters all arrays to only include points after cutoff
        5. Returns filtered arrays for visualization
        
        Parameters:
        -----------
        time_data : np.array
            Array of time values
        *data_series : tuple of np.array
            Data series to filter based on time_window
        time_window : float
            Time window in seconds to include (default: 1.5)
        
        Returns:
        --------
        tuple
            Filtered time_data and data_series
        """
        # Handle empty arrays gracefully
        if len(time_data) == 0:
            return (time_data,) + data_series
        
        try:
            # Create safe copies to avoid race conditions
            # This is critical because data might be modified by receive thread
            # while we're processing it
            time_copy = np.array(time_data, copy=True)
            data_copies = [np.array(series, copy=True) for series in data_series]
            
            # Get the most recent time point - the right edge of our window
            latest_time = time_copy[-1] if len(time_copy) > 0 else 0
            
            # Calculate the cutoff time - the left edge of our window
            cutoff_time = latest_time - time_window
            
            # Find indices where time is >= cutoff_time
            indices = np.where(time_copy >= cutoff_time)[0]
            
            # Defensive check to ensure indices are valid for all arrays
            # This prevents index out of bounds errors if arrays have different lengths
            for i, arr in enumerate(data_copies):
                if len(indices) > 0 and indices[-1] >= len(arr):
                    print(f"Index range mismatch: max index {indices[-1]} exceeds array {i} length {len(arr)}")
                    # Return full arrays as fallback
                    return (time_data,) + data_series
            
            # Handle edge case: no data in the window
            if len(indices) == 0:
                # No data in the time window, return the latest point only
                if len(time_copy) > 0:
                    return (np.array([time_copy[-1]]),) + tuple(np.array([series[-1]]) for series in data_copies)
                else:
                    return (time_copy,) + tuple(data_copies)
            
            # Filter the time data and all data series
            filtered_time = time_copy[indices]
            filtered_series = tuple(series[indices] for series in data_copies)
            
            # Round time values to 3 decimal places to reduce clutter
            filtered_time = np.round(filtered_time, 3)
            
            return (filtered_time,) + filtered_series
            
        except Exception as e:
            print(f"Error in filter_by_time_window: {e}")
            # Return the original data if filtering fails - graceful fallback
            return (time_data,) + data_series

    def get_waveform_data(self, waveform_type, n_points=None, time_window=DEFAULT_TIME_WINDOW):
        """
        Get waveform data for voltage or current for three-phase visualization.
        
        This method retrieves historical waveform data with thread-safe access.
        It's used to visualize three-phase AC waveforms (voltage or current)
        on oscilloscope-like displays in the UI.
        
        Process:
        1. Retrieve time history and waveform data with thread safety locks
        2. Apply adaptive data selection based on available data
        3. Filter data based on either time window or point count
        4. Return synchronized time and waveform arrays for all three phases
        
        Parameters:
        -----------
        waveform_type : str
            The type of waveform to get ('Grid_Voltage' or 'Grid_Current').
        n_points : int or None
            Number of data points to return. If None, returns all available history.
            Only applied if time_window is None.
        time_window : float or None
            Time window in seconds to include (most recent data). 
            If None, returns all available history or applies n_points filter.
            
        Returns:
        --------
        tuple
            (time_data, phase_a, phase_b, phase_c)
            - time_data: numpy array of timestamps (seconds)
            - phase_a: numpy array of Phase A values
            - phase_b: numpy array of Phase B values
            - phase_c: numpy array of Phase C values
            
            All arrays have the same length and are synchronized.
            Empty arrays are returned if no data is available.
        """
        # Validate input parameter to prevent KeyError
        if waveform_type not in self.waveform_data:
            # Return empty arrays if waveform type is not recognized
            return np.array([]), np.array([]), np.array([]), np.array([])
        
        # Get all history first with thread safety
        # Use locks to prevent race conditions with the data collection thread
        with self.time_lock:
            # Convert deque to numpy array for easier manipulation
            time_data = np.array(list(self.time_history))
        
        # Separate lock for waveform data to minimize lock contention
        with self.data_lock:
            # Get all three phases of waveform data
            phase_a = np.array(list(self.waveform_data[waveform_type]['phaseA']))
            phase_b = np.array(list(self.waveform_data[waveform_type]['phaseB']))
            phase_c = np.array(list(self.waveform_data[waveform_type]['phaseC']))
        
        # Adaptive data handling: if we have any data but not enough for the requested window,
        # return all available data rather than an empty set
        if len(time_data) > 0:
            # Check if we have enough data to cover the time window
            # We need at least 2 points and sufficient time range
            if time_window is not None and (len(time_data) < 2 or 
                                        (time_data[-1] - time_data[0]) < time_window):
                print(f"DEBUG: Not enough data for {time_window}s window, using all {len(time_data)} points")
                # Return all available data as fallback
                return time_data, phase_a, phase_b, phase_c
        else:
            # No data available, return empty arrays
            return np.array([]), np.array([]), np.array([]), np.array([])
        
        # Apply time window filter if specified
        if time_window is not None:
            # Use helper method to filter data to specified time window
            time_data, phase_a, phase_b, phase_c = self.filter_by_time_window(
                time_data, phase_a, phase_b, phase_c, time_window=time_window
            )
        # Otherwise apply n_points filter if specified
        elif n_points is not None:
            # Get only the most recent n_points
            n = min(n_points, len(time_data))  # Safety check
            # Take slices from the end of each array
            time_data = time_data[-n:]
            phase_a = phase_a[-n:]
            phase_b = phase_b[-n:]
            phase_c = phase_c[-n:]
        
        # Return time data and all three phase values as synchronized arrays
        return time_data, phase_a, phase_b, phase_c

    def get_power_data(self, n_points=None, time_window=DEFAULT_TIME_WINDOW):
        """
        Get power data for grid, PV, EV, and battery for power flow visualization.
        
        This method retrieves historical power values to visualize energy flow
        between grid, PV panels, EV, and battery storage in the system.
        
        Power convention:
        - Positive grid power: Power flowing from grid to system (consumption)
        - Negative grid power: Power flowing from system to grid (export)
        - Positive PV power: Power generated from PV panels
        - Positive EV power: Power flowing to EV (charging)
        - Negative EV power: Power flowing from EV (V2G mode)
        - Positive battery power: Charging battery
        - Negative battery power: Discharging battery
        
        Process:
        1. Retrieve time and power data with thread safety
        2. Handle edge cases (empty data, insufficient time range)
        3. Apply filtering based on time window or point count
        4. Return synchronized arrays for visualization
        
        Parameters:
        -----------
        n_points : int or None
            Number of data points to return. If None, returns all available history.
            Only applied if time_window is None.
        time_window : float or None
            Time window in seconds to include (most recent data).
            If None, returns all available history or applies n_points filter.
            
        Returns:
        --------
        tuple
            (time_data, grid_power, pv_power, ev_power, battery_power)
            - time_data: numpy array of timestamps (seconds)
            - grid_power: numpy array of grid power values (W)
            - pv_power: numpy array of PV power values (W)
            - ev_power: numpy array of EV power values (W)
            - battery_power: numpy array of battery power values (W)
            
            All arrays have the same length and are synchronized.
            Arrays with single zero value are returned if no data is available.
        """
        # Get all history first with thread safety
        with self.time_lock:
            time_data = np.array(list(self.time_history))
        
        # Acquire data lock to safely read power histories
        with self.data_lock:
            # Get all power values
            grid_power = np.array(list(self.data_history['Grid_Power']))
            pv_power = np.array(list(self.data_history['PhotoVoltaic_Power']))
            ev_power = np.array(list(self.data_history['ElectricVehicle_Power']))
            battery_power = np.array(list(self.data_history['Battery_Power']))
        
        # Adaptive handling: if we have data but not enough for the time window,
        # return all available data rather than filtering potentially too much
        if len(time_data) > 0:
            if time_window is not None and (len(time_data) < 2 or 
                                        (time_data[-1] - time_data[0]) < time_window):
                print(f"DEBUG: Not enough data for {time_window}s window, using all {len(time_data)} points")
                # Return all available data as fallback
                return time_data, grid_power, pv_power, ev_power, battery_power
        else:
            # No data available - return arrays with single zero value
            # This allows plots to initialize with a zero baseline
            return np.array([0]), np.array([0]), np.array([0]), np.array([0]), np.array([0])
        
        # Apply time window filter if specified
        if time_window is not None:
            # Use helper method to filter all power arrays to the specified window
            time_data, grid_power, pv_power, ev_power, battery_power = self.filter_by_time_window(
                time_data, grid_power, pv_power, ev_power, battery_power, time_window=time_window
            )
        # Otherwise apply n_points filter if specified
        elif n_points is not None:
            # Get only the most recent n_points (e.g., for a fixed-size display)
            n = min(n_points, len(time_data))  # Safety check for out of bounds
            # Take slices from the end of each array
            time_data = time_data[-n:]
            grid_power = grid_power[-n:]
            pv_power = pv_power[-n:]
            ev_power = ev_power[-n:]
            battery_power = battery_power[-n:]
        
        # Return synchronized time and power arrays
        return time_data, grid_power, pv_power, ev_power, battery_power

    def get_parameter_history(self, parameter, n_points=None, time_window=DEFAULT_TIME_WINDOW):
        """
        Get historical data for a specific parameter for trend visualization.
        
        This method provides a general-purpose way to retrieve historical values
        for any monitored parameter. It's used for creating trend graphs, analyzing
        parameter behavior over time, and providing data for custom visualizations.
        
        Process:
        1. Validate parameter exists in data history
        2. Retrieve time and parameter data with thread safety
        3. Apply filtering based on time window or point count
        4. Return synchronized time and parameter arrays
        
        Parameters:
        -----------
        parameter : str
            The name of the parameter to get history for (must match a key in data_history).
            Examples: 'Grid_Voltage', 'Frequency', 'Battery_SoC', etc.
        n_points : int or None
            Number of historical data points to return. If None, returns all available history.
            Only applied if time_window is None.
        time_window : float or None
            Time window in seconds to include (most recent data).
            If None, returns all available history or applies n_points filter.
            
        Returns:
        --------
        tuple
            (time_data, param_data)
            - time_data: numpy array of timestamps (seconds)
            - param_data: numpy array of parameter values
            
            Both arrays have the same length and are synchronized.
            Empty arrays are returned if the parameter doesn't exist or no data is available.
        """
        # Validate parameter name to prevent KeyError
        if parameter not in self.data_history:
            # Return empty arrays if parameter is not recognized
            return np.array([]), np.array([])
        
        # Get time history with thread safety
        with self.time_lock:
            time_data = np.array(list(self.time_history))
        
        # Get parameter history with thread safety
        with self.data_lock:
            param_data = np.array(list(self.data_history[parameter]))
        
        # Check for empty data case
        if len(time_data) == 0:
            # No data available, return empty arrays
            return np.array([]), np.array([])
        
        # Apply time window filter if specified
        if time_window is not None:
            # Use helper method to filter data to specified time window
            time_data, param_data = self.filter_by_time_window(
                time_data, param_data, time_window=time_window
            )
        # Otherwise apply n_points filter if specified
        elif n_points is not None:
            # Get only the most recent n_points
            n = min(n_points, len(time_data))  # Safety check
            # Take slices from the end of each array
            time_data = time_data[-n:]
            param_data = param_data[-n:]
        
        # Return synchronized time and parameter data arrays
        return time_data, param_data
    
    def _generate_waveforms(self, voltage_amplitude, current_amplitude, timestamp):
        """
        Generate three-phase waveforms based on the single voltage and current values.
        Creates simulated three-phase waveforms for visualization purposes.
        
        Process:
        1. Get frequency and power factor from latest data
        2. Calculate peak values from RMS values
        3. Generate sine waves with appropriate phase shifts
        4. Apply power factor angle to current waveforms
        5. Store calculated values for visualization
        
        Parameters:
        -----------
        voltage_amplitude : float
            The voltage amplitude value from the hardware (RMS value).
        current_amplitude : float
            The current amplitude value from the hardware (RMS value).
        timestamp : float
            The current time value (seconds since start).
        """
        # Get latest frequency and power factor values with thread safety
        with self.data_lock:
            frequency = self.latest_data.get('Frequency', self.frequency)
            power_factor = self.latest_data.get('Power_Factor', 0.95)
        
        # Convert RMS values to peak values for sine wave generation
        # Peak = RMS * sqrt(2)
        voltage_peak = voltage_amplitude * np.sqrt(2)
        current_peak = current_amplitude * np.sqrt(2)
        
        # Generate time-based angle for the sine waves
        # angle = 2π * f * t
        angle = 2 * np.pi * frequency * timestamp
        
        # Calculate values for the three voltage phases
        # Phase A: sin(angle)
        # Phase B: sin(angle - 120°)
        # Phase C: sin(angle + 120°)
        voltage_a = voltage_peak * np.sin(angle)
        voltage_b = voltage_peak * np.sin(angle - self.phase_shift)
        voltage_c = voltage_peak * np.sin(angle + self.phase_shift)
        
        # Calculate values for the three current phases
        # Apply power factor angle to create phase shift between voltage and current
        actual_pf = max(-1.0, min(1.0, power_factor))  # Clamp to valid range
        power_factor_angle = np.arccos(actual_pf)  # Convert PF to angle
        
        # Generate current waveforms with PF angle offset
        current_a = current_peak * np.sin(angle - power_factor_angle)
        current_b = current_peak * np.sin(angle - self.phase_shift - power_factor_angle)
        current_c = current_peak * np.sin(angle + self.phase_shift - power_factor_angle)
        
        # Store the calculated values with thread safety
        with self.data_lock:
            # Voltage waveforms
            self.waveform_data['Grid_Voltage']['phaseA'].append(voltage_a)
            self.waveform_data['Grid_Voltage']['phaseB'].append(voltage_b)
            self.waveform_data['Grid_Voltage']['phaseC'].append(voltage_c)
            
            # Current waveforms
            self.waveform_data['Grid_Current']['phaseA'].append(current_a)
            self.waveform_data['Grid_Current']['phaseB'].append(current_b)
            self.waveform_data['Grid_Current']['phaseC'].append(current_c)

    def is_connected(self):
        """
        Check if the UDP handler is running and has received data.
        
        Returns:
        --------
        bool
            True if the handler is running and has received data, False otherwise.
        """
        with self.time_lock:
            return self.is_running and len(self.time_history) > 0
            
    def close(self):
        """
        Clean up resources and stop the receive thread.
        
        Shutdown sequence:
        1. Signal threads to stop by setting is_running to False
        2. Allow time for threads to notice the shutdown signal
        3. Wait for receive thread to terminate with timeout
        4. Force close socket to release network resources
        5. Clean up references
        
        This method ensures clean shutdown with no resource leaks.
        """
        print("Stopping UDP handler...")
        
        # First set the running flag to False to signal threads to stop
        self.is_running = False
        
        # Wait a moment to let the threads notice the flag
        # This helps prevent deadlocks and resource conflicts
        time.sleep(0.2)
        
        # Wait for receive thread to terminate with a longer timeout
        if self.receive_thread and self.receive_thread.is_alive():
            print("Waiting for receive thread to terminate...")
            try:
                # Join with timeout to avoid hanging indefinitely
                self.receive_thread.join(timeout=3.0)
            except RuntimeError:
                print("Warning: Error joining receive thread")
                
            # Check if thread actually terminated
            if self.receive_thread.is_alive():
                print("Warning: Receive thread did not terminate cleanly")
        
        # Close the socket after threads have stopped or timed out
        if self.socket:
            try:
                print("Closing UDP socket...")
                self.socket.close()
            except Exception as e:
                print(f"Error closing socket: {e}")
            finally:
                # Always set to None to help garbage collection
                self.socket = None
                
        print("UDP handler stopped")


# Global singleton instance for application-wide use
unified_udp = None


def initialize_unified_udp(server_ip=DEFAULT_SERVER_IP, server_port=DEFAULT_SERVER_PORT, local_port=DEFAULT_CLIENT_PORT):
    """
    Initialize the global unified UDP handler.
    
    This function creates a singleton instance of the UnifiedUDPHandler
    that can be accessed throughout the application.
    
    Process:
    1. Create the handler with provided network parameters
    2. Store it in a global variable for application-wide access
    
    Parameters:
    -----------
    server_ip : str
        The server IP address to communicate with.
    server_port : int
        The server port to communicate with.
    local_port : int
        Local port to bind for receiving data.
        
    Returns:
    --------
    UnifiedUDPHandler
        The initialized UDP handler
    """
    global unified_udp
    # Create new handler instance with provided parameters
    unified_udp = UnifiedUDPHandler(server_ip, server_port, local_port)
    
    # Return the handler for immediate use
    return unified_udp

def get_unified_udp():
    """
    Get the global unified UDP handler instance.
    
    Returns:
    --------
    UnifiedUDPHandler
        The UDP handler, or None if not initialized
    """
    return unified_udp