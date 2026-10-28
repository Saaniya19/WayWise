
from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.common import Location

SegmentKind = Literal[
    "DRIVE",
    "WALK",
    "TRANSIT",
    "WAIT",
    "PARK"
]

class TransitDetails(BaseModel):
    agencyName: str | None
    serviceName: str | None
    routeShortName: str | None
    vehicleType: str | None
    boardingStop: Location
    alightingStop: Location
    headsign: str | None
    stopCount: int | None = Field(default=None, ge=0, strict=True)
    timingBasis: Literal[
        "SCHEDULED",
        "REALTIME",
        "UNKNOWN"
    ]


class JourneySegment(BaseModel):
    id: str
    kind: SegmentKind

    startLocation: Location
    endLocation: Location

    startTime: datetime
    endTime: datetime

    durationSeconds: int = Field(ge=0, strict=True)
    distanceMeters: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False
    )

    encodedPolyline: str | None
    transitDetails: TransitDetails | None

    @model_validator(mode="after")
    def validateSegment(self):
        # Both timestamps must include timezone information
        if (
            self.startTime.utcoffset() is None
            or self.endTime.utcoffset() is None
        ):
            raise ValueError(
                "Segment timestamps must include timezone information"
            )

        # The end cannot occur before the start
        if self.endTime < self.startTime:
            raise ValueError(
                "endTime cannot be earlier than startTime"
            )

        # Duration must agree with the timestamps
        actualDuration = (
            self.endTime - self.startTime
        ).total_seconds()

        if actualDuration != self.durationSeconds:
            raise ValueError(
                "durationSeconds must match the difference "
                "between startTime and endTime"
            )

        # Transit details are only applicable to transit segments
        if self.kind == "TRANSIT":
            if self.transitDetails is None:
                raise ValueError(
                    "TRANSIT segments must include transitDetails"
                )
        elif self.transitDetails is not None:
            raise ValueError(
                "Only TRANSIT segments can include transitDetails"
            )

        # Waiting and parking are stationary activities
        if self.kind in ("WAIT", "PARK"):
            if self.distanceMeters is not None:
                raise ValueError(
                    "WAIT and PARK segments must have distanceMeters=None"
                )

        return self


JourneyType = Literal[
    "WALK_ONLY",
    "WALK_TRANSIT",
    "DRIVE_WALK",
    "DRIVE_WALK_TRANSIT"
]


class Journey(BaseModel):
    id: str
    journeyType: JourneyType

    segments: list[JourneySegment] = Field(min_length=1)

    departureTime: datetime
    arrivalTime: datetime

    totalDurationSeconds: int = Field(ge=0, strict=True)
    transferCount: int = Field(ge=0, strict=True)


    @model_validator(mode="after")
    def validateJourney(self):
        # All journey timestamps must be timezone-aware.
        if (
            self.departureTime.utcoffset() is None
            or self.arrivalTime.utcoffset() is None
        ):
            raise ValueError("Journey timestamps must include a timezone")

        # Journey boundaries must match the segment boundaries.
        if self.departureTime != self.segments[0].startTime:
            raise ValueError(
                "departureTime must match the first segment's startTime"
            )

        if self.arrivalTime != self.segments[-1].endTime:
            raise ValueError(
                "arrivalTime must match the last segment's endTime"
            )

        # Segments must be continuous and chronologically ordered.
        for previousSegment, currentSegment in zip(
            self.segments,
            self.segments[1:]
        ):
            if previousSegment.endTime != currentSegment.startTime:
                raise ValueError(
                    "Adjacent segments must connect in time"
                )
            if previousSegment.kind == "WALK" and currentSegment.kind == "WALK":
                raise ValueError(
                    "Consecutive WALK segments must be merged"
                )

        # Segment identifiers must be unique within a journey.
        segmentIds = [segment.id for segment in self.segments]

        if len(segmentIds) != len(set(segmentIds)):
            raise ValueError("Segment IDs must be unique")

        # Total duration includes driving, walking, waiting, and parking.
        actualDuration = (
            self.arrivalTime - self.departureTime
        ).total_seconds()

        if actualDuration != self.totalDurationSeconds:
            raise ValueError(
                "totalDurationSeconds must match journey timestamps"
            )

        # Every additional transit ride counts as a transfer.
        transitRideCount = sum(
            segment.kind == "TRANSIT"
            for segment in self.segments
        )
        expectedTransfers = max(0, transitRideCount - 1)

        if self.transferCount != expectedTransfers:
            raise ValueError(
                "transferCount does not match the transit segments"
            )

        # Journey type should describe the modes actually used.
        hasDriving = any(
            segment.kind == "DRIVE" for segment in self.segments
        )
        hasTransit = transitRideCount > 0

        if hasDriving and hasTransit:
            expectedType = "DRIVE_WALK_TRANSIT"
        elif hasDriving:
            expectedType = "DRIVE_WALK"
        elif hasTransit:
            expectedType = "WALK_TRANSIT"
        else:
            expectedType = "WALK_ONLY"

        if self.journeyType != expectedType:
            raise ValueError(
                f"journeyType must be {expectedType}"
            )

        return self

