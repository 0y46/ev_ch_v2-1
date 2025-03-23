#!/bin/bash

# Wait longer for desktop environment to fully load
sleep 5

# Make sure display is set
export DISPLAY=:0
export XAUTHORITY=/home/qeeri/.Xauthority

# Force the X server to use hardware acceleration if available
export LIBGL_ALWAYS_HARDWARE=1

# Activate virtual environment with full path
source /home/qeeri/ev_ch/ev_ch_v2/venv_system/bin/activate

# Navigate to the project directory
cd /home/qeeri/ev_ch/ev_ch_v2

# Kill any existing instances
pkill -f "python main.py"

# Clear memory caches to improve performance
sync
echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null

# Start the application in fullscreen mode with higher priority
python main.py --real-data --udp-ip 127.0.0.1 --udp-port 8888 --fullscreen
