from typing import Literal

from pydantic import BaseModel, Field

from app.models.common import Location


# ORIGIN: origin -> station. DESTINATION: station -> destination.
CandidateEnd = Literal["ORIGIN", "DESTINATION"]

AccessMode = Literal["DRIVE"]


class TransitStation(BaseModel):
    """A station from the transit catalogue, with its best-known parking."""
    id: str
    name: str
    location: Location
    services: list[str] = Field(default_factory=list)
    parkingStatus: str = "unknown"
    parkingSiteId: str | None = None


class TransferCandidateDistance(BaseModel):
    """Travel time and distance between one end of the trip and a station."""
    station: TransitStation
    end: CandidateEnd
    mode: AccessMode

    # False when there is no way to travel between the two points,
    # which is different from being too far.
    routeExists: bool
    durationSeconds: int | None = Field(default=None, ge=0)
    distanceMeters: int | None = Field(default=None, ge=0)


class TransferCandidate(BaseModel):
    """A station reachable within the user's limit for that end and mode."""
    station: TransitStation
    end: CandidateEnd
    accessMode: AccessMode = "DRIVE"
    requiresParking: bool = False

    durationSeconds: int = Field(ge=0)
    distanceMeters: int | None = Field(default=None, ge=0)

