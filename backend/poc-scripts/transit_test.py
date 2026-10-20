import os
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 1. Google Routes API endpoint
URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# 2. Retrieve your API key
API_KEY = os.environ["GOOGLE_MAPS_API_KEY"]

# 3. Choose a future weekday at 8:30 AM Toronto time
tz = ZoneInfo("America/Toronto")
day = datetime.now(tz).date() + timedelta(days=1)

while day.weekday() >= 5:
    day += timedelta(days=1)

departure_time = datetime(
    day.year, day.month, day.day, 8, 30,
    tzinfo=tz
).isoformat()

# 4. Define the request
body = {
    "origin": {
        "address": "200 University Ave W, Waterloo, ON"
    },
    "destination": {
        "address": "Union Station, Toronto, ON"
    },
    "travelMode": "TRANSIT",
    "departureTime": departure_time,
    "computeAlternativeRoutes": True,
    "transitPreferences": {
        "allowedTravelModes": ["TRAIN"]
    }
}

# 5. Specify the response fields
headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": API_KEY,
    "X-Goog-FieldMask": (
        "routes.duration,"
        "routes.distanceMeters,"
        "routes.legs.steps.travelMode,"
        "routes.legs.steps.staticDuration,"
        "routes.legs.steps.distanceMeters,"
        "routes.legs.steps.transitDetails"
    )
}

# 6. Send the request
response = requests.post(
    URL,
    headers=headers,
    json=body,
    timeout=30
)

# 7. Print the response
print("HTTP status:", response.status_code)
print("Google API response:", response.text)
response.raise_for_status()

data = response.json()
print(json.dumps(data, indent=2))

print("\nNumber of routes:", len(data.get("routes", [])))
