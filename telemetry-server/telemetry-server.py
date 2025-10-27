import asyncio
import logging
import math
import sys
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pymavlink import mavutil
import uvicorn

from data_handler import DataHandler

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

# FastAPI setup
telemetry_data = {}  # might be unused
app = FastAPI()
data_handler = DataHandler(history_size=2000, emit_interval=0.5)

# --- Command Functions ---
def arm_vehicle():
    logging.info("Sending ARM command")
    mav_connection.mav.command_long_send(
        mav_connection.target_system,
        mav_connection.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 0, 0, 0, 0, 0, 0
    )

def disarm_vehicle():
    logging.info("Sending DISARM command")
    mav_connection.mav.command_long_send(
        mav_connection.target_system,
        mav_connection.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 0, 0, 0, 0, 0, 0, 0
    )

def set_mode(mode_name):
    mode_id = mav_connection.mode_mapping().get(mode_name)
    if mode_id is None:
        logging.error(f"Unknown mode: {mode_name}")
        return
    logging.info(f"Setting mode: {mode_name}")
    mav_connection.mav.set_mode_send(
        mav_connection.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id
    )

def takeoff(altitude):
    logging.info(f"Takeoff to {altitude} meters")
    mav_connection.mav.command_long_send(
        mav_connection.target_system,
        mav_connection.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0, 0, 0, 0, 0, 0, 0, altitude
    )

# --- API Endpoints ---
@app.get("/")
async def serve_index():
    return FileResponse("index.html")

@app.get("/api/telemetry")
async def api_get_latest():
    return await data_handler.get_snapshot()

@app.get("/api/telemetry/history")
async def api_get_history(limit: int = 100):
    return await data_handler.get_history(limit)

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
    return {"status": f"Mode set to {mode_name.upper()}"}

@app.post("/api/takeoff/{altitude}")
async def api_takeoff(altitude: float):
    set_mode("GUIDED")
    await asyncio.sleep(1)
    arm_vehicle()
    await asyncio.sleep(1)
    takeoff(altitude)
    return {"status": f"Takeoff initiated to {altitude}m"}
   
# --- WebSocket ---
async def telemetry_ws(websocket: WebSocket):
    await websocket.accept()
    await data_handler.register_listener(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await data_handler.unregister_listener(websocket)

# --- MAVLink Reading Loop ---
async def read_mavlink():
    while True:
        try:
            msg = await asyncio.get_event_loop().run_in_executor(None, lambda: mav_connection.recv_match(blocking=True, timeout=0.05))
            if not msg:
                await asyncio.sleep(0.01)
                continue

            parsed = None
            msg_type = msg.get_type()

            if msg_type == "GLOBAL_POSITION_INT":
                parsed = {
                    "type": "position",
                    "lat": msg.lat / 1e7,
                    "lon": msg.lon / 1e7,
                    "alt": msg.alt / 1000.0
                }
            elif msg_type == "ATTITUDE":
                parsed = {
                    "type": "attitude",
                    "roll": math.degrees(msg.roll),
                    "pitch": math.degrees(msg.pitch),
                    "yaw": math.degrees(msg.yaw)
                }
            elif msg_type == "BATTERY_STATUS":
                parsed = {"type": "battery", "battery_remaining": getattr(msg, "battery_remaining", None)}

            if parsed:
                await data_handler.process_parsed_message(parsed)

        except Exception as e:
            logging.error(f"MAVLink read error: {e}")
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
