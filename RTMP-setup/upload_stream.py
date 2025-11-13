from google.cloud import storage
import os
import time

# Configuration
BUCKET = "video-stream-rasp"  
PROJECT_ID = "drone-stream-473321"
STREAM_DIR = "stream"

# Set credentials path
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./my-service-account-key.json"

# Initialize Google Cloud Storage client
client = storage.Client(project=PROJECT_ID)
bucket = client.bucket(BUCKET)

uploaded = set()

print("Starting uploader...")
print(f"Bucket: {BUCKET}")
print(f"Watching: {STREAM_DIR}/")
print("-" * 50)

while True:
    try:
        # Check if stream directory exists
        if not os.path.exists(STREAM_DIR):
            print(f"⏳ Waiting for {STREAM_DIR}/ directory to be created...")
            time.sleep(2)
            continue
            
        for file in os.listdir(STREAM_DIR):
            if file.endswith((".ts", ".m3u8")) and file not in uploaded:
                file_path = os.path.join(STREAM_DIR, file)
                blob = bucket.blob(file)
                blob.upload_from_filename(file_path)
                uploaded.add(file)
                print(f"Uploaded: {file}")
    except Exception as e:
        print(f"Error: {e}")
    
    time.sleep(1)
