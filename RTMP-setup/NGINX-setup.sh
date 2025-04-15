#!/bin/bash

# Nginx Installation and Setup Script for Ubuntu 22.04+

echo "=== Nginx Installation and Configuration ==="

# Step 1: Install Nginx
echo -e "\n[1/4] Installing Nginx..."
sudo apt update
sudo apt install -y nginx

# Step 2: Configure Firewall with profile selection
echo -e "\n[2/4] Configuring UFW Firewall..."

# List Nginx-related profiles
mapfile -t profile_array < <(sudo ufw app list | grep -i nginx)

if [ ${#profile_array[@]} -eq 0 ]; then
    echo "No Nginx profiles found in UFW."
else
    echo "Available UFW Nginx profiles:"
    for i in "${!profile_array[@]}"; do
        echo "  [$((i+1))] ${profile_array[$i]}"
    done

    read -p "Enter your choice(s) (e.g., '1 3', leave blank to skip): " choice
    for index in $choice; do
        selected="${profile_array[$((index-1))]}"
        if [ -n "$selected" ]; then
            echo "Allowing UFW profile: $selected"
            sudo ufw allow "$selected"
        fi
    done
fi

echo -e "\nCurrent UFW Rules for Nginx:"
sudo ufw status | grep -i nginx || echo "No rules set yet."

# Step 3: Verify Installation
echo -e "\n[3/4] Verifying Nginx Installation..."
sudo systemctl is-active --quiet nginx && echo "Nginx is running." || echo "Nginx is not running."
sudo systemctl status nginx --no-pager --lines=0

# Get external IP or fallback to local
SERVER_IP=$(hostname -I | awk '{print $1}')
[[ -z "$SERVER_IP" ]] && SERVER_IP="localhost"

echo -e "\nYou should be able to access Nginx at:"
echo "  → http://$SERVER_IP OR http://localhost"

# Step 4: Management Instructions
echo -e "[4/4] Nginx Management Commands:"
cat << EOF

To manage the Nginx service:
  Start:         sudo systemctl start nginx
  Stop:          sudo systemctl stop nginx
  Restart:       sudo systemctl restart nginx
  Reload config: sudo systemctl reload nginx
  Enable:        sudo systemctl enable nginx
  Disable:       sudo systemctl disable nginx

To check status:
  sudo systemctl status nginx

To test configuration:
  sudo nginx -t

EOF

echo "=== Nginx Setup Complete ==="
