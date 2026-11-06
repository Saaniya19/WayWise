'''
 The purpose of the Normalizer is to convert Google's API response into a 
 consistent format that the rest of WayWise can understand. Google returns 
 JSON with it's own field names, nesting and data types. We don't want the
 rest of our backend to depend directly on that structure. So we convert 
 into that into Python objects that follow the models in routing.py. 
'''

from datetime import datetime
from typing import Any

from app.models.routing import (
    Coordinates,
    Leg,
    Route,
    RouteResult,
    Segment,
    TransitDetails,
    TransitStop,
    TravelMode,
)


def parse_duration(value: str | None) -> int | None:
    """Convert Google's duration string (e.g. '125.5s') to seconds."""
    if value is None:
        return None

    try:
        return round(float(value.removesuffix("s")))
    except (ValueError, TypeError):
        return None


def parse_datetime(value: str | None) -> datetime | None:
    """Convert Google's RFC3339 timestamp into a datetime."""
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_coordinates(data: dict | None) -> Coordinates | None:
    if data is None:
        return None

    lat_lng = data.get("latLng", data)

    if not isinstance(lat_lng, dict):
        raise ValueError("Invalid coordinate structure")

    if "latitude" not in lat_lng or "longitude" not in lat_lng:
        raise ValueError("Incomplete coordinates: latitude or longitude missing")

    return Coordinates(
        latitude=lat_lng["latitude"],
        longitude=lat_lng["longitude"],
    )


def parse_transit_stop(data: dict | None) -> TransitStop | None:
    if not data:
        return None

    return TransitStop(
        name=data.get("name"),
        location=parse_coordinates(data.get("location")),
    )


def parse_transit_details(data: dict | None) -> TransitDetails | None:
    if not data:
        return None

    stop_details = data.get("stopDetails") or {}
    transit_line = data.get("transitLine") or {}
    agencies = transit_line.get("agencies") or []
    vehicle = transit_line.get("vehicle") or {}

    return TransitDetails(
        departure_stop=parse_transit_stop(
            stop_details.get("departureStop")
        ),
        arrival_stop=parse_transit_stop(
            stop_details.get("arrivalStop")
        ),
        departure_time=parse_datetime(
            stop_details.get("departureTime")
        ),
        arrival_time=parse_datetime(
            stop_details.get("arrivalTime")
        ),
        line_name=transit_line.get("nameShort")
        or transit_line.get("name"),
        agency_name=agencies[0].get("name") if agencies else None,
        vehicle_type=vehicle.get("type"),
    )


def normalize_segment(data: dict[str, Any]) -> Segment:
    mode = TravelMode(data["travelMode"])

    return Segment(
        mode=mode,
        duration_seconds=parse_duration(
            data.get("staticDuration")
        ),
        distance_meters=data.get("distanceMeters"),
        transit_details=parse_transit_details(
            data.get("transitDetails")
        ),
    )


def normalize_leg(data: dict[str, Any]) -> Leg:
    return Leg(
        segments=[
            normalize_segment(step)
            for step in data.get("steps", [])
        ]
    )


def normalize_route(data: dict[str, Any]) -> Route:
    legs = [
        normalize_leg(leg)
        for leg in data.get("legs", [])
    ]

    transit_segments = [
        segment
        for leg in legs
        for segment in leg.segments
        if segment.mode == TravelMode.TRANSIT
    ]

    transfer_count = (
        max(0, len(transit_segments) - 1)
        if transit_segments
        else 0
    )

    return Route(
        duration_seconds=parse_duration(data.get("duration")),
        distance_meters=data.get("distanceMeters"),
        legs=legs,
        transfer_count=transfer_count,
    )


def normalize_routes(response: dict[str, Any]) -> RouteResult:
    routes = []
    warnings = []

    if not response.get("routes"):
        return RouteResult(
            routes=[],
            warnings=["Google Routes API returned no routes"],
        )

    for index, route_data in enumerate(response["routes"]):
        try:
            routes.append(normalize_route(route_data))
        except (ValueError, TypeError, KeyError) as exc:
            warnings.append(
                f"Could not normalize route {index}: {exc}"
            )

    return RouteResult(routes=routes, warnings=warnings)
