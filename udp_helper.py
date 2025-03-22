# udp_helper.py
"""
Bidirectional UDP communication helper for EV charging application.
Provides functionality for sending parameter updates over UDP protocol
and receiving responses on the same port.
"""

import socket
import threading
import time

from network_config import (
    DEFAULT_SERVER_IP, DEFAULT_SERVER_PORT, DEFAULT_CLIENT_PORT,
    PARAM_PREFIX, HELLO_MESSAGE, TABLE_ID_GRID, TABLE_ID_CHARGING, TABLE_ID_EV
)

class EVChargerUDP:
    """
    Helper class to manage bidirectional UDP communication for the EV Charger application.
    
    This class handles sending parameter updates to the monitoring system
    using a simple CSV format and can receive responses on the same port.
    """
    
    def __init__(self, target_ip=DEFAULT_SERVER_IP, target_port=DEFAULT_SERVER_PORT, local_port=DEFAULT_CLIENT_PORT):
        """
        Initialize bidirectional UDP communication.
        
        Args:
            target_ip (str): IP address of the target server (default: 127.0.0.1)
            target_port (int): UDP port of the server (default: 8888 to match mentor's code)
            local_port (int): Local UDP port to bind to (default: 0, which means system assigns a port)
                              Using 0 allows multiple clients to connect without conflicts
        """
        self.target_address = (target_ip, target_port)
        self.local_port = local_port
        self.socket = None
        self.is_running = False
        self.receive_thread = None
        
        # Table IDs for different table types
        self.table_ids = {
            "grid_settings": TABLE_ID_GRID,
            "charging_setting": TABLE_ID_CHARGING,
            "ev_charging_setting": TABLE_ID_EV
        }
        
        # Dictionary to store the last response received from each remote address
        self.last_responses = {}
        
        # Callback function for handling parameter responses
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
            
            # Allow socket to be reused
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to local port for receiving responses
            # When local_port is 0, the system will assign an available port automatically
            # This matches mentor's approach of using dynamic client ports
            self.socket.bind(('0.0.0.0', self.local_port))
            
            # Get the actual port assigned by the system
            _, self.local_port = self.socket.getsockname()
            
            # Set a timeout so the socket doesn't block indefinitely
            self.socket.settimeout(0.1)  # 100ms timeout
            
            print(f"UDP socket initialized on port {self.local_port} for bidirectional communication")
            print(f"Configured to communicate with server at {self.target_address[0]}:{self.target_address[1]}")
            
            # Send initial hello packet to server to establish communication
            self._send_hello()
            
            return True
        except Exception as e:
            print(f"Failed to initialize UDP socket: {e}")
            self.socket = None
            return False
    
    def _send_hello(self):
        """Send a hello packet to the server to establish communication."""
        try:
            if self.socket:
                # Use the standard hello message
                self.socket.sendto(HELLO_MESSAGE.encode('utf-8'), self.target_address)
                print(f"Sent hello packet to server at {self.target_address[0]}:{self.target_address[1]}")
        except Exception as e:
            print(f"Failed to send hello packet: {e}")
    
    def _start_receive_thread(self):
        """Start a background thread to receive UDP responses."""
        if self.socket is None:
            print("Cannot start receive thread: Socket not initialized")
            return False
        
        # Set the running flag and start the receive thread
        self.is_running = True
        self.receive_thread = threading.Thread(target=self._receive_responses, daemon=True)
        self.receive_thread.start()
        
        return True
    
    def _receive_responses(self):
        """
        Background thread method to continuously receive and process UDP responses.
        Similar to your mentor's 'message' event handler.
        """
        reconnect_interval = 10.0  # Try to reconnect every 5 seconds if no data
        last_reconnect = time.time()
        
        while self.is_running and self.socket:
            try:
                # Attempt to receive data (will timeout after the socket timeout)
                data, addr = self.socket.recvfrom(1024)
                
                if data:
                    # Process the received data
                    message = data.decode('utf-8').strip()
                    
                    # Store the response by address
                    self.last_responses[addr] = {
                        'time': time.time(),
                        'data': message
                    }
                    
                    # If this is a PARAM message or starts with "PARAM"
                    if message.startswith("PARAM"):
                        # This is a parameter request or our own echo
                        # Skip further processing to avoid confusion
                        continue
                    
                    # Check if it looks like a parameter response (e.g., "Vdc_ref,Pev_ref,Ppv_ref")
                    # This mimics your mentor's response format
                    try:
                        values = message.split(',')
                        if 1 <= len(values) <= 10:  # Reasonable number of parameters
                            # Try to parse as numeric values
                            parsed_values = [float(val) for val in values]
                            
                            # Create named reference dictionary if it matches the expected format
                            if len(parsed_values) >= 3:
                                ref_dict = {
                                    "Vdc_ref": parsed_values[0],
                                    "Pev_ref": parsed_values[1],
                                    "Ppv_ref": parsed_values[2]
                                }
                                print(f"Received reference values: {ref_dict}")
                                
                            # Call callback with the parsed values
                            if self.response_callback:
                                self.response_callback(parsed_values, addr)
                    except ValueError:
                        # Not numeric values
                        print(f"Received non-parameter message: {message}")
                    
            except socket.timeout:
                # This is expected if no data is received within the timeout period
                # Periodically try to reconnect if we haven't received any data
                now = time.time()
                if now - last_reconnect > reconnect_interval:
                    self._send_hello()  # Send hello packet to reestablish communication
                    last_reconnect = now
                pass
            except Exception as e:
                if self.is_running:  # Only log errors if we're supposed to be running
                    print(f"Error receiving UDP response: {e}")
                    time.sleep(0.1)  # Prevent tight loop if there's a persistent error
    
    def send_parameter_update(self, table_type, params):
        """
        Send parameter updates over UDP using the CSV format.
        
        Formats the message as:
        PARAM,table_id,param1,value1,param2,value2,...
        
        Args:
            table_type (str): Type of table being updated (e.g., 'charging_setting')
            params (dict): Dictionary of parameter names and their new values
            
        Returns:
            bool: True if sending was successful, False otherwise
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
            csv_parts = [PARAM_PREFIX, str(table_id)]
            
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
            bytes_sent = self.socket.sendto(csv_data.encode('utf-8'), self.target_address)
            
            print(f"Sent {bytes_sent} bytes to {self.target_address}: {csv_data}")
            return True
            
        except Exception as e:
            print(f"Error sending UDP packet: {e}")
            return False
    
    def register_response_callback(self, callback):
        """
        Register a callback function to be called when parameter responses are received.
        
        The callback should accept two arguments:
        - values (list): List of parsed numeric values
        - addr (tuple): Sender's address tuple (ip, port)
        
        Args:
            callback: Function to call when responses are received
        """
        self.response_callback = callback
    
    def get_last_response(self, address=None):
        """
        Get the last response received from a specific address or the target.
        
        Args:
            address: Specific address to get response from, or None for target address
        
        Returns:
            dict or None: Last response data or None if no response received
        """
        if address is None:
            address = self.target_address
            
        return self.last_responses.get(address)
    
    def close(self):
        """Clean up resources and stop the receive thread."""
        self.is_running = False
        
        # Wait for receive thread to terminate
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=1.0)
        
        # Close the socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
            
        print("UDP helper closed")

# Global singleton instance for application-wide use
udp_client = None

def initialize_udp(target_ip=DEFAULT_SERVER_IP, target_port=DEFAULT_SERVER_PORT, local_port=DEFAULT_CLIENT_PORT):
    """
    Initialize the global UDP client for bidirectional communication.
    
    Args:
        target_ip (str): IP address of the target server (default: 127.0.0.1)
        target_port (int): UDP port of the server (default: 8888 to match mentor's code)
        local_port (int): Local UDP port to bind to (default: 0 for system-assigned port)
        
    Returns:
        EVChargerUDP: The initialized UDP client
    """
    global udp_client
    udp_client = EVChargerUDP(target_ip, target_port, local_port)
    
    # Define a simple response handler function
    def handle_parameter_response(values, addr):
        print(f"Parameter response from {addr}: {values}")
        # Here you could update UI elements or other application state
        # based on the received values
    
    # Register the handler
    udp_client.register_response_callback(handle_parameter_response)
    
    return udp_client

def get_udp_client():
    """
    Get the global UDP client instance.
    
    Returns:
        EVChargerUDP: The UDP client, or None if not initialized
    """
    return udp_client