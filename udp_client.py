"""
UDP Client for receiving real-time data from the EV Charging Station.
This module handles receiving and parsing UDP packets from the hardware.
"""

import socket
import threading
import time
import numpy as np
from collections import deque

class UDPClient:
    """
    A UDP client that receives and parses data from the EV Charging Station hardware.
    
    The data format is a CSV string with 21 values:
    Vd,Id,Vdc,Vev,Vpv,Iev,Ipv,Ppv,Pev,Pbattery,Pg,Qg,PF,Fg,THD,s1,s2,s3,s4,SoC_battery,SoC_EV
    """
    
    def __init__(self, ip="127.0.0.1", port=8888, listen_port=0, buffer_size=1024, history_length=1000):
        """
        Initialize the UDP client.
        
        Parameters:
        -----------
        ip : str
            The server IP address to communicate with. Default is '127.0.0.1' for localhost.
        port : int
            The server port to communicate with. Default is 8888 to match mentor's code.
        buffer_size : int
            Size of the receive buffer in bytes.
        history_length : int
            Number of historical data points to store for each parameter.
        """
        # Server connection details
        self.server_ip = ip           # Address of the UDP server
        self.server_port = port       # Port of the UDP server (fixed to 8888 like mentor's code)
        
        # Client details
        self.listen_port = 0          # 0 means the OS will assign an available port
        self.client_port = None       # Will be assigned when socket is bound
        
        self.buffer_size = buffer_size
        self.history_length = history_length
        
        # Socket for receiving UDP packets
        self.socket = None
        
        # Flag to control the receive thread
        self.is_running = False
        self.receive_thread = None
        
        # Data storage - based on the CSV format from the mentor's code
        # The data order is: Vd,Id,Vdc,Vev,Vpv,Iev,Ipv,Ppv,Pev
        self.latest_data = {
            'Grid_Voltage': 0.0,       # Vd
            'Grid_Current': 0.0,       # Id
            'DCLink_Voltage': 0.0,     # Vdc
            'ElectricVehicle_Voltage': 0.0, # Vev
            'PhotoVoltaic_Voltage': 0.0,    # Vpv
            'ElectricVehicle_Current': 0.0, # Iev
            'PhotoVoltaic_Current': 0.0,    # Ipv
            'PhotoVoltaic_Power': 0.0,      # Ppv
            'ElectricVehicle_Power': 0.0,   # Pev
            'Battery_Power': 0.0       # Calculated, not directly from device
        }
        
        # For time series data
        self.time_history = deque(maxlen=history_length)
        
        # History storage for each parameter
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
        
        # For waveform data (will be generated from single values)
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
        
        # Waveform generation parameters
        self.frequency = 50.0  # Hz (grid frequency)
        self.phase_shift = (2 * np.pi) / 3  # 120 degrees in radians
        self.last_waveform_time = 0
    
    def start(self):
        """
        Start the UDP client and begin receiving data.
        
        This method creates a socket, binds it to a dynamically assigned port,
        and starts a background thread to receive and process incoming data.
        
        Returns:
        --------
        bool
            True if started successfully, False otherwise.
        """
        if self.is_running:
            print("UDP client is already running")
            return True
        
        try:
            # Create a UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Set socket options to reuse address (useful if the socket was recently closed)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Set a timeout so the socket doesn't block indefinitely
            self.socket.settimeout(1.0)
            
            # Bind the socket to the listen port (0 means OS will assign a port)
            # This is different from mentor's code but enables dynamic port allocation
            self.socket.bind(("0.0.0.0", self.listen_port))  # Listen on all interfaces
            
            # Get the actual port assigned by the OS
            _, self.client_port = self.socket.getsockname()
            
            print(f"UDP client listening on port {self.client_port}, will communicate with server at {self.server_ip}:{self.server_port}")
            
            # Set the running flag and start the receive thread
            self.is_running = True
            self.receive_thread = threading.Thread(target=self._receive_data, daemon=True)
            self.receive_thread.start()
            
            return True
                
        except Exception as e:
            print(f"Error starting UDP client: {e}")
            if self.socket:
                self.socket.close()
                self.socket = None
            return False
    
    def stop(self):
        """
        Stop the UDP client and clean up resources.
        """
        self.is_running = False
        
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2.0)
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
            
        print("UDP client stopped")
    
    def _receive_data(self):
        """
        Background thread method to continuously receive and process UDP packets.
        The data is expected in CSV format as specified by the mentor's code.
        """
        start_time = time.time()
        packet_count = 0
        
        # Send an initial packet to server to establish communication
        self._send_hello_packet()
        
        while self.is_running:
            try:
                # Attempt to receive data (will timeout after 1 second if no data)
                data, addr = self.socket.recvfrom(self.buffer_size)
                
                # Debug output to confirm receipt
                packet_count += 1
                if packet_count % 100 == 0:
                    print(f"UDP packets received: {packet_count}")
                
                # Calculate current time but DON'T add to time_history yet
                current_time = time.time() - start_time
                
                # Process the received data - time_history is updated inside if valid
                self._process_data(data, current_time)
                
            except socket.timeout:
                # This is expected if no data is received within the timeout period
                # Periodically send a hello packet to ensure server knows our address/port
                if packet_count == 0 and time.time() - start_time > 5.0:  # No data for 5 seconds
                    self._send_hello_packet()
                    start_time = time.time()  # Reset timer to avoid spamming
                pass
            except Exception as e:
                print(f"Error receiving data: {e}")
                time.sleep(0.1)  # Prevent tight loop if there's a persistent error
    
    def _send_hello_packet(self):
        """
        Send a hello packet to the server to establish communication.
        This helps the server know our address and port for responses.
        """
        try:
            # Simple hello message to establish communication
            hello_message = "HELLO"
            self.socket.sendto(hello_message.encode('utf-8'), (self.server_ip, self.server_port))
            print(f"Sent hello packet to {self.server_ip}:{self.server_port}")
        except Exception as e:
            print(f"Error sending hello packet: {e}")
    
    def _process_data(self, data, timestamp):
        """
        Process received UDP data packet.
        
        The data is expected as a CSV string with values:
        Vd,Id,Vdc,Vev,Vpv,Iev,Ipv,Ppv,Pev,Pbattery,Pg,Qg,PF,Fg,THD,s1,s2,s3,s4,SoC_battery,SoC_EV
        
        Also handles ignoring PARAM messages that are part of bidirectional communication.
        
        Parameters:
        -----------
        data : bytes
            The raw data received from the UDP socket.
        timestamp : float
            The timestamp when the data was received.
        """
        try:
            # Decode the bytes to a string
            data_str = data.decode('utf-8').strip()
            
            # Check if this is a parameter update message (starts with "PARAM")
            if data_str.startswith("PARAM"):
                print(f"Received parameter message (skipping): {data_str[:40]}...")
                return  # RETURN WITHOUT ADDING TIMESTAMP
            
            # Count commas to estimate number of values
            comma_count = data_str.count(',')
            
            # If this looks like a reference response (only 2-3 commas)
            if comma_count < 5:
                print(f"Received reference values: {data_str}")
                return  # RETURN WITHOUT ADDING TIMESTAMP
            
            # Split the CSV string into values
            values = data_str.split(',')
            
            # Ensure we have the expected number of values
            expected_values = 21
            if len(values) != expected_values:
                print(f"Warning: Expected {expected_values} values, got {len(values)}")
                return  # RETURN WITHOUT ADDING TIMESTAMP
            
            # Now we know this is valid data - ADD TIMESTAMP TO HISTORY
            self.time_history.append(timestamp)
            
            # Parse the values into floats
            try:
                vd = float(values[0])         # Grid Voltage
                id_val = float(values[1])     # Grid Current
                vdc = float(values[2])        # DC Link Voltage
                vev = float(values[3])        # EV Voltage
                vpv = float(values[4])        # PV Voltage
                iev = float(values[5])        # EV Current
                ipv = float(values[6])        # PV Current
                ppv = float(values[7])        # PV Power
                pev = float(values[8])        # EV Power
                
                # New parameters from mentor:
                pbattery = float(values[9])   # Battery Power
                pgrid = float(values[10])     # Grid Power (now directly measured)
                qgrid = float(values[11])     # Grid Reactive Power
                power_factor = float(values[12])  # Power Factor
                frequency = float(values[13]) # Grid Frequency
                thd = float(values[14])       # Total Harmonic Distortion
                
                # Status indicators (int values 0-3)
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
                
            # Update latest data with all parameters
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

            # ADD THESE NEW HISTORY UPDATES:
            self.data_history['Grid_Reactive_Power'].append(qgrid)
            self.data_history['Power_Factor'].append(power_factor)
            self.data_history['Frequency'].append(frequency)
            self.data_history['THD'].append(thd)
            self.data_history['Battery_SoC'].append(soc_battery)
            self.data_history['EV_SoC'].append(soc_ev)
            
            # Generate three-phase waveforms
            self._generate_waveforms(vd, id_val, timestamp)
            
        except Exception as e:
            print(f"Error processing data: {e}")
    
    def _generate_waveforms(self, voltage_amplitude, current_amplitude, timestamp):
        """
        Generate three-phase waveforms based on the single voltage and current values.
        
        Since the hardware provides only a single value (presumably the magnitude),
        we generate three-phase waveforms with the appropriate phase shifts.
        
        Parameters:
        -----------
        voltage_amplitude : float
            The voltage amplitude value from the hardware.
        current_amplitude : float
            The current amplitude value from the hardware.
        timestamp : float
            The current time value.
        """
        # Calculate the sine wave position based on time
        # Note: The frequency is assumed to be 50Hz
        # Scale the amplitude by sqrt(2) to convert from RMS to peak if needed
        # (depending on how the values are provided by the hardware)
        voltage_peak = voltage_amplitude * np.sqrt(2)  # Convert RMS to peak if needed
        current_peak = current_amplitude * np.sqrt(2)  # Convert RMS to peak if needed
        
        # Generate time-based angle for the sine waves
        angle = 2 * np.pi * self.latest_data.get('Frequency', self.frequency) * timestamp
        
        # Calculate values for the three voltage phases
        voltage_a = voltage_peak * np.sin(angle)
        voltage_b = voltage_peak * np.sin(angle - self.phase_shift)
        voltage_c = voltage_peak * np.sin(angle + self.phase_shift)
        
        # Calculate values for the three current phases
        # Add a small phase shift to simulate typical power factor
        # Get the actual power factor or use 0.95 as fallback
        actual_pf = self.latest_data.get('Power_Factor', 0.95)
        # Ensure power factor is in valid range (-1 to 1)
        actual_pf = max(-1.0, min(1.0, actual_pf))
        power_factor_angle = np.arccos(actual_pf)  # Assume power factor of 0.95 lagging
        current_a = current_peak * np.sin(angle - power_factor_angle)
        current_b = current_peak * np.sin(angle - self.phase_shift - power_factor_angle)
        current_c = current_peak * np.sin(angle + self.phase_shift - power_factor_angle)
        
        # Store the calculated values
        self.waveform_data['Grid_Voltage']['phaseA'].append(voltage_a)
        self.waveform_data['Grid_Voltage']['phaseB'].append(voltage_b)
        self.waveform_data['Grid_Voltage']['phaseC'].append(voltage_c)
        
        self.waveform_data['Grid_Current']['phaseA'].append(current_a)
        self.waveform_data['Grid_Current']['phaseB'].append(current_b)
        self.waveform_data['Grid_Current']['phaseC'].append(current_c)
    
    def get_latest_data(self):
        """
        Get the most recent data point for all parameters.
        
        Returns:
        --------
        dict
            Dictionary containing the latest value for each parameter.
        """
        return self.latest_data.copy()
    
    # Add this function to your UDPClient class:

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
        
        # Get all history first
        time_data = np.array(list(self.time_history))
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
        # Get all history first
        time_data = np.array(list(self.time_history))
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
        
        # Get all history first
        time_data = np.array(list(self.time_history))
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
    
    def is_connected(self):
        """
        Check if the UDP client is running and has received data.
        
        Returns:
        --------
        bool
            True if the client is running and has received data, False otherwise.
        """
        return self.is_running and len(self.time_history) > 0