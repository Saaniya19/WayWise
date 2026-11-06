from dotenv import load_dotenv
load_dotenv()

import os
from datetime import datetime, timezone

import requests

from app.models.routing import Coordinates, RouteResult, TravelMode
from app.services.google_routes_normalizer import normalize_routes
from app.config import GOOGLE_ROUTES_URL

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
