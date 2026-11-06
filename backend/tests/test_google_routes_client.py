from unittest.mock import patch, Mock

import pytest
import requests

from app.models.routing import Coordinates, TravelMode
from app.services.google_routes_client import (
    get_routes,
    GoogleRoutesError,
    GoogleRoutesQuotaError,
    GoogleRoutesAuthenticationError,
)


ORIGIN = Coordinates(latitude=43.4643, longitude=-80.5204)
DESTINATION = Coordinates(latitude=43.6453, longitude=-79.3806)


@patch("app.services.google_routes_client.requests.post")
def test_quota_exceeded(mock_post, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key")

    mock_post.return_value = Mock(status_code=429)

    with pytest.raises(GoogleRoutesQuotaError):
        get_routes(ORIGIN, DESTINATION, TravelMode.TRANSIT)


@patch("app.services.google_routes_client.requests.post")
def test_authentication_error(mock_post, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key")

    mock_post.return_value = Mock(status_code=403)

    with pytest.raises(GoogleRoutesAuthenticationError):
        get_routes(ORIGIN, DESTINATION, TravelMode.TRANSIT)


@patch("app.services.google_routes_client.requests.post")
def test_timeout(mock_post, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key")

    mock_post.side_effect = requests.Timeout()

    with pytest.raises(GoogleRoutesError, match="timed out"):
        get_routes(ORIGIN, DESTINATION, TravelMode.TRANSIT)
        

@pytest.mark.parametrize(
    "mode",
    [
        TravelMode.DRIVE,
        TravelMode.WALK,
        TravelMode.TRANSIT,
    ],
)
@patch("app.services.google_routes_client.requests.post")
def test_request_field_mask(mock_post, mode, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key")

    # Simulate a successful Google API response
    mock_post.return_value = Mock(status_code=200)
    mock_post.return_value.json.return_value = {
        "routes": []
    }

    # Call our client
    get_routes(ORIGIN, DESTINATION, mode)

    # Inspect the outgoing API request
    kwargs = mock_post.call_args.kwargs
    field_mask = kwargs["headers"]["X-Goog-FieldMask"]

    # Verify the correct travel mode was requested
    assert kwargs["json"]["travelMode"] == mode.value

    # Verify common route fields are requested
    assert "routes.duration" in field_mask.split(",")
    assert "routes.distanceMeters" in field_mask.split(",")
    assert "routes.legs.steps.travelMode" in field_mask.split(",")

    # Transit-specific fields should only be requested for TRANSIT
    if mode == TravelMode.TRANSIT:
        assert "routes.legs.steps.transitDetails" in field_mask.split(",")
    else:
        assert "routes.legs.steps.transitDetails" not in field_mask.split(",")

