'''Find transit stations within the user's driving limits of the origin
and destination.'''

import json
import math
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from app.models.candidates import (
    CandidateEnd,
    TransferCandidate,
    TransferCandidateDistance,
    TransitStation,
)
from app.models.common import Location
from app.models.planning import DrivingConstraint, TravelConstraints
from app.services.constraint_filter import DRIVING_TIME_TOLERANCE_SECONDS
from app.services.google_routes_client import get_route_matrix


CATALOGUE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "transit_locations.json"
)

# A generous top speed, used to pre-filter stations.
MAX_DRIVING_SPEED_KMH = 130

EARTH_RADIUS_KM = 6371.0

RouteMatrixFn = Callable[..., list[TransferCandidateDistance]]


def parse_catalogue(data: dict) -> list[TransitStation]:
    """Build TransitStation objects from the transit_locations.json shape,
    attaching each station's first parking site (if any)."""
    parking_by_station: dict[str, dict] = {}

    for site in data.get("parkingSites", []):
        parking_by_station.setdefault(site.get("stationId"), site)

    stations = []

    for raw in data.get("transitStations", []):
        site = parking_by_station.get(raw["id"])

        stations.append(
            TransitStation(
                id=raw["id"],
                name=raw["name"],
                location=Location(
                    latitude=raw["latitude"],
                    longitude=raw["longitude"],
                    name=raw["name"],
                ),
                services=raw.get("services", []),
                parkingStatus=(raw.get("parking") or {}).get(
                    "status", "unknown"
                ),
                parkingSiteId=site.get("id") if site else None,
            )
        )

    return stations


@lru_cache(maxsize=1)
def load_stations(path: Path = CATALOGUE_PATH) -> tuple[TransitStation, ...]:
    with open(path, encoding="utf-8") as f:
        return tuple(parse_catalogue(json.load(f)))


def haversine_km(a: Location, b: Location) -> float:
    """Straight-line distance between two points in km."""
    lat1, lon1 = math.radians(a.latitude), math.radians(a.longitude)
    lat2, lon2 = math.radians(b.latitude), math.radians(b.longitude)

    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin((lon2 - lon1) / 2) ** 2
    )

    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _driving_limit(
    driving: DrivingConstraint, end: CandidateEnd
) -> float | int | None:
    """The user's driving limit for one end of the trip, or None."""
    if driving.limitType == "TIME":
        return (
            driving.maxInitialDrivingSeconds if end == "ORIGIN"
            else driving.maxFinalDrivingSeconds
        )

    return (
        driving.maxInitialDrivingKm if end == "ORIGIN"
        else driving.maxFinalDrivingKm
    )


def straight_line_radius_km(
    driving: DrivingConstraint, limit: float | int
) -> float:
    """Farthest straight-line distance a station can be within the limit."""
    if driving.limitType == "DISTANCE":
        return float(limit)

    max_seconds = limit + DRIVING_TIME_TOLERANCE_SECONDS
    return MAX_DRIVING_SPEED_KMH * max_seconds / 3600


def _within_limit(
    distance: TransferCandidateDistance,
    driving: DrivingConstraint,
    limit: float | int,
) -> bool:
    """Whether a measured drive exists and is within the limit."""
    if not distance.routeExists or distance.durationSeconds is None:
        return False

    if driving.limitType == "TIME":
        # Same tolerance as the constraint filter.
        return (
            distance.durationSeconds
            <= limit + DRIVING_TIME_TOLERANCE_SECONDS
        )

    if distance.distanceMeters is None:
        return False

    return distance.distanceMeters / 1000 <= limit


def _find_candidates(
    point: Location,
    end: CandidateEnd,
    constraints: TravelConstraints,
    stations: list[TransitStation] | tuple[TransitStation, ...] | None,
    route_matrix: RouteMatrixFn,
) -> list[TransferCandidate]:
    driving = constraints.driving

    if driving is None:
        return []

    limit = _driving_limit(driving, end)

    if limit is None:
        return []

    requires_parking = driving.requiresParking and end == "ORIGIN"

    if stations is None:
        stations = load_stations()

    # 1. Straight-line pre-filter
    radius_km = straight_line_radius_km(driving, limit)
    shortlist = [
        station for station in stations
        if haversine_km(point, station.location) <= radius_km
    ]

    if not shortlist:
        return []

    # 2. Real drive times and distances, then limit.
    distances = route_matrix(
        point=point,
        stations=shortlist,
        end=end,
        mode="DRIVE",
    )

    candidates = [
        TransferCandidate(
            station=distance.station,
            end=end,
            requiresParking=requires_parking,
            durationSeconds=distance.durationSeconds,
            distanceMeters=distance.distanceMeters,
        )
        for distance in distances
        if _within_limit(distance, driving, limit)
    ]

    # Sort by quickest first for stable order
    candidates.sort(key=lambda c: (c.durationSeconds, c.station.id))
    return candidates


def find_origin_candidates(
    origin: Location,
    constraints: TravelConstraints,
    stations: list[TransitStation] | None = None,
    route_matrix: RouteMatrixFn = get_route_matrix,
) -> list[TransferCandidate]:
    """Stations the user can drive to from the origin within the limit."""
    return _find_candidates(
        origin, "ORIGIN", constraints, stations, route_matrix
    )


def find_destination_candidates(
    destination: Location,
    constraints: TravelConstraints,
    stations: list[TransitStation] | None = None,
    route_matrix: RouteMatrixFn = get_route_matrix,
) -> list[TransferCandidate]:
    """Stations the user can drive from to the destination within the limit."""
    return _find_candidates(
        destination, "DESTINATION", constraints,
        stations, route_matrix,
    )

