#!/bin/bash

set -e  # Exit on error
set -x  # Print commands

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo"
    exit 1
fi

# Get the username of the person running sudo
USER_NAME=${SUDO_USER:-$(logname)}

# 1. Install essential dependencies
echo "Installing dependencies..."
apt-get update
apt-get install -y \
    python3-pip \
    libnss3-tools \
    curl

# 2. Install Python packages
pip3 install fastapi uvicorn pymavlink websockets

# 3. Install mkcert (for HTTPS)
echo "Setting up mkcert..."
curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
chmod +x mkcert-v*-linux-amd64
mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert
mkcert -install

# 4. Create certs directory and generate certificates as non-root user
sudo -u "$USER_NAME" bash <<EOF
set -e
mkdir -p certs
cd certs
mkcert localhost \$(hostname) 127.0.0.1 ::1
EOF

# 5. Allow port through firewall (if ufw is active)
if command -v ufw &> /dev/null; then
    ufw allow 8000/tcp
fi

# 6. Done
echo ""
echo "========================================"
echo "Setup complete!"
echo ""
echo "Run with:"
echo "  python3 telemetry-server.py"
echo "========================================"

