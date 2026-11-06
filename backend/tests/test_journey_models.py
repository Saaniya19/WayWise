
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models.journey import (
    TransitDetails,
    JourneySegment,
    Journey,
)


@pytest.fixture
def sampleWalkSegment():
    return JourneySegment(
        id="walk-1",
        kind="WALK",
        startLocation={
            "latitude": 43.4723,
            "longitude": -80.5449
        },
        endLocation={
            "latitude": 43.4730,
            "longitude": -80.5430
        },
        startTime="2026-10-22T14:00:00Z",
        endTime="2026-10-22T14:05:00Z",
        durationSeconds=300,
        distanceMeters=400,
        encodedPolyline=None,
        transitDetails=None
    )


@pytest.fixture
def sampleJourney(sampleWalkSegment):
    startLocation = sampleWalkSegment.startLocation
    stationLocation = sampleWalkSegment.endLocation

    destination = {
        "latitude": 43.4950,
        "longitude": -80.5200
    }

    waitSegment = JourneySegment(
        id="wait-1",
        kind="WAIT",
        startLocation=stationLocation,
        endLocation=stationLocation,
        startTime="2026-10-22T14:05:00Z",
        endTime="2026-10-22T14:10:00Z",
        durationSeconds=300,
        distanceMeters=None,
        encodedPolyline=None,
        transitDetails=None
    )

    transitSegment = JourneySegment(
        id="transit-1",
        kind="TRANSIT",
        startLocation=stationLocation,
        endLocation=destination,
        startTime="2026-10-22T14:10:00Z",
        endTime="2026-10-22T14:30:00Z",
        durationSeconds=1200,
        distanceMeters=6000,
        encodedPolyline=None,
        transitDetails=TransitDetails(
            agencyName="Grand River Transit",
            serviceName="Example Route",
            routeShortName="12",
            vehicleType="BUS",
            boardingStop=stationLocation,
            alightingStop=destination,
            headsign="Downtown",
            stopCount=10,
            timingBasis="SCHEDULED"
        )
    )

    return Journey(
        id="journey-1",
        journeyType="WALK_TRANSIT",
        segments=[
            sampleWalkSegment,
            waitSegment,
            transitSegment
        ],
        departureTime="2026-10-22T14:00:00Z",
        arrivalTime="2026-10-22T14:30:00Z",
        totalDurationSeconds=1800,
        transferCount=0
    )


def testValidWalkSegment(sampleWalkSegment):
    assert sampleWalkSegment.kind == "WALK"
    assert sampleWalkSegment.durationSeconds == 300
    assert sampleWalkSegment.transitDetails is None


def testSegmentSerialization(sampleWalkSegment):
    result = sampleWalkSegment.model_dump(mode="json")

    assert result["kind"] == "WALK"
    assert result["durationSeconds"] == 300
    assert result["startTime"] == "2026-10-22T14:00:00Z"


def testInvalidSegmentDuration(sampleWalkSegment):
    data = sampleWalkSegment.model_dump()
    data["durationSeconds"] = 600

    with pytest.raises(ValidationError):
        JourneySegment.model_validate(data)


@pytest.mark.parametrize(
    "field, value",
    [
        ("startTime", "2026-10-22T14:10:00Z"),
        ("endTime", "2026-10-22T13:55:00Z"),
        ("durationSeconds", -1),
        ("distanceMeters", -100),
        ("startTime", "2026-10-22T14:00:00"),
    ]
)
def testInvalidSegmentFields(sampleWalkSegment, field, value):
    data = sampleWalkSegment.model_dump()
    data[field] = value

    with pytest.raises(ValidationError):
        JourneySegment.model_validate(data)


def testWalkCannotContainTransitDetails(sampleWalkSegment):
    data = sampleWalkSegment.model_dump()

    data["transitDetails"] = {
        "agencyName": "GO Transit",
        "serviceName": "Kitchener Line",
        "routeShortName": "KI",
        "vehicleType": "HEAVY_RAIL",
        "boardingStop": data["startLocation"],
        "alightingStop": data["endLocation"],
        "headsign": "Union Station",
        "stopCount": 11,
        "timingBasis": "SCHEDULED",
    }

    with pytest.raises(ValidationError):
        JourneySegment.model_validate(data)


def testTransitRequiresDetails(sampleWalkSegment):
    data = sampleWalkSegment.model_dump()
    data["kind"] = "TRANSIT"

    with pytest.raises(ValidationError):
        JourneySegment.model_validate(data)


def testWaitCannotHaveDistance(sampleWalkSegment):
    data = sampleWalkSegment.model_dump()
    data["kind"] = "WAIT"

    with pytest.raises(ValidationError):
        JourneySegment.model_validate(data)


def testValidTransitDetails():
    transitDetails = TransitDetails(
        agencyName="Grand River Transit",
        serviceName="Westmount",
        routeShortName="12",
        vehicleType="BUS",
        boardingStop={
            "latitude": 43.402251,
            "longitude": -80.496634
        },
        alightingStop={
            "latitude": 43.433305,
            "longitude": -80.50988
        },
        headsign="University/King",
        stopCount=10,
        timingBasis="SCHEDULED"
    )

    assert transitDetails.routeShortName == "12"
    assert transitDetails.stopCount == 10
    assert transitDetails.vehicleType == "BUS"


@pytest.mark.parametrize("stopCount", [-1, 2.5, "10", True])
def testInvalidStopCount(stopCount):
    with pytest.raises(ValidationError):
        TransitDetails(
            agencyName="Grand River Transit",
            serviceName="Westmount",
            routeShortName="12",
            vehicleType="BUS",
            boardingStop={
                "latitude": 43.402251,
                "longitude": -80.496634
            },
            alightingStop={
                "latitude": 43.433305,
                "longitude": -80.50988
            },
            headsign="University/King",
            stopCount=stopCount,
            timingBasis="SCHEDULED"
        )


def testValidJourney(sampleJourney):
    assert sampleJourney.journeyType == "WALK_TRANSIT"
    assert len(sampleJourney.segments) == 3
    assert sampleJourney.totalDurationSeconds == 1800
    assert sampleJourney.transferCount == 0


@pytest.mark.parametrize(
    "field, value",
    [
        ("journeyType", "WALK_ONLY"),
        ("totalDurationSeconds", 1200),
        ("transferCount", 1),
        ("departureTime", "2026-10-22T14:05:00Z"),
        ("arrivalTime", "2026-10-22T14:35:00Z"),
    ]
)
def testInvalidJourneyFields(sampleJourney, field, value):
    data = sampleJourney.model_dump()
    data[field] = value

    with pytest.raises(ValidationError):
        Journey.model_validate(data)


def testJourneyRequiresSegments(sampleJourney):
    data = sampleJourney.model_dump()
    data["segments"] = []

    with pytest.raises(ValidationError):
        Journey.model_validate(data)


def testDuplicateSegmentIds(sampleJourney):
    data = sampleJourney.model_dump()

    data["segments"][1]["id"] = data["segments"][0]["id"]

    with pytest.raises(ValidationError):
        Journey.model_validate(data)


def testJourneyWithTimeGap(sampleJourney):
    data = sampleJourney.model_dump()

    # Shift WAIT forward by one minute.
    data["segments"][1]["startTime"] = "2026-10-22T14:06:00Z"
    data["segments"][1]["endTime"] = "2026-10-22T14:11:00Z"

    with pytest.raises(ValidationError):
        Journey.model_validate(data)
