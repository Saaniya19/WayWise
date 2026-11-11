
from datetime import datetime, timezone, timedelta

import pytest

from app.services.timing_service import checkConnection


@pytest.mark.parametrize(
    "arrivalTime, departureTime, expectedSeconds, expectedFeasible",
    [
        (
            "2026-11-11T10:00:00Z",
            "2026-11-11T10:15:00Z",
            900,
            True
        ),
        (
            "2026-11-11T10:12:00Z",
            "2026-11-11T10:15:00Z",
            180,
            True
        ),
        (
            "2026-11-11T10:15:00Z",
            "2026-11-11T10:15:00Z",
            0,
            True
        ),
        (
            "2026-11-11T10:20:00Z",
            "2026-11-11T10:15:00Z",
            -300,
            False
        ),
        (
            "2026-11-11T23:55:00Z",
            "2026-11-12T00:10:00Z",
            900,
            True
        ),
    ]
)
def testCheckConnection(
    arrivalTime,
    departureTime,
    expectedSeconds,
    expectedFeasible
):
    result = checkConnection(
        datetime.fromisoformat(arrivalTime.replace("Z", "+00:00")),
        datetime.fromisoformat(departureTime.replace("Z", "+00:00"))
    )

    assert result.connectionSeconds == expectedSeconds
    assert result.isFeasible == expectedFeasible


def testDifferentTimezoneOffsets():
    result = checkConnection(
        arrivalTime=datetime.fromisoformat(
            "2026-11-11T10:00:00-05:00"
        ),
        departureTime=datetime.fromisoformat(
            "2026-11-11T15:15:00+00:00"
        )
    )

    assert result.connectionSeconds == 900
    assert result.isFeasible is True


def testRejectNaiveTimestamp():
    with pytest.raises(ValueError):
        checkConnection(
            arrivalTime=datetime(2026, 11, 11, 10, 0),
            departureTime=datetime(
                2026, 11, 11, 10, 15,
                tzinfo=timezone.utc
            )
        )
