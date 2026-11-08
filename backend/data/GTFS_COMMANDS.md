# GTFS scripts: commands

Run these from the **`data/`** directory. No extra Python packages are needed.

## All-in-one: download feeds and regenerate station catalogue

```bash
python3 run_all.py
```

- Reads agency URLs from `sources/gtfs_sources.json`.
- Downloads ZIPs into `sources/source_gtfs_data/` and extracts them into agency subfolders.
- Reuses cached feeds if present.
- Builds `stations/locations.json`, `stations/stops.json`, `stations/locations.geojson`, and `stations/import_report.json`.

## Download without regenerating output

```bash
python3 sources/download_gtfs.py
```

## Rebuild output using existing downloads (no internet)

```bash
python3 merge_gtfs_stations.py
```

## Force refresh of automatic feeds, then rebuild

```bash
python3 sources/download_gtfs.py --force
python3 merge_gtfs_stations.py
```

## Download only selected agencies

```bash
python3 sources/download_gtfs.py --only ttc go
python3 merge_gtfs_stations.py
```

## Provide YRT GTFS manually

YRT requires an official [download form](https://www.yrt.ca/en/about-us/open-data.aspx). Save its ZIP to `sources/source_gtfs_data/YRT-GTFS.zip`, then run `python3 run_all.py`.

## Verify results

Read `sources/source_gtfs_data/download_report.json` for fetch results and `stations/import_report.json` for imports. If an agency shows `missing`, check its ZIP or extracted folder under `sources/source_gtfs_data/`.

The downloader's `checked_at_utc` timestamp describes the check **not** the original download date of cached feeds.
