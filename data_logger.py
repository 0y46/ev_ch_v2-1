# data_logger.py
# This module provides comprehensive data logging functionality for the EV Charging Station.
# It supports both processed data logging for dashboard visualization and 
# raw data logging to capture the exact UDP packets received from hardware.

import os
import csv
import time
from datetime import datetime
import pandas as pd

class DataLogger:
    """
    Data Logger for EV Charging Station Monitor.
    
    This class manages the logging of data from the EV charging system,
    supporting both processed data for dashboard visualization and raw
    data exactly as received from the hardware via UDP.
    
    The logger creates two types of log files:
    1. Processed data: Contains formatted data after processing by the application.
       Used primarily for dashboard visualization and analysis.
    2. Raw data: Contains the exact data as received from the UDP hardware interface.
       Used for debugging and detailed analysis of the communication protocol.
       
    Attributes:
        log_dir (str): Directory where log files will be stored
        raw_log_dir (str): Subdirectory for raw data logs
        current_file (str): Path to the current processed data log file
        raw_file (str): Path to the current raw data log file
        is_logging (bool): Flag indicating if logging is currently active
    """
    
    def __init__(self, log_dir="logs"):
        """
        Initialize the data logger with the specified directory structure.
        
        Creates the log directory and raw logs subdirectory if they don't exist.
        Sets up the file structures and column headers for both processed and raw data.
        
        Parameters:
        -----------
        log_dir : str
            Directory path where log files will be stored. Created if it doesn't exist.
            Default is "logs" in the current working directory.
        """
        # Create main log directory if it doesn't exist
        self.log_dir = log_dir
        try:
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
                print(f"Created log directory: {log_dir}")
        except Exception as e:
            print(f"Warning: Could not create log directory {log_dir}: {e}")
            self.log_dir = "."  # Fallback to current directory if creation fails
        
        # Create raw logs subdirectory
        self.raw_log_dir = os.path.join(log_dir, "raw")
        try:
            if not os.path.exists(self.raw_log_dir):
                os.makedirs(self.raw_log_dir)
                print(f"Created raw log directory: {self.raw_log_dir}")
        except Exception as e:
            print(f"Warning: Could not create raw log directory: {e}")
            self.raw_log_dir = self.log_dir  # Fallback to main log directory
        
        # Initialize file handles and writers for processed data
        self.current_file = None
        self.writer = None
        self.file_handle = None
        
        # Initialize file handles and writers for raw data
        self.raw_file = None
        self.raw_writer = None
        self.raw_file_handle = None
        
        # Logging state
        self.is_logging = False
        self._raw_packet_count = 0  # Counter for managing periodic file flushes
        
        # Define column headers for processed data log file
        # These headers match the processed data format used by the dashboard
        self.headers = [
            "Timestamp",                 # Date and time of the log entry
            "PV_Power",                  # Photovoltaic power in watts
            "EV_Power",                  # Electric vehicle power in watts
            "Battery_Power",             # Battery power in watts
            "V_DC",                      # DC link voltage in volts
            "EV_Voltage",                # Electric vehicle voltage in volts
            "EV_SoC",                    # Electric vehicle state of charge in percentage
            "Demand_Response",           # Demand response setting ("On" or "Off")
            "V2G",                       # Vehicle-to-Grid setting ("On" or "Off")
            "Vg_RMS",                    # Grid voltage RMS value in volts
            "Ig_RMS",                    # Grid current RMS value in amperes
            "Frequency",                 # Grid frequency in Hz
            "THD",                       # Total Harmonic Distortion in percentage
            "Power_Factor",              # Power factor (0 to 1)
            "Active_Power",              # Active power in watts
            "Reactive_Power"             # Reactive power in VAR
        ]
        
        # Define column headers for raw data log file
        # These match exactly the format of the raw UDP packets from the hardware
        self.raw_headers = [
            "Timestamp",                 # Date and time when the packet was received
            "Source_IP",                 # IP address of the packet source
            "Source_Port",               # Port number of the packet source
            "Vd",                        # Grid Voltage (V)
            "Id",                        # Grid Current (A)
            "Vdc",                       # DC Link Voltage (V)
            "Vev",                       # EV Voltage (V)
            "Vpv",                       # PV Voltage (V)
            "Iev",                       # EV Current (A)
            "Ipv",                       # PV Current (A)
            "Ppv",                       # PV Power (W)
            "Pev",                       # EV Power (W)
            "Pbattery",                  # Battery Power (W)
            "Pg",                        # Grid Active Power (W)
            "Qg",                        # Grid Reactive Power (VAR)
            "PF",                        # Power Factor
            "Fg",                        # Grid Frequency (Hz)
            "THD",                       # Total Harmonic Distortion (%)
            "S1",                        # PV Status (0=Off, 1=Standby, 2=Active, 3=Fault)
            "S2",                        # EV Status (0=Off, 1=Standby, 2=Active, 3=Fault)
            "S3",                        # Grid Status (0=Off, 1=Standby, 2=Active, 3=Fault)
            "S4",                        # Battery Status (0=Off, 1=Standby, 2=Active, 3=Fault)
            "SoC_battery",               # Battery State of Charge (%)
            "SoC_EV"                     # EV State of Charge (%)
        ]
        
        print(f"DataLogger initialized. Logs will be saved to: {self.log_dir}")
        print(f"Raw packet logs will be saved to: {self.raw_log_dir}")
    
    def start_logging(self):
        """
        Start logging data to new CSV files.
        
        Creates two new files with timestamp-based names:
        1. A processed data file in the main logs directory
        2. A raw data file in the raw logs subdirectory
        
        Both files are initialized with their respective headers.
        
        Returns:
        --------
        str or None
            Path to the created processed log file, or None if an error occurred.
        """
        # Skip if already logging
        if self.is_logging:
            print("Logging is already active")
            return self.current_file
        
        try:
            # Create timestamp for unique filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Define file paths for both log types
            self.current_file = os.path.join(self.log_dir, f"ev_data_{timestamp}.csv")
            self.raw_file = os.path.join(self.raw_log_dir, f"raw_data_{timestamp}.csv")
            
            # Open file and initialize CSV writer for processed data
            self.file_handle = open(self.current_file, 'w', newline='')
            self.writer = csv.writer(self.file_handle)
            
            # Write header row for processed data
            self.writer.writerow(self.headers)
            
            # Open file and initialize CSV writer for raw data
            self.raw_file_handle = open(self.raw_file, 'w', newline='')
            self.raw_writer = csv.writer(self.raw_file_handle)
            
            # Write header row for raw data
            self.raw_writer.writerow(self.raw_headers)
            
            # Initialize counters
            self._raw_packet_count = 0
            
            # Set logging state to active
            self.is_logging = True
            
            print(f"Logging started: {self.current_file}")
            print(f"Raw data logging started: {self.raw_file}")
            
            return self.current_file
            
        except Exception as e:
            print(f"Error starting logging: {e}")
            
            # Clean up any open files
            self._cleanup_files()
            
            # Reset state
            self.is_logging = False
            return None
    
    def _cleanup_files(self):
        """
        Internal helper method to safely close any open file handles.
        Used during error handling and when stopping logging.
        """
        # Close processed data file if open
        if self.file_handle:
            try:
                self.file_handle.close()
            except Exception as e:
                print(f"Warning: Error closing processed data file: {e}")
            finally:
                self.file_handle = None
                self.writer = None
        
        # Close raw data file if open
        if self.raw_file_handle:
            try:
                self.raw_file_handle.close()
            except Exception as e:
                print(f"Warning: Error closing raw data file: {e}")
            finally:
                self.raw_file_handle = None
                self.raw_writer = None
    
    def log_data(self, data_source):
        """
        Log processed data to CSV file.
        
        This method logs processed data from either a data simulator
        or the unified UDP handler to the processed data log file.
        
        Parameters:
        -----------
        data_source : object
            Either a DataSimulator instance or UnifiedUDPHandler instance
            that provides formatted data for logging
            
        Returns:
        --------
        bool
            True if logging was successful, False otherwise.
        """
        if not self.is_logging:
            return False
        
        try:
            # Check if we're dealing with a simulator or unified UDP handler
            if hasattr(data_source, 'get_table_data') and callable(data_source.get_table_data):
                # Get data from simulator
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
                # Get data from unified UDP handler
                latest_data = data_source.get_latest_data()
                
                # Format timestamp with milliseconds
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                
                # For boolean fields like Demand Response and V2G, derive from power values
                # (since raw UDP data doesn't include these directly)
                demand_response = "On"  # Default to "On" for now
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
            
            # Write row to processed data CSV
            self.writer.writerow(row)
            self.file_handle.flush()  # Ensure data is written immediately
            return True
            
        except Exception as e:
            print(f"Error logging processed data: {e}")
            return False
    
    def log_raw_packet(self, data_str, source_addr=None):
        """
        Log a raw UDP packet exactly as received from the hardware.
        
        This method logs the raw data packet without any processing,
        preserving the exact format as received from the hardware.
        
        Parameters:
        -----------
        data_str : str
            The raw packet data as a CSV-formatted string
            Format expected: Vd,Id,Vdc,Vev,Vpv,Iev,Ipv,Ppv,Pev,Pbattery,Pg,Qg,PF,Fg,THD,s1,s2,s3,s4,SoC_battery,SoC_EV
            
        source_addr : tuple or None
            The source address as (ip, port) if available, or None if not known
            
        Returns:
        --------
        bool
            True if logging was successful, False otherwise.
        """
        # Skip if not logging or if raw file is not open
        if not self.is_logging or not self.raw_file_handle:
            return False
        
        try:
            # Get current timestamp with millisecond precision
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
            # Parse source address information
            if source_addr:
                source_ip = source_addr[0]
                source_port = source_addr[1]
            else:
                source_ip = "unknown"
                source_port = 0
                
            # Parse the raw data string into individual values
            values = data_str.split(',')
            
            # Prepare the row data starting with timestamp and source
            row = [timestamp, source_ip, source_port]
            
            # Add all values from the data packet
            # If the packet has fewer values than expected (21), pad with empty strings
            # Expected format: Vd,Id,Vdc,Vev,Vpv,Iev,Ipv,Ppv,Pev,Pbattery,Pg,Qg,PF,Fg,THD,s1,s2,s3,s4,SoC_battery,SoC_EV
            expected_values = 21
            row.extend(values + [''] * (expected_values - min(len(values), expected_values)))
            
            # Write to CSV
            self.raw_writer.writerow(row)
            
            # Increment packet counter
            self._raw_packet_count += 1
            
            # Flush to disk periodically (every 10 packets)
            # This balances immediate visibility with performance
            if self._raw_packet_count % 10 == 0:
                self.raw_file_handle.flush()
                
            return True
            
        except Exception as e:
            print(f"Error logging raw packet: {e}")
            return False
    
    def stop_logging(self):
        """
        Stop logging and close all log files.
        
        Safely flushes and closes both the processed data and raw data log files,
        ensuring all data is properly written to disk before closing.
        
        Returns:
        --------
        str or None
            Path to the closed processed data log file, or None if no file was open.
        """
        # Check if logging is active
        if not self.is_logging:
            print("No active logging to stop")
            return None
        
        # Save file paths for return value
        processed_file_path = self.current_file
        raw_file_path = self.raw_file
        
        try:
            # Ensure all data is flushed to disk
            if self.file_handle:
                self.file_handle.flush()
            if self.raw_file_handle:
                self.raw_file_handle.flush()
                
            # Close all file handles
            self._cleanup_files()
            
            # Reset file paths
            self.current_file = None
            self.raw_file = None
            
            # Reset logging state
            self.is_logging = False
            self._raw_packet_count = 0
            
            print(f"Logging stopped: {processed_file_path}")
            print(f"Raw data logging stopped: {raw_file_path}")
            
            return processed_file_path
            
        except Exception as e:
            print(f"Error stopping logging: {e}")
            
            # Force cleanup even if there was an error
            self._cleanup_files()
            self.is_logging = False
            self._raw_packet_count = 0
            
            return processed_file_path
    
    def get_logging_status(self):
        """
        Return current logging status information.
        
        Returns a dictionary containing the current state of the logger,
        including whether logging is active and the paths to log files.
        
        Returns:
        --------
        dict
            Dictionary with the following keys:
            - is_logging: bool - True if logging is active
            - current_file: str - Path to processed data file
            - raw_file: str - Path to raw data file
            - raw_packet_count: int - Number of raw packets logged
        """
        return {
            "is_logging": self.is_logging,
            "current_file": self.current_file,
            "raw_file": self.raw_file,
            "raw_packet_count": getattr(self, '_raw_packet_count', 0)
        }
    
    def generate_report(self, file_path=None):
        """
        Generate a simple analysis report from the logged data.
        
        Reads either the specified log file or the most recent log file
        and generates statistics about power flows, averages, etc.
        
        Parameters:
        -----------
        file_path : str or None
            Path to the log file to analyze. If None, uses the most recent log file.
            
        Returns:
        --------
        dict or None
            Dictionary containing analysis results, or None if analysis failed.
        """
        if file_path is None:
            if self.is_logging:
                print("Cannot generate report while logging is active")
                return None
            
            # Find most recent log file
            try:
                log_files = [f for f in os.listdir(self.log_dir) 
                            if f.startswith("ev_data_") and f.endswith(".csv")]
                if not log_files:
                    print("No log files found")
                    return None
                
                # Sort by modification time (most recent first)
                log_files.sort(key=lambda x: os.path.getmtime(os.path.join(self.log_dir, x)), 
                             reverse=True)
                file_path = os.path.join(self.log_dir, log_files[0])
            except Exception as e:
                print(f"Error finding log files: {e}")
                return None
        
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
    
    def analyze_raw_data(self, raw_file_path=None):
        """
        Analyze raw data logs to extract communication statistics.
        
        Reads a raw data log file and generates statistics about
        packet rates, value distributions, etc.
        
        Parameters:
        -----------
        raw_file_path : str or None
            Path to the raw log file to analyze. If None, uses the most recent raw log file.
            
        Returns:
        --------
        dict or None
            Dictionary containing analysis results, or None if analysis failed.
        """
        if raw_file_path is None:
            if self.is_logging:
                print("Cannot analyze raw logs while logging is active")
                return None
            
            # Find most recent raw log file
            try:
                raw_log_files = [f for f in os.listdir(self.raw_log_dir) 
                                if f.startswith("raw_data_") and f.endswith(".csv")]
                if not raw_log_files:
                    print("No raw log files found")
                    return None
                
                # Sort by modification time (most recent first)
                raw_log_files.sort(key=lambda x: os.path.getmtime(os.path.join(self.raw_log_dir, x)), 
                                  reverse=True)
                raw_file_path = os.path.join(self.raw_log_dir, raw_log_files[0])
            except Exception as e:
                print(f"Error finding raw log files: {e}")
                return None
        
        try:
            # Read the raw data
            df = pd.read_csv(raw_file_path)
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            
            # Convert numeric columns
            numeric_cols = ['Vd', 'Id', 'Vdc', 'Vev', 'Vpv', 'Iev', 'Ipv', 
                           'Ppv', 'Pev', 'Pbattery', 'Pg', 'Qg', 'PF', 'Fg', 'THD',
                           'SoC_battery', 'SoC_EV']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Calculate statistics
            stats = {
                "file_path": raw_file_path,
                "start_time": df['Timestamp'].min().strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": df['Timestamp'].max().strftime("%Y-%m-%d %H:%M:%S"),
                "duration_seconds": (df['Timestamp'].max() - df['Timestamp'].min()).total_seconds(),
                "total_packets": len(df),
                "packet_rate": len(df) / max(1, (df['Timestamp'].max() - df['Timestamp'].min()).total_seconds()),
                "source_ips": df['Source_IP'].unique().tolist(),
                "average_values": {col: df[col].mean() for col in numeric_cols if col in df.columns},
                "max_values": {col: df[col].max() for col in numeric_cols if col in df.columns},
                "min_values": {col: df[col].min() for col in numeric_cols if col in df.columns}
            }
            
            # Print a summary
            print(f"\nRaw Data Analysis for: {raw_file_path}")
            print(f"Period: {stats['start_time']} to {stats['end_time']} ({stats['duration_seconds']:.2f} seconds)")
            print(f"Packets: {stats['total_packets']} ({stats['packet_rate']:.2f} packets/second)")
            print(f"Source IPs: {', '.join(stats['source_ips'])}")
            
            return stats
            
        except Exception as e:
            print(f"Error analyzing raw data: {e}")
            return None
    
    def convert_to_mysql(self, csv_file=None):
        """
        Placeholder function for future MySQL database integration.
        
        This function demonstrates how you would convert the CSV data 
        to a MySQL database in the future.
        
        Parameters:
        -----------
        csv_file : str or None
            Path to the CSV file to convert to MySQL, or None to use the most recent log.
        """
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