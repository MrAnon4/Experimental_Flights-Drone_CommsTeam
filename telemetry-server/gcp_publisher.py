from google.cloud import pubsub_v1
import asyncio
import json
import logging
import os

# Edit these with actual GCP credentials (create an .env file if possible with these secrets)
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "YOUR_PROJECT_ID")
TOPIC_ID = os.getenv("GCP_TOPIC_ID", "drone-telemetry")

try:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
except Exception as e:
    logging.error(f"Error initializing Pub/Sub client: {e}")
    publisher = None
    topic_path = None

async def publish_telem(data: dict):
    """Publish telemetry data to Pub/Sub asynchronously."""
    if not publisher or not topic_path:
        return
    try:
        payload = json.dumps(data).encode("utf-8")
        future = publisher.publish(topic_path, payload)
        await asyncio.wrap_future(future)
        logging.info(f"Published telemetry to Pub/Sub topic: {TOPIC_ID}")
    except Exception as e:
        logging.error(f"Failed to publish telemetry: {e}")
