#!/usr/bin/env python3
"""Merge GTA GTFS source feeds into stations/locations.json and stations/stops.json.

Only joins published GTFS stop/route data. Groups platform records using their
explicit parent_station field. Does not infer across-agency or walking transfers.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIND = {'0': 'boarding_stop', '1': 'station', '2': 'entrance', '3': 'generic_node', '4': 'boarding_area'}
REQUIRED = {'stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt'}


class GTFSReader:
    def __init__(self, path: Path):
        self.zip = None
        self.files = {}
        if path.is_dir():
            # Download script creates a flat folder; also support a manually nested folder.
            candidates = sorted(path.rglob('stops.txt'), key=lambda p: (len(p.parts), str(p)))
            if not candidates:
                raise ValueError(f'No stops.txt inside {path}')
            self.files = {p.name.lower(): p for p in candidates[0].parent.iterdir() if p.is_file()}
        else:
            self.zip = zipfile.ZipFile(path)
            for name in sorted(self.zip.namelist(), key=lambda n: (n.count('/'), len(n))):
                if not name.endswith('/'):
                    self.files.setdefault(Path(name).name.lower(), name)
        if not REQUIRED.issubset(self.files):
            self.close()
            raise ValueError('Missing: ' + ', '.join(sorted(REQUIRED - self.files.keys())))

    def close(self):
        if self.zip:
            self.zip.close()

    def rows(self, name: str):
        entry = self.files.get(name.lower())
        if entry is None:
            return
        stream = self.zip.open(entry) if self.zip else entry.open('rb')
        with stream, io.TextIOWrapper(stream, encoding='utf-8-sig', errors='replace', newline='') as text:
            for row in csv.DictReader(text):
                yield {k: (v or '').strip() for k, v in row.items() if k}


def coords(stop: dict) -> tuple[float | None, float | None]:
    try:
        lat, lon = float(stop.get('stop_lat', '')), float(stop.get('stop_lon', ''))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except (TypeError, ValueError):
        pass
    return None, None


def as_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def root_stop(stop_id: str, gtfs_stops: dict[str, dict]) -> str:
    """Walk GTFS parent_station chain; keep malformed references local."""
    current, seen = stop_id, set()
    while current in gtfs_stops and current not in seen:
        seen.add(current)
        row = gtfs_stops[current]
        if (row.get('location_type') or '0') == '1':
            return current
        parent = row.get('parent_station', '')
        if not parent or parent not in gtfs_stops:
            return current
        current = parent
    return stop_id


def service_dates(reader: GTFSReader):
    dates = []
    for row in reader.rows('feed_info.txt'):
        if row.get('feed_start_date'):
            dates.append(row['feed_start_date'])
        if row.get('feed_end_date'):
            dates.append(row['feed_end_date'])
    if dates:
        return {'start': min(dates), 'end': max(dates), 'basis': 'feed_info.txt'}
    for row in reader.rows('calendar.txt'):
        if row.get('start_date'):
            dates.append(row['start_date'])
        if row.get('end_date'):
            dates.append(row['end_date'])
    return {'start': min(dates) if dates else None, 'end': max(dates) if dates else None,
            'basis': 'calendar.txt' if dates else None}


def process_feed(source: dict, path: Path) -> tuple[list[dict], list[dict], dict]:
    reader = GTFSReader(path)
    sid = source['id']
    ns = lambda value: f'{sid}:{value}'
    try:
        source_stops = {r['stop_id']: r for r in reader.rows('stops.txt') if r.get('stop_id')}
        routes = {r['route_id']: r for r in reader.rows('routes.txt') if r.get('route_id')}
        trips = {r['trip_id']: r['route_id'] for r in reader.rows('trips.txt')
                 if r.get('trip_id') and r.get('route_id') in routes}
        if not source_stops:
            raise ValueError('stops.txt contains no stop IDs')
        stop_routes: dict[str, set[str]] = defaultdict(set)
        for row in reader.rows('stop_times.txt'):
            # Discard stops where GTFS explicitly prohibits both boarding and alighting.
            if row.get('pickup_type') == '1' and row.get('drop_off_type') == '1':
                continue
            route_id = trips.get(row.get('trip_id', ''))
            stop_id = row.get('stop_id', '')
            if route_id and stop_id in source_stops:
                stop_routes[stop_id].add(route_id)

        root_by_id = {stop_id: root_stop(stop_id, source_stops) for stop_id in source_stops}
        members = defaultdict(list)
        for stop_id, root in root_by_id.items():
            members[root].append(stop_id)

        stops_out = []
        for stop_id, row in source_stops.items():
            root = root_by_id[stop_id]
            root_kind = source_stops[root].get('location_type') or '0'
            lat, lon = coords(row)
            stops_out.append({
                'id': ns(stop_id), 'gtfs_stop_id': stop_id, 'source_id': sid,
                'name': row.get('stop_name', ''),
                'type': KIND.get(row.get('location_type') or '0', 'other'),
                'location_id': ns(root) if root_kind in ('0', '1') else None,
                'parent_station_id': ns(row['parent_station']) if row.get('parent_station') else None,
                'latitude': lat, 'longitude': lon,
                'stop_code': row.get('stop_code') or None,
                'platform_code': row.get('platform_code') or None,
                'wheelchair_boarding': as_int(row.get('wheelchair_boarding')),
                'route_ids': [ns(r) for r in sorted(stop_routes.get(stop_id, ()))],
            })

        locations_out = []
        for root, member_ids in members.items():
            row = source_stops[root]
            root_type = row.get('location_type') or '0'
            if root_type not in ('0', '1'):
                continue  # A standalone entrance/node isn't a boardable location.
            lat, lon = coords(row)
            if lat is None:
                known = [coords(source_stops[m]) for m in member_ids]
                known = [(a, b) for a, b in known if a is not None]
                if known:
                    lat = sum(a for a, _ in known) / len(known)
                    lon = sum(b for _, b in known) / len(known)
            route_ids = sorted(set().union(*(stop_routes.get(m, set()) for m in member_ids)))
            locations_out.append({
                'id': ns(root), 'source_id': sid, 'agency': source['name'],
                'name': row.get('stop_name', ''),
                'type': 'station' if root_type == '1' else 'standalone_stop',
                'latitude': lat, 'longitude': lon,
                'stop_ids': [ns(m) for m in sorted(member_ids)],
                'routes': [{
                    'id': ns(r),
                    'short_name': routes[r].get('route_short_name', ''),
                    'long_name': routes[r].get('route_long_name', ''),
                    'route_type': as_int(routes[r].get('route_type')),
                } for r in route_ids],
                'stop_code': row.get('stop_code') or None,
                'wheelchair_boarding': as_int(row.get('wheelchair_boarding')),
            })
        meta = {
            'source_id': sid, 'agency': source['name'], 'status': 'ok',
            'input': str(path), 'raw_stop_records': len(stops_out),
            'locations': len(locations_out),
            'formal_stations': sum(r['type'] == 'station' for r in locations_out),
            'routes': len(routes), 'service_dates': service_dates(reader),
            'source_page': source.get('source_page'),
        }
        return locations_out, stops_out, meta
    finally:
        reader.close()


def write_json(path: Path, obj) -> None:
    with path.open('w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')


def merge(parent: Path, sources: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    locations, stops, report = [], [], []
    for src in sources:
        folder = parent / src['folder']
        archive = parent / src['archive']
        # Prefer extracted data (where required files are present), otherwise the archive.
        required = {'stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt'}
        extracted = folder.is_dir() and required.issubset({p.name.lower() for p in folder.iterdir() if p.is_file()})
        path = folder if extracted else archive
        if not path.exists():
            print(f'[MISSING] {src["name"]}: no {src["folder"]}/ or {src["archive"]}')
            report.append({'source_id': src['id'], 'agency': src['name'], 'status': 'missing',
                           'source_page': src.get('source_page')})
            continue
        try:
            loc, st, item = process_feed(src, path)
            locations.extend(loc)
            stops.extend(st)
            report.append(item)
            print(f'[OK] {src["name"]}: {len(loc):,} locations, {len(st):,} stop records')
        except (OSError, ValueError, KeyError, csv.Error, zipfile.BadZipFile) as exc:
            print(f'[FAIL] {src["name"]}: {exc}')
            report.append({'source_id': src['id'], 'agency': src['name'], 'status': 'invalid',
                           'source_page': src.get('source_page'), 'error': str(exc)})
    locations.sort(key=lambda row: (row['source_id'], row['name'], row['id']))
    stops.sort(key=lambda row: (row['source_id'], row['id']))
    return locations, stops, report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--parent', type=Path, default=HERE / 'sources' / 'source_gtfs_data', help='Extracted GTFS folders/ZIPs')
    ap.add_argument('--out', type=Path, default=HERE / 'stations', help='Output JSON directory')
    ap.add_argument('--sources', type=Path, default=HERE / 'sources' / 'gtfs_sources.json')
    args = ap.parse_args()
    sources = json.loads(args.sources.read_text(encoding='utf-8'))
    loc, stops, reports = merge(args.parent.expanduser().resolve(), sources)
    out = args.out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / 'locations.json', loc)
    write_json(out / 'stops.json', stops)
    geo = {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature',
         'geometry': {'type': 'Point', 'coordinates': [p['longitude'], p['latitude']]},
         'properties': {k: v for k, v in p.items() if k not in ('latitude', 'longitude')}}
        for p in loc if p['latitude'] is not None and p['longitude'] is not None
    ]}
    write_json(out / 'locations.geojson', geo)
    report = {
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'sources': reports,
        'totals': {'sources_ok': sum(x['status'] == 'ok' for x in reports),
                   'locations': len(loc), 'stop_records': len(stops),
                   'formal_stations': sum(x['type'] == 'station' for x in loc)}
    }
    write_json(out / 'import_report.json', report)
    print(f'\nOutput: {out}')
    print(f'  {len(loc):,} station/stop locations ({report["totals"]["formal_stations"]:,} formal stations)')
    print(f'  {len(stops):,} original GTFS stop records')
    print(f'  {report["totals"]["sources_ok"]}/{len(reports)} agencies loaded')
    print('  locations.json, stops.json, locations.geojson, import_report.json')
    return 0 if loc else 1


if __name__ == '__main__':
    sys.exit(main())
