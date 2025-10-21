import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pymavlink import mavutil
import sys
from fastapi.responses import FileResponse
import uvicorn
import math

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# MAVLink connection settings
# Connect to MAVProxy's GCS port for two-way communication
MAVLINK_CONNECTION = "udpin:127.0.0.1:14550:source_system=255"
try:
    logging.info(f"Connecting to MAVLink: {MAVLINK_CONNECTION}")
    mav_connection = mavutil.mavlink_connection(MAVLINK_CONNECTION)
    
    # Wait for the first heartbeat to confirm connection
    mav_connection.wait_heartbeat()
    logging.info(f"Heartbeat from system (system {mav_connection.target_system} component {mav_connection.target_component})")
    
except Exception as e:
    logging.error(f"Failed to start MAVLink connection: {e}")
    sys.exit(1)

telemetry_data = {}
app = FastAPI()

# --- Command Functions ---
def arm_vehicle():
    logging.info("Sending ARM command")
    mav_connection.mav.command_long_send(mav_connection.target_system, mav_connection.target_component, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)

def disarm_vehicle():
    logging.info("Sending DISARM command")
    mav_connection.mav.command_long_send(mav_connection.target_system, mav_connection.target_component, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 0, 0, 0, 0, 0, 0, 0)

def set_mode(mode_name):
    mode_id = mav_connection.mode_mapping().get(mode_name)
    if mode_id is None:
        logging.error(f"Mode '{mode_name}' not found.")
        return
    logging.info(f"Setting mode to {mode_name}")
    mav_connection.mav.set_mode_send(mav_connection.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode_id)

def takeoff(altitude):
    logging.info(f"Sending TAKEOFF command to {altitude}m")
    mav_connection.mav.command_long_send(mav_connection.target_system, mav_connection.target_component, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, altitude)

# --- WebSocket and Telemetry Reading ---
class ConnectionManager:
    def __init__(self):
        self.active_connections = set()
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logging.info(f"New WebSocket connection: {websocket.client}")
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logging.info(f"WebSocket disconnected: {websocket.client}")
    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logging.error(f"Error sending to WebSocket: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

# --- API Endpoints ---
@app.get("/api/telemetry")
async def get_latest_telemetry():
    return telemetry_data

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

# --- Command Endpoints ---
@app.post("/api/arm")
async def api_arm_vehicle():
    arm_vehicle()
    return {"status": "ARM command sent"}

@app.post("/api/disarm")
async def api_disarm_vehicle():
    disarm_vehicle()
    return {"status": "DISARM command sent"}

@app.post("/api/mode/{mode_name}")
async def api_set_mode(mode_name: str):
    set_mode(mode_name.upper())
    return {"status": f"SET_MODE command sent for {mode_name.upper()}"}

@app.post("/api/takeoff/{altitude}")
async def api_takeoff(altitude: float):
    # For safety, arm and switch to GUIDED mode before taking off
    set_mode("GUIDED")
    await asyncio.sleep(1) # Give time for mode change
    arm_vehicle()
    await asyncio.sleep(1) # Give time for arming
    takeoff(altitude)
    return {"status": f"TAKEOFF sequence initiated to {altitude}m"}

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def read_mavlink():
    global telemetry_data
    while True:
        try:
            msg = await asyncio.get_event_loop().run_in_executor(None, lambda: mav_connection.recv_match(blocking=True, timeout=0.05))
            if msg:
                if msg.get_type() == "GLOBAL_POSITION_INT":
                    telemetry_data.update({"lat": msg.lat / 1e7, "lon": msg.lon / 1e7, "alt": msg.alt / 1000.0})
                elif msg.get_type() == "ATTITUDE":
                    telemetry_data.update({"roll": math.degrees(msg.roll), "pitch": math.degrees(msg.pitch), "yaw": math.degrees(msg.yaw)})
                elif msg.get_type() == "BATTERY_STATUS":
                    telemetry_data["battery"] = msg.battery_remaining
                await manager.broadcast(telemetry_data)
        except Exception as e:
            logging.error(f"Error reading MAVLink data: {e}")
        await asyncio.sleep(0.01)

# --- Main Application Runner  ---
async def run_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(run_server(), read_mavlink())

if __name__ == "__main__":
    asyncio.run(main())
