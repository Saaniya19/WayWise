from pydantic import BaseModel, Field

from app.models.journey import Journey, JourneySegment, SegmentKind
from app.models.planning import AccessConstraint, TravelConstraints

SEGMENT_TIME_TOLERANCE_SECONDS = 60
DRIVING_TIME_TOLERANCE_SECONDS = 120
BIKING_TIME_TOLERANCE_SECONDS = 60


class ConstraintResult(BaseModel):
    isValid: bool
    violations: list[str] = Field(default_factory=list)
    
    
def getInitialFinalSegments(
    journey: Journey,
    kind: SegmentKind,
) -> tuple[list[JourneySegment], list[JourneySegment]]:

    initialSegments = []
    finalSegments = []

    # Contiguous segments at the start of the journey.
    for segment in journey.segments:
        if segment.kind != kind:
            break

        initialSegments.append(segment)

    # Contiguous segments at the end of the journey.
    for segment in reversed(journey.segments):
        if segment.kind != kind:
            break

        finalSegments.append(segment)

    finalSegments.reverse()

    # Avoid counting a single-mode journey twice.
    if len(initialSegments) == len(journey.segments):
        finalSegments = []

    return initialSegments, finalSegments


def checkInitialFinalLimits(
    journey: Journey,
    kind: SegmentKind,
    constraint: AccessConstraint,
) -> list[str]:

    initialSegments, finalSegments = getInitialFinalSegments(
        journey, kind
    )

    if kind == "DRIVE":
        modeName = "driving"
        tolerance = DRIVING_TIME_TOLERANCE_SECONDS
    else:
        modeName = "biking"
        tolerance = BIKING_TIME_TOLERANCE_SECONDS

    if constraint.limitType == "TIME":
        initialLimit = constraint.maxInitialSeconds
        finalLimit = constraint.maxFinalSeconds
    else:
        initialLimit = constraint.maxInitialKm
        finalLimit = constraint.maxFinalKm

    violations = []

    violations.extend(
        checkModeLimit(
            initialSegments,
            initialLimit,
            "Initial",
            modeName,
            constraint.limitType,
            tolerance,
        )
    )

    violations.extend(
        checkModeLimit(
            finalSegments,
            finalLimit,
            "Final",
            modeName,
            constraint.limitType,
            tolerance,
        )
    )

    return violations


def checkModeLimit(
    segments: list[JourneySegment],
    maxValue: float | int | None,
    label: str,
    modeName: str,
    limitType: str,
    timeToleranceSeconds: int,
) -> list[str]:

    violations = []

    if maxValue is None or not segments:
        return violations

    if limitType == "TIME":
        actual = sum(s.durationSeconds for s in segments)

        if actual > maxValue + timeToleranceSeconds:
            violations.append(
                f"{label} {modeName} time exceeds {maxValue} seconds"
            )

    else:
        if any(s.distanceMeters is None for s in segments):
            violations.append(
                f"{label} {modeName} distance cannot be verified"
            )
            return violations

        actualKm = sum(s.distanceMeters for s in segments) / 1000

        if actualKm > maxValue:
            violations.append(
                f"{label} {modeName} distance exceeds {maxValue} km"
            )

    return violations



def checkConstraints(
    journey: Journey,
    constraints: TravelConstraints,
) -> ConstraintResult:

    violations = []

    # Walking limits apply to each individual segment.
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

    # Maximum number of transit transfers.
    if constraints.transit is not None:
        if journey.transferCount > constraints.transit.maxTransfers:
            violations.append(
                f"Journey has {journey.transferCount} transfers; "
                f"maximum is {constraints.transit.maxTransfers}"
            )

    # Initial/final driving constraints.
    if constraints.driving is not None:
        violations.extend(
            checkInitialFinalLimits(
                journey,
                "DRIVE",
                constraints.driving,
            )
        )

    # Initial/final biking constraints.
    if constraints.biking is not None:
        violations.extend(
            checkInitialFinalLimits(
                journey,
                "BIKE",
                constraints.biking,
            )
        )

    return ConstraintResult(
        isValid=len(violations) == 0,
        violations=violations,
    )
