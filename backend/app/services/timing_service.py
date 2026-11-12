
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ConnectionResult:
    isFeasible: bool
    connectionSeconds: int


def checkConnection(
    arrivalTime: datetime,
    departureTime: datetime
) -> ConnectionResult:
    # Both timestamps must include timezone information.
    if (
        arrivalTime.utcoffset() is None
        or departureTime.utcoffset() is None
    ):
        raise ValueError(
            "Connection timestamps must be timezone-aware"
        )

    # Calculate the time between arrival and departure.
    connectionSeconds = int(
        (departureTime - arrivalTime).total_seconds()
    )

    return ConnectionResult(
        isFeasible=connectionSeconds >= 60,
        connectionSeconds=connectionSeconds
    )
