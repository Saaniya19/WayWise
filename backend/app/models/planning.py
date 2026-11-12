from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator, ConfigDict

from app.models.common import Location
from app.models.journey import Journey


class DrivingConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limitType: Literal["TIME", "DISTANCE"]

    # Distance limits in kilometres
    maxInitialDrivingKm: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    maxFinalDrivingKm: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )

    # Time limits in seconds
    maxInitialDrivingSeconds: int | None = Field(
        default=None, ge=0, strict=True
    )
    maxFinalDrivingSeconds: int | None = Field(
        default=None, ge=0, strict=True
    )

    @model_validator(mode="after")
    def validateDrivingLimit(self):
        distanceFields = (
            self.maxInitialDrivingKm,
            self.maxFinalDrivingKm,
        )
        timeFields = (
            self.maxInitialDrivingSeconds,
            self.maxFinalDrivingSeconds,
        )

        if self.limitType == "TIME":
            if any(value is not None for value in distanceFields):
                raise ValueError(
                    "TIME constraints cannot specify distance limits"
                )
            if all(value is None for value in timeFields):
                raise ValueError("A driving time limit is required")

        else:
            if any(value is not None for value in timeFields):
                raise ValueError(
                    "DISTANCE constraints cannot specify time limits"
                )
            if all(value is None for value in distanceFields):
                raise ValueError("A driving distance limit is required")

        return self


class TransitConstraint(BaseModel):
    maxTransfers: int = Field(ge=0, strict=True)


class TravelConstraints(BaseModel):
    maxWalkingSegmentMinutes: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    maxBikingSegmentMinutes: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    driving: DrivingConstraint | None = None
    transit: TransitConstraint | None = None



class PlanningRequest(BaseModel):
    origin: Location
    destination: Location
    constraints: TravelConstraints


class PlanningError(BaseModel):
    code: str
    message: str
    journeyId: str | None

class PlanningResponse(BaseModel):
    requestId: str
    departureTime: datetime
    journeys: list[Journey] = Field(default_factory=list)
    isPartial: bool = False
    errors: list[PlanningError] = Field(default_factory=list)

    @model_validator(mode="after")
    def validateResponse(self):
        if self.departureTime.utcoffset() is None:
            raise ValueError(
                "departureTime must include timezone information"
            )

        journeyIds = [journey.id for journey in self.journeys]

        if len(journeyIds) != len(set(journeyIds)):
            raise ValueError(
                "Journey IDs must be unique within a response"
            )

        return self
