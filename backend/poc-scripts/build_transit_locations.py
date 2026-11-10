"""Generate WayWise's transit location catalogue from GO and UP GTFS stops.txt.

Run: python build_transit_locations.py --go-stops stops.txt --up-stops 'stops(1).txt'
The parking facts below are a manually reviewed snapshot of official GO station pages;
re-check source pages when refreshing the catalogue.
"""
import argparse
import csv
import json
from datetime import date
from pathlib import Path

VERIFIED_ON = '2026-11-08'
GO_PARKING = {
    'KI': {'status': 'paid_only', 'sourceUrl': 'https://www.gotransit.com/en/free-parking-at-go-stations', 'lots': []},
    'GL': {'status': 'free', 'sourceUrl': 'https://www.gotransit.com/en/find-a-station-or-stop/gl/station-details', 'lots': [('main', 'Main Lot', 15)]},
    'AC': {'status': 'free', 'sourceUrl': 'https://www.gotransit.com/en/find-a-station/ac/station-details', 'lots': [('main', 'Main Lot', 46)]},
    'GE': {'status': 'free', 'sourceUrl': 'https://www.gotransit.com/en/find-a-station-or-stop/ge/station-details', 'lots': [('north', 'North Lot', 223), ('main', 'Main Lot', 425)]},
    'MO': {'status': 'free', 'sourceUrl': 'https://www.gotransit.com/en/find-a-station-or-stop/mo/station-details', 'lots': [('main', 'Main Lot', 1486)]},
    'BE': {'status': 'free', 'sourceUrl': 'https://www.gotransit.com/en/find-a-station-or-stop/be/station-details', 'lots': [('main', 'Main Lot', 1724), ('south', 'South Lot', 646)]},
}

def read_stops(path):
    with open(path, newline='', encoding='utf-8-sig') as file:
        return list(csv.DictReader(file))

def build(go_path, up_path):
    stations = {}
    for row in read_stops(go_path):
        if not row['stop_id'].isalpha():  # GO-feed-specific major-station heuristic
            continue
        sid = row['stop_id']
        stations[sid] = {
            'id': f'GO:{sid}', 'gtfsStopIds': {'GO': sid},
            'name': row['stop_name'],
            'latitude': float(row['stop_lat']), 'longitude': float(row['stop_lon']),
            'services': ['GO'],
            'source': {'type': 'official_gtfs', 'url': row['stop_url'] or 'https://www.metrolinx.com/en/about-us/open-data', 'lastVerified': VERIFIED_ON},
            'parking': {'status': 'unknown', 'sourceUrl': None, 'lastVerified': None},
        }
    for row in read_stops(up_path):
        sid = row['stop_id']
        if sid in stations:
            stations[sid]['services'].append('UP')
            stations[sid]['gtfsStopIds']['UP'] = sid
        else:
            stations[sid] = {
                'id': f'UP:{sid}', 'gtfsStopIds': {'UP': sid},
                'name': row['stop_name'],
                'latitude': float(row['stop_lat']), 'longitude': float(row['stop_lon']),
                'services': ['UP'],
                'source': {'type': 'official_gtfs', 'url': row['stop_url'] or 'https://www.metrolinx.com/en/about-us/open-data', 'lastVerified': VERIFIED_ON},
                'parking': {'status': 'unknown', 'sourceUrl': None, 'lastVerified': None},
            }
    parking_sites, candidates = [], []
    for sid, facts in GO_PARKING.items():
        if sid not in stations:
            raise ValueError(f'Expected GO stop {sid} missing from feed')
        station = stations[sid]
        station['parking'] = {'status': facts['status'], 'sourceUrl': facts['sourceUrl'], 'lastVerified': VERIFIED_ON}
        for lot_code, lot_name, capacity in facts['lots']:
            lot_id = f'GO:{sid}:parking:{lot_code}'
            parking_sites.append({
                'id': lot_id, 'name': f"{station['name']} - {lot_name}",
                'stationId': station['id'],
                'latitude': None, 'longitude': None,
                'coordinatesStatus': 'not_verified',
                'parkingType': 'free_customer', 'publishedSpaceCount': capacity,
                'realTimeSpacesAvailable': None,
                'source': {'type': 'official_station_page', 'url': facts['sourceUrl'], 'lastVerified': VERIFIED_ON},
            })
            candidates.append({
                'id': f'transfer:{lot_id}', 'parkingSiteId': lot_id,
                'boardingStopId': station['id'],
                'walkingAccess': None, 'status': 'pending_walking_verification',
                'source': {'type': 'official_station_page', 'url': facts['sourceUrl'], 'lastVerified': VERIFIED_ON},
            })
    return {
        'schemaVersion': '1.0', 'generatedOn': date.today().isoformat(),
        'notes': 'Station coordinates are GTFS boarding coordinates, NOT parking entrance coordinates. Published parking space counts are capacity, NOT real-time availability. Pending candidates are not yet routable.',
        'transitStations': sorted(stations.values(), key=lambda s: s['name']),
        'parkingSites': sorted(parking_sites, key=lambda x: x['id']),
        'transferCandidates': sorted(candidates, key=lambda x: x['id']),
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--go-stops', default='stops.txt')
    parser.add_argument('--up-stops', default='stops(1).txt')
    parser.add_argument('--output', default='transit_locations.json')
    args = parser.parse_args()
    result = build(args.go_stops, args.up_stops)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"Wrote {len(result['transitStations'])} stations, {len(result['parkingSites'])} documented lots, {len(result['transferCandidates'])} pending transfer links to {args.output}")
