import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pymavlink import mavutil
import sys
from fastapi.responses import FileResponse
import uvicorn
import math
import random
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# MAVLink connection settings
MAVLINK_CONNECTION = "udp:127.0.0.1:14557"
try:
    logging.info(f"Connecting to MAVLink: {MAVLINK_CONNECTION}")
    mav_connection = mavutil.mavlink_connection(MAVLINK_CONNECTION, baud=921600)
    logging.info("MAVLink listener started on UDP:14550")
except Exception as e:
    logging.error(f"Failed to start MAVLink connection: {e}")
    sys.exit(1)

telemetry_data = {}
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081"],  # Expo web dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/api/telemetry")
async def get_latest_telemetry():
    return telemetry_data

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

async def read_mavlink():
    global telemetry_data
    while True:
        try:
        #     msg = await asyncio.get_event_loop().run_in_executor(
        #     None,
        #     lambda: mav_connection.recv_match(blocking=True, timeout=0.05)
        # )

            
        #     if msg:
        #         # if msg.get_type() == "ATTITUDE":
        #         #     print(math.degrees(msg.yaw))
        #         # else:
        #         #    print(f"not attitude, was: {msg.get_type()}")
        #         if msg.get_type() == "GLOBAL_POSITION_INT":
        #             telemetry_data.update({
        #                 "lat": msg.lat / 1e7,
        #                 "lon": msg.lon / 1e7,
        #                 "alt": msg.alt / 1000.0
        #             })
        #         elif msg.get_type() == "ATTITUDE":
        #             print(msg)
        #             telemetry_data.update({
        #                 "roll": math.degrees(msg.roll),
        #                 "pitch": math.degrees(msg.pitch),
        #                 "yaw": math.degrees(msg.yaw)
        #             })
        #         elif msg.get_type() == "BATTERY_STATUS":
        #             telemetry_data["battery"] = msg.battery_remaining

                telemetry_data = {
                "lat": 37.7749 + random.uniform(-0.001, 0.001),
                "lon": -122.4194 + random.uniform(-0.001, 0.001),
                "alt": 10 + random.uniform(-2, 2),
                "roll": random.uniform(-5, 5),
                "pitch": random.uniform(-5, 5),
                "yaw": random.uniform(0, 360),
                "battery": random.randint(50, 100)
                }

                await manager.broadcast(telemetry_data)
                await asyncio.sleep(0.5)
        
        except Exception as e:
            logging.error(f"Error reading MAVLink data: {e}")
        
        # await asyncio.sleep(0.1)

async def run_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    try:
        await asyncio.gather(
            run_server(),
            read_mavlink()
        )
    except KeyboardInterrupt:
        logging.info("Server shutting down...")
    finally:
        # Cleanup all connections
        for connection in list(manager.active_connections):
            try:
                await connection.close()
            except:
                pass
        manager.active_connections.clear()

if __name__ == "__main__":
    asyncio.run(main())
