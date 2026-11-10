from pydantic import BaseModel

class ConstraintResult(BaseModel):
    isValid: bool
    violations: list[str]

def checkConstraints(
    journey: Journey,
    constraints: TravelConstraints
) -> ConstraintResult:
    violations = []

    # Check driving time/distance limits,
    # walking limits, and other supported constraints.

    return ConstraintResult(
        isValid=len(violations) == 0,
        violations=violations
    )
