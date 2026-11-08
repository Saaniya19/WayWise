#!/usr/bin/env python3
"""Download + extract GTA static GTFS Schedule feeds from gtfs_sources.json.

Runs with Python 3.10+ standard library only. Existing valid downloads are
reused unless --force. YRT requires an official manual download.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIRED = {'stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt'}
MAX_ZIP_SIZE = 300 * 1024 * 1024  # 300 MB compressed safety ceiling


def load_sources(path: Path) -> list[dict]:
    sources = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(sources, list):
        raise ValueError('gtfs_sources.json must be a JSON array')
    return sources


def zip_members(path: Path) -> dict[str, str]:
    """Return basename -> ZIP member, preferring shallower archive paths."""
    with zipfile.ZipFile(path) as archive:
        entries = {}
        for info in sorted(archive.infolist(), key=lambda i: (i.filename.count('/'), len(i.filename))):
            if info.is_dir():
                continue
            base = Path(info.filename).name.lower()
            if base.endswith('.txt') and base not in entries:
                entries[base] = info.filename
        if not REQUIRED.issubset(entries):
            raise ValueError('Missing GTFS files: ' + ', '.join(sorted(REQUIRED - entries.keys())))
        return entries


def valid_zip(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        zip_members(path)
        return True
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile):
        return False


def valid_extracted(path: Path) -> bool:
    return path.is_dir() and REQUIRED.issubset({p.name.lower() for p in path.iterdir() if p.is_file()})


def extract_zip(path: Path, destination: Path) -> None:
    """Extract GTFS text files into a flat folder, without unsafe ZIP paths."""
    members = zip_members(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gtfs-extract-', dir=destination.parent) as temp:
        staged = Path(temp) / 'feed'
        staged.mkdir()
        with zipfile.ZipFile(path) as archive:
            for basename, filename in members.items():
                with archive.open(filename) as inp, (staged / basename).open('wb') as out:
                    shutil.copyfileobj(inp, out)
        if not valid_extracted(staged):
            raise ValueError('Extracted feed is missing required GTFS files')
        if destination.exists():
            shutil.rmtree(destination)
        staged.rename(destination)


def fetch(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={
        'User-Agent': 'WayWise-GTFS-Catalogue/1.0 (student capstone)',
        'Accept': 'application/zip,application/octet-stream,*/*',
    })
    with urllib.request.urlopen(request, timeout=90) as response, dest.open('wb') as out:
        downloaded = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            downloaded += len(chunk)
            if downloaded > MAX_ZIP_SIZE:
                raise ValueError('Download exceeds 300 MB size limit')
            out.write(chunk)


def download_all(parent: Path, sources: list[dict], force: bool = False, only: set[str] | None = None) -> list[dict]:
    parent.mkdir(parents=True, exist_ok=True)
    report = []
    for src in sources:
        sid = src['id']
        if only is not None and sid not in only:
            continue
        label, folder, archive = src['name'], parent / src['folder'], parent / src['archive']
        item = {'source_id': sid, 'name': label, 'status': '', 'source_page': src.get('source_page'),
                'download_url': src.get('download_url'), 'archive': src['archive']}
        if not force and valid_extracted(folder):
            item['status'] = 'reused_extracted'
            print(f'[READY] {label}: {folder.name}/ already exists')
        elif not force and valid_zip(archive):
            try:
                extract_zip(archive, folder)
                item['status'] = 'reused_zip'
                print(f'[READY] {label}: extracted existing {archive.name}')
            except Exception as exc:
                item['status'] = 'failed'
                item['error'] = str(exc)
                print(f'[FAIL] {label}: {exc}')
        elif src['download_method'] == 'manual':
            # Even with --force, don't discard a manually collected YRT feed.
            if valid_extracted(folder):
                item['status'] = 'reused_extracted'
                print(f'[READY] {label}: manually collected feed found')
            elif valid_zip(archive):
                try:
                    extract_zip(archive, folder)
                    item['status'] = 'reused_zip'
                    print(f'[READY] {label}: manually collected ZIP extracted')
                except Exception as exc:
                    item['status'] = 'failed'
                    item['error'] = str(exc)
                    print(f'[FAIL] {label}: {exc}')
            else:
                item['status'] = 'manual_required'
                print(f'[MANUAL] {label}: {src["source_page"]}')
                print(f'         Save ZIP as sources/source_gtfs_data/{src["archive"]} and rerun.')
        else:
            url = src.get('download_url')
            print(f'[GET] {label} ...', flush=True)
            if not url:
                item['status'] = 'failed'
                item['error'] = 'Direct source has no URL'
            else:
                # Stage download and unpack before replacing existing good files.
                try:
                    with tempfile.TemporaryDirectory(prefix='gtfs-download-', dir=parent) as temp:
                        temp_zip = Path(temp) / 'download.zip'
                        fetch(url, temp_zip)
                        zip_members(temp_zip)  # Reject HTML error pages / invalid ZIPs.
                        extract_zip(temp_zip, folder)
                        shutil.copy2(temp_zip, archive)
                    item['status'] = 'downloaded'
                    print(f'[OK] {label}: {archive.name} -> {folder.name}/')
                except (OSError, urllib.error.URLError, ValueError, zipfile.BadZipFile) as exc:
                    item['status'] = 'failed'
                    item['error'] = str(exc)
                    print(f'[FAIL] {label}: {exc}')
                    print(f'       Get the ZIP manually from: {src["source_page"]}')
        report.append(item)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--parent', type=Path, default=HERE / 'source_gtfs_data', help='Download directory (default: sources/source_gtfs_data/)')
    ap.add_argument('--sources', type=Path, default=HERE / 'gtfs_sources.json')
    ap.add_argument('--force', action='store_true', help='Fetch fresh direct feeds instead of using existing files')
    ap.add_argument('--only', nargs='+', help='Only selected source IDs, e.g. --only ttc go')
    args = ap.parse_args()
    sources = load_sources(args.sources)
    ids = {s['id'] for s in sources}
    if args.only and not set(args.only).issubset(ids):
        ap.error('Unknown source IDs: ' + ', '.join(sorted(set(args.only) - ids)))
    parent = args.parent.expanduser().resolve()
    report = download_all(parent, sources, args.force, set(args.only) if args.only else None)
    (parent / 'download_report.json').write_text(json.dumps({
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'feeds': report
    }, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    good = sum(r['status'] in ('downloaded', 'reused_extracted', 'reused_zip') for r in report)
    failed = sum(r['status'] == 'failed' for r in report)
    manual = sum(r['status'] == 'manual_required' for r in report)
    print(f'\nDownload summary: {good} ready, {failed} failed, {manual} manual required')
    print(f'Report: {parent / "download_report.json"}')
    return 1 if not good else 0  # Partial imports are permitted, but recorded honestly.


if __name__ == '__main__':
    sys.exit(main())
