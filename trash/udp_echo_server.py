"""
UDP Echo Server for testing the EV charging application.
This mimics your mentor's Node.js server functionality.
"""

import socket
import time
import threading
import random

class EVServerEmulator:
    """
    Emulates the UDP server that your mentor is implementing in Node.js.
    This server receives parameter updates and responds with reference values.
    """
    
    def __init__(self, ip="0.0.0.0", port=5000):
        """
        Initialize the server emulator.
        
        Args:
            ip: IP address to bind to (0.0.0.0 means all interfaces)
            port: Port to listen on
        """
        self.ip = ip
        self.port = port
        self.socket = None
        self.is_running = False
        self.server_thread = None
        
        # Reference values (similar to your mentor's Vdc_ref, Pev_ref, Ppv_ref)
        self.reference_values = {
            "Vdc_ref": 400.0,
            "Pev_ref": -4000.0,
            "Ppv_ref": 2000.0
        }
    
    def start(self):
        """Start the server emulator."""
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.ip, self.port))
            self.socket.settimeout(0.1)  # 100ms timeout
            
            print(f"UDP server emulator listening on {self.ip}:{self.port}")
            
            # Start server thread
            self.is_running = True
            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.server_thread.start()
            
            return True
            
        except Exception as e:
            print(f"Error starting server emulator: {e}")
            if self.socket:
                self.socket.close()
                self.socket = None
            return False
    
    def _server_loop(self):
        """Main server loop for receiving and responding to UDP messages."""
        while self.is_running and self.socket:
            try:
                # Receive data
                data, addr = self.socket.recvfrom(1024)
                
                if data:
                    # Process the received message
                    message = data.decode('utf-8').strip()
                    print(f"Server received from {addr}: {message}")
                    
                    # Check if this is a parameter update (PARAM message)
                    if message.startswith("PARAM"):
                        parts = message.split(',')
                        if len(parts) >= 2:
                            table_id = parts[1]
                            print(f"Parameter update for table {table_id}")
                            
                            # Parse parameters (similar to your mentor's JavaScript)
                            params = {}
                            for i in range(2, len(parts)-1, 2):
                                if i+1 < len(parts):
                                    param_name = parts[i]
                                    param_value = parts[i+1]
                                    params[param_name] = param_value
                                    print(f"  {param_name} = {param_value}")
                            
                            # Process specific table updates
                            # This mimics your mentor's processing logic
                            if table_id == "1":  # Grid settings
                                # Update reference values based on the received parameters
                                pass  # Add your logic here
                            elif table_id == "2":  # Charging setting
                                # Example: If PV power is set, update Ppv_ref
                                if "pv_power" in params:
                                    self.reference_values["Ppv_ref"] = float(params["pv_power"])
                            elif table_id == "3":  # EV charging setting
                                # Example: If EV power is set, update Pev_ref
                                if "ev_power" in params:
                                    self.reference_values["Pev_ref"] = float(params["ev_power"])
                            
                            # Send response with updated reference values (like your mentor's code)
                            # Format: Vdc_ref,Pev_ref,Ppv_ref
                            response = f"{self.reference_values['Vdc_ref']},{self.reference_values['Pev_ref']},{self.reference_values['Ppv_ref']}"
                            self.socket.sendto(response.encode('utf-8'), addr)
                            print(f"Server sent response: {response}")
                    
                    # If not a PARAM message, treat as a regular data packet
                    # (this would be the data your mentor processes and stores in the database)
                    else:
                        # Regular data packet
                        parts = message.split(',')
                        if len(parts) >= 9:  # Similar check as your mentor's code
                            # In your mentor's code, this would update the database
                            # For testing, just log that we received it
                            print(f"Received regular data packet with {len(parts)} values")
                            
                            # Send reference values as response (like your mentor's code)
                            # Slightly vary the values to simulate changes
                            self.reference_values["Vdc_ref"] += random.uniform(-2, 2)
                            response = f"{self.reference_values['Vdc_ref']},{self.reference_values['Pev_ref']},{self.reference_values['Ppv_ref']}"
                            self.socket.sendto(response.encode('utf-8'), addr)
                            print(f"Server sent response: {response}")
            
            except socket.timeout:
                # This is expected if no data is received within the timeout period
                pass
            except Exception as e:
                if self.is_running:  # Only log errors if we're supposed to be running
                    print(f"Error in server loop: {e}")
                    time.sleep(0.1)  # Prevent tight loop if there's a persistent error
    
    def stop(self):
        """Stop the server emulator."""
        self.is_running = False
        
        # Wait for server thread to terminate
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1.0)
        
        # Close the socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
            
        print("Server emulator stopped")

if __name__ == "__main__":
    # Start the server emulator
    server = EVServerEmulator(port=5000)
    server.start()
    
    print("Press Ctrl+C to stop the server...")
    try:
        # Keep the main thread running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.stop()