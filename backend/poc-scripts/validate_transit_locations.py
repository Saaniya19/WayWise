"""Validate the WayWise transit_locations.json catalogue (Pydantic v2)."""
import json
import sys
from datetime import date
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Source(Strict):
    type: Literal['official_gtfs', 'official_station_page']
    url: HttpUrl
    lastVerified: date

class ParkingSummary(Strict):
    status: Literal['unknown', 'free', 'paid_only', 'none']
    sourceUrl: HttpUrl | None
    lastVerified: date | None

    @model_validator(mode='after')
    def verified_has_source(self):
        if self.status != 'unknown' and (self.sourceUrl is None or self.lastVerified is None):
            raise ValueError('Verified parking status needs sourceUrl and lastVerified')
        return self

class Station(Strict):
    id: str = Field(min_length=1)
    gtfsStopIds: dict[str, str]
    name: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    services: list[Literal['GO', 'UP']] = Field(min_length=1)
    source: Source
    parking: ParkingSummary
    
class ParkingSite(Strict):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    stationId: str = Field(min_length=1)
    latitude: float | None = Field(ge=-90, le=90)
    longitude: float | None = Field(ge=-180, le=180)
    coordinatesStatus: Literal['not_verified', 'verified']
    parkingType: Literal['free_customer', 'paid', 'unknown']
    publishedSpaceCount: int | None = Field(ge=0)
    realTimeSpacesAvailable: int | None = Field(ge=0)
    source: Source

    @model_validator(mode='after')
    def verified_coordinates_required(self):
        if self.coordinatesStatus == 'verified' and (self.latitude is None or self.longitude is None):
            raise ValueError('Verified parking coordinates must be provided')
        return self

class WalkingAccess(Strict):
    distanceMeters: float = Field(ge=0)
    durationSeconds: float = Field(ge=0)
    source: Source

class Candidate(Strict):
    id: str = Field(min_length=1)
    parkingSiteId: str = Field(min_length=1)
    boardingStopId: str = Field(min_length=1)
    walkingAccess: WalkingAccess | None
    status: Literal['pending_walking_verification', 'verified']
    source: Source

    @model_validator(mode='after')
    def verified_walking_required(self):
        if self.status == 'verified' and self.walkingAccess is None:
            raise ValueError('Verified candidate needs walkingAccess')
        return self

class Catalogue(Strict):
    schemaVersion: Literal['1.0']
    generatedOn: date
    notes: str
    transitStations: list[Station]
    parkingSites: list[ParkingSite]
    transferCandidates: list[Candidate]
    
    @model_validator(mode='after')
    def validate_references(self):
        stations = {s.id: s for s in self.transitStations}
        lots = {p.id: p for p in self.parkingSites}
        candidate_ids = {c.id for c in self.transferCandidates}
        if len(stations) != len(self.transitStations) or len(lots) != len(self.parkingSites) or len(candidate_ids) != len(self.transferCandidates):
            raise ValueError('Duplicate station, parking site, or transfer candidate ID')
        for lot in self.parkingSites:
            if lot.stationId not in stations:
                raise ValueError(f'Parking site {lot.id} references missing station {lot.stationId}')
        for c in self.transferCandidates:
            if c.parkingSiteId not in lots or c.boardingStopId not in stations:
                raise ValueError(f'Candidate {c.id} references a missing parking site or station')
            if lots[c.parkingSiteId].stationId != c.boardingStopId:
                raise ValueError(f'Candidate {c.id} connects a parking site to the wrong station')
            if c.status == 'verified' and lots[c.parkingSiteId].coordinatesStatus != 'verified':
                raise ValueError(f'Candidate {c.id} needs verified parking coordinates')
        return self

if __name__ == '__main__':
    path = Path(sys.argv[1] if len(sys.argv) > 1 else 'transit_locations.json')
    catalogue = Catalogue.model_validate(json.loads(path.read_text(encoding='utf-8')))
    print(f'Valid v{catalogue.schemaVersion}: {len(catalogue.transitStations)} stations, {len(catalogue.parkingSites)} parking sites, {len(catalogue.transferCandidates)} candidates')
