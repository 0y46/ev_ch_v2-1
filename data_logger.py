# data_logger.py
# This file provides functionality for logging data from the EV charging system

import os
import csv
import time
from datetime import datetime
import pandas as pd

class DataLogger:
    def __init__(self, log_dir="logs"):
        """Initialize data logger with specified directory"""
        # Create log directory if it doesn't exist
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        self.current_file = None
        self.writer = None
        self.file_handle = None
        self.is_logging = False
        
        # Define column headers for the log file
        self.headers = [
            "Timestamp", 
            "PV_Power", "EV_Power", "Battery_Power", "V_DC",
            "EV_Voltage", "EV_SoC", "Demand_Response", "V2G",
            "Vg_RMS", "Ig_RMS", "Frequency", "THD", "Power_Factor",
            "Active_Power", "Reactive_Power"
        ]
    
    def start_logging(self):
        """Start logging data to a new CSV file"""
        if self.is_logging:
            return
        
        # Create a new file with timestamp in name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_file = os.path.join(self.log_dir, f"ev_data_{timestamp}.csv")
        
        # Open file and initialize CSV writer
        self.file_handle = open(self.current_file, 'w', newline='')
        self.writer = csv.writer(self.file_handle)
        
        # Write header row
        self.writer.writerow(self.headers)
        self.is_logging = True
        print(f"Logging started: {self.current_file}")
        
        return self.current_file
    
    def log_data(self, data_simulator):
        """Log current data from the simulator to CSV file"""
        if not self.is_logging:
            return False
        
        # Get current data from simulator
        table_data = data_simulator.get_table_data()
        gauge_data = data_simulator.get_gauge_data()
        
        # Prepare row data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        row = [
            timestamp,
            # Charging settings data
            table_data['charging_setting']['PV power'],
            table_data['charging_setting']['EV power'],
            table_data['charging_setting']['Battery power'],
            table_data['charging_setting']['V_dc'],
            # EV charging settings data
            table_data['ev_charging_setting']['EV voltage'],
            table_data['ev_charging_setting']['EV SoC'],
            "On" if table_data['ev_charging_setting']['Demand Response'] else "Off",
            "On" if table_data['ev_charging_setting']['V2G'] else "Off",
            # Grid settings data
            table_data['grid_settings']['Vg_rms'],
            table_data['grid_settings']['Ig_rms'],
            table_data['grid_settings']['Frequency'],
            table_data['grid_settings']['THD'],
            table_data['grid_settings']['Power factor'],
            # Gauge data
            gauge_data['active_power'],
            gauge_data['reactive_power']
        ]
        
        # Write row to CSV
        self.writer.writerow(row)
        self.file_handle.flush()  # Ensure data is written immediately
        return True
    
    def stop_logging(self):
        """Stop logging and close the current file"""
        if not self.is_logging:
            return
        
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None
            self.writer = None
        
        self.is_logging = False
        print(f"Logging stopped: {self.current_file}")
        
        return self.current_file
    
    def get_logging_status(self):
        """Return current logging status"""
        return {
            "is_logging": self.is_logging,
            "current_file": self.current_file
        }
    
    def convert_to_mysql(self, csv_file=None):
        """
        This is a placeholder function that demonstrates how
        you would convert the CSV data to MySQL in the future.
        """
        # For future implementation:
        # 1. Import mysql.connector
        # 2. Establish connection to MySQL server
        # 3. Create table if not exists
        # 4. Read CSV data
        # 5. Insert data into MySQL table
        
        print("MySQL conversion functionality will be implemented later.")
        print("To implement this functionality:")
        print("1. Install mysql-connector-python package")
        print("2. Setup MySQL server on Raspberry Pi")
        print("3. Create database and table")
        print("4. Update this function to connect and insert data")
        
        # Example code (not functional until MySQL is set up):
        """
        import mysql.connector
        
        # Connect to MySQL
        cnx = mysql.connector.connect(
            host="localhost",
            user="ev_user",
            password="your_password",
            database="ev_charging_db"
        )
        cursor = cnx.cursor()
        
        # Read the CSV file
        df = pd.read_csv(csv_file)
        
        # Insert each row into MySQL
        for _, row in df.iterrows():
            query = "INSERT INTO ev_data VALUES (%s, %s, %s, ...)"
            cursor.execute(query, tuple(row))
        
        cnx.commit()
        cursor.close()
        cnx.close()
        """