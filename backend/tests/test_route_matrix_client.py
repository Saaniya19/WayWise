from unittest.mock import Mock, patch

import pytest
import requests

from app.models.candidates import TransitStation
from app.models.common import Location
from app.services.google_routes_client import (
    ROUTE_MATRIX_MAX_ELEMENTS,
    GoogleRoutesAuthenticationError,
    GoogleRoutesError,
    GoogleRoutesQuotaError,
    get_route_matrix,
)


ORIGIN = Location(latitude=43.4643, longitude=-80.5204)
DESTINATION = Location(latitude=43.6453, longitude=-79.3806)


def station(id, lat, lon):
    return TransitStation(id=id, name=id,
                          location=Location(latitude=lat, longitude=lon))


KITCHENER = station("GO:KI", 43.4557, -80.4931)
GUELPH = station("GO:GL", 43.5468, -80.2489)


def ok_response(payload):
    return Mock(status_code=200, json=Mock(return_value=payload),
                raise_for_status=Mock())


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key")


@patch("app.services.google_routes_client.requests.post")
def test_origin_leg_returns_one_distance_per_station(mock_post, api_key):
    # Google answers out of order; each result is matched to its station.
    mock_post.return_value = ok_response([
        {"originIndex": 0, "destinationIndex": 1, "status": {},
         "condition": "ROUTE_EXISTS", "duration": "1500s",
         "distanceMeters": 30000},
        {"originIndex": 0, "destinationIndex": 0, "status": {},
         "condition": "ROUTE_EXISTS", "duration": "420.4s",
         "distanceMeters": 4100},
    ])

    by_id = {d.station.id: d for d in get_route_matrix(
        ORIGIN, [KITCHENER, GUELPH], "ORIGIN", "DRIVE")}
    kitchener, guelph = by_id["GO:KI"], by_id["GO:GL"]

    assert (kitchener.station, kitchener.end, kitchener.mode) == (
        KITCHENER, "ORIGIN", "DRIVE")
    assert kitchener.routeExists
    assert kitchener.durationSeconds == 420
    assert kitchener.distanceMeters == 4100
    assert guelph.station == GUELPH
    assert guelph.durationSeconds == 1500


@patch("app.services.google_routes_client.requests.post")
def test_origin_leg_goes_from_point_to_stations(mock_post, api_key):
    mock_post.return_value = ok_response([])

    get_route_matrix(ORIGIN, [KITCHENER, GUELPH], "ORIGIN", "DRIVE")

    body = mock_post.call_args.kwargs["json"]
    assert len(body["origins"]) == 1
    assert body["origins"][0]["waypoint"]["location"]["latLng"] == {
        "latitude": ORIGIN.latitude, "longitude": ORIGIN.longitude}
    assert len(body["destinations"]) == 2


@patch("app.services.google_routes_client.requests.post")
def test_destination_leg_goes_from_stations_to_point(mock_post, api_key):
    # At the DESTINATION end, stations are the request's origins.
    mock_post.return_value = ok_response([
        {"originIndex": 1, "destinationIndex": 0, "status": {},
         "condition": "ROUTE_EXISTS", "duration": "900s",
         "distanceMeters": 12000},
    ])

    [guelph] = get_route_matrix(
        DESTINATION, [KITCHENER, GUELPH], "DESTINATION", "DRIVE")

    body = mock_post.call_args.kwargs["json"]
    assert len(body["origins"]) == 2
    assert body["destinations"][0]["waypoint"]["location"]["latLng"] == {
        "latitude": DESTINATION.latitude, "longitude": DESTINATION.longitude}
    assert guelph.station == GUELPH
    assert guelph.end == "DESTINATION"
    assert guelph.durationSeconds == 900


@patch("app.services.google_routes_client.requests.post")
def test_unreachable_and_error_elements(mock_post, api_key):
    mock_post.return_value = ok_response([
        {"originIndex": 0, "destinationIndex": 0,
         "condition": "ROUTE_NOT_FOUND"},
        {"originIndex": 0, "destinationIndex": 1,
         "status": {"code": 5, "message": "not found"}},
    ])

    distances = get_route_matrix(ORIGIN, [KITCHENER, GUELPH], "ORIGIN",
                                 "DRIVE")

    assert all(not d.routeExists for d in distances)
    assert all(d.durationSeconds is None for d in distances)


@patch("app.services.google_routes_client.requests.post")
def test_request_body_and_headers(mock_post, api_key):
    mock_post.return_value = ok_response([])

    get_route_matrix(ORIGIN, [KITCHENER], "ORIGIN", "DRIVE")

    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert body["travelMode"] == "DRIVE"
    # No departure time yet: Google uses "now", with current traffic.
    assert "departureTime" not in body
    assert body["routingPreference"] == "TRAFFIC_AWARE"
    mask = kwargs["headers"]["X-Goog-FieldMask"]
    for field in ("originIndex", "destinationIndex", "duration",
                  "distanceMeters", "condition", "status"):
        assert field in mask


@patch("app.services.google_routes_client.requests.post")
def test_large_station_lists_are_batched(mock_post, api_key):
    many = [station(f"S{i}", 43.4557, -80.4931)
            for i in range(ROUTE_MATRIX_MAX_ELEMENTS + 5)]
    # Each request answers for its first station only.
    mock_post.return_value = ok_response([
        {"status": {}, "condition": "ROUTE_EXISTS", "duration": "60s"}])

    distances = get_route_matrix(ORIGIN, many, "ORIGIN", "DRIVE")

    assert mock_post.call_count == 2
    # Positions restart at 0 in each batch, so the second result is the
    # first station of the second batch.
    assert [d.station.id for d in distances] == [
        "S0", f"S{ROUTE_MATRIX_MAX_ELEMENTS}"]


def test_no_stations_makes_no_request():
    with patch("app.services.google_routes_client.requests.post") as post:
        assert get_route_matrix(ORIGIN, [], "ORIGIN", "DRIVE") == []
        post.assert_not_called()


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    with pytest.raises(GoogleRoutesError, match="GOOGLE_MAPS_API_KEY"):
        get_route_matrix(ORIGIN, [KITCHENER], "ORIGIN", "DRIVE")


@pytest.mark.parametrize(
    "status_code, error",
    [(429, GoogleRoutesQuotaError), (403, GoogleRoutesAuthenticationError)],
)
@patch("app.services.google_routes_client.requests.post")
def test_http_errors(mock_post, status_code, error, api_key):
    mock_post.return_value = Mock(status_code=status_code)
    with pytest.raises(error):
        get_route_matrix(ORIGIN, [KITCHENER], "ORIGIN", "DRIVE")


@patch("app.services.google_routes_client.requests.post")
def test_timeout(mock_post, api_key):
    mock_post.side_effect = requests.Timeout()
    with pytest.raises(GoogleRoutesError, match="timed out"):
        get_route_matrix(ORIGIN, [KITCHENER], "ORIGIN", "DRIVE")


@patch("app.services.google_routes_client.requests.post")
def test_non_list_response(mock_post, api_key):
    mock_post.return_value = ok_response({"error": "nope"})
    with pytest.raises(GoogleRoutesError, match="unexpected"):
        get_route_matrix(ORIGIN, [KITCHENER], "ORIGIN", "DRIVE")


@patch("app.services.google_routes_client.requests.post")
def test_zero_indexes_may_be_omitted(mock_post, api_key):
    # Google's JSON can leave out fields whose value is 0.
    mock_post.return_value = ok_response([
        {"status": {}, "condition": "ROUTE_EXISTS",
         "duration": "160s", "distanceMeters": 822},
    ])

    [kitchener] = get_route_matrix(ORIGIN, [KITCHENER], "ORIGIN", "DRIVE")

    assert kitchener.routeExists
    assert kitchener.durationSeconds == 160
