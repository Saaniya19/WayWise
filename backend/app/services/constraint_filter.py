from pydantic import BaseModel, Field

from app.models.journey import Journey, JourneySegment
from app.models.planning import TravelConstraints


SEGMENT_TIME_TOLERANCE_SECONDS = 60
DRIVING_TIME_TOLERANCE_SECONDS = 120


class ConstraintResult(BaseModel):
    isValid: bool
    violations: list[str] = Field(default_factory=list)


def checkDrive(
    segments: list[JourneySegment],
    maxValue: float | int | None,
    label: str,
    limitType: str,
) -> list[str]:
    violations = []

    if maxValue is None or not segments:
        return violations

    if limitType == "TIME":
        actual = sum(s.durationSeconds for s in segments)

        if actual > maxValue + DRIVING_TIME_TOLERANCE_SECONDS:
            violations.append(
                f"{label} driving time exceeds {maxValue} seconds"
            )

    else:
        if any(s.distanceMeters is None for s in segments):
            violations.append(
                f"{label} driving distance cannot be verified"
            )
            return violations

        actualKm = sum(s.distanceMeters for s in segments) / 1000

        if actualKm > maxValue:
            violations.append(
                f"{label} driving distance exceeds {maxValue} km"
            )

    return violations



def checkConstraints(
    journey: Journey,
    constraints: TravelConstraints
) -> ConstraintResult:
    violations = []

    # Walking and biking limits apply to each individual segment.
    for segment in journey.segments:
        if (
            segment.kind == "WALK"
            and constraints.maxWalkingSegmentMinutes is not None
        ):
            maxSeconds = constraints.maxWalkingSegmentMinutes * 60

            if segment.durationSeconds > maxSeconds + SEGMENT_TIME_TOLERANCE_SECONDS:
                violations.append(
                    f"Walking segment {segment.id} exceeds "
                    f"{constraints.maxWalkingSegmentMinutes} minutes"
                )

        elif (
            segment.kind == "BIKE"
            and constraints.maxBikingSegmentMinutes is not None
        ):
            maxSeconds = constraints.maxBikingSegmentMinutes * 60

            if segment.durationSeconds > maxSeconds + SEGMENT_TIME_TOLERANCE_SECONDS:
                violations.append(
                    f"Biking segment {segment.id} exceeds "
                    f"{constraints.maxBikingSegmentMinutes} minutes"
                )

    # Maximum number of transit transfers.
    if constraints.transit is not None:
        if journey.transferCount > constraints.transit.maxTransfers:
            violations.append(
                f"Journey has {journey.transferCount} transfers; "
                f"maximum is {constraints.transit.maxTransfers}"
            )

    # Initial/final driving constraints.
    if constraints.driving is not None:
        driving = constraints.driving

        # Contiguous driving segments at the start of the journey.
        initialDrive = []
        for segment in journey.segments:
            if segment.kind != "DRIVE":
                break
            initialDrive.append(segment)

        # Contiguous driving segments at the end of the journey.
        finalDrive = []
        for segment in reversed(journey.segments):
            if segment.kind != "DRIVE":
                break
            finalDrive.append(segment)

        # Avoid counting a drive-only journey twice.
        if len(initialDrive) == len(journey.segments):
            finalDrive = []

        if driving.limitType == "TIME":
            violations.extend(
                checkDrive(
                    initialDrive,
                    driving.maxInitialDrivingSeconds,
                    "Initial",
                    "TIME",
                )
            )
            violations.extend(
                checkDrive(
                    finalDrive,
                    driving.maxFinalDrivingSeconds,
                    "Final",
                    "TIME",
                )
            )
        else:
            violations.extend(
                checkDrive(
                    initialDrive,
                    driving.maxInitialDrivingKm,
                    "Initial",
                    "DISTANCE",
                )
            )
            violations.extend(
                checkDrive(
                    finalDrive,
                    driving.maxFinalDrivingKm,
                    "Final",
                    "DISTANCE",
                )
            )


    return ConstraintResult(
        isValid=len(violations) == 0,
        violations=violations
    )
