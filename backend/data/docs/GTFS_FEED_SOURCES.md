# GTA GTFS Schedule feed sources

The `sources/gtfs_sources.json` registry lists the following **ten transit agencies**. Verified against agency feeds and public catalog listings on **November 8, 2026**. URLs can change, and published schedules can be stale even when their downloads succeed.

| Source | Download | Source information | Access |
|---|---|---|---|
| Brampton Transit | [GTFS ZIP](https://www.arcgis.com/sharing/rest/content/items/a355aabd5a8c490186bdce559c9c75fb/data) | [ArcGIS item](https://www.arcgis.com/home/item.html?id=a355aabd5a8c490186bdce559c9c75fb) | Automatic |
| Burlington Transit | [GTFS ZIP](https://opendata.burlington.ca/gtfs-rt/GTFS_Data.zip) | [Directory](https://opendata.burlington.ca/gtfs-rt/) | Automatic |
| Durham Region Transit | [GTFS ZIP](https://maps.durham.ca/OpenDataGTFS/GTFS_Durham_TXT.zip) | [Feed registry](https://www.transit.land/data/feeds/f-dpz-durhamregiontransit) | Automatic |
| GO Transit | [GTFS ZIP](https://assets.metrolinx.com/raw/upload/v1683228856/Documents/Metrolinx/Open%20Data/GO-GTFS.zip) | [Metrolinx developer page](https://www.gotransit.com/en/partner-with-us/software-developers) | Automatic; Metrolinx terms apply |
| Milton Transit | [GTFS ZIP](https://metrolinx.tmix.se/gtfs/gtfs-milton.zip) | [Feed registry](https://www.transit.land/data/feeds/f-milton~on~ca) | Automatic |
| MiWay | [GTFS ZIP](https://www.miapp.ca/GTFS/google_transit.zip) | [Feed registry](https://www.transit.land/data/feeds/f-dpz2-miway) | Automatic |
| Oakville Transit | [GTFS ZIP](https://www.arcgis.com/sharing/rest/content/items/d78a1c1ad6a940009de8b68839a8f606/data) | [ArcGIS item](https://www.arcgis.com/home/item.html?id=d78a1c1ad6a940009de8b68839a8f606) | Automatic |
| TTC | [GTFS ZIP](https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/7795b45e-e65a-4465-81fc-c36b9dfff169/resource/cfb6b2b8-6191-41e3-bda1-b175c51148cb/download/TTC%20Routes%20and%20Schedules%20Data.zip) | [Toronto Open Data](https://open.toronto.ca/dataset/ttc-routes-and-schedules/) | Automatic |
| UP Express | [GTFS ZIP](https://assets.metrolinx.com/raw/upload/v1682367798/Documents/Metrolinx/Open%20Data/UP-GTFS.zip) | [Metrolinx developer page](https://www.gotransit.com/en/partner-with-us/software-developers) | Automatic; Metrolinx terms apply |
| YRT / VIVA | Manual via [YRT's online form](https://www.yrt.ca/en/about-us/open-data.aspx) | [YRT Open Data](https://www.yrt.ca/en/about-us/open-data.aspx) | **Manual**: accept licence, complete form |

**YRT instructions:** Download the GTFS Schedule ZIP from the official page, rename it `YRT-GTFS.zip`, and place it in `sources/source_gtfs_data/`. Re-run `python3 run_all.py`. The script will extract it and include the data automatically.

All links are for **GTFS Schedule** feeds, not live GTFS Realtime. The downloader checks that the downloaded ZIP contains `stops.txt`, `routes.txt`, `trips.txt`, and `stop_times.txt`. Always inspect the import report for missing feeds or expired service dates.
