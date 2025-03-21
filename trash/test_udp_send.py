"""
Test script to verify UDP parameter update sending.
This allows testing the new CSV format for parameter updates.
"""

import sys
import time
from udp_helper import initialize_udp

def test_send_parameter_updates():
    """Test sending parameter updates in CSV format"""
    
    # Initialize UDP client with appropriate target IP and port
    # Replace with your mentor's actual IP and port or use 127.0.0.1 for local testing
    udp_client = initialize_udp(target_ip="127.0.0.1", target_port=5000)
    
    if not udp_client:
        print("Failed to initialize UDP client")
        return
    
    # Test sending grid settings update
    print("\n1. Testing Grid Settings update (table ID: 1):")
    grid_params = {
        "Vg_rms": 230.5,
        "Ig_rms": 12.3,
        "Frequency": 50.2,
        "THD": 2.1,
        "Power factor": 0.98
    }
    udp_client.send_parameter_update("grid_settings", grid_params)
    time.sleep(1)  # Pause to separate messages
    
    # Test sending charging settings update
    print("\n2. Testing Charging Setting update (table ID: 2):")
    charging_params = {
        "PV power": 2500.0,
        "EV power": -4500.0,
        "Battery power": 1500.0
    }
    udp_client.send_parameter_update("charging_setting", charging_params)
    time.sleep(1)
    
    # Test sending EV charging settings update
    print("\n3. Testing EV Charging Setting update (table ID: 3):")
    ev_charging_params = {
        "EV voltage": 60.5,
        "EV SoC": 75.0,
        "Demand Response": True,
        "V2G": False
    }
    udp_client.send_parameter_update("ev_charging_setting", ev_charging_params)
    
    # Try to receive any response (for testing bidirectional communication)
    print("\n4. Testing receive capability (waiting for 2 seconds):")
    udp_client.receive_test(timeout=2.0)
    
    print("\nTest complete!")
    udp_client.close()

if __name__ == "__main__":
    test_send_parameter_updates()