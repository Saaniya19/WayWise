import pytest

from app.models.candidates import TransferCandidateDistance, TransitStation
from app.models.common import Location
from app.models.planning import DrivingConstraint, TravelConstraints
from app.services.constraint_filter import DRIVING_TIME_TOLERANCE_SECONDS
from app.services.transfer_candidates import (
    find_destination_candidates,
    find_origin_candidates,
    haversine_km,
    load_stations,
    parse_catalogue,
    straight_line_radius_km,
)


ORIGIN = Location(latitude=43.4643, longitude=-80.5204)       # Waterloo
DESTINATION = Location(latitude=43.6453, longitude=-79.3806)  # Union


def station(id, lat, lon, parking="free"):
    return TransitStation(
        id=id, name=id, location=Location(latitude=lat, longitude=lon),
        parkingStatus=parking,
    )


# Straight-line distances, roughly: Kitchener ~3 km from the origin,
# Guelph ~22 km, Milton ~53 km (and ~42 km from Union), Oshawa ~140 km.
# Union is at the destination.
KITCHENER = station("GO:KI", 43.4557, -80.4931)
GUELPH = station("GO:GL", 43.5452, -80.2489)
MILTON = station("GO:ML", 43.5180, -79.8737)
UNION = station("GO:UN", 43.6453, -79.3806, parking="none")
OSHAWA = station("GO:OS", 43.8706, -78.8848)
STATIONS = [KITCHENER, GUELPH, MILTON, UNION, OSHAWA]


class FakeMatrix:
    """Stands in for get_route_matrix. Drive time is 60 s per straight
    line km (about 60 km/h); distance is 1.3x the straight line.
    Stations whose id is in unreachable have no route."""

    def __init__(self, unreachable=()):
        self.calls = []
        self.unreachable = set(unreachable)

    def __call__(self, point, stations, end, mode):
        self.calls.append({"point": point, "stations": stations,
                           "end": end, "mode": mode})
        distances = []
        for station in stations:
            km = haversine_km(point, station.location)
            exists = station.id not in self.unreachable
            distances.append(TransferCandidateDistance(
                station=station, end=end, mode=mode,
                routeExists=exists,
                durationSeconds=round(km * 60) if exists else None,
                distanceMeters=round(km * 1300) if exists else None,
            ))
        return distances


def time_limits(initial=None, final=None, parking=True):
    return TravelConstraints(driving=DrivingConstraint(
        limitType="TIME", requiresParking=parking,
        maxInitialDrivingSeconds=initial, maxFinalDrivingSeconds=final))


def distance_limits(initial=None, final=None, parking=True):
    return TravelConstraints(driving=DrivingConstraint(
        limitType="DISTANCE", requiresParking=parking,
        maxInitialDrivingKm=initial, maxFinalDrivingKm=final))


def ids(candidates):
    return [c.station.id for c in candidates]


def test_origin_time_limit_keeps_stations_within_limit():
    matrix = FakeMatrix()
    # 30 minutes: Kitchener (~3 min) and Guelph (~22 min) qualify.
    # Milton (~53 min) passes the generous pre-filter but not the real check.
    result = find_origin_candidates(
        ORIGIN, time_limits(initial=30 * 60), stations=STATIONS,
        route_matrix=matrix)

    assert ids(result) == ["GO:KI", "GO:GL"]
    assert all(c.end == "ORIGIN" for c in result)
    assert result[0].durationSeconds < result[1].durationSeconds


def test_origin_requests_drive_from_origin_to_stations():
    matrix = FakeMatrix()
    find_origin_candidates(ORIGIN, time_limits(initial=30 * 60),
                           stations=STATIONS, route_matrix=matrix)

    [call] = matrix.calls
    assert call["point"] == ORIGIN
    assert call["end"] == "ORIGIN"
    assert call["mode"] == "DRIVE"
    # Oshawa is far outside the straight-line radius, so it is never sent.
    assert OSHAWA not in call["stations"]


def test_destination_requests_drive_from_stations_to_destination():
    matrix = FakeMatrix()
    result = find_destination_candidates(
        DESTINATION, time_limits(final=50 * 60), stations=STATIONS,
        route_matrix=matrix)

    [call] = matrix.calls
    assert call["point"] == DESTINATION
    assert call["end"] == "DESTINATION"
    assert "GO:ML" in ids(result)
    assert "GO:KI" not in ids(result)
    assert all(c.end == "DESTINATION" for c in result)


def test_time_limit_allows_constraint_filter_tolerance():
    # Guelph is ~22 min away by the fake matrix.
    guelph_seconds = round(haversine_km(ORIGIN, GUELPH.location) * 60)
    just_under = guelph_seconds - DRIVING_TIME_TOLERANCE_SECONDS + 1
    just_over = guelph_seconds - DRIVING_TIME_TOLERANCE_SECONDS - 1

    kept = find_origin_candidates(ORIGIN, time_limits(initial=just_under),
                                  stations=[GUELPH], route_matrix=FakeMatrix())
    dropped = find_origin_candidates(ORIGIN, time_limits(initial=just_over),
                                     stations=[GUELPH],
                                     route_matrix=FakeMatrix())
    assert ids(kept) == ["GO:GL"]
    assert dropped == []


def test_distance_limit_uses_real_road_distance():
    # Guelph: ~22 km straight line, ~29 km by the fake road distance.
    straight = haversine_km(ORIGIN, GUELPH.location)
    road = straight * 1.3

    # Passes the straight-line pre-filter but fails on road distance.
    assert find_origin_candidates(
        ORIGIN, distance_limits(initial=(straight + road) / 2),
        stations=[GUELPH], route_matrix=FakeMatrix()) == []

    assert ids(find_origin_candidates(
        ORIGIN, distance_limits(initial=road + 1),
        stations=[GUELPH], route_matrix=FakeMatrix())) == ["GO:GL"]


def test_no_driving_constraint_returns_nothing():
    matrix = FakeMatrix()
    assert find_origin_candidates(ORIGIN, TravelConstraints(),
                                  stations=STATIONS,
                                  route_matrix=matrix) == []
    assert matrix.calls == []


def test_missing_limit_for_that_end_returns_nothing():
    matrix = FakeMatrix()
    constraints = time_limits(initial=30 * 60)
    assert find_destination_candidates(DESTINATION, constraints,
                                       stations=STATIONS,
                                       route_matrix=matrix) == []
    assert matrix.calls == []


def test_nothing_in_range_skips_google():
    matrix = FakeMatrix()
    assert find_origin_candidates(ORIGIN, time_limits(initial=60),
                                  stations=[MILTON],
                                  route_matrix=matrix) == []
    assert matrix.calls == []


def test_unreachable_station_is_dropped():
    matrix = FakeMatrix(unreachable={"GO:KI"})
    assert find_origin_candidates(ORIGIN, time_limits(initial=30 * 60),
                                  stations=[KITCHENER],
                                  route_matrix=matrix) == []


def test_drop_off_does_not_require_parking():
    near_union = Location(latitude=43.64, longitude=-79.39)
    drop_off = find_origin_candidates(
        near_union, time_limits(initial=10 * 60, parking=False),
        stations=STATIONS, route_matrix=FakeMatrix())

    assert ids(drop_off) == ["GO:UN"]
    assert drop_off[0].requiresParking is False


def test_parking_only_applies_at_origin_end():
    result = find_destination_candidates(
        DESTINATION, time_limits(final=10 * 60), stations=STATIONS,
        route_matrix=FakeMatrix())

    # Union has no parking but is still a valid destination station.
    assert ids(result) == ["GO:UN"]
    assert result[0].requiresParking is False


@pytest.mark.parametrize("limit_type, limit, expected_km", [
    ("DISTANCE", 20, 20),
    ("TIME", 3600 - DRIVING_TIME_TOLERANCE_SECONDS, 130),
])
def test_straight_line_radius(limit_type, limit, expected_km):
    driving = (time_limits(initial=limit) if limit_type == "TIME"
               else distance_limits(initial=limit)).driving
    assert straight_line_radius_km(driving, limit) == pytest.approx(expected_km)


def test_parse_catalogue_links_parking_sites():
    data = {
        "transitStations": [{
            "id": "GO:AC", "name": "Acton GO", "latitude": 43.63,
            "longitude": -80.03, "services": ["GO"],
            "parking": {"status": "free"},
        }],
        "parkingSites": [{
            "id": "GO:AC:parking:main", "stationId": "GO:AC",
            "latitude": None, "longitude": None,
        }],
    }
    [acton] = parse_catalogue(data)

    assert acton.parkingStatus == "free"
    assert acton.parkingSiteId == "GO:AC:parking:main"


def test_real_catalogue_loads():
    stations = load_stations()
    assert len(stations) > 0
    assert all(isinstance(s, TransitStation) for s in stations)

