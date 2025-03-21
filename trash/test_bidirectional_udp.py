"""
Test script for bidirectional UDP communication.
This script demonstrates sending parameter updates and receiving responses.
"""

import sys
import time
from udp_helper import initialize_udp

def test_bidirectional_communication():
    """Test bidirectional UDP communication"""
    
    # Initialize UDP client with your mentor's IP address and port
    # Use the same port for sending and receiving
    udp_client = initialize_udp(target_ip="127.0.0.1", target_port=5000, local_port=5000)
    
    if not udp_client:
        print("Failed to initialize UDP client")
        return
    
    # Define a custom response handler
    def my_response_handler(values, addr):
        print(f"Custom handler received: {values} from {addr}")
        # You could update application state here based on the response
    
    # Register the custom handler
    udp_client.register_response_callback(my_response_handler)
    
    print("\n1. Testing Grid Settings update (table ID: 1):")
    grid_params = {
        "Vg_rms": 230.5,
        "Ig_rms": 12.3,
        "Frequency": 50.2,
        "THD": 2.1,
        "Power factor": 0.98
    }
    udp_client.send_parameter_update("grid_settings", grid_params)
    time.sleep(1)  # Wait for potential response
    
    print("\n2. Testing Charging Setting update (table ID: 2):")
    charging_params = {
        "PV power": 2500.0,
        "EV power": -4500.0,
        "Battery power": 1500.0
    }
    udp_client.send_parameter_update("charging_setting", charging_params)
    time.sleep(1)  # Wait for potential response
    
    print("\n3. Testing EV Charging Setting update (table ID: 3):")
    ev_charging_params = {
        "EV voltage": 60.5,
        "EV SoC": 75.0,
        "Demand Response": True,
        "V2G": False
    }
    udp_client.send_parameter_update("ev_charging_setting", ev_charging_params)
    time.sleep(1)  # Wait for potential response
    
    # Keep running to receive responses
    print("\nWaiting for 10 seconds to receive any responses...")
    try:
        time.sleep(10)
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    
    print("\nTest complete!")
    udp_client.close()

if __name__ == "__main__":
    test_bidirectional_communication()