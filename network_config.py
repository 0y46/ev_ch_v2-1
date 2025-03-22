"""
Network configuration constants for the EV Charging Station Monitor application.

This module defines standard network parameters used across different components
of the application to ensure consistency and make changes easier.
"""

# Standard network configuration
DEFAULT_SERVER_PORT = 5000  # The port where the hardware/test server listens
DEFAULT_CLIENT_PORT = 0     # 0 means OS will assign an available port (for client binding)
DEFAULT_SERVER_IP = "127.0.0.1"  # Default IP for local testing/development
DEFAULT_BROADCAST_IP = "0.0.0.0"  # For binding to all interfaces when receiving

# UDP packet settings
DEFAULT_BUFFER_SIZE = 1024  # Standard buffer size for UDP packets
DEFAULT_TIMEOUT = 0.1       # Socket timeout in seconds

# Data format constants
CSV_SEPARATOR = ","        # Separator used in UDP message format
PARAM_PREFIX = "PARAM"     # Prefix for parameter update messages
HELLO_MESSAGE = "HELLO"    # Standard hello/handshake message

# Table ID mapping
TABLE_ID_GRID = 1          # Table ID for grid settings
TABLE_ID_CHARGING = 2      # Table ID for charging settings
TABLE_ID_EV = 3            # Table ID for EV charging settings