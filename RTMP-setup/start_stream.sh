#!/bin/bash

# --- Configuration ---
PROJECT_ID="drone-stream-473321"
BUCKET="raspi-video-stream"
STREAM_DIR="stream"
export GOOGLE_APPLICATION_CREDENTIALS="my-service-account-key.json"

# --- Setup ---
mkdir -p "$STREAM_DIR"

echo "Starting FFmpeg stream simulator..."
echo "Output directory: $STREAM_DIR"
echo "-----------------------------------------"

# --- Check if FFmpeg is installed ---
if ! command -v ffmpeg &> /dev/null; then
    echo "FFmpeg is not installed!"
    echo "Install it using: sudo apt install ffmpeg (Debian/Ubuntu) or brew install ffmpeg (macOS)"
    exit 1
fi

# --- Optional: list video devices ---
# On Linux:
#   v4l2-ctl --list-devices
# On macOS:
#   ffmpeg -f avfoundation -list_devices true -i ""
# Uncomment below if you want to see devices:
# ffmpeg -f avfoundation -list_devices true -i ""

echo "Starting webcam capture..."
# Replace '0' (Linux) or '0' (macOS) with your camera index if needed

# --- Linux (v4l2) example ---
ffmpeg -f v4l2 -framerate 25 -video_size 1280x720 -i /dev/video0 \
  -c:v libx264 -b:v 2M -f hls -hls_time 2 -hls_list_size 5 \
  -hls_flags delete_segments "$STREAM_DIR/playlist.m3u8" &

# --- macOS (avfoundation) alternative ---
# ffmpeg -f avfoundation -framerate 25 -video_size 1280x720 -i "0" \
#   -c:v libx264 -b:v 2M -f hls -hls_time 2 -hls_list_size 5 \
#   -hls_flags delete_segments "$STREAM_DIR/playlist.m3u8" &

# --- Test pattern alternative (no camera needed) ---
# ffmpeg -f lavfi -i testsrc=size=1280x720:rate=25 -f lavfi -i sine=frequency=1000 \
#   -c:v libx264 -b:v 2M -f hls -hls_time 2 -hls_list_size 5 \
#   -hls_flags delete_segments "$STREAM_DIR/playlist.m3u8" &

sleep 5

echo "Starting Python uploader..."
python3 upload_stream.py
