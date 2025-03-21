"""
Test script to receive and display parameter updates.
This can be used to verify that parameter updates are being sent correctly.
"""

import socket
import time

def receive_parameter_updates(ip="0.0.0.0", port=5001, duration=60):
    """
    Listen for parameter updates on the specified IP and port.
    
    Args:
        ip: The IP address to bind to (default: 0.0.0.0)
        port: The port to listen on (default: 5001)
        duration: How long to listen in seconds (default: 60)
    """
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(1.0)  # 1 second timeout
    
    try:
        # Bind the socket to the specified IP and port
        sock.bind((ip, port))
        print(f"Listening for parameter updates on {ip}:{port} for {duration} seconds...")
        
        start_time = time.time()
        count = 0
        
        while time.time() - start_time < duration:
            try:
                # Receive data
                data, addr = sock.recvfrom(1024)
                count += 1
                
                # Decode and print the data
                message = data.decode('utf-8')
                print(f"Received from {addr}: {message}")
                
                # Parse as CSV
                parts = message.split(',')
                if len(parts) >= 2 and parts[0] == "PARAM":
                    table_id = parts[1]
                    print(f"  Table ID: {table_id}")
                    
                    # Parse parameters (name-value pairs)
                    for i in range(2, len(parts)-1, 2):
                        if i+1 < len(parts):
                            param_name = parts[i]
                            param_value = parts[i+1]
                            print(f"  {param_name} = {param_value}")
                
            except socket.timeout:
                # This is expected if no data is received within the timeout period
                pass
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()
        print(f"Finished listening. Received {count} parameter updates.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Listen for parameter updates")
    parser.add_argument("--ip", default="0.0.0.0", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=5001, help="Port to listen on")
    parser.add_argument("--duration", type=int, default=60, help="Duration to listen in seconds")
    
    args = parser.parse_args()
    receive_parameter_updates(args.ip, args.port, args.duration)