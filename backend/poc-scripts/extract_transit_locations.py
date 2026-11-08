import csv
import json
import zipfile


def load_stops(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        with z.open("stops.txt") as f:
            return list(csv.DictReader(
                line.decode("utf-8-sig") for line in f
            ))


stations = {}

# Load GO stations
for row in load_stops("GO-GTFS.zip"):
    # Feed-specific rule for selecting major stations
    if not row["stop_id"].isalpha():
        continue

    station_id = row["stop_id"]

    stations[station_id] = {
        "id": station_id,
        "name": row["stop_name"],
        "latitude": float(row["stop_lat"]),
        "longitude": float(row["stop_lon"]),
        "services": ["GO"],
    }

# Merge UP Express stations
for row in load_stops("UP-GTFS.zip"):
    station_id = row["stop_id"]

    if station_id in stations:
        # Same station: add UP service without duplicating it
        stations[station_id]["services"].append("UP")
    else:
        stations[station_id] = {
            "id": station_id,
            "name": row["stop_name"],
            "latitude": float(row["stop_lat"]),
            "longitude": float(row["stop_lon"]),
            "services": ["UP"],
        }

# Save as one sorted JSON array
combined = sorted(stations.values(), key=lambda s: s["name"])

with open("transit_stations.json", "w") as f:
    json.dump(combined, f, indent=2)

print(f"GO stations: {sum('GO' in s['services'] for s in combined)}")
print(f"UP stations: {sum('UP' in s['services'] for s in combined)}")
print(f"Unique stations: {len(combined)}")
