# WayWise GTA GTFS data
The `sources/` directory holds the GTFS feed registry, its schema, the downloader, and raw downloaded feeds. The merger in the `data/` directory generates the station catalogue under `stations/`.

## Folder layout

```text
data/
├── run_all.py                       # Download + merge with one command
├── merge_gtfs_stations.py           # Generate the station/stop catalogue
├── sources/
│   ├── download_gtfs.py             # Download and unpack GTFS feeds
│   ├── gtfs_sources.json            # Agency names, URLs and manual requirements
│   ├── gtfs_source.schema.json      # Schema for source registry
│   └── source_gtfs_data/            # Downloaded ZIPs, extracted feeds, report
├── stations/                        # Generated JSON and GeoJSON
│   ├── locations.json
│   ├── stops.json
│   ├── locations.geojson
│   └── import_report.json
└── docs/
    ├── GTFS_FEED_SOURCES.md
    └── STATION_DATA_SCHEMA.md
```
