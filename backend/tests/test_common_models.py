
import pytest

from pydantic import ValidationError

from app.models.common import Location


def testValidLocation():
    location = Location(
        latitude=43.4723,
        longitude=-80.5449,
        name="University of Waterloo"
    )

    assert location.latitude == 43.4723
    assert location.longitude == -80.5449
    assert location.name == "University of Waterloo"
    assert location.placeId is None


def testLocationWithoutOptionalFields():
    location = Location(
        latitude=43.4723,
        longitude=-80.5449
    )

    assert location.name is None
    assert location.placeId is None


@pytest.mark.parametrize(
    "latitude",
    [-91, 91, float("nan"), float("inf")]
)
def testInvalidLatitude(latitude):
    with pytest.raises(ValidationError):
        Location(
            latitude=latitude,
            longitude=-80.5449
        )


@pytest.mark.parametrize(
    "longitude",
    [-181, 181, float("nan"), float("-inf")]
)
def testInvalidLongitude(longitude):
    with pytest.raises(ValidationError):
        Location(
            latitude=43.4723,
            longitude=longitude
        )


def testMissingCoordinates():
    with pytest.raises(ValidationError):
        Location(name="University of Waterloo")


def testLocationSerialization():
    location = Location(
        latitude=43.4723,
        longitude=-80.5449,
        placeId="test-place-id"
    )

    result = location.model_dump()

    assert result["latitude"] == 43.4723
    assert result["longitude"] == -80.5449
    assert result["placeId"] == "test-place-id"
