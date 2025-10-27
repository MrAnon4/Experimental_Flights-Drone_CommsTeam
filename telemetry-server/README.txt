chmod +x setup.sh
sudo ./setup.sh
python3 telemetry-server.py


How to Run on RaspberryPi:

1. Authenticate Pub/Sub
export GOOGLE_APPLICATION_CREDENTIALS="/home/pi/PubSubKey.json"
export GCP_PROJECT_ID="your-project-id"
export GCP_TOPIC_ID="drone-telemetry"

2. Install dependencies
pip install -r requirements.txt

3. Run the server
python3 telemetry-server.py

4. Access the dashboard
http://<raspberrypi_ip>:8000/
or
WebSocket stream: ws://<raspberrypi_ip>:8000/ws/telemetry

