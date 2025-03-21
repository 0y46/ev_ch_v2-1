"""
Simple UDP data sender for testing the EV Charging Station Monitor.
Sends valid CSV data in the expected 21-value format.
"""

import socket
import time
import random
import argparse

def send_test_data(ip='127.0.0.1', port=5000, count=20, interval=0.5):
    """Send test UDP packets with valid 21-value format."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"Sending {count} test packets to {ip}:{port}...")
    
    try:
        for i in range(count):
            # Generate valid test data (21 values)
            # Format: Vd,Id,Vdc,Vev,Vpv,Iev,Ipv,Ppv,Pev,Pbattery,Pg,Qg,PF,Fg,THD,s1,s2,s3,s4,SoC_battery,SoC_EV
            vd = 220.0 + random.uniform(-5, 5)
            id_val = 10.0 + random.uniform(-1, 1)
            vdc = 400.0 + random.uniform(-3, 3)
            vev = 350.0 + random.uniform(-2, 2)
            vpv = 380.0 + random.uniform(-3, 3)
            iev = 15.0 + random.uniform(-0.5, 0.5)
            ipv = 8.0 + random.uniform(-0.4, 0.4)
            ppv = vpv * ipv
            pev = vev * iev * -1
            pbattery = 500.0 + random.uniform(-100, 100)
            pg = 1000.0 + random.uniform(-50, 50)
            qg = 200.0 + random.uniform(-20, 20)
            pf = 0.95 + random.uniform(-0.05, 0.05)
            fg = 50.0 + random.uniform(-0.1, 0.1)
            thd = 3.0 + random.uniform(-0.5, 0.5)
            s1 = 2  # Active
            s2 = 2  # Active
            s3 = 2  # Active
            s4 = 2  # Active
            soc_battery = 60.0 + i/10
            soc_ev = 45.0 + i/10
            
            # Format as CSV
            data = f"{vd:.2f},{id_val:.2f},{vdc:.2f},{vev:.2f},{vpv:.2f},{iev:.2f},{ipv:.2f},{ppv:.2f},{pev:.2f}," + \
                   f"{pbattery:.2f},{pg:.2f},{qg:.2f},{pf:.2f},{fg:.2f},{thd:.2f}," + \
                   f"{s1},{s2},{s3},{s4},{soc_battery:.2f},{soc_ev:.2f}"
            
            # Send the data
            sock.sendto(data.encode('utf-8'), (ip, port))
            print(f"Sent packet {i+1}/{count}: {data[:40]}...")
            
            # Wait before sending next packet
            time.sleep(interval)
            
        print(f"All {count} packets sent successfully")
        
    except Exception as e:
        print(f"Error sending data: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Send test UDP data packets')
    parser.add_argument('--ip', default='127.0.0.1', help='Target IP address')
    parser.add_argument('--port', type=int, default=5000, help='Target port')
    parser.add_argument('--count', type=int, default=20, help='Number of packets to send')
    parser.add_argument('--interval', type=float, default=0.5, help='Time between packets (seconds)')
    args = parser.parse_args()
    
    send_test_data(args.ip, args.port, args.count, args.interval)