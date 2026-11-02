from app.services.google_routes_normalizer import normalize_routes


def test_empty_response():
    result = normalize_routes({})

    assert len(result.routes) == 0
    assert len(result.warnings) > 0


def test_missing_optional_fields():
    response = {
        "routes": [
            {
                "duration": "120s",
                "legs": [
                    {
                        "steps": [
                            {"travelMode": "WALK"}
                        ]
                    }
                ]
            }
        ]
    }

    result = normalize_routes(response)

    assert len(result.routes) == 1
    assert result.routes[0].duration_seconds == 120

    segment = result.routes[0].legs[0].segments[0]

    assert segment.mode.value == "WALK"
    assert segment.distance_meters is None
    assert segment.duration_seconds is None


def test_invalid_route():
    response = {
        "routes": [
            {
                "legs": [
                    {
                        "steps": [
                            {"travelMode": "INVALID"}
                        ]
                    }
                ]
            }
        ]
    }

    result = normalize_routes(response)

    assert len(result.routes) == 0
    assert len(result.warnings) > 0


# This test uses a fake Google response that has the same structure as the real API. No API key or network request is required.
# The test verifies that the normalizer preserves different travel modes within a single leg.
def test_transit_details():
    response = {
        "routes": [
            {
                "duration": "3600s",
                "distanceMeters": 25000,
                "legs": [
                    {
                        "steps": [
                            {
                                "travelMode": "WALK",
                                "staticDuration": "300s",
                                "distanceMeters": 400,
                            },
                            {
                                "travelMode": "TRANSIT",
                                "staticDuration": "2400s",
                                "distanceMeters": 20000,
                                "transitDetails": {
                                    "stopDetails": {
                                        "departureStop": {
                                            "name": "Kitchener GO",
                                            "location": {
                                                "latLng": {
                                                    "latitude": 43.455,
                                                    "longitude": -80.493,
                                                }
                                            },
                                        },
                                        "arrivalStop": {
                                            "name": "Bramalea GO",
                                            "location": {
                                                "latLng": {
                                                    "latitude": 43.700,
                                                    "longitude": -79.690,
                                                }
                                            },
                                        },
                                        "departureTime": "2026-11-02T15:00:00Z",
                                        "arrivalTime": "2026-11-02T15:40:00Z",
                                    },
                                    "transitLine": {
                                        "nameShort": "KI",
                                        "agencies": [
                                            {"name": "GO Transit"}
                                        ],
                                        "vehicle": {
                                            "type": "RAIL"
                                        },
                                    },
                                },
                            },
                            {
                                "travelMode": "WALK",
                                "staticDuration": "300s",
                                "distanceMeters": 350,
                            },
                        ]
                    }
                ],
            }
        ]
    }

    result = normalize_routes(response)

    assert len(result.routes) == 1
    assert result.warnings == []

    route = result.routes[0]

    # Route-level information
    assert route.duration_seconds == 3600
    assert route.distance_meters == 25000
    assert route.transfer_count == 0

    # Leg and segment structure
    assert len(route.legs) == 1
    assert len(route.legs[0].segments) == 3

    segments = route.legs[0].segments

    assert segments[0].mode.value == "WALK"
    assert segments[1].mode.value == "TRANSIT"
    assert segments[2].mode.value == "WALK"

    # Transit details
    transit = segments[1].transit_details

    assert transit is not None
    assert transit.departure_stop.name == "Kitchener GO"
    assert transit.arrival_stop.name == "Bramalea GO"

    assert transit.departure_stop.location.latitude == 43.455
    assert transit.arrival_stop.location.longitude == -79.690

    assert transit.departure_time.isoformat() == (
        "2026-11-02T15:00:00+00:00"
    )
    assert transit.arrival_time.isoformat() == (
        "2026-11-02T15:40:00+00:00"
    )

    assert transit.line_name == "KI"
    assert transit.agency_name == "GO Transit"
    assert transit.vehicle_type == "RAIL"


# Testing that the normalizer calculates transfers by counting transit segments and subtracting one
def test_transfer_count():
    response = {
        "routes": [
            {
                "legs": [
                    {
                        "steps": [
                            {"travelMode": "WALK"},
                            {"travelMode": "TRANSIT"},
                            {"travelMode": "WALK"},
                            {"travelMode": "TRANSIT"},
                            {"travelMode": "WALK"},
                            {"travelMode": "TRANSIT"},
                        ]
                    }
                ]
            }
        ]
    }

    result = normalize_routes(response)

    assert len(result.routes) == 1
    assert result.routes[0].transfer_count == 2


# Google might occasionally omit optional fields such as the transit agency, vehicle type, or stop coordinates
# Testing that the normalizer still returns a valid route
def test_partial_transit_details():
    response = {
        "routes": [
            {
                "legs": [
                    {
                        "steps": [
                            {
                                "travelMode": "TRANSIT",
                                "transitDetails": {
                                    "transitLine": {
                                        "name": "Kitchener Line"
                                    }
                                },
                            }
                        ]
                    }
                ]
            }
        ]
    }

    result = normalize_routes(response)

    assert len(result.routes) == 1
    assert result.warnings == []

    transit = result.routes[0].legs[0].segments[0].transit_details

    assert transit.line_name == "Kitchener Line"
    assert transit.agency_name is None
    assert transit.vehicle_type is None
    assert transit.departure_stop is None
    assert transit.arrival_stop is None
    assert transit.departure_time is None
    assert transit.arrival_time is None

