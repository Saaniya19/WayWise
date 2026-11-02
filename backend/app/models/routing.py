'''
General overview of routing classes:

RouteResults consist of Routes (ie. entire journey)
Routes consist of Legs (ie. stop A to stop B)
Legs consist of Segments (eg. WALK, DRIVE, TRANSIT, etc.)
Segments contain optional TransitDetails
'''

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TravelMode(str, Enum):
    DRIVE = "DRIVE"
    WALK = "WALK"
    TRANSIT = "TRANSIT"


class Coordinates(BaseModel):
    latitude: float
    longitude: float


class TransitStop(BaseModel):
    name: str | None = None
    location: Coordinates | None = None


class TransitDetails(BaseModel):
    departure_stop: TransitStop | None = None
    arrival_stop: TransitStop | None = None
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    line_name: str | None = None
    agency_name: str | None = None
    vehicle_type: str | None = None


class Segment(BaseModel):
    mode: TravelMode
    duration_seconds: int | None = None
    distance_meters: int | None = None
    transit_details: TransitDetails | None = None


class Leg(BaseModel):
    segments: list[Segment] = Field(default_factory=list)


class Route(BaseModel):
    duration_seconds: int | None = None
    distance_meters: int | None = None
    legs: list[Leg] = Field(default_factory=list)
    transfer_count: int | None = None


class RouteResult(BaseModel):
    routes: list[Route] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
