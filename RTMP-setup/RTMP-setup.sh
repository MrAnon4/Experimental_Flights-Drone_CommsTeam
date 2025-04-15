#!/bin/bash

# Streamlined Nginx-RTMP Setup Script for Ubuntu 22.04+

# === Prerequisites Check ===
echo "=== Checking Prerequisites ==="
if [ "$(id -u)" -eq 0 ]; then
    echo "ERROR: Do not run as root. Use a non-root user with sudo."
    exit 1
fi

if ! command -v nginx &> /dev/null; then
    echo "ERROR: Nginx is not installed. Please run: sudo apt install nginx"
    exit 1
fi

# === Auto-detect IP addresses ===
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo "Detected LOCAL IP: $LOCAL_IP"

# === Install RTMP Module ===
echo -e "\n=== Installing libnginx-mod-rtmp ==="
sudo apt update && sudo apt install -y libnginx-mod-rtmp

# === Configure Nginx for RTMP ===
echo "Adding RTMP block to nginx.conf..."

read -p "Allow publishing from all IPs? (y/n): " ALLOW_ALL_IPS

sudo tee -a /etc/nginx/nginx.conf > /dev/null <<EOF

rtmp {
    server {
        listen 1935;
        chunk_size 4096;
EOF

if [[ $ALLOW_ALL_IPS =~ ^[Yy]$ ]]; then
    sudo tee -a /etc/nginx/nginx.conf > /dev/null <<EOF
        allow publish all;
EOF
else
    sudo tee -a /etc/nginx/nginx.conf > /dev/null <<EOF
        allow publish 127.0.0.1;
        deny publish all;
EOF
fi

sudo tee -a /etc/nginx/nginx.conf > /dev/null <<EOF

        application live {
            live on;
            record off;
EOF

read -p "Add HLS/DASH support? (y/n): " ADD_HLS_DASH
if [[ $ADD_HLS_DASH =~ ^[Yy]$ ]]; then
    sudo tee -a /etc/nginx/nginx.conf > /dev/null <<EOF
            hls on;
            hls_path /var/www/html/stream/hls;
            hls_fragment 3;
            hls_playlist_length 60;

            dash on;
            dash_path /var/www/html/stream/dash;
EOF
fi

sudo tee -a /etc/nginx/nginx.conf > /dev/null <<EOF
        }
    }
}
EOF

# === Firewall Rules ===
echo -e "\n=== Configuring Firewall ==="
sudo ufw allow 1935/tcp
[[ $ADD_HLS_DASH =~ ^[Yy]$ ]] && sudo ufw allow 8088/tcp

# === Web Interface Setup ===
echo -e "\n=== Setting Up Web Interface ==="
sudo mkdir -p /var/www/html/rtmp
sudo cp /usr/share/doc/libnginx-mod-rtmp/examples/stat.xsl /var/www/html/rtmp/

sudo tee /etc/nginx/sites-available/rtmp > /dev/null <<EOF
server {
    listen 8080;
    server_name localhost;

    location /stat {
        rtmp_stat all;
        rtmp_stat_stylesheet stat.xsl;
    }
    location /stat.xsl {
        root /var/www/html/rtmp;
    }
    location /control {
        rtmp_control all;
    }
EOF

if [[ $ADD_HLS_DASH =~ ^[Yy]$ ]]; then
    sudo mkdir -p /var/www/html/stream
    sudo tee -a /etc/nginx/sites-available/rtmp > /dev/null <<EOF
}

server {
    listen 8088;
    location / {
        add_header Access-Control-Allow-Origin *;
        root /var/www/html/stream;
    }
}

types {
    application/dash+xml mpd;
}
EOF
else
    echo "}" | sudo tee -a /etc/nginx/sites-available/rtmp > /dev/null
fi

# === Activate Configuration ===
echo -e "\n=== Activating Nginx Config ==="
sudo ln -sf /etc/nginx/sites-available/rtmp /etc/nginx/sites-enabled/
sudo systemctl reload nginx.service

# === Summary ===
echo -e "\n=== Setup Complete ==="
echo "RTMP Streaming URL: rtmp://$LOCAL_IP/live OR rtmp://localhost/live"
echo "View Stream via: rtmp://$LOCAL_IP/live/stream_key OR rtmp://localhost/live/stream_key"
[[ $ADD_HLS_DASH =~ ^[Yy]$ ]] && {
    echo "HLS Stream: http://$LOCAL_IP:8088/hls/stream_key.m3u8 OR http://localhost:8088/hls/stream_key.m3u8"
    echo "DASH Stream: http://$LOCAL_IP:8088/dash/stream_key.mpd OR http://localhost:8088/dash/stream_key.mpd"
}
echo "Stats Page: http://localhost:8080/stat"
