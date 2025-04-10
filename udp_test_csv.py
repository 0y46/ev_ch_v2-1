"""
Bidirectional UDP Test script for the EV Charging Station Monitor.
This script:
1. Sends test UDP packets in CSV format to match the hardware's format
2. Receives PARAM messages from the application
3. Responds with reference values (simulating your mentor's system)
"""

import socket
import time
import math
import random
import argparse
import threading

from network_config import (
    DEFAULT_SERVER_IP, DEFAULT_SERVER_PORT
)

class EVChargingTestServer:
    """
    Test server that simulates both the EV charging hardware (sending data)
    and the mentor's server (receiving parameter updates and responding).
    """
    
    def __init__(self, ip=DEFAULT_SERVER_IP, port=DEFAULT_SERVER_PORT, interval=0.1):
        """
        Initialize the test server.
        
        Parameters:
        -----------
        ip : str
            The IP address to bind to and send packets to.
        port : int
            The port to bind to (fixed to 8888 to match mentor's code).
        interval : float
            Time interval between data packets in seconds.
        """
        # Server configuration
        self.ip = ip
        self.port = port  # Fixed port 8888 to match mentor's configuration
        self.interval = interval
        self.socket = None
        
        # Client tracking - store address of any client that connects
        self.client_addresses = {}  # Dictionary to track clients by a unique ID
        
        # Control flags
        self.is_running = False
        self.receive_thread = None
        self.send_thread = None
        
        # Parameters received from the application
        self.received_params = {
            "grid_settings": {},
            "charging_setting": {},
            "ev_charging_setting": {}
        }
        
        # Reference values to send as responses
        # self.reference_values = {
        #    "Vdc_ref": 400.0, 
        #    "Pev_ref": -3000.0,
        #    "Ppv_ref": 2500.0
        #}
        
        # Initialize SoC values with realistic starting points
        self.soc_battery = 60.0  # Initial battery SoC (%)
        self.soc_ev = 45.0       # Initial EV SoC (%)
        
        # Base parameter values for sending data
        self.frequency = 50.0  # Hz
        self.vd = 220.0  # Grid Voltage (V)
        self.id_val = 10.0  # Grid Current (A)
        self.vdc = 400.0  # DC Link Voltage (V)
        self.vev = 350.0  # EV Voltage (V)
        self.vpv = 380.0  # PV Voltage (V)
        self.iev = 15.0  # EV Current (A)
        self.ipv = 8.0  # PV Current (A)
        self.ppv = self.vpv * self.ipv  # PV Power (W)
        self.pev = self.vev * self.iev * -1  # EV Power (W)
        self.pbattery = 500.0  # Battery Power (W)
        self.pf = 0.95  # Power Factor
        
    def initialize_socket(self):
        """
        Initialize the UDP socket for bidirectional communication.
        Binds to port 8888 to match mentor's code.
        
        Returns:
        --------
        bool
            True if initialized successfully, False otherwise.
        """
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Allow socket to be reused
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to the specified IP and port
            # This uses a fixed port 8888 as in mentor's code
            self.socket.bind((self.ip, self.port))
            
            # Set a timeout so receive doesn't block indefinitely
            self.socket.settimeout(0.1)  # 100ms timeout
            
            print(f"UDP test server initialized on {self.ip}:{self.port}")
            return True
        except Exception as e:
            print(f"Error initializing UDP socket: {e}")
            if self.socket:
                self.socket.close()
                self.socket = None
            return False
    
    def start(self, duration=60):
        """
        Start the bidirectional test server.
        
        Parameters:
        -----------
        duration : float
            Total duration to run the test for in seconds.
            
        Returns:
        --------
        bool
            True if started successfully, False otherwise.
        """
        if self.is_running:
            print("Test server is already running")
            return False
        
        if not self.initialize_socket():
            return False
        
        self.is_running = True
        print(f"Starting bidirectional UDP test for {duration} seconds...")
        
        # Start the receive thread to listen for messages from clients
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        
        # Start the send thread to send simulated data packets
        self.send_thread = threading.Thread(target=self._send_loop, args=(duration,), daemon=True)
        self.send_thread.start()
        
        # Wait for the specified duration
        try:
            end_time = time.time() + duration
            while time.time() < end_time and self.is_running:
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\nTest stopped by user")
        finally:
            self.stop()
            
        return True
    
    def stop(self):
        """Stop the test server and clean up resources."""
        if not self.is_running:
            return
            
        self.is_running = False
        
        # Wait for threads to terminate
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=1.0)
        
        if self.send_thread and self.send_thread.is_alive():
            self.send_thread.join(timeout=1.0)
        
        # Close the socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
            
        print("Test server stopped")
    
    def _receive_loop(self):
        """
        Background thread method to continuously receive messages from clients.
        Now accepts any message to establish a connection.
        """
        print("Started receive thread - listening for client messages")
        
        while self.is_running and self.socket:
            try:
                # Attempt to receive data
                data, addr = self.socket.recvfrom(1024)
                
                if data:
                    # Process the received data
                    message = data.decode('utf-8').strip()
                    client_id = f"{addr[0]}:{addr[1]}"  # Create unique client identifier

                    # Check if this is a loopback message from ourselves
                    if addr[1] == self.port and addr[0] in ('127.0.0.1', self.ip):
                        # Skip processing our own messages
                        continue
                    
                    # Add this client to tracked addresses if new
                    if client_id not in self.client_addresses:
                        self.client_addresses[client_id] = addr
                        print(f"New client connected: {client_id}")
                        # Send first data packet immediately to establish connection
                        self._send_data_to_client(addr)
                    
                    # Try to parse this as a parameter update (format: tableID,value1,value2,...)
                    parts = message.split(',')
                    if len(parts) >= 2:
                        try:
                            # Try to extract table ID from the first part
                            table_id = int(parts[0])
                            
                            # Determine table type based on ID
                            table_type = None
                            if table_id == 1:
                                table_type = "grid_settings"
                                # For grid settings, expect 5 values: vg_rms, ig_rms, frequency, thd, power_factor
                                if len(parts) >= 6:  # ID + 5 parameters
                                    params = {
                                        "vg_rms": float(parts[1]),
                                        "ig_rms": float(parts[2]),
                                        "frequency": float(parts[3]),
                                        "thd": float(parts[4]),
                                        "power_factor": float(parts[5])
                                    }
                                    print(f"\nReceived grid_settings update from {client_id}:")
                                    for name, value in params.items():
                                        print(f"  {name} = {value}")
                                        
                                    # Apply updates - No reference response needed
                                    self._apply_parameter_updates(table_type, params)
                                    
                            elif table_id == 2:
                                table_type = "charging_setting"
                                # For charging settings, expect 3 values: pv_power, ev_power, battery_power
                                if len(parts) >= 4:  # ID + 3 parameters
                                    params = {
                                        "pv_power": float(parts[1]),
                                        "ev_power": float(parts[2]),
                                        "battery_power": float(parts[3])
                                    }
                                    print(f"\nReceived charging_setting update from {client_id}:")
                                    for name, value in params.items():
                                        print(f"  {name} = {value}")
                                        
                                    # Apply updates - No reference response needed
                                    self._apply_parameter_updates(table_type, params)
                                    
                            elif table_id == 3:
                                table_type = "ev_charging_setting"
                                # For EV charging settings, expect 4 values: ev_voltage, ev_soc, demand_response, v2g
                                if len(parts) >= 5:  # ID + 4 parameters
                                    params = {
                                        "ev_voltage": float(parts[1]),
                                        "ev_soc": float(parts[2]),
                                        "demand_response": parts[3] == "1",
                                        "v2g": parts[4] == "1"
                                    }
                                    print(f"\nReceived ev_charging_setting update from {client_id}:")
                                    for name, value in params.items():
                                        print(f"  {name} = {value}")
                                        
                                    # Apply updates - No reference response needed
                                    self._apply_parameter_updates(table_type, params)
                        except (ValueError, IndexError) as e:
                            # If parsing fails, just log the message
                            print(f"\nReceived from {client_id}: {message}")
                    else:
                        # Just log the message
                        print(f"\nReceived from {client_id}: {message}")
                
            except socket.timeout:
                # This is expected if no data is received within the timeout period
                pass
            except Exception as e:
                print(f"Error receiving data: {e}")
                time.sleep(0.1)  # Prevent tight loop if there's a persistent error
    
    #def _process_param_message(self, message, addr):
    #    """
    #    Process a received parameter update message.
    #    
    #    Parameters:
    #    -----------
    #    message : str
    #        The parameter update message (PARAM,table_id,param1,value1,...)
    #    addr : tuple
    #        The sender's address (ip, port)
    #    """
    #    # Parse the message
    #    parts = message.split(',')
    #    if len(parts) < 3 or parts[0] != PARAM_PREFIX:
    #        print(f"Invalid parameter message format: {message}")
    #        return
        
        # Extract table ID and map to table type
        table_id = int(parts[1])
        table_type = None
        if table_id == 1:
            table_type = "grid_settings"
        elif table_id == 2:
            table_type = "charging_setting"
        elif table_id == 3:
            table_type = "ev_charging_setting"
        else:
            print(f"Unknown table ID: {table_id}")
            return
            
        # Extract parameters and values
        params = {}
        for i in range(2, len(parts)-1, 2):
            if i+1 < len(parts):
                param_name = parts[i]
                param_value = parts[i+1]
                
                # Convert value to appropriate type
                try:
                    if param_value == "0" or param_value == "1":
                        # Likely a boolean
                        params[param_name] = param_value == "1"
                    else:
                        # Try as float
                        params[param_name] = float(param_value)
                except ValueError:
                    # Leave as string if conversion fails
                    params[param_name] = param_value
                
                print(f"  {param_name} = {params[param_name]}")
        
        # Store the parameters
        self.received_params[table_type] = params
        
        # Apply parameter updates to simulation values
        self._apply_parameter_updates(table_type, params)
        
        # Send a response with reference values (similar to your mentor's system)
        #self._send_reference_response(addr)
    
    def _apply_parameter_updates(self, table_type, params):
        """
        Apply received parameter updates to the simulation values.
        
        Parameters:
        -----------
        table_type : str
            The type of table being updated
        params : dict
            Dictionary of parameter names and their new values
        """
        # Update simulation parameters based on received values
        if table_type == "grid_settings":
            if "vg_rms" in params:
                self.vd = params["vg_rms"]
            if "ig_rms" in params:
                self.id_val = params["ig_rms"]
            if "frequency" in params:
                self.frequency = params["frequency"]
            if "power_factor" in params:
                self.pf = params["power_factor"]
        
        elif table_type == "charging_setting":
            if "pv_power" in params:
                self.ppv = params["pv_power"]
            if "ev_power" in params:
                self.pev = params["ev_power"]
            if "battery_power" in params:
                self.pbattery = params["battery_power"]
        
        elif table_type == "ev_charging_setting":
            if "ev_voltage" in params:
                self.vev = params["ev_voltage"]
            if "ev_soc" in params:
                self.soc_ev = params["ev_soc"]
    
    #def _send_reference_response(self, addr):
    #    """
    #    Send a response with reference values like a mentor's system would.
    #    
    #    Parameters:
    #    -----------
    #    addr : tuple
    #        The address to send the response to (ip, port)
    #    """
    #    # Create response message with reference values (Vdc_ref,Pev_ref,Ppv_ref)
    #    response = f"{self.reference_values['Vdc_ref']},{self.reference_values['Pev_ref']},{self.reference_values['Ppv_ref']}"
    #    
    #    try:
    #        # Send the response
    #        self.socket.sendto(response.encode('utf-8'), addr)
    #        print(f"Sent reference response: {response}")
    #    except Exception as e:
    #        print(f"Error sending reference response: {e}")
    
    def _send_loop(self, duration):
        """
        Background thread method to continuously send data packets.
        
        Parameters:
        -----------
        duration : float
            Total duration to send packets for in seconds.
        """
        print(f"Started send thread - sending data packets every {self.interval} seconds")
        print(f"Format: Vd,Id,Vdc,Vev,Vpv,Iev,Ipv,Ppv,Pev,Pbattery,Pg,Qg,PF,Fg,THD,s1,s2,s3,s4,SoC_battery,SoC_EV")
        
        start_time = time.time()
        packet_count = 0
        
        while self.is_running and time.time() - start_time < duration:
            # Skip if no clients are connected yet
            if not self.client_addresses:
                time.sleep(1.0)  # Wait a bit for clients to connect
                continue
                
            # Send data to all connected clients
            for client_id, addr in list(self.client_addresses.items()):
                self._send_data_to_client(addr)
                
            packet_count += len(self.client_addresses)
            if packet_count % 100 == 0:
                print(f"Sent {packet_count} packets... Battery SoC: {self.soc_battery:.1f}%, EV SoC: {self.soc_ev:.1f}%")
                
            # Wait for the next interval
            time.sleep(self.interval)
        
        elapsed_time = time.time() - start_time
        print(f"Sent {packet_count} packets in {elapsed_time:.2f} seconds")
        print(f"Final values - Battery SoC: {self.soc_battery:.1f}%, EV SoC: {self.soc_ev:.1f}%")
    
    def _send_data_to_client(self, addr):
        """
        Send a data packet to a specific client.
        
        Parameters:
        -----------
        addr : tuple
            The client's address (ip, port)
        """
        try:
            # Current time for waveform calculation
            current_time = time.time()
            
            # Add some randomness to base values
            vd = self.vd + random.uniform(-5, 5)
            id_val = self.id_val + random.uniform(-1, 1)
            vdc = self.vdc + random.uniform(-3, 3)
            vev = self.vev + random.uniform(-2, 2)
            vpv = self.vpv + random.uniform(-3, 3)
            iev = self.iev + random.uniform(-0.5, 0.5)
            ipv = self.ipv + random.uniform(-0.4, 0.4)
            
            # Calculate powers
            ppv = vpv * ipv  # Use simulated instantaneous values
            pev = vev * iev * -1  # Negative for consumption
            
            # Determine power factor with realistic variations
            pf = self.pf + random.uniform(-0.05, 0.05)
            pf = min(1.0, max(0.8, pf))  # Constrain to realistic range
            
            # Battery power with realistic variations
            pbattery = self.pbattery + random.uniform(-100, 100)
            
            # Add a slow oscillation to simulate changing conditions
            oscillation = math.sin(current_time * 0.1) * 50
            ppv += oscillation
            pev -= oscillation
            
            # Grid power balances the system (conservation of energy)
            pg = -1 * (ppv + pev + pbattery) + random.uniform(-50, 50)  # With some noise
            
            # Calculate reactive power
            theta = math.acos(pf)  # Power factor angle
            qg = pg * math.tan(theta)  # Reactive power
            
            # Other electrical parameters
            fg = self.frequency + random.uniform(-0.1, 0.1)  # Grid Frequency (Hz)
            thd = 3.0 + random.uniform(-0.5, 0.5)  # THD (%)
            
            # Status indicators (0=Off, 1=Standby, 2=Active, 3=Fault)
            s1 = 2 if ppv > 100 else 0  # PV Status: Active if generating power
            s2 = 2 if abs(pev) > 100 else 0  # EV Status: Active if charging/discharging
            s3 = 2  # Grid Status: Typically active
            s4 = 2 if abs(pbattery) > 100 else 0  # Battery Status: Active if in use
            
            # Add small chance of fault for realism
            if random.random() < 0.005:  # 0.5% chance
                fault_component = random.randint(1, 4)
                if fault_component == 1: s1 = 3
                elif fault_component == 2: s2 = 3
                elif fault_component == 3: s3 = 3
                else: s4 = 3
            
            # Update SoC values based on power flow
            if pev < 0:  # Charging
                self.soc_ev += (abs(pev) / 10000) * self.interval  # Increase SoC when charging
            else:  # Discharging or idle
                self.soc_ev -= (pev / 20000) * self.interval  # Slower discharge
            
            if pbattery < 0:  # Battery discharging
                self.soc_battery -= (abs(pbattery) / 5000) * self.interval
            else:  # Battery charging
                self.soc_battery += (pbattery / 8000) * self.interval
            
            # Constrain SoC values
            self.soc_battery = max(0, min(100, self.soc_battery))
            self.soc_ev = max(0, min(100, self.soc_ev))
            
            # Format the data as a CSV string with all parameters - WITHOUT reference values at the end
            data = f"{vd:.2f},{id_val:.2f},{vdc:.2f},{vev:.2f},{vpv:.2f},{iev:.2f},{ipv:.2f},{ppv:.2f},{pev:.2f}," + \
                f"{pbattery:.2f},{pg:.2f},{qg:.2f},{pf:.2f},{fg:.2f},{thd:.2f}," + \
                f"{s1},{s2},{s3},{s4},{self.soc_battery:.2f},{self.soc_ev:.2f}"
            
            # Send the data
            self.socket.sendto(data.encode('utf-8'), addr)
                
        except Exception as e:
            print(f"Error sending data packet: {e}")
            # Remove client if we can't send to it anymore
            for client_id, client_addr in list(self.client_addresses.items()):
                if client_addr == addr:
                    print(f"Removing unreachable client: {client_id}")
                    del self.client_addresses[client_id]
                    break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Bidirectional UDP Test for EV Charging Station')
    parser.add_argument('--ip', default='127.0.0.1', help='IP address to bind to')
    parser.add_argument('--port', type=int, default=8888, help='Port to bind to (default: 8888 to match mentor code)')
    parser.add_argument('--interval', type=float, default=0.1, help='Packet interval in seconds')
    parser.add_argument('--duration', type=float, default=60, help='Test duration in seconds')
    args = parser.parse_args()
    
    # Start the bidirectional test server
    server = EVChargingTestServer(args.ip, args.port, args.interval)
    server.start(args.duration)