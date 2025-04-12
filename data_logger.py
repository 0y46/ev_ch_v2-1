# data_logger.py
# This file provides functionality for logging data from the EV charging system

import os
import csv
import time
from datetime import datetime
import pandas as pd

class DataLogger:
    def __init__(self, log_dir="logs"):
        """
        Initialize data logger with specified directory.
        
        Parameters:
        -----------
        log_dir : str
            Directory where log files will be stored. Created if it doesn't exist.
        """
        # Create log directory if it doesn't exist
        self.log_dir = log_dir
        try:
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
                print(f"Created log directory: {log_dir}")
        except Exception as e:
            print(f"Warning: Could not create log directory {log_dir}: {e}")
            self.log_dir = "."  # Fallback to current directory
        
        self.current_file = None
        self.writer = None
        self.file_handle = None
        self.is_logging = False
        self._row_count = 0  # Counter for flushing optimization
        
        # Define column headers for the log file
        self.headers = [
            "Timestamp", 
            "PV_Power", "EV_Power", "Battery_Power", "V_DC",
            "EV_Voltage", "EV_SoC", "Demand_Response", "V2G",
            "Vg_RMS", "Ig_RMS", "Frequency", "THD", "Power_Factor",
            "Active_Power", "Reactive_Power"
        ]
        
        print(f"DataLogger initialized. Logs will be saved to: {self.log_dir}")
    
    def start_logging(self):
        """
        Start logging data to a new CSV file.
        
        Creates a new CSV file with a timestamp-based name in the configured logs directory
        and initializes it with header columns. Sets up the file for writing log entries.
        
        Returns:
        --------
        str or None
            Path to the created log file, or None if an error occurred.
        """
        if self.is_logging:
            print("Logging is already active")
            return self.current_file
        
        try:
            # Create a new file with timestamp in name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_file = os.path.join(self.log_dir, f"ev_data_{timestamp}.csv")
            
            # Open file and initialize CSV writer
            self.file_handle = open(self.current_file, 'w', newline='')
            self.writer = csv.writer(self.file_handle)
            
            # Write header row
            self.writer.writerow(self.headers)
            self.is_logging = True
            self._row_count = 0  # Reset row counter
            print(f"Logging started: {self.current_file}")
            
            return self.current_file
            
        except Exception as e:
            print(f"Error starting logging: {e}")
            # Clean up if necessary
            if self.file_handle:
                try:
                    self.file_handle.close()
                except:
                    pass
                self.file_handle = None
            
            self.writer = None
            self.current_file = None
            self.is_logging = False
            return None
    
    def log_data(self, data_source):
        """
        Log current data to CSV file from either simulator or unified UDP handler.
        
        Parameters:
        -----------
        data_source : object
            Either a DataSimulator instance or UnifiedUDPHandler instance
        
        Returns:
        --------
        bool
            True if logging was successful, False otherwise
        """
        if not self.is_logging:
            return False
        
        try:
            # Check the type of data source we're working with
            if hasattr(data_source, 'get_table_data') and callable(data_source.get_table_data):
                # It's the simulator - use existing method
                table_data = data_source.get_table_data()
                gauge_data = data_source.get_gauge_data()
                
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
                
            elif hasattr(data_source, 'get_latest_data') and callable(data_source.get_latest_data):
                # It's the unified UDP handler - extract data directly
                latest_data = data_source.get_latest_data()
                
                # Format timestamp with milliseconds
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                
                # For boolean fields like Demand Response and V2G, we don't have direct access
                # from the UDP data, so we'll use defaults or derive from power values
                demand_response = "Unknown"  # We don't have this data directly
                v2g = "On" if latest_data.get('ElectricVehicle_Power', 0) > 0 else "Off"  # Positive = discharging = V2G
                
                row = [
                    timestamp,
                    # Charging settings data
                    latest_data.get('PhotoVoltaic_Power', 0),
                    latest_data.get('ElectricVehicle_Power', 0),
                    latest_data.get('Battery_Power', 0),
                    latest_data.get('DCLink_Voltage', 0),
                    # EV charging settings data
                    latest_data.get('ElectricVehicle_Voltage', 0),
                    latest_data.get('EV_SoC', 0),
                    demand_response,
                    v2g,
                    # Grid settings data
                    latest_data.get('Grid_Voltage', 0),
                    latest_data.get('Grid_Current', 0),
                    latest_data.get('Frequency', 50.0),
                    latest_data.get('THD', 0),
                    latest_data.get('Power_Factor', 0.95),
                    # Gauge data equivalent
                    latest_data.get('Grid_Power', 0),
                    latest_data.get('Grid_Reactive_Power', 0)
                ]
            else:
                # Unknown data source type
                print(f"Error: Unsupported data source type: {type(data_source)}")
                return False
            
            # Write row to CSV
            self.writer.writerow(row)
            
            # Flush only occasionally (every 10 rows) to balance performance with reliability
            if self._row_count % 10 == 0:
                self.file_handle.flush()
                
            self._row_count += 1
            return True
            
        except Exception as e:
            print(f"Error logging data: {e}")
            return False
    
    def stop_logging(self):
        """
        Stop logging and close the current file.
        
        Safely closes the active log file and resets internal state.
        Always flushes remaining data before closing to ensure no data is lost.
        
        Returns:
        --------
        str or None
            Path to the closed log file, or None if no file was open.
        """
        if not self.is_logging:
            print("No active logging to stop")
            return None
        
        file_path = self.current_file
        
        try:
            if self.file_handle:
                # Ensure all data is written
                self.file_handle.flush()
                self.file_handle.close()
        except Exception as e:
            print(f"Error closing log file: {e}")
        finally:
            # Reset state even if there was an error
            self.file_handle = None
            self.writer = None
            self.current_file = None
            self.is_logging = False
            self._row_count = 0
            
        print(f"Logging stopped: {file_path}")
        return file_path
    
    def get_logging_status(self):
        """Return current logging status"""
        return {
            "is_logging": self.is_logging,
            "current_file": self.current_file
        }
    
    def log_raw_packet(self, data_str, source_addr=None):
        """
        Log a raw UDP packet for debugging purposes.
        
        Creates or appends to a special debug log file that contains raw packet data.
        This is useful for troubleshooting communication issues.
        
        Parameters:
        -----------
        data_str : str
            The raw packet data as a string
        source_addr : tuple or None
            The source address (ip, port) if available
            
        Returns:
        --------
        bool
            True if logging was successful, False otherwise
        """
        try:
            # Create debug log directory if needed
            debug_dir = os.path.join(self.log_dir, "debug")
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            
            # Create a log filename with today's date
            today = datetime.now().strftime("%Y%m%d")
            debug_file = os.path.join(debug_dir, f"raw_packets_{today}.log")
            
            # Append to the file
            with open(debug_file, 'a') as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                source_info = f" from {source_addr}" if source_addr else ""
                f.write(f"[{timestamp}]{source_info}: {data_str}\n")
            
            return True
        except Exception as e:
            print(f"Error logging raw packet: {e}")
            return False


    def generate_report(self, file_path=None):
        """
        Generate a simple analysis report from the logged data.
        
        This method uses pandas to analyze the logged data and produce
        statistics about power flows, averages, maximums, minimums, etc.
        
        Parameters:
        -----------
        file_path : str or None
            Path to the log file to analyze. If None, uses the most recent log file.
            
        Returns:
        --------
        dict
            Dictionary containing analysis results
        """
        if file_path is None:
            if self.is_logging:
                print("Cannot generate report while logging is active")
                return None
            
            # Find most recent log file
            log_files = [f for f in os.listdir(self.log_dir) 
                        if f.startswith("ev_data_") and f.endswith(".csv")]
            if not log_files:
                print("No log files found")
                return None
            
            # Sort by modification time (most recent first)
            log_files.sort(key=lambda x: os.path.getmtime(os.path.join(self.log_dir, x)), 
                        reverse=True)
            file_path = os.path.join(self.log_dir, log_files[0])
        
        try:
            # Read the data
            df = pd.read_csv(file_path)
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            df.set_index('Timestamp', inplace=True)
            
            # Calculate statistics
            stats = {
                "file_path": file_path,
                "start_time": df.index[0].strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": df.index[-1].strftime("%Y-%m-%d %H:%M:%S"),
                "duration_minutes": (df.index[-1] - df.index[0]).total_seconds() / 60,
                "total_records": len(df),
                "average_power": {
                    "PV_Power": df['PV_Power'].mean(),
                    "EV_Power": df['EV_Power'].mean(),
                    "Battery_Power": df['Battery_Power'].mean(),
                    "Active_Power": df['Active_Power'].mean()
                },
                "max_values": {
                    "PV_Power": df['PV_Power'].max(),
                    "EV_Power": df['EV_Power'].max(),
                    "Battery_Power": df['Battery_Power'].max(),
                    "V_DC": df['V_DC'].max(),
                    "Frequency": df['Frequency'].max()
                },
                "min_values": {
                    "PV_Power": df['PV_Power'].min(),
                    "EV_Power": df['EV_Power'].min(),
                    "Battery_Power": df['Battery_Power'].min(),
                    "V_DC": df['V_DC'].min(),
                    "Frequency": df['Frequency'].min()
                }
            }
            
            # Print a summary
            print(f"\nData Analysis for: {file_path}")
            print(f"Period: {stats['start_time']} to {stats['end_time']} ({stats['duration_minutes']:.2f} minutes)")
            print(f"Records: {stats['total_records']}")
            print("\nAverage Power Values:")
            for k, v in stats['average_power'].items():
                print(f"  {k}: {v:.2f}")
            
            return stats
            
        except Exception as e:
            print(f"Error generating report: {e}")
            return None
        
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