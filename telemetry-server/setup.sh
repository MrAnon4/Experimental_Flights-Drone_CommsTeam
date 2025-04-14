#!/bin/bash

set -e  # Exit on error
set -x  # Print commands

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo"
    exit 1
fi

# 1. Install essential dependencies
echo "Installing dependencies..."
apt-get update
apt-get install -y python3-pip

# 2. Install Python packages
pip3 install fastapi uvicorn pymavlink websockets

# 3. Firewall permission (if ufw is active)
if command -v ufw &> /dev/null; then
    ufw allow 8000/tcp
fi

# Output information
echo ""
echo "========================================"
echo "HTTP Setup Complete!"
echo ""
echo "Run with:"
echo "  python3 telemetry-server.py"
echo "========================================"
