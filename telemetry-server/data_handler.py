import asyncio
import time
from collections import deque
from typing import Dict, Any, Set
from gcp_publisher import publish_telem
import logging

class DataHandler:
    def __init__(self, history_size: int = 1000, emit_interval: float = 0.5):
        self.snapshot: Dict[str, Any] = {}
        self.history = deque(maxlen=history_size)
        self.listeners: Set = set()
        self.emit_interval = emit_interval
        self._lock = asyncio.Lock()
        self._last_emit = 0.0

    async def register_listener(self, ws):
        async with self._lock:
            self.listeners.add(ws)

    async def unregister_listener(self, ws):
        async with self._lock:
            self.listeners.discard(ws)

    async def process_parsed_message(self, data: dict):
        async with self._lock:
            entry = {"ts": time.time(), **data}
            self.history.append(entry)
            msg_type = data.get("type")
            if msg_type:
                self.snapshot[msg_type] = {k: v for k, v in data.items() if k != "type"}

        await self._maybe_broadcast()
        await self._maybe_publish_cloud()

    async def _maybe_broadcast(self):
        now = time.time()
        if now - self._last_emit < self.emit_interval:
            return
        self._last_emit = now

        async with self._lock:
            snapshot_copy = {"ts": time.time(), **self.snapshot}
            listeners = list(self.listeners)

        for ws in listeners:
            try:
                await ws.send_json(snapshot_copy)
            except Exception:
                async with self._lock:
                    self.listeners.discard(ws)

    async def _maybe_publish_cloud(self):
        """Send aggregated snapshot to Pub/Sub periodically."""
        try:
            cloud_payload = {
                "droneId": "drone123",
                **self.snapshot.get("position", {}),
                **self.snapshot.get("attitude", {}),
                **self.snapshot.get("battery", {}),
                "timestamp": time.time()
            }
            asyncio.create_task(publish_telem(cloud_payload))
        except Exception as e:
            logging.error(f"GCP publish error: {e}")

    async def get_snapshot(self):
        async with self._lock:
            return {"ts": time.time(), **self.snapshot}

    async def get_history(self, limit: int = 100):
        async with self._lock:
            return list(self.history)[-limit:]
