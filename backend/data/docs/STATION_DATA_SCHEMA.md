# WayWise station and stop catalogue — data structure

## Source registry: `sources/gtfs_sources.json`

A JSON **array** of one object per agency:

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Stable short code, e.g. `ttc` or `go` |
| `name` | string | Human-readable transit agency |
| `folder` | string | Extracted feed directory under `sources/source_gtfs_data/` |
| `archive` | string | ZIP filename under `sources/source_gtfs_data/` |
| `download_method` | `direct` or `manual` | Can the downloader retrieve it automatically? |
| `download_url` | string or null | Direct GTFS ZIP URL for `direct` sources |
| `source_page` | string | Official/source information page; use if download fails |
| `notes` | string | Licence/access or quality caveats |

Example:

```json
{
  "id": "miway",
  "name": "MiWay",
  "folder": "MiWay-GTFS",
  "archive": "MiWay-GTFS.zip",
  "download_method": "direct",
  "download_url": "https://www.miapp.ca/GTFS/google_transit.zip",
  "source_page": "https://www.transit.land/data/feeds/f-dpz2-miway",
  "notes": ""
}
```


## `stations/locations.json`

A JSON **array**; each object is one *logical location* (a GTFS parent station, or a standalone boarding stop). Fields:

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Unique location ID, e.g. `ttc:100` |
| `source_id` | string | Source identifier, e.g. `ttc` |
| `agency` | string | Agency display name |
| `name` | string | Station or stop name |
| `type` | string | `station` or `standalone_stop` |
| `latitude`, `longitude` | number or null | WGS84 coordinates; null when missing |
| `stop_ids` | array of strings | IDs of all GTFS stop records grouped here, including parent/platform/entrance rows |
| `routes` | array of objects | Distinct transit routes serving member boarding stops |
| `stop_code` | string or null | Published public stop code, if any |
| `wheelchair_boarding` | integer or null | Original GTFS wheelchair accessibility value, if present |

Each `routes` object contains `id`, `short_name`, `long_name`, and integer-or-null `route_type` (e.g. `1` subway, `2` rail, `3` bus, `0` tram). Route names can be empty if a feed omits them.

Example (**illustrative, not real TTC data**):

```json
[
  {
    "id": "ttc:100",
    "source_id": "ttc",
    "agency": "Toronto Transit Commission (TTC)",
    "name": "Example Station",
    "type": "station",
    "latitude": 43.65,
    "longitude": -79.38,
    "stop_ids": ["ttc:100", "ttc:101"],
    "routes": [
      {"id": "ttc:1", "short_name": "1", "long_name": "Example Line", "route_type": 1}
    ],
    "stop_code": null,
    "wheelchair_boarding": 1
  }
]
```


## `stations/stops.json`

A JSON **array** of every original GTFS `stops.txt` record. This includes **formal station rows, platform rows, standalone stops, entrances, and generic nodes**; the filename follows the GTFS `stops.txt` convention.

| Field | Type | Meaning |
|---|---|---|
| `id`, `gtfs_stop_id`, `source_id` | strings | Namespaced ID, original GTFS ID, source code |
| `name` | string | Original GTFS stop/station/entrance name |
| `type` | string | `boarding_stop`, `station`, `entrance`, `generic_node`, `boarding_area`, or `other` |
| `location_id` | string or null | ID in `locations.json` grouping this record |
| `parent_station_id` | string or null | Original GTFS parent reference with source prefix |
| `latitude`, `longitude` | number or null | Original record's coordinates |
| `stop_code`, `platform_code` | string or null | Original stop/platform label |
| `wheelchair_boarding` | integer or null | Original GTFS wheelchair value |
| `route_ids` | array of strings | Routes directly associated with this individual stop record |

Use `location_id` for *stop → location*, or `locations[].stop_ids` for *location → child stops*. A location's route objects are the union of routes from its member stops.


## `stations/locations.geojson`

Standard GeoJSON `FeatureCollection` of the same logical locations as `locations.json`. Each `Feature.geometry` is a `Point` with `[longitude, latitude]` (GeoJSON order). `properties` holds the remaining location fields. Locations without valid coordinates are omitted **from GeoJSON only**.


## `stations/import_report.json`

An object with `created_at_utc`, `sources` (array), and `totals`. Each `sources` entry contains `source_id`, `agency`, `status` (`ok`, `missing`, `invalid`), and a `source_page`. Successful imports also include `input`, counts of raw stop records, locations, stations, routes, and `service_dates` (`start`, `end`, `basis`) where available.

`sources/source_gtfs_data/download_report.json` is a **separate** report of downloading/extraction, with `status` values such as `downloaded`, `reused_extracted`, `reused_zip`, `failed`, or `manual_required`.


## Not included (deliberately)

- No parking metadata or real-time parking availability.
- No geographic merging of a GO station with a nearby TTC station.
- No nearby-stop grouping, transfer detection, or walking-distance computation.
- No service-date or time-of-day filtering of routes.

This is a static, reproducible starting catalogue; the original GTFS feeds remain the source of truth.


## How GTFS is joined

1. Read each agency's `stops.txt` for `stop_id`, stop name, coordinates, type, and `parent_station`.
2. Read `routes.txt` to get route IDs/names/modes.
3. Join `trips.txt` using `trip_id → route_id`.
4. Join `stop_times.txt` using `trip_id → stop_id` to find which routes serve each stop. Exclude stop-time rows that explicitly prohibit both pickup and dropoff.
5. Group each station's platforms/entrances/nodes using **GTFS `parent_station` references only**. Standalone stops become locations of their own.
6. Prefix source-local IDs with the source code, e.g. `ttc:123` and `go:123` are different IDs.

Routes are aggregated from all trips in the feed, **without checking which trips operate today**. Stations from different transit providers are **not** deduplicated or merged geographically. No proximity matching or walking-distance computation is performed.
