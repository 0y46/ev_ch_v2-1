"""
Unified UDP communication handler for EV Charging Station Monitor.
Implements bidirectional communication on a single port like the mentor's Node.js code.
Combines functionality from both udp_client.py and udp_helper.py into a single class.
"""

import socket
import threading
import time
import numpy as np
from collections import deque

class UnifiedUDPHandler:
    """
    Combined UDP handler that uses a single port for both sending and receiving,
    matching the mentor's Node.js server approach.
    """
    
    def __init__(self, server_ip="127.0.0.1", server_port=8888, local_port=0, buffer_size=1024, history_length=1000):
        """
        Initialize the unified UDP handler.
        
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
        # Server connection details
        self.server_ip = server_ip
        self.server_port = server_port
        self.local_port = local_port
        self.buffer_size = buffer_size
        self.history_length = history_length
        
        # Socket for bidirectional communication
        self.socket = None
        
        # Control flags and threads
        self.is_running = False
        self.receive_thread = None
        
        # Table IDs for parameter updates (same as in udp_helper.py)
        self.table_ids = {
            "grid_settings": 1,
            "charging_setting": 2,
            "ev_charging_setting": 3
        }
        
        # Last received reference values
        self.reference_values = {
            "Vdc_ref": None,
            "Pev_ref": None,
            "Ppv_ref": None
        }
        
        # Dictionary to store the last response received from each remote address
        self.last_responses = {}
        
        # Data storage - similar to UDPClient
        self.latest_data = {
            'Grid_Voltage': 0.0,
            'Grid_Current': 0.0,
            'DCLink_Voltage': 0.0,
            'ElectricVehicle_Voltage': 0.0,
            'PhotoVoltaic_Voltage': 0.0,
            'ElectricVehicle_Current': 0.0,
            'PhotoVoltaic_Current': 0.0,
            'PhotoVoltaic_Power': 0.0,
            'ElectricVehicle_Power': 0.0,
            'Battery_Power': 0.0,
            'Grid_Power': 0.0,
            'Grid_Reactive_Power': 0.0,
            'Power_Factor': 0.0,
            'Frequency': 50.0,
            'THD': 0.0,
            'S1_Status': 0,
            'S2_Status': 0,
            'S3_Status': 0,
            'S4_Status': 0,
            'Battery_SoC': 0.0,
            'EV_SoC': 0.0
        }
        
        # For time series data
        self.time_history = deque(maxlen=history_length)
        
        # History storage for each parameter (same as in UDPClient)
        self.data_history = {
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
        
        # For waveform data (same as in UDPClient)
        self.waveform_data = {
            'Grid_Voltage': {
                'phaseA': deque(maxlen=history_length),
                'phaseB': deque(maxlen=history_length),
                'phaseC': deque(maxlen=history_length),
            },
            'Grid_Current': {
                'phaseA': deque(maxlen=history_length),
                'phaseB': deque(maxlen=history_length),
                'phaseC': deque(maxlen=history_length),
            }
        }
        
        # Waveform generation parameters (same as in UDPClient)
        self.frequency = 50.0  # Hz (grid frequency)
        self.phase_shift = (2 * np.pi) / 3  # 120 degrees in radians
        self.last_waveform_time = 0
        
        # Thread safety
        self.data_lock = threading.Lock()
        self.time_lock = threading.Lock()
        
        # Parameter update callback
        self.response_callback = None
        
        # Try to initialize the socket
        self._initialize_socket()
        
        # Start the receive thread
        self._start_receive_thread()
    
    def _initialize_socket(self):
        """
        Initialize the UDP socket for bidirectional communication.
        Handles potential errors during socket creation.
        """
        try:
            # Create a UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Set socket options
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.settimeout(0.5)  # 500ms timeout
            
            # Bind the socket to the local port
            self.socket.bind(("0.0.0.0", self.local_port))
            
            # Get the actual port assigned by the system
            _, self.local_port = self.socket.getsockname()
            
            print(f"UDP socket initialized on port {self.local_port} for bidirectional communication")
            print(f"Configured to communicate with server at {self.server_ip}:{self.server_port}")
            
            # Send initial hello packet to server to establish communication
            self._send_hello()
            
            return True
            
        except Exception as e:
            print(f"Failed to initialize UDP socket: {e}")
            self.socket = None
            return False
    
    def _start_receive_thread(self):
        """Start a background thread to receive UDP responses."""
        if self.socket is None:
            print("Cannot start receive thread: Socket not initialized")
            return False
        
        # Set the running flag and start the receive thread
        self.is_running = True
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        
        return True
    
    def _send_hello(self):
        """Send a hello packet to the server to establish communication."""
        try:
            if self.socket:
                hello_message = "HELLO"
                self.socket.sendto(hello_message.encode('utf-8'), (self.server_ip, self.server_port))
                print(f"Sent hello packet to server at {self.server_ip}:{self.server_port}")
        except Exception as e:
            print(f"Failed to send hello packet: {e}")
    
    def _receive_loop(self):
        """
        Background thread method to continuously receive and process UDP packets.
        Handles both data packets and parameter responses.
        """
        print("Started receive thread - listening for messages")
        start_time = time.time()
        packet_count = 0
        last_hello_time = time.time()
        hello_interval = 10.0  # Send hello every 10 seconds if no data
        
        while self.is_running and self.socket:
            try:
                # Attempt to receive data
                data, addr = self.socket.recvfrom(self.buffer_size)
                
                if data:
                    # Process the received data
                    data_str = data.decode('utf-8').strip()
                    
                    # Check if this is a parameter update message (starts with "PARAM")
                    if data_str.startswith("PARAM"):
                        print(f"Received parameter message (skipping): {data_str[:40]}...")
                        continue  # Skip further processing
                        
                    # Count commas to estimate number of values
                    comma_count = data_str.count(',')
                    
                    # Check if it looks like a reference value response (2-3 values only)
                    if 0 <= comma_count <= 2:
                        # This looks like a reference value response
                        self._process_reference_response(data_str, addr)
                    else:
                        # This looks like a regular data packet
                        packet_count += 1
                        if packet_count % 100 == 0:
                            print(f"UDP packets received: {packet_count}")
                        
                        # Process the data packet with the current time
                        current_time = time.time() - start_time
                        self._process_data_packet(data_str, current_time)
                
            except socket.timeout:
                # This is expected if no data is received within the timeout period
                # Periodically send a hello packet to ensure server knows our address/port
                now = time.time()
                if now - last_hello_time > hello_interval:
                    self._send_hello()
                    last_hello_time = now
                    
            except Exception as e:
                if self.is_running:  # Only log errors if we're supposed to be running
                    print(f"Error in receive loop: {e}")
                    time.sleep(0.1)  # Prevent tight loop if there's a persistent error
    
    def _process_reference_response(self, data_str, addr):
        """
        Process a reference value response from the server.
        
        Parameters:
        -----------
        data_str : str
            The reference value response string (e.g., "400.0,-3000.0,2500.0")
        addr : tuple
            The sender's address (ip, port)
        """
        try:
            # Split the response string into values
            values = data_str.split(',')
            
            # Try to parse the values as floats
            parsed_values = []
            for val in values:
                try:
                    parsed_values.append(float(val))
                except ValueError:
                    # Skip non-numeric values
                    print(f"Skipping non-numeric value: {val}")
                    continue
                    
            # Store the response by address
            self.last_responses[addr] = {
                'time': time.time(),
                'data': data_str
            }
            
            # Update reference values (thread-safe)
            with self.data_lock:
                if len(parsed_values) >= 1:
                    self.reference_values["Vdc_ref"] = parsed_values[0]
                if len(parsed_values) >= 2:
                    self.reference_values["Pev_ref"] = parsed_values[1]
                if len(parsed_values) >= 3:
                    self.reference_values["Ppv_ref"] = parsed_values[2]
            
            print(f"Received reference values: {self.reference_values}")
            
            # Call the response callback if registered
            if self.response_callback:
                self.response_callback(parsed_values, addr)
                
        except Exception as e:
            print(f"Error parsing reference values: {e}")
    
    def _process_data_packet(self, data_str, timestamp):
        """
        Process a data packet from the server.
        Almost identical to the process_data method in UDPClient.
        
        Parameters:
        -----------
        data_str : str
            The data packet as a CSV string
        timestamp : float
            The timestamp when the data was received
        """
        try:
            # Split the CSV string into values
            values = data_str.split(',')
            
            # Ensure we have the expected number of values
            expected_values = 21
            if len(values) != expected_values:
                print(f"Warning: Expected {expected_values} values, got {len(values)}")
                return  # Return without adding timestamp
            
            # Now we know this is valid data - ADD TIMESTAMP TO HISTORY (with thread safety)
            with self.time_lock:
                self.time_history.append(timestamp)
            
            # Parse the values into floats
            try:
                # Same parsing as in UDPClient
                vd = float(values[0])         # Grid Voltage
                id_val = float(values[1])     # Grid Current
                vdc = float(values[2])        # DC Link Voltage
                vev = float(values[3])        # EV Voltage
                vpv = float(values[4])        # PV Voltage
                iev = float(values[5])        # EV Current
                ipv = float(values[6])        # PV Current
                ppv = float(values[7])        # PV Power
                pev = float(values[8])        # EV Power
                
                # New parameters:
                pbattery = float(values[9])   # Battery Power
                pgrid = float(values[10])     # Grid Power
                qgrid = float(values[11])     # Grid Reactive Power
                power_factor = float(values[12])  # Power Factor
                frequency = float(values[13]) # Grid Frequency
                thd = float(values[14])       # Total Harmonic Distortion
                
                # Status indicators
                s1 = int(float(values[15]))   # PV panel status
                s2 = int(float(values[16]))   # EV status
                s3 = int(float(values[17]))   # Grid status
                s4 = int(float(values[18]))   # Battery status
                
                # State of charge values
                soc_battery = float(values[19])  # Battery SoC percentage
                soc_ev = float(values[20])       # EV SoC percentage
                
                # Ensure status values are within valid range (0-3)
                s1 = max(0, min(s1, 3))
                s2 = max(0, min(s2, 3))
                s3 = max(0, min(s3, 3))
                s4 = max(0, min(s4, 3))
                
            except ValueError as e:
                print(f"Error parsing data values: {e}")
                print(f"Raw data: {data_str}")
                return
                
            # Update latest data with all parameters - with thread safety
            with self.data_lock:
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
                
                # Update data history
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
            
            # Generate three-phase waveforms
            self._generate_waveforms(vd, id_val, timestamp)
            
        except Exception as e:
            print(f"Error processing data packet: {e}")
    
    def send_parameter_update(self, table_type, params):
        """
        Send parameter updates over UDP using the CSV format.
        
        Formats the message as:
        PARAM,table_id,param1,value1,param2,value2,...
        
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
        if self.socket is None:
            print("Cannot send: Socket not initialized")
            return False
            
        try:
            # Get table ID 
            table_id = self.table_ids.get(table_type, 0)
            if table_id == 0:
                print(f"Unknown table type: {table_type}")
                return False
            
            # Start building the CSV string with command and table ID
            csv_parts = ["PARAM", str(table_id)]
            
            # Add each parameter and value
            for param_name, value in params.items():
                # Convert parameter name to lowercase with underscores to match expected format
                param_code = param_name.lower().replace(" ", "_")
                # Handle boolean values (convert True/False to 1/0)
                if isinstance(value, bool):
                    value_str = "1" if value else "0"
                else:
                    value_str = str(value)
                
                csv_parts.append(param_code)
                csv_parts.append(value_str)
            
            # Join with commas to create the final CSV string
            csv_data = ",".join(csv_parts)
            
            # Send the CSV data
            bytes_sent = self.socket.sendto(csv_data.encode('utf-8'), (self.server_ip, self.server_port))
            
            print(f"Sent {bytes_sent} bytes to {self.server_ip}:{self.server_port}: {csv_data}")
            print(f"Sent UDP update for {table_type}: {params}")
            return True
            
        except Exception as e:
            print(f"Error sending parameter update: {e}")
            return False
    
    def register_response_callback(self, callback):
        """
        Register a callback function to handle parameter responses.
        
        Parameters:
        -----------
        callback : function
            Function to call when parameter responses are received
            Should accept (values, addr) parameters
        """
        self.response_callback = callback
    
    def get_latest_data(self):
        """
        Get the most recent data point for all parameters.
        
        Returns:
        --------
        dict
            Dictionary containing the latest value for each parameter.
        """
        with self.data_lock:
            return self.latest_data.copy()
    
    def get_reference_values(self):
        """
        Get the current reference values.
        
        Returns:
        --------
        dict
            Dictionary containing the reference values.
        """
        with self.data_lock:
            return self.reference_values.copy()
    
    def get_last_response(self, address=None):
        """
        Get the last response received from a specific address.
        
        Parameters:
        -----------
        address : tuple or None
            Specific address to get response from, or None for server address
        
        Returns:
        --------
        dict or None
            Last response data or None if no response received
        """
        if address is None:
            address = (self.server_ip, self.server_port)
            
        return self.last_responses.get(address)
    
    def filter_by_time_window(self, time_data, *data_series, time_window=None):
        """
        Filter data to only include points within the specified time window from the most recent point.
        Enhanced with race condition protection.
        
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
        # Handle empty arrays
        if len(time_data) == 0:
            return (time_data,) + data_series
        
        try:
            # Create safe copies to avoid race conditions
            time_copy = np.array(time_data, copy=True)
            data_copies = [np.array(series, copy=True) for series in data_series]
            
            # Get the most recent time point
            latest_time = time_copy[-1] if len(time_copy) > 0 else 0
            
            # Calculate the cutoff time
            cutoff_time = latest_time - time_window
            
            # Find indices where time is >= cutoff_time
            indices = np.where(time_copy >= cutoff_time)[0]
            
            # Defensive check to ensure indices are valid for all arrays
            for i, arr in enumerate(data_copies):
                if len(indices) > 0 and indices[-1] >= len(arr):
                    print(f"Index range mismatch: max index {indices[-1]} exceeds array {i} length {len(arr)}")
                    # Return full arrays as fallback
                    return (time_data,) + data_series
            
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
            # Return the original data if filtering fails
            return (time_data,) + data_series

    def get_waveform_data(self, waveform_type, n_points=None, time_window=None):
        """
        Get waveform data for voltage or current.
        
        Parameters:
        -----------
        waveform_type : str
            The type of waveform to get ('Grid_Voltage' or 'Grid_Current').
        n_points : int or None
            Number of data points to return. If None, returns all available history.
        time_window : float or None
            Time window in seconds to include. If None, returns all available history.
        """
        if waveform_type not in self.waveform_data:
            return np.array([]), np.array([]), np.array([]), np.array([])
        
        # Get all history first (with thread safety)
        with self.time_lock:
            time_data = np.array(list(self.time_history))
        
        with self.data_lock:
            phase_a = np.array(list(self.waveform_data[waveform_type]['phaseA']))
            phase_b = np.array(list(self.waveform_data[waveform_type]['phaseB']))
            phase_c = np.array(list(self.waveform_data[waveform_type]['phaseC']))
        
        # IMPORTANT FIX: If there's any data but less than enough for time_window,
        # return all available data rather than an empty set
        if len(time_data) > 0:
            # Use all available data if there's not enough
            if time_window is not None and (len(time_data) < 2 or 
                                        (time_data[-1] - time_data[0]) < time_window):
                print(f"DEBUG: Not enough data for {time_window}s window, using all {len(time_data)} points")
                return time_data, phase_a, phase_b, phase_c
        else:
            return np.array([]), np.array([]), np.array([]), np.array([])
        
        # Original time window filter logic continues...
        if time_window is not None:
            time_data, phase_a, phase_b, phase_c = self.filter_by_time_window(
                time_data, phase_a, phase_b, phase_c, time_window=time_window
            )
        # Otherwise apply n_points filter
        elif n_points is not None:
            # Get the most recent n_points
            n = min(n_points, len(time_data))
            time_data = time_data[-n:]
            phase_a = phase_a[-n:]
            phase_b = phase_b[-n:]
            phase_c = phase_c[-n:]
        
        return time_data, phase_a, phase_b, phase_c

    def get_power_data(self, n_points=None, time_window=None):
        """
        Get power data for grid, PV, EV, and battery.
        
        Parameters:
        -----------
        n_points : int or None
            Number of data points to return. If None, returns all available history.
        time_window : float or None
            Time window in seconds to include. If None, returns all available history.
        """
        # Get all history first (with thread safety)
        with self.time_lock:
            time_data = np.array(list(self.time_history))
        
        with self.data_lock:
            grid_power = np.array(list(self.data_history['Grid_Power']))
            pv_power = np.array(list(self.data_history['PhotoVoltaic_Power']))
            ev_power = np.array(list(self.data_history['ElectricVehicle_Power']))
            battery_power = np.array(list(self.data_history['Battery_Power']))
        
        # IMPORTANT FIX: If there's any data but less than enough for time_window,
        # return all available data rather than an empty set
        if len(time_data) > 0:
            # Use all available data if there's not enough
            if time_window is not None and (len(time_data) < 2 or 
                                        (time_data[-1] - time_data[0]) < time_window):
                print(f"DEBUG: Not enough data for {time_window}s window, using all {len(time_data)} points")
                return time_data, grid_power, pv_power, ev_power, battery_power
        else:
            return np.array([0]), np.array([0]), np.array([0]), np.array([0]), np.array([0])
        
        # Apply time window filter if specified
        if time_window is not None:
            time_data, grid_power, pv_power, ev_power, battery_power = self.filter_by_time_window(
                time_data, grid_power, pv_power, ev_power, battery_power, time_window=time_window
            )
        # Otherwise apply n_points filter
        elif n_points is not None:
            # Get the most recent n_points
            n = min(n_points, len(time_data))
            time_data = time_data[-n:]
            grid_power = grid_power[-n:]
            pv_power = pv_power[-n:]
            ev_power = ev_power[-n:]
            battery_power = battery_power[-n:]
        
        return time_data, grid_power, pv_power, ev_power, battery_power

    def get_parameter_history(self, parameter, n_points=None, time_window=None):
        """
        Get historical data for a specific parameter.
        
        Parameters:
        -----------
        parameter : str
            The name of the parameter to get history for.
        n_points : int or None
            Number of historical data points to return. If None, returns all available history.
        time_window : float or None
            Time window in seconds to include. If None, returns all available history.
        """
        if parameter not in self.data_history:
            return np.array([]), np.array([])
        
        # Get all history first (with thread safety)
        with self.time_lock:
            time_data = np.array(list(self.time_history))
        
        with self.data_lock:
            param_data = np.array(list(self.data_history[parameter]))
        
        # If empty, return empty arrays
        if len(time_data) == 0:
            return np.array([]), np.array([])
        
        # Apply time window filter if specified
        if time_window is not None:
            time_data, param_data = self.filter_by_time_window(
                time_data, param_data, time_window=time_window
            )
        # Otherwise apply n_points filter
        elif n_points is not None:
            # Get the most recent n_points
            n = min(n_points, len(time_data))
            time_data = time_data[-n:]
            param_data = param_data[-n:]
        
        return time_data, param_data
    
    def _generate_waveforms(self, voltage_amplitude, current_amplitude, timestamp):
        """
        Generate three-phase waveforms based on the single voltage and current values.
        Identical to UDPClient's method but with thread safety.
        
        Parameters:
        -----------
        voltage_amplitude : float
            The voltage amplitude value from the hardware.
        current_amplitude : float
            The current amplitude value from the hardware.
        timestamp : float
            The current time value.
        """
        with self.data_lock:
            frequency = self.latest_data.get('Frequency', self.frequency)
            power_factor = self.latest_data.get('Power_Factor', 0.95)
        
        # Calculate the sine wave position based on time
        voltage_peak = voltage_amplitude * np.sqrt(2)  # Convert RMS to peak if needed
        current_peak = current_amplitude * np.sqrt(2)  # Convert RMS to peak if needed
        
        # Generate time-based angle for the sine waves
        angle = 2 * np.pi * frequency * timestamp
        
        # Calculate values for the three voltage phases
        voltage_a = voltage_peak * np.sin(angle)
        voltage_b = voltage_peak * np.sin(angle - self.phase_shift)
        voltage_c = voltage_peak * np.sin(angle + self.phase_shift)
        
        # Calculate values for the three current phases
        actual_pf = max(-1.0, min(1.0, power_factor))
        power_factor_angle = np.arccos(actual_pf)
        current_a = current_peak * np.sin(angle - power_factor_angle)
        current_b = current_peak * np.sin(angle - self.phase_shift - power_factor_angle)
        current_c = current_peak * np.sin(angle + self.phase_shift - power_factor_angle)
        
        # Store the calculated values with thread safety
        with self.data_lock:
            self.waveform_data['Grid_Voltage']['phaseA'].append(voltage_a)
            self.waveform_data['Grid_Voltage']['phaseB'].append(voltage_b)
            self.waveform_data['Grid_Voltage']['phaseC'].append(voltage_c)
            
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
        """Clean up resources and stop the receive thread."""
        print("Stopping UDP handler...")
        self.is_running = False
        
        # Wait for receive thread to terminate
        if self.receive_thread and self.receive_thread.is_alive():
            print("Waiting for receive thread to terminate...")
            self.receive_thread.join(timeout=2.0)
            if self.receive_thread.is_alive():
                print("Warning: Receive thread did not terminate cleanly")
        
        # Close the socket
        if self.socket:
            try:
                print("Closing UDP socket...")
                self.socket.close()
            except Exception as e:
                print(f"Error closing socket: {e}")
            self.socket = None
            
        print("UDP handler stopped")


# Global singleton instance for application-wide use
unified_udp = None

def initialize_unified_udp(server_ip="127.0.0.1", server_port=8888, local_port=0):
    """
    Initialize the global unified UDP handler.
    
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
    unified_udp = UnifiedUDPHandler(server_ip, server_port, local_port)
    
    # Define a simple response handler function
    def handle_parameter_response(values, addr):
        print(f"Parameter response from {addr}: {values}")
        # Here you could update UI elements or other application state
        # based on the received values
    
    # Register the handler
    unified_udp.register_response_callback(handle_parameter_response)
    
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