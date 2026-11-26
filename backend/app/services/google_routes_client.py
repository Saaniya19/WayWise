from dotenv import load_dotenv
load_dotenv()

import os
from datetime import datetime, timezone

import requests

from app.models.candidates import (
    AccessMode,
    CandidateEnd,
    TransferCandidateDistance,
    TransitStation,
)
from app.models.common import Location
from app.models.routing import Coordinates, RouteResult, TravelMode
from app.services.google_routes_normalizer import (
    normalize_route_matrix,
    normalize_routes,
)
from app.config import GOOGLE_ROUTE_MATRIX_URL, GOOGLE_ROUTES_URL

BASE_FIELDS = [
    "routes.duration",
    "routes.distanceMeters",
    "routes.legs.steps.travelMode",
    "routes.legs.steps.staticDuration",
    "routes.legs.steps.distanceMeters",
]

TRANSIT_FIELDS = [
    "routes.legs.steps.transitDetails",
]


def get_field_mask(mode: TravelMode) -> str:
    fields = BASE_FIELDS.copy()

    if mode == TravelMode.TRANSIT:
        fields.extend(TRANSIT_FIELDS)

    return ",".join(fields)



class GoogleRoutesError(Exception):
    """Raised when the Google Routes API request fails."""

class GoogleRoutesQuotaError(GoogleRoutesError):
    pass

class GoogleRoutesAuthenticationError(GoogleRoutesError):
    pass


def _build_request_body(
    origin: Coordinates,
    destination: Coordinates,
    mode: TravelMode,
    departure_time: datetime | None = None,
) -> dict:
    body = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": origin.latitude,
                    "longitude": origin.longitude,
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": destination.latitude,
                    "longitude": destination.longitude,
                }
            }
        },
        "travelMode": mode.value,
        "computeAlternativeRoutes": True,
    }

    if departure_time is not None:
        if departure_time.tzinfo is None:
            raise ValueError(
                "departure_time must be timezone-aware"
            )

        body["departureTime"] = (
            departure_time.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    return body


def get_routes(
    origin: Coordinates,
    destination: Coordinates,
    mode: TravelMode,
    departure_time: datetime | None = None,
) -> RouteResult:

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    if not api_key:
        raise GoogleRoutesError(
            "GOOGLE_MAPS_API_KEY environment variable is missing"
        )

    body = _build_request_body(
        origin, destination, mode, departure_time
    )

    if departure_time is not None:
        if departure_time.tzinfo is None:
            raise ValueError(
                "departure_time must be timezone-aware"
            )

        body["departureTime"] = (
            departure_time.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": get_field_mask(mode),
    }

    try:
        response = requests.post(
            GOOGLE_ROUTES_URL,
            headers=headers,
            json=body,
            timeout=15,
        )
        
        if response.status_code == 429:
            raise GoogleRoutesQuotaError("Google Routes API quota exceeded")

        if response.status_code in (401, 403):
            raise GoogleRoutesAuthenticationError(
                "Google Routes API authentication or permission error"
            )

        response.raise_for_status()
        data = response.json()

    except requests.Timeout as exc:
        raise GoogleRoutesError(
            "Google Routes API request timed out"
        ) from exc

    except requests.RequestException as exc:
        raise GoogleRoutesError(
            f"Google Routes API request failed: {exc}"
        ) from exc

    except ValueError as exc:
        raise GoogleRoutesError(
            "Google Routes API returned invalid JSON"
        ) from exc

    return normalize_routes(data)

ROUTE_MATRIX_MAX_ELEMENTS = 100

ROUTE_MATRIX_FIELD_MASK = ",".join([
    "originIndex",
    "destinationIndex",
    "status",
    "condition",
    "duration",
    "distanceMeters",
])


def _matrix_waypoint(point: Location) -> dict:
    return {
        "waypoint": {
            "location": {
                "latLng": {
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                }
            }
        }
    }


def get_route_matrix(
    point: Location,
    stations: list[TransitStation],
    end: CandidateEnd,
    mode: AccessMode,
) -> list[TransferCandidateDistance]:
    """Travel time and distance between point and each station.

    end sets the direction: ORIGIN is point -> station, DESTINATION is
    station -> point.
    """
    distances = []

    for start in range(0, len(stations), ROUTE_MATRIX_MAX_ELEMENTS):
        batch = slice(start, start + ROUTE_MATRIX_MAX_ELEMENTS)
        batch_stations = stations[batch]
        locations = [station.location for station in batch_stations]

        if end == "ORIGIN":
            data = _request_route_matrix([point], locations, mode)
        else:
            data = _request_route_matrix(locations, [point], mode)

        distances.extend(normalize_route_matrix(
            data, end, mode, batch_stations
        ))

    return distances


def _request_route_matrix(
    origins: list[Location],
    destinations: list[Location],
    mode: AccessMode,
) -> list[dict]:
    """Send one Route Matrix request and return Google's raw JSON list."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    if not api_key:
        raise GoogleRoutesError(
            "GOOGLE_MAPS_API_KEY environment variable is missing"
        )

    travel_mode = TravelMode(mode)
    body = {
        "origins": [_matrix_waypoint(o) for o in origins],
        "destinations": [_matrix_waypoint(d) for d in destinations],
        "travelMode": travel_mode.value,
    }

    # Use current traffic for drive times. Google only allows this for
    # driving, and bills these requests at its higher "Pro" rate.
    if travel_mode == TravelMode.DRIVE:
        body["routingPreference"] = "TRAFFIC_AWARE"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ROUTE_MATRIX_FIELD_MASK,
    }

    try:
        response = requests.post(
            GOOGLE_ROUTE_MATRIX_URL,
            headers=headers,
            json=body,
            timeout=15,
        )

        if response.status_code == 429:
            raise GoogleRoutesQuotaError(
                "Google Route Matrix API quota exceeded"
            )

        if response.status_code in (401, 403):
            raise GoogleRoutesAuthenticationError(
                "Google Route Matrix API authentication or permission error"
            )

        response.raise_for_status()
        data = response.json()

    except requests.Timeout as exc:
        raise GoogleRoutesError(
            "Google Route Matrix API request timed out"
        ) from exc

    except requests.RequestException as exc:
        raise GoogleRoutesError(
            f"Google Route Matrix API request failed: {exc}"
        ) from exc

    except ValueError as exc:
        raise GoogleRoutesError(
            "Google Route Matrix API returned invalid JSON"
        ) from exc

    if not isinstance(data, list):
        raise GoogleRoutesError(
            "Google Route Matrix API returned an unexpected response"
        )

    return data
