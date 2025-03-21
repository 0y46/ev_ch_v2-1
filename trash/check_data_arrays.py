#!/usr/bin/env python3
"""
Diagnostic script to check UDP client data arrays and verify they're synchronized.
"""

import time
import argparse
from udp_client import UDPClient

def diagnostic_check():
    """Run diagnostic checks on UDP client data collections."""
    
    print("Starting UDP Client diagnostic check...")
    
    # Create UDP client
    client = UDPClient(ip="0.0.0.0", port=5000)
    client.start()
    
    try:
        # Run for 10 seconds
        print("Listening for 10 seconds...")
        time.sleep(10)
        
        # Check data collection lengths
        time_len = len(client.time_history)
        
        # Check key data collections
        grid_v_len = len(client.data_history['Grid_Voltage'])
        grid_i_len = len(client.data_history['Grid_Current'])
        pv_power_len = len(client.data_history['PhotoVoltaic_Power'])
        ev_power_len = len(client.data_history['ElectricVehicle_Power'])
        
        # Check waveform data
        va_len = len(client.waveform_data['Grid_Voltage']['phaseA'])
        ia_len = len(client.waveform_data['Grid_Current']['phaseA'])
        
        # Print results
        print("\nDiagnostic Results:")
        print(f"Timestamp history length: {time_len}")
        print(f"Grid Voltage data length: {grid_v_len}")
        print(f"Grid Current data length: {grid_i_len}")
        print(f"PV Power data length: {pv_power_len}")
        print(f"EV Power data length: {ev_power_len}")
        print(f"Grid Voltage waveform length: {va_len}")
        print(f"Grid Current waveform length: {ia_len}")
        
        # Check for synchronization issues
        if (time_len == grid_v_len == grid_i_len == pv_power_len == 
            ev_power_len == va_len == ia_len):
            print("\n✅ SUCCESS: All data collections are synchronized!")
        else:
            print("\n❌ ERROR: Data collections are NOT synchronized!")
            print("Fix the code to only add timestamps when valid data is processed.")
    
    finally:
        # Stop the client
        client.stop()
        print("\nDiagnostic check complete.")

if __name__ == "__main__":
    diagnostic_check()