import asyncio
import json
import logging
import math
import sys
import random
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pymavlink import mavutil
import uvicorn

# --- Configuration ---
# Configure logging to provide clear output
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Dummy Data Mode ---
# SET THIS TO True TO USE SIMULATED DATA FOR DEVELOPMENT
USE_DUMMY_DATA = True

# MAVLink connection settings (adjust for your setup)
# For a simulator on the same machine: "udp:127.0.0.1:14557"
# For a physical drone via serial: "/dev/ttyACM0" (Linux) or "COM3" (Windows) with a baud rate
MAVLINK_CONNECTION_STRING = "udp:127.0.0.1:14557"
MAVLINK_BAUD_RATE = 57600 # Standard for many radios, ignored for UDP

# --- MAVLink Connection ---
# Global variable to hold the connection
mav_connection = None

def connect_to_mavlink():
    """Initializes the MAVLink connection."""
    global mav_connection
    try:
        logging.info(f"Attempting to connect to MAVLink: {MAVLINK_CONNECTION_STRING}")
        mav_connection = mavutil.mavlink_connection(MAVLINK_CONNECTION_STRING, baud=MAVLINK_BAUD_RATE)
        
        # Wait for the first heartbeat to confirm the connection
        mav_connection.wait_heartbeat()
        logging.info("MAVLink connection established! Heartbeat received.")
        
    except Exception as e:
        logging.error(f"Failed to connect to MAVLink: {e}")
        logging.error("Please check the connection string, baud rate, and ensure the drone/simulator is running.")
        sys.exit(1)

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Drone Telemetry API",
    description="Provides real-time drone telemetry data via REST and WebSockets.",
    version="1.0.0"
)

# Global dictionary to store the latest telemetry state
# We initialize it with default values to ensure the structure is always predictable
telemetry_data = {
    "location": {"lat": None, "lon": None, "alt": None},
    "attitude": {"roll": None, "pitch": None, "yaw": None},
    "battery": {"voltage": None, "current": None, "remaining": None},
    "gps_status": {"fix_type": None, "satellites_visible": None},
    "armed": False,
    "mode": "UNKNOWN"
}

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logging.info(f"New client connected: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logging.info(f"Client disconnected: {websocket.client}")

    async def broadcast_json(self, data: dict):
        """Broadcasts data as JSON to all connected clients."""
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except WebSocketDisconnect:
                self.disconnect(connection)
            except Exception as e:
                logging.error(f"Error broadcasting to client {connection.client}: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

# --- API Endpoints ---
@app.get("/api/v1/telemetry", response_class=JSONResponse)
async def get_latest_telemetry():
    """Returns the latest snapshot of all telemetry data as a JSON object."""
    return telemetry_data

@app.websocket("/ws/v1/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """
    Provides a real-time stream of telemetry data.
    Connect to this endpoint to receive JSON updates as they happen.
    """
    await manager.connect(websocket)
    try:
        # Send the current state immediately on connection
        await websocket.send_json(telemetry_data)
        # Keep the connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# --- Dummy Data Generator ---
async def generate_and_broadcast_dummy_data():
    """
    Generates simulated drone telemetry and broadcasts it.
    This runs instead of the MAVLink reader when USE_DUMMY_DATA is True.
    """
    global telemetry_data
    logging.info("Starting dummy data generator.")
    
    # Starting point (Atlanta, GA)
    lat, lon = 33.7490, -84.3880
    alt = 0
    yaw = 0

    while True:
        # Simulate movement
        lat += random.uniform(-0.00005, 0.00005)
        lon += random.uniform(-0.00005, 0.00005)
        alt += random.uniform(-0.5, 0.5)
        if alt < 0: alt = 0 # Don't go underground
        
        yaw = (yaw + random.uniform(-2, 2)) % 360

        telemetry_data = {
            "location": {
                "lat": lat,
                "lon": lon,
                "alt": max(0, alt) # Ensure altitude is not negative
            },
            "attitude": {
                "roll": random.uniform(-5.0, 5.0),
                "pitch": random.uniform(-5.0, 5.0),
                "yaw": yaw
            },
            "battery": {
                "voltage": round(random.uniform(11.8, 12.6), 2),
                "current": round(random.uniform(7.0, 15.0), 2),
                "remaining": int(90 - (time.time() % 600) / 10) # Decrease over 10 mins
            },
            "gps_status": {
                "fix_type": 6, # Corresponds to RTK Fixed
                "satellites_visible": random.randint(10, 15)
            },
            "armed": True,
            "mode": "GUIDED"
        }

        await manager.broadcast_json(telemetry_data)
        await asyncio.sleep(0.5) # Broadcast twice per second


# --- Background MAVLink Reader Task ---
async def read_and_broadcast_mavlink():
    """
    The core background task that reads messages from the drone
    and broadcasts them to connected clients.
    """
    global telemetry_data
    loop = asyncio.get_event_loop()

    while True:
        try:
            # Use run_in_executor to avoid blocking the asyncio event loop
            msg = await loop.run_in_executor(
                None, lambda: mav_connection.recv_match(blocking=True, timeout=1.0)
            )

            if not msg:
                # Timeout, continue to next iteration
                continue

            msg_type = msg.get_type()
            updated = False

            if msg_type == "GLOBAL_POSITION_INT":
                telemetry_data["location"]["lat"] = msg.lat / 1e7
                telemetry_data["location"]["lon"] = msg.lon / 1e7
                telemetry_data["location"]["alt"] = msg.relative_alt / 1000.0 # More common to use relative alt
                updated = True
            
            elif msg_type == "ATTITUDE":
                telemetry_data["attitude"]["roll"] = math.degrees(msg.roll)
                telemetry_data["attitude"]["pitch"] = math.degrees(msg.pitch)
                telemetry_data["attitude"]["yaw"] = math.degrees(msg.yaw)
                updated = True

            elif msg_type == "SYS_STATUS":
                telemetry_data["battery"]["voltage"] = msg.voltage_battery / 1000.0
                telemetry_data["battery"]["current"] = msg.current_battery / 100.0
                telemetry_data["battery"]["remaining"] = msg.battery_remaining
                updated = True

            elif msg_type == "GPS_RAW_INT":
                telemetry_data["gps_status"]["fix_type"] = msg.fix_type
                telemetry_data["gps_status"]["satellites_visible"] = msg.satellites_visible
                updated = True
            
            elif msg_type == "HEARTBEAT":
                telemetry_data["armed"] = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
                telemetry_data["mode"] = mavutil.mode_string_v10(msg)
                updated = True

            # If any data was updated, broadcast the new state
            if updated:
                await manager.broadcast_json(telemetry_data)

        except Exception as e:
            logging.error(f"Error in MAVLink reader task: {e}")
            # Avoid hammering the log in case of rapid errors
            await asyncio.sleep(2)

# --- Application Lifecycle Events ---
@app.on_event("startup")
async def startup_event():
    """Tasks to run when the application starts."""
    if USE_DUMMY_DATA:
        # Start the dummy data generator
        asyncio.create_task(generate_and_broadcast_dummy_data())
    else:
        # Connect to the real MAVLink source and start the reader
        connect_to_mavlink()
        asyncio.create_task(read_and_broadcast_mavlink())

@app.on_event("shutdown")
async def shutdown_event():
    """Tasks to run when the application shuts down."""
    logging.info("Server is shutting down. Closing all connections.")
    for connection in list(manager.active_connections):
        try:
            await connection.close(code=1000)
        except Exception:
            pass # Ignore errors on close
    if mav_connection:
        mav_connection.close()
    logging.info("Shutdown complete.")


if __name__ == "__main__":
    # To run: uvicorn drone_api:app --host 0.0.0.0 --port 8000 --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)

