# Transit Locations Schema

`backend/app/data/transit_locations.json` stores GO/UP transit stations, parking sites, and transfer candidates.

The catalogue uses `schemaVersion` to track structural changes.

## Structure

```json
{
  "schemaVersion": "1.0",
  "transitStations": [
    {
      "id": "KI",
      "name": "Kitchener GO",
      "latitude": 43.455686,
      "longitude": -80.49313,
      "services": ["GO"]
    }
  ],
  "parkingSites": [
    {
      "id": "parking-001",
      "stationId": "KI",
      "name": "Example Parking Lot",
      "latitude": null,
      "longitude": null
    }
  ],
  "transferCandidates": [
    {
      "id": "transfer-001",
      "parkingSiteId": "parking-001",
      "boardingStopId": "KI",
      "walkingAccess": {
        "distanceMeters": null,
        "durationSeconds": null
      },
      "status": "pending",
      "source": {
        "type": "official_station_page",
        "url": null,
        "lastVerified": null
      }
    }
  ]
}
```

## Notes

- IDs uniquely identify records and link parking sites to transit stations.
- `walkingAccess` describes the walk from parking to boarding.
- `source` tracks where information came from and when it was verified.
- `null` indicates unknown or unverified information.
- `pending` candidates must not be treated as verified.
- Schema changes should update this document, the validator, and `schemaVersion`.

*Example parking and transfer records are placeholders, not verified locations.*
