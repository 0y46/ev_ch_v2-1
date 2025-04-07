#!/bin/bash

# Activate virtual environment
source /home/qeeri/Desktop/ev_ch_v2/venv_system/bin/activate

# Navigate to the project directory
cd /home/qeeri/Desktop/ev_ch_v2

# Start the application in fullscreen mode
python main.py --real-data --udp-ip 127.0.0.1 --udp-port 8888 --fullscreen >> /home/qeeri/Desktop/ev_ch_v2/app.log 2>&1