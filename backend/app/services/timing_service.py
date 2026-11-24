
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ConnectionResult:
    isFeasible: bool
    connectionSeconds: int


def checkConnection(
    arrivalTime: datetime,
    departureTime: datetime,
    minBufferSeconds: int = 0,
) -> ConnectionResult:

    if (
        arrivalTime.utcoffset() is None
        or departureTime.utcoffset() is None
    ):
        raise ValueError(
            "Connection timestamps must be timezone-aware"
        )

    connectionSeconds = (
        departureTime - arrivalTime
    ).total_seconds()

    return ConnectionResult(
        isFeasible=connectionSeconds >= minBufferSeconds,
        connectionSeconds=int(connectionSeconds),
    )
