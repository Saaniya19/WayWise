from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator, ConfigDict

from app.models.common import Location
from app.models.journey import Journey


class AccessConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limitType: Literal["TIME", "DISTANCE"]

    # Distance limits in kilometres
    maxInitialKm: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )

    maxFinalKm: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )

    # Time limits in seconds
    maxInitialSeconds: int | None = Field(
        default=None, ge=0, strict=True
    )

    maxFinalSeconds: int | None = Field(
        default=None, ge=0, strict=True
    )

    @model_validator(mode="after")
    def validateLimit(self):
        distanceFields = (
            self.maxInitialKm,
            self.maxFinalKm,
        )

        timeFields = (
            self.maxInitialSeconds,
            self.maxFinalSeconds,
        )

        if self.limitType == "TIME":
            if any(value is not None for value in distanceFields):
                raise ValueError(
                    "TIME constraints cannot specify distance limits"
                )

            if all(value is None for value in timeFields):
                raise ValueError("A time limit is required")

        else:
            if any(value is not None for value in timeFields):
                raise ValueError(
                    "DISTANCE constraints cannot specify time limits"
                )

            if all(value is None for value in distanceFields):
                raise ValueError("A distance limit is required")

        return self


class DrivingConstraint(AccessConstraint):
    requiresParking: bool = Field(default=True, strict=True)


class BikingConstraint(AccessConstraint):
    pass


class TransitConstraint(BaseModel):
    maxTransfers: int = Field(ge=0, strict=True)


class TravelConstraints(BaseModel):
    maxWalkingSegmentMinutes: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    biking: BikingConstraint | None = None
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
