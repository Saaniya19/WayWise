
import pytest

from datetime import datetime, timezone
from pydantic import ValidationError

from app.models.planning import (
    DrivingConstraint,
    TransitConstraint,
    TravelConstraints,
    PlanningRequest,
    PlanningError,
    PlanningResponse,
)


@pytest.mark.parametrize(
    "limitType, maxValue",
    [
        ("TIME", 20),
        ("DISTANCE", 15.5),
    ]
)
def testValidDrivingConstraint(limitType, maxValue):
    constraint = DrivingConstraint(
        limitType=limitType,
        maxValue=maxValue
    )

    assert constraint.limitType == limitType
    assert constraint.maxValue == maxValue


@pytest.mark.parametrize(
    "limitType, maxValue",
    [
        ("SPEED", 20),
        ("TIME", 0),
        ("DISTANCE", -5),
        ("TIME", float("inf")),
        ("TIME", float("nan")),
    ]
)
def testInvalidDrivingConstraint(limitType, maxValue):
    with pytest.raises(ValidationError):
        DrivingConstraint(
            limitType=limitType,
            maxValue=maxValue
        )


@pytest.mark.parametrize("maxTransfers", [0, 1, 3])
def testValidTransitConstraint(maxTransfers):
    constraint = TransitConstraint(maxTransfers=maxTransfers)

    assert constraint.maxTransfers == maxTransfers


@pytest.mark.parametrize("maxTransfers", [-1, 1.5, "2", True])
def testInvalidTransitConstraint(maxTransfers):
    with pytest.raises(ValidationError):
        TransitConstraint(maxTransfers=maxTransfers)



def testValidTravelConstraints():
    constraints = TravelConstraints(
        maxWalkingSegmentMinutes=10,
        driving=DrivingConstraint(
            limitType="TIME",
            maxValue=20
        ),
        transit=TransitConstraint(maxTransfers=1)
    )

    assert constraints.maxWalkingSegmentMinutes == 10
    assert constraints.driving.limitType == "TIME"
    assert constraints.transit.maxTransfers == 1


def testWalkingOnlyConstraints():
    constraints = TravelConstraints(
        maxWalkingSegmentMinutes=15,
        driving=None,
        transit=None
    )

    assert constraints.driving is None
    assert constraints.transit is None


@pytest.mark.parametrize(
    "walkingMinutes",
    [0, -5, float("inf"), float("nan")]
)
def testInvalidWalkingLimit(walkingMinutes):
    with pytest.raises(ValidationError):
        TravelConstraints(
            maxWalkingSegmentMinutes=walkingMinutes,
            driving=None,
            transit=None
        )


def testMissingModeFields():
    with pytest.raises(ValidationError):
        TravelConstraints(maxWalkingSegmentMinutes=10)



def testValidPlanningRequest():
    request = PlanningRequest(
        origin={
            "latitude": 43.4723,
            "longitude": -80.5449
        },
        destination={
            "latitude": 43.6452,
            "longitude": -79.3806
        },
        constraints={
            "maxWalkingSegmentMinutes": 10,
            "driving": {
                "limitType": "TIME",
                "maxValue": 30
            },
            "transit": {
                "maxTransfers": 1
            }
        }
    )

    assert request.origin.latitude == 43.4723
    assert request.constraints.driving.maxValue == 30

    result = request.model_dump()

    assert "parkingDurationMinutes" not in result
    assert "maxWalkingSegmentMinutes" in result["constraints"]


def testMissingDestination():
    with pytest.raises(ValidationError):
        PlanningRequest(
            origin={
                "latitude": 43.4723,
                "longitude": -80.5449
            },
            constraints={
                "maxWalkingSegmentMinutes": 10,
                "driving": None,
                "transit": None
            }
        )


def testPlanningError():
    error = PlanningError(
        code="NO_VALID_ROUTES",
        message="No journeys satisfy the requested constraints.",
        journeyId=None
    )

    assert error.code == "NO_VALID_ROUTES"
    assert error.journeyId is None


def testEmptyPlanningResponse():
    response = PlanningResponse(
        requestId="request-123",
        departureTime=datetime.now(timezone.utc),
        journeys=[],
        isPartial=False,
        errors=[]
    )

    assert response.requestId == "request-123"
    assert response.journeys == []
    assert response.errors == []
    assert response.isPartial is False


def testResponseWithError():
    response = PlanningResponse(
        requestId="request-123",
        departureTime=datetime.now(timezone.utc),
        errors=[
            PlanningError(
                code="PROVIDER_FAILURE",
                message="Transit route search failed.",
                journeyId=None
            )
        ],
        isPartial=True
    )

    assert response.isPartial is True
    assert len(response.errors) == 1
    assert response.errors[0].code == "PROVIDER_FAILURE"


def testNaiveDepartureTime():
    with pytest.raises(ValidationError):
        PlanningResponse(
            requestId="request-123",
            departureTime=datetime(2026, 10, 22, 10, 0),
        )
