#!/usr/bin/env python3
"""One command: download available GTA GTFS feeds, then build the JSON catalogue."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    print('=== 1/2 Download GTFS sources ===', flush=True)
    download = subprocess.run([sys.executable, str(ROOT / 'sources' / 'download_gtfs.py'),
                               '--parent', str(ROOT / 'sources' / 'source_gtfs_data')], cwd=ROOT)
    if download.returncode:
        print('NOTE: Some feeds could not be downloaded. Building with available feeds.', flush=True)
    print('\n=== 2/2 Build locations + stops JSON ===', flush=True)
    merge = subprocess.run([sys.executable, str(ROOT / 'merge_gtfs_stations.py'),
                            '--parent', str(ROOT / 'sources' / 'source_gtfs_data'), '--out', str(ROOT / 'stations')], cwd=ROOT)
    if merge.returncode:
        print('\nERROR: No usable stations catalogue was produced. Check sources/source_gtfs_data/download_report.json.', flush=True)
    return merge.returncode

if __name__ == '__main__':
    sys.exit(main())
