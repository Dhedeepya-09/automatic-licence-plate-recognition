import requests
import sys

url = "https://github.com/nandini-yadav/License-Plate-Detection-using-YOLOv8/raw/main/best.pt"
output = "license_plate_detector.pt"

print(f"Downloading {url}...")
try:
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    with open(output, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print("Download successful!")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
